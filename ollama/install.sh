#!/usr/bin/env bash
# `5code` buyrug'ini terminalga o'rnatadi.
#
#   ./ollama/install.sh
#
# Sudo talab qilmaydi: skript ~/.local/bin ga qo'yiladi va kerak bo'lsa
# PATH ga qo'shiladi.

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"
TARGET="${BIN_DIR}/5code"

c_ok=$'\033[36m'; c_dim=$'\033[2m'; c_off=$'\033[0m'

mkdir -p "$BIN_DIR"

# Skriptni loyiha yo'li bilan to'ldirib nusxalaymiz
sed "s|__PROJECT_DIR__|${PROJECT_DIR}|g" "${PROJECT_DIR}/ollama/5code" > "$TARGET"
chmod +x "$TARGET"
printf '%s✓%s o'\''rnatildi: %s\n' "$c_ok" "$c_off" "$TARGET"

# PATH ni tekshirish
if ! printf '%s' ":${PATH}:" | grep -q ":${BIN_DIR}:"; then
  case "${SHELL##*/}" in
    zsh)  rc="${HOME}/.zshrc" ;;
    bash) rc="${HOME}/.bashrc" ;;
    *)    rc="" ;;
  esac

  line='export PATH="$HOME/.local/bin:$PATH"'
  if [ -n "$rc" ] && ! grep -qF "$line" "$rc" 2>/dev/null; then
    printf '\n# 5code\n%s\n' "$line" >> "$rc"
    printf '%s✓%s PATH qo'\''shildi: %s\n' "$c_ok" "$c_off" "$rc"
    printf '%s  Yangi terminal oching yoki: source %s%s\n' "$c_dim" "$rc" "$c_off"
  else
    printf '%s  PATH ga qo'\''shing: %s%s\n' "$c_dim" "$line" "$c_off"
  fi
fi

# Modelni yaratish (asos model yuklangan bo'lsa)
if command -v ollama >/dev/null 2>&1; then
  if ! curl -fsS http://localhost:11434/api/version >/dev/null 2>&1; then
    nohup ollama serve >/tmp/ollama.log 2>&1 &
    sleep 2
  fi

  base="$(awk '/^FROM /{print $2; exit}' "${PROJECT_DIR}/ollama/Modelfile")"
  if ollama list | awk '{print $1}' | grep -qxF "$base"; then
    ollama create 5code -f "${PROJECT_DIR}/ollama/Modelfile"
    printf '%s✓%s 5code modeli yaratildi\n' "$c_ok" "$c_off"
  else
    printf '%s  Asos model hali yuklanmagan. Yuklash: ollama pull %s%s\n' \
      "$c_dim" "$base" "$c_off"
    printf '%s  Keyin: 5code --update%s\n' "$c_dim" "$c_off"
  fi
else
  printf '%s  Ollama o'\''rnatilmagan: https://ollama.com/download%s\n' "$c_dim" "$c_off"
fi

printf '\nTayyor. Sinab ko'\''ring: %s5code "python da fayl o'\''qish"%s\n' "$c_ok" "$c_off"
