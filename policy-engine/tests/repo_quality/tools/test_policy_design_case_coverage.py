# ruff: noqa: S101

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.quality.validation import build_policy_design_case_coverage as coverage

REPO_ROOT = Path(__file__).resolve().parents[3]
EXPECTED_METRICS = {
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
}


def test_policy_design_case_coverage_builder_writes_baseline_only_dashboard(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "coverage"

    exit_code = coverage.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
        ]
    )

    assert exit_code == 0
    payload = json.loads((output_dir / "coverage.json").read_text(encoding="utf-8"))
    markdown = (output_dir / "coverage.md").read_text(encoding="utf-8")
    metrics = payload["metrics"]

    assert payload["schema_version"] == "policyos.policy_design_case.coverage.v1"
    assert payload["mode"] == "baseline_only"
    assert payload["summary"]["status"] == "baseline_only"
    assert payload["summary"]["runtime_case_gate_coverage"] == {
        "runtime_quality_profile_coverage_pct": 100.0,
        "intent_capability_gate_pct": 100.0,
        "concept_spine_closure_pct": 100.0,
    }
    assert payload["summary"]["portfolio_independence_synthesis_coverage"] == {
        "portfolio_predeclaration_pct": 100.0,
        "effective_independent_count_pct": 100.0,
        "evidence_synthesis_report_pct": 100.0,
    }
    assert set(metrics) == EXPECTED_METRICS
    assert payload["source"]["baseline_coverage"].endswith(
        "_build/policy-design-case/rebaseline/wave-0/coverage.json"
    )
    assert payload["source"]["formal_invariant_specs"].endswith(
        "architecture/policy_design_case/formal_invariant_specs.toml"
    )
    assert payload["output_paths"]["coverage_json"].endswith("coverage.json")
    assert payload["output_paths"]["coverage_markdown"].endswith("coverage.md")
    assert (
        "| Metric | Value | Numerator | Denominator | Denominator Changed | "
        "Baseline | Spine | Claim | Final |"
    ) in markdown

    for metric_id in EXPECTED_METRICS:
        metric = metrics[metric_id]
        assert "numerator" in metric, metric_id
        assert "denominator" in metric, metric_id
        assert isinstance(metric["denominator_changed"], bool), metric_id
        assert metric["definition"]["target"]["final"], metric_id
        if metric_id in {
            "runtime_quality_profile_coverage_pct",
            "intent_capability_gate_pct",
            "concept_spine_closure_pct",
        }:
            assert metric["measurement_status"].startswith(("wave5", "wave8")), metric_id
        elif metric_id in {
            "producer_contract_runtime_evidence_pct",
            "data_forge_snapshot_binding_pct",
            "scholar_literature_strand_pct",
        }:
            assert metric["measurement_status"].startswith("wave14"), metric_id
        elif metric_id == "portfolio_predeclaration_pct":
            assert metric["measurement_status"].startswith("wave15"), metric_id
        elif metric_id in {
            "effective_independent_count_pct",
            "evidence_synthesis_report_pct",
        }:
            assert metric["measurement_status"].startswith("wave20"), metric_id
        elif metric_id == "claim_argument_warrant_pct":
            assert metric["measurement_status"].startswith("wave22"), metric_id
        elif metric_id == "berl_required_reliability_pct":
            assert metric["measurement_status"].startswith("wave23"), metric_id
        elif metric_id == "benchmarking_proportionality_pct":
            assert metric["measurement_status"].startswith("wave31"), metric_id
        elif metric_id == "formal_invariant_spec_pct":
            assert metric["measurement_status"].startswith("wave29"), metric_id
        else:
            assert metric["measurement_status"].startswith("baseline"), metric_id

    family_metric = metrics["case_record_family_schema_pct"]
    assert family_metric["value"] == 0.0
    assert family_metric["numerator"] == 0
    assert family_metric["denominator"] >= 19
    assert metrics["runtime_quality_profile_coverage_pct"]["value"] == 100.0
    assert metrics["intent_capability_gate_pct"]["value"] == 100.0
    assert metrics["concept_spine_closure_pct"]["value"] == 100.0
    assert metrics["producer_contract_runtime_evidence_pct"]["value"] > 0.0
    assert metrics["data_forge_snapshot_binding_pct"]["value"] > 0.0
    assert metrics["scholar_literature_strand_pct"]["value"] > 0.0
    assert metrics["portfolio_predeclaration_pct"]["value"] == 100.0
    assert metrics["effective_independent_count_pct"]["value"] == 100.0
    assert metrics["evidence_synthesis_report_pct"]["value"] == 100.0
    assert metrics["claim_argument_warrant_pct"]["value"] == 100.0
    assert metrics["berl_required_reliability_pct"]["value"] == 100.0
    assert metrics["benchmarking_proportionality_pct"]["value"] == 100.0
    assert metrics["benchmarking_proportionality_pct"]["numerator"] == 2
    assert metrics["benchmarking_proportionality_pct"]["denominator"] == 2
    assert metrics["formal_invariant_spec_pct"]["value"] == 100.0
    assert metrics["reuse_violation_count"]["value"] == 0


def test_policy_design_case_coverage_builder_requires_wave0_baseline(
    tmp_path: Path,
) -> None:
    with pytest.raises(coverage.CoverageInputError, match="Wave 0 baseline coverage"):
        coverage.build_coverage_payload(repo_root=tmp_path)


def test_policy_design_case_coverage_require_targets_uses_final_closeout_evidence(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "coverage"

    exit_code = coverage.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--output-dir",
            str(output_dir),
            "--require-targets",
        ]
    )

    payload = json.loads((output_dir / "coverage.json").read_text(encoding="utf-8"))
    metrics = payload["metrics"]

    assert exit_code == 0
    assert payload["mode"] == "final_targets"
    assert payload["summary"]["status"] == "pass"
    assert payload["summary"]["target_failure_count"] == 0
    assert metrics["case_record_family_schema_pct"]["value"] == 100.0
    assert metrics["walking_skeleton_ref_path_pct"]["value"] == 100.0
    assert metrics["structured_judgement_consultation_pct"]["value"] == 100.0
    assert metrics["implementation_monitoring_evaluation_pct"]["value"] == 100.0
    assert metrics["human_oversight_independence_pct"]["value"] == 100.0
    assert metrics["integrity_self_fmea_maturity_pct"]["value"] == 100.0
    assert metrics["publication_external_audit_pct"]["value"] == 100.0
    assert metrics["pass2_disposition_pct"]["value"] == 100.0
