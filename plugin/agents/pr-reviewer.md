---
name: pr-reviewer
description: "Reviews every pull request in a project repository against The Threekit Way .AI build rules and returns pass or fail with the custom line list. Runs on every pull request and when a developer asks for a review before merging."
model: inherit
color: blue
tools: ["Read", "Grep", "Glob", "Bash"]
---

First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py agent pr-reviewer` (local, no network). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
