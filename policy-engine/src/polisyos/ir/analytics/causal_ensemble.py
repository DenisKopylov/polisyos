"""Represent structural-uncertainty ensembles over causal graph candidates."""

from __future__ import annotations

import math

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.ir.analytics.uncertainty import (
    DistributionFamily,
    IntervalSemantics,
    PropagationMethod,
    UncertaintyEnvelope,
    UncertaintySource,
)
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.registry.refs import CausalModelEnsembleRef


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

    schema_version: str = Field("1.0", pattern=r"^\d+\.\d+$")
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


def persist_causal_model_ensemble(
    store: ArtifactStore,
    ensemble: CausalModelEnsemble,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_model_ensemble",
    schema_version: str = "1.0",
) -> CausalModelEnsembleRef:
    """Persist a causal-model ensemble artifact for structural-uncertainty reporting."""
    ref = put_json_artifact(
        store,
        ensemble.model_dump(mode="json"),
        kind="ir.causal_model_ensemble",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalModelEnsembleRef.model_validate(ref)


def load_causal_model_ensemble(
    store: ArtifactStore,
    ref: CausalModelEnsembleRef,
) -> CausalModelEnsemble:
    """Load causal model ensemble."""
    payload = get_json_artifact(store, ref.artifact_id)
    return CausalModelEnsemble.model_validate(payload)


__all__ = [
    "CausalModelEnsemble",
    "EnsembleMember",
    "load_causal_model_ensemble",
    "persist_causal_model_ensemble",
]
