"""A restarted worker consumes durable authority without recreating a DS20 seal."""

from __future__ import annotations

from pathlib import Path

import pytest

from polisyos.runtime.quality import agent_action_authority as authority
from tests.unit.runtime.quality import test_agent_action_authority as fixtures


def _reserved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(authority, "_utcnow", lambda: fixtures.NOW)
    harness = fixtures._harness(tmp_path)
    operation = fixtures._operation()
    invocation = fixtures._invocation(operation)
    intent = authority.AgentActionIntent(action_kind="search")
    effects: list[str] = []
    binding = fixtures._binding(operation, effects)
    gateway, _, _ = fixtures._prepare_gateway(
        harness,
        contract=fixtures._contract(fixtures._envelope()),
        operation=operation,
        invocation=invocation,
        intent=intent,
        bindings=(binding,),
    )
    with authority.agent_action_authority_scope(gateway):
        persisted = authority.reserve_agent_external_action(
            bound_permission=gateway.bound_permission,
            operation=operation,
            invocation=invocation,
            intent=intent,
        )
    return harness, gateway, persisted, operation, invocation, intent, binding, effects


def _reopen(harness, gateway, persisted, binding, **changes):
    options = {
        "artifact_store": harness.store,
        "event_log": harness.event_log,
        "idempotency_store": harness.idempotency_store,
        "artifact_verifier": harness.verifier,
        "admission_producer_identity": fixtures.ADMISSION_PRODUCER_IDENTITY,
        "write_context": gateway.write_context,
        "contract_refs_by_resource_digest": dict(gateway._contract_refs),
        "mandate_authority_evidence_refs_by_owner_ref": dict(
            gateway._mandate_authority_evidence_refs
        ),
        "admission_refs_by_invocation_hash": dict(gateway._admission_refs),
        "effect_bindings": (binding,),
        "decision_ref": str(persisted.write_result.cas_ref.artifact_id),
    }
    options.update(changes)
    return authority.AgentActionAuthorityGateway.for_persisted_decision(**options)


def test_replay_reopens_allowed_decision_without_request_proof(tmp_path, monkeypatch):
    harness, gateway, persisted, operation, invocation, intent, binding, effects = _reserved(
        tmp_path, monkeypatch
    )
    replay = _reopen(harness, gateway, persisted, binding)
    assert replay is not gateway
    with pytest.raises(authority.AgentActionAuthorityRecordingError, match="replay"):
        _ = replay.bound_permission
    with pytest.raises(authority.AgentActionAuthorityRecordingError, match="replay"):
        replay.persist_decision(persisted.decision)
    with (
        pytest.raises(authority.AgentActionAuthorityRecordingError, match="replay"),
        authority.agent_action_authority_scope(replay),
    ):
        pass
    replay.execute_bound_effect(
        operation=operation,
        invocation=invocation,
        intent=intent,
        persisted=replay.load_persisted_decision(str(persisted.write_result.cas_ref.artifact_id)),
    )
    assert effects == ["search"]


@pytest.mark.parametrize("missing", ["admission", "mandate"])
def test_replay_retains_allow_markers_but_missing_signed_input_refuses(
    tmp_path, monkeypatch, missing
):
    harness, gateway, persisted, _, _, _, binding, effects = _reserved(tmp_path, monkeypatch)
    change = (
        {"admission_refs_by_invocation_hash": {}}
        if missing == "admission"
        else {"mandate_authority_evidence_refs_by_owner_ref": {}}
    )
    assert persisted.decision.outcome == "allowed"
    with pytest.raises(
        (
            authority.AgentActionAuthorityRecordingError,
            authority.AgentActionAuthorityOwnerResolutionError,
        )
    ):
        _reopen(harness, gateway, persisted, binding, **change)
    assert effects == []


def test_replay_binds_permission_snapshot_to_signed_admission(tmp_path, monkeypatch):
    harness, gateway, persisted, _, _, _, binding, effects = _reserved(tmp_path, monkeypatch)
    snapshot = persisted.decision.permission_snapshot
    changed = persisted.decision.model_copy(
        update={"permission_snapshot": snapshot.model_copy(update={"subject": "different-subject"})}
    )
    rewritten = gateway.persist_decision(changed)
    assert rewritten.decision.outcome == "allowed"
    with pytest.raises(authority.AgentActionAuthorityRecordingError, match="replay"):
        _reopen(harness, gateway, rewritten, binding)
    assert effects == []
