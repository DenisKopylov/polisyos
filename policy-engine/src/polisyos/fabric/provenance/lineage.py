"""Fabric field/value lineage helpers built on top of the core provenance graph."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Sequence

from polisyos.core.canon import truncated_hash
from polisyos.fabric.provenance.core import (
    ActivityType,
    EntityType,
    ProvenanceActivity,
    ProvenanceCoreGraph,
    ProvenanceEntity,
    RelationType,
)

__all__ = [
    "FabricLineageTracker",
    "LineageNodeSnapshot",
    "LineageTrace",
    "ImpactAnalysis",
    "trace_value_origin",
    "trace_claim_origin",
    "trace_column_lineage",
    "impact_analysis",
    "export_openlineage_json",
    "export_visualization_graph",
]


_FIELD_KEY_RE = re.compile(r"[^a-zA-Z0-9_.-]+")

LINEAGE_KIND_SOURCE_DATASET = "source_dataset"
LINEAGE_KIND_SOURCE_FIELD = "source_field"
LINEAGE_KIND_EVIDENCE_BUNDLE = "evidence_bundle"
LINEAGE_KIND_TRANSFORM_FIELD = "transform_field"
LINEAGE_KIND_MATERIALIZED_COLUMN = "materialized_column"
LINEAGE_KIND_CLAIM_FIELD = "claim_field"
LINEAGE_KIND_WORLD_FACT = "world_fact"
LINEAGE_KIND_WORLD_EVENT = "world_event"
LINEAGE_KIND_FACT_SEGMENT = "fact_segment"
LINEAGE_KIND_QUERY_RESULT_FIELD = "query_result_field"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _slug(value: str) -> str:
    normalized = _FIELD_KEY_RE.sub("_", str(value or "").strip())
    normalized = normalized.strip("._-")
    return normalized or "unknown"


def _stable_suffix(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=True, default=str)
    return truncated_hash(payload, length=12)


def _activity_type_for_stage(stage_name: str) -> ActivityType:
    lowered = stage_name.lower()
    if "aggregate" in lowered:
        return ActivityType.AGGREGATION
    if "valid" in lowered:
        return ActivityType.VALIDATION
    if "query" in lowered:
        return ActivityType.QUERY
    return ActivityType.ETL


def _node_kind(graph: ProvenanceCoreGraph, node_id: str) -> str:
    entity = graph.get_entity(node_id)
    if entity is not None:
        return str(entity.attributes.get("lineage_kind") or entity.entity_type.value)
    activity = graph.get_activity(node_id)
    if activity is not None:
        return str(activity.parameters.get("lineage_kind") or activity.activity_type.value)
    agent = graph.get_agent(node_id)
    if agent is not None:
        return "agent"
    return "unknown"


def _node_label(graph: ProvenanceCoreGraph, node_id: str) -> str:
    entity = graph.get_entity(node_id)
    if entity is not None:
        return entity.label
    activity = graph.get_activity(node_id)
    if activity is not None:
        return activity.label
    agent = graph.get_agent(node_id)
    if agent is not None:
        return agent.label
    return node_id


def _node_attributes(graph: ProvenanceCoreGraph, node_id: str) -> dict[str, Any]:
    entity = graph.get_entity(node_id)
    if entity is not None:
        return dict(entity.attributes)
    activity = graph.get_activity(node_id)
    if activity is not None:
        return dict(activity.parameters)
    agent = graph.get_agent(node_id)
    if agent is not None:
        return dict(agent.metadata)
    return {}


@dataclass(frozen=True)
class LineageNodeSnapshot:
    """Serializable node summary for trace responses."""

    node_id: str
    label: str
    kind: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LineageTrace:
    """Upstream lineage trace for one value or field."""

    root_id: str
    nodes: tuple[LineageNodeSnapshot, ...]
    edges: tuple[tuple[str, str, str], ...]


@dataclass(frozen=True)
class ImpactAnalysis:
    """Downstream impact summary for one source field."""

    root_id: str
    impacted_nodes: tuple[LineageNodeSnapshot, ...]
    materialized_columns: tuple[str, ...]
    claim_fields: tuple[str, ...]
    query_result_fields: tuple[str, ...]
    world_facts: tuple[str, ...]
    world_events: tuple[str, ...]


class FabricLineageTracker:
    """Helper for emitting column/value lineage into a provenance graph."""

    def __init__(
        self,
        graph_id: str,
        *,
        created_at: datetime | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.graph = ProvenanceCoreGraph(
            graph_id=graph_id,
            created_at=created_at or _utc_now(),
            metadata=dict(metadata or {}),
        )
        self._current_field_nodes: dict[str, str] = {}
        self._dataset_nodes: dict[str, str] = {}
        self._evidence_nodes: dict[str, str] = {}
        self._segment_nodes: dict[str, str] = {}
        self._event_nodes: dict[str, str] = {}

    def register_source_dataset(
        self,
        *,
        connector_id: str,
        dataset_id: str,
        fields: Iterable[str],
        schema_id: str | None = None,
        evidence_ref: str | None = None,
        source_artifact_id: str | None = None,
        label: str | None = None,
    ) -> str:
        dataset_node_id = f"dataset.{connector_id}.{dataset_id}"
        schema_key = schema_id or f"{connector_id}.{dataset_id}"
        dataset_entity = ProvenanceEntity(
            entity_id=dataset_node_id,
            entity_type=EntityType.DATASET,
            label=label or f"{connector_id}:{dataset_id}",
            created_at=_utc_now(),
            attributes={
                "lineage_kind": LINEAGE_KIND_SOURCE_DATASET,
                "connector_id": connector_id,
                "dataset_id": dataset_id,
                "schema_id": schema_id or "",
                "evidence_ref": evidence_ref or "",
                "source_artifact_id": source_artifact_id or "",
            },
        )
        self.graph.add_entity(dataset_entity)
        self._dataset_nodes[dataset_node_id] = dataset_node_id

        for field_name in fields:
            field_node_id = f"field.source.{_slug(schema_key)}.{_slug(field_name)}"
            self.graph.add_entity(
                ProvenanceEntity(
                    entity_id=field_node_id,
                    entity_type=EntityType.DATASET,
                    label=str(field_name),
                    created_at=_utc_now(),
                    attributes={
                        "lineage_kind": LINEAGE_KIND_SOURCE_FIELD,
                        "field": str(field_name),
                        "schema_id": schema_id or "",
                        "connector_id": connector_id,
                        "dataset_id": dataset_id,
                        "dataset_node_id": dataset_node_id,
                        "evidence_ref": evidence_ref or "",
                    },
                )
            )
            self.graph.add_derivation(field_node_id, dataset_node_id)
            self._current_field_nodes[str(field_name)] = field_node_id

        return dataset_node_id

    def attach_evidence_bundle(
        self,
        evidence_ref: str,
        *,
        artifact_id: str | None = None,
        source_node_ids: Sequence[str] | None = None,
    ) -> str:
        node_id = f"evidence.bundle.{_slug(evidence_ref)}"
        if node_id not in self._evidence_nodes:
            self.graph.add_entity(
                ProvenanceEntity(
                    entity_id=node_id,
                    entity_type=EntityType.SNAPSHOT,
                    label=f"Evidence {evidence_ref}",
                    created_at=_utc_now(),
                    attributes={
                        "lineage_kind": LINEAGE_KIND_EVIDENCE_BUNDLE,
                        "evidence_ref": evidence_ref,
                        "artifact_id": artifact_id or "",
                    },
                )
            )
            self._evidence_nodes[evidence_ref] = node_id
            for source_id in source_node_ids or ():
                self.graph.add_derivation(node_id, source_id)
        return node_id

    def record_transform_stage(
        self,
        *,
        stage_name: str,
        started_at: datetime,
        completed_at: datetime,
        input_columns: Sequence[str],
        output_columns: Sequence[str],
        parameters: dict[str, Any],
        evidence_refs: Sequence[Any] | None = None,
    ) -> tuple[str, dict[str, str]]:
        signature = _stable_suffix(stage_name, parameters, tuple(input_columns), tuple(output_columns))
        activity_id = f"transform.{_slug(stage_name)}.{signature}"
        self.graph.add_activity(
            ProvenanceActivity(
                activity_id=activity_id,
                activity_type=_activity_type_for_stage(stage_name),
                label=stage_name,
                started_at=started_at,
                ended_at=completed_at,
                parameters={
                    "lineage_kind": "transform_stage",
                    "stage_name": stage_name,
                    "duration_ms": max(
                        int((completed_at - started_at).total_seconds() * 1000),
                        0,
                    ),
                    **parameters,
                },
            )
        )

        upstream_candidates = self._resolve_upstream_columns(
            stage_name=stage_name,
            input_columns=input_columns,
            output_columns=output_columns,
            parameters=parameters,
        )

        output_nodes: dict[str, str] = {}
        for output_column in output_columns:
            output_node_id = f"field.transform.{signature}.{_slug(output_column)}"
            self.graph.add_entity(
                ProvenanceEntity(
                    entity_id=output_node_id,
                    entity_type=EntityType.DATASET,
                    label=str(output_column),
                    created_at=completed_at,
                    attributes={
                        "lineage_kind": LINEAGE_KIND_TRANSFORM_FIELD,
                        "field": str(output_column),
                        "stage_name": stage_name,
                        "transform_activity_id": activity_id,
                    },
                )
            )

            source_columns = upstream_candidates.get(str(output_column), list(input_columns))
            for source_column in source_columns:
                source_node_id = self._resolve_field_node(source_column)
                if source_node_id is None:
                    continue
                self.graph.add_usage(activity_id, source_node_id)
                self.graph.add_derivation(output_node_id, source_node_id)

            for evidence_ref in evidence_refs or ():
                evidence_text = str(evidence_ref).strip()
                if not evidence_text:
                    continue
                evidence_node_id = self.attach_evidence_bundle(evidence_text)
                self.graph.add_derivation(output_node_id, evidence_node_id)

            self.graph.add_generation(output_node_id, activity_id)
            output_nodes[str(output_column)] = output_node_id

        self._current_field_nodes = dict(output_nodes)
        return activity_id, output_nodes

    def record_materialized_column(
        self,
        *,
        table_name: str,
        column_name: str,
        source_columns: Sequence[str],
        segment_id: str | None = None,
        evidence_ref: str | None = None,
    ) -> str:
        node_id = f"materialized.{_slug(table_name)}.{_slug(column_name)}"
        self.graph.add_entity(
            ProvenanceEntity(
                entity_id=node_id,
                entity_type=EntityType.SNAPSHOT,
                label=f"{table_name}.{column_name}",
                created_at=_utc_now(),
                attributes={
                    "lineage_kind": LINEAGE_KIND_MATERIALIZED_COLUMN,
                    "table": table_name,
                    "column": column_name,
                    "segment_id": segment_id or "",
                    "evidence_ref": evidence_ref or "",
                },
            )
        )
        for source_column in source_columns:
            source_node_id = self._resolve_field_node(source_column)
            if source_node_id is not None:
                self.graph.add_derivation(node_id, source_node_id)
        if segment_id:
            segment_node_id = self._ensure_fact_segment(segment_id)
            self.graph.add_derivation(node_id, segment_node_id)
        if evidence_ref:
            self.graph.add_derivation(node_id, self.attach_evidence_bundle(evidence_ref))
        return node_id

    def record_claim_field(
        self,
        *,
        claim_id: str,
        field_name: str,
        source_columns: Sequence[str],
        evidence_ref: str | None = None,
        world_event_id: str | None = None,
    ) -> str:
        node_id = f"claim.field.{_slug(claim_id)}.{_slug(field_name)}"
        self.graph.add_entity(
            ProvenanceEntity(
                entity_id=node_id,
                entity_type=EntityType.METRIC,
                label=f"{claim_id}.{field_name}",
                created_at=_utc_now(),
                attributes={
                    "lineage_kind": LINEAGE_KIND_CLAIM_FIELD,
                    "claim_id": claim_id,
                    "field": field_name,
                    "evidence_ref": evidence_ref or "",
                    "world_event_id": world_event_id or "",
                },
            )
        )
        for source_column in source_columns:
            source_node_id = self._resolve_field_node(source_column)
            if source_node_id is not None:
                self.graph.add_derivation(node_id, source_node_id)
        if evidence_ref:
            self.graph.add_derivation(node_id, self.attach_evidence_bundle(evidence_ref))
        if world_event_id:
            self.graph.add_derivation(node_id, self._ensure_world_event(world_event_id))
        return node_id

    def record_world_fact(
        self,
        *,
        fact_id: str,
        source_nodes: Sequence[str],
        segment_id: str | None = None,
        world_event_id: str | None = None,
    ) -> str:
        node_id = f"world.fact.{_slug(fact_id)}"
        self.graph.add_entity(
            ProvenanceEntity(
                entity_id=node_id,
                entity_type=EntityType.FACT_SEGMENT,
                label=fact_id,
                created_at=_utc_now(),
                attributes={
                    "lineage_kind": LINEAGE_KIND_WORLD_FACT,
                    "fact_id": fact_id,
                    "segment_id": segment_id or "",
                    "world_event_id": world_event_id or "",
                },
            )
        )
        for source_node in source_nodes:
            resolved = self._resolve_field_node(source_node) or source_node
            self.graph.add_derivation(node_id, resolved)
        if segment_id:
            self.graph.add_derivation(node_id, self._ensure_fact_segment(segment_id))
        if world_event_id:
            self.graph.add_derivation(node_id, self._ensure_world_event(world_event_id))
        return node_id

    def record_query_result_field(
        self,
        *,
        query_id: str,
        field_name: str,
        source_nodes: Sequence[str],
        query_hash: str | None = None,
    ) -> str:
        node_id = f"query.result.{_slug(query_id)}.{_slug(field_name)}"
        self.graph.add_entity(
            ProvenanceEntity(
                entity_id=node_id,
                entity_type=EntityType.QUERY_RESULT,
                label=f"{query_id}.{field_name}",
                created_at=_utc_now(),
                attributes={
                    "lineage_kind": LINEAGE_KIND_QUERY_RESULT_FIELD,
                    "query_id": query_id,
                    "field": field_name,
                    "query_hash": query_hash or "",
                },
            )
        )
        for source_node in source_nodes:
            resolved = self._resolve_field_node(source_node) or source_node
            self.graph.add_derivation(node_id, resolved)
        return node_id

    def _ensure_fact_segment(self, segment_id: str) -> str:
        existing = self._segment_nodes.get(segment_id)
        if existing is not None:
            return existing
        node_id = f"fact.segment.{_slug(segment_id)}"
        self.graph.add_entity(
            ProvenanceEntity(
                entity_id=node_id,
                entity_type=EntityType.FACT_SEGMENT,
                label=segment_id,
                created_at=_utc_now(),
                attributes={
                    "lineage_kind": LINEAGE_KIND_FACT_SEGMENT,
                    "segment_id": segment_id,
                },
            )
        )
        self._segment_nodes[segment_id] = node_id
        return node_id

    def _ensure_world_event(self, world_event_id: str) -> str:
        existing = self._event_nodes.get(world_event_id)
        if existing is not None:
            return existing
        node_id = f"world.event.{_slug(world_event_id)}"
        self.graph.add_entity(
            ProvenanceEntity(
                entity_id=node_id,
                entity_type=EntityType.SNAPSHOT,
                label=world_event_id,
                created_at=_utc_now(),
                attributes={
                    "lineage_kind": LINEAGE_KIND_WORLD_EVENT,
                    "world_event_id": world_event_id,
                },
            )
        )
        self._event_nodes[world_event_id] = node_id
        return node_id

    def _resolve_field_node(self, field_or_node_id: str) -> str | None:
        if field_or_node_id in self.graph.entities:
            return field_or_node_id
        return self._current_field_nodes.get(str(field_or_node_id))

    def _resolve_upstream_columns(
        self,
        *,
        stage_name: str,
        input_columns: Sequence[str],
        output_columns: Sequence[str],
        parameters: dict[str, Any],
    ) -> dict[str, list[str]]:
        mapping: dict[str, list[str]] = {}
        field_mappings = parameters.get("field_mappings")
        reverse_mapping = (
            {str(target): [str(source)] for source, target in field_mappings.items()}
            if isinstance(field_mappings, dict)
            else {}
        )
        group_by = [str(item) for item in parameters.get("group_by", []) if item is not None]
        aggregations = parameters.get("aggregations")

        for column in output_columns:
            column_text = str(column)
            if column_text in reverse_mapping:
                mapping[column_text] = reverse_mapping[column_text]
                continue
            if column_text in input_columns:
                mapping[column_text] = [column_text]
                continue
            if column_text in group_by:
                mapping[column_text] = [column_text]
                continue
            if isinstance(aggregations, dict) and column_text in aggregations and column_text in input_columns:
                mapping[column_text] = [column_text]
                continue
            if stage_name == "filter" or stage_name == "validate":
                mapping[column_text] = [column_text] if column_text in input_columns else list(input_columns)
                continue
            if stage_name.startswith("harmonize_") or stage_name.startswith("impute_"):
                mapping[column_text] = [column_text] if column_text in input_columns else list(input_columns)
                continue
            mapping[column_text] = list(input_columns)
        return mapping


def _walk_graph(
    graph: ProvenanceCoreGraph,
    *,
    roots: Sequence[str],
    direction: str,
    max_depth: int,
) -> tuple[set[str], set[tuple[str, str, str]]]:
    visited: set[str] = set()
    kept_edges: set[tuple[str, str, str]] = set()
    frontier = set(roots)
    depth = 0

    while frontier and depth < max_depth:
        next_frontier: set[str] = set()
        for node_id in frontier:
            if node_id in visited:
                continue
            visited.add(node_id)
            for edge in graph.edges:
                edge_key = (edge.source_id, edge.target_id, edge.relation.value)
                if direction == "upstream":
                    if edge.relation == RelationType.WAS_DERIVED_FROM and edge.source_id == node_id:
                        kept_edges.add(edge_key)
                        next_frontier.add(edge.target_id)
                    elif edge.relation == RelationType.WAS_GENERATED_BY and edge.source_id == node_id:
                        kept_edges.add(edge_key)
                        next_frontier.add(edge.target_id)
                    elif edge.relation == RelationType.USED and edge.source_id == node_id:
                        kept_edges.add(edge_key)
                        next_frontier.add(edge.target_id)
                else:
                    if edge.relation == RelationType.WAS_DERIVED_FROM and edge.target_id == node_id:
                        kept_edges.add(edge_key)
                        next_frontier.add(edge.source_id)
                    elif edge.relation == RelationType.WAS_GENERATED_BY and edge.target_id == node_id:
                        kept_edges.add(edge_key)
                        next_frontier.add(edge.source_id)
                    elif edge.relation == RelationType.USED and edge.target_id == node_id:
                        kept_edges.add(edge_key)
                        next_frontier.add(edge.source_id)
        frontier = next_frontier - visited
        depth += 1
    return visited, kept_edges


def _build_trace(
    graph: ProvenanceCoreGraph,
    *,
    root_id: str,
    visited: Iterable[str],
    edges: Iterable[tuple[str, str, str]],
) -> LineageTrace:
    node_snapshots = tuple(
        sorted(
            (
                LineageNodeSnapshot(
                    node_id=node_id,
                    label=_node_label(graph, node_id),
                    kind=_node_kind(graph, node_id),
                    attributes=_node_attributes(graph, node_id),
                )
                for node_id in set(visited)
            ),
            key=lambda item: item.node_id,
        )
    )
    return LineageTrace(
        root_id=root_id,
        nodes=node_snapshots,
        edges=tuple(sorted(set(edges))),
    )


def trace_value_origin(
    graph: ProvenanceCoreGraph,
    node_id: str,
    *,
    max_depth: int = 64,
) -> LineageTrace:
    """Trace one node's upstream lineage through derivation/generation/use edges."""
    visited, edges = _walk_graph(
        graph,
        roots=[node_id],
        direction="upstream",
        max_depth=max_depth,
    )
    return _build_trace(graph, root_id=node_id, visited=visited, edges=edges)


def trace_column_lineage(
    graph: ProvenanceCoreGraph,
    column_ref: str,
    *,
    max_depth: int = 64,
) -> LineageTrace:
    """Trace lineage for one column node id or uniquely resolvable field name."""
    if column_ref in graph.entities:
        return trace_value_origin(graph, column_ref, max_depth=max_depth)

    candidates = [
        entity.entity_id
        for entity in graph.entities.values()
        if entity.attributes.get("field") == column_ref
    ]
    if not candidates:
        raise KeyError(f"No lineage column found for reference: {column_ref}")
    root_id = sorted(candidates)[0]
    return trace_value_origin(graph, root_id, max_depth=max_depth)


def trace_claim_origin(
    graph: ProvenanceCoreGraph,
    claim_id: str,
    *,
    field: str | None = None,
    max_depth: int = 64,
) -> LineageTrace:
    """Trace lineage for one claim field or all fields belonging to a claim."""
    roots = []
    if field:
        roots = [f"claim.field.{_slug(claim_id)}.{_slug(field)}"]
    else:
        prefix = f"claim.field.{_slug(claim_id)}."
        roots = sorted(node_id for node_id in graph.entities if node_id.startswith(prefix))
    if not roots:
        raise KeyError(f"No claim lineage found for claim_id={claim_id!r}")
    visited, edges = _walk_graph(
        graph,
        roots=roots,
        direction="upstream",
        max_depth=max_depth,
    )
    root_id = roots[0] if len(roots) == 1 else f"claim.{_slug(claim_id)}"
    return _build_trace(graph, root_id=root_id, visited=visited, edges=edges)


def impact_analysis(
    graph: ProvenanceCoreGraph,
    source_schema_id: str,
    field: str,
    *,
    max_depth: int = 64,
) -> ImpactAnalysis:
    """Return downstream impact sets for one source schema field."""
    roots = [
        entity.entity_id
        for entity in graph.entities.values()
        if entity.attributes.get("lineage_kind") == LINEAGE_KIND_SOURCE_FIELD
        and entity.attributes.get("schema_id") == source_schema_id
        and entity.attributes.get("field") == field
    ]
    if not roots:
        raise KeyError(
            f"No source field lineage found for schema_id={source_schema_id!r}, field={field!r}"
        )
    root_id = sorted(roots)[0]
    visited, edges = _walk_graph(
        graph,
        roots=[root_id],
        direction="downstream",
        max_depth=max_depth,
    )
    nodes = tuple(
        sorted(
            (
                LineageNodeSnapshot(
                    node_id=node_id,
                    label=_node_label(graph, node_id),
                    kind=_node_kind(graph, node_id),
                    attributes=_node_attributes(graph, node_id),
                )
                for node_id in visited
            ),
            key=lambda item: item.node_id,
        )
    )

    def _ids(kind: str) -> tuple[str, ...]:
        return tuple(sorted(node.node_id for node in nodes if node.kind == kind and node.node_id != root_id))

    return ImpactAnalysis(
        root_id=root_id,
        impacted_nodes=nodes,
        materialized_columns=_ids(LINEAGE_KIND_MATERIALIZED_COLUMN),
        claim_fields=_ids(LINEAGE_KIND_CLAIM_FIELD),
        query_result_fields=_ids(LINEAGE_KIND_QUERY_RESULT_FIELD),
        world_facts=_ids(LINEAGE_KIND_WORLD_FACT),
        world_events=_ids(LINEAGE_KIND_WORLD_EVENT),
    )


def export_openlineage_json(
    graph: ProvenanceCoreGraph,
    *,
    namespace: str = "polisyos.fabric",
) -> dict[str, Any]:
    """Export a provenance graph into an OpenLineage-shaped event payload."""
    input_entities = []
    output_entities = []
    seen_inputs: set[str] = set()
    seen_outputs: set[str] = set()

    for edge in graph.edges:
        if edge.relation == RelationType.USED and edge.target_id in graph.entities:
            entity = graph.entities[edge.target_id]
            if entity.entity_id not in seen_inputs:
                seen_inputs.add(entity.entity_id)
                input_entities.append(_openlineage_dataset(graph, entity, namespace))
        elif edge.relation == RelationType.WAS_GENERATED_BY and edge.source_id in graph.entities:
            entity = graph.entities[edge.source_id]
            if entity.entity_id not in seen_outputs:
                seen_outputs.add(entity.entity_id)
                output_entities.append(_openlineage_dataset(graph, entity, namespace))

    return {
        "eventType": "COMPLETE",
        "eventTime": graph.created_at.isoformat(),
        "producer": "https://polisyos.io/fabric/openlineage",
        "schemaURL": "https://openlineage.io/spec/1-0-0/OpenLineage.json",
        "run": {
            "runId": graph.compute_stable_id(),
            "facets": {
                "polisyosProvenance": {
                    "_producer": "https://polisyos.io/fabric",
                    "_schemaURL": "https://polisyos.io/schema/fabric-openlineage/1.0",
                    "graphId": graph.graph_id,
                    "nodeCount": len(graph.entities) + len(graph.activities) + len(graph.agents),
                    "edgeCount": len(graph.edges),
                }
            },
        },
        "job": {
            "namespace": namespace,
            "name": graph.graph_id,
        },
        "inputs": input_entities,
        "outputs": output_entities,
    }


def _openlineage_dataset(
    graph: ProvenanceCoreGraph,
    entity: ProvenanceEntity,
    namespace: str,
) -> dict[str, Any]:
    attrs = dict(entity.attributes)
    return {
        "namespace": attrs.get("connector_id") or namespace,
        "name": entity.label,
        "facets": {
            "schema": {
                "_producer": "https://polisyos.io/fabric",
                "_schemaURL": "https://polisyos.io/schema/fabric-openlineage-dataset/1.0",
                "fields": [
                    {
                        "name": str(attrs.get("field") or entity.label),
                        "type": str(attrs.get("lineage_kind") or entity.entity_type.value),
                    }
                ],
            },
            "polisyosEntity": {
                "_producer": "https://polisyos.io/fabric",
                "_schemaURL": "https://polisyos.io/schema/fabric-openlineage-entity/1.0",
                "entityId": entity.entity_id,
                "lineageKind": attrs.get("lineage_kind") or entity.entity_type.value,
            },
        },
    }


def export_visualization_graph(graph: ProvenanceCoreGraph) -> dict[str, Any]:
    """Export a visualization-friendly node/edge graph without runtime dependencies."""
    nodes = [
        {
            "id": node_id,
            "label": _node_label(graph, node_id),
            "kind": _node_kind(graph, node_id),
            "attributes": _node_attributes(graph, node_id),
        }
        for node_id in sorted(
            set(graph.entities) | set(graph.activities) | set(graph.agents)
        )
    ]
    edges = [
        {
            "source": edge.source_id,
            "target": edge.target_id,
            "relation": edge.relation.value,
        }
        for edge in sorted(graph.edges, key=lambda item: item.to_tuple())
    ]
    return {
        "graph_id": graph.graph_id,
        "stable_id": graph.compute_stable_id(),
        "nodes": nodes,
        "edges": edges,
    }
