"""Governance metadata for Fabric schema and contract evolution."""

from __future__ import annotations

import re
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

_ADR_RE = re.compile(r"^(?:ADR-)?\d{4}$")


class SchemaRiskLevel(str, Enum):
    """Risk level assigned to one schema or contract change."""

    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class MigrationStatus(str, Enum):
    """Lifecycle state for downstream migration work."""

    NOT_NEEDED = "not_needed"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    BLOCKED = "blocked"


class SchemaApprovalMetadata(BaseModel):
    """Approval workflow metadata stored alongside schema and contract versions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    owner: str = Field(default="", max_length=256)
    reviewer: str = Field(default="", max_length=256)
    risk_level: SchemaRiskLevel = SchemaRiskLevel.LOW
    migration_status: MigrationStatus = MigrationStatus.NOT_NEEDED
    downstream_impact_summary: str = Field(default="", max_length=4096)
    migration_note: str = Field(default="", max_length=4096)
    adr_refs: tuple[str, ...] = Field(default=())
    approved_major_bump: bool = False

    @field_validator("owner", "reviewer", "downstream_impact_summary", "migration_note")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("adr_refs", mode="before")
    @classmethod
    def _normalize_adr_refs(cls, value: object) -> tuple[str, ...]:
        if value in (None, ""):
            return ()
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise TypeError("adr_refs must be a list/tuple/set of ADR identifiers")
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in value:
            token = str(raw).strip().upper()
            if not token:
                continue
            if not _ADR_RE.fullmatch(token):
                raise ValueError(f"Invalid ADR reference: {raw!r}")
            if not token.startswith("ADR-"):
                token = f"ADR-{token}"
            if token not in seen:
                seen.add(token)
                normalized.append(token)
        return tuple(normalized)

    def validate_breaking_change_requirements(self) -> list[str]:
        """Return missing governance requirements for a breaking change."""
        errors: list[str] = []
        if not self.owner:
            errors.append("owner is required for breaking schema changes")
        if not self.reviewer:
            errors.append("reviewer is required for breaking schema changes")
        if not self.approved_major_bump:
            errors.append("approved_major_bump must be true for breaking schema changes")
        if not self.migration_note:
            errors.append("migration_note is required for breaking schema changes")
        if not self.downstream_impact_summary:
            errors.append("downstream_impact_summary is required for breaking schema changes")
        if not self.adr_refs:
            errors.append("adr_refs must include at least one ADR for breaking schema changes")
        if self.migration_status == MigrationStatus.NOT_NEEDED:
            errors.append("migration_status cannot be not_needed for breaking schema changes")
        return errors


__all__ = [
    "MigrationStatus",
    "SchemaApprovalMetadata",
    "SchemaRiskLevel",
]
