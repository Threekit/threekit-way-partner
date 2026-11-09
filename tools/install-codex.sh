#!/usr/bin/env bash
# Install The Threekit Way .AI into Codex (the CLI, the IDE extension and the desktop app), once per machine.
# Re-run to update (or let the session hook do it).
#
#   git clone https://github.com/Threekit/threekit-way-partner.git ~/.threekit-way && bash ~/.threekit-way/tools/install-codex.sh
#   (the repository is private, so a raw curl of this file returns 404 without a token)
#
# What it does:
#   1. Clones (or pulls) github.com/Threekit/threekit-way-partner into ~/.threekit-way
#   2. Links every specialist into ~/.agents/skills/<name>: Codex reads SKILL.md files there, the same files
#      Claude Code and Cursor read, in the CLI, the IDE extension and the desktop app
#   3. Writes the six agents (pr-reviewer, journey-tester and the rest) as ~/.codex/agents/<name>.toml
#   4. Adds the hooks to ~/.codex/hooks.json: at session start the contract and the record (and a pull of main
#      once a day), after every file edit the scanner. Codex does not ask: trust them once in /hooks
#   5. Adds a section to ~/.codex/AGENTS.md that tells Codex where the plugin lives, so the skills' scripts resolve
# Nothing here touches a project repository; "threekit-way, set up the repo for CUSTOMER" does that and writes
# AGENTS.md, which Codex reads in every repository.
set -euo pipefail
HOME_DIR="${HOME}"
ROOT="${THREEKIT_WAY_HOME:-$HOME_DIR/.threekit-way}"
REPO="${THREEKIT_WAY_REPO:-https://github.com/Threekit/threekit-way-partner.git}"
PLUGIN="$ROOT/plugin"
CODEX="${CODEX_HOME:-$HOME_DIR/.codex}"
SKILLS="$HOME_DIR/.agents/skills"

if [ -d "$ROOT/.git" ]; then
  git -C "$ROOT" pull -q --ff-only origin main || echo "warning: could not pull $ROOT; using the version already there"
  # run the installer just pulled, not the copy this shell already read
  if [ -z "${THREEKIT_WAY_REEXEC:-}" ] && [ "$0" -ef "$ROOT/tools/install-codex.sh" ]; then THREEKIT_WAY_REEXEC=1 exec bash "$ROOT/tools/install-codex.sh" "$@"; fi
else
  case "$REPO" in /*) SRC_URL="file://$REPO" ;; *) SRC_URL="$REPO" ;; esac
  git clone -q --depth 1 "$SRC_URL" "$ROOT"
fi
[ -d "$PLUGIN/skills" ] || { echo "no plugin/skills in $ROOT; is this the threekitway repository?"; exit 1; }

mkdir -p "$SKILLS" "$CODEX/agents"
for d in "$PLUGIN"/skills/*/; do
  name="$(basename "$d")"
  rm -rf "$SKILLS/$name"
  ln -s "${d%/}" "$SKILLS/$name"
done

python3 - "$PLUGIN" "$CODEX" <<'PY'
import json, os, re, sys
plugin, codex = sys.argv[1], sys.argv[2]

# the agents, as Codex custom agents: name, description, developer_instructions
def toml_str(s):
    return '"""\n' + s.replace("\\", "\\\\").replace('"""', '\\"""') + '\n"""'
n = 0
for f in sorted(os.listdir(os.path.join(plugin, "agents"))):
    if not f.endswith(".md"):
        continue
    text = open(os.path.join(plugin, "agents", f), encoding="utf-8").read()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        continue
    head, body = m.group(1), m.group(2).strip()
    meta = {k.strip(): v.strip().strip('"') for k, v in (l.split(":", 1) for l in head.splitlines() if ":" in l)}
    body = body.replace("${CLAUDE_PLUGIN_ROOT}", plugin)
    name = meta.get("name") or f[:-3]
    with open(os.path.join(codex, "agents", name + ".toml"), "w", encoding="utf-8") as out:
        out.write("# Written by The Threekit Way .AI installer from plugin/agents/%s; re-run tools/install-codex.sh to update.\n" % f)
        out.write("name = %s\n" % json.dumps(name))
        out.write("description = %s\n" % json.dumps(meta.get("description", "")))
        out.write("developer_instructions = %s\n" % toml_str(body))
    n += 1

# the hooks: the contract at session start, the scanner after every edit
path = os.path.join(codex, "hooks.json")
try:
    h = json.load(open(path))
except (OSError, ValueError):
    h = {}
hooks = h.setdefault("hooks", {})
env = 'CLAUDE_PLUGIN_ROOT="%s" ' % plugin
def put(event, entry):
    lst = hooks.setdefault(event, [])
    lst[:] = [x for x in lst if "threekit-way" not in json.dumps(x)]
    lst.append(entry)
put("SessionStart", {"hooks": [{"type": "command", "command": env + 'bash "%s/hooks/scripts/codex_session_start.sh"' % plugin, "timeout": 20, "statusMessage": "The Threekit Way .AI"}]})
put("PostToolUse", {"hooks": [{"type": "command", "command": env + 'python3 "%s/hooks/scripts/scan_edit.py"' % plugin, "timeout": 20}]})
json.dump(h, open(path, "w"), indent=2)

# where the plugin lives, in the global AGENTS.md, between markers so a re-run replaces only this part
path = os.path.join(codex, "AGENTS.md")
try:
    text = open(path, encoding="utf-8").read()
except OSError:
    text = ""
block = ("<!-- threekit-way:start -->\n## The Threekit Way .AI\n\n"
         "The Threekit Way .AI plugin is installed at %s. Wherever a skill or an agent says ${CLAUDE_PLUGIN_ROOT}, use %s.\n"
         "In a repository that has threekit-way/project.yaml, the session hook prints the contract and the record; follow those rules. "
         "Use the threekit-way skill for anything about a customer project; it picks the specialist.\n"
         "<!-- threekit-way:end -->\n") % (plugin, plugin)
text = re.sub(r"<!-- threekit-way:start -->.*?<!-- threekit-way:end -->\n?", "", text, flags=re.S).rstrip()
open(path, "w", encoding="utf-8").write((text + "\n\n" if text else "") + block)
print(n)
PY

python3 -c "import yaml, pg8000" 2>/dev/null || python3 -m pip install --quiet --user pyyaml pg8000 2>/dev/null || true

VERSION=$(python3 -c "import json;print(json.load(open('$PLUGIN/.claude-plugin/plugin.json'))['version'])")
echo "The Threekit Way .AI $VERSION is installed for Codex."
echo "  skills:  $(ls "$SKILLS" | grep -c .) in $SKILLS (the CLI, the IDE extension and the desktop app)"
echo "  agents:  $(ls "$CODEX/agents" | grep -c '\.toml$') in $CODEX/agents"
echo "  hooks:   $CODEX/hooks.json (the contract at session start, the scanner after every edit)"
echo "  where:   $CODEX/AGENTS.md (a section between threekit-way markers)"
python3 "$PLUGIN/scripts/dashboard_sync.py" status 2>/dev/null || echo "  dashboard: not connected yet; say 'threekit-way, connect to the dashboard' once in Codex"
echo "Restart Codex once. Codex does not ask about new hooks: run codex, type /hooks and trust the two Threekit Way hooks (until then they do not run)."
echo "Then, in a project repository: threekit-way, set up the repo for CUSTOMER"
