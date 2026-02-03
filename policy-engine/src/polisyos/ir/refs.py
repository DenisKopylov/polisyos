from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from polisyos.ir.kernel.base import ARTIFACT_ID_PATTERN


class EvidenceBundleRef(BaseModel):
    """IR-level reference to a fabric evidence bundle artifact."""

    model_config = ConfigDict(extra="forbid")

    artifact_id: str = Field(pattern=ARTIFACT_ID_PATTERN)
    kind: Literal["fabric.evidence_bundle"] = "fabric.evidence_bundle"
    media_type: Literal["application/json"] = "application/json"


__all__ = ["EvidenceBundleRef"]
