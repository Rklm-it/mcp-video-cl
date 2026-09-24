"""MCP server: lets Claude watch videos (frames) and read what is said (transcript)."""

from __future__ import annotations

import argparse
import asyncio
import base64
import functools
import hmac
import logging
import time
from collections.abc import Callable
from typing import Annotated, Literal

import anyio
import anyio.from_thread
import anyio.to_thread
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ContentBlock, ImageContent, TextContent, ToolAnnotations
from pydantic import Field

from . import frames as fr
from . import sources as src_mod
from . import transcript as tr
from .config import settings
from .sources import SourceError
from .timeutil import fmt_time, parse_time

log = logging.getLogger("video_mcp")

INSTRUCTIONS = """\
This server lets you actually watch videos: it downloads them on the server and returns
key frames as images together with the timestamped transcript.

Sources: any YouTube link (also shorts/live/youtu.be), most sites supported by yt-dlp
(Vimeo, TikTok, Instagram, X, VK, Rutube, Twitch VODs, direct .mp4 links…), or a file name
from the server's local video folder (see list_local_videos).

Typical flow:
1. analyze_video(source) — metadata + frames interleaved with what is being said. Start here.
   For long videos use detail="brief" first (no frames), then look at parts with start/end.
2. analyze_moment(source, start, end) — dense frames + speech for a short fragment.
3. get_frames_at(source, timestamps) — exact moments (e.g. to read a slide or code on screen,
   use frame_width=1280 or more for small text).
4. get_transcript(source) — full text only; paginate with start when it is truncated.
Timestamps accept seconds (95) or "1:35" / "1:02:03". The first call for a video downloads it,
which can take a minute for long videos; later calls reuse the cache.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

mcp = FastMCP(
    "video",
    instructions=INSTRUCTIONS,
    host=settings.host,
    port=settings.port,
    stateless_http=True,
    # Access is protected by the token middleware below; the server sits behind a reverse proxy.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

Source = Annotated[
    str,
    Field(description="YouTube/any video URL, a YouTube video id, or a file name in the local video folder"),
]
TimeArg = Annotated[
    str | float | None, Field(description='Seconds or "m:ss" / "h:mm:ss"; empty = video start/end')
]


# ---------------------------------------------------------------- helpers


class Reporter:
    """Thread-safe progress bridge from worker threads to the MCP client."""

    def __init__(self, ctx: Context | None):
        self.ctx = ctx
        self.step = 0
        self._tasks: set[asyncio.Task] = set()

    def __call__(self, frac: float, message: str) -> None:
        if self.ctx is None:
            return
        self.step += 1
        send = functools.partial(self.ctx.report_progress, self.step, None, message)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:  # called from a worker thread
            try:
                anyio.from_thread.run(send)
            except Exception:  # progress is best-effort
                pass
        else:
            task = loop.create_task(send())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)


async def _run(fn: Callable, *args, **kwargs):
    return await anyio.to_thread.run_sync(functools.partial(fn, *args, **kwargs))


def _text(value: str) -> TextContent:
    return TextContent(type="text", text=value)


def _image(frame: fr.Frame) -> ImageContent:
    return ImageContent(type="image", data=base64.b64encode(frame.jpeg).decode(), mimeType="image/jpeg")


def _range(info: dict, start: TimeArg, end: TimeArg) -> tuple[float, float]:
    duration = float(info.get("duration") or 0)
    s = parse_time(start) or 0.0
    e = parse_time(end)
    if e is None or (duration and e > duration):
        e = duration
    if duration and s >= duration:
        raise SourceError(f"start {fmt_time(s)} is beyond the video length {fmt_time(duration)}")
    if e and e <= s:
        raise SourceError("end must be greater than start")
    return s, e


def _width(frame_width: int | None) -> int:
    return max(160, min(frame_width or settings.frame_width, settings.frame_max_width))


def _header(info: dict, with_description: bool = True) -> str:
    lines = [f"# {info.get('title') or info.get('id')}"]
    who = info.get("channel") or info.get("uploader")
    if who:
        lines.append(f"Channel: {who}")
    date = info.get("upload_date")
    if date and len(date) == 8:
        lines.append(f"Published: {date[:4]}-{date[4:6]}-{date[6:]}")
    if info.get("duration"):
        lines.append(f"Duration: {fmt_time(info['duration'])}")
    stats = [
        f"{label}: {info[key]:,}".replace(",", " ")
        for key, label in (("view_count", "views"), ("like_count", "likes"), ("comment_count", "comments"))
        if info.get(key) is not None
    ]
    if stats:
        lines.append(" · ".join(stats))
    if info.get("webpage_url"):
        lines.append(f"URL: {info['webpage_url']}")
    chapters = info.get("chapters") or []
    if chapters:
        lines.append("\nChapters:")
        lines += [f"  {fmt_time(c.get('start_time'))} {c.get('title')}" for c in chapters]
    if with_description and info.get("description"):
        desc = info["description"].strip()
        if len(desc) > 2000:
            desc = desc[:2000] + "…"
        lines.append(f"\nDescription:\n{desc}")
    return "\n".join(lines)


def _transcript_label(meta: dict) -> str:
    source = meta.get("source", "none")
    lang = meta.get("language")
    return f"{source}{f', language: {lang}' if lang else ''}"


async def _load_transcript(source, lang, start, end, reporter) -> tuple[list[tr.Segment], dict]:
    try:
        return await _run(src_mod.get_transcript, source, lang, True, start, end, reporter)
    except Exception as exc:  # frames are still useful without a transcript
        log.warning("Transcript failed for %s: %s", source.key, exc)
        return [], {"source": "none", "reason": f"transcript failed: {(str(exc).splitlines() or [repr(exc)])[0][:300]}"}


async def _pick_frames(
    source, info: dict, start: float, end: float, count: int, width: int, mode: str,
    threshold: float, reporter: Reporter,
) -> list[fr.Frame]:
    path, offset = await _run(src_mod.get_video_file, source, start, end, reporter)
    file_duration = await _run(fr.probe_duration, path)
    fs = max(0.0, start - offset)
    fe = min(file_duration or end - offset, end - offset) if end else file_duration
    if mode == "uniform":
        times = fr.uniform_times(fs, fe, count)
    else:
        reporter(0.9, "Detecting scene changes…")
        scenes = await _run(fr.detect_scenes, path, fs, fe, threshold)
        times = fr.choose_times(scenes, fs, fe, count)
    reporter(0.95, f"Extracting {len(times)} frames…")
    frames = await _run(fr.grab_frames, path, times, width, offset)
    return fr.dedupe(frames) if mode != "uniform" else frames


def _timeline(
    frames: list[fr.Frame], segments: list[tr.Segment], start: float, end: float, max_chars: int
) -> list[ContentBlock]:
    """Interleave frames with the speech that happens until the next frame."""
    blocks: list[ContentBlock] = []
    used = 0
    truncated_at: float | None = None
    pending = ""
    for i, frame in enumerate(frames):
        seg_start = start if i == 0 else frame.time
        seg_end = frames[i + 1].time if i + 1 < len(frames) else end + 0.01
        speech = tr.text_between(segments, seg_start, seg_end) if segments else ""
        if speech and truncated_at is None and used + len(speech) > max_chars:
            truncated_at = seg_start
        if truncated_at is not None:
            speech = ""
        used += len(speech)
        pending += f"\n\n[{fmt_time(frame.time)}] frame {i + 1}/{len(frames)}"
        blocks.append(_text(pending.strip()))
        blocks.append(_image(frame))
        pending = f"Speech {fmt_time(seg_start)}–{fmt_time(min(seg_end, end))}: {speech}" if speech else ""
    if pending:
        blocks.append(_text(pending))
    if truncated_at is not None:
        blocks.append(
            _text(f"[Transcript cut at {fmt_time(truncated_at)} to save context — call get_transcript "
                  f"with start={fmt_time(truncated_at)} for the rest]")
        )
    return blocks


def _frames_for(detail: str, span: float) -> int:
    if detail == "detailed":
        return int(min(40, max(12, span / 8)))
    return int(min(16, max(6, span / 20)))


def _errors(fn):
    """Log tool duration and failures; FastMCP turns the exception into an error result."""

    @functools.wraps(fn)
    async def wrapper(*args, **kwargs):
        started = time.monotonic()
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            log.warning("%s failed: %s", fn.__name__, exc)
            raise
        finally:
            log.info("%s finished in %.1fs", fn.__name__, time.monotonic() - started)

    return wrapper


# ---------------------------------------------------------------- tools


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@_errors
async def analyze_video(
    source: Source,
    detail: Annotated[
        Literal["brief", "standard", "detailed"],
        Field(description="brief = metadata + transcript, no frames; standard = ~6-16 key frames; "
                          "detailed = up to 40 frames"),
    ] = "standard",
    start: TimeArg = None,
    end: TimeArg = None,
    max_frames: Annotated[int | None, Field(description="Override the number of frames")] = None,
    frame_width: Annotated[int | None, Field(description="Frame width in px (default 768; 1280+ to read small text)")] = None,
    lang: Annotated[str | None, Field(description="Preferred transcript language code, e.g. 'ru' or 'en'")] = None,
    ctx: Context | None = None,
) -> list[ContentBlock]:
    """Watch a video: metadata, key frames (scene changes) and the transcript interleaved on one timeline.

    This is the main tool. Frames are chosen where the picture changes, and each frame is followed
    by what is said until the next frame. Use start/end to focus on part of a long video.
    """
    reporter = Reporter(ctx)
    source_obj = src_mod.resolve(source)
    info = await _run(src_mod.get_info, source_obj)
    s, e = _range(info, start, end)
    segments, meta = await _load_transcript(source_obj, lang, s if start else None, e if end else None, reporter)
    in_range = tr.slice_segments(segments, s, e or None)
    header = _header(info)
    if start is not None or end is not None:
        header += f"\n\nAnalysed range: {fmt_time(s)}–{fmt_time(e)}"
    header += f"\nTranscript: {_transcript_label(meta)}"
    if meta.get("reason"):
        header += f" ({meta['reason']})"
    blocks: list[ContentBlock] = [_text(header)]

    if detail == "brief":
        text, resume = tr.format_transcript(in_range, max_chars=settings.transcript_max_chars)
        blocks.append(_text("## Transcript\n" + (text or "(no speech)")))
        if resume is not None:
            blocks.append(_text(f"[Truncated — call get_transcript with start={fmt_time(resume)} for the rest]"))
        return blocks

    count = max(1, min(max_frames or _frames_for(detail, e - s), settings.max_frames_limit))
    frames = await _pick_frames(source_obj, info, s, e, count, _width(frame_width), "scene", 0.3, reporter)
    blocks.append(_text(f"## Timeline: {len(frames)} key frames with speech"))
    blocks += _timeline(frames, in_range, s, e or frames[-1].time + 1, settings.transcript_max_chars)
    return blocks


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@_errors
async def analyze_moment(
    source: Source,
    start: Annotated[str | float, Field(description='Start of the fragment: seconds or "m:ss"')],
    end: Annotated[str | float, Field(description='End of the fragment: seconds or "m:ss"')],
    frames: Annotated[int, Field(description="Number of evenly spaced frames", ge=1, le=60)] = 8,
    frame_width: Annotated[int | None, Field(description="Frame width in px (default 768)")] = None,
    lang: Annotated[str | None, Field(description="Preferred transcript language code")] = None,
    ctx: Context | None = None,
) -> list[ContentBlock]:
    """Look closely at a short fragment: evenly spaced frames plus the speech between them.

    Good for actions, demos, transitions — anything where motion between key frames matters.
    """
    reporter = Reporter(ctx)
    source_obj = src_mod.resolve(source)
    info = await _run(src_mod.get_info, source_obj)
    s, e = _range(info, start, end)
    segments, meta = await _load_transcript(source_obj, lang, s, e, reporter)
    count = min(frames, settings.max_frames_limit)
    picked = await _pick_frames(source_obj, info, s, e, count, _width(frame_width), "uniform", 0.3, reporter)
    blocks: list[ContentBlock] = [
        _text(f"{info.get('title')}: fragment {fmt_time(s)}–{fmt_time(e)}, {len(picked)} frames. "
              f"Transcript: {_transcript_label(meta)}")
    ]
    blocks += _timeline(picked, tr.slice_segments(segments, s, e or None), s, e or picked[-1].time + 1,
                        settings.transcript_max_chars)
    return blocks


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@_errors
async def get_frames(
    source: Source,
    start: TimeArg = None,
    end: TimeArg = None,
    max_frames: Annotated[int, Field(description="Maximum number of frames", ge=1, le=60)] = 12,
    mode: Annotated[
        Literal["scene", "uniform"],
        Field(description="scene = where the picture changes; uniform = evenly spaced"),
    ] = "scene",
    scene_threshold: Annotated[float, Field(description="Scene change sensitivity 0..1 (lower = more cuts)", ge=0.01, le=1)] = 0.3,
    frame_width: Annotated[int | None, Field(description="Frame width in px (default 768)")] = None,
    ctx: Context | None = None,
) -> list[ContentBlock]:
    """Frames only (no transcript), each labelled with its timestamp."""
    reporter = Reporter(ctx)
    source_obj = src_mod.resolve(source)
    info = await _run(src_mod.get_info, source_obj)
    s, e = _range(info, start, end)
    count = min(max_frames, settings.max_frames_limit)
    picked = await _pick_frames(source_obj, info, s, e, count, _width(frame_width), mode, scene_threshold, reporter)
    blocks: list[ContentBlock] = [_text(f"{info.get('title')}: {len(picked)} frames from {fmt_time(s)}–{fmt_time(e)}")]
    for frame in picked:
        blocks += [_text(f"[{fmt_time(frame.time)}]"), _image(frame)]
    return blocks


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@_errors
async def get_frames_at(
    source: Source,
    timestamps: Annotated[
        list[str | float], Field(description='Moments to capture, e.g. ["0:42", "3:15", 600]', min_length=1, max_length=30)
    ],
    frame_width: Annotated[int | None, Field(description="Frame width in px (default 768; 1280+ for small text)")] = None,
    ctx: Context | None = None,
) -> list[ContentBlock]:
    """Grab frames at exact timestamps — e.g. to read a slide, code or a table shown on screen."""
    reporter = Reporter(ctx)
    source_obj = src_mod.resolve(source)
    info = await _run(src_mod.get_info, source_obj)
    duration = float(info.get("duration") or 0)
    times = sorted({parse_time(t) for t in timestamps})
    if duration:
        times = [min(t, duration - 0.1) for t in times]
    path, offset = await _run(src_mod.get_video_file, source_obj, times[0], times[-1] + 1, reporter)
    picked = await _run(fr.grab_frames, path, [t - offset for t in times], _width(frame_width), offset)
    blocks: list[ContentBlock] = []
    for frame in picked:
        blocks += [_text(f"[{fmt_time(frame.time)}]"), _image(frame)]
    return blocks


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@_errors
async def get_transcript(
    source: Source,
    lang: Annotated[str | None, Field(description="Preferred language code, e.g. 'ru', 'en'. "
                                                 "Default: original language")] = None,
    start: TimeArg = None,
    end: TimeArg = None,
    max_chars: Annotated[int | None, Field(description="Cut the output after this many characters")] = None,
    use_whisper: Annotated[bool, Field(description="Transcribe audio with Whisper if there are no subtitles")] = True,
    ctx: Context | None = None,
) -> list[ContentBlock]:
    """Timestamped transcript: subtitles / auto-captions, or Whisper speech recognition as a fallback."""
    reporter = Reporter(ctx)
    source_obj = src_mod.resolve(source)
    info = await _run(src_mod.get_info, source_obj)
    s, e = _range(info, start, end)
    segments, meta = await _run(
        src_mod.get_transcript, source_obj, lang, use_whisper,
        s if start else None, e if end else None, reporter,
    )
    in_range = tr.slice_segments(segments, s, e or None)
    text, resume = tr.format_transcript(in_range, max_chars=max_chars or settings.transcript_max_chars)
    head = f"{info.get('title')} — transcript ({_transcript_label(meta)})"
    if meta.get("reason"):
        head += f"\n{meta['reason']}"
    blocks = [_text(head + "\n\n" + (text or "(no speech found)"))]
    if resume is not None:
        blocks.append(_text(f"[Truncated — call get_transcript again with start={fmt_time(resume)}]"))
    return blocks


@mcp.tool(annotations=READ_ONLY, structured_output=False)
@_errors
async def get_video_info(
    source: Source,
    include_thumbnail: Annotated[bool, Field(description="Also return the thumbnail / first frame")] = False,
    ctx: Context | None = None,
) -> list[ContentBlock]:
    """Metadata without downloading the video: title, channel, duration, stats, chapters,
    description, available subtitle languages."""
    source_obj = src_mod.resolve(source)
    info = await _run(src_mod.get_info, source_obj)
    text = _header(info)
    manual = sorted((info.get("subtitles") or {}).keys())
    auto_orig = [k[:-5] for k in (info.get("automatic_captions") or {}) if k.endswith("-orig")]
    if manual:
        text += f"\n\nSubtitles: {', '.join(manual)}"
    if auto_orig:
        text += f"\nAuto-captions (original language): {', '.join(auto_orig)}"
    if info.get("tags"):
        text += f"\nTags: {', '.join(info['tags'][:30])}"
    if source_obj.kind == "local":
        text += f"\nResolution: {info.get('width')}x{info.get('height')}, size {info.get('size_mb')} MB"
    blocks: list[ContentBlock] = [_text(text)]
    if include_thumbnail:
        if source_obj.kind == "url" and info.get("thumbnail"):
            data = await _run(src_mod._fetch_bytes, info["thumbnail"])
            if data:
                blocks.append(ImageContent(type="image", data=base64.b64encode(data).decode(),
                                           mimeType="image/jpeg"))
        elif source_obj.kind == "local":
            picked = await _run(fr.grab_frames, source_obj.path, [min(1.0, (info.get("duration") or 2) / 2)],
                                settings.frame_width)
            blocks.append(_image(picked[0]))
    return blocks


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=True), structured_output=False)
@_errors
async def list_local_videos() -> str:
    """List video files uploaded to the server's local folder (usable as `source`)."""
    base = settings.local_video_dir
    if not base.exists():
        return f"Folder {base} does not exist"
    files = sorted(
        p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in src_mod.VIDEO_EXTS
    )
    if not files:
        return f"No videos in {base}. Upload files there (e.g. scp video.mp4 vps:{base}/)."
    return "\n".join(f"{p.relative_to(base)}  ({p.stat().st_size / 1e6:.1f} MB)" for p in files)


# ---------------------------------------------------------------- HTTP app & auth


class TokenAuth:
    """ASGI middleware: accepts `Authorization: Bearer <token>` or a secret path prefix `/<token>/mcp`
    (for clients such as claude.ai custom connectors that cannot send headers)."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path: str = scope.get("path", "")
        if path in ("/health", "/healthz"):
            return await _plain(send, 200, b"ok")
        if self.token:
            prefix = f"/{self.token}"
            headers = dict(scope.get("headers") or [])
            auth = headers.get(b"authorization", b"").decode()
            if path.startswith(prefix + "/"):
                scope = dict(scope, path=path[len(prefix):], raw_path=path[len(prefix):].encode())
            elif not (auth.startswith("Bearer ") and hmac.compare_digest(auth[7:].strip(), self.token)):
                return await _plain(send, 401, b"unauthorized", [(b"www-authenticate", b"Bearer")])
        return await self.app(scope, receive, send)


async def _plain(send, status: int, body: bytes, extra_headers=None):
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"text/plain"), *(extra_headers or [])],
    })
    await send({"type": "http.response.body", "body": body})


def create_app():
    if not settings.token and not settings.allow_no_auth:
        raise SystemExit(
            "VIDEO_MCP_TOKEN is not set. Generate one (openssl rand -hex 32) or set "
            "VIDEO_MCP_ALLOW_NO_AUTH=1 if the port is not reachable from the internet."
        )
    return TokenAuth(mcp.streamable_http_app(), settings.token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Video MCP server")
    parser.add_argument("--transport", choices=["http", "stdio"], default="http")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    settings.local_video_dir.mkdir(parents=True, exist_ok=True)
    src_mod.cleanup_cache()
    if args.transport == "stdio":
        mcp.run("stdio")
        return
    import uvicorn

    log.info("Serving MCP on http://%s:%s/mcp", settings.host, settings.port)
    uvicorn.run(create_app(), host=settings.host, port=settings.port, proxy_headers=True,
                forwarded_allow_ips="*", timeout_keep_alive=120)


if __name__ == "__main__":
    main()
