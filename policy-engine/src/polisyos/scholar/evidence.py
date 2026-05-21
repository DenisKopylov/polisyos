"""Scholar academic and grey-literature evidence contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any

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
    literature_deficit_blockers: Sequence[Mapping[str, Any]] | None = None,
    source_family_independence_tags: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
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
        "literature_deficit_blockers": [
            dict(row) for row in literature_deficit_blockers or ()
        ],
        "source_family_independence_tags": _normalize_independence_tags(
            source_family_independence_tags
        ),
    }
    return normalize_scholar_academic_evidence_report(payload)


def normalize_scholar_academic_evidence_report(
    report: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate and normalize Scholar academic/grey-literature evidence."""

    normalized = dict(report)
    issues: list[dict[str, Any]] = []

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
            "rejected_sources",
            rejected_sources,
            "policy_design_scholar_rejected_sources_missing",
            "Scholar evidence must record rejected literature sources.",
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
    normalized["literature_deficit_blockers"] = blockers
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
    "normalize_scholar_academic_evidence_report",
    "scholar_academic_evidence_required",
]
