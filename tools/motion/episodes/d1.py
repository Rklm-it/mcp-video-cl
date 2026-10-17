"""d1 · «Что такое DDoS-атака?» — топ-тема @aldoniq (42,5 тыс. лайков), наш разбор: ~18 с, хук с кадра 0.

Факты: рекорд — 31,4 Тбит/с, IV кв. 2025, ботнет Aisuru/Kimwolf (Cloudflare, отчёт за Q4 2025 и Threat Report
2026); у четырёх ботнетов — не меньше 3 млн заражённых устройств: видеорегистраторы, веб-камеры, Wi-Fi-роутеры
(Минюст США, 20.03.2026 — The Hacker News, SecurityWeek); Kimwolf — >2 млн неофициальных Android-ТВ-приставок
(KrebsOnSecurity). 31,4 Тбит/с ≈ 3,9 ТБ/с ≈ 200 фильмов 4K по ~20 ГБ каждую секунду.
"""

import math

from episodes.n1 import source
from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog

SERVER = (540, 820)
# where requests fly from: a ring around the server, fixed so every frame draws the same swarm
SOURCES = [(540 + 470 * math.cos(a), 820 + 330 * math.sin(a))
           for a in (i * 2.39996 for i in range(64))]  # golden angle: spread evenly


def server(c: Canvas, center, t, t0, load: float) -> None:
    """Server rack: three units with lights; the lights go red as the load grows."""
    p = prog(t, t0, 0.35)
    if p <= 0:
        return
    cx, cy = center
    lay, d = c.layer()
    for i in range(3):
        y = cy - 120 + i * 84
        d.rounded_rectangle((cx - 130, y, cx + 130, y + 70), radius=14, fill=CARD,
                            outline=RED if load > 0.8 else CYAN, width=4)
        for k in range(3):
            d.ellipse((cx - 100 + k * 34, y + 25, cx - 80 + k * 34, y + 45),
                      fill=RED if load > 0.5 + k * 0.15 else GREEN)
        d.rounded_rectangle((cx + 20, y + 28, cx + 100, y + 42), radius=7, fill=(40, 60, 110))
    c.put(lay, p, glow=10 if load > 0.8 else 0)


def swarm(c: Canvas, t, t0, count: int) -> None:
    """Requests flying into the server from every side, more and more of them."""
    if t < t0:
        return
    lay, d = c.layer()
    tx, ty = SERVER
    for i, (sx, sy) in enumerate(SOURCES[:count]):
        if t - t0 < i * 0.02:
            continue
        ph = ((t - t0) * 0.9 + i * 0.137) % 1.0
        x, y = sx + (tx - sx) * ph, sy + (ty - sy) * ph
        d.ellipse((sx - 9, sy - 9, sx + 9, sy + 9), fill=(255, 77, 109, 160))
        d.line((x - (tx - sx) * 0.05, y - (ty - sy) * 0.05, x, y), fill=(255, 120, 140, 200), width=4)
        d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=RED)
    c.put(lay, glow=6)


def hook(c: Canvas, t: float) -> None:
    c.header("КАК УСТРОЕН ИНТЕРНЕТ", t)
    c.title("ЧТО ТАКОЕ", "DDOS-АТАКА?", t)
    load = ease((t - 0.4) / 2.2)
    swarm(c, t, 0.3, 12 + int(52 * load))
    server(c, SERVER, t, 0.1, load)
    v = 2000 + (2_000_000 - 2000) * load
    c.text((540, 1215), f"{v:,.0f}".replace(",", " "), 72, RED if load > 0.8 else WHITE, "Unbounded", "Black", t,
           0.2, anchor="mm", glow=10)
    c.text((540, 1285), "запросов в секунду · сервер держит 2 000", 32, MUTED, "Manrope", "Bold", t, 0.3,
           anchor="mm")
    c.pill((540, 1030), "сервер лёг", RED, t, 2.6, size=44, text_color=WHITE)


def record(c: Canvas, t: float) -> None:
    c.header("РЕКОРД", t)
    c.title("САМАЯ МОЩНАЯ", "АТАКА В ИСТОРИИ", t)
    v = 31.4 * ease(t / 1.1)
    c.text((540, 640), f"{v:.1f}".replace(".", ","), 190, RED, "Unbounded", "Black", t, 0.0, anchor="mm", glow=14)
    c.text((540, 780), "терабита в секунду", 48, WHITE, "Manrope", "ExtraBold", t, 0.2, anchor="mm")
    # films flying past: ~200 per second
    lay, d = c.layer()
    shown = int(40 * prog(t, 1.0, 1.2))
    for i in range(shown):
        col, row = i % 10, i // 10
        x, y = 115 + col * 88, 870 + row * 70
        d.rounded_rectangle((x, y, x + 70, y + 52), radius=8, fill=(40, 70, 140), outline=CYAN, width=2)
        d.polygon(((x + 27, y + 14), (x + 27, y + 38), (x + 47, y + 26)), fill=WHITE)
    c.put(lay)
    c.pill((540, 1190), "≈ 200 фильмов в 4K — каждую секунду", YELLOW, t, 1.8, size=40)
    source(c, t, "Cloudflare · IV квартал 2025")


def gadget(c: Canvas, center, kind: str, label: str, t, t0) -> None:
    p = c.card((center[0] - 140, center[1] - 150, center[0] + 140, center[1] + 150), t, t0, outline=(70, 95, 160))
    if p <= 0:
        return
    cx, cy = center[0], center[1] - 30
    lay, d = c.layer()
    if kind == "camera":
        d.rounded_rectangle((cx - 70, cy - 40, cx + 50, cy + 40), radius=16, fill=(60, 85, 150))
        d.ellipse((cx - 40, cy - 25, cx + 10, cy + 25), fill=NAVY, outline=CYAN, width=5)
        d.polygon(((cx + 50, cy - 20), (cx + 85, cy - 38), (cx + 85, cy + 38), (cx + 50, cy + 20)), fill=(60, 85, 150))
    elif kind == "router":
        d.rounded_rectangle((cx - 90, cy, cx + 90, cy + 50), radius=12, fill=(60, 85, 150))
        for k in range(4):
            d.ellipse((cx - 65 + k * 30, cy + 20, cx - 55 + k * 30, cy + 30), fill=GREEN)
        d.line((cx - 60, cy, cx - 75, cy - 60), fill=(60, 85, 150), width=8)
        d.line((cx + 60, cy, cx + 75, cy - 60), fill=(60, 85, 150), width=8)
    else:  # tv box
        d.rounded_rectangle((cx - 80, cy - 10, cx + 80, cy + 40), radius=14, fill=(60, 85, 150))
        d.ellipse((cx + 50, cy + 10, cx + 62, cy + 22), fill=CYAN)
        d.rounded_rectangle((cx - 30, cy - 70, cx + 10, cy - 20), radius=8, fill=(45, 65, 120))
    d.text((cx, cy + 95), label, font=font("Manrope", 32, "ExtraBold"), fill=WHITE, anchor="mm")
    c.put(lay, p)
    c.pill((center[0], center[1] + 150), "БОТ", RED, t, t0 + 0.5, size=32, text_color=WHITE)


def who(c: Canvas, t: float) -> None:
    c.header("КТО СТРЕЛЯЛ", t)
    c.title("НЕ ХАКЕРЫ, А", "3 000 000 ГАДЖЕТОВ", t)
    gadget(c, (230, 640), "camera", "камеры", t, 0.2)
    gadget(c, (540, 640), "router", "роутеры", t, 0.6)
    gadget(c, (850, 640), "tv", "ТВ-приставки", t, 1.0)
    c.text((540, 1000), "заражены — и хозяева не знают", 44, YELLOW, "Manrope", "ExtraBold", t, 1.6, anchor="mm")
    source(c, t, "ботнеты Aisuru/Kimwolf · Минюст США, март 2026")


def check(c: Canvas, y, label, t, t0) -> None:
    c.card((90, y, 990, y + 130), t, t0, outline=(60, 85, 150))
    c.text((150, y + 44), label, 40, WHITE, "Manrope", "ExtraBold", t, t0 + 0.05)
    c.mark((920, y + 65), True, t, t0 + 0.4, r=36)


def _loop(c: Canvas, t: float) -> None:
    c.header("ПРОВЕРЬ СВОЙ", t)
    c.title("ТВОЙ РОУТЕР", "ТОЖЕ МОЖЕТ СТРЕЛЯТЬ", t)
    check(c, 480, "смени заводской пароль", t, 0.2)
    check(c, 640, "обнови прошивку", t, 0.6)
    check(c, 800, "приставки — известных марок", t, 1.0)


def outro_instagram(c: Canvas, t: float) -> None:
    _loop(c, t)
    c.pill((540, 1040), "сохрани — проверишь дома", YELLOW, t, 1.5, size=44)


def outro_youtube(c: Canvas, t: float) -> None:
    _loop(c, t)
    c.pill((540, 1040), "сохрани — проверишь дома", YELLOW, t, 1.5, size=44)
    c.text((540, 1150), "подпишись — объясняю, как устроен интернет", 32, MUTED, "Manrope", "ExtraBold", t, 1.7,
           anchor="mm")


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("ЧТО ТАКОЕ", "DDOS-АТАКА?", "И ПРИ ЧЁМ ТУТ РОУТЕР")

SCENES = {
    "d1_01hot": (hook, 6.0, 0.8),
    "d1_02": (record, 5.5, 0.2),
    "d1_03": (who, 6.0, 0.2),
    "d1_04ig": (outro_instagram, 6.0, 0.2),
    "d1_04yt": (outro_youtube, 7.0, 0.2),
}
