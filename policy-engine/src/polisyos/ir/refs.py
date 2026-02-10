from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict

from polisyos.ir.artifacts import ArtifactID


class ArtifactRefModel(BaseModel, Mapping[str, object]):
    model_config = ConfigDict(extra="forbid")

    artifact_id: ArtifactID
    kind: str
    media_type: str

    def __iter__(self) -> Iterator[str]:
        yield "artifact_id"
        yield "kind"
        yield "media_type"

    def __len__(self) -> int:
        return 3

    def __getitem__(self, key: str) -> object:
        if key == "artifact_id":
            return str(self.artifact_id)
        if key == "kind":
            return self.kind
        if key == "media_type":
            return self.media_type
        raise KeyError(key)


class EvidenceBundleRef(ArtifactRefModel):
    """IR-level reference to a fabric evidence bundle artifact."""

    kind: Literal["fabric.evidence_bundle"] = "fabric.evidence_bundle"
    media_type: Literal["application/json"] = "application/json"


class UncertaintyEnvelopeRef(ArtifactRefModel):
    kind: Literal["ir.uncertainty_envelope"] = "ir.uncertainty_envelope"
    media_type: Literal["application/json"] = "application/json"


class HTEResultRef(ArtifactRefModel):
    kind: Literal["ir.hte_result"] = "ir.hte_result"
    media_type: Literal["application/json"] = "application/json"


class PolicyRecommendationRef(ArtifactRefModel):
    kind: Literal["ir.policy_recommendation"] = "ir.policy_recommendation"
    media_type: Literal["application/json"] = "application/json"


class CausalEffectReportRef(ArtifactRefModel):
    kind: Literal["ir.causal_effect_report"] = "ir.causal_effect_report"
    media_type: Literal["application/json"] = "application/json"


class DistributionalReportRef(ArtifactRefModel):
    kind: Literal["ir.distributional_report"] = "ir.distributional_report"
    media_type: Literal["application/json"] = "application/json"


class BacktestReportRef(ArtifactRefModel):
    kind: Literal["ir.backtest_report"] = "ir.backtest_report"
    media_type: Literal["application/json"] = "application/json"


__all__ = [
    "BacktestReportRef",
    "CausalEffectReportRef",
    "DistributionalReportRef",
    "EvidenceBundleRef",
    "ArtifactRefModel",
    "HTEResultRef",
    "PolicyRecommendationRef",
    "UncertaintyEnvelopeRef",
]
