from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

from polisyos.fabric.api import FabricDecisionData, fabric_get_data, run_connectors_ingestion

REPO_ROOT = Path(__file__).resolve().parents[3]
FABRIC_ROOT = REPO_ROOT / "src" / "polisyos" / "fabric"


def test_fabric_root_contains_only_facade_files() -> None:
    root_py_files = sorted(
        path.name for path in (REPO_ROOT / "src" / "polisyos" / "fabric").glob("*.py")
    )

    assert root_py_files == ["__init__.py", "api.py"]


def test_fabric_api_preserves_public_facade_imports() -> None:
    assert FabricDecisionData.__name__ == "FabricDecisionData"
    assert callable(fabric_get_data)
    assert callable(run_connectors_ingestion)


def test_fabric_medium_shims_are_removed_from_last_mile_import_map() -> None:
    retired_ids = {
        "fabric-connectors-sdk",
        "fabric-decision-data",
        "fabric-evidence",
        "fabric-safety",
    }
    retired_sources = {
        "polisyos.fabric.connectors.sdk",
        "polisyos.fabric.decision_data",
        "polisyos.fabric.evidence",
        "polisyos.fabric.safety",
    }
    planned = _planned_source_moves()

    assert retired_ids.isdisjoint({entry["id"] for entry in planned})
    assert retired_sources.isdisjoint({entry["source_fqn"] for entry in planned})


def test_fabric_phase_5_3_import_map_has_explicit_compatibility_behavior() -> None:
    supported_decisions = {
        "moved_with_reexport_shim",
        "retained_with_dated_exception",
        "removed_with_documented_release_note",
    }
    planned = [
        entry
        for entry in _planned_source_moves()
        if entry["owner"] == "team-fabric" and entry["wave"] == "3.1"
    ]

    for entry in planned:
        assert entry["decision"] in supported_decisions
        assert entry["release_note"].startswith("docs/archive/reports/")
        assert entry["sunset"] == "2026-12-31"
        if entry["decision"] == "removed_with_documented_release_note":
            assert entry.get("removal_release")
        else:
            assert entry["target_fqn"]


def test_removed_fabric_alias_imports_are_not_resolved() -> None:
    for module_name in ("polisyos.fabric.decision_data", "polisyos.fabric.safety"):
        assert _find_spec(module_name) is None


def test_fabric_phase_3_1_semantic_group_modules_exist() -> None:
    expected_modules = {
        "ingestion/ingestion.py",
        "ingestion/ingestion_providers.py",
        "connectors/ingestion/connectors_ingestion.py",
        "trust/trust.py",
        "trust/adapter.py",
        "quality/quality.py",
        "quality/fitness_report.py",
        "quality/processing_guarantees.py",
        "evidence/evidence.py",
        "evidence/fact_writer.py",
        "evidence/decision_data.py",
        "identity/manifest.py",
        "identity/segment_manifest.py",
        "numerics/finite.py",
        "data_plane/tabular.py",
        "data_plane/temporal.py",
        "config/config.py",
        "_adapters/observability.py",
        "world/query.py",
    }

    missing = sorted(
        relative_path
        for relative_path in expected_modules
        if not (FABRIC_ROOT / relative_path).is_file()
    )

    assert missing == []


def test_fabric_phase_3_1_removes_wrapper_only_shell_directories() -> None:
    retired_shell_directories = {
        "_connector_bridge",
        "_numeric_parsing",
        "compatibility",
        "connectors_ingestion",
        "decision_data",
        "fact_writer",
        "finite",
        "fitness_report",
        "ingestion_providers",
        "manifest",
        "observability",
        "processing_guarantees",
        "registry",
        "safety",
        "segment_manifest",
        "tabular",
        "temporal",
        "trust_adapter",
        "world_query",
    }

    still_present = sorted(
        relative_path
        for relative_path in retired_shell_directories
        if (FABRIC_ROOT / relative_path).is_dir()
    )

    assert still_present == []


def test_fabric_package_contract_covers_live_first_level_roots() -> None:
    package_contract = tomllib.loads(
        (REPO_ROOT / "architecture" / "packages" / "fabric.toml").read_text(
            encoding="utf-8"
        )
    )
    declared_roots = {
        Path(entry).name for entry in package_contract["layout"]["implementation_roots"]
    }
    live_roots = {
        path.name
        for path in FABRIC_ROOT.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }

    assert live_roots <= declared_roots


def _planned_source_moves() -> list[dict[str, object]]:
    payload = tomllib.loads((REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8"))
    return payload.get("planned_source_move", [])


def _find_spec(module_name: str) -> object | None:
    try:
        return importlib.util.find_spec(module_name)
    except ModuleNotFoundError:
        return None
