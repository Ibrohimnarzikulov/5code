#!/usr/bin/env bash
# CodeAssistant — backend (1221) + frontend (1991)
#
#   ./run.sh          ikkalasini ham (dev rejim)
#   ./run.sh api      faqat backend
#   ./run.sh web      faqat frontend
#   ./run.sh build    React'ni yig'ib, faqat backend (bitta port: 1221)

set -euo pipefail
cd "$(dirname "$0")"

BACKEND_PORT=1221
FRONTEND_PORT=1991

c_acc=$'\033[36m'; c_dim=$'\033[2m'; c_off=$'\033[0m'

# --- Python muhiti ---
if [ ! -d .venv ]; then
  echo "→ venv yaratilmoqda…"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "⚠︎  .env topilmadi — .env.example dan nusxa olinmoqda"
  cp .env.example .env
fi

start_api() {
  printf '%sBackend%s  → http://127.0.0.1:%s  (%s/docs)\n' \
    "$c_acc" "$c_off" "$BACKEND_PORT" "http://127.0.0.1:$BACKEND_PORT"
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" --reload
}

start_web() {
  [ -d web/node_modules ] || (echo "→ npm install…" && cd web && npm install --silent)
  printf '%sFrontend%s → http://localhost:%s\n' "$c_acc" "$c_off" "$FRONTEND_PORT"
  cd web && npm run dev
}

case "${1:-all}" in
  api) start_api ;;
  web) start_web ;;
  build)
    [ -d web/node_modules ] || (cd web && npm install --silent)
    (cd web && npm run build)
    printf '%sReact yig'\''ildi. Bitta port: http://127.0.0.1:%s%s\n' \
      "$c_dim" "$BACKEND_PORT" "$c_off"
    exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port "$BACKEND_PORT"
    ;;
  all)
    start_api & api_pid=$!
    trap 'kill $api_pid 2>/dev/null || true' EXIT INT TERM
    sleep 2
    start_web
    ;;
  *) echo "Noma'lum: $1  (api | web | build | all)"; exit 1 ;;
esac
