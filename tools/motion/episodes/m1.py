"""m1 · «Тебя пересаживают в Max» — по шагам (Moscow Times/РБК 31.07.2026, Mediascope, Википедия)."""

from episodes.n1 import bar, source
from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog

MAXC = (120, 110, 255)  # Max — violet, Telegram — cyan


def app(c: Canvas, box, name, color, t, t0, dim=False) -> None:
    p = c.card(box, t, t0, outline=color, fill=CARD, radius=40, width=6)
    if p <= 0:
        return
    x0, y0, x1, y1 = box
    c.text(((x0 + x1) / 2, (y0 + y1) / 2), name, 46, MUTED if dim else color, "Unbounded", "Black", t, t0,
           anchor="mm")


def hook(c: Canvas, t: float) -> None:
    c.header("01 / ПЕРЕСАДКА", t)
    c.title("ТЕБЯ ПЕРЕСАЖИВАЮТ", "В MAX", t)
    move = ease((t - 1.2) / 1.0)
    app(c, (90, 560, 450, 800), "Telegram", CYAN, t, 0.3, dim=t > 1.6)
    app(c, (630, 560, 990, 800), "MAX", MAXC, t, 0.5)
    # the user walks from Telegram to Max
    x = 270 + (810 - 270) * move
    c.person((x, 960), t, 0.7, color=YELLOW, r=46)
    c.arrow((300, 1090), (780, 1090), t, 1.2, 1.0, color=MAXC, width=6)
    c.text((540, 1180), "по шагам — смотри до конца", 40, MUTED, "Manrope", "ExtraBold", t, 2.2, anchor="mm")


def step_phone(c: Canvas, t: float) -> None:
    c.header("02 / ШАГ 1–2", t)
    c.title("ВШИЛИ В ТЕЛЕФОН", "И В ГОСУСЛУГИ", t)
    c.card((90, 480, 520, 1000), t, 0.3, outline=(70, 95, 160), fill=(14, 24, 56), radius=46)
    c.text((305, 520), "новый смартфон", 30, MUTED, "Manrope", "Bold", t, 0.35, anchor="ma")
    for i in range(6):
        x = 150 + (i % 3) * 120
        y = 600 + (i // 3) * 130
        is_max = i == 0
        c.card((x, y, x + 90, y + 90), t, 0.5 + i * 0.08, outline=MAXC if is_max else (60, 85, 150),
               fill=(60, 50, 140) if is_max else CARD, radius=22, width=3)
        if is_max:
            c.text((x + 45, y + 45), "MAX", 26, WHITE, "Unbounded", "Black", t, 0.5, anchor="mm")
    c.pill((305, 900), "уже установлен", MAXC, t, 1.2, size=30, text_color=WHITE)
    c.card((560, 480, 990, 1000), t, 1.4, outline=(70, 95, 160), fill=(14, 24, 56), radius=46)
    c.text((775, 520), "Госуслуги", 34, WHITE, "Manrope", "ExtraBold", t, 1.45, anchor="ma")
    c.text((775, 640), "подтвердите", 34, WHITE, "Manrope", "ExtraBold", t, 1.7, anchor="mm")
    c.text((775, 690), "вход через", 34, WHITE, "Manrope", "ExtraBold", t, 1.7, anchor="mm")
    c.pill((775, 780), "MAX", MAXC, t, 2.0, size=44, text_color=WHITE)
    source(c, t, "предустановка — с осени 2025 · запрос входа — с декабря 2025")


def step_free(c: Canvas, t: float) -> None:
    c.header("03 / ШАГ 3", t)
    c.title("MAX —", "БЕСПЛАТНО", t)
    c.text((140, 500), "трафик за месяц (пример)", 34, MUTED, "Manrope", "ExtraBold", t, 0.3)
    rows = (("Telegram", CYAN, 1.0), ("MAX", MAXC, 0.0))
    for i, (name, col, frac) in enumerate(rows):
        y = 600 + i * 200
        c.text((140, y), name, 48, col, "Unbounded", "Black", t, 0.4 + i * 0.3)
        bar(c, (140, y + 80, 940, y + 135), max(frac, 0.001), col if frac else (60, 85, 150), t, 0.6 + i * 0.3, 1.4)
        gb = 12 * ease((t - 0.6) / 1.4) if frac else 0
        c.text((940, y + 5), f"{gb:.0f} ГБ", 44, col, "Unbounded", "Black", t, 0.6 + i * 0.3, anchor="ra")
    c.pill((540, 1040), "с августа не тратит твои гигабайты", MAXC, t, 2.2, size=36, text_color=WHITE)
    source(c, t, "соглашение Max и МТС, Билайна, МегаФона, Т2 · РБК, 31.07.2026")


def step_choke(c: Canvas, t: float) -> None:
    c.header("04 / ШАГ 4", t)
    c.title("А TELEGRAM", "ДУШАТ", t)
    rows = (("август 2025", "звонки ограничены"), ("10 февраля 2026", "официальное замедление"),
            ("весна 2026", "без VPN почти не работает"))
    for i, (when, what) in enumerate(rows):
        y = 500 + i * 190
        c.card((90, y, 990, y + 155), t, 0.3 + i * 0.5, outline=RED)
        c.text((140, y + 30), when, 38, RED, "Unbounded", "Black", t, 0.35 + i * 0.5)
        c.text((140, y + 92), what, 36, WHITE, "Manrope", "ExtraBold", t, 0.45 + i * 0.5)
    source(c, t, "Роскомнадзор · Moscow Times · Википедия")


def result(c: Canvas, t: float) -> None:
    c.header("05 / ИТОГ", t)
    c.title("MAX ОБОГНАЛ", "TELEGRAM", t)
    v = 86.2 * ease((t - 0.4) / 1.4)
    c.text((540, 640), f"{v:.1f} МЛН".replace(".", ","), 120, MAXC, "Unbounded", "Black", t, 0.4,
           anchor="mm", glow=14)
    c.text((540, 760), "пользователей Max за июнь 2026", 40, WHITE, "Manrope", "ExtraBold", t, 0.7, anchor="mm")
    c.pill((540, 880), "впервые №1 по месячному охвату", MAXC, t, 1.8, size=38, text_color=WHITE)
    source(c, t, "Mediascope, июнь 2026 · по данным Moscow Times")


def _outro(c: Canvas, t: float) -> None:
    c.header("06 / ТВОЙ ВЫБОР", t)
    c.title("ОСТАТЬСЯ", "В TELEGRAM", t)
    items = ("работает прямо на симке", "даже при белых списках", "голосовые, видео — без тормозов")
    for i, it in enumerate(items):
        y = 500 + i * 160
        c.card((90, y, 990, y + 125), t, 0.3 + i * 0.35, outline=GREEN, fill=CARD)
        c.mark((170, y + 62), True, t, 0.5 + i * 0.35, r=40)
        c.text((240, y + 40), it, 38, WHITE, "Manrope", "ExtraBold", t, 0.45 + i * 0.35)


def outro_youtube(c: Canvas, t: float) -> None:
    _outro(c, t)
    c.pill((540, 1050), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 1.8, size=40)
    c.text((540, 1150), "3 дня бесплатно — проверь сам", 36, MUTED, "Manrope", "ExtraBold", t, 2.1, anchor="mm")


def outro_instagram(c: Canvas, t: float) -> None:
    _outro(c, t)
    c.pill((540, 1050), "напиши VPN в комментах", YELLOW, t, 1.8, size=44)
    c.text((540, 1150), "пришлю ссылку и 3 дня бесплатно", 34, MUTED, "Manrope", "ExtraBold", t, 2.1,
           anchor="mm")


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("ЗАЧЕМ ТЕБЯ", "ПЕРЕСАЖИВАЮТ", "В MAX?")

SCENES = {
    "m1_01": (hook, 5.0),
    "m1_02": (step_phone, 7.0),
    "m1_03": (step_free, 7.0),
    "m1_04": (step_choke, 7.0),
    "m1_05": (result, 6.0),
    "m1_06yt": (outro_youtube, 8.0),
    "m1_06ig": (outro_instagram, 8.0),
    # Instagram cut: no fade-in on frame one — title, apps and the walking user are already on screen
    "m1_01hot": (hook, 4.0, 1.0),
}
