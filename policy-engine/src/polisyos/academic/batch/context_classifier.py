"""Context inference helpers for article extraction in phase 0."""

from __future__ import annotations

from polisyos.ir.analytics.context import ContextProfile, ContextProfileInferenceLevel
from polisyos.ir.analytics.literature import ArticleExtractionResult

_INCOME_LEVEL_MAP: dict[str, str] = {
    "US": "high",
    "DE": "high",
    "GB": "high",
    "FR": "high",
    "JP": "high",
    "CA": "high",
    "AU": "high",
    "UA": "lower_middle",
    "NG": "lower_middle",
    "CN": "upper_middle",
    "BR": "upper_middle",
    "IN": "lower_middle",
    "ZA": "upper_middle",
}


def _resolve_primary_context(countries: set[str], scopes: set[str]) -> tuple[str, str]:
    if len(countries) == 1:
        country = next(iter(countries))
        return country, country
    if countries:
        sorted_countries = sorted(countries)
        context_id = "+".join(sorted_countries[:3])
        label = "Multi-country"
        return context_id, label
    if scopes:
        scope = sorted(scopes)[0]
        return scope.lower().replace(" ", "_"), scope
    return "unknown", "Unknown"


def _lookup_income_level(context_id: str) -> str:
    # For multi-country contexts use first country as proxy for phase-0 basic inference.
    head = context_id.split("+", 1)[0]
    return _INCOME_LEVEL_MAP.get(head, "unknown")


def infer_context_from_article(work: dict, extraction: ArticleExtractionResult) -> ContextProfile:
    """Infer basic ContextProfile from OpenAlex metadata and extraction payload."""
    countries: set[str] = set()
    for authorship in work.get("authorships", []):
        if not isinstance(authorship, dict):
            continue
        for institution in authorship.get("institutions", []):
            if not isinstance(institution, dict):
                continue
            country_code = str(institution.get("country_code") or "").upper().strip()
            if country_code:
                countries.add(country_code)

    scopes = {
        str(parameter.geographic_scope).strip()
        for parameter in extraction.empirical_parameters
        if str(parameter.geographic_scope).strip()
    }

    context_id, context_label = _resolve_primary_context(countries, scopes)
    publication_year = work.get("publication_year") or extraction.year or extraction.publication_year

    return ContextProfile(
        context_id=context_id,
        context_label=context_label,
        countries=sorted(countries),
        income_level=_lookup_income_level(context_id),
        publication_year=int(publication_year) if publication_year else None,
        inference_level=ContextProfileInferenceLevel.INFERRED_BASIC,
        data_sources=["openalex_affiliations", "openalex_metadata"],
    )


__all__ = ["infer_context_from_article"]
