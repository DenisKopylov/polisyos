"""Public backtesting composition bridge module API."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.ir.analytics.alignment_certification import (
    AlignmentVerificationConfig,
    load_alignment_report,
    persist_alignment_report,
    verify_fragment_bundle_alignment,
)
from polisyos.ir.analytics.causal_graph import (
    CausalGraphModel,
    load_causal_graph_model,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.causal_queries import CausalQuery
from polisyos.ir.analytics.cross_graph import (
    SCMFragment,
    load_composition_certificate,
    load_interface_mapping,
    persist_interface_mapping,
    persist_scm_fragment,
)
from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
    load_composition_failure_card_bundle,
)
from polisyos.scientist.engine.context import ExecutionContext
from polisyos.scientist.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ALIGNMENT_REPORT_REF,
    ARTIFACT_COMPOSITION_CERTIFICATE_REF,
    ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF,
    ARTIFACT_INTERFACE_MAPPING_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)


@dataclass(frozen=True)
class CompositionReplayResult:
    """Composition replay result data model."""
    node_status: str
    composition_status: str
    composition_structure_status: str
    composition_review_status: str
    needs_expert_review: bool
    query_statuses: dict[str, str]
    query_reasons: dict[str, str]
    query_traces: dict[str, Any]
    blocking_reasons: list[str]
    failure_cards: list[dict[str, Any]]
    alignment_signature: dict[str, Any] | None
    interface_mapping_signature: dict[str, Any] | None
    composition_certificate_signature: dict[str, Any] | None
    composed_graph_signature: dict[str, Any] | None
    persisted_artifacts: dict[str, bool]


def replay_fragment_composition_case(
    *,
    fragments: list[SCMFragment],
    fragment_graphs: dict[str, CausalGraphModel],
    queries: list[CausalQuery] | None = None,
    alignment_verification_config: AlignmentVerificationConfig | None = None,
    precompute_alignment: bool = False,
    direct_stitch_pairs: list[tuple[str, str]] | None = None,
    cas_root: str,
) -> CompositionReplayResult:
    """Replay fragment composition case helper."""
    store = FileSystemCAS(Path(cas_root))
    registry_bundle = build_default_registry_bundle(store).bundle_ref
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle,
        run_id="R_composition_benchmark_replay",
    )
    ctx = ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("scientist.backtesting.composition_bridge"),
    )

    fragment_refs: list[str] = []
    for fragment in fragments:
        graph = fragment_graphs[fragment.fragment_id]
        graph_ref = persist_causal_graph_model(store, graph)
        persisted_fragment = fragment.model_copy(update={"graph_ref": str(graph_ref.artifact_id)})
        fragment_ref = persist_scm_fragment(store, persisted_fragment)
        fragment_refs.append(str(fragment_ref.artifact_id))

    artifacts_index: dict[str, Any] = {}
    if precompute_alignment:
        report, mapping = verify_fragment_bundle_alignment(
            [
                fragment.model_copy(update={"graph_ref": f"artifact:graph:{fragment.fragment_id}"})
                for fragment in fragments
            ],
            config=alignment_verification_config,
            stitch_pairs=direct_stitch_pairs,
        )
        artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF] = persist_alignment_report(store, report)
        artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF] = persist_interface_mapping(store, mapping)

    state = ExperimentState(
        run_id="R_composition_benchmark_replay",
        artifacts_index=artifacts_index,
        params={
            "scm_fragment_refs": fragment_refs,
            "query_preservation_queries": [
                query.model_dump(mode="json") for query in (queries or [])
            ],
            "alignment_verification_config": (
                alignment_verification_config.model_dump(mode="json")
                if alignment_verification_config is not None
                else {}
            ),
            "direct_stitch_pairs": list(direct_stitch_pairs or []),
        },
    )
    outcome = ReconcileCausalGraphNode().execute(ctx, state)
    if outcome.status != "ok":
        raise RuntimeError(f"scientist composition replay failed: {outcome.status}")

    certificate = load_composition_certificate(
        store,
        outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF],
    )
    alignment_report = load_alignment_report(
        store,
        outcome.state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF],
    )
    interface_mapping = load_interface_mapping(
        store,
        outcome.state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF],
    )
    persisted_artifacts = {
        "alignment_report": ARTIFACT_ALIGNMENT_REPORT_REF in outcome.state.artifacts_index,
        "interface_mapping": ARTIFACT_INTERFACE_MAPPING_REF in outcome.state.artifacts_index,
        "composition_certificate": ARTIFACT_COMPOSITION_CERTIFICATE_REF in outcome.state.artifacts_index,
        "composed_graph": ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in outcome.state.artifacts_index,
        "failure_card_bundle": ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF in outcome.state.artifacts_index,
    }
    composed_graph_signature = None
    if persisted_artifacts["composed_graph"]:
        composed_graph = load_causal_graph_model(
            store,
            outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF],
        )
        composed_graph_signature = _graph_signature(composed_graph)
    if persisted_artifacts["interface_mapping"]:
        load_interface_mapping(
            store,
            outcome.state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF],
        )
    failure_cards: list[dict[str, Any]] = []
    if persisted_artifacts["failure_card_bundle"]:
        bundle = load_composition_failure_card_bundle(
            store,
            outcome.state.artifacts_index[ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF],
        )
        failure_cards = [
            _failure_card_signature(card.model_dump(mode="json"))
            for card in bundle.cards
        ]

    diagnostics = outcome.state.params.get("reconciliation_diagnostics", {})
    query_statuses = {}
    query_reasons = {}
    query_traces = {}
    if isinstance(diagnostics, dict):
        raw_statuses = diagnostics.get("query_preservation_statuses", {})
        if isinstance(raw_statuses, dict):
            query_statuses = {str(key): str(value) for key, value in raw_statuses.items()}
        raw_reasons = diagnostics.get("query_preservation_reasons", {})
        if isinstance(raw_reasons, dict):
            query_reasons = {str(key): str(value) for key, value in raw_reasons.items()}
        raw_traces = diagnostics.get("query_preservation_traces", {})
        if isinstance(raw_traces, dict):
            query_traces = {
                str(key): dict(value)
                for key, value in raw_traces.items()
                if isinstance(value, dict)
            }

    return CompositionReplayResult(
        node_status=outcome.status,
        composition_status=certificate.status,
        composition_structure_status=certificate.structure_status,
        composition_review_status=certificate.review_status,
        needs_expert_review=bool(outcome.state.params.get("needs_expert_review", False)),
        query_statuses=query_statuses,
        query_reasons=query_reasons,
        query_traces=query_traces,
        blocking_reasons=[str(item) for item in certificate.blocking_reasons],
        failure_cards=failure_cards,
        alignment_signature=normalize_alignment_report(alignment_report),
        interface_mapping_signature=normalize_interface_mapping(interface_mapping),
        composition_certificate_signature=normalize_composition_certificate(certificate),
        composed_graph_signature=composed_graph_signature,
        persisted_artifacts=persisted_artifacts,
    )


def normalize_alignment_report(report: Any) -> dict[str, Any]:
    """Normalize alignment report helper."""
    return {
        "fragment_ids": list(report.fragment_ids),
        "overall_status": report.overall_status.value,
        "review_status": report.review_status.value,
        "incompatible_pairs": [list(pair) for pair in report.incompatible_pairs],
        "alignment_assumptions": list(report.alignment_assumptions),
        "ontology_mismatch_warnings": list(report.ontology_mismatch_warnings),
        "measurement_comparability_grade": report.measurement_comparability_grade.value,
        "metadata": report.metadata,
        "certificates": [
            {
                "fragment_a_id": certificate.fragment_a_id,
                "variable_a": certificate.variable_a,
                "fragment_b_id": certificate.fragment_b_id,
                "variable_b": certificate.variable_b,
                "alignment_type": certificate.alignment_type.value,
                "reviewer": certificate.reviewer.value,
                "assumptions_introduced": list(certificate.assumptions_introduced),
                "metadata_checks": [
                    check.model_dump(mode="json")
                    for check in certificate.metadata_checks
                ],
                "metadata": certificate.metadata,
            }
            for certificate in sorted(
                report.per_variable_certificates,
                key=lambda item: (
                    item.fragment_a_id,
                    item.variable_a,
                    item.fragment_b_id,
                    item.variable_b,
                ),
            )
        ],
    }


def normalize_interface_mapping(mapping: Any) -> dict[str, Any]:
    """Normalize interface mapping helper."""
    return {
        "fragment_ids": list(mapping.fragment_ids),
        "entries": [
            {
                "interface_id": entry.interface_id,
                "canonical_node_id": entry.canonical_node_id,
                "observed": entry.observed,
                "alignment_type": entry.alignment_type,
                "reviewer": entry.reviewer,
                "assumptions_introduced": list(entry.assumptions_introduced),
                "bindings": [
                    {
                        "fragment_id": binding.fragment_id,
                        "variable_name": binding.variable_name,
                        "observed": binding.observed,
                        "measurement_model_ref": binding.measurement_model_ref,
                        "definition": binding.definition,
                        "unit": binding.unit,
                        "metadata": binding.metadata,
                    }
                    for binding in entry.bindings
                ],
                "metadata": entry.metadata,
            }
            for entry in sorted(mapping.entries, key=lambda item: item.interface_id)
        ],
    }


def normalize_composition_certificate(certificate: Any) -> dict[str, Any]:
    """Normalize composition certificate helper."""
    return {
        "status": certificate.status,
        "structure_status": certificate.structure_status,
        "review_status": certificate.review_status,
        "checked_queries": dict(sorted(certificate.checked_queries.items())),
        "newly_required_assumptions": list(certificate.newly_required_assumptions),
        "structural_assumptions": list(certificate.structural_assumptions),
        "alignment_assumptions": list(certificate.alignment_assumptions),
        "source_fragment_ids": sorted(certificate.source_fragment_refs),
        "source_fragment_graph_ids": sorted(certificate.source_fragment_graph_refs),
        "blocking_reasons": list(certificate.blocking_reasons),
        "metadata": certificate.metadata,
    }


def _graph_signature(graph: CausalGraphModel) -> dict[str, Any]:
    return {
        "graph_type": graph.graph_type.value,
        "nodes": list(graph.nodes),
        "edges": [
            {
                "src": edge.src,
                "dst": edge.dst,
                "mark_src": edge.mark_src.value,
                "mark_dst": edge.mark_dst.value,
                "lag": int(edge.lag or 0),
            }
            for edge in sorted(
                graph.edges,
                key=lambda item: (
                    item.src,
                    item.dst,
                    item.mark_src.value,
                    item.mark_dst.value,
                    int(item.lag or 0),
                ),
            )
        ],
    }


def _failure_card_signature(card: dict[str, Any]) -> dict[str, Any]:
    return {
        "failure_type": str(card.get("failure_type")),
        "severity": str(card.get("severity")),
        "description": str(card.get("description")),
        "metadata": dict(card.get("metadata", {})),
    }


__all__ = [
    "CompositionReplayResult",
    "normalize_alignment_report",
    "normalize_composition_certificate",
    "normalize_interface_mapping",
    "replay_fragment_composition_case",
]
