#!/usr/bin/env python3
"""Run the W12.B compilation truthfulness audit over the universal corpus."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command
from tools.quality.validation import check_compilation_truthfulness as w11e

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.w12b.compilation_truthfulness_audit.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12b.compilation_truthfulness_audit_manifest.v1"
)
TOOL_NAME = "quality.validation.run-compilation-truthfulness-audit"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.B"
PHASE_NAME = "Compilation Truthfulness Audit Run"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/w12b_compilation_truthfulness_audit.json")
DEFAULT_W11E_OUTPUT = Path(
    "_build/.tmp/production-quality/w12b_compilation_truthfulness_report.json"
)
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave12b_compilation_truthfulness_audit_manifest.json"
)
ROLLOUT_POSTURES = ("research-only", "governed-pilot", "production-capable")
W11E_BUCKETS = w11e.W11E_BUCKETS

FLOOR_POLICY: Mapping[str, Mapping[str, float | None]] = {
    "research-only": {
        "minimum_case_score": None,
        "minimum_aggregate_rate": None,
        "minimum_domain_rate": None,
    },
    "governed-pilot": {
        "minimum_case_score": 50.0,
        "minimum_aggregate_rate": 60.0,
        "minimum_domain_rate": 50.0,
    },
    "production-capable": {
        "minimum_case_score": 70.0,
        "minimum_aggregate_rate": 80.0,
        "minimum_domain_rate": 70.0,
    },
}


def build_w12b_compilation_truthfulness_audit(
    truthfulness_report: Mapping[str, Any],
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_ref: str,
    raw_report_ref: str,
    rollout_posture: str,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Decorate a W11.E report with W12.B rollout-floor blocker semantics."""

    if rollout_posture not in ROLLOUT_POSTURES:
        raise ValueError(f"unknown rollout posture: {rollout_posture}")

    validation = w11e.validate_compilation_truthfulness_report(truthfulness_report)
    summary = _mapping(truthfulness_report.get("summary"))
    cases = [
        _case_with_floor(case, rollout_posture=rollout_posture)
        for case in _sequence_of_mappings(truthfulness_report.get("cases"))
    ]
    floor_evaluation = _evaluate_floors(
        cases=cases,
        summary=summary,
        rollout_posture=rollout_posture,
    )
    blockers = _typed_compilation_blockers(
        cases=cases,
        floor_evaluation=floor_evaluation,
        rollout_posture=rollout_posture,
    )
    issues = [*truthfulness_report.get("issues", []), *validation["issues"]]
    status = _overall_status(
        validation_status=str(validation["status"]),
        w11e_status=str(summary.get("status") or "fail"),
        blockers=blockers,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": generated_at,
        "repo_root": str(Path(repo_root).resolve()),
        "rollout_posture": rollout_posture,
        "corpus_ref": corpus_ref,
        "raw_w11e_report_ref": raw_report_ref,
        "status": status,
        "summary": {
            "case_count": int(summary.get("case_count") or len(cases)),
            "blocked_case_count": int(summary.get("blocked_case_count") or 0),
            "aggregate_compilation_truthfulness_rate": _float_or_zero(
                summary.get("aggregate_compilation_truthfulness_rate")
            ),
            "construct_vocabulary": _mapping(summary.get("construct_vocabulary")),
            "construct_level_truthfulness": _construct_level_truthfulness(summary),
            "by_domain": _mapping_of_mappings(summary.get("by_domain")),
            "by_authority_level": _mapping_of_mappings(summary.get("by_authority_level")),
        },
        "floor_policy": dict(FLOOR_POLICY[rollout_posture]),
        "floor_evaluation": floor_evaluation,
        "cases": cases,
        "typed_compilation_blockers": blockers,
        "metric_policy": {
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
            "compilation_truthfulness_is_separate_metric": True,
        },
        "issues": issues,
        "w11e_validation": validation,
    }


def build_w12b_manifest() -> dict[str, Any]:
    """Build the deterministic W12.B command and metric contract manifest."""

    command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_compilation_truthfulness_audit.py",
        "--repo-root",
        ".",
        "--corpus",
        DEFAULT_CORPUS_PATH.as_posix(),
        "--rollout-posture",
        "governed-pilot",
        "--output",
        DEFAULT_OUTPUT.as_posix(),
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "implemented",
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": GENERATED_AT,
        "owner": "team-evaluation",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12b-compilation-truthfulness-audit-run"
        ),
        "tool_ref": (
            "repo://tools/quality/validation/run_compilation_truthfulness_audit.py"
        ),
        "w11e_tool_ref": (
            "repo://tools/quality/validation/check_compilation_truthfulness.py"
        ),
        "command_contract": {
            "command": render_command(command),
            "output_refs": [
                DEFAULT_OUTPUT.as_posix(),
                DEFAULT_W11E_OUTPUT.as_posix(),
            ],
            "owner": "team-evaluation",
            "next_action": (
                "Repair W11.E missed, hallucinated, scope-drift, or authority-drift "
                "obligations before declaring the W12.B truthfulness floor met."
            ),
        },
        "floor_policy": {posture: dict(policy) for posture, policy in FLOOR_POLICY.items()},
        "metric_policy": {
            "per_case_truthfulness_required": True,
            "aggregate_truthfulness_required": True,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
        },
        "pattern_pass": {
            "relevant_patterns": ["P01", "P03", "P05", "P10", "P13", "P15"],
            "target_correct_pattern": (
                "W12.B consumes the W11.E report as diagnostic evidence, exposes "
                "rollout-posture floor blockers, and keeps compilation "
                "truthfulness separate from useful design and closeout honesty."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12b_compilation_truthfulness_audit.py"
            ),
            "command_ref": render_command(command),
        },
    }


def run_w12b_compilation_truthfulness_audit(
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    rollout_posture: str = "research-only",
    input_report: str | Path | None = None,
    raw_report_output: str | Path = DEFAULT_W11E_OUTPUT,
) -> dict[str, Any]:
    """Run W11.E if needed and return the W12.B decorated report."""

    root = Path(repo_root).resolve()
    if input_report is None:
        truthfulness_report = w11e.build_compilation_truthfulness_report(
            repo_root=root,
            corpus_path=corpus_path,
        )
        raw_output = _resolve(root, Path(raw_report_output))
        atomic_write_json(raw_output, truthfulness_report)
        raw_ref = f"repo://{_repo_relative(root, raw_output)}"
    else:
        input_path = _resolve(root, Path(input_report))
        truthfulness_report = json.loads(input_path.read_text(encoding="utf-8"))
        raw_ref = f"repo://{_repo_relative(root, input_path)}"

    corpus = _resolve(root, Path(corpus_path))
    return build_w12b_compilation_truthfulness_audit(
        truthfulness_report,
        repo_root=root,
        corpus_ref=f"repo://{_repo_relative(root, corpus)}",
        raw_report_ref=raw_ref,
        rollout_posture=rollout_posture,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )


def write_manifest(repo_root: Path, output: Path = DEFAULT_MANIFEST_OUTPUT) -> dict[str, Any]:
    """Write the deterministic W12.B manifest."""

    payload = build_w12b_manifest()
    atomic_write_json(_resolve(repo_root, output), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the W12.B compilation truthfulness audit parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--input-report", type=Path)
    parser.add_argument("--raw-report-output", type=Path, default=DEFAULT_W11E_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest-output", type=Path)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument(
        "--rollout-posture",
        choices=ROLLOUT_POSTURES,
        default="research-only",
    )
    parser.add_argument(
        "--allow-typed-blockers",
        action="store_true",
        help="Exit zero when W12.B floor failures are typed compilation blockers.",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Exit non-zero unless W12.B status is pass.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the W12.B compilation truthfulness audit."""

    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    if args.write_manifest or args.manifest_output:
        write_manifest(repo_root, output=args.manifest_output or DEFAULT_MANIFEST_OUTPUT)
    payload = run_w12b_compilation_truthfulness_audit(
        repo_root=repo_root,
        corpus_path=args.corpus,
        rollout_posture=args.rollout_posture,
        input_report=args.input_report,
        raw_report_output=args.raw_report_output,
    )
    atomic_write_json(_resolve(repo_root, args.output), payload)
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    if payload["status"] == "pass":
        return 0
    if args.allow_typed_blockers and payload["status"] == "blocked":
        return 0
    if args.require_passing:
        return 1
    return 2 if payload["status"] == "blocked" else 1


def _case_with_floor(
    case: Mapping[str, Any],
    *,
    rollout_posture: str,
) -> dict[str, Any]:
    row = dict(case)
    score = _float_or_zero(row.get("per_case_truthfulness_score"))
    floor = FLOOR_POLICY[rollout_posture]["minimum_case_score"]
    below_floor = floor is not None and score < floor
    row["per_case_truthfulness_score"] = score
    row["minimum_case_truthfulness_score"] = floor
    row["floor_status"] = (
        "not_required" if floor is None else "below_floor" if below_floor else "met"
    )
    return row


def _evaluate_floors(
    *,
    cases: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
    rollout_posture: str,
) -> dict[str, Any]:
    policy = FLOOR_POLICY[rollout_posture]
    if policy["minimum_aggregate_rate"] is None:
        return {
            "rollout_posture": rollout_posture,
            "status": "not_required",
            "minimum_case_score": None,
            "minimum_aggregate_rate": None,
            "minimum_domain_rate": None,
            "below_floor_case_ids": [],
            "below_floor_domain_slices": [],
            "aggregate_below_floor": False,
        }

    aggregate_rate = _float_or_zero(summary.get("aggregate_compilation_truthfulness_rate"))
    below_cases = [
        str(case.get("case_id"))
        for case in cases
        if case.get("floor_status") == "below_floor"
    ]
    by_domain = _mapping_of_mappings(summary.get("by_domain"))
    minimum_domain = float(policy["minimum_domain_rate"] or 0.0)
    below_domains = [
        domain
        for domain, row in sorted(by_domain.items())
        if _float_or_zero(row.get("aggregate_compilation_truthfulness_rate"))
        < minimum_domain
    ]
    minimum_aggregate = float(policy["minimum_aggregate_rate"] or 0.0)
    aggregate_below = aggregate_rate < minimum_aggregate
    return {
        "rollout_posture": rollout_posture,
        "status": (
            "not_met" if below_cases or below_domains or aggregate_below else "met"
        ),
        "minimum_case_score": policy["minimum_case_score"],
        "minimum_aggregate_rate": policy["minimum_aggregate_rate"],
        "minimum_domain_rate": policy["minimum_domain_rate"],
        "below_floor_case_ids": below_cases,
        "below_floor_domain_slices": below_domains,
        "aggregate_below_floor": aggregate_below,
    }


def _construct_level_truthfulness(summary: Mapping[str, Any]) -> dict[str, int]:
    construct_summary = _mapping(summary.get("construct_vocabulary"))
    return {
        "true_positive_construct_count": int(
            construct_summary.get("true_positive_construct_count") or 0
        ),
        "missed_construct_count": int(construct_summary.get("missed_construct_count") or 0),
        "hallucinated_construct_count": int(
            construct_summary.get("hallucinated_construct_count") or 0
        ),
        "authority_drift_construct_count": int(
            construct_summary.get("authority_drift_construct_count") or 0
        ),
    }


def _typed_compilation_blockers(
    *,
    cases: Sequence[Mapping[str, Any]],
    floor_evaluation: Mapping[str, Any],
    rollout_posture: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for case in cases:
        if case.get("floor_status") != "below_floor":
            continue
        blockers.append(
            _blocker(
                code="compilation_truthfulness_case_below_floor",
                rollout_posture=rollout_posture,
                case_id=str(case.get("case_id")),
                domain=str(case.get("domain") or "unknown"),
                authority_level=str(case.get("authority_level") or "unknown"),
                actual_score=_float_or_zero(case.get("per_case_truthfulness_score")),
                floor=floor_evaluation.get("minimum_case_score"),
                next_action=(
                    "Repair missed, hallucinated, scope-drift, or authority-drift "
                    "obligations for this case before counting the rollout posture "
                    "truthfulness floor as met."
                ),
            )
        )
    if floor_evaluation.get("aggregate_below_floor"):
        blockers.append(
            _blocker(
                code="compilation_truthfulness_aggregate_floor_not_met",
                rollout_posture=rollout_posture,
                actual_score=None,
                floor=floor_evaluation.get("minimum_aggregate_rate"),
                next_action=(
                    "Repair compiler alignment across the corpus before promotion "
                    "beyond the posture floor."
                ),
            )
        )
    for domain in floor_evaluation.get("below_floor_domain_slices") or []:
        blockers.append(
            _blocker(
                code="compilation_truthfulness_domain_floor_not_met",
                rollout_posture=rollout_posture,
                domain=str(domain),
                actual_score=None,
                floor=floor_evaluation.get("minimum_domain_rate"),
                next_action=(
                    "Repair domain-specific obligation compilation or mark the "
                    "domain slice research-only/held in W12.G."
                ),
            )
        )
    return blockers


def _blocker(
    *,
    code: str,
    rollout_posture: str,
    next_action: str,
    case_id: str | None = None,
    domain: str | None = None,
    authority_level: str | None = None,
    actual_score: float | None,
    floor: object,
) -> dict[str, Any]:
    return {
        "blocker_id": "w12b_" + "_".join(item for item in (case_id, domain, code) if item),
        "code": code,
        "blocker_type": "typed_compilation_blocker",
        "severity": "blocker",
        "phase_id": PHASE_ID,
        "owner": "team-evaluation",
        "case_id": case_id,
        "domain": domain,
        "authority_level": authority_level,
        "rollout_posture": rollout_posture,
        "actual_score": actual_score,
        "floor": floor,
        "message": (
            "Compilation truthfulness is below the rollout-posture floor. This "
            "is a typed compilation blocker, not useful-design success and not "
            "a closeout-honesty failure."
        ),
        "next_action": next_action,
        "blocks_rollout_posture": True,
        "counts_as_useful_design": False,
        "counts_as_closeout_honesty_failure": False,
        "counts_as_closeout_honesty": False,
    }


def _overall_status(
    *,
    validation_status: str,
    w11e_status: str,
    blockers: Sequence[Mapping[str, Any]],
) -> str:
    if validation_status == "fail" or w11e_status == "fail":
        return "fail"
    return "blocked" if blockers else "pass"


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mapping_of_mappings(value: object) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {str(key): row for key, row in value.items() if isinstance(row, Mapping)}


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _float_or_zero(value: object) -> float:
    if isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return 0.0
    return 0.0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
