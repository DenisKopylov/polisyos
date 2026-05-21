"""Offline citation-faithfulness checks for public factual and legal claims."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from typing import Any, Literal

SCHEMA_VERSION = "policyos.scientist.citation_faithfulness.v1"

CitationFaithfulnessLabel = Literal[
    "supports",
    "partially_supports",
    "scope_limited",
    "contradicts",
    "irrelevant",
    "fabricated",
    "unverifiable",
]

BLOCKING_CITATION_LABELS = frozenset(
    {
        "partially_supports",
        "scope_limited",
        "contradicts",
        "irrelevant",
        "fabricated",
        "unverifiable",
    }
)

_PUBLIC_FACTUAL_LEGAL_FAMILIES = frozenset(
    {
        "empirical",
        "fact",
        "factual",
        "legal",
        "normative",
        "statute",
        "statutory",
    }
)
_UNVERIFIABLE_STATUSES = frozenset(
    {
        "blocked",
        "error",
        "failed",
        "missing",
        "not_found",
        "paywalled",
        "unavailable",
        "unfetched",
        "unknown",
    }
)
_FALSE_VALUES = frozenset({"0", "false", "internal", "no", "private"})
_SCOPE_DIMENSIONS = ("legal_scope", "jurisdiction", "date", "population")
_STOP_WORDS = frozenset(
    {
        "a",
        "all",
        "an",
        "and",
        "are",
        "as",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "the",
        "to",
        "was",
        "were",
    }
)


def build_citation_faithfulness_report(
    *,
    claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Return a deterministic citation-faithfulness report.

    The checker uses only provided refs, snippets, and structured scope
    metadata. It intentionally does not call live LLM judges, network fetchers,
    or nondeterministic semantic services.
    """

    evidence_by_ref = _index_evidence(evidence)
    claim_reports: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []

    for index, claim in enumerate(claims):
        claim_id = _claim_id(claim, index)
        claim_family = _claim_family(claim)
        citation_refs = _citation_refs(claim)
        citation_reports: list[dict[str, Any]] = []

        if _is_public_factual_or_legal_claim(claim) and not citation_refs:
            issues.append(
                _issue(
                    code="public_claim_missing_citation",
                    claim_id=claim_id,
                    claim_text=_claim_text(claim),
                    message=f"Public factual/legal claim {claim_id} has no cited refs.",
                    next_action=(
                        "Attach source-backed citation_refs or mark the claim as "
                        "non-public/internal with rationale."
                    ),
                )
            )

        for citation_ref in citation_refs:
            citation = _classify_citation(
                claim=claim,
                claim_id=claim_id,
                citation_ref=citation_ref,
                evidence=evidence_by_ref.get(citation_ref),
            )
            citation_reports.append(citation)
            if (
                _is_public_factual_or_legal_claim(claim)
                and citation["label"] in BLOCKING_CITATION_LABELS
            ):
                issues.append(
                    _issue(
                        code="public_claim_has_unfaithful_citation",
                        claim_id=claim_id,
                        claim_text=_claim_text(claim),
                        citation_ref=citation_ref,
                        label=citation["label"],
                        mismatch_dimensions=citation["mismatch_dimensions"],
                        message=(
                            f"Public factual/legal claim {claim_id} cites "
                            f"{citation_ref} as {citation['label']}."
                        ),
                        next_action=(
                            "Replace or repair the citation, narrow the claim to the "
                            "source scope, or route the claim for human review."
                        ),
                    )
                )

        claim_has_blocking_issue = any(
            issue.get("claim_id") == claim_id and issue.get("severity") == "fail"
            for issue in issues
        )
        claim_status = "fail" if (
            claim_has_blocking_issue
            or any(
                citation["label"] in BLOCKING_CITATION_LABELS
                for citation in citation_reports
                if _is_public_factual_or_legal_claim(claim)
            )
        ) else "pass"
        claim_reports.append(
            {
                "claim_id": claim_id,
                "claim_family": claim_family,
                "public": _is_public_factual_or_legal_claim(claim),
                "claim_text": _claim_text(claim),
                "citation_refs": citation_refs,
                "citations": citation_reports,
                "status": claim_status,
            }
        )

    label_counts = Counter(
        citation["label"]
        for claim_report in claim_reports
        for citation in claim_report["citations"]
    )
    blocking_issues = [
        issue for issue in issues if str(issue.get("severity")) == "fail"
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "fail" if blocking_issues else "pass",
        "live_llm_judging_enabled": False,
        "claims": claim_reports,
        "issues": issues,
        "blocking_issue_count": len(blocking_issues),
        "label_counts": dict(sorted(label_counts.items())),
        "residual_risk": {
            "level": "medium",
            "deterministic_only": True,
            "summary": (
                "Offline checks catch fabricated refs, explicit contradictions, "
                "irrelevant snippets, and structured scope mismatches, but they "
                "do not prove full semantic entailment."
            ),
        },
        "false_pass_limits": [
            "semantic_paraphrase_not_proven",
            "metadata_omission_can_hide_scope_mismatch",
            "quoted_text_may_be_selective_without_full_source_context",
            "structured_support_claim_ids_are_trusted_inputs",
        ],
    }


def build_policy_context_citation_faithfulness_report(
    *,
    claims: Sequence[Mapping[str, Any]],
    normative_evidence: Mapping[str, Any] | None = None,
    fabric_retrieval_trace: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build an offline citation-faithfulness report from runtime evidence payloads."""

    claim_ids_by_ref = _claim_ids_by_citation_ref(claims)
    evidence: list[dict[str, Any]] = []
    for norm in _mapping_items((normative_evidence or {}).get("applied_norms")):
        ref_id = _first_text(
            norm.get("norm_id"),
            norm.get("id"),
            norm.get("artifact_id"),
            norm.get("norm_ref"),
        )
        if not ref_id:
            continue
        evidence.append(
            {
                "ref_id": ref_id,
                "source_id": ref_id,
                "artifact_id": _text(norm.get("artifact_id")),
                "text": _first_text(
                    norm.get("text"),
                    norm.get("legal_text"),
                    norm.get("summary"),
                    norm.get("description"),
                    norm.get("relevance_rationale"),
                    norm.get("title"),
                    ref_id,
                ),
                "jurisdiction": norm.get("jurisdiction"),
                "legal_scope": norm.get("legal_scope") or norm.get("fact_class"),
                "effective_from": norm.get("effective_from") or norm.get("valid_from"),
                "effective_to": norm.get("effective_to") or norm.get("valid_to"),
                "supports_claim_ids": claim_ids_by_ref.get(ref_id, []),
                "fetch_status": norm.get("fetch_status") or "ok",
            }
        )
    for source in _mapping_items((fabric_retrieval_trace or {}).get("selected_sources")):
        ref_id = _first_text(
            source.get("source_id"),
            source.get("data_snapshot_ref"),
            source.get("artifact_id"),
            source.get("id"),
            source.get("url"),
        )
        if not ref_id:
            continue
        evidence.append(
            {
                "ref_id": ref_id,
                "source_id": ref_id,
                "artifact_id": _text(source.get("artifact_id") or source.get("data_snapshot_ref")),
                "url": _text(source.get("url")),
                "text": _first_text(
                    source.get("text"),
                    source.get("snippet"),
                    source.get("summary"),
                    source.get("title"),
                    source.get("source_family"),
                    ref_id,
                ),
                "jurisdiction": source.get("jurisdiction"),
                "population": source.get("population") or source.get("coverage"),
                "supports_claim_ids": claim_ids_by_ref.get(ref_id, []),
                "fetch_status": source.get("fetch_status") or source.get("status") or "ok",
            }
        )
    return build_citation_faithfulness_report(claims=claims, evidence=evidence)


def _classify_citation(
    *,
    claim: Mapping[str, Any],
    claim_id: str,
    citation_ref: str,
    evidence: Mapping[str, Any] | None,
) -> dict[str, Any]:
    if evidence is None:
        return _citation_result(
            citation_ref=citation_ref,
            label="fabricated",
            reason_codes=["citation_ref_not_found"],
        )

    evidence_text = _evidence_text(evidence)
    if _is_unverifiable(evidence, evidence_text=evidence_text):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="unverifiable",
            reason_codes=["source_not_verifiable"],
        )

    if _contains_id(evidence, "contradicts_claim_ids", claim_id):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="contradicts",
            reason_codes=["source_contradicts_claim"],
        )

    mismatch_dimensions = _mismatch_dimensions(claim, evidence)
    explicit_support = _contains_id(evidence, "supports_claim_ids", claim_id)
    if explicit_support:
        if any(dimension in mismatch_dimensions for dimension in _SCOPE_DIMENSIONS):
            return _citation_result(
                citation_ref=citation_ref,
                evidence_ref=_evidence_ref(evidence),
                label="scope_limited",
                reason_codes=["structured_scope_mismatch"],
                mismatch_dimensions=mismatch_dimensions,
            )
        if "exception" in mismatch_dimensions:
            return _citation_result(
                citation_ref=citation_ref,
                evidence_ref=_evidence_ref(evidence),
                label="partially_supports",
                reason_codes=["source_exception_not_preserved"],
                mismatch_dimensions=mismatch_dimensions,
            )
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="supports",
            reason_codes=["structured_support_match"],
        )

    if _looks_contradictory(_claim_text(claim), evidence_text):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="contradicts",
            reason_codes=["lexical_contradiction_proxy"],
        )

    lexical_overlap = _lexical_claim_overlap(_claim_text(claim), evidence_text)
    if lexical_overlap < 0.22:
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="irrelevant",
            reason_codes=["low_lexical_overlap"],
            lexical_overlap=round(lexical_overlap, 6),
        )
    if any(dimension in mismatch_dimensions for dimension in _SCOPE_DIMENSIONS):
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="scope_limited",
            reason_codes=["lexical_match_scope_mismatch"],
            mismatch_dimensions=mismatch_dimensions,
            lexical_overlap=round(lexical_overlap, 6),
        )
    if "exception" in mismatch_dimensions:
        return _citation_result(
            citation_ref=citation_ref,
            evidence_ref=_evidence_ref(evidence),
            label="partially_supports",
            reason_codes=["lexical_match_exception_mismatch"],
            mismatch_dimensions=mismatch_dimensions,
            lexical_overlap=round(lexical_overlap, 6),
        )
    return _citation_result(
        citation_ref=citation_ref,
        evidence_ref=_evidence_ref(evidence),
        label="supports" if lexical_overlap >= 0.62 else "partially_supports",
        reason_codes=["lexical_support_proxy"],
        lexical_overlap=round(lexical_overlap, 6),
    )


def _citation_result(
    *,
    citation_ref: str,
    label: CitationFaithfulnessLabel,
    reason_codes: list[str],
    evidence_ref: str | None = None,
    mismatch_dimensions: list[str] | None = None,
    lexical_overlap: float | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "citation_ref": citation_ref,
        "evidence_ref": evidence_ref or citation_ref,
        "label": label,
        "reason_codes": reason_codes,
        "mismatch_dimensions": sorted(mismatch_dimensions or []),
    }
    if lexical_overlap is not None:
        result["lexical_overlap"] = lexical_overlap
    return result


def _issue(
    *,
    code: str,
    claim_id: str,
    claim_text: str,
    message: str,
    next_action: str,
    citation_ref: str | None = None,
    label: str | None = None,
    mismatch_dimensions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "fail",
        "layer": "scientist_policy_artifacts",
        "phase": "citation_faithfulness",
        "claim_id": claim_id,
        "claim_text": claim_text,
        "citation_ref": citation_ref,
        "label": label,
        "mismatch_dimensions": sorted(mismatch_dimensions or []),
        "message": message,
        "next_action": next_action,
    }


def _index_evidence(
    evidence: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    indexed: dict[str, Mapping[str, Any]] = {}
    for item in evidence:
        for key in (
            "ref_id",
            "citation_ref",
            "snippet_id",
            "source_id",
            "id",
            "artifact_id",
            "url",
        ):
            value = _text(item.get(key))
            if value:
                indexed.setdefault(value, item)
    return indexed


def _mapping_items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes | bytearray):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _claim_ids_by_citation_ref(
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for index, claim in enumerate(claims):
        claim_id = _claim_id(claim, index)
        for ref in _citation_refs(claim):
            output.setdefault(ref, []).append(claim_id)
    return {ref: sorted(dict.fromkeys(ids)) for ref, ids in output.items()}


def _first_text(*values: object) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _claim_id(claim: Mapping[str, Any], index: int) -> str:
    return _text(claim.get("claim_id") or claim.get("id") or f"claim_{index + 1}")


def _claim_family(claim: Mapping[str, Any]) -> str:
    return _normal_token(
        claim.get("claim_family") or claim.get("family") or claim.get("claim_type")
    )


def _claim_text(claim: Mapping[str, Any]) -> str:
    return _text(claim.get("text") or claim.get("claim_text") or claim.get("claim"))


def _citation_refs(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in (
        "citation_refs",
        "citations",
        "source_refs",
        "source_ref",
        "evidence_refs",
        "legal_refs",
        "norm_refs",
    ):
        refs.extend(_as_text_list(claim.get(key)))
    return sorted(dict.fromkeys(refs))


def _is_public_factual_or_legal_claim(claim: Mapping[str, Any]) -> bool:
    raw_public = claim.get("public")
    if raw_public is None:
        public = True
    elif isinstance(raw_public, bool):
        public = raw_public
    else:
        public = _normal_token(raw_public) not in _FALSE_VALUES
    return public and _claim_family(claim) in _PUBLIC_FACTUAL_LEGAL_FAMILIES


def _contains_id(evidence: Mapping[str, Any], key: str, claim_id: str) -> bool:
    return claim_id in set(_as_text_list(evidence.get(key)))


def _is_unverifiable(
    evidence: Mapping[str, Any],
    *,
    evidence_text: str,
) -> bool:
    status = _normal_token(
        evidence.get("fetch_status") or evidence.get("status") or evidence.get("state")
    )
    if status in _UNVERIFIABLE_STATUSES:
        return True
    if evidence.get("unverifiable") is True:
        return True
    return not evidence_text and not (
        evidence.get("supports_claim_ids") or evidence.get("contradicts_claim_ids")
    )


def _evidence_text(evidence: Mapping[str, Any]) -> str:
    return _text(
        evidence.get("text")
        or evidence.get("snippet")
        or evidence.get("quote")
        or evidence.get("summary")
    )


def _evidence_ref(evidence: Mapping[str, Any]) -> str | None:
    for key in ("ref_id", "citation_ref", "snippet_id", "source_id", "id", "url"):
        value = _text(evidence.get(key))
        if value:
            return value
    return None


def _mismatch_dimensions(
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> list[str]:
    mismatches: list[str] = []
    for key in ("legal_scope", "jurisdiction", "population"):
        if _has_token_mismatch(claim.get(key), evidence.get(key)):
            mismatches.append(key)
    if _has_date_mismatch(claim, evidence):
        mismatches.append("date")
    claim_exceptions = set(_as_normal_tokens(claim.get("exceptions")))
    evidence_exceptions = set(_as_normal_tokens(evidence.get("exceptions")))
    if evidence_exceptions and not evidence_exceptions.issubset(claim_exceptions):
        mismatches.append("exception")
    return sorted(dict.fromkeys(mismatches))


def _has_token_mismatch(left: object, right: object) -> bool:
    left_tokens = set(_as_normal_tokens(left))
    right_tokens = set(_as_normal_tokens(right))
    return bool(left_tokens and right_tokens and left_tokens.isdisjoint(right_tokens))


def _has_date_mismatch(
    claim: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> bool:
    claim_date = _first_date(
        claim.get("as_of"),
        claim.get("date"),
        claim.get("effective_date"),
        claim.get("claim_date"),
    )
    if claim_date is None:
        return False
    effective_from = _first_date(
        evidence.get("effective_from"),
        evidence.get("valid_from"),
        evidence.get("published_at"),
    )
    effective_to = _first_date(
        evidence.get("effective_to"),
        evidence.get("valid_to"),
        evidence.get("expires_at"),
        evidence.get("withdrawn_at"),
    )
    if effective_from is not None and claim_date < effective_from:
        return True
    return bool(effective_to is not None and claim_date > effective_to)


def _looks_contradictory(claim_text: str, evidence_text: str) -> bool:
    claim_tokens = set(_tokens(claim_text))
    evidence_tokens = set(_tokens(evidence_text))
    if len(claim_tokens.intersection(evidence_tokens)) < 3:
        return False
    claim_permits = bool(
        claim_tokens.intersection(
            {"allow", "allows", "permit", "permits", "permitted"}
        )
    )
    evidence_prohibits = bool(
        evidence_tokens.intersection(
            {
                "ban",
                "bans",
                "bar",
                "bars",
                "forbid",
                "forbids",
                "prohibit",
                "prohibits",
            }
        )
    )
    claim_available = bool(
        claim_tokens.intersection(
            {"available", "eligible", "qualify", "qualifies"}
        )
    )
    evidence_excludes = bool(
        evidence_tokens.intersection({"exclude", "excluded", "excludes", "except", "ineligible"})
    )
    return (claim_permits and evidence_prohibits) or (
        claim_available and evidence_excludes
    )


def _lexical_claim_overlap(claim_text: str, evidence_text: str) -> float:
    claim_tokens = set(_tokens(claim_text))
    if not claim_tokens:
        return 0.0
    evidence_tokens = set(_tokens(evidence_text))
    return len(claim_tokens.intersection(evidence_tokens)) / len(claim_tokens)


def _tokens(value: str) -> list[str]:
    return [
        token
        for token in re.findall(r"[a-z0-9_]+", value.casefold())
        if token and token not in _STOP_WORDS
    ]


def _first_date(*values: object) -> date | None:
    for value in values:
        parsed = _parse_date(value)
        if parsed is not None:
            return parsed
    return None


def _parse_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _as_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_text(value)] if _text(value) else []
    if isinstance(value, Mapping):
        for key in ("ref_id", "citation_ref", "source_id", "snippet_id", "id"):
            ref = _text(value.get(key))
            if ref:
                return [ref]
        return []
    if isinstance(value, Sequence):
        refs: list[str] = []
        for item in value:
            refs.extend(_as_text_list(item))
        return refs
    return [_text(value)] if _text(value) else []


def _as_normal_tokens(value: object) -> list[str]:
    return [_normal_token(item) for item in _as_text_list(value) if _normal_token(item)]


def _normal_token(value: object) -> str:
    token = re.sub(r"[^a-z0-9_]+", "_", _text(value).casefold()).strip("_")
    return re.sub(r"_+", "_", token)


def _text(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "BLOCKING_CITATION_LABELS",
    "SCHEMA_VERSION",
    "CitationFaithfulnessLabel",
    "build_citation_faithfulness_report",
    "build_policy_context_citation_faithfulness_report",
]
