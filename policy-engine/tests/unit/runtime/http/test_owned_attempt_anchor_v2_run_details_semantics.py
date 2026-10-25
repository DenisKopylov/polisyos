from __future__ import annotations

import json
import math
import threading
from typing import Any

import pytest

from polisyos.core.artifacts.manifest import ArtifactGovernanceInfo, ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.owned_attempt_anchor import (
    OwnedAttemptAnchorRefusalAssociation,
    OwnedAttemptLifecycleEvent,
)
from polisyos.core.security.tenant_context import tenant_scope


def _put_v2_hte_source(
    service: Any,
    *,
    tenant_id: str,
    cell_id: str,
    wrong_target: bool = False,
) -> ArtifactRef:
    """Persist one profile-qualified, bounded synthetic HTE input."""
    row_count = 40
    payload = {
        "outcome": [float(index) / 10 + (index % 2) * 0.5 for index in range(row_count)],
        "treatment": [index % 2 for index in range(row_count)],
        "covariates": [[float(index), float(index % 5)] for index in range(row_count)],
        "confounders": [[float(index % 7)] for index in range(row_count)],
        "feature_names": ["age", "baseline"],
        "confounder_names": ["risk"],
        "sample_ids": [f"candidate-{index}" for index in range(row_count)],
        "metadata": {"source": "synthetic_candidate"},
    }
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        ref = service._artifact_store.put_json(
            {
                "schema_version": "policyos.ir.observation.method_input_envelope.v1",
                "contract_target": {
                    "contract_id": (
                        "foundry.causal.hte_observational_data.v0"
                        if wrong_target
                        else "foundry.causal.hte_observational_data.v1"
                    ),
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
                inputs=[],
                governance=ArtifactGovernanceInfo(classification="public"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
    return ArtifactRef.model_validate(ref, strict=True)


def _submit_v2_request(
    runtime_api_env: dict[str, Any],
    *,
    source_ref: ArtifactRef,
    method_fqn: str,
    target_scope: str,
    requested_guarantee: str,
) -> tuple[Any, dict[str, Any]]:
    """Create one persisted, refs-only observational request without dispatching it."""
    from _helpers.control_worker import stop_embedded_control_worker

    service = runtime_api_env["app"].state._control_service
    stop_embedded_control_worker(service)
    response = runtime_api_env["client"].post(
        "/api/v1/control/runs",
        json={
            "observational_input": {
                "protocol": "method_input_envelope_v1",
                "source_ref": source_ref.model_dump(mode="json"),
                "method": {"fqn": method_fqn},
                "hte_request": {
                    "schema_version": "polisyos.runtime.observational_hte_request.v2",
                    "estimand": "mean_effect_over_selected_x",
                    "target_scope": target_scope,
                    "outcome_variable_id": "outcome.effect",
                    "treatment_variable_id": "treatment.policy",
                    "control_value": 0.0,
                    "treated_value": 1.0,
                    "alpha": 0.05,
                    "requested_guarantee": requested_guarantee,
                },
            }
        },
    )
    assert response.status_code == 200, response.text
    return service, response.json()


def _submit_and_dispatch_v2_request(
    runtime_api_env: dict[str, Any],
    *,
    source_ref: ArtifactRef,
    method_fqn: str,
    target_scope: str,
    requested_guarantee: str,
) -> tuple[Any, dict[str, Any], Any]:
    """Create and dispatch one real control job through its ordinary worker."""
    from _helpers.control_worker import dispatch_one_control_job

    service, accepted = _submit_v2_request(
        runtime_api_env,
        source_ref=source_ref,
        method_fqn=method_fqn,
        target_scope=target_scope,
        requested_guarantee=requested_guarantee,
    )
    job_id = accepted["job_id"]
    assert (
        dispatch_one_control_job(
            store=service._control_store,
            handler=service._process_control_job,
            expected_job_id=job_id,
        )
        == job_id
    )
    record = service._control_store.get_job(job_id)
    assert record is not None
    return service, accepted, record


def test_bounded_store_preflight_uses_true_composite_refusal_without_io(
    runtime_api_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bounded reader fails closed with an exact reason before any transfer."""
    from polisyos.core.artifacts.canonical_profile import CoreJsonReadBoundsRefusalError
    from polisyos.core.artifacts.protocol import (
        CoreJSONArtifactBoundedManifestReader,
        CoreJSONArtifactBoundedManifestReceiptReader,
        CoreJSONArtifactBoundedMemberReader,
        CoreJSONArtifactProfileReader,
        CoreJSONArtifactStreamingReader,
        runtime_protocol_requirements,
    )
    from polisyos.runtime.http.services.control.owned_attempt_anchor import (
        _OwnedAttemptAnchorArtifactStore,
    )

    service = runtime_api_env["app"].state._control_service
    original_store = service._artifact_store
    composite_members = runtime_protocol_requirements(_OwnedAttemptAnchorArtifactStore)
    manifest_receipt_members = runtime_protocol_requirements(
        CoreJSONArtifactBoundedManifestReceiptReader
    )
    bounded_manifest_members = runtime_protocol_requirements(CoreJSONArtifactBoundedManifestReader)
    profile_members = runtime_protocol_requirements(CoreJSONArtifactProfileReader)
    streaming_members = runtime_protocol_requirements(CoreJSONArtifactStreamingReader)
    bounded_members = runtime_protocol_requirements(CoreJSONArtifactBoundedMemberReader)

    assert composite_members
    assert manifest_receipt_members
    assert bounded_manifest_members
    assert profile_members
    assert streaming_members
    assert bounded_members
    manifest_receipt_only = sorted(set(manifest_receipt_members) - set(streaming_members))
    bounded_manifest_only = sorted(set(bounded_manifest_members) - set(profile_members))
    member_open_only = sorted(
        set(bounded_members) - set(streaming_members) - set(manifest_receipt_members)
    )
    stream_only = sorted(
        set(streaming_members) - set(profile_members) - set(bounded_manifest_members)
    )
    store_only = sorted(set(composite_members) - set(bounded_members))
    assert manifest_receipt_only and bounded_manifest_only and member_open_only
    assert stream_only and store_only

    scenarios = (
        (
            {manifest_receipt_only[0]},
            "canon_profile_bounded_manifest_unavailable",
            "selected_manifest_reader_preflight",
            None,
        ),
        (
            {bounded_manifest_only[0]},
            "canon_profile_bounded_manifest_unavailable",
            "selected_manifest_reader_preflight",
            None,
        ),
        (
            {member_open_only[0]},
            "canon_profile_bounded_stream_unavailable",
            "bounded_member_open_preflight",
            None,
        ),
        (
            {store_only[0]},
            "owned_attempt_store_contract_unavailable",
            "bounded_store_protocol_preflight",
            store_only[0],
        ),
        (
            {stream_only[0]},
            "owned_attempt_store_contract_unavailable",
            "bounded_store_protocol_preflight",
            stream_only[0],
        ),
    )

    class PartialStoreProxy:
        def __init__(self, target: object, hidden: set[str]) -> None:
            self._target = target
            self._hidden = hidden
            self.called_methods: list[str] = []

        def __getattr__(self, name: str) -> Any:
            if name in self._hidden:
                raise AttributeError(name)
            member = getattr(self._target, name)
            if not callable(member):
                return member

            def call_without_widening_access(*args: Any, **kwargs: Any) -> Any:
                self.called_methods.append(name)
                return member(*args, **kwargs)

            return call_without_widening_access

    for hidden, code, stage, missing_member in scenarios:
        proxy = PartialStoreProxy(original_store, hidden)
        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(service, "_artifact_store", proxy)
            with pytest.raises(CoreJsonReadBoundsRefusalError) as caught:
                service._require_owned_attempt_anchor_bounded_store(
                    limits=service._observational_read_limits()
                )
        refusal = caught.value
        assert refusal.code == code
        assert refusal.failure_stage == stage
        assert refusal.source_usage_complete is True
        assert refusal.observed_manifest_bytes == 0
        assert refusal.observed_manifest_selection_bytes == 0
        assert refusal.observed_manifest_verification_bytes == 0
        assert refusal.observed_bytes == 0
        assert refusal.observed_depth == 0
        assert refusal.observed_elements == 0
        assert proxy.called_methods == []
        if missing_member is not None:
            assert isinstance(refusal.__cause__, TypeError)
            assert refusal.__cause__ is not None
            assert missing_member in str(refusal.__cause__)


def test_bounded_store_adapter_returns_the_checked_guarded_core_owner(
    runtime_api_env: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same checked owner refuses unscoped reads and keeps scoped reads guarded."""
    from polisyos.core.artifacts.canonical_profile import (
        CoreJsonReadBoundsRefusalError,
        read_core_json_artifact_bounded,
    )
    from polisyos.core.artifacts.ir_adapter import CoreToIRArtifactStoreAdapter
    from polisyos.core.artifacts.ownership import ArtifactOwnershipError
    from polisyos.fabric.connectors.resilience.circuit_breaker import (
        CircuitBreaker,
        CircuitBreakerConfig,
    )
    from polisyos.runtime.http.resilience import (
        BlockingDependencyGuard,
        GuardedDependencyProxy,
    )

    service = runtime_api_env["app"].state._control_service
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    source_ref = _put_v2_hte_source(service, tenant_id=tenant_id, cell_id=cell_id)
    backing_store = service._artifact_store
    guard = BlockingDependencyGuard(
        dependency_name="test-owned-attempt-bounded-adapter",
        timeout_seconds=2.0,
        breaker=CircuitBreaker(
            "test-owned-attempt-bounded-adapter",
            CircuitBreakerConfig(min_throughput=1),
        ),
    )
    guard_calls: list[str] = []
    guarded_run = guard.run

    def record_guarded_run(operation, *args, **kwargs):
        guard_calls.append(getattr(operation, "__name__", type(operation).__name__))
        return guarded_run(operation, *args, **kwargs)

    monkeypatch.setattr(guard, "run", record_guarded_run)
    guarded_owner = GuardedDependencyProxy(target=backing_store, guard=guard)
    adapter = CoreToIRArtifactStoreAdapter(guarded_owner)
    try:
        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(service, "_artifact_store", adapter)
            bounded_store = service._require_owned_attempt_anchor_bounded_store(
                limits=service._observational_read_limits()
            )
            assert bounded_store is guarded_owner
            assert bounded_store is not adapter

            with pytest.raises(CoreJsonReadBoundsRefusalError) as unscoped_caught:
                read_core_json_artifact_bounded(
                    bounded_store, source_ref, limits=service._observational_read_limits()
                )
            unscoped_refusal = unscoped_caught.value
            assert unscoped_refusal.code == "canon_profile_bounded_manifest_unavailable"
            assert unscoped_refusal.failure_stage == "selected_manifest_usage_unknown"
            assert unscoped_refusal.source_usage_complete is False
            assert unscoped_refusal.observed_manifest_bytes is None
            assert unscoped_refusal.observed_manifest_selection_bytes is None
            assert unscoped_refusal.observed_manifest_verification_bytes == 0
            assert unscoped_refusal.observed_payload_bytes == 0
            assert unscoped_refusal.observed_source_bytes is None
            assert isinstance(unscoped_refusal.__cause__, ArtifactOwnershipError)
            assert "active owner is required" in str(unscoped_refusal.__cause__)
            assert guard_calls == ["read_raw_manifest_bytes_bounded"]
            guard_calls.clear()

            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                bounded = read_core_json_artifact_bounded(
                    bounded_store, source_ref, limits=service._observational_read_limits()
                )
            assert bounded.effective_ref == source_ref
            assert bounded.value["contract_target"]["contract_id"] == (
                "foundry.causal.hte_observational_data.v1"
            )
            assert bounded.payload_integrity_verified is True
            assert bounded.observed_manifest_selection_bytes > 0
            assert bounded.observed_payload_bytes > 0
            assert bounded.observed_source_bytes == (
                bounded.observed_manifest_selection_bytes
                + bounded.observed_manifest_verification_bytes
                + bounded.observed_payload_bytes
            )
            assert "read_raw_manifest_bytes_bounded" in guard_calls
            assert "open_member_bounded" in guard_calls

        guard_calls.clear()

        class PartialBoundedOwner:
            """Hide the bounded stream while recording any attempted owner operation."""

            def __init__(self, target: object) -> None:
                self.target = target
                self.invoked: list[str] = []

            def __getattr__(self, name: str) -> Any:
                if name == "open_member_bounded":
                    raise AttributeError(name)
                member = getattr(self.target, name)
                if not callable(member):
                    return member

                def record_operation(*args: Any, **kwargs: Any) -> Any:
                    self.invoked.append(name)
                    return member(*args, **kwargs)

                return record_operation

        partial_owner = PartialBoundedOwner(guarded_owner)
        partial_adapter = CoreToIRArtifactStoreAdapter(partial_owner)
        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(service, "_artifact_store", partial_adapter)
            with pytest.raises(CoreJsonReadBoundsRefusalError) as caught:
                service._require_owned_attempt_anchor_bounded_store(
                    limits=service._observational_read_limits()
                )

        refusal = caught.value
        assert refusal.code == "canon_profile_bounded_stream_unavailable"
        assert refusal.failure_stage == "bounded_member_open_preflight"
        assert refusal.source_usage_complete is True
        assert refusal.observed_manifest_bytes == 0
        assert refusal.observed_manifest_selection_bytes == 0
        assert refusal.observed_manifest_verification_bytes == 0
        assert refusal.observed_payload_bytes == 0
        assert refusal.observed_depth == 0
        assert refusal.observed_elements == 0
        assert partial_owner.invoked == []
        assert guard_calls == []

        class AdapterSubclassWithOverriddenIo(CoreToIRArtifactStoreAdapter):
            """An unknown adapter subtype must prove its own complete read surface."""

            def get_raw_manifest_bytes(self, *args: Any, **kwargs: Any) -> bytes:
                raise AssertionError("subclass I/O must not be bypassed")

        derived_adapter = AdapterSubclassWithOverriddenIo(guarded_owner)
        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(service, "_artifact_store", derived_adapter)
            with pytest.raises(CoreJsonReadBoundsRefusalError) as derived_caught:
                service._require_owned_attempt_anchor_bounded_store(
                    limits=service._observational_read_limits()
                )
        assert derived_caught.value.code == "canon_profile_bounded_manifest_unavailable"
        assert derived_caught.value.failure_stage == "selected_manifest_reader_preflight"
        assert derived_caught.value.observed_source_bytes == 0
        assert guard_calls == []
    finally:
        guard.close()


def test_v2_interval_semantics_and_limitations_survive_fresh_run_details_get(
    runtime_api_env: dict[str, Any],
) -> None:
    """The ordinary GET preserves native interval semantics and candidate limits."""
    pytest.importorskip("econml")
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionSelection,
        _validate_method_execution_selection_wire_payload,
    )

    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    service = runtime_api_env["app"].state._control_service
    source_ref = _put_v2_hte_source(service, tenant_id=tenant_id, cell_id=cell_id)
    service, accepted, record = _submit_and_dispatch_v2_request(
        runtime_api_env,
        source_ref=source_ref,
        method_fqn="causal.hte.causal_forest@2.0.0",
        target_scope="population",
        requested_guarantee="backend_conditional_interval",
    )
    assert record.state == "completed"
    assert record.method_execution_selection is not None
    persisted = _validate_method_execution_selection_wire_payload(record.method_execution_selection)
    assert type(persisted) is DirectMethodExecutionSelection
    assert persisted.hte is not None
    assert persisted.hte.kind == "interval_estimate"
    assert persisted.hte.inference_status == "native_ate_inference_validated"
    assert persisted.owned_attempt_anchor_ref is not None

    run_id = accepted["run_id"]
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{run_id}")
    assert fresh.status_code == 200, fresh.text
    run = fresh.json()["run"]
    assert run["run_id"] != run_id
    assert run["control_job_id"] == accepted["job_id"]
    projection = run["method_execution_selection"]
    assert projection["status"] == "selected"
    assert projection["candidate_only"] is True
    assert projection["request"]["method_fqn"] == "causal.hte.causal_forest@2.0.0"
    selection = projection["selection"]
    assert selection["job_id"] == accepted["job_id"]
    assert selection["run_id"] == run_id
    assert selection["attempt"] == record.attempt
    assert selection["owned_attempt_anchor_ref"] == persisted.owned_attempt_anchor_ref.model_dump(
        mode="json"
    )

    hte = selection["hte"]
    expected = persisted.hte
    assert expected is not None
    assert hte["kind"] == "interval_estimate"
    assert hte["method_profile_id"] == "econml.causal_forest_dml.native_mean@2.0"
    assert hte["method_abi_digest"] == expected.method_abi_digest
    assert hte["inference_status"] == "native_ate_inference_validated"
    assert hte["inference_reason"] is None
    assert hte["requested_alpha"] == 0.05
    assert hte["confidence_level"] == pytest.approx(0.95)
    assert hte["requested_guarantee"] == "backend_conditional_interval"
    assert hte["computed_guarantee"] == "backend_conditional_interval"
    assert hte["lower_bound"] <= hte["point_estimate"] <= hte["upper_bound"]
    assert math.isfinite(hte["lower_bound"])
    assert math.isfinite(hte["point_estimate"])
    assert math.isfinite(hte["upper_bound"])
    assert hte["point_result_ref"] is None
    assert expected.hte_result_ref is not None
    assert expected.inference_basis_ref is not None
    assert hte["hte_result_ref"] == expected.hte_result_ref.model_dump(mode="json")
    assert hte["inference_basis_ref"] == expected.inference_basis_ref.model_dump(mode="json")
    assert hte["hte_result_ref"]["kind"] == "ir.hte_result"
    assert hte["hte_result_ref"]["manifest_profile_sha256"] is not None

    relation = hte["target_relation"]
    assert relation["requested_scope"] == "population"
    assert relation["computed_scope"] == "selected_evaluation_rows"
    assert relation["scope_disposition"] == "requested_claim_not_satisfied"
    assert relation["requested_guarantee"] == "backend_conditional_interval"
    assert relation["computed_guarantee"] == "backend_conditional_interval"
    assert relation["alpha_status"] == "recomputed"
    assert relation["profile_status"] == "qualified"
    assert relation["guarantee_disposition"] == "satisfied"
    assert relation["estimand_status"] == "not_established"
    assert relation["overall_disposition"] == "requested_claim_not_satisfied"
    assert hte["measure_unit_status"] == "not_established"
    assert hte["measure_unit"] is None
    assert {
        "target_population_not_established_by_this_fit",
        "outcome_measure_unit_not_established",
        "causal_interpretation_is_conditional_on_declared_assumptions",
        "source_variable_identity_not_established",
    }.issubset(set(hte["limitations"]))
    assert set(projection["limitations"]) == {
        "candidate_input_not_external_truth",
        "scientific_validity_not_established",
        "units_and_context_not_established",
        "source_access_revalidation_not_established",
    }
    assert "covariates" not in fresh.text
    assert "cate_values" not in fresh.text


def test_v2_input_refusal_is_visible_through_fresh_run_details_get(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker refusal is served as a typed refusal, never a selected result."""
    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    service = runtime_api_env["app"].state._control_service
    source_ref = _put_v2_hte_source(
        service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        wrong_target=True,
    )
    service, accepted, record = _submit_and_dispatch_v2_request(
        runtime_api_env,
        source_ref=source_ref,
        method_fqn="causal.hte.forest_dr@2.0.0",
        target_scope="selected_evaluation_rows",
        requested_guarantee="candidate_point",
    )
    assert record.state == "failed"
    assert record.method_execution_selection is None
    terminal_event = service._control_store.get_job_terminal_source_event_record(accepted["job_id"])
    assert terminal_event.event_type == "job_failed"
    assert terminal_event.payload["owned_attempt_failure_disposition"] == "input_refused"

    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        fresh = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert fresh.status_code == 200, fresh.text
    projection = fresh.json()["run"]["method_execution_selection"]
    assert projection["status"] == "input_refused"
    assert projection["candidate_only"] is True
    assert projection["refusal_code"] == "observational_input_refused"
    assert projection["limitations"] == ["input_refused_before_dispatch"]
    assert projection["selection"] is None
    refusal = projection["input_refusal"]
    assert refusal["schema_version"] == "1.0"
    assert refusal["status"] == "input_refusal_reconciled"
    assert refusal["job_id"] == accepted["job_id"]
    assert refusal["run_id"] == accepted["run_id"]
    typed_refusal = OwnedAttemptAnchorRefusalAssociation.model_validate_json(
        json.dumps(refusal), strict=True
    )
    expected_failed_event = OwnedAttemptLifecycleEvent(
        event_id=terminal_event.event_id,
        job_id=terminal_event.job_id,
        event_type=terminal_event.event_type,
        payload_sha256=terminal_event.payload_sha256,
        created_at=terminal_event.created_at,
    )
    assert typed_refusal.job_failed_event == expected_failed_event
    assert (typed_refusal.job_id, typed_refusal.run_id, typed_refusal.attempt) == (
        accepted["job_id"],
        accepted["run_id"],
        record.attempt,
    )
    assert typed_refusal.refusal.refusal_code == "hte_contract_target_mismatch"
    assert not any(
        key in refusal for key in ("method_result_ref", "method_evidence_ref", "outcome_ref")
    )
    assert "contract_payload" not in fresh.text
    assert "covariates" not in fresh.text
    core_run_id = fresh.json()["run"]["run_id"]
    assert record.progress["core_run_id"] == core_run_id
    assert record.progress["core_run_attempt"] == record.attempt

    # The historical job_running lease value remains well-formed, canonical UTC,
    # and later than its event even after the current row has been released.
    control_store = service._control_store._target
    running_event = control_store._latest_control_job_lifecycle_event_record(
        job_id=accepted["job_id"], event_type="job_running"
    )
    with control_store._sqlite_connection() as connection:
        running_row = connection.execute(
            "SELECT payload_json FROM control_job_events WHERE event_id = ? AND job_id = ?",
            (running_event.event_id, accepted["job_id"]),
        ).fetchone()
        assert running_row is not None
        original_running_json = str(running_row[0])
    for label, historical_expiry in (
        ("missing", None),
        ("malformed", "not-a-time"),
        ("noncanonical", "2999-01-01T00:00:00"),
        ("before event", "1900-01-01T00:00:00+00:00"),
    ):
        changed_payload = json.loads(original_running_json)
        if historical_expiry is None:
            changed_payload.pop("lease_expires_at", None)
        else:
            changed_payload["lease_expires_at"] = historical_expiry
        changed_json = json.dumps(
            changed_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with control_store._sqlite_connection() as connection:
            changed = connection.execute(
                "UPDATE control_job_events SET payload_json = ? WHERE event_id = ? AND job_id = ?",
                (changed_json, running_event.event_id, accepted["job_id"]),
            )
            assert changed.rowcount == 1
            connection.commit()
        try:
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                invalid_history = runtime_api_env["client"].get(
                    f"/api/v1/runs/{accepted['run_id']}"
                )
            assert invalid_history.status_code == 403, f"{label}: {invalid_history.text}"
        finally:
            with control_store._sqlite_connection() as connection:
                restored = connection.execute(
                    "UPDATE control_job_events SET payload_json = ? WHERE event_id = ? AND job_id = ?",
                    (original_running_json, running_event.event_id, accepted["job_id"]),
                )
                assert restored.rowcount == 1
                connection.commit()

    # The terminal event must also preserve the fenced owner and attempt values.
    with control_store._sqlite_connection() as connection:
        terminal_row = connection.execute(
            "SELECT payload_json FROM control_job_events WHERE event_id = ? AND job_id = ?",
            (terminal_event.event_id, accepted["job_id"]),
        ).fetchone()
        assert terminal_row is not None
        original_terminal_json = str(terminal_row[0])
    for label, field, value in (
        ("terminal owner", "lease_owner", "different-terminal-owner"),
        ("terminal attempt", "attempt", record.attempt + 1),
    ):
        changed_payload = json.loads(original_terminal_json)
        changed_payload[field] = value
        changed_json = json.dumps(
            changed_payload,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        with control_store._sqlite_connection() as connection:
            changed = connection.execute(
                "UPDATE control_job_events SET payload_json = ? WHERE event_id = ? AND job_id = ?",
                (changed_json, terminal_event.event_id, accepted["job_id"]),
            )
            assert changed.rowcount == 1
            connection.commit()
        try:
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                invalid_terminal = runtime_api_env["client"].get(
                    f"/api/v1/runs/{accepted['run_id']}"
                )
            assert invalid_terminal.status_code == 403, f"{label}: {invalid_terminal.text}"
        finally:
            with control_store._sqlite_connection() as connection:
                restored = connection.execute(
                    "UPDATE control_job_events SET payload_json = ? WHERE event_id = ? AND job_id = ?",
                    (original_terminal_json, terminal_event.event_id, accepted["job_id"]),
                )
                assert restored.rowcount == 1
                connection.commit()

    # Removing the source-owned binding makes the same real GET fail closed.
    with monkeypatch.context() as binding_removed:
        binding_removed.setattr(
            service,
            "_resolve_observational_method_core_run_binding",
            lambda **_kwargs: None,
        )
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            removed = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
        assert removed.status_code == 403, removed.text

    # Each persisted identity component is load-bearing. A valid event, current lease,
    # and terminal manifest cannot compensate for a different job, attempt, or Core
    # run pointer in the consumer's progress record.
    for field, value in (
        ("job_id", "different-job"),
        ("attempt", record.attempt + 1),
        ("core_run_id", "different-core-run"),
        ("core_run_attempt", record.attempt + 1),
    ):
        drifted_progress = dict(record.progress)
        drifted_progress[field] = value
        service._control_store.upsert_progress(job_id=record.job_id, progress=drifted_progress)
        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            drifted_identity = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
        assert drifted_identity.status_code == 403, drifted_identity.text

    # Restore the exact owner pointer before the byte-drift control below.
    service._control_store.upsert_progress(job_id=record.job_id, progress=record.progress)

    # Change only the persisted JSON encoding after the route's first terminal-event
    # read. The owner resolver remains real; it sees the same event id and payload
    # value under different bytes, so the fresh GET must fail closed on digest drift.
    control_store = service._control_store._target
    original_resolver = service.resolve_owned_attempt_anchor_refusal_association
    tampered_event: dict[str, str | int] = {}

    def tamper_persisted_event_before_real_resolution(*, anchor_ref: Any) -> Any:
        with control_store._sqlite_connection() as connection:
            row = connection.execute(
                "SELECT payload_json FROM control_job_events "
                "WHERE event_id = ? AND job_id = ? AND event_type = 'job_failed'",
                (terminal_event.event_id, accepted["job_id"]),
            ).fetchone()
            assert row is not None
            original_payload_json = str(row[0])
            compact_payload_json = json.dumps(
                json.loads(original_payload_json),
                ensure_ascii=False,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            if compact_payload_json == original_payload_json:
                compact_payload_json = original_payload_json + " "
            updated = connection.execute(
                "UPDATE control_job_events SET payload_json = ? "
                "WHERE event_id = ? AND job_id = ? AND event_type = 'job_failed'",
                (compact_payload_json, terminal_event.event_id, accepted["job_id"]),
            )
            assert updated.rowcount == 1
            connection.commit()
        changed_event = control_store.get_job_terminal_source_event_record(accepted["job_id"])
        tampered_event.update(
            event_id=changed_event.event_id,
            payload_sha256=changed_event.payload_sha256,
        )
        return original_resolver(anchor_ref=anchor_ref)

    monkeypatch.setattr(
        service,
        "resolve_owned_attempt_anchor_refusal_association",
        tamper_persisted_event_before_real_resolution,
    )
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        drifted = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert drifted.status_code == 200, drifted.text
    drifted_projection = drifted.json()["run"]["method_execution_selection"]
    assert tampered_event["event_id"] == terminal_event.event_id
    assert tampered_event["payload_sha256"] != terminal_event.payload_sha256
    assert drifted_projection["status"] == "unavailable"
    assert drifted_projection["limitations"] == ["execution_outcome_not_established"]
    assert drifted_projection.get("input_refusal") is None


def test_v2_input_refusal_access_uses_verified_jwt_principals(
    runtime_api_env: dict[str, Any],
) -> None:
    """Authenticated tenant and cell denials use verified request claims."""
    from tests.unit.runtime.http.test_runtime_api_authz import (
        _AllowOPA,
        _build_secure_client,
        _claims,
        _fixture_bearer,
        _install_authorization_audit_capture,
    )

    tenant_a = runtime_api_env["tenant_a"]
    tenant_b = runtime_api_env["tenant_b"]
    secure_client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
    )
    token_a = _fixture_bearer("owned-refusal-tenant-a")
    token_b = _fixture_bearer("owned-refusal-tenant-b")
    token_wrong_cell = _fixture_bearer("owned-refusal-wrong-cell")
    provider.put_claim(
        token_a,
        _claims(tenant_id=tenant_a, cell_id=cell.cell_id, jti="jwt-owned-refusal-a"),
    )
    provider.put_claim(
        token_b,
        _claims(tenant_id=tenant_b, cell_id=cell.cell_id, jti="jwt-owned-refusal-b"),
    )
    provider.put_claim(
        token_wrong_cell,
        _claims(
            tenant_id=tenant_a,
            cell_id="cell-wrong",
            jti="jwt-owned-refusal-wrong-cell",
        ),
    )

    with secure_client:
        secure_client.headers.update(
            {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": tenant_a}
        )
        secure_env = dict(runtime_api_env)
        secure_env["app"] = secure_client.app
        secure_env["client"] = secure_client

        source_ref = _put_v2_hte_source(
            runtime_api_env["app"].state._control_service,
            tenant_id=tenant_a,
            cell_id=cell.cell_id,
            wrong_target=True,
        )
        service, accepted, record = _submit_and_dispatch_v2_request(
            secure_env,
            source_ref=source_ref,
            method_fqn="causal.hte.forest_dr@2.0.0",
            target_scope="selected_evaluation_rows",
            requested_guarantee="candidate_point",
        )
        assert record.state == "failed"
        assert record.method_execution_selection is None
        terminal_event = service._control_store.get_job_terminal_source_event_record(
            accepted["job_id"]
        )
        assert terminal_event.event_type == "job_failed"
        assert terminal_event.payload["owned_attempt_failure_disposition"] == "input_refused"

        path = f"/api/v1/runs/{accepted['run_id']}"
        owner = secure_client.get(path)
        assert owner.status_code == 200, owner.text
        owner_projection = owner.json()["run"]["method_execution_selection"]
        assert owner_projection["status"] == "input_refused"
        assert owner_projection["candidate_only"] is True
        assert owner_projection["selection"] is None

        audit = _install_authorization_audit_capture(secure_client)
        request_id = "owned-refusal-auth-cross-tenant"
        cross_tenant = secure_client.get(
            path,
            headers={
                "Authorization": f"Bearer {token_b}",
                "X-Tenant-ID": tenant_b,
                "X-Request-ID": request_id,
            },
        )
        assert cross_tenant.status_code == 403, cross_tenant.text
        assert cross_tenant.json().get("code") in {
            "run_tenant_mismatch",
            "authorization_binding_run_unresolved",
        }
        denied = [entry for entry in audit.entries if entry.get("request_id") == request_id]
        assert denied, audit.entries
        assert any(
            entry.get("tenant_id") == tenant_b and entry.get("subject") == "user-1"
            for entry in denied
        ), denied

        cross_cell = secure_client.get(
            path,
            headers={
                "Authorization": f"Bearer {token_wrong_cell}",
                "X-Tenant-ID": tenant_a,
                "X-Request-ID": "owned-refusal-auth-cross-cell",
            },
        )
        assert cross_cell.status_code == 403, cross_cell.text
        assert cross_cell.json().get("code") == "cell_binding_mismatch"


def test_live_method_attempt_is_visible_before_terminal_manifest_get(
    runtime_api_env: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A live lease binds the actual Core trace before it has a terminal manifest."""
    from _helpers.control_worker import dispatch_one_control_job

    tenant_id = runtime_api_env["tenant_a"]
    cell_id = runtime_api_env["cell_a"]
    service = runtime_api_env["app"].state._control_service
    source_ref = _put_v2_hte_source(
        service,
        tenant_id=tenant_id,
        cell_id=cell_id,
        wrong_target=True,
    )
    service, accepted = _submit_v2_request(
        runtime_api_env,
        source_ref=source_ref,
        method_fqn="causal.hte.forest_dr@2.0.0",
        target_scope="selected_evaluation_rows",
        requested_guarantee="candidate_point",
    )
    entered = threading.Event()
    release = threading.Event()
    original_complete = service._complete_observational_method_control_job
    held_core_run: dict[str, str] = {}

    def hold_completion_after_core_start(**kwargs: Any) -> Any:
        if threading.current_thread().name == "live-method-attempt":
            core_run_id = kwargs.get("core_run_id")
            core_run_context = kwargs.get("core_run_context")
            assert type(core_run_id) is str and core_run_id
            assert core_run_context is not None
            held_core_run["run_id"] = core_run_id
            entered.set()
            release.wait()
        return original_complete(**kwargs)

    monkeypatch.setattr(
        service,
        "_complete_observational_method_control_job",
        hold_completion_after_core_start,
    )
    dispatch_result: dict[str, Any] = {}

    def dispatch() -> None:
        try:
            dispatch_result["job_id"] = dispatch_one_control_job(
                store=service._control_store,
                handler=service._process_control_job,
                expected_job_id=accepted["job_id"],
            )
        except Exception as exc:  # surfaced in the test thread after cleanup
            dispatch_result["error"] = exc

    thread = threading.Thread(target=dispatch, name="live-method-attempt", daemon=True)
    thread.start()
    try:
        assert entered.wait(timeout=10), "method worker did not reach post-Core-start completion"
        running = service._control_store.get_job(accepted["job_id"])
        assert running is not None and running.state == "running"
        assert running.lease_owner and running.lease_expires_at is not None
        initial_expiry = running.lease_expires_at
        initial_running_event = service._control_store._latest_control_job_lifecycle_event_record(
            job_id=accepted["job_id"], event_type="job_running"
        )
        initial_event_expiry = initial_running_event.payload["lease_expires_at"]
        assert service._control_store.renew_job_lease(
            job_id=accepted["job_id"],
            worker_id=running.lease_owner,
            lease_seconds=120,
            expected_attempt=running.attempt,
        )
        renewed = service._control_store.get_job(accepted["job_id"])
        assert renewed is not None and renewed.lease_expires_at is not None
        assert renewed.lease_expires_at > initial_expiry
        renewed_running_event = service._control_store._latest_control_job_lifecycle_event_record(
            job_id=accepted["job_id"], event_type="job_running"
        )
        assert renewed_running_event.event_id == initial_running_event.event_id
        assert renewed_running_event.payload_sha256 == initial_running_event.payload_sha256
        assert renewed_running_event.payload["lease_expires_at"] == initial_event_expiry
        assert renewed.lease_expires_at.isoformat() != initial_event_expiry

        with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
            fresh = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
        assert fresh.status_code == 200, fresh.text
        run = fresh.json()["run"]
        assert run["run_id"] == held_core_run["run_id"]
        assert run["run_id"] != accepted["run_id"]
        assert run["source_kind"] == "core_run"
        assert run["status"] == "unknown"
        assert run["finished_at"] is None
        assert run["manifest_ref"] is None
        assert run["has_trace"] is True
        assert run["tenant_id"] == tenant_id
        assert run["cell_id"] == cell_id
        assert run["control_job_id"] == accepted["job_id"]
        projection = run["method_execution_selection"]
        assert projection["status"] == "accepted_pending"
        assert projection["selection"] is None

        # The consumer reads the real owner row. Wrong owner, stale current lease,
        # and changed attempt each deny the same ordinary stable-ID GET.
        control_store = service._control_store._target
        with control_store._sqlite_connection() as connection:
            owner_row = connection.execute(
                "SELECT lease_owner, lease_expires_at, attempt FROM control_jobs WHERE job_id = ?",
                (accepted["job_id"],),
            ).fetchone()
            assert owner_row is not None
            original_owner, original_expiry, original_attempt = owner_row
        owner_drift_cases = (
            ("owner", f"{original_owner}-drift", original_expiry, original_attempt),
            ("stale lease", original_owner, "2000-01-01T00:00:00+00:00", original_attempt),
            ("attempt", original_owner, original_expiry, original_attempt + 1),
        )
        for label, lease_owner, lease_expires_at, attempt in owner_drift_cases:
            with control_store._sqlite_connection() as connection:
                updated = connection.execute(
                    "UPDATE control_jobs SET lease_owner = ?, lease_expires_at = ?, attempt = ? "
                    "WHERE job_id = ?",
                    (lease_owner, lease_expires_at, attempt, accepted["job_id"]),
                )
                assert updated.rowcount == 1
                connection.commit()
            try:
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    owner_drift = runtime_api_env["client"].get(
                        f"/api/v1/runs/{accepted['run_id']}"
                    )
                assert owner_drift.status_code == 403, f"{label}: {owner_drift.text}"
            finally:
                with control_store._sqlite_connection() as connection:
                    restored = connection.execute(
                        "UPDATE control_jobs SET lease_owner = ?, lease_expires_at = ?, attempt = ? "
                        "WHERE job_id = ?",
                        (original_owner, original_expiry, original_attempt, accepted["job_id"]),
                    )
                    assert restored.rowcount == 1
                    connection.commit()

        # The active association comes from the current owner resolver. Removing
        # it while the Core trace remains present must deny the same stable ID.
        with monkeypatch.context() as binding_removed:
            binding_removed.setattr(
                service,
                "_resolve_observational_method_core_run_binding",
                lambda **_kwargs: None,
            )
            with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                removed = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
            assert removed.status_code == 403, removed.text

        # A semantic-equivalent rewrite of the immutable creation-event bytes
        # between owner reads cannot preserve the alias. Restore the test row
        # afterward so the worker's terminal refusal uses the original fixture.
        control_store = service._control_store._target
        original_created_reader = control_store._get_job_created_source_event_record
        created_payload_bytes: dict[str, str] = {}
        created_reads = 0

        def drift_creation_bytes_after_first_read(job_id: str) -> Any:
            nonlocal created_reads
            event = original_created_reader(job_id)
            created_reads += 1
            if created_reads == 1:
                with control_store._sqlite_connection() as connection:
                    row = connection.execute(
                        "SELECT payload_json FROM control_job_events "
                        "WHERE job_id = ? AND event_type = 'job_created'",
                        (job_id,),
                    ).fetchone()
                    assert row is not None
                    original_bytes = str(row[0])
                    created_payload_bytes["original"] = original_bytes
                    compact = json.dumps(
                        json.loads(original_bytes),
                        ensure_ascii=False,
                        allow_nan=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    changed = compact if compact != original_bytes else original_bytes + " "
                    created_payload_bytes["changed"] = changed
                    updated = connection.execute(
                        "UPDATE control_job_events SET payload_json = ? "
                        "WHERE job_id = ? AND event_type = 'job_created'",
                        (changed, job_id),
                    )
                    assert updated.rowcount == 1
                    connection.commit()
            return event

        with monkeypatch.context() as created_event_drift:
            created_event_drift.setattr(
                control_store,
                "_get_job_created_source_event_record",
                drift_creation_bytes_after_first_read,
            )
            try:
                with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
                    drifted_creation = runtime_api_env["client"].get(
                        f"/api/v1/runs/{accepted['run_id']}"
                    )
                assert drifted_creation.status_code == 403, drifted_creation.text
                assert created_reads >= 2
                assert created_payload_bytes["changed"] != created_payload_bytes["original"]
            finally:
                original_bytes = created_payload_bytes.get("original")
                if original_bytes is not None:
                    with control_store._sqlite_connection() as connection:
                        restored = connection.execute(
                            "UPDATE control_job_events SET payload_json = ? "
                            "WHERE job_id = ? AND event_type = 'job_created'",
                            (original_bytes, accepted["job_id"]),
                        )
                        assert restored.rowcount == 1
                        connection.commit()
    finally:
        release.set()
        thread.join(timeout=30)
    assert not thread.is_alive(), "refusal worker did not finish after release"
    assert "error" not in dispatch_result, str(dispatch_result.get("error"))
    assert dispatch_result.get("job_id") == accepted["job_id"]
    failed = service._control_store.get_job(accepted["job_id"])
    assert failed is not None and failed.state == "failed"
    assert failed.progress["state"] == "failed"
    assert failed.progress["phase"] == "direct_method_execution"
    assert failed.progress["job_id"] == accepted["job_id"]
    assert failed.progress["attempt"] == failed.attempt
    assert failed.progress["core_terminal_status"] == "error"
    assert failed.progress["core_run_attempt"] == failed.attempt
    assert failed.progress["core_run_id"] == run["run_id"]
    terminal_event = service._control_store.get_job_terminal_source_event_record(accepted["job_id"])
    assert terminal_event.event_type == "job_failed"
    assert terminal_event.payload["owned_attempt_failure_disposition"] == "input_refused"

    # After truthful failure finalization, the same owner-bound stable ID resolves
    # to the unchanged Core identity and carries the refusal projection.
    with tenant_scope(None, tenant_id=tenant_id, cell_id=cell_id):
        terminal_get = runtime_api_env["client"].get(f"/api/v1/runs/{accepted['run_id']}")
    assert terminal_get.status_code == 200, terminal_get.text
    terminal_run = terminal_get.json()["run"]
    assert terminal_run["run_id"] == run["run_id"]
    assert terminal_run["run_id"] != accepted["run_id"]
    assert terminal_run["source_kind"] == "core_run"
    assert terminal_run["status"] == "error"
    assert terminal_run["control_job_id"] == accepted["job_id"]
    assert terminal_run["method_execution_selection"]["status"] == "input_refused"


def test_refusal_limitations_derive_from_verified_physical_binding() -> None:
    """Bind refusal limitations to the typed writer and physical-only source facts."""
    import pytest

    from polisyos.core.artifacts.manifest import ArtifactRef as CoreArtifactRef
    from polisyos.foundry.data_plane.bindings import (
        HTEPhysicalArraySlotBinding,
        HTEPhysicalSourceMaterializationBinding,
    )
    from polisyos.foundry.methods.catalog.causal.hte_v2 import (
        HTEProducerResourceReceiptV1,
        HTEWriterReadyRefusalV1,
    )
    from polisyos.ir.observation.bundles import ContractCompatibilityTarget
    from polisyos.scientist.compute.hte_outcome_bridge import _expected_refusal_limitations

    method_profile_id = "econml.dml.point_only@2.0"
    artifact_ref = CoreArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="ir.observation_method_input",
        media_type="application/json",
        manifest_profile_sha256="sha256:" + "a" * 64,
    )
    row_order_sha256 = "sha256:" + "b" * 64
    binding = HTEPhysicalSourceMaterializationBinding(
        submitted_ref=artifact_ref,
        effective_ref=artifact_ref,
        source_protocol="method_input_envelope_v1",
        normalization="canonical_passthrough",
        contract_target=ContractCompatibilityTarget(
            contract_id="foundry.causal.hte_observational_data.v1",
            contract_fqn=("polisyos.foundry.methods.catalog.causal.protocols.HTEObservationalData"),
        ),
        effective_payload_sha256="sha256:" + "c" * 64,
        observation_count=2,
        row_order_basis="positional_row_ordinal",
        row_order_sha256=row_order_sha256,
        submitted_sample_ids_state="absent",
        effective_sample_ids_state="absent",
        submitted_confounders_state="absent",
        effective_confounders_state="absent",
        arrays=(
            HTEPhysicalArraySlotBinding(
                physical_slot="outcome_vector",
                payload_pointer="/contract_payload/outcome",
                array_shape=(2,),
                array_dtype="<f8",
                value_sha256="sha256:" + "d" * 64,
                row_order_sha256=row_order_sha256,
            ),
            HTEPhysicalArraySlotBinding(
                physical_slot="treatment_vector",
                payload_pointer="/contract_payload/treatment",
                array_shape=(2,),
                array_dtype="<i8",
                value_sha256="sha256:" + "e" * 64,
                row_order_sha256=row_order_sha256,
            ),
        ),
    )
    writer = HTEWriterReadyRefusalV1(
        method_fqn="causal.hte.double_ml@2.0.0",
        method_abi="2.0.0",
        method_profile_id=method_profile_id,
        resource_receipt=HTEProducerResourceReceiptV1(
            execution_status="not_started",
            method_profile_id=method_profile_id,
        ),
        limitations=("selected_input_or_method_profile_not_established",),
        refusal_stage="prepare",
        refusal_reason="method_profile_unavailable",
        diagnostic_code="dml_profile_invalid",
    )

    assert _expected_refusal_limitations(writer, binding) == (
        "selected_input_or_method_profile_not_established",
        "no_effect_estimate_published",
        "source_variable_identity_not_established",
    )
    contradictory_binding = binding.model_copy(update={"semantic_alignment_status": "established"})
    with pytest.raises(ValueError, match="hte_refusal_limitation_binding_semantics_invalid"):
        _expected_refusal_limitations(writer, contradictory_binding)
