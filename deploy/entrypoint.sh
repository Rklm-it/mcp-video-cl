#!/bin/sh
set -e

mkdir -p /data/videos /data/cache /data/models
export HOME=/home/app
export HF_HOME=/data/models/huggingface
chown -R app:app /data 2>/dev/null || true

# YouTube changes often and old yt-dlp versions stop working: update on every start.
if [ "${YTDLP_AUTO_UPDATE:-1}" = "1" ]; then
  setpriv --reuid=app --regid=app --init-groups \
    pip install --no-cache-dir --quiet --upgrade "yt-dlp[default,deno]" bgutil-ytdlp-pot-provider \
    || echo "WARNING: yt-dlp update failed, using the bundled version"
fi

exec setpriv --reuid=app --regid=app --init-groups video-mcp "$@"
