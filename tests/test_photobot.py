import io

import pytest
from PIL import Image

from video_mcp.photobot import bot as botmod
from video_mcp.photobot import platega, products
from video_mcp.photobot.config import bot_settings


class FakeApi:
    def __init__(self):
        self.sent, self.photos, self.albums, self.videos, self.audios, self.resent = [], [], [], [], [], []
        self.downloaded = []

    def send(self, chat, text, rows=None, reply_keys=None):
        self.sent.append((chat, text, rows))
        return {}

    def edit(self, chat, mid, text, rows=None):
        self.sent.append((chat, text, rows))

    def answer(self, *a, **k):
        pass

    def photo(self, chat, image, caption="", rows=None):
        self.photos.append(image)
        return f"result{len(self.photos)}"

    def album(self, chat, images, caption=""):
        self.albums.append(images)
        return [f"a{i}" for i in range(len(images))]

    def video(self, chat, path, caption=""):
        self.videos.append(path)
        return f"video{len(self.videos)}"

    def audio(self, chat, path, title):
        self.audios.append(title)

    def resend(self, chat, kind, ref):
        self.resent.append((kind, ref))

    def download(self, file_id):
        self.downloaded.append(file_id)
        return file_id.encode()


class Now:
    """Runs submitted jobs right away, so the test sees the result."""

    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture
def made(monkeypatch):
    calls = []

    def fake_make(product, d, refs, refs2, workdir, link, cache):
        calls.append((product, dict(d), refs, refs2))
        if product in ("shoot",):
            return "album", [b"1", b"2", b"3", b"4"]
        if product in ("greet", "char", "animate", "hug", "pvideo", "customvid", "moroz"):
            return "video", workdir / "v.mp4"
        return "photo", b"jpg"

    monkeypatch.setattr(products, "make", fake_make)
    return calls


@pytest.fixture
def bot(tmp_path, monkeypatch, made):
    monkeypatch.setattr(bot_settings, "admin_id", "")
    b = botmod.Bot(FakeApi(), botmod.State(tmp_path / "state.json"), "zhivoe_foto_ru_bot")
    b.pool = Now()
    b.ack_delay = 0
    return b


def photo_msg(uid=7, file_id="big"):
    return {"message": {"chat": {"id": uid}, "from": {"id": uid}, "photo": [{"file_id": "small"}, {"file_id": file_id}]}}


def press(data, uid=7):
    return {"callback_query": {"id": "cb", "from": {"id": uid, "username": "ivan"},
                               "message": {"chat": {"id": uid}, "message_id": 5}, "data": data}}


def say(bot, text, uid=7):
    bot.handle({"message": {"chat": {"id": uid}, "from": {"id": uid, "username": "ivan"}, "text": text}})


def buttons(bot):
    return [value for row in (bot.api.sent[-1][2] or []) for _, value in row]


def pay_with(monkeypatch, tx, status="CONFIRMED"):
    created = []
    monkeypatch.setattr(platega, "create", lambda amount, *a, **k: created.append(amount) or
                        {"transactionId": tx, "url": "https://pay.platega.io/?id=1", "status": "PENDING"})
    monkeypatch.setattr(platega, "status", lambda t: status)
    return created


def test_menu_sections_and_service_cards(bot):
    say(bot, "/start")
    assert "Оживи фото" in bot.api.sent[-2][1]
    assert {"sec:greet", "sec:photo", "sec:live", "sec:memory", "sec:family", "sec:sellers", "sec:idea",
            "orders", "ref", "help"} <= set(buttons(bot))
    bot.handle(press("sec:greet"))
    assert {"svc:greet", "svc:char", "svc:card"} <= set(buttons(bot)) and "svc:moroz" not in buttons(bot)
    bot.handle(press("svc:card"))
    card = bot.api.sent[-1][1]
    assert "бесплатно" in card and "Готово за" in card and buttons(bot)[0] == "go:card"
    for key in botmod.SERVICES:
        assert any(key in keys for _, _, keys in botmod.SECTIONS.values()), key


def test_several_reference_photos_summary_and_payment(bot, monkeypatch, made):
    created = pay_with(monkeypatch, "tx1", "PENDING")
    bot.handle(press("go:style"))
    assert "s:royal" in buttons(bot)
    bot.handle(press("s:royal"))
    assert "Лучше" in bot.api.sent[-1][1] or "фото" in bot.api.sent[-1][1]
    for i in range(3):
        bot.handle(photo_msg(file_id=f"p{i}"))
    assert "Получил фото: <b>3</b>" in bot.api.sent[-1][1] and "done" in buttons(bot)
    bot.handle(press("done"))
    summary = bot.api.sent[-1][1]
    assert "Проверьте заказ" in summary and "Фото: 3" in summary and "Королевский" in summary
    assert created == []  # nothing is paid before «pay»
    bot.handle(press("pay"))
    assert created == [bot_settings.price_style]
    assert buttons(bot)[0].startswith("https://pay.platega.io") and buttons(bot)[1] == "chk:tx1"
    monkeypatch.setattr(platega, "status", lambda tx: "CONFIRMED")
    bot.handle(press("chk:tx1"))
    assert made[0][0] == "style" and made[0][2] == [b"p0", b"p1", b"p2"]
    assert bot.state.orders["tx1"]["status"] == "done" and len(bot.api.photos) == 1
    bot.poll_pending()
    assert len(made) == 1  # a paid order is never made twice


def test_max_photos_moves_on_by_itself(bot, monkeypatch):
    pay_with(monkeypatch, "tx2")
    bot.handle(press("go:animate"))
    bot.handle(photo_msg(file_id="old"))
    assert "Проверьте заказ" in bot.api.sent[-1][1]


def test_first_card_is_free(bot, made):
    bot.handle(press("go:card"))
    bot.handle(press("o:bday"))
    bot.handle(photo_msg())
    bot.handle(press("done"))
    assert "бесплатно" in bot.api.sent[-1][1]
    bot.handle(press("pay"))
    assert made and made[0][0] == "card" and not bot.state.user(7)["free_card"]


def test_photos_first_then_service(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx3")
    bot.handle(photo_msg(file_id="a"))
    bot.handle(photo_msg(file_id="b"))
    assert "Что с ними сделать" in bot.api.sent[-1][1]
    bot.handle(press("go:shoot"))
    assert "Фото: 2" in bot.api.sent[-1][1]
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[0][2] == [b"a", b"b"] and bot.api.albums


def test_upsell_animates_the_result(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx4")
    bot.handle(press("go:restore"))
    bot.handle(photo_msg())
    bot.handle(press("pay"))
    bot.poll_pending()
    assert bot.state.orders["tx4"]["result"] == "result1"
    pay_with(monkeypatch, "tx5")
    bot.handle(press("up:tx4"))
    assert "Оживить" in bot.api.sent[-1][1]
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[-1][0] == "animate" and made[-1][2] == [b"result1"]


def test_video_greeting_walks_all_steps(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx6")
    bot.handle(press("go:greet"))
    assert len([v for v in buttons(bot) if v.startswith("o:")]) == len(products.OCCASIONS)
    bot.handle(press("o:wedding"))
    bot.handle(photo_msg())
    bot.handle(press("done"))
    assert "Как зовут" in bot.api.sent[-1][1]
    say(bot, "маша!!")
    assert "v:host" in buttons(bot) and "v:demo" in buttons(bot)
    monkeypatch.setattr(products, "voice_sample", lambda key, cache: cache / f"{key}.mp3")
    bot.handle(press("v:demo"))
    assert len(bot.api.audios) == len(products.VOICES)
    bot.handle(press("v:m"))
    assert "Маша, поздравляем со свадьбой" in bot.api.sent[-1][1]
    bot.handle(press("t:own"))
    say(bot, "Желаю счастья! https://spam.ru")
    summary = bot.api.sent[-1][1]
    assert "Имя: Маша" in summary and "«Желаю счастья!»" in summary
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[0][1] == {"product": "greet", "occasion": "wedding", "photos": ["big"], "name": "Маша",
                          "voice": "m", "text": "Желаю счастья!"}
    assert len(bot.api.videos) == 1


def test_character_greeting_needs_no_photo(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx7")
    bot.handle(press("go:char"))
    bot.handle(press("h:dragon"))
    bot.handle(press("o:bday"))
    say(bot, "Петя")
    bot.handle(press("t:ready"))
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[0][0] == "char" and made[0][2] == [] and bot.api.videos


def test_two_photo_sets_in_order(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx8")
    bot.handle(press("go:baby"))
    assert "мамы" in bot.api.sent[-1][1]
    bot.handle(photo_msg(file_id="mom1"))
    bot.handle(photo_msg(file_id="mom2"))
    bot.handle(press("done"))
    assert "папы" in bot.api.sent[-1][1]
    bot.handle(photo_msg(file_id="dad"))
    bot.handle(press("done"))
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[0][2] == [b"mom1", b"mom2"] and made[0][3] == [b"dad"]


def test_together_needs_two_photos(bot):
    bot.handle(press("go:together"))
    bot.handle(photo_msg(file_id="one"))
    bot.handle(press("done"))
    assert "хотя бы 2" in bot.api.sent[-1][1]


def test_own_request_without_photo_and_filter(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx9")
    bot.handle(press("sec:idea"))
    assert {"svc:custom", "svc:customvid"} <= set(buttons(bot))
    bot.handle(press("go:custom"))
    say(bot, "голая девушка на пляже")
    assert "не делает" in bot.api.sent[-1][1]
    say(bot, "Рыжий кот в очках читает газету, акварель")
    assert "nophoto" in buttons(bot)
    bot.handle(press("nophoto"))
    assert "Без фото" in bot.api.sent[-1][1]
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[0][1]["prompt"] == "Рыжий кот в очках читает газету, акварель" and made[0][2] == []


def test_failed_job_gives_a_free_retry(bot, monkeypatch):
    pay_with(monkeypatch, "tx10")

    def broken(*a):
        raise RuntimeError("blocked")

    monkeypatch.setattr(products, "make", broken)
    bot.handle(press("go:enhance"))
    bot.handle(photo_msg())
    bot.handle(press("pay"))
    bot.poll_pending()
    assert bot.state.orders["tx10"]["status"] == "failed"
    assert bot.state.user(7)["credits"]["enhance"] == 1 and "бесплатно" in bot.api.sent[-1][1]
    monkeypatch.setattr(platega, "create", lambda *a, **k: pytest.fail("the retry is free"))
    bot.handle(press("go:enhance"))
    bot.handle(photo_msg())
    assert "бесплатно" in bot.api.sent[-1][1]


def test_canceled_payment_makes_nothing(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx11", "CANCELED")
    bot.handle(press("go:animate"))
    bot.handle(photo_msg())
    bot.handle(press("pay"))
    bot.poll_pending()
    assert bot.state.orders["tx11"]["status"] == "canceled" and not made


def test_cancel_and_edit(bot):
    bot.handle(press("go:style"))
    bot.handle(press("s:anime"))
    bot.handle(photo_msg())
    bot.handle(press("done"))
    bot.handle(press("edit"))
    assert "s:royal" in buttons(bot)
    bot.handle(press("cancel"))
    assert not bot.state.user(7).get("draft")


def test_ded_moroz_is_hidden_until_opened(bot, monkeypatch):
    monkeypatch.setattr(bot_settings, "moroz_open", False)
    bot.handle(press("go:moroz"))
    assert not bot.state.user(7).get("draft")


def test_referral_gives_the_inviter_a_free_card(bot, monkeypatch):
    say(bot, "/start", uid=1)
    bot.handle(press("ref", uid=1))
    assert "start=r1" in bot.api.sent[-1][1]
    say(bot, "/start r1", uid=2)
    bot.handle(press("go:card", uid=2))
    bot.handle(press("o:bday", uid=2))
    bot.handle(photo_msg(uid=2))
    bot.handle(press("done", uid=2))
    bot.handle(press("pay", uid=2))
    assert bot.state.user(1)["credits"]["card"] == 1


def test_support_question_goes_to_the_owner(bot, monkeypatch):
    monkeypatch.setattr(bot_settings, "admin_id", "1")
    bot.handle(press("support"))
    say(bot, "Не пришло видео")
    assert bot.api.sent[-2][0] == "1" and "Не пришло видео" in bot.api.sent[-2][1]


def test_my_works_resends_results(bot, monkeypatch):
    bot.handle(press("orders"))
    assert "появятся" in bot.api.sent[-1][1]
    pay_with(monkeypatch, "tx12")
    bot.handle(press("go:shoot"))
    bot.handle(photo_msg())
    bot.handle(press("done"))
    bot.handle(press("pay"))
    bot.poll_pending()
    bot.handle(press("orders"))
    assert "re:tx12" in buttons(bot)
    bot.handle(press("re:tx12", uid=8))
    bot.handle(press("re:tx12"))
    assert bot.api.resent == [("album", ["a0", "a1", "a2", "a3"])]


def test_make_passes_all_reference_photos_to_the_model(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(products, "edit", lambda photos, prompt, aspect="3:4":
                        seen.append((len(photos), prompt)) or Image.new("RGB", (768, 1024), "pink"))
    kind, out = products.make("style", {"style": "royal"}, [b"1", b"2", b"3"], [], tmp_path, "t.me/x", tmp_path)
    assert kind == "photo" and seen[0][0] == 3 and "3 reference photos" in seen[0][1]


def test_image_model_falls_back_when_unavailable(monkeypatch):
    calls = []

    class Resp:
        def __init__(self, code, body):
            self.status_code, self._body, self.text = code, body, str(body)

        def json(self):
            return self._body

    import base64

    buf = io.BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="PNG")
    ok = {"candidates": [{"content": {"parts": [{"inlineData": {"data": base64.b64encode(buf.getvalue()).decode()}}]}}]}

    def post(url, **kw):
        calls.append(url)
        return Resp(404, {"error": "model not found"}) if len(calls) == 1 else Resp(200, ok)

    monkeypatch.setattr(products.net, "post", post)
    monkeypatch.setattr(products.gemini, "headers", lambda: {})
    src = io.BytesIO()
    Image.new("RGB", (100, 100)).save(src, format="JPEG")
    products.edit([src.getvalue()], "x")
    assert "gemini-3-pro-image" in calls[0] and "gemini-3-pro-image" not in calls[1]


def test_platega_request_shape(monkeypatch):
    seen = {}

    class Resp:
        status_code = 200

        def json(self):
            return {"transactionId": "t", "url": "https://pay", "status": "PENDING"}

    def post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, body=json)
        return Resp()

    monkeypatch.setattr(bot_settings, "platega_merchant", "m")
    monkeypatch.setattr(bot_settings, "platega_secret", "s")
    monkeypatch.setattr(platega.net, "post", post)
    platega.create(149, "Оживить фото", 7, "ivan", "animate", "https://t.me/x")
    assert seen["url"] == "https://app.platega.io/v2/transaction/process"
    assert seen["headers"] == {"X-MerchantId": "m", "X-Secret": "s"}
    assert seen["body"]["paymentDetails"] == {"amount": 149, "currency": "RUB"}
    assert seen["body"]["metadata"] == {"userId": "7", "userName": "@ivan"}


def test_vertical_frame_keeps_whole_photo(tmp_path):
    buf = io.BytesIO()
    Image.new("RGB", (1200, 800), "red").save(buf, format="JPEG")
    out = products.vertical_frame(buf.getvalue(), tmp_path / "f.jpg")
    frame = Image.open(out)
    assert frame.size == (720, 1280)
    assert frame.getpixel((360, 640))[0] > 200  # the photo sits in the middle


def test_signed_video_has_link(tmp_path):
    import subprocess

    src = tmp_path / "in.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=blue:s=720x1280:d=1", "-pix_fmt", "yuv420p", str(src)], check=True)
    out = products.sign_video(src, tmp_path / "out.mp4", "t.me/zhivoe_foto_ru_bot")
    assert out.name == "out.mp4" and out.stat().st_size > 0


def test_greeting_video_has_voice_and_title(tmp_path, monkeypatch):
    import json
    import subprocess

    monkeypatch.setattr(products, "edit", lambda photo, prompt, aspect="3:4": Image.new("RGB", (576, 1024), "pink"))

    def fake_animate(frame, prompt, seconds, out, context=True, audio=False):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "color=c=blue:s=720x1280:d=2", "-pix_fmt", "yuv420p", str(out)], check=True)
        return out

    def fake_voice(text, out, key="f"):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                        "sine=frequency=300:duration=3", "-c:a", "libmp3lame", str(out)], check=True)
        return out

    monkeypatch.setattr(products.video_gen, "animate", fake_animate)
    monkeypatch.setattr(products, "voice", fake_voice)
    buf = io.BytesIO()
    Image.new("RGB", (600, 800), "red").save(buf, format="JPEG")
    out = products.greeting(buf.getvalue(), "bday", "Маша", tmp_path, "t.me/zhivoe_foto_ru_bot")
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                                      "-show_entries", "format=duration", "-of", "json", str(out)],
                                     capture_output=True, text=True, check=True).stdout)
    assert {s["codec_type"] for s in info["streams"]} == {"video", "audio"}
    assert float(info["format"]["duration"]) >= 3.9  # the voice (3 s + 0.5 s delay) is not cut by the 2 s clip


def test_clean_name():
    assert products.clean_name("  маша!! ") == "Маша"
    assert products.clean_name("Анна-Мария 123") == "Анна-Мария"
    assert products.clean_name("123") == ""


def test_gateway_voice_falls_back_to_a_free_one(tmp_path, monkeypatch):
    used = []

    def broken(*a):
        raise RuntimeError("500")

    monkeypatch.setattr(products, "_gateway_voice", broken)

    class Talk:
        def __init__(self, text, name, rate, pitch):
            used.append(name)

        async def save(self, path):
            open(path, "wb").write(b"mp3")

    import edge_tts

    monkeypatch.setattr(edge_tts, "Communicate", Talk)
    products.voice("Привет", tmp_path / "v.mp3", "host")
    assert used == ["ru-RU-DmitryNeural"]


def test_nearest_aspect_keeps_the_photo_shape():
    def shape(w, h):
        buf = io.BytesIO()
        Image.new("RGB", (w, h)).save(buf, format="JPEG")
        return products.nearest_aspect(buf.getvalue())

    assert shape(1000, 1000) == "1:1" and shape(900, 1200) == "3:4" and shape(1600, 900) == "16:9"


def test_character_picture_is_made_once(tmp_path, monkeypatch):
    from video_mcp.reels import images

    calls = []
    monkeypatch.setattr(images, "picture", lambda prompt, aspect="1:1", seed=1:
                        calls.append(prompt) or Image.new("RGB", (576, 1024), "green"))
    for _ in range(2):
        products.character_picture("hero", "bday", tmp_path)
    assert len(calls) == 1 and "no logos" in calls[0]


def test_request_filter():
    assert products.allowed_request("Сделай меня рыцарем")
    assert not products.allowed_request("NSFW картинка")


def test_superhero_with_the_name(bot, monkeypatch, made):
    pay_with(monkeypatch, "tx30")
    bot.handle(press("sec:family"))
    assert buttons(bot)[0] == "svc:superhero"
    bot.handle(press("go:superhero"))
    assert "sh:fire" in buttons(bot)
    bot.handle(press("sh:ice"))
    bot.handle(photo_msg(file_id="kid1"))
    bot.handle(photo_msg(file_id="kid2"))
    bot.handle(press("done"))
    assert "Как зовут героя" in bot.api.sent[-1][1]
    say(bot, "маша")
    assert "Ледяной" in bot.api.sent[-1][1] and "Имя: Маша" in bot.api.sent[-1][1]
    bot.handle(press("pay"))
    bot.poll_pending()
    assert made[0][0] == "superhero" and made[0][1]["hero"] == "ice" and made[0][2] == [b"kid1", b"kid2"]


def test_superhero_prompt_is_original_and_titled(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(products, "edit", lambda photos, prompt, aspect="3:4":
                        seen.append(prompt) or Image.new("RGB", (768, 1024), "blue"))
    kind, _ = products.make("superhero", {"hero": "fire", "name": "Маша"}, [b"1", b"2"], [], tmp_path, "t.me/x",
                            tmp_path)
    assert kind == "photo" and 'letter "М"' in seen[0] and "Not resembling" in seen[0]
    assert products.hero_title("Маша") == "Супер-Маша!"
