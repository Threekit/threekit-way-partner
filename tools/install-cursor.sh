#!/usr/bin/env bash
# Install The Threekit Way .AI into Cursor, once per machine. Re-run to update (or let the hook do it).
#
#   git clone https://github.com/Threekit/threekit-way-partner.git ~/.threekit-way && bash ~/.threekit-way/tools/install-cursor.sh
#   (the repository is private, so a raw curl of this file returns 404 without a token)
#
# What it does:
#   1. Clones (or pulls) github.com/Threekit/threekit-way-partner into ~/.threekit-way
#   2. Links every specialist into ~/.cursor/skills/<name> (Cursor reads SKILL.md files there, the same
#      files Claude Code reads), so "threekit-way", "spec-kit", "pr-review" and the rest are available
#      to Cursor's agent in every project
#   3. Writes ~/.cursor/hooks.json so the scanner runs after every file edit in a repository that follows
#      the method, and the plugin pulls the latest main at the start of each session
#   4. Writes a user rule that tells Cursor where the plugin lives, so the skills' scripts resolve
# Nothing here touches a project repository; "threekit-way, set up the repo for CUSTOMER" does that
# from either editor and writes CLAUDE.md, AGENTS.md and .cursor/rules/threekit-way.mdc.
set -euo pipefail
HOME_DIR="${HOME}"
ROOT="${THREEKIT_WAY_HOME:-$HOME_DIR/.threekit-way}"
REPO="${THREEKIT_WAY_REPO:-https://github.com/Threekit/threekit-way-partner.git}"
PLUGIN="$ROOT/plugin"
CURSOR="$HOME_DIR/.cursor"

if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" pull -q --ff-only origin main || echo "warning: could not pull $ROOT; using the version already there"
  # run the installer just pulled, not the copy this shell already read
  if [ -z "${THREEKIT_WAY_REEXEC:-}" ] && [ "$0" -ef "$ROOT/tools/install-cursor.sh" ]; then THREEKIT_WAY_REEXEC=1 exec bash "$ROOT/tools/install-cursor.sh" "$@"; fi
else
  # a local folder (the tests) is cloned like a remote one: git's hard-linked local clone refuses on some systems
  case "$REPO" in /*) SRC_URL="file://$REPO" ;; *) SRC_URL="$REPO" ;; esac
  git clone -q --depth 1 "$SRC_URL" "$ROOT"
fi
[ -d "$PLUGIN/skills" ] || { echo "no plugin/skills in $ROOT; is this the threekitway repository?"; exit 1; }

mkdir -p "$CURSOR/skills" "$CURSOR/rules"
for d in "$PLUGIN"/skills/*/; do
  name="$(basename "$d")"
  rm -rf "$CURSOR/skills/$name"
  ln -s "$d" "$CURSOR/skills/$name"
done

# Where the plugin lives, for every skill that says ${CLAUDE_PLUGIN_ROOT}
cat > "$CURSOR/rules/threekit-way-plugin.mdc" <<EOF
---
description: Where The Threekit Way .AI plugin lives on this machine
alwaysApply: true
---
The Threekit Way .AI plugin is installed at $PLUGIN. Wherever a skill says \${CLAUDE_PLUGIN_ROOT}, use $PLUGIN.
In a repository that has threekit-way/project.yaml, start by running: python3 $PLUGIN/hooks/scripts/session_start.py
and follow the rules it prints. Use the threekit-way skill for anything about a customer project; it picks the specialist.
EOF

# Hooks: scanner after every edit, update at session start
python3 - "$CURSOR/hooks.json" "$PLUGIN" <<'PY'
import json, sys, os
path, plugin = sys.argv[1], sys.argv[2]
try:
    h = json.load(open(path))
except (OSError, ValueError):
    h = {}
h.setdefault("version", 1)
hooks = h.setdefault("hooks", {})
def put(event, cmd):
    lst = hooks.setdefault(event, [])
    lst[:] = [x for x in lst if "threekit-way" not in json.dumps(x)]
    lst.append({"command": cmd})
put("afterFileEdit", f"python3 {plugin}/hooks/scripts/cursor_after_edit.py")
put("beforeSubmitPrompt", f"bash {plugin}/hooks/scripts/cursor_update.sh")
json.dump(h, open(path, "w"), indent=2)
PY

# the two pure-Python libraries the scripts use (the record, the dashboard link); quiet when already there or offline
python3 -c "import yaml, pg8000" 2>/dev/null || python3 -m pip install --quiet --user pyyaml pg8000 2>/dev/null || true

VERSION=$(python3 -c "import json;print(json.load(open('$PLUGIN/.claude-plugin/plugin.json'))['version'])")
echo "The Threekit Way .AI $VERSION is installed for Cursor."
echo "  skills:  $(ls "$CURSOR/skills" | grep -c .) in $CURSOR/skills"
echo "  hooks:   $CURSOR/hooks.json (scanner after every edit, update before each prompt)"
echo "  rule:    $CURSOR/rules/threekit-way-plugin.mdc"
python3 "$PLUGIN/scripts/dashboard_sync.py" status 2>/dev/null || echo "  dashboard: not connected yet; say 'threekit-way, connect to the dashboard' once in Cursor"
echo "Restart Cursor once. Then, in a project repository, ask the agent: threekit-way, set up the repo for CUSTOMER"
