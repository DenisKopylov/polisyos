"""Persisted source facts stay bound to one canonical locked budget read."""

from __future__ import annotations

import hashlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine import budget_ledger
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware


def _owner(path: Path) -> tuple[FileBudgetLedger, BudgetMiddleware]:
    ledger = FileBudgetLedger(path)
    middleware = BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("2"))}),
        ledger=ledger,
    )
    return ledger, middleware


def test_source_profile_binds_actual_fields_bytes_identity_and_revision(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger, middleware = _owner(path)
    ledger.record_spend("run", Decimal("0.25"))
    raw = path.read_bytes()
    wire = json.loads(raw)

    read = middleware.snapshot_with_source_safe()

    assert read.source_profile.predicate_provenance == "recomputed"
    assert read.source_profile.schema_version == "1.6"
    assert read.source_profile.snapshot_fields == frozenset(wire)
    assert read.source_profile.state_fields == frozenset(wire["state"])
    assert read.source_profile.content_sha256 == hashlib.sha256(raw).hexdigest()
    assert read.source_profile.ledger_id == read.snapshot.ledger_id == wire["ledger_id"]
    assert read.source_profile.revision == read.snapshot.revision == 1
    assert read.source_profile.canonical_contract == read.snapshot.canonical_contract
    assert read.source_profile.coordination_mode == read.snapshot.coordination_mode
    assert read.snapshot.state.spent["run"] == Decimal("0.25")
    read.snapshot.state.spent["run"] = Decimal("99")
    assert middleware.budget_state.spent["run"] == Decimal("0.25")
    assert middleware.snapshot_with_source_safe().snapshot.state.spent["run"] == Decimal("0.25")


def test_legacy_defaults_do_not_become_persisted_field_or_identity_evidence(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    ledger, middleware = _owner(path)
    wire = json.loads(path.read_bytes())
    wire["schema_version"] = "1.5"
    del wire["compute_reservations"]
    del wire["ledger_id"]
    path.write_text(json.dumps(wire))

    read = middleware.snapshot_with_source_safe()

    assert read.snapshot.schema_version == "1.6"
    assert read.snapshot.compute_reservations == {}
    assert read.source_profile.schema_version == "1.5"
    assert "compute_reservations" not in read.source_profile.snapshot_fields
    assert "ledger_id" not in read.source_profile.snapshot_fields
    assert read.source_profile.ledger_id is None
    assert read.snapshot.ledger_id is not None
    assert ledger.snapshot().compute_reservations == {}
    assert middleware.snapshot_safe().schema_version == "1.6"


def test_missing_changed_and_incomplete_sources_never_reuse_a_previous_profile(
    tmp_path: Path,
) -> None:
    path = tmp_path / "budget.json"
    ledger, middleware = _owner(path)
    first = middleware.snapshot_with_source_safe()
    ledger.reserve("run", Decimal("0.5"))
    changed = middleware.snapshot_with_source_safe()
    assert changed.source_profile.content_sha256 != first.source_profile.content_sha256
    assert changed.source_profile.revision == first.source_profile.revision + 1
    assert changed.snapshot.state.reserved["run"] == Decimal("0.5")
    wire = json.loads(path.read_bytes())
    del wire["compute_reservations"]
    path.write_text(json.dumps(wire))
    with pytest.raises(ValueError, match="missing snapshot.compute_reservations"):
        middleware.snapshot_with_source_safe()
    path.unlink()
    with pytest.raises(FileNotFoundError, match="explicit load_or_bootstrap"):
        middleware.snapshot_with_source_safe()


def test_source_profile_cannot_use_an_unlocked_second_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "budget.json"
    ledger, middleware = _owner(path)
    other = FileBudgetLedger(path)
    raw = path.read_bytes()
    reader_entered = threading.Event()
    release_reader = threading.Event()
    writer_attempted = threading.Event()
    writer_completed = threading.Event()
    decode = budget_ledger._decode_snapshot
    file_lock = other._file_lock

    def pause_read(value: str):
        if threading.current_thread().name.startswith("source-reader"):
            reader_entered.set()
            assert release_reader.wait(5)
        return decode(value)

    @contextmanager
    def observe_writer_lock(*, exclusive: bool):
        writer_attempted.set()
        with file_lock(exclusive=exclusive):
            yield

    def write() -> None:
        other.reserve("run", Decimal("0.5"))
        writer_completed.set()

    monkeypatch.setattr(budget_ledger, "_decode_snapshot", pause_read)
    monkeypatch.setattr(other, "_file_lock", observe_writer_lock)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="source-reader") as reader:
        with ThreadPoolExecutor(max_workers=1) as writer:
            pending_read = reader.submit(middleware.snapshot_with_source_safe)
            assert reader_entered.wait(5)
            pending_write = writer.submit(write)
            try:
                assert writer_attempted.wait(5)
                assert not writer_completed.wait(0.05)
            finally:
                release_reader.set()
            read = pending_read.result(timeout=5)
            pending_write.result(timeout=5)
    assert read.source_profile.content_sha256 == hashlib.sha256(raw).hexdigest()
    assert read.source_profile.revision == read.snapshot.revision == 0
    assert read.snapshot.state.reserved == {}
    latest = ledger.snapshot_with_source()
    assert latest.source_profile.revision == latest.snapshot.revision == 1
    assert latest.source_profile.content_sha256 != read.source_profile.content_sha256
    assert latest.snapshot.state.reserved["run"] == Decimal("0.5")


def test_source_profile_requires_a_durable_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(RuntimeError, match="configured ledger"):
        BudgetMiddleware(BudgetState()).snapshot_with_source_safe()
    ledger, middleware = _owner(tmp_path / "budget.json")
    monkeypatch.setattr(ledger, "snapshot_with_source", None)
    with pytest.raises(RuntimeError, match="source_profile_not_established"):
        middleware.snapshot_with_source_safe()
