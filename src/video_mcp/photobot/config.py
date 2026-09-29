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
    price_shoot: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_SHOOT", 199))
    price_greet: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_GREET", 199))
    price_moroz: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_MOROZ", 299))
    price_char: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CHAR", 199))
    price_restore: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_RESTORE", 99))
    price_style: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_STYLE", 79))
    price_drawing: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_DRAWING", 99))
    price_enhance: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_ENHANCE", 49))
    price_bg: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_BG", 79))
    price_together: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_TOGETHER", 99))
    price_baby: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_BABY", 99))
    price_hug: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_HUG", 199))
    price_pvideo: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_PVIDEO", 299))
    price_custom: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CUSTOM", 79))
    price_customvid: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PRICE_CUSTOMVID", 199))
    # Ded Moroz video: off until the Russian speech of the video model is checked (planned for November)
    moroz_open: bool = field(default_factory=lambda: _env_bool("PHOTO_BOT_DED_MOROZ", False))
    # Unpaid payment links are forgotten after this many minutes
    payment_minutes: int = field(default_factory=lambda: _env_int("PHOTO_BOT_PAYMENT_MINUTES", 30))
    workers: int = field(default_factory=lambda: _env_int("PHOTO_BOT_WORKERS", 3))

    @property
    def root(self) -> Path:
        return settings.data_dir / "photobot"

    def price(self, product: str) -> int:
        return getattr(self, f"price_{product}")


bot_settings = BotSettings()
