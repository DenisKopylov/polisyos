"""Orchestrator tests for the raw connector-result sink boundary."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from polisyos.fabric.data_plane.orchestrator import run_orchestrated_ingestion
from polisyos.ir.connectors import (
    DataVersion,
    FetchRequest,
    FetchResult,
    QualityTier,
    VersionStrategy,
)

if TYPE_CHECKING:
    from pathlib import Path


def _raw_result() -> FetchResult[list[dict[str, int]]]:
    now = datetime.now(UTC)
    digest = "sha256:" + ("b" * 64)
    return FetchResult(
        data=[{"value": 1}],
        row_count=1,
        schema_id="test.raw",
        schema_version="1.0.0",
        version=DataVersion(
            strategy=VersionStrategy.CONTENT_HASH,
            value=digest,
            timestamp=now,
            content_hash=digest,
        ),
        fetched_at=now,
        completeness=1.0,
        quality_tier=QualityTier.BRONZE,
    )


def test_data_plane_facade_exports_orchestrated_ingestion() -> None:
    from polisyos.fabric import data_plane

    assert data_plane.run_orchestrated_ingestion is run_orchestrated_ingestion


def test_orchestrator_forwards_sink_identity_to_ingestion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen_callbacks: list[tuple[object, object]] = []

    def _fake_ingestion(**kwargs: object) -> None:
        seen_callbacks.append(
            (kwargs["raw_result_sink"], kwargs["raw_http_response_observer"])
        )
        return None

    def _sink(*args: object) -> None:
        del args

    observer = object()

    monkeypatch.setattr(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        _fake_ingestion,
    )

    run_orchestrated_ingestion(
        connector_manifest={"datasets": []},
        source="test",
        license_name="CC-BY-4.0",
        cas_root=tmp_path / "cas",
        produce_snapshot=False,
        raw_result_sink=_sink,
        raw_http_response_observer=observer,  # type: ignore[arg-type]
    )

    assert seen_callbacks == [(_sink, observer)]


def test_raw_result_sink_failure_stops_snapshot_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = _raw_result()
    request = FetchRequest(dataset_id="raw.dataset")
    snapshot_attempted = False

    def _sink(
        connector_id: str,
        dataset_id: str,
        sink_request: FetchRequest,
        sink_result: FetchResult[object],
    ) -> None:
        assert connector_id == "test.connector"
        assert dataset_id == "raw.dataset"
        assert sink_request is request
        assert sink_result is raw
        raise RuntimeError("journal unavailable")

    def _fake_ingestion(**kwargs: object) -> None:
        sink = kwargs["raw_result_sink"]
        assert callable(sink)
        sink("test.connector", "raw.dataset", request, raw)

    def _snapshot_store(*args: object, **kwargs: object) -> object:
        nonlocal snapshot_attempted
        del args, kwargs
        snapshot_attempted = True
        pytest.fail("snapshot persistence ran after the raw-result sink failed")

    monkeypatch.setattr(
        "polisyos.fabric.ingestion.run_connectors_ingestion",
        _fake_ingestion,
    )
    monkeypatch.setattr(
        "polisyos.fabric.data_plane.orchestrator._build_filesystem_artifact_store",
        _snapshot_store,
    )

    with pytest.raises(RuntimeError, match="journal unavailable"):
        run_orchestrated_ingestion(
            connector_manifest={
                "datasets": [{"connector_id": "test.connector", "dataset_id": "raw.dataset"}]
            },
            source="test",
            license_name="CC-BY-4.0",
            cas_root=tmp_path / "cas",
            raw_result_sink=_sink,
        )

    assert snapshot_attempted is False
