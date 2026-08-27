"""Read-only access to the DuckDB knowledge graph + HNSW vector indexes.

This is the persistence layer used by ``search.py``.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from pathlib import Path
from typing import Any

import duckdb
import numpy as np

from polisyos.common.logger import get_logger
from polisyos.core import artifacts, contracts
from polisyos.lex.knowledge.types import (
    LegalDocVersionResult,
    LegalFactResult,
    LegalProvisionResult,
    LegalReferenceEdgeResult,
    LegalRuleThresholdRow,
    LegalSearchResult,
    LegalSourceAnchor,
    LegalSourceBundle,
    LegalTemporalCompetence,
    LegalThresholdEvaluation,
)

logger = get_logger(__name__)
ArtifactID = artifacts.ArtifactID
ArtifactRef = artifacts.ArtifactRef
epoch_contract = contracts.epoch

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
    ("temporal_state", "''"),
    ("temporal_resolution_status", "'unknown'"),
    ("temporal_source_scope", "''"),
    ("temporal_source_kind", "''"),
    ("temporal_confidence", "NULL"),
    ("temporal_provenance_json", "'{}'"),
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

    def __init__(
        self,
        db_path: Path,
        index_dir: Path,
        *,
        canonical_db_ref_path: Path | None = None,
    ) -> None:
        """Open owner data while keeping evidence refs independent of its mount path.

        Args:
            db_path: Physical read-only DuckDB path.
            index_dir: Physical vector-index directory.
            canonical_db_ref_path: Stable logical path used only in emitted DuckDB evidence
                references. When omitted, the physical path preserves the standalone-store API.
        """

        self._db_path = db_path
        self._index_dir = index_dir
        self._canonical_db_ref_path = canonical_db_ref_path or db_path
        self._con = duckdb.connect(str(db_path), read_only=True)

        self._entity_index = None
        self._entity_ids: list[str] | None = None
        self._fact_index = None
        self._fact_ids: list[str] | None = None
        self._provision_index = None
        self._provision_ids: list[str] | None = None
        self._table_exists_cache: dict[str, bool] = {}
        self._table_columns_cache: dict[str, set[str]] = {}
        self._unit_registry_cache: dict[str, tuple[str, float, str]] | None = None

    def _amendment_window_rows(self) -> list[tuple[object, ...]]:
        if not self._table_exists("lex_amendments") or not self._table_exists("lex_facts"):
            return []
        return self._con.execute(
            """
            WITH amendment_windows AS (
                SELECT
                    amendment_id,
                    amended_doc_id,
                    target_anchor,
                    effective_from,
                    created_at,
                    LEAD(effective_from) OVER (
                        PARTITION BY amended_doc_id, target_anchor
                        ORDER BY effective_from, amendment_id
                    ) AS effective_to
                FROM lex_amendments
            ), scopes AS (
                SELECT
                    doc_id,
                    LIST(DISTINCT STRUCT_PACK(
                        jurisdiction := UPPER(TRIM(COALESCE(jurisdiction, ''))),
                        domain := TRIM(COALESCE(top_domain, ''))
                    )) AS scope_rows
                FROM lex_facts
                WHERE TRIM(COALESCE(jurisdiction, '')) <> ''
                  AND TRIM(COALESCE(top_domain, '')) <> ''
                GROUP BY doc_id
            )
            SELECT
                a.amendment_id,
                a.amended_doc_id,
                a.target_anchor,
                a.effective_from,
                a.effective_to,
                a.created_at,
                s.scope_rows
            FROM amendment_windows AS a
            LEFT JOIN scopes AS s ON s.doc_id = a.amended_doc_id
            ORDER BY a.amendment_id
            """
        ).fetchall()

    @staticmethod
    def _parse_amendment_date(value: object) -> date | None:
        if value in {None, ""}:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    @staticmethod
    def _parse_amendment_datetime(value: object) -> datetime | None:
        if value in {None, ""}:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value))
        except ValueError:
            return None

    @classmethod
    def _amendment_source_mapping(cls, row: tuple[object, ...]) -> dict[str, object]:
        effective_from = cls._parse_amendment_date(row[3])
        effective_to = cls._parse_amendment_date(row[4])
        created_datetime = cls._parse_amendment_datetime(row[5])
        scope_values = tuple(
            sorted(
                {
                    (str(value.get("jurisdiction") or ""), str(value.get("domain") or ""))
                    for value in (row[6] or ())
                }
            )
        )
        return {
            "amendment_id": str(row[0]),
            "amended_doc_id": str(row[1] or ""),
            "target_anchor": str(row[2] or ""),
            "effective_from": (
                effective_from.isoformat() if effective_from is not None else str(row[3] or "")
            ),
            "effective_to": (
                effective_to.isoformat()
                if effective_to is not None
                else (None if row[4] is None else str(row[4]))
            ),
            "created_at": (
                created_datetime.isoformat()
                if created_datetime is not None
                else (None if row[5] is None else str(row[5]))
            ),
            "scope_values": [list(value) for value in scope_values],
        }

    def load_amendment_owner_snapshot(self, *, ref: ArtifactRef) -> bytes:
        """Reload the complete ordered owner rows named by a receipt."""

        owner_failure_code = (
            None
            if self._table_exists("lex_amendments") and self._table_exists("lex_facts")
            else "amendment_owner_table_not_established"
        )
        payload = epoch_contract.canonical_epoch_bytes(
            {
                "owner_failure_code": owner_failure_code,
                "rows": [
                    self._amendment_source_mapping(row) for row in self._amendment_window_rows()
                ],
            }
        )
        expected = ArtifactRef(
            artifact_id=ArtifactID.model_validate(f"sha256:{hashlib.sha256(payload).hexdigest()}"),
            kind="lex.amendment_owner_snapshot",
            media_type="application/json",
        )
        if ref != expected:
            raise ValueError("lex_amendment_owner_snapshot_ref_stale")
        return payload

    def resolve_amendment_window_denominator(
        self, *, query: epoch_contract.LegalAmendmentWindowResolutionQuery
    ) -> epoch_contract.LegalAmendmentWindowDenominatorReceipt:
        """Assess the complete amendment table before applying query filters."""

        owner_failure_code = (
            None
            if self._table_exists("lex_amendments") and self._table_exists("lex_facts")
            else "amendment_owner_table_not_established"
        )
        rows = self._amendment_window_rows()
        try:
            cutoff_text = query.visibility_knowledge_cutoff_bytes.decode().strip()
            cutoff = datetime.fromisoformat(cutoff_text.replace("Z", "+00:00"))
        except (UnicodeDecodeError, ValueError):
            cutoff = None
        try:
            admission_text = query.purpose_admission_cutoff_bytes.decode().strip()
            admission_cutoff = datetime.fromisoformat(admission_text.replace("Z", "+00:00"))
        except (UnicodeDecodeError, ValueError):
            admission_cutoff = None
        assessments: list[epoch_contract.LegalAmendmentWindowAssessment] = []
        snapshot_rows: list[dict[str, object]] = []
        for row in rows:
            amended_doc_id = str(row[1] or "")
            effective_from = self._parse_amendment_date(row[3])
            effective_to = self._parse_amendment_date(row[4])
            created_at = row[5]
            scope_values = tuple(
                sorted(
                    {
                        (str(value.get("jurisdiction") or ""), str(value.get("domain") or ""))
                        for value in (row[6] or ())
                    }
                )
            )
            failure_code: str | None = None
            resolved_scope_ref: str | None = None
            if not scope_values:
                failure_code = "amendment_scope_unresolved"
            elif len(scope_values) != 1:
                failure_code = "amendment_scope_ambiguous"
            else:
                scope_raw = epoch_contract.canonical_epoch_bytes(
                    {
                        "jurisdiction": scope_values[0][0],
                        "domain": scope_values[0][1],
                    }
                )
                resolved_scope_ref = f"sha256:{hashlib.sha256(scope_raw).hexdigest()}"
            valid_effect_window_unresolved = effective_from is None or (
                row[4] not in {None, ""} and effective_to is None
            )
            if valid_effect_window_unresolved:
                failure_code = "amendment_valid_effect_window_unresolved"
            elif cutoff is None or admission_cutoff is None or created_at in {None, ""}:
                failure_code = "amendment_knowledge_cutoff_unresolved"
            created_datetime = self._parse_amendment_datetime(created_at)
            if created_at not in {None, ""} and created_datetime is None:
                failure_code = "amendment_knowledge_cutoff_unresolved"
            cutoff_comparable = cutoff
            admission_comparable = admission_cutoff
            if (
                cutoff_comparable is not None
                and created_datetime is not None
                and created_datetime.tzinfo is None
            ):
                cutoff_comparable = cutoff_comparable.replace(tzinfo=None)
            elif (
                cutoff_comparable is not None
                and created_datetime is not None
                and cutoff_comparable.tzinfo is None
            ):
                cutoff_comparable = cutoff_comparable.replace(tzinfo=created_datetime.tzinfo)
            if (
                admission_comparable is not None
                and created_datetime is not None
                and created_datetime.tzinfo is None
            ):
                admission_comparable = admission_comparable.replace(tzinfo=None)
            elif (
                admission_comparable is not None
                and created_datetime is not None
                and admission_comparable.tzinfo is None
            ):
                admission_comparable = admission_comparable.replace(tzinfo=created_datetime.tzinfo)
            scope_matches = scope_values == ((query.jurisdiction.upper(), query.domain),)
            in_valid_window = effective_from is not None and (
                effective_from <= query.valid_effect_value
                and (effective_to is None or query.valid_effect_value < effective_to)
            )
            visible = (
                cutoff_comparable is not None
                and admission_comparable is not None
                and created_datetime is not None
                and created_datetime <= cutoff_comparable
                and created_datetime <= admission_comparable
            )
            if failure_code is not None:
                disposition = "unresolved"
            elif scope_matches and in_valid_window and visible:
                disposition = "applicable"
            else:
                disposition = "not_applicable"
            source_mapping = self._amendment_source_mapping(row)
            source_raw = epoch_contract.canonical_epoch_bytes(source_mapping)
            source_hash = f"sha256:{hashlib.sha256(source_raw).hexdigest()}"
            doc_raw = amended_doc_id.encode()
            doc_hash = f"sha256:{hashlib.sha256(doc_raw).hexdigest()}"
            assessments.append(
                epoch_contract.LegalAmendmentWindowAssessment(
                    amendment_ref=ArtifactRef(
                        artifact_id=ArtifactID.model_validate(source_hash),
                        kind="lex.amendment",
                        media_type="application/json",
                    ),
                    amendment_content_hash=source_hash,
                    amended_doc_ref=ArtifactRef(
                        artifact_id=ArtifactID.model_validate(doc_hash),
                        kind="lex.document",
                        media_type="text/plain",
                    ),
                    resolved_scope_ref=resolved_scope_ref,
                    effective_from=effective_from,
                    effective_to=effective_to,
                    disposition=disposition,
                    failure_code=failure_code,
                )
            )
            snapshot_rows.append(source_mapping)
        snapshot_raw = epoch_contract.canonical_epoch_bytes(
            {
                "owner_failure_code": owner_failure_code,
                "rows": snapshot_rows,
            }
        )
        snapshot_hash = f"sha256:{hashlib.sha256(snapshot_raw).hexdigest()}"
        failures = tuple(
            sorted(
                {
                    *(row.failure_code for row in assessments if row.failure_code),
                    *((owner_failure_code,) if owner_failure_code else ()),
                }
            )
        )
        denominator_raw = epoch_contract.canonical_epoch_bytes(
            {
                "query": query.model_dump(mode="json"),
                "snapshot_hash": snapshot_hash,
                "assessments": [row.model_dump(mode="json") for row in assessments],
            }
        )
        return epoch_contract.LegalAmendmentWindowDenominatorReceipt(
            query=query,
            owner_source_snapshot_ref=ArtifactRef(
                artifact_id=ArtifactID.model_validate(snapshot_hash),
                kind="lex.amendment_owner_snapshot",
                media_type="application/json",
            ),
            owner_source_snapshot_content_hash=snapshot_hash,
            declared_amendment_count=len(assessments),
            assessments=tuple(assessments),
            denominator_hash=f"sha256:{hashlib.sha256(denominator_raw).hexdigest()}",
            status="unresolved" if failures else "resolved",
            failure_codes=failures,
            owner_failure_code=owner_failure_code,
            predicate_class="independently_reconciled",
        )

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
        if quality_band == "high_confidence_norm" and self._table_exists(
            "lex_high_confidence_norms"
        ):
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
            if "temporal_resolution_status" in available_columns:
                clauses.append(
                    f"LOWER(COALESCE({prefix}temporal_resolution_status, 'unknown')) = 'resolved'"
                )
            clauses.append(f"COALESCE({prefix}effective_from, '') <> ''")
            clauses.append(f"{prefix}effective_from <= ?")
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

    def _threshold_fact_table(self) -> str:
        if self._table_exists("lex_normative_ready_facts"):
            return "lex_normative_ready_facts"
        if self._table_exists("lex_normative_facts"):
            return "lex_normative_facts"
        return self._fact_table(
            trust_tier="normative_fact",
            include_candidates=False,
        )

    def _to_rule_threshold_row(self, row: tuple) -> LegalRuleThresholdRow:
        provision_ref = ""
        doc_id = str(row[8] or "")
        provision_anchor = str(row[11] or "")
        if doc_id and provision_anchor:
            provision_ref = self._duckdb_ref(f"lex_provisions/{doc_id}:{provision_anchor}")
        return LegalRuleThresholdRow(
            threshold_id=str(row[0] or ""),
            fact_id=str(row[1] or ""),
            metric=str(row[2] or ""),
            operator=str(row[3] or ""),
            value_decimal=None if row[4] is None else float(row[4]),
            value_text=str(row[5] or ""),
            unit=str(row[6] or ""),
            applies_to=str(row[7] or ""),
            doc_id=doc_id,
            doc_family_id=str(row[9] or ""),
            version_id=str(row[10] or ""),
            provision_anchor=provision_anchor,
            provision_citation=str(row[12] or ""),
            provision_ref=provision_ref,
            jurisdiction=str(row[13] or "UA"),
            top_domain=str(row[14] or ""),
            norm_type=str(row[15] or ""),
            norm_type_canon=str(row[16] or ""),
            effective_from=str(row[17] or ""),
            effective_to=str(row[18] or ""),
            temporal_resolution_status=str(row[19] or ""),
            trust_tier=str(row[20] or "search_candidate"),
        )

    def _threshold_evaluation(
        self,
        threshold: LegalRuleThresholdRow,
        *,
        status: str,
        reason: str,
        normalized_candidate_value: float | None = None,
        normalized_threshold_value: float | None = None,
        canonical_unit: str = "",
        temporal_status: str = "in_force",
    ) -> LegalThresholdEvaluation:
        threshold_ref = self._duckdb_ref(f"lex_rule_thresholds/{threshold.threshold_id}")
        return LegalThresholdEvaluation(
            status=status,
            reason=reason,
            threshold_ref=threshold_ref,
            threshold_id=threshold.threshold_id,
            fact_id=threshold.fact_id,
            metric=threshold.metric,
            operator=threshold.operator,
            applies_to=threshold.applies_to,
            normalized_candidate_value=normalized_candidate_value,
            normalized_threshold_value=normalized_threshold_value,
            canonical_unit=canonical_unit,
            temporal_status=temporal_status,
            obligation_ref=self._duckdb_ref(f"lex_normative_facts/{threshold.fact_id}"),
            provision_ref=threshold.provision_ref,
        )

    def _duckdb_ref(self, fragment: str) -> str:
        """Return a stable owner evidence ref without changing the physical read path."""

        return f"duckdb://{self._canonical_db_ref_path.as_posix()}#{fragment}"

    @staticmethod
    def _threshold_ref(*, threshold_id: str | None, metric: str | None) -> str:
        if threshold_id:
            return f"lex_rule_thresholds/{threshold_id}"
        if metric:
            return f"lex_rule_thresholds?metric={metric}"
        return "lex_rule_thresholds/unresolved"

    @staticmethod
    def _scope_applies(*, declared_scope: str, candidate_scope: str) -> bool:
        declared_tokens = LegalKnowledgeStore._scope_tokens(declared_scope)
        candidate_tokens = LegalKnowledgeStore._scope_tokens(candidate_scope)
        if not declared_tokens or not candidate_tokens:
            return False
        return declared_tokens == candidate_tokens or declared_tokens.issubset(candidate_tokens)

    @staticmethod
    def _scope_tokens(value: str) -> set[str]:
        return {
            token
            for token in (
                str(value or "")
                .strip()
                .lower()
                .replace(",", " ")
                .replace(";", " ")
                .replace(":", " ")
                .split()
            )
            if token
        }

    def _unit_registry(self) -> dict[str, tuple[str, float, str]]:
        if self._unit_registry_cache is not None:
            return self._unit_registry_cache
        registry: dict[str, tuple[str, float, str]] = {
            "%": ("ratio", 1.0, "percent"),
            "percent": ("ratio", 1.0, "percent"),
            "percentage": ("ratio", 1.0, "percent"),
            "ratio": ("ratio", 100.0, "percent"),
            "fraction": ("ratio", 100.0, "percent"),
            "decimal_fraction": ("ratio", 100.0, "percent"),
            "percentage_point": ("percentage_point", 1.0, "percentage_point"),
            "percentage_points": ("percentage_point", 1.0, "percentage_point"),
            "pp": ("percentage_point", 1.0, "percentage_point"),
            "year": ("time", 365.0, "day"),
            "years": ("time", 365.0, "day"),
            "рік": ("time", 365.0, "day"),
            "років": ("time", 365.0, "day"),
            "місяць": ("time", 30.0, "day"),
            "місяц": ("time", 30.0, "day"),
            "місяці": ("time", 30.0, "day"),
            "місяців": ("time", 30.0, "day"),
            "day": ("time", 1.0, "day"),
            "days": ("time", 1.0, "day"),
            "день": ("time", 1.0, "day"),
            "дні": ("time", 1.0, "day"),
            "днів": ("time", 1.0, "day"),
            "дн": ("time", 1.0, "day"),
            "hour": ("time", 1.0 / 24.0, "day"),
            "hours": ("time", 1.0 / 24.0, "day"),
            "година": ("time", 1.0 / 24.0, "day"),
            "години": ("time", 1.0 / 24.0, "day"),
            "годин": ("time", 1.0 / 24.0, "day"),
            "грн": ("currency", 1.0, "uah"),
            "uah": ("currency", 1.0, "uah"),
            "₴": ("currency", 1.0, "uah"),
            "коп": ("currency", 0.01, "uah"),
            "копійка": ("currency", 0.01, "uah"),
            "копійок": ("currency", 0.01, "uah"),
            "кг": ("mass", 1.0, "kg"),
            "kg": ("mass", 1.0, "kg"),
            "кілограм": ("mass", 1.0, "kg"),
            "кілограми": ("mass", 1.0, "kg"),
            "тонна": ("mass", 1000.0, "kg"),
            "тонни": ("mass", 1000.0, "kg"),
            "тонн": ("mass", 1000.0, "kg"),
            "t": ("mass", 1000.0, "kg"),
            "км": ("length", 1.0, "km"),
            "km": ("length", 1.0, "km"),
            "кілометр": ("length", 1.0, "km"),
            "кілометри": ("length", 1.0, "km"),
            "га": ("area", 1.0, "ha"),
            "ha": ("area", 1.0, "ha"),
            "гектар": ("area", 1.0, "ha"),
            "гектари": ("area", 1.0, "ha"),
        }
        if self._table_exists("lex_rule_thresholds"):
            try:
                rows = self._con.execute(
                    """
                    SELECT DISTINCT LOWER(TRIM(COALESCE(unit, ''))) AS unit
                    FROM lex_rule_thresholds
                    WHERE TRIM(COALESCE(unit, '')) != ''
                    ORDER BY unit ASC
                    """
                ).fetchall()
            except duckdb.Error:
                rows = []
            for row in rows:
                token = str(row[0] or "").strip().lower()
                if token and token not in registry:
                    registry[token] = (f"unit:{token}", 1.0, token)
        self._unit_registry_cache = registry
        return registry

    def _normalize_unit_value(self, value: float, unit: str) -> tuple[float, str, str] | None:
        token = str(unit or "").strip().lower()
        if not token:
            return None
        entry = self._unit_registry().get(token)
        if entry is None:
            return None
        dimension, multiplier, canonical_unit = entry
        try:
            return (float(value) * multiplier, dimension, canonical_unit)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _operator_registry() -> dict[str, Any]:
        tolerance = 1e-9
        return {
            "lte": lambda candidate, values: candidate <= values[0] + tolerance,
            "<=": lambda candidate, values: candidate <= values[0] + tolerance,
            "lt": lambda candidate, values: candidate < values[0],
            "<": lambda candidate, values: candidate < values[0],
            "gte": lambda candidate, values: candidate + tolerance >= values[0],
            ">=": lambda candidate, values: candidate + tolerance >= values[0],
            "gt": lambda candidate, values: candidate > values[0],
            ">": lambda candidate, values: candidate > values[0],
            "eq": lambda candidate, values: abs(candidate - values[0]) <= tolerance,
            "=": lambda candidate, values: abs(candidate - values[0]) <= tolerance,
            "range": lambda candidate, values: values[0] - tolerance
            <= candidate
            <= values[1] + tolerance,
            "between": lambda candidate, values: values[0] - tolerance
            <= candidate
            <= values[1] + tolerance,
            "interval": lambda candidate, values: values[0] - tolerance
            <= candidate
            <= values[1] + tolerance,
            "in": lambda candidate, values: any(
                abs(candidate - value) <= tolerance for value in values
            ),
            "∈": lambda candidate, values: any(
                abs(candidate - value) <= tolerance for value in values
            ),
        }

    @staticmethod
    def _parse_numeric_values(*values: str) -> tuple[float, ...]:
        parsed: list[float] = []
        for value in values:
            token = str(value or "").replace(",", ".")
            number = ""
            for char in token:
                if char.isdigit() or char in ".-+":
                    number += char
                elif number:
                    try:
                        parsed.append(float(number))
                    except ValueError:
                        pass
                    number = ""
            if number:
                try:
                    parsed.append(float(number))
                except ValueError:
                    pass
        return tuple(parsed)

    def _threshold_operator_values(self, threshold: LegalRuleThresholdRow) -> tuple[float, ...]:
        operator = str(threshold.operator or "").strip().lower()
        if operator in {"range", "between", "interval", "in", "∈"}:
            values = self._parse_numeric_values(threshold.value_decimal, threshold.value_text)
            if operator in {"range", "between", "interval"} and len(values) >= 2:
                lo, hi = min(values[:2]), max(values[:2])
                return (lo, hi)
            if operator in {"in", "∈"} and values:
                return tuple(dict.fromkeys(values))
        if threshold.value_decimal is None:
            return ()
        try:
            return (float(threshold.value_decimal),)
        except (TypeError, ValueError):
            return ()

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
            temporal_state=row[38] or "",
            temporal_resolution_status=row[39] or "unknown",
            temporal_source_scope=row[40] or "",
            temporal_source_kind=row[41] or "",
            temporal_confidence=float(row[42]) if row[42] is not None else None,
            temporal_provenance_json=row[43] or "{}",
            doc_name=row[44] or "",
            doc_reestr_code=row[45] or "",
            provision_anchor=row[46] or "",
            provision_citation=row[47] or "",
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

        labels, distances = self._entity_index.knn_query(
            query_vector.reshape(1, -1), k=min(top_k, len(self._entity_ids))
        )
        results: list[LegalSearchResult] = []
        for label, dist in zip(labels[0], distances[0], strict=False):
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
        labels, distances = self._fact_index.knn_query(
            query_vector.reshape(1, -1), k=min(top_k, len(self._fact_ids))
        )
        results: list[LegalFactResult] = []
        for label, dist in zip(labels[0], distances[0], strict=False):
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

        labels, distances = self._provision_index.knn_query(
            query_vector.reshape(1, -1), k=min(top_k, len(self._provision_ids))
        )
        results: list[LegalProvisionResult] = []
        for label, dist in zip(labels[0], distances[0], strict=False):
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

    def resolve_rule_threshold(
        self,
        *,
        threshold_id: str | None = None,
        metric: str | None = None,
        applies_to: str | None = None,
        as_of: str | None = None,
        jurisdiction: str | None = None,
        domain: str | None = None,
        doc_family_id: str | None = None,
    ) -> LegalRuleThresholdRow | None:
        """Resolve a threshold row and bind it to its normative fact/provision context."""

        if not self._table_exists("lex_rule_thresholds"):
            return None
        clauses: list[str] = []
        params: list[Any] = []
        if threshold_id:
            clauses.append("t.threshold_id = ?")
            params.append(str(threshold_id).strip())
        elif metric:
            clauses.append("t.metric = ?")
            params.append(str(metric).strip())
        else:
            return None

        fact_table = self._threshold_fact_table()
        fact_clauses, fact_params = self._fact_filters(
            alias="f",
            jurisdiction=jurisdiction,
            domain=domain,
            as_of=None,
            include_candidates=False,
            selected_table=fact_table,
        )
        clauses.extend(fact_clauses)
        params.extend(fact_params)
        if doc_family_id:
            clauses.append("f.doc_family_id = ?")
            params.append(str(doc_family_id).strip())
        where_sql = self._to_where_sql(clauses)
        fact_select = self._select_sql(
            table_name=fact_table,
            alias="f",
            fields=(
                ("doc_id", "''"),
                ("doc_family_id", "''"),
                ("version_id", "''"),
                ("provision_anchor", "''"),
                ("provision_citation", "''"),
                ("jurisdiction", "'UA'"),
                ("top_domain", "''"),
                ("norm_type", "''"),
                ("norm_type_canon", "''"),
                ("effective_from", "''"),
                ("effective_to", "''"),
                ("temporal_resolution_status", "''"),
                ("trust_tier", "'search_candidate'"),
            ),
        )
        rows = self._con.execute(
            f"""
            SELECT t.threshold_id, t.fact_id, t.metric, t.operator, t.value_decimal,
                   t.value_text, t.unit, t.applies_to, {fact_select}
            FROM lex_rule_thresholds t
            LEFT JOIN {fact_table} f ON f.fact_id = t.fact_id
            {where_sql}
            ORDER BY COALESCE(f.confidence, 0.0) DESC, t.threshold_id ASC
            LIMIT 16
            """,
            params,
        ).fetchall()
        resolved_rows = [self._to_rule_threshold_row(row) for row in rows]
        if as_of:
            in_force_rows = [
                threshold
                for threshold in resolved_rows
                if self._threshold_temporal_status_from_row(
                    threshold=threshold,
                    as_of=as_of,
                ).status
                == "in_force"
            ]
            if in_force_rows:
                resolved_rows = in_force_rows
        if applies_to is not None:
            applicable_rows = [
                threshold
                for threshold in resolved_rows
                if self._scope_applies(
                    declared_scope=threshold.applies_to,
                    candidate_scope=applies_to,
                )
            ]
            if applicable_rows:
                return applicable_rows[0]
        return resolved_rows[0] if resolved_rows else None

    def evaluate_rule_threshold(
        self,
        *,
        threshold_id: str | None = None,
        metric: str | None = None,
        candidate_value: float | None,
        candidate_unit: str,
        applies_to: str,
        as_of: str | None = None,
        jurisdiction: str | None = None,
        domain: str | None = None,
        doc_family_id: str | None = None,
    ) -> LegalThresholdEvaluation:
        """Evaluate an applicable L3 threshold with real operator and unit semantics."""

        threshold = self.resolve_rule_threshold(
            threshold_id=threshold_id,
            metric=metric,
            applies_to=applies_to,
            as_of=as_of,
            jurisdiction=jurisdiction,
            domain=domain,
            doc_family_id=doc_family_id,
        )
        threshold_ref = self._threshold_ref(threshold_id=threshold_id, metric=metric)
        if threshold is None:
            return LegalThresholdEvaluation(
                status="blocked",
                reason="threshold_unresolved",
                threshold_ref=threshold_ref,
                temporal_status="blocked",
            )
        if not self._scope_applies(
            declared_scope=threshold.applies_to,
            candidate_scope=applies_to,
        ):
            return self._threshold_evaluation(
                threshold,
                status="not_applicable",
                reason="threshold_not_applicable",
            )
        temporal_status: LegalTemporalCompetence
        if as_of:
            temporal_status = self.resolve_threshold_temporal_competence(
                threshold_id=threshold.threshold_id,
                as_of=as_of,
            )
            if temporal_status.status != "in_force":
                return self._threshold_evaluation(
                    threshold,
                    status="blocked",
                    reason="temporal_not_in_force",
                    temporal_status=temporal_status.status,
                )
        if candidate_value is None:
            return self._threshold_evaluation(
                threshold,
                status="blocked",
                reason="candidate_bound_missing",
            )
        threshold_values = self._threshold_operator_values(threshold)
        if not threshold_values:
            return self._threshold_evaluation(
                threshold,
                status="blocked",
                reason="threshold_bound_missing",
            )
        candidate_normalized = self._normalize_unit_value(candidate_value, candidate_unit)
        threshold_normalized_values = [
            self._normalize_unit_value(value, threshold.unit) for value in threshold_values
        ]
        if candidate_normalized is None or any(
            value is None for value in threshold_normalized_values
        ):
            return self._threshold_evaluation(
                threshold,
                status="blocked",
                reason="unit_unresolved",
            )
        candidate_value_norm, candidate_dimension, _candidate_unit_norm = candidate_normalized
        normalized_thresholds = [
            value for value in threshold_normalized_values if value is not None
        ]
        threshold_dimensions = {value[1] for value in normalized_thresholds}
        threshold_units = {value[2] for value in normalized_thresholds}
        if threshold_dimensions != {candidate_dimension}:
            return self._threshold_evaluation(
                threshold,
                status="blocked",
                reason="unit_incompatible",
                normalized_candidate_value=candidate_value_norm,
                normalized_threshold_value=normalized_thresholds[0][0],
                canonical_unit=sorted(threshold_units)[0],
            )
        threshold_value_norms = tuple(value[0] for value in normalized_thresholds)
        threshold_unit_norm = sorted(threshold_units)[0]
        operator_fn = self._operator_registry().get(str(threshold.operator).strip().lower())
        if operator_fn is None:
            return self._threshold_evaluation(
                threshold,
                status="blocked",
                reason="operator_unresolved",
                normalized_candidate_value=candidate_value_norm,
                normalized_threshold_value=threshold_value_norms[0],
                canonical_unit=threshold_unit_norm,
            )
        admitted = operator_fn(candidate_value_norm, threshold_value_norms)
        return self._threshold_evaluation(
            threshold,
            status="admitted" if admitted else "blocked",
            reason="threshold_satisfied" if admitted else "threshold_violated",
            normalized_candidate_value=candidate_value_norm,
            normalized_threshold_value=threshold_value_norms[0],
            canonical_unit=threshold_unit_norm,
        )

    @staticmethod
    def _parse_lex_date(value: str | None) -> date | None:
        token = str(value or "").strip()
        if not token:
            return None
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d"):
            try:
                return datetime.strptime(token[:10], fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _date_to_iso(value: date | None) -> str:
        return "" if value is None else value.isoformat()

    def _threshold_lineage_rows(
        self,
        threshold: LegalRuleThresholdRow,
    ) -> list[LegalRuleThresholdRow]:
        if not threshold.doc_family_id or not threshold.metric:
            return [threshold]
        fact_table = self._threshold_fact_table()
        fact_select = self._select_sql(
            table_name=fact_table,
            alias="f",
            fields=(
                ("doc_id", "''"),
                ("doc_family_id", "''"),
                ("version_id", "''"),
                ("provision_anchor", "''"),
                ("provision_citation", "''"),
                ("jurisdiction", "'UA'"),
                ("top_domain", "''"),
                ("norm_type", "''"),
                ("norm_type_canon", "''"),
                ("effective_from", "''"),
                ("effective_to", "''"),
                ("temporal_resolution_status", "''"),
                ("trust_tier", "'search_candidate'"),
            ),
        )
        rows = self._con.execute(
            f"""
            SELECT t.threshold_id, t.fact_id, t.metric, t.operator, t.value_decimal,
                   t.value_text, t.unit, t.applies_to, {fact_select}
            FROM lex_rule_thresholds t
            LEFT JOIN {fact_table} f ON f.fact_id = t.fact_id
            WHERE f.doc_family_id = ?
              AND t.metric = ?
            ORDER BY COALESCE(f.effective_from, '') ASC,
                     COALESCE(f.doc_date_acc, '') ASC,
                     COALESCE(f.version_id, '') ASC,
                     t.threshold_id ASC
            """,
            [threshold.doc_family_id, threshold.metric],
        ).fetchall()
        lineage = [self._to_rule_threshold_row(row) for row in rows]
        return lineage or [threshold]

    def _threshold_effective_start(self, threshold: LegalRuleThresholdRow) -> date | None:
        explicit = self._parse_lex_date(threshold.effective_from)
        if explicit is not None:
            return explicit
        if threshold.version_id:
            try:
                row = self._con.execute(
                    """
                    SELECT doc_date_acc
                    FROM lex_doc_versions
                    WHERE version_id = ? OR doc_id = ?
                    ORDER BY version_rank ASC NULLS LAST
                    LIMIT 1
                    """,
                    [threshold.version_id, threshold.doc_id],
                ).fetchone()
            except duckdb.Error:
                row = None
            if row is not None:
                resolved = self._parse_lex_date(str(row[0] or ""))
                if resolved is not None:
                    return resolved
        return None

    def _threshold_next_start(
        self,
        *,
        threshold: LegalRuleThresholdRow,
        start: date | None,
    ) -> date | None:
        candidates: list[date] = []
        if threshold.doc_family_id and self._table_exists("lex_doc_versions"):
            try:
                version_rows = self._con.execute(
                    """
                    SELECT doc_date_acc
                    FROM lex_doc_versions
                    WHERE doc_family_id = ?
                      AND (version_id != ? OR doc_id != ?)
                    ORDER BY version_rank ASC NULLS LAST, doc_date_acc ASC
                    """,
                    [threshold.doc_family_id, threshold.version_id, threshold.doc_id],
                ).fetchall()
            except duckdb.Error:
                version_rows = []
            for row in version_rows:
                version_start = self._parse_lex_date(str(row[0] or ""))
                if version_start is not None and (start is None or version_start > start):
                    candidates.append(version_start)
        for sibling in self._threshold_lineage_rows(threshold):
            if sibling.threshold_id == threshold.threshold_id:
                continue
            sibling_start = self._threshold_effective_start(sibling)
            if sibling_start is None:
                continue
            if start is None or sibling_start > start:
                candidates.append(sibling_start)
        return min(candidates) if candidates else None

    def _threshold_temporal_status_from_row(
        self,
        *,
        threshold: LegalRuleThresholdRow,
        as_of: str,
    ) -> LegalTemporalCompetence:
        subject_ref = self._duckdb_ref(f"lex_rule_thresholds/{threshold.threshold_id}")
        as_of_date = self._parse_lex_date(as_of)
        if as_of_date is None:
            return LegalTemporalCompetence(
                status="blocked",
                subject_ref=subject_ref,
                as_of=as_of,
                reason="as_of_unparseable",
            )
        effective_from = self._threshold_effective_start(threshold)
        effective_to = self._parse_lex_date(threshold.effective_to)
        next_start = self._threshold_next_start(threshold=threshold, start=effective_from)
        stale_after = effective_to
        if next_start is not None and (stale_after is None or next_start < stale_after):
            stale_after = next_start
        if effective_from is not None and as_of_date < effective_from:
            return LegalTemporalCompetence(
                status="not_yet_in_force",
                subject_ref=subject_ref,
                as_of=as_of,
                effective_from=self._date_to_iso(effective_from),
                effective_to=self._date_to_iso(stale_after),
                reason="as_of_before_effective_from",
            )
        if stale_after is not None and as_of_date >= stale_after:
            return LegalTemporalCompetence(
                status="stale",
                subject_ref=subject_ref,
                as_of=as_of,
                effective_from=self._date_to_iso(effective_from),
                effective_to=self._date_to_iso(stale_after),
                stale_after=self._date_to_iso(stale_after),
                reason="superseded_by_later_threshold_version",
            )
        return LegalTemporalCompetence(
            status="in_force",
            subject_ref=subject_ref,
            as_of=as_of,
            effective_from=self._date_to_iso(effective_from),
            effective_to=self._date_to_iso(stale_after),
            reason="threshold_version_in_force",
        )

    def resolve_threshold_temporal_competence(
        self,
        *,
        threshold_id: str,
        as_of: str,
    ) -> LegalTemporalCompetence:
        """Resolve the as-of temporal window for a threshold-backed norm."""

        threshold = self.resolve_rule_threshold(threshold_id=threshold_id)
        subject_ref = self._duckdb_ref(f"lex_rule_thresholds/{threshold_id}")
        if threshold is None:
            return LegalTemporalCompetence(
                status="blocked",
                subject_ref=subject_ref,
                as_of=as_of,
                reason="threshold_unresolved",
            )
        return self._threshold_temporal_status_from_row(threshold=threshold, as_of=as_of)

    def resolve_amendment_temporal_competence(
        self,
        *,
        amendment_id: str,
        as_of: str,
    ) -> LegalTemporalCompetence:
        """Resolve amendment effective_from as temporal competence authority."""

        subject_ref = self._duckdb_ref(f"lex_amendments/{amendment_id}")
        if not self._table_exists("lex_amendments"):
            return LegalTemporalCompetence(
                status="blocked",
                subject_ref=subject_ref,
                as_of=as_of,
                amendment_id=amendment_id,
                reason="amendment_store_unavailable",
            )
        row = self._con.execute(
            """
            SELECT amendment_id, amendment_type, effective_from, amended_doc_id, target_anchor
            FROM lex_amendments
            WHERE amendment_id = ?
            LIMIT 1
            """,
            [str(amendment_id).strip()],
        ).fetchone()
        if row is None:
            return LegalTemporalCompetence(
                status="blocked",
                subject_ref=subject_ref,
                as_of=as_of,
                amendment_id=amendment_id,
                reason="amendment_unresolved",
            )
        effective_from = str(row[2] or "").strip()
        amendment_type = str(row[1] or "").strip()
        amended_doc_id = str(row[3] or "").strip()
        target_anchor = str(row[4] or "").strip()
        if not effective_from:
            return LegalTemporalCompetence(
                status="blocked",
                subject_ref=subject_ref,
                as_of=as_of,
                amendment_id=str(row[0]),
                amendment_type=amendment_type,
                reason="amendment_effective_from_missing",
            )
        as_of_date = self._parse_lex_date(as_of)
        effective_from_date = self._parse_lex_date(effective_from)
        if as_of_date is None or effective_from_date is None:
            return LegalTemporalCompetence(
                status="blocked",
                subject_ref=subject_ref,
                as_of=str(as_of),
                effective_from=effective_from,
                amendment_id=str(row[0]),
                amendment_type=amendment_type,
                reason="amendment_date_unparseable",
            )
        if as_of_date < effective_from_date:
            return LegalTemporalCompetence(
                status="not_yet_in_force",
                subject_ref=subject_ref,
                as_of=str(as_of),
                effective_from=self._date_to_iso(effective_from_date),
                amendment_id=str(row[0]),
                amendment_type=amendment_type,
                reason="as_of_before_effective_from",
            )
        superseding = self._superseding_amendment_start(
            amendment_id=str(row[0]),
            amended_doc_id=amended_doc_id,
            target_anchor=target_anchor,
            effective_from=effective_from_date,
        )
        if superseding is not None and as_of_date >= superseding:
            return LegalTemporalCompetence(
                status="stale",
                subject_ref=subject_ref,
                as_of=str(as_of),
                effective_from=self._date_to_iso(effective_from_date),
                effective_to=self._date_to_iso(superseding),
                stale_after=self._date_to_iso(superseding),
                amendment_id=str(row[0]),
                amendment_type=amendment_type,
                reason="superseded_by_later_amendment",
            )
        return LegalTemporalCompetence(
            status="in_force",
            subject_ref=subject_ref,
            as_of=str(as_of),
            effective_from=self._date_to_iso(effective_from_date),
            effective_to=self._date_to_iso(superseding),
            amendment_id=str(row[0]),
            amendment_type=amendment_type,
            reason="amendment_in_force",
        )

    def _superseding_amendment_start(
        self,
        *,
        amendment_id: str,
        amended_doc_id: str,
        target_anchor: str,
        effective_from: date,
    ) -> date | None:
        clauses = ["amendment_id != ?", "effective_from IS NOT NULL", "effective_from != ''"]
        params: list[Any] = [amendment_id]
        if amended_doc_id:
            clauses.append("amended_doc_id = ?")
            params.append(amended_doc_id)
        else:
            clauses.append("COALESCE(amended_doc_id, '') = ''")
        if target_anchor:
            clauses.append("target_anchor = ?")
            params.append(target_anchor)
        else:
            clauses.append("COALESCE(target_anchor, '') = ''")
        rows = self._con.execute(
            f"""
            SELECT effective_from
            FROM lex_amendments
            {self._to_where_sql(clauses)}
            ORDER BY effective_from ASC, amendment_id ASC
            """,
            params,
        ).fetchall()
        candidates = [
            parsed
            for row in rows
            if (parsed := self._parse_lex_date(str(row[0] or ""))) is not None
            and parsed > effective_from
        ]
        return min(candidates) if candidates else None

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
            clauses.insert(
                0, "(fact_text ILIKE ? OR source_quote_uk ILIKE ? OR condition_text_uk ILIKE ?)"
            )
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
                        if (
                            candidate_pair[0]
                            and candidate_pair[1]
                            and candidate_pair not in seen_pairs
                        ):
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
            "|".join(
                [doc_id, resolved_version_id, *sorted(item.anchor for item in primary_anchors)]
            ).encode("utf-8")
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
