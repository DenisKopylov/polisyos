from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.control import (
    DecisionValidityEventRequest,
    DecisionValidityEventResponse,
    EpochValidityBatchRequest,
)
from polisyos.core.contracts.decision_validity import (
    DecisionBasisSection,
    DecisionDependencyKind,
    DecisionDependencyRef,
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.contracts.runtime import ApiMeta
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.errors import RuntimeHTTPError
from polisyos.scientist.evidence.claims import (
    AppendOnlyClaimLedger,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
    build_default_claim_ledger_owner,
)
from polisyos.scientist.evidence.claims.audit import _persist_append_only_claim_ledger
from polisyos.scientist.evidence.claims.head_index import ClaimLifecycleBridgeNonReceipt
from polisyos.scientist.governance.continuous import load_lifecycle_bridge_result
from polisyos.scientist.governance.continuous.lifecycle_bridge import (
    EpochClaimLifecycleBridgeService,
    build_epoch_claim_lifecycle_bridge,
)
from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    LegalChangePerturbation,
    persist_governance_monitor_event,
    resolve_governance_monitor_event,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness
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


def _artifact_ref(store: FileSystemCAS, artifact_id: str) -> ArtifactRef:
    manifest = store.get_manifest(artifact_id)
    return ArtifactRef(
        artifact_id=manifest.artifact_id,
        kind=manifest.kind,
        media_type=manifest.media_type,
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


def test_monitor_event_request_arm_forbids_every_legacy_authority_field() -> None:
    monitor_ref = {
        "artifact_id": "sha256:" + "a" * 64,
        "kind": "scientist.governance_monitor_event",
        "media_type": "application/json",
    }

    request = DecisionValidityEventRequest.model_validate({"monitor_event_ref": monitor_ref})
    assert request.monitor_event_ref is not None

    forbidden_values = {
        "trigger_type": "law_change",
        "status": "stale",
        "reason": "caller-shaped",
        "dependency_keys": ["norm::caller"],
        "source_ref": "caller://source",
        "dedupe_key": "caller-dedupe",
        "occurred_at": datetime(2026, 8, 27, tzinfo=UTC).isoformat(),
        "payload": {"source_class": "appeal"},
    }
    for field, value in forbidden_values.items():
        with pytest.raises(ValidationError, match="monitor_event_ref arm"):
            DecisionValidityEventRequest.model_validate(
                {"monitor_event_ref": monitor_ref, field: value}
            )

    with pytest.raises(ValidationError, match="legacy arm"):
        DecisionValidityEventRequest.model_validate({"reason": "incomplete"})


def test_monitor_bridge_response_refs_are_an_all_or_none_receipt() -> None:
    ref = {
        "artifact_id": "sha256:" + "b" * 64,
        "kind": "scientist.governance_monitor_event",
        "media_type": "application/json",
    }
    base = {
        "meta": ApiMeta(request_id="request-ds18"),
        "event_id": "event-ds18",
        "dedupe_key": "dedupe-ds18",
        "message": "accepted",
    }
    with pytest.raises(ValidationError, match="bridge refs"):
        DecisionValidityEventResponse.model_validate({**base, "monitor_event_ref": ref})


def test_live_monitor_ref_reloads_bytes_and_persists_lifecycle_and_epoch_bindings(
    runtime_api_env,
) -> None:
    """The live POST must consume the exact event ref, not a parallel shaped class."""

    bearer = _fixture_bearer("decision-validity-monitor-ref")
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
            jti="jwt-decision-validity-monitor-ref",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    with client:
        control = client.app.state._control_service
        store = control._artifact_store
        claim = ClaimRecord(
            claim_id="claim-live-monitor",
            run_id="run-live-monitor",
            claim_type=ClaimType.FACTUAL,
            text="The live monitor claim remains append-only.",
            support_status=ClaimSupportStatus.SUPPORTED,
            publishability=ClaimPublishability.INTERNAL_ONLY,
            readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        )
        ledger_ref = _persist_append_only_claim_ledger(
            store,
            AppendOnlyClaimLedger(
                run_id="run-live-monitor",
                current_claims=[claim],
            ),
        )
        store.record_artifact_owner(
            ledger_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.runtime_http.ds18",
        )
        envelope = DecisionValidityEnvelope(
            decision_lineage_key="lineage-live-monitor",
            policy_fingerprint="policy-live-monitor-v1",
        )
        baseline = DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=DecisionValidityStatus.ACTIVE,
        )
        packet_ref = _put_json(
            store,
            {
                "schema_version": "3.4",
                "run_id": "run-live-monitor",
                "claim_ledger_v2_ref": ledger_ref.model_dump(mode="json"),
                "decision_validity_envelope": envelope.model_dump(mode="json"),
                "decision_validity_baseline": baseline.model_dump(mode="json"),
            },
            kind="scientist.decision_packet",
        )
        store.record_artifact_owner(
            packet_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.runtime_http.ds18",
        )
        control._decision_validity_service.register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=envelope,
            baseline=baseline,
        )
        evidence_ref = _artifact_ref(store, runtime_api_env["legal_artifact_id"])
        monitor = GovernanceMonitorEvent(
            event_id="monitor-live-legal-change",
            decision_packet_ref=packet_ref,
            event_type="policy_context_drift",
            severity="block",
            affected_claim_ids=[claim.claim_id],
            reason="A content-bound legal change requires owner review.",
            occurred_at=datetime(2026, 8, 28, 8, 0, tzinfo=UTC),
            observed_epoch_ref="sha256:" + "e" * 64,
            perturbation=LegalChangePerturbation(
                legal_change_evidence_ref=evidence_ref,
            ),
        )
        persisted = persist_governance_monitor_event(store, monitor)
        store.record_artifact_owner(
            persisted.event_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.runtime_http.ds18",
        )
        assert resolve_governance_monitor_event(store, persisted.event_ref) == persisted

        response = client.post(
            "/api/v1/control/decision-validity/events",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={"monitor_event_ref": persisted.event_ref.model_dump(mode="json")},
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["event_id"] == monitor.event_id
        assert body["monitor_event_ref"] == persisted.event_ref.model_dump(mode="json")
        assert body["affected_packets"] == [str(packet_ref.artifact_id)]
        assert body["affected_statuses"] == {"review_required": 1}
        bridge_ref = ArtifactRef.model_validate(body["lifecycle_bridge_result_ref"])
        bridge = load_lifecycle_bridge_result(store, bridge_ref)
        assert bridge.monitor_event_refs == [persisted.event_ref]
        assert [row.transition for row in bridge.transition_records] == ["review_required"]
        advisory_ref = ArtifactRef.model_validate(body["advisory_event_ref"])
        from polisyos.core.canon import from_canonical_bytes

        advisory_payload = from_canonical_bytes(store.get_bytes(advisory_ref.artifact_id))
        assert advisory_payload["source_class"] == "legal_change"
        assert advisory_payload["observed_epoch_ref"] == monitor.observed_epoch_ref
        assert advisory_payload["target_ref"] == packet_ref.model_dump(mode="json")


def test_monitor_ref_without_epoch_binding_is_rejected_before_bridge_persistence(
    tmp_path,
) -> None:
    from polisyos.runtime.http.services.control import ControlPlaneService
    from polisyos.runtime.http.services.control_registry_providers import (
        resolve_control_registry_providers,
    )

    control = ControlPlaneService(
        cas_root=tmp_path / "cas",
        core_runs_root=tmp_path / "runs",
        registry_providers=resolve_control_registry_providers(),
    )
    store = control._artifact_store
    packet_ref = ArtifactRef(
        artifact_id="sha256:" + "d" * 64,
        kind="scientist.decision_packet",
        media_type="application/json",
    )
    evidence_ref = ArtifactRef(
        artifact_id="sha256:" + "e" * 64,
        kind="lex.legal_report",
        media_type="application/json",
    )
    persisted = persist_governance_monitor_event(
        store,
        GovernanceMonitorEvent(
            event_id="monitor-missing-epoch",
            decision_packet_ref=packet_ref,
            event_type="policy_context_drift",
            severity="warning",
            reason="No observed epoch was bound.",
            perturbation=LegalChangePerturbation(
                legal_change_evidence_ref=evidence_ref,
            ),
        ),
    )
    kinds_before = tuple(
        store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
    )

    with pytest.raises(RuntimeHTTPError) as exc_info:
        control.publish_decision_validity_event(
            DecisionValidityEventRequest(monitor_event_ref=persisted.event_ref)
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "monitor_event_epoch_binding_missing"

    kinds_after = tuple(
        store.get_manifest(artifact_id).kind for artifact_id in store.iter_artifact_ids()
    )
    assert kinds_after.count("scientist.lifecycle_bridge_result") == kinds_before.count(
        "scientist.lifecycle_bridge_result"
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


def test_control_epoch_batch_resolves_ledger_from_packet_not_request(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _epoch_batch_fixture,
    )

    bearer = _fixture_bearer("decision-validity-claim-bridge-invocation")
    client, cell, provider = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=True,
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            jti="jwt-decision-validity-claim-bridge-invocation",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    _, decision_validity, _, transition, query_ref, packet_rows = _epoch_batch_fixture(
        runtime_api_env["cas_root"],
        packet_count=2,
    )
    calls: list[tuple[str, str, str]] = []

    def _record_bridge(
        self,
        *,
        batch_receipt_ref,
        decision_packet_ref,
        requested_query_context_ref,
    ):
        del self
        calls.append(
            (
                str(batch_receipt_ref.artifact_id),
                str(decision_packet_ref.artifact_id),
                requested_query_context_ref,
            )
        )
        return ClaimLifecycleBridgeNonReceipt(code="claim_ledger_owner_not_established")

    monkeypatch.setattr(
        EpochClaimLifecycleBridgeService,
        "bridge_completed_batch",
        _record_bridge,
    )
    with client:
        control = client.app.state._control_service
        control._decision_validity_service = decision_validity
        control._epoch_claim_lifecycle_bridge = build_epoch_claim_lifecycle_bridge(
            completed_batches=decision_validity,
            claim_owner=build_default_claim_ledger_owner(store=control._artifact_store),
            artifacts=control._artifact_store,
        )
        response = control.admit_epoch_validity_batch(
            EpochValidityBatchRequest(
                transition_artifact_ref=transition,
                requested_query_context_ref=query_ref,
            )
        )

    assert response.completion_receipt.claim_bridge_result_refs == ()
    assert response.claim_bridge_result_refs == ()
    assert [row[1] for row in calls] == [packet_ref for packet_ref, _ in packet_rows]
    assert {row[2] for row in calls} == {query_ref}
    assert len({row[0] for row in calls}) == 1


def test_partial_or_pending_epoch_batch_cannot_bridge_claims(
    runtime_api_env,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.unit.scientist.validation.test_decision_validity_service import (
        _epoch_batch_fixture,
    )

    client, _, _ = _build_secure_client(
        runtime_api_env,
        opa_client=_AllowOPA(),
        claims_by_token={},
        raise_server_exceptions=True,
    )
    _, decision_validity, _, transition, query_ref, packet_rows = _epoch_batch_fixture(
        runtime_api_env["cas_root"],
        packet_count=2,
    )
    real_apply = decision_validity._apply_event_to_packet
    apply_count = 0

    def _apply_then_crash(*, packet_ref, event):
        nonlocal apply_count
        apply_count += 1
        if apply_count == 1:
            return real_apply(packet_ref=packet_ref, event=event)
        raise RuntimeError("injected_partial_epoch_batch")

    bridge_calls: list[str] = []

    def _record_bridge(self, *, decision_packet_ref, **_kwargs):
        del self
        bridge_calls.append(str(decision_packet_ref.artifact_id))
        return ClaimLifecycleBridgeNonReceipt(code="claim_ledger_owner_not_established")

    monkeypatch.setattr(decision_validity, "_apply_event_to_packet", _apply_then_crash)
    monkeypatch.setattr(
        EpochClaimLifecycleBridgeService,
        "bridge_completed_batch",
        _record_bridge,
    )
    with client:
        control = client.app.state._control_service
        control._decision_validity_service = decision_validity
        control._epoch_claim_lifecycle_bridge = build_epoch_claim_lifecycle_bridge(
            completed_batches=decision_validity,
            claim_owner=build_default_claim_ledger_owner(store=control._artifact_store),
            artifacts=control._artifact_store,
        )
        with pytest.raises(RuntimeError, match="injected_partial_epoch_batch"):
            control.admit_epoch_validity_batch(
                EpochValidityBatchRequest(
                    transition_artifact_ref=transition,
                    requested_query_context_ref=query_ref,
                )
            )

    pending = decision_validity._state.list_epoch_pending()
    assert len(pending) == 1
    assert pending[0].applied_packet_refs == (packet_rows[0][0],)
    assert decision_validity.enumerate_completed_epoch_batch_evidence() == ()
    with pytest.raises(ValueError, match="decision_validity_epoch_receipt_unresolved"):
        decision_validity.resolve_completed_epoch_batch_evidence(batch_receipt_ref=transition)
    assert bridge_calls == []


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
