#!/usr/bin/env python3
"""GY workflow-mode truth audit check.

Re-derives the node-set algebra from the LIVE workflow specs and confirms the
committed audit artifact matches reality. FAILS (exit 1) on any of:

  * the audit's node_counts / shared-spine / unique-set claims diverging from the
    live specs (audit drifted from code);
  * the shared-spine node_id-identity claim being false;
  * a stale top-level digest;
  * missing required sections.

This makes the artifact a recomputed claim, not prose.

Usage:
    python3 tools/quality/validation/check_layer3_gy_workflow_mode_truth_audit.py [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from tools.lib.timing import run_timed_entrypoint

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "architecture" / "policy_design_case" / "layer3_gy_task0_audit" / "layer3_gy_workflow_mode_truth_audit.json"

REQUIRED_SECTIONS = (
    "selection_truth",
    "workflow_specs",
    "execution_census_real_panel",
    "shared_spine_governance_tail_blocker",
    "consolidation_map",
    "recommended_target_for_future_work",
)


def _live_specs() -> dict[str, dict[str, str]]:
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from loguru import logger as _l  # type: ignore
        _l.remove()
    except Exception:
        pass
    from polisyos.scientist.orchestration.workflows.causal_full import causal_full_workflow_spec
    from polisyos.scientist.orchestration.workflows.policy_design import (
        policy_design_workflow_spec,
    )
    from polisyos.scientist.orchestration.workflows.policy_verified import (
        policy_verified_workflow_spec,
    )

    specs = {
        "policy_design": policy_design_workflow_spec(),
        "causal_full": causal_full_workflow_spec(),
        "policy_verified": policy_verified_workflow_spec(),
    }
    return {name: {n.alias: str(n.node_id) for n in spec.nodes} for name, spec in specs.items()}


def validate(art: dict) -> list[dict]:
    v: list[dict] = []
    for s in REQUIRED_SECTIONS:
        if s not in art:
            v.append({"code": "missing_section", "detail": s})

    # digest
    body = {k: art[k] for k in art if k != "digest"}
    expected = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if art.get("digest") != expected:
        v.append({"code": "digest_mismatch", "detail": f"declared={art.get('digest')} expected={expected}"})

    # recompute node-set algebra from live specs
    try:
        live = _live_specs()
    except Exception as exc:  # pragma: no cover
        v.append({"code": "live_spec_load_failed", "detail": str(exc)[:160]})
        return v

    sets = {k: set(live[k]) for k in live}
    common = sets["policy_design"] & sets["causal_full"] & sets["policy_verified"]
    ws = art.get("workflow_specs", {})

    claimed_counts = ws.get("node_counts", {})
    live_counts = {k: len(live[k]) for k in live}
    if claimed_counts != live_counts:
        v.append({"code": "node_count_drift", "detail": f"claimed={claimed_counts} live={live_counts}"})

    if sorted(ws.get("shared_spine_common_to_all_3", [])) != sorted(common):
        v.append({"code": "shared_spine_drift",
                  "detail": f"claimed {len(ws.get('shared_spine_common_to_all_3', []))} vs live {len(common)}"})

    # node_id identity across the common spine
    nonident = [a for a in common if len({live[k][a] for k in live}) != 1]
    if nonident:
        v.append({"code": "shared_spine_node_id_not_identical", "detail": str(sorted(nonident))})

    # pv subset claim
    claim_subset = ws.get("policy_verified_is_subset_of_policy_design_nodes")
    live_subset = sets["policy_verified"] <= sets["policy_design"]
    if claim_subset != live_subset:
        v.append({"code": "pv_subset_claim_drift", "detail": f"claimed={claim_subset} live={live_subset}"})

    # only_* sets
    checks = {
        "only_policy_design": sets["policy_design"] - sets["causal_full"] - sets["policy_verified"],
        "only_causal_full": sets["causal_full"] - sets["policy_design"] - sets["policy_verified"],
        "only_policy_verified": sets["policy_verified"] - sets["policy_design"] - sets["causal_full"],
    }
    for key, live_set in checks.items():
        if sorted(ws.get(key, [])) != sorted(live_set):
            v.append({"code": f"{key}_drift", "detail": f"claimed={sorted(ws.get(key, []))} live={sorted(live_set)}"})

    return v


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--artifact", type=Path, default=ART)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    if not args.artifact.exists():
        print(f"FAIL: artifact not found: {args.artifact}", file=sys.stderr)
        return 2
    art = json.loads(args.artifact.read_text())
    violations = validate(art)
    report = {"artifact": str(args.artifact), "status": "pass" if not violations else "fail",
              "violation_count": len(violations), "violations": violations}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"GY workflow-mode truth audit: {report['status'].upper()} (violations={len(violations)})")
        for x in violations:
            print(f"  [{x['code']}] {x['detail']}")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
