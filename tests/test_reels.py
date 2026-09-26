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


def make_clip(path, seconds=2, color="red"):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", f"color=c={color}:s=720x1280:d={seconds}:r=24", "-pix_fmt", "yuv420p", str(path)],
                   check=True)
    return path


async def test_animated_scene_uses_generated_clip(monkeypatch):
    from video_mcp.reels import video_gen

    calls = []

    def fake_animate(image, prompt, seconds, out):
        calls.append((prompt, seconds))
        return make_clip(out)

    monkeypatch.setattr(reels_settings, "video", "veo")
    monkeypatch.setattr(video_gen, "animate", fake_animate)
    res = await call("create_reel", title="Хук", scenes=[
        {"text": "Ты теряешь деньги каждый день.", "image_prompt": "wallet on fire", "animate": True},
        {"text": "Вот почему.", "image_prompt": "calculator"},
    ])
    assert not res.isError, res.content[0].text
    text = res.content[0].text
    assert "[video]" in text and "Warning" not in text
    assert calls and calls[0][0] == "wallet on fire" and calls[0][1] > 1.2
    job_id = text.split()[1]
    assert (jobs.job_dir(job_id) / "scene00.ai.mp4").exists()


async def test_failed_animation_falls_back_to_picture(monkeypatch):
    from video_mcp.reels import video_gen

    def broken(*_args):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(reels_settings, "video", "veo")
    monkeypatch.setattr(video_gen, "animate", broken)
    res = await call("create_reel", title="x", scenes=[{"text": "Текст.", "image_prompt": "p", "animate": True}])
    assert not res.isError, res.content[0].text
    assert "— ready" in res.content[0].text and "quota exceeded" in res.content[0].text


async def test_animated_scene_limit(monkeypatch):
    monkeypatch.setattr(reels_settings, "max_animated", 1)
    res = await call("create_reel", title="x", scenes=[
        {"text": "a", "image_prompt": "p", "animate": True}, {"text": "b", "image_prompt": "p", "animate": True}])
    assert res.isError and "limit is 1" in res.content[0].text


async def test_background_music_is_mixed(tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=660:duration=1", "-c:a", "libmp3lame", str(music / "calm.mp3")], check=True)
    monkeypatch.setattr(reels_settings, "music_dir", str(music))
    res = await call("create_reel", title="x", scenes=[{"text": "Музыка играет.", "image_prompt": "p"},
                                                       {"text": "И дальше.", "image_prompt": "q"}])
    assert not res.isError, res.content[0].text
    assert "Music: calm.mp3" in res.content[0].text
    job_id = res.content[0].text.split()[1]
    info = probe(jobs.job_dir(job_id) / "reel.mp4")
    assert float(info["format"]["duration"]) == pytest.approx(2 * 1.45, abs=0.3)

    res = await call("create_reel", title="y", music="none", scenes=[{"text": "Тишина.", "image_prompt": "p"}])
    assert not res.isError and "Music:" not in res.content[0].text


def test_veo_request_flow_through_reseller(tmp_path, monkeypatch):
    from PIL import Image

    from video_mcp.reels import gemini, video_gen

    monkeypatch.setattr(reels_settings, "gemini_key", "k123")
    monkeypatch.setattr(reels_settings, "gemini_auth", "bearer")
    monkeypatch.setattr(reels_settings, "gemini_base_url", "https://api.example.ru/google/v1beta")
    monkeypatch.setattr(reels_settings, "video", "veo")
    monkeypatch.setattr(video_gen, "POLL_SECONDS", 0)
    seen = {}

    class Resp:
        def __init__(self, data, status=200):
            self._data, self.status_code, self.text = data, status, json.dumps(data)

        def json(self):
            return self._data

    def fake_post(url, headers, json, timeout):
        seen["post"] = (url, headers, json)
        return Resp({"name": "models/veo/operations/op1"})

    polls = iter([{"done": False}, {"done": True, "response": {"generateVideoResponse": {"generatedSamples": [
        {"video": {"uri": "https://generativelanguage.googleapis.com/v1beta/files/abc:download?alt=media"}}]}}}])

    def fake_get(url, headers, timeout):
        seen.setdefault("gets", []).append(url)
        return Resp(next(polls))

    def fake_download(uri, out):
        seen["download"] = gemini.proxied(uri)
        return make_clip(out)

    monkeypatch.setattr(video_gen.httpx, "post", fake_post)
    monkeypatch.setattr(video_gen.httpx, "get", fake_get)
    monkeypatch.setattr(gemini, "download", fake_download)
    img = tmp_path / "f.png"
    Image.new("RGB", (1080, 1920), "blue").save(img)
    video_gen.animate(img, "wallet", 5.1, tmp_path / "out.mp4")

    url, headers, body = seen["post"]
    assert url == "https://api.example.ru/google/v1beta/models/veo-3.1-fast-generate-preview:predictLongRunning"
    assert headers == {"Authorization": "Bearer k123"}
    assert body["parameters"]["durationSeconds"] == 6 and body["parameters"]["aspectRatio"] == "9:16"
    assert seen["gets"][0] == "https://api.example.ru/google/v1beta/models/veo/operations/op1"
    assert seen["download"] == "https://api.example.ru/google/v1beta/files/abc:download?alt=media"
    assert video_gen.clip_seconds(3) == 4 and video_gen.clip_seconds(12) == 8


def test_openai_compatible_tts_gateway(tmp_path, monkeypatch):
    mp3 = tmp_path / "src.mp3"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=300:duration=2", "-c:a", "libmp3lame", str(mp3)], check=True)
    seen = {}

    class Resp:
        status_code = 200
        content = mp3.read_bytes()
        text = ""

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, body=json)
        return Resp()

    monkeypatch.setattr(reels_settings, "openai_key", "tw-key")
    monkeypatch.setattr(reels_settings, "openai_base_url", "https://api.timeweb.ai/v1")
    monkeypatch.setattr(tts.httpx, "post", fake_post)
    words = tts._openai("Карта с кэшбэком вернёт часть трат", tmp_path / "out.mp3")
    assert seen["url"] == "https://api.timeweb.ai/v1/audio/speech"
    assert seen["headers"] == {"Authorization": "Bearer tw-key"}
    assert seen["body"]["model"] == "gpt-4o-mini-tts" and seen["body"]["input"].startswith("Карта")
    assert [w.text for w in words][0] == "Карта" and len(words) == 6
    assert words[0].start == pytest.approx(0.08) and words[-1].end == pytest.approx(2 - 0.12, abs=0.1)
    assert all(a.end == pytest.approx(b.start) for a, b in zip(words, words[1:]))
