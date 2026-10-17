"""d1 · «Что такое DDoS-атака?» — топ-тема @aldoniq (42,5 тыс. лайков). ~15 с, одна живая схема на весь ролик:
поле гаджетов заражается, бьёт в сервер, сервер ложится; в конце — «а среди них твой роутер?».

v2 (17.10): первая версия вышла 27 с с замиранием кадра в конце сцен (голос длиннее клипов) и бедной картинкой.
Теперь клипы длиннее голоса и всё время в движении. v3: 13,7 с — «слишком коротко» (владелец), добавлены сцены
«как гаджет становится ботом» и «как спасаются сайты» — ~25 с.

Факты: рекорд — 31,4 Тбит/с, IV кв. 2025, ботнет Aisuru/Kimwolf (Cloudflare, Threat Report 2026); у четырёх
ботнетов — не меньше 3 млн заражённых устройств: видеорегистраторы, веб-камеры, Wi-Fi-роутеры, ТВ-приставки
(Минюст США, 20.03.2026 — The Hacker News, SecurityWeek).
"""

import math
import random

from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog

COLS, ROWS = 7, 5
GRID_X0, GRID_Y0, STEP_X, STEP_Y = 120, 480, 140, 108
SCALE = 1.45
SERVER = (540, 1110)
DEVICES = [(GRID_X0 + col * STEP_X, GRID_Y0 + row * STEP_Y, ("cam", "router", "tv")[(col + row) % 3])
           for row in range(ROWS) for col in range(COLS)]
ORDER = list(range(len(DEVICES)))
random.Random(7).shuffle(ORDER)
RANK = {dev: k / len(ORDER) for k, dev in enumerate(ORDER)}  # when each device gets infected, 0..1
MINE = COLS + 3  # the router the last scene zooms into (kind cycles cam/router/tv by col+row)


def device(d, x, y, kind, color, s=1.0) -> None:
    if kind == "cam":
        d.rounded_rectangle((x - 26 * s, y - 16 * s, x + 18 * s, y + 16 * s), radius=7 * s, fill=color)
        d.ellipse((x - 14 * s, y - 9 * s, x + 4 * s, y + 9 * s), fill=NAVY)
        d.polygon(((x + 18 * s, y - 8 * s), (x + 30 * s, y - 15 * s), (x + 30 * s, y + 15 * s),
                   (x + 18 * s, y + 8 * s)), fill=color)
    elif kind == "router":
        d.rounded_rectangle((x - 30 * s, y - 2 * s, x + 30 * s, y + 18 * s), radius=6 * s, fill=color)
        d.line((x - 20 * s, y - 2 * s, x - 27 * s, y - 24 * s), fill=color, width=max(2, int(5 * s)))
        d.line((x + 20 * s, y - 2 * s, x + 27 * s, y - 24 * s), fill=color, width=max(2, int(5 * s)))
    else:
        d.rounded_rectangle((x - 28 * s, y - 8 * s, x + 28 * s, y + 14 * s), radius=6 * s, fill=color)
        d.ellipse((x + 14 * s, y - 1 * s, x + 20 * s, y + 5 * s), fill=NAVY)


def field(c: Canvas, t: float, infected: float, firing: bool, dim: float = 1.0, mine: float = 0.0,
          wall: float | None = None) -> None:
    """All devices; `infected` 0..1 turns them red one by one, `firing` sends their requests into the server;
    with `wall` (a y) the requests die on the filter line instead of reaching the server."""
    lay, d = c.layer()
    for i, (x, y, kind) in enumerate(DEVICES):
        bad = RANK[i] < infected
        bob = 3 * math.sin(t * 3 + i)  # nothing on screen ever stands still
        device(d, x, y + bob, kind, RED if bad else (70, 105, 180), SCALE)
    c.put(lay, dim)
    if firing:
        lay, d = c.layer()
        tx, ty = SERVER
        for i, (x, y, _) in enumerate(DEVICES):
            if RANK[i] >= infected:
                continue
            for k in range(2):
                ph = (t * 1.4 + i * 0.173 + k * 0.5) % 1.0
                px, py = x + (tx - x) * ph, y + 20 + (ty - y - 20) * ph
                if wall is not None and py > wall:
                    continue
                d.ellipse((px - 6, py - 6, px + 6, py + 6), fill=(255, 90, 120, 230))
        c.put(lay, dim, glow=6)
    if mine > 0:
        x, y, kind = DEVICES[MINE]
        lay, d = c.layer()
        r = 66 + 8 * math.sin(t * 6)
        d.ellipse((x - r, y - r + 5, x + r, y + r + 5), outline=YELLOW, width=7)
        c.put(lay, mine, glow=12)
        if mine >= 1:
            c.pill((x, y - 105), "ТВОЙ РОУТЕР?", YELLOW, t, 0.0, size=40)


def server(c: Canvas, t: float, load: float, dim: float = 1.0) -> None:
    cx, cy = SERVER
    shake = 6 * math.sin(t * 40) * max(0.0, load - 0.85) / 0.15 if load > 0.85 else 0.0
    lay, d = c.layer()
    hot = load > 0.85
    for i in range(3):
        y = cy - 70 + i * 54
        d.rounded_rectangle((cx - 120 + shake, y, cx + 120 + shake, y + 46), radius=10, fill=CARD,
                            outline=RED if hot else CYAN, width=4)
        for k in range(3):
            on = (math.sin(t * 9 + i * 2 + k) > 0) if not hot else True
            d.ellipse((cx - 95 + k * 26 + shake, y + 16, cx - 81 + k * 26 + shake, y + 30),
                      fill=RED if hot else (GREEN if on else (40, 80, 60)))
    # load bar
    x0, x1, yb = 300, 780, cy + 120
    d.rounded_rectangle((x0, yb, x1, yb + 26), radius=13, fill=(30, 45, 90))
    d.rounded_rectangle((x0, yb, x0 + max(26, (x1 - x0) * load), yb + 26), radius=13,
                        fill=RED if hot else GREEN)
    d.text((x1 + 20, yb + 13), f"{int(load * 100)}%", font=font("Manrope", 32, "ExtraBold"),
           fill=RED if hot else WHITE, anchor="lm")
    d.text((x0 - 20, yb + 13), "нагрузка", font=font("Manrope", 28, "Bold"), fill=MUTED, anchor="rm")
    c.put(lay, dim, glow=10 if hot else 0)


def big_title(c: Canvas, lines, t: float, t0: float = 0.0) -> None:
    """@aldoniq-style question: white / YELLOW BIGGER / white, full width."""
    if c.bare:  # the cover draws its own question
        return
    y = 170
    for i, line in enumerate(lines):
        big = i == 1
        size = 118 if big else 70
        while font("Unbounded", size, "Black").getlength(line) > 960:
            size -= 2
        c.text((60, y), line, size, YELLOW if big else WHITE, "Unbounded", "Black", t, t0 + i * 0.12)
        y += size + 12


def hook(c: Canvas, t: float) -> None:
    c.header("КАК УСТРОЕН ИНТЕРНЕТ", t)
    big_title(c, ("ЧТО ТАКОЕ", "DDOS-АТАКА?"), t)
    infected = 0.15 * ease((t - 1.5) / 2.0)
    field(c, t, infected, firing=t > 1.5)
    server(c, t, 0.05 + infected)


def attack(c: Canvas, t: float) -> None:
    c.header("КАК ЭТО РАБОТАЕТ", t)
    c.title("МИЛЛИОНЫ ГАДЖЕТОВ", "БЬЮТ В ОДИН СЕРВЕР", t)
    infected = 0.15 + 0.85 * ease(t / 3.2)
    field(c, t, infected, firing=True)
    load = min(1.0, 0.2 + 0.85 * ease((t - 0.3) / 3.0))
    server(c, t, load)
    c.pill((540, 1330), "СЕРВЕР ЛЁГ", RED, t, 3.3, size=48, text_color=WHITE)


def record(c: Canvas, t: float) -> None:
    c.header("РЕКОРД · CLOUDFLARE", t)
    field(c, t, 1.0, firing=True, dim=0.25)
    server(c, t, 1.0, dim=0.25)
    v = 31.4 * ease(t / 1.0)
    c.text((540, 640), f"{v:.1f}".replace(".", ","), 230, RED, "Unbounded", "Black", t, 0.0, anchor="mm", glow=16)
    c.text((540, 800), "ТЕРАБИТ В СЕКУНДУ", 60, WHITE, "Unbounded", "Black", t, 0.15, anchor="mm")
    c.text((540, 900), "самая мощная атака в истории · конец 2025", 34, MUTED, "Manrope", "ExtraBold", t, 0.4,
           anchor="mm")


TRIES = (("123456", False), ("password", False), ("admin", True))


def infect(c: Canvas, t: float) -> None:
    c.header("КАК ЗАРАЖАЮТ", t)
    c.title("КАК ГАДЖЕТ", "СТАНОВИТСЯ БОТОМ", t)
    won = 0.6 + 1.4 * (len(TRIES) - 1) + 0.8
    lay, d = c.layer()
    device(d, 540, 590 + 4 * math.sin(t * 3), "router", RED if t >= won else (70, 105, 180), 4.2)
    c.put(lay, prog(t, 0.1, 0.4), glow=14 if t >= won else 0)
    c.card((140, 780, 940, 1110), t, 0.2, outline=(70, 95, 160))
    c.text((190, 815), "вход в роутер", 32, MUTED, "Manrope", "Bold", t, 0.3)
    c.text((190, 880), "логин:   admin", 50, WHITE, "Manrope", "ExtraBold", t, 0.35)
    k = max(0, min(len(TRIES) - 1, int((t - 0.6) // 1.4)))
    word, ok = TRIES[k]
    local = t - 0.6 - 1.4 * k
    typed = word[:max(0, int(len(word) * min(1.0, local / 0.7)))] if t >= 0.6 else ""
    cursor = "|" if math.sin(t * 12) > 0 and local < 0.8 else ""
    c.text((190, 960), f"пароль:  {typed}{cursor}", 50, WHITE, "Manrope", "ExtraBold", t, 0.4)
    if local >= 0.8 and t >= 0.6:
        c.mark((860, 990), ok, t, 0.6 + 1.4 * k + 0.8, r=40)
    c.text((540, 1170), "вирус перебирает заводские пароли", 36, YELLOW, "Manrope", "ExtraBold", t, 0.5,
           anchor="mm")
    c.pill((540, 1300), "ВЗЛОМАН — ТЕПЕРЬ ЭТО БОТ", RED, t, won + 0.2, size=44, text_color=WHITE)


WALL = 990


def shield(c: Canvas, t: float) -> None:
    c.header("ЗАЩИТА", t)
    c.title("КАК СПАСАЮТСЯ", "САЙТЫ", t)
    up = prog(t, 0.6, 0.5)
    field(c, t, 1.0, firing=True, wall=WALL if up >= 1 else None)
    lay, d = c.layer()
    d.rounded_rectangle((90, WALL - 12, 90 + 900 * up, WALL + 12), radius=12, fill=CYAN)
    if up >= 1:
        rnd = random.Random(int(t * 20))
        for _ in range(10):  # sparks where the junk hits the filter
            x = rnd.uniform(140, 940)
            d.ellipse((x - 9, WALL - 30, x + 9, WALL - 12), fill=(255, 150, 170))
    c.put(lay, glow=14)
    c.pill((540, WALL), "ФИЛЬТР", CYAN, t, 1.0, size=36)
    server(c, t, 1.0 - 0.85 * ease((t - 1.2) / 1.5))
    c.pill((540, 1330), "мусор отсеян до сервера", GREEN, t, 2.6, size=44)


def yours(c: Canvas, t: float) -> None:
    c.header("ПРОВЕРЬ СЕБЯ", t)
    c.title("3 МИЛЛИОНА ИЗ НИХ —", "ДОМАШНИЕ ГАДЖЕТЫ", t)
    field(c, t, 1.0, firing=True, dim=1.0, mine=prog(t, 0.8, 0.4))
    server(c, t, 1.0)
    c.pill((540, 1330), "смени заводской пароль", YELLOW, t, 2.4, size=46)


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("ЧТО ТАКОЕ", "DDOS-АТАКА?", "И ПРИ ЧЁМ ТУТ ТВОЙ РОУТЕР")

SCENES = {
    "d1_01hot": (hook, 5.0, 0.6),
    "d1_02": (attack, 7.0),
    "d1_03": (record, 5.0),
    "d1_04": (infect, 9.0),
    "d1_05": (shield, 7.0),
    "d1_06": (yours, 7.0),
}
