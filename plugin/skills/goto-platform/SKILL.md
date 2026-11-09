---
name: goto-platform
description: "The only place in the plugin that holds facts about Threekit AI (GoTo Commerce). Load it before anything that reads or writes a tenant, products, catalog, configurators, attributes, rules, BOM, prompts, leads, quotes, metaobjects, metafields. Its first step is discovery against the live tenant through the GoTo connector; the written reference in references/ is a map and a fallback, never the source; references/product-on-paper.md (product's Product on Paper) is the line between platform and custom. Triggers, GoTo, Threekit AI, tenant, app.threekit.ai, configurator, rules, prompts, catalog, the platform, and every specialist that touches the platform."
---

> First: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/plugin_source.py skill goto-platform` (local, no network; the day's pull happened at session start). If it prints instructions, follow those instead of this file; if it prints "installed version is current", continue here.

This is the partner build of The Threekit Way .AI: the text of this skill comes from the dashboard once this computer is connected.
