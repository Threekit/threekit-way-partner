---
name: project-docs
description: "Writes and keeps current the documentation of a project, its data in Threekit AI and its code in the repository, under threekit-way/docs. Called by threekit-way for document the project, document the code, document the data, data dictionary, architecture, how does this project work, update the docs, docs are stale, and by kickoff-pack after the first screen, by pr-review when a reviewed change touches what the docs describe, and by library-keeper at handover. Also writes the one full project document for the handover to support (handover, handover to support, handoff, support handover, close the project). Reads the live tenant and the repository; never documents from memory."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill project-docs` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
