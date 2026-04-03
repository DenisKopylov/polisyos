"""Public observation causal execution module API."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, model_validator

from polisyos.foundry.methods.catalog.causal.protocols import DynamicTreatmentData
from polisyos.ir.analytics.dynamic_regime import ContinuousTimeQuery, TemporalInterventionTrajectory
from polisyos.ir.artifacts import ArtifactStore, InputRef, get_json_artifact, put_json_artifact
from polisyos.ir.canon import CanonSpec
from polisyos.ir.governance.policy_spec import TemporalInterventionSequence
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.observation.bundles import BoundsEstimationBundle, DTRTreatmentSequenceBundleManifest
from polisyos.ir.observation.contract_compilers import BoundsEstimationInput
from polisyos.ir.observation.contracts import IdentificationMode, ObservationFamily, StrategicResponseChannel
from polisyos.ir.refs import (
    BoundsBundleRef,
    CausalExecutionBundleRef,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
)

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
_CAUSAL_EXECUTION_SCHEMA_NAME = "ir.causal_execution_bundle"
_CAUSAL_EXECUTION_SCHEMA_VERSION = "1.0"


class BoundsEstimationTask(KernelModel):
    """Executable bounds-estimation task assembled from observation contracts."""

    task_id: str = Field(..., pattern=ID_PATTERN)
    bounds_input: BoundsEstimationInput
    bundle: BoundsEstimationBundle
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalDTRTask(KernelModel):
    """Executable dynamic treatment regime task for sequential interventions.

    Tasks can be backed by fully materialized dynamic-treatment data, a bundle
    manifest, an explicit temporal intervention sequence, or raw step payloads.
    """

    task_id: str = Field(..., pattern=ID_PATTERN)
    dtr_method: Literal["q_learning", "a_learning", "owl", "dr_dtr"] = "q_learning"
    dynamic_treatment_data: DynamicTreatmentData | None = None
    bundle_manifest: DTRTreatmentSequenceBundleManifest | None = None
    temporal_sequence: TemporalInterventionSequence | None = None
    sequence_id: str | None = Field(default=None, pattern=ID_PATTERN)
    dynamic_intervention_id: str | None = Field(default=None, pattern=ID_PATTERN)
    steps: list[dict[str, Any]] = Field(default_factory=list)
    compiled_interventions: Any | None = None
    identification_mode: IdentificationMode = IdentificationMode.SEQUENTIAL
    strategic_response_expected: bool = False
    transmission_channels: list[StrategicResponseChannel] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    n_units: int = Field(default=10, ge=10)
    time_ids: list[Any] = Field(default_factory=list)
    covariate_names: list[str] = Field(default_factory=list)
    outcome: list[float] | None = None
    continuous_time_query: ContinuousTimeQuery | None = None
    intervention_trajectory: TemporalInterventionTrajectory | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_source(self) -> "TemporalDTRTask":
        has_manifest_payload = bool(
            self.bundle_manifest is not None and self.bundle_manifest.contract_payload
        )
        if any(
            (
                self.dynamic_treatment_data is not None,
                has_manifest_payload,
                self.temporal_sequence is not None,
                bool(self.steps),
            )
        ):
            return self
        raise ValueError(
            "temporal DTR task requires one of dynamic_treatment_data, "
            "bundle_manifest.contract_payload, temporal_sequence, or steps"
        )


class BoundsEstimationEntry(KernelModel):
    """Result row for one bounds-estimation task in a causal execution bundle."""

    task_id: str = Field(..., pattern=ID_PATTERN)
    family: ObservationFamily
    status: Literal["ok", "blocked"]
    interval: tuple[float, float] | None = None
    width: float | None = None
    informative: bool = False
    warnings: list[str] = Field(default_factory=list)
    bounds_bundle_ref: BoundsBundleRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _derive_width(self) -> "BoundsEstimationEntry":
        if self.interval is not None and self.width is None:
            object.__setattr__(self, "width", float(self.interval[1] - self.interval[0]))
        return self


class TemporalDTRExecutionEntry(KernelModel):
    """Execution summary for one temporal dynamic-treatment task."""

    task_id: str = Field(..., pattern=ID_PATTERN)
    sequence_id: str | None = Field(default=None, pattern=ID_PATTERN)
    dynamic_intervention_id: str | None = Field(default=None, pattern=ID_PATTERN)
    status: Literal["ok", "blocked"]
    dtr_method: Literal["q_learning", "a_learning", "owl", "dr_dtr"]
    value_estimate: float | None = None
    warnings: list[str] = Field(default_factory=list)
    dynamic_treatment_regime_ref: DynamicTreatmentRegimeRef | None = None
    effect_trajectory_bundle_ref: EffectTrajectoryBundleRef | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CausalExecutionBundle(KernelModel):
    """Persistable bundle of causal execution outcomes.

    Groups bounds and temporal treatment results emitted by Scientist runners
    so downstream governance, reporting, and artifact loading can treat the
    execution step as a single IR artifact.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    bounds_results: list[BoundsEstimationEntry] = Field(default_factory=list)
    temporal_results: list[TemporalDTRExecutionEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> "CausalExecutionBundle":
        bounds_ids = [item.task_id for item in self.bounds_results]
        if len(bounds_ids) != len(set(bounds_ids)):
            raise ValueError("bounds_results.task_id must be unique")
        temporal_ids = [item.task_id for item in self.temporal_results]
        if len(temporal_ids) != len(set(temporal_ids)):
            raise ValueError("temporal_results.task_id must be unique")
        return self


def persist_causal_execution_bundle(
    store: ArtifactStore,
    bundle: CausalExecutionBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = _CAUSAL_EXECUTION_SCHEMA_NAME,
    schema_version: str = _CAUSAL_EXECUTION_SCHEMA_VERSION,
) -> CausalExecutionBundleRef:
    """Persist a causal execution bundle to the artifact store.

    Args:
        store: Artifact store that owns the persisted JSON payload.
        bundle: Execution results to serialize.
        inputs: Optional upstream artifact references for lineage tracking.
        schema_name: Canonical schema name attached to the artifact metadata.
        schema_version: Canonical schema version attached to the artifact metadata.

    Returns:
        Typed artifact reference pointing at the stored execution bundle.
    """

    ref = put_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        kind="ir.causal_execution_bundle",
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalExecutionBundleRef.model_validate(ref)


def load_causal_execution_bundle(
    store: ArtifactStore,
    ref: CausalExecutionBundleRef,
) -> CausalExecutionBundle:
    """Load a persisted causal execution bundle from the artifact store."""

    payload = get_json_artifact(store, ref.artifact_id)
    return CausalExecutionBundle.model_validate(payload)


__all__ = [
    "BoundsEstimationEntry",
    "BoundsEstimationTask",
    "CausalExecutionBundle",
    "TemporalDTRExecutionEntry",
    "TemporalDTRTask",
    "load_causal_execution_bundle",
    "persist_causal_execution_bundle",
]
