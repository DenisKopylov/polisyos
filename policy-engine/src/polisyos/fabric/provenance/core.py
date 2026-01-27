from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
import hashlib
import json


class EntityType(Enum):
    """PROV-O Entity subtypes for Policy OS domain."""

    DATASET = "dataset"
    METRIC = "metric"
    SNAPSHOT = "snapshot"
    FACT_SEGMENT = "fact_segment"
    QUERY_RESULT = "query_result"
    SIMULATION_STATE = "simulation_state"


class ActivityType(Enum):
    """PROV-O Activity subtypes for Policy OS domain."""

    INGEST = "ingest"
    QUERY = "query"
    ETL = "etl"
    AGGREGATION = "aggregation"
    SIMULATION_STEP = "simulation_step"
    VALIDATION = "validation"
    MERGE = "merge"


class AgentType(Enum):
    """PROV-O Agent subtypes."""

    SYSTEM = "system"
    USER = "user"
    MODEL = "model"
    SCHEDULER = "scheduler"


class RelationType(Enum):
    """W3C PROV-O relations."""

    WAS_DERIVED_FROM = "wasDerivedFrom"
    WAS_GENERATED_BY = "wasGeneratedBy"
    USED = "used"
    WAS_ATTRIBUTED_TO = "wasAttributedTo"
    WAS_ASSOCIATED_WITH = "wasAssociatedWith"
    ACTED_ON_BEHALF_OF = "actedOnBehalfOf"


@dataclass(frozen=True, slots=True)
class ProvenanceEntity:
    """
    Data entity in provenance graph (PROV-O: prov:Entity).

    Represents datasets, metrics, snapshots, or any data artifact
    that participates in the lineage graph.
    """

    entity_id: str
    entity_type: EntityType
    label: str
    created_at: datetime
    attributes: dict[str, str | int | float | bool] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProvenanceEntity):
            return False
        return self.entity_id == other.entity_id

    def __hash__(self) -> int:
        return hash(self.entity_id)


@dataclass(frozen=True, slots=True)
class ProvenanceActivity:
    """
    Transformation activity (PROV-O: prov:Activity).

    Represents an action that transforms or generates entities:
    queries, ETL steps, simulation runs, validations, etc.
    """

    activity_id: str
    activity_type: ActivityType
    label: str
    started_at: datetime
    ended_at: datetime | None = None
    query_hash: str | None = None
    etl_step_id: str | None = None
    code_artifact_ref: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProvenanceActivity):
            return False
        return self.activity_id == other.activity_id

    def __hash__(self) -> int:
        return hash(self.activity_id)


@dataclass(frozen=True, slots=True)
class ProvenanceAgent:
    """
    Agent responsible for activity (PROV-O: prov:Agent).

    Represents the system, user, or AI model that triggered
    or executed an activity.
    """

    agent_id: str
    agent_type: AgentType
    label: str
    metadata: dict[str, str] = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProvenanceAgent):
            return False
        return self.agent_id == other.agent_id

    def __hash__(self) -> int:
        return hash(self.agent_id)


@dataclass(frozen=True, slots=True)
class ProvenanceEdge:
    """
    Directed edge in provenance graph.

    Encodes PROV-O relations between nodes. Edge direction follows
    PROV-O semantics:
      - wasDerivedFrom: derived_entity -> source_entity
      - wasGeneratedBy: entity -> activity
      - used: activity -> entity
      - wasAttributedTo: entity -> agent
      - wasAssociatedWith: activity -> agent
    """

    source_id: str
    target_id: str
    relation: RelationType
    timestamp: datetime | None = None

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ProvenanceEdge):
            return False
        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.relation == other.relation
        )

    def __hash__(self) -> int:
        return hash((self.source_id, self.target_id, self.relation))

    def to_tuple(self) -> tuple[str, str, str]:
        """Deterministic tuple for sorting."""
        return (self.source_id, self.target_id, self.relation.value)


@dataclass
class ProvenanceCoreGraph:
    """
    Minimal lineage graph - always present in Fabric results.

    This is the "core" internal model. PROV-O export is optional
    (via export_provo.py) for STRICT profile or external audit.
    """

    graph_id: str
    entities: dict[str, ProvenanceEntity] = field(default_factory=dict)
    activities: dict[str, ProvenanceActivity] = field(default_factory=dict)
    agents: dict[str, ProvenanceAgent] = field(default_factory=dict)
    edges: list[ProvenanceEdge] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = field(default_factory=dict)

    # --- Node Registration (O(1) insertion) ---

    def add_entity(self, entity: ProvenanceEntity) -> None:
        """Register an entity node. Idempotent by entity_id."""
        self.entities[entity.entity_id] = entity

    def add_activity(self, activity: ProvenanceActivity) -> None:
        """Register an activity node. Idempotent by activity_id."""
        self.activities[activity.activity_id] = activity

    def add_agent(self, agent: ProvenanceAgent) -> None:
        """Register an agent node. Idempotent by agent_id."""
        self.agents[agent.agent_id] = agent

    # --- Edge Registration (PROV-O Relations) ---

    def add_derivation(
        self,
        derived_id: str,
        source_id: str,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Record that derived entity came from source (wasDerivedFrom).

        PROV-O: derived prov:wasDerivedFrom source
        """
        self.edges.append(
            ProvenanceEdge(
                source_id=derived_id,
                target_id=source_id,
                relation=RelationType.WAS_DERIVED_FROM,
                timestamp=timestamp,
            )
        )

    def add_generation(
        self,
        entity_id: str,
        activity_id: str,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Record that entity was generated by activity (wasGeneratedBy).

        PROV-O: entity prov:wasGeneratedBy activity
        """
        self.edges.append(
            ProvenanceEdge(
                source_id=entity_id,
                target_id=activity_id,
                relation=RelationType.WAS_GENERATED_BY,
                timestamp=timestamp,
            )
        )

    def add_usage(
        self,
        activity_id: str,
        entity_id: str,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Record that activity used entity (used).

        PROV-O: activity prov:used entity
        """
        self.edges.append(
            ProvenanceEdge(
                source_id=activity_id,
                target_id=entity_id,
                relation=RelationType.USED,
                timestamp=timestamp,
            )
        )

    def add_attribution(
        self,
        entity_id: str,
        agent_id: str,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Record that entity was attributed to agent (wasAttributedTo).

        PROV-O: entity prov:wasAttributedTo agent
        """
        self.edges.append(
            ProvenanceEdge(
                source_id=entity_id,
                target_id=agent_id,
                relation=RelationType.WAS_ATTRIBUTED_TO,
                timestamp=timestamp,
            )
        )

    def add_association(
        self,
        activity_id: str,
        agent_id: str,
        timestamp: datetime | None = None,
    ) -> None:
        """
        Record that activity was associated with agent (wasAssociatedWith).

        PROV-O: activity prov:wasAssociatedWith agent
        """
        self.edges.append(
            ProvenanceEdge(
                source_id=activity_id,
                target_id=agent_id,
                relation=RelationType.WAS_ASSOCIATED_WITH,
                timestamp=timestamp,
            )
        )

    # --- Query Methods ---

    def get_entity(self, entity_id: str) -> ProvenanceEntity | None:
        """O(1) entity lookup."""
        return self.entities.get(entity_id)

    def get_activity(self, activity_id: str) -> ProvenanceActivity | None:
        """O(1) activity lookup."""
        return self.activities.get(activity_id)

    def get_agent(self, agent_id: str) -> ProvenanceAgent | None:
        """O(1) agent lookup."""
        return self.agents.get(agent_id)

    def get_ancestors(self, entity_id: str, max_depth: int = 10) -> set[str]:
        """
        Find all ancestor entities via wasDerivedFrom edges.

        Uses BFS with depth limit to prevent infinite loops.
        """
        ancestors: set[str] = set()
        frontier = {entity_id}

        for _ in range(max_depth):
            next_frontier: set[str] = set()
            for eid in frontier:
                for edge in self.edges:
                    if (
                        edge.source_id == eid
                        and edge.relation == RelationType.WAS_DERIVED_FROM
                    ):
                        if edge.target_id not in ancestors:
                            ancestors.add(edge.target_id)
                            next_frontier.add(edge.target_id)
            if not next_frontier:
                break
            frontier = next_frontier

        return ancestors

    def get_generating_activity(self, entity_id: str) -> str | None:
        """Find the activity that generated this entity."""
        for edge in self.edges:
            if (
                edge.source_id == entity_id
                and edge.relation == RelationType.WAS_GENERATED_BY
            ):
                return edge.target_id
        return None

    # --- Serialization & Hashing ---

    def compute_stable_id(self) -> str:
        """
        Compute deterministic ID for CAS storage.

        The ID is based on a canonical JSON representation of all
        nodes and edges, ensuring identical graphs produce identical IDs.
        """
        sorted_entities = sorted(
            [
                {
                    "id": e.entity_id,
                    "type": e.entity_type.value,
                    "label": e.label,
                    "created_at": e.created_at.isoformat(),
                    "attributes": dict(sorted(e.attributes.items())),
                }
                for e in self.entities.values()
            ],
            key=lambda x: x["id"],
        )

        sorted_activities = sorted(
            [
                {
                    "id": a.activity_id,
                    "type": a.activity_type.value,
                    "label": a.label,
                    "started_at": a.started_at.isoformat(),
                    "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                    "query_hash": a.query_hash,
                    "etl_step_id": a.etl_step_id,
                    "code_artifact_ref": a.code_artifact_ref,
                    "parameters": a.parameters,
                }
                for a in self.activities.values()
            ],
            key=lambda x: x["id"],
        )

        sorted_agents = sorted(
            [
                {
                    "id": g.agent_id,
                    "type": g.agent_type.value,
                    "label": g.label,
                    "metadata": dict(sorted(g.metadata.items())),
                }
                for g in self.agents.values()
            ],
            key=lambda x: x["id"],
        )

        sorted_edges = sorted([e.to_tuple() for e in self.edges])

        canonical = {
            "entities": sorted_entities,
            "activities": sorted_activities,
            "agents": sorted_agents,
            "edges": sorted_edges,
        }

        content = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for JSON/CAS storage."""
        return {
            "graph_id": self.graph_id,
            "stable_id": self.compute_stable_id(),
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
            "entities": [
                {
                    "entity_id": e.entity_id,
                    "entity_type": e.entity_type.value,
                    "label": e.label,
                    "created_at": e.created_at.isoformat(),
                    "attributes": e.attributes,
                }
                for e in self.entities.values()
            ],
            "activities": [
                {
                    "activity_id": a.activity_id,
                    "activity_type": a.activity_type.value,
                    "label": a.label,
                    "started_at": a.started_at.isoformat(),
                    "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                    "query_hash": a.query_hash,
                    "etl_step_id": a.etl_step_id,
                    "code_artifact_ref": a.code_artifact_ref,
                    "parameters": a.parameters,
                }
                for a in self.activities.values()
            ],
            "agents": [
                {
                    "agent_id": g.agent_id,
                    "agent_type": g.agent_type.value,
                    "label": g.label,
                    "metadata": g.metadata,
                }
                for g in self.agents.values()
            ],
            "edges": [
                {
                    "source_id": e.source_id,
                    "target_id": e.target_id,
                    "relation": e.relation.value,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProvenanceCoreGraph:
        """Deserialize from dictionary."""
        graph = cls(
            graph_id=data["graph_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            metadata=data.get("metadata", {}),
        )

        for e in data.get("entities", []):
            graph.add_entity(
                ProvenanceEntity(
                    entity_id=e["entity_id"],
                    entity_type=EntityType(e["entity_type"]),
                    label=e["label"],
                    created_at=datetime.fromisoformat(e["created_at"]),
                    attributes=e.get("attributes", {}),
                )
            )

        for a in data.get("activities", []):
            graph.add_activity(
                ProvenanceActivity(
                    activity_id=a["activity_id"],
                    activity_type=ActivityType(a["activity_type"]),
                    label=a["label"],
                    started_at=datetime.fromisoformat(a["started_at"]),
                    ended_at=(
                        datetime.fromisoformat(a["ended_at"]) if a.get("ended_at") else None
                    ),
                    query_hash=a.get("query_hash"),
                    etl_step_id=a.get("etl_step_id"),
                    code_artifact_ref=a.get("code_artifact_ref"),
                    parameters=a.get("parameters", {}),
                )
            )

        for g in data.get("agents", []):
            graph.add_agent(
                ProvenanceAgent(
                    agent_id=g["agent_id"],
                    agent_type=AgentType(g["agent_type"]),
                    label=g["label"],
                    metadata=g.get("metadata", {}),
                )
            )

        for e in data.get("edges", []):
            graph.edges.append(
                ProvenanceEdge(
                    source_id=e["source_id"],
                    target_id=e["target_id"],
                    relation=RelationType(e["relation"]),
                    timestamp=(
                        datetime.fromisoformat(e["timestamp"]) if e.get("timestamp") else None
                    ),
                )
            )

        return graph


@dataclass(frozen=True)
class ProvenanceCoreRef:
    """
    Reference to a persisted ProvenanceCoreGraph.

    Used in EvidenceBundle to link to the full lineage graph
    without embedding it directly.
    """

    graph_id: str
    stable_id: str
    artifact_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "graph_id": self.graph_id,
            "stable_id": self.stable_id,
            "artifact_id": self.artifact_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> ProvenanceCoreRef:
        return cls(
            graph_id=data["graph_id"],
            stable_id=data["stable_id"],
            artifact_id=data["artifact_id"],
        )
