"""s3 · «Почему у МТС работает, а у Билайна нет» — motion version."""

from motion import CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, font, prog


def hook(c: Canvas, t: float) -> None:
    c.header("01 / ЗАГАДКА", t)
    c.title("ОДИН VPN —", "РАЗНЫЙ ИТОГ", t)
    c.phone((70, 470, 520, 1180), "МТС", t, 0.25, "ok", 1.5)
    c.phone((560, 470, 1010, 1180), "Билайн", t, 0.45, "fail", 2.2)


def filters(c: Canvas, t: float) -> None:
    c.header("02 / КТО РЕЖЕТ", t)
    c.title("У КАЖДОГО", "ОПЕРАТОРА — ТСПУ", t, size=70)
    # phone -> TSPU box -> internet
    c.card((60, 620, 300, 860), t, 0.3, outline=CYAN)
    c.text((180, 740), "ТЫ", 52, WHITE, "Unbounded", "Black", t, 0.35, anchor="mm")
    c.card((360, 590, 720, 890), t, 0.6, outline=YELLOW, width=6)
    c.text((540, 710), "ТСПУ", 56, YELLOW, "Unbounded", "Black", t, 0.65, anchor="mm")
    c.text((540, 800), "фильтр оператора", 32, MUTED, t=t, t0=0.7, anchor="mm")
    c.card((780, 620, 1020, 860), t, 0.9, outline=CYAN)
    c.text((900, 740), "СЕТЬ", 46, WHITE, "Unbounded", "Black", t, 0.95, anchor="mm")
    c.arrow((305, 740), (352, 740), t, 0.9, 0.3)
    c.arrow((725, 740), (772, 740), t, 1.2, 0.3)
    # packets: green pass, red stop at the box
    for i in range(6):
        t0 = 1.6 + i * 0.35
        p = (t - t0) / 1.2
        if p <= 0:
            continue
        bad = i % 2 == 1
        x = 230 + min(p, 1) * (bad and 230 or 650)
        lay, d = c.layer()
        col = RED if bad else GREEN
        y = 960 + (i % 3) * 60
        d.rounded_rectangle((x - 34, y - 20, x + 34, y + 20), radius=10, fill=col)
        c.put(lay, 1.0 if not (bad and p > 1.4) else max(0.0, 2.4 - p), glow=6)
    c.text((540, 1170), "одни пакеты проходят, другие — нет", 34, MUTED, t=t, t0=2.0, anchor="mm")


def rules(c: Canvas, t: float) -> None:
    c.header("03 / ПРАВИЛА", t)
    c.title("ОБНОВЛЯЮТ", "НЕ ВЕЗДЕ СРАЗУ", t, size=72)
    rows = (("МТС", "старые правила", GREEN, True), ("Билайн", "новое правило", RED, False))
    for i, (op, rule, col, ok) in enumerate(rows):
        y = 560 + i * 260
        c.card((70, y, 1010, y + 210), t, 0.4 + i * 0.5, outline=col)
        c.text((120, y + 45), op, 54, WHITE, "Unbounded", "Black", t, 0.5 + i * 0.5)
        c.text((120, y + 130), rule, 36, MUTED, t=t, t0=0.6 + i * 0.5)
        c.mark((930, y + 105), ok, t, 1.2 + i * 0.5, r=50)
    c.text((540, 1150), "сегодня у одного — через неделю у другого", 56, YELLOW, "Caveat", "Bold", t, 2.2,
           anchor="mm")


def region(c: Canvas, t: float) -> None:
    c.header("04 / РЕГИОН", t)
    c.title("И ГОРОД", "ТОЖЕ РЕШАЕТ", t)
    cities = (("Москва", True), ("Казань", False), ("Екатеринбург", True), ("Новосибирск", False))
    for i, (city, ok) in enumerate(cities):
        y = 560 + i * 150
        c.text((90, y), city, 52, WHITE, "Manrope", "ExtraBold", t, 0.4 + i * 0.35)
        c.pill((880, y + 32), "работает" if ok else "режут", GREEN if ok else RED, t, 0.7 + i * 0.35, size=34)
    c.text((540, 1170), "проверять надо в разных сетях", 34, MUTED, t=t, t0=2.0, anchor="mm")


def fix(c: Canvas, t: float) -> None:
    c.header("05 / ЧТО ДЕЛАТЬ", t)
    c.title("НЕСКОЛЬКО ПУТЕЙ", "И АВТОВЫБОР", t, size=70)
    lanes = ("путь A", "путь B", "путь C")
    for i, name in enumerate(lanes):
        y = 590 + i * 170
        dead = i == 0 and t > 1.4
        col = RED if dead else (GREEN if i == 1 and t > 1.9 else CYAN)
        c.card((70, y, 1010, y + 130), t, 0.3 + i * 0.2, outline=col)
        c.text((120, y + 40), name, 44, WHITE, "Unbounded", "Black", t, 0.4 + i * 0.2)
        if dead:
            c.pill((880, y + 65), "заблокирован", RED, t, 1.4, size=30)
        if i == 1:
            c.pill((880, y + 65), "ты здесь", GREEN, t, 1.9, size=30)
    c.arrow((690, 690), (690, 790), t, 1.6, 0.4, color=YELLOW)
    c.pill((540, 1170), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 2.4, size=40)


SCENES = {
    "s3_01": (hook, 9.0),
    "s3_02": (filters, 9.0),
    "s3_03": (rules, 9.0),
    "s3_04": (region, 9.0),
    "s3_05": (fix, 9.0),
}
