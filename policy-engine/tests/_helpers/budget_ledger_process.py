"""Importable spawned worker for the actual budget-ledger concurrency test."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger


def reserve_in_process(path: str, event: str, request: str, barrier: Any, result: Any) -> None:
    """Compete for one reservation using the real shared file ledger."""
    owner = FileBudgetLedger(Path(path))
    barrier.wait()
    try:
        owner.reserve_compute(event, request, "run", Decimal("0.75"))
    except ValueError as exc:
        result.put(("refused", str(exc)))
    else:
        result.put(("reserved", event))
