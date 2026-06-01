from __future__ import annotations

import copy
import json
from pathlib import Path

from tools.quality.validation import check_policy_design_case_layer2_readiness as readiness

REPO_ROOT = Path(__file__).resolve().parents[3]
S3_MANIFEST = (
    REPO_ROOT
    / "architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json"
)
FIRST_PROVING = REPO_ROOT / "architecture/policy_design_case/layer2_first_proving_case.json"
INVENTORY = REPO_ROOT / "architecture/policy_design_case/inventory.json"


def _s3() -> dict[str, object]:
    return json.loads(S3_MANIFEST.read_text(encoding="utf-8"))


def _issue_codes(validation: dict[str, object]) -> set[str]:
    return {str(issue["code"]) for issue in validation["issues"]}  # type: ignore[index]


def test_layer2_s3_manifest_is_valid() -> None:
    validation = readiness.validate_layer2_readiness(REPO_ROOT)

    assert validation["status"] == "pass", validation["issues"]
    assert validation["summary"]["open_cell_count"] == 4  # type: ignore[index]
    assert validation["summary"]["s3_acquisition_branch_state"] == "implemented"  # type: ignore[index]


def test_layer2_s3_closes_no_cluster_cell() -> None:
    assert _s3()["cells_closed"] == []
    assert _s3()["expected_current_open_cell_count"] == 15


def test_layer2_s3_acquisition_branch_state_is_implemented() -> None:
    assert _s3()["acquisition_branch_state"] == "implemented"


def test_layer2_s3_pinned_constructs_match_first_proving_case() -> None:
    pinned = set(_s3()["pinned_constructs"])  # type: ignore[arg-type]
    proving = set(json.loads(FIRST_PROVING.read_text(encoding="utf-8"))["constructs"])

    assert pinned == proving
    assert len(pinned) == 5


def test_layer2_s3_may_not_use_for_blocks_production_and_scenario_family() -> None:
    deny = set(_s3()["may_not_use_for"])  # type: ignore[arg-type]

    assert {
        "production_claim_authority",
        "scenario_family_authority",
        "claim_authority_from_proxy_or_simulation",
    } <= deny


def test_layer2_s3_grounded_and_staged_constructs_are_disjoint_and_complete() -> None:
    manifest = _s3()
    grounded = set(manifest["constructs_grounded_in_s3"])  # type: ignore[arg-type]
    staged = set(manifest["constructs_staged_followup"])  # type: ignore[arg-type]

    assert grounded
    assert grounded.isdisjoint(staged)
    assert grounded | staged == set(manifest["pinned_constructs"])  # type: ignore[arg-type]


def test_layer2_s3_manifest_is_registered_in_inventory() -> None:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    artifacts = {artifact["path"]: artifact for artifact in inventory["artifacts"]}
    artifact = artifacts["architecture/policy_design_case/layer2_s3_substrate_acquisition_manifest.json"]

    assert artifact["id"] == "layer2_s3_substrate_acquisition_manifest"
    assert artifact["kind"] == "layer2_s3_substrate_acquisition_manifest"
    assert artifact["validator"] == (
        "tools/quality/validation/check_policy_design_case_layer2_readiness.py"
    )
    assert "production_claim_authority" in artifact["may_not_use_for"]


def test_layer2_s3_readiness_rejects_incomplete_authority_boundary() -> None:
    payloads = readiness.load_layer2_readiness_payloads(REPO_ROOT)
    payloads = copy.deepcopy(payloads)
    payloads["s3_substrate_acquisition"]["may_not_use_for"] = [
        "production_claim_authority"
    ]

    validation = readiness.validate_layer2_readiness_payloads(payloads)

    assert validation["status"] == "fail"
    assert "layer2_s3_authority_boundary_incomplete" in _issue_codes(validation)
