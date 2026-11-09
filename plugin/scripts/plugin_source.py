#!/usr/bin/env python3
"""The plugin keeps itself current from the shared database, without GitHub, a catalog or a file.

The dashboard server deploys from main; at every start it publishes the plugin's files into the database
(table plugin_files). Every connected machine pulls them at session start into ~/.threekit-way/current/ and
each skill and agent reads its current text from there. Install once, never reinstall. Only text travels this way
(the method: skills, references, templates, agents); the scripts and hooks are the installed ones.

    python3 plugin_source.py publish [plugin dir] [--if-newer]   store the method's text files and version
                                                     (--if-newer: the server at start, never over a later publication)
    python3 plugin_source.py fetch [--daily]         a machine: pull the current files when they changed
                                                     (--daily: only the first session of the day asks the database)
    python3 plugin_source.py root                    print the folder to read the plugin from (current or installed)
    python3 plugin_source.py skill <name>            print the current SKILL.md of a specialist when it is newer
                                                     than the installed one, else "installed version is current"
    python3 plugin_source.py agent <name>            the same for an agent
    python3 plugin_source.py status                  installed version, current version, where it reads from
"""
import os
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dashboard_db as ddb  # noqa: E402

INSTALLED = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(HERE)
HOME_DIR = os.path.join(os.path.expanduser("~"), ".threekit-way")
CURRENT = os.path.join(HOME_DIR, "current")
EXT = (".md", ".json", ".yaml", ".yml", ".txt", ".mdc")  # the method as text; scripts and hooks stay with the installed copy
SKIP = ("evals/", ".tmp", "__pycache__", "/.")


def vtuple(v):
    try:
        return tuple(int(x) for x in str(v).split(".")[:3])
    except ValueError:
        return (0,)


def version_of(root):
    try:
        with open(os.path.join(root, ".claude-plugin", "plugin.json"), "r", encoding="utf-8") as f:
            return json.load(f).get("version", "")
    except (OSError, ValueError):
        return ""


def files_of(root):
    out = {}
    for dirpath, dirs, names in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root).replace(os.sep, "/")
        if rel_dir == ".":
            rel_dir = ""
        dirs[:] = [d for d in dirs if not d.startswith(".") or d == ".claude-plugin"]
        for n in names:
            rel = (rel_dir + "/" + n) if rel_dir else n
            if not n.endswith(EXT) or any(s in rel + "/" for s in SKIP):
                continue
            with open(os.path.join(dirpath, n), "r", encoding="utf-8", errors="replace") as f:
                out[rel] = f.read()
    return out


def stamp_of(root):
    """version + publication time of a pulled copy, or '' when none."""
    try:
        with open(os.path.join(root, ".claude-plugin", "published.json"), "r", encoding="utf-8") as f:
            d = json.load(f)
        return f"{d.get('version', '')}@{d.get('updated', '')}"
    except (OSError, ValueError):
        return ""


def publish(root, if_newer=False):
    """Store the method as it is under root. Run by the change agent from any connected machine after a change to
    the method, and by the server at start with if_newer (it never overwrites a later publication): every other
    machine has it at its next session start."""
    version = version_of(root)
    if not version:
        sys.exit("no .claude-plugin/plugin.json under " + root)
    if if_newer:
        have = ddb.plugin_version()
        if have and vtuple(have) >= vtuple(version):
            print(f"method {have} is published already (this copy is {version}); nothing to do")
            return
    files = files_of(root)
    updated = ddb.now()
    files[".claude-plugin/published.json"] = json.dumps({"version": version, "updated": updated, "by": os.environ.get("THREEKIT_WAY_USER") or os.environ.get("USER") or "server"})
    ddb.save_plugin(version, files)
    print(f"method {version} published to the dashboard at {updated}: {len(files)} file(s); every connected machine has it at its next session")


STAMP = os.path.join(HOME_DIR, "last-check")


def checked_today():
    try:
        with open(STAMP, "r", encoding="utf-8") as f:
            return f.read().strip() == time.strftime("%Y-%m-%d")
    except OSError:
        return False


def mark_checked():
    try:
        os.makedirs(HOME_DIR, exist_ok=True)
        with open(STAMP, "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d"))
    except OSError:
        pass


def fetch(quiet=False, daily=False):
    """Pull the current files when their version differs from what is cached. Returns the current version or ''.
    daily: only the first session of the day looks at the database; the rest of the day runs on the pulled copy."""
    if not ddb.configured():
        return ""
    if daily and checked_today():
        return version_of(CURRENT)
    try:
        version = ddb.plugin_version()
    except Exception as e:  # noqa: BLE001
        if not quiet:
            print(f"dashboard not reached ({ddb.where()}): {str(e)[:120]}")
        return ""
    if not version:
        return ""
    mark_checked()
    files = ddb.plugin_files()
    try:
        d = json.loads(files.get(".claude-plugin/published.json") or "{}")
        stamp = f"{d.get('version', '')}@{d.get('updated', '')}"
    except ValueError:
        stamp = version + "@"
    if stamp_of(CURRENT) == stamp:
        return version
    import shutil
    tmp = CURRENT + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    for rel, text in files.items():
        full = os.path.join(tmp, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(text)
    shutil.rmtree(CURRENT, ignore_errors=True)
    os.replace(tmp, CURRENT)
    if not quiet:
        print(f"threekit-way {version} is current on this machine (installed {version_of(INSTALLED) or '?'})")
    return version


def use_current():
    """The pulled copy is read when it exists and is not older than the installed one (same version counts:
    the method may have been republished without a version change)."""
    cur, inst = version_of(CURRENT), version_of(INSTALLED)
    return bool(cur) and vtuple(cur) >= vtuple(inst) and os.path.abspath(CURRENT) != os.path.abspath(INSTALLED)


def root():
    """The folder to read the plugin from: the pulled copy, else the installed one."""
    return CURRENT if use_current() else INSTALLED


def partner_build():
    return os.path.exists(os.path.join(INSTALLED, ".claude-plugin", "partner.json"))


def text_of(kind, name):
    if not use_current():
        return None
    path = os.path.join(CURRENT, "skills", name, "SKILL.md") if kind == "skill" else os.path.join(CURRENT, "agents", name + ".md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "publish":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        publish(os.path.abspath(args[0]) if args else INSTALLED, if_newer="--if-newer" in sys.argv)
    elif cmd == "fetch":
        fetch(quiet="--quiet" in sys.argv, daily="--daily" in sys.argv)
    elif cmd == "root":
        print(root())
    elif cmd in ("skill", "agent") and len(sys.argv) > 2:
        t = text_of(cmd, sys.argv[2])
        if t is None and partner_build():
            # the partner build carries no method: it comes from the dashboard once this computer is connected
            fetch(quiet=True)
            t = text_of(cmd, sys.argv[2])
            if t is None:
                import partner_link
                print("STOP: this computer is not connected to The Threekit Way .AI, so the method is not here yet. Tell the person, in one line: "
                      + partner_link.connect_line() + ". When they paste the key, run `python3 " + os.path.join(HERE, "partner_link.py")
                      + " key <the key>`, then run this same command again.")
                return
        if t is None:
            print("installed version is current")
        else:
            print(f"# Current version {version_of(CURRENT)} (installed {version_of(INSTALLED)}). Below, ${{CLAUDE_PLUGIN_ROOT}}/scripts stays {INSTALLED}/scripts; every other ${{CLAUDE_PLUGIN_ROOT}} path (skills, references, templates, agents) means {CURRENT}\n")
            print(t)
    elif cmd == "status":
        inst, cur = version_of(INSTALLED), version_of(CURRENT)
        print(f"installed {inst or '?'} at {INSTALLED}")
        print(f"current   {cur or 'none pulled yet'}" + (f" at {CURRENT}" if cur else ""))
        print("reads from " + root())
        if ddb.configured():
            try:
                print("dashboard has " + (ddb.plugin_version() or "nothing published yet"))
            except Exception as e:  # noqa: BLE001
                print(f"dashboard not reached ({ddb.where()}): {str(e)[:120]}")
        else:
            print("skills update through the Threekit organization plugin; nothing to connect")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
