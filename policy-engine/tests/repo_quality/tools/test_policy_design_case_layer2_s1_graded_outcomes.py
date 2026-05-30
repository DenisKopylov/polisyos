from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.runtime.quality.graded_outcomes import GradedOutcomeInputError
from tools.quality.validation import (
    check_policy_design_case_layer2_s1_graded_outcomes as s1_validator,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
MANIFEST_PATH = (
    REPO_ROOT / "architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json"
)
LIMITATION_REQUIRED_CASE_IDS = [
    "ua-msme-affordable-loans-2022",
    "w11a_boston_operation_ceasefire_1996",
    "w11a_ghana_free_shs_2017",
    "w11a_mexico_ssb_tax_2014",
    "w11a_netherlands_room_for_river_2007",
    "w11a_uk_levelling_up_fund_2021",
    "w11a_uk_mtd_vat_2019",
    "w11a_uk_work_programme_2011",
    "w11a_us_ppp_2020",
]
PRODUCTION_CONTROL_CASE_IDS = [
    "ua-msme-affordable-loans-2022",
    "w11a_berlin_rent_cap_2020",
    "w11a_boston_operation_ceasefire_1996",
    "w11a_eu_temporary_protection_ukraine_2022",
    "w11a_ghana_free_shs_2017",
    "w11a_india_aadhaar_dbt_2016",
    "w11a_mexico_ssb_tax_2014",
    "w11a_netherlands_room_for_river_2007",
    "w11a_pakistan_ehsaas_cash_2020",
    "w11a_uk_levelling_up_fund_2021",
    "w11a_uk_mtd_vat_2019",
    "w11a_uk_work_programme_2011",
    "w11a_us_ppp_2020",
]


def _load_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_s1_manifest_declares_no_open_cell_closure() -> None:
    manifest = _load_manifest()

    assert manifest["slice"] == "S1"
    assert manifest["cells_closed"] == []
    assert manifest["open_cell_count_baseline"] == 17


def test_s1_manifest_names_nine_limitation_cases_and_thirteen_production_controls() -> None:
    manifest = _load_manifest()

    assert manifest["limitation_required_case_ids"] == LIMITATION_REQUIRED_CASE_IDS
    assert manifest["production_strict_control_case_ids"] == PRODUCTION_CONTROL_CASE_IDS
    assert manifest["limitation_required_case_count"] == len(LIMITATION_REQUIRED_CASE_IDS)
    assert manifest["production_strict_control_case_count"] == len(PRODUCTION_CONTROL_CASE_IDS)


def test_s1_manifest_requires_governed_decision_owner_and_canonical_route() -> None:
    manifest = _load_manifest()

    assert manifest["decision_owner_required"] is True
    assert manifest["review_refs_required"] is True
    assert manifest["canonical_route_ref"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )


def test_s1_manifest_is_registered_in_inventory() -> None:
    inventory_path = REPO_ROOT / "architecture/policy_design_case/inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    artifacts = {str(artifact["id"]): artifact for artifact in inventory["artifacts"]}

    row = artifacts["layer2_s1_graded_outcomes_manifest"]
    assert row["path"] == (
        "architecture/policy_design_case/layer2_s1_graded_outcomes_manifest.json"
    )
    assert row["schema_version"] == (
        "policyos.policy_design_case.layer2_s1_graded_outcomes_manifest.v1"
    )
    assert row["owner"] == "team-runtime-quality"
    assert row["status"] == "active"
    assert row["capability_reality_label"] == "implemented"
    assert row["authority_scope"] == "graded_outcome_routing"
    assert "production_closeout_authority" in row["may_not_use_for"]
    assert "claim_authority" in row["may_not_use_for"]
    assert "b_side_design_generation" in row["may_not_use_for"]
    assert row["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_s1_graded_outcomes.py"
    )
    assert row["canonical_route"] == (
        "tools/quality/validation/run_universal_outcome_corpus.py"
    )


def test_s1_validator_reports_governed_limitations_and_production_strictness() -> None:
    summary = s1_validator.validate_s1_graded_outcomes(repo_root=REPO_ROOT)

    assert summary["status"] == "pass"
    assert summary["governed_publish_with_limitation_count"] == 9
    assert summary["production_typed_blocker_count"] == 13
    assert summary["canonical_route_status"] == "pass"


def test_s1_validator_rejects_fabricated_limitation_without_proxy_evidence() -> None:
    with pytest.raises(GradedOutcomeInputError):
        s1_validator.validate_fabricated_limitation_negative_control()


def test_s1_validator_keeps_s0_open_cell_count_unchanged() -> None:
    summary = s1_validator.validate_s1_graded_outcomes(repo_root=REPO_ROOT)

    assert summary["open_cell_count"] == 17
    assert summary["cells_closed"] == []
