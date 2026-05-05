from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_phase1e_test_topology_contract_matches_source_packages() -> None:
    contract = _contract()
    packages = {package["name"]: package for package in contract["package"]}
    wrapper_shims = _wrapper_shim_source_package_names()
    source_packages = {
        path.name
        for path in (REPO_ROOT / "src" / "polisyos").iterdir()
        if path.is_dir()
        and path.name != "__pycache__"
        and (path / "__init__.py").exists()
        and path.name not in wrapper_shims
    }

    assert contract["test_topology"]["status"] == "active"
    assert set(packages) == source_packages

    for name, package in packages.items():
        assert _path(package["source_path"]).is_dir(), name
        assert _path(package["unit_path"]).is_dir(), name
        assert _path(package["conftest_path"]).is_file(), name


def test_phase1e_integration_tests_live_outside_unit_hubs() -> None:
    contract = _contract()

    for package in contract["package"]:
        name = package["name"]
        unit_integration = REPO_ROOT / "tests" / "unit" / name / "integration"
        assert not unit_integration.exists(), name

        integration = package["integration"]
        if integration.get("required") and str(integration.get("path", "")).startswith(
            "tests/integration/"
        ):
            assert _path(integration["path"]).is_dir(), name


def test_phase1e_property_tests_are_present_or_explicitly_excepted() -> None:
    contract = _contract()

    for package in contract["package"]:
        property_contract = package["property"]
        if property_contract["required"]:
            assert _path(property_contract["path"]).is_dir(), package["name"]
        else:
            assert property_contract["reason"], package["name"]


def test_phase1e_large_package_roots_have_no_loose_tests() -> None:
    for package in ("foundry", "scientist"):
        loose_tests = sorted((REPO_ROOT / "tests" / "unit" / package).glob("test_*.py"))
        assert loose_tests == []


def _contract() -> dict[str, Any]:
    return tomllib.loads(
        (REPO_ROOT / "architecture" / "test_topology.toml").read_text(encoding="utf-8")
    )


def _wrapper_shim_source_package_names() -> set[str]:
    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8"))
    return {
        Path(shim["source_path"]).name
        for shim in shims.get("shim", [])
        if shim.get("type") == "wrapper_only"
        and str(shim.get("source_path", "")).startswith("src/polisyos/")
    }


def _path(relative_path: str) -> Path:
    return REPO_ROOT / relative_path
