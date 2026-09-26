import json
import subprocess

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from video_mcp import server
from video_mcp.reels import jobs, publish, render, tts
from video_mcp.reels import tools as reels_tools
from video_mcp.reels.config import reels_settings


def fake_synthesize(text, out):
    """1.2 s of tone per scene with evenly spread word timings (no network)."""
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=300:duration=1.2", "-c:a", "libmp3lame", str(out)], check=True)
    return tts._even_words(text, 0.05, 1.1)


@pytest.fixture(autouse=True)
def reels_env(monkeypatch):
    monkeypatch.setattr(reels_settings, "images", "placeholder")
    monkeypatch.setattr(reels_settings, "tg_token", "")
    monkeypatch.setattr(reels_settings, "yt_client_id", "")
    monkeypatch.setattr(tts, "synthesize", fake_synthesize)
    reels_tools.register(server.mcp, server._run)


async def call(name, **args):
    async with create_connected_server_and_client_session(server.mcp._mcp_server) as client:
        result = await client.call_tool(name, args)
    return result


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                          "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_words_from_elevenlabs_alignment():
    chars = list("Привет мир")
    starts = [i * 0.1 for i in range(len(chars))]
    ends = [s + 0.1 for s in starts]
    words = tts.words_from_chars(chars, starts, ends)
    assert [w.text for w in words] == ["Привет", "мир"]
    assert words[0].start == 0.0 and words[1].end == pytest.approx(1.0)


def test_subtitle_chunks_break_on_punctuation_and_length():
    words = tts._even_words("Кофе каждый день, это 66 000 рублей в год.", 0, 4)
    chunks = [c[0] for c in render.chunk_words(words)]
    assert chunks[0] == "Кофе каждый день,"
    assert all(len(c.split()) <= 3 for c in chunks)
    ass = render.build_ass(words, "DejaVu Sans")
    assert "Dialogue: 0,0:00:00.00" in ass and "КОФЕ КАЖДЫЙ ДЕНЬ," in ass


def test_offer_spans():
    scenes = [{"offer": False}, {"offer": True}, {"offer": True}]
    assert render.offer_spans(scenes, [1.0, 2.0, 1.5]) == [(1.0, 3.0), (3.0, 4.5)]


def test_caption_puts_ad_marking_first():
    job = {"title": "Три ошибки с кэшбэком", "description": "Проверь свою карту", "hashtags": ["деньги"]}
    offer = {"advertiser": "Банк", "erid": "abc123", "link": "https://example.com/x", "link_text": "Оформить"}
    text = publish.caption(job, offer, 1024)
    assert text.startswith("Реклама. Банк. erid: abc123")
    assert "Оформить: https://example.com/x" in text and text.endswith("#деньги")
    assert publish.caption(job, None, 1024).startswith("Три ошибки")


async def test_create_reel_renders_vertical_video_with_offer():
    res = await call("save_offer", offer_id="card", advertiser="Банк", erid="abc123",
                     banner="Карта с кэшбэком — ссылка в профиле", link="https://example.com/x")
    assert not res.isError, res.content[0].text
    res = await call("create_reel", title="Три ошибки с кэшбэком", offer_id="card", hashtags=["деньги"], scenes=[
        {"text": "Банк не доплачивает тебе кэшбэк.", "image_prompt": "bank card on a table"},
        {"text": "Проверь категории в начале месяца.", "image_prompt": "calendar"},
        {"text": "Карта с кэшбэком по ссылке в профиле.", "image_prompt": "happy person", "offer": True},
    ])
    assert not res.isError, res.content[0].text
    text = res.content[0].text
    assert "— ready" in text
    assert sum(1 for c in res.content if c.type == "image") == 4
    job_id = text.split()[1]
    video = jobs.job_dir(job_id) / "reel.mp4"
    info = probe(video)
    streams = {s["codec_type"]: s for s in info["streams"]}
    assert (streams["video"]["width"], streams["video"]["height"]) == (1080, 1920)
    assert "audio" in streams
    assert float(info["format"]["duration"]) == pytest.approx(3 * 1.45, abs=0.3)
    assert (jobs.job_dir(job_id) / "marker.txt").read_text() == "Реклама. Банк. erid: abc123"

    listed = (await call("list_reels")).content[0].text
    assert job_id in listed and "[card]" in listed

    # editing one scene re-renders but keeps the other pictures
    other_png = jobs.job_dir(job_id) / "scene00.png"
    mtime = other_png.stat().st_mtime_ns
    res = await call("edit_reel", job_id=job_id, changes=[{"index": 1, "image_prompt": "wall calendar"}])
    assert not res.isError, res.content[0].text
    assert other_png.stat().st_mtime_ns == mtime

    res = await call("publish_reel", job_id=job_id)
    assert res.isError and "No publish targets" in res.content[0].text

    res = await call("reject_reel", job_id=job_id)
    assert not res.isError
    assert not video.exists() and jobs.load(job_id)["status"] == "rejected"


async def test_offer_scene_requires_offer_id():
    res = await call("create_reel", title="x", scenes=[{"text": "текст", "image_prompt": "p", "offer": True}])
    assert res.isError and "offer_id" in res.content[0].text


async def test_unknown_offer_is_rejected():
    res = await call("create_reel", title="x", offer_id="nope", scenes=[{"text": "текст", "image_prompt": "p"}])
    assert res.isError and "Unknown offer" in res.content[0].text


async def test_scene_with_local_video_media(video_dir):
    res = await call("create_reel", title="Клип", scenes=[{"text": "Смотри внимательно.", "media": "colors.mp4"}])
    assert not res.isError, res.content[0].text
    assert "— ready" in res.content[0].text
