"""High-level hybrid search API for the dataset catalog graph."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.knowledge.store import DatasetCatalogStore

if TYPE_CHECKING:
    from pathlib import Path

    from polisyos.data_forge.domains.catalog.knowledge.types import (
        DatasetSearchResult,
        DistributionResult,
        MetricBindingMatch,
        ResolvedFetchTarget,
    )

logger = get_logger(__name__)
_TEXT_QUERY_EXPANSIONS: tuple[tuple[str, str], ...] = (
    # ── Macroeconomics ──
    ("ввп", "gdp gross domestic product"),
    ("душу населення", "per capita"),
    ("інфляц", "inflation consumer prices cpi"),
    ("споживчі ціни", "consumer prices cpi"),
    ("interest rate", "interest rate central bank monetary policy"),
    ("public debt", "public debt government debt fiscal"),
    ("fiscal", "fiscal balance budget deficit surplus government"),
    ("buget", "budget municipal revenue expenditure"),
    ("budzet", "budget municipal revenue expenditure"),
    ("trade balance", "trade balance export import"),
    ("trade openn", "trade openness trade to gdp"),
    ("fdi", "foreign direct investment fdi inflows"),
    ("remittanc", "remittances money transfers diaspora"),
    # ── Labour ──
    ("безробіт", "unemployment jobless labour market"),
    ("somaj", "unemployment jobless labour market"),
    ("bezroboc", "unemployment jobless labour market"),
    ("youth unemploy", "youth unemployment young jobless"),
    ("молодіж", "youth unemployment young"),
    ("зарплат", "wage salary earnings"),
    ("wage", "wage salary earnings growth"),
    ("informal", "informal economy shadow economy"),
    ("тіньов", "informal economy shadow economy"),
    ("робоч", "labor force labour force participation"),
    ("участь", "participation"),
    ("productiv", "productivity labor output efficiency"),
    ("minimum wage", "minimum wage floor"),
    # ── Migration ──
    ("міграц", "migration migrant refugee"),
    ("migrat", "migration migrant demography population"),
    ("migrac", "migration migrant demography population"),
    ("refugee", "refugee asylum displaced"),
    ("біженц", "refugee asylum displaced"),
    ("displace", "displaced displacement idp"),
    # ── Poverty & Inequality ──
    ("бідн", "poverty deprivation"),
    ("poverty", "poverty headcount deprivation poor"),
    ("gini", "gini inequality income distribution"),
    ("нерівн", "inequality income distribution gini"),
    ("нрівн", "inequality income distribution gini"),
    # ── Demographics ──
    ("demograf", "demography population births deaths"),
    ("fertility", "fertility birth rate reproduction"),
    ("народжуван", "fertility birth rate"),
    ("urbaniz", "urbanization urban population city"),
    # ── Health ──
    ("тривалість життя", "life expectancy"),
    ("здоров", "health mortality healthy life expectancy"),
    ("sanat", "health hospital medical mortality"),
    ("zdrow", "health hospital medical mortality"),
    ("infant mortality", "infant mortality child death neonatal"),
    ("дитяча смертн", "infant mortality child death"),
    ("maternal mortality", "maternal mortality childbirth"),
    ("vaccinat", "vaccination immunization coverage"),
    ("вакцинац", "vaccination immunization coverage"),
    ("obesity", "obesity overweight bmi"),
    ("diabetes", "diabetes prevalence noncommunicable"),
    ("stunting", "stunting malnutrition child wasting"),
    ("hiv", "hiv aids prevalence"),
    ("tuberculosis", "tuberculosis tb incidence"),
    ("clean water", "clean water drinking water sanitation"),
    ("sanitation", "sanitation sewerage water supply"),
    ("uhc", "universal health coverage uhc"),
    ("suicide", "suicide rate mental health"),
    ("smoking", "smoking tobacco prevalence"),
    ("physician", "physician doctor density"),
    ("hospital bed", "hospital beds health capacity"),
    ("health spend", "health spending expenditure"),
    # ── Education ──
    ("освіт", "education school enrollment literacy"),
    ("школ", "school enrollment education"),
    ("educat", "education school enrollment literacy"),
    ("edukac", "education school enrollment literacy"),
    ("szkol", "school enrollment education"),
    ("tertiary", "tertiary enrollment university higher education"),
    ("вища освіт", "tertiary enrollment university"),
    ("dropout", "dropout rate school leaving"),
    ("years of schooling", "years of schooling education duration"),
    ("research output", "scientific publications research output"),
    ("stem", "stem graduates science technology engineering"),
    # ── Governance ──
    ("довір", "social trust values survey"),
    ("врядуван", "institutional quality rule of law government effectiveness"),
    ("корупц", "corruption anticorruption bribery"),
    ("corrupt", "corruption anticorruption bribery transparency"),
    ("демократ", "democracy democratic political freedom"),
    ("democra", "democracy democratic political freedom civil liberties"),
    ("rule of law", "rule of law judicial courts legal"),
    ("судов", "judicial quality courts rule of law"),
    ("trust in govern", "public trust confidence government institution"),
    ("довіра до уряд", "public trust confidence government"),
    # ── Environment ──
    ("co2", "co2 carbon emissions greenhouse gas"),
    ("викид", "emissions co2 carbon greenhouse"),
    ("renewable energy", "renewable energy clean solar wind"),
    ("відновлюван", "renewable energy clean solar wind"),
    ("forest", "forest cover deforestation area"),
    ("ліс", "forest cover deforestation"),
    ("air quality", "air quality pm2.5 pollution"),
    ("water stress", "water stress scarcity freshwater"),
    ("waste", "waste management recycling"),
    # ── Finance ──
    ("financial inclus", "financial inclusion banking unbanked account"),
    ("credit", "credit access domestic lending"),
    ("доход", "income earnings wage"),
    # ── Infrastructure & Digital ──
    ("internet", "internet users access broadband"),
    ("broadband", "broadband internet fixed connectivity"),
    ("mobile", "mobile phone cellular coverage"),
    ("logistic", "logistics performance infrastructure transport"),
    # ── Security ──
    ("homicide", "homicide murder rate violence"),
    ("military", "military spending defense armed forces"),
    ("conflict", "conflict armed conflict violence war"),
    # ── Social ──
    ("gender equal", "gender equality women rights parity"),
    ("гендерн", "gender equality women rights"),
    ("social capital", "social capital civic participation community"),
    ("social protect", "social protection safety net welfare"),
    ("child labor", "child labor child labour work"),
    ("human capital", "human capital index hci"),
    ("tax revenue", "tax revenue fiscal taxation"),
)
# Authoritative source-metric pairs: (source, canonical_metric) → boost
_SOURCE_METRIC_AFFINITY: dict[tuple[str, str], float] = {
    ("who", "life_expectancy"): 0.20,
    ("who", "health_outcomes"): 0.15,
    ("who", "infant_mortality"): 0.20,
    ("who", "maternal_mortality"): 0.20,
    ("who", "vaccination_coverage"): 0.20,
    ("who", "obesity_prevalence"): 0.15,
    ("who", "tuberculosis_incidence"): 0.20,
    ("who", "universal_health_coverage"): 0.20,
    ("who", "physician_density"): 0.15,
    ("who", "homicide_rate"): 0.15,
    ("worldbank", "gdp_per_capita"): 0.20,
    ("worldbank", "gdp"): 0.20,
    ("worldbank", "inequality"): 0.15,
    ("worldbank", "gini_coefficient"): 0.20,
    ("worldbank", "poverty_rate"): 0.20,
    ("worldbank", "unemployment_rate"): 0.15,
    ("worldbank", "institutional_quality"): 0.15,
    ("worldbank", "corruption_level"): 0.15,
    ("worldbank", "financial_inclusion"): 0.15,
    ("eurostat", "unemployment_rate"): 0.15,
    ("eurostat", "employment_rate"): 0.15,
    ("eurostat", "gender_wage_gap"): 0.15,
    ("eurostat", "inflation"): 0.10,
    ("wvs", "social_trust"): 0.25,
    ("wvs", "public_trust"): 0.20,
    ("wvs", "democracy_quality"): 0.20,
    ("wvs", "gender_equality"): 0.15,
    ("wvs", "social_capital"): 0.20,
    ("wvs", "cultural_cluster"): 0.25,
    ("unesco_uis", "education_outcomes"): 0.15,
    ("unesco_uis", "tertiary_enrollment"): 0.15,
}

_SOURCE_QUERY_HINTS: dict[str, tuple[str, ...]] = {
    "data_gov_ro_broad": ("romania", "românia"),
    "data_gov_ro_exec": ("romania", "românia"),
    "data_gov_md_broad": ("moldova", "republica moldova"),
    "data_gov_md_exec": ("moldova", "republica moldova"),
    "data_gov_pl_broad": ("polska", "poland"),
    "data_gov_pl_exec": ("polska", "poland"),
    "paris_opendata_exec": ("paris", "france"),
    "nyc_opendata_exec": ("new york", "nyc"),
    "chicago_opendata_exec": ("chicago",),
    "wikidata_sparql": ("taxonomy", "entity", "alias"),
    "dbpedia_sparql": ("taxonomy", "entity", "alias"),
}


@dataclass(frozen=True)
class SearchFilters:
    """Search filters public type."""

    sources: tuple[str, ...] = ()
    formats: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    year_min: int | None = None
    year_max: int | None = None
    metrics: tuple[str, ...] = ()
    execution_tier: str | None = None
    min_quality_score: float | None = None


@dataclass(frozen=True)
class QueryMetrics:
    """Query metrics data model."""

    query: str
    vector_search_ms: float = 0.0
    text_search_ms: float = 0.0
    total_candidates: int = 0
    after_filter: int = 0
    returned: int = 0
    top_score: float = 0.0
    mean_score: float = 0.0


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _safe_year(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    if not match:
        return None
    return int(match.group(0))


class DatasetCatalogGraph:
    """Read-only access to the dataset catalog with hybrid search."""

    def __init__(
        self,
        db_path: Path,
        index_dir: Path,
        *,
        overlay_path: Path | None = None,
        embedding_model: str = "intfloat/multilingual-e5-large",
    ) -> None:
        self._store = DatasetCatalogStore(
            db_path,
            index_dir,
            overlay_path=overlay_path,
        )
        self._embedding_model_name = embedding_model
        self._embedder = None
        self._embedding_disabled = False
        self._embedding_warning_logged = False
        self._last_query_metrics: QueryMetrics | None = None

    def _get_query_embedding(self, query: str) -> np.ndarray | None:
        if self._embedding_disabled:
            return None
        if not self._store.has_vector_index():
            return None
        try:
            if self._embedder is None:
                from sentence_transformers import SentenceTransformer

                self._embedder = SentenceTransformer(self._embedding_model_name)
            vec = self._embedder.encode([query])[0].astype(np.float32)
            norm = np.linalg.norm(vec)
            if norm > 0:
                vec = vec / norm
            return vec
        except Exception as exc:
            self._embedding_disabled = True
            if not self._embedding_warning_logged:
                logger.warning(
                    "Failed to enable query embeddings; falling back to text-only search: {}", exc
                )
                self._embedding_warning_logged = True
            return None

    @staticmethod
    def _expanded_text_queries(query: str) -> list[str]:
        normalized = " ".join((query or "").lower().split())
        if not normalized:
            return []
        queries = [query]
        extras: list[str] = []
        tokens = {
            token for token in re.split(r"[^\w]+", normalized, flags=re.UNICODE) if len(token) >= 2
        }
        for needle, expansion in _TEXT_QUERY_EXPANSIONS:
            if needle in normalized or any(needle in token for token in tokens):
                if expansion not in extras:
                    extras.append(expansion)
        if extras:
            queries.append(f"{query} {' '.join(extras)}".strip())
        return queries

    def _search_text_candidates(self, query: str, *, top_k: int) -> list[DatasetSearchResult]:
        merged_scores: dict[str, float] = {}
        merged_items: dict[str, DatasetSearchResult] = {}
        queries = self._expanded_text_queries(query) or [query]
        normalized_query = " ".join((query or "").lower().split())
        for q_index, candidate_query in enumerate(queries):
            weight = 1.0 if q_index == 0 else 0.7
            results = self._store.search_by_text(candidate_query, top_k=top_k * 2)
            for rank, item in enumerate(results):
                score = weight * max((top_k * 2) - rank, 1)
                merged_scores[item.id] = merged_scores.get(item.id, 0.0) + score
                if item.id not in merged_items:
                    merged_items[item.id] = item
        for dataset_id, item in merged_items.items():
            hints = _SOURCE_QUERY_HINTS.get(item.source or "", ())
            if hints and any(hint in normalized_query for hint in hints):
                merged_scores[dataset_id] = merged_scores.get(dataset_id, 0.0) + (top_k * 3.0)
        ranked = sorted(merged_scores.items(), key=lambda pair: (-pair[1], pair[0]))
        out: list[DatasetSearchResult] = []
        for did, score in ranked[:top_k]:
            out.append(merged_items[did].model_copy(update={"similarity": score}))
        return out

    @staticmethod
    def _dataset_haystack(item: DatasetSearchResult) -> str:
        return _normalize_text(
            " ".join(
                (
                    item.title,
                    item.description,
                    " ".join(item.keywords),
                    " ".join(item.variables),
                    " ".join(item.polisyos_metrics),
                    " ".join(item.themes),
                    item.source,
                    item.agency,
                    item.publisher,
                )
            )
        )

    @staticmethod
    def _match_terms(item: DatasetSearchResult, query: str) -> list[str]:
        haystack = DatasetCatalogGraph._dataset_haystack(item)
        tokens = [
            token
            for token in dict.fromkeys(
                re.split(r"[^\w]+", _normalize_text(query), flags=re.UNICODE)
            )
            if len(token) >= 2
        ]
        return [token for token in tokens if token in haystack]

    @staticmethod
    def _expansion_terms(query: str) -> list[str]:
        expanded = DatasetCatalogGraph._expanded_text_queries(query)
        if len(expanded) <= 1:
            return []
        return expanded[-1].split()[len(query.split()) :]

    @staticmethod
    def _freshness_boost(item: DatasetSearchResult) -> float:
        candidate_year = (
            _safe_year(item.last_updated)
            or _safe_year(item.coverage.time_end)
            or _safe_year(item.temporal_end)
        )
        if candidate_year is None:
            return 0.0
        if candidate_year >= 2024:
            return 0.2
        if candidate_year >= 2021:
            return 0.1
        if candidate_year >= 2018:
            return 0.05
        return 0.0

    @staticmethod
    def _metric_boost(item: DatasetSearchResult, query: str) -> float:
        normalized_query = _normalize_text(query)
        metric_tokens = {_normalize_text(metric) for metric in item.polisyos_metrics if metric}
        base = (
            0.25 if any(metric and metric in normalized_query for metric in metric_tokens) else 0.0
        )
        # Source-metric affinity: authoritative source for this metric gets extra boost
        affinity = _SOURCE_METRIC_AFFINITY.get(
            (item.source or "", next(iter(metric_tokens), "")), 0.0
        )
        return base + affinity

    @staticmethod
    def _source_boost(item: DatasetSearchResult, query: str) -> float:
        hints = _SOURCE_QUERY_HINTS.get(item.source or "", ())
        normalized_query = _normalize_text(query)
        return (
            0.3
            if hints and any(_normalize_text(hint) in normalized_query for hint in hints)
            else 0.0
        )

    @staticmethod
    def _tier_boost(item: DatasetSearchResult) -> float:
        """Boost execution-ready datasets so they rank above catalog-only ones."""
        tier = str(getattr(item, "execution_tier", "catalog") or "catalog").strip().lower()
        if tier == "transport_ready":
            return 0.15
        if tier == "fetchable":
            return 0.05
        return 0.0

    @staticmethod
    def _passes_filters(item: DatasetSearchResult, filters: SearchFilters | None) -> bool:
        if filters is None:
            return True
        if filters.sources:
            allowed = {source.strip().lower() for source in filters.sources if source.strip()}
            if (item.source or "").strip().lower() not in allowed:
                return False
        if filters.formats:
            allowed_formats = {fmt.strip().lower() for fmt in filters.formats if fmt.strip()}
            if not allowed_formats.intersection({fmt.strip().lower() for fmt in item.formats}):
                return False
        if filters.countries:
            allowed_countries = {
                country.strip().upper() for country in filters.countries if country.strip()
            }
            item_countries = {country.strip().upper() for country in item.coverage.countries}
            if item.spatial:
                item_countries.add(item.spatial.strip().upper())
            if allowed_countries and not allowed_countries.intersection(item_countries):
                return False
        if filters.metrics:
            allowed_metrics = {metric.strip() for metric in filters.metrics if metric.strip()}
            if not allowed_metrics.intersection(set(item.polisyos_metrics)):
                return False
        if filters.execution_tier and item.execution_tier != filters.execution_tier:
            return False
        if filters.min_quality_score is not None and item.quality.execution_readiness_score < float(
            filters.min_quality_score
        ):
            return False
        item_start = _safe_year(item.coverage.time_start) or _safe_year(item.temporal_start)
        item_end = _safe_year(item.coverage.time_end) or _safe_year(item.temporal_end)
        if (
            filters.year_min is not None
            and item_end is not None
            and item_end < int(filters.year_min)
        ):
            return False
        return not (
            filters.year_max is not None
            and item_start is not None
            and item_start > int(filters.year_max)
        )

    def _with_explanation(
        self,
        item: DatasetSearchResult,
        *,
        query: str,
        text_score: float,
        vector_score: float,
        final_score: float,
        explain: bool,
    ) -> DatasetSearchResult:
        if not explain:
            return item.model_copy(update={"similarity": final_score})
        metric_boost = self._metric_boost(item, query)
        source_boost = self._source_boost(item, query)
        freshness_boost = self._freshness_boost(item)
        tier_boost = self._tier_boost(item)
        explanation = {
            "text_score": round(text_score, 6),
            "vector_score": round(vector_score, 6),
            "metric_boost": round(metric_boost, 6),
            "source_boost": round(source_boost, 6),
            "freshness_boost": round(freshness_boost, 6),
            "tier_boost": round(tier_boost, 6),
            "final_score": round(final_score, 6),
            "matched_terms": self._match_terms(item, query),
            "expansion_terms": self._expansion_terms(query),
        }
        return item.model_copy(
            update={"similarity": final_score, "search_explanation": explanation}
        )

    def search_datasets(
        self,
        query: str,
        *,
        domain_filter: str | None = None,
        top_k: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
        filters: SearchFilters | None = None,
        explain: bool = False,
    ) -> list[DatasetSearchResult]:
        candidate_k = max(top_k * 10, 20)
        text_start = time.perf_counter()
        text_results = self._search_text_candidates(query, top_k=candidate_k)
        text_ms = (time.perf_counter() - text_start) * 1000.0

        vector_ms = 0.0
        vec = self._get_query_embedding(query)
        if vec is None:
            filtered = [result for result in text_results if self._passes_filters(result, filters)]
            results = filtered[:top_k]
            if domain_filter:
                results = [r for r in results if domain_filter in r.themes]
            self._last_query_metrics = QueryMetrics(
                query=query,
                vector_search_ms=0.0,
                text_search_ms=text_ms,
                total_candidates=len(text_results),
                after_filter=len(filtered),
                returned=len(results),
                top_score=float(results[0].similarity) if results else 0.0,
                mean_score=float(sum(item.similarity for item in results) / len(results))
                if results
                else 0.0,
            )
            return [
                self._with_explanation(
                    item,
                    query=query,
                    text_score=float(item.similarity),
                    vector_score=0.0,
                    final_score=float(item.similarity)
                    + self._metric_boost(item, query)
                    + self._source_boost(item, query)
                    + self._freshness_boost(item)
                    + self._tier_boost(item),
                    explain=explain,
                )
                for item in results
            ]

        vector_start = time.perf_counter()
        vector_results = self._store.search_by_vector(vec, top_k=candidate_k, min_similarity=0.2)
        vector_ms = (time.perf_counter() - vector_start) * 1000.0

        scores: dict[str, float] = {}
        text_score_map: dict[str, float] = {}
        vector_score_map: dict[str, float] = {}
        result_map: dict[str, DatasetSearchResult] = {}
        for item in vector_results:
            vector_component = item.similarity * vector_weight
            scores[item.id] = scores.get(item.id, 0.0) + vector_component
            vector_score_map[item.id] = vector_component
            result_map[item.id] = item
        for item in text_results:
            text_component = item.similarity * text_weight
            scores[item.id] = scores.get(item.id, 0.0) + text_component
            text_score_map[item.id] = text_component
            if item.id not in result_map:
                result_map[item.id] = item

        ranked_pairs: list[tuple[str, float]] = []
        for dataset_id, base_score in scores.items():
            item = result_map[dataset_id]
            final_score = (
                base_score
                + self._metric_boost(item, query)
                + self._source_boost(item, query)
                + self._freshness_boost(item)
                + self._tier_boost(item)
            )
            ranked_pairs.append((dataset_id, final_score))
        ranked = sorted(ranked_pairs, key=lambda pair: (-pair[1], pair[0]))
        out: list[DatasetSearchResult] = []
        for did, score in ranked:
            item = result_map[did]
            if domain_filter and domain_filter not in item.themes:
                continue
            if not self._passes_filters(item, filters):
                continue
            out.append(
                self._with_explanation(
                    item,
                    query=query,
                    text_score=text_score_map.get(did, 0.0),
                    vector_score=vector_score_map.get(did, 0.0),
                    final_score=score,
                    explain=explain,
                )
            )
            if len(out) >= top_k:
                break

        self._last_query_metrics = QueryMetrics(
            query=query,
            vector_search_ms=vector_ms,
            text_search_ms=text_ms,
            total_candidates=len(scores),
            after_filter=len(out),
            returned=len(out),
            top_score=float(out[0].similarity) if out else 0.0,
            mean_score=float(sum(item.similarity for item in out) / len(out)) if out else 0.0,
        )
        return out

    def suggest_related(self, dataset_id: str, *, top_k: int = 5) -> list[DatasetSearchResult]:
        base_dataset = self._store.get_dataset(dataset_id)
        if base_dataset is None:
            return []
        query = " ".join(
            part
            for part in (
                base_dataset.title,
                " ".join(base_dataset.polisyos_metrics[:5]),
                " ".join(base_dataset.keywords[:10]),
                " ".join(base_dataset.variables[:10]),
            )
            if part
        )
        related = self.search_datasets(
            query,
            top_k=max(top_k * 3, 10),
            filters=SearchFilters(metrics=tuple(base_dataset.polisyos_metrics))
            if base_dataset.polisyos_metrics
            else None,
        )
        deduped = [item for item in related if item.id != dataset_id]
        return deduped[:top_k]

    @property
    def last_query_metrics(self) -> QueryMetrics | None:
        return self._last_query_metrics

    def find_by_polisyos_metric(
        self, metric_name: str, *, top_k: int = 20
    ) -> list[DatasetSearchResult]:
        return self._store.find_by_polisyos_metric(metric_name, top_k=top_k)

    def find_by_variables(
        self, variables: list[str], *, top_k: int = 20
    ) -> list[DatasetSearchResult]:
        return self._store.find_by_variables(variables, top_k=top_k)

    def resolve_metric_bindings(
        self, metric_name: str, *, top_k: int = 20
    ) -> list[MetricBindingMatch]:
        return self._store.resolve_metric_bindings(metric_name, top_k=top_k)

    def search_metric_bindings(
        self,
        query: str,
        *,
        top_k: int = 20,
        modes: tuple[str, ...] = ("exact", "alias", "lexical", "semantic"),
    ) -> list[MetricBindingMatch]:
        return self._store.search_metric_bindings(query, top_k=top_k, modes=modes)

    def resolve_fetch_target(self, dataset_id: str) -> ResolvedFetchTarget | None:
        return self._store.resolve_fetch_target(dataset_id)

    def get_connector_params(self, dataset_id: str) -> dict | None:
        return self._store.get_connector_params(dataset_id)

    def get_distributions(self, dataset_id: str) -> list[DistributionResult]:
        return self._store.get_distributions(dataset_id)

    def close(self) -> None:
        self._store.close()
