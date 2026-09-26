"""Assemble a reel with ffmpeg: animated scenes, voice, burned-in subtitles, ad marking."""

from __future__ import annotations

import logging
import re
import subprocess
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from ..frames import probe_duration
from . import images, tts
from .config import reels_settings
from .jobs import ad_marker

log = logging.getLogger("video_mcp.reels")

FPS = 30
PAUSE = 0.25  # silence after each scene, seconds
_MOTIONS = (
    # zoom in to the centre
    "z='min(1+0.0010*on,1.18)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # zoom out from the centre
    "z='max(1.18-0.0010*on,1)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
    # slow pan left to right on a slightly zoomed picture
    "z='1.12':x='(iw-iw/zoom)*on/{frames}':y='ih/2-(ih/zoom/2)'",
)


@dataclass
class SceneOut:
    visual: Path
    kind: str  # image | video
    audio: Path
    words: list[tts.Word]
    duration: float = 0.0


def _ff(*args: str) -> None:
    proc = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                          capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.strip()[-600:]}")


def render(job: dict, workdir: Path, offer: dict | None, progress: Callable[[float, str], None]) -> Path:
    scenes = job["scenes"]
    outs: list[SceneOut] = []
    for i, scene in enumerate(scenes):
        progress(0.05 + 0.6 * i / len(scenes), f"Scene {i + 1}/{len(scenes)}: picture and voice")
        stem = workdir / f"scene{i:02d}"
        if scene.get("media"):
            visual, kind = images.fetch_media(scene["media"], stem)
        else:
            png = stem.with_suffix(".png")
            if not png.exists():  # keep pictures when a reel is re-rendered
                images.generate(scene["image_prompt"], png, seed=zlib.crc32(f"{job['id']}:{i}".encode()))
            visual, kind = png, "image"
        audio = stem.with_suffix(".mp3")
        words = tts.synthesize(scene["text"], audio)
        outs.append(SceneOut(visual, kind, audio, words))

    progress(0.7, "Joining the voice-over")
    voice, words = _join_voice(outs, workdir)
    total = sum(o.duration for o in outs)

    progress(0.75, "Animating scenes")
    clips = [_scene_clip(o, i, workdir) for i, o in enumerate(outs)]
    concat = workdir / "clips.txt"
    concat.write_text("".join(f"file '{c.name}'\n" for c in clips))
    silent = workdir / "silent.mp4"
    _ff("-f", "concat", "-safe", "0", "-i", str(concat), "-c", "copy", str(silent))

    progress(0.85, "Subtitles and ad marking")
    subs = workdir / "subs.ass"
    subs.write_text(build_ass(words, _font_family(reels_settings.font)))
    vf = [f"ass={subs}:fontsdir={Path(reels_settings.font).parent}"]
    if offer:
        marker = workdir / "marker.txt"
        marker.write_text(ad_marker(offer))
        vf.append(_drawtext(marker, size=_fit_size(ad_marker(offer), 30), color="white", box="black@0.55", y="60"))
        spans = offer_spans(scenes, [o.duration for o in outs])
        if spans and offer.get("banner"):
            banner = workdir / "banner.txt"
            banner.write_text(offer["banner"])
            enable = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in spans)
            vf.append(_drawtext(banner, size=_fit_size(offer["banner"], 46), color="black", box="0xFFD400@0.95", y="h-300",
                                enable=enable))
    final = workdir / "reel.mp4"
    _ff("-i", str(silent), "-i", str(voice), "-vf", ",".join(vf),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(final))
    for leftover in (*clips, silent, concat):
        leftover.unlink(missing_ok=True)
    return final


def _join_voice(outs: list[SceneOut], workdir: Path) -> tuple[Path, list[tts.Word]]:
    """Convert each scene's speech to WAV with a short pause, concatenate, shift word timings."""
    words: list[tts.Word] = []
    parts = []
    offset = 0.0
    for i, o in enumerate(outs):
        wav = workdir / f"voice{i:02d}.wav"
        _ff("-i", str(o.audio), "-af", f"apad=pad_dur={PAUSE}", "-ar", "44100", "-ac", "1", str(wav))
        o.duration = probe_duration(wav)
        words += [tts.Word(w.text, w.start + offset, w.end + offset) for w in o.words]
        offset += o.duration
        parts.append(wav)
    lst = workdir / "voice.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
    voice = workdir / "voice.wav"
    _ff("-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(voice))
    for p in (*parts, lst):
        p.unlink(missing_ok=True)
    return voice, words


def _scene_clip(o: SceneOut, index: int, workdir: Path) -> Path:
    out = workdir / f"clip{index:02d}.mp4"
    common = ["-t", f"{o.duration:.3f}", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
              "-pix_fmt", "yuv420p", "-r", str(FPS)]
    if o.kind == "video":
        _ff("-stream_loop", "-1", "-i", str(o.visual),
            "-vf", f"scale={images.W}:{images.H}:force_original_aspect_ratio=increase,"
                   f"crop={images.W}:{images.H},fps={FPS},setsar=1", *common, str(out))
    else:
        frames = max(1, round(o.duration * FPS))
        motion = _MOTIONS[index % len(_MOTIONS)].format(frames=frames)
        _ff("-loop", "1", "-framerate", str(FPS), "-i", str(o.visual),
            "-vf", f"scale={images.W * 3 // 2}:{images.H * 3 // 2},"
                   f"zoompan={motion}:d=1:s={images.W}x{images.H}:fps={FPS},setsar=1",
            *common, str(out))
    return out


def _drawtext(textfile: Path, size: int, color: str, box: str, y: str, enable: str | None = None) -> str:
    parts = [
        f"drawtext=fontfile={reels_settings.font}", f"textfile={textfile}", "expansion=none",
        f"fontsize={size}", f"fontcolor={color}", "box=1", f"boxcolor={box}", "boxborderw=14",
        "x=(w-tw)/2", f"y={y}",
    ]
    if enable:
        parts.append(f"enable='{enable}'")
    return ":".join(parts)


def _fit_size(text: str, size: int, max_width: int = images.W - 120) -> int:
    """Largest font size (up to `size`) at which the text fits the frame width on one line."""
    while size > 18:
        try:
            width = ImageFont.truetype(reels_settings.font, size).getlength(text)
        except OSError:
            return size
        if width <= max_width:
            break
        size -= 2
    return size


def offer_spans(scenes: list[dict], durations: list[float]) -> list[tuple[float, float]]:
    """Time ranges of the scenes flagged `offer`, for the banner."""
    spans, t = [], 0.0
    for scene, d in zip(scenes, durations):
        if scene.get("offer"):
            spans.append((t, t + d))
        t += d
    return spans


# ---------------------------------------------------------------- subtitles


def _font_family(path: str) -> str:
    try:
        return ImageFont.truetype(path, 10).getname()[0]
    except OSError:
        return "DejaVu Sans"


def _ass_time(t: float) -> str:
    cs = max(0, round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def chunk_words(words: list[tts.Word], max_words: int = 3, max_chars: int = 18) -> list[tuple[str, float, float]]:
    """Group words into short subtitle lines, breaking after punctuation."""
    chunks: list[tuple[str, float, float]] = []
    cur: list[tts.Word] = []
    for w in words:
        if cur and (len(cur) >= max_words or len(" ".join(x.text for x in cur + [w])) > max_chars):
            chunks.append((" ".join(x.text for x in cur), cur[0].start, cur[-1].end))
            cur = []
        cur.append(w)
        if re.search(r"[.,!?;:…—]$", w.text):
            chunks.append((" ".join(x.text for x in cur), cur[0].start, cur[-1].end))
            cur = []
    if cur:
        chunks.append((" ".join(x.text for x in cur), cur[0].start, cur[-1].end))
    # close small gaps so subtitles do not flicker between words
    fixed = []
    for i, (text, start, end) in enumerate(chunks):
        if i + 1 < len(chunks) and chunks[i + 1][1] - end < 0.35:
            end = chunks[i + 1][1]
        fixed.append((text, start, end))
    return fixed


def build_ass(words: list[tts.Word], font_family: str) -> str:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {images.W}
PlayResY: {images.H}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{font_family},82,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,6,3,2,70,70,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for text, start, end in chunk_words(words):
        clean = text.replace("{", "(").replace("}", ")").replace("\n", " ").upper()
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Main,,0,0,0,,{clean}")
    return header + "\n".join(lines) + "\n"
