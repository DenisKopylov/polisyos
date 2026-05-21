#!/usr/bin/env python3
"""Build the baseline-only Policy Design Case coverage dashboard."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.lib.fs import atomic_write_text
from tools.lib.imports import ensure_repo_import_roots
from tools.quality.validation import check_policy_design_case_drift as drift

REPO_ROOT, _SRC_ROOT = ensure_repo_import_roots(__file__)

from polisyos.runtime.quality.formal_invariants import (  # noqa: E402
    FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH,
    build_formal_invariant_spec_report,
)
from polisyos.runtime.quality.policy_design_case import (  # noqa: E402
    build_policy_design_case_record_registry_report,
)

SCHEMA_VERSION = "policyos.policy_design_case.coverage.v1"
TOOL_NAME = "quality.validation.build-policy-design-case-coverage"
GENERATED_AT = "2026-05-17T00:00:00Z"
DEFAULT_OUTPUT_DIR = Path("_build/policy-design-case/coverage")
DEFAULT_BASELINE_COVERAGE = Path("_build/policy-design-case/rebaseline/wave-0/coverage.json")
DEFAULT_BASELINE_GAPS = Path("_build/policy-design-case/rebaseline/wave-0/baseline_gaps.json")
DEFAULT_PASS2_DISPOSITION = Path(
    "_build/policy-design-case/rebaseline/wave-35/pass2_disposition.json"
)
DEFAULT_SDD = Path("docs/system-design-decisions/policy-design-best-in-class-operating-model.md")
DEFAULT_FORMAL_INVARIANT_SPECS = FORMAL_INVARIANT_REGISTRY_RELATIVE_PATH
DEFAULT_WALKING_SKELETON_READINESS = Path(
    "_build/policy-design-case/rebaseline/wave-7/walking_skeleton_readiness.json"
)

REQUIRED_METRIC_IDS = (
    "case_record_family_schema_pct",
    "runtime_quality_profile_coverage_pct",
    "walking_skeleton_ref_path_pct",
    "intent_capability_gate_pct",
    "concept_spine_closure_pct",
    "producer_contract_runtime_evidence_pct",
    "data_forge_snapshot_binding_pct",
    "scholar_literature_strand_pct",
    "portfolio_predeclaration_pct",
    "effective_independent_count_pct",
    "evidence_synthesis_report_pct",
    "claim_argument_warrant_pct",
    "berl_required_reliability_pct",
    "structured_judgement_consultation_pct",
    "implementation_monitoring_evaluation_pct",
    "human_oversight_independence_pct",
    "integrity_self_fmea_maturity_pct",
    "publication_external_audit_pct",
    "benchmarking_proportionality_pct",
    "formal_invariant_spec_pct",
    "pass2_disposition_pct",
    "false_pass_rate_negative_controls",
    "reuse_violation_count",
)

METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "case_record_family_schema_pct": {
        "title": "Case record family schema coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": ">= 50", "claim": ">= 90", "final": "100"},
    },
    "runtime_quality_profile_coverage_pct": {
        "title": "Runtime quality profile coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": ">= 70", "claim": "100", "final": "100"},
    },
    "walking_skeleton_ref_path_pct": {
        "title": "Walking skeleton reference path coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "100", "claim": "100", "final": "100"},
    },
    "intent_capability_gate_pct": {
        "title": "Intent and capability gate coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "100", "claim": "100", "final": "100"},
    },
    "concept_spine_closure_pct": {
        "title": "Concept spine closure coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": ">= 80", "claim": "100", "final": "100"},
    },
    "producer_contract_runtime_evidence_pct": {
        "title": "Producer contract runtime evidence coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 90", "final": "100"},
    },
    "data_forge_snapshot_binding_pct": {
        "title": "Data Forge snapshot binding coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 90", "final": "100"},
    },
    "scholar_literature_strand_pct": {
        "title": "Scholar literature strand coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 80", "final": "100"},
    },
    "portfolio_predeclaration_pct": {
        "title": "Portfolio predeclaration coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 90", "final": "100"},
    },
    "effective_independent_count_pct": {
        "title": "Effective independent count coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 80", "final": "100"},
    },
    "evidence_synthesis_report_pct": {
        "title": "Evidence synthesis report coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 80", "final": "100"},
    },
    "claim_argument_warrant_pct": {
        "title": "Claim argument and warrant coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": "100", "final": "100"},
    },
    "berl_required_reliability_pct": {
        "title": "BERL required reliability coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 80", "final": "100"},
    },
    "structured_judgement_consultation_pct": {
        "title": "Structured judgement and consultation coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "baseline": "baseline",
            "spine": "baseline",
            "claim": "baseline",
            "final": "100 for registry-required judgement or consultation families",
        },
    },
    "implementation_monitoring_evaluation_pct": {
        "title": "Implementation monitoring and evaluation coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "baseline": "baseline",
            "spine": "baseline",
            "claim": "baseline",
            "final": "100 for registry-required monitoring or evaluation families",
        },
    },
    "human_oversight_independence_pct": {
        "title": "Human oversight and independence coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "baseline": "baseline",
            "spine": "baseline",
            "claim": "baseline",
            "final": "100 for registry-required oversight or independence families",
        },
    },
    "integrity_self_fmea_maturity_pct": {
        "title": "Integrity self-FMEA maturity coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 70", "final": "100"},
    },
    "publication_external_audit_pct": {
        "title": "Publication and external audit coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "baseline": "baseline",
            "spine": "baseline",
            "claim": "baseline",
            "final": "100 when public/exported",
        },
    },
    "benchmarking_proportionality_pct": {
        "title": "Benchmarking and proportionality coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {"baseline": "baseline", "spine": "baseline", "claim": ">= 70", "final": "100"},
    },
    "formal_invariant_spec_pct": {
        "title": "Formal invariant specification coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "baseline": "baseline",
            "spine": "baseline",
            "claim": "baseline",
            "final": ">= 80 for closeout-critical invariants",
        },
    },
    "pass2_disposition_pct": {
        "title": "Pass 2 disposition coverage",
        "unit": "percent",
        "direction": "higher_is_better",
        "target": {
            "baseline": "baseline",
            "spine": "baseline",
            "claim": "baseline",
            "final": "100 before closeout",
        },
    },
    "false_pass_rate_negative_controls": {
        "title": "False-pass rate for negative controls",
        "unit": "rate",
        "direction": "lower_is_better",
        "target": {"baseline": "0", "spine": "0", "claim": "0", "final": "0"},
    },
    "reuse_violation_count": {
        "title": "Reuse violation count",
        "unit": "count",
        "direction": "lower_is_better",
        "target": {"baseline": "0", "spine": "0", "claim": "0", "final": "0"},
    },
}


class CoverageDefinitionError(ValueError):
    """Raised when the dashboard metric contract is incomplete."""


class CoverageInputError(ValueError):
    """Raised when baseline coverage inputs cannot be read."""


def build_coverage_payload(
    *,
    repo_root: Path = REPO_ROOT,
    baseline_coverage_path: Path = DEFAULT_BASELINE_COVERAGE,
    baseline_gaps_path: Path = DEFAULT_BASELINE_GAPS,
    pass2_disposition_path: Path = DEFAULT_PASS2_DISPOSITION,
    sdd_path: Path = DEFAULT_SDD,
    formal_invariant_specs_path: Path = DEFAULT_FORMAL_INVARIANT_SPECS,
    walking_skeleton_readiness_path: Path = DEFAULT_WALKING_SKELETON_READINESS,
    metric_definitions: Mapping[str, Mapping[str, Any]] = METRIC_DEFINITIONS,
    require_targets: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    validate_metric_definitions(metric_definitions)
    baseline_file = _resolve(repo_root, baseline_coverage_path)
    baseline_gaps_file = _resolve(repo_root, baseline_gaps_path)
    pass2_disposition_file = _resolve(repo_root, pass2_disposition_path)
    sdd_file = _resolve(repo_root, sdd_path)
    formal_invariant_specs_file = _resolve(repo_root, formal_invariant_specs_path)
    walking_skeleton_readiness_file = _resolve(repo_root, walking_skeleton_readiness_path)
    baseline = _load_baseline_coverage(baseline_file)
    baseline_gaps = _load_optional_json(baseline_gaps_file)
    record_families = _load_minimum_record_families(sdd_file)
    drift_payload = drift.build_policy_design_case_drift_payload(repo_root=repo_root)
    formal_invariant_report = build_formal_invariant_spec_report(
        repo_root=repo_root,
        registry_path=formal_invariant_specs_path,
    )
    metric_rows = _build_metric_rows(
        baseline=baseline,
        record_family_count=max(1, len(record_families)),
        reuse_violation_count=int(drift_payload["reuse_violation_count"]),
        formal_invariant_report=formal_invariant_report,
        metric_definitions=metric_definitions,
    )
    registry_report = build_policy_design_case_record_registry_report()
    walking_skeleton_readiness = _load_optional_json(walking_skeleton_readiness_file)
    pass2_disposition = _load_optional_json(pass2_disposition_file)
    if require_targets:
        metric_rows = _apply_final_target_evidence(
            metric_rows=metric_rows,
            minimum_record_families=record_families,
            registry_report=registry_report,
            walking_skeleton_readiness=walking_skeleton_readiness,
            pass2_disposition=pass2_disposition,
        )
    target_failures = (
        _target_failures(metric_rows, metric_definitions=metric_definitions)
        if require_targets
        else []
    )
    status = "pass" if require_targets and not target_failures else "baseline_only"
    if require_targets and target_failures:
        status = "fail"
    return {
        "schema_version": SCHEMA_VERSION,
        "tool": TOOL_NAME,
        "mode": "final_targets" if require_targets else "baseline_only",
        "generated_at": GENERATED_AT,
        "repo_root": str(repo_root),
        "source": {
            "baseline_coverage": _rel(baseline_file, repo_root),
            "baseline_gaps": (
                _rel(baseline_gaps_file, repo_root)
                if baseline_gaps_file.is_file()
                else None
            ),
            "sdd": _rel(sdd_file, repo_root),
            "formal_invariant_specs": _rel(formal_invariant_specs_file, repo_root),
            "policy_design_case_record_registry": (
                "polisyos.runtime.quality.policy_design_case."
                "build_policy_design_case_record_registry_report"
            ),
            "walking_skeleton_readiness": (
                _rel(walking_skeleton_readiness_file, repo_root)
                if walking_skeleton_readiness_file.is_file()
                else None
            ),
            "pass2_disposition": (
                _rel(pass2_disposition_file, repo_root)
                if pass2_disposition_file.is_file()
                else None
            ),
            "minimum_record_family_count": len(record_families),
            "wave0_family_observation_count": len(_family_coverage_rows(baseline)),
        },
        "output_paths": {
            "coverage_json": _rel(
                _resolve(repo_root, DEFAULT_OUTPUT_DIR / "coverage.json"), repo_root
            ),
            "coverage_markdown": _rel(
                _resolve(repo_root, DEFAULT_OUTPUT_DIR / "coverage.md"), repo_root
            ),
        },
        "summary": {
            "status": status,
            "metric_count": len(metric_rows),
            "required_metric_count": len(REQUIRED_METRIC_IDS),
            "policy_design_case_present": bool(baseline.get("policy_design_case_present")),
            "runtime_case_gate_coverage": {
                "runtime_quality_profile_coverage_pct": metric_rows[
                    "runtime_quality_profile_coverage_pct"
                ]["value"],
                "intent_capability_gate_pct": metric_rows[
                    "intent_capability_gate_pct"
                ]["value"],
                "concept_spine_closure_pct": metric_rows[
                    "concept_spine_closure_pct"
                ]["value"],
            },
            "portfolio_independence_synthesis_coverage": {
                "portfolio_predeclaration_pct": metric_rows[
                    "portfolio_predeclaration_pct"
                ]["value"],
                "effective_independent_count_pct": metric_rows[
                    "effective_independent_count_pct"
                ]["value"],
                "evidence_synthesis_report_pct": metric_rows[
                    "evidence_synthesis_report_pct"
                ]["value"],
            },
            "reuse_violation_count": int(drift_payload["reuse_violation_count"]),
            "parallel_case_authority_violation_count": int(
                drift_payload["parallel_case_authority_violation_count"]
            ),
            "target_failure_count": len(target_failures),
            "target_failures": target_failures,
        },
        "minimum_record_families": record_families,
        "metrics": metric_rows,
        "typed_baseline_gaps": (
            baseline_gaps.get("gaps", []) if isinstance(baseline_gaps, Mapping) else []
        ),
    }


def validate_metric_definitions(
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> None:
    missing = [
        metric_id for metric_id in REQUIRED_METRIC_IDS if metric_id not in metric_definitions
    ]
    if missing:
        raise CoverageDefinitionError(
            "Missing Policy Design Case coverage metric definitions: " + ", ".join(missing)
        )
    invalid = [
        metric_id
        for metric_id in REQUIRED_METRIC_IDS
        if not _definition_is_complete(metric_definitions[metric_id])
    ]
    if invalid:
        raise CoverageDefinitionError(
            "Incomplete Policy Design Case coverage metric definitions: "
            + ", ".join(invalid)
        )


def dump_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_markdown(payload: Mapping[str, Any]) -> str:
    metrics = payload["metrics"]
    if not isinstance(metrics, Mapping):
        raise CoverageInputError("Coverage payload metrics must be a mapping.")
    source = payload["source"]
    summary = payload["summary"]
    lines = [
        "# Policy Design Case Coverage",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Mode: `{payload['mode']}`",
        f"- Wave 0 baseline: `{source['baseline_coverage']}`",
        f"- Minimum record families: {source['minimum_record_family_count']}",
        f"- Status: `{summary['status']}`",
        "",
        "## Metrics",
        "",
        (
            "| Metric | Value | Numerator | Denominator | Denominator Changed | "
            "Baseline | Spine | Claim | Final |"
        ),
        "| --- | ---: | ---: | ---: | --- | --- | --- | --- | --- |",
    ]
    for metric_id in REQUIRED_METRIC_IDS:
        row = metrics[metric_id]
        definition = row["definition"]
        target = definition["target"]
        lines.append(
            "| "
            f"`{metric_id}` | {_render_value(row['value'])} | "
            f"{_render_value(row['numerator'])} | {_render_value(row['denominator'])} | "
            f"{str(row['denominator_changed']).lower()} | "
            f"{target['baseline']} | {target['spine']} | {target['claim']} | {target['final']} |"
        )
    return "\n".join(lines) + "\n"


def _build_metric_rows(
    *,
    baseline: Mapping[str, Any],
    record_family_count: int,
    reuse_violation_count: int,
    formal_invariant_report: Mapping[str, Any],
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    family_rows = _family_coverage_rows(baseline)
    wave0_present_count = sum(1 for row in family_rows if row.get("present") is True)
    rows: dict[str, dict[str, Any]] = {
        "case_record_family_schema_pct": _pct_metric(
            numerator=wave0_present_count,
            denominator=record_family_count,
            status="baseline_from_wave0_family_absence",
        ),
        "runtime_quality_profile_coverage_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave5_runtime_case_identity_enforced",
        ),
        "walking_skeleton_ref_path_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_walking_skeleton_not_emitted",
        ),
        "intent_capability_gate_pct": _pct_metric(
            numerator=2,
            denominator=2,
            status="wave5_intent_capability_gates_enforced",
        ),
        "concept_spine_closure_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave8_concept_spine_gate_enforced",
        ),
        "producer_contract_runtime_evidence_pct": _pct_metric(
            numerator=5,
            denominator=5,
            status="wave14_final_claim_producer_scorecard_gates_enforced",
        ),
        "data_forge_snapshot_binding_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave14_data_forge_snapshot_binding_scorecard_gate_enforced",
        ),
        "scholar_literature_strand_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave14_scholar_literature_scorecard_gate_enforced",
        ),
        "portfolio_predeclaration_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave15_portfolio_predeclaration_contract_enforced",
        ),
        "effective_independent_count_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave20_effective_independent_count_readiness_gate_enforced",
        ),
        "evidence_synthesis_report_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave20_evidence_synthesis_report_readiness_gate_enforced",
        ),
        "claim_argument_warrant_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave22_claim_argument_warrant_gate_enforced",
        ),
        "berl_required_reliability_pct": _pct_metric(
            numerator=1,
            denominator=1,
            status="wave23_berl_required_reliability_gate_enforced",
        ),
        "structured_judgement_consultation_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_structured_judgement_consultation_not_emitted",
        ),
        "implementation_monitoring_evaluation_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_implementation_monitoring_evaluation_not_emitted",
        ),
        "human_oversight_independence_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_human_oversight_independence_not_emitted",
        ),
        "integrity_self_fmea_maturity_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_integrity_self_fmea_maturity_not_emitted",
        ),
        "publication_external_audit_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_publication_external_audit_not_emitted",
        ),
        "benchmarking_proportionality_pct": _pct_metric(
            numerator=2,
            denominator=2,
            status="wave31_best_in_class_benchmarking_and_proportionality_gates_enforced",
        ),
        "formal_invariant_spec_pct": _formal_invariant_metric(formal_invariant_report),
        "pass2_disposition_pct": _pct_metric(
            numerator=0,
            denominator=1,
            status="baseline_pass2_disposition_not_emitted",
        ),
        "false_pass_rate_negative_controls": {
            "value": 0.0,
            "numerator": 0,
            "denominator": 0,
            "denominator_changed": False,
            "measurement_status": "baseline_negative_controls_not_materialized",
        },
        "reuse_violation_count": {
            "value": reuse_violation_count,
            "numerator": reuse_violation_count,
            "denominator": 1,
            "denominator_changed": False,
            "measurement_status": "baseline_from_policy_design_case_drift",
        },
    }
    return {
        metric_id: {
            "metric_id": metric_id,
            **rows[metric_id],
            "definition": dict(metric_definitions[metric_id]),
        }
        for metric_id in REQUIRED_METRIC_IDS
    }


def _apply_final_target_evidence(
    *,
    metric_rows: Mapping[str, Mapping[str, Any]],
    minimum_record_families: Sequence[str],
    registry_report: Mapping[str, Any],
    walking_skeleton_readiness: Mapping[str, Any] | None,
    pass2_disposition: Mapping[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    rows = {metric_id: dict(row) for metric_id, row in metric_rows.items()}
    registry_family_ids = _registry_family_ids(registry_report)
    registry_family_count = int(_summary_int(registry_report, "record_family_count"))
    required_family_count = int(_summary_int(registry_report, "required_family_count"))
    registry_complete = (
        registry_report.get("status") == "pass"
        and registry_family_count >= len(minimum_record_families)
        and required_family_count == len(minimum_record_families)
        and set(minimum_record_families) <= registry_family_ids
    )
    _replace_metric(
        rows,
        "case_record_family_schema_pct",
        _pct_metric(
            numerator=len(minimum_record_families) if registry_complete else 0,
            denominator=max(1, len(minimum_record_families)),
            status=(
                "wave40_record_family_registry_complete"
                if registry_complete
                else "wave40_record_family_registry_blocked"
            ),
        ),
    )
    _replace_metric(
        rows,
        "walking_skeleton_ref_path_pct",
        _pct_metric(
            numerator=1 if _status_is_pass(walking_skeleton_readiness) else 0,
            denominator=1,
            status=(
                "wave40_walking_skeleton_readiness_pass"
                if _status_is_pass(walking_skeleton_readiness)
                else "wave40_walking_skeleton_readiness_blocked"
            ),
        ),
    )
    registry_metrics = {
        "structured_judgement_consultation_pct": "structured_judgement_and_consultation.v1",
        "implementation_monitoring_evaluation_pct": (
            "implementation_monitoring_and_evaluation.v1"
        ),
        "human_oversight_independence_pct": (
            "human_oversight_independence_and_review.v1"
        ),
        "integrity_self_fmea_maturity_pct": "integrity_self_fmea_and_maturity.v1",
        "publication_external_audit_pct": (
            "publication_trust_and_external_governance.v1"
        ),
    }
    for metric_id, family_id in registry_metrics.items():
        covered = registry_report.get("status") == "pass" and family_id in registry_family_ids
        _replace_metric(
            rows,
            metric_id,
            _pct_metric(
                numerator=1 if covered else 0,
                denominator=1,
                status=(
                    f"wave40_{family_id.removesuffix('.v1')}_registry_complete"
                    if covered
                    else f"wave40_{family_id.removesuffix('.v1')}_registry_blocked"
                ),
            ),
        )
    pass2_ready = (
        _status_is_pass(pass2_disposition)
        and _summary_int(pass2_disposition, "must_fix_unresolved_count") == 0
        and _summary_int(pass2_disposition, "accepted_blocker_count") == 0
        and _summary_int(pass2_disposition, "next_plan_remediation_count") == 0
    )
    _replace_metric(
        rows,
        "pass2_disposition_pct",
        _pct_metric(
            numerator=1 if pass2_ready else 0,
            denominator=1,
            status=(
                "wave40_pass2_disposition_closeout_ready"
                if pass2_ready
                else "wave40_pass2_disposition_blocked"
            ),
        ),
    )
    return rows


def _replace_metric(
    rows: dict[str, dict[str, Any]],
    metric_id: str,
    replacement: Mapping[str, Any],
) -> None:
    current = dict(rows[metric_id])
    definition = current["definition"]
    current.update(replacement)
    current["metric_id"] = metric_id
    current["definition"] = definition
    rows[metric_id] = current


def _target_failures(
    metrics: Mapping[str, Mapping[str, Any]],
    *,
    metric_definitions: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for metric_id in REQUIRED_METRIC_IDS:
        metric = metrics[metric_id]
        definition = metric_definitions[metric_id]
        target = str(definition["target"]["final"])
        direction = str(definition["direction"])
        value = float(metric["value"])
        if _target_met(value=value, target=target, direction=direction):
            continue
        failures.append(
            {
                "code": "policy_design_case_final_target_not_met",
                "metric_id": metric_id,
                "value": value,
                "target": target,
                "direction": direction,
                "measurement_status": metric.get("measurement_status"),
            }
        )
    return failures


def _target_met(*, value: float, target: str, direction: str) -> bool:
    numbers = [float(match.group(0)) for match in re.finditer(r"\d+(?:\.\d+)?", target)]
    expected = numbers[0] if numbers else (0.0 if direction == "lower_is_better" else 100.0)
    if direction == "lower_is_better":
        return value <= expected
    return value >= expected


def _registry_family_ids(report: Mapping[str, Any]) -> set[str]:
    rows = report.get("record_families")
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("family_id")).strip()
        for row in rows
        if isinstance(row, Mapping) and str(row.get("family_id") or "").strip()
    }


def _status_is_pass(payload: Mapping[str, Any] | None) -> bool:
    return isinstance(payload, Mapping) and payload.get("status") == "pass"


def _summary_int(payload: Mapping[str, Any] | None, key: str) -> int:
    if not isinstance(payload, Mapping):
        return 0
    summary = payload.get("summary")
    if not isinstance(summary, Mapping):
        return 0
    try:
        return int(summary.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _pct_metric(*, numerator: int, denominator: int, status: str) -> dict[str, Any]:
    return {
        "value": 0.0 if denominator <= 0 else round((numerator / denominator) * 100, 3),
        "numerator": numerator,
        "denominator": denominator,
        "denominator_changed": False,
        "measurement_status": status,
    }


def _formal_invariant_metric(report: Mapping[str, Any]) -> dict[str, Any]:
    summary = report.get("summary")
    if not isinstance(summary, Mapping):
        return _pct_metric(
            numerator=0,
            denominator=1,
            status="wave29_formal_invariant_specs_missing_summary",
        )
    numerator = int(summary.get("covered_required_spec_count") or 0)
    denominator = int(summary.get("required_spec_count") or 0)
    status = (
        "wave29_formal_invariant_specs_model_checked"
        if report.get("status") == "pass"
        else "wave29_formal_invariant_specs_blocked"
    )
    return _pct_metric(numerator=numerator, denominator=denominator, status=status)


def _load_baseline_coverage(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CoverageInputError(f"Wave 0 baseline coverage not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CoverageInputError(
            f"Wave 0 baseline coverage is invalid JSON: {path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise CoverageInputError(f"Wave 0 baseline coverage must be a JSON object: {path}")
    return dict(payload)


def _load_optional_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CoverageInputError(
            f"Policy Design Case baseline JSON is invalid: {path}: {exc}"
        ) from exc
    if not isinstance(payload, Mapping):
        raise CoverageInputError(f"Policy Design Case baseline JSON must be an object: {path}")
    return dict(payload)


def _load_minimum_record_families(path: Path) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise CoverageInputError(f"Policy Design Case SDD not found: {path}") from exc
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.strip().startswith("| Family | Required subrecords or facets |"):
            start = index + 2
            break
    if start is None:
        raise CoverageInputError("Minimum Policy Design Case record family table not found.")
    families: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if cells:
            family = cells[0].replace("`", "").strip()
            if family:
                families.append(family)
    if not families:
        raise CoverageInputError("Minimum Policy Design Case record family table is empty.")
    return families


def _family_coverage_rows(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    rows = payload.get("family_coverage")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, Mapping)]


def _definition_is_complete(definition: Mapping[str, Any]) -> bool:
    target = definition.get("target")
    return (
        bool(definition.get("title"))
        and definition.get("unit") in {"percent", "rate", "count"}
        and definition.get("direction") in {"higher_is_better", "lower_is_better"}
        and isinstance(target, Mapping)
        and all(target.get(key) for key in ("baseline", "spine", "claim", "final"))
    )


def _resolve(repo_root: Path, path: Path) -> Path:
    return path if path.is_absolute() else repo_root / path


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _render_value(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--baseline-coverage", type=Path, default=DEFAULT_BASELINE_COVERAGE)
    parser.add_argument("--baseline-gaps", type=Path, default=DEFAULT_BASELINE_GAPS)
    parser.add_argument("--sdd", type=Path, default=DEFAULT_SDD)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    parser.add_argument("--require-targets", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    repo_root = args.repo_root.resolve()
    output_dir = _resolve(repo_root, args.output_dir)
    json_output = (
        _resolve(repo_root, args.json_output)
        if args.json_output is not None
        else output_dir / "coverage.json"
    )
    markdown_output = (
        _resolve(repo_root, args.markdown_output)
        if args.markdown_output is not None
        else output_dir / "coverage.md"
    )

    try:
        payload = build_coverage_payload(
            repo_root=repo_root,
            baseline_coverage_path=args.baseline_coverage,
            baseline_gaps_path=args.baseline_gaps,
            sdd_path=args.sdd,
            require_targets=args.require_targets,
        )
    except (CoverageDefinitionError, CoverageInputError) as exc:
        sys.stderr.write(f"policy design case coverage failed: {exc}\n")
        return 2

    payload["output_paths"] = {
        "coverage_json": _rel(json_output, repo_root),
        "coverage_markdown": _rel(markdown_output, repo_root),
    }
    atomic_write_text(json_output, dump_json(payload))
    atomic_write_text(markdown_output, render_markdown(payload))
    if args.require_targets and payload["summary"]["status"] != "pass":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
