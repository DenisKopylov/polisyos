from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from polisyos.pdc import (
    S2_DESIGN_SEARCH_SCHEMA_VERSION,
    ConstraintStoreSnapshot,
    CounterexampleRecord,
    DesignCandidateV0,
    DesignGrammarExpansion,
    DesignRecordV0,
    Layer2S2DesignSearchInput,
    Layer2S2DesignSearchInputError,
    RefinementDecision,
    SearchLedger,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
FIRST_PROVING_CASE_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer2_first_proving_case.json"
)
NOW = datetime(2026, 5, 30, tzinfo=UTC)


def _input() -> Layer2S2DesignSearchInput:
    proving_case = json.loads(FIRST_PROVING_CASE_PATH.read_text(encoding="utf-8"))
    return Layer2S2DesignSearchInput(
        schema_version=S2_DESIGN_SEARCH_SCHEMA_VERSION,
        case_id=str(proving_case["case_id"]),
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=tuple(f"objective://{item}" for item in proving_case["constructs"]),
        construct_refs=tuple(f"construct://{item}" for item in proving_case["constructs"]),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=NOW,
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )


def test_s2_shadow_loop_emits_grammar_candidate_counterexample_refinement_and_record() -> None:
    run = run_s2_shadow_design_loop(_input())

    assert isinstance(run.grammar_expansion, DesignGrammarExpansion)
    assert isinstance(run.candidates[0], DesignCandidateV0)
    assert isinstance(run.constraint_store, ConstraintStoreSnapshot)
    assert isinstance(run.counterexamples[0], CounterexampleRecord)
    assert isinstance(run.refinement_decisions[0], RefinementDecision)
    assert isinstance(run.search_ledger, SearchLedger)
    assert isinstance(run.design_record, DesignRecordV0)
    assert run.status == "shadow_ready"
    assert run.search_ledger.counterexample_conversion_rate == 1.0
    assert run.search_ledger.acquisition_branch_state == "bridge_missing"
    assert run.design_record.projection_status == "shadow"
    assert run.design_record.candidate_ref == run.candidates[0].candidate_ref
    assert run.design_record.ledger_refs == [run.search_ledger.ledger_ref]
    assert run.design_record.axis_positions
    assert run.design_record.firewall_status
    assert run.search_ledger.counterexample_refs == [run.counterexamples[0].counterexample_ref]
    assert run.search_ledger.refinement_decision_refs == [run.refinement_decisions[0].decision_ref]
    assert run.refinement_decisions[0].value_of_information.estimate_id == (
        "s2_shadow_refinement_voi"
    )
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for


def test_s2_candidate_is_derived_from_grammar_before_candidate_emission() -> None:
    run = run_s2_shadow_design_loop(_input())

    candidate = run.candidates[0]
    assert candidate.grammar_expansion_ref == run.grammar_expansion.expansion_ref
    assert candidate.source_authority == "deterministic_producer"
    assert candidate.field_source_classification["instrument_family"] == "deterministic_grammar"
    assert candidate.field_source_classification["parameterization"] == "deterministic_grammar"
    assert run.grammar_expansion.instrument_families[:2] == [
        "credit_guarantee",
        "interest_rate_buydown",
    ]
    assert "cash_grant" in run.grammar_expansion.instrument_families


def test_s2_counterexample_classes_are_governed_and_typed() -> None:
    run = run_s2_shadow_design_loop(_input())

    assert set(run.search_ledger.counterexample_class_vocabulary) == {
        "real_design_blocker",
        "substrate_gap",
        "a_spec_gap",
        "abstraction_gap",
        "value_gap",
        "budget_gap",
    }
    assert {record.counterexample_class for record in run.counterexamples} == {
        "real_design_blocker"
    }
    assert run.counterexamples[0].diagnostic.severity == "block"
    assert run.counterexamples[0].diagnostic.authority_purpose == "shadow_design_search_replay"


def test_s2_a_spec_gap_routes_to_governance_not_self_repair() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "a_spec_gap"})
    )

    assert run.status == "governance_required"
    assert run.refinement_decisions[0].decision == "human_decision"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert run.refinement_decisions[0].governance_decision_class_ref == "a_spec_gap"
    assert run.refinement_decisions[0].governance_decision_class is not None
    assert "governance://layer2/s2/a_spec_gap" in run.refinement_decisions[0].governance_refs


def test_s2_substrate_gap_requests_acquisition_without_claiming_acquisition() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "substrate_gap"})
    )

    assert run.status == "acquisition_required"
    assert run.refinement_decisions[0].decision == "acquire"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert run.search_ledger.acquisition_branch_state == "bridge_missing"
    assert "acquisition_authority" in run.design_record.authority_boundary.may_not_use_for


def test_s2_budget_gap_abstains_with_honest_search_incompleteness() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "budget_gap"})
    )

    assert run.status == "abstained"
    assert run.refinement_decisions[0].decision == "abstain"
    assert run.refinement_decisions[0].next_candidate_ref is None
    assert "best_known_shadow_frontier" in run.search_ledger.search_incompleteness_note
    assert "production_recommendation" in run.design_record.authority_boundary.may_not_use_for


def test_s2_blocked_candidate_cannot_be_retried_into_pass_without_new_grammar() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"force_retry_same_candidate": True})
    )

    assert run.status == "blocked"
    assert run.refinement_decisions[0].decision == "block_candidate"
    assert run.search_ledger.no_retry_without_new_grammar is True
    assert run.search_ledger.iterations[-1].status == "blocked_no_retry"


def test_s2_llm_only_candidate_without_grammar_derivation_fails_p15() -> None:
    with pytest.raises(
        Layer2S2DesignSearchInputError,
        match="llm_candidate requires grammar_expansion_ref and remains shadow-only",
    ):
        run_s2_shadow_design_loop(
            _input().model_copy(
                update={
                    "candidate_source_authority": "llm_candidate",
                    "omit_grammar_derivation": True,
                }
            )
        )


def test_s2_replay_key_is_deterministic_for_same_input() -> None:
    first = run_s2_shadow_design_loop(_input())
    second = run_s2_shadow_design_loop(_input())

    assert first.search_ledger.deterministic_replay_key == (
        second.search_ledger.deterministic_replay_key
    )
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_s2_machine_and_reviewer_projection_expose_trace_without_authority() -> None:
    run = run_s2_shadow_design_loop(_input())

    projections = project_s2_design_search(run, audiences=("MACHINE", "REVIEWER"))

    assert set(projections) == {"MACHINE", "REVIEWER"}
    assert projections["MACHINE"]["search_ledger_ref"] == run.search_ledger.ledger_ref
    assert projections["MACHINE"]["grammar_diversity_minimum"] == 3
    assert projections["REVIEWER"]["counterexample_conversion_rate"] == 1.0
    assert "best_known_shadow_frontier" in projections["REVIEWER"]["search_incompleteness_note"]
    assert (
        "publication_authority" in projections["REVIEWER"]["authority_boundary"]["may_not_use_for"]
    )


def test_injected_regime_recorded_on_record_without_self_classification() -> None:
    pure_s2 = run_s2_shadow_design_loop(_input())
    assert pure_s2.candidates[0].regime is None
    assert pure_s2.design_record.envelope.epistemic_regime_scopes == ["ignorance"]

    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
    )

    candidate = run.candidates[0]
    assert candidate.regime == "uncertainty"
    assert candidate.design_strategy == "robust_satisficing"
    assert candidate.commitment_profile_ref == "pdc://layer2/s4/commitment/ua-msme"
    assert candidate.commitment_stakes == "high"
    assert run.design_record.envelope.epistemic_regime_scopes == ["uncertainty"]
    axis_by_cell = {position.cell_ref: position for position in run.design_record.axis_positions}
    assert axis_by_cell["KNOWLEDGE.epistemic_regime"].position == "uncertainty"
    assert axis_by_cell["KNOWLEDGE.epistemic_regime"].evidence_refs == [
        "pdc://layer2/s4/claim/ua-msme/regime"
    ]
    assert "INTERVENTION.reversibility_lifecycle_stakes" in axis_by_cell
    firewall_by_cell = {status.cell_ref: status for status in run.design_record.firewall_status}
    assert "P16" in firewall_by_cell["KNOWLEDGE.epistemic_regime"].pattern_ids
    assert "P23" in firewall_by_cell["INTERVENTION.reversibility_lifecycle_stakes"].pattern_ids
    assert "pdc://layer2/s4/claim/ua-msme/regime" in run.design_record.ledger_refs
    assert "pdc://layer2/s4/commitment/ua-msme" in run.design_record.ledger_refs


def test_four_audience_surface_renders_regime() -> None:
    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
    )

    projections = project_s2_design_search(
        run,
        audiences=("PUBLIC", "REVIEWER", "EXPERT", "MACHINE"),
    )

    assert set(projections) == {"PUBLIC", "REVIEWER", "EXPERT", "MACHINE"}
    for projection in projections.values():
        assert projection["regime"] == "uncertainty"
        assert projection["design_strategy"] == "robust_satisficing"
    assert "limitation" in projections["PUBLIC"]
    assert "risk-regime authority" in projections["PUBLIC"]["limitation"]
    assert "evidence_basis_ref" not in projections["PUBLIC"]
    assert projections["REVIEWER"]["p16_firewall_status"] == "limit"
    assert projections["EXPERT"]["evidence_basis_ref"] == "pdc://layer2/s4/claim/ua-msme/regime"
    assert projections["EXPERT"]["commitment_profile_ref"] == ("pdc://layer2/s4/commitment/ua-msme")
    assert projections["EXPERT"]["stakes_band"] == "high"
    assert projections["EXPERT"]["selected_floor"] == "standard"
    assert projections["MACHINE"]["p23_firewall_status"] == "limit"


def test_public_projection_dropping_limitation_fails() -> None:
    from polisyos.pdc._impl.layer2_design_search import (
        assert_s2_public_projection_has_regime_limitation,
    )

    run = run_s2_shadow_design_loop(
        _input(),
        regime="uncertainty",
        design_strategy="robust_satisficing",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="high",
    )
    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]
    assert_s2_public_projection_has_regime_limitation(public_projection)

    broken_projection = dict(public_projection)
    broken_projection.pop("limitation")
    with pytest.raises(ValueError, match="PUBLIC regime projection requires limitation"):
        assert_s2_public_projection_has_regime_limitation(broken_projection)


def test_precautionary_strategy_blocks_point_optimization_refinement() -> None:
    run = run_s2_shadow_design_loop(
        _input().model_copy(update={"forced_counterexample_class": "abstraction_gap"}),
        regime="ignorance",
        design_strategy="precautionary_adaptive_pathway",
        regime_claim_ref="pdc://layer2/s4/claim/ua-msme/regime",
        commitment_profile_ref="pdc://layer2/s4/commitment/ua-msme",
        commitment_stakes="catastrophic",
    )

    decision = run.refinement_decisions[0]
    assert decision.decision == "reframe"
    assert decision.next_candidate_ref is None
    assert decision.stakes_band == "high_stakes"
    assert "precautionary_adaptive_pathway" in decision.reason


def test_s2_persists_design_record_and_search_ledger(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import persist_s2_design_search_run

    run = run_s2_shadow_design_loop(_input())
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)

    assert refs["design_record"].kind == "policyos.layer2_s2.design_record_v0"
    assert refs["search_ledger"].kind == "policyos.layer2_s2.search_ledger"
    assert refs["design_record"].media_type == "application/json"
    assert refs["search_ledger"].media_type == "application/json"
    design_record = json.loads(store.get_bytes(refs["design_record"].artifact_id))
    search_ledger = json.loads(store.get_bytes(refs["search_ledger"].artifact_id))
    assert design_record["record_id"] == run.design_record.record_id
    assert search_ledger["deterministic_replay_key"] == (run.search_ledger.deterministic_replay_key)


def test_s2_loaded_ledger_replays_same_key(tmp_path: Path) -> None:
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.pdc import load_s2_search_ledger, persist_s2_design_search_run

    run = run_s2_shadow_design_loop(_input())
    store = FileSystemCAS(tmp_path / "cas")
    refs = persist_s2_design_search_run(run, store=store)
    loaded = load_s2_search_ledger(store=store, artifact_ref=refs["search_ledger"])

    assert loaded == run.search_ledger
