"""Runtime-safe compliance report readers/builders for Data Forge artifacts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any


def build_privacy_compliance_report(
    *,
    production_data_sources: Iterable[Mapping[str, Any]] | None = None,
    public_artifact_families: Iterable[Mapping[str, Any]] | None = None,
    override: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build an auditable compliance report through the runtime read_api boundary."""

    from polisyos.data_forge._impl.compliance import (
        build_privacy_compliance_report as _build_privacy_compliance_report,
    )

    return _build_privacy_compliance_report(
        production_data_sources=production_data_sources,
        public_artifact_families=public_artifact_families,
        override=override,
        generated_at=generated_at,
    )


def normalize_privacy_compliance_report(report: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize a compliance report through the runtime read_api boundary."""

    from polisyos.data_forge._impl.compliance import (
        normalize_privacy_compliance_report as _normalize_privacy_compliance_report,
    )

    return _normalize_privacy_compliance_report(report)


__all__ = ["build_privacy_compliance_report", "normalize_privacy_compliance_report"]
