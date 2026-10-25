from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.security.tenant_context import tenant_scope

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.protocol import CoreJSONArtifactStore

pytestmark = pytest.mark.integration

_METHOD_FQN = "causal.hte.causal_forest@2.0.0"
_BASIS_KIND = "ir.ate_inference_basis"
_BASIS_SCHEMA = "polisyos.ir.ATEInferenceBasis"


def _put_hte_source(store: CoreJSONArtifactStore, *, fixture_tag: str) -> ArtifactRef:
    """Write a valid, selected 40-row HTE envelope with a distinct source identity."""
    from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo, SchemaInfo
    from polisyos.core.artifacts.store import PutOptions
    from polisyos.core.canon import CanonSpec

    row_count = 40
    payload = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"{fixture_tag}-{index}" for index in range(row_count)],
        "metadata": {"source": "owned_attempt_inference_basis_test", "fixture": fixture_tag},
    }
    ref = store.put_json(
        {
            "schema_version": "policyos.ir.observation.method_input_envelope.v1",
            "contract_target": {
                "contract_id": "foundry.causal.hte_observational_data.v1",
                "contract_fqn": (
                    "polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"
                ),
            },
            "contract_payload": payload,
        },
        PutOptions(
            kind="ir.observation_method_input",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.ir.ObservationMethodInputEnvelope",
                version="1.0",
            ),
            governance=ArtifactGovernanceInfo(classification="public"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    return ArtifactRef.model_validate(ref, strict=True)


def _request_payload(source_ref: ArtifactRef) -> dict[str, object]:
    return {
        "observational_input": {
            "protocol": "method_input_envelope_v1",
            "source_ref": source_ref.model_dump(mode="json"),
            "method": {"fqn": _METHOD_FQN},
            "hte_request": {
                "schema_version": "polisyos.runtime.observational_hte_request.v2",
                "estimand": "mean_effect_over_selected_x",
                "target_scope": "selected_evaluation_rows",
                "outcome_variable_id": "outcome.effect",
                "treatment_variable_id": "treatment.policy",
                "control_value": 0.0,
                "treated_value": 1.0,
                "alpha": 0.05,
                "requested_guarantee": "backend_conditional_interval",
            },
        }
    }


def test_native_point_fallback_association_binds_the_materialization_ref_and_rejects_drift(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A real native-diagnostic fallback basis joins its full owner materialization identity."""
    pytest.importorskip("econml")
    pytest.importorskip("joblib")

    from _helpers.control_worker import dispatch_one_control_job, stop_embedded_control_worker
    from _helpers.runtime_http import _record_fixture_owner

    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonArtifactBoundedRead,
        CoreJsonReadLimits,
    )
    from polisyos.core.artifacts.manifest import artifact_ref_identity_key
    from polisyos.core.contracts.runtime import _validate_method_execution_selection_wire_payload
    from polisyos.foundry.data_plane.bindings import prepare_hte_observational_input
    from polisyos.foundry.methods.catalog.causal import hte_v2 as hte_v2_module
    from polisyos.runtime.http.services.control import owned_attempt_anchor as owner_module
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        resolve_owned_attempt_anchor_association,
    )

    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    service = runtime_api_env["app"].state._control_service
    assert service is not None
    stop_embedded_control_worker(service)
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
    from polisyos.foundry.methods.selection.history import SelectionHistoryStore

    history_path = tmp_path / "selection-history" / "executions.jsonl"
    monkeypatch.setattr(
        MethodDispatcher,
        "_instance",
        MethodDispatcher(
            runtime_history=SelectionHistoryStore(persist_path=history_path, auto_persist=True)
        ),
    )

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        source_ref = _put_hte_source(service._artifact_store, fixture_tag="owned")
        _record_fixture_owner(
            service._artifact_store, source_ref, tenant_id=tenant_id, cell_id=cell_id
        )
        foreign_source_ref = _put_hte_source(service._artifact_store, fixture_tag="foreign")
        _record_fixture_owner(
            service._artifact_store, foreign_source_ref, tenant_id=tenant_id, cell_id=cell_id
        )
        foreign_prepared = prepare_hte_observational_input(
            store=service._artifact_store,
            source_ref=foreign_source_ref,
            protocol="method_input_envelope_v1",
            method_fqn=_METHOD_FQN,
            limits=service._observational_read_limits(),
            materialization_binding_version="physical_v1",
        )
        foreign_binding_ref = foreign_prepared.materialization_binding_ref
        assert foreign_binding_ref is not None
        assert foreign_binding_ref.manifest_profile_sha256 is not None
        response = runtime_api_env["client"].post(
            "/api/v1/control/runs", json=_request_payload(source_ref)
        )

    assert response.status_code == 200, response.text
    accepted = response.json()
    job_id = accepted["job_id"]
    run_id = accepted["run_id"]

    native_candidate_calls = 0
    original_native_candidate = hte_v2_module._native_interval_candidate

    def force_noncontaining_interval(*args: Any, **kwargs: Any) -> tuple[Any, str]:
        nonlocal native_candidate_calls
        native_candidate_calls += 1
        native_capture, reason = original_native_candidate(*args, **kwargs)
        assert native_capture is not None
        payload = native_capture.model_dump(mode="python")
        payload["native_lower_bound"] = native_capture.native_point + 1.0
        payload["native_upper_bound"] = native_capture.native_point + 2.0
        validated_capture = type(native_capture).model_validate(payload, strict=True)
        return validated_capture, reason

    monkeypatch.setattr(hte_v2_module, "_native_interval_candidate", force_noncontaining_interval)
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    record = service._control_store.get_job(job_id)
    assert native_candidate_calls == 1
    assert record is not None and record.state == "completed", (
        f"state={getattr(record, 'state', None)!r}; "
        f"error={getattr(record, 'error_message', None)!r}"
    )
    selection = _validate_method_execution_selection_wire_payload(record.method_execution_selection)
    assert selection.run_id == run_id
    assert selection.hte is not None and selection.hte.kind == "point_estimate"
    basis_ref = selection.hte.inference_basis_ref
    assert basis_ref is not None and basis_ref.manifest_profile_sha256 is not None
    anchor_ref = selection.owned_attempt_anchor_ref
    assert anchor_ref is not None

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        association = resolve_owned_attempt_anchor_association(
            service=service, anchor_ref=anchor_ref
        )
        assert association.outcome_kind == "point_estimate"
        selected_binding_ref = association.materialization_binding_ref
        assert selected_binding_ref is not None
        assert selected_binding_ref.manifest_profile_sha256 is not None
        assert artifact_ref_identity_key(selected_binding_ref) != artifact_ref_identity_key(
            foreign_binding_ref
        )

        original_read = owner_module._read_profiled_value
        basis_ref_payload = basis_ref.model_dump(mode="json")
        basis_bounded, basis_payload = original_read(
            service=service,
            selected_ref=basis_ref,
            limits=service._observational_read_limits(),
            expected_kind=_BASIS_KIND,
            expected_schema_name=_BASIS_SCHEMA,
            expected_schema_version="1.0",
        )
        assert basis_bounded.effective_ref.model_dump(mode="json") == basis_ref.model_dump(
            mode="json"
        )
        assert isinstance(basis_payload, dict)
        assert basis_payload["materialization_binding_ref"] == selected_binding_ref.model_dump(
            mode="json"
        )
        anchor = owner_module._read_owned_attempt_anchor(
            service=service,
            anchor_ref=anchor_ref,
        )
        writer_ready, _method_evidence_manifest = owner_module._read_owner_selected_method_outputs(
            service=service,
            anchor=anchor,
            anchor_ref=anchor_ref,
            method_result_ref=selection.method_result_ref,
            method_evidence_ref=selection.method_evidence_ref,
        )
        assert writer_ready.kind == "point_estimate"
        assert writer_ready.inference_reason == "native_inference_invalid"
        assert writer_ready.native_diagnostic is not None
        assert not (
            writer_ready.native_diagnostic.native_lower_bound
            <= writer_ready.point_estimate
            <= writer_ready.native_diagnostic.native_upper_bound
        )

        def refuse_basis_mutation(
            mutate: Callable[[dict[str, Any]], dict[str, Any]], *, expected_error: str
        ) -> None:
            reads = 0

            def altered_read(
                *,
                service: owner_module.OwnedAttemptAnchorRuntimeHost,
                selected_ref: ArtifactRef,
                limits: CoreJsonReadLimits,
                expected_kind: str,
                expected_schema_name: str,
                expected_schema_version: str,
            ) -> tuple[CoreJsonArtifactBoundedRead, object]:
                nonlocal reads
                bounded, payload = original_read(
                    service=service,
                    selected_ref=selected_ref,
                    limits=limits,
                    expected_kind=expected_kind,
                    expected_schema_name=expected_schema_name,
                    expected_schema_version=expected_schema_version,
                )
                if (
                    expected_kind == _BASIS_KIND
                    and selected_ref.model_dump(mode="json") == basis_ref_payload
                ):
                    reads += 1
                    assert isinstance(payload, dict)
                    return bounded, mutate(dict(payload))
                return bounded, payload

            monkeypatch.setattr(owner_module, "_read_profiled_value", altered_read)
            try:
                with pytest.raises(ValueError, match=expected_error):
                    resolve_owned_attempt_anchor_association(service=service, anchor_ref=anchor_ref)
                assert reads == 1
            finally:
                monkeypatch.setattr(owner_module, "_read_profiled_value", original_read)

        def omit_materialization_ref(payload: dict[str, Any]) -> dict[str, Any]:
            payload.pop("materialization_binding_ref")
            return payload

        refuse_basis_mutation(
            omit_materialization_ref,
            expected_error="owned_attempt_inference_basis_invalid",
        )

        def replace_binding_id(payload: dict[str, Any]) -> dict[str, Any]:
            payload["materialization_binding_ref"]["artifact_id"] = "sha256:" + "0" * 64
            return payload

        refuse_basis_mutation(
            replace_binding_id,
            expected_error="owned_attempt_inference_basis_binding_mismatch",
        )

        def replace_binding_profile(payload: dict[str, Any]) -> dict[str, Any]:
            payload["materialization_binding_ref"]["manifest_profile_sha256"] = "sha256:" + "f" * 64
            return payload

        refuse_basis_mutation(
            replace_binding_profile,
            expected_error="owned_attempt_inference_basis_binding_mismatch",
        )

        def replace_with_foreign_binding(payload: dict[str, Any]) -> dict[str, Any]:
            payload["materialization_binding_ref"] = foreign_binding_ref.model_dump(mode="json")
            return payload

        refuse_basis_mutation(
            replace_with_foreign_binding,
            expected_error="owned_attempt_inference_basis_binding_mismatch",
        )
