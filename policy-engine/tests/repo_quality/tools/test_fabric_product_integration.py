from __future__ import annotations

from pathlib import Path

import pytest

from tools.quality.validation import fabric_product_integration


def test_fabric_product_integration_report_is_complete() -> None:
    report = fabric_product_integration.build_report()

    assert report["schema_version"] == "fabric.product_integration_report.v1"
    assert report["summary"]["runtime_endpoint_count"] >= 8
    assert report["summary"]["frontend_fixture_count"] >= 12
    assert fabric_product_integration.validate_report(report) == []


def test_fabric_product_integration_public_facade_stays_governed() -> None:
    report = fabric_product_integration.build_report()

    assert report["summary"]["public_facade_stable"] is True
    assert report["compatibility_errors"] == []


def test_fabric_scholar_adapter_reads_relocated_owner_and_rejects_old_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapters = fabric_product_integration.PRODUCT_ADAPTERS
    scholar_adapter = next(row for row in adapters if row["id"] == "scholar.fabric_citation")
    assert scholar_adapter["path"] == ("src/polisyos/scholar/orchestrator/provenance.py")

    report = fabric_product_integration.build_report()
    row = next(
        row for row in report["product_evidence_adapters"] if row["id"] == "scholar.fabric_citation"
    )
    assert row["status"] == "implemented"

    old_path_adapters = tuple(
        {
            **adapter,
            "path": "src/polisyos/scholar/provenance.py",
        }
        if adapter["id"] == "scholar.fabric_citation"
        else adapter
        for adapter in adapters
    )
    monkeypatch.setattr(fabric_product_integration, "PRODUCT_ADAPTERS", old_path_adapters)
    removed_owner_report = fabric_product_integration.build_report()
    removed_row = next(
        row
        for row in removed_owner_report["product_evidence_adapters"]
        if row["id"] == "scholar.fabric_citation"
    )
    assert removed_row["status"] == "missing"
    assert any(
        "scholar.fabric_citation" in error
        for error in fabric_product_integration.validate_report(removed_owner_report)
    )


def test_fabric_lex_adapter_resolves_package_facade_to_typed_implementation() -> None:
    row = next(
        row
        for row in fabric_product_integration._adapter_rows(fabric_product_integration.REPO_ROOT)
        if row["id"] == "lex.fabric_evidence"
    )

    assert row["status"] == "implemented"
    assert row["path"] == "src/polisyos/lex/provenance/__init__.py"
    assert row["implementation_path"] == "src/polisyos/lex/provenance/adapter.py"
    assert row["tokens"] == [
        "LexFabricEvidencePath",
        "lex_evidence_from_evidence_path",
        "lex_evidence_from_fabric_decision_data",
    ]
    assert row["source_resolution"] == {
        "facade": "resolved",
        "implementation": "resolved",
        "exports_resolved": True,
        "implementation_symbols_resolved": True,
        "facade_dispatch_resolved": True,
        "test_present": True,
    }


def test_fabric_lex_adapter_rejects_marker_only_legacy_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = next(
        row
        for row in fabric_product_integration.PRODUCT_ADAPTERS
        if row["id"] == "lex.fabric_evidence"
    )
    monkeypatch.setattr(fabric_product_integration, "PRODUCT_ADAPTERS", (adapter,))
    legacy_module = tmp_path / "src/polisyos/lex/provenance.py"
    legacy_module.parent.mkdir(parents=True)
    legacy_module.write_text(
        "LexFabricEvidencePath lex_evidence_from_evidence_path "
        "lex_evidence_from_fabric_decision_data\n",
        encoding="utf-8",
    )

    row = fabric_product_integration._adapter_rows(tmp_path)[0]

    assert row["status"] == "missing"
    assert row["source_resolution"]["facade"] == "resolved"
    assert row["source_resolution"]["implementation"] == "module_missing"
    assert row["source_resolution"]["implementation_symbols_resolved"] is False


def test_fabric_lex_adapter_rejects_facade_exports_without_implementation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = next(
        row
        for row in fabric_product_integration.PRODUCT_ADAPTERS
        if row["id"] == "lex.fabric_evidence"
    )
    monkeypatch.setattr(fabric_product_integration, "PRODUCT_ADAPTERS", (adapter,))
    facade = tmp_path / "src/polisyos/lex/provenance/__init__.py"
    implementation = facade.parent / "adapter.py"
    facade.parent.mkdir(parents=True)
    facade.write_text(
        "__all__ = ['LexFabricEvidencePath', 'lex_evidence_from_evidence_path', "
        "'lex_evidence_from_fabric_decision_data']\n"
        "_EXPORTS = {'LexFabricEvidencePath': 'LexFabricEvidencePath', "
        "'lex_evidence_from_evidence_path': 'lex_evidence_from_evidence_path', "
        "'lex_evidence_from_fabric_decision_data': 'lex_evidence_from_fabric_decision_data'}\n"
        "import importlib\n"
        "def __getattr__(name):\n"
        "    if name not in _EXPORTS:\n"
        "        raise AttributeError(name)\n"
        "    module = importlib.import_module(f'{__name__}.adapter')\n"
        "    value = getattr(module, _EXPORTS[name])\n"
        "    globals()[name] = value\n"
        "    return value\n",
        encoding="utf-8",
    )
    implementation.write_text(
        "# Marker names alone are not source definitions: LexFabricEvidencePath "
        "lex_evidence_from_evidence_path lex_evidence_from_fabric_decision_data\n",
        encoding="utf-8",
    )

    row = fabric_product_integration._adapter_rows(tmp_path)[0]

    assert row["status"] == "missing"
    assert row["source_resolution"]["facade_dispatch_resolved"] is True
    assert row["source_resolution"]["exports_resolved"] is True
    assert row["source_resolution"]["implementation_symbols_resolved"] is False


def test_fabric_lex_adapter_prefers_package_over_marker_only_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    adapter = next(
        row
        for row in fabric_product_integration.PRODUCT_ADAPTERS
        if row["id"] == "lex.fabric_evidence"
    )
    monkeypatch.setattr(fabric_product_integration, "PRODUCT_ADAPTERS", (adapter,))
    package = tmp_path / "src/polisyos/lex/provenance"
    package.mkdir(parents=True)
    (tmp_path / "src/polisyos/lex/provenance.py").write_text(
        "LexFabricEvidencePath lex_evidence_from_evidence_path "
        "lex_evidence_from_fabric_decision_data\n",
        encoding="utf-8",
    )
    (package / "__init__.py").write_text(
        "__all__ = ['LexFabricEvidencePath', 'lex_evidence_from_evidence_path', "
        "'lex_evidence_from_fabric_decision_data']\n"
        "_EXPORTS = {'LexFabricEvidencePath': 'LexFabricEvidencePath', "
        "'lex_evidence_from_evidence_path': 'lex_evidence_from_evidence_path', "
        "'lex_evidence_from_fabric_decision_data': 'lex_evidence_from_fabric_decision_data'}\n"
        "import importlib\n"
        "def __getattr__(name):\n"
        "    if name not in _EXPORTS:\n"
        "        raise AttributeError(name)\n"
        "    module = importlib.import_module(f'{__name__}.adapter')\n"
        "    value = getattr(module, _EXPORTS[name])\n"
        "    globals()[name] = value\n"
        "    return value\n",
        encoding="utf-8",
    )
    (package / "adapter.py").write_text(
        "class LexFabricEvidencePath: pass\n"
        "def lex_evidence_from_evidence_path(value): return value\n"
        "def lex_evidence_from_fabric_decision_data(value): return value\n",
        encoding="utf-8",
    )
    semantic_test = tmp_path / "tests/unit/lex/provenance/test_adapter.py"
    semantic_test.parent.mkdir(parents=True)
    semantic_test.write_text("def test_adapter(): pass\n", encoding="utf-8")

    row = fabric_product_integration._adapter_rows(tmp_path)[0]

    assert row["status"] == "implemented"
    assert row["path"] == "src/polisyos/lex/provenance/__init__.py"
    assert row["implementation_path"] == "src/polisyos/lex/provenance/adapter.py"
    assert row["source_resolution"]["facade"] == "resolved"
    assert row["source_resolution"]["implementation"] == "resolved"
    assert row["source_resolution"]["implementation_symbols_resolved"] is True
