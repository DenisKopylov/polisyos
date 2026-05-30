#!/usr/bin/env python3
"""Validate Fabric Phase 9 discovery and entity-intelligence contracts."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from polisyos.core.artifacts.store import FileSystemCAS  # noqa: E402
from polisyos.fabric.catalog import (  # noqa: E402
    DatasetDiscoveryBenchmarkPack,
    SemanticDatasetCatalog,
)
from polisyos.fabric.connectors.profiles.registry import SourceProfileRegistry  # noqa: E402
from polisyos.fabric.entity_resolution import (  # noqa: E402
    EntityMatchStore,
    EntityRecord,
    ProbabilisticEntityResolver,
)
from polisyos.fabric.world.materialize import (  # noqa: E402
    WorldGraphEdgeRecord,
    WorldGraphNodeRecord,
    WorldGraphSnapshot,
    build_world_kuzu_conflict_query,
    build_world_kuzu_entity_neighborhood_query,
    build_world_kuzu_origin_query,
    build_world_kuzu_policy_impact_query,
    query_world_conflict_neighborhood,
    query_world_entity_neighborhood,
    query_world_origin_trace,
    query_world_policy_impact,
    query_world_source_overlap,
)
from tools.quality.validation.fabric_source_contracts import (  # noqa: E402
    build_source_contracts,
)

REPORT_SCHEMA_VERSION = "fabric.discovery_intelligence_report.v1"
DEFAULT_EVAL_PATH = REPO_ROOT / "tests" / "_data" / "fabric" / "discovery_eval.json"


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true", help="Print report JSON")
    parser.add_argument("--check", action="store_true", help="Fail on Phase 9 gaps")
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL_PATH)
    return parser.parse_args(argv)


def build_report(*, eval_path: Path = DEFAULT_EVAL_PATH) -> dict[str, Any]:
    contracts = build_source_contracts()
    profiles = tuple(SourceProfileRegistry.get_instance().list_all())
    catalog = SemanticDatasetCatalog(contracts, profiles=profiles)
    entries = catalog.list_entries()
    benchmark = DatasetDiscoveryBenchmarkPack.from_mapping(json.loads(eval_path.read_text("utf-8")))
    eval_report = catalog.evaluate_benchmark(benchmark)
    stale_probe_id = entries[0].source_contract_id if entries else ""
    stale_filtered = False
    stale_allowed = False
    refresh_invalidates = False
    if stale_probe_id:
        refresh_catalog = SemanticDatasetCatalog(contracts, profiles=profiles)
        before = refresh_catalog.get_entry(stale_probe_id)
        updated_contracts = [
            contract.model_copy(update={"version": "phase9-validator-change"})
            if contract.id == stale_probe_id
            else contract
            for contract in contracts
        ]
        changed = refresh_catalog.refresh(updated_contracts, profiles=profiles)
        after = refresh_catalog.get_entry(stale_probe_id)
        refresh_invalidates = (
            stale_probe_id in changed
            and before is not None
            and after is not None
            and before.vector_metadata.fingerprint != after.vector_metadata.fingerprint
        )

        stale_catalog = SemanticDatasetCatalog(contracts, profiles=profiles)
        stale_catalog.mark_stale(stale_probe_id, "phase9_validator_stale_probe")
        filtered_plan = stale_catalog.resolve(stale_probe_id)
        allowed_plan = stale_catalog.resolve(stale_probe_id, allow_stale=True)
        stale_filtered = all(
            candidate.source_contract_id != stale_probe_id for candidate in filtered_plan.candidates
        )
        stale_allowed = any(
            candidate.source_contract_id == stale_probe_id
            and candidate.evidence.vector_metadata.stale
            for candidate in allowed_plan.candidates
        )
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "source_contract_count": len(contracts),
        "profile_count": len(profiles),
        "catalog_entry_count": len(entries),
        "embedding_model": catalog.embedding_model,
        "llm_calls": 0,
        "evidence_coverage": {
            "source_contract": sum(1 for entry in entries if entry.source_contract_id),
            "profile_resolved": sum(1 for entry in entries if entry.profile_status == "resolved"),
            "quality": sum(1 for entry in entries if entry.quality_contract_ref),
            "access": sum(1 for entry in entries if entry.access_classification),
            "source_trust": sum(1 for entry in entries if entry.source_trust_tier),
        },
        "stale_invalidation": {
            "probe_source_contract_id": stale_probe_id,
            "stale_filtered_by_default": stale_filtered,
            "stale_allowed_only_when_explicit": stale_allowed,
            "refresh_invalidates_source_contract_change": refresh_invalidates,
        },
        "eval": {
            "benchmark_id": eval_report.benchmark_id,
            "benchmark_version": eval_report.benchmark_version,
            "total_cases": eval_report.total_cases,
            "passed_cases": eval_report.passed_cases,
            "pass_rate": eval_report.pass_rate,
            "false_positive_failures": eval_report.false_positive_failures,
            "meets_thresholds": benchmark.meets_thresholds(eval_report),
            "outcomes": [
                {
                    "case_id": outcome.case.case_id,
                    "query": outcome.case.query,
                    "expected_source_contract_id": outcome.case.expected_source_contract_id,
                    "matched_source_contract_id": outcome.matched_source_contract_id,
                    "matched_score": outcome.matched_score,
                    "matched_rank": outcome.matched_rank,
                    "passed": outcome.passed,
                    "route": outcome.route,
                }
                for outcome in eval_report.outcomes
            ],
        },
        "entity_resolution": _probe_entity_resolution(),
        "graph_reasoning": _probe_graph_reasoning(),
    }


def _probe_entity_resolution() -> dict[str, Any]:
    resolver = ProbabilisticEntityResolver()
    matches = resolver.resolve(
        [
            EntityRecord(
                entity_id="wb:usa",
                canonical_name="United States",
                source="worldbank",
                aliases=["USA", "United States of America"],
                identifiers={"iso3": "USA"},
                attributes={"region": "north_america"},
            ),
            EntityRecord(
                entity_id="who:us",
                canonical_name="United States of America",
                source="who",
                aliases=["United States", "USA"],
                identifiers={"iso3": "USA"},
                attributes={"region": "north_america"},
            ),
        ],
        min_confidence=0.5,
    )
    candidate = matches[0] if matches else None
    explainable = bool(candidate and candidate.evidence)
    reversible = False
    override_audit_index = False
    accepted_requires_merge = False
    accepted_override_has_provenance = False

    if candidate is not None:
        with tempfile.TemporaryDirectory(prefix="fabric-discovery-") as raw_tmp:
            store = EntityMatchStore(FileSystemCAS(Path(raw_tmp) / "cas"))
            batch_ref = store.persist_candidates(
                [candidate],
                method=resolver.method,
                metadata={"phase": "9-validator"},
            )
            reversible = (
                store.load_candidates(batch_ref.artifact_id).candidates[0].override_status
                == "candidate"
            )
            try:
                store.persist_override(
                    candidate,
                    status="accepted",
                    actor="fabric.phase9.validator",
                    reason="prove merge governance gate",
                    provenance_ref="sha256:" + ("9" * 64),
                )
            except ValueError as exc:
                accepted_requires_merge = "merge_governance_ref" in str(exc)
            override_ref = store.persist_override(
                candidate,
                status="accepted",
                actor="fabric.phase9.validator",
                reason="iso3 identifier and region agree across sources",
                provenance_ref="sha256:" + ("a" * 64),
                merge_governance_ref="merge-review:phase9-validator:entity.usa",
            )
            override = store.load_override(override_ref.artifact_id)
            audit_rows = store.list_override_audit()
            override_audit_index = (
                bool(audit_rows) and audit_rows[0][1].match_id == candidate.match_id
            )
            accepted_override_has_provenance = (
                override.candidate.override_status == "accepted"
                and override.candidate.override_provenance_ref is not None
                and override.candidate.merge_governance_ref
                == "merge-review:phase9-validator:entity.usa"
                and override.audit.actor == "fabric.phase9.validator"
            )

    return {
        "models": [
            "EntityMatchCandidate",
            "EntityOverrideAuditRecord",
            "EntityOverrideEnvelope",
        ],
        "probabilistic_store": bool(candidate),
        "explainable_matches": explainable,
        "reversible_candidates": reversible,
        "accepted_override_requires_merge_governance": accepted_requires_merge,
        "accepted_override_has_provenance": accepted_override_has_provenance,
        "override_audit_index": override_audit_index,
    }


def _probe_graph_reasoning() -> dict[str, bool]:
    snapshot = WorldGraphSnapshot(
        [
            WorldGraphNodeRecord(
                node_id="source.worldbank",
                kind="doc_source",
                label="World Bank",
            ),
            WorldGraphNodeRecord(node_id="source.who", kind="doc_source", label="WHO"),
            WorldGraphNodeRecord(
                node_id="entity.usa",
                kind="entity.country",
                label="United States",
            ),
            WorldGraphNodeRecord(node_id="metric.gdp", kind="metric", label="GDP"),
            WorldGraphNodeRecord(
                node_id="policy.tax",
                kind="policy_domain",
                label="Tax Policy",
            ),
            WorldGraphNodeRecord(
                node_id="conflict.gdp",
                kind="conflict.record",
                label="GDP conflict",
            ),
        ],
        [
            WorldGraphEdgeRecord(
                source_id="source.worldbank",
                target_id="entity.usa",
                kind="source.describes",
            ),
            WorldGraphEdgeRecord(
                source_id="source.who",
                target_id="entity.usa",
                kind="source.describes",
            ),
            WorldGraphEdgeRecord(
                source_id="entity.usa",
                target_id="metric.gdp",
                kind="metric.references",
            ),
            WorldGraphEdgeRecord(
                source_id="entity.usa",
                target_id="policy.tax",
                kind="policy.impacts",
            ),
            WorldGraphEdgeRecord(
                source_id="entity.usa",
                target_id="conflict.gdp",
                kind="conflict.flagged",
            ),
        ],
    )
    neighborhood = query_world_entity_neighborhood(snapshot, "entity.usa", max_hops=2)
    overlap = query_world_source_overlap(snapshot, "entity.usa", max_hops=1)
    origin = query_world_origin_trace(snapshot, "entity.usa", max_hops=2)
    conflicts = query_world_conflict_neighborhood(snapshot, "entity.usa", max_hops=2)
    impact = query_world_policy_impact(snapshot, "entity.usa", max_hops=2)
    origin_query, _ = build_world_kuzu_origin_query("entity.usa", max_hops=2)
    conflict_query, _ = build_world_kuzu_conflict_query("entity.usa", max_hops=2)
    impact_query, _ = build_world_kuzu_policy_impact_query("entity.usa", max_hops=2)
    neighborhood_query, _ = build_world_kuzu_entity_neighborhood_query(
        "entity.usa",
        max_hops=2,
    )

    return {
        "origin_trace": {node.node_id for node in origin.origin_nodes}
        == {"source.worldbank", "source.who"},
        "source_overlap": {node.node_id for node in overlap.overlapping_sources}
        == {"source.worldbank", "source.who"},
        "conflict_neighborhood": {node.node_id for node in conflicts.conflict_nodes}
        == {"conflict.gdp"},
        "policy_impact": {node.node_id for node in impact.impacted_nodes} == {"policy.tax"},
        "entity_neighborhood": "metric.gdp" in {node.node_id for node in neighborhood.nodes},
        "kuzu_helpers": all(
            token
            for token in (
                "origin.kind CONTAINS 'source'" in origin_query,
                "CONTAINS 'conflict'" in conflict_query,
                "neighbor.kind CONTAINS 'policy'" in impact_query,
                "RETURN path" in neighborhood_query,
            )
        ),
    }


def validate_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    count = int(report["catalog_entry_count"])
    coverage = report["evidence_coverage"]
    for key in ("source_contract", "profile_resolved", "quality", "access", "source_trust"):
        if int(coverage.get(key, 0)) != count:
            errors.append(f"discovery evidence coverage gap: {key}")
    if report.get("llm_calls") != 0:
        errors.append("Phase 9 validator must not call LLMs")
    stale = report["stale_invalidation"]
    if not stale.get("stale_filtered_by_default"):
        errors.append("stale dataset vectors are not filtered by default")
    if not stale.get("stale_allowed_only_when_explicit"):
        errors.append("stale dataset vectors are not explicitly labelled when allowed")
    if not stale.get("refresh_invalidates_source_contract_change"):
        errors.append("source-contract changes do not invalidate dataset vectors")
    if not report["eval"].get("meets_thresholds"):
        errors.append("dataset discovery eval thresholds failed")
    graph = report["graph_reasoning"]
    for key in (
        "origin_trace",
        "source_overlap",
        "conflict_neighborhood",
        "policy_impact",
        "entity_neighborhood",
        "kuzu_helpers",
    ):
        if not graph.get(key):
            errors.append(f"missing graph reasoning helper: {key}")
    entity = report["entity_resolution"]
    if not entity.get("probabilistic_store"):
        errors.append("probabilistic entity-resolution store probe failed")
    if not entity.get("explainable_matches"):
        errors.append("entity matches are not explainable")
    if not entity.get("reversible_candidates"):
        errors.append("entity candidates are not reversible")
    if not entity.get("accepted_override_requires_merge_governance"):
        errors.append("entity overrides can accept without merge governance")
    if not entity.get("accepted_override_has_provenance"):
        errors.append("entity override provenance audit is missing")
    if not entity.get("override_audit_index"):
        errors.append("entity override audit index is missing")
    return errors


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    report = build_report(eval_path=args.eval)
    if args.report:
        print(json.dumps(report, indent=2, sort_keys=True))
    errors = validate_report(report) if args.check else []
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    if args.check:
        print("Fabric discovery intelligence check PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
