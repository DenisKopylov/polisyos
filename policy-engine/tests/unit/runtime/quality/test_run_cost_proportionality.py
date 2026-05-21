from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

import pytest

import polisyos.runtime.quality as runtime_quality
from polisyos.runtime.quality.run_cost_proportionality import (
    RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION,
    RunCostProportionalityError,
    build_run_cost_proportionality_ledger_from_quality_context,
    run_cost_ledger_record_id,
    validate_run_cost_proportionality_ledger,
)
from tests._helpers.hds_quality import sha


def _component(cost: float, *, ref_char: str) -> dict[str, object]:
    return {
        "budget_usd": cost + 1.0,
        "actual_cost_usd": cost,
        "evidence_ref": sha(ref_char),
    }


def _ledger() -> dict[str, object]:
    return {
        "schema_version": RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION,
        "ledger_id": "run-cost-ledger-R_wave30",
        "run_id": "R_wave30",
        "job_id": "job-wave30",
        "authority_level": "production",
        "public_impact": "high",
        "runtime_performance_budget": _component(3.0, ref_char="1"),
        "foundry_cost_model": _component(4.0, ref_char="2"),
        "scientist_budget": _component(5.0, ref_char="3"),
        "doe_search_budget": _component(2.5, ref_char="4"),
        "provider_cost": _component(1.5, ref_char="5"),
        "elapsed_time_budget": {
            "budget_seconds": 3600,
            "actual_seconds": 1800,
            "evidence_ref": sha("6"),
        },
        "human_review_burden": {
            "budget_reviewer_hours": 3.0,
            "actual_reviewer_hours": 1.5,
            "evidence_ref": sha("7"),
        },
        "evidence_depth_budget": {
            "authority_level": "production",
            "public_impact": "high",
            "observed_heterogeneity": "moderate",
            "effective_independent_evidence_count": 4,
            "minimum_effective_independent_evidence_count": 4,
            "stopping_rule": "stop only after saturation and no recent direction changes",
            "stopping_decision": "stop",
            "stopping_rule_result_ref": sha("8"),
        },
        "proportionality_evidence": {
            "status": "proportional",
            "rationale": (
                "High-impact production authority warrants four independent evidence "
                "lines and a bounded human review budget."
            ),
            "evidence_ref": sha("9"),
        },
        "budget_change_records": [],
        "evidence_ref": sha("a"),
        "runtime_event_ref": "event://runtime/run-cost/R_wave30",
    }


def test_run_cost_ledger_consolidates_cost_and_evidence_depth_budgets() -> None:
    validated = validate_run_cost_proportionality_ledger(_ledger())

    assert validated["schema_version"] == RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
    assert run_cost_ledger_record_id(validated) == "run-cost-ledger-R_wave30"
    assert validated["total_actual_cost_usd"] == pytest.approx(16.0)
    assert validated["elapsed_seconds"] == pytest.approx(1800.0)
    assert validated["human_review_hours"] == pytest.approx(1.5)
    assert (
        validated["evidence_depth_budget"][
            "required_effective_independent_evidence_count"
        ]
        == 4
    )


def test_high_cost_low_impact_run_requires_proportionality_evidence() -> None:
    ledger = deepcopy(_ledger())
    ledger["authority_level"] = "research"
    ledger["public_impact"] = "low"
    ledger["total_actual_cost_usd"] = 650.0
    ledger["proportionality_evidence"] = {}
    depth = ledger["evidence_depth_budget"]
    assert isinstance(depth, dict)
    depth["authority_level"] = "research"
    depth["public_impact"] = "low"
    depth["effective_independent_evidence_count"] = 1
    depth["minimum_effective_independent_evidence_count"] = 1

    with pytest.raises(
        RunCostProportionalityError,
        match="policy_design_run_cost_high_cost_low_impact_without_proportionality",
    ):
        validate_run_cost_proportionality_ledger(ledger)


def test_evidence_depth_budget_blocks_shallow_stop_under_required_depth() -> None:
    ledger = deepcopy(_ledger())
    depth = ledger["evidence_depth_budget"]
    assert isinstance(depth, dict)
    depth["observed_heterogeneity"] = "high"
    depth["effective_independent_evidence_count"] = 2
    depth["minimum_effective_independent_evidence_count"] = 2
    depth["stopping_decision"] = "stop"

    with pytest.raises(
        RunCostProportionalityError,
        match="policy_design_run_cost_evidence_depth_under_budget",
    ):
        validate_run_cost_proportionality_ledger(ledger)


def test_run_cost_ledger_is_public_runtime_quality_api() -> None:
    assert (
        runtime_quality.RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
        == RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
    )
    assert (
        runtime_quality.validate_run_cost_proportionality_ledger
        is validate_run_cost_proportionality_ledger
    )


def test_run_cost_ledger_is_projected_from_runtime_quality_context() -> None:
    quality_evidence = {
        "policy_design_case": {
            "case_id": "pdc-R_wave30_projected",
            "effective_execution_profile": {
                "requested_authority_level": "production",
                "effective_execution_profile": "production",
                "validation_profile": "governed",
            },
            "public_impact": "high",
            "evidence_lines": [
                {"line_id": "norms", "evidence_ref": sha("1")},
                {"line_id": "data", "evidence_ref": sha("2")},
                {"line_id": "methods", "evidence_ref": sha("3")},
                {"line_id": "review", "evidence_ref": sha("4")},
            ],
            "synthesis_reports": [
                {
                    "record_id": "synthesis-R_wave30_projected",
                    "information_saturation": {
                        "status": "saturated",
                        "observed_heterogeneity": "moderate",
                        "recent_direction_changes": 0,
                    },
                    "run_cost_proportionality": {
                        "status": "proportional",
                        "budget_tier": "production",
                        "marginal_cost_usd": 3.75,
                        "marginal_information_gain": 0.21,
                        "cost_evidence_ref": sha("5"),
                        "proportionality_rationale": (
                            "Production authority and high public impact justify "
                            "the observed marginal evidence-production cost."
                        ),
                    },
                    "evidence_ref": sha("6"),
                }
            ],
            "policy_design_case_ref": sha("7"),
        },
        "foundry_method_report": {
            "status": "pass",
            "foundry_method_report_ref": sha("8"),
            "selected_methods": [
                {
                    "method_id": "causal.difference_in_differences",
                    "estimated_cost_usd": 2.25,
                }
            ],
        },
        "provider_model_quality_ledger": {
            "status": "pass",
            "provider_model_quality_ledger_ref": sha("9"),
            "entries": [
                {
                    "provider": "gateway",
                    "model_id": "qwen",
                    "metrics": {"cost_usd_total": 1.5},
                }
            ],
        },
        "human_review_calibration": {
            "status": "pass",
            "human_review_calibration_report_ref": sha("a"),
            "summary": {"review_count": 2},
            "reviewer_burden": {"reviewer_hours": 1.25},
        },
    }
    job_payload = {
        "job_id": "job-wave30-projected",
        "run_id": "R_wave30_projected",
        "state": "completed",
        "progress": {
            "details": {
                "runtime_quality_refs": {
                    "performance_budget_ref": sha("b"),
                    "foundry_method_report_ref": sha("8"),
                    "provider_model_quality_ledger_ref": sha("9"),
                    "human_review_calibration_report_ref": sha("a"),
                    "policy_design_case_ref": sha("7"),
                },
                "canary_performance_budget": {
                    "phase_budgets": [
                        {"phase": "control", "observed_duration_ms": 120000, "budget_ms": 300000}
                    ]
                },
                "llm_model_variants": [
                    {
                        "model_variant_id": "qwen_1",
                        "provider": "gateway",
                        "model": "qwen",
                        "cost_usd": 1.5,
                    }
                ],
            }
        },
    }

    ledger = build_run_cost_proportionality_ledger_from_quality_context(
        quality_evidence=quality_evidence,
        job_payload=job_payload,
        canary_kind="production",
    )
    validated = validate_run_cost_proportionality_ledger(ledger)

    assert validated["run_id"] == "R_wave30_projected"
    assert validated["job_id"] == "job-wave30-projected"
    assert validated["authority_level"] == "production"
    assert validated["evidence_depth_budget"]["authority_level"] == "production"
    assert validated["foundry_cost_model"]["actual_cost_usd"] == pytest.approx(2.25)
    assert validated["provider_cost"]["actual_cost_usd"] == pytest.approx(1.5)
    assert validated["elapsed_time_budget"]["actual_seconds"] == pytest.approx(120.0)
    assert validated["human_review_burden"]["actual_reviewer_hours"] == pytest.approx(1.25)
    assert validated["evidence_depth_budget"]["required_effective_independent_evidence_count"] == 3
    assert validated["proportionality_evidence"]["evidence_ref"] == sha("5")


def test_run_cost_ledger_contract_has_schema_and_reference_docs() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    schema_path = (
        repo_root
        / "schemas/runtime_quality/policy_design_run_cost_proportionality_ledger_v1.schema.json"
    )
    docs_path = repo_root / "docs/reference/runtime/run-cost-proportionality-ledger.md"

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["$id"] == (
        "polisyos://schemas/runtime_quality/"
        "policy_design_run_cost_proportionality_ledger_v1.schema.json"
    )
    assert schema["properties"]["schema_version"]["const"] == (
        RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION
    )
    required = set(schema["required"])
    for field in (
        "runtime_performance_budget",
        "foundry_cost_model",
        "scientist_budget",
        "doe_search_budget",
        "provider_cost",
        "elapsed_time_budget",
        "human_review_burden",
        "evidence_depth_budget",
    ):
        assert field in required

    docs = docs_path.read_text(encoding="utf-8")
    assert RUN_COST_PROPORTIONALITY_LEDGER_SCHEMA_VERSION in docs
    assert "policy_design_wave30_run_cost_proportionality" in docs
    assert "typed run-cost blocker" in docs
