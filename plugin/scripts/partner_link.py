#!/usr/bin/env python3
"""How a partner's computer reaches the dashboard (docs/PARTNER-ACCESS-2026-11-09.md, Part 3, D5).

Only in the partner build: it carries .claude-plugin/partner.json ({"dashboard": "https://way.3kit.ai"}). The team's
plugin has no such file and never uses anything here; its computers keep their direct database connection.

Connecting, once per computer (and again when the token ends, after 30 days):
  1. the plugin makes a code and a link, way.3kit.ai/connect?code=ABCD-EFGH, and waits in the background
  2. the person opens the link, signs in with the code Cloudflare emails them, and presses Connect this computer
  3. the waiting plugin claims its token and keeps it in ~/.config/threekit-way/token (readable by the person only)
Every read and send then goes through the dashboard's /api/agent/ paths with that token, never the database: the
person's own projects, their decisions, the method. A refused token (ended, revoked) is dropped and the next session
shows the link again.

    python3 partner_link.py status       connected or not, and to which dashboard
    python3 partner_link.py connect      show the link and wait for the approval (up to 15 minutes)
    python3 partner_link.py wait CODE    the background waiter (started by the plugin itself)
    python3 partner_link.py library [words]        search the library files Threekit shares with partners (Part 4)
    python3 partner_link.py submit <project id> [--note TEXT] <file> ...
                                         send this repository's custom files to Threekit for the library, instead of
                                         a pull request on the library (paths relative to the repository root)
"""
import os
import sys
import json
import time
import secrets
import string
import subprocess
import urllib.request
import urllib.error
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
PARTNER_FILE = os.path.join(os.path.dirname(HERE), ".claude-plugin", "partner.json")
CONF = os.environ.get("THREEKIT_WAY_CONFIG") or os.path.join(os.path.expanduser("~"), ".config", "threekit-way")
TOKEN_FILE = os.path.join(CONF, "token")
PENDING_FILE = os.path.join(CONF, "connect.json")
CODE_MINUTES = 14


def partner():
    """The partner build's settings, or None in the team's plugin."""
    try:
        with open(PARTNER_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and d.get("dashboard") else None
    except (OSError, ValueError):
        return None


def base():
    p = partner() or {}
    return (os.environ.get("THREEKIT_WAY_DASHBOARD") or p.get("dashboard") or "").rstrip("/")


def token():
    try:
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            t = f.read().strip()
        return t if t.startswith("twk_") else ""
    except OSError:
        return ""


def _private_write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)


def drop_token():
    try:
        os.remove(TOKEN_FILE)
    except OSError:
        pass


def connected():
    return bool(partner() and token())


def api(method, path, body=None, timeout=20):  # noqa: C901
    """One call to the dashboard with this computer's token. A refused token is dropped."""
    t = token()
    if not t:
        raise RuntimeError("this computer is not connected to The Threekit Way .AI: " + connect_line())
    req = urllib.request.Request(base() + path, data=json.dumps(body).encode("utf-8") if body is not None else None, method=method,
                                 headers={"Authorization": "Bearer " + t, "Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            drop_token()
            raise RuntimeError("the dashboard ended this computer's connection: " + connect_line())
        try:
            msg = json.loads(e.read().decode("utf-8") or "{}").get("error", "")
        except ValueError:
            msg = ""
        raise RuntimeError(f"the dashboard refused ({e.code}): {msg}")


def _new_code():
    a = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(a) for _ in range(4)) + "-" + "".join(secrets.choice(a) for _ in range(4))


def start():
    """The link to open, with a background waiter for it. Reuses a code still waiting."""
    try:
        with open(PENDING_FILE, "r", encoding="utf-8") as f:
            p = json.load(f)
        if p.get("until", 0) > time.time() and p.get("code"):
            return base() + "/connect?code=" + p["code"]
    except (OSError, ValueError):
        pass
    code = _new_code()
    _private_write(PENDING_FILE, json.dumps({"code": code, "until": time.time() + CODE_MINUTES * 60}))
    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), "wait", code], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    except OSError:
        pass
    return base() + "/connect?code=" + code


def connect_line():
    return f"open {start()} , sign in with the code sent to your email, press Connect this computer, then carry on"


def wait(code, minutes=CODE_MINUTES, every=3):
    """Claim the token once the person approved the code. True when connected."""
    until = time.time() + minutes * 60
    while time.time() < until:
        req = urllib.request.Request(base() + "/api/agent/claim", data=json.dumps({"code": code}).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    t = json.loads(r.read().decode("utf-8")).get("token", "")
                    if t.startswith("twk_"):
                        _private_write(TOKEN_FILE, t)
                        try:
                            os.remove(PENDING_FILE)
                        except OSError:
                            pass
                        return True
        except (OSError, ValueError):
            pass
        time.sleep(every)
    return False


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if not partner():
        print("not the partner build: this plugin connects as the Threekit team's does")
        return
    if cmd == "status":
        if not token():
            print("not connected: " + connect_line())
            return
        try:
            me = api("GET", "/api/agent/whoami")
            print(f"connected to {base()} as {me.get('name') or me.get('email')} ({me.get('role')})")
        except RuntimeError as e:
            print(str(e))
    elif cmd == "connect":
        if token():
            print("already connected to " + base())
            return
        link = start()
        print("Open " + link + " , sign in with the code sent to your email and press Connect this computer. Waiting...")
        code = urllib.parse.parse_qs(urllib.parse.urlsplit(link).query).get("code", [""])[0]
        print("connected" if wait(code) else "not connected: the link ended; run this again")
    elif cmd == "wait" and len(sys.argv) > 2:
        wait(sys.argv[2])
    elif cmd == "library":
        q = " ".join(sys.argv[2:])
        try:
            files = api("GET", "/api/agent/library?" + urllib.parse.urlencode({"q": q})).get("files") or []
        except RuntimeError as e:
            sys.exit(str(e))
        if not files:
            print("nothing shared with partners matches" + (f" '{q}'" if q else "") + ": write the code, it goes to the library at handover")
            return
        for f in files:
            print(f"## {f['file']}\nWhat it does: {f.get('what') or ''}\nTalks to: {f.get('goto') or ''}\nFrom: {f.get('project') or ''}, {f.get('copied') or ''}\n"
                  f"First line of your copy: {f['first_line']}\n\n{f.get('text') or ''}\n")
    elif cmd == "submit" and len(sys.argv) > 3:
        args, note = sys.argv[3:], ""
        if "--note" in args:
            i = args.index("--note")
            note = args[i + 1] if i + 1 < len(args) else ""
            args = args[:i] + args[i + 2:]
        files = {}
        for rel in args:
            with open(rel, "r", encoding="utf-8", errors="replace") as fh:
                files[os.path.normpath(rel).replace(os.sep, "/")] = fh.read()
        try:
            r = api("POST", "/api/agent/library/submission", {"project": sys.argv[2], "files": files, "note": note}, timeout=60)
        except RuntimeError as e:
            sys.exit(str(e))
        print(f"submission {r.get('id')} sent: {len(files)} file(s); a Threekit admin packages it into the library")
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
