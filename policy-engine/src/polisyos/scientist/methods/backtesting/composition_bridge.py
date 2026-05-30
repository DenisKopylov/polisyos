"""Replay fragment composition cases through `ReconcileCausalGraphNode` for audit."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.ir_adapter import ensure_ir_artifact_store
from polisyos.core.artifacts.protocol import ArtifactStore as CoreArtifactStore
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.foundry.methods.catalog.causal.composition_failure_cards import (
    load_composition_failure_card_bundle,
)
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
from polisyos.ir.analytics.cross_graph import (
    SCMFragment,
    load_composition_certificate,
    load_interface_mapping,
    persist_interface_mapping,
    persist_scm_fragment,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.nodes.builtins.causal.reconcile_causal_graph import ReconcileCausalGraphNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_ALIGNMENT_REPORT_REF,
    ARTIFACT_COMPOSITION_CERTIFICATE_REF,
    ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF,
    ARTIFACT_INTERFACE_MAPPING_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal_queries import CausalQuery
    from polisyos.ir.artifacts import ArtifactStore as IRArtifactStore

    type CompositionStore = CoreArtifactStore
else:
    IRArtifactStore = Any
    CausalQuery = Any
    CompositionStore = CoreArtifactStore


CompositionStoreFactory = Callable[[Path], CompositionStore]


def _default_composition_store_factory(root: Path) -> CompositionStore:
    from polisyos.core.artifacts.backends.config import (
        ArtifactStoreConfig,
        build_artifact_store,
    )

    return build_artifact_store(ArtifactStoreConfig(root=str(root)))


@dataclass(frozen=True)
class CompositionReplayResult:
    """Capture composition replay status, query-preservation diagnostics, and artifact signatures."""

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
    store: CoreArtifactStore | None = None,
    store_factory: CompositionStoreFactory | None = None,
) -> CompositionReplayResult:
    """Replay one fragment-composition benchmark and normalize the persisted diagnostics.

    Args:
        fragments: Fragment contracts to persist and reconcile.
        fragment_graphs: Graph payloads keyed by `fragment_id`.
        queries: Optional causal queries that must be preserved by composition.
        alignment_verification_config: Optional alignment verifier config.
        precompute_alignment: Persist alignment/interface artifacts before the
            reconcile node runs.
        direct_stitch_pairs: Optional fragment-pair hints for explicit stitching.
        cas_root: CAS root used for replay artifacts.

    Returns:
        `CompositionReplayResult` with node status, composition certificate
        fields, normalized artifact signatures, and failure cards.

    Raises:
        RuntimeError: If `ReconcileCausalGraphNode` fails for the replay case.
    """
    resolved_store = store
    if resolved_store is None:
        factory = store_factory or _default_composition_store_factory
        resolved_store = factory(Path(cas_root))
    ir_store: IRArtifactStore = ensure_ir_artifact_store(resolved_store)
    registry_bundle = build_default_registry_bundle(resolved_store).bundle_ref
    run = RunContext.start(
        store=resolved_store,
        registry_bundle=registry_bundle,
        run_id="R_composition_benchmark_replay",
    )
    ctx = ExecutionContext(
        store=resolved_store,
        run=run,
        logger=logging.getLogger("scientist.backtesting.composition_bridge"),
    )

    fragment_refs: list[str] = []
    for fragment in fragments:
        graph = fragment_graphs[fragment.fragment_id]
        graph_ref = persist_causal_graph_model(ir_store, graph)
        persisted_fragment = fragment.model_copy(update={"graph_ref": str(graph_ref.artifact_id)})
        fragment_ref = persist_scm_fragment(ir_store, persisted_fragment)
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
        artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF] = persist_alignment_report(ir_store, report)
        artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF] = persist_interface_mapping(
            ir_store, mapping
        )

    state = ExperimentState(
        schema_version="1.3",
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

    from polisyos.ir.registry.refs import (
        AlignmentReportRef,
        CausalGraphModelRef,
        CompositionCertificateRef,
        CompositionFailureCardBundleRef,
        InterfaceMappingRef,
    )

    certificate = load_composition_certificate(
        ir_store,
        CompositionCertificateRef.model_validate(
            outcome.state.artifacts_index[ARTIFACT_COMPOSITION_CERTIFICATE_REF]
        ),
    )
    alignment_report = load_alignment_report(
        ir_store,
        AlignmentReportRef.model_validate(
            outcome.state.artifacts_index[ARTIFACT_ALIGNMENT_REPORT_REF]
        ),
    )
    interface_mapping = load_interface_mapping(
        ir_store,
        InterfaceMappingRef.model_validate(
            outcome.state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF]
        ),
    )
    persisted_artifacts = {
        "alignment_report": ARTIFACT_ALIGNMENT_REPORT_REF in outcome.state.artifacts_index,
        "interface_mapping": ARTIFACT_INTERFACE_MAPPING_REF in outcome.state.artifacts_index,
        "composition_certificate": ARTIFACT_COMPOSITION_CERTIFICATE_REF
        in outcome.state.artifacts_index,
        "composed_graph": ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF in outcome.state.artifacts_index,
        "failure_card_bundle": ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF
        in outcome.state.artifacts_index,
    }
    composed_graph_signature = None
    if persisted_artifacts["composed_graph"]:
        composed_graph = load_causal_graph_model(
            ir_store,
            CausalGraphModelRef.model_validate(
                outcome.state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF]
            ),
        )
        composed_graph_signature = _graph_signature(composed_graph)
    if persisted_artifacts["interface_mapping"]:
        load_interface_mapping(
            ir_store,
            InterfaceMappingRef.model_validate(
                outcome.state.artifacts_index[ARTIFACT_INTERFACE_MAPPING_REF]
            ),
        )
    failure_cards: list[dict[str, Any]] = []
    if persisted_artifacts["failure_card_bundle"]:
        bundle = load_composition_failure_card_bundle(
            ir_store,
            CompositionFailureCardBundleRef.model_validate(
                outcome.state.artifacts_index[ARTIFACT_COMPOSITION_FAILURE_CARD_BUNDLE_REF]
            ),
        )
        failure_cards = [
            _failure_card_signature(card.model_dump(mode="json")) for card in bundle.cards
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
    """Convert an alignment report into deterministic JSON for replay assertions."""
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
                    check.model_dump(mode="json") for check in certificate.metadata_checks
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
    """Convert an interface mapping into deterministic JSON for replay assertions."""
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
    """Convert a composition certificate into deterministic JSON for replay assertions."""
    return {
        "status": certificate.status,
        "structure_status": certificate.structure_status,
        "review_status": certificate.review_status,
        "checked_queries": dict(sorted(certificate.checked_queries.items())),
        "query_certificates": {
            str(key): (
                value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)
            )
            for key, value in sorted(getattr(certificate, "query_certificates", {}).items())
        },
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
