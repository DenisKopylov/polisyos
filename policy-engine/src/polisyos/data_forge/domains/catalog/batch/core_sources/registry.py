"""Stage 0b: ingest transportability sources into registry/alignment/observation tables."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, fields
from datetime import UTC, datetime
from importlib import import_module
from typing import TYPE_CHECKING, cast

from polisyos.common.logger import get_logger
from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    CatalogTransportDataset,
    ObservationPlan,
    ObservationShard,
    SupportSketch,
)
from polisyos.data_forge.domains.catalog.batch.core_sources.schema import (
    alignment_audit_columns,
    create_alignment_audit_table,
    create_alignment_review_basis_table,
    resolve_alignment_audit_schema_profile,
    resolve_alignment_review_basis_schema,
)
from polisyos.data_forge.domains.catalog.knowledge.country_codes import (
    iso2_to_numeric,
)
from polisyos.data_forge.domains.catalog.knowledge.proxy_penalties import metric_proxy_alignments
from polisyos.data_forge.domains.catalog.knowledge.variable_alignment import (
    AlignmentMethod,
    VariableAlignment,
    align_semantic,
    calibrate_alignment_confidence,
    load_seed_alignments,
)
from polisyos.data_forge.read_api.academic import CANONICAL_VARIABLES

if TYPE_CHECKING:
    import asyncio
    from collections.abc import Callable, Iterable
    from pathlib import Path

    import duckdb

    from polisyos.data_forge.domains.catalog.batch.config import DatasetBatchConfig
    from polisyos.fabric.connectors.base import DatasetCapabilitySnapshot
    from polisyos.fabric.connectors.profiles.models import SourceExecutionPolicy

from polisyos.data_forge.domains.catalog.batch._core_sources_ingest_contracts import (
    resolve_core_sources_compatibility_binding,
)

logger = get_logger(__name__)

# These are the database relations the catalog core-source producer reads to
# construct its transport plan and the relations it writes for downstream
# catalog consumers. Keep this inventory beside the producer's table schema
# and plan loader so receipt consumers bind the same persisted boundary.
_CORE_SOURCE_RECEIPT_TABLES: dict[str, tuple[str, ...]] = {
    "inputs": ("ds_datasets", "ds_distributions"),
    "outputs": (
        "ds_registry_datasets",
        "ds_variable_alignments",
        "ds_alignment_audit",
        "ds_alignment_review_basis",
        "ds_observations",
    ),
}
_ALIGNMENT_AUDIT_OPERATIONAL_FIELDS = frozenset({"resolved_at"})
_ALIGNMENT_AUDIT_REVIEW_FIELDS = frozenset({"reviewed", "reviewer_override"})
_ALIGNMENT_AUDIT_WRITE_BATCH_SIZE = 500
_ALIGNMENT_REVIEW_BASIS_VERSION = "policyos.catalog.alignment_review_basis.v2"


@dataclass(frozen=True, slots=True)
class _AlignmentReviewBasisRecord:
    """One persisted operational basis for a complete dataset/raw-variable group."""

    dataset_id: str
    raw_variable: str
    basis_version: str
    basis_json: str
    basis_sha256: str


_AlignmentReviewBasisKey = tuple[str, str]
_AlignmentReviewBasisMap = dict[_AlignmentReviewBasisKey, _AlignmentReviewBasisRecord]


def _core_source_receipt_tables() -> dict[str, tuple[str, ...]]:
    """Return the catalog core producer's canonical persisted table boundary."""
    return {role: tuple(names) for role, names in _CORE_SOURCE_RECEIPT_TABLES.items()}


_TRANSPORT_SOURCES = frozenset(
    {
        "worldbank",
        "eurostat",
        "oecd",
        "ilo",
        "who",
        "unpd",
        "wvs",
        "unesco_uis",
    }
)
_LEGACY_WGI_INDICATORS: dict[str, str] = {
    "RL.EST": "institutional_quality",
    "CC.EST": "corruption_level",
    "GE.EST": "state_capacity",
}
_LEGACY_WDI_INDICATORS: dict[str, str] = {
    "NY.GDP.PCAP.PP.CD": "gdp_per_capita",
}
_LEGACY_WVS_INDICATORS_STATIC: dict[str, str] = {
    "A165": "social_trust",
    "A173": "cultural_cluster",
}
_CANONICAL_ROOTS = tuple(sorted(CANONICAL_VARIABLES.keys()))
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_WVS_SPECIAL_AGGREGATIONS_STATIC: dict[str, str] = {"A165": "weighted_share_response_1"}
_WVS_WEIGHT_FIELDS: tuple[str, ...] = ("S017", "S018")
_OBSERVATION_INSERT_BATCH_SIZE = 500
_DEFAULT_OBSERVATION_YEAR_WINDOW: tuple[int, int] = (2018, 2022)
_EUROSTAT_SUBANNUAL_TITLE_TOKENS: tuple[str, ...] = (
    "month",
    "monthly",
    "quarter",
    "quarterly",
    "mensuel",
    "mensuelle",
    "monat",
    "monatlich",
    "quartal",
    "viertelj",
    "trimestr",
)
_DEFAULT_SOURCE_CONCURRENCY: dict[str, int] = {
    "eurostat": 3,
    "worldbank": 4,
    "who": 2,
    "unesco_uis": 2,
    "unpd": 1,
    "oecd": 1,
    "ilo": 1,
    "wvs": 1,
}
_SOURCE_LANE_DEFAULTS: dict[str, int] = {
    "eurostat": 1,
    "oecd": 1,
    "worldbank": 2,
    "who": 1,
    "unesco_uis": 1,
    "ilo": 1,
    "unpd": 1,
    "wvs": 1,
}
_SERIAL_HARVEST_FAMILIES: frozenset[str] = frozenset({"ckan"})
_SERIAL_HARVEST_SOURCES: frozenset[str] = frozenset(
    {
        "data_gov_ua_broad",
        "data_gov_ro_broad",
        "data_gov_md_broad",
        "data_gov_pl_broad",
    }
)
_OBSERVATION_PROGRESS_INTERVAL_SECONDS = 60.0
_FETCH_RESULT_CACHE_SIZE = 256
_OBSERVATION_UNSUPPORTED_EMPTY_THRESHOLD = 2
_OBSERVATION_WRITER_FLUSH_ROWS = 8_000
_OBSERVATION_WRITER_FLUSH_BYTES = 8 * 1024 * 1024
_OBSERVATION_WRITER_FLUSH_SECONDS = 5.0
_OBSERVATION_WRITER_IDLE_FLUSH_SECONDS = 0.25
_OBSERVATION_WRITER_CHECKPOINT_EVERY = 10
_OBSERVATION_WRITER_TRANSACTION_ROWS = 2_000
_OBSERVATION_WRITER_TRANSACTION_ITEMS = 8
_OBSERVATION_WRITER_MIN_MEMORY_LIMIT_BYTES = 4 * 1024 * 1024 * 1024
_OBSERVATION_WRITER_MAX_MEMORY_LIMIT_BYTES = 24 * 1024 * 1024 * 1024
_OBSERVATION_WRITER_MEMORY_LIMIT_FRACTION = 0.60
_CAPABILITY_NEGATIVE_STATUS_CODES = frozenset({404, 405})
_RATE_LIMITED_LOG_COUNTS: dict[str, int] = {}
_BULK_MATERIALIZATION_LOCKS: dict[str, asyncio.Lock] = {}
_ILO_INFERRED_DIMENSION_TOKENS: frozenset[str] = frozenset(
    {
        "AGE",
        "CAT",
        "CBR",
        "CCT",
        "CHL",
        "CUR",
        "DSB",
        "DUR",
        "EC2",
        "ECO",
        "EDU",
        "EST",
        "GEO",
        "HHT",
        "HOW",
        "IND",
        "INS",
        "JOB",
        "MJH",
        "MTS",
        "OC2",
        "OCU",
        "SEX",
        "STU",
    }
)


__OWNER_BOUND_PROXIES: dict[str, object] = {}


def __resolve_implementation_dependency(name: str, owner: str) -> object:
    """Resolve a split-module dependency without facade-global injection."""
    has_context_override, context_override = resolve_core_sources_compatibility_binding(
        f"{__package__}.{owner}", name
    )
    if has_context_override:
        return cast("object", context_override)
    override = globals().get(name)
    if override is not None and override is not __OWNER_BOUND_PROXIES.get(name):
        return override
    module = import_module(f"{__package__}.{owner}")
    return cast("object", getattr(module, name))


def __make_implementation_proxy[**P, R](name: str, owner: str) -> Callable[P, R]:
    """Create a lazy, owner-bound compatibility callable for this module."""

    def __proxy(*args: P.args, **kwargs: P.kwargs) -> R:
        implementation = __resolve_implementation_dependency(name, owner)
        return cast("Callable[P, R]", implementation)(*args, **kwargs)

    __OWNER_BOUND_PROXIES[name] = __proxy
    return cast("Callable[P, R]", globals().setdefault(name, __proxy))


_capability_dimension_values: Callable[..., object] = __make_implementation_proxy(
    "_capability_dimension_values", "validators"
)
_capability_snapshot_cache_key: Callable[..., object] = __make_implementation_proxy(
    "_capability_snapshot_cache_key", "writers"
)
_eurostat_filters_for_countries: Callable[..., object] = __make_implementation_proxy(
    "_eurostat_filters_for_countries", "transformers"
)
_infer_dimension_order_for_plan: Callable[..., object] = __make_implementation_proxy(
    "_infer_dimension_order_for_plan", "writers"
)
_load_json_dict: Callable[..., object] = __make_implementation_proxy(
    "_load_json_dict", "transformers"
)
_normalize_dimension_order: Callable[..., object] = __make_implementation_proxy(
    "_normalize_dimension_order", "writers"
)
_observation_countries: Callable[..., object] = __make_implementation_proxy(
    "_observation_countries", "transformers"
)
_observation_frequency_rank: Callable[..., object] = __make_implementation_proxy(
    "_observation_frequency_rank", "transformers"
)
_observation_shard_id: Callable[..., object] = __make_implementation_proxy(
    "_observation_shard_id", "validators"
)
_observation_time_window_years: Callable[..., object] = __make_implementation_proxy(
    "_observation_time_window_years", "validators"
)
_policy_attr: Callable[..., object] = __make_implementation_proxy("_policy_attr", "api")
_policy_bool_attr: Callable[..., object] = __make_implementation_proxy("_policy_bool_attr", "api")
_policy_int_attr: Callable[..., object] = __make_implementation_proxy("_policy_int_attr", "api")
_policy_optional_int_attr: Callable[..., object] = __make_implementation_proxy(
    "_policy_optional_int_attr", "api"
)
_policy_str_attr: Callable[..., object] = __make_implementation_proxy("_policy_str_attr", "api")
_sdmx_filters_for_countries: Callable[..., object] = __make_implementation_proxy(
    "_sdmx_filters_for_countries", "transformers"
)
_shard_prefers_async_fetch: Callable[..., object] = __make_implementation_proxy(
    "_shard_prefers_async_fetch", "validators"
)
_support_sketch_id: Callable[..., object] = __make_implementation_proxy(
    "_support_sketch_id", "writers"
)
_to_iso3: Callable[..., object] = __make_implementation_proxy("_to_iso3", "transformers")
_tokenize: Callable[..., object] = __make_implementation_proxy("_tokenize", "transformers")
_year_windows: Callable[..., object] = __make_implementation_proxy("_year_windows", "validators")


def _ensure_registry_tables(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_registry_datasets (
            dataset_id    VARCHAR PRIMARY KEY,
            provider      VARCHAR NOT NULL,
            title         VARCHAR NOT NULL,
            coverage_json VARCHAR NOT NULL,
            access_json   VARCHAR NOT NULL,
            update_freq   VARCHAR NOT NULL,
            last_updated  VARCHAR NOT NULL
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_variable_alignments (
            dataset_id     VARCHAR NOT NULL,
            raw_variable   VARCHAR NOT NULL,
            canonical_var  VARCHAR NOT NULL,
            method         VARCHAR NOT NULL,
            confidence     FLOAT NOT NULL,
            evidence       VARCHAR NOT NULL,
            is_proxy       BOOLEAN DEFAULT FALSE,
            proxy_penalty  FLOAT DEFAULT 0.0,
            PRIMARY KEY (dataset_id, raw_variable, canonical_var)
        );
        """
    )
    create_alignment_audit_table(con)
    create_alignment_review_basis_table(con)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS ds_observations (
            observation_id VARCHAR PRIMARY KEY,
            dataset_id     VARCHAR NOT NULL,
            raw_variable   VARCHAR NOT NULL,
            canonical_var  VARCHAR NOT NULL,
            country_code   VARCHAR NOT NULL,
            year           INTEGER,
            survey_year    INTEGER,
            wave           INTEGER,
            value          DOUBLE,
            condition_json VARCHAR DEFAULT '{}',
            acquisition_method VARCHAR DEFAULT NULL,
            source_watermark VARCHAR DEFAULT NULL,
            dataset_version VARCHAR DEFAULT NULL
        );
        """
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_registry_provider ON ds_registry_datasets(provider)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_va_canonical ON ds_variable_alignments(canonical_var)"
    )
    con.execute("CREATE INDEX IF NOT EXISTS idx_va_dataset ON ds_variable_alignments(dataset_id)")
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_alignment_audit_dataset ON ds_alignment_audit(dataset_id)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_country_year ON ds_observations(country_code, year)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_dataset_raw "
        "ON ds_observations(dataset_id, raw_variable)"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_obs_dedup "
        "ON ds_observations(dataset_id, raw_variable, country_code, year)"
    )
    _ensure_observation_provenance_columns(con)
    _ensure_observation_index_compatibility(con)


def _ensure_observation_provenance_columns(con: duckdb.DuckDBPyConnection) -> None:
    try:
        columns = {
            str(row[1]) for row in con.execute("PRAGMA table_info('ds_observations')").fetchall()
        }
    except Exception:
        return
    for column_name in ("acquisition_method", "source_watermark", "dataset_version"):
        if column_name in columns:
            continue
        con.execute(f"ALTER TABLE ds_observations ADD COLUMN {column_name} VARCHAR DEFAULT NULL")


def _ensure_observation_index_compatibility(con: duckdb.DuckDBPyConnection) -> None:
    try:
        indexes = con.execute(
            "SELECT index_name, is_unique FROM duckdb_indexes() WHERE table_name='ds_observations'"
        ).fetchall()
    except Exception:
        return
    for index_name, is_unique in indexes:
        if str(index_name or "") != "idx_obs_dedup" or not bool(is_unique):
            continue
        con.execute("DROP INDEX IF EXISTS idx_obs_dedup")
        con.execute(
            "CREATE INDEX IF NOT EXISTS idx_obs_dedup "
            "ON ds_observations(dataset_id, raw_variable, country_code, year)"
        )
        logger.warning(
            "Dropped legacy UNIQUE idx_obs_dedup to preserve condition-aware "
            "and multi-canonical observations"
        )
        break


def _load_catalog_transport_datasets(
    con: duckdb.DuckDBPyConnection,
    config: DatasetBatchConfig,
) -> list[CatalogTransportDataset]:
    tables = {
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'main'"
        ).fetchall()
    }
    if "ds_datasets" not in tables:
        return []

    dataset_columns = {
        str(row[1]) for row in con.execute("PRAGMA table_info('ds_datasets')").fetchall()
    }
    distribution_columns = (
        {str(row[1]) for row in con.execute("PRAGMA table_info('ds_distributions')").fetchall()}
        if "ds_distributions" in tables
        else set()
    )

    def _dataset_expr(column: str, fallback: str) -> str:
        return f"d.{column}" if column in dataset_columns else fallback

    def _distribution_expr(column: str, fallback: str) -> str:
        return f"dist.{column}" if column in distribution_columns else fallback

    if "ds_distributions" not in tables:
        distribution_join = ""
    elif "preferred_distribution_id" in dataset_columns and "id" in distribution_columns:
        distribution_join = (
            "LEFT JOIN ds_distributions AS dist ON dist.id = d.preferred_distribution_id"
        )
    elif "dataset_id" in distribution_columns:
        distribution_join = """
        LEFT JOIN LATERAL (
            SELECT *
            FROM ds_distributions AS src
            WHERE src.dataset_id = d.id
            ORDER BY COALESCE(src.quality_score, 0.0) DESC, src.id
            LIMIT 1
        ) AS dist ON TRUE
        """
    else:
        distribution_join = ""

    if config.promoted_sources:
        source_filter = sorted(set(config.promoted_sources))
    else:
        source_filter = sorted(_TRANSPORT_SOURCES)
    source_specs = {
        str(spec.name or "").strip().lower(): spec for spec in config.load_registry().sources
    }

    placeholders = ", ".join("?" for _ in source_filter)
    source_dataset_expr = _dataset_expr("source_dataset_id", "''")
    last_updated_expr = _dataset_expr(
        "last_updated", _dataset_expr("updated_at", "CURRENT_DATE::VARCHAR")
    )
    coverage_start_expr = _dataset_expr(
        "coverage_time_start", _dataset_expr("temporal_start", "''")
    )
    coverage_end_expr = _dataset_expr("coverage_time_end", _dataset_expr("temporal_end", "''"))
    source_locator_expr = _distribution_expr("source_locator", "''")
    # The interpolated SQL fragments come from the fixed schema mapping above;
    # source values remain bound parameters in the query execution below.
    query = f"""
        SELECT
            d.id,
            d.source,
            d.title,
            COALESCE(d.description, ''),
            COALESCE(
                NULLIF({source_dataset_expr}, ''),
                NULLIF(d.dataset_id, ''),
                d.id
            ),
            COALESCE({_dataset_expr("update_frequency", "''")}, ''),
            COALESCE({last_updated_expr}::VARCHAR, CURRENT_DATE::VARCHAR),
            json_object(
                'countries', COALESCE({_dataset_expr("coverage_countries", "[]")}, []),
                'regions', COALESCE({_dataset_expr("coverage_regions", "[]")}, []),
                'time_range',
                    CASE
                        WHEN COALESCE({coverage_start_expr}, '') != ''
                             OR COALESCE({coverage_end_expr}, '') != ''
                        THEN COALESCE({coverage_start_expr}, '')
                             || ':'
                             || COALESCE({coverage_end_expr}, '')
                        ELSE ''
                    END,
                'granularity', COALESCE({_dataset_expr("coverage_granularity", "''")}, 'annual')
            ) AS coverage_json,
            json_object(
                'access_type', 'open',
                'api_endpoint', COALESCE({_dataset_expr("access_api_endpoint", "''")}, ''),
                'bulk_download_url',
                    COALESCE({_dataset_expr("access_bulk_download_url", "''")}, ''),
                'license', COALESCE({_dataset_expr("access_license", "d.license")}, d.license, ''),
                'auth_required', COALESCE({_dataset_expr("access_auth_required", "FALSE")}, FALSE)
            ) AS access_json,
            COALESCE({_dataset_expr("execution_tier", "'transport_ready'")}, 'transport_ready'),
            COALESCE(d.variables, []),
            COALESCE(d.keywords, []),
            COALESCE(d.themes, []),
            COALESCE(d.polisyos_metrics, []),
            COALESCE({_distribution_expr("connector_type", "''")}, ''),
            COALESCE({_distribution_expr("profile_id", "''")}, ''),
            COALESCE(
                NULLIF({source_locator_expr}, ''),
                COALESCE(NULLIF({source_dataset_expr}, ''), NULLIF(d.dataset_id, ''), d.id)
            ),
            COALESCE(CAST({_distribution_expr("default_filters", "'{}'::JSON")} AS VARCHAR), '{{}}')
        FROM ds_datasets AS d
        {distribution_join}
        WHERE d.source IN ({placeholders})
    """  # noqa: S608
    rows = con.execute(query, source_filter).fetchall()
    if not rows:
        return []

    out: list[CatalogTransportDataset] = []
    for row in rows:
        source = str(row[1] or "")
        source_spec = source_specs.get(source.lower())
        execution_tier = str(
            row[9] or (source_spec.execution_tier if source_spec is not None else "transport_ready")
        )
        if execution_tier == "catalog" and source not in {"who", "unpd", "unesco_uis"}:
            continue
        coverage_json = str(row[7] or "{}")
        request_dataset_id = str(row[16] or "")
        connector_id = str(row[14] or "") or (
            str(source_spec.connector_id or "") if source_spec is not None else ""
        )
        profile_id = str(row[15] or "") or (
            str(source_spec.profile_id or "") if source_spec is not None else ""
        )
        out.append(
            CatalogTransportDataset(
                catalog_dataset_id=str(row[0]),
                source=source,
                title=str(row[2] or ""),
                description=str(row[3] or ""),
                source_dataset_id=str(row[4] or ""),
                update_frequency=_resolve_catalog_update_frequency(
                    source=source,
                    request_dataset_id=request_dataset_id,
                    title=str(row[2] or ""),
                    update_frequency=str(row[5] or ""),
                    coverage_json=coverage_json,
                ),
                last_updated=str(row[6] or ""),
                coverage_json=coverage_json,
                access_json=str(row[8] or "{}"),
                execution_tier=execution_tier,
                variables=tuple(str(value) for value in list(row[10] or [])),
                keywords=tuple(str(value) for value in list(row[11] or [])),
                themes=tuple(str(value) for value in list(row[12] or [])),
                polisyos_metrics=tuple(str(value) for value in list(row[13] or [])),
                connector_id=connector_id,
                profile_id=profile_id,
                request_dataset_id=request_dataset_id,
                default_filters=_load_json_dict(row[17]),
            )
        )
    return out


def _resolve_catalog_update_frequency(
    *,
    source: str,
    request_dataset_id: str,
    title: str,
    update_frequency: str,
    coverage_json: str,
) -> str:
    normalized_source = str(source or "").strip().lower()
    normalized_frequency = str(update_frequency or "").strip().lower()
    coverage = _load_json_dict(coverage_json)
    coverage_granularity = str(coverage.get("granularity") or "").strip().lower()
    if not normalized_frequency:
        if coverage_granularity in {
            "annual",
            "quarterly",
            "monthly",
            "weekly",
            "daily",
            "wave",
            "irregular",
        }:
            return coverage_granularity
        return ""
    if normalized_source != "eurostat" or normalized_frequency not in {"monthly", "quarterly"}:
        return normalized_frequency
    if _eurostat_request_id_suggests_subannual(request_dataset_id):
        return normalized_frequency
    lowered_title = str(title or "").strip().lower()
    if any(token in lowered_title for token in _EUROSTAT_SUBANNUAL_TITLE_TOKENS):
        return normalized_frequency
    if coverage_granularity in {"annual", "country-year", "yearly"}:
        return "annual"
    return normalized_frequency


def _eurostat_request_id_suggests_subannual(request_dataset_id: str) -> bool:
    normalized = str(request_dataset_id or "").strip().upper()
    if not normalized:
        return False
    if re.search(r"(^|[_$-])[MQ](\d+)?($|[_$-])", normalized):
        return True
    return len(normalized) >= 4 and normalized.endswith(("M", "Q"))


def _upsert_catalog_registry_datasets(
    con: duckdb.DuckDBPyConnection,
    datasets: list[CatalogTransportDataset],
) -> int:
    rows = [
        (
            item.catalog_dataset_id,
            item.source,
            item.title,
            item.coverage_json,
            item.access_json,
            item.update_frequency or "annual",
            item.last_updated or datetime.now(UTC).date().isoformat(),
        )
        for item in datasets
    ]
    if not rows:
        return 0
    con.executemany(
        "INSERT OR REPLACE INTO ds_registry_datasets "
        "(dataset_id, provider, title, coverage_json, access_json, update_freq, last_updated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    return len(rows)


def _build_catalog_alignments(
    datasets: list[CatalogTransportDataset],
    seed_path: Path,
) -> list[VariableAlignment]:
    seed_alignments = load_seed_alignments(seed_path)
    seed_by_var: dict[str, list[VariableAlignment]] = {}
    for item in seed_alignments:
        seed_by_var.setdefault(item.dataset_var.strip().upper(), []).append(item)

    best: dict[tuple[str, str, str], VariableAlignment] = {}
    for dataset in datasets:
        candidate_vars = _candidate_variables(dataset)
        dataset_text_tokens = _tokenize(
            " ".join((dataset.title, dataset.description, *candidate_vars, *dataset.keywords))
        )

        for raw_var in candidate_vars:
            for seed in seed_by_var.get(raw_var.strip().upper(), []):
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=seed.canonical_var,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=seed.method,
                        confidence=seed.confidence,
                        evidence=f"{seed.evidence};source={dataset.source}",
                        is_proxy=seed.is_proxy,
                        proxy_penalty=seed.proxy_penalty,
                    ),
                )

        for metric in dataset.polisyos_metrics:
            if metric in _CANONICAL_ROOTS:
                raw_var = dataset.source_dataset_id or (
                    candidate_vars[0] if candidate_vars else metric
                )
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=metric,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=AlignmentMethod.EXACT,
                        confidence=0.98,
                        evidence="metric_binding_direct_to_canonical_root",
                    ),
                )
            for proxy_alignment in metric_proxy_alignments(metric):
                raw_var = dataset.source_dataset_id or (
                    candidate_vars[0] if candidate_vars else metric
                )
                _remember_alignment(
                    best,
                    VariableAlignment(
                        canonical_var=proxy_alignment.canonical_var,
                        dataset_var=raw_var,
                        dataset_id=dataset.catalog_dataset_id,
                        method=AlignmentMethod.SEMANTIC,
                        confidence=proxy_alignment.confidence,
                        evidence=f"metric_binding_proxy:{metric}",
                        is_proxy=True,
                        proxy_penalty=proxy_alignment.proxy_penalty,
                    ),
                )

        semantic_candidates = [
            canonical_var
            for canonical_var in _CANONICAL_ROOTS
            if _tokenize(canonical_var.replace("_", " ")) & dataset_text_tokens
        ]
        if dataset.source in {
            "worldbank",
            "eurostat",
            "oecd",
            "ilo",
            "who",
            "unpd",
            "wvs",
            "unesco_uis",
        }:
            semantic_candidates.extend(
                metric for metric in dataset.polisyos_metrics if metric in _CANONICAL_ROOTS
            )
        semantic_candidates = sorted(set(semantic_candidates))[:20]
        for canonical_var in semantic_candidates:
            for alignment in align_semantic(
                canonical_var=canonical_var,
                dataset_id=dataset.catalog_dataset_id,
                candidates=candidate_vars,
                threshold=0.45,
                max_results=3,
            ):
                if alignment.confidence < 0.55:
                    continue
                _remember_alignment(best, alignment)

    return list(best.values())


def _candidate_variables(dataset: CatalogTransportDataset) -> list[str]:
    values: list[str] = []
    for item in (dataset.source_dataset_id, *dataset.variables):
        text = str(item or "").strip()
        if text and text not in values:
            values.append(text)
    if not values and dataset.polisyos_metrics:
        values.extend(metric for metric in dataset.polisyos_metrics if metric)
    return values or [dataset.catalog_dataset_id]


def _remember_alignment(
    best: dict[tuple[str, str, str], VariableAlignment],
    alignment: VariableAlignment,
) -> None:
    key = (alignment.dataset_id, alignment.dataset_var, alignment.canonical_var)
    current = best.get(key)
    method_rank = {
        AlignmentMethod.EXACT: 0,
        AlignmentMethod.META_ANALYTIC: 1,
        AlignmentMethod.SEMANTIC: 2,
    }
    if current is None:
        best[key] = alignment
        return
    candidate_rank = method_rank.get(alignment.method, 9)
    current_rank = method_rank.get(current.method, 9)
    if candidate_rank < current_rank or (
        candidate_rank == current_rank and alignment.confidence > current.confidence
    ):
        best[key] = alignment


def _upsert_catalog_alignments(
    con: duckdb.DuckDBPyConnection,
    alignments: list[VariableAlignment],
    *,
    affected_dataset_ids: Iterable[str] = (),
) -> int:
    rows = [
        (
            item.dataset_id,
            item.dataset_var,
            item.canonical_var,
            item.method.value,
            item.confidence,
            item.evidence,
            item.is_proxy,
            item.proxy_penalty,
        )
        for item in alignments
    ]
    dataset_ids = sorted(
        {str(value) for value in affected_dataset_ids if str(value)}
        | {item.dataset_id for item in alignments}
    )
    if dataset_ids:
        con.execute(
            "DELETE FROM ds_variable_alignments WHERE dataset_id = ANY(?)",
            [dataset_ids],
        )
    if rows:
        con.executemany(
            "INSERT INTO ds_variable_alignments "
            "(dataset_id, raw_variable, canonical_var, method, confidence, "
            "evidence, is_proxy, proxy_penalty) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def _bind_catalog_alignment_review_basis(
    datasets: list[CatalogTransportDataset],
    alignments: list[VariableAlignment],
    *,
    profile_material_input_identity: str | None,
    profile_input_coverage: object,
) -> tuple[list[VariableAlignment], _AlignmentReviewBasisMap]:
    """Build separate operational basis rows for complete producer groups.

    Producer-authored alignment evidence is returned unchanged. A basis row is
    emitted only when the full selected dataset, candidate group, material
    identity, and profile coverage are content-bound and reusable.
    """
    from polisyos.data_forge.domains.catalog.batch.config import parse_profile_input_coverage

    coverage_state, profiles = parse_profile_input_coverage(profile_input_coverage)
    identity_is_content_bound = bool(
        isinstance(profile_material_input_identity, str)
        and re.fullmatch(r"[0-9a-f]{64}", profile_material_input_identity)
    )
    datasets_by_id: dict[str, CatalogTransportDataset | None] = {}
    for dataset in datasets:
        dataset_id = dataset.catalog_dataset_id
        if dataset_id in datasets_by_id:
            datasets_by_id[dataset_id] = None
        else:
            datasets_by_id[dataset_id] = dataset

    grouped: dict[tuple[str, str], list[VariableAlignment]] = {}
    for alignment in alignments:
        grouped.setdefault((alignment.dataset_id, alignment.dataset_var), []).append(alignment)

    basis_records: _AlignmentReviewBasisMap = {}
    for (dataset_id, dataset_var), candidates in grouped.items():
        dataset = datasets_by_id.get(dataset_id)
        profile_state = (
            profiles.get(dataset.profile_id)
            if profiles is not None and dataset is not None
            else None
        )
        basis_available = (
            identity_is_content_bound
            and coverage_state == "established"
            and dataset is not None
            and bool(dataset.profile_id)
            and profile_state == "none"
        )
        if basis_available:
            payload = {
                "version": _ALIGNMENT_REVIEW_BASIS_VERSION,
                "profile_material_input_identity": profile_material_input_identity,
                "profile_input_coverage_state": "none",
                "selected_profile_id": dataset.profile_id,
                "selected_dataset": {
                    item.name: getattr(dataset, item.name) for item in fields(dataset)
                },
                "alignment_group": [
                    item.model_dump(mode="json")
                    for item in sorted(candidates, key=lambda candidate: candidate.canonical_var)
                ],
            }
            basis_json = _canonical_alignment_review_basis_json(payload)
            basis_sha256 = hashlib.sha256(basis_json.encode("utf-8")).hexdigest()
            record = _AlignmentReviewBasisRecord(
                dataset_id=dataset_id,
                raw_variable=dataset_var,
                basis_version=_ALIGNMENT_REVIEW_BASIS_VERSION,
                basis_json=basis_json,
                basis_sha256=basis_sha256,
            )
            if _alignment_review_basis_record_is_valid(record):
                basis_records[(dataset_id, dataset_var)] = record
    return list(alignments), basis_records


def _canonical_alignment_review_basis_json(payload: dict[str, object]) -> str:
    """Serialize one operational basis deterministically for storage and hashing."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _alignment_review_basis_record_is_valid(
    record: _AlignmentReviewBasisRecord,
) -> bool:
    """Verify the sidecar record's complete typed payload and recomputed digest."""
    if record.basis_version != _ALIGNMENT_REVIEW_BASIS_VERSION or not re.fullmatch(
        r"[0-9a-f]{64}", record.basis_sha256
    ):
        return False
    try:
        payload = json.loads(record.basis_json)
    except (TypeError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "profile_material_input_identity",
        "profile_input_coverage_state",
        "selected_profile_id",
        "selected_dataset",
        "alignment_group",
    }:
        return False
    if (
        payload.get("version") != record.basis_version
        or payload.get("profile_input_coverage_state") != "none"
        or not isinstance(payload.get("selected_profile_id"), str)
        or not payload["selected_profile_id"].strip()
        or not isinstance(payload.get("profile_material_input_identity"), str)
        or re.fullmatch(r"[0-9a-f]{64}", payload["profile_material_input_identity"]) is None
        or not isinstance(payload.get("selected_dataset"), dict)
        or not isinstance(payload.get("alignment_group"), list)
        or not payload["alignment_group"]
    ):
        return False
    dataset = payload["selected_dataset"]
    dataset_fields = fields(CatalogTransportDataset)
    if set(dataset) != {item.name for item in dataset_fields}:
        return False
    tuple_fields = {"variables", "keywords", "themes", "polisyos_metrics"}
    for item in dataset_fields:
        value = dataset[item.name]
        if item.name in tuple_fields:
            if not isinstance(value, list) or not all(isinstance(member, str) for member in value):
                return False
        elif item.name == "default_filters":
            if not isinstance(value, dict) or not all(
                isinstance(key, str)
                and isinstance(members, list)
                and all(isinstance(member, str) for member in members)
                for key, members in value.items()
            ):
                return False
        elif not isinstance(value, str):
            return False
    if (
        dataset.get("catalog_dataset_id") != record.dataset_id
        or dataset.get("profile_id") != payload["selected_profile_id"]
    ):
        return False
    normalized_group: list[dict[str, object]] = []
    canonical_vars: set[str] = set()
    for raw_alignment in payload["alignment_group"]:
        if not isinstance(raw_alignment, dict) or set(raw_alignment) != set(
            VariableAlignment.model_fields
        ):
            return False
        try:
            alignment = VariableAlignment.model_validate(raw_alignment)
        except Exception:
            return False
        if (
            alignment.dataset_id != record.dataset_id
            or alignment.dataset_var != record.raw_variable
            or alignment.canonical_var in canonical_vars
        ):
            return False
        canonical_vars.add(alignment.canonical_var)
        normalized_group.append(alignment.model_dump(mode="json"))
    if normalized_group != sorted(normalized_group, key=lambda item: str(item["canonical_var"])):
        return False
    canonical_json = _canonical_alignment_review_basis_json(payload)
    return (
        record.basis_json == canonical_json
        and hashlib.sha256(canonical_json.encode("utf-8")).hexdigest() == record.basis_sha256
    )


def _alignment_model_storage_profile(
    con: duckdb.DuckDBPyConnection,
) -> tuple[tuple[str, ...], dict[str, str]]:
    """Derive the persisted alignment projection and types from the producer DTO."""
    columns = {name: name for name in VariableAlignment.model_fields if name != "dataset_var"}
    columns["dataset_var"] = "raw_variable"
    profile: dict[str, str] = {}
    for field_name, field in VariableAlignment.model_fields.items():
        annotation = field.annotation
        if isinstance(annotation, type) and issubclass(annotation, str):
            sql_type = "VARCHAR"
        elif annotation is float:
            sql_type = "FLOAT"
        elif annotation is bool:
            sql_type = "BOOLEAN"
        else:
            raise RuntimeError(
                f"unsupported VariableAlignment field type for {field_name!r}: {annotation!r}"
            )
        profile[columns[field_name]] = sql_type

    actual = con.execute("PRAGMA table_info('ds_variable_alignments')").fetchall()
    actual_names = tuple(str(row[1]) for row in actual)
    expected_names = set(profile)
    if len(actual_names) != len(expected_names) or set(actual_names) != expected_names:
        raise RuntimeError(
            "ds_variable_alignments physical columns do not match the complete "
            "VariableAlignment producer model"
        )
    for row in actual:
        name = str(row[1])
        if str(row[2]).upper() != profile[name]:
            raise RuntimeError(f"ds_variable_alignments has unsupported physical type for {name!r}")
    return actual_names, profile


def _alignment_review_group_status(
    con: duckdb.DuckDBPyConnection,
    alignments: list[VariableAlignment],
    *,
    affected_dataset_ids: Iterable[str] = (),
    candidate_review_bases: _AlignmentReviewBasisMap | None = None,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Compare complete old/new model groups and their independently stored basis."""
    columns, sql_types = _alignment_model_storage_profile(con)
    dataset_ids = sorted(
        {str(value) for value in affected_dataset_ids if str(value)}
        | {alignment.dataset_id for alignment in alignments}
    )
    incoming: dict[tuple[str, str], list[VariableAlignment]] = {}
    for alignment in alignments:
        incoming.setdefault((alignment.dataset_id, alignment.dataset_var), []).append(alignment)

    existing: dict[tuple[str, str], list[tuple[object, ...]]] = {}
    if dataset_ids:
        selected_columns = ", ".join(f'"{column}"' for column in columns)
        persisted_query = (
            "SELECT "  # noqa: S608 - identifiers are derived from the exact producer model.
            + selected_columns
            + " FROM ds_variable_alignments WHERE dataset_id = ANY(?) "
            'ORDER BY "dataset_id", "raw_variable", "canonical_var"'
        )
        persisted = con.execute(
            persisted_query,
            [dataset_ids],
        ).fetchall()
        dataset_index = columns.index("dataset_id")
        variable_index = columns.index("raw_variable")
        for row in persisted:
            group_key = (str(row[dataset_index]), str(row[variable_index]))
            existing.setdefault(group_key, []).append(tuple(row))

    candidate_bases = candidate_review_bases or {}
    existing_bases: _AlignmentReviewBasisMap = {}
    existing_basis_keys: set[tuple[str, str]] = set()
    if dataset_ids:
        resolve_alignment_review_basis_schema(con)
        basis_rows = con.execute(
            "SELECT dataset_id, raw_variable, basis_version, basis_json, basis_sha256 "
            "FROM ds_alignment_review_basis WHERE dataset_id = ANY(?)",
            [dataset_ids],
        ).fetchall()
        for row in basis_rows:
            dataset_id, raw_variable = row[0], row[1]
            if not isinstance(dataset_id, str) or not isinstance(raw_variable, str):
                continue
            group_key = (dataset_id, raw_variable)
            existing_basis_keys.add(group_key)
            if not all(isinstance(value, str) for value in row):
                continue
            record = _AlignmentReviewBasisRecord(
                dataset_id=row[0],
                raw_variable=row[1],
                basis_version=row[2],
                basis_json=row[3],
                basis_sha256=row[4],
            )
            if _alignment_review_basis_record_is_valid(record):
                existing_bases[group_key] = record

    candidate_context_valid: dict[tuple[str, str], bool] = {}
    column_aliases = ", ".join(f'"{column}"' for column in columns)
    cast_columns = ", ".join(
        f'CAST("incoming"."{column}" AS {sql_types[column]}) AS "{column}"' for column in columns
    )
    for group_key, candidates in incoming.items():
        ordered = sorted(candidates, key=lambda candidate: candidate.canonical_var)
        unique_candidates = len({item.canonical_var for item in ordered}) == len(ordered)
        basis = candidate_bases.get(group_key)
        candidate_context_valid[group_key] = (
            unique_candidates
            and basis is not None
            and _alignment_review_basis_record_is_valid(basis)
        )

    candidate_rows: dict[tuple[str, str], list[tuple[object, ...]]] = {}
    ordered_alignments = sorted(
        alignments,
        key=lambda item: (item.dataset_id, item.dataset_var, item.canonical_var),
    )
    for start in range(0, len(ordered_alignments), _ALIGNMENT_AUDIT_WRITE_BATCH_SIZE):
        batch = ordered_alignments[start : start + _ALIGNMENT_AUDIT_WRITE_BATCH_SIZE]
        values_sql = ", ".join("(" + ", ".join("?" for _column in columns) + ")" for _item in batch)
        parameters = [
            item.model_dump(mode="json").get("dataset_var" if column == "raw_variable" else column)
            for item in batch
            for column in columns
        ]
        normalized_query = (
            f"SELECT {cast_columns} FROM (VALUES {values_sql}) "  # noqa: S608 - columns/types are derived from the exact producer model.
            f"AS incoming({column_aliases})"
        )
        normalized_rows = con.execute(normalized_query, parameters).fetchall()
        for item, normalized in zip(batch, normalized_rows, strict=True):
            group_key = (item.dataset_id, item.dataset_var)
            candidate_rows.setdefault(group_key, []).append(tuple(normalized))

    all_groups = set(existing) | set(incoming) | existing_basis_keys | set(candidate_bases)
    reusable: set[tuple[str, str]] = set()
    changed: set[tuple[str, str]] = set()
    for group_key in all_groups:
        old_rows = existing.get(group_key, [])
        new_rows = candidate_rows.get(group_key, [])
        is_unchanged = (
            group_key in incoming
            and candidate_context_valid.get(group_key, False)
            and old_rows == new_rows
            and existing_bases.get(group_key) == candidate_bases.get(group_key)
        )
        (reusable if is_unchanged else changed).add(group_key)
    return reusable, changed


def _upsert_alignment_audit(
    con: duckdb.DuckDBPyConnection,
    alignments: list[VariableAlignment],
    *,
    affected_dataset_ids: Iterable[str] = (),
    candidate_review_bases: _AlignmentReviewBasisMap | None = None,
) -> int:
    rows = _build_alignment_audit_rows(alignments)
    scope_ids = {str(value) for value in affected_dataset_ids if str(value)} | {
        item.dataset_id for item in alignments
    }
    if not rows and not scope_ids:
        return 0

    schema_profile = resolve_alignment_audit_schema_profile(con)
    schema_columns = alignment_audit_columns(schema_profile)
    table_columns = tuple(column.name for column in schema_columns)
    expected_columns = set(table_columns)
    if any(set(row) != expected_columns for row in rows):
        raise RuntimeError(
            "alignment audit producer rows must cover the complete ds_alignment_audit schema"
        )

    reusable_groups, changed_groups = _alignment_review_group_status(
        con,
        alignments,
        affected_dataset_ids=scope_ids,
        candidate_review_bases=candidate_review_bases,
    )
    if changed_groups:
        con.executemany(
            "UPDATE ds_alignment_audit SET reviewed = FALSE, reviewer_override = NULL "
            "WHERE dataset_id = ? AND raw_variable = ?",
            sorted(changed_groups),
        )
    if not rows:
        return 0

    column_list_sql = ", ".join(table_columns)
    placeholders = ", ".join("?" for _column in schema_columns)
    insert_sql = (
        "INSERT OR REPLACE INTO ds_alignment_audit "  # noqa: S608 - names are from the closed schema profile.
        f"({column_list_sql}) VALUES ({placeholders})"
    )
    audit_id_column = table_columns.index("audit_id")
    for start in range(0, len(rows), _ALIGNMENT_AUDIT_WRITE_BATCH_SIZE):
        batch = rows[start : start + _ALIGNMENT_AUDIT_WRITE_BATCH_SIZE]
        existing_rows = con.execute(
            "SELECT * FROM ds_alignment_audit WHERE audit_id = ANY(?)",
            [[row["audit_id"] for row in batch]],
        ).fetchall()
        normalized_values_sql = ", ".join(
            "(" + ", ".join(f"CAST(? AS {column.sql_type})" for column in schema_columns) + ")"
            for _row in batch
        )
        normalized_rows = con.execute(
            # Types come from one of the canonical source-qualified schema profiles.
            f"SELECT * FROM (VALUES {normalized_values_sql}) AS incoming",  # noqa: S608
            [row[column] for row in batch for column in table_columns],
        ).fetchall()
        existing_by_id = {
            record[audit_id_column]: dict(zip(table_columns, record, strict=True))
            for record in existing_rows
        }
        persisted_rows: list[tuple[object, ...]] = []
        for row, normalized_record in zip(batch, normalized_rows, strict=True):
            existing = existing_by_id.get(row["audit_id"])
            candidate = dict(zip(table_columns, normalized_record, strict=True))
            review_group = (str(row["dataset_id"]), str(row["raw_variable"]))
            if (
                existing is not None
                and review_group in reusable_groups
                and _alignment_audit_rows_semantically_equal(existing, candidate)
            ):
                previous_resolution_time = existing.get("resolved_at")
                if isinstance(previous_resolution_time, str) and previous_resolution_time.strip():
                    row["resolved_at"] = previous_resolution_time
                for field in _ALIGNMENT_AUDIT_REVIEW_FIELDS:
                    row[field] = existing[field]
            persisted_rows.append(tuple(row[column] for column in table_columns))
        con.executemany(insert_sql, persisted_rows)
    return len(rows)


def _replace_catalog_alignment_review_bases(
    con: duckdb.DuckDBPyConnection,
    *,
    affected_dataset_ids: Iterable[str],
    candidate_review_bases: _AlignmentReviewBasisMap,
) -> int:
    """Replace internal basis rows for affected catalog datasets after comparison."""
    resolve_alignment_review_basis_schema(con)
    dataset_ids = sorted({str(value) for value in affected_dataset_ids if str(value)})
    if not dataset_ids:
        dataset_ids = sorted({record.dataset_id for record in candidate_review_bases.values()})
    for group_key, record in candidate_review_bases.items():
        if group_key != (record.dataset_id, record.raw_variable):
            raise RuntimeError("alignment review basis key does not match its complete group")
        if record.dataset_id not in dataset_ids or not _alignment_review_basis_record_is_valid(
            record
        ):
            raise RuntimeError("alignment review basis candidate is malformed or out of scope")
    if dataset_ids:
        con.execute(
            "DELETE FROM ds_alignment_review_basis WHERE dataset_id = ANY(?)", [dataset_ids]
        )
    rows = [
        (
            record.dataset_id,
            record.raw_variable,
            record.basis_version,
            record.basis_json,
            record.basis_sha256,
        )
        for _group_key, record in sorted(candidate_review_bases.items())
        if record.dataset_id in dataset_ids
    ]
    if rows:
        con.executemany(
            "INSERT INTO ds_alignment_review_basis "
            "(dataset_id, raw_variable, basis_version, basis_json, basis_sha256) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
    return len(rows)


def _alignment_audit_rows_semantically_equal(
    existing: dict[str, object],
    candidate: dict[str, object],
) -> bool:
    """Compare complete producer rows without review annotations or resolution time."""
    if set(existing) != set(candidate):
        return False
    producer_fields = (
        set(existing) - _ALIGNMENT_AUDIT_OPERATIONAL_FIELDS - _ALIGNMENT_AUDIT_REVIEW_FIELDS
    )
    return all(existing[field] == candidate[field] for field in producer_fields)


def _build_alignment_audit_rows(
    alignments: list[VariableAlignment],
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[VariableAlignment]] = {}
    for alignment in alignments:
        grouped.setdefault((alignment.dataset_id, alignment.dataset_var), []).append(alignment)

    resolved_at = datetime.now(UTC).isoformat()
    rows: list[dict[str, object]] = []
    for candidates in grouped.values():
        ranked = sorted(
            candidates,
            key=lambda item: (
                -calibrate_alignment_confidence(item),
                -float(item.confidence),
                item.canonical_var,
            ),
        )
        for alignment in ranked:
            alternatives = [
                {
                    "canonical_variable": candidate.canonical_var,
                    "method": candidate.method.value,
                    "raw_confidence": float(candidate.confidence),
                    "calibrated_confidence": calibrate_alignment_confidence(candidate),
                }
                for candidate in ranked
                if candidate.canonical_var != alignment.canonical_var
            ][:3]
            audit_id = hashlib.sha256(
                f"{alignment.dataset_id}|{alignment.dataset_var}|{alignment.canonical_var}".encode()
            ).hexdigest()[:24]
            rows.append(
                {
                    "audit_id": audit_id,
                    "dataset_id": alignment.dataset_id,
                    "raw_variable": alignment.dataset_var,
                    "canonical_variable": alignment.canonical_var,
                    "method": alignment.method.value,
                    "raw_confidence": float(alignment.confidence),
                    "calibrated_confidence": calibrate_alignment_confidence(alignment),
                    "alternatives_json": json.dumps(alternatives, ensure_ascii=False),
                    "resolved_at": resolved_at,
                    "reviewed": False,
                    "reviewer_override": None,
                }
            )
    return rows


def _build_catalog_observation_plans(
    datasets: list[CatalogTransportDataset],
    alignments: list[VariableAlignment],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationPlan]:
    by_dataset = {item.catalog_dataset_id: item for item in datasets}
    plans: list[ObservationPlan] = []
    seen: set[tuple[str, str, str]] = set()
    preflight_sources = {item.strip().lower() for item in config.preflight_sources if item.strip()}
    for alignment in alignments:
        dataset = by_dataset.get(alignment.dataset_id)
        if dataset is None:
            continue
        if dataset.source not in _TRANSPORT_SOURCES:
            continue
        if preflight_sources and dataset.source.lower() not in preflight_sources:
            continue
        if not _supports_observation_ingest(dataset, alignment):
            continue
        if alignment.confidence < 0.55:
            continue
        request_dataset_id = (
            dataset.request_dataset_id or dataset.source_dataset_id or alignment.dataset_var
        )
        if not request_dataset_id:
            continue
        key = (dataset.catalog_dataset_id, alignment.dataset_var, alignment.canonical_var)
        if key in seen:
            continue
        seen.add(key)
        plans.append(
            ObservationPlan(
                dataset_id=dataset.catalog_dataset_id,
                source=dataset.source,
                raw_variable=alignment.dataset_var,
                canonical_var=alignment.canonical_var,
                connector_id=dataset.connector_id,
                profile_id=dataset.profile_id,
                request_dataset_id=request_dataset_id,
                default_filters=dataset.default_filters,
                update_frequency=dataset.update_frequency or "annual",
                source_watermark=dataset.last_updated or "",
                dataset_version=request_dataset_id,
            )
        )
    return _limit_observation_plans(plans, datasets, config=config)


def _supports_observation_ingest(
    dataset: CatalogTransportDataset,
    alignment: VariableAlignment,
) -> bool:
    source = str(dataset.source or "").strip().lower()
    if source != "worldbank":
        return True
    if dataset.connector_id and dataset.connector_id != "worldbank.wdi":
        return False
    if dataset.profile_id and dataset.profile_id != "worldbank_wdi":
        return False
    if dataset.polisyos_metrics:
        return True
    return alignment.method in {AlignmentMethod.EXACT, AlignmentMethod.META_ANALYTIC}


def _observation_plan_limit_per_source(config: DatasetBatchConfig) -> int | None:
    if config.preflight_only or config.run_profile == "preflight_core":
        return 2
    if not config.is_sampled_run:
        return None
    base = max(int(config.max_datasets_per_source), 1)
    return max(base, min(base + 2, 6))


def _observation_failure_budget_per_source(config: DatasetBatchConfig) -> int | None:
    if config.is_sampled_run:
        capped = _observation_plan_limit_per_source(config) or 1
        return max(2, min(capped, 4))
    return None


# High-coverage indicators known to have broad country/year data.
# Used to prioritise preflight plan selection so we pick indicators
# that will actually return rows, instead of sorting by hashed dataset_id
# (which is effectively random and caused WHO preflight failures).
_PREFLIGHT_HIGH_COVERAGE_INDICATORS: dict[str, frozenset[str]] = {
    "who": frozenset(
        {
            "WHOSIS_000001",  # Life expectancy at birth
            "WHOSIS_000002",  # Healthy life expectancy (HALE)
            "MDG_0000000001",  # Under-five mortality rate
            "NCD_BMI_30A",  # Prevalence of obesity
            "SA_0000001688",  # Total alcohol per capita consumption
            "WHS7_104",  # Infant mortality rate
            "WHS9_95",  # Maternal mortality ratio
            "NCD_CCS_Diab",  # Diabetes prevalence
        }
    ),
    "unesco_uis": frozenset(
        {
            "CR.1",  # Completion rate, primary
            "SE.ADT.LITR.ZS",  # Adult literacy rate
            "UIS.NERA.1",  # Net enrolment rate, primary
        }
    ),
    "wvs": frozenset(
        {
            "A165",  # Social trust (most people can be trusted)
            "E069_17",  # Confidence: Justice System/Courts
            "A009",  # State of health (subjective)
            "E117",  # Having a democratic political system
            "E035",  # Income equality
            "Y022",  # Welzel equality sub-index
        }
    ),
    "worldbank": frozenset(
        {
            "NY.GDP.PCAP.CD",  # GDP per capita
            "SP.DYN.LE00.IN",  # Life expectancy at birth
            "SE.ADT.LITR.ZS",  # Adult literacy rate
            "SL.UEM.TOTL.ZS",  # Unemployment total
            "SI.POV.GINI",  # GINI index
            "SH.XPD.CHEX.GD.ZS",  # Health expenditure (% of GDP)
        }
    ),
}


def _preflight_indicator_priority(plan: ObservationPlan) -> int:
    """Return 0 for known high-coverage indicators, 1 otherwise."""
    high_coverage = _PREFLIGHT_HIGH_COVERAGE_INDICATORS.get(plan.source)
    if high_coverage and plan.request_dataset_id in high_coverage:
        return 0
    return 1


def _limit_observation_plans(
    plans: list[ObservationPlan],
    datasets: list[CatalogTransportDataset],
    *,
    config: DatasetBatchConfig,
) -> list[ObservationPlan]:
    if not plans:
        return []

    limit = _observation_plan_limit_per_source(config)
    dataset_rank = {
        item.catalog_dataset_id: (
            0 if item.execution_tier == "transport_ready" else 1,
            0 if item.polisyos_metrics else 1,
            item.catalog_dataset_id,
        )
        for item in datasets
    }
    ordered = sorted(
        plans,
        key=lambda item: (
            item.source,
            _preflight_indicator_priority(item),
            dataset_rank.get(item.dataset_id, (9, 9, item.dataset_id)),
            _observation_frequency_rank(item.update_frequency),
            item.canonical_var,
            item.raw_variable,
        ),
    )
    if limit is None:
        return ordered

    grouped: dict[str, list[ObservationPlan]] = {}
    for plan in ordered:
        grouped.setdefault(plan.source, []).append(plan)

    # Collect canonical vars that are important for transport benchmark.
    # Prioritise plans that cover canonical vars not yet covered by other sources.
    transport_benchmark_vars: frozenset[str] = frozenset(
        {
            "gdp_per_capita",
            "unemployment_rate",
            "inflation",
            "migration",
            "health_outcomes",
            "education_outcomes",
            "social_trust",
            "poverty_rate",
            "labor_force_participation",
            "institutional_quality",
        }
    )
    covered_transport_vars: set[str] = set()

    out: list[ObservationPlan] = []
    trimmed = 0
    for _source, source_plans in grouped.items():
        selected: list[ObservationPlan] = []
        seen_keys: set[tuple[str, str, str]] = set()
        seen_canonical: set[str] = set()

        # First pass: prefer plans covering uncovered transport vars.
        transport_first = sorted(
            source_plans,
            key=lambda p: (
                0
                if (
                    p.canonical_var in transport_benchmark_vars
                    and p.canonical_var not in covered_transport_vars
                )
                else 1,
                _preflight_indicator_priority(p),
                p.canonical_var,
            ),
        )
        for plan in transport_first:
            if plan.canonical_var in seen_canonical:
                continue
            selected.append(plan)
            seen_canonical.add(plan.canonical_var)
            seen_keys.add((plan.dataset_id, plan.raw_variable, plan.canonical_var))
            if len(selected) >= limit:
                break

        if len(selected) < limit:
            for plan in source_plans:
                key = (plan.dataset_id, plan.raw_variable, plan.canonical_var)
                if key in seen_keys:
                    continue
                selected.append(plan)
                seen_keys.add(key)
                if len(selected) >= limit:
                    break

        for plan in selected:
            covered_transport_vars.add(plan.canonical_var)
        out.extend(selected)
        trimmed += max(len(source_plans) - len(selected), 0)
    if trimmed:
        logger.info(
            "Trimmed observation plans for sampled run: kept {} of {} plans (per-source limit={})",
            len(out),
            len(ordered),
            limit,
        )
    return out


def _observation_mode_phases(config: DatasetBatchConfig) -> tuple[str, ...]:
    mode = str(getattr(config, "observation_mode", "all") or "all").strip().lower()
    if mode == "core":
        return ("publishable_core",)
    if mode == "backfill":
        return ("long_tail_backfill",)
    return ("publishable_core", "long_tail_backfill")


def _source_runtime_lane_count(
    *,
    source: str,
    policy: SourceExecutionPolicy,
) -> int:
    configured = max(1, _policy_int_attr(policy, "max_concurrency", 1))
    preferred = _SOURCE_LANE_DEFAULTS.get(str(source or "").strip().lower())
    if preferred is None:
        return configured
    return max(1, min(configured, int(preferred)))


def _recommended_transport_for_plan(
    plan: ObservationPlan,
    *,
    phase: str,
    policy: SourceExecutionPolicy,
    capability: DatasetCapabilitySnapshot | None,
    config: DatasetBatchConfig,
) -> str:
    source = str(plan.source or "").strip().lower()
    preferred_transport = (
        _policy_attr(policy, "preferred_core_transport", None)
        if phase == "publishable_core"
        else _policy_attr(policy, "preferred_backfill_transport", None)
    ) or _policy_str_attr(policy, "preferred_transport", "default")
    if source == "wvs":
        return "local_bulk_file"
    if source == "worldbank":
        return str(preferred_transport or "api_grouped")
    if source == "who":
        return str(preferred_transport or "api_grouped")
    if source == "unesco_uis":
        if phase == "long_tail_backfill" and _policy_attr(policy, "bulk_download_url", None):
            return "bulk_file"
        return str(preferred_transport or "api_grouped")
    if source == "unpd":
        return str(preferred_transport or "api_grouped")
    if source in {"oecd", "ilo"}:
        if (
            source == "ilo"
            and phase == "long_tail_backfill"
            and _policy_attr(policy, "bulk_download_url", None)
        ):
            return "bulk_file"
        return str(preferred_transport or "api_grouped")
    if source == "eurostat":
        if phase == "long_tail_backfill" and _policy_attr(policy, "bulk_download_url", None):
            return "bulk_file"
        if _shard_prefers_async_fetch(
            ObservationShard(
                shard_id="transport_probe",
                plan=plan,
                country_code=None,
                country_codes=_observation_countries(source, config=config),
                start_year=config.resolved_year_window[0],
                end_year=config.resolved_year_window[1],
                filters=dict(plan.default_filters),
            ),
            snapshot=capability,
            policy=policy,
            config=config,
        ):
            return "api_async"
        if (
            _policy_bool_attr(policy, "supports_async_fetch", False)
            and source == "eurostat"
            and not config.is_sampled_run
        ):
            return str(preferred_transport or "api_sync")
    return str(
        (
            capability.preferred_transport
            if capability is not None and getattr(capability, "preferred_transport", None)
            else preferred_transport
        )
        or "default"
    )


def _transport_for_phase(sketch: SupportSketch, *, phase: str) -> str:
    if phase == "long_tail_backfill":
        return str(
            sketch.recommended_backfill_transport or sketch.recommended_core_transport or "default"
        )
    return str(
        sketch.recommended_core_transport or sketch.recommended_backfill_transport or "default"
    )


def _country_supported_by_capability(country_code: str, allowed_values: tuple[str, ...]) -> bool:
    if not allowed_values:
        return True
    iso2 = str(country_code or "").strip().upper()
    iso3 = _to_iso3(iso2)
    numeric = iso2_to_numeric(iso2) or ""
    allowed = {str(value).strip().upper() for value in allowed_values if str(value).strip()}
    return iso2 in allowed or iso3 in allowed or numeric in allowed


def _supported_countries_for_plan(
    plan: ObservationPlan,
    *,
    config: DatasetBatchConfig,
    capability: DatasetCapabilitySnapshot | None,
) -> tuple[str, ...]:
    countries = _observation_countries(plan.source, config=config)
    allowed = _capability_dimension_values(capability, "geo", "country", "ref_area")
    if not allowed:
        return countries
    return tuple(
        country for country in countries if _country_supported_by_capability(country, allowed)
    )


def _support_time_range_for_plan(
    plan: ObservationPlan,
    *,
    config: DatasetBatchConfig,
) -> tuple[int, int]:
    if plan.source == "wvs":
        return (1981, 2023)
    return config.resolved_year_window


def _build_support_sketches(
    plans: list[ObservationPlan],
    *,
    config: DatasetBatchConfig,
    plan_capabilities: dict[str, DatasetCapabilitySnapshot | None],
    source_policies: dict[str, SourceExecutionPolicy],
) -> dict[str, SupportSketch]:
    sketches: dict[str, SupportSketch] = {}
    for plan in plans:
        capability = plan_capabilities.get(_capability_snapshot_cache_key(plan))
        policy = source_policies[plan.source]
        time_range = _support_time_range_for_plan(plan, config=config)
        estimated_cardinality = (
            int(capability.estimated_cardinality or 0) if capability is not None else 0
        )
        allowed_dimension_values = (
            {
                str(key): tuple(str(value) for value in values if str(value).strip())
                for key, values in dict(capability.allowed_positions or {}).items()
            }
            if capability is not None and capability.allowed_positions
            else {}
        )
        recommended_core_transport = _recommended_transport_for_plan(
            plan,
            phase="publishable_core",
            policy=policy,
            capability=capability,
            config=config,
        )
        recommended_backfill_transport = _recommended_transport_for_plan(
            plan,
            phase="long_tail_backfill",
            policy=policy,
            capability=capability,
            config=config,
        )
        sketches[_support_sketch_id(plan)] = SupportSketch(
            sketch_id=_support_sketch_id(plan),
            plan=plan,
            dataset_version=str(
                (
                    capability.version_hint
                    if capability is not None and getattr(capability, "version_hint", None)
                    else plan.dataset_version or plan.request_dataset_id
                )
                or plan.request_dataset_id
            ),
            supported_countries=_supported_countries_for_plan(
                plan, config=config, capability=capability
            ),
            time_range=time_range,
            allowed_dimension_values=allowed_dimension_values,
            estimated_cardinality=estimated_cardinality,
            source_watermark=str(plan.source_watermark or ""),
            recommended_core_transport=recommended_core_transport,
            recommended_backfill_transport=recommended_backfill_transport,
            dimension_order=_normalize_dimension_order(
                capability.dimension_order if capability is not None else ()
            )
            or _infer_dimension_order_for_plan(plan),
        )
    return sketches


def _country_groups_for_sketch(
    sketch: SupportSketch,
    *,
    policy: SourceExecutionPolicy,
    phase: str,
) -> tuple[tuple[str, ...], ...]:
    countries = sketch.supported_countries
    if not countries:
        return ((),)
    source = str(sketch.plan.source or "").strip().lower()
    configured_group_limit = (
        _policy_optional_int_attr(policy, "core_group_limit")
        if phase == "publishable_core"
        else _policy_optional_int_attr(policy, "backfill_group_limit")
    )
    if configured_group_limit is not None:
        group_size = max(1, int(configured_group_limit))
    elif source == "unpd":
        group_size = 25
    elif source == "worldbank":
        span_years = max(int(sketch.time_range[1]) - int(sketch.time_range[0]) + 1, 1)
        max_points = _policy_int_attr(policy, "max_sync_cells", 15_000)
        group_size = max(1, max_points // span_years)
    else:
        group_size = len(countries)
    if group_size >= len(countries):
        return (tuple(countries),)
    groups: list[tuple[str, ...]] = []
    for start in range(0, len(countries), group_size):
        groups.append(tuple(countries[start : start + group_size]))
    return tuple(groups)


def _phase_windows_for_sketch(
    sketch: SupportSketch,
    *,
    config: DatasetBatchConfig,
) -> list[tuple[int, int, str]]:
    start_year, end_year = sketch.time_range
    if sketch.plan.source == "wvs":
        return [(1981, 2023, "publishable_core")]
    if config.preflight_only or config.run_profile == "preflight_core" or config.is_sampled_run:
        return [(start_year, end_year, "publishable_core")]
    if sketch.plan.source in {"eurostat", "oecd", "ilo", "unesco_uis"}:
        windows = _year_windows(
            start_year,
            end_year,
            _observation_time_window_years(
                source=sketch.plan.source,
                update_frequency=sketch.plan.update_frequency,
            ),
        )
        if len(windows) <= 1:
            return [
                (window_start, window_end, "publishable_core")
                for window_start, window_end in windows
            ]
        phased: list[tuple[int, int, str]] = []
        for index, (window_start, window_end) in enumerate(windows):
            phase = "publishable_core" if index == len(windows) - 1 else "long_tail_backfill"
            phased.append((window_start, window_end, phase))
        return phased
    return [(start_year, end_year, "publishable_core")]


def _build_observation_shards_from_sketches(
    sketches: dict[str, SupportSketch],
    *,
    config: DatasetBatchConfig,
    source_policies: dict[str, SourceExecutionPolicy],
) -> list[ObservationShard]:
    shards: list[ObservationShard] = []
    for sketch in sketches.values():
        plan = sketch.plan
        policy = source_policies[plan.source]
        for shard_start, shard_end, phase in _phase_windows_for_sketch(sketch, config=config):
            country_groups = _country_groups_for_sketch(
                sketch,
                policy=policy,
                phase=phase,
            )
            for group in country_groups:
                filters = dict(plan.default_filters)
                if group:
                    if plan.source == "eurostat":
                        filters = _eurostat_filters_for_countries(group, base_filters=filters)
                    elif plan.source in {"oecd", "ilo"}:
                        filters = _sdmx_filters_for_countries(group, base_filters=filters)
                country_code = group[0] if len(group) == 1 else None
                shards.append(
                    ObservationShard(
                        shard_id=_observation_shard_id(
                            plan=plan,
                            country_code=country_code,
                            country_codes=group,
                            start_year=shard_start,
                            end_year=shard_end,
                            filters=filters,
                            split_depth=0,
                        ),
                        plan=plan,
                        country_code=country_code,
                        country_codes=group,
                        start_year=shard_start,
                        end_year=shard_end,
                        filters=filters,
                        split_depth=0,
                        phase=phase,
                        acquisition_method=_transport_for_phase(sketch, phase=phase),
                        source_watermark=sketch.source_watermark,
                        dataset_version=sketch.dataset_version,
                        dimension_order=sketch.dimension_order,
                    )
                )
    return shards
