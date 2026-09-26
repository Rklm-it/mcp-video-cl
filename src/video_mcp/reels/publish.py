"""Uploading finished reels: Telegram channel, YouTube Shorts. Plus the Telegram review bot."""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

import httpx

from . import jobs
from .config import reels_settings

log = logging.getLogger("video_mcp.reels")


class PublishError(Exception):
    pass


def caption(job: dict, offer: dict | None, limit: int) -> str:
    """Post text: ad marking first (required when the reel carries an ad), then title and text."""
    parts = []
    if offer:
        parts.append(jobs.ad_marker(offer))
    parts.append(job["title"])
    if job.get("description"):
        parts.append(job["description"])
    if offer and offer.get("link"):
        parts.append(f"{offer.get('link_text') or 'Ссылка'}: {offer['link']}")
    tags = " ".join(f"#{t.lstrip('#')}" for t in job.get("hashtags", []) if t.strip("# "))
    if tags:
        parts.append(tags)
    text = "\n\n".join(parts)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def publish(job_id: str, targets: list[str] | None = None) -> dict:
    """Publish a rendered reel to the given (or all configured) targets. Safe to repeat:
    targets that already succeeded are skipped."""
    with jobs.lock(job_id):
        job = jobs.load(job_id)
        if job["status"] not in ("ready", "published"):
            raise PublishError(f"Reel {job_id} is {job['status']}, only ready reels can be published")
        video = jobs.job_dir(job_id) / "reel.mp4"
        if not video.is_file():
            raise PublishError(f"Reel {job_id} has no video file")
        offer = jobs.get_offer(job.get("offer_id"))
        wanted = targets or reels_settings.publish_targets()
        if not wanted:
            raise PublishError("No publish targets configured (REELS_TG_* or REELS_YT_* in .env)")
        done = job.setdefault("published", {})
        errors = {}
        for target in wanted:
            if target in done:
                continue
            try:
                if target == "telegram":
                    done[target] = _telegram_post(video, caption(job, offer, 1024))
                elif target == "youtube":
                    done[target] = _youtube_upload(video, job, offer)
                else:
                    raise PublishError(f"Unknown target {target!r} (telegram, youtube)")
            except Exception as exc:  # keep going with the other targets
                log.warning("Publishing %s to %s failed: %s", job_id, target, exc)
                errors[target] = str(exc)[:300]
        if done:
            job["status"] = "published"
        job["publish_errors"] = errors
        jobs.save(job)
        return {"published": done, "errors": errors}


# ---------------------------------------------------------------- Telegram


def _tg(method: str, **kwargs) -> dict:
    resp = httpx.post(f"https://api.telegram.org/bot{reels_settings.tg_token}/{method}", timeout=300, **kwargs)
    data = resp.json()
    if not data.get("ok"):
        raise PublishError(f"Telegram {method}: {data.get('description', resp.text[:200])}")
    return data["result"]


def _send_video(chat: str, video: Path, text: str, markup: dict | None = None) -> dict:
    data = {"chat_id": chat, "caption": text, "supports_streaming": "true"}
    if markup:
        data["reply_markup"] = json.dumps(markup)
    with video.open("rb") as f:
        return _tg("sendVideo", data=data, files={"video": ("reel.mp4", f, "video/mp4")})


def _telegram_post(video: Path, text: str) -> str:
    msg = _send_video(reels_settings.tg_channel, video, text)
    chat = msg.get("chat", {})
    if chat.get("username"):
        return f"https://t.me/{chat['username']}/{msg['message_id']}"
    return f"telegram message {msg['message_id']}"


# ---------------------------------------------------------------- YouTube


def _youtube_token() -> str:
    s = reels_settings
    resp = httpx.post("https://oauth2.googleapis.com/token", data={
        "client_id": s.yt_client_id, "client_secret": s.yt_client_secret,
        "refresh_token": s.yt_refresh_token, "grant_type": "refresh_token",
    }, timeout=30)
    if resp.status_code >= 400:
        raise PublishError(f"YouTube auth failed: {resp.text[:300]}")
    return resp.json()["access_token"]


def _youtube_upload(video: Path, job: dict, offer: dict | None) -> str:
    token = _youtube_token()
    tags = [t.lstrip("#") for t in job.get("hashtags", []) if t.strip("# ")]
    meta = {
        "snippet": {
            "title": job["title"][:100],
            "description": caption(job, offer, 4900) + "\n\n#shorts",
            "tags": tags[:15],
            "categoryId": "22",
            "defaultLanguage": "ru",
        },
        "status": {
            "privacyStatus": reels_settings.yt_privacy,
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,  # AI-generated pictures and voice must be disclosed
        },
    }
    size = video.stat().st_size
    init = httpx.post(
        "https://www.googleapis.com/upload/youtube/v3/videos",
        params={"uploadType": "resumable", "part": "snippet,status"},
        headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": "video/mp4",
                 "X-Upload-Content-Length": str(size)},
        json=meta, timeout=60,
    )
    if init.status_code >= 400:
        raise PublishError(f"YouTube upload init failed: {init.text[:300]}")
    with video.open("rb") as f:
        up = httpx.put(init.headers["location"], content=f.read(),
                       headers={"Content-Type": "video/mp4"}, timeout=900)
    if up.status_code >= 400:
        raise PublishError(f"YouTube upload failed: {up.text[:300]}")
    return f"https://youtube.com/shorts/{up.json()['id']}"


# ---------------------------------------------------------------- review bot


def send_for_review(job_id: str) -> None:
    job = jobs.load(job_id)
    offer = jobs.get_offer(job.get("offer_id"))
    text = f"Черновик {job_id}\n\n" + caption(job, offer, 900)
    markup = {"inline_keyboard": [[
        {"text": "✅ Опубликовать", "callback_data": f"pub:{job_id}"},
        {"text": "🗑 Отклонить", "callback_data": f"rej:{job_id}"},
    ]]}
    _send_video(reels_settings.tg_review_chat, jobs.job_dir(job_id) / "reel.mp4", text, markup)


def notify(text: str) -> None:
    """Best-effort message to the review chat."""
    if not reels_settings.review_enabled:
        return
    try:
        _tg("sendMessage", json={"chat_id": reels_settings.tg_review_chat, "text": text})
    except Exception as exc:
        log.warning("Telegram notify failed: %s", exc)


def _handle_callback(cq: dict) -> None:
    chat_id = str(cq.get("message", {}).get("chat", {}).get("id", ""))
    if chat_id != str(reels_settings.tg_review_chat):
        _tg("answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "Нет доступа"})
        return
    action, _, job_id = (cq.get("data") or "").partition(":")
    _tg("answerCallbackQuery", json={"callback_query_id": cq["id"], "text": "Принято, работаю…"})
    if action == "pub":
        try:
            result = publish(job_id)
            lines = [f"{k}: {v}" for k, v in result["published"].items()]
            lines += [f"{k}: ошибка — {v}" for k, v in result["errors"].items()]
            note = "Опубликовано\n" + "\n".join(lines)
        except Exception as exc:
            note = f"Не опубликовано: {exc}"
    elif action == "rej":
        with jobs.lock(job_id):
            job = jobs.load(job_id)
            job["status"] = "rejected"
            jobs.save(job)
            jobs.drop_media(job_id)
        note = "Отклонено, файлы удалены"
    else:
        return
    msg = cq["message"]
    _tg("sendMessage", json={"chat_id": chat_id, "text": f"{job_id}: {note}",
                             "reply_to_message_id": msg["message_id"]})
    _tg("editMessageReplyMarkup", json={"chat_id": chat_id, "message_id": msg["message_id"],
                                        "reply_markup": {"inline_keyboard": []}})


def _review_loop() -> None:
    offset = 0
    while True:
        try:
            updates = _tg("getUpdates", json={"offset": offset, "timeout": 50,
                                              "allowed_updates": ["callback_query"]})
            for upd in updates:
                offset = upd["update_id"] + 1
                if "callback_query" in upd:
                    _handle_callback(upd["callback_query"])
        except Exception as exc:
            log.warning("Review bot: %s", exc)
            time.sleep(10)


def start_review_bot() -> None:
    if reels_settings.review_enabled:
        threading.Thread(target=_review_loop, name="reels-review-bot", daemon=True).start()
        log.info("Reels review bot started")
