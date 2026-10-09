"""s5 · «Бесплатный VPN: кто на тебе зарабатывает» — факты с источниками, две концовки (YouTube / Instagram)."""

from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog

ORANGE = (255, 150, 60)


def source(c: Canvas, t: float, text: str) -> None:
    c.text((540, 1270), text, 30, MUTED, "Manrope", "Bold", t, 0.6, anchor="mm")


def hook(c: Canvas, t: float) -> None:
    c.header("01 / БЕСПЛАТНО?", t)
    c.title("БЕСПЛАТНЫЙ VPN?", "ТОВАР — ЭТО ТЫ", t)
    c.card((90, 480, 990, 760), t, 0.2, outline=(70, 95, 160), fill=(14, 24, 56))
    c.card((130, 520, 330, 720), t, 0.3, outline=CYAN, fill=CARD, radius=40)
    c.text((230, 620), "VPN", 52, CYAN, "Unbounded", "Black", t, 0.35, anchor="mm")
    c.text((370, 545), "Супер VPN", 44, WHITE, "Manrope", "ExtraBold", t, 0.4)
    c.text((370, 610), "4,8 · 10 млн загрузок", 30, MUTED, t=t, t0=0.45)
    paid = t >= 1.6
    c.pill((520, 690), "твои данные" if paid else "БЕСПЛАТНО", RED if paid else GREEN, t, 1.6 if paid else 0.5,
           size=34, text_color=WHITE if paid else NAVY)
    items = ("контакты", "где ты бываешь", "какие сайты открываешь", "чем пользуешься")
    for i, it in enumerate(items):
        t0 = 1.9 + i * 0.3
        p = ease((t - t0) / 0.6)
        if p <= 0:
            continue
        y = 840 + i * 95
        c.arrow((140, y + 30), (140 + 120 * p, y + 30), t, t0, 0.3, color=RED, width=5)
        c.text((300, y + 8), it, 40, WHITE, "Manrope", "ExtraBold", t, t0)


def study(c: Canvas, t: float) -> None:
    c.header("02 / ПРОВЕРКА", t)
    c.title("283 VPN", "ПОД МИКРОСКОПОМ", t)
    cols, size, gap = 23, 34, 6
    x0, y0 = (1080 - (cols * size + (cols - 1) * gap)) // 2, 480
    lay, d = c.layer()
    for i in range(283):
        r, k = divmod(i, cols)
        x, y = x0 + k * (size + gap), y0 + r * (size + gap)
        appear = prog(t, 0.2 + i * 0.002, 0.3)
        if appear <= 0:
            continue
        frac = i / 283
        col = (60, 85, 150)
        if t >= 1.4 and frac < 0.75 * ease((t - 1.4) / 0.8):
            col = ORANGE
        if t >= 2.4 and (i * 37 % 283) / 283 < 0.38 * ease((t - 2.4) / 0.8):
            col = RED
        d.rounded_rectangle((x, y, x + size, y + size), radius=8, fill=col)
    c.put(lay)
    rows = (("75%", "со сторонними трекерами", ORANGE, 1.6), ("38%", "с вредоносным кодом", RED, 2.6),
            ("18%", "вообще не шифруют трафик", WHITE, 3.4))
    # legend under the grid
    gy = y0 + 13 * (size + gap) + 30
    for i, (num, txt, col, t0) in enumerate(rows):
        y = gy + i * 62
        c.text((140, y), num, 50, col, "Unbounded", "Black", t, t0)
        c.text((340, y + 10), txt, 38, WHITE, "Manrope", "ExtraBold", t, t0 + 0.1)
    source(c, t, "исследование CSIRO, UNSW и Беркли, 2016 · приложения Android")


def bandwidth(c: Canvas, t: float) -> None:
    c.header("03 / ТВОЙ ИНТЕРНЕТ", t)
    c.title("ТВОЙ ИНТЕРНЕТ", "ПРОДАЛИ", t)
    c.text((540, 500), "пользователи VPN", 32, MUTED, "Manrope", "ExtraBold", t, 0.3, anchor="mm")
    c.card((70, 700, 290, 820), t, 0.3, outline=ORANGE)
    c.text((180, 760), "чужие", 40, ORANGE, "Unbounded", "Black", t, 0.35, anchor="mm")
    users = [(540, 600 + i * 130) for i in range(4)]
    for i, (x, y) in enumerate(users):
        c.arrow((295, 760), (x - 50, y), t, 1.0 + i * 0.15, 0.35, color=ORANGE, width=4)
        c.person((x, y + 20), t, 0.5 + i * 0.12, color=CYAN, r=28)
    hit = t >= 2.6
    c.card((790, 700, 1010, 820), t, 1.8, outline=RED if hit else (70, 95, 160), width=5 if hit else 3)
    c.text((900, 760), "сайт", 40, RED if hit else WHITE, "Unbounded", "Black", t, 1.85, anchor="mm")
    for i, (x, y) in enumerate(users):
        c.arrow((x + 50, y), (785, 760), t, 2.1 + i * 0.1, 0.35, color=RED, width=4)
    c.pill((540, 1150), "через их устройства атаковали сайт", RED, t, 2.6, size=32, text_color=WHITE)
    source(c, t, "популярный бесплатный VPN, случай 2015 года")


def leak(c: Canvas, t: float) -> None:
    c.header("04 / «БЕЗ ЛОГОВ»", t)
    c.title("«НЕ ХРАНИМ ЛОГИ»", "СЛИЛИ ТЕРАБАЙТ", t)
    c.pill((540, 530), "мы не храним логи", GREEN, t, 0.2, size=40)
    if t >= 1.0:
        p = ease((t - 1.0) / 0.3)
        lay, d = c.layer()
        d.line((300, 530, 300 + 480 * p, 530), fill=RED, width=10)
        c.put(lay, 1.0, glow=6)
    v = 1.2 * ease((t - 1.2) / 1.2)
    c.text((540, 720), f"{v:.1f} ТБ".replace(".", ","), 150, RED, "Unbounded", "Black", t, 1.2, anchor="mm",
           glow=12)
    c.text((540, 830), "данных пользователей в открытом доступе", 34, WHITE, "Manrope", "ExtraBold", t, 1.4,
           anchor="mm")
    items = ("пароли открытым текстом", "IP-адреса устройств", "время подключений")
    for i, it in enumerate(items):
        y = 920 + i * 95
        c.card((140, y, 940, y + 75), t, 2.0 + i * 0.3, outline=RED, fill=CARD, radius=20)
        c.text((180, y + 18), it, 36, WHITE, "Manrope", "ExtraBold", t, 2.05 + i * 0.3)
    source(c, t, "7 бесплатных VPN, утечка 2020 года")


def owner(c: Canvas, t: float) -> None:
    c.header("05 / ВЛАДЕЛЕЦ", t)
    c.title("КАЖДЫЙ ПЯТЫЙ", "ТАЙНО КИТАЙСКИЙ", t)
    c.text((540, 500), "топ-100 бесплатных VPN в App Store (США)", 32, MUTED, "Manrope", "ExtraBold", t, 0.2,
           anchor="mm")
    size, gap = 66, 14
    x0 = (1080 - (10 * size + 9 * gap)) // 2
    lay, d = c.layer()
    for i in range(100):
        r, k = divmod(i, 10)
        x, y = x0 + k * (size + gap), 550 + r * 44
        if prog(t, 0.3 + i * 0.006, 0.3) <= 0:
            continue
        red = t >= 1.5 and (i * 7 % 100) < 20 * ease((t - 1.5) / 0.8)
        d.rounded_rectangle((x, y, x + size, y + 33), radius=10, fill=RED if red else (60, 85, 150))
    c.put(lay)
    c.card((90, 1010, 990, 1210), t, 2.4, outline=RED)
    c.text((140, 1040), "владелец скрыт", 40, WHITE, "Manrope", "ExtraBold", t, 2.5)
    c.text((140, 1110), "часть связана с компанией из военного", 32, MUTED, t=t, t0=2.9)
    c.text((140, 1150), "списка Минобороны США", 32, MUTED, t=t, t0=2.9)
    c.pill((860, 1065), "≈ 20 из 100", RED, t, 2.6, size=30, text_color=WHITE)
    source(c, t, "Tech Transparency Project, апрель 2025")


def _check(c: Canvas, t: float) -> None:
    c.header("06 / КАК ПРОВЕРИТЬ", t)
    c.title("КАК ПРОВЕРИТЬ", "ЛЮБОЙ VPN", t)
    items = ("кто владелец и где компания", "что в политике данных", "за что ты платишь")
    for i, it in enumerate(items):
        y = 500 + i * 160
        c.card((90, y, 990, y + 125), t, 0.3 + i * 0.3, outline=GREEN, fill=CARD)
        c.mark((170, y + 62), True, t, 0.5 + i * 0.3, r=40)
        c.text((240, y + 40), it, 40, WHITE, "Manrope", "ExtraBold", t, 0.45 + i * 0.3)


def outro_youtube(c: Canvas, t: float) -> None:
    _check(c, t)
    c.text((540, 1035), "Nexus живёт на подписке, а не на данных", 38, YELLOW, "Manrope", "ExtraBold", t, 1.6,
           anchor="mm")
    c.pill((540, 1130), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 2.0, size=40)
    c.text((540, 1225), "3 дня бесплатно", 36, MUTED, "Manrope", "ExtraBold", t, 2.2, anchor="mm")


def outro_instagram(c: Canvas, t: float) -> None:
    _check(c, t)
    c.pill((540, 1060), "сохрани и отправь другу", YELLOW, t, 1.6, size=40)
    c.text((540, 1170), "подпишись — разбираем VPN без рекламы", 34, MUTED, "Manrope", "ExtraBold", t, 2.0,
           anchor="mm")


SCENES = {
    "s5_01": (hook, 7.0),
    "s5_02": (study, 8.0),
    "s5_03": (bandwidth, 8.0),
    "s5_04": (leak, 8.0),
    "s5_05": (owner, 8.0),
    "s5_06yt": (outro_youtube, 8.0),
    "s5_06ig": (outro_instagram, 8.0),
}
