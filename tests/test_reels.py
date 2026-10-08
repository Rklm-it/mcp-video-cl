import io
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
    job = {"id": "0926-1200-ab12", "title": "Три ошибки с кэшбэком", "description": "Проверь свою карту",
           "hashtags": ["деньги"]}
    offer = {"advertiser": "Банк", "erid": "abc123", "link": "https://example.com/x?sub1={platform}&sub2={reel}",
             "link_text": "Оформить"}
    text = publish.caption(job, offer, 1024)
    assert text.startswith("Реклама. Банк. erid: abc123")
    assert "Оформить: https://example.com/x?sub1=tg&sub2=0926-1200-ab12" in text and text.endswith("#деньги")
    assert "sub1=yt&" in publish.caption(job, offer, 4900, "yt")
    assert publish.caption(job, None, 1024).startswith("Три ошибки")


async def test_create_reel_renders_vertical_video_with_offer():
    res = await call("save_offer", offer_id="card", advertiser="Банк", erid="abc123",
                     banner="Карта с кэшбэком — ссылка в профиле", link="https://example.com/x")
    assert not res.isError, res.content[0].text
    res = await call("create_reel", background=False, title="Три ошибки с кэшбэком", offer_id="card", hashtags=["деньги"], scenes=[
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
    res = await call("edit_reel", job_id=job_id, background=False, changes=[{"index": 1, "image_prompt": "wall calendar"}])
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
    res = await call("create_reel", background=False, title="Клип", scenes=[{"text": "Смотри внимательно.", "media": "colors.mp4"}])
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

    def fake_animate(image, prompt, seconds, out, context=True):
        calls.append((prompt, seconds))
        return make_clip(out)

    monkeypatch.setattr(reels_settings, "video", "veo")
    monkeypatch.setattr(video_gen, "animate", fake_animate)
    res = await call("create_reel", title="Хук", background=False, scenes=[
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

    def broken(*_args, **_kwargs):
        raise RuntimeError("quota exceeded")

    monkeypatch.setattr(reels_settings, "video", "veo")
    monkeypatch.setattr(video_gen, "animate", broken)
    res = await call("create_reel", title="x", background=False,
                     scenes=[{"text": "Текст.", "image_prompt": "p", "animate": True}])
    assert not res.isError, res.content[0].text
    assert "— ready" in res.content[0].text and "quota exceeded" in res.content[0].text


async def test_animated_scene_limit(monkeypatch):
    monkeypatch.setattr(reels_settings, "max_animated", 1)
    res = await call("create_reel", title="x", scenes=[
        {"text": "a", "image_prompt": "p", "animate": True}, {"text": "b", "image_prompt": "p", "animate": True}])
    assert res.isError and "limit is 1" in res.content[0].text


async def test_scene_label_is_drawn_on_top():
    res = await call("create_reel", background=False, title="x", scenes=[
        {"text": "Это DPI.", "image_prompt": "p", "label": "DPI"}, {"text": "Дальше.", "image_prompt": "q"}])
    assert not res.isError, res.content[0].text
    job_id = res.content[0].text.split()[1]
    workdir = jobs.job_dir(job_id)
    assert (workdir / "label00.txt").read_text() == "DPI"
    assert not (workdir / "label01.txt").exists()
    assert (workdir / "reel.mp4").exists()


async def test_setting_none_skips_scene_context(monkeypatch):
    from video_mcp.reels import images

    seen = []
    real = images.generate
    monkeypatch.setattr(images, "generate", lambda prompt, out, seed, context=True: seen.append(context)
                        or real(prompt, out, seed, context))
    res = await call("create_reel", background=False, title="x", setting="none",
                     scenes=[{"text": "Пакеты летят.", "image_prompt": "packets"}])
    assert not res.isError, res.content[0].text
    res = await call("create_reel", background=False, title="y", scenes=[{"text": "Улица.", "image_prompt": "street"}])
    assert not res.isError, res.content[0].text
    assert seen == [False, True]


async def test_background_music_is_mixed(tmp_path, monkeypatch):
    music = tmp_path / "music"
    music.mkdir()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=660:duration=1", "-c:a", "libmp3lame", str(music / "calm.mp3")], check=True)
    monkeypatch.setattr(reels_settings, "music_dir", str(music))
    res = await call("create_reel", background=False, title="x", scenes=[{"text": "Музыка играет.", "image_prompt": "p"},
                                                       {"text": "И дальше.", "image_prompt": "q"}])
    assert not res.isError, res.content[0].text
    assert "Music: calm.mp3" in res.content[0].text
    job_id = res.content[0].text.split()[1]
    info = probe(jobs.job_dir(job_id) / "reel.mp4")
    assert float(info["format"]["duration"]) == pytest.approx(2 * 1.45, abs=0.3)

    res = await call("create_reel", background=False, title="y", music="none", scenes=[{"text": "Тишина.", "image_prompt": "p"}])
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
    monkeypatch.setattr(video_gen.net, "get", fake_get)
    monkeypatch.setattr(gemini, "download", fake_download)
    img = tmp_path / "f.png"
    Image.new("RGB", (1080, 1920), "blue").save(img)
    video_gen.animate(img, "wallet", 5.1, tmp_path / "out.mp4")

    url, headers, body = seen["post"]
    assert url == "https://api.example.ru/google/v1beta/models/veo-3.1-lite-generate-preview:predictLongRunning"
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
    monkeypatch.setattr(tts.net, "post", fake_post)
    words = tts._openai("Карта с кэшбэком вернёт часть трат", tmp_path / "out.mp3")
    assert seen["url"] == "https://api.timeweb.ai/v1/audio/speech"
    assert seen["headers"] == {"Authorization": "Bearer tw-key"}
    assert seen["body"]["model"] == "gpt-4o-mini-tts" and seen["body"]["input"].startswith("Карта")
    assert [w.text for w in words][0] == "Карта" and len(words) == 6
    assert words[0].start == pytest.approx(0.08) and words[-1].end == pytest.approx(2 - 0.12, abs=0.1)
    assert all(a.end == pytest.approx(b.start) for a, b in zip(words, words[1:]))


async def test_animate_all_renders_in_background(monkeypatch):
    import asyncio

    from video_mcp.reels import video_gen

    calls = []

    def fake_animate(image, prompt, seconds, out, context=True):
        calls.append(prompt)
        return make_clip(out, color="blue")

    monkeypatch.setattr(reels_settings, "video", "veo")
    monkeypatch.setattr(reels_settings, "animate_all", True)
    monkeypatch.setattr(reels_settings, "max_animated", 8)
    monkeypatch.setattr(video_gen, "animate", fake_animate)
    res = await call("create_reel", title="Полное видео", scenes=[
        {"text": "Первая сцена.", "image_prompt": "one"},
        {"text": "Вторая сцена.", "image_prompt": "two"},
        {"text": "Третья без видео.", "image_prompt": "three", "animate": False},
    ])
    assert not res.isError, res.content[0].text
    text = res.content[0].text
    assert "— rendering" in text and "Rendering in the background" in text
    job_id = text.split()[1]
    for _ in range(120):
        if jobs.load(job_id)["status"] != "rendering":
            break
        await asyncio.sleep(0.25)
    job = jobs.load(job_id)
    assert job["status"] == "ready", job.get("error")
    assert sorted(calls) == ["one", "two"]
    assert [s["animate"] for s in job["scenes"]] == [True, True, False]


def test_forbidden_word_stems_match_word_start_only():
    offer = {"forbidden_words": ["работ", "зарплат"]}
    assert jobs.forbidden_hits(offer, ["Как заработать курьером", "Доход до 3400 ₽ в день"]) == []
    hits = jobs.forbidden_hits(offer, ["Работа курьером без опыта", "какая зарплата?"])
    assert len(hits) == 2 and "«Работа»" in hits[0] and "«зарплата»" in hits[1]


async def test_reel_with_banned_words_is_refused():
    res = await call("save_offer", offer_id="eda", advertiser="Яндекс", erid="Ab12", banner="Доход до 3400 ₽ в день",
                     forbidden_words=["работ", "подработ"])
    assert not res.isError
    res = await call("create_reel", title="Подработка курьером", offer_id="eda",
                     scenes=[{"text": "Как заработать на доставке.", "image_prompt": "p", "offer": True}])
    assert res.isError and "«Подработка»" in res.content[0].text
    res = await call("create_reel", title="Доход на доставке", offer_id="eda", background=False,
                     scenes=[{"text": "Как заработать на доставке.", "image_prompt": "p", "offer": True}])
    assert not res.isError, res.content[0].text


def test_cleanup_old_drops_media_of_old_published_reels(tmp_path):
    import os
    import time as _time

    old = {"id": "0901-1000-aaaa", "created": "2026-09-01 10:00:00", "status": "published", "title": "t",
           "scenes": []}
    fresh = dict(old, id="0926-1000-bbbb", created="2026-09-26 10:00:00")
    failed = dict(old, id="0901-1000-cccc", status="failed")
    for j in (old, fresh, failed):
        jobs.save(j)
        (jobs.job_dir(j["id"]) / "reel.mp4").write_bytes(b"x")
    past = _time.time() - 10 * 86400
    for j in (old, failed):
        os.utime(jobs.job_dir(j["id"]) / "job.json", (past, past))
    reels_tools.cleanup_old()
    assert not (jobs.job_dir(old["id"]) / "reel.mp4").exists() and (jobs.job_dir(old["id"]) / "job.json").exists()
    assert (jobs.job_dir(fresh["id"]) / "reel.mp4").exists()
    assert not jobs.job_dir(failed["id"]).exists()


def test_net_retries_server_errors(monkeypatch):
    import httpx

    from video_mcp.reels import net

    answers = []
    calls = []

    def fake_request(method, url, **kwargs):
        calls.append(url)
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(net.httpx, "request", fake_request)
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    answers[:] = [httpx.Response(500), httpx.ConnectError("reset"), httpx.Response(429), httpx.Response(200)]
    assert net.get("https://x").status_code == 200
    assert len(calls) == 4

    monkeypatch.setattr(net, "RETRY_DELAYS", (1,))
    answers[:] = [httpx.Response(502), httpx.Response(502)]
    assert net.post("https://x").status_code == 502
    answers[:] = [httpx.ConnectError("a"), httpx.ConnectError("b")]
    with pytest.raises(httpx.ConnectError):
        net.get("https://x")
    answers[:] = [httpx.Response(400)]
    assert net.get("https://x").status_code == 400
    assert answers == []


def test_openai_tts_drops_instructions_when_gateway_fails(monkeypatch, tmp_path):
    import httpx

    from video_mcp import frames
    from video_mcp.reels import net

    bodies = []

    def fake_post(url, json, **kwargs):
        bodies.append(dict(json))
        return httpx.Response(500 if "instructions" in json else 200, content=b"mp3")

    monkeypatch.setattr(reels_settings, "openai_key", "k")
    monkeypatch.setattr(reels_settings, "openai_tts_instructions", "бодро")
    monkeypatch.setattr(net, "post", fake_post)
    monkeypatch.setattr(frames, "probe_duration", lambda path: 2.0)
    words = tts._openai("раз два", tmp_path / "v.mp3")
    assert [w.text for w in words] == ["раз", "два"]
    assert "instructions" in bodies[0] and "instructions" not in bodies[1]


def test_pollinations_watermark_strip_is_cut(monkeypatch, tmp_path):
    import io

    from PIL import Image

    from video_mcp.reels import images

    picture = Image.new("RGB", (1080, 1920), "blue")
    picture.paste(Image.new("RGB", (300, 60), "white"), (760, 1840))  # the logo
    buf = io.BytesIO()
    picture.save(buf, format="PNG")
    monkeypatch.setattr(reels_settings, "images", "pollinations")
    monkeypatch.setattr(images, "_pollinations", lambda prompt, seed: buf.getvalue())
    out = Image.open(images.generate("cat", tmp_path / "p.png", 1))
    assert out.size == (1080, 1920)
    assert max(out.convert("L").getdata()) < 100  # no white logo left


def test_openai_style_videos_api(tmp_path, monkeypatch):
    import base64

    import httpx
    from PIL import Image

    from video_mcp.reels import video_gen

    monkeypatch.setattr(reels_settings, "video", "openai")
    monkeypatch.setattr(reels_settings, "video_base_url", "https://api.example.ru/v1/")
    monkeypatch.setattr(reels_settings, "video_key", "k1")
    monkeypatch.setattr(reels_settings, "veo_model", "google/veo-3.1-lite")
    monkeypatch.setattr(reels_settings, "veo_resolution", "720p")
    monkeypatch.setattr(video_gen, "POLL_SECONDS", 0)
    seen = {}

    def fake_post(url, headers, timeout, json):
        seen.update(url=url, headers=headers, data=json)
        first = json["frame_images"][0]
        assert first["frame_type"] == "first_frame" and first["type"] == "image_url"
        head, b64 = first["image_url"]["url"].split(",", 1)
        assert head == "data:image/jpeg;base64"
        seen["frame"] = Image.open(io.BytesIO(base64.b64decode(b64))).size
        return httpx.Response(202, json={"id": "video_1", "status": "pending"})

    content = "https://api.example.ru/v1/videos/video_1/content?index=0"
    polls = iter([{"id": "video_1", "status": "pending"},
                  {"id": "video_1", "status": "completed", "unsigned_urls": [content]}])

    def fake_get(url, headers, timeout, **kwargs):
        seen.setdefault("gets", []).append(url)
        if "/content" in url:
            return httpx.Response(200, content=b"mp4")
        return httpx.Response(200, json=next(polls))

    monkeypatch.setattr(video_gen.httpx, "post", fake_post)
    monkeypatch.setattr(video_gen.net, "get", fake_get)
    img = tmp_path / "f.png"
    Image.new("RGB", (1080, 1920), "blue").save(img)
    out = video_gen.animate(img, "wallet", 7.2, tmp_path / "out.mp4")

    assert out.read_bytes() == b"mp4"
    assert seen["url"] == "https://api.example.ru/v1/videos"
    assert seen["headers"] == {"Authorization": "Bearer k1"}
    assert seen["data"]["model"] == "google/veo-3.1-lite" and seen["data"]["duration"] == 8
    assert seen["data"]["aspect_ratio"] == "9:16" and seen["data"]["resolution"] == "720p"
    assert seen["data"]["generate_audio"] is False and seen["frame"] == (720, 1280)
    assert seen["gets"][-1] == content

    polls = iter([{"id": "video_1", "status": "failed", "error": {"message": "blocked"}}])
    with pytest.raises(RuntimeError, match="blocked"):
        video_gen.animate(img, "wallet", 3, tmp_path / "out2.mp4")


def test_openai_tts_gemini_voice_comes_as_wav(tmp_path, monkeypatch):
    import httpx

    from video_mcp.frames import probe_duration
    from video_mcp.reels import net

    wav = tmp_path / "src.wav"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi",
                    "-i", "sine=frequency=300:duration=1.5", "-ar", "24000", "-ac", "1", str(wav)], check=True)
    bodies = []

    def fake_post(url, headers, json, timeout):
        bodies.append(dict(json))
        return httpx.Response(200, content=wav.read_bytes(), headers={"content-type": "audio/wav"})

    monkeypatch.setattr(reels_settings, "openai_key", "k")
    monkeypatch.setattr(reels_settings, "openai_tts_model", "gemini/gemini-2.5-flash-preview-tts")
    monkeypatch.setattr(net, "post", fake_post)
    out = tmp_path / "v.mp3"
    words = tts._openai("раз два три", out)
    assert "response_format" not in bodies[0]
    assert out.read_bytes()[:3] == b"ID3" or out.read_bytes()[:2] in (b"\xff\xfb", b"\xff\xf3")
    assert probe_duration(out) == pytest.approx(1.5, abs=0.1) and len(words) == 3
    assert not out.with_suffix(".wav").exists()


def test_scene_context_goes_into_picture_and_video_prompts(tmp_path, monkeypatch):
    import httpx
    from PIL import Image

    from video_mcp.reels import images, video_gen

    assert "Russia" in reels_settings.scene_context
    monkeypatch.setattr(reels_settings, "scene_context", "Setting: Russia")
    prompts = []
    monkeypatch.setattr(reels_settings, "images", "pollinations")
    monkeypatch.setattr(images, "_pollinations", lambda prompt, seed: prompts.append(prompt) or _png())
    images.generate("courier on a bike", tmp_path / "p.png", 1)
    assert prompts[0].startswith("courier on a bike. Setting: Russia. ")

    monkeypatch.setattr(reels_settings, "scene_context", "")
    images.generate("courier on a bike", tmp_path / "p.png", 1)
    assert "Setting" not in prompts[1]

    monkeypatch.setattr(reels_settings, "scene_context", "Setting: Russia")
    images.generate("packets on a wire", tmp_path / "p.png", 1, context=False)
    assert "Setting" not in prompts[2]

    monkeypatch.setattr(reels_settings, "scene_context", "Setting: Russia")
    monkeypatch.setattr(reels_settings, "video", "openai")
    monkeypatch.setattr(reels_settings, "video_key", "k")
    monkeypatch.setattr(video_gen, "POLL_SECONDS", 0)
    sent = {}
    monkeypatch.setattr(video_gen.httpx, "post", lambda url, **kw: sent.update(kw["json"])
                        or httpx.Response(202, json={"id": "v"}))
    monkeypatch.setattr(video_gen.net, "get", lambda url, **kw: httpx.Response(200, content=b"mp4")
                        if "content" in url else httpx.Response(200, json={"status": "completed"}))
    img = tmp_path / "f.png"
    Image.new("RGB", (1080, 1920)).save(img)
    video_gen.animate(img, "rider waves", 4, tmp_path / "o.mp4")
    assert sent["prompt"].startswith("rider waves. Setting: Russia. ")


def _png():
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (1080, 1920), "gray").save(buf, format="PNG")
    return buf.getvalue()


async def test_generate_image_returns_full_size_picture_without_voice(monkeypatch):
    import base64 as b64

    from PIL import Image

    from video_mcp.reels import images

    asked = []
    buf = io.BytesIO()
    Image.new("RGB", (1024, 1024), "orange").save(buf, format="PNG")
    monkeypatch.setattr(reels_settings, "images", "gemini")
    monkeypatch.setattr(images, "_gemini", lambda prompt, aspect="9:16": asked.append(aspect) or buf.getvalue())
    monkeypatch.setattr(tts, "synthesize", lambda *a: pytest.fail("no voice for a picture"))
    result = await call("generate_image", prompt="mascot", aspect="1:1")
    assert not result.isError
    assert asked == ["1:1"]
    image = Image.open(io.BytesIO(b64.b64decode(result.content[1].data)))
    assert image.size == (1024, 1024)
    assert list((reels_settings.root / "images").glob("*.png"))


async def test_youtube_stats_channel_and_video(monkeypatch):
    from video_mcp.reels import youtube_stats as yts

    monkeypatch.setattr(reels_settings, "yt_client_id", "id")
    monkeypatch.setattr(reels_settings, "yt_client_secret", "secret")
    monkeypatch.setattr(reels_settings, "yt_refresh_token", "rt")
    monkeypatch.setattr(yts, "_youtube_token", lambda: "tok")

    def fake_get(url, token, params):
        assert token == "tok"
        if url.endswith("/channels"):
            return {"items": [{"snippet": {"title": "Nexus"}, "statistics": {"subscriberCount": "7",
                    "viewCount": "1305", "videoCount": "1"},
                    "contentDetails": {"relatedPlaylists": {"uploads": "UU1"}}}]}
        if url.endswith("/playlistItems"):
            return {"items": [{"contentDetails": {"videoId": "abc"}}]}
        if url.endswith("/videos"):
            return {"items": [{"id": "abc", "snippet": {"title": "Белые списки"},
                               "contentDetails": {"duration": "PT41S"}}]}
        dims = params.get("dimensions")
        if dims == "video":
            return {"columnHeaders": [{"name": n} for n in ("video",) + yts.VIDEO_METRICS],
                    "rows": [["abc", 1305, 354, 24.3, 59.2, 24, 2, 1, 7]]}
        if dims == "insightTrafficSourceType":
            return {"columnHeaders": [{"name": "insightTrafficSourceType"}, {"name": "views"}],
                    "rows": [["SHORTS", 970], ["YT_SEARCH", 30]]}
        if dims == "elapsedVideoTimeRatio":
            return {"columnHeaders": [{"name": "elapsedVideoTimeRatio"}, {"name": "audienceWatchRatio"}],
                    "rows": [[i / 100, 1 - i / 200] for i in range(1, 101)]}
        return {"columnHeaders": [{"name": n} for n in yts.VIDEO_METRICS],
                "rows": [[1305, 354, 24.3, 59.2, 24, 2, 1, 7]]}

    monkeypatch.setattr(yts, "_get", fake_get)
    res = await call("youtube_stats")
    text = res.content[0].text
    assert not res.isError, text
    assert "подписчиков 7" in text and "Белые списки — 1305 просм." in text and "ср. 0:24 (59%)" in text

    res = await call("youtube_stats", video="https://youtube.com/shorts/abc")
    text = res.content[0].text
    assert not res.isError, text
    assert "лента Shorts 97%" in text and "поиск YouTube 3%" in text
    assert "Удержание" in text and "0:41 — 50%" in text


def test_youtube_upload_can_be_switched_off(monkeypatch):
    monkeypatch.setattr(reels_settings, "yt_client_id", "id")
    monkeypatch.setattr(reels_settings, "yt_client_secret", "secret")
    monkeypatch.setattr(reels_settings, "yt_refresh_token", "rt")
    assert "youtube" in reels_settings.publish_targets()
    monkeypatch.setattr(reels_settings, "yt_upload", False)
    assert "youtube" not in reels_settings.publish_targets()


async def test_media_start_skips_the_beginning_and_links_keep_case(video_dir):
    from PIL import Image

    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "lavfi", "-i", "color=c=red:s=720x1280:d=2:r=24",
                    "-f", "lavfi", "-i", "color=c=blue:s=720x1280:d=2:r=24",
                    "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]", "-pix_fmt", "yuv420p",
                    str(video_dir / "redblue.mp4")], check=True)
    res = await call("create_reel", background=False, title="x", music="none", scenes=[
        {"text": "Синий.", "media": "redblue.mp4", "media_start": 2.5, "label": "t.me/nexus_subs_bot"}])
    assert not res.isError, res.content[0].text
    workdir = jobs.job_dir(res.content[0].text.split()[1])
    assert (workdir / "label00.txt").read_text() == "t.me/nexus_subs_bot"
    frame = workdir / "f.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", "0.2", "-i",
                    str(workdir / "reel.mp4"), "-frames:v", "1", str(frame)], check=True)
    r, g, b = Image.open(frame).convert("RGB").resize((1, 1)).getpixel((0, 0))
    assert b > r, (r, g, b)
