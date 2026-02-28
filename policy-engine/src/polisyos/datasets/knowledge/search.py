"""High-level hybrid search API for the dataset catalog graph."""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

from polisyos.datasets.knowledge.store import DatasetCatalogStore
from polisyos.datasets.knowledge.types import DatasetSearchResult, DistributionResult

logger = logging.getLogger(__name__)


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

    def _get_query_embedding(self, query: str) -> np.ndarray | None:
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
            logger.warning("Failed to embed query: %s", exc)
            return None

    def search_datasets(
        self,
        query: str,
        *,
        domain_filter: str | None = None,
        top_k: int = 10,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> list[DatasetSearchResult]:
        text_results = self._store.search_by_text(query, top_k=top_k * 2)

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
            out.append(
                DatasetSearchResult(
                    id=item.id,
                    title=item.title,
                    description=item.description,
                    publisher=item.publisher,
                    themes=item.themes,
                    keywords=item.keywords,
                    variables=item.variables,
                    polisyos_metrics=item.polisyos_metrics,
                    spatial=item.spatial,
                    temporal_start=item.temporal_start,
                    temporal_end=item.temporal_end,
                    source_portal=item.source_portal,
                    formats=item.formats,
                    source=item.source,
                    agency=item.agency,
                    dataset_id=item.dataset_id,
                    dedup_key=item.dedup_key,
                    similarity=score,
                    connector_type=item.connector_type,
                    connector_params=item.connector_params,
                )
            )
            if len(out) >= top_k:
                break

        return out

    def find_by_polisyos_metric(self, metric_name: str, *, top_k: int = 20) -> list[DatasetSearchResult]:
        return self._store.find_by_polisyos_metric(metric_name, top_k=top_k)

    def find_by_variables(self, variables: list[str], *, top_k: int = 20) -> list[DatasetSearchResult]:
        return self._store.find_by_variables(variables, top_k=top_k)

    def get_connector_params(self, dataset_id: str) -> dict | None:
        return self._store.get_connector_params(dataset_id)

    def get_distributions(self, dataset_id: str) -> list[DistributionResult]:
        return self._store.get_distributions(dataset_id)

    def close(self) -> None:
        self._store.close()
