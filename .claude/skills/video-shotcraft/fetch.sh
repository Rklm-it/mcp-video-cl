#!/usr/bin/env bash
# Скачивает скилл video-shotcraft (github.com/Vincentwei1021/video-shotcraft,
# Apache-2.0) закреплённой версии в кэш и печатает путь к нему.
#
# В репозиторий скилл не кладём: он весит ~120 МБ (звуки, примеры, галерея),
# а нужен только когда делаем ролик. Версия закреплена — обновлять осознанно,
# поменяв PIN и проверив, что promo/ рендерится.
set -euo pipefail

PIN="43bd349a136651865ecfa6ea1cf012f6e957d304" # 2026-10-18
REPO="https://github.com/Vincentwei1021/video-shotcraft"
DIR="${VIDEO_SHOTCRAFT_DIR:-${XDG_CACHE_HOME:-$HOME/.cache}/video-shotcraft/$PIN}"

if [ ! -f "$DIR/SKILL.md" ]; then
  mkdir -p "$DIR"
  git -C "$DIR" init -q
  git -C "$DIR" remote add origin "$REPO" 2>/dev/null || true
  git -C "$DIR" fetch -q --depth 1 origin "$PIN"
  git -C "$DIR" checkout -q FETCH_HEAD
fi

if [ "${1:-}" = "--template" ] && [ ! -d "$DIR/template/node_modules" ]; then
  (cd "$DIR/template" && npm ci --no-audit --no-fund >/dev/null)
fi

echo "$DIR"
