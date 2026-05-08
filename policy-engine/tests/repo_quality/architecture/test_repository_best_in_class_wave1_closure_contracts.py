from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_ROOT = REPO_ROOT.parent


def test_phase1_1_root_decision_is_machine_readable_and_ignored() -> None:
    topology = _read_toml(REPO_ROOT / "architecture/topology.toml")
    decision = topology["repository_root_decision"]

    assert decision["selected_option"] == "B"
    assert decision["product_root_from_outer"] == "policy-engine"
    assert decision["renovate_target"] == ".github/renovate.json"
    assert "renovate_transition" not in decision
    assert decision["option_c_status"].startswith("rejected")
    assert "source package moves" in decision["rollback_excludes"]

    allow_list = decision["outer_root_allow_list"]["paths"]
    assert decision["outer_root_allow_list"]["mode"] == "fail_closed"
    assert ".github/**" in allow_list
    assert "policy-engine/**" in allow_list
    assert "renovate.json" not in allow_list

    rejected = {row["class"]: row for row in decision["rejected_outer_path_class"]}
    assert {"product_source", "wrong_root_local_state"} <= set(rejected)
    assert "_cache/**" in rejected["wrong_root_local_state"]["examples"]

    gate_ids = {row["id"] for row in decision["root_topology_gate_requirement"]}
    assert {
        "no-product-source-outside-product-root",
        "outer-root-allow-list",
        "no-wrong-root-local-state",
        "product-commands-run-from-product-root",
    } <= gate_ids
    assert {
        row["id"]: row["mode"] for row in decision["root_topology_gate_requirement"]
    } == {
        "no-product-source-outside-product-root": "fail_closed",
        "outer-root-allow-list": "fail_closed",
        "no-wrong-root-local-state": "fail_closed",
        "product-commands-run-from-product-root": "fail_closed",
    }

    outer_gitignore = (WORKSPACE_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "/_build/" in outer_gitignore
    assert "/_cache/" in outer_gitignore


def test_phase1_2_generated_artifact_families_have_lifecycle_fields() -> None:
    payload = _read_toml(REPO_ROOT / "architecture/generated_artifacts.toml")
    families = payload["family"]

    allowed_lifecycles = {
        "source_committed",
        "generated_committed",
        "generated_ignored",
        "runtime_ignored",
        "scratch_ignored",
    }
    allowed_stale = {
        "fail",
        "warn",
        "cleanup_eligible",
        "ignored_by_policy",
        "block_release",
    }

    for family in families:
        for field in (
            "lifecycle",
            "generator",
            "verifier",
            "owner",
            "promotion_target",
            "stale_output_behavior",
        ):
            assert family[field], (family["id"], field)
        assert family["lifecycle"] in allowed_lifecycles, family["id"]
        assert family["stale_output_behavior"] in allowed_stale, family["id"]


def test_phase1_5_dynamic_import_registry_entries_have_targets_and_verifiers() -> None:
    payload = _read_toml(REPO_ROOT / "architecture/imports/dynamic.toml")
    patterns = payload["pattern"]

    assert patterns
    for pattern in patterns:
        assert pattern["owner"], pattern["id"]
        assert pattern["verifier"], pattern["id"]
        assert pattern.get("target") or pattern.get("allowed_targets"), pattern["id"]


def test_phase1_8_directory_contracts_cover_roots_and_match_fixture_transition() -> None:
    payload = _read_toml(REPO_ROOT / "architecture/policies/directory_contracts.toml")
    contracts = {row["path"]: row for row in payload["contract"]}

    assert {
        "architecture",
        "benchmarks",
        "data",
        "design",
        "docs",
        "examples",
        "frontend",
        "apps",
        "ops",
        "packages",
        "release",
        "release-fragments",
        "schemas",
        "src",
        "tests",
        "tools",
        "_build",
        "_cache",
        ".polisyos",
        ".venv",
        "node_modules",
    } <= set(contracts)

    for path, contract in contracts.items():
        for field in (
            "role",
            "allowed_file_kinds",
            "allowed_child_directory_kinds",
            "lifecycle_class",
            "owner",
            "python_import_policy",
            "generated_output_policy",
            "committed_data_policy",
            "readme_index_requirement",
            "ignored_descendant_retention",
            "evidence_or_generated_artifact_promotion_path",
        ):
            assert contract[field], (path, field)

    ratchets = _read_toml(REPO_ROOT / "architecture/tests/ratchets.toml")
    fixture_policy = ratchets["fixture_policy"]
    asset_classes = {row["id"]: row for row in payload["asset_class"]}

    assert fixture_policy["shared_fixture_root"] in {
        root.rstrip("/") for root in asset_classes["test_fixtures"]["current_wave1_roots"]
    }
    assert fixture_policy["shared_golden_root"] in {
        root.rstrip("/") for root in asset_classes["golden_records"]["current_wave1_roots"]
    }
    assert "tests/_data" in fixture_policy["target_fixture_roots"]
    assert "tests/_golden" in fixture_policy["target_golden_roots"]


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))
