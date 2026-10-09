from __future__ import annotations

from datetime import UTC, datetime

import pytest

from polisyos.berl.contracts.display_policy import (
    can_show_bare_bar_chart,
    explanation_limitation_message,
)
from polisyos.berl.contracts.explanation_bundle import (
    AuditReport,
    BackgroundData,
    DisagreementReport,
    ExplanationAssumptions,
    ExplanationBundle,
    FeatureAttribution,
    FeatureContext,
    FeatureDependencePolicy,
    InfidelityReport,
    MethodExplanation,
    ModelContext,
    PerturbationDistribution,
    PredictionContext,
    RedundancyClusterModel,
    RedundancyContext,
    RedundancyEvidenceModel,
    SupportCheck,
    ValidityReport,
    bundle_json_schema,
)
from polisyos.berl.contracts.schema import generated_explanation_bundle_schema
from polisyos.berl.contracts.validation_rules import (
    ValidationThresholds,
    summarize_explanation_response,
    validate_explanation_bundle,
    validate_persisted_explanation_bundle_payload,
)


def _bundle(
    *,
    include_bound: bool = True,
    feature_dependence_policy: str = "marginal",
    feature_dependence_alternatives: tuple[str, ...] = ("marginal_interventional",),
) -> ExplanationBundle:
    infidelity = (
        InfidelityReport(
            point_estimate=0.002,
            upper_bound=0.01,
            confidence=0.95,
            n_eval_perturbations=100,
            residual_cap=1.0,
            bound_type="empirical_bernstein_heldout",
        )
        if include_bound
        else None
    )
    return ExplanationBundle(
        bundle_id="bundle-1",
        created_at=datetime(2026, 4, 26, tzinfo=UTC),
        model=ModelContext(
            model_id="benefits_xgb_v17",
            model_hash="sha256:model",
            model_class="gradient_boosted_trees",
            training_data_hash="sha256:data",
        ),
        prediction=PredictionContext(
            prediction_id="prediction-1",
            row_id="case-1",
            output_name="eligibility_risk",
            output_scale="logit",
            raw_score=1.2,
            display_score=0.77,
            decision_threshold=0.65,
        ),
        feature_context=FeatureContext(
            feature_values_ref="secure://features",
            feature_schema_version="2026-04",
            constraints_ref="constraints-v1",
        ),
        assumptions=ExplanationAssumptions(
            perturbation_distribution=PerturbationDistribution(
                name="conditional_empirical_local",
                radius=0.25,
                categorical_policy="empirical_conditional",
                continuous_policy="knn_conditional_resampling",
                support_constraints="constraints-v1",
            ),
            feature_dependence_policy=FeatureDependencePolicy(
                primary=feature_dependence_policy,
                alternatives_tested=list(feature_dependence_alternatives),
                causal_claim_made=False,
            ),
            background_data=BackgroundData(
                dataset_ref="secure://background",
                n=1000,
                sampling_policy="stratified_recent_training",
            ),
        ),
        redundancy=RedundancyContext(
            clusters=[
                RedundancyClusterModel(
                    cluster_id="income_resources",
                    features=["income", "assets"],
                    evidence=RedundancyEvidenceModel(
                        max_abs_corr=0.82,
                        max_predictability_r2=0.71,
                    ),
                )
            ]
        ),
        methods=[
            MethodExplanation(
                method_id=(
                    "kernel_shap_conditional"
                    if feature_dependence_policy == "conditional_observational"
                    else "kernel_shap"
                ),
                library="shap",
                library_version="x.y.z",
                params={"coalition_samples": 128},
                assumptions={"feature_removal": feature_dependence_policy},
                attributions=[
                    FeatureAttribution(feature="income", value=0.2),
                    FeatureAttribution(feature="assets", value=0.1),
                ],
                infidelity=infidelity,
            )
        ],
        disagreement=DisagreementReport(
            methods_compared=["kernel_shap_conditional"],
            top_k=2,
            top_k_jaccard_median=1.0,
            kendall_tau_median=1.0,
            sign_conflict_features=[],
            flags=[],
        ),
        validity=ValidityReport(
            support_check=SupportCheck(
                ood_rate_eval_perturbations=0.01,
                constraint_violation_rate=0.0,
            ),
            use_restrictions=["Explanation is local to declared perturbations."],
        ),
        audit=AuditReport(
            code_version="explainability-service@sha256:code",
            random_seeds=[1234],
            artifact_refs=["secure://residual_samples.parquet"],
        ),
    )


def test_explanation_bundle_schema_is_available() -> None:
    schema = bundle_json_schema()

    assert schema["title"] == "ExplanationBundle"
    assert "properties" in schema
    generated = generated_explanation_bundle_schema()
    assert generated["$id"] == "https://polisyos.local/schemas/berl/explanation_bundle/1.0.0"


def test_valid_bundle_passes_product_gate() -> None:
    result = validate_explanation_bundle(
        _bundle(),
        thresholds=ValidationThresholds(max_p95_infidelity_upper_bound=0.02),
    )

    assert result.passed
    assert result.display_policy == "analyst_display"
    assert result.violations == ()


def test_conditional_bundle_requires_a_verified_observed_feature_law() -> None:
    result = validate_explanation_bundle(
        _bundle(feature_dependence_policy="conditional_observational")
    )

    assert not result.passed
    assert result.display_policy == "diagnostic_only"
    assert "conditional_feature_law_unverified" in result.violations


@pytest.mark.parametrize("profile", ["future_profile", "conditional", "observational_conditional"])
def test_unknown_feature_dependence_profile_fails_closed(profile: str) -> None:
    result = validate_explanation_bundle(_bundle(feature_dependence_policy=profile))

    assert not result.passed
    assert result.display_policy == "diagnostic_only"
    assert "feature_dependence_profile_unsupported" in result.violations


@pytest.mark.parametrize(
    ("alternative", "expected_violation"),
    [
        ("conditional_observational", "conditional_feature_law_unverified"),
        ("future_profile", "feature_dependence_profile_unsupported"),
    ],
)
def test_unadmitted_alternative_profiles_fail_closed(
    alternative: str,
    expected_violation: str,
) -> None:
    result = validate_explanation_bundle(_bundle(feature_dependence_alternatives=(alternative,)))

    assert not result.passed
    assert result.display_policy == "diagnostic_only"
    assert expected_violation in result.violations


def test_malformed_alternatives_profile_fails_before_model_defaulting() -> None:
    payload = _bundle().model_dump(mode="json")
    payload["assumptions"]["feature_dependence_policy"]["alternatives_tested"] = (
        "conditional_observational"
    )

    bundle, result = validate_persisted_explanation_bundle_payload(payload)

    assert bundle is None
    assert not result.passed
    assert "feature_dependence_profile_malformed" in result.violations


def test_missing_primary_profile_does_not_receive_a_model_default() -> None:
    payload = _bundle().model_dump(mode="json")
    del payload["assumptions"]["feature_dependence_policy"]["primary"]

    bundle, result = validate_persisted_explanation_bundle_payload(payload)

    assert bundle is None
    assert not result.passed
    assert "feature_dependence_profile_malformed" in result.violations


def test_method_profile_must_match_bundle_feature_dependence_profile() -> None:
    method = _bundle().methods[0]
    bundle = _bundle().model_copy(
        update={
            "methods": [
                method.model_copy(
                    update={"assumptions": {"feature_removal": "marginal_interventional"}}
                )
            ]
        }
    )

    result = validate_explanation_bundle(bundle)

    assert not result.passed
    assert "method_feature_dependence_profile_mismatch" in result.violations


def test_missing_bound_fails_closed_as_diagnostic_only() -> None:
    bundle = _bundle(include_bound=False)
    result = validate_explanation_bundle(bundle)

    assert not result.passed
    assert result.faithfulness_claim == "unbounded"
    assert result.display_policy == "diagnostic_only"
    assert "method_missing_infidelity_bound" in result.violations


def test_summary_matches_endpoint_shape() -> None:
    summary = summarize_explanation_response(_bundle())

    assert summary["bundle_id"] == "bundle-1"
    assert summary["status"] == "complete"
    assert isinstance(summary["summary"], dict)
    assert summary["summary"]["primary_driver_level"] == "group"


def test_display_policy_blocks_non_identifiable_bare_bar_chart() -> None:
    bundle = _bundle().model_copy(
        update={
            "disagreement": DisagreementReport(
                methods_compared=["kernel_shap_conditional"],
                top_k=2,
                top_k_jaccard_median=1.0,
                flags=["feature_level_non_identifiable"],
            )
        }
    )

    assert not can_show_bare_bar_chart(bundle)
    assert explanation_limitation_message(bundle) is not None
