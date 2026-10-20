from __future__ import annotations

import math
import sqlite3
from datetime import UTC, datetime

import pytest

from polisyos.core.artifacts import artifact_manifest_profile_sha256, input_ref_from_artifact_ref
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import CanonSpec, from_canonical_bytes
from polisyos.core.contracts.fabric import (
    DataSnapshot,
    DataSnapshotRef,
    DataViewRequestRef,
    data_snapshot_owner_input_requirements,
)
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.ir.connectors import DataVersion, FetchResult, QualityTier, VersionStrategy
from polisyos.ir.model_layer.queries import DataViewRequest
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort, ExecutionTierViolation
from tests._helpers.runtime_http import _build_control_service


class _DatasetRecord:
    def __init__(self, execution_tier: str) -> None:
        self.execution_tier = execution_tier


class _CatalogStore:
    def __init__(self, execution_tier: str) -> None:
        self._dataset = _DatasetRecord(execution_tier)

    def get_dataset(self, dataset_id: str) -> _DatasetRecord | None:
        assert dataset_id == "social_trust"
        return self._dataset


class _RegistryDescriptor:
    dataset_id: str = "social_trust"


class _RegistryEntry:
    def __init__(self) -> None:
        self.short_id = "fabric.mock"
        self.known_datasets: frozenset[str] = frozenset()
        self.dataset_descriptors: tuple[_RegistryDescriptor, ...] = ()
        self.default_config = object()


class _UnusedConnector:
    async def list_datasets(self, handle: object):
        del handle
        if False:
            yield None

    async def fetch(self, handle: object, request: object) -> FetchResult[object]:
        del handle, request
        raise AssertionError("unexpected connector fetch")


class _Registry:
    def get(self, connector_id: str) -> _UnusedConnector:
        raise AssertionError(f"unexpected connector lookup: {connector_id}")

    def get_entry(self, connector_id: str) -> _RegistryEntry:
        raise AssertionError(f"unexpected connector entry lookup: {connector_id}")

    def query_entries(self, *, capabilities: object | None = None) -> list[_RegistryEntry]:
        del capabilities
        return []

    async def get_connection(self, connector_id: str, config: object) -> object:
        raise AssertionError(f"unexpected connection lookup: {connector_id} {config}")

    async def release_connection(self, connector_id: str, handle: object) -> None:
        raise AssertionError(f"unexpected connection release: {connector_id} {handle}")


def test_default_fabric_port_snapshot_marks_survey_repeated_cross_section(tmp_path) -> None:
    now = datetime.now(UTC)
    seen: dict[str, object] = {}
    registry = _Registry()

    def _fake_get_data(
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, object] | None = None,
        registry: object | None = None,
    ) -> FetchResult[object]:
        seen["dataset_id"] = dataset_id
        seen["constraints"] = constraints
        seen["registry"] = registry
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

    store = FileSystemCAS(tmp_path)
    request_payload = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="req_wvs",
            view_type="table",
            metrics=["social_trust"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )

    snapshot_ref = DefaultFabricPort(
        fetch_data=_fake_get_data,
        connector_registry=registry,
    ).snapshot(
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
    assert seen["dataset_id"] == "social_trust"
    assert seen["registry"] is registry
    assert seen["constraints"] == {"page_size": 100}


def test_default_fabric_port_enforces_execution_tier_from_injected_catalog_store(tmp_path) -> None:
    now = datetime.now(UTC)

    def _fake_get_data(
        *,
        dataset_id: str,
        connector_id: str | None = None,
        constraints: dict[str, object] | None = None,
        registry: object | None = None,
    ) -> FetchResult[object]:
        return FetchResult(
            data=[],
            row_count=0,
            schema_id="catalog.only",
            schema_version="1.0",
            version=DataVersion(
                strategy=VersionStrategy.TIMESTAMP,
                value=now.isoformat(),
                timestamp=now,
            ),
            fetched_at=now,
            completeness=1.0,
            quality_tier=QualityTier.SILVER,
            quality_flags=frozenset(),
            bytes_transferred=0,
        )

    store = FileSystemCAS(tmp_path)
    request_payload = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="req_catalog",
            view_type="table",
            metrics=["social_trust"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )

    with pytest.raises(ExecutionTierViolation):
        DefaultFabricPort(
            fetch_data=_fake_get_data,
            catalog_store=_CatalogStore("catalog"),
        ).snapshot(
            store,
            DataViewRequestRef(artifact_id=request_payload.artifact_id),
        )


def test_default_fabric_port_persists_real_sql_dataframe_and_selected_lineage(tmp_path) -> None:
    db_path = tmp_path / "source.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE policy_inputs (income REAL NOT NULL, note TEXT)")
        connection.executemany(
            "INSERT INTO policy_inputs VALUES (?, ?)",
            [(12.5, "first"), (25.0, None)],
        )

    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{db_path}",
            headers={"X-SQL-Table": "policy_inputs"},
        ),
    )
    store = FileSystemCAS(tmp_path / "cas")
    request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="req_sql_inputs",
            view_type="table",
            metrics=["policy_inputs"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
    )

    try:
        snapshot_ref = DefaultFabricPort(connector_registry=registry).snapshot(
            store,
            DataViewRequestRef.model_validate(request_ref.model_dump(mode="python")),
        )
    finally:
        registry.shutdown()

    snapshot = DataSnapshot.model_validate(from_canonical_bytes(store.get_bytes(snapshot_ref)))
    records = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
    snapshot_manifest = store.get_manifest(snapshot_ref)
    request_edge = next(
        edge for edge in snapshot_manifest.inputs if edge.role == "data_view_request_ref"
    )

    assert records == [
        {"income": 12.5, "note": "first"},
        {"income": 25.0, "note": None},
    ]
    assert snapshot_ref.manifest_profile_sha256 is not None
    assert request_edge.artifact_id == request_ref.artifact_id
    assert request_edge.manifest_profile_sha256 == artifact_manifest_profile_sha256(
        store.get_manifest(request_ref)
    )

    control_service = _build_control_service(tmp_path / "control", artifact_store=store)
    try:
        admitted = control_service._validate_control_nl_data_snapshot(
            DataSnapshotRef.model_validate(snapshot_ref.model_dump(mode="python"))
        )
        assert admitted == snapshot
        assert snapshot_manifest.artifact_schema == SchemaInfo(
            name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
            version="0.3.0",
        )

        wrong_schema_ref = store.put_json(
            snapshot,
            ArtifactWriteOptions(
                kind="fabric.data_snapshot",
                media_type="application/json",
                schema=SchemaInfo(name="fabric.data_snapshot.v1", version="1.0"),
                inputs=list(snapshot_manifest.inputs),
            ),
            return_selected_profile=True,
        )
        with pytest.raises(ValueError, match="control_nl_data_snapshot_schema_mismatch"):
            control_service._validate_control_nl_data_snapshot(
                DataSnapshotRef.model_validate(wrong_schema_ref.model_dump(mode="python"))
            )
    finally:
        control_service.close()

    from polisyos.runtime.quality.data_snapshot_lineage import (
        DataSnapshotLineageError,
        validate_data_snapshot_owner_lineage,
    )

    legacy_payload = snapshot.model_dump(mode="json")
    legacy_payload.pop("source_lineage")
    legacy_snapshot = DataSnapshot.model_validate(legacy_payload)
    legacy_snapshot_ref = store.put_json(
        legacy_snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=list(snapshot_manifest.inputs),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    validate_data_snapshot_owner_lineage(store, legacy_snapshot_ref, legacy_snapshot)
    legacy_missing_request_ref = store.put_json(
        legacy_snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.2.0"),
            inputs=[
                edge for edge in snapshot_manifest.inputs if edge.role != "data_view_request_ref"
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(DataSnapshotLineageError, match="manifest_inputs_mismatch"):
        validate_data_snapshot_owner_lineage(
            store,
            legacy_missing_request_ref,
            legacy_snapshot,
        )

    missing_request_edge_ref = store.put_json(
        snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0"),
            inputs=[
                edge for edge in snapshot_manifest.inputs if edge.role != "data_view_request_ref"
            ],
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(DataSnapshotLineageError, match="parent_inputs_mismatch"):
        validate_data_snapshot_owner_lineage(store, missing_request_edge_ref, snapshot)

    alternate_request_ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id="req_sql_inputs_alt",
            view_type="table",
            metrics=["policy_inputs"],
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    alternate_request = DataViewRequestRef.model_validate(
        alternate_request_ref.model_dump(mode="python")
    )
    assert snapshot.source_lineage is not None
    forged_lineage = snapshot.source_lineage.model_copy(
        update={"data_view_request_ref": alternate_request}
    )
    forged_snapshot = snapshot.model_copy(update={"source_lineage": forged_lineage})
    forged_inputs = [
        input_ref_from_artifact_ref(ref, role=role)
        for ref, role in data_snapshot_owner_input_requirements(forged_snapshot)
    ]
    forged_snapshot_ref = store.put_json(
        forged_snapshot,
        ArtifactWriteOptions(
            kind="fabric.data_snapshot",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.core.DataSnapshot", version="0.3.0"),
            inputs=forged_inputs,
        ),
        canon_spec=CanonSpec(forbid_floats=False),
        return_selected_profile=True,
    )
    with pytest.raises(DataSnapshotLineageError, match="source_edges_mismatch"):
        validate_data_snapshot_owner_lineage(store, forged_snapshot_ref, forged_snapshot)


def test_columnar_payload_preserves_nonfinite_as_nonfinite_and_refuses_duplicate_columns(
    tmp_path,
) -> None:
    pandas = pytest.importorskip("pandas")
    from polisyos.scientist.adapters.fabric_bridge import _jsonable

    duplicate_columns = pandas.DataFrame([[1, 2]], columns=["income", "income"])
    with pytest.raises(ValueError, match="duplicate column names"):
        _jsonable(duplicate_columns)

    nullable_and_nonfinite = pandas.DataFrame(
        {"value": pandas.Series([None, float("nan")], dtype=object)}
    )
    converted = _jsonable(nullable_and_nonfinite)
    assert converted[0]["value"] is None
    assert math.isnan(converted[1]["value"])

    arrow = pytest.importorskip("pyarrow")
    assert _jsonable(arrow.table({"income": [1.0, 2.0]})) == [
        {"income": 1.0},
        {"income": 2.0},
    ]

    class CallableButUnsupported:
        columns = ("income",)

        def to_dict(self, *, orient: str) -> list[dict[str, float]]:
            return [{"income": 1.0}]

    with pytest.raises(TypeError, match="unsupported columnar payload type"):
        _jsonable(CallableButUnsupported())
    with pytest.raises((TypeError, ValueError)):
        FileSystemCAS(tmp_path / "nan-cas").put_json(
            converted,
            ArtifactWriteOptions(
                kind="fabric.tabular_payload",
                media_type="application/json",
                schema=SchemaInfo(name="polisyos.fabric.TabularPayload", version="1.0"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
        )
