from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.berl import ExplanationRequest
from polisyos.core.artifacts.store import FileSystemCAS

if TYPE_CHECKING:
    from polisyos.ir import ExplanationBundleRef
    from polisyos.scientist.orchestration.engine.context import ExecutionContext

pytestmark = pytest.mark.integration


def _model(features: dict[str, float]) -> float:
    return features["x1"] + 2 * features["x2"]


def _request(
    *,
    methods: tuple[str, ...] = ("kernel_shap_marginal", "kernel_shap"),
    feature_dependence_policy: str = "marginal_interventional",
) -> ExplanationRequest:
    return ExplanationRequest(
        prediction_id="berl-service-bridge-prediction",
        row_id="row-1",
        x={"x1": 1.0, "x2": 1.0},
        feature_names=("x1", "x2"),
        methods=methods,
        feature_dependence_policy=feature_dependence_policy,
        model_hash="sha256:berl-service-bridge-model",
        feature_schema_version="berl-service-bridge-v1",
        background_rows=(
            {"x1": 0.0, "x2": 0.0},
            {"x1": 1.0, "x2": 0.0},
            {"x1": 0.0, "x2": 1.0},
        ),
        n_eval_perturbations=16,
        residual_cap=0.05,
        random_seed=11,
        adapter_params={"max_exact_shap_features": 2},
    )


def _phase5_result(store_root: Path, ref: ExplanationBundleRef, run_id: str):
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.validation.phase5_preflight import (
        Phase5ArtifactPreflightInput,
        run_phase5_artifact_preflight,
    )

    return run_phase5_artifact_preflight(
        cast("ExecutionContext", SimpleNamespace(store=FileSystemCAS(store_root))),
        ExperimentState(run_id=run_id),
        Phase5ArtifactPreflightInput(
            artifact_ref=ref,
            artifact_kind="scientist.explanation_bundle",
            analyst_facing=False,
        ),
    )


def test_explain_and_persist_persists_aliases_for_fresh_berl_phase5_and_runtime_readers(
    tmp_path: Path,
) -> None:
    from polisyos.berl import (
        ExplanationBundle,
        explain_and_persist,
        load_explanation_bundle,
    )
    from polisyos.ir import ExplanationBundleRef
    from polisyos.runtime.quality.explanation_reliability import (
        build_berl_warrant_reliability_record,
        evaluate_warrant_berl_reliability,
    )

    request = _request()
    store_root = tmp_path / "service-cas"
    ref = explain_and_persist(_model, request, FileSystemCAS(store_root))

    assert isinstance(ref, ExplanationBundleRef)
    assert ref.kind == "scientist.explanation_bundle"
    assert ref.media_type == "application/json"
    assert ref.manifest_profile_sha256 is not None

    # A newly opened BERL reader resolves the exact selected view emitted by the operation.
    loaded = load_explanation_bundle(FileSystemCAS(store_root), ref)
    assert isinstance(loaded, ExplanationBundle)
    assert [method.requested_method_id for method in loaded.methods] == list(request.methods)
    assert [method.effective_method_id for method in loaded.methods] == [
        "kernel_shap",
        "kernel_shap",
    ]
    # The two requests share one effective adapter run, so the existing producer has
    # no disagreement report; its diagnostic-only profile must survive persistence.
    assert loaded.disagreement is None
    assert loaded.display_policy == "diagnostic_only"
    assert loaded.faithfulness_claim == "unbounded"

    # Phase 5 independently opens CAS and preserves the same fail-closed result.
    phase5 = _phase5_result(store_root, ref, "phase5-berl-service-bridge")
    phase5_explanation = next(
        component
        for component in phase5.validation_report.phase5_components
        if component.name == "explanation"
    )
    assert phase5.validation_report.verdict == "blocked"
    assert phase5_explanation.status == "blocked"
    assert any("missing_disagreement_report" in item for item in phase5_explanation.blockers)

    # The inline candidate is deliberately contradictory; Runtime must resolve the stored ref.
    inline_candidate = loaded.model_dump(mode="json")
    inline_candidate["assumptions"]["feature_dependence_policy"]["primary"] = (
        "conditional_observational"
    )
    for method in inline_candidate["methods"]:
        method["assumptions"]["feature_removal"] = "conditional_observational"
    record = build_berl_warrant_reliability_record(
        reliability_id="berl-service-bridge-record",
        claim_id="claim-1",
        explanation_bundle_ref=ref.model_dump_json(),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.05},
        explanation_bundle=inline_candidate,
        expected_explanation_subject={
            "prediction_id": request.prediction_id,
            "model_hash": request.model_hash,
            "feature_schema_version": request.feature_schema_version,
        },
    )
    assert record["candidate_diagnostics_status"] == "fail"

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
    runtime_record = runtime_result.records[0]
    candidate_diagnostics = runtime_record["candidate_diagnostics"]
    assert candidate_diagnostics["source"] == "selected_cas_bundle"
    assert candidate_diagnostics["threshold_decision"]["display_policy"] == loaded.display_policy
    assert (
        "missing_disagreement_report" in candidate_diagnostics["threshold_decision"]["violations"]
    )
    assert (
        "conditional_feature_law_unverified"
        not in candidate_diagnostics["threshold_decision"]["violations"]
    )
    assert [
        method["requested_method_id"] for method in runtime_record["explanation_bundle"]["methods"]
    ] == list(request.methods)
    assert runtime_record["candidate_diagnostics_status"] == "fail"
    assert runtime_record["threshold_decision"]["candidate_status"] == "fail"
    assert runtime_record["threshold_decision"]["status"] == "fail"
    assert any(
        issue.code == "policy_design_warrant_berl_subject_context_not_established"
        for issue in runtime_result.issues
    )
    assert not any(
        "conditional_feature_law_unverified" in issue.message for issue in runtime_result.issues
    )


def test_explanation_orchestrator_explain_keeps_its_in_memory_bundle_contract() -> None:
    from polisyos.berl import ExplanationBundle, ExplanationOrchestrator

    bundle = ExplanationOrchestrator().explain(_model, _request())

    assert isinstance(bundle, ExplanationBundle)
    assert [method.requested_method_id for method in bundle.methods] == [
        "kernel_shap_marginal",
        "kernel_shap",
    ]
    assert all(method.effective_method_id == "kernel_shap" for method in bundle.methods)


def test_explain_and_persist_propagates_writer_failure_without_a_reference(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.berl import explain_and_persist
    from polisyos.core.artifacts.manifest import ArtifactRef
    from polisyos.core.artifacts.store import PutOptions

    def fail_put_bytes(
        self: FileSystemCAS,
        data: bytes,
        opts: PutOptions,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        raise OSError("simulated BERL CAS writer failure")

    monkeypatch.setattr(FileSystemCAS, "put_bytes", fail_put_bytes)
    store = FileSystemCAS(tmp_path / "writer-failure")

    with pytest.raises(OSError, match="simulated BERL CAS writer failure"):
        explain_and_persist(_model, _request(), store)

    assert store.iter_artifact_ids() == []


def test_explain_and_persist_keeps_unsupported_conditional_request_diagnostic(
    tmp_path: Path,
) -> None:
    from polisyos.berl import explain_and_persist, load_explanation_bundle
    from polisyos.runtime.quality.explanation_reliability import (
        build_berl_warrant_reliability_record,
        evaluate_warrant_berl_reliability,
    )

    store_root = tmp_path / "conditional-cas"
    request = _request(
        methods=("kernel_shap_conditional",),
        feature_dependence_policy="conditional_observational",
    )
    ref = explain_and_persist(_model, request, FileSystemCAS(store_root))
    loaded = load_explanation_bundle(FileSystemCAS(store_root), ref)
    method = loaded.methods[0]

    assert method.requested_method_id == "kernel_shap_conditional"
    assert method.effective_method_id is None
    assert method.scope == "diagnostic"
    assert method.attributions == []
    assert method.infidelity is None
    assert loaded.display_policy == "diagnostic_only"
    assert loaded.faithfulness_claim == "unbounded"

    phase5 = _phase5_result(store_root, ref, "phase5-conditional-diagnostic")
    phase5_explanation = next(
        component
        for component in phase5.validation_report.phase5_components
        if component.name == "explanation"
    )
    assert phase5.validation_report.verdict == "blocked"
    assert phase5_explanation.status == "blocked"
    assert any("conditional_feature_law_unverified" in item for item in phase5_explanation.blockers)

    record = build_berl_warrant_reliability_record(
        reliability_id="berl-service-bridge-conditional-record",
        claim_id="claim-conditional",
        explanation_bundle_ref=ref.model_dump_json(),
        validation_thresholds={"max_p95_infidelity_upper_bound": 0.05},
        explanation_bundle=loaded.model_dump(mode="json"),
        expected_explanation_subject={
            "prediction_id": request.prediction_id,
            "model_hash": request.model_hash,
            "feature_schema_version": request.feature_schema_version,
        },
    )
    runtime = evaluate_warrant_berl_reliability(
        {"warrant_reliability_records": [record]},
        {
            "claim_id": "claim-conditional",
            "warrant_id": "warrant-conditional",
            "berl_reliability_refs": [record["reliability_id"]],
        },
        claim_id="claim-conditional",
        artifact_store=FileSystemCAS(store_root),
    )
    runtime_record = runtime.records[0]
    runtime_diagnostics = runtime_record["candidate_diagnostics"]
    assert runtime_diagnostics["source"] == "selected_cas_bundle"
    assert runtime_diagnostics["threshold_decision"]["status"] == "fail"
    assert (
        "conditional_feature_law_unverified"
        in runtime_diagnostics["threshold_decision"]["violations"]
    )
    assert runtime_record["threshold_decision"]["status"] == "fail"
    assert any("conditional_feature_law_unverified" in issue.message for issue in runtime.issues)
