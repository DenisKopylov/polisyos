"""Public compute runner module API."""

from __future__ import annotations

import functools
import os
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol

import numpy as np
from pydantic import BaseModel

from polisyos.common import async_tools as common_async_tools
from polisyos.common.logger import get_logger
from polisyos.common.serialization import to_python_data
from polisyos.core.artifacts import (
    CoreJSONArtifactBoundedInputManifestReader,
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStore,
    ensure_ir_artifact_store,
    matches_runtime_protocol,
    read_core_input_manifest_profile_bounded,
    read_core_manifest_profile_bounded,
)
from polisyos.core.artifacts.backends.config import (
    ArtifactStoreConfig,
    build_artifact_store,
    with_ambient_ownership_enforcement_if_supported,
)
from polisyos.core.artifacts.ids import ArtifactID
from polisyos.core.artifacts.manifest import (
    ArtifactGovernanceInfo,
    ArtifactRef,
    ArtifactTenantContextInfo,
    InputRef,
    SchemaInfo,
    input_ref_from_artifact_ref,
)
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec
from polisyos.core.components import ENTRY_POINT_GROUP_FOUNDRY_METHODS
from polisyos.core.components.bootstrap import build_components_index
from polisyos.core.contracts.foundry import (
    MethodExecutionBundle,
    MethodMetricBindingSet,
)
from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorDispatchContext
from polisyos.foundry.methods import (
    MethodSignature,
    bootstrap_method_registry_from_components,
)
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.exceptions import MethodNotFoundError
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir import ArtifactID as IRArtifactID
from polisyos.ir.analytics import PosteriorPointRole, PosteriorSummaryRef
from polisyos.ir.governance.validation import ValidationIssue
from polisyos.ir.observation.bundles import (
    OBSERVATION_METHOD_INPUT_SCHEMA_NAME,
    OBSERVATION_METHOD_INPUT_SCHEMA_VERSION,
    ContractCompatibilityTarget,
)
from polisyos.scientist.compute.job_spec import (
    JobKey,
    JobResult,
    JobSpec,
    MethodExecutionCaptureProvenance,
)
from polisyos.scientist.orchestration.engine.error_semantics import emit_degraded_path

try:  # pragma: no cover - optional dependency for local/dev environments
    import jax as _jax
    import jax.numpy as _jnp
except ModuleNotFoundError:  # pragma: no cover
    jax: Any | None = None
    jnp: Any = np
else:  # pragma: no cover - exercised only when jax extra is installed
    jax = _jax
    jnp = _jnp

logger = get_logger(__name__)
_METHOD_REGISTRY_BOOTSTRAP_LOCK = threading.RLock()
_RUNNER_DEGRADED_ERRORS = (
    ArithmeticError,
    AttributeError,
    ImportError,
    ModuleNotFoundError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


class _MethodExecutionArtifactStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedInputManifestReader,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Store surface for method admission, bounded reads, and selected output writes."""


class _BoundedJobResultLineageStore(
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    Protocol,
):
    """Store surface for owner-measured selected-manifest lineage reads."""


SIMULATION_RESULTS_MANIFEST_MAX_BYTES = 256 * 1024


if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from polisyos.core.artifacts.protocol import ArtifactStore
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorRef,
        OwnedHTERequestContextV1,
    )
    from polisyos.core.contracts.runtime import (
        DirectMethodExecutionHTESummary,
        MethodExecutionCandidateOutcome,
        ObservationalInputResourcePolicy,
    )
    from polisyos.foundry.data_plane.bindings import (
        HTEInputLimits,
        HTEInputPreparationRefusal,
        PreparedHTEObservationalInput,
    )
    from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
        MethodMetricProjectionRefOutcome,
        MethodMetricProjectionWorkLike,
        _MethodMetricProjectionArtifactStore,
    )


def _build_store(cas_root: Path) -> ArtifactStore:
    store = build_artifact_store(ArtifactStoreConfig(backend="filesystem", root=str(cas_root)))
    return with_ambient_ownership_enforcement_if_supported(store)


def _require_filesystem_store(store: ArtifactStore, *, operation: str) -> FileSystemCAS:
    if isinstance(store, FileSystemCAS):
        return store
    raise TypeError(f"{operation} requires a filesystem-backed artifact store")


def _default_method_registry() -> MethodRegistry:
    return MethodRegistry.get_instance()


def _default_method_dispatcher() -> MethodDispatcher:
    return MethodDispatcher.get_instance()


@dataclass
class ExecutionResult:
    """Execution result data model."""

    exec_artifacts: Any
    applied: Any
    final_state: Any


@dataclass(frozen=True)
class MethodExecutionArtifacts:
    """Method execution artifacts public type."""

    result_ref: ArtifactRef
    evidence_ref: ArtifactRef
    posterior_summary_refs: dict[PosteriorPointRole, PosteriorSummaryRef] = field(
        default_factory=dict
    )


@dataclass(frozen=True)
class MethodRuntimeProviders:
    """Injected runtime providers for method execution orchestration."""

    registry_provider: Callable[[], MethodRegistry]
    dispatcher_provider: Callable[[], MethodDispatcher]


def _has_exact_dict_keys(values: object, expected_keys: tuple[str, ...]) -> bool:
    """Check exact model state after bounding the number of keys inspected."""
    if type(values) is not dict:
        return False
    if len(values) != len(expected_keys):
        return False
    return all(type(key) is str and key in expected_keys for key in tuple(values))


@dataclass(frozen=True, slots=True)
class _ArtifactRefView:
    """Immutable scalar snapshot of one fully selected CAS manifest view."""

    artifact_id: str
    kind: str
    media_type: str
    manifest_profile_sha256: str

    @classmethod
    def capture(cls, ref: ArtifactRef | PosteriorSummaryRef) -> _ArtifactRefView:
        if type(ref) not in {ArtifactRef, PosteriorSummaryRef}:
            raise ValueError("method_execution_requires_canonical_artifact_ref_types")
        ref_values = ref.__dict__
        expected_ref_fields = (
            "artifact_id",
            "kind",
            "media_type",
            "manifest_profile_sha256",
        )
        if (
            not _has_exact_dict_keys(type(ref).model_fields, expected_ref_fields)
            or not _has_exact_dict_keys(ref_values, expected_ref_fields)
            or ref.__pydantic_extra__ is not None
            or ref.__pydantic_private__ is not None
        ):
            raise ValueError("method_execution_requires_full_profile_artifact_refs")

        raw_artifact_id = ref_values.get("artifact_id")
        if type(ref) is ArtifactRef:
            if type(raw_artifact_id) is not ArtifactID:
                raise ValueError("method_execution_requires_full_profile_artifact_refs")
            artifact_id: ArtifactID | IRArtifactID = raw_artifact_id
        else:
            if type(raw_artifact_id) is not IRArtifactID:
                raise ValueError("method_execution_requires_full_profile_artifact_refs")
            artifact_id = raw_artifact_id

        artifact_id_values = artifact_id.__dict__
        if (
            not _has_exact_dict_keys(type(artifact_id).model_fields, ("root",))
            or not _has_exact_dict_keys(artifact_id_values, ("root",))
            or artifact_id.__pydantic_extra__ is not None
            or artifact_id.__pydantic_private__ is not None
        ):
            raise ValueError("method_execution_requires_full_profile_artifact_refs")
        raw_artifact_id_root = artifact_id_values.get("root")
        if (
            type(raw_artifact_id_root) is not str
            or len(raw_artifact_id_root) > len(artifact_id.prefix) + 64
        ):
            raise ValueError("method_execution_requires_full_profile_artifact_refs")
        if type(artifact_id) is ArtifactID:
            validated_artifact_id = ArtifactID.model_validate(
                raw_artifact_id_root,
                strict=True,
            )
        else:
            validated_artifact_id = IRArtifactID.model_validate(
                raw_artifact_id_root,
                strict=True,
            )

        kind = ref_values.get("kind")
        media_type = ref_values.get("media_type")
        manifest_profile_sha256 = ref_values.get("manifest_profile_sha256")
        if (
            type(kind) is not str
            or not kind
            or len(kind) > 255
            or type(media_type) is not str
            or not media_type
            or len(media_type) > 255
            or type(manifest_profile_sha256) is not str
            or len(manifest_profile_sha256) > 71
        ):
            raise ValueError("method_execution_requires_full_profile_artifact_refs")

        identity = {
            "artifact_id": validated_artifact_id,
            "kind": kind,
            "media_type": media_type,
            "manifest_profile_sha256": manifest_profile_sha256,
        }
        if type(ref) is ArtifactRef:
            validated_ref: ArtifactRef | PosteriorSummaryRef = ArtifactRef.model_validate(
                identity,
                strict=True,
            )
            validated_ref = ArtifactRef.model_validate_json(
                validated_ref.model_dump_json(),
                strict=True,
            )
        else:
            validated_ref = PosteriorSummaryRef.model_validate(identity, strict=True)
            validated_ref = PosteriorSummaryRef.model_validate_json(
                validated_ref.model_dump_json(),
                strict=True,
            )
        if (
            validated_ref.artifact_id.root != validated_artifact_id.root
            or validated_ref.kind != kind
            or validated_ref.media_type != media_type
            or validated_ref.manifest_profile_sha256 != manifest_profile_sha256
        ):
            raise ValueError("method_execution_requires_full_profile_artifact_refs")
        return cls(
            artifact_id=validated_artifact_id.root,
            kind=kind,
            media_type=media_type,
            manifest_profile_sha256=manifest_profile_sha256,
        )

    def materialize(self) -> ArtifactRef:
        """Rebuild a fresh, complete public ref without sharing mutable models."""
        return ArtifactRef(
            artifact_id=ArtifactID(self.artifact_id),
            kind=self.kind,
            media_type=self.media_type,
            manifest_profile_sha256=self.manifest_profile_sha256,
        )

    def materialize_posterior_summary(self) -> PosteriorSummaryRef:
        """Rebuild a posterior summary ref without sharing its mutable model."""
        if self.kind != "ir.posterior_summary":
            raise ValueError("method_execution_posterior_ref_kind_invalid")
        return PosteriorSummaryRef.model_validate_json(
            self.materialize().model_dump_json(),
            strict=True,
        )


@dataclass(frozen=True, slots=True, init=False)
class MethodExecutionWork:
    """Reference-only descriptor for one leased observational Method execution.

    The descriptor snapshots both complete selected manifest views into immutable
    scalars. It cannot retain a decoded input, method params, callback, store, or
    result object while waiting in the process-wide FIFO.
    """

    job_id: str
    run_id: str
    attempt: int
    _requested_source: _ArtifactRefView
    _observational_run_intent: _ArtifactRefView

    def __init__(
        self,
        *,
        job_id: str,
        run_id: str,
        attempt: int,
        requested_source_ref: ArtifactRef,
        observational_run_intent_ref: ArtifactRef,
    ) -> None:
        if type(job_id) is not str or not job_id or len(job_id) > 256:
            raise ValueError("method_execution_job_id_invalid")
        if type(run_id) is not str or not run_id or len(run_id) > 256:
            raise ValueError("method_execution_run_id_invalid")
        if type(attempt) is not int or attempt < 1:
            raise ValueError("method_execution_attempt_must_be_positive")
        if (
            type(requested_source_ref) is not ArtifactRef
            or type(observational_run_intent_ref) is not ArtifactRef
        ):
            raise ValueError("method_execution_work_requires_canonical_artifact_refs")
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "attempt", attempt)
        object.__setattr__(
            self, "_requested_source", _ArtifactRefView.capture(requested_source_ref)
        )
        object.__setattr__(
            self,
            "_observational_run_intent",
            _ArtifactRefView.capture(observational_run_intent_ref),
        )

    @property
    def requested_source_ref(self) -> ArtifactRef:
        """Return a fresh full-profile view of the requested source."""
        return self._requested_source.materialize()

    @property
    def observational_run_intent_ref(self) -> ArtifactRef:
        """Return a fresh full-profile view of the immutable submitted intent."""
        return self._observational_run_intent.materialize()


@dataclass(frozen=True, slots=True, init=False)
class MethodMetricProjectionWork:
    """Reference-only descriptor for one graph metric admission attempt."""

    job_id: str
    run_id: str
    attempt: int
    _method_result: _ArtifactRefView | None
    _simulation_result: _ArtifactRefView
    _method_execution_bundle: _ArtifactRefView
    _method_metric_binding_set: _ArtifactRefView

    def __init__(
        self,
        *,
        job_id: str,
        run_id: str,
        attempt: int,
        simulation_result_ref: ArtifactRef,
        method_execution_bundle_ref: ArtifactRef,
        method_metric_binding_set_ref: ArtifactRef,
        method_result_ref: ArtifactRef | None = None,
    ) -> None:
        if type(job_id) is not str or not job_id or len(job_id) > 256:
            raise ValueError("method_metric_work_job_id_invalid")
        if type(run_id) is not str or not run_id or len(run_id) > 256:
            raise ValueError("method_metric_work_run_id_invalid")
        if type(attempt) is not int or attempt < 1:
            raise ValueError("method_metric_work_attempt_must_be_positive")
        refs = (
            simulation_result_ref,
            method_execution_bundle_ref,
            method_metric_binding_set_ref,
        )
        if any(type(ref) is not ArtifactRef for ref in refs):
            raise ValueError("method_metric_work_requires_canonical_graph_refs")
        if method_result_ref is not None and type(method_result_ref) is not ArtifactRef:
            raise ValueError("method_metric_work_method_result_ref_invalid")
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "attempt", attempt)
        object.__setattr__(
            self,
            "_method_result",
            None if method_result_ref is None else _ArtifactRefView.capture(method_result_ref),
        )
        object.__setattr__(
            self,
            "_simulation_result",
            _ArtifactRefView.capture(simulation_result_ref),
        )
        object.__setattr__(
            self,
            "_method_execution_bundle",
            _ArtifactRefView.capture(method_execution_bundle_ref),
        )
        object.__setattr__(
            self,
            "_method_metric_binding_set",
            _ArtifactRefView.capture(method_metric_binding_set_ref),
        )

    @property
    def method_result_ref(self) -> ArtifactRef | None:
        """Return the optional exact method result graph selection."""
        return None if self._method_result is None else self._method_result.materialize()

    @property
    def simulation_result_ref(self) -> ArtifactRef:
        """Return the exact selected SimulationResult view."""
        return self._simulation_result.materialize()

    @property
    def method_execution_bundle_ref(self) -> ArtifactRef:
        """Return the exact selected method execution bundle view."""
        return self._method_execution_bundle.materialize()

    @property
    def method_metric_binding_set_ref(self) -> ArtifactRef:
        """Return the exact selected compiled metric binding set view."""
        return self._method_metric_binding_set.materialize()


@dataclass(frozen=True, slots=True, init=False)
class MethodExecutionPosteriorSummaryRef:
    """Bind one supported posterior point role to its persisted full ref."""

    point_role: PosteriorPointRole
    _ref: _ArtifactRefView

    def __init__(self, point_role: PosteriorPointRole, ref: PosteriorSummaryRef) -> None:
        if type(point_role) is not PosteriorPointRole:
            raise ValueError("method_execution_posterior_point_role_invalid")
        if type(ref) is not PosteriorSummaryRef:
            raise ValueError("method_execution_posterior_ref_type_invalid")
        object.__setattr__(self, "point_role", point_role)
        object.__setattr__(self, "_ref", _ArtifactRefView.capture(ref))

    @property
    def ref(self) -> PosteriorSummaryRef:
        """Return a fresh posterior ref reconstructed from immutable scalars."""
        return self._ref.materialize_posterior_summary()


@dataclass(frozen=True, slots=True)
class MethodExecutionInputRefusalOutcome:
    """Carry one owner-written input-refusal anchor through the shared worker slot."""

    job_id: str
    run_id: str
    attempt: int
    anchor_ref: OwnedAttemptAnchorRef
    refusal_code: str
    failure_stage: str | None

    def __post_init__(self) -> None:
        """Keep the executor result bounded and distinguish it from completed work."""
        from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef

        if (
            type(self.job_id) is not str
            or not self.job_id
            or len(self.job_id) > 128
            or type(self.run_id) is not str
            or not self.run_id
            or len(self.run_id) > 128
            or type(self.attempt) is not int
            or self.attempt < 1
            or type(self.anchor_ref) is not OwnedAttemptAnchorRef
            or type(self.refusal_code) is not str
            or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", self.refusal_code)
            or (
                self.failure_stage is not None
                and (
                    type(self.failure_stage) is not str
                    or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", self.failure_stage)
                )
            )
        ):
            raise ValueError("method_execution_input_refusal_outcome_invalid")


@dataclass(frozen=True, slots=True)
class _RuntimeHTEFinalizedArtifactRefs:
    """Carry the complete HTE ref set after strict projection into Core refs."""

    owned_attempt_anchor_ref: OwnedAttemptAnchorRef
    materialization_binding_ref: ArtifactRef
    hte_outcome_ref: ArtifactRef
    point_result_ref: ArtifactRef | None
    hte_result_ref: ArtifactRef | None
    inference_basis_ref: ArtifactRef | None
    refusal_diagnostic_ref: ArtifactRef | None
    invocation_basis_ref: ArtifactRef | None


def _project_hte_ref_to_core[RuntimeHTECoreRef: BaseModel](
    source_ref: BaseModel,
    source_ref_type: type[BaseModel],
    target_ref_type: type[RuntimeHTECoreRef],
    field_name: str,
    *,
    allow_source_subclass: bool = False,
) -> RuntimeHTECoreRef:
    """Project one role-typed HTE ref through the strict persisted JSON ABI."""
    if allow_source_subclass:
        source_type_matches = isinstance(source_ref, source_ref_type)
    else:
        source_type_matches = type(source_ref) is source_ref_type
    if not source_type_matches:
        raise TypeError(f"method_execution_hte_{field_name}_type_invalid")

    source_payload: dict[str, object] = source_ref.model_dump(mode="json")
    if type(source_payload) is not dict or not all(type(key) is str for key in source_payload):
        raise TypeError(f"method_execution_hte_{field_name}_payload_invalid")
    source_projection = source_ref_type.model_validate(source_payload, strict=True)
    if (
        type(source_projection) is not source_ref_type
        or source_projection.model_dump(mode="json") != source_payload
    ):
        raise ValueError(f"method_execution_hte_{field_name}_source_roundtrip_invalid")

    core_ref = target_ref_type.model_validate(source_payload, strict=True)
    if type(core_ref) is not target_ref_type or core_ref.model_dump(mode="json") != source_payload:
        raise ValueError(f"method_execution_hte_{field_name}_core_roundtrip_invalid")
    return core_ref


def _normalize_hte_finalized_artifact_refs(
    refs: object,
) -> _RuntimeHTEFinalizedArtifactRefs:
    """Strictly project every bridge-owned HTE ref through the JSON boundary.

    Core and IR own distinct reference models. The bridge output is already
    role-typed and its serialized ref payload is the shared ABI, so revalidate
    that complete set in both owners and require exact identity round-tripping.
    This projection preserves provenance; the caller still reconciles the refs
    against Runtime's owned anchor and the bridge's independently projected
    summary before constructing the Runtime outcome.
    """
    from polisyos.core.contracts.owned_attempt_anchor import (
        OwnedAttemptAnchorRef as CoreOwnedAttemptAnchorRef,
    )
    from polisyos.ir.analytics import (
        OwnedAttemptAnchorRef as IROwnedAttemptAnchorRef,
    )
    from polisyos.ir.analytics.hte import (
        ATEInferenceBasisRef,
        HTEFinalizedArtifactRefs,
        HTEOutcomeRef,
        HTEPhysicalSourceMaterializationBindingRef,
        HTEPointResultRef,
        HTERefusalDiagnosticRef,
        HTEResultEvidenceRef,
    )
    from polisyos.ir.registry import ArtifactRefModel

    if not isinstance(refs, HTEFinalizedArtifactRefs) or type(refs) is not HTEFinalizedArtifactRefs:
        raise TypeError("method_execution_hte_finalized_refs_type_invalid")

    expected_fields = frozenset(
        {
            "owned_attempt_anchor_ref",
            "materialization_binding_ref",
            "hte_outcome_ref",
            "point_result_ref",
            "hte_result_ref",
            "inference_basis_ref",
            "refusal_diagnostic_ref",
            "invocation_basis_ref",
        }
    )
    if set(HTEFinalizedArtifactRefs.model_fields) != expected_fields:
        raise ValueError("method_execution_hte_finalized_ref_contract_changed")

    payload: dict[str, object] = refs.model_dump(mode="json")
    if type(payload) is not dict or set(payload) != expected_fields:
        raise ValueError("method_execution_hte_finalized_ref_payload_invalid")
    validated_refs = HTEFinalizedArtifactRefs.model_validate(payload, strict=True)
    if (
        type(validated_refs) is not HTEFinalizedArtifactRefs
        or validated_refs.model_dump(mode="json") != payload
    ):
        raise ValueError("method_execution_hte_finalized_ref_bundle_roundtrip_invalid")

    owned_attempt_anchor_ref = _project_hte_ref_to_core(
        validated_refs.owned_attempt_anchor_ref,
        IROwnedAttemptAnchorRef,
        CoreOwnedAttemptAnchorRef,
        "owned_attempt_anchor_ref",
    )
    materialization_binding_ref = _project_hte_ref_to_core(
        validated_refs.materialization_binding_ref,
        HTEPhysicalSourceMaterializationBindingRef,
        ArtifactRef,
        "materialization_binding_ref",
    )
    hte_outcome_ref = _project_hte_ref_to_core(
        validated_refs.hte_outcome_ref,
        HTEOutcomeRef,
        ArtifactRef,
        "hte_outcome_ref",
    )
    point_result_ref = (
        _project_hte_ref_to_core(
            validated_refs.point_result_ref,
            HTEPointResultRef,
            ArtifactRef,
            "point_result_ref",
        )
        if validated_refs.point_result_ref is not None
        else None
    )
    hte_result_ref = (
        _project_hte_ref_to_core(
            validated_refs.hte_result_ref,
            HTEResultEvidenceRef,
            ArtifactRef,
            "hte_result_ref",
        )
        if validated_refs.hte_result_ref is not None
        else None
    )
    inference_basis_ref = (
        _project_hte_ref_to_core(
            validated_refs.inference_basis_ref,
            ATEInferenceBasisRef,
            ArtifactRef,
            "inference_basis_ref",
        )
        if validated_refs.inference_basis_ref is not None
        else None
    )
    refusal_diagnostic_ref = (
        _project_hte_ref_to_core(
            validated_refs.refusal_diagnostic_ref,
            HTERefusalDiagnosticRef,
            ArtifactRef,
            "refusal_diagnostic_ref",
        )
        if validated_refs.refusal_diagnostic_ref is not None
        else None
    )
    invocation_basis_ref = (
        _project_hte_ref_to_core(
            validated_refs.invocation_basis_ref,
            ArtifactRefModel,
            ArtifactRef,
            "invocation_basis_ref",
            allow_source_subclass=True,
        )
        if validated_refs.invocation_basis_ref is not None
        else None
    )

    return _RuntimeHTEFinalizedArtifactRefs(
        owned_attempt_anchor_ref=owned_attempt_anchor_ref,
        materialization_binding_ref=materialization_binding_ref,
        hte_outcome_ref=hte_outcome_ref,
        point_result_ref=point_result_ref,
        hte_result_ref=hte_result_ref,
        inference_basis_ref=inference_basis_ref,
        refusal_diagnostic_ref=refusal_diagnostic_ref,
        invocation_basis_ref=invocation_basis_ref,
    )


@dataclass(frozen=True, slots=True, init=False)
class MethodExecutionRefOutcome:
    """Bounded worker result containing only selected CAS refs and scalars."""

    job_id: str
    run_id: str
    attempt: int
    _requested_source: _ArtifactRefView
    _observational_run_intent: _ArtifactRefView
    _content_admitted_intent: _ArtifactRefView
    _submitted_input: _ArtifactRefView
    _effective_input: _ArtifactRefView
    _method_result: _ArtifactRefView
    _method_evidence: _ArtifactRefView
    _resource_policy: _ArtifactRefView
    method_fqn: str
    method_version: str
    method_abi_digest: str
    method_build_digest: str
    method_build_digest_scope: Literal["class_source_only"]
    resource_policy_digest: str
    source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"]
    normalization: Literal[
        "canonical_passthrough",
        "legacy_to_method_input_envelope_v1",
    ]
    limitations: tuple[str, ...]
    method_dispatch_binding_status: Literal["recomputed", "not_established"]
    candidate_outcome: MethodExecutionCandidateOutcome | None
    owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None
    hte_outcome_ref: ArtifactRef | None
    point_result_ref: ArtifactRef | None
    hte_result_ref: ArtifactRef | None
    inference_basis_ref: ArtifactRef | None
    refusal_diagnostic_ref: ArtifactRef | None
    invocation_basis_ref: ArtifactRef | None
    hte_summary: DirectMethodExecutionHTESummary | None
    posterior_summary_refs: tuple[MethodExecutionPosteriorSummaryRef, ...] = ()

    def __init__(
        self,
        *,
        job_id: str,
        run_id: str,
        attempt: int,
        requested_source_ref: ArtifactRef,
        observational_run_intent_ref: ArtifactRef,
        content_admitted_intent_ref: ArtifactRef,
        submitted_input_ref: ArtifactRef,
        effective_input_ref: ArtifactRef,
        method_result_ref: ArtifactRef,
        method_evidence_ref: ArtifactRef,
        resource_policy_ref: ArtifactRef,
        method_fqn: str,
        method_version: str,
        method_abi_digest: str,
        method_build_digest: str,
        method_build_digest_scope: Literal["class_source_only"],
        resource_policy_digest: str,
        source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"],
        normalization: Literal[
            "canonical_passthrough",
            "legacy_to_method_input_envelope_v1",
        ],
        limitations: tuple[str, ...],
        method_dispatch_binding_status: Literal["recomputed", "not_established"],
        candidate_outcome: MethodExecutionCandidateOutcome | None,
        posterior_summary_refs: tuple[MethodExecutionPosteriorSummaryRef, ...] = (),
        owned_attempt_anchor_ref: OwnedAttemptAnchorRef | None = None,
        hte_outcome_ref: ArtifactRef | None = None,
        point_result_ref: ArtifactRef | None = None,
        hte_result_ref: ArtifactRef | None = None,
        inference_basis_ref: ArtifactRef | None = None,
        refusal_diagnostic_ref: ArtifactRef | None = None,
        invocation_basis_ref: ArtifactRef | None = None,
        hte_summary: DirectMethodExecutionHTESummary | None = None,
    ) -> None:
        from polisyos.core.contracts.owned_attempt_anchor import OwnedAttemptAnchorRef
        from polisyos.core.contracts.runtime import (
            DirectMethodExecutionHTESummary,
            MethodExecutionCandidateOutcome,
        )

        successor = method_version == "2.0.0"
        if successor:
            if (
                candidate_outcome is not None
                or type(owned_attempt_anchor_ref) is not OwnedAttemptAnchorRef
                or type(hte_outcome_ref) is not ArtifactRef
                or type(hte_summary) is not DirectMethodExecutionHTESummary
                or hte_summary.owned_attempt_anchor_ref != owned_attempt_anchor_ref
                or hte_summary.hte_outcome_ref != hte_outcome_ref
                or hte_summary.point_result_ref != point_result_ref
                or hte_summary.hte_result_ref != hte_result_ref
                or hte_summary.inference_basis_ref != inference_basis_ref
                or hte_summary.refusal_diagnostic_ref != refusal_diagnostic_ref
                or hte_summary.method_result_ref != method_result_ref
                or hte_summary.method_evidence_ref != method_evidence_ref
            ):
                raise ValueError("method_execution_hte_outcome_summary_invalid")
            if hte_summary.kind == "interval_estimate" and (
                hte_result_ref is None
                or point_result_ref is not None
                or inference_basis_ref is None
            ):
                raise ValueError("method_execution_hte_interval_refs_incomplete")
            if hte_summary.kind == "point_estimate" and (
                point_result_ref is None or hte_result_ref is not None
            ):
                raise ValueError("method_execution_hte_point_refs_invalid")
            if hte_summary.kind == "refusal" and any(
                ref is not None for ref in (point_result_ref, hte_result_ref, inference_basis_ref)
            ):
                raise ValueError("method_execution_hte_refusal_refs_invalid")
        elif (
            type(candidate_outcome) is not MethodExecutionCandidateOutcome
            or owned_attempt_anchor_ref is not None
            or hte_outcome_ref is not None
            or point_result_ref is not None
            or hte_result_ref is not None
            or inference_basis_ref is not None
            or refusal_diagnostic_ref is not None
            or invocation_basis_ref is not None
            or hte_summary is not None
        ):
            raise ValueError("method_execution_legacy_candidate_outcome_invalid")
        for name, value in (
            ("job_id", job_id),
            ("run_id", run_id),
            ("attempt", attempt),
            ("method_fqn", method_fqn),
            ("method_version", method_version),
            ("method_abi_digest", method_abi_digest),
            ("method_build_digest", method_build_digest),
            ("method_build_digest_scope", method_build_digest_scope),
            ("resource_policy_digest", resource_policy_digest),
            ("source_protocol", source_protocol),
            ("normalization", normalization),
            ("limitations", limitations),
            ("method_dispatch_binding_status", method_dispatch_binding_status),
            ("candidate_outcome", candidate_outcome),
            ("posterior_summary_refs", posterior_summary_refs),
            ("owned_attempt_anchor_ref", owned_attempt_anchor_ref),
            ("hte_outcome_ref", hte_outcome_ref),
            ("point_result_ref", point_result_ref),
            ("hte_result_ref", hte_result_ref),
            ("inference_basis_ref", inference_basis_ref),
            ("refusal_diagnostic_ref", refusal_diagnostic_ref),
            ("invocation_basis_ref", invocation_basis_ref),
            ("hte_summary", hte_summary),
        ):
            object.__setattr__(self, name, value)
        for name, ref in (
            ("_requested_source", requested_source_ref),
            ("_observational_run_intent", observational_run_intent_ref),
            ("_content_admitted_intent", content_admitted_intent_ref),
            ("_submitted_input", submitted_input_ref),
            ("_effective_input", effective_input_ref),
            ("_method_result", method_result_ref),
            ("_method_evidence", method_evidence_ref),
            ("_resource_policy", resource_policy_ref),
        ):
            if type(ref) is not ArtifactRef:
                raise ValueError("method_execution_outcome_requires_canonical_artifact_refs")
            object.__setattr__(self, name, _ArtifactRefView.capture(ref))
        self.__post_init__()

    @property
    def requested_source_ref(self) -> ArtifactRef:
        """Return the exact full selected requested source view."""
        return self._requested_source.materialize()

    @property
    def observational_run_intent_ref(self) -> ArtifactRef:
        """Return the exact full selected submitted intent view."""
        return self._observational_run_intent.materialize()

    @property
    def content_admitted_intent_ref(self) -> ArtifactRef:
        """Return the exact full selected content-admitted intent view."""
        return self._content_admitted_intent.materialize()

    @property
    def submitted_input_ref(self) -> ArtifactRef:
        """Return the exact full selected submitted input view."""
        return self._submitted_input.materialize()

    @property
    def effective_input_ref(self) -> ArtifactRef:
        """Return the exact full selected normalized input view."""
        return self._effective_input.materialize()

    @property
    def method_result_ref(self) -> ArtifactRef:
        """Return the exact full selected method result view."""
        return self._method_result.materialize()

    @property
    def method_evidence_ref(self) -> ArtifactRef:
        """Return the exact full selected method evidence view."""
        return self._method_evidence.materialize()

    @property
    def resource_policy_ref(self) -> ArtifactRef:
        """Return the exact full selected resource-policy artifact view."""
        return self._resource_policy.materialize()

    def __post_init__(self) -> None:
        """Reject mutable or unbounded values at the long-lived handle boundary."""
        if type(self.attempt) is not int or self.attempt < 1:
            raise ValueError("method_execution_outcome_attempt_must_be_positive")
        if (
            type(self.job_id) is not str
            or not self.job_id
            or len(self.job_id) > 256
            or type(self.run_id) is not str
            or not self.run_id
            or len(self.run_id) > 256
        ):
            raise ValueError("method_execution_outcome_identity_invalid")
        if type(self.method_fqn) is not str or not self.method_fqn or len(self.method_fqn) > 256:
            raise ValueError("method_execution_outcome_fqn_invalid")
        if (
            type(self.method_version) is not str
            or not self.method_version
            or len(self.method_version) > 64
        ):
            raise ValueError("method_execution_outcome_version_invalid")
        for name, value in (
            ("method_abi_digest", self.method_abi_digest),
            ("method_build_digest", self.method_build_digest),
            ("resource_policy_digest", self.resource_policy_digest),
        ):
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"method_execution_outcome_{name}_invalid")
        resource_policy_ref = self.resource_policy_ref
        if (
            resource_policy_ref.kind != "runtime.observational_input_resource_policy"
            or resource_policy_ref.media_type != "application/json"
            or resource_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_execution_outcome_resource_policy_ref_invalid")
        if type(self.method_build_digest_scope) is not str:
            raise ValueError("method_execution_outcome_build_digest_scope_invalid")
        if self.method_build_digest_scope != "class_source_only":
            raise ValueError("method_execution_outcome_build_digest_scope_invalid")
        if type(self.source_protocol) is not str:
            raise ValueError("method_execution_outcome_protocol_invalid")
        if self.source_protocol not in {
            "method_input_envelope_v1",
            "legacy_hte_json_v1",
        }:
            raise ValueError("method_execution_outcome_protocol_invalid")
        if type(self.normalization) is not str:
            raise ValueError("method_execution_outcome_normalization_invalid")
        if self.normalization not in {
            "canonical_passthrough",
            "legacy_to_method_input_envelope_v1",
        }:
            raise ValueError("method_execution_outcome_normalization_invalid")
        if type(self.method_dispatch_binding_status) is not str:
            raise ValueError("method_execution_outcome_binding_status_invalid")
        if self.method_dispatch_binding_status not in {"recomputed", "not_established"}:
            raise ValueError("method_execution_outcome_binding_status_invalid")
        if type(self.limitations) is not tuple or len(self.limitations) > 16:
            raise ValueError("method_execution_outcome_limitations_must_be_bounded_tuple")
        if any(type(item) is not str or len(item) > 255 for item in self.limitations):
            raise ValueError("method_execution_outcome_limitation_invalid")
        if type(self.posterior_summary_refs) is not tuple or len(self.posterior_summary_refs) > 2:
            raise ValueError("method_execution_outcome_posterior_refs_must_be_bounded_tuple")
        if any(
            type(item) is not MethodExecutionPosteriorSummaryRef
            for item in self.posterior_summary_refs
        ):
            raise ValueError("method_execution_outcome_posterior_ref_invalid")


class MethodExecutionAdmission(Protocol):
    """One worker-local, current-lease admission resolved by Runtime."""

    @property
    def derived_tenant_context(self) -> ArtifactTenantContextInfo | None:
        """Return the Runtime job owner for new artifacts, not source provenance."""
        ...

    @property
    def store(self) -> _MethodExecutionArtifactStore:
        """Return the artifact store admitted for this worker lease."""
        ...

    @property
    def protocol(self) -> Literal["method_input_envelope_v1", "legacy_hte_json_v1"]:
        """Return the selected method-input protocol."""
        ...

    @property
    def method_fqn(self) -> str:
        """Return the fully qualified admitted method identity."""
        ...

    @property
    def method_version(self) -> str:
        """Return the admitted method version."""
        ...

    @property
    def effective_params(self) -> Mapping[str, Any]:
        """Return the effective parameters selected for method execution."""
        ...

    @property
    def seed(self) -> int:
        """Return the random seed selected for method execution."""
        ...

    @property
    def limits(self) -> HTEInputLimits:
        """Return the bounded method-input limits for this lease."""
        ...

    @property
    def resource_policy_ref(self) -> ArtifactRef:
        """Return the artifact reference for the admitted resource policy."""
        ...

    @property
    def resource_policy(self) -> ObservationalInputResourcePolicy:
        """Return the parsed resource policy for this method execution."""
        ...

    @property
    def resource_policy_digest(self) -> str:
        """Return the content digest bound to the resource policy."""
        ...

    @property
    def owned_hte_request_context(self) -> OwnedHTERequestContextV1 | None:
        """Return the owned HTE request context when one is admitted."""
        ...

    @property
    def method_abi_digest(self) -> str:
        """Return the admitted method ABI digest."""
        ...

    @property
    def method_build_digest(self) -> str:
        """Return the admitted method build digest."""
        ...


class MethodExecutionAdmissionService(Protocol):
    """Server-owned current-attempt resolver and content-intent writer."""

    def resolve_method_execution_admission(
        self,
        *,
        work: MethodExecutionWork,
    ) -> MethodExecutionAdmission: ...

    def verify_method_registration(
        self,
        admission: MethodExecutionAdmission,
        signature: MethodSignature,
        method_class: type,
    ) -> None: ...

    def persist_pre_output_owned_attempt_anchor(
        self,
        *,
        work: MethodExecutionWork,
        admission: MethodExecutionAdmission,
        prepared: PreparedHTEObservationalInput,
        content_admitted_intent_ref: ArtifactRef,
        method_class: type,
    ) -> OwnedAttemptAnchorDispatchContext: ...

    def persist_pre_output_hte_input_refusal_anchor(
        self,
        *,
        work: MethodExecutionWork,
        admission: MethodExecutionAdmission,
        refusal: HTEInputPreparationRefusal,
        method_class: type,
    ) -> OwnedAttemptAnchorRef: ...

    def persist_content_admitted_intent(
        self,
        *,
        work: MethodExecutionWork,
        admission: MethodExecutionAdmission,
        submitted_ref: ArtifactRef,
        effective_ref: ArtifactRef,
        contract_target: ContractCompatibilityTarget,
        method_fqn: str,
        source_protocol: Literal["method_input_envelope_v1", "legacy_hte_json_v1"],
        normalization: Literal[
            "canonical_passthrough",
            "legacy_to_method_input_envelope_v1",
        ],
        limitations: tuple[str, ...],
        source_governance: ArtifactGovernanceInfo | None,
        source_tenant_context: ArtifactTenantContextInfo | None,
        observed_manifest_bytes: int,
        observed_manifest_selection_bytes: int,
        observed_manifest_verification_bytes: int,
        observed_payload_bytes: int,
        observed_source_bytes: int,
        payload_integrity_verified: Literal[True],
        observed_bytes: int,
        observed_depth: int,
        observed_elements: int,
    ) -> ArtifactRef: ...


class MethodMetricProjectionStoreService(Protocol):
    """Resolve the server-configured store for one current graph selection."""

    def resolve_method_metric_projection_store(
        self,
        *,
        work: MethodMetricProjectionWorkLike,
    ) -> _MethodMetricProjectionArtifactStore | None: ...


def resolve_method_runtime_providers(
    *,
    providers: MethodRuntimeProviders | None = None,
    registry_provider: Callable[[], MethodRegistry] | None = None,
    dispatcher_provider: Callable[[], MethodDispatcher] | None = None,
) -> MethodRuntimeProviders:
    """Resolve the effective method runtime providers for an execution path."""

    if providers is not None and registry_provider is None and dispatcher_provider is None:
        return providers
    return MethodRuntimeProviders(
        registry_provider=(
            registry_provider
            or (providers.registry_provider if providers is not None else None)
            or _default_method_registry
        ),
        dispatcher_provider=(
            dispatcher_provider
            or (providers.dispatcher_provider if providers is not None else None)
            or _default_method_dispatcher
        ),
    )


class RunnerBackend:
    """Backend interface for executing compiled program jobs."""

    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        raise NotImplementedError


class LocalBackend(RunnerBackend):
    """Local execution using FileSystemCAS and Foundry executor."""

    def __init__(
        self,
        *,
        store_factory: Callable[[Path], ArtifactStore] | None = None,
    ) -> None:
        self._store_factory = store_factory or _build_store

    def run(
        self,
        *,
        cas_root: Path,
        program_ref: ArtifactRef,
        exec_plan_ref: ArtifactRef,
        base_state: Any,
        registry_content: Any,
        seed: int,
    ) -> ExecutionResult:
        from polisyos.foundry.execute.executor import (
            apply_state_delta_and_snapshot,
            execute_program_graph,
        )

        store = _require_filesystem_store(
            self._store_factory(cas_root),
            operation="scientist.compute.LocalBackend.run",
        )
        exec_artifacts = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=registry_content.mechanism_registry,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            selector_field_registry=registry_content.selector_field_registry,
            constraint_registry=registry_content.constraint_registry,
            step=int(base_state.step),
            seed=seed,
            capture_env=False,
        )
        final_state, applied = apply_state_delta_and_snapshot(
            store,
            base_state=base_state,
            state_delta_ref=exec_artifacts.state_delta_ref,
            slot_registry=registry_content.slot_registry,
            merge_registry=registry_content.merge_registry,
            step=int(base_state.step),
        )
        return ExecutionResult(
            exec_artifacts=exec_artifacts,
            applied=applied,
            final_state=final_state,
        )


class MethodBackend:
    """Backend for method-based jobs via foundry.methods dispatcher."""

    def __init__(
        self,
        *,
        store_factory: Callable[[Path], ArtifactStore] | None = None,
        providers: MethodRuntimeProviders | None = None,
        registry_provider: Callable[[], MethodRegistry] | None = None,
        dispatcher_provider: Callable[[], MethodDispatcher] | None = None,
        admission_service: MethodExecutionAdmissionService | None = None,
        metric_projection_service: MethodMetricProjectionStoreService | None = None,
    ) -> None:
        if admission_service is not None and providers is None and registry_provider is None:
            raise ValueError("qualified_method_execution_requires_runtime_registry_provider")
        self._store_factory = store_factory or _build_store
        self._providers = resolve_method_runtime_providers(
            providers=providers,
            registry_provider=registry_provider,
            dispatcher_provider=dispatcher_provider,
        )
        self._registry_provider = self._providers.registry_provider
        self._dispatcher_provider = self._providers.dispatcher_provider
        self._admission_service = admission_service
        self._metric_projection_service = metric_projection_service

    def submit_method_execution_work(
        self,
        work: MethodExecutionWork,
    ) -> common_async_tools.SharedExecutionHandle[
        MethodExecutionRefOutcome | MethodExecutionInputRefusalOutcome
    ]:
        """Submit one refs-only observational execution through the shared pool.

        Only immutable job identity and full source/intent refs enter the FIFO.
        When called by an existing shared worker, the fixed worker runs inline so
        it never waits for a child task while holding a physical worker slot.
        """
        if self._admission_service is None:
            raise RuntimeError("method_execution_admission_service_required")
        if type(work) is not MethodExecutionWork:
            raise TypeError("method_execution_work_must_be_typed")
        return common_async_tools.submit_shared_executor_cancellable(
            functools.partial(self._execute_method_execution_work, work)
        )

    def submit_method_metric_projection_work(
        self,
        work: MethodMetricProjectionWork,
    ) -> common_async_tools.SharedExecutionHandle[MethodMetricProjectionRefOutcome]:
        """Submit one fixed graph metric-admission operation to the shared pool."""
        if self._metric_projection_service is None:
            raise RuntimeError("method_metric_projection_service_required")
        if type(work) is not MethodMetricProjectionWork:
            raise TypeError("method_metric_projection_work_must_be_typed")
        return common_async_tools.submit_shared_executor_cancellable(
            functools.partial(self._execute_method_metric_projection_work, work)
        )

    def _execute_method_metric_projection_work(
        self,
        work: MethodMetricProjectionWork,
    ) -> MethodMetricProjectionRefOutcome:
        """Verify a fixed graph source tuple under one physical worker lease."""
        service = self._metric_projection_service
        if service is None:
            raise RuntimeError("method_metric_projection_service_required")

        from polisyos.scientist.nodes.builtins.decide.policy_runtime_method_metrics import (
            MethodMetricProjectionRefOutcome,
            prepare_method_metric_projection_work,
        )

        outcome = prepare_method_metric_projection_work(work=work, resolver=service)
        if type(outcome) is not MethodMetricProjectionRefOutcome:
            raise TypeError("method_metric_projection_worker_return_type_invalid")
        return outcome

    def _execute_method_execution_work(
        self,
        work: MethodExecutionWork,
    ) -> MethodExecutionRefOutcome | MethodExecutionInputRefusalOutcome:
        """Prepare, dispatch, and persist one admitted HTE method under one lease."""
        service = self._admission_service
        if service is None:
            raise RuntimeError("method_execution_admission_service_required")

        requested_source_ref = work.requested_source_ref
        observational_run_intent_ref = work.observational_run_intent_ref
        admission = service.resolve_method_execution_admission(
            work=work,
        )
        if (
            type(admission.method_fqn) is not str
            or not admission.method_fqn
            or type(admission.method_version) is not str
            or not admission.method_version
        ):
            raise ValueError("resolved_method_identity_required")
        if type(admission.protocol) is not str or admission.protocol not in {
            "method_input_envelope_v1",
            "legacy_hte_json_v1",
        }:
            raise ValueError("resolved_method_input_protocol_invalid")
        if (
            type(admission.resource_policy_ref) is not ArtifactRef
            or admission.resource_policy_ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_resource_policy_requires_full_profile_ref")
        resource_policy_ref = _ArtifactRefView.capture(admission.resource_policy_ref).materialize()
        for name, value in (
            ("method_abi_digest", admission.method_abi_digest),
            ("method_build_digest", admission.method_build_digest),
            ("resource_policy_digest", admission.resource_policy_digest),
        ):
            if (
                type(value) is not str
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
            ):
                raise ValueError(f"resolved_{name}_invalid")

        # Resolve only the exact version already admitted by Runtime, then check
        # its ABI and registered implementation bytes before materializing input.
        registry = self._registry_provider()
        method_class = registry.get(admission.method_fqn, version=admission.method_version)
        signature = method_class.signature
        if signature.fqn != admission.method_fqn or signature.version != admission.method_version:
            raise ValueError("resolved_method_registration_identity_changed")
        service.verify_method_registration(admission, signature, method_class)

        # Keep this import lazy: it owns selected-profile reads and HTE-specific
        # target validation; the queued descriptor carries no decoded JSON.
        from polisyos.foundry.data_plane import prepare_hte_observational_input

        try:
            prepared: PreparedHTEObservationalInput = prepare_hte_observational_input(
                store=admission.store,
                source_ref=requested_source_ref,
                protocol=admission.protocol,
                method_fqn=admission.method_fqn,
                limits=admission.limits,
                derived_tenant_context=admission.derived_tenant_context,
                materialization_binding_version=(
                    "physical_v1" if admission.resource_policy.revision == "r5" else None
                ),
            )
        except Exception as exc:
            from polisyos.foundry.data_plane import HTEInputPreparationRefusal

            if type(exc) is not HTEInputPreparationRefusal or admission.method_version != "2.0.0":
                raise
            refusal_anchor_ref = service.persist_pre_output_hte_input_refusal_anchor(
                work=work,
                admission=admission,
                refusal=exc,
                method_class=method_class,
            )
            return MethodExecutionInputRefusalOutcome(
                job_id=work.job_id,
                run_id=work.run_id,
                attempt=work.attempt,
                anchor_ref=refusal_anchor_ref,
                refusal_code=exc.code,
                failure_stage=exc.failure_stage,
            )
        if (
            prepared.method_fqn != admission.method_fqn
            or prepared.source_protocol != admission.protocol
        ):
            raise ValueError("prepared_hte_input_does_not_match_resolved_method_intent")
        if type(prepared.contract_target) is not ContractCompatibilityTarget:
            raise ValueError("prepared_hte_contract_target_invalid")
        if type(prepared.normalization) is not str or prepared.normalization not in {
            "canonical_passthrough",
            "legacy_to_method_input_envelope_v1",
        }:
            raise ValueError("prepared_hte_normalization_invalid")
        if type(prepared.limitations) is not tuple or len(prepared.limitations) > 16:
            raise ValueError("prepared_hte_limitations_must_be_bounded_tuple")
        if any(type(item) is not str or len(item) > 255 for item in prepared.limitations):
            raise ValueError("prepared_hte_limitation_invalid")

        if admission.method_version == "2.0.0" and prepared.data.outcome.shape[0] == 0:
            from polisyos.foundry.data_plane import HTEInputPreparationRefusal

            refusal = HTEInputPreparationRefusal(
                "empty_selected_input",
                observed_manifest_selection_bytes=prepared.observed_manifest_selection_bytes,
                observed_manifest_verification_bytes=prepared.observed_manifest_verification_bytes,
                observed_payload_bytes=prepared.observed_payload_bytes,
                payload_integrity_verified=prepared.payload_integrity_verified,
                source_usage_complete=type(prepared.observed_source_bytes) is int,
                failure_stage="selected_input_validation",
            )
            refusal_anchor_ref = service.persist_pre_output_hte_input_refusal_anchor(
                work=work,
                admission=admission,
                refusal=refusal,
                method_class=method_class,
            )
            return MethodExecutionInputRefusalOutcome(
                job_id=work.job_id,
                run_id=work.run_id,
                attempt=work.attempt,
                anchor_ref=refusal_anchor_ref,
                refusal_code=refusal.code,
                failure_stage=refusal.failure_stage,
            )

        if prepared.payload_integrity_verified is not True:
            raise ValueError("prepared_hte_payload_integrity_not_verified")

        submitted_input_ref = _ArtifactRefView.capture(prepared.submitted_ref).materialize()
        effective_input_ref = _ArtifactRefView.capture(prepared.effective_ref).materialize()
        content_admitted_intent_ref = _ArtifactRefView.capture(
            service.persist_content_admitted_intent(
                work=work,
                admission=admission,
                submitted_ref=submitted_input_ref,
                effective_ref=effective_input_ref,
                contract_target=prepared.contract_target,
                method_fqn=prepared.method_fqn,
                source_protocol=prepared.source_protocol,
                normalization=prepared.normalization,
                limitations=prepared.limitations,
                source_governance=prepared.source_governance,
                source_tenant_context=prepared.source_tenant_context,
                observed_manifest_bytes=prepared.observed_manifest_bytes,
                observed_manifest_selection_bytes=prepared.observed_manifest_selection_bytes,
                observed_manifest_verification_bytes=prepared.observed_manifest_verification_bytes,
                observed_payload_bytes=prepared.observed_payload_bytes,
                observed_source_bytes=prepared.observed_source_bytes,
                payload_integrity_verified=prepared.payload_integrity_verified,
                observed_bytes=prepared.observed_bytes,
                observed_depth=prepared.observed_depth,
                observed_elements=prepared.observed_elements,
            )
        ).materialize()

        runtime_context: OwnedAttemptAnchorDispatchContext | None = None
        if admission.method_version == "2.0.0":
            runtime_context = service.persist_pre_output_owned_attempt_anchor(
                work=work,
                admission=admission,
                prepared=prepared,
                content_admitted_intent_ref=content_admitted_intent_ref,
                method_class=method_class,
            )
            if type(runtime_context) is not OwnedAttemptAnchorDispatchContext:
                raise TypeError("method_execution_owned_anchor_context_invalid")

        # The parsed HTE DTO and every ndarray it owns remain in this frame until
        # dispatch, serialization, and all CAS persistence complete.
        input_state = prepared.data
        method_params = admission.effective_params
        seed = admission.seed
        dispatcher = self._dispatcher_provider()
        dispatch_binding: dict[str, Any] | None = None
        dispatch_binding_status: Literal["recomputed", "not_established"] = "not_established"

        def _dispatch_at_the_admission_point() -> Any:
            nonlocal dispatch_binding, dispatch_binding_status
            try:
                input_schema = prepared.effective_artifact_schema
                if (
                    type(input_schema) is not SchemaInfo
                    or input_schema.name != OBSERVATION_METHOD_INPUT_SCHEMA_NAME
                    or input_schema.version != OBSERVATION_METHOD_INPUT_SCHEMA_VERSION
                ):
                    raise ValueError("prepared_hte_effective_schema_invalid")
                from polisyos.scientist.methods.autotune.execution_work import (
                    MethodDispatchBinding,
                    MethodInputValueFingerprint,
                    _fingerprint_method_request_material,
                    fingerprint_method_input_value,
                )

                if input_state.confounders is None:
                    combined_covariates = input_state.covariates
                else:
                    combined_covariates = np.column_stack(
                        (input_state.covariates, input_state.confounders)
                    )
                slot_values: dict[str, Any] = {
                    "X": combined_covariates,
                    "outcome": input_state.outcome,
                    "treatment": input_state.treatment,
                }
                slot_names = signature.input_slot_names
                if "hte_data" in slot_names:
                    from polisyos.foundry.methods.catalog.causal._econml_adapter import (
                        build_hte_data,
                    )

                    slot_values["hte_data"] = build_hte_data(input_state)
                if not slot_names or not slot_names.issubset(slot_values):
                    raise ValueError("HTE input slots are not covered by typed observations")

                def _fingerprint_slot(name: str) -> MethodInputValueFingerprint:
                    value = slot_values[name]
                    if name != "hte_data":
                        return fingerprint_method_input_value(value)
                    from polisyos.core.canon import fingerprint

                    # Registered HTE methods may accept the complete typed
                    # HTEData value, not only its feature matrix. Hash every
                    # model array plus both ordered name lists under that slot.
                    slot_data = value
                    payload = {
                        "confounder_names": slot_data.confounder_names,
                        "feature_names": slot_data.feature_names,
                        "w": (
                            fingerprint_method_input_value(slot_data.w).model_dump(mode="json")
                            if slot_data.w is not None
                            else None
                        ),
                        "x": fingerprint_method_input_value(slot_data.x).model_dump(mode="json"),
                        "y": fingerprint_method_input_value(slot_data.y).model_dump(mode="json"),
                        "t": fingerprint_method_input_value(slot_data.t).model_dump(mode="json"),
                    }
                    return MethodInputValueFingerprint(
                        dtype="structured-hte-data-v1",
                        shape=[int(dimension) for dimension in slot_data.x.shape],
                        sha256=fingerprint(payload, canon_spec=CanonSpec(forbid_floats=False)),
                    )

                state_fingerprints = {name: _fingerprint_slot(name) for name in sorted(slot_names)}
                binding = MethodDispatchBinding(
                    schema_version=(
                        "1.2"
                        if not state_fingerprints
                        or any(not item.shape for item in state_fingerprints.values())
                        else "1.1"
                    ),
                    method_fqn=signature.fqn,
                    method_version=signature.version,
                    method_seed=seed,
                    method_params_fingerprint=_fingerprint_method_request_material(
                        dict(method_params)
                    ),
                    input_refs=dict.fromkeys(sorted(slot_names), effective_input_ref),
                    input_schemas=dict.fromkeys(sorted(slot_names), input_schema),
                    input_state_fingerprints=state_fingerprints,
                )
            except (OSError, TypeError, ValueError):
                dispatch_binding_status = "not_established"
            else:
                dispatch_binding = binding.model_dump(mode="json")
                dispatch_binding_status = "recomputed"
            dispatch_kwargs: dict[str, Any] = {}
            if runtime_context is not None:
                dispatch_kwargs["runtime_context"] = runtime_context
            return dispatcher.dispatch(
                method_class=method_class,
                signature=signature,
                state=input_state,
                params=method_params,
                seed=seed,
                **dispatch_kwargs,
            )

        method_result = _dispatch_at_the_admission_point()
        raw_output = method_result.output
        candidate_outcome: MethodExecutionCandidateOutcome | None = None
        writer_ready: object | None = None
        if admission.method_version == "2.0.0":
            if runtime_context is None or not isinstance(raw_output, Mapping):
                raise TypeError("direct_method_execution_hte_successor_context_missing")
            writer_ready = raw_output.get("hte_outcome_write_ready")
            if writer_ready is None:
                raise TypeError("direct_method_execution_hte_writer_ready_missing")
        else:
            from polisyos.core.contracts.runtime import MethodExecutionCandidateOutcome
            from polisyos.ir.analytics import CausalEffectReport, CausalMethod

            report = raw_output.get("report") if isinstance(raw_output, Mapping) else None
            if (
                type(report) is not CausalEffectReport
                or report.method is not CausalMethod.FOREST_DR
                or signature.fqn
                not in {
                    "causal.hte.forest_dr@1.0.0",
                    "causal.hte.forest_dr@1.1.0",
                }
            ):
                raise TypeError("direct_method_execution_requires_typed_forest_dr_report")
            candidate_outcome = MethodExecutionCandidateOutcome(
                status=report.status.value,
                estimand=report.estimand,
                point_estimate=report.point_estimate,
                confidence_interval=report.confidence_interval,
                confidence_level=report.confidence_level,
                standard_error=report.standard_error,
                p_value=report.p_value,
                sample_size=report.sample_size,
                n_treated=report.n_treated,
                n_control=report.n_control,
            )
        result_payload = to_python_data(method_result.output, sort_keys=True)
        if not isinstance(result_payload, dict):
            raise TypeError("qualified_method_output_must_be_a_mapping")
        posterior_result = result_payload.get("result")
        declares_posterior_draws = (
            signature.backend.value == "bayesian"
            and isinstance(posterior_result, Mapping)
            and posterior_result.get("sampler_family") == "mcmc"
            and isinstance(posterior_result.get("draws_ref"), str)
        )
        has_posterior_draw_evidence = "posterior_draws" in method_result.artifacts
        if has_posterior_draw_evidence and signature.backend.value != "bayesian":
            raise ValueError("non-Bayesian method cannot emit native posterior draw evidence")
        if declares_posterior_draws and not has_posterior_draw_evidence:
            raise ValueError("method result declares native posterior draws without their evidence")

        def _lineage_refs() -> list[InputRef]:
            pairs: tuple[tuple[str, ArtifactRef], ...] = (
                ("requested_source", requested_source_ref),
                ("observational_run_intent", observational_run_intent_ref),
                ("content_admitted_intent", content_admitted_intent_ref),
                ("submitted_method_input", submitted_input_ref),
                ("effective_method_input", effective_input_ref),
                ("method_resource_policy", resource_policy_ref),
            )
            if runtime_context is not None:
                materialization_binding_ref = (
                    runtime_context.input_capture.materialization_binding_ref
                )
                if materialization_binding_ref is not None:
                    pairs += (
                        (
                            "physical_source_materialization_binding",
                            materialization_binding_ref,
                        ),
                    )
                pairs += (("owned_attempt_anchor", runtime_context.anchor_ref),)
            return [input_ref_from_artifact_ref(ref, role=role) for role, ref in pairs]

        result_ref = _ArtifactRefView.capture(
            admission.store.put_json(
                result_payload,
                ArtifactWriteOptions(
                    kind=f"scientist.method_result.{signature.namespace}",
                    media_type="application/json",
                    schema=SchemaInfo(name="polisyos.scientist.MethodResult", version="0.1.0"),
                    inputs=_lineage_refs(),
                    governance=prepared.source_governance,
                    tenant_context=admission.derived_tenant_context,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        ).materialize()
        evidence_payload: dict[str, Any] = {
            "authority_purpose": "method_execution",
            "authoritative_for": ["execution_reproducibility"],
            "may_not_use_for": ["governance_admissibility", "method_validity"],
            "method_fqn": signature.fqn,
            "method_version": signature.version,
            "method_abi_digest": admission.method_abi_digest,
            "method_build_digest": admission.method_build_digest,
            "method_build_digest_scope": "class_source_only",
            "resource_policy_digest": admission.resource_policy_digest,
            "resource_policy_ref": resource_policy_ref.model_dump(mode="json"),
            "source_protocol": prepared.source_protocol,
            "normalization": prepared.normalization,
            "limitations": list(prepared.limitations),
            "requested_source_ref": requested_source_ref.model_dump(mode="json"),
            "observational_run_intent_ref": observational_run_intent_ref.model_dump(mode="json"),
            "content_admitted_intent_ref": content_admitted_intent_ref.model_dump(mode="json"),
            "submitted_input_ref": submitted_input_ref.model_dump(mode="json"),
            "effective_input_ref": effective_input_ref.model_dump(mode="json"),
            "backend": signature.backend.value,
            "execution_backend": getattr(signature, "execution_backend", signature.backend).value,
            "timing": _content_addressed_timing_policy(),
            "reproducibility": {
                "tier": method_result.reproducibility.determinism_tier.value,
                "seed": method_result.reproducibility.seed,
                "library_versions": dict(
                    sorted(method_result.reproducibility.library_versions.items())
                ),
                "solver_status": method_result.reproducibility.solver_status.value
                if method_result.reproducibility.solver_status
                else None,
                "solver_gap": method_result.reproducibility.solver_gap,
                "solver_iterations": method_result.reproducibility.solver_iterations,
                "fingerprint": method_result.reproducibility.fingerprint,
                "note": method_result.reproducibility.note,
            },
            "warnings": list(method_result.warnings),
            "artifacts": to_python_data(method_result.artifacts, sort_keys=True),
            "method_result_ref": result_ref.model_dump(mode="json"),
            "method_dispatch_binding_status": dispatch_binding_status,
            "candidate_outcome": (
                candidate_outcome.model_dump(mode="json") if candidate_outcome is not None else None
            ),
        }
        if runtime_context is not None:
            evidence_payload["owned_attempt_anchor_ref"] = runtime_context.anchor_ref.model_dump(
                mode="json"
            )
            if runtime_context.input_capture.materialization_binding_ref is not None:
                evidence_payload["materialization_binding_ref"] = (
                    runtime_context.input_capture.materialization_binding_ref.model_dump(
                        mode="json"
                    )
                )
        if dispatch_binding is not None:
            evidence_payload["method_dispatch_binding"] = dispatch_binding
        evidence_ref = _ArtifactRefView.capture(
            admission.store.put_json(
                evidence_payload,
                ArtifactWriteOptions(
                    kind="scientist.method_evidence",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.MethodExecutionEvidence",
                        version="0.1.0",
                    ),
                    inputs=[
                        input_ref_from_artifact_ref(result_ref, role="method_result"),
                        *_lineage_refs(),
                    ],
                    governance=prepared.source_governance,
                    tenant_context=admission.derived_tenant_context,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )
        ).materialize()

        finalized_hte = None
        finalized_hte_refs = None
        if runtime_context is not None:
            from polisyos.scientist.compute.hte_outcome_bridge import (
                persist_runtime_hte_outcome,
            )

            finalized_hte = persist_runtime_hte_outcome(
                store=admission.store,
                writer_ready=writer_ready,
                owned_attempt_anchor_context=runtime_context,
                method_result_ref=result_ref,
                method_evidence_ref=evidence_ref,
            )
            from polisyos.core.contracts.runtime import DirectMethodExecutionHTESummary

            if type(finalized_hte.summary) is not DirectMethodExecutionHTESummary:
                raise TypeError("method_execution_hte_summary_type_invalid")
            finalized_hte_refs = _normalize_hte_finalized_artifact_refs(finalized_hte.artifact_refs)
            if finalized_hte_refs.owned_attempt_anchor_ref != runtime_context.anchor_ref:
                raise ValueError("method_execution_hte_owned_attempt_anchor_mismatch")
            if (
                finalized_hte_refs.materialization_binding_ref
                != finalized_hte.summary.materialization_binding_ref
            ):
                raise ValueError("method_execution_hte_materialization_binding_mismatch")

        posterior_summary_refs: list[MethodExecutionPosteriorSummaryRef] = []
        if has_posterior_draw_evidence:
            from polisyos.foundry.calibration import (
                persist_posterior_summary_from_method_evidence,
            )

            ir_store = ensure_ir_artifact_store(admission.store)
            for point_role in (
                PosteriorPointRole.POSTERIOR_MEAN,
                PosteriorPointRole.POSTERIOR_MEDIAN,
            ):
                summary_ref = persist_posterior_summary_from_method_evidence(
                    ir_store,
                    evidence_ref,
                    point_role=point_role,
                )
                posterior_summary_refs.append(
                    MethodExecutionPosteriorSummaryRef(point_role=point_role, ref=summary_ref)
                )

        # Outcome is constructed only after persistence and contains no result T,
        # DTO, params, ndarray, exception, or execution frame.
        return MethodExecutionRefOutcome(
            job_id=work.job_id,
            run_id=work.run_id,
            attempt=work.attempt,
            requested_source_ref=requested_source_ref,
            observational_run_intent_ref=observational_run_intent_ref,
            content_admitted_intent_ref=content_admitted_intent_ref,
            submitted_input_ref=submitted_input_ref,
            effective_input_ref=effective_input_ref,
            method_result_ref=result_ref,
            method_evidence_ref=evidence_ref,
            resource_policy_ref=resource_policy_ref,
            method_fqn=signature.fqn,
            method_version=signature.version,
            method_abi_digest=admission.method_abi_digest,
            method_build_digest=admission.method_build_digest,
            method_build_digest_scope="class_source_only",
            resource_policy_digest=admission.resource_policy_digest,
            source_protocol=prepared.source_protocol,
            normalization=prepared.normalization,
            limitations=prepared.limitations,
            method_dispatch_binding_status=dispatch_binding_status,
            candidate_outcome=candidate_outcome,
            posterior_summary_refs=tuple(posterior_summary_refs),
            owned_attempt_anchor_ref=(
                finalized_hte_refs.owned_attempt_anchor_ref
                if finalized_hte_refs is not None
                else None
            ),
            hte_outcome_ref=(
                finalized_hte_refs.hte_outcome_ref if finalized_hte_refs is not None else None
            ),
            point_result_ref=(
                finalized_hte_refs.point_result_ref if finalized_hte_refs is not None else None
            ),
            hte_result_ref=(
                finalized_hte_refs.hte_result_ref if finalized_hte_refs is not None else None
            ),
            inference_basis_ref=(
                finalized_hte_refs.inference_basis_ref if finalized_hte_refs is not None else None
            ),
            refusal_diagnostic_ref=(
                finalized_hte_refs.refusal_diagnostic_ref
                if finalized_hte_refs is not None
                else None
            ),
            invocation_basis_ref=(
                finalized_hte_refs.invocation_basis_ref if finalized_hte_refs is not None else None
            ),
            hte_summary=(finalized_hte.summary if finalized_hte is not None else None),
        )

    def run(
        self,
        *,
        cas_root: Path,
        method_fqn: str,
        method_version: str | None,
        input_state: Any,
        method_params: Mapping[str, Any],
        seed: int,
        input_refs: Mapping[str, ArtifactRef] | None = None,
        capture_dispatch_binding: bool = False,
    ) -> ExecutionResult:
        """Run one Method and optionally record the observed dispatch binding."""
        store = self._store_factory(cas_root)
        registry = self._registry_provider()
        resolved_name = method_fqn
        if method_version and "@" not in method_fqn:
            resolved_name = f"{method_fqn}@{method_version}"
        try:
            method_class = registry.get(resolved_name, version=method_version)
        except MethodNotFoundError:
            with _METHOD_REGISTRY_BOOTSTRAP_LOCK:
                try:
                    method_class = registry.get(resolved_name, version=method_version)
                except MethodNotFoundError:
                    components_index, _ = build_components_index(
                        groups=[ENTRY_POINT_GROUP_FOUNDRY_METHODS],
                        include_dev_scan=False,
                    )
                    bootstrap_method_registry_from_components(
                        components_index,
                        registry,
                        resolution_policy=registry.get_default_policy(),
                    )
                    method_class = registry.get(resolved_name, version=method_version)
        signature = method_class.signature

        dispatcher = self._dispatcher_provider()
        dispatch_binding: dict[str, Any] | None = None
        dispatch_binding_status: str | None = None

        def dispatch_with_observation() -> Any:
            nonlocal dispatch_binding, dispatch_binding_status
            if capture_dispatch_binding or method_params.get("capture_execution_work") is True:
                from polisyos.scientist.methods.autotune.execution_work import (
                    MethodDispatchBinding,
                    _fingerprint_method_request_material,
                    fingerprint_method_input_value,
                )

                try:
                    if not isinstance(input_state, Mapping):
                        raise ValueError("dispatch input state is not a slot mapping")
                    input_state_fingerprints = {
                        name: fingerprint_method_input_value(value)
                        for name, value in sorted(input_state.items())
                    }
                    binding = MethodDispatchBinding(
                        schema_version=(
                            "1.2"
                            if not input_state_fingerprints
                            or any(not value.shape for value in input_state_fingerprints.values())
                            else "1.1"
                        ),
                        method_fqn=signature.fqn,
                        method_version=signature.version,
                        method_seed=seed,
                        method_params_fingerprint=_fingerprint_method_request_material(
                            dict(method_params)
                        ),
                        input_refs=dict(input_refs or {}),
                        input_schemas={
                            name: store.get_manifest(ref).artifact_schema
                            for name, ref in sorted((input_refs or {}).items())
                        },
                        input_state_fingerprints=input_state_fingerprints,
                    )
                except (OSError, TypeError, ValueError):
                    dispatch_binding_status = "not_established"
                else:
                    dispatch_binding = binding.model_dump(mode="json")
                    dispatch_binding_status = "recomputed"
            return dispatcher.dispatch(
                method_class=method_class,
                signature=signature,
                state=input_state,
                params=method_params,
                seed=seed,
            )

        method_result = common_async_tools.run_shared_executor_sync(dispatch_with_observation)

        result_payload = to_python_data(method_result.output, sort_keys=True)
        result_inputs: list[InputRef] = []
        for slot_name, ref in sorted((input_refs or {}).items(), key=lambda kv: kv[0]):
            result_inputs.append(input_ref_from_artifact_ref(ref, role=f"input:{slot_name}"))

        result_ref = store.put_json(
            result_payload,
            ArtifactWriteOptions(
                kind=f"scientist.method_result.{signature.namespace}",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodResult",
                    version="0.1.0",
                ),
                inputs=result_inputs,
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

        evidence_payload = {
            "authority_purpose": "method_execution",
            "authoritative_for": ["execution_reproducibility"],
            "may_not_use_for": ["governance_admissibility", "method_validity"],
            "method_fqn": signature.fqn,
            "backend": signature.backend.value,
            "execution_backend": getattr(signature, "execution_backend", signature.backend).value,
            "timing": _content_addressed_timing_policy(),
            "reproducibility": {
                "tier": method_result.reproducibility.determinism_tier.value,
                "seed": method_result.reproducibility.seed,
                "library_versions": dict(
                    sorted(method_result.reproducibility.library_versions.items())
                ),
                "solver_status": method_result.reproducibility.solver_status.value
                if method_result.reproducibility.solver_status
                else None,
                "solver_gap": method_result.reproducibility.solver_gap,
                "solver_iterations": method_result.reproducibility.solver_iterations,
                "fingerprint": method_result.reproducibility.fingerprint,
                "note": method_result.reproducibility.note,
            },
            "warnings": list(method_result.warnings),
            "artifacts": to_python_data(method_result.artifacts, sort_keys=True),
            "result_ref": str(result_ref.artifact_id),
            "method_result_ref": result_ref.model_dump(mode="json"),
        }
        if dispatch_binding_status is not None:
            evidence_payload["method_dispatch_binding_status"] = dispatch_binding_status
            if dispatch_binding is not None:
                evidence_payload["method_dispatch_binding"] = dispatch_binding
        evidence_ref = store.put_json(
            evidence_payload,
            ArtifactWriteOptions(
                kind="scientist.method_evidence",
                media_type="application/json",
                schema=SchemaInfo(
                    name="polisyos.scientist.MethodExecutionEvidence",
                    version="0.1.0",
                ),
                inputs=[
                    InputRef(
                        artifact_id=result_ref.artifact_id,
                        role="method_result",
                        manifest_profile_sha256=result_ref.manifest_profile_sha256,
                    )
                ],
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )

        posterior_result = (
            result_payload.get("result") if isinstance(result_payload, dict) else None
        )
        declares_posterior_draws = (
            method_class.signature.backend.value == "bayesian"
            and isinstance(posterior_result, Mapping)
            and posterior_result.get("sampler_family") == "mcmc"
            and isinstance(posterior_result.get("draws_ref"), str)
        )
        has_posterior_draw_evidence = "posterior_draws" in method_result.artifacts
        if has_posterior_draw_evidence and method_class.signature.backend.value != "bayesian":
            raise ValueError("non-Bayesian method cannot emit native posterior draw evidence")
        if declares_posterior_draws and not has_posterior_draw_evidence:
            raise ValueError("method result declares native posterior draws without their evidence")

        posterior_summary_refs: dict[PosteriorPointRole, PosteriorSummaryRef] = {}
        if has_posterior_draw_evidence:
            from polisyos.foundry.calibration import (
                persist_posterior_summary_from_method_evidence,
            )

            for point_role in (
                PosteriorPointRole.POSTERIOR_MEAN,
                PosteriorPointRole.POSTERIOR_MEDIAN,
            ):
                posterior_summary_refs[point_role] = persist_posterior_summary_from_method_evidence(
                    ensure_ir_artifact_store(store),
                    evidence_ref,
                    point_role=point_role,
                )

        return ExecutionResult(
            exec_artifacts=MethodExecutionArtifacts(
                result_ref=result_ref,
                evidence_ref=evidence_ref,
                posterior_summary_refs=posterior_summary_refs,
            ),
            applied=None,
            final_state=method_result.output,
        )


def _content_addressed_timing_policy() -> dict[str, str]:
    """Return stable timing semantics for content-addressed method evidence."""

    return {
        "policy": "runtime_timing_excluded_from_content_addressed_evidence",
        "reason": (
            "wall/cpu/compile timings are volatile runtime observations; "
            "method evidence CAS identity is restricted to semantic execution provenance"
        ),
    }


def resolve_backend(
    kind: str | None,
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> RunnerBackend:
    """Resolve backend."""
    backend_kind = (kind or os.getenv("POLISYOS_RUNNER_BACKEND") or "local").lower()
    if backend_kind != "local":
        raise ValueError(f"Unsupported runner backend '{backend_kind}'. Only 'local' is available.")
    return LocalBackend(store_factory=store_factory)


def _issue_payload(
    loc: list[Any],
    message: str,
    error_type: str,
    input_value: Any = None,
) -> dict[str, Any]:
    issue = ValidationIssue(
        loc=loc,
        message=message,
        error_type=error_type,
        input_value=input_value,
    )
    return issue.model_dump()


def _runner_degraded(
    *,
    operation: str,
    reason: str,
    exc: BaseException,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emit_degraded_path(
        component="compute.runner",
        operation=operation,
        reason=reason,
        exc=exc,
        details=details,
        log=logger,
    )


def _summarize_state(state: Any) -> dict[str, Any]:
    if state is None:
        return {}
    summary: dict[str, Any] = {}
    try:
        summary["avg_income"] = float(jnp.mean(state.agents.income))
        summary["n_agents"] = int(state.agents.income.shape[0])
    except _RUNNER_DEGRADED_ERRORS as exc:
        _runner_degraded(
            operation="summarize_state",
            reason="summary_field_unavailable",
            exc=exc,
            details={"field": "avg_income"},
        )
    try:
        summary["gov_balance"] = float(state.government_balance)
    except _RUNNER_DEGRADED_ERRORS as exc:
        _runner_degraded(
            operation="summarize_state",
            reason="summary_field_unavailable",
            exc=exc,
            details={"field": "gov_balance"},
        )
    try:
        summary["step"] = int(state.step)
    except _RUNNER_DEGRADED_ERRORS as exc:
        _runner_degraded(
            operation="summarize_state",
            reason="summary_field_unavailable",
            exc=exc,
            details={"field": "step"},
        )
    return summary


def read_job_result_method_execution_capture(
    store: ArtifactStore,
    result: JobResult,
    *,
    max_manifest_bytes: int,
) -> MethodExecutionCaptureProvenance:
    """Resolve capture availability from a JobResult's selected result manifest.

    The returned refs are execution provenance only. This reader does not admit
    a Foundry graph result, establish method validity, or make an authority claim.

    Args:
        store: Configured artifact store that owns the selected simulation result.
        result: Job result whose ``simulation_results_ref`` selects the manifest.
        max_manifest_bytes: Explicit operational bound applied to every selected
            manifest read. It bounds manifest bytes only, not payload or process RSS.

    Returns:
        MethodExecutionCaptureProvenance: Typed availability and exact full-profile refs.

    Raises:
        TypeError: If the store lacks the bounded manifest reader operations.
        ValueError: If a selected manifest, role, profile, or artifact kind is invalid.
    """
    if type(max_manifest_bytes) is not int or max_manifest_bytes < 1:
        raise ValueError("max_manifest_bytes must be a positive integer")
    selected_result_ref = result.simulation_results_ref
    if selected_result_ref is None:
        return MethodExecutionCaptureProvenance(
            availability="unavailable",
            limitations=("simulation_results_ref_absent",),
        )
    if selected_result_ref.manifest_profile_sha256 is None:
        return MethodExecutionCaptureProvenance(
            availability="unavailable",
            limitations=("simulation_results_profile_unselected",),
        )

    if not matches_runtime_protocol(store, _BoundedJobResultLineageStore):
        raise TypeError("artifact store lacks bounded selected-manifest readers")
    bounded_store = store
    result_read = read_core_manifest_profile_bounded(
        bounded_store,
        selected_result_ref,
        max_manifest_bytes=max_manifest_bytes,
    )
    resolved_result_ref = result_read.effective_ref
    if resolved_result_ref != selected_result_ref:
        raise ValueError("JobResult simulation results selection changed during manifest read")
    result_manifest = result_read.manifest
    result_schema = result_manifest.artifact_schema
    if (
        result_manifest.kind != "scientist.simulation_results"
        or result_manifest.media_type != "application/json"
        or result_schema is None
        or result_schema.name != "polisyos.scientist.SimulationResults"
        or result_schema.version != "0.1.0"
    ):
        raise ValueError("JobResult does not select the expected SimulationResults manifest")

    expected_roles: tuple[
        tuple[Literal["method_execution_bundle", "method_metric_binding_set"], str],
        ...,
    ] = (
        ("method_execution_bundle", MethodExecutionBundle.ARTIFACT_KIND),
        ("method_metric_binding_set", MethodMetricBindingSet.ARTIFACT_KIND),
    )
    resolved: dict[str, ArtifactRef] = {}
    absent: list[Literal["method_execution_bundle", "method_metric_binding_set"]] = []
    for role, expected_kind in expected_roles:
        matches = [item for item in result_manifest.inputs if item.role == role]
        if len(matches) > 1:
            raise ValueError(f"SimulationResults manifest repeats the {role!r} role")
        if not matches:
            absent.append(role)
            continue
        input_read = read_core_input_manifest_profile_bounded(
            bounded_store,
            matches[0],
            max_manifest_bytes=max_manifest_bytes,
        )
        selected_ref = input_read.effective_ref
        selected_manifest = input_read.manifest
        if (
            selected_ref.manifest_profile_sha256 != matches[0].manifest_profile_sha256
            or selected_ref.kind != expected_kind
            or selected_ref.media_type != "application/json"
            or selected_manifest.kind != expected_kind
            or selected_manifest.media_type != "application/json"
        ):
            raise ValueError(f"SimulationResults {role!r} role selects an unexpected artifact")
        if role == "method_execution_bundle":
            schema = selected_manifest.artifact_schema
            if (
                schema is None
                or schema.name != MethodExecutionBundle.ARTIFACT_SCHEMA_NAME
                or schema.version
                not in {
                    "1.0",
                    MethodExecutionBundle.ARTIFACT_SCHEMA_VERSION,
                }
            ):
                raise ValueError("method execution bundle role has an unexpected schema")
        if role == "method_metric_binding_set":
            schema = selected_manifest.artifact_schema
            if (
                schema is None
                or schema.name != MethodMetricBindingSet.ARTIFACT_SCHEMA_NAME
                or schema.version != MethodMetricBindingSet.ARTIFACT_SCHEMA_VERSION
            ):
                raise ValueError("method metric binding set role has an unexpected schema")
        resolved[role] = selected_ref

    bundle_ref = resolved.get("method_execution_bundle")
    binding_set_ref = resolved.get("method_metric_binding_set")
    ref_count = int(bundle_ref is not None) + int(binding_set_ref is not None)
    availability: Literal["available", "partial", "unavailable"] = (
        "available" if ref_count == 2 else "partial" if ref_count == 1 else "unavailable"
    )
    limitation_by_role: dict[
        Literal["method_execution_bundle", "method_metric_binding_set"],
        Literal[
            "method_execution_bundle_role_absent",
            "method_metric_binding_set_role_absent",
        ],
    ] = {
        "method_execution_bundle": "method_execution_bundle_role_absent",
        "method_metric_binding_set": "method_metric_binding_set_role_absent",
    }
    limitations: tuple[
        Literal[
            "method_execution_bundle_role_absent",
            "method_metric_binding_set_role_absent",
        ],
        ...,
    ] = tuple(limitation_by_role[role] for role in absent)
    return MethodExecutionCaptureProvenance(
        availability=availability,
        method_execution_bundle_ref=bundle_ref,
        method_metric_binding_set_ref=binding_set_ref,
        limitations=limitations,
    )


def _load_input_refs(
    cas_root: Path,
    input_refs: Mapping[str, ArtifactRef],
    *,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> Any:
    from polisyos.core.artifacts import load_core_json_artifact

    store = (store_factory or _build_store)(cas_root)
    loaded: dict[str, Any] = {}
    for slot_name, ref in input_refs.items():
        loaded[slot_name] = load_core_json_artifact(store, ref)
    return loaded


def _run_legacy_job(
    spec: JobSpec,
    *,
    job_key: JobKey,
    backend: RunnerBackend,
    registry_content: Any,
    base_state: Any,
    cas_root: Path | None,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> JobResult:
    issues: list[dict[str, Any]] = []
    if cas_root is None:
        issues.append(_issue_payload(["job_spec"], "cas_root is required", "runtime"))
    if registry_content is None:
        issues.append(_issue_payload(["job_spec"], "registry_content is required", "runtime"))
    if spec.exec_plan_ref is None:
        issues.append(
            _issue_payload(["job_spec", "exec_plan_ref"], "exec_plan_ref missing", "runtime")
        )
    if spec.program_ref is None:
        issues.append(_issue_payload(["job_spec", "program_ref"], "program_ref missing", "runtime"))

    store = (store_factory or _build_store)(cas_root) if cas_root is not None else None
    if base_state is None and store is not None and spec.state_snapshot_ref is not None:
        try:
            from polisyos.foundry.execute.executor import load_state_snapshot

            filesystem_store = _require_filesystem_store(
                store,
                operation="scientist.compute.run_job.load_state_snapshot",
            )
            base_state = load_state_snapshot(filesystem_store, snapshot_ref=spec.state_snapshot_ref)
        except _RUNNER_DEGRADED_ERRORS as exc:
            envelope = _runner_degraded(
                operation="load_state_snapshot",
                reason="artifact_load_failed",
                exc=exc,
                details={"artifact_ref": str(spec.state_snapshot_ref.artifact_id)},
            )
            issues.append(
                _issue_payload(
                    ["state_snapshot_ref"],
                    f"Failed to load snapshot: {exc}",
                    "runtime",
                    input_value=envelope,
                )
            )

    if base_state is None:
        issues.append(
            _issue_payload(["job_spec", "state_snapshot_ref"], "base_state missing", "runtime")
        )

    if issues:
        return JobResult(job_key=job_key, issues=issues, warnings=["missing inputs for execution"])

    resolved_cas_root = cas_root
    program_ref = spec.program_ref
    exec_plan_ref = spec.exec_plan_ref
    if resolved_cas_root is None:
        raise RuntimeError("cas_root must be present after validation")
    if program_ref is None or exec_plan_ref is None:
        raise RuntimeError("program_ref and exec_plan_ref must be present after validation")

    try:
        cpu_device = None
        prefer_cpu = False
        if jax is not None:
            try:
                cpu_device = jax.devices("cpu")[0]
            except _RUNNER_DEGRADED_ERRORS as exc:
                _runner_degraded(
                    operation="resolve_cpu_device",
                    reason="device_probe_failed",
                    exc=exc,
                )
                cpu_device = None
            try:
                prefer_cpu = any(device.platform == "metal" for device in jax.devices())
            except _RUNNER_DEGRADED_ERRORS as exc:
                _runner_degraded(
                    operation="detect_preferred_device",
                    reason="device_probe_failed",
                    exc=exc,
                )
                prefer_cpu = False
        if cpu_device is not None and prefer_cpu:
            jax_module = jax
            if jax_module is None:
                raise RuntimeError("jax runtime disappeared during backend execution")
            with jax_module.default_device(cpu_device):
                result = backend.run(
                    cas_root=resolved_cas_root,
                    program_ref=program_ref,
                    exec_plan_ref=exec_plan_ref,
                    base_state=base_state,
                    registry_content=registry_content,
                    seed=spec.seed,
                )
        else:
            result = backend.run(
                cas_root=resolved_cas_root,
                program_ref=program_ref,
                exec_plan_ref=exec_plan_ref,
                base_state=base_state,
                registry_content=registry_content,
                seed=spec.seed,
            )
    except _RUNNER_DEGRADED_ERRORS as exc:
        error_type = "runtime"
        loc = ["runtime"]
        if str(exc).startswith("Constraint"):
            error_type = "constraint"
            loc = ["semantic", "constraints"]
        issues.append(_issue_payload(loc, str(exc), error_type))
        return JobResult(job_key=job_key, issues=issues)

    summary_ref = None
    method_execution_bundle_ref = getattr(
        result.exec_artifacts,
        "method_execution_bundle_ref",
        None,
    )
    method_metric_binding_set_ref = getattr(
        result.exec_artifacts,
        "method_metric_binding_set_ref",
        None,
    )
    for role, capture_ref in (
        ("method_execution_bundle", method_execution_bundle_ref),
        ("method_metric_binding_set", method_metric_binding_set_ref),
    ):
        if capture_ref is not None and (
            not isinstance(capture_ref, ArtifactRef) or capture_ref.manifest_profile_sha256 is None
        ):
            raise ValueError(f"{role} must be a full selected-profile ArtifactRef")
    if store is not None and spec.program_ref is not None and spec.exec_plan_ref is not None:
        summary = _summarize_state(result.final_state)
        if summary:
            inputs = [
                input_ref_from_artifact_ref(spec.program_ref, role="program_graph"),
                input_ref_from_artifact_ref(spec.exec_plan_ref, role="exec_plan"),
            ]
            if result.exec_artifacts.state_delta_ref is not None:
                inputs.append(
                    input_ref_from_artifact_ref(
                        result.exec_artifacts.state_delta_ref,
                        role="state_delta",
                    )
                )
            if result.exec_artifacts.metrics_ref is not None:
                inputs.append(
                    input_ref_from_artifact_ref(result.exec_artifacts.metrics_ref, role="metrics")
                )
            if getattr(result.exec_artifacts, "environment_ref", None) is not None:
                inputs.append(
                    input_ref_from_artifact_ref(
                        result.exec_artifacts.environment_ref,
                        role="environment_manifest",
                    )
                )
            if getattr(result.applied, "state_snapshot_ref", None) is not None:
                inputs.append(
                    input_ref_from_artifact_ref(
                        result.applied.state_snapshot_ref,
                        role="state_snapshot",
                    )
                )
            if spec.state_snapshot_ref is not None:
                inputs.append(
                    input_ref_from_artifact_ref(
                        spec.state_snapshot_ref,
                        role="base_snapshot",
                    )
                )
            if method_execution_bundle_ref is not None:
                inputs.append(
                    input_ref_from_artifact_ref(
                        method_execution_bundle_ref,
                        role="method_execution_bundle",
                    )
                )
            if method_metric_binding_set_ref is not None:
                inputs.append(
                    input_ref_from_artifact_ref(
                        method_metric_binding_set_ref,
                        role="method_metric_binding_set",
                    )
                )
            summary_ref = store.put_json(
                summary,
                ArtifactWriteOptions(
                    kind="scientist.simulation_results",
                    media_type="application/json",
                    schema=SchemaInfo(
                        name="polisyos.scientist.SimulationResults",
                        version="0.1.0",
                    ),
                    inputs=inputs,
                ),
                canon_spec=CanonSpec(forbid_floats=False),
                return_selected_profile=True,
            )

    job_result = JobResult(
        job_key=job_key,
        state_delta_ref=result.exec_artifacts.state_delta_ref,
        metrics_ref=result.exec_artifacts.metrics_ref,
        environment_ref=getattr(result.exec_artifacts, "environment_ref", None),
        environment_fingerprint=getattr(result.exec_artifacts, "environment_fingerprint", None),
        state_snapshot_ref=result.applied.state_snapshot_ref
        if hasattr(result.applied, "state_snapshot_ref")
        else None,
        simulation_results_ref=summary_ref,
        final_state=result.final_state,
        warnings=[],
    )
    try:
        if store is None:
            raise RuntimeError("artifact store missing after validated cas_root")
        capture_provenance = read_job_result_method_execution_capture(
            store,
            job_result,
            max_manifest_bytes=SIMULATION_RESULTS_MANIFEST_MAX_BYTES,
        )
    except _RUNNER_DEGRADED_ERRORS:
        capture_provenance = MethodExecutionCaptureProvenance(
            availability="unavailable",
            limitations=("simulation_results_lineage_not_verified",),
        )
        job_result = job_result.model_copy(
            update={"warnings": ["method_execution_capture_lineage_unavailable"]}
        )
    return job_result.model_copy(update={"method_execution_capture": capture_provenance})


def _run_method_job(
    spec: JobSpec,
    *,
    job_key: JobKey,
    cas_root: Path | None,
    method_state: Any,
    backend: MethodBackend,
    adapter_warnings: list[str] | None = None,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
    capture_dispatch_binding: bool = False,
) -> JobResult:
    issues: list[dict[str, Any]] = []
    if cas_root is None:
        issues.append(_issue_payload(["job_spec"], "cas_root is required", "runtime"))
    if not spec.method_fqn:
        issues.append(_issue_payload(["job_spec", "method_fqn"], "method_fqn missing", "runtime"))
    if issues:
        return JobResult(job_key=job_key, issues=issues)

    loaded_state = method_state
    if loaded_state is None and spec.input_refs and cas_root is not None:
        try:
            loaded_state = _load_input_refs(
                cas_root,
                spec.input_refs,
                store_factory=store_factory,
            )
        except _RUNNER_DEGRADED_ERRORS as exc:
            envelope = _runner_degraded(
                operation="load_method_inputs",
                reason="artifact_load_failed",
                exc=exc,
                details={"input_slots": sorted(spec.input_refs)},
            )
            return JobResult(
                job_key=job_key,
                issues=[
                    _issue_payload(
                        ["job_spec", "input_refs"],
                        str(exc),
                        "runtime",
                        input_value=envelope,
                    )
                ],
            )
    if loaded_state is None:
        loaded_state = {}

    resolved_cas_root = cas_root
    method_fqn = spec.method_fqn
    if resolved_cas_root is None:
        raise RuntimeError("cas_root must be present after validation")
    if method_fqn is None:
        raise RuntimeError("method_fqn must be present after validation")

    try:
        result = backend.run(
            cas_root=resolved_cas_root,
            method_fqn=method_fqn,
            method_version=spec.method_version,
            input_state=loaded_state,
            method_params=spec.method_params,
            seed=spec.seed,
            input_refs=spec.input_refs,
            capture_dispatch_binding=capture_dispatch_binding,
        )
    except _RUNNER_DEGRADED_ERRORS as exc:
        return JobResult(
            job_key=job_key,
            issues=[_issue_payload(["method_runner"], str(exc), "runtime")],
        )

    artifacts = result.exec_artifacts
    warnings: list[str] = []
    warnings.extend(adapter_warnings or [])
    if (
        isinstance(result.final_state, dict)
        and "warnings" in result.final_state
        and isinstance(result.final_state["warnings"], list)
    ):
        warnings.extend(str(item) for item in result.final_state["warnings"])

    return JobResult(
        job_key=job_key,
        simulation_results_ref=artifacts.result_ref,
        method_result_ref=artifacts.result_ref,
        method_evidence_ref=artifacts.evidence_ref,
        posterior_summary_refs=artifacts.posterior_summary_refs,
        final_state=result.final_state,
        warnings=warnings,
    )


def run_job(
    spec: JobSpec,
    *,
    backend: RunnerBackend | MethodBackend | None = None,
    registry_content: Any = None,
    base_state: Any = None,
    cas_root: Path | None = None,
    method_state: Any = None,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
    method_runtime_providers: MethodRuntimeProviders | None = None,
    method_registry_provider: Callable[[], MethodRegistry] | None = None,
    method_dispatcher_provider: Callable[[], MethodDispatcher] | None = None,
    capture_dispatch_binding: bool = False,
) -> JobResult:
    """Execute a job spec through the legacy program or Method flow.

    Args:
        backend: A program RunnerBackend or method MethodBackend for the matching job kind.
        capture_dispatch_binding: Record the actual Method request and input-slot state in
            execution evidence. This call-level option is separate from scientific method
            parameters and does not change the JobSpec-derived JobKey.
    """
    job_key = JobKey.from_spec(spec)

    if spec.is_method_job:
        adapter_warnings = _materialize_method_adapter(
            spec,
            cas_root=cas_root,
            store_factory=store_factory,
        )
        method_backend = (
            backend
            if isinstance(backend, MethodBackend)
            else MethodBackend(
                store_factory=store_factory,
                providers=method_runtime_providers,
                registry_provider=method_registry_provider,
                dispatcher_provider=method_dispatcher_provider,
            )
        )
        return _run_method_job(
            spec,
            job_key=job_key,
            cas_root=cas_root,
            method_state=method_state,
            backend=method_backend,
            adapter_warnings=adapter_warnings,
            store_factory=store_factory,
            capture_dispatch_binding=capture_dispatch_binding,
        )

    if isinstance(backend, MethodBackend):
        raise TypeError("MethodBackend cannot execute a legacy-program JobSpec")

    legacy_backend = (
        backend
        if backend is not None
        else resolve_backend(
            None,
            store_factory=store_factory,
        )
    )
    return _run_legacy_job(
        spec,
        job_key=job_key,
        backend=legacy_backend,
        registry_content=registry_content,
        base_state=base_state,
        cas_root=cas_root,
        store_factory=store_factory,
    )


def _materialize_method_adapter(
    spec: JobSpec,
    *,
    cas_root: Path | None,
    store_factory: Callable[[Path], ArtifactStore] | None = None,
) -> list[str]:
    """
    Temporary bridge until all method runs execute through unified ProgramGraph.

    We persist a single-node DAG descriptor so every method run has a stable adapter
    artifact that can be traced in lineage/debug output.
    """
    if cas_root is None:
        return ["legacy_adapter_missing_cas_root"]
    try:
        store = (store_factory or _build_store)(cas_root)
        payload = {
            "adapter_version": "0.1.0",
            "job_kind": "method",
            "method_fqn": spec.method_fqn,
            "method_version": spec.method_version,
            "method_params": spec.method_params,
            "notes": [
                "legacy_method_job_mapped_to_single_node_unified_dag",
            ],
            "program_graph": {
                "nodes": [
                    {
                        "node_id": "method_node_1",
                        "node_kind": "method",
                        "method_fqn": spec.method_fqn,
                    }
                ],
                "edges": [],
            },
        }
        ref = store.put_json(
            payload,
            ArtifactWriteOptions(
                kind="scientist.unified_dag_adapter",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.scientist.UnifiedDagAdapter", version="0.1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True),
        )
        return [f"legacy_method_adapter_ref:{ref.artifact_id}"]
    except _RUNNER_DEGRADED_ERRORS as exc:
        envelope = _runner_degraded(
            operation="materialize_method_adapter",
            reason="artifact_write_failed",
            exc=exc,
            details={"method_fqn": spec.method_fqn},
        )
        return [f"legacy_method_adapter_failed:{envelope['message']}"]
