"""Test-first witnesses for FED-02 bounded federation composition."""

from __future__ import annotations

import gc
import hashlib
import json
import sys
import weakref
from datetime import UTC, datetime

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
    """Equal sample priorities retain entries without ordering their payloads."""
    collector = MergeLogCollector(
        audit_level=AuditLevel.SUMMARY,
        sample_size=2,
        max_entries=1,
        seed="fed02-equal-priority",
    )
    first = MergeLogEntry(
        row_key={"id": 7},
        column="value",
        source_a_id="source-a",
        source_b_id="source-b",
        source_a_value={"payload": 10},
        source_b_value={"payload": 11},
        chosen_value={"payload": 10},
        resolution_policy=ConflictPolicy.TRUST_HIGHEST.value,
    )
    second = MergeLogEntry(
        row_key={"id": 7},
        column="value",
        source_a_id="source-a",
        source_b_id="source-b",
        source_a_value={"payload": 12},
        source_b_value={"payload": 13},
        chosen_value={"payload": 12},
        resolution_policy=ConflictPolicy.TRUST_HIGHEST.value,
    )

    collector.record(first)
    collector.record(second)
    collector.finalize()

    assert collector.summary.total_conflicts == 2
    assert len(collector.summary.sample_entries) == 2
    assert {entry.chosen_value["payload"] for entry in collector.summary.sample_entries} == {
        10,
        12,
    }


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


def test_empty_union_sql_readback_preserves_declared_types(tmp_path) -> None:
    """One registered empty SQL source persists as a typed zero-row result."""
    duckdb = pytest.importorskip("duckdb")
    from polisyos.fabric.connectors.contracts import (
        DataSchema,
        FieldSpec,
        SchemaType,
    )

    database = tmp_path / "typed-empty.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.execute(
            "CREATE TABLE registered_source "
            "(id BIGINT, measure DOUBLE, label VARCHAR)"
        )
        source = connection.execute(
            "SELECT id, measure, label FROM registered_source"
        ).df()
        schema = DataSchema(
            schema_id="fed02.typed_empty",
            version="1.0.0",
            fields=(
                FieldSpec(name="id", data_type=SchemaType.INT64),
                FieldSpec(name="measure", data_type=SchemaType.FLOAT64),
                FieldSpec(name="label", data_type=SchemaType.STRING),
            ),
            primary_key=("id",),
            grain_dims=("id",),
        )
        request = _compose_request(
            CompositionStrategy.UNION,
            schema=schema,
        )
        result, merge_log = _composer().compose(
            sources=[(source, _source_metadata("duckdb_empty"))],
            strategy=request.strategy,
            request=request,
        )
        connection.register("composed_frame", result)
        connection.execute("CREATE TABLE persisted_result AS SELECT * FROM composed_frame")

        actual_schema = connection.execute("DESCRIBE persisted_result").fetchall()
        actual_count = connection.execute(
            "SELECT count(*) FROM persisted_result"
        ).fetchone()[0]
    with duckdb.connect(str(database), read_only=True) as reopened:
        persisted = reopened.execute(
            "SELECT id, measure, label FROM persisted_result"
        ).df()

    assert result.empty
    assert merge_log == []
    assert [(row[0], row[1]) for row in actual_schema] == [
        ("id", "BIGINT"),
        ("measure", "DOUBLE"),
        ("label", "VARCHAR"),
    ]
    assert actual_count == 0
    assert persisted.empty
    assert persisted.columns.tolist() == ["id", "measure", "label"]


def test_union_without_sources_is_not_typed_empty() -> None:
    """An absent source set remains a federation error, not an empty dataset."""
    request = _compose_request(
        CompositionStrategy.UNION,
        key_columns=["id"],
    )

    with pytest.raises(FederationError, match="no sources"):
        _composer().compose(sources=[], strategy=request.strategy, request=request)


def test_join_summary_is_bounded_and_matches_independent_relational_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JOIN SUMMARY exposes seeded top-k events while preserving complete counters."""
    row_count = 80
    event_ids = [f"event-{index:03d}" for index in range(row_count)]
    source_a = pd.DataFrame({"event_id": event_ids, "value": [10] * row_count})
    source_b = pd.DataFrame({"event_id": event_ids, "value": [20] * row_count})
    meta_a = _source_metadata("join_a", trust_level=TrustLevel.HIGH)
    meta_b = _source_metadata("join_b", trust_level=TrustLevel.HIGH)
    tie_seed = "fed02-join-equal-priority"
    audit_seed = "fed02-join-summary-seed"

    # Independent stdlib-only relational and hash oracles. The source rows
    # intentionally repeat the same values: event identity alone distinguishes
    # 80 separate conflict records.
    def digest(payload: dict[str, object]) -> int:
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return int(hashlib.sha256(encoded).hexdigest(), 16)

    expected_values: dict[str, int] = {}
    summary_ranks: list[tuple[int, int, str]] = []
    for sequence, event_id in enumerate(event_ids):
        row_key = {"event_id": event_id}
        source_ranks = {
            source_id: digest(
                {
                    "seed": tie_seed,
                    "source_id": source_id,
                    "row_key": row_key,
                    "column": "value",
                }
            )
            for source_id in (meta_a.connector_id, meta_b.connector_id)
        }
        expected_source = min(source_ranks, key=source_ranks.get)
        expected_values[event_id] = 10 if expected_source == meta_a.connector_id else 20
        summary_ranks.append(
            (
                digest(
                    {
                        "seed": audit_seed,
                        "row_key": row_key,
                        "column": "value",
                        "source_a": meta_a.connector_id,
                        "source_b": meta_b.connector_id,
                        "policy": ConflictPolicy.TRUST_HIGHEST.value,
                    }
                ),
                sequence,
                event_id,
            )
        )
    expected_top_three = [event_id for _, _, event_id in sorted(summary_ranks)[:3]]
    expected_join = [
        (event_id, expected_values[event_id]) for event_id in event_ids
    ]

    original_record = MergeLogCollector.record
    observed_refs: list[weakref.ReferenceType[MergeLogEntry]] = []
    record_frame_live = [True]

    def observe_record(self, entry):  # type: ignore[no-untyped-def]
        if record_frame_live[0]:
            observed_refs.append(weakref.ref(entry))
        return original_record(self, entry)

    monkeypatch.setattr(MergeLogCollector, "record", observe_record)
    join_code = DataComposer._join.__code__
    active_peak = [0]
    previous_trace = sys.gettrace()

    def trace(frame, event, arg):  # type: ignore[no-untyped-def]
        if frame.f_code is join_code:
            live = sum(reference() is not None for reference in observed_refs)
            active_peak[0] = max(active_peak[0], live)
        del arg
        return trace

    def compose(audit_level: AuditLevel, *, sample_size: int = 0):
        request = _compose_request(
            CompositionStrategy.JOIN,
            audit_level=audit_level,
            join_keys=["event_id"],
            join_validate="one_to_one",
            audit_sample_size=sample_size,
            audit_max_entries=sample_size,
            audit_seed=audit_seed,
            tie_breaker_seed=tie_seed,
        )
        composer = _composer()
        frame, merge_log = composer.compose(
            sources=[(source_a, meta_a), (source_b, meta_b)],
            strategy=request.strategy,
            request=request,
        )
        return composer, frame, merge_log

    summary_runs = []
    try:
        for cap in (1, 3):
            observed_refs.clear()
            active_peak[0] = 0
            sys.settrace(trace)
            composer, frame, merge_log = compose(AuditLevel.SUMMARY, sample_size=cap)
            sys.settrace(previous_trace)

            summary = composer.get_last_merge_summary()
            assert summary is not None
            assert list(frame[["event_id", "value"]].itertuples(index=False, name=None)) == expected_join
            assert summary.total_conflicts == row_count
            assert summary.by_policy == {ConflictPolicy.TRUST_HIGHEST.value: row_count}
            assert summary.by_conflict_type == {"duplicate_column": row_count}
            assert summary.by_column == {"value": row_count}
            assert summary.by_source_pair == {
                f"{meta_a.connector_id}->{meta_b.connector_id}": row_count
            }
            assert len(merge_log) == cap
            assert [entry.row_key["event_id"] for entry in merge_log] == expected_top_three[:cap]
            assert summary.sample_entries == merge_log
            assert active_peak[0] <= cap + 4
            gc.collect()
            assert sum(reference() is not None for reference in observed_refs) <= cap
            summary_runs.append(frame)

        full_composer, full_frame, full_log = compose(AuditLevel.FULL)
        none_composer, none_frame, none_log = compose(AuditLevel.NONE)
    finally:
        sys.settrace(previous_trace)
        record_frame_live[0] = False

    pd.testing.assert_frame_equal(summary_runs[0], full_frame)
    pd.testing.assert_frame_equal(summary_runs[0], none_frame)
    assert len(full_log) == row_count
    assert none_log == []
    assert full_composer.get_last_merge_summary().total_conflicts == row_count
    assert none_composer.get_last_merge_summary().total_conflicts == 0


def test_union_summary_measures_active_detail_liveness_and_transient_list_mutant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live-object oracle catches an unnamed transient list hidden until return."""
    row_count = 80
    source_a = pd.DataFrame({"id": range(row_count), "value": [10] * row_count})
    source_b = pd.DataFrame({"id": range(row_count), "value": [11] * row_count})
    union_code = DataComposer._union.__code__
    original_record = MergeLogCollector.record
    observed_refs: list[weakref.ReferenceType[MergeLogEntry]] = []
    active_peak = [0]
    active_code = [union_code]
    observe_entries = [True]

    def observe_record(self, entry):  # type: ignore[no-untyped-def]
        if observe_entries[0]:
            observed_refs.append(weakref.ref(entry))
        return original_record(self, entry)

    monkeypatch.setattr(MergeLogCollector, "record", observe_record)
    previous_trace = sys.gettrace()

    def trace(frame, event, arg):  # type: ignore[no-untyped-def]
        if frame.f_code is active_code[0]:
            live = sum(reference() is not None for reference in observed_refs)
            active_peak[0] = max(active_peak[0], live)
        del arg
        return trace


    def run(cap: int):
        request = _compose_request(
            CompositionStrategy.UNION,
            audit_level=AuditLevel.SUMMARY,
            key_columns=["id"],
            audit_sample_size=cap,
            audit_max_entries=cap,
            audit_seed="fed02-bounded-summary",
        )
        composer = _composer()
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
        return composer, result, merge_log

    try:
        for cap in (1, 3):
            observed_refs.clear()
            active_peak[0] = 0
            active_code[0] = union_code
            sys.settrace(trace)
            composer, result, merge_log = run(cap)
            sys.settrace(previous_trace)
            summary = composer.get_last_merge_summary()
            assert summary is not None
            assert summary.total_conflicts == row_count
            assert summary.by_policy[ConflictPolicy.TRUST_HIGHEST.value] == row_count
            assert summary.by_column["<row>"] == row_count
            assert result["value"].tolist() == [10] * row_count
            assert len(merge_log) == cap
            assert active_peak[0] <= cap + 4
            gc.collect()
            assert sum(reference() is not None for reference in observed_refs) <= cap

        # Adversarial mutant: retain every real detail object in an arbitrary
        # local list through _union's return. The monitor never inspects local
        # variable names and samples the transient peak while the frame is live.
        observed_refs.clear()
        active_peak[0] = 0
        composer = _composer()
        base_union = composer._union

        def transient_retention(sources, request, collector):  # type: ignore[no-untyped-def]
            stash = []
            record = collector.record

            def append_detail(entry):  # type: ignore[no-untyped-def]
                stash.append(entry)
                record(entry)

            collector.record = append_detail
            return base_union(sources, request, collector)

        monkeypatch.setattr(composer, "_union", transient_retention)
        cap_one_request = _compose_request(
            CompositionStrategy.UNION,
            audit_level=AuditLevel.SUMMARY,
            key_columns=["id"],
            audit_sample_size=1,
            audit_max_entries=1,
            audit_seed="fed02-bounded-summary",
        )
        active_code[0] = transient_retention.__code__
        sys.settrace(trace)
        mutant_result, mutant_sample = composer.compose(
            sources=[
                (source_a, _source_metadata("source_a")),
                (
                    source_b,
                    _source_metadata("source_b", trust_level=TrustLevel.MEDIUM),
                ),
            ],
            strategy=cap_one_request.strategy,
            request=cap_one_request,
        )
        sys.settrace(previous_trace)
        mutant_summary = composer.get_last_merge_summary()
        assert mutant_summary is not None
        assert mutant_summary.total_conflicts == row_count
        assert mutant_result["value"].tolist() == [10] * row_count
        assert len(mutant_sample) == 1
        assert active_peak[0] >= row_count
        gc.collect()
        assert sum(reference() is not None for reference in observed_refs) == 1
    finally:
        sys.settrace(previous_trace)
        observe_entries[0] = False


def test_overlay_prepares_each_secondary_once_and_skips_none_audit_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OVERLAY reuses one secondary index and does not materialize NONE logs."""
    primary = pd.DataFrame(
        {
            "id": [1, 2],
            "first": [None, None],
            "second": [None, None],
            "third": [None, None],
        }
    )
    secondary = pd.DataFrame(
        {
            "id": [1, 2],
            "first": [10, 11],
            "second": [20, 21],
            "third": [30, 31],
        }
    )
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

    def unexpected_entry(*args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal created_entries
        created_entries += 1
        return object()

    monkeypatch.setattr(pd.DataFrame, "set_index", counting_set_index)
    monkeypatch.setattr(
        "polisyos.fabric.connectors.federation.composer.MergeLogEntry",
        unexpected_entry,
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


def test_overlay_multi_source_matches_nested_loop_and_audit_oracle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OVERLAY reuses indexes while preserving null masks, source order and audit."""
    primary = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "a": [None, None, 90],
            "b": [None, 20, None],
            "c": [None, None, None],
            "d": ["keep-1", None, "keep-3"],
        }
    )
    secondary_one = pd.DataFrame(
        {
            "id": [1, 2],
            "a": [10, 11],
            "b": [None, 22],
            "c": [30, 31],
            "d": ["first-1", "first-2"],
        }
    )
    secondary_two = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "a": [100, 110, 120],
            "b": [200, 220, 230],
            "c": [300, 310, 320],
            "d": ["second-1", "second-2", "second-3"],
        }
    )
    meta_primary = _source_metadata("overlay_primary")
    meta_one = _source_metadata("overlay_first", trust_level=TrustLevel.MEDIUM)
    meta_two = _source_metadata("overlay_second", trust_level=TrustLevel.LOW)
    request = _compose_request(
        CompositionStrategy.OVERLAY,
        audit_level=AuditLevel.FULL,
        key_columns=["id"],
        primary_source=meta_primary.connector_id,
    )

    original_set_index = pd.DataFrame.set_index
    set_index_calls = 0

    def count_set_index(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal set_index_calls
        set_index_calls += 1
        return original_set_index(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "set_index", count_set_index)
    result, merge_log = _composer().compose(
        sources=[
            (primary, meta_primary),
            (secondary_one, meta_one),
            (secondary_two, meta_two),
        ],
        strategy=request.strategy,
        request=request,
    )

    primary_rows = [dict(row) for row in primary.to_dict("records")]
    secondary_rows = [
        {row["id"]: row for row in frame.to_dict("records")}
        for frame in (secondary_one, secondary_two)
    ]
    columns = ["a", "b", "c", "d"]
    expected_logs: list[tuple[dict[str, int], str, str, object]] = []
    for column in columns:
        for row in primary_rows:
            if row[column] is not None and not pd.isna(row[column]):
                continue
            for source_rows, metadata in zip(
                secondary_rows, (meta_one, meta_two), strict=True
            ):
                candidate = source_rows.get(row["id"], {}).get(column)
                if candidate is None or pd.isna(candidate):
                    continue
                row[column] = candidate
                expected_logs.append(
                    ({"id": row["id"]}, column, metadata.connector_id, candidate)
                )
                break

    observed_rows = [
        {
            column: None if pd.isna(value) else value
            for column, value in row.items()
        }
        for row in result.to_dict("records")
    ]
    expected_rows = [
        {column: None if pd.isna(value) else value for column, value in row.items()}
        for row in primary_rows
    ]
    observed_logs = [
        (entry.row_key, entry.column, entry.source_b_id, entry.chosen_value)
        for entry in merge_log
    ]

    assert observed_rows == expected_rows
    assert observed_logs == expected_logs
    assert all(entry.source_a_id == meta_primary.connector_id for entry in merge_log)
    assert all(entry.conflict_type == "null_fill" for entry in merge_log)
    assert set_index_calls == 3
