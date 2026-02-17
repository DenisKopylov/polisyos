"""Read-only access to the DuckDB knowledge graph + HNSW vector indexes.

This is the persistence layer used by ``search.py``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import numpy as np

from polisyos.lex.knowledge.types import (
    LegalFactResult,
    LegalProvisionResult,
    LegalSearchResult,
)

logger = logging.getLogger(__name__)

_FACT_SELECT = (
    "fact_id, subject_en, predicate, object_en, fact_text, "
    "confidence, norm_type, action_canon, norm_type_canon, "
    "condition_text_uk, exception_text_uk, procedure_text_uk, "
    "thresholds_json, source_quote_uk, doc_name, doc_reestr_code, provision_citation"
)


class LegalKnowledgeStore:
    """Read-only handle to the legal knowledge graph (DuckDB + HNSW)."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = db_path
        self._index_dir = index_dir
        self._con = duckdb.connect(str(db_path), read_only=True)

        self._entity_index = None
        self._entity_ids: list[str] | None = None
        self._fact_index = None
        self._fact_ids: list[str] | None = None
        self._provision_index = None
        self._provision_ids: list[str] | None = None

    # ------------------------------------------------------------------
    # Vector index loading (lazy)
    # ------------------------------------------------------------------

    def _load_entity_index(self) -> None:
        if self._entity_index is not None:
            return
        import hnswlib

        npz_path = self._index_dir / "lex_entity_embeddings.npz"
        hnsw_path = self._index_dir / "lex_entity_index.hnsw"
        if not npz_path.exists() or not hnsw_path.exists():
            logger.warning("Entity index files not found in %s", self._index_dir)
            return

        data = np.load(str(npz_path), allow_pickle=True)
        self._entity_ids = list(data["ids"])
        dim = int(data["vectors"].shape[1])

        idx = hnswlib.Index(space="cosine", dim=dim)
        idx.load_index(str(hnsw_path), max_elements=len(self._entity_ids))
        idx.set_ef(100)
        self._entity_index = idx

    def _load_fact_index(self) -> None:
        if self._fact_index is not None:
            return
        import hnswlib

        npz_path = self._index_dir / "lex_fact_embeddings.npz"
        hnsw_path = self._index_dir / "lex_fact_index.hnsw"
        if not npz_path.exists() or not hnsw_path.exists():
            logger.warning("Fact index files not found in %s", self._index_dir)
            return

        data = np.load(str(npz_path), allow_pickle=True)
        self._fact_ids = list(data["ids"])
        dim = int(data["vectors"].shape[1])

        idx = hnswlib.Index(space="cosine", dim=dim)
        idx.load_index(str(hnsw_path), max_elements=len(self._fact_ids))
        idx.set_ef(100)
        self._fact_index = idx

    def _load_provision_index(self) -> None:
        if self._provision_index is not None:
            return
        import hnswlib

        npz_path = self._index_dir / "lex_provision_embeddings.npz"
        hnsw_path = self._index_dir / "lex_provision_index.hnsw"
        if not npz_path.exists() or not hnsw_path.exists():
            logger.warning("Provision index files not found in %s", self._index_dir)
            return

        data = np.load(str(npz_path), allow_pickle=True)
        self._provision_ids = list(data["ids"])
        dim = int(data["vectors"].shape[1])

        idx = hnswlib.Index(space="cosine", dim=dim)
        idx.load_index(str(hnsw_path), max_elements=len(self._provision_ids))
        idx.set_ef(100)
        self._provision_index = idx

    def _to_fact_result(self, row: tuple, *, similarity: float) -> LegalFactResult:
        return LegalFactResult(
            fact_id=row[0],
            subject_name=row[1] or "",
            predicate=row[2],
            object_name=row[3] or "",
            fact_text=row[4],
            confidence=float(row[5]),
            norm_type=row[6] or "",
            action_canon=row[7] or "",
            norm_type_canon=row[8] or "",
            condition_text_uk=row[9] or "",
            exception_text_uk=row[10] or "",
            procedure_text_uk=row[11] or "",
            thresholds_json=row[12] or "",
            source_quote_uk=row[13] or "",
            doc_name=row[14] or "",
            doc_reestr_code=row[15] or "",
            provision_citation=row[16] or "",
            similarity=similarity,
        )

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def search_entities_by_vector(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[LegalSearchResult]:
        self._load_entity_index()
        if self._entity_index is None or self._entity_ids is None:
            return []

        labels, distances = self._entity_index.knn_query(query_vector.reshape(1, -1), k=min(top_k, len(self._entity_ids)))
        results: list[LegalSearchResult] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            eid = self._entity_ids[int(label)]
            row = self._con.execute(
                "SELECT entity_id, name_en, name_uk, entity_type FROM lex_entities WHERE entity_id = ?",
                [eid],
            ).fetchone()
            if row:
                results.append(
                    LegalSearchResult(
                        entity_id=row[0],
                        name_en=row[1],
                        name_uk=row[2] or "",
                        entity_type=row[3],
                        similarity=similarity,
                    )
                )
        return results

    def search_facts_by_vector(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 20,
        min_similarity: float = 0.3,
    ) -> list[LegalFactResult]:
        self._load_fact_index()
        if self._fact_index is None or self._fact_ids is None:
            return []

        labels, distances = self._fact_index.knn_query(query_vector.reshape(1, -1), k=min(top_k, len(self._fact_ids)))
        results: list[LegalFactResult] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            fid = self._fact_ids[int(label)]
            row = self._con.execute(
                f"SELECT {_FACT_SELECT} FROM lex_facts WHERE fact_id = ?",
                [fid],
            ).fetchone()
            if row:
                results.append(self._to_fact_result(row, similarity=similarity))
        return results

    def search_provisions_by_vector(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 10,
        min_similarity: float = 0.3,
    ) -> list[LegalProvisionResult]:
        self._load_provision_index()
        if self._provision_index is None or self._provision_ids is None:
            return []

        labels, distances = self._provision_index.knn_query(query_vector.reshape(1, -1), k=min(top_k, len(self._provision_ids)))
        results: list[LegalProvisionResult] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            pid = self._provision_ids[int(label)]
            row = self._con.execute(
                "SELECT provision_id, doc_name, doc_reestr_code, citation_label, kind, provision_text "
                "FROM lex_provisions WHERE provision_id = ?",
                [pid],
            ).fetchone()
            if row:
                results.append(
                    LegalProvisionResult(
                        provision_id=row[0],
                        doc_name=row[1] or "",
                        doc_reestr_code=row[2] or "",
                        citation_label=row[3],
                        kind=row[4],
                        provision_text_preview=row[5][:300] if row[5] else "",
                        similarity=similarity,
                    )
                )
        return results

    # ------------------------------------------------------------------
    # Text and structured retrieval
    # ------------------------------------------------------------------

    def text_search_facts(
        self,
        query: str,
        *,
        top_k: int = 20,
    ) -> list[LegalFactResult]:
        pattern = f"%{query}%"
        rows = self._con.execute(
            f"SELECT {_FACT_SELECT} FROM lex_facts "
            "WHERE fact_text ILIKE ? "
            "OR subject_en ILIKE ? "
            "OR object_en ILIKE ? "
            "OR condition_text_uk ILIKE ? "
            "OR exception_text_uk ILIKE ? "
            "OR source_quote_uk ILIKE ? "
            "LIMIT ?",
            [pattern, pattern, pattern, pattern, pattern, pattern, top_k],
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def search_facts_by_action(
        self,
        action_canon: str,
        *,
        top_k: int = 50,
    ) -> list[LegalFactResult]:
        rows = self._con.execute(
            f"SELECT {_FACT_SELECT} FROM lex_facts "
            "WHERE action_canon = ? "
            "ORDER BY confidence DESC LIMIT ?",
            [action_canon, top_k],
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def search_facts_with_threshold(
        self,
        metric: str,
        *,
        top_k: int = 50,
    ) -> list[LegalFactResult]:
        rows = self._con.execute(
            f"SELECT f.{_FACT_SELECT} "
            "FROM lex_facts f "
            "JOIN lex_rule_thresholds t ON t.fact_id = f.fact_id "
            "WHERE t.metric = ? "
            "ORDER BY f.confidence DESC LIMIT ?",
            [metric, top_k],
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def get_facts_for_entity(self, entity_id: str) -> list[LegalFactResult]:
        rows = self._con.execute(
            f"SELECT {_FACT_SELECT} FROM lex_facts WHERE subject_id = ? OR object_id = ?",
            [entity_id, entity_id],
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def find_related_entities(
        self,
        entity_id: str,
        *,
        max_hops: int = 2,
        max_results: int = 50,
    ) -> list[tuple[LegalSearchResult, str, int]]:
        visited: set[str] = {entity_id}
        results: list[tuple[LegalSearchResult, str, int]] = []
        frontier = [entity_id]

        for hop in range(1, max_hops + 1):
            next_frontier: list[str] = []
            for eid in frontier:
                rows = self._con.execute(
                    "SELECT DISTINCT "
                    "CASE WHEN subject_id = ? THEN object_id ELSE subject_id END AS neighbor_id, predicate "
                    "FROM lex_facts WHERE subject_id = ? OR object_id = ?",
                    [eid, eid, eid],
                ).fetchall()

                for neighbor_id, predicate in rows:
                    if neighbor_id in visited:
                        continue
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)

                    entity_row = self._con.execute(
                        "SELECT entity_id, name_en, name_uk, entity_type FROM lex_entities WHERE entity_id = ?",
                        [neighbor_id],
                    ).fetchone()
                    if entity_row:
                        results.append(
                            (
                                LegalSearchResult(
                                    entity_id=entity_row[0],
                                    name_en=entity_row[1],
                                    name_uk=entity_row[2] or "",
                                    entity_type=entity_row[3],
                                    similarity=1.0 / hop,
                                ),
                                predicate,
                                hop,
                            )
                        )
                    if len(results) >= max_results:
                        return results

            frontier = next_frontier

        return results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._con.close()
