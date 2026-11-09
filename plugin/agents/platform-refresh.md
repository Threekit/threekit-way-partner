---
name: platform-refresh
description: "Keeps the plugin and the library current as Threekit AI (GoTo) evolves. Runs on its schedule (weekly by default) and on request (GoTo changed, refresh the reference). Diffs the live platform against the written reference and every verified-against line, writes the proposal, and waits for the change agents approval. Never applies a change on its own."
model: inherit
color: magenta
---

First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py agent platform-refresh` (local, no network). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
