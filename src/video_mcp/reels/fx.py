"""Motion graphics over a scene: a counting number, pop-in stickers, a ring around the action, an arrow,
a flight route, a white flash.

Each effect is drawn frame by frame with PIL into a transparent layer (PNG in MOV keeps the alpha), and the
layer is laid over the scene's clip; labels and subtitles go on top of it later. Positions are fractions
of the 1080x1920 frame: x=0.5, y=0.5 is the centre. With fit="blur" a 16:9 video sits between y≈0.34
and y≈0.66, so the free space above it (y≈0.28) suits counters and stickers."""

from __future__ import annotations

import math
import subprocess
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import images
from .config import reels_settings

W, H = images.W, images.H
TYPES = ("counter", "pop", "circle", "arrow", "route", "flash")
COLORS = {"yellow": (255, 212, 0), "red": (232, 32, 56), "white": (255, 255, 255), "green": (46, 222, 112)}
BLACK = (0, 0, 0, 255)
NAVY = (11, 16, 48)
SIDES = {  # where the arrow comes from → the angle it points at (degrees, counter-clockwise, 0 = right)
    "left": 0, "right": 180, "top": -90, "bottom": 90,
    "top-left": -45, "top-right": -135, "bottom-left": 45, "bottom-right": 135,
}
FLASH_DUR = 0.3
FADE = 0.2  # an effect that ends before its scene fades out over this time
Draw = Callable[[Image.Image, float, float], None]  # (frame, seconds since the effect began, its lifetime)


def check(fx: dict) -> None:
    """Refuse an effect that cannot be drawn, before the reel starts rendering."""
    kind = fx.get("type")
    if kind not in TYPES:
        raise ValueError(f"Unknown effect {kind!r}: {', '.join(TYPES)}")
    if kind == "counter" and fx.get("count_to") is None:
        raise ValueError("counter needs count_to (and count_from, 0 by default)")
    if kind == "pop" and not (fx.get("text") or "").strip():
        raise ValueError("pop needs text")
    if kind == "route" and not 2 <= len(_places(fx)) <= 3:
        raise ValueError("route needs text with 2 or 3 places: 'Дубай > Тель-Авив' or "
                         "'Дубай > Тель-Авив > Эр-Рияд' (the third = where it ended up instead)")


def render_layer(specs: list[dict], duration: float, out: Path, fps: int) -> tuple[Path, float] | None:
    """Draw the scene's effects into a transparent clip. Returns (clip, where it starts in the scene), or None
    when nothing is visible; the clip covers only the time some effect is on screen."""
    effects = []
    for spec in specs:
        at = min(max(0.0, float(spec.get("at") or 0)), duration)
        default = FLASH_DUR if spec["type"] == "flash" else duration - at
        life = min(float(spec.get("dur") or default), duration - at)
        if life > 0:
            effects.append((at, life, life < duration - at - 1e-3, _MAKERS[spec["type"]](spec)))
    if not effects:
        return None
    t0 = min(at for at, *_ in effects)
    t1 = max(at + life for at, life, *_ in effects)
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", "-c:v", "png", "-pix_fmt", "rgba", str(out)],
        stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    blank = bytes(W * H * 4)
    try:
        for i in range(max(1, math.ceil((t1 - t0) * fps))):
            t = t0 + i / fps
            frame = None
            for at, life, fades, draw in effects:
                if at <= t < at + life:
                    frame = frame or Image.new("RGBA", (W, H))
                    if fades and t > at + life - FADE:
                        layer = Image.new("RGBA", (W, H))
                        draw(layer, t - at, life)
                        frame.alpha_composite(_faded(layer, (at + life - t) / FADE))
                    else:
                        draw(frame, t - at, life)
            proc.stdin.write(frame.tobytes() if frame else blank)
    finally:
        proc.stdin.close()
        err = proc.stderr.read().decode(errors="replace")
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed on the effects layer: {err.strip()[-400:]}")
    return out, t0


# ---------------------------------------------------------------- helpers


@lru_cache(maxsize=32)
def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(reels_settings.font, size)
    except OSError:
        return ImageFont.load_default(size)


def _fit(text: str, size: int, max_width: int, stroke: int = 0) -> int:
    """Largest font size (up to `size`) at which one line of text is no wider than `max_width`."""
    while size > 24 and _font(size).getlength(text) + 2 * stroke > max_width:
        size -= 4
    return size


def _rgba(name: str | None, default: str, alpha: int = 255) -> tuple[int, int, int, int]:
    return (*COLORS.get(name or default, COLORS[default]), alpha)


def _faded(img: Image.Image, k: float) -> Image.Image:
    if k >= 1:
        return img
    img = img.copy()
    img.putalpha(img.getchannel("A").point(lambda a: int(a * max(0.0, k))))
    return img


def _put(frame: Image.Image, sprite: Image.Image, cx: float, cy: float) -> None:
    """Composite `sprite` centred at (cx, cy), clipped to the frame."""
    x, y = round(cx - sprite.width / 2), round(cy - sprite.height / 2)
    left, top = max(0, -x), max(0, -y)
    right, bottom = min(sprite.width, W - x), min(sprite.height, H - y)
    if right > left and bottom > top:
        frame.alpha_composite(sprite, (x + left, y + top), (left, top, right, bottom))


def _scaled(sprite: Image.Image, k: float) -> Image.Image:
    if abs(k - 1) < 0.01:
        return sprite
    size = (max(1, round(sprite.width * k)), max(1, round(sprite.height * k)))
    return sprite.resize(size, Image.Resampling.BICUBIC)


def _ease_out(p: float) -> float:
    p = min(1.0, max(0.0, p))
    return 1 - (1 - p) ** 3


def _ease_back(p: float) -> float:
    """Overshoots a little and settles: the «pop»."""
    p = min(1.0, max(0.0, p))
    c1 = 1.70158
    return 1 + (c1 + 1) * (p - 1) ** 3 + c1 * (p - 1) ** 2


def _text(text: str, size: int, fill, stroke: int = 0, box=None, outline=None, pad=(34, 16)) -> Image.Image:
    """One line of text, optionally on a rounded box, with a soft shadow."""
    font = _font(size)
    left, top, right, bottom = font.getbbox(text, stroke_width=stroke)
    px, py = pad if (box or outline) else (stroke, stroke)
    w, h = right - left + 2 * px, bottom - top + 2 * py
    m = 24  # room for the shadow
    img = Image.new("RGBA", (w + 2 * m, h + 2 * m))
    if box or outline:
        shadow = Image.new("RGBA", img.size)
        ImageDraw.Draw(shadow).rounded_rectangle([m + 6, m + 10, m + w + 6, m + h + 10], 20, fill=(0, 0, 0, 150))
        img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(9)))
    draw = ImageDraw.Draw(img)
    if box:
        draw.rounded_rectangle([m, m, m + w, m + h], 20, fill=box)
    if outline:
        draw.rounded_rectangle([m, m, m + w, m + h], 20, outline=outline, width=12)
    draw.text((m + px - left, m + py - top), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=BLACK)
    return img


def _number(value: float, decimals: int) -> str:
    """12 345 678 or 0,81 — Russian thousands spaces and decimal comma, a real minus sign."""
    s = f"{abs(value):,.{decimals}f}".replace(",", " ").replace(".", ",")
    return ("−" if value < 0 and s.strip("0, ") else "") + s


def _places(fx: dict) -> list[str]:
    raw = (fx.get("text") or "").replace("→", ">")
    return [p.strip() for p in raw.split(">") if p.strip()]


# ---------------------------------------------------------------- effects


def _counter(fx: dict) -> Draw:
    """A big number that runs from count_from to count_to and lands with a punch."""
    a, b = float(fx.get("count_from") or 0), float(fx["count_to"])
    d = int(fx.get("decimals") or 0)
    pre, suf = fx.get("prefix") or "", fx.get("suffix") or ""
    color = _rgba(fx.get("color"), "yellow")
    cx, cy = float(fx.get("x", 0.5)) * W, float(fx.get("y") or 0.28) * H
    widest = max((pre + _number(v, d) + suf for v in (a, b, (a + b) / 2)), key=len)
    size = _fit(widest, 168, W - 140, stroke=10)

    def draw(frame: Image.Image, t: float, life: float) -> None:
        run = min(1.6, max(0.5, life * 0.6))  # counting time
        value = a + (b - a) * _ease_out(t / run)
        k = 0.6 + 0.4 * _ease_back(t / 0.3)  # pops in
        if t > run:
            k *= 1 + 0.14 * max(0.0, 1 - (t - run) / 0.25)  # lands with a punch
        _put(frame, _scaled(_text(pre + _number(value, d) + suf, size, color, stroke=10), k), cx, cy)
    return draw


def _pop(fx: dict) -> Draw:
    """A sticker that pops in: sticker (yellow), alert (red, breathing), stamp (slams down), plain (white)."""
    style = fx.get("style") or "sticker"
    text = fx["text"].strip()
    text = text.upper() if style in ("alert", "stamp") else text
    angle = fx.get("angle")
    if angle is None:
        angle = {"sticker": -4, "stamp": -10}.get(style, 0)
    max_w = W - 160
    if style == "sticker":
        size = _fit(text, 96, max_w - 70)
        sprite = _text(text, size, (0, 0, 0, 255), box=_rgba(fx.get("color"), "yellow"))
    elif style == "alert":
        size = _fit(text, 96, max_w - 70)
        sprite = _text(text, size, (255, 255, 255, 255), box=_rgba(fx.get("color"), "red"))
    elif style == "stamp":
        size = _fit(text, 120, max_w - 70)
        red = _rgba(fx.get("color"), "red")
        sprite = _text(text, size, red, box=(255, 255, 255, 215), outline=red)
    else:
        size = _fit(text, 110, max_w, stroke=9)
        sprite = _text(text, size, _rgba(fx.get("color"), "white"), stroke=9)
    if angle:
        sprite = sprite.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    cx, cy = float(fx.get("x", 0.5)) * W, float(fx.get("y") or 0.28) * H

    def draw(frame: Image.Image, t: float, life: float) -> None:
        dx = dy = 0.0
        if style == "stamp":
            p = min(1.0, t / 0.18)
            k = 2.2 - 1.2 * p * p  # falls onto the screen
            img = _faded(_scaled(sprite, k), p)
            if 0.18 < t < 0.5:  # and shakes it
                shake = 14 * (0.5 - t) / 0.32
                dx, dy = shake * math.sin(t * 90), shake * math.cos(t * 70)
        else:
            k = _ease_back(t / 0.35)
            if style == "alert" and t > 0.35:
                k *= 1 + 0.035 * math.sin((t - 0.35) * 2 * math.pi * 1.4)
            img = _scaled(sprite, max(0.05, k))
        _put(frame, img, cx + dx, cy + dy)
    return draw


def _circle(fx: dict) -> Draw:
    """A ring drawn around the action by an invisible marker, a little past full circle like by hand."""
    color = _rgba(fx.get("color"), "red")
    cx, cy = float(fx.get("x", 0.5)) * W, float(fx.get("y") or 0.5) * H
    rx = float(fx.get("r") or 0.14) * W
    ry = rx * 0.82
    s = 2  # drawn at double size, then scaled down: smooth edges
    pad = 24
    box = [pad * s, pad * s, (2 * rx + pad) * s, (2 * ry + pad) * s]
    size = (round(2 * rx + 2 * pad), round(2 * ry + 2 * pad))

    @lru_cache(maxsize=64)
    def ring(sweep: int) -> Image.Image:
        big = Image.new("RGBA", (size[0] * s, size[1] * s))
        d = ImageDraw.Draw(big)
        for start in range(0, sweep, 360):
            end = -100 + min(sweep, start + 360)
            d.arc(box, -100 + start, end, fill=(0, 0, 0, 110), width=22 * s)
            d.arc(box, -100 + start, end, fill=color, width=14 * s)
        return big.resize(size, Image.Resampling.LANCZOS)

    def draw(frame: Image.Image, t: float, life: float) -> None:
        sweep = round(385 * _ease_out(t / 0.45) / 5) * 5  # steps of 5° keep the cache small
        if sweep > 0:
            _put(frame, ring(sweep), cx, cy)
    return draw


def _arrow(fx: dict) -> Draw:
    """A thick arrow that flies in from `side` and keeps poking at the point (x, y)."""
    angle = SIDES.get(fx.get("side") or "left", 0)
    color = _rgba(fx.get("color"), "yellow")
    s, length, shaft, head_w, head_l = 2, 300, 40, 120, 110
    big = Image.new("RGBA", ((length + 20) * s, (head_w + 20) * s))
    mid = (head_w + 20) / 2
    neck = 10 + length - head_l
    pts = [(10, mid - shaft / 2), (neck, mid - shaft / 2), (neck, mid - head_w / 2), (10 + length, mid),
           (neck, mid + head_w / 2), (neck, mid + shaft / 2), (10, mid + shaft / 2)]
    d = ImageDraw.Draw(big)
    d.polygon([(x * s, y * s) for x, y in pts], fill=color, outline=BLACK, width=7 * s)
    sprite = big.resize((big.width // s, big.height // s), Image.Resampling.LANCZOS)
    sprite = sprite.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
    ux, uy = math.cos(math.radians(angle)), -math.sin(math.radians(angle))  # pointing direction on screen
    tip = (length + 20) / 2 - 10  # from the sprite's centre to the tip
    tx, ty = float(fx.get("x", 0.5)) * W, float(fx.get("y") or 0.5) * H

    def draw(frame: Image.Image, t: float, life: float) -> None:
        back = 260 * (1 - _ease_back(t / 0.4))  # flies in
        if t > 0.4:
            back = 22 * (0.5 + 0.5 * math.sin((t - 0.4) * 2 * math.pi * 1.6))  # pokes
        img = sprite if t > 0.15 else _faded(sprite, t / 0.15)
        _put(frame, img, tx - ux * (tip + 12 + back), ty - uy * (tip + 12 + back))
    return draw


def _route(fx: dict) -> Draw:
    """A flight on a card: A → B along an arc; with a third place the plane turns off to it (in red)."""
    places = _places(fx)
    cw, ch = W - 120, 420
    cx, cy = W / 2, float(fx.get("y") or 0.28) * H
    card = Image.new("RGBA", (cw + 48, ch + 48))
    shadow = Image.new("RGBA", card.size)
    ImageDraw.Draw(shadow).rounded_rectangle([30, 34, cw + 30, ch + 34], 34, fill=(0, 0, 0, 140))
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(card).rounded_rectangle([24, 24, cw + 24, ch + 24], 34, fill=(*NAVY, 225))
    ox, oy = 24, 24
    a, b = (ox + 110, oy + 250), (ox + cw - 110, oy + 250)
    planned = _bezier(a, ((a[0] + b[0]) / 2, oy + 60), b)
    diverted = len(places) == 3
    if diverted:
        c = (ox + cw * 0.58, oy + 330)
        path = _bezier(a, (ox + cw * 0.36, oy + 90), c)
    else:
        path = planned
    accent = _rgba(fx.get("color"), "red" if diverted else "yellow")
    d = ImageDraw.Draw(card)
    for i in range(0, len(planned) - 1, 4):  # the planned route, dashed
        d.line([planned[i], planned[i + 1]], fill=(255, 255, 255, 110), width=6)
    font = _font(_fit(max(places, key=len), 40, cw // 3))
    dots = [(a, places[0], (255, 255, 255, 255)), (b, places[1], (255, 255, 255, 255))]
    if diverted:
        dots.append((c, places[2], accent))
    for (x, y), name, col in dots:
        d.ellipse([x - 16, y - 16, x + 16, y + 16], fill=col, outline=BLACK, width=4)
        tw = font.getlength(name)
        lx = min(max(x - tw / 2, ox + 24), ox + cw - 24 - tw)
        d.text((lx, y + 28), name, font=font, fill=col, stroke_width=3, stroke_fill=BLACK)
    plane = _plane()

    def draw(frame: Image.Image, t: float, life: float) -> None:
        img = card.copy()
        fly = min(2.2, max(0.8, life * 0.75))
        p = 0.5 - 0.5 * math.cos(math.pi * min(1.0, max(0.0, (t - 0.25) / fly)))  # eases in and out
        n = max(1, round(p * (len(path) - 1)))
        dd = ImageDraw.Draw(img)
        if n > 1:
            dd.line(path[: n + 1], fill=accent, width=9, joint="curve")
        (x0, y0), (x1, y1) = path[max(0, n - 1)], path[min(len(path) - 1, n + 1)]
        heading = math.degrees(math.atan2(-(y1 - y0), x1 - x0))
        _put(img, plane.rotate(heading, resample=Image.Resampling.BICUBIC, expand=True), *path[n])
        k = 0.9 + 0.1 * _ease_out(t / 0.3)
        _put(frame, _faded(_scaled(img, k), t / 0.2), cx, cy)
    return draw


def _bezier(p0, p1, p2, steps: int = 120) -> list[tuple[float, float]]:
    out = []
    for i in range(steps + 1):
        u = i / steps
        out.append(((1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u * u * p2[0],
                    (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u * u * p2[1]))
    return out


def _plane() -> Image.Image:
    """A small airliner seen from above, nose to the right."""
    s = 4
    pts = [(40, 0), (30, -6), (6, -6), (-8, -36), (-16, -36), (-8, -6), (-26, -6), (-34, -18), (-40, -18),
           (-36, 0), (-40, 18), (-34, 18), (-26, 6), (-8, 6), (-16, 36), (-8, 36), (6, 6), (30, 6)]
    big = Image.new("RGBA", (100 * s, 100 * s))
    ImageDraw.Draw(big).polygon([((x + 50) * s, (y + 50) * s) for x, y in pts], fill=(255, 255, 255, 255),
                                outline=BLACK, width=3 * s)
    return big.resize((100, 100), Image.Resampling.LANCZOS)


def _flash(fx: dict) -> Draw:
    """A white flash that fades out: an impact on the cut."""
    color = _rgba(fx.get("color"), "white")[:3]

    def draw(frame: Image.Image, t: float, life: float) -> None:
        alpha = round(235 * (1 - t / life) ** 2)
        frame.alpha_composite(Image.new("RGBA", (W, H), (*color, alpha)))
    return draw


_MAKERS: dict[str, Callable[[dict], Draw]] = {
    "counter": _counter, "pop": _pop, "circle": _circle, "arrow": _arrow, "route": _route, "flash": _flash,
}
