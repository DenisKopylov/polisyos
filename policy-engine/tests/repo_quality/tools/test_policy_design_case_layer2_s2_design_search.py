from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from polisyos.pdc import Layer2S2DesignSearchInputError
from tools.quality.validation import (
    check_policy_design_case_layer2_s2_design_search as s2_validator,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = REPO_ROOT / "architecture/policy_design_case/layer2_s2_design_search_manifest.json"


def _manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_s2_manifest_declares_closed_cells_and_shadow_scope() -> None:
    manifest = _manifest()

    assert manifest["slice"] == "S2"
    assert manifest["cells_closed"] == [
        "INTERVENTION.design_grammar",
        "INTERVENTION.design_candidate",
    ]
    assert manifest["layer_contributions"][0]["cell_ref"] == (
        "CROSS_CUTTING.scientist_orchestration"
    )
    assert manifest["layer_contributions"][0]["closure_owner_slice"] == "S7"
    assert manifest["open_cell_count_baseline"] == 17
    assert manifest["expected_current_open_cell_count"] == 15
    assert manifest["promotion"] == "shadow_only"
    assert {row["floor_id"] for row in manifest["floors"]} == {
        "s2_counterexample_conversion",
    }
    assert {row["check_id"] for row in manifest["shadow_adequacy_checks"]} == {
        "s2_shadow_grammar_diversity",
    }
    assert manifest["required_governance_decision_classes"] == ["a_spec_gap"]
    assert manifest["required_voi_sites"] == ["s2_refinement_policy"]
    assert "production_recommendation" in manifest["may_not_use_for"]


def test_s2_validator_reports_full_loop_and_floor() -> None:
    summary = s2_validator.validate_s2_design_search(repo_root=REPO_ROOT)

    assert summary["status"] == "pass"
    assert summary["slice"] == "S2"
    assert summary["first_proving_case_id"] == "ua-msme-affordable-loans-2022"
    assert summary["current_open_cell_count"] == 15
    assert summary["expected_current_open_cell_count"] == 15
    assert summary["cells_closed"] == [
        "INTERVENTION.design_grammar",
        "INTERVENTION.design_candidate",
    ]
    assert summary["counterexample_conversion_rate"] == 1.0
    assert summary["grammar_diversity_minimum"] == 3
    assert summary["governance_decision_classes_verified"] == ["a_spec_gap"]
    assert summary["voi_sites_verified"] == ["s2_refinement_policy"]
    assert summary["acquisition_branch_state"] == "bridge_missing"
    assert summary["projection_audiences_verified"] == ["MACHINE", "REVIEWER"]
    assert summary["canonical_route_status"] == "pass"


def test_s2_validator_rejects_llm_only_candidate_negative_control() -> None:
    with pytest.raises(Layer2S2DesignSearchInputError):
        s2_validator.validate_llm_only_candidate_negative_control()


def test_s2_validator_rejects_manifest_that_claims_acquisition() -> None:
    manifest = copy.deepcopy(_manifest())
    manifest["acquisition_branch_state"] = "implemented"

    validation = s2_validator.validate_s2_manifest_payload(manifest)

    assert validation["status"] == "fail"
    assert "s2_acquisition_branch_must_remain_bridge_missing" in {
        issue["code"] for issue in validation["issues"]
    }


def test_s2_manifest_is_registered_in_inventory() -> None:
    inventory = json.loads(
        (REPO_ROOT / "architecture/policy_design_case/inventory.json").read_text(
            encoding="utf-8"
        )
    )
    artifacts = {str(row["id"]): row for row in inventory["artifacts"]}

    row = artifacts["layer2_s2_design_search_manifest"]
    assert row["path"] == "architecture/policy_design_case/layer2_s2_design_search_manifest.json"
    assert row["schema_version"] == (
        "policyos.policy_design_case.layer2_s2_design_search_manifest.v1"
    )
    assert row["owner"] == "team-design-generation"
    assert row["status"] == "active"
    assert row["capability_reality_label"] == "implemented"
    assert row["authority_scope"] == "shadow_design_search_replay"
    assert "acquisition_authority" in row["may_not_use_for"]
    assert "production_recommendation" in row["may_not_use_for"]
    assert row["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_s2_design_search.py"
    )
    assert row["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )
