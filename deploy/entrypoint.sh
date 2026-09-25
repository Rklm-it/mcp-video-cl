#!/bin/sh
set -e

mkdir -p /data/videos /data/cache /data/models
export HOME=/home/app
export HF_HOME=/data/models/huggingface
chown -R app:app /data 2>/dev/null || true

as_app() { setpriv --reuid=app --regid=app --init-groups "$@"; }

# YouTube changes often and old yt-dlp versions stop working: update on every start.
if [ "${YTDLP_AUTO_UPDATE:-1}" = "1" ]; then
  as_app pip install --no-cache-dir --quiet --upgrade "yt-dlp[default,deno]" \
    || echo "WARNING: yt-dlp update failed, using the bundled version"
fi

# The PO-token plugin is only useful together with its provider service (compose profile "pot");
# without it every YouTube request logs a failed ping to 127.0.0.1:4416.
if [ -n "${YTDLP_POT_PROVIDER_URL:-}" ]; then
  as_app pip install --no-cache-dir --quiet --upgrade bgutil-ytdlp-pot-provider \
    || echo "WARNING: could not install bgutil-ytdlp-pot-provider"
elif as_app pip show --quiet bgutil-ytdlp-pot-provider >/dev/null 2>&1; then
  as_app pip uninstall --yes --quiet bgutil-ytdlp-pot-provider || true
fi

exec setpriv --reuid=app --regid=app --init-groups video-mcp "$@"
