from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from polisyos.runtime.quality.design_problem import (
    AuthorityProfile,
    CandidateLever,
    CandidateLeverSpace,
    DesignConstraint,
    DesignObjective,
    DesignProblem,
    DesignStakeholder,
    EvidenceAcquisitionNeeds,
    EvidenceNeed,
    JurisdictionTimeSemantics,
    NLProvenance,
    OutcomeOfInterest,
)
from polisyos.runtime.quality.generation_cycle import (
    CandidateGroundingObservation,
    GenerationCycleController,
    GenerationCycleError,
    GenerationCycleRun,
    PendingN8ValuePort,
    PolicyGroundingPort,
    PromotionPortObservation,
    SimulationPortObservation,
    StrangleReceipt,
    enforce_no_retry_without_new_grammar,
    validate_generation_cycle_run,
)
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tools.quality.validation import check_layer3_gy_generation_cycle_contract as contract

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class _Atom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str = "world_model_record_test"
    target_world_slots: tuple[str, ...] = ("firm_survival",)


@dataclass(frozen=True)
class _Candidate:
    candidate_id: str
    atom: _Atom
    diversity_key: tuple[str, str, str, str]
    status: str = "candidate_unverified"


@dataclass(frozen=True)
class _Ranking:
    candidate_id: str
    score: float
    voi_estimate: float
    trust_level: str = "search_guiding"
    promotion_allowed: bool = False


@dataclass(frozen=True)
class _GenerationResult:
    status: str
    candidates: tuple[_Candidate, ...]
    surrogate_rankings: tuple[_Ranking, ...]
    grounding_dispositions: tuple[Any, ...] = ()


@dataclass(frozen=True)
class _CertificateChain:
    cg1_certificate_id: str = "cg1_cert_test"
    cg1_content_hash: str = "sha256:" + "a" * 64
    cg2_certificate_id: str = "cg2_cert_test"
    cg2_content_hash: str = "sha256:" + "b" * 64
    cg3_certificate_id: str = "cg3_cert_test"
    cg3_content_hash: str = "sha256:" + "c" * 64
    cg4_proxy_gap_risk_id: str | None = None
    cg4_proxy_gap_content_hash: str | None = None
    cg4_quarantine_handoff_id: str | None = None
    cg4_quarantine_handoff_hash: str | None = None
    cg5_action_certificate_id: str | None = None
    cg5_action_content_hash: str | None = None
    cg5_ticket_id: str | None = None
    cg5_ticket_hash: str | None = None


@dataclass(frozen=True)
class _GroundingDisposition:
    proposal_id: str
    candidate_id: str | None
    raw_candidate_hash: str
    disposition: str
    selected_relation: str
    shadow_atom_content_hash: str | None = None
    identified_atom_id: str | None = "atom_test"
    cg2_decision: str | None = "shadow_frozen"
    cg2_reason: str | None = "cg2_frozen_until_cg6"
    cg3_decision: str | None = "shadow"
    cg3_reason: str | None = "cg3_shadow_only"
    rejected_cause: dict[str, Any] | None = None
    certificate_chain: _CertificateChain = _CertificateChain()
    bridge_missing_records: tuple[dict[str, Any], ...] = ()


class _CounterexampleAwareGenerator:
    def __init__(self) -> None:
        self.problems: list[DesignProblem] = []

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        self.problems.append(problem)
        grammar = tuple(problem.runtime_hints.get("generation_cycle_grammar", ()))
        if cycle_index == 0:
            candidates = (
                _Candidate(
                    candidate_id="candidate_cycle_1",
                    atom=_Atom("candidate_cycle_1", "sha256:" + "1" * 64),
                    diversity_key=("grant", "firms", "proxy_only", "baseline"),
                ),
            )
            rankings = (
                _Ranking(
                    candidate_id="candidate_cycle_1",
                    score=0.93,
                    voi_estimate=0.82,
                ),
            )
        elif "repair:search_ceiling_repair_required:missing_supporting_data" in grammar:
            candidates = (
                _Candidate(
                    candidate_id="candidate_cycle_2",
                    atom=_Atom("candidate_cycle_2", "sha256:" + "2" * 64),
                    diversity_key=("grant", "firms", "grounding_repair", "data_bound"),
                ),
            )
            rankings = (
                _Ranking(
                    candidate_id="candidate_cycle_2",
                    score=0.31,
                    voi_estimate=0.41,
                ),
            )
        else:
            candidates = (
                _Candidate(
                    candidate_id="candidate_repeat",
                    atom=_Atom("candidate_repeat", "sha256:" + "1" * 64),
                    diversity_key=("grant", "firms", "proxy_only", "baseline"),
                ),
            )
            rankings = (
                _Ranking(
                    candidate_id="candidate_repeat",
                    score=0.93,
                    voi_estimate=0.82,
                ),
            )
        return _GenerationResult(
            status="generated",
            candidates=candidates,
            surrogate_rankings=rankings,
        )


class _AlwaysLowGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.2 if cycle_index == 0 else 0.68,
            issue_codes=("missing_supporting_data",) if cycle_index == 0 else (),
            evidence_refs=() if cycle_index == 0 else ("evidence://supporting-data",),
            current_valid=False,
        )


class _NoNewGrammarRevision:
    def __call__(self, **kwargs: Any) -> Any:
        prior_cycle = kwargs["prior_cycle"]
        return prior_cycle.revision_request.model_copy(
            update={
                "new_grammar_elements": (),
                "next_grammar_elements": prior_cycle.revision_request.previous_grammar_elements,
                "revised_problem": kwargs["problem"],
                "next_candidate_ref": prior_cycle.selected_candidate_ref,
            }
        )


class _AcquisitionGrounding:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
        generation_result: Any | None = None,
    ) -> CandidateGroundingObservation:
        del problem, cycle_index, generation_result
        return CandidateGroundingObservation(
            candidate_id=str(candidate.candidate_id),
            status="grounding_gap",
            grounding_score=0.1,
            issue_codes=("acquire_data:owner_panel_missing",),
            current_valid=False,
        )


class _EmptyGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        return _GenerationResult(status="generation_unavailable", candidates=(), surrogate_rankings=())


class _LegacyOnlyGenerationPort:
    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        candidate = _Candidate(
            candidate_id="candidate_legacy_only",
            atom=_Atom("candidate_legacy_only", "sha256:" + "3" * 64),
            diversity_key=("grant", "firms", "legacy_matrix", "baseline"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate.candidate_id, score=0.88, voi_estimate=0.4),
            ),
            grounding_dispositions=(),
        )


class _CgfGenerationPort:
    def __init__(self, *, missing_owner_target: bool = False, proxy_gap: bool = False) -> None:
        self._missing_owner_target = missing_owner_target
        self._proxy_gap = proxy_gap

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        candidate = _Candidate(
            candidate_id="candidate_cgf_shadow",
            atom=_Atom(
                "candidate_cgf_shadow",
                "sha256:" + "4" * 64,
                target_world_slots=() if self._missing_owner_target else ("firm_survival",),
            ),
            diversity_key=("grant", "firms", "cgf_shadow", "baseline"),
        )
        chain = _CertificateChain(
            cg4_proxy_gap_risk_id="cg4_proxy_gap_deadbeefdeadbeef" if self._proxy_gap else None,
            cg4_proxy_gap_content_hash="sha256:" + "d" * 64 if self._proxy_gap else None,
            cg4_quarantine_handoff_id="cg4_quarantine_deadbeefdeadbeef"
            if self._proxy_gap
            else None,
            cg4_quarantine_handoff_hash="sha256:" + "e" * 64 if self._proxy_gap else None,
            cg5_action_certificate_id="cg5_action_deadbeefdeadbeef"
            if self._proxy_gap
            else None,
            cg5_action_content_hash="sha256:" + "f" * 64 if self._proxy_gap else None,
        )
        disposition = _GroundingDisposition(
            proposal_id="proposal.cgf_shadow",
            candidate_id=candidate.candidate_id,
            raw_candidate_hash="sha256:" + "5" * 64,
            disposition="shadow_bound",
            selected_relation="exact",
            shadow_atom_content_hash=candidate.atom.content_hash,
            certificate_chain=chain,
            bridge_missing_records=(
                {
                    "pattern": "bridge_missing",
                    "owner": "CG4",
                    "integration_status": "handoff_artifact_n6_direct_intake_not_wired",
                },
            )
            if self._proxy_gap
            else (),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(candidate_id=candidate.candidate_id, score=0.91, voi_estimate=0.6),
            ),
            grounding_dispositions=(disposition,),
        )


class _FabricatedPromotionPort:
    def __call__(self, *, summaries: Any, problem: DesignProblem) -> PromotionPortObservation:
        del problem
        return PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=tuple(summary.candidate_id for summary in summaries),
        )


class _ShrinkingSimulationPort:
    def __call__(
        self,
        *,
        candidate: Any,
        problem: DesignProblem,
        cycle_index: int,
    ) -> SimulationPortObservation:
        del problem, cycle_index
        return SimulationPortObservation(
            candidate_id=str(candidate.candidate_id),
            status="joint_simulated",
            simulation_ref="sha256:" + "6" * 64,
            k_world_ref_before="world_model_record_before",
            k_world_ref_after="world_model_record_after",
        )


def _problem(problem_id: str = "generic_cycle_problem") -> DesignProblem:
    return DesignProblem(
        design_problem_id=problem_id,
        problem_statement="Improve firm survival with grounded support under fiscal constraints.",
        domain="generic_policy",
        nl_provenance=NLProvenance(
            raw_request="Improve firm survival with grounded support.",
            source_surface="test_generation_cycle",
        ),
        authority_profile=AuthorityProfile(
            requester_authority="research_lab",
            requested_authority_level="research",
            mandate="test-only research mandate",
        ),
        jurisdiction_time=JurisdictionTimeSemantics(
            region="UA",
            valid_time="2026",
            as_of="2026-06-29",
            policy_time="2026",
            data_time="2026",
        ),
        objectives=[
            DesignObjective(
                objective_id="firm_survival",
                description="Improve firm survival",
                metric_id="firm_survival",
            )
        ],
        constraints=[
            DesignConstraint(
                constraint_id="shadow_only",
                description="Generated candidates remain shadow until A/N9 certification.",
                hard=True,
                admissibility_basis="request_text",
                source_text="Do not promote generated candidates.",
            )
        ],
        stakeholders=[
            DesignStakeholder(
                stakeholder_id="firms",
                name="Firms",
                role="target_population",
            )
        ],
        outcome_of_interest=OutcomeOfInterest(
            target_variable="firm_survival",
            metric_id="firm_survival",
            estimand="average_treatment_effect",
        ),
        candidate_lever_space=CandidateLeverSpace(
            allowed_operator_kinds=["grant", "tax_relief"],
            candidate_levers=[
                CandidateLever(
                    lever_id="grant",
                    operator_kind="grant",
                    instrument="Targeted grant",
                    target_slot="government_balance",
                )
            ],
        ),
        evidence_acquisition_needs=EvidenceAcquisitionNeeds(
            needs=[
                EvidenceNeed(
                    need_id="supporting_data",
                    question="Which data grounds this effect?",
                    required_for="A-side grounding",
                )
            ]
        ),
    )


def _budget(max_usd: str = "5.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


@pytest.mark.asyncio
async def test_controller_runs_counterexample_driven_revision_over_two_real_cycles() -> None:
    generator = _CounterexampleAwareGenerator()
    controller = GenerationCycleController(
        generation_port=generator,
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(
        _problem(),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert isinstance(run, GenerationCycleRun)
    assert [cycle.selected_candidate_ref for cycle in run.cycles[:2]] == [
        "candidate_cycle_1",
        "candidate_cycle_2",
    ]
    assert run.cycles[1].selected_candidate_content_hash != run.cycles[0].selected_candidate_content_hash
    assert run.cycles[1].driven_by_counterexample_ref == run.cycles[0].counterexample.counterexample_ref
    assert run.cycles[0].revision_request.new_grammar_elements == (
        "repair:search_ceiling_repair_required:missing_supporting_data",
    )
    assert run.cycles[1].introduced_grammar_elements == (
        "repair:search_ceiling_repair_required:missing_supporting_data",
    )
    assert run.cycles[1].revision_driver == "counterexample"
    assert run.cycles[0].voi_decision.next_action == "advance"
    assert run.cycles[-1].voi_decision.next_action in {"stop", "escalate"}
    assert run.fronts.decision.candidate_ids == ()
    assert run.fronts.quarantine.candidate_ids == ("candidate_cycle_1",)
    assert run.fronts.research.candidate_ids == ("candidate_cycle_2",)
    assert run.fronts.portfolio.candidate_ids == ()
    assert run.value_port.status == "value_pending_n8"
    assert validate_generation_cycle_run(run) == ()


def test_no_retry_without_new_grammar_blocks_same_candidate_retry() -> None:
    with pytest.raises(GenerationCycleError, match="no_retry_without_new_grammar"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_cycle_1",
            next_candidate_ref="candidate_cycle_1",
            previous_grammar_elements=("base",),
            next_grammar_elements=("base",),
            introduced_grammar_elements=(),
        )


def test_no_retry_without_new_grammar_rejects_laundered_revision_claim() -> None:
    with pytest.raises(GenerationCycleError, match="new_grammar_elements_not_introduced"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_cycle_1",
            next_candidate_ref="candidate_cycle_2",
            previous_grammar_elements=("base",),
            next_grammar_elements=("base",),
            introduced_grammar_elements=("fabricated_new_axis",),
        )


@pytest.mark.asyncio
async def test_controller_refuses_live_retry_without_new_grammar() -> None:
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
        revision_policy=_NoNewGrammarRevision(),
    )

    run = await controller.run(
        _problem(),
        budget_state=_budget(),
        min_cycles=2,
        max_cycles=3,
    )

    assert run.terminal_status == "blocked"
    assert run.blocked_reason == "no_retry_without_new_grammar"
    assert run.cycles[0].refinement_decision.decision == "block_candidate"
    assert run.cycles[0].search_iteration.status == "blocked_no_retry"


@pytest.mark.asyncio
async def test_revision_changes_when_prior_terminal_changes() -> None:
    search_controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )
    acquisition_controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
    )

    search_run = await search_controller.run(_problem(), budget_state=_budget(), max_cycles=1)
    acquisition_run = await acquisition_controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert search_run.cycles[0].terminal_kind == "search_ceiling_repair_required"
    assert acquisition_run.cycles[0].terminal_kind == "acquisition_required"
    assert (
        search_run.cycles[0].revision_request.new_grammar_elements
        != acquisition_run.cycles[0].revision_request.new_grammar_elements
    )


@pytest.mark.asyncio
async def test_voi_scheduler_changes_next_action_under_varying_budget_and_terminal() -> None:
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )

    advance = controller.decide_next_action(
        candidate_id="candidate_advance",
        proxy_score=0.8,
        voi_estimate=0.8,
        prior_terminal_kind="search_ceiling_repair_required",
        budget_state=_budget("5.0"),
    )
    stop = controller.decide_next_action(
        candidate_id="candidate_stop",
        proxy_score=0.2,
        voi_estimate=0.0,
        prior_terminal_kind="frontier_stable",
        budget_state=_budget("5.0"),
    )
    escalate = controller.decide_next_action(
        candidate_id="candidate_escalate",
        proxy_score=0.8,
        voi_estimate=0.8,
        prior_terminal_kind="acquisition_required",
        budget_state=_budget("5.0"),
    )

    assert advance.next_action == "advance"
    assert stop.next_action == "stop"
    assert escalate.next_action == "escalate"
    assert {advance.scheduler_action, stop.scheduler_action, escalate.terminal_kind} >= {
        "advance",
        "reject",
        "acquisition_required",
    }


@pytest.mark.asyncio
async def test_empty_llm_generation_uses_grammar_fallback_without_promotion() -> None:
    controller = GenerationCycleController(
        generation_port=_EmptyGenerationPort(),
        grounding_port=_AlwaysLowGrounding(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.candidate_summaries
    assert {summary.generation_channel for summary in run.candidate_summaries} == {
        "grammar_fallback"
    }
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_default_grounding_port_rejects_legacy_matrix_without_cgf_disposition() -> None:
    controller = GenerationCycleController(
        generation_port=_LegacyOnlyGenerationPort(),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.cycles[0].grounding.status == "grounding_unavailable"
    assert "cgf_disposition_missing" in run.cycles[0].grounding.issue_codes
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_candidate_owner_target_missing_fails_closed_through_cgf_grounding() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(missing_owner_target=True),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.cycles[0].grounding.status == "grounding_unavailable"
    assert "candidate_owner_target_missing" in run.cycles[0].grounding.issue_codes
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_proxy_gap_candidate_stays_quarantined_before_any_promotion() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(proxy_gap=True),
        grounding_port=PolicyGroundingPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_FabricatedPromotionPort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    summary = run.candidate_summaries[0]
    assert summary.front == "quarantine"
    assert summary.adversarial_validation_status == "completed_shadow_only"
    assert summary.quarantine_action == "adversarial_validate"
    assert run.fronts.decision.candidate_ids == ()
    assert run.fronts.quarantine.candidate_ids == (summary.candidate_id,)


@pytest.mark.asyncio
async def test_k_sim_does_not_shrink_k_world() -> None:
    with pytest.raises(ValueError, match="k_sim_must_not_shrink_k_world"):
        _ShrinkingSimulationPort()(
            candidate=_Candidate(
                candidate_id="candidate_bad_sim",
                atom=_Atom("candidate_bad_sim", "sha256:" + "7" * 64),
                diversity_key=("grant", "firms", "sim", "bad"),
            ),
            problem=_problem(),
            cycle_index=0,
        )


@pytest.mark.asyncio
async def test_generation_cycle_contract_mutations_turn_red() -> None:
    payload = contract.load_contract_payload(REPO_ROOT)
    report = contract.validate_payload(payload)

    assert report["status"] == "pass", report["issues"]
    mutation_statuses = {
        item["mutation_id"]: item["status"]
        for item in payload["behavioral_mutations"]
    }
    assert mutation_statuses == {
        "revision_not_terminal_driven": "red",
        "retry_without_new_grammar_admitted": "red",
        "voi_scheduler_ignored_fixed_cycle_count": "red",
        "single_pass_fixture_survives_as_production_cycle": "red",
        "proxy_gap_candidate_promoted_without_adversarial_validate": "red",
        "decision_front_admitted_non_current_valid": "red",
        "grounding_bypassed_cgf_firewall": "red",
        "coverage_depends_on_llm": "red",
        "k_sim_shrank_k_world": "red",
        "full_denominator_curated_subset": "red",
    }
    assert payload["denominators"]["counts"] == {
        "front_kinds": 4,
        "grounding_dispositions": 5,
        "grounding_statuses": 5,
        "scheduling_actions": 4,
        "terminal_kinds": 12,
    }


def test_generation_cycle_strangle_receipt_recomputes_production_callers() -> None:
    receipt = StrangleReceipt.recompute(REPO_ROOT)

    assert receipt.status == "strangled"
    assert receipt.production_single_pass_callers == ()
    assert receipt.default_cycle_controller.endswith("GenerationCycleController")
    assert not any(
        "src/polisyos/runtime/http/services/control/workspace_loop_transition.py" in caller
        for caller in receipt.allowed_fixture_callers
    )


def test_generation_cycle_strangle_receipt_counts_new_production_caller(tmp_path: Path) -> None:
    caller = (
        tmp_path
        / "src"
        / "polisyos"
        / "runtime"
        / "http"
        / "services"
        / "control"
        / "production_single_pass_probe.py"
    )
    caller.parent.mkdir(parents=True)
    caller.write_text(
        "def execute(loop):\n"
        "    return loop.run_fixture('ua_msme_credit_worldbank_measurement')\n",
        encoding="utf-8",
    )

    receipt = StrangleReceipt.recompute(tmp_path)

    assert receipt.status == "drift"
    assert receipt.allowed_fixture_callers == ()
    assert receipt.production_single_pass_callers == (
        "src/polisyos/runtime/http/services/control/production_single_pass_probe.py:2",
    )
