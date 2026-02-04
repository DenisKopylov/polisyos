from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path
import time
from typing import Any

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.contracts.scholar import BudgetsV1, ResearchIntent, SourceSpec, ThresholdsV1
from polisyos.fabric.claims import extract_claims_from_doc, normalize_claims, resolve_conflicts
from polisyos.fabric.claims.errors import ClaimPipelineError
from polisyos.fabric.claims.extractor_registry import (
    discover_and_bootstrap_extractors,
    get_extractor_registry,
)
from polisyos.fabric.claims.persist import load_claim, load_doc_meta, load_json_artifact
from polisyos.fabric.docs import DocSourceSpec, chunk_doc, ingest_doc_bytes, normalize_doc, structure_doc
from polisyos.fabric.docs.errors import DocPipelineError
from polisyos.fabric.io.db import SimulationDB
from polisyos.ir.world.trust import TrustAssessment, TrustTier

from polisyos.scholar.discover import fetch_url, normalize_seed_sources, read_local_file
from polisyos.scholar.errors import (
    ScholarAcquireError,
    ScholarBundleError,
    ScholarClaimsError,
    ScholarDiscoverError,
    ScholarDocsError,
    ScholarError,
    ScholarReconcileError,
    ScholarValidationError,
)
from polisyos.scholar.orchestrator.bundle import (
    build_knowledge_bundle_payload,
    compute_bundle_id,
    persist_bundle_and_event,
)
from polisyos.scholar.policies import ScholarPolicy
from polisyos.scholar.types import (
    AcquireResult,
    ClaimsPipelineRefs,
    DocPipelineRefs,
    EnrichResultV1,
    EnrichmentReportV1,
    ReconcileRefs,
)

_TRUST_RANK = {
    TrustTier.LOW: 1,
    TrustTier.MEDIUM: 2,
    TrustTier.HIGH: 3,
}


def _coerce_positive_int(value: int | float | str | None, *, field: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        parsed = value
    elif isinstance(value, float):
        if not value.is_integer():
            raise ScholarValidationError(
                f"{field} must be an integer",
                stage="validation",
                details={"field": field, "value": str(value)},
            )
        parsed = int(value)
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped.isdigit():
            raise ScholarValidationError(
                f"{field} must be a positive integer string",
                stage="validation",
                details={"field": field, "value": value},
            )
        parsed = int(stripped)
    else:
        raise ScholarValidationError(
            f"{field} has unsupported type",
            stage="validation",
            details={"field": field, "type": type(value).__name__},
        )

    if parsed <= 0:
        raise ScholarValidationError(
            f"{field} must be > 0",
            stage="validation",
            details={"field": field, "value": parsed},
        )
    return parsed


def _source_props(source: SourceSpec) -> dict[str, str]:
    return source.props


def _doc_source_from_source(
    source: SourceSpec,
    *,
    canonical_url: str | None,
    source_locator: str | None,
) -> DocSourceSpec:
    props = _source_props(source)
    return DocSourceSpec(
        canonical_url=canonical_url,
        official_id=None,
        source_locator=source_locator,
        license=source.license,
        jurisdiction=props.get("jurisdiction"),
        language=props.get("language"),
        source_type=props.get("source_type"),
        title=props.get("title"),
        publisher=props.get("publisher"),
    )


def _acquire_bytes(source: SourceSpec, *, max_bytes: int | None) -> AcquireResult:
    if source.kind != "bytes" or source.data is None or source.source_locator is None:
        raise ScholarValidationError(
            "bytes source requires data and source_locator",
            stage="acquire",
            source_identity=source.source_locator,
        )

    raw_bytes = source.data
    if max_bytes is not None and len(raw_bytes) > max_bytes:
        raise ScholarAcquireError(
            "bytes source exceeds max_bytes_per_doc",
            source_identity=source.source_locator,
            details={"bytes": len(raw_bytes), "max_bytes": max_bytes},
        )

    mime = source.mime_hint.strip() if source.mime_hint else "application/octet-stream"
    doc_source = _doc_source_from_source(
        source,
        canonical_url=None,
        source_locator=source.source_locator,
    )
    return AcquireResult(
        source=source,
        source_identity=source.source_locator,
        raw_bytes=raw_bytes,
        mime=mime,
        doc_source=doc_source,
    )


def _resolve_budgets(intent: ResearchIntent, policy: ScholarPolicy) -> BudgetsV1:
    legacy = intent.budgets or {}
    explicit = intent.budgets_v1

    max_docs = (
        explicit.max_docs
        if explicit is not None and explicit.max_docs is not None
        else _coerce_positive_int(legacy.get("max_docs"), field="max_docs")
    )
    max_bytes_total = (
        explicit.max_bytes_total
        if explicit is not None and explicit.max_bytes_total is not None
        else _coerce_positive_int(legacy.get("max_bytes_total"), field="max_bytes_total")
    )
    max_claims_total = (
        explicit.max_claims_total
        if explicit is not None and explicit.max_claims_total is not None
        else _coerce_positive_int(legacy.get("max_claims_total"), field="max_claims_total")
    )
    max_bytes_per_doc = (
        explicit.max_bytes_per_doc
        if explicit is not None and explicit.max_bytes_per_doc is not None
        else _coerce_positive_int(legacy.get("max_bytes_per_doc"), field="max_bytes_per_doc")
    )

    return BudgetsV1(
        max_docs=max_docs or policy.budgets.max_docs,
        max_bytes_total=max_bytes_total or policy.budgets.max_bytes_total,
        max_claims_total=max_claims_total or policy.budgets.max_claims_total,
        max_bytes_per_doc=max_bytes_per_doc or policy.budgets.max_bytes_per_doc,
    )


def _resolve_thresholds(intent: ResearchIntent, policy: ScholarPolicy) -> ThresholdsV1:
    if intent.thresholds_v1 is not None:
        return intent.thresholds_v1
    return ThresholdsV1(min_doc_trust_tier=policy.thresholds.min_doc_trust_tier)


def _validate_intent(intent: ResearchIntent) -> None:
    if intent.domain is None or not intent.domain.strip():
        raise ScholarValidationError("intent.domain is required", stage="validation")
    if not intent.seed_sources:
        raise ScholarValidationError("intent.seed_sources is required", stage="validation")


def _intent_jurisdictions(intent: ResearchIntent) -> list[str]:
    values = {value for value in intent.jurisdictions if value}
    if intent.jurisdiction:
        values.add(intent.jurisdiction)
    return sorted(values)


def _intent_source_payload(source: SourceSpec) -> dict[str, Any]:
    payload = {
        "kind": source.kind,
        "canonical_url": source.canonical_url,
        "official_id": source.official_id,
        "source_locator": source.source_locator,
        "license": source.license,
        "mime_hint": source.mime_hint,
        "props": {key: source.props[key] for key in sorted(source.props)},
    }
    if source.kind == "local_file":
        payload["path"] = source.path
    if source.kind == "url":
        payload["url"] = source.url
    return payload


def _intent_payload(
    *,
    intent: ResearchIntent,
    sources: list[SourceSpec],
    budgets: BudgetsV1,
    thresholds: ThresholdsV1,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "domain": intent.domain,
        "topic": intent.topic,
        "jurisdictions": _intent_jurisdictions(intent),
        "time_window": intent.time_window.model_dump(mode="python") if intent.time_window else None,
        "seed_sources": [_intent_source_payload(source) for source in sources],
        "claim_targets": sorted(set(intent.claim_targets or [])),
        "budgets_v1": budgets.model_dump(mode="python", exclude_none=True),
        "thresholds_v1": thresholds.model_dump(mode="python"),
        "required_outputs": sorted(set(intent.required_outputs)),
        "notes": list(intent.notes),
    }
    return {key: value for key, value in payload.items() if value is not None}


def _intent_core_for_bundle_id(
    *,
    intent: ResearchIntent,
    sources: list[SourceSpec],
    budgets: BudgetsV1,
    thresholds: ThresholdsV1,
) -> dict[str, Any]:
    seed_identities = []
    for source in sources:
        identity: dict[str, str] = {"kind": source.kind}
        if source.canonical_url is not None:
            identity["canonical_url"] = source.canonical_url
        if source.official_id is not None:
            identity["official_id"] = source.official_id
        if source.source_locator is not None:
            identity["source_locator"] = source.source_locator
        seed_identities.append(identity)

    return {
        "domain": intent.domain,
        "jurisdictions": _intent_jurisdictions(intent),
        "time_window": {
            "start": intent.time_window.start if intent.time_window else None,
            "end": intent.time_window.end if intent.time_window else None,
        },
        "seed_sources": seed_identities,
        "claim_targets": sorted(set(intent.claim_targets or [])),
        "budgets_v1": budgets.model_dump(mode="python", exclude_none=True),
        "thresholds_v1": thresholds.model_dump(mode="python"),
    }


def _doc_tiers_from_reconcile(
    *,
    cas: FileSystemCAS,
    trust_artifact_by_id: dict[str, str],
) -> tuple[dict[str, TrustTier], dict[str, int]]:
    doc_tier_by_version: dict[str, TrustTier] = {}
    tiers_histogram = {"high": 0, "medium": 0, "low": 0}
    for trust_id in sorted(trust_artifact_by_id):
        artifact_id = trust_artifact_by_id[trust_id]
        payload = load_json_artifact(cas, artifact_id)
        assessment = TrustAssessment.model_validate(payload)
        tiers_histogram[assessment.tier.value] += 1
        if assessment.target_world_id.startswith("docv."):
            doc_tier_by_version[assessment.target_world_id] = assessment.tier
    return doc_tier_by_version, tiers_histogram


def enrich_topic(
    *,
    cas: FileSystemCAS,
    fact_log_root: Path,
    intent: ResearchIntent,
    db: SimulationDB | None = None,
    policy: ScholarPolicy | None = None,
) -> EnrichResultV1:
    scholar_policy = policy or ScholarPolicy()
    run_token = str(time.time_ns())

    _validate_intent(intent)
    budgets = _resolve_budgets(intent, scholar_policy)
    thresholds = _resolve_thresholds(intent, scholar_policy)

    try:
        sources = normalize_seed_sources(intent.seed_sources, max_docs=budgets.max_docs)
    except ScholarError:
        raise
    except Exception as exc:  # pragma: no cover - defensive wrapper
        raise ScholarDiscoverError(f"discover stage failed: {exc}") from exc

    acquired_docs: list[AcquireResult] = []
    bytes_total = 0
    acquire_notes: list[str] = []

    for source in sources:
        if source.kind == "local_file":
            acquired = read_local_file(source, max_bytes=budgets.max_bytes_per_doc)
        elif source.kind == "bytes":
            acquired = _acquire_bytes(source, max_bytes=budgets.max_bytes_per_doc)
        elif source.kind == "url":
            acquired = fetch_url(
                source,
                timeout_s=scholar_policy.acquire.timeout_s,
                user_agent=scholar_policy.acquire.user_agent,
                max_bytes=budgets.max_bytes_per_doc,
            )
        else:
            raise ScholarAcquireError(
                f"unsupported source kind: {source.kind}",
                source_identity=source.source_locator,
            )

        next_total = bytes_total + len(acquired.raw_bytes)
        if budgets.max_bytes_total is not None and next_total > budgets.max_bytes_total:
            acquire_notes.append("stopped:max_bytes_total")
            break
        acquired_docs.append(acquired)
        bytes_total = next_total

    docs_refs: list[DocPipelineRefs] = []
    docs_skipped = {"normalize": 0, "structure": 0, "chunk": 0}
    try:
        for idx, acquired in enumerate(acquired_docs):
            ingest_result = ingest_doc_bytes(
                cas=cas,
                fact_log_root=fact_log_root,
                source=acquired.doc_source,
                raw_bytes=acquired.raw_bytes,
                mime=acquired.mime,
                segment_name=f"scholar_docs_ingest_{idx}_{run_token}",
            )

            current_meta_artifact_id = ingest_result.doc_meta_artifact_id
            meta = load_doc_meta(cas, current_meta_artifact_id)

            if meta.normalized_ref is None:
                normalize_result = normalize_doc(
                    cas=cas,
                    fact_log_root=fact_log_root,
                    doc_meta_artifact_id=current_meta_artifact_id,
                    options=scholar_policy.docs.normalize_options,
                    segment_name=f"scholar_docs_normalize_{idx}_{run_token}",
                )
                current_meta_artifact_id = normalize_result.doc_meta_artifact_id
            else:
                docs_skipped["normalize"] += 1

            meta = load_doc_meta(cas, current_meta_artifact_id)
            fragment_count = 0
            if meta.structure_ref is None:
                structure_result = structure_doc(
                    cas=cas,
                    fact_log_root=fact_log_root,
                    doc_meta_artifact_id=current_meta_artifact_id,
                    options=scholar_policy.docs.structure_options,
                    segment_name=f"scholar_docs_structure_{idx}_{run_token}",
                )
                current_meta_artifact_id = structure_result.doc_meta_artifact_id
                fragment_count = len(structure_result.fragment_ids)
            else:
                docs_skipped["structure"] += 1

            meta = load_doc_meta(cas, current_meta_artifact_id)
            chunk_fragment_count = 0
            if meta.chunks_ref is None:
                chunk_result = chunk_doc(
                    cas=cas,
                    fact_log_root=fact_log_root,
                    doc_meta_artifact_id=current_meta_artifact_id,
                    options=scholar_policy.docs.chunk_options,
                    segment_name=f"scholar_docs_chunk_{idx}_{run_token}",
                )
                current_meta_artifact_id = chunk_result.doc_meta_artifact_id
                chunk_fragment_count = len(chunk_result.chunk_fragment_ids)
            else:
                docs_skipped["chunk"] += 1

            final_meta = load_doc_meta(cas, current_meta_artifact_id)
            if fragment_count == 0 and final_meta.structure_ref is not None:
                structure_payload = load_json_artifact(cas, final_meta.structure_ref)
                anchors = structure_payload.get("anchors")
                if isinstance(anchors, list):
                    fragment_count = len(anchors)
            if chunk_fragment_count == 0 and final_meta.chunks_ref is not None:
                chunks_payload = load_json_artifact(cas, final_meta.chunks_ref)
                chunks = chunks_payload.get("chunks")
                if isinstance(chunks, list):
                    chunk_fragment_count = len(chunks)

            docs_refs.append(
                DocPipelineRefs(
                    doc_source_id=final_meta.doc_source_id,
                    doc_version_id=final_meta.doc_version_id,
                    doc_meta_artifact_id=current_meta_artifact_id,
                    normalized_ref=final_meta.normalized_ref,
                    structure_ref=final_meta.structure_ref,
                    chunks_ref=final_meta.chunks_ref,
                    fragment_count=fragment_count,
                    chunk_fragment_count=chunk_fragment_count,
                )
            )
    except DocPipelineError as exc:
        raise ScholarDocsError(f"docs stage failed: {exc}") from exc

    claim_refs: list[ClaimsPipelineRefs] = []
    claim_ids_set: set[str] = set()
    claim_artifact_by_id: dict[str, str] = {}
    normalized_claim_set_artifact_ids: list[str] = []
    extractor_ids_used: set[str] = set()

    extractor_bootstrap_report = discover_and_bootstrap_extractors()
    if extractor_bootstrap_report.errors:
        raise ScholarClaimsError(
            "claims extractor bootstrap failed",
            details={"errors": extractor_bootstrap_report.errors},
        )

    try:
        remaining_claim_budget = budgets.max_claims_total
        for idx, doc_ref in enumerate(docs_refs):
            if remaining_claim_budget is not None and remaining_claim_budget <= 0:
                break

            doc_meta = load_doc_meta(cas, doc_ref.doc_meta_artifact_id)
            resolved_extractor_id, _ = get_extractor_registry().select(
                domain=intent.domain,
                jurisdiction=doc_meta.jurisdiction or intent.jurisdiction,
                language=doc_meta.language,
                mime=doc_meta.mime,
                preferred_id=scholar_policy.claims.extractor_id,
            )
            extractor_ids_used.add(resolved_extractor_id)

            extract_options = replace(
                scholar_policy.claims.extract_options,
                max_claims_total=remaining_claim_budget,
            )
            extracted = extract_claims_from_doc(
                cas=cas,
                fact_log_root=fact_log_root,
                doc_meta_artifact_id=doc_ref.doc_meta_artifact_id,
                extractor_id=resolved_extractor_id,
                options=extract_options,
                segment_name=f"scholar_claims_extract_{idx}_{run_token}",
            )
            normalized = normalize_claims(
                cas=cas,
                fact_log_root=fact_log_root,
                claim_set_artifact_id=extracted.claim_set_artifact_id,
                options=scholar_policy.claims.normalize_options,
                segment_name=f"scholar_claims_normalize_{idx}_{run_token}",
            )

            evidence_refs = [
                ref
                for ref in [extracted.evidence_ref, normalized.evidence_ref]
                if isinstance(ref, str)
            ]
            claim_refs.append(
                ClaimsPipelineRefs(
                    claim_set_artifact_id=extracted.claim_set_artifact_id,
                    normalized_claim_set_artifact_id=normalized.claim_set_artifact_id,
                    claim_ids=sorted(set(normalized.claim_ids)),
                    evidence_refs=sorted(set(evidence_refs)),
                )
            )

            normalized_claim_set_artifact_ids.append(normalized.claim_set_artifact_id)
            claim_ids_set.update(normalized.claim_ids)

            payload = load_json_artifact(cas, normalized.claim_set_artifact_id)
            rows = payload.get("claims")
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    claim_id = row.get("claim_id")
                    artifact_id = row.get("claim_artifact_id")
                    if not isinstance(claim_id, str) or not isinstance(artifact_id, str):
                        continue
                    current = claim_artifact_by_id.get(claim_id)
                    if current is None or artifact_id < current:
                        claim_artifact_by_id[claim_id] = artifact_id

            if remaining_claim_budget is not None:
                remaining_claim_budget -= len(normalized.claim_ids)
    except ClaimPipelineError as exc:
        raise ScholarClaimsError(f"claims stage failed: {exc}") from exc

    all_claim_ids = sorted(claim_ids_set)
    claims_by_id = {
        claim_id: load_claim(cas, claim_artifact_by_id[claim_id])
        for claim_id in sorted(claim_artifact_by_id)
    }

    try:
        resolve_result = resolve_conflicts(
            cas=cas,
            fact_log_root=fact_log_root,
            db=db,
            claim_ids=all_claim_ids,
            claim_set_artifact_ids=sorted(set(normalized_claim_set_artifact_ids)),
            policy_id=scholar_policy.conflict.policy_id,
            options=scholar_policy.claims.resolve_options,
            segment_name=f"scholar_reconcile_{run_token}",
        )
    except ClaimPipelineError as exc:
        raise ScholarReconcileError(f"reconcile stage failed: {exc}") from exc

    reconcile_refs = ReconcileRefs(
        conflict_set_ids=resolve_result.conflict_set_ids,
        conflict_set_artifact_ids=resolve_result.conflict_set_artifact_ids,
        winner_by_conflict_set=resolve_result.winner_by_conflict_set,
        conflict_resolution_artifact_ids=resolve_result.conflict_resolution_artifact_ids,
        trust_assessment_ids=resolve_result.trust_assessment_ids,
        trust_assessment_artifact_ids_by_id=resolve_result.trust_assessment_artifact_ids_by_id,
        quality_report_ids=[resolve_result.quality_report_id]
        if resolve_result.quality_report_id
        else [],
        quality_report_artifact_ids=[resolve_result.quality_report_artifact_id]
        if resolve_result.quality_report_artifact_id
        else [],
    )

    doc_tier_by_version, tiers_histogram = _doc_tiers_from_reconcile(
        cas=cas,
        trust_artifact_by_id=reconcile_refs.trust_assessment_artifact_ids_by_id,
    )
    min_tier_rank = _TRUST_RANK[thresholds.min_doc_trust_tier]

    selected_docs = [
        doc
        for doc in docs_refs
        if (
            doc_tier_by_version.get(doc.doc_version_id) is None
            or _TRUST_RANK[doc_tier_by_version[doc.doc_version_id]] >= min_tier_rank
        )
    ]
    selected_doc_ids = sorted({doc.doc_version_id for doc in selected_docs})
    selected_doc_id_set = set(selected_doc_ids)

    claim_targets = set(intent.claim_targets or [])
    selected_claim_ids: list[str] = []
    for claim_id in all_claim_ids:
        claim = claims_by_id.get(claim_id)
        if claim_targets and claim is not None and claim.predicate_id not in claim_targets:
            continue
        if claim_targets and claim is None:
            continue

        if claim is not None:
            cited_docs = {
                citation.doc.doc_version_id
                for citation in claim.citations
                if citation.doc.doc_version_id is not None
            }
            if cited_docs and cited_docs.isdisjoint(selected_doc_id_set):
                continue

        selected_claim_ids.append(claim_id)

    policy_ids_used = {
        "extractor_id": sorted(extractor_ids_used)[0] if extractor_ids_used else scholar_policy.claims.extractor_id,
        "extractor_ids": ",".join(sorted(extractor_ids_used)),
        "conflict_policy_id": scholar_policy.conflict.policy_id,
        "trust_algorithm_version": scholar_policy.claims.resolve_options.trust_algorithm_version,
        "resolution_algorithm_version": (
            scholar_policy.claims.resolve_options.resolution_algorithm_version
        ),
    }

    intent_payload = _intent_payload(
        intent=intent,
        sources=sources,
        budgets=budgets,
        thresholds=thresholds,
    )
    intent_core = _intent_core_for_bundle_id(
        intent=intent,
        sources=sources,
        budgets=budgets,
        thresholds=thresholds,
    )

    bundle_id = compute_bundle_id(
        intent_core=intent_core,
        doc_version_ids=selected_doc_ids,
        claim_ids=selected_claim_ids,
        policy_ids_used=policy_ids_used,
    )

    predicate_counts = Counter(
        claims_by_id[claim_id].predicate_id
        for claim_id in selected_claim_ids
        if claim_id in claims_by_id
    )
    top_predicates = [
        {"predicate_id": predicate_id, "count": count}
        for predicate_id, count in sorted(
            predicate_counts.items(), key=lambda item: (-item[1], item[0])
        )[:10]
    ]

    quality_issues: list[str] = []
    for artifact_id in reconcile_refs.quality_report_artifact_ids:
        payload = load_json_artifact(cas, artifact_id)
        issues = payload.get("issues")
        if isinstance(issues, list):
            for issue in issues:
                if isinstance(issue, dict) and isinstance(issue.get("code"), str):
                    quality_issues.append(issue["code"])
    quality_issues = sorted(set(quality_issues))

    selected_doc_meta_ids = sorted({doc.doc_meta_artifact_id for doc in selected_docs})
    selected_doc_source_ids = sorted({doc.doc_source_id for doc in selected_docs})

    summary = {
        "docs_count": len(selected_doc_ids),
        "claims_count": len(selected_claim_ids),
        "conflict_sets_count": len(reconcile_refs.conflict_set_ids),
        "trust_assessments_count": len(reconcile_refs.trust_assessment_ids),
        "quality_reports_count": len(reconcile_refs.quality_report_ids),
        "claim_targets_applied": bool(claim_targets),
    }

    bundle_payload = build_knowledge_bundle_payload(
        bundle_id=bundle_id,
        intent_payload=intent_payload,
        doc_meta_artifact_ids=selected_doc_meta_ids,
        doc_version_ids=selected_doc_ids,
        doc_source_ids=selected_doc_source_ids,
        claim_ids=selected_claim_ids,
        claim_set_artifact_ids=sorted(set(normalized_claim_set_artifact_ids)),
        conflict_set_ids=reconcile_refs.conflict_set_ids,
        conflict_set_artifact_ids=reconcile_refs.conflict_set_artifact_ids,
        conflict_resolution_artifact_ids=reconcile_refs.conflict_resolution_artifact_ids,
        trust_assessment_ids=reconcile_refs.trust_assessment_ids,
        trust_assessment_artifact_ids_by_id=(
            reconcile_refs.trust_assessment_artifact_ids_by_id
        ),
        quality_report_ids=reconcile_refs.quality_report_ids,
        quality_report_artifact_ids=reconcile_refs.quality_report_artifact_ids,
        policy_ids_used=policy_ids_used,
        created_by={
            "component": "polisyos.scholar",
            "version": "1.0",
            "pipeline": "discover-acquire-docs-claims-reconcile-bundle",
        },
        summary=summary,
    )

    report_payload = EnrichmentReportV1(
        bundle_artifact_id="",
        bundle_id=bundle_id,
        docs={
            "count": len(selected_doc_ids),
            "doc_version_ids": selected_doc_ids,
            "bytes_total": bytes_total,
            "skipped": docs_skipped,
        },
        claims={
            "count_total": len(selected_claim_ids),
            "by_predicate_topN": top_predicates,
            "filtered": len(all_claim_ids) - len(selected_claim_ids),
        },
        conflicts={
            "sets_seen": len(reconcile_refs.conflict_set_ids),
            "sets_resolved": len(reconcile_refs.winner_by_conflict_set),
            "ties": 0,
            "insufficient_evidence": 0,
        },
        trust={
            "assessments_total": len(reconcile_refs.trust_assessment_ids),
            "tiers_histogram": tiers_histogram,
        },
        quality={
            "issues_top": quality_issues,
            "quality_report_ids": reconcile_refs.quality_report_ids,
        },
        artifacts={
            "doc_meta_artifact_ids": selected_doc_meta_ids,
            "claim_set_artifact_ids": sorted(set(normalized_claim_set_artifact_ids)),
            "conflict_resolution_artifact_ids": reconcile_refs.conflict_resolution_artifact_ids,
            "trust_assessment_artifact_ids": sorted(
                reconcile_refs.trust_assessment_artifact_ids_by_id.values()
            ),
            "quality_report_artifact_ids": reconcile_refs.quality_report_artifact_ids,
        },
        notes=acquire_notes,
    )

    input_artifact_ids = [
        *selected_doc_meta_ids,
        *sorted(set(normalized_claim_set_artifact_ids)),
        *reconcile_refs.conflict_set_artifact_ids,
        *reconcile_refs.conflict_resolution_artifact_ids,
        *sorted(reconcile_refs.trust_assessment_artifact_ids_by_id.values()),
        *reconcile_refs.quality_report_artifact_ids,
    ]

    try:
        knowledge_bundle_ref, report, report_ref = persist_bundle_and_event(
            cas=cas,
            fact_log_root=fact_log_root,
            bundle_payload=bundle_payload,
            report_payload=report_payload,
            doc_version_ids=selected_doc_ids,
            claim_ids=selected_claim_ids,
            conflict_set_ids=reconcile_refs.conflict_set_ids,
            input_artifact_ids=input_artifact_ids,
            segment_name=f"scholar_bundle_build_{run_token}",
            persist_report=scholar_policy.persist_report,
        )
    except Exception as exc:
        raise ScholarBundleError(f"bundle stage failed: {exc}") from exc

    return EnrichResultV1(
        knowledge_bundle_ref=knowledge_bundle_ref,
        bundle_id=bundle_id,
        report=report,
        report_ref=report_ref,
    )


__all__ = ["enrich_topic"]
