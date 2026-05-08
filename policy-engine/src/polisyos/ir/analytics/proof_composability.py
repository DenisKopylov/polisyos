"""Proof-trace composability contracts for cross-fragment causal replay.

This module defines the conservative artifact surface used when a proof trace
from one fragment is replayed against a graph obtained by composition. The
contract intentionally distinguishes between:

- ``reusable``: every replayed step retained its original witness;
- ``revalidate``: the trace shape can be reused but one or more local
  obligations must be checked again on the composed graph;
- ``rederive``: at least one critical witness is broken, so blind replay is
  unsound and the proof must be recomputed from the composed graph;
- ``unknown``: the current kernel does not claim any safe reuse mode.
"""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import (
    EvidenceBundleRef,
    ProofComposabilityCertificateRef,
    ProofWitnessIndexRef,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.causal import ProofBundle


class ProofObligationKind(str, Enum):
    """Kinds of graphical obligations that may license one proof step."""

    M_SEPARATION = "m_separation"
    ANCESTRAL_RESTRICTION = "ancestral_restriction"
    DISTRICT_FACTORIZATION = "district_factorization"
    HEDGE_WITNESS = "hedge_witness"
    FRONTDOOR = "frontdoor"
    G_FORMULA = "g_formula"
    ORACLE = "oracle"
    PROJECTION_EQUIVALENCE = "projection_equivalence"


class ProofComposabilityStatus(str, Enum):
    """Operational replay status for a proof trace after fragment composition."""

    REUSABLE = "reusable"
    REVALIDATE = "revalidate"
    REDERIVE = "rederive"
    UNKNOWN = "unknown"


class ProofReplayStepStatus(str, Enum):
    """Local replay status of one step from an existing proof trace."""

    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class ProofGraphWitness(BaseModel):
    """Machine-checkable graphical witness attached to a proof-trace step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    witness_id: str = Field(min_length=1)
    obligation_kind: ProofObligationKind
    support_vars: tuple[str, ...] = ()
    mutilation: str = ""
    projection_hash: str = ""
    ancestor_signature: tuple[str, ...] = ()
    district_signature: tuple[tuple[str, ...], ...] = ()
    hedge_signature: dict[str, Any] | None = None
    separation_statement: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("support_vars", "ancestor_signature", mode="before")
    @classmethod
    def _normalize_sorted_unique_str_tuple(
        cls,
        value: object,
    ) -> tuple[str, ...]:
        if value in (None, ""):
            return ()
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("expected a list/tuple/set of strings")
        normalized = tuple(sorted({str(item).strip() for item in value if str(item).strip()}))
        return normalized

    @field_validator("district_signature", mode="before")
    @classmethod
    def _normalize_district_signature(
        cls,
        value: object,
    ) -> tuple[tuple[str, ...], ...]:
        if value in (None, ""):
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("district_signature must be a tuple/list of tuples")
        normalized: list[tuple[str, ...]] = []
        for district in value:
            if not isinstance(district, (list, tuple, set)):
                raise ValueError("each district_signature item must be a tuple/list/set")
            cleaned = tuple(sorted({str(item).strip() for item in district if str(item).strip()}))
            if cleaned:
                normalized.append(cleaned)
        return tuple(sorted(set(normalized)))


class ProofWitnessIndex(BaseModel):
    """Index of graphical witnesses used to replay or invalidate one proof trace."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    witnesses: tuple[ProofGraphWitness, ...] = ()
    step_to_witness_ids: dict[str, tuple[str, ...]] = Field(default_factory=dict)
    proof_support_projection_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_witness_links(self) -> ProofWitnessIndex:
        witness_ids = [witness.witness_id for witness in self.witnesses]
        if len(set(witness_ids)) != len(witness_ids):
            raise ValueError("witness ids must be unique")
        known = set(witness_ids)
        for step_id, linked_ids in self.step_to_witness_ids.items():
            if not str(step_id).strip():
                raise ValueError("step_to_witness_ids keys must be non-empty")
            if len(set(linked_ids)) != len(linked_ids):
                raise ValueError("step_to_witness_ids entries must not repeat witness ids")
            missing = sorted(set(linked_ids) - known)
            if missing:
                raise ValueError(
                    f"step_to_witness_ids references unknown witness ids for {step_id}: {missing}"
                )
        return self


class ProofComposabilityCertificate(BaseModel):
    """Certificate describing whether a stored proof trace may be replayed safely."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
    status: ProofComposabilityStatus
    source_fragment_id: str = Field(min_length=1)
    composed_graph_ref: str | None = None
    checked_query: str = Field(min_length=1)
    proof_trace_ref: EvidenceBundleRef | None = None
    witness_index_ref: ProofWitnessIndexRef | None = None
    preserved_witness_ids: tuple[str, ...] = ()
    broken_witness_ids: tuple[str, ...] = ()
    step_statuses: dict[str, ProofReplayStepStatus] = Field(default_factory=dict)
    invalidation_reasons: tuple[str, ...] = ()
    interface_vars: tuple[str, ...] = ()
    new_ancestors: tuple[str, ...] = ()
    new_district_links: tuple[tuple[str, str], ...] = ()
    projection_preservation_passed: bool | None = None
    proof_support_projection_hash: str | None = None
    invalidated_by_graph_hashes: tuple[str, ...] = ()
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "preserved_witness_ids",
        "broken_witness_ids",
        "invalidation_reasons",
        "interface_vars",
        "new_ancestors",
        "invalidated_by_graph_hashes",
        mode="before",
    )
    @classmethod
    def _normalize_str_tuple(
        cls,
        value: object,
    ) -> tuple[str, ...]:
        if value in (None, ""):
            return ()
        if not isinstance(value, (list, tuple, set)):
            raise ValueError("expected a list/tuple/set of strings")
        return tuple(sorted({str(item).strip() for item in value if str(item).strip()}))

    @field_validator("new_district_links", mode="before")
    @classmethod
    def _normalize_district_links(
        cls,
        value: object,
    ) -> tuple[tuple[str, str], ...]:
        if value in (None, ""):
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("new_district_links must be a tuple/list of pairs")
        links: set[tuple[str, str]] = set()
        for item in value:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise ValueError("each new_district_links item must be a pair")
            left = str(item[0]).strip()
            right = str(item[1]).strip()
            if not left or not right:
                raise ValueError("new_district_links pairs must be non-empty")
            links.add(tuple(sorted((left, right))))
        return tuple(sorted(links))

    @model_validator(mode="after")
    def _validate_consistency(self) -> ProofComposabilityCertificate:
        overlap = set(self.preserved_witness_ids) & set(self.broken_witness_ids)
        if overlap:
            raise ValueError(f"witness ids cannot be both preserved and broken: {sorted(overlap)}")
        if self.status is ProofComposabilityStatus.REUSABLE:
            if self.broken_witness_ids or self.invalidation_reasons:
                raise ValueError("reusable certificates cannot declare broken witnesses")
            if self.projection_preservation_passed is False:
                raise ValueError("reusable certificates require preserved proof support projection")
        if self.status is ProofComposabilityStatus.REDERIVE and not (
            self.broken_witness_ids
            or self.invalidation_reasons
            or any(
                step_status is ProofReplayStepStatus.INVALID
                for step_status in self.step_statuses.values()
            )
        ):
            raise ValueError("rederive certificates require a concrete invalidation witness")
        return self


def infer_proof_composability_status(
    *,
    step_statuses: dict[str, ProofReplayStepStatus] | None = None,
    broken_witness_ids: tuple[str, ...] | list[str] | None = None,
    invalidation_reasons: tuple[str, ...] | list[str] | None = None,
    projection_preservation_passed: bool | None = None,
    new_ancestors: tuple[str, ...] | list[str] | None = None,
    new_district_links: tuple[tuple[str, str], ...] | list[tuple[str, str]] | None = None,
) -> ProofComposabilityStatus:
    """Infer the conservative replay status from local witness outcomes."""

    normalized_statuses = {
        step_id: (
            status
            if isinstance(status, ProofReplayStepStatus)
            else ProofReplayStepStatus(str(status))
        )
        for step_id, status in dict(step_statuses or {}).items()
    }
    broken = tuple(str(item).strip() for item in (broken_witness_ids or ()) if str(item).strip())
    reasons = tuple(str(item).strip() for item in (invalidation_reasons or ()) if str(item).strip())
    ancestors = tuple(str(item).strip() for item in (new_ancestors or ()) if str(item).strip())
    districts = tuple(tuple(item) for item in (new_district_links or ()))

    if (
        broken
        or reasons
        or any(status is ProofReplayStepStatus.INVALID for status in normalized_statuses.values())
    ):
        return ProofComposabilityStatus.REDERIVE

    if normalized_statuses and all(
        status is ProofReplayStepStatus.VALID for status in normalized_statuses.values()
    ):
        if projection_preservation_passed is True and not ancestors and not districts:
            return ProofComposabilityStatus.REUSABLE
        return ProofComposabilityStatus.REVALIDATE

    if (
        projection_preservation_passed is False
        or ancestors
        or districts
        or any(status is ProofReplayStepStatus.UNKNOWN for status in normalized_statuses.values())
    ):
        return ProofComposabilityStatus.REVALIDATE

    return ProofComposabilityStatus.UNKNOWN


def build_proof_composability_certificate(
    *,
    source_fragment_id: str,
    checked_query: str,
    composed_graph_ref: str | None = None,
    proof_trace_ref: EvidenceBundleRef | None = None,
    witness_index_ref: ProofWitnessIndexRef | None = None,
    preserved_witness_ids: tuple[str, ...] | list[str] | None = None,
    broken_witness_ids: tuple[str, ...] | list[str] | None = None,
    step_statuses: dict[str, ProofReplayStepStatus | str] | None = None,
    invalidation_reasons: tuple[str, ...] | list[str] | None = None,
    interface_vars: tuple[str, ...] | list[str] | None = None,
    new_ancestors: tuple[str, ...] | list[str] | None = None,
    new_district_links: tuple[tuple[str, str], ...] | list[tuple[str, str]] | None = None,
    projection_preservation_passed: bool | None = None,
    proof_support_projection_hash: str | None = None,
    invalidated_by_graph_hashes: tuple[str, ...] | list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    status: ProofComposabilityStatus | str | None = None,
) -> ProofComposabilityCertificate:
    """Build a composability certificate using the conservative replay theorem."""

    normalized_statuses = {
        step_id: (
            replay_status
            if isinstance(replay_status, ProofReplayStepStatus)
            else ProofReplayStepStatus(str(replay_status))
        )
        for step_id, replay_status in dict(step_statuses or {}).items()
    }
    resolved_status = status if isinstance(status, ProofComposabilityStatus) else None
    if resolved_status is None and status is not None:
        resolved_status = ProofComposabilityStatus(str(status))
    if resolved_status is None:
        resolved_status = infer_proof_composability_status(
            step_statuses=normalized_statuses,
            broken_witness_ids=broken_witness_ids,
            invalidation_reasons=invalidation_reasons,
            projection_preservation_passed=projection_preservation_passed,
            new_ancestors=new_ancestors,
            new_district_links=new_district_links,
        )
    return ProofComposabilityCertificate(
        status=resolved_status,
        source_fragment_id=source_fragment_id,
        composed_graph_ref=composed_graph_ref,
        checked_query=checked_query,
        proof_trace_ref=proof_trace_ref,
        witness_index_ref=witness_index_ref,
        preserved_witness_ids=tuple(preserved_witness_ids or ()),
        broken_witness_ids=tuple(broken_witness_ids or ()),
        step_statuses=normalized_statuses,
        invalidation_reasons=tuple(invalidation_reasons or ()),
        interface_vars=tuple(interface_vars or ()),
        new_ancestors=tuple(new_ancestors or ()),
        new_district_links=tuple(new_district_links or ()),
        projection_preservation_passed=projection_preservation_passed,
        proof_support_projection_hash=proof_support_projection_hash,
        invalidated_by_graph_hashes=tuple(invalidated_by_graph_hashes or ()),
        metadata=dict(metadata or {}),
    )


def proof_composability_summary(
    certificate: ProofComposabilityCertificate,
    *,
    ref: ProofComposabilityCertificateRef | None = None,
) -> dict[str, Any]:
    """Return a compact bundle-friendly summary of a composability certificate."""

    return {
        "status": certificate.status.value,
        "proof_composability_ref": ref.model_dump(mode="json") if ref is not None else None,
        "proof_trace_ref": (
            certificate.proof_trace_ref.model_dump(mode="json")
            if certificate.proof_trace_ref is not None
            else None
        ),
        "witness_index_ref": (
            certificate.witness_index_ref.model_dump(mode="json")
            if certificate.witness_index_ref is not None
            else None
        ),
        "preserved_witness_ids": list(certificate.preserved_witness_ids),
        "broken_witness_ids": list(certificate.broken_witness_ids),
        "projection_preservation_passed": certificate.projection_preservation_passed,
        "proof_support_projection_hash": certificate.proof_support_projection_hash,
        "invalidated_by_graph_hashes": list(certificate.invalidated_by_graph_hashes),
    }


def attach_proof_composability_to_proof_bundle(
    bundle: ProofBundle,
    ref: ProofComposabilityCertificateRef | None,
    certificate: ProofComposabilityCertificate,
) -> ProofBundle:
    """Attach replay/composability evidence to an existing proof bundle."""

    metadata = dict(bundle.metadata)
    summary = proof_composability_summary(certificate, ref=ref)
    metadata["proof_composability"] = summary
    metadata["proof_composability_ref"] = summary["proof_composability_ref"]
    metadata["proof_trace_ref"] = summary["proof_trace_ref"]
    metadata["witness_index_ref"] = summary["witness_index_ref"]
    metadata["composability_status"] = certificate.status.value
    return bundle.model_copy(
        update={
            "proof_trace_ref": certificate.proof_trace_ref,
            "composability_status": certificate.status.value,
            "composability_certificate_ref": ref,
            "witness_index_ref": certificate.witness_index_ref,
            "proof_support_projection_hash": certificate.proof_support_projection_hash,
            "invalidated_by_graph_hashes": list(certificate.invalidated_by_graph_hashes),
            "metadata": metadata,
        }
    )


def persist_proof_witness_index(
    store: ArtifactStore,
    witness_index: ProofWitnessIndex,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.proof_witness_index",
    schema_version: str = "1.0",
) -> ProofWitnessIndexRef:
    """Persist a proof-witness index and return its typed artifact reference."""

    ref = put_json_artifact(
        store,
        witness_index.model_dump(mode="json"),
        kind="ir.proof_witness_index",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ProofWitnessIndexRef.model_validate(ref)


def load_proof_witness_index(
    store: ArtifactStore,
    ref: ProofWitnessIndexRef,
) -> ProofWitnessIndex:
    """Load a proof-witness index."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ProofWitnessIndex.model_validate(payload)


def persist_proof_composability_certificate(
    store: ArtifactStore,
    certificate: ProofComposabilityCertificate,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.proof_composability_certificate",
    schema_version: str = "1.0",
) -> ProofComposabilityCertificateRef:
    """Persist a proof-composability certificate and return its typed ref."""

    ref = put_json_artifact(
        store,
        certificate.model_dump(mode="json"),
        kind="ir.proof_composability_certificate",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return ProofComposabilityCertificateRef.model_validate(ref)


def load_proof_composability_certificate(
    store: ArtifactStore,
    ref: ProofComposabilityCertificateRef,
) -> ProofComposabilityCertificate:
    """Load a proof-composability certificate."""

    payload = get_json_artifact(store, ref.artifact_id)
    return ProofComposabilityCertificate.model_validate(payload)


__all__ = [
    "ProofComposabilityCertificate",
    "ProofComposabilityStatus",
    "ProofGraphWitness",
    "ProofObligationKind",
    "ProofReplayStepStatus",
    "ProofWitnessIndex",
    "attach_proof_composability_to_proof_bundle",
    "build_proof_composability_certificate",
    "infer_proof_composability_status",
    "load_proof_composability_certificate",
    "load_proof_witness_index",
    "persist_proof_composability_certificate",
    "persist_proof_witness_index",
    "proof_composability_summary",
]
