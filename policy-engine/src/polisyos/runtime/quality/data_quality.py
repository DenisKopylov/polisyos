"""Production data quality diagnostics for serious runtime runs."""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

DIAGNOSTIC_KEYS = (
    "schema_drift",
    "missingness",
    "outliers",
    "duplicate_entity_collisions",
    "unit_drift",
    "temporal_leakage",
    "cohort_leakage",
    "label_quality",
    "construct_validity",
    "coverage",
    "recency_ttl",
    "data_dictionary",
)
PRODUCTION_DATA_QUALITY_SCHEMA_VERSION = "policyos.runtime.production_data_quality.v1"
PRODUCTION_DATA_QUALITY_REF_KEY = "production_data_quality_report_ref"
_MISSING_MARKERS = {"", "na", "n/a", "nan", "none", "null", "missing"}
_FIXTURE_MARKERS = ("fixture", "mock", "stub", "sample_data", "testdata")
_MATERIALIZATION_REF_KEYS = (
    "data_snapshot_ref",
    "input_bindings_ref",
    "registry_bundle_ref",
    "quality_report_ref",
)


def build_production_data_quality_report(
    *,
    production_data_root: str | Path | None,
    evidence_context: Mapping[str, Any],
    materialization_refs: Mapping[str, Any],
    data_needs: Sequence[Mapping[str, Any]] | None = None,
    claims: Sequence[Mapping[str, Any]] | None = None,
    now: datetime | None = None,
    degrade_reason: str | None = None,
) -> dict[str, Any]:
    """Build a runtime-owned quality report for the materialized production data."""

    generated_at = _utc(now)
    root = _coerce_root(production_data_root, evidence_context)
    bundles = _context_bundles(evidence_context)
    materialization = _clean_refs(materialization_refs)
    data_need_rows = [dict(item) for item in data_needs or [] if isinstance(item, Mapping)]
    claim_rows = [dict(item) for item in claims or [] if isinstance(item, Mapping)]
    issues: list[dict[str, Any]] = []
    bundle_reports: list[dict[str, Any]] = []
    diagnostics = {key: _diagnostic(key) for key in DIAGNOSTIC_KEYS}
    source_bundle_versions = {
        role: str(bundle.get("version_id"))
        for role, bundle in bundles.items()
        if _text(bundle.get("version_id"))
    }
    row_counts: dict[str, int] = {}
    entity_counts: dict[str, int] = {}

    if root is None or not root.exists():
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message="Production data root is missing or unresolved.",
            next_action="Provide a real POLISYOS_PRODUCTION_DATA_ROOT with a manifest.",
        )
    if _looks_fixture_like(root):
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message="Production data root looks fixture-like.",
            next_action="Run serious profiles with non-fixture production evidence.",
        )
    if not _text(evidence_context.get("manifest_sha256")):
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message="Production data manifest checksum is missing.",
            next_action="Resolve the production-data manifest before materialization.",
        )
    if not bundles:
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message="Production data evidence context has no source bundles.",
            next_action="Use a manifest with versioned production source bundles.",
        )
    for ref_key in _MATERIALIZATION_REF_KEYS:
        ref_value = materialization.get(ref_key)
        if not ref_value or _looks_fixture_like(ref_value):
            _add_issue(
                issues,
                diagnostics["schema_drift"],
                code="production_data_quality_missing",
                severity="fail",
                message=f"Materialization ref {ref_key} is missing or fixture-like.",
                next_action=(
                    "Persist real production snapshot, bindings, registry, and quality refs."
                ),
                ref_key=ref_key,
            )

    for role, bundle in bundles.items():
        bundle_report = _inspect_bundle(
            role=role,
            bundle=bundle,
            root=root,
            data_needs=data_need_rows,
            now=generated_at,
        )
        bundle_reports.append(bundle_report)
        row_counts[role] = int(bundle_report.get("row_count") or 0)
        entity_counts[role] = int(bundle_report.get("entity_count") or 0)
        for diagnostic_key, diagnostic in bundle_report["diagnostics"].items():
            _merge_diagnostic(diagnostics[diagnostic_key], diagnostic)
        issues.extend(bundle_report["issues"])

    claim_diagnostics = _claim_diagnostics(
        claims=claim_rows,
        issues=issues,
    )
    if any(item["major"] and item["status"] == "fail" for item in claim_diagnostics):
        _add_issue(
            issues,
            diagnostics["construct_validity"],
            code="major_recommendation_data_quality_degrade_reason_missing",
            severity="fail",
            message=(
                "A major data-backed recommendation is affected by failing production "
                "data quality diagnostics and has no explicit degrade reason."
            ),
            next_action=(
                "Block production approval or provide a signed degrade reason tied to "
                "the affected recommendation."
            ),
            affects_major_recommendation=True,
        )

    for diagnostic in diagnostics.values():
        diagnostic["status"] = _status_from_issues(diagnostic.get("findings") or [])

    report: dict[str, Any] = {
        "schema_version": PRODUCTION_DATA_QUALITY_SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "status": "pass",
        "source": "production_data_manifest",
        "production_data_root": str(root) if root is not None else None,
        "manifest_path": _text(evidence_context.get("manifest_path")),
        "manifest_checksum": _text(evidence_context.get("manifest_sha256")),
        "manifest_sha256": _text(evidence_context.get("manifest_sha256")),
        "source_bundle_versions": source_bundle_versions,
        "bundles": bundle_reports,
        "data_snapshot_ref": materialization.get("data_snapshot_ref"),
        "input_bindings_ref": materialization.get("input_bindings_ref"),
        "registry_bundle_ref": materialization.get("registry_bundle_ref"),
        "quality_report_ref": materialization.get("quality_report_ref"),
        PRODUCTION_DATA_QUALITY_REF_KEY: materialization.get(PRODUCTION_DATA_QUALITY_REF_KEY),
        "fabric_retrieval_trace_ref": materialization.get("fabric_retrieval_trace_ref"),
        "row_counts": row_counts,
        "entity_counts": entity_counts,
        "diagnostics": diagnostics,
        "claim_diagnostics": claim_diagnostics,
        "issues": issues,
        "data_needs": data_need_rows,
    }
    if degrade_reason:
        report["degrade_reason"] = degrade_reason
    return normalize_production_data_quality_report(report)


def normalize_production_data_quality_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize status and issue severities for scorecard consumption."""

    payload = {str(key): _json_value(value) for key, value in report.items()}
    raw_issues = payload.get("issues")
    issues = (
        [dict(item) for item in raw_issues if isinstance(item, Mapping)]
        if isinstance(raw_issues, list)
        else []
    )
    degrade_reason = _text(payload.get("degrade_reason"))
    normalized_issues: list[dict[str, Any]] = []
    raw_report_status = str(payload.get("status") or "").strip().casefold()
    for issue in issues:
        normalized = dict(issue)
        if (
            "severity" not in normalized
            and "status" not in normalized
            and raw_report_status in {"fail", "failed", "error", "blocked"}
        ):
            normalized["severity"] = "fail"
        severity = _severity(normalized)
        if (
            severity == "fail"
            and degrade_reason
            and bool(normalized.get("affects_major_recommendation"))
        ):
            severity = "warn"
            normalized["degraded"] = True
            normalized["degrade_reason"] = degrade_reason
        normalized["severity"] = severity
        normalized["status"] = severity
        normalized_issues.append(normalized)
    payload["issues"] = normalized_issues

    diagnostics = payload.get("diagnostics")
    if isinstance(diagnostics, Mapping):
        normalized_diagnostics: dict[str, Any] = {}
        for key in DIAGNOSTIC_KEYS:
            diagnostic = diagnostics.get(key)
            if isinstance(diagnostic, Mapping):
                diagnostic_payload = dict(diagnostic)
            else:
                diagnostic_payload = _diagnostic(key)
            diagnostic_payload["status"] = _status_from_issues(
                diagnostic_payload.get("findings") or []
            )
            normalized_diagnostics[key] = diagnostic_payload
        payload["diagnostics"] = normalized_diagnostics

    if any(_severity(issue) == "fail" for issue in normalized_issues):
        payload["status"] = "fail"
    elif any(_severity(issue) == "warn" for issue in normalized_issues):
        payload["status"] = "warn"
    else:
        payload["status"] = "pass"
    payload.setdefault("schema_version", PRODUCTION_DATA_QUALITY_SCHEMA_VERSION)
    return payload


def _inspect_bundle(
    *,
    role: str,
    bundle: Mapping[str, Any],
    root: Path | None,
    data_needs: list[dict[str, Any]],
    now: datetime,
) -> dict[str, Any]:
    diagnostics = {key: _diagnostic(key) for key in DIAGNOSTIC_KEYS}
    issues: list[dict[str, Any]] = []
    bundle_root = _bundle_root(root, bundle)
    data_paths = _data_paths(root, bundle, bundle_root)
    dictionary_path = _metadata_path(root, bundle, "data_dictionary_path", bundle_root)
    dictionary = _load_json_mapping(dictionary_path) if dictionary_path is not None else {}
    rows, columns, row_sources = _load_bundle_rows(data_paths)
    row_count = len(rows)
    dictionary_columns = _dictionary_columns(dictionary)
    entity_columns = _column_list(dictionary, "entity_id_columns") or _matching_columns(
        columns,
        ("entity_id", "entity", "firm_id", "unit_id", "id"),
    )
    time_columns = _column_list(dictionary, "time_columns") or _matching_columns(
        columns,
        ("period", "date", "time", "year", "month"),
    )
    geography_columns = _column_list(dictionary, "geography_columns") or _matching_columns(
        columns,
        ("geography", "country", "country_code", "jurisdiction", "region"),
    )
    population_columns = _column_list(dictionary, "population_columns") or _matching_columns(
        columns,
        ("population", "cohort_population", "target_population"),
    )
    metric_columns = _metric_columns(data_needs, columns, dictionary_columns)

    _bundle_presence_checks(
        role=role,
        bundle=bundle,
        bundle_root=bundle_root,
        data_paths=data_paths,
        row_count=row_count,
        dictionary=dictionary,
        dictionary_path=dictionary_path,
        diagnostics=diagnostics,
        issues=issues,
    )
    _schema_drift_checks(
        role=role,
        bundle=bundle,
        columns=columns,
        dictionary_columns=dictionary_columns,
        diagnostics=diagnostics,
        issues=issues,
    )
    _missingness_checks(
        role=role,
        rows=rows,
        columns=columns,
        metric_columns=metric_columns,
        diagnostics=diagnostics,
        issues=issues,
    )
    _outlier_checks(role=role, rows=rows, columns=columns, diagnostics=diagnostics, issues=issues)
    entity_count = _entity_count(rows, entity_columns)
    _duplicate_checks(
        role=role,
        rows=rows,
        entity_columns=entity_columns,
        time_columns=time_columns,
        diagnostics=diagnostics,
        issues=issues,
    )
    _unit_drift_checks(
        role=role,
        data_needs=data_needs,
        dictionary=dictionary,
        diagnostics=diagnostics,
        issues=issues,
    )
    _temporal_leakage_checks(
        role=role,
        rows=rows,
        time_columns=time_columns,
        now=now,
        diagnostics=diagnostics,
        issues=issues,
    )
    _cohort_leakage_checks(
        role=role,
        rows=rows,
        columns=columns,
        diagnostics=diagnostics,
        issues=issues,
    )
    _label_quality_checks(
        role=role,
        rows=rows,
        columns=columns,
        metric_columns=metric_columns,
        dictionary=dictionary,
        diagnostics=diagnostics,
        issues=issues,
    )
    _construct_validity_checks(
        role=role,
        data_needs=data_needs,
        columns=columns,
        dictionary=dictionary,
        diagnostics=diagnostics,
        issues=issues,
    )
    _coverage_checks(
        role=role,
        rows=rows,
        geography_columns=geography_columns,
        population_columns=population_columns,
        dictionary=dictionary,
        data_needs=data_needs,
        diagnostics=diagnostics,
        issues=issues,
    )
    _recency_checks(
        role=role,
        bundle=bundle,
        dictionary=dictionary,
        now=now,
        diagnostics=diagnostics,
        issues=issues,
    )
    _data_dictionary_checks(
        role=role,
        dictionary=dictionary,
        dictionary_columns=dictionary_columns,
        metric_columns=metric_columns,
        diagnostics=diagnostics,
        issues=issues,
    )

    for diagnostic in diagnostics.values():
        diagnostic["status"] = _status_from_issues(diagnostic.get("findings") or [])

    return {
        "role": role,
        "version_id": _text(bundle.get("version_id")),
        "readiness": _text(bundle.get("readiness")),
        "path": str(bundle_root) if bundle_root is not None else _text(bundle.get("path")),
        "row_count": row_count,
        "entity_count": entity_count,
        "columns": columns,
        "row_sources": [str(path) for path in row_sources],
        "data_dictionary_path": str(dictionary_path) if dictionary_path is not None else None,
        "diagnostics": diagnostics,
        "issues": issues,
    }


def _bundle_presence_checks(
    *,
    role: str,
    bundle: Mapping[str, Any],
    bundle_root: Path | None,
    data_paths: list[Path],
    row_count: int,
    dictionary: Mapping[str, Any],
    dictionary_path: Path | None,
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    readiness = _text(bundle.get("readiness"))
    if _looks_fixture_like(bundle_root) or _looks_fixture_like(bundle.get("path")):
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message=f"Bundle {role} path looks fixture-like.",
            next_action="Replace fixture-like bundle paths with real production bundle versions.",
            bundle_role=role,
        )
    if readiness and any(marker in readiness.casefold() for marker in _FIXTURE_MARKERS):
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message=f"Bundle {role} readiness is fixture-like: {readiness}.",
            next_action="Use a ready production bundle for serious runs.",
            bundle_role=role,
        )
    for required in _list_text(bundle.get("required_files")):
        candidate = (bundle_root / required) if bundle_root is not None else None
        if candidate is not None and candidate.exists():
            continue
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message=f"Bundle {role} required file is missing: {required}.",
            next_action="Repair the production data bundle or regenerate its manifest.",
            bundle_role=role,
            path=required,
        )
    if not data_paths:
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="production_data_quality_missing",
            severity="fail",
            message=f"Bundle {role} has no inspectable tabular production data file.",
            next_action="Point the bundle manifest at CSV, JSONL, JSON, Parquet, or DuckDB data.",
            bundle_role=role,
        )
    if row_count <= 0:
        _add_issue(
            issues,
            diagnostics["coverage"],
            code="production_data_quality_missing",
            severity="fail",
            message=f"Bundle {role} has no observed rows in inspectable production data.",
            next_action="Materialize a non-empty production snapshot before approval.",
            bundle_role=role,
        )
    if dictionary_path is None or not dictionary:
        _add_issue(
            issues,
            diagnostics["data_dictionary"],
            code="data_dictionary_missing",
            severity="fail",
            message=f"Bundle {role} has no usable data dictionary.",
            next_action="Add a data_dictionary_path with column descriptions, roles, and units.",
            bundle_role=role,
        )


def _schema_drift_checks(
    *,
    role: str,
    bundle: Mapping[str, Any],
    columns: list[str],
    dictionary_columns: dict[str, dict[str, Any]],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    expected = _list_text(bundle.get("expected_schema")) or _list_text(
        bundle.get("required_columns")
    )
    if not expected and dictionary_columns:
        expected = list(dictionary_columns)
    if not expected or not columns:
        return
    missing = [column for column in expected if column not in columns]
    extra = [column for column in columns if column not in expected]
    if missing:
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="schema_drift_missing_columns",
            severity="fail",
            message=f"Bundle {role} is missing expected columns: {', '.join(missing[:8])}.",
            next_action="Refresh the bundle or update the manifest schema contract.",
            bundle_role=role,
            columns=missing,
        )
    if extra:
        _add_issue(
            issues,
            diagnostics["schema_drift"],
            code="schema_drift_extra_columns",
            severity="warn",
            message=f"Bundle {role} has columns not described by its schema contract.",
            next_action="Update the data dictionary or remove uncontracted columns.",
            bundle_role=role,
            columns=extra[:20],
        )


def _missingness_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    metric_columns: set[str],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if not rows or not columns:
        return
    rates: dict[str, float] = {}
    for column in columns:
        missing = sum(1 for row in rows if _is_missing(row.get(column)))
        rates[column] = round(missing / len(rows), 6)
    high_missing = {
        column: rate
        for column, rate in rates.items()
        if rate > (0.10 if column in metric_columns else 0.25)
    }
    if high_missing:
        severity = "fail" if any(rate > 0.25 for rate in high_missing.values()) else "warn"
        _add_issue(
            issues,
            diagnostics["missingness"],
            code="production_data_missingness_high",
            severity=severity,
            message=f"Bundle {role} has high missingness in production columns.",
            next_action="Refresh upstream extracts or document a degrade reason before approval.",
            bundle_role=role,
            rates=high_missing,
            metric_ids=sorted(metric_columns.intersection(high_missing)),
            affects_major_recommendation=bool(metric_columns.intersection(high_missing)),
        )
    diagnostics["missingness"]["summary"] = {"rates": rates}


def _outlier_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    ratios: dict[str, float] = {}
    for column in columns:
        values = [_to_float(row.get(column)) for row in rows]
        numeric = sorted(value for value in values if value is not None and math.isfinite(value))
        if len(numeric) < 4:
            continue
        lower_half = numeric[: len(numeric) // 2]
        upper_half = numeric[(len(numeric) + 1) // 2 :]
        q1 = median(lower_half)
        q3 = median(upper_half)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lower = q1 - 3 * iqr
        upper = q3 + 3 * iqr
        outliers = [value for value in numeric if value < lower or value > upper]
        if outliers:
            ratios[column] = round(len(outliers) / len(numeric), 6)
    high = {column: ratio for column, ratio in ratios.items() if ratio > 0.05}
    if high:
        _add_issue(
            issues,
            diagnostics["outliers"],
            code="production_data_outlier_ratio_high",
            severity="fail" if any(value > 0.20 for value in high.values()) else "warn",
            message=f"Bundle {role} has elevated numeric outlier ratios.",
            next_action="Inspect source extracts, winsorization policy, and unit encodings.",
            bundle_role=role,
            ratios=high,
        )
    diagnostics["outliers"]["summary"] = {"ratios": ratios}


def _duplicate_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    entity_columns: list[str],
    time_columns: list[str],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if not rows or not entity_columns:
        return
    key_columns = [column for column in [*entity_columns, *time_columns] if column]
    counts = Counter(tuple(str(row.get(column) or "") for column in key_columns) for row in rows)
    collisions = sum(count - 1 for count in counts.values() if count > 1)
    if collisions:
        _add_issue(
            issues,
            diagnostics["duplicate_entity_collisions"],
            code="duplicate_entity_collision",
            severity="fail",
            message=f"Bundle {role} has duplicate entity/time rows.",
            next_action="Deduplicate entity observations or add disambiguating keys.",
            bundle_role=role,
            duplicate_count=collisions,
            key_columns=key_columns,
        )
    diagnostics["duplicate_entity_collisions"]["summary"] = {
        "duplicate_count": collisions,
        "key_columns": key_columns,
    }


def _unit_drift_checks(
    *,
    role: str,
    data_needs: list[dict[str, Any]],
    dictionary: Mapping[str, Any],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    dictionary_columns = _dictionary_columns(dictionary)
    units_by_metric = _units_by_metric(dictionary_columns)
    mismatches: list[dict[str, str]] = []
    for need in data_needs:
        metric = _metric_id_from_need(need)
        expected_unit = _text(need.get("unit") or need.get("expected_unit"))
        if not metric or not expected_unit:
            continue
        observed_unit = units_by_metric.get(metric)
        if observed_unit and observed_unit.casefold() != expected_unit.casefold():
            mismatches.append(
                {
                    "metric_id": metric,
                    "expected_unit": expected_unit,
                    "observed_unit": observed_unit,
                }
            )
    if mismatches:
        _add_issue(
            issues,
            diagnostics["unit_drift"],
            code="unit_drift_detected",
            severity="fail",
            message=f"Bundle {role} has metric unit drift against data needs.",
            next_action="Align units before method execution or record a typed conversion.",
            bundle_role=role,
            mismatches=mismatches,
            metric_ids=[item["metric_id"] for item in mismatches],
            affects_major_recommendation=True,
        )


def _temporal_leakage_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    time_columns: list[str],
    now: datetime,
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    future_values: list[str] = []
    for column in time_columns:
        for row in rows:
            parsed = _parse_datetime(row.get(column))
            if parsed is not None and parsed > now:
                future_values.append(str(row.get(column)))
    if future_values:
        _add_issue(
            issues,
            diagnostics["temporal_leakage"],
            code="temporal_leakage_future_observations",
            severity="fail",
            message=f"Bundle {role} contains observations after the run as-of timestamp.",
            next_action="Exclude post-decision observations from production materialization.",
            bundle_role=role,
            examples=future_values[:5],
            affects_major_recommendation=True,
        )


def _cohort_leakage_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    leakage_terms = {"test", "holdout", "future", "post_treatment", "leakage"}
    suspect_columns = [
        column
        for column in columns
        if any(token in column.casefold() for token in ("cohort", "split", "sample", "lane"))
    ]
    hits: list[dict[str, str]] = []
    for column in suspect_columns:
        for row in rows:
            value = str(row.get(column) or "").strip().casefold()
            if value in leakage_terms:
                hits.append({"column": column, "value": value})
    if hits:
        _add_issue(
            issues,
            diagnostics["cohort_leakage"],
            code="cohort_leakage_detected",
            severity="fail",
            message=f"Bundle {role} includes holdout/future cohort markers.",
            next_action="Remove evaluation or future cohorts from production materialization.",
            bundle_role=role,
            examples=hits[:10],
            affects_major_recommendation=True,
        )


def _label_quality_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    metric_columns: set[str],
    dictionary: Mapping[str, Any],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    label_columns = _matching_columns(columns, ("label_quality", "label_status", "audit_status"))
    if label_columns:
        weak_values: list[dict[str, str]] = []
        for column in label_columns:
            for row in rows:
                value = str(row.get(column) or "").strip().casefold()
                if value and value not in {"audited", "verified", "validated", "official"}:
                    weak_values.append({"column": column, "value": value})
        if weak_values:
            _add_issue(
                issues,
                diagnostics["label_quality"],
                code="label_quality_weak",
                severity="fail",
                message=f"Bundle {role} has unaudited or weak label-quality markers.",
                next_action="Audit labels or quarantine affected outcome columns.",
                bundle_role=role,
                examples=weak_values[:10],
                affects_major_recommendation=bool(metric_columns),
            )
        return
    if metric_columns and not _text(dictionary.get("label_quality")):
        _add_issue(
            issues,
            diagnostics["label_quality"],
            code="label_quality_metadata_missing",
            severity="warn",
            message=f"Bundle {role} lacks explicit label-quality metadata for metric columns.",
            next_action="Record label audit status for production outcome/treatment variables.",
            bundle_role=role,
            metric_ids=sorted(metric_columns),
        )


def _construct_validity_checks(
    *,
    role: str,
    data_needs: list[dict[str, Any]],
    columns: list[str],
    dictionary: Mapping[str, Any],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    dictionary_columns = _dictionary_columns(dictionary)
    available_metrics = set(columns)
    for column_name, info in dictionary_columns.items():
        available_metrics.add(column_name)
        metric_id = _text(info.get("metric_id") or info.get("metric"))
        if metric_id:
            available_metrics.add(metric_id)
    missing_metrics = [
        metric
        for metric in (_metric_id_from_need(need) for need in data_needs)
        if metric and metric not in available_metrics
    ]
    if missing_metrics:
        _add_issue(
            issues,
            diagnostics["construct_validity"],
            code="construct_validity_metric_missing",
            severity="fail",
            message=f"Bundle {role} does not expose requested production metric(s).",
            next_action="Bind requested outcomes/treatments to dictionary-backed columns.",
            bundle_role=role,
            metric_ids=missing_metrics,
            affects_major_recommendation=True,
        )


def _coverage_checks(
    *,
    role: str,
    rows: list[dict[str, Any]],
    geography_columns: list[str],
    population_columns: list[str],
    dictionary: Mapping[str, Any],
    data_needs: list[dict[str, Any]],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    observed_geographies = _observed_values(rows, geography_columns)
    observed_populations = _observed_values(rows, population_columns)
    coverage_meta = (
        dictionary.get("coverage") if isinstance(dictionary.get("coverage"), Mapping) else {}
    )
    if not observed_geographies:
        observed_geographies = set(_list_text(coverage_meta.get("geographies")))
    if not observed_populations:
        observed_populations = set(_list_text(coverage_meta.get("populations")))
    missing_geographies = []
    missing_populations = []
    for need in data_needs:
        geography = _text(need.get("geography") or need.get("country") or need.get("jurisdiction"))
        population = _text(need.get("population") or need.get("target_population"))
        if geography and observed_geographies and geography not in observed_geographies:
            missing_geographies.append(geography)
        if population and observed_populations and population not in observed_populations:
            missing_populations.append(population)
    if missing_geographies or missing_populations:
        _add_issue(
            issues,
            diagnostics["coverage"],
            code="production_data_coverage_gap",
            severity="fail",
            message=f"Bundle {role} coverage does not match requested geography/population.",
            next_action="Materialize a production snapshot covering the requested cohort.",
            bundle_role=role,
            missing_geographies=sorted(set(missing_geographies)),
            missing_populations=sorted(set(missing_populations)),
            affects_major_recommendation=True,
        )
    diagnostics["coverage"]["summary"] = {
        "geographies": sorted(observed_geographies),
        "populations": sorted(observed_populations),
    }


def _recency_checks(
    *,
    role: str,
    bundle: Mapping[str, Any],
    dictionary: Mapping[str, Any],
    now: datetime,
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    raw_updated = (
        dictionary.get("updated_at")
        or dictionary.get("last_updated")
        or bundle.get("updated_at")
        or bundle.get("generated_at")
    )
    updated_at = _parse_datetime(raw_updated)
    ttl_days = _int_or_default(
        bundle.get("recency_ttl_days")
        or bundle.get("data_quality_ttl_days")
        or dictionary.get("recency_ttl_days"),
        90,
    )
    if updated_at is None:
        _add_issue(
            issues,
            diagnostics["recency_ttl"],
            code="recency_timestamp_missing",
            severity="warn",
            message=f"Bundle {role} lacks a usable recency timestamp.",
            next_action="Record generated_at or updated_at for production bundle TTL checks.",
            bundle_role=role,
        )
        return
    age_days = max((now - updated_at).days, 0)
    diagnostics["recency_ttl"]["summary"] = {
        "updated_at": updated_at.isoformat(),
        "age_days": age_days,
        "ttl_days": ttl_days,
    }
    if age_days > ttl_days:
        _add_issue(
            issues,
            diagnostics["recency_ttl"],
            code="recency_ttl_expired",
            severity="fail",
            message=f"Bundle {role} is older than its production recency TTL.",
            next_action="Refresh the production data snapshot before approval.",
            bundle_role=role,
            age_days=age_days,
            ttl_days=ttl_days,
            affects_major_recommendation=True,
        )


def _data_dictionary_checks(
    *,
    role: str,
    dictionary: Mapping[str, Any],
    dictionary_columns: dict[str, dict[str, Any]],
    metric_columns: set[str],
    diagnostics: dict[str, dict[str, Any]],
    issues: list[dict[str, Any]],
) -> None:
    if not dictionary:
        return
    incomplete: list[str] = []
    for column, info in dictionary_columns.items():
        if not _text(info.get("description") or info.get("definition")):
            incomplete.append(column)
            continue
        metric_id = _text(info.get("metric_id") or info.get("metric"))
        if (column in metric_columns or metric_id in metric_columns) and not _text(
            info.get("unit")
        ):
            incomplete.append(column)
    if incomplete:
        _add_issue(
            issues,
            diagnostics["data_dictionary"],
            code="data_dictionary_incomplete",
            severity="fail",
            message=f"Bundle {role} data dictionary has incomplete production column metadata.",
            next_action="Add descriptions and units for all decision-grade columns.",
            bundle_role=role,
            columns=sorted(set(incomplete)),
        )


def _claim_diagnostics(
    *,
    claims: list[dict[str, Any]],
    issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    major_issues = [
        issue
        for issue in issues
        if _severity(issue) == "fail" and bool(issue.get("affects_major_recommendation"))
    ]
    for index, claim in enumerate(claims):
        claim_id = _text(claim.get("claim_id") or claim.get("id")) or f"claim_{index + 1}"
        major = bool(claim.get("major", True))
        data_refs = _claim_data_refs(claim)
        diagnostics = [
            {
                "code": str(issue.get("code") or ""),
                "diagnostic": str(issue.get("diagnostic") or ""),
                "message": str(issue.get("message") or ""),
            }
            for issue in major_issues
            if major and (_issue_intersects_refs(issue, data_refs) or not data_refs)
        ]
        rows.append(
            {
                "claim_id": claim_id,
                "major": major,
                "status": "fail" if diagnostics else "pass",
                "diagnostics": diagnostics,
                "data_refs": data_refs,
            }
        )
    return rows


def _issue_intersects_refs(issue: Mapping[str, Any], refs: list[str]) -> bool:
    if not refs:
        return False
    metric_ids = _list_text(issue.get("metric_ids"))
    if not metric_ids:
        return True
    return bool(set(metric_ids).intersection(refs))


def _claim_data_refs(claim: Mapping[str, Any]) -> list[str]:
    refs: list[str] = []
    for key in ("data_refs", "metric_refs", "metrics", "outcome_refs", "evidence_refs"):
        raw = claim.get(key)
        if isinstance(raw, str) and raw.strip():
            refs.append(raw.strip())
        elif isinstance(raw, Sequence) and not isinstance(raw, str):
            refs.extend(str(item).strip() for item in raw if str(item).strip())
    grounding = claim.get("grounding")
    if isinstance(grounding, Mapping):
        refs.extend(_claim_data_refs(grounding))
    return sorted(dict.fromkeys(refs))


def _load_bundle_rows(data_paths: list[Path]) -> tuple[list[dict[str, Any]], list[str], list[Path]]:
    rows: list[dict[str, Any]] = []
    columns: list[str] = []
    sources: list[Path] = []
    for path in data_paths:
        loaded = _load_rows(path)
        if loaded is None:
            continue
        source_rows, source_columns = loaded
        if not source_rows and not source_columns:
            continue
        sources.append(path)
        rows.extend(source_rows)
        for column in source_columns:
            if column not in columns:
                columns.append(column)
    return rows, columns, sources


def _load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]] | None:
    suffix = path.suffix.casefold()
    try:
        if suffix == ".csv":
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.DictReader(handle)
                rows = [dict(row) for _, row in zip(range(10_000), reader, strict=False)]
                columns = list(reader.fieldnames or [])
            return rows, columns
        if suffix == ".jsonl":
            rows: list[dict[str, Any]] = []
            with path.open(encoding="utf-8") as handle:
                for index, line in enumerate(handle):
                    if index >= 10_000:
                        break
                    item = json.loads(line)
                    if isinstance(item, Mapping):
                        rows.append(dict(item))
            return rows, _columns_from_rows(rows)
        if suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            raw_rows = payload
            if isinstance(payload, Mapping):
                for key in ("rows", "records", "data", "items"):
                    if isinstance(payload.get(key), list):
                        raw_rows = payload[key]
                        break
            if isinstance(raw_rows, list):
                rows = [dict(item) for item in raw_rows[:10_000] if isinstance(item, Mapping)]
                return rows, _columns_from_rows(rows)
        if suffix == ".duckdb":
            return _load_duckdb_rows(path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, TypeError):
        return None
    return None


def _load_duckdb_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]] | None:
    try:
        import duckdb
    except ModuleNotFoundError:
        return None
    try:
        con = duckdb.connect(str(path), read_only=True)
    except Exception:
        return None
    try:
        tables = con.execute(
            "select table_name from information_schema.tables where table_schema = 'main'"
        ).fetchall()
        for (table_name,) in tables:
            safe_name = str(table_name).replace('"', '""')
            # Table names come from DuckDB's own catalog and quotes are escaped.
            rows = con.execute(f'select * from "{safe_name}" limit 10000').fetchdf()  # noqa: S608
            records = rows.to_dict(orient="records")
            return [dict(row) for row in records], [str(column) for column in rows.columns]
    except Exception:
        return None
    finally:
        con.close()
    return None


def _data_paths(
    root: Path | None,
    bundle: Mapping[str, Any],
    bundle_root: Path | None,
) -> list[Path]:
    keys = (
        "dataset_path",
        "data_path",
        "records_path",
        "csv_path",
        "jsonl_path",
        "json_path",
        "parquet_path",
        "catalog_db_path",
        "academic_db_path",
        "legal_kg_db_path",
    )
    paths: list[Path] = []
    for key in keys:
        path = _metadata_path(root, bundle, key, bundle_root)
        if path is not None and path.exists() and path not in paths:
            paths.append(path)
    if paths:
        return paths
    if bundle_root is None or not bundle_root.exists():
        return []
    for pattern in ("*.csv", "*.jsonl", "*.parquet", "*.duckdb"):
        for path in sorted(bundle_root.glob(pattern)):
            if path not in paths:
                paths.append(path)
    return paths


def _bundle_root(root: Path | None, bundle: Mapping[str, Any]) -> Path | None:
    raw = _text(bundle.get("path"))
    if root is None:
        return Path(raw).expanduser() if raw else None
    if not raw:
        return root
    path = Path(raw).expanduser()
    return path if path.is_absolute() else root / path


def _metadata_path(
    root: Path | None,
    bundle: Mapping[str, Any],
    key: str,
    bundle_root: Path | None,
) -> Path | None:
    raw = _text(bundle.get(key))
    if not raw:
        return None
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    if root is not None:
        return root / path
    return (bundle_root / path) if bundle_root is not None else path


def _load_json_mapping(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _dictionary_columns(dictionary: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    columns = dictionary.get("columns")
    if isinstance(columns, Mapping):
        return {
            str(key): dict(value) if isinstance(value, Mapping) else {}
            for key, value in columns.items()
        }
    if isinstance(columns, list):
        result: dict[str, dict[str, Any]] = {}
        for item in columns:
            if not isinstance(item, Mapping):
                continue
            name = _text(item.get("name") or item.get("column") or item.get("column_name"))
            if name:
                result[name] = dict(item)
        return result
    return {}


def _column_list(dictionary: Mapping[str, Any], key: str) -> list[str]:
    values = _list_text(dictionary.get(key))
    if values:
        return values
    columns = _dictionary_columns(dictionary)
    role = key.removesuffix("_columns")
    return [
        name
        for name, info in columns.items()
        if str(info.get("role") or "").strip().casefold() == role.casefold()
    ]


def _matching_columns(columns: Iterable[str], needles: Iterable[str]) -> list[str]:
    matches: list[str] = []
    for column in columns:
        normalized = column.casefold()
        if any(needle in normalized or normalized == needle for needle in needles):
            matches.append(column)
    return matches


def _metric_columns(
    data_needs: list[dict[str, Any]],
    columns: list[str],
    dictionary_columns: dict[str, dict[str, Any]],
) -> set[str]:
    requested = {_metric_id_from_need(need) for need in data_needs}
    requested.discard(None)
    metric_columns: set[str] = set()
    for column in columns:
        if column in requested:
            metric_columns.add(column)
    for column, info in dictionary_columns.items():
        metric_id = _text(info.get("metric_id") or info.get("metric"))
        if metric_id in requested:
            metric_columns.add(column)
            metric_columns.add(metric_id)
    return metric_columns


def _units_by_metric(dictionary_columns: Mapping[str, Mapping[str, Any]]) -> dict[str, str]:
    result: dict[str, str] = {}
    for column, info in dictionary_columns.items():
        unit = _text(info.get("unit") or info.get("units"))
        if not unit:
            continue
        result[column] = unit
        metric_id = _text(info.get("metric_id") or info.get("metric"))
        if metric_id:
            result[metric_id] = unit
    return result


def _entity_count(rows: list[dict[str, Any]], entity_columns: list[str]) -> int:
    if not rows:
        return 0
    if not entity_columns:
        return len(rows)
    return len({tuple(str(row.get(column) or "") for column in entity_columns) for row in rows})


def _observed_values(rows: list[dict[str, Any]], columns: list[str]) -> set[str]:
    values: set[str] = set()
    for column in columns:
        for row in rows:
            value = _text(row.get(column))
            if value:
                values.add(value)
    return values


def _columns_from_rows(rows: list[dict[str, Any]]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for column in row:
            if column not in columns:
                columns.append(str(column))
    return columns


def _add_issue(
    issues: list[dict[str, Any]],
    diagnostic: dict[str, Any],
    *,
    code: str,
    severity: str,
    message: str,
    next_action: str,
    **details: Any,
) -> None:
    issue = {
        "code": code,
        "severity": severity,
        "status": severity,
        "diagnostic": diagnostic["name"],
        "message": message,
        "next_action": next_action,
        **{key: _json_value(value) for key, value in details.items() if value is not None},
    }
    issues.append(issue)
    findings = diagnostic.setdefault("findings", [])
    if isinstance(findings, list):
        findings.append(issue)


def _merge_diagnostic(target: dict[str, Any], source: Mapping[str, Any]) -> None:
    findings = target.setdefault("findings", [])
    if isinstance(findings, list):
        findings.extend(
            dict(item) for item in source.get("findings") or [] if isinstance(item, Mapping)
        )
    summaries = target.setdefault("summaries", [])
    if isinstance(summaries, list) and isinstance(source.get("summary"), Mapping):
        summaries.append(dict(source["summary"]))


def _diagnostic(name: str) -> dict[str, Any]:
    return {"name": name, "status": "pass", "findings": []}


def _status_from_issues(issues: Sequence[Any]) -> str:
    severities = [_severity(issue) for issue in issues if isinstance(issue, Mapping)]
    if "fail" in severities:
        return "fail"
    if "warn" in severities:
        return "warn"
    return "pass"


def _severity(issue: Mapping[str, Any]) -> str:
    raw = str(issue.get("severity") or issue.get("status") or "warn").strip().casefold()
    return "fail" if raw in {"fail", "failed", "error", "block", "blocked"} else "warn"


def _clean_refs(refs: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(key): str(value).strip()
        for key, value in refs.items()
        if str(key).strip() and isinstance(value, str) and value.strip()
    }


def _context_bundles(evidence_context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw = evidence_context.get("bundles")
    if not isinstance(raw, Mapping):
        return {}
    return {str(role): dict(bundle) for role, bundle in raw.items() if isinstance(bundle, Mapping)}


def _coerce_root(
    production_data_root: str | Path | None,
    evidence_context: Mapping[str, Any],
) -> Path | None:
    raw = production_data_root or evidence_context.get("root")
    if not raw:
        return None
    return Path(str(raw)).expanduser()


def _metric_id_from_need(need: Mapping[str, Any]) -> str | None:
    return _text(
        need.get("metric")
        or need.get("metric_id")
        or need.get("outcome_metric")
        or need.get("query_outcome")
        or need.get("primary_metric")
    )


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip().casefold() in _MISSING_MARKERS


def _to_float(value: Any) -> float | None:
    if _is_missing(value):
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    if text.isdigit() and len(text) == 4:
        text = f"{text}-12-31T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC).replace(microsecond=0)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC, microsecond=0)
    return value.astimezone(UTC).replace(microsecond=0)


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _list_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, Sequence):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _int_or_default(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _looks_fixture_like(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).casefold()
    return any(marker in text for marker in _FIXTURE_MARKERS)


def _json_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_json_value(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


__all__ = [
    "DIAGNOSTIC_KEYS",
    "PRODUCTION_DATA_QUALITY_REF_KEY",
    "PRODUCTION_DATA_QUALITY_SCHEMA_VERSION",
    "build_production_data_quality_report",
    "normalize_production_data_quality_report",
]
