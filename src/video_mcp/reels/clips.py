"""Clips for clipping platforms (Kliply and the like): a fragment of someone's stream or podcast becomes a
vertical 9:16 video with the original sound, big subtitles from the transcript, an optional hook line on
top and the advertiser's banner (a picture or a green-screen video) laid over the frame."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

import httpx

from .. import sources as src_mod
from . import images, render, tts
from .config import reels_settings

W, H = images.W, images.H
LAYOUTS = ("blur", "crop")
MAX_SECONDS = 180


def clips_dir() -> Path:
    d = reels_settings.root / "clips"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _ff(*args: str) -> None:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-500:]}")


def subtitle_words(segments, start: float, end: float) -> list[tts.Word]:
    """Words of the transcript inside [start, end], timed from the clip's own zero."""
    words: list[tts.Word] = []
    for seg in segments:
        if seg.end <= start or seg.start >= end or not seg.text.strip():
            continue
        s, e = max(seg.start, start) - start, min(seg.end, end) - start
        if e - s < 0.2:
            continue
        for w in tts.proportional_words(seg.text, e - s, 0, 0):
            words.append(tts.Word(w.text, w.start + s, w.end + s))
    return words


def _fetch(ref: str, dest: Path) -> Path:
    """A banner: a URL (Google Drive share links included) or a path under the video folder."""
    if ref.startswith("http"):
        if "drive.google.com" in ref and "/file/d/" in ref:
            file_id = ref.split("/file/d/")[1].split("/")[0]
            ref = f"https://drive.google.com/uc?export=download&id={file_id}"
        resp = httpx.get(ref, timeout=120, follow_redirects=True)
        resp.raise_for_status()
        kind = resp.headers.get("content-type", "")
        suffix = ".mp4" if "video" in kind else ".png" if "png" in kind else ".jpg" if "jpeg" in kind else ""
        path = dest.with_suffix(suffix or Path(ref.split("?")[0]).suffix or ".mp4")
        path.write_bytes(resp.content)
        return path
    return src_mod._resolve_local(ref).path


def make_clip(source: str, start: float, end: float, *, layout: str = "blur", subtitles: bool = True,
              hook: str = "", banner: str = "", banner_position: str = "top", banner_width: float = 0.8,
              green_screen: bool = True, lang: str | None = None) -> Path:
    if end <= start:
        raise ValueError("end must be after start")
    if end - start > MAX_SECONDS:
        raise ValueError(f"A clip is at most {MAX_SECONDS} s")
    if layout not in LAYOUTS:
        raise ValueError(f"layout: one of {LAYOUTS}")
    src = src_mod.resolve(source)
    video, offset = src_mod.get_video_file(src, start, end)
    stem = clips_dir() / f"clip-{time.strftime('%Y%m%d-%H%M%S')}"
    duration = end - start

    inputs = ["-ss", f"{max(0.0, start - offset):.3f}", "-t", f"{duration:.3f}", "-i", str(video)]
    if layout == "blur":
        chain = (f"[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                 f"boxblur=24:2,eq=brightness=-0.08[bg];[b]scale={W}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2[v0]")
    else:
        chain = f"[0:v]scale=-2:{H},crop={W}:{H}[v0]"
    last = "v0"

    if banner:
        path = _fetch(banner, stem.with_name(stem.name + "-banner"))
        is_video = path.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv")
        inputs += (["-stream_loop", "-1"] if is_video else ["-loop", "1"]) + ["-i", str(path)]
        key = "chromakey=0x00FF00:0.18:0.08," if green_screen and is_video else ""
        y = "160" if banner_position == "top" else f"H-h-{int(H * 0.24)}"
        chain += (f";[1:v]{key}scale={int(W * banner_width)}:-2,format=rgba[bn];"
                  f"[{last}][bn]overlay=(W-w)/2:{y}:shortest=1[v1]")
        last = "v1"

    filters = [chain]
    if hook:
        text = stem.with_name(stem.name + "-hook.txt")
        text.write_text(hook)
        y = "460" if banner and banner_position == "top" else "110"  # under a top banner
        filters.append(f"[{last}]drawtext=fontfile={reels_settings.font}:textfile={text}:expansion=none:"
                       f"fontsize={render._fit_size(hook, 64)}:fontcolor=white:box=1:boxcolor=black@0.6:"
                       f"boxborderw=18:x=(w-tw)/2:y={y}[v2]")
        last = "v2"
    if subtitles:
        segments, _ = src_mod.get_transcript(src, lang, start=start, end=end)
        words = subtitle_words(segments, start, end)
        if words:
            ass = stem.with_suffix(".ass")
            ass.write_text(render.build_ass(words, render._font_family(reels_settings.font)))
            filters.append(f"[{last}]ass={ass}:fontsdir={Path(reels_settings.font).parent}[v3]")
            last = "v3"

    out = stem.with_suffix(".mp4")
    _ff(*inputs, "-filter_complex", ";".join(filters), "-map", f"[{last}]", "-map", "0:a?",
        "-t", f"{duration:.3f}", "-r", "30", "-c:v", "libx264", "-preset", "veryfast", "-crf", "21",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out))
    for extra in stem.parent.glob(stem.name + "*"):
        if extra != out:
            extra.unlink(missing_ok=True)
    return out
