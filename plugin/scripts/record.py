#!/usr/bin/env python3
"""Read and update a Threekit Way project record without hand-editing YAML.

Usage:
  record.py <project.yaml> status
      One status line, the same one the entry point opens with.
  record.py <project.yaml> get <dotted.path>
  record.py <project.yaml> set <dotted.path> <value> --by <specialist> --note "<what changed>"
      Value is parsed as YAML (so true, 14, "text" and [a, b] all work).
  record.py <project.yaml> add <list.path> '<yaml or json object>' --by <specialist> --note "<what changed>"
      Appends an item to a list (positions, product_requests, weekly_checks, ...).
  record.py <project.yaml> gate <gate_name> <YYYY-MM-DD> "<evidence>" --by <specialist>
      Dates a gate and moves the phase forward when the method says so.
  record.py <project.yaml> next-id positions|product_requests
      Prints the next id (P-003, R-002).

Every set, add and gate appends a log line. The record is validated after every change and
the change is refused when it would make the record invalid.
"""
import sys
import os
import datetime as dt

try:
    import yaml
except ImportError:
    print("error: PyYAML is missing. Install with: pip install pyyaml")
    sys.exit(2)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from validate_record import validate  # noqa: E402

GATE_MOVES_PHASE = {
    "sow_signed": "kickoff",
    "done_signed": "build",
    "pass_rate_signed": "after",
}


class Dumper(yaml.SafeDumper):
    def increase_indent(self, flow=False, indentless=False):
        return super().increase_indent(flow, False)


def load(path):
    import json
    with open(path, "r", encoding="utf-8") as f:
        record = yaml.safe_load(f) or {}
    return json.loads(json.dumps(record, default=str))  # dates as text, so every tool sees one type


def save(path, record):
    with open(path, "w", encoding="utf-8") as f:
        f.write("# The Threekit Way .AI project record. Updated by specialists, validated on every change.\n")
        yaml.dump(record, f, Dumper=Dumper, sort_keys=False, allow_unicode=True, default_flow_style=False)


def get_path(record, dotted):
    node = record
    for part in dotted.split("."):
        if isinstance(node, list):
            node = node[int(part)]
        else:
            node = node[part]
    return node


def set_path(record, dotted, value):
    parts = dotted.split(".")
    node = record
    for part in parts[:-1]:
        if isinstance(node, list):
            node = node[int(part)]
            continue
        if part not in node or node[part] is None:
            node[part] = {}
        node = node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def opt(args, flag, default=""):
    if flag in args:
        i = args.index(flag)
        return args[i + 1]
    return default


def log(record, by, note):
    record.setdefault("log", []).append({"date": dt.date.today().isoformat(), "by": by, "change": note})


def status(record):
    today = dt.date.today()
    phase = record.get("phase", "?")
    parts = [record.get("customer", "?"), phase]
    build = record.get("build") or {}
    if phase == "build" and build.get("start") and build.get("planned_weeks"):
        start = dt.date.fromisoformat(str(build["start"]))
        week = max(1, (today - start).days // 7 + 1)
        parts.append(f"week {week} of {build['planned_weeks']}")
    gates = record.get("gates") or {}
    order = ["sow_signed", "done_signed", "first_screen_seen", "pass_rate_signed", "learnings_written"]
    labels = {
        "sow_signed": "SOW signed", "done_signed": "done signed", "first_screen_seen": "first screen seen",
        "pass_rate_signed": "pass rate signed", "learnings_written": "learnings written",
    }
    due = {
        "sow_signed": "", "done_signed": "", "first_screen_seen": "",
        "pass_rate_signed": build.get("launch_planned", ""),
        "learnings_written": (dt.date.fromisoformat(str(build["launch_actual"])) + dt.timedelta(days=30)).isoformat()
        if build.get("launch_actual") else "",
    }
    nxt = next((g for g in order if not (gates.get(g) or {}).get("date")), None)
    if nxt:
        parts.append(f"next gate: {labels[nxt]}" + (f" due {due[nxt]}" if due.get(nxt) else ""))
    open_pos = sum(1 for p in record.get("positions") or [] if not p.get("answered"))
    waiting = sum(1 for r in record.get("product_requests") or [] if not r.get("answer"))
    parts.append(f"{open_pos} open position{'s' if open_pos != 1 else ''}")
    parts.append(f"{waiting} request{'s' if waiting != 1 else ''} waiting on product")
    checks = [c.get("date") for c in record.get("weekly_checks") or [] if c.get("date")]
    parts.append(f"path to metric last reviewed {max(checks)}" if checks else "path to metric not yet reviewed")
    return ", ".join(str(p) for p in parts) + "."


def commit(path, record, before):
    errors, _ = validate(record)
    if errors:
        print("refused: the change would make the record invalid")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)
    save(path, record)


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(2)
    path, cmd, args = sys.argv[1], sys.argv[2], sys.argv[3:]
    record = load(path)
    by = opt(args, "--by", "unknown")
    note = opt(args, "--note", "")

    if cmd == "status":
        print(status(record))
    elif cmd == "get":
        print(yaml.safe_dump(get_path(record, args[0]), default_flow_style=False).strip())
    elif cmd == "set":
        value = yaml.safe_load(args[1])
        set_path(record, args[0], value)
        log(record, by, note or f"set {args[0]}")
        commit(path, record, None)
        print(f"ok: {args[0]} set")
    elif cmd == "add":
        item = yaml.safe_load(args[1])
        try:
            target = get_path(record, args[0])
        except KeyError:
            set_path(record, args[0], [])  # a list the record did not have yet (notes on older records)
            target = get_path(record, args[0])
        if target is None:
            set_path(record, args[0], [])
            target = get_path(record, args[0])
        if not isinstance(target, list):
            print(f"error: {args[0]} is not a list")
            sys.exit(1)
        target.append(item)
        log(record, by, note or f"added to {args[0]}")
        commit(path, record, None)
        print(f"ok: added to {args[0]}")
    elif cmd == "gate":
        gate, date, evidence = args[0], args[1], args[2]
        if gate not in record.get("gates", {}):
            print(f"error: unknown gate {gate}")
            sys.exit(1)
        dt.date.fromisoformat(date)
        record["gates"][gate] = {"date": date, "evidence": evidence}
        moved = GATE_MOVES_PHASE.get(gate)
        if moved:
            record["phase"] = moved
        if gate == "pass_rate_signed" and not (record.get("build") or {}).get("launch_actual"):
            record.setdefault("build", {})["launch_actual"] = date
        log(record, by, f"gate {gate} passed on {date}" + (f", phase moved to {moved}" if moved else ""))
        commit(path, record, None)
        print(f"ok: gate {gate} dated {date}" + (f", phase is now {moved}" if moved else ""))
    elif cmd == "next-id":
        prefix = {"positions": "P", "product_requests": "R"}[args[0]]
        n = len(record.get(args[0]) or []) + 1
        print(f"{prefix}-{n:03d}")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
