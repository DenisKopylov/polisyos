"""Public world events module API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.world.store.emit import emit_world_event_facts
from polisyos.fabric.world.store.persist import persist_world_event
from polisyos.fabric.world.store.provenance import event_world_provenance_v1
from polisyos.ir.world.event import (
    EventKind,
    ProvActivity,
    ProvActivityType,
    ProvAgent,
    ProvAgentType,
    WorldEvent,
    WorldObjectRef,
)
from polisyos.ir.world.ids import world_event_id_from_payload

__all__ = ["build_deterministic_world_event", "persist_world_event_with_facts"]


def build_deterministic_world_event(
    *,
    event_kind: EventKind,
    agent_id: str,
    agent_type: ProvAgentType,
    agent_label: str,
    activity_id: str,
    activity_type: ProvActivityType,
    activity_label: str,
    inputs: list[WorldObjectRef],
    outputs: list[WorldObjectRef],
    activity_parameters: dict[str, Any] | None = None,
    evidence_ref: str | None = None,
    props: dict[str, Any] | None = None,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
) -> WorldEvent:
    """Build deterministic world event."""
    started = started_at or datetime.now(timezone.utc)
    ended = ended_at or started
    agent = ProvAgent(
        agent_id=agent_id,
        agent_type=agent_type,
        label=agent_label,
    )
    activity = ProvActivity(
        activity_id=activity_id,
        activity_type=activity_type,
        label=activity_label,
        started_at=started,
        ended_at=ended,
        parameters=activity_parameters or {},
    )
    event_payload = {
        "event_kind": event_kind,
        "agent": agent,
        "activity": activity,
        "inputs": inputs,
        "outputs": outputs,
        "evidence_ref": evidence_ref,
        "provenance_ref": None,
    }
    event_id = world_event_id_from_payload(event_payload=event_payload)
    return WorldEvent(
        event_id=event_id,
        event_kind=event_kind,
        agent=agent,
        activity=activity,
        inputs=inputs,
        outputs=outputs,
        evidence_ref=evidence_ref,
        provenance_ref=None,
        props=props or {},
    )


def persist_world_event_with_facts(
    *,
    cas: FileSystemCAS,
    event: WorldEvent,
    facts: list[Any],
) -> str:
    """Persist world event with facts helper."""
    event_ref = persist_world_event(cas, event)
    event_artifact_id = str(event_ref.artifact_id)
    facts.extend(
        emit_world_event_facts(
            event,
            event_artifact_id=event_artifact_id,
            provenance=event_world_provenance_v1(event.event_id),
        )
    )
    return event_artifact_id
