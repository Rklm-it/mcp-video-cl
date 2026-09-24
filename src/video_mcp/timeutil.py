"""Timestamp parsing and formatting."""

from __future__ import annotations

import re

_HMS = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:[.,]\d+)?)$")
_UNITS = re.compile(r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+(?:\.\d+)?)s?)?$")


def parse_time(value: str | float | int | None) -> float | None:
    """Parse "90", "1:30", "01:02:03.5", "1h2m3s", "95s" into seconds."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value < 0:
            raise ValueError(f"Negative timestamp: {value}")
        return float(value)
    text = str(value).strip().lower()
    if not text:
        return None
    match = _HMS.match(text)
    if match:
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes) * 60 + float(seconds.replace(",", "."))
    match = _UNITS.match(text)
    if match and any(match.groups()):
        hours, minutes, seconds = match.groups()
        return int(hours or 0) * 3600 + int(minutes or 0) * 60 + float(seconds or 0)
    raise ValueError(f"Cannot parse timestamp {value!r}; use seconds or mm:ss / hh:mm:ss")


def fmt_time(seconds: float | None) -> str:
    """Format seconds as m:ss or h:mm:ss."""
    if seconds is None:
        return "?"
    total = int(max(0.0, seconds))
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
