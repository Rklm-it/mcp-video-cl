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
    "Use the person or people (or the pet) from this photo. Keep every face exactly recognisable: same face shape, "
    "eyes, nose, "
    "lips, eyebrows, hairline, hair colour, skin tone, age and build — do not beautify into a different person, "
    "do not add or remove people. Natural realistic skin and flattering soft light. "
    "No text, no letters, no digits, no watermark, no logos. "
)

# key: (button, title printed on the card, scene for the model)
OCCASIONS: dict[str, tuple[str, str, str]] = {
    "bday": ("🎂 День рождения", "С днём рождения!",
             "a festive birthday scene: balloons, soft confetti, a cake with lit candles, warm golden bokeh light"),
    "jubilee": ("🥂 Юбилей", "С юбилеем!",
                "an elegant jubilee celebration: golden balloons, flowers, a festive table, warm evening light"),
    "wedding": ("💍 Свадьба", "Совет да любовь!",
                "a wedding celebration: white flowers, soft golden light, delicate festive decorations"),
    "anniv": ("💞 Годовщина", "С годовщиной!",
              "a romantic anniversary evening: candles, roses, soft warm bokeh lights"),
    "love": ("❤️ Любимому человеку", "Люблю тебя!",
             "a romantic scene: soft pink evening light, rose petals, gentle heart-shaped bokeh"),
    "newyear": ("🎄 Новый год", "С Новым годом!",
                "a cozy New Year scene: decorated fir tree, warm garland lights, soft falling snow, sparklers"),
    "mar8": ("🌷 8 Марта", "С 8 Марта!",
             "a bright spring scene with a big bouquet of tulips and mimosa, soft sunlight"),
    "feb23": ("🎖 23 Февраля", "С 23 Февраля!",
              "a festive scene with dark blue and red ribbons, golden stars and warm light, dignified mood"),
    "mother": ("👩‍👧 Маме", "Любимой маме!",
               "a warm cozy home scene with a bouquet of fresh flowers, soft spring sunlight"),
    "baby": ("👶 Рождение малыша", "С рождением малыша!",
             "a gentle scene with pastel balloons, soft toys and warm light, tender mood"),
    "grad": ("🎓 Выпускной", "С выпускным!",
             "a graduation celebration: confetti, balloons, a festive school hall, bright joyful light"),
    "teacher": ("👩‍🏫 День учителя", "С Днём учителя!",
                "a bright school classroom with autumn flowers on the desk, warm sunlight, festive mood"),
    "elders": ("👵 Бабушке и дедушке", "Любимым бабушке и дедушке!",
               "a warm cozy home with autumn flowers, soft golden light, tender family mood"),
    "thanks": ("💐 Спасибо", "Спасибо за всё!",
               "a warm cozy scene with a big bouquet of fresh flowers, soft spring sunlight"),
    "congrats": ("🎉 Любой повод", "Поздравляю!",
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


def edit(photo: bytes | list[bytes], prompt: str, aspect: str = "3:4") -> Image.Image:
    """Gemini image editing: one or several photos plus an instruction, one picture back."""
    photos = photo if isinstance(photo, list) else [photo]
    resp = net.post(
        gemini.url(f"models/{reels_settings.gemini_image_model}:generateContent"),
        headers=gemini.headers(),
        json={
            "contents": [{"parts": [
                *({"inline_data": {"mime_type": "image/jpeg", "data": base64.b64encode(shrink(p)).decode()}}
                  for p in photos),
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


# ---- video greetings ----

# key: (spoken greeting with {name}, title on screen with {name}); ready texts fit the 8-second clip
GREETINGS: dict[str, tuple[str, str]] = {
    "bday": ("{name}, с днём рождения! Пусть этот год принесёт много радости, здоровья и исполнения желаний!",
             "С днём рождения, {name}!"),
    "jubilee": ("{name}, с юбилеем! Здоровья, радости и ещё много счастливых лет рядом с близкими!",
                "С юбилеем, {name}!"),
    "wedding": ("{name}, поздравляем со свадьбой! Любви, нежности и долгих счастливых лет вместе!",
                "{name}, совет да любовь!"),
    "anniv": ("{name}, с нашей годовщиной! Спасибо за каждый день вместе. Я тебя люблю!", "{name}, с годовщиной!"),
    "love": ("{name}, я тебя очень люблю! Спасибо, что ты у меня есть.", "{name}, люблю тебя!"),
    "newyear": ("{name}, с Новым годом! Пусть он будет тёплым, счастливым и полным чудес!", "С Новым годом, {name}!"),
    "mar8": ("{name}, с Восьмым марта! Весеннего настроения, любви и красоты каждый день!", "{name}, с 8 Марта!"),
    "feb23": ("{name}, с Двадцать третьим февраля! Сил, здоровья, удачи и мирного неба!", "{name}, с 23 Февраля!"),
    "mother": ("{name}, мамочка, спасибо тебе за всё! Ты самая лучшая, я тебя очень люблю!", "{name}, любимой маме!"),
    "baby": ("{name}, поздравляем с рождением малыша! Здоровья, крепкого сна и много счастья!",
             "{name}, с рождением малыша!"),
    "grad": ("{name}, с выпускным! Впереди столько нового — пусть всё получится!", "{name}, с выпускным!"),
    "teacher": ("{name}, с Днём учителя! Спасибо за ваш труд, терпение и доброту!", "{name}, с Днём учителя!"),
    "elders": ("{name}, спасибо вам за заботу и тепло! Здоровья, радости и долгих-долгих лет!",
               "{name}, мы вас любим!"),
    "thanks": ("{name}, спасибо тебе за всё! Ты очень дорогой для меня человек.", "Спасибо, {name}!"),
    "congrats": ("{name}, поздравляю от всей души! Пусть всё задуманное сбывается!", "{name}, поздравляю!"),
}
# key: (button, engine, voice, style, sound effect). edge = free Microsoft voices (style = pitch, rate);
# openai = the paid gateway voices (REELS_OPENAI_*, style = how to speak), fall back to FALLBACK.
# Characters are folk and generic ones on purpose: no real people's voices and no copyrighted cartoon heroes.
VOICES: dict[str, tuple[str, str, str, tuple[str, str] | str, str]] = {
    "f": ("👩 Женский", "edge", "ru-RU-SvetlanaNeural", ("+0Hz", "+0%"), ""),
    "m": ("👨 Мужской", "edge", "ru-RU-DmitryNeural", ("+0Hz", "+0%"), ""),
    "soft": ("💖 Нежный", "openai", "shimmer", "Говори по-русски нежно и тепло, с улыбкой в голосе, неторопливо.", ""),
    "host": ("🎤 Ведущий праздника", "openai", "ash",
             "Говори по-русски торжественно и радостно, как ведущий праздника, с восклицаниями.", ""),
    "kid": ("🧒 Детский", "edge", "ru-RU-SvetlanaNeural", ("+45Hz", "+8%"), ""),
    "old": ("👴 Дедушка", "edge", "ru-RU-DmitryNeural", ("-18Hz", "-12%"), ""),
    "moroz": ("🎅 Дед Мороз", "openai", "onyx",
              "Говори по-русски как добрый сказочный Дед Мороз: низким басом, медленно, раскатисто и ласково.", ""),
    "snow": ("❄️ Снегурочка", "openai", "coral",
             "Говори по-русски как сказочная Снегурочка: звонко, нежно, с волшебной интонацией.", ""),
    "tale": ("🧙 Сказочник", "openai", "fable",
             "Говори по-русски как сказочник, который читает детям волшебную сказку: загадочно и тепло.", ""),
    "yaga": ("🧹 Баба-Яга", "openai", "sage",
             "Говори по-русски как смешная сказочная Баба-Яга: скрипучим старческим голосом, хитро и ворчливо.", ""),
    "pirate": ("🏴‍☠️ Пират", "openai", "ash",
               "Говори по-русски как весёлый капитан пиратов: хрипло, азартно, с раскатистым «р».", ""),
    "toon": ("🐭 Мультяшный", "edge", "ru-RU-SvetlanaNeural", ("+90Hz", "+12%"), ""),
    "robot": ("🤖 Робот", "edge", "ru-RU-DmitryNeural", ("-5Hz", "-5%"),
              "aecho=0.8:0.9:8|16:0.5|0.3,flanger=delay=2:depth=3:speed=0.8,volume=1.4"),
}
FALLBACK = {"soft": "f", "host": "m", "moroz": "old", "snow": "f", "tale": "m", "yaga": "old", "pirate": "m"}
MAX_OWN_TEXT = 160  # about 10 seconds of speech: the 8-second clip plus a short hold on the last frame

# Ded Moroz speaks himself (the video model makes the voice); "boy"/"girl" for the Russian word endings
MOROZ_TEXT = {
    "boy": "{name}, здравствуй! Это Дедушка Мороз. Я знаю, ты весь год старался. Жди подарок под ёлкой!",
    "girl": "{name}, здравствуй! Это Дедушка Мороз. Я знаю, ты весь год старалась. Жди подарок под ёлкой!",
}
MOROZ_PICTURE = (
    "Vertical 9:16 photo: kind Russian Ded Moroz (Father Frost) with a long white beard, long red fur coat with "
    "white trim and silver embroidery, tall red hat, magic staff, sitting by a decorated New Year tree in a cozy "
    "wooden Russian log house, warm garland lights, snow outside the window, looking straight into the camera "
    "with a warm smile, medium close-up. Photorealistic, cinematic. No text, no letters, no watermark."
)
MOROZ_VIDEO = (
    "Russian Ded Moroz (Father Frost) looks into the camera, smiles warmly and says clearly in Russian, "
    "in a kind deep grandfatherly voice: \"{text}\" His lips move in sync with the speech, gentle hand gesture, "
    "garland lights twinkle. Soft festive bells in the background"
)


def _ff(*args: str) -> None:
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-400:]}")


def _duration(path: Path) -> float:
    from ..frames import probe_duration

    return probe_duration(path)


def voice(text: str, out: Path, key: str = "f") -> Path:
    """Speech in one of VOICES; a gateway voice that fails falls back to a free one of the same kind."""
    import asyncio

    import edge_tts

    _, engine, name, style, effect = VOICES.get(key, VOICES["f"])
    raw = out.with_name(out.stem + "-raw.mp3") if effect else out
    if engine == "openai":
        try:
            _gateway_voice(text, raw, name, str(style))
        except Exception:  # noqa: BLE001 - the gateway has bad days; a plainer voice beats no greeting
            return voice(text, out, FALLBACK.get(key, "f"))
    else:
        pitch, rate = style

        async def speak() -> None:
            await edge_tts.Communicate(text, name, rate=rate, pitch=pitch).save(str(raw))

        asyncio.run(speak())
    if effect:
        _ff("-i", str(raw), "-af", effect, "-c:a", "libmp3lame", "-b:a", "128k", str(out))
        raw.unlink(missing_ok=True)
    return out


def _gateway_voice(text: str, out: Path, name: str, instructions: str) -> Path:
    s = reels_settings
    if not s.openai_key:
        raise ValueError("no speech gateway")
    resp = net.post(f"{s.openai_base_url.rstrip('/')}/audio/speech", timeout=120,
                    headers={"Authorization": f"Bearer {s.openai_key}"},
                    json={"model": s.openai_tts_model, "voice": name, "input": text,
                          "instructions": instructions, "response_format": "mp3"})
    if resp.status_code >= 400 or len(resp.content) < 1000:
        raise RuntimeError(f"Speech API error {resp.status_code}: {resp.text[:200]}")
    out.write_bytes(resp.content)
    return out


def voice_sample(key: str, cache_dir: Path) -> Path:
    """A short example of the voice, made once."""
    out = cache_dir / f"voice-{key}.mp3"
    if not out.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        voice("Маша, с днём рождения! Пусть этот год будет самым счастливым!", out, key)
    return out


def clean_text(text: str) -> str:
    """The customer's own greeting: no links, one line of plain text, up to MAX_OWN_TEXT characters."""
    import re

    text = re.sub(r"(https?://|www\.|t\.me/|@)\S*", "", text)
    return " ".join(text.split())[:MAX_OWN_TEXT].strip()


def clean_name(text: str) -> str:
    """A first name for the greeting: letters, spaces and hyphens, up to 30 characters, or ''."""
    name = " ".join("".join(c for c in text if c.isalpha() or c in " -").split())[:30].strip(" -")
    return name[:1].upper() + name[1:] if name else ""


def greeting(photo: bytes, occasion: str, name: str, workdir: Path, link: str, voice_key: str = "f",
             text: str = "") -> Path:
    """The customer's photo in a festive scene comes alive, a voice congratulates `name` (a ready text for the
    occasion or the customer's own), the title is on screen."""
    _, _, scene = OCCASIONS[occasion]
    picture = edit(photo, KEEP_FACE + f"Place them in {scene}. Portrait orientation, the people large and "
                                      "centered.", "9:16")
    frame = vertical_frame(jpeg(picture), workdir / "frame.jpg")
    raw = video_gen.animate(frame, ANIMATE_PROMPT, 8, workdir / "raw.mp4", context=False)
    return _voiced(raw, occasion, name, text, voice_key, workdir, link)


def _voiced(raw: Path, occasion: str, name: str, text: str, voice_key: str, workdir: Path, link: str) -> Path:
    """The clip plus the spoken greeting, the title with the name and the bot link; the last frame holds
    while the voice is still speaking."""
    spoken, shown = (s.format(name=name) for s in GREETINGS[occasion])
    speech = voice(text or spoken, workdir / "voice.mp3", voice_key)
    total = max(_duration(raw), _duration(speech) + 1.0)
    (workdir / "title.txt").write_text(shown)
    (workdir / "link.txt").write_text(link)
    font = reels_settings.font
    vf = (f"tpad=stop_mode=clone:stop_duration={total:.2f},"
          f"drawtext=fontfile={font}:textfile={workdir / 'title.txt'}:expansion=none:fontsize=h/22:"
          "fontcolor=white:borderw=4:bordercolor=0x802814:x=(w-tw)/2:y=h-th-h/9,"
          f"drawtext=fontfile={font}:textfile={workdir / 'link.txt'}:expansion=none:fontsize=h/40:"
          "fontcolor=white@0.9:box=1:boxcolor=black@0.4:boxborderw=8:x=w-tw-24:y=h-th-28")
    out = workdir / "greeting.mp4"
    _ff("-i", str(raw), "-i", str(speech), "-filter_complex", f"[0:v]{vf}[v];[1:a]adelay=500|500,apad[a]",
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out))
    return out


# Greetings without a photo, from our own characters. Only original and folk characters: known heroes of
# films and cartoons (Marvel, Disney, Soyuzmultfilm…) belong to their owners.
# key: (button, look for the picture model, voice key)
CHARACTERS: dict[str, tuple[str, str, str]] = {
    "hero": ("🦸 Супергерой", "a friendly original superhero with a sleek silver-and-blue suit and a flowing cape, "
                             "no emblems, no logos, not resembling any known hero", "host"),
    "dragon": ("🐉 Дракончик", "a cute small green dragon with big kind eyes and tiny wings", "toon"),
    "dino": ("🦖 Динозаврик", "a cheerful cute orange baby dinosaur with a party hat", "kid"),
    "fairy": ("🧚 Фея", "a kind fairy with shimmering wings and a glowing magic wand", "snow"),
    "wizard": ("🧙 Волшебник", "a kind old wizard with a long white beard, starry robe and a magic staff", "tale"),
    "pirate": ("🏴‍☠️ Пират", "a jolly pirate captain with a tricorn hat and a parrot on his shoulder", "pirate"),
    "robot": ("🤖 Робот", "a friendly shiny round robot with glowing blue eyes", "robot"),
    "princess": ("👸 Принцесса", "a kind fairy-tale princess in a light blue gown with a small crown", "soft"),
    "bear": ("🐻 Мишка", "a big soft friendly brown teddy bear", "old"),
    "cosmo": ("👨‍🚀 Космонавт", "a smiling cosmonaut in a white spacesuit with the helmet off", "m"),
}
CHARACTER_VIDEO = (
    "The character looks into the camera, smiles, waves happily and celebrates, then speaks warmly to the viewer; "
    "lively cartoon-like animation, festive mood"
)


def character_picture(key: str, occasion: str, cache_dir: Path) -> Path:
    """The character in the occasion's scene, made once per pair and reused."""
    out = cache_dir / f"char-{key}-{occasion}.jpg"
    if not out.exists():
        from ..reels import images

        cache_dir.mkdir(parents=True, exist_ok=True)
        _, look, _ = CHARACTERS[key]
        _, _, scene = OCCASIONS[occasion]
        prompt = (f"Vertical 9:16 bright 3D animated movie still: {look}, in {scene}, facing the camera, "
                  "centered, full of joy, soft cinematic light. No text, no letters, no watermark, no logos.")
        images.picture(prompt, "9:16").save(out, format="JPEG", quality=92)
    return out


def character_greeting(key: str, occasion: str, name: str, text: str, workdir: Path, link: str,
                       cache_dir: Path) -> Path:
    frame = vertical_frame(character_picture(key, occasion, cache_dir).read_bytes(), workdir / "frame.jpg")
    raw = video_gen.animate(frame, CHARACTER_VIDEO, 8, workdir / "raw.mp4", context=False)
    return _voiced(raw, occasion, name, text, CHARACTERS[key][2], workdir, link)


def moroz_picture(cache: Path) -> Path:
    """One Ded Moroz picture, made once and reused as the first frame of every greeting."""
    if not cache.exists():
        from ..reels import images

        cache.parent.mkdir(parents=True, exist_ok=True)
        images.picture(MOROZ_PICTURE, "9:16").save(cache, format="JPEG", quality=92)
    return cache


def moroz(gender: str, name: str, workdir: Path, link: str, cache: Path) -> Path:
    text = MOROZ_TEXT[gender].format(name=name)
    raw = video_gen.animate(moroz_picture(cache), MOROZ_VIDEO.format(text=text), 8, workdir / "raw.mp4",
                            context=False, audio=True)
    return sign_video(raw, workdir / "ded-moroz.mp4", link)


# ---- single-picture products: old photo restoration, looks, a child's drawing ----

RESTORE = (
    "Restore this old photo: remove scratches, dust, cracks, folds, stains and noise, recover lost details, fix "
    "faded contrast and gently sharpen, then colorize it with natural realistic colours true to the era. Keep the "
    "faces, expressions, hair, clothes, background and composition exactly as they are; do not add or remove "
    "anything, do not modernize. No text, no watermark."
)

# key: (button, instruction); the look keeps the person recognisable, a pet photo gets the look too
STYLES: dict[str, tuple[str, str]] = {
    "toon3d": ("🧸 3D-мультфильм", "Turn them into a charming 3D animated movie character: soft shapes, expressive "
                                  "eyes, soft studio light, still clearly the same person."),
    "anime": ("🎌 Аниме", "Redraw them as a beautiful anime illustration with clean lines and soft colours, "
                         "still clearly the same person."),
    "oil": ("🖼 Портрет маслом", "Turn the photo into a classic oil painting portrait with visible brushstrokes, "
                                "rich warm colours and museum lighting."),
    "royal": ("👑 Королевский портрет", "Make a regal 18th-century court portrait: luxurious historical attire, "
                                       "jewellery, palace interior, painted in the old masters style."),
    "space": ("🚀 Космонавт", "Show them as a cosmonaut in a white spacesuit with the helmet off, Earth and stars "
                             "behind, cinematic light."),
    "ussr": ("🎞 Ретро 70-х", "Make it look like a warm Soviet 1970s film photograph: period clothes and hairstyle, "
                             "retro interior, soft film grain and faded colours."),
    "figure": ("📦 Фигурка в коробке", "Turn them into a collectible toy figure standing in a clear blister box "
                                      "with a few matching accessories, product photo on a clean background; the "
                                      "box has no text and no logos."),
    "hero": ("🦸 Супергерой", "Show them as an original superhero in a sleek costume of their own (no known heroes, "
                             "no logos), dramatic city rooftop at sunset."),
    "cv": ("💼 Фото на резюме", "Make a professional business headshot for a CV: neat business-casual outfit, plain "
                              "light-grey studio background, soft even light, friendly confident look, shoulders up."),
    "aged": ("👴 Я в старости", "Show how this person will look at about 75 years old: natural realistic ageing, "
                               "grey hair, wrinkles, same face and features, kind warm look, soft light."),
    "child": ("🧒 Я в детстве", "Show how this person looked as a 6-year-old child: same eye shape, face features "
                               "and hair colour, cute natural childhood photo, soft light."),
    "pet": ("🐾 Питомец-аристократ", "If there is a pet in the photo, paint the pet as a noble aristocrat in a "
                                    "Renaissance oil portrait with a velvet cape and a lace collar; otherwise do "
                                    "the same for the person."),
}

DRAWING = (
    "This is a child's drawing. Turn it into a bright, charming 3D animated movie still: keep exactly the same "
    "characters, objects, colours, composition and the child's ideas, just make them look real and magical, "
    "with soft cinematic light. No text, no letters, no watermark."
)

ASPECT_RATIOS = {"1:1": 1.0, "3:4": 0.75, "4:3": 4 / 3, "9:16": 9 / 16, "16:9": 16 / 9}


def nearest_aspect(photo: bytes) -> str:
    """The supported picture shape closest to the photo's own, so nothing important is cropped."""
    width, height = Image.open(io.BytesIO(photo)).size
    return min(ASPECT_RATIOS, key=lambda a: abs(ASPECT_RATIOS[a] - width / height))


def restore(photo: bytes, link: str) -> bytes:
    return jpeg(sign(edit(photo, RESTORE, nearest_aspect(photo)), link))


def style(photo: bytes, key: str, link: str) -> bytes:
    return jpeg(sign(edit(photo, KEEP_FACE + STYLES[key][1], "3:4"), link))


def drawing(photo: bytes, link: str) -> bytes:
    return jpeg(sign(edit(photo, DRAWING, nearest_aspect(photo)), link))


# ---- photo fixes and two-photo products ----

ENHANCE = (
    "Improve the quality of this photo: make it sharp and clear, remove blur, noise and compression artefacts, fix "
    "exposure and white balance, restore natural colours and fine details. Keep everything else exactly as it is: "
    "same people, faces, pose, clothes, background and framing. No text, no watermark."
)

# key: (button, the new background)
BACKGROUNDS: dict[str, tuple[str, str]] = {
    "white": ("⬜ Белый фон — для Авито и маркетплейсов",
              "a clean pure white studio background with a soft natural shadow under the item"),
    "interior": ("🛋 Красивый интерьер", "a stylish bright modern interior that suits the item, soft daylight"),
    "wood": ("🪵 Деревянный стол", "a warm wooden table surface with a softly blurred cozy background"),
    "nature": ("🌿 Природа", "a fresh natural outdoor setting with greenery and soft sunlight, blurred background"),
}
BACKGROUND = (
    "Keep the main object or person of this photo exactly as it is (shape, colours, labels, details, faces) and "
    "replace everything around it with {scene}. Realistic lighting and shadows that match. Product-photo quality. "
    "Do not add any text, logos or watermarks."
)

HUG = (
    "The first photo shows a person now, the second shows the same person as a child. Make one warm, realistic "
    "photo where the adult hugs their younger self: the adult looks exactly like the first photo and the child "
    "exactly like the second (same faces, hair, clothes style), both smiling, cozy soft light, simple neutral "
    "background, vertical framing, both large in the frame. No text, no watermark."
)
HUG_VIDEO = ("The adult gently hugs the child, both smile and sway a little, the child hugs back; tender, "
             "natural movement, faces stay exactly the same")

TOGETHER = (
    "Put the people from all these photos together into one natural photo, as if they were photographed together: "
    "standing close side by side, relaxed and warm, consistent light and colours, a simple pleasant background. "
    "Keep every face exactly as in its photo — same features, age and hair; do not invent new people. "
    "No text, no watermark."
)

BABY = (
    "The two photos show a couple. Create a realistic portrait of their child at about 3 years old, naturally "
    "combining the features of both parents (eyes, nose, lips, face shape, hair and skin colour). A cute happy "
    "toddler, soft daylight, simple light background. No text, no watermark."
)


def enhance(photo: bytes, link: str) -> bytes:
    return jpeg(sign(edit(photo, ENHANCE, nearest_aspect(photo)), link))


def background(photo: bytes, key: str, link: str) -> bytes:
    return jpeg(sign(edit(photo, BACKGROUND.format(scene=BACKGROUNDS[key][1]), nearest_aspect(photo)), link))


def together(photo: bytes, photo2: bytes, link: str) -> bytes:
    return jpeg(sign(edit([photo, photo2], TOGETHER, "4:3"), link))


def baby(photo: bytes, photo2: bytes, link: str) -> bytes:
    return jpeg(sign(edit([photo, photo2], BABY, "3:4"), link))


def hug(photo: bytes, photo2: bytes, workdir: Path, link: str) -> Path:
    picture = edit([photo, photo2], HUG, "9:16")
    frame = vertical_frame(jpeg(picture), workdir / "frame.jpg")
    raw = video_gen.animate(frame, HUG_VIDEO, 8, workdir / "raw.mp4", context=False)
    return sign_video(raw, workdir / "hug.mp4", link)
