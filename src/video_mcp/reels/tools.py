"""MCP tools of the reels factory, added to the video server when REELS_ENABLED=1."""

from __future__ import annotations

import logging
import shutil
import threading
import time
from typing import Annotated, Literal

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ContentBlock, ToolAnnotations
from pydantic import BaseModel, Field

from .. import frames as fr
from .. import sources as src_mod
from . import jobs, publish, render
from .config import reels_settings

log = logging.getLogger("video_mcp.reels")

INSTRUCTIONS = """
Reels factory (create_reel etc.): you are the scriptwriter and editor, the server does voice,
pictures, rendering and uploading.
1. Write the script yourself: 4-7 scenes, 20-40 s in total. Scene 1 is the hook (a concrete number
   or a surprising claim in the first 2 seconds). Each scene = one or two short spoken sentences +
   an English image_prompt (no text in the picture) or `media` (a URL or a file from the video folder).
   animate turns a scene into a short AI video (paid). With REELS_ANIMATE_ALL=1 every scene is video
   by default; reels with video render in the background and take several minutes.
2. Before calling create_reel, check facts and numbers, and remove promises of easy money, loans,
   microloans and first-person claims that are not true.
3. Ads: only through a saved offer (save_offer) with its erid; mark the scenes that talk about the
   product with offer=true, they get the banner. Keep ads in at most ~30% of reels.
4. After create_reel look at the preview frames. Publish only after the user approved it
   (in chat, or with the Telegram review button when after="review").
"""

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
PUBLISH = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)


class Scene(BaseModel):
    text: str = Field(description="What the voice says in this scene (Russian), 1-2 short sentences")
    image_prompt: str = Field("", description="English picture prompt; no text/letters in the picture")
    media: str | None = Field(None, description="Instead of generating: image/video URL or a file name "
                                                "in the server's video folder (e.g. a clip made in Veo/Kling)")
    offer: bool = Field(False, description="Show the offer banner during this scene")
    animate: bool | None = Field(None, description="Turn the picture into a short AI video (paid). "
                                                   "Default: REELS_ANIMATE_ALL decides")


class SceneEdit(BaseModel):
    index: int = Field(description="0-based scene number")
    text: str | None = None
    image_prompt: str | None = Field(None, description="New prompt: the picture is generated again")
    media: str | None = None
    offer: bool | None = None
    animate: bool | None = None


_registered = False


def _has_video(scenes: list[dict]) -> bool:
    return reels_settings.video != "none" and any(s.get("animate") for s in scenes)


def _check_animated(scenes: list[dict]) -> None:
    count = sum(1 for s in scenes if s.get("animate"))
    if count > reels_settings.max_animated:
        raise ValueError(f"{count} animated scenes, the limit is {reels_settings.max_animated} per reel "
                         "(REELS_MAX_ANIMATED) — each one is a paid video generation")


def register(mcp: FastMCP, run) -> None:
    """Add the reels tools to `mcp`. `run` executes a blocking function in a worker thread."""
    global _registered
    if _registered:
        return
    _registered = True
    mcp._mcp_server.instructions = (mcp._mcp_server.instructions or "") + INSTRUCTIONS

    def previews(job_id: str, count: int = 4) -> list[ContentBlock]:
        from ..server import _image

        video = jobs.job_dir(job_id) / "reel.mp4"
        duration = fr.probe_duration(video)
        times = [duration * (i + 0.5) / count for i in range(count)]
        return [_image(f) for f in fr.grab_frames(video, times, 360)]

    def summary(job: dict) -> str:
        lines = [f"Reel {job['id']} — {job['status']}", f"Title: {job['title']}"]
        if job.get("duration"):
            lines.append(f"Duration: {job['duration']:.1f} s")
        if job.get("offer_id"):
            lines.append(f"Offer: {job['offer_id']}")
        for i, s in enumerate(job["scenes"]):
            flag = (" [offer]" if s.get("offer") else "") + (" [video]" if s.get("animate") else "")
            lines.append(f"  {i}. {s['text']}{flag}")
        if job.get("published"):
            lines.append("Published: " + ", ".join(f"{k}: {v}" for k, v in job["published"].items()))
        if job.get("publish_errors"):
            lines.append("Publish errors: " + ", ".join(f"{k}: {v}" for k, v in job["publish_errors"].items()))
        if job.get("music") and job["music"] != "none":
            lines.append(f"Music: {job['music']}")
        for w in job.get("warnings", []):
            lines.append(f"Warning: {w}")
        if job.get("error"):
            lines.append(f"Error: {job['error']}")
        return "\n".join(lines)

    async def build(job: dict, after: str, ctx: Context | None, background: bool) -> list[ContentBlock]:
        from ..server import Reporter, _text

        if background:
            job["status"] = "rendering"
            jobs.save(job)
            threading.Thread(target=_process_quietly, args=(job, after), daemon=True,
                             name=f"reel-{job['id']}").start()
            where = ("It will arrive in the Telegram review chat when ready."
                     if after == "review" and reels_settings.review_enabled else
                     "Check it with get_reel in a few minutes.")
            return [_text(summary(job) + f"\nRendering in the background (AI video takes a few minutes). {where}")]
        note = await run(process, job, after, Reporter(ctx))
        job = jobs.load(job["id"])
        blocks: list[ContentBlock] = [_text(summary(job) + note)]
        blocks += await run(previews, job["id"])
        return blocks

    @mcp.tool(annotations=READ, structured_output=False)
    async def reels_setup() -> str:
        """Show how the reels factory is configured: voice, pictures, publish targets, offers, counts."""
        s = reels_settings
        counts: dict[str, int] = {}
        for j in jobs.all_jobs():
            counts[j["status"]] = counts.get(j["status"], 0) + 1
        offers = jobs.offers()
        lines = [
            f"Voice: {s.tts}" + (f" ({s.edge_voice}, rate {s.edge_rate})" if s.tts == "edge" else ""),
            f"Pictures: {s.images}",
            f"Video scenes: {s.video}" + (f" ({s.veo_model}, {s.veo_resolution}, max {s.max_animated} per reel)"
                                          if s.video == "veo" else ""),
            f"Music tracks: {len(s.music_tracks())}" + (f" in {s.music_dir}" if s.music_dir else " (REELS_MUSIC_DIR not set)"),
            f"Publish targets: {', '.join(s.publish_targets()) or 'none configured'}",
            f"Telegram review: {'on' if s.review_enabled else 'off'}",
            f"Reels: {counts or 'none yet'}",
            "Offers:" if offers else "Offers: none (add with save_offer)",
        ]
        lines += [f"  {k}: {v['advertiser']}, erid {v['erid']}, banner «{v.get('banner', '')}»"
                  for k, v in offers.items()]
        return "\n".join(lines)

    @mcp.tool(annotations=WRITE, structured_output=False)
    async def save_offer(
        offer_id: Annotated[str, Field(description="Short id, e.g. 'card-cashback'")],
        advertiser: Annotated[str, Field(description="Advertiser name exactly as in the marking data")],
        erid: Annotated[str, Field(description="erid token from the CPA network / ОРД")],
        banner: Annotated[str, Field(description="Short banner on the video, e.g. 'Карта с кэшбэком — ссылка в профиле'")],
        link: Annotated[str, Field(description="Your partner link")] = "",
        link_text: Annotated[str, Field(description="Label before the link in post captions")] = "Оформить",
    ) -> str:
        """Save an ad offer. Reels reference it by offer_id; the marking line «Реклама. <advertiser>.
        erid: <token>» is then added to the video and to post captions automatically."""
        if not erid.strip() or not advertiser.strip():
            raise ValueError("advertiser and erid are required for legal ad marking")
        jobs.save_offer(offer_id, {"advertiser": advertiser.strip(), "erid": erid.strip(),
                                   "banner": banner.strip(), "link": link.strip(),
                                   "link_text": link_text.strip()})
        return f"Offer {offer_id} saved"

    @mcp.tool(annotations=WRITE, structured_output=False)
    async def create_reel(
        title: Annotated[str, Field(description="Post title (YouTube: up to 100 chars)")],
        scenes: Annotated[list[Scene], Field(min_length=1, max_length=12)],
        description: Annotated[str, Field(description="Post text under the video")] = "",
        hashtags: Annotated[list[str] | None, Field(description="Without #, e.g. ['деньги', 'лайфхаки']")] = None,
        offer_id: Annotated[str | None, Field(description="Saved offer for ad reels (see save_offer)")] = None,
        music: Annotated[str | None, Field(description="Track name from the music folder, 'none' for no "
                                                       "music; default: a random track")] = None,
        background: Annotated[bool | None, Field(description="Render in the background and return at once. "
                                                            "Default: yes when the reel has AI video scenes")] = None,
        after: Annotated[
            Literal["none", "review", "publish"],
            Field(description="none = just render; review = send to the Telegram review chat; "
                              "publish = publish right away (only if the user asked for it)"),
        ] = "none",
        ctx: Context | None = None,
    ) -> list[ContentBlock]:
        """Render a vertical reel (1080x1920): voice-over, animated pictures, subtitles and, for ad reels,
        the legal marking and offer banner. Returns the summary and preview frames. Takes 1-3 minutes."""
        items = [s.model_dump() for s in scenes]
        for s in items:
            s["animate"] = effective_animate(s)
        for i, s in enumerate(items):
            if not s["text"].strip():
                raise ValueError(f"Scene {i} has no text")
            if not (s["image_prompt"].strip() or s["media"]):
                raise ValueError(f"Scene {i} needs image_prompt or media")
        if any(s["offer"] for s in items) and not offer_id:
            raise ValueError("Scenes are marked offer=true but no offer_id is given")
        _check_animated(items)
        jobs.get_offer(offer_id)  # validate early
        job = {
            "id": jobs.new_id(), "created": time.strftime("%Y-%m-%d %H:%M:%S"), "status": "rendering",
            "title": title.strip(), "description": description.strip(), "hashtags": hashtags or [],
            "offer_id": offer_id, "scenes": items, "music": music,
        }
        jobs.save(job)
        if background is None:
            background = _has_video(items)
        return await build(job, after, ctx, background)

    @mcp.tool(annotations=WRITE, structured_output=False)
    async def edit_reel(
        job_id: str,
        changes: Annotated[list[SceneEdit] | None, Field(description="Scene changes")] = None,
        title: str | None = None,
        description: str | None = None,
        after: Literal["none", "review", "publish"] = "none",
        ctx: Context | None = None,
    ) -> list[ContentBlock]:
        """Change scenes (text, picture prompt, media, offer flag) or the post text and render again.
        Unchanged pictures are reused."""
        job = jobs.load(job_id)
        if job["status"] in ("published", "rejected"):
            raise ValueError(f"Reel {job_id} is {job['status']}; create a new one instead")
        workdir = jobs.job_dir(job_id)
        for ch in changes or []:
            if not 0 <= ch.index < len(job["scenes"]):
                raise ValueError(f"No scene {ch.index}")
            scene = job["scenes"][ch.index]
            for key in ("text", "image_prompt", "media", "offer", "animate"):
                value = getattr(ch, key)
                if value is not None:
                    scene[key] = value
            if ch.image_prompt is not None or ch.media is not None:
                for old in workdir.glob(f"scene{ch.index:02d}.*"):
                    old.unlink()
        if title is not None:
            job["title"] = title.strip()
        if description is not None:
            job["description"] = description.strip()
        if any(s.get("offer") for s in job["scenes"]) and not job.get("offer_id"):
            raise ValueError("Scenes are marked offer=true but the reel has no offer")
        _check_animated(job["scenes"])
        jobs.save(job)
        return await build(job, after, ctx, _has_video(job["scenes"]))

    @mcp.tool(annotations=READ, structured_output=False)
    async def list_reels(
        status: Annotated[str | None, Field(description="rendering, ready, published, rejected, failed")] = None,
        limit: int = 20,
    ) -> str:
        """List reels, newest first."""
        items = [j for j in jobs.all_jobs() if not status or j["status"] == status][: max(1, limit)]
        if not items:
            return "No reels yet"
        return "\n".join(
            f"{j['id']}  {j['status']:<9}  {j.get('duration', 0):>5.1f}s  {j['title']}"
            + (f"  [{j['offer_id']}]" if j.get("offer_id") else "")
            for j in items
        )

    @mcp.tool(annotations=READ, structured_output=False)
    async def get_reel(
        job_id: str,
        frames: Annotated[int, Field(ge=0, le=8, description="Preview frames to return")] = 4,
    ) -> list[ContentBlock]:
        """Details of one reel with preview frames."""
        from ..server import _text

        job = jobs.load(job_id)
        blocks: list[ContentBlock] = [_text(summary(job))]
        if frames and (jobs.job_dir(job_id) / "reel.mp4").is_file():
            blocks += await run(previews, job_id, frames)
        return blocks

    @mcp.tool(annotations=PUBLISH, structured_output=False)
    async def publish_reel(
        job_id: str,
        targets: Annotated[list[Literal["telegram", "youtube"]] | None,
                           Field(description="Default: all configured")] = None,
    ) -> str:
        """Publish a ready reel. Only after the user approved it. Repeating skips targets already done."""
        result = await run(publish.publish, job_id, targets)
        return f"Published: {result['published'] or 'nothing'}" + (
            f"\nErrors: {result['errors']}" if result["errors"] else "")

    @mcp.tool(annotations=PUBLISH, structured_output=False)
    async def reject_reel(job_id: str) -> str:
        """Mark a reel as rejected and delete its media files."""
        with jobs.lock(job_id):
            job = jobs.load(job_id)
            job["status"] = "rejected"
            jobs.save(job)
            jobs.drop_media(job_id)
        return f"Reel {job_id} rejected"

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=True), structured_output=False)
    async def scout_channel(
        url: Annotated[str, Field(description="Channel URL (YouTube @handle, VK, TikTok…). For YouTube "
                                              "the Shorts tab is used unless the URL points to another tab")],
        limit: Annotated[int, Field(ge=5, le=200)] = 50,
        top: Annotated[int, Field(ge=1, le=50, description="How many best videos to show")] = 15,
    ) -> str:
        """Competitor research: the channel's most viewed recent videos (title, views, link).
        Watch the best ones with analyze_video to learn their hooks and structure."""
        return await run(_scout, url, limit, top)


def process(job: dict, after: str, progress=lambda _f, _m: None) -> str:
    """Render a reel and do the follow-up (review / publish). Returns a note for the summary."""
    offer = jobs.get_offer(job.get("offer_id"))
    workdir = jobs.job_dir(job["id"])
    try:
        with jobs.lock(job["id"]):
            job["status"] = "rendering"
            job.pop("error", None)
            job.pop("warnings", None)
            jobs.save(job)
            started = time.monotonic()
            video = render.render(job, workdir, offer, progress)
            job["duration"] = round(fr.probe_duration(video), 2)
            job["render_seconds"] = round(time.monotonic() - started, 1)
            job["status"] = "ready"
            jobs.save(job)
    except Exception as exc:
        job["status"] = "failed"
        job["error"] = str(exc)[:500]
        jobs.save(job)
        raise
    if after == "review":
        if reels_settings.review_enabled:
            publish.send_for_review(job["id"])
            return "\nSent to the Telegram review chat: publish with the button there."
        return "\nTelegram review chat is not configured; publish with publish_reel after approval."
    if after == "publish":
        return f"\nPublish result: {publish.publish(job['id'])}"
    return ""


def _process_quietly(job: dict, after: str) -> None:
    try:
        process(job, after)
    except Exception as exc:
        log.warning("Background reel %s failed: %s", job["id"], exc)
        publish.notify(f"Ролик {job['id']} «{job['title']}» не собрался: {str(exc)[:300]}")


def effective_animate(scene: dict) -> bool:
    """Explicit flag wins; otherwise REELS_ANIMATE_ALL decides (user video clips are never re-animated)."""
    if scene.get("animate") is not None:
        return bool(scene["animate"])
    return reels_settings.animate_all and reels_settings.video != "none"


def _scout(url: str, limit: int, top: int) -> str:
    from yt_dlp import YoutubeDL

    target = url.rstrip("/")
    is_yt_channel = "youtube.com/@" in target or "/channel/" in target or "/c/" in target
    if is_yt_channel and target.split("/")[-1] not in ("shorts", "videos", "streams"):
        target += "/shorts"
    opts = src_mod._ydl_opts(extract_flat="in_playlist", playlistend=limit, noplaylist=False)
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=False)
    except Exception as exc:
        raise src_mod._friendly(exc) from exc
    entries = [e for e in (info.get("entries") or []) if e]
    if not entries:
        return f"No videos found at {target}"
    entries.sort(key=lambda e: e.get("view_count") or 0, reverse=True)
    lines = [f"{info.get('channel') or info.get('title') or target}: {len(entries)} videos checked, top {top} by views"]
    for e in entries[:top]:
        views = e.get("view_count")
        shown = f"{views:,}".replace(",", " ") if views is not None else "?"
        link = e.get("url") or e.get("webpage_url") or e.get("id")
        lines.append(f"{shown:>13} | {e.get('title')} | {link}")
    return "\n".join(lines)


def cleanup_failed(max_age_days: float = 7) -> None:
    """Remove media of failed/rejected reels older than `max_age_days` (called on start)."""
    cutoff = time.time() - max_age_days * 86400
    for j in jobs.all_jobs():
        d = jobs.job_dir(j["id"])
        if j["status"] in ("failed", "rejected") and (d / "job.json").stat().st_mtime < cutoff:
            shutil.rmtree(d, ignore_errors=True)
