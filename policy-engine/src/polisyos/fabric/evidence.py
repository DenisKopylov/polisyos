from __future__ import annotations

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.contracts.fabric import EvidenceBundle, EvidenceBundleRef, EvidenceStep


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


def persist_evidence_bundle(
    store: FileSystemCAS,
    bundle: EvidenceBundle,
    *,
    schema_name: str = "fabric.evidence_bundle",
    schema_version: str = "1.0",
) -> EvidenceBundleRef:
    """
    Сохраняет EvidenceBundle в CAS и возвращает строгий EvidenceBundleRef.
    """
    ref = store.put_json(
        bundle.model_dump(),
        opts=PutOptions(
            kind="fabric.evidence_bundle",
            media_type="application/json",
            schema=SchemaInfo(name=schema_name, version=schema_version),
        ),
    )
    return EvidenceBundleRef.model_validate(ref.model_dump())
