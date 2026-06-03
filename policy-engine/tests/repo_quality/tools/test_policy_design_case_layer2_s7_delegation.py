from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

import polisyos.runtime.quality as runtime_quality
from polisyos.pdc import (
    Layer2S2DesignSearchInput,
    Layer2S7DelegationPostureInput,
    assert_s2_public_projection_has_delegation_request,
    project_s2_design_search,
    run_s2_shadow_design_loop,
)
from tools.quality.validation import check_policy_design_case_cluster_ownership_map as cluster_map
from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness
from tools.quality.validation import run_universal_outcome_corpus as w12d

REPO_ROOT = Path(__file__).resolve().parents[3]
S7_MANIFEST = REPO_ROOT / "architecture/policy_design_case/layer2_s7_delegation_manifest.json"
S7_MANIFEST_PATH = "architecture/policy_design_case/layer2_s7_delegation_manifest.json"
S7_CASE_SIGNALS = REPO_ROOT / "tests/fixtures/layer2/s7/s7_delegation_case_signals.json"
S7_EXPERT_LABELS = REPO_ROOT / "tests/fixtures/layer2/s7/s7_delegation_expert_labels.json"
S7_WORKFLOW_ONLY_PROBE = (
    REPO_ROOT / "tests/fixtures/layer2/s7/workflow_only_delegation_summary_probe.json"
)
PDC_DESIGN_SEARCH = REPO_ROOT / "src/polisyos/pdc/_impl/layer2_design_search.py"
S7_DELEGATION_PRODUCER = REPO_ROOT / "src/polisyos/runtime/quality/layer2_delegation.py"
S7_CELL = "CROSS_CUTTING.scientist_orchestration"
S7_REQUIRED_ARTIFACTS = {
    "DelegationContract",
    "DecisionRightsMatrix",
    "HumanDecisionRequest",
    "HumanDecisionRecord",
}
S7_REQUIRED_FIREWALLS = {"P26", "P20", "P22", "P12", "P15"}
S7_REQUIRED_DENY = {
    "production_claim_authority",
    "rollout_authority",
    "publication_authority",
    "value_choice_authority",
    "social_weight_selection",
    "outcome_prediction_authority",
    "forecast_calibration_authority",
    "oversight_effectiveness_claim",
    "attention_ledger_authority",
    "resource_allocation_authority",
    "human_approval_without_decision_record",
    "ai_self_authorization",
    "delegated_autonomy_without_mandate",
    "s13_accountability_closure",
}
EXPECTED_LIVE_OPEN_CELLS: set[str] = set()


@pytest.fixture(scope="module")
def w12d_s7_report(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    tmp_path = tmp_path_factory.mktemp("w12d-s7-corpus")
    return w12d.run_w12d_universal_outcome_corpus(
        repo_root=REPO_ROOT,
        corpus_path=REPO_ROOT / "tests/fixtures/universal-corpus",
        graph_output_dir=tmp_path / "graphs",
        hypothesis_ledger_output_dir=tmp_path / "ledgers",
        mode="real_producer",
    )


@pytest.fixture(scope="module")
def w12d_s7_summary(w12d_s7_report: dict[str, Any]) -> dict[str, Any]:
    return dict(w12d_s7_report["s7_delegation_summary"])


def _s7() -> dict[str, Any]:
    return json.loads(S7_MANIFEST.read_text(encoding="utf-8"))


def _payloads() -> dict[str, Any]:
    return readiness.load_layer2_readiness_payloads(REPO_ROOT)


def _inventory_artifact() -> dict[str, Any]:
    artifacts = {
        str(artifact["id"]): artifact
        for artifact in _payloads()["inventory"]["artifacts"]
        if isinstance(artifact, dict)
    }
    return dict(artifacts["layer2_s7_delegation_manifest"])


def _pinned_case(report: dict[str, Any]) -> dict[str, Any]:
    return next(
        dict(case) for case in report["cases"] if case["case_id"] == "ua-msme-affordable-loans-2022"
    )


def _posture_from_s7_block(block: dict[str, Any]) -> Layer2S7DelegationPostureInput:
    return Layer2S7DelegationPostureInput.model_validate(
        {field: block[field] for field in Layer2S7DelegationPostureInput.model_fields}
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


def test_layer2_s7_manifest_is_valid_and_live_open_count_is_3() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)
    manifest = _s7()

    assert validation["status"] == "pass", validation["issues"]
    summary = validation["summary"]
    assert summary["current_open_cell_count"] >= 0
    assert summary["inventory_artifact_count"] >= 18
    assert summary["s7_case_count"] == 13
    assert summary["s7_delegation_precision"] == 1.0
    assert summary["s7_delegation_recall"] == 1.0
    assert summary["s7_responsibility_integrity_pass_rate"] == 1.0
    assert summary["s7_expected_current_open_cell_count"] == 4
    assert manifest["schema_version"] == (
        "policyos.policy_design_case.layer2_s7_delegation_manifest.v1"
    )
    assert manifest["status"] == "active"
    assert manifest["depends_on"] == ["S2", "S6"]


def test_layer2_s7_closes_scientist_orchestration_with_delegation_scope() -> None:
    manifest = _s7()
    payload = cluster_map.load_cluster_ownership_map(REPO_ROOT)
    cell = payload["cell"]["CROSS_CUTTING"]["scientist_orchestration"]
    current_open_cells = readiness._open_cell_refs(payload)  # type: ignore[attr-defined]

    assert set(manifest["cells_closed"]) == {S7_CELL}
    assert S7_CELL not in current_open_cells
    assert cell["owner_module"] == manifest["producer_module"]
    assert cell["ratchet_state"] == "implemented"
    assert cell["p01_chain"] == "implemented"
    assert cell["firewall"] == "P26_responsibility_integrity_laundering"
    assert cell["gap"] == "none_for_s7_delegation_scope"
    assert "ACTOR.mandate_legitimacy" in cell["consumes"]
    assert "workflow-only summaries fail P12" in cell["action"]


def test_layer2_s7_required_artifacts_are_traceable_and_exported() -> None:
    payloads = _payloads()
    trace_s7_artifacts = {
        str(row["name"])
        for row in payloads["artifact_traceability"]["artifact"]
        if row.get("slice") == "S7"
    }

    assert set(_s7()["required_artifacts"]) == S7_REQUIRED_ARTIFACTS
    assert trace_s7_artifacts == S7_REQUIRED_ARTIFACTS
    for artifact_name in S7_REQUIRED_ARTIFACTS:
        artifact = getattr(runtime_quality, artifact_name)
        assert artifact.model_config.get("extra") == "forbid", artifact_name


def test_layer2_s7_firewalls_are_registered_and_floor_is_governed() -> None:
    payloads = _payloads()
    floor = next(
        row
        for row in payloads["floor_governance"]["floor"]
        if row.get("floor_id") == "s7_delegation_integrity"
    )
    registered_patterns = cluster_map._load_failure_pattern_ids(  # type: ignore[attr-defined]
        REPO_ROOT / cluster_map.DEFAULT_FAILURE_PATTERN_REGISTER_PATH,
        [],
    )

    assert set(_s7()["required_firewalls"]) == S7_REQUIRED_FIREWALLS
    assert registered_patterns >= S7_REQUIRED_FIREWALLS
    assert floor["slice"] == "S7"
    assert floor["metric"] == "delegation_precision_recall_and_responsibility_integrity"
    assert floor["floor_owner"] == "governance-board"
    assert floor["revision_rule"] == "decision_rights_matrix_change_requires_governance_owner"


def test_layer2_s7_inventory_registration_exists() -> None:
    artifact = _inventory_artifact()

    assert artifact["id"] == "layer2_s7_delegation_manifest"
    assert artifact["path"] == S7_MANIFEST_PATH
    assert artifact["kind"] == "layer2_s7_delegation_manifest"
    assert artifact["schema_version"] == (
        "policyos.policy_design_case.layer2_s7_delegation_manifest.v1"
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


def test_layer2_s7_inventory_and_manifest_authority_boundaries_match() -> None:
    manifest = _s7()
    artifact = _inventory_artifact()

    assert artifact["authority_scope"] == manifest["authority_scope"]
    assert artifact["may_not_use_for"] == manifest["may_not_use_for"]
    assert set(manifest["may_not_use_for"]) >= S7_REQUIRED_DENY
    assert manifest["producer_module"] == "src/polisyos/runtime/quality/layer2_delegation.py"
    assert manifest["consumer_module"] == "src/polisyos/pdc/_impl/layer2_design_search.py"


def test_layer2_s7_b_side_consumes_injected_posture_only() -> None:
    b_side = PDC_DESIGN_SEARCH.read_text(encoding="utf-8")
    producer = S7_DELEGATION_PRODUCER.read_text(encoding="utf-8")

    forbidden_b_side_tokens = {
        "layer2_delegation",
        "build_decision_rights_matrix",
        "record_human_decision",
        "evaluate_delegation_for_case",
    }
    forbidden_review_imports = {
        "runtime.quality.approval",
        "runtime.quality.human_review",
        "scientist.governance.human_review",
    }
    assert forbidden_b_side_tokens.isdisjoint(b_side)
    assert forbidden_review_imports.isdisjoint(b_side)
    assert forbidden_review_imports.isdisjoint(producer)
    assert "Layer2S7DelegationPostureInput" in b_side


def test_layer2_s7_search_ledger_refs_are_persisted_and_replay_visible(
    w12d_s7_report: dict[str, Any],
) -> None:
    pinned = _pinned_case(w12d_s7_report)
    s2 = pinned["s2_design_search"]
    s7 = pinned["s7_delegation"]
    ledger = s2["search_ledger"]
    handoff_id = s7["handoff_rows"][0]["handoff_id"]

    assert s7["human_decision_request_ref"] in ledger["delegation_request_refs"]
    assert handoff_id in ledger["cluster_handoff_refs"]
    assert handoff_id in {row["handoff_id"] for row in s2["handoff_records"]}
    if s7["human_decision_record_ref"] is not None:
        assert s7["human_decision_record_ref"] in ledger["delegation_record_refs"]
    assert s7["human_decision_request_ref"] in s2["design_record"]["ledger_refs"]
    assert s7["human_decision_request_ref"] in pinned["closeout_visible_refs"]["delegation_refs"]


def test_layer2_s7_public_projection_is_decision_shaped_pull_first(
    w12d_s7_report: dict[str, Any],
) -> None:
    posture = _posture_from_s7_block(_pinned_case(w12d_s7_report)["s7_delegation"])
    posture = posture.model_copy(update={"disposition": "request_human_decision"})
    run = run_s2_shadow_design_loop(_s2_input(), delegation_posture=posture)

    public_projection = project_s2_design_search(run, audiences=("PUBLIC",))["PUBLIC"]

    assert_s2_public_projection_has_delegation_request(public_projection)
    assert public_projection["human_decision_needed"] is True
    assert public_projection["accountable_role"] == posture.required_role
    assert public_projection["available_decision_actions"] == posture.available_actions
    assert public_projection["delegation_limitation"] == posture.limitation_summary
    assert "s7_disposition" not in public_projection


def test_layer2_s7_negative_controls_fail_closed(
    w12d_s7_summary: dict[str, Any],
) -> None:
    negative_results = w12d_s7_summary["negative_control_results"]

    assert w12d_s7_summary["oversight_theater_false_clear_count"] == 0
    assert w12d_s7_summary["wrong_role_false_clear_count"] == 0
    assert w12d_s7_summary["ai_first_high_stakes_false_clear_count"] == 0
    assert w12d_s7_summary["mandate_absent_delegation_false_clear_count"] == 0
    assert set(negative_results) >= {
        "oversight_theater_probe",
        "wrong_role_approval_probe",
        "ai_first_high_stakes_probe",
        "mandate_absent_delegation_probe",
    }
    assert all(not row["false_clear"] for row in negative_results.values())


def test_layer2_s7_workflow_only_summary_cannot_close_p12(
    w12d_s7_summary: dict[str, Any],
) -> None:
    probe = json.loads(S7_WORKFLOW_ONLY_PROBE.read_text(encoding="utf-8"))
    result = w12d_s7_summary["negative_control_results"]["workflow_only_delegation_summary_probe"]

    assert probe["expected_failure_pattern"] == "P12"
    assert probe["typed_producer_artifact_refs"] == []
    assert probe["cluster_handoff_records"] == []
    assert w12d_s7_summary["workflow_only_summary_false_clear_count"] == 0
    assert result["failure_pattern"] == "P12"
    assert result["predicted_disposition"] == "workflow_only_summary_rejected"
    assert result["false_clear"] is False


def test_layer2_s7_manifest_metrics_match_generated_corpus_summary(
    w12d_s7_summary: dict[str, Any],
) -> None:
    manifest = _s7()

    for field in (
        "case_count",
        "delegation_precision",
        "delegation_recall",
        "responsibility_integrity_pass_rate",
        "oversight_theater_false_clear_count",
        "wrong_role_false_clear_count",
        "workflow_only_summary_false_clear_count",
    ):
        assert manifest[field] == w12d_s7_summary[field]


def test_layer2_s7_corpus_summary_records_precision_recall_and_integrity(
    w12d_s7_summary: dict[str, Any],
) -> None:
    assert w12d_s7_summary["schema_version"] == (
        "policyos.policy_design_case.layer2_s7.delegation_corpus_summary.v1"
    )
    assert w12d_s7_summary["case_count"] == 13
    assert w12d_s7_summary["delegation_precision"] == 1.0
    assert w12d_s7_summary["delegation_recall"] == 1.0
    assert w12d_s7_summary["responsibility_integrity_pass_rate"] == 1.0
    assert len(w12d_s7_summary["per_case_delegation_table"]) == 13
    assert w12d_s7_summary["request_emitted_count"] >= 7
    assert w12d_s7_summary["no_interrupt_count"] >= 3
    assert w12d_s7_summary["valid_human_decision_record_count"] >= 6
    assert w12d_s7_summary["governed_pilot_eligible_count"] >= 1
    assert w12d_s7_summary["budget_or_legal_use_request_count"] >= 1
    assert w12d_s7_summary["acquisition_request_count"] >= 1
    assert w12d_s7_summary["final_choice_request_count"] >= 1
    assert set(w12d_s7_summary["decision_need_reason_counts"]) >= {
        "high_stakes",
        "value_laden",
        "out_of_envelope",
        "mandate_limited",
        "budget_required",
        "acquisition_required",
        "final_choice",
    }
    assert set(w12d_s7_summary["interaction_mode_counts"]) >= {
        "request_driven",
        "ai_follow",
    }
    assert set(w12d_s7_summary["disposition_counts"]) >= {
        "request_human_decision",
        "recorded_valid_decision",
        "no_interrupt",
    }


def test_layer2_s7_does_not_mark_s13_or_s14_cells_implemented() -> None:
    payloads = _payloads()
    cluster_payload = payloads["cluster_map"]
    current_open_cells = readiness._open_cell_refs(cluster_payload)  # type: ignore[attr-defined]
    future_cells = {
        str(row["cell_ref"])
        for row in payloads["slice_cell_matrix"]["assignment"]
        if row.get("slice") in {"S13", "S14"}
    }

    assert current_open_cells == EXPECTED_LIVE_OPEN_CELLS
    assert future_cells <= current_open_cells
    for cell_ref in future_cells:
        cluster, axis = cell_ref.split(".", maxsplit=1)
        cell = cluster_payload["cell"][cluster][axis]
        assert cell["ratchet_state"] != "implemented", cell_ref
        assert cell["p01_chain"] != "implemented", cell_ref
