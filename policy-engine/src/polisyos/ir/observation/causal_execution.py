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
from polisyos.ir.artifacts import ArtifactStore, ArtifactTaskBinding, InputRef
from polisyos.ir.artifacts.contracts import ArtifactID, ArtifactOwnerDeclaration, CanonInfo
from polisyos.ir.artifacts.io import _get_owned_json_artifact, _put_owned_json_artifact
from polisyos.ir.kernel.base import ID_PATTERN, KernelModel
from polisyos.ir.migrations.base import (
    CompatibilityMode,
    IRRepresentationRegistration,
    ResolvedSchemaAdmission,
    register_ir_representation,
    register_schema_version,
)
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
        for bounds_entry in self.bounds_results:
            if bounds_entry.bounds_bundle_ref is not None:
                root_ids.add(str(bounds_entry.bounds_bundle_ref.artifact_id))
        for temporal_entry in self.temporal_results:
            if temporal_entry.dynamic_treatment_regime_ref is not None:
                root_ids.add(str(temporal_entry.dynamic_treatment_regime_ref.artifact_id))
            if temporal_entry.effect_trajectory_bundle_ref is not None:
                root_ids.add(str(temporal_entry.effect_trajectory_bundle_ref.artifact_id))
        return tuple(ArtifactID.model_validate(artifact_id) for artifact_id in sorted(root_ids))

    def artifact_task_bindings(self) -> tuple[ArtifactTaskBinding, ...]:
        """Map execution task ids onto the artifacts they produced."""
        bindings: list[ArtifactTaskBinding] = []
        for bounds_entry in sorted(self.bounds_results, key=lambda item: item.task_id):
            bounds_produced: list[ArtifactID] = []
            if bounds_entry.bounds_bundle_ref is not None:
                bounds_produced.append(bounds_entry.bounds_bundle_ref.artifact_id)
            bindings.append(
                ArtifactTaskBinding(
                    task_id=bounds_entry.task_id,
                    task_kind="bounds_estimation",
                    produced_artifact_ids=tuple(sorted(bounds_produced, key=str)),
                    metadata={"status": bounds_entry.status, "family": bounds_entry.family.value},
                )
            )
        for temporal_entry in sorted(self.temporal_results, key=lambda item: item.task_id):
            temporal_produced: list[ArtifactID] = []
            if temporal_entry.dynamic_treatment_regime_ref is not None:
                temporal_produced.append(temporal_entry.dynamic_treatment_regime_ref.artifact_id)
            if temporal_entry.effect_trajectory_bundle_ref is not None:
                temporal_produced.append(temporal_entry.effect_trajectory_bundle_ref.artifact_id)
            bindings.append(
                ArtifactTaskBinding(
                    task_id=temporal_entry.task_id,
                    task_kind="temporal_dtr",
                    produced_artifact_ids=tuple(sorted(temporal_produced, key=str)),
                    metadata={"status": temporal_entry.status, "method": temporal_entry.dtr_method},
                )
            )
        return tuple(bindings)


_OWNER_SCHEMA_NAME = "ir.causal_execution_bundle"
_OWNER_SCHEMA_VERSION = _CAUSAL_EXECUTION_SCHEMA_VERSION
_OWNER_WIRE_POLICY = ("ir.owner.causalexecutionbundle.wire", "1")


def _owner_payload_version(payload: object) -> str:
    """Require an embedded source version; a DTO default is not historical evidence."""
    if not isinstance(payload, dict):
        raise TypeError("Owned CausalExecutionBundle payload must be a JSON object")
    version = payload.get("schema_version")
    if type(version) is not str or not version.strip():
        raise ValueError("Owned CausalExecutionBundle payload requires an explicit schema_version")
    return version


def _validate_owner_source(
    payload: object, admission: ResolvedSchemaAdmission
) -> CausalExecutionBundle:
    """Validate bytes only under this owner exact registered source representation."""
    registration = admission.source_registration
    if registration.schema_name != _OWNER_SCHEMA_NAME:
        raise ValueError("Owned CausalExecutionBundle source has the wrong schema name")
    if registration.payload_version != _owner_payload_version(payload):
        raise ValueError(
            "Owned CausalExecutionBundle payload version disagrees with its representation"
        )
    return CausalExecutionBundle.model_validate(payload)


def _project_owner_source(
    source: CausalExecutionBundle,
    admission: ResolvedSchemaAdmission,
) -> CausalExecutionBundle:
    """Preserve the validated source value when no semantic projection is declared."""
    if not isinstance(source, CausalExecutionBundle):
        raise TypeError("Owned CausalExecutionBundle source was not validated by its owner")
    if admission.source_registration.payload_version != source.schema_version:
        raise ValueError("Owned CausalExecutionBundle projection would change the source version")
    return source


def _validate_owner_profile(
    profile: CanonInfo,
    registration: IRRepresentationRegistration,
) -> bool:
    """Accept only the canonical profile used by this family real writer."""
    expected = CanonInfo.from_spec(CanonSpec(forbid_floats=False))
    return registration.profile_ref is None and profile == expected


_causalexecutionbundle_owner = ArtifactOwnerDeclaration(
    contract_id="ir.observation.causal_execution_bundle.v1",
    dto_fqn="polisyos.ir.observation.causal_execution.CausalExecutionBundle",
    abi_key="ir.causal_execution_bundle",
    registry_key="ir.causal_execution_bundle",
    kind="ir.causal_execution_bundle",
    media_type="application/json",
    purpose="ir.causal_execution_bundle.typed_consumer",
    policy_revision="ir.observation.causal_execution_bundle.v1.owner-admission.v1",
    accepted_wire_policies=(_OWNER_WIRE_POLICY,),
    payload_version_of=_owner_payload_version,
    validate_source=_validate_owner_source,
    project_for_consumer=_project_owner_source,
    validate_profile=_validate_owner_profile,
)


register_schema_version(
    _OWNER_SCHEMA_NAME,
    _OWNER_SCHEMA_VERSION,
    compatibility=CompatibilityMode.NONE,
    notes=(
        (
            "CausalExecutionBundle current owner-admitted represe"
            "ntation; historical predecessors are not registered."
        ),
    ),
)
register_ir_representation(
    registry_key=_causalexecutionbundle_owner.registry_key,
    owner_ref=_causalexecutionbundle_owner.contract_id,
    dto_abi=_causalexecutionbundle_owner.dto_fqn,
    wire_policy_ref=_OWNER_WIRE_POLICY[0],
    wire_policy_revision=_OWNER_WIRE_POLICY[1],
    schema_name=_OWNER_SCHEMA_NAME,
    schema_version=_OWNER_SCHEMA_VERSION,
    payload_version=_OWNER_SCHEMA_VERSION,
    profile_ref=None,
    readable=True,
    writable=True,
    current=True,
    default_write=True,
)


def persist_causal_execution_bundle(
    store: ArtifactStore,
    bundle: CausalExecutionBundle,
    *,
    inputs: list[InputRef] | None = None,
    schema_name: str = "ir.causal_execution_bundle",
    schema_version: str = _CAUSAL_EXECUTION_SCHEMA_VERSION,
) -> CausalExecutionBundleRef:
    """Persist a source-validated CausalExecutionBundle under its exact owned representation."""
    selected = _put_owned_json_artifact(
        store,
        bundle.model_dump(mode="json"),
        owner=_causalexecutionbundle_owner,
        schema_name=schema_name,
        schema_version=schema_version,
        inputs=inputs,
        canon_spec=CanonSpec(forbid_floats=False),
    )
    return CausalExecutionBundleRef.model_validate(selected)


def load_causal_execution_bundle(
    store: ArtifactStore, ref: CausalExecutionBundleRef
) -> CausalExecutionBundle:
    """Read CausalExecutionBundle only after its trusted owner admits the stored representation."""
    return _get_owned_json_artifact(store, ref, owner=_causalexecutionbundle_owner)


__all__ = [
    "BoundsEstimationEntry",
    "BoundsEstimationTask",
    "CausalExecutionBundle",
    "TemporalDTRExecutionEntry",
    "TemporalDTRTask",
    "load_causal_execution_bundle",
    "persist_causal_execution_bundle",
]
