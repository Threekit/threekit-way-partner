#!/usr/bin/env python3
"""PostToolUse hook on the Skill tool. Every time a threekit-way skill is invoked in a repository that follows
the method, one line goes to threekit-way/runs.jsonl: when, which specialist, what was asked, by whom.
The run log is what lets the change agent review the agents instead of trusting them."""
import os
import sys
import json
import getpass
import datetime as dt


def find_record(start):
    d = os.path.abspath(start)
    for _ in range(8):
        p = os.path.join(d, "threekit-way", "project.yaml")
        if os.path.exists(p):
            return p
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return
    ti = payload.get("tool_input") or {}
    skill = str(ti.get("skill") or "")
    if not skill.startswith("threekit-way"):
        return
    rec = find_record(payload.get("cwd") or os.getcwd())
    if not rec:
        return
    row = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": "skill",
           "specialist": skill.split(":")[-1], "text": str(ti.get("args") or "")[:300],
           "by": os.environ.get("THREEKIT_WAY_USER") or getpass.getuser(), "session": str(payload.get("session_id") or "")[:12]}
    with open(os.path.join(os.path.dirname(rec), "runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
