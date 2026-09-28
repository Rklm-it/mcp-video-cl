"""What the bot makes from a customer's photo: a greeting card, a photoshoot of four portraits,
a short «living photo» video. Pictures come from the reels image model (Gemini), the video from
the reels video model (Veo); every result carries the bot's link, so a shared result advertises it."""

from __future__ import annotations

import base64
import io
import subprocess
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from ..reels import gemini, net, video_gen
from ..reels.config import reels_settings

KEEP_FACE = (
    "Use the person or people from this photo. Keep every face exactly recognisable: same face shape, eyes, nose, "
    "lips, eyebrows, hairline, hair colour, skin tone, age and build — do not beautify into a different person, "
    "do not add or remove people. Natural realistic skin and flattering soft light. "
    "No text, no letters, no digits, no watermark, no logos. "
)

# key: (button, title printed on the card, scene for the model)
OCCASIONS: dict[str, tuple[str, str, str]] = {
    "bday": ("🎂 С днём рождения", "С днём рождения!",
             "a festive birthday scene: balloons, soft confetti, a cake with lit candles, warm golden bokeh light"),
    "love": ("❤️ Любимому человеку", "Люблю тебя!",
             "a romantic scene: soft pink evening light, rose petals, gentle heart-shaped bokeh"),
    "thanks": ("💐 Спасибо / маме", "Спасибо за всё!",
               "a warm cozy scene with a big bouquet of fresh flowers, soft spring sunlight"),
    "congrats": ("🎉 Поздравляю", "Поздравляю!",
                 "a celebration scene: golden confetti, sparkling lights, elegant festive decorations"),
}

SHOOT_STYLES = [
    "Professional studio portrait: soft warm key light, clean beige backdrop, elegant casual outfit.",
    "Business portrait in a bright modern office with large windows, smart outfit, confident look.",
    "Golden-hour portrait in an autumn park with yellow leaves, cozy knitwear, soft backlight.",
    "Cinematic evening portrait on a street of a Russian city with warm lights and soft bokeh, stylish coat.",
]

ANIMATE_PROMPT = (
    "The people in this photo come alive: natural subtle movement, blinking, a gentle smile, calm breathing, "
    "a slight head turn; hair and clothes move a little; the camera slowly pushes in. Keep every face exactly "
    "as in the photo, same people, same place, same clothes"
)


def shrink(photo: bytes, side: int = 1024) -> bytes:
    """Big photos make the image API estimate a huge price and refuse; send a ~1024 px JPEG."""
    image = Image.open(io.BytesIO(photo)).convert("RGB")
    image.thumbnail((side, side))
    return jpeg(image)


def jpeg(image: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def edit(photo: bytes, prompt: str, aspect: str = "3:4") -> Image.Image:
    """Gemini image editing: the photo plus an instruction, one picture back."""
    resp = net.post(
        gemini.url(f"models/{reels_settings.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(shrink(photo)).decode()}},
                {"text": prompt},
            ]}],
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
                return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")
    raise RuntimeError("Gemini returned no image (the photo may have been blocked)")


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(reels_settings.font, size)
    except OSError:
        return ImageFont.load_default()


def sign(image: Image.Image, link: str) -> Image.Image:
    """Small bot link in the bottom-right corner."""
    image = image.convert("RGB")
    draw = ImageDraw.Draw(image, "RGBA")
    font = _font(max(16, image.width // 40))
    box = draw.textbbox((0, 0), link, font=font)
    w, h = box[2] - box[0], box[3] - box[1]
    pad = max(6, image.width // 150)
    x, y = image.width - w - 3 * pad, image.height - h - 3 * pad
    draw.rounded_rectangle((x - pad, y - pad, x + w + pad, y + h + 2 * pad), radius=pad, fill=(0, 0, 0, 110))
    draw.text((x, y), link, font=font, fill=(255, 255, 255, 230))
    return image


def title(image: Image.Image, text: str) -> Image.Image:
    """The card greeting in large letters on a soft dark band at the bottom."""
    image = image.convert("RGB")
    size = image.width // 11
    font = _font(size)
    draw = ImageDraw.Draw(image, "RGBA")
    while size > 20 and draw.textlength(text, font=font) > image.width * 0.88:
        size -= 4
        font = _font(size)
    lines = textwrap.wrap(text, 22) or [text]
    line_h = size * 1.2
    band_top = image.height - line_h * len(lines) - size * 1.6
    band = Image.new("RGBA", image.size, (0, 0, 0, 0))
    bd = ImageDraw.Draw(band)
    start = int(band_top - size)
    for y in range(max(0, start), image.height):  # from transparent to dark
        bd.line((0, y, image.width, y), fill=(0, 0, 0, round(170 * (y - start) / (image.height - start))))
    image = Image.alpha_composite(image.convert("RGBA"), band).convert("RGB")
    draw = ImageDraw.Draw(image)
    y = band_top + size * 0.4
    for line in lines:
        w = draw.textlength(line, font=font)
        draw.text(((image.width - w) / 2, y), line, font=font, fill="white",
                  stroke_width=max(2, size // 18), stroke_fill=(120, 40, 20))
        y += line_h
    return image


def card(photo: bytes, occasion: str, link: str) -> bytes:
    _, greeting, scene = OCCASIONS[occasion]
    picture = edit(photo, KEEP_FACE + f"Make a beautiful greeting-card photo of them in {scene}. "
                          "Portrait orientation, the people large and centered, leave some calm space at the "
                          "bottom for a caption.", "3:4")
    return jpeg(sign(title(picture, greeting), link))


def photoshoot(photo: bytes, link: str) -> list[bytes]:
    return [jpeg(sign(edit(photo, KEEP_FACE + style, "3:4"), link)) for style in SHOOT_STYLES]


def vertical_frame(photo: bytes, out: Path, width: int = 720, height: int = 1280) -> Path:
    """The whole photo on a blurred copy of itself, 9:16: nothing is cropped away, no black bars."""
    image = Image.open(io.BytesIO(photo)).convert("RGB")
    scale = max(width / image.width, height / image.height)
    bg = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    left, top = (bg.width - width) // 2, (bg.height - height) // 2
    bg = bg.crop((left, top, left + width, top + height)).filter(ImageFilter.GaussianBlur(28))
    fg = image.copy()
    fg.thumbnail((width, height), Image.Resampling.LANCZOS)
    bg.paste(fg, ((width - fg.width) // 2, (height - fg.height) // 2))
    bg.save(out, format="JPEG", quality=92)
    return out


def animate(photo: bytes, workdir: Path, link: str) -> Path:
    frame = vertical_frame(photo, workdir / "frame.jpg")
    raw = video_gen.animate(frame, ANIMATE_PROMPT, 6, workdir / "raw.mp4", context=False)
    return sign_video(raw, workdir / "living-photo.mp4", link)


def sign_video(src: Path, out: Path, link: str) -> Path:
    text = out.with_suffix(".txt")
    text.write_text(link)
    vf = (f"drawtext=fontfile={reels_settings.font}:textfile={text}:expansion=none:fontsize=h/40:"
          "fontcolor=white@0.9:box=1:boxcolor=black@0.4:boxborderw=8:x=w-tw-24:y=h-th-28")
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src), "-vf", vf,
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                             "-c:a", "copy", "-movflags", "+faststart", str(out)], capture_output=True, text=True)
    if result.returncode != 0:
        return src  # an unsigned video is still worth delivering
    return out
