#!/usr/bin/env python3
"""SessionStart hook. In a repository that follows The Threekit Way .AI (it has threekit-way/project.yaml),
print the contract and the project's status so every coding agent starts with the rules and the record,
without anyone typing threekit-way. Outside such a repository, print nothing."""
import os
import sys
import json
import subprocess

ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def find_record(start):
    d = os.path.abspath(start)
    for _ in range(8):
        rec = os.path.join(d, "threekit-way", "project.yaml")
        if os.path.exists(rec):
            return rec
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    return None


def partner_start():
    """The partner build only (it carries .claude-plugin/partner.json): connect this computer once, then pull the
    method from the dashboard once a day, in the background. The team's plugin skips this entirely."""
    if not os.path.exists(os.path.join(ROOT, ".claude-plugin", "partner.json")):
        return
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    try:
        import partner_link
        if not partner_link.token():
            print("The Threekit Way .AI (partner): this computer is not connected yet, so the skills have no method. "
                  "Before anything else, tell the person in one line: " + partner_link.connect_line() + ". When they paste the "
                  "key, run `python3 " + os.path.join(ROOT, "scripts", "partner_link.py") + " key <the key>`.")
            return
        subprocess.Popen([sys.executable, os.path.join(ROOT, "scripts", "plugin_source.py"), "fetch", "--daily", "--quiet"],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except Exception:  # noqa: BLE001
        pass


def main():
    partner_start()
    rec = find_record(os.getcwd())
    if not rec:
        return
    status = ""
    try:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "record.py"), rec, "status"], capture_output=True, text=True, timeout=10)
        status = (r.stdout or r.stderr).strip()
    except Exception:  # noqa: BLE001
        status = "(record could not be read; run the plugin's scripts/validate_record.py)"
    print("This repository follows The Threekit Way .AI. The threekit-way plugin is active; no need to name it.")
    print("Project record: " + rec)
    print("Status: " + status)
    print("Rules for every coding agent here (full text in CLAUDE.md at the repository root):")
    print("- Before writing code, load the goto-platform skill and run its discovery against the project tenant; read what the platform already holds.")
    print("- Product data, rules and prompts live in Threekit AI, never in JSON, tables, constants or code. When the platform cannot hold something, run platform-gap; never build the workaround.")
    print("- Fix where it lives: a wrong answer is a wrong rule, prompt or product data. Never patch model output in code, never hardcode an edge case.")
    print("- Search the shared library (library-keeper) before any custom code. Run the journeys (journey-test) before a pull request. Every pull request is reviewed by pr-review and approved by a developer.")
    print("- No feature starts without an agreed spec in threekit-way/specs/ (spec-kit). Work its tasks.md top down, tick each task as it lands, name the spec in the pull request. A change outside the spec is a position for the project manager, not a commit.")
    print("- Use the specialists through the threekit-way entry point for positions, gaps, product requests, weekly review, learnings.")
    specs = os.path.join(os.path.dirname(rec), "specs")
    if os.path.isdir(specs):
        open_specs = sorted(d for d in os.listdir(specs) if os.path.isdir(os.path.join(specs, d)))
        if open_specs:
            print("Specs in this repository: " + ", ".join(open_specs) + ". Read the one you work on, spec.md then plan.md then tasks.md.")
    else:
        print("No threekit-way/specs/ folder yet: run spec-kit (constitution, then specify) before building.")


if __name__ == "__main__":
    main()
