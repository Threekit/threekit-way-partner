#!/usr/bin/env python3
"""What crosses the shared database is checked here, on the server and on every machine, with one set of rules.

  project ids        lowercase letters, digits and dashes only; anything else is refused before it becomes a folder
  file paths         relative, inside their folder; an absolute path, a .. or a backslash is refused
  decisions          the record commands a decision taken on the dashboard may run: the page's own actions on the
                     page's own fields, nothing else (no repo, no phase, no arbitrary path)
  the method's text  signed with a key only the change agent and the dashboard server hold; a machine refuses a
                     publication that is unsigned or signed with another key, and keeps its last good copy

    python3 guard.py keygen [file]     make a signing key (the change agent, once); prints the public half to paste
                                       into PUBLIC_KEYS below and the line for the server's environment
    python3 guard.py pubkey [file]     print the public half of an existing key

Signing key, first found wins: THREEKIT_WAY_SIGNING_KEY (the key itself, the server's environment),
THREEKIT_WAY_SIGNING_KEY_FILE, ~/.config/threekit-way/signing-key.json (the change agent's machine). RSA with
SHA-256 (PKCS #1 v1.5), standard library only, so every machine verifies without installing anything.
"""
import os
import re
import sys
import json
import hmac
import hashlib

ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def safe_id(pid):
    """The project id, or ValueError. Ids become folder names on the server, so nothing but [a-z0-9-]."""
    pid = str(pid or "")
    if not ID_RE.match(pid):
        raise ValueError(f"not a valid project id: {pid[:40]!r} (lowercase letters, digits and dashes only)")
    return pid


def safe_rel(rel):
    """A relative path that stays inside its folder, or ValueError."""
    rel = str(rel or "")
    parts = rel.split("/")
    if (not rel or rel.startswith("/") or "\\" in rel or "\x00" in rel or re.match(r"^[A-Za-z]:", rel)
            or any(p in ("", ".", "..") for p in parts)):
        raise ValueError(f"not a safe relative path: {rel[:80]!r}")
    return rel


def safe_join(base, rel):
    """base/rel, refused when the result would leave base (after resolving links)."""
    rel = safe_rel(rel)
    base_real = os.path.realpath(base)
    full = os.path.realpath(os.path.join(base_real, *rel.split("/")))
    if not full.startswith(base_real + os.sep):
        raise ValueError(f"path leaves its folder: {rel[:80]!r}")
    return full


# ---------- decisions: what the page may change, and the commands a decision may carry ----------

# The record fields a person may set from the page. The server refuses any other field and every machine
# refuses a decision that carries one. Prefixes end with a dot; the others are exact.
PAGE_FIELDS = ("people.", "tenant.", "build.launch_planned", "build.planned_weeks", "build.start", "build.launch_actual",
               "launch.session_recording", "launch.pass_report", "launch.change_notices", "sow.metric_shared_by_customer", "sow.change_control_priced",
               "sow.url", "sow.rom_url", "sow.path", "sow.signed", "customer", "project", "value_brief.path",
               "docs.handover_accepted")
# A consultant sets the tenant and the consultant fields only (the name and the sign-in email).
CONSULTANT_FIELDS = ("tenant.", "people.developer")
_FIELD_RE = re.compile(r"^[a-z_]+(\.[a-z_]+)*$")


def page_field(field, prefixes=PAGE_FIELDS):
    field = str(field or "")
    if not _FIELD_RE.match(field):
        return False
    return any(field.startswith(p) if p.endswith(".") else (field == p or field.startswith(p + ".")) for p in prefixes)


_SET_INDEXED = (re.compile(r"^positions\.\d+\.(answered|approved_by)$"), re.compile(r"^weekly_checks\.\d+\.sent_to_customer$"),
                re.compile(r"^after\.metric_reports\.\d+\.sent_to_customer$"),
                re.compile(r"^product_requests\.\d+\.(answer|answered|product_reasoning)$"))
_ADD_LISTS = ("notes", "weekly_checks", "after.metric_reports")
_GATES = ("sow_signed", "done_signed", "first_screen_seen", "pass_rate_signed", "learnings_written")


def allowed_command(cmd):
    """None when this record.py command is one a dashboard decision may run; the reason otherwise."""
    if not isinstance(cmd, list) or not cmd or not all(isinstance(x, str) for x in cmd):
        return "not a list of words"
    verb = cmd[0]
    n = {"set": 2, "add": 2, "gate": 3}.get(verb)
    if n is None or len(cmd) < 1 + n:
        return f"{verb[:20]} is not a decision the page takes"
    # the positional words first (a gate's evidence may be any text), then --by and --note only, each once, with a value
    pos, opts = cmd[1:1 + n], cmd[1 + n:]
    seen = set()
    for i in range(0, len(opts), 2):
        w = opts[i]
        if w not in ("--by", "--note") or w in seen or i + 1 >= len(opts):
            return f"option {w[:20]} is not allowed"
        seen.add(w)
    if verb == "set" and len(pos) == 2:
        if page_field(pos[0]) or any(r.match(pos[0]) for r in _SET_INDEXED):
            return None
        return f"set {pos[0][:60]} is not a decision the page takes"
    if verb == "add" and len(pos) == 2:
        return None if pos[0] in _ADD_LISTS else f"add to {pos[0][:60]} is not a decision the page takes"
    if verb == "gate" and len(pos) == 3:
        return None if pos[0] in _GATES and re.match(r"^\d{4}-\d{2}-\d{2}$", pos[1]) else "not a gate and a date"
    return f"{verb[:20]} is not a decision the page takes"


# ---------- the method's signature ----------

# The public halves of the keys allowed to publish the method. Only text here; the private halves never leave the
# change agent's machine and the server's environment. Rotate: keygen, add the new public half, ship the plugin.
PUBLIC_KEYS = {
    "47f7df90": {"n": "b67f647e2d0fb64e106b67658d4e617a53fa62cae9c03a5c1a71501e7a89b0e507e544f992850a86aa9abde194fd3c2a37e8e8f27e28c64e3106212ecb1a09c11bd55a4029d7201fb084c6d5b854e3545d7b51577f2e62a052d58962fb7c2275e877256edab18faa23a8fa4b6c22c1dad8a0e47c0717bc4dc7a3d3f006b0cda9311d756c096cede80d3d5aed551ffb92c9297a8d1226bc04023e33cef522abc4d45b68eec5d59c411de70cb9e305b451d13a60ba770ea81eec39c276a57b408e3bb72cb9faf9cc64855ff10cf35fb6df6af8b14db1f8e2530ecfcd3de63fbd35ec8115ef272c96314fb3f0003c62bf4cd34a6d95dbc140c06bdeeb0bc8f79a7256b36d01c28cf65b994885214dae2b77177fc6ff03ec8baacfe6aaea3e44f752b5fc7e849913e6c58e106227255a7a3fec8e6aeb67d96e07a7664493b67abf4fb15e09f1d343bbbb1e13d376a5322a60761a306a005524003525ec8ddf314c59f4a64c756cdb17510fdb3b1c47c1ebba3fb89a3e85aa4991b5c043dbb0d41a63",
                 "e": 65537},
}
_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")
SIGNATURE_PATH = ".claude-plugin/signature.json"


def _public_keys():
    keys = {k: (int(v["n"], 16), int(v["e"])) for k, v in PUBLIC_KEYS.items() if v.get("n")}
    extra = os.environ.get("THREEKIT_WAY_METHOD_PUBLIC_KEY", "")
    if extra:
        try:
            v = json.loads(extra)
            keys[v["kid"]] = (int(v["n"], 16), int(v["e"]))
        except (ValueError, KeyError, TypeError):
            pass
    return keys


def digest(version, files):
    """One hash over the version and every file except the signature itself."""
    body = {"version": str(version), "files": {p: hashlib.sha256(t.encode("utf-8")).hexdigest()
                                               for p, t in sorted(files.items()) if p != SIGNATURE_PATH}}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")).digest()


def _em(h, k):
    t = _DIGEST_INFO + h
    return int.from_bytes(b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t, "big")


def signing_key():
    raw = os.environ.get("THREEKIT_WAY_SIGNING_KEY", "")
    path = os.environ.get("THREEKIT_WAY_SIGNING_KEY_FILE") or os.path.join(os.path.expanduser("~"), ".config", "threekit-way", "signing-key.json")
    if not raw and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = f.read()
    if not raw:
        return None
    try:
        k = json.loads(raw)
        return {"kid": k["kid"], "n": int(k["n"], 16), "e": int(k["e"]), "d": int(k["d"], 16)}
    except (ValueError, KeyError, TypeError):
        raise RuntimeError("the signing key is not readable (THREEKIT_WAY_SIGNING_KEY or the key file)")


def sign(version, files):
    """The signature file's text for this publication. RuntimeError when this machine holds no signing key."""
    key = signing_key()
    if not key:
        raise RuntimeError("no signing key here: only the change agent and the dashboard server publish the method")
    k = (key["n"].bit_length() + 7) // 8
    sig = pow(_em(digest(version, files), k), key["d"], key["n"]).to_bytes(k, "big")
    return json.dumps({"version": str(version), "kid": key["kid"], "sig": sig.hex()})


def verify(files):
    """None when the publication carries a valid signature by a known key; the reason otherwise."""
    raw = files.get(SIGNATURE_PATH)
    if not raw:
        return "the method on the dashboard is not signed"
    try:
        s = json.loads(raw)
        n, e = _public_keys()[s["kid"]]
        sig = bytes.fromhex(s["sig"])
    except KeyError:
        return "the method on the dashboard is signed with a key this plugin does not know"
    except (ValueError, TypeError):
        return "the signature of the method on the dashboard is not readable"
    try:
        version = json.loads(files.get(".claude-plugin/plugin.json") or "{}").get("version", "")
    except ValueError:
        version = ""
    if str(s.get("version")) != str(version):
        return "the signature is for another version of the method"
    k = (n.bit_length() + 7) // 8
    if len(sig) != k:
        return "the signature of the method does not match its text"
    got = pow(int.from_bytes(sig, "big"), e, n).to_bytes(k, "big")
    if not hmac.compare_digest(got, _em(digest(version, files), k).to_bytes(k, "big")):
        return "the signature of the method does not match its text"
    return None


def _probable_prime(bits):
    import secrets
    small = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]
    while True:
        c = secrets.randbits(bits) | (1 << (bits - 1)) | (1 << (bits - 2)) | 1
        if any(c % p == 0 for p in small):
            continue
        d, r = c - 1, 0
        while d % 2 == 0:
            d //= 2
            r += 1
        for _ in range(40):
            a = secrets.randbelow(c - 3) + 2
            x = pow(a, d, c)
            if x in (1, c - 1):
                continue
            for _ in range(r - 1):
                x = pow(x, 2, c)
                if x == c - 1:
                    break
            else:
                break
        else:
            return c


def keygen(bits=3072):
    e = 65537
    while True:
        p, q = _probable_prime(bits // 2), _probable_prime(bits // 2)
        phi = (p - 1) * (q - 1)
        if p != q and phi % e:
            break
    n = p * q
    d = pow(e, -1, phi)
    kid = hashlib.sha256(str(n).encode()).hexdigest()[:8]
    return {"kid": kid, "n": format(n, "x"), "e": e, "d": format(d, "x")}


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.expanduser("~"), ".config", "threekit-way", "signing-key.json")
    if cmd == "keygen":
        if os.path.exists(path):
            sys.exit(f"{path} exists already; keep it, or move it away first")
        k = keygen()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(k, f)
        print(f"signing key written to {path} (readable by you only)")
        print(f'public half for PUBLIC_KEYS in plugin/scripts/guard.py: "{k["kid"]}": {{"n": "{k["n"]}", "e": {k["e"]}}}')
    elif cmd == "pubkey":
        with open(path, "r", encoding="utf-8") as f:
            k = json.load(f)
        print(json.dumps({"kid": k["kid"], "n": k["n"], "e": k["e"]}))
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
