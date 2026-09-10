"""Real HTTP Claim supersession with explicit test authority and default refusals."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef, ArtifactWriteOptions
from polisyos.core.contracts.decision_validity import (
    DecisionValidityEnvelope,
    DecisionValidityEvaluation,
    DecisionValidityStatus,
)
from polisyos.core.security.identity import PolicyOSRole
from polisyos.runtime.http.container import RuntimeContainerOverrides
from polisyos.runtime.http.dependencies import build_runtime_api_context
from polisyos.scientist.evidence.claims.export import ClaimExportAudience, ClaimLedgerExport
from polisyos.scientist.evidence.claims.head_index import UnappointedClaimLedgerOwner
from polisyos.scientist.evidence.claims.lifecycle import ClaimLifecycleAction
from polisyos.scientist.governance.continuous.lifecycle_bridge import load_lifecycle_bridge_result
from tests.unit.runtime.http.test_runtime_api_authz import (
    _AllowOPA,
    _build_secure_client,
    _claims,
    _fixture_bearer,
    _install_bound_test_step_up,
)
from tests.unit.scientist.governance.continuous.test_owner_event_producer import (
    _build_owner_event_case,
    _requested_case,
    _signed_authority,
)


@pytest.fixture
def http_owner_case(tmp_path):
    """Keep fixture root trust explicit and use the real guarded runtime CAS."""
    context = build_runtime_api_context(
        cas_root=tmp_path / "cas", core_runs_root=tmp_path / "cas" / "runs"
    )
    return context, _requested_case(_build_owner_event_case(tmp_path, store=context.store))


def _http_client(http_owner_case, *, owner=None):
    context, case = http_owner_case
    store, _, _, _, monitor, _ = case
    tenant = "d7cb6a1c-5a36-4d3d-8da7-4ba22149b967"
    bearer = _fixture_bearer("claim-owner-http")
    client, cell, provider = _build_secure_client(
        {
            "cas_root": context.cas_root,
            "tenant_a": tenant,
            "tenant_b": "5edfdb61-bf9e-4f99-bd06-90504c30eae9",
        },
        opa_client=_AllowOPA(),
        claims_by_token={},
        container_overrides=RuntimeContainerOverrides(
            runtime_api_context=context, claim_ledger_owner=owner
        ),
    )
    provider.put_claim(
        bearer,
        _claims(
            tenant_id=tenant,
            cell_id=cell.cell_id,
            jti="claim-owner-http",
            roles=frozenset({PolicyOSRole.ADMIN}),
        ),
    )
    # These are test-owned prerequisite artifacts, never a production appointment.
    for artifact_id in store.iter_artifact_ids():
        store.record_artifact_owner(
            artifact_id,
            tenant_id=tenant,
            cell_id=cell.cell_id,
            writer="tests.integration.claim_owner_http",
        )
    envelope = DecisionValidityEnvelope(
        decision_lineage_key="claim-owner-http-lineage", policy_fingerprint="claim-owner-http-v1"
    )
    client.app.state.runtime_container.decision_validity_service.register_decision_packet(
        packet_ref=str(monitor.event.decision_packet_ref.artifact_id),
        envelope=envelope,
        baseline=DecisionValidityEvaluation(
            decision_lineage_key=envelope.decision_lineage_key,
            status=DecisionValidityStatus.ACTIVE,
        ),
    )
    return client, bearer, tenant


def _post_monitor(client, bearer, tenant, monitor_ref):
    return client.post(
        "/api/v1/control/decision-validity/events",
        headers={
            "Authorization": f"Bearer {bearer}",
            "X-Tenant-ID": tenant,
            "X-PolicyOS-Step-Up": _install_bound_test_step_up(client),
        },
        json={"monitor_event_ref": monitor_ref.model_dump(mode="json")},
    )


def _read_http_bridge(store, response):
    assert response.status_code == 200, response.text
    ref = ArtifactRef.model_validate(response.json()["lifecycle_bridge_result_ref"])
    return load_lifecycle_bridge_result(store, ref)


def test_monitor_event_persists_claim_supersession_without_in_place_edit(http_owner_case) -> None:
    """The real dev HTTP composition consumes signed test evidence and preserves history."""
    context, case = http_owner_case
    store, _, prepared, initial, monitor, _ = case
    owner, signer = _signed_authority(case)
    old_bytes = store.get_bytes(prepared.initial_ledger_ref.artifact_id)
    client, bearer, tenant = _http_client(http_owner_case, owner=owner)
    with client:
        container = client.app.state.runtime_container
        assert container.runtime_api_context is context
        assert container.claim_ledger_owner is owner
        assert container.epoch_claim_lifecycle_bridge.claim_owner is owner
        first = _read_http_bridge(store, _post_monitor(client, bearer, tenant, monitor.event_ref))
        assert first.owner_event_outcome.code == "claim_owner_event_rejected"
        event_ref = ArtifactRef.model_validate(first.metadata["owner_event_ref"])
        store.sign_artifact(
            event_ref.artifact_id, signer, signer_identity="fixture-supersession-owner"
        )
        bridged = _read_http_bridge(store, _post_monitor(client, bearer, tenant, monitor.event_ref))
        assert bridged.owner_event_outcome.result_kind == "advanced"
        assert bridged.monitor_projection_authority == "advisory"
        assert bridged.updated_ledger.events[-1].action is ClaimLifecycleAction.REVIEW_REQUIRED
        for audience in (ClaimExportAudience.EXPERT, ClaimExportAudience.PUBLIC):
            export = owner.export_current(owner_key=prepared.owner_key, audience=audience)
            assert isinstance(export, ClaimLedgerExport)
            assert export.superseded_claim_ids == ["predecessor"]
            assert "actual-successor" not in {claim.claim_id for claim in export.claims}
        current = owner.resolve_current(owner_key=prepared.owner_key)
        assert current.statement.generation == initial.new_head.statement.generation + 1
        again = _read_http_bridge(store, _post_monitor(client, bearer, tenant, monitor.event_ref))
        assert again.owner_event_outcome.new_head == current
        assert store.get_bytes(prepared.initial_ledger_ref.artifact_id) == old_bytes


def test_default_http_supersession_request_preserves_unappointed_owner_limit(
    http_owner_case,
) -> None:
    """A typed proposal and invented metadata cannot appoint the default Claim owner."""
    _, case = http_owner_case
    store, _, prepared, _, monitor, _ = case
    old_bytes = store.get_bytes(prepared.initial_ledger_ref.artifact_id)
    client, bearer, tenant = _http_client(http_owner_case)
    with client:
        owner = client.app.state.runtime_container.claim_ledger_owner
        assert isinstance(owner, UnappointedClaimLedgerOwner)
        result = _read_http_bridge(store, _post_monitor(client, bearer, tenant, monitor.event_ref))
        assert result.metadata["owner_event_production_result"]["code"] == "claim_head_absent"
        assert result.owner_event_outcome is None
        assert result.updated_ledger.events[-1].action is ClaimLifecycleAction.REVIEW_REQUIRED
        assert owner.resolve_current(owner_key=prepared.owner_key).code == "claim_head_absent"
        assert "owner_event_ref" not in result.metadata
        assert store.get_bytes(prepared.initial_ledger_ref.artifact_id) == old_bytes


@pytest.mark.parametrize("failure", ["absent", "wrong_vocabulary"])
def test_http_supersession_rejects_unresolved_monitor_before_owner_effect(
    http_owner_case, failure
) -> None:
    """Fake inputs fail exact HTTP monitor resolution, before the honest owner limitation."""
    _, case = http_owner_case
    store, _, prepared, _, monitor, _ = case
    old_bytes = store.get_bytes(prepared.initial_ledger_ref.artifact_id)
    if failure == "absent":
        bad_ref = ArtifactRef(
            artifact_id="sha256:" + "f" * 64,
            kind=monitor.event_ref.kind,
            media_type=monitor.event_ref.media_type,
        )
    else:
        bad_ref = store.put_bytes(
            store.get_bytes(monitor.event_ref.artifact_id) + b" ",
            ArtifactWriteOptions(
                kind="fixture.wrong-monitor-vocabulary", media_type="application/json"
            ),
        )
    client, bearer, tenant = _http_client(http_owner_case)
    with client:
        response = _post_monitor(client, bearer, tenant, bad_ref)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "monitor_event_unresolvable"
        assert "lifecycle_bridge_result_ref" not in response.json()
        assert store.get_bytes(prepared.initial_ledger_ref.artifact_id) == old_bytes
