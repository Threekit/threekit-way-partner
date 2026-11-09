---
name: journey-test
description: "Runs every user journey in threekit-way/journeys/ against the project tenant through the GoTo connector and writes the result to last-run.md and, at launch, the pass report draft. Called by threekit-way for run the journeys, run the tests, the journey fails, before I open the PR, UAT run, pass report, and by the journey-tester agent before every pull request and nightly in build and launch. Read-only on the tenant unless a journey creates a quote, and then only on a test lead."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill journey-test` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
