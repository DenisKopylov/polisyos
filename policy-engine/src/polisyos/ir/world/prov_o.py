"""PROV-O aligned bridge contracts for world provenance events."""
from __future__ import annotations

from datetime import UTC
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.world.event import ProvActivity, ProvAgent, WorldEvent, WorldObjectRef


class ProvORecordType(str, Enum):
    """Subset of PROV-O classes used by the IR bridge."""

    ENTITY = "prov:Entity"
    ACTIVITY = "prov:Activity"
    AGENT = "prov:Agent"


class ProvORelationType(str, Enum):
    """Subset of PROV-O properties emitted from world events."""

    USED = "prov:used"
    WAS_GENERATED_BY = "prov:wasGeneratedBy"
    WAS_ASSOCIATED_WITH = "prov:wasAssociatedWith"
    WAS_DERIVED_FROM = "prov:wasDerivedFrom"
    WAS_ATTRIBUTED_TO = "prov:wasAttributedTo"


class ProvOAgent(BaseModel):
    """PROV-O view of one world agent."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iri: str
    type: ProvORecordType = ProvORecordType.AGENT
    label: str
    agent_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvOActivityRecord(BaseModel):
    """PROV-O view of one activity with deterministic duration metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iri: str
    type: ProvORecordType = ProvORecordType.ACTIVITY
    label: str
    activity_type: str
    started_at: str
    ended_at: str | None = None
    duration_seconds: float | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvOEntity(BaseModel):
    """PROV-O entity representing a world object or artifact boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iri: str
    type: ProvORecordType = ProvORecordType.ENTITY
    label: str
    world_id: str | None = None
    artifact_id: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvORelation(BaseModel):
    """Typed PROV-O edge emitted from an immutable world event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    relation: ProvORelationType
    subject: str
    object: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class ProvODocument(BaseModel):
    """JSON-LD-friendly PROV-O bundle derived from one world event."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    context: str = "https://www.w3.org/ns/prov#"
    event_id: str
    agents: list[ProvOAgent] = Field(default_factory=list)
    activities: list[ProvOActivityRecord] = Field(default_factory=list)
    entities: list[ProvOEntity] = Field(default_factory=list)
    relations: list[ProvORelation] = Field(default_factory=list)

    def to_jsonld(self) -> dict[str, Any]:
        """Export a simple JSON-LD compatible payload."""

        graph: list[dict[str, Any]] = []
        for agent in self.agents:
            graph.append(
                {
                    "@id": agent.iri,
                    "@type": agent.type.value,
                    "rdfs:label": agent.label,
                    "polisyos:agentType": agent.agent_type,
                    **agent.attributes,
                }
            )
        for activity in self.activities:
            graph.append(
                {
                    "@id": activity.iri,
                    "@type": activity.type.value,
                    "rdfs:label": activity.label,
                    "polisyos:activityType": activity.activity_type,
                    "prov:startedAtTime": activity.started_at,
                    "prov:endedAtTime": activity.ended_at,
                    "polisyos:durationSeconds": activity.duration_seconds,
                    **activity.attributes,
                }
            )
        for entity in self.entities:
            graph.append(
                {
                    "@id": entity.iri,
                    "@type": entity.type.value,
                    "rdfs:label": entity.label,
                    "polisyos:worldId": entity.world_id,
                    "polisyos:artifactId": entity.artifact_id,
                    **entity.attributes,
                }
            )
        for relation in self.relations:
            graph.append(
                {
                    "@id": f"{relation.subject}->{relation.relation.value}->{relation.object}",
                    "@type": relation.relation.value,
                    "prov:subject": relation.subject,
                    "prov:object": relation.object,
                    **relation.attributes,
                }
            )
        return {"@context": self.context, "@graph": graph}


def prov_o_iri(kind: str, identifier: str) -> str:
    """Build a stable local IRI for one PROV-O record."""

    return f"urn:polisyos:prov:{kind}:{identifier}"


def to_prov_o_agent(agent: ProvAgent) -> ProvOAgent:
    """Convert a world agent to its PROV-O bridge record."""

    attributes: dict[str, Any] = {}
    if agent.component_id is not None:
        attributes["polisyos:componentId"] = agent.component_id
    if agent.model_id is not None:
        attributes["polisyos:modelId"] = agent.model_id
    if agent.metadata:
        attributes["polisyos:metadata"] = dict(agent.metadata)
    return ProvOAgent(
        iri=prov_o_iri("agent", agent.agent_id),
        label=agent.label,
        agent_type=agent.agent_type.value,
        attributes=attributes,
    )


def to_prov_o_activity(activity: ProvActivity) -> ProvOActivityRecord:
    """Convert a world activity to PROV-O with deterministic duration semantics."""

    ended_at = (
        activity.ended_at.astimezone(UTC).isoformat()
        if activity.ended_at is not None
        else None
    )
    duration = None
    if activity.ended_at is not None:
        duration = (activity.ended_at - activity.started_at).total_seconds()
    return ProvOActivityRecord(
        iri=prov_o_iri("activity", activity.activity_id),
        label=activity.label,
        activity_type=activity.activity_type.value,
        started_at=activity.started_at.astimezone(UTC).isoformat(),
        ended_at=ended_at,
        duration_seconds=duration,
        attributes=(
            {"polisyos:parameters": dict(activity.parameters)}
            if activity.parameters
            else {}
        ),
    )


def to_prov_o_entity(ref: WorldObjectRef, *, label: str | None = None) -> ProvOEntity:
    """Convert a world-object reference to a PROV-O entity."""

    identifier = ref.world_id or ref.artifact_id or "unknown"
    return ProvOEntity(
        iri=prov_o_iri("entity", identifier),
        label=label or identifier,
        world_id=ref.world_id,
        artifact_id=ref.artifact_id,
    )


def to_prov_o_world_event(event: WorldEvent) -> ProvODocument:
    """Project one world event into a PROV-O aligned document."""

    agent = to_prov_o_agent(event.agent)
    activity = to_prov_o_activity(event.activity)
    entities: list[ProvOEntity] = []
    relations: list[ProvORelation] = []

    for ref in event.inputs:
        entity = to_prov_o_entity(ref)
        entities.append(entity)
        relations.append(
            ProvORelation(
                relation=ProvORelationType.USED,
                subject=activity.iri,
                object=entity.iri,
            )
        )

    for ref in event.outputs:
        entity = to_prov_o_entity(ref)
        entities.append(entity)
        relations.append(
            ProvORelation(
                relation=ProvORelationType.WAS_GENERATED_BY,
                subject=entity.iri,
                object=activity.iri,
            )
        )
        relations.append(
            ProvORelation(
                relation=ProvORelationType.WAS_ATTRIBUTED_TO,
                subject=entity.iri,
                object=agent.iri,
            )
        )

    if event.evidence_ref is not None:
        evidence = ProvOEntity(
            iri=prov_o_iri("entity", event.evidence_ref),
            label=event.evidence_ref,
            artifact_id=event.evidence_ref,
        )
        entities.append(evidence)
        relations.append(
            ProvORelation(
                relation=ProvORelationType.WAS_DERIVED_FROM,
                subject=activity.iri,
                object=evidence.iri,
            )
        )

    relations.append(
        ProvORelation(
            relation=ProvORelationType.WAS_ASSOCIATED_WITH,
            subject=activity.iri,
            object=agent.iri,
        )
    )

    return ProvODocument(
        event_id=event.event_id,
        agents=[agent],
        activities=[activity],
        entities=entities,
        relations=relations,
    )


__all__ = [
    "ProvOAgent",
    "ProvOActivityRecord",
    "ProvODocument",
    "ProvOEntity",
    "ProvORelation",
    "ProvORelationType",
    "ProvORecordType",
    "prov_o_iri",
    "to_prov_o_activity",
    "to_prov_o_agent",
    "to_prov_o_entity",
    "to_prov_o_world_event",
]
