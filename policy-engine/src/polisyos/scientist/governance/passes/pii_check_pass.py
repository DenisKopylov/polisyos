"""Validate PII scan severity against the tenant deployment tier."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import ValidationError

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)
from polisyos.ir.connectors import PIIScanSummary

_TENANT_PII_CEILINGS: dict[str, str] = {
    "shared": "low",
    "dedicated": "high",
    "sovereign": "critical",
}

_SEVERITY_ORDER = ("none", "low", "medium", "high", "critical")


class PIICheckPass(ValidatorPass):
    """Block PII findings above the tenant ceiling and warn on tolerated detections.

    Reads `pii_scan_results` and `tenant_tier` from `ctx.state`. Missing scans
    emit `PII_SCAN_MISSING` warnings, violations above the tier ceiling emit
    `PII_CEILING_EXCEEDED` blockers, and findings still within the ceiling emit
    `PII_DETECTED_WITHIN_CEILING` warnings.
    """

    @property
    def pass_id(self) -> str:
        return "pii_check"

    @property
    def estimated_cost_ms(self) -> int:
        return 10

    def validate(self, ctx: PassContext) -> list[ComplianceIssue]:
        pii_results = ctx.state.get("pii_scan_results")
        if pii_results is None:
            return [
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "pii_scan_results"],
                    message=(
                        "PII scan results are missing in state. "
                        "Data may not have been scanned during ingestion."
                    ),
                    severity=IssueSeverity.WARNING,
                    code="PII_SCAN_MISSING",
                    suggestion="Enable POLISYOS_PII_ENABLED and propagate pii_scan_results",
                )
            ]

        try:
            max_severity, total_entities, entities_by_type = _extract_scan_fields(pii_results)
        except (TypeError, ValueError, ValidationError):
            return [
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["state", "pii_scan_results"],
                    message=(
                        "PII scan results were supplied but do not conform to the producer "
                        "summary contract; the scan cannot be treated as clean."
                    ),
                    severity=IssueSeverity.BLOCKER,
                    code="PII_SCAN_INVALID",
                    suggestion="Repair or rerun the PII scan and provide its complete typed summary",
                    input_value="invalid_pii_scan_summary",
                )
            ]
        if total_entities <= 0:
            return []

        tenant_tier = str(ctx.state.get("tenant_tier", "shared")).strip().lower()
        ceiling = _TENANT_PII_CEILINGS.get(tenant_tier, "low")

        if _severity_idx(max_severity) > _severity_idx(ceiling):
            summary = ", ".join(
                f"{key}:{value}"
                for key, value in sorted(entities_by_type.items(), key=lambda item: item[0])
            )
            return [
                ComplianceIssue(
                    pass_id=self.pass_id,
                    path=["data_snapshot", "pii"],
                    message=(
                        f"PII severity '{max_severity}' exceeds tenant tier '{tenant_tier}' "
                        f"ceiling '{ceiling}'. total_entities={total_entities}; {summary}"
                    ),
                    severity=IssueSeverity.BLOCKER,
                    code="PII_CEILING_EXCEEDED",
                    suggestion=(
                        "Redact/anonymize sensitive columns, apply masking transform, "
                        "or run on dedicated/sovereign tier"
                    ),
                    input_value=max_severity,
                )
            ]

        return [
            ComplianceIssue(
                pass_id=self.pass_id,
                path=["data_snapshot", "pii"],
                message=(
                    f"PII detected (max_severity={max_severity}, total_entities={total_entities}) "
                    f"within tenant ceiling '{ceiling}'"
                ),
                severity=IssueSeverity.WARNING,
                code="PII_DETECTED_WITHIN_CEILING",
                input_value=max_severity,
            )
        ]


def _extract_scan_fields(value: object) -> tuple[str, int, dict[str, int]]:
    if isinstance(value, PIIScanSummary):
        summary = value
    elif isinstance(value, Mapping):
        payload = dict(value)
        if "max_severity" not in payload or "total_entities_found" not in payload:
            raise ValueError("PII scan summary is missing required decision fields")
        summary = PIIScanSummary.model_validate(payload, strict=True)
    else:
        raise TypeError("PII scan summary must be the producer's typed summary or mapping")

    max_severity = summary.max_severity.strip().lower()
    if max_severity not in _SEVERITY_ORDER:
        raise ValueError("PII scan summary has an unknown maximum severity")
    if any(type(count) is not int or count < 0 for count in summary.entities_by_type.values()):
        raise ValueError("PII scan summary has an invalid entity-type count")
    if any(
        severity not in _SEVERITY_ORDER or type(count) is not int or count < 0
        for severity, count in summary.entities_by_severity.items()
    ):
        raise ValueError("PII scan summary has an invalid severity count")
    if any(entity.severity.strip().lower() not in _SEVERITY_ORDER for entity in summary.entities):
        raise ValueError("PII scan summary contains an unknown entity severity")
    if summary.total_entities_found == 0 and max_severity != "none":
        raise ValueError("PII scan summary severity conflicts with its empty count")
    if summary.total_entities_found > 0 and max_severity == "none":
        raise ValueError("PII scan summary severity conflicts with its non-empty count")
    return max_severity, summary.total_entities_found, dict(summary.entities_by_type)


def _severity_idx(value: str) -> int:
    return _SEVERITY_ORDER.index(value)
