import io

import pytest
from PIL import Image

from video_mcp.photobot import bot as botmod
from video_mcp.photobot import platega, products
from video_mcp.photobot.config import bot_settings


class FakeApi:
    def __init__(self):
        self.sent, self.photos, self.albums, self.videos, self.audios, self.resent = [], [], [], [], [], []

    def send(self, chat, text, rows=None, reply_keys=None):
        self.sent.append((chat, text, rows))
        return {}

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

    def resend(self, chat, kind, ref):
        self.resent.append((kind, ref))

    def audio(self, chat, path, title):
        self.audios.append(title)

    def download(self, file_id):
        buf = io.BytesIO()
        Image.new("RGB", (800, 600), "skyblue").save(buf, format="JPEG")
        return buf.getvalue()


class Now:
    """Runs submitted jobs right away, so the test sees the result."""

    def submit(self, fn, *args):
        fn(*args)


@pytest.fixture
def bot(tmp_path, monkeypatch):
    monkeypatch.setattr(bot_settings, "admin_id", "")
    monkeypatch.setattr(products, "edit", lambda photo, prompt, aspect="3:4": Image.new("RGB", (768, 1024), "pink"))
    b = botmod.Bot(FakeApi(), botmod.State(tmp_path / "state.json"), "zhivoe_foto_ru_bot")
    b.pool = Now()
    return b


def photo_msg(uid=7):
    return {"message": {"chat": {"id": uid}, "from": {"id": uid}, "photo": [{"file_id": "small"}, {"file_id": "big"}]}}


def press(data, uid=7):
    return {"callback_query": {"id": "cb", "from": {"id": uid, "username": "ivan"},
                               "message": {"chat": {"id": uid}}, "data": data}}


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


def test_start_shows_the_menu_and_greetings_section(bot):
    say(bot, "/start")
    assert {"sec:greet", "sec:memory", "sec:family", "sec:fix", "orders", "ref"} <= set(buttons(bot))
    bot.handle(press("sec:memory"))
    assert "p:restore" in buttons(bot) and "p:together" in buttons(bot)
    bot.handle(press("sec:greet"))
    assert {"p:greet", "p:char", "p:card"} <= set(buttons(bot)) and "p:moroz" not in buttons(bot)
    assert "бесплатно" in bot.api.sent[-1][2][2][0][0]


def test_first_card_is_free_then_paid_via_platega(bot, monkeypatch):
    bot.handle(press("p:card"))
    assert "o:bday" in buttons(bot)
    bot.handle(press("o:bday"))
    assert bot.state.user(7)["await"] == "photo"
    bot.handle(photo_msg())
    assert len(bot.api.photos) == 1
    assert not bot.state.user(7)["free_card"]

    created = pay_with(monkeypatch, "tx1", "PENDING")
    bot.handle(press("p:card"))
    bot.handle(press("o:love"))  # the photo sent a moment ago is used without asking again
    assert created == [bot_settings.price_card]
    assert buttons(bot)[0].startswith("https://pay.platega.io") and buttons(bot)[1] == "chk:tx1"
    bot.poll_pending()
    assert bot.state.orders["tx1"]["status"] == "pending" and len(bot.api.photos) == 1
    monkeypatch.setattr(platega, "status", lambda tx: "CONFIRMED")
    bot.handle(press("chk:tx1"))
    assert bot.state.orders["tx1"]["status"] == "done" and len(bot.api.photos) == 2
    bot.poll_pending()  # a paid order is never made twice
    assert len(bot.api.photos) == 2


def test_photo_first_then_service_and_upsell_to_animate(bot, monkeypatch):
    bot.handle(photo_msg())
    assert "sec:memory" in buttons(bot)
    pay_with(monkeypatch, "tx5")
    bot.handle(press("p:restore"))
    bot.poll_pending()
    assert bot.state.orders["tx5"]["status"] == "done" and bot.state.orders["tx5"]["result"] == "result1"
    animated = []
    monkeypatch.setattr(products, "animate", lambda photo, workdir, link: animated.append(1) or workdir / "a.mp4")
    pay_with(monkeypatch, "tx6")
    bot.handle(press("up:tx5"))
    assert bot.state.orders["tx6"]["photo"] == "result1" and bot.state.orders["tx6"]["product"] == "animate"
    bot.poll_pending()
    assert animated and len(bot.api.videos) == 1


def test_style_asks_which_look(bot, monkeypatch):
    pay_with(monkeypatch, "tx7")
    bot.handle(press("p:style"))
    assert "s:royal" in buttons(bot)
    bot.handle(press("s:royal"))
    bot.handle(photo_msg())
    assert bot.state.orders["tx7"]["draft"]["style"] == "royal"
    bot.poll_pending()
    assert len(bot.api.photos) == 1


def test_failed_job_gives_a_free_retry(bot, monkeypatch):
    pay_with(monkeypatch, "tx2")

    def broken(*a):
        raise RuntimeError("blocked")

    monkeypatch.setattr(products, "photoshoot", broken)
    bot.handle(photo_msg())
    bot.handle(press("p:shoot"))
    bot.poll_pending()
    assert bot.state.orders["tx2"]["status"] == "failed"
    assert bot.state.user(7)["credits"]["shoot"] == 1

    monkeypatch.setattr(products, "photoshoot", lambda photo, link: [b"1", b"2", b"3", b"4"])
    monkeypatch.setattr(platega, "create", lambda *a, **k: pytest.fail("the retry is free"))
    bot.handle(press("p:shoot"))
    assert bot.api.albums == [[b"1", b"2", b"3", b"4"]]
    assert bot.state.user(7)["credits"]["shoot"] == 0


def test_canceled_payment_makes_nothing(bot, monkeypatch):
    pay_with(monkeypatch, "tx3", "CANCELED")
    bot.handle(photo_msg())
    bot.handle(press("p:animate"))
    bot.poll_pending()
    assert bot.state.orders["tx3"]["status"] == "canceled"
    assert not bot.api.videos


def test_video_greeting_asks_occasion_photo_name_voice_and_text(bot, monkeypatch):
    pay_with(monkeypatch, "tx4")
    made = []
    monkeypatch.setattr(products, "greeting", lambda photo, occasion, name, workdir, link, voice, text:
                        made.append((occasion, name, voice, text)) or workdir / "g.mp4")
    bot.handle(press("p:greet"))
    assert len([v for v in buttons(bot) if v.startswith("o:")]) == len(products.OCCASIONS)
    bot.handle(press("o:wedding"))
    assert bot.state.user(7)["await"] == "photo"
    bot.handle(photo_msg())
    assert "имя" in bot.api.sent[-1][1]
    say(bot, "маша!!")
    assert "v:host" in buttons(bot) and "v:demo" in buttons(bot)
    monkeypatch.setattr(products, "voice_sample", lambda key, cache: cache / f"{key}.mp3")
    bot.handle(press("v:demo"))
    assert len(bot.api.audios) == len(products.VOICES)
    bot.handle(press("v:m"))
    assert "Маша, поздравляем со свадьбой" in bot.api.sent[-1][1]
    bot.handle(press("t:own"))
    say(bot, "Желаю счастья! https://spam.ru")
    assert bot.state.orders["tx4"]["draft"] == {"product": "greet", "occasion": "wedding", "photo": "big",
                                                "name": "Маша", "voice": "m", "text": "Желаю счастья!"}
    bot.poll_pending()
    assert made == [("wedding", "Маша", "m", "Желаю счастья!")] and len(bot.api.videos) == 1


def test_character_greeting_needs_no_photo(bot, monkeypatch):
    pay_with(monkeypatch, "tx8")
    made = []
    monkeypatch.setattr(products, "character_greeting", lambda key, occasion, name, text, workdir, link, cache:
                        made.append((key, occasion, name, text)) or workdir / "c.mp4")
    bot.handle(press("p:char"))
    assert "h:dragon" in buttons(bot)
    bot.handle(press("h:dragon"))
    bot.handle(press("o:bday"))
    say(bot, "Петя")
    bot.handle(press("t:ready"))
    bot.poll_pending()
    assert made == [("dragon", "bday", "Петя", "")] and len(bot.api.videos) == 1
    assert bot.api.photos == []  # no photo was ever asked for


def test_ded_moroz_is_hidden_until_opened(bot, monkeypatch):
    monkeypatch.setattr(bot_settings, "moroz_open", False)
    bot.handle(press("p:moroz"))
    assert "p:moroz" not in str(bot.api.sent) and not bot.state.user(7).get("draft")


def test_referral_gives_the_inviter_a_free_card(bot, monkeypatch):
    say(bot, "/start", uid=1)
    bot.handle(press("ref", uid=1))
    assert "start=r1" in bot.api.sent[-1][1]
    say(bot, "/start r1", uid=2)
    bot.handle(press("p:card", uid=2))
    bot.handle(press("o:bday", uid=2))
    bot.handle(photo_msg(uid=2))
    assert bot.state.user(1)["credits"]["card"] == 1
    assert any(chat == 1 and "друг" in text.lower() for chat, text, _ in bot.api.sent)
    say(bot, "/start r1", uid=2)  # only once per friend
    bot.handle(press("p:card", uid=2))
    pay_with(monkeypatch, "tx9")
    bot.handle(press("o:love", uid=2))
    bot.poll_pending()
    assert bot.state.user(1)["credits"]["card"] == 1


def test_support_question_goes_to_the_owner(bot, monkeypatch):
    monkeypatch.setattr(bot_settings, "admin_id", "1")
    bot.handle(press("support"))
    say(bot, "Не пришло видео")
    assert bot.api.sent[-2][0] == "1" and "Не пришло видео" in bot.api.sent[-2][1]


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


def test_two_photo_service_asks_both_photos_in_order(bot, monkeypatch):
    pay_with(monkeypatch, "tx10")
    got = []
    monkeypatch.setattr(products, "baby", lambda p1, p2, link: got.append((p1, p2)) or b"img")
    downloaded = []
    real = bot.api.download
    bot.api.download = lambda fid: downloaded.append(fid) or real(fid)
    bot.handle(photo_msg())  # an earlier photo is not taken silently for a two-photo service
    bot.handle(press("p:baby"))
    assert "мамы" in bot.api.sent[-1][1]
    bot.handle({"message": {"chat": {"id": 7}, "from": {"id": 7}, "photo": [{"file_id": "mom"}]}})
    assert "папы" in bot.api.sent[-1][1]
    bot.handle({"message": {"chat": {"id": 7}, "from": {"id": 7}, "photo": [{"file_id": "dad"}]}})
    bot.poll_pending()
    assert downloaded == ["mom", "dad"] and len(got) == 1


def test_background_asks_which_scene(bot, monkeypatch):
    pay_with(monkeypatch, "tx11")
    made = []
    monkeypatch.setattr(products, "background", lambda photo, key, link: made.append(key) or b"img")
    bot.handle(press("p:bg"))
    assert "b:white" in buttons(bot)
    bot.handle(press("b:white"))
    bot.handle(photo_msg())
    bot.poll_pending()
    assert made == ["white"]


def test_my_orders_resends_results(bot, monkeypatch):
    bot.handle(press("orders"))
    assert "пока нет" in bot.api.sent[-1][1]
    pay_with(monkeypatch, "tx12")
    monkeypatch.setattr(products, "photoshoot", lambda photo, link: [b"1", b"2"])
    bot.handle(photo_msg())
    bot.handle(press("p:shoot"))
    bot.poll_pending()
    bot.handle(press("orders"))
    assert "re:tx12" in buttons(bot)
    bot.handle(press("re:tx12", uid=8))  # someone else's order is not sent
    bot.handle(press("re:tx12"))
    assert bot.api.resent == [("album", ["a0", "a1"])]


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


def test_own_request_with_or_without_photo(bot, monkeypatch):
    made = []
    monkeypatch.setattr(products, "custom_picture", lambda photo, prompt, link: made.append((bool(photo), prompt)) or b"i")
    pay_with(monkeypatch, "tx13")
    say(bot, "/start")
    bot.handle(press("sec:custom"))
    assert {"p:custom", "p:customvid"} <= set(buttons(bot))
    bot.handle(press("p:custom"))
    say(bot, "голая девушка на пляже")
    assert "не делает" in bot.api.sent[-1][1]
    say(bot, "Рыжий кот в очках читает газету, акварель")
    assert "nophoto" in buttons(bot)
    bot.handle(press("nophoto"))
    bot.poll_pending()
    assert made == [(False, "Рыжий кот в очках читает газету, акварель")]

    pay_with(monkeypatch, "tx14")
    bot.handle(press("p:custom"))
    bot.handle({"message": {"chat": {"id": 7}, "from": {"id": 7}, "photo": [{"file_id": "me"}]}})  # photo first
    assert "вопрос выше" in bot.api.sent[-1][1]
    say(bot, "Сделай меня рыцарем")
    bot.poll_pending()
    assert made[-1] == (True, "Сделай меня рыцарем") and bot.state.orders["tx14"]["photo"] == "me"


def test_request_filter():
    assert products.allowed_request("Сделай меня рыцарем")
    assert not products.allowed_request("NSFW картинка")


def test_product_video_for_sellers(bot, monkeypatch):
    pay_with(monkeypatch, "tx20")
    made = []
    monkeypatch.setattr(products, "product_video", lambda photo, scene, workdir, link: made.append(scene) or workdir / "p.mp4")
    bot.handle(press("sec:fix"))
    assert buttons(bot)[0] == "p:pvideo"
    bot.handle(press("p:pvideo"))
    bot.handle(press("ps:studio"))
    assert "товар" in bot.api.sent[-1][1]
    bot.handle(photo_msg())
    assert bot.state.orders["tx20"]["amount"] == bot_settings.price_pvideo
    bot.poll_pending()
    assert made == ["studio"] and len(bot.api.videos) == 1
