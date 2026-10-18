#!/usr/bin/env bash
# Adds (or updates) a second channel for the reels factory: its Telegram channel and Instagram account.
# Keys are asked in the terminal without echo and never leave the server.
#   cd /opt/video-mcp && sudo bash deploy/brand-setup.sh            # brand "news" («Ну и новости»)
#   sudo bash deploy/brand-setup.sh other "Другой канал"
# Then: create_reel(brand="news") publishes only there.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$DIR/.env"
[ -f "$ENV" ] || { echo "Нет $ENV — сначала установите сервер: sudo bash install.sh"; exit 1; }
BRAND="${1:-news}"
TITLE="${2:-Ну и новости}"

setv() {  # setv KEY VALUE — replace or append a line in .env
  local tmp
  tmp="$(mktemp)"
  grep -v "^$1=" "$ENV" > "$tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$ENV" && rm -f "$tmp"
}
current() { grep -m1 "^$1=" "$ENV" | cut -d= -f2- || true; }
plain() {  # plain VALUE — refuses characters that would break the JSON line in .env
  case "$1" in *[\"\\\ ]*) echo "  в значении не должно быть пробелов, кавычек и \\"; return 1;; esac
}

echo "== Второй канал «$TITLE» (brand=$BRAND) =="
[ -n "$(current REELS_TG_BOT_TOKEN)" ] || echo "Внимание: нет REELS_TG_BOT_TOKEN — сначала deploy/reels-setup.sh"

while :; do
  read -rp "Telegram-канал (с @, например @nuinovosti_tv): " TG
  case "$TG" in @?*) plain "$TG" && break;; *) echo "  нужен юзернейм с @";; esac
done
while :; do
  read -rp "Instagram: ID пользователя (цифры, Enter — без Instagram): " IG_ID
  [ -z "$IG_ID" ] && break
  case "$IG_ID" in *[!0-9]*) echo "  только цифры";; *) break;; esac
done
IG_TOKEN=""
if [ -n "$IG_ID" ]; then
  while :; do
    read -rsp "Instagram: ключ (маркер доступа, не отображается): " IG_TOKEN; echo
    [ -n "$IG_TOKEN" ] && plain "$IG_TOKEN" && break
  done
fi

# Other brands already in .env stay: the new one is merged in by the container's Python
OLD="$(current REELS_BRANDS)"
NEW="$(docker compose -f "$DIR/docker-compose.yml" run --rm --no-deps -T --entrypoint python video-mcp -c '
import json, sys
old, name, title, tg, ig_id, ig_tok = sys.argv[1:7]
brands = json.loads(old) if old else {}
brands[name] = {"title": title, "tg_channel": tg, "ig_user_id": ig_id, "ig_token": ig_tok, "youtube": False}
print(json.dumps(brands, ensure_ascii=False, separators=(",", ":")))
' "$OLD" "$BRAND" "$TITLE" "$TG" "$IG_ID" "$IG_TOKEN")"
setv REELS_BRANDS "$NEW"

DOMAIN="$(current DOMAIN)"
if [ -n "$IG_ID" ] && [ -z "$(current REELS_PUBLIC_URL)" ]; then
  [ -n "$DOMAIN" ] || { echo "Нет DOMAIN в .env: Instagram скачивает видео по ссылке на этот сервер"; exit 1; }
  setv REELS_PUBLIC_URL "https://$DOMAIN"
fi

echo "Перезапускаю сервер (новые настройки из .env)…"
cd "$DIR" && docker compose up -d
echo "Готово: канал «$TITLE» → $TG${IG_ID:+ и Instagram $IG_ID}. Проверка — инструмент reels_setup."
