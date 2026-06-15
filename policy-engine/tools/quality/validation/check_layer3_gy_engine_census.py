#!/usr/bin/env python3
"""GY-0 Engine Reality Census completeness check.

Validates `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json` against
the GY-0 census discipline. The check FAILS (exit 1) on any of:

  * a row left at `execution_status: unknown` (or empty / not in the vocabulary);
  * a row whose `recommended_gy_action` (verb) contradicts its `gap_class`
    (verb/gap mismatch -- the downstream task may not use a verb the class forbids);
  * a row that reaches an authority slot without a producer-root chain
    (`authority_status: governed` while the gap_class says it is not wired/works,
    or with no evidence_refs) -- the smart-component / laundering firewall;
  * a row missing any required census field;
  * an execution/evidence-bearing row (`runs_*` / `fails` / connector replay) whose
    `output_hash` is absent or is not a `sha256:<64 hex>` digest;
  * a `blocked_upstream` row without a named structured blocker;
  * a stale top-level row_count or census_digest.

Usage:
    python3 tools/quality/validation/check_layer3_gy_engine_census.py [--census PATH] [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

DEFAULT_CENSUS = (
    Path(__file__).resolve().parents[3]
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_engine_census.json"
)

REQUIRED_FIELDS = (
    "asset_id",
    "module_path",
    "entrypoint",
    "existence_status",
    "reachability",
    "execution_status",
    "execution_evidence",
    "consumes",
    "emits",
    "output_destination",
    "authority_status",
    "gap_class",
    "canonical_vs_duplicate",
    "recommended_gy_action",
    "evidence_refs",
)

# execution_status must be one of these; `unknown` is deliberately absent.
ALLOWED_EXECUTION_STATUS = {
    "runs_e2e_on_real",
    "runs_with_deadline_adapter",
    "runs_degraded_dependency",
    "fails",
    "never_invoked",
    "not_exercised_network",
}
# statuses that REQUIRE a recorded output_hash (a real run happened)
EXECUTION_BEARING = {"runs_e2e_on_real", "runs_with_deadline_adapter", "runs_degraded_dependency", "fails"}
# statuses that did not run the outward call but still need a replay/probe hash.
EVIDENCE_HASH_REQUIRED = EXECUTION_BEARING | {"not_exercised_network"}
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

ALLOWED_AUTHORITY = {"governed", "laundered", "candidate_only", "none"}

# gap_class -> allowed recommended_gy_action verbs (the consistency contract)
VERB_GAP = {
    "wired_and_works": {"govern", "none"},
    "wired_but_ungoverned": {"govern", "repair"},
    "wired_but_rotten": {"repair"},
    "built_not_wired": {"wire"},
    "contract_without_producer": {"build"},
    "producer_without_consumer": {"wire"},
    "partial": {"extend", "wire", "repair", "demote", "none"},
    "missing": {"build"},
    # documented census-operational extension (see artifact.gap_taxonomy_extensions)
    "blocked_upstream": {"none", "wire"},
    "blocked_input": {"none", "wire"},
    "out_of_route": {"none"},
}

# authority_status: governed is only honest for assets that actually run and reach a
# consumer (wired_and_works) or work for a bounded scope (partial). Anything else
# claiming `governed` is a producer-root violation.
GOVERNED_OK_GAP = {"wired_and_works", "partial"}


def _canonical_rows_digest(rows: list[dict]) -> str:
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _valid_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def _row_text(value: object) -> str:
    return str(value or "").lower()


def validate(census: dict) -> list[dict]:
    violations: list[dict] = []
    rows = census.get("rows")
    if not isinstance(rows, list) or not rows:
        return [{"row": None, "code": "no_rows", "detail": "census has no rows"}]

    declared_row_count = census.get("row_count")
    if declared_row_count != len(rows):
        violations.append({
            "row": None,
            "code": "row_count_mismatch",
            "detail": f"row_count={declared_row_count!r} but actual rows={len(rows)}",
        })

    declared_digest = census.get("census_digest")
    expected_digest = _canonical_rows_digest(rows)
    if declared_digest != expected_digest:
        violations.append({
            "row": None,
            "code": "census_digest_mismatch",
            "detail": f"census_digest={declared_digest!r}; expected={expected_digest}",
        })

    seen_ids: set[str] = set()
    for i, row in enumerate(rows):
        aid = row.get("asset_id", f"<row {i}>")

        # required fields
        for f in REQUIRED_FIELDS:
            if f not in row or row[f] in (None, "", [], {}):
                # reachability/consumes/evidence may legitimately be small but present;
                # only flag truly missing/empty.
                if f not in row or row[f] in (None, ""):
                    violations.append({"row": aid, "code": "missing_field", "detail": f})

        # duplicate asset_id
        if aid in seen_ids:
            violations.append({"row": aid, "code": "duplicate_asset_id", "detail": aid})
        seen_ids.add(aid)

        es = row.get("execution_status")
        if es == "unknown" or es in (None, ""):
            violations.append({"row": aid, "code": "unknown_execution_status",
                               "detail": f"execution_status={es!r} (the census forbids unknown)"})
        elif es not in ALLOWED_EXECUTION_STATUS:
            violations.append({"row": aid, "code": "bad_execution_status",
                               "detail": f"execution_status={es!r} not in vocabulary"})

        # execution evidence: a real run/probe must carry a real digest. Text such
        # as "n/a", "see file", or raw path references is not reproducible evidence.
        if es in EVIDENCE_HASH_REQUIRED:
            ev = row.get("execution_evidence") or {}
            oh = ev.get("output_hash") if isinstance(ev, dict) else None
            if not oh:
                violations.append({"row": aid, "code": "missing_output_hash",
                                   "detail": f"execution_status={es} requires execution_evidence.output_hash"})
            elif not _valid_sha256(oh):
                violations.append({"row": aid, "code": "bad_output_hash",
                                   "detail": f"execution_status={es} requires sha256:<64 hex>, got {oh!r}"})

        # gap_class
        gap = row.get("gap_class")
        if gap not in VERB_GAP:
            violations.append({"row": aid, "code": "bad_gap_class", "detail": f"gap_class={gap!r}"})

        # verb / gap consistency
        verb = row.get("recommended_gy_action")
        allowed = VERB_GAP.get(gap, set())
        if gap in VERB_GAP and verb not in allowed:
            violations.append({"row": aid, "code": "verb_gap_mismatch",
                               "detail": f"gap_class={gap!r} forbids verb={verb!r}; allowed={sorted(allowed)}"})

        if gap == "blocked_upstream" and not row.get("blocked_by"):
            violations.append({"row": aid, "code": "blocked_upstream_without_blocker",
                               "detail": "blocked_upstream rows must name blocked_by"})

        # authority status vocabulary
        auth = row.get("authority_status")
        if auth not in ALLOWED_AUTHORITY:
            violations.append({"row": aid, "code": "bad_authority_status", "detail": f"authority_status={auth!r}"})

        # producer-root / smart-component firewall: governed requires a runnable,
        # consumer-reaching asset with evidence.
        if auth == "governed":
            if gap not in GOVERNED_OK_GAP:
                violations.append({"row": aid, "code": "authority_without_provenance",
                                   "detail": f"authority_status=governed but gap_class={gap!r} (not wired/works)"})
            if es not in {"runs_e2e_on_real", "runs_with_deadline_adapter"}:
                violations.append({"row": aid, "code": "authority_without_run",
                                   "detail": f"authority_status=governed but execution_status={es!r}"})
            if not row.get("evidence_refs"):
                violations.append({"row": aid, "code": "authority_without_evidence",
                                   "detail": "authority_status=governed but evidence_refs empty"})

        if auth == "laundered":
            if gap != "wired_but_ungoverned":
                violations.append({"row": aid, "code": "laundered_authority_wrong_gap",
                                   "detail": f"authority_status=laundered requires wired_but_ungoverned, got {gap!r}"})
            if verb not in {"govern", "repair"}:
                violations.append({"row": aid, "code": "laundered_authority_wrong_action",
                                   "detail": f"authority_status=laundered requires govern/repair, got {verb!r}"})
            if not row.get("evidence_refs"):
                violations.append({"row": aid, "code": "laundered_authority_without_evidence",
                                   "detail": "authority_status=laundered but evidence_refs empty"})

        if gap == "wired_and_works":
            called = _row_text((row.get("reachability") or {}).get("called_from_production"))
            if any(token in called for token in ("false", "tools-only", "not invoked", "registered-only")):
                violations.append({"row": aid, "code": "wired_and_works_not_production",
                                   "detail": f"wired_and_works must be production-called, got {called!r}"})
            destination = _row_text(row.get("output_destination"))
            if destination.startswith("dropped"):
                violations.append({"row": aid, "code": "wired_and_works_no_consumer",
                                   "detail": f"wired_and_works must reach a consumer, got output_destination={destination!r}"})

    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    ap.add_argument("--json", action="store_true", help="emit machine-readable report")
    args = ap.parse_args(argv)

    if not args.census.exists():
        print(f"FAIL: census artifact not found: {args.census}", file=sys.stderr)
        return 2
    census = json.loads(args.census.read_text())
    violations = validate(census)
    rows = census.get("rows", [])

    report = {
        "census": str(args.census),
        "row_count": len(rows),
        "violation_count": len(violations),
        "status": "pass" if not violations else "fail",
        "violations": violations,
        "status_counts": {
            s: sum(1 for r in rows if r.get("execution_status") == s)
            for s in sorted({r.get("execution_status") for r in rows})
        },
        "gap_counts": {
            g: sum(1 for r in rows if r.get("gap_class") == g)
            for g in sorted({r.get("gap_class") for r in rows})
        },
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"GY-0 census completeness check: {report['status'].upper()}")
        print(f"  rows={report['row_count']}  violations={report['violation_count']}")
        print(f"  execution_status: {report['status_counts']}")
        print(f"  gap_class: {report['gap_counts']}")
        for v in violations:
            print(f"  VIOLATION [{v['code']}] {v['row']}: {v['detail']}")
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
