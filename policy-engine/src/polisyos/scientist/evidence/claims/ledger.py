"""Claim ledger CAS persistence helpers."""

from __future__ import annotations

from collections.abc import Iterable

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.scientist.evidence.claims.models import ClaimLedger

CLAIM_LEDGER_KIND = "scientist.claim_ledger"
CLAIM_LEDGER_SCHEMA_NAME = "polisyos.scientist.claims.ClaimLedger"
CLAIM_LEDGER_SCHEMA_VERSION = "1.0"


def claim_ledger_inputs(
    *,
    source_artifact_refs: Iterable[ArtifactRef] = (),
    decision_readiness_ref: ArtifactRef | None = None,
) -> list[InputRef]:
    """Build manifest lineage inputs for a persisted claim ledger."""

    inputs: list[InputRef] = []
    seen: set[tuple[str, str]] = set()

    def add(ref: ArtifactRef, role: str) -> None:
        key = (str(ref.artifact_id), role)
        if key in seen:
            return
        seen.add(key)
        inputs.append(InputRef(artifact_id=ref.artifact_id, role=role))

    if decision_readiness_ref is not None:
        add(decision_readiness_ref, "decision_readiness")
    for index, ref in enumerate(source_artifact_refs):
        add(ref, f"claim_source[{index}]")
    return inputs


def persist_claim_ledger(
    store: FileSystemCAS,
    ledger: ClaimLedger,
    *,
    inputs: list[InputRef] | None = None,
) -> ArtifactRef:
    """Persist a ClaimLedger as a first-class Scientist CAS artifact."""

    manifest_inputs = (
        list(inputs)
        if inputs is not None
        else claim_ledger_inputs(
            source_artifact_refs=ledger.source_artifact_refs,
            decision_readiness_ref=ledger.decision_readiness_ref,
        )
    )
    return store.put_json(
        ledger,
        PutOptions(
            kind=CLAIM_LEDGER_KIND,
            media_type="application/json",
            schema=SchemaInfo(
                name=CLAIM_LEDGER_SCHEMA_NAME,
                version=CLAIM_LEDGER_SCHEMA_VERSION,
            ),
            inputs=manifest_inputs or None,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_claim_ledger(store: FileSystemCAS, ref: ArtifactRef) -> ClaimLedger:
    """Load a persisted ClaimLedger from CAS."""

    payload = from_canonical_bytes(store.get_bytes(ref.artifact_id))
    return ClaimLedger.model_validate(payload)


__all__ = [
    "CLAIM_LEDGER_KIND",
    "CLAIM_LEDGER_SCHEMA_NAME",
    "CLAIM_LEDGER_SCHEMA_VERSION",
    "claim_ledger_inputs",
    "load_claim_ledger",
    "persist_claim_ledger",
]
