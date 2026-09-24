"""Settings read from environment variables (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    return float(value) if value else default


def _env_bool(name: str, default: bool) -> bool:
    value = _env(name).lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # Transport
    host: str = field(default_factory=lambda: _env("VIDEO_MCP_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: _env_int("VIDEO_MCP_PORT", 8000))
    token: str = field(default_factory=lambda: _env("VIDEO_MCP_TOKEN"))
    allow_no_auth: bool = field(default_factory=lambda: _env_bool("VIDEO_MCP_ALLOW_NO_AUTH", False))

    # Storage
    data_dir: Path = field(default_factory=lambda: Path(_env("VIDEO_MCP_DATA_DIR", "/data")))
    local_video_dir: Path = field(default_factory=lambda: Path(_env("VIDEO_MCP_LOCAL_DIR", "/data/videos")))
    cache_ttl_hours: float = field(default_factory=lambda: _env_float("VIDEO_MCP_CACHE_TTL_HOURS", 48))
    cache_max_gb: float = field(default_factory=lambda: _env_float("VIDEO_MCP_CACHE_MAX_GB", 15))

    # Download
    max_height: int = field(default_factory=lambda: _env_int("VIDEO_MCP_MAX_HEIGHT", 720))
    long_video_max_height: int = field(default_factory=lambda: _env_int("VIDEO_MCP_LONG_VIDEO_MAX_HEIGHT", 480))
    long_video_minutes: float = field(default_factory=lambda: _env_float("VIDEO_MCP_LONG_VIDEO_MINUTES", 60))
    # Videos longer than this are downloaded only in the requested start/end section.
    section_download_minutes: float = field(
        default_factory=lambda: _env_float("VIDEO_MCP_SECTION_DOWNLOAD_MINUTES", 30)
    )
    max_duration_hours: float = field(default_factory=lambda: _env_float("VIDEO_MCP_MAX_DURATION_HOURS", 6))
    cookies_file: str = field(default_factory=lambda: _env("YTDLP_COOKIES"))
    proxy: str = field(default_factory=lambda: _env("YTDLP_PROXY"))
    # Optional bgutil PO-token provider (docker compose profile "pot"), e.g. http://pot-provider:4416
    pot_provider_url: str = field(default_factory=lambda: _env("YTDLP_POT_PROVIDER_URL"))
    allow_private_urls: bool = field(default_factory=lambda: _env_bool("VIDEO_MCP_ALLOW_PRIVATE_URLS", False))

    # Frames
    frame_width: int = field(default_factory=lambda: _env_int("VIDEO_MCP_FRAME_WIDTH", 768))
    frame_max_width: int = field(default_factory=lambda: _env_int("VIDEO_MCP_FRAME_MAX_WIDTH", 1600))
    jpeg_quality: int = field(default_factory=lambda: _env_int("VIDEO_MCP_JPEG_QUALITY", 72))
    max_frames_limit: int = field(default_factory=lambda: _env_int("VIDEO_MCP_MAX_FRAMES_LIMIT", 60))

    # Transcript
    transcript_max_chars: int = field(default_factory=lambda: _env_int("VIDEO_MCP_TRANSCRIPT_MAX_CHARS", 40000))
    whisper_model: str = field(default_factory=lambda: _env("WHISPER_MODEL", "small"))
    whisper_device: str = field(default_factory=lambda: _env("WHISPER_DEVICE", "cpu"))
    whisper_compute_type: str = field(default_factory=lambda: _env("WHISPER_COMPUTE_TYPE", "int8"))
    whisper_enabled: bool = field(default_factory=lambda: _env_bool("WHISPER_ENABLED", True))

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def models_dir(self) -> Path:
        return self.data_dir / "models"


settings = Settings()
