"""Subtitle parsing (json3 / vtt / srt), formatting and Whisper fallback."""

from __future__ import annotations

import html
import json
import logging
import re
import threading
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import settings
from .timeutil import fmt_time

log = logging.getLogger(__name__)


@dataclass
class Segment:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- parsing

_TAG = re.compile(r"<[^>]+>")
_CUE_TIME = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)


def _clock(h: str | None, m: str, s: str, frac: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")[:3]) / 1000


def parse_json3(data: str) -> list[Segment]:
    """YouTube's json3 caption format."""
    payload = json.loads(data)
    segments: list[Segment] = []
    for event in payload.get("events", []):
        if "segs" not in event or event.get("aAppend"):
            continue
        text = "".join(seg.get("utf8", "") for seg in event["segs"])
        text = " ".join(text.split())
        if not text:
            continue
        start = event.get("tStartMs", 0) / 1000
        end = start + event.get("dDurationMs", 0) / 1000
        segments.append(Segment(start, end, text))
    return _dedupe(segments)


def parse_cues(data: str) -> list[Segment]:
    """WebVTT or SRT. Handles YouTube's rolling auto-captions (repeated lines)."""
    segments: list[Segment] = []
    for block in re.split(r"\n\s*\n", data.replace("\r\n", "\n").replace("\r", "\n")):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            match = _CUE_TIME.search(line)
            if not match:
                continue
            g = match.groups()
            start, end = _clock(*g[0:4]), _clock(*g[4:8])
            text_lines = [html.unescape(_TAG.sub("", t)).strip() for t in lines[i + 1 :]]
            text_lines = [t for t in text_lines if t]
            if text_lines:
                segments.append(Segment(start, end, " ".join(text_lines)))
            break
    return _dedupe(segments)


def _dedupe(segments: list[Segment]) -> list[Segment]:
    """Drop rolling-caption repeats: keep only the part of a cue not already said."""
    result: list[Segment] = []
    for seg in segments:
        if result:
            prev = result[-1]
            if seg.text == prev.text:
                prev.end = max(prev.end, seg.end)
                continue
            if seg.text.startswith(prev.text):
                seg = Segment(seg.start, seg.end, seg.text[len(prev.text) :].strip())
            else:
                # Rolling captions repeat the previous line at the start of the next cue.
                words_prev, words_new = prev.text.split(), seg.text.split()
                for k in range(min(len(words_prev), len(words_new) - 1), 0, -1):
                    if words_prev[-k:] == words_new[:k] and k >= 3:
                        seg = Segment(seg.start, seg.end, " ".join(words_new[k:]))
                        break
            if not seg.text:
                prev.end = max(prev.end, seg.end)
                continue
        result.append(seg)
    return result


def parse_subtitles(data: str, ext: str) -> list[Segment]:
    ext = ext.lower().lstrip(".")
    if ext == "json3":
        return parse_json3(data)
    return parse_cues(data)


# ---------------------------------------------------------------- formatting


def slice_segments(segments: list[Segment], start: float | None, end: float | None) -> list[Segment]:
    return [
        s
        for s in segments
        if (start is None or s.end > start) and (end is None or s.start < end)
    ]


def text_between(segments: list[Segment], start: float, end: float) -> str:
    return " ".join(s.text for s in segments if s.start >= start and s.start < end).strip()


def format_transcript(
    segments: list[Segment], group_seconds: float = 20.0, max_chars: int | None = None
) -> tuple[str, float | None]:
    """Render as "[m:ss] text" paragraphs of ~group_seconds.

    Returns (text, resume_at): resume_at is the timestamp where output was cut
    because of max_chars, or None if everything fitted.
    """
    lines: list[str] = []
    size = 0
    group: list[Segment] = []

    def flush() -> str:
        return f"[{fmt_time(group[0].start)}] " + " ".join(s.text for s in group)

    for seg in segments:
        if group and seg.start - group[0].start >= group_seconds:
            line = flush()
            if max_chars is not None and size + len(line) > max_chars and lines:
                return "\n".join(lines), group[0].start
            lines.append(line)
            size += len(line) + 1
            group = []
        group.append(seg)
    if group:
        line = flush()
        if max_chars is not None and size + len(line) > max_chars and lines:
            return "\n".join(lines), group[0].start
        lines.append(line)
    return "\n".join(lines), None


def save_segments(path: Path, segments: list[Segment], meta: dict) -> None:
    path.write_text(
        json.dumps({"meta": meta, "segments": [s.to_dict() for s in segments]}, ensure_ascii=False),
        encoding="utf-8",
    )


def load_segments(path: Path) -> tuple[list[Segment], dict] | None:
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [Segment(**s) for s in payload["segments"]], payload.get("meta", {})


# ---------------------------------------------------------------- whisper

_whisper_model = None
_whisper_lock = threading.Lock()


def whisper_available() -> bool:
    if not settings.whisper_enabled:
        return False
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def transcribe(audio_path: Path, language: str | None = None, offset: float = 0.0) -> tuple[list[Segment], str]:
    """Transcribe with faster-whisper. Returns (segments, detected_language)."""
    global _whisper_model
    from faster_whisper import WhisperModel

    with _whisper_lock:
        if _whisper_model is None:
            settings.models_dir.mkdir(parents=True, exist_ok=True)
            log.info("Loading Whisper model %s", settings.whisper_model)
            _whisper_model = WhisperModel(
                settings.whisper_model,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
                download_root=str(settings.models_dir),
            )
        segments_iter, info = _whisper_model.transcribe(
            str(audio_path), language=language or None, vad_filter=True, beam_size=5
        )
        segments = [
            Segment(round(s.start + offset, 2), round(s.end + offset, 2), s.text.strip())
            for s in segments_iter
            if s.text.strip()
        ]
    return segments, info.language
