from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_args

import pytest

from polisyos.data_requirement import DataQualityMinimums, DataRequirementScope, DataRequirementSpec
from polisyos.data_requirement.compiler import compile_data_requirements_for_scenario
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_planner import (
    AcquisitionCaptureProvenance,
    AcquisitionOwnerArtifact,
    AcquisitionWorldSnapshot,
    RecordedAcquisitionOwnerGateway,
)
from polisyos.runtime.quality.cycle_substrate import (
    CandidateLeverEvidence,
    CycleSubstrateContext,
    build_cycle_substrate_context,
    cycle_substrate_context_binding_hash,
)
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
    CandidateSummary,
    GenerationCycleController,
    GenerationCycleError,
    GenerationCycleRun,
    JointSimulationPort,
    PendingN8ValuePort,
    PolicyGroundingPort,
    PromotionPortObservation,
    SimulationPortObservation,
    StrangleReceipt,
    ValuePortObservation,
    _apply_promotion_to_summaries,
    _build_boundary_world_model_record,
    _derive_fronts,
    _grounding_disposition_denominator,
    enforce_no_retry_without_new_grammar,
    validate_generation_cycle_run,
)
from polisyos.runtime.quality.grounding_disposition_vocab import GroundingDispositionKind
from polisyos.runtime.quality.substrate_registry import (
    SubstrateCoverage,
    SubstrateLayer,
    SubstrateRegistration,
    SubstrateRegistry,
    SubstrateSchemaRegime,
    SubstrateTrustTier,
    build_substrate_registry,
    build_substrate_registry_entry,
)
from polisyos.runtime.quality.world_model_record import WorldModelRecordError
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from tools.quality.validation import check_layer3_gy_generation_cycle_contract as contract

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_grounding_disposition_denominator_derives_from_canonical_type() -> None:
    denominator = tuple(str(item) for item in get_args(GroundingDispositionKind))

    assert _grounding_disposition_denominator() == denominator
    assert contract._denominators()["grounding_dispositions"] == sorted(denominator)


@dataclass(frozen=True)
class _Atom:
    intervention_id: str
    content_hash: str
    status: str = "candidate_unverified"
    world_model_record_ref: str | None = "world_model_record_test"
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
        elif "lever:grant:adversarial_validate:missing_supporting_data" in grammar:
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


class _ConstantStrategyRevision:
    def __call__(self, **kwargs: Any) -> Any:
        prior_cycle = kwargs["prior_cycle"]
        default = kwargs["default_revision"]
        return default.model_copy(
            update={
                "revision_strategy": "adversarial_validate",
                "strategy_payload": {
                    **default.strategy_payload,
                    "terminal_kind": "constant",
                },
                "new_grammar_elements": (
                    "lever:grant:adversarial_validate:missing_supporting_data",
                ),
                "next_grammar_elements": (
                    *prior_cycle.revision_request.previous_grammar_elements,
                    "lever:grant:adversarial_validate:missing_supporting_data",
                ),
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


class _DispositionOnlyGenerationPort:
    """Expose a real N4 non-binding denominator with no fabricated atom."""

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        return _GenerationResult(
            status="generated",
            candidates=(),
            surrogate_rankings=(),
            grounding_dispositions=(
                _GroundingDisposition(
                    proposal_id="gy_n4.education_teaching_method",
                    candidate_id=None,
                    raw_candidate_hash="sha256:" + "7" * 64,
                    disposition="novel_cg3",
                    selected_relation="novel-candidate",
                    identified_atom_id=None,
                    cg2_decision="novel_candidate",
                    cg2_reason="cg2_relation_not_bind_eligible",
                    cg3_decision="route_to_acquisition",
                    cg3_reason="cg3_candidate_unbound",
                ),
            ),
        )


class _NoPromotionPort:
    def __call__(
        self,
        *,
        summaries: Any,
        problem: DesignProblem,
    ) -> PromotionPortObservation:
        del summaries, problem
        return PromotionPortObservation(
            status="not_promoted",
            reason="candidate_unbound",
        )


class _MixedBindingAndDispositionPort:
    """Return one bound candidate and one honest non-binding CGF row."""

    async def __call__(
        self,
        problem: DesignProblem,
        *,
        cycle_index: int,
    ) -> _GenerationResult:
        del problem, cycle_index
        candidate = _Candidate(
            candidate_id="candidate_mixed_bound",
            atom=_Atom(
                "candidate_mixed_bound",
                "sha256:" + "8" * 64,
            ),
            diversity_key=("grant", "firms", "mixed", "bound"),
        )
        return _GenerationResult(
            status="generated",
            candidates=(candidate,),
            surrogate_rankings=(
                _Ranking(
                    candidate_id=candidate.candidate_id,
                    score=0.9,
                    voi_estimate=0.2,
                ),
            ),
            grounding_dispositions=(
                _GroundingDisposition(
                    proposal_id="gy_n4.bound",
                    candidate_id=candidate.candidate_id,
                    raw_candidate_hash="sha256:" + "9" * 64,
                    disposition="shadow_bound",
                    selected_relation="exact",
                    shadow_atom_content_hash=candidate.atom.content_hash,
                ),
                _GroundingDisposition(
                    proposal_id="gy_n4.unbound",
                    candidate_id=None,
                    raw_candidate_hash="sha256:" + "a" * 64,
                    disposition="novel_cg3",
                    selected_relation="novel-candidate",
                    identified_atom_id=None,
                    cg2_decision="novel_candidate",
                    cg2_reason="cg2_relation_not_bind_eligible",
                    cg3_decision="route_to_acquisition",
                    cg3_reason="cg3_candidate_unbound",
                ),
            ),
        )


@pytest.mark.asyncio
async def test_disposition_only_n4_result_never_falls_back_to_grammar() -> None:
    """A usable N4 refusal is a cycle candidate denominator, not spec absence."""

    run = await GenerationCycleController(
        generation_port=_DispositionOnlyGenerationPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_NoPromotionPort(),
        repo_root=REPO_ROOT,
    ).run(
        _problem("education_disposition_only"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    assert run.candidate_summaries[0].generation_channel == "n4_owner"
    assert cycle.selected_candidate_ref == "gy_n4.education_teaching_method"
    assert cycle.selected_candidate_content_hash == "sha256:" + "7" * 64
    assert cycle.grounding.grounding_source == "cgf_firewall"
    assert cycle.grounding.grounding_disposition == "novel_cg3"
    assert cycle.terminal_kind == "search_ceiling_repair_required"
    assert cycle.terminal_kind != "a_spec_gap"
    assert "grammar_fallback" not in json.dumps(cycle.model_dump(mode="json"))


@pytest.mark.asyncio
async def test_mixed_n4_result_keeps_non_binding_disposition_in_denominator() -> None:
    """The bridge covers every disposition, not only the all-empty case."""

    run = await GenerationCycleController(
        generation_port=_MixedBindingAndDispositionPort(),
        value_port=PendingN8ValuePort(),
        promotion_port=_NoPromotionPort(),
        repo_root=REPO_ROOT,
    ).run(
        _problem("mixed_disposition_denominator"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    assert {summary.candidate_id for summary in run.candidate_summaries} == {
        "candidate_mixed_bound",
        "gy_n4.unbound",
    }
    assert {summary.generation_channel for summary in run.candidate_summaries} == {
        "n4_owner"
    }
    unbound = next(
        summary
        for summary in run.candidate_summaries
        if summary.candidate_id == "gy_n4.unbound"
    )
    assert unbound.content_hash == "sha256:" + "a" * 64
    assert unbound.grounding_disposition == "novel_cg3"


class _FabricatedPromotionPort:
    def __call__(self, *, summaries: Any, problem: DesignProblem) -> PromotionPortObservation:
        del problem
        return PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=tuple(summary.candidate_id for summary in summaries),
            receipts=tuple(
                _n9_receipt(summary.candidate_id, consumer_promotable=True)
                for summary in summaries
            ),
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


def _domain_problem(
    *,
    domain: str,
    region: str,
    valid_time: str,
    as_of: str,
    outcome: str,
    stakeholder_id: str,
) -> DesignProblem:
    """Build a domain-shaped problem without changing the boundary owner."""

    return _problem(f"{domain}_boundary_problem").model_copy(
        update={
            "domain": domain,
            "jurisdiction_time": JurisdictionTimeSemantics(
                region=region,
                valid_time=valid_time,
                as_of=as_of,
                policy_time=valid_time,
                data_time=valid_time,
            ),
            "stakeholders": [
                DesignStakeholder(
                    stakeholder_id=stakeholder_id,
                    name=stakeholder_id.replace("_", " ").title(),
                    role="affected_population",
                )
            ],
            "outcome_of_interest": OutcomeOfInterest(
                target_variable=outcome,
                metric_id=outcome,
                estimand="average_treatment_effect",
            ),
        }
    )


def _lane0_registry(*, domain: str, source_id: str) -> SubstrateRegistry:
    """Build one content-addressed registry with domain-shaped vocabulary."""

    registration = SubstrateRegistration(
        source_id=source_id,
        family_id=f"{domain}_causal_priors",
        layer=SubstrateLayer.L2,
        coverage=SubstrateCoverage(
            coverage_score=0.74,
            coverage_kind="lane0.causal_claim_coverage",
            coverage_rule_ref=f"lane0://{domain}/coverage",
            observation_count=7,
            metric_binding_count=3,
        ),
        trust_tier=SubstrateTrustTier(
            tier="derived_proxy",
            trust_cap=0.5,
            trust_multiplier=0.6,
            min_coverage=0.0,
            max_coverage=1.0,
            authority_ref=f"lane0://{domain}/trust",
        ),
        identification_mode="causal_prior_candidate",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"{domain}_schema_v1",
            authority_ref=f"lane0://{domain}/schema",
            source_version="1",
        ),
        data_version=f"{domain}-data-v1",
        snapshot_id=f"{domain}-snapshot-v1",
        source_snapshot_id=f"{domain}-snapshot-v1",
        provenance_refs=(f"lane0://{domain}/causal-claims",),
        authority_refs=(f"lane0://{domain}/registry-owner",),
    )
    return build_substrate_registry(
        (build_substrate_registry_entry(registration),),
        producer_ref="tests.unit.runtime.quality.test_generation_cycle",
        source_catalog_refs=registration.authority_refs,
    )


def _lane0_cycle_context(
    *,
    runtime_hints: dict[str, Any] | None = None,
) -> tuple[DesignProblem, CycleSubstrateContext]:
    """Build one unseen-shape context through the canonical boundary owner."""

    problem = _domain_problem(
        domain="water_quality",
        region="dnieper_basin",
        valid_time="2021/2024",
        as_of="2026-07-12",
        outcome="nitrate_load",
        stakeholder_id="watershed_communities",
    )
    if runtime_hints is not None:
        problem = problem.model_copy(update={"runtime_hints": runtime_hints})
    registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.duckdb",
    )
    selected_hash = registry.entries[0].entry_content_hash
    world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="nitrate_load",
        policy_slot_ids=("nitrate_load",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
    )
    problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    substrate_input_hash = gy_content_hash(
        {"domain": problem.domain, "registry": registry.content_hash}
    )
    binding_hash = cycle_substrate_context_binding_hash(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_input_content_hash=substrate_input_hash,
        substrate_registry_content_hash=registry.content_hash,
        world_model_record_id=world.world_model_record_id,
        world_model_record_content_hash=world.content_hash,
        world_model_record_authority_status=world.authority_status,
        selected_registry_entry_hashes=(selected_hash,),
    )
    candidate = CandidateLeverEvidence(
        lever_id="riparian_buffer_width",
        instrument="water.riparian_buffer_width",
        target_concept="water.nitrate_load",
        status="candidate_unbound",
        entry_content_hash=gy_content_hash(
            {"lever": "riparian_buffer_width", "domain": "water_quality"}
        ),
        substrate_input_content_hash=substrate_input_hash,
        selected_registry_entry_hash=selected_hash,
        context_binding_hash=binding_hash,
        source_refs=("lane0://water-quality/lever",),
    )
    context = build_cycle_substrate_context(
        design_problem_ref=problem_ref,
        domain=problem.domain,
        substrate_registry=registry,
        selected_registry_entry_hashes=(selected_hash,),
        world_model_record=world,
        intervention_substrate=None,
        candidate_levers=(candidate,),
        transport_context=None,
        source_pack_content_hash=gy_content_hash("water-quality-pack"),
        substrate_input_content_hash=substrate_input_hash,
    )
    return problem, context


def test_joint_port_reuses_exact_cycle_context_wmr() -> None:
    """N5 receives the exact WMR object bound into the cycle context."""

    problem, context = _lane0_cycle_context()
    candidate = _Candidate(
        candidate_id="candidate_water_quality",
        atom=_Atom(
            "candidate_water_quality",
            "sha256:" + "b" * 64,
            world_model_record_ref=context.world_model_record.world_model_record_id,
            target_world_slots=("nitrate_load",),
        ),
        diversity_key=("buffer", "watershed", "water", "lane0"),
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )

    assert observation.world_model_record is context.world_model_record
    assert observation.diagnostics["world_model_source"] == "cycle_substrate_context"
    assert observation.k_world_ref_before == context.world_model_record.content_hash
    assert observation.k_world_ref_after == context.world_model_record.content_hash


def test_joint_port_rejects_candidate_ref_mismatched_to_context_wmr() -> None:
    """A candidate's shaped WMR ref cannot override the resolved context world."""

    problem, context = _lane0_cycle_context()
    candidate = _Candidate(
        candidate_id="candidate_water_quality_wrong_world",
        atom=_Atom(
            "candidate_water_quality_wrong_world",
            "sha256:" + "c" * 64,
            world_model_record_ref="world_model_record_0123456789abcdef",
            target_world_slots=("nitrate_load",),
        ),
        diversity_key=("buffer", "watershed", "water", "wrong-world"),
    )

    observation = JointSimulationPort(
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_model_record_unresolved" in observation.authority_blockers


def test_explicit_joint_request_cannot_bypass_context_wmr() -> None:
    """An explicit N5 request with another concrete WMR is refused before simulation."""

    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
    )

    base_problem, _base_context = _lane0_cycle_context()
    request_registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:explicit_request.duckdb",
    )
    request_world = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=base_problem,
        outcome="nitrate_load",
        policy_slot_ids=("nitrate_load",),
        substrate_registry=request_registry,
        selected_registry_entry_hashes=(
            request_registry.entries[0].entry_content_hash,
        ),
    )
    request = JointSimulationRequest.model_construct(
        world_model_record_ref=request_world.world_model_record_id,
        world_model_record=request_world,
    )
    problem, context = _lane0_cycle_context(
        runtime_hints={"joint_simulation_request": request}
    )
    candidate = _Candidate(
        candidate_id="candidate_water_quality_request_mismatch",
        atom=_Atom(
            "candidate_water_quality_request_mismatch",
            "sha256:" + "f" * 64,
            world_model_record_ref=context.world_model_record.content_hash,
            target_world_slots=("nitrate_load",),
        ),
        diversity_key=("buffer", "watershed", "water", "request-mismatch"),
    )
    calls: list[object] = []

    class _RecordingController:
        def run(self, concrete_request: object) -> object:
            calls.append(concrete_request)
            return SimpleNamespace(
                receipt=SimpleNamespace(payload_hash="sha256:" + "1" * 64),
                uncertainty_kind="K_sim",
                promotion_ready_value_packet={},
                engine_decisions=(),
                trajectories=(),
                interaction_terms=(),
            )

    observation = JointSimulationPort(
        controller=_RecordingController(),
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "cycle_substrate_request_wmr_mismatch" in observation.authority_blockers
    assert calls == []


def test_explicit_joint_request_atom_refs_bind_before_injected_controller() -> None:
    """A valid nested atom for another world is refused at the single N5 intake."""

    from polisyos.runtime.quality.intervention_atom_binding import (
        InterventionAtomBinding,
        intervention_atom_content_hash,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationRequest,
    )
    from tools.quality.validation import (
        check_layer3_gy_design_generation_contract as n4_contract,
    )

    base_problem, base_context = _lane0_cycle_context()
    n4_payload = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
        ).read_text(encoding="utf-8")
    )
    candidate_payload = n4_contract.first_shadow_bound_recorded_candidate(
        n4_payload
    )
    atom = InterventionAtomBinding.model_validate(candidate_payload["atom"])
    mismatched_atom = atom.model_copy(
        update={"world_model_record_ref": "world_model_record_0123456789abcdef"}
    )
    mismatched_atom = mismatched_atom.model_copy(
        update={"content_hash": intervention_atom_content_hash(mismatched_atom)}
    )
    mismatched_atom = InterventionAtomBinding.model_validate(
        mismatched_atom.model_dump(mode="python")
    )
    request = JointSimulationRequest.model_construct(
        world_model_record_ref=base_context.world_model_record.world_model_record_id,
        world_model_record=base_context.world_model_record,
        intervention_atoms=(mismatched_atom,),
    )
    problem, context = _lane0_cycle_context(
        runtime_hints={"joint_simulation_request": request}
    )
    assert problem.domain == base_problem.domain
    assert context.world_model_record.content_hash == base_context.world_model_record.content_hash
    candidate = _Candidate(
        candidate_id="candidate_water_quality_nested_atom_mismatch",
        atom=_Atom(
            "candidate_water_quality_nested_atom_mismatch",
            "sha256:" + "2" * 64,
            world_model_record_ref=context.world_model_record.content_hash,
            target_world_slots=("nitrate_load",),
        ),
        diversity_key=("buffer", "watershed", "water", "nested-atom-mismatch"),
    )
    calls: list[object] = []

    class _RecordingController:
        def run(self, concrete_request: object) -> object:
            calls.append(concrete_request)
            return SimpleNamespace(
                receipt=SimpleNamespace(payload_hash="sha256:" + "3" * 64),
                uncertainty_kind="K_sim",
                promotion_ready_value_packet={},
                engine_decisions=(),
                trajectories=(),
                interaction_terms=(),
            )

    observation = JointSimulationPort(
        controller=_RecordingController(),
        repo_root=REPO_ROOT,
        cycle_substrate_context=context,
    )(candidate=candidate, problem=problem, cycle_index=0)

    assert observation.status == "simulation_blocked"
    assert "world_model_record_unresolved" in observation.authority_blockers
    assert calls == []


def test_joint_port_cache_key_tracks_canonical_registry_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A changed canonical registry rebuilds the WMR instead of reusing stale world state."""

    from polisyos.runtime.quality import generation_cycle

    problem, _context = _lane0_cycle_context()
    first_registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.v1.duckdb",
    )
    second_registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.v2.duckdb",
    )
    registries = iter((first_registry, second_registry))

    def _next_registry(_repo_root: Path) -> SubstrateRegistry:
        return next(registries)

    monkeypatch.setattr(
        generation_cycle,
        "build_substrate_registry_from_existing_catalogs",
        _next_registry,
    )
    candidate = _Candidate(
        candidate_id="candidate_water_quality_cache",
        atom=_Atom(
            "candidate_water_quality_cache",
            "sha256:" + "d" * 64,
            world_model_record_ref=None,
            target_world_slots=("nitrate_load",),
        ),
        diversity_key=("buffer", "watershed", "water", "cache"),
    )
    port = JointSimulationPort(repo_root=REPO_ROOT)

    first = port(candidate=candidate, problem=problem, cycle_index=0)
    second = port(candidate=candidate, problem=problem, cycle_index=1)

    assert first.world_model_record is not None
    assert second.world_model_record is not None
    assert first.world_model_record.content_hash != second.world_model_record.content_hash
    assert first.world_model_record.substrate_registry_ref.content_hash == first_registry.content_hash
    assert second.world_model_record.substrate_registry_ref.content_hash == second_registry.content_hash


def test_joint_port_revalidates_context_before_reusing_wmr() -> None:
    """A stale registry checksum cannot retain an old WMR through the context route."""

    _problem_value, context = _lane0_cycle_context()
    stale_context = context.model_copy(
        update={"substrate_registry_content_hash": "sha256:" + "e" * 64}
    )

    with pytest.raises(ValueError, match="cycle_substrate_registry_hash_mismatch"):
        JointSimulationPort(
            repo_root=REPO_ROOT,
            cycle_substrate_context=stale_context,
        )


def test_shaped_wmr_ref_without_resolved_object_is_rejected() -> None:
    """A WMR-looking string cannot substitute for a resolved owner object."""

    problem = _problem("shaped_wmr_ref").model_copy(
        update={
            "runtime_hints": {
                "world_model_record_ref": "world_model_record_0123456789abcdef"
            }
        }
    )
    candidate = _Candidate(
        candidate_id="candidate_shaped_wmr",
        atom=_Atom("candidate_shaped_wmr", "sha256:" + "c" * 64),
        diversity_key=("grant", "firms", "shaped", "wmr"),
    )

    observation = JointSimulationPort(repo_root=REPO_ROOT)(
        candidate=candidate,
        problem=problem,
        cycle_index=0,
    )

    assert observation.status == "simulation_blocked"
    assert "world_model_record_unresolved" in observation.authority_blockers


@pytest.mark.asyncio
async def test_missing_canonical_registry_never_mints_n6_bootstrap_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N7 remains requested when S0 is unavailable; N6 mints no registry."""

    from polisyos.runtime.quality import generation_cycle

    def _owner_unavailable(_repo_root: Path) -> SubstrateRegistry:
        raise FileNotFoundError("lane0 owner unavailable")

    monkeypatch.setattr(
        generation_cycle,
        "build_substrate_registry_from_existing_catalogs",
        _owner_unavailable,
    )
    run = await GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        promotion_port=_NoPromotionPort(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={}
        ),
        repo_root=REPO_ROOT,
    ).run(
        _problem("missing_canonical_registry"),
        budget_state=_budget(),
        min_cycles=1,
        max_cycles=1,
    )

    cycle = run.cycles[0]
    assert cycle.terminal_kind == "acquisition_required"
    assert cycle.acquisition_receipt is None
    assert "n7_substrate_registry_unresolved" in cycle.counterexample.diagnostic.code
    assert "n7_substrate_registry_unresolved" not in cycle.grounding.issue_codes
    assert "n7_route" not in cycle.revision_request.strategy_payload
    assert "n6.bootstrap" not in json.dumps(run.model_dump(mode="json"))


def test_boundary_wmr_uses_injected_registry_and_problem_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The canonical boundary owner must not rebuild or stamp first-vertical scope."""

    from polisyos.runtime.quality import generation_cycle

    registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.duckdb",
    )
    problem = _domain_problem(
        domain="water_quality",
        region="dnieper_basin",
        valid_time="2021/2024",
        as_of="2026-07-12",
        outcome="nitrate_load",
        stakeholder_id="watershed_communities",
    )

    def _unexpected_registry_rebuild(_repo_root: Path) -> SubstrateRegistry:
        raise AssertionError("injected_registry_was_ignored")

    monkeypatch.setattr(
        generation_cycle,
        "build_substrate_registry_from_existing_catalogs",
        _unexpected_registry_rebuild,
    )
    record = _build_boundary_world_model_record(
        repo_root=REPO_ROOT,
        problem=problem,
        outcome="nitrate_load",
        policy_slot_ids=("nitrate_load",),
        substrate_registry=registry,
        selected_registry_entry_hashes=(registry.entries[0].entry_content_hash,),
    )

    assert record.policy_domain == "water_quality"
    assert record.region_or_jurisdiction == "dnieper_basin"
    assert record.valid_time_scope == "2021/2024"
    assert record.tx_time_scope == "2026-07-12"
    assert "watershed_communities" in record.population_scope
    assert record.substrate_registry_ref.content_hash == registry.content_hash
    assert {
        item.entry_content_hash for item in record.substrate_registry_ref.resolved_entries
    } == {registry.entries[0].entry_content_hash}
    assert not record.fabric_world_ref.snapshot_root.startswith("/")
    assert "UA" not in json.dumps(record.model_dump(mode="json"))


def test_boundary_wmr_rejects_selected_entry_absent_from_registry() -> None:
    """A shaped selected hash cannot become a boundary-world authority receipt."""

    registry = _lane0_registry(
        domain="water_quality",
        source_id="l2_watershed_graph:causal_edges.duckdb",
    )
    problem = _domain_problem(
        domain="water_quality",
        region="dnieper_basin",
        valid_time="2021/2024",
        as_of="2026-07-12",
        outcome="nitrate_load",
        stakeholder_id="watershed_communities",
    )

    with pytest.raises(WorldModelRecordError, match="boundary_registry_entry_unresolved"):
        _build_boundary_world_model_record(
            repo_root=REPO_ROOT,
            problem=problem,
            outcome="nitrate_load",
            policy_slot_ids=("nitrate_load",),
            substrate_registry=registry,
            selected_registry_entry_hashes=("sha256:" + "0" * 64,),
        )


def _budget(max_usd: str = "5.0") -> BudgetState:
    return BudgetState(
        limits={"run": BudgetLimit(key="run", max_usd=Decimal(max_usd))},
    )


def _n7_data_requirement_spec() -> DataRequirementSpec:
    return DataRequirementSpec(
        requirement_id="data-requirement:owner-panel-missing",
        claim_id="claim-owner-panel-missing",
        required_data_families=("owner_panel_missing",),
        scope=DataRequirementScope(
            population="firms",
            geography="UA",
            time="annual",
            time_role="observation_time",
        ),
        recency_horizon="P90D",
        lineage_strictness="strict",
        quality_minima=DataQualityMinimums(min_quality_score=0.8, min_completeness=0.95),
        missingness_tolerance=0.02,
        transformation_tolerance="none",
        admissibility_predicates=("source_family_matches_compiled_requirement",),
        mandatory_facets=("source_contract_ref", "lineage_refs"),
        concept_spine_refs=("concept:firm",),
        authority_profile_refs=("authority_profile.research",),
    )


def _n7_owner_payload(
    *,
    acquired_family: str,
    source_id: str,
    candidate_id: str,
) -> dict[str, object]:
    owner_response: dict[str, object] = {
        "owner_response_kind": "recorded_unit_owner_response",
        "acquired_family": acquired_family,
        "source_id": source_id,
        "candidate_id": candidate_id,
    }
    return {
        "owner_response_kind": "real_owner_capture",
        "owner_response": owner_response,
        "raw_owner_response_hash": _n7_stable_json_hash(owner_response),
        "acquired_substrate_registrations": [
            _n7_registration(
                source_id=source_id,
                family_id=acquired_family,
                snapshot_id=f"snapshot:{acquired_family}:2026-07-05",
            ).model_dump(mode="json")
        ],
        "candidate_bindings": [
            {
                "candidate_id": candidate_id,
                "candidate_content_hash": "sha256:" + "7" * 64,
                "target_world_slots": [acquired_family],
            }
        ],
    }


def _n7_stable_json_hash(value: dict[str, object]) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _n9_receipt(
    candidate_id: str,
    *,
    consumer_promotable: bool,
    promotion_lane: str = "production",
    non_promotable_reason: str | None = None,
) -> dict[str, object]:
    return {
        "candidate_id": candidate_id,
        "promoted": True,
        "promotion_lane": promotion_lane,
        "consumer_promotable": consumer_promotable,
        "non_promotable_reason": non_promotable_reason,
    }


def _n7_substrate_registry() -> SubstrateRegistry:
    entry = build_substrate_registry_entry(
        _n7_registration(
            source_id="baseline.owner_panel_missing",
            family_id="owner_panel_missing",
            snapshot_id="baseline:owner_panel_missing",
        )
    )
    return build_substrate_registry(
        (entry,),
        producer_ref="tests.unit.runtime.quality.test_generation_cycle",
        source_catalog_refs=("test://n6-n7/substrate-registry",),
    )


def _n7_registration(*, source_id: str, family_id: str, snapshot_id: str) -> SubstrateRegistration:
    return SubstrateRegistration(
        source_id=source_id,
        family_id=family_id,
        layer=SubstrateLayer.L1,
        coverage=SubstrateCoverage(
            coverage_score=0.9,
            coverage_kind="recorded_owner_response",
            coverage_rule_ref=f"test://coverage/{family_id}",
            dataset_count=1,
            metric_binding_count=1,
            observation_count=1,
        ),
        trust_tier=SubstrateTrustTier(
            tier="recorded",
            trust_cap=0.8,
            trust_multiplier=0.8,
            authority_ref=f"test://trust/{family_id}",
        ),
        identification_mode="observed_panel",
        schema_regime=SubstrateSchemaRegime(
            schema_regime_id=f"manifest:{family_id}",
            authority_ref=f"test://schema/{family_id}",
        ),
        data_version="2026-07-05",
        snapshot_id=snapshot_id,
        source_snapshot_id=snapshot_id,
        provenance_refs=(f"test://provenance/{source_id}",),
        authority_refs=(f"test://authority/{family_id}",),
    )


def _real_n4_generation_result_with_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    """Select one content-matched real candidate without pinning a receipt-local id."""

    payload = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/layer3_gy_design_generation_contract.json"
        ).read_text(encoding="utf-8")
    )
    for result in payload["generation_results"]:
        dispositions = {
            item.get("candidate_id"): item
            for item in result.get("grounding_dispositions") or ()
            if item.get("candidate_id")
        }
        for candidate in result.get("candidates") or ():
            disposition = dispositions.get(candidate.get("candidate_id"))
            if (
                disposition is not None
                and disposition.get("shadow_atom_content_hash")
                == candidate.get("atom", {}).get("content_hash")
            ):
                return result, candidate
    raise AssertionError("missing content-matched real N4 candidate")


def _real_cg4_proxy_gap_result() -> tuple[dict[str, Any], dict[str, Any]]:
    cg4_payload = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/grounding_phrasing_defense_contract.json"
        ).read_text(encoding="utf-8")
    )
    handoff = next(
        item
        for item in cg4_payload["certificate"]["quarantine_handoffs"]
        if item["action"] == "adversarial_validate"
    )
    result, candidate = _real_n4_generation_result_with_candidate()
    disposition = copy.deepcopy(
        next(
            item
            for item in result["grounding_dispositions"]
            if item.get("candidate_id") == candidate["candidate_id"]
        )
    )
    candidate = copy.deepcopy(candidate)
    disposition["candidate_id"] = candidate["candidate_id"]
    disposition["shadow_atom_content_hash"] = candidate["atom"]["content_hash"]
    disposition["disposition"] = "shadow_bound"
    disposition["certificate_chain"] = {
        **(disposition.get("certificate_chain") or {}),
        "quarantine_handoff": handoff,
    }
    return {"status": "generated", "candidates": [candidate], "grounding_dispositions": [disposition]}, candidate


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
    assert run.cycles[0].revision_request.revision_strategy == "adversarial_validate"
    assert run.cycles[0].revision_request.new_grammar_elements == (
        "lever:grant:adversarial_validate:missing_supporting_data",
    )
    assert run.cycles[1].introduced_grammar_elements == (
        "lever:grant:adversarial_validate:missing_supporting_data",
    )
    assert generator.problems[1].runtime_hints["generation_cycle_revision"][
        "revision_strategy"
    ] == "adversarial_validate"
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
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed",),
            introduced_grammar_elements=(),
            design_problem=_problem(),
        )


def test_no_retry_without_new_grammar_rejects_laundered_revision_claim() -> None:
    with pytest.raises(GenerationCycleError, match="new_grammar_elements_not_introduced"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_cycle_1",
            next_candidate_ref="candidate_cycle_2",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed",),
            introduced_grammar_elements=("fabricated_new_axis",),
            design_problem=_problem(),
        )


def test_no_retry_without_new_grammar_rejects_fabricated_owned_by_caller_only() -> None:
    with pytest.raises(GenerationCycleError, match="new_grammar_element_not_owned"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_a",
            next_candidate_ref="candidate_b",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed", "fabricated:not_from_s2_owner"),
            introduced_grammar_elements=("fabricated:not_from_s2_owner",),
            design_problem=_problem(),
        )

    with pytest.raises(GenerationCycleError, match="new_grammar_owner_missing"):
        enforce_no_retry_without_new_grammar(
            previous_candidate_ref="candidate_a",
            next_candidate_ref="candidate_b",
            previous_grammar_elements=("seed",),
            next_grammar_elements=("seed", "fabricated:not_from_s2_owner"),
            introduced_grammar_elements=("fabricated:not_from_s2_owner",),
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
    assert search_run.cycles[0].revision_request.revision_strategy == "adversarial_validate"
    assert acquisition_run.cycles[0].revision_request.revision_strategy == "acquire_or_elicit"
    assert (
        search_run.cycles[0].revision_request.revision_strategy
        != acquisition_run.cycles[0].revision_request.revision_strategy
    )


@pytest.mark.asyncio
async def test_acquisition_required_invokes_n7_and_records_same_cycle_reentry() -> None:
    data_spec = _n7_data_requirement_spec()
    payload = _n7_owner_payload(
        acquired_family="owner_panel_missing",
        source_id="fabric.owner_panel_missing",
        candidate_id="candidate_cycle_1",
    )
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/owner-panel-missing",
        payload=payload,
        cost_usd=2.0,
        quality={"capture": "real_owner_recording"},
        rights={"license": "recorded-open"},
        binding_refs=("candidate_cycle_1",),
        journal_ref="journal://n7/owner-panel-missing/001",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fabric.ingestion.acquire",
            owner_request={"requirement_ref": data_spec.requirement_id},
            owner_response=payload,
            captured_at=datetime(2026, 7, 5, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )
    problem = _problem().model_copy(
        update={
            "runtime_hints": {
                "n7_data_requirement_specs": (data_spec,),
                "n7_world_snapshot": AcquisitionWorldSnapshot(
                    world_ref="world://before/n6-n7",
                    known_slots=("owner_panel_missing",),
                    dependency_index={"owner_panel_missing": ("candidate_cycle_1",)},
                    design_revalidation_stages={
                        "candidate_cycle_1": (
                            "identification",
                            "calibration",
                            "value_set",
                            "grounding",
                        )
                    },
                    substrate_registry=_n7_substrate_registry().model_dump(mode="json"),
                ),
                "n7_useful_design_rate_before": 0.0,
            }
        }
    )
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
    )

    run = await controller.run(problem, budget_state=_budget(), max_cycles=1)

    assert run.cycles[0].acquisition_receipt is not None
    receipt = run.cycles[0].acquisition_receipt
    assert receipt["source_cycle_index"] == 0
    assert receipt["reentry_cycle_index"] == 0
    assert receipt["real_grounding_result_count"] == 1
    assert receipt["useful_design_rate_after"] > 0.0
    assert run.cycles[0].terminal_kind == "grounded_abstention"
    assert run.cycles[0].grounding.status == "grounded_shadow"
    assert run.candidate_summaries[0].grounding_status == "grounded_shadow"
    assert run.acquisition_receipts == (receipt,)


@pytest.mark.asyncio
async def test_acquisition_required_derives_n7_inputs_without_test_hints_and_reenters() -> None:
    compiled = compile_data_requirements_for_scenario(
        {
            "scenario_id": "generic_cycle_problem",
            "text": "Acquire owner_panel_missing to ground the blocked candidate.",
            "domain": "generic_policy",
            "expected_evidence_contract": {
                "admissible_data_source_families": ["owner_panel_missing"]
            },
        }
    )
    data_spec = compiled.specs[0]
    payload = _n7_owner_payload(
        acquired_family="owner_panel_missing",
        source_id="fabric.owner_panel_missing",
        candidate_id="candidate_cycle_1",
    )
    artifact = AcquisitionOwnerArtifact.from_payload(
        owner_component="fabric.ingestion",
        requirement_ref=data_spec.requirement_id,
        artifact_ref="fabric://recorded/owner-panel-missing",
        payload=payload,
        cost_usd=2.0,
        quality={"capture": "recorded-owner"},
        rights={"license": "recorded-open"},
        binding_refs=("candidate_cycle_1",),
        journal_ref="journal://n7/owner-panel-missing/production-default",
        capture_provenance=AcquisitionCaptureProvenance.from_owner_response(
            owner_component="fabric.ingestion",
            owner_endpoint="fabric.ingestion.acquire",
            owner_request={"requirement_ref": data_spec.requirement_id},
            owner_response=payload,
            captured_at=datetime(2026, 7, 5, tzinfo=UTC),
            capture_mode="local_substrate_owner",
        ),
    )
    problem = _problem()
    assert not any(key.startswith("n7_") for key in problem.runtime_hints)
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        acquisition_owner_gateway=RecordedAcquisitionOwnerGateway(
            artifacts_by_requirement={data_spec.requirement_id: artifact}
        ),
    )

    run = await controller.run(problem, budget_state=_budget(), max_cycles=1)

    cycle = run.cycles[0]
    assert cycle.acquisition_receipt is not None
    assert cycle.acquisition_receipt["real_grounding_result_count"] == 1
    assert cycle.terminal_kind != "acquisition_required"
    assert cycle.terminal_kind == "grounded_abstention"
    assert cycle.grounding.status == "grounded_shadow"
    assert cycle.grounding.report_ref
    assert run.candidate_summaries[0].grounding_status == "grounded_shadow"
    assert run.candidate_summaries[0].front == "research"


@pytest.mark.asyncio
async def test_constant_strategy_revision_is_rejected_as_not_terminal_driven() -> None:
    controller = GenerationCycleController(
        generation_port=_CounterexampleAwareGenerator(),
        grounding_port=_AcquisitionGrounding(),
        value_port=PendingN8ValuePort(),
        revision_policy=_ConstantStrategyRevision(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert any(
        issue["code"] == "revision_not_terminal_driven"
        for issue in validate_generation_cycle_run(run)
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


def test_default_grounding_port_resolves_real_serialized_n4_candidate() -> None:
    result, candidate = _real_n4_generation_result_with_candidate()

    grounding = PolicyGroundingPort()(
        candidate=candidate,
        problem=_problem(),
        cycle_index=0,
        generation_result=result,
    )

    assert grounding.candidate_id == candidate["candidate_id"]
    assert grounding.status != "grounding_unavailable"
    assert "cgf_disposition_missing" not in grounding.issue_codes
    assert grounding.grounding_source == "cgf_firewall"
    assert grounding.grounding_disposition in {
        "shadow_bound",
        "novel_cg3",
        "non_binding_abstain",
        "veto_false_analog",
        "unknown_blocked",
    }


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


def test_real_cg4_proxy_gap_shape_routes_to_quarantine() -> None:
    result, candidate = _real_cg4_proxy_gap_result()

    grounding = PolicyGroundingPort()(
        candidate=candidate,
        problem=_problem(),
        cycle_index=0,
        generation_result=result,
    )

    assert grounding.quarantine_action == "adversarial_validate"
    summary = CandidateSummary(
        candidate_id=grounding.candidate_id,
        content_hash=candidate["atom"]["content_hash"],
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.95,
        voi_estimate=0.6,
        grounding_status=grounding.status,
        grounding_source=grounding.grounding_source,
        grounding_disposition=grounding.grounding_disposition,
        grounding_score=grounding.grounding_score,
        current_valid=grounding.current_valid,
        front="quarantine",
        high_proxy=True,
        low_grounding=True,
        quarantine_action=grounding.quarantine_action,
        adversarial_validation_status="completed_shadow_only",
    )
    fronts = _derive_fronts((summary,))

    assert fronts.decision.candidate_ids == ()
    assert fronts.quarantine.candidate_ids == (summary.candidate_id,)


def test_decision_front_positive_and_proxy_conflict_paths_stay_live() -> None:
    current_valid = CandidateSummary(
        candidate_id="candidate_current_valid",
        content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    conflict = current_valid.model_copy(
        update={
            "candidate_id": "candidate_conflict",
            "content_hash": "sha256:" + "3" * 64,
            "proxy_score": 0.95,
            "grounding_score": 0.2,
            "front": "quarantine",
            "high_proxy": True,
            "low_grounding": True,
            "quarantine_action": "adversarial_validate",
            "adversarial_validation_status": "required_before_decision",
        }
    )
    promoted = _apply_promotion_to_summaries(
        (current_valid, conflict),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_current_valid", "candidate_conflict"),
            receipts=(
                _n9_receipt("candidate_current_valid", consumer_promotable=True),
                _n9_receipt("candidate_conflict", consumer_promotable=True),
            ),
        ),
    )
    fronts = _derive_fronts(tuple(promoted))

    assert fronts.decision.candidate_ids == ("candidate_current_valid",)
    assert fronts.quarantine.candidate_ids == ("candidate_conflict",)


def test_blocked_value_candidate_cannot_be_promoted_to_decision_front() -> None:
    current_valid = CandidateSummary(
        candidate_id="candidate_value_blocked",
        content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        value_status="value_blocked",
        value_decision_grade="blocked",
        value_blockers=("uncalibrated_forecast_minted_value",),
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    promoted = _apply_promotion_to_summaries(
        (current_valid,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_value_blocked",),
            receipts=(_n9_receipt("candidate_value_blocked", consumer_promotable=True),),
        ),
    )
    fronts = _derive_fronts(tuple(promoted))

    assert fronts.decision.candidate_ids == ()
    assert fronts.research.candidate_ids == ("candidate_value_blocked",)


def test_contract_lane_n9_receipt_cannot_enter_decision_front() -> None:
    current_valid = CandidateSummary(
        candidate_id="candidate_contract_lane",
        content_hash="sha256:" + "2" * 64,
        cycle_index=0,
        generation_channel="n4_owner",
        proxy_score=0.2,
        voi_estimate=0.1,
        grounding_status="current_valid",
        grounding_source="cgf_firewall",
        grounding_disposition="shadow_bound",
        grounding_score=0.9,
        current_valid=True,
        front="research",
        high_proxy=False,
        low_grounding=False,
    )
    promoted = _apply_promotion_to_summaries(
        (current_valid,),
        PromotionPortObservation(
            status="certified_current_valid",
            certified_candidate_ids=("candidate_contract_lane",),
            receipts=(
                _n9_receipt(
                    "candidate_contract_lane",
                    consumer_promotable=False,
                    promotion_lane="contract_testing",
                    non_promotable_reason="non_production_anchor_scope",
                ),
            ),
        ),
    )
    fronts = _derive_fronts(tuple(promoted))

    assert fronts.decision.candidate_ids == ()
    assert fronts.research.candidate_ids == ("candidate_contract_lane",)


class _BlockedValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            authority_blockers=("uncalibrated_forecast_minted_value",),
            reason="S10 calibration refused authority.",
            decision_grade="blocked",
        )


class _DataGapValuePort:
    def __call__(self, **kwargs: Any) -> ValuePortObservation:
        del kwargs
        return ValuePortObservation(
            status="value_blocked",
            authority_blockers=("acquire_data:value_panel_data_missing",),
            reason="Owner-bound panel observations are missing.",
            decision_grade="blocked",
        )


@pytest.mark.asyncio
async def test_value_block_feeds_revision_before_promotion() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_BlockedValuePort(),
        promotion_port=_FabricatedPromotionPort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.value_port.status == "value_blocked"
    assert run.cycles[0].counterexample.counterexample_class == "value_gap"
    assert run.cycles[0].counterexample.diagnostic.code.endswith(
        "uncalibrated_forecast_minted_value"
    )
    assert run.fronts.decision.candidate_ids == ()


@pytest.mark.asyncio
async def test_value_data_gap_routes_to_n7_acquisition_terminal() -> None:
    controller = GenerationCycleController(
        generation_port=_CgfGenerationPort(),
        value_port=_DataGapValuePort(),
    )

    run = await controller.run(_problem(), budget_state=_budget(), max_cycles=1)

    assert run.value_port.status == "value_blocked"
    assert run.cycles[0].terminal_kind == "acquisition_required"
    assert run.cycles[0].revision_request.revision_strategy == "acquire_or_elicit"
    assert run.cycles[0].refinement_decision.decision == "acquire"
    assert run.cycles[0].search_iteration.status == "acquisition_required"
    assert (
        run.cycles[0].revision_request.strategy_payload["acquisition_request"]["driver"]
        == "acquire_data:value_panel_data_missing"
    )
    assert run.fronts.decision.candidate_ids == ()


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


def test_generation_cycle_contract_write_payload_is_byte_stable() -> None:
    first = contract.build_contract_json_for_write(REPO_ROOT)
    second = contract.build_contract_json_for_write(REPO_ROOT)

    assert first == second
    assert "capture_wall_time_seconds" not in first


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
