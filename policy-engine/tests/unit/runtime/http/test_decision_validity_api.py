from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import EpochValidityBatchRequest
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.security.identity import PolicyOSRole
from polisyos.scientist.validation.decision_validity import DecisionValidityService
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    return store.put_json(
        payload,
        PutOptions(
            kind=kind,
            media_type="application/json",
            schema=SchemaInfo(name=kind, version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def test_epoch_batch_request_has_no_status_reason_dependency_keys_or_verifier() -> None:
    fields = set(EpochValidityBatchRequest.model_fields)
    assert fields == {"transition_artifact_ref", "requested_query_context_ref"}
    ref = {
        "artifact_id": "sha256:" + "1" * 64,
        "kind": "chronology.epoch_transition",
        "media_type": "application/vnd.polisyos.chronology+json",
    }
    for forbidden in (
        "status",
        "reason",
        "dependency_keys",
        "dedupe_key",
        "verifier",
        "targets",
    ):
        with pytest.raises(ValidationError):
            EpochValidityBatchRequest.model_validate(
                {
                    "transition_artifact_ref": ref,
                    "requested_query_context_ref": "sha256:" + "2" * 64,
                    forbidden: "caller-controlled",
                }
            )


def test_generation_control_caller_cannot_supply_epoch_targets_or_status() -> None:
    ref = {
        "artifact_id": "sha256:" + "1" * 64,
        "kind": "chronology.epoch_transition",
        "media_type": "application/vnd.polisyos.chronology+json",
    }

    with pytest.raises(ValidationError):
        EpochValidityBatchRequest.model_validate(
            {
                "transition_artifact_ref": ref,
                "requested_query_context_ref": "sha256:" + "2" * 64,
                "targets": ["packet-from-caller"],
                "status": "active",
            }
        )


def test_epoch_batch_http_preserves_signature_failure_vocabulary(runtime_api_env) -> None:
    bearer = _fixture_bearer("decision-validity-signature-failure")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-decision-validity-signature-failure",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    class _SignatureRejectingVerifier:
        def verify(self, **_kwargs):
            raise ValueError("signature_unverified")

    with client:
        client.app.state._control_service._decision_validity_service._epoch_transition_verifier = (
            _SignatureRejectingVerifier()
        )
        response = client.post(
            "/api/v1/control/decision-validity/epoch-batches",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={
                "transition_artifact_ref": {
                    "artifact_id": runtime_api_env["root_artifact_id"],
                    "kind": "chronology.epoch_transition",
                    "media_type": "application/vnd.polisyos.chronology+json",
                },
                "requested_query_context_ref": "sha256:" + "d" * 64,
            },
        )

    assert response.status_code == 422
    assert response.json()["code"] == "signature_unverified"


def test_generic_http_event_cannot_write_through_pending_epoch_batch(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _epoch_batch_fixture,
    )

    bearer = _fixture_bearer("decision-validity-generic-epoch-refusal")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-decision-validity-generic-epoch-refusal",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    _, owner, verifier, transition, query_ref, packet_rows = _epoch_batch_fixture(
        runtime_api_env["cas_root"],
        packet_count=1,
    )

    def crash_before_first_packet(**_kwargs):
        raise RuntimeError("injected_pending_epoch_batch")

    monkeypatch.setattr(owner, "_apply_event_to_packet", crash_before_first_packet)
    with pytest.raises(RuntimeError, match="injected_pending_epoch_batch"):
        owner.admit_epoch_validity_batch(
            transition_artifact_ref=transition,
            requested_query_context_ref=query_ref,
        )
    monkeypatch.undo()
    pending_before = owner._state.list_epoch_pending()
    packet_ref = packet_rows[0][0]
    state_before = owner._state.load_packet(packet_ref)
    assert len(pending_before) == 1
    assert state_before is not None and state_before.lifecycle_events == []

    with client:
        control = client.app.state._control_service
        outbox_before = control._control_store.list_outbox_events(state=None, limit=500)
        response = client.post(
            "/api/v1/control/decision-validity/events",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={
                "trigger_type": "historical_semantic_revision",
                "status": "stale",
                "reason": "caller_cannot_clear_or_rewrite_epoch_pending",
                "dependency_keys": ["epoch::owner-fixture"],
                "source_ref": "epoch://generic-caller",
            },
        )
        outbox_after = control._control_store.list_outbox_events(state=None, limit=500)

    assert response.status_code == 422
    assert response.json()["code"] == "semantic_epoch_dependency_requires_owner_batch"
    restarted = DecisionValidityService(owner._store, epoch_transition_verifier=verifier)
    assert restarted._state.list_epoch_pending() == pending_before
    state_after = restarted._state.load_packet(packet_ref)
    assert state_after is not None and state_after.lifecycle_events == []
    assert restarted.read_current_projection(packet_ref).status == DecisionValidityStatus.STALE
    assert outbox_after == outbox_before


def test_publish_decision_validity_event_updates_registered_packets(runtime_api_env) -> None:
    bearer = _fixture_bearer("decision-validity-publication")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=False,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-decision-validity-publication",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    store = FileSystemCAS(runtime_api_env["cas_root"])
    service = DecisionValidityService(store)
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="lineage_api_fixture",
        policy_fingerprint="policy_api_fixture_v1",
        normative_basis=DecisionBasisSection(
            dependencies=[
                DecisionDependencyRef(
                    kind=DecisionDependencyKind.NORM_PACK,
                    key="norm::api_fixture",
                )
            ]
        ),
    )
    baseline = DecisionValidityEvaluation(
        decision_lineage_key=envelope.decision_lineage_key,
        status=DecisionValidityStatus.ACTIVE,
        dependency_keys=envelope.dependency_keys(),
    )
    packet_ref = _put_json(
        store,
        {
            "schema_version": "3.4",
            "decision_validity_envelope": envelope.model_dump(mode="json"),
            "decision_validity_baseline": baseline.model_dump(mode="json"),
        },
        kind="scientist.decision_packet",
    )
    store.record_artifact_owner(
        packet_ref.artifact_id,
        tenant_id=runtime_api_env["tenant_a"],
        cell_id=cell.cell_id,
        writer="tests.runtime_http.decision_validity",
    )
    service.register_decision_packet(
        packet_ref=str(packet_ref.artifact_id),
        envelope=envelope,
        baseline=baseline,
    )

    with client:
        response = client.post(
            "/api/v1/control/decision-validity/events",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={
                "trigger_type": "law_change",
                "status": "requires_human_review",
                "reason": "fixture_api_law_changed",
                "dependency_keys": ["norm::api_fixture"],
                "source_ref": "law://fixture/api",
                "occurred_at": datetime(2026, 3, 12, 14, 0, tzinfo=UTC).isoformat(),
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["affected_packets"] == [str(packet_ref.artifact_id)]
    assert body["affected_statuses"] == {"requires_human_review": 1}

    summary = service.get_summary(str(packet_ref.artifact_id), force=True)
    assert summary["status"] == "requires_human_review"
    assert summary["lifecycle"]["events"][0]["reason"] == "fixture_api_law_changed"
