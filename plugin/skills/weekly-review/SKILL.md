---
name: weekly-review
description: "Runs the weekly review of The Threekit Way .AI and drafts the customer update. In build it checks the path to the metric; in launch it prepares the pass-rate gate (testers, pass report, session recording, change notices); after launch it sends the metric itself. Called by threekit-way for Monday, weekly, status, update for CUSTOMER, where are we, go live, UAT, testers, pass report. Also the body of the weekly-reviewer agent."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill weekly-review` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
