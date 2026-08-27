"""Behavioral tests for accepted-anchor lineage compare-and-append."""

from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from polisyos.core.artifacts import ArtifactID, ArtifactRef
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts import chronology as contract


def test_lineage_rejects_stale_expected_heads_without_moving_current() -> None:
    """Accepting a stale candidate instead of comparing heads is the break caught."""
    from polisyos.core.security.anchor_lineage import InMemoryAnchorAcceptanceLineageRepository

    repository = InMemoryAnchorAcceptanceLineageRepository()
    assert repository.current_head_refs == ()
    assert repository.append_token("first", expected_head_tokens=()).status == "appended"
    conflict = repository.append_token("second", expected_head_tokens=())
    assert conflict.status == "head_conflict"
    assert repository.current_head_refs == ("first",)


def _digest(label: str) -> str:
    return f"sha256:{hashlib.sha256(label.encode()).hexdigest()}"


def _ref(label: str) -> ArtifactRef:
    return ArtifactRef(
        artifact_id=ArtifactID.model_validate(_digest(label)),
        kind="fixture.anchor",
        media_type="application/octet-stream",
    )


def _key() -> contract.AnchorAcceptanceLineageKey:
    return contract.AnchorAcceptanceLineageKey(
        family="epoch",
        proof_domain="epoch",
        scope_ref=_digest("scope"),
        authority_purpose="publication",
    )


def _record(
    label: str, predecessors: tuple[ArtifactRef, ...]
) -> contract.AcceptedAnchorRecordEntry:
    return contract.AcceptedAnchorRecordEntry(
        acceptance_record_ref=_ref(f"record-{label}"),
        acceptance_record_content_hash=_digest(f"record-content-{label}"),
        acceptance_digest=_digest(f"acceptance-{label}"),
        signed_statement_evidence_ref=_ref(f"evidence-{label}"),
        requested_query_context_ref=_digest(f"query-{label}"),
        admission_cutoff_ref=_digest(f"cutoff-{label}"),
        predecessor_record_refs=predecessors,
    )


def test_file_lineage_survives_restart_and_preserves_history(tmp_path: Path) -> None:
    """Atomic current-head movement must not discard authentic old records."""
    from polisyos.core.security.anchor_lineage import (
        FileAnchorAcceptanceLineageRepository,
    )

    repository = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage")
    first = _record("first", ())
    result = repository.append_if_current(key=_key(), expected_head_refs=(), record=first)
    assert result.result_kind == "append_success"
    restarted = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage")
    state = restarted.resolve_lineage(key=_key())
    frames = contract._split_framed_records(state.statement_bytes)
    import json

    parsed = contract.AnchorAcceptanceLineageStateStatement.model_validate(json.loads(frames[0]))
    assert parsed.current_record_refs == (first.acceptance_record_ref,)
    assert parsed.records == (first,)


def test_two_concurrent_candidates_leave_one_current_receipt(tmp_path: Path) -> None:
    """Only one candidate may win the same expected-head compare-and-append."""
    from polisyos.core.security.anchor_lineage import (
        FileAnchorAcceptanceLineageRepository,
    )

    repository = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage")
    candidates = (_record("left", ()), _record("right", ()))
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(
            pool.map(
                lambda item: repository.append_if_current(
                    key=_key(), expected_head_refs=(), record=item
                ),
                candidates,
            )
        )
    assert sorted(result.result_kind for result in results) == [
        "append_conflict",
        "append_success",
    ]
    state = repository.resolve_lineage(key=_key())
    import json

    parsed = contract.AnchorAcceptanceLineageStateStatement.model_validate(
        json.loads(contract._split_framed_records(state.statement_bytes)[0])
    )
    assert len(parsed.current_record_refs) == 1
    assert len(parsed.records) == 1


def test_durable_transaction_recovers_after_interrupted_head_move(
    tmp_path: Path, monkeypatch
) -> None:
    """A complete WAL transaction must recover without inventing a receipt."""
    from polisyos.core.security import anchor_lineage
    from polisyos.core.security.anchor_lineage import (
        FileAnchorAcceptanceLineageRepository,
    )

    repository = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage")
    original_replace = anchor_lineage._atomic_replace
    calls = 0

    def interrupt_first_replace(path: Path, payload: bytes) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated crash after durable transaction")
        original_replace(path, payload)

    monkeypatch.setattr(anchor_lineage, "_atomic_replace", interrupt_first_replace)
    first = _record("recoverable", ())
    with pytest.raises(OSError, match="simulated crash after durable transaction"):
        repository.append_if_current(key=_key(), expected_head_refs=(), record=first)

    monkeypatch.setattr(anchor_lineage, "_atomic_replace", original_replace)
    recovered = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage").resolve_lineage(
        key=_key()
    )
    parsed = contract.AnchorAcceptanceLineageStateStatement.model_validate(
        from_canonical_bytes(contract._split_framed_records(recovered.statement_bytes)[0])
    )
    assert parsed.current_record_refs == (first.acceptance_record_ref,)
    assert parsed.records == (first,)


def test_durable_transaction_recovers_receipt_after_head_move(tmp_path: Path, monkeypatch) -> None:
    """A crash after head movement must not strand the positive receipt."""
    from polisyos.core.security.anchor_lineage import (
        FileAnchorAcceptanceLineageRepository,
    )

    repository = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage")
    original_persist = FileAnchorAcceptanceLineageRepository._persist_success
    calls = 0

    def interrupt_first_receipt(self, statement, payload, directory):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("simulated crash after head movement")
        return original_persist(self, statement, payload, directory)

    monkeypatch.setattr(
        FileAnchorAcceptanceLineageRepository,
        "_persist_success",
        interrupt_first_receipt,
    )
    record = _record("receipt-recovery", ())
    with pytest.raises(OSError, match="simulated crash after head movement"):
        repository.append_if_current(key=_key(), expected_head_refs=(), record=record)

    directory = repository._directory(_key())
    assert (directory / "head-index.frame").is_file()
    assert list((directory / "receipts").glob("*.frame")) == []
    monkeypatch.setattr(
        FileAnchorAcceptanceLineageRepository,
        "_persist_success",
        original_persist,
    )
    recovered = FileAnchorAcceptanceLineageRepository(tmp_path / "lineage")
    assert recovered.resolve_lineage(key=_key()).state_content_hash
    receipts = list((directory / "receipts").glob("*.frame"))
    assert len(receipts) == 1
    parsed = contract.AnchorAcceptanceAppendSuccessStatement.model_validate(
        from_canonical_bytes(contract._split_framed_records(receipts[0].read_bytes())[0])
    )
    assert parsed.acceptance_record_ref == record.acceptance_record_ref
