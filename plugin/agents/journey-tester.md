---
name: journey-tester
description: "Runs every user journey in threekit-way/journeys/ against the project tenant and writes last-run.md. Runs before every pull request, nightly during build and launch, and on request. Read-only on the tenant except for a test lead it creates and deletes."
model: inherit
color: yellow
---

First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py agent journey-tester` (local, no network). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
