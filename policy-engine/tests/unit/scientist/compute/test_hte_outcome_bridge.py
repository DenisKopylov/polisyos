"""Exercise the HTE finalizer through portable Runtime-owned CAS artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

pytestmark = pytest.mark.integration


def _put_hte_input(
    service: Any,
    *,
    tenant_id: str,
    cell_id: str,
) -> Any:
    """Write a temporary selected HTE input through the Runtime's artifact store."""
    from polisyos.core.artifacts import ArtifactGovernanceInfo, ArtifactRef, SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec
    from polisyos.core.security.tenant_context import tenant_scope

    row_count = 40
    payload = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"portable-candidate-{index}" for index in range(row_count)],
        "metadata": {"source": "portable_finalizer_test"},
    }
    envelope = {
        "schema_version": "policyos.ir.observation.method_input_envelope.v1",
        "contract_target": {
            "contract_id": "foundry.causal.hte_observational_data.v1",
            "contract_fqn": (
                "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
            ),
        },
        "contract_payload": payload,
    }
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ref = service._artifact_store.put_json(
            envelope,
            PutOptions(
                kind="ir.observation_method_input",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.ir.ObservationMethodInputEnvelope",
                    version="1.0",
                ),
                inputs=[],
                governance=ArtifactGovernanceInfo(classification="public"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    return ArtifactRef.model_validate(ref, strict=True)


def test_writer_owner_binding_recipe_preserves_order_and_selected_profiles() -> None:
    """Keep physical and Search lineage edges ordered and profile-bound."""
    from types import SimpleNamespace

    from polisyos.core.artifacts import ArtifactRef as CoreArtifactRef
    from polisyos.core.artifacts import input_ref_from_artifact_ref
    from polisyos.scientist.compute.hte_outcome_bridge import (
        _assert_manifest_inputs,
        _numeric_outcome_inputs,
        _owner_binding_inputs,
    )

    physical_ref = CoreArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="foundry.hte.physical_source_materialization_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    search_ref = CoreArtifactRef(
        artifact_id="sha256:" + "2" * 64,
        kind="scientist.search.uncertainty_task_binding",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "b" * 64,
    )
    owner_inputs = _owner_binding_inputs(
        materialization_binding_ref=physical_ref,
        search_uncertainty_task_binding_ref=search_ref,
    )
    assert tuple(role for _ref, role in owner_inputs) == (
        "physical_source_materialization_binding",
        "search_uncertainty_task_binding",
    )
    selected_ref_payloads = []
    for selected_ref, _role in owner_inputs:
        assert isinstance(selected_ref, CoreArtifactRef)
        selected_ref_payloads.append(selected_ref.model_dump(mode="json"))
    assert tuple(selected_ref_payloads) == (
        physical_ref.model_dump(mode="json"),
        search_ref.model_dump(mode="json"),
    )

    def manifest_for(inputs: tuple[tuple[object, str], ...]) -> SimpleNamespace:
        selected_inputs = []
        for selected, role in inputs:
            assert isinstance(selected, CoreArtifactRef)
            selected_inputs.append(input_ref_from_artifact_ref(selected, role=role))
        return SimpleNamespace(inputs=tuple(selected_inputs))

    _assert_manifest_inputs(manifest_for(owner_inputs), owner_inputs, CoreArtifactRef)
    with pytest.raises(ValueError, match="hte_bridge_manifest_lineage_mismatch"):
        _assert_manifest_inputs(
            manifest_for(tuple(reversed(owner_inputs))),
            owner_inputs,
            CoreArtifactRef,
        )

    wrong_profile = search_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "c" * 64})
    with pytest.raises(ValueError, match="hte_bridge_manifest_lineage_mismatch"):
        _assert_manifest_inputs(
            manifest_for(
                (
                    owner_inputs[0],
                    (wrong_profile, "search_uncertainty_task_binding"),
                )
            ),
            owner_inputs,
            CoreArtifactRef,
        )

    base_inputs = (
        (physical_ref, "physical_source_materialization_binding"),
        (search_ref, "search_uncertainty_task_binding"),
    )
    point_result_ref = CoreArtifactRef(
        artifact_id="sha256:" + "3" * 64,
        kind="ir.hte_point_result",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "d" * 64,
    )
    basis_ref = CoreArtifactRef(
        artifact_id="sha256:" + "4" * 64,
        kind="ir.ate_inference_basis",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "e" * 64,
    )
    outcome_inputs = _numeric_outcome_inputs(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=basis_ref,
        base_inputs=base_inputs,
    )
    assert outcome_inputs == (
        (point_result_ref, "point_result"),
        (basis_ref, "inference_basis"),
        *base_inputs,
    )
    _assert_manifest_inputs(manifest_for(outcome_inputs), outcome_inputs, CoreArtifactRef)
    with pytest.raises(ValueError, match="hte_bridge_manifest_lineage_mismatch"):
        _assert_manifest_inputs(
            manifest_for(
                ((point_result_ref, "point_result"), *base_inputs, (basis_ref, "inference_basis"))
            ),
            outcome_inputs,
            CoreArtifactRef,
        )
    assert _numeric_outcome_inputs(
        result_ref=point_result_ref,
        result_role="point_result",
        inference_basis_ref=None,
        base_inputs=base_inputs,
    ) == ((point_result_ref, "point_result"), *base_inputs)
    hte_result_ref = CoreArtifactRef(
        artifact_id="sha256:" + "5" * 64,
        kind="ir.hte_result",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "f" * 64,
    )
    assert _numeric_outcome_inputs(
        result_ref=hte_result_ref,
        result_role="hte_result",
        inference_basis_ref=basis_ref,
        base_inputs=base_inputs,
    ) == ((hte_result_ref, "hte_result"), (basis_ref, "inference_basis"), *base_inputs)

    assert _owner_binding_inputs(
        materialization_binding_ref=physical_ref,
        search_uncertainty_task_binding_ref=None,
    ) == ((physical_ref, "physical_source_materialization_binding"),)


def test_portable_owner_refusal_finalizes_and_projection_is_load_bearing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Finalize a real owner-written refusal and reject removal of ref projection."""
    pytest.importorskip(
        "econml",
        reason="the DML selector refusal test requires the installed EconML package",
    )
    pytest.importorskip(
        "joblib",
        reason="the DML selector refusal test requires the installed joblib package",
    )
    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

    import polisyos.foundry.methods.selection.history as selection_history
    from polisyos.common.canonical_profile import CanonicalProfileRefusalError
    from polisyos.core.artifacts import (
        ArtifactRef as CoreArtifactRef,
    )
    from polisyos.core.artifacts import (
        read_core_json_artifact_bounded,
        validate_core_model_bounded_read,
    )
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchor,
        OwnedAttemptAnchorDispatchContext,
        OwnedAttemptAnchorRef,
    )
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        _validate_method_execution_selection_wire_payload,
    )
    from polisyos.core.security.tenant_context import tenant_scope
    from polisyos.foundry.methods.catalog.causal import hte_v2
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore
    from polisyos.ir.analytics.hte import load_hte_outcome, load_hte_refusal_diagnostic
    from polisyos.ir.registry.refs import HTEOutcomeRef, HTERefusalDiagnosticRef
    from polisyos.runtime.http.services.control import owned_attempt_anchor as owner_anchor_module
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        resolve_owned_attempt_anchor_association,
    )
    from polisyos.scientist.compute import hte_outcome_bridge

    attempted_fit_paths: list[bool] = []
    runtime_contexts: list[OwnedAttemptAnchorDispatchContext] = []

    def reject_fit_path(*_args: object, **_kwargs: object) -> Any:
        attempted_fit_paths.append(True)
        raise AssertionError("the unsupported model selector must refuse before estimator work")

    monkeypatch.setattr(hte_v2, "_method_result", reject_fit_path)

    pure_step_with_runtime_context = hte_v2.DoubleMachineLearningV2.pure_step_with_runtime_context

    def record_runtime_context(
        state: object,
        params: dict[str, Any],
        *,
        runtime_context: OwnedAttemptAnchorDispatchContext,
    ) -> dict[str, Any]:
        assert params["model_type"] == "unsupported_profile_sentinel"
        assert type(runtime_context) is OwnedAttemptAnchorDispatchContext
        runtime_contexts.append(runtime_context)
        return pure_step_with_runtime_context(
            state,
            params,
            runtime_context=runtime_context,
        )

    monkeypatch.setattr(
        hte_v2.DoubleMachineLearningV2,
        "pure_step_with_runtime_context",
        staticmethod(record_runtime_context),
    )
    monkeypatch.setattr(
        selection_history,
        "_GLOBAL_HISTORY",
        SelectionHistoryStore(
            persist_path=tmp_path / "selection_history" / "executions.jsonl",
            auto_persist=True,
        ),
    )
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        service = env["app"].state._control_service
        stop_embedded_control_worker(service)
        source_ref = _put_hte_input(
            service,
            tenant_id=env["tenant_a"],
            cell_id=env["cell_a"],
        )
        with tenant_scope(None, tenant_id=env["tenant_a"], cell_id=env["cell_a"]):
            response = env["client"].post(
                "/api/v1/control/runs",
                json={
                    "observational_input": {
                        "protocol": "method_input_envelope_v1",
                        "source_ref": source_ref.model_dump(mode="json"),
                        "method": {
                            "fqn": "causal.hte.double_ml@2.0.0",
                            "params": {"model_type": "unsupported_profile_sentinel"},
                        },
                        "hte_request": {
                            "schema_version": ("polisyos.runtime.observational_hte_request.v2"),
                            "estimand": "mean_effect_over_selected_x",
                            "target_scope": "selected_evaluation_rows",
                            "outcome_variable_id": "outcome.effect",
                            "treatment_variable_id": "treatment.policy",
                            "control_value": 0.0,
                            "treated_value": 1.0,
                            "alpha": 0.05,
                            "requested_guarantee": "candidate_point",
                        },
                    }
                },
            )
        assert response.status_code == 200, response.text
        accepted = response.json()
        job_id = accepted["job_id"]
        run_id = accepted["run_id"]
        assert (
            dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=job_id,
            )
            == job_id
        )

        record = service._control_store.get_latest_job_by_run(run_id)
        assert record is not None and record.state == "completed", (
            f"state={getattr(record, 'state', None)!r}; "
            f"error={getattr(record, 'error_message', None)!r}; "
            f"runtime_context_calls={len(runtime_contexts)}"
        )
        assert isinstance(record.method_execution_selection, dict)
        selection = _validate_method_execution_selection_wire_payload(
            record.method_execution_selection
        )
        assert type(selection) is DirectMethodExecutionSelection
        assert selection.hte is not None and selection.hte.kind == "refusal"
        assert selection.refusal_diagnostic_ref is not None
        assert selection.point_result_ref is None
        assert selection.hte_result_ref is None
        assert selection.inference_basis_ref is None
        assert not attempted_fit_paths
        assert len(runtime_contexts) == 1
        assert runtime_contexts[0].anchor_ref.model_dump(mode="json") == (
            selection.owned_attempt_anchor_ref.model_dump(mode="json")
        )

        with tenant_scope(None, tenant_id=env["tenant_a"], cell_id=env["cell_a"]):
            anchor_ref = OwnedAttemptAnchorRef.model_validate(
                selection.owned_attempt_anchor_ref.model_dump(mode="json"),
                strict=True,
            )
            anchor_bounded = read_core_json_artifact_bounded(
                service._artifact_store,
                CoreArtifactRef.model_validate(anchor_ref.model_dump(mode="json"), strict=True),
                limits=service._observational_read_limits(),
            )
            anchor = validate_core_model_bounded_read(OwnedAttemptAnchor, anchor_bounded)
            context = OwnedAttemptAnchorDispatchContext(
                anchor_ref=anchor_ref,
                input_capture=anchor.input_capture,
                method_abi_digest=anchor.method_abi_digest,
            )
            association = resolve_owned_attempt_anchor_association(
                service=service,
                anchor_ref=anchor_ref,
            )
            assert association.outcome_kind == "refusal"
            assert association.outcome_ref.model_dump(mode="json") == (
                selection.hte_outcome_ref.model_dump(mode="json")
            )
            assert association.refusal_diagnostic_ref.model_dump(mode="json") == (
                selection.refusal_diagnostic_ref.model_dump(mode="json")
            )

            result_bounded = read_core_json_artifact_bounded(
                service._artifact_store,
                selection.method_result_ref,
                limits=service._observational_read_limits(),
            )
            assert isinstance(result_bounded.value, dict)
            writer_ready = result_bounded.value["hte_outcome_write_ready"]
            assert writer_ready["kind"] == "refusal"
            assert writer_ready["refusal_stage"] == "prepare"
            assert writer_ready["refusal_reason"] == "method_profile_unavailable"
            assert writer_ready["diagnostic_code"] == "dml_profile_invalid"
            base_limitations = tuple(writer_ready["limitations"])
            assert base_limitations

            original_profiled_read = owner_anchor_module._read_profiled_value

            def refuse_selected_payload_mutation(
                target_ref: Any,
                *,
                expected_kind: str,
                expected_error: str,
                mutate: Any,
            ) -> None:
                target_identity = target_ref.model_dump(mode="json")

                def altered_profiled_read(**kwargs: Any) -> Any:
                    bounded, payload = original_profiled_read(**kwargs)
                    if (
                        kwargs["expected_kind"] == expected_kind
                        and kwargs["selected_ref"].model_dump(mode="json") == target_identity
                    ):
                        assert isinstance(payload, dict)
                        return bounded, mutate(dict(payload))
                    return bounded, payload

                monkeypatch.setattr(
                    owner_anchor_module, "_read_profiled_value", altered_profiled_read
                )
                try:
                    with pytest.raises(ValueError, match=expected_error):
                        resolve_owned_attempt_anchor_association(
                            service=service,
                            anchor_ref=anchor_ref,
                        )
                finally:
                    monkeypatch.setattr(
                        owner_anchor_module,
                        "_read_profiled_value",
                        original_profiled_read,
                    )

            def remove_writer_limitations(payload: dict[str, Any]) -> dict[str, Any]:
                payload["limitations"] = [
                    value for value in payload["limitations"] if value not in base_limitations
                ]
                return payload

            refuse_selected_payload_mutation(
                selection.refusal_diagnostic_ref,
                expected_kind="ir.hte_refusal_diagnostic",
                expected_error="owned_attempt_refusal_diagnostic_content_mismatch",
                mutate=remove_writer_limitations,
            )

            def add_contradictory_source_claim(payload: dict[str, Any]) -> dict[str, Any]:
                payload["limitations"].append("source_variable_identity_established")
                return payload

            refuse_selected_payload_mutation(
                selection.refusal_diagnostic_ref,
                expected_kind="ir.hte_refusal_diagnostic",
                expected_error="owned_attempt_refusal_diagnostic_content_mismatch",
                mutate=add_contradictory_source_claim,
            )

            def change_diagnostic_binding_identity(payload: dict[str, Any]) -> dict[str, Any]:
                payload["materialization_binding_ref"]["artifact_id"] = "sha256:" + "0" * 64
                return payload

            refuse_selected_payload_mutation(
                selection.refusal_diagnostic_ref,
                expected_kind="ir.hte_refusal_diagnostic",
                expected_error="owned_attempt_refusal_diagnostic_content_mismatch",
                mutate=change_diagnostic_binding_identity,
            )

            def remove_no_effect_fact(payload: dict[str, Any]) -> dict[str, Any]:
                assert "no_effect_estimate_published" in payload["limitations"]
                payload["limitations"].remove("no_effect_estimate_published")
                return payload

            refuse_selected_payload_mutation(
                selection.hte_outcome_ref,
                expected_kind="ir.hte_outcome",
                expected_error="owned_attempt_refusal_outcome_content_mismatch",
                mutate=remove_no_effect_fact,
            )

            # Import the canonical bridge normally, then persist from the actual
            # owner-written anchor, MethodResult, and MethodEvidence refs.
            finalized = hte_outcome_bridge.persist_runtime_hte_outcome(
                store=service._artifact_store,
                writer_ready=writer_ready,
                owned_attempt_anchor_context=context,
                method_result_ref=selection.method_result_ref,
                method_evidence_ref=selection.method_evidence_ref,
            )
            assert finalized.summary.kind == "refusal"
            assert finalized.artifact_refs.refusal_diagnostic_ref is not None
            outcome_ref = HTEOutcomeRef.model_validate(
                finalized.artifact_refs.hte_outcome_ref.model_dump(mode="json"),
                strict=True,
            )
            diagnostic_ref = HTERefusalDiagnosticRef.model_validate(
                finalized.artifact_refs.refusal_diagnostic_ref.model_dump(mode="json"),
                strict=True,
            )
            outcome = load_hte_outcome(service._artifact_store, outcome_ref)
            diagnostic = load_hte_refusal_diagnostic(service._artifact_store, diagnostic_ref)
            assert outcome.kind == "refusal"
            assert outcome.refusal_diagnostic_ref == diagnostic_ref
            assert diagnostic.method_result_ref.model_dump(mode="json") == (
                selection.method_result_ref.model_dump(mode="json")
            )
            assert diagnostic.owned_attempt_anchor_ref.model_dump(mode="json") == (
                anchor_ref.model_dump(mode="json")
            )
            assert finalized.summary.owned_attempt_anchor_ref.model_dump(mode="json") == (
                anchor_ref.model_dump(mode="json")
            )

            # The owner facts remain present while the cross-owner converter is
            # removed. Strict ref validation then rejects the Core model object.
            assert anchor_ref.manifest_profile_sha256 is not None
            assert writer_ready["method_profile_id"] == "econml.dml.point_only@2.0"

            def without_projection(ref: Any, model_type: type[Any]) -> Any:
                return model_type.model_validate(ref, strict=True)

            monkeypatch.setattr(hte_outcome_bridge, "_ir_ref", without_projection)
            with pytest.raises(ValidationError):
                hte_outcome_bridge.persist_runtime_hte_outcome(
                    store=service._artifact_store,
                    writer_ready=writer_ready,
                    owned_attempt_anchor_context=context,
                    method_result_ref=selection.method_result_ref,
                    method_evidence_ref=selection.method_evidence_ref,
                )

            # The actual resource-policy object is re-read at the finalizer's
            # bounded owner boundary; malformed view identity and schema fail.
            policy_ref = CoreArtifactRef.model_validate(
                anchor.resource_policy_ref.model_dump(mode="json"),
                strict=True,
            )
            policy_limits = service._observational_read_limits()
            with pytest.raises((CanonicalProfileRefusalError, ValueError)):
                hte_outcome_bridge._read_bounded(
                    service._artifact_store,
                    policy_ref.model_copy(update={"kind": "runtime.wrong_kind"}),
                    limits=policy_limits,
                    artifact_ref_type=CoreArtifactRef,
                    schema_name="polisyos.runtime.ObservationalInputResourcePolicy",
                    schema_version="1.0",
                )
            with pytest.raises((CanonicalProfileRefusalError, ValueError)):
                hte_outcome_bridge._read_bounded(
                    service._artifact_store,
                    policy_ref.model_copy(update={"manifest_profile_sha256": "sha256:" + "0" * 64}),
                    limits=policy_limits,
                    artifact_ref_type=CoreArtifactRef,
                    schema_name="polisyos.runtime.ObservationalInputResourcePolicy",
                    schema_version="1.0",
                )
            with pytest.raises(ValueError, match="hte_bridge_selected_manifest_identity_mismatch"):
                hte_outcome_bridge._read_bounded(
                    service._artifact_store,
                    policy_ref,
                    limits=policy_limits,
                    artifact_ref_type=CoreArtifactRef,
                    schema_name="polisyos.runtime.WrongPolicySchema",
                    schema_version="1.0",
                )
    finally:
        close_runtime_api_env(env)
