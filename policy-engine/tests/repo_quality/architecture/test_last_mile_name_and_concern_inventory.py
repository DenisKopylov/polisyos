from __future__ import annotations

import json
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from tools.quality.validation import repository_last_mile_inventory as last_mile

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_DIR = (
    REPO_ROOT / "architecture" / "baselines" / "repository_best_in_class_last_mile"
)
NAME_REGISTRY = REPO_ROOT / "architecture" / "name_registry.toml"
CONCERN_CONTRACT = REPO_ROOT / "architecture" / "policies" / "cross_cutting_concerns.toml"

REQUIRED_CONCERNS = {
    "observability",
    "security",
    "registry",
    "discovery",
    "configuration",
    "tracing",
    "telemetry",
    "calibration",
}
REQUIRED_SCIENTIST_FAMILIES = {
    "workflows_orchestration_orchestrator_research_dag",
    "methods_legacy_search_discovery_research_roots",
    "extensions_package_registries",
    "governance_validation_verification_policy_verified",
}
ALLOWED_NAME_DECISIONS = {
    "scoped_ok",
    "rename",
    "merge",
    "canonical_home_with_adapters",
    "sunset_shim",
}
ALLOWED_SCIENTIST_ACTIONS = {
    "wave2_move",
    "wave2_merge",
    "wave2_shim",
    "explicit_non_overlap",
}


@lru_cache(maxsize=1)
def _inventory() -> dict[str, Any]:
    return last_mile.collect_inventory(REPO_ROOT)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def test_phase0_4_baselines_are_present_and_fresh() -> None:
    inventory = _inventory()

    assert last_mile.validate_inventory(inventory) == []
    assert _load_json(BASELINE_DIR / "name_collisions.json") == inventory["name_collisions"]
    assert (
        _load_json(BASELINE_DIR / "cross_cutting_concerns.json")
        == inventory["cross_cutting_concerns"]
    )
    assert (
        _load_json(BASELINE_DIR / "scientist_parallel_implementations.json")
        == inventory["scientist_parallel_implementations"]
    )


def test_phase0_4_repeated_first_level_names_have_registry_decisions() -> None:
    inventory = _inventory()
    registry = _load_toml(NAME_REGISTRY)
    entries = {entry["name"]: entry for entry in registry.get("phase0_4_name_decision", [])}

    assert inventory["name_collisions"]["findings"] == []
    for collision in inventory["name_collisions"]["repeated_first_level_names"]:
        name = collision["name"]
        assert name in entries
        assert entries[name]["decision"] in ALLOWED_NAME_DECISIONS
        assert entries[name]["owner"]
        assert entries[name]["target_phase"]
        assert entries[name]["rationale"]


def test_phase0_4_cross_cutting_concerns_have_canonical_homes_and_adapter_policy() -> None:
    inventory = _inventory()
    concern_contract = _load_toml(CONCERN_CONTRACT)
    contract_by_name = {entry["name"]: entry for entry in concern_contract["concern"]}
    inventory_by_name = {
        entry["name"]: entry for entry in inventory["cross_cutting_concerns"]["concerns"]
    }

    assert REQUIRED_CONCERNS <= set(inventory_by_name)
    for name in REQUIRED_CONCERNS:
        contract = contract_by_name[name]
        row = inventory_by_name[name]

        assert contract["canonical_home"] == row["canonical_home"]
        assert contract["adapter_policy"] == row["adapter_policy"]
        assert contract["proposed_before_wave"] == "1.5"
        assert row["canonical_home"]
        assert row["adapter_policy"]
        assert row["implementation_locations"]


def test_phase0_4_scientist_parallel_families_map_to_wave2_actions() -> None:
    inventory = _inventory()
    families = {
        row["family_id"]: row
        for row in inventory["scientist_parallel_implementations"]["families"]
    }

    assert REQUIRED_SCIENTIST_FAMILIES <= set(families)
    for family_id in REQUIRED_SCIENTIST_FAMILIES:
        family = families[family_id]

        assert family["wave"] == "2"
        assert family["action"] in ALLOWED_SCIENTIST_ACTIONS
        assert family["canonical_home"]
        assert family["current_locations"]
        assert family["rationale"]
