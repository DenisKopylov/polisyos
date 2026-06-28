"""Read-only access to the DuckDB dataset catalog + HNSW vector index."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import duckdb
import numpy as np

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.knowledge.types import (
    DatasetAccess,
    DatasetCoverage,
    DatasetQuality,
    DatasetSearchResult,
    DistributionResult,
    MetricBindingMatch,
    ResolvedFetchTarget,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = get_logger(__name__)

# Execution tier hierarchy (highest to lowest).
_EXECUTION_TIER_RANK: dict[str, int] = {
    "transport_ready": 0,
    "fetchable": 1,
    "catalog": 2,
}


def _tiers_at_or_above(min_tier: str) -> list[str]:
    """Return all tiers at or above *min_tier* in the hierarchy."""
    threshold = _EXECUTION_TIER_RANK.get(min_tier, 2)
    return [tier for tier, rank in _EXECUTION_TIER_RANK.items() if rank <= threshold]


_DATASET_COLUMNS: list[tuple[str, str]] = [
    ("id", "''"),
    ("title", "''"),
    ("description", "''"),
    ("publisher", "''"),
    ("spatial", "''"),
    ("temporal_start", "NULL"),
    ("temporal_end", "NULL"),
    ("source_portal", "''"),
    ("polisyos_metrics", "CAST([] AS VARCHAR[])"),
    ("keywords", "CAST([] AS VARCHAR[])"),
    ("themes", "CAST([] AS VARCHAR[])"),
    ("variables", "CAST([] AS VARCHAR[])"),
    ("formats", "CAST([] AS VARCHAR[])"),
    ("source", "''"),
    ("agency", "''"),
    ("dataset_id", "''"),
    ("source_dataset_id", "''"),
    ("dedup_key", "''"),
    ("execution_tier", "'catalog'"),
    ("update_frequency", "''"),
    ("last_updated", "NULL"),
    ("coverage_countries", "CAST([] AS VARCHAR[])"),
    ("coverage_regions", "CAST([] AS VARCHAR[])"),
    ("coverage_time_start", "NULL"),
    ("coverage_time_end", "NULL"),
    ("coverage_granularity", "''"),
    ("access_api_endpoint", "NULL"),
    ("access_bulk_download_url", "NULL"),
    ("access_license", "''"),
    ("access_auth_required", "FALSE"),
    ("quality_description_score", "0.0"),
    ("quality_machine_readable_score", "0.0"),
    ("quality_parser_support_score", "0.0"),
    ("quality_freshness_score", "0.0"),
    ("quality_execution_readiness_score", "0.0"),
    ("preferred_distribution_id", "''"),
]
_DISTRIBUTION_COLUMNS: list[tuple[str, str]] = [
    ("id", "''"),
    ("dataset_id", "''"),
    ("url", "''"),
    ("format", "''"),
    ("connector_type", "''"),
    ("connector_params", "'{}'"),
    ("source_locator", "''"),
    ("profile_id", "''"),
    ("media_type", "''"),
    ("machine_readable", "FALSE"),
    ("parser_supported", "FALSE"),
    ("size_estimate_bytes", "NULL"),
    ("checksum", "''"),
    ("default_filters", "'{}'"),
    ("quality_score", "0.0"),
]
_BINDING_COLUMNS: list[tuple[str, str]] = [
    ("metric_id", "''"),
    ("dataset_id", "''"),
    ("distribution_id", "''"),
    ("connector_id", "''"),
    ("profile_id", "''"),
    ("request_dataset_id", "''"),
    ("confidence", "0.0"),
    ("metric_inference_confidence", "0.0"),
    ("default_filters", "'{}'"),
    ("execution_tier", "'catalog'"),
    ("source", "''"),
]
_CONNECTOR_ALIASES = {
    "worldbank": "worldbank.wdi",
    "ukons": "ukons.datasets",
    "sdmx": "sdmx.source",
    "wvs": "wvs.wave7",
    "rest_json": "rest.json",
}


class DatasetCatalogStore:
    """Read-only handle to the dataset catalog (DuckDB + HNSW)."""

    def __init__(self, db_path: Path, index_dir: Path) -> None:
        self._db_path = db_path
        self._index_dir = index_dir
        self._con = duckdb.connect(str(db_path), read_only=True)

        self._dataset_index = None
        self._dataset_ids: list[str] | None = None
        self._table_exists_cache: dict[str, bool] = {}
        self._table_columns_cache: dict[str, set[str]] = {}
        self._index_files_available: bool | None = None
        self._index_warning_logged = False

    def has_vector_index(self) -> bool:
        if self._index_files_available is None:
            npz_path = self._index_dir / "ds_dataset_embeddings.npz"
            hnsw_path = self._index_dir / "ds_dataset_index.hnsw"
            self._index_files_available = npz_path.exists() and hnsw_path.exists()
        return bool(self._index_files_available)

    def _table_exists(self, table_name: str) -> bool:
        cached = self._table_exists_cache.get(table_name)
        if cached is not None:
            return cached
        row = self._con.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
            [table_name],
        ).fetchone()
        exists = row is not None
        self._table_exists_cache[table_name] = exists
        return exists

    def _table_columns(self, table_name: str) -> set[str]:
        cached = self._table_columns_cache.get(table_name)
        if cached is not None:
            return cached
        if not self._table_exists(table_name):
            self._table_columns_cache[table_name] = set()
            return set()
        rows = self._con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        columns = {str(row[1]) for row in rows}
        self._table_columns_cache[table_name] = columns
        return columns

    def _select_clause(
        self,
        table_name: str,
        columns: list[tuple[str, str]],
        *,
        alias: str | None = None,
    ) -> str:
        available = self._table_columns(table_name)
        prefix = f"{alias}." if alias else ""
        parts: list[str] = []
        for column_name, default_sql in columns:
            if column_name in available:
                parts.append(f"{prefix}{column_name} AS {column_name}")
            else:
                parts.append(f"{default_sql} AS {column_name}")
        return ", ".join(parts)

    def _fetch_dicts(
        self, sql: str, params: list[object] | tuple[object, ...]
    ) -> list[dict[str, object]]:
        cursor = self._con.execute(sql, params)
        columns = [str(item[0]) for item in cursor.description]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    def _load_dataset_index(self) -> None:
        if self._dataset_index is not None:
            return
        import hnswlib

        npz_path = self._index_dir / "ds_dataset_embeddings.npz"
        hnsw_path = self._index_dir / "ds_dataset_index.hnsw"
        if not self.has_vector_index():
            if not self._index_warning_logged:
                logger.warning("Dataset index files not found in {}", self._index_dir)
                self._index_warning_logged = True
            return

        data = np.load(str(npz_path), allow_pickle=True)
        self._dataset_ids = list(data["ids"])
        dim = int(data["vectors"].shape[1])

        idx = hnswlib.Index(space="cosine", dim=dim)
        idx.load_index(str(hnsw_path), max_elements=len(self._dataset_ids))
        idx.set_ef(100)
        self._dataset_index = idx

    @staticmethod
    def _as_list(value: object) -> list[str]:
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        if isinstance(value, tuple):
            return [str(item) for item in value if str(item)]
        return []

    @staticmethod
    def _as_bool(value: object) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return False

    @staticmethod
    def _json_mapping(value: object) -> dict:
        if isinstance(value, dict):
            return value
        if isinstance(value, str) and value.strip():
            try:
                parsed = json.loads(value)
            except json.JSONDecodeError:
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    @staticmethod
    def _normalize_connector_id(connector_id: str) -> str:
        value = (connector_id or "").strip()
        return _CONNECTOR_ALIASES.get(value, value)

    def _to_dataset_result(
        self, row: dict[str, object], *, similarity: float = 0.0
    ) -> DatasetSearchResult:
        return DatasetSearchResult(
            id=str(row.get("id") or ""),
            title=str(row.get("title") or ""),
            description=str(row.get("description") or ""),
            publisher=str(row.get("publisher") or ""),
            spatial=str(row.get("spatial") or ""),
            temporal_start=str(row["temporal_start"]) if row.get("temporal_start") else None,
            temporal_end=str(row["temporal_end"]) if row.get("temporal_end") else None,
            source_portal=str(row.get("source_portal") or ""),
            polisyos_metrics=self._as_list(row.get("polisyos_metrics")),
            keywords=self._as_list(row.get("keywords")),
            themes=self._as_list(row.get("themes")),
            variables=self._as_list(row.get("variables")),
            formats=self._as_list(row.get("formats")),
            source=str(row.get("source") or ""),
            agency=str(row.get("agency") or ""),
            dataset_id=str(row.get("dataset_id") or ""),
            source_dataset_id=str(row.get("source_dataset_id") or ""),
            dedup_key=str(row.get("dedup_key") or ""),
            execution_tier=str(row.get("execution_tier") or "catalog"),
            update_frequency=str(row.get("update_frequency") or ""),
            last_updated=str(row["last_updated"]) if row.get("last_updated") else None,
            coverage=DatasetCoverage(
                countries=self._as_list(row.get("coverage_countries")),
                regions=self._as_list(row.get("coverage_regions")),
                time_range="",
                time_start=str(row["coverage_time_start"])
                if row.get("coverage_time_start")
                else None,
                time_end=str(row["coverage_time_end"]) if row.get("coverage_time_end") else None,
                granularity=str(row.get("coverage_granularity") or ""),
            ),
            access=DatasetAccess(
                api_endpoint=str(row["access_api_endpoint"])
                if row.get("access_api_endpoint")
                else None,
                bulk_download_url=str(row["access_bulk_download_url"])
                if row.get("access_bulk_download_url")
                else None,
                license=str(row.get("access_license") or ""),
                auth_required=self._as_bool(row.get("access_auth_required")),
            ),
            quality=DatasetQuality(
                description_score=float(row.get("quality_description_score") or 0.0),
                machine_readable_score=float(row.get("quality_machine_readable_score") or 0.0),
                parser_support_score=float(row.get("quality_parser_support_score") or 0.0),
                freshness_score=float(row.get("quality_freshness_score") or 0.0),
                execution_readiness_score=float(
                    row.get("quality_execution_readiness_score") or 0.0
                ),
            ),
            preferred_distribution_id=str(row.get("preferred_distribution_id") or ""),
            similarity=similarity,
        )

    def _to_distribution_result(self, row: dict[str, object]) -> DistributionResult:
        return DistributionResult(
            id=str(row.get("id") or ""),
            dataset_id=str(row.get("dataset_id") or ""),
            url=str(row.get("url") or ""),
            format=str(row.get("format") or ""),
            connector_type=self._normalize_connector_id(str(row.get("connector_type") or "")),
            connector_params=self._json_mapping(row.get("connector_params")),
            source_locator=str(row.get("source_locator") or ""),
            profile_id=str(row.get("profile_id") or ""),
            media_type=str(row.get("media_type") or ""),
            machine_readable=self._as_bool(row.get("machine_readable")),
            parser_supported=self._as_bool(row.get("parser_supported")),
            size_estimate_bytes=int(row["size_estimate_bytes"])
            if row.get("size_estimate_bytes") is not None
            else None,
            checksum=str(row.get("checksum") or ""),
            default_filters=self._json_mapping(row.get("default_filters")),
            quality_score=float(row.get("quality_score") or 0.0),
        )

    def _get_dataset_row(self, dataset_id: str) -> dict[str, object] | None:
        rows = self._fetch_dicts(
            f"SELECT {self._select_clause('ds_datasets', _DATASET_COLUMNS)} FROM ds_datasets WHERE id = ? LIMIT 1",
            [dataset_id],
        )
        return rows[0] if rows else None

    def get_dataset(self, dataset_id: str) -> DatasetSearchResult | None:
        row = self._get_dataset_row(dataset_id)
        if row is None:
            return None
        return self._to_dataset_result(row)

    @staticmethod
    def _infer_request_dataset_id(distribution: DistributionResult) -> str:
        params = distribution.connector_params
        if distribution.source_locator:
            return distribution.source_locator
        if distribution.connector_type == "worldbank.wdi":
            return str(params.get("indicator_id") or distribution.url or "").strip()
        if distribution.connector_type in {
            "ukons.datasets",
            "eurostat.data",
            "sdmx.source",
            "wvs.wave7",
        }:
            return str(
                params.get("dataset_id")
                or params.get("dataflow_id")
                or params.get("indicator_id")
                or distribution.url
                or ""
            ).strip()
        if distribution.connector_type == "ckan.resource":
            package_id = str(params.get("package_id") or "").strip()
            resource_id = str(params.get("resource_id") or "").strip()
            if package_id and resource_id:
                return f"{package_id}/{resource_id}"
            if distribution.url:
                return distribution.url
        if distribution.connector_type == "rest.json":
            return str(params.get("url") or distribution.url or "").strip()
        return distribution.url or ""

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
        select_clause = self._select_clause("ds_datasets", _DATASET_COLUMNS)
        for label, dist in zip(labels[0], distances[0], strict=False):
            similarity = 1.0 - float(dist)
            if similarity < min_similarity:
                continue
            did = self._dataset_ids[int(label)]
            rows = self._fetch_dicts(f"SELECT {select_clause} FROM ds_datasets WHERE id = ?", [did])
            if rows:
                results.append(self._to_dataset_result(rows[0], similarity=similarity))
        return results

    def search_by_text(self, query: str, *, top_k: int = 20) -> list[DatasetSearchResult]:
        normalized = query.strip().lower()
        if not normalized:
            return []

        tokens = [
            token
            for token in dict.fromkeys(re.split(r"[^\w]+", normalized, flags=re.UNICODE))
            if len(token) >= 2
        ][:8]
        if not tokens:
            tokens = [normalized]

        haystack = (
            "lower("
            "coalesce(title, '') || ' ' || "
            "coalesce(description, '') || ' ' || "
            "coalesce(array_to_string(keywords, ' '), '') || ' ' || "
            "coalesce(array_to_string(variables, ' '), '') || ' ' || "
            "coalesce(array_to_string(polisyos_metrics, ' '), '') || ' ' || "
            "coalesce(array_to_string(themes, ' '), '') || ' ' || "
            "coalesce(source, '') || ' ' || "
            "coalesce(agency, '')"
            ")"
        )
        title_expr = "lower(coalesce(title, ''))"
        description_expr = "lower(coalesce(description, ''))"

        score_parts = [
            f"CASE WHEN {title_expr} LIKE ? THEN 8 ELSE 0 END",
            f"CASE WHEN {description_expr} LIKE ? THEN 3 ELSE 0 END",
            f"CASE WHEN {haystack} LIKE ? THEN 2 ELSE 0 END",
        ]
        score_params: list[object] = [f"%{normalized}%", f"%{normalized}%", f"%{normalized}%"]
        where_parts = [f"{haystack} LIKE ?"]
        where_params: list[object] = [f"%{normalized}%"]

        for token in tokens:
            pattern = f"%{token}%"
            score_parts.append(f"CASE WHEN {title_expr} LIKE ? THEN 3 ELSE 0 END")
            score_parts.append(f"CASE WHEN {description_expr} LIKE ? THEN 1 ELSE 0 END")
            score_parts.append(f"CASE WHEN {haystack} LIKE ? THEN 1 ELSE 0 END")
            score_params.extend([pattern, pattern, pattern])
            where_parts.append(f"{haystack} LIKE ?")
            where_params.append(pattern)

        select_clause = self._select_clause("ds_datasets", _DATASET_COLUMNS)
        score_expr = " + ".join(score_parts)
        where_clause = " OR ".join(where_parts)
        rows = self._fetch_dicts(
            f"SELECT {select_clause}, ({score_expr}) AS text_score "
            "FROM ds_datasets "
            f"WHERE {where_clause} "
            "ORDER BY text_score DESC, quality_execution_readiness_score DESC, title ASC, id ASC "
            "LIMIT ?",
            [*score_params, *where_params, top_k],
        )
        return [self._to_dataset_result(row, similarity=1.0) for row in rows]

    def find_by_polisyos_metric(
        self, metric_name: str, *, top_k: int = 20
    ) -> list[DatasetSearchResult]:
        rows = self._fetch_dicts(
            f"SELECT {self._select_clause('ds_datasets', _DATASET_COLUMNS)} FROM ds_datasets "
            "WHERE list_contains(polisyos_metrics, ?) LIMIT ?",
            [metric_name, top_k],
        )
        return [self._to_dataset_result(row, similarity=1.0) for row in rows]

    def find_by_variables(
        self, variables: list[str], *, top_k: int = 20
    ) -> list[DatasetSearchResult]:
        if not variables:
            return []
        conditions = " OR ".join("list_contains(variables, ?)" for _ in variables)
        rows = self._fetch_dicts(
            f"SELECT {self._select_clause('ds_datasets', _DATASET_COLUMNS)} FROM ds_datasets WHERE {conditions} LIMIT ?",
            [*variables, top_k],
        )
        return [self._to_dataset_result(row, similarity=1.0) for row in rows]

    def resolve_metric_bindings(
        self,
        metric_name: str,
        *,
        top_k: int = 20,
        min_execution_tier: str | None = None,
    ) -> list[MetricBindingMatch]:
        """Resolve metric bindings with optional execution tier enforcement.

        When *min_execution_tier* is set, only bindings whose tier meets or
        exceeds the requested minimum are returned.  Tier ordering:
        ``transport_ready`` > ``fetchable`` > ``catalog``.
        """
        if not self._table_exists("ds_metric_bindings"):
            return []
        schema_exists_sql = (
            "EXISTS (SELECT 1 FROM ds_schema_profiles AS sp WHERE sp.dataset_id = b.dataset_id)"
            if self._table_exists("ds_schema_profiles")
            else "FALSE"
        )
        tier_filter_sql = ""
        bind_params: list[object] = [metric_name]
        if min_execution_tier:
            allowed = _tiers_at_or_above(min_execution_tier)
            if allowed:
                placeholders = ", ".join("?" for _ in allowed)
                tier_filter_sql = f"AND COALESCE(b.execution_tier, 'catalog') IN ({placeholders}) "
                bind_params.extend(allowed)
        bind_params.append(top_k)
        rows = self._fetch_dicts(
            f"SELECT {self._select_clause('ds_metric_bindings', _BINDING_COLUMNS, alias='b')}, "
            "COALESCE(ds.title, '') AS title "
            "FROM ds_metric_bindings AS b "
            "LEFT JOIN ds_datasets AS ds ON ds.id = b.dataset_id "
            f"WHERE b.metric_id = ? {tier_filter_sql}"
            "ORDER BY "
            "CASE COALESCE(b.execution_tier, 'catalog') "
            "WHEN 'transport_ready' THEN 0 "
            "WHEN 'fetchable' THEN 1 "
            "ELSE 2 END ASC, "
            f"CASE WHEN {schema_exists_sql} THEN 0 ELSE 1 END ASC, "
            "b.confidence DESC, b.dataset_id ASC "
            "LIMIT ?",
            bind_params,
        )
        out: list[MetricBindingMatch] = []
        for row in rows:
            out.append(
                MetricBindingMatch(
                    metric_id=str(row.get("metric_id") or ""),
                    catalog_dataset_id=str(row.get("dataset_id") or ""),
                    distribution_id=str(row.get("distribution_id") or ""),
                    connector_id=self._normalize_connector_id(str(row.get("connector_id") or "")),
                    profile_id=str(row.get("profile_id") or ""),
                    request_dataset_id=str(row.get("request_dataset_id") or ""),
                    confidence=float(row.get("confidence") or 0.0),
                    metric_inference_confidence=float(
                        row.get("metric_inference_confidence") or 0.0
                    ),
                    default_filters=self._json_mapping(row.get("default_filters")),
                    execution_tier=str(row.get("execution_tier") or "catalog"),
                    source=str(row.get("source") or ""),
                    title=str(row.get("title") or ""),
                )
            )
        return out

    def search_metric_bindings(
        self,
        query: str,
        *,
        top_k: int = 20,
        modes: tuple[str, ...] = ("exact", "alias", "lexical", "semantic"),
        min_execution_tier: str | None = None,
    ) -> list[MetricBindingMatch]:
        """Search metric bindings by exact id, aliases, and lexical construct terms."""

        if not self._table_exists("ds_metric_bindings"):
            return []
        aliases, tokens = self._metric_binding_search_terms(query)
        if not aliases and not tokens:
            return []

        conditions: list[str] = []
        params: list[object] = []
        use_exact = "exact" in modes or "alias" in modes
        use_lexical = "lexical" in modes or "semantic" in modes
        metric_expr = "lower(coalesce(b.metric_id, ''))"
        metric_norm_expr = "replace(replace(lower(coalesce(b.metric_id, '')), '.', '_'), '-', '_')"
        if use_exact and aliases:
            placeholders = ", ".join("?" for _ in aliases)
            conditions.append(f"({metric_expr} IN ({placeholders}))")
            params.extend(aliases)
            conditions.append(f"({metric_norm_expr} IN ({placeholders}))")
            params.extend(aliases)
        if use_lexical:
            for term in (*aliases, *tokens):
                if len(term) < 2:
                    continue
                conditions.append(f"{metric_norm_expr} LIKE ?")
                params.append(f"%{term}%")
        if not conditions:
            return []

        tier_filter_sql = ""
        if min_execution_tier:
            allowed = _tiers_at_or_above(min_execution_tier)
            if allowed:
                placeholders = ", ".join("?" for _ in allowed)
                tier_filter_sql = f"AND COALESCE(b.execution_tier, 'catalog') IN ({placeholders}) "
                params.extend(allowed)
        params.append(max(top_k * 8, top_k))
        rows = self._fetch_dicts(
            f"SELECT {self._select_clause('ds_metric_bindings', _BINDING_COLUMNS, alias='b')}, "
            "COALESCE(ds.title, '') AS title "
            "FROM ds_metric_bindings AS b "
            "LEFT JOIN ds_datasets AS ds ON ds.id = b.dataset_id "
            f"WHERE ({' OR '.join(conditions)}) {tier_filter_sql}"
            "ORDER BY "
            "CASE COALESCE(b.execution_tier, 'catalog') "
            "WHEN 'transport_ready' THEN 0 "
            "WHEN 'fetchable' THEN 1 "
            "ELSE 2 END ASC, "
            "b.confidence DESC, b.dataset_id ASC "
            "LIMIT ?",
            params,
        )
        ranked = sorted(
            rows,
            key=lambda row: (
                self._metric_binding_search_rank(row, aliases, tokens),
                _EXECUTION_TIER_RANK.get(str(row.get("execution_tier") or "catalog"), 2),
                -float(row.get("confidence") or 0.0),
                str(row.get("metric_id") or ""),
                str(row.get("dataset_id") or ""),
            ),
        )
        return [self._to_metric_binding_match(row) for row in ranked[:top_k]]

    @staticmethod
    def _metric_binding_search_terms(query: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
        raw = " ".join(str(query or "").strip().lower().split())
        if not raw:
            return (), ()
        normalized = raw.removeprefix("construct:").removeprefix("policy.")
        variants = (
            raw,
            normalized,
            raw.replace(".", "_").replace("-", "_").replace(" ", "_"),
            normalized.replace(".", "_").replace("-", "_").replace(" ", "_"),
        )
        aliases = tuple(dict.fromkeys(item for item in variants if item))
        tokens = tuple(
            dict.fromkeys(
                token
                for alias in aliases
                for token in re.split(r"[^\w]+", alias, flags=re.UNICODE)
                if len(token) >= 2
            )
        )
        return aliases, tokens

    @staticmethod
    def _metric_binding_search_rank(
        row: dict[str, object],
        aliases: tuple[str, ...],
        tokens: tuple[str, ...],
    ) -> int:
        metric = str(row.get("metric_id") or "").lower()
        metric_norm = metric.replace(".", "_").replace("-", "_")
        if metric in aliases or metric_norm in aliases:
            return 0
        if any(metric_norm.startswith(alias) for alias in aliases if len(alias) >= 3):
            return 1
        if any(metric_norm.startswith(token) for token in tokens):
            return 2
        if any(token in metric_norm for token in tokens):
            return 3
        return 4

    def _to_metric_binding_match(self, row: dict[str, object]) -> MetricBindingMatch:
        return MetricBindingMatch(
            metric_id=str(row.get("metric_id") or ""),
            catalog_dataset_id=str(row.get("dataset_id") or ""),
            distribution_id=str(row.get("distribution_id") or ""),
            connector_id=self._normalize_connector_id(str(row.get("connector_id") or "")),
            profile_id=str(row.get("profile_id") or ""),
            request_dataset_id=str(row.get("request_dataset_id") or ""),
            confidence=float(row.get("confidence") or 0.0),
            metric_inference_confidence=float(row.get("metric_inference_confidence") or 0.0),
            default_filters=self._json_mapping(row.get("default_filters")),
            execution_tier=str(row.get("execution_tier") or "catalog"),
            source=str(row.get("source") or ""),
            title=str(row.get("title") or ""),
        )

    def resolve_fetch_target(self, dataset_id: str) -> ResolvedFetchTarget | None:
        dataset_row = self._get_dataset_row(dataset_id)
        distributions = self.get_distributions(dataset_id)
        if not distributions:
            return None
        preferred_distribution_id = (
            str(dataset_row.get("preferred_distribution_id") or "") if dataset_row else ""
        )
        distribution = sorted(
            distributions,
            key=lambda item: (
                0 if item.id == preferred_distribution_id else 1,
                -int(item.parser_supported),
                -int(item.machine_readable),
                -item.quality_score,
                item.id,
            ),
        )[0]
        request_dataset_id = self._infer_request_dataset_id(distribution)
        if not request_dataset_id:
            return None
        return ResolvedFetchTarget(
            catalog_dataset_id=dataset_id,
            connector_id=self._normalize_connector_id(distribution.connector_type),
            profile_id=distribution.profile_id,
            request_dataset_id=request_dataset_id,
            distribution_id=distribution.id,
            connector_params=distribution.connector_params,
            default_filters=distribution.default_filters,
            machine_readable=distribution.machine_readable,
            parser_supported=distribution.parser_supported,
        )

    def get_connector_params(self, dataset_id: str) -> dict | None:
        target = self.resolve_fetch_target(dataset_id)
        if target is None:
            return None
        return {
            "type": target.connector_id,
            "params": target.connector_params,
            "dataset_id": target.request_dataset_id,
            "profile_id": target.profile_id,
            "distribution_id": target.distribution_id,
            "default_filters": target.default_filters,
            "machine_readable": target.machine_readable,
            "parser_supported": target.parser_supported,
        }

    def get_distributions(self, dataset_id: str) -> list[DistributionResult]:
        rows = self._fetch_dicts(
            f"SELECT {self._select_clause('ds_distributions', _DISTRIBUTION_COLUMNS)} "
            "FROM ds_distributions WHERE dataset_id = ? ORDER BY parser_supported DESC, quality_score DESC, id ASC",
            [dataset_id],
        )
        return [self._to_distribution_result(row) for row in rows]

    def close(self) -> None:
        self._con.close()
