from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from tools.quality.validation import fabric_best_in_class_inventory as inventory

REPO_ROOT = Path(__file__).resolve().parents[2]


def _surface_by_id(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    surfaces = manifest["surfaces"]
    assert isinstance(surfaces, list)
    return {str(row["id"]): row for row in surfaces}


def test_manifest_status_model_and_required_surfaces() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)

    assert manifest["schema_version"] == inventory.SCHEMA_VERSION
    assert manifest["phase"] == 0
    assert manifest["phase_owner"] == inventory.OWNER
    assert manifest["status_model"]["allowed_statuses"] == list(inventory.STATUS_VALUES)
    assert manifest["status_model"]["allowed_priorities"] == list(inventory.PRIORITY_VALUES)
    assert manifest["status_model"]["allowed_severities"] == list(inventory.PRIORITY_VALUES)
    assert manifest["status_model"]["planes"] == list(inventory.PLANES)
    assert inventory.validate_manifest_payload(manifest) == []

    status_counts = manifest["summary"]["status_counts"]
    for status in inventory.STATUS_VALUES:
        assert status in status_counts

    surfaces = _surface_by_id(manifest)
    for surface in surfaces.values():
        assert surface["severity"] == surface["priority"]

    for surface_id in (
        "source_contracts.fabric_registry_snapshot",
        "source_contracts.worldbank.wdi.generic",
        "source.source_contract_v2_platform",
        "source.connector_sdk_authoring_helpers",
        "source.conformance_harness_v2",
        "source.connector_source_modules",
        "source.builtin_source_profiles",
        "evidence.record_replay_store",
        "evidence.production_source_replay_fixtures",
        "semantics.semantic_dataset_catalog",
        "semantics.stale_embedding_invalidation",
        "semantics.nl_to_dataset_resolution_eval",
        "semantics.source_quality_contract_coverage",
        "semantics.source_scorecards",
        "world.bitemporal_world_query",
        "world.discovery_graph_reasoning",
        "trust.entity_resolution_override_governance",
        "trust.source_contract_access_retention_slo",
        "trust.source_deprecation_sunset_policy",
        "trust.lineage_nodes_edges",
        "trust.access_classification",
        "trust.public_facade_exports",
    ):
        assert surface_id in surfaces


def test_source_contracts_have_addressable_manifest_surfaces() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    surfaces = _surface_by_id(manifest)
    contract_ids = manifest["coverage"]["source_contracts"]["contract_ids"]

    for contract_id in contract_ids:
        surface = surfaces[f"source_contracts.{contract_id}"]
        assert surface["status"] == "implemented"
        assert surface["evidence"]["contract_id"] == contract_id
        assert surface["source_files"]
        assert "docs/reference/fabric/schema-compatibility.md" in surface["docs"]


def test_coverage_report_maps_requested_fabric_planes() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    coverage = manifest["coverage"]

    for key in (
        "source_contracts",
        "source_platform",
        "source_profiles",
        "replay_fixtures",
        "quality_contracts",
        "lineage_nodes_edges",
        "temporal_support",
        "access_classification",
        "discovery_intelligence",
        "public_facade_exports",
        "tests_by_plane",
    ):
        assert key in coverage

    assert coverage["source_contracts"]["fabric_registry_contracts"] >= 1
    assert coverage["source_platform"]["source_contract_v2_count"] >= 1
    assert (
        coverage["source_platform"]["replay_fixture_count"]
        == coverage["source_platform"]["source_contract_v2_count"]
    )
    assert coverage["source_platform"]["non_replayable_reason_count"] == 0
    assert (
        coverage["source_platform"]["field_policy_coverage_count"]
        == coverage["source_platform"]["source_contract_v2_count"]
    )
    assert coverage["source_platform"]["source_scorecard_count"] >= 1
    assert (
        coverage["source_platform"]["bounded_read_evidence_count"]
        == coverage["source_platform"]["source_contract_v2_count"]
    )
    assert coverage["discovery_intelligence"]["status"] == "implemented"
    assert coverage["discovery_intelligence"]["llm_calls"] == 0
    assert coverage["discovery_intelligence"]["eval_case_count"] >= 1
    assert coverage["access_classification"]["status"] == "implemented"
    assert coverage["source_profiles"]["profile_count"] >= 1
    assert coverage["public_facade_exports"]["export_count"] >= 1
    for plane in inventory.PLANES:
        assert coverage["tests_by_plane"][plane]


def test_existing_fabric_reference_docs_link_inventory() -> None:
    docs = [
        "connectors.md",
        "profiles.md",
        "data-plane.md",
        "schema-compatibility.md",
        "lineage.md",
        "quality.md",
        "source-platform.md",
        "time-travel.md",
        "discovery-intelligence.md",
    ]

    for doc in docs:
        page = (REPO_ROOT / "docs/reference/fabric" / doc).read_text(encoding="utf-8")
        assert "Best-in-class inventory: [best-in-class-inventory.md]" in page


def test_gap_surfaces_have_owner_follow_up_or_risk_metadata() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    surfaces = _surface_by_id(manifest)

    for surface in surfaces.values():
        status = surface["status"]
        if status in {"partial", "missing", "blocked_by_research"}:
            assert surface["owner"]
            assert surface["follow_up"]

    future = surfaces["world.future_table_snapshot_adapters"]
    assert future["status"] == "not_applicable"
    assert future["evidence"]["production_visible"] is False


def test_manifest_validation_rejects_malformed_gap_and_accepted_risk() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    malformed = deepcopy(manifest)
    surfaces = _surface_by_id(malformed)
    surfaces["world.temporal_graph_reasoning"].pop("follow_up")
    errors = inventory.validate_manifest_payload(malformed)
    assert any("gap surfaces require a follow_up" in error for error in errors)

    malformed = deepcopy(manifest)
    surfaces = _surface_by_id(malformed)
    risk_surface = surfaces["world.future_table_snapshot_adapters"]
    risk_surface["status"] = "accepted_risk"
    errors = inventory.validate_manifest_payload(malformed)
    assert any("accepted_risk metadata is required" in error for error in errors)


def test_render_markdown_includes_planes_gaps_and_validation_commands() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    page = inventory.render_markdown(manifest)

    assert "Phase 0 is report-only" in page
    assert "## Coverage Report" in page
    assert "## Tests By Plane" in page
    for plane in ("Source", "Evidence", "Semantics", "World", "Trust"):
        assert f"## {plane} Plane" in page
    assert "`trust.fabric_decision_envelope`" in page
    assert "`semantics.semantic_dataset_catalog`" in page
    assert "`world.discovery_graph_reasoning`" in page
    assert "uv run python tools/quality/validation/fabric_wave2_strict_closure.py --check" in page
    assert "uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check" in page


def test_checked_in_manifest_and_report_are_current() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    manifest_path = REPO_ROOT / "tools/quality/validation/fabric_best_in_class_manifest.json"
    report_path = REPO_ROOT / "docs/reference/fabric/best-in-class-inventory.md"

    assert manifest_path.read_text(encoding="utf-8") == inventory.dump_json(manifest)
    assert report_path.read_text(encoding="utf-8") == inventory.render_markdown(manifest)
    assert (
        inventory.check_artifacts(
            repo_root=REPO_ROOT,
            manifest_path=manifest_path,
            docs_path=report_path,
        )
        == []
    )


def test_check_artifacts_detects_manifest_drift(tmp_path: Path) -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    manifest_path = tmp_path / "fabric_best_in_class_manifest.json"
    report_path = tmp_path / "best-in-class-inventory.md"
    manifest_path.write_text("{}", encoding="utf-8")
    report_path.write_text(inventory.render_markdown(manifest), encoding="utf-8")

    drift = inventory.check_artifacts(
        repo_root=REPO_ROOT,
        manifest_path=manifest_path,
        docs_path=report_path,
    )

    assert drift == [f"manifest out of date: {manifest_path}"]
