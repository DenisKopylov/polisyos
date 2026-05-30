"""Scenario-aware Lex query normalization for legal authority retrieval."""



from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

LEX_QUERY_NORMALIZATION_SCHEMA_VERSION = "policyos.lex.query_normalization_report.v1"

LEGAL_AUTHORITY_REQUIRED_FACETS = (
    "competence_refs",
    "temporal_validity_refs",
    "policy_instrument_refs",
    "beneficiary_class_refs",
    "fiscal_authority_refs",
    "implementation_agency_refs",
)

_UKRAINIAN_JURISDICTIONS = {"ua", "ukr", "ukraine", "україна"}
_ENGLISH_TAGS = {"en"}
_UKRAINIAN_TAGS = {"uk"}

_CONCEPT_EXPANSIONS: tuple[tuple[str, tuple[str, ...], tuple[str, ...]], ...] = (
    (
        "msme",
        ("msme", "sme", "small business", "medium business", "підприєм", "business"),
        (
            "msme",
            "small and medium enterprises",
            "малі та середні підприємства",
            "мікро-, малі та середні підприємства",
            "підприємство",
            "підприємництво",
            "суб'єкт господарювання",
            "фізична особа-підприємець",
        ),
    ),
    (
        "credit",
        ("credit", "loan", "lending", "кредит", "позик"),
        (
            "credit",
            "credit support",
            "кредит",
            "кредитування",
            "пільговий кредит",
            "державна кредитна підтримка",
            "доступне кредитування",
        ),
    ),
    (
        "grant",
        ("grant", "грант", "non-repayable", "безповорот"),
        (
            "grant",
            "grant support",
            "грант",
            "грантова підтримка",
            "безповоротна допомога",
            "державний грант",
        ),
    ),
    (
        "wartime",
        ("wartime", "war", "martial", "воєн", "військов", "war-time"),
        (
            "wartime",
            "martial law",
            "воєнний стан",
            "воєнного стану",
            "умови воєнного стану",
            "воєнна агресія",
        ),
    ),
    (
        "eligibility",
        ("eligibility", "eligible", "criteria", "умов", "критер", "право"),
        (
            "eligibility",
            "eligibility criteria",
            "критерії eligibility",
            "умови участі",
            "право на участь",
            "вимоги до отримувача",
            "критерії відбору",
        ),
    ),
    (
        "budget",
        ("budget", "fiscal", "бюджет", "видатк", "кошторис"),
        (
            "budget constraint",
            "fiscal authority",
            "бюджетне повноваження",
            "бюджетне обмеження",
            "видатки державного бюджету",
        ),
    ),
    (
        "implementation_agency",
        ("agency", "implementation", "administer", "орган", "агент", "міністер"),
        (
            "implementation agency",
            "administering authority",
            "уповноважений орган",
            "орган реалізації програми",
            "міністерство економіки",
        ),
    ),
)

_FACT_CLASS_EXPANSIONS: Mapping[str, tuple[str, ...]] = {
    "wartime_business_support_authority": (
        "державна підтримка бізнесу",
        "підтримка підприємництва під час воєнного стану",
        "повноваження щодо підтримки бізнесу",
    ),
    "credit_eligibility_rule": (
        "умови кредитування",
        "критерії отримання кредиту",
        "пільговий кредит для підприємців",
    ),
    "budget_constraint": (
        "бюджетні обмеження",
        "фінансування програми",
        "фіскальні повноваження",
    ),
    "equity_and_access_obligation": (
        "рівний доступ",
        "недискримінаційний доступ",
        "доступ для переміщених осіб",
    ),
}


@dataclass(frozen=True)
class LexQueryNormalizationReport:
    """A compact, serializable report for scenario-aware Lex retrieval terms."""

    schema_version: str
    original_terms: tuple[str, ...]
    normalized_terms: tuple[str, ...]
    language_tags: tuple[str, ...]
    jurisdiction_tags: tuple[str, ...]
    confidence: float
    kg_paths: tuple[str, ...]
    language_coverage: Mapping[str, Any]
    legal_requirements: tuple[Mapping[str, Any], ...]
    concept_expansions: tuple[Mapping[str, Any], ...]
    blocker_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""

        return {
            "schema_version": self.schema_version,
            "original_terms": list(self.original_terms),
            "normalized_terms": list(self.normalized_terms),
            "language_tags": list(self.language_tags),
            "jurisdiction_tags": list(self.jurisdiction_tags),
            "confidence": self.confidence,
            "kg_paths": list(self.kg_paths),
            "language_coverage": dict(self.language_coverage),
            "legal_requirements": [dict(item) for item in self.legal_requirements],
            "concept_expansions": [dict(item) for item in self.concept_expansions],
            "blocker_code": self.blocker_code,
        }


def normalize_lex_query_terms(
    *,
    original_terms: Sequence[object] | object,
    target_context: Mapping[str, object] | None = None,
    scenario_evidence_contract: Mapping[str, object] | None = None,
    kg_paths: Sequence[object] | object = (),
    candidate_norm_count: int | None = None,
    blocker_code: str | None = None,
) -> LexQueryNormalizationReport:
    """Expand runtime Lex query terms into bilingual, scenario-aware legal terms."""

    target = _mapping(target_context)
    scenario_contract = _mapping(scenario_evidence_contract)
    original = tuple(_text_list(original_terms))
    jurisdiction_tags = tuple(_jurisdiction_tags(target, scenario_contract))
    legal_requirements = tuple(legal_requirements_from_scenario_contract(scenario_contract))
    expanded_terms, concept_expansions = _expand_terms(
        original_terms=original,
        target_context=target,
        legal_requirements=legal_requirements,
    )
    normalized = tuple(_dedupe([*original, *expanded_terms]))
    language_tags = tuple(_language_tags(normalized, jurisdiction_tags))
    required_languages = ["uk"] if "UA" in jurisdiction_tags else ["en"]
    covered_languages = [tag for tag in ("en", "uk") if tag in language_tags]
    language_coverage = {
        "required": required_languages,
        "covered": covered_languages,
        "status": "pass"
        if set(required_languages).issubset(set(covered_languages))
        else "fail",
    }
    resolved_blocker = _text(blocker_code) or None
    if candidate_norm_count == 0 and resolved_blocker is None:
        resolved_blocker = "no_relevant_norm_found"
    confidence = 0.93 if {"en", "uk"} <= set(language_tags) else 0.72
    return LexQueryNormalizationReport(
        schema_version=LEX_QUERY_NORMALIZATION_SCHEMA_VERSION,
        original_terms=original,
        normalized_terms=normalized,
        language_tags=language_tags,
        jurisdiction_tags=jurisdiction_tags,
        confidence=confidence,
        kg_paths=tuple(_text_list(kg_paths)),
        language_coverage=language_coverage,
        legal_requirements=legal_requirements,
        concept_expansions=tuple(concept_expansions),
        blocker_code=resolved_blocker,
    )


def legal_requirements_from_scenario_contract(
    scenario_evidence_contract: Mapping[str, object] | None,
) -> list[dict[str, Any]]:
    """Project scenario legal requirements with authority facets needed by Lex."""

    contract = _mapping(scenario_evidence_contract)
    requirements: list[dict[str, Any]] = []
    for item in _list(contract.get("requirements")):
        requirement = _mapping(item)
        if requirement.get("domain") != "legal":
            continue
        requirements.append(_normalize_legal_requirement(requirement))
    return requirements


def legal_requirements_from_query_normalization_report(
    query_normalization_report: Mapping[str, object] | None,
) -> list[dict[str, Any]]:
    """Extract legal requirements from a query-normalization payload.

    Older readers sometimes receive the whole wrapper object and sometimes receive the
    nested ``query_normalization_report`` object. This helper accepts both shapes so
    legal requirements discovered during query normalization do not disappear simply
    because the top-level applicability report did not repeat them.
    """

    payload = _mapping(query_normalization_report)
    nested = _mapping(payload.get("query_normalization_report"))
    candidates = _list(payload.get("legal_requirements")) or _list(
        nested.get("legal_requirements")
    )
    requirements: list[dict[str, Any]] = []
    for item in candidates:
        requirement = _mapping(item)
        if not requirement:
            continue
        requirements.append(_normalize_legal_requirement(requirement))
    return requirements


def _normalize_legal_requirement(requirement: Mapping[str, Any]) -> dict[str, Any]:
    required_facets = _dedupe(
        [*_text_list(requirement.get("required_facets")), *LEGAL_AUTHORITY_REQUIRED_FACETS]
    )
    return {
        "requirement_id": _text(requirement.get("requirement_id")),
        "expected_family": _text(requirement.get("expected_family")),
        "required_facets": required_facets,
        "jurisdiction": _text(requirement.get("jurisdiction")),
        "temporal_scope": _text(requirement.get("temporal_scope")),
        "authority_scope": _text_list(requirement.get("authority_scope")),
        "policy_instrument": _text(
            requirement.get("policy_instrument") or requirement.get("instrument_type")
        ),
        "beneficiary_class": _text(requirement.get("beneficiary_class")),
        "fiscal_authority": _text(requirement.get("fiscal_authority")),
        "implementation_agency": _text(requirement.get("implementation_agency")),
        "producer_owner": _text(requirement.get("producer_owner")),
        "reader_owner": _text(requirement.get("reader_owner")),
    }


def _expand_terms(
    *,
    original_terms: tuple[str, ...],
    target_context: Mapping[str, object],
    legal_requirements: tuple[Mapping[str, Any], ...],
) -> tuple[list[str], list[dict[str, Any]]]:
    haystack = " ".join(
        [
            *original_terms,
            _text(target_context.get("policy_domain")),
            _text(target_context.get("domain_hint")),
            *[_text(item.get("expected_family")) for item in legal_requirements],
        ]
    ).casefold()
    expanded: list[str] = []
    concept_expansions: list[dict[str, Any]] = []
    for concept, triggers, terms in _CONCEPT_EXPANSIONS:
        if any(trigger.casefold() in haystack for trigger in triggers):
            expanded.extend(terms)
            concept_expansions.append(
                {
                    "concept": concept,
                    "triggered_by": [
                        trigger for trigger in triggers if trigger.casefold() in haystack
                    ],
                    "terms": list(terms),
                }
            )
    for requirement in legal_requirements:
        expected = _text(requirement.get("expected_family"))
        if not expected:
            continue
        expanded.extend(_FACT_CLASS_EXPANSIONS.get(expected, (expected,)))
    if _is_ukraine_context(target_context) and not any("підприєм" in term for term in expanded):
        expanded.extend(_FACT_CLASS_EXPANSIONS["wartime_business_support_authority"])
        expanded.extend(("підприємство", "підприємництво"))
    return expanded, concept_expansions


def _language_tags(terms: tuple[str, ...], jurisdiction_tags: tuple[str, ...]) -> list[str]:
    tags: set[str] = set()
    for term in terms:
        if any("\u0400" <= char <= "\u04ff" for char in term):
            tags.update(_UKRAINIAN_TAGS)
        if any(("a" <= char.lower() <= "z") for char in term):
            tags.update(_ENGLISH_TAGS)
    if "UA" in jurisdiction_tags:
        tags.add("uk")
    return [tag for tag in ("en", "uk") if tag in tags]


def _jurisdiction_tags(
    target_context: Mapping[str, object],
    scenario_evidence_contract: Mapping[str, object],
) -> list[str]:
    values = [
        _text(target_context.get("jurisdiction") or target_context.get("country")),
        *[
            _text(item.get("jurisdiction"))
            for item in _list(scenario_evidence_contract.get("requirements"))
            if isinstance(item, Mapping)
        ],
    ]
    tags: list[str] = []
    for value in values:
        token = value.casefold()
        if token in _UKRAINIAN_JURISDICTIONS:
            tags.append("UA")
        elif value:
            tags.append(value.upper())
    return _dedupe(tags)


def _is_ukraine_context(target_context: Mapping[str, object]) -> bool:
    return (
        _text(target_context.get("jurisdiction") or target_context.get("country")).casefold()
        in _UKRAINIAN_JURISDICTIONS
    )


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[object]:
    return list(value) if isinstance(value, list | tuple) else []


def _text(value: object) -> str:
    return str(value or "").strip()


def _text_list(value: Sequence[object] | object) -> list[str]:
    if isinstance(value, str):
        token = _text(value)
        return [token] if token else []
    if isinstance(value, list | tuple | set):
        return [token for item in value if (token := _text(item))]
    token = _text(value)
    return [token] if token else []


def _dedupe(values: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        token = _text(value)
        if not token:
            continue
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(token)
    return result


__all__ = [
    "LEGAL_AUTHORITY_REQUIRED_FACETS",
    "LEX_QUERY_NORMALIZATION_SCHEMA_VERSION",
    "LexQueryNormalizationReport",
    "legal_requirements_from_query_normalization_report",
    "legal_requirements_from_scenario_contract",
    "normalize_lex_query_terms",
]
