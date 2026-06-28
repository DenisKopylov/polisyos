from __future__ import annotations

import importlib
from datetime import UTC, datetime
from typing import Any

import pytest

CASE_ID = "ua-msme-affordable-loans-2022"
S10_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s10_outcome_prediction.v1"
S10_RULE_VERSION_REF = "policyos.layer2.s10.outcome_prediction.v1"
S10_FLOOR_ID = "s10_calibration"
NOW = datetime(2026, 6, 2, tzinfo=UTC)


def _s10(name: str) -> Any:
    module = importlib.import_module("polisyos.runtime.quality.design_axes.outcome_prediction")
    return getattr(module, name)


def _authority_boundary(
    *,
    authoritative_for: list[str] | None = None,
    posture: str = "shadow",
) -> dict[str, object]:
    return {
        "authoritative_for": authoritative_for
        or [
            "forecast_support_tiering",
            "observable_subset_calibration",
            "value_grounded_welfare_comparison",
        ],
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "approval_authority",
            "scorecard_authority",
            "preference_learning_authority",
            "s11_calibration",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "source_authority": "deterministic_producer",
        "posture": posture,
        "rule_version_refs": [S10_RULE_VERSION_REF],
    }


def _calibration_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "calibration_id": "layer2.s10.calibration.ua-msme.observable",
        "calibration_ref": "pdc://layer2/s10/ua-msme/calibration/observable-subset",
        "case_id": CASE_ID,
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "observable_subset_ref": "pdc://layer2/s10/ua-msme/observable-subset",
        "prediction_ref": "forecast://ua-msme/credit-access/prediction",
        "observed_outcome_ref": "outcome://ua-msme/credit-access/observed",
        "historical_implementation_ref": "implementation://ua-msme/credit-2022",
        "evaluation_design_ref": "eval://ua-msme/credible-counterfactual",
        "credible_evaluation_evidence_ref": "evidence://ua-msme/credible-evaluation",
        "counterfactual_credibility": "credible",
        "prediction_time": NOW,
        "observation_time": NOW,
        "policy_effective_time": NOW,
        "data_valid_time": NOW,
        "calibration_window_start": NOW,
        "calibration_window_end": NOW,
        "metric_name": "observable_subset_calibration",
        "denominator": 4,
        "numerator": 4,
        "pass_rate": 1.0,
        "calibration_threshold_ref": "repo://architecture/policy_design_case/layer2_floor_governance.toml#s10",
        "floor_passed": True,
        "calibration_status": "pass",
        "interval_coverage_metric": 1.0,
        "calibration_error_metric": 0.0,
        "source_lineage_refs": ["lineage://ua-msme/source-contract"],
        "method_lineage_refs": ["lineage://ua-msme/foundry-causal"],
        "floor_id": S10_FLOOR_ID,
        "authority_boundary": _authority_boundary(
            authoritative_for=["observable_subset_calibration"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S10_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _outcome_distribution_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "distribution_id": "layer2.s10.distribution.ua-msme.credit-access",
        "distribution_ref": "pdc://layer2/s10/ua-msme/distribution/credit-access",
        "case_id": CASE_ID,
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "candidate_design_ref": "candidate://ua-msme/targeted-credit",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ["alternative://ua-msme/cash-transfer"],
        "target_outcome_ref": "outcome://credit-access",
        "outcome_unit_ref": "unit://firm",
        "prediction_horizon_ref": "horizon://12-months",
        "jurisdiction_scope_ref": "jurisdiction://ua",
        "method_family": "foundry_causal",
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "point_estimate_ref": "estimate://ua-msme/credit-access/point",
        "uncertainty_interval_ref": "interval://ua-msme/credit-access/95",
        "interval_lower_ref": "interval://ua-msme/credit-access/95/lower",
        "interval_upper_ref": "interval://ua-msme/credit-access/95/upper",
        "distribution_shape": "bounded_interval",
        "forecast_tier": "observable_calibrated",
        "s5_support_label": "validated_local_dynamic_model",
        "non_observable_downgrade_reason": None,
        "limitation_refs": ["limitation://forecast/support-only"],
        "rule_version_ref": S10_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _welfare_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "comparison_id": "layer2.s10.welfare.ua-msme",
        "comparison_ref": "pdc://layer2/s10/ua-msme/welfare-comparison",
        "case_id": CASE_ID,
        "forecast_support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "candidate_design_ref": "candidate://ua-msme/targeted-credit",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ["alternative://ua-msme/cash-transfer"],
        "outcome_distribution_refs": [
            "pdc://layer2/s10/ua-msme/distribution/credit-access"
        ],
        "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
        "s8_value_tradeoff_disclosure_ref": (
            "pdc://layer2/s8/ua-msme/value-tradeoff-disclosure"
        ),
        "pareto_archive_ref": "pdc://layer2/s8/ua-msme/pareto-archive",
        "authorized_value_schedule_ref": "pdc://layer2/s8/ua-msme/value-schedule",
        "social_weight_provenance_refs": ["foundry://welfare/social-weight-provenance"],
        "principal_refs": ["principal://ua/ministry-of-economy"],
        "conflict_refs": [],
        "blocking_rights_refs": ["rights://ua-msme/legal-equality"],
        "welfare_comparison_status": "value_grounded",
        "ranking_mode": "ranked_with_authorized_values",
        "scalar_summary_allowed": False,
        "scalar_welfare_summary_ref": None,
        "pareto_frontier_ref": "foundry://welfare/frontier/ua-msme",
        "rejected_nondominated_alternative_refs": [
            "alternative://ua-msme/cash-transfer"
        ],
        "limitation_refs": ["limitation://value-choice-bounded"],
        "authority_boundary": _authority_boundary(
            authoritative_for=["value_grounded_welfare_comparison"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S10_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def _forecast_support_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "support_id": "layer2.s10.forecast-support.ua-msme",
        "support_ref": "pdc://layer2/s10/ua-msme/forecast-support",
        "case_id": CASE_ID,
        "source_design_record_ref": "pdc://layer2/s2/ua-msme/design-record-v0",
        "design_graph_ref": "pdc://layer2/s5/ua-msme/recursive-design-graph",
        "prediction_context_ref": "pdc://layer2/s10/ua-msme/prediction-context",
        "policy_context_ref": "policy-context://ua-msme/2022",
        "candidate_design_ref": "candidate://ua-msme/targeted-credit",
        "baseline_design_ref": "baseline://ua-msme/no-new-credit",
        "alternative_design_refs": ["alternative://ua-msme/cash-transfer"],
        "prediction_horizon_ref": "horizon://12-months",
        "target_outcome_refs": ["outcome://credit-access"],
        "jurisdiction_scope_ref": "jurisdiction://ua",
        "s5_forecast_support_ref": "pdc://layer2/s5/ua-msme/system-effect-support",
        "s5_support_label": "validated_local_dynamic_model",
        "s5_base_origin": "validated_local_model",
        "s5_claim_scope": "system_effect",
        "s6_firewall_status_refs": ["pdc://layer2/s6/ua-msme/measurability-adequacy"],
        "s6_limitation_refs": ["pdc://layer2/s6/ua-msme/strategic-response-limitation"],
        "s8_value_choice_provenance_ref": "pdc://layer2/s8/ua-msme/value-choice-provenance",
        "s8_value_tradeoff_disclosure_ref": (
            "pdc://layer2/s8/ua-msme/value-tradeoff-disclosure"
        ),
        "source_contract_ref": "source-contract://ua-msme/panel",
        "method_validity_ref": "method-validity://foundry/causal/local",
        "sensitivity_analysis_ref": "sensitivity://ua-msme/credit-access",
        "dynamic_equilibrium_check_ref": "equilibrium-check://ua-msme/system-effect",
        "equilibrium_caveat_refs": ["caveat://partial-equilibrium"],
        "strategic_response_caveat_refs": ["caveat://strategic-response"],
        "outcome_distribution_refs": [
            "pdc://layer2/s10/ua-msme/distribution/credit-access"
        ],
        "welfare_comparison_ref": "pdc://layer2/s10/ua-msme/welfare-comparison",
        "forecast_tier": "observable_calibrated",
        "forecast_authority_disposition_reason": (
            "validated S5 system-effect support with observable calibration"
        ),
        "method_family": "foundry_causal",
        "observable_subset_ref": "pdc://layer2/s10/ua-msme/observable-subset",
        "calibration_record_ref": "pdc://layer2/s10/ua-msme/calibration/observable-subset",
        "uncertainty_interval_refs": ["interval://ua-msme/credit-access/95"],
        "limitation_refs": ["limitation://forecast/support-only"],
        "abstention_refs": [],
        "authority_boundary": _authority_boundary(
            authoritative_for=["forecast_support_tiering"]
        ),
        "may_not_use_for": _authority_boundary()["may_not_use_for"],
        "rule_version_ref": S10_RULE_VERSION_REF,
    }
    payload.update(overrides)
    return payload


def test_forecast_support_requires_s5_s6_s8_authority_inputs() -> None:
    build_forecast_support = _s10("build_forecast_support")

    for broken_field, broken_value in {
        "s5_forecast_support_ref": None,
        "s6_firewall_status_refs": [],
        "s8_value_choice_provenance_ref": None,
    }.items():
        with pytest.raises(ValueError, match=r"S5|S6|S8|authority"):
            build_forecast_support(
                **_forecast_support_payload(**{broken_field: broken_value})
            )


def test_forecast_support_requires_design_graph_and_prediction_context_refs() -> None:
    build_forecast_support = _s10("build_forecast_support")

    for broken_field in ("design_graph_ref", "prediction_context_ref"):
        with pytest.raises(ValueError, match=r"design_graph|prediction_context"):
            build_forecast_support(
                **_forecast_support_payload(**{broken_field: None})
            )


def test_forecast_authority_disposition_is_derived_from_s5_dictionary() -> None:
    build_forecast_support = _s10("build_forecast_support")

    calibrated = build_forecast_support(**_forecast_support_payload())
    simulation_only = build_forecast_support(
        **_forecast_support_payload(
            s5_base_origin="simulation_only",
            s5_support_label="simulation_only_system_effect",
            forecast_tier="observable_calibrated",
            calibration_record_ref=None,
        )
    )

    assert calibrated.forecast_tier == "observable_calibrated"
    assert simulation_only.forecast_tier == "simulation_only_advisory"
    assert simulation_only.forecast_tier != "observable_calibrated"


def test_observable_subset_calibration_controls_forecast_promotion() -> None:
    build_forecast_support = _s10("build_forecast_support")

    with pytest.raises(ValueError, match=r"calibration|observable"):
        build_forecast_support(
            **_forecast_support_payload(
                forecast_tier="observable_calibrated",
                calibration_record_ref=None,
                observable_subset_ref=None,
            )
        )


def test_observable_calibration_requires_credible_evaluation_evidence() -> None:
    build_calibration_record = _s10("build_forecast_calibration_record")

    with pytest.raises(ValueError, match=r"credible_evaluation|counterfactual"):
        build_calibration_record(
            **_calibration_payload(credible_evaluation_evidence_ref=None)
        )


def test_equilibrium_contested_refuses_single_point_forecast() -> None:
    build_forecast_support = _s10("build_forecast_support")

    with pytest.raises(ValueError, match=r"equilibrium|single|point"):
        build_forecast_support(
            **_forecast_support_payload(
                s5_base_origin="equilibrium_contested",
                s5_support_label="equilibrium_contested",
                forecast_tier="observable_calibrated",
                outcome_distribution_refs=["forecast://ua-msme/single-point"],
                uncertainty_interval_refs=[],
            )
        )


def test_simulation_only_projection_is_evidence_blocked() -> None:
    support = _s10("ForecastSupport").model_validate(
        _forecast_support_payload(
            s5_base_origin="simulation_only",
            s5_support_label="simulation_only_system_effect",
            forecast_tier="simulation_only_advisory",
            calibration_record_ref=None,
        )
    )

    envelope = _s10("verify_prediction_authority_envelope")(forecast_support=support)

    assert envelope.forecast_tier == "simulation_only_advisory"
    assert envelope.denies_claim_authority is True
    assert "claim_authority" in envelope.may_not_use_for
    assert "s10_simulation_only_laundered_as_evidence" in envelope.issue_codes


def test_welfare_comparison_requires_s8_value_choice_provenance() -> None:
    build_welfare = _s10("build_welfare_comparison_record")

    with pytest.raises(ValueError, match=r"S8|value|provenance"):
        build_welfare(
            **_welfare_payload(
                s8_value_choice_provenance_ref=None,
                s8_value_tradeoff_disclosure_ref=None,
            )
        )


def test_scalar_welfare_summary_cannot_hide_pareto_tradeoff() -> None:
    build_welfare = _s10("build_welfare_comparison_record")

    with pytest.raises(ValueError, match=r"Pareto|tradeoff|scalar"):
        build_welfare(
            **_welfare_payload(
                scalar_summary_allowed=True,
                scalar_welfare_summary_ref="welfare://ua-msme/scalar-score",
                pareto_frontier_ref=None,
                rejected_nondominated_alternative_refs=[],
            )
        )


def test_validated_local_model_requires_source_contract_and_method_validity() -> None:
    build_forecast_support = _s10("build_forecast_support")

    with pytest.raises(ValueError, match=r"source_contract|method_validity"):
        build_forecast_support(
            **_forecast_support_payload(
                source_contract_ref=None,
                method_validity_ref=None,
                source_lineage_refs=[],
                method_lineage_refs=[],
            )
        )


def test_regime_label_cannot_promote_forecast_tier() -> None:
    build_forecast_support = _s10("build_forecast_support")

    forecast = build_forecast_support(
        **_forecast_support_payload(
            s5_base_origin="simulation_only",
            s5_support_label="simulation_only_system_effect",
            policy_context_ref="policy-context://ua-msme/risk-regime",
            forecast_tier="observable_calibrated",
            calibration_record_ref=None,
        )
    )

    assert forecast.forecast_tier == "simulation_only_advisory"
    assert "risk-regime" in forecast.policy_context_ref


def test_prediction_authority_envelope_denies_production_and_s11() -> None:
    support = _s10("ForecastSupport").model_validate(_forecast_support_payload())

    envelope = _s10("verify_prediction_authority_envelope")(forecast_support=support)

    assert envelope.denies_production_authority is True
    assert envelope.denies_recommendation_authority is True
    assert envelope.denies_s11_authority is True
    assert {"production_recommendation", "s11_calibration"} <= set(envelope.may_not_use_for)


def test_hidden_uncertainty_interval_is_rejected() -> None:
    with pytest.raises(ValueError, match=r"uncertainty|interval"):
        _s10("OutcomeDistributionRecord").model_validate(
            _outcome_distribution_payload(
                uncertainty_interval_ref=None,
                interval_lower_ref=None,
                interval_upper_ref=None,
            )
        )


def test_transport_without_limitation_is_rejected() -> None:
    build_forecast_support = _s10("build_forecast_support")

    with pytest.raises(ValueError, match=r"transport|limitation"):
        build_forecast_support(
            **_forecast_support_payload(
                s5_base_origin="transported_scholar_estimate",
                s5_support_label="transported_with_heavy_limitation",
                forecast_tier="transported_limited",
                limitation_refs=[],
            )
        )
