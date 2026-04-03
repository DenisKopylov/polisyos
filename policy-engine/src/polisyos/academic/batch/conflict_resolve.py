"""Conflict-set synthesis for finalized academic claims."""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polisyos.academic.batch.config import AcademicBatchConfig
from polisyos.batch_common.manifest import write_stage_manifest

_CONTESTED_DIRECTIONS = {"positive", "negative"}


def _jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(str(part or "").strip() for part in parts).encode("utf-8")
    return f"{prefix}_{hashlib.sha256(payload).hexdigest()[:24]}"


def _adjudication_map(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for row in _load_jsonl(path):
        claim_id = str(row.get("claim_id") or "").strip()
        if claim_id:
            rows[claim_id] = row
    return rows


def _claim_rows(config: AcademicBatchConfig) -> list[dict[str, Any]]:
    for candidate in (
        config.raw_claim_candidates_final_path,
        config.published_claims_final_path,
        config.raw_claim_candidates_path,
    ):
        rows = _load_jsonl(candidate)
        if rows:
            return rows
    return []


def _direction_histogram(rows: list[dict[str, Any]]) -> dict[str, int]:
    histogram: Counter[str] = Counter()
    for row in rows:
        direction = str(row.get("direction") or "mixed").strip().lower() or "mixed"
        histogram[direction] += 1
    return dict(sorted(histogram.items()))


def _resolution_for_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    histogram = _direction_histogram(rows)
    positive = histogram.get("positive", 0)
    negative = histogram.get("negative", 0)
    mixed = histogram.get("mixed", 0) + histogram.get("ambiguous", 0) + histogram.get("non_linear", 0)
    if positive and negative:
        status = "contested"
        dominant_direction = "mixed"
    elif positive:
        status = "resolved"
        dominant_direction = "positive"
    elif negative:
        status = "resolved"
        dominant_direction = "negative"
    elif mixed:
        status = "mixed"
        dominant_direction = "mixed"
    else:
        status = "insufficient"
        dominant_direction = ""
    if status == "resolved":
        runtime_support = "SUPPORTED" if len(rows) >= 2 else "MIXED"
    elif status == "contested":
        runtime_support = "MIXED"
    elif status == "mixed":
        runtime_support = "MIXED"
    else:
        runtime_support = "UNSUPPORTED"
    return {
        "status": status,
        "dominant_direction": dominant_direction,
        "runtime_support": runtime_support,
        "direction_histogram": histogram,
    }


def run_conflict_resolve(config: AcademicBatchConfig) -> dict[str, int]:
    """Run conflict resolve."""
    started_at = datetime.now(UTC).isoformat()
    claim_rows = _claim_rows(config)
    adjudications = _adjudication_map(config.claim_adjudications_path)
    if not claim_rows:
        write_stage_manifest(
            manifest_path=config.manifests_dir / "conflict_resolve.json",
            stage="conflict_resolve",
            status="ok",
            metrics={"claim_sets": 0, "conflict_sets": 0, "contested_sets": 0},
            artifacts=[],
            started_at=started_at,
        )
        return {"claim_sets": 0, "conflict_sets": 0, "contested_sets": 0}

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in claim_rows:
        cause = str(row.get("cause_text") or row.get("cause") or row.get("cause_variable") or "").strip()
        effect = str(row.get("effect_text") or row.get("effect") or row.get("effect_variable") or "").strip()
        if not cause or not effect:
            continue
        grouped[(cause, effect)].append(row)

    claim_sets: list[dict[str, Any]] = []
    conflict_sets: list[dict[str, Any]] = []
    conflict_resolutions: list[dict[str, Any]] = []
    contested_sets = 0
    for (cause, effect), rows in sorted(grouped.items()):
        claim_ids = sorted({str(row.get("claim_id") or "").strip() for row in rows if str(row.get("claim_id") or "").strip()})
        work_ids = sorted({str(row.get("work_id") or row.get("openalex_id") or "").strip() for row in rows if str(row.get("work_id") or row.get("openalex_id") or "").strip()})
        publishable_claims = 0
        supported_claims = 0
        best_confidence = 0.0
        for row in rows:
            claim_id = str(row.get("claim_id") or "").strip()
            adjudication = adjudications.get(claim_id, {})
            if bool(adjudication.get("publishable_edge")) or bool(row.get("publish_to_graph")):
                publishable_claims += 1
            if str(adjudication.get("support_status") or "").strip().lower() == "supported":
                supported_claims += 1
            try:
                best_confidence = max(best_confidence, float(row.get("claim_extraction_confidence") or adjudication.get("claim_validity_score") or 0.0))
            except (TypeError, ValueError):
                pass
        set_id = _stable_id("claimset", cause, effect)
        resolution = _resolution_for_rows(rows)
        claim_set = {
            "claim_set_id": set_id,
            "cause": cause,
            "effect": effect,
            "claim_ids": claim_ids,
            "openalex_ids": work_ids,
            "n_claims": len(rows),
            "n_unique_works": len(work_ids),
            "publishable_claims": publishable_claims,
            "supported_claims": supported_claims,
            "best_confidence": round(best_confidence, 6),
            "direction_histogram": resolution["direction_histogram"],
        }
        claim_sets.append(claim_set)
        conflict_resolutions.append(
            {
                "claim_set_id": set_id,
                "cause": cause,
                "effect": effect,
                **resolution,
                "n_claims": len(rows),
                "n_unique_works": len(work_ids),
            }
        )
        if resolution["status"] in {"contested", "mixed"}:
            conflict_sets.append(
                {
                    "conflict_set_id": _stable_id("conflict", cause, effect),
                    "claim_set_id": set_id,
                    "cause": cause,
                    "effect": effect,
                    "direction_histogram": resolution["direction_histogram"],
                    "claim_ids": claim_ids,
                    "openalex_ids": work_ids,
                    "status": resolution["status"],
                }
            )
        if resolution["status"] == "contested":
            contested_sets += 1

    _jsonl_write(config.claim_sets_path, claim_sets)
    _jsonl_write(config.conflict_sets_path, conflict_sets)
    _jsonl_write(config.conflict_resolutions_path, conflict_resolutions)

    metrics = {
        "claim_sets": len(claim_sets),
        "conflict_sets": len(conflict_sets),
        "contested_sets": contested_sets,
    }
    write_stage_manifest(
        manifest_path=config.manifests_dir / "conflict_resolve.json",
        stage="conflict_resolve",
        status="ok",
        metrics=metrics,
        artifacts=[
            config.claim_sets_path,
            config.conflict_sets_path,
            config.conflict_resolutions_path,
        ],
        started_at=started_at,
    )
    return metrics


__all__ = ["run_conflict_resolve"]
