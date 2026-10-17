"""g1 · «Один твой код — и на тебя оформят кредит» (охват, ~14 с, хук с кадра 0, конец закольцован).

Факты: самозапрет на кредиты — с 1.03.2025, >22,1 млн установок (ЦБ); самозапрет на сим-карты — с 1.09.2025,
через Госуслуги или МФЦ.
"""

from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog


def sms(c: Canvas, center, t, t0) -> None:
    """Incoming SMS with a confirmation code."""
    p = prog(t, t0, 0.3)
    if p <= 0:
        return
    cx, cy = center
    lay, d = c.layer()
    y = cy + (1 - p) * 60
    d.rounded_rectangle((cx - 380, y - 110, cx + 380, y + 110), radius=40, fill=(40, 70, 140))
    d.text((cx - 330, y - 70), "СМС · Госуслуги", font=font("Manrope", 32, "Bold"), fill=MUTED)
    d.text((cx - 330, y - 20), "Код: 4 7 2 9", font=font("Unbounded", 64, "Black"), fill=WHITE)
    c.put(lay, p, glow=8)


def toggle(c: Canvas, y, label, t, t0) -> None:
    on = t >= t0 + 0.5
    c.card((90, y, 990, y + 140), t, t0, outline=GREEN if on else (60, 85, 150), fill=CARD, width=5 if on else 3)
    c.text((140, y + 48), label, 40, WHITE, "Manrope", "ExtraBold", t, t0 + 0.05)
    p = prog(t, t0 + 0.5, 0.25)
    lay, d = c.layer()
    x0, y0 = 800, y + 40
    d.rounded_rectangle((x0, y0, x0 + 140, y0 + 60), radius=30, fill=GREEN if on else (60, 70, 100))
    kx = x0 + 30 + 80 * p
    d.ellipse((kx - 24, y0 + 6, kx + 24, y0 + 54), fill=WHITE)
    c.put(lay, prog(t, t0, 0.3))


def hook(c: Canvas, t: float) -> None:
    c.header("ЗАЩИТА ОТ МОШЕННИКОВ", t)
    c.title("ОДИН КОД —", "КРЕДИТ НА ТЕБЯ", t)
    sms(c, (540, 640), t, 0.2)
    c.arrow((540, 770), (540, 900), t, 0.9, 0.4, color=RED, width=8)
    c.card((140, 920, 940, 1120), t, 1.2, outline=RED, width=6)
    c.text((540, 980), "заявка на кредит", 40, WHITE, "Manrope", "ExtraBold", t, 1.25, anchor="mm")
    c.text((540, 1055), "ОДОБРЕНО", 64, RED, "Unbounded", "Black", t, 1.6, anchor="mm", glow=10)


def bomb(c: Canvas, t: float) -> None:
    c.header("ЦИФРА", t)
    c.title("УЖЕ ЗАКРЫЛИ", "ЭТУ ДЫРУ", t)
    v = 22_100_000 * ease(t / 1.2)
    c.text((540, 680), f"{v:,.0f}".replace(",", " "), 118, GREEN, "Unbounded", "Black", t, 0.0, anchor="mm",
           glow=12)
    c.text((540, 800), "самозапретов на кредиты", 44, WHITE, "Manrope", "ExtraBold", t, 0.2, anchor="mm")
    c.text((540, 1000), "А ТЫ?", 150, YELLOW, "Unbounded", "Black", t, 1.4, anchor="mm", glow=14)
    c.text((540, 1250), "Банк России · с 1 марта 2025", 30, MUTED, "Manrope", "Bold", t, 0.4, anchor="mm")


def how(c: Canvas, t: float) -> None:
    c.header("2 КНОПКИ · БЕСПЛАТНО", t)
    c.title("ГОСУСЛУГИ →", "САМОЗАПРЕТ", t)
    toggle(c, 520, "на кредиты и займы", t, 0.1)
    toggle(c, 700, "на новые сим-карты", t, 0.7)
    c.pill((540, 930), "включается за пару минут", YELLOW, t, 1.6, size=40)
    c.text((540, 1250), "сим-карты — с 1 сентября 2025, можно и через МФЦ", 30, MUTED, "Manrope", "Bold", t, 0.4,
           anchor="mm")


def _loop(c: Canvas, t: float) -> None:
    c.header("СДЕЛАЙ СЕГОДНЯ", t)
    c.title("СДЕЛАЙ СЕГОДНЯ —", "ИНАЧЕ ОДИН КОД…", t)
    # the SMS comes back: the end flows into the first frame
    sms(c, (540, 700), t, 1.0)


def outro_instagram(c: Canvas, t: float) -> None:
    _loop(c, t)
    c.pill((540, 1000), "сохрани и скинь маме", YELLOW, t, 0.3, size=44)


def outro_youtube(c: Canvas, t: float) -> None:
    _loop(c, t)
    c.pill((540, 1000), "сохрани и скинь маме", YELLOW, t, 0.3, size=44)
    c.text((540, 1110), "подпишись — разбираем цифровые засады", 32, MUTED, "Manrope", "ExtraBold", t, 0.5,
           anchor="mm")


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("КАК НА ТЕБЯ", "ОФОРМЯТ КРЕДИТ", "ПО ОДНОМУ КОДУ?")

SCENES = {
    "g1_01hot": (hook, 4.0, 1.0),
    "g1_02": (bomb, 4.5, 0.35),
    "g1_03": (how, 5.0, 0.3),
    "g1_04ig": (outro_instagram, 4.0, 0.3),
    "g1_04yt": (outro_youtube, 4.0, 0.3),
}
