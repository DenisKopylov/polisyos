"""Read-only access to the DuckDB dataset catalog + HNSW vector index."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import numpy as np

from polisyos.datasets.knowledge.types import DatasetSearchResult, DistributionResult

logger = logging.getLogger(__name__)

_DATASET_SELECT = (
    "id, title, description, publisher, spatial, "
    "temporal_start, temporal_end, source_portal, "
    "polisyos_metrics, keywords, themes, variables, formats, "
    "source, agency, dataset_id, dedup_key"
)


class DatasetCatalogStore:
    """Read-only handle to the dataset catalog (DuckDB + HNSW)."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = db_path
        self._index_dir = index_dir
        self._con = duckdb.connect(str(db_path), read_only=True)

        self._dataset_index = None
        self._dataset_ids: list[str] | None = None

    def _load_dataset_index(self) -> None:
        if self._dataset_index is not None:
            return
        import hnswlib

        npz_path = self._index_dir / "ds_dataset_embeddings.npz"
        hnsw_path = self._index_dir / "ds_dataset_index.hnsw"
        if not npz_path.exists() or not hnsw_path.exists():
            logger.warning("Dataset index files not found in %s", self._index_dir)
            return

        data = np.load(str(npz_path), allow_pickle=True)
        self._dataset_ids = list(data["ids"])
        dim = int(data["vectors"].shape[1])

        idx = hnswlib.Index(space="cosine", dim=dim)
        idx.load_index(str(hnsw_path), max_elements=len(self._dataset_ids))
        idx.set_ef(100)
        self._dataset_index = idx

    def _to_dataset_result(self, row: tuple, *, similarity: float = 0.0) -> DatasetSearchResult:
        return DatasetSearchResult(
            id=row[0],
            title=row[1] or "",
            description=row[2] or "",
            publisher=row[3] or "",
            spatial=row[4] or "",
            temporal_start=str(row[5]) if row[5] else None,
            temporal_end=str(row[6]) if row[6] else None,
            source_portal=row[7] or "",
            polisyos_metrics=list(row[8] or []),
            keywords=list(row[9] or []),
            themes=list(row[10] or []),
            variables=list(row[11] or []),
            formats=list(row[12] or []),
            source=row[13] or "",
            agency=row[14] or "",
            dataset_id=row[15] or "",
            dedup_key=row[16] or "",
            similarity=similarity,
        )

    def search_by_vector(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[DatasetSearchResult]:
        self._load_dataset_index()
        if self._dataset_index is None or self._dataset_ids is None:
            return []

        k = min(top_k, len(self._dataset_ids))
        labels, distances = self._dataset_index.knn_query(query_vector.reshape(1, -1), k=k)
        results: list[DatasetSearchResult] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            did = self._dataset_ids[int(label)]
            row = self._con.execute(
                f"SELECT {_DATASET_SELECT} FROM ds_datasets WHERE id = ?",
                [did],
            ).fetchone()
            if row:
                results.append(self._to_dataset_result(row, similarity=similarity))
        return results

    def search_by_text(self, query: str, *, top_k: int = 20) -> list[DatasetSearchResult]:
        pattern = f"%{query}%"
        rows = self._con.execute(
            f"SELECT {_DATASET_SELECT} FROM ds_datasets "
            "WHERE title ILIKE ? OR description ILIKE ? LIMIT ?",
            [pattern, pattern, top_k],
        ).fetchall()
        return [self._to_dataset_result(r, similarity=1.0) for r in rows]

    def find_by_polisyos_metric(self, metric_name: str, *, top_k: int = 20) -> list[DatasetSearchResult]:
        rows = self._con.execute(
            f"SELECT {_DATASET_SELECT} FROM ds_datasets "
            "WHERE list_contains(polisyos_metrics, ?) LIMIT ?",
            [metric_name, top_k],
        ).fetchall()
        return [self._to_dataset_result(r, similarity=1.0) for r in rows]

    def find_by_variables(self, variables: list[str], *, top_k: int = 20) -> list[DatasetSearchResult]:
        if not variables:
            return []
        conditions = " OR ".join("list_contains(variables, ?)" for _ in variables)
        rows = self._con.execute(
            f"SELECT {_DATASET_SELECT} FROM ds_datasets WHERE {conditions} LIMIT ?",
            [*variables, top_k],
        ).fetchall()
        return [self._to_dataset_result(r, similarity=1.0) for r in rows]

    def get_connector_params(self, dataset_id: str) -> dict | None:
        row = self._con.execute(
            "SELECT connector_type, connector_params "
            "FROM ds_distributions "
            "WHERE dataset_id = ? AND connector_type IS NOT NULL AND connector_type != '' "
            "ORDER BY quality_score DESC LIMIT 1",
            [dataset_id],
        ).fetchone()
        if row is None:
            return None
        import json

        params = row[1]
        if isinstance(params, str):
            params = json.loads(params)
        return {"type": row[0], "params": params}

    def get_distributions(self, dataset_id: str) -> list[DistributionResult]:
        rows = self._con.execute(
            "SELECT id, dataset_id, url, format, connector_type, connector_params, quality_score "
            "FROM ds_distributions WHERE dataset_id = ? ORDER BY quality_score DESC",
            [dataset_id],
        ).fetchall()
        import json

        out: list[DistributionResult] = []
        for row in rows:
            params = row[5]
            if isinstance(params, str):
                params = json.loads(params)
            out.append(
                DistributionResult(
                    id=row[0],
                    dataset_id=row[1],
                    url=row[2] or "",
                    format=row[3] or "",
                    connector_type=row[4] or "",
                    connector_params=params if isinstance(params, dict) else {},
                    quality_score=float(row[6]) if row[6] is not None else 0.0,
                )
            )
        return out

    def close(self) -> None:
        self._con.close()
