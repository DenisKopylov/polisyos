"""Public mechanism registry boot module API."""

from __future__ import annotations

from polisyos.foundry.methods.catalog.mechanism.runtime import (
    AdaptiveAgentMechanismMethod,
    IncomeTaxMechanismMethod,
    LaborMarketMechanismMethod,
    QueueMechanismMethod,
    TaxSubsidyMechanismMethod,
)


def register_mechanism_methods() -> tuple[type, ...]:
    """Register mechanism methods."""
    return (
        AdaptiveAgentMechanismMethod,
        TaxSubsidyMechanismMethod,
        IncomeTaxMechanismMethod,
        LaborMarketMechanismMethod,
        QueueMechanismMethod,
    )


__all__ = ["register_mechanism_methods"]
