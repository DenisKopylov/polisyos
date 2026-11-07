"""Native local guards for a protected budget continuation point."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest

from polisyos.core.canon import CanonSpec, content_hash, to_canonical_bytes
from polisyos.scientist.orchestration.engine import budget_ledger as ledger_module
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    _ENGINE_EVENT_PREFIX,
    BudgetLedgerSettlementOutcomeUnknownError,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

_DIGEST = hashlib.sha256(b"controlled effect").hexdigest()


def _primary(path: Path) -> tuple[BudgetMiddleware, bytes]:
    state = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))})
    middleware = BudgetMiddleware(state, ledger=FileBudgetLedger(path, ledger_id="ledger:owner"))
    middleware.record_spend_safe("run", Decimal("5"))
    old_bytes = path.read_bytes()
    middleware.settle_spend_safe("effect-a", "run", Decimal("2"), payload_digest=_DIGEST)
    return middleware, old_bytes


def _continued(primary: BudgetMiddleware, path: Path) -> BudgetMiddleware:
    owner, resource, anchor = primary.continuation_binding()
    return BudgetMiddleware(
        BudgetState(),
        ledger=FileBudgetLedger(path),
        continuation_owner_identity=owner,
        continuation_resource_identity=resource,
        continuation_snapshot_anchor=anchor,
    )


def test_stale_same_owner_snapshot_is_refused_at_actual_admission(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, old_bytes = _primary(path)
    continued = _continued(primary, path)
    assert continued.budget_state.spent["run"] == Decimal("7")
    stale = tmp_path / "stale.json"
    stale.write_bytes(old_bytes)
    os.replace(stale, path)
    calls: list[str] = []

    def producer() -> None:
        continued.pre_check("remaining", budget_key="run")
        calls.append("dispatched")

    with pytest.raises(ValueError, match="budget_ledger_snapshot_anchor_mismatch"):
        producer()
    assert calls == []


def test_exact_ledger_clone_on_different_lock_is_not_the_same_owner(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    owner, resource, anchor = primary.continuation_binding()
    copy = tmp_path / "copied-ledger.json"
    copy.write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="budget_ledger_resource_identity_mismatch"):
        BudgetMiddleware(
            BudgetState(),
            ledger=FileBudgetLedger(copy),
            continuation_owner_identity=owner,
            continuation_resource_identity=resource,
            continuation_snapshot_anchor=anchor,
        )


def test_atomic_continuation_state_is_exact_and_detached(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    owner, resource, (revision, digest), snapshot = continued._continuation_state()
    assert (owner, resource, (revision, digest)) == continued.continuation_binding()
    assert snapshot.revision == revision
    assert content_hash(to_canonical_bytes(snapshot, CanonSpec(forbid_floats=False))) == digest
    assert snapshot.state.spent["run"] == Decimal("7")
    snapshot.state.spent["run"] = Decimal("0")
    assert continued._continuation_state()[3].state.spent["run"] == Decimal("7")


def test_engine_profile_is_explicit_and_leaves_default_accounting_unchanged(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    assert primary.invocation_settlement_profile is None
    owner, resource, anchor = primary.continuation_binding()
    with pytest.raises(ValueError, match="budget_ledger_engine_owner_not_supported"):
        primary._arm_engine_guard(owner, resource, anchor)
    primary.record_spend_safe("run", Decimal("1"))
    assert primary.budget_state.spent["run"] == Decimal("8")

    with pytest.raises(ValueError, match="budget_ledger_engine_owner_not_supported"):
        BudgetMiddleware(BudgetState(), invocation_settlement_profile="single_owner_local_v1")
    with pytest.raises(ValueError, match="budget_invocation_settlement_profile_invalid"):
        BudgetMiddleware(BudgetState(), invocation_settlement_profile="unsupported")  # type: ignore[arg-type]


def test_replaced_lock_is_refused_before_subsequent_budget_use(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    lock_path = path.with_suffix(path.suffix + ".lock")
    replacement = tmp_path / "replacement.lock"
    replacement.touch()
    os.replace(replacement, lock_path)
    with pytest.raises(ValueError, match="budget_ledger_resource_identity_mismatch"):
        continued.pre_check("remaining", budget_key="run")


def test_unaccounted_peer_write_is_not_adopted_as_an_owned_advance(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    peer = FileBudgetLedger(path)
    peer.settle_spend("peer-event", "run", Decimal("1"), payload_digest=_DIGEST)
    with pytest.raises(ValueError, match="budget_ledger_snapshot_anchor_mismatch"):
        continued.pre_check("remaining", budget_key="run")


@pytest.mark.parametrize(
    "operation", ["spend", "begin", "producer", "reserve", "compute", "unknown"]
)
def test_public_ledger_operations_cannot_claim_engine_event_namespace(
    tmp_path: Path, operation: str
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    ledger = FileBudgetLedger(path)
    event = _ENGINE_EVENT_PREFIX + "untrusted"
    before = path.read_bytes()
    actions = {
        "spend": lambda: ledger.settle_spend(event, "run", Decimal("1"), payload_digest=_DIGEST),
        "begin": lambda: ledger.begin_producer_event(event, _DIGEST, "run", "model", "provider"),
        "producer": lambda: ledger.settle_producer_event(
            event, _DIGEST, _DIGEST, "run", "model", "provider", Decimal("1"), "reported"
        ),
        "reserve": lambda: ledger.reserve_compute(event, _DIGEST, "run", Decimal("1")),
        "compute": lambda: ledger.settle_compute(event, _DIGEST, _DIGEST, Decimal("1")),
        "unknown": lambda: ledger.mark_compute_unknown(event, _DIGEST),
    }
    with pytest.raises(ValueError, match="budget_ledger_engine_event_reserved"):
        actions[operation]()
    assert path.read_bytes() == before
    assert primary.budget_state.spent["run"] == Decimal("7")


@pytest.mark.parametrize(
    "operation", ["spend", "begin", "producer", "reserve", "compute", "unknown"]
)
def test_event_subclass_cannot_spoof_the_reserved_namespace(tmp_path: Path, operation: str) -> None:
    class SpoofedEvent(str):
        def startswith(self, *_args, **_kwargs) -> bool:
            return False

        def __str__(self) -> str:
            return "ordinary-event"

    path = tmp_path / "ledger.json"
    _primary(path)
    ledger = FileBudgetLedger(path)
    event = SpoofedEvent(_ENGINE_EVENT_PREFIX + "untrusted")
    before = path.read_bytes()
    actions = {
        "spend": lambda: ledger.settle_spend(event, "run", Decimal("1"), payload_digest=_DIGEST),
        "begin": lambda: ledger.begin_producer_event(event, _DIGEST, "run", "model", "provider"),
        "producer": lambda: ledger.settle_producer_event(
            event, _DIGEST, _DIGEST, "run", "model", "provider", Decimal("1"), "reported"
        ),
        "reserve": lambda: ledger.reserve_compute(event, _DIGEST, "run", Decimal("1")),
        "compute": lambda: ledger.settle_compute(event, _DIGEST, _DIGEST, Decimal("1")),
        "unknown": lambda: ledger.mark_compute_unknown(event, _DIGEST),
    }
    with pytest.raises(ValueError, match="budget_ledger_engine_event_reserved"):
        actions[operation]()
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "operation", ["spend", "begin", "producer", "reserve", "compute", "unknown"]
)
@pytest.mark.parametrize("representation", ["bytes", "enum", "str_enum"])
def test_reserved_namespace_is_checked_after_string_normalization(
    tmp_path: Path, operation: str, representation: str
) -> None:
    class OrdinaryEvent(Enum):
        RESERVED = _ENGINE_EVENT_PREFIX + "untrusted"

    class StringEvent(str, Enum):
        RESERVED = _ENGINE_EVENT_PREFIX + "untrusted"

    event = {
        "bytes": (_ENGINE_EVENT_PREFIX + "untrusted").encode("utf-8"),
        "enum": OrdinaryEvent.RESERVED,
        "str_enum": StringEvent.RESERVED,
    }[representation]
    path = tmp_path / "ledger.json"
    _primary(path)
    ledger = FileBudgetLedger(path)
    before = path.read_bytes()
    actions = {
        "spend": lambda: ledger.settle_spend(event, "run", Decimal("1"), payload_digest=_DIGEST),
        "begin": lambda: ledger.begin_producer_event(event, _DIGEST, "run", "model", "provider"),
        "producer": lambda: ledger.settle_producer_event(
            event, _DIGEST, _DIGEST, "run", "model", "provider", Decimal("1"), "reported"
        ),
        "reserve": lambda: ledger.reserve_compute(event, _DIGEST, "run", Decimal("1")),
        "compute": lambda: ledger.settle_compute(event, _DIGEST, _DIGEST, Decimal("1")),
        "unknown": lambda: ledger.mark_compute_unknown(event, _DIGEST),
    }
    error = ValueError if representation == "str_enum" else TypeError
    pattern = (
        "budget_ledger_engine_event_reserved"
        if representation == "str_enum"
        else "budget_ledger_event_id_invalid"
    )
    with pytest.raises(error, match=pattern):
        actions[operation]()
    assert path.read_bytes() == before


def test_normal_event_string_subclass_is_normalized_once(tmp_path: Path) -> None:
    class Event(str):
        def __str__(self) -> str:
            return "not-the-original-id"

    path = tmp_path / "ledger.json"
    _primary(path)
    ledger = FileBudgetLedger(path)
    receipt = ledger.settle_spend(
        Event("ordinary-event"), "run", Decimal("1"), payload_digest=_DIGEST
    )
    assert type(receipt.event_id) is str and receipt.event_id == "ordinary-event"
    assert ledger.resolve_spend("ordinary-event") == receipt


@pytest.mark.parametrize("method", ["resolve_spend", "resolve_producer_event", "resolve_compute"])
def test_event_resolution_normalizes_strings_and_allows_reserved_reads(
    tmp_path: Path, method: str
) -> None:
    class Event(str):
        def __hash__(self) -> int:
            return 0

        def __eq__(self, _other: object) -> bool:
            return False

    path = tmp_path / "ledger.json"
    _primary(path)
    ledger = FileBudgetLedger(path)
    resolve = getattr(ledger, method)
    assert resolve(Event(_ENGINE_EVENT_PREFIX + "absent")) is None
    with pytest.raises(TypeError, match="budget_ledger_event_id_invalid"):
        resolve(b"ordinary-event")
    if method == "resolve_spend":
        assert resolve(Event("effect-a")).event_id == "effect-a"


def test_strict_owner_refuses_unidentified_additive_mutations(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    before = path.read_bytes()
    with pytest.raises(ValueError, match="budget_ledger_unattributed_mutation_forbidden"):
        continued.record_spend_safe("run", Decimal("1"))
    assert path.read_bytes() == before


def test_confirmed_own_write_advances_guard_and_exact_retry_only_once(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    continued.pre_check("remaining", budget_key="run")
    receipt = continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert (
        continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
        == receipt
    )
    continued.pre_check("later", budget_key="run")
    snapshot = FileBudgetLedger(path).snapshot()
    assert snapshot.state.spent["run"] == Decimal("8")
    assert snapshot.spend_receipts["effect-b"] == receipt


def test_uncertain_own_write_reconfirms_same_event_without_duplicate_charge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    sync = ledger_module._fsync_dir

    def fail_sync(_directory: Path) -> None:
        raise OSError("persistent sync fault after owned replacement")

    monkeypatch.setattr(ledger_module, "_fsync_dir", fail_sync)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert json.loads(path.read_bytes())["state"]["spent"]["run"] == "8"
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        continued.pre_check("remaining", budget_key="run")
    monkeypatch.setattr(ledger_module, "_fsync_dir", sync)
    receipt = continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert (
        continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
        == receipt
    )
    assert FileBudgetLedger(path).snapshot().state.spent["run"] == Decimal("8")


def test_uncertain_candidate_cannot_authorize_a_different_valid_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)

    def fail_sync(_directory: Path) -> None:
        raise OSError("persistent sync fault after owned replacement")

    monkeypatch.setattr(ledger_module, "_fsync_dir", fail_sync)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    changed = json.loads(path.read_bytes())
    changed["state"]["spent"]["run"] = "9"
    path.write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as caught:
        continued.pre_check("remaining", budget_key="run")
    assert caught.value.event_id == "effect-b"
    assert caught.value.payload_digest == _DIGEST


@pytest.mark.parametrize("replacement", ["old_anchor", "missing"])
def test_unknown_owned_write_cannot_fall_back_to_old_anchor_or_missing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    anchor_bytes = path.read_bytes()
    sync = ledger_module._fsync_dir

    def fail_sync(_directory: Path) -> None:
        raise OSError("owned write published but its acknowledgment is unknown")

    monkeypatch.setattr(ledger_module, "_fsync_dir", fail_sync)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError):
        continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert json.loads(path.read_bytes())["state"]["spent"]["run"] == "8"
    pending = tmp_path / "actual-pending.json"
    os.replace(path, pending)
    if replacement == "old_anchor":
        restored = tmp_path / "old-anchor.json"
        restored.write_bytes(anchor_bytes)
        os.replace(restored, path)
    monkeypatch.setattr(ledger_module, "_fsync_dir", sync)

    dispatched: list[str] = []

    def producer() -> None:
        continued.pre_check("remaining", budget_key="run")
        dispatched.append("effect")

    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as caught:
        producer()
    assert dispatched == []
    assert caught.value.event_id == "effect-b"
    assert caught.value.payload_digest == _DIGEST

    os.replace(pending, path)
    receipt = continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert FileBudgetLedger(path).snapshot().state.spent["run"] == Decimal("8")
    assert FileBudgetLedger(path).resolve_spend("effect-b") == receipt


def test_missing_file_without_pending_write_is_not_reported_as_unknown(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    os.replace(path, tmp_path / "moved-ledger.json")
    with pytest.raises(FileNotFoundError):
        continued.pre_check("remaining", budget_key="run")


@pytest.mark.parametrize("kind", ["spend", "producer", "compute"])
def test_postreplace_sync_failure_reconfirms_each_exact_event_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    owner, resource, anchor = primary.continuation_binding()
    ledger = FileBudgetLedger(path)
    ledger.load_existing(
        owner, expected_resource_identity=resource, expected_snapshot_anchor=anchor
    )
    event = f"sync-unknown-{kind}"
    actions = {
        "spend": lambda: ledger.settle_spend(event, "run", Decimal("1"), payload_digest=_DIGEST),
        "producer": lambda: ledger.begin_producer_event(
            event, _DIGEST, "run", "fixture-model", "fixture-provider"
        ),
        "compute": lambda: ledger.reserve_compute(event, _DIGEST, "run", Decimal("1")),
    }
    sync = ledger_module._fsync_dir

    def fail_sync(_directory: Path) -> None:
        raise OSError("persistent sync fault after actual event publication")

    monkeypatch.setattr(ledger_module, "_fsync_dir", fail_sync)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as first:
        actions[kind]()
    assert (first.value.event_id, first.value.payload_digest) == (event, _DIGEST)
    persisted = json.loads(path.read_bytes())
    event_map = {
        "spend": "spend_receipts",
        "producer": "producer_settlements",
        "compute": "compute_reservations",
    }[kind]
    assert event in persisted[event_map]
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as repeated:
        actions[kind]()
    assert (repeated.value.event_id, repeated.value.payload_digest) == (event, _DIGEST)

    monkeypatch.setattr(ledger_module, "_fsync_dir", sync)
    result = actions[kind]()
    assert result.event_id == event
    snapshot = ledger.snapshot()
    if kind == "spend":
        assert snapshot.state.spent["run"] == Decimal("8")
        assert snapshot.spend_receipts[event] == result
    elif kind == "producer":
        assert snapshot.state.spent["run"] == Decimal("7")
        assert snapshot.producer_settlements[event] == result
    else:
        assert snapshot.state.spent["run"] == Decimal("7")
        assert snapshot.compute_reservations[event] == result


@pytest.mark.parametrize("kind", ["spend", "producer", "compute"])
def test_lock_exit_failure_after_confirmed_write_retains_event_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    owner, resource, anchor = primary.continuation_binding()
    ledger = FileBudgetLedger(path)
    ledger.load_existing(
        owner, expected_resource_identity=resource, expected_snapshot_anchor=anchor
    )
    event = f"post-write-{kind}"
    actions = {
        "spend": lambda: ledger.settle_spend(event, "run", Decimal("1"), payload_digest=_DIGEST),
        "producer": lambda: ledger.begin_producer_event(
            event, _DIGEST, "run", "fixture-model", "fixture-provider"
        ),
        "compute": lambda: ledger.reserve_compute(event, _DIGEST, "run", Decimal("1")),
    }
    sync = ledger_module._fsync_dir
    lock_path = path.with_suffix(path.suffix + ".lock")
    retained_lock = tmp_path / "actual-original.lock"
    replacement = tmp_path / "replacement.lock"

    def sync_and_replace_lock(directory: Path) -> None:
        sync(directory)
        os.replace(lock_path, retained_lock)
        replacement.touch()
        os.replace(replacement, lock_path)

    monkeypatch.setattr(ledger_module, "_fsync_dir", sync_and_replace_lock)
    with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as caught:
        actions[kind]()
    assert caught.value.event_id == event
    assert caught.value.payload_digest == _DIGEST
    monkeypatch.setattr(ledger_module, "_fsync_dir", sync)
    os.replace(retained_lock, lock_path)

    result = actions[kind]()
    assert result.event_id == event
    snapshot = ledger.snapshot()
    if kind == "spend":
        assert snapshot.state.spent["run"] == Decimal("8")
        assert snapshot.spend_receipts[event] == result
    elif kind == "producer":
        assert snapshot.state.spent["run"] == Decimal("7")
        assert snapshot.producer_settlements[event] == result
    else:
        assert snapshot.state.spent["run"] == Decimal("7")
        assert snapshot.compute_reservations[event] == result


@pytest.mark.parametrize("kind", ["producer", "compute"])
def test_postreplace_readback_error_retains_event_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    owner, resource, anchor = primary.continuation_binding()
    ledger = FileBudgetLedger(path)
    ledger.load_existing(
        owner, expected_resource_identity=resource, expected_snapshot_anchor=anchor
    )
    event = f"readback-unknown-{kind}"
    actions = {
        "producer": lambda: ledger.begin_producer_event(
            event, _DIGEST, "run", "fixture-model", "fixture-provider"
        ),
        "compute": lambda: ledger.reserve_compute(event, _DIGEST, "run", Decimal("1")),
    }
    sync, read_snapshot = ledger_module._fsync_dir, ledger._read_snapshot
    published = False

    def sync_and_arm(directory: Path) -> None:
        nonlocal published
        sync(directory)
        published = True

    def fail_published_readback():
        if published:
            raise ValueError("controlled readback corruption after event replacement")
        return read_snapshot()

    with monkeypatch.context() as patch:
        patch.setattr(ledger_module, "_fsync_dir", sync_and_arm)
        patch.setattr(ledger, "_read_snapshot", fail_published_readback)
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as caught:
            actions[kind]()
    assert (caught.value.event_id, caught.value.payload_digest) == (event, _DIGEST)
    result = actions[kind]()
    assert result.event_id == event
    assert ledger.snapshot().state.spent["run"] == Decimal("7")


def test_conflicting_prewrite_event_is_not_an_unknown_outcome(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    owner, resource, anchor = primary.continuation_binding()
    ledger = FileBudgetLedger(path)
    ledger.load_existing(
        owner, expected_resource_identity=resource, expected_snapshot_anchor=anchor
    )
    before = path.read_bytes()
    with pytest.raises(ValueError, match="settlement event ID conflicts"):
        ledger.settle_spend("effect-a", "run", Decimal("1"), payload_digest=_DIGEST)
    assert path.read_bytes() == before


@pytest.mark.parametrize("failure_point", ["unlock", "close"])
def test_lock_cleanup_failure_after_write_is_event_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_point: str
) -> None:
    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    lock_identity = os.stat(path.with_suffix(path.suffix + ".lock"))
    real_flock, real_close = fcntl.flock, os.close

    def fail_after_unlock(fd: int, operation: int) -> None:
        real_flock(fd, operation)
        if operation == fcntl.LOCK_UN:
            raise OSError("lock release acknowledgment lost")

    def fail_after_close(fd: int) -> None:
        details = os.fstat(fd)
        is_lock = (details.st_dev, details.st_ino) == (lock_identity.st_dev, lock_identity.st_ino)
        real_close(fd)
        if is_lock:
            raise OSError("lock close acknowledgment lost")

    with monkeypatch.context() as patch:
        if failure_point == "unlock":
            patch.setattr(fcntl, "flock", fail_after_unlock)
        else:
            patch.setattr(os, "close", fail_after_close)
        with pytest.raises(BudgetLedgerSettlementOutcomeUnknownError) as caught:
            continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert (caught.value.event_id, caught.value.payload_digest) == ("effect-b", _DIGEST)
    receipt = continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert FileBudgetLedger(path).resolve_spend("effect-b") == receipt
    assert FileBudgetLedger(path).snapshot().state.spent["run"] == Decimal("8")


def test_postwrite_control_exception_remains_primary_and_records_unknown_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Interrupted(BaseException):
        pass

    path = tmp_path / "ledger.json"
    primary, _old_bytes = _primary(path)
    continued = _continued(primary, path)
    sync = ledger_module._fsync_dir
    real_flock = fcntl.flock

    def interrupt_after_sync(directory: Path) -> None:
        sync(directory)
        raise Interrupted("controlled interruption")

    def fail_after_unlock(fd: int, operation: int) -> None:
        real_flock(fd, operation)
        if operation == fcntl.LOCK_UN:
            raise OSError("secondary lock release failure")

    with monkeypatch.context() as patch:
        patch.setattr(ledger_module, "_fsync_dir", interrupt_after_sync)
        patch.setattr(fcntl, "flock", fail_after_unlock)
        with pytest.raises(Interrupted, match="controlled interruption") as caught:
            continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert any("effect-b" in note and _DIGEST in note for note in caught.value.__notes__)
    assert any("budget lock release also failed" in note for note in caught.value.__notes__)
    receipt = continued.settle_spend_safe("effect-b", "run", Decimal("1"), payload_digest=_DIGEST)
    assert FileBudgetLedger(path).resolve_spend("effect-b") == receipt
    assert FileBudgetLedger(path).snapshot().state.spent["run"] == Decimal("8")
