"""Represent structural-uncertainty ensembles over causal graph candidates."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any, ClassVar

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore  # noqa: TC001
from polisyos.ir.artifacts._lineage import InputRefLike  # noqa: TC001
from polisyos.ir.artifacts.contracts import ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalModelEnsembleRef

_CAUSAL_MODEL_ENSEMBLE_SCHEMA_VERSION = "1.0"


class EnsembleMember(BaseModel):
    """One graph candidate inside a structural-uncertainty ensemble."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    graph_ref: str = Field(min_length=1)
    discovery_method: str = Field(min_length=1)
    weight: float = Field(ge=0.0, le=1.0)
    bootstrap_stability: float = Field(ge=0.0, le=1.0)


class CausalModelEnsemble(BaseModel):
    """Ensemble of causal models capturing structural uncertainty."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    SCHEMA_VERSION: ClassVar[str] = _CAUSAL_MODEL_ENSEMBLE_SCHEMA_VERSION
    schema_version: str = Field(_CAUSAL_MODEL_ENSEMBLE_SCHEMA_VERSION, pattern=r"^\d+\.\d+$")
    members: list[EnsembleMember]
    consensus_graph_ref: str | None = None
    edge_inclusion_frequency: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_members_and_frequency(self) -> CausalModelEnsemble:
        n_members = len(self.members)
        if n_members < 1:
            raise ValueError("CausalModelEnsemble must contain at least one member")
        if n_members > 10:
            raise ValueError("CausalModelEnsemble supports at most 10 members")

        total_weight = sum(float(member.weight) for member in self.members)
        if not math.isfinite(total_weight):
            raise ValueError("member weights must be finite")
        if total_weight <= 0.0:
            raise ValueError("sum of member weights must be > 0")

        for edge_key, freq in self.edge_inclusion_frequency.items():
            if not edge_key:
                raise ValueError("edge_inclusion_frequency keys must be non-empty")
            if not (0.0 <= float(freq) <= 1.0):
                raise ValueError("edge_inclusion_frequency values must be in [0,1]")
        return self

    def to_uncertainty_envelope(
        self,
        query_results: dict[str, list[float]],
    ) -> UncertaintyEnvelope:
        all_estimates: list[float] = []
        for estimates in query_results.values():
            for raw in estimates:
                value = float(raw)
                if math.isfinite(value):
                    all_estimates.append(value)

        if not all_estimates:
            sentinel = 1.0e12
            return UncertaintyEnvelope(
                schema_version=UncertaintyEnvelope.SCHEMA_VERSION,
                point_estimate=0.0,
                confidence_interval=(-sentinel, sentinel),
                confidence_level=None,
                distribution_family=DistributionFamily.UNKNOWN,
                source=UncertaintySource.ENSEMBLE,
                propagation_method=PropagationMethod.NONE,
                interval_semantics=IntervalSemantics.HEURISTIC_RANGE,
                is_heuristic_ci=True,
                gate_eligible=False,
                metadata={
                    "member_count": len(self.members),
                    "edge_frequency_count": len(self.edge_inclusion_frequency),
                    "empty_estimates": True,
                },
            )

        arr = np.asarray(all_estimates, dtype=float)
        return UncertaintyEnvelope(
            schema_version=UncertaintyEnvelope.SCHEMA_VERSION,
            point_estimate=float(np.median(arr)),
            confidence_interval=(
                float(np.percentile(arr, 2.5)),
                float(np.percentile(arr, 97.5)),
            ),
            confidence_level=0.95,
            distribution_family=DistributionFamily.BOOTSTRAP,
            source=UncertaintySource.ENSEMBLE,
            propagation_method=PropagationMethod.MONTE_CARLO,
            interval_semantics=IntervalSemantics.CONFIDENCE_INTERVAL,
            sample_size=int(arr.size),
            is_heuristic_ci=False,
            gate_eligible=True,
            metadata={
                "member_count": len(self.members),
                "edge_frequency_count": len(self.edge_inclusion_frequency),
                "consensus_graph_ref": self.consensus_graph_ref,
            },
        )


def _family_payload_version(value: object) -> str | None:
    """Return a strict embedded version, distinguishing absence from malformed null."""
    if not isinstance(value, Mapping):
        raise ValueError("owned family payload must be an object")
    if "schema_version" not in value:
        return None
    version = value["schema_version"]
    if type(version) is not str or not version.strip():
        raise ValueError("owned family payload schema_version must be a nonempty string")
    return version


def _family_source_mapping(value: object, admission: ResolvedSchemaAdmission) -> dict[str, Any]:
    """Bind payload bytes to the exact tuple already selected from the owner snapshot."""
    if not isinstance(value, Mapping):
        raise ValueError("owned family payload must be an object")
    if _family_payload_version(value) != admission.source_registration.payload_version:
        raise ValueError("payload version differs from exact registered tuple")
    return dict(value)


def _family_profile(profile: CanonInfo, row: IRRepresentationRegistration) -> bool:
    """Require the producer's actual canonicalization profile and no profile alias."""
    return (
        profile == CanonInfo.from_spec(CanonSpec(forbid_floats=False)) and row.profile_ref is None
    )


_ENSEMBLE_OWNER_POLICY = ("causal-model-ensemble-json", "1")
_ENSEMBLE_OWNER = ArtifactOwnerDeclaration(
    contract_id="polisyos.ir.analytics.causal_ensemble.CausalModelEnsemble",
    dto_fqn="polisyos.ir.analytics.causal_ensemble.CausalModelEnsemble",
    abi_key="causal_model_ensemble",
    registry_key="causal_model_ensemble",
    kind="ir.causal_model_ensemble",
    media_type="application/json",
    purpose="causal_model_ensemble",
    policy_revision="1",
    accepted_wire_policies=(_ENSEMBLE_OWNER_POLICY,),
    payload_version_of=_family_payload_version,
    validate_source=_family_source_mapping,
    project_for_consumer=lambda value, _admission: CausalModelEnsemble.model_validate(value),
    validate_profile=_family_profile,
)


def _register_ensemble_owner() -> None:
    """Register the current typed ensemble row as its only default writer."""
    version = CausalModelEnsemble.SCHEMA_VERSION
    register_schema_version(
        "causal_model_ensemble",
        version,
        compatibility=CompatibilityMode.NONE,
        notes=("CausalModelEnsemble current owner JSON representation.",),
    )
    register_ir_representation(
        registry_key="causal_model_ensemble",
        owner_ref=_ENSEMBLE_OWNER.contract_id,
        dto_abi=_ENSEMBLE_OWNER.dto_fqn,
        wire_policy_ref=_ENSEMBLE_OWNER_POLICY[0],
        wire_policy_revision=_ENSEMBLE_OWNER_POLICY[1],
        schema_name="ir.causal_model_ensemble",
        schema_version=version,
        payload_version=version,
        writable=True,
        current=True,
        default_write=True,
    )


_register_ensemble_owner()


def persist_causal_model_ensemble(
    store: ArtifactStore,
    ensemble: CausalModelEnsemble,
    *,
    inputs: Sequence[InputRefLike] | None = None,
    schema_name: str = "ir.causal_model_ensemble",
    schema_version: str = CausalModelEnsemble.SCHEMA_VERSION,
) -> CausalModelEnsembleRef:
    """Persist the ensemble through its exact owner-registered tuple."""
    ref = _put_owned_json_artifact(
        store,
        ensemble.model_dump(mode="json"),
        owner=_ENSEMBLE_OWNER,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalModelEnsembleRef.from_selected_write(ref)


def load_causal_model_ensemble(
    store: ArtifactStore,
    ref: CausalModelEnsembleRef,
) -> CausalModelEnsemble:
    """Load through exact owner-bound artifact admission."""
    return _get_owned_json_artifact(store, ref, owner=_ENSEMBLE_OWNER)


__all__ = [
    "CausalModelEnsemble",
    "EnsembleMember",
    "load_causal_model_ensemble",
    "persist_causal_model_ensemble",
]
