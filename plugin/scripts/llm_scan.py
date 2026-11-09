#!/usr/bin/env python3
"""Find the LLMs a project uses, from its code and its environment variables. Read only.

    python3 llm_scan.py <repository folder>          JSON: models, providers, env vars

What it reads:
  code and config   the providers' SDKs (import or package), their API addresses, and model ids written in the code
  env variables     the names a project reads (process.env.X, os.environ["X"], getenv) and, in .env files, Porter,
                    Docker and CI files, the value of a variable whose name says it holds a model (OPENAI_MODEL,
                    LLM_MODEL, CLAUDE_MODEL...). The value of any other variable (a key, a token, a password) is
                    never read or printed: only that the variable exists, which says which provider is set up.
A model in a value that looks like a reference (${X}) is reported as the variable. Skipped: node_modules, .git,
vendored and build folders, tests and evals, files git does not track, lock files, the plugin's own catalog and anything over 1 MB."""
import os
import re
import sys
import json

SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", ".venv", "venv", "__pycache__", ".cache", "vendor", "coverage", "threekit-way"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "models.yaml"}
CODE_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py", ".rb", ".go", ".java", ".kt", ".cs", ".php", ".json", ".yaml", ".yml", ".toml", ".html", ".vue", ".svelte"}
ENV_FILE = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|[\w.-]*\.env|porter\.ya?ml|docker-compose[\w.-]*\.ya?ml|Dockerfile|app\.ya?ml|\.github/workflows/[\w.-]+\.ya?ml)$")

PROVIDERS = {
    "Anthropic": {"sdk": [r"""from\s+anthropic\b|import\s+anthropic\b|['"]@anthropic-ai/sdk['"]|"anthropic"\s*:"""], "api": [r"api\.anthropic\.com"], "env": ["ANTHROPIC_API_KEY", "CLAUDE_API_KEY"]},
    "OpenAI": {"sdk": [r"""from\s+openai\b|import\s+openai\b|['"]openai['"]\s*[:)]|require\(['"]openai['"]\)"""], "api": [r"api\.openai\.com"], "env": ["OPENAI_API_KEY"]},
    "Google": {"sdk": [r"google\.generativeai|google\.genai|['\"]@google/genai['\"]|['\"]@google/generative-ai['\"]"], "api": [r"generativelanguage\.googleapis\.com"], "env": ["GEMINI_API_KEY", "GOOGLE_API_KEY"]},
    "Groq": {"sdk": [r"""from\s+groq\b|import\s+groq\b|['"]groq-sdk['"]"""], "api": [r"api\.groq\.com"], "env": ["GROQ_API_KEY"]},
    "xAI": {"sdk": [r"""['"]@ai-sdk/xai['"]|from\s+xai_sdk\b"""], "api": [r"api\.x\.ai"], "env": ["XAI_API_KEY", "GROK_API_KEY"]},
}
MODEL_ID = re.compile(r"""['"`=:\s](claude-[a-z0-9][a-z0-9.-]*[a-z0-9]|gpt-[0-9][a-z0-9.-]*[a-z0-9]|o[1-9](?:-[a-z0-9-]+)?|gemini-[0-9][a-z0-9.-]*[a-z0-9]|grok-[0-9][a-z0-9.-]*[a-z0-9]|llama-[0-9][a-z0-9.-]*[a-z0-9]|(?:meta-llama|openai|moonshotai|qwen|deepseek-ai|groq)/[a-z0-9][a-z0-9.-]*[a-z0-9])(?=['"`\s,;)\]}]|$)""", re.I)
PROVIDER_OF = [("claude-", "Anthropic"), ("gpt-", "OpenAI"), ("o1", "OpenAI"), ("o3", "OpenAI"), ("o4", "OpenAI"), ("gemini-", "Google"), ("grok-", "xAI"),
               ("llama-", "Groq"), ("meta-llama/", "Groq"), ("openai/", "Groq"), ("moonshotai/", "Groq"), ("qwen", "Groq"), ("deepseek", "Groq"), ("groq/", "Groq")]
ENV_READ = re.compile(r"""process\.env\.([A-Z][A-Z0-9_]+)|process\.env\[['"]([A-Z][A-Z0-9_]+)['"]\]|os\.environ(?:\.get)?\(?\[?['"]([A-Z][A-Z0-9_]+)['"]|getenv\(['"]([A-Z][A-Z0-9_]+)['"]|import\.meta\.env\.([A-Z][A-Z0-9_]+)""")
ENV_LINE = re.compile(r"""^\s*(?:export\s+|-\s+)?["']?([A-Z][A-Z0-9_]+)["']?\s*[:=]\s*["']?([^"'\s#]*)""")
MODEL_VAR = re.compile(r"MODEL|DEPLOYMENT|ENGINE")


def provider_of(mid):
    m = mid.lower()
    return next((p for k, p in PROVIDER_OF if m.startswith(k)), "")


def tracked(root):
    """The files git tracks, when the folder is a git checkout: generated and ignored files are not the project's."""
    import subprocess
    try:
        r = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return set(r.stdout.split("\0")) - {""} if r.returncode == 0 else None


def files(root):
    only = tracked(root)
    for dp, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".") or d == ".github"]
        for n in names:
            path = os.path.join(dp, n)
            rel = os.path.relpath(path, root).replace(os.sep, "/")
            parts = rel.split("/")
            if any(x in ("tests", "test", "__tests__", "fixtures", "evals", "spec") for x in parts[:-1]) or re.search(r"(^test_|[._]test\.|[._]spec\.)", n):
                continue  # tests mention models without using them
            if n in SKIP_FILES or (only is not None and rel not in only) or os.path.getsize(path) > 1_000_000:
                continue
            ext = os.path.splitext(n)[1].lower()
            if ext in CODE_EXT or ENV_FILE.search(rel):
                yield path, rel


def scan(root):
    models, providers, env_names, env_models = {}, {}, set(), {}
    for path, rel in files(root):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.read().splitlines()
        except OSError:
            continue
        is_env = bool(ENV_FILE.search(rel))
        for i, line in enumerate(lines, 1):
            where = f"{rel}:{i}"
            if is_env:
                m = ENV_LINE.match(line)
                if m:
                    name, value = m.group(1), m.group(2)
                    env_names.add(name)
                    looks = bool(MODEL_ID.search(" " + value + " ")) or bool(provider_of(value))
                    if MODEL_VAR.search(name) and value and not value.startswith("$") and (looks or name.endswith("MODEL")):
                        env_models.setdefault(name, {"value": value, "where": where})
                        models.setdefault(value.lower(), {"model": value.lower(), "provider": provider_of(value), "where": [], "how": "env"})["where"].append(where)
                    continue  # never look further into an env line: its value may be a secret
            for g in ENV_READ.findall(line):
                env_names.add(next(x for x in g if x))
            for p, rule in PROVIDERS.items():
                if any(re.search(r, line) for r in rule["sdk"]):
                    providers.setdefault(p, set()).add("sdk " + where)
                if any(re.search(r, line) for r in rule["api"]):
                    providers.setdefault(p, set()).add("api " + where)
            for mid in MODEL_ID.findall(" " + line):
                mid = mid.lower()
                if re.fullmatch(r"o[1-9]", mid) and not re.search(r"model", line, re.I):
                    continue  # a bare o1 / o3 is only a model when the line says model
                models.setdefault(mid, {"model": mid, "provider": provider_of(mid), "where": [], "how": "code"})["where"].append(where)
    for p, rule in PROVIDERS.items():
        for name in rule["env"]:
            if name in env_names:
                providers.setdefault(p, set()).add("env " + name)
    for m in models.values():
        m["where"] = m["where"][:5]
        if m["provider"]:
            providers.setdefault(m["provider"], set()).add("model " + m["model"])
    return {"models": sorted(models.values(), key=lambda m: m["model"]),
            "providers": {p: sorted(v)[:8] for p, v in sorted(providers.items())},
            "env": {"names": sorted(n for n in env_names if any(k in n for k in ("MODEL", "API_KEY", "OPENAI", "ANTHROPIC", "CLAUDE", "GEMINI", "GROQ", "XAI", "GROK", "LLM"))),
                    "models": env_models}}


if __name__ == "__main__":
    if len(sys.argv) < 2 or not os.path.isdir(sys.argv[1]):
        print(__doc__)
        sys.exit(1)
    print(json.dumps(scan(sys.argv[1]), indent=2))
