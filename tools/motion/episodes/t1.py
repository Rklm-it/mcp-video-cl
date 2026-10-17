"""t1 · «65 млн россиян заходят в Telegram через VPN» — как замедляют Telegram (факты: Википедия, РКН, Дуров)."""

import math

from episodes.n1 import source
from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog


def hook(c: Canvas, t: float) -> None:
    c.header("01 / ЦИФРА", t)
    c.title("ТЕБЯ ОТРЕЗАЮТ", "ОТ TELEGRAM", t)
    v = 65_000_000 * ease((t - 0.4) / 1.6)
    c.text((540, 640), f"{v:,.0f}".replace(",", " "), 118, CYAN, "Unbounded", "Black", t, 0.4, anchor="mm",
           glow=12)
    c.text((540, 760), "россиян каждый день", 44, WHITE, "Manrope", "ExtraBold", t, 0.6, anchor="mm")
    c.text((540, 820), "заходят в Telegram через VPN", 44, WHITE, "Manrope", "ExtraBold", t, 0.8, anchor="mm")
    # crowd of small people
    for i in range(14):
        x = 120 + (i % 7) * 140
        y = 960 + (i // 7) * 120
        c.person((x, y), t, 1.4 + i * 0.05, color=CYAN if i % 5 else YELLOW, r=26)
    c.pill((540, 1210), "по словам Павла Дурова, апрель 2026", YELLOW, t, 2.4, size=32)


def timeline(c: Canvas, t: float) -> None:
    c.header("02 / КАК ДОШЛИ", t)
    c.title("СНАЧАЛА ЗВОНКИ,", "ПОТОМ ВСЁ ОСТАЛЬНОЕ", t)
    rows = (("август 2025", "звонки отключили", RED),
            ("10 февраля 2026", "РКН: замедляем весь Telegram", RED),
            ("март 2026", "6 тыс. жалоб на сбои за день", YELLOW))
    lay, d = c.layer()
    p = prog(t, 0.3, 1.6)
    d.line((150, 520, 150, 520 + 560 * p), fill=(70, 95, 160), width=6)
    c.put(lay)
    for i, (when, what, col) in enumerate(rows):
        y = 520 + i * 200
        t0 = 0.4 + i * 0.5
        pp = prog(t, t0, 0.3)
        if pp > 0:
            lay, d = c.layer()
            d.ellipse((150 - 22, y + 18, 150 + 22, y + 62), fill=col)
            c.put(lay, pp, glow=8)
        c.card((210, y, 990, y + 160), t, t0, outline=col)
        c.text((250, y + 30), when, 40, col, "Unbounded", "Black", t, t0 + 0.05)
        c.text((250, y + 95), what, 36, WHITE, "Manrope", "ExtraBold", t, t0 + 0.1)
    source(c, t, "Википедия: «Блокировка Telegram в России (2026)»")


def media(c: Canvas, t: float) -> None:
    c.header("03 / ЧТО РЕЖУТ", t)
    c.title("ЭТО НЕ ТВОЙ", "ТЕЛЕФОН ГЛЮЧИТ", t)
    c.card((140, 480, 940, 1220), t, 0.2, outline=(70, 95, 160), fill=(14, 24, 56), radius=46)
    c.text((190, 510), "Чат", 40, WHITE, "Manrope", "ExtraBold", t, 0.25)
    c.text((890, 515), "LTE", 30, MUTED, "Manrope", "Bold", t, 0.25, anchor="ra")
    items = (("текст", "привет, ты где?", True), ("голосовое", "0:12", False),
             ("фото", "", False), ("видео", "", False))
    for i, (kind, label, ok) in enumerate(items):
        y = 600 + i * 150
        t0 = 0.5 + i * 0.35
        c.card((190, y, 760, y + 115), t, t0, outline=GREEN if ok else (60, 85, 150), fill=(40, 70, 140),
               radius=30, width=3)
        c.text((230, y + 22), kind, 30, MUTED, "Manrope", "Bold", t, t0)
        if label:
            c.text((230, y + 60), label, 34, WHITE, "Manrope", "ExtraBold", t, t0)
        if ok:
            c.mark((840, y + 58), True, t, t0 + 0.3, r=36)
        elif t >= t0:
            if t < 2.6:
                c.spinner((840, y + 58), t, r=30)
            else:
                c.mark((840, y + 58), False, t, 2.6, r=36)
    source(c, t, "по данным СМИ после замедления, февраль 2026")


def disguise(c: Canvas, t: float) -> None:
    c.header("04 / ОТВЕТ TELEGRAM", t)
    c.title("КОШКИ-МЫШКИ", "С ФИЛЬТРАМИ", t)
    c.card((400, 640, 700, 860), t, 0.3, outline=YELLOW, width=6)
    c.text((550, 725), "ТСПУ", 64, YELLOW, "Unbounded", "Black", t, 0.35, anchor="mm")
    c.text((550, 810), "ищет Telegram", 30, MUTED, t=t, t0=0.4, anchor="mm")
    c.text((90, 600), "как есть", 34, RED, "Manrope", "ExtraBold", t, 0.6)
    c.text((90, 960), "под видом обычного трафика", 34, GREEN, "Manrope", "ExtraBold", t, 1.6)
    for i in range(3):
        # plain Telegram packets stop at the filter
        t0 = 0.8 + i * 0.5
        k = (t - t0) / 0.9
        if k > 0:
            x = 120 + min(k, 1) * 210
            lay, d = c.layer()
            d.rounded_rectangle((x - 55, 726, x + 55, 774), radius=12, fill=RED)
            d.text((x, 750), "TG", font=font("Manrope", 26, "ExtraBold"), fill=NAVY, anchor="mm")
            c.put(lay, 1.0 if k < 1 else max(0.0, 1.8 - k), glow=6)
            if k >= 1:
                c.mark((380, 690), False, t, t0 + 0.9, r=26)
    for i in range(8):
        # disguised packets pass below the filter and fly on
        t1_ = 1.8 + i * 0.6
        k2 = (t - t1_) / 1.6
        if 0 < k2 < 1.2:
            x = 120 + k2 * 900
            lay, d = c.layer()
            d.rounded_rectangle((x - 70, 1036, x + 70, 1084), radius=12, fill=GREEN)
            d.text((x, 1060), "обычный", font=font("Manrope", 24, "ExtraBold"), fill=NAVY, anchor="mm")
            c.put(lay, 1.0, glow=6)
    c.text((540, 1180), "трафик притворяется обычным", 44, YELLOW, "Manrope", "ExtraBold", t, 3.2,
           anchor="mm")
    source(c, t, "заявление Павла Дурова, апрель 2026")


def _outro(c: Canvas, t: float) -> None:
    c.header("05 / ДО И ПОСЛЕ", t)
    c.title("НА СИМКЕ С NEXUS", "РАБОТАЕТ ВСЁ", t)
    cols = ((90, "без VPN", RED, False, 0.3), (560, "с Nexus", GREEN, True, 1.2))
    rows = ("голосовые, видео", "любые сайты", "труднодоступные")
    for x, name, col, ok, t0 in cols:
        c.card((x, 480, x + 430, 900), t, t0, outline=col, width=5)
        c.text((x + 215, 530), name, 44, col, "Unbounded", "Black", t, t0 + 0.05, anchor="mm")
        for k, r in enumerate(rows):
            y = 610 + k * 95
            c.text((x + 30, y), r, 30, WHITE, "Manrope", "ExtraBold", t, t0 + 0.15 + k * 0.15)
            if ok:
                c.mark((x + 385, y + 18), True, t, t0 + 0.3 + k * 0.2, r=26)
            elif t < 1.0:
                c.spinner((x + 385, y + 18), t, r=20)
            else:
                c.mark((x + 385, y + 18), False, t, 1.0 + k * 0.1, r=26)
    c.pill((540, 960), "мобильный интернет · даже при белых списках", CYAN, t, 1.9, size=32)


def outro_youtube(c: Canvas, t: float) -> None:
    _outro(c, t)
    c.pill((540, 1070), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 2.4, size=40)
    c.text((540, 1165), "3 дня бесплатно — проверь сам", 36, MUTED, "Manrope", "ExtraBold", t, 2.4, anchor="mm")


def outro_instagram(c: Canvas, t: float) -> None:
    _outro(c, t)
    c.pill((540, 1070), "напиши VPN в комментах", YELLOW, t, 2.4, size=44)
    c.text((540, 1165), "пришлю ссылку и 3 дня бесплатно", 34, MUTED, "Manrope", "ExtraBold", t, 2.4,
           anchor="mm")


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("КАК ТЕБЯ", "ОТРЕЗАЮТ", "ОТ TELEGRAM?")

SCENES = {
    "t1_01": (hook, 7.0),
    "t1_02": (timeline, 8.0),
    "t1_03": (media, 7.0),
    "t1_04": (disguise, 7.0),
    "t1_05yt": (outro_youtube, 8.0),
    "t1_05ig": (outro_instagram, 8.0),
}
