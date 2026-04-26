"""Snapshot retention contracts."""

from __future__ import annotations

from pydantic import Field

import polisyos.data_forge.kernel.artifacts as artifact_contracts
from polisyos.data_forge.kernel._base import DataForgeModel

RetentionClass = artifact_contracts.RetentionClass


class RetentionPolicy(DataForgeModel):
    """Resolved retention policy for a Data Forge artifact or snapshot."""

    retention_class: RetentionClass
    keep_days: int = Field(ge=0)
    delete_on_expiry: bool = True


__all__ = ["RetentionPolicy"]
