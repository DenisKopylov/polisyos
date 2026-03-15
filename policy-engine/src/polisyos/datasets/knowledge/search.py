"""High-level hybrid search API for the dataset catalog graph."""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np

from polisyos.common.logger import get_logger
from polisyos.datasets.knowledge.store import DatasetCatalogStore
from polisyos.datasets.knowledge.types import (
    DatasetSearchResult,
    DistributionResult,
    MetricBindingMatch,
    ResolvedFetchTarget,
)

logger = get_logger(__name__)
_TEXT_QUERY_EXPANSIONS: tuple[tuple[str, str], ...] = (
    ("ввп", "gdp gross domestic product"),
    ("душу населення", "per capita"),
    ("безробіт", "unemployment jobless labour market"),
    ("інфляц", "inflation consumer prices cpi"),
    ("споживчі ціни", "consumer prices cpi"),
    ("міграц", "migration migrant refugee"),
    ("migrat", "migration migrant demography population"),
    ("migrac", "migration migrant demography population"),
    ("тривалість життя", "life expectancy"),
    ("здоров", "health mortality healthy life expectancy"),
    ("sanat", "health hospital medical mortality"),
    ("zdrow", "health hospital medical mortality"),
    ("освіт", "education school enrollment literacy"),
    ("школ", "school enrollment education"),
    ("educat", "education school enrollment literacy"),
    ("edukac", "education school enrollment literacy"),
    ("szkol", "school enrollment education"),
    ("somaj", "unemployment jobless labour market"),
    ("bezroboc", "unemployment jobless labour market"),
    ("buget", "budget municipal revenue expenditure"),
    ("budzet", "budget municipal revenue expenditure"),
    ("demograf", "demography population births deaths"),
    ("довір", "social trust values survey"),
    ("бідн", "poverty deprivation"),
    ("доход", "income earnings wage"),
    ("робоч", "labor force labour force participation"),
    ("участь", "participation"),
    ("врядуван", "institutional quality rule of law government effectiveness"),
)
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


class DatasetCatalogGraph:
    """Read-only access to the dataset catalog with hybrid search."""

    def __init__(
        self,
        db_path: Path,
        index_dir: Path,
        *,
        embedding_model: str = "intfloat/multilingual-e5-large",
    ) -> None:
        self._store = DatasetCatalogStore(db_path, index_dir)
        self._embedding_model_name = embedding_model
        self._embedder = None
        self._embedding_disabled = False
        self._embedding_warning_logged = False

    def _get_query_embedding(self, query: str) -> np.ndarray | None:
        if self._embedding_disabled:
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
                logger.warning("Failed to enable query embeddings; falling back to text-only search: {}", exc)
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
            token
            for token in re.split(r"[^\w]+", normalized, flags=re.UNICODE)
            if len(token) >= 2
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

    def search_datasets(
        self,
        query: str,
        *,
        domain_filter: str | None = None,
        top_k: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> list[DatasetSearchResult]:
        text_results = self._search_text_candidates(query, top_k=top_k)

        vec = self._get_query_embedding(query)
        if vec is None:
            results = text_results[:top_k]
            if domain_filter:
                results = [r for r in results if domain_filter in r.themes]
            return results

        vector_results = self._store.search_by_vector(vec, top_k=top_k * 2, min_similarity=0.2)

        scores: dict[str, float] = {}
        result_map: dict[str, DatasetSearchResult] = {}
        for item in vector_results:
            scores[item.id] = scores.get(item.id, 0.0) + item.similarity * vector_weight
            result_map[item.id] = item
        for item in text_results:
            scores[item.id] = scores.get(item.id, 0.0) + text_weight
            if item.id not in result_map:
                result_map[item.id] = item

        ranked = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
        out: list[DatasetSearchResult] = []
        for did, score in ranked:
            item = result_map[did]
            if domain_filter and domain_filter not in item.themes:
                continue
            out.append(item.model_copy(update={"similarity": score}))
            if len(out) >= top_k:
                break

        return out

    def find_by_polisyos_metric(self, metric_name: str, *, top_k: int = 20) -> list[DatasetSearchResult]:
        return self._store.find_by_polisyos_metric(metric_name, top_k=top_k)

    def find_by_variables(self, variables: list[str], *, top_k: int = 20) -> list[DatasetSearchResult]:
        return self._store.find_by_variables(variables, top_k=top_k)

    def resolve_metric_bindings(self, metric_name: str, *, top_k: int = 20) -> list[MetricBindingMatch]:
        return self._store.resolve_metric_bindings(metric_name, top_k=top_k)

    def resolve_fetch_target(self, dataset_id: str) -> ResolvedFetchTarget | None:
        return self._store.resolve_fetch_target(dataset_id)

    def get_connector_params(self, dataset_id: str) -> dict | None:
        return self._store.get_connector_params(dataset_id)

    def get_distributions(self, dataset_id: str) -> list[DistributionResult]:
        return self._store.get_distributions(dataset_id)

    def close(self) -> None:
        self._store.close()
