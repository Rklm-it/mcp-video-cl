"""s4 · «Почему дешёвый VPN умирает через месяц» — для зрителя и для владельца VPN."""

import math

from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog


def hook(c: Canvas, t: float) -> None:
    c.header("01 / БОЛЬ", t)
    c.title("КУПИЛ VPN —", "ЧЕРЕЗ МЕСЯЦ УМЕР", t)
    dead = t >= 1.6
    c.card((90, 480, 990, 1000), t, 0.25, outline=RED if dead else CYAN, width=5)
    c.text((140, 520), "моя подписка", 34, MUTED, t=t, t0=0.3)
    day = 1 + int(29 * ease((t - 0.4) / 1.1))
    c.text((540, 700), f"ДЕНЬ {day}", 120, RED if dead else WHITE, "Unbounded", "Black", t, 0.35, anchor="mm")
    if dead:
        c.pill((540, 890), "не подключается", RED, t, 1.6, size=44)
    else:
        c.pill((540, 890), "подключено", GREEN, t, 0.5, size=44)
    c.mark((900, 560), False, t, 1.6, r=46)
    c.text((540, 1120), "−100 ₽", 130, RED, "Unbounded", "Black", t, 2.0, anchor="mm", glow=14)


def one_server(c: Canvas, t: float) -> None:
    c.header("02 / ПОЧЕМУ", t)
    c.title("ОДИН СЕРВЕР", "НА ВСЕХ", t)
    ban = 2.6
    banned = t >= ban
    xs = [130 + i * 117 for i in range(8)]
    sx, sy = 540, 930
    for i, x in enumerate(xs):
        gone = t >= ban + 0.3 + i * 0.06
        c.arrow((x, 620), (sx + (x - sx) * 0.25, sy - 110), t, 0.9 + i * 0.05, 0.4,
                color=RED if gone else CYAN, width=4)
        c.person((x, 560), t, 0.3 + i * 0.07, color=RED if gone else CYAN)
    c.card((300, sy - 110, 780, sy + 110), t, 0.7, outline=RED if banned else YELLOW, width=6)
    c.text((sx, sy - 25), "СЕРВЕР", 60, RED if banned else YELLOW, "Unbounded", "Black", t, 0.75, anchor="mm")
    c.text((sx, sy + 50), "один IP-адрес", 32, MUTED, t=t, t0=0.8, anchor="mm")
    if banned:
        c.pill((sx, sy + 175), "адрес заблокирован", RED, t, ban, size=40)
    c.text((540, 1190), "интернет пропал у всех разом", 46, YELLOW, "Manrope", "ExtraBold", t, ban + 0.6,
           anchor="mm")


def owner(c: Canvas, t: float) -> None:
    c.header("03 / ИЗНУТРИ", t)
    c.title("ВЛАДЕЛЕЦ УЗНАЁТ", "ПОСЛЕДНИМ", t)
    c.card((90, 470, 990, 960), t, 0.2, outline=(70, 95, 160), fill=(14, 24, 56))
    c.text((140, 505), "Поддержка", 40, WHITE, "Manrope", "ExtraBold", t, 0.25)
    n = int(48 * ease((t - 0.4) / 2.0))
    if n:
        c.pill((900, 530), str(n), RED, t, 0.4, size=36, text_color=WHITE)
    msgs = ("не работает!", "VPN лёг?", "верните деньги", "ухожу к другим")
    for i, m in enumerate(msgs):
        c.bubble((140, 600 + i * 88), m, t, 0.5 + i * 0.35, fill=(80, 30, 55) if i >= 2 else (40, 70, 140))
    c.card((90, 1000, 990, 1230), t, 2.4, outline=YELLOW)
    c.text((140, 1035), "чинит руками ночью", 44, YELLOW, "Manrope", "ExtraBold", t, 2.5)
    for i in range(6):
        left = i >= 4 and t >= 3.6
        c.person((170 + i * 95, 1170), t, 2.6 + i * 0.06, color=RED if left else CYAN, r=20)
    if t >= 3.6:
        c.pill((800, 1062), "клиенты уходят", RED, t, 3.6, size=32, text_color=WHITE)


def whitelist(c: Canvas, t: float) -> None:
    c.header("04 / БЕЛЫЕ СПИСКИ", t)
    c.title("БЕЛЫЕ СПИСКИ —", "И VPN МОЛЧИТ", t)
    c.pill((540, 520), "мобильный интернет · LTE", CYAN, t, 0.2, size=36)
    rows = (("Госуслуги", True), ("Банк", True), ("Карты", True), ("Твой VPN", False))
    for i, (name, ok) in enumerate(rows):
        y = 610 + i * 150
        last = not ok
        c.card((90, y, 990, y + 120), t, 0.4 + i * 0.3, outline=RED if last else (60, 85, 150),
               width=6 if last else 3)
        c.text((140, y + 32), name, 48, WHITE, "Unbounded" if last else "Manrope",
               "Black" if last else "ExtraBold", t, 0.45 + i * 0.3)
        if ok:
            c.mark((920, y + 60), True, t, 0.7 + i * 0.3, r=38)
        else:
            if t < 2.0:
                c.spinner((920, y + 60), t, r=32)
            c.mark((920, y + 60), False, t, 2.0, r=42)
    c.text((540, 1250), "пускают только «своих»", 46, YELLOW, "Manrope", "ExtraBold", t, 2.3, anchor="mm")


def monitor(c: Canvas, t: float) -> None:
    c.header("05 / КАК НАДО", t)
    c.title("НОРМАЛЬНЫЙ СЕРВИС", "СЛЕДИТ САМ", t)
    c.card((90, 450, 990, 1110), t, 0.2, outline=CYAN, fill=(14, 24, 56))
    c.text((140, 485), "мониторинг · 24/7", 34, MUTED, "Manrope", "ExtraBold", t, 0.25)
    # heartbeat line running across the card
    if t > 0.4:
        lay, d = c.layer()
        pts = []
        for x in range(140, 941, 6):
            ph = (x - 140) / 800 * 4 * math.pi - t * 6
            spike = 38 * math.exp(-((math.sin(ph / 2) * 4) ** 2)) * math.sin(ph * 3)
            pts.append((x, 580 + spike))
        d.line(pts, fill=GREEN, width=4)
        c.put(lay, prog(t, 0.4), glow=5)
    ban, move = 1.4, 2.2
    servers = ("сервер 1", "сервер 2", "сервер 3")
    for i, name in enumerate(servers):
        y = 660 + i * 130
        bad = i == 1 and t >= ban
        here = (i == 1 and t < move) or (i == 2 and t >= move + 0.5)
        c.card((130, y, 950, y + 105), t, 0.4 + i * 0.2, outline=RED if bad else (60, 85, 150), fill=CARD,
               radius=22, width=5 if bad else 3)
        c.text((170, y + 30), name, 40, WHITE, "Unbounded", "Black", t, 0.45 + i * 0.2)
        if bad:
            c.pill((790, y + 52), "бан", RED, t, ban, size=32, text_color=WHITE)
        else:
            c.pill((790, y + 52), "онлайн", GREEN, t, 0.6 + i * 0.2, size=32)
        if here:
            c.person((560, y + 66), t, 0.6 if i == 1 else move + 0.5, color=YELLOW, r=18)
    # the user is moved from server 2 to server 3
    if move <= t < move + 0.5:
        k = ease((t - move) / 0.5)
        c.person((560, 856 + k * 130), t, move, color=YELLOW, r=18)
    if t >= move:
        c.pill((540, 1066), "переводим клиентов", YELLOW, t, move - 0.2, size=32)
    c.pill((540, 1200), "t.me/nexus_subs_bot · NEXUS3", YELLOW, t, 3.6, size=40)


SCENES = {
    "s4_01": (hook, 8.0),
    "s4_02": (one_server, 8.0),
    "s4_03": (owner, 8.0),
    "s4_04": (whitelist, 8.0),
    "s4_05": (monitor, 8.0),
}
