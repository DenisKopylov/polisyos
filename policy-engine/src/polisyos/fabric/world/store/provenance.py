"""Stable provenance markers for facts emitted by the world-store boundary."""
from __future__ import annotations

from polisyos.ir.fact_log import FactProvenance


def stable_world_provenance_v1(*, license: str = "internal") -> FactProvenance:
    """Return the default provenance envelope for deterministic world facts."""
    return FactProvenance(
        source_id="fabric.world",
        license=license,
        raw_hash="world_abi_v1",
        ingestion_run_id=None,
        script_hash=None,
    )


def event_world_provenance_v1(
    event_id: str, *, license: str = "internal"
) -> FactProvenance:
    """Return a provenance envelope tied to one emitted world event."""
    return FactProvenance(
        source_id="fabric.world.event",
        license=license,
        raw_hash="world_event_v1",
        ingestion_run_id=event_id,
        script_hash=None,
    )


__all__ = [
    "event_world_provenance_v1",
    "stable_world_provenance_v1",
]
