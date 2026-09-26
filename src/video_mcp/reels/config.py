"""Reels settings, read from environment variables (see .env.example, section «Reels»)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import _env, _env_bool, _env_float, _env_int, settings

DEFAULT_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


@dataclass
class ReelsSettings:
    enabled: bool = field(default_factory=lambda: _env_bool("REELS_ENABLED", False))

    # Voice: edge (free Microsoft neural voices) | openai (any OpenAI-compatible /audio/speech, e.g.
    # Timeweb AI Gateway with gpt-4o-mini-tts) | elevenlabs (paid, best quality)
    tts: str = field(default_factory=lambda: _env("REELS_TTS", "edge"))
    edge_voice: str = field(default_factory=lambda: _env("REELS_EDGE_VOICE", "ru-RU-DmitryNeural"))
    edge_rate: str = field(default_factory=lambda: _env("REELS_EDGE_RATE", "+8%"))
    openai_tts_model: str = field(default_factory=lambda: _env("REELS_OPENAI_TTS_MODEL", "gpt-4o-mini-tts"))
    openai_tts_voice: str = field(default_factory=lambda: _env("REELS_OPENAI_TTS_VOICE", "onyx"))
    openai_tts_instructions: str = field(default_factory=lambda: _env(
        "REELS_OPENAI_TTS_INSTRUCTIONS",
        "Говори по-русски живо и уверенно, как ведущий коротких роликов, в бодром темпе."))
    elevenlabs_key: str = field(default_factory=lambda: _env("REELS_ELEVENLABS_API_KEY"))
    elevenlabs_voice: str = field(default_factory=lambda: _env("REELS_ELEVENLABS_VOICE_ID"))
    elevenlabs_model: str = field(default_factory=lambda: _env("REELS_ELEVENLABS_MODEL", "eleven_multilingual_v2"))

    # Pictures: pollinations (free) | gemini (Nano Banana, paid API) | openai (any OpenAI-compatible
    # images API, e.g. a Russian reseller) | placeholder (text on a gradient, for tests)
    images: str = field(default_factory=lambda: _env("REELS_IMAGES", "pollinations"))
    gemini_key: str = field(default_factory=lambda: _env("REELS_GEMINI_API_KEY"))
    # Native Gemini API or a reseller that proxies it (e.g. ProxyAPI: https://api.proxyapi.ru/google/v1beta)
    gemini_base_url: str = field(default_factory=lambda: _env(
        "REELS_GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"))
    # How the key is sent: key = x-goog-api-key header (Google), bearer = Authorization: Bearer (resellers)
    gemini_auth: str = field(default_factory=lambda: _env("REELS_GEMINI_AUTH", "key"))
    gemini_image_model: str = field(default_factory=lambda: _env("REELS_GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image"))
    openai_key: str = field(default_factory=lambda: _env("REELS_OPENAI_API_KEY"))
    openai_base_url: str = field(default_factory=lambda: _env("REELS_OPENAI_BASE_URL", "https://api.openai.com/v1"))
    openai_image_model: str = field(default_factory=lambda: _env("REELS_OPENAI_IMAGE_MODEL", "gpt-image-1"))
    # Sent as `size`; leave empty for models that do not accept it
    openai_image_size: str = field(default_factory=lambda: _env("REELS_OPENAI_IMAGE_SIZE", "1024x1536"))
    image_style: str = field(default_factory=lambda: _env(
        "REELS_IMAGE_STYLE", "vertical 9:16, cinematic, high detail, no text, no letters, no watermark"))

    # Animated scenes: none | veo (Veo 3.1 image-to-video through the Gemini API, paid per second)
    video: str = field(default_factory=lambda: _env("REELS_VIDEO", "none"))
    veo_model: str = field(default_factory=lambda: _env("REELS_VEO_MODEL", "veo-3.1-fast-generate-preview"))
    veo_resolution: str = field(default_factory=lambda: _env("REELS_VEO_RESOLUTION", "720p"))
    # Every generated scene becomes video unless the script says animate=false
    animate_all: bool = field(default_factory=lambda: _env_bool("REELS_ANIMATE_ALL", False))
    # Cost guard: at most this many animated scenes per reel (default 8 with ANIMATE_ALL, else 2)
    max_animated: int = field(default_factory=lambda: _env_int("REELS_MAX_ANIMATED", 0))
    # Parallel video generations per reel
    video_workers: int = field(default_factory=lambda: _env_int("REELS_VIDEO_WORKERS", 4))

    # Background music: a folder with mp3/m4a/wav tracks you are allowed to use
    # (e.g. from the YouTube Audio Library); a random one is mixed under the voice
    music_dir: str = field(default_factory=lambda: _env("REELS_MUSIC_DIR"))
    music_volume: float = field(default_factory=lambda: _env_float("REELS_MUSIC_VOLUME", 0.12))

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

    def __post_init__(self) -> None:
        if self.max_animated <= 0:
            self.max_animated = 8 if self.animate_all else 2

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

    def music_tracks(self) -> list[Path]:
        if not self.music_dir or not Path(self.music_dir).is_dir():
            return []
        return sorted(p for p in Path(self.music_dir).iterdir()
                      if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg", ".aac"))

    def publish_targets(self) -> list[str]:
        targets = []
        if self.tg_token and self.tg_channel:
            targets.append("telegram")
        if self.yt_client_id and self.yt_client_secret and self.yt_refresh_token:
            targets.append("youtube")
        return targets


reels_settings = ReelsSettings()
