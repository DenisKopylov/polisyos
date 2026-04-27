"""Connector governance metadata validation for Fabric production sources."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from polisyos.ir.connectors import ConnectorMetadataSpec

__all__ = [
    "ConnectorGovernanceMetadataIssue",
    "ConnectorGovernanceMetadataReport",
    "validate_connector_governance_metadata",
]


@dataclass(frozen=True, slots=True)
class ConnectorGovernanceMetadataIssue:
    """One missing or malformed connector governance field."""

    connector_id: str
    field: str
    message: str


@dataclass(frozen=True, slots=True)
class ConnectorGovernanceMetadataReport:
    """Validation report for one production connector metadata record."""

    connector_id: str
    issues: tuple[ConnectorGovernanceMetadataIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def validate_connector_governance_metadata(
    metadata: ConnectorMetadataSpec,
    *,
    require_schema: bool = True,
    require_quality_contract: bool = True,
) -> ConnectorGovernanceMetadataReport:
    """Validate Phase 4 metadata required for production connector governance."""

    connector_id = metadata.fully_qualified_id
    issues: list[ConnectorGovernanceMetadataIssue] = []

    def add(field: str, message: str) -> None:
        issues.append(
            ConnectorGovernanceMetadataIssue(
                connector_id=connector_id,
                field=field,
                message=message,
            )
        )

    if not _non_empty(metadata.owner):
        add("owner", "owner is required for production connector metadata")

    if require_schema and not (
        _non_empty(metadata.schema_id) or _non_empty(metadata.schema_id_template)
    ):
        add("schema", "schema_id or schema_id_template is required")

    if not _non_empty(metadata.schema_registry_ref):
        add("schema_registry_ref", "schema registry reference is required")

    if metadata.quality_tier.value <= 0:
        add("quality_tier", "quality tier must be classified above unverified")

    if require_quality_contract and not _non_empty(metadata.quality_contract_id):
        add("quality_contract_id", "quality contract id is required")

    if not _non_empty(metadata.data_classification):
        add("data_classification", "access classification is required")

    sla = metadata.sla
    if sla is None:
        add("sla", "SLA metadata is required")
    else:
        if not 0.0 <= sla.availability_target <= 1.0:
            add("sla.availability_target", "availability target must be a probability")
        if sla.freshness_slo_seconds < 0:
            add("sla.freshness_slo_seconds", "freshness SLO must be non-negative")
        if sla.p95_latency_ms < 0:
            add("sla.p95_latency_ms", "p95 latency SLO must be non-negative")
        if not 0.0 <= sla.replay_success_target <= 1.0:
            add("sla.replay_success_target", "replay success target must be a probability")

    return ConnectorGovernanceMetadataReport(
        connector_id=connector_id,
        issues=tuple(issues),
    )


def _non_empty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())
