"""W3C PROV-JSON serialization and deserialization.

Implements the PROV-JSON format per https://www.w3.org/Submission/prov-json/.
Compatible with ProvToolbox and ProvStore.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from polisyos.core.contracts.provenance import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEdge,
    ProvenanceEntity,
    RelationType,
)


def to_prov_json(graph: ProvenanceCoreGraph) -> dict[str, Any]:
    """Serialize a ProvenanceCoreGraph to W3C PROV-JSON format.

    Returns
    -------
    dict
        PROV-JSON document with keys: prefix, entity, activity, agent,
        wasGeneratedBy, used, wasDerivedFrom, wasAttributedTo, wasAssociatedWith.
    """
    doc: dict[str, Any] = {
        "prefix": {
            "polisyos": "https://polisyos.io/prov/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
        },
    }

    # Entities
    if graph.entities:
        doc["entity"] = {}
        for eid, entity in graph.entities.items():
            doc["entity"][eid] = {
                "prov:type": entity.entity_type.value,
                "prov:label": entity.label,
                "prov:generatedAtTime": entity.created_at.isoformat(),
                **{f"polisyos:{k}": v for k, v in entity.attributes.items()},
            }

    # Activities
    if graph.activities:
        doc["activity"] = {}
        for aid, act in graph.activities.items():
            entry: dict[str, Any] = {
                "prov:type": act.activity_type.value,
                "prov:label": act.label,
                "prov:startTime": act.started_at.isoformat(),
            }
            if act.ended_at:
                entry["prov:endTime"] = act.ended_at.isoformat()
            if act.parameters:
                entry["polisyos:parameters"] = act.parameters
            doc["activity"][aid] = entry

    # Agents
    if graph.agents:
        doc["agent"] = {}
        for gid, agent in graph.agents.items():
            doc["agent"][gid] = {
                "prov:type": agent.agent_type.value,
                "prov:label": agent.label,
                **{f"polisyos:{k}": v for k, v in agent.metadata.items()},
            }

    # Relations (edges)
    _relation_keys = {
        RelationType.WAS_GENERATED_BY: "wasGeneratedBy",
        RelationType.USED: "used",
        RelationType.WAS_DERIVED_FROM: "wasDerivedFrom",
        RelationType.WAS_ATTRIBUTED_TO: "wasAttributedTo",
        RelationType.WAS_ASSOCIATED_WITH: "wasAssociatedWith",
        RelationType.ACTED_ON_BEHALF_OF: "actedOnBehalfOf",
    }

    for edge in graph.edges:
        key = _relation_keys.get(edge.relation)
        if key is None:
            continue
        if key not in doc:
            doc[key] = {}

        edge_id = f"_{edge.source_id}__{edge.target_id}__{edge.relation.value}"
        entry: dict[str, Any] = {}

        if edge.relation == RelationType.WAS_GENERATED_BY:
            entry["prov:entity"] = edge.source_id
            entry["prov:activity"] = edge.target_id
        elif edge.relation == RelationType.USED:
            entry["prov:activity"] = edge.source_id
            entry["prov:entity"] = edge.target_id
        elif edge.relation == RelationType.WAS_DERIVED_FROM:
            entry["prov:generatedEntity"] = edge.source_id
            entry["prov:usedEntity"] = edge.target_id
        elif edge.relation == RelationType.WAS_ATTRIBUTED_TO:
            entry["prov:entity"] = edge.source_id
            entry["prov:agent"] = edge.target_id
        elif edge.relation == RelationType.WAS_ASSOCIATED_WITH:
            entry["prov:activity"] = edge.source_id
            entry["prov:agent"] = edge.target_id

        if edge.timestamp:
            entry["prov:time"] = edge.timestamp.isoformat()

        doc[key][edge_id] = entry

    return doc


def from_prov_json(data: dict[str, Any]) -> ProvenanceCoreGraph:
    """Deserialize a W3C PROV-JSON document to ProvenanceCoreGraph.

    Parameters
    ----------
    data:
        PROV-JSON dict with entity/activity/agent/relation keys.

    Returns
    -------
    ProvenanceCoreGraph
    """
    graph = ProvenanceCoreGraph(graph_id="imported")

    # Parse entities
    for eid, edata in data.get("entity", {}).items():
        attrs = {
            k.replace("polisyos:", ""): v for k, v in edata.items() if k.startswith("polisyos:")
        }
        graph.add_entity(
            ProvenanceEntity(
                entity_id=eid,
                entity_type=EntityType(edata.get("prov:type", "dataset")),
                label=edata.get("prov:label", eid),
                created_at=datetime.fromisoformat(edata["prov:generatedAtTime"])
                if "prov:generatedAtTime" in edata
                else datetime.now(UTC),
                attributes=attrs,
            )
        )

    # Parse activities
    for aid, adata in data.get("activity", {}).items():
        graph.add_activity(
            ProvenanceActivity(
                activity_id=aid,
                activity_type=ActivityType(adata.get("prov:type", "query")),
                label=adata.get("prov:label", aid),
                started_at=datetime.fromisoformat(adata["prov:startTime"])
                if "prov:startTime" in adata
                else datetime.now(UTC),
                ended_at=datetime.fromisoformat(adata["prov:endTime"])
                if "prov:endTime" in adata
                else None,
                parameters=adata.get("polisyos:parameters", {}),
            )
        )

    # Parse agents
    for gid, gdata in data.get("agent", {}).items():
        meta = {
            k.replace("polisyos:", ""): v for k, v in gdata.items() if k.startswith("polisyos:")
        }
        graph.add_agent(
            ProvenanceAgent(
                agent_id=gid,
                agent_type=AgentType(gdata.get("prov:type", "system")),
                label=gdata.get("prov:label", gid),
                metadata=meta,
            )
        )

    # Parse relations
    _parse_relations(
        graph, data, "wasGeneratedBy", RelationType.WAS_GENERATED_BY, "prov:entity", "prov:activity"
    )
    _parse_relations(graph, data, "used", RelationType.USED, "prov:activity", "prov:entity")
    _parse_relations(
        graph,
        data,
        "wasDerivedFrom",
        RelationType.WAS_DERIVED_FROM,
        "prov:generatedEntity",
        "prov:usedEntity",
    )
    _parse_relations(
        graph, data, "wasAttributedTo", RelationType.WAS_ATTRIBUTED_TO, "prov:entity", "prov:agent"
    )
    _parse_relations(
        graph,
        data,
        "wasAssociatedWith",
        RelationType.WAS_ASSOCIATED_WITH,
        "prov:activity",
        "prov:agent",
    )

    return graph


def _parse_relations(
    graph: ProvenanceCoreGraph,
    data: dict[str, Any],
    key: str,
    relation: RelationType,
    source_field: str,
    target_field: str,
) -> None:
    for _edge_id, edata in data.get(key, {}).items():
        source = edata.get(source_field, "")
        target = edata.get(target_field, "")
        ts = datetime.fromisoformat(edata["prov:time"]) if "prov:time" in edata else None
        graph.edges.append(
            ProvenanceEdge(
                source_id=source,
                target_id=target,
                relation=relation,
                timestamp=ts,
            )
        )
