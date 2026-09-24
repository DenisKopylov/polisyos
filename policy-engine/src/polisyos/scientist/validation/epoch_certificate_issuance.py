"""Neutral epoch-issuance port at the canonical Scientist emission boundary.

Runtime supplies the configured owner implementation. Scientist owns the actual
node execution witness and never imports Runtime recipe/epoch implementations.
The port cannot be populated by an HTTP request or an ExperimentState field.
"""

from __future__ import annotations

import marshal
from dataclasses import dataclass, field
from pathlib import Path
from types import CodeType
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from polisyos.core import artifacts, canon, contracts

ArtifactRef = artifacts.ArtifactRef
ArtifactStore = artifacts.ArtifactStore
DecisionValidityEnvelope = contracts.DecisionValidityEnvelope

_COMPLETED_EXECUTION_SEAL = object()
_INVOCATION_SEAL = object()
DECISION_PACKET_PRODUCER = (
    "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
    "BuildDecisionPacketNode.execute"
)
DECISION_PACKET_INVOCATION_KIND = "scientist.decision_packet_invocation"


class DecisionPacketInvocationRecord(BaseModel):
    """Observed invocation, not a claim of complete admitted execution closure."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_producer_ref: Literal[
        "polisyos.scientist.nodes.builtins.decide.decision_packet.builder."
        "BuildDecisionPacketNode.execute"
    ] = DECISION_PACKET_PRODUCER
    state_ref: ArtifactRef
    run_manifest_ref: ArtifactRef
    node_spec_ref: ArtifactRef
    implementation_ref: ArtifactRef
    loaded_code_ref: ArtifactRef
    input_refs: tuple[ArtifactRef, ...]
    observation_status: Literal["observed_only"] = "observed_only"


@dataclass(frozen=True, slots=True)
class CanonicalDecisionPacketInvocation:
    """Internal canonical-call witness; CAS bytes alone cannot mint this handle."""

    invocation_ref: ArtifactRef
    seal: object = field(repr=False)


def require_canonical_decision_packet_invocation(invocation: object) -> None:
    """Reject authorial invocation handles at the emission-owner port."""

    if (
        type(invocation) is not CanonicalDecisionPacketInvocation
        or invocation.seal is not _INVOCATION_SEAL
    ):
        raise ValueError("epoch_certificate_canonical_invocation_not_established")


def decision_packet_invocation_input_refs(*payloads: object) -> tuple[ArtifactRef, ...]:
    """Collect every embedded ref as an observed selector, never an admission claim."""

    refs: dict[tuple[str, str, str], ArtifactRef] = {}

    def collect(value: object) -> None:
        if isinstance(value, dict):
            if set(value) == {"artifact_id", "kind", "media_type"}:
                try:
                    ref = ArtifactRef.model_validate(value)
                except ValueError:
                    pass  # Ordinary candidate JSON remains fully captured in the state.
                else:
                    refs[(str(ref.artifact_id), ref.kind, ref.media_type)] = ref
                    return
            for item in value.values():
                collect(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                collect(item)

    for payload in payloads:
        collect(payload)
    return tuple(refs[key] for key in sorted(refs))


def _capture_decision_packet_invocation(
    *,
    store: ArtifactStore,
    state: BaseModel,
    run_manifest: BaseModel,
    node_spec: BaseModel,
    implementation_file: str,
    implementation_code: CodeType,
    input_refs: tuple[ArtifactRef, ...],
) -> CanonicalDecisionPacketInvocation:
    """Capture the real node call before work, with no final-certificate cycle."""

    def persist(value: BaseModel, kind: str, *, floats: bool = True) -> ArtifactRef:
        spec = canon.CanonSpec(forbid_floats=not floats)
        raw = canon.to_canonical_bytes(value.model_dump(mode="json"), spec)
        ref = store.put_bytes(
            raw,
            artifacts.ArtifactWriteOptions(
                kind=kind,
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=kind, version="1.0"),
                canon=artifacts.CanonInfo.from_spec(spec),
            ),
        )
        if store.get_bytes(ref.artifact_id) != raw or not store.verify(ref.artifact_id).ok:
            raise ValueError("epoch_certificate_invocation_capture_failed")
        return ref

    implementation_ref = store.put_bytes(
        Path(implementation_file).read_bytes(),
        artifacts.ArtifactWriteOptions(
            kind="scientist.observed_producer_source", media_type="text/x-python"
        ),
    )
    refs = decision_packet_invocation_input_refs(
        state.model_dump(mode="json"),
        run_manifest.model_dump(mode="json"),
        node_spec.model_dump(mode="json"),
    )
    if not {(str(ref.artifact_id), ref.kind, ref.media_type) for ref in input_refs}.issubset(
        (str(ref.artifact_id), ref.kind, ref.media_type) for ref in refs
    ):
        raise ValueError("epoch_certificate_invocation_capture_failed")
    record = DecisionPacketInvocationRecord(
        state_ref=persist(state, "scientist.decision_packet_invoked_state"),
        run_manifest_ref=persist(run_manifest, "scientist.decision_packet_invoked_run"),
        node_spec_ref=persist(node_spec, "scientist.decision_packet_invoked_spec"),
        implementation_ref=implementation_ref,
        loaded_code_ref=store.put_bytes(
            marshal.dumps(implementation_code),
            artifacts.ArtifactWriteOptions(
                kind="scientist.observed_loaded_producer_code",
                media_type="application/octet-stream",
            ),
        ),
        input_refs=refs,
    )
    return CanonicalDecisionPacketInvocation(
        invocation_ref=persist(record, DECISION_PACKET_INVOCATION_KIND, floats=False),
        seal=_INVOCATION_SEAL,
    )


class EpochCertificateIssuanceNonReceipt(BaseModel):
    """A missing admitted source cannot create an epoch binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["not_established"] = "not_established"
    code: Literal[
        "epoch_certificate_issuance_input_not_established",
        "epoch_certificate_epoch_owner_not_established",
        "epoch_certificate_execution_closure_not_established",
        "epoch_certificate_canonical_invocation_not_established",
    ] = "epoch_certificate_issuance_input_not_established"


class PersistedEpochCertificateIssuancePreparation(BaseModel):
    """Exact pre-emission basis handle, avoiding a packet self-reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    issuance_basis_ref: ArtifactRef
    issuance_basis_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True, slots=True)
class CompletedDecisionPacketExecution:
    preparation: PersistedEpochCertificateIssuancePreparation
    decision_packet_ref: ArtifactRef
    seal: object = field(repr=False)


def _completed_decision_packet_execution(
    *,
    preparation: PersistedEpochCertificateIssuancePreparation,
    decision_packet_ref: ArtifactRef,
) -> CompletedDecisionPacketExecution:
    """Called only at the canonical node's successful persisted emission seam."""

    return CompletedDecisionPacketExecution(
        preparation=preparation,
        decision_packet_ref=decision_packet_ref,
        seal=_COMPLETED_EXECUTION_SEAL,
    )


def require_canonical_decision_packet_execution(execution: object) -> None:
    """Require the canonical emission witness without exposing its minting operation."""

    if (
        type(execution) is not CompletedDecisionPacketExecution
        or execution.seal is not _COMPLETED_EXECUTION_SEAL
    ):
        raise ValueError("epoch_certificate_canonical_execution_not_established")


@runtime_checkable
class EpochCertificateIssuanceOwner(Protocol):
    """Trusted composition port for exact source preparation and emitted binding."""

    store: ArtifactStore

    def prepare(
        self,
        *,
        run_id: str,
        invocation_input_refs: tuple[ArtifactRef, ...],
        invocation: CanonicalDecisionPacketInvocation | None = None,
    ) -> PersistedEpochCertificateIssuancePreparation | EpochCertificateIssuanceNonReceipt:
        """Resolve independently admitted execution inputs or preserve absence."""
        ...

    def bind_envelope(
        self,
        *,
        preparation: PersistedEpochCertificateIssuancePreparation,
        envelope: DecisionValidityEnvelope,
    ) -> DecisionValidityEnvelope:
        """Return the envelope bound to the exact immutable issuance basis."""
        ...

    def finalize(self, *, execution: CompletedDecisionPacketExecution) -> ArtifactRef:
        """Read back actual emission and admit the immutable certificate binding."""
        ...
