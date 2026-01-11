from __future__ import annotations

from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef, EvidenceStep
from polisyos.core.artifacts.manifest import ArtifactRef


def build_evidence_bundle(
    *,
    sources: list[ArtifactRef] | None = None,
    transforms: list[EvidenceStep] | None = None,
    trust_policy_id: str | None = None,
    notes: list[str] | None = None,
) -> EvidenceBundle:
    return EvidenceBundle(
        sources=sources or [],
        transforms=transforms or [],
        trust_policy_id=trust_policy_id,
        notes=notes or [],
    )
