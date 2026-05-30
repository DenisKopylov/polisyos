#!/usr/bin/env python3
"""Run the W12.G rollout decision phase."""

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

SCHEMA_VERSION = "policyos.policy_design_case.w12g.rollout_decision.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12g.rollout_decision_manifest.v1"
)
TOOL_NAME = "quality.validation.run-policy-design-case-rollout-decision"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.G"
PHASE_NAME = "Rollout Decision"
DEFAULT_OUTPUT = Path("_build/.tmp/production-quality/w12g_rollout_decision.json")
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/wave12g_rollout_decision_manifest.json"
)
DEFAULT_W12A_REPORT = Path(
    "_build/.tmp/production-quality/universal_pdc_local_validation_ladder.json"
)
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
DEFAULT_W12F_REPORT = Path(
    "_build/.tmp/production-quality/w12f_cloud_one_lane_revalidation.json"
)
CONSUMED_PHASES = ("W12.A", "W12.B", "W12.C", "W12.D", "W12.E", "W12.F")
ROLLOUT_POSTURES = ("research-only", "governed-pilot", "production-capable")
FLOOR_POLICY: Mapping[str, Mapping[str, float | None]] = {
    "research-only": {
        "minimum_closeout_honesty_rate": None,
        "minimum_runtime_useful_design_rate": None,
        "minimum_compilation_truthfulness_rate": None,
        "minimum_useful_design_alignment_rate": None,
        "minimum_expert_useful_design_ceiling": None,
    },
    "governed-pilot": {
        "minimum_closeout_honesty_rate": 0.9,
        "minimum_runtime_useful_design_rate": 0.5,
        "minimum_compilation_truthfulness_rate": 60.0,
        "minimum_useful_design_alignment_rate": 0.5,
        "minimum_expert_useful_design_ceiling": 0.5,
    },
    "production-capable": {
        "minimum_closeout_honesty_rate": 0.95,
        "minimum_runtime_useful_design_rate": 0.7,
        "minimum_compilation_truthfulness_rate": 80.0,
        "minimum_useful_design_alignment_rate": 0.7,
        "minimum_expert_useful_design_ceiling": 0.7,
    },
}
FORBIDDEN_ROLLOUT_AUTHORITY = frozenset(
    {
        "producer_domain_truth",
        "claim_evidence_authority",
        "production_closeout_authority",
        "public_projection_authority",
    }
)


def build_w12g_rollout_decision_report(
    *,
    w12a_report: Mapping[str, Any],
    w12b_report: Mapping[str, Any],
    w12c_report: Mapping[str, Any],
    w12d_report: Mapping[str, Any],
    w12d_real_report: Mapping[str, Any] | None = None,
    w12d_stub_report: Mapping[str, Any] | None = None,
    w12e_report: Mapping[str, Any],
    w12f_report: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
    requested_posture: str = "governed-pilot",
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Build the W12.G rollout decision from W12.A-F phase reports."""

    if requested_posture not in ROLLOUT_POSTURES:
        raise ValueError(f"unknown rollout posture: {requested_posture}")

    w12d_reports = _w12d_reports_by_mode(
        primary=w12d_report,
        real=w12d_real_report,
        stub=w12d_stub_report,
    )
    w12d_runtime_report = w12d_reports.get("real_producer") or {}
    w12d_metric_report = w12d_runtime_report or w12d_report
    phase_reports = {
        "W12.A": w12a_report,
        "W12.B": w12b_report,
        "W12.C": w12c_report,
        "W12.D": w12d_metric_report,
        "W12.E": w12e_report,
        "W12.F": w12f_report,
    }
    metrics = _metric_citations(
        w12a_report=w12a_report,
        w12b_report=w12b_report,
        w12c_report=w12c_report,
        w12d_report=w12d_report,
        w12d_real_report=w12d_runtime_report,
        w12d_stub_report=w12d_reports.get("corpus_stub") or {},
    )
    w12d_rollout_blockers = _w12d_rollout_blockers(w12d_metric_report)
    held_domain_slices = _held_domain_slices(w12c_report)
    environment_blockers = _environment_blockers(phase_reports)
    blockers = [
        *_required_phase_blockers(phase_reports),
        *_metric_floor_blockers(metrics=metrics, requested_posture=requested_posture),
        *_corpus_stub_boundary_blockers(
            w12d_metric_report,
            requested_posture=requested_posture,
        ),
    ]
    decision = _decision(requested_posture=requested_posture, blockers=blockers)
    frozen = _frozen_revision_config(
        repo_root=Path(repo_root).resolve(),
        w12f_report=w12f_report,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "phase_id": PHASE_ID,
        "phase_name": PHASE_NAME,
        "generated_at": generated_at,
        "repo_root": str(Path(repo_root).resolve()),
        "requested_posture": requested_posture,
        "status": "blocked" if blockers else "pass",
        "decision": decision,
        "requested_posture_allowed": not blockers,
        "maximum_allowed_posture": requested_posture if not blockers else "hold",
        "w12d_report_modes": {
            "real_producer_present": bool(w12d_runtime_report),
            "corpus_stub_present": bool(w12d_reports.get("corpus_stub")),
        },
        "consumed_phase_reports": _phase_statuses(phase_reports),
        "metric_citations": metrics,
        "domain_authority_metric_matrix": _mapping(
            w12c_report.get("domain_authority_useful_design_matrix")
        ),
        "rollout_blockers": w12d_rollout_blockers,
        "held_domain_slices": held_domain_slices,
        "environment_blockers": environment_blockers,
        "floor_policy": _json_floor_policy(FLOOR_POLICY[requested_posture]),
        "typed_blockers": blockers,
        "remediation_backlog": _remediation_backlog(blockers),
        "rollback_and_kill_switches": rollback_and_kill_switches(),
        "frozen_revision_config": frozen,
        "release_note": {
            "rollout_posture": decision,
            "requested_posture": requested_posture,
            "frozen_git_revision": frozen["git_revision"],
            "metric_citations": metrics,
            "typed_blocker_count": len(blockers),
        },
        "authority_boundary": _phase_authority_boundary(),
        "metric_policy": {
            "rollout_decision_cites_three_metrics": True,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
            "corpus_stub_never_satisfies_production_authority": True,
        },
        "pattern_pass": {
            "relevant_patterns": [
                "P01",
                "P02",
                "P03",
                "P04",
                "P05",
                "P09",
                "P10",
                "P12",
                "P15",
            ],
            "target_correct_pattern": (
                "W12.G consumes phase evidence, cites closeout honesty, runtime "
                "useful design, and compilation truthfulness separately, and "
                "turns any unmet authority/status condition into a typed hold."
            ),
            "missing_capability_labels": sorted(
                {str(blocker.get("capability_label")) for blocker in blockers}
            ),
        },
    }


def build_w12g_manifest() -> dict[str, Any]:
    """Build the deterministic W12.G command contract manifest."""

    command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_policy_design_case_rollout_decision.py",
        "--repo-root",
        ".",
        "--w12a-report",
        DEFAULT_W12A_REPORT.as_posix(),
        "--w12b-report",
        DEFAULT_W12B_REPORT.as_posix(),
        "--w12c-report",
        DEFAULT_W12C_REPORT.as_posix(),
        "--w12d-report",
        DEFAULT_W12D_REPORT.as_posix(),
        "--w12e-report",
        DEFAULT_W12E_REPORT.as_posix(),
        "--w12f-report",
        DEFAULT_W12F_REPORT.as_posix(),
        "--requested-posture",
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
        "owner": "team-release-governance",
        "implementation_plan_ref": (
            "repo://docs/plans/active/"
            "POLICYOS_UNIVERSAL_POLICY_DESIGN_CASE_IMPLEMENTATION_PLAN.md"
            "#w12g-rollout-decision"
        ),
        "tool_ref": (
            "repo://tools/quality/validation/run_policy_design_case_rollout_decision.py"
        ),
        "consumes_phase_reports": list(CONSUMED_PHASES),
        "command_contract": {
            "command": render_command(command),
            "output_refs": [DEFAULT_OUTPUT.as_posix()],
            "required_checks": [
                "w12a_to_w12f_phase_evidence_present",
                "closeout_honesty_metric_cited",
                "runtime_useful_design_metric_cited",
                "compilation_truthfulness_metric_cited",
                "rollback_and_kill_switches_declared",
                "corpus_stub_production_boundary_enforced",
            ],
            "owner": "team-release-governance",
            "next_action": (
                "Promote only when all phase evidence and metric floors pass; "
                "otherwise publish the remediation backlog with frozen revision refs."
            ),
        },
        "floor_policy": {key: _json_floor_policy(value) for key, value in FLOOR_POLICY.items()},
        "metric_policy": {
            "rollout_decision_cites_three_metrics": True,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
            "corpus_stub_never_satisfies_production_authority": True,
        },
        "rollback_and_kill_switches": rollback_and_kill_switches(),
        "authority_boundary": _phase_authority_boundary(),
        "pattern_pass": {
            "relevant_patterns": [
                "P01",
                "P02",
                "P03",
                "P04",
                "P05",
                "P09",
                "P10",
                "P12",
                "P15",
            ],
            "target_correct_pattern": (
                "Rollout decision is a release-governance consumer of A-F evidence, "
                "not a producer, closeout, claim, or public projection authority."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": "repo://tests/repo_quality/tools/test_w12g_rollout_decision.py",
            "command_ref": render_command(command),
        },
    }


def rollback_and_kill_switches() -> list[dict[str, str]]:
    """Return the W12 rollout rollback and kill-switch surface."""

    return [
        {
            "flag": "POLISYOS_DATA_REQ_FAMILY_FALLBACK_FROM_HARDCODED",
            "rollback_action": "restore fallback while catalog-derived data rules are repaired",
            "owner": "team-data-requirements",
        },
        {
            "flag": "POLISYOS_SCIENTIST_V2_ENABLED",
            "rollback_action": "disable universal PDC runtime path at entrypoint",
            "owner": "team-runtime-quality",
        },
        {
            "flag": "POLISYOS_PDC_CORPUS_STUB_MODE",
            "rollback_action": "disable governed-pilot corpus-stub validation mode",
            "owner": "team-evaluation",
        },
    ]


def run_w12g_rollout_decision(
    *,
    repo_root: str | Path = REPO_ROOT,
    w12a_report_path: str | Path = DEFAULT_W12A_REPORT,
    w12b_report_path: str | Path = DEFAULT_W12B_REPORT,
    w12c_report_path: str | Path = DEFAULT_W12C_REPORT,
    w12d_report_path: str | Path = DEFAULT_W12D_REPORT,
    w12d_real_report_path: str | Path | None = None,
    w12d_stub_report_path: str | Path | None = None,
    w12e_report_path: str | Path = DEFAULT_W12E_REPORT,
    w12f_report_path: str | Path = DEFAULT_W12F_REPORT,
    requested_posture: str = "governed-pilot",
) -> dict[str, Any]:
    """Load W12.A-F evidence and return the W12.G rollout decision."""

    root = Path(repo_root).resolve()
    return build_w12g_rollout_decision_report(
        w12a_report=_load_optional_json(_resolve(root, Path(w12a_report_path))),
        w12b_report=_load_optional_json(_resolve(root, Path(w12b_report_path))),
        w12c_report=_load_optional_json(_resolve(root, Path(w12c_report_path))),
        w12d_report=_load_optional_json(_resolve(root, Path(w12d_report_path))),
        w12d_real_report=(
            _load_optional_json(_resolve(root, Path(w12d_real_report_path)))
            if w12d_real_report_path
            else None
        ),
        w12d_stub_report=(
            _load_optional_json(_resolve(root, Path(w12d_stub_report_path)))
            if w12d_stub_report_path
            else None
        ),
        w12e_report=_load_optional_json(_resolve(root, Path(w12e_report_path))),
        w12f_report=_load_optional_json(_resolve(root, Path(w12f_report_path))),
        repo_root=root,
        requested_posture=requested_posture,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    if args.write_manifest:
        atomic_write_json(_resolve(repo_root, args.output), build_w12g_manifest())
        return 0

    report = run_w12g_rollout_decision(
        repo_root=repo_root,
        w12a_report_path=args.w12a_report,
        w12b_report_path=args.w12b_report,
        w12c_report_path=args.w12c_report,
        w12d_report_path=args.w12d_report,
        w12d_real_report_path=args.w12d_real_report,
        w12d_stub_report_path=args.w12d_stub_report,
        w12e_report_path=args.w12e_report,
        w12f_report_path=args.w12f_report,
        requested_posture=args.requested_posture,
    )
    atomic_write_json(_resolve(repo_root, args.output), report)
    if report["status"] == "pass" or args.allow_typed_blockers:
        return 0
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--w12a-report", type=Path, default=DEFAULT_W12A_REPORT)
    parser.add_argument("--w12b-report", type=Path, default=DEFAULT_W12B_REPORT)
    parser.add_argument("--w12c-report", type=Path, default=DEFAULT_W12C_REPORT)
    parser.add_argument("--w12d-report", type=Path, default=DEFAULT_W12D_REPORT)
    parser.add_argument("--w12d-real-report", type=Path)
    parser.add_argument("--w12d-stub-report", type=Path)
    parser.add_argument("--w12e-report", type=Path, default=DEFAULT_W12E_REPORT)
    parser.add_argument("--w12f-report", type=Path, default=DEFAULT_W12F_REPORT)
    parser.add_argument("--requested-posture", choices=ROLLOUT_POSTURES, default="governed-pilot")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--allow-typed-blockers", action="store_true")
    return parser


def _required_phase_blockers(
    phase_reports: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for phase_id, report in phase_reports.items():
        if report.get("status") in {"pass", "warning"}:
            continue
        if phase_id == "W12.D" and not _w12d_rollout_blockers(report):
            continue
        phase_environment_blockers = _phase_environment_blockers(phase_id, report)
        if phase_environment_blockers and _only_environment_blockers(report):
            blockers.extend(
                _blocker(
                    code="w12g_environment_blocker",
                    message=(
                        f"{phase_id} is blocked by an environment/cloud dependency, "
                        "so rollout must hold without counting this as semantic closeout failure."
                    ),
                    owner=_phase_owner(phase_id),
                    capability_label="verification_missing",
                    upstream_phase=phase_id,
                    upstream_status=str(report.get("status") or "missing"),
                    environment_blocker_code=str(
                        blocker.get("environment_blocker_code") or blocker.get("code")
                    ),
                    upstream_blocker_code=str(blocker.get("code") or ""),
                )
                for blocker in phase_environment_blockers
            )
            continue
        blockers.append(
            _blocker(
                code="w12g_required_phase_blocked",
                message=f"{phase_id} did not pass, so rollout must hold.",
                owner=_phase_owner(phase_id),
                capability_label="verification_missing",
                upstream_phase=phase_id,
                upstream_status=str(report.get("status") or "missing"),
            )
        )
    return blockers


def _w12d_rollout_blockers(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    explicit = _sequence_of_mappings(report.get("rollout_blockers"))
    if explicit:
        return explicit
    summary = _mapping(report.get("summary"))
    if "rollout_blocker_count" in summary and int(summary.get("rollout_blocker_count") or 0) == 0:
        return []
    return [
        blocker
        for blocker in _sequence_of_mappings(report.get("typed_blockers"))
        if blocker.get("blocks_rollout_posture", True)
    ]


def _held_domain_slices(report: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return _sequence_of_mappings(report.get("held_domain_slices"))


def _w12d_reports_by_mode(
    *,
    primary: Mapping[str, Any],
    real: Mapping[str, Any] | None,
    stub: Mapping[str, Any] | None,
) -> dict[str, Mapping[str, Any]]:
    reports: dict[str, Mapping[str, Any]] = {}
    for report in (primary, real or {}, stub or {}):
        if not report:
            continue
        mode = str(report.get("mode") or "")
        if mode in {"real_producer", "corpus_stub"}:
            reports[mode] = report
    return reports


def _environment_blockers(
    phase_reports: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    blockers: list[Mapping[str, Any]] = []
    for phase_id, report in phase_reports.items():
        blockers.extend(_phase_environment_blockers(phase_id, report))
    return blockers


def _phase_environment_blockers(
    phase_id: str,
    report: Mapping[str, Any],
) -> list[Mapping[str, Any]]:
    blockers: list[Mapping[str, Any]] = []
    for blocker in _sequence_of_mappings(report.get("typed_blockers")):
        if not _is_environment_blocker(blocker):
            continue
        payload = dict(blocker)
        payload.setdefault("upstream_phase", phase_id)
        payload.setdefault("blocks_rollout_posture", True)
        payload.setdefault("counts_as_closeout_honesty_failure", False)
        blockers.append(payload)
    return blockers


def _only_environment_blockers(report: Mapping[str, Any]) -> bool:
    typed_blockers = _sequence_of_mappings(report.get("typed_blockers"))
    return bool(typed_blockers) and all(
        _is_environment_blocker(blocker) for blocker in typed_blockers
    )


def _is_environment_blocker(blocker: Mapping[str, Any]) -> bool:
    return bool(blocker.get("environment_blocker_code")) or blocker.get("code") in {
        "local_validation_environment_blocker",
        "w12f_cloud_lane_evidence_missing",
    }


def _metric_floor_blockers(
    *,
    metrics: Mapping[str, Mapping[str, Any]],
    requested_posture: str,
) -> list[dict[str, Any]]:
    policy = FLOOR_POLICY[requested_posture]
    checks = (
        (
            "closeout_honesty_rate",
            "minimum_closeout_honesty_rate",
            "w12g_closeout_honesty_floor_not_met",
        ),
        (
            "runtime_useful_design_rate",
            "minimum_runtime_useful_design_rate",
            "w12g_runtime_useful_design_floor_not_met",
        ),
        (
            "compilation_truthfulness_rate",
            "minimum_compilation_truthfulness_rate",
            "w12g_compilation_truthfulness_floor_not_met",
        ),
        (
            "useful_design_alignment_rate",
            "minimum_useful_design_alignment_rate",
            "w12g_useful_design_alignment_floor_not_met",
        ),
        (
            "expert_useful_design_ceiling",
            "minimum_expert_useful_design_ceiling",
            "w12g_expert_useful_design_ceiling_floor_not_met",
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
                    message=f"W12.G rollout metric floor not met: {metric_id}.",
                    owner="team-release-governance",
                    capability_label="semantic_test_missing",
                    metric_id=metric_id,
                    floor=float(floor),
                    value=None if value is None else float(value),
                )
            )
    return blockers


def _corpus_stub_boundary_blockers(
    w12d_report: Mapping[str, Any],
    *,
    requested_posture: str,
) -> list[dict[str, Any]]:
    if requested_posture != "production-capable":
        return []
    if w12d_report.get("mode") != "corpus_stub":
        return []
    return [
        _blocker(
            code="w12g_corpus_stub_cannot_satisfy_production_rollout",
            message=(
                "W12.D corpus-stub mode is governed-pilot validation evidence only "
                "and cannot satisfy production rollout authority."
            ),
            owner="team-release-governance",
            capability_label="surface_out_of_scope",
        )
    ]


def _metric_citations(
    *,
    w12a_report: Mapping[str, Any],
    w12b_report: Mapping[str, Any],
    w12c_report: Mapping[str, Any],
    w12d_report: Mapping[str, Any],
    w12d_real_report: Mapping[str, Any],
    w12d_stub_report: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    w12a_summary = _mapping(w12a_report.get("summary"))
    w12a_outcome_metrics = _mapping(w12a_report.get("outcome_metrics"))
    w12a_closeout_honesty = _mapping(w12a_outcome_metrics.get("closeout_honesty"))
    w12b_summary = _mapping(w12b_report.get("summary"))
    w12c_summary = _mapping(w12c_report.get("summary"))
    w12d_summary = _mapping(w12d_report.get("summary"))
    w12d_real_summary = _mapping(w12d_real_report.get("summary"))
    w12d_stub_summary = _mapping(w12d_stub_report.get("summary"))
    return {
        "closeout_honesty_rate": {
            "value": _first_float(
                w12a_summary.get("closeout_honesty_rate"),
                w12a_closeout_honesty.get("rate"),
                w12d_summary.get("closeout_honesty_rate"),
                1.0 if w12a_report.get("status") == "pass" else None,
            ),
            "source_phase": "W12.A",
        },
        "runtime_useful_design_rate": {
            "value": _first_float(
                w12d_real_summary.get("runtime_useful_design_rate"),
                w12d_real_summary.get("useful_design_rate"),
            ),
            "source_phase": "W12.D",
            "mode": "real_producer"
            if w12d_real_report
            else "missing_real_producer",
        },
        "corpus_stub_useful_design_probe_rate": {
            "value": _first_float(
                w12d_stub_summary.get("runtime_useful_design_rate"),
                w12d_stub_summary.get("useful_design_rate"),
            ),
            "source_phase": "W12.D",
            "mode": "corpus_stub" if w12d_stub_report else "missing_corpus_stub",
        },
        "expert_useful_design_ceiling": {
            "value": _first_float(
                w12d_real_summary.get("expert_useful_design_ceiling"),
                w12d_summary.get("expert_useful_design_ceiling"),
                w12c_summary.get("aggregate_expert_useful_design_ceiling"),
            ),
            "source_phase": "W12.C/W12.D",
        },
        "useful_design_alignment_rate": {
            "value": _first_float(
                w12d_real_summary.get("useful_design_alignment_rate")
            ),
            "source_phase": "W12.D",
            "mode": "real_producer"
            if w12d_real_report
            else "missing_real_producer",
        },
        "stub_alignment_probe_rate": {
            "value": _first_float(w12d_stub_summary.get("useful_design_alignment_rate")),
            "source_phase": "W12.D",
            "mode": "corpus_stub" if w12d_stub_report else "missing_corpus_stub",
        },
        "compilation_truthfulness_rate": {
            "value": _first_float(
                w12b_summary.get("aggregate_compilation_truthfulness_rate")
            ),
            "source_phase": "W12.B",
        },
        "critic_ensemble_diversity_jaccard": {
            "value": _first_float(
                w12c_summary.get("aggregate_critic_ensemble_diversity_jaccard")
            ),
            "source_phase": "W12.C",
        },
    }


def _phase_statuses(
    phase_reports: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, str]]:
    return [
        {"phase_id": phase_id, "status": str(report.get("status") or "missing")}
        for phase_id, report in phase_reports.items()
    ]


def _decision(*, requested_posture: str, blockers: Sequence[Mapping[str, Any]]) -> str:
    if blockers:
        return "hold_for_remediation"
    return {
        "research-only": "promote_research_only",
        "governed-pilot": "promote_governed_pilot",
        "production-capable": "promote_production_capable",
    }[requested_posture]


def _remediation_backlog(blockers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "code": str(blocker.get("code")),
            "owner": str(blocker.get("owner") or "team-release-governance"),
            "next_action": _next_action_for_blocker(str(blocker.get("code"))),
        }
        for blocker in blockers
    ]


def _next_action_for_blocker(code: str) -> str:
    if code == "w12g_required_phase_blocked":
        return "Repair the upstream W12 phase and rerun W12.G with frozen evidence refs."
    if code == "w12g_corpus_stub_cannot_satisfy_production_rollout":
        return "Rerun W12.D in real-producer mode before requesting production-capable rollout."
    return "Repair the failed metric floor or authority boundary before rollout."


def _frozen_revision_config(
    *,
    repo_root: Path,
    w12f_report: Mapping[str, Any],
) -> dict[str, Any]:
    frozen = dict(_mapping(w12f_report.get("frozen_revision_config")))
    if not frozen.get("git_revision"):
        frozen["git_revision"] = _git_revision(repo_root)
    frozen.setdefault("feature_flags", {})
    frozen.setdefault("tuned_config_refs", ["w12.runtime.default"])
    return frozen


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


def _phase_owner(phase_id: str) -> str:
    return {
        "W12.A": "team-evaluation",
        "W12.B": "team-evaluation",
        "W12.C": "team-evaluation",
        "W12.D": "team-runtime-quality",
        "W12.E": "team-runtime-quality",
        "W12.F": "team-runtime-platform",
    }.get(phase_id, "team-release-governance")


def _phase_authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": ["w12g_rollout_decision"],
        "may_not_use_for": sorted(FORBIDDEN_ROLLOUT_AUTHORITY),
    }


def _blocker(
    *,
    code: str,
    message: str,
    owner: str,
    capability_label: str,
    upstream_phase: str | None = None,
    upstream_status: str | None = None,
    metric_id: str | None = None,
    floor: float | None = None,
    value: float | None = None,
    environment_blocker_code: str | None = None,
    upstream_blocker_code: str | None = None,
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
        "upstream_phase": upstream_phase,
        "upstream_status": upstream_status,
        "metric_id": metric_id,
        "floor": floor,
        "value": value,
        "environment_blocker_code": environment_blocker_code,
        "upstream_blocker_code": upstream_blocker_code,
    }.items():
        if item is not None:
            payload[key] = item
    return payload


def _json_floor_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    return dict(policy)


def _first_float(*values: object) -> float | None:
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
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
