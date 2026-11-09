#!/usr/bin/env python3
"""PostToolUse hook on Write/Edit (Claude Code) and every tool in Codex (apply_patch names its files; a shell write is found by what changed). Runs the method's pattern scan on the file that was just written and
reports hits, so a coding agent learns immediately when it put data, rules or prompts in code, patched
model output or hardcoded an edge case. Only in repositories that follow The Threekit Way .AI."""
import os
import sys
import json
import subprocess
import re

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def in_method_repo(path):
    d = os.path.dirname(os.path.abspath(path))
    for _ in range(8):
        if os.path.exists(os.path.join(d, "threekit-way", "project.yaml")):
            return True
        parent = os.path.dirname(d)
        if parent == d:
            return False
        d = parent
    return False


def method_root(path):
    d = os.path.abspath(path) if os.path.isdir(path) else os.path.dirname(os.path.abspath(path))
    for _ in range(8):
        if os.path.exists(os.path.join(d, "threekit-way", "project.yaml")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def changed_since_last_look(root):
    """Codex also writes files through its shell, which names no file: the project's files changed since the last
    look (kept per project in ~/.cache/threekit-way), so each change is reported once. The first look takes only the
    last ten minutes."""
    import time
    import hashlib
    state_path = os.path.join(os.path.expanduser("~"), ".cache", "threekit-way", "codex-scan-" + hashlib.sha1(root.encode()).hexdigest()[:12] + ".json")
    try:
        seen = json.load(open(state_path))
    except (OSError, ValueError):
        seen = None
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-m", "-o", "--exclude-standard"], capture_output=True, text=True, timeout=10).stdout.split("\n")
    except (OSError, subprocess.SubprocessError):
        out = []
    now, files, fresh = time.time(), {}, []
    for rel in filter(None, (x.strip() for x in out)):
        full = os.path.join(root, rel)
        if not os.path.isfile(full) or rel.startswith("threekit-way/"):
            continue
        m = os.path.getmtime(full)
        files[rel] = m
        if (seen is None and now - m < 600) or (seen is not None and seen.get(rel) != m):
            fresh.append(full)
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        json.dump(files, open(state_path, "w"))
    except OSError:
        pass
    return fresh[:20]


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    ti = payload.get("tool_input") or {}
    codex = "turn_id" in payload  # Codex sends the turn; Claude Code does not
    path = ti.get("file_path") or ti.get("path") or ""
    paths = [path] if path else []
    if not path:
        # Codex edits files with apply_patch: the paths are in the patch text, relative to the session's folder
        found = re.findall(r"\*\*\* (?:Update|Add) File: (.+)", json.dumps(ti).replace("\\n", "\n"))
        cwd = payload.get("cwd") or os.getcwd()
        paths = [os.path.join(cwd, p) if not os.path.isabs(p) else p for p in dict.fromkeys(x.strip().strip('"\\') for x in found)]
        if not paths and codex:
            root = method_root(cwd)
            paths = changed_since_last_look(root) if root else []
    text = "\n".join(t for t in (scan(p) for p in paths) if t)
    if not text:
        return
    if codex:
        # Codex gives a PostToolUse hook's words to the agent through additionalContext
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": text}}))
    else:
        print(text)


def scan(path):
    if not path or not os.path.exists(path) or not in_method_repo(path):
        return ""
    if "/threekit-way/" in path.replace("\\", "/"):
        return ""
    r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "scan_patterns.py"), path], capture_output=True, text=True, timeout=15)
    lines = [l for l in r.stdout.splitlines() if " · " in l]
    if not lines:
        return ""
    out = ["The Threekit Way .AI review found %d thing(s) in %s that belong in the platform or in the library, not in code:" % (len(lines), os.path.basename(path))]
    out += ["  " + l.split(os.path.dirname(path) + os.sep)[-1] for l in lines[:12]]
    out.append("Fix where it lives (a rule, product data, a prompt, or this project's own code) or run platform-gap if the platform cannot hold it. pr-review will fail the pull request otherwise.")
    return "\n".join(out)


if __name__ == "__main__":
    main()
