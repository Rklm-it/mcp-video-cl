"""c1 · «Как читер видит сквозь стены?» — топ-тема @aldoniq (21,4 тыс. лайков). ~45 с: почему wallhack вообще
возможен, аимбот, как Valorant прячет врагов, ловушка Valve. Только «как устроено», без инструкций.

Факты: клиент шутера обычно получает позиции всех врагов, даже за стенами — их и читает wallhack. Riot (VALORANT):
«Fog of War» — сервер не присылает позицию врага, пока клиенту не нужно его показать, «wallhack'у нечего видеть»
(riotgames.com, «Demolishing Wallhacks with VALORANT's Fog of War»). Valve, февраль 2023: патч Dota 2 с данными,
которые читает только чит-софт («honeypot»), — навсегда забанено больше 40 000 аккаунтов (IGN, Polygon,
BleepingComputer).
"""

import math

from episodes.z1 import big_title
from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog

MAP = (90, 470, 990, 1150)
WALLS = ((470, 560, 515, 990), (515, 820, 990, 862), (90, 700, 300, 742), (700, 470, 742, 640))
YOU = (230, 1050)
# (x, y, behind a wall?)
ENEMIES = ((820, 600, True), (800, 1010, True), (370, 640, False))
DIST = ("11,0 м", "9,7 м", "6,2 м")


def level(c: Canvas, t: float, dim: float = 1.0) -> None:
    """Top-down level: floor grid, walls, you with a view cone."""
    lay, d = c.layer()
    x0, y0, x1, y1 = MAP
    d.rounded_rectangle(MAP, radius=18, fill=(14, 24, 56), outline=(60, 85, 150), width=3)
    for w in WALLS:
        d.rectangle(w, fill=(95, 120, 190))
    yx, yy = YOU
    a = -1.2 + 0.1 * math.sin(t * 1.5)  # the view sweeps a little: nothing stands still
    cone = [(yx, yy)] + [(yx + 520 * math.cos(a + k * 0.09), yy + 520 * math.sin(a + k * 0.09))
                         for k in range(-6, 7)]
    d.polygon(cone, fill=(94, 231, 255, 40))
    d.polygon(((yx + 34 * math.cos(a), yy + 34 * math.sin(a)), (yx + 22 * math.cos(a + 2.4), yy + 22 * math.sin(a + 2.4)),
               (yx + 22 * math.cos(a - 2.4), yy + 22 * math.sin(a - 2.4))), fill=CYAN)
    d.text((yx, yy + 40), "ты", font=font("Manrope", 30, "ExtraBold"), fill=CYAN, anchor="mm")
    c.put(lay, dim)


def enemy(c: Canvas, x, y, alpha: float, t: float, i: int) -> None:
    lay, d = c.layer()
    bob = 4 * math.sin(t * 3 + i * 2)
    d.ellipse((x - 16, y - 40 + bob, x + 16, y - 8 + bob), fill=RED)
    d.rounded_rectangle((x - 22, y - 6 + bob, x + 22, y + 40 + bob), radius=10, fill=RED)
    c.put(lay, alpha)


def boxes(c: Canvas, t: float, t0: float) -> None:
    """Wallhack overlay: red frames and distances drawn right through the walls."""
    for i, (x, y, _) in enumerate(ENEMIES):
        p = prog(t, t0 + i * 0.3, 0.3)
        if p <= 0:
            continue
        lay, d = c.layer()
        s = 1.3 - 0.3 * p
        d.rectangle((x - 50 * s, y - 70 * s, x + 50 * s, y + 70 * s), outline=RED, width=5)
        d.line((x - 62 * s, y - 70 * s, x - 62 * s, y + 70 * s), fill=GREEN, width=6)
        d.text((x, y + 84 * s), DIST[i], font=font("Manrope", 28, "ExtraBold"), fill=WHITE, anchor="mm")
        c.put(lay, p, glow=8)


def hook(c: Canvas, t: float) -> None:
    c.header("КАК УСТРОЕНЫ ИГРЫ", t)
    big_title(c, ("КАК ЧИТЕР", "ВИДИТ СКВОЗЬ", "СТЕНЫ?"), t)
    level(c, t)
    for i, (x, y, hidden) in enumerate(ENEMIES):
        enemy(c, x, y, 0.25 if hidden else 1.0, t, i)
    boxes(c, t, 0.4)


def packets(c: Canvas, t: float) -> None:
    c.header("ПОЧЕМУ ЭТО ВОЗМОЖНО", t)
    c.title("ИГРА САМА ГОВОРИТ,", "ГДЕ ВСЕ ВРАГИ", t)
    # server → your PC
    lay, d = c.layer()
    for i in range(3):
        y = 500 + i * 54
        d.rounded_rectangle((110, y, 330, y + 44), radius=10, fill=CARD, outline=CYAN, width=3)
    d.text((220, 680), "сервер игры", font=font("Manrope", 30, "ExtraBold"), fill=MUTED, anchor="mm")
    d.rounded_rectangle((720, 490, 970, 640), radius=14, fill=CARD, outline=CYAN, width=4)
    d.rectangle((820, 640, 870, 670), fill=(60, 85, 150))
    d.text((845, 700), "твой ПК", font=font("Manrope", 30, "ExtraBold"), fill=MUTED, anchor="mm")
    c.put(lay, prog(t, 0.1, 0.4))
    lay, d = c.layer()
    for k in range(5):
        ph = (t * 0.8 + k * 0.2) % 1.0
        x = 340 + (710 - 340) * ph
        d.rounded_rectangle((x - 26, 548, x + 26, 576), radius=8, fill=YELLOW)
    c.put(lay, prog(t, 0.4, 0.3), glow=6)
    c.card((110, 780, 970, 1140), t, 0.8, outline=(70, 95, 160))
    rows = ("враг 1:  x 820  y 600   за стеной", "враг 2:  x 800  y 1010  за стеной", "враг 3:  x 370  y 640")
    for i, r in enumerate(rows):
        color = RED if "стеной" in r else WHITE
        c.text((150, 820 + i * 80), r, 38, color, "Manrope", "ExtraBold", t, 1.0 + i * 0.35)
    c.text((540, 1080), "чтобы шаги и выход из-за угла были без задержки", 30, MUTED, "Manrope", "Bold", t, 2.2,
           anchor="mm")
    c.pill((540, 1240), "ТВОЙ ПК ЗНАЕТ ВСЁ", YELLOW, t, 2.8, size=44)


def wallhack(c: Canvas, t: float) -> None:
    c.header("WALLHACK", t)
    c.title("ЧИТ ЧИТАЕТ ПАМЯТЬ", "И РИСУЕТ РАМКИ", t)
    level(c, t)
    for i, (x, y, hidden) in enumerate(ENEMIES):
        enemy(c, x, y, 0.25 if hidden else 1.0, t, i)
    boxes(c, t, 0.8)
    c.pill((540, 1240), "СТЕНА ЕСТЬ — СЕКРЕТА НЕТ", RED, t, 2.2, size=42, text_color=WHITE)


def aimbot(c: Canvas, t: float) -> None:
    c.header("AIMBOT", t)
    c.title("ПРИЦЕЛ НАВОДИТСЯ", "САМ", t)
    tx, ty = 640, 760
    lay, d = c.layer()
    d.ellipse((tx - 60, ty - 150, tx + 60, ty - 30), fill=RED)
    d.rounded_rectangle((tx - 85, ty - 30, tx + 85, ty + 200), radius=30, fill=RED)
    c.put(lay, prog(t, 0.1, 0.3))
    # the crosshair wanders, then snaps to the head in a few frames
    snap = ease((t - 1.6) / 0.1)
    wx, wy = 330 + 60 * math.sin(t * 2.2), 1000 + 40 * math.cos(t * 1.7)
    cx, cy = wx + (tx - wx) * snap, wy + (ty - 90 - wy) * snap
    lay, d = c.layer()
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        d.line((cx + dx * 18, cy + dy * 18, cx + dx * 50, cy + dy * 50), fill=WHITE, width=6)
    if 1.6 <= t < 2.0:
        d.line((wx, wy, cx, cy), fill=(255, 255, 255, 120), width=4)
    c.put(lay, glow=6 if snap >= 1 else 0)
    c.text((540, 1180), "МГНОВЕННО", 96, YELLOW, "Unbounded", "Black", t, 1.8, anchor="mm", glow=12)
    c.text((540, 1270), "человек так не умеет — по этому и ловят", 32, MUTED, "Manrope", "ExtraBold", t, 2.2,
           anchor="mm")


def fog(c: Canvas, t: float) -> None:
    c.header("ЗАЩИТА · VALORANT", t)
    c.title("СЕРВЕР НЕ ПРИСЫЛАЕТ", "ТЕХ, КОГО НЕ ВИДНО", t)
    level(c, t)
    gone = ease((t - 1.0) / 0.8)
    for i, (x, y, hidden) in enumerate(ENEMIES):
        enemy(c, x, y, (0.25 * (1 - gone)) if hidden else 1.0, t, i)
        if hidden and gone > 0.5:
            c.text((x, y), "?", 90, MUTED, "Unbounded", "Black", t, 1.4, anchor="mm")
    c.pill((540, 1240), "ЧИТУ НЕЧЕГО ЧИТАТЬ", GREEN, t, 2.2, size=44)


def trap(c: Canvas, t: float) -> None:
    c.header("ЛОВУШКА · DOTA 2, 2023", t)
    c.title("VALVE ПОСТАВИЛА", "ПРИМАНКУ", t)
    rows = ("позиция героя", "здоровье", "ДАННЫЕ-ПРИМАНКА", "золото")
    for i, r in enumerate(rows):
        y = 480 + i * 92
        bait = "ПРИМАНКА" in r
        c.card((140, y, 940, y + 76), t, 0.2 + i * 0.15, outline=YELLOW if bait else (60, 85, 150),
               width=5 if bait else 3)
        c.text((180, y + 38), r, 36, YELLOW if bait else WHITE, "Manrope", "ExtraBold", t, 0.25 + i * 0.15,
               anchor="lm")
    c.text((540, 880), "их читает только чит", 40, WHITE, "Manrope", "ExtraBold", t, 1.2, anchor="mm")
    v = 40_000 * ease((t - 1.8) / 1.4)
    c.text((540, 1040), f"{v:,.0f}".replace(",", " "), 150, RED, "Unbounded", "Black", t, 1.8, anchor="mm", glow=14)
    c.text((540, 1150), "аккаунтов — бан навсегда", 44, WHITE, "Manrope", "ExtraBold", t, 2.0, anchor="mm")


def outro(c: Canvas, t: float) -> None:
    c.header("ИТОГ", t)
    c.title("ЧИТЕР ВСЕГДА", "НА ШАГ ПОЗАДИ", t)
    level(c, t)
    for i, (x, y, hidden) in enumerate(ENEMIES):
        enemy(c, x, y, 0.25 if hidden else 1.0, t, i)
    c.pill((540, 1240), "скинь тому, кто опять умер за стеной", YELLOW, t, 1.0, size=38)


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("КАК ЧИТЕР", "ВИДИТ СКВОЗЬ", "СТЕНЫ?")

SCENES = {
    "c1_01hot": (hook, 5.0, 0.6),
    "c1_02": (packets, 9.0),
    "c1_03": (wallhack, 7.0),
    "c1_04": (aimbot, 7.0),
    "c1_05": (fog, 8.0),
    "c1_06": (trap, 10.0),
    "c1_07": (outro, 7.0),
}
