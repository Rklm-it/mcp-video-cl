"""Scene pictures: generated from a prompt, or taken from a file/URL the user supplies."""

from __future__ import annotations

import base64
import io
import random
import textwrap
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx
from PIL import Image, ImageDraw, ImageFont

from .. import sources as src_mod
from . import gemini, net
from .config import reels_settings

W, H = 1080, 1920
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_MEDIA_BYTES = 300 * 1024 * 1024


def generate(prompt: str, out: Path, seed: int, context: bool = True) -> Path:
    """Generate a 1080x1920 picture for `prompt` and save it as PNG. `context=False` skips the scene setting."""
    provider = reels_settings.images
    setting = reels_settings.scene_context if context else ""
    full = ". ".join(filter(None, [prompt, setting, reels_settings.image_style]))
    if provider == "pollinations":
        return fit(_cut_watermark(Image.open(io.BytesIO(_pollinations(full, seed)))), out)
    elif provider == "gemini":
        raw = _gemini(full)
    elif provider == "openai":
        raw = _openai(full)
    elif provider == "placeholder":
        return placeholder(prompt, out, seed)
    else:
        raise ValueError(f"Unknown REELS_IMAGES={provider!r} (pollinations, gemini, openai, placeholder)")
    return fit(Image.open(io.BytesIO(raw)), out)


ASPECTS = {"1:1": (1024, 1024), "9:16": (1080, 1920), "16:9": (1920, 1080), "3:4": (1080, 1440), "4:3": (1440, 1080)}


def picture(prompt: str, aspect: str = "1:1", seed: int = 1) -> Image.Image:
    """One standalone picture (avatar, cover, post image): the prompt as is, no scene setting added."""
    provider = reels_settings.images
    width, height = ASPECTS[aspect]
    if provider == "gemini":
        raw = _gemini(prompt, aspect)
    elif provider == "openai":
        raw = _openai(prompt)
    elif provider == "pollinations":
        raw = _pollinations(prompt, seed, width, height)
    else:
        return Image.new("RGB", (width, height), "gray")
    return Image.open(io.BytesIO(raw)).convert("RGB")


def fit(image: Image.Image, out: Path) -> Path:
    """Scale and centre-crop to exactly 1080x1920."""
    image = image.convert("RGB")
    scale = max(W / image.width, H / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left, top = (image.width - W) // 2, (image.height - H) // 2
    image.crop((left, top, left + W, top + H)).save(out, format="PNG")
    return out


# Anonymous Pollinations ignores nologo and stamps its logo in the bottom-right corner
POLLINATIONS_WATERMARK = 0.07


def _cut_watermark(image: Image.Image) -> Image.Image:
    """Drop the bottom strip with the logo; fit() then scales the rest back to 1080x1920."""
    return image.crop((0, 0, image.width, round(image.height * (1 - POLLINATIONS_WATERMARK))))


def _pollinations(prompt: str, seed: int, width: int = W, height: int = H) -> bytes:
    resp = net.get(
        f"https://image.pollinations.ai/prompt/{quote(prompt)}",
        params={"width": width, "height": height, "nologo": "true", "seed": seed},
        timeout=180,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.content


def _gemini(prompt: str, aspect: str = "9:16") -> bytes:
    resp = net.post(
        gemini.url(f"models/{reels_settings.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": aspect}},
        },
        timeout=180,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Gemini error {resp.status_code}: {resp.text[:300]}")
    for cand in resp.json().get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            data = (part.get("inlineData") or part.get("inline_data") or {}).get("data")
            if data:
                return base64.b64decode(data)
    raise RuntimeError("Gemini returned no image (prompt may have been blocked)")


def _openai(prompt: str) -> bytes:
    s = reels_settings
    if not s.openai_key:
        raise ValueError("Set REELS_OPENAI_API_KEY")
    resp = net.post(
        f"{s.openai_base_url.rstrip('/')}/images/generations",
        headers={"Authorization": f"Bearer {s.openai_key}"},
        json={"model": s.openai_image_model, "prompt": prompt, "n": 1,
              **({"size": s.openai_image_size} if s.openai_image_size else {})},
        timeout=240,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Images API error {resp.status_code}: {resp.text[:300]}")
    item = resp.json()["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    return net.get(item["url"], timeout=120).content


def placeholder(text: str, out: Path, seed: int) -> Path:
    """Gradient with the prompt written on it: free, offline, handy for testing the pipeline."""
    rnd = random.Random(seed)
    top = tuple(rnd.randint(20, 120) for _ in range(3))
    bottom = tuple(rnd.randint(120, 230) for _ in range(3))
    image = Image.new("RGB", (W, H))
    draw = ImageDraw.Draw(image)
    for y in range(H):
        k = y / H
        draw.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * k) for a, b in zip(top, bottom)))
    try:
        font = ImageFont.truetype(reels_settings.font, 54)
    except OSError:
        font = ImageFont.load_default()
    draw.multiline_text((80, 300), textwrap.fill(text, 28), font=font, fill="white", spacing=14)
    image.save(out, format="PNG")
    return out


VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}
PAGE_CUT_SECONDS = 90  # a scene never needs more of someone's video than this


def _cut_from_page(ref: str, start: float, dest: Path) -> Path:
    """A video page (YouTube, VK, X, TikTok…): download through yt-dlp like the analysis tools do and cut
    [start, start + 90 s] without the original sound — the reel puts its own voice over it."""
    import subprocess

    if dest.is_file():  # re-render of the same reel: the cut is already here
        return dest
    src = src_mod.resolve(ref)
    video, offset = src_mod.get_video_file(src, start, start + PAGE_CUT_SECONDS)
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{max(0.0, start - offset):.3f}",
         "-t", str(PAGE_CUT_SECONDS), "-i", str(video), "-an", "-c:v", "libx264", "-preset", "veryfast",
         "-crf", "20", "-pix_fmt", "yuv420p", str(dest)], capture_output=True, text=True)
    if proc.returncode != 0 or not dest.is_file():
        raise ValueError(f"Could not cut {ref}: {proc.stderr.strip()[-300:]}")
    return dest


def fetch_media(ref: str, dest_stem: Path, start: float = 0.0) -> tuple[Path, str, float]:
    """Get a user-supplied picture or clip: a direct URL, a video page, or a file from the local video folder.
    Returns (path, "image" | "video", where to start inside the returned file)."""
    parsed = urlparse(ref)
    suffix = Path(parsed.path).suffix.lower()
    if parsed.scheme in ("http", "https") and suffix not in IMAGE_EXTS | VIDEO_EXTS:
        try:
            return _cut_from_page(ref, start, dest_stem.with_suffix(".cut.mp4")), "video", 0.0
        except src_mod.SourceError as exc:
            page_error = str(exc)  # not a page yt-dlp knows: maybe a direct file without an extension
    else:
        page_error = ""
    if parsed.scheme in ("http", "https"):
        src_mod._check_public_host(parsed.hostname or "")
        suffix = Path(parsed.path).suffix.lower() or ".bin"
        path = dest_stem.with_suffix(suffix)
        with httpx.stream("GET", ref, timeout=300, follow_redirects=True) as resp:
            resp.raise_for_status()
            size = 0
            with path.open("wb") as f:
                for chunk in resp.iter_bytes():
                    size += len(chunk)
                    if size > MAX_MEDIA_BYTES:
                        raise ValueError(f"{ref} is larger than {MAX_MEDIA_BYTES // 2**20} MB")
                    f.write(chunk)
            ctype = resp.headers.get("content-type", "")
        if ctype.startswith("text/html"):
            raise ValueError(f"{ref} is a web page, not a picture or a video"
                             + (f"; the video downloader said: {page_error}" if page_error else ""))
        kind = "image" if ctype.startswith("image/") or suffix in IMAGE_EXTS else "video"
    else:
        path = src_mod._resolve_local(ref).path
        kind = "image" if path.suffix.lower() in IMAGE_EXTS else "video"
    if kind == "image":
        return fit(Image.open(path), dest_stem.with_suffix(".png")), "image", 0.0
    return path, "video", start
