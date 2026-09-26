"""Voice-over with word timings (the timings drive the subtitles)."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass
from pathlib import Path

import httpx

from .config import reels_settings


@dataclass
class Word:
    text: str
    start: float
    end: float


def synthesize(text: str, out: Path) -> list[Word]:
    """Write speech for `text` to `out` (mp3) and return word timings relative to its start."""
    provider = reels_settings.tts
    if provider == "edge":
        return asyncio.run(_edge(text, out))
    if provider == "elevenlabs":
        return _elevenlabs(text, out)
    raise ValueError(f"Unknown REELS_TTS={provider!r} (use edge or elevenlabs)")


async def _edge(text: str, out: Path) -> list[Word]:
    import edge_tts

    comm = edge_tts.Communicate(
        text, reels_settings.edge_voice, rate=reels_settings.edge_rate, boundary="WordBoundary"
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


def _elevenlabs(text: str, out: Path) -> list[Word]:
    s = reels_settings
    if not (s.elevenlabs_key and s.elevenlabs_voice):
        raise ValueError("Set REELS_ELEVENLABS_API_KEY and REELS_ELEVENLABS_VOICE_ID")
    resp = httpx.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{s.elevenlabs_voice}/with-timestamps",
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
