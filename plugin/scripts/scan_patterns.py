#!/usr/bin/env python3
"""Pattern scan for the Threekit Way pull request review.

Usage: python3 scan_patterns.py <file-or-folder> [...] [--json]

Prints one line per hit: file:line · category · the matched text. Exit 0 always; the
review judges the hits. The patterns are the deterministic half of the review; see
skills/pr-review/references/patterns.md for what each category means.
"""
import sys
import os
import re
import json

CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte", ".go", ".java", ".cs", ".rb", ".php"}
DATA_EXT = {".json", ".csv", ".xlsx", ".xls", ".yaml", ".yml"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "__pycache__", "venv", ".venv", "threekit-way"}
SKIP_FILES = {"package.json", "package-lock.json", "tsconfig.json", "pyproject.toml", "project.yaml", ".eslintrc.json", "yarn.lock"}

DATA_KEYS = re.compile(r'"(sku|price|prices|options|values|rules|bom|bom_rules|attributes|products|families)"\s*:', re.I)

PATTERNS = [
    ("data outside the platform", re.compile(r"\b(const|let|var|final|static)?\s*(OPTIONS|PRICES|PRICE_LIST|FAMILIES|SKUS|SKU_LIST|PRODUCTS|RULES|CATALOG)\s*[:=]\s*[\[\{\(]", re.I)),
    ("data outside the platform", re.compile(r"CREATE TABLE\s+\w*(product|quote|lead|price|option)", re.I)),
    ("rules in code", re.compile(r"\bif\b[^\n]*\b(width|height|depth|length|finish|material|color|colour|family|variant|option|attribute)\b[^\n]*(==|===|!=|>|<|in\b)", re.I)),
    ("rules in code", re.compile(r"\b(incompatible|allowed_with|requires|excludes|not_allowed|disallow)\w*\s*[:=(]", re.I)),
    ("rules in code", re.compile(r"\.filter\([^)]*\b(valid|allowed|available|compatible)\b", re.I)),
    ("prompts in code", re.compile(r"(['\"`])\s*(You are|Respond with|Always answer|Never answer|As an assistant|System prompt)", re.I)),
    ("prompts in code", re.compile(r"\bsystem\s*[:=]\s*['\"`]", re.I)),
    ("patched model output", re.compile(r"\b(re\.(match|search|sub|findall)|RegExp|\.match\(|\.replace\()\s*[^\n]*\b(response|answer|completion|output|reply|result)\b", re.I)),
    ("patched model output", re.compile(r"\b(response|answer|completion|reply|output)\b\s*\.(replace|match|split|slice)\(", re.I)),
    ("patched model output", re.compile(r"\b(response|answer|completion|reply)\b[^\n]*\.(includes|startswith|startsWith|endswith|endsWith|contains)\(", re.I)),
    ("patched model output", re.compile(r"\bif\b[^\n]*['\"][^'\"]+['\"]\s+in\s+(response|answer|completion|reply)\b", re.I)),
    ("hardcoded edge case", re.compile(r"\bif\b[^\n]*\b(sku|customer|dealer|tenant|tenantId|tenant_id)\b[^\n]*(==|===)\s*['\"][^'\"]+['\"]", re.I)),
    ("hardcoded edge case", re.compile(r"\b(TODO:?\s*remove|temporary|hack|workaround|quick fix)\b", re.I)),
    ("screen computes validity", re.compile(r"\b(isValid|checkValid|validateLocally|computePrice|calculatePrice|getPrice|filterOptions)\b\s*[=(]", re.I)),
]


def iter_files(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
            continue
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                yield os.path.join(root, f)


def scan_file(path):
    hits = []
    base = os.path.basename(path)
    ext = os.path.splitext(base)[1].lower()
    if base in SKIP_FILES:
        return hits
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except OSError:
        return hits
    if ext in DATA_EXT:
        if ext in {".xlsx", ".xls"} or DATA_KEYS.search(text):
            hits.append((path, 1, "data outside the platform", f"data file {base}"))
        return hits
    if ext not in CODE_EXT:
        return hits
    for n, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        if s.startswith(("//", "#", "*", "/*")):
            if PATTERNS[-2][1].search(line):
                hits.append((path, n, "hardcoded edge case", s[:120]))
            continue
        for cat, rx in PATTERNS:
            m = rx.search(line)
            if m:
                hits.append((path, n, cat, s[:120]))
                break
    return hits


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_json = "--json" in sys.argv
    if not args:
        print(__doc__)
        return
    hits = []
    for f in iter_files(args):
        hits.extend(scan_file(f))
    if as_json:
        print(json.dumps([{"file": h[0], "line": h[1], "category": h[2], "text": h[3]} for h in hits], indent=2))
        return
    for h in hits:
        print(f"{h[0]}:{h[1]} · {h[2]} · {h[3]}")
    print(f"{len(hits)} hit(s) in {len(set(h[0] for h in hits))} file(s)")


if __name__ == "__main__":
    main()
