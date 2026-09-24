"""Frame extraction with ffmpeg: scene-change detection, uniform sampling, dedupe."""

from __future__ import annotations

import io
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from .config import settings


@dataclass
class Frame:
    time: float  # seconds on the original video's timeline
    jpeg: bytes
    width: int
    height: int
    dhash: int
    colors: tuple[int, ...]  # 4x4 RGB thumbnail, catches colour changes dHash (grayscale) misses


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    try:
        return float(out)
    except ValueError:
        return 0.0


_PTS = re.compile(r"pts_time:([\d.]+)")
_SCORE = re.compile(r"lavfi\.scene_score=([\d.]+)")


def detect_scenes(path: Path, start: float, end: float, threshold: float) -> list[tuple[float, float]]:
    """Return [(time_in_file, score)] of scene changes between start and end (file timeline)."""
    span = end - start
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-loglevel", "error"]
    if span > 15 * 60:
        # Long ranges: compare keyframes only, which is an order of magnitude faster.
        cmd += ["-skip_frame", "nokey"]
        vf = f"scale=160:-2,select='gt(scene\\,{threshold})',metadata=print:file=-"
    else:
        fps = 4 if span <= 120 else 2
        vf = f"fps={fps},scale=160:-2,select='gt(scene\\,{threshold})',metadata=print:file=-"
    cmd += ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(path), "-an", "-sn", "-dn", "-vf", vf]
    cmd += ["-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg scene detection failed: {proc.stderr.strip()[-500:]}")
    result: list[tuple[float, float]] = []
    pending: float | None = None
    for line in proc.stdout.splitlines():
        m = _PTS.search(line)
        if m:
            pending = float(m.group(1))
            continue
        m = _SCORE.search(line)
        if m and pending is not None:
            result.append((start + pending, float(m.group(1))))
            pending = None
    return result


def uniform_times(start: float, end: float, count: int) -> list[float]:
    if count <= 0:
        return []
    if count == 1:
        return [start + (end - start) / 2]
    step = (end - start) / count
    return [start + step * (i + 0.5) for i in range(count)]


def choose_times(
    scenes: list[tuple[float, float]], start: float, end: float, max_frames: int
) -> list[float]:
    """Pick up to max_frames timestamps: strongest scene changes, spread over the range,
    topped up with uniform samples where the video is static."""
    span = max(end - start, 0.001)
    min_gap = span / (max_frames * 2.5)
    chosen: list[float] = [min(start + 0.5, start + span / 2)]
    for t, _score in sorted(scenes, key=lambda x: -x[1]):
        if len(chosen) >= max_frames:
            break
        if all(abs(t - c) >= min_gap for c in chosen):
            chosen.append(t)
    if len(chosen) < max_frames:
        # Fill the largest gaps so static stretches still get coverage.
        target = max(max_frames // 2, min(max_frames, 4))
        while len(chosen) < target:
            points = sorted(chosen) + [end]
            prev = start
            best_gap, best_mid = 0.0, None
            for p in points:
                if p - prev > best_gap:
                    best_gap, best_mid = p - prev, (p + prev) / 2
                prev = p
            if best_mid is None or best_gap < min_gap * 2:
                break
            chosen.append(best_mid)
    return sorted(chosen)


def dhash(image: Image.Image) -> int:
    small = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    pixels = small.tobytes()
    bits = 0
    for row in range(8):
        for col in range(8):
            bits = (bits << 1) | (pixels[row * 9 + col] > pixels[row * 9 + col + 1])
    return bits


def color_signature(image: Image.Image) -> tuple[int, ...]:
    return tuple(image.convert("RGB").resize((4, 4), Image.Resampling.BOX).tobytes())


def extract_frame(path: Path, time_in_file: float, width: int) -> tuple[bytes, int, int, int, tuple[int, ...]]:
    width = max(64, min(width, settings.frame_max_width))
    proc = subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", f"{max(0.0, time_in_file):.3f}", "-i", str(path),
            "-frames:v", "1", "-an", "-sn",
            "-vf", f"scale='min({width},iw)':-2",
            "-f", "image2pipe", "-vcodec", "png", "-",
        ],
        capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"ffmpeg could not grab frame at {time_in_file:.2f}s: {proc.stderr.decode()[-300:]}")
    image = Image.open(io.BytesIO(proc.stdout)).convert("RGB")
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=settings.jpeg_quality, optimize=True)
    return buf.getvalue(), image.width, image.height, dhash(image), color_signature(image)


def grab_frames(path: Path, times_in_file: list[float], width: int, offset: float = 0.0) -> list[Frame]:
    """Extract frames at the given file timestamps; `offset` maps them to the video timeline."""
    duration = probe_duration(path)
    safe = [min(t, max(0.0, duration - 0.05)) if duration else t for t in times_in_file]
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda t: extract_frame(path, t, width), safe))
    return [Frame(t + offset, *data) for t, data in zip(safe, results)]


def is_similar(a: Frame, b: Frame, max_distance: int = 4, max_color_diff: float = 10.0) -> bool:
    if bin(a.dhash ^ b.dhash).count("1") > max_distance:
        return False
    diff = sum(abs(x - y) for x, y in zip(a.colors, b.colors)) / max(len(a.colors), 1)
    return diff <= max_color_diff


def dedupe(frames: list[Frame]) -> list[Frame]:
    """Drop frames that look the same as the previous kept frame (static shots, talking heads)."""
    kept: list[Frame] = []
    for frame in frames:
        if kept and is_similar(frame, kept[-1]):
            continue
        kept.append(frame)
    return kept
