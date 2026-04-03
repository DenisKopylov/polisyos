"""Audit miss feedback queue helpers."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def build_feedback_queue_rows(audit_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build feedback queue rows."""
    feedback_rows: list[dict[str, Any]] = []
    for row in audit_rows:
        if not bool(row.get("miss", False)):
            continue
        categories = list(row.get("miss_categories") or [])
        cluster_key = _cluster_key(
            quality_family=str(row.get("quality_family") or "other"),
            legal_unit_subtype=str(row.get("legal_unit_subtype") or "unknown"),
            miss_categories=categories,
        )
        feedback_rows.append(
            {
                "feedback_id": hashlib.sha256(
                    "|".join(
                        [
                            str(row.get("doc_id") or ""),
                            str(row.get("provision_anchor") or ""),
                            cluster_key,
                        ]
                    ).encode("utf-8")
                ).hexdigest()[:24],
                "doc_id": str(row.get("doc_id") or ""),
                "provision_anchor": str(row.get("provision_anchor") or ""),
                "quality_family": str(row.get("quality_family") or "other"),
                "legal_unit_subtype": str(row.get("legal_unit_subtype") or ""),
                "route_class": str(row.get("route_class") or ""),
                "deterministic_reason_codes": list(row.get("gate_reason_codes") or []),
                "llm_delta": int(row.get("llm_count") or 0) - int(row.get("baseline_count") or 0),
                "miss_categories": categories,
                "cluster_key": cluster_key,
                "suggestion_family": _suggestion_family(categories),
                "metadata": {
                    "empty_spo_only": bool(row.get("empty_spo_only", False)),
                    "reference_bearing": bool(row.get("reference_bearing", False)),
                    "threshold_bearing": bool(row.get("threshold_bearing", False)),
                    "audit_miss_prone": bool(row.get("audit_miss_prone", False)),
                },
            }
        )
    return feedback_rows


def write_candidate_patterns(*, feedback_rows: list[dict[str, Any]], output_dir: Path) -> Path:
    """Write candidate patterns helper."""
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in feedback_rows:
        grouped[str(row.get("cluster_key") or "other")].append(row)
    payload = {
        "generated_from_feedback": True,
        "clusters": [
            {
                "cluster_key": cluster_key,
                "count": len(rows),
                "suggestion_family": str(rows[0].get("suggestion_family") or "generic"),
                "examples": [
                    {
                        "doc_id": str(item.get("doc_id") or ""),
                        "provision_anchor": str(item.get("provision_anchor") or ""),
                        "miss_categories": list(item.get("miss_categories") or []),
                    }
                    for item in rows[:5]
                ],
            }
            for cluster_key, rows in sorted(grouped.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
    }
    out_path = output_dir / "pattern_feedback_candidates.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _cluster_key(*, quality_family: str, legal_unit_subtype: str, miss_categories: list[str]) -> str:
    categories = ",".join(sorted(str(item).strip() for item in miss_categories if str(item).strip()))
    return f"{quality_family}:{legal_unit_subtype}:{categories or 'generic'}"


def _suggestion_family(miss_categories: list[str]) -> str:
    if any(category in {"reference_amendment", "reference"} for category in miss_categories):
        return "reference"
    if any(category in {"threshold", "sanction"} for category in miss_categories):
        return "threshold"
    if any(category in {"temporal", "temporal_clause"} for category in miss_categories):
        return "temporal"
    return "normative"
