"""Real-process durable settlement acknowledgment and exact-retry witnesses."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware

_DIGEST = hashlib.sha256(b"actual immutable producer response").hexdigest()
_EVENT = {
    "event_id": "producer/run/request-1:run",
    "key": "run",
    "amount": "2",
    "provider": "provider",
    "payload_digest": _DIGEST,
}

_CHILD = r"""
import hashlib, json, os, signal, stat, sys
from decimal import Decimal
from pathlib import Path
from polisyos.scientist.orchestration.engine import budget_ledger as module
from polisyos.scientist.orchestration.engine.budget import BudgetState
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
assert Path(module.__file__).resolve().is_relative_to(Path(sys.argv[3]))
path, action, spec = Path(sys.argv[1]), sys.argv[2], json.loads(sys.argv[4])
ledger = module.FileBudgetLedger(path, mutation_history_limit=2)
before = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
try:
    if action == "load":
        state = ledger.load()
        receipt = None
    else:
        middleware = BudgetMiddleware(BudgetState(), ledger=ledger)
        if action == "concurrent":
            print("READY", flush=True)
            assert sys.stdin.readline().strip() == "GO"
        if action == "fault":
            stage = spec.pop("fault")
            actual_fsync, actual_replace = os.fsync, os.replace
            def fsync(fd):
                directory = stat.S_ISDIR(os.fstat(fd).st_mode)
                if (stage == "file_fsync" and not directory
                        or stage == "directory_fsync" and directory):
                    raise OSError("actual settlement publication fault")
                return actual_fsync(fd)
            def replace(source, target):
                if Path(target) == path and stage == "replace_before":
                    raise OSError("settlement replacement refused")
                result = actual_replace(source, target)
                if Path(target) == path and stage == "kill_after_replace":
                    os.kill(os.getpid(), signal.SIGKILL)
                return result
            os.fsync, os.replace = fsync, replace
        if action == "resolve":
            receipt = middleware.resolve_spend_safe(spec["event_id"])
        elif action == "owner":
            receipt = None
        else:
            spec["amount"] = Decimal(spec["amount"])
            receipt = middleware.settle_spend_safe(**spec)
        state = middleware.budget_state
    out = {"status": "accepted", "state": state.model_dump(mode="json"),
           "receipt": receipt.model_dump(mode="json") if receipt is not None else None}
    if action == "owner":
        out["owner"] = middleware.settlement_owner_identity
except (ValueError, OSError, RuntimeError) as error:
    out = {"status": "refused", "exception": type(error).__name__}
    if isinstance(error, module.BudgetLedgerSettlementOutcomeUnknownError):
        out.update(status="unknown", event_id=error.event_id, payload_digest=error.payload_digest)
out["before"] = before
out["after"] = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
print(json.dumps(out))
"""


def _command(path: Path, action: str, spec: dict[str, Any]) -> tuple[list[str], dict[str, str]]:
    source_root = Path(__file__).resolve().parents[5] / "src"
    return (
        [sys.executable, "-c", _CHILD, str(path), action, str(source_root), json.dumps(spec)],
        {**os.environ, "PYTHONPATH": str(source_root)},
    )


def _child(path: Path, action: str, spec: dict[str, Any] | None = None) -> dict[str, Any]:
    command, env = _command(path, action, spec or _EVENT)
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=30, check=False
    )
    if result.returncode == -9:
        return {"status": "killed"}
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _middleware(path: Path, *, history: int = 2) -> BudgetMiddleware:
    return BudgetMiddleware(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))}),
        ledger=FileBudgetLedger(
            path, ledger_id="ledger:actual-owner", mutation_history_limit=history
        ),
    )


def _settle(middleware: BudgetMiddleware) -> Any:
    return middleware.settle_spend_safe(**{**_EVENT, "amount": Decimal(_EVENT["amount"])})


def test_exact_event_retry_survives_restart_and_bounded_journal_eviction(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    middleware = _middleware(path)
    first = _settle(middleware)
    assert middleware.budget_state.spent["run"] == Decimal("2")
    for _ in range(4):
        middleware.record_spend_safe("run", Decimal("1"), provider="provider")
    snapshot = FileBudgetLedger(path).snapshot()
    assert len(snapshot.recent_mutations) == 2
    assert all(m.operation != "settle_spend" for m in snapshot.recent_mutations)
    before = path.read_bytes()
    repeated = _child(path, "settle")
    assert repeated["receipt"] == first.model_dump(mode="json")
    assert repeated["state"]["spent"]["run"] == "6"
    assert repeated["before"] == repeated["after"]
    assert path.read_bytes() == before
    assert _child(path, "resolve")["receipt"] == repeated["receipt"]


@pytest.mark.parametrize(
    "change",
    [{"amount": "3"}, {"key": "other"}, {"provider": "other"}, {"payload_digest": "0" * 64}],
)
def test_conflicting_event_identity_refuses_without_modifying_bytes(
    tmp_path: Path,
    change: dict[str, str],
) -> None:
    path = tmp_path / "ledger.json"
    _settle(_middleware(path))
    observed = _child(path, "settle", {**_EVENT, **change})
    assert observed["exception"] == "ValueError", observed
    assert observed["before"] == observed["after"]
    assert _child(path, "resolve")["state"]["spent"]["run"] == "2"


@pytest.mark.parametrize(
    "stage,published",
    [
        ("file_fsync", False),
        ("replace_before", False),
        ("directory_fsync", True),
        ("kill_after_replace", True),
    ],
)
def test_lost_ack_remains_unknown_until_actual_reopen_and_exact_retry(
    tmp_path: Path,
    stage: str,
    published: bool,
) -> None:
    path = tmp_path / "ledger.json"
    _middleware(path)
    fault = _child(path, "fault", {**_EVENT, "fault": stage})
    if stage == "kill_after_replace":
        assert fault["status"] == "killed"
    else:
        assert fault["status"] == "unknown", fault
        assert fault["event_id"] == _EVENT["event_id"]
        assert fault["payload_digest"] == _DIGEST
    reopened = _child(path, "resolve")
    assert (reopened["receipt"] is not None) is published
    assert reopened["state"]["spent"].get("run", "0") == ("2" if published else "0")
    retried = _child(path, "settle")
    assert retried["state"]["spent"]["run"] == "2"
    assert _child(path, "settle")["receipt"] == retried["receipt"]


def test_concurrent_actual_middleware_producers_apply_same_event_once(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _middleware(path)
    processes = []
    for _ in range(4):
        command, env = _command(path, "concurrent", _EVENT)
        processes.append(
            subprocess.Popen(
                command,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        )
    for process in processes:
        assert process.stdout is not None
        assert process.stdout.readline().strip() == "READY"
    for process in processes:
        assert process.stdin is not None
        process.stdin.write("GO\n")
        process.stdin.flush()
    results = []
    for process in processes:
        output, error = process.communicate(timeout=30)
        assert process.returncode == 0, output + error
        results.append(json.loads(output))
    assert all(r["status"] == "accepted" for r in results)
    assert all(r["receipt"] == results[0]["receipt"] for r in results)
    final = _child(path, "resolve")
    assert final["state"]["spent"]["run"] == "2"
    assert final["state"]["provider_spent"]["provider"] == "2"
    assert final["receipt"]["revision"] == 1


def test_complete_legacy_wire_upgrades_but_sparse_legacy_never_defaults(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    _middleware(path)
    old = json.loads(path.read_bytes())
    old["schema_version"] = "1.0"
    del old["spend_receipts"]
    del old["completion_obligations"]
    path.write_text(json.dumps(old))
    before = path.read_bytes()
    assert _child(path, "load")["status"] == "accepted"
    assert path.read_bytes() == before
    assert _child(path, "settle")["receipt"]["revision"] == 1
    assert json.loads(path.read_bytes())["schema_version"] == "1.2"
    for missing in ("limits", "spent", "provider_spent", "reserved"):
        damaged = copy.deepcopy(old)
        del damaged["state"][missing]
        path.write_text(json.dumps(damaged))
        observed = _child(path, "settle")
        assert observed["exception"] == "ValueError", observed
        assert observed["before"] == observed["after"]


@pytest.mark.parametrize(
    "missing",
    ["event_id", "payload_digest", "key", "amount", "revision", "committed_at", "spend_receipts"],
)
def test_required_settlement_wire_fields_cannot_silently_forget_ack(
    tmp_path: Path,
    missing: str,
) -> None:
    path = tmp_path / "ledger.json"
    _settle(_middleware(path))
    wire = json.loads(path.read_bytes())
    if missing == "spend_receipts":
        del wire[missing]
    else:
        del wire["spend_receipts"][_EVENT["event_id"]][missing]
    path.write_text(json.dumps(wire))
    for action in ("load", "resolve", "settle"):
        observed = _child(path, action)
        assert observed["exception"] == "ValueError", observed
        assert observed["before"] == observed["after"]


@pytest.mark.parametrize(
    "tamper",
    [
        "identity",
        "revision",
        "spend",
        "provider",
        "schema_type",
        "schema_unknown",
        "canonical_contract",
        "coordination_mode",
    ],
)
def test_inconsistent_settlement_wire_refuses_all_actual_inlets(
    tmp_path: Path, tamper: str
) -> None:
    path = tmp_path / "ledger.json"
    _settle(_middleware(path))
    wire = json.loads(path.read_bytes())
    receipt = wire["spend_receipts"][_EVENT["event_id"]]
    if tamper == "identity":
        receipt["event_id"] = "another-event"
    elif tamper == "revision":
        receipt["revision"] = wire["revision"] + 1
    elif tamper == "spend":
        wire["state"]["spent"]["run"] = "1"
    elif tamper == "provider":
        wire["state"]["provider_spent"]["provider"] = "1"
    elif tamper == "schema_type":
        wire["schema_version"] = []
    elif tamper == "schema_unknown":
        wire["schema_version"] = "999.99"
    else:
        wire[tamper] = "foreign-unsupported-contract"
    path.write_text(json.dumps(wire))
    for action in ("load", "resolve", "settle"):
        observed = _child(path, action)
        assert observed["exception"] == "ValueError", observed
        assert observed["before"] == observed["after"]


def test_memory_only_middleware_cannot_issue_durable_ack_or_owner_identity() -> None:
    middleware = BudgetMiddleware(BudgetState())
    with pytest.raises(RuntimeError, match="configured ledger"):
        _settle(middleware)
    with pytest.raises(RuntimeError, match="configured ledger"):
        middleware.resolve_spend_safe(_EVENT["event_id"])
    with pytest.raises(RuntimeError, match="configured ledger"):
        _ = middleware.settlement_owner_identity
    assert middleware.budget_state.spent == {}


def test_cold_settlement_cannot_publish_an_implicit_unlimited_ledger(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    ledger = FileBudgetLedger(path)
    with pytest.raises(FileNotFoundError, match="explicit load_or_bootstrap"):
        ledger.settle_spend(**{**_EVENT, "amount": Decimal("2")})
    assert not path.exists()
    with pytest.raises(FileNotFoundError):
        ledger.resolve_spend(_EVENT["event_id"])


def test_nullable_provider_omission_is_valid_in_a_real_settlement_receipt(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    observed = _child(path, "settle", {**_EVENT, "provider": None})
    assert observed["receipt"]["provider"] is None
    wire = json.loads(path.read_bytes())
    assert "provider" not in wire["spend_receipts"][_EVENT["event_id"]]
    assert _child(path, "resolve")["receipt"] == observed["receipt"]


def test_owner_identity_is_actual_persisted_and_stable_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    with pytest.raises(FileNotFoundError):
        _ = FileBudgetLedger(path).settlement_owner_identity
    middleware = _middleware(path)
    expected = middleware.settlement_owner_identity
    assert expected[0] == "ledger:actual-owner"
    assert tuple(_child(path, "owner")["owner"]) == expected
    wire = json.loads(path.read_bytes())
    wire.pop("ledger_id")
    path.write_text(json.dumps(wire))
    with pytest.raises(ValueError, match="persisted ledger identity"):
        _ = middleware.settlement_owner_identity
