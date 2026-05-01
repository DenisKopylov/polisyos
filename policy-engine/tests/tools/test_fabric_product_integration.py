from __future__ import annotations

from tools.quality.validation.fabric_product_integration import build_report, validate_report


def test_fabric_product_integration_report_is_complete() -> None:
    report = build_report()

    assert report["schema_version"] == "fabric.product_integration_report.v1"
    assert report["summary"]["runtime_endpoint_count"] >= 8
    assert report["summary"]["frontend_fixture_count"] >= 12
    assert validate_report(report) == []


def test_fabric_product_integration_public_facade_stays_governed() -> None:
    report = build_report()

    assert report["summary"]["public_facade_stable"] is True
    assert report["compatibility_errors"] == []
