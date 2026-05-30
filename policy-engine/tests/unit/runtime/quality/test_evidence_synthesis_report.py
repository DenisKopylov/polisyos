from __future__ import annotations

# ruff: noqa: S101
import json
from copy import deepcopy
from pathlib import Path

import pytest

import polisyos.runtime.quality as runtime_quality
from polisyos.runtime.quality.evidence_synthesis import (
    EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION,
    EvidenceSynthesisReportError,
    build_evidence_synthesis_report,
    evidence_synthesis_refs_by_claim,
    validate_evidence_synthesis_report_record,
)
from tests._helpers.hds_quality import sha

REPO_ROOT = Path(__file__).resolve().parents[4]
SCHEMA_PATH = (
    REPO_ROOT
    / "schemas/runtime_quality/policy_design_evidence_synthesis_report_v1.schema.json"
)


def _multiverse_curve() -> dict[str, object]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case.multiverse_specification_curve.v1"
        ),
        "curve_id": "multiverse-rec-1",
        "claim_ids": ["rec_1"],
        "portfolio_id": "portfolio-rec-1",
        "source_kind_counts": {
            "backtesting": 1,
            "foundry_sensitivity": 1,
            "scientist_discovery": 1,
            "scientist_doe": 1,
        },
        "specification_records": [
            {
                "specification_id": "twfe-baseline",
                "claim_ids": ["rec_1"],
                "source_kind": "scientist_doe",
                "decision": "defensible",
                "estimate": 0.03,
                "standard_error": 0.01,
                "sign": "positive",
                "significant": True,
                "drivers": {"model_family": "two_way_fixed_effects"},
            },
            {
                "specification_id": "event-study",
                "claim_ids": ["rec_1"],
                "source_kind": "scientist_discovery",
                "decision": "defensible",
                "estimate": 0.02,
                "standard_error": 0.01,
                "sign": "positive",
                "significant": True,
                "drivers": {"model_family": "event_study"},
            },
            {
                "specification_id": "matched-did",
                "claim_ids": ["rec_1"],
                "source_kind": "foundry_sensitivity",
                "decision": "defensible",
                "estimate": 0.01,
                "standard_error": 0.01,
                "sign": "positive",
                "significant": False,
                "drivers": {"model_family": "matched_did"},
            },
            {
                "specification_id": "severe-backtest-loss",
                "claim_ids": ["rec_1"],
                "source_kind": "backtesting",
                "decision": "rejected",
                "estimate": -0.12,
                "standard_error": 0.02,
                "sign": "negative",
                "significant": True,
                "rejection_reason": "Severe backtest reversed the claim direction.",
                "drivers": {"model_family": "placebo_backtest"},
            },
        ],
        "defensible_specifications": [
            {"specification_id": "event-study"},
            {"specification_id": "matched-did"},
            {"specification_id": "twfe-baseline"},
        ],
        "rejected_specifications": [
            {
                "specification_id": "severe-backtest-loss",
                "rejection_reason": "Severe backtest reversed the claim direction.",
            }
        ],
        "result_distribution": {
            "n_specifications": 4,
            "defensible_count": 3,
            "rejected_count": 1,
            "sign_counts": {"positive": 3, "negative": 1, "zero": 0},
            "estimate_min": -0.12,
            "estimate_max": 0.03,
            "estimate_median": 0.015,
            "share_significant": 0.75,
        },
        "drivers_of_divergence": [
            {
                "axis": "model_family",
                "values": ["event_study", "matched_did", "placebo_backtest"],
            }
        ],
        "claim_markers": [
            {
                "claim_id": "rec_1",
                "marker": "fragile",
                "reason_codes": ["rejected_specifications_diverge"],
            }
        ],
        "evidence_ref": sha("2"),
        "runtime_event_ref": sha("e"),
        "previous_wave_refs": _previous_wave_refs(),
    }


def _disconfirming_ledger() -> dict[str, object]:
    return {
        "schema_version": (
            "policyos.runtime.policy_design_case.disconfirming_evidence_ledger.v1"
        ),
        "ledger_id": "disconfirming-ledger-rec-1",
        "portfolio_id": "portfolio-rec-1",
        "claim_ids": ["rec_1"],
        "disconfirming_lines": ["severe-backtest-loss"],
        "ir_falsification_reports": [
            {
                "tests": [
                    {
                        "test_name": "severe-backtest-loss",
                        "test_kind": "placebo_treatment",
                        "passed": False,
                        "p_value": 0.01,
                        "interpretation": "Backtest materially challenges the claim.",
                        "is_critical": True,
                    }
                ],
                "n_passed": 0,
                "n_failed": 1,
                "overall_passed": False,
                "critical_failures": ["severe-backtest-loss"],
            }
        ],
        "adversarial_plans": [{"strategy": "grid_extreme"}],
        "severe_tests": [
            {
                "test_id": "severe-backtest-loss",
                "line_id": "severe-backtest-loss",
                "claim_id": "rec_1",
                "test_kind": "negative_control",
                "severity": "severe",
                "rationale": "The severe backtest can reverse the policy claim.",
                "expected_failure_mode": "backtest_direction_reversal",
                "result": "failed",
                "evidence_ref": sha("3"),
                "runtime_event_ref": sha("4"),
            }
        ],
        "evidence_ref": sha("5"),
        "runtime_event_ref": sha("6"),
        "previous_wave_refs": _previous_wave_refs(),
    }


def _previous_wave_refs() -> dict[str, list[str]]:
    return {
        "portfolio_design_refs": ["portfolio-rec-1"],
        "evidence_line_refs": ["line-data"],
        "independence_map_refs": ["independence-map-rec-1"],
        "multiverse_curve_refs": ["multiverse-rec-1"],
        "disconfirming_ledger_refs": ["disconfirming-ledger-rec-1"],
    }


def _cost_proportionality() -> dict[str, object]:
    return {
        "status": "proportional",
        "budget_tier": "standard",
        "estimated_run_cost_usd": 18.25,
        "marginal_cost_usd": 2.5,
        "marginal_information_gain": 0.01,
        "cost_evidence_ref": sha("9"),
        "proportionality_rationale": (
            "The unresolved direction change warrants one additional independent "
            "line before stopping."
        ),
    }


def test_synthesis_report_records_weighting_certainty_bias_stopping_and_cost() -> None:
    report = build_evidence_synthesis_report(
        report_id="synthesis-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        multiverse_curve=_multiverse_curve(),
        disconfirming_ledgers=[_disconfirming_ledger()],
        primary_synthesis_rule={
            "rule_id": "ivw_defensible_only",
            "weighting": "inverse_variance",
            "included_decisions": ["defensible"],
        },
        sensitivity_synthesis_rules=[
            {
                "rule_id": "equal_weight_with_severe_backtests",
                "weighting": "equal",
                "included_decisions": ["defensible", "rejected"],
                "reasonable": True,
            }
        ],
        heterogeneity_model={
            "model": "random_effects",
            "tau_squared": 0.006,
            "i_squared": 0.71,
            "interpretation": "high",
        },
        certainty_framework={
            "framework": "GRADE-like",
            "rating": "low",
            "downgrade_reasons": ["synthesis_rule_direction_change"],
        },
        publication_bias_treatment={
            "method": "trim_and_fill_shadow",
            "status": "assessed",
            "small_study_effect": "possible",
        },
        inclusion_policy={
            "policy_id": "predeclared-portfolio-inclusion",
            "included_decisions": ["defensible"],
            "rationale": "Primary estimate follows predeclared defensible specs.",
        },
        exclusion_policy={
            "policy_id": "exclude-invalid-primary-include-sensitivity",
            "excluded_decisions": ["rejected"],
            "rationale": (
                "Rejected severe tests are excluded from primary synthesis but "
                "included in sensitivity."
            ),
        },
        information_saturation={
            "status": "not_saturated",
            "effective_independent_evidence_count": 3,
            "minimum_effective_independent_evidence_count": 4,
            "recent_direction_changes": 1,
            "stopping_decision": "continue",
        },
        run_cost_proportionality=_cost_proportionality(),
        divergence_evidence=[
            {
                "evidence_id": "divergence-synthesis-rule-direction-change",
                "kind": "synthesis_rule_sensitivity",
                "claim_ids": ["rec_1"],
                "summary": "Reasonable synthesis rules change the claim direction.",
                "evidence_ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref=sha("c"),
        previous_wave_refs=_previous_wave_refs(),
    )

    validated = validate_evidence_synthesis_report_record(
        report,
        multiverse_curves=[_multiverse_curve()],
        disconfirming_ledgers=[_disconfirming_ledger()],
        major_claim_ids=["rec_1"],
    )

    assert validated["schema_version"] == EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION
    assert validated["claim_direction"] == "positive"
    assert validated["synthesis_estimate"]["rule_id"] == "ivw_defensible_only"
    assert validated["weighting_model"]["strategy"] == "inverse_variance"
    assert validated["publication_bias_treatment"]["status"] == "assessed"
    assert validated["information_saturation"]["stopping_decision"] == "continue"
    assert validated["run_cost_proportionality"]["cost_evidence_ref"] == sha("9")
    assert validated["divergence_assessment"]["status"] == "divergent"
    assert validated["sensitivity_to_synthesis_rules"][0]["direction"] == "negative"
    assert validated["sensitivity_to_synthesis_rules"][0]["direction_changed"] is True
    assert validated["effective_evidence_mass"]["effective_support_mass"] == 3.0
    assert validated["effective_evidence_mass"]["effective_counterevidence_mass"] == 1.0
    assert validated["effective_evidence_mass"]["raw_count_display_policy"][
        "raw_count_authority"
    ] == "diagnostic_only"


def test_synthesis_report_projects_claim_ref_axis_for_compiler() -> None:
    report = build_evidence_synthesis_report(
        report_id="synthesis-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        multiverse_curve=_multiverse_curve(),
        disconfirming_ledgers=[_disconfirming_ledger()],
        primary_synthesis_rule={
            "rule_id": "ivw_defensible_only",
            "weighting": "inverse_variance",
            "included_decisions": ["defensible"],
        },
        sensitivity_synthesis_rules=[
            {
                "rule_id": "equal_weight_with_severe_backtests",
                "weighting": "equal",
                "included_decisions": ["defensible", "rejected"],
                "reasonable": True,
            }
        ],
        heterogeneity_model={"model": "random_effects", "i_squared": 0.71},
        certainty_framework={"framework": "GRADE-like", "rating": "low"},
        publication_bias_treatment={"method": "trim_and_fill_shadow", "status": "assessed"},
        inclusion_policy={"policy_id": "predeclared-portfolio-inclusion"},
        exclusion_policy={"policy_id": "exclude-invalid-primary-include-sensitivity"},
        information_saturation={
            "status": "not_saturated",
            "effective_independent_evidence_count": 3,
            "minimum_effective_independent_evidence_count": 4,
            "recent_direction_changes": 1,
            "stopping_decision": "continue",
        },
        run_cost_proportionality=_cost_proportionality(),
        divergence_evidence=[
            {
                "evidence_id": "divergence-synthesis-rule-direction-change",
                "kind": "synthesis_rule_sensitivity",
                "claim_ids": ["rec_1"],
                "summary": "Reasonable synthesis rules change the claim direction.",
                "evidence_ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref=sha("c"),
        previous_wave_refs=_previous_wave_refs(),
    )

    assert evidence_synthesis_refs_by_claim([report]) == {"rec_1": ["synthesis-rec-1"]}


def test_synthesis_report_preserves_disconfirming_generator_for_effective_mass() -> None:
    report = build_evidence_synthesis_report(
        report_id="synthesis-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        multiverse_curve=_multiverse_curve(),
        disconfirming_ledgers=(row for row in [_disconfirming_ledger()]),
        primary_synthesis_rule={
            "rule_id": "ivw_defensible_only",
            "weighting": "inverse_variance",
            "included_decisions": ["defensible"],
        },
        sensitivity_synthesis_rules=[
            {
                "rule_id": "equal_weight_with_severe_backtests",
                "weighting": "equal",
                "included_decisions": ["defensible", "rejected"],
                "reasonable": True,
            }
        ],
        heterogeneity_model={"model": "random_effects", "i_squared": 0.71},
        certainty_framework={"framework": "GRADE-like", "rating": "low"},
        publication_bias_treatment={"method": "trim_and_fill_shadow", "status": "assessed"},
        inclusion_policy={"policy_id": "predeclared-portfolio-inclusion"},
        exclusion_policy={"policy_id": "exclude-invalid-primary-include-sensitivity"},
        information_saturation={
            "status": "not_saturated",
            "effective_independent_evidence_count": 3,
            "minimum_effective_independent_evidence_count": 4,
            "recent_direction_changes": 1,
            "stopping_decision": "continue",
        },
        run_cost_proportionality=_cost_proportionality(),
        divergence_evidence=[
            {
                "evidence_id": "divergence-synthesis-rule-direction-change",
                "kind": "synthesis_rule_sensitivity",
                "claim_ids": ["rec_1"],
                "summary": "Reasonable synthesis rules change the claim direction.",
                "evidence_ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref=sha("c"),
    )

    assert "disconfirming-ledger-rec-1" in report["disconfirming_ledger_refs"]
    assert report["effective_evidence_mass"]["effective_counterevidence_mass"] == 1.0


def test_synthesis_report_rejects_hidden_direction_change_without_divergence_evidence() -> None:
    report = build_evidence_synthesis_report(
        report_id="synthesis-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        multiverse_curve=_multiverse_curve(),
        disconfirming_ledgers=[_disconfirming_ledger()],
        primary_synthesis_rule={
            "rule_id": "ivw_defensible_only",
            "weighting": "inverse_variance",
            "included_decisions": ["defensible"],
        },
        sensitivity_synthesis_rules=[
            {
                "rule_id": "equal_weight_with_severe_backtests",
                "weighting": "equal",
                "included_decisions": ["defensible", "rejected"],
                "reasonable": True,
            }
        ],
        heterogeneity_model={"model": "random_effects", "i_squared": 0.71},
        certainty_framework={"framework": "GRADE-like", "rating": "low"},
        publication_bias_treatment={"method": "trim_and_fill_shadow", "status": "assessed"},
        inclusion_policy={"policy_id": "predeclared-portfolio-inclusion"},
        exclusion_policy={"policy_id": "exclude-invalid-primary-include-sensitivity"},
        information_saturation={
            "status": "not_saturated",
            "effective_independent_evidence_count": 3,
            "minimum_effective_independent_evidence_count": 4,
            "recent_direction_changes": 1,
            "stopping_decision": "continue",
        },
        run_cost_proportionality=_cost_proportionality(),
        divergence_evidence=[
            {
                "evidence_id": "divergence-synthesis-rule-direction-change",
                "kind": "synthesis_rule_sensitivity",
                "claim_ids": ["rec_1"],
                "summary": "Reasonable synthesis rules change the claim direction.",
                "evidence_ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref=sha("c"),
        previous_wave_refs=_previous_wave_refs(),
    )
    hidden = deepcopy(report)
    hidden["divergence_assessment"] = {
        "status": "convergent",
        "reason_codes": ["claimed_robust_without_surface"],
    }
    hidden["divergence_evidence"] = []

    with pytest.raises(
        EvidenceSynthesisReportError,
        match="policy_design_synthesis_divergence_evidence_missing",
    ):
        validate_evidence_synthesis_report_record(hidden)


def test_synthesis_report_rejects_raw_count_without_collapse_reasons() -> None:
    report = build_evidence_synthesis_report(
        report_id="synthesis-rec-1",
        claim_id="rec_1",
        portfolio_id="portfolio-rec-1",
        multiverse_curve=_multiverse_curve(),
        disconfirming_ledgers=[_disconfirming_ledger()],
        primary_synthesis_rule={
            "rule_id": "ivw_defensible_only",
            "weighting": "inverse_variance",
            "included_decisions": ["defensible"],
        },
        sensitivity_synthesis_rules=[
            {
                "rule_id": "equal_weight_with_severe_backtests",
                "weighting": "equal",
                "included_decisions": ["defensible", "rejected"],
                "reasonable": True,
            }
        ],
        heterogeneity_model={"model": "random_effects", "i_squared": 0.71},
        certainty_framework={"framework": "GRADE-like", "rating": "low"},
        publication_bias_treatment={"method": "trim_and_fill_shadow", "status": "assessed"},
        inclusion_policy={"policy_id": "predeclared-portfolio-inclusion"},
        exclusion_policy={"policy_id": "exclude-invalid-primary-include-sensitivity"},
        information_saturation={
            "status": "not_saturated",
            "effective_independent_evidence_count": 1,
            "minimum_effective_independent_evidence_count": 4,
            "recent_direction_changes": 0,
            "stopping_decision": "continue",
        },
        run_cost_proportionality=_cost_proportionality(),
        divergence_evidence=[
            {
                "evidence_id": "divergence-synthesis-rule-direction-change",
                "kind": "synthesis_rule_sensitivity",
                "claim_ids": ["rec_1"],
                "summary": "Reasonable synthesis rules change the claim direction.",
                "evidence_ref": sha("a"),
            }
        ],
        evidence_ref=sha("b"),
        runtime_event_ref=sha("c"),
        previous_wave_refs=_previous_wave_refs(),
    )
    inflated = deepcopy(report)
    inflated["effective_evidence_mass"] = {
        "raw_evidence_line_count": 10,
        "effective_support_mass": 1.0,
        "effective_counterevidence_mass": 1.0,
        "collapse_reasons": [],
        "raw_count_display_policy": {"raw_count_authority": "diagnostic_only"},
    }

    with pytest.raises(
        EvidenceSynthesisReportError,
        match="policy_design_synthesis_effective_mass_collapse_reasons_missing",
    ):
        validate_evidence_synthesis_report_record(inflated)


def test_synthesis_report_json_schema_names_required_wave19_surfaces() -> None:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == (
        EVIDENCE_SYNTHESIS_REPORT_SCHEMA_VERSION
    )
    assert set(schema["required"]) >= {
        "report_id",
        "claim_ids",
        "portfolio_id",
        "effective_evidence_mass",
        "weighting_model",
        "heterogeneity_model",
        "certainty_framework",
        "publication_bias_treatment",
        "inclusion_policy",
        "exclusion_policy",
        "sensitivity_to_synthesis_rules",
        "information_saturation",
        "run_cost_proportionality",
        "divergence_assessment",
    }


def test_synthesis_report_is_public_runtime_quality_api() -> None:
    assert runtime_quality.build_evidence_synthesis_report is build_evidence_synthesis_report
    assert (
        runtime_quality.validate_evidence_synthesis_report_record
        is validate_evidence_synthesis_report_record
    )
