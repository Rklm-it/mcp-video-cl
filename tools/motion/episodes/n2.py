"""n2 · новость 05.10.2026: Минцифры обсуждает плату за международный мобильный трафик (Коммерсантъ)."""

from episodes.n1 import bar, source
from motion import CARD, CYAN, GREEN, MUTED, RED, WHITE, YELLOW, Canvas, ease, font, prog


def news(c: Canvas, t: float) -> None:
    c.header("НОВОСТЬ · 05.10", t)
    c.title("VPN МОЖЕТ", "СТАТЬ ПЛАТНЫМ", t)
    c.card((70, 500, 370, 720), t, 0.2, outline=CYAN)
    c.text((220, 585), "ТЫ", 60, WHITE, "Unbounded", "Black", t, 0.25, anchor="mm")
    c.text((220, 665), "мобильный", 32, MUTED, t=t, t0=0.3, anchor="mm")
    c.card((710, 500, 1010, 720), t, 0.5, outline=CYAN)
    c.text((860, 585), "VPN", 60, WHITE, "Unbounded", "Black", t, 0.55, anchor="mm")
    c.text((860, 665), "за границей", 32, MUTED, t=t, t0=0.6, anchor="mm")
    c.arrow((380, 610), (700, 610), t, 0.8, 0.5, color=YELLOW, width=7)
    c.text((540, 560), "международный", 30, YELLOW, "Manrope", "ExtraBold", t, 1.0, anchor="mm")
    c.text((540, 660), "трафик", 30, YELLOW, "Manrope", "ExtraBold", t, 1.0, anchor="mm")
    v = 50 * ease((t - 1.4) / 1.0)
    c.text((540, 880), f"{v:.0f} ГБ", 150, WHITE, "Unbounded", "Black", t, 1.4, anchor="mm", glow=10)
    c.pill((540, 1030), "сверх лимита — платно", RED, t, 2.4, size=44, text_color=WHITE)
    source(c, t, "Минцифры обсуждает с операторами · Коммерсантъ, 05.10")


def price(c: Canvas, t: float) -> None:
    c.header("02 / СКОЛЬКО", t)
    c.title("150 ₽", "ЗА ГИГАБАЙТ", t)
    c.pill((540, 510), "план, который звучал весной", CYAN, t, 0.2, size=34)
    c.card((90, 580, 990, 1210), t, 0.3, outline=(70, 95, 160), fill=(14, 24, 56))
    c.text((140, 615), "зарубежный трафик за месяц", 34, MUTED, "Manrope", "ExtraBold", t, 0.35)
    # 0..30 GB scale: green up to 15, red above
    x0, x1, y = 140, 940, 700
    p = ease((t - 0.6) / 1.4)
    lay, d = c.layer()
    d.rounded_rectangle((x0, y, x1, y + 60), radius=30, fill=(30, 45, 90))
    mid = x0 + (x1 - x0) / 2
    d.rounded_rectangle((x0, y, x0 + max(60, (mid - x0) * min(1, p * 2)), y + 60), radius=30, fill=GREEN)
    if p > 0.5:
        d.rectangle((mid, y, mid + (x1 - mid) * (p - 0.5) * 2, y + 60), fill=RED)
    c.put(lay, prog(t, 0.6))
    c.text((x0, 785), "0", 32, MUTED, t=t, t0=0.7)
    c.text((mid, 785), "15 ГБ", 32, WHITE, "Manrope", "ExtraBold", t, 1.0, anchor="ma")
    c.text((x1, 785), "30 ГБ", 32, WHITE, "Manrope", "ExtraBold", t, 1.4, anchor="ra")
    c.text((140, 880), "в лимите", 38, GREEN, "Manrope", "ExtraBold", t, 1.2)
    c.text((940, 880), "по 150 ₽ за ГБ", 38, RED, "Manrope", "ExtraBold", t, 1.6, anchor="ra")
    k = 2250 * ease((t - 2.0) / 1.0)
    c.text((540, 1030), f"+{k:,.0f} ₽".replace(",", " "), 120, RED, "Unbounded", "Black", t, 2.0, anchor="mm",
           glow=12)
    c.text((540, 1140), "за 30 ГБ — например", 34, MUTED, "Manrope", "ExtraBold", t, 2.3, anchor="mm")
    source(c, t, "по данным Forbes; пример — расчёт Nexus")


def who(c: Canvas, t: float) -> None:
    c.header("03 / КОГО ЗАДЕНЕТ", t)
    c.title("КАЖДЫЙ", "СЕДЬМОЙ", t)
    for i in range(7):
        x = 150 + i * 130
        red = i == 6 and t >= 1.4
        c.person((x, 620), t, 0.3 + i * 0.1, color=RED if red else CYAN, r=32)
    c.card((90, 760, 990, 920), t, 1.6, outline=RED)
    c.text((140, 795), "13,8%", 64, RED, "Unbounded", "Black", t, 1.7)
    c.text((470, 800), "тратят больше", 34, WHITE, "Manrope", "ExtraBold", t, 1.8)
    c.text((470, 845), "50 ГБ в месяц", 34, WHITE, "Manrope", "ExtraBold", t, 1.8)
    c.card((90, 950, 990, 1110), t, 2.3, outline=CYAN)
    c.text((140, 985), "24 ГБ", 64, CYAN, "Unbounded", "Black", t, 2.4)
    c.text((470, 990), "тратит средний", 34, WHITE, "Manrope", "ExtraBold", t, 2.5)
    c.text((470, 1035), "абонент", 34, WHITE, "Manrope", "ExtraBold", t, 2.5)
    source(c, t, "мобильный трафик, 2025 · оценки экспертов, Коммерсантъ")


def when(c: Canvas, t: float) -> None:
    c.header("04 / КОГДА", t)
    c.title("ПОКА ТОЛЬКО", "ОБСУЖДЕНИЕ", t)
    rows = (("Минцифры", "обсуждает с операторами", YELLOW, None),
            ("операторы", "технического решения нет", RED, False),
            ("сроки", "могут сдвинуться", CYAN, None))
    for i, (who_, what, col, ok) in enumerate(rows):
        y = 500 + i * 200
        c.card((90, y, 990, y + 165), t, 0.3 + i * 0.4, outline=col)
        c.text((140, y + 35), who_, 48, WHITE, "Unbounded", "Black", t, 0.35 + i * 0.4)
        c.text((140, y + 105), what, 34, MUTED, t=t, t0=0.45 + i * 0.4)
        if ok is False:
            c.mark((920, y + 82), False, t, 0.7 + i * 0.4, r=40)
        else:
            c.pill((880, y + 82), "?", col, t, 0.7 + i * 0.4, size=40)
    source(c, t, "Коммерсантъ, 05.10 · Минцифры не ответили")


def _nexus(c: Canvas, t: float) -> None:
    c.header("05 / А ЧТО NEXUS", t)
    c.title("NEXUS", "ПОДСТРОИТСЯ", t)
    items = ("работает при белых списках", "несколько путей, автовыбор", "под новые правила — без переплат")
    for i, it in enumerate(items):
        y = 500 + i * 160
        c.card((90, y, 990, y + 125), t, 0.3 + i * 0.35, outline=GREEN, fill=CARD)
        c.mark((170, y + 62), True, t, 0.5 + i * 0.35, r=40)
        c.text((240, y + 40), it, 40, WHITE, "Manrope", "ExtraBold", t, 0.45 + i * 0.35)


def outro_youtube(c: Canvas, t: float) -> None:
    _nexus(c, t)
    c.pill((540, 1050), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 1.8, size=40)
    c.text((540, 1150), "3 дня бесплатно · подпишись на новости", 34, MUTED, "Manrope", "ExtraBold", t, 2.1,
           anchor="mm")


def outro_instagram(c: Canvas, t: float) -> None:
    _nexus(c, t)
    c.pill((540, 1050), "напиши VPN в комментах", YELLOW, t, 1.8, size=44)
    c.text((540, 1150), "пришлю ссылку и 3 дня бесплатно", 34, MUTED, "Manrope", "ExtraBold", t, 2.1,
           anchor="mm")


SCENES = {
    "n2_01": (news, 8.0),
    "n2_02": (price, 8.0),
    "n2_03": (who, 7.0),
    "n2_04": (when, 7.0),
    "n2_05yt": (outro_youtube, 9.0),
    "n2_05ig": (outro_instagram, 9.0),
}
