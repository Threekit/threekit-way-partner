#!/usr/bin/env bash
# Cursor beforeSubmitPrompt hook: pull the latest plugin from main at most once a day, silently.
# Never blocks the prompt; always answers continue.
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"   # the plugin folder
REPO="$(cd "$ROOT/.." && pwd)"                 # the threekitway checkout
STAMP="$HOME/.cache/threekit-way/cursor-pull"
mkdir -p "$(dirname "$STAMP")"
if [ ! -f "$STAMP" ] || [ -n "$(find "$STAMP" -mmin +1440 2>/dev/null)" ]; then
  ( git -C "$REPO" pull -q --ff-only origin main >/dev/null 2>&1 || true )
  touch "$STAMP"
fi
echo '{"continue": true}'
