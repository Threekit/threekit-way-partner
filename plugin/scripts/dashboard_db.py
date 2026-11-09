#!/usr/bin/env python3
"""The one database The Threekit Way .AI shares between the specialists and the dashboard.

Three tables in the schema threekit_way: projects (the threekit-way/ folder of each repository, as the specialists
last sent it), events (the decisions people take on the dashboard, with the record commands that apply them) and
plugin_files (the plugin itself, published by the dashboard server from main, pulled by every machine at session
start so the skills keep themselves current).
The specialists write projects and read events from the repository they run in; the dashboard reads projects and
writes events. Nobody writes into a repository from outside it.

Where the address comes from, first found wins:
    THREEKIT_WAY_DATABASE_URL          in the environment ("off": not connected at all, for tests and evals)
    ~/.threekit-way/database.url       written once by `threekit-way, connect to the dashboard`
Never DATABASE_URL or POSTGRES_* from the environment: on a developer's machine those name the developer's own
database. The dashboard server hands its own address in (set_url), in its own process only.

    postgresql://user:password@host:5432/threekitway_db     needs the pg8000 driver: python3 -m pip install --user pg8000
    sqlite:////absolute/path.db                              a developer machine or the tests, standard library

Any address that is not this machine is reached over SSL, or not at all: no fallback to clear text. Only the
server may switch it off, explicitly (sslmode=disable in its address, or DATABASE_SSL=0), for a database inside
its own private network. The dashboard's database is Google Cloud SQL, whose certificate comes from Cloud SQL's
own authority and names the instance, not the address: database-cert.pem next to this file pins that one
certificate (verify-ca, Google's documented mode), so only that database is accepted, and the address is not
compared with the name. THREEKIT_WAY_DATABASE_CERT names another pinned file; "system" uses the system's
authorities with the full check instead.

    python3 dashboard_db.py status      where it connects and what it holds
"""
import os
import sys
import json
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard  # noqa: E402

HOME_FILE = os.path.join(os.path.expanduser("~"), ".threekit-way", "database.url")
# the team's address, the same for everyone, shipped inside the plugin: installing it connects the machine
TEAM_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "team-database.url")
SCHEMA = os.environ.get("DATABASE_SCHEMA", "threekit_way")


_SERVER = {"url": "", "on": False}


def set_url(u):
    """The dashboard server's own address (its DATABASE_URL or POSTGRES_*), for this process only."""
    _SERVER.update(url=u or "", on=True)


def url():
    if _SERVER["on"]:
        return _SERVER["url"]
    u = os.environ.get("THREEKIT_WAY_DATABASE_URL", "").strip()
    if u:
        return "" if u == "off" else u
    for path in (HOME_FILE, TEAM_FILE):
        try:
            with open(path, "r", encoding="utf-8") as f:
                u = f.read().strip()
            if u:
                return u
        except OSError:
            pass
    return ""


LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
PINNED_CERT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database-cert.pem")


def tls_context():
    """The SSL settings for the database: the pinned certificate when there is one (verify-ca), else the system's
    authorities with the name checked (verify-full). Never a context that accepts any certificate."""
    import ssl
    pin = os.environ.get("THREEKIT_WAY_DATABASE_CERT", "") or PINNED_CERT
    if pin == "system" or not os.path.exists(pin):
        return ssl.create_default_context()
    ctx = ssl.create_default_context(cafile=pin)  # only this certificate is trusted, not the system's list
    ctx.verify_flags |= getattr(ssl, "VERIFY_X509_PARTIAL_CHAIN", 0x80000)  # the pinned server certificate is the anchor
    ctx.check_hostname = False  # Cloud SQL's certificate names the instance, not the address
    return ctx


def ssl_needed(u):
    """True unless the database is on this machine, or the server explicitly said its private network has none."""
    p = urllib.parse.urlsplit(u)
    if (p.hostname or "").lower() in LOCAL_HOSTS:
        return False
    if _SERVER["on"] and ("sslmode=disable" in (p.query or "") or os.environ.get("DATABASE_SSL", "") == "0"):
        return False
    return True


def _agent():
    """The partner build on a connected computer: every call goes through the dashboard with the computer's token
    (partner_link.py), never to the database. None for the server, for the team's plugin (no partner.json), for a
    computer with a database address, and for the tests' "off"."""
    if _SERVER["on"] or url() or os.environ.get("THREEKIT_WAY_DATABASE_URL", "").strip() == "off":
        return None
    try:
        import partner_link
    except ImportError:
        return None
    return partner_link if partner_link.connected() else None


def configured():
    return bool(url()) or bool(_agent())


def where():
    """The address without the password, for messages."""
    a = _agent()
    if a:
        return a.base()
    u = url()
    return u.split("@")[-1] if "@" in u else u


def connect(u=None):
    """(connection, placeholder, table prefix). Creates the database on a first Postgres start when allowed."""
    u = u or url()
    if not u:
        raise RuntimeError("no database address: run `threekit-way, connect to the dashboard` once on this machine")
    if u.startswith("sqlite:"):
        import sqlite3
        path = u[len("sqlite://"):][1:]
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        c = sqlite3.connect(path, timeout=10)
        return c, "?", ""
    if not u.startswith(("postgres://", "postgresql://")):
        raise RuntimeError("the database address must start with postgresql:// or sqlite:")
    try:
        import pg8000.dbapi as pg
    except ImportError:
        raise RuntimeError("the pg8000 driver is missing: python3 -m pip install --user pg8000")
    p = urllib.parse.urlsplit(u)
    kw = dict(user=urllib.parse.unquote(p.username or ""), password=urllib.parse.unquote(p.password or ""),
              host=p.hostname, port=p.port or 5432, timeout=15 if _SERVER["on"] else 5)  # a machine never waits long
    dbname = (p.path or "/").lstrip("/") or "postgres"
    sslc = tls_context() if ssl_needed(u) else None

    def missing_db(e):
        return "3D000" in str(e) or "does not exist" in str(e)

    try:
        c = pg.connect(database=dbname, ssl_context=sslc, **kw)
    except Exception as e:  # noqa: BLE001
        if missing_db(e) and dbname != "postgres":
            admin = pg.connect(database="postgres", ssl_context=sslc, **kw)
            admin.autocommit = True
            admin.cursor().execute('CREATE DATABASE "' + dbname.replace('"', "") + '"')
            admin.close()
            c = pg.connect(database=dbname, ssl_context=sslc, **kw)
        elif sslc and "certificate" in str(e).lower():
            raise RuntimeError("the database's SSL certificate is not trusted on this machine; the connection stays closed rather than unencrypted")
        elif sslc and "ssl" in str(e).lower():
            raise RuntimeError("the database does not accept SSL; the address must reach it over SSL (no clear text off this machine)")
        else:
            raise
    return c, "%s", SCHEMA + "."


def open_db():
    """A connection with the tables in place. The tables are created only when missing, so a narrower database
    user (schema.sql, threekit_way_agent: no CREATE, no DELETE) works once the server has made them."""
    c, ph, pre = connect()
    cur = c.cursor()
    try:
        cur.execute(f"SELECT 1 FROM {pre}projects WHERE 1 = 0")
        cur.execute(f"SELECT 1 FROM {pre}events WHERE 1 = 0")
        cur.execute(f"SELECT 1 FROM {pre}plugin_files WHERE 1 = 0")
        return c, ph, pre
    except Exception:  # noqa: BLE001
        c.rollback()
    if pre:
        cur.execute("CREATE SCHEMA IF NOT EXISTS " + SCHEMA)
    cur.execute("CREATE TABLE IF NOT EXISTS " + pre + "projects (id TEXT PRIMARY KEY, customer TEXT, source TEXT, files TEXT NOT NULL, received TEXT NOT NULL, sender TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS " + pre + "events (id TEXT PRIMARY KEY, project TEXT NOT NULL, at TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, args TEXT NOT NULL, cmds TEXT NOT NULL)")
    cur.execute("CREATE TABLE IF NOT EXISTS " + pre + "plugin_files (path TEXT PRIMARY KEY, text TEXT NOT NULL, version TEXT NOT NULL, updated TEXT NOT NULL)")
    c.commit()
    return c, ph, pre


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def save_project(pid, files, source, sender=""):
    """The threekit-way/ folder of one project: {relative path: text}. Returns the time stored."""
    a = _agent()
    if a:
        return a.api("POST", "/api/agent/project", {"id": pid, "files": files}).get("received", "")
    pid = guard.safe_id(pid)
    for rel in files:
        guard.safe_rel(rel)
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        customer = ""
        for line in (files.get("threekit-way/project.yaml") or "").splitlines():
            if line.startswith("customer:"):
                customer = line.split(":", 1)[1].strip().strip('"').strip("'")
                break
        when = now()
        # one statement, no DELETE: the machines' database user has no DELETE grant (schema.sql)
        cur.execute(f"INSERT INTO {pre}projects (id, customer, source, files, received, sender) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}) "
                    "ON CONFLICT (id) DO UPDATE SET customer = EXCLUDED.customer, source = EXCLUDED.source, files = EXCLUDED.files, "
                    "received = EXCLUDED.received, sender = EXCLUDED.sender",
                    (pid, customer, source, json.dumps(files, ensure_ascii=False), when, (sender or "")[:80]))
        c.commit()
        return when
    finally:
        c.close()


def project(pid):
    a = _agent()
    if a:
        return a.api("GET", "/api/agent/project?id=" + urllib.parse.quote(str(pid))).get("project")
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT id, customer, source, files, received, sender FROM {pre}projects WHERE id = {ph}", (pid,))
        r = cur.fetchone()
        return {"id": r[0], "customer": r[1], "source": r[2], "files": json.loads(r[3]), "received": r[4], "sender": r[5]} if r else None
    finally:
        c.close()


def fingerprint():
    """What changed, cheaply: the count and the latest time of projects and events. The dashboard compares it
    between page loads and reads the records again when a specialist has sent something."""
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT COUNT(*), MAX(received) FROM {pre}projects")
        a = cur.fetchone()
        cur.execute(f"SELECT COUNT(*), MAX(id) FROM {pre}events")
        b = cur.fetchone()
        return f"{a[0]}:{a[1] or ''}:{b[0]}:{b[1] or ''}"
    finally:
        c.close()


def projects():
    a = _agent()
    if a:
        return a.api("GET", "/api/agent/projects").get("projects") or []
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT id, customer, source, files, received, sender FROM {pre}projects ORDER BY id")
        return [{"id": r[0], "customer": r[1], "source": r[2], "files": json.loads(r[3]), "received": r[4], "sender": r[5]} for r in cur.fetchall()]
    finally:
        c.close()


def delete_project(pid):
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"DELETE FROM {pre}projects WHERE id = {ph}", (pid,))
        cur.execute(f"DELETE FROM {pre}events WHERE project = {ph}", (pid,))
        c.commit()
    finally:
        c.close()


def add_event(pid, actor, action, args, cmds):
    """A decision taken on the dashboard, with the record.py commands that apply it."""
    import secrets
    pid = guard.safe_id(pid)
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        eid = "%013d-%s" % (int(time.time() * 1000), secrets.token_hex(3))
        cur.execute(f"INSERT INTO {pre}events (id, project, at, actor, action, args, cmds) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})",
                    (eid, pid, now(), (actor or "")[:80], action, json.dumps(args, ensure_ascii=False), json.dumps(cmds, ensure_ascii=False)))
        c.commit()
        return eid
    finally:
        c.close()


def events(pid, since=""):
    """Decisions for a project after the event id `since` (empty: all), oldest first."""
    a = _agent()
    if a:
        return a.api("GET", "/api/agent/events?" + urllib.parse.urlencode({"project": pid, "since": since or ""})).get("events") or []
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT id, at, actor, action, args, cmds FROM {pre}events WHERE project = {ph} AND id > {ph} ORDER BY id", (pid, since or ""))
        return [{"id": r[0], "at": r[1], "by": r[2], "action": r[3], "args": json.loads(r[4]), "cmds": json.loads(r[5])} for r in cur.fetchall()]
    finally:
        c.close()


if __name__ == "__main__":
    if not configured():
        print("no database address; run `threekit-way, connect to the dashboard` once on this machine")
        sys.exit(1)
    try:
        ps = projects()
    except Exception as e:  # noqa: BLE001
        print(f"cannot reach the database at {where()}: {e}")
        sys.exit(1)
    print(f"database {where()}: {len(ps)} project(s)")
    for p in ps:
        print(f"  {p['id']:24s} {p['customer'] or '':24s} {p['source'] or '':8s} {p['received']}  {p['sender'] or ''}")


# ---------- the plugin itself: published by the server, pulled by every machine ----------

def save_plugin(version, files):
    """Replace the published plugin: {relative path: text} and its version."""
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        when = now()
        cur.execute(f"DELETE FROM {pre}plugin_files")
        for rel, text in files.items():
            cur.execute(f"INSERT INTO {pre}plugin_files (path, text, version, updated) VALUES ({ph}, {ph}, {ph}, {ph})", (rel, text, version, when))
        c.commit()
    finally:
        c.close()


def plugin_version():
    a = _agent()
    if a:
        return a.api("GET", "/api/agent/method").get("version") or ""
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT version FROM {pre}plugin_files WHERE path = {ph}", (".claude-plugin/plugin.json",))
        r = cur.fetchone()
        return r[0] if r else ""
    finally:
        c.close()


def plugin_files():
    a = _agent()
    if a:
        return a.api("GET", "/api/agent/method?files=1", timeout=60).get("files") or {}
    c, ph, pre = open_db()
    try:
        cur = c.cursor()
        cur.execute(f"SELECT path, text FROM {pre}plugin_files")
        return {r[0]: r[1] for r in cur.fetchall()}
    finally:
        c.close()
