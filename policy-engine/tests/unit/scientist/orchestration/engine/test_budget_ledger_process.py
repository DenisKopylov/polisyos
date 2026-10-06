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
import hashlib, json, sys
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
    if action == "spend":
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
        print(json.dumps({"probes": results, "before": before, "after": signature()}))
        sys.exit(0)
    else:
        raise AssertionError(action)
except (ValueError, FileNotFoundError, BudgetExhaustedError) as exc:
    print(json.dumps({"refused": True, "exception": type(exc).__name__,
                      "before": before, "after": signature()}))
else:
    print(json.dumps({"refused": False, "state": state.model_dump(mode="json"),
                      "before": before, "after": signature()}))
"""


def _child(path: Path, action: str) -> dict[str, Any]:
    env = dict(os.environ)
    source_root = Path(__file__).resolve().parents[5] / "src"
    env["PYTHONPATH"] = str(source_root)
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, str(path), action, str(source_root)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
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
    path.write_text(payload)
    result = _child(path, "invalid")
    assert all(p["refused"] and p["bytes_unchanged"] for p in result["probes"].values()), result
    assert path.read_text() == payload


def test_parseable_sparse_existing_snapshot_is_not_unlimited_or_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    complete = _complete_snapshot(path)
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
