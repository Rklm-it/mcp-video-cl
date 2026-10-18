"""o1 · «Сделай это сегодня — пока не отключили мобильный интернет» (охватная тема, Instagram ~20 с)."""

import math

from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog


def hook(c: Canvas, t: float) -> None:
    c.header("ЧЕК-ЛИСТ НА ОТКЛЮЧЕНИЕ", t)
    c.title("СДЕЛАЙ ЭТО", "ПОКА ЕСТЬ ИНТЕРНЕТ", t)
    # phone losing signal
    c.card((300, 480, 780, 1100), t, 0.1, outline=(70, 95, 160), fill=(14, 24, 56), radius=56)
    lay, d = c.layer()
    bars = 4 - min(4, int(max(0.0, t - 0.6) / 0.35))
    for i in range(4):
        x = 420 + i * 60
        h = 40 + i * 40
        d.rounded_rectangle((x, 760 - h, x + 40, 760), radius=8, fill=WHITE if i < bars else (50, 65, 110))
    c.put(lay)
    c.text((540, 830), "LTE" if bars else "НЕТ СЕТИ", 56, WHITE if bars else RED, "Unbounded", "Black", t, 0.1,
           anchor="mm")
    if not bars:
        c.mark((540, 960), False, t, 2.0, r=56)
    c.pill((540, 1180), "3 шага — сохрани", YELLOW, t, 0.3, size=44)


def offline(c: Canvas, t: float) -> None:
    c.header("ШАГ 1", t)
    c.title("СКАЧАЙ", "ОФЛАЙН", t)
    # map card with a pin
    c.card((90, 480, 520, 900), t, 0.2, outline=CYAN, fill=CARD)
    lay, d = c.layer()
    for k in range(6):
        d.line((90, 530 + k * 65, 520, 500 + k * 75), fill=(40, 70, 130), width=6)
        d.line((140 + k * 70, 480, 120 + k * 75, 900), fill=(40, 70, 130), width=4)
    c.put(lay, prog(t, 0.2))
    c.mark((305, 680), True, t, 0.8, r=40)
    c.text((305, 850), "карты города", 34, WHITE, "Manrope", "ExtraBold", t, 0.6, anchor="mm")
    docs = ("билеты", "QR-коды", "документы")
    for i, dname in enumerate(docs):
        y = 480 + i * 145
        c.card((560, y, 990, y + 120), t, 0.9 + i * 0.3, outline=YELLOW, fill=CARD, radius=22)
        c.text((600, y + 38), dname, 38, WHITE, "Manrope", "ExtraBold", t, 0.95 + i * 0.3)
        c.mark((940, y + 60), True, t, 1.2 + i * 0.3, r=28)
    c.pill((540, 1000), "скрины — в галерею", YELLOW, t, 2.0, size=40)


def cash(c: Canvas, t: float) -> None:
    c.header("ШАГ 2", t)
    c.title("НЕМНОГО", "НАЛИЧНЫХ", t)
    # terminal without connection
    c.card((90, 480, 520, 1000), t, 0.2, outline=(70, 95, 160), fill=(14, 24, 56), radius=36)
    c.text((305, 560), "терминал", 36, MUTED, "Manrope", "ExtraBold", t, 0.25, anchor="mm")
    if t < 1.3:
        c.spinner((305, 720), t, r=50)
    else:
        c.mark((305, 720), False, t, 1.3, r=56)
    c.text((305, 880), "нет связи", 40, RED, "Unbounded", "Black", t, 1.4, anchor="mm")
    # banknotes
    for i in range(3):
        y = 560 + i * 120
        p = prog(t, 1.6 + i * 0.2, 0.4)
        if p <= 0:
            continue
        lay, d = c.layer()
        x = 600 + (1 - p) * 120
        d.rounded_rectangle((x, y, x + 360, y + 160), radius=18, fill=(60, 140, 90), outline=(120, 220, 150), width=4)
        d.text((x + 180, y + 80), "₽", font=font("Unbounded", 80, "Black"), fill=(200, 255, 210), anchor="mm")
        c.put(lay, p)
    c.text((540, 1120), "без связи отваливаются и терминалы", 38, YELLOW, "Manrope", "ExtraBold", t, 2.3,
           anchor="mm")


def _vpn(c: Canvas, t: float) -> None:
    c.header("ШАГ 3", t)
    c.title("VPN ДЛЯ", "БЕЛЫХ СПИСКОВ", t)
    items = ("офлайн-карты и скрины", "немного наличных", "VPN, который работает на симке")
    for i, it in enumerate(items):
        y = 480 + i * 150
        c.card((90, y, 990, y + 120), t, 0.2 + i * 0.25, outline=GREEN, fill=CARD)
        c.mark((165, y + 60), True, t, 0.35 + i * 0.25, r=38)
        c.text((230, y + 38), it, 38, WHITE, "Manrope", "ExtraBold", t, 0.3 + i * 0.25)


def outro_instagram(c: Canvas, t: float) -> None:
    _vpn(c, t)
    c.pill((540, 1000), "напиши VPN в комментах", YELLOW, t, 1.2, size=44)
    c.pill((540, 1110), "сохрани, чтобы не потерять", WHITE, t, 1.6, size=36)


def outro_youtube(c: Canvas, t: float) -> None:
    _vpn(c, t)
    c.pill((540, 1000), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 1.2, size=40)
    c.pill((540, 1110), "сохрани, чтобы не потерять", WHITE, t, 1.6, size=36)


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("ЧТО СДЕЛАТЬ,", "ПОКА ЕСТЬ", "ИНТЕРНЕТ?")

SCENES = {
    "o1_01hot": (hook, 4.0, 0.6),
    "o1_02": (offline, 6.0),
    "o1_03": (cash, 5.0),
    "o1_04ig": (outro_instagram, 7.0),
    "o1_04yt": (outro_youtube, 7.0),
}
