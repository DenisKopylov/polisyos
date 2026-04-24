"""Validate PII scan severity against the tenant deployment tier."""

from __future__ import annotations

from polisyos.core.governance.passes.base import (
    ComplianceIssue,
    IssueSeverity,
    PassContext,
    ValidatorPass,
)

_TENANT_PII_CEILINGS: dict[str, str] = {
    "shared": "low",
    "dedicated": "high",
    "sovereign": "critical",
}

_SEVERITY_ORDER = ["none", "low", "medium", "high", "critical"]


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

        max_severity, total_entities, entities_by_type = _extract_scan_fields(pii_results)
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
    if isinstance(value, dict):
        max_severity = str(value.get("max_severity", "none")).strip().lower()
        total_entities = _to_non_negative_int(value.get("total_entities_found", 0))
        by_type_raw = value.get("entities_by_type", {})
        if isinstance(by_type_raw, dict):
            entities_by_type = {
                str(key): _to_non_negative_int(item) for key, item in by_type_raw.items()
            }
        else:
            entities_by_type = {}
        return max_severity, total_entities, entities_by_type

    max_severity = str(getattr(value, "max_severity", "none")).strip().lower()
    total_entities = _to_non_negative_int(getattr(value, "total_entities_found", 0))
    by_type_raw = getattr(value, "entities_by_type", {})
    if isinstance(by_type_raw, dict):
        entities_by_type = {
            str(key): _to_non_negative_int(item) for key, item in by_type_raw.items()
        }
    else:
        entities_by_type = {}
    return max_severity, total_entities, entities_by_type


def _to_non_negative_int(value: object) -> int:
    try:
        return max(0, int(value))
    except (OverflowError, TypeError, ValueError):
        return 0


def _severity_idx(value: str) -> int:
    try:
        return _SEVERITY_ORDER.index(value)
    except ValueError:
        return 0
