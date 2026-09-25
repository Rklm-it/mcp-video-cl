#!/usr/bin/env bash
# One-command install / update of video-mcp on a fresh VPS (Ubuntu/Debian).
#
#   curl -fsSL https://raw.githubusercontent.com/Rklm-it/mcp-video-cl/HEAD/install.sh | sudo bash
#
# Re-run the same command to update: settings in .env are kept.
# Optional environment: DOMAIN=video.example.com  VIDEO_MCP_DIR=/opt/video-mcp  NO_START=1
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Rklm-it/mcp-video-cl.git}"
DIR="${VIDEO_MCP_DIR:-/opt/video-mcp}"

say()  { printf '\033[1;32m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*"; }
die()  { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

ask() {  # ask "question" "default" -> answer (reads the terminal even when piped from curl)
  local answer=""
  if [ -r /dev/tty ] && [ -z "${NONINTERACTIVE:-}" ]; then
    read -r -p "$1 [$2]: " answer </dev/tty || true
  fi
  echo "${answer:-$2}"
}

set_env() {  # set_env KEY VALUE: add or replace a line in .env
  if grep -q "^$1=" .env 2>/dev/null; then
    sed -i "s|^$1=.*|$1=$2|" .env
  else
    echo "$1=$2" >> .env
  fi
}

[ "$(id -u)" -eq 0 ] || die "запустите от root: curl ... | sudo bash"

# ---------------------------------------------------------------- packages
if ! command -v git >/dev/null || ! command -v curl >/dev/null || ! command -v ss >/dev/null; then
  say "Ставлю git, curl, iproute2"
  apt-get update -qq && apt-get install -y -qq git curl ca-certificates iproute2 >/dev/null
fi
if ! command -v docker >/dev/null; then
  say "Ставлю Docker"
  curl -fsSL https://get.docker.com | sh >/dev/null
fi
docker compose version >/dev/null 2>&1 || die "нет плагина docker compose (apt-get install docker-compose-plugin)"
systemctl enable --now docker >/dev/null 2>&1 || true

# ---------------------------------------------------------------- code
if [ -d "$DIR/.git" ]; then
  say "Обновляю код в $DIR"
  git -C "$DIR" pull --ff-only -q
else
  say "Скачиваю код в $DIR"
  git clone -q "$REPO_URL" "$DIR"
fi
cd "$DIR"
mkdir -p data/videos secrets

# ---------------------------------------------------------------- settings
FIRST_RUN=0
if [ ! -f .env ]; then
  FIRST_RUN=1
  cp .env.example .env
fi

IP="$(curl -4 -fsS --max-time 10 https://api.ipify.org 2>/dev/null \
  || curl -4 -fsS --max-time 10 https://ifconfig.me 2>/dev/null || true)"
CURRENT_DOMAIN="$(grep -E '^DOMAIN=' .env | cut -d= -f2- || true)"
if [ -n "${DOMAIN:-}" ]; then
  :
elif [ "$FIRST_RUN" = 1 ] || [ -z "$CURRENT_DOMAIN" ] || [ "$CURRENT_DOMAIN" = "video.example.com" ]; then
  DEFAULT_DOMAIN=""
  [ -n "$IP" ] && DEFAULT_DOMAIN="$(echo "$IP" | tr . -).sslip.io"
  echo
  echo "Домен для HTTPS. Если своего домена нет, просто нажмите Enter:"
  echo "будет использован бесплатный адрес по IP сервера ($DEFAULT_DOMAIN)."
  DOMAIN="$(ask "Домен" "$DEFAULT_DOMAIN")"
else
  DOMAIN="$CURRENT_DOMAIN"
fi
[ -n "$DOMAIN" ] || die "не удалось определить IP сервера; запустите с DOMAIN=ваш.домен"
set_env DOMAIN "$DOMAIN"

TOKEN="$(grep -E '^VIDEO_MCP_TOKEN=' .env | cut -d= -f2- || true)"
if [ -z "$TOKEN" ] || [ "$TOKEN" = "change-me" ]; then
  FIRST_RUN=1  # also covers a first run that stopped half-way
  TOKEN="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
fi

RAM_MB="$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)"
if [ "$RAM_MB" -lt 2000 ] && [ "$(awk '/SwapTotal/ {print $2}' /proc/meminfo)" -eq 0 ] && [ ! -e /swapfile ]; then
  say "Мало памяти (${RAM_MB} МБ): добавляю файл подкачки 2 ГБ (/swapfile)"
  if { fallocate -l 2G /swapfile 2>/dev/null || dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none; } \
    && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile; then
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
  else
    rm -f /swapfile
    warn "не удалось включить подкачку, продолжаю без неё"
  fi
fi
if [ "$FIRST_RUN" = 1 ]; then
  if [ "$RAM_MB" -lt 1500 ]; then
    warn "Всего ${RAM_MB} МБ RAM: Whisper (распознавание речи без субтитров) выключен"
    set_env WITH_WHISPER 0
    set_env WHISPER_ENABLED 0
  elif [ "$RAM_MB" -lt 3000 ]; then
    set_env WHISPER_MODEL base
  fi
fi
set_env VIDEO_MCP_TOKEN "$TOKEN"

if [ -f secrets/cookies.txt ]; then
  set_env YTDLP_COOKIES /secrets/cookies.txt
fi

# ---------------------------------------------------------------- checks
if [ -n "$IP" ] && command -v getent >/dev/null; then
  RESOLVED="$(getent ahostsv4 "$DOMAIN" | awk 'NR==1 {print $1}' || true)"
  if [ "$RESOLVED" != "$IP" ]; then
    warn "$DOMAIN указывает на '${RESOLVED:-никуда}', а IP этого сервера $IP."
    warn "Создайте A-запись $DOMAIN -> $IP, иначе HTTPS-сертификат не выдадут."
  fi
fi
port_owner() {  # port_owner PORT -> program name listening on it (empty if free)
  local who
  # (no "| grep -q" here: with pipefail an early grep exit makes the pipeline fail at random)
  [ -n "$(ss -ltnH "sport = :$1" 2>/dev/null)" ] || return 0
  who="$(ss -ltnpH "sport = :$1" 2>/dev/null | grep -o 'users:(("[^"]*"' | head -1 | cut -d'"' -f2 || true)"
  if [ -z "$who" ] || [ "$who" = "docker-proxy" ]; then
    who="docker: $(docker ps --format '{{.Names}} ({{.Image}}) {{.Ports}}' 2>/dev/null | grep -E ":$1->" | cut -d' ' -f1-2 | head -1 || true)"
  fi
  echo "${who:-неизвестная программа}"
}

# builtin = our Caddy container on 80/443; system-caddy = add a site to Caddy already on the host
CADDY_DIR="${CADDY_DIR:-/etc/caddy}"
PROXY_MODE="$(grep -E '^PROXY_MODE=' .env | cut -d= -f2- || true)"
if [ -z "$PROXY_MODE" ]; then
  OWNER80="$(port_owner 80)"
  OWNER443="$(port_owner 443)"
  if [ -z "$OWNER80$OWNER443" ]; then
    PROXY_MODE=builtin
  elif { [ "$OWNER80" = caddy ] || [ "$OWNER443" = caddy ]; } && [ -f "$CADDY_DIR/Caddyfile" ]; then
    PROXY_MODE=system-caddy
    say "На сервере уже работает Caddy: добавлю в него сайт $DOMAIN, остальные сайты не трогаю"
  else
    echo
    warn "Порты 80/443 нужны для HTTPS, но уже заняты:"
    [ -n "$OWNER80" ] && echo "  порт 80: $OWNER80"
    [ -n "$OWNER443" ] && echo "  порт 443: $OWNER443"
    echo
    echo "Скопируйте вывод этих команд и пришлите его Claude, он подскажет, как встроиться рядом:"
    echo "  ss -ltnp | grep -E ':(80|443) '"
    echo "  docker ps --format '{{.Names}}  {{.Image}}  {{.Ports}}'"
    echo "  ls /etc/nginx/sites-enabled /etc/caddy 2>/dev/null"
    die "установка остановлена, чтобы не сломать то, что уже работает на сервере"
  fi
  set_env PROXY_MODE "$PROXY_MODE"
fi

HOST_PORT="$(grep -E '^VIDEO_MCP_HOST_PORT=' .env | cut -d= -f2- || true)"
if [ -z "$HOST_PORT" ]; then
  HOST_PORT=8765
  while [ -n "$(port_owner "$HOST_PORT")" ]; do HOST_PORT=$((HOST_PORT + 1)); done
  set_env VIDEO_MCP_HOST_PORT "$HOST_PORT"
fi

if command -v ufw >/dev/null && [[ "$(ufw status 2>/dev/null)" == *"Status: active"* ]]; then
  ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null
fi

configure_system_caddy() {
  local main="$CADDY_DIR/Caddyfile" pattern dir glob target stamp
  stamp="$(date +%s)"
  # Prefer a directory the Caddyfile already imports, e.g. "import sites/*" or "import /etc/caddy/sites/*.caddy"
  pattern="$(grep -E '^[[:space:]]*import[[:space:]]+[^[:space:]]*\*' "$main" | head -1 | awk '{print $2}' || true)"
  if [ -n "$pattern" ]; then
    dir="$(dirname "$pattern")"
    glob="$(basename "$pattern")"
    case "$dir" in /*) ;; *) dir="$CADDY_DIR/$dir" ;; esac
    target="$dir/video-mcp${glob##*\*}"
  else
    target="$CADDY_DIR/video-mcp.caddy"
  fi
  cp "$main" "$main.bak.video-mcp.$stamp"
  mkdir -p "$(dirname "$target")"
  cat > "$target" <<CADDY
# video-mcp (added by install.sh; delete this file and reload Caddy to remove)
$DOMAIN {
	reverse_proxy 127.0.0.1:$HOST_PORT {
		flush_interval -1
		transport http {
			read_timeout 30m
			write_timeout 30m
		}
	}
}
CADDY
  if [[ "$(caddy adapt --config "$main" --adapter caddyfile 2>/dev/null)" != *"\"$DOMAIN\""* ]]; then
    # the file is not picked up by an import: import it explicitly
    grep -qF "import $target" "$main" || printf '\nimport %s\n' "$target" >> "$main"
  fi
  if ! caddy validate --config "$main" --adapter caddyfile >/tmp/video-mcp-caddy.log 2>&1; then
    cp "$main.bak.video-mcp.$stamp" "$main"
    rm -f "$target"
    cat /tmp/video-mcp-caddy.log >&2
    die "конфиг Caddy не прошёл проверку, изменения откатил; ваш Caddy работает как раньше"
  fi
  if ! systemctl reload caddy 2>/dev/null && ! caddy reload --config "$main" --adapter caddyfile 2>/dev/null; then
    cp "$main.bak.video-mcp.$stamp" "$main"
    rm -f "$target"
    die "не удалось перезагрузить Caddy, изменения откатил"
  fi
  say "Сайт $DOMAIN добавлен в Caddy ($target), копия старого конфига: $main.bak.video-mcp.$stamp"
}

[ -n "${NO_START:-}" ] && { say "NO_START: настройки записаны в $DIR/.env, запуск пропущен"; exit 0; }

# ---------------------------------------------------------------- start
say "Собираю и запускаю (первый раз 3-10 минут)"
if [ "$PROXY_MODE" = builtin ]; then
  docker compose --profile builtin-proxy up -d --build --remove-orphans
else
  docker compose up -d --build --remove-orphans
  grep -rqsF "reverse_proxy 127.0.0.1:$HOST_PORT" "$CADDY_DIR" || configure_system_caddy
fi

say "Жду, пока заработает https://$DOMAIN"
OK=0
for _ in $(seq 1 "${HEALTH_TRIES:-60}"); do
  if curl -fsS --max-time 5 "https://$DOMAIN/health" >/dev/null 2>&1; then OK=1; break; fi
  sleep 5
done

URL="https://$DOMAIN/$TOKEN/mcp"
cat > CONNECT.txt <<EOF
claude.ai / Claude Desktop / телефон:
  Настройки -> Connectors -> Add custom connector
  URL: $URL

Claude Code:
  claude mcp add --transport http video https://$DOMAIN/mcp --header "Authorization: Bearer $TOKEN"
EOF
chmod 600 CONNECT.txt .env

echo
if [ "$OK" = 1 ]; then
  say "Готово! Сервер работает."
else
  warn "Сервер пока не отвечает по HTTPS. Посмотрите логи: cd $DIR && docker compose logs caddy video-mcp"
fi
echo
cat CONNECT.txt
echo
echo "Это сохранено в $DIR/CONNECT.txt. Никому не показывайте ссылку: в ней токен доступа."
echo "Обновление: запустите ту же команду установки ещё раз."
echo "Если YouTube пишет 'not a bot': положите cookies.txt в $DIR/secrets/ и снова запустите команду установки."
