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


def means(c: Canvas, t: float) -> None:
    c.header("03 / ЧТО ЭТО ЗНАЧИТ", t)
    c.title("БЛОКИРОВАТЬ", "БУДУТ БЫСТРЕЕ", t)
    c.pill((540, 520), "прогноз Nexus", CYAN, t, 0.2, size=34)
    for i in range(3):
        y = 610 + i * 175
        dead = t >= 1.3 + i * 0.5
        c.card((90, y, 990, y + 140), t, 0.4 + i * 0.15, outline=RED if dead else (60, 85, 150),
               width=5 if dead else 3)
        c.text((140, y + 30), f"VPN {'ABC'[i]}", 46, WHITE, "Unbounded", "Black", t, 0.45 + i * 0.15)
        c.text((140, y + 92), "один сервер", 30, MUTED, t=t, t0=0.5 + i * 0.15)
        if dead:
            c.pill((830, y + 70), "заблокирован", RED, t, 1.3 + i * 0.5, size=30, text_color=WHITE)
        else:
            c.pill((830, y + 70), "работает", GREEN, t, 0.6 + i * 0.15, size=30)
    c.text((540, 1200), "слабые VPN будут умирать чаще", 46, YELLOW, "Manrope", "ExtraBold", t, 2.9,
           anchor="mm")


def todo(c: Canvas, t: float) -> None:
    c.header("04 / ЧТО ДЕЛАТЬ", t)
    c.title("ВЫБИРАЙ VPN", "С ЗАПАСОМ", t)
    items = ("несколько серверов", "сам переключает на рабочий", "есть пробный период")
    for i, it in enumerate(items):
        y = 520 + i * 165
        c.card((90, y, 990, y + 130), t, 0.3 + i * 0.35, outline=GREEN, fill=CARD)
        c.mark((170, y + 65), True, t, 0.5 + i * 0.35, r=40)
        c.text((240, y + 42), it, 44, WHITE, "Manrope", "ExtraBold", t, 0.45 + i * 0.35)
    c.pill((540, 1100), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 1.9, size=40)
    c.text((540, 1200), "3 дня бесплатно", 40, MUTED, "Manrope", "ExtraBold", t, 2.1, anchor="mm")


SCENES = {
    "n1_01": (money, 7.0),
    "n1_02": (where, 7.0),
    "n1_03": (means, 7.0),
    "n1_04": (todo, 7.0),
}
