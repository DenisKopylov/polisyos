"""Test-first witnesses for FED-02 bounded federation composition."""

from __future__ import annotations

import gc
import weakref
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

from polisyos.fabric.connectors.federation import (
    AuditLevel,
    CompositionRequest,
    CompositionStrategy,
    ConflictPolicy,
    ConflictResolver,
    DataComposer,
    FederationError,
    MergeLogEntry,
)
from polisyos.fabric.connectors.federation.composer import MergeLogCollector
from polisyos.fabric.connectors.federation.types import SourceMetadata
from polisyos.ir.connectors import ConnectorMetadataSpec, QualityTier, TrustLevel


def _source_metadata(
    short_id: str,
    *,
    trust_level: TrustLevel = TrustLevel.HIGH,
) -> SourceMetadata:
    metadata = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace="fed02.test",
        source_name=f"Source {short_id}",
        source_organization="PolicyOS test",
        trust_level=trust_level,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
    )
    return SourceMetadata(
        connector_id=metadata.fully_qualified_id,
        metadata=metadata,
        fetched_at=datetime(2024, 1, 1, tzinfo=UTC),
        row_count=0,
    )


def _compose_request(
    strategy: CompositionStrategy,
    *,
    audit_level: AuditLevel = AuditLevel.NONE,
    **kwargs: object,
) -> CompositionRequest:
    return CompositionRequest(
        dataset_pattern="fed02.test",
        strategy=strategy,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        audit_level=audit_level,
        **kwargs,
    )


def _composer() -> DataComposer:
    return DataComposer(conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST))


def test_equal_priority_summary_heap_does_not_compare_merge_log_payloads() -> None:
    """Stable-hash ties preserve conflict details and deterministic sample order."""
    chosen_values: list[list[object]] = []
    for _ in range(2):
        collector = MergeLogCollector(
            audit_level=AuditLevel.SUMMARY,
            sample_size=2,
            max_entries=1,
            seed="fed02-equal-priority",
        )
        # Stable sampling deliberately excludes values, so same row/source/policy
        # entries tie even when the conflicting payloads differ.
        for left_value, right_value in ((10, 11), (12, 13)):
            collector.record(
                MergeLogEntry(
                    row_key={"id": 7},
                    column="value",
                    source_a_id="source-a",
                    source_b_id="source-b",
                    source_a_value={"payload": left_value},
                    source_b_value={"payload": right_value},
                    chosen_value={"payload": left_value},
                    resolution_policy=ConflictPolicy.TRUST_HIGHEST.value,
                )
            )
        collector.finalize()

        assert collector.summary.total_conflicts == 2
        assert len(collector.summary.sample_entries) == 2
        chosen_values.append(
            [entry.chosen_value["payload"] for entry in collector.summary.sample_entries]
        )

    assert chosen_values == [[10, 12], [10, 12]]


def test_empty_union_preserves_declared_columns_and_dtypes() -> None:
    """A valid empty source remains a typed empty UNION result."""
    source = pd.DataFrame(
        {
            "id": pd.Series([], dtype="int64"),
            "measure": pd.Series([], dtype="float64"),
        }
    )
    request = _compose_request(
        CompositionStrategy.UNION,
        key_columns=["id"],
    )

    result, merge_log = _composer().compose(
        sources=[(source, _source_metadata("empty"))],
        strategy=request.strategy,
        request=request,
    )

    assert result.empty
    assert result.columns.tolist() == source.columns.tolist()
    assert result.dtypes.equals(source.dtypes)
    assert merge_log == []


def test_empty_duckdb_source_union_persists_and_reads_back_typed_schema(tmp_path: Path) -> None:
    """DuckDB production/readback keeps an empty UNION's declared SQL types."""
    duckdb = pytest.importorskip("duckdb")
    database_path = tmp_path / "empty-source.duckdb"
    connection = duckdb.connect(str(database_path))
    try:
        connection.execute(
            "CREATE TABLE empty_source (id BIGINT, measure DOUBLE)"
        )
        source = connection.execute("SELECT * FROM empty_source").df()
        request = _compose_request(
            CompositionStrategy.UNION,
            key_columns=["id"],
        )
        result, merge_log = _composer().compose(
            sources=[(source, _source_metadata("empty_duckdb"))],
            strategy=request.strategy,
            request=request,
        )
        assert result.empty
        assert result.dtypes.equals(source.dtypes)
        assert merge_log == []

        connection.register("composed_empty", result)
        connection.execute(
            "CREATE TABLE composed_empty_result AS SELECT * FROM composed_empty"
        )
    finally:
        connection.close()

    readback = duckdb.connect(str(database_path), read_only=True)
    try:
        schema = readback.execute(
            "DESCRIBE composed_empty_result"
        ).fetchall()
        rows = readback.execute(
            "SELECT * FROM composed_empty_result"
        ).fetchall()
    finally:
        readback.close()

    assert [(name, sql_type) for name, sql_type, *_ in schema] == [
        ("id", "BIGINT"),
        ("measure", "DOUBLE"),
    ]
    assert rows == []


def test_union_without_sources_is_not_typed_empty() -> None:
    """An absent source set remains a federation error, not an empty dataset."""
    request = _compose_request(
        CompositionStrategy.UNION,
        key_columns=["id"],
    )

    with pytest.raises(FederationError, match="no sources"):
        _composer().compose(sources=[], strategy=request.strategy, request=request)


def test_union_summary_bounds_live_detail_objects_and_counts_every_conflict() -> None:
    """SUMMARY retains only sampled detail objects while counting all conflicts."""
    row_count = 80
    source_a = pd.DataFrame({"id": range(row_count), "value": [10] * row_count})
    source_b = pd.DataFrame({"id": range(row_count), "value": [11] * row_count})
    request = _compose_request(
        CompositionStrategy.UNION,
        audit_level=AuditLevel.SUMMARY,
        key_columns=["id"],
        audit_sample_size=1,
        audit_max_entries=1,
        audit_seed="fed02-bounded-summary",
    )

    class TrackingResolver(ConflictResolver):
        def __init__(self, *, retain_all: bool = False) -> None:
            super().__init__(policy=ConflictPolicy.TRUST_HIGHEST)
            self.entry_refs: list[weakref.ReferenceType[MergeLogEntry]] = []
            self.retained_entries: list[MergeLogEntry] = []
            self.retain_all = retain_all

        def resolve_conflict(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            resolution = super().resolve_conflict(*args, **kwargs)
            if resolution.log_entry is not None:
                self.entry_refs.append(weakref.ref(resolution.log_entry))
                if self.retain_all:
                    self.retained_entries.append(resolution.log_entry)
            return resolution

    def run_census(*, retain_all: bool) -> tuple[int, int, int]:
        resolver = TrackingResolver(retain_all=retain_all)
        composer = DataComposer(conflict_resolver=resolver)
        result, merge_log = composer.compose(
            sources=[
                (source_a, _source_metadata("source_a")),
                (
                    source_b,
                    _source_metadata("source_b", trust_level=TrustLevel.MEDIUM),
                ),
            ],
            strategy=request.strategy,
            request=request,
        )
        summary = composer.get_last_merge_summary()
        assert summary is not None
        assert summary.total_conflicts == row_count
        assert summary.by_policy[ConflictPolicy.TRUST_HIGHEST.value] == row_count
        assert result["value"].tolist() == [10] * row_count
        assert len(merge_log) == 1
        assert len(summary.sample_entries) == 1

        gc.collect()
        live_details = sum(reference() is not None for reference in resolver.entry_refs)
        return summary.total_conflicts, len(resolver.entry_refs), live_details

    assert run_census(retain_all=False) == (row_count, row_count, 1)
    # Control: the same observer sees unbounded detail when a consumer holds
    # every returned entry, so the test measures live objects, not a local name.
    assert run_census(retain_all=True) == (row_count, row_count, row_count)


def test_overlay_prepares_each_secondary_once_and_skips_none_audit_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """OVERLAY reads a persisted source once and emits no NONE audit details."""
    duckdb = pytest.importorskip("duckdb")
    database_path = tmp_path / "overlay.duckdb"
    connection = duckdb.connect(str(database_path))
    primary_frame = pd.DataFrame(
        {
            "id": [1, 2],
            "first": [None, None],
            "second": [None, None],
            "third": [None, None],
        }
    )
    secondary_frame = pd.DataFrame(
        {
            "id": [1, 2],
            "first": [10, 11],
            "second": [20, 21],
            "third": [30, 31],
        }
    )
    connection.register("primary_frame", primary_frame)
    connection.register("secondary_frame", secondary_frame)
    connection.execute("CREATE TABLE primary_source AS SELECT * FROM primary_frame")
    connection.execute(
        "CREATE TABLE secondary_source AS SELECT * FROM secondary_frame"
    )
    primary = connection.execute("SELECT * FROM primary_source").df()
    secondary = connection.execute("SELECT * FROM secondary_source").df()
    request = _compose_request(
        CompositionStrategy.OVERLAY,
        key_columns=["id"],
        primary_source=_source_metadata("primary").connector_id,
    )

    original_set_index = pd.DataFrame.set_index
    set_index_calls = 0

    def counting_set_index(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal set_index_calls
        set_index_calls += 1
        return original_set_index(self, *args, **kwargs)

    created_entries = 0

    original_entry = MergeLogEntry

    def tracking_entry(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal created_entries
        created_entries += 1
        return original_entry(*args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "set_index", counting_set_index)
    monkeypatch.setattr(
        "polisyos.fabric.connectors.federation.composer.MergeLogEntry",
        tracking_entry,
    )

    result, merge_log = _composer().compose(
        sources=[
            (primary, _source_metadata("primary")),
            (secondary, _source_metadata("secondary")),
        ],
        strategy=request.strategy,
        request=request,
    )

    assert set_index_calls == 2
    assert created_entries == 0
    assert merge_log == []
    assert result.set_index("id")[["first", "second", "third"]].to_dict("list") == {
        "first": [10, 11],
        "second": [20, 21],
        "third": [30, 31],
    }
    connection.register("composed_overlay", result)
    connection.execute(
        "CREATE TABLE overlay_result AS SELECT * FROM composed_overlay"
    )
    connection.close()

    readback = duckdb.connect(str(database_path), read_only=True)
    try:
        persisted = readback.execute(
            "SELECT id, first, second, third FROM overlay_result ORDER BY id"
        ).fetchall()
    finally:
        readback.close()

    assert persisted == [(1, 10.0, 20.0, 30.0), (2, 11.0, 21.0, 31.0)]
