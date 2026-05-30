from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path
from typing import Any

from polisyos.core.components import EXTENSION_ENTRY_POINT_GROUPS
from tools.ops_runners.release.build_release_notes import CURATED_SECTIONS

REPO_ROOT = Path(__file__).resolve().parents[3]

REQUIRED_EXTENSION_POINTS = {
    "polisyos.fabric_connectors",
    "polisyos.scientist_governance_passes",
    "polisyos.foundry_methods",
    "polisyos.scientist_nodes",
    "polisyos.data_forge_domains",
    "polisyos.lex_normpacks",
    "polisyos.runtime_middlewares",
}

REQUIRED_COMPATIBILITY_CATEGORIES = {
    "python_public_api",
    "schema_openapi_abi",
    "extension_plugin_abi",
    "runtime_state_format",
    "persisted_artifact_format",
    "js_package_api",
}

REQUIRED_DEPRECATION_WINDOWS = {
    "shim_packages",
    "renamed_public_imports",
    "extension_contract_versions",
    "runtime_state_migration_readers",
    "generated_client_compatibility",
}


def test_phase1_5_extension_points_are_owned_versioned_and_discoverable() -> None:
    contract = _read_toml("architecture/extension_points.toml")
    pyproject = _read_toml("pyproject.toml")
    project_entry_points = pyproject["project"]["entry-points"]
    extension_points = {row["name"]: row for row in contract["extension_point"]}

    assert set(extension_points) == REQUIRED_EXTENSION_POINTS
    assert set(EXTENSION_ENTRY_POINT_GROUPS) == REQUIRED_EXTENSION_POINTS

    for name, row in extension_points.items():
        assert row["owner"].startswith("team-"), name
        assert row["contract"], name
        assert row["contract_version"] == "1.0", name
        assert row["abi_compatibility"] == "semver-major", name
        assert row["deprecation_notice_window"], name
        assert row["entry_point_group"] in project_entry_points, name
        assert row["builtin_loader"], name
        assert row["builtin_loader_owner"].startswith("team-"), name
        assert row["builtin_loader_verifier"], name
        assert row["dynamic_import_target"], name
        assert row["dynamic_import_verifier"], name
        assert row["example_package"].startswith("examples/extensions/"), name
        assert "pip install -e" in row["example_smoke_command"], name
        assert row["example_expectations"], name
        _assert_resolves(row["contract"])


def test_phase1_5_dynamic_import_and_example_contracts_are_declared() -> None:
    extension_contract = _read_toml("architecture/extension_points.toml")
    dynamic_imports = _read_toml("architecture/imports/dynamic.toml")["dynamic_imports"]

    policy = extension_contract["dynamic_import_policy"]
    assert policy["required_registry_fields"] == ["owner", "target", "verifier"]
    assert "entry-point group" in policy["plugin_discovery_rule"]
    assert "architecture/imports/dynamic.toml" in policy["ad_hoc_import_rule"]

    assert dynamic_imports["extension_points"] == "architecture/extension_points.toml"
    assert dynamic_imports["new_entry_required_fields"] == [
        "owner",
        "target_or_allowed_targets",
        "verifier",
    ]

    examples_readme = (REPO_ROOT / "examples/extensions/README.md").read_text(
        encoding="utf-8"
    )
    assert "python -m pip install -e" in examples_readme
    assert "contract_version" in examples_readme


def test_phase1_5_versioning_policy_categories_and_windows_are_machine_readable() -> None:
    contract = _read_toml("architecture/extension_points.toml")
    categories = {row["id"]: row for row in contract["compatibility_category"]}
    windows = {row["id"]: row for row in contract["deprecation_window"]}

    assert set(categories) == REQUIRED_COMPATIBILITY_CATEGORIES
    assert set(windows) == REQUIRED_DEPRECATION_WINDOWS

    for row in categories.values():
        assert row["source_of_truth"]
        assert row["breaking_change_signal"]
        assert row["release_fragment_change_class"]

    for row in windows.values():
        assert row["category"] in categories
        assert row["minimum_notice"]
        assert row["removal_gate"]
        assert row["owner"].startswith("team-")

    adr = (
        REPO_ROOT / "docs/adr/repository-structure-0135-versioning-out-of-package-names.md"
    ).read_text(encoding="utf-8")
    for label in (
        "Python public API",
        "Schema/OpenAPI ABI",
        "Extension plugin ABI",
        "Runtime-state format",
        "Persisted artifact format",
        "JS package API",
    ):
        assert label in adr


def test_phase1_5_future_versioned_concepts_do_not_create_versioned_packages() -> None:
    allowed_existing: set[str] = set()
    versioned_packages = {
        path.relative_to(REPO_ROOT).as_posix()
        for path in (REPO_ROOT / "src/polisyos").rglob("*")
        if path.is_dir()
        and (path / "__init__.py").exists()
        and re.search(r"_\d+(?:_\d+)+$", path.name)
    }

    assert versioned_packages <= allowed_existing


def test_phase1_5_release_fragments_carry_user_visible_change_classes() -> None:
    template = _read_toml("release-fragments/template.toml")

    assert template["change_class"] == "internal"
    assert "change_class" in CURATED_SECTIONS
    assert CURATED_SECTIONS["change_class"] == "Change Classes"

    readme = (REPO_ROOT / "release-fragments/README.md").read_text(encoding="utf-8")
    for change_class in (
        "python-public-api",
        "schema-openapi-abi",
        "extension-plugin-abi",
        "runtime-state-format",
        "persisted-artifact-format",
        "js-package-api",
    ):
        assert change_class in readme


def _read_toml(path: str) -> dict[str, Any]:
    return tomllib.loads((REPO_ROOT / path).read_text(encoding="utf-8"))


def _assert_resolves(fqn: str) -> None:
    module_name, attr = fqn.rsplit(".", 1)
    module = importlib.import_module(module_name)
    assert hasattr(module, attr), fqn
