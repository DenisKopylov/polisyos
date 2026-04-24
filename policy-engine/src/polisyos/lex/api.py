"""Orchestrate the Lex legal pipeline through stable stage-level entry points.

Use this module when an external caller needs the canonical stage order for legal processing:
``ingest_legal_doc_bytes`` persists raw text and document metadata, ``build_legal_structure``
creates provision fragments, ``build_version_index`` and ``resolve_active_version`` select the
temporal document revision, ``assemble_norm_pack`` materializes a snapshot of applicable norms,
and ``evaluate_legality`` / ``propose_changes`` bridge the snapshot into governance workflows.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from polisyos.core.components import ENTRY_POINT_GROUP_LEX_EVALUATORS
from polisyos.core.components.bootstrap import build_components_index
from polisyos.core.contracts.lex import (
    ChangeProposalRef,
    LegalEvaluationRequest,
    LegalReportRef,
)
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

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.fabric.io.db import SimulationDB


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
    """Structure a normalized legal document into provision fragments.

    Call this after ``ingest_legal_doc_bytes(..., run_normalize=True)`` when a legal source is
    ready to expose article/part/point anchors for SPO extraction, citations, and NormPack
    assembly.

    Args:
        cas: Artifact store containing the current ``DocMeta`` and normalized text artifact.
        fact_log_root: World fact-log root where fragment facts and provenance events are written.
        doc_meta_artifact_id: Artifact id of the document metadata object to enrich.
        options: Optional jurisdiction/ruleset and extraction toggles.
        segment_name: Optional world segment name prefix.

    Returns:
        Provision index, fragment identifiers, updated ``DocMeta`` artifact id, and emitted world
        event/segment references.

    Raises:
        LexNotReadyError: If the document has not been normalized yet.
        LexStructureError: If fragment construction or persistence fails.
        LexValidationError: If document metadata or extracted structure is inconsistent.
    """

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
    """Build the temporal version index for one legal document family.

    The index reads all document revisions already attached to ``doc_source_id``, validates
    publication/effective-date metadata, detects overlapping effective ranges, and writes the
    pointer used later by ``resolve_active_version``.

    Args:
        cas: Artifact store holding document metadata artifacts.
        fact_log_root: Fact-log root used to discover existing ``DOC_HAS_VERSION`` relations and
            persist the new pointer/event facts.
        doc_source_id: Stable legal source identifier shared by all revisions.
        options: Optional selection policy and provenance settings.
        segment_name: Optional world segment name prefix.

    Returns:
        Persisted version-index references and any quality warnings collected while normalizing
        temporal metadata.

    Raises:
        LexVersioningError: If no revisions exist or index construction fails.
        LexValidationError: If source metadata violates expected date/identity contracts.
    """

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
    """Resolve the document revision that is effective on an ``as_of`` date.

    The resolver uses an explicit ``version_index_artifact_id`` when provided; otherwise it walks
    the fact log to find the latest source-properties pointer emitted by ``build_version_index``.

    Args:
        cas: Artifact store containing the persisted version index and document metadata payloads.
        doc_source_id: Stable document-family identifier.
        as_of_iso: Inclusive ISO date used for temporal resolution.
        strategy: Optional resolver mode, tie-breaker, and candidate-return controls.

    Returns:
        Selected document version, the version-index artifact used for the decision, and a
        machine-readable explanation trace. ``selected_doc_version_id`` is ``None`` when no
        candidate is effective on ``as_of_iso``.

    Raises:
        LexNotReadyError: If no version-index pointer exists for ``doc_source_id``.
        LexValidationError: If ``as_of_iso`` or resolver strategy settings are unsupported.
        LexVersioningError: If the version-index artifact cannot be loaded or validated.
    """

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
    """Assemble a jurisdiction/date-specific ``NormPack`` from corpus and claim artifacts.

    Use this stage after document versions and provision indexes exist. The assembler can select
    active source documents from the corpus or consume explicit claim-set artifacts, resolve
    claim conflicts, attach trust assessments, and persist the resulting ``NormPack`` plus an
    ``ASSEMBLE_NORM_PACK`` provenance event.

    Args:
        cas: Artifact store containing legal metadata, claim sets, and NormPack outputs.
        fact_log_root: World fact-log root used for source selection and event persistence.
        request: NormPack scope, temporal selector, conflict/trust policy ids, and soft budgets.
        db: Optional world materialization used by conflict resolution.
        segment_name: Optional world segment name prefix.

    Returns:
        Materialized NormPack artifact/world ids, selected source/claim references, conflict and
        trust outputs, and warning strings for partial-but-usable assemblies.

    Raises:
        LexNotReadyError: If required provision indexes or normalized artifacts are missing.
        LexValidationError: If request normalization, claim loading, or artifact identity checks fail.
    """

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
    """Evaluate a policy or NormPack request with a configured legal evaluator.

    The function bootstraps evaluator entry points, resolves ``request.eval_policy_id``, and
    returns both the persisted legal report and any evaluator-produced change proposals.

    Args:
        cas: Artifact store used by the evaluator backend.
        fact_log_root: Fact-log root for evaluator provenance and report persistence.
        request: Legal evaluation request contract from ``polisyos.core.contracts.lex``.
        segment_name: Optional world segment name prefix.

    Returns:
        ``(LegalReportRef, list[ChangeProposalRef])`` produced by the selected evaluator.

    Raises:
        LexValidationError: If evaluator bootstrap fails or the selected policy cannot be resolved.
    """

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
    """Evaluate jurisdictional transport constraints for a candidate policy spec.

    Args:
        jurisdiction: Jurisdiction code used by the legal bridge.
        policy_domain: Policy domain key to scope constraint retrieval.
        policy_spec: Optional policy payload; ``causal_graph`` is injected when supplied separately.
        causal_graph: Optional graph object forwarded under ``policy_spec['causal_graph']``.
        legal_kg_db_path: Optional path to the legal knowledge graph database.

    Returns:
        Constraint set emitted by ``LegalConstraintBridge`` for the requested jurisdiction/domain.
    """
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
    """Generate legal change proposals from a persisted legality report.

    Args:
        cas: Artifact store containing ``based_on_report_ref``.
        fact_log_root: Fact-log root for proposal provenance events and segments.
        based_on_report_ref: Legal report reference returned by ``evaluate_legality``.
        segment_name: Optional world segment name prefix.

    Returns:
        Change-proposal references created by the active proposal backend.
    """

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
