"""Partition contracts for Data Forge assets."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field

from polisyos.data_forge.kernel._base import DataForgeModel


class PartitionKind(str, Enum):
    """Supported partition families."""

    NONE = "none"
    DAILY = "daily"
    HASH = "hash"


class PartitionSpec(DataForgeModel):
    """Base partition specification."""

    kind: PartitionKind


class NoPartition(PartitionSpec):
    """Unpartitioned asset marker."""

    kind: Literal[PartitionKind.NONE] = PartitionKind.NONE


class DailyPartition(PartitionSpec):
    """UTC-by-default daily partition contract."""

    kind: Literal[PartitionKind.DAILY] = PartitionKind.DAILY
    timezone: str = "UTC"
    start_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class HashPartition(PartitionSpec):
    """Hash-bucket partition contract."""

    kind: Literal[PartitionKind.HASH] = PartitionKind.HASH
    buckets: int = Field(ge=1)
    key_field: str = Field(min_length=1)


__all__ = [
    "DailyPartition",
    "HashPartition",
    "NoPartition",
    "PartitionKind",
    "PartitionSpec",
]
