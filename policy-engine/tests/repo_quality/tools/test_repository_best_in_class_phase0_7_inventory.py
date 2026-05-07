from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from tools.quality.validation import repository_best_in_class_phase0_7_inventory as phase0_7

REPO_ROOT = Path(__file__).resolve().parents[3]


@lru_cache(maxsize=1)
def _inventory() -> dict[str, object]:
    return phase0_7.collect_inventory(REPO_ROOT)


def test_inventory_covers_phase_scope_surfaces() -> None:
    inventory = _inventory()

    assert phase0_7.validate_inventory(inventory) == []
    assert inventory["schema_version"] == phase0_7.SCHEMA_VERSION
    assert inventory["phase"] == "0.7"

    documentation = inventory["documentation"]
    lifecycle_counts = documentation["lifecycle_counts"]
    for lifecycle in (
        "active-plan",
        "accepted-plan",
        "archived",
        "adr",
        "runbook",
        "migration",
        "design",
        "architecture-prose",
    ):
        assert lifecycle in lifecycle_counts
        assert lifecycle_counts[lifecycle] > 0

    assert documentation["tag_counts"]["release-note"] >= 1

    high_volume_paths = {
        row["path"] for row in inventory["high_volume_subtrees"]["rows"]
    }
    assert high_volume_paths == set(phase0_7.HIGH_VOLUME_SUBTREES)

    workspace_roots = {
        row["path"]: row for row in inventory["top_level_directories"]["workspace_root"]
    }
    for local_root in (".claude", ".cursor", ".git", "_cache", "tmp"):
        if local_root in workspace_roots:
            assert workspace_roots[local_root]["local_only"] is True
    if "_cache" in workspace_roots:
        assert workspace_roots["_cache"]["ignored_file_count"] > 0
    assert workspace_roots[".github"]["local_only"] is False

    asset_counts = inventory["assets"]["counts"]
    for category in (
        "product_seed_assets",
        "test_fixtures",
        "golden_records_snapshots",
        "example_assets",
        "frontend_test_fixtures",
        "empty_directories",
        "ds_store",
        "pycache_dirs",
        "egg_info_residue",
        "local_audit_reports",
        "benchmark_reports",
    ):
        assert category in asset_counts


def test_adr_metadata_reports_required_machine_field_gaps() -> None:
    adr = _inventory()["adr_metadata"]

    assert adr["total"] > 100
    for field in phase0_7.ADR_REQUIRED_MACHINE_FIELDS:
        assert adr["missing_field_counts"][field] > 0

    rows = {row["path"]: row for row in adr["rows"]}
    lifecycle_adr = rows["docs/adr/0126-docs-lifecycle-diataxis-plans-archive.md"]
    assert lifecycle_adr["body_status"].lower() == "proposed"
    assert lifecycle_adr["body_related_present"] is True
    assert set(lifecycle_adr["missing_machine_fields"]) == set(
        phase0_7.ADR_REQUIRED_MACHINE_FIELDS
    )

    versioning_adr = rows[
        "docs/adr/repository-structure-0135-versioning-out-of-package-names.md"
    ]
    assert versioning_adr["body_status"].lower() == "accepted"


def test_extension_points_and_examples_are_decision_mapped() -> None:
    inventory = _inventory()
    surfaces = {
        row["surface"]: row for row in inventory["extension_points"]["surfaces"]
    }

    assert set(surfaces) == {
        "Fabric connectors",
        "Scientist governance passes",
        "Foundry methods",
        "Scientist nodes",
        "Data Forge domains",
        "Lex norm packs",
        "Runtime middlewares",
    }
    assert len(surfaces["Fabric connectors"]["entry_points"]) >= 1
    assert len(surfaces["Scientist governance passes"]["entry_points"]) >= 1
    assert len(surfaces["Foundry methods"]["candidates"]) >= 1
    assert len(surfaces["Runtime middlewares"]["candidates"]) >= 1
    for surface in surfaces.values():
        assert surface["future_phase"]
        assert surface["decision"]

    examples = {row["path"]: row for row in inventory["examples"]["rows"]}
    assert "examples/ir_base_demo.py" in examples
    assert examples["examples/ir_base_demo.py"]["future_phase"] == "1.5, 4.10, 6.4"


def test_markdown_brief_contains_acceptance_and_refresh_commands() -> None:
    page = phase0_7.render_markdown(_inventory())

    assert "# Repository Best-In-Class Phase 0.7 Decision Brief" in page
    assert "No docs lifecycle moves" in page
    assert "## ADR Metadata Inventory" in page
    assert "## Extension-Point Inventory" in page
    assert "## Asset And Residue Inventory" in page
    assert "repository_best_in_class_phase0_7_inventory.py --check" in page


def test_dump_json_is_stable_and_machine_readable() -> None:
    payload = json.loads(phase0_7.dump_json(_inventory()))

    assert payload["schema_version"] == phase0_7.SCHEMA_VERSION
    assert payload["phase"] == "0.7"
    assert payload["decision_queue"]
