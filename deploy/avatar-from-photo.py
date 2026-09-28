"""Channel avatar from the owner's photo: the image model keeps the face and restyles the picture.
Results go to /data/avatar-<n>.png and, as files, to the Telegram review chat.

Run inside the container (photo = URL or a path under /data):
    docker compose exec -T video-mcp python - <photo-url-or-path> < deploy/avatar-from-photo.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import httpx

from video_mcp.reels import gemini, net
from video_mcp.reels.config import reels_settings as s

KEEP = (
    "Use the man from this photo. Keep his face, identity, age, hairstyle and beard exactly the same — "
    "it must be clearly the same person. Square avatar for a Telegram channel about personal finance, "
    "must read well as a small circle: head and shoulders, centered, close-up. "
    "No text, no letters, no digits, no watermark. "
)

STYLES = [
    "Professional studio portrait photo: soft warm light, shallow depth of field, calm confident friendly "
    "smile, dark navy sweater, clean muted warm orange-beige background. Photorealistic, not a cartoon.",
    "Premium editorial illustration in a realistic painterly style (like a magazine columnist portrait): "
    "natural proportions, subtle brush texture, warm colours, soft teal background. Not a cartoon.",
    "Clean modern portrait photo with soft rim light, light-grey background, holding a simple calculator "
    "near the chest, smart trustworthy look. Photorealistic, not a cartoon.",
]


def load(src: str) -> tuple[bytes, str]:
    if src.startswith("http"):
        resp = httpx.get(src, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "image/jpeg").split(";")[0]
    path = Path(src)
    return path.read_bytes(), "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def restyle(photo: bytes, mime: str, style: str) -> bytes | None:
    resp = net.post(
        gemini.url(f"models/{s.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(photo).decode()}},
                {"text": KEEP + style},
            ]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}},
        },
        timeout=180,
    )
    if resp.status_code >= 400:
        print(f"Gemini error {resp.status_code}: {resp.text[:300]}")
        return None
    data = next((
        (p.get("inlineData") or p.get("inline_data") or {}).get("data")
        for c in resp.json().get("candidates", []) for p in c.get("content", {}).get("parts", [])
        if (p.get("inlineData") or p.get("inline_data"))
    ), None)
    return base64.b64decode(data) if data else None


def main() -> None:
    photo, mime = load(sys.argv[1])
    for n, style in enumerate(STYLES, 1):
        img = restyle(photo, mime, style)
        if not img:
            print(f"#{n}: no image")
            continue
        out = Path(f"/data/avatar-{n}.png")
        out.write_bytes(img)
        print(f"#{n}: saved {out}")
        if s.tg_token and s.tg_review_chat:
            r = httpx.post(f"https://api.telegram.org/bot{s.tg_token}/sendDocument",
                           data={"chat_id": s.tg_review_chat, "caption": f"Аватар по фото, вариант {n}"},
                           files={"document": (out.name, img, "image/png")}, timeout=60)
            print(f"#{n}: " + ("sent to Telegram" if r.status_code == 200 else f"Telegram error {r.status_code}"))


if __name__ == "__main__":
    main()
