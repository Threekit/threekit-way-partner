---
name: llm-advisor
description: "Recommends the most appropriate LLM and its exact version for a project's requirements, records the choice in the project record, and keeps the model catalog current so retiring models are flagged on the dashboard. Called by threekit-way for which model, which LLM, recommend a model, choose an LLM, model for CUSTOMER, is our model being retired, model deprecation, LLM obsolescence, and by kickoff-pack when the project uses AI, by weekly-review when the dashboard flags a model, and on request after launch when a completed project is affected."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill llm-advisor` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
