from __future__ import annotations

import json
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime
from math import sqrt
from types import SimpleNamespace
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
from polisyos.scientist.validation.phase5_preflight import (
    Phase5ArtifactPreflightInput,
    build_phase5_validation_report,
    run_phase5_artifact_preflight,
)

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


def test_cached_failed_kernel_aliases_keep_null_identity_after_fresh_cas_read(
    tmp_path,
) -> None:
    from polisyos.berl import (
        ExplanationOrchestrator,
        ExplanationRequest,
        load_explanation_bundle,
        persist_explanation_bundle,
    )
    from polisyos.core.artifacts.store import FileSystemCAS

    feature_names = tuple(f"x{index}" for index in range(11))
    request = ExplanationRequest(
        prediction_id="cached-kernel-alias-failure",
        row_id="row-1",
        x=dict.fromkeys(feature_names, 1.0),
        feature_names=feature_names,
        methods=("kernel_shap", "kernel_shap_marginal"),
        feature_dependence_policy="marginal_interventional",
        background_rows=(
            dict.fromkeys(feature_names, 0.0),
            dict.fromkeys(feature_names, 1.0),
        ),
        n_eval_perturbations=2,
        random_seed=7,
        include_disagreement=False,
        include_redundancy=False,
    )

    def model(features: dict[str, float]) -> float:
        return sum(features.values())

    producer_store = FileSystemCAS(tmp_path)
    produced = ExplanationOrchestrator().explain(model, request)

    ref = persist_explanation_bundle(producer_store, produced)
    loaded = load_explanation_bundle(FileSystemCAS(tmp_path), ref)
    methods = loaded.methods

    assert [method.requested_method_id for method in methods] == [
        "kernel_shap",
        "kernel_shap_marginal",
    ]
    for method, requested_method_id in zip(
        methods,
        request.methods,
        strict=True,
    ):
        assert method.method_id == requested_method_id
        assert method.effective_method_id is None
        assert method.params["requested_method_id"] == requested_method_id
        assert method.params["effective_method_id"] is None
        assert method.scope == "diagnostic"
        assert method.attributions == []
        assert method.infidelity is None
        assert "reduce features" in str(method.params["diagnostic"])

    component = _explanation_component_for(loaded)
    assert component.status == "blocked"
    assert any("diagnostic-only" in item for item in component.blockers)


@pytest.mark.parametrize(
    ("feature_dependence_policy", "method_id"),
    [
        ("marginal_interventional", "kernel_shap_marginal"),
        ("conditional_observational", "kernel_shap_conditional"),
    ],
)
@pytest.mark.parametrize("preexisting_view", [False, True], ids=["empty-cas", "same-id-collision"])
def test_explanation_orchestrator_bundle_crosses_cas_into_existing_consumers(
    tmp_path,
    feature_dependence_policy: str,
    method_id: str,
    preexisting_view: bool,
) -> None:
    from polisyos.berl import (
        ExplanationOrchestrator,
        ExplanationRequest,
        load_explanation_bundle,
        persist_explanation_bundle,
    )
    from polisyos.berl.contracts.schema import explanation_bundle_schema_id
    from polisyos.core.artifacts import SchemaInfo
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.runtime.quality.explanation_reliability import (
        build_berl_warrant_reliability_record,
        evaluate_warrant_berl_reliability,
    )
    from polisyos.runtime.quality.scorecard import (
        policy_design_case_claim_closeout_gates,
    )
    from polisyos.scientist.nodes.builtins.state_keys import (
        ARTIFACT_EXPLANATION_BUNDLE_REF,
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
        model_hash="sha256:berl-fixture-model",
        feature_schema_version="berl-fixture-schema-v1",
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
    if preexisting_view:
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

    phase5_store = FileSystemCAS(store_root)
    phase5_result = run_phase5_artifact_preflight(
        cast("ExecutionContext", SimpleNamespace(store=phase5_store)),
        ExperimentState(run_id=f"phase5-{feature_dependence_policy}"),
        Phase5ArtifactPreflightInput(
            artifact_ref=ref,
            artifact_kind="scientist.explanation_bundle",
            analyst_facing=False,
        ),
    )
    phase5_explanation = next(
        component
        for component in phase5_result.validation_report.phase5_components
        if component.name == "explanation"
    )
    state_ref_report = build_phase5_validation_report(
        cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(store_root))),
        ExperimentState(
            run_id=f"phase5-state-ref-{feature_dependence_policy}",
            artifacts_index={
                ARTIFACT_EXPLANATION_BUNDLE_REF: ArtifactRef.model_validate(
                    ref.model_dump(mode="python")
                )
            },
        ),
    )
    state_ref_explanation = next(
        component
        for component in state_ref_report.phase5_components
        if component.name == "explanation"
    )
    phase5_manifest = phase5_store.get_manifest(phase5_result.validation_ref.artifact_id)
    explanation_lineage = next(item for item in phase5_manifest.inputs if item.role == "artifact")

    record = build_berl_warrant_reliability_record(
        reliability_id=f"berl-{feature_dependence_policy}",
        claim_id="claim-1",
        explanation_bundle_ref=ref.model_dump_json(),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.05},
        explanation_bundle=loaded.model_dump(mode="json"),
        expected_explanation_subject={
            "prediction_id": request.prediction_id,
            "model_hash": request.model_hash,
            "feature_schema_version": request.feature_schema_version,
        },
    )
    # The embedded object is deliberately the opposite profile; both consumers must
    # resolve the same selected CAS ref rather than trusting this candidate copy.
    inline_candidate = loaded.model_dump(mode="json")
    inline_profile = (
        "marginal_interventional"
        if feature_dependence_policy == "conditional_observational"
        else "conditional_observational"
    )
    inline_candidate["assumptions"]["feature_dependence_policy"]["primary"] = inline_profile
    inline_candidate["methods"][0]["assumptions"]["feature_removal"] = inline_profile
    record["explanation_bundle"] = inline_candidate
    runtime_result = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [record]},
        {
            "claim_id": "claim-1",
            "warrant_id": "warrant-1",
            "berl_reliability_refs": [record["reliability_id"]],
        },
        claim_id="claim-1",
        artifact_store=FileSystemCAS(store_root),
    )
    runtime_case = {
        "final_major_claims": [
            {"claim_id": "claim-1", "major": True, "warrant_refs": ["warrant-1"]}
        ],
        "warrants": [
            {
                "warrant_id": "warrant-1",
                "claim_id": "claim-1",
                "warrant_text": "The persisted explanation supports the scoped claim.",
                "assumptions": ["The declared feature profile is in scope."],
                "applicability_limits": ["Only the resolved model and schema are covered."],
                "requires_explanation_reliability": True,
                "berl_reliability_refs": [record["reliability_id"]],
            }
        ],
        "warrant_reliability_records": [record],
    }
    runtime_scorecard_gates = policy_design_case_claim_closeout_gates(
        runtime_case,
        canary_kind="production",
        artifact_store=FileSystemCAS(store_root),
    )
    runtime_scorecard_codes = {str(gate.get("code")) for gate in runtime_scorecard_gates}

    assert loaded.bundle_id == produced.bundle_id
    assert ref.manifest_profile_sha256 is not None
    assert "manifest_profile_sha256" in record["explanation_bundle_ref"]
    expected_default_schema = "0.9.0" if preexisting_view else "1.0.0"
    assert (
        producer_store.get_manifest(ref.artifact_id).artifact_schema.version
        == expected_default_schema
    )
    assert str(explanation_lineage.artifact_id) == str(ref.artifact_id)
    assert explanation_lineage.manifest_profile_sha256 == ref.manifest_profile_sha256
    if feature_dependence_policy == "marginal_interventional":
        method = loaded.methods[0]
        assert method.requested_method_id == "kernel_shap_marginal"
        assert method.effective_method_id == "kernel_shap"
        assert loaded.display_policy == "analyst_display"
        assert explanation_component.status == "pass"
        assert phase5_explanation.status == "pass", phase5_explanation.blockers
        assert phase5_result.validation_report.verdict == "pass"
        assert state_ref_explanation.status == "pass"
        assert any(
            issue.code == "policy_design_warrant_berl_subject_context_not_established"
            for issue in runtime_result.issues
        )
        assert runtime_result.records[0]["threshold_decision"]["status"] == "fail"
        assert (
            runtime_result.records[0]["candidate_diagnostics"]["threshold_decision"]["status"]
            == "pass"
        )
        assert (
            "policy_design_warrant_berl_subject_context_not_established" in runtime_scorecard_codes
        )
    else:
        method = loaded.methods[0]
        assert method.scope == "diagnostic"
        assert method.attributions == []
        assert method.requested_method_id == method_id
        assert method.effective_method_id is None
        assert "no verified conditional law" in method.params["diagnostic"]
        assert loaded.audit.artifact_refs == ["cas://self-attested/conditional-law-verified"]
        assert explanation_component.status == "blocked"
        assert phase5_explanation.status == "blocked"
        assert phase5_result.validation_report.verdict == "blocked"
        assert state_ref_explanation.status == "blocked"
        assert any(
            "conditional_feature_law_unverified" in blocker
            for blocker in explanation_component.blockers
        )
        assert any(
            "conditional_feature_law_unverified" in issue.message for issue in runtime_result.issues
        )
        assert any(
            "conditional_feature_law_unverified" in str(gate.get("message"))
            for gate in runtime_scorecard_gates
        )

    profileless_result = run_phase5_artifact_preflight(
        cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(store_root))),
        ExperimentState(run_id=f"phase5-profileless-{feature_dependence_policy}"),
        Phase5ArtifactPreflightInput(
            artifact_ref=ref.model_copy(update={"manifest_profile_sha256": None}),
            artifact_kind="scientist.explanation_bundle",
            analyst_facing=False,
        ),
    )
    if preexisting_view:
        assert any(
            "explanation_bundle_manifest_contract_mismatch" in str(item)
            for item in profileless_result.validation_report.normalized_payload["phase5"][
                "failed_evidence_refs"
            ]
        )
        assert profileless_result.validation_report.verdict == "blocked"
    else:
        assert (
            profileless_result.validation_report.verdict == phase5_result.validation_report.verdict
        )

    wrong_profile_result = run_phase5_artifact_preflight(
        cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(store_root))),
        ExperimentState(run_id=f"phase5-corrupt-profile-{feature_dependence_policy}"),
        Phase5ArtifactPreflightInput(
            artifact_ref=ref.model_copy(update={"manifest_profile_sha256": f"sha256:{'0' * 64}"}),
            artifact_kind="scientist.explanation_bundle",
            analyst_facing=False,
        ),
    )
    assert any(
        "explanation_bundle_manifest_contract_mismatch" in str(item)
        for item in wrong_profile_result.validation_report.normalized_payload["phase5"][
            "failed_evidence_refs"
        ]
    )
    assert wrong_profile_result.validation_report.verdict == "blocked"

    wrong_subject_record = deepcopy(record)
    wrong_subject_record["expected_explanation_subject"] = {
        **record["expected_explanation_subject"],
        "prediction_id": "a-different-prediction",
    }
    wrong_subject_result = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [wrong_subject_record]},
        {
            "claim_id": "claim-1",
            "warrant_id": "warrant-1",
            "berl_reliability_refs": [wrong_subject_record["reliability_id"]],
        },
        claim_id="claim-1",
        artifact_store=FileSystemCAS(store_root),
    )
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_subject_mismatch"
        for issue in wrong_subject_result.issues
    )

    malformed_ref_record = deepcopy(record)
    malformed_ref_record["explanation_bundle_ref"] = "{not-json"
    malformed_ref_result = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [malformed_ref_record]},
        {
            "claim_id": "claim-1",
            "warrant_id": "warrant-1",
            "berl_reliability_refs": [malformed_ref_record["reliability_id"]],
        },
        claim_id="claim-1",
        artifact_store=FileSystemCAS(store_root),
    )
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_ref_invalid"
        for issue in malformed_ref_result.issues
    )
    assert malformed_ref_result.records[0]["threshold_decision"]["status"] == "fail"

    wrong_selected_profile = ref.model_dump(mode="json")
    wrong_selected_profile["manifest_profile_sha256"] = "sha256:" + "0" * 64
    wrong_profile_record = deepcopy(record)
    wrong_profile_record["explanation_bundle_ref"] = json.dumps(wrong_selected_profile)
    wrong_profile_runtime_result = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [wrong_profile_record]},
        {
            "claim_id": "claim-1",
            "warrant_id": "warrant-1",
            "berl_reliability_refs": [wrong_profile_record["reliability_id"]],
        },
        claim_id="claim-1",
        artifact_store=FileSystemCAS(store_root),
    )
    assert any(
        issue.code == "policy_design_warrant_berl_bundle_unresolved"
        for issue in wrong_profile_runtime_result.issues
    )


def test_correlated_rho_08_source_bundle_keeps_conditional_refused_and_marginal_control_distinct(
    tmp_path,
) -> None:
    from polisyos.berl import (
        ExplanationOrchestrator,
        ExplanationRequest,
        load_explanation_bundle,
        persist_explanation_bundle,
    )
    from polisyos.core.artifacts import ensure_ir_artifact_store
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.ir.artifacts import get_json_artifact
    from polisyos.ir.model_layer.canon import CanonViolation
    from polisyos.runtime.quality.explanation_reliability import (
        build_berl_warrant_reliability_record,
        evaluate_warrant_berl_reliability,
    )
    from polisyos.runtime.quality.scorecard import (
        policy_design_case_claim_closeout_gates,
    )

    orthogonal = 1.0 / sqrt(3.0)
    background = (
        {"x1": -1.0, "x2": -0.8 + 0.6 * orthogonal},
        {"x1": 0.0, "x2": -1.2 * orthogonal},
        {"x1": 1.0, "x2": 0.8 + 0.6 * orthogonal},
    )
    x_values = [row["x1"] for row in background]
    y_values = [row["x2"] for row in background]
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    covariance = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values, strict=True))
    x_norm = sum((x - x_mean) ** 2 for x in x_values)
    y_norm = sum((y - y_mean) ** 2 for y in y_values)
    assert covariance / sqrt(x_norm * y_norm) == pytest.approx(0.8)

    def model(row: dict[str, float]) -> float:
        return row["x1"]

    store = FileSystemCAS(tmp_path)
    producer = ExplanationOrchestrator()
    cases = (
        ("marginal_interventional", "kernel_shap_marginal"),
        ("conditional_observational", "kernel_shap_conditional"),
    )

    def manifest_reader_for(manifest: object) -> Callable[[object], object]:
        def read_manifest(_selector: object) -> object:
            return manifest

        return read_manifest

    for profile, method_id in cases:
        request = ExplanationRequest(
            prediction_id=f"prediction-{profile}",
            row_id="row-rho-08",
            x={"x1": 1.0, "x2": 1.0},
            feature_names=("x1", "x2"),
            methods=(method_id,),
            feature_dependence_policy=profile,
            model_id="rho-08-linear-model",
            model_hash="sha256:rho-08-model",
            feature_schema_version="rho-08-feature-schema-v1",
            background_rows=background,
            n_eval_perturbations=64,
            residual_cap=0.1,
            random_seed=7,
        )
        bundle = producer.explain(model, request)
        ref = persist_explanation_bundle(store, bundle)
        fresh_store = FileSystemCAS(tmp_path)
        loaded = load_explanation_bundle(fresh_store, ref)
        assert loaded.bundle_id == bundle.bundle_id
        assert loaded.prediction.prediction_id == request.prediction_id
        assert loaded.model.model_hash == request.model_hash
        assert loaded.feature_context.feature_schema_version == request.feature_schema_version
        assert (
            loaded.assumptions.feature_dependence_policy.primary
            == request.feature_dependence_policy
        )
        assert loaded.methods[0].requested_method_id == method_id

        ir_store = ensure_ir_artifact_store(store)
        raw_before = ir_store.get_bytes(ref)
        selected_manifest_before = ir_store.get_manifest_bytes(ref)
        missing_typed_manifest = SimpleNamespace(
            get_bytes=ir_store.get_bytes,
            get_manifest_bytes=ir_store.get_manifest_bytes,
        )
        with pytest.raises(
            CanonViolation,
            match="ir_artifact_selected_manifest_unavailable",
        ):
            get_json_artifact(missing_typed_manifest, ref)

        mismatched_manifest = ir_store.get_manifest(ref).model_copy(
            update={"kind": "scientist.other"}
        )
        mismatched_typed_manifest = SimpleNamespace(
            get_bytes=ir_store.get_bytes,
            get_manifest_bytes=ir_store.get_manifest_bytes,
            get_manifest=manifest_reader_for(mismatched_manifest),
        )
        with pytest.raises(
            CanonViolation,
            match="ir_artifact_selected_manifest_changed",
        ):
            get_json_artifact(mismatched_typed_manifest, ref)
        with pytest.raises(
            ValueError,
            match="explanation_bundle_manifest_contract_mismatch",
        ):
            load_explanation_bundle(mismatched_typed_manifest, ref)
        with pytest.raises(TypeError, match="does not support selected BERL reads"):
            load_explanation_bundle(missing_typed_manifest, ref)
        assert ir_store.get_bytes(ref) == raw_before
        assert ir_store.get_manifest_bytes(ref) == selected_manifest_before

        subject = {
            "prediction_id": request.prediction_id,
            "model_hash": request.model_hash,
            "feature_schema_version": request.feature_schema_version,
        }
        record = build_berl_warrant_reliability_record(
            reliability_id=f"berl-rho08-{profile}",
            claim_id="claim-rho08",
            warrant_id="warrant-rho08",
            explanation_bundle_ref=ref.model_dump_json(),
            validation_thresholds={"max_p95_infidelity_upper_bound": 0.05},
            explanation_bundle=loaded.model_dump(mode="json"),
            expected_explanation_subject=subject,
        )
        case = {"warrant_reliability_records": [record]}
        warrant = {
            "claim_id": "claim-rho08",
            "warrant_id": "warrant-rho08",
            "berl_reliability_refs": [record["reliability_id"]],
        }
        runtime = evaluate_warrant_berl_reliability(
            case,
            warrant,
            claim_id="claim-rho08",
            artifact_store=FileSystemCAS(tmp_path),
        )
        scorecard_case = {
            "final_major_claims": [
                {
                    "claim_id": "claim-rho08",
                    "major": True,
                    "warrant_refs": ["warrant-rho08"],
                }
            ],
            "warrants": [
                {
                    **warrant,
                    "warrant_text": "A source-bound BERL bundle supports this claim.",
                    "assumptions": ["The named feature profile applies."],
                    "applicability_limits": ["The named model and schema apply."],
                    "requires_explanation_reliability": True,
                }
            ],
            "warrant_reliability_records": [record],
        }
        gates = policy_design_case_claim_closeout_gates(
            scorecard_case,
            canary_kind="production",
            artifact_store=FileSystemCAS(tmp_path),
        )
        phase5 = run_phase5_artifact_preflight(
            cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(tmp_path))),
            ExperimentState(run_id=f"phase5-rho08-{profile}"),
            Phase5ArtifactPreflightInput(
                artifact_ref=ref,
                artifact_kind="scientist.explanation_bundle",
                analyst_facing=False,
            ),
        )
        phase5_explanation = next(
            component
            for component in phase5.validation_report.phase5_components
            if component.name == "explanation"
        )
        if profile == "marginal_interventional":
            values = {item.feature: item.value for item in loaded.methods[0].attributions}
            assert values == pytest.approx({"x1": 1.0, "x2": 0.0})
            assert any(
                issue.code == "policy_design_warrant_berl_subject_context_not_established"
                for issue in runtime.issues
            )
            assert runtime.records[0]["threshold_decision"]["status"] == "fail"
            assert (
                runtime.records[0]["candidate_diagnostics"]["threshold_decision"]["status"]
                == "pass"
            )
            assert "policy_design_warrant_berl_subject_context_not_established" in {
                str(gate.get("code")) for gate in gates
            }
            assert phase5_explanation.status == "pass"
        else:
            assert loaded.methods[0].scope == "diagnostic"
            assert loaded.methods[0].attributions == []
            assert any(
                "conditional_feature_law_unverified" in issue.message for issue in runtime.issues
            )
            assert any(
                "conditional_feature_law_unverified" in str(gate.get("message")) for gate in gates
            )
            assert phase5_explanation.status == "blocked"
