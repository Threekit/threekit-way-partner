#!/usr/bin/env python3
"""The link between a project repository and the dashboard: the shared database, nothing else.

    python3 dashboard_sync.py push      send threekit-way/ (the record, the specs, the run log) to the database
    python3 dashboard_sync.py pull      apply the decisions people took on the dashboard to the record here
    python3 dashboard_sync.py both      pull, then push (what every specialist run does)
    python3 dashboard_sync.py status    where the database is and whether this project is in it

The repository is the record; the dashboard is where people decide. The specialists call this after every
run, so the dashboard shows what the repository holds, and every decision taken on the page (an approval, a
gate, a note, a weekly check, a field) is applied here with record.py, in order, exactly as the page did,
before the next specialist reads the record. Nothing writes into a repository from outside it.

Once per machine: `threekit-way, connect to the dashboard` stores the database address in
~/.threekit-way/database.url (or set THREEKIT_WAY_DATABASE_URL). THREEKIT_WAY_PROJECT overrides the project id
(default: the repository folder name). Quiet when the machine is not connected: a specialist must still run.
"""
import os
import re
import sys
import json
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dashboard_db as ddb  # noqa: E402

RECORD_PY = os.path.join(HERE, "record.py")
EXT = (".yaml", ".yml", ".md", ".jsonl", ".json", ".txt")
MAX = 1_500_000


def repo_root(start="."):
    d = os.path.abspath(start)
    for _ in range(8):
        if os.path.isdir(os.path.join(d, "threekit-way")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def project_id(root):
    pid = os.environ.get("THREEKIT_WAY_PROJECT") or os.path.basename(root)
    return re.sub(r"[^a-z0-9]+", "-", pid.lower()).strip("-")[:48]


def who(root):
    """The person: THREEKIT_WAY_USER, else the git identity of the checkout, else the login."""
    if os.environ.get("THREEKIT_WAY_USER"):
        return os.environ["THREEKIT_WAY_USER"]
    for key in ("user.name", "user.email"):
        try:
            v = subprocess.run(["git", "config", key], cwd=root, capture_output=True, text=True, timeout=5).stdout.strip()
            if v:
                return v
        except (OSError, subprocess.SubprocessError):
            pass
    import getpass
    return getpass.getuser()


def push(root, quiet=False):
    files = {}
    base = os.path.join(root, "threekit-way")
    for dirpath, _dirs, names in os.walk(base):
        for n in names:
            if n.startswith(".") or not n.endswith(EXT):
                continue
            full = os.path.join(dirpath, n)
            if os.path.getsize(full) > MAX:
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                files[rel] = f.read()
    if "threekit-way/project.yaml" not in files:
        print("threekit-way/project.yaml is missing; nothing sent")
        return
    pid = project_id(root)
    prev = ddb.project(pid)
    if prev and prev.get("source") == "created":
        # the project was started on the dashboard: its record wins, the page's values fill what it left empty
        files["threekit-way/project.yaml"] = merge_created(prev["files"].get("threekit-way/project.yaml", ""), files["threekit-way/project.yaml"])
        with open(os.path.join(root, "threekit-way", "project.yaml"), "w", encoding="utf-8") as f:
            f.write(files["threekit-way/project.yaml"])
    when = ddb.save_project(pid, files, "repo", who(root))
    print(f"sent {len(files)} file(s) of {pid} to the dashboard ({when})")


def merge_created(created_text, incoming_text):
    """The repository's record wins; fields it leaves empty keep the value typed on the page."""
    try:
        import yaml
    except ImportError:
        return incoming_text
    try:
        c = yaml.safe_load(created_text) or {}
        inc = yaml.safe_load(incoming_text) or {}
    except yaml.YAMLError:
        return incoming_text
    changed = False
    for path in ("customer", "project", "repo", "tenant.id", "tenant.url", "tenant.catalog", "people.project_manager", "people.developer",
                 "people.customer_sponsor", "people.product_contact", "sow.url", "sow.rom_url", "value_brief.path"):
        node_c, node_i = c, inc
        keys = path.split(".")
        for k in keys[:-1]:
            node_c = (node_c or {}).get(k) or {}
            if not isinstance(node_i.get(k), dict):
                node_i[k] = {}
            node_i = node_i[k]
        if not node_i.get(keys[-1]) and node_c.get(keys[-1]):
            node_i[keys[-1]] = node_c[keys[-1]]
            changed = True
    return yaml.safe_dump(inc, sort_keys=False, allow_unicode=True) if changed else incoming_text


def pull(root, quiet=False):
    cursor_path = os.path.join(root, "threekit-way", ".dashboard-cursor")
    since = ""
    if os.path.exists(cursor_path):
        with open(cursor_path, "r", encoding="utf-8") as f:
            since = f.read().strip()
    evs = ddb.events(project_id(root), since)
    record = os.path.join(root, "threekit-way", "project.yaml")
    applied = 0
    for ev in evs:
        for cmd in ev.get("cmds") or []:
            r = subprocess.run([sys.executable, RECORD_PY, record] + list(cmd), capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                print(f"decision {ev['id']} ({ev.get('action')} by {ev.get('by')}) did not apply: {(r.stdout + r.stderr).strip()[-200:]}")
                continue
            applied += 1
        since = ev["id"]
    if evs:
        with open(cursor_path, "w", encoding="utf-8") as f:
            f.write(since)
    if evs or not quiet:
        print(f"{len(evs)} decision(s) from the dashboard, {applied} command(s) applied to the record")
    return len(evs)


def main():
    what = sys.argv[1] if len(sys.argv) > 1 else "both"
    quiet = "--quiet" in sys.argv
    if what not in ("pull", "push", "both", "status"):
        sys.exit("usage: dashboard_sync.py push | pull | both | status [--quiet]")
    root = repo_root()
    if what == "status":
        if not ddb.configured():
            sys.exit("not connected: run `threekit-way, connect to the dashboard` once on this machine")
        try:
            ps = ddb.projects()
        except Exception as e:  # noqa: BLE001
            sys.exit(f"cannot reach the database at {ddb.where()}: {e}")
        print(f"connected to {ddb.where()}: {len(ps)} project(s) on the dashboard")
        if root:
            pid = project_id(root)
            p = next((x for x in ps if x["id"] == pid), None)
            print(f"this repository ({pid}): " + (f"last sent {p['received']} by {p['sender']}" if p else "not sent yet; the next specialist run sends it"))
        return
    if not root:
        sys.exit("no threekit-way/ folder here; run this from the project repository")
    if not ddb.configured():
        if quiet:
            return
        sys.exit("not connected to the dashboard: run `threekit-way, connect to the dashboard` once on this machine")
    try:
        if what in ("pull", "both"):
            pull(root, quiet)
        if what in ("push", "both"):
            push(root, quiet)
    except Exception as e:  # noqa: BLE001
        if quiet:
            print(f"dashboard not reached ({ddb.where()}): {str(e)[:120]}")
            return
        sys.exit(f"dashboard not reached ({ddb.where()}): {e}")


if __name__ == "__main__":
    main()
