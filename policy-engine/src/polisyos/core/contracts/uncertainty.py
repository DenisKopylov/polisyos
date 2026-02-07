from __future__ import annotations

from typing import Literal

from ..artifacts.manifest import ArtifactRef


class UncertaintyEnvelopeRef(ArtifactRef):
    kind: Literal["ir.uncertainty_envelope"] = "ir.uncertainty_envelope"
    media_type: Literal["application/json"] = "application/json"


__all__ = ["UncertaintyEnvelopeRef"]
