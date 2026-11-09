---
name: platform-refresh
description: "Keeps the plugin current as Threekit AI (GoTo) evolves. Compares the live platform (capabilities, API spec) with the written reference and every verified-against line in the plugin and the library, writes the diff and the proposed updates, and hands them to the change agent for approval. Called by threekit-way for GoTo changed, refresh the platform reference, is this still right, new GoTo version, and by the platform-refresh agent on its schedule. Never applies a change without approval."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill platform-refresh` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
