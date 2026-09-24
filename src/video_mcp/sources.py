"""Resolving sources (URLs via yt-dlp, local files), downloading and caching."""

from __future__ import annotations

import hashlib
import ipaddress
import json
import logging
import re
import shutil
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from . import frames as fr
from . import transcript as tr
from .config import settings

log = logging.getLogger(__name__)

Progress = Callable[[float, str], None]

VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v", ".flv", ".ts", ".mpg", ".mpeg", ".wmv", ".3gp"}
INFO_TTL_SECONDS = 3 * 3600  # signed media/subtitle URLs in yt-dlp info expire after a few hours
SUB_FORMATS = ("json3", "vtt", "srt")

_YT_ID = re.compile(
    r"(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|live/|embed/|v/)|youtu\.be/|youtube-nocookie\.com/embed/)"
    r"([A-Za-z0-9_-]{11})"
)


class SourceError(Exception):
    """User-facing error (bad source, blocked download, ...)."""


def _noop(_frac: float, _msg: str) -> None:
    pass


@dataclass
class Source:
    raw: str
    kind: str  # "url" | "local"
    key: str
    url: str | None = None
    path: Path | None = None

    @property
    def cache(self) -> Path:
        d = settings.cache_dir / self.key
        d.mkdir(parents=True, exist_ok=True)
        return d


# ---------------------------------------------------------------- resolving


def resolve(raw: str) -> Source:
    raw = (raw or "").strip()
    if not raw:
        raise SourceError("Empty source: pass a video URL or a file name from the server's video folder")
    parsed = urlparse(raw)
    if parsed.scheme in ("http", "https"):
        match = _YT_ID.search(raw)
        if match:
            vid = match.group(1)
            return Source(raw, "url", f"yt_{vid}", url=f"https://www.youtube.com/watch?v={vid}")
        _check_public_host(parsed.hostname or "")
        return Source(raw, "url", "url_" + hashlib.sha1(raw.encode()).hexdigest()[:16], url=raw)
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", raw) and not (settings.local_video_dir / raw).exists():
        return resolve(f"https://www.youtube.com/watch?v={raw}")
    return _resolve_local(raw[7:] if parsed.scheme == "file" else raw)


def _resolve_local(raw: str) -> Source:
    base = settings.local_video_dir.resolve()
    candidate = Path(raw)
    path = (candidate if candidate.is_absolute() else base / candidate).resolve()
    if base != path and base not in path.parents:
        raise SourceError(f"Local files must be inside {base}")
    if not path.is_file():
        raise SourceError(f"File not found: {path}. Use list_local_videos to see available files.")
    stat = path.stat()
    digest = hashlib.sha1(f"{path}:{stat.st_size}:{stat.st_mtime_ns}".encode()).hexdigest()[:16]
    return Source(raw, "local", f"file_{digest}", path=path)


def _check_public_host(host: str) -> None:
    if settings.allow_private_urls:
        return
    if not host:
        raise SourceError("URL has no host")
    try:
        addrs = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise SourceError(f"Cannot resolve host {host}: {exc}") from exc
    for addr in addrs:
        ip = ipaddress.ip_address(addr.split("%")[0])
        if not ip.is_global:
            raise SourceError(f"Refusing to fetch non-public address {host} ({ip})")


# ---------------------------------------------------------------- locks & cache housekeeping

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def touch(src: Source) -> None:
    (src.cache / ".last_used").write_text(str(time.time()))


def _last_used(d: Path) -> float:
    marker = d / ".last_used"
    try:
        return float(marker.read_text())
    except (OSError, ValueError):
        return d.stat().st_mtime


def _dir_size(d: Path) -> int:
    return sum(f.stat().st_size for f in d.rglob("*") if f.is_file())


def cleanup_cache() -> None:
    root = settings.cache_dir
    if not root.exists():
        return
    now = time.time()
    entries = []
    for d in root.iterdir():
        if not d.is_dir() or _lock(d.name).locked():
            continue
        used = _last_used(d)
        if now - used > settings.cache_ttl_hours * 3600:
            shutil.rmtree(d, ignore_errors=True)
            continue
        entries.append((used, d, _dir_size(d)))
    total = sum(size for _, _, size in entries)
    limit = settings.cache_max_gb * 1024**3
    for _used, d, size in sorted(entries, key=lambda e: e[0]):
        if total <= limit:
            break
        shutil.rmtree(d, ignore_errors=True)
        total -= size


# ---------------------------------------------------------------- yt-dlp plumbing


class _YtdlLogger:
    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        log.warning("yt-dlp: %s", msg)

    def error(self, msg: str) -> None:
        log.error("yt-dlp: %s", msg)


def _cookie_copy() -> str | None:
    """yt-dlp rewrites its cookie file, so work on a writable copy of the mounted one."""
    if not settings.cookies_file:
        return None
    original = Path(settings.cookies_file)
    if not original.is_file():
        log.warning("YTDLP_COOKIES=%s does not exist, ignoring", original)
        return None
    working = settings.data_dir / "cookies.working.txt"
    if not working.exists() or working.stat().st_mtime < original.stat().st_mtime:
        working.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, working)
    return str(working)


def _ydl_opts(**extra) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "socket_timeout": 30,
        "retries": 5,
        "fragment_retries": 5,
        "extractor_retries": 2,
        "logger": _YtdlLogger(),
    }
    cookies = _cookie_copy()
    if cookies:
        opts["cookiefile"] = cookies
    if settings.proxy:
        opts["proxy"] = settings.proxy
    if settings.pot_provider_url:
        opts["extractor_args"] = {"youtubepot-bgutilhttp": {"base_url": [settings.pot_provider_url]}}
    opts.update(extra)
    return opts


def _friendly(exc: Exception) -> SourceError:
    text = re.sub(r"\x1b\[[0-9;]*m", "", str(exc))
    hint = ""
    lowered = text.lower()
    if "not a bot" in lowered or "sign in to confirm" in lowered or "http error 429" in lowered:
        hint = (
            " — YouTube is blocking this server's IP. Put a cookies.txt from a logged-in browser into"
            " YTDLP_COOKIES and/or set YTDLP_PROXY (see README, section 'YouTube blocks the VPS')."
        )
    elif "private video" in lowered or "members-only" in lowered or ("age" in lowered and "confirm" in lowered):
        hint = " — this video needs an authorised account: configure YTDLP_COOKIES."
    return SourceError(text + hint)


def _progress_hook(progress: Progress, label: str):
    last = [0.0]

    def hook(d: dict) -> None:
        if d.get("status") != "downloading" or time.time() - last[0] < 2:
            return
        last[0] = time.time()
        done = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        frac = done / total if total else 0.0
        progress(min(frac, 0.99), f"{label}: {done / 1e6:.0f}/{total / 1e6:.0f} MB" if total else label)

    return hook


# ---------------------------------------------------------------- metadata


def get_info(src: Source, refresh: bool = False) -> dict:
    with _lock(src.key):
        touch(src)
        cached = src.cache / "info.json"
        if not refresh and cached.exists() and (
            src.kind == "local" or time.time() - cached.stat().st_mtime < INFO_TTL_SECONDS
        ):
            return json.loads(cached.read_text(encoding="utf-8"))
        info = _local_info(src.path) if src.kind == "local" else _remote_info(src.url)
        cached.write_text(json.dumps(info, ensure_ascii=False), encoding="utf-8")
        return info


def _remote_info(url: str) -> dict:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    try:
        with YoutubeDL(_ydl_opts()) as ydl:
            info = ydl.sanitize_info(ydl.extract_info(url, download=False))
    except DownloadError as exc:
        raise _friendly(exc) from exc
    if info.get("_type") == "playlist":
        raise SourceError("This is a playlist/channel URL — pass a link to a single video")
    keep = (
        "id", "title", "fulltitle", "description", "channel", "uploader", "channel_url", "uploader_url",
        "upload_date", "timestamp", "duration", "view_count", "like_count", "comment_count", "tags",
        "categories", "chapters", "language", "webpage_url", "extractor_key", "is_live", "live_status",
        "subtitles", "automatic_captions", "thumbnail", "width", "height", "fps", "age_limit",
    )
    trimmed = {k: info.get(k) for k in keep if info.get(k) is not None}
    if not trimmed.get("duration"):
        # Direct file links carry no duration in yt-dlp metadata; ask ffprobe.
        media = info.get("url") or next((f.get("url") for f in info.get("requested_formats") or []), None)
        if media and media.startswith(("http://", "https://")):
            trimmed["duration"] = _probe_url_duration(media)
    for field in ("subtitles", "automatic_captions"):
        tracks = trimmed.get(field) or {}
        trimmed[field] = {
            lang: [{"ext": t.get("ext"), "url": t.get("url"), "name": t.get("name")} for t in items
                   if t.get("ext") in SUB_FORMATS]
            for lang, items in tracks.items()
            if lang != "live_chat"
        }
        trimmed[field] = {k: v for k, v in trimmed[field].items() if v}
    return trimmed


def _probe_url_duration(url: str) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-rw_timeout", "15000000", "-show_entries", "format=duration",
             "-of", "csv=p=0", url],
            capture_output=True, text=True, timeout=30,
        ).stdout.strip()
        return float(out) if out and out != "N/A" else None
    except (subprocess.TimeoutExpired, ValueError):
        return None


def _local_info(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SourceError(f"ffprobe failed on {path.name}: {proc.stderr.strip()[-300:]}")
    probe = json.loads(proc.stdout)
    fmt = probe.get("format", {})
    video = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
    tags = fmt.get("tags", {})
    return {
        "id": path.name,
        "title": tags.get("title") or path.stem,
        "duration": float(fmt.get("duration") or 0),
        "width": video.get("width"),
        "height": video.get("height"),
        "has_audio": any(s.get("codec_type") == "audio" for s in probe.get("streams", [])),
        "subtitle_streams": sum(1 for s in probe.get("streams", []) if s.get("codec_type") == "subtitle"),
        "webpage_url": f"file://{path}",
        "extractor_key": "local",
        "size_mb": round(path.stat().st_size / 1e6, 1),
    }


# ---------------------------------------------------------------- video download


def _height_for(duration: float | None) -> int:
    if duration and duration > settings.long_video_minutes * 60:
        return settings.long_video_max_height
    return settings.max_height


def _find(cache: Path, stem: str) -> Path | None:
    for p in sorted(cache.glob(f"{stem}.*")):
        if p.suffix not in (".part", ".ytdl", ".json") and not p.name.endswith(".part"):
            return p
    return None


def get_video_file(
    src: Source, start: float | None = None, end: float | None = None, progress: Progress = _noop
) -> tuple[Path, float]:
    """Return (file, offset): file time 0 corresponds to `offset` seconds of the video."""
    if src.kind == "local":
        touch(src)
        return src.path, 0.0
    info = get_info(src)
    duration = info.get("duration") or 0
    if info.get("is_live"):
        raise SourceError("Live streams are not supported until they finish")
    if duration and duration > settings.max_duration_hours * 3600 and start is None:
        raise SourceError(
            f"Video is {duration / 3600:.1f} h long; pass start/end to analyse a part of it"
        )

    wants_section = (
        duration > settings.section_download_minutes * 60
        and (start is not None or end is not None)
        and ((end or duration) - (start or 0)) < duration * 0.8
    )
    with _lock(src.key):
        touch(src)
        full = _find(src.cache, "video")
        if full:
            return full, 0.0
        if wants_section:
            need_from = max(0.0, (start or 0) - 1)
            need_to = min(duration, (end or duration) + 1)
            for sec in src.cache.glob("section_*"):
                # section_<offset>_<end>.<ext> covers [offset, end] of the video timeline
                m = re.match(r"section_(-?[\d.]+)_([\d.]+)$", sec.stem)
                if m and float(m.group(1)) <= need_from and float(m.group(2)) >= need_to:
                    return sec, float(m.group(1))
            s0 = max(0.0, (start or 0) - 3)
            e0 = min(duration, (end or duration) + 3)
            path = _download(src, "section_tmp", duration, progress, section=(s0, e0))
            file_dur = fr.probe_duration(path)
            if file_dur > 0:
                # Stream-copy cuts start at the keyframe before s0; the end is exact, so infer the offset.
                extra = file_dur - (e0 - s0)
                offset = s0 - extra if 0 < extra < 20 else s0
                final = path.with_name(f"section_{offset:.2f}_{e0:.2f}{path.suffix}")
                path.rename(final)
                result = (final, offset)
            else:
                log.warning("Section download of %s produced an unreadable file, downloading in full", src.key)
                path.unlink(missing_ok=True)
                wants_section = False
        if not wants_section:
            result = (_download(src, "video", duration, progress), 0.0)
    cleanup_cache()
    return result


def _download(
    src: Source, stem: str, duration: float, progress: Progress, section: tuple[float, float] | None = None,
    audio: bool = False,
) -> Path:
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, download_range_func

    if audio:
        fmt = "ba[ext=m4a]/ba/b"
        label = "Downloading audio"
    else:
        h = _height_for(duration)
        fmt = f"bv*[height<={h}][vcodec^=avc1]/bv*[height<={h}]/b[height<={h}]/bv*/b"
        label = f"Downloading video (≤{h}p)"
    extra: dict = {
        "format": fmt,
        "outtmpl": str(src.cache / f"{stem}.%(ext)s"),
        "progress_hooks": [_progress_hook(progress, label)],
        "overwrites": True,
        "continuedl": True,
    }
    if section:
        extra["download_ranges"] = download_range_func(None, [section])
    progress(0.0, label)
    try:
        with YoutubeDL(_ydl_opts(**extra)) as ydl:
            info = ydl.extract_info(src.url, download=True)
    except DownloadError as exc:
        raise _friendly(exc) from exc
    downloads = info.get("requested_downloads") or []
    path = Path(downloads[0]["filepath"]) if downloads and downloads[0].get("filepath") else _find(src.cache, stem)
    if not path or not path.exists():
        raise SourceError("Download finished but the file was not found")
    return path


# ---------------------------------------------------------------- transcript


def _pick_track(info: dict, lang: str | None) -> tuple[str, dict, str] | None:
    """Return (language, track, kind) where kind is 'subtitles' | 'auto-captions' | 'auto-translated'."""
    manual: dict = info.get("subtitles") or {}
    auto: dict = info.get("automatic_captions") or {}
    original = next((k[:-5] for k in auto if k.endswith("-orig")), None) or info.get("language")

    def best(tracks: list[dict]) -> dict:
        return min(tracks, key=lambda t: SUB_FORMATS.index(t["ext"]))

    def match(pool: dict, wanted: str) -> str | None:
        if wanted in pool:
            return wanted
        return next((k for k in pool if k.split("-")[0] == wanted.split("-")[0]), None)

    prefs = [p for p in (lang, original) if p]
    for pref in prefs:
        key = match(manual, pref)
        if key:
            return key, best(manual[key]), "subtitles"
        if f"{pref}-orig" in auto:
            return pref, best(auto[f"{pref}-orig"]), "auto-captions"
        key = match(auto, pref)
        if key:
            kind = "auto-captions" if original and key.split("-")[0] == original.split("-")[0] else "auto-translated"
            return key, best(auto[key]), kind
    if manual:
        key = next(iter(manual))
        return key, best(manual[key]), "subtitles"
    orig_key = next((k for k in auto if k.endswith("-orig")), None)
    if orig_key:
        return orig_key[:-5], best(auto[orig_key]), "auto-captions"
    return None


def get_transcript(
    src: Source, lang: str | None = None, allow_whisper: bool = True,
    start: float | None = None, end: float | None = None, progress: Progress = _noop,
) -> tuple[list[tr.Segment], dict]:
    """Full-video transcript (subtitles, else Whisper). Returns (segments, meta)."""
    tag = re.sub(r"[^A-Za-z0-9_-]", "", lang or "auto")
    cached = tr.load_segments(src.cache / f"transcript_{tag}.json")
    if cached:
        touch(src)
        return cached

    info = get_info(src)
    segments: list[tr.Segment] = []
    meta: dict = {}
    if src.kind == "url":
        picked = _pick_track(info, lang)
        if picked:
            code, track, kind = picked
            try:
                data = _fetch_text(track["url"])
            except Exception as exc:  # signed subtitle URLs expire: refresh metadata once
                log.info("Subtitle download failed (%s), refreshing metadata", exc)
                info = get_info(src, refresh=True)
                picked = _pick_track(info, lang)
                if not picked:
                    raise SourceError(f"Subtitle download failed: {exc}") from exc
                code, track, kind = picked
                try:
                    data = _fetch_text(track["url"])
                except Exception as exc2:
                    raise _friendly(exc2) from exc2
            segments = tr.parse_subtitles(data, track["ext"])
            meta = {"source": kind, "language": code}
    else:
        segments, meta = _local_subtitles(src.path)

    if segments:
        tr.save_segments(src.cache / f"transcript_{tag}.json", segments, meta)
        return segments, meta
    if not allow_whisper or not tr.whisper_available():
        return [], {"source": "none", "reason": "no subtitles found and Whisper is disabled"}
    return _whisper(src, info, lang, start, end, progress)


def _fetch_text(url: str) -> str:
    from yt_dlp import YoutubeDL

    with YoutubeDL(_ydl_opts()) as ydl:
        return ydl.urlopen(url).read().decode("utf-8", errors="replace")


def _fetch_bytes(url: str) -> bytes | None:
    """Download a small image (thumbnail) and return it as JPEG."""
    import io

    from PIL import Image
    from yt_dlp import YoutubeDL

    try:
        with YoutubeDL(_ydl_opts()) as ydl:
            raw = ydl.urlopen(url).read()
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        image.thumbnail((settings.frame_width, settings.frame_width))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=settings.jpeg_quality)
        return buf.getvalue()
    except Exception as exc:
        log.warning("Thumbnail download failed: %s", exc)
        return None


def _local_subtitles(path: Path) -> tuple[list[tr.Segment], dict]:
    for ext in ("vtt", "srt"):
        for sidecar in sorted(path.parent.glob(f"{path.stem}*.{ext}")):
            segments = tr.parse_subtitles(sidecar.read_text(encoding="utf-8", errors="replace"), ext)
            if segments:
                return segments, {"source": f"sidecar {sidecar.name}", "language": None}
    proc = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-map", "0:s:0", "-f", "webvtt", "-"],
        capture_output=True, text=True,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        segments = tr.parse_cues(proc.stdout)
        if segments:
            return segments, {"source": "embedded subtitles", "language": None}
    return [], {}


def _whisper(
    src: Source, info: dict, lang: str | None, start: float | None, end: float | None, progress: Progress
) -> tuple[list[tr.Segment], dict]:
    duration = info.get("duration") or 0
    s = start or 0.0
    e = end if end is not None else duration
    whole = s <= 0 and (not duration or e >= duration)
    if duration and (e - s) > 90 * 60:
        raise SourceError(
            "No subtitles; Whisper on more than 90 minutes at once is too slow on CPU — pass start/end"
        )
    tag = re.sub(r"[^A-Za-z0-9_-]", "", lang or "auto")
    cache_name = f"transcript_{tag}.json" if whole else f"whisper_{tag}_{int(s)}_{int(e)}.json"
    cached = tr.load_segments(src.cache / cache_name)
    if cached:
        return cached

    if src.kind == "local":
        media = src.path
        if info.get("has_audio") is False:
            return [], {"source": "none", "reason": "file has no audio track"}
    else:
        with _lock(src.key):
            media = _find(src.cache, "audio") or _download(src, "audio", duration, progress, audio=True)

    wav = src.cache / f"whisper_{int(s)}_{int(e)}.wav"
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    if not whole:
        cmd += ["-ss", f"{s:.2f}", "-to", f"{e:.2f}"]
    cmd += ["-i", str(media), "-vn", "-ac", "1", "-ar", "16000", str(wav)]
    subprocess.run(cmd, check=True, capture_output=True)
    progress(0.5, f"Transcribing {fmt_minutes(e - s)} of audio with Whisper ({settings.whisper_model}, CPU)…")
    try:
        segments, detected = tr.transcribe(wav, lang, offset=0.0 if whole else s)
    finally:
        wav.unlink(missing_ok=True)
    meta = {"source": f"whisper-{settings.whisper_model}", "language": detected}
    if not whole:
        meta["range"] = [s, e]
    tr.save_segments(src.cache / cache_name, segments, meta)
    return segments, meta


def fmt_minutes(seconds: float) -> str:
    return f"{seconds / 60:.0f} min" if seconds >= 60 else f"{seconds:.0f} s"
