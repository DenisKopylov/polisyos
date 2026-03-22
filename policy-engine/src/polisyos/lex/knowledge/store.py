"""Read-only access to the DuckDB knowledge graph + HNSW vector indexes.

This is the persistence layer used by ``search.py``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from polisyos.common.logger import get_logger
from polisyos.lex.knowledge.types import (
    LegalDocVersionResult,
    LegalFactResult,
    LegalProvisionResult,
    LegalReferenceEdgeResult,
    LegalSearchResult,
    LegalSourceAnchor,
    LegalSourceBundle,
)

logger = get_logger(__name__)

_FACT_SELECT_FIELDS: tuple[tuple[str, str], ...] = (
    ("fact_id", "''"),
    ("subject_en", "''"),
    ("predicate", "''"),
    ("object_en", "''"),
    ("fact_text", "''"),
    ("confidence", "0.0"),
    ("norm_type", "''"),
    ("action_canon", "''"),
    ("norm_type_canon", "''"),
    ("condition_text_uk", "''"),
    ("exception_text_uk", "''"),
    ("procedure_text_uk", "''"),
    ("thresholds_json", "'[]'"),
    ("source_quote_uk", "''"),
    ("trust_tier", "'search_candidate'"),
    ("grounding_status", "'missing_quote'"),
    ("canonical_status", "'raw'"),
    ("reference_resolution_status", "'not_applicable'"),
    ("structure_quality", "''"),
    ("constraint_type_canon", "''"),
    ("legal_unit_subtype", "''"),
    ("route_class", "''"),
    ("empty_spo_retry_eligible", "FALSE"),
    ("audit_miss_prone", "FALSE"),
    ("reference_bearing", "FALSE"),
    ("threshold_bearing", "FALSE"),
    ("fused_confidence", "NULL"),
    ("confidence_breakdown_json", "''"),
    ("consistency_score", "NULL"),
    ("hallucination_flags_json", "''"),
    ("quality_band", "''"),
    ("doc_id", "''"),
    ("doc_family_id", "''"),
    ("version_id", "''"),
    ("jurisdiction", "'UA'"),
    ("top_domain", "''"),
    ("effective_from", "''"),
    ("effective_to", "''"),
    ("doc_name", "''"),
    ("doc_reestr_code", "''"),
    ("provision_anchor", "''"),
    ("provision_citation", "''"),
)

_PROVISION_SELECT_FIELDS: tuple[tuple[str, str], ...] = (
    ("provision_id", "''"),
    ("doc_id", "''"),
    ("version_id", "''"),
    ("doc_name", "''"),
    ("doc_reestr_code", "''"),
    ("anchor_path", "''"),
    ("citation_label", "''"),
    ("kind", "''"),
    ("provision_text", "''"),
    ("struct_kind", "''"),
    ("section_role", "''"),
    ("legal_unit_subtype", "''"),
    ("route_class", "''"),
    ("empty_spo_retry_eligible", "FALSE"),
    ("audit_miss_prone", "FALSE"),
    ("reference_bearing", "FALSE"),
    ("threshold_bearing", "FALSE"),
    ("fallback_allowed_for_reasoning", "FALSE"),
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
        self._table_exists_cache: dict[str, bool] = {}
        self._table_columns_cache: dict[str, set[str]] = {}

    def _table_exists(self, table_name: str) -> bool:
        cached = self._table_exists_cache.get(table_name)
        if cached is not None:
            return cached
        exists = bool(
            self._con.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
                [table_name],
            ).fetchone()[0]
        )
        self._table_exists_cache[table_name] = exists
        return exists

    def _fact_table(
        self,
        *,
        trust_tier: str | None,
        include_candidates: bool,
        quality_band: str | None = None,
    ) -> str:
        if quality_band == "high_confidence_norm" and self._table_exists("lex_high_confidence_norms"):
            return "lex_high_confidence_norms"
        if trust_tier == "normative_fact" and self._table_exists("lex_normative_facts"):
            return "lex_normative_facts"
        if trust_tier == "grounded_fact" and self._table_exists("lex_fact_grounded"):
            return "lex_fact_grounded"
        if trust_tier == "search_candidate" and self._table_exists("lex_fact_candidates"):
            return "lex_fact_candidates"
        if not include_candidates and self._table_exists("lex_fact_grounded"):
            return "lex_fact_grounded"
        return "lex_facts"

    def _fact_filters(
        self,
        *,
        alias: str = "",
        trust_tier: str | None = None,
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
        include_candidates: bool = False,
        selected_table: str = "lex_facts",
    ) -> tuple[list[str], list[Any]]:
        prefix = f"{alias}." if alias else ""
        clauses: list[str] = []
        params: list[Any] = []
        available_columns = self._table_columns(selected_table)

        if trust_tier:
            clauses.append(f"{prefix}trust_tier = ?")
            params.append(trust_tier)
        elif (not include_candidates) and selected_table == "lex_facts":
            clauses.append(f"{prefix}trust_tier IN ('grounded_fact', 'normative_fact')")

        if jurisdiction:
            clauses.append(f"UPPER(COALESCE({prefix}jurisdiction, '')) = ?")
            params.append(jurisdiction.strip().upper())
        if domain:
            clauses.append(f"LOWER(COALESCE({prefix}top_domain, '')) = ?")
            params.append(domain.strip().lower())
        if legal_unit_subtype and "legal_unit_subtype" in available_columns:
            clauses.append(f"LOWER(COALESCE({prefix}legal_unit_subtype, '')) = ?")
            params.append(legal_unit_subtype.strip().lower())
        if route_class and "route_class" in available_columns:
            clauses.append(f"LOWER(COALESCE({prefix}route_class, '')) = ?")
            params.append(route_class.strip().lower())
        if quality_band and "quality_band" in available_columns:
            clauses.append(f"LOWER(COALESCE({prefix}quality_band, '')) = ?")
            params.append(quality_band.strip().lower())
        if min_fused_confidence is not None and "fused_confidence" in available_columns:
            clauses.append(f"COALESCE({prefix}fused_confidence, {prefix}confidence, 0.0) >= ?")
            params.append(float(min_fused_confidence))
        if as_of:
            clauses.append(
                f"(COALESCE({prefix}effective_from, '') = '' OR {prefix}effective_from <= ?)"
            )
            params.append(as_of)
            clauses.append(
                f"(COALESCE({prefix}effective_to, '') = '' OR {prefix}effective_to >= ?)"
            )
            params.append(as_of)
        return clauses, params

    def _to_where_sql(self, clauses: list[str]) -> str:
        if not clauses:
            return ""
        return " WHERE " + " AND ".join(clauses)

    def _table_columns(self, table_name: str) -> set[str]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        rows = self._con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            """,
            [table_name],
        ).fetchall()
        columns = {str(row[0]) for row in rows}
        self._table_columns_cache[table_name] = columns
        return columns

    def _select_sql(
        self,
        *,
        table_name: str,
        fields: tuple[tuple[str, str], ...],
        alias: str = "",
    ) -> str:
        prefix = f"{alias}." if alias else ""
        available_columns = self._table_columns(table_name)
        selected: list[str] = []
        for column_name, default_sql in fields:
            if column_name in available_columns:
                selected.append(f"{prefix}{column_name}")
            else:
                selected.append(f"{default_sql} AS {column_name}")
        return ", ".join(selected)

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
            trust_tier=row[14] or "search_candidate",
            grounding_status=row[15] or "missing_quote",
            canonical_status=row[16] or "raw",
            reference_resolution_status=row[17] or "not_applicable",
            structure_quality=row[18] or "",
            constraint_type_canon=row[19] or "",
            legal_unit_subtype=row[20] or "",
            route_class=row[21] or "",
            empty_spo_retry_eligible=bool(row[22]),
            audit_miss_prone=bool(row[23]),
            reference_bearing=bool(row[24]),
            threshold_bearing=bool(row[25]),
            fused_confidence=float(row[26]) if row[26] is not None else None,
            confidence_breakdown_json=row[27] or "",
            consistency_score=float(row[28]) if row[28] is not None else None,
            hallucination_flags_json=row[29] or "",
            quality_band=row[30] or "",
            doc_id=row[31] or "",
            doc_family_id=row[32] or "",
            version_id=row[33] or "",
            jurisdiction=row[34] or "UA",
            top_domain=row[35] or "",
            effective_from=row[36] or "",
            effective_to=row[37] or "",
            doc_name=row[38] or "",
            doc_reestr_code=row[39] or "",
            provision_anchor=row[40] or "",
            provision_citation=row[41] or "",
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
        trust_tier: str | None = None,
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        self._load_fact_index()
        if self._fact_index is None or self._fact_ids is None:
            return []

        table_name = self._fact_table(
            trust_tier=trust_tier,
            include_candidates=include_candidates,
            quality_band=quality_band,
        )
        labels, distances = self._fact_index.knn_query(query_vector.reshape(1, -1), k=min(top_k, len(self._fact_ids)))
        results: list[LegalFactResult] = []
        for label, dist in zip(labels[0], distances[0]):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            fid = self._fact_ids[int(label)]
            clauses, params = self._fact_filters(
                trust_tier=trust_tier,
                jurisdiction=jurisdiction,
                domain=domain,
                as_of=as_of,
                legal_unit_subtype=legal_unit_subtype,
                route_class=route_class,
                min_fused_confidence=min_fused_confidence,
                quality_band=quality_band,
                include_candidates=include_candidates,
                selected_table=table_name,
            )
            clauses.insert(0, "fact_id = ?")
            params.insert(0, fid)
            fact_select = self._select_sql(table_name=table_name, fields=_FACT_SELECT_FIELDS)
            row = self._con.execute(
                f"SELECT {fact_select} FROM {table_name}{self._to_where_sql(clauses)}",
                params,
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
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
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
            clauses = ["provision_id = ?"]
            params: list[Any] = [pid]
            available_columns = self._table_columns("lex_provisions")
            if legal_unit_subtype and "legal_unit_subtype" in available_columns:
                clauses.append("LOWER(COALESCE(legal_unit_subtype, '')) = ?")
                params.append(legal_unit_subtype.strip().lower())
            if route_class and "route_class" in available_columns:
                clauses.append("LOWER(COALESCE(route_class, '')) = ?")
                params.append(route_class.strip().lower())
            provision_select = self._select_sql(
                table_name="lex_provisions",
                fields=_PROVISION_SELECT_FIELDS,
            )
            row = self._con.execute(
                f"SELECT {provision_select} FROM lex_provisions{self._to_where_sql(clauses)}",
                params,
            ).fetchone()
            if row:
                results.append(
                    LegalProvisionResult(
                        provision_id=row[0],
                        doc_id=row[1] or "",
                        version_id=row[2] or "",
                        doc_name=row[3] or "",
                        doc_reestr_code=row[4] or "",
                        anchor_path=row[5] or "",
                        citation_label=row[6],
                        kind=row[7],
                        provision_text_preview=row[8][:300] if row[8] else "",
                        struct_kind=row[9] or "",
                        section_role=row[10] or "",
                        legal_unit_subtype=row[11] or "",
                        route_class=row[12] or "",
                        empty_spo_retry_eligible=bool(row[13]),
                        audit_miss_prone=bool(row[14]),
                        reference_bearing=bool(row[15]),
                        threshold_bearing=bool(row[16]),
                        fallback_allowed_for_reasoning=bool(row[17]),
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
        trust_tier: str | None = None,
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        table_name = self._fact_table(
            trust_tier=trust_tier,
            include_candidates=include_candidates,
            quality_band=quality_band,
        )
        pattern = f"%{query}%"
        clauses, params = self._fact_filters(
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
            include_candidates=include_candidates,
            selected_table=table_name,
        )
        text_clause = (
            "(fact_text ILIKE ? OR subject_en ILIKE ? OR object_en ILIKE ? "
            "OR condition_text_uk ILIKE ? OR exception_text_uk ILIKE ? OR source_quote_uk ILIKE ?)"
        )
        clauses.insert(0, text_clause)
        params = [pattern, pattern, pattern, pattern, pattern, pattern, *params, top_k]
        fact_select = self._select_sql(table_name=table_name, fields=_FACT_SELECT_FIELDS)
        rows = self._con.execute(
            f"SELECT {fact_select} FROM {table_name}{self._to_where_sql(clauses)} LIMIT ?",
            params,
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def search_facts_by_action(
        self,
        action_canon: str,
        *,
        top_k: int = 50,
        trust_tier: str | None = "normative_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        table_name = self._fact_table(
            trust_tier=trust_tier,
            include_candidates=include_candidates,
            quality_band=quality_band,
        )
        clauses, params = self._fact_filters(
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
            include_candidates=include_candidates,
            selected_table=table_name,
        )
        clauses.insert(0, "action_canon = ?")
        params = [action_canon, *params, top_k]
        fact_select = self._select_sql(table_name=table_name, fields=_FACT_SELECT_FIELDS)
        rows = self._con.execute(
            f"SELECT {fact_select} FROM {table_name}{self._to_where_sql(clauses)} "
            "ORDER BY confidence DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def search_facts_with_threshold(
        self,
        metric: str,
        *,
        top_k: int = 50,
        trust_tier: str | None = "normative_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        table_name = self._fact_table(
            trust_tier=trust_tier,
            include_candidates=include_candidates,
            quality_band=quality_band,
        )
        clauses, params = self._fact_filters(
            alias="f",
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
            include_candidates=include_candidates,
            selected_table=table_name,
        )
        clauses.insert(0, "t.metric = ?")
        params = [metric, *params, top_k]
        fact_select = self._select_sql(table_name=table_name, fields=_FACT_SELECT_FIELDS, alias="f")
        rows = self._con.execute(
            f"SELECT {fact_select} "
            f"FROM {table_name} f "
            "JOIN lex_rule_thresholds t ON t.fact_id = f.fact_id "
            f"{self._to_where_sql(clauses)} "
            "ORDER BY f.confidence DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def find_constraints(
        self,
        *,
        query: str | None = None,
        top_k: int = 50,
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        table_name = self._fact_table(
            trust_tier="normative_fact",
            include_candidates=False,
            quality_band=quality_band,
        )
        clauses, params = self._fact_filters(
            trust_tier="normative_fact",
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
            include_candidates=False,
            selected_table=table_name,
        )
        clauses.insert(
            0,
            "("
            "norm_type_canon IN ('obligation', 'prohibition', 'permission') "
            "OR COALESCE(thresholds_json, '[]') <> '[]' "
            "OR COALESCE(procedure_text_uk, '') <> '' "
            "OR COALESCE(exception_text_uk, '') <> ''"
            ")",
        )
        if query:
            pattern = f"%{query}%"
            clauses.insert(0, "(fact_text ILIKE ? OR source_quote_uk ILIKE ? OR condition_text_uk ILIKE ?)")
            params = [pattern, pattern, pattern, *params, top_k]
        else:
            params = [*params, top_k]
        fact_select = self._select_sql(table_name=table_name, fields=_FACT_SELECT_FIELDS)
        rows = self._con.execute(
            f"SELECT {fact_select} FROM {table_name}{self._to_where_sql(clauses)} "
            "ORDER BY confidence DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def get_applicable_norms(
        self,
        *,
        domain: str | None = None,
        jurisdiction: str | None = None,
        as_of: str | None = None,
        top_k: int = 100,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        return self.find_constraints(
            query=None,
            top_k=top_k,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
        )

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    def get_facts_for_entity(
        self,
        entity_id: str,
        *,
        trust_tier: str | None = "grounded_fact",
        jurisdiction: str | None = None,
        domain: str | None = None,
        as_of: str | None = None,
        include_candidates: bool = False,
        legal_unit_subtype: str | None = None,
        route_class: str | None = None,
        min_fused_confidence: float | None = None,
        quality_band: str | None = None,
    ) -> list[LegalFactResult]:
        table_name = self._fact_table(
            trust_tier=trust_tier,
            include_candidates=include_candidates,
            quality_band=quality_band,
        )
        clauses, params = self._fact_filters(
            trust_tier=trust_tier,
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=as_of,
            legal_unit_subtype=legal_unit_subtype,
            route_class=route_class,
            min_fused_confidence=min_fused_confidence,
            quality_band=quality_band,
            include_candidates=include_candidates,
            selected_table=table_name,
        )
        clauses.insert(0, "(subject_id = ? OR object_id = ?)")
        params = [entity_id, entity_id, *params]
        fact_select = self._select_sql(table_name=table_name, fields=_FACT_SELECT_FIELDS)
        rows = self._con.execute(
            f"SELECT {fact_select} FROM {table_name}{self._to_where_sql(clauses)}",
            params,
        ).fetchall()
        return [self._to_fact_result(r, similarity=1.0) for r in rows]

    def find_related_entities(
        self,
        entity_id: str,
        *,
        max_hops: int = 2,
        max_results: int = 50,
        trust_tier: str | None = "grounded_fact",
        include_candidates: bool = False,
    ) -> list[tuple[LegalSearchResult, str, int]]:
        table_name = self._fact_table(
            trust_tier=trust_tier,
            include_candidates=include_candidates,
        )
        visited: set[str] = {entity_id}
        results: list[tuple[LegalSearchResult, str, int]] = []
        frontier = [entity_id]

        for hop in range(1, max_hops + 1):
            next_frontier: list[str] = []
            for eid in frontier:
                rows = self._con.execute(
                    "SELECT DISTINCT "
                    "CASE WHEN subject_id = ? THEN object_id ELSE subject_id END AS neighbor_id, predicate "
                    f"FROM {table_name} WHERE subject_id = ? OR object_id = ?",
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

    def load_provisions_by_anchor(
        self,
        doc_id: str,
        anchors: list[str],
    ) -> list[LegalSourceAnchor]:
        if not doc_id.strip() or not anchors:
            return []
        placeholders = ", ".join(["?"] * len(anchors))
        rows = self._con.execute(
            f"""
            SELECT
                COALESCE(doc_id, ''),
                COALESCE(version_id, ''),
                COALESCE(anchor_path, ''),
                COALESCE(citation_label, ''),
                COALESCE(provision_text, ''),
                COALESCE(struct_kind, ''),
                COALESCE(section_role, ''),
                COALESCE(legal_unit_subtype, ''),
                COALESCE(route_class, ''),
                COALESCE(appendix_id, ''),
                COALESCE(table_id, '')
            FROM lex_provisions
            WHERE doc_id = ? AND anchor_path IN ({placeholders})
            """,
            [doc_id, *anchors],
        ).fetchall()
        results: list[LegalSourceAnchor] = []
        for row in rows:
            context_prefix = self.load_appendix_context(doc_id, row[2])
            results.append(
                LegalSourceAnchor(
                    doc_id=row[0],
                    version_id=row[1],
                    anchor=row[2],
                    citation_label=row[3],
                    provision_text=row[4],
                    struct_kind=row[5],
                    section_role=row[6],
                    legal_unit_subtype=row[7],
                    route_class=row[8],
                    appendix_id=row[9],
                    table_id=row[10],
                    context_prefix=context_prefix,
                )
            )
        return results

    def load_doc_version_chain(
        self,
        *,
        doc_id: str | None = None,
        doc_family_id: str | None = None,
    ) -> list[LegalDocVersionResult]:
        if not self._table_exists("lex_doc_versions"):
            return []
        resolved_family_id = (doc_family_id or "").strip()
        if not resolved_family_id and doc_id:
            row = self._con.execute(
                "SELECT COALESCE(doc_family_id, '') FROM lex_doc_versions WHERE doc_id = ? LIMIT 1",
                [doc_id],
            ).fetchone()
            resolved_family_id = str(row[0] or "") if row else ""
        if not resolved_family_id:
            return []
        rows = self._con.execute(
            """
            SELECT
                COALESCE(doc_id, ''),
                COALESCE(doc_family_id, ''),
                COALESCE(version_id, ''),
                COALESCE(doc_reestr_code, ''),
                COALESCE(doc_name, ''),
                COALESCE(doc_type, ''),
                COALESCE(doc_status, ''),
                COALESCE(doc_date_acc, ''),
                COALESCE(version_rank, 0),
                COALESCE(previous_version_id, ''),
                COALESCE(next_version_id, ''),
                COALESCE(is_latest, FALSE)
            FROM lex_doc_versions
            WHERE doc_family_id = ?
            ORDER BY version_rank
            """,
            [resolved_family_id],
        ).fetchall()
        return [
            LegalDocVersionResult(
                doc_id=row[0],
                doc_family_id=row[1],
                version_id=row[2],
                doc_reestr_code=row[3],
                doc_name=row[4],
                doc_type=row[5],
                doc_status=row[6],
                doc_date_acc=row[7],
                version_rank=int(row[8] or 0),
                previous_version_id=row[9],
                next_version_id=row[10],
                is_latest=bool(row[11]),
            )
            for row in rows
        ]

    def load_appendix_context(
        self,
        doc_id: str,
        anchor: str,
        *,
        max_depth: int = 4,
    ) -> list[str]:
        if not doc_id.strip() or not anchor.strip():
            return []
        context: list[str] = []
        current_anchor = anchor
        seen: set[str] = set()
        for _ in range(max_depth):
            row = self._con.execute(
                """
                SELECT
                    COALESCE(parent_anchor, ''),
                    COALESCE(citation_label, ''),
                    COALESCE(provision_text, '')
                FROM lex_provisions
                WHERE doc_id = ? AND anchor_path = ?
                LIMIT 1
                """,
                [doc_id, current_anchor],
            ).fetchone()
            if not row:
                break
            parent_anchor = str(row[0] or "")
            if not parent_anchor or parent_anchor in seen:
                break
            seen.add(parent_anchor)
            parent_row = self._con.execute(
                """
                SELECT
                    COALESCE(citation_label, ''),
                    COALESCE(provision_text, '')
                FROM lex_provisions
                WHERE doc_id = ? AND anchor_path = ?
                LIMIT 1
                """,
                [doc_id, parent_anchor],
            ).fetchone()
            if parent_row:
                citation = str(parent_row[0] or "").strip()
                text = str(parent_row[1] or "").strip()
                preview = text[:240] if text else ""
                label = " ".join(part for part in (citation, preview) if part).strip()
                if label:
                    context.append(label)
            current_anchor = parent_anchor
        return context

    def expand_reference_neighborhood(
        self,
        *,
        doc_id: str,
        anchors: list[str],
        max_hops: int = 2,
    ) -> list[LegalReferenceEdgeResult]:
        if not self._table_exists("lex_reference_edges"):
            return []
        frontier: list[tuple[str, str]] = [(doc_id, anchor) for anchor in anchors if anchor]
        seen_pairs = set(frontier)
        seen_edges: set[tuple[str, str, str, str, str]] = set()
        results: list[LegalReferenceEdgeResult] = []
        for _ in range(max(max_hops, 0)):
            next_frontier: list[tuple[str, str]] = []
            for current_doc_id, current_anchor in frontier:
                rows = self._con.execute(
                    """
                    SELECT
                        COALESCE(source_doc_id, ''),
                        COALESCE(source_anchor, ''),
                        COALESCE(target_doc_id, ''),
                        COALESCE(target_anchor, ''),
                        COALESCE(relation_type, ''),
                        COALESCE(resolution_status, ''),
                        COALESCE(resolution_confidence, 0.0),
                        COALESCE(ref_text_uk, '')
                    FROM lex_reference_edges
                    WHERE (source_doc_id = ? AND source_anchor = ?)
                       OR (target_doc_id = ? AND target_anchor = ?)
                    """,
                    [current_doc_id, current_anchor, current_doc_id, current_anchor],
                ).fetchall()
                for row in rows:
                    edge_key = (row[0], row[1], row[2], row[3], row[4])
                    if edge_key in seen_edges:
                        continue
                    seen_edges.add(edge_key)
                    results.append(
                        LegalReferenceEdgeResult(
                            source_doc_id=row[0],
                            source_anchor=row[1],
                            target_doc_id=row[2],
                            target_anchor=row[3],
                            relation_type=row[4],
                            resolution_status=row[5],
                            resolution_confidence=float(row[6] or 0.0),
                            ref_text_uk=row[7],
                        )
                    )
                    for candidate_pair in (
                        (row[0], row[1]),
                        (row[2], row[3]),
                    ):
                        if candidate_pair[0] and candidate_pair[1] and candidate_pair not in seen_pairs:
                            seen_pairs.add(candidate_pair)
                            next_frontier.append(candidate_pair)
            frontier = next_frontier
            if not frontier:
                break
        return results

    def load_source_bundle(
        self,
        *,
        doc_id: str,
        anchors: list[str],
        version_id: str | None = None,
        max_reference_hops: int = 2,
        candidate_fact_ids: list[str] | None = None,
        candidate_provision_ids: list[str] | None = None,
    ) -> LegalSourceBundle | None:
        if not doc_id.strip() or not anchors:
            return None
        primary_anchors = self.load_provisions_by_anchor(doc_id, anchors)
        if not primary_anchors:
            return None
        first = primary_anchors[0]
        doc_row = self._con.execute(
            """
            SELECT
                COALESCE(doc_name, ''),
                COALESCE(doc_reestr_code, ''),
                COALESCE(doc_type, '')
            FROM lex_provisions
            WHERE doc_id = ? AND anchor_path = ?
            LIMIT 1
            """,
            [doc_id, first.anchor],
        ).fetchone()
        reference_neighborhood = self.expand_reference_neighborhood(
            doc_id=doc_id,
            anchors=[item.anchor for item in primary_anchors],
            max_hops=max_reference_hops,
        )
        version_chain = self.load_doc_version_chain(doc_id=doc_id)
        resolved_version_id = version_id or first.version_id
        source_family = ""
        for item in primary_anchors:
            if item.legal_unit_subtype:
                source_family = item.legal_unit_subtype
                break
        bundle_id = hashlib.sha256(
            "|".join([doc_id, resolved_version_id, *sorted(item.anchor for item in primary_anchors)]).encode(
                "utf-8"
            )
        ).hexdigest()[:20]
        appendix_context: list[str] = []
        for anchor in primary_anchors:
            for context_item in anchor.context_prefix:
                if context_item and context_item not in appendix_context:
                    appendix_context.append(context_item)
        return LegalSourceBundle(
            bundle_id=bundle_id,
            doc_id=doc_id,
            version_id=resolved_version_id,
            doc_name=str(doc_row[0] or "") if doc_row else "",
            doc_reestr_code=str(doc_row[1] or "") if doc_row else "",
            source_family=source_family,
            primary_anchors=primary_anchors,
            appendix_context=appendix_context,
            reference_neighborhood=reference_neighborhood,
            version_chain=version_chain,
            candidate_fact_ids=list(candidate_fact_ids or []),
            candidate_provision_ids=list(candidate_provision_ids or []),
            notes=[f"doc_type={doc_row[2]}" for _ in [0] if doc_row and doc_row[2]],
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        self._con.close()
