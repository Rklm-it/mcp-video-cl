"""YouTube channel analytics: what Studio shows only to the owner (retention, traffic sources, view %).

Uses the same OAuth client as the upload; the refresh token must include the read-only scopes
(run `video-mcp-youtube-auth` again after upgrading).
"""

from __future__ import annotations

import datetime as dt

import httpx

from .publish import _youtube_token

DATA = "https://www.googleapis.com/youtube/v3"
ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"

VIDEO_METRICS = ("views", "estimatedMinutesWatched", "averageViewDuration", "averageViewPercentage",
                 "likes", "comments", "shares", "subscribersGained")
SOURCES = {
    "SHORTS": "лента Shorts", "YT_SEARCH": "поиск YouTube", "YT_CHANNEL": "страница канала",
    "SUBSCRIBER": "подписки", "YT_OTHER_PAGE": "другие страницы YouTube", "RELATED_VIDEO": "похожие видео",
    "EXT_URL": "внешние сайты", "NO_LINK_OTHER": "прямые заходы", "PLAYLIST": "плейлисты",
    "NOTIFICATION": "уведомления", "BROWSE": "главная и рекомендации",
}


class StatsError(RuntimeError):
    pass


def _get(url: str, token: str, params: dict) -> dict:
    resp = httpx.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=60)
    if resp.status_code >= 400:
        raise StatsError(f"YouTube API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def _report(token: str, start: str, end: str, metrics: str, **extra) -> list[dict]:
    data = _get(ANALYTICS, token, {"ids": "channel==MINE", "startDate": start, "endDate": end,
                                   "metrics": metrics, **extra})
    names = [h["name"] for h in data.get("columnHeaders", [])]
    return [dict(zip(names, row)) for row in data.get("rows", [])]


def _uploads(token: str, limit: int = 50) -> tuple[dict, list[dict]]:
    ch = _get(f"{DATA}/channels", token, {"part": "snippet,statistics,contentDetails", "mine": "true"})
    if not ch.get("items"):
        raise StatsError("No channel on this Google account")
    channel = ch["items"][0]
    playlist = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    items = _get(f"{DATA}/playlistItems", token,
                 {"part": "contentDetails", "playlistId": playlist, "maxResults": min(limit, 50)})
    ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    if not ids:
        return channel, []
    vids = _get(f"{DATA}/videos", token, {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)})
    return channel, vids.get("items", [])


def _secs(seconds) -> str:
    s = int(round(float(seconds or 0)))
    return f"{s // 60}:{s % 60:02d}"


def report(video: str | None = None, days: int = 28) -> str:
    """Text report: the whole channel (one line per video) or one video in depth."""
    token = _youtube_token()
    end = dt.date.today()
    start = (end - dt.timedelta(days=days)).isoformat()
    end_s = end.isoformat()
    channel, videos = _uploads(token)
    titles = {v["id"]: v["snippet"]["title"] for v in videos}
    st = channel.get("statistics", {})
    lines = [f"Канал «{channel['snippet']['title']}»: подписчиков {st.get('subscriberCount', '—')}, "
             f"просмотров {st.get('viewCount', '—')}, видео {st.get('videoCount', '—')}.",
             f"Период: {start} — {end_s}."]

    if video:
        vid = video.rsplit("/", 1)[-1].split("?")[0]
        rows = _report(token, start, end_s, ",".join(VIDEO_METRICS), filters=f"video=={vid}")
        r = rows[0] if rows else {}
        lines.append(f"\n«{titles.get(vid, vid)}» ({vid})")
        lines.append(f"Просмотры {r.get('views', 0)}, лайки {r.get('likes', 0)}, комментарии {r.get('comments', 0)}, "
                     f"репосты {r.get('shares', 0)}, подписчиков +{r.get('subscribersGained', 0)}.")
        lines.append(f"Средний просмотр {_secs(r.get('averageViewDuration'))} "
                     f"({float(r.get('averageViewPercentage') or 0):.0f}% длины), "
                     f"всего {float(r.get('estimatedMinutesWatched') or 0) / 60:.1f} ч.")
        src = _report(token, start, end_s, "views", dimensions="insightTrafficSourceType",
                      filters=f"video=={vid}", sort="-views")
        total = sum(int(s["views"]) for s in src) or 1
        if src:
            lines.append("Откуда зрители: " + ", ".join(
                f"{SOURCES.get(s['insightTrafficSourceType'], s['insightTrafficSourceType'])} "
                f"{100 * int(s['views']) / total:.0f}%" for s in src))
        ret = _report(token, start, end_s, "audienceWatchRatio", dimensions="elapsedVideoTimeRatio",
                      filters=f"video=={vid}")
        if ret:
            dur = _duration(next((v for v in videos if v["id"] == vid), None))
            points = [r for i, r in enumerate(ret) if i % 10 == 0 or i == len(ret) - 1]
            lines.append("Удержание (доля зрителей, ещё смотрящих): " + ", ".join(
                f"{_secs(float(p['elapsedVideoTimeRatio']) * dur) if dur else p['elapsedVideoTimeRatio']} — "
                f"{100 * float(p['audienceWatchRatio']):.0f}%" for p in points))
        else:
            lines.append("Удержание: данных пока нет (YouTube считает до двух суток).")
        return "\n".join(lines)

    rows = _report(token, start, end_s, ",".join(VIDEO_METRICS), dimensions="video", sort="-views",
                   maxResults=50)
    if not rows:
        lines.append("За период просмотров нет (данные приходят с задержкой до двух суток).")
    for r in rows:
        lines.append(f"• {titles.get(r['video'], r['video'])[:60]} — {r['views']} просм., "
                     f"ср. {_secs(r['averageViewDuration'])} ({float(r['averageViewPercentage']):.0f}%), "
                     f"лайки {r['likes']}, подписки +{r['subscribersGained']} — youtu.be/{r['video']}")
    return "\n".join(lines)


def _duration(video: dict | None) -> float:
    """ISO 8601 duration (PT41S, PT1M5S) in seconds; 0 if unknown."""
    if not video:
        return 0.0
    iso = video.get("contentDetails", {}).get("duration", "")
    total, num = 0.0, ""
    for ch in iso.removeprefix("PT"):
        if ch.isdigit() or ch == ".":
            num += ch
        elif num:
            total += float(num) * {"H": 3600, "M": 60, "S": 1}.get(ch, 0)
            num = ""
    return total
