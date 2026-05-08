from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase1e_test_topology_contract_matches_source_packages() -> None:
    contract = _contract()
    packages = {package["name"]: package for package in contract["package"]}
    wrapper_shims = _wrapper_shim_source_package_names()
    source_exceptions = _source_package_exception_names(contract)
    source_packages = {
        path.name
        for path in (REPO_ROOT / "src" / "polisyos").iterdir()
        if path.is_dir()
        and path.name != "__pycache__"
        and (path / "__init__.py").exists()
        and path.name not in wrapper_shims
        and path.name not in source_exceptions
    }

    assert contract["test_topology"]["status"] == "active"
    assert set(packages) == source_packages

    for name, package in packages.items():
        assert _path(package["source_path"]).is_dir(), name
        assert _path(package["unit_path"]).is_dir(), name
        assert _path(package["conftest_path"]).is_file(), name

    for exception in contract.get("source_package_exception", []):
        assert _path(exception["source_path"]).is_dir(), exception["name"]
        assert exception["classification"], exception["name"]
        assert exception["owner"], exception["name"]
        assert exception["reason"], exception["name"]
        assert exception["sunset"], exception["name"]
        assert exception["issue"], exception["name"]


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


def test_phase35_repo_quality_tests_are_consolidated_or_redirected() -> None:
    contract = _contract()
    topology = contract["test_topology"]

    assert topology["contract_root"] == "tests/contract"
    assert topology["repo_quality_root"] == "tests/repo_quality"

    for key in (
        "repo_quality_architecture_root",
        "repo_quality_lint_root",
        "repo_quality_tools_root",
    ):
        root = _path(topology[key])
        assert root.is_dir(), key
        assert list(root.rglob("test_*.py")), key

    for legacy_root in topology["legacy_repo_quality_redirect_roots"]:
        root = _path(legacy_root)
        assert root.is_dir(), legacy_root
        assert (root / "README.md").is_file(), legacy_root
        assert list(root.rglob("test_*.py")) == [], legacy_root

    rules = {rule["id"] for rule in contract["topology_rule"]}
    assert "repo-quality-tests-are-consolidated" in rules


def _contract() -> dict[str, Any]:
    return tomllib.loads(
        (REPO_ROOT / "architecture" / "tests" / "topology.toml").read_text(encoding="utf-8")
    )


def _wrapper_shim_source_package_names() -> set[str]:
    shims = tomllib.loads((REPO_ROOT / "architecture" / "shims.toml").read_text(encoding="utf-8"))
    return {
        Path(shim["source_path"]).name
        for shim in shims.get("shim", [])
        if shim.get("type") == "wrapper_only"
        and str(shim.get("source_path", "")).startswith("src/polisyos/")
    }


def _source_package_exception_names(contract: dict[str, Any]) -> set[str]:
    return {exception["name"] for exception in contract.get("source_package_exception", [])}


def _path(relative_path: str) -> Path:
    return REPO_ROOT / relative_path
