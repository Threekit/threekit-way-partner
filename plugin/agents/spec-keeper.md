---
name: spec-keeper
description: "Keeps every feature of a project behind an agreed spec. Drafts the spec, plan and tasks under threekit-way/specs from the path that pays, an approved scope change or a custom answer from product, and checks every pull request against its spec for drift. Runs when a spec is asked for, when a position with a scope change is approved, when product answers custom, and on every pull request after the pr-reviewer."
model: inherit
color: purple
tools: ["Read", "Grep", "Glob", "Bash"]
---

First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py agent spec-keeper` (local, no network). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
