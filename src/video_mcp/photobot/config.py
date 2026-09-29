"""Photo bot settings, read from environment variables (see .env.example, section «Photo bot»)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ..config import _env, _env_bool, _env_int, settings


@dataclass
class BotSettings:
    token: str = field(default_factory=lambda: _env("PHOTO_BOT_TOKEN"))
    # Telegram user id of the owner: payment and error notices, /stats
    admin_id: str = field(default_factory=lambda: _env("PHOTO_BOT_ADMIN_ID"))
    platega_merchant: str = field(default_factory=lambda: _env("PLATEGA_MERCHANT_ID"))
    platega_secret: str = field(default_factory=lambda: _env("PLATEGA_SECRET"))
    platega_base_url: str = field(default_factory=lambda: _env("PLATEGA_BASE_URL", "https://app.platega.io"))
    # Prices in rubles
    price_animate: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_ANIMATE", 149))
    price_card: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CARD", 99))
    price_shoot: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_SHOOT", 399))
    price_greet: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_GREET", 249))
    price_moroz: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_MOROZ", 299))
    price_char: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CHAR", 249))
    price_restore: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_RESTORE", 149))
    price_style: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_STYLE", 149))
    price_drawing: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_DRAWING", 149))
    price_enhance: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_ENHANCE", 99))
    price_bg: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_BG", 149))
    price_together: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_TOGETHER", 149))
    price_baby: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_BABY", 149))
    price_hug: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_HUG", 299))
    price_pvideo: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_PVIDEO", 349))
    price_superhero: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_SUPERHERO", 149))
    price_custom: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CUSTOM", 149))
    price_customvid: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CUSTOMVID", 249))
    # Ded Moroz video: off until the Russian speech of the video model is checked (planned for November)
    moroz_open: bool = field(default_factory=lambda: _env_bool("PHOTO_BOT_DED_MOROZ", False))
    # Unpaid payment links are forgotten after this many minutes
    payment_minutes: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PAYMENT_MINUTES", 30))
    # Picture model for everything made from photos, best first; the next is tried when a model is unavailable
    image_model: str = field(default_factory=lambda: _env("PHOTO_BOT_IMAGE_MODEL", "gemini-3-pro-image-preview"))
    workers: int = field(default_factory=lambda: _env_int("PHOTO_BOT_WORKERS", 3))

    @property
    def root(self) -> Path:
        return settings.data_dir / "photobot"

    def image_models(self) -> list[str]:
        from ..reels.config import reels_settings

        chain = [self.image_model, "gemini-3.1-flash-image-preview", reels_settings.gemini_image_model]
        return list(dict.fromkeys(m for m in chain if m))

    def price(self, product: str) -> int:
        return getattr(self, f"price_{product}")


bot_settings = BotSettings()
