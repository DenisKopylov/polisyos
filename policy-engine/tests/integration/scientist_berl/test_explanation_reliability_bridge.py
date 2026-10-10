from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import pytest

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
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.validation.phase5_preflight import build_phase5_validation_report

if TYPE_CHECKING:
    from polisyos.ir.governance.validation import Phase5GateComponent
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

pytestmark = pytest.mark.integration


def test_scientist_preflight_uses_berl_validation_for_explanation_reliability() -> None:
    valid_bundle = _explanation_bundle()
    valid_component = _explanation_component_for(valid_bundle)
    conditional_component = _explanation_component_for(
        _explanation_bundle(feature_dependence_policy="conditional_observational")
    )
    unbounded_component = _explanation_component_for(
        valid_bundle.model_copy(
            update={"methods": [valid_bundle.methods[0].model_copy(update={"infidelity": None})]}
        )
    )

    assert valid_component.status == "pass"
    assert valid_component.blockers == []
    assert conditional_component.status == "blocked"
    assert any(
        "conditional_feature_law_unverified" in item for item in conditional_component.blockers
    )
    assert unbounded_component.status == "blocked"
    assert any("method_missing_infidelity_bound" in item for item in unbounded_component.blockers)
    assert any("diagnostic-only" in item for item in unbounded_component.blockers)


def _explanation_component_for(bundle: ExplanationBundle) -> Phase5GateComponent:
    report = build_phase5_validation_report(
        _ctx(),
        ExperimentState(run_id="scientist-berl-bridge"),
        artifact_payload=bundle.model_dump(mode="json"),
        artifact_kind="scientist.explanation_bundle",
    )
    return next(
        component for component in report.phase5_components if component.name == "explanation"
    )


def _ctx() -> ExecutionContext:
    return cast("ExecutionContext", object())


def _explanation_bundle(
    *, feature_dependence_policy: str = "marginal_interventional"
) -> ExplanationBundle:
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
                primary=feature_dependence_policy,
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
                method_id=(
                    "kernel_shap_conditional"
                    if feature_dependence_policy == "conditional_observational"
                    else "kernel_shap"
                ),
                library="berl-fixture",
                library_version="1.0.0",
                params={"coalition_samples": 64},
                assumptions={"feature_removal": feature_dependence_policy},
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


@pytest.mark.parametrize(
    ("feature_dependence_policy", "method_id"),
    [
        ("marginal_interventional", "kernel_shap_marginal"),
        ("conditional_observational", "kernel_shap_conditional"),
    ],
)
def test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers(
    tmp_path,
    feature_dependence_policy: str,
    method_id: str,
) -> None:
    from polisyos.berl import (
        ExplanationOrchestrator,
        ExplanationRequest,
        load_explanation_bundle,
        persist_explanation_bundle,
    )
    from polisyos.berl.contracts.schema import explanation_bundle_schema_id
    from polisyos.core.artifacts import SchemaInfo
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.runtime.quality.explanation_reliability import (
        build_berl_warrant_reliability_record,
        evaluate_warrant_berl_reliability,
    )

    store_root = tmp_path / feature_dependence_policy
    producer = ExplanationOrchestrator()

    def model(row: dict[str, float]) -> float:
        return row["x1"] + 2 * row["x2"]

    request = ExplanationRequest(
        prediction_id=f"prediction-{feature_dependence_policy}",
        row_id="row-1",
        x={"x1": 1.0, "x2": 1.0},
        feature_names=("x1", "x2"),
        methods=(method_id,),
        feature_dependence_policy=feature_dependence_policy,
        background_rows=(
            {"x1": 0.0, "x2": 0.0},
            {"x1": 1.0, "x2": 0.0},
            {"x1": 0.0, "x2": 1.0},
        ),
        n_eval_perturbations=64,
        residual_cap=0.01,
        random_seed=7,
        adapter_params={"max_exact_shap_features": 2},
        artifact_refs=(
            ("cas://self-attested/conditional-law-verified",)
            if feature_dependence_policy == "conditional_observational"
            else ()
        ),
    )

    produced = producer.explain(model, request)
    producer_store = FileSystemCAS(store_root)
    producer_store.put_json(
        produced.model_dump(mode="json", round_trip=True),
        PutOptions(
            kind="scientist.explanation_bundle",
            media_type="application/json",
            schema=SchemaInfo(
                name=explanation_bundle_schema_id(),
                version="0.9.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )
    ref = persist_explanation_bundle(producer_store, produced)
    loaded = load_explanation_bundle(FileSystemCAS(store_root), ref)
    explanation_component = _explanation_component_for(loaded)

    record = build_berl_warrant_reliability_record(
        reliability_id=f"berl-{feature_dependence_policy}",
        claim_id="claim-1",
        explanation_bundle_ref=ref.model_dump_json(),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.05},
        explanation_bundle=loaded.model_dump(mode="json"),
    )
    record["explanation_bundle"] = loaded.model_dump(mode="json")
    runtime_result = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [record]},
        {
            "claim_id": "claim-1",
            "warrant_id": "warrant-1",
            "berl_reliability_refs": [record["reliability_id"]],
        },
        claim_id="claim-1",
    )

    assert loaded.bundle_id == produced.bundle_id
    assert ref.manifest_profile_sha256 is not None
    assert "manifest_profile_sha256" in record["explanation_bundle_ref"]
    if feature_dependence_policy == "marginal_interventional":
        method = loaded.methods[0]
        assert method.requested_method_id == "kernel_shap_marginal"
        assert method.effective_method_id == "kernel_shap"
        assert loaded.display_policy == "analyst_display"
        assert explanation_component.status == "pass"
        assert runtime_result.issues == ()
    else:
        method = loaded.methods[0]
        assert method.scope == "diagnostic"
        assert method.attributions == []
        assert "no verified conditional law" in method.params["diagnostic"]
        assert loaded.audit.artifact_refs == ["cas://self-attested/conditional-law-verified"]
        assert explanation_component.status == "blocked"
        assert any(
            "conditional_feature_law_unverified" in blocker
            for blocker in explanation_component.blockers
        )
        assert any(
            "conditional_feature_law_unverified" in issue.message for issue in runtime_result.issues
        )
