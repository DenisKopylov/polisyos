from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from polisyos.core.artifacts import ArtifactID, read_core_json_artifact
from tests.unit.runtime.http.test_human_decision_service import NOW as HUMAN_DECISION_NOW
from tests.unit.runtime.quality.test_agent_action_authority import (
    DIGEST,
    _authority_module,
    _prepare_gateway,
    _prepared_v2_human_decision,
    _produce,
)


@dataclass(frozen=True)
class _PreparedAuthorization:
    fixture: Any
    gateway: Any
    persisted: Any
    human_record: Any
    adapter: Any


def _prepare_authorization(tmp_path: Path) -> _PreparedAuthorization:
    fixture, receipt, adapter = _prepared_v2_human_decision(tmp_path)
    human_record = receipt.record
    gateway, _, _ = _prepare_gateway(
        fixture.harness,
        contract=fixture.contract,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
        bindings=(fixture.binding,),
        contract_ref_override=human_record.basis_ref,
        human_decision_service=fixture.service,
        human_decision_adapters={human_record.human_decision_request_ref: adapter},
        mandate_authority_at=human_record.recorded_at,
    )
    decision = _produce(
        gateway=gateway,
        operation=fixture.operation,
        invocation=fixture.invocation,
        intent=fixture.intent,
    )
    assert decision.outcome == "allowed"
    return _PreparedAuthorization(
        fixture=fixture,
        gateway=gateway,
        persisted=gateway.persist_decision(decision),
        human_record=human_record,
        adapter=adapter,
    )


def _dispatch_state(gateway: Any) -> tuple[frozenset[str], tuple[tuple[str, bytes], ...]]:
    store = gateway._idempotency_store
    files = tuple(
        sorted((path.name, path.read_bytes()) for path in store._root.iterdir() if path.is_file())
    )
    return frozenset(store._pending), files


def _verify_without_side_effects(
    prepared: _PreparedAuthorization,
    *,
    expected_error: str | None = None,
) -> None:
    fixture = prepared.fixture
    gateway = prepared.gateway
    authority = _authority_module()
    dispatch_before = _dispatch_state(gateway)
    effects_before = list(fixture.effects)

    with (
        patch.object(gateway, "begin_dispatch", wraps=gateway.begin_dispatch) as begin,
        patch.object(gateway, "complete_dispatch", wraps=gateway.complete_dispatch) as complete,
        patch.object(gateway, "release_dispatch", wraps=gateway.release_dispatch) as release,
        patch.object(
            fixture.service,
            "resolve_gateway_adapter",
            wraps=fixture.service.resolve_gateway_adapter,
        ) as resolve_ds9,
    ):
        if expected_error is None:
            assert (
                gateway.verify_bound_authorization(
                    operation=fixture.operation,
                    invocation=fixture.invocation,
                    intent=fixture.intent,
                    persisted=prepared.persisted,
                )
                is None
            )
        else:
            with pytest.raises(
                authority.AgentActionAuthorityRecordingError,
                match=expected_error,
            ):
                gateway.verify_bound_authorization(
                    operation=fixture.operation,
                    invocation=fixture.invocation,
                    intent=fixture.intent,
                    persisted=prepared.persisted,
                )
        assert (begin.call_count, complete.call_count, release.call_count) == (0, 0, 0)
        assert resolve_ds9.call_count == 0

    assert fixture.effects == effects_before
    assert _dispatch_state(gateway) == dispatch_before


def test_preflight_repeats_without_effect_or_dispatch_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authority = _authority_module()
    scenario_clock = [HUMAN_DECISION_NOW]
    monkeypatch.setattr(authority, "_utcnow", lambda: scenario_clock[0])
    prepared = _prepare_authorization(tmp_path)
    fixture = prepared.fixture
    persisted = prepared.persisted
    assert prepared.human_record.recorded_at == HUMAN_DECISION_NOW
    assert fixture.effects == []

    for _ in range(3):
        _verify_without_side_effects(prepared)
    assert fixture.effects == []

    assert (
        prepared.gateway.execute_bound_effect(
            operation=fixture.operation,
            invocation=fixture.invocation,
            intent=fixture.intent,
            persisted=persisted,
        )
        == "search"
    )
    assert fixture.effects == ["search"]


def test_preflight_rejects_envelope_time_and_status_changes_without_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use real signed inputs plus a bounded resolved-owner seam for immutable changes.

    Future, expired, and revoked variants alter only the resolved-owner return
    value. Each runs with an independently revalidated, current DS9 record; the
    variants isolate downstream predicates and do not claim altered contracts
    were signed or persisted. The later real-envelope expiry check is additional
    evidence only; the human record has expired by then.
    """
    authority = _authority_module()
    scenario_clock = [HUMAN_DECISION_NOW]
    monkeypatch.setattr(authority, "_utcnow", lambda: scenario_clock[0])
    prepared = _prepare_authorization(tmp_path)
    fixture = prepared.fixture
    monkeypatch.setattr(fixture.service, "_clock", lambda: scenario_clock[0])
    gateway = prepared.gateway
    persisted = prepared.persisted
    resolved = gateway.resolve_delegation_contract(DIGEST)
    envelope = next(
        row
        for row in resolved.contract.action_envelopes
        if row.envelope_id == persisted.decision.envelope_id
    )
    mandate_payload = read_core_json_artifact(
        fixture.harness.store,
        ArtifactID.model_validate(resolved.mandate_authority_evidence_ref),
    ).value
    mandate = authority.CurrentMandateOwnerEvidence.model_validate(mandate_payload)
    after_expiry = envelope.valid_until + timedelta(seconds=1)

    assert envelope.status == "active"
    assert persisted.decision.decided_at < envelope.valid_until < after_expiry
    assert resolved.contract_cas_ref == persisted.decision.contract_ref
    assert mandate.current is True
    assert mandate.effective_from <= after_expiry < mandate.effective_until
    assert mandate.revoked_at is None or after_expiry < mandate.revoked_at

    scenario_clock[0] = persisted.decision.decided_at + timedelta(seconds=1)
    assert envelope.valid_from <= scenario_clock[0] < envelope.valid_until
    real_resolve = gateway.resolve_delegation_contract
    for owner_change in ("future", "expired", "revoked"):
        assert prepared.human_record.valid_from <= scenario_clock[0]
        assert scenario_clock[0] < prepared.human_record.valid_until
        fixture.service.revalidate_gateway_adapter_custody(prepared.adapter)
        if owner_change == "future":
            changed_envelope = envelope.model_copy(
                update={"valid_from": scenario_clock[0] + timedelta(seconds=1)}
            )
        elif owner_change == "expired":
            changed_envelope = envelope.model_copy(
                update={"valid_until": scenario_clock[0] - timedelta(seconds=1)}
            )
        else:
            changed_envelope = envelope.model_copy(update={"status": "revoked"})
        changed_contract = resolved.contract.model_copy(
            update={
                "action_envelopes": tuple(
                    changed_envelope if row.envelope_id == envelope.envelope_id else row
                    for row in resolved.contract.action_envelopes
                )
            }
        )

        def _resolved_owner_seam(
            resource_digest: str,
            *,
            resolved_contract: Any = changed_contract,
        ) -> Any:
            actual = real_resolve(resource_digest)
            assert actual.contract_cas_ref == persisted.decision.contract_ref
            return actual.model_copy(update={"contract": resolved_contract})

        with monkeypatch.context() as seam:
            seam.setattr(gateway, "resolve_delegation_contract", _resolved_owner_seam)
            _verify_without_side_effects(
                prepared,
                expected_error="delegation envelope is no longer live",
            )

    scenario_clock[0] = after_expiry
    _verify_without_side_effects(
        prepared,
        expected_error="delegation envelope is no longer live",
    )
    assert fixture.effects == []
