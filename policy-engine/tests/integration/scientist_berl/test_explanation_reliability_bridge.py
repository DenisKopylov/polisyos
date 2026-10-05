from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest
from pydantic import ValidationError as PydanticValidationError

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
    SupportCheck,
    ValidityReport,
)
from polisyos.berl.service import ExplanationOrchestrator, ExplanationRequest
from polisyos.runtime.quality.explanation_reliability import _validate_bundle_record
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.phase5_preflight import build_phase5_validation_report

if TYPE_CHECKING:
    from polisyos.ir.governance.validation import Phase5GateComponent
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

pytestmark = pytest.mark.integration


def test_scientist_preflight_uses_berl_validation_for_explanation_reliability() -> None:
    valid_bundle = _explanation_bundle()
    valid_component = _explanation_component_for(valid_bundle)
    unbounded_component = _explanation_component_for(
        valid_bundle.model_copy(
            update={
                "methods": [
                    valid_bundle.methods[0].model_copy(update={"infidelity": None})
                ]
            }
        )
    )

    assert valid_component.status == "pass"
    assert valid_component.blockers == []
    assert unbounded_component.status == "blocked"
    assert any(
        "method_missing_infidelity_bound" in item
        for item in unbounded_component.blockers
    )
    assert any("diagnostic-only" in item for item in unbounded_component.blockers)


def test_orchestrator_persisted_bundle_is_admitted_by_both_consumers(
    persisted_orchestrator_bundle: dict[str, object],
) -> None:
    runtime_record, runtime_issues = _validate_bundle_record(
        persisted_orchestrator_bundle,
        thresholds={},
        evidence_ref="cas://berl/orchestrator-bundle",
    )
    phase5_component = _phase5_explanation_component(persisted_orchestrator_bundle)

    threshold_decision = runtime_record["threshold_decision"]
    assert isinstance(threshold_decision, dict)
    assert threshold_decision["status"] == "pass"
    assert runtime_issues == ()
    assert phase5_component.status == "pass"


@pytest.mark.parametrize(
    "mutation",
    ["unknown_version", "missing_defaulted_field", "nested_fake_field"],
)
def test_persisted_bundle_profile_rejects_invalid_artifact_at_both_consumers(
    persisted_orchestrator_bundle: dict[str, object],
    mutation: str,
) -> None:
    payload = deepcopy(persisted_orchestrator_bundle)
    if mutation == "unknown_version":
        payload["schema_version"] = "9.9.9"
    elif mutation == "missing_defaulted_field":
        payload.pop("validity")
    else:
        model_payload = payload["model"]
        assert isinstance(model_payload, dict)
        model_payload["unclaimed"] = "not in the persisted profile"

    if mutation == "nested_fake_field":
        with pytest.raises(PydanticValidationError):
            ExplanationBundle.model_validate(payload)
    else:
        # The construction DTO is deliberately more permissive than the
        # persisted-output contract for valid semver candidates and defaults.
        ExplanationBundle.model_validate(payload)

    runtime_record, runtime_issues = _validate_bundle_record(
        payload,
        thresholds={},
        evidence_ref="cas://berl/orchestrator-bundle",
    )
    phase5_component = _phase5_explanation_component(payload)

    threshold_decision = runtime_record["threshold_decision"]
    assert isinstance(threshold_decision, dict)
    assert threshold_decision["status"] == "fail"
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_invalid" for issue in runtime_issues
    )
    assert any("persisted" in issue.message.lower() for issue in runtime_issues)
    assert phase5_component.status == "blocked"
    assert any("persisted" in item.lower() for item in phase5_component.blockers)


@pytest.fixture(scope="module")
def persisted_orchestrator_bundle(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    request = ExplanationRequest(
        prediction_id="berl-persisted-prediction",
        row_id="berl-persisted-row",
        x={"x": 1.0},
        feature_names=("x",),
        methods=("kernel_shap",),
        output_scale="score",
        feature_dependence_policy="marginal",
        model_id="persisted-policy-model",
        model_hash="sha256:persisted-policy-model",
        model_class="linear-policy-model",
        training_data_hash="sha256:persisted-training-data",
        feature_values_ref="cas://features/berl-persisted-row",
        feature_schema_version="berl-fixture-v1",
        constraints_ref="cas://constraints/berl-persisted-row",
        background_rows=({"x": 0.0}, {"x": 1.0}),
        n_eval_perturbations=256,
        perturbation_radius=0.1,
        residual_cap=1.0,
        random_seed=7,
        include_disagreement=False,
    )
    bundle = ExplanationOrchestrator().explain(
        lambda features: 2.0 * float(features["x"]),
        request,
    )
    artifact_path = tmp_path_factory.mktemp("berl-persisted") / "bundle.json"
    artifact_path.write_text(bundle.model_dump_json() + "\n", encoding="utf-8")
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _explanation_component_for(bundle: ExplanationBundle) -> Phase5GateComponent:
    return _phase5_explanation_component(bundle.model_dump(mode="json"))


def _phase5_explanation_component(payload: dict[str, object]) -> Phase5GateComponent:
    report = build_phase5_validation_report(
        _ctx(),
        ExperimentState(run_id="scientist-berl-bridge"),
        artifact_payload=payload,
        artifact_kind="scientist.explanation_bundle",
    )
    return next(
        component
        for component in report.phase5_components
        if component.name == "explanation"
    )


def _ctx() -> ExecutionContext:
    return cast("ExecutionContext", object())


def _explanation_bundle() -> ExplanationBundle:
    return ExplanationBundle(
        bundle_id="scientist-berl-bridge-bundle",
        created_at=datetime(2026, 5, 7, tzinfo=UTC),
        model=ModelContext(
            model_id="scientist-policy-model",
            model_hash="sha256:model",
            model_class="logistic_policy_model",
            training_data_hash="sha256:training-data",
        ),
        prediction=PredictionContext(
            prediction_id="prediction-1",
            row_id="case-1",
            output_name="policy_readiness",
            output_scale="probability",
            raw_score=0.72,
            display_score=0.72,
            decision_threshold=0.65,
        ),
        feature_context=FeatureContext(
            feature_values_ref="cas://features/prediction-1",
            feature_schema_version="2026-05",
            constraints_ref="cas://constraints/policy-readiness",
        ),
        assumptions=ExplanationAssumptions(
            perturbation_distribution=PerturbationDistribution(
                name="conditional_empirical_local",
                radius=0.2,
                categorical_policy="observed_support_only",
                continuous_policy="local_empirical_resampling",
                support_constraints="cas://constraints/policy-readiness",
            ),
            feature_dependence_policy=FeatureDependencePolicy(
                primary="conditional_observational",
                alternatives_tested=["marginal_interventional"],
                causal_claim_made=False,
            ),
            background_data=BackgroundData(
                dataset_ref="cas://background/policy-readiness",
                n=120,
                sampling_policy="fixed_fixture_sample",
            ),
        ),
        methods=[
            MethodExplanation(
                method_id="kernel_shap_conditional",
                library="berl-fixture",
                library_version="1.0.0",
                params={"coalition_samples": 64},
                assumptions={"feature_removal": "conditional_observational"},
                attributions=[
                    FeatureAttribution(feature="employment_rate", value=0.18),
                    FeatureAttribution(feature="budget_share", value=0.08),
                ],
                infidelity=InfidelityReport(
                    point_estimate=0.004,
                    upper_bound=0.012,
                    confidence=0.95,
                    n_eval_perturbations=64,
                    residual_cap=1.0,
                    bound_type="empirical_bernstein_heldout",
                ),
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
            use_restrictions=["Local to the declared perturbation support."],
        ),
        audit=AuditReport(
            code_version="scientist-explainability@sha256:code",
            random_seeds=[7],
            artifact_refs=["cas://berl/residuals"],
        ),
    )
