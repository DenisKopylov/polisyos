"""Assemble NormPack snapshots from active legal provisions, claims, and conflict resolution.

This module is the semantic boundary between corpus/versioning outputs and runtime legal
evaluation. It selects applicable provisions, extracts/normalizes norm claims, resolves
claim conflicts, converts canonical claims into ``NormRule`` objects, and persists a
``NormPack`` plus world provenance.
"""

from __future__ import annotations

import re
from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import (
    ENTRY_POINT_GROUP_LEX_EXTRACTORS,
    ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS,
    ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS,
)
from polisyos.core.components.bootstrap import build_components_index
from polisyos.data_forge.read_api import legal as legal_read_api
from polisyos.fabric.claims import resolve_conflicts
from polisyos.fabric.claims.extractor_registry import discover_and_bootstrap_extractors
from polisyos.fabric.claims.persist import (
    claim_artifact_ids_by_claim_id,
    load_claim,
    load_doc_meta,
    load_json_artifact,
)
from polisyos.fabric.world import (
    append_world_segment_index,
    emit_world_node_facts,
    stable_world_provenance_v1,
    write_world_fact_segment,
)
from polisyos.fabric.world.events import (
    build_deterministic_world_event,
    persist_world_event_with_facts,
)
from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN, ID_PATTERN
from polisyos.ir.norm_pack import NormPack, NormRef, NormRule, RuleType
from polisyos.ir.world.abi import NodeKind
from polisyos.ir.world.conflict import ConflictSet
from polisyos.ir.world.event import (
    EventKind,
    ProvActivityType,
    ProvAgentType,
    WorldObjectRef,
)
from polisyos.ir.world.ids import (
    artifact_id_to_world_id,
    stable_world_id_from_canon,
)
from polisyos.ir.world.trust import TrustAssessment
from polisyos.lex.common import collapse_ws, parse_iso_date
from polisyos.lex.errors import LexNotReadyError, LexValidationError
from polisyos.lex.normpack.applicability import applicability_key, build_norm_applicability
from polisyos.lex.normpack.extract_norm_claims import ProvisionSelection, extract_norm_claims
from polisyos.lex.normpack.policies import (
    ASSEMBLY_PIPELINE_ID,
    CLAIMS_NORMALIZE_VERSION,
    CONFLICT_RESOLUTION_ALGORITHM_VERSION,
    CONFLICT_TRUST_ALGORITHM_VERSION,
    DEFAULT_EXTRACTOR_ID,
    DEFAULT_INCLUDED_PROVISION_KINDS,
    DEFAULT_PREVIEW_LIMIT,
    DEFAULT_SELECTION_POLICY_ID,
    DOMAIN_KEYWORDS,
    NORM_PACK_KIND,
)
from polisyos.lex.normpack.provider_registry import (
    discover_and_bootstrap_providers,
    get_norm_pack_provider_registry,
)
from polisyos.lex.normpack.select_sources import (
    normalize_as_of,
    select_active_doc_versions,
    select_doc_sources,
)
from polisyos.lex.types import (
    NormPackBudgets,
    NormPackBuildRequest,
    NormPackBuildResult,
    SelectedDocVersion,
)

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.fabric.io.db import SimulationDB
    from polisyos.ir.world.claim import Claim

_ID_RE = re.compile(ID_PATTERN)


def _normalize_request(
    request: NormPackBuildRequest,
) -> tuple[NormPackBuildRequest, str, str, str | None]:
    jurisdiction_norm = request.jurisdiction.strip().casefold()
    if _ID_RE.fullmatch(jurisdiction_norm) is None:
        raise LexValidationError(f"jurisdiction must match {ID_PATTERN}: {request.jurisdiction!r}")

    as_of_norm = normalize_as_of(request.as_of)

    domain_norm: str | None = None
    if request.domain is not None:
        domain_norm = request.domain.strip().casefold()
        if _ID_RE.fullmatch(domain_norm) is None:
            raise LexValidationError(f"domain must match {ID_PATTERN}: {request.domain!r}")

    if request.selection_policy_id != DEFAULT_SELECTION_POLICY_ID:
        raise LexValidationError(f"unsupported selection_policy_id: {request.selection_policy_id}")
    for field_name, value in (
        ("selection_policy_id", request.selection_policy_id),
        ("conflict_policy_id", request.conflict_policy_id),
        ("trust_policy_id", request.trust_policy_id),
    ):
        if _ID_RE.fullmatch(value) is None:
            raise LexValidationError(f"{field_name} must match {ID_PATTERN}: {value!r}")

    doc_source_ids: list[str] | None = None
    if request.doc_source_ids is not None:
        doc_source_ids = sorted(set(request.doc_source_ids))
        for doc_source_id in doc_source_ids:
            if _ID_RE.fullmatch(doc_source_id) is None:
                raise LexValidationError(
                    f"doc_source_id must match {ID_PATTERN}: {doc_source_id!r}"
                )

    claim_set_artifact_ids: list[str] | None = None
    if request.claim_set_artifact_ids is not None:
        claim_set_artifact_ids = sorted(set(request.claim_set_artifact_ids))
        for artifact_id in claim_set_artifact_ids:
            if re.fullmatch(ARTIFACT_ID_PATTERN, artifact_id) is None:
                raise LexValidationError(
                    f"claim_set_artifact_id must match {ARTIFACT_ID_PATTERN}: {artifact_id!r}"
                )

    budgets = request.budgets
    for field_name, value in (
        ("max_docs", budgets.max_docs),
        ("max_provisions", budgets.max_provisions),
        ("max_claims", budgets.max_claims),
    ):
        if value is not None and value < 0:
            raise LexValidationError(f"{field_name} must be >= 0")

    normalized = NormPackBuildRequest(
        jurisdiction=jurisdiction_norm,
        as_of=as_of_norm,
        domain=domain_norm,
        doc_source_ids=doc_source_ids,
        claim_set_artifact_ids=claim_set_artifact_ids,
        selection_policy_id=request.selection_policy_id,
        conflict_policy_id=request.conflict_policy_id,
        trust_policy_id=request.trust_policy_id,
        budgets=NormPackBudgets(
            max_docs=budgets.max_docs,
            max_provisions=budgets.max_provisions,
            max_claims=budgets.max_claims,
        ),
    )
    return normalized, jurisdiction_norm, as_of_norm, domain_norm


def _build_provision_preview(*, normalized_text: str, start: int, end: int) -> str:
    preview = normalized_text[start:end]
    return collapse_ws(preview).casefold()[:DEFAULT_PREVIEW_LIMIT]


def _domain_match(
    *,
    domain_norm: str | None,
    keywords: list[str],
    citation_label: str,
    preview: str,
) -> bool:
    if domain_norm is None:
        return True
    citation_norm = citation_label.casefold()
    return any(keyword in citation_norm or keyword in preview for keyword in keywords)


def _select_provisions(
    *,
    cas: FileSystemCAS,
    selected_doc_versions: list[SelectedDocVersion],
    domain_norm: str | None,
    max_provisions: int | None,
) -> tuple[list[ProvisionSelection], list[str], list[str]]:
    warnings: list[str] = []
    selected: list[ProvisionSelection] = []

    keywords = DOMAIN_KEYWORDS.get(domain_norm or "", []) if domain_norm is not None else []
    if domain_norm is not None and not keywords:
        warnings.append(f"warning:unknown_domain:{domain_norm}")

    for doc in sorted(selected_doc_versions, key=lambda row: row.doc_source_id):
        meta = load_doc_meta(cas, doc.doc_meta_artifact_id)
        if meta.normalized_ref is None:
            raise LexNotReadyError(
                "run polisyos.lex.api.build_legal_structure for this doc_version",
                doc_source_id=meta.doc_source_id,
                doc_version_id=meta.doc_version_id,
            )

        lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
        if not isinstance(lex_props, dict):
            lex_props = {}
        provision_index_ref = lex_props.get("provision_index_ref")
        if not isinstance(provision_index_ref, str) or not provision_index_ref:
            raise LexNotReadyError(
                "run polisyos.lex.api.build_legal_structure for this doc_version",
                doc_source_id=meta.doc_source_id,
                doc_version_id=meta.doc_version_id,
            )

        index = legal_read_api.load_provision_index(cas, provision_index_ref)
        if index.doc_version_id != meta.doc_version_id or index.doc_source_id != meta.doc_source_id:
            raise LexValidationError(
                "provision index doc identity mismatch",
                doc_source_id=meta.doc_source_id,
                doc_version_id=meta.doc_version_id,
            )

        normalized_payload = load_json_artifact(cas, meta.normalized_ref)
        normalized_text = normalized_payload.get("text")
        if not isinstance(normalized_text, str):
            raise LexValidationError("normalized artifact missing text")

        for provision in index.provisions:
            if provision.kind not in DEFAULT_INCLUDED_PROVISION_KINDS:
                continue
            preview = _build_provision_preview(
                normalized_text=normalized_text,
                start=provision.offset_start,
                end=provision.offset_end,
            )
            if not _domain_match(
                domain_norm=domain_norm,
                keywords=keywords,
                citation_label=provision.citation_label,
                preview=preview,
            ):
                continue

            selected.append(
                ProvisionSelection(
                    fragment_id=provision.fragment_id,
                    doc_source_id=index.doc_source_id,
                    doc_version_id=index.doc_version_id,
                    doc_meta_artifact_id=doc.doc_meta_artifact_id,
                    provision_index_artifact_id=provision_index_ref,
                    provision_key=provision.provision_key,
                    anchor_path=provision.anchor_path,
                    citation_label=provision.citation_label,
                    kind=provision.kind,
                    offset_start=provision.offset_start,
                    offset_end=provision.offset_end,
                )
            )

    selected.sort(
        key=lambda row: (
            row.doc_version_id,
            row.anchor_path,
            row.fragment_id,
        )
    )

    deduped: list[ProvisionSelection] = []
    seen_fragment_ids: set[str] = set()
    for row in selected:
        if row.fragment_id in seen_fragment_ids:
            continue
        seen_fragment_ids.add(row.fragment_id)
        deduped.append(row)
    selected = deduped

    if max_provisions is not None and len(selected) > max_provisions:
        warnings.append(f"warning:max_provisions_truncated:{max_provisions}/{len(selected)}")
        selected = selected[:max_provisions]

    selected_fragment_ids = sorted({row.fragment_id for row in selected})
    return selected, selected_fragment_ids, sorted(set(warnings))


def _claim_set_matches_request(
    *,
    claim_set_payload: dict[str, Any],
    meta: Any,
    jurisdiction_norm: str,
    domain_norm: str | None,
    as_of_norm: str,
) -> bool:
    meta_jurisdiction = (
        (meta.jurisdiction or "").strip().casefold() if getattr(meta, "jurisdiction", None) else ""
    )
    if meta_jurisdiction and meta_jurisdiction != jurisdiction_norm:
        return False

    payload_domain = claim_set_payload.get("domain")
    payload_domain_norm = (
        payload_domain.strip().casefold() if isinstance(payload_domain, str) else ""
    )
    if domain_norm is not None and payload_domain_norm and payload_domain_norm != domain_norm:
        return False

    lex_props = meta.props.get("lex") if isinstance(meta.props, dict) else None
    if not isinstance(lex_props, dict):
        lex_props = {}
    effective_from = parse_iso_date(
        lex_props.get("effective_from")
        if isinstance(lex_props.get("effective_from"), str)
        else None
    )
    effective_to = parse_iso_date(
        lex_props.get("effective_to") if isinstance(lex_props.get("effective_to"), str) else None
    )
    as_of_date = parse_iso_date(as_of_norm)
    if as_of_date is None:
        return True
    if effective_from is not None and effective_from > as_of_date:
        return False
    return not (effective_to is not None and effective_to < as_of_date)


def _select_claim_sets(
    *,
    cas: FileSystemCAS,
    claim_set_artifact_ids: list[str],
    jurisdiction_norm: str,
    domain_norm: str | None,
    as_of_norm: str,
) -> tuple[list[SelectedDocVersion], list[str], list[str], list[str], list[str], list[str]]:
    selected_doc_versions: list[SelectedDocVersion] = []
    selected_fragment_ids: set[str] = set()
    selected_claim_set_artifact_ids: list[str] = []
    provision_index_artifact_ids: set[str] = set()
    warnings: list[str] = []

    for artifact_id in sorted(set(claim_set_artifact_ids)):
        payload = load_json_artifact(cas, artifact_id)
        doc_meta_artifact_id = payload.get("doc_meta_artifact_id")
        doc_source_id = payload.get("doc_source_id")
        doc_version_id = payload.get("doc_version_id")
        if (
            not isinstance(doc_meta_artifact_id, str)
            or not isinstance(doc_source_id, str)
            or not isinstance(doc_version_id, str)
        ):
            warnings.append(f"warning:invalid_claim_set_payload:{artifact_id}")
            continue
        meta = load_doc_meta(cas, doc_meta_artifact_id)
        if not _claim_set_matches_request(
            claim_set_payload=payload,
            meta=meta,
            jurisdiction_norm=jurisdiction_norm,
            domain_norm=domain_norm,
            as_of_norm=as_of_norm,
        ):
            warnings.append(f"warning:claim_set_filtered:{artifact_id}")
            continue

        selected_doc_versions.append(
            SelectedDocVersion(
                doc_source_id=doc_source_id,
                doc_version_id=doc_version_id,
                doc_meta_artifact_id=doc_meta_artifact_id,
                selection_policy_id="lex.batch.claim_set_v1",
                used_version_index_artifact_id=None,
                explanation=["selected_via=claim_set_artifact_ids"],
            )
        )
        selected_claim_set_artifact_ids.append(artifact_id)

        parent_payload: dict[str, Any] | None = None
        input_claim_set_artifact_id = payload.get("input_claim_set_artifact_id")
        if isinstance(input_claim_set_artifact_id, str) and input_claim_set_artifact_id:
            try:
                parent_payload = load_json_artifact(cas, input_claim_set_artifact_id)
            except Exception:
                parent_payload = None

        for fragment_id in payload.get("selected_fragment_ids", []) or []:
            if isinstance(fragment_id, str):
                selected_fragment_ids.add(fragment_id)
        if parent_payload is not None:
            for fragment_id in parent_payload.get("selected_fragment_ids", []) or []:
                if isinstance(fragment_id, str):
                    selected_fragment_ids.add(fragment_id)

        claim_rows = payload.get("claims")
        if isinstance(claim_rows, list):
            for row in claim_rows:
                if not isinstance(row, dict):
                    continue
                source_fragment_id = row.get("source_fragment_id")
                if isinstance(source_fragment_id, str) and source_fragment_id:
                    selected_fragment_ids.add(source_fragment_id)
                claim_artifact_id = row.get("claim_artifact_id")
                if not isinstance(claim_artifact_id, str) or not claim_artifact_id:
                    continue
                claim = load_claim(cas, claim_artifact_id)
                for citation in claim.citations:
                    if citation.fragment_id:
                        selected_fragment_ids.add(citation.fragment_id)

        maybe_provision_index_artifact_id = payload.get("provision_index_artifact_id")
        if (
            not isinstance(maybe_provision_index_artifact_id, str)
            or not maybe_provision_index_artifact_id
        ) and parent_payload is not None:
            maybe_provision_index_artifact_id = parent_payload.get("provision_index_artifact_id")
        if isinstance(maybe_provision_index_artifact_id, str) and maybe_provision_index_artifact_id:
            provision_index_artifact_ids.add(maybe_provision_index_artifact_id)

    norm_claim_ids = sorted(
        claim_artifact_ids_by_claim_id(
            cas=cas,
            claim_set_artifact_ids=selected_claim_set_artifact_ids,
        )
    )
    selected_doc_versions.sort(key=lambda row: row.doc_source_id)
    return (
        selected_doc_versions,
        sorted(selected_fragment_ids),
        sorted(set(selected_claim_set_artifact_ids)),
        norm_claim_ids,
        sorted(provision_index_artifact_ids),
        sorted(set(warnings)),
    )


def _load_claims_by_id(
    *,
    cas: FileSystemCAS,
    claim_ids: list[str],
    claim_artifact_ids_by_id: dict[str, str],
) -> dict[str, Claim]:
    out: dict[str, Claim] = {}
    for claim_id in sorted(set(claim_ids)):
        artifact_id = claim_artifact_ids_by_id.get(claim_id)
        if artifact_id is None:
            raise LexValidationError(f"missing claim artifact for claim_id={claim_id}")
        claim = load_claim(cas, artifact_id)
        if claim.claim_id != claim_id:
            raise LexValidationError(
                f"claim artifact mismatch: expected {claim_id}, got {claim.claim_id}"
            )
        out[claim_id] = claim
    return out


def _load_conflict_sets(
    *,
    cas: FileSystemCAS,
    conflict_set_artifact_ids: list[str],
) -> dict[str, ConflictSet]:
    out: dict[str, ConflictSet] = {}
    for artifact_id in sorted(set(conflict_set_artifact_ids)):
        payload = load_json_artifact(cas, artifact_id)
        conflict_set = ConflictSet.model_validate(payload)
        out[conflict_set.conflict_set_id] = conflict_set
    return out


def _build_canonical_claim_ids(
    *,
    claim_ids: list[str],
    conflict_sets_by_id: dict[str, ConflictSet],
    winner_by_conflict_set: dict[str, str],
) -> tuple[list[str], dict[str, str]]:
    member_claim_ids = {
        claim_id
        for conflict_set in conflict_sets_by_id.values()
        for claim_id in conflict_set.member_claim_ids
    }

    winners = set(winner_by_conflict_set.values())
    canonical = winners.union(set(claim_ids) - member_claim_ids)
    canonical_claim_ids = sorted(canonical)

    conflict_set_by_winner: dict[str, str] = {}
    for conflict_set_id, winner in sorted(winner_by_conflict_set.items()):
        existing = conflict_set_by_winner.get(winner)
        if existing is None or conflict_set_id < existing:
            conflict_set_by_winner[winner] = conflict_set_id

    return canonical_claim_ids, conflict_set_by_winner


def _extractor_ids_by_claim(
    *,
    cas: FileSystemCAS,
    claim_set_artifact_ids: list[str],
) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for artifact_id in sorted(set(claim_set_artifact_ids)):
        payload = load_json_artifact(cas, artifact_id)
        extractor_id = payload.get("extractor_id")
        if not isinstance(extractor_id, str):
            continue
        claim_rows = payload.get("claims")
        if not isinstance(claim_rows, list):
            continue
        for row in claim_rows:
            if not isinstance(row, dict):
                continue
            claim_id = row.get("claim_id")
            if isinstance(claim_id, str):
                mapping.setdefault(claim_id, extractor_id)
    return mapping


def _trust_by_target(
    *,
    cas: FileSystemCAS,
    trust_assessment_artifact_ids_by_id: dict[str, str],
) -> dict[str, TrustAssessment]:
    mapping: dict[str, TrustAssessment] = {}
    for trust_assessment_id in sorted(trust_assessment_artifact_ids_by_id):
        artifact_id = trust_assessment_artifact_ids_by_id[trust_assessment_id]
        payload = load_json_artifact(cas, artifact_id)
        assessment = TrustAssessment.model_validate(payload)
        target_id = assessment.target_world_id
        current = mapping.get(target_id)
        if current is None or assessment.trust_assessment_id < current.trust_assessment_id:
            mapping[target_id] = assessment
    return mapping


def claims_to_norm_rules(
    *,
    claims_by_id: dict[str, Claim],
    canonical_claim_ids: list[str],
    jurisdiction_norm: str,
    conflict_set_by_winner: dict[str, str],
    trust_by_target: dict[str, TrustAssessment],
    extractor_id_by_claim: dict[str, str],
) -> list[NormRule]:
    """Convert canonical claim winners into deterministic ``NormRule`` records.

    Args:
        claims_by_id: Loaded claim payloads keyed by claim id.
        canonical_claim_ids: Winning claim ids after conflict resolution plus non-conflicting claims.
        jurisdiction_norm: Normalized jurisdiction used when deriving applicability metadata.
        conflict_set_by_winner: Mapping from winning claim id to originating conflict-set id.
        trust_by_target: Trust assessments keyed by target world id.
        extractor_id_by_claim: Extractor provenance keyed by claim id.

    Returns:
        Sorted ``NormRule`` records with citations, applicability, and backend metadata linking
        each rule back to source claims, conflict sets, trust scores, and extractors.

    Raises:
        KeyError: If ``canonical_claim_ids`` references a claim missing from ``claims_by_id``.
    """
    sortable: list[tuple[str, str, str, NormRule]] = []

    for claim_id in sorted(set(canonical_claim_ids)):
        claim = claims_by_id[claim_id]

        rule_type = RuleType.OBLIGATION
        if isinstance(claim.props.get("lex"), dict) and bool(claim.props["lex"].get("must_not")):
            rule_type = RuleType.PROHIBITION

        operator: str | None = None
        lex_props = claim.props.get("lex")
        if isinstance(lex_props, dict):
            lex_operator = lex_props.get("operator")
            if isinstance(lex_operator, str) and lex_operator.strip():
                operator = lex_operator.strip()
        if operator is None:
            qualifier_operator = claim.qualifiers.get("op")
            if isinstance(qualifier_operator, str) and qualifier_operator.strip():
                operator = qualifier_operator.strip()

        description = claim.predicate_id
        if claim.unit_id:
            description = f"{description} {claim.value_text} [{claim.unit_id}]"
        else:
            description = f"{description} {claim.value_text}"

        provision_refs: list[NormRef] = []
        for citation in claim.citations:
            if citation.fragment_id is None:
                continue
            provision_refs.append(
                NormRef(
                    provision_id=citation.fragment_id,
                    citations=[citation],
                )
            )
        provision_refs.sort(key=lambda row: row.provision_id)

        applicability = build_norm_applicability(
            claim=claim,
            jurisdiction_norm=jurisdiction_norm,
        )
        trust_assessment = trust_by_target.get(claim.claim_id)

        backend_metadata: dict[str, Any] = {
            "predicate_id": claim.predicate_id,
            "operator": operator,
            "value_text": claim.value_text,
            "value_decimal": (
                str(claim.value_decimal) if claim.value_decimal is not None else None
            ),
            "unit_id": claim.unit_id,
            "source_claim_id": claim.claim_id,
            "conflict_set_id": conflict_set_by_winner.get(claim.claim_id),
            "trust_score": (str(trust_assessment.score) if trust_assessment is not None else None),
            "trust_tier": (trust_assessment.tier.value if trust_assessment is not None else None),
            "extractor_id": extractor_id_by_claim.get(claim.claim_id),
        }

        rule = NormRule(
            norm_id=claim.claim_id,
            provision_refs=provision_refs,
            rule_type=rule_type,
            description=description,
            applicability=applicability,
            backend_metadata=backend_metadata,
        )
        sortable.append(
            (
                claim.predicate_id,
                applicability_key(applicability),
                rule.norm_id,
                rule,
            )
        )

    sortable.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in sortable]


def persist_norm_pack(
    *,
    cas: FileSystemCAS,
    norm_pack: NormPack,
    provision_index_artifact_ids: list[str],
    claim_set_artifact_ids: list[str],
    conflict_resolution_artifact_ids: list[str],
    trust_assessment_artifact_ids: list[str],
) -> str:
    """Persist a ``NormPack`` artifact with complete artifact-level lineage.

    Args:
        cas: Artifact store that receives the serialized NormPack.
        norm_pack: Materialized snapshot to persist.
        provision_index_artifact_ids: Provision-index inputs used for rule extraction.
        claim_set_artifact_ids: Claim-set inputs that contributed canonical claims.
        conflict_resolution_artifact_ids: Conflict-resolution artifacts attached as provenance.
        trust_assessment_artifact_ids: Trust-assessment artifacts attached as provenance.

    Returns:
        Artifact id of the persisted ``polisyos.ir.NormPack`` payload.
    """
    inputs: list[InputRef] = []
    seen: set[tuple[str, str]] = set()

    def _append(role: str, artifact_id: str) -> None:
        key = (role, artifact_id)
        if key in seen:
            return
        seen.add(key)
        inputs.append(
            InputRef(
                artifact_id=ArtifactID.model_validate(artifact_id),
                role=role,
            )
        )

    for artifact_id in sorted(set(provision_index_artifact_ids)):
        _append("provision_index", artifact_id)
    for artifact_id in sorted(set(claim_set_artifact_ids)):
        _append("claim_set", artifact_id)
    for artifact_id in sorted(set(conflict_resolution_artifact_ids)):
        _append("conflict_resolution", artifact_id)
    for artifact_id in sorted(set(trust_assessment_artifact_ids)):
        _append("trust_assessment", artifact_id)

    ref = cas.put_json(
        norm_pack.model_dump(mode="python"),
        opts=PutOptions(
            kind=NORM_PACK_KIND,
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.NormPack", version="1.0"),
            inputs=inputs or None,
        ),
    )
    return str(ref.artifact_id)


def emit_norm_pack_world_facts(
    *,
    norm_pack_artifact_id: str,
) -> tuple[str, list[Any]]:
    """Create world-node facts that expose a persisted NormPack artifact in materialized stores."""
    norm_pack_world_id = artifact_id_to_world_id(
        prefix="artifact",
        artifact_id=norm_pack_artifact_id,
    )
    facts = emit_world_node_facts(
        node_id=norm_pack_world_id,
        kind=NodeKind.ARTIFACT,
        label=None,
        artifact_id=norm_pack_artifact_id,
        props_ref=None,
        provenance=stable_world_provenance_v1(),
    )
    return norm_pack_world_id, facts


def emit_norm_pack_assemble_event(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: NormPackBuildRequest,
    jurisdiction_norm: str,
    as_of_norm: str,
    domain_norm: str | None,
    selected_doc_versions: list[SelectedDocVersion],
    selected_fragment_ids: list[str],
    norm_claim_ids: list[str],
    conflict_set_ids: list[str],
    trust_assessment_ids: list[str],
    claim_set_artifact_ids: list[str],
    provision_index_artifact_ids: list[str],
    conflict_resolution_artifact_ids: list[str],
    norm_pack_world_id: str,
    semantic_facts: list[Any],
    segment_name: str | None,
    counts: dict[str, int],
) -> tuple[str, str, Any]:
    """Persist an ``ASSEMBLE_NORM_PACK`` world event and the corresponding fact segment.

    Returns:
        Tuple of ``(world_event_id, world_event_artifact_id, world_segment_manifest)``.
    """
    inputs: list[WorldObjectRef] = []
    for doc in sorted(selected_doc_versions, key=lambda row: row.doc_version_id):
        inputs.append(WorldObjectRef(world_id=doc.doc_version_id))
    for fragment_id in sorted(set(selected_fragment_ids)):
        inputs.append(WorldObjectRef(world_id=fragment_id))
    for claim_id in sorted(set(norm_claim_ids)):
        inputs.append(WorldObjectRef(world_id=claim_id))
    for conflict_set_id in sorted(set(conflict_set_ids)):
        inputs.append(WorldObjectRef(world_id=conflict_set_id))
    for trust_assessment_id in sorted(set(trust_assessment_ids)):
        inputs.append(WorldObjectRef(world_id=trust_assessment_id))
    for artifact_id in sorted(set(claim_set_artifact_ids)):
        inputs.append(WorldObjectRef(artifact_id=artifact_id))
    for artifact_id in sorted(set(provision_index_artifact_ids)):
        inputs.append(WorldObjectRef(artifact_id=artifact_id))
    for artifact_id in sorted(set(conflict_resolution_artifact_ids)):
        inputs.append(WorldObjectRef(artifact_id=artifact_id))

    outputs = [WorldObjectRef(world_id=norm_pack_world_id)]
    props = {
        "pipeline": ASSEMBLY_PIPELINE_ID,
        "jurisdiction": jurisdiction_norm,
        "as_of": as_of_norm,
        "domain": domain_norm,
        "selection_policy_id": request.selection_policy_id,
        "conflict_policy_id": request.conflict_policy_id,
        "trust_policy_id": request.trust_policy_id,
        "counts": counts,
    }
    event = build_deterministic_world_event(
        event_kind=EventKind.ASSEMBLE_NORM_PACK,
        agent_id="prov.agent.lex_normpack",
        agent_type=ProvAgentType.SYSTEM,
        agent_label="Lex NormPack",
        activity_id="prov.activity.lex_normpack.assemble",
        activity_type=ProvActivityType.ASSEMBLE_NORM_PACK,
        activity_label="Assemble norm pack",
        inputs=inputs,
        outputs=outputs,
        props=props,
    )
    event_id = event.event_id
    facts = list(semantic_facts)
    event_artifact_id = persist_world_event_with_facts(cas=cas, event=event, facts=facts)

    manifest = write_world_fact_segment(
        facts,
        fact_log_root=fact_log_root,
        segment_name=segment_name or "lex_normpack_assemble",
    )
    append_world_segment_index(manifest, fact_log_root=fact_log_root)

    return event_id, event_artifact_id, manifest


def assemble_norm_pack(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    request: NormPackBuildRequest,
    db: SimulationDB | None = None,
    segment_name: str | None = None,
) -> NormPackBuildResult:
    """Build and persist a NormPack snapshot for one jurisdiction/date/domain slice.

    The assembler prefers explicit ``claim_set_artifact_ids`` when provided, otherwise it resolves
    active document versions from the corpus and extracts claims from selected provisions. Static
    provider outputs are used only when no local documents or claim sets are available.
    """
    normalized_request, jurisdiction_norm, as_of_norm, domain_norm = _normalize_request(request)
    run_suffix = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")

    warnings: list[str] = []
    if normalized_request.budgets.max_docs == 0:
        warnings.append("warning:max_docs_zero")
    if normalized_request.budgets.max_provisions == 0:
        warnings.append("warning:max_provisions_zero")
    if normalized_request.budgets.max_claims == 0:
        warnings.append("warning:max_claims_zero")

    components_index, _ = build_components_index(
        groups=[
            ENTRY_POINT_GROUP_NORM_PACK_PROVIDERS,
            ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS,
            ENTRY_POINT_GROUP_LEX_EXTRACTORS,
        ],
        include_dev_scan=True,
    )

    provider_bootstrap = discover_and_bootstrap_providers(components_index=components_index)
    if provider_bootstrap.errors:
        warnings.extend(
            [
                f"warning:normpack_provider_bootstrap_error:{msg}"
                for msg in provider_bootstrap.errors
            ]
        )

    direct_claim_set_artifact_ids = sorted(set(normalized_request.claim_set_artifact_ids or []))
    doc_source_ids: list[str] = []
    if not direct_claim_set_artifact_ids:
        doc_source_ids = select_doc_sources(
            cas=cas,
            fact_log_root=fact_log_root,
            request=normalized_request,
        )

    provider_record = get_norm_pack_provider_registry().resolve(
        jurisdiction=jurisdiction_norm,
        domain=domain_norm,
    )
    if provider_record is not None and not doc_source_ids and not direct_claim_set_artifact_ids:
        try:
            provided = provider_record.provider.get_static_norm_pack(
                cas,
                jurisdiction=jurisdiction_norm,
                domain=domain_norm,
                as_of=as_of_norm,
            )
            norm_pack_artifact_id: str
            norm_pack: NormPack
            if isinstance(provided, ArtifactRef):
                norm_pack_artifact_id = str(provided.artifact_id)
                payload = load_json_artifact(cas, norm_pack_artifact_id)
                norm_pack = NormPack.model_validate(payload)
            elif isinstance(provided, str):
                norm_pack_artifact_id = provided
                payload = load_json_artifact(cas, norm_pack_artifact_id)
                norm_pack = NormPack.model_validate(payload)
            else:
                norm_pack = (
                    provided
                    if isinstance(provided, NormPack)
                    else NormPack.model_validate(provided)
                )
                norm_pack_artifact_id = persist_norm_pack(
                    cas=cas,
                    norm_pack=norm_pack,
                    provision_index_artifact_ids=[],
                    claim_set_artifact_ids=[],
                    conflict_resolution_artifact_ids=[],
                    trust_assessment_artifact_ids=[],
                )

            norm_pack_world_id, semantic_facts = emit_norm_pack_world_facts(
                norm_pack_artifact_id=norm_pack_artifact_id,
            )
            counts = {
                "docs": 0,
                "provisions": 0,
                "claims": 0,
                "conflicts": 0,
                "rules": len(norm_pack.norms),
            }
            world_event_id, world_event_artifact_id, world_segment_manifest = (
                emit_norm_pack_assemble_event(
                    cas=cas,
                    fact_log_root=fact_log_root,
                    request=normalized_request,
                    jurisdiction_norm=jurisdiction_norm,
                    as_of_norm=as_of_norm,
                    domain_norm=domain_norm,
                    selected_doc_versions=[],
                    selected_fragment_ids=[],
                    norm_claim_ids=[],
                    conflict_set_ids=[],
                    trust_assessment_ids=[],
                    claim_set_artifact_ids=[],
                    provision_index_artifact_ids=[],
                    conflict_resolution_artifact_ids=[],
                    norm_pack_world_id=norm_pack_world_id,
                    semantic_facts=semantic_facts,
                    segment_name=segment_name or f"lex_normpack_provider_{run_suffix}",
                    counts=counts,
                )
            )
            provider_warnings = sorted(set(warnings))
            return NormPackBuildResult(
                request=normalized_request,
                jurisdiction_norm=jurisdiction_norm,
                as_of_norm=as_of_norm,
                domain_norm=domain_norm,
                selected_doc_versions=[],
                selected_fragment_ids=[],
                claim_set_artifact_ids=[],
                norm_claim_ids=[],
                conflict_set_ids=[],
                conflict_resolution_artifact_ids=[],
                trust_assessment_ids=[],
                norm_pack_artifact_id=norm_pack_artifact_id,
                norm_pack_world_id=norm_pack_world_id,
                world_event_id=world_event_id,
                world_event_artifact_id=world_event_artifact_id,
                world_segment_manifest=world_segment_manifest,
                built_by=f"provider:{provider_record.component_id}",
                warnings=provider_warnings,
            )
        except Exception as exc:
            warnings.append(
                f"warning:normpack_provider_failed:{provider_record.component_id}:{exc}"
            )
    elif provider_record is not None and (doc_source_ids or direct_claim_set_artifact_ids):
        warnings.append(
            f"warning:normpack_provider_skipped_local_docs_present:{provider_record.component_id}"
        )

    extractor_bootstrap = discover_and_bootstrap_extractors(components_index=components_index)
    if extractor_bootstrap.errors:
        warnings.extend(
            [f"warning:extractor_bootstrap_error:{msg}" for msg in extractor_bootstrap.errors]
        )

    if direct_claim_set_artifact_ids:
        (
            selected_doc_versions,
            selected_fragment_ids,
            claim_set_artifact_ids,
            norm_claim_ids,
            provision_index_artifact_ids,
            claim_set_warnings,
        ) = _select_claim_sets(
            cas=cas,
            claim_set_artifact_ids=direct_claim_set_artifact_ids,
            jurisdiction_norm=jurisdiction_norm,
            domain_norm=domain_norm,
            as_of_norm=as_of_norm,
        )
        warnings.extend(claim_set_warnings)
        selected_provisions: list[ProvisionSelection] = []
        if normalized_request.doc_source_ids:
            warnings.append("warning:doc_source_ids_ignored_in_claim_set_mode")
    else:
        selected_doc_versions, source_warnings = select_active_doc_versions(
            cas=cas,
            fact_log_root=fact_log_root,
            request=normalized_request,
            jurisdiction_norm=jurisdiction_norm,
            as_of_norm=as_of_norm,
            doc_source_ids=doc_source_ids,
        )
        warnings.extend(source_warnings)

        if not selected_doc_versions:
            warnings.append("warning:no_doc_versions_selected")

        selected_provisions, selected_fragment_ids, provision_warnings = _select_provisions(
            cas=cas,
            selected_doc_versions=selected_doc_versions,
            domain_norm=domain_norm,
            max_provisions=normalized_request.budgets.max_provisions,
        )
        warnings.extend(provision_warnings)

        if not selected_fragment_ids:
            warnings.append("warning:no_provisions_selected")

        provision_index_artifact_ids = sorted(
            {row.provision_index_artifact_id for row in selected_provisions}
        )

        extract_result = extract_norm_claims(
            cas=cas,
            fact_log_root=fact_log_root,
            jurisdiction_norm=jurisdiction_norm,
            domain_norm=domain_norm,
            extractor_id=DEFAULT_EXTRACTOR_ID,
            provisions=selected_provisions,
            max_claims=normalized_request.budgets.max_claims,
            normalize_claim_sets=True,
            segment_name=f"lex_normpack_extract_claims_{run_suffix}",
        )
        warnings.extend(extract_result.warnings)

        claim_set_artifact_ids = sorted(set(extract_result.claim_set_artifact_ids))
        norm_claim_ids = sorted(set(extract_result.claim_ids))
    if not selected_doc_versions:
        warnings.append("warning:no_doc_versions_selected")
    if not selected_fragment_ids:
        warnings.append("warning:no_provisions_selected")
    if not norm_claim_ids:
        warnings.append("warning:no_norm_claims_selected")

    conflict_set_ids: list[str] = []
    conflict_set_artifact_ids: list[str] = []
    conflict_resolution_artifact_ids: list[str] = []
    trust_assessment_ids: list[str] = []
    trust_assessment_artifact_ids_by_id: dict[str, str] = {}
    winner_by_conflict_set: dict[str, str] = {}

    if norm_claim_ids:
        resolve_result = resolve_conflicts(
            cas=cas,
            fact_log_root=fact_log_root,
            db=db,
            conflict_set_ids=None,
            claim_ids=norm_claim_ids,
            claim_set_artifact_ids=claim_set_artifact_ids,
            policy_id=normalized_request.conflict_policy_id,
            segment_name=f"lex_normpack_resolve_conflicts_{run_suffix}",
        )
        conflict_set_ids = sorted(set(resolve_result.conflict_set_ids))
        conflict_set_artifact_ids = sorted(set(resolve_result.conflict_set_artifact_ids))
        winner_by_conflict_set = dict(resolve_result.winner_by_conflict_set)
        conflict_resolution_artifact_ids = sorted(
            set(resolve_result.conflict_resolution_artifact_ids)
        )
        trust_assessment_ids = sorted(set(resolve_result.trust_assessment_ids))
        trust_assessment_artifact_ids_by_id = dict(
            resolve_result.trust_assessment_artifact_ids_by_id
        )

    conflict_sets_by_id = _load_conflict_sets(
        cas=cas,
        conflict_set_artifact_ids=conflict_set_artifact_ids,
    )

    canonical_claim_ids, conflict_set_by_winner = _build_canonical_claim_ids(
        claim_ids=norm_claim_ids,
        conflict_sets_by_id=conflict_sets_by_id,
        winner_by_conflict_set=winner_by_conflict_set,
    )

    claim_artifact_ids_by_id = claim_artifact_ids_by_claim_id(
        cas=cas,
        claim_set_artifact_ids=claim_set_artifact_ids,
    )
    claims_by_id = _load_claims_by_id(
        cas=cas,
        claim_ids=canonical_claim_ids,
        claim_artifact_ids_by_id=claim_artifact_ids_by_id,
    )

    trust_by_target = _trust_by_target(
        cas=cas,
        trust_assessment_artifact_ids_by_id=trust_assessment_artifact_ids_by_id,
    )
    extractor_id_by_claim = _extractor_ids_by_claim(
        cas=cas,
        claim_set_artifact_ids=claim_set_artifact_ids,
    )

    norm_rules = claims_to_norm_rules(
        claims_by_id=claims_by_id,
        canonical_claim_ids=canonical_claim_ids,
        jurisdiction_norm=jurisdiction_norm,
        conflict_set_by_winner=conflict_set_by_winner,
        trust_by_target=trust_by_target,
        extractor_id_by_claim=extractor_id_by_claim,
    )

    selected_doc_source_ids = sorted({row.doc_source_id for row in selected_doc_versions})
    selected_doc_version_ids = sorted({row.doc_version_id for row in selected_doc_versions})

    algorithm_versions = {
        "norm_claim_extractor_id": DEFAULT_EXTRACTOR_ID,
        "claims_normalize_version": (
            CLAIMS_NORMALIZE_VERSION if claim_set_artifact_ids else "none"
        ),
        "conflict_trust_algorithm_version": CONFLICT_TRUST_ALGORITHM_VERSION,
        "conflict_resolution_algorithm_version": CONFLICT_RESOLUTION_ALGORITHM_VERSION,
    }

    pack_id_payload = {
        "request": {
            "jurisdiction": jurisdiction_norm,
            "as_of": as_of_norm,
            "domain": domain_norm,
        },
        "selection_policy_id": normalized_request.selection_policy_id,
        "conflict_policy_id": normalized_request.conflict_policy_id,
        "trust_policy_id": normalized_request.trust_policy_id,
        "selected_doc_version_ids": selected_doc_version_ids,
        "canonical_claim_ids": canonical_claim_ids,
        "algorithm_versions": algorithm_versions,
    }
    pack_id = stable_world_id_from_canon(prefix="normpack", payload=pack_id_payload)

    metadata_warnings = sorted(set(warnings))
    norm_pack = NormPack(
        pack_id=pack_id,
        jurisdiction=jurisdiction_norm,
        effective_date=as_of_norm,
        norms=norm_rules,
        metadata={
            "selection_policy_id": normalized_request.selection_policy_id,
            "conflict_policy_id": normalized_request.conflict_policy_id,
            "trust_policy_id": normalized_request.trust_policy_id,
            "domain": domain_norm,
            "source_doc_version_ids": selected_doc_version_ids,
            "source_doc_source_ids": selected_doc_source_ids,
            "source_fragment_ids": selected_fragment_ids,
            "algorithm_versions": algorithm_versions,
            "budgets": asdict(normalized_request.budgets),
            "actual_counts": {
                "docs": len(selected_doc_versions),
                "provisions": len(selected_fragment_ids),
                "claims": len(norm_claim_ids),
                "canonical_claims": len(canonical_claim_ids),
                "conflicts": len(conflict_set_ids),
                "rules": len(norm_rules),
            },
            "warnings": metadata_warnings,
        },
    )

    trust_assessment_artifact_ids = [
        trust_assessment_artifact_ids_by_id[trust_id]
        for trust_id in sorted(trust_assessment_artifact_ids_by_id)
    ]
    norm_pack_artifact_id = persist_norm_pack(
        cas=cas,
        norm_pack=norm_pack,
        provision_index_artifact_ids=provision_index_artifact_ids,
        claim_set_artifact_ids=claim_set_artifact_ids,
        conflict_resolution_artifact_ids=conflict_resolution_artifact_ids,
        trust_assessment_artifact_ids=trust_assessment_artifact_ids,
    )

    norm_pack_world_id, semantic_facts = emit_norm_pack_world_facts(
        norm_pack_artifact_id=norm_pack_artifact_id,
    )

    counts = {
        "docs": len(selected_doc_versions),
        "provisions": len(selected_fragment_ids),
        "claims": len(norm_claim_ids),
        "conflicts": len(conflict_set_ids),
        "rules": len(norm_rules),
    }
    world_event_id, world_event_artifact_id, world_segment_manifest = emit_norm_pack_assemble_event(
        cas=cas,
        fact_log_root=fact_log_root,
        request=normalized_request,
        jurisdiction_norm=jurisdiction_norm,
        as_of_norm=as_of_norm,
        domain_norm=domain_norm,
        selected_doc_versions=selected_doc_versions,
        selected_fragment_ids=selected_fragment_ids,
        norm_claim_ids=norm_claim_ids,
        conflict_set_ids=conflict_set_ids,
        trust_assessment_ids=trust_assessment_ids,
        claim_set_artifact_ids=claim_set_artifact_ids,
        provision_index_artifact_ids=provision_index_artifact_ids,
        conflict_resolution_artifact_ids=conflict_resolution_artifact_ids,
        norm_pack_world_id=norm_pack_world_id,
        semantic_facts=semantic_facts,
        segment_name=segment_name or f"lex_normpack_assemble_{run_suffix}",
        counts=counts,
    )

    return NormPackBuildResult(
        request=normalized_request,
        jurisdiction_norm=jurisdiction_norm,
        as_of_norm=as_of_norm,
        domain_norm=domain_norm,
        selected_doc_versions=selected_doc_versions,
        selected_fragment_ids=selected_fragment_ids,
        claim_set_artifact_ids=claim_set_artifact_ids,
        norm_claim_ids=norm_claim_ids,
        conflict_set_ids=conflict_set_ids,
        conflict_resolution_artifact_ids=conflict_resolution_artifact_ids,
        trust_assessment_ids=trust_assessment_ids,
        norm_pack_artifact_id=norm_pack_artifact_id,
        norm_pack_world_id=norm_pack_world_id,
        world_event_id=world_event_id,
        world_event_artifact_id=world_event_artifact_id,
        world_segment_manifest=world_segment_manifest,
        built_by=f"pipeline:{ASSEMBLY_PIPELINE_ID}",
        warnings=metadata_warnings,
    )


__all__ = [
    "assemble_norm_pack",
    "claims_to_norm_rules",
    "emit_norm_pack_assemble_event",
    "emit_norm_pack_world_facts",
    "persist_norm_pack",
]
