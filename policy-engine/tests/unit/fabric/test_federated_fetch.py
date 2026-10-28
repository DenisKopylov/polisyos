"""Real SQL acquisition, selected replay and the existing Scientist consumer."""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from polisyos.core.artifacts import input_ref_from_artifact_ref, load_core_json_artifact
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot, DataViewRequestRef
from polisyos.fabric import FederationFetchRequest, FederationFetchSource, fabric_get_data
from polisyos.fabric.connectors.base import ConnectionConfig
from polisyos.fabric.connectors.federation.artifact import (
    FederationArtifactRef,
    SelectedFederationInput,
    read_verified_federation_derivation,
)
from polisyos.fabric.connectors.federation.types import (
    CompositionRequest,
    CompositionStrategy,
    ConflictPolicy,
    FederationError,
    SourceMetadata,
)
from polisyos.fabric.connectors.registry import ConnectorRegistry
from polisyos.fabric.connectors.sources.sql_query import SQLQueryConnector
from polisyos.fabric.federated_fetch import (
    FederationFetchAudit,
    FederationSnapshotProjectionError,
    prepare_federation_core_payload,
)
from polisyos.ir.connectors import QualityTier, TrustLevel
from polisyos.ir.model_layer.queries import DataViewRequest, Pagination
from polisyos.scientist.adapters.fabric_bridge import DefaultFabricPort


def _registry(tmp_path: Path) -> ConnectorRegistry:
    db = tmp_path / "inputs.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE left_input (id INTEGER, value REAL)")
        connection.execute("CREATE TABLE right_input (id INTEGER, value REAL)")
        connection.execute("CREATE TABLE empty_input (id INTEGER, value REAL)")
        connection.executemany("INSERT INTO left_input VALUES (?, ?)", [(1, 10), (2, None)])
        connection.executemany("INSERT INTO right_input VALUES (?, ?)", [(1, None), (2, 20)])
    registry = ConnectorRegistry()
    registry.register(SQLQueryConnector, ConnectionConfig(url=f"sqlite:///{db}"))
    return registry


def _spec(tmp_path: Path, *, empty: bool = False) -> FederationFetchRequest:
    tables = ("empty_input",) if empty else ("left_input", "right_input")
    return FederationFetchRequest(
        composition=CompositionRequest(
            dataset_pattern="policy_inputs",
            strategy=CompositionStrategy.UNION if empty else CompositionStrategy.JOIN,
            conflict_policy=ConflictPolicy.TRUST_HIGHEST,
            key_columns=["id"],
            join_keys=["id"],
            join_validate="one_to_one",
            join_max_rows=2,
            tie_breaker_seed="real-sql-bridge",
        ),
        sources=tuple(FederationFetchSource("sql.query", table) for table in tables),
        output_root=tmp_path / "selected",
    )


def _request(
    store: FileSystemCAS,
    *,
    limit: int = 100,
    metrics: list[str] | None = None,
    request_id: str = "federated-sql-inputs",
) -> DataViewRequestRef:
    ref = store.put_json(
        DataViewRequest(
            schema_version="1.0",
            request_id=request_id,
            view_type="table",
            metrics=["policy_inputs"] if metrics is None else metrics,
            pagination=Pagination(limit=limit),
        ),
        ArtifactWriteOptions(
            kind="ir.data_view_request",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.ir.DataViewRequest", version="1.0"),
        ),
        return_selected_profile=True,
    )
    return DataViewRequestRef.model_validate(ref.model_dump(mode="python"))


def _snapshot(store: FileSystemCAS, ref: object) -> DataSnapshot:
    return DataSnapshot.model_validate(from_canonical_bytes(store.get_bytes(ref)))


def test_real_connector_fetch_persists_and_freshly_replays_selected_composition(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    try:
        result = fabric_get_data(dataset_id="policy_inputs", registry=registry, federation=spec)
    finally:
        registry.shutdown()
    assert result.data.sort_values("id")["value"].tolist() == [10, 20]
    assert result.row_count == 2
    audit = result.federation_audit
    assert [fetch.dataset_id for fetch in audit.fetches] == ["left_input", "right_input"]
    assert {fetch.connector_id for fetch in audit.fetches} == {"sql.query@1.0.0"}
    assert audit.selected_bytes_basis == "recomputed"
    assert audit.leaf_history_basis == "consumer_asserted"
    assert result.quality_tier == QualityTier.UNVERIFIED
    assert result.source_updated_at is None
    assert result.version.content_hash == f"sha256:{audit.manifest_sha256}"
    fresh = read_verified_federation_derivation(
        audit.artifact_root, FederationArtifactRef(audit.manifest_sha256)
    )
    pd.testing.assert_frame_equal(result.data, fresh.data)
    assert len(fresh.source_ids_by_cell) == 2
    assert fresh.source_ids_by_cell[0]["value"] != fresh.source_ids_by_cell[1]["value"]
    wire = audit.model_dump_json()
    assert FederationFetchAudit.model_validate_json(wire) == audit
    with pytest.raises(ValidationError):
        FederationFetchAudit.model_validate({**audit.model_dump(), "authority": "official"})


def test_actual_port_writes_replayed_rows_and_bound_candidate_audit(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    request = _request(store)
    try:
        ref = DefaultFabricPort(connector_registry=registry, federation=spec).snapshot(
            store, request
        )
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    records = from_canonical_bytes(store.get_bytes(snapshot.data_ref))
    assert sorted(records, key=lambda row: row["id"]) == [
        {"id": 1, "value": 10.0},
        {"id": 2, "value": 20.0},
    ]
    warnings = from_canonical_bytes(store.get_bytes(snapshot.warnings_ref))
    audit = next(
        warning["data"]
        for warning in warnings["warnings"]
        if warning["code"] == "fabric.federation.candidate_derivation"
    )
    assert audit["manifest_sha256"] == snapshot.stats["federation_manifest_sha256"]
    assert audit["leaf_history_basis"] == "consumer_asserted"
    quality = from_canonical_bytes(store.get_bytes(snapshot.quality_report_ref))
    assert quality["freshness_status"]["level"] == "unknown"
    manifest = store.get_manifest_by_profile(ref.artifact_id, ref.manifest_profile_sha256)
    warning_edge = input_ref_from_artifact_ref(snapshot.warnings_ref, role="warnings_ref")
    assert warning_edge in manifest.inputs


def test_port_ignores_mutable_payload_and_reopens_actual_selected_bytes(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    try:
        selected = fabric_get_data(
            dataset_id="policy_inputs",
            registry=registry,
            federation=spec,
            constraints={"page_size": 100},
        )
        forged = selected.model_copy(
            update={"data": pd.DataFrame({"id": [1, 2], "value": [999, 999]})}
        )
        ref = DefaultFabricPort(
            fetch_data=lambda **kwargs: forged,
            federation=spec,
            connector_registry=registry,
        ).snapshot(store, _request(store))
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    rows = load_core_json_artifact(store, snapshot.data_ref)
    assert [row["value"] for row in rows] == [10, 20]


def test_port_refuses_corrupted_selected_bytes_instead_of_trusting_status(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    try:
        selected = fabric_get_data(
            dataset_id="policy_inputs",
            registry=registry,
            federation=spec,
            constraints={"page_size": 100},
        )
        (spec.output_root / "manifest.json").write_bytes(b"{}")
        with pytest.raises(FederationError):
            DefaultFabricPort(
                fetch_data=lambda **kwargs: selected,
                federation=spec,
                connector_registry=registry,
            ).snapshot(store, _request(store))
    finally:
        registry.shutdown()


def test_successful_empty_source_keeps_selected_schema_through_port(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path, empty=True)
    store = FileSystemCAS(tmp_path / "cas")
    try:
        ref = DefaultFabricPort(connector_registry=registry, federation=spec).snapshot(
            store, _request(store)
        )
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    assert from_canonical_bytes(store.get_bytes(snapshot.data_ref)) == []
    schema = from_canonical_bytes(store.get_bytes(snapshot.data_schema_ref))
    assert schema["federation_columns"] == [
        {"name": "id", "pandas_dtype": "object"},
        {"name": "value", "pandas_dtype": "object"},
    ]


def test_fetch_failure_does_not_publish_a_successful_empty_derivation(tmp_path) -> None:
    registry = _registry(tmp_path)
    base = _spec(tmp_path)
    spec = FederationFetchRequest(
        composition=base.composition,
        sources=(FederationFetchSource("sql.query", "missing_table"),),
        output_root=base.output_root,
    )
    try:
        with pytest.raises(pd.errors.DatabaseError):
            fabric_get_data(dataset_id="policy_inputs", registry=registry, federation=spec)
    finally:
        registry.shutdown()
    assert not spec.output_root.exists()


def test_selected_parent_trust_filter_reads_actual_leaf_declarations_not_carrier(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    try:
        selected = fabric_get_data(dataset_id="policy_inputs", registry=registry, federation=spec)
        metadata = registry.get_entry("sql.query").metadata
        raised_carrier = metadata.model_copy(update={"trust_level": TrustLevel.AUTHORITATIVE})
        parent = SelectedFederationInput(
            spec.output_root,
            FederationArtifactRef(selected.federation_audit.manifest_sha256),
            SourceMetadata(
                connector_id=raised_carrier.fully_qualified_id,
                metadata=raised_carrier,
                fetched_at=selected.fetched_at,
                row_count=selected.row_count,
            ),
        )
        request = FederationFetchRequest(
            composition=replace(spec.composition, min_trust_level=TrustLevel.AUTHORITATIVE),
            sources=(parent,),
            output_root=tmp_path / "child",
        )
        with pytest.raises(FederationError, match="declared leaf below"):
            fabric_get_data(dataset_id="policy_inputs", registry=registry, federation=request)
    finally:
        registry.shutdown()
    assert not request.output_root.exists()


def test_sql_limit_is_an_explicit_unknown_capture_not_source_eof(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = replace(_spec(tmp_path), sources=(FederationFetchSource("sql.query", "left_input"),))
    try:
        result = fabric_get_data(
            dataset_id="policy_inputs",
            registry=registry,
            federation=spec,
            constraints={"page_size": 1},
        )
    finally:
        registry.shutdown()
    assert result.row_count == 1
    observation = result.federation_audit.fetches[0]
    assert observation.pagination_reported is False  # Actual SQL marker is insufficient.
    assert observation.source_completeness == "not_established"
    assert observation.source_scope == "captured_rows_only"
    assert "federation.source_completeness_not_established" in result.quality_flags


@pytest.mark.parametrize(
    "constraints",
    [
        {"filters": {"id": ["1"]}},
        {"date_start": "2021-01-01"},
    ],
)
def test_unsupported_scope_refuses_before_any_real_fetch(
    tmp_path, monkeypatch, constraints
) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)

    async def forbidden_fetch(*args, **kwargs):
        raise AssertionError("unsupported scope reached connector fetch")

    monkeypatch.setattr(SQLQueryConnector, "fetch", forbidden_fetch)
    try:
        with pytest.raises(FederationError, match="Filter/date scope"):
            fabric_get_data(
                dataset_id="policy_inputs",
                registry=registry,
                federation=spec,
                constraints=constraints,
            )
    finally:
        registry.shutdown()
    assert not spec.output_root.exists()


def test_valid_other_selected_artifact_cannot_be_snapshotted_as_requested_p(tmp_path) -> None:
    registry = _registry(tmp_path)
    p = _spec(tmp_path)
    q = replace(
        p,
        output_root=tmp_path / "other-selected",
        composition=replace(p.composition, dataset_pattern="other_dataset"),
        sources=(FederationFetchSource("sql.query", "right_input"),),
    )
    store = FileSystemCAS(tmp_path / "cas")
    try:
        other = fabric_get_data(
            dataset_id="other_dataset",
            registry=registry,
            federation=q,
            constraints={"page_size": 100},
        )
        # Q is internally valid. Its root/ref/observations must not select P.
        read_verified_federation_derivation(
            q.output_root, FederationArtifactRef(other.federation_audit.manifest_sha256)
        )
        with pytest.raises(FederationError):
            DefaultFabricPort(
                fetch_data=lambda **kwargs: other,
                federation=p,
                connector_registry=registry,
            ).snapshot(store, _request(store))
    finally:
        registry.shutdown()


def test_mutable_return_observations_do_not_replace_selected_acquisition_bytes(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    try:
        selected = fabric_get_data(
            dataset_id="policy_inputs",
            registry=registry,
            federation=spec,
            constraints={"page_size": 100},
        )
        fake_audit = selected.federation_audit.model_copy(update={"fetches": ()})
        forged = selected.model_copy(update={"federation_audit": fake_audit})
        ref = DefaultFabricPort(
            fetch_data=lambda **kwargs: forged,
            federation=spec,
            connector_registry=registry,
        ).snapshot(store, _request(store))
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    warnings = load_core_json_artifact(store, snapshot.warnings_ref)
    audit = next(
        row["data"]
        for row in warnings["warnings"]
        if row["code"] == "fabric.federation.candidate_derivation"
    )
    assert len(audit["fetches"]) == 2
    assert {row["dataset_id"] for row in audit["fetches"]} == {"left_input", "right_input"}


def test_real_sql_null_survives_selected_replay_and_actual_core_consumer(tmp_path) -> None:
    registry = _registry(tmp_path)
    spec = replace(_spec(tmp_path), sources=(FederationFetchSource("sql.query", "left_input"),))
    store = FileSystemCAS(tmp_path / "cas")
    try:
        ref = DefaultFabricPort(connector_registry=registry, federation=spec).snapshot(
            store, _request(store)
        )
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    assert load_core_json_artifact(store, snapshot.data_ref) == [
        {"id": 1, "value": 10.0},
        {"id": 2, "value": None},
    ]
    schema = load_core_json_artifact(store, snapshot.data_schema_ref)
    assert schema["federation_columns"] == [
        {"name": "id", "pandas_dtype": "int64"},
        {"name": "value", "pandas_dtype": "float64"},
    ]


@pytest.mark.parametrize(
    "row",
    [
        {"value": -0.0},
        {"_type": "float", "repr": "1"},
        {"_type": "ordinary", "value": 1},
        {"value": float("inf")},
        {"value": pd.Timestamp("2026-01-01T00:00:00.123456789Z")},
    ],
)
def test_exact_snapshot_profile_refuses_generic_unrepresentable_semantics(row) -> None:
    with pytest.raises(FederationSnapshotProjectionError):
        prepare_federation_core_payload(None, frame=pd.DataFrame([row]))


def test_snapshot_profile_preserves_every_supported_scalar_without_name_blacklist() -> None:
    frame = pd.DataFrame(
        {
            "__source_id": ["a", "b"],
            "value": [1.000000000001, None],
            "count": pd.Series([1, None], dtype="Int64"),
        }
    )
    rows = prepare_federation_core_payload(None, frame=frame)
    assert rows == [
        {"__source_id": "a", "value": 1.000000000001, "count": 1},
        {"__source_id": "b", "value": None, "count": None},
    ]


def test_parent_only_snapshot_carries_typed_unavailable_warning_history(tmp_path) -> None:
    registry = _registry(tmp_path)
    first_spec = _spec(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")
    try:
        first = fabric_get_data(
            dataset_id="policy_inputs", registry=registry, federation=first_spec
        )
        assert "sql_query" in first.quality_flags
        metadata = registry.get_entry("sql.query").metadata
        parent = SelectedFederationInput(
            first_spec.output_root,
            FederationArtifactRef(first.federation_audit.manifest_sha256),
            SourceMetadata(
                connector_id=metadata.fully_qualified_id,
                metadata=metadata,
                fetched_at=first.fetched_at,
                row_count=first.row_count,
            ),
        )
        child_spec = replace(first_spec, sources=(parent,), output_root=tmp_path / "child")
        ref = DefaultFabricPort(connector_registry=registry, federation=child_spec).snapshot(
            store, _request(store)
        )
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    warnings = load_core_json_artifact(store, snapshot.warnings_ref)
    audit = next(
        row["data"]
        for row in warnings["warnings"]
        if row["code"] == "fabric.federation.candidate_derivation"
    )
    assert audit["fetches"] == []
    assert audit["fetches_scope"] == "fresh_connector_fetches_only"
    assert audit["parent_history"] == "unavailable"
    assert audit["parents"][0]["warning_history"] == "not_established"
    assert any(
        row["msg"] == "federation.parent_quality_history_unavailable"
        for row in warnings["warnings"]
    )


def test_held_parent_cannot_silently_satisfy_new_date_constraint(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    first_spec = _spec(tmp_path)
    try:
        first = fabric_get_data(
            dataset_id="policy_inputs", registry=registry, federation=first_spec
        )
        metadata = registry.get_entry("sql.query").metadata
        parent = SelectedFederationInput(
            first_spec.output_root,
            FederationArtifactRef(first.federation_audit.manifest_sha256),
            SourceMetadata(
                connector_id=metadata.fully_qualified_id,
                metadata=metadata,
                fetched_at=first.fetched_at,
                row_count=first.row_count,
            ),
        )
        spec = replace(first_spec, sources=(parent,), output_root=tmp_path / "child")

        def forbidden_replay(*args, **kwargs):
            raise AssertionError("unsupported date scope reached parent replay")

        monkeypatch.setattr(
            "polisyos.fabric.federated_fetch.read_verified_federation_derivation", forbidden_replay
        )
        with pytest.raises(FederationError, match="Filter/date scope"):
            fabric_get_data(
                dataset_id="policy_inputs",
                registry=registry,
                federation=spec,
                constraints={"date_start": "2021-01-01"},
            )
    finally:
        registry.shutdown()
    assert not spec.output_root.exists()


class _RecordingCAS(FileSystemCAS):
    def __init__(self, root):
        super().__init__(root)
        self.published_kinds = []

    def put_json(self, value, opts, *args, **kwargs):
        self.published_kinds.append(opts.kind)
        return super().put_json(value, opts, *args, **kwargs)


def test_real_sql_tag_collision_is_refused_before_any_core_data_publication(tmp_path) -> None:
    registry = _registry(tmp_path)
    db = tmp_path / "inputs.sqlite"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE tagged_input (_type TEXT, repr TEXT)")
        connection.execute("INSERT INTO tagged_input VALUES ('float', '1')")
    base = _spec(tmp_path)
    spec = replace(
        base,
        sources=(FederationFetchSource("sql.query", "tagged_input"),),
        composition=replace(base.composition, join_keys=["_type"], key_columns=["_type"]),
    )
    store = _RecordingCAS(tmp_path / "cas")
    request = _request(store)
    store.published_kinds.clear()
    try:
        with pytest.raises(FederationSnapshotProjectionError):
            DefaultFabricPort(connector_registry=registry, federation=spec).snapshot(store, request)
    finally:
        registry.shutdown()
    assert store.published_kinds == []


def test_datetime_requires_an_admitted_bounded_owner_projection() -> None:
    frame = pd.DataFrame(
        {
            "time": [pd.Timestamp("2026-01-01T00:00:00Z")],
            "value": [None],
        }
    )
    with pytest.raises(FederationSnapshotProjectionError):
        prepare_federation_core_payload(None, frame=frame)


def _synthetic_selected_callback_result(
    spec,
    registry,
    *,
    page_size=100,
    frame=None,
    frames=None,
):
    """Adversary: real kernel/receipt, same intent, but NO connector fetch.

    This helper deliberately bypasses the bridge producer. Its public result
    and self-selected receipt must never prove connector capture authentication.
    """
    import hashlib
    import json
    from datetime import UTC, datetime

    from polisyos.fabric.connectors.federation.artifact import persist_federation_derivation
    from polisyos.fabric.connectors.federation.composer import DataComposer
    from polisyos.fabric.connectors.federation.resolver import ConflictResolver
    from polisyos.fabric.federated_fetch import (
        _FORMAT,
        FederationFetchObservation,
        _result,
        freeze_federation_request,
    )
    from polisyos.ir.connectors import (
        DataVersion,
        FetchProvenanceEnvelope,
        FetchQualityEnvelope,
        FetchRequest,
        FetchTransferEnvelope,
        VersionStrategy,
    )

    context = json.loads(
        freeze_federation_request(
            dataset_id=spec.composition.dataset_pattern,
            federation=spec,
            constraints={"page_size": page_size},
            registry=registry,
        )
    )
    now = datetime.now(UTC)
    inputs = []
    for position, source in enumerate(spec.sources):
        if isinstance(source, SelectedFederationInput):
            inputs.append(source)
        else:
            selected_frame = (
                frames[position]
                if frames is not None and position in frames
                else frame
                if frame is not None
                else pd.DataFrame({"id": [1], "value": [999.0]})
            )
            metadata = registry.get_entry(source.connector_id).metadata
            inputs.append(
                (
                    selected_frame,
                    SourceMetadata(
                        connector_id=metadata.fully_qualified_id,
                        metadata=metadata,
                        fetched_at=now,
                        row_count=len(selected_frame),
                    ),
                )
            )
    ref = persist_federation_derivation(
        spec.output_root,
        DataComposer(
            ConflictResolver(
                spec.composition.conflict_policy, tie_breaker_seed=spec.composition.tie_breaker_seed
            )
        ),
        inputs,
        spec.composition,
    )
    held = {digest: Path(path) for digest, path in context["held_parents"].items()}
    verified = read_verified_federation_derivation(spec.output_root, ref, held_parents=held)
    manifest = json.loads((spec.output_root / "manifest.json").read_text())
    observations = []
    for position, source in enumerate(spec.sources):
        if isinstance(source, SelectedFederationInput):
            continue
        metadata = registry.get_entry(source.connector_id).metadata
        selected_frame = inputs[position][0]
        request = FetchRequest(dataset_id=source.dataset_id, page_size=page_size)
        observations.append(
            FederationFetchObservation(
                position=position,
                selected_source_sha256=manifest["sources"][position]["sha256"],
                connector_id=metadata.fully_qualified_id,
                dataset_id=source.dataset_id,
                request_key=request.request_key,
                observed_at=now,
                row_count=len(selected_frame),
                schema_id="synthetic-claim",
                schema_version="1.0",
                quality=FetchQualityEnvelope(completeness=1.0, quality_tier=QualityTier.GOLD),
                transfer=FetchTransferEnvelope(),
                provenance=FetchProvenanceEnvelope(
                    version=DataVersion(
                        strategy=VersionStrategy.REVISION, value="synthetic-claim", timestamp=now
                    ),
                    fetched_at=now,
                ),
                pagination_reported=False,
            )
        )
    receipt = {
        "format": _FORMAT,
        "context": context,
        "kernel_ref": ref.manifest_sha256,
        "fetches": [row.model_dump(mode="json") for row in observations],
        "observed_at": now.isoformat(),
        "elapsed_ms": 0.0,
    }
    payload = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    (spec.output_root / "acquisition.json").write_bytes(payload)
    return _result(
        verified,
        spec.output_root,
        ref,
        hashlib.sha256(payload).hexdigest(),
        context,
        tuple(observations),
        now,
        0.0,
    )


@pytest.mark.parametrize("through_port", [False, True])
def test_disjoint_union_obeys_actual_composed_output_bound(tmp_path, through_port) -> None:
    registry = _registry(tmp_path)
    with sqlite3.connect(tmp_path / "inputs.sqlite") as connection:
        connection.execute("DELETE FROM right_input")
        connection.executemany("INSERT INTO right_input VALUES (?, ?)", [(3, 30), (4, 40)])
    base = _spec(tmp_path)
    spec = replace(base, composition=replace(base.composition, strategy=CompositionStrategy.UNION))
    store = _RecordingCAS(tmp_path / "cas")
    request = _request(store, limit=1)
    store.published_kinds.clear()
    try:
        with pytest.raises(FederationError, match="Composed output.*row bound"):
            if through_port:
                DefaultFabricPort(connector_registry=registry, federation=spec).snapshot(
                    store, request
                )
            else:
                fabric_get_data(
                    dataset_id="policy_inputs",
                    registry=registry,
                    federation=spec,
                    constraints={"page_size": 1},
                )
        # The engineering-bounded kernel result is valid; the error is the
        # actual requested output scope, not setup/collection or a marker.
        import hashlib

        digest = hashlib.sha256((spec.output_root / "manifest.json").read_bytes()).hexdigest()
        actual = read_verified_federation_derivation(
            spec.output_root, FederationArtifactRef(digest)
        )
        assert len(actual.data) == 2
    finally:
        registry.shutdown()
    assert store.published_kinds == []
    assert not (spec.output_root / "acquisition.json").exists()


def test_expanding_join_obeys_actual_query_output_bound(tmp_path) -> None:
    registry = _registry(tmp_path)
    with sqlite3.connect(tmp_path / "inputs.sqlite") as connection:
        connection.execute("DELETE FROM left_input")
        connection.execute("DELETE FROM right_input")
        connection.executemany("INSERT INTO left_input VALUES (?, ?)", [(1, 10), (1, 20)])
        connection.executemany("INSERT INTO right_input VALUES (?, ?)", [(1, 10), (1, 20)])
    base = _spec(tmp_path)
    spec = replace(
        base, composition=replace(base.composition, join_validate="many_to_many", join_max_rows=4)
    )
    store = _RecordingCAS(tmp_path / "cas")
    request = _request(store, limit=2)
    store.published_kinds.clear()
    try:
        with pytest.raises(FederationError, match="Composed output.*row bound"):
            DefaultFabricPort(connector_registry=registry, federation=spec).snapshot(store, request)
        import hashlib

        digest = hashlib.sha256((spec.output_root / "manifest.json").read_bytes()).hexdigest()
        actual = read_verified_federation_derivation(
            spec.output_root, FederationArtifactRef(digest)
        )
        assert len(actual.data) == 4
    finally:
        registry.shutdown()
    assert store.published_kinds == []


def test_connector_page_hint_cannot_exceed_declared_capture_bound(tmp_path) -> None:
    initial = _registry(tmp_path)
    initial.shutdown()
    registry = ConnectorRegistry()
    registry.register(
        SQLQueryConnector,
        ConnectionConfig(
            url=f"sqlite:///{tmp_path / 'inputs.sqlite'}",
            headers={"X-SQL-Query": "SELECT * FROM left_input"},
        ),
    )
    base = _spec(tmp_path)
    spec = replace(base, sources=(FederationFetchSource("sql.query", "left_input"),))
    try:
        # The actual configured SQL query, like a multi-page connector, returns
        # two materialized rows despite page_size1. No transport marker is EOF.
        with pytest.raises(FederationError, match="Returned connector capture.*row bound"):
            fabric_get_data(
                dataset_id="policy_inputs",
                registry=registry,
                federation=spec,
                constraints={"page_size": 1},
            )
    finally:
        registry.shutdown()
    assert not spec.output_root.exists()


def test_same_intent_synthetic_capture_remains_consumer_asserted(tmp_path, monkeypatch) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    store = FileSystemCAS(tmp_path / "cas")

    async def forbidden_fetch(*args, **kwargs):
        raise AssertionError("synthetic receipt unexpectedly made a connector fetch")

    monkeypatch.setattr(SQLQueryConnector, "fetch", forbidden_fetch)
    try:
        synthetic = _synthetic_selected_callback_result(spec, registry)
        ref = DefaultFabricPort(
            fetch_data=lambda **kwargs: synthetic, federation=spec, connector_registry=registry
        ).snapshot(store, _request(store))
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    assert [row["value"] for row in load_core_json_artifact(store, snapshot.data_ref)] == [999.0]
    warnings = load_core_json_artifact(store, snapshot.warnings_ref)
    audit = next(
        row["data"]
        for row in warnings["warnings"]
        if row["code"] == "fabric.federation.candidate_derivation"
    )
    assert audit["capture_origin_basis"] == "consumer_asserted"
    assert audit["observation_origin_basis"] == "consumer_asserted"
    assert audit["selected_bytes_basis"] == "recomputed"
    assert all(row["captured_bytes_basis"] == "consumer_asserted" for row in audit["fetches"])
    assert all(row["provenance_basis"] == "consumer_asserted" for row in audit["fetches"])
    assert all(row["observation_basis"] == "consumer_asserted" for row in audit["fetches"])
    assert all(row["selected_member_bytes_basis"] == "recomputed" for row in audit["fetches"])
    assert load_core_json_artifact(store, snapshot.quality_report_ref)["tier"] == "unverified"
    assert "source=federation_receipt_consumer_asserted" in snapshot.notes


def test_valid_callback_child_cannot_bypass_frozen_whole_leaf_preference(tmp_path) -> None:
    from polisyos.fabric.connectors.federation.artifact import persist_federation_derivation
    from polisyos.fabric.connectors.federation.composer import DataComposer
    from polisyos.fabric.connectors.federation.resolver import ConflictResolver

    registry = _registry(tmp_path)
    base = _spec(tmp_path)
    store = _RecordingCAS(tmp_path / "cas")
    try:
        fetched = fabric_get_data(
            dataset_id="left_input", connector_id="sql.query", registry=registry
        )
        metadata = registry.get_entry("sql.query").metadata
        low = metadata.model_copy(update={"trust_level": TrustLevel.LOW})
        low_source = SourceMetadata(
            connector_id=low.fully_qualified_id,
            metadata=low,
            fetched_at=fetched.fetched_at,
            row_count=fetched.row_count,
        )
        low_request = replace(base.composition, min_trust_level=TrustLevel.LOW)
        parent_root = tmp_path / "low-parent"
        parent_ref = persist_federation_derivation(
            parent_root,
            DataComposer(
                ConflictResolver(
                    low_request.conflict_policy, tie_breaker_seed=low_request.tie_breaker_seed
                )
            ),
            [(fetched.data, low_source)],
            low_request,
        )
        high = metadata.model_copy(update={"trust_level": TrustLevel.AUTHORITATIVE})
        selected = SelectedFederationInput(
            parent_root,
            parent_ref,
            SourceMetadata(
                connector_id=high.fully_qualified_id,
                metadata=high,
                fetched_at=fetched.fetched_at,
                row_count=fetched.row_count,
            ),
        )
        spec = replace(
            base,
            sources=(selected,),
            output_root=tmp_path / "synthetic-child",
            composition=replace(base.composition, min_trust_level=TrustLevel.AUTHORITATIVE),
        )
        # Genuine kernel child/receipt matches root, source, request and hashes.
        # It bypasses the normal bridge producer, not the real fresh consumer.
        synthetic = _synthetic_selected_callback_result(spec, registry)
        read_verified_federation_derivation(
            spec.output_root,
            FederationArtifactRef(synthetic.federation_audit.manifest_sha256),
            held_parents={parent_ref.manifest_sha256: parent_root},
        )
        request = _request(store)
        store.published_kinds.clear()
        with pytest.raises(FederationError, match="Fresh selected graph.*declared leaf below"):
            DefaultFabricPort(
                fetch_data=lambda **kwargs: synthetic, federation=spec, connector_registry=registry
            ).snapshot(store, request)
    finally:
        registry.shutdown()
    assert store.published_kinds == []


@pytest.mark.parametrize("metrics", [[""], [" "], ["\t\n"], ["policy_inputs", "left_input"]])
def test_opt_in_admits_explicit_query_quantity_before_any_callback(
    tmp_path, monkeypatch, metrics
) -> None:
    registry = _registry(tmp_path)
    spec = _spec(tmp_path)
    store = _RecordingCAS(tmp_path / "cas")
    # The legacy fallback would select this request ID for a blank metric.
    request = _request(store, metrics=metrics, request_id="policy_inputs")
    store.published_kinds.clear()
    calls = []

    def forbidden_callback(**kwargs):
        calls.append(kwargs)
        raise AssertionError("unsupported query reached callback")

    async def forbidden_fetch(*args, **kwargs):
        raise AssertionError("unsupported query reached connector")

    monkeypatch.setattr(SQLQueryConnector, "fetch", forbidden_fetch)
    try:
        with pytest.raises(ValueError, match="exactly one nonblank explicit metric"):
            DefaultFabricPort(
                fetch_data=forbidden_callback, connector_registry=registry, federation=spec
            ).snapshot(store, request)
    finally:
        registry.shutdown()
    assert calls == []
    assert store.published_kinds == []
    assert not spec.output_root.exists()


@pytest.mark.parametrize("held_parent", [False, True])
def test_fresh_consumer_refuses_overbound_source_even_when_inner_join_fits(
    tmp_path,
    held_parent,
) -> None:
    from polisyos.fabric.connectors.federation.artifact import persist_federation_derivation
    from polisyos.fabric.connectors.federation.composer import DataComposer
    from polisyos.fabric.connectors.federation.resolver import ConflictResolver

    registry = _registry(tmp_path)
    base = _spec(tmp_path)
    two_rows = pd.DataFrame({"id": [1, 2], "value": [10.0, 11.0]})
    one_row = pd.DataFrame({"id": [1], "value": [20.0]})
    sources = base.sources
    held = {}
    try:
        if held_parent:
            # Genuine producer input/held parent; only the bridge acquisition
            # admission is bypassed by the selected callback below.
            fetched = fabric_get_data(
                dataset_id="left_input", connector_id="sql.query", registry=registry
            )
            metadata = registry.get_entry("sql.query").metadata
            source = SourceMetadata(
                connector_id=metadata.fully_qualified_id,
                metadata=metadata,
                fetched_at=fetched.fetched_at,
                row_count=len(two_rows),
            )
            parent_root = tmp_path / "parent"
            parent_ref = persist_federation_derivation(
                parent_root,
                DataComposer(
                    ConflictResolver(
                        base.composition.conflict_policy,
                        tie_breaker_seed=base.composition.tie_breaker_seed,
                    )
                ),
                [(two_rows, source)],
                base.composition,
            )
            selected = SelectedFederationInput(parent_root, parent_ref, source)
            sources = (selected, base.sources[1])
            held = {parent_ref.manifest_sha256: parent_root}
        spec = replace(
            base,
            sources=sources,
            composition=replace(base.composition, join_how="inner"),
            output_root=tmp_path / "callback-child",
        )
        # Both source artifacts and the child are valid. Their output fits the
        # query; source 0 still exceeds it. No producer precheck is invoked.
        synthetic = _synthetic_selected_callback_result(
            spec,
            registry,
            page_size=1,
            frames={0: two_rows, 1: one_row},
        )
        actual = read_verified_federation_derivation(
            spec.output_root,
            FederationArtifactRef(synthetic.federation_audit.manifest_sha256),
            held_parents=held,
        )
        assert len(actual.data) == 1
        store = _RecordingCAS(tmp_path / "cas")
        request = _request(store, limit=1)
        store.published_kinds.clear()
        with pytest.raises(
            FederationError, match="(?:Selected parent|Declared connector capture).*row bound"
        ):
            DefaultFabricPort(
                fetch_data=lambda **kwargs: synthetic, connector_registry=registry, federation=spec
            ).snapshot(store, request)
        assert store.published_kinds == []
    finally:
        registry.shutdown()


@pytest.mark.parametrize("federated", [False, True])
def test_wave_column_is_not_admitted_survey_basis_on_candidate_route(tmp_path, federated) -> None:
    from polisyos.core.registry import build_default_registry_bundle
    from polisyos.foundry.data_plane.bindings import build_input_bindings, load_input_bindings

    registry = _registry(tmp_path)
    # Wave phenomenon measurements do not supply a repeated-survey design.
    with sqlite3.connect(tmp_path / "inputs.sqlite") as connection:
        connection.execute("CREATE TABLE wave_input (id INTEGER, wave REAL, value REAL)")
        connection.executemany(
            "INSERT INTO wave_input VALUES (?, ?, ?)", [(1, 0.5, 10), (2, 1.5, 20)]
        )
    store = FileSystemCAS(tmp_path / "cas")
    base = _spec(tmp_path)
    spec = replace(base, sources=(FederationFetchSource("sql.query", "wave_input"),))
    request = _request(store, metrics=["policy_inputs" if federated else "wave_input"])
    try:
        ref = DefaultFabricPort(
            connector_registry=registry, federation=spec if federated else None
        ).snapshot(store, request)
    finally:
        registry.shutdown()
    snapshot = _snapshot(store, ref)
    rows = load_core_json_artifact(store, snapshot.data_ref)
    assert [row["wave"] for row in rows] == [0.5, 1.5]
    # Exercise the actual downstream writer and fresh report/binding readers,
    # not a duplicate warning predicate or a marker-only snapshot assertion.
    built = build_input_bindings(
        store,
        data_snapshot_ref=ref,
        registry_bundle_ref=build_default_registry_bundle(store).bundle_ref,
    )
    bindings = load_input_bindings(store, built.input_bindings_ref)
    report = load_core_json_artifact(store, built.input_binding_report_ref)
    survey_warning = "Input snapshot is survey repeated cross-section"
    if federated:
        assert "data_shape" not in snapshot.stats
        assert snapshot.stats["federation_data_shape_basis"] == "not_established"
        assert snapshot.stats["federation_workflow_compatibility_basis"] == "not_established"
        assert not any(
            key in snapshot.stats
            for key in (
                "wave_field",
                "survey_year_field",
                "sample_weight_field",
                "inclusion_probabilities_field",
            )
        )
        # These are the actual definite shape/workflow note fields emitted by
        # the legacy projection, independent of whether shape stats are present.
        # Reject the full advice quantity, not input column names or one value.
        semantic_note_fields = {"data_shape", "allowed_workflows", "blocked_workflows"}
        assert not any(note.partition("=")[0] in semantic_note_fields for note in snapshot.notes)
        warning_payload = load_core_json_artifact(store, snapshot.warnings_ref)
        audit = next(
            warning["data"]
            for warning in warning_payload["warnings"]
            if warning["code"] == "fabric.federation.candidate_derivation"
        )
        assert audit["data_shape_basis"] == "not_established"
        assert audit["workflow_compatibility_basis"] == "not_established"
        assert not any(survey_warning in warning for warning in report["warnings"])
        assert not any("survey_repeated_cross_section" in note for note in bindings.notes)
        assert not any("survey_repeated_cross_section" in note for note in report["notes"])
    else:
        # Compatibility witness only; no new basis is attributed to this legacy
        # heuristic. The new opt-in does not alter the existing default branch.
        assert snapshot.stats["data_shape"] == "survey_repeated_cross_section"
        assert {note.partition("=")[0] for note in snapshot.notes} >= {
            "data_shape",
            "allowed_workflows",
            "blocked_workflows",
        }
        assert any(survey_warning in warning for warning in report["warnings"])
        assert "snapshot.data_shape=survey_repeated_cross_section" in bindings.notes
