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
from .config import reels_settings

W, H = 1080, 1920
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_MEDIA_BYTES = 300 * 1024 * 1024


def generate(prompt: str, out: Path, seed: int) -> Path:
    """Generate a 1080x1920 picture for `prompt` and save it as PNG."""
    provider = reels_settings.images
    full = f"{prompt}. {reels_settings.image_style}" if reels_settings.image_style else prompt
    if provider == "pollinations":
        raw = _pollinations(full, seed)
    elif provider == "gemini":
        raw = _gemini(full)
    elif provider == "openai":
        raw = _openai(full)
    elif provider == "placeholder":
        return placeholder(prompt, out, seed)
    else:
        raise ValueError(f"Unknown REELS_IMAGES={provider!r} (pollinations, gemini, openai, placeholder)")
    return fit(Image.open(io.BytesIO(raw)), out)


def fit(image: Image.Image, out: Path) -> Path:
    """Scale and centre-crop to exactly 1080x1920."""
    image = image.convert("RGB")
    scale = max(W / image.width, H / image.height)
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left, top = (image.width - W) // 2, (image.height - H) // 2
    image.crop((left, top, left + W, top + H)).save(out, format="PNG")
    return out


def _pollinations(prompt: str, seed: int) -> bytes:
    resp = httpx.get(
        f"https://image.pollinations.ai/prompt/{quote(prompt)}",
        params={"width": W, "height": H, "nologo": "true", "seed": seed},
        timeout=180,
        follow_redirects=True,
    )
    resp.raise_for_status()
    return resp.content


def _gemini(prompt: str) -> bytes:
    s = reels_settings
    if not s.gemini_key:
        raise ValueError("Set REELS_GEMINI_API_KEY")
    resp = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_image_model}:generateContent",
        headers={"x-goog-api-key": s.gemini_key},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "9:16"}},
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
    resp = httpx.post(
        f"{s.openai_base_url.rstrip('/')}/images/generations",
        headers={"Authorization": f"Bearer {s.openai_key}"},
        json={"model": s.openai_image_model, "prompt": prompt, "size": "1024x1536", "n": 1},
        timeout=240,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Images API error {resp.status_code}: {resp.text[:300]}")
    item = resp.json()["data"][0]
    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    return httpx.get(item["url"], timeout=120).content


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


def fetch_media(ref: str, dest_stem: Path) -> tuple[Path, str]:
    """Get a user-supplied picture or clip: a URL or a file from the local video folder.
    Returns (path, "image" | "video")."""
    parsed = urlparse(ref)
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
        kind = "image" if ctype.startswith("image/") or suffix in IMAGE_EXTS else "video"
    else:
        path = src_mod._resolve_local(ref).path
        kind = "image" if path.suffix.lower() in IMAGE_EXTS else "video"
    if kind == "image":
        return fit(Image.open(path), dest_stem.with_suffix(".png")), "image"
    return path, "video"
