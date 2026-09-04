"""Read-only access to the academic knowledge DuckDB + HNSW vector index."""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

import duckdb
import numpy as np

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.academic.knowledge.types import (
    CLAIM_VOCABULARY_COLUMN_CONTRACT,
    CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN,
    CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
    CLAIM_VOCABULARY_STORE_COLUMNS,
    BoundaryConditionResult,
    CausalClaimResult,
    CausalClaimResultV1,
    CausalClaimResultV2,
    ClaimLineageAuditPage,
    ClaimLineageAuditRecord,
    ClaimLineageCursorError,
    ClaimTableSchemaError,
    ClaimVocabularyLimitation,
    ClaimVocabularyProjectionBinding,
    ClaimVocabularySourceRowBinding,
    ParameterEstimateResult,
    WorkSearchResult,
)
from polisyos.ir.analytics import (
    ClaimVocabularyAxisStatus,
    DesignFamily,
    EvidenceStrength,
    SourceBasis,
    VersionedClaimVocabularyEnvelope,
    adapt_legacy_claim_occurrence_as_v2_absence,
)

logger = get_logger(__name__)

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping

_LEGACY_LOOKALIKE_COLUMNS = {
    "design_family_hint",
    "evidence_strength",
    "source_basis",
    "claim_extraction_confidence",
}
_V2_REQUIRED_COLUMNS = set(CLAIM_VOCABULARY_STORE_COLUMNS) | {
    CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN
}
_V2_COLUMN_CONTRACT = CLAIM_VOCABULARY_COLUMN_CONTRACT
_CLAIM_BASE_COLUMNS = {
    "id",
    "work_id",
    "cause",
    "effect",
    "direction",
    "mechanism",
    "trust_score",
}


def _canonical_json_value(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _canonical_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    return value


def _json_hash(value: object) -> str:
    encoded = json.dumps(
        _canonical_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _parse_publish_blockers(value: object) -> tuple[str, ...]:
    """Decode the historical JSON, comma, and semicolon blocker encodings."""

    if value is None:
        return ()
    if isinstance(value, (list, tuple)):
        values = value
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return ()
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            decoded = None
        values = decoded if isinstance(decoded, list) else text.replace(";", ",").split(",")
    else:
        values = (value,)
    return tuple(str(item).strip() for item in values if str(item).strip())


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
        self._claim_schema_cache: dict[str, str] = {}

        self._work_index = None
        self._work_ids: list[str] | None = None

    @classmethod
    def _from_connection(
        cls,
        connection: duckdb.DuckDBPyConnection,
    ) -> ScholarKnowledgeStore:
        """Construct the projection owner around an existing connection."""

        store = cls.__new__(cls)
        store._con = connection
        store._db_path = Path("")
        store._index_dir = Path("")
        store._claim_schema_cache = {}
        store._work_index = None
        store._work_ids = None
        return store

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
            query_vector.reshape(1, -1),
            k=k,
        )
        results: list[WorkSearchResult] = []
        for label, dist in zip(labels[0], distances[0], strict=False):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            wid = self._work_ids[int(label)]
            row = self._con.execute(
                f"SELECT {_WORK_SELECT} FROM ac_works WHERE id = ?",
                [wid],
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
        self,
        query: str,
        *,
        top_k: int = 20,
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
        rows = self._select_claim_rows(
            "ac_causal_claims",
            "c.cause ILIKE ? AND c.effect ILIKE ? AND c.trust_score >= ?",
            [cause_pattern, effect_pattern, min_trust],
            order_by="c.trust_score DESC, c.id ASC",
        )
        return [self._project_claim_row(row, source_table="ac_causal_claims") for row in rows]

    def search_causal_claims(
        self,
        query: str,
        *,
        top_k: int = 20,
        min_trust: float = 0.0,
    ) -> list[CausalClaimResult]:
        pattern = f"%{query}%"
        rows = self._select_claim_rows(
            "ac_causal_claims",
            "(c.cause ILIKE ? OR c.effect ILIKE ? OR c.mechanism ILIKE ?) "
            "AND c.trust_score >= ?",
            [pattern, pattern, pattern, min_trust],
            order_by="c.trust_score DESC, c.id ASC",
            limit=top_k,
        )
        return [self._project_claim_row(row, source_table="ac_causal_claims") for row in rows]

    def get_causal_claims_v1_audit(
        self, cause: str, effect: str, *, min_trust: float = 0.0
    ) -> list[CausalClaimResultV1]:
        """Return the deprecated lossy compatibility view for audit tooling."""
        return [
            self._as_v1_audit(result)
            for result in self.get_causal_claims(cause, effect, min_trust=min_trust)
        ]

    def search_causal_claims_v1_audit(
        self, query: str, *, top_k: int = 20, min_trust: float = 0.0
    ) -> list[CausalClaimResultV1]:
        """Return the deprecated lossy compatibility search view."""
        return [
            self._as_v1_audit(result)
            for result in self.search_causal_claims(query, top_k=top_k, min_trust=min_trust)
        ]

    def _schema_descriptor(self, table: str) -> tuple[tuple[object, ...], ...]:
        """Return schema facts that affect projection and pagination identity."""
        catalog, schema = self._active_relation_location()
        rows = self._con.execute(
            "SELECT column_name, data_type, is_nullable, column_default "
            "FROM information_schema.columns "
            "WHERE table_catalog = ? AND table_schema = ? AND table_name = ? "
            "ORDER BY ordinal_position",
            [catalog, schema, table],
        ).fetchall()
        return tuple(tuple(row) for row in rows)

    def _active_relation_location(self) -> tuple[str, str]:
        """Return the catalog/schema resolved by unqualified Store reads."""
        row = self._con.execute("SELECT current_database(), current_schema()").fetchone()
        if row is None:
            raise ClaimTableSchemaError("cannot resolve active claim relation location")
        return str(row[0]), str(row[1])

    def _claim_table_schema(self, table: str) -> str:
        if table not in {"ac_causal_claims_raw", "ac_causal_claims"}:
            raise ClaimTableSchemaError(f"unsupported claim source table: {table}")
        cached = getattr(self, "_claim_schema_cache", {}).get(table)
        if cached is not None:
            return cached
        descriptor = self._schema_descriptor(table)
        columns = {str(row[0]) for row in descriptor}
        if not columns:
            raise ClaimTableSchemaError(f"claim table is missing: {table}")
        missing_base = _CLAIM_BASE_COLUMNS - columns
        if missing_base:
            raise ClaimTableSchemaError(
                f"claim table {table} is missing base columns {sorted(missing_base)}"
            )
        has_discriminator = CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN in columns
        sidecar_columns = _V2_REQUIRED_COLUMNS - {CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN}
        if has_discriminator:
            if not columns >= _V2_REQUIRED_COLUMNS:
                missing = sorted(_V2_REQUIRED_COLUMNS - columns)
                raise ClaimTableSchemaError(f"partial v2 claim schema {table}; missing {missing}")
            if "strength" in columns:
                raise ClaimTableSchemaError(f"generic strength is forbidden in explicit v2 table {table}")
            actual_contract = {
                str(name): (str(data_type), str(nullable), default)
                for name, data_type, nullable, default in descriptor
                if str(name) in _V2_COLUMN_CONTRACT
            }
            if actual_contract != _V2_COLUMN_CONTRACT:
                raise ClaimTableSchemaError(f"v2 claim schema contract mismatch in {table}")
            if self._identity_constraint_descriptor(table) is None:
                raise ClaimTableSchemaError(f"canonical claim identity constraint is missing in {table}")
            schema = "explicit_v2"
            self._claim_schema_cache[table] = schema
            return schema
        unexpected = columns & sidecar_columns - _LEGACY_LOOKALIKE_COLUMNS
        if unexpected:
            raise ClaimTableSchemaError(f"partial v2 claim schema {table}; found {sorted(unexpected)}")
        if "strength" not in columns:
            raise ClaimTableSchemaError(f"legacy claim table {table} is missing base columns ['strength']")
        schema = "legacy_v1"
        self._claim_schema_cache[table] = schema
        return schema

    def _select_claim_rows(
        self,
        table: str,
        predicate: str,
        params: list[object],
        *,
        order_by: str,
        limit: int | None = None,
    ) -> list[dict[str, object]]:
        schema = self._claim_table_schema(table)
        del schema
        suffix = f" LIMIT {int(limit)}" if limit is not None else ""
        rows = self._con.execute(
            f"SELECT c.*, w.title AS __work_title, w.year AS __work_year FROM {table} c "
            f"LEFT JOIN ac_works w ON c.work_id = w.id WHERE {predicate} ORDER BY {order_by}{suffix}",
            params,
        )
        columns = [str(item[0]) for item in rows.description]
        return [dict(zip(columns, row, strict=True)) for row in rows.fetchall()]

    def _project_claim_row(self, row: Mapping[str, object], *, source_table: str) -> CausalClaimResultV2:
        schema = self._claim_table_schema(source_table)
        source_schema = "explicit_v2" if schema == "explicit_v2" else "legacy_v1"
        try:
            if schema == "legacy_v1":
                envelope = adapt_legacy_claim_occurrence_as_v2_absence(
                    {
                        "cause": str(row.get("cause") or ""),
                        "effect": str(row.get("effect") or ""),
                        "direction": str(row.get("direction") or ""),
                        "strength": str(row.get("strength") or ""),
                        "mechanism": str(row.get("mechanism") or ""),
                    }
                )
            else:
                envelope = VersionedClaimVocabularyEnvelope.model_validate(
                    {
                        "schema_version": row.get(CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN),
                        **{
                            name: row.get(name)
                            for name in (
                                "cause",
                                "effect",
                                "direction",
                                "mechanism",
                                *CLAIM_VOCABULARY_STORE_COLUMNS,
                            )
                        },
                    }
                )
        except Exception as exc:
            raise ClaimTableSchemaError(f"invalid {schema} row in {source_table}") from exc
        identity = str(row.get("id") or "").strip()
        selected = {key: value for key, value in row.items() if not key.startswith("__")}
        source_binding = ClaimVocabularySourceRowBinding(
            source_table=source_table,
            source_schema_version=source_schema,
            source_identity=identity,
            source_row_sha256=_json_hash(selected),
        )
        vocabulary_payload = {
            "design_family_hint": envelope.design_family_hint.value if envelope.design_family_hint else None,
            "design_family_hint_status": envelope.design_family_hint_status.value,
            "evidence_strength": envelope.evidence_strength.value if envelope.evidence_strength else None,
            "evidence_strength_status": envelope.evidence_strength_status.value,
            "claim_extraction_confidence": envelope.claim_extraction_confidence,
            "claim_extraction_confidence_status": envelope.claim_extraction_confidence_status.value,
            "source_basis": envelope.source_basis.value if envelope.source_basis else None,
            "source_basis_status": envelope.source_basis_status.value,
            "legacy_strength_label": envelope.legacy_strength_label,
            "record_extraction_mode": envelope.record_extraction_mode,
        }
        binding = ClaimVocabularyProjectionBinding(
            projection_rule_version=CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
            subject_kind="claim_row",
            source_rows=(source_binding,),
            projected_vocabulary_sha256=_json_hash(vocabulary_payload),
        )
        return CausalClaimResultV2(
            schema_version="2.0",
            id=identity,
            work_id=str(row.get("work_id") or ""),
            cause=envelope.cause,
            effect=envelope.effect,
            direction=envelope.direction,
            mechanism=envelope.mechanism,
            domain=str(row.get("domain") or ""),
            trust_score=float(row.get("trust_score") or 0.0),
            work_title=str(row.get("__work_title") or ""),
            work_year=int(row["__work_year"]) if row.get("__work_year") is not None else None,
            design_family_hint=envelope.design_family_hint,
            design_family_hint_status=envelope.design_family_hint_status,
            evidence_strength=envelope.evidence_strength,
            evidence_strength_status=envelope.evidence_strength_status,
            claim_extraction_confidence=envelope.claim_extraction_confidence,
            claim_extraction_confidence_status=envelope.claim_extraction_confidence_status,
            source_basis=envelope.source_basis,
            source_basis_status=envelope.source_basis_status,
            legacy_strength_label=envelope.legacy_strength_label,
            record_extraction_mode=envelope.record_extraction_mode,
            limitations=(ClaimVocabularyLimitation.AMBIGUOUS_LEGACY_VOCABULARY,)
            if envelope.legacy_strength_label is not None
            else (),
            projection_binding=binding,
            strong_design_evidence=bool(row.get("strong_design_evidence") or False),
            design_quality_tier=int(row["design_quality_tier"]) if row.get("design_quality_tier") is not None else None,
            publish_blockers=_parse_publish_blockers(row.get("publish_blockers")),
            candidate_layer=str(row.get("candidate_layer") or "candidate"),
        )

    def project_edge_summary(
        self,
        *,
        source_table: str,
        source_identity: str,
        source_row: Mapping[str, object] | None = None,
        cause: str,
        effect: str,
        direction: str,
        evidence_strength: str | None,
        mechanism: str,
        domain: str,
        trust_score: float,
        work_title: str,
        work_id: str = "",
        source_bindings: tuple[ClaimVocabularySourceRowBinding, ...] | None = None,
    ) -> CausalClaimResultV2:
        """Project an exact/family/contested edge summary without cross-axis inference."""
        _, resolved_binding = self._edge_source_row(source_table, source_identity)
        if (
            source_row is not None
            and _json_hash(dict(source_row)) != resolved_binding.source_row_sha256
        ):
            raise ClaimTableSchemaError(
                f"source row binding mismatch: {source_table}/{source_identity}"
            )
        resolved_bindings: list[ClaimVocabularySourceRowBinding] = []
        physical_rows: list[dict[str, object]] = []
        for supplied_binding in source_bindings or (resolved_binding,):
            physical_row, expected = self._edge_source_row(
                supplied_binding.source_table,
                supplied_binding.source_identity,
            )
            if supplied_binding != expected:
                raise ClaimTableSchemaError(
                    "source row binding mismatch: "
                    f"{supplied_binding.source_table}/{supplied_binding.source_identity}"
                )
            resolved_bindings.append(expected)
            physical_rows.append(physical_row)
        if resolved_binding not in resolved_bindings:
            raise ClaimTableSchemaError(
                f"source row binding mismatch: {source_table}/{source_identity}"
            )

        semantic_rows = [
            self._edge_row_semantics(binding.source_table, row)
            for binding, row in zip(resolved_bindings, physical_rows, strict=True)
        ]
        expected_identity = (cause, effect, direction)
        if any(semantics[:3] != expected_identity for semantics in semantic_rows):
            raise ClaimTableSchemaError(
                f"source row semantics mismatch: {source_table}/{source_identity}"
            )

        physical_evidence = [semantics[3] for semantics in semantic_rows]
        evidence = self._strongest_physical_evidence(physical_evidence)
        try:
            supplied_evidence = (
                EvidenceStrength(str(evidence_strength)) if evidence_strength else None
            )
        except ValueError as exc:
            raise ClaimTableSchemaError(
                f"invalid evidence_strength in {source_table}/{source_identity}"
            ) from exc
        if supplied_evidence != evidence:
            raise ClaimTableSchemaError(
                f"source row semantics mismatch: {source_table}/{source_identity}"
            )

        envelope = VersionedClaimVocabularyEnvelope(
            cause=cause,
            effect=effect,
            direction=direction,
            mechanism=mechanism,
            evidence_strength=evidence,
            evidence_strength_status=(
                ClaimVocabularyAxisStatus.CANDIDATE
                if evidence is not None
                else ClaimVocabularyAxisStatus.NOT_ESTABLISHED
            ),
        )
        vocabulary_payload = {
            "evidence_strength": evidence.value if evidence else None,
            "evidence_strength_status": envelope.evidence_strength_status.value,
            "cause": cause,
            "effect": effect,
            "direction": direction,
        }
        binding = ClaimVocabularyProjectionBinding(
            projection_rule_version=CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
            subject_kind="edge_summary",
            source_rows=tuple(resolved_bindings),
            projected_vocabulary_sha256=_json_hash(vocabulary_payload),
        )
        return CausalClaimResultV2(
            id=source_identity,
            work_id=work_id,
            cause=cause,
            effect=effect,
            direction=direction,
            mechanism=mechanism,
            domain=domain,
            trust_score=trust_score,
            work_title=work_title,
            evidence_strength=evidence,
            evidence_strength_status=envelope.evidence_strength_status,
            projection_binding=binding,
        )

    def source_row_binding_for_edge(
        self, source_table: str, source_identity: str
    ) -> ClaimVocabularySourceRowBinding:
        """Bind the exact physical edge row used by a summary query."""
        return self._edge_source_row(source_table, source_identity)[1]

    def _edge_source_row(
        self, source_table: str, source_identity: str
    ) -> tuple[dict[str, object], ClaimVocabularySourceRowBinding]:
        """Read and bind one exact physical edge row."""
        id_column = {
            "ac_skg_edges": "edge_id",
            "ac_skg_family_edges": "family_edge_id",
            "ac_skg_contested_edges": "contested_edge_id",
        }.get(source_table)
        if id_column is None:
            raise ClaimTableSchemaError(f"unsupported edge source table: {source_table}")
        result = self._con.execute(
            f"SELECT * FROM {source_table} WHERE {id_column} = ?", [source_identity]
        )
        columns = [str(item[0]) for item in result.description]
        row = result.fetchone()
        if row is None:
            raise ClaimTableSchemaError(f"missing edge source row: {source_table}/{source_identity}")
        mapped = dict(zip(columns, row, strict=True))
        binding = ClaimVocabularySourceRowBinding(
            source_table=source_table,
            source_schema_version="explicit_edge_summary",
            source_identity=source_identity,
            source_row_sha256=_json_hash(mapped),
        )
        return mapped, binding

    @staticmethod
    def _edge_row_semantics(
        source_table: str, row: Mapping[str, object]
    ) -> tuple[str, str, str, EvidenceStrength | None]:
        """Derive only the vocabulary-bearing semantics from a bound edge row."""
        columns = {
            "ac_skg_edges": ("src", "dst", "direction"),
            "ac_skg_family_edges": ("src_family", "dst_family", "direction"),
            "ac_skg_contested_edges": (
                "src_family",
                "dst_family",
                "dominant_direction",
            ),
        }.get(source_table)
        if columns is None:
            raise ClaimTableSchemaError(f"unsupported edge source table: {source_table}")
        missing = [name for name in (*columns, "evidence_strength") if name not in row]
        if missing:
            raise ClaimTableSchemaError(
                f"edge source table {source_table} is missing semantic columns {missing}"
            )
        raw_evidence = row.get("evidence_strength")
        clean_evidence = str(raw_evidence).strip() if raw_evidence is not None else ""
        try:
            evidence = EvidenceStrength(clean_evidence) if clean_evidence else None
        except ValueError as exc:
            raise ClaimTableSchemaError(
                f"invalid evidence_strength in {source_table}"
            ) from exc
        direction = str(row.get(columns[2]) or "")
        if source_table == "ac_skg_contested_edges" and not direction:
            direction = "mixed"
        return (
            str(row.get(columns[0]) or ""),
            str(row.get(columns[1]) or ""),
            direction,
            evidence,
        )

    @staticmethod
    def _strongest_physical_evidence(
        values: list[EvidenceStrength | None],
    ) -> EvidenceStrength | None:
        """Replay the existing edge-summary ordering over explicit typed values."""
        present = [value for value in values if value is not None]
        if not present:
            return None
        from polisyos.data_forge.domains.academic.knowledge.skg_store import (
            EVIDENCE_WEIGHTS,
        )

        best = present[0]
        best_score = EVIDENCE_WEIGHTS.get(
            best.value, EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value]
        )
        for value in present[1:]:
            score = EVIDENCE_WEIGHTS.get(
                value.value, EVIDENCE_WEIGHTS[EvidenceStrength.UNKNOWN.value]
            )
            if score > best_score:
                best = value
                best_score = score
        return best

    @staticmethod
    def _as_v1_audit(result: CausalClaimResultV2) -> CausalClaimResultV1:
        return CausalClaimResultV1(
            id=result.id,
            work_id=result.work_id,
            cause=result.cause,
            effect=result.effect,
            direction=result.direction,
            mechanism=result.mechanism,
            domain=result.domain,
            trust_score=result.trust_score,
            work_title=result.work_title,
            work_year=result.work_year,
            v2_projection_binding=result.projection_binding,
        )

    def _identity_constraint_descriptor(self, table: str) -> tuple[object, ...] | None:
        """Return the exact canonical identity constraint descriptor for ``table``."""

        catalog_name, schema_name = self._active_relation_location()
        rows = self._con.execute(
            "SELECT tc.constraint_catalog, tc.constraint_schema, tc.constraint_name, "
            "tc.constraint_type, kcu.column_name, kcu.ordinal_position "
            "FROM information_schema.table_constraints tc "
            "JOIN information_schema.key_column_usage kcu "
            "ON tc.constraint_catalog = kcu.constraint_catalog "
            "AND tc.constraint_schema = kcu.constraint_schema "
            "AND tc.constraint_name = kcu.constraint_name "
            "AND tc.table_catalog = kcu.table_catalog "
            "AND tc.table_schema = kcu.table_schema "
            "AND tc.table_name = kcu.table_name "
            "WHERE tc.table_catalog = ? AND tc.table_schema = ? AND tc.table_name = ? "
            "AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE') "
            "ORDER BY tc.constraint_catalog, tc.constraint_schema, tc.constraint_name, "
            "kcu.ordinal_position",
            [catalog_name, schema_name, table],
        ).fetchall()
        keys: dict[tuple[str, str, str, str], list[tuple[int, str]]] = {}
        for catalog, schema, name, kind, column, ordinal in rows:
            key = (str(catalog), str(schema), str(name), str(kind))
            keys.setdefault(key, []).append((int(ordinal), str(column)))
        candidates: list[tuple[object, ...]] = []
        for (catalog, schema, name, kind), columns in keys.items():
            ordered_columns = tuple(column for _, column in sorted(columns))
            if ordered_columns in (("id",), ("id", "work_id")):
                candidates.append((catalog, schema, name, kind, ordered_columns))
        if candidates:
            return min(candidates)
        return None

    def _audit_status_predicate(self, schema: str, status: str) -> str:
        if schema == "legacy_v1":
            return "1=0" if status == "candidate" else "1=1"
        statuses = [
            "design_family_hint_status",
            "evidence_strength_status",
            "claim_extraction_confidence_status",
            "source_basis_status",
        ]
        if status == "not_established":
            return " AND ".join(f"c.{name} = 'not_established'" for name in statuses)
        if status == "candidate":
            return " OR ".join(f"c.{name} = 'candidate'" for name in statuses)
        return "1=1"

    @staticmethod
    def _explicit_v2_invalid_predicate(alias: str) -> str:
        """Return a SQL predicate for rows the strict v2 envelope rejects."""

        allowed_values = {
            "design_family_hint": tuple(item.value for item in DesignFamily),
            "evidence_strength": tuple(item.value for item in EvidenceStrength),
            "source_basis": tuple(item.value for item in SourceBasis),
        }
        invalid: list[str] = [
            f"{alias}.{CLAIM_VOCABULARY_DISCRIMINATOR_COLUMN} IS DISTINCT FROM '2.0'"
        ]
        axes = (
            "design_family_hint",
            "evidence_strength",
            "claim_extraction_confidence",
            "source_basis",
        )
        for value_column in axes:
            status_column = f"{value_column}_status"
            invalid.append(
                "NOT (("
                f"{alias}.{value_column} IS NULL AND "
                f"{alias}.{status_column} = 'not_established') OR ("
                f"{alias}.{value_column} IS NOT NULL AND "
                f"{alias}.{status_column} = 'candidate'))"
            )
        for column, values in allowed_values.items():
            options = ", ".join(f"'{value}'" for value in values)
            invalid.append(
                f"({alias}.{column} IS NOT NULL AND {alias}.{column} NOT IN ({options}))"
            )
        invalid.append(
            f"({alias}.claim_extraction_confidence IS NOT NULL AND NOT "
            f"({alias}.claim_extraction_confidence BETWEEN 0.0 AND 1.0))"
        )
        return " OR ".join(f"({predicate})" for predicate in invalid)

    def audit_claim_lineage(
        self,
        *,
        status: str = "all",
        cursor: str | None = None,
        limit: int = 100,
    ) -> ClaimLineageAuditPage:
        """Page raw claim identities through a bounded keyset audit read."""
        if status not in {"not_established", "candidate", "all"}:
            raise ClaimLineageCursorError(f"unsupported audit status: {status}")
        if not 1 <= int(limit) <= 500:
            raise ClaimLineageCursorError("audit limit must be between 1 and 500")
        table = "ac_causal_claims_raw"
        schema = self._claim_table_schema(table)
        identity_constraint = self._identity_constraint_descriptor(table)
        identity_witness = (
            "declared_constraint"
            if identity_constraint is not None
            else "reconciled_unique_identity"
        )
        descriptor = [
            *self._schema_descriptor(table),
            ("identity_constraint", identity_constraint),
            schema,
        ]
        schema_hash = _json_hash(descriptor)
        last_id = ""
        last_work_id = ""
        total: int | None = None
        if cursor is not None:
            try:
                raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
                payload = json.loads(raw)
                checksum = payload.pop("checksum")
                if _json_hash(payload) != checksum:
                    raise ValueError("cursor checksum mismatch")
                if (
                    payload.get("status") != status
                    or payload.get("projection_rule_version") != CLAIM_VOCABULARY_PROJECTION_RULE_VERSION
                    or payload.get("schema_hash") != schema_hash
                    or payload.get("identity_witness") != identity_witness
                ):
                    raise ValueError("cursor basis mismatch")
                last_id, last_work_id = str(payload["last_id"]), str(payload["last_work_id"])
                total = int(payload["total_identities"])
            except Exception as exc:
                raise ClaimLineageCursorError("invalid or incompatible audit cursor") from exc
        status_predicate = self._audit_status_predicate(schema, status)
        if total is None:
            invalid_count_sql = "0"
            if schema == "explicit_v2":
                invalid_count_sql = (
                    f"(SELECT count(*) FROM {table} invalid_row WHERE "
                    f"{self._explicit_v2_invalid_predicate('invalid_row')})"
                )
            relation_count_row = self._con.execute(
                f"SELECT count(*), count(DISTINCT (c.id, c.work_id)), "
                f"count(*) FILTER (WHERE c.id IS NULL OR c.work_id IS NULL) "
                f", {invalid_count_sql} "
                f"FROM {table} c"
            ).fetchone()
            if relation_count_row is None:
                raise ClaimLineageCursorError("claim identity reconciliation returned no result")
            relation_total, distinct_identities, null_identities, invalid_rows = (
                int(value) for value in relation_count_row
            )
            if invalid_rows:
                raise ClaimTableSchemaError(
                    f"invalid explicit_v2 row in {table}; count={invalid_rows}"
                )
            if relation_total != distinct_identities or null_identities:
                raise ClaimLineageCursorError(
                    "raw claim identity uniqueness constraint is absent or inconsistent; "
                    "reconciliation found duplicate or null identities"
                )
            filtered_count_row = self._con.execute(
                f"SELECT count(*) FROM {table} c WHERE ({status_predicate})"
            ).fetchone()
            if filtered_count_row is None:
                raise ClaimLineageCursorError("claim lineage filtered count returned no result")
            total = int(filtered_count_row[0])
        keyset = ""
        params: list[object] = []
        if cursor is not None:
            keyset = " AND (c.id, c.work_id) > (?, ?)"
            params.extend([last_id, last_work_id])
        rows = self._con.execute(
            f"SELECT c.* FROM {table} c WHERE ({status_predicate}){keyset} ORDER BY c.id, c.work_id LIMIT ?",
            [*params, int(limit) + 1],
        )
        columns = [str(item[0]) for item in rows.description]
        mapped = [dict(zip(columns, row, strict=True)) for row in rows.fetchall()]
        has_more = len(mapped) > int(limit)
        mapped = mapped[: int(limit)]
        records: list[ClaimLineageAuditRecord] = []
        for row in mapped:
            projected = self._project_claim_row(row, source_table=table)
            records.append(
                ClaimLineageAuditRecord(
                    id=projected.id,
                    work_id=projected.work_id,
                    cause=projected.cause,
                    effect=projected.effect,
                    direction=projected.direction,
                    mechanism=projected.mechanism,
                    legacy_strength_label=projected.legacy_strength_label,
                    vocabulary=VersionedClaimVocabularyEnvelope(
                        cause=projected.cause,
                        effect=projected.effect,
                        direction=projected.direction,
                        mechanism=projected.mechanism,
                        design_family_hint=projected.design_family_hint,
                        design_family_hint_status=projected.design_family_hint_status,
                        evidence_strength=projected.evidence_strength,
                        evidence_strength_status=projected.evidence_strength_status,
                        claim_extraction_confidence=projected.claim_extraction_confidence,
                        claim_extraction_confidence_status=projected.claim_extraction_confidence_status,
                        source_basis=projected.source_basis,
                        source_basis_status=projected.source_basis_status,
                        legacy_strength_label=projected.legacy_strength_label,
                        record_extraction_mode=projected.record_extraction_mode,
                    ),
                    projection_binding=projected.projection_binding,
                    limitations=projected.limitations,
                )
            )
        next_cursor = None
        if has_more and records:
            payload = {
                "last_id": records[-1].id,
                "last_work_id": records[-1].work_id,
                "status": status,
                "projection_rule_version": CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
                "schema_hash": schema_hash,
                "total_identities": total,
                "identity_witness": identity_witness,
            }
            next_cursor = base64.urlsafe_b64encode(
                json.dumps({**payload, "checksum": _json_hash(payload)}, sort_keys=True).encode("utf-8")
            ).decode("ascii")
        return ClaimLineageAuditPage(
            items=tuple(records),
            total_identities=total,
            next_cursor=next_cursor,
            status_filter=status,
            projection_rule_version=CLAIM_VOCABULARY_PROJECTION_RULE_VERSION,
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
                "topic_ids query failed for %s: %s",
                work_id,
                exc,
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
                "boundary_conditions query failed for %s: %s",
                work_id,
                exc,
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


def load_causal_claim_results_v2(db_path: Path) -> Iterator[CausalClaimResultV2]:
    """Stream all curated claim projections from a read-only database path."""
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        yield from iter_causal_claim_results_v2(connection)
    finally:
        connection.close()


def iter_causal_claim_results_v2(
    connection: duckdb.DuckDBPyConnection,
) -> Iterator[CausalClaimResultV2]:
    """Stream curated v2 claim projections from an existing read-only connection."""
    store = ScholarKnowledgeStore._from_connection(connection)
    schema = store._claim_table_schema("ac_causal_claims")
    if schema not in {"legacy_v1", "explicit_v2"}:
        raise ClaimTableSchemaError(f"unsupported curated claim schema: {schema}")
    result = connection.execute(
        "SELECT c.*, w.title AS __work_title, w.year AS __work_year "
        "FROM ac_causal_claims c LEFT JOIN ac_works w ON c.work_id = w.id "
        "ORDER BY c.id"
    )
    columns = [str(item[0]) for item in result.description]
    while True:
        batch = result.fetchmany(256)
        if not batch:
            break
        for row in batch:
            yield store._project_claim_row(dict(zip(columns, row, strict=True)), source_table="ac_causal_claims")


def audit_academic_claim_lineage(
    db_path: Path,
    *,
    status: str = "all",
    cursor: str | None = None,
    limit: int = 100,
) -> ClaimLineageAuditPage:
    """Read one raw claim lineage page using a read-only store."""
    store = ScholarKnowledgeStore(db_path, Path(db_path).parent)
    try:
        return store.audit_claim_lineage(status=status, cursor=cursor, limit=limit)
    finally:
        store.close()
