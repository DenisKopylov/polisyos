"""
Evidence aggregation for multi-source composition.

Extends the evidence system to support composite evidence bundles that
track provenance across multiple sources with deterministic identifiers.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.canon import content_hash, to_canonical_bytes
from polisyos.core.contracts.fabric import (
    EvidenceBundle,
    EvidenceStep,
    ProvenanceCoreRefModel,
)
from polisyos.fabric.connectors.federation.types import (
    CompositionStrategy,
    MergeLogEntry,
)
from polisyos.fabric.evidence import persist_provenance_graph
from polisyos.fabric.finite import ensure_probability
from polisyos.fabric.provenance.core import (
    ActivityType,
    AgentType,
    EntityType,
    ProvenanceActivity,
    ProvenanceAgent,
    ProvenanceCoreGraph,
    ProvenanceCoreRef,
    ProvenanceEntity,
)

_DETERMINISTIC_TIMESTAMP = datetime(1970, 1, 1, tzinfo=UTC)


def build_composite_evidence_bundle(
    *,
    source_bundles: list[EvidenceBundle],
    composition_strategy: CompositionStrategy,
    merge_log: list[MergeLogEntry],
    store: FileSystemCAS,
    composed_by: str = "FederationEngine",
    deterministic: bool = True,
    deterministic_seed: str | None = None,
) -> EvidenceBundle:
    """
    Create a composite evidence bundle from multiple source bundles.

    This represents derived data that combines multiple sources.

    Args:
        source_bundles: List of evidence bundles from source data
        composition_strategy: Strategy used for composition
        merge_log: Log of conflict resolutions
        store: CAS store for persisting provenance
        composed_by: Identifier of composition agent
        deterministic: If True, use deterministic provenance timestamps/ids
        deterministic_seed: Optional seed to influence deterministic IDs

    Returns:
        Composite EvidenceBundle with aggregated provenance
    """
    # Collect all source references
    all_source_refs = []
    for bundle in source_bundles:
        all_source_refs.extend(bundle.sources)

    composition_transform = EvidenceStep(
        op=f"compose_{composition_strategy.value}",
        details={
            "strategy": composition_strategy.value,
            "num_sources": len(source_bundles),
            "num_conflicts": len(merge_log),
            "composed_by": composed_by,
        },
    )

    all_transforms = [composition_transform]
    for bundle in source_bundles:
        all_transforms.extend(bundle.transforms)

    composite_prov_ref = _build_composite_provenance(
        source_bundles=source_bundles,
        composition_strategy=composition_strategy,
        merge_log=merge_log,
        store=store,
        composed_by=composed_by,
        deterministic=deterministic,
        deterministic_seed=deterministic_seed,
    )

    prov_model = ProvenanceCoreRefModel(
        graph_id=composite_prov_ref.graph_id,
        stable_id=composite_prov_ref.stable_id,
        artifact_id=composite_prov_ref.artifact_id,
    )

    composite_quality = _aggregate_quality_indicators(
        [b.quality_indicators for b in source_bundles if b.quality_indicators]
    )

    return EvidenceBundle(
        sources=all_source_refs,
        transforms=all_transforms,
        trust_policy_id="federation_composite",
        provenance_ref=prov_model,
        quality_indicators=composite_quality,
        notes=[
            f"Composite evidence from {len(source_bundles)} sources",
            f"Strategy: {composition_strategy.value}",
            f"Conflicts resolved: {len(merge_log)}",
        ],
    )


def _build_composite_provenance(
    *,
    source_bundles: list[EvidenceBundle],
    composition_strategy: CompositionStrategy,
    merge_log: list[MergeLogEntry],
    store: FileSystemCAS,
    composed_by: str,
    deterministic: bool,
    deterministic_seed: str | None,
) -> ProvenanceCoreRef:
    """Build W3C PROV-O graph for composition."""
    digest = _digest_composition(
        source_bundles=source_bundles,
        composition_strategy=composition_strategy,
        merge_log=merge_log,
        composed_by=composed_by,
        seed=deterministic_seed,
    )

    graph_id = f"composition_{digest[:8]}"
    timestamp = _DETERMINISTIC_TIMESTAMP if deterministic else datetime.now(UTC)

    graph = ProvenanceCoreGraph(
        graph_id=graph_id,
        created_at=timestamp,
        metadata={"composed_by": composed_by},
    )

    # Add source entities
    source_entities = []
    for i, bundle in enumerate(source_bundles):
        bundle_id = f"bundle_{i}"
        if bundle.provenance_ref:
            bundle_id = bundle.provenance_ref.graph_id

        entity = ProvenanceEntity(
            entity_id=f"source_{i}",
            entity_type=EntityType.DATASET,
            label=f"Source {i}",
            created_at=timestamp,
            attributes={
                "bundle_id": bundle_id,
                "num_sources": len(bundle.sources),
                "num_transforms": len(bundle.transforms),
            },
        )
        graph.add_entity(entity)
        source_entities.append(entity)

    # Add composition activity
    activity = ProvenanceActivity(
        activity_id="composition",
        activity_type=ActivityType.ETL,
        label=f"Composition: {composition_strategy.value}",
        started_at=timestamp,
        ended_at=timestamp,
        parameters={
            "strategy": composition_strategy.value,
            "num_sources": len(source_bundles),
            "num_conflicts": len(merge_log),
        },
    )
    graph.add_activity(activity)

    agent = ProvenanceAgent(
        agent_id="federation_engine",
        agent_type=AgentType.SYSTEM,
        label="Federation Engine",
        metadata={"version": "1.0"},
    )
    graph.add_agent(agent)

    for source_entity in source_entities:
        graph.add_usage(activity.activity_id, source_entity.entity_id, timestamp=None)

    graph.add_association(activity.activity_id, agent.agent_id, timestamp=None)

    composite_entity = ProvenanceEntity(
        entity_id="composite",
        entity_type=EntityType.DATASET,
        label="Composite Dataset",
        created_at=timestamp,
        attributes={
            "strategy": composition_strategy.value,
        },
    )
    graph.add_entity(composite_entity)

    graph.add_generation(composite_entity.entity_id, activity.activity_id, timestamp=None)

    return persist_provenance_graph(store, graph)


def _aggregate_quality_indicators(
    quality_dicts: list[dict[str, dict] | None],
) -> dict[str, dict] | None:
    """
    Aggregate quality indicators from multiple sources.

    Takes minimum across sources for conservative estimates.
    """
    if not quality_dicts:
        return None

    valid_dicts = [d for d in quality_dicts if d is not None]
    if not valid_dicts:
        return None

    all_metrics = set()
    for d in valid_dicts:
        all_metrics.update(d.keys())

    aggregated = {}
    for metric_name in all_metrics:
        metric_values = []
        for d in valid_dicts:
            if metric_name in d:
                metric_values.append(d[metric_name])

        if not metric_values:
            continue

        scores = []
        invalid_scores = 0
        for value in metric_values:
            try:
                scores.append(
                    ensure_probability(
                        value.get("score", 0.0),
                        what=f"{metric_name} quality score",
                        clamp=True,
                    )
                )
            except ValueError:
                invalid_scores += 1
                scores.append(0.0)
        min_score = min(scores) if scores else 0.0

        aggregated[metric_name] = {
            "score": min_score,
            "method": "min_across_sources",
            "num_sources": len(metric_values),
            "invalid_scores": invalid_scores,
        }

    return aggregated if aggregated else None


def _digest_composition(
    *,
    source_bundles: list[EvidenceBundle],
    composition_strategy: CompositionStrategy,
    merge_log: list[MergeLogEntry],
    composed_by: str,
    seed: str | None,
) -> str:
    source_ids = []
    for bundle in source_bundles:
        if bundle.provenance_ref:
            source_ids.append(bundle.provenance_ref.stable_id)
        else:
            source_ids.extend([str(ref) for ref in bundle.sources])

    payload = {
        "sources": sorted(source_ids),
        "strategy": composition_strategy.value,
        "merge_log": _digest_merge_log(merge_log),
        "composed_by": composed_by,
        "seed": seed or "",
        "version": "1.0",
    }

    canonical = to_canonical_bytes(payload)
    return content_hash(canonical)


def _digest_merge_log(merge_log: list[MergeLogEntry]) -> str:
    entries = []
    for entry in merge_log:
        payload = entry.to_dict()
        payload.pop("timestamp", None)
        entries.append(payload)

    entries = sorted(
        entries,
        key=lambda item: (
            json.dumps(item.get("row_key"), sort_keys=True, default=str),
            item.get("column") or "",
            item.get("source_a", {}).get("id", ""),
            item.get("source_b", {}).get("id", ""),
        ),
    )

    canonical = to_canonical_bytes(entries)
    return content_hash(canonical)
