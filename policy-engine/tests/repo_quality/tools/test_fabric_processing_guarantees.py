from __future__ import annotations

from tools.quality.validation import fabric_processing_guarantees


def test_processing_guarantee_report_is_check_ready() -> None:
    report = fabric_processing_guarantees.build_report()

    assert report["schema_version"] == fabric_processing_guarantees.REPORT_SCHEMA_VERSION
    assert report["source_contract_count"] == 20
    assert report["exactly_once_claim_count"] == 0
    assert fabric_processing_guarantees.validate_report(report) == []
    assert any(
        row["guarantee"] == "at_least_once_with_dedupe"
        for row in report["streaming_contracts"]
    )


def test_processing_guarantee_gate_main_check_passes() -> None:
    assert fabric_processing_guarantees.main(["--check"]) == 0
