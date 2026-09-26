"""Animated scenes: the scene picture becomes the first frame of a short AI video (Veo 3.1)."""

from __future__ import annotations

import base64
import io
import logging
import time
from pathlib import Path

import httpx
from PIL import Image

from . import gemini
from .config import reels_settings

log = logging.getLogger("video_mcp.reels")

VEO_DURATIONS = (4, 6, 8)
POLL_SECONDS = 10
TIMEOUT_SECONDS = 600
NEGATIVE = "text, letters, captions, subtitles, watermark, logo, distorted faces, extra fingers"


def clip_seconds(scene_seconds: float) -> int:
    """Shortest allowed clip that covers the scene (longer scenes hold the last frame)."""
    return next((d for d in VEO_DURATIONS if d >= scene_seconds), VEO_DURATIONS[-1])


def animate(image: Path, prompt: str, seconds: float, out: Path) -> Path:
    provider = reels_settings.video
    if provider == "veo":
        return _veo(image, prompt, clip_seconds(seconds), out)
    raise ValueError(f"Video generation is off (REELS_VIDEO={provider!r}); set REELS_VIDEO=veo")


def _veo(image: Path, prompt: str, seconds: int, out: Path) -> Path:
    s = reels_settings
    frame = Image.open(image).convert("RGB")
    frame.thumbnail((720, 1280))
    buf = io.BytesIO()
    frame.save(buf, format="PNG")
    body = {
        "instances": [{
            "prompt": f"{prompt}. Smooth cinematic camera motion, natural movement, vertical 9:16.",
            "image": {"bytesBase64Encoded": base64.b64encode(buf.getvalue()).decode(), "mimeType": "image/png"},
        }],
        "parameters": {"aspectRatio": "9:16", "durationSeconds": seconds, "resolution": s.veo_resolution,
                       "negativePrompt": NEGATIVE},
    }
    resp = httpx.post(gemini.url(f"models/{s.veo_model}:predictLongRunning"), headers=gemini.headers(),
                      json=body, timeout=120)
    if resp.status_code >= 400:
        raise RuntimeError(f"Veo error {resp.status_code}: {resp.text[:300]}")
    name = resp.json()["name"]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        time.sleep(POLL_SECONDS)
        op = httpx.get(gemini.url(name), headers=gemini.headers(), timeout=60).json()
        if op.get("error"):
            raise RuntimeError(f"Veo failed: {op['error'].get('message', op['error'])}")
        if op.get("done"):
            break
        if time.monotonic() > deadline:
            raise RuntimeError(f"Veo did not finish in {TIMEOUT_SECONDS // 60} minutes")
    result = op.get("response", {}).get("generateVideoResponse", {})
    samples = result.get("generatedSamples") or []
    if not samples:
        reasons = result.get("raiMediaFilteredReasons") or ["no video returned"]
        raise RuntimeError(f"Veo returned no video: {'; '.join(map(str, reasons))}")
    return gemini.download(samples[0]["video"]["uri"], out)
