"""Public engine context module API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from polisyos.core.security import AuditLog
    from polisyos.data_forge.read_api.academic import PreparedSKGRead
    from polisyos.pdc import EvalSafetyVerifierPort, EvaluationExecutionContext
    from polisyos.scientist.evidence.claims.head_index import ClaimLedgerOwnerPort
    from polisyos.scientist.orchestration.engine.metrics_protocol import EngineMetricsCollector
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
    prepared_skg_read: PreparedSKGRead | None = field(
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
    from polisyos.core.canon import from_canonical_bytes
    from polisyos.scientist.orchestration.engine.state import ExperimentState as _ExperimentState
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
    return basis_state


@dataclass(frozen=True, kw_only=True)
class ClaimCapableExecutionContext(ExecutionContext):
    """Execution context whose Claim persistence authority is explicit and non-optional."""

    claim_ledger_owner: ClaimLedgerOwnerPort
