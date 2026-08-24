"""Runtime-container wiring tests for the epoch custody provider."""

from __future__ import annotations


def test_container_contract_exposes_provider_not_internal_service() -> None:
    """Injecting the internal service instead of the provider is the break caught."""
    from polisyos.runtime.http.container import RuntimeServiceContainer

    annotations = RuntimeServiceContainer.__annotations__
    assert "epoch_anchor_custody_provider" in annotations
    assert "epoch_anchor_custody_service" not in annotations
