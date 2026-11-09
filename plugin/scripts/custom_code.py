#!/usr/bin/env python3
"""Custom code: the one definition and the one count, used by pr-review, library-keeper, project-docs, the record
validator and the dashboard. Nobody counts by hand. Read only.

    python3 custom_code.py <repo> [--library <library checkout> --folder <project folder>] [--record <project.yaml>] [--json]

Custom code (counted): every file git tracks in the repository that is code the project wrote, by extension:
  .js .mjs .cjs .ts .tsx .jsx .py .rb .go .java .kt .cs .php .swift .html .htm .css .scss .sass .less .vue .svelte
  .sh .bash .sql; tests, pages and servers included.
Never counted, never listed: the threekit-way/ folder, docs (.md .txt .rst), package manifests and lock files
  (package.json, requirements.txt, pyproject.toml...), configuration (*.config.*, config.json, tsconfig, .yaml/.yml,
  .toml, .ini), hosting configuration (Dockerfile, porter.yaml, CI workflows, .dockerignore, .gitignore), environment
  files (.env, .env.*), generated and vendored folders (node_modules, dist, build, vendor, .next, coverage), images,
  fonts and other binaries, the editors' and agents' files (.cursor/, .claude/, CLAUDE.md, AGENTS.md).
Excluded by rule (listed, with the reason, never copied, never counted as missing):
  data     a data file: .json or .csv or .tsv or .ndjson that is not configuration or a manifest
  secret   a code file that holds a credential (a key, a token, a private key)
  prompt   a prompt file: under a prompts/ folder, or *.prompt, *.prompt.txt
  exception a file the project decided to keep out, recorded under library.excluded in the record, with the reason
           and the person who decided
Library state of each custom file, against <library>/<folder>/<same path>:
  copied     a byte-for-byte copy is stored
  stale      a copy is stored but differs: the file changed after the last package
  not copied no copy is stored
"""
import os
import re
import sys
import json
import subprocess

CODE_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".rb", ".go", ".java", ".kt", ".cs", ".php", ".swift",
            ".html", ".htm", ".css", ".scss", ".sass", ".less", ".vue", ".svelte", ".sh", ".bash", ".sql"}
DATA_EXT = {".json", ".csv", ".tsv", ".ndjson", ".jsonl"}
SKIP_DIRS = {"threekit-way", "node_modules", "dist", "build", "vendor", ".next", "coverage", ".cursor", ".claude", ".github", "__pycache__", ".venv", "venv"}
CONFIG_JSON = re.compile(r"(^|/)(package(-lock)?\.json|tsconfig[\w.-]*\.json|jsconfig\.json|composer\.json|[\w.-]*config(\.[\w-]+)?\.json|\.?[\w.-]*rc\.json|manifest\.json|vercel\.json|netlify\.json|app\.json)$", re.I)
SECRET = re.compile(r"""(-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|gsk_[A-Za-z0-9]{20,}|xai-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{30,}|xox[bap]-[A-Za-z0-9-]{20,})\b|(api[_-]?key|secret|token|password)\s*[:=]\s*['"][A-Za-z0-9_\-/+=]{24,}['"])""", re.I)
REASONS = ("data", "secret", "prompt", "exception")


def tracked(repo):
    """The files git tracks. Without git (or outside a checkout), every file under the folder except the folders
    that are never the project's (.git, node_modules and the others never counted)."""
    try:
        r = subprocess.run(["git", "-C", repo, "ls-files", "-z"], capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            return sorted(p for p in r.stdout.split("\0") if p)
    except (OSError, subprocess.SubprocessError):
        pass
    out = []
    for dp, dirs, names in os.walk(repo):
        dirs[:] = [d for d in dirs if d != ".git" and d not in SKIP_DIRS]
        out += [os.path.relpath(os.path.join(dp, n), repo).replace(os.sep, "/") for n in names]
    return sorted(out)


def lines_of(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return 0, b""
    return (data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)), data


def exceptions_of(record_path):
    """library.excluded entries with reason exception (or any reason a person recorded), by path."""
    if not record_path or not os.path.exists(record_path):
        return {}
    try:
        import yaml
        with open(record_path, "r", encoding="utf-8") as f:
            rec = yaml.safe_load(f) or {}
    except Exception:  # noqa: BLE001
        return {}
    out = {}
    for e in ((rec.get("library") or {}).get("excluded") or []):
        if isinstance(e, dict) and e.get("path"):
            out[str(e["path"]).strip("/")] = e
    return out


def classify(rel, data):
    """custom | (excluded, reason) | None (never counted)."""
    parts = rel.split("/")
    name = parts[-1]
    if any(p in SKIP_DIRS for p in parts[:-1]) or name in ("CLAUDE.md", "AGENTS.md"):
        return None
    ext = os.path.splitext(name)[1].lower()
    if name.startswith(".env") or name == "Dockerfile" or name.startswith("."):
        return None
    if "prompts" in parts[:-1] or name.endswith((".prompt", ".prompt.txt", ".prompt.md")):
        return ("excluded", "prompt")
    if ext in DATA_EXT:
        return None if CONFIG_JSON.search(rel) else ("excluded", "data")
    if ext not in CODE_EXT:
        return None
    if SECRET.search(data.decode("utf-8", "ignore")):
        return ("excluded", "secret")
    return "custom"


def count(repo, library=None, folder=None, record=None):
    record = record or os.path.join(repo, "threekit-way", "project.yaml")
    exc = exceptions_of(record)
    files, excluded = [], []
    for rel in tracked(repo):
        n, data = lines_of(os.path.join(repo, rel))
        kind = classify(rel, data)
        if kind is None:
            continue
        if rel in exc and kind == "custom":
            e = exc[rel]
            excluded.append({"path": rel, "lines": n, "reason": e.get("reason") or "exception", "by": e.get("by", ""), "note": e.get("note", "")})
            continue
        if kind != "custom":
            e = exc.get(rel) or {}
            excluded.append({"path": rel, "lines": n, "reason": kind[1], "by": e.get("by", "rule"), "note": e.get("note", "")})
            continue
        state = "not copied"
        if library and folder:
            lib = os.path.join(library, folder, rel)
            if os.path.isfile(lib):
                with open(lib, "rb") as f:
                    state = "copied" if f.read() == data else "stale"
        files.append({"path": rel, "lines": n, "state": state})
    t = lambda st: sum(f["lines"] for f in files if f["state"] == st)  # noqa: E731
    try:
        head = subprocess.run(["git", "-C", repo, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        head = ""
    return {"repo": os.path.abspath(repo), "commit": head, "library": bool(library and folder), "folder": folder or "",
            "files": files, "excluded": excluded,
            "totals": {"custom_lines": sum(f["lines"] for f in files), "copied_lines": t("copied"), "stale_lines": t("stale"),
                       "unlisted_lines": t("not copied"), "excluded_lines": sum(e["lines"] for e in excluded),
                       "custom_files": len(files), "copied_files": sum(1 for f in files if f["state"] == "copied"),
                       "stale_files": sum(1 for f in files if f["state"] == "stale"),
                       "unlisted_files": sum(1 for f in files if f["state"] == "not copied"), "excluded_files": len(excluded)}}


def record_counts(lib):
    """The numbers a record holds under library:, the new fields first, custom_lines_unlisted (the old name of
    unlisted_lines) when a record has only that."""
    lib = lib or {}
    unl = lib.get("unlisted_lines")
    if unl is None:
        unl = lib.get("custom_lines_unlisted") or 0
    return {"custom_lines": lib.get("custom_lines") or 0, "copied_lines": lib.get("copied_lines") or 0,
            "stale_lines": lib.get("stale_lines") or 0, "unlisted_lines": unl or 0,
            "excluded": [e for e in lib.get("excluded") or [] if isinstance(e, dict)],
            "packaged_commit": lib.get("packaged_commit") or "", "packaged_on": lib.get("packaged_on") or ""}


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print(__doc__)
        return 1
    opt = lambda k: args[args.index(k) + 1] if k in args and args.index(k) + 1 < len(args) else None  # noqa: E731
    res = count(args[0], opt("--library"), opt("--folder"), opt("--record"))
    if "--json" in args:
        print(json.dumps(res, indent=2))
        return 0
    t = res["totals"]
    print(f"Custom code in {res['repo']} at {res['commit']}" + (f", against the library folder {res['folder']}" if res["library"] else ", no library given") + ":")
    for f in res["files"]:
        print(f"  {f['state']:<11} {f['lines']:>6}  {f['path']}")
    for e in res["excluded"]:
        print(f"  excluded    {e['lines']:>6}  {e['path']}  ({e['reason']}{', ' + e['by'] if e['by'] and e['by'] != 'rule' else ''}{': ' + e['note'] if e['note'] else ''})")
    print(f"Totals: custom {t['custom_lines']} lines in {t['custom_files']} files; copied {t['copied_lines']}, stale {t['stale_lines']}, "
          f"not copied {t['unlisted_lines']}; excluded {t['excluded_lines']} lines in {t['excluded_files']} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
