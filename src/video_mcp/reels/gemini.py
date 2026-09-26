"""Gemini API access (Google directly or a reseller that proxies the same API)."""

from __future__ import annotations

from pathlib import Path

import httpx

from .config import reels_settings

GOOGLE_BASE = "https://generativelanguage.googleapis.com/v1beta"


def headers() -> dict[str, str]:
    s = reels_settings
    if not s.gemini_key:
        raise ValueError("Set REELS_GEMINI_API_KEY")
    if s.gemini_auth == "bearer":
        return {"Authorization": f"Bearer {s.gemini_key}"}
    return {"x-goog-api-key": s.gemini_key}


def url(path: str) -> str:
    """`path` is relative to the API version root, e.g. 'models/x:generateContent'."""
    return f"{reels_settings.gemini_base_url.rstrip('/')}/{path.lstrip('/')}"


def proxied(uri: str) -> str:
    """File links in responses point at Google; route them through the configured base URL."""
    base = reels_settings.gemini_base_url.rstrip("/")
    if base != GOOGLE_BASE and uri.startswith(GOOGLE_BASE):
        return base + uri[len(GOOGLE_BASE):]
    return uri


def download(uri: str, out: Path) -> Path:
    with httpx.stream("GET", proxied(uri), headers=headers(), timeout=300, follow_redirects=True) as resp:
        if resp.status_code >= 400:
            resp.read()
            raise RuntimeError(f"Gemini file download failed {resp.status_code}: {resp.text[:300]}")
        with out.open("wb") as f:
            for chunk in resp.iter_bytes():
                f.write(chunk)
    return out
