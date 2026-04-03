"""Cell and tenant models for cell-based tenant isolation."""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from polisyos.core.security.settings import get_security_settings

_UUID7_LOCK = threading.Lock()
_LAST_UUID7_TS_MS = -1
_UUID7_COUNTER = 0


class CellTier(StrEnum):
    """Cell tier public type."""
    DEDICATED = "dedicated"
    SHARED = "shared"


class IsolationLevel(StrEnum):
    """Isolation level public type."""
    NAMESPACE = "namespace"
    VCLUSTER = "vcluster"


class DatabaseBackendKind(StrEnum):
    """Database backend kind public type."""
    DUCKDB = "duckdb"
    POSTGRES = "postgres"


def _generate_uuid7() -> str:
    """Generate a UUIDv7-compatible value with monotonic timestamp prefix."""

    global _LAST_UUID7_TS_MS
    global _UUID7_COUNTER

    import secrets
    import time

    now_ms = int(time.time() * 1000)
    with _UUID7_LOCK:
        if now_ms == _LAST_UUID7_TS_MS:
            _UUID7_COUNTER = (_UUID7_COUNTER + 1) & 0x0FFF
        else:
            _LAST_UUID7_TS_MS = now_ms
            _UUID7_COUNTER = secrets.randbits(12)

        rand_b = secrets.randbits(62)
        value = (now_ms & ((1 << 48) - 1)) << 80
        value |= 0x7 << 76
        value |= (_UUID7_COUNTER & 0x0FFF) << 64
        value |= 0x2 << 62
        value |= rand_b

    return str(uuid.UUID(int=value))


class CellSpec(BaseModel):
    """Provisioning contract for one isolation cell that can host PolicyOS tenants."""
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    cell_id: str = Field(default_factory=_generate_uuid7)
    tier: CellTier
    max_tenants: int = Field(default=50, ge=1, le=200)
    region: str = Field(min_length=3, max_length=64)
    isolation_level: IsolationLevel = Field(default=IsolationLevel.NAMESPACE)
    db_backend: DatabaseBackendKind = Field(default=DatabaseBackendKind.POSTGRES)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("cell_id")
    @classmethod
    def _validate_cell_id(cls, value: str) -> str:
        parsed = uuid.UUID(value)
        if parsed.version != 7:
            raise ValueError("cell_id must be UUIDv7")
        return value

    @field_validator("max_tenants")
    @classmethod
    def _validate_capacity(cls, value: int, info: ValidationInfo) -> int:
        tier = info.data.get("tier")
        if tier == CellTier.DEDICATED and value != 1:
            raise ValueError("Dedicated cells must have max_tenants=1")
        return value

    @field_validator("region")
    @classmethod
    def _validate_region(cls, value: str) -> str:
        settings = get_security_settings()
        allowlist = settings.allowed_regions()
        if allowlist and value not in allowlist:
            raise ValueError(
                f"Unsupported region {value!r}. Allowed regions: {sorted(allowlist)}"
            )
        return value

    @property
    def namespace(self) -> str:
        return f"polisyos-cell-{self.cell_slug}"

    @property
    def cell_slug(self) -> str:
        return self.cell_id[:8]

    @property
    def requires_rls(self) -> bool:
        return self.tier == CellTier.SHARED and self.db_backend == DatabaseBackendKind.POSTGRES


class TenantSpec(BaseModel):
    """Tenant enrollment record used when assigning workloads into security cells."""
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    tenant_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(min_length=1, max_length=256)
    tier: CellTier = Field(default=CellTier.SHARED)
    region: str = Field(min_length=3, max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("tenant_id")
    @classmethod
    def _validate_tenant_id(cls, value: str) -> str:
        uuid.UUID(value)
        return value


class CellAssignment(BaseModel):
    """Cell assignment public type."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: str
    cell_id: str
    assigned_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


__all__ = [
    "CellTier",
    "IsolationLevel",
    "DatabaseBackendKind",
    "CellSpec",
    "TenantSpec",
    "CellAssignment",
]
