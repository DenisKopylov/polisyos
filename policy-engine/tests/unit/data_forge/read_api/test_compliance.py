from __future__ import annotations

from datetime import UTC, datetime

from polisyos.data_forge.read_api import (
    build_privacy_compliance_report,
    normalize_privacy_compliance_report,
)
from polisyos.data_forge.read_api.compliance import (
    build_privacy_compliance_report as build_report_from_surface,
)


def test_compliance_read_api_builds_runtime_safe_report_without_raw_records() -> None:
    report = build_report_from_surface(
        production_data_sources=[
            {
                "source_id": "source.ua.registry",
                "fields": [{"name": "tax_id", "redaction_status": "masked"}],
                "license": "cc-by",
                "public_export_allowed": True,
                "internal_note": "not part of public summary",
            }
        ],
        generated_at=datetime(2026, 5, 28, tzinfo=UTC),
    )

    assert report["schema_version"] == "policyos.privacy_compliance_report.v1"
    assert report["status"] == "pass"
    assert report["summary"]["production_data_source_count"] == 1
    assert report["production_data_sources"][0]["source_id"] == "source.ua.registry"
    assert "internal_note" not in report["production_data_sources"][0]


def test_compliance_facade_normalizes_blocking_issue_status() -> None:
    normalized = normalize_privacy_compliance_report(
        {
            "status": "unknown",
            "issues": [
                {
                    "code": "public_export_not_allowed",
                    "severity": "blocking",
                }
            ],
        }
    )

    assert normalized["status"] == "fail"
    assert normalized["summary"]["blocking_issue_count"] == 1
    assert build_privacy_compliance_report is build_report_from_surface
