#!/usr/bin/env python3
"""Run the W12.F cloud one-lane revalidation phase."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command, run_command

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.w12f.cloud_one_lane_revalidation.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12f.cloud_one_lane_revalidation_manifest.v1"
)
TOOL_NAME = "quality.validation.run-policy-design-case-cloud-one-lane-revalidation"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.F"
PHASE_NAME = "Cloud One-Lane Revalidation"
DEFAULT_CLOUD_LANE_ID = (
    "profile-research__provider-live_gonka_proxy__data-canonical_production"
    "__scenario-public_golden__ui-api_only"
)
DEFAULT_OUTPUT = Path(
    "_build/.tmp/production-quality/w12f_cloud_one_lane_revalidation.json"
)
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave12f_cloud_one_lane_revalidation_manifest.json"
)
DEFAULT_MATRIX_RUN_REPORT = Path("_build/.tmp/production-quality/cloud_wave12/canary_matrix.json")
DEFAULT_W12B_REPORT = Path(
    "_build/.tmp/production-quality/w12b_compilation_truthfulness_audit.json"
)
DEFAULT_W12C_REPORT = Path(
    "_build/.tmp/production-quality/w12c_domain_coverage_critic_diversity_audit.json"
)
DEFAULT_W12D_REPORT = Path(
    "_build/.tmp/production-quality/w12d_universal_outcome_corpus_run.json"
)
DEFAULT_W12E_REPORT = Path(
    "_build/.tmp/production-quality/w12e_bundle_replay_inspection.json"
)
ROLLOUT_POSTURES = ("research-only", "governed-pilot", "production-capable")
FLOOR_POLICY: Mapping[str, Mapping[str, float | None]] = {
    "research-only": {
        "minimum_runtime_useful_design_rate": None,
        "minimum_useful_design_alignment_rate": None,
        "minimum_compilation_truthfulness_rate": None,
    },
    "governed-pilot": {
        "minimum_runtime_useful_design_rate": 0.5,
        "minimum_useful_design_alignment_rate": 0.5,
        "minimum_compilation_truthfulness_rate": 60.0,
    },
    "production-capable": {
        "minimum_runtime_useful_design_rate": 0.7,
        "minimum_useful_design_alignment_rate": 0.7,
        "minimum_compilation_truthfulness_rate": 80.0,
    },
}
FORBIDDEN_CLOUD_AUTHORITY = frozenset(
    {
        "producer_domain_truth",
        "claim_evidence_authority",
        "production_closeout_authority",
        "public_projection_authority",
    }
)


def build_w12f_cloud_one_lane_revalidation_report(
    *,
    matrix_run_report: Mapping[str, Any],
    w12b_report: Mapping[str, Any],
    w12c_report: Mapping[str, Any],
    w12d_report: Mapping[str, Any],
    w12e_report: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
    rollout_posture: str = "governed-pilot",
    lane_id: str = DEFAULT_CLOUD_LANE_ID,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the W12.F one-lane cloud revalidation report."""

    if rollout_posture not in ROLLOUT_POSTURES:
        raise ValueError(f"unknown rollout posture: {rollout_posture}")

    lane = _select_lane(matrix_run_report, lane_id)
    metrics = _outcome_metrics(
        w12b_report=w12b_report,
        w12c_report=w12c_report,
        w12d_report=w12d_report,
    )
    blockers = [
        *_lane_blockers(lane=lane, lane_id=lane_id),
        *_phase_blockers(w12e_report=w12e_report),
        *_metric_floor_blockers(metrics=metrics, rollout_posture=rollout_posture),
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": generated_at,
        "repo_root": str(Path(repo_root).resolve()),
        "rollout_posture": rollout_posture,
        "status": "blocked" if blockers else "pass",
        "summary": {
            "selected_lane_id": lane_id,
            "selected_lane_status": str(lane.get("status") or "missing"),
            "scorecard_status": str(lane.get("scorecard_status") or "missing"),
            "bundle_path": lane.get("bundle_path"),
            "typed_blocker_count": len(blockers),
        },
        "selected_lane": dict(lane),
        "outcome_metrics": metrics,
        "floor_policy": _json_floor_policy(FLOOR_POLICY[rollout_posture]),
        "floor_evaluation": _floor_evaluation(metrics, rollout_posture=rollout_posture),
        "frozen_revision_config": _frozen_revision_config(Path(repo_root).resolve()),
        "typed_blockers": blockers,
        "authority_boundary": _phase_authority_boundary(),
        "metric_policy": {
            "preserves_three_outcome_metrics": True,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
            "cloud_lane_evidence_is_producer_authority": False,
        },
        "pattern_pass": {
            "relevant_patterns": ["P01", "P02", "P03", "P05", "P10", "P12", "P15"],
            "target_correct_pattern": (
                "W12.F consumes one frozen cloud/debug lane plus W12 metric reports, "
                "keeps unknown provenance collapses typed, and refuses to treat a "
                "lane scorecard as producer, claim, closeout, or projection authority."
            ),
            "missing_capability_labels": sorted(
                {str(blocker.get("capability_label")) for blocker in blockers}
            ),
        },
    }


def build_w12f_manifest() -> dict[str, Any]:
    """Build the deterministic W12.F command contract manifest."""

    cloud_command = (
        "uv",
        "run",
        "python",
        "tools/ops_runners/runtime/run_canary_matrix.py",
        "--only-lane",
        DEFAULT_CLOUD_LANE_ID,
        "--allow-live-provider",
        "--json-output",
        DEFAULT_MATRIX_RUN_REPORT.as_posix(),
    )
    report_command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_policy_design_case_cloud_one_lane_revalidation.py",
        "--repo-root",
        ".",
        "--matrix-run-report",
        DEFAULT_MATRIX_RUN_REPORT.as_posix(),
        "--w12b-report",
        DEFAULT_W12B_REPORT.as_posix(),
        "--w12c-report",
        DEFAULT_W12C_REPORT.as_posix(),
        "--w12d-report",
        DEFAULT_W12D_REPORT.as_posix(),
        "--w12e-report",
        DEFAULT_W12E_REPORT.as_posix(),
        "--output",
        DEFAULT_OUTPUT.as_posix(),
    )
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "status": "implemented",
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": GENERATED_AT,
        "owner": "team-runtime-platform",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12f-cloud-one-lane-revalidation"
        ),
        "tool_ref": (
            "repo://tools/quality/validation/"
            "run_policy_design_case_cloud_one_lane_revalidation.py"
        ),
        "canary_matrix_tool_ref": "repo://tools/ops_runners/runtime/run_canary_matrix.py",
        "command_contract": {
            "cloud_lane_command": render_command(cloud_command),
            "report_command": render_command(report_command),
            "output_refs": [
                DEFAULT_MATRIX_RUN_REPORT.as_posix(),
                DEFAULT_OUTPUT.as_posix(),
            ],
            "required_checks": [
                "selected_cloud_lane_passed",
                "no_unknown_provenance_collapse",
                "frozen_revision_config_recorded",
                "three_outcome_metrics_preserved",
            ],
            "owner": "team-runtime-platform",
            "next_action": (
                "Rerun the frozen one-lane cloud/debug matrix after repairing "
                "typed lane, provenance, W12.E, or metric-floor blockers."
            ),
        },
        "floor_policy": {key: _json_floor_policy(value) for key, value in FLOOR_POLICY.items()},
        "metric_policy": {
            "preserves_three_outcome_metrics": True,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
        },
        "authority_boundary": _phase_authority_boundary(),
        "pattern_pass": {
            "relevant_patterns": ["P01", "P02", "P03", "P05", "P10", "P12", "P15"],
            "target_correct_pattern": (
                "Cloud one-lane evidence is a rollout validation input, not "
                "producer or closeout authority."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12f_cloud_one_lane_revalidation.py"
            ),
            "command_ref": render_command(report_command),
        },
    }


def run_w12f_cloud_one_lane_revalidation(
    *,
    repo_root: str | Path = REPO_ROOT,
    matrix_run_report_path: str | Path = DEFAULT_MATRIX_RUN_REPORT,
    w12b_report_path: str | Path = DEFAULT_W12B_REPORT,
    w12c_report_path: str | Path = DEFAULT_W12C_REPORT,
    w12d_report_path: str | Path = DEFAULT_W12D_REPORT,
    w12e_report_path: str | Path = DEFAULT_W12E_REPORT,
    rollout_posture: str = "governed-pilot",
    lane_id: str = DEFAULT_CLOUD_LANE_ID,
) -> dict[str, Any]:
    """Load phase evidence and return the W12.F report."""

    root = Path(repo_root).resolve()
    return build_w12f_cloud_one_lane_revalidation_report(
        matrix_run_report=_load_optional_json(_resolve(root, Path(matrix_run_report_path))),
        w12b_report=_load_optional_json(_resolve(root, Path(w12b_report_path))),
        w12c_report=_load_optional_json(_resolve(root, Path(w12c_report_path))),
        w12d_report=_load_optional_json(_resolve(root, Path(w12d_report_path))),
        w12e_report=_load_optional_json(_resolve(root, Path(w12e_report_path))),
        repo_root=root,
        rollout_posture=rollout_posture,
        lane_id=lane_id,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    if args.write_manifest:
        atomic_write_json(_resolve(repo_root, args.output), build_w12f_manifest())
        return 0

    report = run_w12f_cloud_one_lane_revalidation(
        repo_root=repo_root,
        matrix_run_report_path=args.matrix_run_report,
        w12b_report_path=args.w12b_report,
        w12c_report_path=args.w12c_report,
        w12d_report_path=args.w12d_report,
        w12e_report_path=args.w12e_report,
        rollout_posture=args.rollout_posture,
        lane_id=args.lane_id,
    )
    atomic_write_json(_resolve(repo_root, args.output), report)
    if report["status"] == "pass" or args.allow_typed_blockers:
        return 0
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--matrix-run-report", type=Path, default=DEFAULT_MATRIX_RUN_REPORT)
    parser.add_argument("--w12b-report", type=Path, default=DEFAULT_W12B_REPORT)
    parser.add_argument("--w12c-report", type=Path, default=DEFAULT_W12C_REPORT)
    parser.add_argument("--w12d-report", type=Path, default=DEFAULT_W12D_REPORT)
    parser.add_argument("--w12e-report", type=Path, default=DEFAULT_W12E_REPORT)
    parser.add_argument("--lane-id", default=DEFAULT_CLOUD_LANE_ID)
    parser.add_argument("--rollout-posture", choices=ROLLOUT_POSTURES, default="governed-pilot")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--allow-typed-blockers", action="store_true")
    return parser


def _select_lane(matrix_run_report: Mapping[str, Any], lane_id: str) -> Mapping[str, Any]:
    for lane in _sequence_of_mappings(matrix_run_report.get("lanes")):
        if lane.get("lane_id") == lane_id:
            return lane
    return {}


def _lane_blockers(*, lane: Mapping[str, Any], lane_id: str) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    if not lane:
        blockers.append(
            _blocker(
                code="w12f_cloud_lane_evidence_missing",
                message="W12.F did not receive evidence for the selected cloud/debug lane.",
                owner="team-runtime-platform",
                capability_label="producer_missing",
                lane_id=lane_id,
            )
        )
        return blockers
    if lane.get("status") != "passed":
        blockers.append(
            _blocker(
                code="w12f_cloud_lane_not_passed",
                message="The selected cloud/debug lane did not pass.",
                owner="team-runtime-platform",
                capability_label="verification_missing",
                lane_id=lane_id,
                observed_status=str(lane.get("status") or "missing"),
            )
        )
    if _sequence(lane.get("unknown_provenance_collapses")):
        blockers.append(
            _blocker(
                code="w12f_unknown_provenance_collapse",
                message="The cloud lane reported an unknown-provenance collapse.",
                owner="team-runtime-platform",
                capability_label="provenance_missing",
                lane_id=lane_id,
            )
        )
    if _sequence(lane.get("source_truth_conflicts")):
        blockers.append(
            _blocker(
                code="w12f_source_truth_conflict",
                message="The cloud lane reported source-truth conflicts.",
                owner="team-runtime-platform",
                capability_label="semantic_test_missing",
                lane_id=lane_id,
            )
        )
    return blockers


def _phase_blockers(*, w12e_report: Mapping[str, Any]) -> list[dict[str, Any]]:
    if w12e_report.get("status") in {None, "", "pass"}:
        return []
    return [
        _blocker(
            code="w12f_required_w12e_phase_blocked",
            message="W12.E bundle/replay/inspection evidence is blocked.",
            owner="team-runtime-quality",
            capability_label="verification_missing",
            upstream_phase="W12.E",
        )
    ]


def _metric_floor_blockers(
    *,
    metrics: Mapping[str, Mapping[str, Any]],
    rollout_posture: str,
) -> list[dict[str, Any]]:
    policy = FLOOR_POLICY[rollout_posture]
    checks = (
        (
            "runtime_useful_design_rate",
            "minimum_runtime_useful_design_rate",
            "w12f_runtime_useful_design_floor_not_met",
        ),
        (
            "useful_design_alignment_rate",
            "minimum_useful_design_alignment_rate",
            "w12f_useful_design_alignment_floor_not_met",
        ),
        (
            "compilation_truthfulness_rate",
            "minimum_compilation_truthfulness_rate",
            "w12f_compilation_truthfulness_floor_not_met",
        ),
    )
    blockers: list[dict[str, Any]] = []
    for metric_id, floor_key, code in checks:
        floor = policy[floor_key]
        if floor is None:
            continue
        value = metrics.get(metric_id, {}).get("value")
        if value is None or float(value) < float(floor):
            blockers.append(
                _blocker(
                    code=code,
                    message=f"W12.F metric floor not met: {metric_id}.",
                    owner="team-evaluation",
                    capability_label="semantic_test_missing",
                    metric_id=metric_id,
                    floor=float(floor),
                    value=None if value is None else float(value),
                )
            )
    return blockers


def _outcome_metrics(
    *,
    w12b_report: Mapping[str, Any],
    w12c_report: Mapping[str, Any],
    w12d_report: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    w12b_summary = _mapping(w12b_report.get("summary"))
    w12c_summary = _mapping(w12c_report.get("summary"))
    w12d_summary = _mapping(w12d_report.get("summary"))
    return {
        "closeout_honesty_rate": {
            "value": _float_or_none(w12d_summary.get("closeout_honesty_rate")),
            "source_phase": "W12.D",
        },
        "runtime_useful_design_rate": {
            "value": _float_or_none(
                w12d_summary.get("runtime_useful_design_rate")
                or w12d_summary.get("useful_design_rate")
            ),
            "source_phase": "W12.D",
        },
        "expert_useful_design_ceiling": {
            "value": _float_or_none(
                w12d_summary.get("expert_useful_design_ceiling")
                or w12c_summary.get("aggregate_expert_useful_design_ceiling")
            ),
            "source_phase": "W12.D/W12.C",
        },
        "useful_design_alignment_rate": {
            "value": _float_or_none(w12d_summary.get("useful_design_alignment_rate")),
            "source_phase": "W12.D",
        },
        "compilation_truthfulness_rate": {
            "value": _float_or_none(
                w12b_summary.get("aggregate_compilation_truthfulness_rate")
            ),
            "source_phase": "W12.B",
        },
        "critic_ensemble_diversity_jaccard": {
            "value": _float_or_none(
                w12c_summary.get("aggregate_critic_ensemble_diversity_jaccard")
            ),
            "source_phase": "W12.C",
        },
    }


def _floor_evaluation(
    metrics: Mapping[str, Mapping[str, Any]],
    *,
    rollout_posture: str,
) -> dict[str, Any]:
    policy = FLOOR_POLICY[rollout_posture]
    return {
        "rollout_posture": rollout_posture,
        "runtime_useful_design_rate_met": _floor_met(
            metrics["runtime_useful_design_rate"]["value"],
            policy["minimum_runtime_useful_design_rate"],
        ),
        "useful_design_alignment_rate_met": _floor_met(
            metrics["useful_design_alignment_rate"]["value"],
            policy["minimum_useful_design_alignment_rate"],
        ),
        "compilation_truthfulness_rate_met": _floor_met(
            metrics["compilation_truthfulness_rate"]["value"],
            policy["minimum_compilation_truthfulness_rate"],
        ),
    }


def _floor_met(value: object, floor: float | None) -> bool | None:
    if floor is None:
        return None
    if value is None:
        return False
    return float(value) >= floor


def _frozen_revision_config(repo_root: Path) -> dict[str, Any]:
    return {
        "git_revision": _git_revision(repo_root),
        "selected_lane_id": DEFAULT_CLOUD_LANE_ID,
        "feature_flags": {
            "POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED": "runtime",
            "POLISYOS_SCIENTIST_V2_ENABLED": "runtime",
        },
        "tuned_config_refs": ["w12.runtime.default"],
    }


def _git_revision(repo_root: Path) -> str:
    git_bin = shutil.which("git")
    if git_bin is None:
        return "unknown"
    try:
        completed = run_command(
            [git_bin, "rev-parse", "HEAD"],
            cwd=repo_root,
            allowed_prefixes=([git_bin],),
            check=True,
            text=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def _phase_authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["w12f_cloud_one_lane_revalidation"],
        "may_not_use_for": sorted(FORBIDDEN_CLOUD_AUTHORITY),
    }


def _blocker(
    *,
    code: str,
    message: str,
    owner: str,
    capability_label: str,
    lane_id: str | None = None,
    observed_status: str | None = None,
    upstream_phase: str | None = None,
    metric_id: str | None = None,
    floor: float | None = None,
    value: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "message": message,
        "owner": owner,
        "capability_label": capability_label,
        "counts_as_useful_design": False,
        "counts_as_closeout_honesty_failure": False,
        "blocks_rollout_posture": True,
    }
    for key, item in {
        "lane_id": lane_id,
        "observed_status": observed_status,
        "upstream_phase": upstream_phase,
        "metric_id": metric_id,
        "floor": floor,
        "value": value,
    }.items():
        if item is not None:
            payload[key] = item
    return payload


def _json_floor_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    return dict(policy)


def _float_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> Sequence[Any]:
    return value if isinstance(value, Sequence) and not isinstance(value, str | bytes) else ()


def _sequence_of_mappings(value: object) -> list[Mapping[str, Any]]:
    return [item for item in _sequence(value) if isinstance(item, Mapping)]


def _resolve(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def _load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"payload": payload}


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
