# video-mcp — Claude смотрит видео

Свой MCP-сервер, аналог [mcp-video-analyzer](https://github.com/guimatheus92/mcp-video-analyzer),
который работает на вашем VPS. Даёте Claude ссылку на YouTube (или другой сайт, или файл на сервере),
и он получает **и картинку, и звук**:

- **ключевые кадры** (JPEG) в местах смены сцены, каждый с таймкодом;
- **транскрипт с таймкодами**: субтитры автора или автосубтитры YouTube, а если их нет —
  распознавание речи через Whisper прямо на сервере;
- **единую ленту**: кадр, потом то, что говорят до следующего кадра, потом следующий кадр и т.д.
  Так Claude видит, что показывают в момент, когда об этом говорят;
- метаданные: название, канал, дата, просмотры, главы, описание.

Видео скачивается на VPS (через yt-dlp, по умолчанию не выше 720p) и кэшируется, поэтому
повторные запросы к тому же видео выполняются быстро.

## Инструменты

| Инструмент | Что делает |
|---|---|
| `analyze_video` | Главный. Метаданные + ключевые кадры + речь на одной ленте. `detail`: `brief` (без кадров), `standard` (6–16 кадров), `detailed` (до 40). Можно передать `start`/`end`. |
| `analyze_moment` | Фрагмент крупным планом: равномерные кадры и речь между `start` и `end`. |
| `get_frames_at` | Кадры в точные моменты (`["1:23", "4:05"]`), чтобы прочитать слайд, код или таблицу. Для мелкого текста передайте `frame_width=1280`. |
| `get_frames` | Только кадры: по сменам сцен или равномерно. |
| `get_transcript` | Только текст с таймкодами. Длинный транскрипт отдаётся частями (`start=` для продолжения). |
| `get_video_info` | Метаданные без скачивания видео, список языков субтитров, превью. |
| `list_local_videos` | Файлы, загруженные в папку сервера `data/videos`. |

Источником может быть:
- любая ссылка на YouTube: `watch`, `youtu.be`, `shorts`, `live`, или просто ID видео;
- ссылки на сайты, которые поддерживает yt-dlp: VK, Rutube, Vimeo, TikTok, Instagram, X, Twitch VOD и другие;
- прямые ссылки на `.mp4`;
- файлы в `data/videos` на сервере (например, `lecture.mp4`).

## Как это устроено

```
Claude (claude.ai / Desktop / Claude Code)
        │  MCP (Streamable HTTP, HTTPS + токен)
        ▼
Caddy :443  ──►  video-mcp :8000
                   ├─ yt-dlp (+Deno)    → метаданные, субтитры, видео ≤720p
                   ├─ ffmpeg            → детекция смен сцен, кадры
                   ├─ faster-whisper    → речь → текст, если нет субтитров
                   └─ /data/cache       → кэш (TTL 48 ч, лимит 15 ГБ)
```

## Установка на VPS — одной командой

Нужен чистый VPS с Ubuntu или Debian: от 2 ГБ RAM и 20 ГБ диска. Зайдите на него по SSH и выполните:

```bash
curl -fsSL https://raw.githubusercontent.com/Rklm-it/mcp-video-cl/HEAD/install.sh | sudo bash
```

Скрипт спросит только домен. Если домена нет, нажмите Enter: будет использован бесплатный адрес
вида `1-2-3-4.sslip.io` по IP сервера, HTTPS-сертификат выдаётся на него автоматически. Дальше скрипт сам:
- поставит Docker;
- скачает код в `/opt/video-mcp`;
- сгенерирует секретный токен;
- подберёт настройки Whisper под объём памяти;
- откроет порты 80/443;
- соберёт и запустит сервер с HTTPS.

Если на сервере уже работает **Caddy**, скрипт не трогает его сайты. Он добавляет свой отдельный
файл-сайт (например, `/etc/caddy/sites/video-mcp`), проверяет конфиг и перезагружает Caddy.
Если проверка не прошла, изменения откатываются. Если порты заняты чем-то другим, скрипт
останавливается и показывает, кто их занял.

В конце он выведет готовую ссылку для Claude. Она же сохраняется в `/opt/video-mcp/CONNECT.txt`.

**Обновление** — та же команда ещё раз. Токен и настройки сохраняются.

<details>
<summary>Установка вручную</summary>

```bash
git clone https://github.com/Rklm-it/mcp-video-cl.git /opt/video-mcp
cd /opt/video-mcp
cp .env.example .env
nano .env        # DOMAIN=video.ваш-домен.ru, VIDEO_MCP_TOKEN=$(openssl rand -hex 32)
mkdir -p data/videos secrets
docker compose up -d --build
docker compose logs -f video-mcp
```

Проверка: `curl https://ДОМЕН/health` должен вернуть `ok`. Для сертификата нужны открытые порты 80 и 443.
</details>

> Если на сервере уже стоит nginx, закомментируйте сервис `caddy`, откройте
> `ports: ["127.0.0.1:8000:8000"]` у `video-mcp` и добавьте в nginx:
> ```nginx
> location / {
>     proxy_pass http://127.0.0.1:8000;
>     proxy_http_version 1.1;
>     proxy_set_header Host $host;
>     proxy_buffering off;            # прогресс идёт через SSE
>     proxy_read_timeout 1800s;
> }
> ```

## Подключение к Claude

У сервера два адреса, оба защищены токеном:
- `https://ДОМЕН/mcp` — токен передаётся в заголовке `Authorization: Bearer ТОКЕН`;
- `https://ДОМЕН/ТОКЕН/mcp` — секретный путь для клиентов, которые не умеют передавать заголовки (claude.ai).

### claude.ai, Claude Desktop, мобильное приложение
Настройки → **Connectors** → **Add custom connector**:
- Name: `Video`
- URL: `https://video.ваш-домен.ru/ВАШ_ТОКЕН/mcp`

Коннектор синхронизируется на всех устройствах. Включите его в чате через меню инструментов и
пишите, например: *«Посмотри видео https://youtu.be/… и сделай конспект со скриншотами ключевых моментов»*.

### Claude Code
```bash
claude mcp add --transport http video https://video.ваш-домен.ru/mcp \
  --header "Authorization: Bearer ВАШ_ТОКЕН"
```
Если Claude Code жалуется на размер ответа, поднимите лимит: `export MAX_MCP_OUTPUT_TOKENS=60000`.

### Локально, без сервера (stdio)
```bash
pip install -e ".[whisper]"   # плюс ffmpeg в системе
claude mcp add video -e VIDEO_MCP_DATA_DIR=$HOME/.cache/video-mcp -- video-mcp --transport stdio
```

## YouTube блокирует VPS

YouTube часто не отдаёт видео на IP дата-центров и отвечает *«Sign in to confirm you're not a bot»*.
Сервер показывает эту ошибку Claude вместе с подсказкой. Что можно сделать, от простого к сложному:

1. **Обновить yt-dlp.** Он обновляется при каждом старте контейнера (`YTDLP_AUTO_UPDATE=1`),
   поэтому достаточно `docker compose restart video-mcp`.
2. **Cookies.** Лучше взять запасной Google-аккаунт: активный аккаунт с сервера YouTube может ограничить.
   Войдите в YouTube в приватном окне браузера, экспортируйте cookies расширением
   «Get cookies.txt LOCALLY» в формате Netscape и закройте окно. Файл положите в
   `/opt/video-mcp/secrets/cookies.txt` и снова запустите команду установки: она подхватит файл сама.
   Подробности: [инструкция yt-dlp](https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies).
3. **PO-токены.** `docker compose --profile pot up -d` и `YTDLP_POT_PROVIDER_URL=http://pot-provider:4416` в `.env`.
4. **Прокси.** Резидентный или мобильный: `YTDLP_PROXY=socks5://user:pass@host:port`.

Субтитры и метаданные блокируются реже, чем скачивание видео. Если скачать видео не удалось,
`get_transcript` и `analyze_video(detail="brief")` часто всё равно работают.

## Свои видео

Загрузите файл в папку `data/videos` на сервере:
```bash
scp lecture.mp4 root@vps:/opt/video-mcp/data/videos/
```
После этого пишите Claude: *«Разбери lecture.mp4»*. Субтитры сервер берёт из файла рядом
(`lecture.srt` / `lecture.vtt`) или из самого контейнера. Если их нет, речь распознаёт Whisper.

## Расход контекста

Кадр шириной 768 px стоит около 450 токенов. `standard` с 16 кадрами — около 7 тысяч токенов
плюс транскрипт. Практичные приёмы:
- для длинных видео сначала `analyze_video(detail="brief")`: транскрипт и главы, без кадров;
  потом `analyze_video(start=…, end=…)` или `analyze_moment` на интересных местах;
- для чтения текста с экрана — `get_frames_at` с `frame_width=1280`;
- транскрипт в одном ответе ограничен (`VIDEO_MCP_TRANSCRIPT_MAX_CHARS`), а в конце есть подсказка,
  откуда продолжить.

Видео длиннее 30 минут при запросе с `start`/`end` скачиваются не целиком, а только нужным
куском. Видео длиннее часа скачиваются в 480p.

## Настройки (`.env`)

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `VIDEO_MCP_TOKEN` | — | секретный токен (обязателен) |
| `DOMAIN` | — | домен для HTTPS (Caddy) |
| `YTDLP_COOKIES` | — | путь к cookies.txt внутри контейнера |
| `YTDLP_PROXY` | — | прокси для yt-dlp |
| `YTDLP_POT_PROVIDER_URL` | — | адрес bgutil PO-token провайдера |
| `YTDLP_AUTO_UPDATE` | `1` | обновлять yt-dlp при старте |
| `WHISPER_ENABLED` | `1` | распознавать речь, если нет субтитров |
| `WHISPER_MODEL` | `small` | `tiny`/`base`/`small`/`medium`/`large-v3` |
| `VIDEO_MCP_MAX_HEIGHT` | `720` | максимальное качество скачивания |
| `VIDEO_MCP_LONG_VIDEO_MAX_HEIGHT` | `480` | качество для видео длиннее `VIDEO_MCP_LONG_VIDEO_MINUTES` (60) |
| `VIDEO_MCP_SECTION_DOWNLOAD_MINUTES` | `30` | с какой длины качать только нужный кусок |
| `VIDEO_MCP_MAX_DURATION_HOURS` | `6` | более длинные видео — только с `start`/`end` |
| `VIDEO_MCP_FRAME_WIDTH` | `768` | ширина кадров по умолчанию |
| `VIDEO_MCP_FRAME_MAX_WIDTH` | `1600` | максимальная ширина кадра |
| `VIDEO_MCP_JPEG_QUALITY` | `72` | качество JPEG |
| `VIDEO_MCP_TRANSCRIPT_MAX_CHARS` | `40000` | лимит транскрипта в одном ответе |
| `VIDEO_MCP_CACHE_TTL_HOURS` | `48` | сколько хранить скачанное |
| `VIDEO_MCP_CACHE_MAX_GB` | `15` | лимит кэша на диске |
| `VIDEO_MCP_ALLOW_PRIVATE_URLS` | `0` | разрешить ссылки на локальную сеть |

## Обслуживание

```bash
cd /opt/video-mcp
docker compose logs -f video-mcp      # логи
docker compose restart video-mcp      # перезапуск + обновление yt-dlp
```
Обновление всего сервера — снова запустите команду установки.

## Разработка

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"            # нужен ffmpeg в системе
pytest
```

Тесты генерируют ролик ffmpeg'ом (красная → зелёная → синяя сцена с субтитрами) и прогоняют
все инструменты через настоящий MCP-клиент. Они проверяют скачивание по HTTP через yt-dlp,
частичную загрузку длинных видео, fallback на Whisper, авторизацию по заголовку и по секретному
пути.
