FROM python:3.12-slim

ARG WITH_WHISPER=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 app \
 && python -m venv /opt/venv \
 && chown -R app:app /opt/venv
ENV PATH=/opt/venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    VIDEO_MCP_DATA_DIR=/data \
    VIDEO_MCP_LOCAL_DIR=/data/videos \
    VIDEO_MCP_HOST=0.0.0.0 \
    VIDEO_MCP_PORT=8000

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
# yt-dlp[default,deno] also installs Deno, the JS runtime yt-dlp needs for YouTube.
RUN pip install --no-cache-dir . bgutil-ytdlp-pot-provider \
 && if [ "$WITH_WHISPER" = "1" ]; then pip install --no-cache-dir ".[whisper]"; fi \
 && chown -R app:app /opt/venv

COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD curl -fs http://127.0.0.1:8000/health || exit 1
ENTRYPOINT ["/entrypoint.sh"]
