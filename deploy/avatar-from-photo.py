"""Channel avatar from the owner's photo: the image model keeps the face and restyles the picture.
Results go to /data/avatar-<n>.png and, as files, to the Telegram review chat.

Run inside the container (photo = URL or a path under /data):
    docker compose exec -T video-mcp python - <photo-url-or-path> [--cartoon] ["Eyes are grey, hair is dark blond."] \
        < deploy/avatar-from-photo.py
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import httpx

from video_mcp.reels import gemini, net
from video_mcp.reels.config import reels_settings as s

KEEP = (
    "Edit this exact photo, do not redraw the person. The face must stay pixel-identical: same eyes, nose, "
    "mouth, skin, facial hair, hairline and expression — do not beautify, slim, age or change it in any way. "
    "Only change what is listed below. Crop to a square head-and-shoulders avatar, face centered and large, "
    "so it reads well as a small circle. No text, no letters, no watermark. "
    "If the photo is black-and-white or has filters (glitch stripes, colour fringing, heavy grain), "
    "remove the filters and noise and restore natural realistic colour with a natural skin tone. "
)

STYLES = [
    "Replace only the background with a clean soft warm orange-beige studio backdrop and even out the "
    "lighting to soft daylight. Keep the clothes as they are.",
    "Replace only the background with a soft muted teal studio backdrop, add gentle studio lighting, "
    "and change the clothing to a plain dark navy sweater.",
    "Replace only the background with a clean light-grey studio backdrop with soft rim light, "
    "and change the clothing to a plain grey hoodie.",
]


CARTOON = (
    "Turn the man from this photo into a stylized cartoon avatar that is still clearly him: keep his face "
    "shape, eye shape, nose, lips, eyebrows, ears, hairstyle and hair colour recognisable, like a skilled "
    "caricature artist would — slightly exaggerated but never a different person. Remove any photo filters. "
    "Square avatar for a Telegram channel about personal finance, head and shoulders, centered, large, "
    "reads well as a small circle. No text, no letters, no digits, no watermark. "
)

CARTOON_STYLES = [
    "Style: modern 3D animated movie character, soft lighting, friendly confident smile, "
    "dark navy hoodie, holding a small orange calculator, warm orange background.",
    "Style: clean flat 2D vector illustration with bold shapes and soft gradients, slight smile, "
    "grey hoodie, solid teal background.",
    "Style: hand-drawn comic / graphic-novel portrait with confident ink lines and flat colours, "
    "calm smart look, holding a golden coin with the ruble sign, soft yellow background.",
]


def load(src: str) -> tuple[bytes, str]:
    if src.startswith("http"):
        resp = httpx.get(src, timeout=60, follow_redirects=True)
        resp.raise_for_status()
        return resp.content, resp.headers.get("content-type", "image/jpeg").split(";")[0]
    path = Path(src)
    return path.read_bytes(), "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def restyle(photo: bytes, mime: str, style: str, base: str = KEEP) -> bytes | None:
    resp = net.post(
        gemini.url(f"models/{s.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": base64.b64encode(photo).decode()}},
                {"text": base + style},
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
    args = sys.argv[1:]
    cartoon = "--cartoon" in args
    args = [a for a in args if a != "--cartoon"]
    photo, mime = load(args[0])
    extra = " ".join(args[1:])  # e.g. "Eyes are grey-blue, hair is dark blond."
    base, styles = (CARTOON, CARTOON_STYLES) if cartoon else (KEEP, STYLES)
    for n, style in enumerate(styles, 1):
        img = restyle(photo, mime, f"{style} {extra}".strip(), base)
        if not img:
            print(f"#{n}: no image")
            continue
        out = Path(f"/data/avatar-{'cartoon-' if cartoon else ''}{n}.png")
        out.write_bytes(img)
        print(f"#{n}: saved {out}")
        if s.tg_token and s.tg_review_chat:
            r = httpx.post(f"https://api.telegram.org/bot{s.tg_token}/sendDocument",
                           data={"chat_id": s.tg_review_chat, "caption": f"Аватар по фото, вариант {n}"},
                           files={"document": (out.name, img, "image/png")}, timeout=60)
            print(f"#{n}: " + ("sent to Telegram" if r.status_code == 200 else f"Telegram error {r.status_code}"))


if __name__ == "__main__":
    main()
