from __future__ import annotations

from datetime import datetime, timezone

from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataViewRequestRef
from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy
from polisyos.ir.queries import DataViewRequest
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort


def test_default_fabric_port_snapshot_marks_survey_repeated_cross_section(monkeypatch, tmp_path) -> None:
    now = datetime.now(timezone.utc)

    def _fake_get_data(*, dataset_id: str, connector_id=None, constraints=None):  # noqa: ARG001
        return FetchResult(
            data=[
                {
                    "country_code": "UA",
                    "survey_year": 2020,
                    "wave": 7,
                    "sample_weight": 1.25,
                    "value": 0.61,
                }
            ],
            row_count=1,
            schema_id="wvs.timeseries",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=now.isoformat(),
                timestamp=now,
            ),
            fetched_at=now,
            source_updated_at=now,
            completeness=1.0,
            quality_tier=QualityTier.GOLD,
            quality_flags=frozenset(),
            bytes_transferred=256,
        )

    monkeypatch.setattr(
        "polisyos.scientist.adapters.fabric_bridge.fabric_get_data",
        _fake_get_data,
    )

    store = FileSystemCAS(tmp_path)
    request_payload = store.put_json(
        DataViewRequest(
            request_id="req_wvs",
            view_type="table",
            metrics=["social_trust"],
        ),
        PutOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )

    snapshot_ref = DefaultFabricPort().snapshot(
        store,
        DataViewRequestRef(artifact_id=request_payload.artifact_id),
    )
    snapshot_payload = from_canonical_bytes(store.get_bytes(snapshot_ref.artifact_id))
    snapshot = DataSnapshot.model_validate(snapshot_payload)

    assert snapshot.stats["data_shape"] == "survey_repeated_cross_section"
    assert snapshot.stats["survey_year_field"] == "survey_year"
    assert snapshot.stats["wave_field"] == "wave"
    assert snapshot.stats["sample_weight_field"] == "sample_weight"
    assert "allowed_workflows=transport,survey,hte,repeated_cross_section" in snapshot.notes
