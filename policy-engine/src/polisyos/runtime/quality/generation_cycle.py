"""Generation-cycle controller for revising design candidates under A.

The controller owns the N6 loop shape only. It runs the existing simple workflow
engine over N4 generation, A-side grounding, N5 simulation/value ports, S2
counterexample/refinement records, and VOI routing. It never promotes a
candidate and it never fabricates value; missing N8/N9 organs are explicit ports.

Owner breadcrumbs: N4 lives in ``runtime.quality.design_generation``, CGF
grounding dispositions in the same N4 result, N5 in
``runtime.quality.joint_simulation_horizon``, S2 records in
``pdc._impl.layer2_design_search``, and VOI routing in
``scientist.methods.search.voi_scheduler``. This module is the thin N6
controller over those owners, not a second grounding or search engine.
"""

from __future__ import annotations

import ast
import inspect
import math
import re
import time
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core import components as core_components
from polisyos.core import contracts as core_contracts
from polisyos.core.contracts.value_outer_set import (
    DataTrust,
    ValueOuterSet,
    ValueOuterSetIdentificationStatus,
)
from polisyos.data_forge import read_api as data_forge_read_api
from polisyos.data_requirement.compiler import DataRequirementCompiler
from polisyos.foundry.methods.selection import (
    MethodSelectionReceipt,
    method_selection_context_hash,
)
from polisyos.pdc import (
    ArtifactRef,
    CounterexampleRecord,
    RefinementDecision,
    SearchIteration,
    SearchTerminalKind,
    SearchTerminalState,
    TypedDiagnosticRecord,
    ValueOfInformationEstimate,
    gy_artifact_self_identity_projection,
    gy_content_hash,
)
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionPlannerReport,
    AcquisitionReceipt,
    AcquisitionRequirementGap,
    AcquisitionWorldSnapshot,
    RealAcquisitionOwnerGateway,
    grounding_coverage_requirement_gap,
    l1_variable_availability_requirement_gap,
    plan_requirement_gap_acquisition,
    run_acquisition_closed_loop,
    value_input_world_knowledge_requirement_gap,
)
from polisyos.runtime.quality.design_problem import DesignProblem  # noqa: TC001
from polisyos.runtime.quality.evaluation_modes import (
    EvaluationMode as ValueEvaluationMode,
)
from polisyos.runtime.quality.evaluation_modes import (
    EvaluationModeResolution,
    resolve_evaluation_mode,
)
from polisyos.runtime.quality.evaluation_safety import (
    EvalSafetyAdmissionChallenge,
    EvalSafetyVerifierPort,
    EvaluationExecutionContext,
    EvaluationInputProvenance,
    evaluation_safety_consumer_admission_is_verified,
)
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
from polisyos.runtime.quality.intervention_substrate import InterventionLeverRefusal
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
    JointSimulationRequest,
    JointSimulationResult,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateLayer,
    SubstrateRegistry,
    SubstrateRegistryError,
    build_substrate_registry_from_existing_catalogs,
)
from polisyos.runtime.quality.workspace.loop import (
    SearchExitDecisionInputs,
    select_search_terminal,
)
from polisyos.runtime.quality.world_model_record import (
    WorldModelRecord,
    WorldModelRecordError,
)
from polisyos.scientist.methods.search.voi_scheduler import (
    ParetoSnapshot,
    SchedulingDecision,
    SimpleVOIScheduler,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState  # noqa: TC001
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine

if TYPE_CHECKING:
    from polisyos.runtime.quality.cycle_substrate import CycleSubstrateContext
    from polisyos.runtime.quality.data_state_substrate import L1VariableAvailability
    from polisyos.runtime.quality.open_world_risk import (
        OpenWorldRiskArtifactResolver,
        PromotionRuntime,
    )

GENERATION_CYCLE_SCHEMA_VERSION = "policyos.runtime.generation_cycle_controller.v1"
GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION = (
    "policyos.policy_design_case.layer3_gy.generation_cycle_contract.v1"
)
GENERATION_CYCLE_RULE_VERSION = "policyos.layer3.gy.n6.generation_cycle.v1"
GENERATION_CYCLE_CONTROLLER_REF = (
    "polisyos.runtime.quality.generation_cycle.GenerationCycleController"
)
ENGINE_SIMPLE_OWNER_REF = (
    "polisyos.scientist.orchestration.workflows.engine_simple.SimpleLoopEngine"
)
_N7_ROUTING_FAILURE_CODES = frozenset(
    {
        "n7_cycle_substrate_context_invalid",
        "n7_cycle_substrate_context_mismatch",
        "n7_requirement_gap_invalid",
        "n7_substrate_registry_invalid",
        "n7_substrate_registry_unresolved",
    }
)

FrontKind = Literal["decision", "research", "quarantine", "portfolio"]
GenerationChannel = Literal["n4_owner", "grammar_fallback"]
RevisionStrategy = Literal[
    "acquire_or_elicit",
    "adversarial_validate",
    "spec_gap_reframe",
    "hold_abstain",
    "terminal_stop",
    "human_escalation",
    "tool_repair",
    "composition_repair",
    "recursive_block",
]
GroundingStatus = Literal[
    "current_valid",
    "grounded_shadow",
    "grounding_gap",
    "grounding_failed",
    "grounding_unavailable",
]
LoopNextAction = Literal["advance", "stop", "escalate", "blocked"]
QuarantineAction = Literal["none", "adversarial_validate"]
ValuePortStatus = Literal["value_pending_n8", "value_ready", "value_blocked"]
PromotionPortStatus = Literal["promotion_pending_n9", "certified_current_valid", "not_promoted"]
TerminalStatus = Literal["completed", "blocked"]


class GenerationCycleError(ValueError):
    """Fail-closed generation-cycle error."""

    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(f"{code}: {message or code}")


class _StrictModel(BaseModel):
    """Strict immutable base model for public N6 artifacts."""

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)


class CandidateGroundingObservation(_StrictModel):
    """A-side grounding observation for one generated candidate."""

    candidate_id: str = Field(..., min_length=1)
    status: GroundingStatus
    grounding_score: float = Field(ge=0.0, le=1.0)
    issue_codes: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    current_valid: bool = False
    report_ref: str | None = None
    grounding_source: Literal["cgf_firewall", "grounding_unavailable"] = "grounding_unavailable"
    grounding_disposition: str | None = None
    cgf_certificate_refs: tuple[str, ...] = ()
    quarantine_action: QuarantineAction = "none"
    adversarial_validation_ref: str | None = None
    acquisition_requirement: AcquisitionRequirementGap | None = None

    @model_validator(mode="after")
    def _current_valid_requires_grounding(self) -> CandidateGroundingObservation:
        if self.current_valid and self.status != "current_valid":
            raise ValueError("current_valid_requires_current_valid_status")
        if self.status in {"current_valid", "grounded_shadow"} and (
            self.grounding_source != "cgf_firewall" or not self.grounding_disposition
        ):
            raise ValueError("grounded_status_requires_cgf_firewall_disposition")
        if self.acquisition_requirement is not None:
            if self.status in {"current_valid", "grounded_shadow"}:
                raise ValueError("grounded_status_cannot_require_acquisition")
            if self.acquisition_requirement.metadata.get("source") != ("cgf_grounding_coverage"):
                raise ValueError("grounding_acquisition_requirement_not_canonical")
        return self


class SimulationPortObservation(_StrictModel):
    """N5 joint-simulation observation for one selected candidate."""

    candidate_id: str = Field(..., min_length=1)
    status: Literal["joint_simulated", "simulation_pending_n5", "simulation_blocked"]
    simulation_ref: str | None = None
    uncertainty_kind: str | None = None
    authority_blockers: tuple[str, ...] = ()
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    k_world_ref_before: str | None = None
    k_world_ref_after: str | None = None
    world_model_record: WorldModelRecord | None = Field(default=None, exclude=True)
    k_world_update_mode: Literal["read_only_no_k_world_narrowing"] = (
        "read_only_no_k_world_narrowing"
    )

    @model_validator(mode="after")
    def _k_sim_cannot_shrink_k_world(self) -> SimulationPortObservation:
        if (
            self.k_world_ref_before is not None
            and self.k_world_ref_after is not None
            and self.k_world_ref_before != self.k_world_ref_after
        ):
            raise ValueError("k_sim_must_not_shrink_k_world")
        return self


def _joint_simulation_port_outcome(
    result: JointSimulationResult,
) -> tuple[Literal["joint_simulated", "simulation_blocked"], tuple[str, ...]]:
    """Project the real N5 outcome without relabeling an unsupported run."""

    unsupported = (
        result.receipt.calibration_status in {"unsupported_coupling_gated", "no_run"}
        or not result.trajectories
        or any(decision.decision != "selected" for decision in result.engine_decisions)
    )
    blockers = list(result.promotion_ready_value_packet.get("authority_blockers", ()))
    if unsupported:
        blockers.extend(result.feedback_classification.support_blockers)
        for decision in result.engine_decisions:
            blockers.extend(decision.blockers)
        if not blockers:
            blockers.append("joint_simulation_no_supported_trajectory")
        return "simulation_blocked", tuple(dict.fromkeys(str(item) for item in blockers))
    return "joint_simulated", tuple(dict.fromkeys(str(item) for item in blockers))


class ValueTransportReceipt(_StrictModel):
    """N8 transport receipt bound to the WMR version that produced value."""

    status: Literal["transported_limited", "direct", "blocked"]
    world_model_record_id: str = Field(..., min_length=1)
    world_model_record_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    transport_result_ref: str = Field(..., min_length=1)
    transport_status: str = Field(..., min_length=1)
    transport_mode: str = Field(..., min_length=1)
    identification_engine: str = Field(..., min_length=1)
    required_target_data: tuple[str, ...] = ()
    limitation_refs: tuple[str, ...] = ()


class ValueCalibrationReceipt(_StrictModel):
    """N8 calibration admission receipt delegated to the S10 owner semantics."""

    status: Literal["pass", "blocked"]
    forecast_tier: str = Field(..., min_length=1)
    calibration_record_ref: str | None = None
    uncertainty_interval_refs: tuple[str, ...] = ()
    false_clear_counts: dict[str, int] = Field(default_factory=dict)
    issue_codes: tuple[str, ...] = ()


class ValueOwnerRow(_StrictModel):
    """One content-bound owner outcome row used only for value-data shape."""

    unit_id: str = Field(min_length=1)
    period_id: int
    outcome_value: float
    source_row_content_hashes: tuple[str, ...] = Field(min_length=1)
    row_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_row_content(self) -> ValueOwnerRow:
        expected = gy_content_hash(
            {
                "unit_id": self.unit_id,
                "period_id": self.period_id,
                "outcome_value": self.outcome_value,
                "source_row_content_hashes": self.source_row_content_hashes,
            }
        )
        if self.row_content_hash != expected:
            raise ValueError("value_owner_row_content_hash_mismatch")
        return self


VALUE_DATA_SHAPE_RULE_VERSION = "polisyos.runtime.value_data_shape.v1"


def is_value_panel_shape(
    *,
    longitudinal_unit_count: int,
    period_count: int,
) -> bool:
    """Classify panel readiness under the canonical owner-data shape rule."""

    return longitudinal_unit_count >= 3 and period_count >= 4


def _derived_value_data_modalities(
    rows: Sequence[ValueOwnerRow],
) -> tuple[str, ...]:
    """Derive conservative method-selection modalities from owner row shape."""

    periods_by_unit: dict[str, set[int]] = {}
    for row in rows:
        periods_by_unit.setdefault(row.unit_id, set()).add(row.period_id)
    longitudinal_units = sum(1 for periods in periods_by_unit.values() if len(periods) >= 4)
    modalities = {"tabular"}
    if is_value_panel_shape(
        longitudinal_unit_count=longitudinal_units,
        period_count=len({row.period_id for row in rows}),
    ):
        modalities.add("panel")
    return tuple(sorted(modalities))


class ValueDataProfile(_StrictModel):
    """Method-neutral owner rows and their still-missing treatment knowledge."""

    schema_version: Literal["policyos.runtime.value_data_profile.v1"] = (
        "policyos.runtime.value_data_profile.v1"
    )
    outcome: str = Field(min_length=1)
    rows: tuple[ValueOwnerRow, ...] = Field(min_length=4)
    owner_row_count: int = Field(ge=4)
    unit_count: int = Field(ge=1)
    period_count: int = Field(ge=1)
    available_data_modalities: tuple[str, ...]
    treatment_assignment_status: Literal["owner_assignment_unresolved"] = (
        "owner_assignment_unresolved"
    )
    owner_access_ref: str = Field(min_length=1)
    owner_rows_content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^sha256:[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_profile_content(self) -> ValueDataProfile:
        if self.owner_row_count != len(self.rows):
            raise ValueError("value_data_profile_row_count_mismatch")
        if self.unit_count != len({row.unit_id for row in self.rows}):
            raise ValueError("value_data_profile_unit_count_mismatch")
        if self.period_count != len({row.period_id for row in self.rows}):
            raise ValueError("value_data_profile_period_count_mismatch")
        modalities = tuple(sorted(set(self.available_data_modalities)))
        if self.available_data_modalities != modalities or "tabular" not in modalities:
            raise ValueError("value_data_profile_modalities_not_canonical")
        if modalities != _derived_value_data_modalities(self.rows):
            raise ValueError("value_data_profile_modalities_not_derived")
        rows_payload = tuple(row.model_dump(mode="json") for row in self.rows)
        if self.owner_rows_content_hash != gy_content_hash(rows_payload):
            raise ValueError("value_data_profile_owner_rows_hash_mismatch")
        payload = gy_artifact_self_identity_projection(self)
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("value_data_profile_content_hash_mismatch")
        return self


class ValueReceiptConsistencyPredicate(_StrictModel):
    """One generation-owner recomputation over a value receipt's internal refs."""

    rule_version: Literal["polisyos.runtime.value_receipt_consistency.v1"] = (
        "polisyos.runtime.value_receipt_consistency.v1"
    )
    predicate_id: Literal[
        "transport_wmr_hash_equals_receipt_wmr_hash",
        "outer_set_wmr_ref_equals_receipt_wmr_hash",
    ]
    source_basis: Literal["receipt_internal_consistency"] = "receipt_internal_consistency"
    candidate_id: str = Field(..., min_length=1)
    observed_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    expected_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    satisfied: bool
    predicate_provenance: Literal["recomputed"] = "recomputed"
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    @classmethod
    def recompute(
        cls,
        *,
        predicate_id: Literal[
            "transport_wmr_hash_equals_receipt_wmr_hash",
            "outer_set_wmr_ref_equals_receipt_wmr_hash",
        ],
        candidate_id: str,
        observed_ref: str,
        expected_ref: str,
    ) -> ValueReceiptConsistencyPredicate:
        """Recompute and content-bind one exact receipt-consistency predicate."""

        payload = {
            "rule_version": "polisyos.runtime.value_receipt_consistency.v1",
            "predicate_id": predicate_id,
            "source_basis": "receipt_internal_consistency",
            "candidate_id": candidate_id,
            "observed_ref": observed_ref,
            "expected_ref": expected_ref,
            "satisfied": observed_ref == expected_ref,
            "predicate_provenance": "recomputed",
        }
        return cls(**payload, content_hash=gy_content_hash(payload))

    @model_validator(mode="after")
    def _verify_content_hash(self) -> ValueReceiptConsistencyPredicate:
        payload = self.model_dump(mode="json", exclude={"content_hash"})
        if self.content_hash != gy_content_hash(payload):
            raise ValueError("value_receipt_predicate_content_hash_mismatch")
        return self


class ValueGateReceipt(_StrictModel):
    """Replay-visible value receipt emitted only after live owner gates pass."""

    schema_version: str = "policyos.runtime.generation_cycle.value_gate_receipt.v1"
    candidate_id: str = Field(..., min_length=1)
    evaluation_mode: ValueEvaluationMode
    selected_method_fqn: str = Field(..., min_length=1)
    method_selection_trace: tuple[str, ...] = ()
    identification_status: ValueOuterSetIdentificationStatus
    value_outer_set: ValueOuterSet
    transport_receipt: ValueTransportReceipt
    calibration_receipt: ValueCalibrationReceipt
    world_model_record_id: str = Field(..., min_length=1)
    world_model_record_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    value_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    wall_time_ms: float = Field(ge=0.0)
    wmr_cache_status: Literal["built", "reused"]
    k_world_ref_before: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    k_world_ref_after: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")

    def decisive_consistency_predicates(
        self,
    ) -> tuple[ValueReceiptConsistencyPredicate, ...]:
        """Return the two decisive, owner-recomputed internal consistency checks."""

        expected = self.world_model_record_content_hash
        return (
            ValueReceiptConsistencyPredicate.recompute(
                predicate_id="transport_wmr_hash_equals_receipt_wmr_hash",
                candidate_id=self.candidate_id,
                observed_ref=self.transport_receipt.world_model_record_content_hash,
                expected_ref=expected,
            ),
            ValueReceiptConsistencyPredicate.recompute(
                predicate_id="outer_set_wmr_ref_equals_receipt_wmr_hash",
                candidate_id=self.candidate_id,
                observed_ref=self.value_outer_set.world_model_record_ref,
                expected_ref=expected,
            ),
        )

    @model_validator(mode="after")
    def _simulate_only_does_not_shrink_k_world(self) -> ValueGateReceipt:
        if self.evaluation_mode == "simulate_only" and (
            self.k_world_ref_before != self.k_world_ref_after
        ):
            raise ValueError("simulate_only_shrank_k_world")
        error_codes = {
            "transport_wmr_hash_equals_receipt_wmr_hash": ("transport_wmr_hash_mismatch"),
            "outer_set_wmr_ref_equals_receipt_wmr_hash": ("outer_set_wmr_ref_mismatch"),
        }
        for predicate in self.decisive_consistency_predicates():
            if not predicate.satisfied:
                raise ValueError(
                    f"value_world_version_laundered:{error_codes[predicate.predicate_id]}"
                )
        return self


class ValuePortObservation(_StrictModel):
    """N8 value-port observation; pending is explicit and non-authoritative."""

    status: ValuePortStatus = "value_pending_n8"
    candidate_id: str | None = Field(default=None, min_length=1)
    value_ref: str | None = None
    authority_blockers: tuple[str, ...] = ("value_gate_pending_n8",)
    reason: str = "N8 value gate is not present; N6 will not fabricate value."
    evaluation_mode: ValueEvaluationMode | None = None
    selected_method_fqn: str | None = None
    method_selection_receipt: MethodSelectionReceipt | None = None
    value_data_profile_content_hash: str | None = None
    acquisition_requirement: AcquisitionRequirementGap | None = None
    identification_status: ValueOuterSetIdentificationStatus | None = None
    decision_grade: Literal["blocked", "low", "medium", "high"] | None = None
    world_model_record_content_hash: str | None = None
    transport_receipt: ValueTransportReceipt | None = None
    calibration_receipt: ValueCalibrationReceipt | None = None
    value_receipt: ValueGateReceipt | None = None
    wall_time_ms: float | None = Field(default=None, ge=0.0)

    @model_validator(mode="after")
    def _verify_value_authority_shape(self) -> ValuePortObservation:
        if self.status == "value_ready":
            if self.value_receipt is None or self.method_selection_receipt is None:
                raise ValueError("value_ready_requires_owner_receipts")
            if self.acquisition_requirement is not None:
                raise ValueError("value_ready_cannot_carry_unsatisfied_acquisition")
        elif self.value_receipt is not None:
            raise ValueError("blocked_or_pending_value_cannot_carry_value_receipt")
        if self.acquisition_requirement is not None and self.status != "value_blocked":
            raise ValueError("value_acquisition_requirement_requires_blocked_status")
        if self.acquisition_requirement is not None:
            if self.candidate_id is None:
                raise ValueError("value_acquisition_requirement_not_canonical")
            if self.authority_blockers == ("treatment_assignment_not_owner_derived",):
                expected = value_input_world_knowledge_requirement_gap(
                    claim_ref=f"value-claim:{self.candidate_id}"
                )
            elif self.authority_blockers == ("acquire_data:value_panel_data_missing",):
                from polisyos.runtime.quality.data_state_substrate import (
                    L1VariableAvailability,
                )

                metadata = self.acquisition_requirement.metadata
                binding = metadata.get("candidate_binding")
                availability = metadata.get("availability")
                if not isinstance(binding, Mapping) or not isinstance(availability, Mapping):
                    raise ValueError("value_acquisition_requirement_not_canonical")
                availability_payload = dict(availability)
                availability_payload.pop("availability_content_hash", None)
                expected = l1_variable_availability_requirement_gap(
                    candidate_id=str(binding.get("candidate_id") or ""),
                    candidate_content_hash=str(binding.get("candidate_content_hash") or ""),
                    design_problem_ref=str(binding.get("design_problem_ref") or ""),
                    availability=L1VariableAvailability.model_validate(availability_payload),
                    authority_level=str(metadata.get("authority_level") or ""),
                )
                if binding.get("candidate_id") != self.candidate_id:
                    raise ValueError("value_acquisition_requirement_not_canonical")
            else:
                raise ValueError("value_acquisition_requirement_not_canonical")
            if self.acquisition_requirement.model_dump(mode="json") != expected.model_dump(
                mode="json"
            ):
                raise ValueError("value_acquisition_requirement_not_canonical")
        if (
            self.method_selection_receipt is not None
            and self.selected_method_fqn != self.method_selection_receipt.selected_method_fqn
        ):
            raise ValueError("value_observation_selection_receipt_method_mismatch")
        return self


class PreN9OpenWorldRiskGateObservation(_StrictModel):
    """Transport-only replay input captured before an epoch refusal reaches N9."""

    ordinal: int = Field(ge=0)
    gate_payload: dict[str, Any] = Field(min_length=1)


class PromotionPortObservation(_StrictModel):
    """N9 promotion-port observation; N6 does not promote."""

    status: PromotionPortStatus = "promotion_pending_n9"
    certified_candidate_ids: tuple[str, ...] = ()
    reason: str = "N9 promotion gate is not present; N6 emits no certification."
    receipts: tuple[dict[str, Any], ...] = ()
    strangle_receipt: dict[str, Any] | None = None
    pre_n9_open_world_gates: tuple[PreN9OpenWorldRiskGateObservation, ...] = Field(
        default=(),
        exclude_if=lambda rows: not rows,
    )

    @model_validator(mode="after")
    def _pre_n9_gate_observations_are_negative_only(self) -> PromotionPortObservation:
        if not self.pre_n9_open_world_gates:
            return self
        if (
            self.status != "not_promoted"
            or self.reason != "epoch_validity_refused:policy_admission_missing"
            or self.receipts
            or self.certified_candidate_ids
        ):
            raise ValueError("pre_n9_open_world_gate_observation_not_negative_only")
        ordinals = tuple(row.ordinal for row in self.pre_n9_open_world_gates)
        if ordinals != tuple(range(len(ordinals))):
            raise ValueError("pre_n9_open_world_gate_observation_ordinal_mismatch")
        return self


class CandidateFront(_StrictModel):
    """One stratified frontier returned by the generation cycle."""

    front_kind: FrontKind
    candidate_ids: tuple[str, ...] = ()
    reason: str = Field(..., min_length=1)


class GenerationCycleFronts(_StrictModel):
    """Four stratified fronts emitted by N6."""

    decision: CandidateFront
    research: CandidateFront
    quarantine: CandidateFront
    portfolio: CandidateFront

    def candidate_ids_by_front(self) -> dict[str, tuple[str, ...]]:
        """Return candidate ids grouped by front kind."""

        return {
            "decision": self.decision.candidate_ids,
            "research": self.research.candidate_ids,
            "quarantine": self.quarantine.candidate_ids,
            "portfolio": self.portfolio.candidate_ids,
        }


class CandidateSummary(_StrictModel):
    """Front-derivation state for one generated candidate."""

    candidate_id: str = Field(..., min_length=1)
    content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    cycle_index: int = Field(ge=0)
    generation_channel: GenerationChannel = "n4_owner"
    proxy_score: float = Field(ge=0.0, le=1.0)
    voi_estimate: float = Field(ge=0.0)
    grounding_status: GroundingStatus
    grounding_source: Literal["cgf_firewall", "grounding_unavailable"] = "grounding_unavailable"
    grounding_disposition: str | None = None
    grounding_score: float = Field(ge=0.0, le=1.0)
    current_valid: bool
    value_status: ValuePortStatus = "value_pending_n8"
    value_decision_grade: Literal["blocked", "low", "medium", "high"] | None = None
    value_ref: str | None = None
    value_blockers: tuple[str, ...] = ()
    value_receipt: ValueGateReceipt | None = Field(default=None, exclude=True)
    certified_by_n9: bool = False
    front: FrontKind
    high_proxy: bool
    low_grounding: bool
    quarantine_action: QuarantineAction = "none"
    adversarial_validation_status: Literal[
        "not_required",
        "required_before_decision",
        "completed_shadow_only",
    ] = "not_required"
    counterexample_ref: str | None = None


class LoopVOIDecision(_StrictModel):
    """VOI scheduler decision projected to N6 loop actions."""

    candidate_id: str = Field(..., min_length=1)
    terminal_kind: str = Field(..., min_length=1)
    scheduler_action: str = Field(..., min_length=1)
    scheduler_reason: str = Field(..., min_length=1)
    priority: float
    next_action: LoopNextAction
    reason: str = Field(..., min_length=1)


class DesignRevisionRequest(_StrictModel):
    """Counterexample-driven revision request for the next cycle."""

    revision_id: str = Field(..., min_length=1)
    source_counterexample_ref: str = Field(..., min_length=1)
    source_terminal_kind: str = Field(..., min_length=1)
    previous_candidate_ref: str = Field(..., min_length=1)
    next_candidate_ref: str = Field(..., min_length=1)
    previous_grammar_elements: tuple[str, ...]
    new_grammar_elements: tuple[str, ...]
    next_grammar_elements: tuple[str, ...]
    revision_strategy: RevisionStrategy
    strategy_payload: dict[str, Any] = Field(default_factory=dict)
    revised_problem: DesignProblem
    revision_driver: Literal["counterexample"] = "counterexample"

    @property
    def introduced_grammar_elements(self) -> tuple[str, ...]:
        """Return grammar elements added by this revision."""

        previous = set(self.previous_grammar_elements)
        return tuple(item for item in self.next_grammar_elements if item not in previous)


def _cycle_acquisition_requirement(
    grounding: CandidateGroundingObservation,
    value_port: ValuePortObservation,
) -> AcquisitionRequirementGap | None:
    """Return the earliest-stage real acquisition requirement for one cycle."""

    return grounding.acquisition_requirement or value_port.acquisition_requirement


class GenerationCycleRecord(_StrictModel):
    """Replay-visible record for one real generate-ground-value-revise cycle."""

    cycle_index: int = Field(ge=0)
    design_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    grammar_elements: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    selected_candidate_ref: str = Field(..., min_length=1)
    selected_candidate_content_hash: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    grounding: CandidateGroundingObservation
    simulation: SimulationPortObservation
    value_port: ValuePortObservation
    terminal_kind: str = Field(..., min_length=1)
    counterexample: CounterexampleRecord
    refinement_decision: RefinementDecision
    search_iteration: SearchIteration
    voi_decision: LoopVOIDecision
    revision_request: DesignRevisionRequest
    driven_by_counterexample_ref: str | None = None
    introduced_grammar_elements: tuple[str, ...] = ()
    revision_driver: Literal["counterexample", "none"] = "none"
    acquisition_receipt: dict[str, Any] | None = None
    acquisition_routing_report: AcquisitionPlannerReport | None = None

    @model_validator(mode="after")
    def _bind_every_stage_to_selected_candidate(self) -> GenerationCycleRecord:
        selected = self.selected_candidate_ref
        if (
            selected not in self.candidate_ids
            or self.grounding.candidate_id != selected
            or self.simulation.candidate_id != selected
            or (
                self.value_port.candidate_id is not None
                and self.value_port.candidate_id != selected
            )
            or self.counterexample.candidate_ref != selected
        ):
            raise ValueError("cycle_stage_candidate_mismatch")
        requirement = _cycle_acquisition_requirement(
            self.grounding,
            self.value_port,
        )
        if requirement is None:
            return self
        metadata = requirement.metadata
        binding = metadata.get("candidate_binding")
        if not isinstance(binding, Mapping):
            return self
        if (
            binding.get("candidate_id") != selected
            or binding.get("candidate_content_hash") != self.selected_candidate_content_hash
            or binding.get("design_problem_ref") != self.design_problem_ref
        ):
            raise ValueError("cycle_acquisition_candidate_binding_mismatch")
        return self

    @model_validator(mode="after")
    def _routing_evidence_is_not_owner_evidence(self) -> GenerationCycleRecord:
        if self.acquisition_receipt is not None and self.acquisition_routing_report is not None:
            raise ValueError("acquisition_route_cannot_mint_owner_receipt")
        if self.acquisition_routing_report is None:
            return self
        if self.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            raise ValueError("acquisition_route_cannot_satisfy_terminal")
        requirement = _cycle_acquisition_requirement(
            self.grounding,
            self.value_port,
        )
        records = self.acquisition_routing_report.acquisition_records
        if requirement is None or len(records) != 1:
            raise ValueError("acquisition_route_requirement_mismatch")
        record = records[0]
        if (
            record.requirement_gap_ref != requirement.requirement_gap_id
            or record.compiled_requirement_ref != requirement.compiled_requirement_ref
            or record.claim_ref != requirement.claim_ref
        ):
            raise ValueError("acquisition_route_requirement_mismatch")
        return self


class StrangleReceipt(_StrictModel):
    """Recomputed receipt proving run_fixture is not the production N6 cycle."""

    status: Literal["strangled", "drift"]
    default_cycle_controller: str
    predecessor_ref: str = "runtime.quality.workspace.loop.WorkspaceLoop.run_fixture"
    allowed_fixture_callers: tuple[str, ...] = ()
    production_single_pass_callers: tuple[str, ...] = ()
    verified_by: str = GENERATION_CYCLE_CONTROLLER_REF

    @classmethod
    def recompute(cls, repo_root: Path | None = None) -> StrangleReceipt:
        """Scan source callers and return the current single-pass strangle state."""

        root = (repo_root or Path.cwd()).resolve()
        callers = _run_fixture_callers(root)
        production_callers = tuple(
            caller for caller in callers if not _is_allowed_fixture_caller(caller)
        )
        return cls(
            status="strangled" if not production_callers else "drift",
            default_cycle_controller=GENERATION_CYCLE_CONTROLLER_REF,
            allowed_fixture_callers=tuple(
                caller for caller in callers if _is_allowed_fixture_caller(caller)
            ),
            production_single_pass_callers=production_callers,
        )


class GenerationCycleRun(_StrictModel):
    """N6 run artifact containing cycles, fronts, ports, and strangle evidence."""

    schema_version: str = GENERATION_CYCLE_SCHEMA_VERSION
    run_id: str = Field(..., min_length=1)
    design_problem_ref: str = Field(..., pattern=r"^sha256:[0-9a-f]{64}$")
    controller_ref: str = GENERATION_CYCLE_CONTROLLER_REF
    engine_owner_ref: str = ENGINE_SIMPLE_OWNER_REF
    terminal_denominator: tuple[str, ...]
    cycles: tuple[GenerationCycleRecord, ...]
    acquisition_receipts: tuple[dict[str, Any], ...] = ()
    fronts: GenerationCycleFronts
    candidate_summaries: tuple[CandidateSummary, ...]
    value_port: ValuePortObservation
    promotion_port: PromotionPortObservation
    strangle_receipt: StrangleReceipt
    terminal_status: TerminalStatus = "completed"
    blocked_reason: str | None = None


class GenerationPort(Protocol):
    """Protocol for N4 candidate generation."""

    def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> Awaitable[object] | object:
        """Generate candidates for one cycle."""


class GroundingPort(Protocol):
    """Protocol for A-side candidate grounding."""

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: object,
    ) -> CandidateGroundingObservation:
        """Ground one candidate under A."""


class SimulationPort(Protocol):
    """Protocol for N5 joint simulation."""

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        """Simulate one selected candidate."""


class ValuePort(Protocol):
    """Protocol for N8 value gating."""

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        """Return an N8 value observation or a pending port."""


class PromotionPort(Protocol):
    """Protocol for N9 promotion."""

    def __call__(
        self,
        *,
        admitted_batch: core_contracts.PersistedPreN9AdmittedCandidateBatch,
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Return N9 certification state for candidates."""


class RevisionPolicy(Protocol):
    """Protocol for counterexample-driven revisions."""

    def __call__(
        self,
        *,
        problem: DesignProblem,
        prior_cycle: GenerationCycleRecord,
        counterexample: CounterexampleRecord,
        terminal_kind: str,
        default_revision: DesignRevisionRequest,
    ) -> DesignRevisionRequest:
        """Return the next revision request."""


@dataclass(frozen=True)
class _N4OwnerContextUnavailableResult:
    """Typed U4 refusal before a fixed Scientist vertical can become authority."""

    status: str = "cycle_substrate_context_unavailable"
    candidates: tuple[object, ...] = ()
    surrogate_rankings: tuple[object, ...] = ()
    grounding_dispositions: tuple[object, ...] = ()


class N4GenerationPort:
    """Default N4 port calling the real design generation owner."""

    def __init__(
        self,
        *,
        model_id: str,
        llm_client: object | None = None,
        repo_root: Path | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
    ) -> None:
        self._model_id = model_id
        self._llm_client = llm_client
        self._repo_root = repo_root
        self._cycle_substrate_context = cycle_substrate_context

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> object:
        """Call N4 generation for this cycle."""

        del cycle_index
        if self._cycle_substrate_context is None:
            return _N4OwnerContextUnavailableResult()
        from polisyos.runtime.quality.design_generation import (
            generate_design_candidate_bundle_under_a,
        )

        organ_run = await generate_design_candidate_bundle_under_a(
            problem,
            model_id=self._model_id,
            llm_client=self._llm_client,
            repo_root=self._repo_root,
            cycle_substrate_context=self._cycle_substrate_context,
        )
        return organ_run.result


class PolicyGroundingPort:
    """A-side grounding port reading N4 CGF firewall dispositions."""

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: object,
    ) -> CandidateGroundingObservation:
        """Resolve the generated candidate through N4's CGF disposition records."""

        del cycle_index
        candidate_id = _candidate_id(candidate)
        candidate_content_hash = _candidate_content_hash(candidate)
        design_problem_ref = _problem_ref(problem)
        authority_level = problem.authority_profile.requested_authority_level
        disposition = _grounding_disposition_for_candidate(
            candidate,
            generation_result=generation_result,
        )
        if disposition is None:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("cgf_disposition_missing",),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        owner_issues = _candidate_owner_validation_issues(candidate, disposition)
        if owner_issues:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=owner_issues,
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        raw_disposition = str(_object_get(disposition, "disposition") or "")
        if raw_disposition not in _grounding_disposition_denominator():
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("unknown_grounding_disposition", raw_disposition),
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                authority_level=authority_level,
            )
        chain = _object_get(disposition, "certificate_chain")
        certificate_refs = _certificate_refs(chain)
        proxy_gap_ref, quarantine_handoff_ref = _cg4_quarantine_refs(chain)
        bridge_codes = tuple(
            str(_object_get(record, "integration_status") or _object_get(record, "pattern") or "")
            for record in _sequence(_object_get(disposition, "bridge_missing_records"))
            if _object_get(record, "integration_status") or _object_get(record, "pattern")
        )
        issue_codes = _dedupe(
            (
                raw_disposition,
                *(
                    str(value)
                    for value in (
                        _object_get(disposition, "cg2_reason"),
                        _object_get(disposition, "cg3_reason"),
                    )
                    if value
                ),
                *bridge_codes,
                *(
                    ("cg4_proxy_gap:adversarial_validate",)
                    if proxy_gap_ref and quarantine_handoff_ref
                    else ()
                ),
            )
        )
        status, score = _grounding_status_and_score(
            raw_disposition,
            proxy_gap=bool(proxy_gap_ref),
        )
        grounding_ref = gy_content_hash(
            {
                "candidate_id": candidate_id,
                "disposition": _json_ready(disposition),
                "source": "cgf_firewall",
            }
        )
        acquisition_requirement = None
        if status not in {"current_valid", "grounded_shadow"}:
            acquisition_requirement = grounding_coverage_requirement_gap(
                candidate_id=candidate_id,
                candidate_content_hash=candidate_content_hash,
                design_problem_ref=design_problem_ref,
                issue_codes=issue_codes,
                evidence_refs=certificate_refs,
                authority_level=authority_level,
                grounding_report_ref=grounding_ref,
            )
        return CandidateGroundingObservation(
            candidate_id=candidate_id,
            status=status,
            grounding_score=score,
            issue_codes=issue_codes,
            evidence_refs=certificate_refs,
            current_valid=False,
            report_ref=grounding_ref,
            grounding_source="cgf_firewall",
            grounding_disposition=raw_disposition,
            cgf_certificate_refs=certificate_refs,
            quarantine_action=(
                "adversarial_validate" if proxy_gap_ref and quarantine_handoff_ref else "none"
            ),
            adversarial_validation_ref=(
                str(quarantine_handoff_ref) if quarantine_handoff_ref else None
            ),
            acquisition_requirement=acquisition_requirement,
        )


class JointSimulationPort:
    """Default N5 port calling the joint simulation controller when request data exists."""

    def __init__(
        self,
        controller: JointSimulationHorizonController | None = None,
        *,
        repo_root: Path | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
    ) -> None:
        self._controller = controller or JointSimulationHorizonController()
        self._repo_root = repo_root
        if cycle_substrate_context is not None:
            from polisyos.runtime.quality.cycle_substrate import (
                revalidate_cycle_substrate_context,
            )

            revalidate_cycle_substrate_context(cycle_substrate_context)
        self._cycle_substrate_context = cycle_substrate_context
        self._boundary_world_cache: dict[str, WorldModelRecord] = {}
        self._boundary_world_cache_index: dict[str, str] = {}

    def __call__(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        """Run N5 from a supplied request factory, otherwise return a pending port."""

        candidate_id = _candidate_id(candidate)
        factory = problem.runtime_hints.get("joint_simulation_request_factory")
        request = None
        if callable(factory):
            request = factory(candidate=candidate, problem=problem, cycle_index=cycle_index)
        elif problem.runtime_hints.get("joint_simulation_request") is not None:
            request = problem.runtime_hints["joint_simulation_request"]
        if request is None:
            world_record = None
            world_error_code: str | None = None
            diagnostics: dict[str, Any] = {
                "port": "N5",
                "reason": "joint_simulation_request_missing",
            }
            try:
                world_record = self._boundary_world_model_record(
                    candidate=candidate,
                    problem=problem,
                )
                diagnostics.update(
                    {
                        "world_model_record_id": world_record.world_model_record_id,
                        "world_model_record_content_hash": world_record.content_hash,
                        "world_model_source": (
                            "cycle_substrate_context"
                            if self._cycle_substrate_context is not None
                            else "real_substrate_registry_boundary"
                        ),
                        "simulation_status": "pending_full_joint_request",
                    }
                )
            except Exception as exc:
                world_error_code = str(
                    getattr(exc, "code", None) or "world_model_record_unavailable"
                )
                diagnostics.update(
                    {
                        "world_model_source": "unavailable",
                        "world_model_error_code": world_error_code,
                        "world_model_error": str(exc),
                    }
                )
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status=(
                    "simulation_pending_n5" if world_record is not None else "simulation_blocked"
                ),
                authority_blockers=tuple(
                    item
                    for item in (
                        "joint_simulation_request_missing",
                        world_error_code,
                    )
                    if item is not None
                ),
                diagnostics=diagnostics,
                k_world_ref_before=(
                    world_record.content_hash if world_record is not None else None
                ),
                k_world_ref_after=(world_record.content_hash if world_record is not None else None),
                world_model_record=world_record,
            )
        request = (
            request
            if isinstance(request, JointSimulationRequest)
            else JointSimulationRequest.model_validate(request)
        )
        try:
            request = self._request_with_verified_world_model(
                request=request,
                candidate=candidate,
                problem=problem,
            )
        except WorldModelRecordError as exc:
            source = (
                "cycle_substrate_context"
                if self._cycle_substrate_context is not None
                else "joint_simulation_request"
            )
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_blocked",
                authority_blockers=(exc.code,),
                diagnostics={
                    "port": "N5",
                    "reason": exc.code,
                    "world_model_source": source,
                    "world_model_error": str(exc),
                },
            )
        result = self._controller.run(request)
        k_world_ref = request.world_model_record.content_hash
        status, authority_blockers = _joint_simulation_port_outcome(result)
        return SimulationPortObservation(
            candidate_id=candidate_id,
            status=status,
            simulation_ref=result.receipt.payload_hash,
            uncertainty_kind=result.uncertainty_kind,
            authority_blockers=authority_blockers,
            diagnostics={
                "engine_decisions": [
                    item.model_dump(mode="json") for item in result.engine_decisions
                ],
                "trajectory_count": len(result.trajectories),
                "interaction_count": len(result.interaction_terms),
                "world_model_record_id": request.world_model_record.world_model_record_id,
                "world_model_record_content_hash": request.world_model_record.content_hash,
            },
            k_world_ref_before=k_world_ref,
            k_world_ref_after=k_world_ref,
            world_model_record=request.world_model_record,
        )

    def _request_with_verified_world_model(
        self,
        *,
        request: JointSimulationRequest,
        candidate: object,
        problem: DesignProblem,
    ) -> JointSimulationRequest:
        """Resolve every request/candidate ref against one concrete WMR object."""

        request_refs = (
            ("joint_simulation_request", request.world_model_record_ref),
            *tuple(
                (
                    f"joint_simulation_request.intervention_atoms[{index}]",
                    _object_get(atom, "world_model_record_ref"),
                )
                for index, atom in enumerate(getattr(request, "intervention_atoms", ()) or ())
            ),
        )
        if self._cycle_substrate_context is not None:
            context_record = self._context_world_model_record(
                candidate=candidate,
                problem=problem,
            )
            from polisyos.runtime.quality.cycle_substrate import (
                resolve_world_model_atom_identity,
            )

            for atom in getattr(request, "intervention_atoms", ()) or ():
                resolve_world_model_atom_identity(
                    atom=atom,
                    world_model_record=context_record,
                    expected_world_model_content_hash=context_record.content_hash,
                )
            accepted = {
                context_record.world_model_record_id,
                context_record.content_hash,
            }
            if (
                request.world_model_record.world_model_record_id
                != context_record.world_model_record_id
                or request.world_model_record.content_hash != context_record.content_hash
                or request.world_model_record_ref not in accepted
            ):
                raise WorldModelRecordError("cycle_substrate_request_wmr_mismatch")
            self._assert_world_model_reference_bindings(
                candidate=candidate,
                problem=problem,
                world_model_record=context_record,
                additional_refs=request_refs,
            )
            return request.model_copy(update={"world_model_record": context_record})
        from polisyos.runtime.quality.cycle_substrate import (
            resolve_world_model_atom_identity,
        )

        for atom in getattr(request, "intervention_atoms", ()) or ():
            resolve_world_model_atom_identity(
                atom=atom,
                world_model_record=request.world_model_record,
                expected_world_model_content_hash=request.world_model_record.content_hash,
            )
        self._assert_world_model_reference_bindings(
            candidate=candidate,
            problem=problem,
            world_model_record=request.world_model_record,
            additional_refs=request_refs,
        )
        return request

    def _context_world_model_record(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
    ) -> WorldModelRecord:
        """Return the exact verified context WMR and bind all supplied refs to it."""

        if self._cycle_substrate_context is None:
            raise WorldModelRecordError("cycle_substrate_context_missing")
        from polisyos.runtime.quality.cycle_substrate import (
            resolve_candidate_lever_world_identity,
            resolve_cycle_substrate_world_identity,
            revalidate_cycle_substrate_context,
        )

        context = revalidate_cycle_substrate_context(self._cycle_substrate_context)
        if context.design_problem_ref != _problem_ref(problem):
            raise WorldModelRecordError("cycle_substrate_design_problem_mismatch")
        if context.domain != problem.domain:
            raise WorldModelRecordError("cycle_substrate_problem_domain_mismatch")
        record = self._cycle_substrate_context.world_model_record
        atom = _object_get(candidate, "atom")
        if atom is None:
            if _object_get(candidate, "status") != "candidate_unbound":
                raise WorldModelRecordError(
                    "world_identity_unresolved",
                    "candidate atom is absent",
                )
            resolve_candidate_lever_world_identity(
                context,
                refusal=_object_get(candidate, "lever_resolution"),
            )
        else:
            resolve_cycle_substrate_world_identity(context, atom=atom)
        self._assert_world_model_reference_bindings(
            candidate=candidate,
            problem=problem,
            world_model_record=record,
        )
        return record

    @staticmethod
    def _assert_world_model_reference_bindings(
        *,
        candidate: object,
        problem: DesignProblem,
        world_model_record: WorldModelRecord,
        additional_refs: Sequence[tuple[str, object]] = (),
    ) -> None:
        """Reject every supplied loose WMR ref that does not resolve to the object."""

        atom = _object_get(candidate, "atom")
        supplied_refs = (
            (
                "problem.runtime_hints.world_model_record_ref",
                _runtime_hint_optional(problem, "world_model_record_ref"),
            ),
            ("candidate.world_model_record_ref", _object_get(candidate, "world_model_record_ref")),
            ("candidate.atom.world_model_record_ref", _object_get(atom, "world_model_record_ref")),
            *additional_refs,
        )
        accepted = {
            world_model_record.world_model_record_id,
            world_model_record.content_hash,
        }
        mismatches = tuple(
            f"{label}={value}"
            for label, value in supplied_refs
            if value is not None and str(value).strip() and str(value) not in accepted
        )
        if mismatches:
            raise WorldModelRecordError(
                "world_model_record_unresolved",
                ";".join(mismatches),
            )

    def _boundary_world_model_record(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
    ) -> WorldModelRecord:
        """Build a lightweight WMR boundary over the real substrate registry.

        This is not a replacement for the N3/N5 full simulation request. It is
        the fail-closed bridge that keeps N8 from treating an unwired request as
        an acquisition gap while the full joint simulation remains pending.
        """

        if self._cycle_substrate_context is not None:
            return self._context_world_model_record(
                candidate=candidate,
                problem=problem,
            )

        repo_root = (self._repo_root or Path.cwd()).resolve()
        outcome = _value_outcome_variable(candidate, problem) or "value_outcome"
        slots = tuple(_candidate_target_world_slots(candidate)) or (outcome,)
        registry = build_substrate_registry_from_existing_catalogs(repo_root)
        selected_entry_hashes = tuple(
            sorted(entry.entry_content_hash for entry in registry.entries)
        )
        cache_identity = {
            "design_problem_ref": _problem_ref(problem),
            "substrate_registry_content_hash": registry.content_hash,
            "selected_registry_entry_hashes": selected_entry_hashes,
            "outcome_hash": gy_content_hash(outcome),
            "policy_slot_hash": gy_content_hash(slots),
        }
        cache_index_key = gy_content_hash(cache_identity)
        cache_key = self._boundary_world_cache_index.get(cache_index_key)
        if cache_key is not None:
            record = self._boundary_world_cache[cache_key]
            self._assert_world_model_reference_bindings(
                candidate=candidate,
                problem=problem,
                world_model_record=record,
            )
            return record
        record = _build_boundary_world_model_record(
            repo_root=repo_root,
            problem=problem,
            outcome=outcome,
            policy_slot_ids=slots,
            substrate_registry=registry,
            selected_registry_entry_hashes=selected_entry_hashes,
        )
        cache_key = gy_content_hash(
            {
                **cache_identity,
                "world_model_record_content_hash": record.content_hash,
            }
        )
        self._boundary_world_cache[cache_key] = record
        self._boundary_world_cache_index[cache_index_key] = cache_key
        self._assert_world_model_reference_bindings(
            candidate=candidate,
            problem=problem,
            world_model_record=record,
        )
        return record


class PendingN8ValuePort:
    """Honest N8-pending value port."""

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        """Return a typed pending value state without fabricating value."""

        del candidate, simulation, problem, cycle_index
        return ValuePortObservation()


class ValueOwnerAccessError(ValueError):
    """Fail-closed owner access error for N8 value inputs."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        *,
        owner_access_ref: str | None = None,
        owner_gap_evidence: L1VariableAvailability | None = None,
    ) -> None:
        self.code = code
        self.owner_access_ref = owner_access_ref
        self.owner_gap_evidence = owner_gap_evidence
        detail = message or code
        if owner_access_ref:
            detail = f"{detail} owner_access_ref={owner_access_ref}"
        super().__init__(detail)


class ValueOwnerGateway(Protocol):
    """Owner access surface for N8 input materialization."""

    def load_value_data_profile(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> ValueDataProfile:
        """Load content-bound outcome rows without inventing treatment knowledge."""

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
        method_result: object,
        selected_method_fqn: str,
    ) -> Mapping[str, Any]:
        """Invoke S10 outcome-prediction owners for the Foundry method output."""

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> Mapping[str, Any]:
        """Derive a selection diagram from the source-to-target world relationship."""


@dataclass(frozen=True)
class RealValueOwnerGateway:
    """Production owner access for N8 value inputs."""

    repo_root: Path | None = None
    cycle_substrate_context: CycleSubstrateContext | None = None
    catalog_overlay_path: Path | None = None

    def load_value_data_profile(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> ValueDataProfile:
        """Load method-neutral rows through the real substrate owner."""

        del world_record
        outcome = _value_outcome_variable(candidate, problem)
        if outcome is None:
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                "candidate outcome/world slot is not bound to a substrate variable",
                owner_access_ref="substrate_owner://outcome_missing",
            )
        repo_root = (self.repo_root or Path.cwd()).resolve()
        try:
            from polisyos.runtime.quality.data_state_substrate import (
                l1_dcat_variable_availability,
            )

            availability = l1_dcat_variable_availability(
                repo_root,
                outcome,
                overlay_path=self.catalog_overlay_path,
            )
        except Exception as exc:
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                f"substrate owner access failed for {outcome}: {exc}",
                owner_access_ref="substrate_owner://l1_dcat_access_failed",
            ) from exc
        owner_access_ref = availability.coverage_ref
        if availability.status != "available":
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                (
                    f"substrate owner found no panel data for {outcome} "
                    f"(datasets={availability.dataset_count}, "
                    f"bindings={availability.metric_binding_count}, "
                    f"observations={availability.observation_count})"
                ),
                owner_access_ref=owner_access_ref,
                owner_gap_evidence=availability,
            )
        profile = _load_value_data_profile_from_l1_dcat(
            repo_root=repo_root,
            outcome=outcome,
            owner_access_ref=owner_access_ref,
            overlay_path=self.catalog_overlay_path,
        )
        if profile is None:
            raise ValueOwnerAccessError(
                "acquire_data:value_owner_rows_missing",
                f"substrate owner found {outcome} but no usable owner rows",
                owner_access_ref=owner_access_ref,
            )
        return profile

    def produce_forecast_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
        method_result: object,
        selected_method_fqn: str,
    ) -> Mapping[str, Any]:
        """Invoke S10 outcome-prediction contracts over the Foundry method output."""

        return _build_real_s10_forecast_inputs(
            candidate=candidate,
            problem=problem,
            world_record=world_record,
            method_result=method_result,
            selected_method_fqn=selected_method_fqn,
        )

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> Mapping[str, Any]:
        """Derive transport inputs through the selection-diagram owner."""

        treatment = _candidate_transport_treatment_variable(candidate)
        outcome = _candidate_transport_outcome_variable(candidate, problem)
        return {
            "selection_diagram": _build_candidate_selection_diagram(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
                query_treatment=treatment,
                query_outcome=outcome,
                cycle_substrate_context=self.cycle_substrate_context,
            ),
            "query_treatment": treatment,
            "query_outcome": outcome,
        }


FOUNDRY_VALUE_PORT_EVALUATOR_ID = core_components.ComponentId(
    "polisyos.runtime.quality.foundry_value_port@1.0.0"
)


def simulation_evaluation_input_ref(
    simulation: SimulationPortObservation,
) -> ArtifactRef | None:
    """Return the canonical reference for the actual N5 observation."""

    if (
        simulation.status != "joint_simulated"
        or not simulation.simulation_ref
        or simulation.authority_blockers
    ):
        return None
    try:
        return ArtifactRef(
            artifact_id=f"polisyos.runtime.n5.simulation.{simulation.candidate_id}",
            artifact_type="joint_simulation_observation",
            content_hash=simulation.simulation_ref,
            schema_ref="policyos.runtime.n5.joint_simulation_observation.v1",
            uri=f"runtime://n5/simulation/{simulation.candidate_id}",
            version="1.0.0",
        )
    except ValueError:
        return None


def simulation_value_execution_context(
    *,
    candidate: object,
    simulation: SimulationPortObservation,
    problem: DesignProblem,
) -> EvaluationExecutionContext:
    """Build an explicit certificate-free context from the actual N5 output."""

    input_ref = simulation_evaluation_input_ref(simulation)
    world = simulation.world_model_record
    if input_ref is None or world is None:
        raise ValueError("eval_safety_simulation_input_unresolved")
    candidate_id = _candidate_id(candidate)
    if simulation.candidate_id != candidate_id:
        raise ValueError("eval_safety_simulation_candidate_mismatch")
    world_hash = str(_object_get(world, "content_hash") or "")
    world_id = str(_object_get(world, "world_model_record_id") or "")
    if not world_hash or not world_id:
        raise ValueError("eval_safety_simulation_wmr_unresolved")
    design_problem_ref = _problem_ref(problem)
    intake_hash = gy_content_hash(
        {
            "candidate_id": candidate_id,
            "design_problem_ref": design_problem_ref,
            "simulation_input_ref": input_ref.model_dump(mode="json"),
            "world_model_record_content_hash": world_hash,
        }
    )
    intake_ref = ArtifactRef(
        artifact_id=f"polisyos.runtime.n6.simulation_intake.{candidate_id}",
        artifact_type="evaluation_attempt_intake",
        content_hash=intake_hash,
        schema_ref="policyos.runtime.eval_safety.intake.v1",
        uri=f"runtime://n6/simulation-intake/{candidate_id}",
        version="1.0.0",
    )
    return EvaluationExecutionContext(
        intake_ref=intake_ref,
        evaluator_owner_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID,
        design_problem_ref=design_problem_ref,
        evaluation_mode="simulate_only",
        candidate_ref=ArtifactRef(
            artifact_id=candidate_id,
            artifact_type="candidate",
            content_hash=_candidate_content_hash(candidate),
            schema_ref="policyos.runtime.candidate.v1",
            uri=f"runtime://candidate/{candidate_id}",
            version="1.0.0",
        ),
        world_model_record_ref=ArtifactRef(
            artifact_id=world_id,
            artifact_type="world_model_record",
            content_hash=world_hash,
            schema_ref="policyos.runtime.world_model_record.v1",
            uri=f"runtime://world-model/{world_id}",
            version="1.0.0",
        ),
        target_population_scope_ref=ArtifactRef(
            artifact_id=f"polisyos.runtime.n5.simulation_population.{candidate_id}",
            artifact_type="simulation_population_scope",
            content_hash=input_ref.content_hash,
            schema_ref="policyos.runtime.n5.simulation_population_scope.v1",
            uri=f"runtime://n5/simulation-population/{candidate_id}",
            version="1.0.0",
        ),
        rule_version="polisyos.runtime.eval_safety.simulation_only@1.0.0",
        intended_start_at=datetime.now(UTC),
        evaluation_input_refs=(input_ref,),
        evaluation_input_provenance=(
            EvaluationInputProvenance(
                input_ref=input_ref,
                input_class="simulation",
                predicate_provenance="recomputed",
            ),
        ),
        eval_safety_certificate_ref=None,
        eval_safety_revision_head_ref=None,
    )


class FoundryValuePort:
    """Default N8 port delegating value authority to Foundry and S10 owners."""

    def __init__(
        self,
        *,
        evaluation_context: EvaluationExecutionContext,
        eval_safety_verifier: EvalSafetyVerifierPort | None = None,
        owner_gateway: ValueOwnerGateway | None = None,
        data_trust: DataTrust | None = None,
        requested_method_fqn: str | None = None,
        observation_to_contract_manifest: object | None = None,
        runtime_budget_ms: float | None = None,
        repo_root: Path | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
    ) -> None:
        self._owner_gateway = owner_gateway or RealValueOwnerGateway(
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
        )
        self._evaluation_context = evaluation_context
        self._eval_safety_verifier = eval_safety_verifier
        self._data_trust = data_trust
        self._requested_method_fqn = requested_method_fqn
        self._observation_to_contract_manifest = observation_to_contract_manifest
        self._runtime_budget_ms = runtime_budget_ms
        self._cycle_substrate_context = cycle_substrate_context
        self._world_cache: dict[str, object] = {}

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        """Compute value over a named WMR or fail closed with typed blockers."""

        started = time.monotonic()
        del cycle_index
        candidate_id = _candidate_id(candidate)
        context = self._evaluation_context
        mode = context.evaluation_mode
        if context.evaluator_owner_id != FOUNDRY_VALUE_PORT_EVALUATOR_ID:
            return _blocked_value_observation(
                code="eval_safety_evaluator_owner_mismatch",
                reason="EvalSafety context is bound to another evaluator owner.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if context.design_problem_ref != _problem_ref(problem):
            return _blocked_value_observation(
                code="eval_safety_design_problem_binding_mismatch",
                reason="EvalSafety context does not bind this DesignProblem.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        actual_input_ref = simulation_evaluation_input_ref(simulation)
        actual_input_provenance = next(
            (
                row
                for row in context.evaluation_input_provenance
                if actual_input_ref is not None and row.input_ref == actual_input_ref
            ),
            None,
        )
        actual_input_is_bound = bool(
            actual_input_ref is not None
            and actual_input_ref in context.evaluation_input_refs
            and actual_input_provenance is not None
            and actual_input_provenance.predicate_provenance
            in {"recomputed", "independently_reconciled"}
        )
        if not actual_input_is_bound:
            return _blocked_value_observation(
                code=(
                    "eval_safety_simulation_provenance_mismatch"
                    if mode == "simulate_only"
                    else "eval_safety_execution_context_binding_mismatch"
                ),
                reason="EvalSafety context does not bind the actual N5 input.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if mode == "simulate_only":
            declared_inputs_are_simulation = (
                context.attempt_class == "simulation"
                and actual_input_provenance is not None
                and actual_input_provenance.input_class == "simulation"
            )
            actual_n5_is_simulation = bool(
                simulation.status == "joint_simulated"
                and simulation.simulation_ref
                and not simulation.authority_blockers
                and simulation.candidate_id == candidate_id
                and simulation.k_world_update_mode == "read_only_no_k_world_narrowing"
                and simulation.k_world_ref_before is not None
                and simulation.k_world_ref_before == simulation.k_world_ref_after
            )
            if not declared_inputs_are_simulation or not actual_n5_is_simulation:
                return _blocked_value_observation(
                    code="eval_safety_simulation_provenance_mismatch",
                    reason="simulate_only requires independently established simulation inputs.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
        if simulation.candidate_id != candidate_id:
            return _blocked_value_observation(
                code="value_candidate_simulation_mismatch",
                reason=(
                    "N8 refuses value evidence produced for a different candidate; "
                    f"candidate={candidate_id} simulation={simulation.candidate_id}."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        world_record, _cache_status, world_error = self._world_record_from_simulation(simulation)
        if world_error is not None or world_record is None:
            return _blocked_value_observation(
                code=world_error or "value_world_model_record_unwired",
                reason=(
                    "N8 production value requires the cycle's typed WorldModelRecord; "
                    "missing WMR is controller wiring, not an acquisition gap."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if mode != "simulate_only":
            if (
                context.candidate_ref.artifact_id != candidate_id
                or context.candidate_ref.content_hash != _candidate_content_hash(candidate)
                or context.world_model_record_ref.content_hash
                != str(_object_get(world_record, "content_hash"))
            ):
                return _blocked_value_observation(
                    code="eval_safety_execution_context_binding_mismatch",
                    reason="EvalSafety context does not bind this candidate and WMR.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
            verifier = self._eval_safety_verifier
            if verifier is None:
                return _blocked_value_observation(
                    code="eval_safety_verifier_unresolved",
                    reason="Non-simulation value work requires the verification-only safety port.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
            challenge = EvalSafetyAdmissionChallenge.fresh(
                consumer_component_id=FOUNDRY_VALUE_PORT_EVALUATOR_ID
            )
            admission = verifier.require_admission(context, challenge)
            if (
                not evaluation_safety_consumer_admission_is_verified(
                    admission, context, challenge
                )
                or context.eval_safety_certificate_ref is None
                or admission.certificate_ref is None
                or admission.current_revision_head_ref is None
                or context.eval_safety_revision_head_ref is None
                or bool(admission.blocker_codes)
                or admission.intake_ref != context.intake_ref
                or admission.certificate_ref != context.eval_safety_certificate_ref
                or admission.current_revision_head_ref
                != context.eval_safety_revision_head_ref
            ):
                return _blocked_value_observation(
                    code=(
                        admission.blocker_codes[0]
                        if admission.blocker_codes
                        else "eval_safety_consumer_admission_blocked"
                    ),
                    reason="EvalSafety consumer admission did not verify this exact context.",
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                )
        inputs = self._selection_inputs()
        data_trust = self._data_trust
        if mode in {"retrospective", "measurement_audit"} and data_trust is None:
            return _blocked_value_observation(
                code="data_trust_gate_missing",
                reason="Retrospective and measurement-audit value modes require DataTrust.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
            )
        if (
            self._cycle_substrate_context is not None
            and not _candidate_estimand_binding_is_unresolved(candidate)
        ):
            world_identity_error = _value_candidate_world_identity_error(
                cycle_substrate_context=self._cycle_substrate_context,
                candidate=candidate,
                world_record=world_record,
            )
            if world_identity_error is not None:
                return _blocked_value_observation(
                    code="world_identity_unresolved",
                    reason=world_identity_error,
                    mode=mode,
                    started=started,
                    candidate_id=candidate_id,
                    world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
                )
        try:
            method_state = self._owner_gateway.load_value_data_profile(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
            )
        except ValueOwnerAccessError as exc:
            acquisition_requirement = None
            if exc.owner_gap_evidence is not None:
                outcome = _value_outcome_variable(candidate, problem)
                if outcome != exc.owner_gap_evidence.variable_id:
                    return _blocked_value_observation(
                        code="value_owner_gap_evidence_mismatch",
                        reason=(
                            "L1 availability evidence names another outcome; "
                            f"expected={outcome} actual={exc.owner_gap_evidence.variable_id}."
                        ),
                        mode=mode,
                        started=started,
                        candidate_id=candidate_id,
                        world_model_record_content_hash=str(
                            _object_get(world_record, "content_hash")
                        ),
                    )
                acquisition_requirement = l1_variable_availability_requirement_gap(
                    candidate_id=candidate_id,
                    candidate_content_hash=_candidate_content_hash(candidate),
                    design_problem_ref=_problem_ref(problem),
                    availability=exc.owner_gap_evidence,
                    authority_level=problem.authority_profile.requested_authority_level,
                )
            return _blocked_value_observation(
                code=exc.code,
                reason=str(exc),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                acquisition_requirement=acquisition_requirement,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        if not isinstance(method_state, ValueDataProfile):
            return _blocked_value_observation(
                code="value_owner_data_profile_invalid",
                reason="N8 owner returned an unverified value-data profile.",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        selector_problem = _selector_problem_for_value_profile(problem, method_state)
        selection = _select_value_method(
            candidate=candidate,
            problem=selector_problem,
            inputs=inputs,
        )
        if selection.get("status") != "selected" or not selection.get("selected_method_fqn"):
            return _blocked_value_observation(
                code=_first_text(selection.get("blockers")) or "value_method_selection_blocked",
                reason=str(selection.get("reason") or "Foundry selector refused value method."),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=_optional_text(selection.get("selected_method_fqn")),
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            selection_receipt = MethodSelectionReceipt.model_validate(
                selection.get("selection_receipt")
            )
        except Exception as exc:
            return _blocked_value_observation(
                code="value_method_selection_authority_unresolved",
                reason=f"Foundry selector receipt was invalid: {exc}",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=_optional_text(selection.get("selected_method_fqn")),
                value_data_profile_content_hash=method_state.content_hash,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            selection_receipt.verify_selection_context(
                method_selection_context_hash(
                    candidate=candidate,
                    problem=selector_problem,
                    requested_method_fqn=_optional_text(inputs.get("method_fqn")),
                    observation_to_contract_manifest=inputs.get("observation_to_contract_manifest"),
                    runtime_budget_ms=(
                        float(inputs["runtime_budget_ms"])
                        if inputs.get("runtime_budget_ms") is not None
                        else None
                    ),
                )
            )
        except ValueError as exc:
            return _blocked_value_observation(
                code="value_method_selection_context_hash_mismatch",
                reason=f"Foundry selector receipt context did not match owner rows: {exc}",
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=selection_receipt.selected_method_fqn,
                value_data_profile_content_hash=method_state.content_hash,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        selected_method_fqn = selection_receipt.selected_method_fqn
        if _candidate_estimand_binding_is_unresolved(candidate):
            return _blocked_value_observation(
                code="method_estimand_binding_mismatch",
                reason=(
                    "The advisor selected a real method over owner-resolved outcome rows, "
                    "but the candidate_unbound intervention has no estimand binding."
                ),
                mode=mode,
                started=started,
                candidate_id=candidate_id,
                selected_method_fqn=selected_method_fqn,
                method_selection_receipt=selection_receipt,
                value_data_profile_content_hash=method_state.content_hash,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        return _blocked_value_observation(
            code="treatment_assignment_not_owner_derived",
            reason=(
                f"substrate owner resolved outcome rows for {method_state.outcome}, but no "
                "canonical owner-derived treatment assignment producer is registered; "
                "candidate and intervention-atom exposure fields are not world knowledge"
            ),
            mode=mode,
            started=started,
            selected_method_fqn=selected_method_fqn,
            method_selection_receipt=selection_receipt,
            value_data_profile_content_hash=method_state.content_hash,
            candidate_id=candidate_id,
            acquisition_requirement=value_input_world_knowledge_requirement_gap(
                claim_ref=f"value-claim:{candidate_id}"
            ),
            world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
        )

    def _selection_inputs(self) -> dict[str, Any]:
        return {
            "method_fqn": self._requested_method_fqn,
            "observation_to_contract_manifest": self._observation_to_contract_manifest,
            "runtime_budget_ms": self._runtime_budget_ms,
        }

    def _world_record_from_simulation(
        self,
        simulation: SimulationPortObservation,
    ) -> tuple[object | None, Literal["built", "reused"], str | None]:
        raw = simulation.world_model_record
        if raw is None:
            return None, "built", "value_world_model_record_unwired"
        try:
            record = (
                raw if isinstance(raw, WorldModelRecord) else WorldModelRecord.model_validate(raw)
            )
        except Exception as exc:
            return None, "built", f"world_model_record_invalid:{exc}"
        content_hash = str(record.content_hash)
        if content_hash in self._world_cache:
            return self._world_cache[content_hash], "reused", None
        self._world_cache[content_hash] = record
        return record, "built", None


@dataclass(frozen=True)
class _DefaultSimulationBoundFoundryValuePort:
    """Derive the default Foundry context only after the actual N5 output exists."""

    repo_root: Path | None
    cycle_substrate_context: CycleSubstrateContext | None

    def __call__(
        self,
        *,
        candidate: object,
        simulation: SimulationPortObservation,
        problem: DesignProblem,
        cycle_index: int,
    ) -> ValuePortObservation:
        try:
            context = simulation_value_execution_context(
                candidate=candidate,
                simulation=simulation,
                problem=problem,
            )
        except ValueError:
            return _blocked_value_observation(
                code="eval_safety_simulation_provenance_mismatch",
                reason="The actual N5 observation cannot establish simulation provenance.",
                mode="simulate_only",
                started=time.monotonic(),
                candidate_id=_candidate_id(candidate),
            )
        return FoundryValuePort(
            evaluation_context=context,
            repo_root=self.repo_root,
            cycle_substrate_context=self.cycle_substrate_context,
        )(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=cycle_index,
        )


class PendingN9PromotionPort:
    """Honest N9-pending promotion port."""

    def __call__(
        self,
        *,
        admitted_batch: core_contracts.PersistedPreN9AdmittedCandidateBatch,
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Return no certifications because N6 does not promote."""

        del admitted_batch, problem
        return PromotionPortObservation()


class CounterexampleDrivenRevisionPolicy:
    """Default S2-style revision policy that adds grammar from the prior counterexample."""

    def __call__(
        self,
        *,
        problem: DesignProblem,
        prior_cycle: GenerationCycleRecord,
        counterexample: CounterexampleRecord,
        terminal_kind: str,
        default_revision: DesignRevisionRequest,
    ) -> DesignRevisionRequest:
        """Return the default counterexample-driven revision."""

        del problem, prior_cycle, counterexample, terminal_kind
        return default_revision


@dataclass(frozen=True)
class _CheapSignal:
    expected_value_proxy: float
    expected_information_gain: float


@dataclass(frozen=True)
class _StageResult:
    cheap_signal: _CheapSignal
    feedback: dict[str, Any]


@dataclass(frozen=True)
class _VOIDecisionTicket:
    candidate_hash: str
    current_level: int
    next_level: int | None
    last_result: _StageResult
    stage_results: dict[int, _StageResult]
    context: dict[str, Any]


@dataclass(frozen=True)
class _GrammarFallbackAtom:
    intervention_id: str
    content_hash: str
    target_world_slots: tuple[str, ...]
    world_model_record_ref: str
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _GrammarFallbackCandidate:
    candidate_id: str
    atom: _GrammarFallbackAtom
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"
    generator_path: str = "grammar_fallback"


@dataclass(frozen=True)
class _GrammarFallbackRanking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "proposal_only"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _GrammarFallbackResult:
    status: str
    candidates: tuple[_GrammarFallbackCandidate, ...]
    surrogate_rankings: tuple[_GrammarFallbackRanking, ...]
    grounding_dispositions: tuple[object, ...] = ()
    fallback_reason: str = "llm_generation_unavailable"


@dataclass(frozen=True)
class _DispositionCandidate:
    """Internal route for a CGF disposition that correctly minted no atom."""

    candidate_id: str
    content_hash: str
    proposal_id: str
    grounding_disposition: str
    lever_resolution: InterventionLeverRefusal | None = None
    status: str = "candidate_unbound"
    generator_path: str = "n4_grounding_disposition"


class GenerationCycleController:
    """Thin N6 controller over SimpleLoopEngine and real generation organs."""

    def __init__(
        self,
        *,
        generation_port: GenerationPort | None = None,
        grounding_port: GroundingPort | None = None,
        simulation_port: SimulationPort | None = None,
        value_port: ValuePort | None = None,
        promotion_port: PromotionPort | None = None,
        epoch_subject_authority: core_contracts.EpochValidityPreN9SubjectAuthority | None = None,
        epoch_validity_gate: core_contracts.EpochValidityAuthorityGate | None = None,
        epoch_n9_evidence_resolver: core_contracts.EpochValidityN9EvidenceResolver | None = None,
        revision_policy: RevisionPolicy | None = None,
        voi_scheduler: SimpleVOIScheduler | None = None,
        acquisition_owner_gateway: object | None = None,
        repo_root: Path | None = None,
        model_id: str | None = None,
        cycle_substrate_context: CycleSubstrateContext | None = None,
        promotion_runtime: PromotionRuntime | None = None,
        authority_scope: Literal["production", "contract_testing"] = "production",
        generated_at: datetime | None = None,
        high_proxy_threshold: float = 0.8,
        low_grounding_threshold: float = 0.5,
    ) -> None:
        if generation_port is None and model_id is None:
            generation_port = _UnavailableGenerationPort()
        self._generation_port = generation_port or N4GenerationPort(
            model_id=str(model_id),
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
        )
        self._grounding_port = grounding_port or PolicyGroundingPort()
        self._simulation_port = simulation_port or JointSimulationPort(
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
        )
        self._value_port = value_port or _DefaultSimulationBoundFoundryValuePort(
            repo_root=repo_root,
            cycle_substrate_context=cycle_substrate_context,
        )
        if authority_scope == "production" and promotion_port is not None:
            raise ValueError("production_promotion_port_must_be_container_derived")
        if authority_scope == "production" and any(
            dependency is not None
            for dependency in (
                epoch_subject_authority,
                epoch_validity_gate,
                epoch_n9_evidence_resolver,
            )
        ):
            raise ValueError("production_epoch_dependencies_must_be_runtime_derived")
        if promotion_port is None:
            from polisyos.runtime.quality.promotion_sequence import CanonicalN9PromotionPort

            promotion_port = CanonicalN9PromotionPort(
                repo_root=repo_root,
                promotion_runtime=promotion_runtime,
                epoch_n9_evidence_resolver=(
                    epoch_n9_evidence_resolver
                    or getattr(promotion_runtime, "epoch_n9_evidence_resolver", None)
                ),
            )
        self._promotion_port = promotion_port
        self._promotion_runtime = promotion_runtime
        self._authority_scope = authority_scope
        self._epoch_subject_authority = epoch_subject_authority or getattr(
            promotion_runtime, "epoch_subject_authority", None
        )
        self._epoch_validity_gate = epoch_validity_gate or getattr(
            promotion_runtime, "epoch_validity_gate", None
        )
        self._epoch_n9_evidence_resolver = epoch_n9_evidence_resolver or getattr(
            promotion_runtime, "epoch_n9_evidence_resolver", None
        )
        self._open_world_resolver = getattr(
            promotion_port,
            "open_world_resolver",
            None,
        )
        self._revision_policy = revision_policy or CounterexampleDrivenRevisionPolicy()
        self._acquisition_owner_gateway = acquisition_owner_gateway
        self._voi_scheduler = voi_scheduler or SimpleVOIScheduler(
            stage_costs={3: Decimal("0.5"), 4: Decimal("1.0")},
            min_roi_threshold=1.0,
        )
        self._repo_root = repo_root
        self._cycle_substrate_context = cycle_substrate_context
        self._generated_at = generated_at
        self._high_proxy_threshold = high_proxy_threshold
        self._low_grounding_threshold = low_grounding_threshold
        self._engine = SimpleLoopEngine(
            [
                ("generate", self._generate_node),
                ("ground", self._ground_node),
                ("joint_value", self._joint_value_node),
                ("revise", self._revise_node),
            ],
            terminal_node="revise",
        )

    async def run(
        self,
        problem: DesignProblem,
        *,
        budget_state: BudgetState,
        min_cycles: int = 2,
        max_cycles: int = 3,
    ) -> GenerationCycleRun:
        """Run generate-ground-value-revise cycles until VOI or a blocker stops."""

        if max_cycles < 1:
            raise GenerationCycleError("max_cycles_must_be_positive")
        design_problem_ref = _problem_ref(problem)
        current_problem = problem
        cycles: list[GenerationCycleRecord] = []
        summaries: list[CandidateSummary] = []
        terminal_status: TerminalStatus = "completed"
        blocked_reason: str | None = None

        cycle_index = 0
        while True:
            if cycle_index >= max_cycles:
                terminal_status = "blocked"
                blocked_reason = "voi_safety_cap_reached_without_scheduler_stop"
                if cycles:
                    cycles[-1] = _blocked_cycle(cycles[-1], reason=blocked_reason)
                break
            previous = cycles[-1] if cycles else None
            cycle, cycle_summaries = await self._run_cycle(
                current_problem,
                cycle_index=cycle_index,
                budget_state=budget_state,
                previous_cycle=previous,
            )
            if previous is not None:
                fake_reason = _fake_cycle_reason(previous, cycle)
                if fake_reason is not None:
                    terminal_status = "blocked"
                    blocked_reason = fake_reason
                    cycle = _blocked_cycle(cycle, reason=fake_reason)
            acquisition_receipt: AcquisitionReceipt | None = None
            try:
                routing_report = self._plan_n7_requirement_gap_if_requested(
                    current_problem,
                    cycle=cycle,
                )
                if routing_report is not None:
                    cycle = _cycle_with_acquisition_routing_report(
                        cycle,
                        report=routing_report,
                    )
                else:
                    acquisition_receipt = self._run_n7_acquisition_if_requested(
                        current_problem,
                        cycle=cycle,
                    )
            except GenerationCycleError as exc:
                if exc.code not in _N7_ROUTING_FAILURE_CODES:
                    raise
                cycle = _cycle_with_n7_route_failure(cycle, reason=exc.code)
            if acquisition_receipt is not None:
                cycle, cycle_summaries = self._reenter_cycle_after_n7_acquisition(
                    current_problem,
                    cycle=cycle,
                    cycle_summaries=cycle_summaries,
                    acquisition_receipt=acquisition_receipt,
                    budget_state=budget_state,
                )
            cycles.append(cycle)
            summaries.extend(cycle_summaries)
            if terminal_status == "blocked":
                break
            if cycle.voi_decision.next_action != "advance":
                break
            try:
                enforce_no_retry_without_new_grammar(
                    previous_candidate_ref=cycle.selected_candidate_ref,
                    next_candidate_ref=cycle.revision_request.next_candidate_ref,
                    previous_grammar_elements=cycle.revision_request.previous_grammar_elements,
                    next_grammar_elements=cycle.revision_request.next_grammar_elements,
                    introduced_grammar_elements=(cycle.revision_request.new_grammar_elements),
                    design_problem=current_problem,
                )
            except GenerationCycleError as exc:
                terminal_status = "blocked"
                blocked_reason = exc.code
                cycles[-1] = _blocked_cycle(cycle, reason=exc.code)
                break
            current_problem = cycle.revision_request.revised_problem
            cycle_index += 1

        promotion = self._promote_completed_generation(
            summaries=tuple(summaries),
            problem=problem,
        )
        summaries = _apply_promotion_to_summaries(
            tuple(summaries),
            promotion,
            problem=problem,
            open_world_resolver=self._open_world_resolver,
        )
        fronts = _derive_fronts(tuple(summaries))
        run = GenerationCycleRun(
            run_id=f"generation_cycle_{design_problem_ref.removeprefix('sha256:')[:16]}",
            design_problem_ref=design_problem_ref,
            terminal_denominator=_terminal_denominator(),
            cycles=tuple(cycles),
            acquisition_receipts=tuple(
                cycle.acquisition_receipt for cycle in cycles if cycle.acquisition_receipt
            ),
            fronts=fronts,
            candidate_summaries=tuple(summaries),
            value_port=cycles[-1].value_port if cycles else ValuePortObservation(),
            promotion_port=promotion,
            strangle_receipt=StrangleReceipt.recompute(self._repo_root),
            terminal_status=terminal_status,
            blocked_reason=blocked_reason,
        )
        return run

    def _promote_completed_generation(
        self,
        *,
        summaries: tuple[CandidateSummary, ...],
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Run the fixed post-loop subject/gate strangle before canonical N9."""

        runtime = self._promotion_runtime
        if runtime is None:
            if self._authority_scope != "contract_testing":
                return PromotionPortObservation(
                    status="not_promoted",
                    reason="epoch_validity_refused:promotion_runtime_not_established",
                )
            # Arbitrary ports exist only in an explicit contract-testing lane.
            try:
                return self._promotion_port(  # type: ignore[call-arg]
                    summaries=summaries,
                    problem=problem,
                )
            except TypeError:
                return PromotionPortObservation(
                    status="not_promoted",
                    reason="epoch_validity_refused:promotion_runtime_not_established",
                )
        subject_authority = self._epoch_subject_authority
        gate = self._epoch_validity_gate
        if subject_authority is None or gate is None or self._epoch_n9_evidence_resolver is None:
            return PromotionPortObservation(
                status="not_promoted",
                reason="epoch_validity_refused:epoch_validity_owner_not_established",
            )
        from polisyos.runtime.quality.epoch_validity_cascade import (
            seal_pre_n9_admitted_candidate_batch,
        )
        from polisyos.runtime.quality.open_world_risk import (
            PromotionRuntimeBatch,
        )

        prepared = runtime._prepare_completed_generation(problem=problem, summaries=summaries)
        if not isinstance(prepared, PromotionRuntimeBatch):
            return PromotionPortObservation(
                status="not_promoted",
                reason=f"open_world_risk_refused:{prepared.code}",
            )
        admissions: list[core_contracts.PreN9AdmittedCandidate] = []
        aggregate = prepared.contexts.aggregate_context
        for bound in prepared.contexts.ordered_bound_members:
            subject = subject_authority.persist_for_n9(bound_member_ref=bound.bound_member_ref)
            gate_result = gate.reconcile_before_n9(subject_ref=subject.subject_ref)
            if isinstance(gate_result, core_contracts.EpochValidityGateNonReceipt):
                observations: tuple[PreN9OpenWorldRiskGateObservation, ...] = ()
                if gate_result.code == "policy_admission_missing":
                    observations = tuple(
                        PreN9OpenWorldRiskGateObservation(
                            ordinal=ordinal,
                            gate_payload=prepared.gates_by_candidate_id[
                                summary.candidate_id
                            ].model_dump(mode="json"),
                        )
                        for ordinal, summary in enumerate(summaries)
                    )
                return PromotionPortObservation(
                    status="not_promoted",
                    reason=f"epoch_validity_refused:{gate_result.code}",
                    pre_n9_open_world_gates=observations,
                )
            occurrence = runtime.context_repository.resolve_occurrence(
                occurrence_ref=bound.statement.candidate_occurrence_ref
            )
            admissions.append(
                core_contracts.PreN9AdmittedCandidate(
                    aggregate_context_ref=aggregate.context_ref,
                    aggregate_context_content_hash=aggregate.semantic_hash,
                    bound_member_ref=bound.bound_member_ref,
                    bound_member_content_hash=bound.bound_member_content_hash,
                    candidate_occurrence_ref=bound.statement.candidate_occurrence_ref,
                    candidate_occurrence_content_hash=(
                        core_contracts.c4_semantic_digest("candidate_occurrence", occurrence)
                    ),
                    subject_ref=subject.subject_ref,
                    subject_content_hash=subject.subject_content_hash,
                    gate_evidence_ref=gate_result.gate_evidence_ref,
                    gate_evidence_content_hash=gate_result.gate_evidence_content_hash,
                )
            )
        admitted_batch = seal_pre_n9_admitted_candidate_batch(
            store=runtime.store,
            denominator=prepared.candidate_denominator,
            contexts=prepared.contexts,
            admissions=admissions,
        )
        return self._promotion_port(admitted_batch=admitted_batch, problem=problem)

    def decide_next_action(
        self,
        *,
        candidate_id: str,
        proxy_score: float,
        voi_estimate: float,
        prior_terminal_kind: str,
        budget_state: BudgetState,
    ) -> LoopVOIDecision:
        """Project the VOI scheduler and prior terminal into the next loop action."""

        if prior_terminal_kind not in _terminal_denominator():
            return LoopVOIDecision(
                candidate_id=candidate_id,
                terminal_kind=str(prior_terminal_kind),
                scheduler_action="unsupported_terminal",
                scheduler_reason="unsupported_terminal",
                priority=0.0,
                next_action="blocked",
                reason="unsupported_terminal",
            )
        stage_result = _StageResult(
            cheap_signal=_CheapSignal(
                expected_value_proxy=max(float(proxy_score), 0.0),
                expected_information_gain=max(float(voi_estimate), 0.0),
            ),
            feedback={},
        )
        decision = self._voi_scheduler.prioritize(
            [
                _VOIDecisionTicket(
                    candidate_hash=candidate_id,
                    current_level=2,
                    next_level=3,
                    last_result=stage_result,
                    stage_results={2: stage_result},
                    context={},
                )
            ],
            budget_state,
            ParetoSnapshot(),
        )[0]
        if prior_terminal_kind in {
            SearchTerminalKind.ACQUISITION_REQUIRED.value,
            SearchTerminalKind.HUMAN_DECISION_REQUIRED.value,
            SearchTerminalKind.A_SPEC_GAP.value,
        }:
            next_action: LoopNextAction = "escalate"
            reason = f"terminal_requires_escalation:{prior_terminal_kind}"
        elif prior_terminal_kind in {
            SearchTerminalKind.FRONTIER_STABLE.value,
            SearchTerminalKind.BUDGET_EXHAUSTED.value,
            SearchTerminalKind.GROUNDED_ADMISSIBLE.value,
            SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE.value,
            SearchTerminalKind.GROUNDED_ABSTENTION.value,
        }:
            next_action = "stop"
            reason = f"terminal_stops_loop:{prior_terminal_kind}"
        elif decision.recommended_action == "advance":
            next_action = "advance"
            reason = "voi_scheduler_advanced"
        elif decision.recommended_action == "retry_cheaper":
            next_action = "escalate"
            reason = "voi_scheduler_retry_cheaper_requires_escalation"
        else:
            next_action = "stop"
            reason = f"voi_scheduler_stopped:{decision.recommended_action}"
        return LoopVOIDecision(
            candidate_id=candidate_id,
            terminal_kind=prior_terminal_kind,
            scheduler_action=decision.recommended_action,
            scheduler_reason=decision.reason,
            priority=decision.priority,
            next_action=next_action,
            reason=reason,
        )

    async def _run_cycle(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
        budget_state: BudgetState,
        previous_cycle: GenerationCycleRecord | None,
    ) -> tuple[GenerationCycleRecord, tuple[CandidateSummary, ...]]:
        state: dict[str, Any] = {
            "problem": problem,
            "cycle_index": cycle_index,
            "budget_state": budget_state,
            "previous_cycle": previous_cycle,
        }
        finished = await self._engine.run_async(state)
        return finished["cycle"], tuple(finished["candidate_summaries"])

    def _run_n7_acquisition_if_requested(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
    ) -> AcquisitionReceipt | None:
        if cycle.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            return None
        acquisition_request = cycle.revision_request.strategy_payload.get("acquisition_request")
        if not isinstance(acquisition_request, Mapping):
            return None
        specs = self._n7_data_requirement_specs(problem, acquisition_request=acquisition_request)
        world_snapshot = self._n7_world_snapshot(
            problem,
            cycle=cycle,
            acquisition_request=acquisition_request,
            specs=specs,
        )
        owner_gateway = self._n7_owner_gateway(problem)
        if not specs:
            return None

        return run_acquisition_closed_loop(
            run_id=f"n7-reentry:{problem.design_problem_id}:{cycle.cycle_index}",
            acquisition_request={**acquisition_request, "cycle_index": cycle.cycle_index},
            data_requirement_specs=tuple(specs),
            world_snapshot=world_snapshot,
            design_problem=problem,
            owner_gateway=owner_gateway,
            useful_design_rate_before=float(
                problem.runtime_hints.get("n7_useful_design_rate_before") or 0.0
            ),
            generated_at=self._generated_at,
        )

    def _plan_n7_requirement_gap_if_requested(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
    ) -> AcquisitionPlannerReport | None:
        """Route one typed requirement gap without fabricating acquired evidence."""

        if cycle.terminal_kind != SearchTerminalKind.ACQUISITION_REQUIRED.value:
            return None
        acquisition_request = cycle.revision_request.strategy_payload.get("acquisition_request")
        if not isinstance(acquisition_request, Mapping):
            return None
        raw_gap = acquisition_request.get("requirement_gap")
        if raw_gap is None:
            return None
        try:
            gap = AcquisitionRequirementGap.model_validate(raw_gap)
        except Exception as exc:
            raise GenerationCycleError(
                "n7_requirement_gap_invalid",
                str(exc),
            ) from exc
        return plan_requirement_gap_acquisition(
            run_id=(f"n7-routing:{problem.design_problem_id}:{cycle.cycle_index}"),
            requirement_gaps=(gap,),
            generated_at=self._generated_at,
        )

    def _n7_data_requirement_specs(
        self,
        problem: DesignProblem,
        *,
        acquisition_request: Mapping[str, Any],
    ) -> tuple[object, ...]:
        hinted = problem.runtime_hints.get("n7_data_requirement_specs")
        if hinted is not None:
            return tuple(hinted)
        explicit = acquisition_request.get("data_requirement_specs") or acquisition_request.get(
            "compiled_requirement_specs"
        )
        if isinstance(explicit, Sequence) and not isinstance(explicit, str | bytes | bytearray):
            return tuple(explicit)
        families = _n7_required_data_families(problem, acquisition_request)
        if not families:
            return ()
        report = DataRequirementCompiler().compile_for_scenario(
            {
                "scenario_id": problem.design_problem_id,
                "text": problem.problem_statement,
                "domain": problem.domain,
                "expected_evidence_contract": {
                    "admissible_data_source_families": list(families),
                },
            }
        )
        return tuple(report.specs)

    def _n7_world_snapshot(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
        acquisition_request: Mapping[str, Any],
        specs: Sequence[object],
    ) -> AcquisitionWorldSnapshot:
        hinted = problem.runtime_hints.get("n7_world_snapshot")
        if hinted is not None:
            return (
                hinted
                if isinstance(hinted, AcquisitionWorldSnapshot)
                else AcquisitionWorldSnapshot.model_validate(hinted)
            )
        families = _n7_required_families_from_specs(specs) or _n7_required_data_families(
            problem,
            acquisition_request,
        )
        registry = _n7_substrate_registry(
            problem,
            families=families,
            repo_root=self._repo_root or Path.cwd(),
            cycle_substrate_context=self._cycle_substrate_context,
        )
        context_world_ref = (
            self._cycle_substrate_context.world_model_record_content_hash
            if self._cycle_substrate_context is not None
            else None
        )
        world_ref_hint = _runtime_hint_optional(problem, "world_model_record_ref")
        world_ref = str(
            world_ref_hint or f"s0://substrate-registry/{registry.substrate_version_id}"
        )
        if context_world_ref is not None:
            world_ref = context_world_ref
        return AcquisitionWorldSnapshot(
            world_ref=world_ref,
            known_slots=families,
            dependency_index=dict.fromkeys(families, (cycle.selected_candidate_ref,)),
            design_revalidation_stages={
                cycle.selected_candidate_ref: (
                    "identification",
                    "calibration",
                    "value_set",
                    "grounding",
                )
            },
            substrate_registry=registry.model_dump(mode="json"),
            world_model_record_ref=(context_world_ref or world_ref_hint),
        )

    def _n7_owner_gateway(self, problem: DesignProblem) -> object:
        hinted = problem.runtime_hints.get("n7_owner_gateway")
        if hinted is not None:
            return hinted
        if self._acquisition_owner_gateway is not None:
            return self._acquisition_owner_gateway
        return RealAcquisitionOwnerGateway(repo_root=self._repo_root or Path.cwd())

    def _reenter_cycle_after_n7_acquisition(
        self,
        problem: DesignProblem,
        *,
        cycle: GenerationCycleRecord,
        cycle_summaries: tuple[CandidateSummary, ...],
        acquisition_receipt: AcquisitionReceipt,
        budget_state: BudgetState,
    ) -> tuple[GenerationCycleRecord, tuple[CandidateSummary, ...]]:
        receipt_payload = acquisition_receipt.model_dump(mode="json")
        rederived = _n7_rederived_grounding_for_candidate(
            acquisition_receipt,
            candidate_id=cycle.selected_candidate_ref,
        )
        if rederived is None:
            return (
                cycle.model_copy(update={"acquisition_receipt": receipt_payload}),
                cycle_summaries,
            )
        grounding = CandidateGroundingObservation(
            candidate_id=cycle.selected_candidate_ref,
            status=rederived.status,
            grounding_score=rederived.grounding_score,
            issue_codes=rederived.issue_codes,
            evidence_refs=rederived.evidence_refs,
            current_valid=rederived.status == "current_valid",
            report_ref=rederived.report_ref,
            grounding_source="cgf_firewall",
            grounding_disposition="shadow_bound",
            cgf_certificate_refs=rederived.evidence_refs,
        )
        prior_summary = next(
            (
                summary
                for summary in cycle_summaries
                if summary.candidate_id == cycle.selected_candidate_ref
            ),
            None,
        )
        proxy_score = prior_summary.proxy_score if prior_summary is not None else 0.0
        voi_estimate = prior_summary.voi_estimate if prior_summary is not None else 0.0
        terminal_kind = _select_terminal_kind(
            grounding=grounding,
            proxy_score=proxy_score,
            value_port=cycle.value_port,
        )
        counterexample = _counterexample_record(
            problem=problem,
            cycle_index=cycle.cycle_index,
            candidate_id=cycle.selected_candidate_ref,
            grounding=grounding,
            value_port=cycle.value_port,
        )
        revision = _default_revision_request(
            problem=problem,
            cycle_index=cycle.cycle_index,
            candidate_id=cycle.selected_candidate_ref,
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            grounding=grounding,
            value_port=cycle.value_port,
        )
        voi_decision = self.decide_next_action(
            candidate_id=cycle.selected_candidate_ref,
            proxy_score=proxy_score,
            voi_estimate=voi_estimate,
            prior_terminal_kind=terminal_kind,
            budget_state=budget_state,
        )
        selected_candidate = {
            "candidate_id": cycle.selected_candidate_ref,
            "content_hash": cycle.selected_candidate_content_hash,
            "atom": {
                "content_hash": cycle.selected_candidate_content_hash,
                "target_world_slots": rederived.source_slots,
                "world_model_record_ref": acquisition_receipt.grown_world_after_ref,
            },
        }
        reentered = _cycle_record(
            problem=problem,
            cycle_index=cycle.cycle_index,
            candidate_ids=cycle.candidate_ids,
            selected_candidate=selected_candidate,
            grounding=grounding,
            simulation=cycle.simulation,
            value_port=cycle.value_port,
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            revision=revision,
            voi_decision=voi_decision,
        ).model_copy(update={"acquisition_receipt": receipt_payload})
        return reentered, _n7_reentered_summaries(
            cycle_summaries,
            candidate_id=cycle.selected_candidate_ref,
            grounding=grounding,
            low_grounding_threshold=self._low_grounding_threshold,
        )

    async def _generate_node(self, state: dict[str, Any]) -> dict[str, Any]:
        result = self._generation_port(
            state["problem"],
            cycle_index=int(state["cycle_index"]),
        )
        if inspect.isawaitable(result):
            result = await result
        owner_candidates = tuple(getattr(result, "candidates", ()) or ())
        disposition_candidates = _disposition_candidates(
            result,
            existing_candidates=owner_candidates,
        )
        candidates = (*owner_candidates, *disposition_candidates)
        generation_channel: GenerationChannel = "n4_owner"
        if not candidates or (
            getattr(result, "status", None) != "generated" and not disposition_candidates
        ):
            result = _grammar_fallback_result(
                state["problem"],
                cycle_index=int(state["cycle_index"]),
                reason=str(getattr(result, "status", None) or "generation_unavailable"),
            )
            candidates = tuple(result.candidates)
            generation_channel = "grammar_fallback"
        if not candidates:
            raise GenerationCycleError("generation_unavailable")
        rankings = _ranking_by_candidate(result)
        selected = max(
            candidates,
            key=lambda candidate: rankings.get(_candidate_id(candidate), (0.0, 0.0))[0],
        )
        return {
            **state,
            "generation_result": result,
            "generation_channel": generation_channel,
            "candidates": candidates,
            "rankings": rankings,
            "selected_candidate": selected,
        }

    def _ground_node(self, state: dict[str, Any]) -> dict[str, Any]:
        problem = state["problem"]
        cycle_index = int(state["cycle_index"])
        grounding_by_candidate: dict[str, CandidateGroundingObservation] = {}
        summaries: list[CandidateSummary] = []
        for candidate in state["candidates"]:
            candidate_id = _candidate_id(candidate)
            grounding = self._grounding_port(
                candidate=candidate,
                problem=problem,
                cycle_index=cycle_index,
                generation_result=state["generation_result"],
            )
            grounding_by_candidate[candidate_id] = grounding
            proxy_score, voi_estimate = state["rankings"].get(candidate_id, (0.0, 0.0))
            high_proxy = proxy_score >= self._high_proxy_threshold
            low_grounding = (
                grounding.grounding_score < self._low_grounding_threshold
                or grounding.status in {"grounding_failed", "grounding_unavailable"}
            )
            front: FrontKind = (
                "quarantine"
                if grounding.quarantine_action == "adversarial_validate"
                or (high_proxy and low_grounding)
                else "research"
            )
            adversarial_status = "not_required"
            if front == "quarantine":
                adversarial_status = (
                    "completed_shadow_only"
                    if grounding.quarantine_action == "adversarial_validate"
                    and grounding.adversarial_validation_ref
                    else "required_before_decision"
                )
            summaries.append(
                CandidateSummary(
                    candidate_id=candidate_id,
                    content_hash=_candidate_content_hash(candidate),
                    cycle_index=cycle_index,
                    generation_channel=state["generation_channel"],
                    proxy_score=proxy_score,
                    voi_estimate=voi_estimate,
                    grounding_status=grounding.status,
                    grounding_source=grounding.grounding_source,
                    grounding_disposition=grounding.grounding_disposition,
                    grounding_score=grounding.grounding_score,
                    current_valid=grounding.current_valid,
                    front=front,
                    high_proxy=high_proxy,
                    low_grounding=low_grounding,
                    quarantine_action=grounding.quarantine_action,
                    adversarial_validation_status=adversarial_status,
                )
            )
        selected_id = _candidate_id(state["selected_candidate"])
        return {
            **state,
            "grounding_by_candidate": grounding_by_candidate,
            "selected_grounding": grounding_by_candidate[selected_id],
            "candidate_summaries": tuple(summaries),
        }

    def _joint_value_node(self, state: dict[str, Any]) -> dict[str, Any]:
        candidate = state["selected_candidate"]
        problem = state["problem"]
        cycle_index = int(state["cycle_index"])
        simulation = self._simulation_port(
            candidate=candidate,
            problem=problem,
            cycle_index=cycle_index,
        )
        value = self._value_port(
            candidate=candidate,
            simulation=simulation,
            problem=problem,
            cycle_index=cycle_index,
        )
        return {**state, "simulation": simulation, "value_port": value}

    def _revise_node(self, state: dict[str, Any]) -> dict[str, Any]:
        problem = state["problem"]
        cycle_index = int(state["cycle_index"])
        candidate = state["selected_candidate"]
        candidate_id = _candidate_id(candidate)
        grounding = state["selected_grounding"]
        proxy_score, voi_estimate = state["rankings"].get(candidate_id, (0.0, 0.0))
        terminal_kind = _select_terminal_kind(
            grounding=grounding,
            proxy_score=proxy_score,
            value_port=state["value_port"],
        )
        counterexample = _counterexample_record(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            grounding=grounding,
            value_port=state["value_port"],
        )
        default_revision = _default_revision_request(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            grounding=grounding,
            value_port=state["value_port"],
        )
        placeholder_cycle = _cycle_record(
            problem=problem,
            cycle_index=cycle_index,
            candidate_ids=tuple(_candidate_id(item) for item in state["candidates"]),
            selected_candidate=candidate,
            grounding=grounding,
            simulation=state["simulation"],
            value_port=state["value_port"],
            terminal_kind=terminal_kind,
            counterexample=counterexample,
            revision=default_revision,
            voi_decision=LoopVOIDecision(
                candidate_id=candidate_id,
                terminal_kind=terminal_kind,
                scheduler_action="pending",
                scheduler_reason="pending",
                priority=0.0,
                next_action="blocked",
                reason="pending",
            ),
        )
        revision = self._revision_policy(
            problem=problem,
            prior_cycle=placeholder_cycle,
            counterexample=counterexample,
            terminal_kind=terminal_kind,
            default_revision=default_revision,
        )
        next_action = self.decide_next_action(
            candidate_id=candidate_id,
            proxy_score=proxy_score,
            voi_estimate=voi_estimate,
            prior_terminal_kind=terminal_kind,
            budget_state=state["budget_state"],
        )
        decision = _refinement_decision(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            counterexample=counterexample,
            revision=revision,
            next_action=next_action,
        )
        iteration = _search_iteration(
            problem=problem,
            cycle_index=cycle_index,
            candidate_id=candidate_id,
            counterexample=counterexample,
            decision=decision,
            next_action=next_action,
        )
        cycle = placeholder_cycle.model_copy(
            update={
                "voi_decision": next_action,
                "refinement_decision": decision,
                "search_iteration": iteration,
                "revision_request": revision,
                "driven_by_counterexample_ref": _cycle_driver_ref(problem, counterexample),
                "introduced_grammar_elements": _cycle_introduced_grammar(problem),
                "revision_driver": (
                    "counterexample" if _cycle_driver_ref(problem, counterexample) else "none"
                ),
            }
        )
        summaries = tuple(
            _summary_with_value_observation(
                summary,
                value_port=state["value_port"],
                counterexample_ref=counterexample.counterexample_ref,
            )
            if summary.candidate_id == candidate_id
            else summary
            for summary in state["candidate_summaries"]
        )
        return {**state, "cycle": cycle, "candidate_summaries": summaries}


class _UnavailableGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> object:
        del problem, cycle_index
        raise GenerationCycleError(
            "generation_port_missing",
            "Provide N4GenerationPort(model_id=...) or an explicit generation port.",
        )


def enforce_no_retry_without_new_grammar(
    *,
    previous_candidate_ref: str,
    next_candidate_ref: str,
    previous_grammar_elements: Sequence[str],
    next_grammar_elements: Sequence[str],
    introduced_grammar_elements: Sequence[str],
    design_problem: DesignProblem | None = None,
) -> None:
    """Enforce the S2 no-retry-without-new-grammar discipline."""

    previous = tuple(previous_grammar_elements)
    next_items = tuple(next_grammar_elements)
    introduced = tuple(introduced_grammar_elements)
    actual_introduced = tuple(item for item in next_items if item not in set(previous))
    same_candidate = previous_candidate_ref == next_candidate_ref
    grammar_did_not_grow = set(next_items).issubset(set(previous)) or not actual_introduced
    if set(introduced) != set(actual_introduced):
        if not introduced and grammar_did_not_grow:
            pass
        else:
            raise GenerationCycleError("new_grammar_elements_not_introduced")
    if actual_introduced:
        if design_problem is None:
            raise GenerationCycleError("new_grammar_owner_missing")
        _validate_owned_grammar_elements(
            actual_introduced,
            design_problem=design_problem,
        )
    if same_candidate and grammar_did_not_grow:
        raise GenerationCycleError("no_retry_without_new_grammar")
    if grammar_did_not_grow:
        raise GenerationCycleError("no_retry_without_new_grammar")


def validate_generation_cycle_run(
    run: GenerationCycleRun | Mapping[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Behaviorally validate an N6 run artifact."""

    if not isinstance(run, GenerationCycleRun):
        try:
            run = GenerationCycleRun.model_validate(run)
        except ValueError as exc:
            return ({"code": "generation_cycle_run_invalid", "error": str(exc)},)
    issues: list[dict[str, Any]] = []
    if run.engine_owner_ref != ENGINE_SIMPLE_OWNER_REF:
        issues.append({"code": "parallel_loop_engine_used"})
    expected_denominator = _terminal_denominator()
    if run.terminal_denominator != expected_denominator:
        issues.append({"code": "terminal_denominator_not_derived"})
    if not run.cycles:
        issues.append({"code": "cycle_denominator_empty"})
    for index, cycle in enumerate(run.cycles):
        if cycle.terminal_kind not in expected_denominator:
            issues.append(
                {
                    "code": "unsupported_terminal_not_honest",
                    "cycle_index": index,
                    "terminal_kind": cycle.terminal_kind,
                }
            )
        expected_terminal_kind = _select_terminal_kind(
            grounding=cycle.grounding,
            proxy_score=0.0,
            value_port=cycle.value_port,
        )
        if cycle.terminal_kind != expected_terminal_kind:
            issues.append(
                {
                    "code": "incoherent_single_terminal_state",
                    "cycle_index": index,
                    "expected_terminal_kind": expected_terminal_kind,
                    "actual_terminal_kind": cycle.terminal_kind,
                }
            )
        if cycle.voi_decision.scheduler_action not in _scheduling_action_denominator() | {
            "pending",
            "blocked",
            "unsupported_terminal",
        }:
            issues.append(
                {
                    "code": "unknown_voi_action_not_fail_closed",
                    "cycle_index": index,
                    "scheduler_action": cycle.voi_decision.scheduler_action,
                }
            )
        try:
            expected_strategy = _revision_strategy_for_terminal_kind(
                cycle.revision_request.source_terminal_kind
            )
        except GenerationCycleError:
            expected_strategy = None
        if cycle.revision_request.revision_strategy != expected_strategy:
            issues.append(
                {
                    "code": "revision_not_terminal_driven",
                    "cycle_index": index,
                    "terminal_kind": cycle.revision_request.source_terminal_kind,
                    "expected_strategy": expected_strategy,
                    "actual_strategy": cycle.revision_request.revision_strategy,
                }
            )
        if (
            cycle.revision_request.strategy_payload.get("terminal_kind")
            != cycle.revision_request.source_terminal_kind
        ):
            issues.append(
                {
                    "code": "revision_not_terminal_driven",
                    "cycle_index": index,
                    "terminal_kind": cycle.revision_request.source_terminal_kind,
                    "payload_terminal_kind": cycle.revision_request.strategy_payload.get(
                        "terminal_kind"
                    ),
                }
            )
        try:
            _validate_owned_grammar_elements(
                cycle.revision_request.new_grammar_elements,
                design_problem=cycle.revision_request.revised_problem,
            )
        except GenerationCycleError as exc:
            issues.append(
                {
                    "code": exc.code,
                    "cycle_index": index,
                    "terminal_kind": cycle.revision_request.source_terminal_kind,
                }
            )
        if (
            cycle.simulation.k_world_ref_before is not None
            and cycle.simulation.k_world_ref_after is not None
            and cycle.simulation.k_world_ref_before != cycle.simulation.k_world_ref_after
        ):
            issues.append({"code": "k_sim_shrank_k_world", "cycle_index": index})
        if index > 0:
            previous = run.cycles[index - 1]
            if cycle.selected_candidate_content_hash == previous.selected_candidate_content_hash:
                issues.append({"code": "fake_cycle_same_candidate_repeated"})
            if cycle.driven_by_counterexample_ref != previous.counterexample.counterexample_ref:
                issues.append({"code": "cycle_two_not_counterexample_driven"})
            if not cycle.introduced_grammar_elements:
                issues.append({"code": "retry_without_new_grammar_admitted"})
        if cycle.voi_decision.next_action in {"stop", "escalate"} and index < len(run.cycles) - 1:
            issues.append({"code": "voi_scheduler_ignored_fixed_cycle_count"})
    if (
        run.terminal_status == "completed"
        and run.cycles
        and run.cycles[-1].voi_decision.next_action == "advance"
    ):
        issues.append({"code": "voi_scheduler_ignored_fixed_cycle_count"})
    all_ids = tuple(summary.candidate_id for summary in run.candidate_summaries)
    front_map = run.fronts.candidate_ids_by_front()
    front_ids = tuple(candidate_id for ids in front_map.values() for candidate_id in ids)
    if sorted(front_ids) != sorted(all_ids) or len(set(front_ids)) != len(front_ids):
        issues.append({"code": "fronts_do_not_cover_full_candidate_set"})
    summary_by_id = {summary.candidate_id: summary for summary in run.candidate_summaries}
    for candidate_id in run.fronts.decision.candidate_ids:
        summary = summary_by_id.get(candidate_id)
        if summary is None:
            continue
        if not (summary.certified_by_n9 and summary.current_valid):
            issues.append({"code": "decision_front_admitted_non_current_valid"})
        if _summary_value_blocks_promotion(summary):
            issues.append(
                {
                    "code": "value_blocked_candidate_promoted_to_decision_front",
                    "candidate_id": candidate_id,
                }
            )
        if summary.high_proxy and summary.adversarial_validation_status != "completed_shadow_only":
            issues.append(
                {
                    "code": "proxy_gap_candidate_promoted_without_adversarial_validate",
                    "candidate_id": candidate_id,
                }
            )
    for summary in run.candidate_summaries:
        if summary.grounding_status in {"current_valid", "grounded_shadow"} and (
            summary.grounding_source != "cgf_firewall" or not summary.grounding_disposition
        ):
            issues.append(
                {
                    "code": "grounding_bypassed_cgf_firewall",
                    "candidate_id": summary.candidate_id,
                }
            )
        if summary.front == "decision" and summary.generation_channel == "grammar_fallback":
            issues.append(
                {
                    "code": "coverage_depends_on_llm",
                    "candidate_id": summary.candidate_id,
                }
            )
        if summary.high_proxy and summary.low_grounding and summary.front != "quarantine":
            issues.append(
                {
                    "code": "proxy_gap_candidate_promoted_without_adversarial_validate",
                    "candidate_id": summary.candidate_id,
                }
            )
    if run.strangle_receipt.status != "strangled":
        issues.append({"code": "single_pass_fixture_survives_as_production_cycle"})
    if run.value_port.status == "value_ready" and not run.value_port.value_ref:
        issues.append({"code": "fabricated_value_without_n8"})
    if (
        run.promotion_port.status == "certified_current_valid"
        and not run.promotion_port.certified_candidate_ids
    ):
        issues.append({"code": "fabricated_promotion_without_n9"})
    observations = run.promotion_port.pre_n9_open_world_gates
    if observations and (
        len(observations) != len(run.candidate_summaries)
        or tuple(row.ordinal for row in observations) != tuple(range(len(run.candidate_summaries)))
    ):
        issues.append({"code": "pre_n9_open_world_gate_denominator_mismatch"})
    return tuple(issues)


def generation_cycle_terminal_state(run: GenerationCycleRun) -> SearchTerminalState:
    """Project one N6 run into the existing typed search-terminal contract."""

    if not run.cycles:
        return SearchTerminalState(
            kind=SearchTerminalKind.RECURSIVE_BLOCKED,
            reason="The canonical generation cycle emitted no executable cycle.",
            blocking_obligations=["cycle_denominator_empty"],
        )
    if run.terminal_status == "blocked":
        reason = run.blocked_reason or "generation_cycle_blocked"
        if reason == "voi_safety_cap_reached_without_scheduler_stop":
            return SearchTerminalState(
                kind=SearchTerminalKind.BUDGET_EXHAUSTED,
                reason="The N6 cycle safety cap was reached before scheduler closure.",
                blocking_obligations=[reason],
                budget_kind="cycle",
            )
        return SearchTerminalState(
            kind=SearchTerminalKind.RECURSIVE_BLOCKED,
            reason="The canonical generation cycle blocked before safe closure.",
            blocking_obligations=[reason],
        )

    last_cycle = run.cycles[-1]
    kind = SearchTerminalKind(last_cycle.terminal_kind)
    costed_plan: dict[str, Any] | None = None
    data_need_spec: dict[str, Any] | None = None
    if kind is SearchTerminalKind.ACQUISITION_REQUIRED:
        if last_cycle.acquisition_routing_report is not None:
            costed_plan = {
                "canonical_planner_report": (
                    last_cycle.acquisition_routing_report.model_dump(mode="json")
                )
            }
        requirement = _cycle_acquisition_requirement(
            last_cycle.grounding,
            last_cycle.value_port,
        )
        if requirement is not None:
            data_need_spec = requirement.model_dump(mode="json")
    blockers = list(last_cycle.grounding.issue_codes)
    blockers.extend(last_cycle.value_port.authority_blockers)
    return SearchTerminalState(
        kind=kind,
        reason="Terminal emitted by the canonical generation-cycle owner.",
        blocking_obligations=list(dict.fromkeys(blockers)),
        costed_plan=costed_plan,
        data_need_spec=data_need_spec,
    )


def _terminal_denominator() -> tuple[str, ...]:
    return tuple(item.value for item in SearchTerminalKind)


def _scheduling_action_denominator() -> set[str]:
    annotation = SchedulingDecision.model_fields["recommended_action"].annotation
    return {str(item) for item in get_args(annotation)}


def _front_denominator() -> tuple[str, ...]:
    return tuple(str(item) for item in get_args(FrontKind))


def _grounding_status_denominator() -> tuple[str, ...]:
    return tuple(str(item) for item in get_args(GroundingStatus))


def _grounding_disposition_denominator() -> tuple[str, ...]:
    return tuple(str(item) for item in get_args(GroundingDispositionKind))


def _revision_strategy_for_terminal_kind(terminal_kind: str) -> RevisionStrategy:
    if terminal_kind == SearchTerminalKind.ACQUISITION_REQUIRED.value:
        return "acquire_or_elicit"
    if terminal_kind == SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value:
        return "adversarial_validate"
    if terminal_kind == SearchTerminalKind.A_SPEC_GAP.value:
        return "spec_gap_reframe"
    if terminal_kind == SearchTerminalKind.GROUNDED_ABSTENTION.value:
        return "hold_abstain"
    if terminal_kind in {
        SearchTerminalKind.BUDGET_EXHAUSTED.value,
        SearchTerminalKind.FRONTIER_STABLE.value,
        SearchTerminalKind.GROUNDED_ADMISSIBLE.value,
        SearchTerminalKind.GROUNDED_PARTIAL_ADMISSIBLE.value,
    }:
        return "terminal_stop"
    if terminal_kind == SearchTerminalKind.HUMAN_DECISION_REQUIRED.value:
        return "human_escalation"
    if terminal_kind == SearchTerminalKind.TOOL_FAILURE.value:
        return "tool_repair"
    if terminal_kind == SearchTerminalKind.COMPOSITION_INVALID.value:
        return "composition_repair"
    if terminal_kind == SearchTerminalKind.RECURSIVE_BLOCKED.value:
        return "recursive_block"
    raise GenerationCycleError("unknown_terminal_kind", terminal_kind)


def _revision_strategy_grammar_element(
    problem: DesignProblem,
    *,
    strategy: RevisionStrategy,
    issue: str,
) -> str:
    lever = problem.candidate_lever_space.candidate_levers[0]
    return f"lever:{lever.lever_id}:{strategy}:{_slug(issue)}"


def _revision_grammar_elements(
    problem: DesignProblem,
    *,
    strategy: RevisionStrategy,
    issue: str,
) -> tuple[str, ...]:
    if strategy in {
        "adversarial_validate",
        "spec_gap_reframe",
        "tool_repair",
        "composition_repair",
        "recursive_block",
    }:
        return (
            _revision_strategy_grammar_element(
                problem,
                strategy=strategy,
                issue=issue,
            ),
        )
    return ()


def _revision_strategy_payload(
    *,
    strategy: RevisionStrategy,
    terminal_kind: str,
    issue: str,
    counterexample: CounterexampleRecord,
    new_grammar_elements: Sequence[str],
    cycle_index: int,
    acquisition_requirement: AcquisitionRequirementGap | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategy": strategy,
        "terminal_kind": terminal_kind,
        "issue": issue,
        "source_counterexample_ref": counterexample.counterexample_ref,
    }
    if strategy == "acquire_or_elicit":
        acquisition_request: dict[str, Any] = {
            "request_kind": "owner_grounding_evidence",
            "driver": issue,
            "counterexample_ref": counterexample.counterexample_ref,
            "cycle_index": cycle_index,
            "consumer_owner": "polisyos.runtime.quality.acquisition_planner",
            "reentry": "same_generation_cycle_index",
            "network_policy": "record_replay_required_for_routine_check",
        }
        if acquisition_requirement is not None:
            acquisition_request["requirement_gap"] = acquisition_requirement.model_dump(mode="json")
        payload["acquisition_request"] = acquisition_request
    elif strategy == "adversarial_validate":
        payload["adversarial_validation"] = {
            "counterexample_ref": counterexample.counterexample_ref,
            "grammar_constraints": tuple(new_grammar_elements),
        }
    elif strategy == "spec_gap_reframe":
        payload["spec_gap"] = {
            "missing_owner_signal": issue,
            "counterexample_ref": counterexample.counterexample_ref,
        }
    elif strategy == "hold_abstain":
        payload["hold_reason"] = "value_pending_n8_or_grounded_abstention"
    elif strategy == "terminal_stop":
        payload["stop_reason"] = terminal_kind
    else:
        payload["repair_scope"] = strategy
    return payload


def _validate_owned_grammar_elements(
    elements: Sequence[str],
    *,
    design_problem: DesignProblem,
) -> None:
    lever_ids = {lever.lever_id for lever in design_problem.candidate_lever_space.candidate_levers}
    strategies = {str(item) for item in get_args(RevisionStrategy)}
    for element in elements:
        parts = str(element).split(":")
        if len(parts) != 4 or parts[0] != "lever":
            raise GenerationCycleError("new_grammar_element_not_owned", str(element))
        _, lever_id, strategy, issue = parts
        if lever_id not in lever_ids or strategy not in strategies or not issue:
            raise GenerationCycleError("new_grammar_element_not_owned", str(element))


def _n7_required_data_families(
    problem: DesignProblem,
    acquisition_request: Mapping[str, Any],
) -> tuple[str, ...]:
    del problem
    families: list[str] = []

    def add(value: object) -> None:
        text = str(value or "").strip()
        if text and text not in families:
            families.append(text)

    for key in ("required_data_families", "world_slots", "target_world_slots"):
        raw = acquisition_request.get(key)
        if isinstance(raw, str):
            add(raw)
        elif isinstance(raw, Sequence):
            for item in raw:
                add(item)
    for key in ("target_world_slot", "world_slot"):
        add(acquisition_request.get(key))
    driver = str(acquisition_request.get("driver") or "")
    if driver.startswith("acquire_data:"):
        add(driver.split(":", 1)[1])
    return tuple(families)


def _n7_required_families_from_specs(specs: Sequence[object]) -> tuple[str, ...]:
    families: list[str] = []
    for spec in specs:
        payload = spec.model_dump(mode="json") if isinstance(spec, BaseModel) else spec
        if not isinstance(payload, Mapping):
            continue
        raw = payload.get("required_data_families")
        if isinstance(raw, str):
            values = (raw,)
        elif isinstance(raw, Sequence):
            values = tuple(raw)
        else:
            values = ()
        for item in values:
            text = str(item or "").strip()
            if text and text not in families:
                families.append(text)
    return tuple(families)


def _n7_substrate_registry(
    problem: DesignProblem,
    *,
    families: Sequence[str],
    repo_root: Path,
    cycle_substrate_context: CycleSubstrateContext | None = None,
) -> SubstrateRegistry:
    del families
    if cycle_substrate_context is not None:
        from polisyos.runtime.quality.cycle_substrate import (
            revalidate_cycle_substrate_context,
        )

        try:
            context = revalidate_cycle_substrate_context(cycle_substrate_context)
        except ValueError as exc:
            raise GenerationCycleError(
                "n7_cycle_substrate_context_invalid",
                str(exc),
            ) from exc
        if context.design_problem_ref != _problem_ref(problem) or context.domain != problem.domain:
            raise GenerationCycleError("n7_cycle_substrate_context_mismatch")
        return cycle_substrate_context.substrate_registry
    for key in ("substrate_registry", "s0_substrate_registry"):
        raw = problem.runtime_hints.get(key)
        if raw is not None:
            try:
                return SubstrateRegistry.model_validate(
                    raw.model_dump(mode="python") if isinstance(raw, SubstrateRegistry) else raw
                )
            except ValueError as exc:
                raise GenerationCycleError(
                    "n7_substrate_registry_invalid",
                    str(exc),
                ) from exc
    try:
        return build_substrate_registry_from_existing_catalogs(repo_root)
    except (SubstrateRegistryError, FileNotFoundError, ValueError) as exc:
        raise GenerationCycleError(
            "n7_substrate_registry_unresolved",
            str(exc),
        ) from exc


def _n7_rederived_grounding_for_candidate(
    receipt: AcquisitionReceipt,
    *,
    candidate_id: str,
) -> object | None:
    for row in receipt.grounding_rederivations:
        if row.design_id == candidate_id and row.status in {"current_valid", "grounded_shadow"}:
            return row
    return None


def _n7_reentered_summaries(
    summaries: tuple[CandidateSummary, ...],
    *,
    candidate_id: str,
    grounding: CandidateGroundingObservation,
    low_grounding_threshold: float,
) -> tuple[CandidateSummary, ...]:
    updated: list[CandidateSummary] = []
    low_grounding = grounding.grounding_score < low_grounding_threshold or grounding.status in {
        "grounding_failed",
        "grounding_unavailable",
    }
    for summary in summaries:
        if summary.candidate_id != candidate_id:
            updated.append(summary)
            continue
        front: FrontKind = "quarantine" if summary.high_proxy and low_grounding else "research"
        updated.append(
            summary.model_copy(
                update={
                    "grounding_status": grounding.status,
                    "grounding_source": grounding.grounding_source,
                    "grounding_disposition": grounding.grounding_disposition,
                    "grounding_score": grounding.grounding_score,
                    "current_valid": grounding.current_valid,
                    "front": front,
                    "low_grounding": low_grounding,
                    "quarantine_action": grounding.quarantine_action,
                    "adversarial_validation_status": (
                        "not_required"
                        if front != "quarantine"
                        else summary.adversarial_validation_status
                    ),
                }
            )
        )
    return tuple(updated)


def _value_outcome_variable(candidate: object, problem: DesignProblem) -> str | None:
    outcome = _object_get(_object_get(problem, "outcome_of_interest"), "target_variable")
    if outcome:
        return str(outcome)
    for slot in _candidate_target_world_slots(candidate):
        text = _optional_text(slot)
        if text:
            return text
    return None


def _candidate_target_world_slots(candidate: object) -> tuple[str, ...]:
    atom = _object_get(candidate, "atom")
    return tuple(
        str(slot)
        for slot in _sequence(_object_get(atom, "target_world_slots"))
        if _optional_text(slot)
    )


def _load_value_data_profile_from_l1_dcat(
    *,
    repo_root: Path,
    outcome: str,
    owner_access_ref: str,
    overlay_path: Path | None = None,
) -> ValueDataProfile | None:
    """Load deterministic owner rows without deriving an exposure assignment."""

    try:
        from polisyos.runtime.quality.substrate_registry import (
            default_substrate_catalog_paths,
        )
    except Exception as exc:  # pragma: no cover - local dependency surface.
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_rows_missing",
            f"substrate row loader dependencies unavailable: {exc}",
            owner_access_ref="substrate_owner://row_loader_dependency_missing",
        ) from exc

    dcat_path = default_substrate_catalog_paths(repo_root).l1_dcat_path
    if not dcat_path.exists():
        raise ValueOwnerAccessError(
            "acquire_data:value_owner_rows_missing",
            f"L1 DCAT catalog missing at {dcat_path}",
            owner_access_ref="substrate_owner://l1_dcat_missing",
        )
    selected_overlay = overlay_path or (
        data_forge_read_api.catalog.default_acquisition_overlay_path(repo_root)
    )
    con = data_forge_read_api.catalog.open_catalog_read_session(
        dcat_path,
        overlay_path=selected_overlay,
    )
    try:
        raw_rows = con.execute(
            """
            SELECT
              COALESCE(NULLIF(country_code, ''), 'unknown') AS unit_id,
              COALESCE(year, survey_year, wave) AS period_id,
              value,
              dataset_id,
              observation_id
            FROM ds_observations
            WHERE canonical_var = ?
              AND value IS NOT NULL
              AND COALESCE(year, survey_year, wave) IS NOT NULL
            ORDER BY unit_id, period_id, dataset_id, observation_id, value
            LIMIT 20000
            """,
            [outcome],
        ).fetchall()
    finally:
        con.close()
    grouped: dict[tuple[str, int], list[tuple[float, str, str]]] = {}
    for unit, period, value, dataset_id, observation_id in raw_rows:
        numeric_value = float(value)
        if not math.isfinite(numeric_value):
            continue
        grouped.setdefault((str(unit), int(period)), []).append(
            (numeric_value, str(dataset_id), str(observation_id))
        )
    owner_rows = tuple(
        _value_owner_row(
            outcome=outcome,
            unit_id=unit_id,
            period_id=period_id,
            source_rows=tuple(values),
        )
        for (unit_id, period_id), values in sorted(grouped.items())
    )
    if len(owner_rows) < 4:
        return None
    unit_count = len({row.unit_id for row in owner_rows})
    period_count = len({row.period_id for row in owner_rows})
    modalities = _derived_value_data_modalities(owner_rows)
    rows_payload = tuple(row.model_dump(mode="json") for row in owner_rows)
    payload = {
        "schema_version": "policyos.runtime.value_data_profile.v1",
        "outcome": outcome,
        "rows": rows_payload,
        "owner_row_count": len(owner_rows),
        "unit_count": unit_count,
        "period_count": period_count,
        "available_data_modalities": modalities,
        "treatment_assignment_status": "owner_assignment_unresolved",
        "owner_access_ref": owner_access_ref,
        "owner_rows_content_hash": gy_content_hash(rows_payload),
    }
    return ValueDataProfile.model_validate({**payload, "content_hash": gy_content_hash(payload)})


def _value_owner_row(
    *,
    outcome: str,
    unit_id: str,
    period_id: int,
    source_rows: tuple[tuple[float, str, str], ...],
) -> ValueOwnerRow:
    ordered = tuple(sorted(source_rows, key=lambda row: (row[1], row[2], row[0])))
    source_hashes = tuple(
        gy_content_hash(
            {
                "outcome": outcome,
                "unit_id": unit_id,
                "period_id": period_id,
                "value": value,
                "dataset_id": dataset_id,
                "observation_id": observation_id,
            }
        )
        for value, dataset_id, observation_id in ordered
    )
    outcome_value = math.fsum(value for value, _, _ in ordered) / len(ordered)
    row_payload = {
        "unit_id": unit_id,
        "period_id": period_id,
        "outcome_value": outcome_value,
        "source_row_content_hashes": source_hashes,
    }
    return ValueOwnerRow(
        **row_payload,
        row_content_hash=gy_content_hash(row_payload),
    )


def _candidate_estimand_binding_is_unresolved(candidate: object) -> bool:
    """Return only a conservative refusal signal; this can never grant authority."""

    disposition = str(_object_get(candidate, "grounding_disposition") or "")
    status = str(_object_get(candidate, "status") or "")
    return status == "candidate_unbound" or (bool(disposition) and disposition != "shadow_bound")


def _value_candidate_world_identity_error(
    *,
    cycle_substrate_context: CycleSubstrateContext,
    candidate: object,
    world_record: WorldModelRecord,
) -> str | None:
    """Resolve a bound candidate against the exact cycle world or explain refusal."""

    from polisyos.runtime.quality.cycle_substrate import (
        resolve_cycle_substrate_world_identity,
    )

    try:
        resolved_world = resolve_cycle_substrate_world_identity(
            cycle_substrate_context,
            atom=_object_get(candidate, "atom"),
        )
    except (TypeError, WorldModelRecordError) as exc:
        return f"N8 candidate world identity refused: {exc}"
    if resolved_world.world_model_record_content_hash != world_record.content_hash:
        return "N8 simulation WMR differs from the resolved candidate world."
    return None


def _build_boundary_world_model_record(
    *,
    repo_root: Path,
    problem: DesignProblem,
    outcome: str,
    policy_slot_ids: Sequence[str],
    substrate_registry: SubstrateRegistry | None = None,
    selected_registry_entry_hashes: Sequence[str] | None = None,
) -> WorldModelRecord:
    """Build one limited WMR from canonical registry evidence.

    An explicitly supplied registry has already crossed its owner's verification
    boundary and is consumed directly. The function never selects entries by a
    domain name; selected content hashes and ``DesignProblem`` scope determine
    the resulting world. When no registry is supplied, the canonical catalog
    owner is still used for existing first-vertical callers.
    """

    from polisyos.runtime.quality.world_model_record import (
        BranchMode,
        DataForgeBindingRef,
        FabricWorldRef,
        FoundryBindingRef,
        PolicySlotBinding,
        ResolvedSubstrateEntryRef,
        SimulationModelRef,
        SkgCausalPriorRef,
        SubstrateRegistryRef,
        world_model_record_content_hash,
    )

    registry = (
        SubstrateRegistry.model_validate(substrate_registry.model_dump(mode="python"))
        if substrate_registry is not None
        else build_substrate_registry_from_existing_catalogs(repo_root)
    )
    selected_hashes = tuple(
        dict.fromkeys(
            str(item)
            for item in (
                selected_registry_entry_hashes
                if selected_registry_entry_hashes is not None
                else (entry.entry_content_hash for entry in registry.entries)
            )
            if str(item).strip()
        )
    )
    if not selected_hashes:
        raise WorldModelRecordError("boundary_registry_entries_missing")
    raw_selected = tuple(
        str(item)
        for item in (selected_registry_entry_hashes or selected_hashes)
        if str(item).strip()
    )
    if len(raw_selected) != len(set(raw_selected)):
        raise WorldModelRecordError("boundary_registry_entry_duplicate")
    entries_by_hash = {entry.entry_content_hash: entry for entry in registry.entries}
    missing_hashes = sorted(set(selected_hashes).difference(entries_by_hash))
    if missing_hashes:
        raise WorldModelRecordError(
            "boundary_registry_entry_unresolved",
            ",".join(missing_hashes),
        )
    selected_entries = tuple(entries_by_hash[entry_hash] for entry_hash in sorted(selected_hashes))
    resolved_entries = tuple(
        ResolvedSubstrateEntryRef(
            source_id=entry.source_id,
            family_id=entry.family_id,
            layer=entry.layer,
            coverage_score=entry.coverage.coverage_score,
            trust_tier=entry.trust_tier.tier,
            trust_cap=entry.trust_tier.trust_cap,
            identification_mode=entry.identification_mode,
            schema_regime_id=entry.schema_regime.schema_regime_id,
            data_version=entry.data_version,
            snapshot_id=entry.snapshot_id,
            source_snapshot_id=entry.source_snapshot_id,
            entry_content_hash=entry.entry_content_hash,
        )
        for entry in selected_entries
    )
    registry_artifact_ref = (
        f"substrate-registry://{registry.substrate_version_id}/"
        f"{registry.content_hash.removeprefix('sha256:')}"
    )
    registry_ref = SubstrateRegistryRef(
        substrate_version_id=registry.substrate_version_id,
        content_hash=registry.content_hash,
        registry_artifact_ref=registry_artifact_ref,
        resolved_entries=resolved_entries,
    )
    slots = tuple(dict.fromkeys(str(slot) for slot in policy_slot_ids if str(slot).strip()))
    population_scope = "stakeholders:" + ",".join(
        sorted(stakeholder.stakeholder_id for stakeholder in problem.stakeholders)
    )
    resolution = str(problem.runtime_hints.get("world_resolution") or "entity_observation_period")
    slot_map = tuple(
        PolicySlotBinding(
            slot_id=slot,
            state_path=f"substrate.{problem.domain}.{slot}",
            entity_scope=population_scope,
            temporal_granularity=resolution,
        )
        for slot in (slots or (outcome,))
    )
    primary_entry = next(
        (entry for entry in selected_entries if entry.layer is SubstrateLayer.L2),
        selected_entries[0],
    )
    primary_source_ref = next(
        (
            str(ref)
            for ref in (*primary_entry.provenance_refs, *primary_entry.authority_refs)
            if str(ref).strip()
        ),
        f"substrate-source://{primary_entry.source_id}",
    )
    selected_query_digest = gy_content_hash(
        {
            "registry_content_hash": registry.content_hash,
            "selected_registry_entry_hashes": sorted(selected_hashes),
        }
    )
    scope_hash = gy_content_hash(
        {
            "problem_id": problem.design_problem_id,
            "domain": problem.domain,
            "outcome": outcome,
            "registry": registry.content_hash,
            "selected_registry_entry_hashes": sorted(selected_hashes),
            "slots": [binding.model_dump(mode="json") for binding in slot_map],
        }
    )
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "limited",
        "producer_ref": (
            "polisyos.runtime.quality.generation_cycle._build_boundary_world_model_record"
        ),
        "region_or_jurisdiction": problem.jurisdiction_time.region,
        "population_scope": population_scope,
        "policy_domain": problem.domain,
        "valid_time_scope": problem.jurisdiction_time.valid_time,
        "tx_time_scope": problem.jurisdiction_time.as_of,
        "resolution": resolution,
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root="repo://production_data",
            snapshot_id=registry.substrate_version_id,
            branch="observed",
            as_of_valid_time=problem.jurisdiction_time.valid_time,
            as_of_tx_time=problem.jurisdiction_time.as_of,
            world_query_policy="selected_substrate_registry_entries",
            provenance_manifest_ref=registry_artifact_ref,
            content_query_digest=selected_query_digest,
            content_query_row_count=len(selected_entries),
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=primary_entry.snapshot_id,
            release_id=primary_entry.data_version,
            role="domain",
            read_api_identity=primary_entry.source_id,
            snapshot_ref=primary_source_ref,
            merkle_root=f"registry:{registry.substrate_version_id}",
            data_hash=registry.content_hash,
            provenance_manifest_ref=registry_artifact_ref,
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=gy_content_hash({"boundary": "model_spec", "scope": scope_hash}),
            model_spec_hash=gy_content_hash({"boundary": "model_hash", "scope": scope_hash}),
            model_id="model_registry_boundary",
            data_snapshot_ref=gy_content_hash({"boundary": "data_snapshot", "scope": scope_hash}),
            registry_bundle_ref=gy_content_hash(
                {"boundary": "registry_bundle", "scope": scope_hash}
            ),
            assumptions=(
                {
                    "assumption": "full N3/N5 simulation request remains pending",
                    "status": "upstream_residual",
                },
            ),
            fidelity_level="boundary",
            calibration_ref=gy_content_hash({"boundary": "calibration", "scope": scope_hash}),
            calibrated=False,
        ),
        "foundry_binding_ref": FoundryBindingRef(
            input_bindings_ref=gy_content_hash({"boundary": "input_bindings", "scope": scope_hash}),
            bound_state_snapshot_ref=gy_content_hash(
                {"boundary": "bound_state_snapshot", "scope": scope_hash}
            ),
            mapping_rules_ref=gy_content_hash({"boundary": "mapping_rules", "scope": scope_hash}),
            state_slot_digest=gy_content_hash(
                {
                    "boundary": "state_slots",
                    "slots": [binding.model_dump(mode="json") for binding in slot_map],
                }
            ),
        ),
        "skg_causal_prior_ref": SkgCausalPriorRef(
            skg_snapshot_ref=primary_source_ref,
            skg_version_id=primary_entry.data_version,
            source_data_snapshot_id=primary_entry.source_snapshot_id,
        ),
        "substrate_registry_ref": registry_ref,
        "policy_slot_map": slot_map,
    }
    draft = WorldModelRecord.model_construct(
        world_model_record_id="world_model_record_0000000000000000",
        content_hash=gy_content_hash({"boundary": "placeholder", "scope": scope_hash}),
        **fields,
    )
    content_hash = world_model_record_content_hash(draft)
    return WorldModelRecord(
        world_model_record_id=f"world_model_record_{content_hash.removeprefix('sha256:')[:16]}",
        content_hash=content_hash,
        **fields,
    )


def _build_default_selection_diagram(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    cycle_substrate_context: CycleSubstrateContext | None,
) -> object:
    return _build_candidate_selection_diagram(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        query_treatment=_candidate_transport_treatment_variable(candidate),
        query_outcome=_candidate_transport_outcome_variable(candidate, problem),
        cycle_substrate_context=cycle_substrate_context,
    )


def _build_candidate_selection_diagram(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    query_treatment: str,
    query_outcome: str,
    cycle_substrate_context: CycleSubstrateContext | None,
) -> object:
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.transportability import (
        SelectionDiagramBuilder,
        measured_transport_severity,
    )
    from polisyos.runtime.quality.cycle_substrate import (
        revalidate_cycle_substrate_context,
    )

    if cycle_substrate_context is None:
        raise ValueOwnerAccessError(
            "acquire_data:transport_context_unresolved",
            "content-bound source/target transport context is absent",
            owner_access_ref="cycle_substrate_context://transport_context_missing",
        )
    try:
        context = revalidate_cycle_substrate_context(cycle_substrate_context)
    except ValueError as exc:
        raise ValueOwnerAccessError(
            "transport_context_invalid",
            str(exc),
            owner_access_ref="cycle_substrate_context://content_validation_failed",
        ) from exc
    expected_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    if context.design_problem_ref != expected_problem_ref or context.domain != problem.domain:
        raise ValueOwnerAccessError(
            "transport_context_problem_mismatch",
            "transport context is not bound to the active DesignProblem",
            owner_access_ref=context.content_hash,
        )
    if (
        context.world_model_record_content_hash != world_record.content_hash
        or context.world_model_record.world_model_record_id != world_record.world_model_record_id
    ):
        raise ValueOwnerAccessError(
            "transport_context_world_mismatch",
            "transport context is not bound to the active WorldModelRecord",
            owner_access_ref=context.content_hash,
        )
    transport = context.transport_context
    if transport is None:
        raise ValueOwnerAccessError(
            "acquire_data:transport_context_unresolved",
            "content-bound source/target transport measurements are absent",
            owner_access_ref=context.content_hash,
        )
    transport_covariates = tuple(observation.canonical_var for observation in transport.covariates)
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=list(dict.fromkeys((query_treatment, query_outcome, *transport_covariates))),
        edges=[
            CausalEdge(src=query_treatment, dst=query_outcome),
            *[CausalEdge(src=covariate, dst=query_outcome) for covariate in transport_covariates],
        ],
    )
    source_context = ContextProfile(
        context_id=transport.source_context_id,
        context_label=f"measured-source:{transport.source_context_id}",
        data_sources=[observation.source_row_content_hash for observation in transport.covariates],
    )
    target_context = ContextProfile(
        context_id=transport.target_context_id,
        context_label=f"measured-target:{transport.target_context_id}",
        data_sources=[observation.target_row_content_hash for observation in transport.covariates],
    )
    builder = SelectionDiagramBuilder(graph)
    for observation in transport.covariates:
        builder.add_measured_sigma_variable(
            observation.canonical_var,
            source_value=observation.source_value,
            target_value=observation.target_value,
            severity=measured_transport_severity(
                observation.source_value,
                observation.target_value,
            ),
            role=None,
            source_ref=observation.source_row_content_hash,
            target_ref=observation.target_row_content_hash,
        )
    return builder.build(
        source_context=source_context,
        target_context=target_context,
    )


def _candidate_transport_treatment_variable(candidate: object) -> str:
    atom = _object_get(candidate, "atom")
    raw = (
        _object_get(candidate, "treatment_variable")
        or _object_get(atom, "treatment_variable")
        or _object_get(atom, "intervention_id")
        or _candidate_id(candidate)
    )
    return _slug(str(raw))


def _candidate_transport_outcome_variable(candidate: object, problem: DesignProblem) -> str:
    return _slug(_value_outcome_variable(candidate, problem) or "value_outcome")


def _build_s10_forecast_inputs(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    method_result: object,
    selected_method_fqn: str,
    forecast_tier: str,
    calibration_status: str | None,
    policy_context_ref: str,
    expected_policy_context_ref: str,
    false_clear_counts: Mapping[str, int],
    calibration_evidence: Mapping[str, object] | None = None,
) -> Mapping[str, Any]:
    from datetime import UTC, datetime

    from polisyos.runtime.quality.design_axes.outcome_prediction import (
        build_forecast_calibration_record,
        build_forecast_support,
    )

    now = datetime(2026, 6, 2, tzinfo=UTC)
    outcome = _value_outcome_variable(candidate, problem) or "value_outcome"
    report = _method_report(method_result)
    evidence = dict(calibration_evidence or {})
    report_ref = gy_content_hash(
        {
            "method_fqn": selected_method_fqn,
            "point_estimate": str(_object_get(report, "point_estimate")),
            "confidence_interval": str(_object_get(report, "confidence_interval")),
            "calibration_evidence": evidence,
            "world_model_record_content_hash": world_record.content_hash,
        }
    )
    authority = _s10_value_authority_boundary()
    calibration_ref = (
        f"s10://n8/{report_ref.removeprefix('sha256:')}/calibration"
        if calibration_status is not None
        else None
    )
    calibration = None
    if calibration_status is not None:
        calibration = build_forecast_calibration_record(
            calibration_id=f"n8.calibration.{report_ref.removeprefix('sha256:')[:16]}",
            calibration_ref=calibration_ref,
            case_id=problem.design_problem_id,
            forecast_support_ref=f"s10://n8/{report_ref}/forecast-support",
            observable_subset_ref=f"s10://n8/{outcome}/observable-subset",
            prediction_ref=f"forecast://n8/{report_ref}",
            observed_outcome_ref=f"outcome://{outcome}/observed",
            historical_implementation_ref=f"implementation://{world_record.world_model_record_id}",
            evaluation_design_ref=f"eval://{selected_method_fqn}",
            credible_evaluation_evidence_ref=f"evidence://{report_ref}",
            counterfactual_credibility=str(
                evidence.get("counterfactual_credibility") or "credible"
            ),
            prediction_time=now,
            observation_time=now,
            policy_effective_time=now,
            data_valid_time=now,
            calibration_window_start=now,
            calibration_window_end=now,
            metric_name="observable_subset_calibration",
            denominator=int(evidence.get("denominator") or 0),
            numerator=int(evidence.get("numerator") or 0),
            pass_rate=float(evidence.get("pass_rate") or 0.0),
            calibration_threshold_ref="repo://architecture/policy_design_case/layer2_floor_governance.toml#s10",
            floor_passed=bool(evidence.get("floor_passed", calibration_status == "pass")),
            calibration_status=calibration_status,
            interval_coverage_metric=evidence.get("interval_coverage_metric"),
            calibration_error_metric=evidence.get("calibration_error_metric"),
            source_lineage_refs=[f"lineage://{world_record.world_model_record_id}/substrate"],
            method_lineage_refs=[f"lineage://{selected_method_fqn}"],
            floor_id="s10_calibration",
            authority_boundary=authority,
            may_not_use_for=authority["may_not_use_for"],
            rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
        )
    support_base_origin = (
        "simulation_only"
        if forecast_tier == "simulation_only_advisory"
        else "validated_local_model"
    )
    support_label = (
        "simulation_only_system_effect"
        if forecast_tier == "simulation_only_advisory"
        else "validated_local_dynamic_model"
    )
    support = build_forecast_support(
        support_id=f"n8.forecast-support.{report_ref.removeprefix('sha256:')[:16]}",
        support_ref=f"s10://n8/{report_ref}/forecast-support",
        case_id=problem.design_problem_id,
        source_design_record_ref=f"design://{problem.design_problem_id}",
        design_graph_ref=f"design-graph://{problem.design_problem_id}",
        prediction_context_ref=f"prediction-context://{world_record.world_model_record_id}",
        policy_context_ref=policy_context_ref,
        candidate_design_ref=f"candidate://{_candidate_id(candidate)}",
        baseline_design_ref=f"baseline://{problem.design_problem_id}",
        alternative_design_refs=[],
        prediction_horizon_ref=f"horizon://{world_record.valid_time_scope}",
        target_outcome_refs=[f"outcome://{outcome}"],
        jurisdiction_scope_ref=str(world_record.region_or_jurisdiction),
        s5_forecast_support_ref=f"s5://{report_ref}",
        s5_support_label=support_label,
        s5_base_origin=support_base_origin,
        s5_claim_scope="system_effect",
        s6_firewall_status_refs=[f"s6://{_candidate_id(candidate)}"],
        s6_limitation_refs=[],
        s8_value_choice_provenance_ref=f"s8://{problem.design_problem_id}/value-choice",
        s8_value_tradeoff_disclosure_ref=f"s8://{problem.design_problem_id}/tradeoff",
        source_contract_ref=f"source-contract://{world_record.world_model_record_id}/panel",
        method_validity_ref=f"method-validity://{selected_method_fqn}",
        sensitivity_analysis_ref=f"sensitivity://{report_ref}",
        dynamic_equilibrium_check_ref=f"equilibrium-check://{report_ref}",
        equilibrium_caveat_refs=[],
        strategic_response_caveat_refs=[],
        outcome_distribution_refs=[f"distribution://{report_ref}"],
        welfare_comparison_ref=f"welfare://{problem.design_problem_id}",
        forecast_tier=forecast_tier,
        forecast_authority_disposition_reason=str(
            evidence.get("forecast_authority_disposition_reason")
            or "S10 owner forecast over Foundry method output"
        ),
        method_family="foundry_causal",
        observable_subset_ref=f"s10://n8/{outcome}/observable-subset",
        calibration_record_ref=calibration_ref,
        uncertainty_interval_refs=[f"interval://{report_ref}/95"],
        limitation_refs=[],
        abstention_refs=[],
        authority_boundary=authority,
        may_not_use_for=authority["may_not_use_for"],
        rule_version_ref="policyos.layer2.s10.outcome_prediction.v1",
    )
    return {
        "forecast_support": support,
        "forecast_calibration_record": calibration,
        "policy_context_ref": expected_policy_context_ref,
        "forecast_integrity_report": {"false_clear_counts": dict(false_clear_counts)},
        "false_clear_counts": dict(false_clear_counts),
    }


def _build_real_s10_forecast_inputs(
    *,
    candidate: object,
    problem: DesignProblem,
    world_record: WorldModelRecord,
    method_result: object,
    selected_method_fqn: str,
) -> Mapping[str, Any]:
    report = _method_report(method_result)
    evidence = _s10_calibration_evidence_from_report(report)
    policy_context_ref = f"policy-context://{world_record.world_model_record_id}"
    return _build_s10_forecast_inputs(
        candidate=candidate,
        problem=problem,
        world_record=world_record,
        method_result=method_result,
        selected_method_fqn=selected_method_fqn,
        forecast_tier=str(evidence["forecast_tier"]),
        calibration_status=str(evidence["calibration_status"]),
        policy_context_ref=policy_context_ref,
        expected_policy_context_ref=policy_context_ref,
        false_clear_counts=evidence["false_clear_counts"],  # type: ignore[arg-type]
        calibration_evidence=evidence,
    )


def _s10_calibration_evidence_from_report(report: object | None) -> dict[str, object]:
    from polisyos.runtime.quality.design_axes.outcome_prediction import S10_FALSE_CLEAR_FIELDS

    false_clear_counts = dict.fromkeys(S10_FALSE_CLEAR_FIELDS, 0)
    if report is None:
        false_clear_counts["uncalibrated_observable_promotion_false_clear_count"] = 1
        return {
            "forecast_tier": "observable_calibrated",
            "calibration_status": "blocked",
            "denominator": 1,
            "numerator": 0,
            "pass_rate": 0.0,
            "floor_passed": False,
            "interval_coverage_metric": 0.0,
            "calibration_error_metric": 1.0,
            "counterfactual_credibility": "missing_report",
            "false_clear_counts": false_clear_counts,
            "forecast_authority_disposition_reason": (
                "S10 owner refused value because the Foundry report was missing."
            ),
        }
    point = _object_get(report, "point_estimate")
    interval = _object_get(report, "confidence_interval")
    standard_error = _object_get(report, "standard_error")
    diagnostics = tuple(_sequence(_object_get(report, "diagnostics")))
    finite_point = _is_finite_number(point)
    finite_interval = (
        isinstance(interval, Sequence)
        and not isinstance(interval, str | bytes | bytearray)
        and len(interval) == 2
        and all(_is_finite_number(item) for item in interval)
    )
    finite_se = standard_error is None or _is_finite_number(standard_error)
    diagnostics_pass = all(bool(_object_get(item, "passed", True)) for item in diagnostics)
    sample_size = max(1, int(_object_get(report, "sample_size") or 0))
    treated = int(_object_get(report, "n_treated") or 0)
    control = int(_object_get(report, "n_control") or 0)
    pre_periods = int(_object_get(report, "pre_periods") or 0)
    post_periods = int(_object_get(report, "post_periods") or 0)
    credible = (
        finite_point
        and finite_interval
        and finite_se
        and diagnostics_pass
        and treated > 0
        and control > 0
        and pre_periods > 0
        and post_periods > 0
    )
    if not credible:
        false_clear_counts["uncalibrated_observable_promotion_false_clear_count"] = 1
    interval_width = 0.0
    interval_coverage = 0.0
    relative_uncertainty = 1.0
    if finite_interval and isinstance(interval, Sequence):
        lower = float(interval[0])
        upper = float(interval[1])
        interval_width = abs(upper - lower)
        scale = max(abs(float(point or 0.0)), 1.0)
        relative_uncertainty = interval_width / scale
        interval_coverage = float(_object_get(report, "confidence_level") or 0.95)
    denominator = sample_size
    numerator = sample_size if credible else 0
    return {
        "forecast_tier": "observable_calibrated",
        "calibration_status": "pass" if credible else "limit",
        "denominator": denominator,
        "numerator": numerator,
        "pass_rate": numerator / denominator,
        "floor_passed": credible,
        "interval_coverage_metric": interval_coverage,
        "calibration_error_metric": min(relative_uncertainty, 1.0),
        "counterfactual_credibility": "credible" if credible else "limited",
        "false_clear_counts": false_clear_counts,
        "ci_width": interval_width,
        "standard_error": float(standard_error) if _is_finite_number(standard_error) else None,
        "forecast_authority_disposition_reason": (
            "S10 owner forecast support derived from Foundry CausalEffectReport "
            f"(finite_ci={finite_interval}, diagnostics_pass={diagnostics_pass}, "
            f"sample_size={sample_size}, ci_width={interval_width:.6g})."
        ),
    }


def _is_finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _s10_value_authority_boundary() -> dict[str, Any]:
    return {
        "authoritative_for": [
            "forecast_support_tiering",
            "observable_subset_calibration",
            "value_grounded_welfare_comparison",
        ],
        "may_not_use_for": [
            "production_recommendation",
            "production_claim_authority",
            "rollout_authority",
            "publication_authority",
            "claim_authority",
            "closeout_authority",
            "approval_authority",
            "scorecard_authority",
            "preference_learning_authority",
            "s11_calibration",
            "s12_envelope_growth",
            "s13_accountability_closure",
            "s14_universality",
        ],
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": ["policyos.layer2.s10.outcome_prediction.v1"],
    }


def _value_evaluation_mode(inputs: Mapping[str, Any]) -> EvaluationModeResolution:
    """Return the strict typed resolution for an untrusted N8 mode token."""

    raw = inputs.get("evaluation_mode")
    return resolve_evaluation_mode(raw if isinstance(raw, str) else None)


def _value_data_trust(inputs: Mapping[str, Any]) -> DataTrust | None:
    raw = inputs.get("data_trust")
    if raw is None:
        return None
    return raw if isinstance(raw, DataTrust) else DataTrust.model_validate(raw)


def _simulate_only_data_trust() -> DataTrust:
    return DataTrust(
        tier="simulate_only_shadow",
        trust_cap=0.6,
        trust_multiplier=0.6,
        min_coverage=0.0,
        max_coverage=1.0,
        promotion_floor=0.5,
        authority_ref="policyos.runtime.n8.simulate_only_shadow",
    )


def _blocked_value_observation(
    *,
    code: str,
    reason: str,
    mode: ValueEvaluationMode,
    started: float,
    candidate_id: str | None = None,
    calibration_receipt: ValueCalibrationReceipt | None = None,
    selected_method_fqn: str | None = None,
    method_selection_receipt: MethodSelectionReceipt | None = None,
    value_data_profile_content_hash: str | None = None,
    acquisition_requirement: AcquisitionRequirementGap | None = None,
    world_model_record_content_hash: str | None = None,
    transport_receipt: ValueTransportReceipt | None = None,
) -> ValuePortObservation:
    return ValuePortObservation(
        status="value_blocked",
        candidate_id=candidate_id,
        value_ref=None,
        authority_blockers=(code,),
        reason=reason,
        evaluation_mode=mode,
        selected_method_fqn=selected_method_fqn,
        method_selection_receipt=method_selection_receipt,
        value_data_profile_content_hash=value_data_profile_content_hash,
        acquisition_requirement=acquisition_requirement,
        decision_grade="blocked",
        world_model_record_content_hash=world_model_record_content_hash,
        transport_receipt=transport_receipt,
        calibration_receipt=calibration_receipt,
        wall_time_ms=(time.monotonic() - started) * 1000.0,
    )


def _value_calibration_receipt(
    *,
    inputs: Mapping[str, Any],
    world_record: object,
) -> ValueCalibrationReceipt:
    raw_support = inputs.get("forecast_support")
    if raw_support is None:
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier="blocked",
            issue_codes=("forecast_support_missing",),
        )
    try:
        from polisyos.runtime.quality.design_axes.outcome_prediction import (
            ForecastCalibrationRecord,
            ForecastSupport,
            verify_prediction_authority_envelope,
        )

        support = (
            raw_support
            if isinstance(raw_support, ForecastSupport)
            else ForecastSupport.model_validate(raw_support)
        )
        raw_calibration = inputs.get("forecast_calibration_record") or inputs.get(
            "calibration_record"
        )
        calibration = None
        if raw_calibration is not None:
            calibration = (
                raw_calibration
                if isinstance(raw_calibration, ForecastCalibrationRecord)
                else ForecastCalibrationRecord.model_validate(raw_calibration)
            )
        envelope = verify_prediction_authority_envelope(
            forecast_support=support,
            calibration_record=calibration,
        )
    except Exception as exc:
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier="blocked",
            issue_codes=("uncalibrated_forecast_minted_value", str(exc)),
        )
    false_clear_counts = _false_clear_counts(inputs)
    if any(count > 0 for count in false_clear_counts.values()):
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=("uncalibrated_forecast_minted_value",),
        )
    expected_policy_context = _optional_text(inputs.get("policy_context_ref"))
    if expected_policy_context and support.policy_context_ref != expected_policy_context:
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=("regime_laundered_forecast_minted_value",),
        )
    if support.forecast_tier == "observable_calibrated":
        if calibration is None or calibration.calibration_status != "pass":
            return ValueCalibrationReceipt(
                status="blocked",
                forecast_tier=support.forecast_tier,
                calibration_record_ref=support.calibration_record_ref,
                uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
                false_clear_counts=false_clear_counts,
                issue_codes=("uncalibrated_forecast_minted_value",),
            )
    elif support.forecast_tier != "transported_limited":
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=("uncalibrated_forecast_minted_value",),
        )
    if envelope.envelope_status != "pass":
        return ValueCalibrationReceipt(
            status="blocked",
            forecast_tier=support.forecast_tier,
            calibration_record_ref=support.calibration_record_ref,
            uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
            false_clear_counts=false_clear_counts,
            issue_codes=tuple(envelope.issue_codes) or ("uncalibrated_forecast_minted_value",),
        )
    del world_record
    return ValueCalibrationReceipt(
        status="pass",
        forecast_tier=support.forecast_tier,
        calibration_record_ref=support.calibration_record_ref,
        uncertainty_interval_refs=tuple(support.uncertainty_interval_refs),
        false_clear_counts=false_clear_counts,
    )


def _false_clear_counts(inputs: Mapping[str, Any]) -> dict[str, int]:
    raw = inputs.get("false_clear_counts")
    if not isinstance(raw, Mapping):
        report = inputs.get("forecast_integrity_report")
        if isinstance(report, Mapping):
            raw = report.get("false_clear_counts")
        else:
            raw = getattr(report, "false_clear_counts", None)
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): max(0, int(value or 0)) for key, value in raw.items()}


def _select_value_method(
    *,
    candidate: object,
    problem: object,
    inputs: Mapping[str, Any],
) -> dict[str, Any]:
    try:
        from polisyos.foundry.methods.selection import select_value_method_for_problem
    except ImportError as exc:
        return {
            "status": "blocked",
            "blockers": ("value_method_selector_unavailable",),
            "reason": str(exc),
        }
    return select_value_method_for_problem(
        candidate=candidate,
        problem=problem,
        requested_method_fqn=_optional_text(inputs.get("method_fqn")),
        observation_to_contract_manifest=inputs.get("observation_to_contract_manifest"),
        runtime_budget_ms=(
            float(inputs["runtime_budget_ms"])
            if inputs.get("runtime_budget_ms") is not None
            else None
        ),
    )


def _selector_problem_for_value_profile(
    problem: DesignProblem,
    profile: ValueDataProfile,
) -> Mapping[str, object]:
    """Bind method selection to the exact owner-derived data profile."""

    return _selector_problem_with_owner_context(
        problem,
        {
            "value_required_data_modalities": profile.available_data_modalities,
            "value_data_characteristics": {
                "n_obs": profile.owner_row_count,
                "n_units": profile.unit_count,
                "n_periods": profile.period_count,
                "is_panel": "panel" in profile.available_data_modalities,
                "treatment_is_binary": None,
                "outcome_is_continuous": None,
            },
            "value_data_profile_content_hash": profile.content_hash,
        },
    )


def _selector_problem_with_owner_context(
    problem: DesignProblem,
    context: Mapping[str, object],
) -> DesignProblem:
    """Project owner data context without discarding problem authority."""

    return problem.model_copy(update={"runtime_hints": dict(context)})


def _run_value_transport(
    *,
    inputs: Mapping[str, Any],
    world_record: object,
) -> tuple[ValueTransportReceipt | None, str | None]:
    raw_diagram = inputs.get("selection_diagram")
    if raw_diagram is None:
        return None, "transport_selection_diagram_missing"
    try:
        from polisyos.foundry.methods.catalog.causal.transport_engine import (
            solve_transportability,
        )
        from polisyos.ir.analytics.transportability import (
            SelectionDiagram,
            TransportabilityStatus,
        )

        diagram = (
            raw_diagram
            if isinstance(raw_diagram, SelectionDiagram)
            else SelectionDiagram.model_validate(raw_diagram)
        )
        result = solve_transportability(
            selection_diagram=diagram,
            query_treatment=str(inputs.get("query_treatment") or "X"),
            query_outcome=str(inputs.get("query_outcome") or "Y"),
            solver_mode=str(inputs.get("transport_solver_mode") or "auto"),
            allow_degraded_transport=False,
        )
        if result.status is TransportabilityStatus.UNSUPPORTED:
            return None, "untransportable_forecast_minted_value"
        world_hash = str(_object_get(world_record, "content_hash"))
        transport_ref = gy_content_hash(result.model_dump(mode="json"))
        status: Literal["transported_limited", "direct", "blocked"] = (
            "direct" if not diagram.s_nodes else "transported_limited"
        )
        return (
            ValueTransportReceipt(
                status=status,
                world_model_record_id=str(_object_get(world_record, "world_model_record_id")),
                world_model_record_content_hash=world_hash,
                transport_result_ref=transport_ref,
                transport_status=str(result.status.value),
                transport_mode=str(result.transport_mode.value),
                identification_engine=result.identification_engine,
                required_target_data=tuple(str(item) for item in result.required_target_data),
                limitation_refs=tuple(str(item) for item in result.warnings),
            ),
            None,
        )
    except Exception as exc:
        return None, f"untransportable_forecast_minted_value:{exc}"


def _value_outer_set_from_foundry_result(
    *,
    method_result: object,
    transport_receipt: ValueTransportReceipt,
    calibration_receipt: ValueCalibrationReceipt,
    world_record: object,
    data_trust: DataTrust,
) -> ValueOuterSet:
    report = _method_report(method_result)
    if report is None:
        raise ValueError("foundry_method_refused_value:report_missing")
    point = getattr(report, "point_estimate", None)
    interval = getattr(report, "confidence_interval", None)
    if point is None or interval is None:
        raise ValueError("foundry_method_refused_value:uncertainty_missing")
    point_value = float(point)
    lower_ci, upper_ci = (float(interval[0]), float(interval[1]))
    identification_status = _derive_value_identification_status(
        transport_receipt=transport_receipt,
        calibration_receipt=calibration_receipt,
    )
    if identification_status == "point":
        lower = upper = point_value
    elif identification_status == "proxy":
        half_width = max(abs(upper_ci - lower_ci) / 2.0, abs(point_value) * 0.1, 0.01)
        lower = point_value - half_width
        upper = point_value + half_width
    else:
        lower = lower_ci
        upper = upper_ci
        if lower == upper:
            lower -= 0.01
            upper += 0.01
    method_name = str(getattr(report, "method", "foundry_value"))
    world_hash = str(_object_get(world_record, "content_hash"))
    return ValueOuterSet.interval_box(
        coordinates=(method_name,),
        lower=(lower,),
        upper=(upper,),
        identification_mode=identification_status,
        assumptions=(
            "foundry_method_output",
            f"transport:{transport_receipt.transport_status}",
            f"forecast_tier:{calibration_receipt.forecast_tier}",
        ),
        assumption_status=(
            "declared" if identification_status == "proxy" else "externally_supported"
        ),
        calibration_scope={
            "forecast_tier": calibration_receipt.forecast_tier,
            "transport_status": transport_receipt.transport_status,
            "transport_mode": transport_receipt.transport_mode,
        },
        data_trust=data_trust,
        world_model_record_ref=world_hash,
        epoch=str(_object_get(world_record, "valid_time_scope") or world_hash),
        representation_status="certified",
    )


def _derive_value_identification_status(
    *,
    transport_receipt: ValueTransportReceipt,
    calibration_receipt: ValueCalibrationReceipt,
) -> ValueOuterSetIdentificationStatus:
    if calibration_receipt.forecast_tier == "transported_limited":
        return "proxy"
    if transport_receipt.status == "transported_limited":
        return "partial"
    if transport_receipt.transport_status in {
        "partially_identified",
        "bounded_non_identified",
    }:
        return "partial"
    return "point"


def _method_report(method_result: object) -> object | None:
    output = getattr(method_result, "output", None)
    if isinstance(output, Mapping):
        return output.get("report")
    return None


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _first_text(value: object) -> str | None:
    values = _sequence(value)
    for item in values:
        text = _optional_text(item)
        if text:
            return text
    return None


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _problem_ref(problem: DesignProblem) -> str:
    return gy_content_hash(problem.model_dump(mode="json"))


def _runtime_hint_optional(problem: DesignProblem, key: str) -> object | None:
    return problem.runtime_hints.get(key, None)


def _candidate_id(candidate: object) -> str:
    return str(
        _object_get(candidate, "candidate_id") or _object_get(candidate, "id") or "candidate"
    )


def _candidate_content_hash(candidate: object) -> str:
    atom = _object_get(candidate, "atom")
    provenance = _object_get(candidate, "provenance")
    value = (
        _object_get(atom, "content_hash")
        or _object_get(candidate, "content_hash")
        or _object_get(provenance, "content_hash")
    )
    if isinstance(value, str) and value.startswith("sha256:"):
        return value
    return gy_content_hash(_json_ready(_candidate_id(candidate)))


def _grounding_disposition_for_candidate(
    candidate: object,
    *,
    generation_result: object,
) -> object | None:
    candidate_id = _candidate_id(candidate)
    candidate_hash = _candidate_content_hash(candidate)
    for disposition in _sequence(_object_get(generation_result, "grounding_dispositions")):
        disposition_candidate_id = _object_get(disposition, "candidate_id")
        proposal_id = _object_get(disposition, "proposal_id")
        raw_candidate_hash = _object_get(disposition, "raw_candidate_hash")
        shadow_hash = _object_get(disposition, "shadow_atom_content_hash")
        if disposition_candidate_id and str(disposition_candidate_id) == candidate_id:
            return disposition
        if (
            proposal_id
            and str(proposal_id) == candidate_id
            and raw_candidate_hash
            and str(raw_candidate_hash) == candidate_hash
        ):
            return disposition
        if shadow_hash and str(shadow_hash) == candidate_hash:
            return disposition
    return None


def _candidate_owner_validation_issues(
    candidate: object,
    disposition: object,
) -> tuple[str, ...]:
    issues: list[str] = []
    candidate_id = _candidate_id(candidate)
    disposition_candidate_id = _object_get(disposition, "candidate_id")
    if disposition_candidate_id and str(disposition_candidate_id) != candidate_id:
        issues.append("candidate_cgf_id_mismatch")
    raw_disposition = str(_object_get(disposition, "disposition") or "")
    if raw_disposition != "shadow_bound":
        proposal_id = str(_object_get(disposition, "proposal_id") or "")
        raw_candidate_hash = str(_object_get(disposition, "raw_candidate_hash") or "")
        if proposal_id != candidate_id:
            issues.append("candidate_cgf_proposal_id_mismatch")
        if raw_candidate_hash != _candidate_content_hash(candidate):
            issues.append("candidate_cgf_raw_hash_mismatch")
        return tuple(_dedupe(issues))
    atom = _object_get(candidate, "atom")
    if atom is None:
        issues.append("candidate_atom_missing")
        return tuple(issues)
    target_world_slots = tuple(
        str(item) for item in _sequence(_object_get(atom, "target_world_slots", ()))
    )
    if not target_world_slots:
        issues.append("candidate_owner_target_missing")
    world_ref = _object_get(atom, "world_model_record_ref")
    if world_ref and str(world_ref).startswith("world_model_record_pending:"):
        issues.append("candidate_world_model_ref_pending")
    if raw_disposition == "shadow_bound":
        shadow_hash = _object_get(disposition, "shadow_atom_content_hash")
        if shadow_hash and str(shadow_hash) != _candidate_content_hash(candidate):
            issues.append("candidate_cgf_content_hash_mismatch")
        if not shadow_hash:
            issues.append("candidate_cgf_shadow_hash_missing")
    return tuple(_dedupe(issues))


def _disposition_candidates(
    result: object,
    *,
    existing_candidates: Sequence[object],
) -> tuple[_DispositionCandidate, ...]:
    """Project every usable non-binding N4 disposition into the N6 denominator."""

    existing_ids = {_candidate_id(candidate) for candidate in existing_candidates}
    existing_hashes = {_candidate_content_hash(candidate) for candidate in existing_candidates}
    projected: list[_DispositionCandidate] = []
    for disposition in _sequence(_object_get(result, "grounding_dispositions")):
        disposition_kind = str(_object_get(disposition, "disposition") or "")
        if (
            disposition_kind not in _grounding_disposition_denominator()
            or disposition_kind == "shadow_bound"
        ):
            continue
        proposal_id = str(_object_get(disposition, "proposal_id") or "")
        raw_candidate_hash = str(_object_get(disposition, "raw_candidate_hash") or "")
        if not proposal_id or not re.fullmatch(r"sha256:[0-9a-f]{64}", raw_candidate_hash):
            continue
        candidate_id = str(_object_get(disposition, "candidate_id") or proposal_id)
        if candidate_id in existing_ids or raw_candidate_hash in existing_hashes:
            continue
        projected.append(
            _DispositionCandidate(
                candidate_id=candidate_id,
                content_hash=raw_candidate_hash,
                proposal_id=proposal_id,
                grounding_disposition=disposition_kind,
                lever_resolution=_verified_candidate_lever_refusal(disposition),
            )
        )
        existing_ids.add(candidate_id)
        existing_hashes.add(raw_candidate_hash)
    return tuple(projected)


def _verified_candidate_lever_refusal(
    disposition: object,
) -> InterventionLeverRefusal | None:
    """Return a strict content-bound L6 refusal or fail closed to no witness."""

    raw = _object_get(disposition, "lever_resolution")
    if raw is None:
        return None
    try:
        return InterventionLeverRefusal.model_validate(
            raw.model_dump(mode="python") if hasattr(raw, "model_dump") else raw
        )
    except (AttributeError, TypeError, ValueError):
        return None


def _grounding_status_and_score(
    disposition: str,
    *,
    proxy_gap: bool,
) -> tuple[GroundingStatus, float]:
    if disposition == "shadow_bound":
        return "grounded_shadow", 0.2 if proxy_gap else 0.72
    if disposition == "novel_cg3":
        return "grounding_gap", 0.35
    if disposition == "non_binding_abstain":
        return "grounding_gap", 0.2
    if disposition in {"veto_false_analog", "unknown_blocked"}:
        return "grounding_failed", 0.0
    return "grounding_unavailable", 0.0


def _grounding_unavailable(
    candidate_id: str,
    *,
    issue_codes: Sequence[str],
    candidate_content_hash: str | None = None,
    design_problem_ref: str | None = None,
    authority_level: str | None = None,
) -> CandidateGroundingObservation:
    normalized_issues = tuple(str(item) for item in issue_codes if str(item))
    report_ref = gy_content_hash(
        {
            "candidate_id": candidate_id,
            "issue_codes": normalized_issues,
            "source": "grounding_unavailable",
        }
    )
    acquisition_requirement = None
    if (
        candidate_content_hash is not None
        and design_problem_ref is not None
        and authority_level is not None
    ):
        acquisition_requirement = grounding_coverage_requirement_gap(
            candidate_id=candidate_id,
            candidate_content_hash=candidate_content_hash,
            design_problem_ref=design_problem_ref,
            issue_codes=normalized_issues,
            evidence_refs=(),
            authority_level=authority_level,
            grounding_report_ref=report_ref,
        )
    return CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_unavailable",
        grounding_score=0.0,
        issue_codes=normalized_issues,
        evidence_refs=(),
        current_valid=False,
        report_ref=report_ref,
        grounding_source="grounding_unavailable",
        acquisition_requirement=acquisition_requirement,
    )


def _cg4_quarantine_refs(chain: object) -> tuple[object | None, object | None]:
    if chain is None:
        return None, None
    handoff = _object_get(chain, "quarantine_handoff") or _object_get(
        chain, "cg4_quarantine_handoff"
    )
    proxy_gap = _object_get(chain, "proxy_gap_risk") or _object_get(chain, "cg4_proxy_gap_risk")
    proxy_gap_ref = (
        _object_get(chain, "cg4_proxy_gap_risk_id")
        or _object_get(proxy_gap, "risk_id")
        or _object_get(proxy_gap, "proxy_gap_risk_id")
        or _object_get(handoff, "risk_id")
    )
    handoff_ref = (
        _object_get(handoff, "handoff_id")
        or _object_get(handoff, "record_id")
        or _object_get(chain, "cg4_quarantine_handoff_id")
        or _object_get(chain, "cg5_action_certificate_id")
        or _object_get(chain, "cg5_ticket_id")
    )
    action = _object_get(handoff, "action")
    if proxy_gap_ref and (handoff_ref or action == "adversarial_validate"):
        return proxy_gap_ref, handoff_ref or proxy_gap_ref
    return None, None


def _certificate_refs(chain: object) -> tuple[str, ...]:
    if chain is None:
        return ()
    refs: list[str] = []
    for field in (
        "cg1_certificate_id",
        "cg1_content_hash",
        "cg2_certificate_id",
        "cg2_content_hash",
        "cg3_certificate_id",
        "cg3_content_hash",
        "cg4_proxy_gap_risk_id",
        "cg4_proxy_gap_content_hash",
        "cg4_quarantine_handoff_id",
        "cg4_quarantine_handoff_hash",
        "cg5_action_certificate_id",
        "cg5_action_content_hash",
        "cg5_ticket_id",
        "cg5_ticket_hash",
    ):
        value = _object_get(chain, field)
        if value:
            refs.append(str(value))
    handoff = _object_get(chain, "quarantine_handoff") or _object_get(
        chain, "cg4_quarantine_handoff"
    )
    for field in ("handoff_id", "content_hash", "risk_id", "risk_content_hash"):
        value = _object_get(handoff, field)
        if value:
            refs.append(str(value))
    return tuple(_dedupe(refs))


def _grammar_fallback_result(
    problem: DesignProblem,
    *,
    cycle_index: int,
    reason: str,
) -> _GrammarFallbackResult:
    candidates: list[_GrammarFallbackCandidate] = []
    rankings: list[_GrammarFallbackRanking] = []
    grammar = tuple(
        str(item) for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
    )
    levers = tuple(problem.candidate_lever_space.candidate_levers)
    for index, lever in enumerate(levers):
        payload = {
            "cycle_index": cycle_index,
            "grammar": grammar,
            "lever": lever.model_dump(mode="json"),
            "reason": reason,
        }
        content_hash = gy_content_hash(payload)
        candidate_id = f"candidate_fallback_{content_hash.removeprefix('sha256:')[:16]}"
        target_slots = (str(lever.target_slot),) if lever.target_slot else ()
        atom = _GrammarFallbackAtom(
            intervention_id=str(lever.lever_id),
            content_hash=content_hash,
            target_world_slots=target_slots,
            world_model_record_ref=str(
                _runtime_hint_optional(problem, "world_model_record_ref")
                or "world_model_record_fallback_shadow"
            ),
        )
        candidates.append(
            _GrammarFallbackCandidate(
                candidate_id=candidate_id,
                atom=atom,
                diversity_key=(
                    str(lever.operator_kind),
                    str(lever.target_slot),
                    "grammar_fallback",
                    str(index),
                ),
            )
        )
        rankings.append(
            _GrammarFallbackRanking(
                candidate_id=candidate_id,
                score=max(0.1, 0.35 - (index * 0.05)),
                voi_estimate=max(0.1, 0.3 - (index * 0.05)),
            )
        )
    return _GrammarFallbackResult(
        status="generated" if candidates else "generation_unavailable",
        candidates=tuple(candidates),
        surrogate_rankings=tuple(rankings),
        fallback_reason=reason,
    )


def _ranking_by_candidate(result: object) -> dict[str, tuple[float, float]]:
    rankings: dict[str, tuple[float, float]] = {}
    for ranking in getattr(result, "surrogate_rankings", ()) or ():
        rankings[str(getattr(ranking, "candidate_id", ""))] = (
            float(getattr(ranking, "score", 0.0) or 0.0),
            float(getattr(ranking, "voi_estimate", 0.0) or 0.0),
        )
    return rankings


def _select_terminal_kind(
    *,
    grounding: CandidateGroundingObservation,
    proxy_score: float,
    value_port: ValuePortObservation,
) -> str:
    del proxy_score
    if grounding.acquisition_requirement is not None:
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    if any(str(code).startswith("acquire_data:") for code in grounding.issue_codes):
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    if grounding.status == "grounding_unavailable":
        return SearchTerminalKind.A_SPEC_GAP.value
    if grounding.quarantine_action == "adversarial_validate":
        return SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value
    if grounding.status in {"grounding_gap", "grounding_failed"}:
        return SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value
    if value_port.status == "value_pending_n8":
        return SearchTerminalKind.GROUNDED_ABSTENTION.value
    if value_port.acquisition_requirement is not None:
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    value_issue = _value_revision_issue(value_port)
    if value_issue and value_issue.startswith("acquire_data:"):
        return SearchTerminalKind.ACQUISITION_REQUIRED.value
    if value_issue:
        return SearchTerminalKind.SEARCH_CEILING_REPAIR_REQUIRED.value
    if grounding.current_valid:
        return SearchTerminalKind.GROUNDED_ADMISSIBLE.value
    inputs = SearchExitDecisionInputs(
        high_voi_untried=False,
        acquisition_required=False,
        frontier_stable=True,
        positive_terminal=SearchTerminalKind.GROUNDED_ABSTENTION,
    )
    return select_search_terminal(inputs).kind.value


def _counterexample_record(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    grounding: CandidateGroundingObservation,
    value_port: ValuePortObservation | None = None,
) -> CounterexampleRecord:
    value_issue = _value_revision_issue(value_port)
    issue = value_issue or (grounding.issue_codes[0] if grounding.issue_codes else grounding.status)
    counterexample_class = "value_gap" if value_issue else "real_design_blocker"
    slug = _slug(problem.design_problem_id)
    return CounterexampleRecord(
        counterexample_id=f"gy.n6.counterexample.{slug}.{cycle_index + 1:03d}",
        counterexample_ref=f"pdc://gy/n6/{slug}/counterexample/{cycle_index + 1:03d}",
        case_id=problem.design_problem_id,
        candidate_ref=candidate_id,
        counterexample_class=counterexample_class,
        diagnostic=TypedDiagnosticRecord(
            diagnostic_id=f"gy.n6.diagnostic.{slug}.{cycle_index + 1:03d}",
            code=(f"n6.value.{issue}" if value_issue else f"n6.{grounding.status}.{issue}"),
            severity="block",
            message=f"Candidate {candidate_id} requires revision for {issue}.",
            authority_purpose="shadow_search_refinement_only",
            owner="team-policyos-runtime",
            rule_version_ref=GENERATION_CYCLE_RULE_VERSION,
        ),
        evidence_refs=list(
            (value_port.value_ref,) if value_port is not None and value_port.value_ref else ()
        )
        or list(grounding.evidence_refs or ("grounding://missing",)),
        routed_to="refinement_policy",
    )


def _value_revision_issue(value_port: ValuePortObservation | None) -> str | None:
    if value_port is None:
        return None
    if value_port.status == "value_blocked":
        return (
            value_port.authority_blockers[0] if value_port.authority_blockers else "value_blocked"
        )
    if value_port.status == "value_ready" and value_port.decision_grade in {"blocked", "low"}:
        return f"value_{value_port.decision_grade}"
    return None


def _summary_with_value_observation(
    summary: CandidateSummary,
    *,
    value_port: ValuePortObservation,
    counterexample_ref: str,
) -> CandidateSummary:
    value_issue = _value_revision_issue(value_port)
    update: dict[str, Any] = {
        "value_status": value_port.status,
        "value_decision_grade": value_port.decision_grade,
        "value_ref": value_port.value_ref,
        "value_blockers": tuple(value_port.authority_blockers),
        "value_receipt": value_port.value_receipt,
    }
    if value_issue:
        update["counterexample_ref"] = counterexample_ref
        update["front"] = "research" if summary.front == "decision" else summary.front
        update["certified_by_n9"] = False
    return summary.model_copy(update=update)


def _summary_value_blocks_promotion(summary: CandidateSummary) -> bool:
    return summary.value_status == "value_blocked" or summary.value_decision_grade in {
        "blocked",
        "low",
    }


def _default_revision_request(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    terminal_kind: str,
    counterexample: CounterexampleRecord,
    grounding: CandidateGroundingObservation | None = None,
    value_port: ValuePortObservation | None = None,
) -> DesignRevisionRequest:
    previous_grammar = tuple(
        str(item) for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
    )
    diagnostic_code = str(counterexample.diagnostic.code).split(".")
    issue = diagnostic_code[-1] if diagnostic_code else counterexample.counterexample_class
    strategy = _revision_strategy_for_terminal_kind(terminal_kind)
    new_grammar_elements = _revision_grammar_elements(
        problem,
        strategy=strategy,
        issue=issue,
    )
    strategy_payload = _revision_strategy_payload(
        strategy=strategy,
        terminal_kind=terminal_kind,
        issue=issue,
        counterexample=counterexample,
        new_grammar_elements=new_grammar_elements,
        cycle_index=cycle_index,
        acquisition_requirement=(
            grounding.acquisition_requirement
            if grounding is not None and grounding.acquisition_requirement is not None
            else value_port.acquisition_requirement
            if value_port is not None
            else None
        ),
    )
    next_grammar = _dedupe((*previous_grammar, *new_grammar_elements))
    revised_problem = problem.model_copy(
        update={
            "runtime_hints": {
                **problem.runtime_hints,
                "generation_cycle_grammar": next_grammar,
                "generation_cycle_revision": {
                    "source_counterexample_ref": counterexample.counterexample_ref,
                    "previous_candidate_ref": candidate_id,
                    "revision_strategy": strategy,
                    "strategy_payload": strategy_payload,
                    "new_grammar_elements": new_grammar_elements,
                },
            }
        }
    )
    next_ref = (
        "candidate://pending/"
        + gy_content_hash(
            {
                "previous_candidate_ref": candidate_id,
                "counterexample_ref": counterexample.counterexample_ref,
                "revision_strategy": strategy,
                "new_grammar": new_grammar_elements,
            }
        ).removeprefix("sha256:")[:16]
    )
    return DesignRevisionRequest(
        revision_id=f"gy.n6.revision.{_slug(problem.design_problem_id)}.{cycle_index + 1:03d}",
        source_counterexample_ref=counterexample.counterexample_ref,
        source_terminal_kind=terminal_kind,
        previous_candidate_ref=candidate_id,
        next_candidate_ref=next_ref,
        previous_grammar_elements=previous_grammar,
        new_grammar_elements=new_grammar_elements,
        next_grammar_elements=next_grammar,
        revision_strategy=strategy,
        strategy_payload=strategy_payload,
        revised_problem=revised_problem,
    )


def _refinement_decision(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    counterexample: CounterexampleRecord,
    revision: DesignRevisionRequest,
    next_action: LoopVOIDecision,
) -> RefinementDecision:
    decision: Literal[
        "refine",
        "acquire",
        "reframe",
        "decompose",
        "human_decision",
        "abstain",
        "block_candidate",
    ]
    if next_action.next_action == "blocked":
        decision = "block_candidate"
    elif (
        next_action.next_action == "escalate"
        and next_action.terminal_kind == "acquisition_required"
    ):
        decision = "acquire"
    elif next_action.next_action == "escalate":
        decision = "human_decision"
    elif next_action.next_action == "stop":
        decision = "abstain"
    else:
        decision = "refine"
    slug = _slug(problem.design_problem_id)
    governance_ref = (
        f"governance://gy/n6/{slug}/terminal/{cycle_index + 1:03d}"
        if decision == "human_decision"
        else None
    )
    return RefinementDecision(
        decision_id=f"gy.n6.refinement.{slug}.{cycle_index + 1:03d}",
        decision_ref=f"pdc://gy/n6/{slug}/refinement/{cycle_index + 1:03d}",
        case_id=problem.design_problem_id,
        candidate_ref=candidate_id,
        consumed_counterexample_refs=[counterexample.counterexample_ref],
        decision=decision,
        next_candidate_ref=revision.next_candidate_ref if decision == "refine" else None,
        value_of_information=ValueOfInformationEstimate(
            estimate_id=f"gy_n6_voi_{cycle_index + 1:03d}",
            purpose="Schedule N6 shadow revision only; does not grant authority.",
            budget_dimensions=["compute", "acquisition", "human_attention"],
            used_by_sites=["runtime.quality.generation_cycle"],
            owner="team-policyos-runtime",
            rule_version_ref=GENERATION_CYCLE_RULE_VERSION,
        ),
        budget_refs=["budget://gy/n6/shadow-loop"],
        stakes_band="moderate",
        governance_decision_class_ref=governance_ref,
        governance_refs=[governance_ref] if governance_ref else [],
        reason=f"{next_action.reason}; terminal={next_action.terminal_kind}",
    )


def _search_iteration(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_id: str,
    counterexample: CounterexampleRecord,
    decision: RefinementDecision,
    next_action: LoopVOIDecision,
) -> SearchIteration:
    if decision.decision == "block_candidate" or next_action.next_action == "blocked":
        status = "blocked_no_retry"
    elif decision.decision == "human_decision":
        status = "governance_required"
    elif decision.decision == "acquire":
        status = "acquisition_required"
    elif decision.decision == "abstain":
        status = "abstained"
    else:
        status = "refined_shadow"
    return SearchIteration(
        iteration_id=f"gy.n6.iteration.{_slug(problem.design_problem_id)}.{cycle_index + 1:03d}",
        candidate_ref=candidate_id,
        counterexample_refs=[counterexample.counterexample_ref],
        refinement_decision_ref=decision.decision_ref,
        status=status,
    )


def _cycle_record(
    *,
    problem: DesignProblem,
    cycle_index: int,
    candidate_ids: tuple[str, ...],
    selected_candidate: object,
    grounding: CandidateGroundingObservation,
    simulation: SimulationPortObservation,
    value_port: ValuePortObservation,
    terminal_kind: str,
    counterexample: CounterexampleRecord,
    revision: DesignRevisionRequest,
    voi_decision: LoopVOIDecision,
) -> GenerationCycleRecord:
    decision = _refinement_decision(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=_candidate_id(selected_candidate),
        counterexample=counterexample,
        revision=revision,
        next_action=voi_decision,
    )
    iteration = _search_iteration(
        problem=problem,
        cycle_index=cycle_index,
        candidate_id=_candidate_id(selected_candidate),
        counterexample=counterexample,
        decision=decision,
        next_action=voi_decision,
    )
    return GenerationCycleRecord(
        cycle_index=cycle_index,
        design_problem_ref=_problem_ref(problem),
        grammar_elements=tuple(
            str(item) for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
        ),
        candidate_ids=candidate_ids,
        selected_candidate_ref=_candidate_id(selected_candidate),
        selected_candidate_content_hash=_candidate_content_hash(selected_candidate),
        grounding=grounding,
        simulation=simulation,
        value_port=value_port,
        terminal_kind=terminal_kind,
        counterexample=counterexample,
        refinement_decision=decision,
        search_iteration=iteration,
        voi_decision=voi_decision,
        revision_request=revision,
    )


def _blocked_cycle(cycle: GenerationCycleRecord, *, reason: str) -> GenerationCycleRecord:
    decision = cycle.refinement_decision.model_copy(
        update={
            "decision": "block_candidate",
            "next_candidate_ref": None,
            "reason": reason,
        }
    )
    iteration = cycle.search_iteration.model_copy(update={"status": "blocked_no_retry"})
    voi = cycle.voi_decision.model_copy(
        update={
            "next_action": "blocked",
            "reason": reason,
            "scheduler_action": (
                cycle.voi_decision.scheduler_action
                if cycle.voi_decision.scheduler_action != "pending"
                else "blocked"
            ),
        }
    )
    return cycle.model_copy(
        update={
            "refinement_decision": decision,
            "search_iteration": iteration,
            "voi_decision": voi,
        }
    )


def _cycle_with_acquisition_routing_report(
    cycle: GenerationCycleRecord,
    *,
    report: AcquisitionPlannerReport,
) -> GenerationCycleRecord:
    """Attach typed N7 routing evidence through full record validation."""

    values = {name: getattr(cycle, name) for name in GenerationCycleRecord.model_fields}
    values["acquisition_routing_report"] = report
    return GenerationCycleRecord.model_validate(values)


def _cycle_with_n7_route_failure(
    cycle: GenerationCycleRecord,
    *,
    reason: str,
) -> GenerationCycleRecord:
    """Retain an acquisition terminal while recording a failed canonical N7 route."""

    counterexample = cycle.counterexample.model_copy(
        update={
            "counterexample_class": "substrate_gap",
            "diagnostic": cycle.counterexample.diagnostic.model_copy(
                update={
                    "code": f"n6.acquisition.{reason}",
                    "message": (
                        "Acquisition remains required because the canonical "
                        f"N7 route refused the request: {reason}."
                    ),
                }
            ),
            "routed_to": "acquisition",
        }
    )
    return cycle.model_copy(
        update={
            "counterexample": counterexample,
            "acquisition_receipt": None,
            "acquisition_routing_report": None,
        }
    )


def _fake_cycle_reason(
    previous: GenerationCycleRecord,
    current: GenerationCycleRecord,
) -> str | None:
    if current.selected_candidate_content_hash == previous.selected_candidate_content_hash:
        return "fake_cycle_same_candidate_repeated"
    if current.driven_by_counterexample_ref != previous.counterexample.counterexample_ref:
        return "cycle_two_not_counterexample_driven"
    if not current.introduced_grammar_elements:
        return "no_retry_without_new_grammar"
    return None


def _derive_fronts(summaries: tuple[CandidateSummary, ...]) -> GenerationCycleFronts:
    by_front: dict[FrontKind, list[str]] = {
        "decision": [],
        "research": [],
        "quarantine": [],
        "portfolio": [],
    }
    for summary in summaries:
        by_front[summary.front].append(summary.candidate_id)
    return GenerationCycleFronts(
        decision=CandidateFront(
            front_kind="decision",
            candidate_ids=tuple(by_front["decision"]),
            reason="N9-certified current_valid candidates only; N6 does not promote.",
        ),
        research=CandidateFront(
            front_kind="research",
            candidate_ids=tuple(by_front["research"]),
            reason="Promising shadow candidates below decision authority.",
        ),
        quarantine=CandidateFront(
            front_kind="quarantine",
            candidate_ids=tuple(by_front["quarantine"]),
            reason="High-proxy or high-gap candidates require adversarial validation first.",
        ),
        portfolio=CandidateFront(
            front_kind="portfolio",
            candidate_ids=tuple(by_front["portfolio"]),
            reason="Portfolio synthesis is Phase-5 deferred.",
        ),
    )


def _apply_promotion_to_summaries(
    summaries: tuple[CandidateSummary, ...],
    promotion: PromotionPortObservation,
    *,
    problem: DesignProblem | None = None,
    open_world_resolver: OpenWorldRiskArtifactResolver | None = None,
) -> list[CandidateSummary]:
    certified = set(promotion.certified_candidate_ids)
    result: list[CandidateSummary] = []
    for summary in summaries:
        can_promote = (
            summary.candidate_id in certified
            and promotion.status == "certified_current_valid"
            and _promotion_receipt_allows_decision_front(
                promotion,
                summary,
                problem=problem,
                open_world_resolver=open_world_resolver,
            )
            and summary.current_valid
            and not _summary_value_blocks_promotion(summary)
            and (
                not summary.high_proxy
                or summary.adversarial_validation_status == "completed_shadow_only"
            )
        )
        if can_promote:
            result.append(
                summary.model_copy(
                    update={
                        "front": "decision",
                        "certified_by_n9": True,
                    }
                )
            )
        else:
            result.append(summary)
    return result


def _promotion_receipt_allows_decision_front(
    promotion: PromotionPortObservation,
    summary: CandidateSummary,
    *,
    problem: DesignProblem | None,
    open_world_resolver: OpenWorldRiskArtifactResolver | None = None,
) -> bool:
    from polisyos.runtime.quality.promotion_sequence import (
        promotion_receipt_allows_decision_front,
    )

    return promotion_receipt_allows_decision_front(
        promotion,
        summary,
        design_problem=problem,
        open_world_resolver=open_world_resolver,
    )


def _run_fixture_callers(repo_root: Path) -> tuple[str, ...]:
    src_root = repo_root / "src"
    if not src_root.is_dir():
        return ()
    callers: list[str] = []
    for path in src_root.rglob("*.py"):
        relative = path.relative_to(repo_root).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            callers.append(f"{relative}:syntax_error")
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if _call_name(node.func) != "run_fixture":
                continue
            callers.append(f"{relative}:{node.lineno}")
    return tuple(sorted(callers))


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_allowed_fixture_caller(caller: str) -> bool:
    return caller.startswith("src/polisyos/runtime/quality/workspace/loop.py:")


def _cycle_driver_ref(
    problem: DesignProblem,
    current_counterexample: CounterexampleRecord,
) -> str | None:
    revision = problem.runtime_hints.get("generation_cycle_revision")
    if isinstance(revision, Mapping):
        ref = revision.get("source_counterexample_ref")
        if ref:
            return str(ref)
    return current_counterexample.counterexample_ref


def _cycle_introduced_grammar(problem: DesignProblem) -> tuple[str, ...]:
    revision = problem.runtime_hints.get("generation_cycle_revision")
    if not isinstance(revision, Mapping):
        return ()
    raw = revision.get("new_grammar_elements")
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, Sequence):
        return tuple(str(item) for item in raw if str(item))
    return ()


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value.lower()).strip("_") or "case"


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return tuple(result)


def _json_ready(value: object) -> object:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return [_json_ready(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        return {
            str(field): _json_ready(getattr(value, str(field)))
            for field in getattr(value, "__dataclass_fields__", {})
        }
    return value


def _object_get(value: object, field: str, default: object | None = None) -> object | None:
    if isinstance(value, Mapping):
        return value.get(field, default)
    return getattr(value, field, default)


def _sequence(value: object | None) -> tuple[object, ...]:
    if value is None:
        return ()
    if isinstance(value, Sequence) and not isinstance(value, str | bytes | bytearray):
        return tuple(value)
    return (value,)


__all__ = [
    "GENERATION_CYCLE_CONTRACT_SCHEMA_VERSION",
    "GENERATION_CYCLE_CONTROLLER_REF",
    "GENERATION_CYCLE_SCHEMA_VERSION",
    "VALUE_DATA_SHAPE_RULE_VERSION",
    "CandidateFront",
    "CandidateGroundingObservation",
    "CandidateSummary",
    "CounterexampleDrivenRevisionPolicy",
    "DesignRevisionRequest",
    "FoundryValuePort",
    "GenerationCycleController",
    "GenerationCycleError",
    "GenerationCycleFronts",
    "GenerationCycleRecord",
    "GenerationCycleRun",
    "JointSimulationPort",
    "LoopVOIDecision",
    "N4GenerationPort",
    "PendingN8ValuePort",
    "PendingN9PromotionPort",
    "PolicyGroundingPort",
    "PreN9OpenWorldRiskGateObservation",
    "PromotionPortObservation",
    "RealValueOwnerGateway",
    "SimulationPortObservation",
    "StrangleReceipt",
    "ValueCalibrationReceipt",
    "ValueGateReceipt",
    "ValuePortObservation",
    "ValueTransportReceipt",
    "enforce_no_retry_without_new_grammar",
    "generation_cycle_terminal_state",
    "is_value_panel_shape",
    "simulation_evaluation_input_ref",
    "simulation_value_execution_context",
    "validate_generation_cycle_run",
]
