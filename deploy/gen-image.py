"""Generate square pictures with the reels image model (Gemini) and send them to the Telegram review chat.

Run inside the container (no photo needed):
    docker compose exec -T video-mcp python - < deploy/gen-image.py
Pictures are saved to /data/gen-<n>.png (= ./data on the host) and sent as files, full resolution.
"""

from __future__ import annotations

import base64
import sys
from pathlib import Path

import httpx

from video_mcp.reels import gemini, net
from video_mcp.reels.config import reels_settings as s

STYLE = (
    "Square avatar for a Telegram channel about personal finance, must read well as a small circle: "
    "one character, head and shoulders, centered, big and close, plain solid background. "
    "Modern flat 2D vector illustration, bold clean shapes, smooth gradients, friendly and trustworthy, "
    "premium quality like a top app mascot. No text, no letters, no digits, no watermark."
)

PROMPTS = [
    "A friendly Russian man around 35 with short dark hair and a neat short beard, warm smile, "
    "holding a big orange calculator next to his face, one eyebrow raised as if checking the math, "
    "navy blue shirt, bright warm orange background.",
    "A cheerful Russian man around 35 with short hair and stubble, wearing round glasses, winking, "
    "holding a golden coin with the ruble sign between two fingers, casual dark hoodie, "
    "deep teal background.",
    "A confident Russian man around 35 with short hair and a light beard, thoughtful smile, "
    "a pencil behind his ear, holding a small notebook with a rising line chart drawn in it, "
    "denim shirt, soft yellow background.",
]


def generate(prompt: str) -> bytes | None:
    resp = net.post(
        gemini.url(f"models/{s.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [{"text": f"{STYLE} {prompt}"}]}],
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
    prompts = sys.argv[1:] or PROMPTS
    for n, prompt in enumerate(prompts, 1):
        img = generate(prompt)
        if not img:
            print(f"#{n}: no image")
            continue
        out = Path(f"/data/gen-{n}.png")
        out.write_bytes(img)
        print(f"#{n}: saved {out}")
        if s.tg_token and s.tg_review_chat:
            r = httpx.post(f"https://api.telegram.org/bot{s.tg_token}/sendDocument",
                           data={"chat_id": s.tg_review_chat, "caption": f"Аватар, вариант {n}"},
                           files={"document": (out.name, img, "image/png")}, timeout=60)
            print(f"#{n}: " + ("sent to Telegram" if r.status_code == 200 else f"Telegram error {r.status_code}"))


if __name__ == "__main__":
    main()
