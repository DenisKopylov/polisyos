"""Ignored B37 discriminator; run only in G's assigned candidate checkout/compute slot.

From policy-engine/ with the candidate's own interpreter:
  PYTHONPATH=src .venv/bin/python _build/e02-g-continuation-20261006/proposedprobe.py
This uses temporary files only and never opens production data.
"""
from __future__ import annotations

import copy
import json
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Callable

from polisyos.scientist.orchestration.engine.budget import (
    BudgetExhaustedError,
    BudgetLimit,
    BudgetState,
)
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
import polisyos.scientist.orchestration.engine.budget_ledger as ledger_module


def _must_refuse_unchanged(name: str, path: Path, action: Callable[[], object]) -> None:
    before = path.read_bytes() if path.exists() else None
    try:
        action()
    except (ValueError, FileNotFoundError):
        pass
    else:
        raise AssertionError(f"{name} accepted an inadmissible ledger")
    after = path.read_bytes() if path.exists() else None
    if after != before:
        raise AssertionError(f"{name} rewrote the rejected ledger")


def _config(*, limit: str = "10", spent: str = "2") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(limit))},
        spent={"run": Decimal(spent)},
    )


def _probe_missing_and_configured_consumers(root: Path) -> None:
    absent_ops = {
        "load": lambda ledger: ledger.load(),
        "snapshot": lambda ledger: ledger.snapshot(),
        "record_spend": lambda ledger: ledger.record_spend("run", Decimal("1")),
        "reserve": lambda ledger: ledger.reserve("run", Decimal("1")),
        "release": lambda ledger: ledger.release("run", Decimal("1")),
        "commit_reservation": lambda ledger: ledger.commit_reservation("run", Decimal("1")),
    }
    for name, operation in absent_ops.items():
        path = root / f"absent-{name}.json"
        _must_refuse_unchanged(name, path, lambda p=path, op=operation: op(FileBudgetLedger(p)))
        if path.exists():
            raise AssertionError(f"cold {name} created a JSON ledger")

    # The middleware constructor supplies an explicit initial state. Its cold
    # record_spend_safe path must retain that configuration through reopen.
    bounded_path = root / "middleware-bounded.json"
    bounded = BudgetMiddleware(_config(), ledger=FileBudgetLedger(bounded_path))
    bounded.pre_check("node")
    bounded.record_spend_safe("run", Decimal("1"), provider="probe")
    reopened = FileBudgetLedger(bounded_path).load()
    if reopened.limits["run"].max_usd != Decimal("10") or reopened.spent["run"] != Decimal("3"):
        raise AssertionError(f"cold bounded middleware lost its configured state: {reopened}")

    # Explicit unlimited bootstrap is distinct from an implicit cold mutation.
    unlimited_path = root / "middleware-unlimited.json"
    unlimited = BudgetMiddleware(BudgetState(), ledger=FileBudgetLedger(unlimited_path))
    unlimited.record_spend_safe("run", Decimal("1"))
    reopened_unlimited = FileBudgetLedger(unlimited_path).load()
    if reopened_unlimited.limits or reopened_unlimited.spent.get("run") != Decimal("1"):
        raise AssertionError(f"explicit unlimited middleware state changed: {reopened_unlimited}")

    exhausted_path = root / "middleware-exhausted.json"
    exhausted = BudgetMiddleware(_config(spent="10"), ledger=FileBudgetLedger(exhausted_path))
    try:
        exhausted.pre_check("node")
    except BudgetExhaustedError:
        pass
    else:
        raise AssertionError("cold configured exhausted middleware admitted pre_check")
    reopened_exhausted = FileBudgetLedger(exhausted_path).load()
    if reopened_exhausted.spent.get("run") != Decimal("10"):
        raise AssertionError(f"cold middleware lost exhausted spend: {reopened_exhausted}")


def _probe_existing_payloads(root: Path) -> None:
    seed_path = root / "seed.json"
    seed = FileBudgetLedger(seed_path)
    seed.load_or_bootstrap(_config())
    seed.record_spend("run", Decimal("1"), provider="probe")
    complete = json.loads(seed_path.read_text(encoding="utf-8"))

    variants: dict[str, object] = {
        "empty_object": {},
        "empty_nested_state": {"state": {}},
        "malformed": "{\"state\":",
    }
    missing_defaulted_state_field = copy.deepcopy(complete)
    del missing_defaulted_state_field["state"]["spent"]
    variants["missing_defaulted_state_spent"] = missing_defaulted_state_field

    wrong_typed_present_field = copy.deepcopy(complete)
    wrong_typed_present_field["revision"] = str(complete["revision"])
    variants["present_but_wrong_type_revision"] = wrong_typed_present_field

    nonfinite_present_amount = copy.deepcopy(complete)
    nonfinite_present_amount["state"]["spent"]["run"] = "NaN"
    variants["present_but_nonfinite_spend"] = nonfinite_present_amount

    config = _config()
    for variant, value in variants.items():
        raw = value if isinstance(value, str) else json.dumps(value)
        path = root / f"{variant}.json"
        path.write_text(raw, encoding="utf-8")

        direct_ops = {
            "load": lambda p=path: FileBudgetLedger(p).load(),
            "snapshot": lambda p=path: FileBudgetLedger(p).snapshot(),
            "bootstrap": lambda p=path: FileBudgetLedger(p).load_or_bootstrap(config),
            "record_spend": lambda p=path: FileBudgetLedger(p).record_spend("run", Decimal("1")),
            "reserve": lambda p=path: FileBudgetLedger(p).reserve("run", Decimal("1")),
            "release": lambda p=path: FileBudgetLedger(p).release("run", Decimal("1")),
            "commit": lambda p=path: FileBudgetLedger(p).commit_reservation("run", Decimal("1")),
        }
        for name, action in direct_ops.items():
            path.write_text(raw, encoding="utf-8")
            _must_refuse_unchanged(f"{variant}/{name}", path, action)

        # Exercise the actual configured middleware's public read and mutation
        # methods after admission, so the test is not constructor-only.
        path.write_text(seed_path.read_text(encoding="utf-8"), encoding="utf-8")
        ledger = FileBudgetLedger(path)
        middleware = BudgetMiddleware(config, ledger=ledger)
        middleware_ops = {
            "pre_check": lambda: middleware.pre_check("node"),
            "check_thresholds": lambda: middleware.check_thresholds(),
            "budget_state": lambda: middleware.budget_state,
            "record_spend_safe": lambda: middleware.record_spend_safe("run", Decimal("1")),
            "reserve_safe": lambda: middleware.reserve_safe("run", Decimal("1")),
            "release_safe": lambda: middleware.release_safe("run", Decimal("1")),
            "commit_safe": lambda: middleware.commit_safe("run", Decimal("1")),
        }
        for name, action in middleware_ops.items():
            path.write_text(raw, encoding="utf-8")
            _must_refuse_unchanged(f"{variant}/middleware.{name}", path, action)

    # This complete, type-valid but noncanonical contract string is deliberately
    # diagnostic only. B37 requires completeness/admission, not cryptographic
    # authenticity of otherwise valid bytes; do not turn this into a pass/fail
    # claim without a ratified content-authenticity contract.
    unknown_version = copy.deepcopy(complete)
    unknown_version["schema_version"] = "99.0"
    version_path = root / "unsupported-version.json"
    version_path.write_text(json.dumps(unknown_version), encoding="utf-8")
    version_ledger = FileBudgetLedger(version_path)
    original_bytes = version_path.read_bytes()
    try:
        version_ledger.load()
        observed_before = version_ledger.snapshot().schema_version
        version_ledger.record_spend("run", Decimal("1"))
        observed_after = json.loads(version_path.read_text())["schema_version"]
        print(json.dumps({"probe": "unsupported_schema_version", "load_accepted": True, "before": observed_before, "after_mutation": observed_after, "bytes_rewritten": version_path.read_bytes() != original_bytes}))
    except (ValueError, FileNotFoundError) as error:
        print(json.dumps({"probe": "unsupported_schema_version", "load_accepted": False, "error_type": type(error).__name__, "bytes_rewritten": version_path.read_bytes() != original_bytes}))

    forged = copy.deepcopy(complete)
    forged["canonical_contract"] = "nonempty-unrecognized-contract"
    forged_path = root / "valid-shaped-foreign-contract.json"
    forged_path.write_text(json.dumps(forged), encoding="utf-8")
    try:
        observed = FileBudgetLedger(forged_path).snapshot().canonical_contract
    except (ValueError, FileNotFoundError):
        print("valid-shaped foreign contract: refused")
    else:
        print(f"valid-shaped foreign contract: accepted as {observed!r} (not_established boundary)")


def main() -> None:
    print(f"runtime source: {Path(ledger_module.__file__).resolve()}")
    scratch = Path(__file__).resolve().parent / "results" / "tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="e02-b37-oracle-", dir=scratch))
    print(f"retained fixtures: {root}")
    _probe_missing_and_configured_consumers(root)
    _probe_existing_payloads(root)
    print("B37 scoped discriminator passed; valid-content identity remains a separate not_established boundary")


if __name__ == "__main__":
    main()
