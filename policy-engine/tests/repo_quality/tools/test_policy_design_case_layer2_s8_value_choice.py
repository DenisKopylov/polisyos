from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality as runtime_quality
from polisyos.pdc import (
    Layer2S2DesignSearchInput,
    Layer2S8ValuePostureInput,
    assert_s2_public_projection_has_value_tradeoff_disclosure,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness
from tools.quality.validation import run_universal_outcome_corpus as w12d

REPO_ROOT = Path(__file__).resolve().parents[3]
S8_MANIFEST = REPO_ROOT / "architecture/policy_design_case/layer2_s8_value_choice_manifest.json"
S8_MANIFEST_PATH = "architecture/policy_design_case/layer2_s8_value_choice_manifest.json"
PDC_DESIGN_SEARCH = REPO_ROOT / "src/polisyos/pdc/_impl/layer2_design_search.py"
S8_VALUE_CHOICE_PRODUCER = REPO_ROOT / "src/polisyos/runtime/quality/design_axes/value_choice_provenance.py"
S8_CELL = "ACTOR.value_choice_provenance"
S8_REQUIRED_ARTIFACTS = {
    "AuthorizedValueSchedule",
    "ObjectiveFunctionProvenanceRecord",
    "ParetoArchive",
    "ValueChoiceProvenanceRecord",
    "ValueTradeoffDisclosureRecord",
    "ValueChoiceIntegrityReport",
}
S8_REQUIRED_FIREWALLS = {"P20", "P22", "P12", "P15", "P26"}
S8_REQUIRED_DENY = {
    "production_claim_authority",
    "production_recommendation",
    "rollout_authority",
    "publication_authority",
    "claim_authority",
    "scalar_welfare_authority",
    "preference_learning_authority",
    "mandate_creation",
    "social_weight_selection_without_authorized_schedule",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "s9_projection_maturity",
    "s10_forecast_support",
    "s11_calibration",
    "s12_envelope_growth",
    "s13_accountability_closure",
    "s14_universality",
}
S8_FALSE_CLEAR_FIELDS = (
    "llm_weight_false_clear_count",
    "corpus_weight_false_clear_count",
    "blocked_mandate_value_choice_false_clear_count",
    "pareto_ranking_without_value_source_false_clear_count",
    "multi_principal_silent_average_false_clear_count",
    "s7_decision_substitution_false_clear_count",
    "shadow_scenario_authority_false_clear_count",
    "missing_arrow_disclosure_false_clear_count",
)
EXPECTED_LIVE_OPEN_CELLS: set[str] = set()
RULE_VERSION_REF = "policyos.layer2.s8.value_choice.v1"


@pytest.fixture(scope="module")
def w12d_s8_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp_path = tmp_path_factory.mktemp("w12d-s8-corpus")
    return w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )


@pytest.fixture(scope="module")
def w12d_s8_summary(w12d_s8_report: dict[str, Any]) -> dict[str, Any]:
    return dict(w12d_s8_report["s8_value_choice_summary"])


def _s8() -> dict[str, Any]:
    return json.loads(S8_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s8_value_choice_manifest"])


def _pinned_case(report: dict[str, Any]) -> dict[str, Any]:
    return next(
        dict(case) for case in report["cases"] if case["case_id"] == "ua-msme-affordable-loans-2022"
    )


def _posture_from_s8_block(block: dict[str, Any]) -> Layer2S8ValuePostureInput:
    return Layer2S8ValuePostureInput.model_validate(
        {field: block[field] for field in Layer2S8ValuePostureInput.model_fields}
    )


def _s2_input() -> Layer2S2DesignSearchInput:
    return Layer2S2DesignSearchInput(
        case_id="ua-msme-affordable-loans-2022",
        intent_ref="repo://architecture/policy_design_case/layer2_first_proving_case.json",
        grammar_ref="repo://src/polisyos/policy_grammar",
        actor_ref="actor://ua/ministry-of-economy",
        domain="ukrainian_msme_credit",
        objective_refs=(
            "objective://credit_program_enrollment",
            "objective://firm_survival",
            "objective://regional_displacement_pressure",
            "objective://credit_access",
            "objective://fiscal_burden_per_beneficiary",
        ),
        construct_refs=(
            "construct://credit_program_enrollment",
            "construct://firm_survival",
            "construct://regional_displacement_pressure",
            "construct://credit_access",
            "construct://fiscal_burden_per_beneficiary",
        ),
        authority_profile_ref="authority_profile.shadow",
        requested_posture="shadow",
        generated_at=datetime(2026, 6, 1, tzinfo=UTC),
        rule_version_ref="policyos.layer2.s2.design_search.v1",
    )


def _authority_boundary() -> dict[str, object]:
    return {
        "authoritative_for": ["value_choice_provenance"],
        "may_not_use_for": sorted(S8_REQUIRED_DENY),
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": [RULE_VERSION_REF],
    }


def test_layer2_s8_manifest_is_valid_and_open_count_is_3() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _s8()

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]
    assert summary["current_open_cell_count"] >= 0
    assert summary["inventory_artifact_count"] >= 18
    assert summary["s8_case_count"] == 13
    assert summary["s8_value_provenance_completeness"] == 1.0
    assert summary["s8_expected_current_open_cell_count"] == 3
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s8_value_choice_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["depends_on"] == ["S2", "S6", "S7"]


def test_layer2_s8_closes_actor_value_choice_provenance_cell() -> None:
    manifest = _s8()
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    cell = payload["cell"]["ACTOR"]["value_choice_provenance"]
    current_open_cells = readiness._open_cell_refs(payload)  # type: ignore[attr-defined]

    assert set(manifest["cells_closed"]) == {S8_CELL}
    assert S8_CELL not in current_open_cells
    assert current_open_cells == EXPECTED_LIVE_OPEN_CELLS
    assert cell["owner_module"] == manifest["producer_module"]
    assert cell["ratchet_state"] == "implemented"
    assert cell["p01_chain"] == "implemented"
    assert cell["firewall"] == "P20_normative_choice_laundering"
    assert cell["gap"] == "none_for_s8_value_choice_provenance_scope"


def test_layer2_s8_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    trace_s8_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S8"
    }

    assert set(_s8()["required_artifacts"]) == S8_REQUIRED_ARTIFACTS
    assert trace_s8_artifacts == S8_REQUIRED_ARTIFACTS
    for artifact_name in S8_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_layer2_s8_firewalls_are_registered_and_floor_is_governed() -> None:
    payloads = _payloads()
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s8_value_provenance"
    )
    registered_patterns = cluster_map._load_failure_pattern_ids(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_FAILURE_PATTERN_REGISTER_PATH,
        [],
    )

    assert set(_s8()["required_firewalls"]) == S8_REQUIRED_FIREWALLS
    assert registered_patterns >= S8_REQUIRED_FIREWALLS
    assert floor["slice"] == "S8"
    assert floor["metric"] == "value_provenance_completeness"
    assert floor["floor_owner"] == "governance-board"
    assert floor["revision_rule"] == "ranked_recommendations_require_authorized_value_source"


def test_layer2_s8_inventory_registration_exists() -> None:
    artifact = _inventory_artifact()

    assert artifact["id"] == "layer2_s8_value_choice_manifest"
    assert artifact["path"] == S8_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s8_value_choice_manifest"
    assert artifact["schema_version"] == (
        "policyos.policy_design_case.layer2_s8_value_choice_manifest.v1"
    )
    assert artifact["owner"] == "governance-board"
    assert artifact["status"] == "active"
    assert artifact["capability_reality_label"] == "implemented"
    assert artifact["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    )
    assert artifact["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )


def test_layer2_s8_inventory_and_manifest_authority_boundaries_match() -> None:
    manifest = _s8()
    artifact = _inventory_artifact()

    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]
    assert set(manifest["may_not_use_for"]) >= S8_REQUIRED_DENY
    assert manifest["producer_module"] == ("src/polisyos/runtime/quality/design_axes/value_choice_provenance.py")


def test_layer2_s8_b_side_consumes_injected_posture_only() -> None:
    b_side = PDC_DESIGN_SEARCH.read_text(encoding="utf-8")
    producer = S8_VALUE_CHOICE_PRODUCER.read_text(encoding="utf-8")

    forbidden_b_side_tokens = {
        "layer2_value_choice",
        "build_authorized_value_schedule",
        "build_pareto_archive",
        "build_value_choice_provenance_record",
        "s8_value_provenance_integrity",
    }
    assert forbidden_b_side_tokens.isdisjoint(b_side)
    assert "runtime.quality.layer2_value_choice" not in b_side
    assert "Layer2S8ValuePostureInput" in b_side
    assert "build_authorized_value_schedule" in producer


def test_layer2_s8_search_ledger_refs_are_persisted_and_replay_visible(
    w12d_s8_report: dict[str, Any],
) -> None:
    pinned = _pinned_case(w12d_s8_report)
    s2 = pinned["s2_design_search"]
    s8 = pinned["s8_value_choice"]
    ledger = s2["search_ledger"]
    handoff_id = s8["handoff_rows"][0]["handoff_id"]

    assert s8["pareto_archive_ref"] in ledger["pareto_archive_refs"]
    assert s8["value_choice_provenance_ref"] in ledger["value_choice_provenance_refs"]
    assert handoff_id in ledger["cluster_handoff_refs"]
    assert handoff_id in {row["handoff_id"] for row in s2["handoff_records"]}
    assert s8["value_choice_provenance_ref"] in s2["design_record"]["ledger_refs"]
    assert s8["value_choice_provenance_ref"] == s2["value_posture"]["value_choice_provenance_ref"]


def test_layer2_s8_public_projection_is_tradeoff_shaped_pull_first(
    w12d_s8_report: dict[str, Any],
) -> None:
    posture = _posture_from_s8_block(_pinned_case(w12d_s8_report)["s8_value_choice"])
    run = run_s2_shadow_design_loop(_s2_input(), value_posture=posture)

    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]

    assert_s2_public_projection_has_value_tradeoff_disclosure(public_projection)
    assert public_projection["value_tradeoff_disclosure_present"] is True
    assert public_projection["value_tradeoff_summary"]
    assert public_projection["frontier_value_source_note"]
    assert "authorized_value_schedule_ref" not in public_projection
    assert "raw_social_weights" not in public_projection
    assert "s8_value_disposition" not in public_projection


def test_layer2_s8_shadow_scenario_schedules_are_not_authority() -> None:
    shadow_schedule = runtime_quality.build_shadow_scenario_value_schedule(
        schedule_ref="pdc://layer2/s8/shadow/readiness-scenario",
        case_id="layer2-s8-repo-quality-probe",
        principal_refs=["principal://repo-quality"],
        social_weight_provenance_refs=["pdc://layer2/s8/repo-quality/social-weight"],
        scenario_label="repo-quality shadow scenario",
        rule_version_ref=RULE_VERSION_REF,
    )

    assert shadow_schedule.disposition == "shadow_scenario_only"
    assert "ranked_recommendation_authority" in shadow_schedule.may_not_use_for
    with pytest.raises(runtime_quality.P20NormativeChoiceError, match="shadow_scenario"):
        runtime_quality.build_pareto_archive(
            archive_id="layer2.s8.repo_quality.shadow",
            archive_ref="pdc://layer2/s8/repo-quality/shadow-pareto",
            case_id="layer2-s8-repo-quality-probe",
            ranking_mode="ranked_with_authorized_values",
            archive_status="probe",
            value_schedule_ref=shadow_schedule.schedule_ref,
            authority_boundary=_authority_boundary(),
            rule_version_ref=RULE_VERSION_REF,
        )


def test_layer2_s8_arrow_disclosure_rows_are_required_for_multi_principal_conflict() -> None:
    with pytest.raises(runtime_quality.P20NormativeChoiceError, match="affected groups"):
        runtime_quality.build_value_choice_provenance_record(
            record_id="layer2.s8.repo_quality.multi_principal",
            record_ref="pdc://layer2/s8/repo-quality/multi-principal",
            case_id="layer2-s8-repo-quality-probe",
            selected_alternative_ref="policy://repo-quality/alternative",
            objective_provenance_ref="pdc://layer2/s8/repo-quality/objective",
            value_schedule_ref="pdc://layer2/s8/repo-quality/authorized-schedule",
            pareto_archive_ref="pdc://layer2/s8/repo-quality/pareto",
            conflict_rows=[{"principal_ref": "principal://repo-quality"}],
            disposition="authorized",
            integrity_status="pass",
            authority_boundary=_authority_boundary(),
            rule_version_ref=RULE_VERSION_REF,
        )


def test_layer2_s8_negative_controls_fail_closed(w12d_s8_summary: dict[str, Any]) -> None:
    negative_results = w12d_s8_summary["negative_control_results"]

    for field in S8_FALSE_CLEAR_FIELDS:
        assert w12d_s8_summary[field] == 0
    assert set(negative_results) >= {
        "llm_social_weight_probe",
        "blocked_mandate_value_choice_probe",
        "pareto_ranking_without_value_source_probe",
        "multi_principal_conflict_probe",
        "s7_human_decision_substitution_probe",
        "shadow_scenario_authority_spoof_probe",
        "missing_arrow_disclosure_probe",
    }
    assert all(not row["false_clear"] for row in negative_results.values())


def test_layer2_s8_manifest_metrics_match_generated_corpus_summary(
    w12d_s8_summary: dict[str, Any],
) -> None:
    manifest = _s8()

    for field in (
        "case_count",
        "value_provenance_completeness",
        "authorized_value_schedule_recall",
        "pareto_archive_coverage",
        "tradeoff_disclosure_coverage",
        *S8_FALSE_CLEAR_FIELDS,
    ):
        assert manifest[field] == w12d_s8_summary[field]


def test_layer2_s8_corpus_summary_records_floor_and_integrity(
    w12d_s8_summary: dict[str, Any],
) -> None:
    manifest = _s8()

    assert w12d_s8_summary["schema_version"] == (
        "policyos.policy_design_case.layer2_s8.value_choice_corpus_summary.v1"
    )
    assert manifest["floor_id"] == "s8_value_provenance"
    assert manifest["floor_metric"] == "value_provenance_completeness"
    assert w12d_s8_summary["case_count"] == 13
    assert w12d_s8_summary["value_provenance_completeness"] == 1.0
    assert w12d_s8_summary["authorized_value_schedule_recall"] == 1.0
    assert w12d_s8_summary["pareto_archive_coverage"] == 1.0
    assert w12d_s8_summary["tradeoff_disclosure_coverage"] == 1.0
    assert len(w12d_s8_summary["negative_control_results"]) >= 7
    assert set(w12d_s8_summary["disposition_counts"]) >= {
        "authorized",
        "advisory_only",
        "contested_multi_principal",
        "shadow_scenario_only",
    }
    assert set(w12d_s8_summary["coverage_label_counts"]) >= {
        "authorized_schedule_present",
        "multi_principal_conflict",
        "shadow_scenario_value_schedule",
        "llm_proposed_weights",
    }


def test_layer2_s8_does_not_mark_s13_or_s14_cells_implemented() -> None:
    payloads = _payloads()
    cluster_payload = payloads["cluster_map"]
    current_open_cells = readiness._open_cell_refs(cluster_payload)  # type: ignore[attr-defined]
    later_cells = {
        str(row["cell_ref"])
        for row in payloads["slice_cell_matrix"]["assignment"]
        if row.get("slice") in {"S13", "S14"}
    }

    assert current_open_cells == EXPECTED_LIVE_OPEN_CELLS
    assert later_cells <= current_open_cells
    for cell_ref in later_cells:
        cluster, axis = cell_ref.split(".", maxsplit=1)
        cell = cluster_payload["cell"][cluster][axis]
        assert cell["ratchet_state"] != "implemented", cell_ref
        assert cell["p01_chain"] != "implemented", cell_ref
