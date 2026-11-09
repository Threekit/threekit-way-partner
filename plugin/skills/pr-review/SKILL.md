---
name: pr-review
description: "Reviews a pull request against The Threekit Way .AI build rules and returns pass or fail with the list of every custom line for the handover. Called by threekit-way for review this PR, review the diff, can I merge, check my changes, and by the pr-reviewer agent on every pull request. Fails on data, rules or prompts outside the platform, patched model output, hardcoded edge cases, the app calling the consulting library and journeys not run."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill pr-review` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
