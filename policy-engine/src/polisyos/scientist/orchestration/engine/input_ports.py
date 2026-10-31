"""Engine-owned physical node inputs and their persisted attempt basis.

The full predecessor is retained only by the executor. This is a state contract
boundary, not a Python, filesystem, or arbitrary artifact-store sandbox.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, replace
from threading import RLock
from typing import TYPE_CHECKING, Any, Literal, TypeGuard

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import (
    ArtifactRef,
    ArtifactWriteOptions,
    CoreJSONArtifactBoundedManifestReader,
    CoreJSONArtifactBoundedManifestReceiptReader,
    CoreJSONArtifactBoundedMemberReader,
    CoreJSONArtifactStreamingReader,
    InputRef,
    RawManifestBytesReader,
    SchemaInfo,
    artifact_ref_identity_key,
    input_ref_from_artifact_ref,
    load_core_json_artifact,
    matches_runtime_protocol_definition,
)
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.run.manifest import RunInvocationImplementationIdentity
from polisyos.scientist.governance.report import GovernanceReport
from polisyos.scientist.orchestration.engine.producer_currentness import (
    ProducerArtifactAdmission,
    ProducerArtifactCurrentness,
)
from polisyos.scientist.orchestration.engine.protocol import (
    InputAwareNodeSpec,
    NodeInputContract,
    NodeOutcome,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.state_branching import (
    _completed_producer_value,
    mutation_journal_for_state,
)
from polisyos.scientist.orchestration.engine.state_merge import merge_parallel_outcomes

if TYPE_CHECKING:
    from contextlib import AbstractContextManager

    from polisyos.core.artifacts import (
        ArtifactBoundedManifestRead,
        ArtifactID,
        ArtifactManifest,
        ArtifactStore,
        CoreJSONArtifactBoundedMemberAttempt,
        CoreJSONArtifactMemberStream,
        VerificationReport,
    )
    from polisyos.core.run.context import _RunInvocationAttempt
    from polisyos.core.run.manifest import RunInvocationStarted
    from polisyos.scientist.methods.search.judge_stack import JudgeVerdict
    from polisyos.scientist.orchestration.engine.context import ExecutionContext
    from polisyos.scientist.validation.policy_verified.phase5_candidate import (
        Phase5CandidateAssessment,
    )

_INPUT_BASIS_ROLE = "node_input_basis"
_INPUT_BASIS_KIND = "scientist.node_input_basis"
_INPUT_BASIS_SCHEMA = "polisyos.scientist.orchestration.engine.NodeInputBasis"
_CANON = CanonSpec(forbid_floats=False, sort_keys=True, exclude_none=False)
_MISSING = object()


class NodeInputPortError(ValueError):
    """A selected component input or its attempt binding is not established."""


def _state_bytes(state: ExperimentState) -> bytes:
    return to_canonical_bytes(state.model_dump(mode="python"), _CANON)


def _value_at(state: ExperimentState, path: str) -> Any:
    current: Any = state
    for part in path.split("."):
        if isinstance(current, BaseModel):
            current = getattr(current, part, _MISSING)
        elif isinstance(current, dict):
            current = current.get(part, _MISSING)
        else:
            return _MISSING
    return current


def _project(state: ExperimentState, contract: NodeInputContract) -> ExperimentState:
    projected = ExperimentState(run_id=state.run_id)
    for path in contract.state_paths:
        value = _value_at(state, path)
        if value is _MISSING:
            continue
        value = _completed_producer_value(value)
        parts = path.split(".")
        if len(parts) == 1:
            setattr(projected, path, value)
            continue
        target = getattr(projected, parts[0])
        for part in parts[1:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = value
    return projected


class NodeInputBasis(BaseModel):
    """Bind the consumed projection to an exact predecessor, contract and attempt."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    run_id: str = Field(min_length=1)
    node_alias: str = Field(min_length=1)
    attempt_id: str = Field(min_length=1)
    attempt_number: int = Field(ge=1)
    contract: NodeInputContract
    implementation_identity: RunInvocationImplementationIdentity
    implementation_dependencies_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bind_params: dict[str, Any]
    predecessor_state_ref: ArtifactRef
    projected_state_sha256: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    path_presence: dict[str, Literal["missing", "null", "value"]]
    execution_kind: Literal["producer", "cache_replay"] = "producer"
    source_cache_entry_ref: ArtifactRef | None = None

    @model_validator(mode="after")
    def _validate_basis(self) -> NodeInputBasis:
        if (
            self.predecessor_state_ref.manifest_profile_sha256 is None
            or self.implementation_identity.component_id != self.contract.component_id
            or set(self.path_presence) != set(self.contract.state_paths)
            or (self.execution_kind == "cache_replay") != (self.source_cache_entry_ref is not None)
            or (
                self.source_cache_entry_ref is not None
                and self.source_cache_entry_ref.manifest_profile_sha256 is None
            )
        ):
            raise ValueError("node_input_basis_identity_invalid")
        return self


def input_basis_options(basis: NodeInputBasis) -> ArtifactWriteOptions:
    """Use existing CAS lineage for this Engine-owned input binding."""
    inputs = [input_ref_from_artifact_ref(basis.predecessor_state_ref, role="predecessor")]
    if basis.source_cache_entry_ref is not None:
        inputs.append(input_ref_from_artifact_ref(basis.source_cache_entry_ref, role="cache_entry"))
    return ArtifactWriteOptions(
        kind=_INPUT_BASIS_KIND,
        media_type="application/json",
        schema=SchemaInfo(name=_INPUT_BASIS_SCHEMA, version="1.0"),
        inputs=inputs,
    )


@dataclass(frozen=True)
class NodeInputSelection:
    """Safe selected input coordinates; carries no predecessor or completion grant."""

    run_id: str
    component_id: str
    contract_id: str
    node_alias: str
    attempt_id: str
    basis_ref: ArtifactRef
    input_state_ref: ArtifactRef


_PHASE5_COMPONENT = "scientist.node_evaluate_verified_policy_phase5@1.0.0"
_PHASE5_CONTRACT = "policy_verified_phase5.v1"
_PHASE5_SOURCE_PATHS = (
    "artifacts_index.verified_policy_body_ref",
    "artifacts_index.verified_policy_candidate_ref",
    "reports_index.governance_report_ref",
)
_PHASE5_INPUT_PATHS = ("schema_version", "run_id", "execution_profile", *_PHASE5_SOURCE_PATHS)
_BODY_COMPONENT = "scientist.node_build_verified_policy_body@1.0.0"
_CANDIDATE_COMPONENT = "scientist.node_select_policy_candidate@1.0.0"
_GOVERNANCE_COMPONENT = "scientist.node_run_governance@1.2.0"
_PHASE5_OUTPUT_PATH = "artifacts_index.phase5_candidate_assessment_ref"
_COMPLETION_COMPONENT = "scientist.node_build_verified_policy_report@1.1.0"
_COMPLETION_CONTRACT = "policy_verified_completion.v1"
_COMPLETION_SOURCE_PATHS = (
    *_PHASE5_SOURCE_PATHS[:2],
    _PHASE5_OUTPUT_PATH,
    _PHASE5_SOURCE_PATHS[2],
)
_COMPLETION_EVIDENCE_ROLES = (
    "fairness_audit_report_ref",
    "shift_diagnostic_report_ref",
    "sensitivity_analysis_bundle_ref",
    "sensitivity_result_ref",
    "explanation_bundle_ref",
)
_COMPLETION_EVIDENCE_PATHS = tuple(
    f"{mapping}.{role}"
    for role in _COMPLETION_EVIDENCE_ROLES
    for mapping in ("artifacts_index", "reports_index")
)
_COMPLETION_REQUIREMENT_PATHS = (
    "params.high_impact",
    "params.phase5_requires_fairness",
    "params.protected_attributes",
    "params.phase5_require_advisor_consensus",
    "params.phase5_require_judge_verdict",
    "params.phase5_enforce_publication",
)
_COMPLETION_REF_PATHS = (*_COMPLETION_SOURCE_PATHS, *_COMPLETION_EVIDENCE_PATHS)
_COMPLETION_INPUT_PATHS = (
    "schema_version",
    "run_id",
    "execution_profile",
    *_COMPLETION_REF_PATHS,
    *_COMPLETION_REQUIREMENT_PATHS,
)
_COMPLETION_OUTPUT_PATHS = (
    "verified_policy_report_ref",
    "artifacts_index.verified_policy_report_ref",
    "artifacts_index.validation_report_ref",
)


def _phase5_source_profile(contract: NodeInputContract) -> bool:
    if contract.component_id != _PHASE5_COMPONENT:
        return False
    if (
        contract.contract_id != _PHASE5_CONTRACT
        or contract.state_paths != _PHASE5_INPUT_PATHS
        or contract.artifact_ref_paths != _PHASE5_SOURCE_PATHS
        or contract.bind_param_keys
    ):
        raise NodeInputPortError("node_input_source_view_contract_unsupported")
    return True


def _completion_source_profile(contract: NodeInputContract) -> bool:
    if contract.component_id != _COMPLETION_COMPONENT:
        return False
    if (
        contract.contract_id != _COMPLETION_CONTRACT
        or contract.state_paths != _COMPLETION_INPUT_PATHS
        or contract.artifact_ref_paths != _COMPLETION_REF_PATHS
        or contract.bind_param_keys
    ):
        raise NodeInputPortError("node_input_completion_contract_unsupported")
    return True


def _source_view_profile(contract: NodeInputContract) -> None:
    _phase5_source_profile(contract)
    _completion_source_profile(contract)


def _composed_currentness(
    statuses: tuple[ProducerArtifactCurrentness, ...],
) -> ProducerArtifactCurrentness:
    if "invalid" in statuses:
        return "invalid"
    if "stale" in statuses:
        return "stale"
    if "not_established" in statuses:
        return "not_established"
    return "current"


@dataclass(frozen=True)
class PolicyCompositionOccurrence:
    """Detached selected output and currentness; carries no readable basis grant."""

    artifact_ref: ArtifactRef | None
    status: ProducerArtifactCurrentness
    reason_code: str
    attempt_id: str | None = None
    attempt_basis_ref: ArtifactRef | None = None


@dataclass(frozen=True)
class PolicyCompositionEvidence:
    """An explicit evidence role, including absent or conflicting selections."""

    role: str
    artifact_ref: ArtifactRef | None
    status: ProducerArtifactCurrentness
    reason_code: str


@dataclass(frozen=True)
class VerifiedPolicyCompletionAdmission:
    """Fixed limited-composition facts for an exact pending report attempt.

    ``current`` describes source/occurrence integrity. It does not establish a
    legal verifier, evidence adequacy, independent nonrequirements or permission
    to publish. Nested domain DTOs are detached on every owner read.
    """

    run_id: str
    attempt_id: str
    input_state_ref: ArtifactRef
    selected_attempt_ref: ArtifactRef
    body: PolicyCompositionOccurrence
    candidate: PolicyCompositionOccurrence
    phase5: PolicyCompositionOccurrence
    historical_body: PolicyCompositionOccurrence
    historical_candidate: PolicyCompositionOccurrence
    initial_governance: PolicyCompositionOccurrence
    final_governance: PolicyCompositionOccurrence
    threshold: ProducerArtifactAdmission
    evidence: tuple[PolicyCompositionEvidence, ...]
    assessment: Phase5CandidateAssessment | None
    candidate_verdict: JudgeVerdict | None
    governance_report: GovernanceReport | None
    unsupported_requirements: tuple[str, ...] = ()
    limitation_codes: tuple[str, ...] = ()
    purpose: Literal["limited_policy_composition"] = "limited_policy_composition"
    requirement_authority: Literal["not_established"] = "not_established"
    publishable: Literal[False] = False

    @property
    def body_ref(self) -> ArtifactRef | None:
        """Return the exact selected body identity without a read capability."""
        return self.body.artifact_ref

    @property
    def candidate_ref(self) -> ArtifactRef | None:
        """Return the exact selected candidate identity."""
        return self.candidate.artifact_ref

    @property
    def phase5_assessment_ref(self) -> ArtifactRef | None:
        """Return the exact selected diagnostic identity."""
        return self.phase5.artifact_ref

    @property
    def initial_governance_ref(self) -> ArtifactRef | None:
        """Return the diagnostic's authenticated historical governance identity."""
        return self.initial_governance.artifact_ref

    @property
    def final_governance_ref(self) -> ArtifactRef | None:
        """Return the separately selected current governance identity."""
        return self.final_governance.artifact_ref

    @property
    def status(self) -> ProducerArtifactCurrentness:
        """Combine source integrity without interpreting missing evidence as approval."""
        return _composed_currentness(
            (
                self.body.status,
                self.candidate.status,
                self.phase5.status,
                self.historical_body.status,
                self.historical_candidate.status,
                self.initial_governance.status,
                self.final_governance.status,
                self.threshold.status,
                *(item.status for item in self.evidence if item.artifact_ref is not None),
                *(("not_established",) if self.unsupported_requirements else ()),
            )
        )


class VerifiedPolicyPhase5Admission(BaseModel):
    """Selected-source currentness facts, without predecessor/history access.

    Current source provenance does not confer publication permission or establish
    the isolation/adequacy of every governance pass. The actual consumer remains
    the fixed candidate-diagnostic component.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1.0"] = "1.0"
    purpose: Literal["selected_source_currentness"] = "selected_source_currentness"
    run_id: str
    attempt_id: str
    component_id: Literal["scientist.node_evaluate_verified_policy_phase5@1.0.0"]
    contract_id: Literal["policy_verified_phase5.v1"]
    input_state_ref: ArtifactRef
    body_ref: ArtifactRef | None
    candidate_ref: ArtifactRef | None
    governance_ref: ArtifactRef | None
    body_status: ProducerArtifactCurrentness
    candidate_status: ProducerArtifactCurrentness
    governance_status: ProducerArtifactCurrentness
    body_reason_code: str
    candidate_reason_code: str
    governance_reason_code: str
    body_attempt_id: str | None = None
    candidate_attempt_id: str | None = None
    governance_attempt_id: str | None = None
    governance_report: GovernanceReport | None = None

    @model_validator(mode="after")
    def _check_admitted_sources(self) -> VerifiedPolicyPhase5Admission:
        for ref, status in (
            (self.body_ref, self.body_status),
            (self.candidate_ref, self.candidate_status),
            (self.governance_ref, self.governance_status),
        ):
            if status == "current" and (ref is None or ref.manifest_profile_sha256 is None):
                raise ValueError("node_input_current_source_profile_missing")
        if (self.governance_status == "current") != (self.governance_report is not None):
            raise ValueError("node_input_governance_report_not_admitted")
        return self

    @property
    def status(self) -> ProducerArtifactCurrentness:
        """Compose all required source currentness results without promoting a gap."""
        statuses = (self.body_status, self.candidate_status, self.governance_status)
        if "invalid" in statuses:
            return "invalid"
        if "stale" in statuses:
            return "stale"
        if "not_established" in statuses:
            return "not_established"
        return "current"


def _selected_role_ref(state: ExperimentState, path: str) -> ArtifactRef | None:
    value = _value_at(state, path)
    if value is _MISSING or value is None:
        return None
    return ArtifactRef.model_validate(
        value.model_dump() if isinstance(value, ArtifactRef) else value
    )


def _basis_from_input(store: ArtifactStore, input_ref: ArtifactRef) -> NodeInputBasis | None:
    manifest = store.get_manifest(input_ref)
    edges = [edge for edge in manifest.inputs if edge.role == _INPUT_BASIS_ROLE]
    if len(edges) != 1 or edges[0].manifest_profile_sha256 is None:
        return None
    edge = edges[0]
    ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=_INPUT_BASIS_KIND,
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    return NodeInputBasis.model_validate(load_core_json_artifact(store, ref))


def _preceding_attempts(
    ctx: ExecutionContext, before: _RunInvocationAttempt | None
) -> list[_RunInvocationAttempt]:
    attempts = ctx.run.read_runtime_invocation_attempts()
    if before is None:
        return attempts
    indexes = [
        index
        for index, attempt in enumerate(attempts)
        if attempt.basis.attempt_id == before.basis.attempt_id
        and attempt.basis_ref == before.basis_ref
    ]
    if len(indexes) != 1:
        raise NodeInputPortError("node_input_source_occurrence_not_owner_linked")
    return attempts[: indexes[0]]


def _latest_selected_producer(
    ctx: ExecutionContext,
    predecessor: ExperimentState,
    ref: ArtifactRef | None,
    *,
    role: Literal["body", "candidate"],
    before: _RunInvocationAttempt | None = None,
) -> tuple[ProducerArtifactCurrentness, str, str | None]:
    """Use the existing owner against the exact latest selected occurrence."""
    from polisyos.scientist.orchestration.engine.component_identity import (
        _OWNERS,
        _require_owner_definition,
    )
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        resolve_engine_produced_artifact,
    )

    component = _BODY_COMPONENT if role == "body" else _CANDIDATE_COMPONENT
    if ref is None:
        return "not_established", f"selected_{role}_absent", None
    try:
        owner = _OWNERS.get(component)
        if owner is None or owner.input_contract_json is None:
            return "not_established", f"selected_{role}_implementation_not_established", None
        _, _, spec_accessor = _require_owner_definition(owner)
        contract = NodeInputContract.model_validate_json(owner.input_contract_json)
        spec = spec_accessor(owner.node_type())
        if tuple(spec.state_reads) != contract.state_paths:
            return "not_established", f"selected_{role}_input_contract_unsupported", None
        if role == "body":
            from polisyos.scientist.validation.policy_verified import load_verified_policy_body

            load_verified_policy_body(ctx.store, ref)
        else:
            from polisyos.scientist.policy_design.schema import load_policy_candidate_schema

            load_policy_candidate_schema(ctx.store, ref)
        manifest = ctx.store.get_manifest(ref)
        attempt_edges = [edge for edge in manifest.inputs if edge.role == "selected_attempt"]
        input_edges = [edge for edge in manifest.inputs if edge.role == "selected_input"]
        if len(attempt_edges) != 1 or len(input_edges) != 1:
            return "not_established", f"selected_{role}_attempt_lineage_missing", None
        attempts = [
            attempt
            for attempt in _preceding_attempts(ctx, before)
            if attempt.basis.component_id == component
        ]
        if not attempts:
            return "not_established", f"selected_{role}_producer_missing", None
        latest = attempts[-1]
        if latest.outcome is None or latest.outcome.status != "ok":
            return (
                "not_established",
                f"selected_{role}_latest_attempt_not_successful",
                latest.basis.attempt_id,
            )
        selected_key = artifact_ref_identity_key(ref)
        if not any(
            artifact_ref_identity_key(output) == selected_key
            for output in latest.outcome.output_refs
        ):
            return "stale", f"selected_{role}_occurrence_not_latest", latest.basis.attempt_id
        physical = [
            attempt
            for attempt in attempts
            if input_ref_from_artifact_ref(attempt.basis_ref, role="selected_attempt")
            == attempt_edges[0]
            and input_ref_from_artifact_ref(attempt.basis.input_state_ref, role="selected_input")
            == input_edges[0]
        ]
        if len(physical) != 1:
            return "not_established", f"selected_{role}_attempt_not_owner_linked", None
        physical_attempt = physical[0]
        if latest.basis_ref != physical_attempt.basis_ref:
            replay = _basis_from_input(ctx.store, latest.basis.input_state_ref)
            if replay is None or replay.execution_kind != "cache_replay":
                return "stale", f"selected_{role}_occurrence_not_latest", latest.basis.attempt_id
        physical_admission = resolve_engine_produced_artifact(
            ctx,
            predecessor,
            ref,
            expected_component_id=component,
            expected_node_spec=spec,
            source_read_paths=contract.state_paths,
            expected_attempt_id=physical_attempt.basis.attempt_id,
            expected_basis_ref=physical_attempt.basis_ref,
        )
        if not physical_admission.is_current:
            return (
                physical_admission.status,
                physical_admission.reason_code,
                physical_attempt.basis.attempt_id,
            )
        current = resolve_engine_produced_artifact(
            ctx,
            predecessor,
            ref,
            expected_component_id=component,
            expected_node_spec=spec,
            source_read_paths=contract.state_paths,
            expected_attempt_id=latest.basis.attempt_id,
            expected_basis_ref=latest.basis_ref,
        )
        return current.status, current.reason_code, latest.basis.attempt_id
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
        return "not_established", f"selected_{role}_owner_revalidation_failed", None


class _CompletedOccurrenceRefused(NodeInputPortError):
    def __init__(self, status: ProducerArtifactCurrentness, reason_code: str) -> None:
        self.admission = ProducerArtifactAdmission(status, reason_code)
        super().__init__(reason_code)


@dataclass(frozen=True)
class _CompletedPhase5Occurrence:
    """Engine-local reconstruction; never install it in a node context."""

    attempt: _RunInvocationAttempt
    predecessor: ExperimentState
    successor: ExperimentState
    assessment: Phase5CandidateAssessment
    initial_governance: GovernanceReport
    initial_attempt: _RunInvocationAttempt
    body_attempt_id: str
    candidate_attempt_id: str


def _invocation_context(
    ctx: ExecutionContext, attempt: _RunInvocationAttempt, *, successful: bool
) -> ExecutionContext:
    from polisyos.scientist.orchestration.engine.context import (
        ExecutionContext as Context,
    )
    from polisyos.scientist.orchestration.engine.context import _EngineInvocationBinding

    return Context(
        store=ctx.store,
        run=ctx.run,
        logger=ctx.logger,
        _engine_invocation=_EngineInvocationBinding(
            run_id=attempt.basis.run_id,
            attempt_id=attempt.basis.attempt_id,
            basis_ref=attempt.basis_ref,
            require_successful_completion=successful,
        ),
    )


def _invocation_precedes(
    ctx: ExecutionContext, prior: _RunInvocationAttempt, later: _RunInvocationAttempt
) -> bool:
    """Use the actual selected workflow graph, never an alias or timestamp policy."""
    from polisyos.scientist.orchestration.engine.workflow_spec import WorkflowSpec

    if (
        prior.basis.workflow_spec_ref != later.basis.workflow_spec_ref
        or prior.basis.run_id != later.basis.run_id
        or not any(item.basis_ref == prior.basis_ref for item in _preceding_attempts(ctx, later))
    ):
        return False
    workflow = WorkflowSpec.model_validate(
        load_core_json_artifact(ctx.store, later.basis.workflow_spec_ref)
    )
    nodes = {node.alias: node for node in workflow.nodes}
    if later.basis.node_alias not in nodes or prior.basis.node_alias not in nodes:
        return False
    pending = list(nodes[later.basis.node_alias].depends_on)
    ancestors: set[str] = set()
    while pending:
        alias = pending.pop()
        if alias not in nodes:
            return False
        if alias not in ancestors:
            ancestors.add(alias)
            pending.extend(nodes[alias].depends_on)
    return prior.basis.node_alias in ancestors


def _completed_phase5_occurrence(
    ctx: ExecutionContext,
    selected_ref: ArtifactRef,
    *,
    before: _RunInvocationAttempt,
) -> _CompletedPhase5Occurrence:
    """Reopen a fixed successful diagnostic, preserving its historical source basis."""
    from polisyos.scientist.governance.report_currentness import (
        resolve_current_governance_report,
    )
    from polisyos.scientist.orchestration.engine.component_identity import (
        _OWNERS,
        _require_owner_definition,
    )
    from polisyos.scientist.orchestration.engine.context import (
        _load_engine_owned_invocation_input_state,
    )
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        _load_invocation_output_state,
        engine_invocation_identity_is_current,
    )
    from polisyos.scientist.validation.policy_verified.phase5_candidate import (
        load_phase5_candidate_assessment,
    )

    attempts = _preceding_attempts(ctx, before)
    selected = [item for item in attempts if item.basis.component_id == _PHASE5_COMPONENT]
    if not selected:
        raise _CompletedOccurrenceRefused("not_established", "completed_phase5_producer_missing")
    attempt = selected[-1]
    outcome = attempt.outcome
    if outcome is None or outcome.status != "ok" or outcome.outcome_state_ref is None:
        raise _CompletedOccurrenceRefused(
            "not_established", "completed_phase5_latest_attempt_not_successful"
        )
    if not any(
        artifact_ref_identity_key(ref) == artifact_ref_identity_key(selected_ref)
        for ref in outcome.output_refs
    ):
        raise _CompletedOccurrenceRefused("stale", "completed_phase5_occurrence_not_latest")
    if not _invocation_precedes(ctx, attempt, before):
        raise _CompletedOccurrenceRefused(
            "not_established", "completed_phase5_not_selected_workflow_ancestor"
        )
    owner = _OWNERS.get(_PHASE5_COMPONENT)
    if owner is None or owner.input_contract_json is None:
        raise _CompletedOccurrenceRefused(
            "not_established", "completed_phase5_implementation_not_established"
        )
    _, _, spec_accessor = _require_owner_definition(owner)
    contract = NodeInputContract.model_validate_json(owner.input_contract_json)
    spec = spec_accessor(owner.node_type())
    if (
        not _phase5_source_profile(contract)
        or tuple(spec.state_reads) != contract.state_paths
        or tuple(spec.state_writes) != (_PHASE5_OUTPUT_PATH,)
        or not engine_invocation_identity_is_current(
            ctx, attempt.basis, expected_component_id=_PHASE5_COMPONENT
        )
    ):
        raise _CompletedOccurrenceRefused(
            "not_established", "completed_phase5_implementation_not_established"
        )
    bound_ctx = _invocation_context(ctx, attempt, successful=True)
    projected = _load_engine_owned_invocation_input_state(
        bound_ctx, ExperimentState(run_id=attempt.basis.run_id)
    )
    basis = _basis_from_input(ctx.store, attempt.basis.input_state_ref)
    if projected is None or basis is None or basis.execution_kind != "producer":
        raise _CompletedOccurrenceRefused(
            "not_established", "completed_phase5_input_basis_not_established"
        )
    predecessor = _load_invocation_output_state(ctx, basis.predecessor_state_ref)
    output = _load_invocation_output_state(ctx, outcome.outcome_state_ref)
    assessment = load_phase5_candidate_assessment(ctx.store, selected_ref)
    if (
        assessment.run_id != attempt.basis.run_id
        or assessment.selected_input_ref != attempt.basis.input_state_ref
        or assessment.selected_attempt_ref != attempt.basis_ref
        or _selected_role_ref(output, _PHASE5_OUTPUT_PATH) != selected_ref
        or len(outcome.output_refs) != 3
        or {artifact_ref_identity_key(ref) for ref in outcome.output_refs}
        != {
            artifact_ref_identity_key(ref)
            for ref in (selected_ref, assessment.judge_verdict_ref, assessment.threshold_basis_ref)
        }
        or any(
            _selected_role_ref(predecessor, path) != ref
            for path, ref in zip(
                _PHASE5_SOURCE_PATHS,
                (assessment.body_ref, assessment.candidate_ref, assessment.governance_ref),
                strict=True,
            )
        )
    ):
        raise _CompletedOccurrenceRefused(
            "invalid", "completed_phase5_selected_source_or_attempt_mismatch"
        )
    # Core records the physically projected outcome. Reapply precisely the one
    # owned ref write to the original full predecessor; hidden maps are never
    # deleted or recovered by projecting the consumer backwards.
    outcome_state = NodeOutcome(status="ok", state=output, artifacts=list(outcome.output_refs))
    projected_merge = merge_parallel_outcomes(
        projected, {"phase5": outcome_state}, {"phase5": [_PHASE5_OUTPUT_PATH]}
    )
    full_merge = merge_parallel_outcomes(
        predecessor, {"phase5": outcome_state}, {"phase5": [_PHASE5_OUTPUT_PATH]}
    )
    if (
        projected_merge.conflicts
        or full_merge.conflicts
        or _state_bytes(projected_merge.state) != _state_bytes(output)
    ):
        raise _CompletedOccurrenceRefused("invalid", "completed_phase5_output_outside_contract")
    source_attempt_ids = []
    sources: tuple[tuple[Literal["body", "candidate"], ArtifactRef], ...] = (
        ("body", assessment.body_ref),
        ("candidate", assessment.candidate_ref),
    )
    for role, ref in sources:
        status, reason, source_attempt_id = _latest_selected_producer(
            ctx, predecessor, ref, role=role, before=attempt
        )
        if status != "current" or source_attempt_id is None:
            raise _CompletedOccurrenceRefused(status, reason)
        source = [item for item in attempts if item.basis.attempt_id == source_attempt_id]
        if len(source) != 1 or not _invocation_precedes(ctx, source[0], attempt):
            raise _CompletedOccurrenceRefused(
                "not_established", f"completed_phase5_{role}_not_selected_workflow_ancestor"
            )
        source_attempt_ids.append(source_attempt_id)
    initial = resolve_current_governance_report(ctx, predecessor, assessment.governance_ref)
    binding = initial.report.invocation_binding if initial.report is not None else None
    if not initial.is_current or binding is None:
        raise _CompletedOccurrenceRefused(initial.status, initial.reason_code)
    prior_governance = [
        item
        for item in _preceding_attempts(ctx, attempt)
        if item.basis.component_id == _GOVERNANCE_COMPONENT
    ]
    if (
        not prior_governance
        or prior_governance[-1].basis_ref != binding.attempt_basis_ref
        or prior_governance[-1].basis.attempt_id != binding.attempt_id
    ):
        raise _CompletedOccurrenceRefused("stale", "completed_phase5_initial_governance_not_latest")
    initial_attempt = prior_governance[-1]
    initial_outcome = initial_attempt.outcome
    if (
        initial_outcome is None
        or initial_outcome.outcome_state_ref is None
        or not _invocation_precedes(ctx, initial_attempt, attempt)
        or _state_bytes(_load_invocation_output_state(ctx, initial_outcome.outcome_state_ref))
        != _state_bytes(predecessor)
    ):
        raise _CompletedOccurrenceRefused(
            "stale", "completed_phase5_initial_governance_transition_changed"
        )
    assert initial.report is not None
    return _CompletedPhase5Occurrence(
        attempt=attempt,
        predecessor=predecessor,
        successor=full_merge.state,
        assessment=assessment,
        initial_governance=initial.report,
        initial_attempt=initial_attempt,
        body_attempt_id=source_attempt_ids[0],
        candidate_attempt_id=source_attempt_ids[1],
    )


def reconcile_verified_policy_phase5_transition(
    ctx: ExecutionContext, state: ExperimentState, initial_basis_ref: ArtifactRef
) -> ProducerArtifactAdmission:
    """Recompute the exact initial-Gov → Phase-5 → pending final-Gov transition.

    Only the fixed candidate diagnostic's declared output may bridge the two
    governance occurrences. The whole original predecessor is compared; this
    operation returns no state, history, grant or publication authority.
    """
    from polisyos.scientist.orchestration.engine.context import (
        _EngineInvocationBinding,
        _load_engine_owned_invocation_input_state,
    )
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        engine_invocation_identity_is_current,
    )

    try:
        binding = ctx._engine_invocation
        if type(binding) is not _EngineInvocationBinding:
            raise NodeInputPortError("phase5_transition_consumer_not_owner_linked")
        matches = [
            item
            for item in ctx.run.read_runtime_invocation_attempts()
            if item.basis.attempt_id == binding.attempt_id and item.basis_ref == binding.basis_ref
        ]
        if (
            len(matches) != 1
            or matches[0].outcome is not None
            or matches[0].basis.component_id != _GOVERNANCE_COMPONENT
            or not engine_invocation_identity_is_current(
                ctx, matches[0].basis, expected_component_id=_GOVERNANCE_COMPONENT
            )
        ):
            raise NodeInputPortError("phase5_transition_consumer_not_owner_linked")
        current = matches[0]
        current_input = _load_engine_owned_invocation_input_state(ctx, state)
        if current_input is None or _state_bytes(current_input) != _state_bytes(state):
            raise NodeInputPortError("phase5_transition_consumer_input_changed")
        ref = _selected_role_ref(current_input, _PHASE5_OUTPUT_PATH)
        if ref is None:
            raise NodeInputPortError("phase5_transition_selected_assessment_absent")
        occurrence = _completed_phase5_occurrence(ctx, ref, before=current)
        if occurrence.initial_attempt.basis_ref != initial_basis_ref:
            raise NodeInputPortError("phase5_transition_initial_governance_mismatch")
        if _state_bytes(occurrence.successor) != _state_bytes(current_input):
            raise _CompletedOccurrenceRefused("stale", "phase5_transition_full_state_changed")
        return ProducerArtifactAdmission("current", "phase5_transition_recomputed")
    except _CompletedOccurrenceRefused as exc:
        return exc.admission
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        reason = (
            str(exc) if isinstance(exc, NodeInputPortError) else "phase5_transition_not_established"
        )
        return ProducerArtifactAdmission("not_established", reason)


class _VerifiedPolicyPhase5AdmissionOwner:
    """Fixed readonly run-owner channel; it stores no predecessor state.

    The supported operation reopens the actual pending consumer basis and exact
    predecessor through the existing owners. Only the detached admission DTO is
    returned; there is no arbitrary selector, callback, run-history or store API.
    """

    __slots__ = ("__definition_sha256", "__identity", "__logger", "__run", "__selection", "__store")

    def __init__(
        self,
        ctx: ExecutionContext,
        selection: NodeInputSelection,
        identity: RunInvocationImplementationIdentity,
        definition_sha256: str,
    ) -> None:
        self.__store, self.__run, self.__logger = ctx.store, ctx.run, ctx.logger
        self.__selection, self.__identity, self.__definition_sha256 = (
            selection,
            identity,
            definition_sha256,
        )

    def read(self) -> VerifiedPolicyPhase5Admission:
        from polisyos.scientist.governance.report_currentness import (
            resolve_current_governance_report,
        )
        from polisyos.scientist.orchestration.engine.component_identity import (
            _OWNERS,
            matches_engine_component_identity,
        )
        from polisyos.scientist.orchestration.engine.context import (
            ExecutionContext as Context,
        )
        from polisyos.scientist.orchestration.engine.context import (
            _EngineInvocationBinding,
            _load_engine_owned_invocation_input_state,
        )

        selection = self.__selection
        owner = _OWNERS.get(selection.component_id)
        if (
            owner is None
            or owner.input_definition_sha256 != self.__definition_sha256
            or not matches_engine_component_identity(self.__identity, selection.component_id, {})
        ):
            raise NodeInputPortError("node_input_source_view_consumer_changed")
        ctx = Context(
            store=self.__store,
            run=self.__run,
            logger=self.__logger,
            _engine_invocation=_EngineInvocationBinding(
                run_id=selection.run_id,
                attempt_id=selection.attempt_id,
                basis_ref=selection.basis_ref,
            ),
        )
        matches = [
            attempt
            for attempt in self.__run.read_runtime_invocation_attempts()
            if attempt.basis.attempt_id == selection.attempt_id
            and attempt.basis_ref == selection.basis_ref
        ]
        if len(matches) != 1:
            raise NodeInputPortError("node_input_source_view_attempt_not_owner_linked")
        attempt = matches[0]
        if (
            attempt.outcome is not None
            or attempt.basis.component_id != selection.component_id
            or attempt.basis.input_state_ref != selection.input_state_ref
            or attempt.basis.implementation_identity != self.__identity
        ):
            raise NodeInputPortError("node_input_source_view_attempt_mismatch")
        projected = _load_engine_owned_invocation_input_state(
            ctx, ExperimentState(run_id=selection.run_id)
        )
        if projected is None:
            raise NodeInputPortError("node_input_source_view_input_missing")
        basis = _basis_from_input(self.__store, selection.input_state_ref)
        if basis is None or not _phase5_source_profile(basis.contract):
            raise NodeInputPortError("node_input_source_view_contract_unsupported")
        predecessor = ExperimentState.model_validate(
            load_core_json_artifact(self.__store, basis.predecessor_state_ref)
        )
        body_ref, candidate_ref, governance_ref = (
            _selected_role_ref(predecessor, path) for path in _PHASE5_SOURCE_PATHS
        )
        body_status, body_reason, body_attempt = _latest_selected_producer(
            ctx, predecessor, body_ref, role="body"
        )
        candidate_status, candidate_reason, candidate_attempt = _latest_selected_producer(
            ctx, predecessor, candidate_ref, role="candidate"
        )
        governance = resolve_current_governance_report(ctx, predecessor, governance_ref)
        report = governance.report if governance.is_current else None
        governance_status = governance.status
        governance_reason = governance.reason_code
        governance_attempt = (
            report.invocation_binding.attempt_id
            if report is not None and report.invocation_binding is not None
            else None
        )
        governance_attempts = [
            item
            for item in self.__run.read_runtime_invocation_attempts()
            if item.basis.component_id == _GOVERNANCE_COMPONENT
        ]
        if governance.is_current and (
            not governance_attempts
            or governance_attempts[-1].basis.attempt_id != governance_attempt
        ):
            governance_status, governance_reason, report = (
                "stale",
                "selected_governance_occurrence_not_latest",
                None,
            )
        return VerifiedPolicyPhase5Admission(
            run_id=selection.run_id,
            attempt_id=selection.attempt_id,
            component_id=_PHASE5_COMPONENT,
            contract_id=_PHASE5_CONTRACT,
            input_state_ref=selection.input_state_ref,
            body_ref=body_ref,
            candidate_ref=candidate_ref,
            governance_ref=governance_ref,
            body_status=body_status,
            candidate_status=candidate_status,
            governance_status=governance_status,
            body_reason_code=body_reason,
            candidate_reason_code=candidate_reason,
            governance_reason_code=governance_reason,
            body_attempt_id=body_attempt,
            candidate_attempt_id=candidate_attempt,
            governance_attempt_id=governance_attempt,
            governance_report=report,
        )


def read_verified_policy_phase5_admission(
    ctx: ExecutionContext, state: ExperimentState
) -> VerifiedPolicyPhase5Admission:
    """Revalidate fixed Phase-5 sources through the private run-owner channel.

    Args:
        ctx: The active Engine-appointed restricted consumer context.
        state: The exact unchanged input projection delivered to that consumer.

    Returns:
        Detached selected-source facts and an admitted governance report, without
        predecessor content, run history or a completion/publication grant.

    Raises:
        NodeInputPortError: The consumer, input or pending attempt is not the
            selected Engine-owned invocation.
    """
    selection = read_input_port_basis(ctx, state)
    owner = ctx._verified_policy_phase5_admission_owner
    if type(owner) is not _VerifiedPolicyPhase5AdmissionOwner or not _phase5_source_profile(
        NodeInputContract(
            contract_id=selection.contract_id,
            component_id=selection.component_id,
            state_paths=_PHASE5_INPUT_PATHS,
            artifact_ref_paths=_PHASE5_SOURCE_PATHS,
        )
    ):
        raise NodeInputPortError("node_input_source_view_not_installed")
    admission = owner.read()
    # The scoped read checks timeout/revocation again after owner I/O and binds
    # the result to the actual unchanged consumer input, never caller flags.
    current = read_input_port_basis(ctx, state)
    if (
        current != selection
        or admission.run_id != selection.run_id
        or admission.attempt_id != selection.attempt_id
        or admission.input_state_ref != selection.input_state_ref
    ):
        raise NodeInputPortError("node_input_source_view_attempt_mismatch")
    return admission.model_copy(deep=True)


def _completion_evidence(
    ctx: ExecutionContext, predecessor: ExperimentState
) -> tuple[tuple[PolicyCompositionEvidence, ...], tuple[str, ...]]:
    from polisyos.scientist.validation.phase5_preflight import (
        _PHASE5_OWNER_KINDS,
        _is_phase5_ref_key,
        _load_phase5_owned_evidence,
        _Phase5RefCandidate,
    )

    evidence = []
    unsupported = []
    for role in _COMPLETION_EVIDENCE_ROLES:
        selected = tuple(
            ref
            for mapping in ("artifacts_index", "reports_index")
            if (ref := _selected_role_ref(predecessor, f"{mapping}.{role}")) is not None
        )
        if not selected:
            evidence.append(
                PolicyCompositionEvidence(role, None, "not_established", "phase5_evidence_absent")
            )
            continue
        ref = selected[0]
        if any(
            artifact_ref_identity_key(item) != artifact_ref_identity_key(ref) for item in selected
        ):
            evidence.append(
                PolicyCompositionEvidence(role, ref, "invalid", "phase5_evidence_role_conflict")
            )
            continue
        try:
            _load_phase5_owned_evidence(
                ctx,
                role,
                _Phase5RefCandidate(
                    reference=ref,
                    ref_text=str(ref.artifact_id),
                    expected_kind=_PHASE5_OWNER_KINDS[role],
                ),
            )
        except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError):
            evidence.append(
                PolicyCompositionEvidence(role, ref, "invalid", "phase5_evidence_owner_invalid")
            )
        else:
            evidence.append(
                PolicyCompositionEvidence(role, ref, "current", "phase5_evidence_owner_recomputed")
            )
    for mapping_name in ("inputs", "artifacts_index", "reports_index", "params"):
        for key, value in getattr(predecessor, mapping_name).items():
            path = f"{mapping_name}.{key}"
            if value is not None and _is_phase5_ref_key(key) and path not in _COMPLETION_REF_PATHS:
                unsupported.append(path)
    # These legacy payload channels are data, never selected judge/advisor
    # occurrences. Their presence must not vanish when the physical port is cut.
    for key, value in predecessor.params.items():
        path = f"params.{key}"
        if value is not None and (
            key
            in {
                "judge_verdict",
                "phase5_judge_verdict",
                "method_advisor",
                "method_advisor_result",
                "advisor_result",
                "cross_method_consensus",
                "advisor_consensus",
                "ddm_readiness",
                "drift_readiness",
            }
            or (key.startswith("phase5_") and path not in _COMPLETION_REQUIREMENT_PATHS)
        ):
            unsupported.append(path)
    if predecessor.params.get("phase5_require_advisor_consensus"):
        # There is no selected advisor evidence owner in the fixed profile.
        unsupported.append("params.phase5_require_advisor_consensus")
    return tuple(evidence), tuple(sorted(set(unsupported)))


def _completion_occurrence(
    ctx: ExecutionContext,
    ref: ArtifactRef | None,
    status: ProducerArtifactCurrentness,
    reason: str,
    attempt_id: str | None,
) -> PolicyCompositionOccurrence:
    attempts = [
        item
        for item in ctx.run.read_runtime_invocation_attempts()
        if item.basis.attempt_id == attempt_id
    ]
    return PolicyCompositionOccurrence(
        ref,
        status,
        reason,
        attempt_id,
        attempts[0].basis_ref if len(attempts) == 1 else None,
    )


def _completion_facts(
    ctx: ExecutionContext,
    selection: NodeInputSelection,
    consumer: _RunInvocationAttempt,
    predecessor: ExperimentState,
) -> VerifiedPolicyCompletionAdmission:
    from polisyos.scientist.governance.report_currentness import (
        resolve_current_governance_report,
    )
    from polisyos.scientist.methods.search.judge_stack import load_candidate_judge_verdict
    from polisyos.scientist.methods.search.judge_threshold_basis import (
        resolve_judge_threshold_basis,
        selected_judge_threshold_registry,
    )
    from polisyos.scientist.orchestration.engine.context import (
        _load_engine_owned_invocation_input_state,
    )
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        _load_invocation_output_state,
    )

    body_ref, candidate_ref, phase5_ref, final_ref = (
        _selected_role_ref(predecessor, path) for path in _COMPLETION_SOURCE_PATHS
    )

    def absent(ref: ArtifactRef | None) -> PolicyCompositionOccurrence:
        return PolicyCompositionOccurrence(
            ref, "not_established", "completion_source_not_established"
        )

    body, candidate, phase5 = absent(body_ref), absent(candidate_ref), absent(phase5_ref)
    historical_body, historical_candidate, initial_governance = (
        absent(None),
        absent(None),
        absent(None),
    )
    final_governance = absent(final_ref)
    threshold = ProducerArtifactAdmission("not_established", "completion_threshold_not_established")
    assessment = None
    candidate_verdict = None
    governance_report = None
    evidence, unsupported = _completion_evidence(ctx, predecessor)
    limitations = [
        "legal_claim_verification_not_established",
        "option_program_correspondence_not_established",
        "phase5_requirement_scope_not_established",
        *(f"phase5_evidence_absent:{item.role}" for item in evidence if item.artifact_ref is None),
    ]
    try:
        if body_ref is None or candidate_ref is None or phase5_ref is None or final_ref is None:
            raise NodeInputPortError("completion_selected_source_absent")
        occurrence = _completed_phase5_occurrence(ctx, phase5_ref, before=consumer)
        assessment = occurrence.assessment
        phase5 = _completion_occurrence(
            ctx,
            phase5_ref,
            "current",
            "completed_phase5_occurrence_recomputed",
            occurrence.attempt.basis.attempt_id,
        )
        historical_body = _completion_occurrence(
            ctx,
            assessment.body_ref,
            "current",
            "completion_historical_body_recomputed",
            occurrence.body_attempt_id,
        )
        historical_candidate = _completion_occurrence(
            ctx,
            assessment.candidate_ref,
            "current",
            "completion_historical_candidate_recomputed",
            occurrence.candidate_attempt_id,
        )
        initial_governance = _completion_occurrence(
            ctx,
            assessment.governance_ref,
            "current",
            "completion_initial_governance_recomputed",
            occurrence.initial_attempt.basis.attempt_id,
        )
        if artifact_ref_identity_key(body_ref) != artifact_ref_identity_key(
            assessment.body_ref
        ) or artifact_ref_identity_key(candidate_ref) != artifact_ref_identity_key(
            assessment.candidate_ref
        ):
            raise _CompletedOccurrenceRefused("stale", "completion_selected_source_changed")
        body = _completion_occurrence(
            ctx,
            body_ref,
            *_latest_selected_producer(ctx, predecessor, body_ref, role="body", before=consumer),
        )
        candidate = _completion_occurrence(
            ctx,
            candidate_ref,
            *_latest_selected_producer(
                ctx, predecessor, candidate_ref, role="candidate", before=consumer
            ),
        )
        final = resolve_current_governance_report(ctx, predecessor, final_ref)
        final_binding = final.report.invocation_binding if final.report is not None else None
        final_governance = _completion_occurrence(
            ctx,
            final_ref,
            final.status,
            final.reason_code,
            final_binding.attempt_id if final_binding is not None else None,
        )
        if not final.is_current or final_binding is None:
            raise _CompletedOccurrenceRefused(final.status, final.reason_code)
        final_attempts = [
            item
            for item in _preceding_attempts(ctx, consumer)
            if item.basis.component_id == _GOVERNANCE_COMPONENT
        ]
        if (
            not final_attempts
            or final_attempts[-1].basis_ref != final_binding.attempt_basis_ref
            or final_binding.attempt_basis_ref == occurrence.initial_attempt.basis_ref
            or artifact_ref_identity_key(final_ref)
            == artifact_ref_identity_key(assessment.governance_ref)
        ):
            raise _CompletedOccurrenceRefused(
                "stale", "completion_final_governance_not_latest_distinct"
            )
        final_attempt = final_attempts[-1]
        final_input = _load_engine_owned_invocation_input_state(
            _invocation_context(ctx, final_attempt, successful=True), predecessor
        )
        final_outcome = final_attempt.outcome
        if (
            final_input is None
            or final_outcome is None
            or final_outcome.outcome_state_ref is None
            or not _invocation_precedes(ctx, occurrence.attempt, final_attempt)
            or not _invocation_precedes(ctx, final_attempt, consumer)
            or _state_bytes(final_input) != _state_bytes(occurrence.successor)
            or _state_bytes(_load_invocation_output_state(ctx, final_outcome.outcome_state_ref))
            != _state_bytes(predecessor)
        ):
            raise _CompletedOccurrenceRefused(
                "stale", "completion_final_governance_transition_changed"
            )
        live_threshold = resolve_judge_threshold_basis(
            ctx.store, assessment.threshold_basis_ref, selected_judge_threshold_registry()
        )
        threshold = ProducerArtifactAdmission(live_threshold.status, live_threshold.reason_code)
        candidate_verdict = load_candidate_judge_verdict(ctx.store, assessment.judge_verdict_ref)
        governance_report = final.report
        limitations.extend(assessment.limitation_codes)
        if any(item.source == "missing" for item in assessment.threshold_uses):
            limitations.append("phase5_threshold_requirement_not_established")
        if governance_report is not None and governance_report.verdict != "approve":
            limitations.append(f"final_governance_{governance_report.verdict}")
    except _CompletedOccurrenceRefused as exc:
        phase5 = replace(phase5, status=exc.admission.status, reason_code=exc.admission.reason_code)
        limitations.append(exc.admission.reason_code)
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, NodeInputPortError)
            else "completion_owner_revalidation_failed"
        )
        phase5 = replace(phase5, status="not_established", reason_code=reason)
        limitations.append(reason)
    return VerifiedPolicyCompletionAdmission(
        run_id=selection.run_id,
        attempt_id=selection.attempt_id,
        input_state_ref=selection.input_state_ref,
        selected_attempt_ref=selection.basis_ref,
        body=body,
        candidate=candidate,
        phase5=phase5,
        historical_body=historical_body,
        historical_candidate=historical_candidate,
        initial_governance=initial_governance,
        final_governance=final_governance,
        threshold=threshold,
        evidence=evidence,
        assessment=assessment,
        candidate_verdict=candidate_verdict,
        governance_report=governance_report,
        unsupported_requirements=unsupported,
        limitation_codes=tuple(dict.fromkeys(limitations)),
    )


class _VerifiedPolicyCompletionAdmissionOwner:
    """Fixed completion read operation; raw predecessor exists only as a local."""

    __slots__ = ("__definition_sha256", "__identity", "__logger", "__run", "__selection", "__store")

    def __init__(
        self,
        ctx: ExecutionContext,
        selection: NodeInputSelection,
        identity: RunInvocationImplementationIdentity,
        definition_sha256: str,
    ) -> None:
        self.__store, self.__run, self.__logger = ctx.store, ctx.run, ctx.logger
        self.__selection, self.__identity, self.__definition_sha256 = (
            selection,
            identity,
            definition_sha256,
        )

    def read(self) -> VerifiedPolicyCompletionAdmission:
        from polisyos.scientist.orchestration.engine.component_identity import (
            _OWNERS,
            matches_engine_component_identity,
        )
        from polisyos.scientist.orchestration.engine.context import (
            ExecutionContext as Context,
        )
        from polisyos.scientist.orchestration.engine.context import (
            _EngineInvocationBinding,
            _load_engine_owned_invocation_input_state,
        )
        from polisyos.scientist.orchestration.engine.producer_currentness import (
            _load_invocation_output_state,
        )

        selection = self.__selection
        owner = _OWNERS.get(selection.component_id)
        if (
            owner is None
            or owner.input_definition_sha256 != self.__definition_sha256
            or not matches_engine_component_identity(self.__identity, _COMPLETION_COMPONENT, {})
        ):
            raise NodeInputPortError("node_input_completion_consumer_changed")
        ctx = Context(
            store=self.__store,
            run=self.__run,
            logger=self.__logger,
            _engine_invocation=_EngineInvocationBinding(
                run_id=selection.run_id,
                attempt_id=selection.attempt_id,
                basis_ref=selection.basis_ref,
            ),
        )
        matches = [
            item
            for item in self.__run.read_runtime_invocation_attempts()
            if item.basis.attempt_id == selection.attempt_id
            and item.basis_ref == selection.basis_ref
        ]
        if (
            len(matches) != 1
            or matches[0].outcome is not None
            or matches[0].basis.component_id != _COMPLETION_COMPONENT
            or matches[0].basis.input_state_ref != selection.input_state_ref
            or matches[0].basis.implementation_identity != self.__identity
        ):
            raise NodeInputPortError("node_input_completion_attempt_mismatch")
        projected = _load_engine_owned_invocation_input_state(
            ctx, ExperimentState(run_id=selection.run_id)
        )
        basis = _basis_from_input(self.__store, selection.input_state_ref)
        if projected is None or basis is None or not _completion_source_profile(basis.contract):
            raise NodeInputPortError("node_input_completion_contract_unsupported")
        predecessor = _load_invocation_output_state(ctx, basis.predecessor_state_ref)
        return _completion_facts(ctx, selection, matches[0], predecessor)


def read_verified_policy_completion_admission(
    ctx: ExecutionContext, state: ExperimentState
) -> VerifiedPolicyCompletionAdmission:
    """Revalidate completed source occurrences for the fixed limited report port.

    The returned immutable coordinates and detached domain DTOs carry no public
    predecessor/history interface, raw CAS grant, or permission to publish.
    """
    selection = read_input_port_basis(ctx, state)
    owner = ctx._verified_policy_completion_admission_owner
    if (
        type(owner) is not _VerifiedPolicyCompletionAdmissionOwner
        or selection.component_id != _COMPLETION_COMPONENT
        or selection.contract_id != _COMPLETION_CONTRACT
    ):
        raise NodeInputPortError("node_input_completion_view_not_installed")
    result = owner.read()
    if read_input_port_basis(ctx, state) != selection or (
        result.run_id,
        result.attempt_id,
        result.input_state_ref,
        result.selected_attempt_ref,
    ) != (selection.run_id, selection.attempt_id, selection.input_state_ref, selection.basis_ref):
        raise NodeInputPortError("node_input_completion_attempt_mismatch")
    return deepcopy(result)


def read_completed_verified_policy_composition(
    ctx: ExecutionContext,
    *,
    current_state: ExperimentState,
    report_ref: ArtifactRef,
    expected_attempt_ref: ArtifactRef,
    expected_input_ref: ArtifactRef,
) -> VerifiedPolicyCompletionAdmission:
    """Fresh-read a report's exact completed composition through the run owner.

    The report declaration selects an occurrence; it cannot establish one. This
    operation reopens that successful occurrence, its fixed projected output and
    private predecessor before reusing the pending owner's source reconciliation.
    Returned facts expose neither predecessor/history access nor publication
    permission. Recognized current evidence and unsupported selections are checked
    without granting access to unrelated hidden state. The caller must separately
    reconcile its current report selection and fixed input values.

    Raises:
        NodeInputPortError: The report, selected occurrence or fixed transition
            cannot be independently established by the actual run owner.
    """
    from polisyos.scientist.orchestration.engine.context import (
        _load_engine_owned_invocation_input_state,
    )
    from polisyos.scientist.orchestration.engine.producer_currentness import (
        _load_invocation_output_state,
    )
    from polisyos.scientist.validation.policy_verified.models import load_verified_policy_report

    try:
        if any(
            ref.manifest_profile_sha256 is None
            for ref in (report_ref, expected_attempt_ref, expected_input_ref)
        ):
            raise NodeInputPortError("completed_composition_selected_profile_missing")
        report = load_verified_policy_report(ctx.store, report_ref)
        binding = report.composition
        if binding is None or (
            current_state.run_id != binding.run_id
            or artifact_ref_identity_key(binding.selected_attempt_ref)
            != artifact_ref_identity_key(expected_attempt_ref)
            or artifact_ref_identity_key(binding.selected_input_ref)
            != artifact_ref_identity_key(expected_input_ref)
        ):
            raise NodeInputPortError("completed_composition_declared_occurrence_mismatch")
        matches = [
            attempt
            for attempt in ctx.run.read_runtime_invocation_attempts()
            if artifact_ref_identity_key(attempt.basis_ref)
            == artifact_ref_identity_key(expected_attempt_ref)
        ]
        if len(matches) != 1:
            raise NodeInputPortError("completed_composition_occurrence_not_owner_linked")
        attempt = matches[0]
        outcome = attempt.outcome
        if (
            attempt.basis.component_id != _COMPLETION_COMPONENT
            or attempt.basis.run_id != binding.run_id
            or artifact_ref_identity_key(attempt.basis.input_state_ref)
            != artifact_ref_identity_key(expected_input_ref)
            or outcome is None
            or outcome.status != "ok"
            or outcome.outcome_state_ref is None
            or not any(
                artifact_ref_identity_key(ref) == artifact_ref_identity_key(report_ref)
                for ref in outcome.output_refs
            )
        ):
            raise NodeInputPortError("completed_composition_occurrence_mismatch")
        projected = _load_engine_owned_invocation_input_state(
            _invocation_context(ctx, attempt, successful=True),
            ExperimentState(run_id=attempt.basis.run_id),
        )
        basis = _basis_from_input(ctx.store, attempt.basis.input_state_ref)
        if (
            projected is None
            or basis is None
            or basis.execution_kind != "producer"
            or not _completion_source_profile(basis.contract)
        ):
            raise NodeInputPortError("completed_composition_input_basis_not_established")
        output = _load_invocation_output_state(ctx, outcome.outcome_state_ref)
        validation_ref = _selected_role_ref(output, "artifacts_index.validation_report_ref")
        selected_reports = tuple(
            _selected_role_ref(output, path) for path in _COMPLETION_OUTPUT_PATHS[:2]
        )
        if (
            any(
                ref is None
                or artifact_ref_identity_key(ref) != artifact_ref_identity_key(report_ref)
                for ref in selected_reports
            )
            or validation_ref is None
            or validation_ref.kind != "scientist.validation_report"
            or validation_ref.manifest_profile_sha256 is None
            or len(outcome.output_refs) != 2
            or {artifact_ref_identity_key(ref) for ref in outcome.output_refs}
            != {
                artifact_ref_identity_key(report_ref),
                artifact_ref_identity_key(validation_ref),
            }
        ):
            raise NodeInputPortError("completed_composition_selected_output_mismatch")
        merged = merge_parallel_outcomes(
            projected,
            {"completion": NodeOutcome(status="ok", state=output)},
            {"completion": list(_COMPLETION_OUTPUT_PATHS)},
        )
        if merged.conflicts or _state_bytes(merged.state) != _state_bytes(output):
            raise NodeInputPortError("completed_composition_output_outside_contract")
        predecessor = _load_invocation_output_state(ctx, basis.predecessor_state_ref)
        selection = NodeInputSelection(
            run_id=attempt.basis.run_id,
            component_id=attempt.basis.component_id,
            contract_id=basis.contract.contract_id,
            node_alias=attempt.basis.node_alias,
            attempt_id=attempt.basis.attempt_id,
            basis_ref=attempt.basis_ref,
            input_state_ref=attempt.basis.input_state_ref,
        )
        facts = _completion_facts(ctx, selection, attempt, predecessor)
        if any(
            actual is None
            or artifact_ref_identity_key(actual) != artifact_ref_identity_key(declared)
            for actual, declared in (
                (facts.body_ref, binding.body_ref),
                (facts.candidate_ref, binding.candidate_ref),
                (facts.phase5_assessment_ref, binding.phase5_assessment_ref),
                (facts.initial_governance_ref, binding.initial_governance_ref),
                (facts.final_governance_ref, binding.final_governance_ref),
            )
        ):
            raise NodeInputPortError("completed_composition_source_binding_mismatch")
        current_evidence, current_unsupported = _completion_evidence(ctx, current_state)
        if (
            current_evidence != facts.evidence
            or current_unsupported != facts.unsupported_requirements
        ):
            reason = "completion_current_evidence_scope_changed"
            facts = replace(
                facts,
                phase5=replace(facts.phase5, status="stale", reason_code=reason),
                unsupported_requirements=tuple(
                    sorted(set(facts.unsupported_requirements) | set(current_unsupported))
                ),
                limitation_codes=tuple(dict.fromkeys((*facts.limitation_codes, reason))),
            )
        return deepcopy(facts)
    except NodeInputPortError:
        raise
    except (AttributeError, KeyError, OSError, RuntimeError, TypeError, ValueError) as exc:
        raise NodeInputPortError("completed_composition_owner_revalidation_failed") from exc


def _selected_refs(state: ExperimentState, contract: NodeInputContract) -> tuple[ArtifactRef, ...]:
    refs = []
    for path in contract.artifact_ref_paths:
        value = _value_at(state, path)
        if value is _MISSING or value is None:
            continue
        try:
            ref = ArtifactRef.model_validate(
                value.model_dump() if isinstance(value, ArtifactRef) else value
            )
        except (TypeError, ValueError) as exc:
            raise NodeInputPortError("node_input_artifact_role_invalid") from exc
        if ref.manifest_profile_sha256 is None:
            raise NodeInputPortError("node_input_selected_profile_missing")
        refs.append(ref)
    return tuple(refs)


def _supports_raw_manifest(store: object) -> TypeGuard[RawManifestBytesReader]:
    return matches_runtime_protocol_definition(store, RawManifestBytesReader)


def _supports_bounded_manifest(store: object) -> TypeGuard[CoreJSONArtifactBoundedManifestReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactBoundedManifestReader)


def _supports_manifest_receipt(
    store: object,
) -> TypeGuard[CoreJSONArtifactBoundedManifestReceiptReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactBoundedManifestReceiptReader)


def _supports_streaming(store: object) -> TypeGuard[CoreJSONArtifactStreamingReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactStreamingReader)


def _supports_bounded_member(store: object) -> TypeGuard[CoreJSONArtifactBoundedMemberReader]:
    return matches_runtime_protocol_definition(store, CoreJSONArtifactBoundedMemberReader)


class _NodeInputStore:
    """Use the existing CAS owner only for selected inputs and this producer's writes.

    No root path, raw owner, inventory or blanket delegation is exposed. The
    selected input's manifest may describe audit lineage; following that lineage
    does not enroll its inaccessible basis or full predecessor for node reads.
    """

    __slots__ = (
        "__definition_sha256",
        "__identity",
        "__lock",
        "__node",
        "__params",
        "__refs",
        "__store",
    )

    def __init__(
        self,
        store: ArtifactStore,
        state: ExperimentState,
        node: Any,
        params: dict[str, Any],
        identity: RunInvocationImplementationIdentity,
        contract: NodeInputContract,
        selection: NodeInputSelection | None = None,
        *,
        definition_sha256: str,
        readable_refs: tuple[ArtifactRef, ...] | None = None,
    ) -> None:
        self.__definition_sha256 = definition_sha256
        self.__store = store
        self.__lock = RLock()
        refs = _selected_refs(state, contract) if readable_refs is None else readable_refs
        if selection is not None:
            refs = (*refs, selection.input_state_ref)
        if any(ref.manifest_profile_sha256 is None for ref in refs):
            raise NodeInputPortError("node_input_selected_profile_missing")
        self.__refs = {artifact_ref_identity_key(ref): ref.model_copy(deep=True) for ref in refs}
        self.__node, self.__params, self.__identity = node, dict(params), identity

    def _current(self) -> None:
        from polisyos.scientist.orchestration.engine.component_identity import (
            _OWNERS,
            capture_engine_component_identity,
        )

        if (
            capture_engine_component_identity(
                self.__node, self.__identity.component_id, self.__params
            )
            != self.__identity
            or (owner := _OWNERS.get(self.__identity.component_id)) is None
            or owner.input_definition_sha256 != self.__definition_sha256
        ):
            raise NodeInputPortError("node_input_contract_source_changed")

    def _resolve(self, selector: Any, profile: str | None = None) -> ArtifactRef:
        from polisyos.core.artifacts.manifest import artifact_reference_parts

        self._current()
        if isinstance(selector, (ArtifactRef, InputRef)):
            artifact_id = selector.artifact_id
            profile = selector.manifest_profile_sha256 if profile is None else profile
        else:
            artifact_id, selected_profile, _ = artifact_reference_parts(selector)
            profile = selected_profile if profile is None else profile
        with self.__lock:
            matches = [
                ref
                for key, ref in self.__refs.items()
                if key[0] == str(artifact_id) and (profile is None or key[3] == profile)
            ]
            if isinstance(selector, ArtifactRef):
                matches = [
                    ref
                    for ref in matches
                    if ref.kind == selector.kind and ref.media_type == selector.media_type
                ]
            if len(matches) != 1:
                raise NodeInputPortError("node_input_artifact_read_not_selected")
            return matches[0].model_copy(deep=True)

    def _remember(self, ref: ArtifactRef) -> ArtifactRef:
        if type(ref) is not ArtifactRef or ref.manifest_profile_sha256 is None:
            raise NodeInputPortError("node_input_output_profile_not_established")
        self._current()
        with self.__lock:
            self.__refs[artifact_ref_identity_key(ref)] = ref.model_copy(deep=True)
        return ref

    def iter_artifact_ids(self) -> list[ArtifactID]:
        """Enumerate only this callback's selected or produced artifacts."""
        self._current()
        with self.__lock:
            return list(
                {
                    str(ref.artifact_id): ref.artifact_id.model_copy(deep=True)
                    for ref in self.__refs.values()
                }.values()
            )

    def has(self, artifact_id: Any) -> bool:
        return self.__store.has(self._resolve(artifact_id))

    def get_bytes(self, artifact_id: Any) -> bytes:
        return self.__store.get_bytes(self._resolve(artifact_id))

    def get_manifest(self, artifact_id: Any) -> ArtifactManifest:
        return self.__store.get_manifest(self._resolve(artifact_id))

    def get_manifest_by_profile(
        self, artifact_id: Any, manifest_profile_sha256: str
    ) -> ArtifactManifest:
        return self.__store.get_manifest(self._resolve(artifact_id, manifest_profile_sha256))

    def verify(self, artifact_id: Any) -> VerificationReport:
        return self.__store.verify(self._resolve(artifact_id))

    def get_raw_manifest_bytes(
        self, artifact_id: Any, *, manifest_profile_sha256: str | None = None
    ) -> bytes:
        selected = self._resolve(artifact_id, manifest_profile_sha256)
        if not _supports_raw_manifest(self.__store):
            raise NotImplementedError("node_input_raw_manifest_read_unsupported")
        return self.__store.get_raw_manifest_bytes(selected)

    def get_raw_manifest_bytes_bounded(
        self,
        artifact_id: Any,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> bytes:
        selected = self._resolve(artifact_id, manifest_profile_sha256)
        if not _supports_bounded_manifest(self.__store):
            raise NotImplementedError("node_input_bounded_manifest_read_unsupported")
        return self.__store.get_raw_manifest_bytes_bounded(
            selected, max_manifest_bytes=max_manifest_bytes
        )

    def get_raw_manifest_bytes_bounded_for_input(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> bytes:
        return self.get_raw_manifest_bytes_bounded(
            self._resolve(input_ref), max_manifest_bytes=max_manifest_bytes
        )

    def read_raw_manifest_bytes_bounded(
        self,
        artifact_id: Any,
        *,
        max_manifest_bytes: int,
        manifest_profile_sha256: str | None = None,
    ) -> ArtifactBoundedManifestRead:
        selected = self._resolve(artifact_id, manifest_profile_sha256)
        if not _supports_manifest_receipt(self.__store):
            raise NotImplementedError("node_input_manifest_receipt_read_unsupported")
        return self.__store.read_raw_manifest_bytes_bounded(
            selected, max_manifest_bytes=max_manifest_bytes
        )

    def read_raw_manifest_bytes_bounded_for_input(
        self, input_ref: InputRef, *, max_manifest_bytes: int
    ) -> ArtifactBoundedManifestRead:
        return self.read_raw_manifest_bytes_bounded(
            self._resolve(input_ref), max_manifest_bytes=max_manifest_bytes
        )

    def open_member(
        self,
        artifact_id: Any,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int | None = None,
        expected_manifest_sha256: str | None = None,
    ) -> AbstractContextManager[CoreJSONArtifactMemberStream]:
        selected = self._resolve(artifact_id)
        if not _supports_streaming(self.__store):
            raise NotImplementedError("node_input_member_read_unsupported")
        return self.__store.open_member(
            selected,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
        )

    def open_member_bounded(
        self,
        artifact_id: Any,
        member: Literal["blob"],
        *,
        max_manifest_bytes: int,
        expected_manifest_sha256: str,
        max_member_bytes: int,
    ) -> CoreJSONArtifactBoundedMemberAttempt:
        selected = self._resolve(artifact_id)
        if not _supports_bounded_member(self.__store):
            raise NotImplementedError("node_input_bounded_member_read_unsupported")
        return self.__store.open_member_bounded(
            selected,
            member,
            max_manifest_bytes=max_manifest_bytes,
            expected_manifest_sha256=expected_manifest_sha256,
            max_member_bytes=max_member_bytes,
        )

    def put_bytes(
        self, data: bytes, opts: ArtifactWriteOptions, *, return_selected_profile: bool = False
    ) -> ArtifactRef:
        self._current()
        return self._remember(self.__store.put_bytes(data, opts, return_selected_profile=True))

    def put_json(
        self,
        obj: object,
        opts: ArtifactWriteOptions,
        canon_spec: CanonSpec | None = None,
        *,
        return_selected_profile: bool = False,
    ) -> ArtifactRef:
        self._current()
        return self._remember(
            self.__store.put_json(obj, opts, canon_spec=canon_spec, return_selected_profile=True)
        )


class _NodeInputRunView:
    """Expose only scoped CAS, trace emission and output tenant coordinates."""

    __slots__ = ("__run", "store")
    _METHODS = frozenset({"emit", "artifact_tenant_context"})

    def __init__(self, run: Any, store: _NodeInputStore) -> None:
        self.__run, self.store = run, store

    def __getattr__(self, name: str) -> Any:
        if name in self._METHODS:
            return getattr(self.__run, name)
        raise AttributeError(name)


def _restricted_context(
    ctx: ExecutionContext, port: _NodeInputPort, selection: NodeInputSelection | None = None
) -> ExecutionContext:
    source_owner = None
    completion_owner = None
    readable_refs: tuple[ArtifactRef, ...] | None = None
    if _phase5_source_profile(port.contract):
        readable_refs = ()
        if selection is not None:
            source_owner = _VerifiedPolicyPhase5AdmissionOwner(
                ctx, selection, port.identity, port.definition_sha256
            )
            admission = source_owner.read()
            readable_refs = tuple(
                ref
                for ref, status in (
                    (admission.body_ref, admission.body_status),
                    (admission.candidate_ref, admission.candidate_status),
                    (admission.governance_ref, admission.governance_status),
                )
                if ref is not None and status == "current"
            )
    if _completion_source_profile(port.contract):
        readable_refs = ()
        if selection is not None:
            completion_owner = _VerifiedPolicyCompletionAdmissionOwner(
                ctx, selection, port.identity, port.definition_sha256
            )
            completion = completion_owner.read()
            readable_refs = tuple(
                ref
                for ref, status in (
                    (completion.body_ref, completion.body.status),
                    (completion.candidate_ref, completion.candidate.status),
                    (completion.phase5_assessment_ref, completion.phase5.status),
                    (completion.final_governance_ref, completion.final_governance.status),
                    *((item.artifact_ref, item.status) for item in completion.evidence),
                )
                if ref is not None and status == "current"
            )
    store = _NodeInputStore(
        ctx.store,
        port.projected,
        port.node,
        port.params,
        port.identity,
        port.contract,
        selection,
        definition_sha256=port.definition_sha256,
        readable_refs=readable_refs,
    )
    from polisyos.scientist.orchestration.engine.context import ExecutionContext as Context

    # A fresh base context is an allowlist. New caller/subclass capabilities do
    # not silently enter this profile when ExecutionContext grows another port.
    fields: dict[str, Any] = {
        "store": store,
        "run": _NodeInputRunView(ctx.run, store),
        "logger": ctx.logger,
        "depth": ctx.depth,
        "_node_input_selection": selection,
        "_verified_policy_phase5_admission_owner": source_owner,
        "_verified_policy_completion_admission_owner": completion_owner,
        "_engine_invocation": ctx._engine_invocation if selection is not None else None,
    }
    return Context(**fields)


def _read_scoped_node_input(ctx: ExecutionContext, state: ExperimentState) -> ExperimentState:
    selection = ctx._node_input_selection
    binding = ctx._engine_invocation
    if (
        type(selection) is not NodeInputSelection
        or binding is None
        or state.run_id != selection.run_id
        or (binding.run_id, binding.attempt_id, binding.basis_ref)
        != (selection.run_id, selection.attempt_id, selection.basis_ref)
    ):
        raise NodeInputPortError("node_input_scoped_attempt_mismatch")
    return ExperimentState.model_validate(
        load_core_json_artifact(ctx.store, selection.input_state_ref)
    )


def read_input_port_basis(ctx: ExecutionContext, state: ExperimentState) -> NodeInputSelection:
    """Bind the unchanged physical input before returning safe attempt coordinates."""
    selection = ctx._node_input_selection
    if type(selection) is not NodeInputSelection:
        raise NodeInputPortError("node_input_port_not_installed")
    persisted = _read_scoped_node_input(ctx, state)
    if _state_bytes(persisted) != _state_bytes(state):
        raise NodeInputPortError("node_input_port_state_changed")
    return replace(
        selection,
        basis_ref=selection.basis_ref.model_copy(deep=True),
        input_state_ref=selection.input_state_ref.model_copy(deep=True),
    )


@dataclass(frozen=True)
class _NodeInputPort:
    """Executor-local state; never place this predecessor-bearing object in context."""

    node: Any
    params: dict[str, Any]
    contract: NodeInputContract
    identity: RunInvocationImplementationIdentity
    definition_sha256: str
    predecessor: ExperimentState
    projected: ExperimentState
    writes: tuple[str, ...]

    def callback_context(self, ctx: ExecutionContext) -> ExecutionContext:
        return _restricted_context(ctx, self)

    def attempt_context(
        self,
        ctx: ExecutionContext,
        *,
        node_alias: str,
        attempt_id: str,
        basis_ref: ArtifactRef,
        input_state_ref: ArtifactRef,
    ) -> ExecutionContext:
        selection = NodeInputSelection(
            run_id=self.projected.run_id,
            component_id=self.contract.component_id,
            contract_id=self.contract.contract_id,
            node_alias=node_alias,
            attempt_id=attempt_id,
            basis_ref=basis_ref.model_copy(deep=True),
            input_state_ref=input_state_ref.model_copy(deep=True),
        )
        return _restricted_context(ctx, self, selection)

    def require_current(self) -> RunInvocationImplementationIdentity:
        from polisyos.scientist.orchestration.engine.component_identity import (
            _OWNERS,
            capture_engine_component_identity,
        )

        current = capture_engine_component_identity(
            self.node, self.contract.component_id, self.params
        )
        if (
            current is None
            or current != self.identity
            or (owner := _OWNERS.get(self.contract.component_id)) is None
            or owner.input_definition_sha256 != self.definition_sha256
        ):
            raise NodeInputPortError("node_input_contract_source_changed")
        return current

    def cache_binding(self) -> dict[str, Any]:
        self.require_current()
        return {
            "contract": self.contract.model_dump(mode="json"),
            "implementation_dependencies_sha256": self.definition_sha256,
            "node_spec_sha256": self.identity.node_spec_sha256,
            "implementation": self.identity.model_dump(mode="json"),
            "projected_state_sha256": "sha256:"
            + hashlib.sha256(_state_bytes(self.projected)).hexdigest(),
        }

    def basis(
        self,
        *,
        predecessor_ref: ArtifactRef,
        attempt_state: ExperimentState,
        node_alias: str,
        attempt_id: str,
        attempt_number: int,
        source_cache_entry_ref: ArtifactRef | None = None,
    ) -> NodeInputBasis:
        self.require_current()
        # Retry may carry only explicitly declared spend; it cannot widen the input.
        if _state_bytes(attempt_state) != _state_bytes(self.projected):
            raise NodeInputPortError("node_input_attempt_projection_changed")
        presence = {}
        for path in self.contract.state_paths:
            value = _value_at(self.predecessor, path)
            presence[path] = (
                "missing" if value is _MISSING else "null" if value is None else "value"
            )
        return NodeInputBasis(
            run_id=attempt_state.run_id,
            node_alias=node_alias,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            contract=self.contract,
            implementation_identity=self.identity,
            implementation_dependencies_sha256=self.definition_sha256,
            bind_params=self.params,
            predecessor_state_ref=predecessor_ref,
            projected_state_sha256="sha256:"
            + hashlib.sha256(_state_bytes(attempt_state)).hexdigest(),
            path_presence=presence,
            execution_kind="cache_replay" if source_cache_entry_ref is not None else "producer",
            source_cache_entry_ref=source_cache_entry_ref,
        )

    def validate_outcome(self, outcome: NodeOutcome) -> None:
        self.require_current()
        if outcome.status == "fail":
            return
        merged = merge_parallel_outcomes(
            self.projected,
            {"port": outcome},
            {"port": list(self.writes)},
            mutation_journals={"port": mutation_journal_for_state(outcome.state)},
        )
        if merged.conflicts or _state_bytes(merged.state) != _state_bytes(outcome.state):
            raise NodeInputPortError("node_input_outcome_outside_contract")

    def merge_outcome(self, outcome: NodeOutcome) -> NodeOutcome:
        self.validate_outcome(outcome)
        if outcome.status != "ok":
            return outcome.model_copy(update={"state": self.predecessor})
        merged = merge_parallel_outcomes(
            self.predecessor,
            {"port": outcome},
            {"port": list(self.writes)},
            mutation_journals={"port": mutation_journal_for_state(outcome.state)},
        )
        if merged.conflicts:
            raise NodeInputPortError("node_input_output_merge_conflict")
        return outcome.model_copy(update={"state": merged.state})


def preflight_node_input_port(
    registered_node: Any, component_id: str, params: dict[str, Any]
) -> None:
    """Admit held definitions and bind keys before any protected semantic callback."""
    from polisyos.scientist.orchestration.engine.component_identity import (
        _preflight_registered_input,
    )

    try:
        contract_json = _preflight_registered_input(registered_node, component_id, params)
        if contract_json is not None:
            contract = NodeInputContract.model_validate_json(contract_json)
            _source_view_profile(contract)
            if contract.component_id != component_id:
                raise ValueError("node_input_contract_component_mismatch")
            return
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        raise NodeInputPortError("node_input_contract_source_not_established") from exc
    # Unprotected legacy discovery retains its historical spec read. Merely
    # offering an unknown input contract cannot admit a bind or producer call.
    spec = registered_node.spec
    if isinstance(spec, InputAwareNodeSpec) or hasattr(spec, "input_contract"):
        raise NodeInputPortError("node_input_contract_source_not_established")


def admit_node_input_port(
    node: Any, state: ExperimentState, params: dict[str, Any]
) -> _NodeInputPort | None:
    """Select a physical input only for an independently held builtin contract."""
    from polisyos.scientist.orchestration.engine.component_identity import (
        _OWNERS,
        _require_input_definition,
        capture_engine_component_identity,
    )

    try:
        definition_owner = _require_input_definition(node, params)
    except (AttributeError, KeyError, OSError, TypeError, ValueError) as exc:
        raise NodeInputPortError("node_input_contract_source_not_established") from exc
    spec = node.spec
    metadata = getattr(spec, "metadata", None)
    component_id = str(getattr(metadata, "component_id", ""))
    expected_owner = _OWNERS.get(component_id)
    if not isinstance(spec, InputAwareNodeSpec):
        protected_type = any(
            owner.node_type is type(node) and owner.input_contract_sha256 is not None
            for owner in _OWNERS.values()
        )
        if (
            protected_type
            or (expected_owner is not None and expected_owner.input_contract_sha256 is not None)
            or hasattr(spec, "input_contract")
        ):
            raise NodeInputPortError("node_input_contract_unsupported")
        return None
    try:
        contract = NodeInputContract.model_validate_json(spec.input_contract.model_dump_json())
    except (TypeError, ValueError) as exc:
        raise NodeInputPortError("node_input_contract_unsupported") from exc
    _source_view_profile(contract)
    if (
        _completion_source_profile(contract)
        and tuple(spec.state_writes) != _COMPLETION_OUTPUT_PATHS
    ):
        raise NodeInputPortError("node_input_completion_writes_unsupported")
    if set(params) - set(contract.bind_param_keys):
        raise NodeInputPortError("node_input_bind_params_outside_contract")
    identity = capture_engine_component_identity(node, str(spec.metadata.component_id), params)
    if (
        identity is None
        or definition_owner is None
        or definition_owner.input_definition_sha256 is None
    ):
        raise NodeInputPortError("node_input_contract_source_not_established")
    predecessor = _completed_producer_value(state)
    projected = _project(predecessor, contract)
    _selected_refs(projected, contract)
    return _NodeInputPort(
        node=node,
        params=dict(params),
        contract=contract,
        identity=identity,
        definition_sha256=definition_owner.input_definition_sha256,
        predecessor=predecessor,
        projected=projected,
        writes=tuple(spec.state_writes),
    )


def validate_node_input_basis(
    store: ArtifactStore, started: RunInvocationStarted, projected: ExperimentState
) -> None:
    """Reconcile a selected input basis; never return its hidden predecessor.

    Legacy inputs remain compatible. A protected input-aware component cannot
    downgrade to that legacy path by removing the basis edge.
    """
    from polisyos.scientist.orchestration.engine.component_identity import (
        _OWNERS,
        matches_engine_component_identity,
    )

    manifest = store.get_manifest(started.input_state_ref)
    edges = [edge for edge in manifest.inputs if edge.role == _INPUT_BASIS_ROLE]
    owner = _OWNERS.get(started.component_id)
    requires_port = owner is not None and owner.input_contract_sha256 is not None
    if not edges:
        if requires_port:
            raise NodeInputPortError("node_input_basis_missing")
        return
    if len(edges) != 1 or len(manifest.inputs) != 1 or not edges[0].manifest_profile_sha256:
        raise NodeInputPortError("node_input_basis_ambiguous")
    edge = edges[0]
    basis_ref = ArtifactRef(
        artifact_id=edge.artifact_id,
        kind=_INPUT_BASIS_KIND,
        media_type="application/json",
        manifest_profile_sha256=edge.manifest_profile_sha256,
    )
    basis_manifest = store.get_manifest(basis_ref)
    if basis_manifest.kind != _INPUT_BASIS_KIND or basis_manifest.artifact_schema != SchemaInfo(
        name=_INPUT_BASIS_SCHEMA, version="1.0"
    ):
        raise NodeInputPortError("node_input_basis_schema_invalid")
    basis = NodeInputBasis.model_validate(load_core_json_artifact(store, basis_ref))
    if not store.verify(started.input_state_ref).ok:
        raise NodeInputPortError("node_input_state_integrity_invalid")
    if (
        (
            basis.run_id,
            basis.node_alias,
            basis.attempt_id,
            basis.attempt_number,
            basis.contract.component_id,
        )
        != (
            started.run_id,
            started.node_alias,
            started.attempt_id,
            started.attempt_number,
            started.component_id,
        )
        or basis.implementation_identity != started.implementation_identity
        or owner is None
        or basis.implementation_dependencies_sha256 != owner.input_definition_sha256
        or owner.input_contract_sha256
        != hashlib.sha256(
            to_canonical_bytes(basis.contract.model_dump(mode="json"), _CANON)
        ).hexdigest()
        or not matches_engine_component_identity(
            basis.implementation_identity, started.component_id, basis.bind_params
        )
        or basis.projected_state_sha256
        != "sha256:" + hashlib.sha256(_state_bytes(projected)).hexdigest()
    ):
        raise NodeInputPortError("node_input_basis_attempt_mismatch")
    if basis_manifest.inputs != input_basis_options(basis).inputs:
        raise NodeInputPortError("node_input_predecessor_lineage_mismatch")
    predecessor_manifest = store.get_manifest(basis.predecessor_state_ref)
    if (
        predecessor_manifest.kind != "scientist.experiment_state"
        or predecessor_manifest.artifact_schema is None
        or predecessor_manifest.artifact_schema.name
        != "polisyos.scientist.orchestration.engine.ExperimentState"
    ):
        raise NodeInputPortError("node_input_predecessor_contract_invalid")
    predecessor = ExperimentState.model_validate(
        load_core_json_artifact(store, basis.predecessor_state_ref)
    )
    expected = _project(predecessor, basis.contract)
    presence = {}
    for path in basis.contract.state_paths:
        value = _value_at(predecessor, path)
        presence[path] = "missing" if value is _MISSING else "null" if value is None else "value"
    if (
        predecessor.run_id != basis.run_id
        or predecessor_manifest.artifact_schema.version != predecessor.schema_version
        or basis.path_presence != presence
        or _state_bytes(expected) != _state_bytes(projected)
    ):
        raise NodeInputPortError("node_input_basis_projection_mismatch")
