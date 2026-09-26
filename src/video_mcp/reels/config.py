"""Reels settings, read from environment variables (see .env.example, section «Reels»)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import _env, _env_bool, settings

DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@dataclass
class ReelsSettings:
    enabled: bool = field(default_factory=lambda: _env_bool("REELS_ENABLED", False))

    # Voice: edge (free Microsoft neural voices) | elevenlabs (paid, best quality)
    tts: str = field(default_factory=lambda: _env("REELS_TTS", "edge"))
    edge_voice: str = field(default_factory=lambda: _env("REELS_EDGE_VOICE", "ru-RU-DmitryNeural"))
    edge_rate: str = field(default_factory=lambda: _env("REELS_EDGE_RATE", "+8%"))
    elevenlabs_key: str = field(default_factory=lambda: _env("REELS_ELEVENLABS_API_KEY"))
    elevenlabs_voice: str = field(default_factory=lambda: _env("REELS_ELEVENLABS_VOICE_ID"))
    elevenlabs_model: str = field(default_factory=lambda: _env("REELS_ELEVENLABS_MODEL", "eleven_multilingual_v2"))

    # Pictures: pollinations (free) | gemini (Nano Banana, paid API) | openai (any OpenAI-compatible
    # images API, e.g. a Russian reseller) | placeholder (text on a gradient, for tests)
    images: str = field(default_factory=lambda: _env("REELS_IMAGES", "pollinations"))
    gemini_key: str = field(default_factory=lambda: _env("REELS_GEMINI_API_KEY"))
    gemini_image_model: str = field(default_factory=lambda: _env("REELS_GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"))
    openai_key: str = field(default_factory=lambda: _env("REELS_OPENAI_API_KEY"))
    openai_base_url: str = field(default_factory=lambda: _env("REELS_OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_image_model: str = field(default_factory=lambda: _env("REELS_OPENAI_IMAGE_MODEL", "gpt-image-1"))
    image_style: str = field(default_factory=lambda: _env(
        "REELS_IMAGE_STYLE", "vertical 9:16, cinematic, high detail, no text, no letters, no watermark"))

    font: str = field(default_factory=lambda: _env("REELS_FONT", DEFAULT_FONT))

    # Telegram: bot that posts to the channel and sends drafts to the review chat
    tg_token: str = field(default_factory=lambda: _env("REELS_TG_BOT_TOKEN"))
    tg_channel: str = field(default_factory=lambda: _env("REELS_TG_CHANNEL"))
    tg_review_chat: str = field(default_factory=lambda: _env("REELS_TG_REVIEW_CHAT_ID"))

    # YouTube Data API (OAuth refresh token from `video-mcp-youtube-auth`)
    yt_client_id: str = field(default_factory=lambda: _env("REELS_YT_CLIENT_ID"))
    yt_client_secret: str = field(default_factory=lambda: _env("REELS_YT_CLIENT_SECRET"))
    yt_refresh_token: str = field(default_factory=lambda: _env("REELS_YT_REFRESH_TOKEN"))
    yt_privacy: str = field(default_factory=lambda: _env("REELS_YT_PRIVACY", "public"))

    @property
    def root(self) -> Path:
        return settings.data_dir / "reels"

    @property
    def jobs_dir(self) -> Path:
        return self.root / "jobs"

    @property
    def offers_file(self) -> Path:
        return self.root / "offers.json"

    @property
    def review_enabled(self) -> bool:
        return bool(self.tg_token and self.tg_review_chat)

    def publish_targets(self) -> list[str]:
        targets = []
        if self.tg_token and self.tg_channel:
            targets.append("telegram")
        if self.yt_client_id and self.yt_client_secret and self.yt_refresh_token:
            targets.append("youtube")
        return targets


reels_settings = ReelsSettings()
