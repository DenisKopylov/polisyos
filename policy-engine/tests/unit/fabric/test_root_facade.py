from __future__ import annotations

from pathlib import Path

from polisyos.fabric.api import FabricDecisionData, fabric_get_data, run_connectors_ingestion

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_fabric_root_contains_only_facade_files() -> None:
    root_py_files = sorted(
        path.name for path in (REPO_ROOT / "src" / "polisyos" / "fabric").glob("*.py")
    )

    assert root_py_files == ["__init__.py", "api.py"]


def test_fabric_api_preserves_public_facade_imports() -> None:
    assert FabricDecisionData.__name__ == "FabricDecisionData"
    assert callable(fabric_get_data)
    assert callable(run_connectors_ingestion)
