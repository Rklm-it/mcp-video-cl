"""Dialogue, orders and payments of the photo bot.

/start opens a menu of services. A service is a list of steps (occasion, photo, name, voice, text…); the bot
asks for whatever is still missing, then makes an order. The first card is free, the rest is paid through a
Platega link. A background loop polls pending payments; a paid order goes to a worker that makes the result
and sends it. A failed job gives the customer a free retry of the same service.
State lives in one JSON file under /data/photobot (the photos themselves are not stored)."""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import platega, products
from .config import bot_settings
from .tg import Api

log = logging.getLogger("video_mcp.photobot")

# key: (menu name, what the bot is making, how long it takes)
SERVICES: dict[str, tuple[str, str, str]] = {
    "greet": ("🎥 Видео-поздравление с вашим фото", "видео-поздравление", "3–5 минут"),
    "char": ("🦸 Видео-поздравление от персонажа", "видео-поздравление", "3–5 минут"),
    "card": ("💌 Открытка с вашим фото", "открытку", "около минуты"),
    "animate": ("🎬 Оживить фото", "живое видео", "3–5 минут"),
    "restore": ("🕰 Реставрация и цвет старого фото", "реставрацию", "около минуты"),
    "style": ("✨ Образ по фото", "образ", "около минуты"),
    "shoot": ("📸 Фотосессия (4 фото)", "фотосессию", "1–2 минуты"),
    "drawing": ("🖍 Рисунок ребёнка → мультик", "мультик из рисунка", "около минуты"),
    "enhance": ("🔍 Улучшить качество фото", "улучшение фото", "около минуты"),
    "bg": ("🛍 Новый фон / фото товара", "фото с новым фоном", "около минуты"),
    "together": ("👨‍👩‍👧 Соединить людей на одном фото", "общее фото", "около минуты"),
    "baby": ("👶 Каким будет наш ребёнок", "портрет вашего будущего ребёнка", "около минуты"),
    "hug": ("🤗 Обнять себя в детстве", "видео, где вы обнимаете себя маленького", "3–5 минут"),
    "custom": ("✍️ Картинка по вашему описанию", "картинку по вашему описанию", "около минуты"),
    "customvid": ("✍️ Видео по вашему описанию", "видео по вашему описанию", "3–5 минут"),
    "moroz": ("🎅 Видео от Деда Мороза", "видео от Деда Мороза", "3–5 минут"),
}
# What each service needs, in the order the bot asks
STEPS: dict[str, list[str]] = {
    "greet": ["occasion", "photo", "name", "voice", "text"],
    "char": ["character", "occasion", "name", "text"],
    "card": ["occasion", "photo"],
    "animate": ["photo"],
    "restore": ["photo"],
    "style": ["style", "photo"],
    "shoot": ["photo"],
    "drawing": ["photo"],
    "enhance": ["photo"],
    "bg": ["scene", "photo"],
    "together": ["photo", "photo2"],
    "baby": ["photo", "photo2"],
    "hug": ["photo", "photo2"],
    "custom": ["prompt", "photo"],
    "customvid": ["prompt", "photo"],
    "moroz": ["gender", "name"],
}
# Services that take two photos never reuse an earlier photo silently: the order of the two matters
TWO_PHOTOS = {k for k, steps in STEPS.items() if "photo2" in steps}
PHOTO2_ASK = {
    "together": ("Пришлите фото первого человека (лицо крупно).", "Теперь фото второго человека."),
    "baby": ("Пришлите фото мамы (лицо крупно, анфас).", "Теперь фото папы."),
    "hug": ("Пришлите ваше фото сейчас (лицо крупно).", "Теперь ваше детское фото — можно снять бумажный снимок "
                                                        "телефоном."),
}
PICTURES = {"card", "restore", "style", "drawing", "enhance", "bg", "together", "baby", "custom"}
OPTIONAL_PHOTO = {"custom", "customvid"}
PROMPT_TIPS = (
    "✍️ Опишите словами, что сделать — чем подробнее, тем лучше.\n\n"
    "<b>С вашим фото</b>, например:\n"
    "• «Сделай меня рыцарем в доспехах на фоне замка»\n"
    "• «Добавь на фото снег и новогодние огоньки»\n"
    "• «Пусть я еду на белом коне по полю» (для видео)\n\n"
    "<b>Без фото</b>, например:\n"
    "• «Рыжий кот в очках читает газету в кафе, акварель»\n"
    "• «Уютный домик в зимнем лесу, вечер, горят окна»\n\n"
    "Нельзя: обнажёнка, жестокость, реальные знаменитости и политики, чужие бренды и мультгерои."
)
# Menu sections: key -> (title, text, services)
SECTIONS: dict[str, tuple[str, str, list[str]]] = {
    "memory": ("🕰 Старые фото и память",
               "Верните старым фото чёткость и цвет, оживите их или соберите на одном фото людей, которые не "
               "успели сфотографироваться вместе.", ["restore", "animate", "together", "enhance"]),
    "looks": ("✨ Образы и фотосессии",
              "Вы — в 3D-мультфильме, аниме, на королевском портрете, в космосе, на фото для резюме; "
              "или сразу 4 фото в разных стилях.", ["style", "shoot"]),
    "family": ("👨‍👩‍👧 Семья и дети",
               "Обнять себя в детстве, увидеть вашего будущего ребёнка, превратить детский рисунок в мультик.",
               ["hug", "baby", "drawing", "together"]),
    "custom": ("✍️ Свой запрос",
               "Опишите словами, что хотите, — с вашим фото или без него. Нейросеть сделает картинку или видео.",
               ["custom", "customvid"]),
    "fix": ("🛠 Улучшить фото и фон",
            "Сделать размытое фото чётким. Поставить товар или человека на белый фон для Авито и маркетплейсов "
            "или в красивый интерьер.", ["enhance", "bg"]),
}
PHOTO_ASK = {
    "restore": "Пришлите старое фото. Можно просто сфотографировать бумажный снимок телефоном — ровно и без бликов.",
    "drawing": "Пришлите фото детского рисунка — сверху, ровно, при хорошем свете.",
    "shoot": "Пришлите фото, где хорошо видно лицо: лучше крупно, при дневном свете, без очков от солнца.",
}
PHOTO_FRESH_SECONDS = 15 * 60  # a photo sent this recently is used without asking again
MENU_KEY = "📋 Меню"
POLL_SECONDS = 10

HELP = (
    "<b>Как это работает</b>\n\n"
    "1. Выберите в меню, что сделать.\n"
    "2. Бот спросит всё нужное: повод, фото, имя.\n"
    "3. Оплатите по СБП или картой — без подписок, один раз за заказ.\n"
    "4. Через 1–5 минут результат придёт сюда.\n\n"
    "Можно и наоборот: просто пришлите фото, и бот предложит, что с ним сделать.\n\n"
    "Не получилось — бот повторит бесплатно. Вопросы — кнопка «Написать в поддержку».\n"
    "Условия: /terms"
)

TERMS = (
    "<b>Условия</b>\n\n"
    "Бот делает из ваших фото открытки, образы, фотосессии, реставрацию и видео-поздравления с помощью "
    "нейросетей. Оплата — один раз за каждый заказ, через платёжный сервис Platega (СБП или карта). Подписок и "
    "автосписаний нет.\n\n"
    "Присылайте только свои фото или фото людей, которые согласны на обработку. Нельзя: чужие фото без "
    "согласия, обнажёнку, насилие, фото и тексты для обмана людей.\n\n"
    "Если нейросеть не справилась, бот предложит повторить бесплатно. Если и так не вышло — напишите в "
    "поддержку, вернём деньги.\n\n"
    "Фото мы не храним: оно нужно только на время создания результата."
)


def _grid(buttons: list[tuple[str, str]], per_row: int = 2) -> list[list[tuple[str, str]]]:
    return [buttons[i:i + per_row] for i in range(0, len(buttons), per_row)]


class State:
    """users: {id: {"free_card", "credits": {service: n}, "photo", "photo_at", "draft", "await", "ref"}},
    orders: {id: {"user", "chat", "product", "draft", "photo", "status", "amount", "created", "result"}}."""

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
            return self.data["users"].setdefault(str(uid), {"free_card": True, "credits": {}, "photo": ""})

    @property
    def orders(self) -> dict[str, dict]:
        return self.data["orders"]


class Bot:
    def __init__(self, api: Api, state: State, username: str):
        self.api = api
        self.state = state
        self.username = username
        self.link = f"t.me/{username}"
        self.pool = ThreadPoolExecutor(max_workers=bot_settings.workers)

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
            draft = user.get("draft") or {}
            product = draft.get("product", "")
            with self.state.lock:
                user.update(photo=file_id, photo_at=time.time())
                waiting = user.get("await")
                if waiting in ("photo", "photo2"):
                    draft[waiting] = file_id
                    user.pop("await")
                elif draft and "photo" in STEPS[product] and "photo" not in draft and product not in TWO_PHOTOS:
                    draft["photo"] = file_id  # sent ahead of time, e.g. while the bot waits for a name
                    self.state.save()
                    self.api.send(chat, "Фото получил 👍 Теперь ответьте, пожалуйста, на вопрос выше.")
                    return
                self.state.save()
            if draft and waiting in ("photo", "photo2"):
                self.next_step(chat, who)
            else:
                self.main_menu(chat, "Фото получил 👍 Что с ним сделать?")
        elif text in (MENU_KEY, "/menu"):
            self.reset(user)
            self.main_menu(chat)
        elif text.startswith("/help"):
            self.api.send(chat, HELP, [[("✉️ Написать в поддержку", "support")], [(MENU_KEY, "menu")]])
        elif text.startswith("/terms"):
            self.api.send(chat, TERMS)
        elif text.startswith("/stats") and self.is_admin(uid):
            self.api.send(chat, self.stats())
        elif user.get("await") in ("name", "text", "support", "prompt") and text:
            self.on_answer(chat, who, user, text)
        elif user.get("await") in ("photo", "photo2"):
            self.api.send(chat, "Жду фото — пришлите его как картинку. Или откройте меню, чтобы выбрать другое.",
                          [[(MENU_KEY, "menu")]])
        else:
            self.main_menu(chat, "Выберите, что сделать 👇")

    def on_start(self, chat: int, uid: int, text: str) -> None:
        new = not self.state.known(uid)
        user = self.state.user(uid)
        arg = text.split(maxsplit=1)[1] if " " in text else ""
        with self.state.lock:
            if new and arg.startswith("r") and arg[1:].isdigit() and arg[1:] != str(uid):
                user["ref"] = arg[1:]
            self.reset(user)
            self.state.save()
        s = bot_settings
        free = " Первая открытка — бесплатно 🎁" if user.get("free_card") else ""
        self.api.send(chat, "Привет! Я делаю из фото поздравления, открытки, образы и живые видео 📸✨\n\n"
                            "Оплата по СБП или картой, без подписок. "
                            f"Цены от {min(s.price(k) for k in SERVICES)} ₽.{free}",
                      reply_keys=[MENU_KEY])
        self.main_menu(chat)

    def on_button(self, cb: dict) -> None:
        chat, who, data = cb["message"]["chat"]["id"], cb["from"], cb.get("data", "")
        uid = who["id"]
        self.api.answer(cb["id"])
        user = self.state.user(uid)
        draft = user.get("draft") or {}
        kind, _, value = data.partition(":")
        if data == "menu":
            self.reset(user)
            self.main_menu(chat)
        elif data == "sec:greet":
            self.greetings_menu(chat, uid)
        elif kind == "sec" and value in SECTIONS:
            self.section(chat, value)
        elif data == "orders":
            self.my_orders(chat, uid)
        elif kind == "re" and self.state.orders.get(value, {}).get("user") == uid:
            order = self.state.orders[value]
            self.api.resend(chat, order.get("kind", "photo"), order["result"])
        elif data == "help":
            self.api.send(chat, HELP, [[("✉️ Написать в поддержку", "support")], [(MENU_KEY, "menu")]])
        elif data == "ref":
            self.referral(chat, uid)
        elif data == "support":
            with self.state.lock:
                user["await"] = "support"
            self.api.send(chat, "Напишите вопрос одним сообщением — передам владельцу бота.")
        elif kind == "chk":
            self.check_now(chat, value)
        elif kind == "p" and value in SERVICES and (value != "moroz" or bot_settings.moroz_open):
            with self.state.lock:
                user["draft"] = {"product": value}
                user.pop("await", None)
            self.next_step(chat, who)
        elif kind == "up" and self.state.orders.get(value, {}).get("kind") == "photo":
            with self.state.lock:
                user["draft"] = {"product": "animate", "photo": self.state.orders[value]["result"]}
            self.next_step(chat, who)
        elif not draft:
            self.main_menu(chat, "Выберите, что сделать 👇")
        elif kind == "o" and value in products.OCCASIONS:
            self.answer(chat, who, user, "occasion", value)
        elif kind == "h" and value in products.CHARACTERS:
            self.answer(chat, who, user, "character", value)
        elif kind == "s" and value in products.STYLES:
            self.answer(chat, who, user, "style", value)
        elif kind == "b" and value in products.BACKGROUNDS:
            self.answer(chat, who, user, "scene", value)
        elif kind == "m" and value in ("boy", "girl"):
            self.answer(chat, who, user, "gender", value)
        elif kind == "v" and value == "demo":
            self.voice_demo(chat)
        elif kind == "v" and value in products.VOICES:
            self.answer(chat, who, user, "voice", value)
        elif data == "nophoto" and draft.get("product") in OPTIONAL_PHOTO:
            self.answer(chat, who, user, "photo", "")
        elif data == "t:ready":
            self.answer(chat, who, user, "text", "")
        elif data == "t:own":
            with self.state.lock:
                user["await"] = "text"
            self.api.send(chat, f"Напишите своё поздравление одним сообщением, до {products.MAX_OWN_TEXT} "
                                "символов. Имя в начале добавлять не нужно — оно будет на экране.")

    # ---- menus ----

    def main_menu(self, chat: int, text: str = "Что сделаем? 👇") -> None:
        s = bot_settings
        rows = [
            [("🎁 Поздравления", "sec:greet")],
            [(f"🎬 Оживить фото · {s.price_animate} ₽", "p:animate")],
            *[[(title, f"sec:{key}")] for key, (title, _, _) in SECTIONS.items()],
            [("✍️ Свой запрос: картинка или видео", "sec:custom")],
            [("📂 Мои заказы", "orders"), ("👥 Пригласить друга", "ref")],
            [("❓ Помощь", "help")],
        ]
        self.api.send(chat, text, rows)

    def section(self, chat: int, key: str) -> None:
        title, text, services = SECTIONS[key]
        rows = [[(f"{SERVICES[k][0]} · {bot_settings.price(k)} ₽", f"p:{k}")] for k in services]
        self.api.send(chat, f"<b>{title}</b>\n\n{text}", rows + [[("⬅️ Назад", "menu")]])

    def my_orders(self, chat: int, uid: int) -> None:
        done = [(oid, o) for oid, o in self.state.orders.items()
                if o.get("user") == uid and o["status"] == "done" and o.get("result")][-8:]
        if not done:
            self.api.send(chat, "Готовых заказов пока нет.", [[(MENU_KEY, "menu")]])
            return
        rows = [[(f"{SERVICES[o['product']][0]} · {time.strftime('%d.%m', time.localtime(o['created']))}",
                  f"re:{oid}")] for oid, o in reversed(done)]
        self.api.send(chat, "📂 Ваши последние заказы — нажмите, чтобы получить ещё раз:", rows + [[(MENU_KEY, "menu")]])

    def greetings_menu(self, chat: int, uid: int) -> None:
        s = bot_settings
        card = "бесплатно" if self.state.user(uid).get("free_card") else f"{s.price_card} ₽"
        rows = [
            [(f"🎥 Видео с вашим фото · {s.price_greet} ₽", "p:greet")],
            [(f"🦸 Видео от персонажа, без фото · {s.price_char} ₽", "p:char")],
            [(f"💌 Открытка с вашим фото · {card}", "p:card")],
        ]
        if bot_settings.moroz_open:
            rows.append([(f"🎅 Видео от Деда Мороза · {s.price_moroz} ₽", "p:moroz")])
        rows.append([("⬅️ Назад", "menu")])
        self.api.send(chat, "🎁 <b>Поздравления</b> — на день рождения, свадьбу, юбилей, Новый год, 8 Марта, "
                            "23 Февраля и любой другой повод.\n\n"
                            "🎥 Ваше фото оживает на празднике, голос поздравляет по имени, имя на экране.\n"
                            "🦸 Дракончик, фея, супергерой или пират поздравляют по имени — фото не нужно.\n"
                            "💌 Вы на праздничной открытке с надписью.", rows)

    def referral(self, chat: int, uid: int) -> None:
        link = f"https://t.me/{self.username}?start=r{uid}"
        self.api.send(chat, "👥 <b>Пригласите друга</b>\n\nОтправьте ему эту ссылку. Друг получит бесплатную "
                            "открытку, а когда он сделает первый заказ — бесплатная открытка придёт и вам.\n\n"
                            f"{link}", [[("📤 Поделиться", f"https://t.me/share/url?url={link}")], [(MENU_KEY, "menu")]])

    # ---- the steps of a service ----

    def reset(self, user: dict) -> None:
        with self.state.lock:
            user.pop("draft", None)
            user.pop("await", None)

    def answer(self, chat: int, who: dict, user: dict, step: str, value: str) -> None:
        with self.state.lock:
            user["draft"][step] = value
            user.pop("await", None)
            self.state.save()
        self.next_step(chat, who)

    def next_step(self, chat: int, who: dict) -> None:
        user = self.state.user(who["id"])
        draft = user["draft"]
        product = draft["product"]
        for step in STEPS[product]:
            if step in draft:
                continue
            if (step == "photo" and product not in TWO_PHOTOS and user.get("photo")
                    and time.time() - user.get("photo_at", 0) < PHOTO_FRESH_SECONDS):
                draft["photo"] = user["photo"]
                continue
            self.ask(chat, user, product, step)
            return
        with self.state.lock:
            user.pop("draft", None)
            self.state.save()
        self.order(chat, who, product, draft)

    def ask(self, chat: int, user: dict, product: str, step: str) -> None:
        if step in ("photo", "photo2", "name", "prompt"):
            with self.state.lock:
                user["await"] = step
                self.state.save()
        back = [("⬅️ Меню", "menu")]
        if step == "occasion":
            buttons = [(label, f"o:{key}") for key, (label, _, _) in products.OCCASIONS.items()]
            self.api.send(chat, "Какой повод?", _grid(buttons) + [back])
        elif step == "character":
            buttons = [(label, f"h:{key}") for key, (label, _, _) in products.CHARACTERS.items()]
            self.api.send(chat, "Кто будет поздравлять?", _grid(buttons) + [back])
        elif step == "style":
            buttons = [(label, f"s:{key}") for key, (label, _) in products.STYLES.items()]
            self.api.send(chat, "Какой образ?", _grid(buttons) + [back])
        elif step == "scene":
            buttons = [(label, f"b:{key}") for key, (label, _) in products.BACKGROUNDS.items()]
            self.api.send(chat, "Какой фон нужен?", [[b] for b in buttons] + [back])
        elif step == "gender":
            self.api.send(chat, "Кого поздравляет Дед Мороз?", [[("👦 Мальчика", "m:boy"), ("👧 Девочку", "m:girl")]])
        elif step == "prompt":
            self.api.send(chat, PROMPT_TIPS, [back])
        elif step == "photo" and product in OPTIONAL_PHOTO:
            self.api.send(chat, "Пришлите фото, если запрос про него. Если фото не нужно — нажмите кнопку.",
                          [[("🚫 Без фото", "nophoto")], back])
        elif step in ("photo", "photo2") and product in PHOTO2_ASK:
            self.api.send(chat, PHOTO2_ASK[product][step == "photo2"], [back])
        elif step == "photo":
            self.api.send(chat, PHOTO_ASK.get(product, "Пришлите фото, где хорошо видно лицо."), [back])
        elif step == "name":
            self.api.send(chat, "Как зовут того, кого поздравляем? Напишите имя, например: Маша")
        elif step == "voice":
            self.api.send(chat, "Каким голосом поздравить?", self.voice_buttons())
        elif step == "text":
            draft = user["draft"]
            ready = products.GREETINGS[draft["occasion"]][0].format(name=draft["name"])
            self.api.send(chat, f"Готовое поздравление:\n\n<i>{ready}</i>\n\nОставить его или написать своё?",
                          [[("✅ Оставить", "t:ready")], [("✍️ Написать своё", "t:own")]])

    def on_answer(self, chat: int, who: dict, user: dict, text: str) -> None:
        what = user["await"]
        if what == "support":
            with self.state.lock:
                user.pop("await")
            name = f"@{who['username']}" if who.get("username") else who.get("first_name", "")
            self.notify_admin(f"✉️ Вопрос от {name} (id {who['id']}):\n\n{text[:1500]}")
            self.api.send(chat, "Передал, вам ответят в личные сообщения. Спасибо!", [[(MENU_KEY, "menu")]])
        elif what == "prompt":
            prompt = " ".join(text.split())[:600]
            if len(prompt) < 5:
                self.api.send(chat, "Опишите чуть подробнее, что хотите получить.")
            elif not products.allowed_request(prompt):
                self.api.send(chat, "Такое бот не делает. Опишите другой запрос.")
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

    @staticmethod
    def voice_buttons() -> list[list[tuple[str, str]]]:
        buttons = [(label, f"v:{key}") for key, (label, *_) in products.VOICES.items()]
        return _grid(buttons) + [[("🔊 Послушать голоса", "v:demo")]]

    def voice_demo(self, chat: int) -> None:
        self.api.send(chat, "Сейчас пришлю примеры, пару секунд…")
        for key, (label, *_) in products.VOICES.items():
            try:
                self.api.audio(chat, products.voice_sample(key, bot_settings.root / "voices"), label)
            except Exception:  # noqa: BLE001
                log.warning("voice sample %s failed", key, exc_info=True)
        self.api.send(chat, "Каким голосом поздравить?", self.voice_buttons())

    # ---- admin ----

    def is_admin(self, uid: int | str) -> bool:
        return bool(bot_settings.admin_id) and str(uid) == bot_settings.admin_id

    def stats(self) -> str:
        orders = list(self.state.orders.values())
        paid = [o for o in orders if o.get("amount") and o["status"] in ("paid", "running", "done", "failed")]
        by_service: dict[str, int] = {}
        for o in paid:
            by_service[o["product"]] = by_service.get(o["product"], 0) + 1
        lines = "\n".join(f"  {SERVICES[k][0]}: {n}" for k, n in sorted(by_service.items(), key=lambda x: -x[1]))
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

    def order(self, chat: int, who: dict, product: str, draft: dict) -> None:
        uid = who["id"]
        with self.state.lock:
            user = self.state.user(uid)
            order = {"user": uid, "chat": chat, "product": product, "draft": draft, "photo": draft.get("photo", ""),
                     "photo2": draft.get("photo2", ""),
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
        price = bot_settings.price(product)
        name = SERVICES[product][0]
        try:
            tx = platega.create(price, f"{name} — бот {self.link}", uid, who.get("username", ""),
                                payload=product, return_url=f"https://{self.link}")
        except Exception as exc:  # noqa: BLE001 - the customer needs an answer whatever broke
            log.exception("payment link failed")
            self.notify_admin(f"⚠️ Не создалась ссылка на оплату: {exc}")
            self.api.send(chat, "Не получилось создать оплату. Попробуйте через пару минут.", [[(MENU_KEY, "menu")]])
            return
        with self.state.lock:
            order.update(status="pending", amount=price)
            self.state.orders[tx["transactionId"]] = order
            self.state.save()
        self.api.send(chat, f"{name} — <b>{price} ₽</b>\n\nОплатите по кнопке (СБП или карта). "
                            "Как только оплата пройдёт, я сам начну работу и пришлю результат сюда.",
                      [[(f"💳 Оплатить {price} ₽", tx["url"])], [("✅ Я оплатил", f"chk:{tx['transactionId']}")]])

    def check_now(self, chat: int, oid: str) -> None:
        order = self.state.orders.get(oid)
        if not order:
            return
        if order["status"] == "pending":
            self.poll_one(oid)
        if self.state.orders[oid]["status"] == "pending":
            self.api.send(chat, "Оплата пока не пришла. Обычно это занимает до минуты — я проверю сам и начну.")

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
            self.notify_admin(f"💰 Оплата {order['amount']} ₽: {SERVICES[order['product']][0]} (user {order['user']})")
            self.start(oid)
        elif order["status"] == "canceled":
            self.api.send(order["chat"], "Оплата не прошла. Можно попробовать ещё раз.", [[(MENU_KEY, "menu")]])

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
        _, doing, wait = SERVICES[product]
        self.api.send(chat, f"Принял, делаю {doing}. Это займёт {wait}.")
        workdir = Path(tempfile.mkdtemp(prefix="photobot-"))
        cache = bot_settings.root / "cache"
        try:
            photo = self.api.download(order["photo"]) if order["photo"] else b""
            photo2 = self.api.download(order["photo2"]) if order.get("photo2") else b""
            caption = f"Готово! Ещё: {self.link}"
            d = order["draft"]
            upsell = [[(f"🎬 Оживить это фото · {bot_settings.price_animate} ₽", f"up:{oid}")], [(MENU_KEY, "menu")]]
            if product in PICTURES:
                picture = {
                    "card": lambda: products.card(photo, d["occasion"], self.link),
                    "restore": lambda: products.restore(photo, self.link),
                    "style": lambda: products.style(photo, d["style"], self.link),
                    "drawing": lambda: products.drawing(photo, self.link),
                    "enhance": lambda: products.enhance(photo, self.link),
                    "bg": lambda: products.background(photo, d["scene"], self.link),
                    "together": lambda: products.together(photo, photo2, self.link),
                    "baby": lambda: products.baby(photo, photo2, self.link),
                    "custom": lambda: products.custom_picture(photo, d["prompt"], self.link),
                }[product]()
                order.update(kind="photo", result=self.api.photo(chat, picture, caption, upsell))
            elif product == "shoot":
                order.update(kind="album", result=self.api.album(chat, products.photoshoot(photo, self.link), caption))
            else:
                video = {
                    "greet": lambda: products.greeting(photo, d["occasion"], d["name"], workdir, self.link,
                                                       d.get("voice", "f"), d.get("text", "")),
                    "char": lambda: products.character_greeting(d["character"], d["occasion"], d["name"],
                                                                d.get("text", ""), workdir, self.link, cache),
                    "moroz": lambda: products.moroz(d["gender"], d["name"], workdir, self.link,
                                                    cache / "ded-moroz.jpg"),
                    "hug": lambda: products.hug(photo, photo2, workdir, self.link),
                    "customvid": lambda: products.custom_video(photo, d["prompt"], workdir, self.link),
                    "animate": lambda: products.animate(photo, workdir, self.link),
                }[product]()
                order.update(kind="video", result=self.api.video(chat, video, caption))
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
            self.notify_admin(f"⚠️ Заказ не получился ({SERVICES[product][0]}, user {order['user']}, "
                              f"{order['amount']} ₽): {str(exc)[:300]}")
            if "photo" in STEPS[product]:
                self.api.send(chat, "Не получилось: нейросеть не приняла это фото. Пришлите другое фото "
                                    "(лицо крупно, без очень тёмного света) и выберите ту же услугу — "
                                    "повторю бесплатно.", [[(MENU_KEY, "menu")]])
            else:
                self.api.send(chat, "Не получилось сделать видео. Закажите снова — повторю бесплатно.",
                              [[(MENU_KEY, "menu")]])
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        with self.state.lock:
            order["status"] = status
            self.state.save()
        if status == "done":
            self.reward_referrer(order["user"])
            if order.get("kind") != "photo":
                self.api.send(chat, "Понравилось? Перешлите друзьям 🙂 Или сделайте что-нибудь ещё:",
                              [[(MENU_KEY, "menu")], [("👥 Пригласить друга", "ref")]])

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
            self.api.send(int(ref), "🎁 Ваш друг сделал первый заказ — вам бесплатная открытка! Выберите её в "
                                    "меню «Поздравления».", [[(MENU_KEY, "menu")]])
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
    api.call("setMyCommands", commands=[{"command": "menu", "description": "Меню"},
                                        {"command": "help", "description": "Как это работает"},
                                        {"command": "terms", "description": "Условия и возврат"}])
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
