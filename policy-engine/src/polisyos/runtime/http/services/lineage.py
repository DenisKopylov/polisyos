"""Resolve artifact and value provenance into runtime lineage response DTOs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from time import perf_counter
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.graph import NodeStatus, resolve_dependency_graph
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.canon import content_hash, from_canonical_bytes
from polisyos.core.contracts.runtime import (
    ArtifactLineageEdge,
    ArtifactLineageNode,
    ArtifactLineageView,
    LineageCompactSummaryItem,
    LineageExportLinks,
    LineageGraphEdge,
    LineageGraphNode,
    LineageGraphView,
    LineageRef,
    LineageSummaryKind,
    QuantityCoverageEntry,
    QuantityCoverageSummary,
    QuantityValue,
    TemporalRef,
    TemporalScope,
    UnitRef,
)
from polisyos.fabric.decision_data import (
    FabricDecisionData,
    FabricDecisionDataCoverage,
    SourceContractRef,
    coverage_from_decision_data,
    from_runtime_quantities,
)

if TYPE_CHECKING:
    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.fabric.provenance.lineage import LineageTrace
    from polisyos.runtime.http.services.run_index import IndexedRunRecord


class LineageService:
    """Build bounded upstream dependency graphs from CAS manifests.

    Traversal is capped by `default_max_depth` and `default_max_nodes` to keep
    API responses predictable. Missing or corrupted dependencies are surfaced in
    the returned `ArtifactLineageView` rather than raised as hard failures.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        default_max_depth: int = 64,
        default_max_nodes: int = 2000,
        default_timeout_seconds: float = 1.5,
        traversal_batch_size: int = 128,
    ) -> None:
        self._store = store
        self._default_max_depth = max(default_max_depth, 1)
        self._default_max_nodes = max(default_max_nodes, 1)
        self._default_timeout_seconds = max(default_timeout_seconds, 0.01)
        self._traversal_batch_size = max(traversal_batch_size, 1)

    def build_for_artifact_ids(
        self,
        artifact_ids: list[ArtifactID],
        *,
        max_depth: int | None = None,
        max_nodes: int | None = None,
        timeout_seconds: float | None = None,
    ) -> ArtifactLineageView:
        """Return a merged lineage graph for one or more root artifacts."""
        if not artifact_ids:
            return ArtifactLineageView(root_artifact_ids=[])

        depth_limit = max_depth if max_depth is not None else self._default_max_depth
        node_limit = max_nodes if max_nodes is not None else self._default_max_nodes
        timeout_budget = (
            max(float(timeout_seconds), 0.01)
            if timeout_seconds is not None
            else self._default_timeout_seconds
        )

        node_map: dict[str, ArtifactLineageNode] = {}
        edge_map: dict[tuple[str, str, str], ArtifactLineageEdge] = {}
        missing_ids: set[str] = set()
        corrupted_ids: set[str] = set()
        is_complete = True

        for root_id in artifact_ids:
            graph = resolve_dependency_graph(
                self._store,
                root_id,
                max_depth=depth_limit,
                max_nodes=node_limit,
                verify_integrity=True,
                timeout_seconds=timeout_budget,
                batch_size=self._traversal_batch_size,
            )
            if graph.timed_out or not graph.is_complete:
                is_complete = False

            for node in graph.nodes.values():
                artifact_id = str(node.artifact_id)
                status = node.status.value
                existing = node_map.get(artifact_id)
                candidate = ArtifactLineageNode(
                    artifact_id=artifact_id,
                    role=node.role,
                    kind=node.kind,
                    status=status,
                    byte_size=max(int(node.byte_size), 0),
                    depth=max(int(node.depth), 0),
                )
                if existing is None:
                    node_map[artifact_id] = candidate
                else:
                    node_map[artifact_id] = _merge_nodes(existing, candidate)

                if node.status == NodeStatus.CORRUPTED:
                    corrupted_ids.add(artifact_id)
                    is_complete = False
                elif node.status != NodeStatus.PRESENT:
                    missing_ids.add(artifact_id)
                    is_complete = False

            for edge in graph.edges:
                key = (str(edge.parent_id), str(edge.child_id), edge.role)
                if key not in edge_map:
                    edge_map[key] = ArtifactLineageEdge(
                        parent_artifact_id=key[0],
                        child_artifact_id=key[1],
                        role=key[2],
                    )

        nodes = sorted(node_map.values(), key=lambda item: (item.depth, item.artifact_id))
        edges = sorted(
            edge_map.values(),
            key=lambda item: (item.parent_artifact_id, item.child_artifact_id, item.role),
        )
        total_size = sum(node.byte_size for node in nodes)

        return ArtifactLineageView(
            root_artifact_ids=[str(item) for item in artifact_ids],
            total_nodes=len(nodes),
            total_edges=len(edges),
            total_size_bytes=total_size,
            is_complete=is_complete,
            missing_artifact_ids=sorted(missing_ids),
            corrupted_artifact_ids=sorted(corrupted_ids),
            nodes=nodes,
            edges=edges,
        )

    def build_runtime_lineage(self, lineage_id: str) -> LineageGraphView:
        """Return a compact + full runtime lineage graph for one lineage id."""
        artifact_id = _parse_artifact_lineage_id(lineage_id)
        if artifact_id is not None and self._store.has(artifact_id):
            artifact_view = self.build_for_artifact_ids([artifact_id])
            return _artifact_lineage_to_runtime_view(
                lineage_id=lineage_id,
                artifact_view=artifact_view,
            )

        return _untraced_lineage_view(
            lineage_id=lineage_id,
            reason_code="lineage_id_not_resolved",
            tracking_issue="policyos://quantity-coverage/unresolved-lineage",
        )

    def build_runtime_lineage_batch(self, lineage_ids: list[str]) -> list[LineageGraphView]:
        """Return runtime lineage graphs preserving request order."""
        resolved: dict[str, LineageGraphView] = {}
        for lineage_id in lineage_ids:
            if lineage_id not in resolved:
                resolved[lineage_id] = self.build_runtime_lineage(lineage_id)
        return [resolved[lineage_id] for lineage_id in lineage_ids]

    def build_from_fabric_trace(
        self,
        trace: LineageTrace,
        *,
        lineage_id: str | None = None,
    ) -> LineageGraphView:
        """Project a Fabric `LineageTrace` into the runtime lineage graph contract.

        Runtime HTTP lookups resolve persisted artifact lineage today. This
        adapter is the in-process bridge for Fabric value lineage callers that
        already hold a `trace_value_origin()` / `trace_claim_origin()` result.
        """
        resolved_id = lineage_id or f"fabric:{trace.root_id}"
        nodes = [
            LineageGraphNode(
                id=str(node.node_id),
                kind=str(node.kind or "unknown"),
                label=str(node.label or node.node_id),
                metadata=dict(getattr(node, "attributes", {}) or {}),
            )
            for node in getattr(trace, "nodes", ())
        ]
        edges = [
            LineageGraphEdge(
                source_id=str(source_id),
                target_id=str(target_id),
                relation=str(relation),
            )
            for source_id, target_id, relation in getattr(trace, "edges", ())
        ]
        payload_for_hash = {
            "lineage_id": resolved_id,
            "nodes": [node.model_dump(mode="json") for node in nodes],
            "edges": [edge.model_dump(mode="json") for edge in edges],
        }
        return LineageGraphView(
            id=resolved_id,
            status="verified" if nodes else "untraced",
            hash=content_hash(json.dumps(payload_for_hash, sort_keys=True), prefix=True),
            freshness="current" if nodes else "unknown",
            compact_summary=_compact_summary_from_runtime_nodes(nodes, root_id=trace.root_id),
            nodes=nodes,
            edges=edges,
            exports=_export_links(resolved_id),
            metadata={
                "source": "fabric.lineage_trace",
                "root_id": str(trace.root_id),
                "total_nodes": len(nodes),
                "total_edges": len(edges),
            },
        )

    def export_runtime_lineage(self, lineage_id: str, *, format_name: str) -> dict[str, Any]:
        """Return a best-effort external lineage representation for one runtime lineage id."""
        graph = self.build_runtime_lineage(lineage_id)
        if format_name == "openlineage":
            inputs = [
                {"namespace": "polisyos.lineage", "name": node.id}
                for node in graph.nodes
                if node.id != graph.id
            ]
            outputs = [{"namespace": "polisyos.lineage", "name": graph.id}]
            return {
                "eventType": "COMPLETE",
                "producer": "polisyos-runtime-api",
                "run": {"runId": graph.id},
                "job": {"namespace": "polisyos.runtime.lineage", "name": graph.id},
                "inputs": inputs,
                "outputs": outputs,
                "facets": {
                    "polisyos_status": {
                        "_producer": "polisyos-runtime-api",
                        "_schemaURL": "https://polisyos.dev/schemas/lineage-status",
                        "status": graph.status,
                        "freshness": graph.freshness,
                        "hash": graph.hash,
                    }
                },
            }
        if format_name == "prov":
            return {
                "prefix": {"polisyos": "https://polisyos.dev/prov/"},
                "entity": {
                    node.id: {
                        "prov:label": node.label,
                        "polisyos:kind": node.kind,
                        **node.metadata,
                    }
                    for node in graph.nodes
                },
                "wasDerivedFrom": [
                    {
                        "generatedEntity": edge.target_id,
                        "usedEntity": edge.source_id,
                        "polisyos:relation": edge.relation,
                    }
                    for edge in graph.edges
                ],
            }
        raise ValueError(f"Unsupported lineage export format: {format_name}")

    def build_quantity_inventory_for_run(
        self,
        run: IndexedRunRecord,
    ) -> tuple[list[QuantityValue], QuantityCoverageSummary, list[QuantityCoverageEntry]]:
        """Build a class-aware quantity inventory for one indexed run."""
        quantities: list[QuantityValue] = []
        entries: list[QuantityCoverageEntry] = []
        decision_packet_ref = run.decision_packet_ref

        if decision_packet_ref is not None:
            artifact_id = ArtifactID.model_validate(str(decision_packet_ref.artifact_id))
            payload = _load_json_artifact(self._store, artifact_id)
            if isinstance(payload, dict):
                quantities.extend(
                    _decision_packet_quantities(
                        payload,
                        artifact_id=str(artifact_id),
                        run_started_at=run.details.started_at,
                        run_finished_at=run.details.finished_at,
                    )
                )

        telemetry_lineage = _untraced_ref(
            reason_code="runtime_telemetry_not_decision_bearing",
            tracking_issue="policyos://quantity-coverage/runtime-telemetry",
            lineage_id=f"run:{run.run_id}:telemetry",
        )
        if run.details.duration_ms is not None:
            quantities.append(
                QuantityValue(
                    point=float(run.details.duration_ms),
                    unit=UnitRef(code="ms", system="ucum", display="ms"),
                    metric_id="duration_ms",
                    label="Run duration",
                    lineage=telemetry_lineage,
                    time=_temporal_ref(run.details.started_at, run.details.finished_at),
                    quantity_class="telemetry",
                )
            )
        quantities.append(
            QuantityValue(
                point=float(run.summary.root_artifact_count),
                unit=UnitRef(code="1", system="ucum", display="count"),
                metric_id="root_artifact_count",
                label="Root artifact count",
                lineage=telemetry_lineage,
                time=_temporal_ref(run.details.started_at, run.details.finished_at),
                quantity_class="telemetry",
            )
        )

        for quantity in quantities:
            entries.append(_coverage_entry(quantity))

        return quantities, _coverage_summary(entries), entries

    def build_fabric_decision_data_for_run(
        self,
        run: IndexedRunRecord,
        *,
        temporal_scope: TemporalScope | None = None,
    ) -> tuple[list[FabricDecisionData], FabricDecisionDataCoverage]:
        """Build Fabric trust envelopes for decision quantities in one run."""
        quantities, coverage, _entries = self.build_quantity_inventory_for_run(run)
        return self.build_fabric_decision_data_for_quantities(
            quantities,
            coverage,
            temporal_scope=temporal_scope,
        )

    def build_fabric_decision_data_for_quantities(
        self,
        quantities: list[QuantityValue],
        coverage: QuantityCoverageSummary,
        *,
        temporal_scope: TemporalScope | None = None,
    ) -> tuple[list[FabricDecisionData], FabricDecisionDataCoverage]:
        """Project Runtime QuantityValue rows into Fabric trust envelopes."""
        decision_data = from_runtime_quantities(
            quantities,
            source_contract=SourceContractRef(
                id="runtime.decision_packet.generic",
                version="0.1.0",
            ),
            temporal_scope=temporal_scope,
        )
        return (
            decision_data,
            coverage_from_decision_data(
                decision_data,
                telemetry=coverage.telemetry,
                layout=coverage.layout,
                debug=coverage.debug,
            ),
        )

    def benchmark_compact_lineage_batch(self, lineage_ids: list[str]) -> dict[str, Any]:
        """Measure local compact lineage batch lookup latency for acceptance tests."""
        started = perf_counter()
        lineages = self.build_runtime_lineage_batch(lineage_ids)
        elapsed_ms = (perf_counter() - started) * 1000.0
        return {
            "count": len(lineage_ids),
            "unique_count": len(set(lineage_ids)),
            "p95_ms": elapsed_ms,
            "status_counts": {
                status: sum(lineage.status == status for lineage in lineages)
                for status in sorted({lineage.status for lineage in lineages})
            },
        }


def _merge_nodes(lhs: ArtifactLineageNode, rhs: ArtifactLineageNode) -> ArtifactLineageNode:
    best_status = lhs.status
    if lhs.status != "present" and rhs.status == "present":
        best_status = rhs.status
    elif lhs.status != "present" and rhs.status != "present":
        best_status = min(lhs.status, rhs.status)

    return ArtifactLineageNode(
        artifact_id=lhs.artifact_id,
        role=lhs.role or rhs.role,
        kind=lhs.kind or rhs.kind,
        status=best_status,
        byte_size=max(lhs.byte_size, rhs.byte_size),
        depth=min(lhs.depth, rhs.depth),
    )


def _parse_artifact_lineage_id(lineage_id: str) -> ArtifactID | None:
    candidate = lineage_id.removeprefix("artifact:")
    try:
        return ArtifactID.model_validate(candidate)
    except (TypeError, ValueError):
        return None


def _artifact_lineage_to_runtime_view(
    *,
    lineage_id: str,
    artifact_view: ArtifactLineageView,
) -> LineageGraphView:
    status = "verified" if artifact_view.is_complete else "disputed"
    freshness = "current" if artifact_view.is_complete else "stale"
    nodes = [
        LineageGraphNode(
            id=node.artifact_id,
            kind=node.kind or "artifact",
            label=node.kind or _short_id(node.artifact_id),
            metadata={
                "role": node.role,
                "status": node.status,
                "byte_size": node.byte_size,
                "depth": node.depth,
            },
        )
        for node in artifact_view.nodes
    ]
    edges = [
        LineageGraphEdge(
            source_id=edge.parent_artifact_id,
            target_id=edge.child_artifact_id,
            relation=edge.role,
        )
        for edge in artifact_view.edges
    ]
    payload_for_hash = {
        "lineage_id": lineage_id,
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "edges": [edge.model_dump(mode="json") for edge in edges],
    }
    compact_summary = _compact_summary_from_artifact_view(artifact_view)
    return LineageGraphView(
        id=lineage_id,
        status=status,
        hash=content_hash(json.dumps(payload_for_hash, sort_keys=True), prefix=True),
        freshness=freshness,
        compact_summary=compact_summary,
        nodes=nodes,
        edges=edges,
        exports=_export_links(lineage_id),
        metadata={
            "root_artifact_ids": list(artifact_view.root_artifact_ids),
            "total_nodes": artifact_view.total_nodes,
            "total_edges": artifact_view.total_edges,
            "total_size_bytes": artifact_view.total_size_bytes,
            "missing_artifact_ids": list(artifact_view.missing_artifact_ids),
            "corrupted_artifact_ids": list(artifact_view.corrupted_artifact_ids),
        },
    )


def _compact_summary_from_artifact_view(
    artifact_view: ArtifactLineageView,
) -> list[LineageCompactSummaryItem]:
    if not artifact_view.nodes:
        return [LineageCompactSummaryItem(kind="unknown", label="No lineage nodes")]

    deepest = sorted(
        artifact_view.nodes,
        key=lambda node: (-node.depth, node.artifact_id),
    )[:3]
    roots = {
        artifact_id
        for artifact_id in artifact_view.root_artifact_ids
        if any(node.artifact_id == artifact_id for node in artifact_view.nodes)
    }
    items: list[LineageCompactSummaryItem] = []
    for node in reversed(deepest):
        kind = "source" if node.depth > 0 else "artifact"
        items.append(
            LineageCompactSummaryItem(
                kind=kind,
                label=node.kind or _short_id(node.artifact_id),
                id=node.artifact_id,
            )
        )
    for root_id in sorted(roots):
        if any(item.id == root_id for item in items):
            continue
        root_node = next(node for node in artifact_view.nodes if node.artifact_id == root_id)
        items.append(
            LineageCompactSummaryItem(
                kind="result",
                label=root_node.kind or _short_id(root_id),
                id=root_id,
            )
        )
    return items[:4]


def _compact_summary_from_runtime_nodes(
    nodes: list[LineageGraphNode],
    *,
    root_id: str,
) -> list[LineageCompactSummaryItem]:
    if not nodes:
        return [LineageCompactSummaryItem(kind="unknown", label="No lineage nodes")]
    root = next((node for node in nodes if node.id == root_id), nodes[-1])
    sources = [
        node
        for node in nodes
        if node.kind in {"source_dataset", "source_field", "dataset"} and node.id != root.id
    ][:2]
    transforms = [
        node
        for node in nodes
        if node.kind in {"transform_stage", "transform_field", "materialized_column"}
        and node.id != root.id
    ][:1]
    ordered = [*sources, *transforms, root]
    if not sources and not transforms:
        ordered = nodes[:3]
        if root not in ordered:
            ordered.append(root)
    return [
        LineageCompactSummaryItem(
            kind=_summary_kind_for_node(node),
            label=node.label,
            id=node.id,
        )
        for node in ordered[:4]
    ]


def _summary_kind_for_node(node: LineageGraphNode) -> LineageSummaryKind:
    if node.kind in {"source_dataset", "source_field", "dataset"}:
        return "source"
    if node.kind in {"transform_stage", "transform_field", "materialized_column"}:
        return "transform"
    if node.kind in {"agent", "model"}:
        return node.kind
    if node.kind in {"claim_field", "query_result_field", "world_fact"}:
        return "result"
    return "unknown"


def _untraced_lineage_view(
    *,
    lineage_id: str,
    reason_code: str,
    tracking_issue: str,
) -> LineageGraphView:
    return LineageGraphView(
        id=lineage_id,
        status="untraced",
        freshness="unknown",
        compact_summary=[
            LineageCompactSummaryItem(kind="unknown", label="Untraced quantity", id=lineage_id)
        ],
        nodes=[
            LineageGraphNode(
                id=lineage_id,
                kind="untraced",
                label="Untraced quantity",
                metadata={
                    "reason_code": reason_code,
                    "tracking_issue": tracking_issue,
                },
            )
        ],
        edges=[],
        exports=_export_links(lineage_id),
        metadata={
            "reason_code": reason_code,
            "tracking_issue": tracking_issue,
        },
    )


def _export_links(lineage_id: str) -> LineageExportLinks:
    return LineageExportLinks(
        openlineage=f"/api/v1/lineage/{lineage_id}/export/openlineage",
        prov=f"/api/v1/lineage/{lineage_id}/export/prov",
    )


def _untraced_ref(
    *,
    reason_code: str,
    tracking_issue: str,
    lineage_id: str = "untraced",
) -> LineageRef:
    return LineageRef(
        id=lineage_id,
        status="untraced",
        freshness="unknown",
        reason_code=reason_code,
        tracking_issue=tracking_issue,
        summary={"reason": reason_code},
        compact_summary=[
            LineageCompactSummaryItem(kind="unknown", label="Untraced", id=lineage_id)
        ],
    )


def _verified_artifact_ref(artifact_id: str, *, label: str) -> LineageRef:
    return LineageRef(
        id=f"artifact:{artifact_id}",
        status="verified",
        freshness="current",
        summary={"source": label, "artifact": artifact_id},
        compact_summary=[
            LineageCompactSummaryItem(kind="source", label="Decision packet", id=artifact_id),
            LineageCompactSummaryItem(kind="result", label=label, id=f"artifact:{artifact_id}"),
        ],
    )


def _load_json_artifact(store: ArtifactStore, artifact_id: ArtifactID) -> object | None:
    try:
        return from_canonical_bytes(store.get_bytes(artifact_id))
    except (FileNotFoundError, TypeError, ValueError):
        return None


def _decision_packet_quantities(
    payload: dict[str, Any],
    *,
    artifact_id: str,
    run_started_at: datetime | None,
    run_finished_at: datetime | None,
) -> list[QuantityValue]:
    quantities: list[QuantityValue] = []
    temporal = _temporal_ref(run_started_at, run_finished_at)

    simulation_results = payload.get("simulation_results")
    if isinstance(simulation_results, dict):
        for metric_id, value in sorted(simulation_results.items()):
            if _is_number(value):
                metric_text = str(metric_id)
                quantities.append(
                    _quantity(
                        point=float(value),
                        metric_id=metric_text,
                        label=metric_text,
                        path=f"decision_packet.simulation_results.{metric_text}",
                        artifact_id=artifact_id,
                        time=temporal,
                    )
                )

    backtest = payload.get("backtest")
    if isinstance(backtest, dict):
        trust_score = backtest.get("trust_score")
        if _is_number(trust_score):
            quantities.append(
                _quantity(
                    point=float(trust_score),
                    metric_id="trust_score",
                    label="Backtest trust score",
                    path="decision_packet.backtest.trust_score",
                    artifact_id=artifact_id,
                    time=temporal,
                )
            )

    comparisons = payload.get("metric_validation_comparison_rows")
    if isinstance(comparisons, list):
        for index, row in enumerate(comparisons):
            if isinstance(row, dict):
                quantities.extend(
                    _metric_comparison_quantities(
                        row,
                        index=index,
                        artifact_id=artifact_id,
                        time=temporal,
                    )
                )

    return quantities


def _metric_comparison_quantities(
    row: dict[str, Any],
    *,
    index: int,
    artifact_id: str,
    time: TemporalRef | None,
) -> list[QuantityValue]:
    metric_id = str(row.get("metric_id") or f"metric_{index}")
    fields = (
        "baseline_value",
        "candidate_value",
        "delta_value",
        "effect_size",
        "p_value",
        "p_adj",
        "alpha",
        "statistic",
    )
    quantities: list[QuantityValue] = []
    for field_name in fields:
        value = row.get(field_name)
        if not _is_number(value):
            continue
        quantities.append(
            _quantity(
                point=float(value),
                metric_id=f"{metric_id}.{field_name}",
                label=f"{metric_id} {field_name}",
                path=(f"decision_packet.metric_validation_comparison_rows[{index}].{field_name}"),
                artifact_id=artifact_id,
                time=time,
            )
        )
    return quantities


def _quantity(
    *,
    point: float,
    metric_id: str,
    label: str,
    path: str,
    artifact_id: str,
    time: TemporalRef | None,
) -> QuantityValue:
    return QuantityValue(
        point=point,
        unit=_unit_for_metric(metric_id),
        metric_id=metric_id,
        label=label,
        lineage=_verified_artifact_ref(artifact_id, label=path),
        time=time,
        quantity_class="decision",
    )


def _unit_for_metric(metric_id: str) -> UnitRef:
    lowered = metric_id.lower()
    if "duration" in lowered or lowered.endswith("_ms"):
        return UnitRef(code="ms", system="ucum", display="ms")
    if "cost" in lowered or "budget" in lowered:
        return UnitRef(code="[USD]", system="ucum", display="USD")
    if any(token in lowered for token in ("count", "nodes", "observations")):
        return UnitRef(code="1", system="ucum", display="count")
    if any(token in lowered for token in ("score", "rate", "risk", "p_value", "alpha")):
        return UnitRef(code="1", system="ucum", display="score")
    return UnitRef(code="1", system="ucum", display="value")


def _temporal_ref(started_at: datetime | None, finished_at: datetime | None) -> TemporalRef | None:
    if started_at is None and finished_at is None:
        return None
    return TemporalRef(
        valid_at=_as_utc(started_at),
        tx_at=_as_utc(finished_at or started_at),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _coverage_entry(quantity: QuantityValue) -> QuantityCoverageEntry:
    return QuantityCoverageEntry(
        path=quantity.lineage.summary.get("source", quantity.metric_id or "quantity"),
        quantity_class=quantity.quantity_class,
        status=quantity.lineage.status,
        lineage_id=quantity.lineage.id,
        metric_id=quantity.metric_id,
        reason_code=quantity.lineage.reason_code,
        tracking_issue=quantity.lineage.tracking_issue,
    )


def _coverage_summary(entries: list[QuantityCoverageEntry]) -> QuantityCoverageSummary:
    return QuantityCoverageSummary(
        total=len(entries),
        decision=sum(entry.quantity_class == "decision" for entry in entries),
        telemetry=sum(entry.quantity_class == "telemetry" for entry in entries),
        layout=sum(entry.quantity_class == "layout" for entry in entries),
        debug=sum(entry.quantity_class == "debug" for entry in entries),
        traced=sum(entry.status != "untraced" for entry in entries),
        untraced=sum(entry.status == "untraced" for entry in entries),
    )


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _short_id(value: str) -> str:
    if len(value) <= 18:
        return value
    return f"{value[:12]}...{value[-6:]}"
