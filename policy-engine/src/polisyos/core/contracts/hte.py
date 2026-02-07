from __future__ import annotations

from typing import Literal

from ..artifacts.manifest import ArtifactRef


class HTEResultRef(ArtifactRef):
    kind: Literal["ir.hte_result"] = "ir.hte_result"
    media_type: Literal["application/json"] = "application/json"


class PolicyRecommendationRef(ArtifactRef):
    kind: Literal["ir.policy_recommendation"] = "ir.policy_recommendation"
    media_type: Literal["application/json"] = "application/json"


__all__ = ["HTEResultRef", "PolicyRecommendationRef"]
