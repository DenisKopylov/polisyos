from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytest.importorskip("aiohttp")

FORBIDDEN_HELPERS = frozenset(
    {
        "_get_session",
        "_request_json",
        "_retry_after_seconds",
        "_build_version",
        "_parse_http_datetime",
        "_frame_completeness",
        "_safe_int",
        "_safe_float",
    }
)

CONNECTOR_CLASSES = {
    "world_bank.py": "WorldBankConnector",
    "wvs.py": "WVSConnector",
    "eurostat.py": "EurostatConnector",
    "ukons.py": "UKONSConnector",
}


def _sources_root() -> Path:
    return Path(__file__).resolve().parents[4] / "src" / "polisyos" / "fabric" / "connectors" / "sources"


def test_production_connectors_subclass_http_connector_base() -> None:
    from polisyos.fabric.connectors.sources.eurostat import EurostatConnector
    from polisyos.fabric.connectors.sources.http_base import HTTPConnectorBase
    from polisyos.fabric.connectors.sources.ukons import UKONSConnector
    from polisyos.fabric.connectors.sources.wvs import WVSConnector
    from polisyos.fabric.connectors.sources.world_bank import WorldBankConnector

    assert issubclass(WorldBankConnector, HTTPConnectorBase)
    assert issubclass(WVSConnector, HTTPConnectorBase)
    assert issubclass(EurostatConnector, HTTPConnectorBase)
    assert issubclass(UKONSConnector, HTTPConnectorBase)


def test_no_forbidden_helper_definitions_in_production_sources() -> None:
    root = _sources_root()
    for filename, class_name in CONNECTOR_CLASSES.items():
        path = root / filename
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

        connector_class = next(
            (
                node
                for node in tree.body
                if isinstance(node, ast.ClassDef) and node.name == class_name
            ),
            None,
        )
        assert connector_class is not None, f"Missing {class_name} in {filename}"

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert (
                    node.name not in FORBIDDEN_HELPERS
                ), f"{filename} defines forbidden module helper {node.name}"

        for node in connector_class.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert (
                    node.name not in FORBIDDEN_HELPERS
                ), f"{filename} defines forbidden connector helper {node.name}"
