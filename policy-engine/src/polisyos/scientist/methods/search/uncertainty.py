"""Typed search uncertainty contracts for funnel routing and judge semantics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo, input_ref_from_artifact_ref
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.ir import UncertaintyType


class UncertaintyEstimate(BaseModel):
    """Single typed uncertainty estimate."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    level: float = Field(ge=0.0, le=1.0)
    source: str = Field(min_length=1)
    quantification_method: str = Field(min_length=1)
    is_reducible: bool
    recommended_action: str | None = None


class UncertaintyEnvelope(BaseModel):
    """Typed uncertainty attached to search-stage confidence claims."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    uncertainties: dict[UncertaintyType, UncertaintyEstimate]

    @model_validator(mode="after")
    def _validate_all_types_present(self) -> UncertaintyEnvelope:
        expected = set(UncertaintyType)
        actual = set(self.uncertainties)
        if actual != expected:
            missing = sorted(item.value for item in expected - actual)
            extra = sorted(str(item) for item in actual - expected)
            problems: list[str] = []
            if missing:
                problems.append(f"missing={missing}")
            if extra:
                problems.append(f"extra={extra}")
            raise ValueError(
                "uncertainties must contain exactly one estimate for each "
                f"UncertaintyType ({', '.join(problems)})"
            )
        return self

    @staticmethod
    def _unknown_estimate(
        *,
        source: str,
        quantification_method: str,
        is_reducible: bool,
    ) -> UncertaintyEstimate:
        return UncertaintyEstimate(
            level=1.0,
            source=source,
            quantification_method=quantification_method,
            is_reducible=is_reducible,
        )

    @classmethod
    def unknown(
        cls,
        source: str = "not assessed at this fidelity",
        *,
        quantification_method: str = "not_assessed",
        is_reducible: bool = True,
    ) -> UncertaintyEnvelope:
        """Build an envelope where every type is unassessed and maximally uncertain."""

        return cls(
            uncertainties={
                uncertainty_type: cls._unknown_estimate(
                    source=source,
                    quantification_method=quantification_method,
                    is_reducible=is_reducible,
                )
                for uncertainty_type in UncertaintyType
            }
        )

    @classmethod
    def deterministic(cls) -> UncertaintyEnvelope:
        """Compatibility factory for deterministic gates that do not assess uncertainty."""

        return cls.unknown(
            source="deterministic gate; not assessed at this fidelity",
            quantification_method="static_rule",
            is_reducible=True,
        )

    @classmethod
    def from_partial(
        cls,
        partial: Mapping[UncertaintyType, UncertaintyEstimate],
        *,
        source: str = "not assessed at this fidelity",
        quantification_method: str = "not_assessed",
        is_reducible: bool = True,
    ) -> UncertaintyEnvelope:
        """Fill missing uncertainty types with explicit unassessed estimates."""

        payload: dict[UncertaintyType, UncertaintyEstimate] = {}
        for uncertainty_type in UncertaintyType:
            payload[uncertainty_type] = partial.get(
                uncertainty_type,
                cls._unknown_estimate(
                    source=source,
                    quantification_method=quantification_method,
                    is_reducible=is_reducible,
                ),
            )
        return cls(uncertainties=payload)

    @classmethod
    def merge_max(
        cls,
        envelopes: Iterable[UncertaintyEnvelope],
    ) -> UncertaintyEnvelope:
        """Merge envelopes by taking the highest uncertainty estimate per type."""

        envelope_list = list(envelopes)
        if not envelope_list:
            return cls.unknown()

        payload: dict[UncertaintyType, UncertaintyEstimate] = {}
        for uncertainty_type in UncertaintyType:
            payload[uncertainty_type] = max(
                (env.uncertainties[uncertainty_type] for env in envelope_list),
                key=lambda estimate: estimate.level,
            )
        return cls(uncertainties=payload)

    def with_update(
        self,
        uncertainty_type: UncertaintyType,
        estimate: UncertaintyEstimate,
    ) -> UncertaintyEnvelope:
        """Return a new envelope with one estimate replaced."""

        updated = dict(self.uncertainties)
        updated[uncertainty_type] = estimate
        return UncertaintyEnvelope(uncertainties=updated)


class SearchUncertaintyBasis(BaseModel):
    """Producer-declared scientific identity for a routing observation.

    Content binding proves identity, not the producer's refinement law or any
    publication authority. No observation supersedes another under this contract.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    subject_ref: ArtifactRef
    value_ref: ArtifactRef
    input_refs: tuple[ArtifactRef, ...] = Field(min_length=1)
    rule_ref: ArtifactRef
    producer_ref: ArtifactRef
    valid_time: AwareDatetime
    estimand: str = Field(min_length=1)
    unit: str = Field(min_length=1)


class SearchUncertaintyObservation(BaseModel):
    """A producer observation whose envelope and complete basis are CAS bound."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    basis_ref: ArtifactRef
    producer_ref: ArtifactRef
    risk_ref: ArtifactRef
    envelope: UncertaintyEnvelope


def search_uncertainty_observation_ref(payload: Mapping[str, object]) -> ArtifactRef | None:
    """Read a native producer ref for later content-bound intake, without admission."""
    raw = payload.get("uncertainty_observation_ref")
    if raw is None:
        return None
    try:
        return ArtifactRef.model_validate(raw)
    except (TypeError, ValueError):
        return None


def persist_search_uncertainty(
    store: FileSystemCAS,
    payload: SearchUncertaintyBasis | SearchUncertaintyObservation,
) -> ArtifactRef:
    """Persist a supplied routing basis or observation without granting authority."""
    suffix = "basis" if isinstance(payload, SearchUncertaintyBasis) else "observation"
    dependencies = (
        [
            payload.subject_ref,
            payload.value_ref,
            *payload.input_refs,
            payload.rule_ref,
            payload.producer_ref,
        ]
        if isinstance(payload, SearchUncertaintyBasis)
        else [payload.basis_ref, payload.producer_ref, payload.risk_ref]
    )
    return store.put_json(
        payload,
        PutOptions(
            kind=f"scientist.search.uncertainty_{suffix}",
            media_type="application/json",
            schema=SchemaInfo(name=type(payload).__name__, version=payload.schema_version),
            inputs=[
                input_ref_from_artifact_ref(ref, role="uncertainty_input") for ref in dependencies
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
    )


def load_search_uncertainty_observation(
    store: FileSystemCAS,
    observation_ref: ArtifactRef,
    expected_basis_ref: ArtifactRef,
    expected_envelope: UncertaintyEnvelope,
    expected_subject_ref: ArtifactRef,
) -> SearchUncertaintyObservation:
    """Resolve actual bytes and reject a stale, foreign or substituted observation."""
    for ref, kind in (
        (observation_ref, "scientist.search.uncertainty_observation"),
        (expected_basis_ref, "scientist.search.uncertainty_basis"),
    ):
        if ref.kind != kind or store.get_manifest(ref).kind != kind:
            raise ValueError("Search uncertainty artifact kind mismatch")
        if not store.verify(ref).ok:
            raise ValueError("Search uncertainty artifact integrity failure")
    basis = SearchUncertaintyBasis.model_validate(
        from_canonical_bytes(store.get_bytes(expected_basis_ref))
    )
    if basis.subject_ref != expected_subject_ref:
        raise ValueError("Search uncertainty basis differs from the configured candidate")
    observation = SearchUncertaintyObservation.model_validate(
        from_canonical_bytes(store.get_bytes(observation_ref))
    )
    if observation.basis_ref != expected_basis_ref:
        raise ValueError("Search uncertainty observation has a foreign or stale basis")
    if observation.producer_ref != basis.producer_ref:
        raise ValueError("Search uncertainty observation has a foreign producer")
    if observation.envelope != expected_envelope:
        raise ValueError("Search uncertainty observation differs from the stage envelope")
    # Every declared input must resolve; a plausible ref is not a supplied input.
    for ref in (
        basis.subject_ref,
        basis.value_ref,
        *basis.input_refs,
        basis.rule_ref,
        basis.producer_ref,
        observation.risk_ref,
    ):
        store.get_manifest(ref)
        store.get_bytes(ref)
    return observation
