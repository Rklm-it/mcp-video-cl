import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT = Path(sys.argv[1])
FONT = "/usr/share/fonts/opentype/inter/Inter-Black.otf"
if not Path(FONT).exists():
    FONT = "/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf"
S = 1080
YEL, RED, NAVY, WHITE, BLACK = (255, 212, 0), (232, 32, 56), (11, 16, 48), (255, 255, 255), (0, 0, 0)

def f(size): return ImageFont.truetype(FONT, size)

def center_text(d, y, text, size, fill, stroke=0, sfill=BLACK, rot=None):
    font = f(size)
    w = d.textlength(text, font=font)
    d.text(((S - w) / 2, y), text, font=font, fill=fill, stroke_width=stroke, stroke_fill=sfill)

def v1():  # Красный круг, «НУ И» + «НОВОСТИ» на жёлтой плашке
    im = Image.new("RGB", (S, S), RED); d = ImageDraw.Draw(im)
    center_text(d, 260, "НУ И", 230, WHITE)
    band = Image.new("RGBA", (S, 260), (0, 0, 0, 0)); bd = ImageDraw.Draw(band)
    bd.rounded_rectangle([150, 25, S - 150, 235], 28, fill=YEL)
    font = f(140); w = bd.textlength("НОВОСТИ", font=font)
    bd.text(((S - w) / 2, 40), "НОВОСТИ", font=font, fill=BLACK)
    band = band.rotate(-5, resample=Image.BICUBIC, expand=False)
    im.paste(band, (0, 560), band)
    return im

def v2():  # Тёмный, огромное «НУ?!» — читается даже в 40 px
    im = Image.new("RGB", (S, S), NAVY); d = ImageDraw.Draw(im)
    font = f(360); t1, t2 = "НУ", "?!"
    w1, w2 = d.textlength(t1, font=font), d.textlength(t2, font=font)
    x = (S - w1 - w2) / 2
    d.text((x, 300), t1, font=font, fill=WHITE)
    d.text((x + w1, 300), t2, font=font, fill=YEL)
    center_text(d, 760, "НОВОСТИ", 96, RED)
    return im

def v3():  # Жёлтый, бейдж «СРОЧНО»-стиль: красная плашка «НУ И» и чёрное «НОВОСТИ»
    im = Image.new("RGB", (S, S), YEL); d = ImageDraw.Draw(im)
    font = f(150); t = "НУ И"; w = d.textlength(t, font=font)
    d.rounded_rectangle([(S - w) / 2 - 40, 300, (S + w) / 2 + 40, 490], 26, fill=RED)
    d.text(((S - w) / 2, 312), t, font=font, fill=WHITE)
    center_text(d, 520, "НОВОСТИ", 190, BLACK)
    return im

sheet = Image.new("RGB", (3 * 400 + 80, 560), (245, 245, 245)); sd = ImageDraw.Draw(sheet)
for i, (name, make) in enumerate((("1", v1), ("2", v2), ("3", v3))):
    im = make(); im.save(OUT / f"logo-{name}.png")
    small = im.resize((360, 360), Image.LANCZOS)
    mask = Image.new("L", (360, 360), 0); ImageDraw.Draw(mask).ellipse([0, 0, 359, 359], fill=255)
    x = 20 + i * 420
    sheet.paste(small, (x, 20), mask)
    tiny = im.resize((80, 80), Image.LANCZOS); m2 = Image.new("L", (80, 80), 0); ImageDraw.Draw(m2).ellipse([0, 0, 79, 79], fill=255)
    sheet.paste(tiny, (x + 140, 420), m2)
    sd.text((x + 170, 510), name, font=f(36), fill=BLACK)
sheet.save(OUT / "logos.png")
