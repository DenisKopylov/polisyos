"""Real-process budget ledger admission, publication and recovery controls."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSnapshot,
    FileBudgetLedger,
)

_CHILD = r"""
import hashlib, json, os, signal, stat, sys
from decimal import Decimal
from pathlib import Path
from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError, BudgetLimit, BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
import polisyos.scientist.orchestration.engine.budget_ledger as source_module
assert Path(source_module.__file__).resolve().is_relative_to(Path(sys.argv[3]))

path, action = Path(sys.argv[1]), sys.argv[2]
ledger = FileBudgetLedger(path)
configured = BudgetState(
    limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
    spent={"run": Decimal("10")},
)
def signature():
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None
before = signature()
try:
    if action in {"fault_bootstrap", "fault_spend"}:
        stage = sys.argv[4]
        actual_fsync, actual_replace = os.fsync, os.replace
        def injected_fsync(fd):
            directory = stat.S_ISDIR(os.fstat(fd).st_mode)
            if stage == "file_fsync" and not directory:
                raise OSError("injected file fsync failure")
            if stage == "directory_fsync" and directory:
                raise OSError("injected directory fsync after publication")
            return actual_fsync(fd)
        def injected_replace(source, destination):
            if Path(destination) == path:
                if stage == "replace_before":
                    raise OSError("injected replacement failure")
                if stage == "kill_before_replace":
                    os.kill(os.getpid(), signal.SIGKILL)
                result = actual_replace(source, destination)
                if stage == "kill_after_replace":
                    os.kill(os.getpid(), signal.SIGKILL)
                return result
            return actual_replace(source, destination)
        os.fsync, os.replace = injected_fsync, injected_replace
        state = (ledger.load_or_bootstrap(configured) if action == "fault_bootstrap"
                 else ledger.record_spend("run", Decimal("1")).state)
    elif action in {"concurrent_writer", "concurrent_reader"}:
        middleware = BudgetMiddleware(configured, ledger=ledger)
        print("READY", flush=True)
        assert sys.stdin.readline().strip() == "GO"
        if action == "concurrent_writer":
            for _ in range(25):
                middleware.record_spend_safe("run", Decimal("1"), provider="provider")
        else:
            previous = Decimal("0")
            for _ in range(50):
                observed = middleware.budget_state
                assert observed.limits["run"].max_usd == Decimal("100")
                current = observed.spent.get("run", Decimal("0"))
                assert previous <= current <= Decimal("100")
                previous = current
        state = middleware.budget_state
    elif action == "spend":
        state = ledger.record_spend("run", Decimal("1")).state
    elif action == "unlimited":
        state = ledger.load_or_bootstrap(BudgetState())
    elif action == "load":
        state = ledger.load()
    elif action == "middleware":
        middleware = BudgetMiddleware(configured, ledger=ledger)
        middleware.pre_check("node")
        state = middleware.budget_state
    elif action == "middleware_spend":
        middleware = BudgetMiddleware(configured, ledger=ledger)
        middleware.record_spend_safe("run", Decimal("1"), provider="provider")
        state = middleware.budget_state
    elif action == "invalid":
        probes = {
            "load": ledger.load,
            "snapshot": ledger.snapshot,
            "record_spend": lambda: ledger.record_spend("run", Decimal("1")),
            "reserve": lambda: ledger.reserve("run", Decimal("1")),
            "release": lambda: ledger.release("run", Decimal("1")),
            "commit": lambda: ledger.commit_reservation("run", Decimal("1")),
            "bootstrap": lambda: ledger.load_or_bootstrap(configured),
            "middleware": lambda: BudgetMiddleware(configured, ledger=ledger).pre_check("node"),
            "reopen": lambda: FileBudgetLedger(path).load(),
        }
        results = {}
        for name, probe in probes.items():
            try:
                probe()
            except (ValueError, FileNotFoundError) as exc:
                results[name] = {"refused": True, "exception": type(exc).__name__}
            else:
                results[name] = {"refused": False}
            results[name]["bytes_unchanged"] = signature() == before
        baseline_path = path.with_suffix(".baseline")
        if baseline_path.exists():
            malformed = path.read_bytes()
            path.write_bytes(baseline_path.read_bytes())
            middleware = BudgetMiddleware(configured, ledger=ledger)
            path.write_bytes(malformed)
            live = {
                "middleware_read": lambda: middleware.budget_state,
                "middleware_pre_check": lambda: middleware.pre_check("node"),
                "middleware_thresholds": middleware.check_thresholds,
                "middleware_spend": lambda: middleware.record_spend_safe("run", Decimal("1")),
                "middleware_reserve": lambda: middleware.reserve_safe("run", Decimal("1")),
                "middleware_release": lambda: middleware.release_safe("run", Decimal("1")),
                "middleware_commit": lambda: middleware.commit_safe("run", Decimal("1")),
            }
            for name, probe in live.items():
                try:
                    probe()
                except (ValueError, FileNotFoundError) as exc:
                    results[name] = {"refused": True, "exception": type(exc).__name__}
                else:
                    results[name] = {"refused": False}
                results[name]["bytes_unchanged"] = signature() == before
        print(json.dumps({"probes": results, "before": before, "after": signature()}))
        sys.exit(0)
    else:
        raise AssertionError(action)
except (ValueError, OSError, BudgetExhaustedError) as exc:
    print(json.dumps({"refused": True, "exception": type(exc).__name__,
                      "before": before, "after": signature()}))
else:
    print(json.dumps({"refused": False, "state": state.model_dump(mode="json"),
                      "before": before, "after": signature()}))
"""


def _child(path: Path, action: str, *args: str, allow_kill: bool = False) -> dict[str, Any]:
    env = dict(os.environ)
    source_root = Path(__file__).resolve().parents[5] / "src"
    env["PYTHONPATH"] = str(source_root)
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, str(path), action, str(source_root), *args],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if allow_kill and result.returncode == -9:
        return {"killed": True, "exit_code": result.returncode}
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def _complete_snapshot(path: Path) -> dict[str, Any]:
    ledger = FileBudgetLedger(path)
    ledger.load_or_bootstrap(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("10"))},
            spent={"run": Decimal("2")},
            provider_spent={"provider": Decimal("2")},
            reserved={"run": Decimal("1")},
        )
    )
    ledger.commit_reservation("run", Decimal("1"), provider="provider")
    return json.loads(path.read_text())


def _required_paths(
    value: Any, schema: dict[str, Any], definitions: dict[str, Any], path: tuple[Any, ...] = ()
) -> list[tuple[Any, ...]]:
    """Walk the complete real writer record against its serialization schema."""
    if "$ref" in schema:
        schema = definitions[schema["$ref"].rsplit("/", 1)[1]]
    alternatives = schema.get("anyOf", [])
    if alternatives:
        schema = next((s for s in alternatives if s.get("type") != "null"), schema)
        if "$ref" in schema:
            schema = definitions[schema["$ref"].rsplit("/", 1)[1]]
    result: list[tuple[Any, ...]] = []
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key, item in value.items():
            item_schema = properties.get(key, schema.get("additionalProperties", {}))
            if not isinstance(item_schema, dict):
                continue
            nullable = any(s.get("type") == "null" for s in item_schema.get("anyOf", []))
            if key in properties and not nullable:
                result.append((*path, key))
            result.extend(_required_paths(item, item_schema, definitions, (*path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.extend(
                _required_paths(item, schema.get("items", {}), definitions, (*path, index))
            )
    return result


def test_cold_record_spend_requires_bootstrap_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    result = _child(path, "spend")
    assert result["refused"] is True, result
    assert not path.exists(), "cold mutation must not publish an unlimited snapshot"
    control = _child(path, "middleware")
    assert control["exception"] == "BudgetExhaustedError", control
    assert _child(path, "middleware")["exception"] == "BudgetExhaustedError"


def test_explicit_unlimited_bootstrap_remains_valid_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    assert _child(path, "unlimited")["refused"] is False
    assert _child(path, "spend")["state"]["spent"]["run"] == "1"
    reopened = _child(path, "load")
    assert reopened["state"]["limits"] == {}
    assert reopened["state"]["spent"]["run"] == "1"


@pytest.mark.parametrize("payload", ["", '{"schema_version":', "{}", '{"state": {}}'])
def test_malformed_existing_ledger_is_not_rebootstrapped(tmp_path: Path, payload: str) -> None:
    path = tmp_path / "budget.json"
    _complete_snapshot(path)
    path.with_suffix(".baseline").write_bytes(path.read_bytes())
    path.write_text(payload)
    result = _child(path, "invalid")
    assert all(p["refused"] and p["bytes_unchanged"] for p in result["probes"].values()), result
    assert path.read_text() == payload


def test_parseable_sparse_existing_snapshot_is_not_unlimited_or_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    complete = _complete_snapshot(path)
    path.with_suffix(".baseline").write_bytes(path.read_bytes())
    schema = BudgetLedgerSnapshot.model_json_schema(mode="serialization")
    failures = []
    paths = _required_paths(complete, schema, schema.get("$defs", {}))
    assert ("state", "limits") in paths and ("state", "spent") in paths
    for missing in paths:
        sparse = copy.deepcopy(complete)
        owner = sparse
        for component in missing[:-1]:
            owner = owner[component]
        del owner[missing[-1]]
        path.write_text(json.dumps(sparse))
        result = _child(path, "invalid")
        if not all(p["refused"] and p["bytes_unchanged"] for p in result["probes"].values()):
            failures.append({"missing": missing, "result": result})
    assert failures == [], failures


def test_legal_nullable_omissions_remain_readable_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    complete = _complete_snapshot(path)
    del complete["ledger_id"]
    del complete["last_writer"]
    for mutation in complete["recent_mutations"]:
        for name in ["key", "amount", "applied_amount", "provider", "reserved"]:
            mutation.pop(name, None)
    path.write_text(json.dumps(complete))
    observed = _child(path, "load")
    assert observed["refused"] is False
    assert observed["state"]["limits"]["run"]["max_usd"] == "10"
    assert observed["state"]["spent"]["run"] == "3"


@pytest.mark.parametrize(
    ("field_path", "value"),
    [
        (("revision",), "1"),
        (("revision",), True),
        (("revision",), -1),
        (("updated_at",), "not-a-time"),
        (("state", "spent"), []),
        (("state", "spent", "run"), "NaN"),
        (("state", "spent", "run"), "Infinity"),
        (("state", "spent", "run"), "-1"),
        (("state", "reserved", "run"), "-1"),
        (("state", "provider_spent", "provider"), "-1"),
        (("state", "limits", "run", "max_usd"), "-1"),
        (("last_writer", "pid"), "1"),
        (("recent_mutations",), {}),
    ],
)
def test_invalid_typed_accounting_never_rewrites_existing_bytes(
    tmp_path: Path, field_path: tuple[str, ...], value: Any
) -> None:
    path = tmp_path / "budget.json"
    complete = _complete_snapshot(path)
    path.with_suffix(".baseline").write_bytes(path.read_bytes())
    owner = complete
    for component in field_path[:-1]:
        owner = owner[component]
    owner[field_path[-1]] = value
    path.write_text(json.dumps(complete))
    result = _child(path, "invalid")
    assert all(p["refused"] and p["bytes_unchanged"] for p in result["probes"].values()), result


@pytest.mark.parametrize("cold", [False, True])
@pytest.mark.parametrize(
    "stage",
    [
        "file_fsync",
        "replace_before",
        "directory_fsync",
        "kill_before_replace",
        "kill_after_replace",
    ],
)
def test_process_publication_fault_reopens_complete_or_requires_recovery(
    tmp_path: Path, cold: bool, stage: str
) -> None:
    path = tmp_path / "budget.json"
    if not cold:
        _complete_snapshot(path)
    result = _child(
        path,
        "fault_bootstrap" if cold else "fault_spend",
        stage,
        allow_kill=stage.startswith("kill_"),
    )
    if stage.startswith("kill_"):
        assert result["killed"] is True
    else:
        assert result["exception"] == "OSError", result
    reopened = _child(path, "load")
    if cold and stage in {"file_fsync", "replace_before", "kill_before_replace"}:
        assert not path.exists(), "failed first publication must not leave an empty target"
        assert reopened["exception"] == "FileNotFoundError", reopened
        assert _child(path, "middleware")["exception"] == "BudgetExhaustedError"
    else:
        assert reopened["refused"] is False, reopened
        assert reopened["state"]["limits"]["run"]["max_usd"] == "10"
        if cold:
            assert reopened["state"]["spent"]["run"] == "10"
            assert _child(path, "middleware")["exception"] == "BudgetExhaustedError"
        else:
            expected = (
                "3" if stage in {"file_fsync", "replace_before", "kill_before_replace"} else "4"
            )
            assert reopened["state"]["spent"]["run"] == expected


def test_concurrent_real_middleware_processes_preserve_spend_and_exhausted_cap(
    tmp_path: Path,
) -> None:
    path = tmp_path / "budget.json"
    FileBudgetLedger(path).load_or_bootstrap(
        BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("100"))})
    )
    source_root = Path(__file__).resolve().parents[5] / "src"
    children = []
    try:
        for action in ["concurrent_writer"] * 4 + ["concurrent_reader"]:
            child = subprocess.Popen(
                [sys.executable, "-c", _CHILD, str(path), action, str(source_root)],
                env={**os.environ, "PYTHONPATH": str(source_root)},
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            children.append(child)
        for child in children:
            assert child.stdout is not None
            assert child.stdout.readline().strip() == "READY"
        for child in children:
            assert child.stdin is not None
            child.stdin.write("GO\n")
            child.stdin.flush()
        for child in children:
            stdout, stderr = child.communicate(timeout=30)
            assert child.returncode == 0, stdout + stderr
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=10)
    reopened = _child(path, "load")
    assert reopened["state"]["spent"]["run"] == "100"
    assert reopened["state"]["provider_spent"]["provider"] == "100"
    assert _child(path, "middleware")["exception"] == "BudgetExhaustedError"
