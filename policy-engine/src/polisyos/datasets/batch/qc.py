"""Stage 7: QC checks for datasets pipeline."""

from __future__ import annotations

import json
import random
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.batch_common.qc import QCCheck, QCReport, evaluate_fail_fast, write_qc_report
from polisyos.common.logger import get_logger
from polisyos.datasets.batch.benchmark import (
    active_readiness_thresholds_for_profile,
    readiness_thresholds_for_profile,
)
from polisyos.datasets.batch.config import DatasetBatchConfig

logger = get_logger(__name__)


def _is_smoke_like_run(config: DatasetBatchConfig) -> bool:
    return config.is_sampled_run or config.uses_custom_registry or config.run_profile == "preflight_core"


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as fh:
        return sum(1 for _ in fh)


def _file_size(path: Path) -> int:
    if not path.exists():
        return 0
    return int(path.stat().st_size)


def _source_counts_towards_description_qc(spec: object) -> bool:
    family = str(getattr(spec, "family", "") or "").strip().lower()
    run_lane = str(getattr(spec, "run_lane", "") or "").strip().lower()
    if run_lane == "enrichment":
        return False
    if family in {"sdmx", "who", "uis", "worldbank", "unpd", "wvs"} and run_lane == "empirical":
        return False
    return True


def _url_is_reachable(url: str, *, timeout: int = 10) -> bool:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return False

    requests = (
        urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"}),
        urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "Mozilla/5.0", "Range": "bytes=0-0"},
        ),
    )
    for request in requests:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                if int(resp.status) < 500:
                    return True
        except Exception as exc:
            logger.debug("Ignored exception for %s %s: {}", request.get_method(), url, exc)
    return False


def _latest_manifest(source_dir: Path) -> Path | None:
    if not source_dir.exists():
        return None
    snaps = sorted([p for p in source_dir.iterdir() if p.is_dir()])
    if not snaps:
        return None
    manifest = snaps[-1] / "manifest.json"
    return manifest if manifest.exists() else None


def _previous_snapshot_root(config: DatasetBatchConfig) -> Path | None:
    parent = config.snapshot_root.parent
    if not parent.exists():
        return None
    current = config.snapshot_root.resolve()
    siblings = sorted(
        [path for path in parent.iterdir() if path.is_dir() and (path / "datasets").exists()],
        key=lambda item: (item.name, item.stat().st_mtime_ns),
    )
    older_by_name = [path for path in siblings if path.resolve() != current and path.name < current.name]
    if older_by_name:
        return older_by_name[-1]
    older_by_time = [path for path in siblings if path.resolve() != current and path.stat().st_mtime_ns <= current.stat().st_mtime_ns]
    return older_by_time[-1] if older_by_time else None


def _manifest_count_for_snapshot(snapshot_root: Path, source: str) -> int | None:
    manifest_path = _latest_manifest(snapshot_root / "datasets" / "raw" / source)
    if manifest_path is None:
        return None
    with open(manifest_path, "r", encoding="utf-8") as fh:
        manifest = json.load(fh)
    payload = Path(manifest.get("payload", ""))
    return _line_count(payload)


def _table_exists(con: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    row = con.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'main' AND table_name = ?",
        [table_name],
    ).fetchone()
    return row is not None


def _table_columns(con: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    if not _table_exists(con, table_name):
        return set()
    return {
        str(row[1])
        for row in con.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    }


def _scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list[object] | None = None) -> float:
    row = con.execute(sql, params or []).fetchone()
    value = row[0] if row else 0.0
    return float(value or 0.0)


def _duplicate_ratio(config: DatasetBatchConfig, merged_total: int) -> float:
    if not config.duplicates_report_path.exists() or merged_total <= 0:
        return 0.0
    with open(config.duplicates_report_path, "r", encoding="utf-8") as fh:
        duplicate_rows = sum(1 for index, _line in enumerate(fh) if index > 0)
    return round((100.0 * duplicate_rows) / merged_total, 3)


def _coverage_heatmap_path(config: DatasetBatchConfig) -> Path:
    return config.component_dir / "coverage_heatmap.json"


def _generate_coverage_heatmap(
    con: duckdb.DuckDBPyConnection,
    *,
    countries: tuple[str, ...],
    variables: tuple[str, ...],
    year_range: tuple[int, int],
) -> dict[str, dict[str, dict[str, object]]]:
    start_year, end_year = year_range
    matrix: dict[str, dict[str, dict[str, object]]] = {}
    for country in countries:
        country_data: dict[str, dict[str, object]] = {}
        for variable in variables:
            rows = con.execute(
                "SELECT DISTINCT COALESCE(year, survey_year) AS observed_year "
                "FROM ds_observations "
                "WHERE country_code = ? AND canonical_var = ? "
                "AND COALESCE(year, survey_year) BETWEEN ? AND ? "
                "ORDER BY observed_year",
                [country, variable, start_year, end_year],
            ).fetchall()
            observed_years = [int(row[0]) for row in rows if row and row[0] is not None]
            if len(observed_years) >= (end_year - start_year + 1):
                status = "full"
            elif observed_years:
                status = "partial"
            else:
                status = "missing"
            country_data[variable] = {
                "available_years": observed_years,
                "latest_year": observed_years[-1] if observed_years else None,
                "count": len(observed_years),
                "status": status,
            }
        matrix[country] = country_data
    return matrix


def _check_observation_coverage(
    con: duckdb.DuckDBPyConnection,
    *,
    countries: tuple[str, ...],
    variables: tuple[str, ...],
    year_range: tuple[int, int],
) -> QCCheck:
    start_year, end_year = year_range
    total_cells = len(countries) * len(variables) * ((end_year - start_year) + 1)
    if total_cells <= 0:
        return QCCheck(
            name="observation_coverage_pct",
            passed=True,
            value=100.0,
            threshold=60.0,
            severity="info",
        )
    filled = con.execute(
        "SELECT COUNT(*) FROM ("
        "SELECT DISTINCT country_code, canonical_var, COALESCE(year, survey_year) AS observed_year "
        "FROM ds_observations "
        "WHERE country_code IN (SELECT UNNEST(?::VARCHAR[])) "
        "AND canonical_var IN (SELECT UNNEST(?::VARCHAR[])) "
        "AND COALESCE(year, survey_year) BETWEEN ? AND ?"
        ")",
        [list(countries), list(variables), start_year, end_year],
    ).fetchone()[0]
    coverage = (100.0 * float(filled or 0)) / float(total_cells)
    return QCCheck(
        name="observation_coverage_pct",
        passed=coverage >= 60.0,
        value=round(coverage, 3),
        threshold=60.0,
        severity="warning",
        message="Coverage across active countries, core variables, and requested years",
    )


def _check_cross_source_consistency(con: duckdb.DuckDBPyConnection) -> QCCheck:
    disagreements = con.execute(
        "WITH multi_source AS ("
        "SELECT canonical_var, country_code, COALESCE(year, survey_year) AS observed_year, "
        "MIN(value) AS min_val, MAX(value) AS max_val, AVG(value) AS mean_val, "
        "COUNT(DISTINCT dataset_id) AS n_sources "
        "FROM ds_observations "
        "WHERE value IS NOT NULL "
        "GROUP BY canonical_var, country_code, COALESCE(year, survey_year) "
        "HAVING COUNT(DISTINCT dataset_id) > 1"
        ") "
        "SELECT canonical_var, country_code, observed_year, min_val, max_val, n_sources, "
        "(max_val - min_val) / NULLIF(ABS(mean_val), 0) AS relative_spread "
        "FROM multi_source "
        "WHERE (max_val - min_val) / NULLIF(ABS(mean_val), 0) > 0.15 "
        "ORDER BY relative_spread DESC "
        "LIMIT 20"
    ).fetchall()
    return QCCheck(
        name="cross_source_value_spread",
        passed=len(disagreements) <= 5,
        value=len(disagreements),
        threshold=5,
        severity="warning",
        message="Cross-source disagreements above 15% relative spread",
    )


def _non_blocking_smoke_check(check: QCCheck, *, message: str) -> QCCheck:
    return QCCheck(
        name=check.name,
        passed=True,
        severity="info",
        value=check.value,
        threshold=check.threshold,
        message=message,
    )


def run_qc(config: DatasetBatchConfig, *, fail_fast: bool | None = None) -> QCReport:
    started_at = datetime.now(UTC).isoformat()
    checks: list[QCCheck] = []
    metrics: dict[str, float | int] = {}
    smoke_like = _is_smoke_like_run(config)

    source_dirs = [p for p in config.raw_dir.iterdir() if p.is_dir()] if config.raw_dir.exists() else []
    manifest_actual_counts: dict[str, int] = {}

    parity_failures = 0
    zero_row_sources = 0
    for source_dir in source_dirs:
        manifest_path = _latest_manifest(source_dir)
        if not manifest_path:
            continue
        with open(manifest_path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        payload = Path(manifest.get("payload", ""))
        declared = int(manifest.get("count", 0))
        actual = _line_count(payload)
        manifest_actual_counts[source_dir.name] = actual
        if declared != actual:
            parity_failures += 1
        if actual == 0:
            zero_row_sources += 1

    metrics["zero_row_sources"] = zero_row_sources
    checks.append(
        QCCheck(
            name="manifest_count_parity",
            passed=parity_failures == 0,
            threshold=0,
            value=parity_failures,
            message="Number of raw manifests with count mismatch",
        )
    )
    registry_specs = {spec.name: spec for spec in config.load_registry().sources}
    rest_bytes_by_source: dict[str, int] = {}
    rest_rows_by_source: dict[str, int] = {}
    history_budget_exceeded_sources: list[str] = []
    for source, actual_rows in sorted(manifest_actual_counts.items()):
        spec = registry_specs.get(source)
        if spec is None or spec.family != "rest":
            continue
        manifest_path = _latest_manifest(config.raw_dir / source)
        payload_path = None
        if manifest_path is not None:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            payload_path = Path(payload.get("payload", ""))
        payload_bytes = _file_size(payload_path) if payload_path else 0
        rest_rows_by_source[source] = actual_rows
        rest_bytes_by_source[source] = payload_bytes
        rows_exceeded = spec.max_rows_per_snapshot is not None and actual_rows > int(spec.max_rows_per_snapshot)
        bytes_exceeded = spec.max_bytes_per_snapshot is not None and payload_bytes > int(spec.max_bytes_per_snapshot)
        if rows_exceeded or bytes_exceeded:
            history_budget_exceeded_sources.append(source)
            checks.append(
                QCCheck(
                    name=f"rest_history_budget_{source}",
                    passed=False,
                    severity="warning",
                    value=max(actual_rows, payload_bytes),
                    threshold=spec.max_rows_per_snapshot or spec.max_bytes_per_snapshot or 0,
                    message=f"REST snapshot budget exceeded for {source}",
                )
            )
    metrics["rest_rows_by_source"] = rest_rows_by_source
    metrics["rest_bytes_by_source"] = rest_bytes_by_source
    metrics["history_budget_exceeded_sources"] = history_budget_exceeded_sources
    metrics["source_publish_blocking"] = {
        spec.name: bool(spec.publish_blocking)
        for spec in sorted(registry_specs.values(), key=lambda item: item.name)
        if spec.enabled
    }
    previous_snapshot_root = _previous_snapshot_root(config)
    anomalies_total = 0
    anomaly_drops = 0
    anomaly_spikes = 0
    anomaly_baseline_resets = 0
    anomaly_checks_skipped = int(smoke_like)

    if previous_snapshot_root is not None and not anomaly_checks_skipped:
        execution_sources = {
            spec.name
            for spec in registry_specs.values()
            if spec.publish_blocking
        }
        for source, actual in sorted(manifest_actual_counts.items()):
            previous = _manifest_count_for_snapshot(previous_snapshot_root, source)
            if previous is None:
                continue
            spec = registry_specs.get(source)
            critical_source = source in set(config.promoted_sources) or source in execution_sources or bool(
                spec.publish_blocking if spec else False
            )
            if previous > 0 and actual == 0:
                anomalies_total += 1
                checks.append(
                    QCCheck(
                        name=f"source_anomaly_{source}_zero_after_nonzero",
                        passed=False,
                        severity="critical" if critical_source else "warning",
                        value=actual,
                        threshold=1,
                        message=(
                            f"Current raw count for '{source}' dropped to zero after previous snapshot had {previous} rows"
                        ),
                    )
                )
                continue
            if previous <= 0:
                continue
            delta_pct = round((100.0 * (actual - previous)) / previous, 3)
            if source == "wvs" and previous <= 5 and actual >= 10:
                anomaly_baseline_resets += 1
                logger.info(
                    "Skipping anomaly spike for WVS baseline reset: previous={}, current={}",
                    previous,
                    actual,
                )
                continue
            if delta_pct <= -70.0:
                anomalies_total += 1
                anomaly_drops += 1
                checks.append(
                    QCCheck(
                        name=f"source_anomaly_{source}_count_drop_pct",
                        passed=False,
                        severity="warning",
                        value=delta_pct,
                        threshold=-70.0,
                        message=(
                            f"Raw count for '{source}' changed from {previous} to {actual} rows vs previous snapshot"
                        ),
                    )
                )
            elif delta_pct >= 300.0:
                anomalies_total += 1
                anomaly_spikes += 1
                checks.append(
                    QCCheck(
                        name=f"source_anomaly_{source}_count_spike_pct",
                        passed=False,
                        severity="warning",
                        value=delta_pct,
                        threshold=300.0,
                        message=(
                            f"Raw count for '{source}' changed from {previous} to {actual} rows vs previous snapshot"
                        ),
                    )
                )

    metrics["source_anomalies_total"] = anomalies_total
    metrics["source_anomaly_drops_total"] = anomaly_drops
    metrics["source_anomaly_spikes_total"] = anomaly_spikes
    metrics["source_anomaly_baseline_resets_total"] = anomaly_baseline_resets
    metrics["source_anomaly_checks_skipped"] = anomaly_checks_skipped
    checks.append(
        QCCheck(
            name="source_anomalies_total",
            passed=anomalies_total == 0,
            severity="warning",
            value=anomalies_total,
            threshold=0,
            message="Total number of source count anomalies compared with previous snapshot",
        )
    )

    merged_total = 0
    description_qc_total = 0
    empty_title = 0
    empty_desc = 0
    if config.merged_records_path.exists():
        with open(config.merged_records_path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                merged_total += 1
                source = str(row.get("source", "")).strip()
                spec = registry_specs.get(source)
                if not _source_counts_towards_description_qc(spec):
                    continue
                description_qc_total += 1
                if not str(row.get("title", "")).strip():
                    empty_title += 1
                if not str(row.get("description", "")).strip():
                    empty_desc += 1

    title_pct = (100.0 * empty_title / description_qc_total) if description_qc_total else 0.0
    desc_pct = (100.0 * empty_desc / description_qc_total) if description_qc_total else 0.0
    metrics["merged_total"] = merged_total
    metrics["description_qc_total"] = description_qc_total
    metrics["empty_title_pct"] = round(title_pct, 3)
    metrics["empty_description_pct"] = round(desc_pct, 3)
    metrics["duplicate_ratio_pct"] = _duplicate_ratio(config, merged_total)

    checks.append(QCCheck(name="empty_title_pct", passed=title_pct <= 5.0, value=title_pct, threshold=5.0))
    checks.append(QCCheck(name="empty_description_pct", passed=desc_pct <= 60.0, value=desc_pct, threshold=60.0))

    reachable = 0
    checked = 0
    if config.db_path.exists():
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            rows = con.execute(
                "SELECT DISTINCT url FROM ds_distributions "
                "WHERE url IS NOT NULL AND length(trim(url)) > 0 LIMIT 500"
            ).fetchall()
        finally:
            con.close()

        urls = [str(r[0]) for r in rows if isinstance(r[0], str) and r[0].startswith(("http://", "https://"))]
        random.seed(42)
        sample = random.sample(urls, k=min(20, len(urls))) if urls else []
        for url in sample:
            checked += 1
            if _url_is_reachable(url, timeout=10):
                reachable += 1

    reach_pct = (100.0 * reachable / checked) if checked else 100.0
    metrics["url_sample_checked"] = checked
    metrics["url_sample_reachable_pct"] = round(reach_pct, 3)
    checks.append(
        QCCheck(
            name="url_sample_reachability_pct",
            passed=reach_pct >= 70.0,
            value=reach_pct,
            threshold=70.0,
            severity="warning" if checked == 0 else "critical",
        )
    )

    if config.db_path.exists():
        con = duckdb.connect(str(config.db_path), read_only=True)
        try:
            dataset_columns = _table_columns(con, "ds_datasets")
            distribution_columns = _table_columns(con, "ds_distributions")
            has_bindings = _table_exists(con, "ds_metric_bindings")
            has_schema_profiles = _table_exists(con, "ds_schema_profiles")
            has_alignments = _table_exists(con, "ds_variable_alignments")

            if distribution_columns:
                dist_total = _scalar(con, "SELECT count(*) FROM ds_distributions")
                metrics["distribution_total"] = int(dist_total)
                if "machine_readable" in distribution_columns:
                    machine_pct = _scalar(
                        con,
                        "SELECT 100.0 * avg(CASE WHEN machine_readable THEN 1 ELSE 0 END) FROM ds_distributions",
                    )
                elif "format" in distribution_columns:
                    machine_pct = _scalar(
                        con,
                        "SELECT 100.0 * avg(CASE WHEN upper(format) IN ('CSV','JSON','SDMX-JSON','XLSX','XLS','ODS') "
                        "THEN 1 ELSE 0 END) FROM ds_distributions",
                    )
                else:
                    machine_pct = 0.0

                if "parser_supported" in distribution_columns:
                    parser_pct = _scalar(
                        con,
                        "SELECT 100.0 * avg(CASE WHEN parser_supported THEN 1 ELSE 0 END) FROM ds_distributions",
                    )
                else:
                    parser_pct = 0.0

                metrics["machine_readable_distribution_pct"] = round(machine_pct, 3)
                metrics["parser_supported_distribution_pct"] = round(parser_pct, 3)

            if dataset_columns:
                dataset_total = _scalar(con, "SELECT count(*) FROM ds_datasets")
                metrics["dataset_total"] = int(dataset_total)
                temporal_pct = _scalar(
                    con,
                    "SELECT 100.0 * avg(CASE WHEN coalesce(coverage_time_start, temporal_start, '') != '' "
                    "OR coalesce(coverage_time_end, temporal_end, '') != '' THEN 1 ELSE 0 END) FROM ds_datasets",
                )
                geo_expr = (
                    "coalesce(array_length(coverage_countries), 0) > 0 "
                    "OR coalesce(array_length(coverage_regions), 0) > 0 "
                    "OR coalesce(spatial, '') != ''"
                )
                geographic_pct = _scalar(
                    con,
                    f"SELECT 100.0 * avg(CASE WHEN {geo_expr} THEN 1 ELSE 0 END) FROM ds_datasets",
                )
                readiness_avg = _scalar(
                    con,
                    "SELECT avg(coalesce(quality_execution_readiness_score, 0.0)) FROM ds_datasets",
                )
                metrics["datasets_with_temporal_coverage_pct"] = round(temporal_pct, 3)
                metrics["datasets_with_geographic_coverage_pct"] = round(geographic_pct, 3)
                metrics["execution_readiness_score_avg"] = round(readiness_avg, 4)

                if has_bindings:
                    bindings_pct = _scalar(
                        con,
                        "SELECT 100.0 * count(DISTINCT b.dataset_id) / NULLIF(count(DISTINCT d.id), 0) "
                        "FROM ds_datasets d LEFT JOIN ds_metric_bindings b ON b.dataset_id = d.id",
                    )
                    metrics["datasets_with_metric_binding_pct"] = round(bindings_pct, 3)
                    metrics["core_metric_resolve_pct"] = round(bindings_pct, 3)
                else:
                    metrics["datasets_with_metric_binding_pct"] = 0.0
                    metrics["core_metric_resolve_pct"] = 0.0

                if has_schema_profiles:
                    schema_pct = _scalar(
                        con,
                        "SELECT 100.0 * count(DISTINCT s.dataset_id) / NULLIF(count(DISTINCT d.id), 0) "
                        "FROM ds_datasets d LEFT JOIN ds_schema_profiles s ON s.dataset_id = d.id",
                    )
                    metrics["datasets_with_schema_profile_pct"] = round(schema_pct, 3)
                else:
                    metrics["datasets_with_schema_profile_pct"] = 0.0

                if _table_exists(con, "ds_observations"):
                    coverage_variables = (
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
                    )
                    active_countries = tuple(config.resolved_active_countries[:10])
                    coverage_check = _check_observation_coverage(
                        con,
                        countries=active_countries,
                        variables=coverage_variables,
                        year_range=config.resolved_year_window,
                    )
                    metrics["observation_coverage_pct"] = float(coverage_check.value or 0.0)
                    heatmap = _generate_coverage_heatmap(
                        con,
                        countries=active_countries,
                        variables=coverage_variables,
                        year_range=config.resolved_year_window,
                    )
                    heatmap_path = _coverage_heatmap_path(config)
                    heatmap_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(heatmap_path, "w", encoding="utf-8") as fh:
                        json.dump(heatmap, fh, ensure_ascii=False, indent=2)
                    metrics["coverage_heatmap_path"] = str(heatmap_path)
                    cross_source_check = _check_cross_source_consistency(con)
                    if smoke_like:
                        checks.append(
                            _non_blocking_smoke_check(
                                coverage_check,
                                message="Observation coverage recorded for smoke/preflight run but not enforced as blocking gate",
                            )
                        )
                        checks.append(
                            _non_blocking_smoke_check(
                                cross_source_check,
                                message="Cross-source spread recorded for smoke/preflight run but not enforced as blocking gate",
                            )
                        )
                    else:
                        checks.append(coverage_check)
                        checks.append(cross_source_check)

                if has_alignments and "execution_tier" in dataset_columns:
                    transport_pct = _scalar(
                        con,
                        "SELECT 100.0 * avg(CASE WHEN EXISTS ("
                        "  SELECT 1 FROM ds_variable_alignments va "
                        "  WHERE va.dataset_id IN (d.id, d.dataset_id, coalesce(NULLIF(d.source_dataset_id, ''), d.dataset_id, d.id))"
                        ") THEN 1 ELSE 0 END) "
                        "FROM ds_datasets d WHERE d.execution_tier = 'transport_ready'",
                    )
                    metrics["transport_ready_var_coverage_pct"] = round(transport_pct, 3)
                else:
                    metrics["transport_ready_var_coverage_pct"] = 0.0

                core_ingest_manifest = config.manifests_dir / "core_sources_ingest.json"
                if core_ingest_manifest.exists():
                    with open(core_ingest_manifest, "r", encoding="utf-8") as fh:
                        ingest_manifest = json.load(fh)
                    ingest_metrics = ingest_manifest.get("metrics") if isinstance(ingest_manifest, dict) else {}
                    if isinstance(ingest_metrics, dict):
                        for key in (
                            "observations_attempted",
                            "observations_inserted",
                            "observations_replaced",
                        ):
                            metrics[key] = int(ingest_metrics.get(key, 0) or 0)

                execution_sources = sorted(
                    spec.name
                    for spec in registry_specs.values()
                    if spec.execution_tier != "catalog"
                )
                for source in execution_sources:
                    dataset_count = _scalar(con, "SELECT count(*) FROM ds_datasets WHERE source = ?", [source])
                    if dataset_count <= 0:
                        continue

                    if distribution_columns and "parser_supported" in distribution_columns:
                        parser_source_pct = _scalar(
                            con,
                            "SELECT 100.0 * avg(CASE WHEN dist.parser_supported THEN 1 ELSE 0 END) "
                            "FROM ds_distributions dist "
                            "JOIN ds_datasets ds ON ds.id = dist.dataset_id "
                            "WHERE ds.source = ?",
                            [source],
                        )
                        checks.append(
                            QCCheck(
                                name=f"{source}_execution_parser_supported_distribution_pct",
                                passed=parser_source_pct >= 70.0,
                                value=parser_source_pct,
                                threshold=70.0,
                                severity="warning",
                            )
                        )

                    readiness_source_avg = _scalar(
                        con,
                        "SELECT avg(coalesce(quality_execution_readiness_score, 0.0)) "
                        "FROM ds_datasets WHERE source = ?",
                        [source],
                    )
                    checks.append(
                        QCCheck(
                            name=f"{source}_execution_readiness_score_avg",
                            passed=readiness_source_avg >= 0.55,
                            value=readiness_source_avg,
                            threshold=0.55,
                            severity="warning",
                        )
                    )

                promoted_sources = set(config.promoted_sources)
                for source in sorted(promoted_sources):
                    actual = manifest_actual_counts.get(source, 0)
                    checks.append(
                        QCCheck(
                            name=f"promoted_{source}_nonempty",
                            passed=actual > 0,
                            value=actual,
                            threshold=1,
                            message=f"Latest raw snapshot row count for promoted source '{source}'",
                        )
                    )
                    dataset_count = _scalar(con, "SELECT count(*) FROM ds_datasets WHERE source = ?", [source])
                    if dataset_count <= 0:
                        continue

                    if distribution_columns and "parser_supported" in distribution_columns:
                        parser_source_pct = _scalar(
                            con,
                            "SELECT 100.0 * avg(CASE WHEN dist.parser_supported THEN 1 ELSE 0 END) "
                            "FROM ds_distributions dist "
                            "JOIN ds_datasets ds ON ds.id = dist.dataset_id "
                            "WHERE ds.source = ?",
                            [source],
                        )
                        checks.append(
                            QCCheck(
                                name=f"promoted_{source}_parser_supported_distribution_pct",
                                passed=parser_source_pct >= 80.0,
                                value=parser_source_pct,
                                threshold=80.0,
                            )
                        )

                    if has_bindings:
                        binding_source_pct = _scalar(
                            con,
                            "SELECT 100.0 * count(DISTINCT b.dataset_id) / NULLIF(count(DISTINCT ds.id), 0) "
                            "FROM ds_datasets ds LEFT JOIN ds_metric_bindings b ON b.dataset_id = ds.id "
                            "WHERE ds.source = ?",
                            [source],
                        )
                        checks.append(
                            QCCheck(
                                name=f"promoted_{source}_metric_binding_pct",
                                passed=binding_source_pct >= 85.0,
                                value=binding_source_pct,
                                threshold=85.0,
                            )
                        )

                    if has_alignments and "execution_tier" in dataset_columns:
                        transport_source_pct = _scalar(
                            con,
                            "SELECT 100.0 * avg(CASE WHEN EXISTS ("
                            "  SELECT 1 FROM ds_variable_alignments va "
                            "  WHERE va.dataset_id IN ("
                            "    ds.id, "
                            "    coalesce(NULLIF(ds.source_dataset_id, ''), ds.dataset_id), "
                            "    ds.dataset_id"
                            "  )"
                            ") THEN 1 ELSE 0 END) "
                            "FROM ds_datasets ds "
                            "WHERE ds.source = ? "
                            "AND coalesce(NULLIF(ds.execution_tier, ''), 'catalog') <> 'catalog'",
                            [source],
                        )
                        checks.append(
                            QCCheck(
                                name=f"promoted_{source}_transport_ready_alignment_pct",
                                passed=transport_source_pct >= 1.0,
                                value=transport_source_pct,
                                threshold=1.0,
                                severity="critical",
                            )
                        )
        finally:
            con.close()

    if config.benchmark_report_path.exists():
        with open(config.benchmark_report_path, "r", encoding="utf-8") as fh:
            benchmark_payload = json.load(fh)
        benchmark_metrics = benchmark_payload.get("metrics") if isinstance(benchmark_payload, dict) else {}
        if isinstance(benchmark_metrics, dict):
            readiness_thresholds = readiness_thresholds_for_profile(config.run_profile)
            active_thresholds = active_readiness_thresholds_for_profile(config.run_profile)
            vector_index_available = bool(benchmark_metrics.get("benchmark_search_vector_index_available", 0))
            for key, value in benchmark_metrics.items():
                if isinstance(value, (int, float)):
                    metrics[key] = value
            for metric_name, threshold in active_thresholds.items():
                if metric_name not in benchmark_metrics:
                    continue
                value = float(benchmark_metrics.get(metric_name, 0.0) or 0.0)
                severity = "critical"
                effective_threshold = threshold
                message = ""
                if (
                    smoke_like
                    and metric_name == "benchmark_search_top5_relevance_pct"
                    and not vector_index_available
                ):
                    severity = "warning"
                    effective_threshold = min(threshold, 50.0)
                    message = "Sampled/text-only run without vector index; search threshold relaxed for smoke QC"
                checks.append(
                    QCCheck(
                        name=metric_name,
                        passed=value >= effective_threshold,
                        severity=severity,
                        value=value,
                        threshold=effective_threshold,
                        message=message,
                    )
                )
            metrics["benchmark_thresholds"] = readiness_thresholds
    else:
        checks.append(
            QCCheck(
                name="benchmark_report_present",
                passed=False,
                severity="warning",
                value=0,
                threshold=1,
                message="Benchmark stage has not produced benchmark_report.json",
            )
        )

    report = QCReport(scope="datasets", checks=checks, metrics=metrics)
    write_qc_report(config.qc_report_path, report)
    write_stage_manifest(
        manifest_path=config.manifests_dir / "qc.json",
        stage="qc",
        status="ok" if report.passed else "failed",
        metrics={"passed": report.passed, **metrics},
        artifacts=[config.qc_report_path],
        started_at=started_at,
    )
    evaluate_fail_fast(report, fail_fast=config.fail_fast_qc if fail_fast is None else fail_fast)
    return report
