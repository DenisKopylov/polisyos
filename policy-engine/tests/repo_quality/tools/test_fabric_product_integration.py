from __future__ import annotations

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
