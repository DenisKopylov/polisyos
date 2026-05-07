from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_phase2_9_asset_placement_contract_separates_review_classes() -> None:
    payload = _read_toml(REPO_ROOT / "architecture/asset_placement.toml")
    header = payload["asset_placement"]

    assert header["status"] == "report_only"
    assert header["phase"] == "repository-best-in-class-phase-2.9"
    assert header["validator_command"].endswith("directory-hygiene-assets --fail-on-contract-errors")
    assert "clean-local-reports" in header["cleanup_command"]

    classes = {row["id"]: row for row in payload["asset_class"]}
    assert {
        "product_seed_assets",
        "test_fixtures",
        "golden_records",
        "examples_tutorial_assets",
        "local_reports",
        "generated_benchmark_reports",
    } <= set(classes)

    assert classes["product_seed_assets"]["review_class"] == "product_data"
    assert classes["test_fixtures"]["review_class"] == "test_data"
    assert classes["golden_records"]["review_class"] == "golden_snapshot"
    assert classes["local_reports"]["commit_policy"] == "ignored_until_reviewed"
    assert classes["generated_benchmark_reports"]["local_roots"] == [
        "benchmarks/_reports/",
        "_build/benchmark-results/",
    ]


def test_phase2_9_product_fixture_and_budget_rules_are_explicit() -> None:
    payload = _read_toml(REPO_ROOT / "architecture/asset_placement.toml")
    budgets = payload["budgets"]

    assert budgets["default_max_product_asset_file_bytes"] <= 1048576
    assert budgets["default_max_product_asset_total_bytes"] <= 10485760
    assert ".csv" in budgets["allowed_product_asset_suffixes"]
    assert ".parquet" in budgets["forbidden_product_asset_suffixes"]

    fixtures = {row["id"]: row for row in payload["registered_product_fixture"]}
    topics = fixtures["catalog-relevant-topics-domain-fixtures"]
    assert topics["runtime_product_input"] is True
    assert topics["rename_decision"] == "retain-fixtures-name-by-contract"
    assert (REPO_ROOT / topics["path"]).exists()
    assert "docs/adr/repository-structure-0137-production-data-fixtures.md" in topics[
        "source_contracts"
    ]


def test_phase2_9_report_only_gate_and_cleanup_route_are_registered() -> None:
    gates = _read_toml(REPO_ROOT / "architecture/gates/report_only.toml")
    gate = {row["id"]: row for row in gates["gate"]}["directory-hygiene-assets"]
    assert gate["mode"] == "report_only"
    assert gate["evidence"] == "architecture/asset_placement.toml"
    assert "architecture/asset_placement.toml" in gate["source_contracts"]

    runtime_state = _read_toml(REPO_ROOT / "architecture/local_runtime_state.toml")
    assert any("clean-local-reports" in command for command in runtime_state["local_runtime_state"]["cleanup_commands"])
    reports = {
        row["id"]: row for row in runtime_state["state_class"]
    }["reports"]
    assert "clean-local-reports" in reports["preferred_stale_cleanup_command"]


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))
