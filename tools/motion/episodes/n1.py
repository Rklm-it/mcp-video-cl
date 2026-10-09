"""n1 · новость 06.10.2026: на блокировки за 2027–2029 заложили почти 60 млрд ₽ (Forbes, проект бюджета)."""

from motion import CARD, CYAN, GREEN, MUTED, RED, WHITE, YELLOW, Canvas, ease, font, prog

SOURCE = "по данным Forbes · проект бюджета 2027–2029"


def source(c: Canvas, t: float, text: str = SOURCE) -> None:
    c.text((540, 1270), text, 30, MUTED, "Manrope", "Bold", t, 0.6, anchor="mm")


def bar(c: Canvas, box, frac: float, color, t: float, t0: float, dur: float = 0.9) -> None:
    x0, y0, x1, y1 = box
    p = prog(t, t0, dur)
    if p <= 0:
        return
    lay, d = c.layer()
    d.rounded_rectangle(box, radius=(y1 - y0) // 2, fill=(30, 45, 90))
    xe = x0 + max(y1 - y0, (x1 - x0) * frac * p)
    d.rounded_rectangle((x0, y0, xe, y1), radius=(y1 - y0) // 2, fill=color)
    c.put(lay, min(1.0, p * 3), glow=8)


def money(c: Canvas, t: float) -> None:
    c.header("НОВОСТЬ · 06.10", t)
    c.title("БЛОКИРОВКИ", "ПОДОРОЖАЛИ ВДВОЕ", t)
    c.card((90, 470, 990, 1210), t, 0.2, outline=RED, fill=(14, 24, 56))
    c.text((140, 510), "расходы на блокировки за 3 года", 34, MUTED, "Manrope", "ExtraBold", t, 0.3)
    v = 60 * ease((t - 0.5) / 1.4)
    c.text((540, 680), f"{v:.0f} МЛРД ₽", 100, RED, "Unbounded", "Black", t, 0.4, anchor="mm", glow=12)
    rows = (("план 2 года назад", 32, MUTED, 1.4), ("новый план", 60, RED, 1.9))
    for i, (name, val, col, t0) in enumerate(rows):
        y = 840 + i * 170
        c.text((140, y), name, 36, WHITE, "Manrope", "ExtraBold", t, t0)
        c.text((940, y), f"{val} млрд", 36, col if i else WHITE, "Unbounded", "Black", t, t0, anchor="ra")
        bar(c, (140, y + 60, 940, y + 110), val / 60, col if i else (110, 125, 170), t, t0 + 0.1)
    c.pill((450, 1030), "×2", YELLOW, t, 2.8, size=34)
    source(c, t)


def where(c: Canvas, t: float) -> None:
    c.header("02 / НА ЧТО", t)
    c.title("ФИЛЬТРЫ ТСПУ", "У КАЖДОГО ОПЕРАТОРА", t)
    # operators -> TSPU box
    ops = ("МТС", "Билайн", "Мегафон", "Т2")
    for i, op in enumerate(ops):
        x = 160 + i * 253
        c.card((x - 105, 480, x + 105, 580), t, 0.3 + i * 0.12, outline=CYAN, radius=20)
        c.text((x, 530), op, 34, WHITE, "Manrope", "ExtraBold", t, 0.35 + i * 0.12, anchor="mm")
        c.arrow((x, 585), (540 + (x - 540) * 0.35, 660), t, 0.8 + i * 0.08, 0.35, color=CYAN, width=4)
    c.card((300, 665, 780, 775), t, 0.9, outline=YELLOW, width=6)
    c.text((540, 720), "ТСПУ", 60, YELLOW, "Unbounded", "Black", t, 0.95, anchor="mm")
    years = (("2027", 19.87), ("2028", 19.844), ("2029", 19.87))
    for i, (yr, val) in enumerate(years):
        y = 840 + i * 120
        c.text((140, y + 8), yr, 40, WHITE, "Unbounded", "Black", t, 1.3 + i * 0.3)
        bar(c, (320, y + 10, 760, y + 60), val / 20, YELLOW, t, 1.35 + i * 0.3, 0.6)
        c.text((940, y + 12), f"{val:.2f}".replace(".", ","), 36, YELLOW, "Unbounded", "Black", t,
               1.5 + i * 0.3, anchor="ra")
    source(c, t, "млрд ₽ в год · ГРЧЦ (Роскомнадзор), проект бюджета")


def capacity(c: Canvas, t: float) -> None:
    c.header("03 / ЦЕЛЬ", t)
    c.title("ФИЛЬТРЫ", "РАЗГОНЯТ", t)
    c.card((90, 470, 990, 1210), t, 0.2, outline=CYAN, fill=(14, 24, 56))
    c.text((140, 510), "пропускная способность ТСПУ к 2030", 34, MUTED, "Manrope", "ExtraBold", t, 0.3)
    v = 953.9 * ease((t - 0.5) / 1.6)
    c.text((540, 690), f"{v:,.0f}".replace(",", " "), 150, CYAN, "Unbounded", "Black", t, 0.4, anchor="mm",
           glow=12)
    c.text((540, 800), "терабит в секунду", 40, WHITE, "Manrope", "ExtraBold", t, 0.5, anchor="mm")
    rows = (("план 2024 года", 725.6, (110, 125, 170), 1.4), ("план Минцифры 2025–2030", 953.9, CYAN, 1.9))
    for i, (name, val, col, t0) in enumerate(rows):
        y = 900 + i * 140
        c.text((140, y), name, 34, WHITE, "Manrope", "ExtraBold", t, t0)
        c.text((940, y), f"{val:g}".replace(".", ","), 34, col, "Unbounded", "Black", t, t0, anchor="ra")
        bar(c, (140, y + 55, 940, y + 100), val / 953.9, col, t, t0 + 0.1)
    source(c, t, "Тбит/с · по данным Forbes, план Минцифры")


def chips(c: Canvas, t: float) -> None:
    c.header("04 / ПОЧЕМУ ДОРОЖЕ", t)
    c.title("ПАМЯТЬ", "ПОДОРОЖАЛА В РАЗЫ", t)
    # memory chip
    p = c.card((330, 480, 750, 760), t, 0.2, outline=YELLOW, fill=CARD, radius=18, width=6)
    if p > 0:
        lay, d = c.layer()
        for k in range(7):
            x = 365 + k * 55
            d.rectangle((x, 455, x + 22, 480), fill=YELLOW)
            d.rectangle((x, 760, x + 22, 785), fill=YELLOW)
        c.put(lay, p)
    c.text((540, 590), "RAM", 70, YELLOW, "Unbounded", "Black", t, 0.3, anchor="mm")
    c.text((540, 680), "для DPI-фильтров", 30, MUTED, t=t, t0=0.4, anchor="mm")
    k = 1 + 5 * ease((t - 0.8) / 1.2)
    c.text((540, 900), f"×{k:.0f}" if t < 2.0 else "×4–6", 130, RED, "Unbounded", "Black", t, 0.8,
           anchor="mm", glow=12)
    c.text((540, 1010), "рост цены за год — из-за бума ИИ", 38, WHITE, "Manrope", "ExtraBold", t, 1.6,
           anchor="mm")
    c.pill((540, 1120), "64 ГБ памяти на каждые 10 Гбит/с", YELLOW, t, 2.3, size=34)
    source(c, t, "оценки экспертов ComNews, RUVDS · Forbes")


def next_(c: Canvas, t: float) -> None:
    c.header("05 / ЧТО ДАЛЬШЕ", t)
    c.title("ФИЛЬТРЫ ДОЙДУТ", "ДО МЕЛКИХ ОПЕРАТОРОВ", t)
    c.pill((540, 520), "прогноз экспертов", CYAN, t, 0.2, size=34)
    ops = (("крупные операторы", True), ("региональные", False), ("новые узлы связи", False))
    for i, (name, has) in enumerate(ops):
        y = 610 + i * 165
        done = has or t >= 1.6 + i * 0.5
        c.card((90, y, 990, y + 130), t, 0.4 + i * 0.2, outline=YELLOW if done else (60, 85, 150),
               width=5 if done else 3)
        c.text((140, y + 42), name, 44, WHITE, "Manrope", "ExtraBold", t, 0.45 + i * 0.2)
        if done:
            c.pill((830, y + 65), "ТСПУ", YELLOW, t, 0.6 if has else 1.6 + i * 0.5, size=32)
        else:
            c.pill((830, y + 65), "пока нет", (60, 85, 150), t, 0.6, size=32, text_color=WHITE)
    c.pill((540, 1150), "подпишись — новости блокировок", WHITE, t, 2.8, size=36)
    c.text((540, 1250), "VPN при белых списках: t.me/nexus_subs_bot", 28, MUTED, "Manrope", "Bold", t, 3.0,
           anchor="mm")


SCENES = {
    "n1_01": (money, 7.0),
    "n1_02": (where, 7.0),
    "n1_03": (capacity, 7.0),
    "n1_04": (chips, 8.0),
    "n1_05": (next_, 8.0),
}
