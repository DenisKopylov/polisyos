from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from polisyos.fabric.pii.detector import PresidioConfig, PresidioDetector
from polisyos.fabric.pii.models import PIISeverity
from polisyos.fabric.pii.stage import PIIDetectionStage
from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy


def _make_fetch_result(df: pd.DataFrame) -> FetchResult[pd.DataFrame]:
    now = datetime.now(timezone.utc)
    return FetchResult(
        data=df,
        row_count=len(df),
        schema_id="test.schema",
        schema_version="1.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value="sha256:" + "1" * 64,
            timestamp=now,
            content_hash="sha256:" + "1" * 64,
        ),
        fetched_at=now,
        source_updated_at=now,
        completeness=1.0,
        quality_tier=QualityTier.SILVER,
        quality_flags=frozenset(),
        has_more=False,
        next_page_token=None,
        total_count=len(df),
        fetch_duration_ms=12.0,
        bytes_transferred=1024,
    )


def test_detector_finds_multiple_pii_types() -> None:
    detector = PresidioDetector(PresidioConfig(score_threshold=0.5, sample_rate=1.0))

    df = pd.DataFrame(
        {
            "email": ["john@example.com", "jane@gov.uk"],
            "phone": ["+1-555-123-4567", "+44 20 7946 0958"],
            "tax_id": ["12-3456789", "98-7654321"],
            "ssn": ["123-45-6789", "987-65-4321"],
            "beneficiary": ["BEN-123456", "BENF_789012"],
            "case_ref": ["CASE-123456", "REF_556677"],
            "ip": ["10.0.0.1", "192.168.1.5"],
        }
    )

    result = detector.scan_dataframe(df)

    assert result.total_entities_found > 0
    assert len(result.entities_by_type) >= 5
    assert result.max_severity in {PIISeverity.HIGH, PIISeverity.CRITICAL}


def test_detector_sampling_for_large_frames() -> None:
    detector = PresidioDetector(
        PresidioConfig(
            score_threshold=0.7,
            sample_rate=0.1,
            sample_min_rows=100,
        )
    )

    df = pd.DataFrame(
        {
            "email": [f"user{i}@example.com" for i in range(1000)],
            "value": list(range(1000)),
        }
    )

    result = detector.scan_dataframe(df)
    assert result.sampled is True
    assert result.sample_rate == 0.1
    assert result.total_records_scanned == 100


def test_stage_attaches_pii_scan_to_fetch_result() -> None:
    stage = PIIDetectionStage(
        detector=PresidioDetector(PresidioConfig(score_threshold=0.5, sample_rate=1.0))
    )
    result = _make_fetch_result(
        pd.DataFrame({"email": ["one@example.com"], "tax_id": ["12-3456789"]})
    )

    updated, scan = stage.process_fetch_result(result)

    assert updated.pii_scan is not None
    assert updated.pii_scan.total_entities_found == scan.total_entities_found
    assert any(flag.startswith("pii:") for flag in updated.quality_flags)


def test_empty_dataframe_returns_none_severity() -> None:
    detector = PresidioDetector(PresidioConfig())
    result = detector.scan_dataframe(pd.DataFrame())

    assert result.total_entities_found == 0
    assert result.max_severity == PIISeverity.NONE
