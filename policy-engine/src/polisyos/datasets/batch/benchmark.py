"""Stage 7.5: consumer benchmark suites for datasets pipeline."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polisyos.academic.knowledge.canonical_seed import CANONICAL_VARIABLES
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.datasets.batch.config import DatasetBatchConfig
from polisyos.datasets.knowledge.search import DatasetCatalogGraph
from polisyos.datasets.knowledge.types import DatasetSearchResult, MetricBindingMatch

READINESS_THRESHOLDS: dict[str, float] = {
    "benchmark_search_top5_relevance_pct": 80.0,
    "benchmark_retrieval_ready_pct": 85.0,
    "benchmark_transport_ready_pct": 80.0,
    "benchmark_foundry_fitness_pct": 80.0,
    "benchmark_source_preflight_ready_pct": 90.0,
}
_PROFILE_THRESHOLD_SKIPS: dict[str, frozenset[str]] = {
    "preflight_core": frozenset(
        {
            "benchmark_transport_ready_pct",
            "benchmark_foundry_fitness_pct",
        }
    ),
}
_EMPIRICAL_OBSERVATION_SOURCES = frozenset(
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
_EXPLICIT_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "gdp_per_capita": ("gdp",),
    "inflation": ("inflation_rate", "cpi", "avg_price"),
    "migration": ("net_migration", "refugee", "population"),
    "health_outcomes": ("life_expectancy", "infant_mortality", "maternal_mortality", "healthy_life_expectancy", "health_spending"),
    "education_outcomes": ("enrollment", "completion", "school_enrollment", "education_spending", "literacy"),
    "labor_force_participation": ("employment_rate",),
    "institutional_quality": ("state_capacity", "corruption_level", "rule_of_law"),
}


@dataclass(frozen=True)
class SearchBenchmarkCase:
    """Multilingual search benchmark case."""

    case_id: str
    query: str
    expected_metrics: tuple[str, ...] = ()
    expected_sources: tuple[str, ...] = ()
    expected_tokens: tuple[str, ...] = ()
    domain_filter: str | None = None


@dataclass(frozen=True)
class BenchmarkSuite:
    """Deterministic benchmark definitions for consumer-facing quality."""

    search_cases: tuple[SearchBenchmarkCase, ...]
    retrieval_metrics: tuple[str, ...]
    transport_variables: tuple[str, ...]
    foundry_metrics: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkOutcome:
    """Result of one benchmark stage run."""

    report_path: Path
    metrics: dict[str, float | int]


def readiness_thresholds_for_profile(run_profile: str) -> dict[str, float]:
    thresholds = dict(READINESS_THRESHOLDS)
    profile = str(run_profile or "prod_full").strip() or "prod_full"
    if profile == "preflight_core":
        thresholds["benchmark_source_preflight_ready_pct"] = 90.0
    return thresholds


def active_readiness_thresholds_for_profile(run_profile: str) -> dict[str, float]:
    thresholds = readiness_thresholds_for_profile(run_profile)
    skipped = _PROFILE_THRESHOLD_SKIPS.get(str(run_profile or "prod_full").strip() or "prod_full", frozenset())
    return {name: value for name, value in thresholds.items() if name not in skipped}


DEFAULT_BENCHMARK_SUITE = BenchmarkSuite(
    search_cases=(
        SearchBenchmarkCase(
            case_id="gdp_en",
            query="gdp per capita",
            expected_metrics=("gdp_per_capita", "gdp"),
            expected_sources=("worldbank", "oecd", "eurostat"),
            expected_tokens=("gdp", "gross domestic product", "per capita"),
        ),
        SearchBenchmarkCase(
            case_id="gdp_uk",
            query="ввп на душу населення",
            expected_metrics=("gdp_per_capita", "gdp"),
            expected_sources=("worldbank", "oecd", "eurostat"),
            expected_tokens=("gdp", "gross domestic product", "per capita", "ввп"),
        ),
        SearchBenchmarkCase(
            case_id="unemployment_en",
            query="unemployment rate",
            expected_metrics=("unemployment_rate",),
            expected_sources=("ilo", "eurostat", "ukons", "data_gov_ua_exec"),
            expected_tokens=("unemployment", "jobless", "labour market", "labor market"),
        ),
        SearchBenchmarkCase(
            case_id="unemployment_uk",
            query="рівень безробіття",
            expected_metrics=("unemployment_rate",),
            expected_sources=("ilo", "eurostat", "ukons", "data_gov_ua_exec"),
            expected_tokens=("unemployment", "jobless", "безробіт"),
        ),
        SearchBenchmarkCase(
            case_id="inflation_en",
            query="inflation consumer prices",
            expected_metrics=("inflation",),
            expected_sources=("oecd", "eurostat", "worldbank", "ukons"),
            expected_tokens=("inflation", "consumer prices", "cpi"),
        ),
        SearchBenchmarkCase(
            case_id="inflation_uk",
            query="інфляція споживчі ціни",
            expected_metrics=("inflation",),
            expected_sources=("oecd", "eurostat", "worldbank", "ukons"),
            expected_tokens=("inflation", "consumer prices", "cpi", "інфляц"),
        ),
        SearchBenchmarkCase(
            case_id="migration_en",
            query="migration flows",
            expected_metrics=("migration",),
            expected_sources=("unpd", "worldbank", "data_gov_ua_exec"),
            expected_tokens=("migration", "migrant", "population movement"),
        ),
        SearchBenchmarkCase(
            case_id="migration_uk",
            query="міграційні потоки",
            expected_metrics=("migration",),
            expected_sources=("unpd", "worldbank", "data_gov_ua_exec"),
            expected_tokens=("migration", "migrant", "міграц"),
        ),
        SearchBenchmarkCase(
            case_id="health_en",
            query="health outcomes life expectancy",
            expected_metrics=("health_outcomes",),
            expected_sources=("who", "worldbank", "data_gov_ua_exec"),
            expected_tokens=("health", "life expectancy", "mortality"),
        ),
        SearchBenchmarkCase(
            case_id="health_uk",
            query="очікувана тривалість життя здоров'я",
            expected_metrics=("health_outcomes",),
            expected_sources=("who", "worldbank", "data_gov_ua_exec"),
            expected_tokens=("health", "life expectancy", "тривалість життя", "здоров"),
        ),
        SearchBenchmarkCase(
            case_id="education_en",
            query="education outcomes enrollment",
            expected_metrics=("education_outcomes",),
            expected_sources=("unesco_uis", "worldbank", "data_gov_ua_exec"),
            expected_tokens=("education", "enrollment", "school", "learning"),
        ),
        SearchBenchmarkCase(
            case_id="education_uk",
            query="освітні результати зарахування до школи",
            expected_metrics=("education_outcomes",),
            expected_sources=("unesco_uis", "worldbank", "data_gov_ua_exec"),
            expected_tokens=("education", "enrollment", "school", "освіт", "школ"),
        ),
        SearchBenchmarkCase(
            case_id="trust_en",
            query="social trust survey",
            expected_metrics=("social_trust",),
            expected_sources=("wvs",),
            expected_tokens=("social trust", "trust", "survey", "values survey"),
        ),
        SearchBenchmarkCase(
            case_id="trust_uk",
            query="соціальна довіра опитування",
            expected_metrics=("social_trust",),
            expected_sources=("wvs",),
            expected_tokens=("social trust", "trust", "values survey", "довір"),
        ),
        SearchBenchmarkCase(
            case_id="poverty_en",
            query="poverty rate income deprivation",
            expected_metrics=("poverty_rate",),
            expected_sources=("worldbank", "oecd", "data_gov_ua_exec"),
            expected_tokens=("poverty", "deprivation", "low income"),
        ),
        SearchBenchmarkCase(
            case_id="poverty_uk",
            query="рівень бідності та доходи",
            expected_metrics=("poverty_rate",),
            expected_sources=("worldbank", "oecd", "data_gov_ua_exec"),
            expected_tokens=("poverty", "income", "бідн", "доход"),
        ),
        SearchBenchmarkCase(
            case_id="labor_en",
            query="labor force participation",
            expected_metrics=("labor_force_participation",),
            expected_sources=("ilo", "worldbank"),
            expected_tokens=("labor force", "labour force", "participation"),
        ),
        SearchBenchmarkCase(
            case_id="labor_uk",
            query="участь у робочій силі",
            expected_metrics=("labor_force_participation",),
            expected_sources=("ilo", "worldbank"),
            expected_tokens=("labor force", "labour force", "participation", "робоч"),
        ),
    ),
    retrieval_metrics=(
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
    ),
    transport_variables=(
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
    ),
    foundry_metrics=(
        "gdp_per_capita",
        "unemployment_rate",
        "inflation",
        "migration",
        "health_outcomes",
        "education_outcomes",
        "poverty_rate",
        "labor_force_participation",
    ),
)

_ROMANIA_DISCOVERY_CASES: tuple[SearchBenchmarkCase, ...] = (
    SearchBenchmarkCase(
        case_id="romania_budget",
        query="buget local romania",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("buget", "budget", "local", "municipal"),
    ),
    SearchBenchmarkCase(
        case_id="romania_education",
        query="educatie romania scoala",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("educat", "scoala", "school", "student"),
    ),
    SearchBenchmarkCase(
        case_id="romania_health",
        query="sanatate publica romania",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("sanat", "health", "hospital", "medical"),
    ),
    SearchBenchmarkCase(
        case_id="romania_labor",
        query="somaj romania piata muncii",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("somaj", "unemployment", "munc", "labor"),
    ),
    SearchBenchmarkCase(
        case_id="romania_migration",
        query="migratie demografie romania",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("migrat", "demograf", "population", "migration"),
    ),
    SearchBenchmarkCase(
        case_id="romania_ukraine_budget_compare",
        query="buget local romania ucraina comparator",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("buget", "romania", "ukraine", "ucraina"),
    ),
    SearchBenchmarkCase(
        case_id="romania_eu_comparator",
        query="romania comparator regional ue",
        expected_sources=("data_gov_ro_broad", "data_gov_ro_exec"),
        expected_tokens=("romania", "regional", "comparator", "ue"),
    ),
)

_MOLDOVA_DISCOVERY_CASES: tuple[SearchBenchmarkCase, ...] = (
    SearchBenchmarkCase(
        case_id="moldova_budget",
        query="buget local moldova",
        expected_sources=("data_gov_md_broad", "data_gov_md_exec"),
        expected_tokens=("buget", "budget", "local", "municipal"),
    ),
    SearchBenchmarkCase(
        case_id="moldova_education",
        query="educatie moldova scoala",
        expected_sources=("data_gov_md_broad", "data_gov_md_exec"),
        expected_tokens=("educat", "scoala", "school", "student"),
    ),
    SearchBenchmarkCase(
        case_id="moldova_health",
        query="sanatate publica moldova",
        expected_sources=("data_gov_md_broad", "data_gov_md_exec"),
        expected_tokens=("sanat", "health", "hospital", "medical"),
    ),
    SearchBenchmarkCase(
        case_id="moldova_labor",
        query="somaj moldova piata muncii",
        expected_sources=("data_gov_md_broad", "data_gov_md_exec"),
        expected_tokens=("somaj", "unemployment", "munc", "labor"),
    ),
    SearchBenchmarkCase(
        case_id="moldova_migration",
        query="migratie demografie moldova",
        expected_sources=("data_gov_md_broad", "data_gov_md_exec"),
        expected_tokens=("migrat", "demograf", "population", "migration"),
    ),
)

_POLAND_DISCOVERY_CASES: tuple[SearchBenchmarkCase, ...] = (
    SearchBenchmarkCase(
        case_id="poland_budget",
        query="budzet lokalny polska",
        expected_sources=("data_gov_pl_broad", "data_gov_pl_exec"),
        expected_tokens=("budzet", "budget", "local", "municipal"),
    ),
    SearchBenchmarkCase(
        case_id="poland_education",
        query="edukacja polska szkola",
        expected_sources=("data_gov_pl_broad", "data_gov_pl_exec"),
        expected_tokens=("edukac", "szkol", "school", "student"),
    ),
    SearchBenchmarkCase(
        case_id="poland_health",
        query="zdrowie publiczne polska",
        expected_sources=("data_gov_pl_broad", "data_gov_pl_exec"),
        expected_tokens=("zdrow", "health", "hospital", "medical"),
    ),
    SearchBenchmarkCase(
        case_id="poland_labor",
        query="bezrobocie polska rynek pracy",
        expected_sources=("data_gov_pl_broad", "data_gov_pl_exec"),
        expected_tokens=("bezroboc", "unemployment", "pracy", "labor"),
    ),
    SearchBenchmarkCase(
        case_id="poland_migration",
        query="migracja demografia polska",
        expected_sources=("data_gov_pl_broad", "data_gov_pl_exec"),
        expected_tokens=("migrac", "demografi", "population", "migration"),
    ),
)
_MUNICIPAL_DISCOVERY_CASES: tuple[SearchBenchmarkCase, ...] = (
    SearchBenchmarkCase(
        case_id="municipal_mobility",
        query="municipal mobility transit open data",
        expected_sources=("paris_opendata_exec", "nyc_opendata_exec", "chicago_opendata_exec"),
        expected_tokens=("mobility", "transit", "transport", "municipal"),
    ),
    SearchBenchmarkCase(
        case_id="municipal_housing",
        query="city housing inspections open data",
        expected_sources=("nyc_opendata_exec", "chicago_opendata_exec"),
        expected_tokens=("housing", "inspection", "city", "municipal"),
    ),
)
_ENRICHMENT_DISCOVERY_CASES: tuple[SearchBenchmarkCase, ...] = (
    SearchBenchmarkCase(
        case_id="entity_resolution",
        query="country aliases entity resolution taxonomy",
        expected_sources=("wikidata_sparql", "dbpedia_sparql"),
        expected_tokens=("entity", "alias", "taxonomy", "linked"),
    ),
)


def _pct(successes: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round((100.0 * successes) / total, 3)


def _normalize_text(value: str) -> str:
    return " ".join((value or "").lower().split())


def _metric_aliases(metric_id: str) -> tuple[str, ...]:
    aliases: list[str] = []
    for candidate in (metric_id, *_EXPLICIT_METRIC_ALIASES.get(metric_id, ())):
        text = str(candidate or "").strip()
        if text and text not in aliases:
            aliases.append(text)
    if metric_id in CANONICAL_VARIABLES:
        for child in CANONICAL_VARIABLES[metric_id]:
            if child == "_root":
                continue
            if child not in aliases:
                aliases.append(child)
    return tuple(aliases)


def _result_text(result: DatasetSearchResult) -> str:
    return _normalize_text(
        " ".join(
            [
                result.title,
                result.description,
                result.publisher,
                result.source,
                result.agency,
                " ".join(result.keywords),
                " ".join(result.variables),
                " ".join(result.polisyos_metrics),
                " ".join(result.themes),
            ]
        )
    )


def _result_matches_case(result: DatasetSearchResult, case: SearchBenchmarkCase) -> bool:
    metrics = {item.strip().lower() for item in result.polisyos_metrics if item}
    expected_metrics = {
        alias.strip().lower()
        for item in case.expected_metrics
        for alias in _metric_aliases(item)
        if alias
    }
    if expected_metrics and metrics.intersection(expected_metrics):
        return True

    source = (result.source or "").strip().lower()
    expected_sources = {item.strip().lower() for item in case.expected_sources if item}
    if expected_sources and source in expected_sources:
        return True

    haystack = _result_text(result)
    return any(token and _normalize_text(token) in haystack for token in case.expected_tokens)


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
        [table_name],
    ).fetchone()
    return row is not None


def _rest_manifest_metrics(config: DatasetBatchConfig) -> tuple[dict[str, int], dict[str, int], list[str]]:
    rest_rows_by_source: dict[str, int] = {}
    rest_bytes_by_source: dict[str, int] = {}
    history_budget_exceeded_sources: list[str] = []
    registry = {spec.name: spec for spec in config.load_registry().sources}
    for source_dir in sorted([path for path in config.raw_dir.iterdir() if path.is_dir()]) if config.raw_dir.exists() else []:
        spec = registry.get(source_dir.name)
        if spec is None or spec.family != "rest":
            continue
        snapshots = sorted([path for path in source_dir.iterdir() if path.is_dir()])
        if not snapshots:
            continue
        payload_path = snapshots[-1] / "payload.jsonl"
        row_count = 0
        if payload_path.exists():
            with open(payload_path, "r", encoding="utf-8") as fh:
                row_count = sum(1 for line in fh if line.strip())
        payload_bytes = int(payload_path.stat().st_size) if payload_path.exists() else 0
        rest_rows_by_source[spec.name] = row_count
        rest_bytes_by_source[spec.name] = payload_bytes
        rows_exceeded = spec.max_rows_per_snapshot is not None and row_count > int(spec.max_rows_per_snapshot)
        bytes_exceeded = spec.max_bytes_per_snapshot is not None and payload_bytes > int(spec.max_bytes_per_snapshot)
        if rows_exceeded or bytes_exceeded:
            history_budget_exceeded_sources.append(spec.name)
    return rest_rows_by_source, rest_bytes_by_source, history_budget_exceeded_sources


def _latest_source_manifest(source_dir: Path) -> Path | None:
    if not source_dir.exists():
        return None
    snapshots = sorted(path for path in source_dir.iterdir() if path.is_dir())
    if not snapshots:
        return None
    manifest_path = snapshots[-1] / "manifest.json"
    return manifest_path if manifest_path.exists() else None


def _load_json_list(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _source_counts(
    con: duckdb.DuckDBPyConnection,
    *,
    query: str,
) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in con.execute(query).fetchall()}


def _auth_or_env_error(text: str) -> bool:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return False
    return any(
        token in lowered
        for token in (
            "token is required",
            "auth",
            "credential",
            "authorization",
            "api key",
            "bearer",
        )
    )


def _run_source_preflight_benchmark(
    config: DatasetBatchConfig,
    con: duckdb.DuckDBPyConnection,
) -> tuple[dict[str, object], dict[str, float | int]]:
    registry = config.load_registry()
    blocking_sources = [
        spec
        for spec in registry.sources
        if spec.enabled and spec.publish_blocking and spec.run_lane == "empirical"
    ]
    dataset_counts = (
        _source_counts(con, query="SELECT source, COUNT(*) FROM ds_datasets GROUP BY source")
        if _table_exists(con, "ds_datasets")
        else {}
    )
    registry_counts = (
        _source_counts(con, query="SELECT provider, COUNT(*) FROM ds_registry_datasets GROUP BY provider")
        if _table_exists(con, "ds_registry_datasets")
        else {}
    )
    binding_counts = (
        _source_counts(
            con,
            query=(
                "SELECT ds.source, COUNT(*) "
                "FROM ds_metric_bindings AS mb "
                "JOIN ds_datasets AS ds ON ds.id = mb.dataset_id "
                "GROUP BY ds.source"
            ),
        )
        if _table_exists(con, "ds_metric_bindings") and _table_exists(con, "ds_datasets")
        else {}
    )
    schema_counts = (
        _source_counts(
            con,
            query=(
                "SELECT ds.source, COUNT(*) "
                "FROM ds_schema_profiles AS sp "
                "JOIN ds_datasets AS ds ON ds.id = sp.dataset_id "
                "GROUP BY ds.source"
            ),
        )
        if _table_exists(con, "ds_schema_profiles") and _table_exists(con, "ds_datasets")
        else {}
    )
    summary_payload: dict[str, object] = {}
    summary_path = config.manifests_dir / "observation_source_summary.json"
    if summary_path.exists():
        with open(summary_path, "r", encoding="utf-8") as fh:
            loaded = json.load(fh)
        if isinstance(loaded, dict):
            summary_payload = loaded
    completed_payload = _load_json_list(config.manifests_dir / "completed_observation_shards.json")
    failed_payload = _load_json_list(config.manifests_dir / "failed_observation_shards.json")
    deferred_payload = _load_json_list(config.manifests_dir / "deferred_observation_plans.json")
    errors_by_source: dict[str, list[str]] = {}
    for item in [*failed_payload, *deferred_payload]:
        source = str(item.get("source") or "").strip()
        if not source:
            continue
        errors_by_source.setdefault(source, []).append(str(item.get("error") or ""))

    cases: list[dict[str, object]] = []
    ready = 0
    auth_failures = 0
    for spec in blocking_sources:
        manifest_path = _latest_source_manifest(config.raw_dir / spec.name)
        raw_count = 0
        if manifest_path is not None:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            raw_count = int(manifest.get("count", 0) or 0)
        summary = summary_payload.get(spec.name, {})
        completed = int(summary.get("complete", 0) or 0) if isinstance(summary, dict) else 0
        complete_with_rows = int(summary.get("complete_with_rows", 0) or 0) if isinstance(summary, dict) else 0
        complete_empty = int(summary.get("complete_empty", 0) or 0) if isinstance(summary, dict) else 0
        deferred = int(summary.get("deferred", 0) or 0) if isinstance(summary, dict) else 0
        failed = int(summary.get("failed", 0) or 0) if isinstance(summary, dict) else 0
        empirical_rows = int(summary.get("rows", 0) or 0) if isinstance(summary, dict) else 0
        if completed and complete_with_rows == 0 and complete_empty == 0:
            if empirical_rows > 0:
                complete_with_rows = completed
            else:
                complete_empty = completed
        dataset_count = int(dataset_counts.get(spec.name, 0))
        registry_count = int(registry_counts.get(spec.name, 0))
        binding_count = int(binding_counts.get(spec.name, 0))
        schema_count = int(schema_counts.get(spec.name, 0))
        auth_or_env_failure = any(_auth_or_env_error(error) for error in errors_by_source.get(spec.name, []))
        if auth_or_env_failure:
            auth_failures += 1

        empirical_required = spec.name in _EMPIRICAL_OBSERVATION_SOURCES
        has_graph_presence = dataset_count > 0
        has_execution_artifacts = binding_count > 0 or schema_count > 0 or registry_count > 0
        has_empirical_rows = complete_with_rows > 0 or empirical_rows > 0

        if raw_count <= 0 and dataset_count <= 0 and completed <= 0 and deferred <= 0 and failed <= 0:
            status = "missing"
        elif failed > 0 or auth_or_env_failure:
            status = "failed_with_manifest"
        elif deferred > 0:
            status = "partial_with_deferred_manifest"
        else:
            status = "complete"

        empirical_status = "none"
        if complete_with_rows > 0 or empirical_rows > 0:
            empirical_status = "complete_with_rows"
        elif complete_empty > 0 or completed > 0:
            empirical_status = "complete_empty"

        if empirical_required:
            source_ready = raw_count > 0 and has_graph_presence and has_empirical_rows and failed == 0 and not auth_or_env_failure
        else:
            source_ready = raw_count > 0 and has_graph_presence and has_execution_artifacts and failed == 0 and not auth_or_env_failure
        if source_ready:
            ready += 1

        # Determine failure_reason for diagnostics when source is not ready.
        failure_reason: str | None = None
        if not source_ready:
            if auth_or_env_failure:
                failure_reason = "auth_or_env"
            elif failed > 0:
                failure_reason = "fetch_error"
            elif empirical_required and not has_empirical_rows and complete_empty > 0:
                failure_reason = "indicators_empty"
            elif raw_count <= 0:
                failure_reason = "no_raw_data"
            elif not has_graph_presence:
                failure_reason = "no_catalog_entry"
            elif empirical_required and not has_empirical_rows:
                failure_reason = "no_empirical_data"
            elif not has_execution_artifacts:
                failure_reason = "no_execution_artifacts"

        cases.append(
            {
                "source": spec.name,
                "raw_count": raw_count,
                "catalog_count": dataset_count,
                "dataset_count": dataset_count,
                "registry_count": registry_count,
                "binding_count": binding_count,
                "schema_profile_count": schema_count,
                "completed_shards": completed,
                "complete_with_rows_shards": complete_with_rows,
                "complete_empty_shards": complete_empty,
                "deferred_shards": deferred,
                "failed_shards": failed,
                "status": status,
                "empirical_status": empirical_status,
                "empirical_rows": empirical_rows,
                "auth_or_env_failure": auth_or_env_failure,
                "ready": source_ready,
                "failure_reason": failure_reason,
            }
        )

    total = len(blocking_sources)
    return {"sources": cases}, {
        "benchmark_source_preflight_sources_total": total,
        "benchmark_source_preflight_ready_pct": _pct(ready, total),
        "benchmark_source_preflight_auth_failures_total": auth_failures,
    }


def _source_exists(con: duckdb.DuckDBPyConnection, source_name: str) -> bool:
    if not _table_exists(con, "ds_datasets"):
        return False
    row = con.execute(
        "SELECT 1 FROM ds_datasets WHERE source = ? LIMIT 1",
        [source_name],
    ).fetchone()
    return row is not None


def _benchmark_suite_for_snapshot(
    con: duckdb.DuckDBPyConnection,
    suite: BenchmarkSuite,
) -> BenchmarkSuite:
    if suite is not DEFAULT_BENCHMARK_SUITE:
        return suite

    search_cases = list(suite.search_cases)
    if _source_exists(con, "data_gov_ro_broad") or _source_exists(con, "data_gov_ro_exec"):
        search_cases.extend(_ROMANIA_DISCOVERY_CASES)
    if _source_exists(con, "data_gov_md_broad") or _source_exists(con, "data_gov_md_exec"):
        search_cases.extend(_MOLDOVA_DISCOVERY_CASES)
    if _source_exists(con, "data_gov_pl_broad") or _source_exists(con, "data_gov_pl_exec"):
        search_cases.extend(_POLAND_DISCOVERY_CASES)
    if any(
        _source_exists(con, source_name)
        for source_name in ("paris_opendata_exec", "nyc_opendata_exec", "chicago_opendata_exec")
    ):
        search_cases.extend(_MUNICIPAL_DISCOVERY_CASES)
    if _source_exists(con, "wikidata_sparql") or _source_exists(con, "dbpedia_sparql"):
        search_cases.extend(_ENRICHMENT_DISCOVERY_CASES)

    return BenchmarkSuite(
        search_cases=tuple(search_cases),
        retrieval_metrics=suite.retrieval_metrics,
        transport_variables=suite.transport_variables,
        foundry_metrics=suite.foundry_metrics,
    )


def _run_search_benchmark(
    graph: DatasetCatalogGraph,
    *,
    suite: BenchmarkSuite,
    vector_index_available: bool,
) -> tuple[dict[str, object], dict[str, float | int]]:
    case_results: list[dict[str, object]] = []
    top1_hits = 0
    top5_hits = 0

    for case in suite.search_cases:
        results = graph.search_datasets(case.query, domain_filter=case.domain_filter, top_k=5)
        top5_hit = any(_result_matches_case(item, case) for item in results[:5])
        top1_hit = bool(results[:1]) and _result_matches_case(results[0], case)
        top1_hits += int(top1_hit)
        top5_hits += int(top5_hit)
        case_results.append(
            {
                "case_id": case.case_id,
                "query": case.query,
                "top1_hit": top1_hit,
                "top5_hit": top5_hit,
                "results": [
                    {
                        "id": item.id,
                        "title": item.title,
                        "source": item.source,
                        "metrics": item.polisyos_metrics,
                        "similarity": round(float(item.similarity), 6),
                    }
                    for item in results[:5]
                ],
            }
        )

    metrics = {
        "benchmark_search_cases_total": len(suite.search_cases),
        "benchmark_search_vector_index_available": int(vector_index_available),
        "benchmark_search_top1_relevance_pct": _pct(top1_hits, len(suite.search_cases)),
        "benchmark_search_top5_relevance_pct": _pct(top5_hits, len(suite.search_cases)),
    }
    return {"cases": case_results}, metrics


def _binding_ready(binding: MetricBindingMatch) -> bool:
    return bool(
        binding.connector_id
        and binding.request_dataset_id
        and binding.execution_tier in {"fetchable", "transport_ready"}
    )


def _binding_rank(binding: MetricBindingMatch, *, preferred_metric_id: str) -> tuple[float, ...]:
    tier_rank = {
        "transport_ready": 0,
        "fetchable": 1,
        "catalog": 2,
    }.get(str(binding.execution_tier or "catalog"), 3)
    return (
        float(tier_rank),
        0.0 if _binding_ready(binding) else 1.0,
        0.0 if binding.metric_id == preferred_metric_id else 1.0,
        -float(binding.confidence),
    )


def _resolve_metric_bindings_with_aliases(
    graph: DatasetCatalogGraph,
    metric_id: str,
    *,
    top_k: int,
) -> tuple[str, list[MetricBindingMatch]]:
    best: dict[tuple[str, str], MetricBindingMatch] = {}
    matched_metric = metric_id
    for candidate_metric in _metric_aliases(metric_id):
        bindings = graph.resolve_metric_bindings(candidate_metric, top_k=top_k)
        if bindings and matched_metric == metric_id:
            matched_metric = candidate_metric
        for item in bindings:
            key = (item.catalog_dataset_id, item.distribution_id)
            current = best.get(key)
            if current is None or item.confidence > current.confidence:
                best[key] = item
    ranked = sorted(
        best.values(),
        key=lambda item: (
            *_binding_rank(item, preferred_metric_id=metric_id),
            item.catalog_dataset_id,
            item.distribution_id or "",
        ),
    )
    return matched_metric, ranked[:top_k]


def _run_retrieval_benchmark(
    graph: DatasetCatalogGraph,
    *,
    suite: BenchmarkSuite,
) -> tuple[dict[str, object], dict[str, float | int]]:
    metric_results: list[dict[str, object]] = []
    binding_hits = 0
    target_hits = 0
    ready_hits = 0

    for metric_id in suite.retrieval_metrics:
        matched_metric_id, bindings = _resolve_metric_bindings_with_aliases(graph, metric_id, top_k=5)
        ready_binding = next((item for item in bindings if _binding_ready(item)), None)
        target = graph.resolve_fetch_target(ready_binding.catalog_dataset_id) if ready_binding else None
        binding_hit = ready_binding is not None
        target_hit = target is not None and bool(target.connector_id and target.request_dataset_id)
        ready = binding_hit and target_hit
        binding_hits += int(binding_hit)
        target_hits += int(target_hit)
        ready_hits += int(ready)
        metric_results.append(
            {
                "metric_id": metric_id,
                "matched_metric_id": matched_metric_id if ready_binding else "",
                "binding_hit": binding_hit,
                "fetch_target_hit": target_hit,
                "ready": ready,
                "binding_dataset_id": ready_binding.catalog_dataset_id if ready_binding else "",
                "connector_id": ready_binding.connector_id if ready_binding else "",
                "profile_id": ready_binding.profile_id if ready_binding else "",
                "request_dataset_id": ready_binding.request_dataset_id if ready_binding else "",
            }
        )

    total = len(suite.retrieval_metrics)
    metrics = {
        "benchmark_retrieval_metrics_total": total,
        "benchmark_retrieval_binding_pct": _pct(binding_hits, total),
        "benchmark_retrieval_fetch_target_pct": _pct(target_hits, total),
        "benchmark_retrieval_ready_pct": _pct(ready_hits, total),
    }
    return {"metrics": metric_results}, metrics


def _run_transport_benchmark(
    con: duckdb.DuckDBPyConnection,
    *,
    suite: BenchmarkSuite,
) -> tuple[dict[str, object], dict[str, float | int]]:
    has_alignments = _table_exists(con, "ds_variable_alignments")
    has_observations = _table_exists(con, "ds_observations")
    has_registry = _table_exists(con, "ds_registry_datasets")
    variable_results: list[dict[str, object]] = []
    alignment_hits = 0
    observation_hits = 0
    ready_hits = 0

    for canonical_var in suite.transport_variables:
        aliases = _metric_aliases(canonical_var)
        placeholders = ", ".join("?" for _ in aliases)
        alignment_hit = False
        observation_hit = False
        registry_hit = False
        if has_alignments:
            alignment_hit = bool(
                con.execute(
                    f"SELECT 1 FROM ds_variable_alignments WHERE canonical_var IN ({placeholders}) LIMIT 1",
                    list(aliases),
                ).fetchone()
            )
        if has_observations:
            observation_hit = bool(
                con.execute(
                    f"SELECT 1 FROM ds_observations WHERE canonical_var IN ({placeholders}) LIMIT 1",
                    list(aliases),
                ).fetchone()
            )
        if has_alignments and has_registry:
            registry_hit = bool(
                con.execute(
                    "SELECT 1 FROM ds_registry_datasets rd "
                    "JOIN ds_variable_alignments va ON va.dataset_id = rd.dataset_id "
                    f"WHERE va.canonical_var IN ({placeholders}) LIMIT 1",
                    list(aliases),
                ).fetchone()
            )
        ready = alignment_hit and observation_hit and registry_hit
        alignment_hits += int(alignment_hit)
        observation_hits += int(observation_hit)
        ready_hits += int(ready)
        variable_results.append(
            {
                "canonical_var": canonical_var,
                "alignment_hit": alignment_hit,
                "observation_hit": observation_hit,
                "registry_hit": registry_hit,
                "ready": ready,
            }
        )

    total = len(suite.transport_variables)
    metrics = {
        "benchmark_transport_variables_total": total,
        "benchmark_transport_alignment_pct": _pct(alignment_hits, total),
        "benchmark_transport_observation_pct": _pct(observation_hits, total),
        "benchmark_transport_ready_pct": _pct(ready_hits, total),
    }
    return {"variables": variable_results}, metrics


def _run_foundry_benchmark(
    con: duckdb.DuckDBPyConnection,
    graph: DatasetCatalogGraph,
    *,
    suite: BenchmarkSuite,
) -> tuple[dict[str, object], dict[str, float | int]]:
    has_schema = _table_exists(con, "ds_schema_profiles")
    has_distributions = _table_exists(con, "ds_distributions")
    metric_results: list[dict[str, object]] = []
    fitness_hits = 0

    for metric_id in suite.foundry_metrics:
        matched_metric_id, bindings = _resolve_metric_bindings_with_aliases(graph, metric_id, top_k=10)
        selected_binding: MetricBindingMatch | None = None
        selected_distribution_id = ""
        selected_fetch_target = None
        schema_ready = False
        parser_supported = False
        machine_readable = False
        fit = False

        for binding in bindings:
            dataset_id = binding.catalog_dataset_id
            fetch_target = graph.resolve_fetch_target(dataset_id) if dataset_id else None
            binding_schema_ready = False
            if has_schema and dataset_id:
                binding_schema_ready = bool(
                    con.execute(
                        "SELECT 1 FROM ds_schema_profiles WHERE dataset_id = ? LIMIT 1",
                        [dataset_id],
                    ).fetchone()
                )
            binding_distribution_id = str(binding.distribution_id or (fetch_target.distribution_id if fetch_target else ""))
            binding_parser_supported = False
            binding_machine_readable = False
            if has_distributions and binding_distribution_id:
                dist_row = con.execute(
                    "SELECT parser_supported, machine_readable FROM ds_distributions WHERE id = ? LIMIT 1",
                    [binding_distribution_id],
                ).fetchone()
                if dist_row is not None:
                    binding_parser_supported = bool(dist_row[0])
                    binding_machine_readable = bool(dist_row[1])
            binding_fit = bool(
                dataset_id
                and binding.execution_tier in {"fetchable", "transport_ready"}
                and binding_schema_ready
                and binding_parser_supported
                and binding_machine_readable
                and fetch_target is not None
                and fetch_target.connector_id
                and fetch_target.request_dataset_id
            )
            if selected_binding is None:
                selected_binding = binding
                selected_distribution_id = binding_distribution_id
                selected_fetch_target = fetch_target
                schema_ready = binding_schema_ready
                parser_supported = binding_parser_supported
                machine_readable = binding_machine_readable
                fit = binding_fit
            if binding_fit:
                selected_binding = binding
                selected_distribution_id = binding_distribution_id
                selected_fetch_target = fetch_target
                schema_ready = binding_schema_ready
                parser_supported = binding_parser_supported
                machine_readable = binding_machine_readable
                fit = True
                break

        dataset_id = selected_binding.catalog_dataset_id if selected_binding else ""
        execution_tier = str(selected_binding.execution_tier) if selected_binding else "catalog"
        matched_metric_id = str(selected_binding.metric_id) if selected_binding else matched_metric_id
        fitness_hits += int(fit)
        metric_results.append(
            {
                "metric_id": metric_id,
                "matched_metric_id": matched_metric_id,
                "dataset_id": dataset_id,
                "distribution_id": selected_distribution_id,
                "execution_tier": execution_tier,
                "schema_ready": schema_ready,
                "parser_supported": parser_supported,
                "machine_readable": machine_readable,
                "fetch_target_ready": bool(selected_fetch_target and selected_fetch_target.request_dataset_id),
                "fit": fit,
            }
        )

    total = len(suite.foundry_metrics)
    metrics = {
        "benchmark_foundry_metrics_total": total,
        "benchmark_foundry_fitness_pct": _pct(fitness_hits, total),
    }
    return {"metrics": metric_results}, metrics


def run_benchmark(
    config: DatasetBatchConfig,
    *,
    suite: BenchmarkSuite = DEFAULT_BENCHMARK_SUITE,
) -> BenchmarkOutcome:
    """Run deterministic consumer benchmark suites and write JSON report."""
    started_at = datetime.now(UTC).isoformat()
    thresholds = readiness_thresholds_for_profile(config.run_profile)
    graph = DatasetCatalogGraph(db_path=config.db_path, index_dir=config.index_dir)
    con = duckdb.connect(str(config.db_path), read_only=True)
    try:
        active_suite = _benchmark_suite_for_snapshot(con, suite)
        search_payload, search_metrics = _run_search_benchmark(
            graph,
            suite=active_suite,
            vector_index_available=(config.index_dir / "ds_dataset_index.hnsw").exists(),
        )
        retrieval_payload, retrieval_metrics = _run_retrieval_benchmark(graph, suite=active_suite)
        transport_payload, transport_metrics = _run_transport_benchmark(con, suite=active_suite)
        foundry_payload, foundry_metrics = _run_foundry_benchmark(con, graph, suite=active_suite)
        preflight_payload, preflight_metrics = _run_source_preflight_benchmark(config, con)
    finally:
        con.close()
        graph.close()

    metrics: dict[str, float | int] = {}
    metrics.update(search_metrics)
    metrics.update(retrieval_metrics)
    metrics.update(transport_metrics)
    metrics.update(foundry_metrics)
    metrics.update(preflight_metrics)
    rest_rows_by_source, rest_bytes_by_source, history_budget_exceeded_sources = _rest_manifest_metrics(config)
    metrics["history_budget_exceeded_sources_total"] = len(history_budget_exceeded_sources)

    report = {
        "kind": "datasets_benchmark",
        "snapshot_root": str(config.snapshot_root),
        "component_dir": str(config.component_dir),
        "generated_at": datetime.now(UTC).isoformat(),
        "run_profile": config.run_profile,
        "thresholds": thresholds,
        "suite": {
            "search_cases": [asdict(case) for case in active_suite.search_cases],
            "retrieval_metrics": list(active_suite.retrieval_metrics),
            "transport_variables": list(active_suite.transport_variables),
            "foundry_metrics": list(active_suite.foundry_metrics),
        },
        "metrics": metrics,
        "rest_rows_by_source": rest_rows_by_source,
        "rest_bytes_by_source": rest_bytes_by_source,
        "history_budget_exceeded_sources": history_budget_exceeded_sources,
        "search": search_payload,
        "retrieval": retrieval_payload,
        "transport": transport_payload,
        "foundry": foundry_payload,
        "source_preflight": preflight_payload,
        "source_publish_blocking": {
            spec.name: bool(spec.publish_blocking)
            for spec in sorted(config.load_registry().sources, key=lambda item: item.name)
            if spec.enabled
        },
    }

    config.benchmark_report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config.benchmark_report_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)

    write_stage_manifest(
        manifest_path=config.manifests_dir / "benchmark.json",
        stage="benchmark",
        status="ok",
        metrics={
            **metrics,
            "rest_rows_by_source": rest_rows_by_source,
            "rest_bytes_by_source": rest_bytes_by_source,
            "history_budget_exceeded_sources": history_budget_exceeded_sources,
            "source_publish_blocking": report["source_publish_blocking"],
        },
        artifacts=[config.benchmark_report_path],
        started_at=started_at,
    )
    return BenchmarkOutcome(report_path=config.benchmark_report_path, metrics=metrics)
