from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any

import pytest

CASE_ID = "ua-msme-affordable-loans-2022"
S11_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s11_predictive_knowledge.v1"
S11_RULE_VERSION_REF = "policyos.layer2.s11.predictive_knowledge.v1"
S11_FLOOR_ID = "s11_axis_calibration"
NOW = datetime(2026, 6, 2, tzinfo=UTC)


def _s11(name: str) -> Any:
    module = importlib.import_module("polisyos.runtime.quality")
    return getattr(module, name)


def _authority_boundary(
    *,
    authoritative_for: list[str] | None = None,
    posture: str = "shadow",
) -> dict[str, object]:
    return {
        "authoritative_for": authoritative_for
        or [
            "per_axis_predictive_calibration",
            "predictive_axis_maturity_upgrade",
            "proof_carrying_analytics_validity",
            "claim_bound_ir_analytics_bridge",
            "s6_fail_closed_relaxation_decision",
        ],
        "may_not_use_for": [
            "production_authority",
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "runtime_closeout_authority",
            "approval_authority",
            "scorecard_authority",
            "calibrated_equilibrium_prediction",
            "rich_simulation_authority",
            "portfolio_optimization_authority",
            "preference_learning_authority",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
            "mandate_legitimacy_predictive_upgrade",
            "historical_prior_current_evidence",
            "llm_method_authority",
        ],
        "source_authority": "deterministic_producer",
        "posture": posture,
        "rule_version_refs": [S11_RULE_VERSION_REF],
    }


def _calibration_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": S11_SCHEMA_VERSION,
        "calibration_id": "layer2.s11.calibration.ua-msme.measurability",
        "calibration_ref": "pdc://layer2/s11/ua-msme/calibration/measurability",
        "case_id": CASE_ID,
        "axis": "measurability",
        "cell_ref": "SYSTEM.measurability",
        "s6_floor_record_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
        "s10_forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "s10_forecast_calibration_record_ref": "pdc://layer2/s10/ua-msme/calibration",
        "calibration_ledger_ref": "calibration-ledger://ua-msme/current-run",
        "calibration_scope_ref": "scope://ua-msme/current-policy",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "model_family": "foundry_causal",
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "method_infrastructure_refs": ["foundry://methods/calibration/local-causal"],
        "source_lineage_refs": ["lineage://ua-msme/source-contract"],
        "method_lineage_refs": ["lineage://ua-msme/foundry-causal"],
        "effective_independence_refs": ["independence://ua-msme/current-run"],
        "sensitivity_analysis_ref": "sensitivity://ua-msme/measurability",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "counterfactual_credibility_ref": "counterfactual://ua-msme/credible",
        "prediction_time": NOW,
        "observation_time": NOW,
        "policy_effective_time": NOW,
        "data_valid_time": NOW,
        "calibration_window_start": NOW,
        "calibration_window_end": NOW,
        "denominator": 4,
        "numerator": 4,
        "pass_rate": 1.0,
        "threshold": 0.75,
        "threshold_ref": "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11",
        "floor_id": S11_FLOOR_ID,
        "floor_passed": True,
        "calibration_status": "pass",
        "residual_limitation_refs": ["limitation://s11/measurability/current-run"],
        "authority_boundary": _authority_boundary(
            authoritative_for=["per_axis_predictive_calibration"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _upgrade_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "upgrade_id": "layer2.s11.upgrade.ua-msme.measurability",
        "upgrade_ref": "pdc://layer2/s11/ua-msme/upgrade/measurability",
        "case_id": CASE_ID,
        "axis": "measurability",
        "cell_ref": "SYSTEM.measurability",
        "from_maturity": "fail_closed",
        "target_maturity": "predictive",
        "effective_maturity": "predictive",
        "relaxation_decision": "relaxed_to_predictive",
        "s6_floor_record_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
        "s6_floor_disposition": "limit",
        "s10_forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "predictive_model_ref": "model://s11/ua-msme/measurability",
        "axis_model_evidence_refs": ["evidence://s11/ua-msme/measurability"],
        "capacity_dimension_rows": [],
        "strategic_response_channel_rows": [],
        "calibration_record_ref": "pdc://layer2/s11/ua-msme/calibration/measurability",
        "proof_carrying_analytics_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "dynamic_equilibrium_check_ref": "equilibrium-check://ua-msme/system-effect",
        "equilibrium_caveat_refs": ["caveat://ua-msme/partial-equilibrium"],
        "forecast_quality_disposition": "unchanged_s10_tier_consumed",
        "regime_strategy_constraint_ref": "constraint://s11/regime/measurability",
        "residual_limitation_refs": ["limitation://s11/measurability/current-run"],
        "constraint_store_update_refs": ["constraint://s11/measurability/relaxed"],
        "authority_boundary": _authority_boundary(
            authoritative_for=["predictive_axis_maturity_upgrade"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _proof_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "proof_id": "layer2.s11.proof.ua-msme.credit-access",
        "proof_ref": "pdc://layer2/s11/ua-msme/proof/credit-access",
        "case_id": CASE_ID,
        "claim_id": "rec_credit_guarantee",
        "design_comparison_ref": "comparison://ua-msme/credit-vs-cash",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ["alternative://ua-msme/cash-transfer"],
        "ir_analytics_refs": ["ir.analytics.partial_id.msme_survival"],
        "method_output_refs": ["ir.method.partial_identification.ate"],
        "ir_certificate_refs": ["ir.certificate.dual.msme_survival"],
        "negative_certificate_refs": [],
        "proof_status": "identified",
        "proof_composability_status": "reusable",
        "proof_composability_refs": ["ir.proof_composability.msme_survival"],
        "method_requirement_refs": ["method-requirement://partial-identification"],
        "uncertainty_refs": ["ir.uncertainty.msme_survival"],
        "independence_refs": ["independence://ua-msme/current-run"],
        "effective_independence_collapse_refs": [],
        "counter_evidence_refs": [],
        "limitation_refs": ["limitation://proof/partial-identification"],
        "blocker_refs": [],
        "ir_analytics_bridge_ref": "ir-analytics-bridge://ua-msme/credit-access",
        "claim_registry_entry_ref": "claim-registry://ua-msme/rec_credit_guarantee",
        "comparison_consumer_ref": "design-comparison://ua-msme/credit-vs-cash",
        "source_lineage_refs": ["lineage://ua-msme/source-contract"],
        "method_lineage_refs": ["lineage://ua-msme/ir-analytics"],
        "authority_boundary": _authority_boundary(
            authoritative_for=["proof_carrying_analytics_validity"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _integrity_payload(**overrides: object) -> dict[str, object]:
    false_clear_counts = dict.fromkeys(_s11("S11_FALSE_CLEAR_FIELDS"), 0)
    payload: dict[str, object] = {
        "report_id": "layer2.s11.integrity.ua-msme",
        "case_count": 1,
        "axis_count": 4,
        "predictive_axis_count": 2,
        "reverted_fail_closed_axis_count": 2,
        "per_axis_predictive_calibration_numerator": 4,
        "per_axis_predictive_calibration_denominator": 4,
        "per_axis_predictive_calibration_pass_rate": 1.0,
        "per_axis_predictive_calibration_threshold": 0.75,
        "per_axis_predictive_calibration_threshold_ref": (
            "repo://architecture/policy_design_case/layer2_floor_governance.toml#s11"
        ),
        "per_axis_predictive_calibration_status": "pass",
        "per_axis_predictive_calibration_floor_passed": True,
        "proof_bound_claim_count": 1,
        "unbound_analytics_rejected_count": 1,
        "negative_certificate_block_count": 1,
        "forecast_quality_downgrade_count": 1,
        "regime_strategy_constraint_count": 1,
        "method_infrastructure_consumed_count": 1,
        "weakest_boundary_inheritance_count": 4,
        "false_clear_counts": false_clear_counts,
        "authority_boundary": _authority_boundary(
            authoritative_for=["per_axis_predictive_calibration"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S11_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _s6_posture() -> dict[str, object]:
    return {
        "s6_floor_status_refs": [
            "pdc://layer2/s6/ua-msme/measurability-adequacy",
            "pdc://layer2/s6/ua-msme/aggregation-validity",
            "pdc://layer2/s6/ua-msme/capacity-feasibility",
            "pdc://layer2/s6/ua-msme/strategic-response",
        ],
        "s6_axis_rows": [
            {
                "axis": "measurability",
                "cell_ref": "SYSTEM.measurability",
                "record_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "limit",
            }
        ],
        "s6_bridge_consumer_rows": [
            {
                "cell_ref": "SYSTEM.measurability",
                "consumer_ref": "KNOWLEDGE.epistemic_regime",
                "producer_ref": "pdc://layer2/s6/ua-msme/measurability-adequacy",
                "disposition": "limit",
            }
        ],
        "s6_constraint_store_update_refs": ["constraint://s6/measurability"],
        "s6_c3_authority_dimension_refs": [
            "pdc://layer2/s6/ua-msme/cluster-authority-dimensions/measurability_adequacy"
        ],
        "post_intervention_dgp_update_ref": "pdc://layer2/s6/ua-msme/post-intervention-dgp",
        "system_dynamics_handoff_required": True,
    }


def test_predictive_axis_upgrade_requires_s6_floor_s10_forecast_and_calibration_refs() -> None:
    build_upgrade = _s11("build_predictive_axis_upgrade_record")

    for broken_field in (
        "s6_floor_record_ref",
        "s10_forecast_support_ref",
        "calibration_record_ref",
    ):
        with pytest.raises(ValueError, match=r"S6|S10|calibration"):
            build_upgrade(**_upgrade_payload(**{broken_field: None}))


def test_axis_relaxation_reverts_fail_closed_when_calibration_fails_or_stale() -> None:
    build_upgrade = _s11("build_predictive_axis_upgrade_record")

    reverted = build_upgrade(
        **_upgrade_payload(
            effective_maturity="fail_closed",
            relaxation_decision="reverted_fail_closed",
            forecast_quality_disposition="downgraded_by_s11_calibration",
            regime_strategy_constraint_ref="constraint://s11/regime/stale-calibration",
            residual_limitation_refs=["limitation://s11/stale-calibration"],
        )
    )

    assert reverted.effective_maturity == "fail_closed"
    assert reverted.relaxation_decision == "reverted_fail_closed"
    assert reverted.forecast_quality_disposition == "downgraded_by_s11_calibration"
    assert reverted.regime_strategy_constraint_ref


def test_unbound_ir_analytics_does_not_raise_claim_or_comparison_strength() -> None:
    build_proof = _s11("build_proof_carrying_analytics_record")

    with pytest.raises(ValueError, match=r"claim|comparison|bridge|bound"):
        build_proof(
            **_proof_payload(
                claim_id="",
                design_comparison_ref="",
                ir_analytics_bridge_ref="",
            )
        )


def test_negative_certificate_blocks_proof_carrying_analytics() -> None:
    build_proof = _s11("build_proof_carrying_analytics_record")
    verify_envelope = _s11("verify_s11_predictive_knowledge_authority_envelope")

    proof = build_proof(
        **_proof_payload(
            negative_certificate_refs=["ir.negative_certificate.hedge.msme"],
            proof_status="not_identified",
            blocker_refs=["ir.negative_certificate.hedge.msme"],
        )
    )
    envelope = verify_envelope(proof_carrying_analytics_record=proof)

    assert envelope.proof_blocked is True
    assert "ir.negative_certificate.hedge.msme" in envelope.blocker_refs


def test_mandate_legitimacy_is_not_predictive_transition_without_matrix_row() -> None:
    build_upgrade = _s11("build_predictive_axis_upgrade_record")

    with pytest.raises(ValueError, match=r"mandate|matrix|predictive"):
        build_upgrade(
            **_upgrade_payload(
                axis="mandate_legitimacy",
                cell_ref="ACTOR.mandate_legitimacy",
                s6_floor_record_ref="pdc://layer2/s6/ua-msme/mandate-legitimacy",
                effective_maturity="predictive",
            )
        )


def test_historical_prior_outside_context_cannot_improve_current_authority() -> None:
    build_calibration = _s11("build_predictive_axis_calibration_record")

    with pytest.raises(ValueError, match=r"historical|context|current"):
        build_calibration(
            **_calibration_payload(
                calibration_ledger_ref="calibration-ledger://historical-prior/out-of-scope",
                calibration_scope_ref="scope://historical/other-jurisdiction",
                policy_context_ref="policy-context://not-ua-msme",
                floor_passed=True,
                calibration_status="pass",
            )
        )


def test_capacity_predictive_upgrade_requires_axis_dimension_grounding() -> None:
    build_upgrade = _s11("build_predictive_axis_upgrade_record")

    with pytest.raises(ValueError, match=r"capacity|dimension|grounding"):
        build_upgrade(
            **_upgrade_payload(
                axis="state_capacity_feasibility",
                cell_ref="ACTOR.state_capacity_feasibility",
                s6_floor_record_ref="pdc://layer2/s6/ua-msme/capacity-feasibility",
                capacity_dimension_rows=[],
            )
        )


def test_strategic_response_predictive_upgrade_requires_goodhart_lucas_channel_rows() -> None:
    build_upgrade = _s11("build_predictive_axis_upgrade_record")

    with pytest.raises(ValueError, match=r"Goodhart|Lucas|strategic|channel"):
        build_upgrade(
            **_upgrade_payload(
                axis="strategic_response",
                cell_ref="OTHER_AGENTS.strategic_response",
                s6_floor_record_ref="pdc://layer2/s6/ua-msme/strategic-response",
                strategic_response_channel_rows=[],
                dynamic_equilibrium_check_ref=None,
                equilibrium_caveat_refs=[],
            )
        )


def test_s11_calibration_gate_changes_forecast_quality_and_regime_strategy() -> None:
    build_posture = _s11("build_s11_predictive_knowledge_posture")

    posture = build_posture(
        case_id=CASE_ID,
        calibration_records=[
            _calibration_payload(
                calibration_ref="pdc://layer2/s11/ua-msme/calibration/stale",
                calibration_status="stale",
                floor_passed=False,
                numerator=1,
                pass_rate=0.25,
            )
        ],
        proof_records=[_proof_payload()],
        axis_upgrade_rows=[
            _upgrade_payload(
                effective_maturity="fail_closed",
                relaxation_decision="reverted_fail_closed",
                forecast_quality_disposition="downgraded_by_s11_calibration",
            )
        ],
        **_s6_posture(),
    )

    assert posture["forecast_quality_disposition"] == "downgraded_by_s11_calibration"
    assert posture["regime_strategy_constraint_ref"]
    assert posture["s10_forecast_tier"] == "observable_calibrated"


def test_method_infrastructure_advancement_is_consumed_not_reclosed() -> None:
    summarize = _s11("summarize_s11_predictive_knowledge_integrity")

    summary = summarize(
        case_count=1,
        axis_upgrade_records=[
            _upgrade_payload(
                axis_model_evidence_refs=["foundry://validation/method-validity"],
            )
        ],
        method_infrastructure_refs=["foundry://methods/calibration/local-causal"],
        cells_closed=["KNOWLEDGE.calibration", "KNOWLEDGE.ir_proof_carrying_analytics"],
    )

    assert summary.method_infrastructure_consumed_count == 1
    assert "CROSS_CUTTING.method_infrastructure" not in summary.cells_closed


def test_s11_artifacts_have_authority_boundary_and_deny_production_surface() -> None:
    build_calibration = _s11("build_predictive_axis_calibration_record")
    build_upgrade = _s11("build_predictive_axis_upgrade_record")
    build_proof = _s11("build_proof_carrying_analytics_record")

    artifacts = [
        build_calibration(**_calibration_payload()),
        build_upgrade(**_upgrade_payload()),
        build_proof(**_proof_payload()),
    ]

    for artifact in artifacts:
        assert artifact.authority_boundary.authoritative_for
        assert "production_authority" in artifact.may_not_use_for
        assert "rich_simulation_authority" in artifact.may_not_use_for
        assert "claim_authority" in artifact.may_not_use_for


def test_s11_summary_counts_predictive_and_reverted_axes_separately() -> None:
    report_model = _s11("S11PredictiveKnowledgeIntegrityReport")

    report = report_model.model_validate(_integrity_payload())

    assert report.predictive_axis_count == 2
    assert report.reverted_fail_closed_axis_count == 2
    assert report.predictive_axis_count + report.reverted_fail_closed_axis_count == (
        report.axis_count
    )
    assert report.per_axis_predictive_calibration_denominator == report.axis_count


def test_s11_integrity_report_requires_exact_false_clear_keys() -> None:
    report_model = _s11("S11PredictiveKnowledgeIntegrityReport")
    false_clear_counts = dict.fromkeys(_s11("S11_FALSE_CLEAR_FIELDS"), 0)
    false_clear_counts["unexpected_extra_probe"] = 0

    with pytest.raises(ValueError, match="S11_FALSE_CLEAR_FIELDS"):
        report_model.model_validate(
            _integrity_payload(false_clear_counts=false_clear_counts)
        )
