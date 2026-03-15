"""Curate and publish numeric effect estimates after resolve_finalize."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.academic.batch.resolve_finalize import (
    _curated_numeric_rows,
    _jsonl_write,
    _parameter_point_value,
    _simulation_ready_parameters,
    _strict_simulation_ready_rows,
)
from polisyos.batch_common.manifest import write_stage_manifest
from polisyos.ir.analytics.literature import ArticleExtractionResult, ParameterType


def _load_final_results(path: Path) -> list[ArticleExtractionResult]:
    rows: list[ArticleExtractionResult] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(ArticleExtractionResult.model_validate_json(line))
    return rows


def _load_context_profiles(path: Path) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return profiles
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            work_id = str(row.get("id") or "").strip()
            if work_id and isinstance(row.get("context_profile"), dict):
                profiles[work_id] = dict(row["context_profile"])
    return profiles


def _raw_numeric_rows(result: ArticleExtractionResult, source_context: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for parameter in result.empirical_parameters:
        if parameter.parameter_type != ParameterType.QUANTITATIVE:
            continue
        point_estimate, estimate_source = _parameter_point_value(parameter, mode="balanced")
        rows.append(
            {
                "numeric_id": hashlib.sha256(
                    f"raw|{result.openalex_id}|{parameter.name}|{point_estimate}|{parameter.unit or ''}".encode("utf-8")
                ).hexdigest()[:24],
                "openalex_id": result.openalex_id,
                "canonical_name": parameter.name,
                "display_name": parameter.display_name or parameter.name,
                "estimate_type": estimate_source or ("range_only" if parameter.value_range is not None else "raw_value"),
                "point_estimate": point_estimate,
                "value_range": list(parameter.value_range) if parameter.value_range is not None else None,
                "confidence_interval": list(parameter.confidence_interval) if parameter.confidence_interval else None,
                "std_error": parameter.std_error,
                "unit": parameter.unit,
                "evidence_strength": parameter.evidence_strength.value,
                "source_layer": "raw_numeric",
                "source_context": source_context or None,
            }
        )
    return rows

def run_numeric_extract(config: AcademicBatchConfig) -> dict[str, int]:
    started_at = datetime.now(UTC).isoformat()
    final_results = _load_final_results(config.resolve_extract_final_results_path)
    context_profiles = _load_context_profiles(config.resolve_extract_final_works_path)
    if not final_results:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "numeric_extract.json",
            stage="numeric_extract",
            status="ok",
            metrics={"works_seen": 0, "raw_numeric": 0, "curated_numeric": 0, "simulation_ready": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"works_seen": 0, "raw_numeric": 0, "curated_numeric": 0, "simulation_ready": 0}

    raw_rows: list[dict[str, Any]] = []
    curated_rows: list[dict[str, Any]] = []
    simulation_rows: list[dict[str, Any]] = []

    for result in final_results:
        source_context = context_profiles.get(result.openalex_id, {})
        raw_rows.extend(_raw_numeric_rows(result, source_context))
        curated = _curated_numeric_rows(
            result,
            mode=config.numeric_precision_mode,
            source_context=source_context,
        )
        curated_rows.extend(curated)
        strict_rows = _strict_simulation_ready_rows(curated)
        if strict_rows:
            simulation_rows.extend(strict_rows)
            continue
        # Keep backward-compatible fallback in balanced/off modes, but never in high_precision.
        if config.numeric_precision_mode != "high_precision":
            simulation_rows.extend(
                _simulation_ready_parameters(
                    result,
                    mode=config.numeric_precision_mode,
                    source_context=source_context,
                )
            )

    _jsonl_write(config.numeric_estimates_raw_path, raw_rows)
    _jsonl_write(config.numeric_estimates_curated_path, curated_rows)
    _jsonl_write(config.simulation_ready_numeric_path, simulation_rows)

    metrics = {
        "works_seen": len(final_results),
        "raw_numeric": len(raw_rows),
        "curated_numeric": len(curated_rows),
        "simulation_ready": len(simulation_rows),
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "numeric_extract.json",
        stage="numeric_extract",
        status="ok",
        metrics=metrics,
        artifacts=[
            config.numeric_estimates_raw_path,
            config.numeric_estimates_curated_path,
            config.simulation_ready_numeric_path,
        ],
        started_at=started_at,
    )
    return metrics


__all__ = ["run_numeric_extract"]
