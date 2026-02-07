from __future__ import annotations

from typing import Literal

from ..artifacts.manifest import ArtifactRef


class CausalEffectReportRef(ArtifactRef):
    kind: Literal["ir.causal_effect_report"] = "ir.causal_effect_report"
    media_type: Literal["application/json"] = "application/json"


__all__ = ["CausalEffectReportRef"]

