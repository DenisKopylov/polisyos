from __future__ import annotations

import json
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/layer3/g0"


def _g0() -> Any:
    return import_module("polisyos.runtime.quality.layer3_grounding_inventory")


def _fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _issue_codes(report: Any) -> set[str]:
    payload = report.model_dump() if hasattr(report, "model_dump") else report
    return {str(issue["code"]) for issue in payload["issues"]}


def _authority_boundary() -> dict[str, object]:
    return {
        "authoritative_for": ["layer3_g0_pre_adapter_triage"],
        "may_not_use_for": ["adapter_admission", "publication_authority"],
        "source_authority": "deterministic_producer",
        "posture": "shadow",
        "rule_version_refs": ["policyos.layer3.g0.grounding_subordination.v1"],
    }


def _triage_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "capability_id": "scenario_family_authority_selector",
        "disposition": "quarantine",
        "rationale": "Scenario-family selectors are projection-only and cannot be adapter authority.",
        "evidence_refs": [
            "repo://src/polisyos/runtime/quality/scenario_evidence_contract.py#L349",
            "repo://architecture/shims.toml#L176",
        ],
        "missing_capability_labels": ["verification_missing"],
        "quarantine_ref": "quarantine://layer3-g0/scenario-family-authority-selector",
        "adapter_admissibility": "blocked",
        "authority_boundary": _authority_boundary(),
    }
    payload.update(overrides)
    return payload


def _quarantine_entry() -> dict[str, object]:
    return {
        "target_id": "scenario_family_authority_selector",
        "target_kind": "source_touchpoint",
        "reason": "Projection-only scenario-family evidence cannot become source authority.",
        "pattern_ids": ["P05", "P06", "P15"],
        "blocker_codes": ["layer3_g0_quarantined_source_admitted"],
        "enforcement_surface": "adapter_admission_registry",
        "release_condition": "human-governed adapter evidence and source-truth path are required",
    }


def _adapter_admission_record(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "adapter_id": "scenario-family-shadow-adapter",
        "source_ids": ["scenario_family_authority_selector"],
        "port_ids": ["evidence.source_quality"],
        "maturity": "fail_closed",
        "promotion_state": "shadow",
        "conformance_status": "not_run_pre_adapter",
        "quarantine_check": "blocked",
        "admission_state": "blocked",
        "admitted": False,
        "adapter_contract_path_refs": [],
        "source_touchpoint_refs": ["touchpoint://runtime-quality/scenario-family"],
    }
    payload.update(overrides)
    return payload


def test_capability_triage_record_rejects_unknown_disposition_and_extra_fields() -> None:
    g0 = _g0()

    with pytest.raises(ValidationError, match="disposition"):
        g0.CapabilityTriageRecord.model_validate(
            _triage_payload(disposition="candidate_maybe")
        )

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        g0.CapabilityTriageRecord.model_validate(
            _triage_payload(untracked_status="hidden_contract_only")
        )


def test_quarantine_registry_blocks_adapter_admission_for_scenario_family_authority() -> None:
    g0 = _g0()
    quarantines = [g0.QuarantineRegistryEntry.model_validate(_quarantine_entry())]
    admitted = g0.AdapterAdmissionRecord.model_validate(
        _adapter_admission_record(
            quarantine_check="not_blocked",
            admission_state="admitted",
            admitted=True,
        )
    )

    report = g0.validate_adapter_admission_registry(
        admission_records=[admitted],
        quarantine_registry=quarantines,
    )

    assert report.status == "fail"
    assert "layer3_g0_quarantined_source_admitted" in _issue_codes(report)


def test_port_map_is_derived_from_cluster_map_without_new_ports() -> None:
    g0 = _g0()
    cluster_map_path = REPO_ROOT / "architecture/policy_design_case/cluster_ownership_map.toml"

    port_map = g0.build_port_map_from_cluster_map(cluster_map_path)
    assert len(port_map.ports) == 27
    assert port_map.summary["port_count"] == 27
    assert all("cluster_ownership_map.toml" in port.source_line_ref for port in port_map.ports)

    mutated_payload = port_map.model_dump(mode="json")
    mutated_payload["ports"].append(
        {
            "port_id": "layer3.synthetic_new_port",
            "cluster": "LAYER3",
            "facet": "synthetic",
            "publishes": [],
            "consumes": [],
            "source_line_ref": "test://not-derived",
        }
    )
    report = g0.validate_port_map(
        persisted=g0.PortMap.model_validate(mutated_payload),
        cluster_map_path=cluster_map_path,
    )

    assert report.status == "fail"
    assert "layer3_g0_port_map_drift" in _issue_codes(report)


def test_portless_capability_requires_governed_waist_change_open_question() -> None:
    g0 = _g0()
    payload = _fixture("malformed_portless_capability_missing_open_question.json")["payload"]

    report = g0.validate_capability_inventory_payload(payload)

    assert report.status == "fail"
    assert "layer3_g0_portless_capability_missing_open_question" in _issue_codes(report)


def test_data_asset_port_requires_lineage_rights_freshness_fitness_and_contamination_check() -> None:
    g0 = _g0()
    payload = _fixture("malformed_data_asset_missing_evidence.json")["payload"][
        "data_asset_ports"
    ][0]

    with pytest.raises(
        ValidationError,
        match=r"lineage_ref|rights_ref|freshness_ref|fitness_ref|contamination_check_ref",
    ):
        g0.DataAssetPort.model_validate(payload)


def test_adapter_admission_cannot_exceed_conformance_maturity() -> None:
    g0 = _g0()
    overclaim = g0.AdapterAdmissionRecord.model_validate(
        _adapter_admission_record(
            maturity="calibrated",
            conformance_status="not_run_pre_adapter",
            promotion_state="governed_promoted",
            admission_state="candidate_shadow_only",
        )
    )

    report = g0.validate_adapter_admission_registry(
        admission_records=[overclaim],
        quarantine_registry=[],
    )

    assert report.status == "fail"
    assert "layer3_g0_adapter_maturity_overclaim" in _issue_codes(report)


def test_inventory_requires_asset_level_data_and_processing_transform_entries() -> None:
    g0 = _g0()
    payload = {
        "required_roots": [
            {
                "root_id": "production_data",
                "path": "production_data",
                "discovered_assets": ["production_data/manifest.json"],
                "discovered_transforms": ["tools/ops_runners/ukraine_data/summarize.py"],
            }
        ],
        "data_assets": [
            {
                "asset_id": "production_data",
                "data_kind": "data_asset",
                "path": "production_data",
                "owning_root": "production_data",
                "owner_evidence_ref": "repo://production_data/manifest.json",
                "lineage_evidence_ref": "repo://production_data/manifest.json",
                "rights_evidence_ref": "repo://production_data/manifest.json",
                "freshness_evidence_ref": "repo://production_data/manifest.json",
                "fitness_evidence_ref": "repo://production_data/manifest.json",
                "contamination_check_ref": "repo://production_data/manifest.json",
            }
        ],
        "processing_transforms": [],
    }

    report = g0.validate_data_asset_inventory_payload(payload)

    assert report.status == "fail"
    assert "layer3_g0_data_asset_unclassified" in _issue_codes(report)
    assert "layer3_g0_processing_transform_unclassified" in _issue_codes(report)


def test_runtime_touchpoint_requires_registration_and_blocks_admission_without_contract() -> None:
    g0 = _g0()
    missing_registration = _fixture("malformed_touchpoint_missing_registration.json")["payload"]
    admission_without_contract = _fixture(
        "malformed_touchpoint_admission_without_contract.json"
    )["payload"]

    missing_report = g0.validate_runtime_quality_touchpoint_inventory(
        missing_registration
    )
    admission_report = g0.validate_runtime_quality_touchpoint_inventory(
        admission_without_contract
    )

    assert missing_report.status == "fail"
    assert "layer3_g0_source_touchpoint_registration_missing" in _issue_codes(
        missing_report
    )
    assert admission_report.status == "fail"
    assert "layer3_g0_touchpoint_admission_without_contract" in _issue_codes(
        admission_report
    )


def test_runtime_touchpoint_scan_includes_local_imports_in_producer_pipeline() -> None:
    g0 = _g0()

    touchpoints = g0.build_runtime_quality_touchpoint_inventory(REPO_ROOT)
    producer_pipeline_roots = {
        touchpoint.import_root
        for touchpoint in touchpoints
        if touchpoint.file == "src/polisyos/runtime/quality/producer_pipeline.py"
    }

    assert len(touchpoints) == 22
    assert g0.SOURCE_TOUCHPOINT_SCAN_MODE == "ast_top_level_and_local_imports"
    assert producer_pipeline_roots >= {
        "fabric",
        "lex",
        "foundry",
        "scholar",
        "participation_requirement",
        "scholar_requirement",
    }


def test_g0_does_not_mutate_source_truth_lattice_adapter_paths() -> None:
    g0 = _g0()
    lattice_path = REPO_ROOT / "architecture/production_quality/source_truth_lattice.toml"

    adapter_paths = g0.load_source_truth_adapter_paths(lattice_path)
    assert len(adapter_paths) == 9

    report = g0.validate_source_truth_lattice_adapter_paths(
        adapter_paths=[*adapter_paths, "layer3_g0_shadow_adapter"],
        baseline_adapter_paths=adapter_paths,
    )

    assert report.status == "fail"
    assert "layer3_g0_source_truth_lattice_mutated_in_g0" in _issue_codes(report)


def test_status_composition_blocks_quarantine_and_premature_admission() -> None:
    g0 = _g0()

    matrix = g0.build_status_composition_matrix()
    report = g0.validate_status_composition_matrix(
        matrix,
        cases=[
            {
                "case_id": "quarantine_dominates_admission",
                "quarantine_check": "blocked",
                "admission_state": "admitted",
                "expected_issue_code": "layer3_g0_quarantined_source_admitted",
            },
            {
                "case_id": "promotion_before_g4",
                "conformance_status": "not_run_pre_adapter",
                "promotion_state": "governed_promoted",
                "expected_issue_code": "layer3_g0_status_composition_missing",
            },
        ],
    )

    assert len(matrix.rules) == 4
    assert report.status == "fail"
    assert "layer3_g0_quarantined_source_admitted" in _issue_codes(report)
    assert "layer3_g0_status_composition_missing" in _issue_codes(report)


def test_import_policy_constitution_conflict_must_be_recorded_as_followup() -> None:
    g0 = _g0()
    payload = {
        "adr_id": "0175",
        "adr_status": "Proposed",
        "import_policy_constitution_conflict_recorded": False,
        "policy_toml_pdc_allowlist_narrowing_followup_recorded": False,
        "registry_crosswalk_clarification_recorded": True,
        "open_questions_mode": "tracked_empirically_open",
        "human_acceptance_ref": None,
    }

    report = g0.validate_governance_followups(payload)

    assert report.status == "fail"
    assert "layer3_g0_import_policy_constitution_conflict_unrecorded" in _issue_codes(
        report
    )


def test_registry_crosswalk_clarifies_preservation_vs_admission_registry() -> None:
    g0 = _g0()
    payload = {
        "adr_id": "0175",
        "adr_status": "Proposed",
        "import_policy_constitution_conflict_recorded": True,
        "policy_toml_pdc_allowlist_narrowing_followup_recorded": True,
        "registry_crosswalk_clarification_recorded": False,
        "open_questions_mode": "tracked_empirically_open",
        "human_acceptance_ref": None,
    }

    report = g0.validate_governance_followups(payload)

    assert report.status == "fail"
    assert "layer3_g0_registry_conflation_unrecorded" in _issue_codes(report)


def test_adr_acceptance_requires_human_principal_ref() -> None:
    g0 = _g0()
    payload = _fixture("malformed_adr_missing_human_acceptance.json")["payload"]

    report = g0.validate_layer3_g0_adr(payload)

    assert report.status == "fail"
    assert "layer3_g0_adr_human_acceptance_missing" in _issue_codes(report)


def test_first_vertical_case_keeps_corpus_case_id_and_construct_bundle_id_distinct() -> None:
    g0 = _g0()
    record = g0.FirstVerticalCaseRecord.model_validate(
        {
            "case_ref": "architecture/policy_design_case/layer3_first_vertical_case.json",
            "first_vertical_corpus_case_id": "ua-msme-affordable-loans-2022",
            "first_vertical_construct_bundle_id": "ukrainian_msme_credit_constructs",
            "authority_posture": "not_attempted_g0_pre_adapter",
        }
    )

    assert record.first_vertical_corpus_case_id == "ua-msme-affordable-loans-2022"
    assert record.first_vertical_construct_bundle_id == "ukrainian_msme_credit_constructs"

    report = g0.validate_first_vertical_case_record(
        {
            "case_ref": "architecture/policy_design_case/layer3_first_vertical_case.json",
            "first_vertical_corpus_case_id": "ukrainian_msme_credit_constructs",
            "first_vertical_construct_bundle_id": "ukrainian_msme_credit_constructs",
            "authority_posture": "not_attempted_g0_pre_adapter",
        }
    )

    assert report.status == "fail"
    assert "layer3_g0_first_case_id_mismatch" in _issue_codes(report)
