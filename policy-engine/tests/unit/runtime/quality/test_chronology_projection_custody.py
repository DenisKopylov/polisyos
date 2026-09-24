from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from polisyos.core import canon
from polisyos.core.contracts import chronology as contract
from polisyos.runtime.quality import chronology_proof
from tests._helpers import chronology_qualification as qualification_fixture
from tests._helpers.chronology_qualification import make_qualification_case


@pytest.fixture(autouse=True)
def _clear_owner_appointment() -> Any:
    registry = chronology_proof._PERSISTENCE_REGISTRY
    registry._clear_for_test()
    yield
    registry._clear_for_test()


@pytest.mark.parametrize("shape", ["epoch", "inventory"])
def test_verified_native_result_requires_reloaded_projection_and_proof(
    tmp_path: Path, shape: Any
) -> None:
    case = make_qualification_case(tmp_path, shape=shape, member_count=2)
    result = case.appoint_consumer().qualify(adapter=case.adapter, request=case.query)

    assert isinstance(result, contract.NativeChronologyQualified)
    projection = result.projection_receipt
    raw = case.store.get_bytes(projection.artifact_ref.artifact_id)
    assert case.store.verify(projection.artifact_ref.artifact_id).ok
    records = contract._split_framed_records(raw)
    assert len(records) == 1
    statement = contract.NativeChronologyProjectionStatement.model_validate(
        canon.from_canonical_bytes(records[0])
    )
    assert statement.reconciliation == result.reconciliation
    assert statement.proof_result == result.proof_result
    assert statement.reconciliation.owner_context.query == case.query
    assert result.persisted_proof.verification_statement.result == result.proof_result
    assert case.store.verify(result.persisted_proof.artifact_ref.artifact_id).ok


@pytest.mark.parametrize("fault", ["absent", "corrupt"])
def test_projection_storage_failure_preserves_native_terminal_and_refuses_qualified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    case = make_qualification_case(tmp_path, shape="inventory", member_count=2)
    original = case.store.put_bytes

    def put(payload: bytes, options: Any) -> Any:
        if options.kind == "core.chronology.native_projection":
            if fault == "absent":
                raise OSError("projection custody unavailable")
            return original(b"corrupt projection", options)
        return original(payload, options)

    monkeypatch.setattr(case.store, "put_bytes", put)
    result = case.appoint_consumer().qualify(adapter=case.adapter, request=case.query)

    assert isinstance(result, contract.NativeProjectionCustodyGap)
    assert result.reconciliation.owner_context.owner_qualified_candidate.candidate == case.candidate
    assert result.proof_result.verified_member_count == 2


def test_non_utf8_native_member_reaches_persisted_qualified_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    native_bytes = b"\xff\x00\x80\xfe"
    monkeypatch.setattr(qualification_fixture, "_native_bytes", lambda **_: native_bytes)
    case = make_qualification_case(tmp_path, shape="inventory", member_count=1)

    result = case.appoint_consumer().qualify(adapter=case.adapter, request=case.query)

    assert isinstance(result, contract.NativeChronologyQualified)
    candidate = result.projection_receipt.statement.reconciliation.owner_context.owner_qualified_candidate.candidate
    assert candidate.ordered_members[0].native_bytes == native_bytes
    assert case.store.verify(result.persisted_proof.artifact_ref.artifact_id).ok
