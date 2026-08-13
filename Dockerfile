# --- CodeAssistant ---
# 1-bosqich: React frontendni yig'ish
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json* ./
RUN npm install --silent
COPY web/ ./
RUN npm run build

# 2-bosqich: Python backend + tayyor frontend
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY --from=web /web/dist ./web/dist

RUN mkdir -p /srv/data /srv/workspace

ENV DATABASE_URL=sqlite+aiosqlite:////srv/data/codeassistant.db \
    WORKSPACE_ROOT=/srv/workspace

EXPOSE 1221

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://localhost:1221/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "1221"]
