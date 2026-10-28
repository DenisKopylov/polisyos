"""Bounded readers for owner-selected AD01 method metric projections."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, SupportsIndex

from pydantic import BaseModel, ConfigDict, Field, StrictStr

from polisyos.core.artifacts import (
    ArtifactID,
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    CoreJsonArtifactBoundedRead,
    CoreJSONArtifactStore,
    CoreJsonReadBoundsRefusalError,
    CoreJsonReadLimits,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    artifact_manifest_profile_sha256,
    input_ref_from_artifact_ref,
    read_core_input_manifest_profile_bounded,
    read_core_json_artifact_bounded,
    read_core_manifest_profile_bounded,
    validate_core_model_bounded_read,
)
from polisyos.core.artifacts.manifest import (
    ArtifactManifest,
    ArtifactRef,
    InputRef,
    artifact_ref_identity_key,
)
from polisyos.core.canon import CanonSpec
from polisyos.scientist.methods.search.objective import (
    MethodMetricObservation,
    MethodMetricPredicateEvidence,
    SelectedMethodMetricArtifactRef,
    method_metric_observation_input_refs,
)
from polisyos.scientist.methods.search.objective import (
    MethodMetricSourceUnit as SearchMethodMetricSourceUnit,
)
from polisyos.scientist.orchestration.engine.context import (
    CompletedMethodMetricSelectionOwner,
    CompletedMethodMetricSource,
    CompletedOwnedMethodExecutionSelection,
    MethodExecutionSelectionOwner,
    MethodMetricProjectionAssociation,
    OwnedMethodExecutionSelection,
)
from polisyos.scientist.policy_design.objectives import PolicyEvaluationVector

if TYPE_CHECKING:
    from typing import NoReturn

    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.core.contracts.foundry import (
        ExecPlan,
        MethodExecutionBundle,
        MethodExecutionOccurrence,
        MethodExecutionReturnedSlot,
        MethodMetricBinding,
        MethodMetricSemanticContract,
        ProgramGraph,
    )
    from polisyos.ir.kernel.method_metrics import MethodMetricSourceUnit
    from polisyos.ir.kernel.units import UnitSpecType
    from polisyos.ir.trinity import TrinityBundle

MAX_POLICY_EVALUATION_VECTOR_BYTES = 8 * 1024 * 1024
MAX_METHOD_METRIC_SOURCE_BYTES = 16 * 1024 * 1024
MAX_METHOD_METRIC_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_METHOD_METRIC_TOTAL_SOURCE_BYTES = 64 * 1024 * 1024
MAX_METHOD_METRIC_READ_DEPTH = 128
MAX_METHOD_METRIC_READ_ELEMENTS = 1_000_000
MAX_METHOD_METRIC_OUTPUT_READ_DEPTH = 32
MAX_METHOD_METRIC_OUTPUT_READ_ELEMENTS = 16_384
MAX_METHOD_METRIC_MANIFEST_INPUTS = 100_000
MAX_METHOD_METRIC_VECTOR_INPUTS = 65_536
MAX_METHOD_METRIC_BINDINGS = 512
MAX_METHOD_EXECUTION_OCCURRENCES = 2048
MAX_METHOD_METRIC_OBSERVATIONS = 8192
METHOD_METRIC_PROJECTION_VERIFIER_ID = "scientist.ad01.method_metric_projection"
METHOD_METRIC_PROJECTION_VERIFIER_REVISION = "1.0"


class _MethodMetricProjectionArtifactStore(
    CoreJSONArtifactStore,
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Store surface for owner writes and selected, bounded JSON reads."""


class _MethodMetricProjectionArtifactReader(
    CoreJSONArtifactBoundedInputManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    Protocol,
):
    """Read-only Core surface for bounded completed-source projection reads."""


class MethodMetricProjectionReadResult(BaseModel):
    """Result of a cheap selected-projection read; row statuses remain per observation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["selected", "verification_missing", "invalid"]
    vector_ref: SelectedMethodMetricArtifactRef | None = None
    observations: tuple[MethodMetricObservation, ...] = Field(default_factory=tuple)
    limitations: tuple[StrictStr, ...] = Field(default_factory=tuple)


_COMPLETED_METHOD_METRIC_PROJECTION_SEAL = object()


class _EphemeralMethodMetricCapability:
    """Reject generic copying and persistence of an in-process admission capability."""

    __slots__ = ()

    def __setattr__(self, name: str, value: object) -> None:
        del name, value
        raise AttributeError("ephemeral_method_metric_capability_is_immutable")

    def __delattr__(self, name: str) -> None:
        del name
        raise AttributeError("ephemeral_method_metric_capability_is_immutable")

    def __copy__(self) -> NoReturn:
        raise TypeError("ephemeral_method_metric_capability_copy_is_forbidden")

    def __deepcopy__(self, memo: dict[int, Any]) -> NoReturn:
        del memo
        raise TypeError("ephemeral_method_metric_capability_copy_is_forbidden")

    def __reduce__(self) -> NoReturn:
        raise TypeError("ephemeral_method_metric_capability_persistence_is_forbidden")

    def __reduce_ex__(self, protocol: SupportsIndex) -> NoReturn:
        del protocol
        raise TypeError("ephemeral_method_metric_capability_persistence_is_forbidden")


class _CompletedMethodMetricProjectionBasis(_EphemeralMethodMetricCapability):
    """Read-only candidate evidence issued after Runtime owner and artifact rechecks."""

    source_run_id: str
    source_candidate_ref: _SelectedArtifactRefSnapshot
    source_experiment_state_ref: _SelectedArtifactRefSnapshot
    source_job_id: str
    source_attempt: int
    simulation_result_ref: _SelectedArtifactRefSnapshot
    method_execution_bundle_ref: _SelectedArtifactRefSnapshot
    method_metric_binding_set_ref: _SelectedArtifactRefSnapshot
    projection_vector_ref: _SelectedArtifactRefSnapshot
    observations: tuple[MethodMetricObservation, ...]
    verifier_revision: str
    verifier_implementation_sha256: str
    __slots__ = (
        "_seal",
        "method_execution_bundle_ref",
        "method_metric_binding_set_ref",
        "observations",
        "projection_vector_ref",
        "simulation_result_ref",
        "source_attempt",
        "source_candidate_ref",
        "source_experiment_state_ref",
        "source_job_id",
        "source_run_id",
        "verifier_implementation_sha256",
        "verifier_revision",
    )

    def __init__(
        self,
        *,
        source_run_id: str,
        source_candidate_ref: ArtifactRef,
        source_experiment_state_ref: ArtifactRef,
        source_job_id: str,
        source_attempt: int,
        simulation_result_ref: ArtifactRef,
        method_execution_bundle_ref: ArtifactRef,
        method_metric_binding_set_ref: ArtifactRef,
        projection_vector_ref: ArtifactRef,
        observations: tuple[MethodMetricObservation, ...],
        verifier_revision: str,
        verifier_implementation_sha256: str,
        _seal: object,
    ) -> None:
        if _seal is not _COMPLETED_METHOD_METRIC_PROJECTION_SEAL:
            raise ValueError("completed_method_metric_basis_must_be_issued_by_owner_reader")
        if type(source_run_id) is not str or not source_run_id:
            raise ValueError("completed_method_metric_basis_source_run_id_invalid")
        if type(source_job_id) is not str or not source_job_id:
            raise ValueError("completed_method_metric_basis_job_id_invalid")
        if type(source_attempt) is not int or source_attempt < 1:
            raise ValueError("completed_method_metric_basis_attempt_invalid")
        if not observations:
            raise ValueError("completed_method_metric_basis_observations_missing")
        object.__setattr__(self, "source_run_id", source_run_id)
        object.__setattr__(
            self,
            "source_candidate_ref",
            _SelectedArtifactRefSnapshot.capture(
                source_candidate_ref,
                kind="scientist.policy_design.candidate",
            ),
        )
        object.__setattr__(
            self,
            "source_experiment_state_ref",
            _SelectedArtifactRefSnapshot.capture(
                source_experiment_state_ref,
                kind="scientist.experiment_state",
            ),
        )
        object.__setattr__(self, "source_job_id", source_job_id)
        object.__setattr__(self, "source_attempt", source_attempt)
        object.__setattr__(
            self,
            "simulation_result_ref",
            _SelectedArtifactRefSnapshot.capture(
                simulation_result_ref,
                kind="foundry.simulation_result",
            ),
        )
        object.__setattr__(
            self,
            "method_execution_bundle_ref",
            _SelectedArtifactRefSnapshot.capture(
                method_execution_bundle_ref,
                kind="foundry.method_execution_bundle",
            ),
        )
        object.__setattr__(
            self,
            "method_metric_binding_set_ref",
            _SelectedArtifactRefSnapshot.capture(
                method_metric_binding_set_ref,
                kind="foundry.method_metric_binding_set",
            ),
        )
        object.__setattr__(
            self,
            "projection_vector_ref",
            _SelectedArtifactRefSnapshot.capture(
                projection_vector_ref,
                kind="scientist.policy_evaluation_vector",
            ),
        )
        object.__setattr__(self, "observations", tuple(observations))
        object.__setattr__(self, "verifier_revision", verifier_revision)
        object.__setattr__(
            self,
            "verifier_implementation_sha256",
            verifier_implementation_sha256,
        )
        object.__setattr__(self, "_seal", _seal)

    @property
    def candidate_ref(self) -> ArtifactRef:
        """Return a fresh full-profile selected candidate ref."""
        return self.source_candidate_ref.materialize()

    @property
    def source_state_ref(self) -> ArtifactRef:
        """Return a fresh full-profile terminal experiment-state ref."""
        return self.source_experiment_state_ref.materialize()

    @property
    def vector_ref(self) -> ArtifactRef:
        """Return a fresh full-profile selected projection ref."""
        return self.projection_vector_ref.materialize()

    def cache_source_identity(self) -> dict[str, object]:
        """Return only complete immutable source tuple scalars for cache partitioning."""
        return {
            "job_id": self.source_job_id,
            "run_id": self.source_run_id,
            "attempt": self.source_attempt,
            "method_result_ref": None,
            "simulation_result_ref": self.simulation_result_ref.materialize().model_dump(
                mode="json"
            ),
            "method_execution_bundle_ref": self.method_execution_bundle_ref.materialize().model_dump(
                mode="json"
            ),
            "method_metric_binding_set_ref": self.method_metric_binding_set_ref.materialize().model_dump(
                mode="json"
            ),
        }


@dataclass(frozen=True, slots=True)
class CompletedMethodMetricProjectionReadResult:
    """Result of resolving a completed source for later policy evaluation."""

    status: Literal["selected", "verification_missing", "invalid"]
    basis: _CompletedMethodMetricProjectionBasis | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.status == "selected":
            if type(self.basis) is not _CompletedMethodMetricProjectionBasis:
                raise ValueError("selected_completed_method_metrics_require_owner_basis")
            if self.basis._seal is not _COMPLETED_METHOD_METRIC_PROJECTION_SEAL:
                raise ValueError("selected_completed_method_metrics_have_invalid_seal")
            if self.limitations:
                raise ValueError("selected_completed_method_metrics_cannot_have_limitations")
        elif self.basis is not None or not self.limitations:
            raise ValueError("limited_completed_method_metrics_require_reason_only")


def read_completed_admitted_method_metric_projection(
    store: _MethodMetricProjectionArtifactReader,
    *,
    owner: CompletedMethodMetricSelectionOwner,
    source_run_id: str | None,
    candidate_ref: ArtifactRef,
    tenant_id: str | None,
    cell_id: str | None,
    request_status: Literal["absent", "requested", "invalid"] = "requested",
) -> CompletedMethodMetricProjectionReadResult:
    """Resolve source observations through Runtime's completed owner and exact candidate.

    ``source_run_id`` and ``candidate_ref`` are lookup keys only. Runtime rechecks the
    completed job, current attempt, tenant/cell creation scope, terminal finalization,
    and the candidate identity extracted from Foundry's admitted execution-input basis.
    This reader accepts no state- or request-supplied producer/vector refs.
    """
    if request_status == "absent":
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_source_not_requested",),
        )
    if request_status == "invalid":
        return CompletedMethodMetricProjectionReadResult(
            status="invalid",
            limitations=("completed_method_metric_source_run_request_invalid",),
        )
    if not isinstance(source_run_id, str) or not source_run_id.strip():
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_source_run_id_not_requested",),
        )
    if (
        not isinstance(tenant_id, str)
        or not tenant_id.strip()
        or not isinstance(cell_id, str)
        or not cell_id.strip()
    ):
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("current_method_metric_access_scope_not_established",),
        )
    try:
        requested_candidate = _selected_ref(
            candidate_ref,
            kind="scientist.policy_design.candidate",
        )
        source = owner.resolve_completed_method_metric_selection(
            source_run_id=source_run_id,
            candidate_ref=_core_artifact_ref(requested_candidate),
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_owner_lookup_unavailable",),
        )
    if source is None:
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_source_not_established",),
        )
    try:
        source_candidate = _selected_ref(
            source.source_candidate_ref,
            kind="scientist.policy_design.candidate",
        )
        source_state = _selected_ref(
            source.source_experiment_state_ref,
            kind="scientist.experiment_state",
        )
        selection = source.selection
        if selection.selection_kind != "graph_method":
            return CompletedMethodMetricProjectionReadResult(
                status="verification_missing",
                limitations=("completed_method_metric_source_is_not_graph_execution",),
            )
        if selection.metric_verification_status != "verified":
            return CompletedMethodMetricProjectionReadResult(
                status="verification_missing",
                limitations=("completed_method_metric_source_has_no_verified_projection",),
            )
        if selection.method_result_ref is not None:
            return CompletedMethodMetricProjectionReadResult(
                status="invalid",
                limitations=("completed_graph_selection_aliases_direct_method_result",),
            )
        selected_candidate = _selected_ref(
            selection.source_candidate_ref,
            kind="scientist.policy_design.candidate",
        )
        selected_state = _selected_ref(
            selection.source_experiment_state_ref,
            kind="scientist.experiment_state",
        )
    except (AttributeError, TypeError, ValueError):
        return CompletedMethodMetricProjectionReadResult(
            status="invalid",
            limitations=("completed_method_metric_source_identity_invalid",),
        )
    if (
        source.source_run_id != source_run_id
        or selection.run_id != source_run_id
        or not _same_selected_ref(source_candidate, requested_candidate)
        or not _same_selected_ref(selected_candidate, source_candidate)
        or not _same_selected_ref(selected_state, source_state)
    ):
        return CompletedMethodMetricProjectionReadResult(
            status="invalid",
            limitations=("completed_method_metric_candidate_or_state_join_mismatch",),
        )

    read_result = _read_owned_method_metric_projection(store, selection=selection)
    if read_result.status != "selected" or read_result.vector_ref is None:
        return CompletedMethodMetricProjectionReadResult(
            status=read_result.status,
            limitations=read_result.limitations
            or ("completed_method_metric_projection_not_selected",),
        )
    association = selection.method_metric_projection
    if association is None:
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_projection_association_missing",),
        )
    try:
        basis = _CompletedMethodMetricProjectionBasis(
            source_run_id=source_run_id,
            source_candidate_ref=source_candidate,
            source_experiment_state_ref=source_state,
            source_job_id=selection.job_id,
            source_attempt=selection.attempt,
            simulation_result_ref=_selected_ref(
                selection.simulation_result_ref,
                kind="foundry.simulation_result",
            ),
            method_execution_bundle_ref=_selected_ref(
                selection.method_execution_bundle_ref,
                kind="foundry.method_execution_bundle",
            ),
            method_metric_binding_set_ref=_selected_ref(
                selection.method_metric_binding_set_ref,
                kind="foundry.method_metric_binding_set",
            ),
            projection_vector_ref=read_result.vector_ref,
            observations=read_result.observations,
            verifier_revision=association.verifier_revision,
            verifier_implementation_sha256=association.verifier_implementation_sha256,
            _seal=_COMPLETED_METHOD_METRIC_PROJECTION_SEAL,
        )
    except (TypeError, ValueError):
        return CompletedMethodMetricProjectionReadResult(
            status="invalid",
            limitations=("completed_method_metric_basis_construction_failed",),
        )
    # The bounded CAS read can outlive the completed selection. Re-resolve the
    # complete owner tuple after the read; selected bytes are not a currentness
    # receipt by themselves. Runtime returns immutable typed source selections.
    try:
        current = owner.resolve_completed_method_metric_selection(
            source_run_id=source_run_id,
            candidate_ref=_core_artifact_ref(requested_candidate),
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_owner_reselection_unavailable",),
        )
    if current != source:
        return CompletedMethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("completed_method_metric_source_changed_during_read",),
        )
    return CompletedMethodMetricProjectionReadResult(status="selected", basis=basis)


def attach_completed_method_metric_observation_projection(
    evaluation: PolicyEvaluationVector,
    *,
    candidate_ref: ArtifactRef,
    basis: object,
) -> PolicyEvaluationVector:
    """Attach owner-selected observations to the matching candidate evaluation vector.

    This preserves the ObjectiveStack's independently computed channels. Metric rows
    remain candidate-only observations and do not create a score, calibration, or
    external-law conclusion.
    """
    if (
        type(basis) is not _CompletedMethodMetricProjectionBasis
        or basis._seal is not _COMPLETED_METHOD_METRIC_PROJECTION_SEAL
    ):
        raise ValueError("completed_method_metric_projection_basis_not_owner_issued")
    selected_candidate = _selected_ref(
        candidate_ref,
        kind="scientist.policy_design.candidate",
    )
    if not _same_selected_ref(selected_candidate, basis.source_candidate_ref.materialize()):
        raise _InvalidProjectionError("completed_method_metric_candidate_does_not_match_evaluation")
    if evaluation.method_metric_observations:
        raise _InvalidProjectionError("evaluation_already_contains_method_metric_observations")
    metadata = dict(evaluation.metadata)
    metadata["completed_method_metric_projection"] = {
        "source_run_id": basis.source_run_id,
        "source_candidate_ref": basis.candidate_ref.model_dump(mode="json"),
        "source_experiment_state_ref": basis.source_state_ref.model_dump(mode="json"),
        "projection_vector_ref": basis.vector_ref.model_dump(mode="json"),
        "verifier_revision": basis.verifier_revision,
        "verifier_implementation_sha256": basis.verifier_implementation_sha256,
        "authority_status": "candidate_only",
        "score_status": "not_established",
    }
    payload = evaluation.model_dump(mode="python")
    payload["method_metric_observations"] = basis.observations
    payload["metadata"] = metadata
    return PolicyEvaluationVector.model_validate(payload)


def admit_completed_method_metric_objective_score(
    basis: object | None,
    *,
    candidate_ref: ArtifactRef | None,
    request_status: Literal["absent", "requested", "invalid"],
) -> Any | None:
    """Replay the configured whole-objective score from a fresh owner basis.

    This uses the existing weighted ``composite``/``search_metric`` evaluator only
    when every configured objective has one unambiguous, observed method metric,
    all objective directions are supported, no target rule is omitted, and units
    are compatible under that evaluator. It does not turn observations into external
    calibration, causal validity, legal meaning, or publication authority.
    """
    from polisyos.scientist.methods.search.objective import (
        ObjectiveScoreAdmission,
        ObjectiveScoreStatus,
        _unestablished_score_assessment,
        reconcile_objective_score_assessment,
    )

    if request_status == "absent":
        return None
    if request_status == "invalid":
        return ObjectiveScoreAdmission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="not_established",
            reported_assessment=None,
            recomputed_assessment=None,
            reason="completed_method_metric_source_run_request_invalid",
        )
    if basis is None:
        return ObjectiveScoreAdmission(
            status=ObjectiveScoreStatus.NOT_ESTABLISHED,
            predicate_status="not_established",
            reported_assessment=_unestablished_score_assessment(
                "completed_method_metric_source_not_established"
            ),
            recomputed_assessment=None,
            reason="completed_method_metric_source_not_established",
        )
    if (
        type(basis) is not _CompletedMethodMetricProjectionBasis
        or basis._seal is not _COMPLETED_METHOD_METRIC_PROJECTION_SEAL
    ):
        return ObjectiveScoreAdmission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="not_established",
            reported_assessment=None,
            recomputed_assessment=None,
            reason="completed_method_metric_basis_not_owner_issued",
        )
    try:
        selected_candidate = _selected_ref(
            candidate_ref,
            kind="scientist.policy_design.candidate",
        )
    except (TypeError, ValueError):
        return ObjectiveScoreAdmission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="not_established",
            reported_assessment=None,
            recomputed_assessment=None,
            reason="completed_method_metric_evaluation_candidate_invalid",
        )
    if not _same_selected_ref(selected_candidate, basis.candidate_ref):
        return ObjectiveScoreAdmission(
            status=ObjectiveScoreStatus.INVALID,
            predicate_status="not_established",
            reported_assessment=None,
            recomputed_assessment=None,
            reason="completed_method_metric_evaluation_candidate_mismatch",
        )
    assessment = _completed_method_metric_objective_assessment(basis)
    return reconcile_objective_score_assessment(
        assessment,
        {},
        owner_context=basis,
    )


_FUNNEL_METHOD_METRIC_CONTEXT_PREFIX = "_funnel_method_metric_"
_FUNNEL_METHOD_METRIC_CONTEXT_KEYS = frozenset(
    {
        "_funnel_method_metric_projection_identity",
        "_funnel_method_metric_projection_basis",
        "_funnel_method_metric_score_required",
        "_funnel_method_metric_source_request_status",
    }
)


@dataclass(frozen=True, slots=True)
class _FunnelMethodMetricIntent:
    """One immutable admission snapshot of the Runtime-owned metric capsule."""

    status: Literal["legacy", "absent", "requested", "invalid"]
    projection_basis: object | None


def _funnel_method_metric_intent(context: Mapping[str, Any]) -> _FunnelMethodMetricIntent:
    """Classify the whole emitted context family before any legacy fallback."""
    family = {
        key
        for key in context
        if isinstance(key, str) and key.startswith(_FUNNEL_METHOD_METRIC_CONTEXT_PREFIX)
    }
    if not family:
        return _FunnelMethodMetricIntent(status="legacy", projection_basis=None)

    # Runtime emits one coherent four-field capsule. Any partial/lost status,
    # unrecognized family extension, or malformed member stays fail-closed.
    if family - _FUNNEL_METHOD_METRIC_CONTEXT_KEYS:
        return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)
    status_key = "_funnel_method_metric_source_request_status"
    required_key = "_funnel_method_metric_score_required"
    identity_key = "_funnel_method_metric_projection_identity"
    basis_key = "_funnel_method_metric_projection_basis"
    if (
        status_key not in family
        or required_key not in family
        or identity_key not in family
        or basis_key not in family
    ):
        return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)

    request_status = context[status_key]
    required = context[required_key]
    identity = context[identity_key]
    basis = context[basis_key]
    if (
        type(request_status) is not str
        or request_status not in {"requested", "invalid", "absent"}
        or type(required) is not bool
        or not isinstance(identity, Mapping)
        or identity.get("request_status") != request_status
    ):
        return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)

    requested_run_id = identity.get("requested_source_run_id")
    selected_source = identity.get("selected_source")
    if request_status == "absent":
        if (
            required
            or requested_run_id is not None
            or basis is not None
            or selected_source is not None
        ):
            return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)
        return _FunnelMethodMetricIntent(status="absent", projection_basis=None)

    if request_status == "requested":
        if type(requested_run_id) is not str or not requested_run_id.strip() or not required:
            return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)
        if basis is None:
            if selected_source is not None:
                return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)
        elif (
            not isinstance(selected_source, Mapping)
            or selected_source.get("run_id") != requested_run_id
            or getattr(basis, "source_run_id", None) != requested_run_id
        ):
            return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)
        return _FunnelMethodMetricIntent(status="requested", projection_basis=basis)

    return _FunnelMethodMetricIntent(status="invalid", projection_basis=None)


def admit_funnel_method_metric_objective_score(
    context: Mapping[str, Any],
) -> Any | None:
    """Resolve one coherent Runtime capsule or retain the exact legacy route."""
    intent = _funnel_method_metric_intent(context)
    if intent.status in {"legacy", "absent"}:
        return None
    candidate_ref = context.get("policy_candidate_ref")
    if intent.status == "requested":
        return admit_completed_method_metric_objective_score(
            intent.projection_basis,
            candidate_ref=candidate_ref,
            request_status="requested",
        )
    return admit_completed_method_metric_objective_score(
        intent.projection_basis,
        candidate_ref=candidate_ref,
        request_status="invalid",
    )


def recompute_completed_method_metric_score(
    assessment: Any,
    *,
    owner_context: object | None,
) -> Any | None:
    """Recompute a selected method-metric score from its exact private owner basis."""
    if (
        type(owner_context) is not _CompletedMethodMetricProjectionBasis
        or owner_context._seal is not _COMPLETED_METHOD_METRIC_PROJECTION_SEAL
    ):
        return None
    expected = _completed_method_metric_objective_assessment(owner_context)
    return expected if expected == assessment else None


def _completed_method_metric_objective_assessment(
    basis: _CompletedMethodMetricProjectionBasis,
) -> Any:
    """Build one all-objective assessment from owner-bound observations.

    Incomplete coverage, repeated bindings/occurrences, unsupported target or
    maintain-range rules stay typed limited. No first-row selection is permitted.
    """
    from decimal import Decimal, InvalidOperation

    from polisyos.scientist.methods.search.objective import (
        ObjectiveScoreStatus,
        _evaluate_configured_objective_source,
        _make_score_assessment,
    )

    observations = tuple(basis.observations)
    ordered = tuple(
        sorted(
            observations,
            key=lambda item: (
                item.objective_id,
                item.binding_id,
                item.occurrence_id or "",
                item.output_ref.artifact_id if item.output_ref is not None else "",
            ),
        )
    )
    rule: dict[str, Any] = {
        "kind": "completed_method_metric_objectives",
        "version": "1.0",
        "source": {
            "source_run_id": basis.source_run_id,
            "source_candidate_ref": basis.candidate_ref.model_dump(mode="json"),
            "source_experiment_state_ref": basis.source_state_ref.model_dump(mode="json"),
            "projection_vector_ref": basis.vector_ref.model_dump(mode="json"),
            "verifier_revision": basis.verifier_revision,
            "verifier_implementation_sha256": basis.verifier_implementation_sha256,
        },
        "configured_objective_count": max(
            (item.configured_objective_count or 0 for item in ordered),
            default=0,
        ),
        "observations": [
            {
                "objective_id": item.objective_id,
                "metric_id": item.metric_id,
                "metric_unit_id": item.metric_unit_id,
                "objective_direction": item.objective_direction,
                "objective_weight": item.objective_weight,
                "objective_target_present": item.objective_target_present,
                "objective_target_sha256": item.objective_target_sha256,
                "objective_spec_sha256": item.objective_spec_sha256,
                "configured_objective_count": item.configured_objective_count,
                "binding_id": item.binding_id,
                "occurrence_id": item.occurrence_id,
                "invocation_id": item.invocation_id,
                "output_ref": (
                    None if item.output_ref is None else item.output_ref.model_dump(mode="json")
                ),
                "input_capture_ref": (
                    None
                    if item.input_capture_ref is None
                    else item.input_capture_ref.model_dump(mode="json")
                ),
                "source_status": item.source_status,
                "value": item.value,
                "limitations": list(item.limitations),
            }
            for item in ordered
        ],
    }
    objective_count = rule["configured_objective_count"]
    source_rows = [item for item in ordered if item.source_status == "observed"]
    source_values = tuple(
        sorted(
            (item.objective_id, float(item.value)) for item in source_rows if item.value is not None
        )
    )
    source_fields = tuple(
        sorted(
            {item.objective_id for item in source_rows}
            | {f"metric_units.{item.objective_id}" for item in source_rows}
        )
    )
    unit_bindings = tuple(
        sorted(
            (item.objective_id, item.metric_unit_id) for item in source_rows if item.metric_unit_id
        )
    )

    status = ObjectiveScoreStatus.NOT_ESTABLISHED
    limitation = "configured_method_metric_objective_coverage_incomplete"
    score: float | None = None
    observed_statuses = {item.source_status for item in ordered}
    if "invalid" in observed_statuses:
        status = ObjectiveScoreStatus.INVALID
        limitation = "configured_method_metric_observation_invalid"
    elif "not_established" in observed_statuses:
        limitation = "configured_method_metric_observation_not_established"
    elif "unavailable" in observed_statuses:
        status = ObjectiveScoreStatus.UNAVAILABLE
        limitation = "configured_method_metric_observation_unavailable"
    else:
        counts: dict[str, int] = {}
        for item in ordered:
            counts[item.objective_id] = counts.get(item.objective_id, 0) + 1
        if objective_count < 1 or len(ordered) != objective_count:
            limitation = "configured_method_metric_objective_count_not_fully_covered"
        elif any(value != 1 for value in counts.values()):
            limitation = "configured_method_metric_objective_has_repeated_binding_or_occurrence"
        elif len(counts) != objective_count:
            limitation = "configured_method_metric_objective_identity_coverage_incomplete"
        elif any(
            item.configured_objective_count != objective_count
            or item.objective_spec_sha256 is None
            or item.metric_unit_id is None
            or item.value is None
            or item.objective_direction not in {"minimize", "maximize", "maintain_range"}
            or item.objective_weight is None
            or item.objective_target_present is None
            or item.objective_target_present != (item.objective_target_sha256 is not None)
            for item in ordered
        ):
            status = ObjectiveScoreStatus.INVALID
            limitation = "configured_method_metric_objective_contract_malformed"
        elif any(item.objective_target_present for item in ordered):
            limitation = "configured_method_metric_objective_target_rule_not_supported"
        elif any(item.objective_direction == "maintain_range" for item in ordered):
            limitation = "configured_method_metric_maintain_range_rule_not_supported"
        else:
            children: list[dict[str, Any]] = []
            invalid_weight = False
            for item in ordered:
                try:
                    weight = Decimal(item.objective_weight or "")
                except (InvalidOperation, TypeError, ValueError):
                    invalid_weight = True
                    break
                if not weight.is_finite() or weight < 0:
                    invalid_weight = True
                    break
                weight_float = float(weight)
                if not math.isfinite(weight_float):
                    invalid_weight = True
                    break
                children.append(
                    {
                        "kind": "search_metric",
                        "metric_name": item.objective_id,
                        "source_direction": item.objective_direction,
                        "normalized_direction": "minimize",
                        "expected_unit": item.metric_unit_id,
                        "weight": weight_float,
                    }
                )
            if invalid_weight:
                status = ObjectiveScoreStatus.INVALID
                limitation = "configured_method_metric_objective_weight_invalid"
            else:
                configured_rule = {"kind": "composite", "children": children}
                rule["configured_rule"] = configured_rule
                scalar_source = {
                    **{item.objective_id: item.value for item in ordered},
                    "metric_units": {item.objective_id: item.metric_unit_id for item in ordered},
                }
                evaluation = _evaluate_configured_objective_source(configured_rule, scalar_source)
                status = evaluation.status
                score = evaluation.value
                limitation = evaluation.limitation

    if status is not ObjectiveScoreStatus.AVAILABLE:
        score = None
    return _make_score_assessment(
        rule=rule,
        required_input_groups=tuple((item.objective_id,) for item in source_rows),
        source_fields=source_fields,
        source_values=source_values,
        source_unit_bindings=unit_bindings if status is ObjectiveScoreStatus.AVAILABLE else (),
        status=status,
        value=score,
        limitation=limitation,
    )


def read_current_admitted_method_metric_projection(
    store: _MethodMetricProjectionArtifactReader,
    *,
    owner: MethodExecutionSelectionOwner,
    run_id: str,
    tenant_id: str,
    cell_id: str,
) -> MethodMetricProjectionReadResult:
    """Resolve and read the authenticated current-purpose projection for one run.

    The route must authorize its principal before calling this owner lookup. Runtime then
    rederives the durable run/job/attempt scope and returns only its completed current row.
    A missing owner selection is limited; request-supplied refs are never accepted here.
    """
    try:
        selection = owner.get_method_execution_selection(
            run_id=run_id,
            tenant_id=tenant_id,
            cell_id=cell_id,
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("current_method_execution_selection_unavailable",),
        )
    if selection is None:
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("current_method_execution_selection_not_established",),
        )
    if selection.run_id != run_id:
        return MethodMetricProjectionReadResult(
            status="invalid",
            limitations=("runtime_owner_returned_a_different_run_selection",),
        )
    if selection.selection_kind != "graph_method":
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("direct_method_selection_has_no_graph_metric_projection",),
        )
    if selection.method_result_ref is not None:
        return MethodMetricProjectionReadResult(
            status="invalid",
            limitations=("graph_method_selection_cannot_alias_direct_method_result",),
        )
    if selection.metric_verification_status != "verified":
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("runtime_owner_has_no_verified_method_metric_projection",),
        )
    projection = _read_owned_method_metric_projection(store, selection=selection)
    if projection.status != "selected":
        return projection
    try:
        current = owner.get_method_execution_selection(
            run_id=run_id, tenant_id=tenant_id, cell_id=cell_id
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("current_method_execution_reselection_unavailable",),
        )
    if current != selection:
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("current_method_execution_selection_changed_during_read",),
        )
    return projection


def _read_owned_method_metric_projection(
    store: _MethodMetricProjectionArtifactReader,
    *,
    selection: OwnedMethodExecutionSelection,
) -> MethodMetricProjectionReadResult:
    """Read the owner-selected projection without reopening outputs, arrays, or laws."""
    source_refs = (
        selection.simulation_result_ref,
        selection.method_execution_bundle_ref,
        selection.method_metric_binding_set_ref,
    )
    association = selection.method_metric_projection
    if association is None or any(ref is None for ref in source_refs):
        return MethodMetricProjectionReadResult(
            status="verification_missing",
            limitations=("current_method_metric_projection_association_absent",),
        )

    try:
        read_budget = _ProjectionReadBudget()
        simulation_ref = _selected_ref(
            selection.simulation_result_ref,
            kind="foundry.simulation_result",
        )
        bundle_ref = _selected_ref(
            selection.method_execution_bundle_ref,
            kind="foundry.method_execution_bundle",
        )
        binding_ref = _selected_ref(
            selection.method_metric_binding_set_ref,
            kind="foundry.method_metric_binding_set",
        )
        selected_candidate_ref = _selected_ref(
            selection.source_candidate_ref,
            kind="scientist.policy_design.candidate",
        )
        vector_ref = _selected_ref(
            association.vector_ref,
            kind="scientist.policy_evaluation_vector",
        )
        if not association.verifier_revision or not _is_sha256_digest(
            association.verifier_implementation_sha256
        ):
            raise _InvalidProjectionError("owned_verifier_revision_invalid")
        if association.verifier_revision != METHOD_METRIC_PROJECTION_VERIFIER_REVISION:
            raise _InvalidProjectionError("owned_verifier_revision_unsupported")
        if _digest_value(association.verifier_implementation_sha256) != _digest_value(
            _verifier_implementation_sha256()
        ):
            raise _InvalidProjectionError("owned_verifier_implementation_is_stale")

        vector_read = _read_bounded_method_metric_artifact(
            store,
            ref=vector_ref,
            max_bytes=MAX_POLICY_EVALUATION_VECTOR_BYTES,
            read_budget=read_budget,
        )
        vector_manifest = vector_read.manifest
        schema = vector_manifest.artifact_schema
        if (
            schema is None
            or schema.name != "polisyos.scientist.policy_design.PolicyEvaluationVector"
        ):
            raise _InvalidProjectionError("selected_policy_evaluation_vector_schema_invalid")
        if len(vector_manifest.inputs) > MAX_METHOD_METRIC_VECTOR_INPUTS:
            raise _InvalidProjectionError(
                "selected_policy_evaluation_vector_input_count_exceeds_bound"
            )
        if schema.version in {"1.0", "1.1", "1.2"}:
            legacy_payload = vector_read.value
            if (
                isinstance(legacy_payload, Mapping)
                and "method_metric_observations" in legacy_payload
            ):
                if schema.version == "1.2":
                    return MethodMetricProjectionReadResult(
                        status="verification_missing",
                        vector_ref=vector_ref,
                        limitations=("policy_evaluation_vector_1_2_metric_contract_is_limited",),
                    )
                raise _InvalidProjectionError(
                    "legacy_vector_carries_unversioned_method_metric_field"
                )
            _validate_bounded_method_metric_model(
                PolicyEvaluationVector,
                vector_read,
                expected_kind="scientist.policy_evaluation_vector",
                expected_schema_name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                expected_schema_versions={schema.version},
            )
            return MethodMetricProjectionReadResult(
                status="verification_missing",
                vector_ref=vector_ref,
                limitations=(f"legacy_policy_evaluation_vector_{schema.version}_is_limited",),
            )
        if schema.version != "1.3":
            raise _InvalidProjectionError("selected_policy_evaluation_vector_version_unsupported")
        vector = _validate_bounded_method_metric_model(
            PolicyEvaluationVector,
            vector_read,
            expected_kind="scientist.policy_evaluation_vector",
            expected_schema_name="polisyos.scientist.policy_design.PolicyEvaluationVector",
            expected_schema_versions={"1.3"},
        )
        raw_candidate_ref = vector.metadata.get("source_candidate_ref")
        if not isinstance(raw_candidate_ref, Mapping):
            raise _InvalidProjectionError("selected_vector_source_candidate_missing")
        vector_candidate_ref = _selected_ref(
            ArtifactRef.model_validate(raw_candidate_ref),
            kind="scientist.policy_design.candidate",
        )
        if not _same_selected_ref(vector_candidate_ref, selected_candidate_ref):
            raise _InvalidProjectionError("selected_vector_candidate_does_not_match_runtime_owner")

        simulation_manifest = _selected_manifest(store, simulation_ref, read_budget=read_budget)
        bundle_manifest = _selected_manifest(store, bundle_ref, read_budget=read_budget)
        binding_manifest = _selected_manifest(store, binding_ref, read_budget=read_budget)
        _validate_small_source_manifests(
            store=store,
            simulation_manifest=simulation_manifest,
            bundle_manifest=bundle_manifest,
            binding_manifest=binding_manifest,
            simulation_ref=simulation_ref,
            bundle_ref=bundle_ref,
            binding_ref=binding_ref,
            read_budget=read_budget,
        )

        observations = vector.method_metric_observations
        if not observations:
            return MethodMetricProjectionReadResult(
                status="verification_missing",
                vector_ref=vector_ref,
                limitations=("selected_policy_evaluation_vector_has_no_method_observations",),
            )
        if (
            vector.candidate_id is not None
            or vector.primary
            or vector.hard_constraints
            or vector.secondary
            or vector.penalties
            or vector.score_assessment is not None
            or vector.score_source is not None
            or not vector.feasible
            or vector.blocking_reasons
        ):
            raise _InvalidProjectionError("selected_method_metric_vector_is_not_observation_only")
        expected_tuple = _MethodMetricSourceTuple(
            job_id=selection.job_id,
            run_id=selection.run_id,
            attempt=selection.attempt,
            method_result_ref=None,
            simulation_result_ref=simulation_ref,
            method_execution_bundle_ref=bundle_ref,
            method_metric_binding_set_ref=binding_ref,
        )
        if vector.metadata.get("source_tuple_sha256") != _source_tuple_sha256(expected_tuple):
            raise _InvalidProjectionError(
                "selected_vector_source_tuple_does_not_match_current_owner"
            )
        if any(
            observation.binding_set_ref != binding_ref
            or observation.execution_bundle_ref != bundle_ref
            or observation.simulation_result_ref != simulation_ref
            or observation.verifier_revision != association.verifier_revision
            or observation.verifier_id != METHOD_METRIC_PROJECTION_VERIFIER_ID
            or _digest_value(observation.verifier_code_digest)
            != _digest_value(association.verifier_implementation_sha256)
            for observation in observations
        ):
            raise _InvalidProjectionError(
                "observation_source_or_verifier_does_not_match_owned_selection"
            )
        _validate_vector_input_edges(vector_manifest, observations)
        _validate_bundle_output_edges(bundle_manifest, observations)
        return MethodMetricProjectionReadResult(
            status="selected",
            vector_ref=vector_ref,
            observations=observations,
        )
    except _InvalidProjectionError as exc:
        return MethodMetricProjectionReadResult(
            status="invalid",
            limitations=(str(exc),),
        )
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return MethodMetricProjectionReadResult(
            status="invalid",
            limitations=("selected_method_metric_projection_readback_failed",),
        )


def _selected_ref(ref: ArtifactRef | None, *, kind: str) -> SelectedMethodMetricArtifactRef:
    """Validate a full selected-profile JSON reference and freeze its nested fields."""
    if ref is None:
        raise _InvalidProjectionError("selected_method_metric_source_ref_missing")
    selected = SelectedMethodMetricArtifactRef.model_validate(
        {field_name: getattr(ref, field_name) for field_name in ArtifactRef.model_fields}
    )
    if selected.kind != kind or selected.media_type != "application/json":
        raise _InvalidProjectionError("selected_method_metric_source_ref_kind_mismatch")
    return selected


def _same_selected_ref(left: ArtifactRef | None, right: ArtifactRef | None) -> bool:
    """Compare complete selected artifact identities, including profile and media."""
    return left is not None and right is not None and _ref_key(left) == _ref_key(right)


def _core_artifact_ref(ref: ArtifactRef) -> ArtifactRef:
    """Materialize Core's exact base selector from the narrower observation DTO."""
    return ArtifactRef.model_validate(
        {field_name: getattr(ref, field_name) for field_name in ArtifactRef.model_fields}
    )


def _selected_manifest(
    store: _MethodMetricProjectionArtifactReader,
    ref: ArtifactRef,
    *,
    read_budget: _ProjectionReadBudget,
) -> ArtifactManifest:
    """Resolve one bounded manifest and account its actual selected-sidecar bytes."""
    selected_ref = _selected_ref(ref, kind=ref.kind)
    key = artifact_ref_identity_key(selected_ref)
    cached = read_budget.manifests.get(key)
    if cached is not None:
        return cached
    try:
        bounded_manifest = read_core_manifest_profile_bounded(
            store,
            _core_artifact_ref(selected_ref),
            max_manifest_bytes=read_budget.max_manifest_bytes_for(selected_ref),
        )
    except FileNotFoundError as exc:
        raise _UnestablishedProjectionError("selected_method_metric_manifest_unavailable") from exc
    except CoreJsonReadBoundsRefusalError as exc:
        read_budget.account_execution_source_bytes(_core_observed_source_bytes(exc))
        raise _InvalidProjectionError(
            "selected_method_metric_manifest_exceeds_bounded_read"
        ) from exc
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _InvalidProjectionError("selected_method_metric_manifest_profile_invalid") from exc
    manifest = bounded_manifest.manifest
    read_budget.account_execution_source_bytes(_core_observed_source_bytes(bounded_manifest))
    read_budget.account_manifest(
        _core_artifact_ref(selected_ref), bounded_manifest.observed_manifest_bytes
    )
    if (
        str(manifest.artifact_id) != str(selected_ref.artifact_id)
        or manifest.kind != selected_ref.kind
        or manifest.media_type != selected_ref.media_type
        or artifact_manifest_profile_sha256(manifest) != selected_ref.manifest_profile_sha256
    ):
        raise _InvalidProjectionError("selected_method_metric_manifest_profile_mismatch")
    input_limit = (
        MAX_METHOD_METRIC_VECTOR_INPUTS
        if selected_ref.kind == "scientist.policy_evaluation_vector"
        else MAX_METHOD_METRIC_MANIFEST_INPUTS
    )
    if len(manifest.inputs) > input_limit:
        raise _InvalidProjectionError("selected_method_metric_manifest_input_count_exceeds_bound")
    read_budget.manifests[key] = manifest
    return manifest


def _validate_small_source_manifests(
    *,
    store: _MethodMetricProjectionArtifactReader,
    simulation_manifest: ArtifactManifest,
    bundle_manifest: ArtifactManifest,
    binding_manifest: ArtifactManifest,
    simulation_ref: SelectedMethodMetricArtifactRef,
    bundle_ref: SelectedMethodMetricArtifactRef,
    binding_ref: SelectedMethodMetricArtifactRef,
    read_budget: _ProjectionReadBudget,
) -> None:
    """Check the selected one-way manifest edges without decoding bundle or result payloads."""
    simulation_schema = simulation_manifest.artifact_schema
    if (
        simulation_schema is None
        or simulation_schema.name != "polisyos.core.SimulationResult"
        or simulation_schema.version not in {"1.3", "1.4"}
    ):
        raise _InvalidProjectionError("selected_simulation_result_schema_invalid")
    if bundle_manifest.artifact_schema is None or (
        bundle_manifest.artifact_schema.name != "polisyos.core.MethodExecutionBundle"
        or bundle_manifest.artifact_schema.version not in {"1.0", "1.1"}
    ):
        raise _InvalidProjectionError("selected_method_execution_bundle_schema_invalid")
    if binding_manifest.artifact_schema is None or (
        binding_manifest.artifact_schema.name != "polisyos.core.MethodMetricBindingSet"
        or binding_manifest.artifact_schema.version != "1.0"
    ):
        raise _InvalidProjectionError("selected_method_metric_binding_set_schema_invalid")
    _require_exact_manifest_edge(
        simulation_manifest,
        role="method_execution",
        ref=bundle_ref,
    )
    _require_exact_manifest_edge(
        bundle_manifest,
        role="method_metric_binding_set",
        ref=binding_ref,
    )
    bundle_graph_ref = _one_profiled_manifest_input(
        store,
        bundle_manifest,
        role="program_graph",
        kind="foundry.program_graph",
        read_budget=read_budget,
    )
    binding_graph_ref = _one_profiled_manifest_input(
        store,
        binding_manifest,
        role="program_graph",
        kind="foundry.program_graph",
        read_budget=read_budget,
    )
    if artifact_ref_identity_key(bundle_graph_ref) != artifact_ref_identity_key(binding_graph_ref):
        raise _InvalidProjectionError("bundle_and_binding_graph_edges_disagree")
    exec_plan_edges = [edge for edge in bundle_manifest.inputs if edge.role == "exec_plan"]
    if len(exec_plan_edges) != 1:
        raise _InvalidProjectionError("execution_bundle_exec_plan_edge_missing_or_ambiguous")
    exec_plan_manifest = _manifest_from_input_edge(
        store,
        exec_plan_edges[0],
        expected_kind="foundry.exec_plan",
        read_budget=read_budget,
    )
    if (
        exec_plan_manifest.kind != "foundry.exec_plan"
        or exec_plan_manifest.artifact_schema is None
        or exec_plan_manifest.artifact_schema.name != "polisyos.core.ExecPlan"
        or exec_plan_manifest.artifact_schema.version != "0.2.0"
    ):
        raise _InvalidProjectionError("selected_exec_plan_schema_invalid")
    _require_exact_manifest_edge(
        exec_plan_manifest,
        role="method_metric_bindings",
        ref=binding_ref,
    )
    plan_graph_ref = _one_profiled_manifest_input(
        store,
        exec_plan_manifest,
        role="program_graph",
        kind="foundry.program_graph",
        read_budget=read_budget,
    )
    if artifact_ref_identity_key(plan_graph_ref) != artifact_ref_identity_key(bundle_graph_ref):
        raise _InvalidProjectionError("bundle_and_exec_plan_graph_edges_disagree")
    for role, kind, schema_name, schema_versions in (
        ("policy", "ir.trinity_bundle", "polisyos.ir.TrinityBundle", {"1.0"}),
        (
            "registry_bundle",
            "core.registry_bundle",
            None,
            None,
        ),
        (
            "metric_registry",
            "ir.metric_registry",
            "polisyos.ir.kernel.MetricRegistry",
            {"1.0", "1.1"},
        ),
        (
            "units_registry",
            "ir.units_registry",
            "polisyos.ir.kernel.UnitsRegistry",
            {"1.0"},
        ),
    ):
        ref = _one_profiled_manifest_input(
            store,
            binding_manifest,
            role=role,
            kind=kind,
            read_budget=read_budget,
        )
        selected_manifest = _selected_manifest(store, ref, read_budget=read_budget)
        if not _schema_matches_expected_contract(
            selected_manifest.artifact_schema,
            expected_schema_name=schema_name,
            expected_schema_versions=schema_versions,
        ):
            raise _InvalidProjectionError(f"selected_binding_{role}_schema_invalid")
    if simulation_ref.kind != simulation_manifest.kind:
        raise _InvalidProjectionError("selected_simulation_result_kind_mismatch")


def _validate_vector_input_edges(
    vector_manifest: ArtifactManifest,
    observations: tuple[MethodMetricObservation, ...],
) -> None:
    """Require exactly the selected observation edges, with no shadow duplicates."""
    required = method_metric_observation_input_refs(observations)
    expected = {
        (
            role,
            artifact_ref_identity_key(ref)[0],
            artifact_ref_identity_key(ref)[3],
        )
        for role, ref in required
    }
    actual = [
        (
            edge.role,
            str(edge.artifact_id),
            edge.manifest_profile_sha256,
        )
        for edge in vector_manifest.inputs
    ]
    actual_keys = set(actual)
    if len(actual) != len(actual_keys) or actual_keys != expected:
        raise _InvalidProjectionError("policy_evaluation_vector_method_metric_edges_missing")


def _validate_bundle_output_edges(
    bundle_manifest: ArtifactManifest,
    observations: tuple[MethodMetricObservation, ...],
) -> None:
    """Confirm each observed payload is a direct selected bundle input, without reading bytes."""
    schema = bundle_manifest.artifact_schema
    if schema is None:
        raise _InvalidProjectionError("selected_method_execution_bundle_schema_invalid")
    if schema.version == "1.0" and any(
        observation.source_status == "observed" for observation in observations
    ):
        raise _InvalidProjectionError(
            "observed_method_metric_requires_current_prestate_bundle_schema"
        )
    edges_by_role: dict[str, list[InputRef]] = {}
    for edge in bundle_manifest.inputs:
        edges_by_role.setdefault(edge.role, []).append(edge)
    for observation in observations:
        environment_ref = observation.environment_manifest_ref
        if environment_ref is not None:
            _require_exact_manifest_edge(
                bundle_manifest,
                edges_by_role=edges_by_role,
                role="environment_manifest",
                ref=environment_ref,
            )
        if observation.source_status == "observed" and environment_ref is None:
            raise _InvalidProjectionError("observed_method_metric_environment_manifest_missing")
        output_ref = observation.output_ref
        if output_ref is not None:
            _require_exact_manifest_edge(
                bundle_manifest,
                edges_by_role=edges_by_role,
                role=f"method_output:{observation.occurrence_id}:{observation.slot_id}",
                ref=output_ref,
            )
        input_capture_ref = observation.input_capture_ref
        if input_capture_ref is not None:
            if observation.occurrence_id is None:
                raise _InvalidProjectionError("unmatched_method_metric_binding_has_input_capture")
            _require_exact_manifest_edge(
                bundle_manifest,
                edges_by_role=edges_by_role,
                role=f"method_metric_input_capture:{observation.occurrence_id}",
                ref=input_capture_ref,
            )
        if observation.source_status == "observed" and input_capture_ref is None:
            raise _InvalidProjectionError("observed_method_metric_input_capture_missing")
        prestate_rows = [
            item
            for item in observation.predicate_evidence
            if item.predicate_id == "selected_input_capture_and_prestate_identity"
        ]
        if observation.source_status == "observed":
            if observation.occurrence_id is None or len(prestate_rows) != 1:
                raise _InvalidProjectionError("observed_method_metric_prestate_evidence_missing")
            prestate_ref = prestate_rows[0].evidence_ref
            if prestate_ref is None:
                raise _InvalidProjectionError("observed_method_metric_prestate_ref_missing")
            _require_exact_manifest_edge(
                bundle_manifest,
                edges_by_role=edges_by_role,
                role=f"method_prestate:{observation.occurrence_id}",
                ref=prestate_ref,
            )


def _one_profiled_manifest_input(
    store: _MethodMetricProjectionArtifactReader,
    manifest: ArtifactManifest,
    *,
    role: str,
    kind: str,
    read_budget: _ProjectionReadBudget,
) -> SelectedMethodMetricArtifactRef:
    """Resolve one full-profile lineage edge into a strict typed ref."""
    edges = [edge for edge in manifest.inputs if edge.role == role]
    if len(edges) != 1 or edges[0].manifest_profile_sha256 is None:
        raise _InvalidProjectionError(f"selected_manifest_requires_one_profiled_{role}_edge")
    selected_manifest = _manifest_from_input_edge(
        store,
        edges[0],
        expected_kind=kind,
        read_budget=read_budget,
    )
    if selected_manifest.kind != kind:
        raise _InvalidProjectionError(f"selected_manifest_{role}_edge_kind_mismatch")
    return SelectedMethodMetricArtifactRef(
        artifact_id=selected_manifest.artifact_id,
        kind=selected_manifest.kind,
        media_type=selected_manifest.media_type,
        manifest_profile_sha256=edges[0].manifest_profile_sha256,
    )


def _manifest_from_input_edge(
    store: _MethodMetricProjectionArtifactReader,
    edge: InputRef,
    *,
    expected_kind: str,
    read_budget: _ProjectionReadBudget,
) -> ArtifactManifest:
    """Resolve the exact sidecar selected by a manifest input without reading its payload."""
    profile = edge.manifest_profile_sha256
    if profile is None:
        raise _InvalidProjectionError("exec_plan_selected_profile_missing")
    try:
        selected_ref = ArtifactRef(
            artifact_id=edge.artifact_id,
            kind=expected_kind,
            media_type="application/json",
            manifest_profile_sha256=profile,
        )
    except (TypeError, ValueError) as exc:
        raise _InvalidProjectionError("selected_manifest_edge_ref_invalid") from exc
    return _selected_manifest(store, selected_ref, read_budget=read_budget)


def _digest_value(value: str) -> str:
    """Normalize an optional SHA-256 prefix for exact verifier digest comparison."""
    return value.removeprefix("sha256:")


def _is_sha256_digest(value: str) -> bool:
    """Accept the canonical digest spelling used by the registered verifier owner."""
    digest = value.removeprefix("sha256:")
    return len(digest) == 64 and all(character in "0123456789abcdef" for character in digest)


def _method_class_source_sha256[MethodClassT](method_class: type[MethodClassT]) -> str | None:
    """Recompute the producer's narrowly declared class-source digest."""
    try:
        source = inspect.getsource(method_class).encode("utf-8")
    except (OSError, TypeError, UnicodeError):
        return None
    return "sha256:" + hashlib.sha256(source).hexdigest()


class _InvalidProjectionError(ValueError):
    """Internal fail-closed read diagnostic with a bounded public reason."""


@dataclass(frozen=True, slots=True)
class _RegisteredMethodMetricBindingContract:
    """Current owner metadata needed to validate an available compiled binding."""

    law_identity: tuple[str, str, str] | None
    semantics_match: bool
    adapter_identity: tuple[str, str, str] | None
    input_unit_contract: tuple[tuple[str, str, MethodMetricSourceUnit], ...] | None
    actual_input_units: tuple[tuple[str, MethodMetricSourceUnit], ...]
    actual_input_slot_ids: tuple[str, ...]
    input_contract_resolved: bool = False
    output_slot_contract_matches: bool | None = None


@dataclass(frozen=True, slots=True)
class _MethodMetricBindingAdmission:
    """One typed decision separating persisted consistency from positive premises."""

    status: Literal["unavailable", "requires_positive_validation", "admitted"]
    law_identity: tuple[str, str, str]
    adapter_identity: tuple[str, str, str]
    limitation: str | None = None


def _admit_method_metric_binding(
    *,
    binding_availability: Literal["available", "unavailable"],
    binding_limitation: str | None,
    binding_semantics: Any,
    metric_semantics: Any,
    binding_law_identity: tuple[str, str, str],
    binding_adapter_identity: tuple[str, str, str],
    positive_contract: _RegisteredMethodMetricBindingContract | None = None,
) -> _MethodMetricBindingAdmission:
    """Admit one binding as unavailable or validate its complete positive contract.

    Persisted cross-artifact disagreement is invalid for every row. Positive-only law,
    adapter, ABI-input, and unit premises are evaluated together only for a binding
    that claims ``available``; a consistent compiler limitation never needs them.
    """
    if binding_semantics != metric_semantics:
        raise _InvalidProjectionError("method_metric_binding_semantics_registry_mismatch")
    if binding_availability == "unavailable":
        if not binding_limitation:
            raise _InvalidProjectionError("unavailable_method_metric_binding_has_no_limitation")
        return _MethodMetricBindingAdmission(
            status="unavailable",
            law_identity=binding_law_identity,
            adapter_identity=binding_adapter_identity,
            limitation=binding_limitation,
        )

    if positive_contract is None:
        return _MethodMetricBindingAdmission(
            status="requires_positive_validation",
            law_identity=binding_law_identity,
            adapter_identity=binding_adapter_identity,
        )
    if positive_contract.law_identity is None:
        raise _InvalidProjectionError("available_method_metric_binding_has_no_registered_law")
    if binding_law_identity != positive_contract.law_identity:
        raise _InvalidProjectionError("method_metric_registered_law_identity_mismatch")
    if binding_semantics is None or not positive_contract.semantics_match:
        raise _InvalidProjectionError("available_method_metric_binding_semantics_unregistered")
    if (
        positive_contract.adapter_identity is None
        or binding_adapter_identity != positive_contract.adapter_identity
    ):
        raise _InvalidProjectionError("method_metric_registered_adapter_identity_mismatch")
    if (
        not positive_contract.input_contract_resolved
        or positive_contract.output_slot_contract_matches is None
    ):
        return _MethodMetricBindingAdmission(
            status="requires_positive_validation",
            law_identity=positive_contract.law_identity,
            adapter_identity=positive_contract.adapter_identity,
        )
    if positive_contract.input_unit_contract is None:
        raise _InvalidProjectionError("available_method_metric_input_contract_unregistered")
    if not positive_contract.output_slot_contract_matches:
        raise _InvalidProjectionError("method_metric_output_slot_contract_mismatch")

    expected_slots: dict[str, MethodMetricSourceUnit] = {}
    expected_roles: set[str] = set()
    for role_id, slot_id, unit in positive_contract.input_unit_contract:
        if role_id in expected_roles:
            raise _InvalidProjectionError("registered_method_metric_input_contract_not_unique")
        expected_roles.add(role_id)
        if slot_id in expected_slots:
            raise _InvalidProjectionError("registered_method_metric_input_contract_not_unique")
        expected_slots[slot_id] = unit
    provided_units: dict[str, MethodMetricSourceUnit] = {}
    for slot_id, unit in positive_contract.actual_input_units:
        if slot_id in provided_units:
            raise _InvalidProjectionError("current_method_input_unit_inventory_not_unique")
        provided_units[slot_id] = unit
    if (
        not expected_slots
        or set(positive_contract.actual_input_slot_ids) != set(expected_slots)
        or len(positive_contract.actual_input_slot_ids)
        != len(set(positive_contract.actual_input_slot_ids))
        or set(provided_units) != set(expected_slots)
        or any(
            not _same_method_metric_source_unit(provided_units[slot_id], expected_unit)
            for slot_id, expected_unit in expected_slots.items()
        )
    ):
        raise _InvalidProjectionError("method_metric_registered_input_contract_mismatch")
    return _MethodMetricBindingAdmission(
        status="admitted",
        law_identity=positive_contract.law_identity,
        adapter_identity=positive_contract.adapter_identity,
    )


@dataclass(slots=True)
class _ProjectionReadBudget:
    """Bound actual reads across source admission and projection verification."""

    max_bytes: int = MAX_METHOD_METRIC_TOTAL_SOURCE_BYTES
    max_manifest_bytes: int = MAX_METHOD_METRIC_MANIFEST_BYTES
    observed_manifest_bytes: int = 0
    observed_payload_bytes: int = 0
    manifest_refs: set[tuple[str, str, str, str | None]] = field(default_factory=set)
    payload_refs: set[tuple[str, str, str, str | None]] = field(default_factory=set)
    manifests: dict[tuple[str, str, str, str | None], ArtifactManifest] = field(
        default_factory=dict
    )
    observed_execution_source_bytes: int = 0

    @property
    def observed_bytes(self) -> int:
        """Return measured store-transfer bytes, including integrity verification reads."""
        return self.observed_execution_source_bytes

    @property
    def remaining_bytes(self) -> int:
        """Return the aggregate capacity left before any further bounded read."""
        return self.max_bytes - self.observed_bytes

    def max_manifest_bytes_for(self, ref: ArtifactRef) -> int:
        """Bound a metadata-only read by the remaining aggregate capacity."""
        key = artifact_ref_identity_key(ref)
        remaining = self.remaining_bytes
        if remaining < 1:
            raise _InvalidProjectionError("method_metric_source_bytes_exceed_bounded_admission")
        if key in self.manifest_refs:
            return min(self.max_manifest_bytes, remaining)
        return min(self.max_manifest_bytes, remaining)

    def limits_for_payload(self, ref: ArtifactRef, *, max_bytes: int) -> CoreJsonReadLimits:
        """Choose per-read limits whose worst-case sum fits the remaining budget."""
        key = artifact_ref_identity_key(ref)
        if key in self.payload_refs:
            raise _InvalidProjectionError("selected_method_metric_payload_read_repeated")
        remaining = self.remaining_bytes
        if remaining < 3:
            raise _InvalidProjectionError("method_metric_source_bytes_exceed_bounded_admission")
        # Core's selected manifest and digest-bound member open are separate
        # store reads, so reserve both before allowing payload transfer.
        manifest_limit = min(self.max_manifest_bytes, remaining // 3)
        payload_limit = min(max_bytes, remaining - 2 * manifest_limit)
        if payload_limit < 1 or manifest_limit < 1:
            raise _InvalidProjectionError("method_metric_source_bytes_exceed_bounded_admission")
        output = ref.kind == "foundry.method_output"
        return CoreJsonReadLimits(
            max_bytes=payload_limit,
            max_depth=(
                MAX_METHOD_METRIC_OUTPUT_READ_DEPTH if output else MAX_METHOD_METRIC_READ_DEPTH
            ),
            max_elements=(
                MAX_METHOD_METRIC_OUTPUT_READ_ELEMENTS
                if output
                else MAX_METHOD_METRIC_READ_ELEMENTS
            ),
            max_manifest_bytes=manifest_limit,
        )

    def account_manifest(self, ref: ArtifactRef, observed_bytes: int) -> None:
        """Record unique selected-manifest content bytes for diagnostics only."""
        key = artifact_ref_identity_key(ref)
        self._account_once(
            key,
            observed_bytes,
            seen=self.manifest_refs,
            counter_name="observed_manifest_bytes",
        )

    def account_payload(self, ref: ArtifactRef, observed_bytes: int) -> None:
        """Record unique selected-payload content bytes for diagnostics only."""
        key = artifact_ref_identity_key(ref)
        self._account_once(
            key,
            observed_bytes,
            seen=self.payload_refs,
            counter_name="observed_payload_bytes",
        )

    def account_execution_source_bytes(self, observed_bytes: int) -> None:
        """Count exact selected-store transfers, preserving over-cap attempts."""
        if type(observed_bytes) is not int or observed_bytes < 0:
            raise _InvalidProjectionError("method_metric_observed_byte_count_invalid")
        self.observed_execution_source_bytes += observed_bytes
        if self.observed_bytes > self.max_bytes:
            raise _InvalidProjectionError("method_metric_source_bytes_exceed_bounded_admission")

    def account_refused_execution_source_bytes(self, observed_bytes: int) -> None:
        """Retain exact transfer usage from a bounded refusal before returning limited."""
        if type(observed_bytes) is not int or observed_bytes < 0:
            raise _UnestablishedProjectionError("method_metric_transfer_accounting_not_established")
        self.observed_execution_source_bytes += observed_bytes

    def account_bounded_read(
        self,
        ref: ArtifactRef,
        bounded_read: CoreJsonArtifactBoundedRead,
    ) -> None:
        """Account one Core read's measured total store transfers and content bytes."""
        observed_source_bytes = _core_observed_source_bytes(bounded_read)
        self.account_execution_source_bytes(observed_source_bytes)
        self.account_manifest(ref, bounded_read.observed_manifest_bytes)
        self.account_payload(ref, bounded_read.observed_bytes)

    def account_refused_read(
        self,
        ref: ArtifactRef,
        *,
        observed_manifest_bytes: int,
        observed_bytes: int,
        observed_source_bytes: int,
    ) -> None:
        """Account the exact transfer count from a bounded refusal before limiting it."""
        self.account_refused_execution_source_bytes(observed_source_bytes)
        self.account_manifest(ref, observed_manifest_bytes)
        if observed_bytes:
            self.account_payload(ref, observed_bytes)

    def _account_once(
        self,
        key: tuple[str, str, str, str | None],
        observed_bytes: int,
        *,
        seen: set[tuple[str, str, str, str | None]],
        counter_name: Literal["observed_manifest_bytes", "observed_payload_bytes"],
    ) -> None:
        if type(observed_bytes) is not int or observed_bytes < 0:
            raise _InvalidProjectionError("method_metric_observed_byte_count_invalid")
        if key in seen:
            return
        seen.add(key)
        setattr(self, counter_name, getattr(self, counter_name) + observed_bytes)


def _core_observed_source_bytes(receipt: object) -> int:
    """Require the Core owner-reported sum of all store transfers for a read."""
    observed = getattr(receipt, "observed_source_bytes", None)
    if type(observed) is not int or observed < 0:
        raise _UnestablishedProjectionError("core_store_transfer_accounting_not_established")
    return observed


class _BoundedExecutionSourceReader:
    """Route Foundry's complete source-admission walk through the shared budget."""

    def __init__(
        self,
        store: _MethodMetricProjectionArtifactStore,
        read_budget: _ProjectionReadBudget,
    ) -> None:
        self._store = store
        self._read_budget = read_budget
        self.last_source_identity: str | None = None
        self._pending_state_blob_bindings: dict[
            tuple[tuple[str, str, str, str | None], str, str, str | None], ArtifactRef
        ] = {}

    def read_selected_manifest(
        self,
        ref: ArtifactRef,
    ) -> tuple[ArtifactManifest, int]:
        """Read one exact selected manifest under the remaining aggregate cap."""
        self._pending_state_blob_bindings.clear()
        self.last_source_identity = (
            f"selected:{ref.artifact_id}:{ref.kind}:{ref.media_type}:{ref.manifest_profile_sha256}"
        )
        remaining = self._read_budget.remaining_bytes
        if remaining < 1:
            self._raise_budget_refusal(observed_bytes=0)
        limit = min(self._read_budget.max_manifest_bytes, remaining)
        try:
            bounded = read_core_manifest_profile_bounded(
                self._store,
                _core_artifact_ref(ref),
                max_manifest_bytes=limit,
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self._raise_core_read_refusal(exc, read_kind="selected_manifest")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            observed = getattr(exc, "observed_source_bytes", None)
            if type(observed) is not int or observed < 0:
                raise _UnestablishedProjectionError(
                    "core_manifest_transfer_accounting_not_established"
                ) from exc
            self._account_refusal(observed)
            self._raise_budget_refusal(observed_bytes=observed, cause=exc)
        observed = _core_observed_source_bytes(bounded)
        self._account_read(observed)
        if ref.kind == "foundry.state_snapshot":
            observed += self._bind_selected_state_snapshot_parent(ref, bounded.manifest)
        return bounded.manifest, observed

    def _bind_selected_state_snapshot_parent(
        self,
        ref: ArtifactRef,
        manifest: ArtifactManifest,
    ) -> int:
        """Resolve one strict snapshot parent before allowing its binary child edge."""
        from polisyos.core.contracts.foundry import StateSnapshot

        if (
            ref.manifest_profile_sha256 is None
            or ref.kind != "foundry.state_snapshot"
            or ref.media_type != "application/json"
            or manifest.kind != "foundry.state_snapshot"
            or manifest.media_type != "application/json"
        ):
            raise _InvalidProjectionError("state_snapshot_selected_identity_invalid")

        typed_manifest, value, manifest_bytes, payload_bytes = self.read_typed_model(
            StateSnapshot,
            ref,
        )
        if typed_manifest != manifest or not isinstance(value, StateSnapshot):
            raise _InvalidProjectionError("state_snapshot_selected_payload_identity_mismatch")
        expected_schema_version = StateSnapshot.SCHEMA_MANIFEST_VERSION_BY_PAYLOAD_VERSION.get(
            value.schema_version
        )
        if (
            expected_schema_version is None
            or manifest.artifact_schema
            != SchemaInfo(
                name="polisyos.core.StateSnapshot",
                version=expected_schema_version,
            )
            or value.lineage_inputs is None
            or value.state_ref.kind != "foundry.state_blob"
            or value.state_ref.media_type != "application/x-npz"
            or value.state_ref.manifest_profile_sha256 is None
        ):
            raise _InvalidProjectionError("state_snapshot_payload_identity_invalid")

        expected_edge = input_ref_from_artifact_ref(value.state_ref, role="state_blob")
        state_blob_edges = [edge for edge in manifest.inputs if edge.role == "state_blob"]
        if (
            manifest.inputs != value.lineage_inputs
            or len(state_blob_edges) != 1
            or state_blob_edges[0] != expected_edge
        ):
            raise _InvalidProjectionError("state_snapshot_blob_parent_edge_mismatch")

        self._pending_state_blob_bindings[
            (
                artifact_ref_identity_key(ref),
                str(expected_edge.artifact_id),
                expected_edge.role,
                expected_edge.manifest_profile_sha256,
            )
        ] = value.state_ref
        return manifest_bytes + payload_bytes

    def read_edge_manifest(
        self,
        parent_ref: ArtifactRef,
        edge: InputRef,
    ) -> tuple[ArtifactRef, ArtifactManifest, int]:
        """Resolve one profiled input edge without synthesizing kind or media."""
        pending_state_blob_ref = self._pending_state_blob_bindings.pop(
            (
                artifact_ref_identity_key(parent_ref),
                str(edge.artifact_id),
                edge.role,
                edge.manifest_profile_sha256,
            ),
            None,
        )
        self.last_source_identity = (
            f"edge:{parent_ref.artifact_id}:{parent_ref.manifest_profile_sha256}:"
            f"{edge.role}:{edge.artifact_id}:{edge.manifest_profile_sha256}"
        )
        remaining = self._read_budget.remaining_bytes
        if remaining < 1:
            self._raise_budget_refusal(observed_bytes=0)
        limit = min(self._read_budget.max_manifest_bytes, remaining)
        if pending_state_blob_ref is not None:
            return self._read_bound_state_blob_manifest(
                edge,
                pending_state_blob_ref,
                max_manifest_bytes=limit,
            )
        try:
            bounded = read_core_input_manifest_profile_bounded(
                self._store,
                edge,
                max_manifest_bytes=limit,
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self._raise_core_read_refusal(exc, read_kind="input_edge_manifest")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            observed = getattr(exc, "observed_source_bytes", None)
            if type(observed) is not int or observed < 0:
                raise _UnestablishedProjectionError(
                    "core_manifest_transfer_accounting_not_established"
                ) from exc
            self._account_refusal(observed)
            self._raise_budget_refusal(observed_bytes=observed, cause=exc)
        observed = _core_observed_source_bytes(bounded)
        self._account_read(observed)
        return bounded.effective_ref, bounded.manifest, observed

    def _read_bound_state_blob_manifest(
        self,
        edge: InputRef,
        selected_ref: ArtifactRef,
        *,
        max_manifest_bytes: int,
    ) -> tuple[ArtifactRef, ArtifactManifest, int]:
        """Read only the exact binary child selected by a validated snapshot parent."""
        if (
            edge.role != "state_blob"
            or edge != input_ref_from_artifact_ref(selected_ref, role="state_blob")
            or selected_ref.kind != "foundry.state_blob"
            or selected_ref.media_type != "application/x-npz"
            or selected_ref.manifest_profile_sha256 is None
        ):
            raise _InvalidProjectionError("state_blob_selected_parent_binding_invalid")
        try:
            bounded = read_core_manifest_profile_bounded(
                self._store,
                selected_ref,
                max_manifest_bytes=max_manifest_bytes,
                allow_profile_absent=True,
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self._raise_core_read_refusal(exc, read_kind="state_blob_manifest")
        except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
            observed = getattr(exc, "observed_source_bytes", None)
            if type(observed) is not int or observed < 0:
                raise _UnestablishedProjectionError(
                    "core_manifest_transfer_accounting_not_established"
                ) from exc
            self._account_refusal(observed)
            self._raise_budget_refusal(observed_bytes=observed, cause=exc)
        manifest = bounded.manifest
        if (
            bounded.effective_ref != selected_ref
            or manifest.artifact_id != selected_ref.artifact_id
            or manifest.kind != "foundry.state_blob"
            or manifest.media_type != "application/x-npz"
            or manifest.artifact_schema is not None
            or manifest.canon is not None
            or artifact_manifest_profile_sha256(manifest) != selected_ref.manifest_profile_sha256
        ):
            raise _InvalidProjectionError("state_blob_manifest_identity_mismatch")
        observed = _core_observed_source_bytes(bounded)
        self._account_read(observed)
        return selected_ref, manifest, observed

    def _raise_core_read_refusal(
        self,
        exc: CoreJsonReadBoundsRefusalError,
        *,
        read_kind: str,
    ) -> NoReturn:
        """Keep bounded overruns, semantic refusal, and unknown usage distinct."""
        observed = _core_observed_source_bytes(exc)
        limit_name = getattr(exc, "limit_name", None)
        if type(limit_name) is str:
            observed_limit = {
                "max_manifest_bytes": getattr(exc, "observed_manifest_bytes", None),
                "max_bytes": getattr(exc, "observed_payload_bytes", None),
                "max_depth": getattr(exc, "observed_depth", None),
                "max_elements": getattr(exc, "observed_elements", None),
            }.get(limit_name)
            limit_value = getattr(exc, "limit_value", None)
            if (
                type(observed_limit) is int
                and type(limit_value) is int
                and limit_value >= 0
                and observed_limit > limit_value
                and limit_name in {"max_manifest_bytes", "max_bytes"}
            ):
                self._account_refusal(observed)
                remaining_bytes = self._read_budget.remaining_bytes + observed
                if limit_name == "max_manifest_bytes" and limit_value == remaining_bytes:
                    self._raise_budget_refusal(observed_bytes=observed, cause=exc)
                raise _UnestablishedProjectionError(
                    f"{read_kind}_bounded_{limit_name}_limit_exceeded"
                ) from exc
            if (
                type(observed_limit) is int
                and type(limit_value) is int
                and limit_value >= 0
                and observed_limit > limit_value
            ):
                self._account_refusal(observed)
                raise _UnestablishedProjectionError(
                    f"{read_kind}_bounded_{limit_name}_limit_exceeded"
                ) from exc
            self._account_refusal(observed)
            raise _UnestablishedProjectionError(
                f"{read_kind}_bounded_limit_evidence_inconsistent"
            ) from exc
        if getattr(exc, "failure_stage", None) in {
            "selected_manifest_profile_validation",
            "selected_manifest_result_validation",
            "selected_manifest_local_validation",
        }:
            self._account_read(observed)
            code = getattr(exc, "code", None)
            if type(code) is not str or not code:
                code = "profile_validation_refused"
            raise _InvalidProjectionError(f"{read_kind}_refused:{code}") from exc
        self._account_refusal(observed)
        raise _UnestablishedProjectionError(
            f"{read_kind}_bounded_read_outcome_not_established"
        ) from exc

    def read_typed_model[ModelT: BaseModel](
        self,
        model: type[ModelT],
        ref: ArtifactRef,
    ) -> tuple[ArtifactManifest, ModelT, int, int]:
        """Read and strictly validate one Core model within remaining bytes."""
        from polisyos.foundry.execute.api import ExecutionSourceBoundedReadRefusal

        self._pending_state_blob_bindings.clear()
        self.last_source_identity = (
            f"typed:{model.__module__}.{model.__qualname__}:{ref.artifact_id}:"
            f"{ref.kind}:{ref.media_type}:{ref.manifest_profile_sha256}"
        )
        remaining = self._read_budget.remaining_bytes
        if remaining < 3:
            raise ExecutionSourceBoundedReadRefusal(
                "method_metric_source_bytes_exceed_bounded_admission",
                observed_bytes=0,
                limit_bytes=remaining,
            )
        # Core selects and revalidates the profile manifest before reading the
        # payload. Reserve both manifest transfers before admitting payload.
        manifest_limit = min(self._read_budget.max_manifest_bytes, max(1, remaining // 3))
        payload_limit = remaining - 2 * manifest_limit
        limits = CoreJsonReadLimits(
            max_bytes=payload_limit,
            max_depth=MAX_METHOD_METRIC_READ_DEPTH,
            max_elements=MAX_METHOD_METRIC_READ_ELEMENTS,
            max_manifest_bytes=manifest_limit,
        )
        try:
            bounded = read_core_json_artifact_bounded(
                self._store, _core_artifact_ref(ref), limits=limits
            )
        except CoreJsonReadBoundsRefusalError as exc:
            self._raise_core_read_refusal(exc, read_kind="typed_model")
        manifest = bounded.manifest
        try:
            value = validate_core_model_bounded_read(model, bounded)
        except Exception as exc:
            raise ValueError("method_metric_execution_source_typed_model_invalid") from exc
        if not isinstance(value, model):
            raise TypeError("method_metric_execution_source_typed_model_contract_mismatch")
        observed_source_bytes = _core_observed_source_bytes(bounded)
        payload_bytes = bounded.observed_bytes
        manifest_transfer_bytes = observed_source_bytes - payload_bytes
        if manifest_transfer_bytes < bounded.observed_manifest_bytes:
            raise TypeError("core_transfer_receipt_omits_selected_manifest_read")
        self._account_read(observed_source_bytes)
        return manifest, value, manifest_transfer_bytes, payload_bytes

    def _account_read(self, observed_bytes: int) -> None:
        """Charge every physical Foundry source read, including repeated refs."""
        try:
            self._read_budget.account_execution_source_bytes(observed_bytes)
        except _InvalidProjectionError as exc:
            self._raise_budget_refusal(observed_bytes=observed_bytes, cause=exc)

    def _account_refusal(self, observed_bytes: int) -> None:
        """Charge exact bounded-refusal usage before refusing all subsequent reads."""
        self._read_budget.account_refused_execution_source_bytes(observed_bytes)

    def _raise_budget_refusal(
        self,
        *,
        observed_bytes: int,
        cause: Exception | None = None,
    ) -> NoReturn:
        """Return the AD01 protocol's typed shared-budget refusal."""
        from polisyos.foundry.execute.api import ExecutionSourceBoundedReadRefusal

        raise ExecutionSourceBoundedReadRefusal(
            "method_metric_source_bytes_exceed_bounded_admission",
            observed_bytes=observed_bytes,
            limit_bytes=self._read_budget.max_bytes,
        ) from cause


@dataclass(frozen=True, slots=True)
class _SelectedArtifactRefSnapshot:
    """Immutable scalar copy of the complete base ArtifactRef identity."""

    artifact_id: ArtifactID
    kind: str
    media_type: str
    manifest_profile_sha256: str

    @classmethod
    def capture(cls, ref: ArtifactRef, *, kind: str) -> _SelectedArtifactRefSnapshot:
        """Validate and snapshot one exact full-profile JSON ref."""
        if not isinstance(ref, ArtifactRef):
            raise TypeError("method_metric_source_ref_must_be_artifact_ref")
        if (
            ref.kind != kind
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
        ):
            raise ValueError("method_metric_source_ref_requires_selected_profile")
        return cls(
            artifact_id=ref.artifact_id,
            kind=ref.kind,
            media_type=ref.media_type,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )

    def materialize(self) -> ArtifactRef:
        """Return a fresh full-profile view rather than exposing mutable input state."""
        return ArtifactRef(
            artifact_id=self.artifact_id,
            kind=self.kind,
            media_type=self.media_type,
            manifest_profile_sha256=self.manifest_profile_sha256,
        )


@dataclass(frozen=True, slots=True, init=False)
class _MethodMetricSourceTuple:
    """Immutable current-job tuple that binds a projection receipt to its producer refs."""

    job_id: str
    run_id: str
    attempt: int
    _method_result_ref: _SelectedArtifactRefSnapshot | None
    _simulation_result_ref: _SelectedArtifactRefSnapshot
    _method_execution_bundle_ref: _SelectedArtifactRefSnapshot
    _method_metric_binding_set_ref: _SelectedArtifactRefSnapshot

    def __init__(
        self,
        *,
        job_id: str,
        run_id: str,
        attempt: int,
        method_result_ref: ArtifactRef | None,
        simulation_result_ref: ArtifactRef,
        method_execution_bundle_ref: ArtifactRef,
        method_metric_binding_set_ref: ArtifactRef,
    ) -> None:
        if type(job_id) is not str or not job_id or len(job_id) > 256:
            raise ValueError("method_metric_job_id_invalid")
        if type(run_id) is not str or not run_id or len(run_id) > 256:
            raise ValueError("method_metric_run_id_invalid")
        if type(attempt) is not int or attempt < 1:
            raise ValueError("method_metric_attempt_must_be_positive")
        object.__setattr__(self, "job_id", job_id)
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "attempt", attempt)
        if method_result_ref is not None:
            object.__setattr__(
                self,
                "_method_result_ref",
                _SelectedArtifactRefSnapshot.capture(
                    method_result_ref,
                    kind=method_result_ref.kind,
                ),
            )
        else:
            object.__setattr__(self, "_method_result_ref", None)
        object.__setattr__(
            self,
            "_simulation_result_ref",
            _SelectedArtifactRefSnapshot.capture(
                simulation_result_ref,
                kind="foundry.simulation_result",
            ),
        )
        object.__setattr__(
            self,
            "_method_execution_bundle_ref",
            _SelectedArtifactRefSnapshot.capture(
                method_execution_bundle_ref,
                kind="foundry.method_execution_bundle",
            ),
        )
        object.__setattr__(
            self,
            "_method_metric_binding_set_ref",
            _SelectedArtifactRefSnapshot.capture(
                method_metric_binding_set_ref,
                kind="foundry.method_metric_binding_set",
            ),
        )

    @property
    def method_result_ref(self) -> ArtifactRef | None:
        """Materialize the optional exact non-graph Method result ref."""
        return None if self._method_result_ref is None else self._method_result_ref.materialize()

    @property
    def simulation_result_ref(self) -> ArtifactRef:
        """Materialize the selected graph simulation result ref."""
        return self._simulation_result_ref.materialize()

    @property
    def method_execution_bundle_ref(self) -> ArtifactRef:
        """Materialize the selected graph execution bundle ref."""
        return self._method_execution_bundle_ref.materialize()

    @property
    def method_metric_binding_set_ref(self) -> ArtifactRef:
        """Materialize the selected compile-time metric binding set ref."""
        return self._method_metric_binding_set_ref.materialize()


_VERIFIED_METHOD_METRIC_PROJECTION_SEAL = object()


class _VerifiedMethodMetricProjectionAdmission(_EphemeralMethodMetricCapability):
    """In-process capability proving one staged vector matches one exact source tuple."""

    source_tuple: _MethodMetricSourceTuple
    __slots__ = (
        "_seal",
        "_source_candidate_ref",
        "_vector_ref",
        "source_tuple",
        "verifier_implementation_sha256",
        "verifier_revision",
    )
    verifier_revision: str
    verifier_implementation_sha256: str

    def __init__(
        self,
        *,
        source_tuple: _MethodMetricSourceTuple,
        source_candidate_ref: ArtifactRef,
        vector_ref: ArtifactRef,
        verifier_revision: str,
        verifier_implementation_sha256: str,
        _seal: object,
    ) -> None:
        if _seal is not _VERIFIED_METHOD_METRIC_PROJECTION_SEAL:
            raise ValueError("method_metric_projection_admission_must_be_issued_by_worker")
        if type(source_tuple) is not _MethodMetricSourceTuple:
            raise TypeError("method_metric_projection_source_tuple_must_be_owned_type")
        if not verifier_revision or not _is_sha256_digest(verifier_implementation_sha256):
            raise ValueError("method_metric_projection_verifier_identity_invalid")
        object.__setattr__(self, "source_tuple", source_tuple)
        object.__setattr__(
            self,
            "_source_candidate_ref",
            _SelectedArtifactRefSnapshot.capture(
                source_candidate_ref,
                kind="scientist.policy_design.candidate",
            ),
        )
        object.__setattr__(
            self,
            "_vector_ref",
            _SelectedArtifactRefSnapshot.capture(
                vector_ref,
                kind="scientist.policy_evaluation_vector",
            ),
        )
        object.__setattr__(self, "verifier_revision", verifier_revision)
        object.__setattr__(
            self,
            "verifier_implementation_sha256",
            verifier_implementation_sha256,
        )
        object.__setattr__(self, "_seal", _seal)

    @property
    def vector_ref(self) -> ArtifactRef:
        """Materialize a fresh vector ref for the atomic Runtime selection write."""
        return self._vector_ref.materialize()

    @property
    def source_candidate_ref(self) -> ArtifactRef:
        """Materialize the candidate proven by Foundry's bounded input-basis walk."""
        return self._source_candidate_ref.materialize()


def is_verified_method_metric_projection_admission(value: object) -> bool:
    """Check the exact worker-issued in-process admission capability."""
    return (
        type(value) is _VerifiedMethodMetricProjectionAdmission
        and value._seal is _VERIFIED_METHOD_METRIC_PROJECTION_SEAL
    )


class MethodMetricProjectionRefOutcome(_EphemeralMethodMetricCapability):
    """Bounded refs-only outcome for the fixed AD01 SharedExecutor operation."""

    status: Literal["verified", "verification_missing", "invalid"]
    admission: _VerifiedMethodMetricProjectionAdmission | None
    limitations: tuple[str, ...]

    __slots__ = ("admission", "limitations", "status")

    def __init__(
        self,
        *,
        status: Literal["verified", "verification_missing", "invalid"],
        admission: _VerifiedMethodMetricProjectionAdmission | None = None,
        limitations: tuple[str, ...] = (),
    ) -> None:
        if status == "verified":
            if not is_verified_method_metric_projection_admission(admission):
                raise ValueError("verified_method_metric_projection_requires_worker_receipt")
            if limitations:
                raise ValueError("verified_method_metric_projection_cannot_have_failure_reason")
        elif admission is not None or not limitations:
            raise ValueError("nonreceipt_method_metric_outcome_requires_limitation_only")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "admission", admission)
        object.__setattr__(self, "limitations", tuple(limitations))


class MethodMetricProjectionWorkLike(Protocol):
    """Read-only structural view accepted by the configured-CAS resolver."""

    @property
    def job_id(self) -> str:
        """Return the selected execution job identity."""
        ...

    @property
    def run_id(self) -> str:
        """Return the selected execution run identity."""
        ...

    @property
    def attempt(self) -> int:
        """Return the selected lease attempt."""
        ...

    @property
    def simulation_result_ref(self) -> ArtifactRef:
        """Return the selected simulation result ref."""
        ...

    @property
    def method_execution_bundle_ref(self) -> ArtifactRef:
        """Return the selected method execution bundle ref."""
        ...

    @property
    def method_metric_binding_set_ref(self) -> ArtifactRef:
        """Return the selected method metric binding set ref."""
        ...

    @property
    def method_result_ref(self) -> ArtifactRef | None:
        """Return the optional selected method result ref."""
        ...


class MethodMetricProjectionStoreResolver(Protocol):
    """Server-owned service that resolves the configured CAS for one fixed work item."""

    def resolve_method_metric_projection_store(
        self,
        *,
        work: MethodMetricProjectionWorkLike,
    ) -> _MethodMetricProjectionArtifactStore | None: ...


class _UnestablishedProjectionError(ValueError):
    """A validly absent source cannot support a selected projection receipt."""


def prepare_method_metric_projection_admission(
    store: _MethodMetricProjectionArtifactStore,
    *,
    source_tuple: _MethodMetricSourceTuple,
) -> MethodMetricProjectionRefOutcome:
    """Verify selected graph execution evidence and stage a v1.2 metric projection.

    The worker accepts no request-supplied labels, decoded arrays, or caller-owned CAS
    root. Its caller resolves the configured store on the server side and submits only
    immutable source references. The returned token is a staged content/law receipt;
    Runtime must still match the complete tuple under the live job fence before it
    associates the projection with a completed run.
    """
    if type(source_tuple) is not _MethodMetricSourceTuple:
        return MethodMetricProjectionRefOutcome(
            status="invalid",
            limitations=("method_metric_source_tuple_type_invalid",),
        )
    if source_tuple.method_result_ref is not None:
        return MethodMetricProjectionRefOutcome(
            status="invalid",
            limitations=("graph_method_metric_projection_cannot_alias_direct_method_result",),
        )
    try:
        read_budget = _ProjectionReadBudget()
        source_candidate_ref = _admit_execution_source_candidate(
            store,
            source_tuple=source_tuple,
            read_budget=read_budget,
        )
        observations = _admit_method_metric_observations(
            store,
            source_tuple=source_tuple,
            read_budget=read_budget,
        )
        if not observations:
            raise _UnestablishedProjectionError("method_metric_binding_set_has_no_bindings")
        vector = PolicyEvaluationVector(
            metadata={
                "projection_kind": "ad01_method_metric_observation_projection",
                "projection_version": "1.0",
                "authority_status": "candidate_only",
                "source_tuple_sha256": _source_tuple_sha256(source_tuple),
                "source_candidate_ref": source_candidate_ref.model_dump(mode="json"),
            },
            method_metric_observations=observations,
        )
        vector_ref = _persist_method_metric_projection(store, vector=vector)
        _verify_staged_method_metric_projection(
            store,
            vector_ref=vector_ref,
            expected_vector=vector,
            source_tuple=source_tuple,
            source_candidate_ref=source_candidate_ref,
            read_budget=read_budget,
        )
        verifier_digest = _verifier_implementation_sha256()
        admission = _VerifiedMethodMetricProjectionAdmission(
            source_tuple=source_tuple,
            source_candidate_ref=source_candidate_ref,
            vector_ref=vector_ref,
            verifier_revision=METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
            verifier_implementation_sha256=verifier_digest,
            _seal=_VERIFIED_METHOD_METRIC_PROJECTION_SEAL,
        )
        return MethodMetricProjectionRefOutcome(status="verified", admission=admission)
    except _UnestablishedProjectionError as exc:
        return MethodMetricProjectionRefOutcome(
            status="verification_missing",
            limitations=(str(exc),),
        )
    except _InvalidProjectionError as exc:
        return MethodMetricProjectionRefOutcome(status="invalid", limitations=(str(exc),))
    except (
        AttributeError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        ValueError,
    ) as exc:
        reason = _bounded_projection_reason(exc)
        return MethodMetricProjectionRefOutcome(status="invalid", limitations=(reason,))


def prepare_method_metric_projection_work(
    *,
    work: MethodMetricProjectionWorkLike,
    resolver: MethodMetricProjectionStoreResolver,
) -> MethodMetricProjectionRefOutcome:
    """Run the fixed refs-only admission step against the server-selected CAS.

    This function does not dispatch work. It snapshots the immutable AD02 descriptor,
    resolves a configured CAS through the server-owned service, and invokes the fixed
    admission verifier once. Callers cannot provide an arbitrary storage root.
    """
    try:
        source_tuple = _MethodMetricSourceTuple(
            job_id=work.job_id,
            run_id=work.run_id,
            attempt=work.attempt,
            method_result_ref=work.method_result_ref,
            simulation_result_ref=work.simulation_result_ref,
            method_execution_bundle_ref=work.method_execution_bundle_ref,
            method_metric_binding_set_ref=work.method_metric_binding_set_ref,
        )
        store = resolver.resolve_method_metric_projection_store(work=work)
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError):
        return MethodMetricProjectionRefOutcome(
            status="invalid",
            limitations=("method_metric_projection_work_or_resolver_invalid",),
        )
    if store is None:
        return MethodMetricProjectionRefOutcome(
            status="verification_missing",
            limitations=("configured_method_metric_projection_store_not_available",),
        )
    return prepare_method_metric_projection_admission(store, source_tuple=source_tuple)


def _admit_execution_source_candidate(
    store: _MethodMetricProjectionArtifactStore,
    *,
    source_tuple: _MethodMetricSourceTuple,
    read_budget: _ProjectionReadBudget,
    comparison_basis_collector: list[Any] | None = None,
) -> SelectedMethodMetricArtifactRef:
    """Derive the source candidate from Foundry's complete bounded basis admission."""
    from polisyos.core.contracts.foundry import SimulationResultRef
    from polisyos.foundry.execute.api import (
        ExecutionSourceAdmissionRefusal,
        ExecutionSourceBoundedReadRefusal,
        admit_execution_source_bounded,
    )

    simulation_ref = _selected_ref(
        source_tuple.simulation_result_ref,
        kind="foundry.simulation_result",
    )
    typed_simulation_ref = SimulationResultRef.model_validate(
        simulation_ref.model_dump(mode="python")
    )
    before = read_budget.observed_execution_source_bytes
    reader = _BoundedExecutionSourceReader(store, read_budget)
    try:
        admission = admit_execution_source_bounded(
            store,
            typed_simulation_ref,
            reader=reader,
        )
    except ExecutionSourceBoundedReadRefusal as exc:
        core_cause = exc.__cause__
        raise _UnestablishedProjectionError(
            "foundry_execution_source_admission_bounded_read_not_established:"
            f"source={reader.last_source_identity!r};"
            f"cause={type(core_cause).__name__ if core_cause is not None else None}:"
            f"{core_cause!s};"
            f"stage={getattr(core_cause, 'failure_stage', None)!r};"
            f"limit={getattr(exc, 'limit_bytes', None)};"
            f"observed={getattr(exc, 'observed_bytes', None)};"
            f"total={read_budget.observed_execution_source_bytes};"
            f"remaining={read_budget.remaining_bytes}"
        ) from exc
    except ExecutionSourceAdmissionRefusal as exc:
        cause: BaseException | None = exc.__cause__
        while cause is not None:
            if isinstance(cause, _UnestablishedProjectionError):
                raise cause
            if isinstance(cause, _InvalidProjectionError):
                raise cause
            cause = cause.__cause__
        raise _InvalidProjectionError(f"foundry_execution_source_admission_refused:{exc}") from exc

    observed_source_bytes = read_budget.observed_execution_source_bytes - before
    if (
        type(admission.source_read_bytes) is not int
        or admission.source_read_bytes != observed_source_bytes
    ):
        raise _InvalidProjectionError("foundry_execution_source_read_accounting_mismatch")
    if admission.mode != "single_step_basis" or admission.basis is None:
        raise _UnestablishedProjectionError(
            "foundry_execution_source_has_no_single_step_candidate_basis"
        )
    if comparison_basis_collector is not None:
        comparison_basis_collector.append(admission.basis)
    try:
        return _selected_ref(
            admission.basis.candidate_ref,
            kind="scientist.policy_design.candidate",
        )
    except (AttributeError, TypeError, ValueError) as exc:
        raise _InvalidProjectionError("foundry_execution_source_candidate_ref_invalid") from exc


def _admit_method_metric_observations(
    store: _MethodMetricProjectionArtifactStore,
    *,
    source_tuple: _MethodMetricSourceTuple,
    read_budget: _ProjectionReadBudget,
    comparison_collector: list[dict[str, Any]] | None = None,
    comparison_candidate: Any | None = None,
) -> tuple[MethodMetricObservation, ...]:
    """Resolve and reconcile the whole selected graph → bundle → binding source chain."""
    from polisyos.core.artifacts.environment import EnvironmentManifest
    from polisyos.core.artifacts.registry import RegistryBundlePayload
    from polisyos.core.contracts.foundry import (
        ExecPlan,
        MethodExecutionBundle,
        MethodMetricBindingSet,
        ProgramGraph,
        SimulationResult,
    )
    from polisyos.foundry.methods.exceptions import MethodNotFoundError
    from polisyos.foundry.methods.selection.registry import MethodRegistry
    from polisyos.ir.kernel.method_metrics import (
        MethodMetricSourceUnit as RegisteredMethodMetricSourceUnit,
    )
    from polisyos.ir.kernel.method_metrics import (
        registered_method_metric_input_unit_contract,
        registered_method_metric_law_metadata_for,
        registered_method_metric_semantics_match,
        registered_method_metric_unit_adapter_metadata,
    )
    from polisyos.ir.kernel.metrics import MetricRegistry
    from polisyos.ir.kernel.units import UnitsRegistry
    from polisyos.ir.trinity import TrinityBundle

    simulation_ref = _selected_ref(
        source_tuple.simulation_result_ref,
        kind="foundry.simulation_result",
    )
    bundle_ref = _selected_ref(
        source_tuple.method_execution_bundle_ref,
        kind="foundry.method_execution_bundle",
    )
    binding_ref = _selected_ref(
        source_tuple.method_metric_binding_set_ref,
        kind="foundry.method_metric_binding_set",
    )

    simulation_manifest, simulation = _load_method_metric_model(
        store,
        ref=simulation_ref,
        model=SimulationResult,
        expected_kind="foundry.simulation_result",
        expected_schema_name="polisyos.core.SimulationResult",
        expected_schema_versions={"1.3", "1.4"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    simulation_schema = simulation_manifest.artifact_schema
    if simulation_schema is None:
        raise _InvalidProjectionError("simulation_result_artifact_schema_missing")
    if simulation.schema_version != simulation_schema.version:
        raise _InvalidProjectionError("simulation_result_payload_schema_version_mismatch")

    _require_exact_manifest_edge(
        simulation_manifest,
        role="method_execution",
        ref=bundle_ref,
    )
    bundle_read = _read_bounded_method_metric_artifact(
        store,
        ref=bundle_ref,
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    bundle_manifest = bundle_read.manifest
    bundle_schema = bundle_manifest.artifact_schema
    if (
        bundle_manifest.kind != "foundry.method_execution_bundle"
        or bundle_manifest.media_type != "application/json"
        or bundle_schema is None
        or bundle_schema.name != "polisyos.core.MethodExecutionBundle"
        or bundle_schema.version not in {"1.0", "1.1"}
    ):
        raise _InvalidProjectionError("selected_method_execution_bundle_schema_invalid")
    if bundle_schema.version == "1.0":
        # The v1.0 contract predates the dispatch-time sparse prestate and full
        # method-metric input capture. Keep it readable as a typed limitation, but
        # never coerce the v1.1 model or treat an adjacent manifest edge as proof.
        raise _UnestablishedProjectionError(
            "legacy_method_execution_bundle_v1_0_lacks_current_prestate_contract"
        )
    bundle = _validate_bounded_method_metric_model(
        MethodExecutionBundle,
        bundle_read,
        expected_kind="foundry.method_execution_bundle",
        expected_schema_name="polisyos.core.MethodExecutionBundle",
        expected_schema_versions={"1.1"},
    )
    _require_exact_payload_ref(bundle.program_graph_ref, kind="foundry.program_graph")
    _require_payload_ref_match(
        bundle.exec_plan_ref,
        simulation.exec_plan_ref,
        reason="simulation_result_exec_plan_payload_mismatch",
    )
    _require_payload_ref_match(
        bundle.method_metric_binding_set_ref,
        binding_ref,
        reason="execution_bundle_binding_payload_mismatch",
    )
    graph_ref = _selected_ref(bundle.program_graph_ref, kind="foundry.program_graph")
    plan_ref = _selected_ref(bundle.exec_plan_ref, kind="foundry.exec_plan")
    _require_exact_manifest_edge(bundle_manifest, role="program_graph", ref=graph_ref)
    _require_exact_manifest_edge(bundle_manifest, role="exec_plan", ref=plan_ref)
    _require_exact_manifest_edge(bundle_manifest, role="method_metric_binding_set", ref=binding_ref)

    environment_ref: SelectedMethodMetricArtifactRef | None = None
    if bundle.environment_manifest_ref is not None:
        environment_ref = _selected_ref(
            bundle.environment_manifest_ref,
            kind="foundry.environment_manifest",
        )
        _require_exact_manifest_edge(
            bundle_manifest,
            role="environment_manifest",
            ref=environment_ref,
        )
    elif any(edge.role == "environment_manifest" for edge in bundle_manifest.inputs):
        raise _InvalidProjectionError("method_metric_bundle_has_unclaimed_environment_manifest")

    plan_manifest, plan = _load_method_metric_model(
        store,
        ref=plan_ref,
        model=ExecPlan,
        expected_kind="foundry.exec_plan",
        expected_schema_name="polisyos.core.ExecPlan",
        expected_schema_versions={"0.2.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _require_payload_ref_match(
        plan.program_ref, graph_ref, reason="exec_plan_program_payload_mismatch"
    )
    _require_exact_manifest_edge(plan_manifest, role="program_graph", ref=graph_ref)
    _require_exact_manifest_edge(
        plan_manifest,
        role="method_metric_bindings",
        ref=binding_ref,
    )
    if simulation_schema.version not in {"1.3", "1.4"}:
        raise _InvalidProjectionError("simulation_result_schema_unsupported")

    binding_manifest, binding_set = _load_method_metric_model(
        store,
        ref=binding_ref,
        model=MethodMetricBindingSet,
        expected_kind="foundry.method_metric_binding_set",
        expected_schema_name="polisyos.core.MethodMetricBindingSet",
        expected_schema_versions={"1.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _require_payload_ref_match(
        binding_set.program_graph_ref,
        graph_ref,
        reason="binding_set_program_graph_payload_mismatch",
    )
    _require_exact_manifest_edge(binding_manifest, role="program_graph", ref=graph_ref)

    policy_ref = _selected_ref(binding_set.policy_ref, kind="ir.trinity_bundle")
    registry_bundle_ref = _selected_ref(
        binding_set.registry_bundle_ref,
        kind="core.registry_bundle",
    )
    metric_registry_ref = _selected_ref(
        binding_set.metric_registry_ref,
        kind="ir.metric_registry",
    )
    units_registry_ref = _selected_ref(
        binding_set.units_registry_ref,
        kind="ir.units_registry",
    )
    _require_exact_manifest_edge(binding_manifest, role="policy", ref=policy_ref)
    _require_exact_manifest_edge(binding_manifest, role="registry_bundle", ref=registry_bundle_ref)
    _require_exact_manifest_edge(binding_manifest, role="metric_registry", ref=metric_registry_ref)
    _require_exact_manifest_edge(binding_manifest, role="units_registry", ref=units_registry_ref)
    _, policy = _load_method_metric_model(
        store,
        ref=policy_ref,
        model=TrinityBundle,
        expected_kind="ir.trinity_bundle",
        expected_schema_name="polisyos.ir.TrinityBundle",
        expected_schema_versions={"1.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    registry_bundle_manifest, registry_bundle = _load_method_metric_model(
        store,
        ref=registry_bundle_ref,
        model=RegistryBundlePayload,
        expected_kind="core.registry_bundle",
        expected_schema_name=None,
        expected_schema_versions=None,
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    if registry_bundle.metric_registry is None or registry_bundle.units_registry is None:
        raise _InvalidProjectionError("registry_bundle_registry_refs_missing")
    _require_payload_ref_match(
        registry_bundle.metric_registry,
        metric_registry_ref,
        reason="registry_bundle_metric_ref_mismatch",
    )
    _require_payload_ref_match(
        registry_bundle.units_registry,
        units_registry_ref,
        reason="registry_bundle_units_ref_mismatch",
    )
    _, metric_registry = _load_method_metric_model(
        store,
        ref=metric_registry_ref,
        model=MetricRegistry,
        expected_kind="ir.metric_registry",
        expected_schema_name="polisyos.ir.kernel.MetricRegistry",
        expected_schema_versions={"1.0", "1.1"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _, units_registry = _load_method_metric_model(
        store,
        ref=units_registry_ref,
        model=UnitsRegistry,
        expected_kind="ir.units_registry",
        expected_schema_name="polisyos.ir.kernel.UnitsRegistry",
        expected_schema_versions={"1.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _require_exact_manifest_edge(
        registry_bundle_manifest,
        role="metric_registry",
        ref=metric_registry_ref,
    )
    _require_exact_manifest_edge(
        registry_bundle_manifest,
        role="units_registry",
        ref=units_registry_ref,
    )

    graph_manifest, graph = _load_method_metric_model(
        store,
        ref=graph_ref,
        model=ProgramGraph,
        expected_kind="foundry.program_graph",
        expected_schema_name="polisyos.core.ProgramGraph",
        expected_schema_versions={"0.2.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _require_payload_ref_match(
        graph.ir_ref,
        policy_ref,
        reason="program_graph_policy_payload_mismatch",
    )
    _require_exact_manifest_edge(graph_manifest, role="ir", ref=policy_ref)
    _require_exact_manifest_edge(graph_manifest, role="registry_bundle", ref=registry_bundle_ref)
    if not graph.nodes:
        raise _UnestablishedProjectionError("selected_program_graph_has_no_method_nodes")
    _validate_execution_capture_order(graph=graph, plan=plan, bundle=bundle)
    comparison_graph: dict[str, Any] | None = None
    if comparison_collector is not None and comparison_candidate is not None:
        if comparison_candidate.trinity_bundle != policy:
            raise _InvalidProjectionError("completed_rank_candidate_trinity_mismatch")
        comparison_graph = _compiled_method_comparison_graph(
            store,
            graph=graph,
            graph_manifest=graph_manifest,
            plan=plan,
            policy=policy,
            policy_ref=policy_ref,
            registry_bundle=registry_bundle,
            registry_bundle_ref=registry_bundle_ref,
            registry_bundle_manifest=registry_bundle_manifest,
            read_budget=read_budget,
        )

    if len(binding_set.bindings) > MAX_METHOD_METRIC_BINDINGS:
        raise _InvalidProjectionError("method_metric_binding_count_exceeds_bounded_admission")
    if len(bundle.occurrences) > MAX_METHOD_EXECUTION_OCCURRENCES:
        raise _InvalidProjectionError("method_execution_occurrence_count_exceeds_bounded_admission")

    objectives = tuple(policy.problem_frame.objectives)
    objective_ids = [objective.objective_id for objective in objectives]
    if len(objective_ids) != len(set(objective_ids)):
        raise _InvalidProjectionError("selected_problem_frame_objective_ids_are_not_unique")
    objective_count = len(objectives)
    verifier_code_digest = _verifier_implementation_sha256()
    registry: MethodRegistry | None = None
    environment_loaded = False
    comparison_environment: dict[str, Any] | None = None
    observations: list[MethodMetricObservation] = []
    for binding in binding_set.bindings:
        objective_rows = [
            objective for objective in objectives if objective.objective_id == binding.objective_id
        ]
        if len(objective_rows) != 1 or objective_rows[0].metric_id != binding.metric_id:
            raise _InvalidProjectionError("method_metric_binding_objective_metric_mismatch")
        objective = objective_rows[0]
        metric = metric_registry.metrics.get(binding.metric_id)
        if metric is None:
            raise _InvalidProjectionError("method_metric_binding_metric_not_in_registry")
        if binding.semantics != metric.method_semantics:
            raise _InvalidProjectionError("method_metric_binding_semantics_registry_mismatch")
        if not metric.unit_id or metric.unit_id not in units_registry.units:
            raise _InvalidProjectionError("method_metric_binding_target_unit_missing")
        target_unit = units_registry.units[metric.unit_id]
        if _canonical_model(binding.target_unit) != _canonical_model(target_unit):
            raise _InvalidProjectionError("method_metric_binding_target_unit_registry_mismatch")

        graph_nodes = [node for node in graph.nodes if node.node_id == binding.node_id]
        if len(graph_nodes) != 1:
            raise _InvalidProjectionError("method_metric_binding_node_not_unique_in_graph")
        graph_node = graph_nodes[0]
        if graph_node.node_kind != "method" or graph_node.method_fqn != binding.method_fqn:
            raise _InvalidProjectionError("method_metric_binding_node_method_mismatch")
        if (
            graph_node.method_version is not None
            and graph_node.method_version != binding.method_version
        ):
            raise _InvalidProjectionError("method_metric_binding_node_version_mismatch")

        occurrences = [
            occurrence for occurrence in bundle.occurrences if occurrence.node_id == binding.node_id
        ]
        if any(
            occurrence.node_kind != "method"
            or (occurrence.method_fqn is not None and occurrence.method_fqn != binding.method_fqn)
            or (
                occurrence.method_version is not None
                and occurrence.method_version != binding.method_version
            )
            or (
                occurrence.method_abi_digest is not None
                and occurrence.method_abi_digest != binding.method_abi_digest
            )
            or (
                occurrence.method_abi_digest_algorithm is not None
                and occurrence.method_abi_digest_algorithm != binding.method_abi_digest_algorithm
            )
            for occurrence in occurrences
        ):
            raise _InvalidProjectionError("method_metric_occurrence_identity_mismatch")

        source_unit = RegisteredMethodMetricSourceUnit.model_validate(
            binding.source_unit.model_dump(mode="python")
        )
        binding_law_identity = (
            binding.law_id,
            binding.law_version,
            binding.law_code_digest,
        )
        binding_adapter_identity = (
            binding.adapter_id,
            binding.adapter_version,
            binding.adapter_code_digest,
        )
        admission = _admit_method_metric_binding(
            binding_availability=binding.availability,
            binding_limitation=binding.limitation,
            binding_semantics=binding.semantics,
            metric_semantics=metric.method_semantics,
            binding_law_identity=binding_law_identity,
            binding_adapter_identity=binding_adapter_identity,
        )

        def append_unobserved_rows(
            *,
            status: Literal["unavailable", "invalid", "not_established"],
            limitation: str,
            current_admission: _MethodMetricBindingAdmission,
            selected_binding: MethodMetricBinding = binding,
            selected_occurrences: tuple[MethodExecutionOccurrence, ...] = tuple(occurrences),
            selected_target_unit: UnitSpecType = target_unit,
            selected_source_unit: RegisteredMethodMetricSourceUnit = source_unit,
        ) -> None:
            rows = selected_occurrences if selected_occurrences else (None,)
            if len(observations) + len(rows) > MAX_METHOD_METRIC_OBSERVATIONS:
                raise _UnestablishedProjectionError(
                    "method_metric_observation_count_exceeds_bounded_admission"
                )
            for occurrence in rows:
                row_status = status if occurrence is not None else "not_established"
                row_limitation = (
                    limitation
                    if occurrence is not None
                    else "selected_graph_contains_no_matching_method_occurrence"
                )
                observations.append(
                    _build_unobserved_method_metric_observation(
                        binding=selected_binding,
                        occurrence=occurrence,
                        environment_ref=environment_ref,
                        target_unit=selected_target_unit,
                        source_unit=selected_source_unit,
                        binding_set_ref=binding_ref,
                        execution_bundle_ref=bundle_ref,
                        simulation_result_ref=simulation_ref,
                        status=row_status,
                        limitation=row_limitation,
                        law_identity=current_admission.law_identity,
                        adapter_identity=current_admission.adapter_identity,
                        verifier_code_digest=verifier_code_digest,
                    )
                )

        if admission.status == "unavailable":
            append_unobserved_rows(
                status="unavailable",
                limitation=admission.limitation or "compiled_method_metric_binding_unavailable",
                current_admission=admission,
            )
            continue
        if admission.status != "requires_positive_validation":
            raise _InvalidProjectionError("method_metric_binding_admission_state_invalid")

        registered_law_identity = registered_method_metric_law_metadata_for(
            binding.method_fqn,
            binding.method_version,
        )
        registered_semantics_match = (
            registered_law_identity is not None
            and registered_method_metric_semantics_match(binding.law_id, binding.semantics)
        )
        registered_adapter_identity = registered_method_metric_unit_adapter_metadata()
        positive_contract = _RegisteredMethodMetricBindingContract(
            law_identity=registered_law_identity,
            semantics_match=registered_semantics_match,
            adapter_identity=registered_adapter_identity,
            input_unit_contract=None,
            actual_input_units=(),
            actual_input_slot_ids=(),
        )
        admission = _admit_method_metric_binding(
            binding_availability=binding.availability,
            binding_limitation=binding.limitation,
            binding_semantics=binding.semantics,
            metric_semantics=metric.method_semantics,
            binding_law_identity=binding_law_identity,
            binding_adapter_identity=binding_adapter_identity,
            positive_contract=positive_contract,
        )

        if registry is None:
            registry = MethodRegistry.get_instance()
        signature = registry.get_signature(binding.method_fqn)
        try:
            method_class = registry.get(binding.method_fqn)
        except MethodNotFoundError:
            method_class = None
        class_signature = None if method_class is None else getattr(method_class, "signature", None)
        if (
            signature is not None
            and class_signature is not None
            and (
                class_signature.fqn != signature.fqn
                or class_signature.version != signature.version
                or class_signature.abi_digest() != signature.abi_digest()
            )
        ):
            raise _InvalidProjectionError("current_method_class_and_registry_signature_disagree")
        if signature is None or class_signature is None or method_class is None:
            append_unobserved_rows(
                status="not_established",
                limitation="current_method_registry_signature_unavailable",
                current_admission=admission,
            )
            continue

        slot = signature.get_output_slot(binding.output_slot_id)
        if (
            signature.version != binding.method_version
            or signature.abi_digest() != binding.method_abi_digest
            or binding.method_abi_digest_algorithm != "blake2b"
            or slot is None
        ):
            raise _InvalidProjectionError("method_metric_current_method_abi_mismatch")

        actual_input_units = tuple(
            sorted(
                [
                    (
                        input_slot.name,
                        RegisteredMethodMetricSourceUnit.model_validate(
                            {
                                "dimension": input_slot.unit.dimension,
                                "symbol": input_slot.unit.symbol,
                                "scale": input_slot.unit.scale,
                            }
                        ),
                    )
                    for input_slot in signature.input_slots
                ],
                key=lambda row: row[0],
            )
        )
        input_unit_contract = registered_method_metric_input_unit_contract(
            binding.law_id,
            binding.semantics,
        )
        output_slot_contract_matches = _registered_method_metric_output_slot_contract_matches(
            binding=binding,
            slot=slot,
            registered_law_identity=registered_law_identity,
            registered_semantics_match=registered_semantics_match,
        )
        positive_contract = _RegisteredMethodMetricBindingContract(
            law_identity=registered_law_identity,
            semantics_match=registered_semantics_match,
            adapter_identity=registered_adapter_identity,
            input_unit_contract=input_unit_contract,
            actual_input_units=actual_input_units,
            actual_input_slot_ids=tuple(
                sorted(input_slot.name for input_slot in signature.input_slots)
            ),
            input_contract_resolved=True,
            output_slot_contract_matches=output_slot_contract_matches,
        )
        admission = _admit_method_metric_binding(
            binding_availability=binding.availability,
            binding_limitation=binding.limitation,
            binding_semantics=binding.semantics,
            metric_semantics=metric.method_semantics,
            binding_law_identity=binding_law_identity,
            binding_adapter_identity=binding_adapter_identity,
            positive_contract=positive_contract,
        )
        if admission.status != "admitted":
            raise _InvalidProjectionError("method_metric_binding_positive_contract_not_admitted")
        law_identity = admission.law_identity
        adapter_identity = admission.adapter_identity
        current_class_source_digest = _method_class_source_sha256(method_class)

        if not occurrences:
            append_unobserved_rows(
                status="not_established",
                limitation="selected_graph_contains_no_matching_method_occurrence",
                current_admission=admission,
            )
            continue
        if environment_ref is None:
            append_unobserved_rows(
                status="not_established",
                limitation="actual_method_environment_manifest_missing",
                current_admission=admission,
            )
            continue
        if not environment_loaded:
            if comparison_collector is None:
                environment_manifest, environment = _load_method_metric_model(
                    store,
                    ref=environment_ref,
                    model=EnvironmentManifest,
                    expected_kind="foundry.environment_manifest",
                    expected_schema_name="polisyos.core.artifacts.environment.EnvironmentManifest",
                    expected_schema_versions={"1.0"},
                    max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
                    read_budget=read_budget,
                )
            else:
                # Read raw fields as well as the typed model: the environment
                # adapter ignores extras, but this bounded comparison must not.
                environment_read = _read_bounded_method_metric_artifact(
                    store,
                    ref=environment_ref,
                    max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
                    read_budget=read_budget,
                )
                environment_manifest = environment_read.manifest
                environment = _validate_bounded_method_metric_model(
                    EnvironmentManifest,
                    environment_read,
                    expected_kind="foundry.environment_manifest",
                    expected_schema_name="polisyos.core.artifacts.environment.EnvironmentManifest",
                    expected_schema_versions={"1.0"},
                )
                raw_environment = json.loads(environment_read.raw_payload_bytes)
                comparison_environment = _ex_ante_comparison_environment(
                    raw_environment,
                    manifest=environment_manifest,
                    plan_ref=plan_ref,
                )
            environment_schema = environment_manifest.artifact_schema
            if environment_schema is None:
                raise _InvalidProjectionError("environment_manifest_artifact_schema_missing")
            if environment.schema_version != environment_schema.version:
                raise _InvalidProjectionError(
                    "environment_manifest_payload_schema_version_mismatch"
                )
            environment_loaded = True

        if occurrences:
            if len(observations) + len(occurrences) > MAX_METHOD_METRIC_OBSERVATIONS:
                raise _UnestablishedProjectionError(
                    "method_metric_observation_count_exceeds_bounded_admission"
                )
            for occurrence in occurrences:
                occurrence_identity_available = (
                    occurrence.method_fqn == binding.method_fqn
                    and occurrence.method_version == binding.method_version
                    and occurrence.method_abi_digest == binding.method_abi_digest
                    and occurrence.method_abi_digest_algorithm == "blake2b"
                )
                occurrence_build_identity_available = (
                    occurrence.method_build_digest_scope == "class_source_only"
                    and occurrence.method_build_digest is not None
                    and current_class_source_digest is not None
                    and occurrence.method_build_digest == current_class_source_digest
                )
                observations.append(
                    _observe_binding_occurrence(
                        store=store,
                        bundle_manifest=bundle_manifest,
                        read_budget=read_budget,
                        binding=binding,
                        occurrence=occurrence,
                        graph_node=graph_node,
                        signature=signature,
                        objective=objective,
                        objective_count=objective_count,
                        metric_unit_id=metric.unit_id,
                        graph_ref=graph_ref,
                        plan_ref=plan_ref,
                        environment_ref=environment_ref,
                        target_unit=target_unit,
                        source_unit=RegisteredMethodMetricSourceUnit.model_validate(
                            binding.source_unit.model_dump(mode="python")
                        ),
                        binding_set_ref=binding_ref,
                        execution_bundle_ref=bundle_ref,
                        simulation_result_ref=simulation_ref,
                        method_registry_available=(
                            signature is not None
                            and class_signature is not None
                            and slot is not None
                        ),
                        occurrence_identity_available=occurrence_identity_available,
                        occurrence_build_identity_available=occurrence_build_identity_available,
                        law_identity=law_identity,
                        adapter_identity=adapter_identity,
                        verifier_code_digest=verifier_code_digest,
                        comparison_collector=comparison_collector,
                        comparison_environment=comparison_environment,
                        comparison_graph=comparison_graph,
                    )
                )
        else:
            observations.append(
                _build_unobserved_method_metric_observation(
                    binding=binding,
                    occurrence=None,
                    environment_ref=environment_ref,
                    target_unit=target_unit,
                    source_unit=RegisteredMethodMetricSourceUnit.model_validate(
                        binding.source_unit.model_dump(mode="python")
                    ),
                    binding_set_ref=binding_ref,
                    execution_bundle_ref=bundle_ref,
                    simulation_result_ref=simulation_ref,
                    status="not_established",
                    limitation="selected_graph_contains_no_matching_method_occurrence",
                    law_identity=law_identity,
                    adapter_identity=adapter_identity,
                    verifier_code_digest=verifier_code_digest,
                )
            )
    return tuple(observations)


def _compiled_method_comparison_graph(
    store: _MethodMetricProjectionArtifactReader,
    *,
    graph: ProgramGraph,
    graph_manifest: ArtifactManifest,
    plan: ExecPlan,
    policy: TrinityBundle,
    policy_ref: SelectedMethodMetricArtifactRef,
    registry_bundle: RegistryBundlePayload,
    registry_bundle_ref: SelectedMethodMetricArtifactRef,
    registry_bundle_manifest: ArtifactManifest,
    read_budget: _ProjectionReadBudget,
) -> dict[str, Any] | None:
    """Reconcile the complete canonical compiler closure before source ref projection."""
    from polisyos.core.contracts.execution_plan import ExecutionPlan
    from polisyos.core.contracts.foundry import LoweredIR, LoweredIRRef
    from polisyos.foundry.compile import replay_method_program_graph
    from polisyos.ir.kernel import ConstraintRegistry

    if sum(node.node_kind == "method" for node in graph.nodes) != 1:
        return None
    if any(item.enabled for item in policy.policy_spec.interventions):
        return None
    source_edges = [edge for edge in graph_manifest.inputs if edge.role == "execution_plan_source"]
    if not source_edges:
        raise _UnestablishedProjectionError("comparison_graph_selected_method_plan_not_established")
    if len(source_edges) != 1 or source_edges[0].manifest_profile_sha256 is None:
        raise _InvalidProjectionError("comparison_graph_selected_method_plan_missing")
    edge = source_edges[0]
    method_plan_ref = _selected_ref(
        ArtifactRef(
            artifact_id=edge.artifact_id,
            kind="scientist.execution_plan",
            media_type="application/json",
            manifest_profile_sha256=edge.manifest_profile_sha256,
        ),
        kind="scientist.execution_plan",
    )
    method_manifest, method_plan = _load_method_metric_model(
        store,
        ref=method_plan_ref,
        model=ExecutionPlan,
        expected_kind="scientist.execution_plan",
        expected_schema_name="polisyos.core.ExecutionPlan",
        expected_schema_versions={"1.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _require_exact_manifest_edge(method_manifest, role="policy_candidate", ref=policy_ref)
    lowered_ref = _selected_ref(graph.lowered_ir_ref, kind="foundry.lowered_ir")
    _require_exact_manifest_edge(graph_manifest, role="lowered_ir", ref=lowered_ref)
    lowered_manifest, lowered = _load_method_metric_model(
        store,
        ref=lowered_ref,
        model=LoweredIR,
        expected_kind="foundry.lowered_ir",
        expected_schema_name="polisyos.foundry.LoweredIR",
        expected_schema_versions={"0.2.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    _require_payload_ref_match(
        lowered.ir_ref, policy_ref, reason="comparison_lowering_policy_mismatch"
    )
    _require_exact_manifest_edge(lowered_manifest, role="ir", ref=policy_ref)
    _require_exact_manifest_edge(lowered_manifest, role="registry_bundle", ref=registry_bundle_ref)
    constraint_ref = _selected_ref(
        registry_bundle.constraint_registry, kind="ir.constraint_registry"
    )
    _require_exact_manifest_edge(
        registry_bundle_manifest, role="constraint_registry", ref=constraint_ref
    )
    _, constraints = _load_method_metric_model(
        store,
        ref=constraint_ref,
        model=ConstraintRegistry,
        expected_kind="ir.constraint_registry",
        expected_schema_name="polisyos.ir.kernel.ConstraintRegistry",
        expected_schema_versions={"1.0"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    try:
        replayed, order = replay_method_program_graph(
            policy=policy,
            policy_ref=_core_artifact_ref(policy_ref),
            lowered_ir=lowered,
            lowered_ir_ref=LoweredIRRef.model_validate(lowered_ref.model_dump(mode="python")),
            method_plan=method_plan,
            constraint_registry=constraints,
        )
    except (TypeError, ValueError) as exc:
        raise _InvalidProjectionError("comparison_canonical_method_graph_replay_failed") from exc
    if graph != replayed or plan.order != order:
        raise _InvalidProjectionError("comparison_canonical_method_graph_or_order_mismatch")
    if (
        plan.policy_fidelity_level != lowered.policy_fidelity_level
        or plan.constraint_mode != lowered.constraint_mode
    ):
        raise _InvalidProjectionError("comparison_exec_plan_lowering_posture_mismatch")
    return {
        "graph": graph.model_dump(mode="json", exclude={"ir_ref", "lowered_ir_ref"}),
        "plan": plan.model_dump(mode="json", exclude={"program_ref"}),
        "lowering": lowered.model_dump(mode="json", exclude={"ir_ref"}),
    }


def _validate_execution_capture_order(
    *, graph: ProgramGraph, plan: ExecPlan, bundle: MethodExecutionBundle
) -> None:
    """Reconcile each captured occurrence against the selected graph and plan position."""
    if len(plan.order) > MAX_METHOD_EXECUTION_OCCURRENCES:
        raise _InvalidProjectionError("selected_exec_plan_order_exceeds_bounded_capture")
    nodes_by_id = {node.node_id: node for node in graph.nodes}
    if len(nodes_by_id) != len(graph.nodes):
        raise _InvalidProjectionError("selected_program_graph_node_ids_are_not_unique")
    if any(node_id not in nodes_by_id for node_id in plan.order):
        raise _InvalidProjectionError("selected_exec_plan_references_unknown_graph_node")

    occurrence_positions: dict[str, set[int]] = {}
    for occurrence in bundle.occurrences:
        if (
            occurrence.plan_index >= len(plan.order)
            or plan.order[occurrence.plan_index] != occurrence.node_id
        ):
            raise _InvalidProjectionError(
                "method_execution_occurrence_does_not_match_selected_plan"
            )
        graph_node = nodes_by_id[occurrence.node_id]
        if occurrence.node_kind != graph_node.node_kind:
            raise _InvalidProjectionError("method_execution_occurrence_kind_disagrees_with_graph")
        occurrence_positions.setdefault(occurrence.invocation_id, set()).add(occurrence.plan_index)

    expected_positions = set(range(len(plan.order)))
    if any(positions != expected_positions for positions in occurrence_positions.values()):
        raise _InvalidProjectionError("method_execution_occurrence_inventory_is_incomplete")


def _selected_returned_slot(
    *,
    occurrence: MethodExecutionOccurrence,
    signature: Any,
    output_slot_id: str,
    expected_value_path: tuple[str, ...],
    selected_value: int | float | None = None,
) -> tuple[MethodExecutionReturnedSlot | None, str | None]:
    """Join a selected scalar capture to its complete ABI return inventory."""
    if occurrence.returned_slot_inventory_status != "captured":
        return (
            None,
            occurrence.returned_slot_inventory_limitation
            or "method_returned_slot_inventory_not_established",
        )

    signature_outputs = {slot.name: slot for slot in signature.output_slots}
    inventory: dict[str, Any] = {}
    for row in occurrence.returned_slots:
        if row.slot_id in inventory:
            raise _InvalidProjectionError("duplicate_returned_method_output_inventory_slot")
        inventory[row.slot_id] = row
    if not set(signature_outputs).issubset(inventory):
        return None, "method_returned_slot_inventory_omits_signature_output"
    for slot_id, signature_slot in signature_outputs.items():
        row = inventory[slot_id]
        if (
            not row.declared_by_signature
            or row.declared_slot_type != _method_signature_slot_type_name(signature_slot.slot_type)
            or row.declared_shape != tuple(str(dimension) for dimension in signature_slot.shape)
        ):
            raise _InvalidProjectionError(
                "returned_method_slot_inventory_disagrees_with_current_method_abi"
            )
    if any(
        row.declared_by_signature
        for slot_id, row in inventory.items()
        if slot_id not in signature_outputs
    ):
        raise _InvalidProjectionError("undeclared_returned_slot_claims_method_signature_membership")

    signature_slot = signature_outputs.get(output_slot_id)
    returned = inventory.get(output_slot_id)
    if signature_slot is None or returned is None:
        return None, "selected_method_output_not_in_complete_return_inventory"
    expected_shape = tuple(str(dimension) for dimension in signature_slot.shape)
    if not returned.declared_by_signature or returned.declared_shape != expected_shape:
        raise _InvalidProjectionError("selected_returned_slot_disagrees_with_current_method_abi")
    if returned.returned != "returned":
        raise _InvalidProjectionError("captured_method_output_disagrees_with_return_inventory")
    if (
        _method_signature_slot_type_name(signature_slot.slot_type) != "SCALAR"
        or signature_slot.shape != ()
    ):
        raise _InvalidProjectionError("selected_method_output_is_not_a_declared_scalar")
    if (
        returned.codec_status != "json_scalar_supported"
        or returned.retention_status != "selected_metric_output"
    ):
        return None, "selected_method_scalar_return_not_fully_captured"
    # Foundry may expose a JSON-valued ABI slot while separately persisting a
    # typed scalar selected through the exact non-empty value path. The caller
    # has already content-read that MethodOutputPayload and matched its path.
    selected_value_is_numeric = selected_value is None or type(selected_value) in {int, float}
    # Direct scalar selection requires the content-read typed value so the
    # persisted owner type claim cannot stand alone.
    direct_scalar_runtime_type_matches = selected_value is not None and (
        (type(selected_value) is int and returned.runtime_type == "builtins.int")
        or (type(selected_value) is float and returned.runtime_type == "builtins.float")
    )
    direct_scalar = (
        not expected_value_path
        and selected_value_is_numeric
        and direct_scalar_runtime_type_matches
        and returned.runtime_shape_status == "captured"
        and returned.runtime_shape == ()
    )
    selected_json_member = (
        bool(expected_value_path)
        and selected_value_is_numeric
        and returned.runtime_type == "builtins.dict"
        and _is_exact_json_result_container_unit(getattr(signature_slot, "unit", None))
        and returned.runtime_shape_status == "not_established"
        and returned.runtime_shape is None
    )
    if not (direct_scalar or selected_json_member):
        return None, "selected_method_scalar_return_not_fully_captured"
    return returned, None


def _registered_method_metric_output_slot_contract_matches(
    *,
    binding: MethodMetricBinding,
    slot: Any,
    registered_law_identity: tuple[str, str, str] | None,
    registered_semantics_match: bool,
) -> bool:
    """Join the current ABI container to the exact registered metric law."""
    return (
        registered_law_identity is not None
        and (binding.law_id, binding.law_version, binding.law_code_digest)
        == registered_law_identity
        and registered_semantics_match
        and binding.semantics is not None
        and binding.output_shape == "scalar"
        and _method_signature_slot_type_name(slot.slot_type) == "SCALAR"
        and slot.shape == ()
        and slot.contract_id == binding.output_contract_id
        and tuple(binding.output_value_path) == tuple(binding.semantics.output_value_path)
        # The registered law selects a numeric child from this exact JSON
        # result container. Its ABI unit differs from the selected metric unit.
        and _is_exact_json_result_container_unit(slot.unit)
    )


def _is_exact_json_result_container_unit(unit: Any) -> bool:
    """Recognize the selected method ABI's exact JSON container unit."""
    return (
        getattr(unit, "dimension", None) == "result"
        and getattr(unit, "symbol", None) == "json"
        and getattr(unit, "scale", None) == 1.0
    )


def _method_signature_slot_type_name(slot_type: object) -> str | None:
    """Use the stable enum-name representation persisted by Foundry's owner."""
    name = getattr(slot_type, "name", None)
    return name if type(name) is str and name else None


def _same_method_metric_source_unit(
    left: MethodMetricSourceUnit,
    right: MethodMetricSourceUnit,
) -> bool:
    """Compare exact unit identity without confusing numeric representation with meaning."""
    return (
        left.dimension == right.dimension
        and left.symbol == right.symbol
        and type(left.scale) in {int, float}
        and type(right.scale) in {int, float}
        and left.scale == right.scale
    )


def _search_method_metric_source_unit(
    source_unit: MethodMetricSourceUnit,
) -> SearchMethodMetricSourceUnit:
    """Convert the IR-owned source unit through the Search observation schema."""
    return SearchMethodMetricSourceUnit.model_validate(source_unit.model_dump(mode="python"))


def _method_metric_execution_context(
    *,
    occurrence: MethodExecutionOccurrence,
    graph_node: Any,
    signature: Any,
    semantics: MethodMetricSemanticContract,
    expected_method_fqn: str,
    expected_method_version: str,
    expected_method_abi_digest: str,
    expected_method_abi_digest_algorithm: str,
    expected_output_slot_id: str,
    expected_output_value_path: tuple[str, ...],
) -> tuple[Any | None, str | None]:
    """Reconcile captured dispatch with the selected graph, current ABI, and metric roles."""
    from polisyos.ir.kernel.method_metrics import (
        MethodMetricBackendAttempt,
        MethodMetricExecutionContext,
        MethodMetricInputContext,
        MethodMetricInputRoleContext,
        MethodMetricParameterContext,
    )

    dispatch = occurrence.dispatch
    if dispatch is None:
        return None, "method_dispatch_record_missing"
    method_fqn = occurrence.method_fqn
    method_version = occurrence.method_version
    method_abi_digest = occurrence.method_abi_digest
    method_abi_digest_algorithm = occurrence.method_abi_digest_algorithm
    if (
        method_fqn is None
        or method_version is None
        or method_abi_digest is None
        or method_abi_digest_algorithm is None
    ):
        raise _InvalidProjectionError("method_execution_current_abi_identity_mismatch")
    signature_input_slot_ids = tuple(sorted(slot.name for slot in signature.input_slots))
    signature_output_slot_ids = tuple(sorted(slot.name for slot in signature.output_slots))
    signature_parameter_names = tuple(sorted(parameter.name for parameter in signature.parameters))
    if (
        method_fqn != expected_method_fqn
        or method_version != expected_method_version
        or method_abi_digest != expected_method_abi_digest
        or method_abi_digest_algorithm != expected_method_abi_digest_algorithm
        or signature.fqn != expected_method_fqn
        or signature.version != expected_method_version
        or signature.abi_digest() != expected_method_abi_digest
        or expected_method_abi_digest_algorithm != "blake2b"
    ):
        raise _InvalidProjectionError("method_execution_current_abi_identity_mismatch")
    if dispatch.graph_input_ids != tuple(graph_node.inputs):
        raise _InvalidProjectionError("method_dispatch_graph_inputs_disagree_with_selected_graph")
    if dispatch.signature_input_slot_ids != signature_input_slot_ids:
        raise _InvalidProjectionError("method_dispatch_input_signature_inventory_mismatch")
    if dispatch.signature_parameter_names != signature_parameter_names:
        raise _InvalidProjectionError("method_dispatch_parameter_signature_inventory_mismatch")

    input_rows = {row.slot_id: row for row in dispatch.input_slot_values}
    if len(input_rows) != len(dispatch.input_slot_values):
        raise _InvalidProjectionError("duplicate_method_dispatch_input_slot_identity")
    if set(input_rows) != set(signature_input_slot_ids):
        return None, "method_dispatch_input_slot_inventory_not_established"
    input_value_contexts: list[MethodMetricInputContext] = []
    for slot_id in signature_input_slot_ids:
        row = input_rows[slot_id]
        if row.status == "captured":
            value_sha256 = row.value_sha256
            if value_sha256 is None:
                raise _InvalidProjectionError("captured_method_dispatch_input_digest_missing")
            input_value_contexts.append(
                MethodMetricInputContext(
                    method_input_slot_id=slot_id,
                    status="captured",
                    value_sha256=value_sha256,
                )
            )
        else:
            input_value_contexts.append(
                MethodMetricInputContext(
                    method_input_slot_id=slot_id,
                    status="not_established",
                    value_sha256=None,
                )
            )
    input_values = tuple(input_value_contexts)

    requested_parameters = graph_node.method_params
    parameter_specs = {parameter.name: parameter for parameter in signature.parameters}
    if not isinstance(requested_parameters, Mapping) or any(
        type(name) is not str for name in requested_parameters
    ):
        raise _InvalidProjectionError("selected_graph_method_parameters_invalid")
    expected_parameter_names = set(parameter_specs) | set(requested_parameters)
    parameter_rows = {row.name: row for row in dispatch.parameter_values}
    if len(parameter_rows) != len(dispatch.parameter_values):
        raise _InvalidProjectionError("duplicate_method_dispatch_parameter_identity")
    if set(parameter_rows) != expected_parameter_names:
        return None, "method_dispatch_effective_parameter_inventory_not_established"
    parameter_contexts = []
    for name in sorted(expected_parameter_names):
        row = parameter_rows[name]
        if name in parameter_specs:
            expected_source = "requested" if name in requested_parameters else "signature_default"
            expected_value = (
                requested_parameters[name]
                if name in requested_parameters
                else parameter_specs[name].default
            )
        else:
            expected_source = "requested_unresolved"
            expected_value = None
        if row.source != expected_source:
            raise _InvalidProjectionError("method_dispatch_parameter_provenance_mismatch")
        if row.status == "captured" and expected_source != "requested_unresolved":
            try:
                encoded = json.dumps(
                    expected_value,
                    ensure_ascii=False,
                    allow_nan=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            except (TypeError, ValueError, OverflowError, RecursionError):
                return None, "method_effective_parameter_value_not_recomputable"
            if (
                len(encoded) > 262144
                or row.value != json.loads(encoded)
                or row.value_sha256 != hashlib.sha256(encoded).hexdigest()
            ):
                raise _InvalidProjectionError("method_dispatch_effective_parameter_value_mismatch")
        parameter_contexts.append(
            MethodMetricParameterContext(
                name=name,
                source=row.source,
                status=(
                    "captured"
                    if row.status == "captured" and row.source != "requested_unresolved"
                    else "unsupported_codec"
                ),
                value_sha256=(
                    row.value_sha256
                    if row.status == "captured" and row.source != "requested_unresolved"
                    else None
                ),
            )
        )

    input_role_rows: list[MethodMetricInputRoleContext] = []
    for role in semantics.input_roles:
        input_slot = input_rows.get(role.method_input_slot_id)
        if input_slot is not None and input_slot.status == "captured":
            value_sha256 = input_slot.value_sha256
            if value_sha256 is None:
                raise _InvalidProjectionError("captured_method_dispatch_role_digest_missing")
            input_role_rows.append(
                MethodMetricInputRoleContext(
                    role_id=role.role_id,
                    method_input_slot_id=role.method_input_slot_id,
                    value_sha256=value_sha256,
                )
            )

    dispatch_seed_status = dispatch.seed_status
    if dispatch_seed_status == "reconciled":
        seed_status: Literal["reconciled", "mismatch", "not_established"] = "reconciled"
    elif dispatch_seed_status == "mismatch":
        seed_status = "mismatch"
    else:
        seed_status = "not_established"
    dispatch_backend_status = dispatch.backend_identity_status
    if dispatch_backend_status == "reconciled":
        backend_status: Literal["reconciled", "mismatch", "not_established"] = "reconciled"
    elif dispatch_backend_status == "mismatch":
        backend_status = "mismatch"
    else:
        backend_status = "not_established"
    prestate_captured = dispatch.input_state_status == "captured"
    return MethodMetricExecutionContext(
        dispatch_outcome=dispatch.outcome,
        method_fqn=method_fqn,
        method_version=method_version,
        method_abi_digest=method_abi_digest,
        method_abi_digest_algorithm=method_abi_digest_algorithm,
        method_build_digest=occurrence.method_build_digest,
        method_build_digest_scope=(occurrence.method_build_digest_scope or "unavailable"),
        output_slot_id=expected_output_slot_id,
        output_value_path=expected_output_value_path,
        started_at=dispatch.started_at,
        completed_at=dispatch.completed_at,
        dispatch_elapsed_ms=dispatch.dispatch_elapsed_ms,
        runner_wall_time_ms=dispatch.runner_wall_time_ms,
        runner_cpu_time_ms=dispatch.runner_cpu_time_ms,
        runner_compile_time_ms=dispatch.runner_compile_time_ms,
        graph_input_ids=dispatch.graph_input_ids,
        signature_input_slot_ids=signature_input_slot_ids,
        signature_output_slot_ids=signature_output_slot_ids,
        signature_parameter_names=signature_parameter_names,
        parameter_resolution_status=(
            "captured" if dispatch.parameter_resolution_status == "captured" else "not_established"
        ),
        parameter_values=tuple(parameter_contexts),
        prestate_identity_status="captured" if prestate_captured else "not_established",
        prestate_identity_sha256=(
            dispatch.input_state_identity_sha256 if prestate_captured else None
        ),
        input_slot_values=input_values,
        input_role_values=tuple(input_role_rows),
        seed_status=seed_status,
        root_seed=dispatch.root_seed,
        step=dispatch.step,
        method_seed=dispatch.method_seed,
        reproducibility_seed=dispatch.reproducibility_seed,
        method_key_words=dispatch.method_key_words,
        rng_state_status=(
            "key_captured"
            if dispatch.rng_state_status == "key_captured"
            else "runner_rng_state_not_retained"
        ),
        requested_backend=dispatch.requested_backend,
        selected_backend=dispatch.selected_backend,
        backend_selection_reason=dispatch.backend_selection_reason,
        backend_trace_status=(
            dispatch.backend_trace_status
            if dispatch.backend_trace_status in {"captured", "not_established", "not_started"}
            else "not_established"
        ),
        backend_attempts=tuple(
            MethodMetricBackendAttempt.model_validate(item.model_dump(mode="python"))
            for item in dispatch.backend_attempts
        ),
        fallback_status=(
            dispatch.fallback_status
            if dispatch.fallback_status
            in {"fell_back", "not_fell_back", "not_established", "not_started"}
            else "not_established"
        ),
        backend_identity_status=backend_status,
        actual_backend=(dispatch.actual_backend if backend_status == "reconciled" else None),
    ), None


def _objective_spec_direction(objective: Any) -> str:
    """Return the exact selected IR objective direction spelling."""
    direction = getattr(objective, "direction", None)
    return str(getattr(direction, "value", direction))


def _objective_spec_weight(objective: Any) -> str:
    """Preserve the selected IR objective weight as a canonical decimal string."""
    weight = getattr(objective, "weight", None)
    return str(weight)


def _objective_spec_sha256(objective: Any) -> str:
    """Hash the complete typed objective spec, including target and attached KPI refs."""
    if not isinstance(objective, BaseModel):
        raise _InvalidProjectionError("selected_problem_frame_objective_is_not_typed")
    return _canonical_sha256(objective.model_dump(mode="json"))


def _objective_spec_target_sha256(objective: Any) -> str | None:
    """Hash an explicitly present target without assigning target semantics."""
    if not isinstance(objective, BaseModel):
        raise _InvalidProjectionError("selected_problem_frame_objective_is_not_typed")
    target = objective.model_dump(mode="json").get("target")
    return None if target is None else _canonical_sha256({"target": target})


def _method_dispatch_input_map_sha256(
    arrays: tuple[tuple[str, Any], ...],
) -> str:
    """Recompute the producer's sparse dispatch-input identity from decoded bytes."""
    digest = hashlib.sha256()
    digest.update(b"policyos.method_dispatch_input_map.sha256.v1\0")
    slot_ids = tuple(slot_id for slot_id, _ in arrays)
    if len(slot_ids) != len(set(slot_ids)) or not arrays:
        raise _InvalidProjectionError("method_dispatch_input_map_slot_inventory_invalid")
    for slot_id, array in sorted(arrays, key=lambda item: item[0]):
        if (
            type(slot_id) is not str
            or not slot_id
            or getattr(array, "ndim", None) != 1
            or getattr(getattr(array, "dtype", None), "kind", None) not in {"i", "u", "f"}
        ):
            raise _InvalidProjectionError("method_dispatch_input_map_array_contract_invalid")
        dtype = array.dtype.str
        shape = tuple(int(value) for value in array.shape)
        if not shape or shape[0] <= 0:
            raise _InvalidProjectionError("method_dispatch_input_map_array_shape_invalid")
        raw = array.tobytes(order="C")
        components = (
            slot_id.encode("utf-8"),
            dtype.encode("ascii"),
            json.dumps(shape, separators=(",", ":")).encode("ascii"),
            raw,
        )
        for component in components:
            digest.update(len(component).to_bytes(8, "big", signed=False))
            digest.update(component)
    return digest.hexdigest()


def _method_dispatch_input_slot_sha256(array: Any) -> str:
    """Recompute the producer's per-slot digest from exact selected array bytes."""
    dtype = array.dtype.str
    shape = tuple(int(value) for value in array.shape)
    digest = hashlib.sha256()
    digest.update(dtype.encode("ascii"))
    digest.update(json.dumps(shape, separators=(",", ":")).encode("ascii"))
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def _captured_input_arrays_from_snapshot(
    *,
    store: _MethodMetricProjectionArtifactStore,
    read_budget: _ProjectionReadBudget,
    snapshot_ref: ArtifactRef,
    origin_state_ref: ArtifactRef | None,
    capture: Any,
    dispatch: Any,
    signature: Any,
) -> tuple[tuple[Any, ...], str]:
    """Resolve and independently bind every captured method input to its prestate."""
    from polisyos.core.contracts.foundry import StateSnapshot, StateSnapshotRef
    from polisyos.foundry.execute import (
        StateSnapshotInputReadRefusal,
        read_state_snapshot_inputs_bounded,
    )
    from polisyos.ir.kernel.method_metrics import MethodMetricCapturedInputArray

    capture_rows = {item.slot_id: item for item in capture.slots}
    signature_slot_ids = tuple(sorted(slot.name for slot in signature.input_slots))
    dispatch_slot_rows = {item.slot_id: item for item in dispatch.input_slot_values}
    if (
        len(capture_rows) != len(capture.slots)
        or len(dispatch_slot_rows) != len(dispatch.input_slot_values)
        or set(capture_rows) != set(signature_slot_ids)
        or set(dispatch_slot_rows) != set(signature_slot_ids)
        or tuple(sorted(dispatch.signature_input_slot_ids)) != signature_slot_ids
    ):
        raise _UnestablishedProjectionError(
            "method_metric_current_prestate_input_inventory_not_established"
        )

    remaining = read_budget.remaining_bytes
    if remaining < 6:
        raise _UnestablishedProjectionError(
            "method_metric_current_prestate_exceeds_bounded_admission"
        )
    # The bounded snapshot reader consumes two selected manifests, each once
    # for parsing and once for digest-bound member opening, plus the snapshot
    # JSON and NPZ member bytes. Divide one aggregate allowance across those
    # six physical components before permitting the reader to inflate arrays.
    manifest_limit = min(MAX_METHOD_METRIC_MANIFEST_BYTES, max(1, remaining // 8))
    payload_remaining = remaining - 4 * manifest_limit
    snapshot_payload_limit = min(MAX_METHOD_METRIC_SOURCE_BYTES, max(1, payload_remaining // 2))
    state_blob_limit = min(
        MAX_METHOD_METRIC_SOURCE_BYTES,
        payload_remaining - snapshot_payload_limit,
    )
    if state_blob_limit < 1:
        raise _UnestablishedProjectionError(
            "method_metric_current_prestate_exceeds_bounded_admission"
        )
    try:
        typed_snapshot_ref = StateSnapshotRef.model_validate(snapshot_ref.model_dump(mode="python"))
        bounded = read_state_snapshot_inputs_bounded(
            store,
            snapshot_ref=typed_snapshot_ref,
            slot_ids=signature_slot_ids,
            max_manifest_bytes=manifest_limit,
            max_snapshot_payload_bytes=snapshot_payload_limit,
            max_state_blob_bytes=state_blob_limit,
            # Foundry uses this independent ceiling for snapshot JSON structure too;
            # the NPZ reader separately requires the exact selected slot inventory.
            max_entries=32,
            max_elements=MAX_METHOD_METRIC_READ_ELEMENTS,
        )
    except StateSnapshotInputReadRefusal as exc:
        observed_source_bytes = getattr(exc, "observed_source_bytes", None)
        usage = getattr(exc, "usage", None)
        if type(observed_source_bytes) is not int or observed_source_bytes < 0:
            raise _UnestablishedProjectionError(
                "method_metric_current_prestate_transfer_accounting_not_established"
            ) from exc
        if usage is None or getattr(usage, "observed_source_bytes", None) != observed_source_bytes:
            raise _UnestablishedProjectionError(
                "method_metric_current_prestate_transfer_accounting_not_established"
            ) from exc
        read_budget.account_refused_execution_source_bytes(observed_source_bytes)
        reason = exc.reason if type(exc.reason) is str and exc.reason else "unreported_refusal"
        observed = exc.observed_bytes if type(exc.observed_bytes) is int else "unmeasured"
        limit = exc.limit_bytes if type(exc.limit_bytes) is int else "unmeasured"
        raise _UnestablishedProjectionError(
            "method_metric_current_prestate_bounded_read_refused:"
            f"{reason}:observed={observed}:limit={limit}"
        ) from exc

    observed_source_bytes = getattr(bounded, "observed_source_bytes", None)
    if type(observed_source_bytes) is not int or observed_source_bytes < 0:
        raise _UnestablishedProjectionError(
            "method_metric_current_prestate_transfer_accounting_not_established"
        )
    read_budget.account_execution_source_bytes(observed_source_bytes)
    usage = getattr(bounded, "usage", None)
    if usage is None or getattr(usage, "observed_source_bytes", None) != observed_source_bytes:
        raise _InvalidProjectionError("method_metric_current_prestate_transfer_receipt_mismatch")
    if (
        getattr(bounded, "payload_integrity_verified", None) is not True
        or getattr(bounded, "snapshot_payload_integrity_verified", None) is not True
        or getattr(bounded, "state_blob_payload_integrity_verified", None) is not True
    ):
        raise _UnestablishedProjectionError(
            "method_metric_current_prestate_integrity_not_established"
        )
    if (
        _ref_key(bounded.snapshot_ref) != _ref_key(snapshot_ref)
        or bounded.snapshot.schema_version != StateSnapshot.METHOD_INPUT_SCHEMA_VERSION
        or bounded.state_blob_ref.kind != "foundry.state_blob"
        or bounded.state_blob_ref.media_type != "application/x-npz"
        or len(bounded.arrays) != len(signature_slot_ids)
        or bounded.observed_entries != len(signature_slot_ids)
        or bounded.observed_elements > MAX_METHOD_METRIC_READ_ELEMENTS
    ):
        raise _InvalidProjectionError("method_metric_current_prestate_snapshot_mismatch")
    origin_edges = [
        edge for edge in bounded.snapshot_manifest.inputs if edge.role == "dispatch_origin_state"
    ]
    if origin_state_ref is None:
        if origin_edges:
            raise _InvalidProjectionError("method_metric_snapshot_has_unclaimed_dispatch_origin")
    else:
        _require_exact_manifest_edge(
            bounded.snapshot_manifest,
            role="dispatch_origin_state",
            ref=_selected_ref(origin_state_ref, kind="foundry.state_snapshot"),
        )

    arrays = tuple(bounded.arrays)
    if tuple(slot_id for slot_id, _ in arrays) != signature_slot_ids:
        raise _InvalidProjectionError("method_metric_current_prestate_slot_order_mismatch")
    recomputed_map_digest = _method_dispatch_input_map_sha256(arrays)
    if (
        dispatch.input_state_identity_algorithm != "policyos.method_dispatch_input_map.sha256.v1"
        or capture.prestate_identity_algorithm != "policyos.method_dispatch_input_map.sha256.v1"
        or dispatch.input_state_identity_sha256 != recomputed_map_digest
        or capture.prestate_identity_sha256 != recomputed_map_digest
    ):
        raise _InvalidProjectionError("method_metric_current_prestate_content_identity_mismatch")

    captured_arrays: list[Any] = []
    for slot_id, array in arrays:
        capture_row = capture_rows[slot_id]
        dispatch_row = dispatch_slot_rows[slot_id]
        if (
            capture_row.dtype != array.dtype.str
            or tuple(capture_row.shape) != tuple(int(value) for value in array.shape)
            or capture_row.value_sha256 != _method_dispatch_input_slot_sha256(array)
            or dispatch_row.status != "captured"
            or dispatch_row.value_sha256 != capture_row.value_sha256
        ):
            raise _InvalidProjectionError("method_metric_current_prestate_slot_content_mismatch")
        values = tuple(array.tolist())
        if any(type(value) not in {int, float} for value in values) or any(
            isinstance(value, float) and not math.isfinite(value) for value in values
        ):
            raise _UnestablishedProjectionError(
                "method_metric_current_prestate_numeric_values_not_established"
            )
        captured_arrays.append(
            MethodMetricCapturedInputArray(
                slot_id=slot_id,
                dtype=array.dtype.str,
                shape=tuple(int(value) for value in array.shape),
                values=values,
                value_sha256=capture_row.value_sha256,
                unit=capture_row.unit,
            )
        )
    return tuple(captured_arrays), recomputed_map_digest


def _observe_binding_occurrence(
    *,
    store: _MethodMetricProjectionArtifactStore,
    bundle_manifest: ArtifactManifest,
    read_budget: _ProjectionReadBudget,
    binding: MethodMetricBinding,
    occurrence: MethodExecutionOccurrence,
    graph_node: Any,
    signature: Any,
    objective: Any,
    objective_count: int,
    metric_unit_id: str,
    graph_ref: SelectedMethodMetricArtifactRef,
    plan_ref: SelectedMethodMetricArtifactRef,
    environment_ref: SelectedMethodMetricArtifactRef | None,
    target_unit: UnitSpecType,
    source_unit: MethodMetricSourceUnit,
    binding_set_ref: SelectedMethodMetricArtifactRef,
    execution_bundle_ref: SelectedMethodMetricArtifactRef,
    simulation_result_ref: SelectedMethodMetricArtifactRef,
    method_registry_available: bool,
    occurrence_identity_available: bool,
    occurrence_build_identity_available: bool,
    law_identity: tuple[str, str, str],
    adapter_identity: tuple[str, str, str],
    verifier_code_digest: str,
    comparison_collector: list[dict[str, Any]] | None = None,
    comparison_environment: dict[str, Any] | None = None,
    comparison_graph: dict[str, Any] | None = None,
) -> MethodMetricObservation:
    """Build one occurrence row, retaining typed non-observation reasons."""
    from polisyos.core.contracts.foundry import (
        MethodMetricInputCapturePayload,
        MethodOutputPayload,
    )

    if occurrence.status != "succeeded":
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="unavailable",
            limitation=f"method_occurrence_{occurrence.status}",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    semantics = binding.semantics
    if semantics is None:
        raise _InvalidProjectionError("admitted_method_metric_binding_semantics_missing")
    dispatch = occurrence.dispatch
    if dispatch is None or dispatch.outcome != "succeeded":
        raise _InvalidProjectionError("successful_method_occurrence_dispatch_mismatch")
    prestate_source_ref: ArtifactRef | None = None
    if dispatch.input_state_source_ref is not None:
        prestate_source_ref = _selected_ref(
            dispatch.input_state_source_ref,
            kind="foundry.state_snapshot",
        )
        _require_exact_manifest_edge(
            bundle_manifest,
            role=f"method_prestate_source:{occurrence.occurrence_id}",
            ref=prestate_source_ref,
        )
    elif any(
        edge.role == f"method_prestate_source:{occurrence.occurrence_id}"
        for edge in bundle_manifest.inputs
    ):
        raise _InvalidProjectionError("method_metric_bundle_has_unclaimed_dispatch_origin")
    if (
        dispatch.input_state_status != "captured"
        or dispatch.input_state_ref is None
        or dispatch.input_state_relation != "current_visible_state"
        or dispatch.input_state_identity_algorithm != "policyos.method_dispatch_input_map.sha256.v1"
    ):
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="current_visible_method_dispatch_prestate_not_established",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    input_state_ref = _selected_ref(
        dispatch.input_state_ref,
        kind="foundry.state_snapshot",
    )
    _require_exact_manifest_edge(
        bundle_manifest,
        role=f"method_prestate:{occurrence.occurrence_id}",
        ref=input_state_ref,
    )
    if signature is None:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="current_method_registry_signature_unavailable",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )

    output_rows = [row for row in occurrence.output_slots if row.slot_id == binding.output_slot_id]
    if len(output_rows) != 1:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="selected_output_slot_not_recorded_for_occurrence",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    output_slot = output_rows[0]
    output_ref: SelectedMethodMetricArtifactRef | None = None
    output_payload: MethodOutputPayload | None = None
    if output_slot.status == "captured":
        output_ref = _selected_ref(output_slot.output_ref, kind="foundry.method_output")
        _require_exact_manifest_edge(
            bundle_manifest,
            role=f"method_output:{occurrence.occurrence_id}:{binding.output_slot_id}",
            ref=output_ref,
        )
        output_manifest, selected_output_payload = _load_method_metric_model(
            store,
            ref=output_ref,
            model=MethodOutputPayload,
            expected_kind="foundry.method_output",
            expected_schema_name="polisyos.core.MethodOutputPayload",
            expected_schema_versions={"1.0"},
            max_bytes=1024 * 1024,
            read_budget=read_budget,
        )
        output_payload = selected_output_payload
        if (
            output_payload.occurrence_id != occurrence.occurrence_id
            or output_payload.invocation_id != occurrence.invocation_id
            or output_payload.node_id != occurrence.node_id
            or output_payload.slot_id != binding.output_slot_id
            or tuple(output_payload.value_path) != tuple(binding.output_value_path)
            or output_manifest.artifact_schema is None
            or output_manifest.artifact_schema.version != output_payload.schema_version
        ):
            raise _InvalidProjectionError("selected_method_output_payload_identity_mismatch")
    elif output_slot.output_ref is not None:
        raise _InvalidProjectionError("uncaptured_method_output_has_payload_ref")

    if output_slot.status != "captured":
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=None,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="unavailable",
            limitation=output_slot.limitation or f"method_output_{output_slot.status}",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )

    if output_payload is None:
        raise _InvalidProjectionError("captured_method_output_payload_missing")

    returned_slot, returned_slot_limitation = _selected_returned_slot(
        occurrence=occurrence,
        signature=signature,
        output_slot_id=binding.output_slot_id,
        expected_value_path=tuple(binding.output_value_path),
        selected_value=output_payload.value,
    )
    if returned_slot_limitation is not None:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation=returned_slot_limitation,
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    if returned_slot is None:
        raise _InvalidProjectionError("selected_method_return_inventory_inconsistent")

    if environment_ref is None:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=None,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="actual_method_environment_manifest_missing",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    if not method_registry_available:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="current_method_registry_signature_unavailable",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    if not occurrence_identity_available:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="actual_method_abi_identity_missing_from_occurrence",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    if not occurrence_build_identity_available:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation="actual_method_class_source_identity_not_reconciled",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )

    if dispatch.method_metric_input_capture_status != "captured" or (
        dispatch.method_metric_input_capture_ref is None
    ):
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation=(
                dispatch.method_metric_input_capture_limitation
                or "registered_method_metric_input_capture_not_established"
            ),
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    input_capture_ref = _selected_ref(
        dispatch.method_metric_input_capture_ref,
        kind="foundry.method_metric_input_capture",
    )
    _require_exact_manifest_edge(
        bundle_manifest,
        role=f"method_metric_input_capture:{occurrence.occurrence_id}",
        ref=input_capture_ref,
    )
    input_capture_manifest, input_capture = _load_method_metric_model(
        store,
        ref=input_capture_ref,
        model=MethodMetricInputCapturePayload,
        expected_kind="foundry.method_metric_input_capture",
        expected_schema_name="polisyos.core.MethodMetricInputCapture",
        expected_schema_versions={"1.1"},
        max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
        read_budget=read_budget,
    )
    input_capture_schema = input_capture_manifest.artifact_schema
    if input_capture_schema is None:
        raise _InvalidProjectionError("method_metric_input_capture_artifact_schema_missing")
    if input_capture.schema_version != input_capture_schema.version:
        raise _InvalidProjectionError("method_metric_input_capture_schema_version_mismatch")
    _require_payload_ref_match(
        input_capture.program_graph_ref,
        graph_ref,
        reason="method_metric_input_capture_graph_mismatch",
    )
    _require_payload_ref_match(
        input_capture.exec_plan_ref,
        plan_ref,
        reason="method_metric_input_capture_plan_mismatch",
    )
    _require_payload_ref_match(
        input_capture.method_metric_binding_set_ref,
        binding_set_ref,
        reason="method_metric_input_capture_binding_set_mismatch",
    )
    _require_payload_ref_match(
        input_capture.pre_dispatch_state_ref,
        input_state_ref,
        reason="method_metric_input_capture_prestate_ref_mismatch",
    )
    _require_exact_manifest_edge(
        input_capture_manifest,
        role="pre_dispatch_state",
        ref=input_state_ref,
    )
    if (
        input_capture.occurrence_id != occurrence.occurrence_id
        or input_capture.invocation_id != occurrence.invocation_id
        or input_capture.node_id != occurrence.node_id
        or dispatch.input_state_identity_sha256 is None
        or input_capture.prestate_identity_algorithm
        != "policyos.method_dispatch_input_map.sha256.v1"
        or input_capture.prestate_identity_sha256 != dispatch.input_state_identity_sha256
    ):
        raise _InvalidProjectionError("method_metric_input_capture_identity_mismatch")

    captured_input_values, recomputed_prestate_identity_sha256 = (
        _captured_input_arrays_from_snapshot(
            store=store,
            read_budget=read_budget,
            snapshot_ref=input_state_ref,
            origin_state_ref=prestate_source_ref,
            capture=input_capture,
            dispatch=dispatch,
            signature=signature,
        )
    )

    from polisyos.ir.kernel.method_metrics import (
        apply_registered_ex_ante_mean_change_law,
        apply_registered_method_metric_unit_adapter,
        resolve_registered_method_metric_unit_adapter,
    )

    execution_context, context_limitation = _method_metric_execution_context(
        occurrence=occurrence,
        graph_node=graph_node,
        signature=signature,
        semantics=semantics,
        expected_method_fqn=binding.method_fqn,
        expected_method_version=binding.method_version,
        expected_method_abi_digest=binding.method_abi_digest,
        expected_method_abi_digest_algorithm=binding.method_abi_digest_algorithm,
        expected_output_slot_id=binding.output_slot_id,
        expected_output_value_path=tuple(binding.output_value_path),
    )
    if execution_context is None:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="not_established",
            limitation=context_limitation or "method_execution_context_not_established",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    law = apply_registered_ex_ante_mean_change_law(
        output_payload.value,
        semantics,
        execution_context=execution_context,
        input_values=captured_input_values,
        input_capture_prestate_identity_sha256=recomputed_prestate_identity_sha256,
        expected_method_fqn=binding.method_fqn,
        expected_method_version=binding.method_version,
        expected_method_abi_digest=binding.method_abi_digest,
        expected_method_abi_digest_algorithm=binding.method_abi_digest_algorithm,
        expected_method_build_digest=occurrence.method_build_digest or "",
        expected_output_slot_id=binding.output_slot_id,
        expected_output_value_path=tuple(binding.output_value_path),
        target_unit=target_unit,
    )
    adapter = resolve_registered_method_metric_unit_adapter(
        source_unit,
        target_unit,
        law_id=binding.law_id,
        semantics=semantics,
    )
    if (
        (law.law_id, law.law_version, law.code_digest) != law_identity
        or (adapter.adapter_id, adapter.adapter_version, adapter.code_digest) != adapter_identity
        or adapter.operation != binding.conversion_operation
        or adapter.factor_numerator != binding.conversion_factor_numerator
        or adapter.factor_denominator != binding.conversion_factor_denominator
    ):
        raise _InvalidProjectionError("method_metric_registered_law_or_adapter_replay_mismatch")
    if law.status != "available" or adapter.operation == "unsupported":
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="unavailable",
            limitation=(
                law.limitation
                or adapter.limitation
                or "method_metric_direct_law_or_unit_relation_unavailable"
            ),
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    adapted = apply_registered_method_metric_unit_adapter(law, adapter)
    if adapted.status != "available" or adapted.value is None:
        return _build_unobserved_method_metric_observation(
            binding=binding,
            occurrence=occurrence,
            environment_ref=environment_ref,
            output_ref=output_ref,
            target_unit=target_unit,
            source_unit=source_unit,
            binding_set_ref=binding_set_ref,
            execution_bundle_ref=execution_bundle_ref,
            simulation_result_ref=simulation_result_ref,
            status="unavailable",
            limitation=adapted.limitation or "method_metric_exact_unit_value_unavailable",
            law_identity=law_identity,
            adapter_identity=adapter_identity,
            verifier_code_digest=verifier_code_digest,
        )
    value = adapted.value
    if not math.isfinite(value):
        raise _InvalidProjectionError("method_metric_converted_value_not_finite")

    law_predicates = tuple(
        MethodMetricPredicateEvidence(
            predicate_id=item.predicate_id,
            classification=item.classification,
            evidence_ref=(
                None
                if item.classification == "not_established"
                else input_state_ref
                if "pre_dispatch_state" in item.predicate_id
                else input_capture_ref
                if "input" in item.predicate_id
                else output_ref
            ),
            evidence_sha256=item.evidence_sha256,
            limitation=item.limitation,
        )
        for item in law.predicate_evidence
    )
    predicates = (
        MethodMetricPredicateEvidence(
            predicate_id="selected_graph_binding_and_metric_registry",
            classification="recomputed",
            evidence_ref=binding_set_ref,
        ),
        MethodMetricPredicateEvidence(
            predicate_id="selected_method_occurrence_and_output_payload",
            classification="recomputed",
            evidence_ref=output_ref,
        ),
        MethodMetricPredicateEvidence(
            predicate_id="selected_input_capture_and_prestate_identity",
            classification="independently_reconciled",
            evidence_ref=input_state_ref,
        ),
        MethodMetricPredicateEvidence(
            predicate_id="registered_ex_ante_law_and_exact_unit_adapter",
            classification="recomputed",
            evidence_ref=input_capture_ref,
        ),
        *law_predicates,
    )
    context = {
        "binding": binding.model_dump(mode="json"),
        "occurrence": occurrence.model_dump(mode="json"),
        "output": output_payload.model_dump(mode="json"),
        "returned_slot": returned_slot.model_dump(mode="json"),
        "execution_context": execution_context.model_dump(mode="json"),
        "law": law.model_dump(mode="json"),
        "adapter": adapter.model_dump(mode="json"),
        "adapted": adapted.model_dump(mode="json"),
        "refs": [
            _ref_key(binding_set_ref),
            _ref_key(execution_bundle_ref),
            _ref_key(simulation_result_ref),
            _ref_key(environment_ref),
            _ref_key(output_ref),
            _ref_key(input_capture_ref),
            _ref_key(input_state_ref),
        ],
    }
    observation = MethodMetricObservation(
        source_status="observed",
        binding_set_ref=binding_set_ref,
        execution_bundle_ref=execution_bundle_ref,
        simulation_result_ref=simulation_result_ref,
        environment_manifest_ref=environment_ref,
        output_ref=output_ref,
        input_capture_ref=input_capture_ref,
        binding_id=binding.binding_id,
        objective_id=binding.objective_id,
        metric_id=binding.metric_id,
        metric_unit_id=metric_unit_id,
        objective_direction=_objective_spec_direction(objective),
        objective_weight=_objective_spec_weight(objective),
        objective_target_present=getattr(objective, "target", None) is not None,
        objective_target_sha256=_objective_spec_target_sha256(objective),
        objective_spec_sha256=_objective_spec_sha256(objective),
        configured_objective_count=objective_count,
        occurrence_id=occurrence.occurrence_id,
        invocation_id=occurrence.invocation_id,
        plan_index=occurrence.plan_index,
        node_id=binding.node_id,
        method_fqn=binding.method_fqn,
        method_version=binding.method_version,
        method_abi_digest=binding.method_abi_digest,
        method_abi_digest_algorithm=binding.method_abi_digest_algorithm,
        method_build_digest=occurrence.method_build_digest,
        method_build_digest_scope=occurrence.method_build_digest_scope or "unavailable",
        slot_id=binding.output_slot_id,
        population_id=semantics.population_id,
        axes=tuple(semantics.axes),
        denominator_id=semantics.denominator_id,
        time_role=semantics.time_role,
        quantity_kind=semantics.quantity_kind,
        quantity_role=semantics.quantity_role,
        source_unit=_search_method_metric_source_unit(source_unit),
        target_unit=target_unit,
        value=value,
        law_id=law.law_id,
        law_version=law.law_version,
        law_code_digest=law.code_digest,
        adapter_id=adapter.adapter_id,
        adapter_version=adapter.adapter_version,
        adapter_code_digest=adapter.code_digest,
        verifier_id=METHOD_METRIC_PROJECTION_VERIFIER_ID,
        verifier_revision=METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
        verifier_code_digest=verifier_code_digest,
        checked_context_sha256=_canonical_sha256(context),
        predicate_evidence=predicates,
        limitations=(
            "candidate_observation_only",
            "external_population_representativeness_not_established",
            "external_causal_validity_not_established",
            "external_empirical_calibration_not_established",
            "external_legal_permission_not_established",
        ),
    )
    if comparison_collector is not None:
        contract = _ex_ante_rank_comparison_contract(
            observation=observation,
            execution_context=execution_context,
            capture=input_capture,
            environment=comparison_environment,
            graph=comparison_graph,
        )
        if contract is not None:
            comparison_collector.append(contract)
    return observation


@dataclass(frozen=True, slots=True)
class CompletedExAnteRankProjection:
    """One recomputed candidate-grade scalar and its exact comparison contract.

    This result is not an issuer or a persistent capability. A Runtime-owned
    consumer must resolve the completed source again at every action/read.
    """

    status: Literal["selected", "verification_missing", "invalid"]
    candidate_hash: str | None = None
    minimized_score: float | None = None
    maximizing_coordinate: float | None = None
    comparison_contract_sha256: str | None = None
    limitations: tuple[str, ...] = ()
    authority_status: Literal["candidate_only"] = "candidate_only"

    def __post_init__(self) -> None:
        if self.status == "selected":
            if (
                not self.candidate_hash
                or self.minimized_score is None
                or not math.isfinite(self.minimized_score)
                or self.maximizing_coordinate != -self.minimized_score
                or not self.comparison_contract_sha256
                or self.limitations
            ):
                raise ValueError("selected_ex_ante_rank_projection_requires_recomputed_basis")
        elif (
            self.candidate_hash is not None
            or self.minimized_score is not None
            or self.maximizing_coordinate is not None
            or self.comparison_contract_sha256 is not None
            or not self.limitations
        ):
            raise ValueError("limited_ex_ante_rank_projection_requires_reason_only")


def _ex_ante_comparison_environment(
    raw_environment: Any,
    *,
    manifest: ArtifactManifest,
    plan_ref: SelectedMethodMetricArtifactRef,
) -> dict[str, Any]:
    """Reconcile the selected producer plan before projecting run-specific identity.

    The caller has bounded-read the environment and validated the selected plan,
    its graph and the actual execution chain. Keep that complete source evidence;
    omit only the capture instant and this independently reconciled plan ID from
    the candidate comparison. Unknown producer metadata has no admitted meaning
    in this narrow profile and therefore cannot establish comparability.
    """
    from polisyos.core.artifacts.environment import EnvironmentManifest

    known_fields = set(EnvironmentManifest.model_fields) | set(
        EnvironmentManifest.model_computed_fields
    )
    known_fields.update(
        field.alias for field in EnvironmentManifest.model_computed_fields.values() if field.alias
    )
    if (
        type(raw_environment) is not dict
        or "captured_at" not in raw_environment
        or set(raw_environment) - known_fields
    ):
        raise _UnestablishedProjectionError("ranking_environment_payload_not_established")
    metadata = raw_environment.get("custom_metadata")
    if type(metadata) is not dict or set(metadata) != {
        "seed",
        "seed_source",
        "randomization_profile",
        "exec_plan_id",
        "loaded_method_identities",
        "environment_fingerprint_excludes_loaded_method_identity",
        "environment_identity_scope",
    }:
        raise _UnestablishedProjectionError("ranking_environment_metadata_not_supported")
    # A matching ID alone cannot distinguish two selected profiles of the same
    # plan bytes. Require the exact sidecar edge as well as its payload identity.
    _require_exact_manifest_edge(manifest, role="exec_plan", ref=plan_ref)
    if type(metadata["exec_plan_id"]) is not str or metadata["exec_plan_id"] != str(
        plan_ref.artifact_id
    ):
        raise _InvalidProjectionError("ranking_environment_selected_plan_id_mismatch")
    return {
        **{key: value for key, value in raw_environment.items() if key != "captured_at"},
        "custom_metadata": {key: value for key, value in metadata.items() if key != "exec_plan_id"},
    }


def _ex_ante_rank_comparison_contract(
    *,
    observation: MethodMetricObservation,
    execution_context: Any,
    capture: Any,
    environment: dict[str, Any] | None,
    graph: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Partition only the registered paired-array profile after full AD01 replay.

    Actual baseline bytes, both array layouts, complete resolved parameters,
    backend/seed contract, source environment and objective/measurement rules
    remain in the comparison. The verified scenario bytes may differ between
    candidates. This helper does not authenticate a caller or issue authority.
    """
    from polisyos.ir.kernel.method_metrics import METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID

    if (
        observation.source_status != "observed"
        or observation.method_fqn != "policy.evaluation.ex_ante_simulation@1.0.0"
        or observation.method_version != "1.0.0"
        or observation.law_id != METHOD_METRIC_EX_ANTE_MEAN_CHANGE_LAW_ID
        or observation.configured_objective_count != 1
        or observation.objective_spec_sha256 is None
        or observation.objective_direction not in {"minimize", "maximize"}
        or observation.objective_target_present is not False
        or observation.method_build_digest_scope != "class_source_only"
        or observation.method_build_digest is None
        or environment is None
        or graph is None
        or execution_context.parameter_resolution_status != "captured"
        or any(row.status != "captured" for row in execution_context.parameter_values)
        or execution_context.prestate_identity_status != "captured"
        or execution_context.backend_identity_status != "reconciled"
        or execution_context.backend_trace_status != "captured"
        or execution_context.fallback_status != "not_fell_back"
        or execution_context.seed_status != "reconciled"
        or set(execution_context.signature_input_slot_ids) != {"baseline", "scenario"}
        or set(execution_context.signature_parameter_names) != {"poverty_line"}
    ):
        return None
    slots = {slot.slot_id: slot for slot in capture.slots}
    if set(slots) != {"baseline", "scenario"} or len(capture.slots) != 2:
        return None
    if slots["baseline"].shape != slots["scenario"].shape:
        return None
    role_values = {
        (item.role_id, item.method_input_slot_id): item.value_sha256
        for item in execution_context.input_role_values
    }
    if role_values != {
        ("baseline", "baseline"): slots["baseline"].value_sha256,
        ("scenario", "scenario"): slots["scenario"].value_sha256,
    }:
        return None
    # Retain the complete typed observation except selected run-specific refs,
    # values and execution digest, which the AD01 owner has just revalidated.
    observation_contract = observation.model_dump(
        mode="json",
        exclude={
            "binding_set_ref",
            "execution_bundle_ref",
            "simulation_result_ref",
            "environment_manifest_ref",
            "output_ref",
            "input_capture_ref",
            "occurrence_id",
            "invocation_id",
            "value",
            "checked_context_sha256",
            "predicate_evidence",
        },
    )
    # Reconciled predicate classes and limitations remain part of the contract;
    # source-specific evidence refs/digests were independently replayed above.
    observation_contract["predicate_evidence"] = [
        {
            "predicate_id": row.predicate_id,
            "classification": row.classification,
            "limitation": row.limitation,
        }
        for row in observation.predicate_evidence
    ]
    execution = execution_context.model_dump(
        mode="json",
        exclude={
            "started_at",
            "completed_at",
            "dispatch_elapsed_ms",
            "runner_wall_time_ms",
            "runner_cpu_time_ms",
            "runner_compile_time_ms",
            "prestate_identity_sha256",
            "input_slot_values",
            "input_role_values",
        },
    )
    baseline = slots["baseline"].model_dump(mode="json")
    scenario = slots["scenario"].model_dump(mode="json", exclude={"value_sha256"})
    return {
        "profile": "completed_ex_ante_single_objective_v1",
        "observation": observation_contract,
        "execution": execution,
        "environment": environment,
        "graph_and_plan": graph,
        "baseline": baseline,
        "scenario_layout": scenario,
    }


def recompute_completed_ex_ante_rank_projection(
    store: _MethodMetricProjectionArtifactStore,
    *,
    basis: object | None,
    candidate_ref: ArtifactRef | None,
) -> CompletedExAnteRankProjection:
    """Replay a freshly selected owner basis for one candidate-only rank coordinate.

    ``basis`` must come from the completed Runtime owner read in the same
    authorized consumer. This helper accepts no persisted source/profile claim.
    It does not authenticate a structural owner passed to that earlier read.
    """
    from polisyos.scientist.methods.search.objective import ObjectiveScoreStatus

    if type(basis) is not _CompletedMethodMetricProjectionBasis:
        return CompletedExAnteRankProjection(
            status="verification_missing", limitations=("completed_method_metric_basis_missing",)
        )
    score = admit_completed_method_metric_objective_score(
        basis, candidate_ref=candidate_ref, request_status="requested"
    )
    if (
        score is None
        or score.status is not ObjectiveScoreStatus.AVAILABLE
        or score.predicate_status != "recomputed"
        or score.reported_assessment != score.recomputed_assessment
        or score.recomputed_assessment is None
        or score.recomputed_assessment.value is None
    ):
        return CompletedExAnteRankProjection(
            status="verification_missing", limitations=("completed_whole_objective_not_available",)
        )
    try:
        selected_candidate = _selected_ref(candidate_ref, kind="scientist.policy_design.candidate")
        if not _same_selected_ref(selected_candidate, basis.candidate_ref):
            raise _InvalidProjectionError("completed_rank_candidate_mismatch")
        source_tuple = _MethodMetricSourceTuple(
            job_id=basis.source_job_id,
            run_id=basis.source_run_id,
            attempt=basis.source_attempt,
            method_result_ref=None,
            simulation_result_ref=basis.simulation_result_ref.materialize(),
            method_execution_bundle_ref=basis.method_execution_bundle_ref.materialize(),
            method_metric_binding_set_ref=basis.method_metric_binding_set_ref.materialize(),
        )
        budget = _ProjectionReadBudget()
        execution_bases: list[Any] = []
        replay_candidate = _admit_execution_source_candidate(
            store,
            source_tuple=source_tuple,
            read_budget=budget,
            comparison_basis_collector=execution_bases,
        )
        if (
            not _same_selected_ref(replay_candidate, selected_candidate)
            or len(execution_bases) != 1
        ):
            raise _InvalidProjectionError("completed_rank_candidate_replay_mismatch")
        source = execution_bases[0]
        if (
            not _same_selected_ref(source.candidate_data_snapshot_ref, source.data_snapshot_ref)
            or not all(
                _same_selected_ref(source.candidate_registry_bundle_ref, ref)
                for ref in (
                    source.binding_registry_ref,
                    source.compile_registry_ref,
                    source.runtime_registry_ref,
                )
            )
            or source.parameter_override_bundle_ref is not None
            or source.observed_range_bundle_ref is not None
            or source.request.feedback_config_ref is not None
        ):
            return CompletedExAnteRankProjection(
                status="verification_missing",
                limitations=("completed_ex_ante_source_inputs_not_comparable",),
            )
        from polisyos.scientist.policy_design.schema import PolicyCandidateSchema

        candidate_manifest, candidate = _load_method_metric_model(
            store,
            ref=selected_candidate,
            model=PolicyCandidateSchema,
            expected_kind=PolicyCandidateSchema.ARTIFACT_KIND,
            expected_schema_name=PolicyCandidateSchema.ARTIFACT_SCHEMA_NAME,
            expected_schema_versions={PolicyCandidateSchema.ARTIFACT_SCHEMA_VERSION},
            max_bytes=MAX_METHOD_METRIC_SOURCE_BYTES,
            read_budget=budget,
        )
        _require_exact_manifest_edge(
            candidate_manifest,
            role="world_model_data_snapshot",
            ref=source.candidate_data_snapshot_ref,
        )
        _require_exact_manifest_edge(
            candidate_manifest,
            role="world_model_registry",
            ref=source.candidate_registry_bundle_ref,
        )
        model_spec = candidate.trinity_bundle.model_spec
        if str(model_spec.data_snapshot_ref) != str(source.data_snapshot_ref.artifact_id) or str(
            model_spec.registry_bundle_ref
        ) != str(source.candidate_registry_bundle_ref.artifact_id):
            return CompletedExAnteRankProjection(
                status="verification_missing",
                limitations=("completed_ex_ante_candidate_model_source_mismatch",),
            )
        contracts: list[dict[str, Any]] = []
        replayed = _admit_method_metric_observations(
            store,
            source_tuple=source_tuple,
            read_budget=budget,
            comparison_collector=contracts,
            comparison_candidate=candidate,
        )
        if replayed != basis.observations:
            raise _InvalidProjectionError("completed_rank_selected_observation_replay_mismatch")
        if len(replayed) != 1 or len(contracts) != 1:
            return CompletedExAnteRankProjection(
                status="verification_missing",
                limitations=("completed_ex_ante_profile_not_supported",),
            )
        minimized = float(score.recomputed_assessment.value)
        if not math.isfinite(minimized):
            raise _InvalidProjectionError("completed_rank_score_not_finite")
        return CompletedExAnteRankProjection(
            status="selected",
            candidate_hash=candidate.candidate_hash(),
            minimized_score=minimized,
            maximizing_coordinate=-minimized,
            comparison_contract_sha256=_canonical_sha256(
                {
                    "method": contracts[0],
                    "registry": source.candidate_registry_bundle_ref.model_dump(mode="json"),
                    "request": source.request.model_dump(
                        mode="json",
                        exclude={"exec_plan_ref", "input_bindings_ref", "registry_bundle_ref"},
                    ),
                    "request_fields_set": source.request_fields_set,
                    "request_exec_config_fields_set": source.request_exec_config_fields_set,
                    "effective_execution": {
                        key: getattr(source, key)
                        for key in (
                            "effective_step",
                            "effective_seed",
                            "effective_seed_source",
                            "effective_mode",
                            "effective_max_steps",
                            "effective_determinism_tier",
                            "effective_nan_guard_enabled",
                            "effective_jit",
                            "effective_capture_env",
                        )
                    },
                }
            ),
        )
    except _UnestablishedProjectionError as exc:
        return CompletedExAnteRankProjection(status="verification_missing", limitations=(str(exc),))
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return CompletedExAnteRankProjection(
            status="invalid", limitations=("completed_rank_source_replay_invalid",)
        )


def _build_unobserved_method_metric_observation(
    *,
    binding: MethodMetricBinding,
    occurrence: MethodExecutionOccurrence | None,
    environment_ref: SelectedMethodMetricArtifactRef | None,
    output_ref: SelectedMethodMetricArtifactRef | None = None,
    target_unit: UnitSpecType,
    source_unit: MethodMetricSourceUnit,
    binding_set_ref: SelectedMethodMetricArtifactRef,
    execution_bundle_ref: SelectedMethodMetricArtifactRef,
    simulation_result_ref: SelectedMethodMetricArtifactRef,
    status: Literal["unavailable", "invalid", "not_established"],
    limitation: str,
    law_identity: tuple[str, str, str],
    adapter_identity: tuple[str, str, str],
    verifier_code_digest: str,
) -> MethodMetricObservation:
    """Retain a precise non-observation row without inventing a numeric value."""
    semantics = binding.semantics
    invocation_id = None if occurrence is None else occurrence.invocation_id
    plan_index = None if occurrence is None else occurrence.plan_index
    return MethodMetricObservation(
        source_status=status,
        binding_set_ref=binding_set_ref,
        execution_bundle_ref=execution_bundle_ref,
        simulation_result_ref=simulation_result_ref,
        environment_manifest_ref=environment_ref,
        output_ref=output_ref,
        binding_id=binding.binding_id,
        objective_id=binding.objective_id,
        metric_id=binding.metric_id,
        occurrence_id=None if occurrence is None else occurrence.occurrence_id,
        invocation_id=invocation_id,
        plan_index=plan_index,
        node_id=binding.node_id,
        method_fqn=binding.method_fqn,
        method_version=binding.method_version,
        method_abi_digest=binding.method_abi_digest,
        method_abi_digest_algorithm=binding.method_abi_digest_algorithm,
        method_build_digest=(None if occurrence is None else occurrence.method_build_digest),
        method_build_digest_scope=(
            "unavailable"
            if occurrence is None or occurrence.method_build_digest_scope is None
            else occurrence.method_build_digest_scope
        ),
        slot_id=binding.output_slot_id,
        population_id=None if semantics is None else semantics.population_id,
        axes=() if semantics is None else tuple(semantics.axes),
        denominator_id=None if semantics is None else semantics.denominator_id,
        time_role=None if semantics is None else semantics.time_role,
        quantity_kind=None if semantics is None else semantics.quantity_kind,
        quantity_role=None if semantics is None else semantics.quantity_role,
        source_unit=_search_method_metric_source_unit(source_unit),
        target_unit=target_unit,
        law_id=law_identity[0],
        law_version=law_identity[1],
        law_code_digest=law_identity[2],
        adapter_id=adapter_identity[0],
        adapter_version=adapter_identity[1],
        adapter_code_digest=adapter_identity[2],
        verifier_id=METHOD_METRIC_PROJECTION_VERIFIER_ID,
        verifier_revision=METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
        verifier_code_digest=verifier_code_digest,
        checked_context_sha256=_canonical_sha256(
            {
                "binding": binding.model_dump(mode="json"),
                "occurrence": (None if occurrence is None else occurrence.model_dump(mode="json")),
                "limitation": limitation,
            }
        ),
        limitations=(limitation,),
    )


def _read_bounded_method_metric_artifact(
    store: _MethodMetricProjectionArtifactReader,
    *,
    ref: SelectedMethodMetricArtifactRef,
    max_bytes: int,
    read_budget: _ProjectionReadBudget,
) -> CoreJsonArtifactBoundedRead:
    """Read one selected blob through Core's bounded manifest and payload path."""
    core_ref = _core_artifact_ref(ref)
    key = artifact_ref_identity_key(core_ref)
    if key in read_budget.manifest_refs and key not in read_budget.payload_refs:
        raise _InvalidProjectionError("selected_method_metric_manifest_would_be_read_twice")
    limits = read_budget.limits_for_payload(core_ref, max_bytes=max_bytes)
    try:
        bounded_read = read_core_json_artifact_bounded(store, core_ref, limits=limits)
    except FileNotFoundError as exc:
        raise _UnestablishedProjectionError(
            "selected_method_metric_artifact_bytes_unavailable"
        ) from exc
    except CoreJsonReadBoundsRefusalError as exc:
        observed_source_bytes = _core_observed_source_bytes(exc)
        observed_manifest_bytes = exc.observed_manifest_bytes
        observed_payload_bytes = exc.observed_bytes
        if (
            type(observed_manifest_bytes) is not int
            or observed_manifest_bytes < 0
            or type(observed_payload_bytes) is not int
            or observed_payload_bytes < 0
        ):
            read_budget.account_refused_execution_source_bytes(observed_source_bytes)
            raise _UnestablishedProjectionError(
                "core_bounded_refusal_transfer_accounting_not_established"
            ) from exc
        read_budget.account_refused_read(
            core_ref,
            observed_manifest_bytes=observed_manifest_bytes,
            observed_bytes=observed_payload_bytes,
            observed_source_bytes=observed_source_bytes,
        )
        raise _InvalidProjectionError(
            "selected_method_metric_artifact_exceeds_bounded_read"
        ) from exc
    except (AttributeError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise _InvalidProjectionError(
            "selected_method_metric_artifact_bounded_read_failed"
        ) from exc
    read_budget.account_bounded_read(core_ref, bounded_read)
    read_budget.manifests[key] = bounded_read.manifest
    return bounded_read


def _schema_matches_expected_contract(
    schema: SchemaInfo | None,
    *,
    expected_schema_name: str | None,
    expected_schema_versions: set[str] | None,
) -> bool:
    """Match either an exact schema descriptor or the owner's exact no-schema contract."""
    if expected_schema_name is None and expected_schema_versions is None:
        return schema is None
    return (
        schema is not None
        and expected_schema_name is not None
        and expected_schema_versions is not None
        and schema.name == expected_schema_name
        and schema.version in expected_schema_versions
    )


def _validate_bounded_method_metric_model[ModelT: BaseModel](
    model: type[ModelT],
    bounded_read: CoreJsonArtifactBoundedRead,
    *,
    expected_kind: str,
    expected_schema_name: str | None,
    expected_schema_versions: set[str] | None,
) -> ModelT:
    """Apply Core's typed adapter to an already bounded selected-profile read."""
    manifest = bounded_read.manifest
    schema_matches = _schema_matches_expected_contract(
        manifest.artifact_schema,
        expected_schema_name=expected_schema_name,
        expected_schema_versions=expected_schema_versions,
    )
    if (
        manifest.kind != expected_kind
        or manifest.media_type != "application/json"
        or not schema_matches
    ):
        raise _InvalidProjectionError("selected_method_metric_artifact_schema_or_kind_mismatch")
    try:
        return validate_core_model_bounded_read(model, bounded_read)
    except Exception as exc:
        # Typed Core rejection is a supplied-source defect, not permission to default.
        raise _InvalidProjectionError("selected_method_metric_artifact_payload_invalid") from exc


def _load_method_metric_model[ModelT: BaseModel](
    store: _MethodMetricProjectionArtifactStore,
    *,
    ref: SelectedMethodMetricArtifactRef,
    model: type[ModelT],
    expected_kind: str,
    expected_schema_name: str | None,
    expected_schema_versions: set[str] | None,
    max_bytes: int,
    read_budget: _ProjectionReadBudget,
) -> tuple[ArtifactManifest, ModelT]:
    """Load one strict model from a single bounded selected-profile read."""
    bounded_read = _read_bounded_method_metric_artifact(
        store,
        ref=ref,
        max_bytes=max_bytes,
        read_budget=read_budget,
    )
    payload = _validate_bounded_method_metric_model(
        model,
        bounded_read,
        expected_kind=expected_kind,
        expected_schema_name=expected_schema_name,
        expected_schema_versions=expected_schema_versions,
    )
    return bounded_read.manifest, payload


def _require_exact_manifest_edge(
    manifest: ArtifactManifest,
    *,
    edges_by_role: Mapping[str, list[InputRef]] | None = None,
    role: str,
    ref: SelectedMethodMetricArtifactRef,
) -> None:
    """Require exactly one selected-profile edge for a payload relationship."""
    edges = (
        edges_by_role.get(role, [])
        if edges_by_role is not None
        else [edge for edge in manifest.inputs if edge.role == role]
    )
    if len(edges) != 1:
        raise _InvalidProjectionError(f"selected_manifest_requires_one_{role}_edge")
    edge = edges[0]
    if (
        edge.manifest_profile_sha256 is None
        or str(edge.artifact_id) != str(ref.artifact_id)
        or edge.manifest_profile_sha256 != ref.manifest_profile_sha256
    ):
        raise _InvalidProjectionError(f"selected_manifest_{role}_edge_profile_mismatch")


def _require_exact_payload_ref(ref: ArtifactRef, *, kind: str) -> None:
    """Reject unselected or incorrectly typed embedded graph refs."""
    if (
        not isinstance(ref, ArtifactRef)
        or ref.kind != kind
        or ref.media_type != "application/json"
        or ref.manifest_profile_sha256 is None
    ):
        raise _InvalidProjectionError("method_metric_payload_ref_requires_exact_selected_profile")


def _require_payload_ref_match(
    actual: ArtifactRef,
    expected: ArtifactRef,
    *,
    reason: str,
) -> None:
    """Compare all base ArtifactRef fields, including the exact selected profile."""
    if artifact_ref_identity_key(actual) != artifact_ref_identity_key(expected):
        raise _InvalidProjectionError(reason)


def _canonical_model(value: BaseModel) -> str:
    """Return deterministic strict JSON for model equality across typed registries."""
    return json.dumps(
        value.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _canonical_sha256(value: object) -> str:
    """Hash a deterministic JSON context without treating the digest as authority."""
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _source_tuple_sha256(source_tuple: _MethodMetricSourceTuple) -> str:
    """Bind the staged vector metadata to immutable run and producer refs."""
    return _canonical_sha256(
        {
            "job_id": source_tuple.job_id,
            "run_id": source_tuple.run_id,
            "attempt": source_tuple.attempt,
            "method_result_ref": (
                None
                if source_tuple.method_result_ref is None
                else _ref_key(source_tuple.method_result_ref)
            ),
            "simulation_result_ref": _ref_key(source_tuple.simulation_result_ref),
            "method_execution_bundle_ref": _ref_key(source_tuple.method_execution_bundle_ref),
            "method_metric_binding_set_ref": _ref_key(source_tuple.method_metric_binding_set_ref),
        }
    )


def _ref_key(ref: ArtifactRef | None) -> tuple[str, str, str, str | None] | None:
    """Project one full reference into immutable scalar identity fields."""
    if ref is None:
        return None
    return artifact_ref_identity_key(ref)


def _verifier_implementation_sha256() -> str:
    """Digest the deployed verifier source bytes for Runtime's exact association."""
    return "sha256:" + hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def _bounded_projection_reason(exc: Exception) -> str:
    """Return a non-sensitive reason code instead of serializing artifact data/errors."""
    if isinstance(exc, _InvalidProjectionError):
        return str(exc)
    return "method_metric_projection_source_read_or_validation_failed"


def _persist_method_metric_projection(
    store: _MethodMetricProjectionArtifactStore,
    *,
    vector: PolicyEvaluationVector,
) -> ArtifactRef:
    """Persist an observation-only v1.3 vector with exact selected source edges."""
    if (
        not vector.method_metric_observations
        or vector.primary
        or vector.hard_constraints
        or vector.secondary
        or vector.penalties
        or vector.score_assessment is not None
        or vector.score_source is not None
        or not vector.feasible
        or vector.blocking_reasons
    ):
        raise _InvalidProjectionError("method_metric_projection_must_remain_observation_only")
    inputs = [
        input_ref_from_artifact_ref(ref, role=role)
        for role, ref in method_metric_observation_input_refs(vector.method_metric_observations)
    ]
    return store.put_json(
        vector,
        PutOptions(
            kind="scientist.policy_evaluation_vector",
            media_type="application/json",
            schema=SchemaInfo(
                name="polisyos.scientist.policy_design.PolicyEvaluationVector",
                version="1.3",
            ),
            producer=ProducerInfo(
                component=METHOD_METRIC_PROJECTION_VERIFIER_ID,
                version=METHOD_METRIC_PROJECTION_VERIFIER_REVISION,
            ),
            inputs=inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False, exclude_none=False),
        return_selected_profile=True,
    )


def _verify_staged_method_metric_projection(
    store: _MethodMetricProjectionArtifactStore,
    *,
    vector_ref: ArtifactRef,
    expected_vector: PolicyEvaluationVector,
    source_tuple: _MethodMetricSourceTuple,
    source_candidate_ref: ArtifactRef,
    read_budget: _ProjectionReadBudget,
) -> None:
    """Read back the exact just-written vector and its source lineage before issuing."""
    selected_vector_ref = _selected_ref(
        vector_ref,
        kind="scientist.policy_evaluation_vector",
    )
    vector_manifest, vector = _load_method_metric_model(
        store,
        ref=selected_vector_ref,
        model=PolicyEvaluationVector,
        expected_kind="scientist.policy_evaluation_vector",
        expected_schema_name="polisyos.scientist.policy_design.PolicyEvaluationVector",
        expected_schema_versions={"1.3"},
        max_bytes=MAX_POLICY_EVALUATION_VECTOR_BYTES,
        read_budget=read_budget,
    )
    if (
        vector.method_metric_observations != expected_vector.method_metric_observations
        or _canonical_model(vector) != _canonical_model(expected_vector)
        or vector.metadata.get("source_tuple_sha256") != _source_tuple_sha256(source_tuple)
        or vector.metadata.get("source_candidate_ref")
        != _selected_ref(
            source_candidate_ref,
            kind="scientist.policy_design.candidate",
        ).model_dump(mode="json")
    ):
        raise _InvalidProjectionError("staged_method_metric_vector_readback_mismatch")
    _validate_vector_input_edges(vector_manifest, vector.method_metric_observations)
    selected_simulation_ref = _selected_ref(
        source_tuple.simulation_result_ref,
        kind="foundry.simulation_result",
    )
    selected_bundle_ref = _selected_ref(
        source_tuple.method_execution_bundle_ref,
        kind="foundry.method_execution_bundle",
    )
    selected_binding_ref = _selected_ref(
        source_tuple.method_metric_binding_set_ref,
        kind="foundry.method_metric_binding_set",
    )
    if any(
        observation.simulation_result_ref != selected_simulation_ref
        or observation.execution_bundle_ref != selected_bundle_ref
        or observation.binding_set_ref != selected_binding_ref
        for observation in vector.method_metric_observations
    ):
        raise _InvalidProjectionError("staged_vector_does_not_bind_expected_source_tuple")
