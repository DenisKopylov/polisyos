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
import time
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from polisyos.core.contracts.value_outer_set import (
    DataTrust,
    ValueOuterSet,
    ValueOuterSetIdentificationStatus,
)
from polisyos.data_requirement.compiler import DataRequirementCompiler
from polisyos.pdc import (
    CounterexampleRecord,
    RefinementDecision,
    SearchTerminalKind,
    TypedDiagnosticRecord,
    ValueOfInformationEstimate,
    gy_content_hash,
)
from polisyos.pdc._impl.layer2_design_search import SearchIteration
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionReceipt,
    AcquisitionWorldSnapshot,
    RealAcquisitionOwnerGateway,
    run_acquisition_closed_loop,
)
from polisyos.runtime.quality.design_problem import DesignProblem  # noqa: TC001
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
from polisyos.runtime.quality.joint_simulation_horizon import (
    JointSimulationHorizonController,
    JointSimulationRequest,
)
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateRegistryError,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
    build_substrate_registry_from_existing_catalogs,
)
from polisyos.runtime.quality.workspace.loop import (
    SearchExitDecisionInputs,
    select_search_terminal,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecord
from polisyos.scientist.methods.search.voi_scheduler import (
    ParetoSnapshot,
    SchedulingDecision,
    SimpleVOIScheduler,
)
from polisyos.scientist.orchestration.engine.budget import BudgetState  # noqa: TC001
from polisyos.scientist.orchestration.workflows.engine_simple import SimpleLoopEngine

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
ValueEvaluationMode = Literal[
    "simulate_only",
    "retrospective",
    "measurement_audit",
    "sandbox_pilot",
    "field_pilot",
    "deployment",
]
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
    grounding_source: Literal["cgf_firewall", "grounding_unavailable"] = (
        "grounding_unavailable"
    )
    grounding_disposition: str | None = None
    cgf_certificate_refs: tuple[str, ...] = ()
    quarantine_action: QuarantineAction = "none"
    adversarial_validation_ref: str | None = None

    @model_validator(mode="after")
    def _current_valid_requires_grounding(self) -> CandidateGroundingObservation:
        if self.current_valid and self.status != "current_valid":
            raise ValueError("current_valid_requires_current_valid_status")
        if self.status in {"current_valid", "grounded_shadow"} and (
            self.grounding_source != "cgf_firewall" or not self.grounding_disposition
        ):
            raise ValueError("grounded_status_requires_cgf_firewall_disposition")
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

    @model_validator(mode="after")
    def _simulate_only_does_not_shrink_k_world(self) -> ValueGateReceipt:
        if self.evaluation_mode == "simulate_only" and (
            self.k_world_ref_before != self.k_world_ref_after
        ):
            raise ValueError("simulate_only_shrank_k_world")
        if self.transport_receipt.world_model_record_content_hash != (
            self.world_model_record_content_hash
        ):
            raise ValueError("value_world_version_laundered")
        if self.value_outer_set.world_model_record_ref != self.world_model_record_content_hash:
            raise ValueError("value_world_version_laundered")
        return self


class ValuePortObservation(_StrictModel):
    """N8 value-port observation; pending is explicit and non-authoritative."""

    status: ValuePortStatus = "value_pending_n8"
    value_ref: str | None = None
    authority_blockers: tuple[str, ...] = ("value_gate_pending_n8",)
    reason: str = "N8 value gate is not present; N6 will not fabricate value."
    evaluation_mode: ValueEvaluationMode | None = None
    selected_method_fqn: str | None = None
    identification_status: ValueOuterSetIdentificationStatus | None = None
    decision_grade: Literal["blocked", "low", "medium", "high"] | None = None
    world_model_record_content_hash: str | None = None
    transport_receipt: ValueTransportReceipt | None = None
    calibration_receipt: ValueCalibrationReceipt | None = None
    value_receipt: ValueGateReceipt | None = None
    wall_time_ms: float | None = Field(default=None, ge=0.0)


class PromotionPortObservation(_StrictModel):
    """N9 promotion-port observation; N6 does not promote."""

    status: PromotionPortStatus = "promotion_pending_n9"
    certified_candidate_ids: tuple[str, ...] = ()
    reason: str = "N9 promotion gate is not present; N6 emits no certification."


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
    grounding_source: Literal["cgf_firewall", "grounding_unavailable"] = (
        "grounding_unavailable"
    )
    grounding_disposition: str | None = None
    grounding_score: float = Field(ge=0.0, le=1.0)
    current_valid: bool
    value_status: ValuePortStatus = "value_pending_n8"
    value_decision_grade: Literal["blocked", "low", "medium", "high"] | None = None
    value_ref: str | None = None
    value_blockers: tuple[str, ...] = ()
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
        summaries: Sequence[CandidateSummary],
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


class N4GenerationPort:
    """Default N4 port calling the real design generation owner."""

    def __init__(
        self,
        *,
        model_id: str,
        llm_client: object | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._model_id = model_id
        self._llm_client = llm_client
        self._repo_root = repo_root

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> object:
        """Call N4 generation for this cycle."""

        del cycle_index
        from polisyos.runtime.quality.design_generation import (
            generate_design_candidate_bundle_under_a,
        )

        organ_run = await generate_design_candidate_bundle_under_a(
            problem,
            model_id=self._model_id,
            llm_client=self._llm_client,
            repo_root=self._repo_root,
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

        del problem, cycle_index
        candidate_id = _candidate_id(candidate)
        disposition = _grounding_disposition_for_candidate(
            candidate,
            generation_result=generation_result,
        )
        if disposition is None:
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("cgf_disposition_missing",),
            )
        owner_issues = _candidate_owner_validation_issues(candidate, disposition)
        if owner_issues:
            return _grounding_unavailable(candidate_id, issue_codes=owner_issues)
        raw_disposition = str(_object_get(disposition, "disposition") or "")
        if raw_disposition not in _grounding_disposition_denominator():
            return _grounding_unavailable(
                candidate_id,
                issue_codes=("unknown_grounding_disposition", raw_disposition),
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
        )


class JointSimulationPort:
    """Default N5 port calling the joint simulation controller when request data exists."""

    def __init__(
        self,
        controller: JointSimulationHorizonController | None = None,
        *,
        repo_root: Path | None = None,
    ) -> None:
        self._controller = controller or JointSimulationHorizonController()
        self._repo_root = repo_root
        self._boundary_world_cache: dict[str, WorldModelRecord] = {}

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
                        "world_model_source": "real_substrate_registry_boundary",
                        "simulation_status": "pending_full_joint_request",
                    }
                )
            except Exception as exc:
                diagnostics.update(
                    {
                        "world_model_source": "unavailable",
                        "world_model_error": str(exc),
                    }
                )
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_pending_n5",
                authority_blockers=("joint_simulation_request_missing",),
                diagnostics=diagnostics,
                k_world_ref_before=(
                    world_record.content_hash
                    if world_record is not None
                    else _candidate_world_ref(candidate, problem)
                ),
                k_world_ref_after=(
                    world_record.content_hash
                    if world_record is not None
                    else _candidate_world_ref(candidate, problem)
                ),
                world_model_record=world_record,
            )
        request = (
            request
            if isinstance(request, JointSimulationRequest)
            else JointSimulationRequest.model_validate(request)
        )
        result = self._controller.run(request)
        k_world_ref = request.world_model_record.content_hash
        return SimulationPortObservation(
            candidate_id=candidate_id,
            status="joint_simulated",
            simulation_ref=result.receipt.payload_hash,
            uncertainty_kind=result.uncertainty_kind,
            authority_blockers=tuple(
                result.promotion_ready_value_packet.get("authority_blockers", ())
            ),
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

        repo_root = (self._repo_root or Path.cwd()).resolve()
        outcome = _value_outcome_variable(candidate, problem) or "value_outcome"
        slots = tuple(_candidate_target_world_slots(candidate)) or (outcome,)
        cache_key = gy_content_hash(
            {
                "repo_root": repo_root.as_posix(),
                "problem_id": problem.design_problem_id,
                "domain": problem.domain,
                "outcome": outcome,
                "slots": slots,
            }
        )
        if cache_key in self._boundary_world_cache:
            return self._boundary_world_cache[cache_key]
        record = _build_boundary_world_model_record(
            repo_root=repo_root,
            problem=problem,
            outcome=outcome,
            policy_slot_ids=slots,
        )
        self._boundary_world_cache[cache_key] = record
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
    ) -> None:
        self.code = code
        self.owner_access_ref = owner_access_ref
        detail = message or code
        if owner_access_ref:
            detail = f"{detail} owner_access_ref={owner_access_ref}"
        super().__init__(detail)


class ValueOwnerGateway(Protocol):
    """Owner access surface for N8 input materialization."""

    def load_panel_observational_data(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> object:
        """Load owner-bound panel data for the candidate outcome and world slot."""

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

    def load_panel_observational_data(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> object:
        """Load panel data through the real substrate owner or return a real gap."""

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

            availability = l1_dcat_variable_availability(repo_root, outcome)
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
            )
        panel = _load_panel_from_l1_dcat(
            repo_root=repo_root,
            outcome=outcome,
            candidate=candidate,
        )
        if panel is None:
            raise ValueOwnerAccessError(
                "acquire_data:value_panel_data_missing",
                f"substrate owner found {outcome} but no usable panel matrix",
                owner_access_ref=owner_access_ref,
            )
        return panel

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

        del candidate, problem, world_record, method_result, selected_method_fqn
        raise ValueOwnerAccessError(
            "s10_outcome_prediction_owner_unavailable",
            (
                "S10 outcome_prediction execution owner is not locally callable; "
                "N8 refuses to mint value from a builder-shaped forecast."
            ),
            owner_access_ref="s10_owner://outcome_prediction_unavailable",
        )

    def build_transport_inputs(
        self,
        *,
        candidate: object,
        problem: DesignProblem,
        world_record: WorldModelRecord,
    ) -> Mapping[str, Any]:
        """Derive transport inputs through the selection-diagram owner."""

        return {
            "selection_diagram": _build_default_selection_diagram(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
            ),
            "query_treatment": "X",
            "query_outcome": "Y",
        }


class FoundryValuePort:
    """Default N8 port delegating value authority to Foundry and S10 owners."""

    def __init__(
        self,
        *,
        owner_gateway: ValueOwnerGateway | None = None,
        evaluation_mode: ValueEvaluationMode = "simulate_only",
        data_trust: DataTrust | None = None,
        requested_method_fqn: str | None = None,
        method_params: Mapping[str, Any] | None = None,
        observation_to_contract_manifest: object | None = None,
        runtime_budget_ms: float | None = None,
        seed: int = 42,
        repo_root: Path | None = None,
    ) -> None:
        self._owner_gateway = owner_gateway or RealValueOwnerGateway(repo_root=repo_root)
        self._evaluation_mode = evaluation_mode
        self._data_trust = data_trust
        self._requested_method_fqn = requested_method_fqn
        self._method_params = dict(method_params or {})
        self._observation_to_contract_manifest = observation_to_contract_manifest
        self._runtime_budget_ms = runtime_budget_ms
        self._seed = seed
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
        inputs = self._selection_inputs()
        mode = self._evaluation_mode
        if mode in {"sandbox_pilot", "field_pilot", "deployment"}:
            return _blocked_value_observation(
                code="eval_safety_gate_unavailable",
                reason="EvalSafety is not wired yet; pilot/deployment value execution is blocked.",
                mode=mode,
                started=started,
            )
        data_trust = self._data_trust
        if mode in {"retrospective", "measurement_audit"} and data_trust is None:
            return _blocked_value_observation(
                code="data_trust_gate_missing",
                reason="Retrospective and measurement-audit value modes require DataTrust.",
                mode=mode,
                started=started,
            )
        data_trust = data_trust or _simulate_only_data_trust()
        world_record, cache_status, world_error = self._world_record_from_simulation(simulation)
        if world_error is not None or world_record is None:
            return _blocked_value_observation(
                code=world_error or "value_world_model_record_unwired",
                reason=(
                    "N8 production value requires the cycle's typed WorldModelRecord; "
                    "missing WMR is controller wiring, not an acquisition gap."
                ),
                mode=mode,
                started=started,
            )
        try:
            method_state = self._owner_gateway.load_panel_observational_data(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
            )
        except ValueOwnerAccessError as exc:
            return _blocked_value_observation(
                code=exc.code,
                reason=str(exc),
                mode=mode,
                started=started,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        selection = _select_value_method(
            candidate=candidate,
            problem=problem,
            inputs=inputs,
            method_state=method_state,
        )
        if selection.get("status") != "selected" or not selection.get("selected_method_fqn"):
            return _blocked_value_observation(
                code=_first_text(selection.get("blockers")) or "value_method_selection_blocked",
                reason=str(selection.get("reason") or "Foundry selector refused value method."),
                mode=mode,
                started=started,
                selected_method_fqn=_optional_text(selection.get("selected_method_fqn")),
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        method_result = None
        method_error = None
        selected_method_fqn = str(selection["selected_method_fqn"])
        attempted_methods: list[str] = []
        for method_fqn in _candidate_value_method_trace(
            selection=selection,
            requested_method_fqn=self._requested_method_fqn,
        ):
            attempted_methods.append(method_fqn)
            method_result, method_error = _run_value_method(
                method_fqn=method_fqn,
                method_state=method_state,
                method_params=self._method_params,
                seed=self._seed,
            )
            if method_error is None and method_result is not None:
                selected_method_fqn = method_fqn
                break
        if method_error is not None or method_result is None:
            return _blocked_value_observation(
                code=method_error or "foundry_method_refused_value",
                reason=(
                    "Foundry method did not produce a usable causal value estimate "
                    f"(attempted_methods={attempted_methods})."
                ),
                mode=mode,
                started=started,
                selected_method_fqn=selected_method_fqn,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            forecast_inputs = self._owner_gateway.produce_forecast_inputs(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
                method_result=method_result,
                selected_method_fqn=selected_method_fqn,
            )
        except ValueOwnerAccessError as exc:
            return _blocked_value_observation(
                code=exc.code,
                reason=str(exc),
                mode=mode,
                started=started,
                selected_method_fqn=selected_method_fqn,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        calibration_receipt = _value_calibration_receipt(
            inputs=forecast_inputs,
            world_record=world_record,
        )
        if calibration_receipt.status == "blocked":
            return _blocked_value_observation(
                code=(
                    calibration_receipt.issue_codes[0]
                    if calibration_receipt.issue_codes
                    else "forecast_calibration_blocked"
                ),
                reason="S10 outcome-prediction calibration refused value authority.",
                mode=mode,
                started=started,
                calibration_receipt=calibration_receipt,
                selected_method_fqn=selected_method_fqn,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            transport_inputs = self._owner_gateway.build_transport_inputs(
                candidate=candidate,
                problem=problem,
                world_record=world_record,
            )
        except ValueOwnerAccessError as exc:
            return _blocked_value_observation(
                code=exc.code,
                reason=str(exc),
                mode=mode,
                started=started,
                calibration_receipt=calibration_receipt,
                selected_method_fqn=selected_method_fqn,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        transport_receipt, transport_error = _run_value_transport(
            inputs=transport_inputs,
            world_record=world_record,
        )
        if transport_error is not None or transport_receipt is None:
            return _blocked_value_observation(
                code=transport_error or "untransportable_forecast_minted_value",
                reason="Transport owner refused to produce a transport receipt.",
                mode=mode,
                started=started,
                calibration_receipt=calibration_receipt,
                selected_method_fqn=selected_method_fqn,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
            )
        try:
            value_set = _value_outer_set_from_foundry_result(
                method_result=method_result,
                transport_receipt=transport_receipt,
                calibration_receipt=calibration_receipt,
                world_record=world_record,
                data_trust=data_trust,
            )
        except ValueError as exc:
            return _blocked_value_observation(
                code=str(exc).split(":", 1)[0],
                reason=str(exc),
                mode=mode,
                started=started,
                calibration_receipt=calibration_receipt,
                selected_method_fqn=selected_method_fqn,
                world_model_record_content_hash=str(_object_get(world_record, "content_hash")),
                transport_receipt=transport_receipt,
            )
        decision = value_set.promotion_decision()
        world_hash = str(_object_get(world_record, "content_hash"))
        value_ref = gy_content_hash(
            {
                "candidate_id": _candidate_id(candidate),
                "world_model_record_content_hash": world_hash,
                "method_fqn": selected_method_fqn,
                "value_outer_set": value_set.canonical_payload(),
                "transport_receipt": transport_receipt.model_dump(mode="json"),
                "calibration_receipt": calibration_receipt.model_dump(mode="json"),
            }
        )
        receipt = ValueGateReceipt(
            candidate_id=_candidate_id(candidate),
            evaluation_mode=mode,
            selected_method_fqn=selected_method_fqn,
            method_selection_trace=tuple(str(item) for item in selection.get("score_trace", ())),
            identification_status=value_set.identification_status,
            value_outer_set=value_set,
            transport_receipt=transport_receipt,
            calibration_receipt=calibration_receipt,
            world_model_record_id=str(_object_get(world_record, "world_model_record_id")),
            world_model_record_content_hash=world_hash,
            value_ref=value_ref,
            wall_time_ms=(time.monotonic() - started) * 1000.0,
            wmr_cache_status=cache_status,
            k_world_ref_before=world_hash,
            k_world_ref_after=world_hash,
        )
        blockers = tuple(reason for reason in decision.reasons if reason != "eligible")
        return ValuePortObservation(
            status="value_ready",
            value_ref=value_ref,
            authority_blockers=blockers,
            reason=(
                "N8 value computed by Foundry method execution plus "
                "transport/calibration gates."
            ),
            evaluation_mode=mode,
            selected_method_fqn=selected_method_fqn,
            identification_status=value_set.identification_status,
            decision_grade=decision.capped_decision_grade,
            world_model_record_content_hash=world_hash,
            transport_receipt=transport_receipt,
            calibration_receipt=calibration_receipt,
            value_receipt=receipt,
            wall_time_ms=receipt.wall_time_ms,
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
                raw
                if isinstance(raw, WorldModelRecord)
                else WorldModelRecord.model_validate(raw)
            )
        except Exception as exc:
            return None, "built", f"world_model_record_invalid:{exc}"
        content_hash = str(record.content_hash)
        if content_hash in self._world_cache:
            return self._world_cache[content_hash], "reused", None
        self._world_cache[content_hash] = record
        return record, "built", None


class PendingN9PromotionPort:
    """Honest N9-pending promotion port."""

    def __call__(
        self,
        *,
        summaries: Sequence[CandidateSummary],
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        """Return no certifications because N6 does not promote."""

        del summaries, problem
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
        revision_policy: RevisionPolicy | None = None,
        voi_scheduler: SimpleVOIScheduler | None = None,
        acquisition_owner_gateway: object | None = None,
        repo_root: Path | None = None,
        model_id: str | None = None,
        high_proxy_threshold: float = 0.8,
        low_grounding_threshold: float = 0.5,
    ) -> None:
        if generation_port is None and model_id is None:
            generation_port = _UnavailableGenerationPort()
        self._generation_port = generation_port or N4GenerationPort(
            model_id=str(model_id),
            repo_root=repo_root,
        )
        self._grounding_port = grounding_port or PolicyGroundingPort()
        self._simulation_port = simulation_port or JointSimulationPort()
        self._value_port = value_port or FoundryValuePort()
        self._promotion_port = promotion_port or PendingN9PromotionPort()
        self._revision_policy = revision_policy or CounterexampleDrivenRevisionPolicy()
        self._acquisition_owner_gateway = acquisition_owner_gateway
        self._voi_scheduler = voi_scheduler or SimpleVOIScheduler(
            stage_costs={3: Decimal("0.5"), 4: Decimal("1.0")},
            min_roi_threshold=1.0,
        )
        self._repo_root = repo_root
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
            acquisition_receipt = self._run_n7_acquisition_if_requested(
                current_problem,
                cycle=cycle,
            )
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
                    introduced_grammar_elements=(
                        cycle.revision_request.new_grammar_elements
                    ),
                    design_problem=current_problem,
                )
            except GenerationCycleError as exc:
                terminal_status = "blocked"
                blocked_reason = exc.code
                cycles[-1] = _blocked_cycle(cycle, reason=exc.code)
                break
            current_problem = cycle.revision_request.revised_problem
            cycle_index += 1

        promotion = self._promotion_port(summaries=tuple(summaries), problem=problem)
        summaries = _apply_promotion_to_summaries(tuple(summaries), promotion)
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
            owner_gateway=owner_gateway,
            useful_design_rate_before=float(
                problem.runtime_hints.get("n7_useful_design_rate_before") or 0.0
            ),
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
        )
        world_ref_hint = _runtime_hint_optional(problem, "world_model_record_ref")
        world_ref = str(world_ref_hint or f"s0://substrate-registry/{registry.substrate_version_id}")
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
            world_model_record_ref=_runtime_hint_optional(problem, "world_model_record_ref"),
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
        candidates = tuple(getattr(result, "candidates", ()) or ())
        generation_channel: GenerationChannel = "n4_owner"
        if getattr(result, "status", None) != "generated" or not candidates:
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
    if run.terminal_status == "completed" and len(run.cycles) < 2:
        issues.append({"code": "positive_cycle_denominator_missing"})
    for index, cycle in enumerate(run.cycles):
        if cycle.terminal_kind not in expected_denominator:
            issues.append(
                {
                    "code": "unsupported_terminal_not_honest",
                    "cycle_index": index,
                    "terminal_kind": cycle.terminal_kind,
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
        if (
            summary.grounding_status in {"current_valid", "grounded_shadow"}
            and (
                summary.grounding_source != "cgf_firewall"
                or not summary.grounding_disposition
            )
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
    return tuple(issues)


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
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "strategy": strategy,
        "terminal_kind": terminal_kind,
        "issue": issue,
        "source_counterexample_ref": counterexample.counterexample_ref,
    }
    if strategy == "acquire_or_elicit":
        payload["acquisition_request"] = {
            "request_kind": "owner_grounding_evidence",
            "driver": issue,
            "counterexample_ref": counterexample.counterexample_ref,
            "cycle_index": cycle_index,
            "consumer_owner": "polisyos.runtime.quality.acquisition_planner",
            "reentry": "same_generation_cycle_index",
            "network_policy": "record_replay_required_for_routine_check",
        }
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
) -> SubstrateRegistry:
    for key in ("substrate_registry", "s0_substrate_registry"):
        raw = problem.runtime_hints.get(key)
        if raw is not None:
            return (
                raw
                if isinstance(raw, SubstrateRegistry)
                else SubstrateRegistry.model_validate(raw)
            )
    try:
        return build_substrate_registry_from_existing_catalogs(repo_root)
    except (SubstrateRegistryError, FileNotFoundError, ValueError):
        pass
    entries = [
        build_substrate_registry_entry(
            SubstrateRegistration(
                source_id=f"n6.bootstrap.{family}",
                family_id=family,
                layer=SubstrateLayer.L1,
                coverage=SubstrateCoverage(
                    coverage_score=0.01,
                    coverage_kind="n6_bootstrap_world_slot",
                    coverage_rule_ref=f"n6://coverage/{family}",
                    dataset_count=1,
                    metric_binding_count=1,
                    observation_count=1,
                ),
                trust_tier=SubstrateTrustTier(
                    tier="bootstrap",
                    trust_cap=0.01,
                    trust_multiplier=0.01,
                    authority_ref=f"n6://trust/{family}",
                ),
                identification_mode="bootstrap_slot",
                schema_regime=SubstrateSchemaRegime(
                    schema_regime_id=f"manifest:{family}",
                    authority_ref=f"n6://schema/{family}",
                ),
                data_version="n6-bootstrap",
                snapshot_id=f"n6-bootstrap:{family}",
                source_snapshot_id=f"n6-bootstrap:{family}",
                provenance_refs=(f"n6://provenance/{family}",),
                authority_refs=(f"n6://authority/{family}",),
            )
        )
        for family in families
    ]
    return build_substrate_registry(
        entries,
        producer_ref="polisyos.runtime.quality.generation_cycle.N6",
        source_catalog_refs=(f"n6://{problem.design_problem_id}/bootstrap-substrate-registry",),
    )


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


def _load_panel_from_l1_dcat(
    *,
    repo_root: Path,
    outcome: str,
    candidate: object,
) -> object | None:
    try:
        import duckdb
        import numpy as np

        from polisyos.foundry.methods.catalog.causal.protocols import PanelObservationalData
        from polisyos.runtime.quality.substrate_registry import default_substrate_catalog_paths
    except Exception as exc:  # pragma: no cover - local dependency surface.
        raise ValueOwnerAccessError(
            "acquire_data:value_panel_data_missing",
            f"substrate panel loader dependencies unavailable: {exc}",
            owner_access_ref="substrate_owner://panel_loader_dependency_missing",
        ) from exc

    dcat_path = default_substrate_catalog_paths(repo_root).l1_dcat_path
    if not dcat_path.exists():
        raise ValueOwnerAccessError(
            "acquire_data:value_panel_data_missing",
            f"L1 DCAT catalog missing at {dcat_path}",
            owner_access_ref="substrate_owner://l1_dcat_missing",
        )
    con = duckdb.connect(str(dcat_path), read_only=True)
    try:
        rows = con.execute(
            """
            SELECT
              COALESCE(NULLIF(country_code, ''), 'unknown') AS unit_id,
              COALESCE(year, survey_year, wave) AS period_id,
              avg(value) AS value
            FROM ds_observations
            WHERE canonical_var = ?
              AND value IS NOT NULL
              AND COALESCE(year, survey_year, wave) IS NOT NULL
            GROUP BY unit_id, period_id
            ORDER BY unit_id, period_id
            LIMIT 5000
            """,
            [outcome],
        ).fetchall()
    finally:
        con.close()
    if not rows:
        return None
    periods = sorted({int(period) for _, period, _ in rows})
    units = sorted({str(unit) for unit, _, _ in rows})
    if len(periods) < 4 or len(units) < 3:
        return None
    period_index = {period: index for index, period in enumerate(periods)}
    unit_index = {unit: index for index, unit in enumerate(units)}
    matrix = np.full((len(units), len(periods)), np.nan, dtype=float)
    for unit, period, value in rows:
        matrix[unit_index[str(unit)], period_index[int(period)]] = float(value)
    usable_units = np.where(np.sum(~np.isnan(matrix), axis=1) >= 4)[0]
    if len(usable_units) < 3:
        return None
    matrix = matrix[usable_units, :]
    usable_periods = np.where(np.sum(~np.isnan(matrix), axis=0) >= 2)[0]
    if len(usable_periods) < 4:
        return None
    matrix = matrix[:, usable_periods]
    global_mean = float(np.nanmean(matrix))
    col_means = np.nanmean(matrix, axis=0)
    col_means = np.where(np.isnan(col_means), global_mean, col_means)
    missing_rows, missing_cols = np.where(np.isnan(matrix))
    matrix[missing_rows, missing_cols] = col_means[missing_cols]
    units = [units[int(index)] for index in usable_units]
    periods = [periods[int(index)] for index in usable_periods]
    treatment, time_treatment = _candidate_treatment_assignment(
        candidate=candidate,
        units=units,
        periods=periods,
    )
    return PanelObservationalData(
        outcome=matrix,
        treatment=treatment,
        time_treatment=time_treatment,
    )


def _candidate_treatment_assignment(
    *,
    candidate: object,
    units: Sequence[str],
    periods: Sequence[int],
) -> tuple[Any, int]:
    import numpy as np

    atom = _object_get(candidate, "atom")
    treated_units_raw = (
        _object_get(candidate, "treated_unit_ids")
        or _object_get(candidate, "treated_units")
        or _object_get(atom, "treated_unit_ids")
        or _object_get(atom, "treated_units")
        or _object_get(atom, "treatment_unit_ids")
    )
    treated_units = tuple(
        str(unit)
        for unit in _sequence(treated_units_raw)
        if _optional_text(unit) is not None
    )
    if not treated_units:
        raise ValueOwnerAccessError(
            "acquire_data:value_treatment_assignment_missing",
            "candidate intervention does not identify treated substrate units",
            owner_access_ref="candidate_owner://treated_units_missing",
        )
    unit_index = {str(unit): index for index, unit in enumerate(units)}
    treated_indices = tuple(unit_index[unit] for unit in treated_units if unit in unit_index)
    if not treated_indices:
        raise ValueOwnerAccessError(
            "acquire_data:value_treatment_assignment_missing",
            (
                "candidate treated units are absent from the substrate panel "
                f"(treated_units={treated_units})"
            ),
            owner_access_ref="substrate_owner://treated_units_not_in_panel",
        )
    period_raw = (
        _object_get(candidate, "treatment_period")
        or _object_get(candidate, "time_treatment")
        or _object_get(atom, "treatment_period")
        or _object_get(atom, "time_treatment")
        or _object_get(atom, "treatment_start_period")
    )
    if period_raw is None:
        raise ValueOwnerAccessError(
            "acquire_data:value_treatment_assignment_missing",
            "candidate intervention does not identify a treatment start period",
            owner_access_ref="candidate_owner://treatment_period_missing",
        )
    period_index = _resolve_treatment_period_index(period_raw, periods)
    if period_index <= 0 or period_index >= len(periods) - 1:
        raise ValueOwnerAccessError(
            "acquire_data:value_treatment_assignment_missing",
            (
                "candidate treatment period must leave pre/post periods in the "
                f"substrate panel (period={period_raw})"
            ),
            owner_access_ref="candidate_owner://treatment_period_out_of_panel_range",
        )
    treatment = np.asarray([0 for _ in units], dtype=int)
    for index in treated_indices:
        treatment[int(index)] = 1
    if int(np.sum(treatment)) <= 0:
        raise ValueOwnerAccessError(
            "acquire_data:value_treatment_assignment_missing",
            "candidate-derived treatment vector is empty",
            owner_access_ref="candidate_owner://treatment_vector_empty",
        )
    return treatment, period_index


def _resolve_treatment_period_index(period_raw: object, periods: Sequence[int]) -> int:
    if isinstance(period_raw, int):
        if period_raw in periods:
            return list(periods).index(period_raw)
        if 0 <= period_raw < len(periods):
            return period_raw
    text = str(period_raw).strip()
    if text:
        for index, period in enumerate(periods):
            if text == str(period):
                return index
    raise ValueOwnerAccessError(
        "acquire_data:value_treatment_assignment_missing",
        f"candidate treatment period {period_raw!r} is absent from the substrate panel",
        owner_access_ref="substrate_owner://treatment_period_not_in_panel",
    )


def _build_boundary_world_model_record(
    *,
    repo_root: Path,
    problem: DesignProblem,
    outcome: str,
    policy_slot_ids: Sequence[str],
) -> WorldModelRecord:
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

    registry = build_substrate_registry_from_existing_catalogs(repo_root)
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
        for entry in sorted(
            registry.entries,
            key=lambda item: (item.layer.value, item.source_id, item.family_id),
        )
    )
    registry_ref = SubstrateRegistryRef(
        substrate_version_id=registry.substrate_version_id,
        content_hash=registry.content_hash,
        registry_artifact_ref=(
            "repo://production_data/canonical/local_data_20260501"
            "#substrate_registry_from_existing_catalogs"
        ),
        resolved_entries=resolved_entries,
    )
    slots = tuple(dict.fromkeys(str(slot) for slot in policy_slot_ids if str(slot).strip()))
    slot_map = tuple(
        PolicySlotBinding(
            slot_id=slot,
            state_path=f"substrate.l1.{slot}",
            entity_scope="country",
            temporal_granularity="year",
        )
        for slot in (slots or (outcome,))
    )
    scope_hash = gy_content_hash(
        {
            "problem_id": problem.design_problem_id,
            "domain": problem.domain,
            "outcome": outcome,
            "registry": registry.content_hash,
            "slots": [binding.model_dump(mode="json") for binding in slot_map],
        }
    )
    fields: dict[str, Any] = {
        "schema_version": "policyos.runtime.world_model_record.v1",
        "authority_status": "limited",
        "producer_ref": (
            "polisyos.runtime.quality.generation_cycle."
            "_build_boundary_world_model_record"
        ),
        "region_or_jurisdiction": "UA",
        "population_scope": "real_l1_dcat_country_panel",
        "policy_domain": problem.domain or "runtime_quality",
        "valid_time_scope": "2018/2023",
        "tx_time_scope": "2026-07-06T00:00:00+00:00",
        "resolution": "country_year",
        "branch_mode": BranchMode.OBSERVED,
        "fabric_world_ref": FabricWorldRef(
            snapshot_root=str(repo_root / "production_data"),
            snapshot_id=registry.substrate_version_id,
            branch="observed",
            as_of_valid_time="2026-07-06T00:00:00+00:00",
            as_of_tx_time="2026-07-06T00:00:00+00:00",
            world_query_policy="real_substrate_registry_boundary",
            provenance_manifest_ref="repo://production_data/manifest.json",
            content_query_digest=registry.content_hash,
            content_query_row_count=len(registry.entries),
        ),
        "data_forge_binding_ref": DataForgeBindingRef(
            snapshot_id=registry.substrate_version_id,
            release_id="production_data_20260327",
            role="domain",
            read_api_identity="l1_dcat.duckdb",
            snapshot_ref=(
                "repo://production_data/datasets_full_phase3full_20260327_183054/"
                "dataset_catalog.duckdb"
            ),
            merkle_root=f"registry:{registry.substrate_version_id}",
            data_hash=registry.content_hash,
            provenance_manifest_ref="repo://production_data/manifest.json",
        ),
        "simulation_model_ref": SimulationModelRef(
            model_spec_ref=gy_content_hash({"boundary": "model_spec", "scope": scope_hash}),
            model_spec_hash=gy_content_hash({"boundary": "model_hash", "scope": scope_hash}),
            model_id="model_real_l1_dcat_boundary",
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
            skg_snapshot_ref=(
                "repo://production_data/policyos_academic_runtime_slim_20260411T112032Z/"
                "academic/graph/scholar_knowledge.duckdb"
            ),
            skg_version_id="production_data_20260411_boundary",
            source_data_snapshot_id=registry.substrate_version_id,
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
) -> object:
    del candidate, problem
    from polisyos.ir.analytics.causal_graph import CausalEdge, CausalGraphModel, GraphType
    from polisyos.ir.analytics.context import ContextProfile
    from polisyos.ir.analytics.transportability import build_selection_diagram

    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    context_id = f"world:{world_record.world_model_record_id}"
    region = str(world_record.region_or_jurisdiction or "")
    context = ContextProfile(
        context_id=context_id,
        context_label=region,
        countries=[region.split("-", 1)[0]] if region else [],
        time_period=str(world_record.valid_time_scope),
    )
    return build_selection_diagram(context, context, graph)


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
) -> Mapping[str, Any]:
    from datetime import UTC, datetime

    from polisyos.runtime.quality.design_axes.outcome_prediction import (
        build_forecast_calibration_record,
        build_forecast_support,
    )

    now = datetime(2026, 6, 2, tzinfo=UTC)
    outcome = _value_outcome_variable(candidate, problem) or "value_outcome"
    report = _method_report(method_result)
    report_ref = gy_content_hash(
        {
            "method_fqn": selected_method_fqn,
            "point_estimate": str(_object_get(report, "point_estimate")),
            "confidence_interval": str(_object_get(report, "confidence_interval")),
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
            counterfactual_credibility="credible",
            prediction_time=now,
            observation_time=now,
            policy_effective_time=now,
            data_valid_time=now,
            calibration_window_start=now,
            calibration_window_end=now,
            metric_name="observable_subset_calibration",
            denominator=4,
            numerator=4 if calibration_status == "pass" else 0,
            pass_rate=1.0 if calibration_status == "pass" else 0.0,
            calibration_threshold_ref="repo://architecture/policy_design_case/layer2_floor_governance.toml#s10",
            floor_passed=calibration_status == "pass",
            calibration_status=calibration_status,
            interval_coverage_metric=1.0 if calibration_status == "pass" else 0.0,
            calibration_error_metric=0.0 if calibration_status == "pass" else 1.0,
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
        forecast_authority_disposition_reason="S10 owner forecast over Foundry method output",
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


def _value_evaluation_mode(inputs: Mapping[str, Any]) -> ValueEvaluationMode:
    raw = str(inputs.get("evaluation_mode") or "simulate_only")
    allowed = set(get_args(ValueEvaluationMode))
    return raw if raw in allowed else "simulate_only"  # type: ignore[return-value]


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
    calibration_receipt: ValueCalibrationReceipt | None = None,
    selected_method_fqn: str | None = None,
    world_model_record_content_hash: str | None = None,
    transport_receipt: ValueTransportReceipt | None = None,
) -> ValuePortObservation:
    return ValuePortObservation(
        status="value_blocked",
        value_ref=None,
        authority_blockers=(code,),
        reason=reason,
        evaluation_mode=mode,
        selected_method_fqn=selected_method_fqn,
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
    problem: DesignProblem,
    inputs: Mapping[str, Any],
    method_state: object | None = None,
) -> dict[str, Any]:
    try:
        from polisyos.foundry.methods.selection import select_value_method_for_problem
    except ImportError as exc:
        return {
            "status": "blocked",
            "blockers": ("value_method_selector_unavailable",),
            "reason": str(exc),
        }
    selector_problem: object = problem
    if _is_panel_observational_data(method_state) and inputs.get("method_fqn") is None:
        selector_problem = _selector_problem_with_owner_context(
            problem,
            {
                "value_method_hint": "panel",
                "value_required_data_modalities": ("panel",),
            },
        )
    return select_value_method_for_problem(
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


def _is_panel_observational_data(value: object | None) -> bool:
    return (
        value is not None
        and hasattr(value, "outcome")
        and hasattr(value, "treatment")
        and hasattr(value, "time_treatment")
    )


def _selector_problem_with_owner_context(
    problem: DesignProblem,
    context: Mapping[str, object],
) -> Mapping[str, object]:
    outcome = _object_get(problem, "outcome_of_interest")
    if hasattr(outcome, "model_dump"):
        outcome_payload = outcome.model_dump(mode="json")
    elif isinstance(outcome, Mapping):
        outcome_payload = dict(outcome)
    else:
        outcome_payload = {}
    return {
        "design_problem_id": str(_object_get(problem, "design_problem_id") or ""),
        "problem_statement": str(_object_get(problem, "problem_statement") or ""),
        "domain": str(_object_get(problem, "domain") or ""),
        "outcome_of_interest": outcome_payload,
        "runtime_hints": dict(context),
    }


def _run_value_method(
    *,
    method_fqn: str,
    method_state: object,
    method_params: Mapping[str, Any],
    seed: int,
) -> tuple[object | None, str | None]:
    try:
        from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
        from polisyos.foundry.methods.selection.registry import get_registry
        from polisyos.ir.analytics.causal import EstimationStatus

        registry = get_registry()
        method_cls = registry.get(method_fqn)
        result = MethodDispatcher.get_instance().dispatch(
            method_class=method_cls,
            signature=method_cls.signature,
            state=method_state,
            params=method_params,
            seed=seed,
        )
        report = _method_report(result)
        if report is None or getattr(report, "status", None) is not EstimationStatus.SUCCESS:
            status = getattr(getattr(report, "status", None), "value", None) or getattr(
                report, "status", None
            )
            reason = getattr(report, "status_reason", None) or getattr(
                report, "diagnostics", None
            )
            detail = ":".join(str(item) for item in (status, reason) if item)
            return None, (
                f"foundry_method_refused_value:{detail}"
                if detail
                else "foundry_method_refused_value"
            )
        return result, None
    except Exception as exc:
        return None, f"foundry_method_refused_value:{exc}"


def _candidate_value_method_trace(
    *,
    selection: Mapping[str, Any],
    requested_method_fqn: str | None,
) -> tuple[str, ...]:
    selected = _optional_text(selection.get("selected_method_fqn"))
    if requested_method_fqn:
        return (str(requested_method_fqn),) if requested_method_fqn else ()
    ordered: list[str] = []
    for value in (selected, *_sequence(selection.get("score_trace"))):
        method_fqn = _optional_text(value)
        if method_fqn and method_fqn not in ordered:
            ordered.append(method_fqn)
    return tuple(ordered)


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
        _object_get(candidate, "candidate_id")
        or _object_get(candidate, "id")
        or "candidate"
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


def _candidate_world_ref(candidate: object, problem: DesignProblem) -> str | None:
    atom = _object_get(candidate, "atom")
    value = _object_get(atom, "world_model_record_ref")
    if value:
        return str(value)
    hint = _runtime_hint_optional(problem, "world_model_record_ref")
    return str(hint) if hint else None


def _grounding_disposition_for_candidate(
    candidate: object,
    *,
    generation_result: object,
) -> object | None:
    candidate_id = _candidate_id(candidate)
    candidate_hash = _candidate_content_hash(candidate)
    for disposition in _sequence(_object_get(generation_result, "grounding_dispositions")):
        disposition_candidate_id = _object_get(disposition, "candidate_id")
        shadow_hash = _object_get(disposition, "shadow_atom_content_hash")
        if disposition_candidate_id and str(disposition_candidate_id) == candidate_id:
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
    if str(_object_get(disposition, "disposition") or "") == "shadow_bound":
        shadow_hash = _object_get(disposition, "shadow_atom_content_hash")
        if shadow_hash and str(shadow_hash) != _candidate_content_hash(candidate):
            issues.append("candidate_cgf_content_hash_mismatch")
        if not shadow_hash:
            issues.append("candidate_cgf_shadow_hash_missing")
    return tuple(_dedupe(issues))


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
) -> CandidateGroundingObservation:
    return CandidateGroundingObservation(
        candidate_id=candidate_id,
        status="grounding_unavailable",
        grounding_score=0.0,
        issue_codes=tuple(str(item) for item in issue_codes if str(item)),
        evidence_refs=(),
        current_valid=False,
        grounding_source="grounding_unavailable",
    )


def _cg4_quarantine_refs(chain: object) -> tuple[object | None, object | None]:
    if chain is None:
        return None, None
    handoff = _object_get(chain, "quarantine_handoff") or _object_get(
        chain, "cg4_quarantine_handoff"
    )
    proxy_gap = _object_get(chain, "proxy_gap_risk") or _object_get(
        chain, "cg4_proxy_gap_risk"
    )
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
        str(item)
        for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
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
    issue = value_issue or (
        grounding.issue_codes[0] if grounding.issue_codes else grounding.status
    )
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
            code=(
                f"n6.value.{issue}"
                if value_issue
                else f"n6.{grounding.status}.{issue}"
            ),
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
            value_port.authority_blockers[0]
            if value_port.authority_blockers
            else "value_blocked"
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
) -> DesignRevisionRequest:
    previous_grammar = tuple(
        str(item)
        for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
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
    next_ref = "candidate://pending/" + gy_content_hash(
        {
            "previous_candidate_ref": candidate_id,
            "counterexample_ref": counterexample.counterexample_ref,
            "revision_strategy": strategy,
            "new_grammar": new_grammar_elements,
        }
    ).removeprefix("sha256:")[:16]
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
            str(item)
            for item in problem.runtime_hints.get("generation_cycle_grammar", ("seed",))
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
) -> list[CandidateSummary]:
    certified = set(promotion.certified_candidate_ids)
    result: list[CandidateSummary] = []
    for summary in summaries:
        can_promote = (
            summary.candidate_id in certified
            and promotion.status == "certified_current_valid"
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
    "PromotionPortObservation",
    "RealValueOwnerGateway",
    "SimulationPortObservation",
    "StrangleReceipt",
    "ValueCalibrationReceipt",
    "ValueGateReceipt",
    "ValuePortObservation",
    "ValueTransportReceipt",
    "enforce_no_retry_without_new_grammar",
    "validate_generation_cycle_run",
]
