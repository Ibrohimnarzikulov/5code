#!/usr/bin/env bash
# CodeAssistant / 5code — bir qatorli o'rnatuvchi.
#
#   curl -fsSL https://raw.githubusercontent.com/Ibrohimnarzikulov/5code/main/install.sh | bash
#
# Nima qiladi:
#   1. Loyihani ~/codeassistant ga clone qiladi (mavjud bo'lsa — yangilaydi)
#   2. Python venv + bog'liqliklarni o'rnatadi
#   3. `5code` buyrug'ini PATH ga qo'shadi (Claude Code uslubidagi agentic CLI)
#
# Qayta ishga tushirish xavfsiz — mavjud o'rnatishni yangilaydi (git pull).

set -euo pipefail

REPO_URL="https://github.com/Ibrohimnarzikulov/5code.git"
INSTALL_DIR="${CODEASSISTANT_DIR:-$HOME/5code}"

c_ok=$'\033[36m'; c_dim=$'\033[2m'; c_err=$'\033[31m'; c_bold=$'\033[1m'; c_off=$'\033[0m'

info() { printf '%s→%s %s\n' "$c_ok" "$c_off" "$1"; }
ok()   { printf '%s✓%s %s\n' "$c_ok" "$c_off" "$1"; }
warn() { printf '%s  %s%s\n' "$c_dim" "$1" "$c_off"; }
die()  { printf '%s✗ %s%s\n' "$c_err" "$1" "$c_off" >&2; exit 1; }

printf '%s%s5code%s %s— Claude Code uslubidagi terminal AI yordamchisi%s\n\n' \
  "$c_bold" "$c_ok" "$c_off" "$c_dim" "$c_off"

command -v git >/dev/null 2>&1 || die "git o'rnatilmagan: https://git-scm.com/downloads"
command -v python3 >/dev/null 2>&1 || die "python3 o'rnatilmagan: https://python.org/downloads"

# --- Loyihani yuklab olish (yoki yangilash) ---
if [ -d "$INSTALL_DIR/.git" ]; then
  info "Mavjud o'rnatish topildi: $INSTALL_DIR — yangilanmoqda…"
  git -C "$INSTALL_DIR" pull --ff-only
else
  info "Yuklab olinmoqda: $INSTALL_DIR"
  git clone --depth 1 "$REPO_URL" "$INSTALL_DIR"
fi

# --- Python muhiti ---
if [ ! -x "$INSTALL_DIR/.venv/bin/python" ]; then
  info "Python muhiti sozlanmoqda…"
  python3 -m venv "$INSTALL_DIR/.venv"
  "$INSTALL_DIR/.venv/bin/pip" install -q --upgrade pip
  "$INSTALL_DIR/.venv/bin/pip" install -q -r "$INSTALL_DIR/requirements.txt"
fi
ok "Python muhiti tayyor"

# --- .env ---
if [ ! -f "$INSTALL_DIR/.env" ]; then
  cp "$INSTALL_DIR/.env.example" "$INSTALL_DIR/.env"
  warn ".env yaratildi (.env.example asosida) — kerak bo'lsa AI_PROVIDER/kalitlarni tahrirlang"
fi

# --- `5code` buyrug'ini PATH ga o'rnatish ---
bash "$INSTALL_DIR/ollama/install.sh"

# --- Ollama holati ---
if ! command -v ollama >/dev/null 2>&1; then
  printf '\n'
  warn "Ollama topilmadi — 5code lokal model uchun shu kerak bo'ladi."
  warn "O'rnatish: https://ollama.com/download"
  warn "Keyin:     ollama pull qwen2.5-coder:14b && 5code --update"
fi

printf '\n%s✓ Tayyor.%s Sinab ko'\''ring:\n\n  %s5code "python da fayl o'\''qish"%s\n\n' \
  "$c_ok" "$c_off" "$c_bold" "$c_off"
