"""One-time helper: get a YouTube refresh token for uploading Shorts.

Run on the server:  docker compose run --rm --entrypoint video-mcp-youtube-auth video-mcp
"""

from __future__ import annotations

import sys
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from .config import reels_settings

SCOPE = "https://www.googleapis.com/auth/youtube.upload"
REDIRECT = "http://localhost"


def main() -> None:
    client_id = reels_settings.yt_client_id or input("OAuth Client ID: ").strip()
    client_secret = reels_settings.yt_client_secret or input("OAuth Client secret: ").strip()
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode({
        "client_id": client_id, "redirect_uri": REDIRECT, "response_type": "code",
        "scope": SCOPE, "access_type": "offline", "prompt": "consent",
    })
    print("\n1. Откройте ссылку в браузере и войдите в Google-аккаунт канала:\n")
    print(url)
    print("\n2. После разрешения браузер откроет http://localhost/... и покажет ошибку — это нормально.")
    answer = input("3. Скопируйте адрес из строки браузера целиком и вставьте сюда: ").strip()
    code = parse_qs(urlparse(answer).query).get("code", [answer])[0]
    resp = httpx.post("https://oauth2.googleapis.com/token", data={
        "code": code, "client_id": client_id, "client_secret": client_secret,
        "redirect_uri": REDIRECT, "grant_type": "authorization_code",
    }, timeout=30)
    data = resp.json()
    if "refresh_token" not in data:
        sys.exit(f"Не получилось: {data}")
    print("\nГотово. Добавьте в .env и перезапустите сервер:\n")
    print(f"REELS_YT_CLIENT_ID={client_id}")
    print(f"REELS_YT_CLIENT_SECRET={client_secret}")
    print(f"REELS_YT_REFRESH_TOKEN={data['refresh_token']}")


if __name__ == "__main__":
    main()
