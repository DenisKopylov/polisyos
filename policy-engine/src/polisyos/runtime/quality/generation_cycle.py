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
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class ValuePortObservation(_StrictModel):
    """N8 value-port observation; pending is explicit and non-authoritative."""

    status: ValuePortStatus = "value_pending_n8"
    value_ref: str | None = None
    authority_blockers: tuple[str, ...] = ("value_gate_pending_n8",)
    reason: str = "N8 value gate is not present; N6 will not fabricate value."


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

    def __init__(self, controller: JointSimulationHorizonController | None = None) -> None:
        self._controller = controller or JointSimulationHorizonController()

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
            return SimulationPortObservation(
                candidate_id=candidate_id,
                status="simulation_pending_n5",
                authority_blockers=("joint_simulation_request_missing",),
                diagnostics={"port": "N5", "reason": "joint_simulation_request_missing"},
                k_world_ref_before=_candidate_world_ref(candidate, problem),
                k_world_ref_after=_candidate_world_ref(candidate, problem),
            )
        result = self._controller.run(request)
        k_world_ref = _candidate_world_ref(candidate, problem)
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
            },
            k_world_ref_before=k_world_ref,
            k_world_ref_after=k_world_ref,
        )


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
        self._value_port = value_port or PendingN8ValuePort()
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
        world_ref = str(
            problem.runtime_hints.get("world_model_record_ref")
            or f"s0://substrate-registry/{registry.substrate_version_id}"
        )
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
            world_model_record_ref=problem.runtime_hints.get("world_model_record_ref"),
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
            summary.model_copy(update={"counterexample_ref": counterexample.counterexample_ref})
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


def _problem_ref(problem: DesignProblem) -> str:
    return gy_content_hash(problem.model_dump(mode="json"))


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
    hint = problem.runtime_hints.get("world_model_record_ref")
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
                problem.runtime_hints.get("world_model_record_ref")
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
) -> CounterexampleRecord:
    issue = grounding.issue_codes[0] if grounding.issue_codes else grounding.status
    slug = _slug(problem.design_problem_id)
    return CounterexampleRecord(
        counterexample_id=f"gy.n6.counterexample.{slug}.{cycle_index + 1:03d}",
        counterexample_ref=f"pdc://gy/n6/{slug}/counterexample/{cycle_index + 1:03d}",
        case_id=problem.design_problem_id,
        candidate_ref=candidate_id,
        counterexample_class="real_design_blocker",
        diagnostic=TypedDiagnosticRecord(
            diagnostic_id=f"gy.n6.diagnostic.{slug}.{cycle_index + 1:03d}",
            code=f"n6.{grounding.status}.{issue}",
            severity="block",
            message=f"Candidate {candidate_id} requires revision for {issue}.",
            authority_purpose="shadow_search_refinement_only",
            owner="team-policyos-runtime",
            rule_version_ref=GENERATION_CYCLE_RULE_VERSION,
        ),
        evidence_refs=list(grounding.evidence_refs or ("grounding://missing",)),
        routed_to="refinement_policy",
    )


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
    "SimulationPortObservation",
    "StrangleReceipt",
    "ValuePortObservation",
    "enforce_no_retry_without_new_grammar",
    "validate_generation_cycle_run",
]
