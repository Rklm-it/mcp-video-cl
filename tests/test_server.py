import base64
import io

import httpx
import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from PIL import Image

from video_mcp import server
from video_mcp.config import settings


async def call(name: str, **args):
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool(name, args)
    assert not result.isError, result.content[0].text
    return result.content


def texts(content) -> str:
    return "\n".join(c.text for c in content if c.type == "text")


def images(content):
    return [Image.open(io.BytesIO(base64.b64decode(c.data))) for c in content if c.type == "image"]


def dominant(img: Image.Image) -> str:
    r, g, b = img.convert("RGB").resize((1, 1)).getpixel((0, 0))
    return max((("red", r), ("green", g), ("blue", b)), key=lambda x: x[1])[0]


async def test_list_local_videos():
    content = await call("list_local_videos")
    assert "colors.mp4" in texts(content)


async def test_analyze_video_local_interleaves_frames_and_speech():
    content = await call("analyze_video", source="colors.mp4")
    text = texts(content)
    imgs = images(content)
    assert "sidecar colors.vtt" in text
    assert "red scene" in text and "turns green" in text and "blue" in text
    assert 3 <= len(imgs) <= 16
    assert {dominant(i) for i in imgs} == {"red", "green", "blue"}
    # every image is preceded by a timestamp label
    kinds = [c.type for c in content]
    assert all(kinds[i - 1] == "text" for i, k in enumerate(kinds) if k == "image")


async def test_analyze_video_brief_has_no_frames():
    content = await call("analyze_video", source="colors.mp4", detail="brief")
    assert not images(content)
    assert "[0:00] Hello, this is the red scene." in texts(content)


async def test_get_frames_at_exact_moments():
    content = await call("get_frames_at", source="colors.mp4", timestamps=["0:02", 6, "10"], frame_width=200)
    imgs = images(content)
    assert [dominant(i) for i in imgs] == ["red", "green", "blue"]
    assert imgs[0].width == 200
    assert "[0:02]" in texts(content) and "[0:10]" in texts(content)


async def test_analyze_moment_uniform_frames():
    content = await call("analyze_moment", source="colors.mp4", start="0:03", end="0:06", frames=4)
    assert len(images(content)) == 4
    assert "turns green" in texts(content)


async def test_get_transcript_range():
    content = await call("get_transcript", source="colors.mp4", start=4, end=8)
    text = texts(content)
    assert "turns green" in text and "red scene" not in text


async def test_errors_are_reported_not_raised():
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool("analyze_video", {"source": "missing.mp4"})
    assert result.isError and "File not found" in result.content[0].text


async def test_url_download_path(http_video):
    """Goes through yt-dlp (generic extractor) + download + cache, like a YouTube link would."""
    content = await call("get_frames", source=http_video, max_frames=6)
    imgs = images(content)
    assert {dominant(i) for i in imgs} == {"red", "green", "blue"}
    cached = list(settings.cache_dir.glob("url_*/video.*"))
    assert len(cached) == 1
    # second call reuses the cached download
    content = await call("get_frames_at", source=http_video, timestamps=[9])
    assert dominant(images(content)[0]) == "blue"


@pytest.fixture
def http_app(monkeypatch):
    monkeypatch.setattr(settings, "token", "s3cret")
    return server.create_app()


INIT = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {},
               "clientInfo": {"name": "test", "version": "1"}},
}
HEADERS = {"accept": "application/json, text/event-stream", "content-type": "application/json"}


async def _post(app, path, headers):
    transport = httpx.ASGITransport(app=app)
    async with server.mcp.session_manager.run():
        async with httpx.AsyncClient(transport=transport, base_url="https://video.example.com") as client:
            return await client.post(path, json=INIT, headers={**HEADERS, **headers})


async def test_http_requires_token(http_app):
    resp = await _post(http_app, "/mcp", {})
    assert resp.status_code == 401


async def test_http_bearer_and_secret_path(http_app):
    server.mcp._session_manager = None
    app = server.create_app()
    resp = await _post(app, "/mcp", {"authorization": "Bearer s3cret"})
    assert resp.status_code == 200 and "serverInfo" in resp.text
    server.mcp._session_manager = None
    app = server.create_app()
    resp = await _post(app, "/s3cret/mcp", {})
    assert resp.status_code == 200 and "serverInfo" in resp.text


async def test_health_is_public(http_app):
    transport = httpx.ASGITransport(app=http_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://x") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        # OAuth discovery must say "no OAuth" (404), not "unauthorized"
        for path in ("/.well-known/oauth-protected-resource", "/.well-known/oauth-authorization-server"):
            assert (await client.get(path)).status_code == 404


async def test_url_section_download_keeps_timeline(http_video, monkeypatch):
    """Long videos download only the requested section; frame timestamps must stay on the video timeline."""
    monkeypatch.setattr(settings, "section_download_minutes", 0.05)  # treat the 12 s clip as "long"
    content = await call("analyze_moment", source=http_video, start="0:08.5", end="0:11", frames=3)
    assert [dominant(i) for i in images(content)] == ["blue", "blue", "blue"]
    assert "everything is blue" not in texts(content)  # no subtitles for a bare mp4 link
    assert not list(settings.cache_dir.glob("url_*/video.*"))
    assert list(settings.cache_dir.glob("url_*/section_*"))
    content = await call("get_frames_at", source=http_video, timestamps=["0:05"])
    assert dominant(images(content)[0]) == "green"


async def test_whisper_fallback_when_no_subtitles(http_video, monkeypatch):
    """No subtitles -> audio is downloaded, cut to 16 kHz wav and passed to Whisper (mocked here)."""
    from video_mcp import transcript as tr

    calls = []

    def fake_transcribe(wav, language=None, offset=0.0):
        import subprocess

        probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels",
                                "-of", "csv=p=0", str(wav)], capture_output=True, text=True).stdout.strip()
        calls.append((probe, offset))
        return [tr.Segment(offset + 1, offset + 3, "recognised speech")], "en"

    monkeypatch.setattr(settings, "whisper_enabled", True)
    monkeypatch.setattr(tr, "whisper_available", lambda: True)
    monkeypatch.setattr(tr, "transcribe", fake_transcribe)
    content = await call("get_transcript", source=http_video)
    assert "recognised speech" in texts(content) and "whisper" in texts(content)
    assert calls == [("16000,1", 0.0)]
    assert list(settings.cache_dir.glob("url_*/audio.*"))
    # cached: Whisper is not run again
    await call("analyze_video", source=http_video, detail="brief")
    assert len(calls) == 1


def test_access_log_hides_token_and_health():
    import logging

    flt = server.AccessLogFilter("s3cret")

    def record(path):
        return logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                                 ("1.2.3.4:0", "POST", path, "1.1", 200), None)

    rec = record("/s3cret/mcp")
    assert flt.filter(rec) and "s3cret" not in rec.getMessage() and "/***/mcp" in rec.getMessage()
    assert not flt.filter(record("/health"))
    rec = record("/.env")
    assert flt.filter(rec) and rec.getMessage().endswith('"POST /.env HTTP/1.1" 200')
