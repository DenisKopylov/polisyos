from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from tools.quality.validation import fabric_best_in_class_inventory as inventory

REPO_ROOT = Path(__file__).resolve().parents[3]


def _surface_by_id(manifest: dict[str, object]) -> dict[str, dict[str, object]]:
    surfaces = manifest["surfaces"]
    assert isinstance(surfaces, list)
    return {str(row["id"]): row for row in surfaces}


def test_module_file_prefers_package_initializer_over_sibling_module(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "src" / "polisyos" / "lex"
    legacy_candidate = source_root / "provenance.py"
    legacy_candidate.mkdir(parents=True)
    package_initializer = source_root / "provenance" / "__init__.py"
    package_initializer.parent.mkdir(parents=True)
    package_initializer.write_text("__all__ = []\n", encoding="utf-8")

    resolved, error = inventory._module_file(tmp_path, "polisyos.lex.provenance")

    assert resolved == package_initializer
    assert error is None

    legacy_candidate.rmdir()
    legacy_candidate.write_text("__all__ = []\n", encoding="utf-8")
    resolved, error = inventory._module_file(tmp_path, "polisyos.lex.provenance")
    assert resolved == package_initializer
    assert error is None


def test_module_file_rejects_invalid_and_unsupported_candidates(tmp_path: Path) -> None:
    source_root = tmp_path / "src" / "polisyos" / "lex"
    directory_candidate = source_root / "directory_candidate.py"
    directory_candidate.mkdir(parents=True)
    (source_root / "directory_candidate.pyi").write_text("value: int\n", encoding="utf-8")

    resolved, error = inventory._module_file(tmp_path, "polisyos.lex.directory_candidate")
    assert resolved == directory_candidate
    assert error == "module_missing"

    resolved, error = inventory._module_file(tmp_path, "polisyos.lex..invalid")
    assert resolved is None
    assert error == "module_outside_source_root"

    outside_file = tmp_path / "outside.py"
    outside_file.write_text("value = 1\n", encoding="utf-8")
    escaped_module = source_root / "escaped.py"
    escaped_module.symlink_to(outside_file)
    resolved, error = inventory._module_file(tmp_path, "polisyos.lex.escaped")
    assert resolved is None
    assert error == "module_outside_source_root"


def test_package_facade_marker_does_not_replace_missing_adapter_implementation(
    tmp_path: Path,
) -> None:
    facade = tmp_path / "src" / "polisyos" / "lex" / "provenance" / "__init__.py"
    facade.parent.mkdir(parents=True)
    facade.write_text("LexFabricEvidencePath = object\n", encoding="utf-8")

    kind, module_path, tree, class_node, error = inventory._resolve_class_symbol(
        tmp_path,
        "polisyos.lex.provenance.adapter",
        "LexFabricEvidencePath",
        {},
    )

    assert kind == "unknown"
    assert module_path is None
    assert tree is None
    assert class_node is None
    assert error == "module_missing"


def test_product_adapter_surface_tracks_lex_package_and_implementation() -> None:
    manifest = inventory.build_manifest(REPO_ROOT)
    surface = _surface_by_id(manifest)["trust.product_evidence_adapters"]

    assert surface["status"] == "implemented"
    assert surface["evidence"]["lex"] is True
    assert "src/polisyos/lex/provenance/__init__.py" in surface["source_files"]
    assert "src/polisyos/lex/provenance/adapter.py" in surface["source_files"]
    assert "tests/unit/lex/provenance/test_adapter.py" in surface["tests"]


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

    assert (
        "Source of truth: `tools/quality/validation/fabric_best_in_class_inventory.py`, "
        "`tools/quality/validation/fabric_best_in_class_manifest.json`, and repository "
        "source inputs listed in the manifest's `input_receipt`."
    ) in page
    assert "Phase 0 is report-only" in page
    assert "## Coverage Report" in page
    assert "## Tests By Plane" in page
    for plane in ("Source", "Evidence", "Semantics", "World", "Trust"):
        assert f"## {plane} Plane" in page
    assert "`trust.fabric_decision_envelope`" in page
    assert "`semantics.semantic_dataset_catalog`" in page
    assert "`world.discovery_graph_reasoning`" in page
    assert "uv run python tools/quality/validation/fabric_wave2_strict_closure.py --check" in page
    assert (
        "uv run python tools/quality/validation/fabric_best_in_class_inventory.py --check" in page
    )


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


def _write_connector_fixture(root: Path, *, include_beta: bool = False) -> None:
    source_dir = root / "src/polisyos/fabric/connectors/sources"
    source_dir.mkdir(parents=True, exist_ok=True)
    (root / "src/polisyos/fabric/connectors").mkdir(parents=True, exist_ok=True)
    (root / "src/polisyos/fabric/connectors/base.py").write_text(
        "from typing import ClassVar, Protocol\n"
        "class SourceConnector(Protocol):\n"
        "    connector_id: ClassVar[str]\n"
        "    capabilities: ClassVar[int]\n"
        "    metadata: ClassVar[dict[str, str]]\n"
        "class BaseConnector:\n"
        "    connector_id: ClassVar[str] = 'base.connector'\n"
        "    capabilities: ClassVar[int] = 0\n"
        "    metadata: ClassVar[dict[str, str]]\n",
        encoding="utf-8",
    )
    (source_dir / "sample.py").write_text(
        "from typing import Protocol\n"
        "from polisyos.fabric.connectors.base import BaseConnector\n"
        "raise RuntimeError('connector source must not be imported for inventory')\n"
        "class AlphaConnector(BaseConnector):\n"
        "    connector_id = 'alpha'\n"
        "    capabilities = 1\n"
        "    metadata = {}\n"
        "class HiddenConnector(BaseConnector):\n"
        "    connector_id = 'hidden'\n"
        "    capabilities = 1\n"
        "    metadata = {}\n"
        "class HelperConnector(BaseConnector):\n"
        "    pass\n"
        "class AlphaProtocol(Protocol):\n"
        "    connector_id: str\n"
        "def normalize_rows(value):\n"
        "    return value\n"
        + (
            "class BetaConnector(BaseConnector):\n"
            "    connector_id = 'beta'\n"
            "    capabilities = 1\n"
            "    metadata = {}\n"
            if include_beta
            else ""
        ),
        encoding="utf-8",
    )
    exports = ["AlphaConnector", "AlphaProtocol", "HelperConnector", "normalize_rows"]
    if include_beta:
        exports.append("BetaConnector")
    (source_dir / "__init__.py").write_text(
        "from polisyos.fabric.connectors.sources.sample import (\n"
        + "".join(f"    {name},\n" for name in exports)
        + ")\n__all__ = [\n"
        + "".join(f"    {name!r},\n" for name in exports)
        + "]\n",
        encoding="utf-8",
    )


def _connector_export_evidence(root: Path) -> dict[str, object]:
    manifest = inventory.build_manifest(root)
    return _surface_by_id(manifest)["source.connector_public_exports"]["evidence"]


def test_concrete_exports_resolve_declared_connector_classes_only(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)

    evidence = _connector_export_evidence(tmp_path)

    assert evidence["concrete_connectors"] == ["AlphaConnector"]
    assert evidence["concrete_connector_count"] == 1
    assert evidence["export_count"] == 4
    assert evidence["declared_exports"] == [
        "AlphaConnector",
        "AlphaProtocol",
        "HelperConnector",
        "normalize_rows",
    ]
    assert {row["export"] for row in evidence["excluded_exports"]} == {
        "AlphaProtocol",
        "HelperConnector",
        "normalize_rows",
    }
    excluded_by_name = {row["export"]: row["reason"] for row in evidence["excluded_exports"]}
    assert "missing_declared_SourceConnector_slots" in excluded_by_name["HelperConnector"]
    assert "HiddenConnector" not in evidence["declared_exports"]
    assert evidence["inventory_complete"] is True
    assert evidence["unresolved_exports"] == []


def test_added_declared_connector_changes_count_and_input_receipt(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    before = inventory.build_manifest(tmp_path)
    _write_connector_fixture(tmp_path, include_beta=True)

    after = inventory.build_manifest(tmp_path)
    evidence = _surface_by_id(after)["source.connector_public_exports"]["evidence"]

    assert evidence["concrete_connectors"] == ["AlphaConnector", "BetaConnector"]
    assert evidence["concrete_connector_count"] == 2
    assert before["input_receipt"] != after["input_receipt"]
    receipt_paths = {row["path"] for row in after["input_receipt"]["inputs"]}
    assert "src/polisyos/fabric/connectors/sources/sample.py" in receipt_paths


def test_connector_property_removal_keeps_name_but_stops_counting(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    before = _connector_export_evidence(tmp_path)
    source = tmp_path / "src/polisyos/fabric/connectors/sources/sample.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "class AlphaConnector(BaseConnector):", "class AlphaConnector(object):"
        ),
        encoding="utf-8",
    )

    after = _connector_export_evidence(tmp_path)

    assert before["concrete_connectors"] == ["AlphaConnector"]
    assert after["concrete_connectors"] == []
    assert after["concrete_connector_count"] == 0
    assert after["export_count"] == before["export_count"]


def test_unreadable_export_module_is_receipted_and_makes_coverage_partial(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_connector_fixture(tmp_path)
    original_read_text = Path.read_text

    def unread_sample(path: Path, *args, **kwargs) -> str:
        if path.name == "sample.py":
            raise PermissionError("fixture marks the exported class module unreadable")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unread_sample)
    manifest = inventory.build_manifest(tmp_path)
    surface = _surface_by_id(manifest)["source.connector_public_exports"]
    evidence = surface["evidence"]
    receipt_rows = manifest["input_receipt"]["inputs"]

    assert surface["status"] == "partial"
    assert evidence["inventory_complete"] is False
    assert any(
        "unreadable:PermissionError" in row["reason"] for row in evidence["unresolved_exports"]
    )
    assert any(
        row["path"] == "src/polisyos/fabric/connectors/sources/sample.py"
        and row["operation"] == "read_text"
        and row["status"] == "unreadable"
        for row in receipt_rows
    )


def test_markdown_binds_compactly_and_cli_check_prints_full_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    _write_connector_fixture(tmp_path)
    manifest_path = tmp_path / "artifacts/manifest.json"
    report_path = tmp_path / "artifacts/report.md"
    manifest = inventory.update_artifacts(
        repo_root=tmp_path,
        manifest_path=manifest_path,
        docs_path=report_path,
    )
    page = inventory.render_markdown(manifest)

    assert "## Input Receipt" in page
    assert (
        f"Receipt SHA-256: `{inventory._input_receipt_digest(manifest['input_receipt'])}`" in page
    )
    assert "matched_paths" not in page
    assert (
        inventory.main(
            [
                "--repo-root",
                str(tmp_path),
                "--manifest",
                "artifacts/manifest.json",
                "--docs-out",
                "artifacts/report.md",
                "--check",
            ]
        )
        == 0
    )
    stdout = capsys.readouterr().out
    assert "Input receipt (explicit operations; incomplete by construction):" in stdout
    assert "src/polisyos/fabric/connectors/sources/sample.py" in stdout
    assert '"text_sha256"' in stdout


def test_markdown_preserves_source_scope_and_selector_as_literal_text(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    manifest = inventory.build_manifest(tmp_path)
    receipt = manifest["input_receipt"]

    page = inventory.render_markdown(manifest)

    assert receipt["complete_verdict"] is False
    assert f"Scope: `{receipt['scope']}`" in page
    assert f"Selector: `{receipt['selector']}`" in page
    assert "complete verdict: `false`" in page
    assert "`concrete_connector_count`=1" in page
    assert "src/polisyos/fabric/connectors/sources/__init__.py::__all__" in page


def test_unresolved_declared_connector_import_makes_coverage_partial(tmp_path: Path) -> None:
    source_dir = tmp_path / "src/polisyos/fabric/connectors/sources"
    source_dir.mkdir(parents=True)
    (source_dir / "__init__.py").write_text(
        "from polisyos.fabric.connectors.sources.missing import MissingConnector\n"
        "__all__ = ['MissingConnector']\n",
        encoding="utf-8",
    )

    manifest = inventory.build_manifest(tmp_path)
    surface = _surface_by_id(manifest)["source.connector_public_exports"]
    evidence = surface["evidence"]

    assert surface["status"] == "partial"
    assert evidence["inventory_complete"] is False
    assert evidence["concrete_connector_count"] == 0
    assert evidence["unresolved_exports"]
    assert "missing" in json.dumps(evidence["unresolved_exports"]).lower()


def test_dynamic_public_export_list_remains_partial(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    source_dir = tmp_path / "src/polisyos/fabric/connectors/sources"
    (source_dir / "__init__.py").write_text(
        "__all__ = ['ConnectorCandidate'] + dynamic_exports\n",
        encoding="utf-8",
    )

    surface = _surface_by_id(inventory.build_manifest(tmp_path))["source.connector_public_exports"]
    evidence = surface["evidence"]

    assert surface["status"] == "partial"
    assert evidence["inventory_complete"] is False
    assert evidence["unresolved_exports"] == [
        {
            "export": "__all__",
            "reason": "dynamic_or_non_string_public_export_list",
        }
    ]


def test_mutated_public_export_list_remains_partial(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    source_init = tmp_path / "src/polisyos/fabric/connectors/sources/__init__.py"
    source_init.write_text(
        "from polisyos.fabric.connectors.sources.sample import AlphaConnector\n"
        "__all__ = ['AlphaConnector']\n"
        "__all__.append('DynamicConnector')\n",
        encoding="utf-8",
    )

    surface = _surface_by_id(inventory.build_manifest(tmp_path))["source.connector_public_exports"]
    evidence = surface["evidence"]

    assert surface["status"] == "partial"
    assert evidence["inventory_complete"] is False
    assert evidence["unresolved_exports"] == [
        {
            "export": "__all__",
            "reason": "dynamic_or_non_string_public_export_list",
        }
    ]


def test_aliased_mutated_public_export_list_makes_manifest_partial(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    source_init = tmp_path / "src/polisyos/fabric/connectors/sources/__init__.py"
    source_init.write_text(
        "from polisyos.fabric.connectors.sources.sample import AlphaConnector\n"
        "__all__ = exported = ['AlphaConnector']\n"
        "exported.append('BetaConnector')\n",
        encoding="utf-8",
    )

    manifest = inventory.build_manifest(tmp_path)
    surface = _surface_by_id(manifest)["source.connector_public_exports"]

    assert surface["status"] == "partial"
    assert surface["evidence"]["inventory_complete"] is False
    assert surface["evidence"]["concrete_connector_count"] == 0
    assert surface["evidence"]["unresolved_exports"] == [
        {
            "export": "__all__",
            "reason": "aliased_or_multi_target_public_export_assignment",
        }
    ]


def test_rebound_exported_class_makes_manifest_partial(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    sample = tmp_path / "src/polisyos/fabric/connectors/sources/sample.py"
    sample.write_text(
        sample.read_text(encoding="utf-8") + "AlphaConnector = object\n",
        encoding="utf-8",
    )

    manifest = inventory.build_manifest(tmp_path)
    surface = _surface_by_id(manifest)["source.connector_public_exports"]

    assert surface["status"] == "partial"
    assert surface["evidence"]["inventory_complete"] is False
    assert surface["evidence"]["concrete_connector_count"] == 0
    assert surface["evidence"]["unresolved_exports"] == [
        {"export": "AlphaConnector", "reason": "symbol_rebound_in_module"}
    ]


def test_equal_family_counts_with_different_ids_remain_partial(tmp_path: Path) -> None:
    _write_connector_fixture(tmp_path)
    snapshot = tmp_path / "schemas/snapshots/fabric/source_contracts_v2.json"
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(
        json.dumps(
            {
                "contracts": {
                    "other.connector.contract": {
                        "connector_id": "other.connector",
                        "contract": {"id": "other.connector.contract"},
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    validator = tmp_path / "tools/quality/validation/fabric_source_contracts.py"
    validator.parent.mkdir(parents=True, exist_ok=True)
    validator.write_text("# source-contract validator marker\n", encoding="utf-8")

    manifest = inventory.build_manifest(tmp_path)
    surface = _surface_by_id(manifest)["source.entrypoint_coverage.direct_import_families"]

    assert surface["evidence"]["concrete_connector_count"] == 1
    assert surface["evidence"]["source_contract_v2_count"] == 1
    assert surface["evidence"]["source_contracts_validator_present"] is True
    assert surface["status"] == "partial"
    assert surface["evidence"]["mapped_identity_status"] == "not_established"
    assert surface["evidence"]["source_family_state"] == "partial"
