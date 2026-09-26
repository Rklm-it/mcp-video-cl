#!/usr/bin/env bash
# Turns on the reels factory on an installed server: asks for the keys in the terminal
# (they are not echoed and never leave the server), writes them to .env and rebuilds.
#   cd /opt/video-mcp && sudo bash deploy/reels-setup.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV="$DIR/.env"
[ -f "$ENV" ] || { echo "Нет $ENV — сначала установите сервер: sudo bash install.sh"; exit 1; }

setv() {  # setv KEY VALUE — replace or append a line in .env
  local tmp
  tmp="$(mktemp)"
  grep -v "^$1=" "$ENV" > "$tmp" || true
  printf '%s=%s\n' "$1" "$2" >> "$tmp"
  cat "$tmp" > "$ENV" && rm -f "$tmp"
}
current() { grep -m1 "^$1=" "$ENV" | cut -d= -f2- || true; }
ask() {  # ask VAR "prompt" [secret] — keeps the current value on empty input
  local have value
  have="$(current "$1")"
  if [ -n "${3:-}" ]; then
    read -rsp "$2${have:+ (Enter — оставить текущий)}: " value; echo
  else
    read -rp "$2${have:+ [$have]}: " value
  fi
  value="${value:-$have}"
  [ -n "$value" ] || { echo "  нужно заполнить"; ask "$@"; return; }
  setv "$1" "$value"
}

echo "== Фабрика рилсов: настройка =="
echo "Ключи вводятся без отображения на экране."
echo
ask REELS_OPENAI_API_KEY "Ключ Timeweb AI Gateway (голос)" secret
ask REELS_GEMINI_API_KEY "Ключ ProxyAPI (видео Veo)" secret
ask REELS_TG_BOT_TOKEN "Токен Telegram-бота от @BotFather" secret
ask REELS_TG_CHANNEL "Канал для публикаций, например @dohod_dostavka"

if [ -z "$(current REELS_TG_REVIEW_CHAT_ID)" ]; then
  echo
  echo "Напишите своему боту в Telegram команду /start, потом нажмите Enter."
  read -r _
  token="$(current REELS_TG_BOT_TOKEN)"
  chat="$(curl -fsS "https://api.telegram.org/bot${token}/getUpdates" \
    | grep -o '"chat":{"id":[0-9]*' | tail -n1 | grep -o '[0-9]*$' || true)"
  if [ -n "$chat" ]; then
    echo "Нашёл ваш чат: $chat"
    setv REELS_TG_REVIEW_CHAT_ID "$chat"
  else
    ask REELS_TG_REVIEW_CHAT_ID "Не нашёл чат автоматически. Введите chat id вручную"
  fi
fi

# Fixed settings: Timeweb voice, free frames, Veo 3.1 Lite video through ProxyAPI, music folder
setv REELS_ENABLED 1
setv REELS_TTS openai
setv REELS_OPENAI_BASE_URL https://api.timeweb.ai/v1
setv REELS_IMAGES pollinations
setv REELS_VIDEO veo
setv REELS_ANIMATE_ALL 1
setv REELS_VEO_RESOLUTION 720p
[ -n "$(current REELS_VEO_MODEL)" ] || setv REELS_VEO_MODEL veo-3.1-lite-generate-preview
setv REELS_GEMINI_BASE_URL https://api.proxyapi.ru/google/v1beta
setv REELS_GEMINI_AUTH bearer
setv REELS_MUSIC_DIR /data/music
chmod 600 "$ENV"

mkdir -p "$DIR/data/music"
tracks="$(find "$DIR/data/music" -maxdepth 1 -type f | wc -l)"
echo
echo "Музыка: $tracks трек(ов) в $DIR/data/music (можно добавить позже, без перезапуска)."
echo "Пересобираю сервер…"
bash "$DIR/install.sh"
echo
echo "Готово. Проверка: docker compose -f $DIR/docker-compose.yml logs video-mcp | grep -i reels"
