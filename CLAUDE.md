# video-mcp

MCP-сервер на VPS пользователя: даёт Claude смотреть видео (`src/video_mcp`) и, с `REELS_ENABLED=1`,
делать и публиковать вертикальные ролики (`src/video_mcp/reels`). Установка и настройки — в `README.md`.

- Проект с роликами и партнёрским оффером: **сначала прочитать `docs/reels/README.md`**. Там решения, правила
  текста рекламы, **правила кадра (всё российское: улицы, ДПС, рубли, без чужих брендов)**, цены, статус запуска
  и следующие шаги. Сценарии, конкуренты и стратегия лежат в `docs/reels/`.
- Заработок: **актуальный план — `docs/plan-v2.md`** (пересчёт 29.09), схема запуска — `docs/launch.md`, исследование — `docs/money-research.md`.
- Шортсы Nexus (YouTube @Nexus.systems): **стиль — `docs/nexus/style-guide.md`** (образец — instagram @aldoniq), сценарии и воронка — `docs/nexus/`.
- Промо-ролики продукта (анимация настоящего интерфейса): скилл **`.claude/skills/video-shotcraft`** (Remotion).
  Готовое промо панели — `promo/nexus-panel/` (как пересобрать — его `README.md`), файлы — `docs/nexus/promo/`.
  Следующее — обзор на YouTube с озвучкой ElevenLabs: план и запись экрана — `promo/nexus-review/README.md`.
- Тесты: `pip install -e ".[dev,reels]" && pytest -q` (нужен ffmpeg и шрифт DejaVu).
- Секреты (ключи API, токены) в репозиторий не коммитить. На сервере они живут в `.env`, а пишет их
  туда `deploy/reels-setup.sh`.
- Пользователь пишет по-русски, отвечать по-русски.
