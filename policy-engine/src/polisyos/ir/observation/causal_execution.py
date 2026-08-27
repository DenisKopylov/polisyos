"""Define executable causal tasks and persisted execution-result bundles.

Execution bundles are the post-readiness boundary object: Scientist runners
consume task specs such as ``BoundsEstimationTask`` and ``TemporalDTRTask``,
emit result rows, and persist a ``CausalExecutionBundle`` for downstream
governance, reporting, and artifact loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from pydantic import Field, model_validator

from polisyos.ir._internal.validation import ensure_unique_ids
from polisyos.ir.artifacts import (
    ArtifactStore,
    ArtifactTaskBinding,
    InputRef,
    get_json_artifact,
    put_json_artifact,
)
from polisyos.ir.artifacts.contracts import ArtifactID
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.model_layer.canon import CanonSpec
from polisyos.ir.observation.contracts import (
    IdentificationMode,
    ObservationFamily,
    StrategicResponseChannel,
)
from polisyos.ir.registry.refs import (
    BoundsBundleRef,
    CausalExecutionBundleRef,
    DynamicTreatmentRegimeRef,
    EffectTrajectoryBundleRef,
)

if TYPE_CHECKING:
    from polisyos.ir.analytics.dynamic_regime import (
        ContinuousTimeQuery,
        TemporalInterventionTrajectory,
    )
    from polisyos.ir.governance.policy_spec import TemporalInterventionSequence
    from polisyos.ir.observation.bundles import (
        BoundsEstimationBundle,
        DTRTreatmentSequenceBundleManifest,
    )
    from polisyos.ir.observation.contract_compilers import BoundsEstimationInput
else:
    from polisyos.ir.analytics.dynamic_regime import (
        ContinuousTimeQuery,
        TemporalInterventionTrajectory,
    )
    from polisyos.ir.governance.policy_spec import TemporalInterventionSequence
    from polisyos.ir.observation.bundles import (
        BoundsEstimationBundle,
        DTRTreatmentSequenceBundleManifest,
    )
    from polisyos.ir.observation.contract_compilers import BoundsEstimationInput

SCHEMA_VERSION_PATTERN = r"^\d+\.\d+$"
_CAUSAL_EXECUTION_SCHEMA_NAME = "ir.causal_execution_bundle"
_CAUSAL_EXECUTION_SCHEMA_VERSION = "1.0"


class BoundsEstimationTask(KernelModel):
    """Package one bounds-estimation run assembled from observation contracts.

    This task couples compiler output (``bounds_input``) with the strategy
    catalog in ``bundle`` and optional estimator parameters. Bounds runners can
    execute this object directly after readiness checks pass.
    """

    task_id: str = Field(..., pattern=ID_PATTERN)
    bounds_input: BoundsEstimationInput
    bundle: BoundsEstimationBundle
    params: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemporalDTRTask(KernelModel):
    """Executable dynamic treatment regime task for sequential interventions.

    Tasks can be backed by a neutral dynamic-treatment payload, a bundle
    manifest, an explicit temporal intervention sequence, or raw step payloads.
    """

    task_id: str = Field(..., pattern=ID_PATTERN)
    dtr_method: Literal["q_learning", "a_learning", "owl", "dr_dtr"] = "q_learning"
    dynamic_treatment_data: dict[str, Any] | None = None
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
    def _validate_source(self) -> TemporalDTRTask:
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
    """Store the outcome of one bounds-estimation task.

    ``status`` is read by downstream reporting and governance: ``ok`` means the
    interval can be surfaced, while ``blocked`` means callers should inspect
    ``warnings`` and avoid treating ``interval`` as decision-grade output.
    """

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
    def _derive_width(self) -> BoundsEstimationEntry:
        if self.interval is not None and self.width is None:
            object.__setattr__(self, "width", float(self.interval[1] - self.interval[0]))
        return self


class TemporalDTRExecutionEntry(KernelModel):
    """Store one dynamic-treatment execution result and its artifact refs.

    Temporal DTR runners write ``value_estimate`` plus optional trajectory and
    policy refs; downstream governance reads ``status`` to decide whether the
    sequence result is usable or blocked.
    """

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
    """Persist bounds and sequential-treatment outputs with status and lineage metadata.

    Groups bounds and temporal treatment results emitted by Scientist runners
    so downstream governance, reporting, and artifact loading can treat the
    execution step as a single IR artifact.
    """

    schema_version: str = Field("1.0", pattern=SCHEMA_VERSION_PATTERN)
    bounds_results: list[BoundsEstimationEntry] = Field(default_factory=list)
    temporal_results: list[TemporalDTRExecutionEntry] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_unique_ids(self) -> CausalExecutionBundle:
        ensure_unique_ids(
            self.bounds_results,
            key_fn=lambda item: item.task_id,
            label="bounds_results.task_id",
        )
        ensure_unique_ids(
            self.temporal_results,
            key_fn=lambda item: item.task_id,
            label="temporal_results.task_id",
        )
        return self

    def root_artifact_ids(self) -> tuple[ArtifactID, ...]:
        """Return result artifacts that act as lineage roots for this execution bundle."""
        root_ids: set[str] = set()
        for entry in self.bounds_results:
            if entry.bounds_bundle_ref is not None:
                root_ids.add(str(entry.bounds_bundle_ref.artifact_id))
        for entry in self.temporal_results:
            if entry.dynamic_treatment_regime_ref is not None:
                root_ids.add(str(entry.dynamic_treatment_regime_ref.artifact_id))
            if entry.effect_trajectory_bundle_ref is not None:
                root_ids.add(str(entry.effect_trajectory_bundle_ref.artifact_id))
        return tuple(ArtifactID.model_validate(artifact_id) for artifact_id in sorted(root_ids))

    def artifact_task_bindings(self) -> tuple[ArtifactTaskBinding, ...]:
        """Map execution task ids onto the artifacts they produced."""
        bindings: list[ArtifactTaskBinding] = []
        for entry in sorted(self.bounds_results, key=lambda item: item.task_id):
            produced: list[ArtifactID] = []
            if entry.bounds_bundle_ref is not None:
                produced.append(entry.bounds_bundle_ref.artifact_id)
            bindings.append(
                ArtifactTaskBinding(
                    task_id=entry.task_id,
                    task_kind="bounds_estimation",
                    produced_artifact_ids=tuple(sorted(produced, key=str)),
                    metadata={"status": entry.status, "family": entry.family.value},
                )
            )
        for entry in sorted(self.temporal_results, key=lambda item: item.task_id):
            produced = []
            if entry.dynamic_treatment_regime_ref is not None:
                produced.append(entry.dynamic_treatment_regime_ref.artifact_id)
            if entry.effect_trajectory_bundle_ref is not None:
                produced.append(entry.effect_trajectory_bundle_ref.artifact_id)
            bindings.append(
                ArtifactTaskBinding(
                    task_id=entry.task_id,
                    task_kind="temporal_dtr",
                    produced_artifact_ids=tuple(sorted(produced, key=str)),
                    metadata={"status": entry.status, "method": entry.dtr_method},
                )
            )
        return tuple(bindings)


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
    """Load and validate a persisted execution bundle from artifact storage.

    Args:
        store: Artifact store containing the JSON payload.
        ref: Typed execution-bundle reference returned by the persistence helper.

    Returns:
        The validated causal execution bundle.
    """

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
