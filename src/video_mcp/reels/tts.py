"""Voice-over with word timings (the timings drive the subtitles)."""

from __future__ import annotations

import asyncio
import base64
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import net
from .config import reels_settings


@dataclass
class Word:
    text: str
    start: float
    end: float


def synthesize(text: str, out: Path, voice: str | None = None) -> list[Word]:
    """Write speech for `text` to `out` (mp3) and return word timings relative to its start.

    `voice` overrides the configured voice with a spec (see `parse_voice`), e.g. for voice samples."""
    provider, model, name = parse_voice(voice) if voice else (reels_settings.tts, "", "")
    if provider == "edge":
        words = asyncio.run(_edge(text, out, name))
    elif provider == "elevenlabs":
        words = _elevenlabs(text, out, name)
    elif provider == "openai":
        words = _openai(text, out, model, name)
    else:
        raise ValueError(f"Unknown REELS_TTS={provider!r} (use edge, openai or elevenlabs)")
    return _speed_up(out, words, reels_settings.voice_speed)


def parse_voice(spec: str) -> tuple[str, str, str]:
    """'edge:ru-RU-DmitryNeural' | 'elevenlabs:<voice id>' | '<gateway model>:<voice>' (OpenAI-compatible,
    e.g. 'gemini/gemini-2.5-flash-preview-tts:Charon') -> (provider, model, voice)."""
    head, _, name = spec.rpartition(":")
    if not head or not name:
        raise ValueError(f"Voice spec {spec!r}: expected '<provider or model>:<voice>'")
    if head in ("edge", "elevenlabs"):
        return head, "", name
    return "openai", head, name


def _speed_up(out: Path, words: list[Word], speed: float) -> list[Word]:
    """Faster speech sounds livelier and keeps shorts short; the pitch stays the same (atempo)."""
    if abs(speed - 1.0) < 0.01:
        return words
    tmp = out.with_name(out.stem + ".speed.mp3")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out),
                    "-filter:a", f"atempo={speed:.3f}", "-c:a", "libmp3lame", "-b:a", "128k", str(tmp)],
                   check=True)
    tmp.replace(out)
    return [Word(w.text, w.start / speed, w.end / speed) for w in words]


async def _edge(text: str, out: Path, voice: str = "") -> list[Word]:
    import edge_tts

    comm = edge_tts.Communicate(
        text, voice or reels_settings.edge_voice, rate=reels_settings.edge_rate, boundary="WordBoundary"
    )
    words: list[Word] = []
    with out.open("wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 1e7  # 100 ns units
                words.append(Word(chunk["text"], start, start + chunk["duration"] / 1e7))
    if not words:
        words = _even_words(text, 0.0, max(1.0, len(text) / 15))
    return words


def _elevenlabs(text: str, out: Path, voice: str = "") -> list[Word]:
    s = reels_settings
    voice = voice or s.elevenlabs_voice
    if not (s.elevenlabs_key and voice):
        raise ValueError("Set REELS_ELEVENLABS_API_KEY and REELS_ELEVENLABS_VOICE_ID")
    resp = net.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps",
        params={"output_format": "mp3_44100_128"},
        headers={"xi-api-key": s.elevenlabs_key},
        json={"text": text, "model_id": s.elevenlabs_model},
        timeout=180,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ElevenLabs error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    out.write_bytes(base64.b64decode(data["audio_base64"]))
    alignment = data.get("alignment") or data.get("normalized_alignment") or {}
    return words_from_chars(
        alignment.get("characters", []),
        alignment.get("character_start_times_seconds", []),
        alignment.get("character_end_times_seconds", []),
    )


def _openai(text: str, out: Path, model: str = "", voice: str = "") -> list[Word]:
    """OpenAI-compatible /audio/speech. It returns no timings, so words are spread over the audio
    by their length, which is close enough for 2-3 word subtitle lines."""
    from ..frames import probe_duration

    s = reels_settings
    if not s.openai_key:
        raise ValueError("Set REELS_OPENAI_API_KEY (and REELS_OPENAI_BASE_URL for a gateway)")
    model, voice = model or s.openai_tts_model, voice or s.openai_tts_voice
    body = {"model": model, "voice": voice, "input": text}
    if not model.startswith("gemini/"):
        # Timeweb answers 500 to any response_format for Gemini voices; they come as WAV by default
        body["response_format"] = "mp3"
    if s.openai_tts_instructions:
        body["instructions"] = s.openai_tts_instructions
    url, auth = f"{s.openai_base_url.rstrip('/')}/audio/speech", {"Authorization": f"Bearer {s.openai_key}"}
    resp = net.post(url, headers=auth, json=body, timeout=180)
    if net.retryable(resp) and "instructions" in body:
        # Some gateways fail on the voice-style field: better a plainer voice than no reel
        body.pop("instructions")
        resp = net.post(url, headers=auth, json=body, timeout=180)
    if resp.status_code >= 400:
        raise RuntimeError(f"Speech API error {resp.status_code}: {resp.text[:300]}")
    if resp.content[:4] == b"RIFF":  # WAV: keep the mp3 file the rest of the pipeline expects
        wav = out.with_suffix(".wav")
        wav.write_bytes(resp.content)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav),
                        "-c:a", "libmp3lame", "-b:a", "128k", str(out)], check=True)
        wav.unlink()
    else:
        out.write_bytes(resp.content)
    return proportional_words(text, probe_duration(out))


def proportional_words(text: str, duration: float, lead: float = 0.08, tail: float = 0.12) -> list[Word]:
    """Word timings spread by word length (+1 for the gap) over the spoken part of the audio."""
    parts = text.split()
    if not parts:
        return []
    start, end = lead, max(lead + 0.2, duration - tail)
    weights = [len(p) + 1 for p in parts]
    per = (end - start) / sum(weights)
    words, t = [], start
    for p, w in zip(parts, weights):
        words.append(Word(p, t, t + w * per))
        t += w * per
    return words


def words_from_chars(chars: list[str], starts: list[float], ends: list[float]) -> list[Word]:
    """Group per-character timings (ElevenLabs alignment) into words."""
    words: list[Word] = []
    buf, w_start, w_end = "", 0.0, 0.0
    for ch, st, en in zip(chars, starts, ends):
        if ch.isspace():
            if buf:
                words.append(Word(buf, w_start, w_end))
                buf = ""
            continue
        if not buf:
            w_start = st
        buf += ch
        w_end = en
    if buf:
        words.append(Word(buf, w_start, w_end))
    return words


def _even_words(text: str, start: float, duration: float) -> list[Word]:
    parts = text.split()
    step = duration / max(len(parts), 1)
    return [Word(p, start + i * step, start + (i + 1) * step) for i, p in enumerate(parts)]
