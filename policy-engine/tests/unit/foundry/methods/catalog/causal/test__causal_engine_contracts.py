from __future__ import annotations

from polisyos.foundry.methods.catalog.causal import causal_engine as runtime
from polisyos.foundry.methods.catalog.causal._causal_engine_contracts import (
    DataReadinessBlockedError,
)


def test_causal_engine_contracts_are_reexported_from_runtime_module() -> None:
    assert runtime.DataReadinessBlockedError is DataReadinessBlockedError
    assert issubclass(DataReadinessBlockedError, RuntimeError)
