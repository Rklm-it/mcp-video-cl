"""Dialogue, orders and payments of the photo bot.

A customer sends a photo, picks a product; the first card is free, the rest is paid through a Platega
link. A background loop polls pending payments; a paid order goes to a worker that makes the result
and sends it. A failed job gives the customer a free retry of the same product.
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

NAMES = {"animate": "🎬 Оживить фото", "card": "💌 Открытка", "shoot": "📸 Фотосессия (4 фото)",
         "greet": "🎁 Видео-поздравление", "moroz": "🎅 Видео от Деда Мороза"}
WAIT = {"animate": "3–5 минут", "card": "около минуты", "shoot": "1–2 минуты", "greet": "3–5 минут",
        "moroz": "3–5 минут"}
DOING = {"animate": "живое видео", "card": "открытку", "shoot": "фотосессию", "greet": "видео-поздравление",
         "moroz": "видео от Деда Мороза"}
NO_PHOTO = {"moroz"}
POLL_SECONDS = 10

TERMS = (
    "<b>Условия</b>\n\n"
    "Бот делает из вашего фото открытку, фотосессию или короткое «живое» видео с помощью нейросетей. "
    "Оплата — один раз за каждый заказ, через платёжный сервис Platega (СБП или карта). Подписок и "
    "автосписаний нет.\n\n"
    "Присылайте только свои фото или фото людей, которые согласны на обработку. Нельзя: чужие фото без "
    "согласия, обнажёнку, насилие, фото для обмана людей.\n\n"
    "Если нейросеть не справилась, бот предложит повторить бесплатно. Если и так не вышло — напишите "
    "владельцу бота, вернём деньги.\n\n"
    "Фото мы не храним: оно нужно только на время создания результата."
)


class State:
    """users: {id: {"free_card": bool, "credits": {product: n}, "photo": file_id}},
        orders: {id: {"user", "product", "draft" (occasion, name, voice, text…), "photo", "status", "amount", "created"}}."""

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
        self.link = f"t.me/{username}"
        self.pool = ThreadPoolExecutor(max_workers=bot_settings.workers)

    # ---- incoming updates ----

    def handle(self, update: dict) -> None:
        if "callback_query" in update:
            self.on_button(update["callback_query"])
        elif "message" in update:
            self.on_message(update["message"])

    def on_message(self, msg: dict) -> None:
        chat, uid = msg["chat"]["id"], msg["from"]["id"]
        text = (msg.get("text") or "").strip()
        file_id = ""
        if msg.get("photo"):
            file_id = msg["photo"][-1]["file_id"]
        elif (msg.get("document") or {}).get("mime_type", "").startswith("image/"):
            file_id = msg["document"]["file_id"]
        user = self.state.user(uid)
        if file_id:
            with self.state.lock:
                user["photo"] = file_id
                user.pop("await", None)
                user.pop("draft", None)
                self.state.save()
            self.menu(chat, uid)
        elif text.startswith("/start"):
            with self.state.lock:
                user.pop("await", None)
                user.pop("draft", None)
            self.api.send(chat, self.welcome(uid), self.moroz_button(uid))
        elif text.startswith("/terms"):
            self.api.send(chat, TERMS)
        elif text.startswith("/stats") and self.is_admin(uid):
            self.api.send(chat, self.stats())
        elif user.get("await") and text:
            self.on_answer(chat, msg["from"], user, text)
        else:
            self.api.send(chat, "Пришлите фото — лучше, где хорошо видно лицо. Дальше выберете, что сделать.")

    def on_button(self, cb: dict) -> None:
        chat, uid, data = cb["message"]["chat"]["id"], cb["from"]["id"], cb.get("data", "")
        self.api.answer(cb["id"])
        user = self.state.user(uid)
        if data.startswith("chk:"):
            self.check_now(chat, data[4:])
        elif data == "p:moroz" and self.moroz_button(uid):
            self.api.send(chat, "Кого поздравляет Дед Мороз?", [[("👦 Мальчика", "m:boy"), ("👧 Девочку", "m:girl")]])
        elif data in ("m:boy", "m:girl"):
            self.ask(chat, user, "name", {"product": "moroz", "gender": data[2:]})
        elif data == "v:demo":
            self.voice_demo(chat)
        elif data.startswith("v:") and data[2:] in products.VOICES and user.get("draft"):
            self.choose_text(chat, user, data[2:])
        elif data == "t:ready" and user.get("draft"):
            with self.state.lock:
                draft = user.pop("draft")
                user.pop("await", None)
            self.order(chat, cb["from"], draft["product"], draft)
        elif data == "t:own" and user.get("draft"):
            self.ask(chat, user, "text")
        elif not user.get("photo"):
            self.api.send(chat, "Сначала пришлите фото.")
        elif data in ("p:card", "p:greet"):
            prefix = data[2]  # c = card, g = greeting
            buttons = [(label, f"{prefix}:{key}") for key, (label, _, _) in products.OCCASIONS.items()]
            self.api.send(chat, "Какой повод?", [buttons[i:i + 2] for i in range(0, len(buttons), 2)])
        elif data.startswith("c:") and data[2:] in products.OCCASIONS:
            self.order(chat, cb["from"], "card", {"occasion": data[2:]})
        elif data.startswith("g:") and data[2:] in products.OCCASIONS:
            self.ask(chat, user, "name", {"product": "greet", "occasion": data[2:]})
        elif data in ("p:animate", "p:shoot"):
            self.order(chat, cb["from"], data[2:], {})

    # ---- greeting questions: name -> voice -> ready or own text ----

    def ask(self, chat: int, user: dict, what: str, draft: dict | None = None) -> None:
        with self.state.lock:
            if draft is not None:
                user["draft"] = draft
            user["await"] = what
            self.state.save()
        if what == "name":
            self.api.send(chat, "Как зовут того, кого поздравляем? Напишите имя, например: Маша")
        else:
            self.api.send(chat, f"Напишите своё поздравление одним сообщением, до {products.MAX_OWN_TEXT} "
                                "символов. Имя в начале добавлять не нужно — оно будет на экране.")

    def on_answer(self, chat: int, who: dict, user: dict, text: str) -> None:
        draft = user.get("draft") or {}
        if user["await"] == "name":
            name = products.clean_name(text)
            if not name:
                self.api.send(chat, "Напишите имя буквами, например: Маша")
                return
            with self.state.lock:
                draft["name"] = name
                user.pop("await")
                self.state.save()
            if draft.get("product") == "moroz":
                with self.state.lock:
                    user.pop("draft", None)
                self.order(chat, who, "moroz", draft)
            else:
                self.api.send(chat, "Каким голосом поздравить?", self.voice_buttons())
        else:
            own = products.clean_text(text)
            if not own:
                self.api.send(chat, "Напишите текст поздравления словами.")
                return
            with self.state.lock:
                draft["text"] = own
                user.pop("await")
                user.pop("draft", None)
            self.order(chat, who, draft["product"], draft)

    @staticmethod
    def voice_buttons() -> list[list[tuple[str, str]]]:
        buttons = [(label, f"v:{key}") for key, (label, *_) in products.VOICES.items()]
        return [buttons[i:i + 2] for i in range(0, len(buttons), 2)] + [[("🔊 Послушать голоса", "v:demo")]]

    def voice_demo(self, chat: int) -> None:
        self.api.send(chat, "Сейчас пришлю примеры, пару секунд…")
        for key, (label, *_) in products.VOICES.items():
            try:
                self.api.audio(chat, products.voice_sample(key, bot_settings.root / "voices"), label)
            except Exception:  # noqa: BLE001
                log.warning("voice sample %s failed", key, exc_info=True)
        self.api.send(chat, "Каким голосом поздравить?", self.voice_buttons())

    def choose_text(self, chat: int, user: dict, voice_key: str) -> None:
        with self.state.lock:
            user["draft"]["voice"] = voice_key
            self.state.save()
        draft = user["draft"]
        ready = products.GREETINGS[draft["occasion"]][0].format(name=draft["name"])
        self.api.send(chat, f"Готовое поздравление:\n\n<i>{ready}</i>\n\nОставить его или написать своё?",
                      [[("✅ Оставить", "t:ready")], [("✍️ Написать своё", "t:own")]])

    def is_admin(self, uid: int | str) -> bool:
        return bool(bot_settings.admin_id) and str(uid) == bot_settings.admin_id

    def moroz_button(self, uid: int) -> list | None:
        if bot_settings.moroz_open or self.is_admin(uid):
            return [[(f"{NAMES['moroz']} — {bot_settings.price_moroz} ₽", "p:moroz")]]
        return None

    # ---- texts ----

    def welcome(self, uid: int) -> str:
        free = self.state.user(uid).get("free_card")
        s = bot_settings
        moroz = (f"{NAMES['moroz']} — именное видео: Дед Мороз сам называет имя ребёнка и хвалит его. "
                 f"{s.price_moroz} ₽ (фото не нужно)\n") if self.moroz_button(uid) else ""
        return (
            "Привет! Я оживляю фото и делаю из них поздравления 📸✨\n\n"
            f"{NAMES['animate']} — старое или любимое фото начинает двигаться: моргает, улыбается. "
            f"{s.price_animate} ₽\n"
            f"{NAMES['greet']} — на любой повод: день рождения, свадьба, юбилей, Новый год, 8 Марта, "
            "23 Февраля и другие. Фото оживает, голос поздравляет по имени, можно свой текст. "
            f"{s.price_greet} ₽\n"
            f"{NAMES['card']} — вы на праздничной открытке с поздравлением. {s.price_card} ₽"
            + (" — <b>первая бесплатно</b>" if free else "") + "\n"
            f"{NAMES['shoot']} — студия, офис, осенний парк, вечерний город. {s.price_shoot} ₽\n"
            + moroz + "\n"
            "Пришлите фото, где хорошо видно лицо. Оплата по СБП или картой, без подписок.\n"
            "Условия: /terms"
        )

    def menu(self, chat: int, uid: int) -> None:
        s, user = bot_settings, self.state.user(uid)
        card = "бесплатно" if user.get("free_card") else f"{s.price_card} ₽"
        self.api.send(chat, "Фото получил. Что сделать?", [
            [(f"{NAMES['animate']} — {s.price_animate} ₽", "p:animate")],
            [(f"{NAMES['greet']} — {s.price_greet} ₽", "p:greet")],
            [(f"{NAMES['card']} — {card}", "p:card")],
            [(f"{NAMES['shoot']} — {s.price_shoot} ₽", "p:shoot")],
        ])

    def stats(self) -> str:
        orders = list(self.state.orders.values())
        paid = [o for o in orders if o.get("amount") and o["status"] in ("paid", "running", "done", "failed")]
        return (f"Пользователей: {len(self.state.data['users'])}\n"
                f"Заказов: {len(orders)}, оплачено: {len(paid)}\n"
                f"Выручка: {sum(o['amount'] for o in paid)} ₽\n"
                f"Бесплатных открыток: {sum(1 for o in orders if not o.get('amount') and o['status'] == 'done')}")

    # ---- orders ----

    def order(self, chat: int, who: dict, product: str, draft: dict) -> None:
        uid = who["id"]
        with self.state.lock:
            user = self.state.user(uid)
            order = {"user": uid, "chat": chat, "product": product, "draft": draft,
                     "photo": "" if product in NO_PHOTO else user["photo"],
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
        try:
            tx = platega.create(price, f"{NAMES[product]} — бот {self.link}", uid, who.get("username", ""),
                                payload=product, return_url=f"https://{self.link}")
        except Exception as exc:  # noqa: BLE001 - the customer needs an answer whatever broke
            log.exception("payment link failed")
            self.notify_admin(f"⚠️ Не создалась ссылка на оплату: {exc}")
            self.api.send(chat, "Не получилось создать оплату. Попробуйте через пару минут.")
            return
        with self.state.lock:
            order.update(status="pending", amount=price)
            self.state.orders[tx["transactionId"]] = order
            self.state.save()
        self.api.send(chat, f"{NAMES[product]} — <b>{price} ₽</b>\n\nОплатите по кнопке (СБП или карта). "
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
            self.notify_admin(f"💰 Оплата {order['amount']} ₽: {NAMES[order['product']]} (user {order['user']})")
            self.start(oid)
        elif order["status"] == "canceled":
            self.api.send(order["chat"], "Оплата не прошла. Можно попробовать ещё раз — выберите услугу заново.")

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
        self.api.send(chat, f"Принял, делаю {DOING[product]}. Это займёт {WAIT[product]}.")
        workdir = Path(tempfile.mkdtemp(prefix="photobot-"))
        try:
            photo = self.api.download(order["photo"]) if order["photo"] else b""
            caption = f"Готово! Ещё: {self.link}"
            d = order["draft"]
            if product == "card":
                self.api.photo(chat, products.card(photo, d["occasion"], self.link), caption)
            elif product == "shoot":
                self.api.album(chat, products.photoshoot(photo, self.link), caption)
            elif product == "greet":
                self.api.video(chat, products.greeting(photo, d["occasion"], d["name"], workdir, self.link,
                                                       d.get("voice", "f"), d.get("text", "")), caption)
            elif product == "moroz":
                self.api.video(chat, products.moroz(d["gender"], d["name"], workdir, self.link,
                                                    bot_settings.root / "ded-moroz.jpg"), caption)
            else:
                self.api.video(chat, products.animate(photo, workdir, self.link), caption)
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
            self.notify_admin(f"⚠️ Заказ не получился ({NAMES[product]}, user {order['user']}, "
                              f"{order['amount']} ₽): {str(exc)[:300]}")
            if product in NO_PHOTO:
                self.api.send(chat, "Не получилось сделать видео. Нажмите /start и закажите снова — "
                                    "повторю бесплатно.")
            else:
                self.api.send(chat, "Не получилось: нейросеть не приняла это фото. Пришлите другое фото "
                                    "(лицо крупно, без очень тёмного света) и выберите ту же услугу — "
                                    "повторю бесплатно.")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        with self.state.lock:
            order["status"] = status
            self.state.save()
        if status == "done":
            self.api.send(chat, "Понравилось? Пришлите ещё фото — или перешлите результат друзьям 🙂")

    def notify_admin(self, text: str) -> None:
        if bot_settings.admin_id:
            try:
                self.api.send(bot_settings.admin_id, text)
            except Exception:  # noqa: BLE001
                log.warning("admin notice failed", exc_info=True)


def _poller(bot: Bot, stop: threading.Event) -> None:
    while not stop.wait(POLL_SECONDS):
        try:
            bot.poll_pending()
        except Exception:  # noqa: BLE001
            log.exception("payment poll failed")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not bot_settings.token:
        raise SystemExit("Set PHOTO_BOT_TOKEN")
    api = Api(bot_settings.token)
    me = api.call("getMe")
    bot = Bot(api, State(bot_settings.root / "state.json"), me["username"])
    api.call("setMyCommands", commands=[{"command": "start", "description": "Что умеет бот и цены"},
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
