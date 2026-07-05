from __future__ import annotations

from polisyos.runtime.quality import grounding_benchmark as gb
from polisyos.runtime.quality.grounding_benchmark import (
    GroundingBenchmarkCase,
    GroundingBenchmarkDecision,
    GroundingBenchmarkScoreboard,
    build_grounding_benchmark_reference_for_contract_testing,
    run_grounding_benchmark_for_contract_testing,
    validate_grounding_benchmark_payload,
)


def test_benchmark_drops_underivable_labels_instead_of_authoring_truth() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)
    forged = GroundingBenchmarkCase.model_validate(
        {
            **scoreboard.cases[0].model_dump(mode="json"),
            "case_id": "unit.forged_label",
            "label_derivation": {
                "derivation_kind": "hand_asserted",
                "owner_refs": (),
                "proof_hash": "sha256:" + "0" * 64,
            },
        }
    )

    forged_scoreboard = run_grounding_benchmark_for_contract_testing(
        reference,
        cases=(*scoreboard.cases, forged),
    )

    assert forged_scoreboard.summary["dropped_underivable_cases"] >= 1
    assert any(row.case_id == "unit.forged_label" for row in forged_scoreboard.dropped_cases)


def test_must_negative_wrong_atom_identification_counts_false_bind() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    atoms = gb._selected_atoms(reference, limit=2)  # noqa: SLF001
    case = gb._name_collision_false_analog_case(atoms[0], "epoch_0", 0)  # noqa: SLF001

    decision = GroundingBenchmarkDecision(
        case_id=case.case_id,
        case_hash=case.case_hash,
        baseline_id="exact_match_alias_table",
        epoch_id=case.epoch_id,
        stream=case.stream,
        family=case.family,
        relation="exact",
        selected_atom_id=atoms[1].atom_id,
        replay_complete=False,
        latency_ms=0.0,
    )

    assert gb._is_false_bind(case, decision) == 1  # noqa: SLF001


def test_baseline_defeating_families_are_present_and_nonzero_for_honest_baselines() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)
    families = {case.family for case in scoreboard.cases if case.stream == "stress"}

    assert "name_collision_false_analog" in families
    assert "high_lexical_similarity_false_analog" in families
    assert "joint_type_inconsistent" in families

    exact_collision = _slice(
        scoreboard,
        baseline="exact_match_alias_table",
        stream="stress",
        family="name_collision_false_analog",
    )
    lexical_high = _slice(
        scoreboard,
        baseline="lexical_similarity_duckdb_fts_top1",
        stream="stress",
        family="high_lexical_similarity_false_analog",
    )
    greedy_joint = _slice(
        scoreboard,
        baseline="greedy_per_axis",
        stream="stress",
        family="joint_type_inconsistent",
    )

    assert exact_collision.false_bind.numerator >= 1
    assert lexical_high.false_bind.numerator >= 1
    assert greedy_joint.false_bind.numerator >= 1


def test_greedy_baseline_is_identification_only_not_cgf_hybrid() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)

    greedy_decisions = [
        decision
        for decision in scoreboard.decisions
        if decision.baseline_id == "greedy_per_axis"
    ]

    assert greedy_decisions
    assert all(decision.bind_decision == "abstain" for decision in greedy_decisions)
    assert all(decision.admission_decision == "not_applicable" for decision in greedy_decisions)
    assert all(decision.certificate_chain for decision in greedy_decisions)
    assert all(
        "greedy_identification_only_no_cg2_cg3_safety" in decision.decision_notes
        for decision in greedy_decisions
    )


def test_entity_linker_baseline_is_explicitly_unavailable() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)

    config = scoreboard.baseline_configs["entity_linker_recorded_replay"]
    assert "honestly_unavailable" in config.provenance
    assert all(
        decision.relation == "unavailable"
        for decision in scoreboard.decisions
        if decision.baseline_id == "entity_linker_recorded_replay"
    )


def test_label_derivation_resolves_owner_refs_against_epoch_reference() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    atoms = gb._selected_atoms(reference, limit=1)  # noqa: SLF001
    forged = gb._make_case(  # noqa: SLF001
        stream="stress",
        family="unit_unresolvable_owner_ref",
        epoch_id="epoch_0",
        proposal=gb._proposal(  # noqa: SLF001
            operator=str(atoms[0].signature.op or ""),
            target=atoms[0].signature.X_do[0],
            outcome=atoms[0].signature.outcome[0],
            raw_text="unit unresolved owner proof",
        ),
        labels=("must-",),
        expected_atom_id=atoms[0].atom_id,
        expected_operator=str(atoms[0].signature.op or ""),
        expected_target=atoms[0].signature.X_do[0],
        construction_family="minimal_critical_axis_swap",
        derivation_kind="owner_atom_minimal_critical_axis_swap",
        owner_refs=("L2_CAUSAL_CLAIM::missing_owner_edge",),
        source_atom_id=atoms[0].atom_id,
        index=99,
        decisive="owner_ref_resolution_required",
    )

    base = run_grounding_benchmark_for_contract_testing(reference)
    scoreboard = run_grounding_benchmark_for_contract_testing(
        reference,
        cases=(*base.cases, forged),
    )

    assert any(
        row.case_id == forged.case_id
        and row.reason == "label_derivation_owner_ref_unresolved"
        for row in scoreboard.dropped_cases
    )


def test_scoreboard_requires_growth_headline_and_self_verifying_hash() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)

    assert GroundingBenchmarkScoreboard.model_validate(scoreboard.model_dump(mode="json"))
    assert scoreboard.headline.growth_epoch_count >= 2
    assert scoreboard.headline.metric_id == "false_bind_rate_under_growth"
    assert all(row.epoch_id for row in scoreboard.score_slices)

    corrupted = scoreboard.model_dump(mode="json")
    corrupted["headline"]["growth_epoch_count"] = 0
    corrupted["content_hash"] = "sha256:" + "0" * 64
    report = validate_grounding_benchmark_payload(corrupted)

    assert report["status"] == "fail"
    assert "grounding_benchmark_headline_growth_missing" in report["issue_codes"]
    assert "grounding_benchmark_content_hash_mismatch" in report["issue_codes"]


def test_exact_match_baseline_keeps_alias_table_and_detects_config_drift() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)

    exact = scoreboard.baseline_configs["exact_match_alias_table"]
    assert exact.alias_table_hash
    assert exact.config_hash == exact.expected_config_hash

    corrupted = scoreboard.model_dump(mode="json")
    corrupted["baseline_configs"]["exact_match_alias_table"]["alias_table_hash"] = (
        "sha256:" + "0" * 64
    )
    corrupted["content_hash"] = "sha256:" + "0" * 64
    report = validate_grounding_benchmark_payload(corrupted)

    assert report["status"] == "fail"
    assert "grounding_benchmark_baseline_config_hash_mismatch" in report["issue_codes"]


def test_detector_liveness_broken_variants_degrade_headline() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    scoreboard = run_grounding_benchmark_for_contract_testing(reference)

    variants = {
        row.variant_id: row
        for row in scoreboard.detector_liveness
        if row.variant_id != "working_stack"
    }

    assert {
        "cg1_critical_veto_disabled_only",
        "cg1_critical_veto_disabled_stacked_similarity",
        "cg2_calibration_owner_validation_bypassed_only",
        "cg2_calibration_owner_validation_bypassed_stacked_freeze",
        "cg3_disable_mechanism_witness_resolution_only",
        "cg3_mechanism_witness_trust_restored_stacked",
    }.issubset(variants)
    assert all(row.detection_floor != "not_applicable" for row in variants.values())
    assert all(row.confident_wrong_interval.denominator == row.denominator for row in variants.values())


def test_scoreboard_is_deterministic_for_same_reference_and_seed() -> None:
    reference = build_grounding_benchmark_reference_for_contract_testing()
    first = run_grounding_benchmark_for_contract_testing(reference)
    second = run_grounding_benchmark_for_contract_testing(reference)

    assert first.content_hash == second.content_hash
    assert first.benchmark_id == second.benchmark_id


def _slice(
    scoreboard: GroundingBenchmarkScoreboard,
    *,
    baseline: str,
    stream: str,
    family: str,
):
    return next(
        row
        for row in scoreboard.score_slices
        if row.baseline_id == baseline and row.stream == stream and row.family == family
    )
