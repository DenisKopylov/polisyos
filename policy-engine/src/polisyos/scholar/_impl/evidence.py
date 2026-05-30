"""Scholar academic and grey-literature evidence contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from typing import Any

from polisyos.scholar_requirement import (
    ScholarSupportRequirementSpec,
    normalize_scholar_support_requirement_specs,
    requirement_specs_by_claim,
)

SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION = "policyos.scholar.academic_evidence.v1"
SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY = "scholar_evidence_ref"
SCHOLAR_ACADEMIC_EVIDENCE_FILENAME = "scholar_academic_evidence.json"

_RUNTIME_PROVENANCE_KINDS = frozenset(
    {
        "runtime_emitted",
        "runtime_blocker",
        "scholar_runtime",
    }
)
_STALE_STATUSES = frozenset({"expired", "fail", "failed", "stale"})
_DEFAULT_MAX_SOURCE_AGE_DAYS = 1095
_PARTICIPATION_LIKE_CLAIM_USES = frozenset(
    {
        "affected_person_preference",
        "affected-person-preference",
        "dissent",
        "existence",
        "legitimacy",
        "participation_legitimacy",
        "participation-legitimacy",
        "preference",
        "prevalence",
        "qualitative",
        "role-feasibility",
        "role_feasibility",
    }
)
_HIGH_AUTHORITY_PARTICIPATION_USES = frozenset(
    {
        "affected_person_preference",
        "affected-person-preference",
        "legitimacy",
        "participation_legitimacy",
        "participation-legitimacy",
        "preference",
        "prevalence",
    }
)


def build_scholar_academic_evidence_report(
    *,
    scholar_evidence_ref: str,
    research_intent: Mapping[str, Any],
    query_graph: Mapping[str, Any],
    provider_traces: Sequence[Mapping[str, Any]],
    source_scoring: Sequence[Mapping[str, Any]],
    snippets: Sequence[Mapping[str, Any]],
    citations: Sequence[Mapping[str, Any]],
    freshness: Mapping[str, Any],
    corpus_lineage: Mapping[str, Any],
    selected_sources: Sequence[Mapping[str, Any]],
    rejected_sources: Sequence[Mapping[str, Any]],
    support_links: Sequence[Mapping[str, Any]],
    conflict_links: Sequence[Mapping[str, Any]] | None = None,
    duplicate_markers: Sequence[Mapping[str, Any]] | None = None,
    polarity_markers: Sequence[Mapping[str, Any]] | None = None,
    dependence_records: Sequence[Mapping[str, Any]] | None = None,
    participation_downgrade_records: Sequence[Mapping[str, Any]] | None = None,
    literature_deficit_blockers: Sequence[Mapping[str, Any]] | None = None,
    source_family_independence_tags: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    support_requirement_specs: Sequence[Mapping[str, Any] | ScholarSupportRequirementSpec]
    | None = None,
    cas_ref: str | None = None,
    runtime_event_ref: str | None = None,
    producer_component: str = "polisyos.scholar.academic_evidence",
) -> dict[str, Any]:
    """Build and normalize Scholar's Phase 12.3 evidence record."""

    payload = {
        "schema_version": SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION,
        SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY: scholar_evidence_ref,
        "cas_ref": cas_ref or scholar_evidence_ref,
        "runtime_event_ref": runtime_event_ref,
        "capability_reality_status": "implemented",
        "runtime_authority_envelope": _authority_envelope(),
        "provenance_kind": "runtime_emitted",
        "producer_component": producer_component,
        "research_intent": dict(research_intent),
        "query_graph": dict(query_graph),
        "provider_traces": [dict(row) for row in provider_traces],
        "source_scoring": [dict(row) for row in source_scoring],
        "snippets": [dict(row) for row in snippets],
        "citations": [dict(row) for row in citations],
        "freshness": dict(freshness),
        "corpus_lineage": dict(corpus_lineage),
        "selected_sources": [dict(row) for row in selected_sources],
        "rejected_sources": [dict(row) for row in rejected_sources],
        "support_links": [dict(row) for row in support_links],
        "conflict_links": [dict(row) for row in conflict_links or ()],
        "duplicate_markers": [dict(row) for row in duplicate_markers or ()],
        "polarity_markers": [dict(row) for row in polarity_markers or ()],
        "dependence_records": [dict(row) for row in dependence_records or ()],
        "participation_downgrade_records": [
            dict(row) for row in participation_downgrade_records or ()
        ],
        "literature_deficit_blockers": [
            dict(row) for row in literature_deficit_blockers or ()
        ],
        "support_requirement_specs": [
            spec.model_dump(mode="json")
            if isinstance(spec, ScholarSupportRequirementSpec)
            else dict(spec)
            for spec in support_requirement_specs or ()
        ],
        "source_family_independence_tags": _normalize_independence_tags(
            source_family_independence_tags
        ),
    }
    return normalize_scholar_academic_evidence_report(payload)


def build_scholar_academic_evidence_report_from_web_bundle(
    *,
    scholar_evidence_ref: str,
    bundle: object,
    corpus_snapshot_ref: str,
    lineage_ref: str,
    cas_ref: str | None = None,
    runtime_event_ref: str | None = None,
    max_source_age_days: int = _DEFAULT_MAX_SOURCE_AGE_DAYS,
    as_of: date | datetime | str | None = None,
    requirement_specs: Sequence[Mapping[str, Any] | ScholarSupportRequirementSpec] | None = None,
) -> dict[str, Any]:
    """Build W3.D Scholar academic evidence from a search evidence bundle.

    Args:
        scholar_evidence_ref: Runtime CAS-like ref for the Scholar report.
        bundle: `WebEvidenceBundle` or compatible mapping emitted by Scholar search.
        corpus_snapshot_ref: Runtime ref for the search corpus snapshot.
        lineage_ref: Runtime lineage ref for the search run.
        cas_ref: Optional CAS ref for the normalized Scholar report.
        runtime_event_ref: Optional runtime event ref for the adapter emission.
        max_source_age_days: Freshness ceiling used for derived freshness rows.
        as_of: Date used to compute freshness when source age is not already present.

    Returns:
        Normalized Scholar academic evidence report with W3.D markers.
    """

    payload = _bundle_payload(bundle)
    scholar_requirements = normalize_scholar_support_requirement_specs(requirement_specs)
    requirements_by_claim = requirement_specs_by_claim(scholar_requirements)
    brief = _mapping(payload.get("brief"))
    query_graph = _mapping(payload.get("query_graph"))
    sources = _mapping_list(payload.get("sources"))
    snippets = _mapping_list(payload.get("snippets"))
    claim_supports = _mapping_list(payload.get("claim_supports"))
    query_traces = _mapping_list(payload.get("query_traces"))
    bundle_id = _text(payload.get("bundle_id")) or "scholar-web-evidence-bundle"
    as_of_date = _date_from(as_of) or datetime.now(UTC).date()
    relevance_by_source = _max_relevance_by_source(snippets)
    independence_tags = _source_family_tags_from_sources(sources)
    selected_sources = [
        {
            "source_id": source_id,
            "source_family": _text(source.get("source_type")) or "web",
            "source_family_independence_tag": independence_tags[source_id],
            "underlying_study_id": independence_tags[source_id],
            "publication_tier": _publication_tier_from_source(source),
            "dataset_ids": _text_list(source.get("dataset_ids")),
            "author_names": _text_list(source.get("author_names")),
            "institution_names": _text_list(source.get("institution_names")),
            "citation_network_refs": _text_list(source.get("citation_network_refs")),
            "replication_of_source_id": _text(source.get("replication_of_source_id")),
            "review_status": _text(source.get("review_status")),
            "published_at": _text(source.get("published_at")),
            "page_age_days": _int(source.get("page_age_days")),
            "rights": "open_metadata",
            "duplicate_of_source_id": _text(source.get("duplicate_of_source_id")),
            "url": _text(source.get("url")),
            "title": _text(source.get("title")),
        }
        for source in sources
        if (source_id := _source_id(source))
        and (_text(source.get("fetch_status")) or "ok") not in {"blocked", "error"}
    ]
    family_counts = _source_family_counts(
        selected_sources,
        independence_tags=independence_tags,
    )
    rejected_sources = [
        {
            "source_id": source_id,
            "source_family": _text(source.get("source_type")) or "web",
            "reason_code": (
                _text(source.get("fetch_status"))
                or _text(source.get("error"))
                or "rejected"
            ),
        }
        for source in sources
        if (source_id := _source_id(source))
        and (_text(source.get("fetch_status")) or "ok") in {"blocked", "error"}
    ]
    source_scoring = [
        {
            "source_id": source_id,
            "quality_score": _float(source.get("quality_score")) or 0.0,
            "freshness_score": _freshness_score(
                _int(source.get("page_age_days")),
                max_source_age_days=max_source_age_days,
            ),
            "relevance_score": relevance_by_source.get(source_id, 0.0),
            "independence_score": _source_independence_score(
                source,
                independence_tags=independence_tags,
                family_counts=family_counts,
            ),
        }
        for source in sources
        if (source_id := _source_id(source))
    ]
    citation_rows = [
        {
            "citation_id": f"citation:{snippet_id}",
            "source_id": source_id,
            "snippet_ids": [snippet_id],
            "evidence_ref": scholar_evidence_ref,
            "provenance_kind": "runtime_emitted",
            "source_surface": "scholar_retrieval",
        }
        for snippet in snippets
        if (snippet_id := _text(snippet.get("snippet_id")))
        and (source_id := _source_id(snippet))
    ]
    support_links = [
        _support_link_from_bundle(row, requirements_by_claim=requirements_by_claim)
        for row in claim_supports
    ]
    effective_support_by_claim = _effective_support_by_claim(
        support_links=support_links,
        selected_sources=selected_sources,
        independence_tags=independence_tags,
    )
    support_links = [
        _support_link_with_requirement_counts(
            link,
            requirements_by_claim=requirements_by_claim,
            effective_support_by_claim=effective_support_by_claim,
        )
        for link in support_links
    ]
    conflict_links = _conflict_links_from_supports(support_links)
    dependence_records = _dependence_records_from_sources(
        selected_sources,
        independence_tags=independence_tags,
        include_collapse_reasons=bool(scholar_requirements),
    )
    literature_deficit_blockers = _requirement_deficit_blockers(
        requirements=scholar_requirements,
        support_links=support_links,
        selected_sources=selected_sources,
    )
    return build_scholar_academic_evidence_report(
        scholar_evidence_ref=scholar_evidence_ref,
        cas_ref=cas_ref,
        runtime_event_ref=runtime_event_ref,
        research_intent={
            "intent_id": f"research-intent:{bundle_id}",
            "question": _text(brief.get("question")) or "",
            "policy_domain": _text(brief.get("domain")) or "",
            "jurisdictions": _text_list(brief.get("jurisdictions")),
            "required_source_types": _text_list(brief.get("required_source_types")),
        },
        query_graph={
            "graph_id": f"query-graph:{bundle_id}",
            "root_query": _text(brief.get("question")) or "",
            "nodes": _mapping_list(query_graph.get("nodes")),
            "root_node_ids": _text_list(query_graph.get("root_node_ids")),
        },
        provider_traces=[
            {
                "trace_id": _text(trace.get("trace_id"))
                or f"trace:{_text(trace.get('query_node_id')) or index + 1}",
                **dict(trace),
            }
            for index, trace in enumerate(query_traces)
        ],
        source_scoring=source_scoring,
        snippets=snippets,
        citations=citation_rows,
        freshness={
            "status": "pass",
            "as_of": as_of_date.isoformat(),
            "max_source_age_days": max_source_age_days,
            "sources": [
                {
                    "source_id": source_id,
                    "published_at": _text(source.get("published_at")),
                    "age_days": _int(source.get("page_age_days")),
                    "status": "pass",
                }
                for source in sources
                if (source_id := _source_id(source))
            ],
        },
        corpus_lineage={
            "knowledge_bundle_ref": bundle_id,
            "corpus_snapshot_ref": corpus_snapshot_ref,
            "lineage_ref": lineage_ref,
        },
        selected_sources=selected_sources,
        rejected_sources=rejected_sources,
        support_links=support_links,
        conflict_links=conflict_links,
        duplicate_markers=_duplicate_markers_from_sources(sources),
        polarity_markers=_polarity_markers_from_supports(support_links),
        dependence_records=dependence_records,
        participation_downgrade_records=_participation_downgrades_from_supports(
            support_links
        ),
        literature_deficit_blockers=literature_deficit_blockers,
        support_requirement_specs=scholar_requirements,
        source_family_independence_tags=independence_tags,
    )


def normalize_scholar_academic_evidence_report(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize Scholar academic/grey-literature evidence."""

    normalized = dict(report)
    issues: list[dict[str, Any]] = []
    normalized["capability_reality_status"] = "implemented"
    normalized["runtime_authority_envelope"] = _authority_envelope()

    schema_version = _text(report.get("schema_version"))
    if schema_version != SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION:
        issues.append(
            _issue(
                "policy_design_scholar_schema_version_invalid",
                "Scholar academic evidence must use the Phase 12.3 schema version.",
                next_action=(
                    "Regenerate Scholar evidence with the current academic evidence schema."
                ),
            )
        )
    normalized["schema_version"] = SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION

    ref = _text(
        report.get(SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY)
        or report.get("evidence_ref")
        or report.get("cas_ref")
    )
    if ref is None or not _runtime_refish(ref):
        issues.append(
            _issue(
                "policy_design_scholar_evidence_ref_missing",
                "Scholar evidence must carry a CAS-like runtime evidence ref.",
                next_action="Persist Scholar academic evidence through runtime CAS.",
            )
        )
    else:
        normalized[SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY] = ref

    provenance = _text(report.get("provenance_kind"))
    if provenance not in _RUNTIME_PROVENANCE_KINDS:
        issues.append(
            _issue(
                "policy_design_scholar_runtime_provenance_missing",
                "Scholar evidence must be runtime-emitted or an explicit runtime blocker.",
                next_action="Emit Scholar evidence from the Scholar runtime producer.",
            )
        )

    blockers = _mapping_list(
        report.get("literature_deficit_blockers")
        or report.get("retrieval_blocker_refs")
        or report.get("blockers")
    )
    selected_sources = _mapping_list(report.get("selected_sources"))
    rejected_sources = _mapping_list(report.get("rejected_sources"))
    source_scoring = _mapping_list(report.get("source_scoring"))
    snippets = _mapping_list(report.get("snippets"))
    citations = _mapping_list(report.get("citations"))
    support_links = _mapping_list(report.get("support_links"))
    conflict_links = _mapping_list(report.get("conflict_links"))
    duplicate_markers = _mapping_list(report.get("duplicate_markers"))
    polarity_markers = _mapping_list(report.get("polarity_markers"))
    dependence_records = _mapping_list(report.get("dependence_records"))
    participation_downgrade_records = _mapping_list(
        report.get("participation_downgrade_records")
        or report.get("participation_downgrades")
        or report.get("claim_use_downgrades")
    )
    support_requirement_specs = normalize_scholar_support_requirement_specs(
        report.get("support_requirement_specs")
        or report.get("scholar_support_requirement_specs")
        or report.get("requirement_specs")
    )
    requirements_by_claim = requirement_specs_by_claim(support_requirement_specs)
    generated_participation_downgrades = False
    if not participation_downgrade_records and requirements_by_claim:
        participation_downgrade_records = _participation_downgrades_from_requirements(
            support_links=support_links,
            requirements_by_claim=requirements_by_claim,
        )
        generated_participation_downgrades = bool(participation_downgrade_records)

    for field_name, value, code, message in (
        (
            "research_intent",
            report.get("research_intent"),
            "policy_design_scholar_research_intent_missing",
            "Scholar evidence must record the research intent.",
        ),
        (
            "query_graph",
            report.get("query_graph"),
            "policy_design_scholar_query_graph_missing",
            "Scholar evidence must record the query graph.",
        ),
        (
            "freshness",
            report.get("freshness"),
            "policy_design_scholar_freshness_missing",
            "Scholar evidence must record literature freshness.",
        ),
        (
            "corpus_lineage",
            report.get("corpus_lineage"),
            "policy_design_scholar_corpus_lineage_missing",
            "Scholar evidence must record corpus lineage.",
        ),
    ):
        if not isinstance(value, Mapping) or not value:
            issues.append(_issue(code, message, next_action=f"Emit {field_name}."))

    for field_name, rows, code, message in (
        (
            "provider_traces",
            _mapping_list(report.get("provider_traces")),
            "policy_design_scholar_provider_traces_missing",
            "Scholar evidence must record provider traces.",
        ),
        (
            "source_scoring",
            source_scoring,
            "policy_design_scholar_source_scoring_missing",
            "Scholar evidence must record source scoring.",
        ),
        (
            "snippets",
            snippets,
            "policy_design_scholar_snippets_missing",
            "Scholar evidence must record citation snippets.",
        ),
        (
            "citations",
            citations,
            "policy_design_scholar_citations_missing",
            "Scholar evidence must record citation records.",
        ),
        (
            "selected_sources",
            selected_sources,
            "policy_design_scholar_selected_sources_missing",
            "Scholar evidence must record selected literature sources.",
        ),
        (
            "support_links",
            support_links,
            "policy_design_scholar_support_links_missing",
            "Scholar evidence must link sources to supported claims.",
        ),
    ):
        if not rows and not blockers:
            issues.append(_issue(code, message, next_action=f"Emit {field_name}."))

    query_graph = report.get("query_graph")
    if isinstance(query_graph, Mapping) and not _mapping_list(query_graph.get("nodes")):
        issues.append(
            _issue(
                "policy_design_scholar_query_graph_missing",
                "Scholar query graph must contain query nodes.",
                next_action="Persist Scholar query graph nodes.",
            )
        )
    corpus_lineage = report.get("corpus_lineage")
    if isinstance(corpus_lineage, Mapping) and not any(
        _text(corpus_lineage.get(key))
        for key in ("corpus_snapshot_ref", "knowledge_bundle_ref", "lineage_ref")
    ):
        issues.append(
            _issue(
                "policy_design_scholar_corpus_lineage_missing",
                "Scholar corpus lineage must include a snapshot, bundle, or lineage ref.",
                next_action="Persist Scholar corpus lineage refs.",
            )
        )

    selected_ids = {_source_id(row) for row in selected_sources if _source_id(row)}
    scoring_ids = {_source_id(row) for row in source_scoring if _source_id(row)}
    missing_scoring = sorted(selected_ids - scoring_ids)
    if missing_scoring:
        issues.append(
            _issue(
                "policy_design_scholar_source_scoring_missing",
                "Every selected Scholar source must have a scoring row.",
                next_action="Attach source scoring to every selected literature source.",
                refs=missing_scoring,
            )
        )

    independence_tags = _normalize_independence_tags(
        report.get("source_family_independence_tags")
    )
    normalized["source_family_independence_tags"] = independence_tags
    missing_independence = []
    for row in selected_sources:
        source_id = _source_id(row)
        tag = (
            _text(row.get("source_family_independence_tag"))
            or _text(row.get("independence_tag"))
            or independence_tags.get(source_id or "")
        )
        if source_id and tag is None:
            missing_independence.append(source_id)
    if not independence_tags and selected_sources:
        missing_independence.extend(
            _source_id(row) or "unknown" for row in selected_sources
        )
    if missing_independence:
        issues.append(
            _issue(
                "policy_design_scholar_source_family_independence_missing",
                "Every selected academic or grey-literature source must carry an independence tag.",
                next_action="Mark selected Scholar sources with source-family independence tags.",
                refs=sorted(dict.fromkeys(missing_independence)),
            )
        )

    if not rejected_sources and "rejected_sources" not in report and not blockers:
        issues.append(
            _issue(
                "policy_design_scholar_rejected_sources_missing",
                (
                    "Scholar evidence must record rejected literature sources or "
                    "an explicit empty audit."
                ),
                next_action="Emit rejected_sources, even when no literature was rejected.",
            )
        )

    issues.extend(
        _duplicate_marker_issues(
            selected_sources=selected_sources,
            duplicate_markers=duplicate_markers,
            field_present="duplicate_markers" in report,
            blockers=blockers,
        )
    )
    issues.extend(
        _polarity_marker_issues(
            support_links=support_links,
            polarity_markers=polarity_markers,
            field_present="polarity_markers" in report,
            blockers=blockers,
        )
    )
    issues.extend(
        _dependence_record_issues(
            selected_sources=selected_sources,
            source_scoring=source_scoring,
            independence_tags=independence_tags,
            dependence_records=dependence_records,
            field_present="dependence_records" in report,
            blockers=blockers,
        )
    )
    issues.extend(
        _participation_downgrade_issues(
            support_links=support_links,
            participation_downgrade_records=participation_downgrade_records,
            field_present=(
                "participation_downgrade_records" in report
                or "participation_downgrades" in report
                or "claim_use_downgrades" in report
                or generated_participation_downgrades
            ),
            blockers=blockers,
        )
    )

    snippet_ids = {
        _text(row.get("snippet_id")) for row in snippets if _text(row.get("snippet_id"))
    }
    for citation in citations:
        citation_issues = _citation_provenance_issues(citation, snippet_ids)
        issues.extend(citation_issues)

    for issue in _freshness_issues(report.get("freshness"), selected_ids):
        issues.append(issue)

    if not conflict_links and "conflict_links" not in report:
        issues.append(
            _issue(
                "policy_design_scholar_conflict_links_missing",
                (
                    "Scholar evidence must emit conflict links or an explicit empty "
                    "conflict assessment."
                ),
                next_action="Emit conflict_links for Scholar support/conflict assessment.",
            )
        )

    normalized["provider_traces"] = _mapping_list(report.get("provider_traces"))
    normalized["source_scoring"] = source_scoring
    normalized["snippets"] = snippets
    normalized["citations"] = citations
    normalized["selected_sources"] = selected_sources
    normalized["rejected_sources"] = rejected_sources
    normalized["support_links"] = support_links
    normalized["conflict_links"] = conflict_links
    normalized["duplicate_markers"] = duplicate_markers
    normalized["polarity_markers"] = polarity_markers
    normalized["dependence_records"] = dependence_records
    normalized["participation_downgrade_records"] = participation_downgrade_records
    normalized["literature_deficit_blockers"] = blockers
    normalized["support_requirement_specs"] = [
        spec.model_dump(mode="json") for spec in support_requirement_specs
    ]
    normalized["issues"] = _dedupe_issues(issues)
    if normalized["issues"]:
        normalized["status"] = "fail"
    elif blockers:
        normalized["status"] = "blocked"
    else:
        normalized["status"] = "pass"
    return normalized


def scholar_academic_evidence_required(quality_evidence: Mapping[str, Any]) -> bool:
    """Return whether the current Policy Design Case requires Scholar evidence."""

    case = quality_evidence.get("policy_design_case")
    if isinstance(case, Mapping):
        ledger = case.get("capability_ledger")
        if isinstance(ledger, Mapping):
            explicit = ledger.get("literature_evidence_required")
            if isinstance(explicit, bool):
                return explicit
            if isinstance(explicit, str) and explicit.strip().casefold() in {
                "1",
                "required",
                "true",
                "yes",
            }:
                return True
        for claim in _mapping_list(case.get("final_major_claims") or case.get("major_claims")):
            if _truthy_refs(claim.get("literature_refs")) or _truthy_refs(
                claim.get("scholar_refs")
            ):
                return True

    semantic = quality_evidence.get("semantic_binding_ledger")
    if isinstance(semantic, Mapping):
        for section in ("scientist", "final_compiler"):
            for binding in _mapping_list(semantic.get(section)):
                if _truthy_refs(binding.get("required_literature_refs")):
                    return True
        if _mapping_list(semantic.get("scholar")):
            return True

    grounding = quality_evidence.get("policy_grounding_matrix")
    if isinstance(grounding, Mapping):
        for claim in _mapping_list(grounding.get("claims")):
            if _truthy_refs(claim.get("literature_refs")) or _truthy_refs(
                claim.get("scholar_refs")
            ):
                return True
    return False


def _citation_provenance_issues(
    citation: Mapping[str, Any],
    known_snippet_ids: set[str | None],
) -> list[dict[str, Any]]:
    source_surface = (_text(citation.get("source_surface")) or "").casefold()
    provenance = (_text(citation.get("provenance_kind")) or "").casefold()
    evidence_ref = _text(citation.get("evidence_ref") or citation.get("citation_ref"))
    snippet_ids = _text_list(citation.get("snippet_ids") or citation.get("snippet_id"))
    source_id = _source_id(citation)
    narrative = source_surface == "narrative_citation" or provenance == "narrative_citation"
    missing_runtime_provenance = (
        provenance not in _RUNTIME_PROVENANCE_KINDS
        or source_id is None
        or not snippet_ids
        or evidence_ref is None
        or not _runtime_refish(evidence_ref)
    )
    if narrative or missing_runtime_provenance:
        return [
            _issue(
                "policy_design_scholar_narrative_citation_without_provenance",
                (
                    "Narrative citations cannot satisfy Scholar literature evidence without "
                    "runtime provenance."
                ),
                next_action=(
                    "Replace narrative citation text with Scholar citation records "
                    "that reference source ids, snippets, and runtime evidence refs."
                ),
                refs=[_text(citation.get("citation_id")) or source_id or "unknown_citation"],
            )
        ]
    missing_snippets = sorted(set(snippet_ids) - {item for item in known_snippet_ids if item})
    if missing_snippets:
        return [
            _issue(
                "policy_design_scholar_citation_snippet_missing",
                "Scholar citation references snippets that are absent from the snippet ledger.",
                next_action="Persist every citation snippet in Scholar snippets.",
                refs=missing_snippets,
            )
        ]
    return []


def _freshness_issues(freshness: object, selected_source_ids: set[str]) -> list[dict[str, Any]]:
    if not isinstance(freshness, Mapping):
        return []
    issues: list[dict[str, Any]] = []
    status = (_text(freshness.get("status") or freshness.get("freshness_status")) or "").casefold()
    if status in _STALE_STATUSES:
        issues.append(
            _issue(
                "policy_design_scholar_literature_freshness_stale",
                "Scholar literature freshness status is stale.",
                next_action="Refresh Scholar retrieval or emit a literature-deficit blocker.",
            )
        )
    max_age_days = _int(freshness.get("max_source_age_days") or freshness.get("max_age_days"))
    max_age_days = max_age_days if max_age_days is not None else _DEFAULT_MAX_SOURCE_AGE_DAYS
    as_of = _date_from(freshness.get("as_of") or freshness.get("checked_at"))
    source_rows = _mapping_list(freshness.get("sources") or freshness.get("source_freshness"))
    freshness_source_ids = {_source_id(row) for row in source_rows if _source_id(row)}
    missing_rows = sorted(selected_source_ids - freshness_source_ids)
    if selected_source_ids and missing_rows:
        issues.append(
            _issue(
                "policy_design_scholar_literature_freshness_missing",
                "Every selected Scholar source must have freshness metadata.",
                next_action="Attach freshness metadata to every selected literature source.",
                refs=missing_rows,
            )
        )
    for row in source_rows:
        row_status = (_text(row.get("status") or row.get("freshness_status")) or "").casefold()
        source_id = _source_id(row) or "unknown_source"
        if row_status in _STALE_STATUSES:
            issues.append(
                _issue(
                    "policy_design_scholar_literature_freshness_stale",
                    "Selected Scholar literature source is stale.",
                    next_action="Refresh the stale source or emit a literature-deficit blocker.",
                    refs=[source_id],
                )
            )
            continue
        age_days = _int(row.get("age_days") or row.get("page_age_days"))
        published_at = _date_from(
            row.get("published_at") or row.get("source_freshness_at") or row.get("updated_at")
        )
        if age_days is None and as_of is not None and published_at is not None:
            age_days = max(0, (as_of - published_at).days)
        if age_days is not None and age_days > max_age_days:
            issues.append(
                _issue(
                    "policy_design_scholar_literature_freshness_stale",
                    "Selected Scholar literature source exceeds the freshness policy.",
                    next_action="Refresh the stale source or emit a literature-deficit blocker.",
                    refs=[source_id],
                )
            )
    return issues


def _duplicate_marker_issues(
    *,
    selected_sources: Sequence[Mapping[str, Any]],
    duplicate_markers: Sequence[Mapping[str, Any]],
    field_present: bool,
    blockers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if blockers:
        return []
    if selected_sources and not field_present:
        return [
            _issue(
                "policy_design_scholar_duplicate_markers_missing",
                "Scholar evidence must explicitly record duplicate markers, even when none exist.",
                next_action=(
                    "Emit duplicate_markers as an explicit empty assessment or with "
                    "duplicate source refs."
                ),
            )
        ]
    duplicate_source_ids = {
        source_id
        for row in selected_sources
        if (source_id := _source_id(row)) and _text(row.get("duplicate_of_source_id"))
    }
    if not duplicate_source_ids:
        return []
    marker_source_ids = {
        source_id
        for marker in duplicate_markers
        if (
            source_id := _text(
                marker.get("duplicate_source_id")
                or marker.get("source_id")
                or marker.get("source_ref")
            )
        )
    }
    missing = sorted(duplicate_source_ids - marker_source_ids)
    if not missing:
        return []
    return [
        _issue(
            "policy_design_scholar_duplicate_markers_missing",
            "Selected duplicate Scholar sources must have explicit duplicate markers.",
            next_action="Attach duplicate markers naming canonical and duplicate source ids.",
            refs=missing,
        )
    ]


def _polarity_marker_issues(
    *,
    support_links: Sequence[Mapping[str, Any]],
    polarity_markers: Sequence[Mapping[str, Any]],
    field_present: bool,
    blockers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if blockers:
        return []
    if support_links and not field_present:
        return [
            _issue(
                "policy_design_scholar_polarity_markers_missing",
                "Scholar support/conflict links must preserve polarity markers.",
                next_action="Emit polarity_markers for claim/source/snippet support and conflict.",
            )
        ]
    if not support_links:
        return []
    marker_claim_ids = {
        claim_id for marker in polarity_markers if (claim_id := _claim_id(marker))
    }
    missing_claim_ids = sorted(
        {
            claim_id
            for link in support_links
            if (claim_id := _claim_id(link)) and claim_id not in marker_claim_ids
        }
    )
    if not missing_claim_ids:
        return []
    return [
        _issue(
            "policy_design_scholar_polarity_markers_missing",
            "Every Scholar support link must have a polarity marker for its claim.",
            next_action="Attach polarity markers to every Scholar claim-support link.",
            refs=missing_claim_ids,
        )
    ]


def _dependence_record_issues(
    *,
    selected_sources: Sequence[Mapping[str, Any]],
    source_scoring: Sequence[Mapping[str, Any]],
    independence_tags: Mapping[str, str],
    dependence_records: Sequence[Mapping[str, Any]],
    field_present: bool,
    blockers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if blockers:
        return []
    issues: list[dict[str, Any]] = []
    if selected_sources and not field_present:
        issues.append(
            _issue(
                "policy_design_scholar_dependence_records_missing",
                "Scholar evidence must include source-family dependence records.",
                next_action=(
                    "Emit dependence_records with raw and effective source counts for "
                    "literature source families."
                ),
            )
        )
        return issues
    if selected_sources and not dependence_records:
        issues.append(
            _issue(
                "policy_design_scholar_dependence_records_missing",
                "Scholar evidence must include at least one source-family dependence record.",
                next_action=(
                    "Emit dependence_records with raw and effective source counts for "
                    "selected literature."
                ),
            )
        )

    source_ids_by_key: dict[str, list[str]] = {}
    for row in selected_sources:
        source_id = _source_id(row)
        if not source_id:
            continue
        key = _source_dependence_key(row, independence_tags)
        source_ids_by_key.setdefault(key, []).append(source_id)

    records_by_key: dict[str, list[Mapping[str, Any]]] = {}
    for record in dependence_records:
        key = _dependence_record_key(record)
        if key:
            records_by_key.setdefault(key, []).append(record)
        raw_count = _int(
            record.get("raw_source_count")
            or record.get("raw_publication_count")
            or record.get("raw_line_count")
        )
        effective_count = _int(
            record.get("effective_source_count")
            or record.get("effective_publication_count")
            or record.get("effective_support_count")
        )
        if raw_count is not None and effective_count is not None and effective_count > raw_count:
            issues.append(
                _issue(
                    "policy_design_scholar_source_family_dependence_unaccounted",
                    "Scholar dependence records cannot report effective support above raw support.",
                    next_action="Regenerate dependence records with effective count <= raw count.",
                    refs=[_text(record.get("record_id")) or "unknown_dependence_record"],
                )
            )

    scoring_by_source = {
        source_id: row for row in source_scoring if (source_id := _source_id(row))
    }
    for key, source_ids in sorted(source_ids_by_key.items()):
        if len(source_ids) <= 1:
            continue
        records = records_by_key.get(key, [])
        if not records:
            issues.append(
                _issue(
                    "policy_design_scholar_source_family_dependence_unaccounted",
                    (
                        "Multiple Scholar publications share an underlying study or "
                        "source-family tag without a collapse record."
                    ),
                    next_action=(
                        "Collapse publications from the same study/source family into "
                        "one effective support unit before reporting evidence strength."
                    ),
                    refs=source_ids,
                )
            )
            continue
        if not any(_record_collapses_sources(record, source_ids) for record in records):
            issues.append(
                _issue(
                    "policy_design_scholar_source_family_dependence_unaccounted",
                    (
                        "Dependent Scholar publications must report an effective source "
                        "count lower than the raw source count."
                    ),
                    next_action=(
                        "Set effective_source_count below raw_source_count for shared "
                        "underlying studies or mark a justified independent source family."
                    ),
                    refs=source_ids,
                )
            )
        elif all(
            _float(scoring_by_source.get(source_id, {}).get("independence_score")) == 1.0
            for source_id in source_ids
        ):
            issues.append(
                _issue(
                    "policy_design_scholar_source_family_dependence_unaccounted",
                    (
                        "Source scoring cannot mark every dependent publication as fully "
                        "independent."
                    ),
                    next_action=(
                        "Lower per-source independence_score or explain the collapse in "
                        "dependence_records."
                    ),
                    refs=source_ids,
                )
            )
    return issues


def _participation_downgrade_issues(
    *,
    support_links: Sequence[Mapping[str, Any]],
    participation_downgrade_records: Sequence[Mapping[str, Any]],
    field_present: bool,
    blockers: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if blockers:
        return []
    if support_links and not field_present:
        return [
            _issue(
                "policy_design_scholar_participation_downgrade_missing",
                (
                    "Scholar evidence must explicitly preserve participation claim-use "
                    "downgrades or non-participation boundaries."
                ),
                next_action=(
                    "Emit participation_downgrade_records before Scholar support is "
                    "used for affected-person or participation-like claims."
                ),
            )
        ]
    participation_like_links = [link for link in support_links if _participation_like_link(link)]
    if not participation_like_links:
        return []
    issues: list[dict[str, Any]] = []
    records_by_claim: dict[str, list[Mapping[str, Any]]] = {}
    for record in participation_downgrade_records:
        if claim_id := _claim_id(record):
            records_by_claim.setdefault(claim_id, []).append(record)
    for link in participation_like_links:
        claim_id = _claim_id(link) or "unknown_claim"
        requested = _claim_use(link)
        records = records_by_claim.get(claim_id, [])
        if not records:
            issues.append(
                _issue(
                    "policy_design_scholar_participation_downgrade_missing",
                    (
                        "Participation-like Scholar support must carry a claim-use "
                        "downgrade or explicit boundary record."
                    ),
                    next_action=(
                        "Emit the ADR-0167 claim_use_allowed boundary before consuming "
                        "Scholar output for participation-like support."
                    ),
                    refs=[claim_id],
                )
            )
            continue
        for record in records:
            allowed = _claim_use_allowed(record)
            if not allowed:
                issues.append(
                    _issue(
                        "policy_design_scholar_participation_downgrade_missing",
                        "Participation downgrade records must include claim_use_allowed.",
                        next_action=(
                            "Compute claim_use_allowed from ADR-0167 before Scholar "
                            "support consumption."
                        ),
                        refs=[claim_id],
                    )
                )
                continue
            if (
                requested in _HIGH_AUTHORITY_PARTICIPATION_USES
                and allowed in _HIGH_AUTHORITY_PARTICIPATION_USES
                and not _text(record.get("participation_ref"))
                and not _text(record.get("participation_provenance_ref"))
            ):
                issues.append(
                    _issue(
                        "policy_design_scholar_participation_authority_leak",
                        (
                            "Academic Scholar support cannot by itself satisfy "
                            "affected-person prevalence, preference, or legitimacy."
                        ),
                        next_action=(
                            "Downgrade to a supported claim use or attach real "
                            "participation provenance before preserving prevalence or "
                            "legitimacy authority."
                        ),
                        refs=[claim_id],
                    )
                )
    return issues


def _normalize_independence_tags(value: object) -> dict[str, str]:
    if isinstance(value, Mapping):
        return {
            str(key): str(raw).strip()
            for key, raw in value.items()
            if str(key).strip() and str(raw).strip()
        }
    tags: dict[str, str] = {}
    for row in _mapping_list(value):
        source_id = _source_id(row)
        tag = _text(
            row.get("source_family_independence_tag")
            or row.get("independence_tag")
            or row.get("tag")
        )
        if source_id and tag:
            tags[source_id] = tag
    return tags


def _bundle_payload(bundle: object) -> dict[str, Any]:
    model_dump = getattr(bundle, "model_dump", None)
    if callable(model_dump):
        dumped = model_dump(mode="json", exclude_none=True)
        return dict(dumped) if isinstance(dumped, Mapping) else {}
    if isinstance(bundle, Mapping):
        return dict(bundle)
    return {}


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _max_relevance_by_source(snippets: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    relevance: dict[str, float] = {}
    for snippet in snippets:
        source_id = _source_id(snippet)
        if not source_id:
            continue
        score = _float(snippet.get("relevance_score")) or 0.0
        relevance[source_id] = max(relevance.get(source_id, 0.0), score)
    return relevance


def _freshness_score(age_days: int | None, *, max_source_age_days: int) -> float:
    if age_days is None:
        return 0.0
    max_age = max(max_source_age_days, 1)
    return round(max(0.0, 1.0 - min(age_days, max_age) / max_age), 6)


def _source_family_tag(source: Mapping[str, Any]) -> str:
    return (
        _text(source.get("underlying_study_id"))
        or _text(source.get("content_sha256"))
        or ":".join(
            item
            for item in (
                _text(source.get("source_type")) or "web",
                _text(source.get("domain")) or "unknown_domain",
                _source_id(source) or "unknown_source",
            )
            if item
        )
    )


def _source_family_tags_from_sources(sources: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    base_tags: dict[str, str] = {}
    by_source_id: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        source_id = _source_id(source)
        if not source_id:
            continue
        by_source_id[source_id] = source
        base_tags[source_id] = _source_family_tag(source)

    tags: dict[str, str] = {}
    for source_id, source in by_source_id.items():
        canonical_source_id = _text(source.get("duplicate_of_source_id"))
        tags[source_id] = (
            base_tags.get(canonical_source_id or "")
            or canonical_source_id
            or base_tags[source_id]
        )
    return tags


def _source_family_counts(
    selected_sources: Sequence[Mapping[str, Any]],
    *,
    independence_tags: Mapping[str, str],
) -> dict[str, int]:
    counts: dict[str, int] = {}
    for source in selected_sources:
        key = _source_dependence_key(source, independence_tags)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _source_independence_score(
    source: Mapping[str, Any],
    *,
    independence_tags: Mapping[str, str],
    family_counts: Mapping[str, int],
) -> float:
    if _text(source.get("duplicate_of_source_id")):
        return 0.0
    key = _source_dependence_key(source, independence_tags)
    raw_count = family_counts.get(key, 1)
    if raw_count <= 1:
        return 1.0
    return round(1.0 / raw_count, 6)


def _support_link_from_bundle(
    row: Mapping[str, Any],
    *,
    requirements_by_claim: Mapping[str, ScholarSupportRequirementSpec] | None = None,
) -> dict[str, Any]:
    metadata = _mapping(row.get("metadata"))
    claim_id = _claim_id(row) or "claim.unknown"
    requirement = (requirements_by_claim or {}).get(claim_id)
    snippet_ids = _text_list(row.get("snippet_ids"))
    source_ids = _text_list(row.get("source_ids"))
    requested_use = (
        _claim_use(row)
        or _claim_use(metadata)
        or (requirement.participation_claim_use_requested if requirement else "")
        or "academic_support"
    )
    payload = {
        "link_id": _text(row.get("link_id")) or f"support:{claim_id}",
        "claim_id": claim_id,
        "claim_text": _text(row.get("claim_text")) or "",
        "claim_use_requested": requested_use,
        "claim_use_allowed": _claim_use_allowed(row)
        or _claim_use_allowed(metadata)
        or (requirement.participation_claim_use_allowed if requirement else "")
        or "academic_support",
        "authority_level": _text(row.get("authority_level"))
        or _text(metadata.get("authority_level"))
        or (requirement.authority_level if requirement else "")
        or "research",
        "population_scope": _text(row.get("population_scope"))
        or _text(metadata.get("population_scope"))
        or (requirement.population_scope if requirement else "")
        or "general_population",
        "source_ids": source_ids,
        "snippet_ids": snippet_ids,
        "citation_ids": [f"citation:{snippet_id}" for snippet_id in snippet_ids],
        "support_score": _float(row.get("support_score")) or 0.0,
        "conflict_score": _float(row.get("conflict_score")) or 0.0,
        "support_status": _text(row.get("support_status"))
        or _text(metadata.get("support_status"))
        or "unsupported",
        "metadata": metadata,
    }
    if requirement is not None:
        payload.update(
            {
                "support_ref": f"scholar-support-ref:{requirement.requirement_id}",
                "requirement_id": requirement.requirement_id,
                "required_publication_tier": requirement.required_publication_tier,
                "required_recency_days": requirement.recency_days,
                "required_replication_count": requirement.required_replication_count,
                "required_independence_breadth": requirement.required_independence_breadth,
                "required_citation_network_depth": (
                    requirement.required_citation_network_depth
                ),
            }
        )
    return payload


def _conflict_links_from_supports(
    support_links: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    conflict_links: list[dict[str, Any]] = []
    for link in support_links:
        claim_id = _claim_id(link) or "claim.unknown"
        conflict_score = _float(link.get("conflict_score")) or 0.0
        conflict_links.append(
            {
                "link_id": f"conflict:{claim_id}",
                "conflict_ref": f"scholar-conflict-ref:{claim_id}",
                "claim_id": claim_id,
                "requirement_id": _text(link.get("requirement_id")),
                "source_ids": _text_list(link.get("source_ids")),
                "status": "active" if conflict_score > 0.0 else "none_detected",
                "conflict_score": conflict_score,
                "resolution": "No active contradiction after source screening."
                if conflict_score <= 0.0
                else "Directionally conflicting Scholar snippets require review.",
            }
        )
    return conflict_links


def _duplicate_markers_from_sources(sources: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "marker_id": f"duplicate:{source_id}",
            "source_id": source_id,
            "duplicate_source_id": source_id,
            "canonical_source_id": canonical_source_id,
            "duplicate_basis": "content_sha256"
            if _text(source.get("content_sha256"))
            else "source_identity",
        }
        for source in sources
        if (source_id := _source_id(source))
        and (canonical_source_id := _text(source.get("duplicate_of_source_id")))
    ]


def _polarity_markers_from_supports(
    support_links: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    markers: list[dict[str, Any]] = []
    for link in support_links:
        claim_id = _claim_id(link) or "claim.unknown"
        snippet_ids = _text_list(link.get("snippet_ids"))
        source_ids = _text_list(link.get("source_ids"))
        conflict_score = _float(link.get("conflict_score")) or 0.0
        support_score = _float(link.get("support_score")) or 0.0
        polarity = "mixed" if conflict_score > 0.0 else "support"
        if support_score <= 0.0 and conflict_score <= 0.0:
            polarity = "neutral"
        for index, snippet_id in enumerate(snippet_ids or [claim_id]):
            markers.append(
                {
                    "marker_id": f"polarity:{claim_id}:{snippet_id}",
                    "claim_id": claim_id,
                    "source_id": source_ids[min(index, len(source_ids) - 1)]
                    if source_ids
                    else "unknown_source",
                    "snippet_id": snippet_id,
                    "polarity": polarity,
                    "support_status": _text(link.get("support_status")) or "unsupported",
                }
            )
    return markers


def _dependence_records_from_sources(
    selected_sources: Sequence[Mapping[str, Any]],
    *,
    independence_tags: Mapping[str, str],
    include_collapse_reasons: bool = False,
) -> list[dict[str, Any]]:
    source_ids_by_key: dict[str, list[str]] = {}
    sources_by_id = {
        source_id: source
        for source in selected_sources
        if (source_id := _source_id(source))
    }
    for source in selected_sources:
        source_id = _source_id(source)
        if not source_id:
            continue
        key = _source_dependence_key(source, independence_tags)
        source_ids_by_key.setdefault(key, []).append(source_id)
    records: list[dict[str, Any]] = []
    for key, source_ids in sorted(source_ids_by_key.items()):
        raw_count = len(source_ids)
        effective_count = 1 if raw_count > 1 else raw_count
        record = {
            "record_id": f"dependence:{key}",
            "source_ids": source_ids,
            "source_family_independence_tag": key,
            "underlying_study_id": key,
            "dependence_basis": "source_family_independence_tag",
            "raw_source_count": raw_count,
            "effective_source_count": effective_count,
        }
        if include_collapse_reasons:
            record["independence_ref"] = f"scholar-independence-ref:{key}"
            record["collapse_reasons"] = _collapse_reasons_for_sources(
                source_ids=source_ids,
                sources_by_id=sources_by_id,
            )
        records.append(record)
    return records


def _participation_downgrades_from_supports(
    support_links: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for link in support_links:
        claim_id = _claim_id(link) or "claim.unknown"
        requested = _claim_use(link) or "academic_support"
        participation_like = _participation_like_link(link)
        records.append(
            {
                "record_id": f"participation-downgrade:{claim_id}:{requested}",
                "claim_id": claim_id,
                "claim_use_requested": requested,
                "claim_use_allowed": "context-only"
                if participation_like
                else "academic_support",
                "authority_level": _text(link.get("authority_level")) or "research",
                "population_scope": _text(link.get("population_scope"))
                or "general_population",
                "authority_boundary": "academic_publication_not_participation_provenance"
                if participation_like
                else "scholar_academic_support_only",
                "downgrade_reason": (
                    "scholar_source_cannot_satisfy_affected_population_prevalence"
                    if participation_like
                    else "not_participation_claim"
                ),
                "public_projection_effect": "show_limitation"
                if participation_like
                else "none",
            }
        )
    return records


def _participation_downgrades_from_requirements(
    *,
    support_links: Sequence[Mapping[str, Any]],
    requirements_by_claim: Mapping[str, ScholarSupportRequirementSpec],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for link in support_links:
        claim_id = _claim_id(link) or "claim.unknown"
        requirement = requirements_by_claim.get(claim_id)
        if requirement is None:
            continue
        requested = _claim_use(link) or requirement.participation_claim_use_requested
        records.append(
            {
                "record_id": f"participation-downgrade:{claim_id}:{requested}",
                "claim_id": claim_id,
                "claim_use_requested": requested,
                "claim_use_allowed": requirement.participation_claim_use_allowed,
                "authority_level": requirement.authority_level,
                "population_scope": requirement.population_scope,
                "authority_boundary": requirement.authority_boundary,
                "downgrade_reason": (
                    "scholar_source_cannot_satisfy_affected_population_prevalence"
                    if requirement.participation_like_claim
                    else "not_participation_claim"
                ),
                "public_projection_effect": "show_limitation"
                if requirement.participation_like_claim
                else "none",
            }
        )
    return records


def _effective_support_by_claim(
    *,
    support_links: Sequence[Mapping[str, Any]],
    selected_sources: Sequence[Mapping[str, Any]],
    independence_tags: Mapping[str, str],
) -> dict[str, tuple[int, int]]:
    selected_by_id = {
        source_id: source for source in selected_sources if (source_id := _source_id(source))
    }
    counts: dict[str, tuple[int, int]] = {}
    for link in support_links:
        claim_id = _claim_id(link)
        if not claim_id:
            continue
        source_ids = _text_list(link.get("source_ids"))
        raw_count = len(source_ids)
        dependence_keys = {
            _source_dependence_key(selected_by_id.get(source_id, {}), independence_tags)
            for source_id in source_ids
            if source_id in selected_by_id
        }
        counts[claim_id] = (raw_count, len(dependence_keys))
    return counts


def _support_link_with_requirement_counts(
    link: Mapping[str, Any],
    *,
    requirements_by_claim: Mapping[str, ScholarSupportRequirementSpec],
    effective_support_by_claim: Mapping[str, tuple[int, int]],
) -> dict[str, Any]:
    payload = dict(link)
    claim_id = _claim_id(link)
    if not claim_id:
        return payload
    requirement = requirements_by_claim.get(claim_id)
    if requirement is None:
        return payload
    raw_count, effective_count = effective_support_by_claim.get(claim_id, (0, 0))
    payload.update(
        {
            "raw_support_count": raw_count,
            "effective_support_count": effective_count,
            "effective_independence_breadth": effective_count,
            "required_replication_count": requirement.required_replication_count,
            "required_independence_breadth": requirement.required_independence_breadth,
            "requirement_status": "satisfied"
            if (
                effective_count >= requirement.required_replication_count
                and effective_count >= requirement.required_independence_breadth
            )
            else "blocked",
        }
    )
    return payload


def _requirement_deficit_blockers(
    *,
    requirements: Sequence[ScholarSupportRequirementSpec],
    support_links: Sequence[Mapping[str, Any]],
    selected_sources: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    links_by_claim = {
        claim_id: link for link in support_links if (claim_id := _claim_id(link))
    }
    selected_by_id = {
        source_id: source for source in selected_sources if (source_id := _source_id(source))
    }
    blockers: list[dict[str, Any]] = []
    for requirement in requirements:
        link = links_by_claim.get(requirement.claim_id)
        effective_count = _int(link.get("effective_support_count")) if link else 0
        effective_count = effective_count or 0
        claim_sources = _requirement_source_rows(link, selected_by_id)
        if effective_count < requirement.required_replication_count:
            blockers.append(
                _requirement_blocker(
                    code="policy_design_scholar_requirement_replication_unmet",
                    requirement=requirement,
                    observed=effective_count,
                    required=requirement.required_replication_count,
                    dimension="replication_count",
                )
            )
        if effective_count < requirement.required_independence_breadth:
            blockers.append(
                _requirement_blocker(
                    code="policy_design_scholar_requirement_independence_unmet",
                    requirement=requirement,
                    observed=effective_count,
                    required=requirement.required_independence_breadth,
                    dimension="independence_breadth",
                )
            )
        if not _publication_tier_satisfied(requirement, claim_sources):
            blockers.append(
                _requirement_blocker(
                    code="policy_design_scholar_requirement_publication_tier_unmet",
                    requirement=requirement,
                    observed=0,
                    required=1,
                    dimension="publication_tier",
                )
            )
        recency_observed = _recency_days_observed(claim_sources)
        if recency_observed is None or recency_observed > requirement.recency_days:
            blockers.append(
                _requirement_blocker(
                    code="policy_design_scholar_requirement_recency_unmet",
                    requirement=requirement,
                    observed=recency_observed or 0,
                    required=requirement.recency_days,
                    dimension="recency_days",
                )
            )
        citation_depth_observed = _citation_network_depth_observed(claim_sources)
        if citation_depth_observed < requirement.required_citation_network_depth:
            blockers.append(
                _requirement_blocker(
                    code=(
                        "policy_design_scholar_requirement_"
                        "citation_network_depth_unmet"
                    ),
                    requirement=requirement,
                    observed=citation_depth_observed,
                    required=requirement.required_citation_network_depth,
                    dimension="citation_network_depth",
                )
            )
    return blockers


def _requirement_source_rows(
    link: Mapping[str, Any] | None,
    selected_by_id: Mapping[str, Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if link is None:
        return []
    return [
        selected_by_id[source_id]
        for source_id in _text_list(link.get("source_ids"))
        if source_id in selected_by_id
    ]


def _requirement_blocker(
    *,
    code: str,
    requirement: ScholarSupportRequirementSpec,
    observed: int,
    required: int,
    dimension: str,
) -> dict[str, Any]:
    return {
        "blocker_id": f"scholar-requirement-blocker:{requirement.requirement_id}:{dimension}",
        "code": code,
        "severity": "block",
        "requirement_id": requirement.requirement_id,
        "claim_id": requirement.claim_id,
        "dimension": dimension,
        "observed": observed,
        "required": required,
        "next_action": (
            "Acquire additional independent Scholar evidence or emit an accepted "
            "literature deficit for this claim."
        ),
    }


def _publication_tier_satisfied(
    requirement: ScholarSupportRequirementSpec,
    selected_sources: Sequence[Mapping[str, Any]],
) -> bool:
    required_rank = _publication_tier_rank(requirement.required_publication_tier)
    for source in selected_sources:
        if _publication_tier_rank(_publication_tier_from_source(source)) >= required_rank:
            return True
    return False


def _recency_days_observed(sources: Sequence[Mapping[str, Any]]) -> int | None:
    ages = [
        age_days
        for source in sources
        if (age_days := _int(source.get("page_age_days"))) is not None
    ]
    return min(ages) if ages else None


def _citation_network_depth_observed(sources: Sequence[Mapping[str, Any]]) -> int:
    return max(
        (len(_text_list(source.get("citation_network_refs"))) for source in sources),
        default=0,
    )


def _publication_tier_from_source(source: Mapping[str, Any]) -> str:
    explicit = _text(source.get("publication_tier"))
    if explicit:
        return explicit
    source_type = (_text(source.get("source_type")) or "").casefold()
    domain = (_text(source.get("domain")) or "").casefold()
    if source_type in {"academic", "journal", "peer_reviewed", "systematic_review"}:
        return "peer_reviewed"
    if source_type in {"working_paper", "preprint"}:
        return "working_paper"
    if source_type in {"government", "law"} or domain.endswith(".gov"):
        return "government_report"
    return "grey_literature"


def _publication_tier_rank(tier: str) -> int:
    return {
        "grey_literature": 0,
        "government_report": 1,
        "working_paper": 2,
        "peer_reviewed": 3,
        "systematic_review": 4,
    }.get(tier, 0)


def _collapse_reasons_for_sources(
    *,
    source_ids: Sequence[str],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    if len(source_ids) <= 1:
        return []
    rows = [sources_by_id[source_id] for source_id in source_ids if source_id in sources_by_id]
    reasons: list[str] = []
    if _shared_value(rows, "underlying_study_id") or _shared_value(rows, "study_id"):
        reasons.append("shared_underlying_study")
    if _shared_sequence_value(rows, "dataset_ids") or _shared_value(rows, "dataset_id"):
        reasons.append("shared_dataset")
    if _shared_sequence_value(rows, "author_names"):
        reasons.append("shared_author_pool")
    if _shared_sequence_value(rows, "institution_names"):
        reasons.append("shared_institution_pool")
    if _shared_sequence_value(rows, "citation_network_refs"):
        reasons.append("citation_network_dependence")
    if _shared_value(rows, "replication_of_source_id"):
        reasons.append("shared_replication_lineage")
    return reasons or ["shared_source_family"]


def _shared_value(rows: Sequence[Mapping[str, Any]], key: str) -> bool:
    values = {_text(row.get(key)) for row in rows if _text(row.get(key))}
    return len(values) == 1 and bool(values)


def _shared_sequence_value(rows: Sequence[Mapping[str, Any]], key: str) -> bool:
    if len(rows) <= 1:
        return False
    common: set[str] | None = None
    for row in rows:
        values = set(_text_list(row.get(key)))
        if not values:
            return False
        common = values if common is None else common & values
    return bool(common)


def _source_dependence_key(row: Mapping[str, Any], independence_tags: Mapping[str, str]) -> str:
    source_id = _source_id(row) or ""
    return (
        _text(row.get("underlying_study_id"))
        or _text(row.get("study_id"))
        or _text(row.get("source_family_independence_tag"))
        or _text(row.get("independence_tag"))
        or independence_tags.get(source_id)
        or source_id
    )


def _dependence_record_key(record: Mapping[str, Any]) -> str | None:
    return _text(
        record.get("underlying_study_id")
        or record.get("study_id")
        or record.get("source_family_independence_tag")
        or record.get("independence_tag")
        or record.get("dependence_cluster_id")
        or record.get("source_family_cluster_id")
    )


def _record_collapses_sources(record: Mapping[str, Any], source_ids: Sequence[str]) -> bool:
    raw_count = _int(
        record.get("raw_source_count")
        or record.get("raw_publication_count")
        or record.get("raw_line_count")
    )
    effective_count = _int(
        record.get("effective_source_count")
        or record.get("effective_publication_count")
        or record.get("effective_support_count")
    )
    record_source_ids = set(_text_list(record.get("source_ids") or record.get("literature_refs")))
    if raw_count is None:
        raw_count = len(record_source_ids) if record_source_ids else len(source_ids)
    return effective_count is not None and raw_count > 1 and effective_count < raw_count


def _participation_like_link(link: Mapping[str, Any]) -> bool:
    claim_use = _claim_use(link)
    if claim_use in _PARTICIPATION_LIKE_CLAIM_USES:
        return True
    metadata = link.get("metadata")
    if isinstance(metadata, Mapping):
        metadata_use = _claim_use(metadata)
        if metadata_use in _PARTICIPATION_LIKE_CLAIM_USES:
            return True
        if metadata.get("participation_like") is True:
            return True
    claim_family = (
        _text(link.get("claim_family"))
        or _text(link.get("family"))
        or _text(link.get("support_family"))
        or ""
    ).casefold()
    return claim_family in {"participation", "preference", "legitimacy"}


def _claim_use(row: Mapping[str, Any]) -> str:
    return (
        _text(
            row.get("claim_use_requested")
            or row.get("requested_claim_use")
            or row.get("claim_use")
            or row.get("use")
        )
        or ""
    ).casefold()


def _claim_use_allowed(row: Mapping[str, Any]) -> str:
    return (
        _text(
            row.get("claim_use_allowed")
            or row.get("allowed_claim_use")
            or row.get("allowed_use")
        )
        or ""
    ).casefold()


def _claim_id(row: Mapping[str, Any]) -> str | None:
    return _text(row.get("claim_id") or row.get("claim_ref") or row.get("claim"))


def _mapping_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _text_list(value: object) -> list[str]:
    if isinstance(value, str):
        text = _text(value)
        return [text] if text else []
    if not isinstance(value, Sequence):
        return []
    return [text for item in value if (text := _text(item)) is not None]


def _truthy_refs(value: object) -> bool:
    return bool(_text_list(value))


def _source_id(row: Mapping[str, Any]) -> str | None:
    return _text(row.get("source_id") or row.get("literature_ref") or row.get("id"))


def _text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date_from(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if text is None:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.fromisoformat(text.split("T", 1)[0]).date()
        except ValueError:
            return None


def _runtime_refish(value: str) -> bool:
    return value.startswith("sha256:") or value.startswith("cas://sha256/")


def _authority_envelope() -> dict[str, tuple[str, ...] | str]:
    return {
        "authority_role": "producer_authority",
        "provenance_kind": "runtime_emitted",
        "authoritative_for": (
            "academic_support_links",
            "academic_conflict_links",
            "source_scoring",
            "corpus_lineage",
            "source_family_independence",
            "literature_deficit_blockers",
        ),
        "may_not_use_for": (
            "affected_person_representativeness",
            "participation_legitimacy",
            "legal_authority",
            "source_family_satisfaction",
            "method_validity",
            "closeout_pass",
        ),
    }


def _issue(
    code: str,
    message: str,
    *,
    next_action: str,
    refs: Sequence[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "code": code,
        "severity": "fail",
        "phase": "scholar_academic_evidence",
        "message": message,
        "next_action": next_action,
    }
    if refs:
        payload["refs"] = list(refs)
    return payload


def _dedupe_issues(issues: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, tuple[str, ...]]] = set()
    deduped: list[dict[str, Any]] = []
    for issue in issues:
        refs = tuple(str(ref) for ref in issue.get("refs", []) or [])
        key = (str(issue.get("code") or ""), refs)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(dict(issue))
    return deduped


__all__ = [
    "SCHOLAR_ACADEMIC_EVIDENCE_FILENAME",
    "SCHOLAR_ACADEMIC_EVIDENCE_REF_KEY",
    "SCHOLAR_ACADEMIC_EVIDENCE_SCHEMA_VERSION",
    "build_scholar_academic_evidence_report",
    "build_scholar_academic_evidence_report_from_web_bundle",
    "normalize_scholar_academic_evidence_report",
    "scholar_academic_evidence_required",
]
