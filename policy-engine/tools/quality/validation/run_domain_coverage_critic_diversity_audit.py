#!/usr/bin/env python3
"""Run the W12.C domain coverage and critic diversity audit."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_json
from tools.lib.imports import ensure_repo_import_roots
from tools.lib.runner import render_command
from tools.quality.validation import check_critic_ensemble_diversity as w11f_critic
from tools.quality.validation import check_domain_coverage_breadth as w11f_domain

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

SCHEMA_VERSION = "policyos.policy_design_case.w12c.domain_coverage_critic_audit.v1"
MANIFEST_SCHEMA_VERSION = (
    "policyos.policy_design_case.wave12c.domain_coverage_critic_audit_manifest.v1"
)
TOOL_NAME = "quality.validation.run-domain-coverage-critic-diversity-audit"
GENERATED_AT = "2026-05-25T00:00:00Z"
PHASE_ID = "W12.C"
PHASE_NAME = "Domain Coverage And Critic Diversity Audit Run"
DEFAULT_CORPUS_PATH = Path("tests/fixtures/universal-corpus")
DEFAULT_OUTPUT = Path(
    "_build/.tmp/production-quality/w12c_domain_coverage_critic_diversity_audit.json"
)
DEFAULT_DOMAIN_OUTPUT = Path(
    "_build/.tmp/production-quality/w12c_domain_coverage_breadth_report.json"
)
DEFAULT_CRITIC_OUTPUT = Path(
    "_build/.tmp/production-quality/w12c_critic_ensemble_diversity_report.json"
)
DEFAULT_MANIFEST_OUTPUT = Path(
    "architecture/policy_design_case/"
    "wave12c_domain_coverage_critic_diversity_audit_manifest.json"
)
ROLLOUT_POSTURES = ("research-only", "governed-pilot", "production-capable")
AUTHORITY_LEVELS = w11f_domain.AUTHORITY_LEVELS
REQUIRED_CRITIC_ROLES = w11f_critic.REQUIRED_CRITIC_ROLES
GOVERNED_CRITIC_DIVERSITY_FLOOR = w11f_critic.DEFAULT_DIVERSITY_FLOOR

FLOOR_POLICY: Mapping[str, Mapping[str, Any]] = {
    "research-only": {
        "minimum_domain_breadth": None,
        "minimum_useful_design_rate": None,
        "minimum_critic_diversity_jaccard": None,
        "committed_authority_levels": (),
        "minimum_domain_authority_useful_design_count": None,
    },
    "governed-pilot": {
        "minimum_domain_breadth": 4,
        "minimum_useful_design_rate": 0.5,
        "minimum_critic_diversity_jaccard": GOVERNED_CRITIC_DIVERSITY_FLOOR,
        "committed_authority_levels": ("research", "governed"),
        "minimum_domain_authority_useful_design_count": 1,
    },
    "production-capable": {
        "minimum_domain_breadth": 6,
        "minimum_useful_design_rate": 0.7,
        "minimum_critic_diversity_jaccard": GOVERNED_CRITIC_DIVERSITY_FLOOR,
        "committed_authority_levels": ("research", "governed", "production"),
        "minimum_domain_authority_useful_design_count": 1,
    },
}


def build_w12c_domain_coverage_critic_diversity_audit(
    *,
    domain_coverage_report: Mapping[str, Any],
    critic_diversity_report: Mapping[str, Any],
    repo_root: str | Path = REPO_ROOT,
    corpus_ref: str,
    raw_domain_report_ref: str,
    raw_critic_report_ref: str,
    rollout_posture: str,
    generated_at: str = GENERATED_AT,
) -> dict[str, Any]:
    """Decorate W11.F reports with W12.C rollout-floor semantics.

    Args:
        domain_coverage_report: W11.F domain breadth report.
        critic_diversity_report: W11.F critic diversity report.
        repo_root: Product repository root recorded in the report.
        corpus_ref: Repo-relative corpus reference.
        raw_domain_report_ref: Repo-relative raw W11.F domain report reference.
        raw_critic_report_ref: Repo-relative raw W11.F critic report reference.
        rollout_posture: Requested rollout posture.
        generated_at: Deterministic or runtime report timestamp.

    Returns:
        A JSON-serializable W12.C audit report.
    """

    if rollout_posture not in ROLLOUT_POSTURES:
        raise ValueError(f"unknown rollout posture: {rollout_posture}")

    domain_validation = w11f_domain.validate_domain_coverage_breadth_report(
        domain_coverage_report
    )
    critic_validation = w11f_critic.validate_critic_ensemble_diversity_report(
        critic_diversity_report
    )
    domain_summary = _mapping(domain_coverage_report.get("summary"))
    critic_summary = _mapping(critic_diversity_report.get("summary"))
    domain_matrix = _domain_authority_matrix(domain_coverage_report)
    critic_summary_decorated = _critic_diversity_jaccard_summary(
        critic_diversity_report
    )
    floor_evaluation = _evaluate_floors(
        domain_matrix=domain_matrix,
        domain_summary=domain_summary,
        critic_summary=critic_summary,
        rollout_posture=rollout_posture,
    )
    blockers = _typed_domain_coverage_blockers(
        floor_evaluation=floor_evaluation,
        domain_matrix=domain_matrix,
        rollout_posture=rollout_posture,
    )
    held_domain_slices = _held_domain_slices(
        floor_evaluation=floor_evaluation,
        domain_matrix=domain_matrix,
        rollout_posture=rollout_posture,
    )
    generated_warnings = _critic_monoculture_warnings(
        floor_evaluation=floor_evaluation,
        critic_diversity_report=critic_diversity_report,
        rollout_posture=rollout_posture,
    )
    raw_critic_warnings = _sequence_of_mappings(critic_diversity_report.get("warnings"))
    warnings = [*generated_warnings, *raw_critic_warnings]
    rollout_cap = _rollout_cap(
        critic_warning_active=bool(generated_warnings),
        rollout_posture=rollout_posture,
    )
    issues = [
        *_sequence_of_mappings(domain_coverage_report.get("issues")),
        *_sequence_of_mappings(critic_diversity_report.get("issues")),
        *domain_validation["issues"],
        *critic_validation["issues"],
    ]
    status = _overall_status(
        domain_validation_status=str(domain_validation["status"]),
        critic_validation_status=str(critic_validation["status"]),
        domain_status=str(domain_summary.get("status") or "fail"),
        critic_status=str(critic_summary.get("status") or "fail"),
        blockers=blockers,
        warning_active=bool(generated_warnings),
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
        "raw_w11f_domain_coverage_report_ref": raw_domain_report_ref,
        "raw_w11f_critic_diversity_report_ref": raw_critic_report_ref,
        "status": status,
        "summary": {
            "case_count": int(domain_summary.get("case_count") or 0),
            "committed_domain_count": int(domain_summary.get("committed_domain_count") or 0),
            "domain_coverage_breadth": int(domain_summary.get("domain_coverage_breadth") or 0),
            # ``aggregate_expert_useful_design_ceiling`` and the per-authority
            # ceilings come from W11.F over the corpus annotations. They
            # represent what experts say the universal compiler SHOULD be able
            # to deliver. The runtime achievement is reported separately by
            # W12.D as ``runtime_useful_design_rate``. The W12.G rollout
            # decision compares both against the rollout-posture floors. The
            # ``floor_evaluation`` key still uses the legacy internal name
            # while ``aggregate_expert_useful_design_ceiling`` is the
            # consumer-facing alias.
            "aggregate_expert_useful_design_ceiling": floor_evaluation[
                "aggregate_useful_design_rate"
            ],
            "per_authority_expert_useful_design_ceiling": _mapping_of_mappings(
                domain_summary.get("per_authority_expert_useful_design_ceiling")
            ),
            "aggregate_critic_ensemble_diversity_jaccard": (
                critic_summary_decorated["aggregate_critic_ensemble_diversity_jaccard"]
            ),
        },
        "floor_policy": _json_floor_policy(FLOOR_POLICY[rollout_posture]),
        "floor_evaluation": floor_evaluation,
        "domain_authority_useful_design_matrix": domain_matrix,
        "held_domain_slices": held_domain_slices,
        "domain_coverage_breadth_summary": {
            "domain_coverage_breadth": int(domain_summary.get("domain_coverage_breadth") or 0),
            "committed_domain_count": int(domain_summary.get("committed_domain_count") or 0),
            "non_trivial_domain_ids": list(
                _sequence(domain_summary.get("non_trivial_domain_ids"))
            ),
            "domains": _mapping_of_mappings(domain_coverage_report.get("domains")),
        },
        "critic_diversity_jaccard_summary": critic_summary_decorated,
        "typed_domain_coverage_blockers": blockers,
        "warnings": warnings,
        "rollout_cap": rollout_cap,
        "metric_policy": {
            "typed_blockers_count_as_useful_design": False,
            "accepted_deficits_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
            "critic_monoculture_caps_rollout": "governed-pilot-or-below",
            "domain_coverage_and_critic_diversity_are_separate_metrics": True,
        },
        "issues": issues,
        "w11f_validation": {
            "domain_coverage": domain_validation,
            "critic_diversity": critic_validation,
        },
    }


def build_w12c_manifest() -> dict[str, Any]:
    """Build the deterministic W12.C command and metric contract manifest."""

    command = (
        "uv",
        "run",
        "python",
        "tools/quality/validation/run_domain_coverage_critic_diversity_audit.py",
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
            "#w12c-domain-coverage-and-critic-diversity-audit-run"
        ),
        "tool_ref": (
            "repo://tools/quality/validation/"
            "run_domain_coverage_critic_diversity_audit.py"
        ),
        "w11f_tool_refs": [
            "repo://tools/quality/validation/check_domain_coverage_breadth.py",
            "repo://tools/quality/validation/check_critic_ensemble_diversity.py",
        ],
        "command_contract": {
            "command": render_command(command),
            "output_refs": [
                DEFAULT_OUTPUT.as_posix(),
                DEFAULT_DOMAIN_OUTPUT.as_posix(),
                DEFAULT_CRITIC_OUTPUT.as_posix(),
            ],
            "owner": "team-evaluation",
            "next_action": (
                "Repair zero-useful committed domain slices or critic monoculture "
                "before declaring production-capable rollout posture."
            ),
        },
        "floor_policy": {
            posture: _json_floor_policy(policy)
            for posture, policy in FLOOR_POLICY.items()
        },
        "metric_policy": {
            "domain_authority_useful_design_matrix_required": True,
            "critic_diversity_jaccard_summary_required": True,
            "typed_blockers_count_as_useful_design": False,
            "typed_blockers_are_closeout_honesty_failures": False,
            "critic_monoculture_caps_rollout": "governed-pilot-or-below",
        },
        "pattern_pass": {
            "relevant_patterns": ["P01", "P03", "P05", "P10", "P13", "P15"],
            "target_correct_pattern": (
                "W12.C consumes W11.F measurement reports, exposes domain x "
                "authority useful-design coverage, and treats critic monoculture "
                "as a rollout cap warning rather than useful-design evidence."
            ),
            "missing_capability_labels": [],
        },
        "validation": {
            "test_ref": (
                "repo://tests/repo_quality/tools/"
                "test_w12c_domain_coverage_critic_diversity_audit.py"
            ),
            "command_ref": render_command(command),
        },
    }


def run_w12c_domain_coverage_critic_diversity_audit(
    *,
    repo_root: str | Path = REPO_ROOT,
    corpus_path: str | Path = DEFAULT_CORPUS_PATH,
    critic_input_path: str | Path | None = None,
    w12d_report_path: str | Path | None = None,
    rollout_posture: str = "research-only",
    domain_coverage_report: str | Path | None = None,
    critic_diversity_report: str | Path | None = None,
    raw_domain_report_output: str | Path = DEFAULT_DOMAIN_OUTPUT,
    raw_critic_report_output: str | Path = DEFAULT_CRITIC_OUTPUT,
) -> dict[str, Any]:
    """Run W11.F tools if needed and return the W12.C decorated audit."""

    root = Path(repo_root).resolve()
    corpus = _resolve(root, Path(corpus_path))
    critic_input = _resolve(root, Path(critic_input_path or corpus_path))

    if domain_coverage_report is None:
        domain_payload = w11f_domain.build_domain_coverage_breadth_report(
            repo_root=root,
            corpus_path=corpus,
        )
        domain_output = _resolve(root, Path(raw_domain_report_output))
        atomic_write_json(domain_output, domain_payload)
        domain_ref = f"repo://{_repo_relative(root, domain_output)}"
    else:
        domain_path = _resolve(root, Path(domain_coverage_report))
        domain_payload = json.loads(domain_path.read_text(encoding="utf-8"))
        domain_ref = f"repo://{_repo_relative(root, domain_path)}"

    if critic_diversity_report is None:
        if w12d_report_path is not None:
            w12d_path = _resolve(root, Path(w12d_report_path))
            critic_cases, critic_load_issues = _critic_cases_from_w12d_report(
                repo_root=root,
                w12d_report_path=w12d_path,
            )
            critic_payload = w11f_critic.build_critic_ensemble_diversity_report_from_cases(
                repo_root=root,
                input_path=w12d_path,
                cases=critic_cases,
                load_issues=critic_load_issues,
            )
        else:
            critic_payload = w11f_critic.build_critic_ensemble_diversity_report(
                repo_root=root,
                input_path=critic_input,
            )
        critic_output = _resolve(root, Path(raw_critic_report_output))
        atomic_write_json(critic_output, critic_payload)
        critic_ref = f"repo://{_repo_relative(root, critic_output)}"
    else:
        critic_path = _resolve(root, Path(critic_diversity_report))
        critic_payload = json.loads(critic_path.read_text(encoding="utf-8"))
        critic_ref = f"repo://{_repo_relative(root, critic_path)}"

    return build_w12c_domain_coverage_critic_diversity_audit(
        domain_coverage_report=domain_payload,
        critic_diversity_report=critic_payload,
        repo_root=root,
        corpus_ref=f"repo://{_repo_relative(root, corpus)}",
        raw_domain_report_ref=domain_ref,
        raw_critic_report_ref=critic_ref,
        rollout_posture=rollout_posture,
        generated_at=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    )


def write_manifest(repo_root: Path, output: Path = DEFAULT_MANIFEST_OUTPUT) -> dict[str, Any]:
    """Write the deterministic W12.C manifest."""

    payload = build_w12c_manifest()
    atomic_write_json(_resolve(repo_root, output), payload)
    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build the W12.C audit parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument(
        "--critic-input",
        type=Path,
        help="Optional W11.F critic input path; defaults to --corpus.",
    )
    parser.add_argument(
        "--w12d-report",
        type=Path,
        help=(
            "Optional W12.D runtime report whose per-case critic_ensemble_report_ref "
            "artifacts should be used as the critic diversity input."
        ),
    )
    parser.add_argument("--domain-coverage-report", type=Path)
    parser.add_argument("--critic-diversity-report", type=Path)
    parser.add_argument("--raw-domain-report-output", type=Path, default=DEFAULT_DOMAIN_OUTPUT)
    parser.add_argument("--raw-critic-report-output", type=Path, default=DEFAULT_CRITIC_OUTPUT)
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
        help="Return zero when W12.C finds typed domain-coverage blockers.",
    )
    parser.add_argument(
        "--require-passing",
        action="store_true",
        help="Return non-zero for warning or blocked W12.C reports.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for the W12.C audit."""

    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.repo_root).resolve()

    if args.write_manifest:
        manifest_output = args.manifest_output or DEFAULT_MANIFEST_OUTPUT
        write_manifest(root, manifest_output)

    report = run_w12c_domain_coverage_critic_diversity_audit(
        repo_root=root,
        corpus_path=args.corpus,
        critic_input_path=args.critic_input,
        w12d_report_path=args.w12d_report,
        rollout_posture=args.rollout_posture,
        domain_coverage_report=args.domain_coverage_report,
        critic_diversity_report=args.critic_diversity_report,
        raw_domain_report_output=args.raw_domain_report_output,
        raw_critic_report_output=args.raw_critic_report_output,
    )
    output = _resolve(root, args.output)
    atomic_write_json(output, report)

    json.dump(report, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")

    if report["status"] == "fail":
        return 1
    if report["status"] == "blocked" and not args.allow_typed_blockers:
        return 2
    if report["status"] == "warning" and args.require_passing:
        return 2
    return 0


def _domain_authority_matrix(
    domain_coverage_report: Mapping[str, Any],
) -> dict[str, dict[str, dict[str, Any]]]:
    domain_rows = _mapping_of_mappings(domain_coverage_report.get("domains"))
    domains = sorted(domain_rows)
    if not domains:
        domains = sorted(
            {
                str(case.get("domain") or "unknown")
                for case in _sequence_of_mappings(domain_coverage_report.get("cases"))
            }
        )

    matrix: dict[str, dict[str, dict[str, Any]]] = {
        domain: {
            authority_level: _empty_matrix_cell(
                domain=domain,
                authority_level=authority_level,
                domain_row=domain_rows.get(domain, {}),
            )
            for authority_level in AUTHORITY_LEVELS
        }
        for domain in domains
    }
    for case in _sequence_of_mappings(domain_coverage_report.get("cases")):
        case_id = str(case.get("case_id") or "unknown-case")
        domain = str(case.get("domain") or "unknown")
        if domain not in matrix:
            matrix[domain] = {
                authority_level: _empty_matrix_cell(
                    domain=domain,
                    authority_level=authority_level,
                    domain_row=domain_rows.get(domain, {}),
                )
                for authority_level in AUTHORITY_LEVELS
            }
        for row in _sequence_of_mappings(case.get("authority_useful_design")):
            authority_level = _normalized_token(row.get("authority_level") or "research")
            cell = matrix[domain].setdefault(
                authority_level,
                _empty_matrix_cell(
                    domain=domain,
                    authority_level=authority_level,
                    domain_row=domain_rows.get(domain, {}),
                ),
            )
            cell["case_count"] += 1
            if row.get("counts_toward_useful_design"):
                cell["useful_design_count"] += 1
                cell["useful_case_ids"].append(case_id)
            else:
                cell["non_useful_case_ids"].append(case_id)
                labels = {
                    _normalized_token(label)
                    for label in _sequence(row.get("adjudication_labels"))
                    if _normalized_token(label)
                }
                cell["adjudication_labels"] = sorted(
                    {*cell["adjudication_labels"], *labels}
                )
                if labels and labels <= {"false_pass", "fabricated_unverifiable"}:
                    cell["negative_control_case_ids"].append(case_id)
                blocker_code = row.get("blocker_code")
                if blocker_code:
                    cell["blocker_codes"] = sorted(
                        {*cell["blocker_codes"], str(blocker_code)}
                    )

    for rows in matrix.values():
        for cell in rows.values():
            cell["non_useful_count"] = cell["case_count"] - cell["useful_design_count"]
            cell["useful_design_rate"] = _rate(
                int(cell["useful_design_count"]),
                int(cell["case_count"]),
            )
            cell["useful_case_ids"] = sorted(dict.fromkeys(cell["useful_case_ids"]))
            cell["non_useful_case_ids"] = sorted(
                dict.fromkeys(cell["non_useful_case_ids"])
            )
            cell["blocker_codes"] = sorted(dict.fromkeys(cell["blocker_codes"]))
            cell["negative_control_case_ids"] = sorted(
                dict.fromkeys(cell["negative_control_case_ids"])
            )
            if (
                cell["case_count"] > 0
                and cell["useful_design_count"] == 0
                and len(cell["negative_control_case_ids"]) == cell["case_count"]
            ):
                cell["slice_classification"] = "negative_control_only"
            elif cell["useful_design_count"] > 0:
                cell["slice_classification"] = "positive_committed"
            elif cell["case_count"] > 0:
                cell["slice_classification"] = "non_useful_committed"
            else:
                cell["slice_classification"] = "empty"
    return {domain: matrix[domain] for domain in sorted(matrix)}


def _empty_matrix_cell(
    *,
    domain: str,
    authority_level: str,
    domain_row: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "domain": domain,
        "authority_level": authority_level,
        "case_count": 0,
        "useful_design_count": 0,
        "non_useful_count": 0,
        "useful_design_rate": 0.0,
        "useful_case_ids": [],
        "non_useful_case_ids": [],
        "blocker_codes": [],
        "adjudication_labels": [],
        "negative_control_case_ids": [],
        "slice_classification": "empty",
        "domain_non_trivial_graph": bool(domain_row.get("non_trivial_graph")),
        "typed_blockers_count_as_useful_design": False,
        "accepted_deficits_count_as_useful_design": False,
    }


def _critic_diversity_jaccard_summary(
    critic_diversity_report: Mapping[str, Any],
) -> dict[str, Any]:
    summary = _mapping(critic_diversity_report.get("summary"))
    by_domain: dict[str, list[Mapping[str, Any]]] = {}
    for case in _sequence_of_mappings(critic_diversity_report.get("cases")):
        by_domain.setdefault(str(case.get("domain") or "unknown"), []).append(case)
    return {
        "aggregate_critic_ensemble_diversity_jaccard": _float_or_zero(
            summary.get("aggregate_critic_ensemble_diversity_jaccard")
        ),
        "diversity_floor": _float_or_zero(summary.get("diversity_floor")),
        "cases_below_diversity_floor": int(summary.get("cases_below_diversity_floor") or 0),
        "cases_with_monoculture_warning": int(
            summary.get("cases_with_monoculture_warning") or 0
        ),
        "required_critic_roles": list(_sequence(summary.get("required_critic_roles"))),
        "by_domain": {
            domain: _critic_domain_summary(cases)
            for domain, cases in sorted(by_domain.items())
        },
        "cases": [
            {
                "case_id": case.get("case_id"),
                "domain": case.get("domain"),
                "authority_level": case.get("authority_level"),
                "critic_count": case.get("critic_count"),
                "pairwise_jaccard_similarity": _float_or_zero(
                    case.get("pairwise_jaccard_similarity")
                ),
                "critic_ensemble_diversity_jaccard": _float_or_zero(
                    case.get("critic_ensemble_diversity_jaccard")
                ),
                "below_diversity_floor": bool(case.get("below_diversity_floor")),
                "missing_critic_roles": list(_sequence(case.get("missing_critic_roles"))),
            }
            for case in _sequence_of_mappings(critic_diversity_report.get("cases"))
        ],
    }


def _critic_domain_summary(cases: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    diversities = [
        _float_or_zero(case.get("critic_ensemble_diversity_jaccard"))
        for case in cases
    ]
    return {
        "case_count": len(cases),
        "aggregate_critic_ensemble_diversity_jaccard": _rate_sum(diversities),
        "cases_below_diversity_floor": sum(
            1 for case in cases if case.get("below_diversity_floor")
        ),
        "cases_with_monoculture_warning": sum(
            1
            for case in cases
            if any(
                warning.get("code") == "critic_monoculture"
                for warning in _sequence_of_mappings(case.get("warnings"))
            )
        ),
    }


def _evaluate_floors(
    *,
    domain_matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
    domain_summary: Mapping[str, Any],
    critic_summary: Mapping[str, Any],
    rollout_posture: str,
) -> dict[str, Any]:
    policy = FLOOR_POLICY[rollout_posture]
    committed_levels = list(policy["committed_authority_levels"])
    committed_domains = sorted(domain_matrix)
    below_slices: list[str] = []
    held_slices: list[str] = []
    for domain in committed_domains:
        for authority_level in committed_levels:
            cell = _mapping(domain_matrix.get(domain, {}).get(authority_level))
            if cell.get("slice_classification") == "negative_control_only":
                held_slices.append(f"{domain}:{authority_level}")
                continue
            if int(cell.get("useful_design_count") or 0) < int(
                policy["minimum_domain_authority_useful_design_count"] or 0
            ):
                below_slices.append(f"{domain}:{authority_level}")

    aggregate_rate = _aggregate_useful_design_rate(
        domain_matrix=domain_matrix,
        domains=committed_domains,
        authority_levels=committed_levels,
        held_slices=held_slices,
    )
    minimum_rate = policy["minimum_useful_design_rate"]
    minimum_breadth = policy["minimum_domain_breadth"]
    minimum_critic_diversity = policy["minimum_critic_diversity_jaccard"]
    breadth = int(domain_summary.get("domain_coverage_breadth") or 0)
    critic_diversity = _float_or_zero(
        critic_summary.get("aggregate_critic_ensemble_diversity_jaccard")
    )
    critic_cases_below_floor = int(critic_summary.get("cases_below_diversity_floor") or 0)
    floor_required = any(
        value is not None
        for value in (minimum_rate, minimum_breadth, minimum_critic_diversity)
    )
    breadth_below_floor = minimum_breadth is not None and breadth < int(minimum_breadth)
    useful_rate_below_floor = (
        minimum_rate is not None and aggregate_rate < float(minimum_rate)
    )
    critic_below_floor = (
        minimum_critic_diversity is not None
        and (
            critic_diversity < float(minimum_critic_diversity)
            or critic_cases_below_floor > 0
        )
    )
    blocker_floor_not_met = bool(
        below_slices or breadth_below_floor or useful_rate_below_floor
    )
    status = (
        "not_required"
        if not floor_required
        else "not_met"
        if blocker_floor_not_met
        else "warning"
        if critic_below_floor
        else "met"
    )
    return {
        "rollout_posture": rollout_posture,
        "status": status,
        "committed_domain_ids": committed_domains,
        "committed_authority_levels": committed_levels,
        "minimum_domain_authority_useful_design_count": (
            policy["minimum_domain_authority_useful_design_count"]
        ),
        "minimum_domain_breadth": minimum_breadth,
        "actual_domain_coverage_breadth": breadth,
        "domain_breadth_below_floor": breadth_below_floor,
        "minimum_useful_design_rate": minimum_rate,
        "aggregate_useful_design_rate": aggregate_rate,
        "useful_design_rate_below_floor": useful_rate_below_floor,
        "below_floor_domain_authority_slices": below_slices,
        "held_domain_authority_slices": held_slices,
        "minimum_critic_diversity_jaccard": minimum_critic_diversity,
        "aggregate_critic_ensemble_diversity_jaccard": critic_diversity,
        "critic_cases_below_diversity_floor": critic_cases_below_floor,
        "critic_diversity_below_floor": critic_below_floor,
    }


def _aggregate_useful_design_rate(
    *,
    domain_matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
    domains: Sequence[str],
    authority_levels: Sequence[str],
    held_slices: Sequence[str] = (),
) -> float:
    useful = 0
    total = 0
    held = set(held_slices)
    for domain in domains:
        for authority_level in authority_levels:
            if f"{domain}:{authority_level}" in held:
                continue
            cell = _mapping(domain_matrix.get(domain, {}).get(authority_level))
            useful += int(cell.get("useful_design_count") or 0)
            total += int(cell.get("case_count") or 0)
    return _rate(useful, total)


def _typed_domain_coverage_blockers(
    *,
    floor_evaluation: Mapping[str, Any],
    domain_matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
    rollout_posture: str,
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []
    for slice_ref in _sequence(floor_evaluation.get("below_floor_domain_authority_slices")):
        domain, authority_level = str(slice_ref).split(":", 1)
        cell = _mapping(domain_matrix.get(domain, {}).get(authority_level))
        blockers.append(
            _domain_blocker(
                code="domain_coverage_zero_useful_design",
                domain=domain,
                authority_level=authority_level,
                rollout_posture=rollout_posture,
                actual_score=float(cell.get("useful_design_count") or 0),
                floor=float(
                    floor_evaluation.get("minimum_domain_authority_useful_design_count")
                    or 0
                ),
                next_action=(
                    "Repair the case outcome, add a useful-design corpus case for "
                    "this committed domain slice, or mark the slice research-only/held."
                ),
            )
        )
    if floor_evaluation.get("domain_breadth_below_floor"):
        blockers.append(
            _domain_blocker(
                code="domain_coverage_breadth_below_floor",
                domain=None,
                authority_level=None,
                rollout_posture=rollout_posture,
                actual_score=float(floor_evaluation.get("actual_domain_coverage_breadth") or 0),
                floor=float(floor_evaluation.get("minimum_domain_breadth") or 0),
                next_action=(
                    "Repair W6.C graph coverage or hold uncovered domains before "
                    "claiming the requested rollout posture."
                ),
            )
        )
    if floor_evaluation.get("useful_design_rate_below_floor"):
        blockers.append(
            _domain_blocker(
                code="domain_coverage_useful_design_rate_below_floor",
                domain=None,
                authority_level=None,
                rollout_posture=rollout_posture,
                actual_score=float(floor_evaluation.get("aggregate_useful_design_rate") or 0),
                floor=float(floor_evaluation.get("minimum_useful_design_rate") or 0),
                next_action=(
                    "Repair non-useful outcomes before using domain coverage as "
                    "capability evidence."
                ),
            )
        )
    return blockers


def _held_domain_slices(
    *,
    floor_evaluation: Mapping[str, Any],
    domain_matrix: Mapping[str, Mapping[str, Mapping[str, Any]]],
    rollout_posture: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for slice_ref in _sequence(floor_evaluation.get("held_domain_authority_slices")):
        domain, authority_level = str(slice_ref).split(":", 1)
        cell = _mapping(domain_matrix.get(domain, {}).get(authority_level))
        rows.append(
            {
                "slice_ref": slice_ref,
                "domain": domain,
                "authority_level": authority_level,
                "rollout_posture": rollout_posture,
                "classification": "negative_control_only",
                "case_count": int(cell.get("case_count") or 0),
                "negative_control_case_ids": list(
                    _sequence(cell.get("negative_control_case_ids"))
                ),
                "blocks_governed_pilot": False,
                "blocks_production_capable": True,
                "counts_as_useful_design": False,
                "counts_as_closeout_honesty_failure": False,
                "next_action": (
                    "Add a positive useful-design case for this domain slice or "
                    "explicitly scope it out before production-capable rollout."
                ),
            }
        )
    return rows


def _domain_blocker(
    *,
    code: str,
    domain: str | None,
    authority_level: str | None,
    rollout_posture: str,
    actual_score: float,
    floor: float,
    next_action: str,
) -> dict[str, Any]:
    parts = ["w12c", domain or "aggregate", authority_level or "all", code]
    return {
        "blocker_id": "_".join(_slug(part) for part in parts),
        "code": code,
        "blocker_type": "typed_domain_coverage_blocker",
        "severity": "blocker",
        "phase_id": PHASE_ID,
        "owner": "team-evaluation",
        "case_id": None,
        "domain": domain,
        "authority_level": authority_level,
        "rollout_posture": rollout_posture,
        "actual_score": actual_score,
        "floor": floor,
        "message": (
            "Domain coverage/useful-design evidence is below the rollout-posture "
            "floor. This typed blocker is diagnostic evidence, not useful design."
        ),
        "next_action": next_action,
        "blocks_rollout_posture": True,
        "counts_as_useful_design": False,
        "counts_as_closeout_honesty_failure": False,
        "counts_as_closeout_honesty": False,
    }


def _critic_monoculture_warnings(
    *,
    floor_evaluation: Mapping[str, Any],
    critic_diversity_report: Mapping[str, Any],
    rollout_posture: str,
) -> list[dict[str, Any]]:
    if not floor_evaluation.get("critic_diversity_below_floor"):
        return []
    below_case_ids = [
        str(case.get("case_id"))
        for case in _sequence_of_mappings(critic_diversity_report.get("cases"))
        if case.get("below_diversity_floor")
    ]
    return [
        {
            "warning_id": "w12c_critic_monoculture_rollout_cap",
            "code": "critic_monoculture",
            "severity": "warn",
            "phase_id": PHASE_ID,
            "owner": "team-evaluation",
            "rollout_posture": rollout_posture,
            "rollout_cap": "governed-pilot-or-below",
            "maximum_posture": "governed-pilot",
            "requested_posture_allowed": _posture_rank(rollout_posture)
            <= _posture_rank("governed-pilot"),
            "actual_score": floor_evaluation[
                "aggregate_critic_ensemble_diversity_jaccard"
            ],
            "floor": floor_evaluation["minimum_critic_diversity_jaccard"],
            "case_ids_below_floor": below_case_ids,
            "message": (
                "Critic ensemble diversity is below the W11.F floor; rollout is "
                "capped at governed pilot or below."
            ),
            "next_action": (
                "Repair critic role bases or W6.E report inputs before using the "
                "ensemble as production-capable rollout evidence."
            ),
            "counts_as_useful_design": False,
            "counts_as_closeout_honesty_failure": False,
        }
    ]


def _rollout_cap(*, critic_warning_active: bool, rollout_posture: str) -> dict[str, Any]:
    maximum = "governed-pilot" if critic_warning_active else "production-capable"
    return {
        "maximum_posture": maximum,
        "reason": "critic_monoculture" if critic_warning_active else None,
        "requested_posture": rollout_posture,
        "requested_posture_allowed": _posture_rank(rollout_posture)
        <= _posture_rank(maximum),
    }


def _overall_status(
    *,
    domain_validation_status: str,
    critic_validation_status: str,
    domain_status: str,
    critic_status: str,
    blockers: Sequence[Mapping[str, Any]],
    warning_active: bool,
) -> str:
    if (
        domain_validation_status == "fail"
        or critic_validation_status == "fail"
        or domain_status == "fail"
        or critic_status == "fail"
    ):
        return "fail"
    if blockers:
        return "blocked"
    if warning_active:
        return "warning"
    return "pass"


def _critic_cases_from_w12d_report(
    *,
    repo_root: Path,
    w12d_report_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    payload = _load_json(w12d_report_path)
    cases: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    for case in _sequence_of_mappings(payload.get("cases")):
        case_id = str(case.get("case_id") or "unknown-case")
        llm = _mapping(case.get("llm_universal_compilation"))
        ref = str(
            llm.get("critic_ensemble_report_ref")
            or llm.get("critic_ensemble_report_artifact_ref")
            or case.get("critic_ensemble_report_ref")
            or ""
        )
        if not ref:
            issues.append(
                _issue(
                    code="w12c_runtime_critic_report_ref_missing",
                    message="W12.D case is missing critic_ensemble_report_ref.",
                    severity="warn",
                    case_id=case_id,
                )
            )
            continue
        critic_path = _resolve_artifact_ref(repo_root, ref)
        if not critic_path.exists():
            issues.append(
                _issue(
                    code="w12c_runtime_critic_report_missing",
                    message=f"W12.D critic report artifact does not exist: {ref}",
                    severity="warn",
                    case_id=case_id,
                )
            )
            continue
        critic_payload = _load_json(critic_path)
        critic_payload.setdefault("case_id", case_id)
        critic_payload.setdefault("domain", case.get("domain"))
        critic_payload.setdefault("authority_level", case.get("authority_level"))
        critic_payload["_source_path"] = str(critic_path)
        cases.append(critic_payload)
    return cases, issues


def _resolve_artifact_ref(repo_root: Path, ref: str) -> Path:
    if ref.startswith("repo://"):
        value = ref.removeprefix("repo://")
        candidate = Path(value)
        return candidate if candidate.is_absolute() else repo_root / candidate
    candidate = Path(ref)
    return candidate if candidate.is_absolute() else repo_root / candidate


def _issue(
    code: str,
    message: str,
    *,
    severity: str,
    **extra: object,
) -> dict[str, Any]:
    payload = {"code": code, "message": message, "severity": severity}
    payload.update({key: value for key, value in extra.items() if value is not None})
    return payload


def _json_floor_policy(policy: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in policy.items()
    }


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return dict(payload) if isinstance(payload, Mapping) else {"payload": payload}


def _repo_relative(repo_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_of_mappings(value: object) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping):
        return {}
    return {
        str(key): dict(row)
        for key, row in sorted(value.items(), key=lambda item: str(item[0]))
        if isinstance(row, Mapping)
    }


def _sequence(value: object) -> tuple[Any, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    if isinstance(value, Sequence):
        return tuple(value)
    return ()


def _sequence_of_mappings(value: object) -> tuple[Mapping[str, Any], ...]:
    return tuple(row for row in _sequence(value) if isinstance(row, Mapping))


def _float_or_zero(value: object) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _rate_sum(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)


def _posture_rank(posture: str) -> int:
    return ROLLOUT_POSTURES.index(posture)


def _normalized_token(value: object) -> str:
    text = str(value or "").strip().casefold().replace("::", ":")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_.:/-]+", "_", text)
    return text.strip("_")


def _slug(value: object) -> str:
    slug = _normalized_token(value).replace("/", "_").replace(":", "_")
    return slug or "none"


if __name__ == "__main__":
    raise SystemExit(main())
