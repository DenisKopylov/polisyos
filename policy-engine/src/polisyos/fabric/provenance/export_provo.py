"""Public provenance export provo module API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from polisyos.core.audit.prov_json import ProvJsonConverter
from polisyos.fabric.provenance.core import (
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceEdge,
    ProvenanceEntity,
)
from polisyos.fabric.temporal import ensure_aware_utc

PROV_CONTEXT = {
    "@context": {
        "prov": "http://www.w3.org/ns/prov#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "polisyos": "https://polisyos.io/ns/provenance#",
        "Entity": "prov:Entity",
        "Activity": "prov:Activity",
        "Agent": "prov:Agent",
        "wasDerivedFrom": {"@id": "prov:wasDerivedFrom", "@type": "@id"},
        "wasGeneratedBy": {"@id": "prov:wasGeneratedBy", "@type": "@id"},
        "used": {"@id": "prov:used", "@type": "@id"},
        "wasAttributedTo": {"@id": "prov:wasAttributedTo", "@type": "@id"},
        "wasAssociatedWith": {"@id": "prov:wasAssociatedWith", "@type": "@id"},
        "actedOnBehalfOf": {"@id": "prov:actedOnBehalfOf", "@type": "@id"},
        "generatedAtTime": {"@id": "prov:generatedAtTime", "@type": "xsd:dateTime"},
        "startedAtTime": {"@id": "prov:startedAtTime", "@type": "xsd:dateTime"},
        "endedAtTime": {"@id": "prov:endedAtTime", "@type": "xsd:dateTime"},
        "label": "rdfs:label",
        "entityType": "polisyos:entityType",
        "activityType": "polisyos:activityType",
        "agentType": "polisyos:agentType",
        "queryHash": "polisyos:queryHash",
        "etlStepId": "polisyos:etlStepId",
        "codeArtifactRef": "polisyos:codeArtifactRef",
    }
}


def _format_datetime(dt: datetime) -> str:
    """Format datetime for JSON-LD (ISO 8601 with timezone)."""
    return ensure_aware_utc(dt, what="provenance datetime").isoformat().replace("+00:00", "Z")


def _escape_nquads_literal(value: str) -> str:
    """Escape a string for use in an RDF N-Quads literal."""
    escaped: list[str] = []
    for char in str(value):
        codepoint = ord(char)
        if char == "\\":
            escaped.append("\\\\")
        elif char == '"':
            escaped.append('\\"')
        elif char == "\n":
            escaped.append("\\n")
        elif char == "\r":
            escaped.append("\\r")
        elif char == "\t":
            escaped.append("\\t")
        elif codepoint < 0x20 or codepoint == 0x7F:
            escaped.append(f"\\u{codepoint:04X}")
        else:
            escaped.append(char)
    return "".join(escaped)


def _entity_to_jsonld(entity: ProvenanceEntity, base_uri: str) -> dict[str, Any]:
    """Convert ProvenanceEntity to JSON-LD node."""
    node: dict[str, Any] = {
        "@id": f"{base_uri}entity/{entity.entity_id}",
        "@type": "Entity",
        "label": entity.label,
        "generatedAtTime": _format_datetime(entity.created_at),
        "entityType": entity.entity_type.value,
    }

    for key, value in entity.attributes.items():
        node[f"polisyos:{key}"] = value

    return node


def _activity_to_jsonld(activity: ProvenanceActivity, base_uri: str) -> dict[str, Any]:
    """Convert ProvenanceActivity to JSON-LD node."""
    node: dict[str, Any] = {
        "@id": f"{base_uri}activity/{activity.activity_id}",
        "@type": "Activity",
        "label": activity.label,
        "startedAtTime": _format_datetime(activity.started_at),
        "activityType": activity.activity_type.value,
    }

    if activity.ended_at:
        node["endedAtTime"] = _format_datetime(activity.ended_at)

    if activity.query_hash:
        node["queryHash"] = activity.query_hash

    if activity.etl_step_id:
        node["etlStepId"] = activity.etl_step_id

    if activity.code_artifact_ref:
        node["codeArtifactRef"] = activity.code_artifact_ref

    return node


def _agent_to_jsonld(agent: ProvenanceAgent, base_uri: str) -> dict[str, Any]:
    """Convert ProvenanceAgent to JSON-LD node."""
    node: dict[str, Any] = {
        "@id": f"{base_uri}agent/{agent.agent_id}",
        "@type": "Agent",
        "label": agent.label,
        "agentType": agent.agent_type.value,
    }

    for key, value in agent.metadata.items():
        node[f"polisyos:{key}"] = value

    return node


def _get_node_prefix(node_id: str, graph: ProvenanceCoreGraph) -> str:
    """Determine node type prefix for URI construction."""
    if node_id in graph.entities:
        return "entity"
    if node_id in graph.activities:
        return "activity"
    if node_id in graph.agents:
        return "agent"
    return "unknown"


def export_to_provo_jsonld(
    graph: ProvenanceCoreGraph,
    base_uri: str = "https://polisyos.io/provenance/",
) -> dict[str, Any]:
    """
    Export provenance graph to W3C PROV-O JSON-LD format.

    This is the optional export for STRICT validation profile or
    external audit requirements.
    """
    nodes: list[dict[str, Any]] = []

    for entity in graph.entities.values():
        nodes.append(_entity_to_jsonld(entity, base_uri))

    for activity in graph.activities.values():
        nodes.append(_activity_to_jsonld(activity, base_uri))

    for agent in graph.agents.values():
        nodes.append(_agent_to_jsonld(agent, base_uri))

    edges_by_source: dict[str, list[ProvenanceEdge]] = {}
    for edge in graph.edges:
        edges_by_source.setdefault(edge.source_id, []).append(edge)

    for node in nodes:
        node_id = node["@id"].split("/")[-1]
        if node_id in edges_by_source:
            for edge in edges_by_source[node_id]:
                target_prefix = _get_node_prefix(edge.target_id, graph)
                target_uri = f"{base_uri}{target_prefix}/{edge.target_id}"

                rel_key = edge.relation.value
                if rel_key in node:
                    if isinstance(node[rel_key], list):
                        node[rel_key].append({"@id": target_uri})
                    else:
                        node[rel_key] = [node[rel_key], {"@id": target_uri}]
                else:
                    node[rel_key] = {"@id": target_uri}

    return {**PROV_CONTEXT, "@graph": nodes}


def export_to_provo_nquads(
    graph: ProvenanceCoreGraph,
    base_uri: str = "https://polisyos.io/provenance/",
) -> str:
    """
    Export provenance graph to N-Quads format for RDF triple stores.
    """
    lines: list[str] = []
    prov = "http://www.w3.org/ns/prov#"
    rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    rdfs = "http://www.w3.org/2000/01/rdf-schema#"
    xsd = "http://www.w3.org/2001/XMLSchema#"

    def uri(suffix: str) -> str:
        return f"<{base_uri}{suffix}>"

    for entity in graph.entities.values():
        subj = uri(f"entity/{entity.entity_id}")
        lines.append(f"{subj} <{rdf}type> <{prov}Entity> .")
        lines.append(f'{subj} <{rdfs}label> "{_escape_nquads_literal(entity.label)}" .')
        lines.append(
            f"{subj} <{prov}generatedAtTime> "
            f'"{_format_datetime(entity.created_at)}"^^<{xsd}dateTime> .'
        )

    for activity in graph.activities.values():
        subj = uri(f"activity/{activity.activity_id}")
        lines.append(f"{subj} <{rdf}type> <{prov}Activity> .")
        lines.append(f'{subj} <{rdfs}label> "{_escape_nquads_literal(activity.label)}" .')
        lines.append(
            f"{subj} <{prov}startedAtTime> "
            f'"{_format_datetime(activity.started_at)}"^^<{xsd}dateTime> .'
        )
        if activity.ended_at:
            lines.append(
                f"{subj} <{prov}endedAtTime> "
                f'"{_format_datetime(activity.ended_at)}"^^<{xsd}dateTime> .'
            )

    for agent in graph.agents.values():
        subj = uri(f"agent/{agent.agent_id}")
        lines.append(f"{subj} <{rdf}type> <{prov}Agent> .")
        lines.append(f'{subj} <{rdfs}label> "{_escape_nquads_literal(agent.label)}" .')

    for edge in graph.edges:
        source_prefix = _get_node_prefix(edge.source_id, graph)
        target_prefix = _get_node_prefix(edge.target_id, graph)

        subj = uri(f"{source_prefix}/{edge.source_id}")
        obj = uri(f"{target_prefix}/{edge.target_id}")
        pred = f"<{prov}{edge.relation.value}>"

        lines.append(f"{subj} {pred} {obj} .")

    return "\n".join(lines)


def export_to_prov_json(
    graph: ProvenanceCoreGraph,
    *,
    run_id: str | None = None,
    include_bundle: bool = True,
) -> dict[str, Any]:
    """
    Export provenance graph to W3C PROV-JSON.

    This complements JSON-LD / N-Quads exporters and is intended for
    external audit package generation.
    """
    return ProvJsonConverter(run_id=run_id, include_bundle=include_bundle).convert(graph)
