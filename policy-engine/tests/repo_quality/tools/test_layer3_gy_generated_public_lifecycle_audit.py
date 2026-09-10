from __future__ import annotations

import hashlib
import json
import re
import tomllib
from importlib import import_module
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
AUDIT_PATH = (
    REPO_ROOT
    / "architecture"
    / "policy_design_case"
    / "layer3_gy_task0_audit"
    / "layer3_gy_generated_public_lifecycle_audit.json"
)


def _validator() -> Any:
    return import_module("tools.quality.validation.check_layer3_gy_generated_public_lifecycle_audit")


def _load_audit() -> dict[str, Any]:
    return json.loads(AUDIT_PATH.read_text(encoding="utf-8"))


def _codes(violations: list[dict[str, Any]]) -> set[str]:
    return {str(item["code"]) for item in violations}


def _row(audit: dict[str, Any], row_id: str) -> dict[str, Any]:
    for row in audit["lifecycle_matrix"]:
        if row.get("row_id") == row_id:
            return row
    raise AssertionError(f"missing row {row_id}")


def _surface(audit: dict[str, Any], surface_id: str) -> dict[str, Any]:
    for row in audit["public_surface_lifecycle"]:
        if row.get("surface_id") == surface_id:
            return row
    raise AssertionError(f"missing surface {surface_id}")


def _negative(audit: dict[str, Any], negative_id: str) -> dict[str, Any]:
    for row in audit["negative_assertions"]:
        if row.get("id") == negative_id:
            return row
    raise AssertionError(f"missing negative assertion {negative_id}")


def test_gy_generated_public_lifecycle_validator_passes_current_artifact() -> None:
    validator = _validator()

    assert validator.validate(_load_audit()) == []


@pytest.mark.parametrize("registered", [False, True])
def test_inventory_registration_is_recomputed_from_custody(
    tmp_path: Path, registered: bool
) -> None:
    """The inventory's own custody is a measured registry fact, not a constant."""
    architecture = tmp_path / "architecture"
    (architecture / "policy_design_case").mkdir(parents=True)
    (architecture / "public_surface").mkdir()
    (architecture / "generated_artifacts.toml").write_text(
        '[[family]]\nid = "pdc-source"\noutputs = '
        + ('["architecture/policy_design_case/inventory.json"]' if registered else "[]")
        + "\n",
        encoding="utf-8",
    )
    (architecture / "policy_design_case/inventory.json").write_text(
        '{"artifacts": []}\n', encoding="utf-8"
    )
    (architecture / "public_surface/contract.toml").write_text("", encoding="utf-8")
    report = {
        "discovered_artifacts": [],
        "registered_outputs": [],
        "producer_declared_outputs": [],
        "source_committed_outputs": [],
        "output_root_files": [],
        "unaccounted_output_root_files": [],
        "registered_artifact_count": 0,
        "orphan_count": 0,
        "phantom_output_count": 0,
        "duplicate_claim_count": 0,
    }
    facts = _validator()._lifecycle_facts(tmp_path, report)
    assert facts["policy_design_case_inventory_registered_in_generated_artifacts"] is registered


@pytest.mark.parametrize("suffix", [".blob", ".jsonl"])
def test_output_root_census_includes_unregistered_cas_members(
    tmp_path: Path, suffix: str
) -> None:
    root = tmp_path / "architecture/cas"
    root.mkdir(parents=True)
    artifact = root / f"unregistered{suffix}"
    artifact.write_bytes(b"source evidence\n")
    observed = _validator()._iter_contract_derived_output_root_files(
        tmp_path, {"architecture/cas"}, (set(), set())
    )
    assert observed == [artifact.relative_to(tmp_path).as_posix()]


@pytest.mark.parametrize(
    ("prefix", "schema"),
    [
        ("policyos.gy_n10.cg1_l2_prior_census", "policyos.gy_n10.cg1_l2_prior_census.compact.v1"),
        ("policyos.policy_design_case.gy_n13a.acquisition_census", "policyos.policy_design_case.gy_n13a.acquisition_census.v1"),
        ("policyos.layer3.gy.n13b", "policyos.layer3.gy.n13b.lifecycle_manifest.v3"),
    ],
)
def test_actual_producer_namespaces_have_bounded_lifecycle_custody(
    tmp_path: Path, prefix: str, schema: str
) -> None:
    artifact = tmp_path / "receipt.json"
    artifact.write_text(json.dumps({"schema_version": schema}), encoding="utf-8")
    family = {"id": "actual-owner", "lifecycle_schema_prefixes": [prefix]}
    issues = []
    validator = _validator()
    assert validator._family_lifecycle_schema_prefixes(family, issues) == (prefix,)
    validator._validate_producer_output_provenance(tmp_path, family, "receipt.json", issues)
    assert issues == []


@pytest.mark.parametrize(
    "prefix", ["policyos", "policyos.layer3", "policyos.layer3.gy", "policyos.gy_", "policyos.policy_design_case"]
)
def test_lifecycle_custody_rejects_unbounded_namespaces(prefix: str) -> None:
    assert not _validator()._is_bounded_family_lifecycle_schema_prefix(prefix)


def test_inventory_byte_drift_reaches_its_registered_verifier(tmp_path: Path) -> None:
    """Exercise the real registry's inventory owner through M1's actual consumer."""
    relative = "architecture/policy_design_case/inventory.json"
    registry = (REPO_ROOT / "architecture/generated_artifacts.toml").read_text()
    blocks = ["[[family]]" + block for block in registry.split("[[family]]")[1:]]
    owners = [block for block in blocks if relative in tomllib.loads(block)["family"][0].get("outputs", [])]
    assert len(owners) == 1
    inventory = tmp_path / relative
    inventory.parent.mkdir(parents=True)
    inventory.write_bytes((REPO_ROOT / relative).read_bytes())
    digest = "sha256:" + hashlib.sha256(inventory.read_bytes()).hexdigest()
    block = re.sub(
        r'(source_integrity_sha256\."' + re.escape(relative) + r'" = ")[^"]+("\s*)',
        lambda match: match[1] + digest + match[2],
        owners[0],
    )
    (tmp_path / "architecture/generated_artifacts.toml").write_text(block)
    validator = _validator()
    before = validator.validate_gy_lifecycle_registry(tmp_path)
    assert not any(issue["code"] == "layer3_gy_source_output_integrity_drift" for issue in before["issues"])
    inventory.write_bytes(inventory.read_bytes() + b"\n")
    after = validator.validate_gy_lifecycle_registry(tmp_path)
    assert any(
        issue["code"] == "layer3_gy_source_output_integrity_drift" and issue.get("path") == relative
        for issue in after["issues"]
    )


def test_real_alternative_namespaces_are_discovered_without_registration(tmp_path: Path) -> None:
    """Removing an entire family cannot hide its real producer's schema markers."""
    family_ids = {
        "policy-design-case-layer3-gy-n10-cg1-l2-relation-census",
        "policy-design-case-layer3-gy-n13a-acquisition-census",
        "policy-design-case-layer3-gy-n13b-acquisition-executor",
    }
    families = tomllib.loads((REPO_ROOT / "architecture/generated_artifacts.toml").read_text())["family"]
    selected = [family for family in families if family["id"] in family_ids]
    assert {family["id"] for family in selected} == family_ids
    expected = set()
    for family in selected:
        assert family["outputs"]
        for relative in family["outputs"]:
            destination = tmp_path / "new-location" / Path(relative).name
            destination.parent.mkdir(exist_ok=True)
            destination.write_bytes((REPO_ROOT / relative).read_bytes())
            expected.add(destination.relative_to(tmp_path).as_posix())
    assert expected == {path.relative_to(tmp_path).as_posix() for path in tmp_path.rglob("*.json")}
    assert set(_validator()._iter_gy_marked_artifact_files(tmp_path, (set(), set()))) == expected


def test_gy_generated_public_lifecycle_rejects_missing_gy_family_registration() -> None:
    validator = _validator()
    audit = _load_audit()
    gy = _row(audit, "layer3_gy_task0_audit_artifacts")
    gy["registered"] = False
    gy["family_id"] = None
    gy["outputs_registered_count"] = 0
    gy["stale_output_behavior"] = "missing_registry"
    audit["summary"]["gy_generated_family_registered"] = False
    audit["summary"]["gy_artifact_files_registered_count"] = 0

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_family_registration_drift" in codes
    assert "gy_family_id_drift" in codes
    assert "gy_registered_output_count_drift" in codes
    assert "gy_stale_policy_drift" in codes


def test_gy_generated_public_lifecycle_rejects_public_surface_family_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    surface = _surface(audit, "policy_design_case_generated_audit_surfaces_section")
    surface["gy_surface_registered"] = False
    audit["summary"]["gy_public_surface_family_registered"] = False

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_public_surface_registration_drift" in codes


def test_gy_generated_public_lifecycle_rejects_projection_refs_as_api_enforcement() -> None:
    validator = _validator()
    audit = _load_audit()
    projection = _surface(audit, "layer3_public_export_projection_refs")
    projection["api_dashboard_enforcement"] = True
    projection["public_export_route_registered"] = True
    _negative(
        audit,
        "do_not_count_projection_refs_as_api_dashboard_enforcement",
    )["assertion_holds"] = False

    codes = _codes(validator.validate(audit))
    assert "projection_refs_api_enforcement_laundering" in codes
    assert "projection_refs_public_export_laundering" in codes
    assert "negative_assertion_not_enforced" in codes


def test_gy_generated_public_lifecycle_rejects_missing_registered_stale_policy() -> None:
    validator = _validator()
    audit = _load_audit()
    openapi = _row(audit, "runtime_openapi_snapshot")
    openapi["stale_output_behavior"] = ""

    codes = _codes(validator.validate(audit))
    assert "registered_family_missing_lifecycle_metadata" in codes


def test_gy_generated_public_lifecycle_rejects_missing_pdc_inventory_gy_entries() -> None:
    validator = _validator()
    audit = _load_audit()
    pdc = _row(audit, "policy_design_case_inventory")
    pdc["contains_gy_entries"] = False
    audit["summary"]["policy_design_case_inventory_gy_entries"] = 0

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "pdc_inventory_gy_entry_missing" in codes


def test_gy_generated_public_lifecycle_rejects_file_inventory_drift() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["gy_artifact_inventory"]["paths"] = audit["gy_artifact_inventory"]["paths"][:-1]
    audit["summary"]["gy_artifact_files_detected"] -= 1

    codes = _codes(validator.validate(audit))
    assert "summary_semantics_drift" in codes
    assert "gy_detected_artifact_list_drift" in codes


def test_gy_generated_public_lifecycle_rejects_missing_pattern_and_acceptance() -> None:
    validator = _validator()
    audit = _load_audit()
    audit["classification"]["patterns"] = [
        pattern for pattern in audit["classification"]["patterns"] if pattern != "P31"
    ]
    audit["acceptance_signal"] = [
        item
        for item in audit["acceptance_signal"]
        if "producer write-closure" not in item
    ]

    codes = _codes(validator.validate(audit))
    assert "pattern_coverage_drift" in codes
    assert "missing_acceptance_guardrail" in codes
