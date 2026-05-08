from __future__ import annotations

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


def test_fabric_phase_0_3_import_map_declares_shell_group_targets() -> None:
    expected_targets = {
        "polisyos.fabric._connector_bridge": "polisyos.fabric",
        "polisyos.fabric._numeric_parsing": "polisyos.fabric._internal.numeric_parsing",
        "polisyos.fabric.compatibility": "polisyos.fabric._internal.compatibility",
        "polisyos.fabric.config": "polisyos.fabric.config.config",
        "polisyos.fabric.connectors.sdk": "polisyos.fabric.connectors.sdk.scaffold",
        "polisyos.fabric.connectors_ingestion": (
            "polisyos.fabric.connectors.ingestion.connectors_ingestion"
        ),
        "polisyos.fabric.decision_data": "polisyos.fabric.evidence.decision_data",
        "polisyos.fabric.evidence": "polisyos.fabric.evidence.evidence",
        "polisyos.fabric.extensions": "polisyos.fabric.extensions.api",
        "polisyos.fabric.fact_writer": "polisyos.fabric.evidence.fact_writer",
        "polisyos.fabric.finite": "polisyos.fabric.numerics.finite",
        "polisyos.fabric.fitness_report": "polisyos.fabric.quality.fitness_report",
        "polisyos.fabric.ingestion_providers": (
            "polisyos.fabric.ingestion.ingestion_providers"
        ),
        "polisyos.fabric.manifest": "polisyos.fabric.identity.manifest",
        "polisyos.fabric.observability": "polisyos.fabric._adapters.observability",
        "polisyos.fabric.processing_guarantees": (
            "polisyos.fabric.quality.processing_guarantees"
        ),
        "polisyos.fabric.product_integration": "polisyos.fabric.product_integration",
        "polisyos.fabric.registry": "polisyos.fabric._internal.registry",
        "polisyos.fabric.safety": "polisyos.fabric.quality.safety",
        "polisyos.fabric.segment_manifest": "polisyos.fabric.identity.segment_manifest",
        "polisyos.fabric.tabular": "polisyos.fabric.data_plane.tabular",
        "polisyos.fabric.temporal": "polisyos.fabric.data_plane.temporal",
        "polisyos.fabric.trust": "polisyos.fabric.trust.trust",
        "polisyos.fabric.trust_adapter": "polisyos.fabric.trust.adapter",
        "polisyos.fabric.world_query": "polisyos.fabric.world.query",
    }
    planned = _planned_source_moves_by_source()

    for source_fqn, target_fqn in expected_targets.items():
        entry = planned[source_fqn]

        assert entry["target_fqn"] == target_fqn
        assert entry["owner"] == "team-fabric"
        assert entry["sunset"] == "2026-12-31"
        assert entry["test"].endswith(
            "test_fabric_phase_0_3_import_map_declares_shell_group_targets"
        )


def test_fabric_phase_5_3_import_map_has_explicit_compatibility_behavior() -> None:
    supported_decisions = {
        "moved_with_reexport_shim",
        "retained_with_dated_exception",
        "removed_with_documented_release_note",
    }
    planned = [
        entry
        for entry in _planned_source_moves_by_source().values()
        if entry["owner"] == "team-fabric" and entry["wave"] == "3.1"
    ]

    assert planned
    for entry in planned:
        assert entry["decision"] in supported_decisions
        assert entry["release_note"].startswith("docs/archive/reports/")
        assert entry["sunset"] == "2026-12-31"
        if entry["decision"] == "removed_with_documented_release_note":
            assert entry.get("removal_release")
        else:
            assert entry["target_fqn"]


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


def _planned_source_moves_by_source() -> dict[str, dict[str, object]]:
    payload = tomllib.loads((REPO_ROOT / "architecture/shims.toml").read_text(encoding="utf-8"))
    return {entry["source_fqn"]: entry for entry in payload["planned_source_move"]}
