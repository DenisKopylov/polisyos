"""Layer 2 S2 shadow design-search contracts and deterministic producer."""

from __future__ import annotations

import hashlib
import json
import re
from typing import TYPE_CHECKING, Literal

from pydantic import AwareDatetime, Field, model_validator

from polisyos.core import artifacts, canon

from .layer2_readiness import (
    AuthorityBoundary,
    AxisFirewallStatus,
    AxisPositionDeclaration,
    CertifiedOperationEnvelope,
    DesignRecordV0,
    EpistemicRegime,
    GovernanceDecisionClass,
    Layer2ReadinessModel,
    ValueOfInformationEstimate,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

S2_DESIGN_SEARCH_SCHEMA_VERSION = "policyos.policy_design_case.layer2_s2_design_search.v1"
S2_DESIGN_RECORD_RULE_VERSION = "policyos.layer2.s2.design_search.v1"

CounterexampleClass = Literal[
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap",
]
FieldSourceClass = Literal[
    "deterministic_grammar",
    "llm_candidate",
    "human_reviewer",
    "corpus_exemplar",
    "producer_derived_constraint",
]
S2RunStatus = Literal[
    "shadow_ready",
    "blocked",
    "governance_required",
    "acquisition_required",
    "abstained",
]
RefinementDecisionKind = Literal[
    "refine",
    "acquire",
    "reframe",
    "decompose",
    "human_decision",
    "abstain",
    "block_candidate",
]

_COUNTEREXAMPLE_CLASS_VOCABULARY: list[str] = [
    "real_design_blocker",
    "substrate_gap",
    "a_spec_gap",
    "abstraction_gap",
    "value_gap",
    "budget_gap",
]
_INSTRUMENT_FAMILIES = [
    "credit_guarantee",
    "interest_rate_buydown",
    "cash_grant",
]
_AUTHORITY_PURPOSE = "shadow_design_search_replay"
_SEARCH_INCOMPLETENESS_NOTE = (
    "best_known_shadow_frontier is a replayable S2 trace only; it is not exhaustive, "
    "admissibility authority, or a production recommendation."
)
_MAY_NOT_USE_FOR = [
    "production_recommendation",
    "publication_authority",
    "rollout_authority",
    "claim_authority",
    "production_closeout_authority",
    "acquisition_authority",
    "source_contract_authority",
]
_NON_POINT_OPTIMIZATION_STRATEGIES = frozenset(
    {
        "robust_satisficing",
        "frame_indexed_portfolio",
        "precautionary_adaptive_pathway",
    }
)


class Layer2S2DesignSearchInputError(ValueError):
    """Raised when S2 shadow design-search input violates firewalls."""


class Layer2S2DesignSearchInput(Layer2ReadinessModel):
    """Input for the deterministic one-case S2 shadow design-search loop."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    case_id: str = Field(..., min_length=1)
    intent_ref: str = Field(..., min_length=1)
    grammar_ref: str = Field(..., min_length=1)
    actor_ref: str = Field(..., min_length=1)
    domain: str = Field(..., min_length=1)
    objective_refs: tuple[str, ...] = Field(..., min_length=1)
    construct_refs: tuple[str, ...] = Field(..., min_length=1)
    authority_profile_ref: str = Field(..., min_length=1)
    requested_posture: Literal["shadow"] = "shadow"
    generated_at: AwareDatetime
    rule_version_ref: str = S2_DESIGN_RECORD_RULE_VERSION
    forced_counterexample_class: CounterexampleClass | None = None
    force_retry_same_candidate: bool = False
    candidate_source_authority: Literal["deterministic_producer", "llm_candidate"] = (
        "deterministic_producer"
    )
    omit_grammar_derivation: bool = False


class TypedDiagnosticRecord(Layer2ReadinessModel):
    """Design-time diagnostic carried by S2 counterexamples."""

    diagnostic_id: str
    code: str
    severity: Literal["warn", "block", "governance_required"]
    message: str
    authority_purpose: str
    owner: str
    rule_version_ref: str


class DesignGrammarExpansion(Layer2ReadinessModel):
    """Grammar-derived design-space expansion used before candidate emission."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    expansion_id: str
    expansion_ref: str
    case_id: str
    intent_ref: str
    source_grammar_ref: str
    instrument_families: list[str] = Field(..., min_length=2)
    parameter_space: dict[str, list[str]]
    constraints: list[str]
    construct_demand_refs: list[str]
    authority_boundary: AuthorityBoundary
    generated_at: AwareDatetime


class DesignCandidateV0(Layer2ReadinessModel):
    """S2 minimal typed design candidate produced from grammar expansion."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    candidate_id: str
    candidate_ref: str
    case_id: str
    grammar_expansion_ref: str
    instrument_family: str
    parameterization: dict[str, str]
    objective_refs: list[str]
    construct_refs: list[str]
    source_authority: Literal["deterministic_producer", "llm_candidate"]
    field_source_classification: dict[str, FieldSourceClass]
    authority_boundary: AuthorityBoundary
    status: Literal["candidate_unverified", "a_verified_shadow", "blocked"]
    regime: EpistemicRegime | None = None
    design_strategy: str | None = None
    commitment_profile_ref: str | None = None
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None

    @model_validator(mode="after")
    def _validate_grammar_first(self) -> DesignCandidateV0:
        if not self.grammar_expansion_ref:
            raise ValueError("DesignCandidateV0 requires grammar_expansion_ref")
        if self.source_authority == "llm_candidate" and self.status != "candidate_unverified":
            raise ValueError("llm_candidate cannot become A-verified authority")
        return self


class ConstraintStoreSnapshot(Layer2ReadinessModel):
    """Snapshot of S2 constraints consumed by A-side verification."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    snapshot_id: str
    snapshot_ref: str
    grammar_expansion_ref: str
    constraint_ids: list[str]
    hard_constraint_ids: list[str]
    governance_owned_gap_ids: list[str]


class CounterexampleRecord(Layer2ReadinessModel):
    """Typed counterexample emitted by S2 A-verification."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    counterexample_id: str
    counterexample_ref: str
    case_id: str
    candidate_ref: str
    counterexample_class: CounterexampleClass
    diagnostic: TypedDiagnosticRecord
    evidence_refs: list[str]
    routed_to: Literal[
        "refinement_policy",
        "acquisition",
        "governance",
        "abstention",
        "blocked",
    ]


class RefinementDecision(Layer2ReadinessModel):
    """Decision produced by consuming typed S2 counterexamples."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    decision_id: str
    decision_ref: str
    case_id: str
    candidate_ref: str
    consumed_counterexample_refs: list[str]
    decision: RefinementDecisionKind
    next_candidate_ref: str | None = None
    value_of_information: ValueOfInformationEstimate
    budget_refs: list[str] = Field(..., min_length=1)
    stakes_band: Literal["low", "moderate", "high", "high_stakes"]
    governance_decision_class_ref: str | None = None
    governance_decision_class: GovernanceDecisionClass | None = None
    governance_refs: list[str] = Field(default_factory=list)
    reason: str

    @model_validator(mode="after")
    def _validate_governance_handoff(self) -> RefinementDecision:
        if self.decision == "human_decision" and not self.governance_decision_class_ref:
            raise ValueError("human_decision requires governance_decision_class_ref")
        if self.governance_decision_class and (
            self.governance_decision_class.decision_class_id
            != self.governance_decision_class_ref
        ):
            raise ValueError("governance decision class ref mismatch")
        return self


class SearchIteration(Layer2ReadinessModel):
    """Single replay-visible S2 search iteration."""

    iteration_id: str
    candidate_ref: str
    counterexample_refs: list[str]
    refinement_decision_ref: str
    status: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ]


class SearchLedger(Layer2ReadinessModel):
    """Replayable S2 search ledger."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    ledger_id: str
    ledger_ref: str
    case_id: str
    iterations: list[SearchIteration]
    candidate_refs: list[str]
    counterexample_refs: list[str]
    refinement_decision_refs: list[str]
    deterministic_replay_key: str
    counterexample_conversion_rate: float
    grammar_diversity_minimum: int
    instrument_family_coverage: list[str]
    counterexample_class_vocabulary: list[str]
    acquisition_branch_state: Literal["bridge_missing"] = "bridge_missing"
    no_retry_without_new_grammar: bool
    search_incompleteness_note: str


class ClusterInterfaceContract(Layer2ReadinessModel):
    """Typed cluster blackboard interface used by S2 handoffs."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    contract_id: str
    cell_ref: str
    publishes: list[str]
    consumes: list[str]
    authority_boundary: AuthorityBoundary


class ClusterHandoffRecord(Layer2ReadinessModel):
    """Typed handoff record proving Scientist/design workflow did not launder authority."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    handoff_id: str
    workflow_ref: str
    source_cell_ref: str
    target_cell_ref: str
    artifact_refs: list[str]
    disposition: Literal["emitted", "consumed", "rejected", "blocked"]
    authority_purpose: str
    may_not_use_for: list[str]


class Layer2S2DesignSearchRun(Layer2ReadinessModel):
    """Complete S2 shadow design-search run."""

    schema_version: str = S2_DESIGN_SEARCH_SCHEMA_VERSION
    run_id: str
    status: S2RunStatus
    grammar_expansion: DesignGrammarExpansion
    constraint_store: ConstraintStoreSnapshot
    candidates: list[DesignCandidateV0]
    counterexamples: list[CounterexampleRecord]
    refinement_decisions: list[RefinementDecision]
    search_ledger: SearchLedger
    cluster_interface_contracts: list[ClusterInterfaceContract]
    handoff_records: list[ClusterHandoffRecord]
    design_record: DesignRecordV0


def run_s2_shadow_design_loop(
    input: Layer2S2DesignSearchInput,
    *,
    regime: EpistemicRegime | None = None,
    design_strategy: str | None = None,
    regime_claim_ref: str | None = None,
    commitment_profile_ref: str | None = None,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None,
) -> Layer2S2DesignSearchRun:
    """Run the deterministic S2 one-case shadow design-search loop."""

    if input.candidate_source_authority == "llm_candidate" and input.omit_grammar_derivation:
        raise Layer2S2DesignSearchInputError(
            "llm_candidate requires grammar_expansion_ref and remains shadow-only"
        )
    boundary = _shadow_boundary(input)
    run_id = f"layer2.s2.{_slug(input.case_id)}"
    expansion = _grammar_expansion(input, boundary=boundary)
    candidate = _candidate(
        input,
        expansion=expansion,
        boundary=boundary,
        regime=regime,
        design_strategy=design_strategy,
        commitment_profile_ref=commitment_profile_ref,
        commitment_stakes=commitment_stakes,
    )
    constraint_store = _constraint_store(input, expansion=expansion)
    counterexample = _counterexample(input, candidate=candidate)
    decision = _refinement_decision(
        input,
        candidate=candidate,
        counterexample=counterexample,
    )
    iteration_status = _iteration_status(input, decision)
    ledger = _search_ledger(
        input,
        candidate=candidate,
        counterexample=counterexample,
        decision=decision,
        iteration_status=iteration_status,
    )
    design_record = _design_record(
        input,
        candidate=candidate,
        ledger=ledger,
        boundary=boundary,
        regime=regime,
        regime_claim_ref=regime_claim_ref,
        commitment_profile_ref=commitment_profile_ref,
        design_strategy=design_strategy,
        commitment_stakes=commitment_stakes,
    )
    status: S2RunStatus = (
        "governance_required"
        if decision.decision == "human_decision"
        else "acquisition_required"
        if decision.decision == "acquire"
        else "abstained"
        if decision.decision == "abstain"
        else "blocked"
        if decision.decision == "block_candidate"
        else "shadow_ready"
    )
    return Layer2S2DesignSearchRun(
        run_id=run_id,
        status=status,
        grammar_expansion=expansion,
        constraint_store=constraint_store,
        candidates=[candidate],
        counterexamples=[counterexample],
        refinement_decisions=[decision],
        search_ledger=ledger,
        cluster_interface_contracts=_cluster_interfaces(boundary),
        handoff_records=_handoff_records(candidate, expansion, ledger),
        design_record=design_record,
    )


def project_s2_design_search(
    run: Layer2S2DesignSearchRun,
    *,
    audiences: tuple[Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"], ...],
) -> dict[str, dict[str, object]]:
    """Project S2 search trace without minting recommendation authority."""

    projections: dict[str, dict[str, object]] = {}
    boundary = run.design_record.authority_boundary.model_dump(mode="json")
    regime_axis = _axis_position(run.design_record, "KNOWLEDGE.epistemic_regime")
    commitment_axis = _axis_position(
        run.design_record,
        "INTERVENTION.reversibility_lifecycle_stakes",
    )
    p16_firewall = _firewall_status(run.design_record, "KNOWLEDGE.epistemic_regime")
    p23_firewall = _firewall_status(
        run.design_record,
        "INTERVENTION.reversibility_lifecycle_stakes",
    )
    for audience in audiences:
        projection: dict[str, object] = {
            "schema_version": S2_DESIGN_SEARCH_SCHEMA_VERSION,
            "audience": audience,
            "status": run.status,
            "design_record_id": run.design_record.record_id,
            "search_ledger_ref": run.search_ledger.ledger_ref,
            "candidate_refs": list(run.search_ledger.candidate_refs),
            "counterexample_refs": list(run.search_ledger.counterexample_refs),
            "refinement_decision_refs": list(run.search_ledger.refinement_decision_refs),
            "counterexample_conversion_rate": run.search_ledger.counterexample_conversion_rate,
            "grammar_diversity_minimum": run.search_ledger.grammar_diversity_minimum,
            "instrument_family_coverage": list(run.search_ledger.instrument_family_coverage),
            "acquisition_branch_state": run.search_ledger.acquisition_branch_state,
            "search_incompleteness_note": run.search_ledger.search_incompleteness_note,
            "authority_boundary": boundary,
        }
        if regime_axis is not None:
            projection.update(
                _regime_projection_fields(
                    audience,
                    regime_axis=regime_axis,
                    commitment_axis=commitment_axis,
                    p16_firewall=p16_firewall,
                    p23_firewall=p23_firewall,
                    candidate=run.candidates[0],
                )
            )
            if audience == "PUBLIC":
                assert_s2_public_projection_has_regime_limitation(projection)
        projections[audience] = projection
    return projections


def assert_s2_public_projection_has_regime_limitation(
    projection: Mapping[str, object],
) -> None:
    """Require the load-bearing PUBLIC limitation for projected S4 regime data."""

    if projection.get("audience") == "PUBLIC" and projection.get("regime"):
        limitation = projection.get("limitation")
        if not isinstance(limitation, str) or not limitation.strip():
            raise ValueError("PUBLIC regime projection requires limitation")


def persist_s2_design_search_run(
    run: Layer2S2DesignSearchRun,
    *,
    store: artifacts.FileSystemCAS,
) -> dict[str, artifacts.ArtifactRef]:
    """Persist S2 DesignRecordV0 and SearchLedger as canonical CAS artifacts."""

    producer = artifacts.ProducerInfo(
        component="polisyos.pdc.layer2_design_search",
        version=S2_DESIGN_RECORD_RULE_VERSION,
    )
    design_record_ref = store.put_json(
        run.design_record.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="policyos.layer2_s2.design_record_v0",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s2.design_record_v0",
                version=run.design_record.schema_version,
            ),
            producer=producer,
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    search_ledger_ref = store.put_json(
        run.search_ledger.model_dump(mode="json"),
        artifacts.PutOptions(
            kind="policyos.layer2_s2.search_ledger",
            media_type="application/json",
            schema=artifacts.SchemaInfo(
                name="policyos.layer2_s2.search_ledger",
                version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
            ),
            producer=producer,
        ),
        canon_spec=canon.CanonSpec(forbid_floats=False),
    )
    return {
        "design_record": design_record_ref,
        "search_ledger": search_ledger_ref,
    }


def load_s2_search_ledger(
    *,
    store: artifacts.FileSystemCAS,
    artifact_ref: artifacts.ArtifactRef,
) -> SearchLedger:
    """Load a persisted S2 SearchLedger from CAS."""

    payload = canon.from_canonical_bytes(store.get_bytes(artifact_ref.artifact_id))
    return SearchLedger.model_validate(payload)


def _shadow_boundary(input: Layer2S2DesignSearchInput) -> AuthorityBoundary:
    return AuthorityBoundary(
        authoritative_for=[
            "shadow_design_search_replay",
            "machine_replay_trace",
            "reviewer_search_trace",
        ],
        may_not_use_for=list(_MAY_NOT_USE_FOR),
        source_authority=input.candidate_source_authority,
        posture="shadow",
        rule_version_refs=[input.rule_version_ref],
    )


def _grammar_expansion(
    input: Layer2S2DesignSearchInput,
    *,
    boundary: AuthorityBoundary,
) -> DesignGrammarExpansion:
    slug = _slug(input.case_id)
    return DesignGrammarExpansion(
        expansion_id=f"layer2.s2.grammar.{slug}",
        expansion_ref=f"pdc://layer2/s2/{slug}/grammar-expansion",
        case_id=input.case_id,
        intent_ref=input.intent_ref,
        source_grammar_ref=input.grammar_ref,
        instrument_families=list(_INSTRUMENT_FAMILIES),
        parameter_space={
            "coverage": ["partial_portfolio", "targeted_sector"],
            "risk_share": ["first_loss", "pari_passu"],
            "delivery_channel": ["bank_intermediated", "public_fund"],
        },
        constraints=[
            "shadow_only",
            "a_side_verification_required",
            "no_acquisition_authority",
        ],
        construct_demand_refs=list(input.construct_refs),
        authority_boundary=boundary,
        generated_at=input.generated_at,
    )


def _candidate(
    input: Layer2S2DesignSearchInput,
    *,
    expansion: DesignGrammarExpansion,
    boundary: AuthorityBoundary,
    regime: EpistemicRegime | None = None,
    design_strategy: str | None = None,
    commitment_profile_ref: str | None = None,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None,
) -> DesignCandidateV0:
    slug = _slug(input.case_id)
    return DesignCandidateV0(
        candidate_id=f"layer2.s2.candidate.{slug}.credit_guarantee",
        candidate_ref=f"pdc://layer2/s2/{slug}/candidate/credit-guarantee",
        case_id=input.case_id,
        grammar_expansion_ref=expansion.expansion_ref,
        instrument_family="credit_guarantee",
        parameterization={
            "coverage": "partial_portfolio",
            "risk_share": "first_loss",
            "delivery_channel": "bank_intermediated",
        },
        objective_refs=list(input.objective_refs),
        construct_refs=list(input.construct_refs),
        source_authority=input.candidate_source_authority,
        field_source_classification={
            "instrument_family": "deterministic_grammar",
            "parameterization": "deterministic_grammar",
            "objective_refs": "producer_derived_constraint",
            "construct_refs": "producer_derived_constraint",
        },
        authority_boundary=boundary,
        status="candidate_unverified",
        regime=regime,
        design_strategy=design_strategy,
        commitment_profile_ref=commitment_profile_ref,
        commitment_stakes=commitment_stakes,
    )


def _constraint_store(
    input: Layer2S2DesignSearchInput,
    *,
    expansion: DesignGrammarExpansion,
) -> ConstraintStoreSnapshot:
    slug = _slug(input.case_id)
    return ConstraintStoreSnapshot(
        snapshot_id=f"layer2.s2.constraints.{slug}",
        snapshot_ref=f"pdc://layer2/s2/{slug}/constraint-store",
        grammar_expansion_ref=expansion.expansion_ref,
        constraint_ids=[
            "shadow_only",
            "authority_boundary_required",
            "a_side_counterexample_required",
        ],
        hard_constraint_ids=["shadow_only", "authority_boundary_required"],
        governance_owned_gap_ids=["a_spec_gap"],
    )


def _counterexample(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
) -> CounterexampleRecord:
    counterexample_class = input.forced_counterexample_class or "real_design_blocker"
    if input.force_retry_same_candidate:
        routed_to = "blocked"
    elif counterexample_class == "a_spec_gap":
        routed_to = "governance"
    elif counterexample_class == "substrate_gap":
        routed_to = "acquisition"
    elif counterexample_class == "budget_gap":
        routed_to = "abstention"
    else:
        routed_to = "refinement_policy"

    return CounterexampleRecord(
        counterexample_id=f"layer2.s2.counterexample.{_slug(input.case_id)}.001",
        counterexample_ref=f"pdc://layer2/s2/{_slug(input.case_id)}/counterexample/001",
        case_id=input.case_id,
        candidate_ref=candidate.candidate_ref,
        counterexample_class=counterexample_class,
        diagnostic=TypedDiagnosticRecord(
            diagnostic_id=f"layer2.s2.diagnostic.{_slug(input.case_id)}.001",
            code=f"s2.{counterexample_class}",
            severity="governance_required" if counterexample_class == "a_spec_gap" else "block",
            message=_counterexample_message(counterexample_class),
            authority_purpose=_AUTHORITY_PURPOSE,
            owner="team-policyos-runtime",
            rule_version_ref=input.rule_version_ref,
        ),
        evidence_refs=[
            "repo://architecture/policy_design_case/layer2_first_proving_case.json",
        ],
        routed_to=routed_to,
    )


def _refinement_decision(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    counterexample: CounterexampleRecord,
) -> RefinementDecision:
    if input.force_retry_same_candidate:
        decision: RefinementDecisionKind = "block_candidate"
    elif counterexample.counterexample_class == "a_spec_gap":
        decision = "human_decision"
    elif counterexample.counterexample_class == "substrate_gap":
        decision = "acquire"
    elif counterexample.counterexample_class == "budget_gap":
        decision = "abstain"
    else:
        decision = "refine"
    if (
        decision == "refine"
        and candidate.design_strategy in _NON_POINT_OPTIMIZATION_STRATEGIES
        and counterexample.counterexample_class != "real_design_blocker"
    ):
        decision = "reframe"

    governance_class = _governance_decision_class(input) if decision == "human_decision" else None
    governance_ref = (
        counterexample.counterexample_class if decision == "human_decision" else None
    )
    return RefinementDecision(
        decision_id=f"layer2.s2.refinement.{_slug(input.case_id)}.001",
        decision_ref=f"pdc://layer2/s2/{_slug(input.case_id)}/refinement/001",
        case_id=input.case_id,
        candidate_ref=candidate.candidate_ref,
        consumed_counterexample_refs=[counterexample.counterexample_ref],
        decision=decision,
        next_candidate_ref=(
            f"pdc://layer2/s2/{_slug(input.case_id)}/candidate/refined-001"
            if decision == "refine"
            else None
        ),
        value_of_information=ValueOfInformationEstimate(
            estimate_id="s2_shadow_refinement_voi",
            purpose="Schedule shadow refinement only; does not relax authority floors.",
            budget_dimensions=["human_attention", "acquisition", "compute"],
            used_by_sites=["layer2.s2.shadow_design_loop"],
            owner="team-policyos-runtime",
            rule_version_ref=input.rule_version_ref,
        ),
        budget_refs=["budget://layer2/s2/shadow-loop"],
        stakes_band=_stakes_band_for_commitment(candidate.commitment_stakes),
        governance_decision_class_ref=governance_ref,
        governance_decision_class=governance_class,
        governance_refs=(
            ["governance://layer2/s2/a_spec_gap"] if decision == "human_decision" else []
        ),
        reason=_decision_reason(
            decision,
            counterexample.counterexample_class,
            design_strategy=candidate.design_strategy,
        ),
    )


def _iteration_status(
    input: Layer2S2DesignSearchInput,
    decision: RefinementDecision,
) -> Literal[
    "blocked",
    "blocked_no_retry",
    "governance_required",
    "acquisition_required",
    "abstained",
    "refined_shadow",
]:
    if input.force_retry_same_candidate or decision.decision == "block_candidate":
        return "blocked_no_retry"
    if decision.decision == "human_decision":
        return "governance_required"
    if decision.decision == "acquire":
        return "acquisition_required"
    if decision.decision == "abstain":
        return "abstained"
    return "refined_shadow"


def _search_ledger(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    counterexample: CounterexampleRecord,
    decision: RefinementDecision,
    iteration_status: Literal[
        "blocked",
        "blocked_no_retry",
        "governance_required",
        "acquisition_required",
        "abstained",
        "refined_shadow",
    ],
) -> SearchLedger:
    slug = _slug(input.case_id)
    replay_key = _deterministic_replay_key(
        input,
        candidate=candidate,
        counterexample=counterexample,
        decision=decision,
    )
    return SearchLedger(
        ledger_id=f"layer2.s2.ledger.{slug}",
        ledger_ref=f"pdc://layer2/s2/{slug}/search-ledger",
        case_id=input.case_id,
        iterations=[
            SearchIteration(
                iteration_id=f"layer2.s2.iteration.{slug}.001",
                candidate_ref=candidate.candidate_ref,
                counterexample_refs=[counterexample.counterexample_ref],
                refinement_decision_ref=decision.decision_ref,
                status=iteration_status,
            )
        ],
        candidate_refs=[candidate.candidate_ref],
        counterexample_refs=[counterexample.counterexample_ref],
        refinement_decision_refs=[decision.decision_ref],
        deterministic_replay_key=replay_key,
        counterexample_conversion_rate=1.0,
        grammar_diversity_minimum=3,
        instrument_family_coverage=list(_INSTRUMENT_FAMILIES),
        counterexample_class_vocabulary=list(_COUNTEREXAMPLE_CLASS_VOCABULARY),
        acquisition_branch_state="bridge_missing",
        no_retry_without_new_grammar=input.force_retry_same_candidate,
        search_incompleteness_note=_SEARCH_INCOMPLETENESS_NOTE,
    )


def _design_record(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    ledger: SearchLedger,
    boundary: AuthorityBoundary,
    regime: EpistemicRegime | None = None,
    regime_claim_ref: str | None = None,
    commitment_profile_ref: str | None = None,
    design_strategy: str | None = None,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None = None,
) -> DesignRecordV0:
    slug = _slug(input.case_id)
    axis_positions = [
        AxisPositionDeclaration(
            cluster="INTERVENTION",
            axis="design_grammar",
            position="grammar_expanded_shadow_only",
            evidence_refs=[candidate.grammar_expansion_ref],
            authority_purpose=_AUTHORITY_PURPOSE,
            rule_version_ref=input.rule_version_ref,
        ),
        AxisPositionDeclaration(
            cluster="INTERVENTION",
            axis="design_candidate",
            position="candidate_emitted_from_grammar_shadow_only",
            evidence_refs=[candidate.candidate_ref],
            authority_purpose=_AUTHORITY_PURPOSE,
            rule_version_ref=input.rule_version_ref,
        ),
    ]
    firewall_status = [
        AxisFirewallStatus(
            cell_ref="INTERVENTION.design_grammar",
            status="pass",
            pattern_ids=["P10", "P15"],
            reason="Grammar expansion precedes candidate emission in the S2 shadow loop.",
            maturity="predictive",
            rule_version_ref=input.rule_version_ref,
        ),
        AxisFirewallStatus(
            cell_ref="INTERVENTION.design_candidate",
            status="warn",
            pattern_ids=["P05", "P25"],
            reason="Candidate is replay-visible but remains shadow-only and non-exhaustive.",
            maturity="fail_closed",
            rule_version_ref=input.rule_version_ref,
        ),
    ]
    ledger_refs = [ledger.ledger_ref]
    projection_audiences: list[Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]] = [
        "MACHINE",
        "REVIEWER",
    ]
    if regime is not None:
        axis_positions.append(
            AxisPositionDeclaration(
                cluster="KNOWLEDGE",
                axis="epistemic_regime",
                position=regime,
                evidence_refs=[regime_claim_ref] if regime_claim_ref else [],
                authority_purpose="design_strategy_selection",
                rule_version_ref=input.rule_version_ref,
            )
        )
        axis_positions.append(
            AxisPositionDeclaration(
                cluster="INTERVENTION",
                axis="reversibility_lifecycle_stakes",
                position=_commitment_axis_position(
                    commitment_stakes=commitment_stakes,
                    design_strategy=design_strategy,
                ),
                evidence_refs=[commitment_profile_ref] if commitment_profile_ref else [],
                authority_purpose="commitment_gated_floor_selection",
                rule_version_ref=input.rule_version_ref,
            )
        )
        firewall_status.append(
            AxisFirewallStatus(
                cell_ref="KNOWLEDGE.epistemic_regime",
                status="pass" if regime == "risk" else "limit",
                pattern_ids=["P16"],
                reason=f"A-side injected {regime} regime selects {design_strategy or 'strategy'}.",
                maturity="fail_closed",
                rule_version_ref=input.rule_version_ref,
            )
        )
        firewall_status.append(
            AxisFirewallStatus(
                cell_ref="INTERVENTION.reversibility_lifecycle_stakes",
                status="pass" if commitment_stakes == "low" else "limit",
                pattern_ids=["P23"],
                reason=(
                    f"Commitment stakes {commitment_stakes or 'unknown'} select "
                    f"{_selected_floor_for_commitment(commitment_stakes)} floor."
                ),
                maturity="fail_closed",
                rule_version_ref=input.rule_version_ref,
            )
        )
        ledger_refs.extend(
            ref for ref in (regime_claim_ref, commitment_profile_ref) if ref is not None
        )
        projection_audiences = ["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"]

    return DesignRecordV0(
        record_id=f"layer2.s2.design_record.{slug}",
        candidate_ref=candidate.candidate_ref,
        candidate_source=candidate.source_authority,
        projection_status="shadow",
        authority_boundary=boundary,
        axis_positions=axis_positions,
        firewall_status=firewall_status,
        envelope=CertifiedOperationEnvelope(
            envelope_id=f"layer2.s2.envelope.{slug}",
            domains=[input.domain],
            posture_scopes=["shadow"],
            epistemic_regime_scopes=[regime] if regime else ["ignorance"],
            actor_scopes=[input.actor_ref],
            method_scopes=["deterministic_shadow_design_search"],
            certified_for=[
                "shadow_design_search_replay",
                "machine_replay_trace",
                "reviewer_search_trace",
            ],
            not_certified_for=list(_MAY_NOT_USE_FOR),
            rule_version_ref=input.rule_version_ref,
        ),
        ledger_refs=ledger_refs,
        projection_audiences=projection_audiences,
    )


def _axis_position(
    record: DesignRecordV0,
    cell_ref: str,
) -> AxisPositionDeclaration | None:
    for position in record.axis_positions:
        if position.cell_ref == cell_ref:
            return position
    return None


def _firewall_status(
    record: DesignRecordV0,
    cell_ref: str,
) -> AxisFirewallStatus | None:
    for status in record.firewall_status:
        if status.cell_ref == cell_ref:
            return status
    return None


def _regime_projection_fields(
    audience: Literal["PUBLIC", "REVIEWER", "EXPERT", "MACHINE"],
    *,
    regime_axis: AxisPositionDeclaration,
    commitment_axis: AxisPositionDeclaration | None,
    p16_firewall: AxisFirewallStatus | None,
    p23_firewall: AxisFirewallStatus | None,
    candidate: DesignCandidateV0,
) -> dict[str, object]:
    commitment = _parse_commitment_axis_position(
        commitment_axis.position if commitment_axis else ""
    )
    design_strategy = (
        commitment.get("design_strategy") or candidate.design_strategy or "strategy_not_injected"
    )
    fields: dict[str, object] = {
        "regime": regime_axis.position,
        "design_strategy": design_strategy,
        "limitation": (
            f"{regime_axis.position} is an A-side regime classification for shadow design "
            "strategy only; it does not grant risk-regime authority, production authority, "
            "publication authority, or rollout authority."
        ),
        "commitment_posture": commitment_axis.position if commitment_axis else "not_projected",
        "adaptive_posture": _adaptive_posture(design_strategy),
    }
    if audience in {"REVIEWER", "EXPERT", "MACHINE"}:
        fields.update(
            {
                "p16_firewall_status": p16_firewall.status if p16_firewall else "limit",
                "p23_firewall_status": p23_firewall.status if p23_firewall else "limit",
            }
        )
    if audience in {"EXPERT", "MACHINE"}:
        fields.update(
            {
                "evidence_basis_ref": _first_ref(regime_axis.evidence_refs),
                "commitment_profile_ref": (
                    _first_ref(commitment_axis.evidence_refs) if commitment_axis else None
                ),
                "asymmetry_penalty": _asymmetry_penalty(regime_axis.position),
                "stakes_band": commitment.get("stakes", candidate.commitment_stakes or "unknown"),
                "lifecycle_stage": commitment.get("lifecycle_stage", "see_commitment_profile"),
                "selected_floor": commitment.get(
                    "selected_floor",
                    _selected_floor_for_commitment(candidate.commitment_stakes),
                ),
            }
        )
    return fields


def _commitment_axis_position(
    *,
    commitment_stakes: Literal["low", "high", "catastrophic"] | None,
    design_strategy: str | None,
) -> str:
    return ";".join(
        [
            f"stakes={commitment_stakes or 'unknown'}",
            "lifecycle_stage=see_commitment_profile",
            f"selected_floor={_selected_floor_for_commitment(commitment_stakes)}",
            f"design_strategy={design_strategy or 'not_injected'}",
        ]
    )


def _parse_commitment_axis_position(position: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for part in position.split(";"):
        key, separator, value = part.partition("=")
        if separator and key and value:
            parsed[key] = value
    return parsed


def _first_ref(refs: list[str]) -> str | None:
    return refs[0] if refs else None


def _asymmetry_penalty(regime: str) -> float:
    if regime == "risk":
        return 0.0
    if regime == "ignorance":
        return 2.0
    return 1.0


def _adaptive_posture(design_strategy: object) -> str:
    if design_strategy == "expected_welfare_optimization":
        return "optimization_shadow_only"
    if design_strategy == "frame_indexed_portfolio":
        return "frame_indexed_limited"
    if design_strategy == "precautionary_adaptive_pathway":
        return "precautionary_adaptive"
    return "robust_limited"


def _cluster_interfaces(boundary: AuthorityBoundary) -> list[ClusterInterfaceContract]:
    return [
        ClusterInterfaceContract(
            contract_id="layer2.s2.cluster.interface.design_grammar",
            cell_ref="INTERVENTION.design_grammar",
            publishes=["DesignGrammarExpansion"],
            consumes=["Layer2S2DesignSearchInput"],
            authority_boundary=boundary,
        ),
        ClusterInterfaceContract(
            contract_id="layer2.s2.cluster.interface.design_candidate",
            cell_ref="INTERVENTION.design_candidate",
            publishes=["DesignCandidateV0", "SearchLedger", "DesignRecordV0"],
            consumes=["DesignGrammarExpansion", "CounterexampleRecord"],
            authority_boundary=boundary,
        ),
    ]


def _handoff_records(
    candidate: DesignCandidateV0,
    expansion: DesignGrammarExpansion,
    ledger: SearchLedger,
) -> list[ClusterHandoffRecord]:
    return [
        ClusterHandoffRecord(
            handoff_id="layer2.s2.handoff.generation",
            workflow_ref="workflow://layer2/s2/shadow-design-loop",
            source_cell_ref="INTERVENTION.design_grammar",
            target_cell_ref="INTERVENTION.design_candidate",
            artifact_refs=[expansion.expansion_ref, candidate.candidate_ref, ledger.ledger_ref],
            disposition="emitted",
            authority_purpose=_AUTHORITY_PURPOSE,
            may_not_use_for=list(_MAY_NOT_USE_FOR),
        )
    ]


def _governance_decision_class(input: Layer2S2DesignSearchInput) -> GovernanceDecisionClass:
    return GovernanceDecisionClass(
        decision_class_id="a_spec_gap",
        label="A-side specification gap",
        required_role="policy_design_governance_reviewer",
        default_posture="shadow",
        high_stakes=False,
        authority_boundary=AuthorityBoundary(
            authoritative_for=["governance_gap_routing"],
            may_not_use_for=list(_MAY_NOT_USE_FOR),
            source_authority="human_governance",
            posture="shadow",
            rule_version_refs=[input.rule_version_ref],
        ),
    )


def _deterministic_replay_key(
    input: Layer2S2DesignSearchInput,
    *,
    candidate: DesignCandidateV0,
    counterexample: CounterexampleRecord,
    decision: RefinementDecision,
) -> str:
    payload = {
        "case_id": input.case_id,
        "intent_ref": input.intent_ref,
        "grammar_ref": input.grammar_ref,
        "objective_refs": list(input.objective_refs),
        "construct_refs": list(input.construct_refs),
        "candidate_ref": candidate.candidate_ref,
        "counterexample_class": counterexample.counterexample_class,
        "decision": decision.decision,
        "value_of_information.estimate_id": decision.value_of_information.estimate_id,
        "budget_refs": list(decision.budget_refs),
    }
    if any(
        value is not None
        for value in (
            candidate.regime,
            candidate.design_strategy,
            candidate.commitment_profile_ref,
            candidate.commitment_stakes,
        )
    ):
        payload.update(
            {
                "regime": candidate.regime,
                "design_strategy": candidate.design_strategy,
                "commitment_profile_ref": candidate.commitment_profile_ref,
                "commitment_stakes": candidate.commitment_stakes,
            }
        )
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _counterexample_message(counterexample_class: str) -> str:
    if counterexample_class == "a_spec_gap":
        return "A-side specification is incomplete and must route to governance."
    if counterexample_class == "substrate_gap":
        return (
            "Required substrate is unavailable; acquisition is required but not authorized by S2."
        )
    if counterexample_class == "budget_gap":
        return "Search budget is exhausted; S2 must abstain from best-candidate authority."
    return "Candidate violates a shadow A-side design constraint and must be refined."


def _decision_reason(
    decision: RefinementDecisionKind,
    counterexample_class: str,
    *,
    design_strategy: str | None = None,
) -> str:
    if decision == "human_decision":
        return "A-side specification gaps are governance-owned and cannot be self-repaired."
    if decision == "acquire":
        return "Substrate gaps route to acquisition while preserving bridge_missing authority."
    if decision == "abstain":
        return "Budget gaps preserve search incompleteness instead of laundering a frontier."
    if decision == "block_candidate":
        return "The same blocked candidate cannot be retried into a pass without new grammar."
    if decision == "reframe":
        strategy_note = f" under {design_strategy}" if design_strategy else ""
        frame_note = (
            "; frame-indexed portfolios remain a limitation until S8 value provenance"
            if design_strategy == "frame_indexed_portfolio"
            else ""
        )
        return (
            f"{counterexample_class} is consumed by reframe{strategy_note}, "
            "not point-optimization refinement"
            f"{frame_note}."
        )
    return f"{counterexample_class} is consumed by deterministic shadow refinement."


def _stakes_band_for_commitment(
    commitment_stakes: Literal["low", "high", "catastrophic"] | None,
) -> Literal["low", "moderate", "high", "high_stakes"]:
    if commitment_stakes == "catastrophic":
        return "high_stakes"
    if commitment_stakes == "high":
        return "high"
    if commitment_stakes == "low":
        return "low"
    return "moderate"


def _selected_floor_for_commitment(
    commitment_stakes: Literal["low", "high", "catastrophic"] | None,
) -> Literal["low_stakes", "standard", "high_stakes"]:
    if commitment_stakes == "catastrophic":
        return "high_stakes"
    if commitment_stakes == "low":
        return "low_stakes"
    return "standard"


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip(".-")
    if not slug or not slug[0].isalpha():
        return f"s2.{slug or 'record'}"
    return slug
