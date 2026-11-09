#!/usr/bin/env python3
"""Validate a Threekit Way project record (threekit-way/project.yaml).

Usage: python3 validate_record.py <path-to-project.yaml> [--json]

Exit 0 when valid, 1 when invalid. Prints one line per problem, plain words,
so a specialist can fix the record before running.

The checks are the method's rules, not a generic schema:
- the record has the fields the specialists write
- the phase matches the gates that have dates
- rules with a clock (48 hours for positions, 5 working days for product
  requests, weekly checks in build, metric reports after launch) are flagged
  when late, as warnings, so the dashboard can show red
"""
import sys
import json
import datetime as dt

try:
    import yaml
except ImportError:
    print("error: PyYAML is missing. Install with: pip install pyyaml")
    sys.exit(2)

PHASES = ["sell", "kickoff", "build", "launch", "after"]
GATES = ["sow_signed", "done_signed", "first_screen_seen", "pass_rate_signed", "learnings_written"]
# The gate that must have a date for the record to be in a given phase.
PHASE_REQUIRES_GATE = {
    "kickoff": "sow_signed",
    "build": "done_signed",
    "launch": "done_signed",
    "after": "pass_rate_signed",
}


def parse_date(value):
    if not value:
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError:
        return None


def working_days_between(a, b):
    days = 0
    d = a
    while d < b:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            days += 1
    return days


def validate(record, today=None):
    today = today or dt.date.today()
    errors, warnings = [], []

    def need(path, cond, msg):
        if not cond:
            errors.append(f"{path}: {msg}")

    need("record_version", record.get("record_version") == 1, "must be 1")
    need("customer", bool(record.get("customer")), "customer name is empty")
    phase = record.get("phase")
    need("phase", phase in PHASES, f"must be one of {', '.join(PHASES)}")

    for key in ["tenant", "people", "sow", "gates", "build", "library", "launch", "after"]:
        need(key, isinstance(record.get(key), dict), "section is missing")
    for key in ["weekly_checks", "positions", "product_requests", "log"]:
        need(key, isinstance(record.get(key), list), "must be a list")
    if record.get("notes") is not None:
        need("notes", isinstance(record.get("notes"), list), "must be a list")
    if record.get("specs") is not None:
        need("specs", isinstance(record.get("specs"), list), "must be a list")
        for i, s in enumerate(record.get("specs") or []):
            need(f"specs.{i}.status", (s or {}).get("status") in ("draft", "agreed", "planned", "in_build", "done"),
                 "must be draft, agreed, planned, in_build or done")

    if errors:
        return errors, warnings

    gates = record["gates"]
    for g in GATES:
        need(f"gates.{g}", isinstance(gates.get(g), dict), "gate is missing")
        if isinstance(gates.get(g), dict) and gates[g].get("date"):
            need(f"gates.{g}.date", parse_date(gates[g]["date"]) is not None, "not a date (YYYY-MM-DD)")
            need(f"gates.{g}.evidence", bool(gates[g].get("evidence")), "a gate with a date needs evidence")

    # Phase must be backed by its gate, and a dated later gate means the phase is stale.
    req = PHASE_REQUIRES_GATE.get(phase)
    if req and not gates.get(req, {}).get("date"):
        errors.append(f"phase: is '{phase}' but gates.{req}.date is empty")
    if phase == "sell" and gates.get("sow_signed", {}).get("date"):
        errors.append("phase: is 'sell' but the SOW is signed; move to kickoff")
    if phase in ("sell", "kickoff") and gates.get("done_signed", {}).get("date"):
        errors.append(f"phase: is '{phase}' but done is signed; move to build")
    if phase in ("sell", "kickoff", "build", "launch") and gates.get("pass_rate_signed", {}).get("date"):
        errors.append(f"phase: is '{phase}' but the pass rate is signed; move to after")

    # Two hard stops, the contract matters: no build without a definition of done, no pass rate signed without
    # three named testers. Everything else a phase expects is "to finish": a warning, shown in red with an owner
    # (method_rules.py), never a reason to refuse recording what happened.
    def finish(path, cond, msg):
        if not cond:
            warnings.append(f"to finish: {path}: {msg}")

    sow = record["sow"]
    if phase in ("build", "launch", "after"):
        need("sow.definition_of_done", bool(sow.get("definition_of_done")), "a signed definition of done is required before build")
    if gates.get("pass_rate_signed", {}).get("date"):
        need("people.testers", len(record["people"].get("testers") or []) >= 3, "the pass rate is signed by three named testers")
    if phase != "sell":
        finish("sow.definition_of_done", bool(sow.get("definition_of_done")), "agreed at kickoff")
        metric = sow.get("metric") or {}
        finish("sow.metric.name", bool(metric.get("name")), "the one metric")
        finish("sow.metric.target", bool(metric.get("target")), "the metric target")
        finish("sow.path_that_pays", bool(sow.get("path_that_pays")), "phase 1 in one sentence")
        finish("sow.change_control_priced", sow.get("change_control_priced") is True, "change control priced in the SOW")
        finish("sow.uat_window_days", (sow.get("uat_window_days") or 0) >= 14, "a UAT window of at least 14 days")
        finish("tenant.id", bool(record["tenant"].get("id")), "the Threekit AI tenant")
        finish("people.product_contact", bool(record["people"].get("product_contact")), "one named person at product")
    if phase in ("launch", "after"):
        finish("people.testers", len(record["people"].get("testers") or []) >= 3, "three named testers")
        finish("launch.session_recording", record["launch"].get("session_recording") is True, "session recording on")

    # Clocks. Warnings, so the dashboard shows red without blocking the specialist.
    for p in record["positions"]:
        if p.get("answered"):
            continue
        received = parse_date(p.get("received"))
        if received and (today - received).days > 2:
            warnings.append(f"position {p.get('id')}: open for {(today - received).days} days, the rule is 48 hours")
    for r in record["product_requests"]:
        if r.get("answer"):
            continue
        sent = parse_date(r.get("sent"))
        if sent and working_days_between(sent, today) > 5:
            warnings.append(f"request {r.get('id')}: waiting on product for {working_days_between(sent, today)} working days, the rule is five")
    if phase == "build":
        checks = [parse_date(c.get("date")) for c in record["weekly_checks"]]
        checks = [c for c in checks if c]
        last = max(checks) if checks else None
        if last is None:
            warnings.append("weekly_checks: no path-to-metric check recorded yet")
        elif (today - last).days > 7:
            warnings.append(f"weekly_checks: last check was {(today - last).days} days ago, the rule is weekly")
    if phase == "after":
        reports = [parse_date(r.get("date")) for r in record["after"].get("metric_reports") or []]
        reports = [r for r in reports if r]
        last = max(reports) if reports else None
        if last is None:
            warnings.append("after.metric_reports: no metric report sent yet")
        elif (today - last).days > 7:
            warnings.append(f"after.metric_reports: last report was {(today - last).days} days ago, the rule is weekly")
        launched = parse_date(record["build"].get("launch_actual"))
        if launched and not gates["learnings_written"].get("date") and (today - launched).days > 30:
            warnings.append(f"learnings: {(today - launched).days} days since launch, the rule is 30")
    from custom_code import record_counts, REASONS
    lc = record_counts(record["library"])
    if lc["unlisted_lines"] > 0:
        warnings.append(f"library: {lc['unlisted_lines']} custom lines are not copied to the library (custom_code.py lists them; package them)")
    if lc["stale_lines"] > 0:
        warnings.append(f"library: {lc['stale_lines']} custom lines changed since the last package"
                        + (f" at {lc['packaged_commit']}" if lc["packaged_commit"] else "") + " (package again)")
    for i, e in enumerate(lc["excluded"]):
        if not e.get("path") or e.get("reason") not in REASONS:
            errors.append(f"library.excluded.{i}: needs a path and a reason ({', '.join(REASONS)})")
        elif e.get("reason") == "exception" and not (e.get("by") and e.get("note")):
            errors.append(f"library.excluded.{i}: an exception names who decided (by) and why (note)")

    return errors, warnings


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    path = sys.argv[1]
    as_json = "--json" in sys.argv
    try:
        with open(path, "r", encoding="utf-8") as f:
            record = yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001
        print(f"error: cannot read {path}: {e}")
        sys.exit(1)
    errors, warnings = validate(record)
    if as_json:
        print(json.dumps({"valid": not errors, "errors": errors, "warnings": warnings}, indent=2))
    else:
        for e in errors:
            print(f"error: {e}")
        for w in warnings:
            print(f"warning: {w}")
        if not errors:
            print(f"ok: {record.get('customer')} is a valid record in phase {record.get('phase')}"
                  + (f" with {len(warnings)} warning(s)" if warnings else ""))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
