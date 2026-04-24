"""Public audit prov json module API."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from polisyos.core.canon import truncated_hash
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

PROV_JSON_PREFIXES: dict[str, str] = {
    "pos": "https://polisyos.io/ns/",
    "posrun": "https://polisyos.io/run/",
    "posart": "https://polisyos.io/artifact/",
    "prov": "http://www.w3.org/ns/prov#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
}

ARTIFACT_KIND_MAP: dict[str, str] = {
    "scientist.decision_packet": "pos:DecisionPacket",
    "scientist.experiment_state": "pos:ExperimentState",
    "scientist.workflow_report": "pos:WorkflowReport",
    "foundry.program_graph": "pos:ProgramGraph",
    "foundry.exec_plan": "pos:ExecPlan",
    "foundry.simulation_result": "pos:SimulationResult",
    "foundry.metrics": "pos:Metrics",
    "foundry.environment_manifest": "pos:EnvironmentManifest",
    "fabric.evidence_bundle": "pos:EvidenceBundle",
    "fabric.data_snapshot": "pos:DataSnapshot",
    "core.registry_bundle": "pos:RegistryBundle",
    "core.run_manifest": "pos:RunManifest",
    "core.trace.jsonl": "pos:TraceLog",
    "fabric.provenance_graph": "pos:ProvenanceGraph",
}

ENTITY_TYPE_MAP: dict[EntityType, str] = {
    EntityType.DATASET: "pos:Dataset",
    EntityType.METRIC: "pos:Metric",
    EntityType.SNAPSHOT: "pos:Snapshot",
    EntityType.FACT_SEGMENT: "pos:FactSegment",
    EntityType.QUERY_RESULT: "pos:QueryResult",
    EntityType.SIMULATION_STATE: "pos:SimulationState",
}

ACTIVITY_TYPE_MAP: dict[ActivityType, str] = {
    ActivityType.INGEST: "pos:DataIngestion",
    ActivityType.QUERY: "pos:UDFQuery",
    ActivityType.ETL: "pos:ETL",
    ActivityType.AGGREGATION: "pos:Aggregation",
    ActivityType.SIMULATION_STEP: "pos:Simulation",
    ActivityType.VALIDATION: "pos:Validation",
    ActivityType.MERGE: "pos:Merge",
}

AGENT_TYPE_MAP: dict[AgentType, str] = {
    AgentType.SYSTEM: "pos:SystemAgent",
    AgentType.USER: "prov:Person",
    AgentType.MODEL: "pos:LLMAgent",
    AgentType.SCHEDULER: "pos:SchedulerAgent",
}

_ARTIFACT_ID_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


def _qual_name(value: str) -> dict[str, str]:
    return {"$": value, "type": "prov:QUALIFIED_NAME"}


def _xsd_datetime(value: datetime) -> dict[str, str]:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    iso = value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return {"$": iso, "type": "xsd:dateTime"}


def _sanitize(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_./:-]+", "_", value)


def _edge_id(prefix: str, src: str, tgt: str, rel: str) -> str:
    digest = truncated_hash(f"{src}|{tgt}|{rel}", length=16)
    return f"_:{prefix}{digest}"


class ProvJsonConverter:
    """Convert internal ProvenanceCoreGraph to W3C PROV-JSON."""

    def __init__(
        self,
        *,
        run_id: str | None = None,
        include_bundle: bool = True,
    ) -> None:
        self._run_id = run_id
        self._include_bundle = include_bundle

    def convert(self, graph: ProvenanceCoreGraph) -> dict[str, Any]:
        entity = {
            self._qualify_entity_id(item.entity_id): self._entity_to_prov_json(item)
            for item in sorted(graph.entities.values(), key=lambda it: it.entity_id)
        }
        activity = {
            self._qualify_activity_id(item.activity_id): self._activity_to_prov_json(item)
            for item in sorted(graph.activities.values(), key=lambda it: it.activity_id)
        }
        agent = {
            self._qualify_agent_id(item.agent_id): self._agent_to_prov_json(item)
            for item in sorted(graph.agents.values(), key=lambda it: it.agent_id)
        }

        relations = self._edges_to_prov_json(graph.edges)
        result: dict[str, Any] = {
            "prefix": dict(PROV_JSON_PREFIXES),
            "entity": entity,
            "activity": activity,
            "agent": agent,
            **relations,
        }

        if self._include_bundle and self._run_id:
            result["bundle"] = {
                f"posrun:{_sanitize(self._run_id)}": {
                    "entity": entity,
                    "activity": activity,
                    "agent": agent,
                    **relations,
                }
            }

        return result

    def _qualify_entity_id(self, entity_id: str) -> str:
        match = _ARTIFACT_ID_RE.match(entity_id)
        if match:
            return f"posart:{match.group(1)}"
        if entity_id.startswith("posart:"):
            return entity_id
        if entity_id.startswith("posrun:"):
            return entity_id
        return f"pos:{_sanitize(entity_id)}"

    def _qualify_activity_id(self, activity_id: str) -> str:
        if activity_id.startswith("posrun:"):
            return activity_id
        if self._run_id:
            return f"posrun:{_sanitize(self._run_id)}/activity/{_sanitize(activity_id)}"
        return f"pos:activity/{_sanitize(activity_id)}"

    def _qualify_agent_id(self, agent_id: str) -> str:
        if agent_id.startswith("pos:"):
            return agent_id
        if agent_id.startswith("posrun:"):
            return agent_id
        return f"pos:agent/{_sanitize(agent_id)}"

    def _entity_to_prov_json(self, entity: ProvenanceEntity) -> dict[str, Any]:
        kind = str(entity.attributes.get("kind", ""))
        prov_type = ARTIFACT_KIND_MAP.get(
            kind, ENTITY_TYPE_MAP.get(entity.entity_type, "pos:Entity")
        )
        data: dict[str, Any] = {
            "prov:type": _qual_name(prov_type),
            "prov:label": entity.label,
            "prov:generatedAtTime": _xsd_datetime(entity.created_at),
        }
        for key, value in sorted(entity.attributes.items(), key=lambda item: item[0]):
            data[f"pos:{_sanitize(key)}"] = value
        return data

    def _activity_to_prov_json(self, activity: ProvenanceActivity) -> dict[str, Any]:
        data: dict[str, Any] = {
            "prov:type": _qual_name(ACTIVITY_TYPE_MAP.get(activity.activity_type, "pos:Activity")),
            "prov:label": activity.label,
            "prov:startTime": _xsd_datetime(activity.started_at),
        }
        if activity.ended_at is not None:
            data["prov:endTime"] = _xsd_datetime(activity.ended_at)
            duration_ms = int((activity.ended_at - activity.started_at).total_seconds() * 1000)
            data["pos:durationMs"] = max(0, duration_ms)
        if activity.query_hash:
            data["pos:queryHash"] = activity.query_hash
        if activity.etl_step_id:
            data["pos:etlStepId"] = activity.etl_step_id
        if activity.code_artifact_ref:
            data["pos:codeArtifactRef"] = activity.code_artifact_ref
        if activity.parameters:
            data["pos:parameters"] = activity.parameters
        return data

    def _agent_to_prov_json(self, agent: ProvenanceAgent) -> dict[str, Any]:
        data: dict[str, Any] = {
            "prov:type": _qual_name(AGENT_TYPE_MAP.get(agent.agent_type, "pos:Agent")),
            "prov:label": agent.label,
        }
        if agent.metadata:
            data["pos:metadata"] = dict(agent.metadata)
        return data

    def _edges_to_prov_json(
        self, edges: list[ProvenanceEdge]
    ) -> dict[str, dict[str, dict[str, str]]]:
        grouped: dict[str, dict[str, dict[str, str]]] = {
            "wasGeneratedBy": {},
            "used": {},
            "wasDerivedFrom": {},
            "wasAttributedTo": {},
            "wasAssociatedWith": {},
            "actedOnBehalfOf": {},
        }
        for edge in sorted(edges, key=lambda item: item.to_tuple()):
            src = self._qualify_node_id(edge.source_id)
            tgt = self._qualify_node_id(edge.target_id)
            if edge.relation == RelationType.WAS_GENERATED_BY:
                grouped["wasGeneratedBy"][_edge_id("wgb", src, tgt, edge.relation.value)] = {
                    "prov:entity": src,
                    "prov:activity": tgt,
                }
            elif edge.relation == RelationType.USED:
                grouped["used"][_edge_id("usd", src, tgt, edge.relation.value)] = {
                    "prov:activity": src,
                    "prov:entity": tgt,
                }
            elif edge.relation == RelationType.WAS_DERIVED_FROM:
                grouped["wasDerivedFrom"][_edge_id("wdf", src, tgt, edge.relation.value)] = {
                    "prov:generatedEntity": src,
                    "prov:usedEntity": tgt,
                }
            elif edge.relation == RelationType.WAS_ATTRIBUTED_TO:
                grouped["wasAttributedTo"][_edge_id("wat", src, tgt, edge.relation.value)] = {
                    "prov:entity": src,
                    "prov:agent": tgt,
                }
            elif edge.relation == RelationType.WAS_ASSOCIATED_WITH:
                grouped["wasAssociatedWith"][_edge_id("waw", src, tgt, edge.relation.value)] = {
                    "prov:activity": src,
                    "prov:agent": tgt,
                }
            elif edge.relation == RelationType.ACTED_ON_BEHALF_OF:
                grouped["actedOnBehalfOf"][_edge_id("aob", src, tgt, edge.relation.value)] = {
                    "prov:delegate": src,
                    "prov:responsible": tgt,
                }
        return grouped

    def _qualify_node_id(self, node_id: str) -> str:
        if _ARTIFACT_ID_RE.match(node_id):
            return self._qualify_entity_id(node_id)
        if node_id.startswith("agent/") or node_id.startswith("pos:agent/"):
            return self._qualify_agent_id(node_id.replace("agent/", "", 1))
        if "/" in node_id or ":" in node_id:
            if node_id.startswith("posrun:"):
                return node_id
            if node_id.startswith("posart:"):
                return node_id
            if node_id.startswith("pos:"):
                return node_id
            if self._run_id:
                return f"posrun:{_sanitize(self._run_id)}/{_sanitize(node_id)}"
        return self._qualify_entity_id(node_id)


def prov_json_to_dot(prov_json: dict[str, Any]) -> str:
    """Render PROV-JSON to Graphviz DOT."""
    lines = [
        "digraph Provenance {",
        "    rankdir=BT;",
        '    node [fontname="Helvetica"];',
        '    edge [fontname="Helvetica", fontsize=10];',
    ]
    for ent_id, ent in sorted(prov_json.get("entity", {}).items()):
        label = str(ent.get("prov:label", ent_id)).replace('"', "'")
        node = _sanitize(ent_id).replace("/", "_").replace(":", "_")
        lines.append(f'    {node} [label="{label}", shape=box, style=filled, fillcolor=lightblue];')
    for act_id, act in sorted(prov_json.get("activity", {}).items()):
        label = str(act.get("prov:label", act_id)).replace('"', "'")
        node = _sanitize(act_id).replace("/", "_").replace(":", "_")
        lines.append(
            f'    {node} [label="{label}", shape=ellipse, style=filled, fillcolor=lightyellow];'
        )
    for agent_id, agent in sorted(prov_json.get("agent", {}).items()):
        label = str(agent.get("prov:label", agent_id)).replace('"', "'")
        node = _sanitize(agent_id).replace("/", "_").replace(":", "_")
        lines.append(
            f'    {node} [label="{label}", shape=diamond, style=filled, fillcolor=lightgreen];'
        )

    for rel in prov_json.get("wasGeneratedBy", {}).values():
        _dot_edge(lines, rel.get("prov:entity"), rel.get("prov:activity"), "generated", "green")
    for rel in prov_json.get("used", {}).values():
        _dot_edge(lines, rel.get("prov:activity"), rel.get("prov:entity"), "used", "orange")
    for rel in prov_json.get("wasDerivedFrom", {}).values():
        _dot_edge(
            lines,
            rel.get("prov:generatedEntity"),
            rel.get("prov:usedEntity"),
            "derived",
            "blue",
        )
    for rel in prov_json.get("wasAttributedTo", {}).values():
        _dot_edge(lines, rel.get("prov:entity"), rel.get("prov:agent"), "attributed", "purple")
    for rel in prov_json.get("wasAssociatedWith", {}).values():
        _dot_edge(
            lines,
            rel.get("prov:activity"),
            rel.get("prov:agent"),
            "associated",
            "purple",
        )
    lines.append("}")
    return "\n".join(lines)


def _dot_edge(lines: list[str], src: Any, tgt: Any, label: str, color: str) -> None:
    if not isinstance(src, str) or not isinstance(tgt, str):
        return
    src_node = _sanitize(src).replace("/", "_").replace(":", "_")
    tgt_node = _sanitize(tgt).replace("/", "_").replace(":", "_")
    lines.append(f'    {src_node} -> {tgt_node} [color={color}, label="{label}"];')


def build_core_graph_from_prov_json(prov_json: dict[str, Any]) -> ProvenanceCoreGraph:
    """Best-effort conversion for visualization tooling."""
    graph = ProvenanceCoreGraph(graph_id="prov_json_import")

    for ent_id, ent in prov_json.get("entity", {}).items():
        graph.add_entity(
            ProvenanceEntity(
                entity_id=ent_id,
                entity_type=EntityType.DATASET,
                label=str(ent.get("prov:label", ent_id)),
                created_at=datetime.now(UTC),
                attributes={},
            )
        )
    for act_id, act in prov_json.get("activity", {}).items():
        graph.add_activity(
            ProvenanceActivity(
                activity_id=act_id,
                activity_type=ActivityType.VALIDATION,
                label=str(act.get("prov:label", act_id)),
                started_at=datetime.now(UTC),
                ended_at=datetime.now(UTC),
            )
        )
    for agent_id, agent in prov_json.get("agent", {}).items():
        graph.add_agent(
            ProvenanceAgent(
                agent_id=agent_id,
                agent_type=AgentType.SYSTEM,
                label=str(agent.get("prov:label", agent_id)),
            )
        )

    for rel in prov_json.get("wasGeneratedBy", {}).values():
        ent = rel.get("prov:entity")
        act = rel.get("prov:activity")
        if isinstance(ent, str) and isinstance(act, str):
            graph.add_generation(ent, act)
    for rel in prov_json.get("used", {}).values():
        act = rel.get("prov:activity")
        ent = rel.get("prov:entity")
        if isinstance(act, str) and isinstance(ent, str):
            graph.add_usage(act, ent)
    for rel in prov_json.get("wasDerivedFrom", {}).values():
        gen = rel.get("prov:generatedEntity")
        used = rel.get("prov:usedEntity")
        if isinstance(gen, str) and isinstance(used, str):
            graph.add_derivation(gen, used)
    for rel in prov_json.get("wasAttributedTo", {}).values():
        ent = rel.get("prov:entity")
        agent = rel.get("prov:agent")
        if isinstance(ent, str) and isinstance(agent, str):
            graph.add_attribution(ent, agent)
    for rel in prov_json.get("wasAssociatedWith", {}).values():
        act = rel.get("prov:activity")
        agent = rel.get("prov:agent")
        if isinstance(act, str) and isinstance(agent, str):
            graph.add_association(act, agent)

    return graph
