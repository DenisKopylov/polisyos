"""Read-only preflight selection for a same-source candidate experiment reuse.

This module selects already-computed candidate input and N5 artifacts from the
latest verified predecessor. It does not authorize a new action, grant source
rights, establish source currentness, spend budget, fetch data, or write state.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.artifacts import ArtifactRef
from polisyos.pdc import OperationClass, OperationContract, OperationInvocationRecord, PortSpec
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateExperimentTerminalHistory,
    ResolvedAcquisitionEvaluation,
    _candidate_model_values_same,
    _candidate_ref_same,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    POLICY_KIND,
    CandidateUnpricedPolicyScope,
)
from polisyos.runtime.quality.agent_action_authority import (
    CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND as CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
)
from polisyos.runtime.quality.agent_action_authority import (
    AgentActionIntent,
    agent_action_content_hash,
)

if TYPE_CHECKING:
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedCandidateExperimentOrigin
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _CurrentCandidateExperimentActionContext,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import CandidateAcquisitionSource
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourcePaths,
        SubstrateRegistry,
    )


_SHA256_PATTERN = r"^sha256:[0-9a-f]{64}$"
_CANDIDATE_ACTION_KIND = "runtime_quality.acquisition_candidate_action_receipt"
_TERMINAL_KIND = "runtime_quality.acquisition_route_loop_receipt"
_SOURCE_KIND = "runtime.quality.candidate_acquisition_source"
_N5_INPUT_KIND = "runtime.quality.candidate_simulation_n5_input"
_N5_EXECUTION_KIND = "runtime.quality.candidate_simulation_execution"
_N5_RESULT_KIND = "polisyos.runtime.joint_simulation_result"


@dataclass(frozen=True, slots=True)
class CandidateExperimentReuseSelection:
    """Exact prior artifacts selected for a possible same-source continuation.

    This read result is not a reuse permit or current authority. A later action
    must have its own typed receipt and independently verified authorization.
    """

    tenant_id: str
    cell_id: str
    run_id: str
    route_id: str
    current_action_generation: int
    current_action_phase_ref: ArtifactRef
    predecessor_terminal_ref: ArtifactRef
    predecessor_action_ref: ArtifactRef
    source_ref: ArtifactRef
    source: CandidateAcquisitionSource
    n5_input_ref: ArtifactRef
    n5_execution_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    catalog_source_selection_basis: Literal[
        "legacy_default_candidate_only", "explicit_path_candidate_only"
    ]
    catalog_source_content_ref: str | None
    authority_provision_content_sha256: str
    source_currentness: Literal["source_currentness_not_established"] = (
        "source_currentness_not_established"
    )


class CandidateExperimentReuseActionRequest(BaseModel):
    """Ingress selectors for requesting a distinct candidate-reuse PA2 decision.

    These selectors can be checked against the latest persisted predecessor
    before a worker lease or executing phase exists. They are not a reuse
    result, permission, or source-currentness claim.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    route_id: str = Field(pattern=_SHA256_PATTERN)
    predecessor_terminal_ref: ArtifactRef
    predecessor_action_ref: ArtifactRef
    source_ref: ArtifactRef
    n5_input_ref: ArtifactRef
    n5_execution_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    policy_ref: ArtifactRef
    idempotency_key: str = Field(min_length=1, max_length=200, strict=True)
    human_decision_record_ref: str | None = Field(default=None, pattern=_SHA256_PATTERN)

    @model_validator(mode="after")
    def _require_selected_profiles(self) -> CandidateExperimentReuseActionRequest:
        for name, kind in (
            ("predecessor_terminal_ref", _TERMINAL_KIND),
            ("predecessor_action_ref", _CANDIDATE_ACTION_KIND),
            ("source_ref", _SOURCE_KIND),
            ("n5_input_ref", _N5_INPUT_KIND),
            ("n5_execution_ref", _N5_EXECUTION_KIND),
            ("n5_result_ref", _N5_RESULT_KIND),
            ("policy_ref", POLICY_KIND),
        ):
            ref = getattr(self, name)
            if (
                type(ref) is not ArtifactRef
                or set(type(ref).model_fields) != set(ArtifactRef.model_fields)
                or set(vars(ref)) != set(ArtifactRef.model_fields)
                or ref.__pydantic_extra__
                or ref.kind != kind
                or ref.media_type != "application/json"
                or ref.manifest_profile_sha256 is None
            ):
                raise ValueError("candidate_experiment_reuse_selected_profile_invalid:" + name)
        if (
            self.idempotency_key != self.idempotency_key.strip()
            or self.route_id != self.route_id.strip()
        ):
            raise ValueError("candidate_experiment_reuse_request_identity_invalid")
        return self


def _candidate_experiment_reuse_job_id(
    *,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    source_job_id: str,
    source_payload_ref: str,
    request_content_hash: str,
    route_id: str,
    predecessor_action_generation: int,
    action_generation: int,
    policy_ref: ArtifactRef,
    policy_scope: CandidateUnpricedPolicyScope,
    request: CandidateExperimentReuseActionRequest,
    authority_provision_content_sha256: str,
    catalog_source_selection_basis: Literal[
        "legacy_default_candidate_only", "explicit_path_candidate_only"
    ],
    catalog_source_content_ref: str | None,
) -> str:
    """Derive an idempotent job identity from the exact ingress request."""
    binding = agent_action_content_hash(
        {
            "action_kind": CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
            "tenant_id": tenant_id,
            "cell_id": cell_id,
            "run_id": run_id,
            "source_job_id": source_job_id,
            "source_payload_ref": source_payload_ref,
            "request_content_hash": request_content_hash,
            "route_id": route_id,
            "predecessor_action_generation": predecessor_action_generation,
            "action_generation": action_generation,
            "policy_ref": policy_ref.model_dump(mode="json"),
            "policy_scope": policy_scope.model_dump(mode="json"),
            "authority_provision_content_sha256": authority_provision_content_sha256,
            "catalog_source_selection_basis": catalog_source_selection_basis,
            "catalog_source_content_ref": catalog_source_content_ref,
            # The decision payload still binds the full request. Optional
            # human-decision evidence does not change the stable job identity.
            "request": request.model_dump(mode="json", exclude={"human_decision_record_ref"}),
        }
    )
    return "candidate-experiment-reuse-" + binding.removeprefix("sha256:")


class CandidateExperimentReuseActionSelection(BaseModel):
    """Canonical ingress selection before the worker phase and lease exist.

    The owner resolves the expected predecessor fields from persisted history;
    validation rejects request pins that do not match that owner selection.
    A later worker must independently resolve the executing phase and lease.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    tenant_id: str = Field(min_length=1, strict=True)
    cell_id: str = Field(min_length=1, strict=True)
    run_id: str = Field(min_length=1, strict=True)
    source_job_id: str = Field(min_length=1, strict=True)
    source_payload_ref: str = Field(pattern=_SHA256_PATTERN)
    request_content_hash: str = Field(pattern=_SHA256_PATTERN)
    route_id: str = Field(pattern=_SHA256_PATTERN)
    predecessor_action_generation: int = Field(ge=1, strict=True)
    action_generation: int = Field(ge=2, strict=True)
    action_job_id: str = Field(pattern=r"^candidate-experiment-reuse-[0-9a-f]{64}$")
    predecessor_terminal_ref: ArtifactRef
    predecessor_action_ref: ArtifactRef
    source_ref: ArtifactRef
    n5_input_ref: ArtifactRef
    n5_execution_ref: ArtifactRef
    n5_result_ref: ArtifactRef
    policy_ref: ArtifactRef
    policy_scope: CandidateUnpricedPolicyScope
    catalog_source_selection_basis: Literal[
        "legacy_default_candidate_only", "explicit_path_candidate_only"
    ]
    catalog_source_content_ref: str | None
    authority_provision_content_sha256: str = Field(pattern=_SHA256_PATTERN)
    source_currentness: Literal["source_currentness_not_established"] = (
        "source_currentness_not_established"
    )
    request: CandidateExperimentReuseActionRequest

    @model_validator(mode="after")
    def _bind_request_to_owner_selection(self) -> CandidateExperimentReuseActionSelection:
        if any(
            value != value.strip()
            for value in (self.tenant_id, self.cell_id, self.run_id, self.source_job_id)
        ):
            raise ValueError("candidate_experiment_reuse_selection_identity_invalid")
        if self.action_generation != self.predecessor_action_generation + 1:
            raise ValueError("candidate_experiment_reuse_generation_identity_mismatch")
        if (
            (self.tenant_id, self.cell_id, self.run_id)
            != (self.policy_scope.tenant_id, self.policy_scope.cell_id, self.policy_scope.run_id)
            or self.source_job_id != self.policy_scope.source_job_id
            or self.route_id != self.request.route_id
            or self.request.policy_ref != self.policy_ref
            or self.request.predecessor_terminal_ref != self.predecessor_terminal_ref
            or self.request.predecessor_action_ref != self.predecessor_action_ref
            or self.request.source_ref != self.source_ref
            or self.request.n5_input_ref != self.n5_input_ref
            or self.request.n5_execution_ref != self.n5_execution_ref
            or self.request.n5_result_ref != self.n5_result_ref
        ):
            raise ValueError("candidate_experiment_reuse_request_selection_mismatch")
        if (
            self.catalog_source_selection_basis == "legacy_default_candidate_only"
            and self.catalog_source_content_ref is not None
        ) or (
            self.catalog_source_selection_basis == "explicit_path_candidate_only"
            and (
                not isinstance(self.catalog_source_content_ref, str)
                or not self.catalog_source_content_ref.startswith("catalog_read_source_content://")
            )
        ):
            raise ValueError("candidate_experiment_reuse_catalog_identity_invalid")
        expected_job_id = _candidate_experiment_reuse_job_id(
            tenant_id=self.tenant_id,
            cell_id=self.cell_id,
            run_id=self.run_id,
            source_job_id=self.source_job_id,
            source_payload_ref=self.source_payload_ref,
            request_content_hash=self.request_content_hash,
            route_id=self.route_id,
            predecessor_action_generation=self.predecessor_action_generation,
            action_generation=self.action_generation,
            policy_ref=self.policy_ref,
            policy_scope=self.policy_scope,
            request=self.request,
            authority_provision_content_sha256=self.authority_provision_content_sha256,
            catalog_source_selection_basis=self.catalog_source_selection_basis,
            catalog_source_content_ref=self.catalog_source_content_ref,
        )
        if self.action_job_id != expected_job_id:
            raise ValueError("candidate_experiment_reuse_job_identity_mismatch")
        return self


def candidate_experiment_reuse_action_tuple(
    selection: CandidateExperimentReuseActionSelection,
) -> tuple[OperationContract, OperationInvocationRecord, AgentActionIntent]:
    """Bind a no-fetch candidate-only proposal to exact prior evidence and policy.

    The tuple only requests PA2 evaluation. It does not assert that the
    predecessor is current, numerically adequate, permitted, or reusable. The
    worker must reopen and verify the predecessor evaluation before producing
    any reuse outcome; a fresh signed decision remains an external input.
    """
    if type(selection) is not CandidateExperimentReuseActionSelection:
        raise ValueError("candidate_experiment_reuse_action_selection_untyped")
    selection = CandidateExperimentReuseActionSelection.model_validate(
        selection.model_dump(mode="python")
    )
    selected_ports = [
        PortSpec(
            port_id=f"port-{name.replace('_', '-')}",
            direction="consumes",
            port_type=ref.kind,
            claim_shape={
                "artifact_kind": ref.kind,
                "purpose": "exact_selected_candidate_evidence",
            },
            multiplicity={"min": 1, "max": 1},
            constraints={
                "manifest_profile_required": True,
                "artifact_ref": ref.model_dump(mode="json"),
            },
        )
        for name, ref in (
            ("predecessor_terminal", selection.predecessor_terminal_ref),
            ("predecessor_action", selection.predecessor_action_ref),
            ("source", selection.source_ref),
            ("n5_input", selection.n5_input_ref),
            ("n5_execution", selection.n5_execution_ref),
            ("n5_result", selection.n5_result_ref),
            ("policy", selection.policy_ref),
        )
    ]
    operation = OperationContract(
        operation_id=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
        operation_version="v1",
        operation_class=OperationClass.BIND,
        consumes=selected_ports,
        produces=[],
        formal_preconditions=[
            {"id": "latest_predecessor_terminal_replayed", "owner_replay_required": True},
            {"id": "selected_n5_evaluation_replayed", "owner_replay_required": True},
            {"id": "same_basis_required_for_retention", "owner_recompute_required": True},
            {"id": "fresh_signed_reuse_action_permission", "owner_decision_required": True},
        ],
        allowed_internal_execution=[],
        implementation_refs=[
            {"module": __name__, "symbol": "candidate_experiment_reuse_action_tuple"}
        ],
        cost_model={
            "source_fetch": "none",
            "new_n5_invocations": 0,
            "monetary_cost": "not_established",
        },
        authority_transform={"kind": "preserves"},
        failure_modes=[
            "authority_refused",
            "predecessor_changed",
            "predecessor_n5_not_established",
            "reuse_equivalence_not_established",
        ],
        repair_options=[OperationClass.ESCALATE],
    )
    parameters = {
        "tenant_id": selection.tenant_id,
        "cell_id": selection.cell_id,
        "run_id": selection.run_id,
        "source_job_id": selection.source_job_id,
        "source_payload_ref": selection.source_payload_ref,
        "request_content_hash": selection.request_content_hash,
        "route_id": selection.route_id,
        "action_job_id": selection.action_job_id,
        "predecessor_action_generation": selection.predecessor_action_generation,
        "action_generation": selection.action_generation,
        "policy_ref": selection.policy_ref.model_dump(mode="json"),
        "policy_scope": selection.policy_scope.model_dump(mode="json"),
        "catalog_source_selection_basis": selection.catalog_source_selection_basis,
        "catalog_source_content_ref": selection.catalog_source_content_ref,
        "authority_provision_content_sha256": selection.authority_provision_content_sha256,
        "source_currentness": selection.source_currentness,
        # Human-decision proof lookup is part of the authenticated HTTP
        # request, not the semantic action PA2 authorizes. The frozen
        # selection retains the exact body field for that proof lookup.
        "request": selection.request.model_dump(mode="json", exclude={"human_decision_record_ref"}),
        "effect": {
            "purpose": "candidate_only",
            "source_fetch": "none",
            "new_n5_invocations": 0,
            "source_currentness": "source_currentness_not_established",
            "observed_admission": False,
            "publication_authority": False,
        },
    }
    invocation = OperationInvocationRecord(
        invocation_id="candidate-experiment-reuse."
        + agent_action_content_hash(parameters).removeprefix("sha256:"),
        operation_id=operation.operation_id,
        operation_version=operation.operation_version,
        workspace_id=selection.run_id,
        cycle_index=selection.policy_scope.source_cycle_index,
        selected_by={"producer": "runtime.candidate_experiment_reuse"},
        selection_rationale_ref=selection.route_id,
        # The PDC artifact envelope uses a different ArtifactRef ABI and needs
        # the canonical byte/content binding to translate refs safely. Keep
        # core CAS refs in the immutable request parameters/ports; do not
        # invent PDC content hashes here.
        input_artifacts=[],
        parameters=parameters,
        internal_trace={"phase": "candidate_experiment_reuse_decision_only"},
        tool_calls=[],
        human_requests=[],
        output_artifacts=[],
        applicability_result="not_established",
        budget_delta={},
        status="started",
    )
    return (
        operation,
        invocation,
        AgentActionIntent(action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND),
    )


def _selected_predecessor_evaluation(
    history: CandidateExperimentTerminalHistory,
) -> ResolvedAcquisitionEvaluation:
    """Select only the N5 occurrence explicitly bound by a verified terminal."""
    from polisyos.runtime.quality.acquisition_evaluation import (
        AcquisitionSelectedEvaluation,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )

    if type(history) is not CandidateExperimentTerminalHistory:
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified")
    terminal = history.terminal
    if type(terminal) is AcquisitionCandidateExperimentTerminalReceipt:
        if terminal.terminal_outcome == "candidate_reentry_completed":
            evaluation = history.reentry_evaluation
        elif terminal.terminal_outcome == "candidate_evaluation_retained":
            evaluation = history.evaluation
        else:
            raise ValueError("candidate_experiment_reuse_predecessor_n5_not_selected")
    elif type(terminal) is AcquisitionCandidateExperimentTerminalReceiptV2:
        evaluation = _selected_reused_predecessor_evaluation(history)
    else:
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified")
    if (
        type(evaluation) is not ResolvedAcquisitionEvaluation
        or type(evaluation.selected) is not AcquisitionSelectedEvaluation
        or terminal.selected_basis_ref is None
        or terminal.selected_evaluation is None
        or terminal.selected_evaluation_witness_ref is None
        or not _candidate_model_values_same(
            terminal.selected_evaluation,
            evaluation.selected.model_copy(update={"basis_ref": terminal.selected_basis_ref}),
        )
        or terminal.selected_evaluation_witness_ref != evaluation.selected.n5_execution_ref
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_n5_binding_mismatch")
    return evaluation


def _selected_reused_predecessor_evaluation(
    history: CandidateExperimentTerminalHistory,
) -> ResolvedAcquisitionEvaluation:
    """Require a verified V2 retention to preserve its immediate predecessor's N5."""
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        AcquisitionCandidateExperimentTerminalReceiptV2,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.candidate_experiment_reuse_occurrence import (
        CandidateExperimentReuseOccurrence,
    )

    terminal = history.terminal
    occurrence = history.reuse_occurrence
    origin = history.origin
    if (
        type(terminal) is not AcquisitionCandidateExperimentTerminalReceiptV2
        or terminal.terminal_outcome != "candidate_evaluation_retained"
        or type(occurrence) is not CandidateExperimentReuseOccurrence
        or occurrence.source_currentness != "source_currentness_not_established"
        or occurrence.observed_data_authority is not False
        or occurrence.publication_authority is not False
        or type(origin) is not VerifiedCandidateExperimentOrigin
        or len(history.phase_chain) != 3
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified")
    prefix = origin.candidate_terminal_history_chain
    if (
        type(prefix) is not tuple
        or not prefix
        or type(terminal.reuse_occurrence_ref) is not ArtifactRef
        or type(history.reuse_occurrence_ref) is not ArtifactRef
        or not _candidate_ref_same(terminal.reuse_occurrence_ref, history.reuse_occurrence_ref)
        or history.reuse_occurrence_ref.manifest_profile_sha256 is None
        or history.reuse_occurrence_ref.kind
        != "runtime_quality.candidate_experiment_reuse_occurrence"
        or history.reuse_occurrence_ref.media_type != "application/json"
        or str(terminal.reuse_occurrence_ref.artifact_id) not in terminal.owner_receipt_refs
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified")

    predecessor = prefix[-1]
    if type(predecessor) is not CandidateExperimentTerminalHistory:
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified")
    selection = occurrence.selection
    if type(selection) is not CandidateExperimentReuseActionSelection:
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified")
    try:
        selection = CandidateExperimentReuseActionSelection.model_validate(
            selection.model_dump(mode="python")
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reuse_predecessor_history_unverified") from exc
    predecessor_terminal = predecessor.terminal
    current_head = history.head
    predecessor_head = predecessor.head
    executing = history.phase_chain[-2]
    if (
        type(history.terminal_ref) is not ArtifactRef
        or history.terminal_ref.kind != _TERMINAL_KIND
        or history.terminal_ref.media_type != "application/json"
        or history.terminal_ref.manifest_profile_sha256 is None
        or str(history.terminal_ref.artifact_id) != current_head.receipt_ref
        or history.terminal_ref.manifest_profile_sha256
        != current_head.receipt_manifest_profile_sha256
        or selection.tenant_id != current_head.tenant_id
        or selection.cell_id != current_head.cell_id
        or selection.run_id != current_head.run_id
        or selection.source_job_id != current_head.source_job_id
        or selection.route_id != current_head.route_id
        or selection.source_payload_ref != terminal.source_payload_ref
        or selection.request_content_hash != terminal.request_content_hash
        or (
            selection.tenant_id,
            selection.cell_id,
            selection.run_id,
            selection.source_job_id,
            selection.route_id,
            selection.source_payload_ref,
            selection.request_content_hash,
            selection.action_generation,
            selection.action_job_id,
        )
        != (
            terminal.tenant_id,
            terminal.cell_id,
            terminal.run_id,
            terminal.source_job_id,
            terminal.route_id,
            terminal.source_payload_ref,
            terminal.request_content_hash,
            terminal.action_generation,
            terminal.job_id,
        )
        or selection.action_job_id != current_head.job_id
        or selection.action_generation != current_head.action_generation
        or selection.action_generation != selection.predecessor_action_generation + 1
        or selection.predecessor_action_generation != predecessor_head.action_generation
        or terminal.job_id != current_head.job_id
        or terminal.action_generation != current_head.action_generation
        or current_head.receipt_phase != "terminal"
        or predecessor_head.receipt_phase != "terminal"
        or predecessor_terminal.action_generation != predecessor_head.action_generation
        or str(predecessor.terminal_ref.artifact_id) != predecessor_head.receipt_ref
        or predecessor.terminal_ref.manifest_profile_sha256
        != predecessor_head.receipt_manifest_profile_sha256
        # The action occurrence links the earlier terminal; the current
        # terminal's phase predecessor is this action's own executing receipt.
        or type(executing.receipt) is not AcquisitionCandidateExperimentPhaseReceipt
        or executing.receipt.receipt_phase != "executing"
        or executing.receipt.job_id != current_head.job_id
        or executing.receipt.action_generation != current_head.action_generation
        or executing.receipt_ref != str(occurrence.executing_phase_ref.artifact_id)
        or terminal.predecessor_receipt_ref != executing.receipt_ref
        or current_head.predecessor_receipt_ref != executing.receipt_ref
        or not _candidate_ref_same(
            executing.receipt.authority_decision_ref, occurrence.pa2_decision_ref
        )
        or not _candidate_ref_same(
            terminal.candidate_action_ref, predecessor_terminal.candidate_action_ref
        )
        or not _candidate_ref_same(selection.predecessor_terminal_ref, predecessor.terminal_ref)
        or not _candidate_ref_same(
            selection.predecessor_action_ref, predecessor_terminal.candidate_action_ref
        )
        or not _candidate_ref_same(selection.source_ref, predecessor.action.candidate_source_ref)
        or not _candidate_ref_same(selection.source_ref, history.action.candidate_source_ref)
        or not _candidate_ref_same(selection.policy_ref, terminal.policy_ref)
        or not _candidate_ref_same(selection.policy_ref, predecessor_terminal.policy_ref)
        or not _candidate_model_values_same(selection.policy_scope, terminal.policy_scope)
        or not _candidate_model_values_same(
            selection.policy_scope, predecessor_terminal.policy_scope
        )
        or (origin.tenant_id, origin.cell_id, origin.run_id, origin.source_job_id)
        != (
            current_head.tenant_id,
            current_head.cell_id,
            current_head.run_id,
            current_head.source_job_id,
        )
        or origin.route_id != current_head.route_id
        or origin.source_payload_ref != terminal.source_payload_ref
        or origin.request_content_hash != terminal.request_content_hash
        or not _candidate_ref_same(origin.policy_ref, terminal.policy_ref)
        or not _candidate_model_values_same(origin.policy_scope, terminal.policy_scope)
        or origin.current_terminal_history is not predecessor
        or origin.current_action_head not in (None, predecessor_head)
        or history.action.action_job_id != predecessor.action.action_job_id
        or history.action.action_generation != predecessor.action.action_generation
        or history.source.job_id != history.action.action_job_id
        or history.action.source_job_id != current_head.source_job_id
        or predecessor.action.source_job_id != predecessor_head.source_job_id
        or (
            history.source.tenant_id,
            history.source.cell_id,
            history.source.run_id,
            history.source.job_id,
            history.source.route_id,
        )
        != (
            predecessor.source.tenant_id,
            predecessor.source.cell_id,
            predecessor.source.run_id,
            predecessor.source.job_id,
            predecessor.source.route_id,
        )
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_occurrence_binding_mismatch")

    predecessor_evaluation = _selected_predecessor_evaluation(predecessor)
    evaluation = history.evaluation
    if (
        type(evaluation) is not ResolvedAcquisitionEvaluation
        or type(evaluation.selected) is not type(predecessor_evaluation.selected)
        or evaluation.selected.candidate_id != predecessor_evaluation.selected.candidate_id
        or evaluation.selected.candidate_content_hash
        != predecessor_evaluation.selected.candidate_content_hash
        or evaluation.selected.design_problem_ref
        != predecessor_evaluation.selected.design_problem_ref
        or evaluation.selected.world_model_record_hash
        != predecessor_evaluation.selected.world_model_record_hash
        or evaluation.selected.evaluation_job_id
        != predecessor_evaluation.selected.evaluation_job_id
        or evaluation.selected.evaluation_run_id
        != predecessor_evaluation.selected.evaluation_run_id
        or evaluation.selected.generation_run_id
        != predecessor_evaluation.selected.generation_run_id
        or evaluation.selected.cycle_index != predecessor_evaluation.selected.cycle_index
        or not _candidate_ref_same(
            selection.n5_input_ref, predecessor_evaluation.selected.n5_input_ref
        )
        or not _candidate_ref_same(
            selection.n5_execution_ref, predecessor_evaluation.selected.n5_execution_ref
        )
        or not _candidate_ref_same(
            selection.n5_result_ref, predecessor_evaluation.selected.n5_result_ref
        )
        or not _candidate_ref_same(
            evaluation.selected.n5_input_ref, predecessor_evaluation.selected.n5_input_ref
        )
        or not _candidate_ref_same(
            evaluation.selected.n5_execution_ref, predecessor_evaluation.selected.n5_execution_ref
        )
        or not _candidate_ref_same(
            evaluation.selected.n5_result_ref, predecessor_evaluation.selected.n5_result_ref
        )
        or not _candidate_ref_same(
            evaluation.selected.n4_source_ref, predecessor_evaluation.selected.n4_source_ref
        )
        or not _candidate_ref_same(
            evaluation.selected.context_job_ref, predecessor_evaluation.selected.context_job_ref
        )
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_n5_binding_mismatch")
    return evaluation


def _reopen_current_reuse_catalog_context(
    *,
    control_service: ControlPlaneService,
    substrate_registry: SubstrateRegistry,
) -> CatalogServingSourcePaths:
    """Reopen the exact Catalog serving context and its independent registry fence."""
    from polisyos.runtime.quality.substrate_registry import (
        CatalogServingSourcePaths,
        current_catalog_serving_source,
        require_catalog_serving_source_unchanged,
        require_catalog_source_registry_binding,
    )

    catalog_source = control_service.catalog_serving_source
    if (
        type(catalog_source) is not CatalogServingSourcePaths
        or catalog_source.repo_root != Path(control_service._repo_root).resolve()
        or current_catalog_serving_source() is not catalog_source
    ):
        raise ValueError("candidate_experiment_reuse_catalog_scope_not_established")
    require_catalog_serving_source_unchanged(catalog_source)
    require_catalog_source_registry_binding(
        catalog_source.repo_root, substrate_registry, catalog_source
    )
    if current_catalog_serving_source() is not catalog_source:
        raise ValueError("candidate_experiment_reuse_catalog_scope_changed")
    require_catalog_serving_source_unchanged(catalog_source)
    require_catalog_source_registry_binding(
        catalog_source.repo_root, substrate_registry, catalog_source
    )
    return catalog_source


def _reopen_current_reuse_wdi_source(
    *,
    control_service: ControlPlaneService,
    source_ref: ArtifactRef,
    expected_source: CandidateAcquisitionSource,
    expected_bridge: AcquisitionWorldGrowthBridge | None = None,
) -> tuple[WorldBankWDIAcquisitionExecutionPort, CandidateAcquisitionSource]:
    """Reopen the production WDI provision and exact historical source owner.

    The execution port is checked as the already-composed typed production
    owner. A fresh port built from the canonical provision is used only to
    replay authority and selected source bytes; this function never calls its
    transport or reserves an attempt.
    """
    from polisyos.data_forge.read_api import catalog
    from polisyos.runtime.http.services.acquisition_action_service import (
        AcquisitionActionService,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
        build_production_world_bank_wdi_execution_port,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionWorldGrowthBridge,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )

    action_service = getattr(
        getattr(control_service, "_acquisition_job_handler", None), "__self__", None
    )
    live_port = getattr(action_service, "_production_execution_port", None)
    if (
        type(action_service) is not AcquisitionActionService
        or action_service.control_service is not control_service
        or type(live_port) is not WorldBankWDIAcquisitionExecutionPort
        or action_service._execution_port is not live_port
        or live_port._artifact_store is not control_service._artifact_store
        or type(live_port._authority) is not catalog.CanonicalAcquisitionAuthority
    ):
        raise ValueError("candidate_experiment_reuse_wdi_authority_not_composed")
    if expected_bridge is not None and (
        type(expected_bridge) is not AcquisitionWorldGrowthBridge
        or live_port._world_growth_bridge is not expected_bridge
        or expected_bridge._source_control_service is not control_service
        or expected_bridge.artifact_store is not control_service._artifact_store
        or expected_bridge.authority is not live_port._authority
    ):
        raise ValueError("candidate_experiment_reuse_wdi_bridge_not_composed")

    current_port = build_production_world_bank_wdi_execution_port(control_service=control_service)
    if (
        type(current_port) is not WorldBankWDIAcquisitionExecutionPort
        or current_port._artifact_store is not control_service._artifact_store
        or type(current_port._authority) is not catalog.CanonicalAcquisitionAuthority
        or current_port._registry != live_port._registry
        or current_port._provision != live_port._provision
        or current_port._provision_content_sha256 != live_port._provision_content_sha256
        or current_port._authority.repo_root != live_port._authority.repo_root
        or current_port._authority.baseline_path != live_port._authority.baseline_path
        or current_port._authority.l5_path != live_port._authority.l5_path
        or current_port._authority.provision != live_port._authority.provision
        or current_port._authority.provision_content_sha256
        != live_port._authority.provision_content_sha256
    ):
        raise ValueError("candidate_experiment_reuse_wdi_authority_changed")

    source = read_candidate_acquisition_source(
        control_service._artifact_store,
        source_ref=source_ref,
        authority=current_port._authority,
    )
    if (
        source != expected_source
        or source.source_currentness != "source_currentness_not_established"
    ):
        raise ValueError("candidate_experiment_reuse_current_source_mismatch")
    return current_port, source


def resolve_candidate_experiment_reuse_action_selection(
    *,
    control_service: ControlPlaneService,
    tenant_id: str,
    cell_id: str,
    run_id: str,
    request: CandidateExperimentReuseActionRequest,
) -> CandidateExperimentReuseActionSelection:
    """Reopen an exact current predecessor for a lease-free reuse request.

    This is an ingress selection only. The request's prior terminal and N5
    references are replayed through the canonical action-history owner, then
    joined to the current Control head and current Catalog/policy owners. It
    does not create a job, request PA2, execute N5, spend budget, or authorize
    source use. A worker must repeat the owner checks under its own lease.
    """
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        ControlPlaneService,
    )
    from polisyos.runtime.http.services.control_plane_store import AcquisitionActionHeadRecord
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
        AcquisitionRouteClosureError,
        AcquisitionRouteLoop,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.substrate_registry import (
        _catalog_content_ref,
        current_catalog_serving_source,
    )

    if type(request) is not CandidateExperimentReuseActionRequest:
        raise ValueError("candidate_experiment_reuse_request_untyped")
    request = CandidateExperimentReuseActionRequest.model_validate(
        request.model_dump(mode="python")
    )
    if any(
        not isinstance(value, str) or not value or value != value.strip()
        for value in (tenant_id, cell_id, run_id)
    ):
        raise ValueError("candidate_experiment_reuse_authenticated_scope_invalid")

    if type(control_service) is not ControlPlaneService:
        raise ValueError("candidate_experiment_reuse_control_owner_not_composed")
    service = control_service
    sink = service.acquisition_route_sink
    if (
        service._control_store is None
        or service._artifact_store is None
        or service._diagnostic_event_log is None
        or type(sink) is not AcquisitionRouteLoopAuthoritySink
        or sink._control_store is not service._control_store
        or sink._artifact_store is not service._artifact_store
        or sink._event_log is not service._diagnostic_event_log
        or sink._core_source_resolver != service.resolve_completed_control_job_core_run_source
    ):
        raise ValueError("candidate_experiment_reuse_control_owner_not_composed")
    loop = AcquisitionRouteLoop(
        control_store=service._control_store,
        artifact_store=service._artifact_store,
        event_log=service._diagnostic_event_log,
        core_source_resolver=service.resolve_completed_control_job_core_run_source,
        tenant_id=tenant_id,
        cell_id=cell_id,
        action_outcome_reader=sink,
    )
    try:
        origin = loop.resolve_candidate_experiment_predecessor_origin(
            run_id=run_id,
            predecessor_terminal_ref=request.predecessor_terminal_ref,
        )
    except (OSError, RuntimeError, TypeError, ValueError, AcquisitionRouteClosureError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("candidate_experiment_reuse_"):
            raise
        raise ValueError("candidate_experiment_reuse_predecessor_not_current") from exc

    chain = origin.candidate_terminal_history_chain
    if (
        type(origin) is not VerifiedCandidateExperimentOrigin
        or not chain
        or origin.current_terminal_history is not chain[-1]
        or (origin.tenant_id, origin.cell_id, origin.run_id) != (tenant_id, cell_id, run_id)
        or origin.route_id != request.route_id
        or origin.policy_ref != request.policy_ref
        or chain[-1].terminal_ref != request.predecessor_terminal_ref
        or chain[-1].head.action_generation != len(chain)
        or chain[-1].terminal.action_generation != len(chain)
        or chain[-1].head.receipt_phase != "terminal"
        or chain[-1].terminal.terminal_outcome == "candidate_blocked"
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_not_latest_verified")

    history = chain[-1]
    evaluation = _selected_predecessor_evaluation(history)
    selected = evaluation.selected
    action = history.action
    source_ref = action.candidate_source_ref
    if (
        request.predecessor_action_ref != history.terminal.candidate_action_ref
        or request.source_ref != source_ref
        or request.n5_input_ref != selected.n5_input_ref
        or request.n5_execution_ref != selected.n5_execution_ref
        or request.n5_result_ref != selected.n5_result_ref
        or (
            type(history.terminal) is AcquisitionCandidateExperimentTerminalReceipt
            and (
                action.action_generation != history.head.action_generation
                or action.action_job_id != history.head.job_id
            )
        )
        or (action.tenant_id, action.cell_id, action.run_id, action.route_id)
        != (tenant_id, cell_id, run_id, request.route_id)
        or action.source_job_id != origin.source_job_id
        or history.source.job_id != action.action_job_id
        or history.source.route_id != origin.route_id
        or history.source.tenant_id != tenant_id
        or history.source.cell_id != cell_id
        or history.source.run_id != run_id
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_pins_mismatch")

    try:
        current_policy_ref, current_policy = resolve_current_candidate_unpriced_policy(
            control_service=service,
            scope=origin.policy_scope,
        )
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        raise ValueError("candidate_experiment_reuse_current_policy_not_established") from exc
    if (
        current_policy_ref != origin.policy_ref
        or current_policy.scope != origin.policy_scope
        or current_policy.source_payload_ref != origin.source_payload_ref
        or current_policy.request_content_hash != origin.request_content_hash
        or current_policy.purpose != "bounded_candidate_experiment_voi_unknown"
        or current_policy.configured_template is None
    ):
        raise ValueError("candidate_experiment_reuse_current_policy_changed")

    catalog_source = _reopen_current_reuse_catalog_context(
        control_service=service,
        substrate_registry=evaluation.handoff.context.substrate_registry,
    )
    current_wdi_port, _source = _reopen_current_reuse_wdi_source(
        control_service=service,
        source_ref=source_ref,
        expected_source=history.source,
    )

    heads = service._control_store.list_acquisition_action_heads_for_source(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id=origin.source_job_id,
    )
    if (
        not isinstance(heads, tuple)
        or any(type(head) is not AcquisitionActionHeadRecord for head in heads)
        or any(
            (head.tenant_id, head.cell_id, head.run_id, head.source_job_id, head.route_id)
            != (tenant_id, cell_id, run_id, origin.source_job_id, origin.route_id)
            for head in heads
        )
        or tuple(head.action_generation for head in heads) != tuple(range(1, len(heads) + 1))
        or heads != tuple(item.head for item in chain)
        or not heads
        or heads[-1] != history.head
    ):
        raise ValueError("candidate_experiment_reuse_predecessor_not_current_control_head")

    predecessor_generation = history.head.action_generation
    action_generation = predecessor_generation + 1
    catalog_source_content_ref = (
        _catalog_content_ref(catalog_source)
        if catalog_source.selection_basis == "explicit_path_candidate_only"
        else None
    )
    action_job_id = _candidate_experiment_reuse_job_id(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        route_id=origin.route_id,
        predecessor_action_generation=predecessor_generation,
        action_generation=action_generation,
        source_job_id=origin.source_job_id,
        source_payload_ref=origin.source_payload_ref,
        request_content_hash=origin.request_content_hash,
        policy_ref=origin.policy_ref,
        policy_scope=origin.policy_scope,
        request=request,
        authority_provision_content_sha256=current_wdi_port._provision_content_sha256,
        catalog_source_selection_basis=catalog_source.selection_basis,
        catalog_source_content_ref=catalog_source_content_ref,
    )
    if any(head.job_id == action_job_id for head in heads):
        # This selector admits a new generation. The HTTP retry path instead
        # reopens the exact already-enqueued request and its signed decision.
        raise ValueError("candidate_experiment_reuse_job_identity_conflict")

    # Re-read the authority source and Control head after all selected refs and
    # current Catalog/policy state have been reopened.
    try:
        refreshed_origin = loop._resolve_candidate_experiment_source(run_id=run_id)
    except (OSError, RuntimeError, TypeError, ValueError, AcquisitionRouteClosureError) as exc:
        raise ValueError("candidate_experiment_reuse_current_source_changed") from exc
    catalog_after = _reopen_current_reuse_catalog_context(
        control_service=service,
        substrate_registry=evaluation.handoff.context.substrate_registry,
    )
    if (
        not _candidate_model_values_same(
            replace(
                origin,
                current_action_head=None,
                current_terminal_history=None,
                candidate_terminal_history_chain=(),
            ),
            refreshed_origin,
        )
        or service._control_store.list_acquisition_action_heads_for_source(
            tenant_id=tenant_id,
            cell_id=cell_id,
            run_id=run_id,
            source_job_id=origin.source_job_id,
        )
        != heads
        or current_catalog_serving_source() is not catalog_source
        or catalog_after is not catalog_source
    ):
        raise ValueError("candidate_experiment_reuse_current_owner_changed")

    return CandidateExperimentReuseActionSelection(
        tenant_id=tenant_id,
        cell_id=cell_id,
        run_id=run_id,
        source_job_id=origin.source_job_id,
        source_payload_ref=origin.source_payload_ref,
        request_content_hash=origin.request_content_hash,
        route_id=origin.route_id,
        predecessor_action_generation=predecessor_generation,
        action_generation=action_generation,
        action_job_id=action_job_id,
        predecessor_terminal_ref=history.terminal_ref,
        predecessor_action_ref=history.terminal.candidate_action_ref,
        source_ref=source_ref,
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        policy_ref=origin.policy_ref,
        policy_scope=origin.policy_scope,
        catalog_source_selection_basis=catalog_source.selection_basis,
        catalog_source_content_ref=catalog_source_content_ref,
        authority_provision_content_sha256=current_wdi_port._provision_content_sha256,
        source_currentness="source_currentness_not_established",
        request=request,
    )


def resolve_current_candidate_experiment_reuse(
    *,
    bridge: AcquisitionWorldGrowthBridge,
    origin: VerifiedCandidateExperimentOrigin,
    action_context: _CurrentCandidateExperimentActionContext,
) -> CandidateExperimentReuseSelection:
    """Resolve a read-only selection from the exact current action and predecessor.

    The supplied origin and action context are re-opened through the actual
    control, Catalog, source-authority, CAS, and terminal-history owners. No
    action is executed and no budget, transport, event, or artifact is written.
    """
    from polisyos.data_forge.read_api import catalog
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        verify_candidate_experiment_terminal_history,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
        VerifiedCandidateExperimentOrigin,
    )
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_action import (
        _current_candidate_experiment_action_context,
        _CurrentCandidateExperimentActionContext,
    )
    from polisyos.runtime.quality.substrate_registry import _catalog_content_ref

    # Check the authenticated context before consulting its history. The exact
    # current helper below replays this phase and the complete latest chain.
    if type(origin) is not VerifiedCandidateExperimentOrigin:
        raise ValueError("candidate_experiment_reuse_origin_not_verified")
    if type(action_context) is not _CurrentCandidateExperimentActionContext:
        raise ValueError("candidate_experiment_reuse_action_context_not_verified")
    chain = origin.candidate_terminal_history_chain
    if not chain:
        raise ValueError("candidate_experiment_reuse_predecessor_terminal_missing")
    if type(bridge) is not AcquisitionWorldGrowthBridge:
        raise ValueError("candidate_experiment_reuse_bridge_not_composed")

    phase = action_context.phase
    current_outcome = action_context.outcome
    if (
        type(phase) is not AcquisitionCandidateExperimentPhaseReceipt
        or phase.receipt_phase != "executing"
        or action_context.action is not None
        or current_outcome.executing_phase != phase
        or current_outcome.executing_phase_ref is None
        or current_outcome.head != origin.current_action_head
        or len(current_outcome.phase_chain) != 2
        or phase.action_generation != len(chain) + 1
    ):
        raise ValueError("candidate_experiment_reuse_current_action_not_executing")

    latest = chain[-1]
    requested = current_outcome.phase_chain[0].receipt
    if (
        type(latest) is not CandidateExperimentTerminalHistory
        or type(requested) is not AcquisitionCandidateExperimentPhaseReceipt
        or requested.receipt_phase != "requested"
        or requested.action_generation != phase.action_generation
        # V1's requested phase intentionally has no predecessor field. The
        # distinct immutable reuse request pins the prior terminal and is
        # joined against this replayed history by the action selection owner.
        or requested.predecessor_receipt_ref is not None
        or latest.head.action_generation != len(chain)
        or latest.terminal.action_generation != len(chain)
        or latest.head.receipt_phase != "terminal"
        or latest.terminal.terminal_outcome == "candidate_blocked"
        or phase.tenant_id != origin.tenant_id
        or phase.cell_id != origin.cell_id
        or phase.run_id != origin.run_id
        or phase.source_job_id != origin.source_job_id
        or phase.route_id != origin.route_id
    ):
        raise ValueError("candidate_experiment_reuse_latest_predecessor_not_verified")

    service = bridge._source_control_service
    if (
        type(service) is not ControlPlaneService
        or service._control_store is not bridge.control_store
        or service._artifact_store is not bridge.artifact_store
        or service._diagnostic_event_log is not bridge.event_log
        or service.acquisition_route_sink is not bridge.action_head_sink
    ):
        raise ValueError("candidate_experiment_reuse_control_owner_not_composed")

    # Re-resolve the exact current worker phase. This verifies the action head,
    # authenticated running job, and full current origin including its terminal
    # chain; a caller-created dataclass instance cannot serve as proof.
    current = _current_candidate_experiment_action_context(
        bridge,
        origin,
        current_outcome.executing_phase_ref,
        required_phase="executing",
    )
    if current != action_context:
        raise ValueError("candidate_experiment_reuse_current_context_changed")

    # Replay the latest terminal through the persisted PA2/action/source/N5
    # history reader, binding its full selected manifest profile.
    replayed = verify_candidate_experiment_terminal_history(
        control_service=service,
        head=latest.head,
        terminal_ref=latest.terminal_ref,
    )
    if not _candidate_model_values_same(replayed, latest):
        raise ValueError("candidate_experiment_reuse_predecessor_history_changed")
    evaluation = _selected_predecessor_evaluation(replayed)

    action = replayed.action
    source_ref = action.candidate_source_ref
    if (
        source_ref.manifest_profile_sha256 is None
        or action.tenant_id != origin.tenant_id
        or action.cell_id != origin.cell_id
        or action.run_id != origin.run_id
        or action.source_job_id != origin.source_job_id
        or action.route_id != origin.route_id
        or replayed.source.job_id != action.action_job_id
        or replayed.source.route_id != origin.route_id
        or replayed.source.tenant_id != origin.tenant_id
        or replayed.source.cell_id != origin.cell_id
        or replayed.source.run_id != origin.run_id
    ):
        raise ValueError("candidate_experiment_reuse_source_scope_mismatch")

    # Catalog serving context and WDI source authority are separate owners.
    # Reopen the former's registry/context fence, then independently reopen
    # the latter's exact production provision and historical source bytes.
    composed_authority = bridge.authority
    if type(composed_authority) is not catalog.CanonicalAcquisitionAuthority:
        raise ValueError("candidate_experiment_reuse_wdi_authority_not_composed")
    if Path(bridge.repo_root).resolve() != composed_authority.repo_root:
        raise ValueError("candidate_experiment_reuse_wdi_owner_root_mismatch")
    catalog_source = _reopen_current_reuse_catalog_context(
        control_service=service,
        substrate_registry=evaluation.handoff.context.substrate_registry,
    )
    current_wdi_port, source = _reopen_current_reuse_wdi_source(
        control_service=service,
        source_ref=source_ref,
        expected_source=replayed.source,
        expected_bridge=bridge,
    )
    if (
        current_wdi_port._authority.repo_root != composed_authority.repo_root
        or current_wdi_port._authority.baseline_path != composed_authority.baseline_path
        or current_wdi_port._authority.l5_path != composed_authority.l5_path
        or current_wdi_port._authority.provision != composed_authority.provision
        or current_wdi_port._authority.provision_content_sha256
        != composed_authority.provision_content_sha256
    ):
        raise ValueError("candidate_experiment_reuse_wdi_authority_changed")

    selected = evaluation.selected
    phase_manifest = bridge.artifact_store.get_manifest(current_outcome.executing_phase_ref)
    from polisyos.core.artifacts import artifact_ref_for_manifest

    current_phase_ref = artifact_ref_for_manifest(phase_manifest)
    if (
        current_phase_ref.manifest_profile_sha256 is None
        or current_phase_ref.kind
        != "runtime_quality.acquisition_candidate_experiment_phase_receipt"
        or str(current_phase_ref.artifact_id) != action_context.outcome.phase_chain[-1].receipt_ref
        or current_phase_ref.manifest_profile_sha256
        != current_outcome.head.receipt_manifest_profile_sha256
    ):
        raise ValueError("candidate_experiment_reuse_current_phase_profile_mismatch")

    # Close the read with another exact current-context check so a changed head,
    # job lease, or predecessor chain cannot race this selection.
    after = _current_candidate_experiment_action_context(
        bridge,
        origin,
        current_outcome.executing_phase_ref,
        required_phase="executing",
    )
    catalog_after = _reopen_current_reuse_catalog_context(
        control_service=service,
        substrate_registry=evaluation.handoff.context.substrate_registry,
    )
    wdi_after, source_after = _reopen_current_reuse_wdi_source(
        control_service=service,
        source_ref=source_ref,
        expected_source=replayed.source,
        expected_bridge=bridge,
    )
    if (
        after != action_context
        or catalog_after is not catalog_source
        or wdi_after._provision_content_sha256 != current_wdi_port._provision_content_sha256
        or wdi_after._registry != current_wdi_port._registry
        or source_after != source
    ):
        raise ValueError("candidate_experiment_reuse_current_owner_changed")

    return CandidateExperimentReuseSelection(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        route_id=origin.route_id,
        current_action_generation=phase.action_generation,
        current_action_phase_ref=current_phase_ref,
        predecessor_terminal_ref=latest.terminal_ref,
        predecessor_action_ref=latest.terminal.candidate_action_ref,
        source_ref=source_ref,
        source=source,
        n5_input_ref=selected.n5_input_ref,
        n5_execution_ref=selected.n5_execution_ref,
        n5_result_ref=selected.n5_result_ref,
        catalog_source_selection_basis=catalog_source.selection_basis,
        catalog_source_content_ref=(
            _catalog_content_ref(catalog_source)
            if catalog_source.selection_basis == "explicit_path_candidate_only"
            else None
        ),
        authority_provision_content_sha256=current_wdi_port._provision_content_sha256,
    )
