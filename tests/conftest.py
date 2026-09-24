import functools
import http.server
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from video_mcp.config import settings

VTT = """WEBVTT

00:00:00.500 --> 00:00:03.500
Hello, this is the red scene.

00:00:04.500 --> 00:00:07.500
Now the picture turns green.

00:00:08.500 --> 00:00:11.500
And finally everything is blue.
"""


def make_video(path: Path) -> None:
    """12 s video: 4 s red, 4 s green, 4 s blue (each with a moving test pattern box), sine audio."""
    parts = []
    for color in ("red", "lime", "blue"):
        parts += ["-f", "lavfi", "-i", f"color=c={color}:s=640x360:d=4:r=25"]
    filt = (
        "[0:v][1:v][2:v]concat=n=3:v=1:a=0,"
        "drawbox=x='mod(t*80,560)':y=140:w=80:h=80:color=white:t=fill[v]"
    )
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *parts,
         "-f", "lavfi", "-i", "sine=frequency=440:duration=12",
         "-filter_complex", filt, "-map", "[v]", "-map", "3:a",
         "-c:v", "libx264", "-g", "25", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)],
        check=True,
    )


@pytest.fixture(scope="session")
def video_dir(tmp_path_factory) -> Path:
    d = tmp_path_factory.mktemp("videos")
    make_video(d / "colors.mp4")
    (d / "colors.vtt").write_text(VTT)
    return d


@pytest.fixture(autouse=True)
def isolated_settings(tmp_path, video_dir, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "local_video_dir", video_dir)
    monkeypatch.setattr(settings, "whisper_enabled", False)
    monkeypatch.setattr(settings, "cookies_file", "")
    monkeypatch.setattr(settings, "proxy", "")
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    yield


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler plus byte ranges, which ffmpeg needs to seek (YouTube supports them)."""

    def log_message(self, *args):
        pass

    def send_head(self):
        header = self.headers.get("Range")
        path = Path(self.translate_path(self.path))
        if not header or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        first, _, last = header.removeprefix("bytes=").partition("-")
        start = int(first) if first else size - int(last)
        end = int(last) if first and last else size - 1
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        try:
            if remaining is None:
                return super().copyfile(source, outputfile)
            while remaining > 0:
                chunk = source.read(min(65536, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass


@pytest.fixture
def http_video(video_dir, tmp_path, monkeypatch):
    """Serve the test video over local HTTP so the yt-dlp download path is exercised."""
    served = tmp_path / "www"
    served.mkdir()
    shutil.copy(video_dir / "colors.mp4", served / "clip.mp4")
    handler = functools.partial(RangeHandler, directory=str(served))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(settings, "allow_private_urls", True)
    yield f"http://127.0.0.1:{server.server_address[1]}/clip.mp4"
    server.shutdown()
