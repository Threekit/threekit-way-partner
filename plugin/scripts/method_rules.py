#!/usr/bin/env python3
"""The method as code: what each project must do this week, and which rules it passes.

Two functions, both pure, both read a project record:

  actions(record, today) -> list of actions for this week
      Each action: what to do, who does it, what to say to threekit-way to do it, how late it is.
  rules(record, today)   -> list of rule results
      Each rule: id (from the full-review checklist), pass | fail | not yet, evidence.

Used by dashboard/sync.py. The validator covers the record's shape; this covers the method.
"""
import datetime as dt

PHASES = ["sell", "kickoff", "build", "launch", "after"]


def d(value):
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def working_days(a, b):
    n, x = 0, a
    while x < b:
        x += dt.timedelta(days=1)
        if x.weekday() < 5:
            n += 1
    return n


def action(what, owner, say, late_days=0, due=None, kind="do"):
    return {"what": what, "owner": owner, "say": say, "late_days": max(0, late_days or 0),
            "due": due.isoformat() if isinstance(due, dt.date) else (due or ""), "kind": kind}


def actions(r, today):
    out = []
    phase = r.get("phase", "sell")
    cust = r.get("customer", "the customer")
    sow = r.get("sow") or {}
    m = sow.get("metric") or {}
    gates = r.get("gates") or {}
    people = r.get("people") or {}
    build = r.get("build") or {}
    lib = r.get("library") or {}
    launch = r.get("launch") or {}
    after = r.get("after") or {}

    def gate(name):
        return d((gates.get(name) or {}).get("date"))

    # Every phase: the clocks
    for p in r.get("positions") or []:
        if not p.get("answered"):
            rec = d(p.get("received"))
            late = (today - rec).days - 2 if rec else 0
            out.append(action(f"Answer {cust} on \"{p.get('ask', '')}\" ({p.get('id')})", "Project manager",
                              f"threekit-way, write the position on {p.get('id')} for {cust}", late, rec + dt.timedelta(days=2) if rec else None,
                              "late" if late > 0 else "due"))
    for q in r.get("product_requests") or []:
        if not q.get("answer"):
            sent = d(q.get("sent"))
            wd = working_days(sent, today) if sent else 0
            out.append(action(f"Chase {people.get('product_contact') or 'product'} on {q.get('id')}: {q.get('outcome', '')}", "Project manager",
                              f"threekit-way, product status on {q.get('id')} for {cust}", wd - 5, None,
                              "late" if wd > 5 else "due"))
    from custom_code import record_counts
    lc = record_counts(lib)
    if lc["unlisted_lines"] > 0 or lc["stale_lines"] > 0:
        parts = [f"{lc['unlisted_lines']} not copied" if lc["unlisted_lines"] else "", f"{lc['stale_lines']} changed since the last package" if lc["stale_lines"] else ""]
        out.append(action("Package the custom code into the library: " + ", ".join(p for p in parts if p) + " (lines)", "Developer",
                          f"threekit-way, package the custom code for {cust}", 0, None, "due"))

    if phase == "sell":
        missing = []
        if not sow.get("definition_of_done"):
            missing.append("definition of done")
        if not (m.get("name") and m.get("baseline") and m.get("target")):
            missing.append("one metric with baseline and target")
        if not sow.get("path_that_pays"):
            missing.append("the path that pays as phase 1")
        if not sow.get("change_control_priced"):
            missing.append("priced change control")
        if (sow.get("uat_window_days") or 0) < 14:
            missing.append("a two-week UAT window")
        if not sow.get("metric_shared_by_customer"):
            missing.append("the customer's agreement to share the metric")
        if missing:
            out.append(action("Close the SOW gaps: " + ", ".join(missing), "Project manager",
                              f"threekit-way, SOW draft attached for {cust}", 0, None, "do"))
        if not (r.get("tenant") or {}).get("id"):
            out.append(action("Create the Threekit AI tenant and load a sample of the customer's data before signature", "Developer",
                              f"threekit-way, set up the tenant for {cust}", 0, None, "do"))
        vb = d((r.get("value_brief") or {}).get("updated"))
        if not vb:
            out.append(action("Write the one-page value brief", "Project manager", f"threekit-way, value brief for {cust}", 0, None, "do"))
        elif (today - vb).days > 90:
            out.append(action(f"Refresh the value brief ({(today - vb).days} days old)", "Project manager", f"threekit-way, value brief for {cust}", 0, None, "due"))
        if not missing and (r.get("tenant") or {}).get("id"):
            out.append(action("Get the SOW signed; the five items and the tenant are in place", "Project manager",
                              f"threekit-way, {cust} signed on <date>", 0, None, "do"))

    if phase == "kickoff":
        signed = gate("sow_signed")
        due = signed + dt.timedelta(days=7) if signed else None
        late = (today - due).days if due else 0
        if not gate("done_signed"):
            out.append(action(f"Get the definition of done signed by {people.get('customer_sponsor') or 'the sponsor'}", "Project manager",
                              f"threekit-way, kickoff pack for {cust}", late, due, "late" if late > 0 else "due"))
        if not gate("first_screen_seen"):
            out.append(action("Show the customer the first engine-driven screen on the path that pays", "Developer",
                              f"threekit-way, first screen for {cust}", late, due, "late" if late > 0 else "due"))
        if not people.get("product_contact"):
            out.append(action("Get one named person at product for this project", "Project manager",
                              f"threekit-way, kickoff pack for {cust}", late, due, "late" if late > 0 else "due"))

    if phase == "build":
        checks = [d(c.get("date")) for c in r.get("weekly_checks") or []]
        checks = [c for c in checks if c]
        last = max(checks) if checks else None
        since = (today - last).days if last else 99
        if since > 7:
            out.append(action("Run the weekly review of the path to the metric and send the customer update", "Project manager",
                              f"threekit-way, Monday for {cust}", since - 7, (last + dt.timedelta(days=7)) if last else today, "late" if since > 7 else "due"))
        latest = sorted([c for c in r.get("weekly_checks") or [] if c.get("date")], key=lambda c: str(c["date"]))
        if latest and latest[-1].get("on_path") is False:
            out.append(action(f"Get back on the path: {latest[-1].get('note', '')}", "Project manager",
                              f"threekit-way, full review of {cust}", 0, None, "late"))
        lp = d(build.get("launch_planned"))
        if lp and (lp - today).days <= 14 and len(people.get("testers") or []) < 3:
            out.append(action(f"Name three testers at {cust}; launch is in {(lp - today).days} days", "Project manager",
                              f"threekit-way, testers for {cust}", 0, lp - dt.timedelta(days=14), "due"))
        if lp and (lp - today).days <= 14 and not launch.get("session_recording"):
            out.append(action("Turn session recording on before UAT", "Developer", f"threekit-way, launch check for {cust}", 0, lp - dt.timedelta(days=14), "due"))
        if lp and today > lp:
            out.append(action(f"Launch date passed {(today - lp).days} days ago without a signed pass report; price the change or launch", "Project manager",
                              f"threekit-way, full review of {cust}", (today - lp).days, lp, "late"))

    if phase == "launch":
        if len(people.get("testers") or []) < 3:
            out.append(action(f"Name three testers at {cust}", "Project manager", f"threekit-way, testers for {cust}", 0, None, "late"))
        if not launch.get("session_recording"):
            out.append(action("Turn session recording on", "Developer", f"threekit-way, launch check for {cust}", 0, None, "late"))
        if not launch.get("pass_report"):
            out.append(action("Run every journey and draft the pass report for the testers", "Developer", f"threekit-way, run the journeys for {cust}", 0, None, "due"))
        else:
            out.append(action("Get the pass report signed by the three testers", "Project manager", f"threekit-way, {cust} pass report signed on <date>", 0, None, "due"))

    if phase == "after":
        la = d(build.get("launch_actual")) or gate("pass_rate_signed")
        reports = [d(x.get("date")) for x in after.get("metric_reports") or []]
        reports = [x for x in reports if x]
        last = max(reports) if reports else la
        since = (today - last).days if last else 99
        window = int(m.get("window_days") or 90)
        if la and (today - la).days <= window + 7 and since > 7:
            out.append(action(f"Send {cust} this week's value of {m.get('name') or 'the metric'}", "Project manager",
                              f"threekit-way, weekly for {cust}", since - 7, last + dt.timedelta(days=7) if last else today, "late"))
        if la and not gate("learnings_written"):
            due = la + dt.timedelta(days=30)
            late = (today - due).days
            out.append(action("Write the learnings and propose the edits to the method", "Project manager",
                              f"threekit-way, learnings for {cust}", late, due, "late" if late > 0 else ("due" if late > -7 else "do")))
        if la and (today - la).days >= window:
            out.append(action(f"Day {window} reached: confirm whether the target was met and open the phase 2 conversation", "Project manager",
                              f"threekit-way, value brief for {cust}", 0, la + dt.timedelta(days=window), "due"))

    order = {"late": 0, "due": 1, "do": 2}
    out.sort(key=lambda a: (order[a["kind"]], -a["late_days"]))
    return out


def rules(r, today):
    """The computable rows of the full-review checklist. Returns [{id, rule, result, evidence}]."""
    phase = r.get("phase", "sell")
    pi = PHASES.index(phase) if phase in PHASES else 0
    sow = r.get("sow") or {}
    m = sow.get("metric") or {}
    gates = r.get("gates") or {}
    people = r.get("people") or {}
    build = r.get("build") or {}
    lib = r.get("library") or {}
    launch = r.get("launch") or {}
    after = r.get("after") or {}
    positions = r.get("positions") or []
    requests = r.get("product_requests") or []
    checks = r.get("weekly_checks") or []
    out = []

    def gate(name):
        return d((gates.get(name) or {}).get("date"))

    def row(rid, rule, phase_index, ok, evidence):
        if pi < phase_index:
            out.append({"id": rid, "rule": rule, "result": "not yet", "evidence": ""})
        else:
            out.append({"id": rid, "rule": rule, "result": "pass" if ok else "fail", "evidence": evidence})

    vb = d((r.get("value_brief") or {}).get("updated"))
    row("S1", "A one-page value brief exists and is less than 90 days old", 0, bool(vb) and (today - vb).days <= 90,
        f"updated {vb}" if vb else "no brief")
    row("S2", "Definition of done is one sentence about the user", 1, bool(sow.get("definition_of_done")), sow.get("definition_of_done") or "empty")
    row("S3", "One metric with baseline, target and window", 1, bool(m.get("name") and m.get("baseline") and m.get("target")),
        f"{m.get('name', '')}: {m.get('baseline', '?')} to {m.get('target', '?')} in {m.get('window_days', 90)} days" if m.get("name") else "no metric")
    row("S4", "Phase 1 is the path that pays", 1, bool(sow.get("path_that_pays")), sow.get("path_that_pays") or "empty")
    row("S5", "Change control is priced in the SOW", 1, sow.get("change_control_priced") is True, "priced" if sow.get("change_control_priced") else "not priced")
    row("S6", "UAT window of at least 14 days", 1, (sow.get("uat_window_days") or 0) >= 14, f"{sow.get('uat_window_days') or 0} days")
    row("S7", "Customer agreed to share the metric weekly after launch", 1, sow.get("metric_shared_by_customer") is True,
        "agreed" if sow.get("metric_shared_by_customer") else "not agreed")
    row("S8", "Tenant existed before signature", 1, bool((r.get("tenant") or {}).get("id")), (r.get("tenant") or {}).get("id") or "no tenant")
    row("S10", "The signed SOW is linked and read into the baseline every spec traces to", 1, bool(sow.get("url") or sow.get("path")) and bool(sow.get("baseline")),
        ("linked" if (sow.get("url") or sow.get("path")) else "no SOW link") + (", baseline " + str(sow.get("baseline")) if sow.get("baseline") else ", no baseline yet"))

    ss, ds, fs = gate("sow_signed"), gate("done_signed"), gate("first_screen_seen")
    row("K1", "Done signed within one week of SOW signature", 2, bool(ss and ds and (ds - ss).days <= 7),
        f"{(ds - ss).days} days after signature" if ss and ds else "not signed")
    row("K2", "First screen seen within one week, on the path that pays", 2, bool(ss and fs and (fs - ss).days <= 7),
        f"{(fs - ss).days} days after signature" if ss and fs else "not seen")
    row("K4", "One named person at product", 1, bool(people.get("product_contact")), people.get("product_contact") or "none")

    dated = sorted([d(c.get("date")) for c in checks if d(c.get("date"))])
    gaps_ok = all((b - a).days <= 7 for a, b in zip(dated, dated[1:])) if len(dated) > 1 else True
    last_ok = bool(dated) and (today - dated[-1]).days <= 7 if phase == "build" else bool(dated)
    row("B1", "Path to the metric reviewed every week, none missed", 2, bool(dated) and gaps_ok and last_ok,
        f"{len(dated)} checks, last {dated[-1]}" if dated else "no checks")
    late_pos = [p for p in positions if p.get("received") and ((d(p.get("answered")) or today) - d(p.get("received"))).days > 2]
    row("B2", "Every customer ask has a position within 48 hours", 2, not late_pos,
        f"{len(late_pos)} late of {len(positions)}" if positions else "no asks yet")
    unpriced = [p for p in positions if p.get("scope_change") and not p.get("price")]
    row("B3", "Every scope change is priced", 2, not unpriced, f"{len(unpriced)} unpriced" if unpriced else f"{sum(1 for p in positions if p.get('scope_change'))} changes, all priced")
    from custom_code import record_counts
    lc = record_counts(lib)
    row("B4", "Rules, prompts and data live in the platform, none in code", 2, lc["unlisted_lines"] == 0,
        f"{lc['unlisted_lines']} custom lines not copied to the library")
    specs = r.get("specs") or []
    live = [s for s in specs if s.get("status") in ("agreed", "planned", "in_build", "done")]
    changes = [p for p in positions if p.get("scope_change") and p.get("answered")]
    unspecced = [p for p in changes if not any(s.get("from") == p.get("id") for s in live)]
    has_path_spec = any(s.get("from") == "sow" for s in live)
    row("B13", "The path that pays and every scope change have an agreed spec", 2, has_path_spec and not unspecced,
        (f"{len(live)} agreed spec{'s' if len(live) != 1 else ''}" + (f", {len(unspecced)} scope change{'s' if len(unspecced) != 1 else ''} without one" if unspecced else "")) if specs else "no spec yet")
    bad_req = [q for q in requests if not (q.get("outcome") and q.get("cross_customer_why"))]
    row("B6", "Every product request names the outcome and the cross-customer why", 2, not bad_req,
        f"{len(requests)} requests" if requests else "no requests yet")
    slow = [q for q in requests if q.get("sent") and working_days(d(q["sent"]), d(q.get("answered")) or today) > 5]
    row("B7", "Product answered within five working days with a path", 2, not slow,
        f"{len(slow)} over five days" if slow else f"{len(requests)} answered in time" if requests else "no requests yet")
    custom = [q for q in requests if q.get("answer") == "custom"]
    row("B8", "Custom code (product said custom) has a copy in the library", 2, all(q.get("library_entry") for q in custom),
        f"{sum(1 for q in custom if q.get('library_entry'))} of {len(custom)} with a copy" if custom else "none custom")
    lp = d(build.get("launch_planned"))
    row("B12", "Launch date held, or changed through priced change control", 2, not (lp and phase in ("build", "launch") and today > lp),
        f"planned {lp}" if lp else "no date")

    row("L1", "Three named testers", 3, len(people.get("testers") or []) >= 3, f"{len(people.get('testers') or [])} named")
    row("L2", "One pass report, signed", 3, bool(launch.get("pass_report")) and bool(gate("pass_rate_signed")),
        launch.get("pass_report") or "no report")
    row("L3", "Session recording on", 3, launch.get("session_recording") is True, "on" if launch.get("session_recording") else "off")

    la = d(build.get("launch_actual")) or gate("pass_rate_signed")
    reps = sorted([d(x.get("date")) for x in after.get("metric_reports") or [] if d(x.get("date"))])
    row("A1", "The metric goes to the customer every week", 4, bool(reps) and (today - reps[-1]).days <= 7,
        f"{len(reps)} reports, last {reps[-1]}" if reps else "none sent")
    lw = gate("learnings_written")
    row("A2", "Learnings written within 30 days of launch", 4, bool(la and lw and (lw - la).days <= 30),
        f"written {lw}" if lw else (f"{(today - la).days} days since launch" if la else "no launch date"))
    lc = record_counts(lib)
    row("A4", "Custom code from the project is in the library", 4, lc["unlisted_lines"] == 0 and lc["stale_lines"] == 0,
        f"copied {lc['copied_lines']}, changed since the package {lc['stale_lines']}, not copied {lc['unlisted_lines']} lines; "
        f"{len(lc['excluded'])} files excluded by rule" + (f"; packaged at {lc['packaged_commit']}" if lc["packaged_commit"] else ""))
    return out
