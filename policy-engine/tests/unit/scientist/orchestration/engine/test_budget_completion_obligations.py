"""Real-file/process admission and completion obligations, separate from charges."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import select
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerCompletionObligation,
    BudgetLedgerCompletionOutcomeUnknownError,
    BudgetLedgerCompletionResolution,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

_CHILD = """
import json, sys
from decimal import Decimal
from pathlib import Path
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
path, action, key = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
before = path.read_bytes()
try:
    middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
    if action == 'precheck': middleware.pre_check('new-provider', key)
    elif action == 'reserve': assert middleware.reserve_safe(key, Decimal('.01'))
    elif action == 'spend': middleware.record_spend_safe(key, Decimal('.02'))
    elif action == 'load': middleware.budget_state
    else: raise ValueError(action)
    result = {'outcome': 'accepted'}
except (ValueError, OSError, RuntimeError) as error:
    result = {'outcome': 'refused', 'exception': type(error).__name__}
result['unchanged'] = before == path.read_bytes()
print(json.dumps(result))
"""


def _child(path: Path, action: str, key: str = "run") -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "-c", _CHILD, str(path), action, key],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    return json.loads(completed.stdout)


def _middleware(path: Path) -> BudgetMiddleware:
    return BudgetMiddleware(
        BudgetState(
            limits={key: BudgetLimit(key=key, max_usd=Decimal("10")) for key in ("run", "other")}
        ),
        ledger=FileBudgetLedger(path),
    )


def _record(
    *, amount: str | None = None, kind: str = "provider", owner_epoch: str = "observed-owner"
) -> BudgetLedgerCompletionObligation:
    body = {
        "event_id": "actual-attempt",
        "kind": kind,
        "amount": amount,
        "provider": "actual-provider",
        "request_digest": "request",
        "response_digest": "answer",
    }
    digest = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    return BudgetLedgerCompletionObligation(
        obligation_id="actual-attempt",
        event_payload=body,
        event_digest=digest,
        run_id="actual-run",
        owner_epoch=owner_epoch,
        budget_keys=("run",),
        reserved_amounts={"run": Decimal(".01")},
        phase="cost_unknown" if amount is None else "ledger_ack_unknown",
    )


def _receipt(middleware: BudgetMiddleware, record: BudgetLedgerCompletionObligation) -> str:
    receipt = middleware.settle_spend_safe(
        record.event_payload["event_id"] + ":budget:" + hashlib.sha256(b"run").hexdigest(),
        "run",
        Decimal(record.event_payload["amount"]),
        provider="actual-provider",
        payload_digest=hashlib.sha256(f"{record.event_digest}:run".encode()).hexdigest(),
    )
    return receipt.event_id


class _ActualAuditResolver:
    def __init__(self, path: Path) -> None:
        self.path = path

    def resolve(self, record, owner_resolution_ref):
        # Resolve exact published bytes; an arbitrary ref/boolean cannot clear.
        assert owner_resolution_ref == str(self.path)
        assert json.loads(self.path.read_text()) == record.required_action
        return BudgetLedgerCompletionResolution(
            obligation_id=record.obligation_id,
            record_digest=record.payload_digest,
            phase=record.phase,
            known_receipt_ids=record.known_receipt_ids,
            owner_resolution_ref=owner_resolution_ref,
        )


def test_unknown_cost_reopen_blocks_same_key_but_other_key_can_reserve(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    assert middleware.reserve_safe("run", Decimal(".01"))
    record = middleware.retain_completion_obligation_safe(_record())
    for action in ("precheck", "reserve"):
        result = _child(path, action)
        assert result == {
            "outcome": "refused",
            "exception": "BudgetLedgerCompletionRequiredError",
            "unchanged": True,
        }
    assert _child(path, "reserve", "other")["outcome"] == "accepted"
    # Already observed work and reservation release do not erase the gate.
    middleware.record_spend_safe("other", Decimal(".02"))
    middleware.release_safe("run", Decimal(".01"))
    assert FileBudgetLedger(path).snapshot().completion_obligations[record.obligation_id] == record
    assert not FileBudgetLedger(path).snapshot().spend_receipts
    assert _child(path, "precheck")["exception"] == "BudgetLedgerCompletionRequiredError"


def test_known_charge_survives_audit_failure_and_exact_reconciliation_never_recharges(
    tmp_path: Path,
) -> None:
    path, audit = tmp_path / "ledger.json", tmp_path / "protected-act.json"
    middleware = _middleware(path)
    record = middleware.retain_completion_obligation_safe(_record(amount=".02"))
    receipt_id = _receipt(middleware, record)
    action = {
        "run_id": "actual-run",
        "actor": "budget-owner",
        "action": "COMMITTED",
        "metadata": {"original_attempt": record.event_payload["event_id"]},
    }
    pending = middleware.transition_completion_obligation_safe(
        record.model_copy(
            update={
                "phase": "protected_audit_pending",
                "known_receipt_ids": (receipt_id,),
                "required_action": action,
            }
        ),
        record.payload_digest,
    )
    middleware.release_safe("run", Decimal(".01"))
    bound = middleware.with_completion_resolver(_ActualAuditResolver(audit))
    audit.mkdir()
    before = path.read_bytes()
    with pytest.raises(IsADirectoryError):
        bound.complete_completion_obligation_safe(
            pending.obligation_id, pending.payload_digest, (receipt_id,), str(audit)
        )
    assert path.read_bytes() == before
    assert _child(path, "reserve")["exception"] == "BudgetLedgerCompletionRequiredError"
    audit.rmdir()
    with audit.open("w") as stream:
        json.dump(action, stream)
        stream.flush()
        os.fsync(stream.fileno())
    assert bound.complete_completion_obligation_safe(
        pending.obligation_id, pending.payload_digest, (receipt_id,), str(audit)
    )
    reopened = FileBudgetLedger(path).snapshot()
    assert reopened.state.spent["run"] == Decimal(".02")
    assert len(reopened.spend_receipts) == 1 and not reopened.completion_obligations
    assert not bound.complete_completion_obligation_safe(
        pending.obligation_id, pending.payload_digest, (receipt_id,), str(audit)
    )
    assert _child(path, "precheck")["outcome"] == "accepted"


@pytest.mark.parametrize(
    "change",
    [
        {"run_id": "foreign-run"},
        {"budget_keys": ("other",), "reserved_amounts": {"other": Decimal(".01")}},
        {"event_digest": "0" * 64},
        {"phase": "ledger_ack_unknown"},
    ],
)
def test_unknown_event_cannot_be_rewritten_to_clear_pending(tmp_path: Path, change: dict) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    record = middleware.retain_completion_obligation_safe(_record())
    before = path.read_bytes()
    with pytest.raises(ValueError):
        middleware.transition_completion_obligation_safe(
            record.model_copy(update=change), record.payload_digest
        )
    assert path.read_bytes() == before
    with pytest.raises(ValueError):
        middleware.complete_completion_obligation_safe(
            record.obligation_id, record.payload_digest, ()
        )
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "missing",
    [
        "completion_obligations",
        "obligation_id",
        "event_payload",
        "event_digest",
        "run_id",
        "owner_epoch",
        "budget_keys",
        "reserved_amounts",
        "phase",
        "known_receipt_ids",
    ],
)
def test_current_wire_missing_completion_fields_fails_real_child_unchanged(
    tmp_path: Path, missing: str
) -> None:
    path = tmp_path / "ledger.json"
    record = _middleware(path).retain_completion_obligation_safe(_record())
    wire = json.loads(path.read_text())
    if missing == "completion_obligations":
        del wire[missing]
    else:
        del wire["completion_obligations"][record.obligation_id][missing]
    path.write_text(json.dumps(wire))
    for action in ("load", "precheck", "reserve", "spend"):
        result = _child(path, action)
        assert result["outcome"] == "refused" and result["unchanged"], result


@pytest.mark.parametrize("version", ["1.0", "1.1"])
def test_full_legacy_snapshots_migrate_explicitly_without_attesting_unknown_old_cost(
    tmp_path: Path, version: str
) -> None:
    path = tmp_path / "ledger.json"
    _middleware(path)
    wire = json.loads(path.read_text())
    wire["schema_version"] = version
    del wire["completion_obligations"]
    if version == "1.0":
        del wire["spend_receipts"]
    path.write_text(json.dumps(wire))
    before = path.read_bytes()
    assert FileBudgetLedger(path).load().spent == {} and path.read_bytes() == before
    _middleware(path)
    current = FileBudgetLedger(path).snapshot()
    assert current.schema_version == "1.2" and not current.completion_obligations
    damaged = copy.deepcopy(wire)
    del damaged["state"]["spent"]
    path.write_text(json.dumps(damaged))
    assert _child(path, "reserve")["unchanged"]
    assert _child(path, "reserve")["outcome"] == "refused"


@pytest.mark.parametrize(
    "fault,published", [("fsync", False), ("replace", False), ("directory", True)]
)
def test_completion_publication_fault_reopens_complete_old_or_new_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str, published: bool
) -> None:
    import polisyos.scientist.orchestration.engine.budget_ledger as module

    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    record = _record()
    actual_fsync, actual_replace = module.os.fsync, module.os.replace
    replaced = False

    def fsync(fd):
        if fault == "fsync" or (fault == "directory" and replaced):
            raise OSError("actual fsync refusal")
        return actual_fsync(fd)

    def replace(source, target):
        nonlocal replaced
        if fault == "replace":
            raise OSError("actual replacement refusal")
        result = actual_replace(source, target)
        replaced = True
        return result

    with monkeypatch.context() as patch:
        patch.setattr(module.os, "fsync", fsync)
        patch.setattr(module.os, "replace", replace)
        with pytest.raises(BudgetLedgerCompletionOutcomeUnknownError):
            middleware.retain_completion_obligation_safe(record)
    snapshot = FileBudgetLedger(path).snapshot()
    assert bool(snapshot.completion_obligations) is published
    assert snapshot.schema_version == "1.2" and not snapshot.spend_receipts
    assert snapshot.state.limits["run"].max_usd == 10
    # A before-publication failure lacks a persisted event; no crash recovery
    # or fresh-owner unknown-cost safety is claimed for that boundary.
    assert _child(path, "load")["outcome"] == "accepted"


def _intent(
    middleware: BudgetMiddleware, event_id: str = "actual-attempt", key: str = "run"
) -> BudgetLedgerCompletionObligation:
    body = {
        "event_id": event_id,
        "kind": "provider_intent",
        "amount": None,
        "request_digest": "request",
        "request": {"operation": "write actual response"},
    }
    return BudgetLedgerCompletionObligation(
        obligation_id=event_id,
        event_payload=body,
        event_digest="sha256:"
        + hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        run_id="actual-run",
        owner_epoch=middleware.completion_owner_epoch,
        budget_keys=(key,),
        reserved_amounts={key: Decimal(".01")},
        phase="provider_in_flight",
    )


def _physical_work(path: Path, attempt: str) -> None:
    with path.open("a") as stream:
        stream.write(json.dumps({"attempt": attempt, "response": "actual response"}) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


@pytest.mark.parametrize("after_work", [False, True])
@pytest.mark.parametrize("fault", ["fsync", "replace", "directory"])
def test_intent_faults_never_lose_physical_admission_uncertainty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, after_work: bool, fault: str
) -> None:
    import polisyos.scientist.orchestration.engine.budget_ledger as module

    path, work = tmp_path / "ledger.json", tmp_path / "provider.jsonl"
    middleware = _middleware(path)
    intent = _intent(middleware)
    if after_work:
        assert middleware.admit_provider_intent_safe(intent)
        _physical_work(work, intent.obligation_id)
    observed = _record(owner_epoch=intent.owner_epoch)
    actual_fsync, actual_replace = module.os.fsync, module.os.replace
    replaced = False

    def fsync(fd):
        if fault == "fsync" or (fault == "directory" and replaced):
            raise OSError("actual fsync refusal")
        return actual_fsync(fd)

    def replace(source, target):
        nonlocal replaced
        if fault == "replace":
            raise OSError("actual replacement refusal")
        result = actual_replace(source, target)
        replaced = True
        return result

    with monkeypatch.context() as patch:
        patch.setattr(module.os, "fsync", fsync)
        patch.setattr(module.os, "replace", replace)

        def perform():
            if after_work:
                middleware.transition_completion_obligation_safe(observed, intent.payload_digest)
            elif middleware.admit_provider_intent_safe(intent):
                _physical_work(work, intent.obligation_id)

        with pytest.raises(BudgetLedgerCompletionOutcomeUnknownError):
            perform()
    assert (len(work.read_text().splitlines()) if work.exists() else 0) == int(after_work)
    snapshot = FileBudgetLedger(path).snapshot()
    assert not snapshot.spend_receipts and snapshot.state.limits["run"].max_usd == 10
    if after_work or fault == "directory":
        assert _child(path, "reserve")["exception"] == "BudgetLedgerCompletionRequiredError"
    # A clone of this same owner cannot exploit an old in-flight disk phase.
    sibling = middleware.with_completion_resolver(_ActualAuditResolver(tmp_path / "unused"))
    if after_work and fault != "directory":
        # Replaying the exact older disk record is not acknowledgment of the
        # observed completion whose publication failed. Keep that uncertainty.
        sibling.transition_completion_obligation_safe(intent, intent.payload_digest)
    with pytest.raises(RuntimeError):
        sibling.admit_provider_intent_safe(_intent(sibling, "second-attempt"))
    assert (len(work.read_text().splitlines()) if work.exists() else 0) == int(after_work)
    assert sibling.admit_provider_intent_safe(_intent(sibling, "different-key", "other"))


def test_four_controlled_live_intents_are_concurrent_but_unknown_blocks_new_work(
    tmp_path: Path,
) -> None:
    path, work = tmp_path / "ledger.json", tmp_path / "provider.jsonl"
    middleware = _middleware(path)

    def producer(number):
        intent = _intent(middleware, f"attempt-{number}")
        assert middleware.admit_provider_intent_safe(intent)
        _physical_work(work, intent.obligation_id)
        return intent

    with ThreadPoolExecutor(max_workers=4) as workers:
        intents = list(workers.map(producer, range(4)))
    assert len(work.read_text().splitlines()) == 4
    snapshot = FileBudgetLedger(path).snapshot()
    assert len(snapshot.completion_obligations) == 4
    assert snapshot.state.reserved["run"] == Decimal(".04")
    assert _child(path, "precheck")["exception"] == "BudgetLedgerCompletionRequiredError"
    middleware.pre_check("controlled-sibling")
    event = _record(owner_epoch=middleware.completion_owner_epoch)
    body = {**event.event_payload, "event_id": intents[0].obligation_id}
    unknown = event.model_copy(
        update={
            "obligation_id": intents[0].obligation_id,
            "event_payload": body,
            "event_digest": "sha256:"
            + hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
        }
    )
    middleware.transition_completion_obligation_safe(unknown, intents[0].payload_digest)
    with pytest.raises(RuntimeError):
        middleware.admit_provider_intent_safe(_intent(middleware, "fifth"))
    with pytest.raises(RuntimeError):
        middleware.reserve_safe("run", Decimal(".01"))
    assert len(work.read_text().splitlines()) == 4


def test_inherited_live_owner_cannot_admit_after_actual_fork(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    intent = _intent(middleware)
    assert middleware.admit_provider_intent_safe(intent)
    read_fd, write_fd = os.pipe()
    child_pid = os.fork()
    if child_pid == 0:
        os.close(read_fd)
        try:
            middleware.pre_check("foreign-fork")
            observed = "accepted"
        except RuntimeError as error:
            observed = type(error).__name__
        os.write(write_fd, observed.encode())
        os.close(write_fd)
        os._exit(0)
    os.close(write_fd)
    observed = os.read(read_fd, 1024).decode()
    os.close(read_fd)
    _, status = os.waitpid(child_pid, 0)
    assert status == 0 and observed == "BudgetLedgerCompletionRequiredError"
    assert len(FileBudgetLedger(path).snapshot().completion_obligations) == 1


_ADMISSION_CHILD = """
import json, os, signal, sys
from pathlib import Path
import polisyos.scientist.orchestration.engine.budget_ledger as module
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerCompletionObligation, FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
path, work, mode, spec = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], json.loads(sys.argv[4])
middleware = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(path))
spec['owner_epoch'] = middleware.completion_owner_epoch
intent = BudgetLedgerCompletionObligation.model_validate_json(json.dumps(spec), strict=True)
actual_replace = module.os.replace
def replace(source, target):
    if mode == 'barrier':
        print('entered-real-replace', flush=True)
        assert sys.stdin.readline().strip() == 'publish'
    result = actual_replace(source, target)
    if mode == 'kill': os.kill(os.getpid(), signal.SIGKILL)
    return result
module.os.replace = replace
assert middleware.admit_provider_intent_safe(intent)
with work.open('a') as stream:
    stream.write(json.dumps({'attempt': intent.obligation_id}) + '\\n')
    stream.flush()
    os.fsync(stream.fileno())
print('physical-work-complete', flush=True)
"""


@pytest.mark.parametrize("mode", ["barrier", "kill"])
def test_actual_process_publication_serializes_fresh_admission_or_retains_killed_intent(
    tmp_path: Path, mode: str
) -> None:
    path, work = tmp_path / "ledger.json", tmp_path / "provider.jsonl"
    middleware = _middleware(path)
    arguments = [
        sys.executable,
        "-c",
        _ADMISSION_CHILD,
        str(path),
        str(work),
        mode,
        _intent(middleware).model_dump_json(),
    ]
    with subprocess.Popen(
        arguments, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    ) as publisher:
        if mode == "barrier":
            assert publisher.stdout is not None and publisher.stdin is not None
            ready, _, _ = select.select([publisher.stdout], [], [], 30)
            assert ready, "publisher failed to reach real atomic replacement"
            assert publisher.stdout.readline().strip() == "entered-real-replace"
            # Reader invokes actual middleware/ledger while the publisher owns
            # the stable lock. No check followed by a separate reserve is used.
            reader = subprocess.Popen(
                [sys.executable, "-c", _CHILD, str(path), "reserve", "run"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            publisher.stdin.write("publish\n")
            publisher.stdin.flush()
            reader_out, reader_err = reader.communicate(timeout=30)
            assert reader.returncode == 0, reader_out + reader_err
            assert json.loads(reader_out)["exception"] == "BudgetLedgerCompletionRequiredError"
        stdout, stderr = publisher.communicate(timeout=30)
        assert publisher.returncode == (0 if mode == "barrier" else -9), stdout + stderr
    snapshot = FileBudgetLedger(path).snapshot()
    assert len(snapshot.completion_obligations) == 1 and not snapshot.spend_receipts
    assert snapshot.state.reserved["run"] == Decimal(".01")
    assert (len(work.read_text().splitlines()) if work.exists() else 0) == (mode == "barrier")
    assert _child(path, "precheck")["exception"] == "BudgetLedgerCompletionRequiredError"
    # SIGKILL attests process interruption after replace, not power-loss durability.


def test_same_amount_foreign_receipt_and_boolean_resolver_cannot_clear_actual_pending(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    record = middleware.retain_completion_obligation_safe(_record(amount=".02"))
    foreign = middleware.settle_spend_safe(
        "different-producer",
        "run",
        Decimal(".02"),
        provider="actual-provider",
        payload_digest="a" * 64,
    )
    before = path.read_bytes()
    with pytest.raises(ValueError):
        middleware.transition_completion_obligation_safe(
            record.model_copy(update={"known_receipt_ids": (foreign.event_id,)}),
            record.payload_digest,
        )
    assert path.read_bytes() == before
    receipt_id = _receipt(middleware, record)
    known = middleware.transition_completion_obligation_safe(
        record.model_copy(update={"known_receipt_ids": (receipt_id,)}), record.payload_digest
    )

    class BooleanResolver:
        def resolve(self, obligation, owner_resolution_ref):
            return True

    bound = middleware.with_completion_resolver(BooleanResolver())
    before = path.read_bytes()
    with pytest.raises(ValueError):
        bound.complete_completion_obligation_safe(
            known.obligation_id, known.payload_digest, known.known_receipt_ids, "asserted-success"
        )
    assert path.read_bytes() == before
    assert _child(path, "precheck")["exception"] == "BudgetLedgerCompletionRequiredError"


class _UnenteredWorkResolver:
    def __init__(self, work: Path) -> None:
        self.work = work

    def resolve(self, record, owner_resolution_ref):
        if self.work.exists():
            raise RuntimeError("actual producer work was entered")
        return BudgetLedgerCompletionResolution(
            obligation_id=record.obligation_id,
            record_digest=record.payload_digest,
            phase=record.phase,
            known_receipt_ids=(),
            owner_resolution_ref=owner_resolution_ref,
            status="not_admitted",
        )


@pytest.mark.parametrize("publication_failed", [False, True])
def test_original_unentered_owner_abort_restores_only_its_actual_reserved_amount(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, publication_failed: bool
) -> None:
    import polisyos.scientist.orchestration.engine.budget_ledger as module

    path, work = tmp_path / "ledger.json", tmp_path / "provider.jsonl"
    middleware = _middleware(path)
    assert middleware.reserve_safe("run", Decimal(".03"))
    intent = _intent(middleware)
    if publication_failed:

        def refuse_replace(source, target):
            raise OSError("intent replacement refused before physical work")

        with monkeypatch.context() as patch:
            patch.setattr(module.os, "replace", refuse_replace)
            with pytest.raises(BudgetLedgerCompletionOutcomeUnknownError):
                middleware.admit_provider_intent_safe(intent)
    else:
        assert middleware.admit_provider_intent_safe(intent)
    bound = middleware.with_completion_resolver(_UnenteredWorkResolver(work))
    assert bound.abort_provider_intent_safe(intent.obligation_id, intent.payload_digest)
    assert FileBudgetLedger(path).snapshot().state.reserved["run"] == Decimal(".03")
    assert not FileBudgetLedger(path).snapshot().completion_obligations
    bound.pre_check("later-unentered-control")


def test_actual_entered_work_and_fresh_owner_cannot_abort_original_intent(tmp_path: Path) -> None:
    path, work = tmp_path / "ledger.json", tmp_path / "provider.jsonl"
    middleware = _middleware(path)
    intent = _intent(middleware)
    assert middleware.admit_provider_intent_safe(intent)
    _physical_work(work, intent.obligation_id)
    for owner in (
        middleware.with_completion_resolver(_UnenteredWorkResolver(work)),
        _middleware(path).with_completion_resolver(_UnenteredWorkResolver(work)),
    ):
        before = path.read_bytes()
        with pytest.raises((ValueError, RuntimeError)):
            owner.abort_provider_intent_safe(intent.obligation_id, intent.payload_digest)
        assert path.read_bytes() == before


def test_failed_second_key_reservation_leaves_no_partial_intent_or_first_key_charge(
    tmp_path: Path,
) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    intent = _intent(middleware).model_copy(
        update={
            "budget_keys": ("run", "other"),
            "reserved_amounts": {"run": Decimal(".01"), "other": Decimal("11")},
        }
    )
    before = path.read_bytes()
    assert not middleware.admit_provider_intent_safe(intent)
    assert path.read_bytes() == before
    assert not FileBudgetLedger(path).snapshot().state.reserved
