"""Animated scenes: the scene picture becomes the first frame of a short AI video (Veo 3.1)."""

from __future__ import annotations

import base64
import io
import logging
import time
from pathlib import Path

import httpx
from PIL import Image

from . import gemini, net
from .config import reels_settings

log = logging.getLogger("video_mcp.reels")

VEO_DURATIONS = (4, 6, 8)
POLL_SECONDS = 10
TIMEOUT_SECONDS = 600
NEGATIVE = "text, letters, captions, subtitles, watermark, logo, distorted faces, extra fingers"


def _with_context(prompt: str) -> str:
    return f"{prompt}. {reels_settings.scene_context}" if reels_settings.scene_context else prompt


def clip_seconds(scene_seconds: float) -> int:
    """Shortest allowed clip that covers the scene (longer scenes hold the last frame)."""
    return next((d for d in VEO_DURATIONS if d >= scene_seconds), VEO_DURATIONS[-1])


def animate(image: Path, prompt: str, seconds: float, out: Path) -> Path:
    provider = reels_settings.video
    if provider == "veo":
        return _veo(image, prompt, clip_seconds(seconds), out)
    if provider == "openai":
        return _openai_videos(image, prompt, clip_seconds(seconds), out)
    raise ValueError(f"Video generation is off (REELS_VIDEO={provider!r}); set REELS_VIDEO=veo or openai")


def _veo(image: Path, prompt: str, seconds: int, out: Path) -> Path:
    s = reels_settings
    frame = Image.open(image).convert("RGB")
    frame.thumbnail((720, 1280))
    buf = io.BytesIO()
    frame.save(buf, format="PNG")
    body = {
        "instances": [{
            "prompt": f"{_with_context(prompt)}. Smooth cinematic camera motion, natural movement, vertical 9:16.",
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
        poll = net.get(gemini.url(name), headers=gemini.headers(), timeout=60)
        if poll.status_code >= 400:
            raise RuntimeError(f"Veo status error {poll.status_code}: {poll.text[:300]}")
        op = poll.json()
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


def _openai_videos(image: Path, prompt: str, seconds: int, out: Path) -> Path:
    """The /videos API as ProxyAPI serves it (OpenRouter's format): JSON with the scene picture as
    frame_images[first_frame]; the job goes pending -> completed and lists its files in unsigned_urls.
    Checked on ProxyAPI: input_reference is silently ignored (the clip ignores the picture)."""
    s = reels_settings
    if not s.video_key:
        raise ValueError("Set REELS_VIDEO_API_KEY (or REELS_GEMINI_API_KEY)")
    base, auth = s.video_base_url.rstrip("/"), {"Authorization": f"Bearer {s.video_key}"}
    width, height = (1080, 1920) if s.veo_resolution == "1080p" else (720, 1280)
    buf = io.BytesIO()
    Image.open(image).convert("RGB").resize((width, height), Image.Resampling.LANCZOS).save(buf, "JPEG", quality=90)
    frame = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    resp = httpx.post(f"{base}/videos", headers=auth, timeout=120, json={
        "model": s.veo_model,
        "prompt": f"{_with_context(prompt)}. Smooth cinematic camera motion, natural movement, vertical 9:16. Avoid: {NEGATIVE}.",
        "duration": seconds,
        "resolution": s.veo_resolution,
        "aspect_ratio": "9:16",
        "generate_audio": False,  # the voice-over replaces it, and silent clips are cheaper
        "frame_images": [{"type": "image_url", "image_url": {"url": frame}, "frame_type": "first_frame"}],
    })
    if resp.status_code >= 400:
        raise RuntimeError(f"Video API error {resp.status_code}: {resp.text[:300]}")
    video_id = resp.json()["id"]
    deadline = time.monotonic() + TIMEOUT_SECONDS
    while True:
        time.sleep(POLL_SECONDS)
        poll = net.get(f"{base}/videos/{video_id}", headers=auth, timeout=60)
        if poll.status_code >= 400:
            raise RuntimeError(f"Video status error {poll.status_code}: {poll.text[:300]}")
        job = poll.json()
        if job.get("status") == "completed":
            break
        if job.get("status") in ("failed", "cancelled", "expired") or job.get("error"):
            error = job.get("error") or job.get("status")
            raise RuntimeError(f"Video failed: {error.get('message', error) if isinstance(error, dict) else error}")
        if time.monotonic() > deadline:
            raise RuntimeError(f"Video did not finish in {TIMEOUT_SECONDS // 60} minutes")
    url = (job.get("unsigned_urls") or [f"{base}/videos/{video_id}/content"])[0]
    video = net.get(url, headers=auth, timeout=300, follow_redirects=True)
    if video.status_code >= 400:
        raise RuntimeError(f"Video download failed {video.status_code}: {video.text[:300]}")
    out.write_bytes(video.content)
    return out
