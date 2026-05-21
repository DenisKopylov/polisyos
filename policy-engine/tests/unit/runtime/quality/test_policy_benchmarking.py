from __future__ import annotations

# ruff: noqa: S101
from copy import deepcopy
from pathlib import Path

import pytest

import polisyos.runtime.quality as runtime_quality
from polisyos.runtime.quality.policy_benchmarking import (
    POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION,
    PolicyBenchmarkingError,
    best_in_class_benchmarking_record_id,
    validate_policy_benchmarking_record,
    validate_policy_design_best_in_class_benchmarking_records,
)
from tests._helpers.hds_quality import blocking_codes, complete_quality_evidence, scorecard_for, sha


def _metric(
    observed: float,
    target: float,
    *,
    direction: str,
    ref_char: str,
    sample_size: int = 12,
) -> dict[str, object]:
    return {
        "observed_value": observed,
        "target_value": target,
        "direction": direction,
        "sample_size": sample_size,
        "evidence_ref": sha(ref_char),
        "runtime_event_ref": f"event://policy-design-case/benchmarking/{ref_char}",
    }


def _record() -> dict[str, object]:
    return {
        "schema_version": POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION,
        "record_id": "best-in-class-benchmarking-R_wave31",
        "case_id": "pdc-R_wave31",
        "run_id": "R_wave31",
        "job_id": "job-wave31",
        "authority_level": "production",
        "domain": "wartime_msme_support",
        "status": "pass",
        "benchmark_claim_ids": ["rec_1"],
        "run_cost_ledger_refs": [sha("1")],
        "proportionality_evidence_refs": [sha("2")],
        "metrics": {
            "external_audit_pass_rate": _metric(
                0.98,
                0.95,
                direction="higher_is_better",
                ref_char="3",
            ),
            "human_team_benchmark": _metric(
                0.91,
                0.9,
                direction="higher_is_better",
                ref_char="4",
            ),
            "reversal_rate": _metric(
                0.01,
                0.03,
                direction="lower_is_better",
                ref_char="5",
            ),
            "retraction_rate": _metric(
                0.005,
                0.02,
                direction="lower_is_better",
                ref_char="b",
            ),
            "calibration_error": _metric(
                0.025,
                0.04,
                direction="lower_is_better",
                ref_char="6",
            ),
            "claim_substantiation_rate": _metric(
                0.96,
                0.95,
                direction="higher_is_better",
                ref_char="7",
            ),
            "triangulation_coverage": _metric(
                0.94,
                0.9,
                direction="higher_is_better",
                ref_char="8",
            ),
            "operator_time_to_root_cause_seconds": _metric(
                900,
                1200,
                direction="lower_is_better",
                ref_char="9",
            ),
        },
        "evidence_ref": sha("a"),
        "runtime_event_ref": "event://policy-design-case/benchmarking/R_wave31",
    }


def test_best_in_class_benchmarking_record_covers_required_metrics_and_cost_refs() -> None:
    validated = validate_policy_benchmarking_record(_record())

    assert validated["schema_version"] == POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION
    assert best_in_class_benchmarking_record_id(validated) == (
        "best-in-class-benchmarking-R_wave31"
    )
    assert set(validated["metrics"]) == {
        "external_audit_pass_rate",
        "human_team_benchmark",
        "reversal_rate",
        "retraction_rate",
        "calibration_error",
        "claim_substantiation_rate",
        "triangulation_coverage",
        "operator_time_to_root_cause_seconds",
    }
    assert validated["run_cost_ledger_refs"] == [sha("1")]
    assert validated["proportionality_evidence_refs"] == [sha("2")]


def test_best_in_class_claim_without_benchmark_evidence_is_blocked() -> None:
    case = {
        "final_major_claims": [
            {
                "claim_id": "rec_1",
                "major": True,
                "text": "This recommendation is best in class for wartime MSME support.",
                "best_in_class": True,
            }
        ]
    }

    result = validate_policy_design_best_in_class_benchmarking_records(case)

    assert result.status == "fail"
    assert {issue.code for issue in result.issues} == {
        "policy_design_best_in_class_benchmarking_record_missing"
    }


def test_best_in_class_benchmarking_record_rejects_missing_required_metric() -> None:
    record = deepcopy(_record())
    metrics = record["metrics"]
    assert isinstance(metrics, dict)
    metrics.pop("triangulation_coverage")

    with pytest.raises(
        PolicyBenchmarkingError,
        match="policy_design_best_in_class_benchmark_metric_missing",
    ):
        validate_policy_benchmarking_record(record)


def test_best_in_class_benchmarking_rejects_combined_reversal_retraction_substitute() -> None:
    record = deepcopy(_record())
    metrics = record["metrics"]
    assert isinstance(metrics, dict)
    metrics["reversal_retraction_rate"] = metrics.pop("reversal_rate")
    metrics.pop("retraction_rate")

    with pytest.raises(
        PolicyBenchmarkingError,
        match="policy_design_best_in_class_benchmark_metric_missing",
    ):
        validate_policy_benchmarking_record(record)


def test_best_in_class_benchmarking_record_rejects_local_cost_refs() -> None:
    record = deepcopy(_record())
    record["run_cost_ledger_refs"] = ["quality_evidence/run_cost.json"]

    with pytest.raises(
        PolicyBenchmarkingError,
        match="policy_design_best_in_class_run_cost_ref_invalid",
    ):
        validate_policy_benchmarking_record(record)


def test_best_in_class_benchmarking_scorecard_blocks_unfalsifiable_claim() -> None:
    evidence = complete_quality_evidence()
    case = evidence["policy_design_case"]
    assert isinstance(case, dict)
    case["final_major_claims"] = [
        {
            "claim_id": "rec_1",
            "major": True,
            "text": "PolicyOS output is best-in-class for wartime MSME support.",
            "best_in_class": True,
        }
    ]

    scorecard = scorecard_for(quality_evidence=evidence)

    assert "policy_design_best_in_class_benchmarking_record_missing" in blocking_codes(
        scorecard
    )


def test_best_in_class_benchmarking_record_is_public_runtime_quality_api() -> None:
    assert (
        runtime_quality.POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION
        == POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION
    )
    assert runtime_quality.validate_policy_benchmarking_record is (
        validate_policy_benchmarking_record
    )


def test_best_in_class_benchmarking_contract_has_schema_and_reference_docs() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    schema_path = (
        repo_root
        / "schemas/runtime_quality/policy_design_best_in_class_benchmarking_v1.schema.json"
    )
    docs_path = repo_root / "docs/reference/runtime/best-in-class-benchmarking.md"

    assert schema_path.exists()
    assert docs_path.exists()
    assert POLICY_BENCHMARKING_RECORD_SCHEMA_VERSION in docs_path.read_text(
        encoding="utf-8"
    )
