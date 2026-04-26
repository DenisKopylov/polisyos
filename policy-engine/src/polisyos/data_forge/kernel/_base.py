"""Internal base models for Data Forge contracts."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict


class DataForgeModel(BaseModel):
    """Strict immutable base model for Data Forge contract payloads."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def utc_now() -> datetime:
    """Return a second-granularity UTC timestamp for stable manifests."""
    return datetime.now(UTC).replace(microsecond=0)


__all__ = ["DataForgeModel", "utc_now"]
