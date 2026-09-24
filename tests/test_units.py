import json

import pytest

from video_mcp import frames as fr
from video_mcp import sources
from video_mcp import transcript as tr
from video_mcp.timeutil import fmt_time, parse_time


@pytest.mark.parametrize(
    "value,expected",
    [(None, None), (95, 95.0), ("95", 95.0), ("1:35", 95.0), ("01:02:03", 3723.0),
     ("1:02:03.5", 3723.5), ("1h2m3s", 3723.0), ("90s", 90.0), ("2m", 120.0), ("", None)],
)
def test_parse_time(value, expected):
    assert parse_time(value) == expected


def test_parse_time_rejects_garbage():
    with pytest.raises(ValueError):
        parse_time("soon")


def test_fmt_time():
    assert fmt_time(5) == "0:05"
    assert fmt_time(3723.9) == "1:02:03"


def test_parse_json3_skips_appends_and_empty():
    data = json.dumps({"events": [
        {"tStartMs": 0, "dDurationMs": 2000, "segs": [{"utf8": "Привет"}, {"utf8": " мир"}]},
        {"tStartMs": 1000, "aAppend": 1, "segs": [{"utf8": "\n"}]},
        {"tStartMs": 2000, "dDurationMs": 1000},
        {"tStartMs": 3000, "dDurationMs": 1500, "segs": [{"utf8": "второй"}]},
    ]})
    segs = tr.parse_json3(data)
    assert [(s.start, s.text) for s in segs] == [(0.0, "Привет мир"), (3.0, "второй")]


def test_parse_rolling_youtube_vtt():
    vtt = """WEBVTT
Kind: captions

00:00:00.000 --> 00:00:02.000 align:start position:0%
we<00:00:00.500><c> are</c><00:00:01.000><c> testing</c>

00:00:02.000 --> 00:00:02.010 align:start position:0%
we are testing

00:00:02.010 --> 00:00:04.000 align:start position:0%
we are testing
the rolling captions here
"""
    segs = tr.parse_cues(vtt)
    assert " ".join(s.text for s in segs) == "we are testing the rolling captions here"


def test_parse_srt():
    srt = "1\n00:00:01,000 --> 00:00:02,500\nFirst line\n\n2\n00:00:03,000 --> 00:00:04,000\n<i>Second</i>\n"
    segs = tr.parse_cues(srt)
    assert [(s.start, s.end, s.text) for s in segs] == [(1.0, 2.5, "First line"), (3.0, 4.0, "Second")]


def test_format_transcript_truncates_with_resume_point():
    segs = [tr.Segment(i * 10, i * 10 + 9, f"sentence number {i}") for i in range(20)]
    text, resume = tr.format_transcript(segs, group_seconds=20, max_chars=100)
    assert text.startswith("[0:00] sentence number 0 sentence number 1")
    assert resume is not None and resume > 0
    full, none = tr.format_transcript(segs)
    assert none is None and full.count("\n") == 9


def test_choose_times_spreads_and_fills():
    scenes = [(10.0, 0.9), (10.5, 0.8), (50.0, 0.5)]
    times = fr.choose_times(scenes, 0, 100, 8)
    assert times == sorted(times)
    assert 10.0 in times and 10.5 not in times  # too close to a stronger cut
    assert len(times) >= 4  # static parts get uniform fill


def test_pick_track_prefers_original_language():
    info = {
        "subtitles": {"de": [{"ext": "vtt", "url": "de"}], "en-US": [{"ext": "vtt", "url": "en-manual"}]},
        "automatic_captions": {
            "en-orig": [{"ext": "vtt", "url": "en-orig.vtt"}, {"ext": "json3", "url": "en-orig.json3"}],
            "en": [{"ext": "json3", "url": "en.json3"}],
            "ru": [{"ext": "json3", "url": "ru.json3"}],
        },
    }
    # manual subtitles in the original language win
    assert sources._pick_track(info, None)[1]["url"] == "en-manual"
    # an explicitly requested language wins
    assert sources._pick_track(info, "de")[1]["url"] == "de"
    # original-language auto captions beat manual subtitles in another language
    del info["subtitles"]["en-US"]
    assert sources._pick_track(info, None)[1]["url"] == "en-orig.json3"
    info["subtitles"] = {}
    lang, track, kind = sources._pick_track(info, None)
    assert (lang, track["url"], kind) == ("en", "en-orig.json3", "auto-captions")
    lang, track, kind = sources._pick_track(info, "ru")
    assert (lang, kind) == ("ru", "auto-translated")
    # no auto captions at all -> any manual track
    assert sources._pick_track({"subtitles": {"fr": [{"ext": "srt", "url": "fr"}]}}, None)[0] == "fr"


def test_resolve_youtube_variants():
    for url in ("https://youtu.be/dQw4w9WgXcQ?t=5", "https://www.youtube.com/shorts/dQw4w9WgXcQ",
                "https://m.youtube.com/watch?feature=share&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"):
        src = sources.resolve(url)
        assert src.key == "yt_dQw4w9WgXcQ"
        assert src.url == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


def test_resolve_blocks_private_hosts_and_path_escape():
    with pytest.raises(sources.SourceError):
        sources.resolve("http://127.0.0.1/video.mp4")
    with pytest.raises(sources.SourceError):
        sources.resolve("../../etc/passwd")


def test_scene_detection_finds_color_cuts(video_dir):
    scenes = fr.detect_scenes(video_dir / "colors.mp4", 0, 12, 0.3)
    cut_times = [t for t, score in scenes if score > 0.3]
    assert any(abs(t - 4) < 0.6 for t in cut_times)
    assert any(abs(t - 8) < 0.6 for t in cut_times)


def test_grab_frames_and_dedupe(video_dir):
    frames = fr.grab_frames(video_dir / "colors.mp4", [1.0, 1.04, 6.0], width=320)
    assert all(f.width == 320 and f.jpeg[:2] == b"\xff\xd8" for f in frames)
    kept = fr.dedupe(frames)
    assert len(kept) == 2
