from __future__ import annotations

# ruff: noqa: S101
import copy
import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_capability_ratchet as ratchet

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_SMOKE_PATH = REPO_ROOT / "architecture/policy_design_case/wave1_baseline_smoke_corpus.json"
CLOSEOUT_SMOKE_PATH = REPO_ROOT / "architecture/policy_design_case/wave1_closeout_reader_smoke.json"
WAVE3_CORPUS_COVERAGE_PATH = (
    REPO_ROOT / "architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json"
)
WAVE3_I3_CHECKPOINT_PATH = (
    REPO_ROOT / "architecture/policy_design_case/wave3_i3_producer_adapter_checkpoint/manifest.json"
)
WAVE4_I4_MANIFEST_PATH = (
    REPO_ROOT / "architecture/policy_design_case/wave4_i4_runtime_closeout_manifest.json"
)
WAVE6E_MANIFEST_PATH = (
    REPO_ROOT
    / "architecture/policy_design_case/wave6e_llm_formulator_critic_ensemble_manifest.json"
)
WAVE6_UNIVERSAL_KERNEL_IDS = {
    "w6a_universal_policy_grammar_compiler",
    "w6b_governed_obligation_rule_catalog",
    "w6c_obligation_graph_compiler",
    "w6d_claim_decomposition_compiler",
    "w6e_llm_formulator_critic_ensemble",
    "w6f_hypothesis_ledger_candidate_firewall",
}
WAVE9_ADVANCED_LIFECYCLE_IDS = {
    "w9a_drift_detector_implementations",
    "w9b_partial_scope_reissue_mechanics",
    "w9c_data_forge_snapshot_provenance_manifest",
    "w9d_memory_decay_ttl_contamination_controls",
    "w9e_continuous_governance_lifecycle_bridge",
    "w9f_rule_evolution_replay_engine",
    "w9i9_lifecycle_drift_smoke",
}
WAVE10_TEMPORAL_COST_FMEA_IDS = {
    "w10a_bounded_liveness_deadline_invariants",
    "w10b_review_effectiveness_measurement",
    "w10c_missing_r14_adversarial_probes",
    "w10d_authority_level_run_cost_gate",
    "w10e_complexity_budget_governance_pruning",
    "w10f_repair_decision_fmea_annotation",
    "w10i10_cost_gate_fmea_smoke",
}
WAVE11_OUTCOME_CORPUS_IDS = {
    "w11b_claim_evidence_decomposition_annotations",
    "w11c_expert_adjudication_labels",
}
POLICY_EVIDENCE_OPEN_LABELS: dict[str, str] = {}
POLICY_EVIDENCE_IMPLEMENTED_LABELS = {
    "policy_evidence_capability_graph": "implemented",
    "requirement_to_capability_resolver": "implemented",
    "construct_registry": "implemented",
    "capability_index_compiler": "implemented",
    "authority_composition": "implemented",
    "cross_modal_capability_graph": "implemented",
    "production_data_acquisition_planner": "implemented",
    "legacy_scenario_family_authority": "surface_out_of_scope",
}
TRACEABILITY_ROLLOUT_FIELDS = {
    "feature_flag_or_scope",
    "canary_or_revalidation",
    "rollback_or_reversal",
}


def test_w1a_capability_reality_report_is_generated_and_valid() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    generated = ratchet.build_capability_reality_report_payload(REPO_ROOT)
    validation = ratchet.validate_capability_reality_report(payload, repo_root=REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert payload == generated
    assert payload["schema_version"] == ratchet.SCHEMA_VERSION
    assert payload["ratchet_integrity_status"] == "pass"
    assert payload["summary"]["capability_claims_total"] >= 5
    assert payload["summary"]["state_counts"]["implemented"] >= 1
    assert "contract_only" in payload["debt_algebra"]["base_points"]
    assert payload["debt_algebra"]["purpose_multipliers"]["authority_gate"] == 2.0
    assert payload["readiness"]["band"] == "green"
    assert "semantic_test_missing" in payload["ratchet_templates"]


def test_wave1_foundation_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}

    assert {
        "w1a_capability_ratchet",
        "w1b_semantic_fixtures",
        "w1c_status_and_deficits",
        "w1d_closeout_reader_skeleton",
        "w1e_documentation_paths",
    } <= set(claims)
    for capability_id in (
        "w1a_capability_ratchet",
        "w1b_semantic_fixtures",
        "w1c_status_and_deficits",
        "w1d_closeout_reader_skeleton",
        "w1e_documentation_paths",
    ):
        claim = claims[capability_id]
        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= set(claim["evidence_refs"]), capability_id

    _assert_only_phase0_policy_evidence_debt_is_open(payload)


def test_wave2_shared_carrier_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    wave2_capability_ids = {
        "w2a_concept_spine_handshake",
        "w2b_rule_evolution_registry",
        "w2c_cost_degradation_telemetry",
        "w2d_soft_gate_telemetry",
        "w2e_calibration_ledger",
        "w2f_balanced_memory_schema",
        "w2i2_walking_skeleton",
    }

    assert wave2_capability_ids <= set(claims)
    for capability_id in wave2_capability_ids:
        claim = claims[capability_id]
        evidence_refs = set(claim["evidence_refs"])

        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "semantic_test_ref",
        } <= evidence_refs, capability_id
        assert "surface_ref" in evidence_refs or claim["surface_out_of_scope"], capability_id

    _assert_only_phase0_policy_evidence_debt_is_open(payload)


def test_wave3_producer_adapter_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    wave3_capability_ids = {
        "w3a_ir_analytics_bridge",
        "w3b_lex_legal_adapter",
        "w3c_fabric_data_adapter",
        "w3d_scholar_adapter",
        "w3e_foundry_method_adapter",
        "w3f_data_forge_closeout_binding",
        "w3g_acquisition_planner",
        "w3i3_producer_adapter_checkpoint",
    }

    assert wave3_capability_ids <= set(claims)
    for capability_id in wave3_capability_ids:
        claim = claims[capability_id]
        evidence_refs = set(claim["evidence_refs"])

        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= evidence_refs, capability_id

    _assert_only_phase0_policy_evidence_debt_is_open(payload)


def test_wave3_exit_records_i3_checkpoint_and_adapter_corpus_coverage() -> None:
    coverage = json.loads(WAVE3_CORPUS_COVERAGE_PATH.read_text(encoding="utf-8"))
    checkpoint = json.loads(WAVE3_I3_CHECKPOINT_PATH.read_text(encoding="utf-8"))

    assert coverage["schema_version"] == (
        "policyos.policy_design_case.wave3.producer_adapter_corpus_coverage.v1"
    )
    assert coverage["status"] == "recorded"
    assert {
        "ir_analytics",
        "lex",
        "fabric",
        "scholar",
        "foundry",
        "data_forge",
        "acquisition",
    } <= {producer["producer"] for producer in coverage["producer_coverage"]}
    assert all(
        producer["authority_bearing_fixture_ref"]
        and producer["blocked_or_laundering_fixture_ref"]
        and producer["typed_blocker_fixture_ref"]
        and producer["capability_reality_status"] == "implemented"
        and producer["authority_envelope_ref"]
        and producer["context_only_is_non_authoritative"] is True
        for producer in coverage["producer_coverage"]
    )
    _assert_repo_refs_resolve(coverage)

    assert checkpoint["schema_version"] == (
        "policyos.policy_design_case.wave3.i3_producer_adapter_checkpoint.v1"
    )
    assert checkpoint["status"] == "passed"
    assert checkpoint["adapter_set_status"] == "accepted_for_remaining_breadth"
    assert checkpoint["producer_adapter_corpus_coverage_ref"] == (
        "repo://architecture/policy_design_case/wave3_producer_adapter_corpus_coverage.json"
    )
    assert checkpoint["validation"]["commands"] == [
        "uv run pytest tests/unit/lex tests/unit/fabric tests/unit/foundry tests/unit/scientist -q",
        "uv run pytest tests/unit/runtime/quality -q",
    ]


def test_policy_evidence_capability_graph_phase7_labels_are_recorded() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    input_claims = {
        claim["capability_id"]: claim for claim in payload["capability_claim_inputs"]
    }

    assert {
        capability_id: claims[capability_id]["reality_state"]
        for capability_id in POLICY_EVIDENCE_OPEN_LABELS
    } == POLICY_EVIDENCE_OPEN_LABELS
    assert {
        capability_id: claims[capability_id]["reality_state"]
        for capability_id in POLICY_EVIDENCE_IMPLEMENTED_LABELS
    } == POLICY_EVIDENCE_IMPLEMENTED_LABELS
    for capability_id in (
        "policy_evidence_capability_graph",
        "requirement_to_capability_resolver",
        "construct_registry",
        "capability_index_compiler",
    ):
        claim = claims[capability_id]
        input_claim = input_claims[capability_id]
        assert claim["release_blocker"] is False, capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["owner"] == "team-runtime-quality", capability_id
        assert input_claim["decision_refs"] == ["ADR-0174"], capability_id

    construct_claim = claims["construct_registry"]
    assert construct_claim["reality_state"] == "implemented"
    assert construct_claim["owner"] == "team-runtime-quality"
    assert construct_claim["evidence_refs"]["artifact_ref"] == (
        "repo://architecture/policy_design_case/construct_registry_v1.yaml"
    )
    assert input_claims["construct_registry"]["decision_refs"] == ["ADR-0174"]
    authority_claim = claims["authority_composition"]
    assert authority_claim["reality_state"] == "implemented"
    assert authority_claim["evidence_refs"]["typed_contract_ref"] == (
        "repo://src/polisyos/runtime/quality/capability_authority.py#CapabilityBindingResult"
    )

    cross_modal_claim = claims["cross_modal_capability_graph"]
    cross_modal_evidence_refs = set(cross_modal_claim["evidence_refs"])
    assert cross_modal_claim["owner"] == "team-runtime-quality"
    assert cross_modal_claim["release_blocker"] is False
    assert cross_modal_claim["graduation_allowed"] is True
    assert {
        "typed_contract_ref",
        "producer_ref",
        "artifact_ref",
        "bridge_ref",
        "consumer_ref",
        "verification_ref",
        "surface_ref",
        "semantic_test_ref",
    } <= cross_modal_evidence_refs
    assert input_claims["cross_modal_capability_graph"]["decision_refs"] == ["ADR-0174"]
    legacy_claim = claims["legacy_scenario_family_authority"]
    assert legacy_claim["reality_state"] == "surface_out_of_scope"
    assert legacy_claim["surface_out_of_scope"]["rationale"]
    assert legacy_claim["evidence_refs"]["surface_ref"] == (
        "repo://architecture/shims.toml#scenario_family_authority_lookup"
    )

    _assert_only_phase0_policy_evidence_debt_is_open(payload)


def test_wave4_runtime_closeout_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    wave4_capability_ids = {
        "w4a_nl_replay_orchestration",
        "w4b_portfolio_aggregation",
        "w4c_lifecycle_partial_reissue",
        "w4d_closeout_integration",
        "w4e_typed_pdc_projection_backend",
        "w4i4_runtime_pdc_graph_closeout",
    }

    assert wave4_capability_ids <= set(claims)
    for capability_id in wave4_capability_ids:
        claim = claims[capability_id]
        evidence_refs = set(claim["evidence_refs"])

        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= evidence_refs, capability_id

    _assert_only_phase0_policy_evidence_debt_is_open(payload)


def test_wave4_exit_records_i4_manifest_and_contract_evidence() -> None:
    manifest = json.loads(WAVE4_I4_MANIFEST_PATH.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == (
        "policyos.policy_design_case.wave4.i4_runtime_closeout_manifest.v1"
    )
    assert manifest["status"] == "closed"
    assert manifest["wave_id"] == "Wave 4"
    assert manifest["integration_slice"] == "I4"
    assert {
        "W4.A",
        "W4.B",
        "W4.C",
        "W4.D",
        "W4.E",
        "I4",
    } <= {phase["phase_id"] for phase in manifest["completed_phases"]}
    assert {
        "runtime_orchestration_continuity",
        "portfolio_effective_support",
        "lifecycle_partial_reissue",
        "can_i_closeout",
        "typed_policy_design_case_projection",
        "i4_policy_design_case_graph",
    } <= {artifact["artifact_id"] for artifact in manifest["artifacts_produced"]}
    assert {
        "w4a_nl_replay_orchestration",
        "w4b_portfolio_aggregation",
        "w4c_lifecycle_partial_reissue",
        "w4d_closeout_integration",
        "w4e_typed_pdc_projection_backend",
        "w4i4_runtime_pdc_graph_closeout",
    } <= {
        row["capability_id"]
        for row in manifest["capability_states_closed"]
        if row["reality_state"] == "implemented"
    }
    assert manifest["i4_evidence"]["happy_path"]["closeout_status"] == "closed"
    assert manifest["i4_evidence"]["typed_blocker_path"]["blocker_kind"] == (
        "scoped_lifecycle_partial_reissue"
    )
    assert manifest["i4_evidence"]["typed_blocker_path"]["whole_case_rewrite"] is False
    assert manifest["deferred_blockers"] == []
    _assert_repo_refs_resolve(manifest)


def test_wave5_external_surface_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    wave5_capability_ids = {
        "w5a_external_surfaces_truth",
        "w5b_semantic_evaluation_packs",
        "w5c_calibration_behavior",
        "w5d_balanced_memory_behavior",
        "w5e_operator_docs_runbooks",
        "w5i5_external_consumer_truth_check",
    }

    assert wave5_capability_ids <= set(claims)
    for capability_id in wave5_capability_ids:
        claim = claims[capability_id]
        evidence_refs = set(claim["evidence_refs"])

        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= evidence_refs, capability_id

    _assert_only_phase0_policy_evidence_debt_is_open(payload)


def test_wave5_exit_records_i5_manifest_and_influence_boundaries() -> None:
    manifest_path = (
        REPO_ROOT / "architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["schema_version"] == (
        "policyos.policy_design_case.wave5.i5_external_consumer_truth_manifest.v1"
    )
    assert manifest["status"] == "closed"
    assert manifest["wave_id"] == "Wave 5"
    assert manifest["integration_slice"] == "I5"
    assert {
        "W5.A",
        "W5.B",
        "W5.C",
        "W5.D",
        "W5.E",
        "I5",
    } <= {phase["phase_id"] for phase in manifest["completed_phases"]}
    assert {
        "w5a_external_surfaces_truth",
        "w5b_semantic_evaluation_packs",
        "w5c_calibration_behavior",
        "w5d_balanced_memory_behavior",
        "w5e_operator_docs_runbooks",
        "w5i5_external_consumer_truth_check",
    } <= {
        row["capability_id"]
        for row in manifest["capability_states_closed"]
        if row["reality_state"] == "implemented"
    }
    assert {
        "public",
        "reviewer",
        "expert",
        "machine",
    } == {row["audience"] for row in manifest["i5_evidence"]["external_contract_fixtures"]}
    assert all(
        row["contract_status"] == "pass"
        and row["semantic_omission_manifest_status"] == "pass"
        and row["closeout_truth_preserved"] is True
        for row in manifest["i5_evidence"]["external_contract_fixtures"]
    )
    assert manifest["i5_evidence"]["dashboard_truth_check"]["none_to_success"] == "blocked"
    assert manifest["i5_evidence"]["calibration_boundary"]["current_run_evidence_effect"] == "none"
    assert (
        manifest["i5_evidence"]["memory_boundary"]["evidence_slot_admission"]
        == "forbidden"
    )
    assert manifest["deferred_blockers"] == []
    _assert_repo_refs_resolve(manifest)


def test_wave6a_local_validation_ladder_claim_is_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    claim = claims["w6a_local_validation_ladder"]

    assert claim["reality_state"] == "implemented"
    assert claim["graduation_allowed"] is True
    assert claim["release_blocker"] is False
    assert {
        "typed_contract_ref",
        "producer_ref",
        "artifact_ref",
        "bridge_ref",
        "consumer_ref",
        "verification_ref",
        "surface_ref",
        "semantic_test_ref",
    } <= set(claim["evidence_refs"])

    manifest = json.loads(
        (
            REPO_ROOT
            / "architecture/policy_design_case/wave6_local_validation_ladder_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.wave6.local_validation_ladder_manifest.v1"
    )
    assert manifest["metric_policy"]["typed_blockers_count_as_useful_design"] is False
    assert manifest["metric_policy"]["accepted_deficits_count_as_useful_design"] is False
    assert "local_production_debug" in manifest["required_categories"]
    _assert_repo_refs_resolve(manifest)


def test_wave6e_llm_formulator_critic_ensemble_claim_is_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}
    claim = claims["w6e_llm_formulator_critic_ensemble"]

    assert claim["reality_state"] == "implemented"
    assert claim["graduation_allowed"] is True
    assert claim["release_blocker"] is False
    assert {
        "typed_contract_ref",
        "producer_ref",
        "artifact_ref",
        "bridge_ref",
        "consumer_ref",
        "verification_ref",
        "surface_ref",
        "semantic_test_ref",
    } <= set(claim["evidence_refs"])

    manifest = json.loads(WAVE6E_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.wave6e.llm_formulator_critic_ensemble.v1"
    )
    assert manifest["formulator"]["source_class"] == "llm_candidate"
    assert manifest["formulator"]["admission_state"] == "candidate_unverified"
    assert manifest["formulator"]["authoritative_for"] == []
    assert {
        "field",
        "risk",
        "obligation",
        "missing_question",
        "method_need",
    } <= set(manifest["formulator"]["candidate_kinds"])
    assert len({critic["substantive_basis"] for critic in manifest["critics"]}) == 8
    assert {
        "legal",
        "fiscal",
        "equity",
        "data",
        "implementation",
        "affected_person",
        "adversarial",
        "monitoring",
    } == {critic["role"] for critic in manifest["critics"]}
    assert "critic_monoculture_identical_output" in manifest["negative_tests"]
    _assert_repo_refs_resolve(manifest)


def test_wave6_universal_compilation_kernel_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}

    assert set(claims) >= WAVE6_UNIVERSAL_KERNEL_IDS
    for capability_id in WAVE6_UNIVERSAL_KERNEL_IDS:
        claim = claims[capability_id]
        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= set(claim["evidence_refs"]), capability_id


def test_wave9_advanced_lifecycle_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}

    assert set(claims) >= WAVE9_ADVANCED_LIFECYCLE_IDS
    for capability_id in WAVE9_ADVANCED_LIFECYCLE_IDS:
        claim = claims[capability_id]
        input_claim = next(
            row
            for row in payload["capability_claim_inputs"]
            if row["capability_id"] == capability_id
        )

        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= set(claim["evidence_refs"]), capability_id
        assert "P07" in input_claim["research_refs"], capability_id
        assert "P09" in input_claim["research_refs"], capability_id


def test_wave10_temporal_cost_fmea_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}

    assert set(claims) >= WAVE10_TEMPORAL_COST_FMEA_IDS
    for capability_id in WAVE10_TEMPORAL_COST_FMEA_IDS:
        claim = claims[capability_id]
        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= set(claim["evidence_refs"]), capability_id


def test_wave11_outcome_corpus_claims_are_closed_in_exit_report() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    claims = {claim["capability_id"]: claim for claim in payload["capability_claims"]}

    assert set(claims) >= WAVE11_OUTCOME_CORPUS_IDS
    input_claims = {
        row["capability_id"]: row for row in payload["capability_claim_inputs"]
    }

    for capability_id in WAVE11_OUTCOME_CORPUS_IDS:
        claim = claims[capability_id]
        assert claim["reality_state"] == "implemented", capability_id
        assert claim["graduation_allowed"] is True, capability_id
        assert claim["release_blocker"] is False, capability_id
        assert {
            "typed_contract_ref",
            "producer_ref",
            "artifact_ref",
            "bridge_ref",
            "consumer_ref",
            "verification_ref",
            "surface_ref",
            "semantic_test_ref",
        } <= set(claim["evidence_refs"]), capability_id
        assert "P10" in input_claims[capability_id]["research_refs"], capability_id
    assert "C26" in input_claims["w11b_claim_evidence_decomposition_annotations"]["research_refs"]
    assert "C30" in input_claims["w11c_expert_adjudication_labels"]["research_refs"]


def test_wave1_implemented_claims_include_plan_traceability_rows() -> None:
    payload = ratchet.load_capability_reality_report(REPO_ROOT)
    input_claims = {claim["capability_id"]: claim for claim in payload["capability_claim_inputs"]}

    for claim in payload["capability_claims"]:
        capability_id = claim["capability_id"]
        if claim["reality_state"] != "implemented":
            continue
        input_claim = input_claims[capability_id]
        research_refs = input_claim["research_refs"]
        traceability = claim["traceability"]
        rollout_refs = input_claim["rollout_refs"]

        assert any(str(ref).startswith("C") for ref in research_refs), capability_id
        assert any(str(ref).startswith("E") for ref in research_refs), capability_id
        assert any(str(ref).startswith("P") for ref in research_refs), capability_id
        assert input_claim.get("decision_refs") or input_claim.get("no_adr_required"), capability_id
        assert input_claim["reuse_classification"] in {
            "wire_existing",
            "extend_existing",
            "consolidate_existing",
            "build_new",
        }, capability_id
        if input_claim["reuse_classification"] == "build_new":
            assert input_claim.get("rejected_reuse_evidence"), capability_id
        assert set(rollout_refs) >= TRACEABILITY_ROLLOUT_FIELDS, capability_id
        assert traceability["research_refs"] == research_refs
        assert traceability["reuse_classification"] == input_claim["reuse_classification"]
        assert traceability["rollout_refs"] == rollout_refs


def test_wave1_exit_records_baseline_and_closeout_smoke_artifacts() -> None:
    baseline = json.loads(BASELINE_SMOKE_PATH.read_text(encoding="utf-8"))
    closeout = json.loads(CLOSEOUT_SMOKE_PATH.read_text(encoding="utf-8"))

    assert baseline["schema_version"] == "policyos.policy_design_case.wave1.baseline_smoke.v1"
    assert baseline["status"] == "recorded"
    assert len(baseline["smoke_cases"]) >= 3
    assert {case["domain"] for case in baseline["smoke_cases"]} >= {
        "housing",
        "public_health",
        "tax_benefit",
    }
    assert all(case["pre_implementation_behavior"] for case in baseline["smoke_cases"])
    assert all(
        case["capability_reality_state"] != "implemented" for case in baseline["smoke_cases"]
    )

    assert closeout["schema_version"] == "policyos.runtime.can_i_closeout.reader_skeleton.v1"
    assert closeout["status"] in {"blocked", "incomplete"}
    assert closeout["can_closeout"] is False
    assert closeout["authority_envelope"]["authoritative_for"] == ["closeout_verdict"]
    assert "closeout_module_reader_stubbed" in {issue["code"] for issue in closeout["issues"]}


def test_w1a_validator_rejects_implemented_without_semantic_test_ref() -> None:
    payload = ratchet.build_capability_reality_report_payload(REPO_ROOT)
    payload = copy.deepcopy(payload)
    implemented = next(
        claim
        for claim in payload["capability_claim_inputs"]
        if claim["reality_state"] == "implemented"
    )
    implemented.pop("semantic_test_ref")
    mutated = ratchet.rebuild_report_from_inputs(payload)

    validation = ratchet.validate_capability_reality_report(mutated, repo_root=REPO_ROOT)

    assert validation["status"] == "fail"
    assert "capability_implemented_chain_incomplete" in _issue_codes(validation)


def test_w1a_validator_rejects_open_debt_without_owner_hold_or_target() -> None:
    payload = ratchet.build_capability_reality_report_payload(REPO_ROOT)
    payload = copy.deepcopy(payload)
    open_claim = payload["capability_claim_inputs"][0]
    open_claim["reality_state"] = "contract_only"
    open_claim["owner"] = ""
    open_claim["hold_reason"] = ""
    open_claim["next_wave_target"] = ""
    mutated = ratchet.rebuild_report_from_inputs(payload)

    validation = ratchet.validate_capability_reality_report(mutated, repo_root=REPO_ROOT)

    assert validation["status"] == "fail"
    assert {
        "capability_debt_owner_missing",
        "capability_debt_hold_reason_missing",
        "capability_debt_next_wave_target_missing",
    } <= _issue_codes(validation)


def test_w1a_validator_rejects_implemented_without_traceability_row() -> None:
    payload = ratchet.build_capability_reality_report_payload(REPO_ROOT)
    payload = copy.deepcopy(payload)
    implemented = next(
        claim
        for claim in payload["capability_claim_inputs"]
        if claim["reality_state"] == "implemented"
    )
    implemented.pop("research_refs")
    mutated = ratchet.rebuild_report_from_inputs(payload)

    validation = ratchet.validate_capability_reality_report(mutated, repo_root=REPO_ROOT)

    assert validation["status"] == "fail"
    assert "capability_implemented_traceability_missing" in _issue_codes(validation)


def test_w1a_validator_rejects_unresolvable_repo_anchor() -> None:
    payload = ratchet.build_capability_reality_report_payload(REPO_ROOT)
    payload = copy.deepcopy(payload)
    implemented = next(
        claim
        for claim in payload["capability_claim_inputs"]
        if claim["reality_state"] == "implemented"
    )
    implemented["semantic_test_ref"] = (
        "repo://tests/unit/runtime/quality/test_capability_ratchet.py"
        "#test_anchor_that_does_not_exist"
    )
    mutated = ratchet.rebuild_report_from_inputs(payload)

    validation = ratchet.validate_capability_reality_report(mutated, repo_root=REPO_ROOT)

    assert validation["status"] == "fail"
    assert "capability_repo_ref_anchor_missing" in _issue_codes(validation)


def test_w1a_reference_doc_links_report_command_and_pattern_pass() -> None:
    doc_path = REPO_ROOT / "docs/reference/policy-design-case-capability-ratchet.md"
    doc = doc_path.read_text(encoding="utf-8")

    assert "architecture/policy_design_case/capability_reality_report.json" in doc
    assert "check_policy_design_case_capability_ratchet.py" in doc
    assert "P01" in doc
    assert "P03" in doc
    assert "P10" in doc
    assert "P13" in doc
    assert "`surface_out_of_scope`" in doc


def test_w1a_cli_can_write_json_output(tmp_path: Path) -> None:
    output_path = tmp_path / "ratchet-validation.json"

    exit_code = ratchet.main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--json-output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["status"] == "pass"
    assert payload["report_path"] == ratchet.DEFAULT_REPORT_PATH.as_posix()


def _assert_only_phase0_policy_evidence_debt_is_open(payload: dict[str, object]) -> None:
    claims = {
        str(claim["capability_id"]): claim
        for claim in payload["capability_claims"]  # type: ignore[index]
    }
    open_claims = {
        capability_id: claim["reality_state"]
        for capability_id, claim in claims.items()
        if claim["reality_state"] not in {"implemented", "surface_out_of_scope"}
    }

    assert open_claims == POLICY_EVIDENCE_OPEN_LABELS
    assert payload["summary"]["open_debt_count"] == len(  # type: ignore[index]
        POLICY_EVIDENCE_OPEN_LABELS
    )
    assert payload["summary"]["release_blocker_count"] == 0  # type: ignore[index]
    assert payload["readiness"]["band"] == "green"  # type: ignore[index]


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {
        str(issue["code"])
        for issue in validation["issues"]  # type: ignore[index]
    }


def _assert_repo_refs_resolve(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            _assert_repo_refs_resolve(item, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_repo_refs_resolve(item, f"{path}[{index}]")
        return
    if isinstance(value, str) and value.startswith("repo://"):
        assert (
            ratchet.validate_repo_reference(
                value,
                repo_root=REPO_ROOT,
                path=path,
            )
            is None
        )
