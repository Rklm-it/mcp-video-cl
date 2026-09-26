"""Reel jobs and ad offers stored as JSON files under /data/reels."""

from __future__ import annotations

import json
import re
import secrets
import shutil
import threading
import time
from pathlib import Path

from .config import reels_settings

STATUSES = ("rendering", "ready", "published", "rejected", "failed")
_ID = re.compile(r"[a-z0-9-]{6,40}")
_guard = threading.Lock()
_locks: dict[str, threading.Lock] = {}


class JobError(Exception):
    pass


def lock(job_id: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(job_id, threading.Lock())


def new_id() -> str:
    return time.strftime("%m%d-%H%M") + "-" + secrets.token_hex(2)


def job_dir(job_id: str) -> Path:
    if not _ID.fullmatch(job_id or ""):
        raise JobError(f"Bad job id: {job_id!r}")
    return reels_settings.jobs_dir / job_id


def save(job: dict) -> None:
    d = job_dir(job["id"])
    d.mkdir(parents=True, exist_ok=True)
    job["updated"] = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = d / "job.json.tmp"
    tmp.write_text(json.dumps(job, ensure_ascii=False, indent=2))
    tmp.replace(d / "job.json")


def load(job_id: str) -> dict:
    path = job_dir(job_id) / "job.json"
    if not path.is_file():
        raise JobError(f"Reel {job_id} not found. Use list_reels to see existing ones.")
    return json.loads(path.read_text())


def all_jobs() -> list[dict]:
    base = reels_settings.jobs_dir
    if not base.exists():
        return []
    jobs = []
    for path in base.glob("*/job.json"):
        try:
            jobs.append(json.loads(path.read_text()))
        except (OSError, ValueError):
            continue
    return sorted(jobs, key=lambda j: j.get("created", ""), reverse=True)


def drop_media(job_id: str) -> None:
    """Delete the heavy files of a rejected reel, keep job.json for the history."""
    d = job_dir(job_id)
    for item in d.iterdir():
        if item.name == "job.json":
            continue
        shutil.rmtree(item) if item.is_dir() else item.unlink(missing_ok=True)


# ---------------------------------------------------------------- offers


def offers() -> dict[str, dict]:
    path = reels_settings.offers_file
    if not path.is_file():
        return {}
    return json.loads(path.read_text())


def save_offer(offer_id: str, offer: dict) -> None:
    data = offers()
    data[offer_id] = offer
    path = reels_settings.offers_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_offer(offer_id: str | None) -> dict | None:
    if not offer_id:
        return None
    data = offers()
    if offer_id not in data:
        known = ", ".join(data) or "none"
        raise JobError(f"Unknown offer {offer_id!r}. Known offers: {known}. Add one with save_offer.")
    return data[offer_id]


def ad_marker(offer: dict) -> str:
    """Legal marking line required for ads in Russia: «Реклама», advertiser, erid token."""
    return f"Реклама. {offer['advertiser']}. erid: {offer['erid']}"
