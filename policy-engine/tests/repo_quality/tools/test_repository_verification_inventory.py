from __future__ import annotations

from pathlib import Path

from tools.quality.validation import repository_verification_inventory as inventory

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase04_inventory_covers_verification_surfaces() -> None:
    payload = inventory.build_inventory(REPO_ROOT)

    assert payload["schema_version"] == inventory.SCHEMA_VERSION
    assert payload["phase"] == "0.4"
    assert payload["mode"] == "read_only_inventory"

    packages = {row["package"]: row for row in payload["mirror_ratios"]["packages"]}
    for package in inventory.TRACKED_PACKAGES:
        assert package in packages
        assert "strict_module_mirror_ratio" in packages[package]
        assert "property_test_file_count" in packages[package]

    shims = payload["mirror_ratios"]["compatibility_shims"]
    assert not any(row["source_package"] == "ddm_15_7" for row in shims)
    assert not any(row["source_package"] == "synthetic_world" for row in shims)

    fixtures = payload["fixtures"]
    assert fixtures["roots"]["tests/_data"]["exists"]
    assert fixtures["roots"]["tests/_golden"]["exists"]
    assert fixtures["roots"]["tests/_helpers"]["exists"]
    assert fixtures["roots"]["tests/contract"]["exists"]
    assert "pytest_collectable_tests_under_data_like_dirs" in fixtures

    roles = {
        row["path"]: row["role"]
        for row in payload["test_role_inventory"]["role_roots"]
    }
    assert roles["tests/contract"] == "product_contract"
    assert roles["tests/repo_quality/architecture"] == "repository_quality"
    assert roles["tests/repo_quality/lint"] == "repository_quality"
    assert roles["tests/repo_quality/tools"] == "repository_quality"

    property_coverage = payload["property_coverage"]
    assert property_coverage["missing_data_contract_heavy_packages"] == []

    benchmarks = payload["benchmarks"]
    assert benchmarks["benchmark_root"]["py_file_count"] > 0
    assert benchmarks["performance_tests"]["test_file_count"] > 0
    assert benchmarks["pytest_configuration"]["benchmark_storage"] == "file://./_cache/benchmarks"

    pytest = payload["pytest"]
    assert pytest["testpaths"].strip() == "tests"
    assert pytest["import_mode"] == "importlib"
    assert pytest["conftest_count"] > 0
    duplicate_fixtures = {row["fixture"]: row for row in pytest["duplicate_fixture_names"]}
    assert {"cas_store", "isolated_registry"}.issubset(duplicate_fixtures)
    assert pytest["scope_ambiguous_fixture_names"] == []


def test_phase04_inventory_artifacts_are_current() -> None:
    assert inventory.check_artifacts(repo_root=REPO_ROOT) == []
