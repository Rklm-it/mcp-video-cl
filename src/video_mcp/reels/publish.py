"""Uploading finished reels: Telegram channel, YouTube Shorts. Plus the Telegram review bot."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import threading
import time
from pathlib import Path

import httpx

from ..config import settings
from . import jobs
from .config import reels_settings

log = logging.getLogger("video_mcp.reels")


class PublishError(Exception):
    pass


def tracked_link(link: str, job: dict, platform: str) -> str:
    """Fill {reel} and {platform} in a partner link, so the CPA stats (subid) show which reel
    and which platform brought the lead."""
    return link.replace("{reel}", job.get("id", "")).replace("{platform}", platform)


def caption(job: dict, offer: dict | None, limit: int, platform: str = "tg") -> str:
    """Post text: ad marking first (required when the reel carries an ad), then title and text."""
    parts = []
    if offer:
        parts.append(jobs.ad_marker(offer))
    parts.append(job["title"])
    if job.get("description"):
        parts.append(job["description"])
    if offer and offer.get("link"):
        parts.append(f"{offer.get('link_text') or 'Ссылка'}: {tracked_link(offer['link'], job, platform)}")
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
        brand = reels_settings.brand(job.get("brand", ""))
        wanted = targets or reels_settings.publish_targets(job.get("brand", ""))
        if not wanted:
            raise PublishError("No publish targets configured (REELS_TG_*, REELS_YT_*, REELS_IG_* or "
                               "REELS_BRANDS in .env)")
        done = job.setdefault("published", {})
        errors = {}
        for target in wanted:
            if target in done:
                continue
            try:
                if target == "telegram":
                    if not brand["tg_channel"]:
                        raise PublishError("No Telegram channel for this brand")
                    done[target] = _telegram_post(brand["tg_channel"], video, caption(job, offer, 1024))
                elif target == "youtube":
                    done[target] = _youtube_upload(video, job, offer)
                elif target == "instagram":
                    done[target] = _instagram_post(job_id, brand, caption(job, offer, 2200, "ig"))
                else:
                    raise PublishError(f"Unknown target {target!r} (telegram, youtube, instagram)")
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


def _telegram_post(channel: str, video: Path, text: str) -> str:
    msg = _send_video(channel, video, text)
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
            "description": caption(job, offer, 4900, "yt") + "\n\n#shorts",
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


# ---------------------------------------------------------------- Instagram


def media_sig(job_id: str) -> str:
    """Signature in the public video path: without it nobody can list or guess reel files."""
    if not settings.token:
        raise PublishError("Instagram needs VIDEO_MCP_TOKEN: it signs the public link to the video")
    return hmac.new(settings.token.encode(), f"reel:{job_id}".encode(), hashlib.sha256).hexdigest()[:32]


def media_url(job_id: str) -> str:
    if not reels_settings.public_url:
        raise PublishError("REELS_PUBLIC_URL is not set: Instagram downloads the video by link "
                           "(https://<your domain>)")
    return f"{reels_settings.public_url}/reels-media/{job_id}/{media_sig(job_id)}.mp4"


def media_file(path: str) -> Path | None:
    """The reel file behind a public /reels-media/<job>/<sig>.mp4 path, or None if the path is not valid."""
    parts = path.strip("/").split("/")
    if len(parts) != 3 or parts[0] != "reels-media" or not parts[2].endswith(".mp4"):
        return None
    job_id, sig = parts[1], parts[2][:-4]
    try:
        if not hmac.compare_digest(sig, media_sig(job_id)):
            return None
        video = jobs.job_dir(job_id) / "reel.mp4"
    except (PublishError, jobs.JobError):
        return None
    return video if video.is_file() else None


def _ig(method: str, path: str, **kwargs) -> dict:
    resp = httpx.request(method, f"{reels_settings.ig_api}/{path}", timeout=60, **kwargs)
    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error") or {}
        raise PublishError(f"Instagram {path}: {err.get('message') or resp.text[:300]}")
    return data


IG_REFRESH_AFTER = 20 * 86400  # long-lived tokens live 60 days and can be refreshed once they are a day old


def _ig_token(brand: dict) -> str:
    """The freshest token for this account: refreshed every 20 days and kept in /data/reels/ig_tokens.json,
    so the one written into .env once keeps working."""
    store = reels_settings.root / "ig_tokens.json"
    try:
        saved = json.loads(store.read_text())
    except (OSError, ValueError):
        saved = {}
    entry = saved.get(brand["ig_user_id"]) or {}
    token = entry.get("token") or brand["ig_token"]
    if time.time() - entry.get("refreshed", 0) < IG_REFRESH_AFTER:
        return token
    try:
        fresh = _ig("GET", "refresh_access_token",
                    params={"grant_type": "ig_refresh_token", "access_token": token})["access_token"]
    except Exception as exc:  # the old token may still be valid: use it and try again next time
        log.warning("Instagram token refresh failed: %s", exc)
        return token
    saved[brand["ig_user_id"]] = {"token": fresh, "refreshed": time.time()}
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(saved))
    return fresh


IG_POLL_SECONDS, IG_POLL_LIMIT = 5, 120  # Instagram processes a reel for up to ~10 minutes


def _instagram_post(job_id: str, brand: dict, text: str) -> str:
    """Reel via the official API: container from the public video link → wait until processed → publish."""
    token = _ig_token(brand)
    user = brand["ig_user_id"]
    container = _ig("POST", f"{user}/media", data={
        "media_type": "REELS", "video_url": media_url(job_id), "caption": text,
        "share_to_feed": "true", "thumb_offset": "0", "access_token": token,
    })["id"]
    for _ in range(IG_POLL_LIMIT):
        status = _ig("GET", container, params={"fields": "status_code,status", "access_token": token})
        code = status.get("status_code")
        if code == "FINISHED":
            break
        if code in ("ERROR", "EXPIRED"):
            raise PublishError(f"Instagram could not process the video: {status.get('status') or code}")
        time.sleep(IG_POLL_SECONDS)
    else:
        raise PublishError("Instagram is still processing the video after 10 minutes; publish again later")
    media = _ig("POST", f"{user}/media_publish", data={"creation_id": container, "access_token": token})["id"]
    try:
        return _ig("GET", media, params={"fields": "permalink", "access_token": token}).get("permalink") or media
    except PublishError:
        return f"instagram media {media}"


# ---------------------------------------------------------------- review bot


def send_for_review(job_id: str) -> None:
    job = jobs.load(job_id)
    offer = jobs.get_offer(job.get("offer_id"))
    brand = reels_settings.brand(job.get("brand", ""))
    where = ", ".join(reels_settings.publish_targets(job.get("brand", ""))) or "никуда не настроено"
    head = f"Черновик {job_id}" + (f" · {brand['title']}" if brand["title"] else "") + f"\nКуда: {where}"
    text = head + "\n\n" + caption(job, offer, 900, "review")
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
