"""Public engine context module API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.core.security import AuditLog
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
    from polisyos.pdc import EvalSafetyVerifierPort, EvaluationExecutionContext
    from polisyos.scientist.evidence.claims.head_index import ClaimLedgerOwnerPort
    from polisyos.scientist.orchestration.engine.child_computation import _ManagedStageBSession
    from polisyos.scientist.orchestration.engine.input_ports import (
        NodeInputSelection,
        _VerifiedPolicyCompletionAdmissionOwner,
        _VerifiedPolicyPhase5AdmissionOwner,
    )
    from polisyos.scientist.orchestration.engine.metrics_protocol import (
        EngineMetricsCollector,
    )
    from polisyos.scientist.orchestration.engine.state import ExperimentState
    from polisyos.scientist.validation.epoch_certificate_issuance import (
        EpochCertificateIssuanceOwner,
    )

from polisyos.core.artifacts import ArtifactRef
from polisyos.core.artifacts.protocol import ArtifactStore
from polisyos.core.contracts.fabric import DataSnapshotRef, DataViewRequestRef
from polisyos.core.contracts.foundry import (
    CompileRequest,
    CompileResult,
    ExecuteRequest,
    ExecuteResult,
)
from polisyos.core.contracts.lex import ChangeProposalRef, LegalContext, LegalReportRef
from polisyos.core.contracts.runtime import (
    CompletedMethodHTESource,
    MethodExecutionSelection,
)
from polisyos.core.contracts.scholar import KnowledgeBundleRef, ResearchIntent
from polisyos.core.run.context import RunContext


@runtime_checkable
class FoundryPort(Protocol):
    """Foundry port public type."""

    def compile(
        self, store: ArtifactStore, request: CompileRequest
    ) -> CompileResult:  # pragma: no cover - protocol
        ...

    def execute(
        self, store: ArtifactStore, request: ExecuteRequest
    ) -> ExecuteResult:  # pragma: no cover - protocol
        ...


@runtime_checkable
class FabricPort(Protocol):
    """Fabric port public type."""

    def snapshot(
        self, store: ArtifactStore, request_ref: DataViewRequestRef
    ) -> DataSnapshotRef:  # pragma: no cover - protocol
        ...


@runtime_checkable
class ScholarPort(Protocol):
    """Scholar port public type."""

    def enrich(
        self, store: ArtifactStore, intent: ResearchIntent
    ) -> KnowledgeBundleRef:  # pragma: no cover - protocol
        ...


@runtime_checkable
class LexPort(Protocol):
    """Lex port public type."""

    def evaluate(
        self, store: ArtifactStore, context: LegalContext
    ) -> tuple[LegalReportRef, ChangeProposalRef | None]:  # pragma: no cover - protocol
        ...


@runtime_checkable
class MethodMetricProjectionAssociation(Protocol):
    """Runtime-owned projection association selected for an authorized run."""

    @property
    def vector_ref(self) -> ArtifactRef: ...

    @property
    def verifier_revision(self) -> str: ...

    @property
    def verifier_implementation_sha256(self) -> str: ...


@runtime_checkable
class OwnedMethodExecutionSelection(Protocol):
    """Current method selection read from the owning Runtime control record."""

    @property
    def selection_kind(self) -> Literal["graph_method", "direct_method"]: ...

    @property
    def job_id(self) -> str: ...

    @property
    def run_id(self) -> str: ...

    @property
    def attempt(self) -> int: ...

    @property
    def method_result_ref(self) -> ArtifactRef | None: ...

    @property
    def simulation_result_ref(self) -> ArtifactRef | None: ...

    @property
    def method_execution_bundle_ref(self) -> ArtifactRef | None: ...

    @property
    def method_metric_binding_set_ref(self) -> ArtifactRef | None: ...

    @property
    def source_candidate_ref(self) -> ArtifactRef | None: ...

    @property
    def metric_verification_status(
        self,
    ) -> Literal["verified", "verification_missing"]: ...

    @property
    def method_metric_projection(self) -> MethodMetricProjectionAssociation | None: ...


@runtime_checkable
class MethodExecutionSelectionOwner(Protocol):
    """Resolve the authenticated current selection from Runtime ownership."""

    def get_method_execution_selection(
        self,
        *,
        run_id: str,
        tenant_id: str,
        cell_id: str,
    ) -> MethodExecutionSelection | None: ...


@runtime_checkable
class CompletedOwnedMethodExecutionSelection(OwnedMethodExecutionSelection, Protocol):
    """Completed graph selection with Runtime-owned candidate and terminal-state joins."""

    @property
    def source_candidate_ref(self) -> ArtifactRef | None: ...

    @property
    def source_experiment_state_ref(self) -> ArtifactRef: ...


@runtime_checkable
class CompletedMethodMetricSource(Protocol):
    """Exact completed graph source resolved by the current Runtime owner."""

    @property
    def source_run_id(self) -> str:
        """Return the exact completed source run."""
        ...

    @property
    def source_candidate_ref(self) -> ArtifactRef:
        """Return the owner-selected source candidate."""
        ...

    @property
    def source_experiment_state_ref(self) -> ArtifactRef:
        """Return the terminal Core source-state ref."""
        ...

    @property
    def selection(self) -> CompletedOwnedMethodExecutionSelection:
        """Return the completed graph method selection."""
        ...


@runtime_checkable
class CompletedMethodMetricSelectionOwner(Protocol):
    """Resolve completed current graph evidence for a later policy evaluation."""

    def resolve_completed_method_metric_selection(
        self,
        *,
        source_run_id: str,
        candidate_ref: ArtifactRef,
        tenant_id: str,
        cell_id: str | None,
    ) -> CompletedMethodMetricSource | None: ...


MethodMetricSelectionOwnerPort = CompletedMethodMetricSelectionOwner


@runtime_checkable
class CompletedMethodHTESelectionOwner(Protocol):
    """Resolve completed owner-selected HTE evidence for a later decision packet."""

    def resolve_completed_method_hte_selection(
        self,
        *,
        source_run_id: str,
        tenant_id: str,
        cell_id: str | None,
    ) -> CompletedMethodHTESource | None: ...


CompletedMethodHTESelectionOwnerPort = CompletedMethodHTESelectionOwner


@runtime_checkable
class Tracer(Protocol):
    """Tracer public type."""

    def start_as_current_span(
        self, name: str, attributes: dict[str, Any] | None = None
    ) -> Any:  # pragma: no cover - protocol
        ...


@dataclass(frozen=True)
class _EngineInvocationBinding:
    """Lookup handle to one selected-profile invocation basis owned by the engine."""

    run_id: str
    attempt_id: str
    basis_ref: ArtifactRef
    require_successful_completion: bool = False
    effective_timeout_s: float | None = None
    supervisor_deadline_monotonic: float | None = None


@dataclass(frozen=True)
class ExecutionContext:
    """Execution context public type."""

    store: ArtifactStore
    run: RunContext
    logger: logging.Logger
    tracer: Tracer | None = None

    metrics: EngineMetricsCollector | None = None
    audit: AuditLog | None = None

    depth: int = 0

    fabric: FabricPort | None = None
    foundry: FoundryPort | None = None
    scholar: ScholarPort | None = None
    lex: LexPort | None = None

    memory: Any | None = None  # PersistentMemoryStore (lazy import to avoid cycles)

    eval_safety_execution_context: EvaluationExecutionContext | None = field(
        default=None,
        kw_only=True,
    )
    eval_safety_verifier: EvalSafetyVerifierPort | None = field(
        default=None,
        kw_only=True,
    )
    epoch_certificate_issuance_owner: EpochCertificateIssuanceOwner | None = field(
        default=None,
        kw_only=True,
    )
    method_metric_selection_owner: MethodMetricSelectionOwnerPort | None = field(
        default=None,
        kw_only=True,
        repr=False,
    )
    completed_method_hte_selection_owner: CompletedMethodHTESelectionOwnerPort | None = field(
        default=None,
        kw_only=True,
        repr=False,
    )
    prepared_skg_read: PreparedSKGRead | None = field(
        default=None,
        kw_only=True,
        repr=False,
    )
    _node_input_selection: NodeInputSelection | None = field(default=None, kw_only=True, repr=False)
    _verified_policy_phase5_admission_owner: _VerifiedPolicyPhase5AdmissionOwner | None = field(
        default=None, kw_only=True, repr=False
    )
    _verified_policy_completion_admission_owner: _VerifiedPolicyCompletionAdmissionOwner | None = (
        field(default=None, kw_only=True, repr=False)
    )
    _child_stage_b_session: _ManagedStageBSession | None = field(
        default=None,
        kw_only=True,
        repr=False,
    )
    _engine_invocation: _EngineInvocationBinding | None = field(
        default=None,
        kw_only=True,
        repr=False,
    )


def _load_engine_owned_invocation_input_state(
    ctx: ExecutionContext,
    state: ExperimentState,
) -> ExperimentState | None:
    """Fresh-read the selected-profile workflow input for this engine attempt.

    A missing binding keeps historical behavior and establishes no source origin.
    A present binding must match the run-owner invocation record, its workflow node,
    and the selected-profile input-state artifact read back from CAS.
    """
    if getattr(ctx, "_node_input_selection", None) is not None:
        from polisyos.scientist.orchestration.engine.input_ports import _read_scoped_node_input

        return _read_scoped_node_input(ctx, state)
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.state import (
        ExperimentState as _ExperimentState,
    )
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    binding = ctx._engine_invocation
    if binding is None:
        return None
    if not isinstance(binding, _EngineInvocationBinding):
        raise ValueError("runtime_candidate_invocation_binding_invalid")
    run = ctx.run
    if (
        binding.run_id != run.run_manifest.run_id
        or binding.basis_ref.manifest_profile_sha256 is None
    ):
        raise ValueError("runtime_candidate_invocation_owner_mismatch")
    if state.run_id != run.run_manifest.run_id:
        raise ValueError("runtime_candidate_invocation_run_mismatch")
    attempts = run.read_runtime_invocation_attempts()
    matches = [
        attempt
        for attempt in attempts
        if attempt.basis.attempt_id == binding.attempt_id and attempt.basis_ref == binding.basis_ref
    ]
    if len(matches) != 1:
        raise ValueError("runtime_candidate_invocation_basis_not_owner_linked")
    attempt = matches[0]
    basis = attempt.basis
    if basis.run_id != run.run_manifest.run_id:
        raise ValueError("runtime_candidate_invocation_run_mismatch")
    if binding.require_successful_completion and (
        attempt.outcome is None or attempt.outcome.status != "ok"
    ):
        raise ValueError("runtime_candidate_invocation_not_successful")

    workflow_manifest = ctx.store.get_manifest(basis.workflow_spec_ref)
    if (
        workflow_manifest.kind != "scientist.workflow_spec"
        or workflow_manifest.artifact_schema is None
        or workflow_manifest.artifact_schema.name
        != "polisyos.scientist.orchestration.engine.WorkflowSpec"
    ):
        raise ValueError("runtime_candidate_workflow_spec_contract_invalid")
    workflow_spec = WorkflowSpec.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(basis.workflow_spec_ref))
    )
    workflow_nodes = [node for node in workflow_spec.nodes if node.alias == basis.node_alias]
    if len(workflow_nodes) != 1 or str(workflow_nodes[0].node_id) != basis.component_id:
        raise ValueError("runtime_candidate_workflow_node_binding_mismatch")

    state_manifest = ctx.store.get_manifest(basis.input_state_ref)
    if (
        state_manifest.kind != "scientist.experiment_state"
        or state_manifest.artifact_schema is None
        or state_manifest.artifact_schema.name
        != "polisyos.scientist.orchestration.engine.ExperimentState"
    ):
        raise ValueError("runtime_candidate_input_state_contract_invalid")
    basis_state = _ExperimentState.model_validate(
        from_canonical_bytes(ctx.store.get_bytes(basis.input_state_ref))
    )
    if (
        basis_state.run_id != run.run_manifest.run_id
        or state_manifest.artifact_schema.version != basis_state.schema_version
    ):
        raise ValueError("runtime_candidate_input_state_basis_mismatch")
    from polisyos.scientist.orchestration.engine.input_ports import validate_node_input_basis

    validate_node_input_basis(ctx.store, basis, basis_state)
    return basis_state


@dataclass(frozen=True, kw_only=True)
class ClaimCapableExecutionContext(ExecutionContext):
    """Execution context whose Claim persistence authority is explicit and non-optional."""

    claim_ledger_owner: ClaimLedgerOwnerPort
