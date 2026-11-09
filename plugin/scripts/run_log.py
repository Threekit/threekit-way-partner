#!/usr/bin/env python3
"""The run log: one JSON line per specialist run, in threekit-way/runs.jsonl next to the record.

    python3 scripts/run_log.py <record> start <specialist> "<input in one line>" [--by NAME]
    python3 scripts/run_log.py <record> end <specialist> "<result in one line>" [--by NAME] [--status ok|failed|refused]
    python3 scripts/run_log.py <record> list [N]

The router writes start and end around every specialist, the Skill hook writes a line on every
threekit-way skill invocation, and the dashboard shows the log on the project's Activity tab.
It answers "which agent ran, when, on what, with what result", which the record alone does not.
The dashboard reads it from the repository on GitHub, with the record.
"""
import os
import sys
import json
import getpass
import datetime as dt


def opt(flag, default=""):
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    rec = os.path.abspath(sys.argv[1])
    path = os.path.join(os.path.dirname(rec), "runs.jsonl")
    cmd = sys.argv[2]
    if cmd == "list":
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 20
        rows = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                rows = [json.loads(line) for line in f if line.strip()]
        for r in rows[-n:]:
            print(f"{r.get('at', '')[:16]}  {r.get('event', ''):5s}  {r.get('specialist', ''):22s} {r.get('by', ''):14s} {r.get('text', '')[:80]}")
        return
    if cmd not in ("start", "end") or len(sys.argv) < 5:
        print(__doc__)
        sys.exit(2)
    row = {"at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "event": cmd, "specialist": sys.argv[3],
           "text": sys.argv[4][:300], "by": opt("--by", "") or os.environ.get("THREEKIT_WAY_USER") or getpass.getuser()}
    if cmd == "end":
        row["status"] = opt("--status", "ok")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"ok: {cmd} {row['specialist']} logged to {os.path.relpath(path)}")
    # the dashboard reads this log from the repository once it is pushed; nothing is sent from here


if __name__ == "__main__":
    main()
