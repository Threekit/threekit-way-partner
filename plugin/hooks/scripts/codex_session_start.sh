#!/usr/bin/env bash
# Codex SessionStart hook: pull the latest plugin from main at most once a day, silently, then print the contract
# and the record when the session opens in a repository that follows the method (plain output becomes context).
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"   # the plugin folder
REPO="$(cd "$ROOT/.." && pwd)"                 # the threekitway checkout
STAMP="$HOME/.cache/threekit-way/codex-pull"
mkdir -p "$(dirname "$STAMP")"
if [ ! -f "$STAMP" ] || [ -n "$(find "$STAMP" -mmin +1440 2>/dev/null)" ]; then
  ( git -C "$REPO" pull -q --ff-only origin main >/dev/null 2>&1 || true )
  touch "$STAMP"
fi
CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$ROOT}" python3 "$ROOT/hooks/scripts/session_start.py" 2>/dev/null || true
exit 0
