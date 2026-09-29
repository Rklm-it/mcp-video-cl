import json
import subprocess

from video_mcp.reels import clips
from video_mcp.transcript import Segment


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
                          "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


def test_vertical_clip_with_sound_subtitles_hook_and_green_banner(video_dir):
    banner = video_dir / "banner.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i",
                    "color=c=0x00FF00:s=600x150:d=2", "-vf", "drawbox=x=50:y=40:w=500:h=70:color=white:t=fill",
                    "-pix_fmt", "yuv420p", str(banner)], check=True)
    out = clips.make_clip("colors.mp4", 1, 9, hook="Смотри до конца", banner="banner.mp4")
    info = probe(out)
    streams = {s["codec_type"]: s for s in info["streams"]}
    assert streams["video"]["width"] == 1080 and streams["video"]["height"] == 1920
    assert "audio" in streams
    assert 7.5 < float(info["format"]["duration"]) < 8.5
    assert not list(out.parent.glob(out.stem + "-*"))  # helper files are cleaned up


def test_crop_layout_without_extras(video_dir):
    out = clips.make_clip("colors.mp4", 0, 5, layout="crop", subtitles=False)
    assert probe(out)["streams"][0]["height"] == 1920


def test_subtitle_words_are_timed_from_the_clip_start():
    segs = [Segment(0, 2, "до клипа"), Segment(10, 12, "первое слово"), Segment(30, 32, "после")]
    words = clips.subtitle_words(segs, 9, 20)
    assert [w.text for w in words] == ["первое", "слово"]
    assert 0.9 <= words[0].start < words[1].start < 3.1


def test_transparent_banner_is_trimmed_to_the_logo(tmp_path):
    from PIL import Image

    canvas = Image.new("RGBA", (1000, 600), (0, 0, 0, 0))
    canvas.paste((255, 0, 0, 255), (400, 250, 600, 350))
    canvas.save(tmp_path / "b.png")
    out = clips.trim_picture(tmp_path / "b.png")
    assert Image.open(out).size == (280, 180)
