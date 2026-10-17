"""z1 · «Как файлы сжимаются — и почему фото в архиве не худеют?» — топ-тема @aldoniq (42,5 тыс. лайков,
13,1 тыс. репостов). ~25 с, клипы длиннее голоса и всё время в движении (урок d1).

Факты: ZIP сжимает алгоритмом DEFLATE = LZ77 (Лемпель и Зив, 1977: повтор заменяется ссылкой «расстояние, длина»)
+ код Хаффмана (частые символы — короткий код). JPEG/MP4 уже сжаты — повторов почти нет, ZIP их почти не
уменьшает. 42.zip — 42 КБ, 5 уровней вложенных архивов по 16, внизу файлы по 4,3 ГБ: всего 4,5 ПБ (Википедия).
"""

import math

from motion import CARD, CYAN, GREEN, MUTED, NAVY, RED, WHITE, YELLOW, Canvas, ease, font, prog

PHRASE = "МАМА МЫЛА РАМУ"


def big_title(c: Canvas, lines, t: float) -> None:
    if c.bare:  # the cover draws its own question
        return
    y = 170
    for i, line in enumerate(lines):
        big = i == 1
        size = 118 if big else 70
        while font("Unbounded", size, "Black").getlength(line) > 960:
            size -= 2
        c.text((60, y), line, size, YELLOW if big else WHITE, "Unbounded", "Black", t, i * 0.12)
        y += size + 12


def file_row(c: Canvas, y: int, name: str, before: str, after: str, frac: float, color, t: float, t0: float) -> None:
    """A file card whose size bar shrinks to `frac` once it has been zipped."""
    p = c.card((90, y, 990, y + 170), t, t0, outline=(70, 95, 160))
    if p <= 0:
        return
    lay, d = c.layer()
    d.rounded_rectangle((120, y + 30, 200, y + 140), radius=10, fill=(225, 232, 250))
    d.polygon(((175, y + 30), (200, y + 55), (175, y + 55)), fill=(160, 175, 210))
    d.text((230, y + 30), name, font=font("Manrope", 40, "ExtraBold"), fill=WHITE)
    shrink = ease((t - t0 - 0.8) / 1.2)
    w = 700 * (1 - (1 - frac) * shrink)
    d.rounded_rectangle((230, y + 100, 930, y + 128), radius=14, fill=(30, 45, 90))
    d.rounded_rectangle((230, y + 100, 230 + w, y + 128), radius=14, fill=color)
    label = after if shrink > 0.95 else before
    d.text((960, y + 50), label, font=font("Unbounded", 40, "Black"), fill=color, anchor="rm")
    c.put(lay, p)


def hook(c: Canvas, t: float) -> None:
    c.header("КАК УСТРОЕН КОМПЬЮТЕР", t)
    big_title(c, ("КАК ФАЙЛЫ", "СЖИМАЮТСЯ?", "И ПОЧЕМУ ФОТО — НЕТ"), t)
    file_row(c, 560, "текст.txt", "100 КБ", "25 КБ", 0.25, GREEN, t, 0.2)
    file_row(c, 780, "фото.jpg", "4 МБ", "4 МБ", 0.99, RED, t, 0.5)
    c.pill((540, 1050), "ZIP", YELLOW, t, 0.4, size=44)


def tiles(c: Canvas, text: str, x0: int, y: int, t: float, t0: float, color=WHITE, fill=CARD, size=46) -> int:
    """Letters as tiles; returns the x after the last tile."""
    x = x0
    lay, d = c.layer()
    f = font("Unbounded", size, "Black")
    for i, ch in enumerate(text):
        w = 30 if ch == " " else 62
        if ch != " ":
            p = prog(t, t0 + i * 0.03, 0.25)
            if p > 0:
                d.rounded_rectangle((x, y, x + 56, y + 76), radius=10, fill=fill)
                d.text((x + 28, y + 38), ch, font=f, fill=color, anchor="mm")
        x += w
    c.put(lay)
    return x


def repeats(c: Canvas, t: float) -> None:
    c.header("ПРИЁМ 1 · ПОВТОРЫ", t)
    c.title("ПОВТОР НЕ ПИШЕТСЯ", "ВТОРОЙ РАЗ", t)
    tiles(c, PHRASE, 80, 520, t, 0.2, fill=(40, 70, 140))
    collapse = ease((t - 2.4) / 0.6)
    if collapse < 1:
        lay, d = c.layer()
        c.put(lay)
        tiles(c, PHRASE, 80, 660, t, 1.0, color=NAVY, fill=YELLOW)
        if collapse > 0:
            cover, dd = c.layer()
            dd.rectangle((80 + 900 * (1 - collapse), 650, 1000, 750), fill=(11, 20, 48, int(255 * collapse)))
            c.put(cover)
    c.pill((540, 700), "ССЫЛКА: 14 БУКВ НАЗАД", YELLOW, t, 2.9, size=40)
    c.arrow((540, 655), (540, 605), t, 3.2, 0.4, color=YELLOW, width=6)
    c.text((540, 900), "14 букв → 2 числа", 64, GREEN, "Unbounded", "Black", t, 3.6, anchor="mm", glow=10)
    c.text((540, 1000), "так работает ZIP: алгоритм LZ77, 1977 год", 32, MUTED, "Manrope", "Bold", t, 3.8,
           anchor="mm")


CODES = (("О", "01", GREEN), ("А", "100", GREEN), ("Ж", "11011", YELLOW), ("Ъ", "1101001101", RED))


def codes(c: Canvas, t: float) -> None:
    c.header("ПРИЁМ 2 · КОРОТКИЕ КОДЫ", t)
    c.title("ЧАСТАЯ БУКВА —", "КОРОТКИЙ КОД", t)
    for i, (ch, bits, color) in enumerate(CODES):
        y = 500 + i * 150
        t0 = 0.3 + i * 0.4
        c.card((90, y, 990, y + 120), t, t0, outline=(60, 85, 150))
        c.text((150, y + 60), ch, 70, WHITE, "Unbounded", "Black", t, t0, anchor="mm")
        n = len(bits)
        p = prog(t, t0 + 0.2, 0.6)
        lay, d = c.layer()
        d.rounded_rectangle((230, y + 38, 230 + 60 * n * p, y + 82), radius=10, fill=color)
        c.put(lay, glow=6)
        c.text((250 + 60 * n, y + 60), f"{n} бит", 36, color, "Manrope", "ExtraBold", t, t0 + 0.7, anchor="lm")
    c.text((540, 1160), "текст худеет в разы", 56, GREEN, "Unbounded", "Black", t, 2.4, anchor="mm", glow=10)


def photo(c: Canvas, t: float) -> None:
    c.header("ПОЧЕМУ ФОТО — НЕТ", t)
    c.title("ФОТО И ВИДЕО", "УЖЕ СЖАТЫ", t)
    # a JPEG's bytes: noise, no repeats left to find
    lay, d = c.layer()
    for r in range(8):
        for k in range(14):
            v = (math.sin((r * 14 + k) * 12.9898 + int(t * 6) * 0.7) * 43758.5453) % 1
            d.rounded_rectangle((100 + k * 63, 470 + r * 46, 152 + k * 63, 506 + r * 46), radius=6,
                                fill=(int(40 + 160 * v), int(60 + 90 * v), int(140 + 80 * (1 - v))))
    c.put(lay, prog(t, 0.2, 0.5))
    c.pill((540, 880), "ПОВТОРОВ НЕ ОСТАЛОСЬ", RED, t, 1.0, size=42, text_color=WHITE)
    file_row(c, 960, "фото.jpg → архив", "4 МБ", "3,9 МБ", 0.97, RED, t, 1.4)


def bomb(c: Canvas, t: float) -> None:
    c.header("ZIP-БОМБА", t)
    c.title("А БЫВАЕТ", "НАОБОРОТ", t)
    p = prog(t, 0.2, 0.4)
    lay, d = c.layer()
    d.rounded_rectangle((400, 470, 520, 610), radius=12, fill=(225, 232, 250))
    d.rounded_rectangle((430, 560, 490, 595), radius=6, fill=(180, 140, 40))
    d.text((460, 578), "ZIP", font=font("Manrope", 22, "ExtraBold"), fill=WHITE, anchor="mm")
    d.text((560, 540), "42 КБ", font=font("Unbounded", 64, "Black"), fill=WHITE, anchor="lm")
    c.put(lay, p)
    c.arrow((540, 650), (540, 760), t, 0.8, 0.4, color=RED, width=8)
    grow = ease((t - 1.2) / 1.6)
    c.text((540, 900), f"{4.5 * grow:.1f}".replace(".", ","), 180, RED, "Unbounded", "Black", t, 1.2, anchor="mm",
           glow=16)
    c.text((540, 1035), "ПЕТАБАЙТА", 70, WHITE, "Unbounded", "Black", t, 1.3, anchor="mm")
    c.text((540, 1105), "≈ миллион фильмов в HD · архив 42.zip", 34, MUTED, "Manrope", "ExtraBold", t, 1.6, anchor="mm")
    lay, d = c.layer()
    d.rounded_rectangle((160, 1175, 920, 1211), radius=18, fill=(30, 45, 90))
    d.rounded_rectangle((160, 1175, 160 + 760 * grow, 1211), radius=18, fill=RED)
    c.put(lay, prog(t, 1.2, 0.3), glow=8)
    c.pill((540, 1300), "ДИСК ЗАПОЛНЕН", RED, t, 2.9, size=42, text_color=WHITE)


DOCX_FILES = ("[Content_Types].xml", "word/document.xml", "word/styles.xml", "word/media/image1.png",
              "docProps/core.xml")


def docx(c: Canvas, t: float) -> None:
    c.header("ФАКТ", t)
    c.title("ТВОЙ .DOCX —", "ЭТО ТОЖЕ ZIP", t)
    renamed = t >= 1.6
    lay, d = c.layer()
    p = prog(t, 0.2, 0.4)
    d.rounded_rectangle((120, 470, 240, 620), radius=12, fill=(225, 232, 250))
    d.rounded_rectangle((140, 560, 220, 595), radius=6, fill=(180, 140, 40) if renamed else (45, 110, 220))
    d.text((180, 578), "ZIP" if renamed else "W", font=font("Manrope", 24, "ExtraBold"), fill=WHITE, anchor="mm")
    name = "отчёт.zip" if renamed else "отчёт.docx"
    # the extension is retyped letter by letter
    if 1.0 <= t < 1.6:
        k = int((t - 1.0) / 0.6 * 4)
        name = "отчёт." + ("docx"[:4 - k] if k < 4 else "")
    d.text((280, 545), name, font=font("Unbounded", 60, "Black"), fill=YELLOW if renamed else WHITE, anchor="lm")
    c.put(lay, p)
    if renamed:
        c.card((90, 680, 990, 1120), t, 1.9, outline=(70, 95, 160))
        c.text((140, 715), "внутри:", 32, MUTED, "Manrope", "Bold", t, 2.0)
        for i, f in enumerate(DOCX_FILES):
            c.text((140, 775 + i * 64), "· " + f, 38, WHITE, "Manrope", "ExtraBold", t, 2.1 + i * 0.2)
    c.pill((540, 1220), "переименуй и открой", YELLOW, t, 3.4, size=44)


def nest(c: Canvas, t: float) -> None:
    c.header("КАК УСТРОЕНА БОМБА", t)
    c.title("16 АРХИВОВ,", "В КАЖДОМ ЕЩЁ 16", t)
    lvl = min(5, int(max(0.0, t - 0.4) / 0.7) + 1)
    lay, d = c.layer()
    # each level: a row of 16 boxes, smaller and denser — a tree that explodes downwards
    for L in range(lvl):
        y = 480 + L * 110
        n = 16
        w = 820 / n
        for k in range(n):
            x = 90 + k * w
            col = (180, 140, 40) if L < 4 else RED
            d.rounded_rectangle((x + 3, y, x + w - 3, y + 70), radius=6, fill=col)
        d.text((990, y + 35), "×16", font=font("Manrope", 30, "ExtraBold"), fill=WHITE, anchor="rm")
    c.put(lay, glow=6)
    if lvl >= 5:
        c.text((540, 1090), "1 048 576 файлов", 66, WHITE, "Unbounded", "Black", t, 3.4, anchor="mm")
        c.text((540, 1180), "по 4,3 ГБ = 4,5 ПБ", 66, RED, "Unbounded", "Black", t, 3.7, anchor="mm", glow=12)
        c.pill((540, 1300), "сохрани — пригодится", YELLOW, t, 4.4, size=42)


# обложка (первый кадр и PNG для «Обложка → из фотоплёнки»): хук вопросом, как у @aldoniq
COVER = ("КАК ФАЙЛЫ", "СЖИМАЮТСЯ?", "И ПОЧЕМУ ФОТО — НЕТ")

SCENES = {
    "z1_01hot": (hook, 5.0, 0.6),
    "z1_02": (repeats, 8.0),
    "z1_03": (codes, 7.0),
    "z1_04": (photo, 7.0),
    "z1_05": (docx, 8.0),
    "z1_06": (bomb, 8.0),
    "z1_07": (nest, 9.0),
}
