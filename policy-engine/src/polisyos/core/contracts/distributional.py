from __future__ import annotations

from typing import Literal

from ..artifacts.manifest import ArtifactRef


class DistributionalReportRef(ArtifactRef):
    kind: Literal["ir.distributional_report"] = "ir.distributional_report"
    media_type: Literal["application/json"] = "application/json"


__all__ = ["DistributionalReportRef"]
