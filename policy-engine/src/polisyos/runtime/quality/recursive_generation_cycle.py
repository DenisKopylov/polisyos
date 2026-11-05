"""Thin depth-N router over canonical recursion and generation-cycle owners."""

from __future__ import annotations

import ast
import hashlib
from collections.abc import Callable, Mapping
from contextvars import ContextVar
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ModelWrapValidatorHandler,
    PrivateAttr,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef as CASArtifactRef
from polisyos.pdc import (
    CompositionCertificate,
    EvalSafetyAdmissionChallenge,
    SearchTerminalKind,
    SearchTerminalState,
    SubDesignContract,
    evaluation_safety_consumer_admission_is_verified,
    gy_artifact_self_identity_projection,
    gy_content_hash,
)
from polisyos.runtime.quality.candidate_simulation import (
    CandidateScenarioMaterializationV1,
    CandidateScenarioNumericMaterializationV1,
    CandidateSimulationContextHandoff,
)
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
    CycleSubstrateContextArtifactOwner,
    VerifiedNLJobBudgetScope,
    VerifiedNLJobScope,
)
from polisyos.runtime.quality.design_axes.coupling_composition import (
    RecursiveDesignGraph,
    compose_subdesigns,
)
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.evaluation_modes import (
    ExecutionIntentBand,
    execution_intent_band_for_mode,
    resolve_evaluation_mode,
    resolve_execution_intent_band,
)
from polisyos.runtime.quality.evaluation_safety import EvaluationExecutionContext
from polisyos.runtime.quality.generation_cycle import (
    FOUNDRY_VALUE_PORT_EVALUATOR_ID,
    FoundryValuePort,
    GenerationCycleController,
    GenerationCycleError,
    GenerationCycleRun,
    N4GenerationPort,
    _bind_scoped_n5_invocation_policy,
    generation_cycle_terminal_state,
    load_joint_simulation_result,
    persist_joint_simulation_result,
    validate_generation_cycle_candidate_run,
    validate_generation_cycle_run_history,
)
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleSimulationAdmissionOwner,
    GenericCycleSimulationChildSelectionV1,
    GenericCycleSimulationContextHandoffV1,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationControllerError,
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
    SimulationProofReceipt,
)
from polisyos.runtime.quality.workspace.loop import (
    SearchExitDecisionInputs,
    select_search_terminal,
)
from polisyos.scientist.orchestration.engine.producer_budget import (
    BudgetInvocationCapacityObservation,
    BudgetInvocationExhaustionWitness,
    ProducerBudgetObserver,
    ProducerBudgetSourceError,
    verify_standard_invocation_exhaustion_historical,
)

if TYPE_CHECKING:
    from polisyos.core import contracts as core_contracts
    from polisyos.core.artifacts import ArtifactStore, ArtifactWriteOptions
    from polisyos.core.contracts import CatalogRunProfile
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.data_forge_binding import (
        MeasurementRootExecutionBinding,
    )
    from polisyos.runtime.quality.evaluation_safety import EvalSafetyVerifierPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.open_world_risk import PromotionRuntime
    from polisyos.runtime.quality.substrate_registry import CatalogServingSourcePaths
    from polisyos.scientist import BudgetState
    from polisyos.scientist.orchestration.engine import (
        BudgetInvocationQuotaPolicy,
        BudgetLedgerProducerRunBinding,
        BudgetMiddleware,
    )

RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION = "policyos.runtime.recursive_generation_cycle.v1"
RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION = (
    "policyos.runtime.recursive_generation_cycle.partial.v2"
)
RECURSIVE_GENERATION_CYCLE_PARTIAL_V3_SCHEMA_VERSION = (
    "policyos.runtime.recursive_generation_cycle.partial.v3"
)
RECURSIVE_GENERATION_CYCLE_PARTIAL_V4_SCHEMA_VERSION = (
    "policyos.runtime.recursive_generation_cycle.partial.v4"
)
_N4_CHILD_PROFILE_SET_CANON = canon.CanonSpec(forbid_floats=False)
_GENERIC_LEAF_CAPSULE_CANON = canon.CanonSpec(forbid_floats=False)
ExecutionIntent = Literal[
    "candidate_only",
    "simulate_only",
    "retrospective",
    "measurement_audit",
    "sandbox_pilot",
    "field_pilot",
    "deployment",
]
RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF = (
    "polisyos.runtime.quality.recursive_generation_cycle.RecursiveGenerationCycleController"
)
# These are the complete set of ref-less v1 recursive-run identities currently
# tracked in the repository.  A self-computed hash is integrity evidence only;
# it is not permission to reopen pre-CAS numeric evidence.
_AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES = frozenset(
    {
        "sha256:b72e66af7330f57830ca9c70c348051e53b858e02a5b82893988855823c7a3c1",
        "sha256:13647b6958aac56b004faded5752b31cc7d53fde67c9476f1f899051b4edab50",
        "sha256:47cf94dbe46aa90e9a0a9b3208459f4687a0ea1c651ef5d8dbce8a738db09f6d",
        "sha256:17a29992ae4ce1720290a40e1a7651bf5949176e718520824d74b80c2b8a2328",
        "sha256:23ad1413786ccf1e3c1d13c09d33a9df87bb3a18c798570be245206c352d72ec",
        "sha256:027db04a69e899eb80c911de9df7432d31fa8afd480baf0dae8f49ca62362137",
        "sha256:d6ddaacf81d9cc4c48b049c4070149026d1fd8e07a118890a5abc1745c952535",
    }
)
_LEGACY_RECURSIVE_V1_CONTEXT: ContextVar[bool] = ContextVar(
    "polisyos_legacy_recursive_v1_context",
    default=False,
)
_LEGACY_RECURSIVE_FIXTURE_SYMBOLS = frozenset(
    {
        "run_recursive_case",
        "coupling_graph_for_subdesigns",
        "_recursive_case_child_fixtures",
    }
)
_DEFAULT_RECURSIVE_ROUTE_SYMBOL = "build_default_recursive_generation_cycle_controller"


def _is_authenticated_legacy_v1(value: object) -> bool:
    """Return whether value is one exact tracked pre-CAS recursive artifact."""

    if not isinstance(value, Mapping):
        return False
    if value.get("schema_version") != RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION:
        return False
    raw_nodes = value.get("nodes")
    if not isinstance(raw_nodes, (list, tuple)) or not raw_nodes:
        return False
    if any(not isinstance(node, Mapping) for node in raw_nodes):
        return False
    if any("joint_simulation_ref" in node for node in raw_nodes):
        return False
    raw_content_hash = value.get("content_hash")
    if raw_content_hash not in _AUTHENTIC_LEGACY_RECURSIVE_V1_CONTENT_HASHES:
        return False
    legacy_payload = {key: item for key, item in value.items() if key != "content_hash"}
    return gy_content_hash(legacy_payload) == raw_content_hash


def _joint_simulation_is_unsupported(result: JointSimulationResult) -> bool:
    """Return whether N5 emitted no supported trajectory for composition."""

    return (
        result.receipt.calibration_status in {"unsupported_coupling_gated", "no_run"}
        or not result.trajectories
        or not any(decision.decision == "selected" for decision in result.engine_decisions)
        or result.diagnostics.get("physical_work_interruption")
        == "n5_physical_budget_scope_lost_after_work"
    )


class RecursiveGenerationCycleError(ValueError):
    """Fail-closed depth-N routing error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _RecursiveBudgetStopError(Exception):
    """Unwind the router after an owner-issued leaf budget terminal."""

    def __init__(
        self,
        budget_stop_node_ref: str,
        frontier_node_refs: tuple[str, ...] = (),
    ) -> None:
        self.budget_stop_node_ref = budget_stop_node_ref
        self.frontier_node_refs = frontier_node_refs
        super().__init__("recursive_child_budget_exhausted")


class _RecursiveStandardQuotaStopError(Exception):
    """Unwind before a sibling after owner-replayed standard N5 exhaustion."""

    def __init__(
        self,
        *,
        stop_parent_node_ref: str,
        pending_child_node_ref: str,
        pending_child_index: int,
        frontier_node_refs: tuple[str, ...],
        exhaustion_witness: BudgetInvocationExhaustionWitness,
    ) -> None:
        self.stop_parent_node_ref = stop_parent_node_ref
        self.pending_child_node_ref = pending_child_node_ref
        self.pending_child_index = pending_child_index
        self.frontier_node_refs = frontier_node_refs
        self.exhaustion_witness = exhaustion_witness
        super().__init__("recursive_standard_n5_capacity_exhausted")


class _StrictModel(BaseModel):
    """Strict immutable base for public depth-N artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RecursiveLeafContextCapsule(_StrictModel):
    """Complete candidate leaf inputs, without inheriting a parent authority grant."""

    schema_version: Literal["policyos.runtime.recursive_leaf_context.v1"] = (
        "policyos.runtime.recursive_leaf_context.v1"
    )
    authority_purpose: Literal["candidate_leaf_replay_only"] = "candidate_leaf_replay_only"
    node_ref: str = Field(min_length=1)
    parent_ref: str = Field(min_length=1)
    problem: DesignProblem
    handoff: CandidateSimulationContextHandoff
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_complete_child(self) -> RecursiveLeafContextCapsule:
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
            cycle_job_profile_selection_ref,
        )

        if self.node_ref == self.parent_ref:
            raise ValueError("recursive_leaf_parent_is_child")
        if (
            self.handoff.context.design_problem_ref != cycle_job_design_problem_ref(self.problem)
            or self.handoff.context.domain != self.problem.domain
            or self.handoff.profile.profile_selection_ref
            != cycle_job_profile_selection_ref(self.problem)
        ):
            raise ValueError("recursive_leaf_capsule_full_problem_mismatch")
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("recursive_leaf_capsule_content_mismatch")
        return self


def _generic_n4_child_selection(
    *,
    node_ref: str,
    parent_ref: str,
    parent_problem: DesignProblem,
    parent_handoff: GenericCycleSimulationContextHandoffV1,
    child_problem: DesignProblem,
    source_result_ref: str,
    source_atom_refs: tuple[str, ...],
    semantic_ref: str,
    n4_source_ref: CASArtifactRef,
) -> GenericCycleSimulationChildSelectionV1:
    """Build the owner selection only from one replayed N4 child row."""
    from polisyos.runtime.quality.cycle_substrate import (
        cycle_job_design_problem_ref,
        generic_n4_child_profile_selection_ref,
    )

    if parent_handoff.n4_child_profile_family_ref is None:
        raise RecursiveGenerationCycleError(
            "recursive_generic_child_profile_family_not_established"
        )
    parent_problem_ref = cycle_job_design_problem_ref(parent_problem)
    child_full_ref = cycle_job_design_problem_ref(child_problem)
    child_uri = "design-problem://" + child_full_ref.removeprefix("sha256:")
    expected_parent_uri = "design-problem://" + parent_problem_ref.removeprefix("sha256:")
    if node_ref != child_uri or parent_ref != expected_parent_uri:
        raise RecursiveGenerationCycleError("recursive_generic_child_problem_identity_mismatch")
    source_record = child_problem.runtime_hints.get("n4_candidate_child_source")
    if not isinstance(source_record, Mapping):
        raise RecursiveGenerationCycleError("recursive_generic_child_source_lineage_missing")
    if source_record.get("parent_design_problem_ref") != parent_problem_ref:
        raise RecursiveGenerationCycleError("recursive_generic_child_source_parent_mismatch")
    selection_ref = generic_n4_child_profile_selection_ref(
        child_problem,
        parent_problem_ref=parent_problem_ref,
        source_result_ref=source_result_ref,
        source_atom_refs=source_atom_refs,
        semantic_ref=semantic_ref,
    )
    return GenericCycleSimulationChildSelectionV1(
        node_ref=node_ref,
        parent_ref=parent_ref,
        parent_problem=parent_problem,
        parent_handoff=parent_handoff,
        problem=child_problem,
        full_child_problem_ref=child_full_ref,
        parent_problem_ref=parent_problem_ref,
        source_result_ref=source_result_ref,
        source_atom_refs=source_atom_refs,
        semantic_ref=semantic_ref,
        n4_source_ref=n4_source_ref,
        n4_child_profile_family_ref=parent_handoff.n4_child_profile_family_ref,
        profile_selection_ref=selection_ref,
    )


class RecursiveN4ChildProfileBindingV1(_StrictModel):
    """One actual N4-derived child joined to its owner-selected profile."""

    node_ref: str = Field(min_length=1)
    parent_ref: str = Field(min_length=1)
    problem: DesignProblem
    source_ref: CASArtifactRef
    source_result_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_atom_refs: tuple[str, ...] = Field(min_length=1)
    semantic_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    selection: GenericCycleSimulationChildSelectionV1
    handoff: GenericCycleSimulationContextHandoffV1

    @model_validator(mode="after")
    def _bind_child_profile(self) -> RecursiveN4ChildProfileBindingV1:
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )

        if (
            self.node_ref == self.parent_ref
            or self.source_ref.kind != "runtime.generation_source_handoff"
            or self.source_ref.media_type != "application/json"
            or self.handoff.context.design_problem_ref != cycle_job_design_problem_ref(self.problem)
            or self.handoff.profile.profile_selection_kind != "n4_candidate_child"
            or self.handoff.profile.profile_selection_ref != self.selection.profile_selection_ref
            or self.selection.node_ref != self.node_ref
            or self.selection.parent_ref != self.parent_ref
            or self.selection.problem != self.problem
            or self.selection.source_result_ref != self.source_result_ref
            or self.selection.source_atom_refs != self.source_atom_refs
            or self.selection.semantic_ref != self.semantic_ref
            or self.selection.n4_source_ref != self.source_ref
            or self.selection.n4_child_profile_family_ref
            != self.handoff.n4_child_profile_family_ref
            or self.selection.parent_handoff.n4_child_profile_family_ref
            != self.handoff.n4_child_profile_family_ref
            or len(self.source_atom_refs) != len(set(self.source_atom_refs))
            or tuple(self.source_atom_refs) != tuple(sorted(self.source_atom_refs))
            or any(not value.strip() for value in self.source_atom_refs)
        ):
            raise ValueError("recursive_n4_child_profile_binding_invalid")
        expected_node = "design-problem://" + cycle_job_design_problem_ref(
            self.problem
        ).removeprefix("sha256:")
        if self.node_ref != expected_node:
            raise ValueError("recursive_n4_child_profile_node_ref_mismatch")
        return self


class RecursiveN4ChildProfileSetV1(_StrictModel):
    """Complete candidate-only profile family derived from one persisted N4 result."""

    schema_version: Literal["policyos.runtime.quality.recursive_n4_child_profile_set.v1"] = (
        "policyos.runtime.quality.recursive_n4_child_profile_set.v1"
    )
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    parent_problem: DesignProblem
    parent_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parent_handoff: GenericCycleSimulationContextHandoffV1
    n4_child_profile_family_ref: CASArtifactRef
    source_ref: CASArtifactRef
    children: tuple[RecursiveN4ChildProfileBindingV1, ...] = Field(min_length=1)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_complete_family(self) -> RecursiveN4ChildProfileSetV1:
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )

        scope = (self.job_id, self.run_id, self.tenant_id, self.cell_id)
        if (
            self.parent_problem_ref != cycle_job_design_problem_ref(self.parent_problem)
            or self.source_ref.kind != "runtime.generation_source_handoff"
            or self.source_ref.media_type != "application/json"
            or self.n4_child_profile_family_ref.kind
            != "runtime.quality.generic_cycle_simulation_child_profile_family"
            or self.n4_child_profile_family_ref.media_type != "application/json"
            or self.parent_handoff.n4_child_profile_family_ref != self.n4_child_profile_family_ref
            or (
                self.parent_handoff.job_id,
                self.parent_handoff.run_id,
                self.parent_handoff.tenant_id,
                self.parent_handoff.cell_id,
            )
            != scope
            or self.parent_handoff.context.design_problem_ref != self.parent_problem_ref
        ):
            raise ValueError("recursive_n4_child_profile_family_parent_binding_invalid")
        node_refs = tuple(row.node_ref for row in self.children)
        if len(node_refs) != len(set(node_refs)):
            raise ValueError("recursive_n4_child_profile_family_duplicate_child")
        if any(
            row.parent_ref != "design-problem://" + self.parent_problem_ref.removeprefix("sha256:")
            or row.source_ref != self.source_ref
            or row.selection.parent_handoff != self.parent_handoff
            or row.selection.n4_child_profile_family_ref != self.n4_child_profile_family_ref
            or row.selection.n4_source_ref != self.source_ref
            or (
                row.handoff.job_id,
                row.handoff.run_id,
                row.handoff.tenant_id,
                row.handoff.cell_id,
            )
            != scope
            for row in self.children
        ):
            raise ValueError("recursive_n4_child_profile_family_child_scope_mismatch")
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("recursive_n4_child_profile_family_content_mismatch")
        return self


class RecursiveLeafContextCapsuleV2(_StrictModel):
    """Generic N5 leaf replay inputs bound to the full source-derived family."""

    schema_version: Literal["policyos.runtime.recursive_leaf_context.v2"] = (
        "policyos.runtime.recursive_leaf_context.v2"
    )
    authority_purpose: Literal["cycle_input_candidate_only"] = "cycle_input_candidate_only"
    node_ref: str = Field(min_length=1)
    parent_ref: str = Field(min_length=1)
    problem: DesignProblem
    child_selection: GenericCycleSimulationChildSelectionV1
    handoff: GenericCycleSimulationContextHandoffV1
    n4_source_ref: CASArtifactRef
    n4_child_profile_family_ref: CASArtifactRef
    n4_child_profile_set_ref: CASArtifactRef
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_generic_leaf(self) -> RecursiveLeafContextCapsuleV2:
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )

        if (
            self.node_ref == self.parent_ref
            or self.handoff.context.design_problem_ref != cycle_job_design_problem_ref(self.problem)
            or self.handoff.profile.profile_selection_kind != "n4_candidate_child"
            or self.handoff.profile.profile_selection_ref
            != self.child_selection.profile_selection_ref
            or self.child_selection.node_ref != self.node_ref
            or self.child_selection.parent_ref != self.parent_ref
            or self.child_selection.problem != self.problem
            or self.child_selection.full_child_problem_ref
            != cycle_job_design_problem_ref(self.problem)
            or self.child_selection.n4_source_ref != self.n4_source_ref
            or self.n4_source_ref.kind != "runtime.generation_source_handoff"
            or self.n4_source_ref.media_type != "application/json"
            or type(self.n4_child_profile_family_ref) is not CASArtifactRef
            or self.n4_child_profile_family_ref.kind
            != "runtime.quality.generic_cycle_simulation_child_profile_family"
            or self.n4_child_profile_family_ref.media_type != "application/json"
            or self.handoff.n4_child_profile_family_ref != self.n4_child_profile_family_ref
            or self.child_selection.n4_child_profile_family_ref != self.n4_child_profile_family_ref
            or self.child_selection.parent_handoff.n4_child_profile_family_ref
            != self.n4_child_profile_family_ref
            or self.n4_child_profile_set_ref.kind
            != "runtime.quality.recursive_n4_child_profile_set"
            or self.n4_child_profile_set_ref.media_type != "application/json"
        ):
            raise ValueError("recursive_generic_leaf_binding_invalid")
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("recursive_generic_leaf_content_mismatch")
        return self


class RecursiveLeafContextOwner:
    """Reconcile leaf inputs with the current job and configured profile owners.

    Natural-language child runs retain the execution owner's ephemeral verified
    job scope so current-job replay remains bound to the live worker lease.
    """

    def __init__(
        self,
        *,
        store: ArtifactStore,
        context_owner: CycleSubstrateContextArtifactOwner,
        admission_owner: ConfiguredCandidateSimulationContextAdmissionOwner | None,
        generic_admission_owner: GenericCycleSimulationAdmissionOwner | None = None,
        verified_nl_job_scope: VerifiedNLJobScope | None = None,
        repo_root: Path | None = None,
    ) -> None:
        if type(context_owner) is not CycleSubstrateContextArtifactOwner:
            raise TypeError("recursive_leaf_context_owner_not_canonical")
        if admission_owner is not None and (
            type(admission_owner) is not ConfiguredCandidateSimulationContextAdmissionOwner
        ):
            raise TypeError("recursive_leaf_admission_owner_not_canonical")
        if generic_admission_owner is not None and (
            type(generic_admission_owner) is not GenericCycleSimulationAdmissionOwner
        ):
            raise TypeError("recursive_leaf_generic_admission_owner_not_canonical")
        if verified_nl_job_scope is not None:
            if type(verified_nl_job_scope) is not VerifiedNLJobScope:
                raise TypeError("recursive_leaf_verified_scope_not_canonical")
            if not verified_nl_job_scope._was_issued_by_verified_nl_execution_owner:
                raise ValueError("recursive_leaf_verified_scope_not_issued")
        if admission_owner is None and generic_admission_owner is None:
            raise TypeError("recursive_leaf_profile_admission_owner_missing")
        if repo_root is not None and (
            not isinstance(repo_root, Path) or not repo_root.is_absolute()
        ):
            raise TypeError("recursive_leaf_repo_root_must_be_absolute_path")
        if (
            context_owner._store is not store
            or (admission_owner is not None and admission_owner._store is not store)
            or (generic_admission_owner is not None and generic_admission_owner.store is not store)
        ):
            raise ValueError("recursive_leaf_store_owner_mismatch")
        self._store = store
        self._context_owner = context_owner
        self._admission_owner = admission_owner
        self._generic_admission_owner = generic_admission_owner
        self._verified_nl_job_scope = verified_nl_job_scope
        self._repo_root = repo_root.resolve() if repo_root is not None else None

    def admit_n4_child_profile_family(
        self,
        *,
        parent_problem: DesignProblem,
        parent_handoff: GenericCycleSimulationContextHandoffV1,
        source_ref: CASArtifactRef,
        source_run_id: str,
        source_repository: GenerationSourceRepository,
    ) -> tuple[tuple[object, ...], dict[str, GenericCycleSimulationContextHandoffV1]]:
        """Recompute the complete persisted N4 child family before admitting profiles.

        The pre-N4 family is an explicit candidate-only input. This method
        reloads the exact source artifact, derives every child from its real
        ``GenerationUnderAResult``, joins the whole set one-to-one to the
        configured family, and only then persists child context handoffs.
        """
        if self._generic_admission_owner is None or self._verified_nl_job_scope is None:
            raise RecursiveGenerationCycleError("recursive_generic_admission_owner_missing")
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository,
        )

        if type(source_repository) is not GenerationSourceRepository:
            raise RecursiveGenerationCycleError("recursive_generic_source_repository_untyped")
        parent = self._generic_admission_owner.resolve_handoff(
            handoff=parent_handoff,
            problem=parent_problem,
            verified_nl_job_scope=self._verified_nl_job_scope,
            context_owner=self._context_owner,
            repo_root=self._repo_root,
        )
        pre_family_ref = parent.n4_child_profile_family_ref
        if pre_family_ref is None:
            raise RecursiveGenerationCycleError(
                "recursive_generic_child_profile_family_not_established"
            )
        configured_family = self._generic_admission_owner.resolve_child_profile_family(
            pre_family_ref,
            parent_handoff=parent,
            parent_problem=parent_problem,
            verified_nl_job_scope=self._verified_nl_job_scope,
            context_owner=self._context_owner,
            repo_root=self._repo_root,
        )
        source = source_repository.load(
            source_ref,
            run_id=source_run_id,
            expected_run_id=parent.run_id,
            expected_job_id=parent.job_id,
            expected_tenant_id=parent.tenant_id,
            expected_cell_id=parent.cell_id,
            context_job_ref=parent.context_job_ref,
            profile_ref=parent.profile_ref,
            n4_child_profile_family_ref=pre_family_ref,
        )
        if (
            source.problem != parent_problem
            or source.cycle_substrate_context != parent.context
            or source.generation_result.design_problem_ref
            != gy_content_hash(parent_problem.model_dump(mode="json"))
            or source.generation_result.status != "generated"
        ):
            raise RecursiveGenerationCycleError("recursive_generic_n4_source_binding_mismatch")
        from polisyos.runtime.quality.design_generation import (
            derive_n4_candidate_child_problems,
        )

        children = derive_n4_candidate_child_problems(
            parent_problem,
            source.generation_result,
            model_id=source.generation_result.model_id,
        )
        if not children:
            raise RecursiveGenerationCycleError("recursive_generic_n4_child_source_empty")
        parent_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            parent_problem
        ).removeprefix("sha256:")
        selections: list[tuple[str, object, GenericCycleSimulationChildSelectionV1]] = []
        for child in children:
            node_ref = "design-problem://" + cycle_job_design_problem_ref(
                child.problem
            ).removeprefix("sha256:")
            selection = _generic_n4_child_selection(
                node_ref=node_ref,
                parent_ref=parent_node_ref,
                parent_problem=parent_problem,
                parent_handoff=parent,
                child_problem=child.problem,
                source_result_ref=child.source_result_ref,
                source_atom_refs=child.source_atom_refs,
                semantic_ref=child.semantic_ref,
                n4_source_ref=source_ref,
            )
            selections.append((node_ref, child, selection))
        selection_refs = tuple(row[2].profile_selection_ref for row in selections)
        configured_refs = tuple(
            member.profile_selection_ref for member in configured_family.children
        )
        if (
            len(selection_refs) != len(set(selection_refs))
            or len(configured_refs) != len(set(configured_refs))
            or set(selection_refs) != set(configured_refs)
        ):
            raise RecursiveGenerationCycleError(
                "recursive_generic_n4_child_family_denominator_mismatch"
            )
        selections_by_profile: list[tuple[str, object, GenericCycleSimulationChildSelectionV1]] = []
        for node_ref, child, selection in selections:
            profile_id = self._generic_admission_owner.configured_profile_id_for_child_selection(
                selection
            )
            member = next(
                (
                    row
                    for row in configured_family.children
                    if row.profile_id == profile_id
                    and row.profile_selection_ref == selection.profile_selection_ref
                ),
                None,
            )
            if member is None:
                raise RecursiveGenerationCycleError(
                    "recursive_generic_n4_child_profile_not_in_pre_family"
                )
            selections_by_profile.append((node_ref, child, selection))
        child_handoffs: dict[str, GenericCycleSimulationContextHandoffV1] = {}
        for node_ref, child, selection in selections_by_profile:
            offer = self._generic_admission_owner.admit_child_context(
                selection=selection,
                job_id=parent.job_id,
                run_id=parent.run_id,
                tenant_id=parent.tenant_id,
                cell_id=parent.cell_id,
                verified_nl_job_scope=self._verified_nl_job_scope,
                context_owner=self._context_owner,
                repo_root=self._repo_root,
            )
            handoff = self._generic_admission_owner.persist_handoff(
                offer=offer,
                problem=child.problem,
                job_id=parent.job_id,
                run_id=parent.run_id,
                tenant_id=parent.tenant_id,
                cell_id=parent.cell_id,
                verified_nl_job_scope=self._verified_nl_job_scope,
                context_owner=self._context_owner,
                repo_root=self._repo_root,
            )
            if handoff.n4_child_profile_family_ref != pre_family_ref:
                raise RecursiveGenerationCycleError(
                    "recursive_generic_n4_child_handoff_family_mismatch"
                )
            current = self._generic_admission_owner.resolve_handoff(
                handoff=handoff,
                problem=child.problem,
                verified_nl_job_scope=self._verified_nl_job_scope,
                context_owner=self._context_owner,
                repo_root=self._repo_root,
                child_selection=selection,
            )
            if current != handoff or node_ref in child_handoffs:
                raise RecursiveGenerationCycleError(
                    "recursive_generic_n4_child_handoff_replay_mismatch"
                )
            child_handoffs[node_ref] = handoff
        if len(child_handoffs) != len(children):
            raise RecursiveGenerationCycleError(
                "recursive_generic_n4_child_handoff_denominator_mismatch"
            )
        return tuple(children), child_handoffs

    def require_current(self, capsule: RecursiveLeafContextCapsule) -> None:
        """Resolve complete child evidence afresh before candidate execution."""
        capsule = RecursiveLeafContextCapsule.model_validate(capsule.model_dump(mode="json"))
        handoff = capsule.handoff
        resolved = self._context_owner.resolve_for_current_job(
            handoff.context_job_ref,
            problem=capsule.problem,
            repo_root=self._repo_root,
            verified_nl_job_scope=self._verified_nl_job_scope,
        )
        if (
            resolved.problem != capsule.problem
            or resolved.context != handoff.context
            or (resolved.job_id, resolved.run_id, resolved.tenant_id, resolved.cell_id)
            != (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id)
        ):
            raise RecursiveGenerationCycleError("recursive_leaf_current_job_binding_mismatch")
        self._require_current_profile(capsule)

    def _require_current_profile(self, capsule: RecursiveLeafContextCapsule) -> None:
        if self._admission_owner is None:
            raise RecursiveGenerationCycleError("recursive_leaf_candidate_admission_owner_missing")
        handoff = capsule.handoff
        offer = self._admission_owner.admit_context(
            problem=capsule.problem,
            job_id=handoff.job_id,
            run_id=handoff.run_id,
            tenant_id=handoff.tenant_id,
            cell_id=handoff.cell_id,
        )
        if offer is None or any(
            getattr(offer, name) != getattr(handoff, name)
            for name in (
                "context",
                "profile",
                "profile_config_ref",
                "model_declaration",
                "model_declaration_ref",
                "ncm_ref",
            )
        ):
            raise RecursiveGenerationCycleError("recursive_leaf_configured_profile_not_current")

    def persist(self, capsule: RecursiveLeafContextCapsule) -> CASArtifactRef:
        """Persist only after the actual job and profile owners reconcile inputs."""
        from polisyos.core import artifacts, canon
        from polisyos.core.artifacts import ArtifactTenantContextInfo

        self.require_current(capsule)
        return self._store.put_json(
            capsule.model_dump(mode="json"),
            artifacts.ArtifactWriteOptions(
                kind="runtime.quality.recursive_leaf_context",
                media_type="application/json",
                schema=artifacts.SchemaInfo(name=capsule.schema_version, version="1.0"),
                inputs=[
                    artifacts.InputRef(
                        artifact_id=capsule.handoff.context_job_ref.artifact_id,
                        role="leaf_context_job",
                    )
                ],
                tenant_context=ArtifactTenantContextInfo(
                    tenant_id=capsule.handoff.tenant_id, cell_id=capsule.handoff.cell_id
                ),
            ),
            canon_spec=canon.CanonSpec(forbid_floats=False),
        )

    def currentness_resolver(
        self,
        ref: CASArtifactRef,
        capsule: RecursiveLeafContextCapsule,
    ) -> Callable[[], bool]:
        """Bind a live currentness callback to one persisted recursive child.

        The callback first replays the exact child capsule at its CAS ref, then
        reconciles that capsule's job context against the active execution
        owner. It is suitable for the child ``GenerationCycleController``'s
        candidate-only lease gate; it does not grant root or protected authority.
        """
        bound_capsule = RecursiveLeafContextCapsule.model_validate(capsule.model_dump(mode="json"))

        def require_current() -> bool:
            handoff = bound_capsule.handoff
            # Resolve the active worker lease before reading the persisted
            # capsule. Historical CAS identity is checked only after the
            # current-job owner admits this exact handoff.
            self.require_current(bound_capsule)
            replayed = self.read(
                ref,
                node_ref=bound_capsule.node_ref,
                parent_ref=bound_capsule.parent_ref,
                problem=bound_capsule.problem,
                expected_job_id=handoff.job_id,
                expected_run_id=handoff.run_id,
                expected_tenant_id=handoff.tenant_id,
                expected_cell_id=handoff.cell_id,
            )
            if replayed != bound_capsule:
                raise RecursiveGenerationCycleError(
                    "recursive_leaf_capsule_currentness_binding_mismatch"
                )
            return True

        return require_current

    def read(
        self,
        ref: CASArtifactRef,
        *,
        node_ref: str,
        parent_ref: str,
        problem: DesignProblem,
        expected_job_id: str,
        expected_run_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
    ) -> RecursiveLeafContextCapsule:
        """Resolve historical CAS evidence and current configuration without an old lease."""
        from polisyos.core import artifacts
        from polisyos.core.artifacts import (
            ArtifactTenantContextInfo,
            load_core_json_artifact,
        )

        if (
            ref.kind != "runtime.quality.recursive_leaf_context"
            or ref.media_type != "application/json"
            or not self._store.verify(ref).ok
        ):
            raise RecursiveGenerationCycleError("recursive_leaf_capsule_ref_invalid")
        raw = self._store.get_bytes(ref)
        if str(ref.artifact_id) != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise RecursiveGenerationCycleError("recursive_leaf_capsule_cas_content_mismatch")
        capsule = RecursiveLeafContextCapsule.model_validate(
            load_core_json_artifact(self._store, ref, raw_payload_bytes=raw)
        )
        if (capsule.node_ref, capsule.parent_ref, capsule.problem) != (
            node_ref,
            parent_ref,
            problem,
        ):
            raise RecursiveGenerationCycleError("recursive_leaf_capsule_reader_binding_mismatch")
        manifest = self._store.get_manifest(ref)
        if manifest.inputs != [
            artifacts.InputRef(
                artifact_id=capsule.handoff.context_job_ref.artifact_id,
                role="leaf_context_job",
            )
        ] or manifest.tenant_context != ArtifactTenantContextInfo(
            tenant_id=expected_tenant_id, cell_id=expected_cell_id
        ):
            raise RecursiveGenerationCycleError("recursive_leaf_capsule_manifest_binding_mismatch")
        historical = self._context_owner.resolve_historical_job_artifact(
            capsule.handoff.context_job_ref,
            problem=problem,
            expected_job_id=expected_job_id,
            expected_run_id=expected_run_id,
            expected_tenant_id=expected_tenant_id,
            expected_cell_id=expected_cell_id,
        )
        if historical.context != capsule.handoff.context or (
            capsule.handoff.job_id,
            capsule.handoff.run_id,
            capsule.handoff.tenant_id,
            capsule.handoff.cell_id,
        ) != (expected_job_id, expected_run_id, expected_tenant_id, expected_cell_id):
            raise RecursiveGenerationCycleError(
                "recursive_leaf_capsule_historical_binding_mismatch"
            )
        self._require_current_profile(capsule)
        return capsule

    @staticmethod
    def _n4_child_profile_set_write_options(
        family: RecursiveN4ChildProfileSetV1,
    ) -> object:
        """Return the complete candidate-only family manifest projection."""
        from polisyos.core import artifacts
        from polisyos.core.artifacts import (
            ArtifactSameInputClosureInfo,
            ArtifactTenantContextInfo,
            input_ref_from_artifact_ref,
        )

        inputs = [
            input_ref_from_artifact_ref(family.source_ref, role="n4_source"),
            input_ref_from_artifact_ref(
                family.n4_child_profile_family_ref,
                role="n4_child_profile_family",
            ),
            input_ref_from_artifact_ref(
                family.parent_handoff.context_job_ref,
                role="parent_context_job",
            ),
            input_ref_from_artifact_ref(
                family.parent_handoff.profile_ref,
                role="parent_generic_profile",
            ),
        ]
        for row in family.children:
            suffix = gy_content_hash({"node_ref": row.node_ref}).removeprefix("sha256:")[:20]
            inputs.extend(
                (
                    input_ref_from_artifact_ref(
                        row.handoff.context_job_ref,
                        role=f"child_context_job:{suffix}",
                    ),
                    input_ref_from_artifact_ref(
                        row.handoff.profile_ref,
                        role=f"child_generic_profile:{suffix}",
                    ),
                )
            )
        return artifacts.ArtifactWriteOptions(
            kind="runtime.quality.recursive_n4_child_profile_set",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name=family.schema_version,
                version="1.0",
            ),
            producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
            canon=artifacts.CanonInfo.from_spec(_N4_CHILD_PROFILE_SET_CANON),
            inputs=inputs,
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=family.tenant_id,
                cell_id=family.cell_id,
            ),
            same_input_closure=ArtifactSameInputClosureInfo(
                closure_id=(
                    f"recursive-n4-child-profile-set:{family.run_id}:"
                    f"{family.job_id}:{family.content_hash}"
                ),
                status="candidate_only",
                run_id=family.run_id,
                job_id=family.job_id,
                tenant_id=family.tenant_id,
                cell_id=family.cell_id,
            ),
        )

    def persist_n4_child_profile_set(
        self,
        *,
        parent_problem: DesignProblem,
        parent_handoff: GenericCycleSimulationContextHandoffV1,
        source_ref: CASArtifactRef,
        child_handoffs: Mapping[str, GenericCycleSimulationContextHandoffV1],
        source_run_id: str,
        source_repository: GenerationSourceRepository,
    ) -> CASArtifactRef:
        """Persist the full child set only after source replay and all owner joins."""
        if self._generic_admission_owner is None or self._verified_nl_job_scope is None:
            raise RecursiveGenerationCycleError("recursive_generic_admission_owner_missing")
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.design_generation import (
            derive_n4_candidate_child_problems,
        )

        parent = self._generic_admission_owner.resolve_handoff(
            handoff=parent_handoff,
            problem=parent_problem,
            verified_nl_job_scope=self._verified_nl_job_scope,
            context_owner=self._context_owner,
            repo_root=self._repo_root,
        )
        if parent.n4_child_profile_family_ref is None:
            raise RecursiveGenerationCycleError(
                "recursive_generic_child_profile_family_not_established"
            )
        self._generic_admission_owner.resolve_child_profile_family(
            parent.n4_child_profile_family_ref,
            parent_handoff=parent,
            parent_problem=parent_problem,
            verified_nl_job_scope=self._verified_nl_job_scope,
            context_owner=self._context_owner,
            repo_root=self._repo_root,
        )
        source = source_repository.load(
            source_ref,
            run_id=source_run_id,
            expected_run_id=parent.run_id,
            expected_job_id=parent.job_id,
            expected_tenant_id=parent.tenant_id,
            expected_cell_id=parent.cell_id,
            context_job_ref=parent.context_job_ref,
            profile_ref=parent.profile_ref,
            n4_child_profile_family_ref=parent.n4_child_profile_family_ref,
        )
        if source.problem != parent_problem or source.generation_result.status != "generated":
            raise RecursiveGenerationCycleError("recursive_generic_n4_source_binding_mismatch")
        actual_children = derive_n4_candidate_child_problems(
            parent_problem,
            source.generation_result,
            model_id=source.generation_result.model_id,
        )
        actual_by_ref = {
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:"): child
            for child in actual_children
        }
        if len(actual_by_ref) != len(actual_children) or set(child_handoffs) != set(actual_by_ref):
            raise RecursiveGenerationCycleError("recursive_generic_n4_child_denominator_mismatch")
        rows: list[RecursiveN4ChildProfileBindingV1] = []
        parent_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            parent_problem
        ).removeprefix("sha256:")
        for node_ref, child in actual_by_ref.items():
            handoff = child_handoffs[node_ref]
            if type(handoff) is not GenericCycleSimulationContextHandoffV1:
                raise RecursiveGenerationCycleError("recursive_generic_child_handoff_untyped")
            selection = _generic_n4_child_selection(
                node_ref=node_ref,
                parent_ref=parent_node_ref,
                parent_problem=parent_problem,
                parent_handoff=parent,
                child_problem=child.problem,
                source_result_ref=child.source_result_ref,
                source_atom_refs=child.source_atom_refs,
                semantic_ref=child.semantic_ref,
                n4_source_ref=source_ref,
            )
            selected_profile_id = (
                self._generic_admission_owner.configured_profile_id_for_child_selection(selection)
            )
            if (
                handoff.profile.profile_id != selected_profile_id
                or handoff.n4_child_profile_family_ref != parent.n4_child_profile_family_ref
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_generic_child_handoff_profile_join_mismatch"
                )
            current = self._generic_admission_owner.resolve_handoff(
                handoff=handoff,
                problem=child.problem,
                verified_nl_job_scope=self._verified_nl_job_scope,
                context_owner=self._context_owner,
                repo_root=self._repo_root,
                child_selection=selection,
            )
            if current != handoff:
                raise RecursiveGenerationCycleError("recursive_generic_child_handoff_not_current")
            rows.append(
                RecursiveN4ChildProfileBindingV1(
                    node_ref=node_ref,
                    parent_ref=parent_node_ref,
                    problem=child.problem,
                    source_ref=source_ref,
                    source_result_ref=child.source_result_ref,
                    source_atom_refs=child.source_atom_refs,
                    semantic_ref=child.semantic_ref,
                    selection=selection,
                    handoff=handoff,
                )
            )
        payload: dict[str, object] = {
            "schema_version": "policyos.runtime.quality.recursive_n4_child_profile_set.v1",
            "authority_purpose": "cycle_input_candidate_only",
            "job_id": parent.job_id,
            "run_id": parent.run_id,
            "tenant_id": parent.tenant_id,
            "cell_id": parent.cell_id,
            "source_run_id": source.run_id,
            "parent_problem": parent_problem.model_dump(mode="json"),
            "parent_problem_ref": parent.context.design_problem_ref,
            "parent_handoff": parent.model_dump(mode="json"),
            "n4_child_profile_family_ref": parent.n4_child_profile_family_ref.model_dump(
                mode="json"
            ),
            "source_ref": source_ref.model_dump(mode="json"),
            "children": [row.model_dump(mode="json") for row in rows],
        }
        family = RecursiveN4ChildProfileSetV1.model_validate(
            {**payload, "content_hash": gy_content_hash(payload)}
        )
        options = self._n4_child_profile_set_write_options(family)
        ref = self._store.put_json(
            family.model_dump(mode="json"),
            options,
            canon_spec=_N4_CHILD_PROFILE_SET_CANON,
            return_selected_profile=True,
        )
        if type(ref) is not CASArtifactRef or ref.manifest_profile_sha256 is None:
            raise RecursiveGenerationCycleError(
                "recursive_n4_child_profile_set_selected_ref_not_returned"
            )
        self.load_n4_child_profile_set(
            ref,
            expected_job_id=parent.job_id,
            expected_run_id=parent.run_id,
            expected_tenant_id=parent.tenant_id,
            expected_cell_id=parent.cell_id,
            expected_parent_handoff=parent,
            source_repository=source_repository,
        )
        return ref

    def load_n4_child_profile_set(
        self,
        ref: CASArtifactRef,
        *,
        expected_job_id: str,
        expected_run_id: str,
        expected_tenant_id: str,
        expected_cell_id: str,
        expected_parent_handoff: GenericCycleSimulationContextHandoffV1,
        source_repository: GenerationSourceRepository,
    ) -> RecursiveN4ChildProfileSetV1:
        """Resolve the exact persisted set against real source and historical owners."""
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.runtime.quality.cycle_substrate import (
            cycle_job_design_problem_ref,
        )
        from polisyos.runtime.quality.design_generation import (
            derive_n4_candidate_child_problems,
        )
        from polisyos.runtime.quality.generation_source import (
            _has_owner_profile,
            _ref_selects_manifest,
        )

        if (
            type(ref) is not CASArtifactRef
            or ref.kind != "runtime.quality.recursive_n4_child_profile_set"
            or ref.media_type != "application/json"
            or not self._store.verify(ref).ok
        ):
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_set_ref_invalid")
        raw = self._store.get_bytes(ref)
        if str(ref.artifact_id) != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_set_cas_mismatch")
        family = RecursiveN4ChildProfileSetV1.model_validate(
            load_core_json_artifact(self._store, ref, raw_payload_bytes=raw)
        )
        if (
            family.job_id,
            family.run_id,
            family.tenant_id,
            family.cell_id,
            family.parent_handoff,
        ) != (
            expected_job_id,
            expected_run_id,
            expected_tenant_id,
            expected_cell_id,
            expected_parent_handoff,
        ) or (
            family.n4_child_profile_family_ref
            != expected_parent_handoff.n4_child_profile_family_ref
        ):
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_set_scope_mismatch")
        manifest = self._store.get_manifest(ref)
        options = self._n4_child_profile_set_write_options(family)
        if not _ref_selects_manifest(ref, manifest) or not _has_owner_profile(manifest, options):
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_set_manifest_mismatch")
        if self._generic_admission_owner is None:
            raise RecursiveGenerationCycleError("recursive_generic_admission_owner_missing")
        historical_parent = self._context_owner.resolve_historical_job_artifact(
            family.parent_handoff.context_job_ref,
            problem=family.parent_problem,
            expected_job_id=family.job_id,
            expected_run_id=family.run_id,
            expected_tenant_id=family.tenant_id,
            expected_cell_id=family.cell_id,
        )
        if historical_parent.context != family.parent_handoff.context:
            raise RecursiveGenerationCycleError(
                "recursive_n4_child_profile_parent_context_mismatch"
            )
        self._generic_admission_owner.resolve_profile_historical(
            family.parent_handoff.profile_ref,
            expected_profile=family.parent_handoff.profile,
            job_id=family.job_id,
            run_id=family.run_id,
            tenant_id=family.tenant_id,
            cell_id=family.cell_id,
        )
        if family.n4_child_profile_family_ref is None:
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_pre_family_missing")
        configured_family = self._generic_admission_owner.resolve_child_profile_family_historical(
            family.n4_child_profile_family_ref,
            expected_parent_handoff=family.parent_handoff,
            expected_parent_problem=family.parent_problem,
        )
        source = source_repository.load(
            family.source_ref,
            run_id=family.source_run_id,
            expected_run_id=family.run_id,
            expected_job_id=family.job_id,
            expected_tenant_id=family.tenant_id,
            expected_cell_id=family.cell_id,
            context_job_ref=family.parent_handoff.context_job_ref,
            profile_ref=family.parent_handoff.profile_ref,
            n4_child_profile_family_ref=family.n4_child_profile_family_ref,
        )
        if (
            source.problem != family.parent_problem
            or source.generation_result.status != "generated"
        ):
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_source_mismatch")
        actual_children = derive_n4_candidate_child_problems(
            family.parent_problem,
            source.generation_result,
            model_id=source.generation_result.model_id,
        )
        actual_by_ref = {
            "design-problem://"
            + cycle_job_design_problem_ref(child.problem).removeprefix("sha256:"): child
            for child in actual_children
        }
        rows_by_ref = {row.node_ref: row for row in family.children}
        if len(rows_by_ref) != len(family.children) or set(rows_by_ref) != set(actual_by_ref):
            raise RecursiveGenerationCycleError(
                "recursive_n4_child_profile_set_denominator_mismatch"
            )
        parent_node_ref = "design-problem://" + cycle_job_design_problem_ref(
            family.parent_problem
        ).removeprefix("sha256:")
        configured_members = {member.profile_id: member for member in configured_family.children}
        for node_ref, child in actual_by_ref.items():
            row = rows_by_ref[node_ref]
            expected_selection = _generic_n4_child_selection(
                node_ref=node_ref,
                parent_ref=parent_node_ref,
                parent_problem=family.parent_problem,
                parent_handoff=family.parent_handoff,
                child_problem=child.problem,
                source_result_ref=child.source_result_ref,
                source_atom_refs=child.source_atom_refs,
                semantic_ref=child.semantic_ref,
                n4_source_ref=family.source_ref,
            )
            if (
                row.parent_ref != parent_node_ref
                or row.problem != child.problem
                or row.source_ref != family.source_ref
                or row.source_result_ref != child.source_result_ref
                or row.source_atom_refs != child.source_atom_refs
                or row.semantic_ref != child.semantic_ref
                or row.selection != expected_selection
                or row.handoff.n4_child_profile_family_ref != family.n4_child_profile_family_ref
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_n4_child_profile_source_join_mismatch"
                )
            member = configured_members.get(row.handoff.profile.profile_id)
            if (
                member is None
                or member.profile_selection_ref != row.selection.profile_selection_ref
                or member.profile_content_hash != row.handoff.profile.content_hash
                or member.profile_ref != row.handoff.profile_ref
            ):
                raise RecursiveGenerationCycleError("recursive_n4_child_profile_not_in_pre_family")
            historical = self._context_owner.resolve_historical_job_artifact(
                row.handoff.context_job_ref,
                problem=row.problem,
                expected_job_id=family.job_id,
                expected_run_id=family.run_id,
                expected_tenant_id=family.tenant_id,
                expected_cell_id=family.cell_id,
            )
            if historical.context != row.handoff.context:
                raise RecursiveGenerationCycleError("recursive_n4_child_profile_context_mismatch")
            self._generic_admission_owner.resolve_profile_historical(
                row.handoff.profile_ref,
                expected_profile=row.handoff.profile,
                job_id=family.job_id,
                run_id=family.run_id,
                tenant_id=family.tenant_id,
                cell_id=family.cell_id,
            )
        return family

    def require_current_n4_child_profile_set(
        self,
        ref: CASArtifactRef,
        *,
        expected_parent_handoff: GenericCycleSimulationContextHandoffV1,
        source_repository: GenerationSourceRepository,
    ) -> RecursiveN4ChildProfileSetV1:
        """Replay the complete set and every profile against the active issued lease."""
        if self._generic_admission_owner is None or self._verified_nl_job_scope is None:
            raise RecursiveGenerationCycleError("recursive_generic_admission_owner_missing")
        family = self.load_n4_child_profile_set(
            ref,
            expected_job_id=expected_parent_handoff.job_id,
            expected_run_id=expected_parent_handoff.run_id,
            expected_tenant_id=expected_parent_handoff.tenant_id,
            expected_cell_id=expected_parent_handoff.cell_id,
            expected_parent_handoff=expected_parent_handoff,
            source_repository=source_repository,
        )
        self._generic_admission_owner.resolve_handoff(
            handoff=family.parent_handoff,
            problem=family.parent_problem,
            verified_nl_job_scope=self._verified_nl_job_scope,
            context_owner=self._context_owner,
            repo_root=self._repo_root,
        )
        if family.n4_child_profile_family_ref is None:
            raise RecursiveGenerationCycleError("recursive_n4_child_profile_pre_family_missing")
        self._generic_admission_owner.resolve_child_profile_family(
            family.n4_child_profile_family_ref,
            parent_handoff=family.parent_handoff,
            parent_problem=family.parent_problem,
            verified_nl_job_scope=self._verified_nl_job_scope,
            context_owner=self._context_owner,
            repo_root=self._repo_root,
        )
        for row in family.children:
            self._generic_admission_owner.resolve_handoff(
                handoff=row.handoff,
                problem=row.problem,
                verified_nl_job_scope=self._verified_nl_job_scope,
                context_owner=self._context_owner,
                repo_root=self._repo_root,
                child_selection=row.selection,
            )
        return family

    def persist_generic_capsule(
        self,
        capsule: RecursiveLeafContextCapsuleV2,
        *,
        parent_handoff: GenericCycleSimulationContextHandoffV1,
        source_repository: GenerationSourceRepository,
    ) -> CASArtifactRef:
        """Persist a generic N5 capsule only after whole-family currentness replay."""
        family = self.require_current_n4_child_profile_set(
            capsule.n4_child_profile_set_ref,
            expected_parent_handoff=parent_handoff,
            source_repository=source_repository,
        )
        row = next(
            (item for item in family.children if item.node_ref == capsule.node_ref),
            None,
        )
        if (
            row is None
            or row.problem != capsule.problem
            or row.handoff != capsule.handoff
            or row.selection != capsule.child_selection
        ):
            raise RecursiveGenerationCycleError("recursive_generic_capsule_family_binding_mismatch")

        ref = self._store.put_json(
            capsule.model_dump(mode="json"),
            self._generic_capsule_write_options(capsule),
            canon_spec=_GENERIC_LEAF_CAPSULE_CANON,
            return_selected_profile=True,
        )
        if type(ref) is not CASArtifactRef or ref.manifest_profile_sha256 is None:
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_selected_ref_not_returned"
            )
        return ref

    @staticmethod
    def _generic_capsule_write_options(
        capsule: RecursiveLeafContextCapsuleV2,
    ) -> ArtifactWriteOptions:
        """Return the exact manifest profile used for a generic leaf capsule."""
        from polisyos.core import artifacts
        from polisyos.core.artifacts import (
            ArtifactTenantContextInfo,
            input_ref_from_artifact_ref,
        )

        if type(capsule) is not RecursiveLeafContextCapsuleV2:
            raise RecursiveGenerationCycleError("recursive_generic_capsule_untyped")
        return artifacts.ArtifactWriteOptions(
            kind="runtime.quality.recursive_leaf_context",
            media_type="application/json",
            schema=artifacts.SchemaInfo(name=capsule.schema_version, version="2.0"),
            producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
            canon=artifacts.CanonInfo.from_spec(_GENERIC_LEAF_CAPSULE_CANON),
            inputs=[
                input_ref_from_artifact_ref(
                    capsule.handoff.context_job_ref,
                    role="leaf_context_job",
                ),
                input_ref_from_artifact_ref(
                    capsule.handoff.profile_ref,
                    role="generic_cycle_simulation_profile",
                ),
                input_ref_from_artifact_ref(capsule.n4_source_ref, role="n4_source"),
                input_ref_from_artifact_ref(
                    capsule.n4_child_profile_family_ref,
                    role="n4_child_profile_family",
                ),
                input_ref_from_artifact_ref(
                    capsule.n4_child_profile_set_ref,
                    role="n4_child_profile_set",
                ),
            ],
            tenant_context=ArtifactTenantContextInfo(
                tenant_id=capsule.handoff.tenant_id,
                cell_id=capsule.handoff.cell_id,
            ),
        )

    def resolve_generic_capsule_historical(
        self,
        ref: CASArtifactRef,
        *,
        expected_node_ref: str,
        expected_parent_ref: str,
        expected_problem: DesignProblem,
        expected_parent_handoff: GenericCycleSimulationContextHandoffV1,
        expected_child_profile_set_ref: CASArtifactRef,
        source_repository: GenerationSourceRepository,
    ) -> RecursiveLeafContextCapsuleV2:
        """Reopen a selected generic capsule and its complete historical N4 family.

        This is a read-only historical owner path. It does not create a worker
        lease, re-resolve current configuration, or grant simulation authority.
        The expected parent handoff and child-profile-set ref must come from the
        independently reopened compiled owner, not from the capsule itself.
        """
        from polisyos.core.artifacts import load_core_json_artifact
        from polisyos.runtime.quality.generation_source import (
            GenerationSourceRepository as CanonicalSourceRepository,
        )
        from polisyos.runtime.quality.generation_source import (
            _has_owner_profile,
            _ref_selects_manifest,
        )

        if (
            type(ref) is not CASArtifactRef
            or ref.kind != "runtime.quality.recursive_leaf_context"
            or ref.media_type != "application/json"
            or ref.manifest_profile_sha256 is None
            or type(expected_node_ref) is not str
            or not expected_node_ref
            or type(expected_parent_ref) is not str
            or not expected_parent_ref
            or type(expected_problem) is not DesignProblem
            or type(expected_parent_handoff) is not GenericCycleSimulationContextHandoffV1
            or type(expected_child_profile_set_ref) is not CASArtifactRef
            or expected_child_profile_set_ref.kind
            != "runtime.quality.recursive_n4_child_profile_set"
            or expected_child_profile_set_ref.media_type != "application/json"
            or expected_child_profile_set_ref.manifest_profile_sha256 is None
            or expected_parent_handoff.context_job_ref.manifest_profile_sha256 is None
            or expected_parent_handoff.profile_ref.manifest_profile_sha256 is None
            or expected_parent_handoff.n4_child_profile_family_ref is None
            or expected_parent_handoff.n4_child_profile_family_ref.manifest_profile_sha256 is None
            or type(source_repository) is not CanonicalSourceRepository
            or source_repository.store is not self._store
            or self._generic_admission_owner is None
            or self._generic_admission_owner.store is not self._store
        ):
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_historical_inputs_invalid"
            )
        expected_scope = (
            expected_parent_handoff.job_id,
            expected_parent_handoff.run_id,
            expected_parent_handoff.tenant_id,
            expected_parent_handoff.cell_id,
        )
        if (
            expected_parent_handoff.profile.profile_selection_kind != "problem"
            or not self._store.verify(ref).ok
        ):
            raise RecursiveGenerationCycleError("recursive_generic_capsule_historical_ref_invalid")
        raw = self._store.get_bytes(ref)
        if str(ref.artifact_id) != "sha256:" + hashlib.sha256(raw).hexdigest():
            raise RecursiveGenerationCycleError("recursive_generic_capsule_historical_cas_mismatch")
        manifest = self._store.get_manifest(ref)
        if not _ref_selects_manifest(ref, manifest):
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_historical_profile_mismatch"
            )
        try:
            capsule = RecursiveLeafContextCapsuleV2.model_validate(
                load_core_json_artifact(self._store, ref, raw_payload_bytes=raw)
            )
        except (TypeError, ValueError) as exc:
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_historical_payload_invalid"
            ) from exc
        if not _has_owner_profile(manifest, self._generic_capsule_write_options(capsule)):
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_historical_manifest_mismatch"
            )
        if (
            capsule.node_ref != expected_node_ref
            or capsule.parent_ref != expected_parent_ref
            or capsule.problem != expected_problem
            or capsule.child_selection.parent_handoff != expected_parent_handoff
            or capsule.n4_child_profile_set_ref != expected_child_profile_set_ref
            or capsule.n4_source_ref.manifest_profile_sha256 is None
            or capsule.n4_child_profile_family_ref.manifest_profile_sha256 is None
            or capsule.handoff.context_job_ref.manifest_profile_sha256 is None
            or capsule.handoff.profile_ref.manifest_profile_sha256 is None
            or capsule.handoff.n4_child_profile_family_ref is None
            or capsule.handoff.n4_child_profile_family_ref.manifest_profile_sha256 is None
            or capsule.handoff.n4_child_profile_family_ref
            != expected_parent_handoff.n4_child_profile_family_ref
            or (
                capsule.handoff.job_id,
                capsule.handoff.run_id,
                capsule.handoff.tenant_id,
                capsule.handoff.cell_id,
            )
            != expected_scope
        ):
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_historical_binding_mismatch"
            )
        family = self.load_n4_child_profile_set(
            expected_child_profile_set_ref,
            expected_job_id=expected_parent_handoff.job_id,
            expected_run_id=expected_parent_handoff.run_id,
            expected_tenant_id=expected_parent_handoff.tenant_id,
            expected_cell_id=expected_parent_handoff.cell_id,
            expected_parent_handoff=expected_parent_handoff,
            source_repository=source_repository,
        )
        matching_rows = tuple(row for row in family.children if row.node_ref == expected_node_ref)
        if (
            len(matching_rows) != 1
            or family.source_ref != capsule.n4_source_ref
            or family.n4_child_profile_family_ref != capsule.n4_child_profile_family_ref
            or matching_rows[0].parent_ref != expected_parent_ref
            or matching_rows[0].problem != capsule.problem
            or matching_rows[0].selection != capsule.child_selection
            or matching_rows[0].handoff != capsule.handoff
        ):
            raise RecursiveGenerationCycleError(
                "recursive_generic_capsule_historical_family_mismatch"
            )
        return capsule

    def generic_root_currentness_resolver(
        self,
        *,
        handoff: GenericCycleSimulationContextHandoffV1,
        problem: DesignProblem,
        currentness: Callable[[], bool],
    ) -> Callable[[], bool]:
        """Bind an exact generic root/parent handoff to its live lease and family."""
        if (
            self._generic_admission_owner is None
            or self._verified_nl_job_scope is None
            or type(handoff) is not GenericCycleSimulationContextHandoffV1
            or handoff.profile.profile_selection_kind != "problem"
            or not callable(currentness)
        ):
            raise RecursiveGenerationCycleError("recursive_generic_root_owner_incomplete")

        def require_current() -> bool:
            if currentness() is not True:
                raise RecursiveGenerationCycleError("recursive_generic_root_lease_not_current")
            resolved = self._generic_admission_owner.resolve_handoff(
                handoff=handoff,
                problem=problem,
                verified_nl_job_scope=self._verified_nl_job_scope,
                context_owner=self._context_owner,
                repo_root=self._repo_root,
            )
            if handoff.n4_child_profile_family_ref is not None:
                self._generic_admission_owner.resolve_child_profile_family(
                    handoff.n4_child_profile_family_ref,
                    parent_handoff=handoff,
                    parent_problem=problem,
                    verified_nl_job_scope=self._verified_nl_job_scope,
                    context_owner=self._context_owner,
                    repo_root=self._repo_root,
                )
            if resolved != handoff or currentness() is not True:
                raise RecursiveGenerationCycleError("recursive_generic_root_handoff_not_current")
            return True

        return require_current

    def generic_currentness_resolver(
        self,
        capsule_ref: CASArtifactRef,
        capsule: RecursiveLeafContextCapsuleV2,
        *,
        parent_handoff: GenericCycleSimulationContextHandoffV1,
        source_repository: GenerationSourceRepository,
    ) -> Callable[[], bool]:
        """Bind the N5 callback to the persisted family and exact child capsule."""

        def require_current() -> bool:
            from polisyos.core.artifacts import load_core_json_artifact

            family = self.require_current_n4_child_profile_set(
                capsule.n4_child_profile_set_ref,
                expected_parent_handoff=parent_handoff,
                source_repository=source_repository,
            )
            family_row = next(
                (item for item in family.children if item.node_ref == capsule.node_ref),
                None,
            )
            if (
                family_row is None
                or family_row.problem != capsule.problem
                or family_row.handoff != capsule.handoff
                or family_row.selection != capsule.child_selection
                or family.n4_child_profile_family_ref != capsule.n4_child_profile_family_ref
                or family.source_ref != capsule.n4_source_ref
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_generic_capsule_family_binding_mismatch"
                )

            if (
                capsule_ref.kind != "runtime.quality.recursive_leaf_context"
                or capsule_ref.manifest_profile_sha256 is None
                or not self._store.verify(capsule_ref).ok
            ):
                raise RecursiveGenerationCycleError("recursive_generic_capsule_ref_invalid")
            body = self._store.get_bytes(capsule_ref)
            if str(capsule_ref.artifact_id) != "sha256:" + hashlib.sha256(body).hexdigest():
                raise RecursiveGenerationCycleError("recursive_generic_capsule_cas_mismatch")
            replayed = RecursiveLeafContextCapsuleV2.model_validate(
                load_core_json_artifact(self._store, capsule_ref, raw_payload_bytes=body)
            )
            manifest = self._store.get_manifest(capsule_ref)
            from polisyos.runtime.quality.generation_source import (
                _has_owner_profile,
                _ref_selects_manifest,
            )

            if (
                replayed != capsule
                or not _ref_selects_manifest(capsule_ref, manifest)
                or not _has_owner_profile(
                    manifest,
                    self._generic_capsule_write_options(capsule),
                )
            ):
                raise RecursiveGenerationCycleError("recursive_generic_capsule_manifest_mismatch")
            return True

        return require_current


class RecursiveCycleBudget(_StrictModel):
    """Explicit recursion and leaf-cycle limits owned by the thin router."""

    max_depth: int = Field(ge=0, le=99)
    max_nodes: int = Field(ge=1, le=100)
    min_cycles_per_leaf: int = Field(ge=1)
    max_cycles_per_leaf: int = Field(ge=1)

    @model_validator(mode="after")
    def _cycle_range_is_coherent(self) -> RecursiveCycleBudget:
        if self.min_cycles_per_leaf > self.max_cycles_per_leaf:
            raise ValueError("recursive_cycle_budget_range_incoherent")
        return self


def _legacy_supplied_field_tree(value: object, payload: object) -> object:
    """Preserve supplied v1 fields, including JSON-normalized map keys."""

    if isinstance(value, BaseModel) and isinstance(payload, dict):
        fields_by_key = {
            key: name
            for name, field in type(value).model_fields.items()
            for key in (name, field.alias, field.serialization_alias)
            if isinstance(key, str)
        }
        return {
            key: _legacy_supplied_field_tree(getattr(value, fields_by_key[key]), item)
            for key, item in payload.items()
            if key in fields_by_key and fields_by_key[key] in value.model_fields_set
        }
    if isinstance(value, Mapping) and isinstance(payload, dict):
        return {
            key: _legacy_supplied_field_tree(
                next(
                    (
                        original_value
                        for original_key, original_value in value.items()
                        if original_key == key or str(original_key) == key
                    ),
                    item,
                ),
                item,
            )
            for key, item in payload.items()
        }
    if isinstance(value, (tuple, list)) and isinstance(payload, (tuple, list)):
        return [
            _legacy_supplied_field_tree(original, item)
            for original, item in zip(value, payload, strict=True)
        ]
    return payload


class ParentJointCandidateSourceMember(_StrictModel):
    """One exact parent-frame N4 member selected for a candidate joint run."""

    child_node_ref: str = Field(min_length=1)
    child_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    semantic_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_candidate_id: str = Field(min_length=1)
    source_candidate_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    source_atom_id: str = Field(min_length=1)
    source_atom_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parent_problem_frame_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ParentJointCandidateSelectionV1(_StrictModel):
    """Content-bound, candidate-only selection of one actual N4 member per child."""

    schema_version: Literal[
        "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v1"
    ] = "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v1"
    authority_purpose: Literal["candidate_only"] = "candidate_only"
    selection_rule: Literal["n4_unique_parent_source_members.v1"] = (
        "n4_unique_parent_source_members.v1"
    )
    parent_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    n4_source_ref: CASArtifactRef
    n4_source_result_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    context_job_ref: CASArtifactRef
    profile_ref: CASArtifactRef
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    world_model_record_ref: str = Field(min_length=1)
    world_model_record_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    outcome_variable: str = Field(min_length=1)
    child_node_refs: tuple[str, ...] = Field(min_length=2)
    members: tuple[ParentJointCandidateSourceMember, ...] = Field(min_length=2)
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_selected_source_members(self) -> ParentJointCandidateSelectionV1:
        if (
            type(self.n4_source_ref) is not CASArtifactRef
            or self.n4_source_ref.kind != "runtime.generation_source_handoff"
            or self.n4_source_ref.media_type != "application/json"
            or type(self.context_job_ref) is not CASArtifactRef
            or self.context_job_ref.kind != "runtime.quality.cycle_substrate_context_job"
            or self.context_job_ref.media_type != "application/json"
            or type(self.profile_ref) is not CASArtifactRef
            or self.profile_ref.kind != "runtime.quality.generic_cycle_simulation_profile"
            or self.profile_ref.media_type != "application/json"
        ):
            raise ValueError("recursive_parent_joint_candidate_owner_refs_invalid")
        if (
            len(self.child_node_refs) != len(set(self.child_node_refs))
            or tuple(member.child_node_ref for member in self.members) != self.child_node_refs
            or any(
                member.parent_problem_frame_ref != self.parent_design_problem_ref
                for member in self.members
            )
            or len({member.source_candidate_id for member in self.members}) != len(self.members)
            or len({member.source_atom_content_hash for member in self.members})
            != len(self.members)
        ):
            raise ValueError("recursive_parent_joint_candidate_member_denominator_invalid")
        payload = self.model_dump(mode="json", exclude={"content_hash"})
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_parent_joint_candidate_selection_hash_mismatch")
        return self


class ParentJointCandidateSelectionV2(ParentJointCandidateSelectionV1):
    """Bind an explicit all-source-member diagnostic without claiming composition.

    N4 candidates are alternatives. This receipt records the caller's request
    to inspect every unique source member as a hypothetical candidate
    diagnostic; it does not make that set an authored compound design or prove
    child-to-parent refinement.
    """

    schema_version: Literal[
        "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v2"
    ] = "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v2"
    selection_rule: Literal["hypothetical_all_unique_n4_source_members.v2"] = (
        "hypothetical_all_unique_n4_source_members.v2"
    )
    candidate_intent: Literal["n4_unique_parent_source_members.v1"]
    member_basis: Literal["hypothetical_all_unique_n4_source_members"] = (
        "hypothetical_all_unique_n4_source_members"
    )
    source_candidate_relationship: Literal["alternatives"] = "alternatives"
    composition_status: Literal["not_established"] = "not_established"
    composition_limitation_code: Literal[
        "n4_source_candidates_are_alternatives_not_authored_compound_design"
    ] = "n4_source_candidates_are_alternatives_not_authored_compound_design"
    child_to_parent_refinement_status: Literal["not_established"] = "not_established"
    child_to_parent_refinement_limitation_code: Literal[
        "child_to_parent_refinement_rule_not_established"
    ] = "child_to_parent_refinement_rule_not_established"
    joint_simulation_request_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class ParentJointCandidateSelectionV4(ParentJointCandidateSelectionV2):
    """Bind configured numeric projections without asserting authored composition."""

    schema_version: Literal[
        "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v4"
    ] = "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v4"
    component_materializations: tuple[
        CandidateScenarioMaterializationV1 | CandidateScenarioNumericMaterializationV1, ...
    ] = Field(min_length=2)

    @model_validator(mode="after")
    def _bind_materialized_source_members(self) -> ParentJointCandidateSelectionV4:
        if len(self.members) != len(self.component_materializations) or any(
            materialization.candidate_id != member.source_candidate_id
            or materialization.original_atom_hash != member.source_atom_content_hash
            or materialization.problem_ref != self.parent_design_problem_ref
            or materialization.context_job_ref != str(self.context_job_ref.artifact_id)
            or materialization.source_handoff_ref != str(self.n4_source_ref.artifact_id)
            or materialization.world_model_record_hash != self.world_model_record_content_hash
            for member, materialization in zip(
                self.members, self.component_materializations, strict=True
            )
        ):
            raise ValueError("recursive_parent_joint_materialization_member_mismatch")
        derived_hashes = tuple(
            item.derived_n5_atom.content_hash for item in self.component_materializations
        )
        if len(set(derived_hashes)) != len(derived_hashes):
            raise ValueError("recursive_parent_joint_materialization_duplicate")
        return self


class ParentJointAuthoredRelationV1(_StrictModel):
    """Persist one explicit, candidate-only relation and its actual L6 projections."""

    schema_version: Literal[
        "policyos.runtime.recursive_generation_cycle.authored_joint_relation.v1"
    ] = "policyos.runtime.recursive_generation_cycle.authored_joint_relation.v1"
    authority_purpose: Literal["candidate_only"] = "candidate_only"
    candidate_intent: Literal["authored_joint_components.v1"] = "authored_joint_components.v1"
    source_candidate_relationship: Literal["alternatives"] = "alternatives"
    selected_member_relationship: Literal["joint_components"] = "joint_components"
    composition_status: Literal["authored_candidate"] = "authored_candidate"
    child_to_parent_refinement_status: Literal["not_established"] = "not_established"
    job_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    tenant_id: str = Field(min_length=1)
    cell_id: str = Field(min_length=1)
    source_run_id: str = Field(min_length=1)
    intent_digest: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    request_payload_ref: CASArtifactRef
    n4_source_ref: CASArtifactRef
    n4_source_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    n4_source_result_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    parent_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    context_job_ref: CASArtifactRef
    context_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    profile_ref: CASArtifactRef
    profile_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    profile_selection_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    world_model_record_ref: str = Field(min_length=1)
    world_model_record_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    outcome_variable: str = Field(min_length=1)
    members: tuple[ParentJointCandidateSourceMember, ...] = Field(min_length=2)
    component_materializations: tuple[
        CandidateScenarioMaterializationV1 | CandidateScenarioNumericMaterializationV1, ...
    ] = Field(min_length=2)
    joint_simulation_request_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _bind_source_and_materializations(self) -> ParentJointAuthoredRelationV1:
        for ref, kind in (
            (self.request_payload_ref, "runtime.control_job_payload.natural_language_run"),
            (self.n4_source_ref, "runtime.generation_source_handoff"),
            (self.context_job_ref, "runtime.quality.cycle_substrate_context_job"),
            (self.profile_ref, "runtime.quality.generic_cycle_simulation_profile"),
        ):
            if (
                type(ref) is not CASArtifactRef
                or ref.kind != kind
                or ref.media_type != "application/json"
                or (
                    kind == "runtime.control_job_payload.natural_language_run"
                    and not ref.manifest_profile_sha256
                )
            ):
                raise ValueError("recursive_authored_joint_source_ref_invalid")
        if len(self.members) != len(self.component_materializations) or len(
            {member.source_candidate_id for member in self.members}
        ) != len(self.members):
            raise ValueError("recursive_authored_joint_member_denominator_invalid")
        for member, materialization in zip(
            self.members, self.component_materializations, strict=True
        ):
            if (
                member.parent_problem_frame_ref != self.parent_design_problem_ref
                or materialization.candidate_id != member.source_candidate_id
                or materialization.original_atom_hash != member.source_atom_content_hash
                or materialization.problem_ref != self.parent_design_problem_ref
                or materialization.context_hash != self.context_content_hash
                or materialization.context_job_ref != str(self.context_job_ref.artifact_id)
                or materialization.source_handoff_ref != str(self.n4_source_ref.artifact_id)
                or materialization.profile_hash != self.profile_content_hash
                or materialization.world_model_record_hash != self.world_model_record_content_hash
                or materialization.derived_n5_atom.problem_frame_ref
                != self.parent_design_problem_ref
                or materialization.derived_n5_atom.world_model_record_ref
                != self.world_model_record_ref
            ):
                raise ValueError("recursive_authored_joint_materialization_binding_mismatch")
        if self.content_hash != gy_content_hash(
            self.model_dump(mode="json", exclude={"content_hash"})
        ):
            raise ValueError("recursive_authored_joint_relation_hash_mismatch")
        return self


class ParentJointCandidateSelectionV3(ParentJointCandidateSelectionV1):
    """Select a requestor-authored joint candidate without claiming coupling authority."""

    schema_version: Literal[
        "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v3"
    ] = "policyos.runtime.recursive_generation_cycle.parent_joint_candidate_selection.v3"
    selection_rule: Literal["authored_joint_components.v1"] = "authored_joint_components.v1"
    candidate_intent: Literal["authored_joint_components.v1"] = "authored_joint_components.v1"
    source_candidate_relationship: Literal["alternatives"] = "alternatives"
    selected_member_relationship: Literal["joint_components"] = "joint_components"
    composition_status: Literal["authored_candidate"] = "authored_candidate"
    child_to_parent_refinement_status: Literal["not_established"] = "not_established"
    child_to_parent_refinement_limitation_code: Literal[
        "child_to_parent_refinement_rule_not_established"
    ] = "child_to_parent_refinement_rule_not_established"
    request_payload_ref: CASArtifactRef
    relation_ref: CASArtifactRef
    relation_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    joint_simulation_request_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    derived_atom_ids: tuple[str, ...] = Field(min_length=2)
    derived_atom_content_hashes: tuple[str, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _bind_authored_selection(self) -> ParentJointCandidateSelectionV3:
        for ref, kind in (
            (self.request_payload_ref, "runtime.control_job_payload.natural_language_run"),
            (self.relation_ref, "runtime.quality.recursive_authored_joint_relation"),
        ):
            if (
                type(ref) is not CASArtifactRef
                or ref.kind != kind
                or ref.media_type != "application/json"
                or not ref.manifest_profile_sha256
            ):
                raise ValueError("recursive_authored_joint_selection_ref_invalid")
        if (
            len(self.members) != len(self.derived_atom_ids)
            or len(self.members) != len(self.derived_atom_content_hashes)
            or len(set(self.derived_atom_ids)) != len(self.derived_atom_ids)
            or len(set(self.derived_atom_content_hashes)) != len(self.derived_atom_content_hashes)
            or any(
                len(atom_id) != 21
                or not atom_id.startswith("atom_")
                or any(ch not in "0123456789abcdef" for ch in atom_id[5:])
                for atom_id in self.derived_atom_ids
            )
            or any(
                len(content_hash) != 71
                or not content_hash.startswith("sha256:")
                or any(ch not in "0123456789abcdef" for ch in content_hash[7:])
                for content_hash in self.derived_atom_content_hashes
            )
            or any(
                original.source_atom_content_hash == derived_hash
                for original, derived_hash in zip(
                    self.members, self.derived_atom_content_hashes, strict=True
                )
            )
        ):
            raise ValueError("recursive_authored_joint_materialization_denominator_invalid")
        return self


def _authored_joint_relation_options(relation: ParentJointAuthoredRelationV1) -> object:
    """Describe the selected candidate relation and its exact input closure."""
    from polisyos.core import artifacts
    from polisyos.core.artifacts import (
        ArtifactSameInputClosureInfo,
        ArtifactTenantContextInfo,
        input_ref_from_artifact_ref,
    )

    return artifacts.ArtifactWriteOptions(
        kind="runtime.quality.recursive_authored_joint_relation",
        media_type="application/json",
        schema=artifacts.SchemaInfo(name=relation.schema_version, version="1.0"),
        producer=artifacts.ProducerInfo(component=__name__, version="1.0"),
        canon=artifacts.CanonInfo.from_spec(_N4_CHILD_PROFILE_SET_CANON),
        inputs=[
            input_ref_from_artifact_ref(relation.request_payload_ref, role="nl_request_payload"),
            input_ref_from_artifact_ref(relation.n4_source_ref, role="n4_source"),
            input_ref_from_artifact_ref(relation.context_job_ref, role="parent_context_job"),
            input_ref_from_artifact_ref(relation.profile_ref, role="parent_generic_profile"),
        ],
        tenant_context=ArtifactTenantContextInfo(
            tenant_id=relation.tenant_id,
            cell_id=relation.cell_id,
        ),
        same_input_closure=ArtifactSameInputClosureInfo(
            closure_id=f"recursive-authored-joint:{relation.run_id}:{relation.content_hash}",
            status="candidate_only",
            run_id=relation.run_id,
            job_id=relation.job_id,
            tenant_id=relation.tenant_id,
            cell_id=relation.cell_id,
        ),
    )


def _authored_joint_request_payload(
    *,
    store: ArtifactStore,
    ref: CASArtifactRef,
    handoff: GenericCycleSimulationContextHandoffV1,
    intent_digest: str,
) -> None:
    """Check selected queue bytes; the HTTP owner also verifies authorization."""
    from polisyos.core.artifacts import read_core_json_artifact
    from polisyos.runtime.quality.generation_source import _ref_selects_manifest

    if (
        type(ref) is not CASArtifactRef
        or ref.kind != "runtime.control_job_payload.natural_language_run"
        or ref.media_type != "application/json"
        or not ref.manifest_profile_sha256
        or not store.verify(ref).ok
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_request_ref_invalid")
    raw = store.get_bytes(ref)
    manifest = store.get_manifest(ref)
    if (
        str(ref.artifact_id) != "sha256:" + hashlib.sha256(raw).hexdigest()
        or not _ref_selects_manifest(ref, manifest)
        or manifest.artifact_schema is None
        or manifest.artifact_schema.name != "polisyos.runtime.ControlJobPayload"
        or manifest.artifact_schema.version != "1.1"
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_request_profile_mismatch")
    payload = read_core_json_artifact(store, ref, raw_payload_bytes=raw).value
    if not isinstance(payload, Mapping):
        raise RecursiveGenerationCycleError("recursive_authored_joint_request_payload_invalid")
    binding = payload.get("execution_intent_binding")
    snapshot = payload.get("nl_request_snapshot")
    snapshot_request = snapshot.get("request") if isinstance(snapshot, Mapping) else None
    if (
        not isinstance(binding, Mapping)
        or not isinstance(snapshot_request, Mapping)
        or payload.get("joint_interaction_candidate_intent") != "authored_joint_components.v1"
        or snapshot_request.get("joint_interaction_candidate_intent")
        != "authored_joint_components.v1"
        or binding.get("intent_digest") != intent_digest
        or binding.get("admission_status") != "established"
        or binding.get("canonical_mode") != "simulate_only"
        or (
            binding.get("job_id"),
            binding.get("run_id"),
            binding.get("tenant_id"),
            binding.get("cell_id"),
        )
        != (handoff.job_id, handoff.run_id, handoff.tenant_id, handoff.cell_id)
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_request_binding_mismatch")


def _materialized_joint_source_basis(
    *,
    source_ref: CASArtifactRef,
    source_run_id: str,
    source_repository: GenerationSourceRepository,
    handoff: GenericCycleSimulationContextHandoffV1,
    admission_owner: GenericCycleSimulationAdmissionOwner,
    members: tuple[ParentJointCandidateSourceMember, ...],
    request: JointSimulationRequest,
    hypothetical_diagnostic: bool = False,
) -> tuple[
    object,
    tuple[CandidateScenarioMaterializationV1 | CandidateScenarioNumericMaterializationV1, ...],
]:
    """Rebuild the complete source denominator, L6 materialization, and N5 request."""
    from polisyos.runtime.quality.cycle_substrate import cycle_job_design_problem_ref
    from polisyos.runtime.quality.design_generation import derive_n4_candidate_child_problems
    from polisyos.runtime.quality.generation_cycle import JointSimulationPort
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    if (
        type(source_repository) is not GenerationSourceRepository
        or type(admission_owner) is not GenericCycleSimulationAdmissionOwner
        or type(handoff) is not GenericCycleSimulationContextHandoffV1
        or source_repository.store is not admission_owner.store
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_owner_not_established")
    source = source_repository.load(
        source_ref,
        run_id=source_run_id,
        expected_run_id=handoff.run_id,
        expected_job_id=handoff.job_id,
        expected_tenant_id=handoff.tenant_id,
        expected_cell_id=handoff.cell_id,
        context_job_ref=handoff.context_job_ref,
        profile_ref=handoff.profile_ref,
        n4_child_profile_family_ref=handoff.n4_child_profile_family_ref,
    )
    if (
        source.generation_result.status != "generated"
        or source.cycle_substrate_context != handoff.context
        or source.trinity_bundle is None
        or source.problem.outcome_of_interest.target_variable not in request.selected_outcomes
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_source_mismatch")
    children = derive_n4_candidate_child_problems(
        source.problem,
        source.generation_result,
        model_id=source.generation_result.model_id,
    )
    candidates = {item.candidate_id: item for item in source.generation_result.candidates}
    if len(children) != len(members) or len(candidates) != len(members):
        raise RecursiveGenerationCycleError("recursive_authored_joint_denominator_mismatch")
    for child, member in zip(children, members, strict=True):
        candidate = candidates.get(member.source_candidate_id)
        child_problem_ref = cycle_job_design_problem_ref(child.problem)
        if (
            candidate is None
            or member.child_node_ref
            != "design-problem://" + child_problem_ref.removeprefix("sha256:")
            or member.child_design_problem_ref != child_problem_ref
            or member.semantic_ref != child.semantic_ref
            or member.source_candidate_content_hash
            != gy_content_hash(candidate.model_dump(mode="json"))
            or member.source_atom_id != candidate.atom.atom_id
            or member.source_atom_content_hash != candidate.atom.content_hash
            or child.source_atom_refs != (candidate.atom.content_hash,)
            or member.parent_problem_frame_ref != cycle_job_design_problem_ref(source.problem)
            or candidate.atom.problem_frame_ref != member.parent_problem_frame_ref
        ):
            raise RecursiveGenerationCycleError("recursive_authored_joint_source_member_mismatch")
    materializations = admission_owner.materialize_source_atoms(
        handoff=handoff,
        source_ref=source_ref,
        source_run_id=source_run_id,
        candidate_ids=tuple(member.source_candidate_id for member in members),
    )
    atoms = tuple(item.derived_n5_atom for item in materializations)
    outcome = source.problem.outcome_of_interest.target_variable
    world = handoff.profile.context_inputs.world_model_record
    variable_map = JointSimulationPort._joint_simulation_variable_map(
        atoms=atoms,
        outcome=outcome,
        raw_hint=None,
    )
    n5 = handoff.profile.n5
    scope_fields = (
        {
            "candidate_intent": "n4_unique_parent_source_members.v1",
            "member_basis": "hypothetical_all_unique_n4_source_members",
            "source_candidate_relationship": "alternatives",
            "composition_status": "not_established",
            "composition_limitation_code": (
                "n4_source_candidates_are_alternatives_not_authored_compound_design"
            ),
            "child_to_parent_refinement_status": "not_established",
            "child_to_parent_refinement_limitation_code": (
                "child_to_parent_refinement_rule_not_established"
            ),
        }
        if hypothetical_diagnostic
        else {}
    )
    expected_request = JointSimulationRequest(
        world_model_record_ref=world.world_model_record_id,
        world_model_record=world,
        intervention_atoms=atoms,
        selected_outcomes=(outcome,),
        horizon=n5.horizon,
        engine_plan=admission_owner.build_engine_plans(
            profile=handoff.profile,
            world_record=world,
            outcome=outcome,
            variable_map=variable_map,
        ),
        baseline_state=dict(n5.baseline_state),
        comparator_refs=n5.comparator_refs,
        budget_ref=n5.budget_ref,
        seed=n5.seed,
        replications=n5.replications,
        **scope_fields,
    )
    if request.model_dump(mode="json") != expected_request.model_dump(mode="json"):
        raise RecursiveGenerationCycleError("recursive_authored_joint_request_replay_mismatch")
    return source, materializations


def persist_authored_joint_components(
    *,
    store: ArtifactStore,
    source_repository: GenerationSourceRepository,
    source_ref: CASArtifactRef,
    source_run_id: str,
    parent_handoff: GenericCycleSimulationContextHandoffV1,
    admission_owner: GenericCycleSimulationAdmissionOwner,
    verified_nl_job_scope: VerifiedNLJobScope,
    request_payload_ref: CASArtifactRef,
    members: tuple[ParentJointCandidateSourceMember, ...],
    component_materializations: tuple[
        CandidateScenarioMaterializationV1 | CandidateScenarioNumericMaterializationV1, ...
    ],
    request: JointSimulationRequest,
) -> tuple[ParentJointAuthoredRelationV1, CASArtifactRef]:
    """Persist a candidate relation only after actual job, source, and L6 replay."""
    if (
        type(verified_nl_job_scope) is not VerifiedNLJobScope
        or not verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
        or (
            verified_nl_job_scope.job_id,
            verified_nl_job_scope.run_id,
            verified_nl_job_scope.tenant_id,
            verified_nl_job_scope.cell_id,
        )
        != (
            parent_handoff.job_id,
            parent_handoff.run_id,
            parent_handoff.tenant_id,
            parent_handoff.cell_id,
        )
        or admission_owner.store is not store
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_job_scope_not_established")
    _authored_joint_request_payload(
        store=store,
        ref=request_payload_ref,
        handoff=parent_handoff,
        intent_digest=verified_nl_job_scope.intent_digest,
    )
    source, replayed = _materialized_joint_source_basis(
        source_ref=source_ref,
        source_run_id=source_run_id,
        source_repository=source_repository,
        handoff=parent_handoff,
        admission_owner=admission_owner,
        members=members,
        request=request,
    )
    if replayed != component_materializations:
        raise RecursiveGenerationCycleError("recursive_authored_joint_materialization_mismatch")
    world = parent_handoff.profile.context_inputs.world_model_record
    fields: dict[str, object] = {
        "job_id": parent_handoff.job_id,
        "run_id": parent_handoff.run_id,
        "tenant_id": parent_handoff.tenant_id,
        "cell_id": parent_handoff.cell_id,
        "source_run_id": source_run_id,
        "intent_digest": verified_nl_job_scope.intent_digest,
        "request_payload_ref": request_payload_ref,
        "n4_source_ref": source_ref,
        "n4_source_content_hash": source.content_hash,
        "n4_source_result_content_hash": gy_content_hash(
            source.generation_result.model_dump(mode="json")
        ),
        "parent_design_problem_ref": source.generation_result.design_problem_ref,
        "context_job_ref": parent_handoff.context_job_ref,
        "context_content_hash": parent_handoff.context.content_hash,
        "profile_ref": parent_handoff.profile_ref,
        "profile_content_hash": parent_handoff.profile.content_hash,
        "profile_selection_ref": parent_handoff.profile.profile_selection_ref,
        "world_model_record_ref": world.world_model_record_id,
        "world_model_record_content_hash": world.content_hash,
        "outcome_variable": source.problem.outcome_of_interest.target_variable,
        "members": members,
        "component_materializations": replayed,
        "joint_simulation_request_content_hash": gy_content_hash(request.model_dump(mode="json")),
    }
    draft = ParentJointAuthoredRelationV1.model_construct(
        **fields,
        content_hash="sha256:" + "0" * 64,
    )
    payload = draft.model_dump(mode="json", exclude={"content_hash"})
    relation = ParentJointAuthoredRelationV1.model_validate(
        {**payload, "content_hash": gy_content_hash(payload)}
    )
    ref = store.put_json(
        relation.model_dump(mode="json"),
        _authored_joint_relation_options(relation),
        canon_spec=_N4_CHILD_PROFILE_SET_CANON,
        return_selected_profile=True,
    )
    loaded = load_authored_joint_components(
        store=store,
        relation_ref=ref,
        source_repository=source_repository,
        parent_handoff=parent_handoff,
        admission_owner=admission_owner,
        request=request,
    )
    if loaded != relation:
        raise RecursiveGenerationCycleError("recursive_authored_joint_readback_mismatch")
    return relation, ref


def load_authored_joint_components(
    *,
    store: ArtifactStore,
    relation_ref: CASArtifactRef,
    source_repository: GenerationSourceRepository,
    parent_handoff: GenericCycleSimulationContextHandoffV1,
    admission_owner: GenericCycleSimulationAdmissionOwner,
    request: JointSimulationRequest,
    selection: ParentJointCandidateSelectionV3 | None = None,
) -> ParentJointAuthoredRelationV1:
    """Reopen and recompute a selected relation; no causal authority is conferred."""
    from polisyos.core.artifacts import load_core_json_artifact
    from polisyos.runtime.quality.generation_source import _has_owner_profile, _ref_selects_manifest

    if (
        type(relation_ref) is not CASArtifactRef
        or relation_ref.kind != "runtime.quality.recursive_authored_joint_relation"
        or relation_ref.media_type != "application/json"
        or not relation_ref.manifest_profile_sha256
        or admission_owner.store is not store
        or not store.verify(relation_ref).ok
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_relation_ref_invalid")
    raw = store.get_bytes(relation_ref)
    if str(relation_ref.artifact_id) != "sha256:" + hashlib.sha256(raw).hexdigest():
        raise RecursiveGenerationCycleError("recursive_authored_joint_relation_cas_mismatch")
    relation = ParentJointAuthoredRelationV1.model_validate(
        load_core_json_artifact(store, relation_ref, raw_payload_bytes=raw)
    )
    manifest = store.get_manifest(relation_ref)
    if not _ref_selects_manifest(relation_ref, manifest) or not _has_owner_profile(
        manifest, _authored_joint_relation_options(relation)
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_relation_profile_mismatch")
    if (
        (relation.job_id, relation.run_id, relation.tenant_id, relation.cell_id)
        != (
            parent_handoff.job_id,
            parent_handoff.run_id,
            parent_handoff.tenant_id,
            parent_handoff.cell_id,
        )
        or relation.context_job_ref != parent_handoff.context_job_ref
        or relation.context_content_hash != parent_handoff.context.content_hash
        or relation.profile_ref != parent_handoff.profile_ref
        or relation.profile_content_hash != parent_handoff.profile.content_hash
        or relation.profile_selection_ref != parent_handoff.profile.profile_selection_ref
        or relation.joint_simulation_request_content_hash
        != gy_content_hash(request.model_dump(mode="json"))
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_relation_scope_mismatch")
    _authored_joint_request_payload(
        store=store,
        ref=relation.request_payload_ref,
        handoff=parent_handoff,
        intent_digest=relation.intent_digest,
    )
    source, replayed = _materialized_joint_source_basis(
        source_ref=relation.n4_source_ref,
        source_run_id=relation.source_run_id,
        source_repository=source_repository,
        handoff=parent_handoff,
        admission_owner=admission_owner,
        members=relation.members,
        request=request,
    )
    if (
        relation.n4_source_content_hash != source.content_hash
        or relation.n4_source_result_content_hash
        != gy_content_hash(source.generation_result.model_dump(mode="json"))
        or relation.component_materializations != replayed
        or relation.world_model_record_ref != request.world_model_record_ref
        or relation.world_model_record_content_hash != request.world_model_record.content_hash
        or relation.outcome_variable not in request.selected_outcomes
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_relation_replay_mismatch")
    if selection is not None and (
        type(selection) is not ParentJointCandidateSelectionV3
        or selection.relation_ref != relation_ref
        or selection.relation_content_hash != relation.content_hash
        or selection.request_payload_ref != relation.request_payload_ref
        or selection.n4_source_ref != relation.n4_source_ref
        or selection.n4_source_result_content_hash != relation.n4_source_result_content_hash
        or selection.context_job_ref != relation.context_job_ref
        or selection.profile_ref != relation.profile_ref
        or selection.profile_selection_ref != relation.profile_selection_ref
        or selection.parent_design_problem_ref != relation.parent_design_problem_ref
        or selection.members != relation.members
        or selection.joint_simulation_request_content_hash
        != relation.joint_simulation_request_content_hash
        or selection.derived_atom_ids != tuple(item.derived_n5_atom.atom_id for item in replayed)
        or selection.derived_atom_content_hashes
        != tuple(item.derived_n5_atom.content_hash for item in replayed)
    ):
        raise RecursiveGenerationCycleError("recursive_authored_joint_selection_replay_mismatch")
    return relation


def replay_parent_joint_candidate_materializations(
    *,
    selection: ParentJointCandidateSelectionV4,
    request: JointSimulationRequest,
    parent_handoff: GenericCycleSimulationContextHandoffV1,
    admission_owner: GenericCycleSimulationAdmissionOwner,
) -> tuple[CandidateScenarioMaterializationV1 | CandidateScenarioNumericMaterializationV1, ...]:
    """Recompute the selected hypothetical numeric basis from its immutable owners.

    This verifies source-to-request derivation, not currentness or composition.
    Runtime callers separately check the live context and worker lease. A fresh
    historical reader can replay the selected profile without a configured set.
    """
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    if (
        type(selection) is not ParentJointCandidateSelectionV4
        or type(parent_handoff) is not GenericCycleSimulationContextHandoffV1
        or type(admission_owner) is not GenericCycleSimulationAdmissionOwner
        or type(request) is not JointSimulationRequest
    ):
        raise RecursiveGenerationCycleError("recursive_parent_joint_materialization_owner_untyped")
    selection = ParentJointCandidateSelectionV4.model_validate(selection.model_dump(mode="python"))
    if (
        selection.context_job_ref != parent_handoff.context_job_ref
        or selection.profile_ref != parent_handoff.profile_ref
        or selection.profile_selection_ref != parent_handoff.profile.profile_selection_ref
        or selection.parent_design_problem_ref != parent_handoff.context.design_problem_ref
        or selection.joint_simulation_request_content_hash
        != gy_content_hash(request.model_dump(mode="json"))
    ):
        raise RecursiveGenerationCycleError("recursive_parent_joint_materialization_scope_mismatch")
    source, replayed = _materialized_joint_source_basis(
        source_ref=selection.n4_source_ref,
        source_run_id=parent_handoff.run_id,
        source_repository=GenerationSourceRepository(admission_owner.store),
        handoff=parent_handoff,
        admission_owner=admission_owner,
        members=selection.members,
        request=request,
        hypothetical_diagnostic=True,
    )
    if (
        selection.n4_source_result_content_hash
        != gy_content_hash(source.generation_result.model_dump(mode="json"))
        or selection.world_model_record_ref != request.world_model_record_ref
        or selection.world_model_record_content_hash != request.world_model_record.content_hash
        or tuple(request.selected_outcomes) != (selection.outcome_variable,)
        or selection.component_materializations != replayed
    ):
        raise RecursiveGenerationCycleError(
            "recursive_parent_joint_materialization_replay_mismatch"
        )
    return replayed


class RecursiveCycleNode(_StrictModel):
    """One replay-visible node routed through existing depth owners."""

    node_ref: str = Field(min_length=1)
    parent_ref: str | None = None
    depth: int = Field(ge=0)
    child_refs: tuple[str, ...] = ()
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    cycle_run: GenerationCycleRun | None = None
    joint_simulation: JointSimulationResult | None = None
    joint_simulation_ref: CASArtifactRef | None = None
    joint_simulation_request: JointSimulationRequest | None = None
    joint_simulation_request_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    joint_candidate_selection: (
        ParentJointCandidateSelectionV1
        | ParentJointCandidateSelectionV2
        | ParentJointCandidateSelectionV3
        | ParentJointCandidateSelectionV4
        | None
    ) = Field(
        default=None,
        exclude_if=lambda value: value is None,
    )
    joint_candidate_selection_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
        exclude_if=lambda value: value is None,
    )
    leaf_context_ref: CASArtifactRef | None = None
    composition_certificate: CompositionCertificate | None = None
    terminal: SearchTerminalState
    _legacy_v1_missing_joint_simulation_ref: bool = PrivateAttr(default=False)

    @field_validator("cycle_run", mode="before")
    @classmethod
    def _load_persisted_leaf_run(cls, value: object) -> object:
        """Reconcile every leaf with intrinsic N6 history, without currentness."""

        if isinstance(value, GenerationCycleRun):
            payload = value.model_dump(mode="json")
        elif isinstance(value, Mapping):
            payload = value
        else:
            return value
        issues = validate_generation_cycle_run_history(payload)
        if issues:
            codes = ",".join(str(issue["code"]) for issue in issues)
            raise ValueError(f"recursive_leaf_generation_cycle_history_invalid:{codes}")
        return (
            value
            if isinstance(value, GenerationCycleRun)
            else GenerationCycleRun.model_validate(payload)
        )

    @model_validator(mode="after")
    def _only_leaves_run_n6(self) -> RecursiveCycleNode:
        legacy_v1 = _LEGACY_RECURSIVE_V1_CONTEXT.get()
        if legacy_v1:
            object.__setattr__(self, "_legacy_v1_missing_joint_simulation_ref", True)
        if self.joint_simulation is None and self.joint_simulation_ref is not None:
            raise ValueError("recursive_simulation_ref_without_result")
        if (
            self.joint_simulation is not None
            and self.joint_simulation_ref is None
            and not legacy_v1
        ):
            raise ValueError("recursive_simulation_result_requires_cas_ref")
        if self.joint_simulation_ref is not None and (
            self.joint_simulation_ref.kind != "polisyos.runtime.joint_simulation_result"
            or self.joint_simulation_ref.media_type != "application/json"
        ):
            raise ValueError("recursive_simulation_ref_contract_mismatch")
        if (self.joint_simulation_request is None) != (
            self.joint_simulation_request_content_hash is None
        ):
            raise ValueError("recursive_parent_n5_request_binding_shape_invalid")
        if self.joint_simulation_request is not None:
            request = self.joint_simulation_request
            result = self.joint_simulation
            expected_request_hash = gy_content_hash(request.model_dump(mode="json"))
            graph = request.coupling_graph
            if (
                result is None
                or self.joint_simulation_ref is None
                or self.joint_simulation_request_content_hash != expected_request_hash
                or request.world_model_record.content_hash != result.world_model_record_content_hash
                or request.world_model_record_ref != result.world_model_record_ref
                or tuple(atom.intervention_id for atom in request.intervention_atoms)
                != tuple(result.atom_ids)
                or tuple(request.selected_outcomes) != tuple(result.selected_outcomes)
                or request.horizon.model_dump(mode="json") != result.horizon.model_dump(mode="json")
                or any(
                    atom.problem_frame_ref != self.design_problem_ref
                    for atom in request.intervention_atoms
                )
                or (graph is None and self.joint_candidate_selection is None)
                or (
                    graph is not None
                    and (
                        graph.design_ref != self.node_ref
                        or tuple(graph.module_refs) != tuple(self.child_refs)
                    )
                )
            ):
                raise ValueError("recursive_parent_n5_request_result_binding_mismatch")
            if result.schema_version in {
                "policyos.runtime.joint_simulation_horizon.v4",
                "policyos.runtime.joint_simulation_horizon.v5",
            }:
                from polisyos.runtime.quality.joint_simulation_horizon import (
                    _replication_seeds,
                )

                if result.diagnostics.get(
                    "requested_replications"
                ) != request.replications or tuple(
                    result.diagnostics.get("replication_seeds", ())
                ) != tuple(_replication_seeds(request)):
                    raise ValueError("recursive_parent_n5_request_seed_binding_mismatch")
        elif self.joint_simulation_request_content_hash is not None:
            raise ValueError("recursive_parent_n5_request_content_hash_without_request")
        if (self.joint_candidate_selection is None) != (
            self.joint_candidate_selection_content_hash is None
        ):
            raise ValueError("recursive_parent_joint_candidate_selection_binding_shape_invalid")
        if self.joint_candidate_selection is not None:
            selection = self.joint_candidate_selection
            request = self.joint_simulation_request
            if self.composition_certificate is not None:
                raise ValueError("recursive_candidate_selection_cannot_claim_composition")
            if (
                self.joint_candidate_selection_content_hash != selection.content_hash
                or request is None
                or request.coupling_graph is not None
                or selection.parent_design_problem_ref != self.design_problem_ref
                or selection.child_node_refs != self.child_refs
                or selection.world_model_record_ref != request.world_model_record_ref
                or selection.world_model_record_content_hash
                != request.world_model_record.content_hash
                or selection.outcome_variable not in request.selected_outcomes
                or (
                    isinstance(selection, ParentJointCandidateSelectionV3)
                    and (
                        selection.derived_atom_ids
                        != tuple(atom.atom_id for atom in request.intervention_atoms)
                        or selection.derived_atom_content_hashes
                        != tuple(atom.content_hash for atom in request.intervention_atoms)
                    )
                )
                or (
                    isinstance(selection, ParentJointCandidateSelectionV4)
                    and tuple(item.derived_n5_atom for item in selection.component_materializations)
                    != tuple(request.intervention_atoms)
                )
                or (
                    not isinstance(
                        selection,
                        (ParentJointCandidateSelectionV3, ParentJointCandidateSelectionV4),
                    )
                    and (
                        tuple(member.source_atom_id for member in selection.members)
                        != tuple(atom.atom_id for atom in request.intervention_atoms)
                        or tuple(member.source_atom_content_hash for member in selection.members)
                        != tuple(atom.content_hash for atom in request.intervention_atoms)
                    )
                )
            ):
                raise ValueError("recursive_parent_joint_candidate_request_binding_mismatch")
            if isinstance(selection, ParentJointCandidateSelectionV3):
                if selection.joint_simulation_request_content_hash != gy_content_hash(
                    request.model_dump(mode="json")
                ) or any(
                    getattr(request, field_name) is not None
                    for field_name in (
                        "candidate_intent",
                        "member_basis",
                        "source_candidate_relationship",
                        "composition_status",
                        "composition_limitation_code",
                        "child_to_parent_refinement_status",
                        "child_to_parent_refinement_limitation_code",
                    )
                ):
                    raise ValueError("recursive_parent_authored_joint_request_binding_mismatch")
            elif isinstance(selection, ParentJointCandidateSelectionV2):
                if (
                    request is None
                    or selection.joint_simulation_request_content_hash
                    != gy_content_hash(request.model_dump(mode="json"))
                    or request.candidate_intent != selection.candidate_intent
                    or request.member_basis != selection.member_basis
                    or request.source_candidate_relationship
                    != selection.source_candidate_relationship
                    or request.composition_status != selection.composition_status
                    or request.composition_limitation_code != selection.composition_limitation_code
                    or request.child_to_parent_refinement_status
                    != selection.child_to_parent_refinement_status
                    or request.child_to_parent_refinement_limitation_code
                    != selection.child_to_parent_refinement_limitation_code
                ):
                    raise ValueError("recursive_parent_joint_candidate_v2_request_hash_mismatch")
            elif any(
                getattr(request, field_name) is not None
                for field_name in (
                    "candidate_intent",
                    "member_basis",
                    "source_candidate_relationship",
                    "composition_status",
                    "composition_limitation_code",
                    "child_to_parent_refinement_status",
                    "child_to_parent_refinement_limitation_code",
                )
            ):
                raise ValueError("recursive_parent_joint_candidate_v1_scope_unbound")
            if (
                self.composition_certificate is None
                and not _joint_simulation_is_unsupported(self.joint_simulation)
                and (
                    self.terminal.kind is not SearchTerminalKind.RECURSIVE_BLOCKED
                    or "observed_coupling_evidence_missing"
                    not in self.terminal.blocking_obligations
                )
            ):
                raise ValueError("recursive_parent_joint_candidate_requires_blocked_composition")
        if self.child_refs and self.cycle_run is not None:
            raise ValueError("recursive_internal_node_cannot_run_leaf_cycle")
        if self.leaf_context_ref is not None and (
            self.child_refs
            or self.leaf_context_ref.kind != "runtime.quality.recursive_leaf_context"
            or self.leaf_context_ref.media_type != "application/json"
        ):
            raise ValueError("recursive_leaf_context_ref_contract_mismatch")
        if not self.child_refs and self.cycle_run is None:
            raise ValueError("recursive_leaf_requires_generation_cycle")
        if not self.child_refs and (
            self.joint_simulation is not None or self.composition_certificate is not None
        ):
            raise ValueError("recursive_leaf_cannot_mint_parent_evidence")
        if len(self.child_refs) < 2 and (
            self.joint_simulation is not None or self.composition_certificate is not None
        ):
            raise ValueError("recursive_unary_parent_cannot_mint_coupled_evidence")
        if self.composition_certificate is not None and self.joint_simulation is None:
            raise ValueError("recursive_composition_requires_joint_simulation")
        if self.composition_certificate is not None and (
            self.composition_certificate.parent_workspace_id != self.node_ref
            or self.composition_certificate.target_policy_program_ref != self.node_ref
        ):
            raise ValueError("recursive_composition_parent_binding_mismatch")
        if self.joint_simulation is not None:
            unsupported = _joint_simulation_is_unsupported(self.joint_simulation)
            if unsupported and self.composition_certificate is not None:
                raise ValueError("recursive_unsupported_n5_cannot_mint_composition")
            if (
                not unsupported
                and self.composition_certificate is None
                and self.joint_candidate_selection is None
            ):
                raise ValueError("recursive_supported_n5_requires_composition")
        return self

    @model_serializer(mode="wrap")
    def _serialize_without_legacy_or_empty_simulation_ref(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        """Keep v1 identity bytes stable while omitting empty ref defaults."""

        payload = handler(self)
        if self._legacy_v1_missing_joint_simulation_ref:
            supplied = _legacy_supplied_field_tree(self, payload)
            if not isinstance(supplied, dict):
                raise TypeError("historical_recursive_payload_invalid")
            payload = supplied
        if self.joint_simulation_ref is None:
            payload.pop("joint_simulation_ref", None)
        if self.leaf_context_ref is None:
            payload.pop("leaf_context_ref", None)
        return payload


class RecursiveGenerationCycleRun(_StrictModel):
    """Content-bound depth-N run emitted by the thin recursive router."""

    schema_version: str = RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION
    run_id: str = Field(min_length=1)
    controller_ref: str = RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF
    authority_scope: Literal["production", "contract_testing"] = "production"
    recursive_graph: RecursiveDesignGraph
    recursive_graph_ref: str = Field(min_length=1)
    recursive_graph_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_node_ref: str = Field(min_length=1)
    root_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recursive_budget: RecursiveCycleBudget
    observed_max_depth: int = Field(ge=0)
    nodes: tuple[RecursiveCycleNode, ...] = Field(min_length=1)
    terminal: SearchTerminalState
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="wrap")
    @classmethod
    def _admit_authenticated_legacy_v1(
        cls,
        value: object,
        handler: ModelWrapValidatorHandler,
    ) -> RecursiveGenerationCycleRun:
        """Scope legacy ref omission to exact tracked identities during validation."""

        token = _LEGACY_RECURSIVE_V1_CONTEXT.set(_is_authenticated_legacy_v1(value))
        try:
            return handler(value)
        finally:
            _LEGACY_RECURSIVE_V1_CONTEXT.reset(token)

    @property
    def leaf_nodes(self) -> tuple[RecursiveCycleNode, ...]:
        """Return nodes whose real N6 leaf runs produced terminal evidence."""

        return tuple(node for node in self.nodes if not node.child_refs)

    @property
    def joint_simulation_receipts(self) -> tuple[SimulationProofReceipt, ...]:
        """Return only receipts emitted live by the canonical N5 owner."""

        return tuple(
            node.joint_simulation.receipt
            for node in self.nodes
            if node.joint_simulation is not None
        )

    @model_validator(mode="after")
    def _verify_content_binding(self) -> RecursiveGenerationCycleRun:
        if (
            self.recursive_graph_ref != self.recursive_graph.graph_ref
            or self.recursive_graph_content_hash
            != gy_content_hash(self.recursive_graph.model_dump(mode="json"))
        ):
            raise ValueError("recursive_run_graph_binding_mismatch")
        by_ref = {node.node_ref: node for node in self.nodes}
        if len(by_ref) != len(self.nodes):
            raise ValueError("recursive_run_duplicate_node")
        root = by_ref.get(self.root_node_ref)
        if root is None or root.parent_ref is not None or root.depth != 0:
            raise ValueError("recursive_run_root_incoherent")
        if self.root_design_problem_ref != root.design_problem_ref:
            raise ValueError("recursive_run_root_problem_mismatch")
        if (
            self.root_node_ref != self.recursive_graph.root_design_ref
            or set(by_ref) != set(self.recursive_graph.node_refs)
            or {(node.node_ref, child_ref) for node in self.nodes for child_ref in node.child_refs}
            != set(self.recursive_graph.parent_child_edges)
        ):
            raise ValueError("recursive_run_graph_topology_mismatch")
        if self.terminal != root.terminal:
            raise ValueError("recursive_run_terminal_not_root_derived")
        if self.observed_max_depth != max(node.depth for node in self.nodes):
            raise ValueError("recursive_run_observed_depth_incoherent")
        if (
            len(self.nodes) > self.recursive_budget.max_nodes
            or self.observed_max_depth > self.recursive_budget.max_depth
        ):
            raise ValueError("recursive_run_budget_incoherent")
        for node in sorted(self.nodes, key=lambda item: item.depth, reverse=True):
            if len(node.child_refs) != len(set(node.child_refs)):
                raise ValueError("recursive_run_duplicate_child")
            for child_ref in node.child_refs:
                child = by_ref.get(child_ref)
                if (
                    child is None
                    or child.parent_ref != node.node_ref
                    or child.depth != node.depth + 1
                ):
                    raise ValueError("recursive_run_topology_incoherent")
            if node.node_ref != self.root_node_ref:
                parent = by_ref.get(node.parent_ref or "")
                if parent is None or node.node_ref not in parent.child_refs:
                    raise ValueError("recursive_run_topology_incoherent")
            if (
                node.cycle_run is not None
                and node.cycle_run.design_problem_ref != node.design_problem_ref
            ):
                raise ValueError("recursive_run_leaf_problem_mismatch")
            if node.cycle_run is not None:
                if node.terminal != generation_cycle_terminal_state(node.cycle_run):
                    raise ValueError("recursive_run_leaf_terminal_not_owner_derived")
                continue
            routed_children = tuple(by_ref[child_ref] for child_ref in node.child_refs)
            if len(routed_children) == 1:
                expected_terminal = _fold_unary_terminal(routed_children[0])
            elif node.joint_simulation is not None and node.composition_certificate is not None:
                expected_terminal = _fold_composed_terminal(
                    children=routed_children,
                    joint_simulation=node.joint_simulation,
                    certificate=node.composition_certificate,
                )
            elif node.joint_simulation is not None:
                expected_terminal = _fold_uncertified_joint_terminal(node)
            else:
                expected_terminal = _fold_uncomposed_parent_terminal(node.terminal)
            if node.terminal != expected_terminal:
                raise ValueError("recursive_run_parent_terminal_not_owner_derived")
        payload = gy_artifact_self_identity_projection(self)
        payload.pop("leaf_nodes", None)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


class RecursiveCyclePendingNode(_StrictModel):
    """A graph member not executed before the recursive budget stop."""

    node_ref: str = Field(min_length=1)
    parent_ref: str | None = None
    depth: int = Field(ge=0)
    child_refs: tuple[str, ...] = ()
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")


class RecursiveCycleFailure(_StrictModel):
    """Exact node-local failure emitted by one recursive leaf execution."""

    origin_node_ref: str = Field(min_length=1)
    stage: Literal["leaf_generation"] = "leaf_generation"
    exception_type: str = Field(min_length=1)
    error_code: str | None = None
    error_message: str


class RecursiveCycleFailedNode(_StrictModel):
    """A recursive branch that failed after an earlier sibling completed."""

    node_ref: str = Field(min_length=1)
    parent_ref: str | None = None
    depth: int = Field(ge=0)
    child_refs: tuple[str, ...] = ()
    design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    failure: RecursiveCycleFailure


class _RecursiveLeafExecutionError(Exception):
    """Carry one exact N6 leaf error until a completed sibling can be retained."""

    def __init__(self, node_ref: str, error: Exception) -> None:
        self.node_ref = node_ref
        self.error = error
        error_code = getattr(error, "code", None)
        self.failure = RecursiveCycleFailure(
            origin_node_ref=node_ref,
            stage="leaf_generation",
            exception_type=type(error).__name__,
            error_code=error_code if isinstance(error_code, str) else None,
            error_message=str(error),
        )
        super().__init__(self.failure.error_message)


class _RecursiveSiblingFailureError(Exception):
    """Mark a failed branch only after an earlier direct sibling completed."""

    def __init__(
        self,
        failed_node_ref: str,
        failure: RecursiveCycleFailure,
    ) -> None:
        self.failed_node_ref = failed_node_ref
        self.failure = failure
        super().__init__(failure.error_message)


def _validate_recursive_partial_graph(
    *,
    recursive_graph: RecursiveDesignGraph,
    recursive_graph_ref: str,
    recursive_graph_content_hash: str,
    root_node_ref: str,
    root_design_problem_ref: str,
    recursive_budget: RecursiveCycleBudget,
    observed_max_depth: int,
    nodes: tuple[RecursiveCycleNode | RecursiveCyclePendingNode | RecursiveCycleFailedNode, ...],
) -> tuple[
    dict[str, RecursiveCycleNode | RecursiveCyclePendingNode | RecursiveCycleFailedNode],
    dict[str, list[str]],
    dict[str, str],
]:
    """Recompute graph, budget, node topology, and completed-node semantics."""

    if (
        recursive_graph_ref != recursive_graph.graph_ref
        or recursive_graph_content_hash != gy_content_hash(recursive_graph.model_dump(mode="json"))
    ):
        raise ValueError("recursive_run_graph_binding_mismatch")

    node_refs = tuple(recursive_graph.node_refs)
    by_ref = {node.node_ref: node for node in nodes}
    if len(by_ref) != len(nodes) or set(by_ref) != set(node_refs):
        raise ValueError("recursive_partial_graph_denominator_mismatch")
    children_by_ref: dict[str, list[str]] = {ref: [] for ref in node_refs}
    parent_by_ref: dict[str, str] = {}
    for parent_ref, child_ref in recursive_graph.parent_child_edges:
        if parent_ref not in children_by_ref or child_ref not in children_by_ref:
            raise ValueError("recursive_run_graph_topology_mismatch")
        if child_ref in parent_by_ref:
            raise ValueError("recursive_run_graph_topology_mismatch")
        children_by_ref[parent_ref].append(child_ref)
        parent_by_ref[child_ref] = parent_ref
    if set(parent_by_ref) != set(node_refs) - {root_node_ref}:
        raise ValueError("recursive_run_graph_topology_mismatch")

    root = by_ref.get(root_node_ref)
    if (
        root_node_ref != recursive_graph.root_design_ref
        or not isinstance(root, RecursiveCyclePendingNode)
        or root.parent_ref is not None
        or root.depth != 0
        or root.design_problem_ref != root_design_problem_ref
    ):
        raise ValueError("recursive_partial_root_not_pending")

    depths: dict[str, int] = {}

    def visit(node_ref: str, depth: int) -> None:
        if node_ref in depths or depth > recursive_budget.max_depth:
            raise ValueError("recursive_partial_graph_topology_incoherent")
        depths[node_ref] = depth
        for child_ref in children_by_ref[node_ref]:
            visit(child_ref, depth + 1)

    visit(root_node_ref, 0)
    if (
        set(depths) != set(node_refs)
        or len(node_refs) > recursive_budget.max_nodes
        or observed_max_depth != max(depths.values())
    ):
        raise ValueError("recursive_partial_graph_budget_incoherent")

    for node_ref in node_refs:
        node = by_ref[node_ref]
        expected_parent = parent_by_ref.get(node_ref)
        expected_children = tuple(children_by_ref[node_ref])
        if (
            node.parent_ref != expected_parent
            or node.depth != depths[node_ref]
            or node.child_refs != expected_children
        ):
            raise ValueError("recursive_partial_node_topology_mismatch")
        if isinstance(node, (RecursiveCyclePendingNode, RecursiveCycleFailedNode)):
            continue
        if (
            node.cycle_run is not None
            and node.cycle_run.design_problem_ref != node.design_problem_ref
        ):
            raise ValueError("recursive_run_leaf_problem_mismatch")
        if node.cycle_run is not None:
            if node.terminal != generation_cycle_terminal_state(node.cycle_run):
                raise ValueError("recursive_run_leaf_terminal_not_owner_derived")
            continue
        routed_children = tuple(by_ref[child_ref] for child_ref in node.child_refs)
        if any(not isinstance(child, RecursiveCycleNode) for child in routed_children):
            raise ValueError("recursive_partial_completed_parent_has_pending_child")
        if len(routed_children) == 1:
            expected_terminal = _fold_unary_terminal(routed_children[0])
        elif node.joint_simulation is not None and node.composition_certificate is not None:
            expected_terminal = _fold_composed_terminal(
                children=routed_children,
                joint_simulation=node.joint_simulation,
                certificate=node.composition_certificate,
            )
        elif node.joint_simulation is not None:
            expected_terminal = _fold_uncertified_joint_terminal(node)
        else:
            expected_terminal = _fold_uncomposed_parent_terminal(node.terminal)
        if node.terminal != expected_terminal:
            raise ValueError("recursive_run_parent_terminal_not_owner_derived")
    return by_ref, children_by_ref, parent_by_ref


class RecursiveGenerationCyclePartialRunV2(_StrictModel):
    """Content-bound checkpoint preserving completed work and its pending frontier.

    This artifact represents traversal stopped by a real N6 child budget terminal.
    It deliberately has no root terminal: a partial graph cannot be projected as a
    completed design outcome or as epistemic abstention.
    """

    schema_version: Literal["policyos.runtime.recursive_generation_cycle.partial.v2"] = (
        RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    controller_ref: str = RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF
    authority_scope: Literal["production", "contract_testing"] = "production"
    recursive_graph: RecursiveDesignGraph
    recursive_graph_ref: str = Field(min_length=1)
    recursive_graph_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_node_ref: str = Field(min_length=1)
    root_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recursive_budget: RecursiveCycleBudget
    observed_max_depth: int = Field(ge=0)
    nodes: tuple[RecursiveCycleNode | RecursiveCyclePendingNode, ...] = Field(min_length=1)
    traversal_status: Literal["budget_stopped"] = "budget_stopped"
    traversal_stop_reason: Literal["child_budget_exhausted"] = "child_budget_exhausted"
    budget_stop_node_ref: str = Field(min_length=1)
    frontier_node_refs: tuple[str, ...] = ()
    terminal: None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @property
    def leaf_nodes(self) -> tuple[RecursiveCycleNode, ...]:
        """Return only leaves whose canonical N6 runs actually completed."""

        return tuple(
            node
            for node in self.nodes
            if isinstance(node, RecursiveCycleNode) and not node.child_refs
        )

    @property
    def pending_node_refs(self) -> tuple[str, ...]:
        """Return graph members with no execution result."""

        return tuple(
            node.node_ref for node in self.nodes if isinstance(node, RecursiveCyclePendingNode)
        )

    @model_validator(mode="after")
    def _verify_partial_checkpoint(self) -> RecursiveGenerationCyclePartialRunV2:
        by_ref, children_by_ref, parent_by_ref = _validate_recursive_partial_graph(
            recursive_graph=self.recursive_graph,
            recursive_graph_ref=self.recursive_graph_ref,
            recursive_graph_content_hash=self.recursive_graph_content_hash,
            root_node_ref=self.root_node_ref,
            root_design_problem_ref=self.root_design_problem_ref,
            recursive_budget=self.recursive_budget,
            observed_max_depth=self.observed_max_depth,
            nodes=self.nodes,
        )
        if self.terminal is not None:
            raise ValueError("recursive_partial_root_not_pending")
        budget_stop = by_ref.get(self.budget_stop_node_ref)
        if (
            not isinstance(budget_stop, RecursiveCycleNode)
            or budget_stop.child_refs
            or budget_stop.cycle_run is None
            or budget_stop.terminal.kind is not SearchTerminalKind.BUDGET_EXHAUSTED
        ):
            raise ValueError("recursive_partial_budget_stop_not_owner_derived")

        pending_refs = {
            node_ref
            for node_ref, node in by_ref.items()
            if isinstance(node, RecursiveCyclePendingNode)
        }
        if len(self.frontier_node_refs) != len(set(self.frontier_node_refs)):
            raise ValueError("recursive_partial_frontier_duplicate")
        frontier_refs = set(self.frontier_node_refs)
        if not frontier_refs.issubset(pending_refs):
            raise ValueError("recursive_partial_frontier_not_pending")
        stop_ancestors: set[str] = set()
        current_parent = parent_by_ref.get(self.budget_stop_node_ref)
        while current_parent is not None:
            stop_ancestors.add(current_parent)
            current_parent = parent_by_ref.get(current_parent)
        frontier_subtrees: set[str] = set()

        def collect_frontier_subtree(node_ref: str) -> None:
            if node_ref in frontier_subtrees:
                return
            frontier_subtrees.add(node_ref)
            for child_ref in children_by_ref[node_ref]:
                collect_frontier_subtree(child_ref)

        for frontier_ref in frontier_refs:
            if parent_by_ref.get(frontier_ref) not in stop_ancestors:
                raise ValueError("recursive_partial_frontier_not_sibling_of_stop_path")
            collect_frontier_subtree(frontier_ref)
        if pending_refs != stop_ancestors | frontier_subtrees:
            raise ValueError("recursive_partial_frontier_denominator_mismatch")

        # The producer routes children depth-first. When a budget-stopped leaf
        # unwinds, every sibling before that path has already completed, while
        # every sibling after it is still pending. The frontier tuple is emitted
        # in unwind order (deepest parent first), so validate its exact content
        # and order instead of treating any same-parent pending node as an
        # interchangeable frontier. This is an intrinsic history check only;
        # it does not establish that the embedded cycle results were actually
        # produced by the canonical owner.
        expected_frontier_refs: list[str] = []

        def require_pending_subtree(node_ref: str) -> None:
            if not isinstance(by_ref[node_ref], RecursiveCyclePendingNode):
                raise ValueError("recursive_partial_later_sibling_not_pending")
            for child_ref in children_by_ref[node_ref]:
                require_pending_subtree(child_ref)

        path_child_ref = self.budget_stop_node_ref
        while path_child_ref != self.root_node_ref:
            path_parent_ref = parent_by_ref.get(path_child_ref)
            if path_parent_ref is None:
                raise ValueError("recursive_partial_budget_stop_outside_root")
            path_siblings = children_by_ref[path_parent_ref]
            path_position = path_siblings.index(path_child_ref)
            if any(
                not isinstance(by_ref[sibling_ref], RecursiveCycleNode)
                for sibling_ref in path_siblings[:path_position]
            ):
                raise ValueError("recursive_partial_prior_sibling_not_completed")
            later_sibling_refs = path_siblings[path_position + 1 :]
            expected_frontier_refs.extend(later_sibling_refs)
            for sibling_ref in later_sibling_refs:
                require_pending_subtree(sibling_ref)
            path_child_ref = path_parent_ref

        if self.frontier_node_refs != tuple(expected_frontier_refs):
            raise ValueError("recursive_partial_frontier_order_mismatch")

        payload = gy_artifact_self_identity_projection(self)
        payload.pop("leaf_nodes", None)
        payload.pop("pending_node_refs", None)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


class RecursiveGenerationCyclePartialRunV3(_StrictModel):
    """Content-bound checkpoint retaining completed siblings after N6 failure."""

    schema_version: Literal["policyos.runtime.recursive_generation_cycle.partial.v3"] = (
        RECURSIVE_GENERATION_CYCLE_PARTIAL_V3_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    controller_ref: str = RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF
    authority_scope: Literal["production", "contract_testing"] = "production"
    recursive_graph: RecursiveDesignGraph
    recursive_graph_ref: str = Field(min_length=1)
    recursive_graph_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_node_ref: str = Field(min_length=1)
    root_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recursive_budget: RecursiveCycleBudget
    observed_max_depth: int = Field(ge=0)
    nodes: tuple[
        RecursiveCycleNode | RecursiveCyclePendingNode | RecursiveCycleFailedNode,
        ...,
    ] = Field(min_length=1)
    traversal_status: Literal["failed"] = "failed"
    traversal_failure_reason: Literal["independent_sibling_failure"] = "independent_sibling_failure"
    failed_node_ref: str = Field(min_length=1)
    terminal: None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @property
    def leaf_nodes(self) -> tuple[RecursiveCycleNode, ...]:
        """Return only leaves whose canonical N6 runs actually completed."""

        return tuple(
            node
            for node in self.nodes
            if isinstance(node, RecursiveCycleNode) and not node.child_refs
        )

    @property
    def pending_node_refs(self) -> tuple[str, ...]:
        """Return nodes that traversal did not reach before the failure."""

        return tuple(
            node.node_ref for node in self.nodes if isinstance(node, RecursiveCyclePendingNode)
        )

    @property
    def failed_node(self) -> RecursiveCycleFailedNode:
        """Return the unique failed branch captured by this partial run."""

        return next(node for node in self.nodes if isinstance(node, RecursiveCycleFailedNode))

    @model_validator(mode="after")
    def _verify_failed_checkpoint(self) -> RecursiveGenerationCyclePartialRunV3:
        by_ref, children_by_ref, parent_by_ref = _validate_recursive_partial_graph(
            recursive_graph=self.recursive_graph,
            recursive_graph_ref=self.recursive_graph_ref,
            recursive_graph_content_hash=self.recursive_graph_content_hash,
            root_node_ref=self.root_node_ref,
            root_design_problem_ref=self.root_design_problem_ref,
            recursive_budget=self.recursive_budget,
            observed_max_depth=self.observed_max_depth,
            nodes=self.nodes,
        )
        if self.terminal is not None:
            raise ValueError("recursive_partial_root_not_pending")

        failed_nodes = tuple(
            node for node in self.nodes if isinstance(node, RecursiveCycleFailedNode)
        )
        if len(failed_nodes) != 1 or failed_nodes[0].node_ref != self.failed_node_ref:
            raise ValueError("recursive_partial_failed_node_denominator_mismatch")
        failed_node = failed_nodes[0]
        parent_ref = parent_by_ref.get(failed_node.node_ref)
        if parent_ref is None or not isinstance(by_ref[parent_ref], RecursiveCyclePendingNode):
            raise ValueError("recursive_partial_failure_parent_not_pending")
        siblings = children_by_ref[parent_ref]
        failed_position = siblings.index(failed_node.node_ref)
        completed_sibling_refs = siblings[:failed_position]
        if not completed_sibling_refs or any(
            not isinstance(by_ref[sibling_ref], RecursiveCycleNode)
            for sibling_ref in completed_sibling_refs
        ):
            raise ValueError("recursive_partial_failure_without_completed_sibling")

        def require_pending_subtree(node_ref: str) -> None:
            if not isinstance(by_ref[node_ref], RecursiveCyclePendingNode):
                raise ValueError("recursive_partial_later_sibling_not_pending")
            for child_ref in children_by_ref[node_ref]:
                require_pending_subtree(child_ref)

        path_child_ref = failed_node.node_ref
        while path_child_ref != self.root_node_ref:
            path_parent_ref = parent_by_ref.get(path_child_ref)
            if path_parent_ref is None:
                raise ValueError("recursive_partial_failed_branch_outside_root")
            path_siblings = children_by_ref[path_parent_ref]
            path_position = path_siblings.index(path_child_ref)
            if path_parent_ref != parent_ref and any(
                not isinstance(by_ref[sibling_ref], RecursiveCycleNode)
                for sibling_ref in path_siblings[:path_position]
            ):
                raise ValueError("recursive_partial_prior_sibling_not_completed")
            for sibling_ref in path_siblings[path_position + 1 :]:
                require_pending_subtree(sibling_ref)
            path_child_ref = path_parent_ref

        current_parent: str | None = parent_ref
        while current_parent is not None:
            if not isinstance(by_ref[current_parent], RecursiveCyclePendingNode):
                raise ValueError("recursive_partial_failure_ancestor_not_pending")
            current_parent = parent_by_ref.get(current_parent)

        failure_origin = failed_node.failure.origin_node_ref
        if failure_origin not in by_ref or children_by_ref[failure_origin]:
            raise ValueError("recursive_partial_failure_origin_not_leaf")
        if failure_origin != failed_node.node_ref and not isinstance(
            by_ref[failure_origin], RecursiveCyclePendingNode
        ):
            raise ValueError("recursive_partial_failure_origin_already_completed")
        current = failure_origin
        while current != failed_node.node_ref:
            current = parent_by_ref.get(current, "")
            if not current:
                raise ValueError("recursive_partial_failure_origin_outside_failed_branch")

        failed_descendants: set[str] = set()

        def collect_failed_descendants(node_ref: str) -> None:
            for child_ref in children_by_ref[node_ref]:
                failed_descendants.add(child_ref)
                collect_failed_descendants(child_ref)

        collect_failed_descendants(failed_node.node_ref)
        if any(isinstance(by_ref[node_ref], RecursiveCycleNode) for node_ref in failed_descendants):
            raise ValueError("recursive_partial_failed_branch_contains_completed_descendant")

        payload = gy_artifact_self_identity_projection(self)
        payload.pop("leaf_nodes", None)
        payload.pop("pending_node_refs", None)
        payload.pop("failed_node", None)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


class RecursiveGenerationCyclePartialRunV4(_StrictModel):
    """Candidate checkpoint stopped before a sibling by replayable N5 capacity.

    This parent-level capacity policy is distinct from V2's owner-issued N6
    leaf budget terminal. It does not establish that the pending child would
    require physical N5 work.
    """

    schema_version: Literal["policyos.runtime.recursive_generation_cycle.partial.v4"] = (
        RECURSIVE_GENERATION_CYCLE_PARTIAL_V4_SCHEMA_VERSION
    )
    run_id: str = Field(min_length=1)
    controller_ref: str = RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF
    authority_scope: Literal["production", "contract_testing"] = "production"
    recursive_graph: RecursiveDesignGraph
    recursive_graph_ref: str = Field(min_length=1)
    recursive_graph_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    root_node_ref: str = Field(min_length=1)
    root_design_problem_ref: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    recursive_budget: RecursiveCycleBudget
    observed_max_depth: int = Field(ge=0)
    nodes: tuple[RecursiveCycleNode | RecursiveCyclePendingNode, ...] = Field(min_length=1)
    traversal_status: Literal["capacity_stopped"] = "capacity_stopped"
    traversal_stop_reason: Literal["standard_n5_invocation_capacity_exhausted"] = (
        "standard_n5_invocation_capacity_exhausted"
    )
    stop_parent_node_ref: str = Field(min_length=1)
    pending_child_node_ref: str = Field(min_length=1)
    pending_child_index: int = Field(ge=1, strict=True)
    frontier_node_refs: tuple[str, ...] = Field(min_length=1)
    invocation_exhaustion_witness: BudgetInvocationExhaustionWitness
    limitation_code: Literal["physical_need_not_established"] = "physical_need_not_established"
    terminal: None = None
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @property
    def leaf_nodes(self) -> tuple[RecursiveCycleNode, ...]:
        """Return completed leaf nodes without treating pending work as absent."""

        return tuple(
            node
            for node in self.nodes
            if isinstance(node, RecursiveCycleNode) and not node.child_refs
        )

    @property
    def pending_node_refs(self) -> tuple[str, ...]:
        """Return every graph member that traversal did not execute."""

        return tuple(
            node.node_ref for node in self.nodes if isinstance(node, RecursiveCyclePendingNode)
        )

    @model_validator(mode="after")
    def _verify_capacity_checkpoint(self) -> RecursiveGenerationCyclePartialRunV4:
        by_ref, children_by_ref, parent_by_ref = _validate_recursive_partial_graph(
            recursive_graph=self.recursive_graph,
            recursive_graph_ref=self.recursive_graph_ref,
            recursive_graph_content_hash=self.recursive_graph_content_hash,
            root_node_ref=self.root_node_ref,
            root_design_problem_ref=self.root_design_problem_ref,
            recursive_budget=self.recursive_budget,
            observed_max_depth=self.observed_max_depth,
            nodes=self.nodes,
        )
        if self.terminal is not None:
            raise ValueError("recursive_capacity_partial_root_not_pending")
        if (
            self.invocation_exhaustion_witness.standard_limit_units <= 0
            or self.invocation_exhaustion_witness.not_a_permit is not True
        ):
            raise ValueError("recursive_capacity_partial_witness_invalid")
        stop_parent = by_ref.get(self.stop_parent_node_ref)
        if not isinstance(stop_parent, RecursiveCyclePendingNode):
            raise ValueError("recursive_capacity_partial_stop_parent_not_pending")
        siblings = children_by_ref[self.stop_parent_node_ref]
        if (
            self.pending_child_index >= len(siblings)
            or siblings[self.pending_child_index] != self.pending_child_node_ref
            or parent_by_ref.get(self.pending_child_node_ref) != self.stop_parent_node_ref
        ):
            raise ValueError("recursive_capacity_partial_pending_child_binding_mismatch")

        pending_refs = {
            node_ref
            for node_ref, node in by_ref.items()
            if isinstance(node, RecursiveCyclePendingNode)
        }
        expected_frontier_refs: list[str] = []
        expected_pending_refs: set[str] = set()

        def require_pending_subtree(node_ref: str) -> None:
            if not isinstance(by_ref[node_ref], RecursiveCyclePendingNode):
                raise ValueError("recursive_capacity_partial_frontier_not_pending")
            if node_ref in expected_pending_refs:
                raise ValueError("recursive_capacity_partial_frontier_duplicate")
            expected_pending_refs.add(node_ref)
            for child_ref in children_by_ref[node_ref]:
                require_pending_subtree(child_ref)

        # The stop parent is still being expanded. Its first not-yet-visited
        # child and every later sibling subtree are the first frontier slice.
        expected_pending_refs.add(self.stop_parent_node_ref)
        later_refs = siblings[self.pending_child_index :]
        expected_frontier_refs.extend(later_refs)
        for frontier_ref in later_refs:
            require_pending_subtree(frontier_ref)
        path_child_ref = self.stop_parent_node_ref
        while path_child_ref != self.root_node_ref:
            path_parent_ref = parent_by_ref.get(path_child_ref)
            if path_parent_ref is None:
                raise ValueError("recursive_capacity_partial_stop_outside_root")
            path_siblings = children_by_ref[path_parent_ref]
            path_position = path_siblings.index(path_child_ref)
            if any(
                not isinstance(by_ref[prior_ref], RecursiveCycleNode)
                for prior_ref in path_siblings[:path_position]
            ):
                raise ValueError("recursive_capacity_partial_prior_sibling_not_completed")
            later_refs = path_siblings[path_position + 1 :]
            expected_frontier_refs.extend(later_refs)
            for frontier_ref in later_refs:
                require_pending_subtree(frontier_ref)
            expected_pending_refs.add(path_parent_ref)
            path_child_ref = path_parent_ref

        if pending_refs != expected_pending_refs:
            raise ValueError("recursive_capacity_partial_frontier_denominator_mismatch")
        if self.frontier_node_refs != tuple(expected_frontier_refs):
            raise ValueError("recursive_capacity_partial_frontier_order_mismatch")
        if not any(
            node.cycle_run is not None
            and any(
                cycle.simulation.simulation_result_ref is not None
                for cycle in node.cycle_run.cycles
            )
            for node in self.nodes
            if isinstance(node, RecursiveCycleNode) and not node.child_refs
        ):
            raise ValueError("recursive_capacity_partial_without_completed_n5")

        payload = gy_artifact_self_identity_projection(self)
        payload.pop("leaf_nodes", None)
        payload.pop("pending_node_refs", None)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("recursive_generation_cycle_content_hash_mismatch")
        return self


def _recursive_capacity_prefix_work(
    *,
    completed_nodes: Mapping[str, RecursiveCycleNode],
    witness: BudgetInvocationExhaustionWitness,
    store: ArtifactStore,
) -> bool:
    """Match owner witness operations to selected physical work in completed nodes."""

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationResult,
    )

    expected_ids = {operation_id for operation_id, _ in witness.terminal_witnesses}
    observed: dict[str, str] = {}
    loaded_results: set[tuple[str, str | None]] = set()
    for node in completed_nodes.values():
        cycle_run = node.cycle_run
        if cycle_run is None:
            continue
        for cycle in cycle_run.cycles:
            simulation = cycle.simulation
            result_ref = simulation.simulation_result_ref
            if result_ref is None:
                if simulation.status == "joint_simulated":
                    return False
                continue
            if not simulation.simulation_ref:
                return False
            result_key = (str(result_ref.artifact_id), result_ref.manifest_profile_sha256)
            if result_key in loaded_results:
                continue
            loaded_results.add(result_key)
            try:
                result = load_joint_simulation_result(
                    result_ref,
                    store=store,
                    expected_receipt_payload_hash=simulation.simulation_ref,
                )
                if type(result) is not JointSimulationResult:
                    return False
                work_items = result.physical_work_observations
            except (OSError, RuntimeError, TypeError, ValueError):
                return False
            for item in work_items:
                operation_id = item.invocation_quota_operation_id
                if (
                    operation_id is None
                    or item.invocation_quota_profile_digest != witness.profile_digest
                    or item.invocation_quota_purpose != "standard"
                    or item.invocation_quota_status not in {"completed", "failed"}
                    or item.invocation_quota_status != item.status
                ):
                    return False
                encoded = gy_content_hash(item.model_dump(mode="json"))
                prior = observed.get(operation_id)
                if prior is not None and prior != encoded:
                    return False
                observed[operation_id] = encoded
    return bool(observed) and set(observed) == expected_ids


def verify_recursive_standard_n5_capacity_partial_run(
    partial: RecursiveGenerationCyclePartialRunV4,
    *,
    observer: ProducerBudgetObserver,
    store: ArtifactStore,
) -> bool:
    """Reopen the quota owner and N5 results bound by a capacity partial.

    Intrinsic validation of V4 is not owner custody. This reader checks the
    exact canonical observer and selected N5 result artifacts again.
    """

    if type(partial) is not RecursiveGenerationCyclePartialRunV4:
        raise RecursiveGenerationCycleError("recursive_capacity_partial_untyped")
    try:
        partial = RecursiveGenerationCyclePartialRunV4.model_validate(
            partial.model_dump(mode="json")
        )
    except (TypeError, ValueError) as exc:
        raise RecursiveGenerationCycleError(
            "recursive_capacity_partial_intrinsic_history_invalid"
        ) from exc
    if (
        type(observer) is not ProducerBudgetObserver
        or "observe_standard_invocation_capacity" in vars(observer)
        or "verify_standard_invocation_exhaustion" in vars(observer)
    ):
        raise RecursiveGenerationCycleError("recursive_capacity_partial_owner_not_canonical")
    witness = partial.invocation_exhaustion_witness
    try:
        if ProducerBudgetObserver.verify_standard_invocation_exhaustion(
            observer, witness
        ) is not True or not _recursive_capacity_prefix_work(
            completed_nodes={
                node.node_ref: node
                for node in partial.nodes
                if isinstance(node, RecursiveCycleNode)
            },
            witness=witness,
            store=store,
        ):
            raise RecursiveGenerationCycleError("recursive_capacity_partial_owner_replay_mismatch")
    except ProducerBudgetSourceError as exc:
        raise RecursiveGenerationCycleError(
            "recursive_capacity_partial_owner_not_established"
        ) from exc
    return True


def verify_recursive_standard_n5_capacity_partial_run_historical(
    partial: RecursiveGenerationCyclePartialRunV4,
    *,
    settlement_store: BudgetMiddleware,
    expected_run_binding: BudgetLedgerProducerRunBinding,
    expected_policy: BudgetInvocationQuotaPolicy,
    store: ArtifactStore,
) -> bool:
    """Replay a persisted V4 stop from independently reopened completed-run owners.

    The caller must resolve the original completed NL binding and the selected
    generic N5 input policy through their canonical owners. This reader only
    replays the historical ledger witness and the exact completed-prefix N5
    result artifacts; it does not derive either selection from the witness.

    Args:
        partial: Persisted recursive capacity checkpoint.
        settlement_store: Existing read-only settlement owner for the source run.
        expected_run_binding: Original binding reopened from the completed NL job.
        expected_policy: Policy reopened from the selected generic N5 input owner.
        store: Canonical artifact store used to reopen selected N5 results.

    Returns:
        True when the owner witness and all terminal standard N5 operations
        exactly match the completed prefix in this partial.

    Raises:
        RecursiveGenerationCycleError: If intrinsic history, owner evidence, or
            selected N5 result bindings cannot be established.
    """
    if type(partial) is not RecursiveGenerationCyclePartialRunV4:
        raise RecursiveGenerationCycleError("recursive_capacity_partial_untyped")
    try:
        partial = RecursiveGenerationCyclePartialRunV4.model_validate(
            partial.model_dump(mode="json")
        )
    except (TypeError, ValueError) as exc:
        raise RecursiveGenerationCycleError(
            "recursive_capacity_partial_intrinsic_history_invalid"
        ) from exc
    witness = partial.invocation_exhaustion_witness
    try:
        if (
            verify_standard_invocation_exhaustion_historical(
                settlement_store=settlement_store,
                expected_run_binding=expected_run_binding,
                expected_policy=expected_policy,
                witness=witness,
            )
            is not True
        ):
            raise RecursiveGenerationCycleError("recursive_capacity_partial_owner_replay_mismatch")
    except ProducerBudgetSourceError as exc:
        raise RecursiveGenerationCycleError(
            "recursive_capacity_partial_owner_not_established"
        ) from exc
    if not _recursive_capacity_prefix_work(
        completed_nodes={
            node.node_ref: node for node in partial.nodes if isinstance(node, RecursiveCycleNode)
        },
        witness=witness,
        store=store,
    ):
        raise RecursiveGenerationCycleError(
            "recursive_capacity_partial_completed_prefix_work_mismatch"
        )
    return True


def _observed_standard_exhaustion_witness(
    observer: object | None,
) -> BudgetInvocationExhaustionWitness | None:
    """Return only a freshly owner-replayed standard exhaustion witness."""

    if (
        type(observer) is not ProducerBudgetObserver
        or "observe_standard_invocation_capacity" in vars(observer)
        or "verify_standard_invocation_exhaustion" in vars(observer)
    ):
        return None
    try:
        observation = ProducerBudgetObserver.observe_standard_invocation_capacity(observer)
        if (
            type(observation) is not BudgetInvocationCapacityObservation
            or observation.status != "exhausted"
            or observation.predicate_basis != "independently_reconciled"
            or observation.not_a_permit is not True
        ):
            return None
        witness = observation.exhaustion_witness
        if type(witness) is not BudgetInvocationExhaustionWitness:
            return None
        if (
            ProducerBudgetObserver.verify_standard_invocation_exhaustion(observer, witness)
            is not True
        ):
            return None
        return witness
    except (OSError, ProducerBudgetSourceError, RuntimeError, TypeError, ValueError):
        return None


def _build_sibling_failed_recursive_run_v3(
    *,
    recursive_graph: RecursiveDesignGraph,
    problems_by_node: Mapping[str, DesignProblem],
    problem_refs_by_node: Mapping[str, str],
    completed_nodes_by_ref: Mapping[str, RecursiveCycleNode],
    children_by_node: Mapping[str, list[str]],
    parent_by_node: Mapping[str, str],
    depths: Mapping[str, int],
    recursive_budget: RecursiveCycleBudget,
    failed_node_ref: str,
    failure: RecursiveCycleFailure,
    authority_scope: Literal["production", "contract_testing"],
) -> RecursiveGenerationCyclePartialRunV3:
    """Seal completed siblings, the exact failed branch, and unvisited nodes."""

    if failed_node_ref in completed_nodes_by_ref or failed_node_ref not in problems_by_node:
        raise RecursiveGenerationCycleError("recursive_partial_failure_node_unresolved")
    nodes: list[RecursiveCycleNode | RecursiveCyclePendingNode | RecursiveCycleFailedNode] = []
    for node_ref in recursive_graph.node_refs:
        completed = completed_nodes_by_ref.get(node_ref)
        if completed is not None:
            nodes.append(completed)
        elif node_ref == failed_node_ref:
            nodes.append(
                RecursiveCycleFailedNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=tuple(children_by_node[node_ref]),
                    design_problem_ref=problem_refs_by_node[node_ref],
                    failure=failure,
                )
            )
        else:
            nodes.append(
                RecursiveCyclePendingNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=tuple(children_by_node[node_ref]),
                    design_problem_ref=problem_refs_by_node[node_ref],
                )
            )
    node_payloads = [node.model_dump(mode="json") for node in nodes]
    payload: dict[str, object] = {
        "schema_version": RECURSIVE_GENERATION_CYCLE_PARTIAL_V3_SCHEMA_VERSION,
        "run_id": f"recursive:{recursive_graph.graph_id}",
        "controller_ref": RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF,
        "authority_scope": authority_scope,
        "recursive_graph": recursive_graph.model_dump(mode="json"),
        "recursive_graph_ref": recursive_graph.graph_ref,
        "recursive_graph_content_hash": gy_content_hash(recursive_graph.model_dump(mode="json")),
        "root_node_ref": recursive_graph.root_design_ref,
        "root_design_problem_ref": problem_refs_by_node[recursive_graph.root_design_ref],
        "recursive_budget": recursive_budget.model_dump(mode="json"),
        "observed_max_depth": max(depths.values()),
        "nodes": node_payloads,
        "traversal_status": "failed",
        "traversal_failure_reason": "independent_sibling_failure",
        "failed_node_ref": failed_node_ref,
        "terminal": None,
    }
    return RecursiveGenerationCyclePartialRunV3.model_validate(
        {
            **payload,
            "nodes": tuple(nodes),
            "content_hash": gy_content_hash(payload),
        }
    )


def _build_budget_stopped_recursive_run_v2(
    *,
    recursive_graph: RecursiveDesignGraph,
    problems_by_node: Mapping[str, DesignProblem],
    problem_refs_by_node: Mapping[str, str],
    completed_nodes_by_ref: Mapping[str, RecursiveCycleNode],
    children_by_node: Mapping[str, list[str]],
    parent_by_node: Mapping[str, str],
    depths: Mapping[str, int],
    recursive_budget: RecursiveCycleBudget,
    budget_stop_node_ref: str,
    frontier_node_refs: tuple[str, ...],
    authority_scope: Literal["production", "contract_testing"],
) -> RecursiveGenerationCyclePartialRunV2:
    """Seal actual routed children and graph-only pending nodes in one checkpoint."""

    nodes: list[RecursiveCycleNode | RecursiveCyclePendingNode] = []
    for node_ref in recursive_graph.node_refs:
        completed = completed_nodes_by_ref.get(node_ref)
        if completed is not None:
            nodes.append(completed)
        else:
            nodes.append(
                RecursiveCyclePendingNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=tuple(children_by_node[node_ref]),
                    design_problem_ref=problem_refs_by_node[node_ref],
                )
            )
    node_payloads = [node.model_dump(mode="json") for node in nodes]
    payload: dict[str, object] = {
        "schema_version": RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION,
        "run_id": f"recursive:{recursive_graph.graph_id}",
        "controller_ref": RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF,
        "authority_scope": authority_scope,
        "recursive_graph": recursive_graph.model_dump(mode="json"),
        "recursive_graph_ref": recursive_graph.graph_ref,
        "recursive_graph_content_hash": gy_content_hash(recursive_graph.model_dump(mode="json")),
        "root_node_ref": recursive_graph.root_design_ref,
        "root_design_problem_ref": problem_refs_by_node[recursive_graph.root_design_ref],
        "recursive_budget": recursive_budget.model_dump(mode="json"),
        "observed_max_depth": max(depths.values()),
        "nodes": node_payloads,
        "traversal_status": "budget_stopped",
        "traversal_stop_reason": "child_budget_exhausted",
        "budget_stop_node_ref": budget_stop_node_ref,
        "frontier_node_refs": list(frontier_node_refs),
        "terminal": None,
    }
    return RecursiveGenerationCyclePartialRunV2.model_validate(
        {
            **payload,
            "nodes": tuple(nodes),
            "content_hash": gy_content_hash(payload),
        }
    )


def _build_capacity_stopped_recursive_run_v4(
    *,
    recursive_graph: RecursiveDesignGraph,
    problems_by_node: Mapping[str, DesignProblem],
    problem_refs_by_node: Mapping[str, str],
    completed_nodes_by_ref: Mapping[str, RecursiveCycleNode],
    children_by_node: Mapping[str, list[str]],
    parent_by_node: Mapping[str, str],
    depths: Mapping[str, int],
    recursive_budget: RecursiveCycleBudget,
    stop_parent_node_ref: str,
    pending_child_node_ref: str,
    pending_child_index: int,
    frontier_node_refs: tuple[str, ...],
    exhaustion_witness: BudgetInvocationExhaustionWitness,
    authority_scope: Literal["production", "contract_testing"],
) -> RecursiveGenerationCyclePartialRunV4:
    """Seal completed N5 work and the exact next-child capacity frontier."""

    nodes: list[RecursiveCycleNode | RecursiveCyclePendingNode] = []
    for node_ref in recursive_graph.node_refs:
        completed = completed_nodes_by_ref.get(node_ref)
        if completed is not None:
            nodes.append(completed)
        else:
            nodes.append(
                RecursiveCyclePendingNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=tuple(children_by_node[node_ref]),
                    design_problem_ref=problem_refs_by_node[node_ref],
                )
            )
    node_payloads = [node.model_dump(mode="json") for node in nodes]
    payload: dict[str, object] = {
        "schema_version": RECURSIVE_GENERATION_CYCLE_PARTIAL_V4_SCHEMA_VERSION,
        "run_id": f"recursive:{recursive_graph.graph_id}",
        "controller_ref": RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF,
        "authority_scope": authority_scope,
        "recursive_graph": recursive_graph.model_dump(mode="json"),
        "recursive_graph_ref": recursive_graph.graph_ref,
        "recursive_graph_content_hash": gy_content_hash(recursive_graph.model_dump(mode="json")),
        "root_node_ref": recursive_graph.root_design_ref,
        "root_design_problem_ref": problem_refs_by_node[recursive_graph.root_design_ref],
        "recursive_budget": recursive_budget.model_dump(mode="json"),
        "observed_max_depth": max(depths.values()),
        "nodes": node_payloads,
        "traversal_status": "capacity_stopped",
        "traversal_stop_reason": "standard_n5_invocation_capacity_exhausted",
        "stop_parent_node_ref": stop_parent_node_ref,
        "pending_child_node_ref": pending_child_node_ref,
        "pending_child_index": pending_child_index,
        "frontier_node_refs": list(frontier_node_refs),
        "invocation_exhaustion_witness": exhaustion_witness.model_dump(mode="json"),
        "limitation_code": "physical_need_not_established",
        "terminal": None,
    }
    return RecursiveGenerationCyclePartialRunV4.model_validate(
        {
            **payload,
            "nodes": tuple(nodes),
            "content_hash": gy_content_hash(payload),
        }
    )


CycleControllerFactory = Callable[[str, DesignProblem], GenerationCycleController]


class DepthNStrangleReceipt(_StrictModel):
    """Live, source-bound caller census for the depth-N recursive route.

    A caller census is positive evidence only when the controlled source slice
    was present and parsed successfully. Missing source or a parse failure is
    therefore represented separately from a real prohibited caller; both are
    non-positive outcomes, but they require different remediation.
    """

    status: Literal["strangled", "drift", "not_established"]
    source_state: Literal[
        "available",
        "missing",
        "parse_error",
        "read_error",
        "not_established",
    ]
    source_content_hash: str | None = Field(
        default=None,
        pattern=r"^sha256:[0-9a-f]{64}$",
    )
    parse_errors: tuple[str, ...] = ()
    default_controller: str
    predecessor_symbols: tuple[str, ...]
    production_fixture_callers: tuple[str, ...]
    production_default_routes: tuple[str, ...]
    verified_by: str = (
        "polisyos.runtime.quality.recursive_generation_cycle.recompute_depth_n_strangle_receipt"
    )


def recompute_depth_n_strangle_receipt(
    repo_root: Path | None = None,
) -> DepthNStrangleReceipt:
    """Census the controlled source slice and surviving fixture callers.

    The receipt binds successful results to the bytes of ``src/polisyos``
    Python files. It deliberately withholds a source hash when the slice is
    absent, unreadable, or contains syntax errors, because a partial census is
    not evidence that the legacy caller is gone.
    """

    if repo_root is None:
        return DepthNStrangleReceipt(
            status="not_established",
            source_state="not_established",
            source_content_hash=None,
            parse_errors=(),
            default_controller="unresolved",
            predecessor_symbols=tuple(sorted(_LEGACY_RECURSIVE_FIXTURE_SYMBOLS)),
            production_fixture_callers=(),
            production_default_routes=(),
        )
    root = repo_root.resolve()
    source_root = root / "src/polisyos"
    callers: list[str] = []
    default_routes: list[str] = []
    parse_errors: list[str] = []
    source_files: dict[str, str] = {}
    if not source_root.is_dir():
        return DepthNStrangleReceipt(
            status="not_established",
            source_state="missing",
            source_content_hash=None,
            parse_errors=(),
            default_controller="unresolved",
            predecessor_symbols=tuple(sorted(_LEGACY_RECURSIVE_FIXTURE_SYMBOLS)),
            production_fixture_callers=(),
            production_default_routes=(),
        )

    for path in sorted(source_root.rglob("*.py")):
        relative = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            source_files[relative] = "sha256:" + hashlib.sha256(raw).hexdigest()
            tree = ast.parse(raw.decode("utf-8"), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError) as exc:
            parse_errors.append(f"{relative}:parse_error:{type(exc).__name__}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                node.name in _LEGACY_RECURSIVE_FIXTURE_SYMBOLS
            ):
                callers.append(f"{path.relative_to(root)}:{node.lineno}:definition:{node.name}")
            if not isinstance(node, ast.Call):
                continue
            symbol = None
            if isinstance(node.func, ast.Name):
                symbol = node.func.id
            elif isinstance(node.func, ast.Attribute):
                symbol = node.func.attr
            if symbol in _LEGACY_RECURSIVE_FIXTURE_SYMBOLS:
                callers.append(f"{path.relative_to(root)}:{node.lineno}:call:{symbol}")
            if symbol == _DEFAULT_RECURSIVE_ROUTE_SYMBOL:
                default_routes.append(f"{path.relative_to(root)}:{node.lineno}:call:{symbol}")
    ordered = tuple(sorted(set(callers)))
    routes = tuple(sorted(set(default_routes)))
    ordered_parse_errors = tuple(sorted(set(parse_errors)))
    if ordered_parse_errors:
        source_state: Literal["available", "missing", "parse_error", "read_error"] = (
            "read_error"
            if any(item.rsplit(":", 1)[-1] == "OSError" for item in ordered_parse_errors)
            else "parse_error"
        )
        source_content_hash = None
        status: Literal["strangled", "drift", "not_established"] = "not_established"
    else:
        source_state = "available"
        source_content_hash = gy_content_hash(
            {
                "scope": "src/polisyos",
                "files": dict(sorted(source_files.items())),
            }
        )
        status = "drift" if ordered or not routes else "strangled"
    return DepthNStrangleReceipt(
        status=status,
        source_state=source_state,
        source_content_hash=source_content_hash,
        parse_errors=ordered_parse_errors,
        default_controller=(RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF if routes else "unresolved"),
        predecessor_symbols=tuple(sorted(_LEGACY_RECURSIVE_FIXTURE_SYMBOLS)),
        production_fixture_callers=ordered,
        production_default_routes=routes,
    )


def _problem_ref(problem: DesignProblem) -> str:
    return gy_content_hash(problem.model_dump(mode="json"))


def _leaf_terminal(run: GenerationCycleRun) -> SearchTerminalState:
    return generation_cycle_terminal_state(run)


def _fold_unary_terminal(child: RecursiveCycleNode) -> SearchTerminalState:
    return SearchTerminalState(
        kind=child.terminal.kind,
        reason="Unary recursive parent routed its child terminal without widening authority.",
        blocking_obligations=list(child.terminal.blocking_obligations),
        budget_kind=child.terminal.budget_kind,
        costed_plan=child.terminal.costed_plan,
        data_need_spec=child.terminal.data_need_spec,
    )


def _fold_composed_terminal(
    *,
    children: tuple[RecursiveCycleNode, ...],
    joint_simulation: JointSimulationResult,
    certificate: CompositionCertificate,
) -> SearchTerminalState:
    kinds = {child.terminal.kind for child in children}
    unsupported_simulation = _joint_simulation_is_unsupported(joint_simulation)
    positive_terminal = SearchTerminalKind.GROUNDED_ADMISSIBLE
    if SearchTerminalKind.GROUNDED_ABSTENTION in kinds:
        positive_terminal = SearchTerminalKind.GROUNDED_ABSTENTION
    elif SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE in kinds:
        positive_terminal = SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE
    decision = select_search_terminal(
        SearchExitDecisionInputs(
            spec_gap=SearchTerminalKind.A_SPEC_GAP in kinds,
            tool_failure=SearchTerminalKind.TOOL_FAILURE in kinds,
            composition_invalid=(
                certificate.verdict == "not_composable"
                or SearchTerminalKind.COMPOSITION_INVALID in kinds
            ),
            recursive_blocked=(
                unsupported_simulation or SearchTerminalKind.RECURSIVE_BLOCKED in kinds
            ),
            poor_recall=SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED in kinds,
            human_decision_required=SearchTerminalKind.HUMAN_DECISION_REQUIRED in kinds,
            acquisition_required=SearchTerminalKind.ACQUISITION_REQUIRED in kinds,
            budget_exhausted_kind=(
                "recursive" if SearchTerminalKind.BUDGET_EXHAUSTED in kinds else None
            ),
            frontier_stable=SearchTerminalKind.FRONTIER_STABLE in kinds,
            positive_terminal=positive_terminal,
        )
    )
    blockers = [blocker for child in children for blocker in child.terminal.blocking_obligations]
    blockers.extend(obligation.obligation_id for obligation in certificate.unresolved_obligations)
    blockers.extend(joint_simulation.feedback_classification.support_blockers)
    acquisition_children = tuple(
        child
        for child in children
        if child.terminal.kind is SearchTerminalKind.ACQUISITION_REQUIRED
    )
    costed_plan = None
    data_need_spec = None
    if decision.kind is SearchTerminalKind.ACQUISITION_REQUIRED and len(acquisition_children) == 1:
        costed_plan = acquisition_children[0].terminal.costed_plan
        data_need_spec = acquisition_children[0].terminal.data_need_spec
    return SearchTerminalState(
        kind=decision.kind,
        reason=decision.reason,
        blocking_obligations=list(dict.fromkeys(blockers)),
        budget_kind=decision.budget_kind,
        costed_plan=costed_plan,
        data_need_spec=data_need_spec,
    )


def _blocked_parent_terminal(reason: str) -> SearchTerminalState:
    return SearchTerminalState(
        kind=SearchTerminalKind.RECURSIVE_BLOCKED,
        reason="Recursive parent lacks owner-proven coupling/composition inputs.",
        blocking_obligations=[reason],
    )


def _fold_uncertified_joint_terminal(node: RecursiveCycleNode) -> SearchTerminalState:
    """Preserve the correct blocked reason for a joint result without a certificate."""
    simulation = node.joint_simulation
    if simulation is None or node.composition_certificate is not None:
        raise ValueError("recursive_uncertified_joint_not_established")
    if _joint_simulation_is_unsupported(simulation):
        return _blocked_parent_terminal("unsupported_coupling_gated")
    if node.joint_candidate_selection is not None:
        return _blocked_parent_terminal("observed_coupling_evidence_missing")
    # Preserve the prior blocked fold for a legacy uncomposed shape; the
    # node's validator rejects a supported result without a selection or certificate.
    return _blocked_parent_terminal("unsupported_coupling_gated")


_RECURSIVE_N5_PARENT_REFUSAL_CODES = frozenset(
    {
        "recursive_n5_invocation_selection_not_established",
        "n5_physical_budget_scope_not_established",
        "n5_physical_budget_scope_binding_mismatch",
        "n5_physical_usd_reservation_not_established",
        "n5_physical_budget_cap_mismatch",
        "n5_invocation_quota_owner_not_established",
        "n5_invocation_quota_settlement_owner_mismatch",
        "n5_invocation_quota_run_binding_mismatch",
        "n5_invocation_selected_profile_not_established",
        "n5_invocation_quota_profile_not_established",
        "n5_invocation_quota_selection_mismatch",
        "n5_invocation_quota_capacity_not_established",
        "n5_invocation_quota_exhausted",
        "n5_invocation_selection_conflict",
        "n5_invocation_selection_failed",
        "n5_invocation_selection_not_established",
        "n5_protected_purpose_not_established",
    }
)


_UNCOMPOSED_PARENT_DIAGNOSTIC_CODES = (
    frozenset(
        {
            "observed_coupling_evidence_missing",
            "subdesign_contract_denominator_missing",
            "recursive_coupling_design_ref_mismatch",
            "recursive_coupling_child_denominator_mismatch",
            "recursive_coupling_edge_unresolved",
            "recursive_subdesign_denominator_mismatch",
            "recursive_subdesign_terminal_binding_mismatch",
            "recursive_n5_atom_problem_binding_mismatch",
            "recursive_n5_outcome_problem_binding_mismatch",
        }
    )
    | _RECURSIVE_N5_PARENT_REFUSAL_CODES
)


def _recursive_n5_parent_refusal(exc: Exception) -> str:
    """Preserve known refusal categories without admitting arbitrary diagnostics."""
    code = str(exc)
    if isinstance(exc, ProducerBudgetSourceError) and code in _RECURSIVE_N5_PARENT_REFUSAL_CODES:
        return code
    return "recursive_n5_invocation_selection_not_established"


def _fold_uncomposed_parent_terminal(
    terminal: SearchTerminalState,
) -> SearchTerminalState:
    """Admit only conservative blocked shape for bounded uncomposed parents.

    The blocker codes are router diagnostics, not recomputed facts about the
    source coupling graph or subdesign contracts. Full and partial artifacts lack enough
    owner evidence to re-establish those predicates, so this helper preserves
    only a blocked terminal with no acquisition, budget, or positive authority
    fields; all other terminal shapes are refused.
    """

    if (
        terminal.kind is not SearchTerminalKind.RECURSIVE_BLOCKED
        or len(terminal.blocking_obligations) != 1
        or terminal.blocking_obligations[0] not in _UNCOMPOSED_PARENT_DIAGNOSTIC_CODES
    ):
        raise ValueError("recursive_parent_not_conservatively_blocked")
    expected = _blocked_parent_terminal(terminal.blocking_obligations[0])
    if terminal != expected:
        raise ValueError("recursive_parent_terminal_not_owner_derived")
    return expected


def _composition_claims_for_problem(
    problem: DesignProblem,
    *,
    target_policy_program_ref: str,
) -> tuple[dict[str, object], ...]:
    """Project parent intent as candidate-only claims for the composition owner."""

    problem_ref = _problem_ref(problem)
    return tuple(
        {
            "claim_ref": (
                f"claim://design-problem/{problem_ref.removeprefix('sha256:')}/"
                f"objective/{objective.objective_id}"
            ),
            "claim_text": objective.description,
            "outcome_variable": problem.outcome_of_interest.target_variable,
            "target_policy_program_ref": target_policy_program_ref,
            "grounding_refs": (),
        }
        for objective in problem.objectives
    )


def _branch_binding_issue(
    *,
    node_ref: str,
    problem_ref: str,
    problem: DesignProblem,
    child_refs: tuple[str, ...],
    routed_children: tuple[RecursiveCycleNode, ...],
    request: JointSimulationRequest,
    subdesigns: tuple[SubDesignContract, ...],
) -> str | None:
    """Resolve branch identities before N5 or composition can emit evidence."""

    graph = request.coupling_graph
    if graph is None:
        return "observed_coupling_evidence_missing"
    if graph.design_ref != node_ref:
        return "recursive_coupling_design_ref_mismatch"
    if len(graph.module_refs) != len(set(graph.module_refs)) or set(graph.module_refs) != set(
        child_refs
    ):
        return "recursive_coupling_child_denominator_mismatch"
    if any(
        edge.source_module_ref not in child_refs or edge.target_module_ref not in child_refs
        for edge in graph.interaction_edges
    ):
        return "recursive_coupling_edge_unresolved"
    by_workspace = {subdesign.workspace_id: subdesign for subdesign in subdesigns}
    if len(by_workspace) != len(subdesigns) or set(by_workspace) != set(child_refs):
        return "recursive_subdesign_denominator_mismatch"
    routed_by_ref = {child.node_ref: child for child in routed_children}
    for child_ref in child_refs:
        subdesign = by_workspace[child_ref]
        routed = routed_by_ref[child_ref]
        if (
            subdesign.parent_workspace_id != node_ref
            or subdesign.search_exit.workspace_id != child_ref
            or subdesign.search_exit.terminal_state != routed.terminal
        ):
            return "recursive_subdesign_terminal_binding_mismatch"
    if any(atom.problem_frame_ref != problem_ref for atom in request.intervention_atoms):
        return "recursive_n5_atom_problem_binding_mismatch"
    if problem.outcome_of_interest.target_variable not in request.selected_outcomes:
        return "recursive_n5_outcome_problem_binding_mismatch"
    return None


def build_default_recursive_generation_cycle_controller(
    *,
    promotion_runtime: PromotionRuntime,
    eval_safety_verifier: EvalSafetyVerifierPort | None = None,
    repo_root: Path | None = None,
    model_id: str | None = None,
    catalog_run_profile: CatalogRunProfile | None = None,
    catalog_serving_source: CatalogServingSourcePaths | None = None,
    capability_resolver: core_contracts.CapabilityResolverPort | None = None,
    measurement_root_execution_binding: MeasurementRootExecutionBinding | None = None,
) -> RecursiveGenerationCycleController:
    """Build the production router from one container-owned promotion runtime."""

    return RecursiveGenerationCycleController(
        repo_root=repo_root,
        model_id=model_id,
        catalog_run_profile=catalog_run_profile,
        catalog_serving_source=catalog_serving_source,
        capability_resolver=capability_resolver,
        measurement_root_execution_binding=measurement_root_execution_binding,
        promotion_runtime=promotion_runtime,
        eval_safety_verifier=eval_safety_verifier,
    )


class RecursiveGenerationCycleController:
    """Route a recursive design graph and delegate every engine decision."""

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        model_id: str | None = None,
        catalog_run_profile: CatalogRunProfile | None = None,
        catalog_serving_source: CatalogServingSourcePaths | None = None,
        capability_resolver: core_contracts.CapabilityResolverPort | None = None,
        measurement_root_execution_binding: MeasurementRootExecutionBinding | None = None,
        promotion_runtime: PromotionRuntime | None = None,
        artifact_store: ArtifactStore | None = None,
        eval_safety_verifier: EvalSafetyVerifierPort | None = None,
        epoch_subject_authority: core_contracts.EpochValidityPreN9SubjectAuthority | None = None,
        epoch_validity_gate: core_contracts.EpochValidityAuthorityGate | None = None,
        epoch_n9_evidence_resolver: core_contracts.EpochValidityN9EvidenceResolver | None = None,
    ) -> None:
        if capability_resolver is not None:
            from polisyos.core.artifacts import matches_runtime_protocol
            from polisyos.core.contracts import CapabilityResolverPort

            if not matches_runtime_protocol(capability_resolver, CapabilityResolverPort):
                raise TypeError("recursive_capability_resolver_invalid")
        if promotion_runtime is not None and any(
            dependency is not None
            for dependency in (
                epoch_subject_authority,
                epoch_validity_gate,
                epoch_n9_evidence_resolver,
            )
        ):
            raise ValueError("recursive_epoch_dependencies_must_be_runtime_derived")
        if promotion_runtime is not None:
            if artifact_store is not None and artifact_store is not promotion_runtime.store:
                raise ValueError("recursive_artifact_store_owner_mismatch")
            artifact_store = promotion_runtime.store
        self._repo_root = repo_root.resolve() if repo_root is not None else None
        self._leaf_model_id = model_id
        self._catalog_run_profile = catalog_run_profile
        self._catalog_serving_source = catalog_serving_source
        self._capability_resolver = capability_resolver
        self._measurement_root_execution_binding = measurement_root_execution_binding
        self._promotion_runtime = promotion_runtime
        self._artifact_store = artifact_store
        self._eval_safety_verifier = eval_safety_verifier
        self._epoch_subject_authority = epoch_subject_authority or getattr(
            promotion_runtime, "epoch_subject_authority", None
        )
        self._epoch_validity_gate = epoch_validity_gate or getattr(
            promotion_runtime, "epoch_validity_gate", None
        )
        self._epoch_n9_evidence_resolver = epoch_n9_evidence_resolver or getattr(
            promotion_runtime, "epoch_n9_evidence_resolver", None
        )
        self._cycle_controller_factory: CycleControllerFactory | None = None
        self._authority_scope: Literal["production", "contract_testing"] = "production"
        self._joint_simulation_controller = JointSimulationHorizonController()

    @classmethod
    def for_contract_testing(
        cls,
        *,
        cycle_controller_factory: CycleControllerFactory,
        repo_root: Path | None = None,
        artifact_store: ArtifactStore | None = None,
    ) -> RecursiveGenerationCycleController:
        """Build a visibly non-production router over canonical scripted N6 owners."""

        controller = cls(repo_root=repo_root, artifact_store=artifact_store)
        controller._cycle_controller_factory = cycle_controller_factory
        controller._authority_scope = "contract_testing"
        return controller

    async def run(
        self,
        recursive_graph: RecursiveDesignGraph,
        *,
        problems_by_node: Mapping[str, DesignProblem],
        budget_state: BudgetState,
        _producer_budget_reconciler: Callable[[BudgetState], None] | None = None,
        physical_n5_budget_scope: VerifiedNLJobBudgetScope | None = None,
        recursive_budget: RecursiveCycleBudget,
        joint_simulation_requests_by_node: Mapping[str, JointSimulationRequest] | None = None,
        joint_candidate_selections_by_node: Mapping[
            str,
            ParentJointCandidateSelectionV1
            | ParentJointCandidateSelectionV2
            | ParentJointCandidateSelectionV3
            | ParentJointCandidateSelectionV4,
        ]
        | None = None,
        joint_candidate_currentness_resolvers_by_node: Mapping[str, Callable[[], bool]]
        | None = None,
        subdesign_contracts_by_node: Mapping[str, tuple[SubDesignContract, ...]] | None = None,
        cycle_substrate_contexts_by_node: Mapping[str, CycleSubstrateContext] | None = None,
        candidate_simulation_handoffs_by_node: Mapping[str, CandidateSimulationContextHandoff]
        | None = None,
        candidate_simulation_currentness_resolvers_by_node: Mapping[str, Callable[[], bool]]
        | None = None,
        generic_simulation_handoffs_by_node: Mapping[str, GenericCycleSimulationContextHandoffV1]
        | None = None,
        generic_simulation_currentness_resolvers_by_node: Mapping[str, Callable[[], bool]]
        | None = None,
        generic_n4_child_profile_set_ref: CASArtifactRef | None = None,
        generic_n4_source_repository: GenerationSourceRepository | None = None,
        generic_parent_handoff: GenericCycleSimulationContextHandoffV1 | None = None,
        leaf_context_owner: RecursiveLeafContextOwner | None = None,
        n4_generation_ports_by_node: Mapping[str, N4GenerationPort] | None = None,
        evaluation_contexts_by_node: Mapping[str, EvaluationExecutionContext] | None = None,
        execution_intents_by_node: Mapping[str, ExecutionIntent] | None = None,
    ) -> (
        RecursiveGenerationCycleRun
        | RecursiveGenerationCyclePartialRunV2
        | RecursiveGenerationCyclePartialRunV3
        | RecursiveGenerationCyclePartialRunV4
    ):
        """Run N6 leaves and preserve typed checkpoints for stops or sibling failures."""

        if physical_n5_budget_scope is not None:
            if type(physical_n5_budget_scope) is not VerifiedNLJobBudgetScope or not (
                physical_n5_budget_scope._was_issued_by_verified_nl_budget_owner
            ):
                raise RecursiveGenerationCycleError("n5_physical_budget_scope_not_established")
            intent_scope = (
                leaf_context_owner._verified_nl_job_scope
                if leaf_context_owner is not None
                else None
            )
            if intent_scope is not None and any(
                getattr(intent_scope, name) != getattr(physical_n5_budget_scope, name)
                for name in ("job_id", "run_id", "tenant_id", "cell_id", "worker_id", "attempt")
            ):
                raise RecursiveGenerationCycleError("n5_physical_budget_scope_job_mismatch")

        # The reusable parent controller must not retain another run's budget owner.
        invocation_joint_controller = self._joint_simulation_controller
        if type(_producer_budget_reconciler) is ProducerBudgetObserver:
            try:
                _producer_budget_reconciler.require_bound_state(budget_state)
            except ProducerBudgetSourceError as exc:
                raise RecursiveGenerationCycleError(
                    "recursive_n5_budget_state_binding_mismatch"
                ) from exc
            if type(invocation_joint_controller) is not JointSimulationHorizonController or (
                invocation_joint_controller._settings.authority_scope != "production"
            ):
                raise RecursiveGenerationCycleError("recursive_n5_budget_controller_not_canonical")
            invocation_joint_controller = JointSimulationHorizonController(
                method_registry=invocation_joint_controller._registry,
                policy=invocation_joint_controller.policy,
                producer_budget_observer=_producer_budget_reconciler,
                physical_n5_budget_scope=physical_n5_budget_scope,
            )

        if _producer_budget_reconciler is not None:
            if not callable(_producer_budget_reconciler):
                raise RecursiveGenerationCycleError("recursive_producer_budget_reconciler_invalid")
            if self._cycle_controller_factory is not None:
                raise RecursiveGenerationCycleError(
                    "recursive_producer_budget_custom_factory_unsupported"
                )

        if self._authority_scope == "production" and (
            self._promotion_runtime is None
            or self._epoch_subject_authority is None
            or self._epoch_validity_gate is None
            or self._epoch_n9_evidence_resolver is None
        ):
            raise RecursiveGenerationCycleError("recursive_epoch_owner_not_established")

        node_refs = tuple(recursive_graph.node_refs)
        if len(node_refs) != len(set(node_refs)):
            raise RecursiveGenerationCycleError("recursive_graph_duplicate_node")
        if recursive_graph.root_design_ref not in node_refs:
            raise RecursiveGenerationCycleError("recursive_graph_root_missing")
        if len(node_refs) > recursive_budget.max_nodes:
            raise RecursiveGenerationCycleError("recursive_node_budget_exhausted")
        if set(problems_by_node) != set(node_refs):
            raise RecursiveGenerationCycleError("recursive_problem_denominator_mismatch")
        generic_identity = bool(generic_simulation_handoffs_by_node) or (
            generic_parent_handoff is not None
        )
        if generic_identity:
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_design_problem_ref,
            )

            problem_refs_by_node = {
                node_ref: cycle_job_design_problem_ref(problems_by_node[node_ref])
                for node_ref in node_refs
            }
        else:
            problem_refs_by_node = {
                node_ref: _problem_ref(problems_by_node[node_ref]) for node_ref in node_refs
            }

        children: dict[str, list[str]] = {node_ref: [] for node_ref in node_refs}
        parent_by_node: dict[str, str] = {}
        for parent_ref, child_ref in recursive_graph.parent_child_edges:
            if parent_ref not in children or child_ref not in children:
                raise RecursiveGenerationCycleError("recursive_graph_edge_unresolved")
            if child_ref == recursive_graph.root_design_ref:
                raise RecursiveGenerationCycleError("recursive_graph_root_has_parent")
            if child_ref in parent_by_node:
                raise RecursiveGenerationCycleError("recursive_graph_multiple_parents")
            children[parent_ref].append(child_ref)
            parent_by_node[child_ref] = parent_ref
        if set(parent_by_node) != set(node_refs) - {recursive_graph.root_design_ref}:
            raise RecursiveGenerationCycleError("recursive_graph_unreachable_node")

        depths: dict[str, int] = {}
        active: set[str] = set()

        def visit(node_ref: str, depth: int) -> None:
            if node_ref in active:
                raise RecursiveGenerationCycleError("recursive_graph_cycle_detected")
            if node_ref in depths:
                return
            if depth > recursive_budget.max_depth:
                raise RecursiveGenerationCycleError("recursive_depth_budget_exhausted")
            active.add(node_ref)
            depths[node_ref] = depth
            for child_ref in children[node_ref]:
                visit(child_ref, depth + 1)
            active.remove(node_ref)

        visit(recursive_graph.root_design_ref, 0)
        if set(depths) != set(node_refs):
            raise RecursiveGenerationCycleError("recursive_graph_unreachable_node")
        leaf_refs = {node_ref for node_ref, child_refs in children.items() if not child_refs}
        if candidate_simulation_handoffs_by_node is not None:
            from polisyos.runtime.quality.candidate_simulation import (
                CandidateSimulationContextHandoff,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                cycle_job_design_problem_ref,
            )

            if not set(candidate_simulation_handoffs_by_node).issubset(leaf_refs):
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_simulation_handoff_not_leaf"
                )
            for node_ref, handoff in candidate_simulation_handoffs_by_node.items():
                if type(handoff) is not CandidateSimulationContextHandoff:
                    raise RecursiveGenerationCycleError(
                        "recursive_candidate_simulation_handoff_untyped"
                    )
                if (
                    handoff.context.design_problem_ref
                    != cycle_job_design_problem_ref(problems_by_node[node_ref])
                    or (cycle_substrate_contexts_by_node or {}).get(node_ref) != handoff.context
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_candidate_simulation_handoff_binding_mismatch"
                    )
        handoff_refs = set(candidate_simulation_handoffs_by_node or {})
        child_handoff_refs = handoff_refs - {recursive_graph.root_design_ref}
        if child_handoff_refs and type(leaf_context_owner) is not RecursiveLeafContextOwner:
            raise RecursiveGenerationCycleError("recursive_child_context_owner_not_established")
        # The root callback stays caller-owned. Each child callback is derived
        # below from its persisted capsule and canonical leaf owner; accepting
        # caller-provided child callbacks would let a sibling borrow another
        # child's currentness decision.
        expected_callback_refs = handoff_refs - child_handoff_refs
        if set(candidate_simulation_currentness_resolvers_by_node or {}) != expected_callback_refs:
            raise RecursiveGenerationCycleError(
                "recursive_candidate_simulation_currentness_denominator_mismatch"
            )
        leaf_capsule_refs: dict[str, CASArtifactRef] = {}
        currentness_resolvers = dict(candidate_simulation_currentness_resolvers_by_node or {})
        for node_ref in child_handoff_refs:
            if (execution_intents_by_node or {}).get(node_ref) != "simulate_only":
                raise RecursiveGenerationCycleError("recursive_child_capsule_intent_not_candidate")
            handoff = (candidate_simulation_handoffs_by_node or {})[node_ref]
            capsule_payload = {
                "schema_version": "policyos.runtime.recursive_leaf_context.v1",
                "authority_purpose": "candidate_leaf_replay_only",
                "node_ref": node_ref,
                "parent_ref": parent_by_node[node_ref],
                "problem": problems_by_node[node_ref].model_dump(mode="json"),
                "handoff": handoff.model_dump(mode="json"),
            }
            capsule = RecursiveLeafContextCapsule.model_validate(
                {**capsule_payload, "content_hash": gy_content_hash(capsule_payload)}
            )
            if leaf_context_owner is None:  # pragma: no cover - checked above
                raise RecursiveGenerationCycleError("recursive_child_context_owner_not_established")
            capsule_ref = leaf_context_owner.persist(capsule)
            leaf_capsule_refs[node_ref] = capsule_ref
            currentness_resolvers[node_ref] = leaf_context_owner.currentness_resolver(
                capsule_ref,
                capsule,
            )
        generic_handoffs = dict(generic_simulation_handoffs_by_node or {})
        generic_child_selections: dict[str, GenericCycleSimulationChildSelectionV1] = {}
        generic_currentness_resolvers: dict[str, Callable[[], bool]] = {}
        generic_leaf_capsule_refs: dict[str, CASArtifactRef] = {}
        root_generic_refs = set(generic_handoffs) & {recursive_graph.root_design_ref}
        if set(generic_simulation_currentness_resolvers_by_node or {}) != root_generic_refs:
            raise RecursiveGenerationCycleError(
                "recursive_generic_root_currentness_denominator_mismatch"
            )
        if root_generic_refs:
            root_ref = recursive_graph.root_design_ref
            if (
                leaf_refs != {root_ref}
                or set(generic_handoffs) != {root_ref}
                or handoff_refs
                or type(generic_handoffs[root_ref]) is not GenericCycleSimulationContextHandoffV1
                or generic_handoffs[root_ref].n4_child_profile_family_ref is not None
                or type(leaf_context_owner) is not RecursiveLeafContextOwner
                or generic_n4_child_profile_set_ref is not None
                or generic_n4_source_repository is not None
                or generic_parent_handoff is not None
                or (cycle_substrate_contexts_by_node or {}).get(root_ref)
                != generic_handoffs[root_ref].context
                or (execution_intents_by_node or {}).get(root_ref) != "simulate_only"
            ):
                raise RecursiveGenerationCycleError("recursive_generic_root_binding_mismatch")
            require_root_current = leaf_context_owner.generic_root_currentness_resolver(
                handoff=generic_handoffs[root_ref],
                problem=problems_by_node[root_ref],
                currentness=generic_simulation_currentness_resolvers_by_node[root_ref],
            )
            require_root_current()
            # The fixed selected handoff was verified above. The leaf controller
            # reopens its current handoff after reissue; retain the independent
            # upstream lease/config predicate rather than the old-ref closure.
            generic_currentness_resolvers[root_ref] = (
                generic_simulation_currentness_resolvers_by_node[root_ref]
            )
        elif generic_handoffs:
            if handoff_refs:
                raise RecursiveGenerationCycleError(
                    "recursive_candidate_and_generic_child_profiles_conflict"
                )
            if (
                type(leaf_context_owner) is not RecursiveLeafContextOwner
                or generic_n4_child_profile_set_ref is None
                or generic_n4_source_repository is None
                or generic_parent_handoff is None
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_generic_n4_child_profile_owner_incomplete"
                )
            expected_generic_leaf_refs = leaf_refs - {recursive_graph.root_design_ref}
            if set(generic_handoffs) != expected_generic_leaf_refs:
                raise RecursiveGenerationCycleError(
                    "recursive_generic_child_handoff_denominator_mismatch"
                )
            family = leaf_context_owner.require_current_n4_child_profile_set(
                generic_n4_child_profile_set_ref,
                expected_parent_handoff=generic_parent_handoff,
                source_repository=generic_n4_source_repository,
            )
            family_by_ref = {row.node_ref: row for row in family.children}
            if set(family_by_ref) != expected_generic_leaf_refs:
                raise RecursiveGenerationCycleError(
                    "recursive_generic_child_family_denominator_mismatch"
                )
            for node_ref in expected_generic_leaf_refs:
                handoff = generic_handoffs[node_ref]
                row = family_by_ref[node_ref]
                if (
                    type(handoff) is not GenericCycleSimulationContextHandoffV1
                    or row.handoff != handoff
                    or row.problem != problems_by_node[node_ref]
                    or row.parent_ref != parent_by_node.get(node_ref)
                    or row.selection.parent_handoff != generic_parent_handoff
                    or row.selection.n4_child_profile_family_ref
                    != generic_parent_handoff.n4_child_profile_family_ref
                    or (cycle_substrate_contexts_by_node or {}).get(node_ref) != handoff.context
                    or execution_intent_band_for_mode(
                        (execution_intents_by_node or {}).get(node_ref, "candidate_only")
                    )
                    not in {
                        ExecutionIntentBand.CANDIDATE_ONLY,
                        ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
                    }
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_generic_child_family_binding_mismatch"
                    )
                generic_child_selections[node_ref] = row.selection
                capsule_payload: dict[str, object] = {
                    "schema_version": "policyos.runtime.recursive_leaf_context.v2",
                    "authority_purpose": "cycle_input_candidate_only",
                    "node_ref": node_ref,
                    "parent_ref": parent_by_node[node_ref],
                    "problem": problems_by_node[node_ref].model_dump(mode="json"),
                    "child_selection": row.selection.model_dump(mode="json"),
                    "handoff": handoff.model_dump(mode="json"),
                    "n4_source_ref": family.source_ref.model_dump(mode="json"),
                    "n4_child_profile_family_ref": family.n4_child_profile_family_ref.model_dump(
                        mode="json"
                    ),
                    "n4_child_profile_set_ref": generic_n4_child_profile_set_ref.model_dump(
                        mode="json"
                    ),
                }
                capsule = RecursiveLeafContextCapsuleV2.model_validate(
                    {
                        **capsule_payload,
                        "content_hash": gy_content_hash(capsule_payload),
                    }
                )
                capsule_ref = leaf_context_owner.persist_generic_capsule(
                    capsule,
                    parent_handoff=generic_parent_handoff,
                    source_repository=generic_n4_source_repository,
                )
                generic_leaf_capsule_refs[node_ref] = capsule_ref
                generic_currentness_resolvers[node_ref] = (
                    leaf_context_owner.generic_currentness_resolver(
                        capsule_ref,
                        capsule,
                        parent_handoff=generic_parent_handoff,
                        source_repository=generic_n4_source_repository,
                    )
                )
        elif any(
            value is not None
            for value in (
                generic_n4_child_profile_set_ref,
                generic_n4_source_repository,
                generic_parent_handoff,
            )
        ):
            raise RecursiveGenerationCycleError("recursive_generic_child_family_without_handoffs")
        if (candidate_simulation_handoffs_by_node or generic_handoffs) and (
            self._cycle_controller_factory is not None
        ):
            raise RecursiveGenerationCycleError(
                "recursive_candidate_simulation_factory_bypass_forbidden"
            )
        if execution_intents_by_node is not None:
            if set(execution_intents_by_node) != leaf_refs:
                raise RecursiveGenerationCycleError(
                    "recursive_execution_intent_denominator_mismatch"
                )
            if any(
                execution_intent_band_for_mode(intent) is ExecutionIntentBand.NOT_ESTABLISHED
                for intent in execution_intents_by_node.values()
            ):
                raise RecursiveGenerationCycleError("recursive_execution_intent_not_canonical")
            if self._cycle_controller_factory is not None and any(
                execution_intent_band_for_mode(intent) is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                for intent in execution_intents_by_node.values()
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_custom_factory_context_not_consumed"
                )
        if evaluation_contexts_by_node is not None:
            supplied_context_refs = set(evaluation_contexts_by_node)
            required_eval_safety_refs = (
                leaf_refs
                if execution_intents_by_node is None
                else {
                    node_ref
                    for node_ref, intent in execution_intents_by_node.items()
                    if execution_intent_band_for_mode(intent)
                    is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                }
            )
            if (
                not supplied_context_refs.issubset(leaf_refs)
                or not required_eval_safety_refs.issubset(supplied_context_refs)
                or (execution_intents_by_node is None and supplied_context_refs != leaf_refs)
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_context_denominator_mismatch"
                )
            if self._cycle_controller_factory is not None and any(
                isinstance(context, EvaluationExecutionContext)
                and execution_intent_band_for_mode(context.evaluation_mode)
                is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                for context in evaluation_contexts_by_node.values()
            ):
                raise RecursiveGenerationCycleError(
                    "recursive_eval_safety_custom_factory_context_not_consumed"
                )
        if self._cycle_controller_factory is None:
            candidate_band_only = bool(execution_intents_by_node) and all(
                execution_intent_band_for_mode(intent)
                in {
                    ExecutionIntentBand.CANDIDATE_ONLY,
                    ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
                }
                for intent in execution_intents_by_node.values()
            )
            if (
                evaluation_contexts_by_node is None
                and cycle_substrate_contexts_by_node is None
                and not candidate_band_only
            ):
                missing_owner_code = (
                    "recursive_data_trust_owner_not_established"
                    if execution_intents_by_node is not None
                    and not any(
                        execution_intent_band_for_mode(intent)
                        is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                        for intent in execution_intents_by_node.values()
                    )
                    and any(
                        execution_intent_band_for_mode(intent)
                        is ExecutionIntentBand.DATA_TRUST_REQUIRED
                        for intent in execution_intents_by_node.values()
                    )
                    else "recursive_eval_safety_context_not_established"
                )
                raise RecursiveGenerationCycleError(missing_owner_code)
            if evaluation_contexts_by_node is not None and any(
                not isinstance(context, EvaluationExecutionContext)
                for context in evaluation_contexts_by_node.values()
            ):
                raise RecursiveGenerationCycleError("recursive_eval_safety_context_not_canonical")
            for node_ref, intent in (execution_intents_by_node or {}).items():
                context = (evaluation_contexts_by_node or {}).get(node_ref)
                intent_band = execution_intent_band_for_mode(intent)
                if intent_band in {
                    ExecutionIntentBand.CANDIDATE_ONLY,
                    ExecutionIntentBand.SIMULATE_ONLY_ATTEMPT,
                }:
                    if intent_band is ExecutionIntentBand.CANDIDATE_ONLY and context is not None:
                        raise RecursiveGenerationCycleError(
                            "recursive_candidate_intent_has_eval_safety_context"
                        )
                    if context is None:
                        continue
                if context is None:
                    if intent_band is ExecutionIntentBand.DATA_TRUST_REQUIRED:
                        raise RecursiveGenerationCycleError(
                            "recursive_data_trust_owner_not_established"
                        )
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_context_denominator_mismatch"
                    )
                if context.evaluation_mode != intent:
                    code = (
                        "recursive_eval_safety_execution_mode_mismatch"
                        if intent_band is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                        else "recursive_execution_intent_context_mode_mismatch"
                    )
                    raise RecursiveGenerationCycleError(code)
            protected_node_refs = (
                {
                    node_ref
                    for node_ref, intent in execution_intents_by_node.items()
                    if execution_intent_band_for_mode(intent)
                    is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                }
                if execution_intents_by_node is not None
                else {
                    node_ref
                    for node_ref, context in (evaluation_contexts_by_node or {}).items()
                    if execution_intent_band_for_mode(context.evaluation_mode)
                    is ExecutionIntentBand.EVAL_SAFETY_REQUIRED
                }
            )
            for node_ref in protected_node_refs:
                context = (evaluation_contexts_by_node or {}).get(node_ref)
                if context is None or context.design_problem_ref != _problem_ref(
                    problems_by_node[node_ref]
                ):
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_design_problem_mismatch"
                    )
                verifier = self._eval_safety_verifier
                if verifier is None:
                    raise RecursiveGenerationCycleError("recursive_eval_safety_context_not_current")
                challenge = EvalSafetyAdmissionChallenge.fresh(
                    consumer_component_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID
                )
                try:
                    admission = verifier.require_admission(context, challenge)
                except Exception as exc:
                    raise RecursiveGenerationCycleError(
                        "recursive_eval_safety_context_not_current",
                        type(exc).__name__,
                    ) from exc
                if (
                    not evaluation_safety_consumer_admission_is_verified(
                        admission,
                        context,
                        challenge,
                    )
                    or bool(admission.blocker_codes)
                    or context.eval_safety_certificate_ref is None
                    or context.eval_safety_revision_head_ref is None
                    or admission.certificate_ref != context.eval_safety_certificate_ref
                    or admission.current_revision_head_ref != context.eval_safety_revision_head_ref
                ):
                    raise RecursiveGenerationCycleError("recursive_eval_safety_context_not_current")

        def effective_intent_band(node_ref: str) -> ExecutionIntentBand:
            explicit_intent = (execution_intents_by_node or {}).get(node_ref)
            if explicit_intent is not None:
                return execution_intent_band_for_mode(explicit_intent)
            evaluation_context = (evaluation_contexts_by_node or {}).get(node_ref)
            if isinstance(evaluation_context, EvaluationExecutionContext):
                return execution_intent_band_for_mode(evaluation_context.evaluation_mode)
            if (
                self._authority_scope == "contract_testing"
                and type(self) is RecursiveGenerationCycleController
            ):
                return resolve_execution_intent_band(
                    attempt_present=False,
                    mode_resolution=resolve_evaluation_mode(None),
                )
            return ExecutionIntentBand.NOT_ESTABLISHED

        intent_bands_by_leaf = {node_ref: effective_intent_band(node_ref) for node_ref in leaf_refs}
        if self._authority_scope == "production" and any(
            band is ExecutionIntentBand.NOT_ESTABLISHED for band in intent_bands_by_leaf.values()
        ):
            raise RecursiveGenerationCycleError("recursive_execution_intent_not_established")

        if n4_generation_ports_by_node is not None:
            if self._cycle_controller_factory is not None:
                raise RecursiveGenerationCycleError(
                    "recursive_n4_port_and_controller_factory_conflict"
                )
            if set(n4_generation_ports_by_node) != leaf_refs:
                raise RecursiveGenerationCycleError("recursive_n4_port_denominator_mismatch")
            if any(
                not isinstance(port, N4GenerationPort)
                for port in n4_generation_ports_by_node.values()
            ):
                raise RecursiveGenerationCycleError("recursive_n4_port_not_canonical")

        node_results: dict[str, RecursiveCycleNode] = {}

        async def route(node_ref: str) -> RecursiveCycleNode:
            problem = problems_by_node[node_ref]
            problem_ref = problem_refs_by_node[node_ref]
            child_refs = tuple(children[node_ref])
            if not child_refs:
                context = (cycle_substrate_contexts_by_node or {}).get(node_ref)
                if context is not None:
                    from polisyos.runtime.quality.cycle_substrate import (
                        revalidate_cycle_substrate_context,
                    )

                    revalidate_cycle_substrate_context(context)
                    if context.design_problem_ref != problem_ref:
                        raise RecursiveGenerationCycleError(
                            "recursive_leaf_context_problem_mismatch"
                        )
                if self._cycle_controller_factory is None:
                    evaluation_context = (evaluation_contexts_by_node or {}).get(node_ref)
                    if (
                        evaluation_context is not None
                        and evaluation_context.design_problem_ref != problem_ref
                    ):
                        raise RecursiveGenerationCycleError(
                            "recursive_eval_safety_design_problem_mismatch"
                        )
                    value_port = (
                        FoundryValuePort(
                            evaluation_context=evaluation_context,
                            eval_safety_verifier=self._eval_safety_verifier,
                            repo_root=self._repo_root,
                            cycle_substrate_context=context,
                            artifact_store=self._artifact_store,
                        )
                        if evaluation_context is not None
                        else None
                    )
                    controller = GenerationCycleController(
                        generation_port=(n4_generation_ports_by_node or {}).get(node_ref),
                        value_port=value_port,
                        eval_safety_verifier=self._eval_safety_verifier,
                        repo_root=self._repo_root,
                        model_id=self._leaf_model_id,
                        catalog_run_profile=self._catalog_run_profile,
                        catalog_serving_source=self._catalog_serving_source,
                        capability_resolver=self._capability_resolver,
                        measurement_root_execution_binding=self._measurement_root_execution_binding,
                        cycle_substrate_context=context,
                        candidate_cycle_context_artifact_owner=(
                            leaf_context_owner._context_owner
                            if leaf_context_owner is not None
                            else None
                        ),
                        candidate_cycle_verified_nl_job_scope=(
                            leaf_context_owner._verified_nl_job_scope
                            if leaf_context_owner is not None
                            else None
                        ),
                        physical_n5_budget_scope=physical_n5_budget_scope,
                        candidate_simulation_context_admission_owner=(
                            leaf_context_owner._admission_owner
                            if leaf_context_owner is not None
                            else None
                        ),
                        candidate_simulation_handoff=(
                            candidate_simulation_handoffs_by_node or {}
                        ).get(node_ref),
                        candidate_simulation_currentness_resolver=(
                            currentness_resolvers.get(node_ref)
                        ),
                        generic_cycle_simulation_handoff=generic_handoffs.get(node_ref),
                        generic_cycle_simulation_child_selection=generic_child_selections.get(
                            node_ref
                        ),
                        generic_cycle_simulation_admission_owner=(
                            leaf_context_owner._generic_admission_owner
                            if leaf_context_owner is not None
                            else None
                        ),
                        generic_cycle_simulation_currentness_resolver=(
                            generic_currentness_resolvers.get(node_ref)
                        ),
                        generic_n4_child_profile_set_ref=generic_n4_child_profile_set_ref,
                        promotion_runtime=self._promotion_runtime,
                        artifact_store=self._artifact_store,
                        _producer_budget_reconciler=_producer_budget_reconciler,
                    )
                else:
                    controller = self._cycle_controller_factory(node_ref, problem)
                if not isinstance(controller, GenerationCycleController):
                    raise RecursiveGenerationCycleError("recursive_leaf_controller_not_canonical")
                if (
                    self._authority_scope == "contract_testing"
                    and execution_intents_by_node is None
                    and (evaluation_contexts_by_node or {}).get(node_ref) is None
                ):
                    from polisyos.runtime.quality.promotion_sequence import (
                        CanonicalN9PromotionPort,
                    )

                    candidate_cas_is_parent_owned = (
                        controller._authority_scope == "contract_testing"
                        and self._artifact_store is not None
                        and controller._artifact_store is self._artifact_store
                    )
                    candidate_scope_is_established = (
                        controller._authority_scope == "production" or candidate_cas_is_parent_owned
                    )
                    if (
                        type(self) is not RecursiveGenerationCycleController
                        or type(controller) is not GenerationCycleController
                        or not candidate_scope_is_established
                        or controller._promotion_runtime is not None
                        or type(controller._promotion_port) is not CanonicalN9PromotionPort
                        or "run" in vars(controller)
                        or "_promote_completed_generation" in vars(controller)
                        or "deployment_identity_refusal" in vars(controller._promotion_port)
                    ):
                        raise RecursiveGenerationCycleError(
                            "recursive_contract_testing_candidate_n9_owner_not_established"
                        )
                if context is not None and controller._cycle_substrate_context is not context:
                    raise RecursiveGenerationCycleError(
                        "recursive_contract_testing_context_not_consumed"
                    )
                try:
                    cycle_run = await controller.run(
                        problem,
                        budget_state=budget_state,
                        min_cycles=recursive_budget.min_cycles_per_leaf,
                        max_cycles=recursive_budget.max_cycles_per_leaf,
                        stable_design_problem_ref=problem_ref,
                    )
                except Exception as exc:
                    raise _RecursiveLeafExecutionError(node_ref, exc) from exc
                capsule_ref = leaf_capsule_refs.get(node_ref)
                if capsule_ref is not None:
                    if leaf_context_owner is None:  # pragma: no cover - preflight checks owner
                        raise RecursiveGenerationCycleError(
                            "recursive_child_context_owner_not_established"
                        )
                    handoff = (candidate_simulation_handoffs_by_node or {})[node_ref]
                    leaf_context_owner.read(
                        capsule_ref,
                        node_ref=node_ref,
                        parent_ref=parent_by_node[node_ref],
                        problem=problem,
                        expected_job_id=handoff.job_id,
                        expected_run_id=handoff.run_id,
                        expected_tenant_id=handoff.tenant_id,
                        expected_cell_id=handoff.cell_id,
                    )
                generic_capsule_ref = generic_leaf_capsule_refs.get(node_ref)
                if generic_capsule_ref is not None or node_ref in root_generic_refs:
                    require_generic_current = (
                        controller._generic_cycle_simulation_currentness_resolver
                        if node_ref in root_generic_refs
                        else generic_currentness_resolvers.get(node_ref)
                    )
                    if require_generic_current is None:
                        raise RecursiveGenerationCycleError(
                            "recursive_generic_currentness_callback_missing"
                        )
                    require_generic_current()
                if cycle_run.design_problem_ref != problem_ref:
                    raise RecursiveGenerationCycleError("recursive_leaf_problem_binding_mismatch")
                # N6 currentness governs authority, not whether a computed leaf
                # can continue as candidate input to recursion. Protected
                # authority consumers keep the strict validator at their owner.
                issues = validate_generation_cycle_candidate_run(cycle_run)
                if issues:
                    raise RecursiveGenerationCycleError(
                        "recursive_leaf_generation_cycle_invalid",
                        str(issues),
                    )
                result = RecursiveCycleNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    design_problem_ref=problem_ref,
                    cycle_run=cycle_run,
                    leaf_context_ref=(
                        leaf_capsule_refs.get(node_ref) or generic_leaf_capsule_refs.get(node_ref)
                    ),
                    terminal=_leaf_terminal(cycle_run),
                )
                node_results[node_ref] = result
                if (
                    result.terminal.kind is SearchTerminalKind.BUDGET_EXHAUSTED
                    and node_ref != recursive_graph.root_design_ref
                ):
                    # Preserve this canonical N6 run, then unwind before the
                    # router can visit a sibling or start ancestor composition.
                    raise _RecursiveBudgetStopError(node_ref)
                return result

            routed_children_list: list[RecursiveCycleNode] = []
            for child_index, child_ref in enumerate(child_refs):
                try:
                    routed_child = await route(child_ref)
                except _RecursiveBudgetStopError as stop:
                    frontier_node_refs = (
                        *stop.frontier_node_refs,
                        *child_refs[child_index + 1 :],
                    )
                    raise _RecursiveBudgetStopError(
                        stop.budget_stop_node_ref,
                        frontier_node_refs,
                    ) from None
                except _RecursiveStandardQuotaStopError as stop:
                    frontier_node_refs = (
                        *stop.frontier_node_refs,
                        *child_refs[child_index + 1 :],
                    )
                    raise _RecursiveStandardQuotaStopError(
                        stop_parent_node_ref=stop.stop_parent_node_ref,
                        pending_child_node_ref=stop.pending_child_node_ref,
                        pending_child_index=stop.pending_child_index,
                        frontier_node_refs=frontier_node_refs,
                        exhaustion_witness=stop.exhaustion_witness,
                    ) from None
                except _RecursiveSiblingFailureError:
                    raise
                except _RecursiveLeafExecutionError as failure:
                    if not routed_children_list:
                        raise
                    raise _RecursiveSiblingFailureError(
                        child_ref,
                        failure.failure,
                    ) from failure
                except Exception as exc:
                    if child_ref not in leaf_refs:
                        raise
                    failure = _RecursiveLeafExecutionError(child_ref, exc)
                    if not routed_children_list:
                        raise failure from exc
                    raise _RecursiveSiblingFailureError(
                        child_ref,
                        failure.failure,
                    ) from failure
                routed_children_list.append(routed_child)
                if child_index + 1 < len(child_refs):
                    observer = invocation_joint_controller._producer_budget_observer
                    witness = _observed_standard_exhaustion_witness(observer)
                    if (
                        witness is not None
                        and self._artifact_store is not None
                        and _recursive_capacity_prefix_work(
                            completed_nodes=node_results,
                            witness=witness,
                            store=self._artifact_store,
                        )
                    ):
                        raise _RecursiveStandardQuotaStopError(
                            stop_parent_node_ref=node_ref,
                            pending_child_node_ref=child_refs[child_index + 1],
                            pending_child_index=child_index + 1,
                            frontier_node_refs=child_refs[child_index + 1 :],
                            exhaustion_witness=witness,
                        )
            routed_children = tuple(routed_children_list)
            if len(routed_children) != 1:
                request = (joint_simulation_requests_by_node or {}).get(node_ref)
                candidate_selection = (joint_candidate_selections_by_node or {}).get(node_ref)
                subdesigns = (subdesign_contracts_by_node or {}).get(node_ref)
                if request is None:
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal("observed_coupling_evidence_missing"),
                    )
                    node_results[node_ref] = result
                    return result
                if candidate_selection is not None:
                    selection_issue = None
                    if isinstance(candidate_selection, ParentJointCandidateSelectionV3):
                        if (
                            self._artifact_store is None
                            or generic_n4_source_repository is None
                            or generic_parent_handoff is None
                            or leaf_context_owner is None
                            or leaf_context_owner._generic_admission_owner is None
                        ):
                            selection_issue = (
                                "recursive_authored_joint_relation_owner_not_established"
                            )
                        else:
                            try:
                                load_authored_joint_components(
                                    store=self._artifact_store,
                                    relation_ref=candidate_selection.relation_ref,
                                    source_repository=generic_n4_source_repository,
                                    parent_handoff=generic_parent_handoff,
                                    admission_owner=leaf_context_owner._generic_admission_owner,
                                    request=request,
                                    selection=candidate_selection,
                                )
                            except (OSError, RuntimeError, TypeError, ValueError):
                                selection_issue = (
                                    "recursive_authored_joint_relation_replay_not_established"
                                )
                    elif isinstance(candidate_selection, ParentJointCandidateSelectionV4):
                        if (
                            generic_parent_handoff is None
                            or leaf_context_owner is None
                            or leaf_context_owner._generic_admission_owner is None
                            or candidate_selection.parent_design_problem_ref != problem_ref
                            or candidate_selection.child_node_refs != child_refs
                            or request.coupling_graph is not None
                        ):
                            selection_issue = (
                                "recursive_parent_joint_materialization_owner_not_established"
                            )
                        else:
                            try:
                                replay_parent_joint_candidate_materializations(
                                    selection=candidate_selection,
                                    request=request,
                                    parent_handoff=generic_parent_handoff,
                                    admission_owner=leaf_context_owner._generic_admission_owner,
                                )
                            except (OSError, RuntimeError, TypeError, ValueError):
                                selection_issue = (
                                    "recursive_parent_joint_materialization_replay_not_established"
                                )
                    elif (
                        request.coupling_graph is not None
                        or candidate_selection.parent_design_problem_ref != problem_ref
                        or candidate_selection.child_node_refs != child_refs
                        or candidate_selection.world_model_record_ref
                        != request.world_model_record_ref
                        or candidate_selection.world_model_record_content_hash
                        != request.world_model_record.content_hash
                        or candidate_selection.outcome_variable not in request.selected_outcomes
                        or tuple(member.source_atom_id for member in candidate_selection.members)
                        != tuple(atom.atom_id for atom in request.intervention_atoms)
                        or tuple(
                            member.source_atom_content_hash
                            for member in candidate_selection.members
                        )
                        != tuple(atom.content_hash for atom in request.intervention_atoms)
                        or any(
                            atom.problem_frame_ref != problem_ref
                            for atom in request.intervention_atoms
                        )
                    ):
                        selection_issue = (
                            "recursive_parent_joint_candidate_request_binding_not_established"
                        )
                    currentness_resolver = (
                        joint_candidate_currentness_resolvers_by_node or {}
                    ).get(node_ref)
                    if selection_issue is None and (
                        currentness_resolver is None or currentness_resolver() is not True
                    ):
                        selection_issue = "generic_cycle_simulation_currentness_not_established"
                    if selection_issue is not None:
                        result = RecursiveCycleNode(
                            node_ref=node_ref,
                            parent_ref=parent_by_node.get(node_ref),
                            depth=depths[node_ref],
                            child_refs=child_refs,
                            design_problem_ref=problem_ref,
                            terminal=_blocked_parent_terminal(selection_issue),
                        )
                        node_results[node_ref] = result
                        return result
                elif request.coupling_graph is None:
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal("observed_coupling_evidence_missing"),
                    )
                    node_results[node_ref] = result
                    return result
                if candidate_selection is None and (
                    subdesigns is None or len(subdesigns) != len(child_refs)
                ):
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal("subdesign_contract_denominator_missing"),
                    )
                    node_results[node_ref] = result
                    return result
                binding_issue = (
                    None
                    if candidate_selection is not None
                    else _branch_binding_issue(
                        node_ref=node_ref,
                        problem_ref=problem_ref,
                        problem=problem,
                        child_refs=child_refs,
                        routed_children=routed_children,
                        request=request,
                        subdesigns=subdesigns,
                    )
                )
                if binding_issue is not None:
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal(binding_issue),
                    )
                    node_results[node_ref] = result
                    return result
                if self._artifact_store is None:
                    raise RecursiveGenerationCycleError(
                        "recursive_n5_runtime_store_not_established",
                        "The parent N5 run cannot start without its runtime-owned result store.",
                    )
                selected_parent_n5_profile = None
                try:
                    if (
                        candidate_selection is not None
                        and generic_parent_handoff is not None
                        and leaf_context_owner is not None
                        and leaf_context_owner._generic_admission_owner is not None
                    ):
                        # Reopen the owner-selected profile; a request or candidate
                        # label cannot select a physical-work allocation.
                        owner = leaf_context_owner._generic_admission_owner
                        selected_profile = owner.resolve_profile(
                            generic_parent_handoff.profile_ref,
                            expected_profile=generic_parent_handoff.profile,
                            job_id=generic_parent_handoff.job_id,
                            run_id=generic_parent_handoff.run_id,
                            tenant_id=generic_parent_handoff.tenant_id,
                            cell_id=generic_parent_handoff.cell_id,
                        )
                        selected_parent_n5_profile = selected_profile.n5
                    invocation_scope = _bind_scoped_n5_invocation_policy(
                        invocation_joint_controller._producer_budget_observer,
                        n5_profile=selected_parent_n5_profile,
                        physical_n5_budget_scope=physical_n5_budget_scope,
                    )
                except (OSError, RuntimeError, TypeError, ValueError) as exc:
                    from polisyos.core.artifacts import raise_artifact_read_access_error

                    raise_artifact_read_access_error(exc)
                    code = _recursive_n5_parent_refusal(exc)
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal(code),
                    )
                    node_results[node_ref] = result
                    return result
                try:
                    with invocation_scope:
                        joint_simulation = invocation_joint_controller.run(request)
                except ProducerBudgetSourceError as exc:
                    from polisyos.core.artifacts import raise_artifact_read_access_error

                    raise_artifact_read_access_error(exc)
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        terminal=_blocked_parent_terminal(_recursive_n5_parent_refusal(exc)),
                    )
                    node_results[node_ref] = result
                    return result
                if not _joint_simulation_is_unsupported(joint_simulation):
                    try:
                        invocation_joint_controller.validate_selected_result(
                            request=request, result=joint_simulation
                        )
                    except (JointSimulationControllerError, TypeError, ValueError) as exc:
                        raise RecursiveGenerationCycleError(
                            "recursive_n5_execution_binding_not_established", str(exc)
                        ) from exc
                try:
                    from polisyos.core.artifacts import ArtifactTenantContextInfo

                    joint_simulation_ref = persist_joint_simulation_result(
                        joint_simulation,
                        store=self._artifact_store,
                        tenant_context=(
                            ArtifactTenantContextInfo(
                                tenant_id=generic_parent_handoff.tenant_id,
                                cell_id=generic_parent_handoff.cell_id,
                            )
                            if generic_parent_handoff is not None
                            else None
                        ),
                    )
                except GenerationCycleError as exc:
                    raise RecursiveGenerationCycleError(
                        "recursive_n5_result_persistence_failed",
                        str(exc),
                    ) from exc
                if _joint_simulation_is_unsupported(joint_simulation):
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        joint_simulation=joint_simulation,
                        joint_simulation_ref=joint_simulation_ref,
                        joint_simulation_request=request,
                        joint_simulation_request_content_hash=gy_content_hash(
                            request.model_dump(mode="json")
                        ),
                        joint_candidate_selection=candidate_selection,
                        joint_candidate_selection_content_hash=(
                            candidate_selection.content_hash
                            if candidate_selection is not None
                            else None
                        ),
                        terminal=_blocked_parent_terminal("unsupported_coupling_gated"),
                    )
                    node_results[node_ref] = result
                    return result
                if candidate_selection is not None:
                    result = RecursiveCycleNode(
                        node_ref=node_ref,
                        parent_ref=parent_by_node.get(node_ref),
                        depth=depths[node_ref],
                        child_refs=child_refs,
                        design_problem_ref=problem_ref,
                        joint_simulation=joint_simulation,
                        joint_simulation_ref=joint_simulation_ref,
                        joint_simulation_request=request,
                        joint_simulation_request_content_hash=gy_content_hash(
                            request.model_dump(mode="json")
                        ),
                        joint_candidate_selection=candidate_selection,
                        joint_candidate_selection_content_hash=candidate_selection.content_hash,
                        terminal=_blocked_parent_terminal("observed_coupling_evidence_missing"),
                    )
                    node_results[node_ref] = result
                    return result
                certificate = compose_subdesigns(
                    subdesigns=subdesigns,
                    claims=_composition_claims_for_problem(
                        problem,
                        target_policy_program_ref=node_ref,
                    ),
                    graph=request.coupling_graph,
                    parent_workspace_id=node_ref,
                    rule_version_ref=recursive_graph.rule_version_ref,
                )
                result = RecursiveCycleNode(
                    node_ref=node_ref,
                    parent_ref=parent_by_node.get(node_ref),
                    depth=depths[node_ref],
                    child_refs=child_refs,
                    design_problem_ref=problem_ref,
                    joint_simulation=joint_simulation,
                    joint_simulation_ref=joint_simulation_ref,
                    joint_simulation_request=request,
                    joint_simulation_request_content_hash=gy_content_hash(
                        request.model_dump(mode="json")
                    ),
                    composition_certificate=certificate,
                    terminal=_fold_composed_terminal(
                        children=routed_children,
                        joint_simulation=joint_simulation,
                        certificate=certificate,
                    ),
                )
                node_results[node_ref] = result
                return result
            result = RecursiveCycleNode(
                node_ref=node_ref,
                parent_ref=parent_by_node.get(node_ref),
                depth=depths[node_ref],
                child_refs=child_refs,
                design_problem_ref=problem_ref,
                terminal=_fold_unary_terminal(routed_children[0]),
            )
            node_results[node_ref] = result
            return result

        original_leaf_error: Exception | None = None
        try:
            root = await route(recursive_graph.root_design_ref)
        except _RecursiveStandardQuotaStopError as stop:
            return _build_capacity_stopped_recursive_run_v4(
                recursive_graph=recursive_graph,
                problems_by_node=problems_by_node,
                problem_refs_by_node=problem_refs_by_node,
                completed_nodes_by_ref=node_results,
                children_by_node=children,
                parent_by_node=parent_by_node,
                depths=depths,
                recursive_budget=recursive_budget,
                stop_parent_node_ref=stop.stop_parent_node_ref,
                pending_child_node_ref=stop.pending_child_node_ref,
                pending_child_index=stop.pending_child_index,
                frontier_node_refs=stop.frontier_node_refs,
                exhaustion_witness=stop.exhaustion_witness,
                authority_scope=self._authority_scope,
            )
        except _RecursiveBudgetStopError as stop:
            return _build_budget_stopped_recursive_run_v2(
                recursive_graph=recursive_graph,
                problems_by_node=problems_by_node,
                problem_refs_by_node=problem_refs_by_node,
                completed_nodes_by_ref=node_results,
                children_by_node=children,
                parent_by_node=parent_by_node,
                depths=depths,
                recursive_budget=recursive_budget,
                budget_stop_node_ref=stop.budget_stop_node_ref,
                frontier_node_refs=stop.frontier_node_refs,
                authority_scope=self._authority_scope,
            )
        except _RecursiveSiblingFailureError as failure:
            return _build_sibling_failed_recursive_run_v3(
                recursive_graph=recursive_graph,
                problems_by_node=problems_by_node,
                problem_refs_by_node=problem_refs_by_node,
                completed_nodes_by_ref=node_results,
                children_by_node=children,
                parent_by_node=parent_by_node,
                depths=depths,
                recursive_budget=recursive_budget,
                failed_node_ref=failure.failed_node_ref,
                failure=failure.failure,
                authority_scope=self._authority_scope,
            )
        except _RecursiveLeafExecutionError as failure:
            original_leaf_error = failure.error
        if original_leaf_error is not None:
            raise original_leaf_error
        ordered_nodes = tuple(node_results[node_ref] for node_ref in node_refs)
        node_payloads = tuple(node.model_dump(mode="json") for node in ordered_nodes)
        payload = {
            "schema_version": RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION,
            "run_id": f"recursive:{recursive_graph.graph_id}",
            "controller_ref": RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF,
            "authority_scope": self._authority_scope,
            "recursive_graph": recursive_graph.model_dump(mode="json"),
            "recursive_graph_ref": recursive_graph.graph_ref,
            "recursive_graph_content_hash": gy_content_hash(
                recursive_graph.model_dump(mode="json")
            ),
            "root_node_ref": recursive_graph.root_design_ref,
            "root_design_problem_ref": problem_refs_by_node[recursive_graph.root_design_ref],
            "recursive_budget": recursive_budget.model_dump(mode="json"),
            "observed_max_depth": max(depths.values()),
            "nodes": node_payloads,
            "terminal": root.terminal.model_dump(mode="json"),
        }
        return RecursiveGenerationCycleRun.model_validate(
            {
                **payload,
                # Keep the already-validated leaf objects on the live route.
                # Their SimulationPortObservation carries the exact owner WMR
                # as an internal provenance handle excluded from JSON output.
                "nodes": ordered_nodes,
                "content_hash": gy_content_hash(payload),
            }
        )


__all__ = [
    "RECURSIVE_GENERATION_CYCLE_CONTROLLER_REF",
    "RECURSIVE_GENERATION_CYCLE_PARTIAL_V2_SCHEMA_VERSION",
    "RECURSIVE_GENERATION_CYCLE_PARTIAL_V3_SCHEMA_VERSION",
    "RECURSIVE_GENERATION_CYCLE_PARTIAL_V4_SCHEMA_VERSION",
    "RECURSIVE_GENERATION_CYCLE_SCHEMA_VERSION",
    "DepthNStrangleReceipt",
    "RecursiveCycleBudget",
    "RecursiveCycleFailedNode",
    "RecursiveCycleFailure",
    "RecursiveCycleNode",
    "RecursiveCyclePendingNode",
    "RecursiveGenerationCycleController",
    "RecursiveGenerationCycleError",
    "RecursiveGenerationCyclePartialRunV2",
    "RecursiveGenerationCyclePartialRunV3",
    "RecursiveGenerationCyclePartialRunV4",
    "RecursiveGenerationCycleRun",
    "RecursiveLeafContextCapsule",
    "RecursiveLeafContextOwner",
    "build_default_recursive_generation_cycle_controller",
    "recompute_depth_n_strangle_receipt",
    "verify_recursive_standard_n5_capacity_partial_run",
    "verify_recursive_standard_n5_capacity_partial_run_historical",
]
