"""Public lex api module API."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import ENTRY_POINT_GROUP_LEX_EVALUATORS
from polisyos.core.components.bootstrap import build_components_index
from polisyos.core.contracts.lex import (
    ChangeProposalRef,
    LegalEvaluationRequest,
    LegalReportRef,
)
from polisyos.fabric.io.db import SimulationDB
from polisyos.lex.corpus.ingest import ingest_legal_doc_bytes as _ingest_legal_doc_bytes
from polisyos.lex.corpus.structure import build_legal_structure as _build_legal_structure
from polisyos.lex.corpus.versioning import (
    build_version_index as _build_version_index,
)
from polisyos.lex.corpus.versioning import (
    resolve_active_version as _resolve_active_version,
)
from polisyos.lex.legal_evaluation.change_proposals import (
    propose_changes_impl as _propose_changes_impl,
)
from polisyos.lex.legal_evaluation.evaluator_registry import (
    discover_and_bootstrap_evaluators,
    get_evaluator_registry,
)
from polisyos.lex.legal_evaluation.transport_constraints import (
    LegalConstraintBridge,
    LegalConstraintSet,
)
from polisyos.lex.normpack.assemble_pack import assemble_norm_pack as _assemble_norm_pack
from polisyos.lex.types import (
    ActiveVersionResult,
    ActiveVersionStrategy,
    LegalDocSource,
    LexIngestOptions,
    LexIngestResult,
    LexStructureOptions,
    LexStructureResult,
    LexVersionIndexOptions,
    LexVersionIndexResult,
    NormPackBuildRequest,
    NormPackBuildResult,
)


def ingest_legal_doc_bytes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    source: LegalDocSource,
    raw_bytes: bytes,
    mime: str,
    options: LexIngestOptions | None = None,
    segment_name: str | None = None,
) -> LexIngestResult:
    """Persist and optionally normalize raw legal document bytes.

    Args:
        cas: Artifact store used for raw and derived document payloads.
        fact_log_root: Root directory for world-event and segment persistence.
        source: Canonical metadata describing the document source.
        raw_bytes: Raw document body.
        mime: MIME type for the uploaded payload.
        options: Optional stage toggles for normalization, structure, and chunking.
        segment_name: Optional fact-log segment override.

    Returns:
        References to the raw document artifact and any derived Lex artifacts.
    """

    return _ingest_legal_doc_bytes(
        cas=cas,
        fact_log_root=fact_log_root,
        source=source,
        raw_bytes=raw_bytes,
        mime=mime,
        options=options,
        segment_name=segment_name,
    )


def build_legal_structure(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_meta_artifact_id: str,
    options: LexStructureOptions | None = None,
    segment_name: str | None = None,
) -> LexStructureResult:
    """Build provision structure for an ingested legal document artifact."""

    return _build_legal_structure(
        cas=cas,
        fact_log_root=fact_log_root,
        doc_meta_artifact_id=doc_meta_artifact_id,
        options=options,
        segment_name=segment_name,
    )


def build_version_index(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    doc_source_id: str,
    options: LexVersionIndexOptions | None = None,
    segment_name: str | None = None,
) -> LexVersionIndexResult:
    """Compute the version-selection index for one legal document source."""

    return _build_version_index(
        cas=cas,
        fact_log_root=fact_log_root,
        doc_source_id=doc_source_id,
        options=options,
        segment_name=segment_name,
    )


def resolve_active_version(
    *,
    cas: FileSystemCAS,
    doc_source_id: str,
    as_of_iso: str,
    strategy: ActiveVersionStrategy | None = None,
) -> ActiveVersionResult:
    """Resolve the legally active document version for a requested date."""

    return _resolve_active_version(
        cas=cas,
        doc_source_id=doc_source_id,
        as_of_iso=as_of_iso,
        strategy=strategy,
    )


def assemble_norm_pack(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: NormPackBuildRequest,
    db: SimulationDB | None = None,
    segment_name: str | None = None,
) -> NormPackBuildResult:
    """Assemble a jurisdiction/date-specific `NormPack` from Lex corpus assets."""

    return _assemble_norm_pack(
        cas=cas,
        fact_log_root=fact_log_root,
        request=request,
        db=db,
        segment_name=segment_name,
    )


def evaluate_legality(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: LegalEvaluationRequest,
    segment_name: str | None = None,
) -> tuple[LegalReportRef, list[ChangeProposalRef]]:
    """Run the configured Lex legality evaluator and return report artifacts."""

    components_index, _ = build_components_index(
        groups=[ENTRY_POINT_GROUP_LEX_EVALUATORS],
        include_dev_scan=True,
    )
    bootstrap_report = discover_and_bootstrap_evaluators(
        components_index=components_index,
    )
    if bootstrap_report.errors:
        from polisyos.lex.errors import LexValidationError

        raise LexValidationError(
            "lex evaluator bootstrap failed",
            details={"errors": bootstrap_report.errors},
        )

    evaluator = get_evaluator_registry().resolve(request.eval_policy_id)
    return evaluator.evaluate(cas, fact_log_root, request, segment_name)


def evaluate_transport_constraints(
    *,
    jurisdiction: str,
    policy_domain: str,
    policy_spec: dict[str, Any] | None = None,
    causal_graph: Any | None = None,
    legal_kg_db_path: Path | str | None = None,
) -> LegalConstraintSet:
    """Evaluate transport constraints helper."""
    normalized_policy_spec = dict(policy_spec or {})
    if causal_graph is not None and "causal_graph" not in normalized_policy_spec:
        normalized_policy_spec["causal_graph"] = causal_graph
    bridge = LegalConstraintBridge(db_path=legal_kg_db_path)
    return bridge.get_constraints_for_policy(
        jurisdiction=jurisdiction,
        policy_domain=policy_domain,
        policy_spec=normalized_policy_spec,
    )


def propose_changes(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    based_on_report_ref: LegalReportRef,
    segment_name: str | None = None,
) -> list[ChangeProposalRef]:
    """Generate change proposals from a previously produced legality report."""

    return _propose_changes_impl(
        cas=cas,
        fact_log_root=fact_log_root,
        based_on_report_ref=based_on_report_ref,
        segment_name=segment_name,
    )


__all__ = [
    "ActiveVersionResult",
    "ActiveVersionStrategy",
    "ChangeProposalRef",
    "LegalDocSource",
    "LegalEvaluationRequest",
    "LegalReportRef",
    "LexIngestOptions",
    "LexIngestResult",
    "LexStructureOptions",
    "LexStructureResult",
    "LexVersionIndexOptions",
    "LexVersionIndexResult",
    "NormPackBuildRequest",
    "NormPackBuildResult",
    "assemble_norm_pack",
    "build_legal_structure",
    "build_version_index",
    "evaluate_legality",
    "evaluate_transport_constraints",
    "ingest_legal_doc_bytes",
    "propose_changes",
    "resolve_active_version",
]
