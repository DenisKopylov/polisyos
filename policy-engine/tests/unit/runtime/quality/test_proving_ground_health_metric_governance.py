from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import polisyos.runtime.quality.proving_ground.health_metric_governance as g8

REPO_ROOT = Path(__file__).resolve().parents[4]


def test_g8_declares_red_baseline_contract() -> None:
    assert g8.G8_SCHEMA_VERSION == (
        "policyos.policy_design_case.layer3_g8_health_metric_governance.v1"
    )
    assert g8.G8_RULE_VERSION == "policyos.layer3.g8.health_metric_governance.v1"
    assert g8.G8_SURFACE_ID == "layer3_g8_health_metric_governance_surface"
    assert g8.G8_GENERATED_ARTIFACT_FAMILY_ID == (
        "policy-design-case-layer3-g8-health-metric-governance-artifacts"
    )
    assert set(g8.G8_CANONICAL_METRIC_IDS) == {
        "envelope-expansion-rate",
        "adapter-semantic-loss",
        "governance-throughput",
        "demand-pull-vs-abstention",
        "search-recall@known-seeds+index-staleness",
    }
    assert "useful_design_rate_optimization" in g8.G8_MAY_NOT_USE_FOR
    assert "hidden_fixture_access" in g8.G8_MAY_NOT_USE_FOR
    assert "layer3_g8_metric_improved_by_threshold_lowering" in g8.ALL_ISSUE_CODES
    assert "layer3_g8_search_recall_miss_reported_as_domain_ceiling" in g8.ALL_ISSUE_CODES
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in g8.ALL_ISSUE_CODES
    assert "layer3_g8_global_seed_health_used_as_current_blocker_health" in g8.ALL_ISSUE_CODES
    assert "layer3_g8_positive_open_question_reducer_provenance_missing" in (
        g8.ALL_ISSUE_CODES
    )


def test_g8_models_are_strict_and_frozen() -> None:
    row = g8.Layer3G8Issue(
        issue_code="layer3_g8_metric_source_missing",
        ref="repo://missing",
        message="Metric source is missing.",
    )
    assert row.issue_code == "layer3_g8_metric_source_missing"
    with pytest.raises(ValidationError):
        g8.Layer3G8Issue(
            issue_code="layer3_g8_metric_source_missing",
            ref="repo://missing",
            message="Metric source is missing.",
            surprise=True,
        )
    with pytest.raises(ValidationError):
        row.ref = "repo://mutated"


def test_g8_metric_registry_preserves_g0_ledger_semantics() -> None:
    registry = g8.build_g8_health_metric_registry()

    assert registry.status == "pass"
    assert len(registry.entries) == 5
    by_id = {entry.metric_id: entry for entry in registry.entries}
    assert by_id["envelope-expansion-rate"].owner == "team-runtime-quality"
    assert by_id["governance-throughput"].owner == "principal-governance"
    assert by_id["search-recall@known-seeds+index-staleness"].trend_vocabulary == (
        "fresh_recall_ok",
        "search_ceiling",
    )
    assert by_id["search-recall@known-seeds+index-staleness"].source_ledger_ref == (
        "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml"
        "#search-recall@known-seeds+index-staleness"
    )


def test_g8_alias_normalization_accepts_existing_g1_to_g7_spellings() -> None:
    assert g8.canonical_metric_id("search-recall@known-seeds + index-staleness") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id(
        "search-recall@known-seeds+index-staleness(region)"
    ) == "search-recall@known-seeds+index-staleness"
    assert g8.canonical_metric_id("envelope_expansion_rate_region") == (
        "envelope-expansion-rate"
    )
    assert g8.canonical_metric_id("g4-governed-promoted-count") == (
        "governance-throughput"
    )
    assert g8.canonical_metric_id("abstention_or_blocker_rate") == (
        "demand-pull-vs-abstention"
    )
    assert g8.canonical_metric_id("g7_s14_grounded_breadth_feed_status") == (
        "demand-pull-vs-abstention"
    )
    assert g8.canonical_metric_id("search_recall.freshness_status") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id("gl_search_recall_freshness_status") == (
        "search-recall@known-seeds+index-staleness"
    )
    assert g8.canonical_metric_id("unknown-local-metric") is None


def test_g8_source_snapshot_reads_current_g0_to_g7_and_s14_artifacts() -> None:
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)

    assert snapshot.status == "pass"
    assert "layer3_g8_metric_source_missing" not in snapshot.issue_codes
    assert snapshot.source_count >= 44
    refs = {source.source_ref for source in snapshot.sources}
    assert "repo://architecture/policy_design_case/layer3_health_metric_ledgers.toml" in refs
    assert "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g4_governance_throughput_delta.json" in refs
    assert "repo://architecture/policy_design_case/layer3_g5_health_metric_delta.toml" in refs
    assert (
        "repo://architecture/policy_design_case/layer3_g5_dependency_health_metric_snapshot.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g5_useful_design_metric_eligibility_join.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g6_demand_pull_vs_abstention_delta.json"
        in refs
    )
    assert "repo://architecture/policy_design_case/layer3_g6_conformance_report.json" in refs
    assert (
        "repo://architecture/policy_design_case/layer3_g6_orchestration_choice_audit.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g7_search_recall_freshness_join.json"
        in refs
    )
    assert "repo://architecture/policy_design_case/layer3_g7_health_metric_delta.toml" in refs
    assert (
        "repo://architecture/policy_design_case/layer3_g7_g5_g6_authority_boundary_report.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer3_g7_region_widening_audit_surface.json"
        in refs
    )
    assert (
        "repo://architecture/policy_design_case/layer2_s14_universality_assurance_manifest.json"
        in refs
    )


def test_g8_source_snapshot_audits_g1_universal_search_contract_fields() -> None:
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    source = next(
        source
        for source in snapshot.sources
        if source.source_ref
        == "repo://architecture/policy_design_case/layer3_g1_search_recall_freshness.json"
    )

    assert source.search_contract_status == "pass"
    assert source.search_contract_ref.endswith("#search_recall_freshness")
    assert source.search_contract_corpus_kind == "canonical"
    assert source.search_contract_corpus_snapshot_hash.startswith("sha256:")
    assert source.search_contract_replay_command_present is True
    assert source.search_contract_replay_expected_output_hash.startswith("sha256:")
    assert source.search_contract_issue_codes == ()


def test_g8_normalizes_current_metric_dialects_without_losing_raw_refs() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )

    assert signals.status == "pass"
    assert "layer3_g8_metric_source_missing" not in signals.issue_codes
    by_metric = {metric_id: [] for metric_id in g8.G8_CANONICAL_METRIC_IDS}
    for signal in signals.signals:
        by_metric[signal.metric_id].append(signal)
        assert signal.raw_source_ref.startswith("repo://architecture/policy_design_case/")
        assert signal.authoritative_for == g8.G8_AUTHORITATIVE_FOR
        assert "closeout_authority" in signal.may_not_use_for

    assert all(by_metric.values())
    search_refs = {
        signal.raw_key
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    }
    assert "search-recall@known-seeds + index-staleness" in search_refs
    demand_readings = by_metric["demand-pull-vs-abstention"]
    assert any(signal.raw_key == "abstention_or_blocker_rate" for signal in demand_readings)
    assert any(
        signal.slice_id == "G6"
        and signal.raw_key == "abstention_or_blocker_rate"
        and signal.status == "abstention_inertia"
        for signal in demand_readings
    )
    assert any(
        signal.slice_id == "G6"
        and signal.raw_key == "grounded_result_rate"
        and signal.status == "no_grounded_response"
        for signal in demand_readings
    )
    assert any(
        signal.slice_id == "G3"
        and signal.raw_key == "search_recall.freshness_status"
        and signal.status == "pass"
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    )
    assert any(
        signal.slice_id == "GL"
        and signal.raw_key == "known_seed_status"
        and signal.status == "pass"
        for signal in by_metric["search-recall@known-seeds+index-staleness"]
    )


def test_g8_metric_trend_report_exposes_all_five_ci_visible_metrics() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    report = g8.build_g8_metric_trend_report(registry=registry, signals=signals)

    assert report.status == "pass"
    assert {row.metric_id for row in report.metric_trends} == set(g8.G8_CANONICAL_METRIC_IDS)
    by_metric = {row.metric_id: row for row in report.metric_trends}
    assert by_metric["demand-pull-vs-abstention"].latest_status in {
        "abstention_inertia",
        "blocked_by_current_g5_unchanged_blocker",
        "blocked_no_real_grounded_breadth",
        "no_grounded_response",
        "pass",
    }
    assert by_metric["search-recall@known-seeds+index-staleness"].source_refs
    assert report.ci_report_status == "first_class_metric_trends_visible"


def test_g8_current_state_does_not_claim_domain_ceiling() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert diagnosis.status == "pass"
    assert gate.status == "search_ceiling_repair_required"
    assert gate.domain_ceiling_claim_allowed is False
    assert diagnosis.search_health_classification.seed_corpus_status == "fail"
    assert diagnosis.search_health_classification.current_blocker_status == "unmeasured"
    assert (
        "layer3_g8_blocker_specific_search_diagnostic_missing"
        in diagnosis.issue_codes
    )
    assert (
        "layer3_g8_flat_expansion_reported_as_domain_ceiling_without_search_health"
        not in gate.issue_codes
    )
    assert gate.current_blocker_refs
    assert diagnosis.effective_independence_status == "singular"
    assert diagnosis.effective_independent_evidence_count == 0
    assert diagnosis.effective_independence_source_ref == (
        "repo://architecture/policy_design_case/layer3_g5_effective_evidence_independence.json"
        "#independence_map_payload.effective_mass_report"
    )


def test_g8_search_recall_miss_blocks_domain_ceiling() -> None:
    signals = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G5", "g5_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "grounded_result_rate", 0.0),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search-recall@known-seeds+index-staleness",
                "search_ceiling",
            ),
        ),
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert gate.status == "search_ceiling_repair_required"
    assert gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_search_recall_miss_reported_as_domain_ceiling" in gate.issue_codes


def test_g8_unmeasured_g1_recall_blocks_healthy_search_answer() -> None:
    signals = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G5", "g5_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "grounded_result_rate", 0.0),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "g1_search_recall_status",
                "not_measured",
            ),
        ),
    )

    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert gate.status == "search_ceiling_repair_required"
    assert gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_search_recall_miss_reported_as_domain_ceiling" in gate.issue_codes


def test_task6_g8_pinned_case_search_health_changes_with_case_diagnostic_data(
    tmp_path: Path,
) -> None:
    repo_root = _write_task6_case_health_repo(tmp_path)
    global_search_ceiling = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G4", "g4_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "g6_demand_pull_vs_abstention_status", "pass"),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search-recall@known-seeds+index-staleness",
                "search_ceiling",
            ),
        ),
    )
    case_specific_recall = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            *global_search_ceiling.signals,
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search-recall@known-seeds+index-staleness",
                "pass",
                case_id="case:task6",
                diagnostic_scope="blocker_specific_recall",
            ),
        ),
    )

    global_diagnosis = g8.build_g8_cross_metric_diagnosis(
        signals=global_search_ceiling,
        repo_root=repo_root,
        case_id="case:task6",
    )
    global_gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=global_diagnosis)
    case_diagnosis = g8.build_g8_cross_metric_diagnosis(
        signals=case_specific_recall,
        repo_root=repo_root,
        case_id="case:task6",
    )
    case_gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=case_diagnosis)

    assert global_gate.status == "search_ceiling_repair_required"
    assert case_diagnosis.search_recall_freshness_status == "pass"
    assert "search_ceiling" in case_diagnosis.diagnoses
    assert case_gate.status == "search_ceiling_repair_required"
    assert case_gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_domain_ceiling_claim_without_admission_or_deref" in (
        case_gate.issue_codes
    )


def test_task11_domain_ceiling_requires_blocker_frontier_admission_and_deref(
    tmp_path: Path,
) -> None:
    repo_root = _write_task6_case_health_repo(tmp_path)
    full_blocker_recall = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G4", "g4_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "g6_demand_pull_vs_abstention_status", "pass"),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search-recall@known-seeds+index-staleness",
                "search_ceiling",
            ),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search_recall.blocker_specific_frontier",
                {
                    "status": "pass",
                    "search_frontier_status": "pass",
                    "freshness_status": "pass",
                    "admission_status": "pass",
                    "dereferenced_artifact_status": "pass",
                },
                case_id="case:task11",
                diagnostic_scope="blocker_specific_recall",
            ),
        ),
    )

    diagnosis = g8.build_g8_cross_metric_diagnosis(
        signals=full_blocker_recall,
        repo_root=repo_root,
        case_id="case:task11",
    )
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert diagnosis.search_health_classification.current_blocker_status == "pass"
    assert gate.domain_ceiling_precondition_statuses == {
        "search_frontier": "pass",
        "freshness": "pass",
        "admission": "pass",
        "dereferenced_artifacts": "pass",
    }
    assert gate.status == "domain_ceiling_candidate"
    assert gate.domain_ceiling_claim_allowed is True


def test_task11_global_seed_pass_without_blocker_specific_ledger_blocks_search_answer() -> None:
    signals = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G4", "g4_governance_throughput_status", "pass"),
            _signal("demand-pull-vs-abstention", "G6", "g6_demand_pull_vs_abstention_status", "pass"),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G1",
                "search-recall@known-seeds+index-staleness",
                "pass",
            ),
        ),
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    ledger = g8.build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=gate,
        repo_root=REPO_ROOT,
    )

    answer = {
        row.question_id: row for row in ledger.answers
    }["8.4-search-recall-freshness"]
    assert answer.answer_status == "answered_currently_blocked"
    assert answer.search_health_classification["seed_corpus"] == "pass"
    assert answer.search_health_classification["current_blocker"] == "unmeasured"
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in ledger.issue_codes
    assert "layer3_g8_global_seed_health_used_as_current_blocker_health" in (
        ledger.issue_codes
    )


def test_task11_positive_open_question_answers_carry_reducer_provenance() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    ledger = g8.build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=gate,
        repo_root=REPO_ROOT,
    )

    positive_answers = [
        row for row in ledger.answers if row.answer_status == "answered_currently_healthy"
    ]

    assert positive_answers
    for row in positive_answers:
        assert row.produced_by["reducer_id"].startswith("reduce_g8_open_question")
        assert row.produced_by["rule_version"]
        assert row.produced_by["input_hashes"]
        assert row.produced_by["output_hash"].startswith("sha256:")


def test_g8_zero_grounded_response_blocks_domain_ceiling_as_abstention_inertia() -> None:
    signals = g8.Layer3G8NormalizedMetricSignals(
        status="pass",
        signals=(
            _signal("envelope-expansion-rate", "G5", "g5_envelope_expansion_status", "flat"),
            _signal("governance-throughput", "G4", "g4_governance_throughput_status", "pass"),
            _signal(
                "demand-pull-vs-abstention",
                "G6",
                "abstention_or_blocker_rate",
                "abstention_inertia",
            ),
            _signal("adapter-semantic-loss", "G7", "semantic_loss_status", "pass"),
            _signal(
                "search-recall@known-seeds+index-staleness",
                "G7",
                "g1_search_recall_status",
                "pass",
            ),
        ),
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    assert "abstention_inertia" in diagnosis.diagnoses
    assert gate.status == "search_ceiling_repair_required"
    assert gate.domain_ceiling_claim_allowed is False
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in gate.issue_codes
    assert "layer3_g8_abstention_inertia_hidden_as_honesty" in gate.issue_codes


def test_g8_metric_gaming_firewall_blocks_threshold_lowering_and_useful_design_optimization() -> None:
    firewall = g8.build_g8_metric_gaming_firewall(
        metric_changes=[
            {
                "metric_id": "demand-pull-vs-abstention",
                "claimed_improvement": True,
                "change_class": "threshold_lowered",
                "target_metric": "useful_design_rate",
                "source_ref": "test://threshold-lowering",
            }
        ]
    )

    assert firewall.status == "blocked"
    assert "layer3_g8_metric_improved_by_threshold_lowering" in firewall.issue_codes
    assert "layer3_g8_useful_design_rate_optimized" in firewall.issue_codes


def test_g8_warning_lifecycle_requires_owner_and_aging_policy() -> None:
    ledger = g8.build_g8_warning_lifecycle_ledger(
        warnings=[
            {
                "warning_id": "metric-stale",
                "metric_id": "search-recall@known-seeds+index-staleness",
                "severity": "warn",
                "owner": "",
                "deadline": "2026-06-17",
                "aging_policy": "",
                "source_ref": (
                    "repo://architecture/policy_design_case/"
                    "layer3_g1_health_metric_delta.toml"
                ),
            }
        ]
    )

    assert ledger.status == "blocked"
    assert "layer3_g8_warning_owner_missing" in ledger.issue_codes
    assert "layer3_g8_warning_aging_policy_missing" in ledger.issue_codes


def test_g8_default_warning_lifecycle_owns_current_grounding_blocker() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    ledger = g8.build_g8_default_warning_lifecycle_ledger(diagnosis=diagnosis)

    assert ledger.status == "pass"
    assert ledger.issue_codes == ()
    assert len(ledger.warnings) == 1
    warning = ledger.warnings[0]
    assert warning.warning_id == "layer3-g8-current-grounding-blocker"
    assert warning.owner == "team-runtime-quality"
    assert warning.aging_policy == "escalate_if_unchanged_after_next_g_slice"
    assert warning.accepted_deficit_policy == (
        "may_pass_engineering_readiness_but_blocks_domain_ceiling_claim"
    )
    assert warning.metric_id == "envelope-expansion-rate"


def test_g8_d44_rebasing_receipt_uses_freeze_hashes_without_hidden_payload_refs() -> None:
    rule = g8.build_g8_d44_corpus_rebasing_rule(repo_root=REPO_ROOT)
    coverage = g8.build_g8_d44_reannotation_coverage_matrix(
        rule=rule,
        repo_root=REPO_ROOT,
    )
    trigger_ledger = g8.build_g8_d44_rebasing_trigger_ledger(repo_root=REPO_ROOT)
    candidate_set = g8.build_g8_d44_rebasing_candidate_set(repo_root=REPO_ROOT)
    integrity_join = g8.build_g8_sealed_battery_integrity_join(repo_root=REPO_ROOT)
    receipt = g8.build_g8_d44_rebasing_receipt(
        rule=rule,
        candidate_set=candidate_set,
        repo_root=REPO_ROOT,
    )

    serialized = receipt.model_dump_json()
    assert rule.status == "pass"
    assert len(rule.required_reannotation_fields) == len(
        g8.D44_REQUIRED_REANNOTATION_FIELDS
    )
    assert coverage.status == "pass"
    assert {row.field_id for row in coverage.field_rows} == set(
        g8.D44_REQUIRED_REANNOTATION_FIELDS
    )
    assert {row.coverage_status for row in coverage.field_rows} <= {
        "required_for_next_rebase",
        "satisfied_by_existing_s14_record",
    }
    assert any(
        row.coverage_status == "satisfied_by_existing_s14_record"
        for row in coverage.field_rows
    )
    assert any(
        row.coverage_status == "required_for_next_rebase"
        for row in coverage.field_rows
    )
    assert trigger_ledger.status == "pass_no_rebase_due"
    assert (
        trigger_ledger.current_action
        == "no_rebase_required_current_g7_has_no_real_grounded_breadth"
    )
    assert receipt.status == "pass_no_rebase_required"
    assert integrity_join.status == "pass"
    assert integrity_join.hidden_payload_access_status == "not_observed"
    assert receipt.pre_rebase_freeze_hash.startswith("sha256:")
    assert receipt.post_rebase_freeze_hash == receipt.pre_rebase_freeze_hash
    assert "sealed_gold_label_ref" not in serialized
    assert "expected_boundary_disposition" not in serialized
    assert "input_condition_ref" not in serialized
    assert receipt.hidden_payload_access_status == "not_accessed_by_g8"


def test_g8_sealed_battery_join_blocks_mutation_or_floor_lowering() -> None:
    join = g8.build_g8_sealed_battery_integrity_join(
        repo_root=REPO_ROOT,
        rebasing_attempt={
            "post_rebase_freeze_hash": "sha256:" + "2" * 64,
            "pre_rebase_freeze_hash": "sha256:" + "1" * 64,
            "floor_change": "lowered",
            "hidden_payload_ref": "sealed_gold_label_ref://leak",
        },
    )

    assert join.status == "blocked"
    assert "layer3_g8_rebasing_mutates_sealed_battery" in join.issue_codes
    assert "layer3_g8_rebasing_lowers_s14_floor" in join.issue_codes
    assert "layer3_g8_rebasing_leaks_gold_or_hidden_payload" in join.issue_codes


def test_g8_open_question_ledger_answers_every_vision_question_with_current_evidence() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    ledger = g8.build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=gate,
        repo_root=REPO_ROOT,
    )

    assert ledger.status == "blocked"
    assert {row.question_id for row in ledger.answers} == {
        "8.4-waist-altitude",
        "8.4-real-grounding-cost",
        "8.4-demand-pull-strength",
        "8.4-search-recall-freshness",
        "8.4-agent-orchestration-authority-leak",
    }
    answers = {row.question_id: row for row in ledger.answers}
    assert (
        answers["8.4-real-grounding-cost"].answer_status
        == "provisional_insufficient_data"
    )
    assert (
        answers["8.4-demand-pull-strength"].answer_status
        == "provisional_insufficient_data"
    )
    assert (
        answers["8.4-search-recall-freshness"].answer_status
        == "answered_currently_blocked"
    )
    assert answers["8.4-search-recall-freshness"].search_health_classification == {
        "seed_corpus": "fail",
        "pinned_request": "unmeasured",
        "current_blocker": "unmeasured",
        "production_readiness": "blocked_current_blocker_search_unmeasured",
    }
    assert "layer3_g8_blocker_specific_search_diagnostic_missing" in ledger.issue_codes
    assert "recommendation_authority" in ledger.may_not_use_for


def test_g8_open_question_ledger_reflects_current_unchanged_blocker() -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)
    ledger = g8.build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=gate,
        repo_root=REPO_ROOT,
    )

    answers = {row.question_id: row for row in ledger.answers}
    real_grounding_answer = answers["8.4-real-grounding-cost"].current_answer
    demand_answer = answers["8.4-demand-pull-strength"].current_answer

    assert "unchanged_blocker" in real_grounding_answer
    assert "no grounded regional breadth" in real_grounding_answer
    assert "current G5/G7 blockers" in demand_answer
    assert "not an honesty success claim" in demand_answer


def test_g8_open_question_ledger_dereferences_metric_source_refs(
    tmp_path: Path,
) -> None:
    registry = g8.build_g8_health_metric_registry()
    snapshot = g8.build_g8_metric_source_snapshot(REPO_ROOT)
    signals = g8.build_g8_normalized_metric_signals(
        registry=registry,
        source_snapshot=snapshot,
    )
    diagnosis = g8.build_g8_cross_metric_diagnosis(signals=signals, repo_root=REPO_ROOT)
    gate = g8.build_g8_domain_vs_search_ceiling_gate(diagnosis=diagnosis)

    ledger = g8.build_g8_open_question_answer_ledger(
        diagnosis=diagnosis,
        ceiling_gate=gate,
        repo_root=tmp_path,
    )

    assert ledger.status == "blocked"
    assert "layer3_g8_open_question_evidence_ref_unresolved" in set(ledger.issue_codes)
    assert "required_ref_missing_artifact" in set(ledger.issue_codes)


def test_g8_audit_surface_is_expert_machine_and_public_projection_is_reference_only() -> None:
    bundle = g8.build_layer3_g8_bundle(REPO_ROOT)

    assert bundle.audit_surface.status == "blocked"
    assert bundle.audit_surface.surface_audiences == ("EXPERT", "MACHINE")
    assert bundle.audit_surface.domain_vs_search_ceiling_status == (
        "search_ceiling_repair_required"
    )
    assert bundle.audit_surface.metric_trend_report_status == "pass"
    assert bundle.audit_surface.d44_reannotation_coverage_status == "pass"
    assert bundle.audit_surface.sealed_battery_integrity_status == "pass"
    assert bundle.closeout_signal_consumer_gate.status == "pass"
    assert bundle.closeout_signal_consumer_gate.closeout_consumption_status == (
        "readiness_visible_no_authority"
    )
    assert "closeout_authority" in bundle.closeout_signal_consumer_gate.denied_uses
    assert bundle.public_export_projection_refs.public_projection_status == (
        "out_of_scope_reference_only"
    )
    assert "recommendation_authority" in bundle.public_export_projection_refs.denied_uses
    assert bundle.replay_manifest["manifest_id"] == (
        "layer3-g8-health-metric-governance-replay"
    )


def test_g8_conformance_report_covers_required_negatives() -> None:
    bundle = g8.build_layer3_g8_bundle(REPO_ROOT)

    assert bundle.conformance_report.status == "pass"
    required = set(g8.G8_CONFORMANCE_NEGATIVE_EXPECTED_ISSUE_CODES)
    observed = {
        result["negative_id"] for result in bundle.conformance_report.negative_results
    }
    assert observed == required
    assert bundle.conformance_report.missing_negative_ids == ()
    assert not bundle.conformance_report.failing_negative_ids


def _signal(
    metric_id: str,
    slice_id: str,
    raw_key: str,
    value: object,
    *,
    case_id: str | None = None,
    diagnostic_scope: str = "global_metric",
) -> g8.Layer3G8NormalizedMetricSignal:
    status = str(value.get("status")) if isinstance(value, dict) else str(value)
    return g8.Layer3G8NormalizedMetricSignal(
        signal_id=f"test://{metric_id}/{slice_id}/{raw_key}",
        slice_id=slice_id,
        metric_id=metric_id,
        raw_key=raw_key,
        raw_value=value,
        status=status,
        raw_source_ref=f"repo://test#{raw_key}",
        source_digest="sha256:" + "1" * 64,
        freshness_status="fresh_committed",
        authority_boundary_status="pass",
        observed_at="2026-06-10T00:00:00Z",
        case_id=case_id,
        diagnostic_scope=diagnostic_scope,
    )


def _write_task6_case_health_repo(tmp_path: Path) -> Path:
    pdc = tmp_path / "architecture/policy_design_case"
    pdc.mkdir(parents=True)
    (pdc / "layer3_g5_readiness_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.layer3_g5_conversion.v1",
                "g5_conversion_outcome": "typed_blocker -> grounded_abstention",
                "summary": {
                    "g5_conversion_outcome": "typed_blocker -> grounded_abstention"
                },
            }
        ),
        encoding="utf-8",
    )
    (pdc / "layer3_g7_readiness_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "policyos.policy_design_case.layer3_g7_region_widening.v1",
                "g7_region_value_closure_status": "region_closed",
                "g7_region_grounded_case_count": 1,
                "summary": {
                    "g7_region_value_closure_status": "region_closed",
                    "g7_region_grounded_case_count": 1,
                },
            }
        ),
        encoding="utf-8",
    )
    (pdc / "layer3_g5_effective_evidence_independence.json").write_text(
        json.dumps(
            {
                "schema_version": (
                    "policyos.policy_design_case.layer3_g5_effective_evidence_"
                    "independence.v1"
                ),
                "independence_map_payload": {
                    "effective_mass_report": {
                        "independence_status": "singular",
                        "effective_independent_evidence_count": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    return tmp_path
