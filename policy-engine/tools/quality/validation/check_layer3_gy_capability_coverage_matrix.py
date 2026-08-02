#!/usr/bin/env python3
"""GY repo-wide capability coverage matrix check.

Recomputes the summary from the rows (so the headline counts cannot drift from the
grid) and enforces row integrity. FAILS (exit 1) on any of:

  * a row missing a chain stage, or using a status outside the vocabulary;
  * a row with no `audits` citation, bad `gap_class`, or verb inconsistent with gap;
  * a declared summary that disagrees with the recomputed one;
  * a stale top-level digest.

Usage:
    python3 tools/quality/validation/check_layer3_gy_capability_coverage_matrix.py [--json]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

ART = (
    Path(__file__).resolve().parents[3]
    / "architecture" / "policy_design_case" / "layer3_gy_task0_audit"
    / "layer3_gy_capability_coverage_matrix.json"
)

STAGES = ["contract", "producer", "artifact_or_event", "bridge", "consumer", "surface", "semantic_test"]
STATUS = {"proven", "partial", "bridge_missing", "surface_missing", "absent", "not_audited", "out_of_route", "n/a"}
VERB_GAP = {
    "wired_and_works": {"govern", "none"},
    "wired_but_ungoverned": {"govern", "repair", "build"},
    "wired_but_rotten": {"repair"},
    "built_not_wired": {"wire"},
    "contract_without_producer": {"build"},
    "producer_without_consumer": {"wire"},
    "partial": {"extend", "wire", "repair", "demote", "none"},
    "missing": {"build"},
    "blocked_upstream": {"none", "wire"},
}


def validate(art: dict) -> list[dict]:
    v: list[dict] = []
    rows = art.get("rows")
    if not isinstance(rows, list) or not rows:
        return [{"code": "no_rows", "detail": "matrix has no rows"}]

    # digest
    body = {k: art[k] for k in art if k != "digest"}
    exp = "sha256:" + hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    if art.get("digest") != exp:
        v.append({"code": "digest_mismatch", "detail": f"declared={art.get('digest')} expected={exp}"})

    seen = set()
    for i, r in enumerate(rows):
        cid = r.get("capability", f"<row {i}>")
        if cid in seen:
            v.append({"code": "duplicate_capability", "detail": cid})
        seen.add(cid)
        chain = r.get("chain") or {}
        for s in STAGES:
            c = chain.get(s)
            if not isinstance(c, dict) or "status" not in c:
                v.append({"code": "missing_stage", "detail": f"{cid}: {s}"})
            elif c["status"] not in STATUS:
                v.append({"code": "bad_status", "detail": f"{cid}.{s}={c['status']!r}"})
        if not r.get("audits"):
            v.append({"code": "uncited_row", "detail": cid})
        gap = r.get("gap_class")
        if gap not in VERB_GAP:
            v.append({"code": "bad_gap_class", "detail": f"{cid}: {gap!r}"})
        elif r.get("verb") not in VERB_GAP[gap]:
            v.append({"code": "verb_gap_mismatch", "detail": f"{cid}: gap={gap} verb={r.get('verb')!r}"})

    # recompute summary
    recomputed = {s: dict(Counter(r["chain"][s]["status"] for r in rows if s in r.get("chain", {}))) for s in STAGES}
    declared = (art.get("summary") or {}).get("stage_status_counts") or {}
    for s in STAGES:
        if declared.get(s) != recomputed[s]:
            v.append({"code": "summary_drift", "detail": f"stage {s}: declared={declared.get(s)} recomputed={recomputed[s]}"})
    declared_rc = (art.get("summary") or {}).get("row_count")
    if declared_rc != len(rows):
        v.append({"code": "row_count_drift", "detail": f"declared={declared_rc} actual={len(rows)}"})
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
              "row_count": len(art.get("rows", [])), "violation_count": len(violations), "violations": violations}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"GY capability coverage matrix: {report['status'].upper()} (rows={report['row_count']}, violations={len(violations)})")
        for x in violations:
            print(f"  [{x['code']}] {x['detail']}")
    return 0 if not violations else 1


if __name__ == "__main__":
    import sys

    from tools.lib.timing import run_timed_entrypoint

    raise SystemExit(run_timed_entrypoint(main, script_path=__file__, argv=sys.argv[1:]))
