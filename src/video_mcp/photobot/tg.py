"""The few Telegram Bot API calls the bot needs, over plain HTTP (long polling, no webhook)."""

from __future__ import annotations

import json
from pathlib import Path

import httpx

Button = tuple[str, str]  # (text, "callback data") or (text, "https://link")


def keyboard(rows: list[list[Button]]) -> str:
    return json.dumps({"inline_keyboard": [
        [{"text": text, "url": value} if value.startswith("http") else {"text": text, "callback_data": value}
         for text, value in row] for row in rows]})


class Api:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"
        self.files = f"https://api.telegram.org/file/bot{token}"

    def call(self, method: str, files: dict | None = None, timeout: float = 60, **params) -> dict:
        params = {k: v for k, v in params.items() if v is not None}
        resp = httpx.post(f"{self.base}/{method}", data=params if files else None,
                          json=None if files else params, files=files, timeout=timeout)
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram {method}: {data.get('description', resp.text[:200])}")
        return data["result"]

    def updates(self, offset: int, timeout: int = 50) -> list[dict]:
        resp = httpx.post(f"{self.base}/getUpdates", timeout=timeout + 15, json={
            "offset": offset, "timeout": timeout, "allowed_updates": ["message", "callback_query"]})
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram getUpdates: {data.get('description')}")
        return data["result"]

    def send(self, chat: int | str, text: str, rows: list[list[Button]] | None = None,
             reply_keys: list[str] | None = None) -> dict:
        """`rows` = buttons under the message; `reply_keys` = a permanent keyboard under the input field."""
        markup = keyboard(rows) if rows else None
        if reply_keys:
            markup = json.dumps({"keyboard": [[{"text": k}] for k in reply_keys], "resize_keyboard": True,
                                 "is_persistent": True})
        return self.call("sendMessage", chat_id=chat, text=text, parse_mode="HTML",
                         disable_web_page_preview=True, reply_markup=markup)

    def edit(self, chat: int | str, message_id: int, text: str, rows: list[list[Button]] | None = None) -> None:
        try:
            self.call("editMessageText", chat_id=chat, message_id=message_id, text=text, parse_mode="HTML",
                      disable_web_page_preview=True, reply_markup=keyboard(rows) if rows else None)
        except RuntimeError:
            pass  # "message is not modified" and similar are harmless

    def answer(self, callback_id: str, text: str = "") -> None:
        try:
            self.call("answerCallbackQuery", callback_query_id=callback_id, text=text or None)
        except (RuntimeError, httpx.HTTPError):
            pass

    def photo(self, chat: int | str, image: bytes, caption: str = "", rows: list[list[Button]] | None = None) -> str:
        """Returns the file_id of the sent photo (to reuse it without uploading again)."""
        msg = self.call("sendPhoto", chat_id=chat, caption=caption or None, parse_mode="HTML",
                        reply_markup=keyboard(rows) if rows else None,
                        files={"photo": ("photo.jpg", image, "image/jpeg")}, timeout=120)
        return (msg.get("photo") or [{}])[-1].get("file_id", "")

    def resend(self, chat: int | str, kind: str, ref: str | list[str]) -> None:
        """Send an earlier result again by its Telegram file_id (no upload)."""
        if kind == "album":
            self.call("sendMediaGroup", chat_id=chat, media=json.dumps([{"type": "photo", "media": f} for f in ref]))
        else:
            self.call("sendVideo" if kind == "video" else "sendPhoto", chat_id=chat, **{kind: ref})

    def album(self, chat: int | str, images: list[bytes], caption: str = "") -> list[str]:
        media = [{"type": "photo", "media": f"attach://p{i}",
                  **({"caption": caption, "parse_mode": "HTML"} if i == 0 and caption else {})}
                 for i in range(len(images))]
        files = {f"p{i}": (f"p{i}.jpg", img, "image/jpeg") for i, img in enumerate(images)}
        msgs = self.call("sendMediaGroup", chat_id=chat, media=json.dumps(media), files=files, timeout=180)
        return [(m.get("photo") or [{}])[-1].get("file_id", "") for m in msgs]

    def video(self, chat: int | str, path: Path, caption: str = "") -> str:
        with path.open("rb") as f:
            msg = self.call("sendVideo", chat_id=chat, caption=caption or None, parse_mode="HTML",
                            supports_streaming="true", files={"video": (path.name, f, "video/mp4")}, timeout=300)
        return (msg.get("video") or {}).get("file_id", "")

    def audio(self, chat: int | str, path: Path, title: str) -> None:
        with path.open("rb") as f:
            self.call("sendAudio", chat_id=chat, title=title, performer="Оживи фото",
                      files={"audio": (path.name, f, "audio/mpeg")}, timeout=120)

    def download(self, file_id: str) -> bytes:
        info = self.call("getFile", file_id=file_id)
        resp = httpx.get(f"{self.files}/{info['file_path']}", timeout=120)
        resp.raise_for_status()
        return resp.content
