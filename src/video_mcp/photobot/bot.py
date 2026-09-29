"""Dialogue, orders and payments of the photo bot «Оживи фото».

The menu is a short list of sections; a section lists services; a service opens a card that says in plain words
what the customer gets, what to send, how long it takes and what it costs. «Начать» walks through the service's
steps (occasion, several reference photos, name, voice, text…), then a summary screen shows the order and the
price. The first card is free, the rest is paid through a Platega link; a background loop polls pending
payments and a worker makes the result. A failed job gives the customer a free retry of the same service.
Navigation edits one message instead of piling up new ones. State lives in /data/photobot/state.json (the
photos themselves are not stored, only Telegram file ids)."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from . import platega, products
from .config import bot_settings
from .tg import Api

log = logging.getLogger("video_mcp.photobot")


@dataclass(frozen=True)
class Service:
    title: str          # button and headings
    about: str          # the card: what the customer gets, in plain words
    steps: tuple        # what the bot asks, in order
    doing: str          # «делаю …»
    wait: str           # how long it takes
    ask: str = ""       # what photos to send
    min_refs: int = 1
    max_refs: int = 5
    ask2: str = ""      # the second set of photos (hug, baby)


SERVICES: dict[str, Service] = {
    "greet": Service(
        "🎥 Видео-поздравление",
        "Фото человека оживает на празднике: он улыбается, вокруг шарики, ёлка или цветы — под ваш повод. "
        "Голос поздравляет по имени, имя крупно на экране. Можно выбрать голос и написать свой текст.",
        ("occasion", "photos", "name", "voice", "text"), "видео-поздравление", "3–5 минут",
        ask="Пришлите фото того, кого поздравляем. <b>Лучше 2–5 фото</b> с разных сторон — так лицо получится "
            "точнее. Можно одним альбомом."),
    "char": Service(
        "🦸 Поздравление от персонажа",
        "Дракончик, фея, супергерой, пират или робот поздравляют по имени. Фото не нужно — идеально для детей.",
        ("character", "occasion", "name", "text"), "видео-поздравление", "3–5 минут"),
    "card": Service(
        "💌 Открытка с фото",
        "Праздничная открытка: человек с вашего фото в красивой обстановке и крупная надпись — «С днём рождения!», "
        "«Люблю тебя!» и другие.",
        ("occasion", "photos"), "открытку", "около минуты",
        ask="Пришлите фото того, кто будет на открытке. <b>Лучше 2–5 фото</b> — лицо получится точнее."),
    "moroz": Service(
        "🎅 Видео от Деда Мороза",
        "Дед Мороз сам называет имя ребёнка, хвалит его и обещает подарок. Фото не нужно.",
        ("gender", "name"), "видео от Деда Мороза", "3–5 минут"),
    "shoot": Service(
        "📸 Фотосессия: 4 фото",
        "Четыре профессиональных портрета из ваших селфи: студия, офис, осенний парк, вечерний город.",
        ("photos",), "фотосессию", "2–3 минуты",
        ask="Пришлите <b>3–6 своих фото</b>: лицо крупно, при хорошем свете, с разных сторон. Чем больше фото — "
            "тем больше похоже.", max_refs=8),
    "style": Service(
        "✨ Новый образ",
        "Вы — в 3D-мультфильме, аниме, на портрете маслом, в образе короля, космонавта, супергероя; фото на "
        "резюме; вы в старости или в детстве.",
        ("style", "photos"), "образ", "около минуты",
        ask="Пришлите <b>2–5 своих фото</b>, лицо крупно. Чем больше фото — тем больше похоже.", max_refs=8),
    "animate": Service(
        "🎬 Оживить фото",
        "Люди на фото начинают двигаться: моргают, улыбаются, камера плавно приближается. Особенно трогательно "
        "со старыми семейными снимками.",
        ("photos",), "живое видео", "3–5 минут",
        ask="Пришлите одно фото, которое нужно оживить.", max_refs=1),
    "hug": Service(
        "🤗 Обнять себя в детстве",
        "Видео, где вы сегодняшний обнимаете себя маленького. Нужны ваши фото сейчас и детские.",
        ("photos", "photos2"), "видео, где вы обнимаете себя маленького", "3–5 минут",
        ask="Пришлите <b>1–3 своих фото сейчас</b>, лицо крупно.",
        ask2="Теперь <b>1–3 ваших детских фото</b>. Бумажный снимок можно просто сфотографировать телефоном.",
        max_refs=3),
    "restore": Service(
        "🕰 Реставрация старого фото",
        "Уберём царапины, пятна и заломы, вернём чёткость и раскрасим в естественные цвета.",
        ("photos",), "реставрацию", "около минуты",
        ask="Пришлите старое фото. Бумажный снимок можно сфотографировать телефоном — ровно, без бликов.",
        max_refs=1),
    "enhance": Service(
        "🔍 Улучшить качество",
        "Размытое, тёмное или маленькое фото станет чётким и ярким. Всё остальное останется как было.",
        ("photos",), "улучшение фото", "около минуты",
        ask="Пришлите фото, которое нужно улучшить.", max_refs=1),
    "together": Service(
        "👨‍👩‍👧 Собрать всех на одном фото",
        "Соединим на одном снимке людей с разных фото — например, тех, кто так и не сфотографировался вместе.",
        ("photos",), "общее фото", "около минуты",
        ask="Пришлите <b>2–6 фото — на каждом один человек</b>, лицо крупно.", min_refs=2, max_refs=6),
    "baby": Service(
        "👶 Каким будет наш ребёнок",
        "Портрет вашего будущего малыша: нейросеть смешает черты мамы и папы.",
        ("photos", "photos2"), "портрет вашего будущего ребёнка", "около минуты",
        ask="Пришлите <b>1–3 фото мамы</b>, лицо крупно.", ask2="Теперь <b>1–3 фото папы</b>.", max_refs=3),
    "drawing": Service(
        "🖍 Детский рисунок → мультик",
        "Рисунок ребёнка превратится в яркую картинку из мультфильма — с теми же героями и цветами.",
        ("photos",), "мультик из рисунка", "около минуты",
        ask="Пришлите фото рисунка — сверху, ровно, при хорошем свете.", max_refs=1),
    "pvideo": Service(
        "🎬 Видео для карточки товара",
        "Видео 8 секунд для WB, Ozon или Авито: товар крутится в студии, стоит в интерьере или эффектно в свете. "
        "Товар остаётся точно таким, как на фото.",
        ("pscene", "photos"), "видео для карточки товара", "3–5 минут",
        ask="Пришлите <b>1–4 фото товара</b> с разных сторон: целиком, без рук и лишних предметов.", max_refs=4),
    "bg": Service(
        "🛍 Товар на новом фоне",
        "Поставим товар на белый фон для маркетплейса, в интерьер, на деревянный стол или на природу.",
        ("scene", "photos"), "фото с новым фоном", "около минуты",
        ask="Пришлите <b>1–3 фото товара</b>: целиком, без рук.", max_refs=3),
    "custom": Service(
        "🖼 Картинка по описанию",
        "Опишите словами, что хотите, — с вашими фото или без. Например: «сделай меня рыцарем у замка» или "
        "«рыжий кот в очках читает газету, акварель».",
        ("prompt", "photos"), "картинку по вашему описанию", "около минуты",
        ask="Пришлите фото, если запрос про вас (лучше 2–5 фото). Если фото не нужно — нажмите «Без фото».",
        min_refs=0, max_refs=6),
    "customvid": Service(
        "🎞 Видео по описанию",
        "Опишите, что должно происходить в видео, — с вашими фото или без. Например: «я еду на белом коне по "
        "полю» или «уютный домик в зимнем лесу, идёт снег».",
        ("prompt", "photos"), "видео по вашему описанию", "3–5 минут",
        ask="Пришлите фото, если видео про вас (лучше 2–5 фото). Если фото не нужно — нажмите «Без фото».",
        min_refs=0, max_refs=6),
}

# Menu sections: key -> (button, headline, services)
SECTIONS: dict[str, tuple[str, str, list[str]]] = {
    "greet": ("🎁 Поздравления", "Видео и открытки на любой праздник — с вашим фото или от сказочного персонажа.",
              ["greet", "char", "card", "moroz"]),
    "photo": ("📸 Фотосессии и образы", "Красивые портреты и новые образы из ваших обычных селфи.",
              ["shoot", "style"]),
    "live": ("🎬 Живые фото", "Фотографии, которые двигаются.", ["animate", "hug"]),
    "memory": ("🕰 Старые фото", "Вернуть старым снимкам чёткость и цвет, собрать родных вместе.",
               ["restore", "enhance", "together", "animate"]),
    "family": ("👨‍👩‍👧 Семья и дети", "Для мам, пап и бабушек.", ["baby", "drawing", "hug", "char"]),
    "sellers": ("🛍 Продавцам", "Видео и фото для карточек на WB, Ozon и Авито.", ["pvideo", "bg", "enhance"]),
    "idea": ("✍️ Своя идея", "Опишите словами — нейросеть сделает картинку или видео.", ["custom", "customvid"]),
}

PHOTO_STEPS = ("photos", "photos2")
TEXT_STEPS = ("name", "text", "prompt", "support")
PICK_STEPS = {  # step -> (question, callback prefix, options: key -> label, columns)
    "occasion": ("🎉 <b>Какой повод?</b>", "o", lambda: {k: v[0] for k, v in products.OCCASIONS.items()}, 2),
    "character": ("🦸 <b>Кто будет поздравлять?</b>", "h", lambda: {k: v[0] for k, v in products.CHARACTERS.items()}, 2),
    "style": ("✨ <b>Какой образ?</b>", "s", lambda: {k: v[0] for k, v in products.STYLES.items()}, 2),
    "pscene": ("🎬 <b>Какое видео нужно?</b>", "ps", lambda: {k: v[0] for k, v in products.PRODUCT_SCENES.items()}, 1),
    "scene": ("🛍 <b>Какой фон нужен?</b>", "b", lambda: {k: v[0] for k, v in products.BACKGROUNDS.items()}, 1),
    "gender": ("🎅 <b>Кого поздравляет Дед Мороз?</b>", "g", lambda: {"boy": "👦 Мальчика", "girl": "👧 Девочку"}, 2),
    "voice": ("🎙 <b>Каким голосом поздравить?</b>", "v", lambda: {k: v[0] for k, v in products.VOICES.items()}, 2),
}
PREFIX_STEP = {prefix: step for step, (_, prefix, _, _) in PICK_STEPS.items()}
PHOTO_FRESH_SECONDS = 15 * 60  # photos sent before choosing a service are used if this fresh
MENU_KEY = "🏠 Меню"
POLL_SECONDS = 10

WELCOME = (
    "👋 <b>Привет! Я «Оживи фото».</b>\n\n"
    "Делаю из обычных фото то, что хочется переслать близким:\n"
    "🎥 видео-поздравления с голосом и именем\n"
    "📸 фотосессии и новые образы\n"
    "🎬 живые фото — люди на снимке двигаются\n"
    "🕰 реставрацию старых семейных фото\n\n"
    "Как это работает: выберите, что сделать → пришлите фото → оплатите → через 1–5 минут результат придёт сюда.\n"
    "Оплата по СБП или картой, без подписок.{free}"
)
HELP = (
    "💬 <b>Помощь</b>\n\n"
    "<b>Как заказать</b>\n"
    "1. Нажмите «🏠 Меню» и выберите, что сделать.\n"
    "2. Бот задаст пару вопросов и попросит фото.\n"
    "3. Проверьте заказ и оплатите по СБП или картой.\n"
    "4. Через 1–5 минут результат придёт в этот чат.\n\n"
    "<b>Какие фото подходят</b>\n"
    "Лицо крупно, хороший свет, без тёмных очков. Несколько фото с разных сторон — лучше одного: лицо "
    "получится точнее. Можно отправить сразу альбомом.\n\n"
    "<b>Если не получилось</b> — бот сам предложит повторить бесплатно. Остались вопросы — напишите в поддержку.\n\n"
    "Условия: /terms"
)
TERMS = (
    "📄 <b>Условия</b>\n\n"
    "Бот делает из ваших фото открытки, образы, фотосессии, реставрацию и видео с помощью нейросетей. Оплата — "
    "один раз за каждый заказ, через платёжный сервис Platega (СБП или карта). Подписок и автосписаний нет.\n\n"
    "Присылайте только свои фото или фото людей, которые согласны на обработку. Нельзя: чужие фото без "
    "согласия, обнажёнку, насилие, фото и тексты для обмана людей.\n\n"
    "Если нейросеть не справилась, бот предложит повторить бесплатно. Если и так не вышло — напишите в "
    "поддержку, вернём деньги.\n\n"
    "Фото мы не храним: они нужны только на время работы."
)


def _grid(buttons: list[tuple[str, str]], per_row: int = 2) -> list[list[tuple[str, str]]]:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


class State:
    """users: {id: {"free_card", "credits", "loose": [file ids], "loose_at", "draft", "await", "ref", "screen"}},
    orders: {id: {"user", "chat", "product", "draft", "photos", "photos2", "status", "amount", "created",
    "kind", "result"}}."""

    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.data = {"users": {}, "orders": {}}
        if path.exists():
            self.data = json.loads(path.read_text())

    def save(self) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1))
            tmp.replace(self.path)

    def known(self, uid: int | str) -> bool:
        return str(uid) in self.data["users"]

    def user(self, uid: int | str) -> dict:
        with self.lock:
            return self.data["users"].setdefault(str(uid), {"free_card": True, "credits": {}})

    @property
    def orders(self) -> dict[str, dict]:
        return self.data["orders"]


class Bot:
    ack_delay = 1.5  # photos of one album arrive as separate messages: answer once, after the burst

    def __init__(self, api: Api, state: State, username: str):
        self.api = api
        self.state = state
        self.username = username
        self.link = f"t.me/{username}"
        self.pool = ThreadPoolExecutor(max_workers=bot_settings.workers)
        self._acks: dict[str, threading.Timer] = {}

    # ---- helpers ----

    def price(self, key: str) -> int:
        return bot_settings.price(key)

    def price_label(self, uid: int, key: str) -> str:
        if key == "card" and self.state.user(uid).get("free_card"):
            return "бесплатно"
        return f"{self.price(key)} ₽"

    def show(self, chat: int, mid: int | None, text: str, rows: list | None = None) -> None:
        """Navigation edits the message the button was pressed on; otherwise a new message."""
        if mid:
            try:
                self.api.edit(chat, mid, text, rows)
                return
            except Exception:  # noqa: BLE001 - fall back to a new message
                pass
        self.api.send(chat, text, rows)

    def is_admin(self, uid: int | str) -> bool:
        return bool(bot_settings.admin_id) and str(uid) == bot_settings.admin_id

    def visible(self, key: str) -> bool:
        return key != "moroz" or bot_settings.moroz_open

    # ---- incoming updates ----

    def handle(self, update: dict) -> None:
        if "callback_query" in update:
            self.on_button(update["callback_query"])
        elif "message" in update:
            self.on_message(update["message"])

    def on_message(self, msg: dict) -> None:
        chat, who = msg["chat"]["id"], msg["from"]
        uid = who["id"]
        text = (msg.get("text") or "").strip()
        file_id = ""
        if msg.get("photo"):
            file_id = msg["photo"][-1]["file_id"]
        elif (msg.get("document") or {}).get("mime_type", "").startswith("image/"):
            file_id = msg["document"]["file_id"]
        if text.startswith("/start"):
            self.on_start(chat, uid, text)
            return
        user = self.state.user(uid)
        if file_id:
            self.on_photo(chat, who, user, file_id)
        elif text in (MENU_KEY, "/menu", "📋 Меню"):
            self.reset(user)
            self.main_menu(chat, None)
        elif text.startswith("/help"):
            self.help(chat, None)
        elif text.startswith("/terms"):
            self.api.send(chat, TERMS)
        elif text.startswith("/stats") and self.is_admin(uid):
            self.api.send(chat, self.stats())
        elif user.get("await") in TEXT_STEPS and text:
            self.on_text(chat, who, user, text)
        elif user.get("await") in PHOTO_STEPS:
            self.api.send(chat, "📷 Жду фото — отправьте его как картинку (можно несколько сразу).")
        else:
            self.main_menu(chat, None, "Выберите, что сделать 👇")

    def on_start(self, chat: int, uid: int, text: str) -> None:
        new = not self.state.known(uid)
        user = self.state.user(uid)
        arg = text.split(maxsplit=1)[1] if " " in text else ""
        with self.state.lock:
            if new and arg.startswith("r") and arg[1:].isdigit() and arg[1:] != str(uid):
                user["ref"] = arg[1:]
            self.reset(user)
            self.state.save()
        free = "\n\n🎁 <b>Первая открытка — бесплатно.</b>" if user.get("free_card") else ""
        self.api.send(chat, WELCOME.format(free=free), reply_keys=[MENU_KEY])
        self.main_menu(chat, None)

    def on_button(self, cb: dict) -> None:
        chat, who, data = cb["message"]["chat"]["id"], cb["from"], cb.get("data", "")
        mid = cb["message"].get("message_id")
        uid = who["id"]
        self.api.answer(cb["id"])
        user = self.state.user(uid)
        draft = user.get("draft") or {}
        kind, _, value = data.partition(":")
        if data == "menu":
            self.reset(user)
            self.main_menu(chat, mid)
        elif kind == "sec" and value in SECTIONS:
            self.section(chat, mid, uid, value)
        elif kind == "svc" and value in SERVICES and self.visible(value):
            self.service_card(chat, mid, uid, value)
        elif kind == "go" and value in SERVICES and self.visible(value):
            self.begin(chat, who, user, value)
        elif data == "orders":
            self.my_orders(chat, mid, uid)
        elif kind == "re" and self.state.orders.get(value, {}).get("user") == uid:
            order = self.state.orders[value]
            self.api.resend(chat, order.get("kind", "photo"), order["result"])
        elif data == "help":
            self.help(chat, mid)
        elif data == "ref":
            self.referral(chat, mid, uid)
        elif data == "support":
            with self.state.lock:
                user["await"] = "support"
            self.api.send(chat, "✉️ Напишите вопрос одним сообщением — передам владельцу бота.")
        elif kind == "chk":
            self.check_now(chat, value)
        elif kind == "up" and self.state.orders.get(value, {}).get("kind") == "photo":
            with self.state.lock:
                user["draft"] = {"product": "animate", "photos": [self.state.orders[value]["result"]]}
                user.pop("await", None)
            self.summary(chat, None, user)
        elif not draft:
            self.main_menu(chat, mid, "Выберите, что сделать 👇")
        elif data == "pay":
            self.order(chat, who, user)
        elif data == "cancel":
            self.reset(user)
            self.main_menu(chat, mid, "Заказ отменён. Что сделаем? 👇")
        elif data == "edit":
            with self.state.lock:
                user["draft"] = {"product": draft["product"]}
            self.next_step(chat, who, user, mid)
        elif data == "done":
            self.photos_done(chat, who, user, mid)
        elif data == "redo":
            step = user.get("await")
            if step in PHOTO_STEPS:
                with self.state.lock:
                    draft[step] = []
                self.show(chat, mid, "Хорошо, пришлите фото заново 📷")
        elif data == "nophoto" and SERVICES[draft["product"]].min_refs == 0:
            self.answer(chat, who, user, "photos", [], mid)
        elif kind == "v" and value == "demo":
            self.voice_demo(chat)
        elif kind in PREFIX_STEP:
            step = PREFIX_STEP[kind]
            if value in PICK_STEPS[step][2]():
                self.answer(chat, who, user, step, value, mid)
        elif data == "t:ready":
            self.answer(chat, who, user, "text", "", mid)
        elif data == "t:own":
            with self.state.lock:
                user["await"] = "text"
            self.show(chat, mid, f"✍️ Напишите своё поздравление одним сообщением, до {products.MAX_OWN_TEXT} "
                                 "символов.\n\nИмя в начале писать не нужно — оно будет на экране.")

    # ---- screens ----

    def main_menu(self, chat: int, mid: int | None, text: str = "") -> None:
        buttons = [(title, f"sec:{key}") for key, (title, _, _) in SECTIONS.items()]
        rows = _grid(buttons[:6]) + [[buttons[6]]] + [
            [("📂 Мои работы", "orders"), ("🎁 Подарок другу", "ref")],
            [("💬 Помощь", "help")],
        ]
        self.show(chat, mid, text or "🏠 <b>Что сделаем?</b>\n\nВыберите раздел 👇", rows)

    def section(self, chat: int, mid: int | None, uid: int, key: str) -> None:
        title, headline, keys = SECTIONS[key]
        rows = [[(f"{SERVICES[k].title} · {self.price_label(uid, k)}", f"svc:{k}")] for k in keys if self.visible(k)]
        self.show(chat, mid, f"<b>{title}</b>\n\n{headline}", rows + [[("⬅️ Назад", "menu")]])

    def service_card(self, chat: int, mid: int | None, uid: int, key: str) -> None:
        s = SERVICES[key]
        needs = ("📷 Фото не нужно" if not any(st in PHOTO_STEPS for st in s.steps)
                 else "📷 Фото по желанию" if s.min_refs == 0
                 else "📷 Понадобится фото" if s.max_refs == 1 else "📷 Понадобятся фото (лучше несколько)")
        back = next((sec for sec, (_, _, keys) in SECTIONS.items() if key in keys), "")
        text = (f"<b>{s.title}</b>\n\n{s.about}\n\n"
                f"{needs}\n⏱ Готово за {s.wait}\n💳 Цена: <b>{self.price_label(uid, key)}</b>")
        self.show(chat, mid, text, [[("▶️ Начать", f"go:{key}")], [("⬅️ Назад", f"sec:{back}" if back else "menu")]])

    def help(self, chat: int, mid: int | None) -> None:
        self.show(chat, mid, HELP, [[("✉️ Написать в поддержку", "support")], [("⬅️ Меню", "menu")]])

    def my_orders(self, chat: int, mid: int | None, uid: int) -> None:
        done = [(oid, o) for oid, o in self.state.orders.items()
                if o.get("user") == uid and o["status"] == "done" and o.get("result")][-8:]
        if not done:
            self.show(chat, mid, "📂 Здесь появятся ваши готовые работы.", [[("⬅️ Меню", "menu")]])
            return
        rows = [[(f"{SERVICES[o['product']].title} · {time.strftime('%d.%m', time.localtime(o['created']))}",
                  f"re:{oid}")] for oid, o in reversed(done)]
        self.show(chat, mid, "📂 <b>Мои работы</b>\n\nНажмите, чтобы получить ещё раз:", rows + [[("⬅️ Меню", "menu")]])

    def referral(self, chat: int, mid: int | None, uid: int) -> None:
        link = f"https://t.me/{self.username}?start=r{uid}"
        self.show(chat, mid, "🎁 <b>Подарите другу открытку</b>\n\nОтправьте ему ссылку — первая открытка у друга "
                             "будет бесплатной. А когда он сделает первый заказ, бесплатная открытка придёт и вам.\n\n"
                             f"{link}",
                  [[("📤 Отправить другу", f"https://t.me/share/url?url={link}")], [("⬅️ Меню", "menu")]])

    # ---- the steps of a service ----

    def reset(self, user: dict) -> None:
        with self.state.lock:
            user.pop("draft", None)
            user.pop("await", None)

    def begin(self, chat: int, who: dict, user: dict, key: str) -> None:
        with self.state.lock:
            user["draft"] = {"product": key}
            user.pop("await", None)
            loose, fresh = user.get("loose") or [], time.time() - user.get("loose_at", 0) < PHOTO_FRESH_SECONDS
            s = SERVICES[key]
            if loose and fresh and "photos" in s.steps and "photos2" not in s.steps:
                user["draft"]["photos"] = loose[:s.max_refs]  # photos sent before choosing the service
            user.pop("loose", None)
        self.next_step(chat, who, user, None)

    def answer(self, chat: int, who: dict, user: dict, step: str, value, mid: int | None = None) -> None:
        with self.state.lock:
            user["draft"][step] = value
            user.pop("await", None)
            self.state.save()
        self.next_step(chat, who, user, mid)

    def next_step(self, chat: int, who: dict, user: dict, mid: int | None) -> None:
        draft = user["draft"]
        s = SERVICES[draft["product"]]
        for step in s.steps:
            if step in draft and not (step in PHOTO_STEPS and len(draft[step]) < s.min_refs):
                continue
            self.ask(chat, user, step, mid)
            return
        self.summary(chat, mid, user)

    def ask(self, chat: int, user: dict, step: str, mid: int | None) -> None:
        draft = user["draft"]
        s = SERVICES[draft["product"]]
        with self.state.lock:
            user["await"] = step
            if step in PHOTO_STEPS:
                draft.setdefault(step, [])
            self.state.save()
        cancel = [("✖️ Отменить", "cancel")]
        if step in PICK_STEPS:
            question, prefix, options, cols = PICK_STEPS[step]
            buttons = [(label, f"{prefix}:{key}") for key, label in options().items()]
            extra = [[("🔊 Послушать голоса", "v:demo")]] if step == "voice" else []
            self.show(chat, mid, question, _grid(buttons, cols) + extra + [cancel])
        elif step in PHOTO_STEPS:
            text = s.ask if step == "photos" else s.ask2
            rows = [[("🚫 Без фото", "nophoto")]] if s.min_refs == 0 else []
            self.show(chat, mid, f"📷 {text}\n\n<i>Когда пришлёте все фото — нажмите «Дальше».</i>", rows + [cancel])
        elif step == "name":
            self.show(chat, mid, "✏️ <b>Как зовут того, кого поздравляем?</b>\n\nНапишите имя, например: Маша",
                      [cancel])
        elif step == "prompt":
            self.show(chat, mid, "✍️ <b>Опишите, что хотите получить.</b> Чем подробнее — тем лучше.\n\n"
                                 "Например:\n• «Сделай меня рыцарем в доспехах на фоне замка»\n"
                                 "• «Уютный домик в зимнем лесу, вечер, горят окна»\n"
                                 "• «Я еду на белом коне по полю» (для видео)\n\n"
                                 "<i>Нельзя: обнажёнку, жестокость, реальных знаменитостей, чужие бренды "
                                 "и мультгероев.</i>", [cancel])
        elif step == "text":
            ready = products.GREETINGS[draft["occasion"]][0].format(name=draft["name"])
            self.show(chat, mid, f"💬 <b>Текст поздравления</b>\n\n<i>«{ready}»</i>\n\nОставить или написать своё?",
                      [[("✅ Оставить", "t:ready"), ("✍️ Своё", "t:own")], cancel])

    def on_photo(self, chat: int, who: dict, user: dict, file_id: str) -> None:
        step = user.get("await")
        with self.state.lock:
            if step in PHOTO_STEPS:
                s = SERVICES[user["draft"]["product"]]
                photos = user["draft"].setdefault(step, [])
                if len(photos) < s.max_refs:
                    photos.append(file_id)
            else:  # photos before a service is chosen: keep them for the service
                if time.time() - user.get("loose_at", 0) > PHOTO_FRESH_SECONDS:
                    user["loose"] = []
                user.setdefault("loose", []).append(file_id)
                user["loose"] = user["loose"][-8:]
                user["loose_at"] = time.time()
            self.state.save()
        self.schedule_ack(chat, who)

    def schedule_ack(self, chat: int, who: dict) -> None:
        key = str(who["id"])
        with self.state.lock:
            if key in self._acks:
                return
            if self.ack_delay <= 0:
                self._acks[key] = None  # type: ignore[assignment]
            else:
                timer = threading.Timer(self.ack_delay, self.ack_photos, args=(chat, who))
                self._acks[key] = timer
                timer.start()
                return
        self.ack_photos(chat, who)

    def ack_photos(self, chat: int, who: dict) -> None:
        with self.state.lock:
            self._acks.pop(str(who["id"]), None)
        user = self.state.user(who["id"])
        step = user.get("await")
        if step not in PHOTO_STEPS:
            count = len(user.get("loose") or [])
            self.main_menu(chat, None, f"📥 Получил фото: {count}. <b>Что с ними сделать?</b> 👇")
            return
        s = SERVICES[user["draft"]["product"]]
        count = len(user["draft"].get(step, []))
        if count >= s.max_refs:
            self.photos_done(chat, who, user, None)
            return
        more = f"Можно добавить ещё {s.max_refs - count}" if s.max_refs > 1 else ""
        self.api.send(chat, f"📥 Получил фото: <b>{count}</b>. {more}".strip(),
                      [[("➡️ Дальше", "done")], [("🔄 Заново", "redo"), ("✖️ Отменить", "cancel")]])

    def photos_done(self, chat: int, who: dict, user: dict, mid: int | None) -> None:
        step = user.get("await")
        if step not in PHOTO_STEPS:
            return
        s = SERVICES[user["draft"]["product"]]
        photos = user["draft"].get(step, [])
        need = max(1, s.min_refs)
        if len(photos) < need:
            self.api.send(chat, f"Нужно хотя бы {need} фото 📷")
            return
        self.answer(chat, who, user, step, photos, mid)

    def on_text(self, chat: int, who: dict, user: dict, text: str) -> None:
        what = user["await"]
        if what == "support":
            with self.state.lock:
                user.pop("await")
            name = f"@{who['username']}" if who.get("username") else who.get("first_name", "")
            self.notify_admin(f"✉️ Вопрос от {name} (id {who['id']}):\n\n{text[:1500]}")
            self.api.send(chat, "✅ Передал. Вам ответят в личные сообщения.", [[("⬅️ Меню", "menu")]])
        elif what == "prompt":
            prompt = " ".join(text.split())[:600]
            if len(prompt) < 5:
                self.api.send(chat, "Опишите чуть подробнее, что хотите получить 🙂")
            elif not products.allowed_request(prompt):
                self.api.send(chat, "🚫 Такое бот не делает. Опишите другой запрос.")
            else:
                self.answer(chat, who, user, "prompt", prompt)
        elif what == "name":
            name = products.clean_name(text)
            if not name:
                self.api.send(chat, "Напишите имя буквами, например: Маша")
                return
            self.answer(chat, who, user, "name", name)
        else:
            own = products.clean_text(text)
            if not own:
                self.api.send(chat, "Напишите текст поздравления словами.")
                return
            self.answer(chat, who, user, "text", own)

    def summary(self, chat: int, mid: int | None, user: dict) -> None:
        """The whole order on one screen before paying."""
        d = user["draft"]
        key = d["product"]
        lines = [f"🧾 <b>Проверьте заказ</b>\n", f"<b>{SERVICES[key].title}</b>"]
        labels = {
            "occasion": ("🎉 Повод", lambda v: products.OCCASIONS[v][0]),
            "character": ("🦸 Персонаж", lambda v: products.CHARACTERS[v][0]),
            "style": ("✨ Образ", lambda v: products.STYLES[v][0]),
            "pscene": ("🎬 Видео", lambda v: products.PRODUCT_SCENES[v][0]),
            "scene": ("🛍 Фон", lambda v: products.BACKGROUNDS[v][0]),
            "gender": ("👶 Кого", lambda v: {"boy": "мальчика", "girl": "девочку"}[v]),
            "name": ("✏️ Имя", str),
            "voice": ("🎙 Голос", lambda v: products.VOICES[v][0]),
        }
        for step, (label, fmt) in labels.items():
            if d.get(step):
                lines.append(f"{label}: {fmt(d[step])}")
        if "text" in d:
            lines.append("💬 Текст: " + (f"«{d['text']}»" if d["text"] else "готовый"))
        if d.get("prompt"):
            lines.append(f"✍️ Запрос: «{d['prompt']}»")
        for step in PHOTO_STEPS:
            if step in d:
                lines.append(f"📷 Фото: {len(d[step])}" if d[step] else "📷 Без фото")
        uid = int(next(k for k, v in self.state.data["users"].items() if v is user))
        free = self.is_admin(uid) or (key == "card" and user.get("free_card")) or user["credits"].get(key, 0) > 0
        price = "бесплатно 🎁" if free else f"{self.price(key)} ₽"
        lines.append(f"\n⏱ Готово за {SERVICES[key].wait}\n💳 Итого: <b>{price}</b>")
        with self.state.lock:
            user["await"] = "confirm"
        pay = "✅ Сделать бесплатно" if free else f"💳 Перейти к оплате · {self.price(key)} ₽"
        self.show(chat, mid, "\n".join(lines), [[(pay, "pay")], [("✏️ Изменить", "edit"), ("✖️ Отменить", "cancel")]])

    def voice_demo(self, chat: int) -> None:
        self.api.send(chat, "🔊 Сейчас пришлю примеры голосов…")
        for key, (label, *_) in products.VOICES.items():
            try:
                self.api.audio(chat, products.voice_sample(key, bot_settings.root / "voices"), label)
            except Exception:  # noqa: BLE001
                log.warning("voice sample %s failed", key, exc_info=True)
        question, prefix, options, cols = PICK_STEPS["voice"]
        buttons = [(label, f"{prefix}:{key}") for key, label in options().items()]
        self.api.send(chat, question, _grid(buttons, cols) + [[("✖️ Отменить", "cancel")]])

    # ---- admin ----

    def stats(self) -> str:
        orders = list(self.state.orders.values())
        paid = [o for o in orders if o.get("amount") and o["status"] in ("paid", "running", "done", "failed")]
        by_service: dict[str, int] = {}
        for o in paid:
            by_service[o["product"]] = by_service.get(o["product"], 0) + 1
        lines = "\n".join(f"  {SERVICES[k].title}: {n}" for k, n in sorted(by_service.items(), key=lambda x: -x[1]))
        return (f"Пользователей: {len(self.state.data['users'])}\n"
                f"Заказов: {len(orders)}, оплачено: {len(paid)}\n"
                f"Выручка: {sum(o['amount'] for o in paid)} ₽\n"
                f"Бесплатных: {sum(1 for o in orders if not o.get('amount') and o['status'] == 'done')}\n"
                + (f"По услугам:\n{lines}" if lines else ""))

    def notify_admin(self, text: str) -> None:
        if bot_settings.admin_id:
            try:
                self.api.send(bot_settings.admin_id, text)
            except Exception:  # noqa: BLE001
                log.warning("admin notice failed", exc_info=True)

    # ---- orders ----

    def order(self, chat: int, who: dict, user: dict) -> None:
        uid = who["id"]
        with self.state.lock:
            draft = user.pop("draft")
            user.pop("await", None)
            product = draft["product"]
            order = {"user": uid, "chat": chat, "product": product, "draft": draft,
                     "photos": draft.get("photos", []), "photos2": draft.get("photos2", []),
                     "status": "new", "amount": 0, "created": time.time()}
            if self.is_admin(uid):
                order["credit"] = True  # the owner tries everything for free
            elif product == "card" and user.get("free_card"):
                user["free_card"] = False
                order["free"] = True
            elif user["credits"].get(product, 0) > 0:
                user["credits"][product] -= 1
                order["credit"] = True
            if order.get("free") or order.get("credit"):
                oid = uuid.uuid4().hex
                order["status"] = "paid"
                self.state.orders[oid] = order
                self.state.save()
                self.start(oid)
                return
        price = self.price(product)
        title = SERVICES[product].title
        try:
            tx = platega.create(price, f"{title} — бот {self.link}", uid, who.get("username", ""),
                                payload=product, return_url=f"https://{self.link}")
        except Exception as exc:  # noqa: BLE001 - the customer needs an answer whatever broke
            log.exception("payment link failed")
            self.notify_admin(f"⚠️ Не создалась ссылка на оплату: {exc}")
            with self.state.lock:
                user["draft"] = draft
            self.api.send(chat, "😔 Не получилось создать оплату. Попробуйте через пару минут.",
                          [[("🔁 Попробовать снова", "pay")], [("⬅️ Меню", "menu")]])
            return
        with self.state.lock:
            order.update(status="pending", amount=price)
            self.state.orders[tx["transactionId"]] = order
            self.state.save()
        self.api.send(chat, f"💳 <b>{title} — {price} ₽</b>\n\nНажмите «Оплатить» и оплатите по СБП или картой. "
                            "Как только оплата пройдёт, я сам начну работу и пришлю результат сюда.",
                      [[(f"💳 Оплатить {price} ₽", tx["url"])], [("✅ Я оплатил", f"chk:{tx['transactionId']}")]])

    def check_now(self, chat: int, oid: str) -> None:
        order = self.state.orders.get(oid)
        if not order:
            return
        if order["status"] == "pending":
            self.poll_one(oid)
        if self.state.orders[oid]["status"] == "pending":
            self.api.send(chat, "⏳ Оплата пока не пришла. Обычно это до минуты — я проверю сам и начну.")

    def poll_one(self, oid: str) -> None:
        try:
            status = platega.status(oid)
        except Exception:  # noqa: BLE001
            log.warning("status check failed for %s", oid, exc_info=True)
            return
        with self.state.lock:
            order = self.state.orders[oid]
            if order["status"] != "pending":
                return
            if status == "CONFIRMED":
                order["status"] = "paid"
            elif status in ("CANCELED", "CHARGEBACKED"):
                order["status"] = "canceled"
            elif time.time() - order["created"] > bot_settings.payment_minutes * 60:
                order["status"] = "expired"
            else:
                return
            self.state.save()
        if order["status"] == "paid":
            self.notify_admin(f"💰 Оплата {order['amount']} ₽: {SERVICES[order['product']].title} "
                              f"(user {order['user']})")
            self.start(oid)
        elif order["status"] == "canceled":
            self.api.send(order["chat"], "Оплата не прошла. Можно попробовать ещё раз.", [[("⬅️ Меню", "menu")]])

    def poll_pending(self) -> None:
        for oid in [k for k, o in list(self.state.orders.items()) if o["status"] == "pending"]:
            self.poll_one(oid)

    def resume(self) -> None:
        """After a restart: finish paid orders that were not delivered."""
        for oid, order in list(self.state.orders.items()):
            if order["status"] in ("paid", "running"):
                self.start(oid)

    def start(self, oid: str) -> None:
        self.pool.submit(self.run, oid)

    def run(self, oid: str) -> None:
        order = self.state.orders[oid]
        with self.state.lock:
            order["status"] = "running"
            self.state.save()
        chat, product = order["chat"], order["product"]
        s = SERVICES[product]
        self.api.send(chat, f"✨ Принял! Делаю {s.doing}.\n⏱ Обычно это {s.wait} — пришлю сюда, как будет готово.")
        workdir = Path(tempfile.mkdtemp(prefix="photobot-"))
        try:
            refs = [self.api.download(f) for f in order.get("photos", [])]
            refs2 = [self.api.download(f) for f in order.get("photos2", [])]
            kind, result = products.make(product, order["draft"], refs, refs2, workdir, self.link,
                                         bot_settings.root / "cache")
            caption = f"✅ Готово! {s.title}\nЕщё: {self.link}"
            if kind == "photo":
                upsell = [[(f"🎬 Оживить это фото · {self.price('animate')} ₽", f"up:{oid}")],
                          [("🏠 Меню", "menu"), ("🎁 Подарок другу", "ref")]]
                order.update(kind="photo", result=self.api.photo(chat, result, caption, upsell))
            elif kind == "album":
                order.update(kind="album", result=self.api.album(chat, result, caption))
            else:
                order.update(kind="video", result=self.api.video(chat, result, caption))
            status = "done"
        except Exception as exc:  # noqa: BLE001
            log.exception("order %s failed", oid)
            status = "failed"
            with self.state.lock:
                user = self.state.user(order["user"])
                if order.get("free"):
                    user["free_card"] = True
                else:
                    user["credits"][product] = user["credits"].get(product, 0) + 1
            self.notify_admin(f"⚠️ Заказ не получился ({s.title}, user {order['user']}, "
                              f"{order['amount']} ₽): {str(exc)[:300]}")
            hint = ("Попробуйте другие фото — лицо крупно, при хорошем свете. " if order.get("photos") else "")
            self.api.send(chat, f"😔 Не получилось: нейросеть не справилась. {hint}Закажите «{s.title}» ещё раз — "
                                "это будет <b>бесплатно</b>.", [[("🔁 Повторить", f"svc:{product}")],
                                                                [("⬅️ Меню", "menu")]])
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        with self.state.lock:
            order["status"] = status
            self.state.save()
        if status == "done":
            self.reward_referrer(order["user"])
            if order.get("kind") != "photo":
                self.api.send(chat, "Понравилось? Перешлите близким 💛",
                              [[("🏠 Меню", "menu"), ("🎁 Подарок другу", "ref")]])

    def reward_referrer(self, uid: int | str) -> None:
        """The friend's first finished order gives the one who invited them a free card."""
        with self.state.lock:
            user = self.state.user(uid)
            ref = user.get("ref")
            if not ref or user.get("ref_paid") or not self.state.known(ref):
                return
            user["ref_paid"] = True
            inviter = self.state.user(ref)
            inviter["credits"]["card"] = inviter["credits"].get("card", 0) + 1
            self.state.save()
        try:
            self.api.send(int(ref), "🎁 Ваш друг сделал первый заказ — вам бесплатная открытка! Она в разделе "
                                    "«Поздравления».", [[("🏠 Меню", "menu")]])
        except Exception:  # noqa: BLE001
            log.warning("referral notice failed", exc_info=True)


def _poller(bot: Bot, stop: threading.Event) -> None:
    while not stop.wait(POLL_SECONDS):
        try:
            bot.poll_pending()
        except Exception:  # noqa: BLE001
            log.exception("payment poll failed")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its request lines carry the bot token in the URL
    if not bot_settings.token:
        raise SystemExit("Set PHOTO_BOT_TOKEN")
    api = Api(bot_settings.token)
    me = api.call("getMe")
    bot = Bot(api, State(bot_settings.root / "state.json"), me["username"])
    api.call("setMyCommands", commands=[{"command": "menu", "description": "🏠 Меню"},
                                        {"command": "help", "description": "💬 Как это работает"},
                                        {"command": "terms", "description": "📄 Условия и возврат"}])
    for method, field_name, value in (
        ("setMyShortDescription", "short_description",
         "Оживлю фото, сделаю видео-поздравление с именем, фотосессию и реставрацию старых снимков. "
         "Первая открытка бесплатно."),
        ("setMyDescription", "description",
         "🎥 Видео-поздравления с голосом и именем\n📸 Фотосессии и новые образы из селфи\n"
         "🎬 Живые фото — люди на снимке двигаются\n🕰 Реставрация старых фото\n🛍 Видео для карточек товаров\n\n"
         "Оплата по СБП или картой, без подписок. Первая открытка — бесплатно 🎁"),
    ):
        try:
            api.call(method, **{field_name: value})
        except Exception:  # noqa: BLE001
            log.warning("%s failed", method, exc_info=True)
    bot.resume()
    threading.Thread(target=_poller, args=(bot, threading.Event()), daemon=True).start()
    log.info("photo bot @%s started", me["username"])
    offset = 0
    while True:
        try:
            for update in api.updates(offset):
                offset = update["update_id"] + 1
                try:
                    bot.handle(update)
                except Exception:  # noqa: BLE001
                    log.exception("update failed")
        except Exception:  # noqa: BLE001
            log.warning("getUpdates failed, retrying", exc_info=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
