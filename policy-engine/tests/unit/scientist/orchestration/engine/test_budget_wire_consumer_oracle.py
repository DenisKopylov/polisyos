"""Independent emitted-wire and fresh-process budget consumer witnesses."""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger

# This is an explicit consumer contract, independent of the decoder's schema
# traversal. Nullable fields are deliberately excluded.
_MANDATORY_PATHS = [
    ("schema_version",),
    ("canonical_contract",),
    ("coordination_mode",),
    ("revision",),
    ("updated_at",),
    ("recent_mutations",),
    ("state",),
    ("state", "limits"),
    ("state", "spent"),
    ("state", "provider_spent"),
    ("state", "reserved"),
    ("state", "limits", "run", "key"),
    ("state", "limits", "run", "max_usd"),
    ("last_writer", "host_id"),
    ("last_writer", "writer_id"),
    ("last_writer", "pid"),
    ("recent_mutations", 0, "revision"),
    ("recent_mutations", 0, "operation"),
    ("recent_mutations", 0, "committed_at"),
    ("recent_mutations", 0, "writer"),
    ("recent_mutations", 0, "writer", "host_id"),
    ("recent_mutations", 0, "writer", "writer_id"),
    ("recent_mutations", 0, "writer", "pid"),
]

_CHILD = r"""
import hashlib, json, os, sys
from decimal import Decimal
from pathlib import Path
from polisyos.scientist.orchestration.engine import budget_ledger as module
from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError, BudgetLimit, BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
assert Path(module.__file__).resolve().is_relative_to(Path(sys.argv[2]))
if os.environ.get("E02_B_PROPERTY_REMOVAL") == "budget-wire":
    module._require_wire_fields = lambda *args, **kwargs: None
path = Path(sys.argv[1])
before = hashlib.sha256(path.read_bytes()).hexdigest()
ledger = module.FileBudgetLedger(path)
configured = BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("3"))},
                         spent={"run": Decimal("3")})
out = {}
for name in ("load", "record_spend", "middleware"):
    try:
        if name == "load":
            ledger.load()
        elif name == "record_spend":
            ledger.record_spend("run", Decimal("2"))
        else:
            middleware = BudgetMiddleware(configured, ledger=ledger)
            middleware.pre_check("actual-node")
    except (ValueError, FileNotFoundError) as error:
        out[name] = {"status": "refused", "error": type(error).__name__}
    except BudgetExhaustedError:
        out[name] = {"status": "exhausted"}
    else:
        out[name] = {"status": "accepted"}
    out[name]["unchanged"] = hashlib.sha256(path.read_bytes()).hexdigest() == before
print(json.dumps(out))
"""


def _real_snapshot(path: Path) -> dict:
    FileBudgetLedger(path).load_or_bootstrap(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal("3"))},
            spent={"run": Decimal("3")},
            provider_spent={"provider": Decimal("3")},
            reserved={"run": Decimal("1")},
        )
    )
    return json.loads(path.read_bytes())


def _consumer(path: Path) -> dict:
    source_root = Path(__file__).resolve().parents[5] / "src"
    env = {**os.environ, "PYTHONPATH": str(source_root)}
    result = subprocess.run(
        [sys.executable, "-c", _CHILD, str(path), str(source_root)],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("missing", _MANDATORY_PATHS, ids=lambda p: ".".join(map(str, p)))
def test_each_independently_named_wire_field_is_required_by_real_consumers(
    tmp_path: Path,
    missing: tuple,
) -> None:
    path = tmp_path / "budget.json"
    snapshot = copy.deepcopy(_real_snapshot(path))
    owner = snapshot
    for component in missing[:-1]:
        owner = owner[component]
    del owner[missing[-1]]
    damaged = json.dumps(snapshot).encode()
    path.write_bytes(damaged)
    observed = _consumer(path)
    assert all(v["status"] == "refused" and v["unchanged"] for v in observed.values()), observed
    assert path.read_bytes() == damaged


def test_nullable_wire_omissions_preserve_exhausted_budget_across_processes(tmp_path: Path) -> None:
    path = tmp_path / "budget.json"
    snapshot = _real_snapshot(path)
    for name in ("ledger_id", "last_writer"):
        snapshot.pop(name)
    snapshot["state"]["limits"]["run"].pop("soft_limit_usd", None)
    for mutation in snapshot["recent_mutations"]:
        for name in ("key", "amount", "applied_amount", "provider", "reserved"):
            mutation.pop(name, None)
    path.write_text(json.dumps(snapshot))
    observed = _consumer(path)
    assert observed["load"] == {"status": "accepted", "unchanged": True}
    assert observed["record_spend"] == {"status": "accepted", "unchanged": False}
    assert observed["middleware"]["status"] == "exhausted"
    state = FileBudgetLedger(path).load()
    assert state.spent["run"] == Decimal("5")
    assert state.remaining("run") == Decimal("-3")
