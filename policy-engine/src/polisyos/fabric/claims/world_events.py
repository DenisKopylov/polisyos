from __future__ import annotations

from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldEvent,
    WorldObjectRef,
)

__all__ = ["build_claims_world_event", "persist_claims_world_event"]


def build_claims_world_event(
    *,
    event_kind: EventKind,
    activity_type: ProvActivityType,
    activity_id: str,
    activity_label: str,
    agent_id: str,
    inputs: list[WorldObjectRef],
    outputs: list[WorldObjectRef],
    evidence_ref: str | None = None,
    props: dict[str, Any] | None = None,
) -> WorldEvent:
    """Build deterministic Fabric Claims world event."""
    return build_deterministic_world_event(
        event_kind=event_kind,
        agent_id=agent_id,
        agent_type=ProvAgentType.EXTRACTOR,
        agent_label="Fabric Claims",
        activity_id=activity_id,
        activity_type=activity_type,
        activity_label=activity_label,
        inputs=inputs,
        outputs=outputs,
        evidence_ref=evidence_ref,
        props=props or {},
    )


def persist_claims_world_event(
    *,
    cas: FileSystemCAS,
    event: WorldEvent,
    facts: list[Any],
) -> str:
    """Persist world event and append corresponding world facts."""
    return persist_world_event_with_facts(
        cas=cas,
        event=event,
        facts=facts,
    )
