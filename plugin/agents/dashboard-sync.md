---
name: dashboard-sync
description: "Collects every project record (threekit-way/project.yaml) from the repositories listed in dashboard/sync.yaml, validates each, builds dashboard/data.json and republishes the dashboard page. Runs on its schedule (a few times a day) and on request (refresh the dashboard, sync the dashboard)."
model: inherit
color: cyan
tools: ["Read", "Bash", "Glob"]
---

First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py agent dashboard-sync` (local, no network). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
