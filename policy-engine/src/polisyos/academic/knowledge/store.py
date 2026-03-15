"""Read-only access to the academic knowledge DuckDB + HNSW vector index."""

from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np

from polisyos.academic.knowledge.types import (
    BoundaryConditionResult,
    CausalClaimResult,
    ParameterEstimateResult,
    WorkSearchResult,
)
from polisyos.common.logger import get_logger

logger = get_logger(__name__)


_WORK_SELECT = (
    "id, title, doi, abstract, year, publication_date, language, work_type, is_retracted, "
    "cited_by_count, fwci, citation_percentile, citation_top_1, citation_top_10, journal, source_id, "
    "is_oa, has_fulltext, full_text_url, trust_score, study_design"
)


class ScholarKnowledgeStore:
    """Read-only handle to the academic knowledge graph (DuckDB + HNSW)."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = db_path
        self._index_dir = index_dir
        self._con = duckdb.connect(str(db_path), read_only=True)

        self._work_index = None
        self._work_ids: list[str] | None = None

    # ------------------------------------------------------------------
    # Vector index loading (lazy)
    # ------------------------------------------------------------------

    def _load_work_index(self) -> None:
        if self._work_index is not None:
            return
        import hnswlib

        npz_path = self._index_dir / "ac_work_embeddings.npz"
        hnsw_path = self._index_dir / "ac_work_index.hnsw"
        if not npz_path.exists() or not hnsw_path.exists():
            logger.warning("Work index files not found in %s", self._index_dir)
            return

        data = np.load(str(npz_path), allow_pickle=True)
        self._work_ids = list(data["ids"])
        dim = int(data["vectors"].shape[1])

        idx = hnswlib.Index(space="cosine", dim=dim)
        idx.load_index(str(hnsw_path), max_elements=len(self._work_ids))
        idx.set_ef(100)
        self._work_index = idx

    def _to_work_result(
        self,
        row: tuple,
        *,
        similarity: float = 0.0,
        run_id: str = "",
        pass_name: str = "",
        topic_ids: list[str] | None = None,
    ) -> WorkSearchResult:
        abstract = row[3] or ""
        return WorkSearchResult(
            id=row[0],
            title=row[1] or "",
            doi=row[2] or "",
            abstract_snippet=abstract[:500],
            year=row[4],
            publication_date=row[5] or "",
            language=row[6] or "",
            work_type=row[7] or "",
            is_retracted=bool(row[8]),
            cited_by_count=row[9] or 0,
            fwci=float(row[10]) if row[10] is not None else None,
            citation_percentile=float(row[11]) if row[11] is not None else None,
            citation_is_top_1_percent=bool(row[12]),
            citation_is_top_10_percent=bool(row[13]),
            journal=row[14] or "",
            source_id=row[15] or "",
            is_oa=bool(row[16]),
            has_fulltext=bool(row[17]),
            full_text_url=row[18] or "",
            trust_score=float(row[19]) if row[19] is not None else 0.0,
            study_design=row[20] or "",
            similarity=similarity,
            run_id=run_id,
            pass_name=pass_name,
            topic_ids=topic_ids or [],
        )

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    def search_works_by_vector(
        self,
        query_vector: np.ndarray,
        *,
        top_k: int = 20,
        min_similarity: float = 0.3,
    ) -> list[WorkSearchResult]:
        self._load_work_index()
        if self._work_index is None or self._work_ids is None:
            return []

        k = min(top_k, len(self._work_ids))
        labels, distances = self._work_index.knn_query(
            query_vector.reshape(1, -1), k=k,
        )
        results: list[WorkSearchResult] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            wid = self._work_ids[int(label)]
            row = self._con.execute(
                f"SELECT {_WORK_SELECT} FROM ac_works WHERE id = ?", [wid],
            ).fetchone()
            if row:
                topic_ids = self._topic_ids_for_work(wid)
                result = self._to_work_result(row, similarity=similarity, topic_ids=topic_ids)
                # Attach pre-extracted estimates
                estimates = self.get_estimates_for_work(wid)
                if estimates:
                    result = WorkSearchResult(
                        **{**result.model_dump(), "pre_extracted_estimates": estimates},
                    )
                results.append(result)
        return results

    # ------------------------------------------------------------------
    # Text search
    # ------------------------------------------------------------------

    def text_search_works(
        self, query: str, *, top_k: int = 20,
    ) -> list[WorkSearchResult]:
        pattern = f"%{query}%"
        rows = self._con.execute(
            f"SELECT {_WORK_SELECT} FROM ac_works "
            "WHERE title ILIKE ? OR abstract ILIKE ? "
            "ORDER BY trust_score DESC LIMIT ?",
            [pattern, pattern, top_k],
        ).fetchall()
        results: list[WorkSearchResult] = []
        for r in rows:
            topic_ids = self._topic_ids_for_work(str(r[0]))
            results.append(self._to_work_result(r, similarity=1.0, topic_ids=topic_ids))
        return results

    # ------------------------------------------------------------------
    # Parameter estimates
    # ------------------------------------------------------------------

    def get_estimates_for_work(self, work_id: str) -> list[ParameterEstimateResult]:
        rows = self._con.execute(
            "SELECT e.id, e.work_id, e.variable_name, e.estimate, e.ci_low, e.ci_high, "
            "e.std_error, e.unit, e.domain, e.study_design, e.sample_size, "
            "e.country, e.period_start, e.period_end, e.trust_score, e.raw_context, "
            "w.title, w.year "
            "FROM ac_parameter_estimates e "
            "JOIN ac_works w ON e.work_id = w.id "
            "WHERE e.work_id = ?",
            [work_id],
        ).fetchall()
        return [self._to_estimate(r) for r in rows]

    def get_parameter_estimates(
        self,
        variable_name: str,
        domain: str | None = None,
        country: str | None = None,
    ) -> list[ParameterEstimateResult]:
        filters = ["e.variable_name = ?"]
        params: list = [variable_name]
        if domain:
            filters.append("e.domain = ?")
            params.append(domain)
        if country:
            filters.append("(e.country = ? OR e.country IS NULL OR e.country = '')")
            params.append(country)
        rows = self._con.execute(
            "SELECT e.id, e.work_id, e.variable_name, e.estimate, e.ci_low, e.ci_high, "
            "e.std_error, e.unit, e.domain, e.study_design, e.sample_size, "
            "e.country, e.period_start, e.period_end, e.trust_score, e.raw_context, "
            "w.title, w.year "
            "FROM ac_parameter_estimates e "
            "JOIN ac_works w ON e.work_id = w.id "
            f"WHERE {' AND '.join(filters)} "
            "ORDER BY e.trust_score DESC",
            params,
        ).fetchall()
        return [self._to_estimate(r) for r in rows]

    def _to_estimate(self, row: tuple) -> ParameterEstimateResult:
        return ParameterEstimateResult(
            id=row[0] or "",
            work_id=row[1] or "",
            variable_name=row[2] or "",
            estimate=float(row[3]),
            ci_low=float(row[4]) if row[4] is not None else None,
            ci_high=float(row[5]) if row[5] is not None else None,
            std_error=float(row[6]) if row[6] is not None else None,
            unit=row[7] or "",
            domain=row[8] or "",
            study_design=row[9] or "",
            sample_size=int(row[10]) if row[10] is not None else None,
            country=row[11] or "",
            period_start=int(row[12]) if row[12] is not None else None,
            period_end=int(row[13]) if row[13] is not None else None,
            trust_score=float(row[14]) if row[14] is not None else 0.0,
            raw_context=row[15] or "",
            work_title=row[16] or "",
            work_year=int(row[17]) if row[17] is not None else None,
        )

    # ------------------------------------------------------------------
    # Causal claims
    # ------------------------------------------------------------------

    def get_causal_claims(
        self,
        cause: str,
        effect: str,
        *,
        min_trust: float = 0.0,
    ) -> list[CausalClaimResult]:
        cause_pattern = f"%{cause}%"
        effect_pattern = f"%{effect}%"
        rows = self._con.execute(
            "SELECT c.id, c.work_id, c.cause, c.effect, c.direction, c.strength, "
            "c.mechanism, c.domain, c.trust_score, w.title, w.year "
            "FROM ac_causal_claims c "
            "JOIN ac_works w ON c.work_id = w.id "
            "WHERE c.cause ILIKE ? AND c.effect ILIKE ? "
            "AND c.trust_score >= ? "
            "ORDER BY c.trust_score DESC",
            [cause_pattern, effect_pattern, min_trust],
        ).fetchall()
        return [self._to_claim(r) for r in rows]

    def search_causal_claims(
        self,
        query: str,
        *,
        top_k: int = 20,
        min_trust: float = 0.0,
    ) -> list[CausalClaimResult]:
        pattern = f"%{query}%"
        rows = self._con.execute(
            "SELECT c.id, c.work_id, c.cause, c.effect, c.direction, c.strength, "
            "c.mechanism, c.domain, c.trust_score, w.title, w.year "
            "FROM ac_causal_claims c "
            "JOIN ac_works w ON c.work_id = w.id "
            "WHERE (c.cause ILIKE ? OR c.effect ILIKE ? OR c.mechanism ILIKE ?) "
            "AND c.trust_score >= ? "
            "ORDER BY c.trust_score DESC LIMIT ?",
            [pattern, pattern, pattern, min_trust, top_k],
        ).fetchall()
        return [self._to_claim(r) for r in rows]

    def _to_claim(self, row: tuple) -> CausalClaimResult:
        return CausalClaimResult(
            id=row[0] or "",
            work_id=row[1] or "",
            cause=row[2] or "",
            effect=row[3] or "",
            direction=row[4] or "",
            strength=row[5] or "",
            mechanism=row[6] or "",
            domain=row[7] or "",
            trust_score=float(row[8]) if row[8] is not None else 0.0,
            work_title=row[9] or "",
            work_year=int(row[10]) if row[10] is not None else None,
        )

    # ------------------------------------------------------------------
    # Topic-aware lookups
    # ------------------------------------------------------------------

    def _topic_ids_for_work(self, work_id: str) -> list[str]:
        try:
            rows = self._con.execute(
                "SELECT DISTINCT topic_id FROM ac_topic_selections WHERE work_id = ?",
                [work_id],
            ).fetchall()
        except (OSError, RuntimeError) as exc:
            logger.debug(
                "topic_ids query failed for %s: %s", work_id, exc,
            )
            return []
        return [str(r[0]) for r in rows if r and r[0]]

    def search_works_by_topic(
        self,
        topic_id: str,
        *,
        run_id: str | None = None,
        pass_name: str | None = None,
        top_k: int = 20,
    ) -> list[WorkSearchResult]:
        filters = ["ts.topic_id = ?"]
        params: list = [topic_id]
        if run_id:
            filters.append("ts.run_id = ?")
            params.append(run_id)
        if pass_name:
            filters.append("r.pass_name = ?")
            params.append(pass_name)
        params.append(top_k)

        rows = self._con.execute(
            f"SELECT {_WORK_SELECT}, ts.run_id, r.pass_name "
            "FROM ac_topic_selections ts "
            "JOIN ac_works w ON ts.work_id = w.id "
            "LEFT JOIN ac_runs r ON ts.run_id = r.run_id "
            f"WHERE {' AND '.join(filters)} "
            "ORDER BY ts.rank ASC, w.trust_score DESC LIMIT ?",
            params,
        ).fetchall()

        out: list[WorkSearchResult] = []
        for row in rows:
            wid = str(row[0] or "")
            topic_ids = self._topic_ids_for_work(wid)
            out.append(
                self._to_work_result(
                    row[:21],
                    similarity=1.0,
                    run_id=str(row[21] or ""),
                    pass_name=str(row[22] or ""),
                    topic_ids=topic_ids,
                )
            )
        return out

    def get_boundary_conditions_for_work(self, work_id: str) -> list[BoundaryConditionResult]:
        try:
            rows = self._con.execute(
                "SELECT boundary_id, work_id, variable, operator, threshold_value, scope_text, confidence "
                "FROM ac_boundary_conditions WHERE work_id = ?",
                [work_id],
            ).fetchall()
        except (OSError, RuntimeError) as exc:
            logger.debug(
                "boundary_conditions query failed for %s: %s", work_id, exc,
            )
            return []
        return [
            BoundaryConditionResult(
                id=str(r[0] or ""),
                work_id=str(r[1] or ""),
                variable=str(r[2] or ""),
                operator=str(r[3] or ""),
                threshold_value=str(r[4] or ""),
                scope_text=str(r[5] or ""),
                confidence=float(r[6]) if r[6] is not None else 0.0,
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._con.close()
