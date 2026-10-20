"""Экраны iPhone (тёмная тема, русский интерфейс) для инструкции «скачать Happ/INCY: регион → Казахстан».

Записи экрана со сменой именно на Казахстан на русском нет, а кольца поверх чужой записи промахиваются
мимо кнопок. Поэтому весь путь нарисован здесь по образцу настоящей записи (YouTube KWZQmE53jZI,
App Store → «Настройки учетной записи»), и кнопка шага подсвечена прямо в кадре — жёлтой рамкой.
Кадр 1080×1920; ключевые кнопки держатся вне полосы субтитров (y≈0.70–0.82).

    python3 make_screens.py <каталог>
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SX0, SX1 = 70, 1010          # экран телефона
BG = (28, 28, 30)            # лист
CARD = (44, 44, 46)
SEP = (60, 60, 64)
WHITE = (255, 255, 255)
GRAY = (142, 142, 147)
DIM = (99, 99, 102)
BLUE = (10, 132, 255)
SELECT = (58, 58, 62)
MARK = (255, 214, 10)        # подсветка кнопки шага

FONTS = "/usr/share/fonts/opentype/inter/"


def font(size, weight="Regular"):
    try:
        return ImageFont.truetype(f"{FONTS}Inter-{weight}.otf", size)
    except OSError:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


class Screen:
    def __init__(self, sheet=True):
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        top, bottom = (70, 120, 235), (120, 70, 200)
        for y in range(H):
            t = y / H
            d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
        self.img = img.filter(ImageFilter.GaussianBlur(4))
        self.d = ImageDraw.Draw(self.img)
        d = self.d
        d.rounded_rectangle([SX0 - 26, -80, SX1 + 26, H + 80], 130, fill=(20, 20, 22),
                            outline=(120, 120, 128), width=6)
        d.rounded_rectangle([SX0, -40, SX1, H + 40], 100, fill=(0, 0, 0))
        if sheet:
            d.rounded_rectangle([SX0, 120, SX1, H + 40], 54, fill=BG)
        d.text((SX0 + 120, 62), "19:08", font=font(40, "SemiBold"), fill=WHITE, anchor="mm")
        for i, h in enumerate((12, 18, 24, 30)):
            d.rectangle([SX1 - 200 + i * 13, 76 - h, SX1 - 191 + i * 13, 76], fill=WHITE)
        d.rounded_rectangle([SX1 - 120, 46, SX1 - 54, 78], 9, outline=WHITE, width=3)
        d.rectangle([SX1 - 115, 51, SX1 - 75, 73], fill=WHITE)
        self.marks = []

    def text(self, xy, s, size=44, weight="Regular", fill=WHITE, anchor="lm"):
        self.d.text(xy, s, font=font(size, weight), fill=fill, anchor=anchor)

    def cross(self, cx, cy):
        self.d.ellipse([cx - 40, cy - 40, cx + 40, cy + 40], fill=CARD)
        for a, b in (((-15, -15), (15, 15)), ((-15, 15), (15, -15))):
            self.d.line([(cx + a[0], cy + a[1]), (cx + b[0], cy + b[1])], fill=WHITE, width=5)

    def title(self, s, close=True):
        self.text(((SX0 + SX1) // 2, 190), s, 42, "SemiBold", anchor="mm")
        if close:
            self.cross(SX1 - 80, 190)

    def mark(self, box, radius=30):
        """Жёлтая рамка вокруг кнопки шага (рисуется последней, поверх всего)."""
        self.marks.append((box, radius))

    def save(self, path):
        for (x0, y0, x1, y1), r in self.marks:
            glow = Image.new("RGBA", (W, H))
            ImageDraw.Draw(glow).rounded_rectangle([x0 - 10, y0 - 10, x1 + 10, y1 + 10], r + 10,
                                                   outline=MARK + (150,), width=18)
            self.img.paste(glow.filter(ImageFilter.GaussianBlur(10)), (0, 0), glow.filter(ImageFilter.GaussianBlur(10)))
            self.d = ImageDraw.Draw(self.img)
            self.d.rounded_rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], r + 6, outline=MARK, width=8)
        self.img.save(path)


ROW = 128
LX, RX = SX0 + 44, SX1 - 44


def card(s, y, rows, value_x=None, mark=None):
    """rows: (подпись, значение, цвет значения, шеврон). mark — номер строки для подсветки."""
    d = s.d
    d.rounded_rectangle([LX, y, RX, y + ROW * len(rows)], 36, fill=CARD)
    for i, (label, value, vcolor, chevron) in enumerate(rows):
        ry = y + i * ROW
        if i:
            d.line([(LX + 38, ry), (RX, ry)], fill=SEP, width=2)
        s.text((LX + 38, ry + ROW // 2), label, 42)
        if value:
            if value_x:
                s.text((value_x, ry + ROW // 2), value, 42, fill=vcolor)
            else:
                s.text((RX - (78 if chevron else 38), ry + ROW // 2), value, 42, fill=vcolor, anchor="rm")
        if chevron:
            s.text((RX - 38, ry + ROW // 2 - 4), "›", 54, fill=DIM, anchor="rm")
        if mark == i:
            s.mark((LX, ry, RX, ry + ROW), 24)
    return y + ROW * len(rows)


def appstore(out, query=None):
    s = Screen(sheet=False)
    s.text((LX, 210), "Поиск", 78, "Bold")
    s.d.ellipse([SX1 - 150, 160, SX1 - 50, 260], fill=(225, 60, 60))
    s.text((SX1 - 100, 210), "И", 50, "SemiBold", anchor="mm")
    y = 330
    s.text((LX, y), "Обзор", 46, "Bold")
    tiles = [("Топ приложений", (70, 140, 230)), ("Топ игр", (240, 150, 60)),
             ("Топ платных", (80, 190, 110)), ("Игры", (140, 110, 230)),
             ("Продуктивность", (90, 150, 240)), ("Фото и видео", (240, 170, 60))]
    tw, th = (RX - LX - 30) // 2, 220
    for i, (name, color) in enumerate(tiles):
        x0 = LX + (i % 2) * (tw + 30)
        y0 = y + 60 + (i // 2) * (th + 30)
        s.d.rounded_rectangle([x0, y0, x0 + tw, y0 + th], 30, fill=color)
        s.text((x0 + 30, y0 + th - 50), name, 38, "SemiBold")
    bar = (LX, H - 230, RX, H - 120)
    s.d.rounded_rectangle(bar, 55, fill=CARD)
    s.d.ellipse([LX + 40, H - 194, LX + 74, H - 160], outline=GRAY, width=5)
    s.d.line([(LX + 70, H - 164), (LX + 88, H - 146)], fill=GRAY, width=6)
    if query:
        s.text((LX + 115, H - 175), query, 46, "Medium")
        s.mark(bar, 55)
    else:
        s.text((LX + 115, H - 175), "Игры, приложения и др.", 44, fill=GRAY)
        s.mark((SX1 - 150, 160, SX1 - 50, 260), 50)
    s.save(out)


def account_menu(out):
    s = Screen()
    s.title("Уч. запись")
    y = 290
    s.d.rounded_rectangle([LX, y, RX, y + 170], 36, fill=CARD)
    s.d.ellipse([LX + 34, y + 35, LX + 134, y + 135], fill=(225, 60, 60))
    s.text((LX + 84, y + 85), "И", 50, "SemiBold", anchor="mm")
    s.text((LX + 165, y + 65), "Иван Иванов", 46, "SemiBold")
    s.text((LX + 165, y + 115), "ivan@icloud.com", 34, fill=GRAY)
    s.mark((LX, y, RX, y + 170), 30)
    y += 220
    y = card(s, y, [("Приложения", "", GRAY, True), ("История покупок", "", GRAY, True),
                    ("Уведомления", "", GRAY, True)])
    y += 50
    s.d.rounded_rectangle([LX, y, RX, y + 3 * ROW], 36, fill=CARD)
    for i, t in enumerate(("Погасить подарочную карту или код", "Отправить подарочную карту",
                           "Пополнить Аккаунт Apple")):
        s.text((LX + 38, y + i * ROW + ROW // 2), t, 40, fill=BLUE)
    s.save(out)


def settings(out, country, mark):
    s = Screen()
    s.title("Настройки учетной записи")
    y = 290
    y = card(s, y, [("Аккаунт Apple", "ivan@icloud.com", GRAY, True)])
    y += 45
    rows = [("Способы оплаты", "Нет", GRAY, True), ("Страна/регион", country, GRAY, True)]
    y = card(s, y, rows, mark=1 if mark == "country" else None)
    y += 45
    y = card(s, y, [("Пополнить Аккаунт Apple", "", GRAY, True)], mark=0 if mark == "balance" else None)
    y += 45
    card(s, y, [("История покупок", "", GRAY, True), ("Подписки", "", GRAY, True),
                ("Скрытые покупки", "", GRAY, True)], mark=1 if mark == "subs" else None)
    s.save(out)


def country_list(out):
    s = Screen()
    s.title("Страна или регион")
    y = 290
    s.text((LX, y), "К", 38, "SemiBold", fill=GRAY)
    y += 45
    for name in ["Кабо-Верде", "Казахстан", "Камбоджа", "Камерун", "Канада", "Катар", "Кения", "Кипр"]:
        if name == "Казахстан":
            s.d.rectangle([SX0, y, SX1, y + ROW], fill=SELECT)
            s.mark((LX - 20, y + 6, SX1 - 90, y + ROW - 6), 22)
        s.text((LX, y + ROW // 2), name, 46, "Medium" if name == "Казахстан" else "Regular")
        s.d.line([(LX, y + ROW), (SX1 - 80, y + ROW)], fill=SEP, width=2)
        y += ROW
    for i, ch in enumerate("АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЭЮЯ"):
        s.text((SX1 - 34, 330 + i * 46), ch, 26, "SemiBold", fill=BLUE, anchor="mm")
    s.save(out)


def change_country(out):
    s = Screen()
    s.d.ellipse([SX0 + 40, 150, SX0 + 120, 230], fill=CARD)
    s.text((SX0 + 80, 188), "‹", 60, fill=WHITE, anchor="mm")
    y = 320
    s.text((LX, y), "Изменение страны", 54, "Bold")
    s.text((LX, y + 70), "или региона", 54, "Bold")
    for i, line in enumerate(("При изменении страны или региона", "важно учесть некоторые детали.")):
        s.text((LX, y + 160 + i * 56), line, 40, fill=GRAY)
    s.text((LX, y + 330), "Обратите внимание:", 40, "SemiBold")
    for i, line in enumerate(("Некоторые покупки могут быть", "недоступны в новой стране или регионе.")):
        s.text((LX, y + 400 + i * 54), line, 38, fill=GRAY)
    btn = (LX, H - 330, RX, H - 210)
    s.d.rounded_rectangle(btn, 60, fill=BLUE)
    s.text(((LX + RX) // 2, H - 270), "Продолжить", 44, "SemiBold", anchor="mm")
    s.mark(btn, 60)
    s.d.rounded_rectangle([LX, H - 180, RX, H - 70], 55, outline=SEP, width=3)
    s.text(((LX + RX) // 2, H - 125), "Отменить", 44, "SemiBold", anchor="mm")
    s.save(out)


def payment_form(out, mark):
    s = Screen()
    s.cross(SX0 + 80, 190)
    s.text(((SX0 + SX1) // 2 - 20, 190), "Способ оплаты", 42, "SemiBold", anchor="mm")
    done = (SX1 - 230, 150, SX1 - 40, 230)
    s.d.rounded_rectangle(done, 40, fill=CARD)
    s.text(((done[0] + done[2]) // 2, 190), "Готово", 40, "SemiBold", anchor="mm")
    if mark == "done":
        s.mark(done, 40)
    y = 290
    s.d.rounded_rectangle([LX, y, RX, y + 3 * ROW], 36, fill=CARD)
    for i, t in enumerate(("Кредитная или дебетовая карта", "Мобильный телефон", "Нет")):
        if i:
            s.d.line([(LX + 38, y + i * ROW), (RX, y + i * ROW)], fill=SEP, width=2)
        s.text((LX + 38, y + i * ROW + ROW // 2), t, 42)
    s.text((RX - 44, y + 2 * ROW + ROW // 2), "✓", 52, "SemiBold", fill=BLUE, anchor="rm")
    if mark == "none":
        s.mark((LX, y + 2 * ROW, RX, y + 3 * ROW), 24)
    y += 3 * ROW + 50
    s.text((LX + 38, y), "Адрес выставления счета", 36, fill=GRAY)
    y += 35
    vx = LX + 340
    card(s, y, [("Адрес", "Толе би 55", WHITE, False), ("Город", "Алматы", WHITE, False),
                ("Регион", "Алматы", WHITE, False), ("Индекс", "050000", WHITE, False),
                ("Телефон", "+7 9001234567", WHITE, False), ("Страна", "Казахстан", DIM, False)],
         value_x=vx)
    s.save(out)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()
    appstore(out / "01-appstore.png")
    account_menu(out / "02-account.png")
    settings(out / "03-subs.png", "Россия", "subs")
    settings(out / "04-country.png", "Россия", "country")
    country_list(out / "05-kazakhstan.png")
    change_country(out / "06-continue.png")
    payment_form(out / "07-none.png", "none")
    payment_form(out / "08-done.png", "done")
    settings(out / "09-kz.png", "Казахстан", "country")
    appstore(out / "10-search.png", query="Happ")
