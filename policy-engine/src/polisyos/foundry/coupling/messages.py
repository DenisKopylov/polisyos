"""Typed message envelopes for DES/ABM coupling."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SOURCE_ABM = "abm"
SOURCE_DES = "des"
TARGET_ABM = "abm"
TARGET_DES = "des"

KIND_ARRIVAL = "arrival"
KIND_CLAIM_ARRIVAL = "claim_arrival"
KIND_QUEUE_ADMIT = "queue_admit"
KIND_QUEUE_REJECT = "queue_reject"
KIND_SERVICE_START = "service_start"
KIND_SERVICE_COMPLETE = "service_complete"
KIND_ELIGIBILITY_UPDATE = "eligibility_update"
KIND_APPEAL_UPDATE = "appeal_update"
KIND_AGENT_DECISION = "agent_decision"
KIND_POLICY_CHANGE = "policy_change"
KIND_OBSERVATION_EMIT = "observation_emit"

ARRIVAL_KINDS = frozenset({KIND_ARRIVAL, KIND_CLAIM_ARRIVAL})


@dataclass(frozen=True, slots=True)
class CouplingMessage:
    """Inter-kernel envelope used instead of direct cross-kernel state mutation."""

    time: float
    source: str
    target: str
    kind: str
    entity_id: str | int | None = None
    priority: int = 0
    causal_parent: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    rng_stream: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "time", float(self.time))
        object.__setattr__(self, "source", str(self.source))
        object.__setattr__(self, "target", str(self.target))
        object.__setattr__(self, "kind", str(self.kind))
        object.__setattr__(self, "priority", int(self.priority))
        object.__setattr__(self, "payload", dict(self.payload))

    def with_time(self, time: float) -> CouplingMessage:
        """Return the same envelope at a new timestamp."""
        return CouplingMessage(
            time=time,
            source=self.source,
            target=self.target,
            kind=self.kind,
            entity_id=self.entity_id,
            priority=self.priority,
            causal_parent=self.causal_parent,
            payload=self.payload,
            rng_stream=self.rng_stream,
        )

    def with_route(
        self, *, source: str | None = None, target: str | None = None
    ) -> CouplingMessage:
        """Return the same envelope with an adjusted source and/or target."""
        return CouplingMessage(
            time=self.time,
            source=self.source if source is None else source,
            target=self.target if target is None else target,
            kind=self.kind,
            entity_id=self.entity_id,
            priority=self.priority,
            causal_parent=self.causal_parent,
            payload=self.payload,
            rng_stream=self.rng_stream,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to plain JSON-like data for method outputs and diagnostics."""
        return {
            "time": self.time,
            "source": self.source,
            "target": self.target,
            "kind": self.kind,
            "entity_id": self.entity_id,
            "priority": self.priority,
            "causal_parent": self.causal_parent,
            "payload": dict(self.payload),
            "rng_stream": self.rng_stream,
        }


def message_sort_key(message: CouplingMessage) -> tuple[float, int, str, str]:
    """Stable deterministic order for simultaneous coupling messages."""
    entity = "" if message.entity_id is None else str(message.entity_id)
    return (float(message.time), int(message.priority), str(message.kind), entity)


def sort_messages(
    messages: list[CouplingMessage] | tuple[CouplingMessage, ...],
) -> tuple[CouplingMessage, ...]:
    """Return messages in deterministic causality-preserving order."""
    return tuple(sorted(messages, key=message_sort_key))


def entity_index(entity_id: str | int | None) -> int | None:
    """Best-effort mapping from an envelope entity id to an agent slot index."""
    if entity_id is None:
        return None
    if isinstance(entity_id, int):
        return entity_id if entity_id >= 0 else None

    text = str(entity_id).strip()
    if not text:
        return None
    if text.lstrip("-").isdigit():
        value = int(text)
        return value if value >= 0 else None

    suffix = []
    for char in reversed(text):
        if not char.isdigit():
            break
        suffix.append(char)
    if not suffix:
        return None
    return int("".join(reversed(suffix)))


__all__ = [
    "ARRIVAL_KINDS",
    "KIND_AGENT_DECISION",
    "KIND_APPEAL_UPDATE",
    "KIND_ARRIVAL",
    "KIND_CLAIM_ARRIVAL",
    "KIND_ELIGIBILITY_UPDATE",
    "KIND_OBSERVATION_EMIT",
    "KIND_POLICY_CHANGE",
    "KIND_QUEUE_ADMIT",
    "KIND_QUEUE_REJECT",
    "KIND_SERVICE_COMPLETE",
    "KIND_SERVICE_START",
    "SOURCE_ABM",
    "SOURCE_DES",
    "TARGET_ABM",
    "TARGET_DES",
    "CouplingMessage",
    "entity_index",
    "message_sort_key",
    "sort_messages",
]
