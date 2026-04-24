from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pandas as pd

from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.fabric.data_plane.quarantine import list_quarantine_records
from polisyos.fabric.ingestion import _apply_transform_pipeline, _sanitize_fetch_result
from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy


def _fetch_result(data) -> FetchResult:
    now = datetime.now(UTC)
    return FetchResult(
        data=data,
        row_count=len(data),
        schema_id="test.schema",
        schema_version="1.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value="sha256:" + ("a" * 64),
            timestamp=now,
            content_hash="sha256:" + ("a" * 64),
        ),
        fetched_at=now,
        completeness=1.0,
        quality_tier=QualityTier.SILVER,
    )


def test_row_isolation_quarantines_bad_transform_rows_without_losing_batch(tmp_path):
    class ValidationTransform:
        pass

    class FakePipeline:
        def compile(self):
            return SimpleNamespace(
                stages=[SimpleNamespace(name="validate", transform=ValidationTransform())]
            )

        def apply(self, data, context=None):
            del context
            if data["value"].astype(str).str.contains("bad").any():
                raise RuntimeError("bad row")
            return SimpleNamespace(data=data.assign(status="ok"), warnings=[])

    store = FileSystemCAS(tmp_path / "cas")
    result, _graph, warnings, quarantined = _apply_transform_pipeline(
        _fetch_result(pd.DataFrame({"value": ["ok", "bad", "ok2"]})),
        FakePipeline(),
        connector_id="test.conn",
        dataset_id="demo",
        cas_store=store,
    )

    assert quarantined == 1
    assert result.row_count == 2
    assert any("row isolation fallback" in warning for warning in warnings)
    records = list_quarantine_records(store, source="connector.transform:test.conn:demo")
    assert len(records) == 1
    assert records[0][1].reason == "transform_error"


def test_non_finite_metrics_are_quarantined_per_row(tmp_path):
    store = FileSystemCAS(tmp_path / "cas")
    result, warnings, quarantined = _sanitize_fetch_result(
        _fetch_result(
            [
                {"metric_value": 1.5, "country": "US"},
                {"metric_value": float("inf"), "country": "UA"},
                {"metric_value": 2.0, "country": "DE"},
            ]
        ),
        connector_id="test.conn",
        dataset_id="demo",
        cas_store=store,
    )

    assert quarantined == 1
    assert result.row_count == 2
    assert any("non_finite_metric" in warning for warning in warnings)
    records = list_quarantine_records(store, source="connector.fetch:test.conn:demo")
    assert len(records) == 1
    assert records[0][1].reason == "non_finite_metric"
