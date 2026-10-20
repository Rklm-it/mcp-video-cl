"""Экраны iPhone (тёмная тема, русский интерфейс) для инструкции «регион App Store → Казахстан».

Записи экрана со сменой именно на Казахстан на русском не нашлось: общие шаги в ролике — настоящая
запись (YouTube KWZQmE53jZI, App Store → «Настройки учетной записи»), а три экрана, где видна страна,
нарисованы здесь в том же виде — телефон по центру кадра 1080×1920, по краям фон записи.

    python3 make_screens.py <каталог>
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1080, 1920
SX0, SX1 = 97, 982           # экран телефона (как в записи после кадрирования)
BG = (28, 28, 30)            # лист
CARD = (44, 44, 46)
SEP = (60, 60, 64)
WHITE = (255, 255, 255)
GRAY = (142, 142, 147)
DIM = (99, 99, 102)
BLUE = (10, 132, 255)
HILITE = (58, 58, 62)

FONTS = "/usr/share/fonts/opentype/inter/"


def font(size, weight="Regular"):
    for name in (f"Inter-{weight}.otf", "Inter-Regular.otf"):
        try:
            return ImageFont.truetype(FONTS + name, size)
        except OSError:
            continue
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", size)


def phone() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    """Фон записи (сине-фиолетовый) + корпус телефона + пустой тёмный лист."""
    img = Image.new("RGB", (W, H))
    top, bottom = (70, 120, 235), (120, 70, 200)
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / H
        d.line([(0, y), (W, y)], fill=tuple(int(a + (b - a) * t) for a, b in zip(top, bottom)))
    img = img.filter(ImageFilter.GaussianBlur(4))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([SX0 - 30, -60, SX1 + 30, H + 60], 120, fill=(20, 20, 22), outline=(120, 120, 128), width=6)
    d.rounded_rectangle([SX0, 0, SX1, H + 40], 90, fill=(0, 0, 0))
    d.rounded_rectangle([SX0, 110, SX1, H + 40], 50, fill=BG)
    # строка состояния: время в красной плашке записи экрана, как в исходнике
    d.rounded_rectangle([SX0 + 40, 22, SX0 + 190, 72], 25, fill=(230, 50, 50))
    d.text((SX0 + 115, 47), "19:08", font=font(30, "SemiBold"), fill=WHITE, anchor="mm")
    for i, h in enumerate((10, 16, 22, 28)):
        d.rectangle([SX1 - 175 + i * 12, 60 - h, SX1 - 167 + i * 12, 60], fill=WHITE)
    d.rounded_rectangle([SX1 - 100, 34, SX1 - 40, 62], 8, outline=WHITE, width=3)
    d.rectangle([SX1 - 95, 39, SX1 - 60, 57], fill=WHITE)
    return img, d


def cross(d, cx, cy, r=14):
    d.line([(cx - r, cy - r), (cx + r, cy + r)], fill=WHITE, width=5)
    d.line([(cx - r, cy + r), (cx + r, cy - r)], fill=WHITE, width=5)


def header(d, title, right=None, close=True):
    d.text(((SX0 + SX1) // 2, 172), title, font=font(38, "SemiBold"), fill=WHITE, anchor="mm")
    if close:
        d.ellipse([SX1 - 110, 132, SX1 - 34, 208], fill=CARD)
        cross(d, SX1 - 72, 170)
    if right:
        d.ellipse([SX0 + 34, 132, SX0 + 110, 208], fill=CARD)
        cross(d, SX0 + 72, 170)
        d.rounded_rectangle([SX1 - 190, 132, SX1 - 34, 208], 38, fill=CARD)
        d.text((SX1 - 112, 170), right, font=font(34, "Medium"), fill=WHITE, anchor="mm")


ROW = 118
LX, RX = SX0 + 48, SX1 - 48   # края карточек


def card(d, y, rows, value_x=None):
    """rows: (подпись, значение, цвет значения, шеврон, подсветка). Возвращает низ карточки."""
    d.rounded_rectangle([LX, y, RX, y + ROW * len(rows)], 34, fill=CARD)
    for i, (label, value, vcolor, chevron, hi) in enumerate(rows):
        ry = y + i * ROW
        if hi:
            d.rectangle([LX, ry, RX, ry + ROW], fill=HILITE)
        if i:
            d.line([(LX + 36, ry), (RX, ry)], fill=SEP, width=2)
        d.text((LX + 36, ry + ROW // 2), label, font=font(38), fill=WHITE, anchor="lm")
        if value:
            x = value_x or (RX - (70 if chevron else 36))
            anchor = "lm" if value_x else "rm"
            d.text((x, ry + ROW // 2), value, font=font(38), fill=vcolor, anchor=anchor)
        if chevron:
            d.text((RX - 36, ry + ROW // 2), "›", font=font(48), fill=DIM, anchor="rm")
    return y + ROW * len(rows)


def country_list(out: Path):
    img, d = phone()
    header(d, "Страна или регион")
    y = 250
    d.text((LX, y), "К", font=font(34, "SemiBold"), fill=GRAY, anchor="lm")
    y += 50
    names = ["Кабо-Верде", "Казахстан", "Камбоджа", "Камерун", "Канада", "Катар", "Кения", "Кипр",
             "Киргизия", "Китай", "Колумбия"]
    for name in names:
        hi = name == "Казахстан"
        if hi:
            d.rectangle([SX0, y, SX1, y + ROW], fill=HILITE)
        d.text((LX, y + ROW // 2), name, font=font(40, "Medium" if hi else "Regular"), fill=WHITE, anchor="lm")
        d.line([(LX, y + ROW), (SX1 - 70, y + ROW)], fill=SEP, width=2)
        y += ROW
    letters = "АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЭЮЯ"
    for i, ch in enumerate(letters):
        d.text((SX1 - 30, 300 + i * 46), ch, font=font(24, "SemiBold"), fill=BLUE, anchor="mm")
    d.rounded_rectangle([LX - 10, H - 190, SX1 - 70, H - 100], 45, fill=CARD)
    d.text((LX + 80, H - 145), "Поиск", font=font(38), fill=GRAY, anchor="lm")
    d.ellipse([LX + 22, H - 162, LX + 48, H - 136], outline=GRAY, width=4)
    d.line([(LX + 45, H - 139), (LX + 58, H - 126)], fill=GRAY, width=5)
    img.save(out)


def payment_form(out: Path):
    img, d = phone()
    header(d, "Добавление способа о…", right="Готово", close=False)
    y = 250
    d.text((LX + 36, y), "Способ оплаты", font=font(32), fill=GRAY, anchor="lm")
    y += 40
    d.rounded_rectangle([LX, y, RX, y + 3 * ROW + 50], 34, fill=CARD)
    d.text((LX + 36, y + 50), "Кредитная или дебетовая карта", font=font(38), fill=WHITE, anchor="lm")
    d.text((LX + 36, y + 98), "Visa, MasterCard, American Express", font=font(28), fill=GRAY, anchor="lm")
    d.line([(LX + 36, y + ROW + 50), (RX, y + ROW + 50)], fill=SEP, width=2)
    d.text((LX + 36, y + ROW + 50 + ROW // 2), "Мобильный телефон", font=font(38), fill=WHITE, anchor="lm")
    d.line([(LX + 36, y + 2 * ROW + 50), (RX, y + 2 * ROW + 50)], fill=SEP, width=2)
    d.text((LX + 36, y + 2 * ROW + 50 + ROW // 2), "Нет", font=font(38), fill=WHITE, anchor="lm")
    d.text((RX - 40, y + 2 * ROW + 50 + ROW // 2), "✓", font=font(46, "SemiBold"), fill=BLUE, anchor="rm")
    y += 3 * ROW + 50 + 70
    d.text((LX + 36, y), "Адрес выставления счета", font=font(32), fill=GRAY, anchor="lm")
    y += 40
    vx = LX + 330
    y = card(d, y, [
        ("Адрес", "Толе би 55", WHITE, False, False),
        ("Адрес", "Необязательно", DIM, False, False),
        ("Город", "Алматы", WHITE, False, False),
        ("Регион", "Алматы", WHITE, False, False),
        ("Индекс", "050000", WHITE, False, False),
        ("Страна/регион", "Казахстан", DIM, False, False),
    ], value_x=vx)
    y += 50
    y = card(d, y, [("Телефон", "+7  9001234567", WHITE, False, False)], value_x=vx)
    y += 50
    card(d, y, [("Имя", "Иван", WHITE, False, False), ("Фамилия", "Иванов", WHITE, False, False)], value_x=vx)
    img.save(out)


def account(out: Path, country: str, address: str):
    img, d = phone()
    header(d, "Настройки учетной записи")
    y = 250
    y = card(d, y, [("Аккаунт Apple", "•••••@gmail.com", GRAY, True, False)])
    y += 40
    y = card(d, y, [
        ("Способы оплаты", "Нет", GRAY, True, False),
        ("Адрес для выставления счета", address, GRAY, True, False),
        ("Страна/регион", country, GRAY, True, False),
    ])
    y += 40
    y = card(d, y, [("Пополнение счета учетной записи", "", GRAY, True, False)])
    y += 40
    y = card(d, y, [("История покупок", "", GRAY, True, False), ("Подписки", "", GRAY, True, False),
                    ("Скрытые покупки", "", GRAY, True, False)])
    y += 40
    card(d, y, [("Отзывы и оценки", "", GRAY, True, False)])
    img.save(out)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    country_list(out / "kz-list.png")
    payment_form(out / "kz-form.png")
    account(out / "kz-done.png", "Казахстан", "Толе…")
