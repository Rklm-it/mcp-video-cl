"""Motion-graphics scenes for Nexus shorts (style: docs/nexus/style-guide.md).

A scene is a function draw(c: Canvas, t: float) called for every frame; render() turns it into a
vertical 1080x1920 mp4 that create_reel takes as `media`. Elements appear over time with easing,
like an animated presentation: dark "blueprint" background, chapter header, two-line title with a
yellow second line, cards, arrows, status pills.

    python tools/motion/motion.py s3 out_dir/
"""

from __future__ import annotations

import math
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FONTS = Path(__file__).parent / "fonts"

NAVY = (11, 20, 48)
GRID = (26, 42, 85)
CARD = (18, 32, 74)
WHITE = (240, 244, 255)
MUTED = (150, 165, 205)
YELLOW = (255, 201, 60)
CYAN = (94, 231, 255)
RED = (255, 77, 109)
GREEN = (74, 222, 128)


@lru_cache(maxsize=None)
def font(name: str, size: int, weight: str = "Bold") -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(FONTS / f"{name}[wght].ttf"), size)
    f.set_variation_by_name(weight)
    return f


def ease(x: float) -> float:
    """easeOutCubic clamped to 0..1."""
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def prog(t: float, t0: float, dur: float = 0.45) -> float:
    return ease((t - t0) / dur)


@lru_cache(maxsize=1)
def background() -> Image.Image:
    img = Image.new("RGB", (W, H), NAVY)
    d = ImageDraw.Draw(img)
    for x in range(0, W, 45):
        d.line((x, 0, x, H), fill=GRID, width=1)
    for y in range(0, H, 45):
        d.line((0, y, W, y), fill=GRID, width=1)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g = ImageDraw.Draw(glow)
    g.ellipse((-400, 500, 900, 1800), fill=(40, 90, 200, 70))
    g.ellipse((500, -300, 1500, 700), fill=(255, 190, 60, 25))
    img.paste(glow.filter(ImageFilter.GaussianBlur(180)), (0, 0), glow.filter(ImageFilter.GaussianBlur(180)))
    d = ImageDraw.Draw(img)
    for r in (420, 640, 860):
        d.ellipse((W // 2 - r, 980 - r, W // 2 + r, 980 + r), outline=(34, 54, 104), width=2)
    vignette = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vignette).rectangle((0, 0, W, H), fill=0)
    return img


class Canvas:
    def __init__(self):
        self.img = background().copy().convert("RGBA")

    def layer(self) -> tuple[Image.Image, ImageDraw.ImageDraw]:
        lay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        return lay, ImageDraw.Draw(lay)

    def put(self, lay: Image.Image, alpha: float = 1.0, glow: int = 0) -> None:
        if alpha < 1:
            a = lay.getchannel("A").point(lambda v: int(v * alpha))
            lay.putalpha(a)
        if glow:
            b = lay.filter(ImageFilter.GaussianBlur(glow))
            self.img.alpha_composite(b)
        self.img.alpha_composite(lay)

    # ---- building blocks -------------------------------------------------------------------
    def header(self, chapter: str, t: float) -> None:
        a = prog(t, 0, 0.3)
        lay, d = self.layer()
        d.text((60, 70), "NEXUS · СЕТИ И VPN", font=font("Manrope", 28, "ExtraBold"), fill=MUTED)
        f = font("Manrope", 28, "ExtraBold")
        w = d.textlength(chapter, font=f)
        d.text((W - 60 - w, 70), chapter, font=f, fill=YELLOW)
        d.line((60, 122, 60 + (W - 120) * a, 122), fill=(60, 80, 140), width=2)
        self.put(lay, a)

    def title(self, line1: str, line2: str, t: float, t0: float = 0.1, size: int = 78) -> None:
        f = font("Unbounded", size, "Black")
        for i, (text, color) in enumerate(((line1, WHITE), (line2, YELLOW))):
            if not text:
                continue
            p = prog(t, t0 + i * 0.18, 0.5)
            lay, d = self.layer()
            d.text((60, 175 + i * (size + 18) + (1 - p) * 40), text, font=f, fill=color)
            self.put(lay, p)

    def text(self, xy, text, size=40, color=WHITE, name="Manrope", weight="Bold", t=1.0, t0=0.0,
             anchor="la", glow=0) -> None:
        p = prog(t, t0)
        lay, d = self.layer()
        x, y = xy
        d.text((x, y + (1 - p) * 25), text, font=font(name, size, weight), fill=color, anchor=anchor)
        self.put(lay, p, glow)

    def card(self, box, t, t0, outline=CYAN, fill=CARD, radius=28, width=4) -> float:
        p = prog(t, t0)
        x0, y0, x1, y1 = box
        s = 0.92 + 0.08 * p
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        bw, bh = (x1 - x0) * s / 2, (y1 - y0) * s / 2
        lay, d = self.layer()
        d.rounded_rectangle((cx - bw, cy - bh, cx + bw, cy + bh), radius=radius, fill=fill, outline=outline,
                            width=width)
        self.put(lay, p)
        return p

    def pill(self, center, text, color, t, t0, size=40, text_color=NAVY) -> None:
        p = prog(t, t0, 0.35)
        if p <= 0:
            return
        f = font("Manrope", size, "ExtraBold")
        lay, d = self.layer()
        w = d.textlength(text, font=f) + 56
        h = size + 30
        cx, cy = center
        s = 0.6 + 0.4 * ease((t - t0) / 0.25)
        d.rounded_rectangle((cx - w * s / 2, cy - h * s / 2, cx + w * s / 2, cy + h * s / 2), radius=h,
                            fill=color)
        if s > 0.95:
            d.text((cx, cy), text, font=f, fill=text_color, anchor="mm")
        self.put(lay, p)

    def arrow(self, a, b, t, t0, dur=0.5, color=CYAN, width=6) -> None:
        p = prog(t, t0, dur)
        if p <= 0:
            return
        (x0, y0), (x1, y1) = a, b
        xe, ye = x0 + (x1 - x0) * p, y0 + (y1 - y0) * p
        lay, d = self.layer()
        d.line((x0, y0, xe, ye), fill=color, width=width)
        if p > 0.9:
            ang = math.atan2(y1 - y0, x1 - x0)
            for s in (-1, 1):
                d.line((x1, y1, x1 - 26 * math.cos(ang + s * 0.5), y1 - 26 * math.sin(ang + s * 0.5)),
                       fill=color, width=width)
        self.put(lay, 1.0, glow=6)

    def mark(self, center, ok: bool, t, t0, r=44) -> None:
        """Green check or red cross in a circle that pops in."""
        p = prog(t, t0, 0.3)
        if p <= 0:
            return
        cx, cy = center
        rr = r * (0.5 + 0.5 * p)
        color = GREEN if ok else RED
        lay, d = self.layer()
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=color)
        k = rr * 0.45
        if ok:
            d.line((cx - k, cy, cx - k * 0.2, cy + k * 0.7, cx + k, cy - k * 0.6), fill=NAVY, width=int(rr / 5),
                   joint="curve")
        else:
            d.line((cx - k, cy - k, cx + k, cy + k), fill=NAVY, width=int(rr / 5))
            d.line((cx - k, cy + k, cx + k, cy - k), fill=NAVY, width=int(rr / 5))
        self.put(lay, p, glow=10)

    def spinner(self, center, t, r=40, color=MUTED) -> None:
        cx, cy = center
        lay, d = self.layer()
        start = (t * 360) % 360
        d.arc((cx - r, cy - r, cx + r, cy + r), start, start + 270, fill=color, width=8)
        self.put(lay)

    def phone(self, box, operator, t, t0, state: str, mark_t: float) -> None:
        """Phone mockup: operator in the status bar, chat bubbles; state ok/fail decides the ending."""
        p = self.card(box, t, t0, outline=(70, 95, 160), fill=(14, 24, 56), radius=46, width=5)
        if p <= 0:
            return
        x0, y0, x1, y1 = box
        lay, d = self.layer()
        d.rounded_rectangle(((x0 + x1) / 2 - 50, y0 + 18, (x0 + x1) / 2 + 50, y0 + 34), radius=8, fill=(5, 10, 25))
        d.text((x0 + 34, y0 + 52), operator, font=font("Manrope", 34, "ExtraBold"), fill=WHITE)
        d.text((x1 - 34, y0 + 56), "LTE ▮▮▮▮", font=font("Manrope", 26, "Bold"), fill=MUTED, anchor="ra")
        d.line((x0 + 30, y0 + 110, x1 - 30, y0 + 110), fill=(40, 60, 110), width=2)
        self.put(lay, p)
        cx = (x0 + x1) / 2
        if state == "ok":
            for i, (w, side) in enumerate(((230, 0), (170, 1), (250, 0), (150, 1))):
                tt = t0 + 0.4 + i * 0.25
                pb = prog(t, tt, 0.3)
                if pb <= 0:
                    continue
                yb = y0 + 150 + i * 92
                bx0 = x0 + 34 if side == 0 else x1 - 34 - w
                lay, d = self.layer()
                d.rounded_rectangle((bx0, yb, bx0 + w, yb + 66), radius=24,
                                    fill=(40, 70, 140) if side == 0 else (30, 110, 160))
                self.put(lay, pb)
        else:
            if t < mark_t:
                self.spinner((cx, y0 + 330), t)
            self.text((cx, y0 + 440), "нет соединения", 30, MUTED, t=t, t0=mark_t, anchor="ma")
        self.mark((cx, y1 - 90), state == "ok", t, mark_t, r=46)


def render(draw, seconds: float, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out)],
        stdin=subprocess.PIPE)
    for i in range(int(seconds * FPS)):
        c = Canvas()
        draw(c, i / FPS)
        proc.stdin.write(c.img.convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait():
        raise RuntimeError(f"ffmpeg failed for {out}")
    return out


if __name__ == "__main__":
    import importlib

    episode, out_dir = sys.argv[1], Path(sys.argv[2])
    mod = importlib.import_module(f"episodes.{episode}")
    for name, (draw, seconds) in mod.SCENES.items():
        print(render(draw, seconds, out_dir / f"{name}.mp4"))
