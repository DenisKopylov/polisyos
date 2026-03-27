from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict

from polisyos.ir.analytics.cross_graph import (
    EvidenceSourceKind,
    EvidenceSourceState,
    EvidenceSourceStatus,
)


class EvidenceSourcesConfig(BaseModel):
    """Normalized external evidence-source configuration shared across runtimes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    academic_db_path: str | None = None
    academic_index_dir: str | None = None
    datasets_db_path: str | None = None
    legal_db_path: str | None = None
    benchmark_suite_path: str | None = None
    benchmark_report_path: str | None = None
    academic_demand_backlog_path: str | None = None


_EVIDENCE_SOURCE_FIELDS = (
    "academic_db_path",
    "academic_index_dir",
    "datasets_db_path",
    "legal_db_path",
    "benchmark_suite_path",
    "benchmark_report_path",
    "academic_demand_backlog_path",
)


def normalize_evidence_sources_config(
    *payloads: Mapping[str, Any] | None,
) -> EvidenceSourcesConfig:
    """Build one normalized source config from flat and nested payloads.

    New nested ``evidence_sources`` values override legacy flat fields.
    """

    merged: dict[str, Any] = {}
    for payload in payloads:
        if not isinstance(payload, Mapping):
            continue
        for field in _EVIDENCE_SOURCE_FIELDS:
            value = payload.get(field)
            if value is not None:
                merged[field] = value
        nested = payload.get("evidence_sources")
        if isinstance(nested, Mapping):
            for field in _EVIDENCE_SOURCE_FIELDS:
                value = nested.get(field)
                if value is not None:
                    merged[field] = value
    return EvidenceSourcesConfig.model_validate(merged)


def merge_evidence_sources_payload(
    payload: Mapping[str, Any] | None,
    evidence_sources: EvidenceSourcesConfig,
) -> dict[str, Any]:
    """Apply normalized source paths to an existing config payload."""

    merged = dict(payload or {})
    merged.pop("evidence_sources", None)
    for field, value in evidence_sources.model_dump(mode="json").items():
        if value is not None:
            merged[field] = value
    return merged


def build_path_source_status(
    source: EvidenceSourceKind,
    path: str | None,
    *,
    disabled: bool = False,
    detail: str | None = None,
) -> EvidenceSourceStatus:
    """Classify one path-backed source into an availability status."""

    normalized_path = str(path or "").strip() or None
    if disabled:
        return EvidenceSourceStatus(
            source=source,
            configured=False,
            status=EvidenceSourceState.DISABLED,
            path=normalized_path,
            detail=detail,
        )
    if not normalized_path:
        return EvidenceSourceStatus(
            source=source,
            configured=False,
            status=EvidenceSourceState.MISSING_CONFIG,
            path=None,
            detail=detail,
        )
    path_obj = Path(normalized_path)
    if not path_obj.exists():
        return EvidenceSourceStatus(
            source=source,
            configured=True,
            status=EvidenceSourceState.MISSING_PATH,
            path=normalized_path,
            detail=detail,
            warnings=[f"path_missing:{normalized_path}"],
        )
    return EvidenceSourceStatus(
        source=source,
        configured=True,
        status=EvidenceSourceState.AVAILABLE,
        path=str(path_obj),
        detail=detail,
    )


def update_source_status(
    status: EvidenceSourceStatus,
    *,
    state: EvidenceSourceState,
    detail: str | None = None,
    warnings: list[str] | None = None,
    provenance_refs: list[str] | None = None,
) -> EvidenceSourceStatus:
    """Return a modified source status without mutating the original object."""

    merged_warnings = [*status.warnings, *(warnings or [])]
    merged_provenance = [*status.provenance_refs, *(provenance_refs or [])]
    return status.model_copy(
        update={
            "status": state,
            "detail": detail or status.detail,
            "warnings": merged_warnings,
            "provenance_refs": merged_provenance,
        }
    )


__all__ = [
    "EvidenceSourcesConfig",
    "build_path_source_status",
    "merge_evidence_sources_payload",
    "normalize_evidence_sources_config",
    "update_source_status",
]
