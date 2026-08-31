from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from _helpers.runtime_http import build_runtime_api_env, close_runtime_api_env

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.contracts.decision_validity import (
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.security.identity import PolicyOSRole
from polisyos.scientist.evidence.claims import (
    AppendOnlyClaimLedger,
    ClaimLifecycleAction,
    ClaimPublishability,
    ClaimRecord,
    ClaimSupportStatus,
    ClaimType,
)
from polisyos.scientist.evidence.claims.audit import _persist_append_only_claim_ledger
from polisyos.scientist.governance.continuous import load_lifecycle_bridge_result
from polisyos.scientist.governance.continuous.monitors import (
    GovernanceMonitorEvent,
    LegalChangePerturbation,
    persist_governance_monitor_event,
)
from polisyos.scientist.methods.search.readiness import DecisionReadiness
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)


@pytest.fixture
def runtime_api_env(tmp_path: Path) -> Iterator[dict[str, object]]:
    env = build_runtime_api_env(tmp_path, include_test_client=True)
    try:
        yield env
    finally:
        close_runtime_api_env(env)


def _put_json(store: FileSystemCAS, payload: object, *, kind: str) -> ArtifactRef:
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


def test_monitor_event_persists_claim_supersession_without_in_place_edit(
    runtime_api_env,
) -> None:
    """A monitor-triggered supersession must persist a new history, never edit its input."""

    bearer = _fixture_bearer("ds11-claim-supersession")
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
            jti="jwt-ds11-claim-supersession",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )

    with client:
        control = client.app.state._control_service
        store = control._artifact_store
        predecessor = ClaimRecord(
            claim_id="claim-ds11-predecessor",
            run_id="run-ds11-lifecycle",
            claim_type=ClaimType.FACTUAL,
            text="The predecessor remains visible in immutable claim history.",
            support_status=ClaimSupportStatus.SUPPORTED,
            publishability=ClaimPublishability.PUBLISHABLE,
            readiness_level=DecisionReadiness.RESEARCH_ARTIFACT,
        )
        predecessor_ledger_ref = _persist_append_only_claim_ledger(
            store,
            AppendOnlyClaimLedger(
                run_id=predecessor.run_id,
                current_claims=[predecessor],
            ),
        )
        predecessor_ledger_bytes = store.get_bytes(predecessor_ledger_ref.artifact_id)
        store.record_artifact_owner(
            predecessor_ledger_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.integration.ds11",
        )

        envelope = DecisionValidityEnvelope(
            decision_lineage_key="lineage-ds11-lifecycle",
            policy_fingerprint="policy-ds11-lifecycle-v1",
        )
        baseline = DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=DecisionValidityStatus.ACTIVE,
        )
        packet_ref = _put_json(
            store,
            {
                "schema_version": "3.4",
                "run_id": predecessor.run_id,
                "claim_ledger_v2_ref": predecessor_ledger_ref.model_dump(mode="json"),
                "decision_validity_envelope": envelope.model_dump(mode="json"),
                "decision_validity_baseline": baseline.model_dump(mode="json"),
            },
            kind="scientist.decision_packet",
        )
        store.record_artifact_owner(
            packet_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.integration.ds11",
        )
        control._decision_validity_service.register_decision_packet(
            packet_ref=str(packet_ref.artifact_id),
            envelope=envelope,
            baseline=baseline,
        )

        monitor = GovernanceMonitorEvent(
            event_id="monitor-ds11-supersession",
            decision_packet_ref=packet_ref,
            event_type="policy_context_drift",
            severity="block",
            affected_claim_ids=[predecessor.claim_id],
            reason="Verified replacement evidence requires a superseding claim.",
            occurred_at=datetime(2026, 8, 30, 9, 0, tzinfo=UTC),
            observed_epoch_ref="sha256:" + "e" * 64,
            perturbation=LegalChangePerturbation(
                legal_change_evidence_ref=_artifact_ref(
                    store,
                    runtime_api_env["legal_artifact_id"],
                ),
            ),
            metadata={
                "superseded_by_claim_id": "claim-ds11-successor",
            },
        )
        persisted_monitor = persist_governance_monitor_event(store, monitor)
        store.record_artifact_owner(
            persisted_monitor.event_ref.artifact_id,
            tenant_id=runtime_api_env["tenant_a"],
            cell_id=cell.cell_id,
            writer="tests.integration.ds11",
        )

        response = client.post(
            "/api/v1/control/decision-validity/events",
            headers={
                "Authorization": f"Bearer {bearer}",
                "X-Tenant-ID": runtime_api_env["tenant_a"],
                "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
            },
            json={
                "monitor_event_ref": persisted_monitor.event_ref.model_dump(mode="json")
            },
        )

        assert response.status_code == 200, response.text
        bridge_ref = ArtifactRef.model_validate(
            response.json()["lifecycle_bridge_result_ref"]
        )
        persisted_bridge = load_lifecycle_bridge_result(store, bridge_ref)

        assert store.get_bytes(predecessor_ledger_ref.artifact_id) == predecessor_ledger_bytes
        assert persisted_bridge.original_claim_ledger_ref == predecessor_ledger_ref
        assert [
            event.action for event in persisted_bridge.updated_ledger.events
        ] == [ClaimLifecycleAction.SUPERSEDED]
        assert persisted_bridge.updated_ledger.events[0].metadata[
            "superseded_by_claim_id"
        ] == "claim-ds11-successor"
        assert persisted_bridge.updated_ledger != AppendOnlyClaimLedger.model_validate_json(
            predecessor_ledger_bytes
        )
