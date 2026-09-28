"""Improve a photo with the reels image model (Gemini) and send the result to the Telegram review chat.

Run inside the container, the photo must be in ./data on the host (= /data in the container):
    docker compose exec video-mcp python /app/deploy/enhance-photo.py /data/photo.jpg
or, if deploy/ is not in the image:
    docker compose exec -T video-mcp python - /data/photo.jpg < deploy/enhance-photo.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import httpx

from video_mcp.reels import gemini, net
from video_mcp.reels.config import reels_settings as s

PROMPT = (
    "Retouch this real photo of a man into a high-quality square profile picture (avatar). "
    "Keep his face, identity, hair, clothing and pose exactly the same — do not change who he is. "
    "Crop to head and shoulders, centred. Increase sharpness and detail, remove noise and blur, "
    "natural skin tones, soft even light, softly blurred background with no other people. "
    "Photorealistic, no text, no filters, no cartoon."
)


def main() -> None:
    src = Path(sys.argv[1])
    mime = "image/png" if src.suffix.lower() == ".png" else "image/jpeg"
    resp = net.post(
        gemini.url(f"models/{s.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(src.read_bytes()).decode()}},
                {"text": PROMPT},
            ]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}},
        },
        timeout=180,
    )
    if resp.status_code >= 400:
        sys.exit(f"Gemini error {resp.status_code}: {resp.text[:300]}")
    data = next((
        (p.get("inlineData") or p.get("inline_data") or {}).get("data")
        for c in resp.json().get("candidates", []) for p in c.get("content", {}).get("parts", [])
        if (p.get("inlineData") or p.get("inline_data"))
    ), None)
    if not data:
        sys.exit("Gemini returned no image")
    out = src.with_name(src.stem + "-enhanced.png")
    out.write_bytes(base64.b64decode(data))
    print(f"saved {out}")
    if s.tg_token and s.tg_review_chat:
        with out.open("rb") as f:
            r = httpx.post(f"https://api.telegram.org/bot{s.tg_token}/sendDocument",
                           data={"chat_id": s.tg_review_chat, "caption": "Аватар после улучшения"},
                           files={"document": (out.name, f, "image/png")}, timeout=60)
        print("sent to Telegram" if r.status_code == 200 else f"Telegram error {r.status_code}")


if __name__ == "__main__":
    main()
