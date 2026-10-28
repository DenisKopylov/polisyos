"""Test-first witnesses for FED-02 bounded federation composition."""

from __future__ import annotations

import hashlib
import json
import sys
import tracemalloc
import weakref
from dataclasses import replace
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
    MergeLogSummary,
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


def test_union_without_sources_is_not_typed_empty() -> None:
    """An absent source set remains a federation error, not an empty dataset."""
    request = _compose_request(
        CompositionStrategy.UNION,
        key_columns=["id"],
    )

    with pytest.raises(FederationError, match="no sources"):
        _composer().compose(sources=[], strategy=request.strategy, request=request)


def test_union_summary_has_one_bounded_collector_and_exact_conflict_count() -> None:
    """SUMMARY exposes one sample while retaining the complete conflict count."""
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

    captured_locals: dict[str, object] = {}
    union_code = DataComposer._union.__code__
    previous_trace = sys.gettrace()
    composer = _composer()

    def trace(frame, event, arg):  # type: ignore[no-untyped-def]
        if frame.f_code is union_code and event == "return":
            captured_locals.update(frame.f_locals)
        del arg
        return trace

    sys.settrace(trace)
    try:
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
    finally:
        sys.settrace(previous_trace)

    summary = composer.get_last_merge_summary()
    assert summary is not None
    assert summary.total_conflicts == row_count
    assert summary.by_policy[ConflictPolicy.TRUST_HIGHEST.value] == row_count
    assert result["value"].tolist() == [10] * row_count
    assert len(merge_log) == 1
    assert "merge_log" not in captured_locals


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


def _federation_join_case(
    left_values: list[int],
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
    SourceMetadata,
    SourceMetadata,
]:
    """Build distinct left events that intentionally share one JOIN key."""
    left = pd.DataFrame(
        {
            "key": [1] * len(left_values),
            "event_id": [f"event-{index}" for index in range(len(left_values))],
            "value": left_values,
        }
    )
    right = pd.DataFrame({"key": [1], "value": [11]})
    return (
        left,
        right,
        _source_metadata("join_left", trust_level=TrustLevel.HIGH),
        _source_metadata("join_right", trust_level=TrustLevel.MEDIUM),
    )


def _federation_join_request(
    audit_level: AuditLevel,
    *,
    sample_size: int = 3,
    max_entries: int = 3,
    seed: str = "fed02-join-repeat-key",
) -> CompositionRequest:
    return _compose_request(
        CompositionStrategy.JOIN,
        audit_level=audit_level,
        join_keys=["key"],
        join_how="left",
        join_validate="many_to_one",
        audit_sample_size=sample_size,
        audit_max_entries=max_entries,
        audit_seed=seed,
    )


def _reference_join_sample_ids(
    left: pd.DataFrame,
    left_metadata: SourceMetadata,
    right_metadata: SourceMetadata,
    *,
    seed: str,
    cap: int,
) -> list[str]:
    """Independently rank source-row conflicts using the declared stable inputs."""
    conflicts: list[tuple[int, int, str]] = []
    right_values = {1: 11}
    for ordinal, row in left.iterrows():
        right_value = right_values[row["key"]]
        if row["value"] == right_value:
            continue
        event_id = str(row["event_id"])
        payload = {
            "seed": seed,
            "row_key": {"key": row["key"]},
            "column": "value",
            "source_a": left_metadata.connector_id,
            "source_b": right_metadata.connector_id,
            "policy": ConflictPolicy.TRUST_HIGHEST.value,
        }
        encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        priority = int(hashlib.sha256(encoded).hexdigest(), 16)
        conflicts.append((priority, int(ordinal), event_id))
    return [
        event_id for _, _, event_id in sorted(conflicts, key=lambda item: (item[0], item[1]))[:cap]
    ]


def _event_ids_from_distinct_join_logs(
    entries: list[MergeLogEntry],
    left: pd.DataFrame,
) -> list[str]:
    """Read actual event occurrence independently of whether payload values duplicate."""
    return [str(left.iloc[entry.row_index]["event_id"]) for entry in entries]


def test_join_summary_is_bounded_deterministic_and_preserves_full_counters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real JOIN owner handles repeated equal-priority sample keys."""
    left, right, left_meta, right_meta = _federation_join_case([10, 12])
    seed = "fed02-join-repeat-key"
    expected_result = pd.DataFrame(
        {"key": [1, 1], "event_id": ["event-0", "event-1"], "value": [10, 12]}
    )
    sampled_results: dict[int, tuple[pd.DataFrame, list[MergeLogEntry]]] = {}

    for cap in (1, 3):
        request = _federation_join_request(AuditLevel.SUMMARY, sample_size=cap, seed=seed)
        composer = _composer()
        live_references: list[weakref.ReferenceType[MergeLogEntry]] = []
        live_counts: list[int] = []
        heap_sizes: list[int] = []
        original_record = MergeLogCollector.record

        def record_and_count(
            self: MergeLogCollector,
            entry: MergeLogEntry,
            *,
            _original_record=original_record,
            _live_references=live_references,
            _live_counts=live_counts,
            _heap_sizes=heap_sizes,
        ) -> None:
            _original_record(self, entry)
            _live_references.append(weakref.ref(entry))
            _live_counts.append(sum(reference() is not None for reference in _live_references))
            _heap_sizes.append(len(self._sample_heap))

        with monkeypatch.context() as scoped:
            scoped.setattr(MergeLogCollector, "record", record_and_count)
            result, merge_log = composer.compose(
                sources=[(left, left_meta), (right, right_meta)],
                strategy=CompositionStrategy.JOIN,
                request=request,
            )
        summary = composer.get_last_merge_summary()
        assert summary is not None
        assert result.reset_index(drop=True).equals(expected_result)
        assert summary.total_conflicts == 2
        assert summary.by_column == {"value": 2}
        assert summary.by_conflict_type == {"duplicate_column": 2}
        assert summary.by_policy == {ConflictPolicy.TRUST_HIGHEST.value: 2}
        assert summary.by_source_pair == {f"{left_meta.connector_id}->{right_meta.connector_id}": 2}
        assert max(live_counts) <= cap + 1
        assert max(heap_sizes) <= cap
        assert len(merge_log) == min(cap, 2)
        assert _event_ids_from_distinct_join_logs(merge_log, left) == (
            _reference_join_sample_ids(
                left,
                left_meta,
                right_meta,
                seed=seed,
                cap=cap,
            )
        )

        repeated_composer = _composer()
        repeated_result, repeated_log = repeated_composer.compose(
            sources=[(left, left_meta), (right, right_meta)],
            strategy=CompositionStrategy.JOIN,
            request=request,
        )
        assert repeated_result.equals(result)
        assert repeated_log == merge_log
        sampled_results[cap] = (result, merge_log)

    # Equal priorities are normal for repeated join keys. Distinct source events
    # with an identical payload remain two conflict observations, not one.
    duplicate_left, duplicate_right, duplicate_left_meta, duplicate_right_meta = (
        _federation_join_case([10, 10])
    )
    duplicate_request = _federation_join_request(AuditLevel.SUMMARY, sample_size=3)
    duplicate_composer = _composer()
    duplicate_result, duplicate_log = duplicate_composer.compose(
        sources=[
            (duplicate_left, duplicate_left_meta),
            (duplicate_right, duplicate_right_meta),
        ],
        strategy=CompositionStrategy.JOIN,
        request=duplicate_request,
    )
    duplicate_summary = duplicate_composer.get_last_merge_summary()
    assert duplicate_result["event_id"].tolist() == ["event-0", "event-1"]
    assert duplicate_summary is not None
    assert duplicate_summary.total_conflicts == 2
    assert len(duplicate_log) == 2
    assert {entry.row_index for entry in duplicate_log} == {0, 1}
    assert all(entry.source_a_occurrence and entry.source_b_occurrence for entry in duplicate_log)
    for cap in (1, 3):
        duplicate_request = replace(duplicate_request, audit_sample_size=cap)
        duplicate_result, actual_log = duplicate_composer.compose(
            [(duplicate_left, duplicate_left_meta), (duplicate_right, duplicate_right_meta)],
            CompositionStrategy.JOIN,
            duplicate_request,
        )
        assert _event_ids_from_distinct_join_logs(
            actual_log, duplicate_left
        ) == _reference_join_sample_ids(
            duplicate_left,
            duplicate_left_meta,
            duplicate_right_meta,
            seed=duplicate_request.audit_seed or "",
            cap=cap,
        )

    # Audit modes alter detail retention only; the numeric result is identical
    # for the same ordered inputs and request semantics.
    full_composer = _composer()
    full_result, full_log = full_composer.compose(
        sources=[(left, left_meta), (right, right_meta)],
        strategy=CompositionStrategy.JOIN,
        request=_federation_join_request(AuditLevel.FULL, sample_size=3, max_entries=3),
    )
    full_summary = full_composer.get_last_merge_summary()
    none_composer = _composer()
    none_result, none_log = none_composer.compose(
        sources=[(left, left_meta), (right, right_meta)],
        strategy=CompositionStrategy.JOIN,
        request=_federation_join_request(AuditLevel.NONE, sample_size=3, max_entries=3),
    )
    none_summary = none_composer.get_last_merge_summary()
    pd.testing.assert_frame_equal(full_result, sampled_results[3][0])
    pd.testing.assert_frame_equal(none_result, sampled_results[3][0])
    assert full_summary is not None and full_summary.total_conflicts == 2
    assert len(full_log) == 2
    assert none_summary is not None and none_summary.total_conflicts == 0
    assert none_log == []


def _run_union_with_live_detail_census(
    monkeypatch: pytest.MonkeyPatch,
    *,
    audit_level: AuditLevel,
    retain_all_transiently: bool,
) -> tuple[pd.DataFrame, list[MergeLogEntry], MergeLogSummary, list[int], int]:
    """Count live detail objects while the real DataComposer._union is active."""
    row_count = 80
    source_a = pd.DataFrame({"id": range(row_count), "value": [10] * row_count})
    source_b = pd.DataFrame({"id": range(row_count), "value": [11] * row_count})
    metadata_a = _source_metadata("source_a")
    metadata_b = _source_metadata("source_b", trust_level=TrustLevel.MEDIUM)
    request = _compose_request(
        CompositionStrategy.UNION,
        audit_level=audit_level,
        key_columns=["id"],
        audit_sample_size=1,
        audit_max_entries=1,
        audit_seed="fed02-live-union-details",
    )
    references: list[weakref.ReferenceType[MergeLogEntry]] = []
    live_counts: list[int] = []
    transient_retention: list[MergeLogEntry] = []
    original_record = MergeLogCollector.record

    def record_and_count(self: MergeLogCollector, entry: MergeLogEntry) -> None:
        original_record(self, entry)
        references.append(weakref.ref(entry))
        if retain_all_transiently:
            # Negative control for the prior hidden local list: keep actual
            # details alive without changing the collector's visible cap.
            transient_retention.append(entry)
        live_counts.append(sum(reference() is not None for reference in references))

    monkeypatch.setattr(MergeLogCollector, "record", record_and_count)
    composer = _composer()
    result, merge_log = composer.compose(
        sources=[(source_a, metadata_a), (source_b, metadata_b)],
        strategy=CompositionStrategy.UNION,
        request=request,
    )
    summary = composer.get_last_merge_summary()
    assert summary is not None
    return result, merge_log, summary, live_counts, len(transient_retention)


@pytest.mark.parametrize("audit_level", [AuditLevel.SUMMARY, AuditLevel.FULL])
def test_union_bounds_live_details_while_preserving_complete_conflict_counts(
    monkeypatch: pytest.MonkeyPatch,
    audit_level: AuditLevel,
) -> None:
    """An 80-conflict UNION retains only the configured detail sample/list."""
    with monkeypatch.context() as scoped:
        result, merge_log, summary, live_counts, transient_count = (
            _run_union_with_live_detail_census(
                scoped,
                audit_level=audit_level,
                retain_all_transiently=False,
            )
        )

    assert len(result) == 80
    assert result["value"].tolist() == [10] * 80
    assert summary.total_conflicts == 80
    assert summary.by_column == {"<row>": 80}
    assert summary.by_conflict_type == {"overlap": 80}
    assert summary.by_source_pair == {
        f"{_source_metadata('source_a').connector_id}->"
        f"{_source_metadata('source_b').connector_id}": 80
    }
    assert len(merge_log) == 1
    if audit_level == AuditLevel.FULL:
        assert summary.extra["audit_entries_retained"] == 1
        assert summary.extra["audit_entries_dropped"] == 79
    else:
        assert summary.sample_entries == merge_log
    assert max(live_counts) <= 2  # bounded collector record plus current resolver record
    assert transient_count == 0

    # Increasing the sample cap changes detail count but not complete counters.
    wide_request = _compose_request(
        CompositionStrategy.UNION,
        audit_level=AuditLevel.SUMMARY,
        key_columns=["id"],
        audit_sample_size=3,
        audit_max_entries=3,
        audit_seed="fed02-live-union-details",
    )
    wide_composer = _composer()
    _, wide_log = wide_composer.compose(
        sources=[
            (
                pd.DataFrame({"id": range(80), "value": [10] * 80}),
                _source_metadata("source_a"),
            ),
            (
                pd.DataFrame({"id": range(80), "value": [11] * 80}),
                _source_metadata("source_b", trust_level=TrustLevel.MEDIUM),
            ),
        ],
        strategy=CompositionStrategy.UNION,
        request=wide_request,
    )
    wide_summary = wide_composer.get_last_merge_summary()
    assert wide_summary is not None
    assert len(wide_log) == 3
    assert wide_summary.total_conflicts == summary.total_conflicts
    assert wide_summary.by_column == summary.by_column
    assert wide_summary.by_source_pair == summary.by_source_pair


def test_union_live_detail_census_detects_transient_retention_mutant(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The live-object oracle rejects hidden retention with capped visible output."""
    with monkeypatch.context() as scoped:
        result, merge_log, summary, live_counts, transient_count = (
            _run_union_with_live_detail_census(
                scoped,
                audit_level=AuditLevel.SUMMARY,
                retain_all_transiently=True,
            )
        )

    assert len(result) == 80
    assert len(merge_log) == 1
    assert summary.total_conflicts == 80
    assert transient_count == 80
    assert max(live_counts) == 80


def test_union_none_audit_never_passes_details_to_collector(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NONE keeps the same UNION result without creating collector detail state."""
    row_count = 80
    source_a = pd.DataFrame({"id": range(row_count), "value": [10] * row_count})
    source_b = pd.DataFrame({"id": range(row_count), "value": [11] * row_count})
    request = _compose_request(
        CompositionStrategy.UNION,
        audit_level=AuditLevel.NONE,
        key_columns=["id"],
        audit_sample_size=1,
        audit_max_entries=1,
    )

    def unexpected_detail(
        self: MergeLogCollector,
        entry: MergeLogEntry,
    ) -> None:
        del self, entry
        pytest.fail("NONE audit passed a detail entry to the bounded collector")

    monkeypatch.setattr(MergeLogCollector, "record", unexpected_detail)
    result, merge_log = _composer().compose(
        sources=[
            (source_a, _source_metadata("source_a")),
            (
                source_b,
                _source_metadata("source_b", trust_level=TrustLevel.MEDIUM),
            ),
        ],
        strategy=CompositionStrategy.UNION,
        request=request,
    )

    assert len(result) == row_count
    assert result["value"].tolist() == [10] * row_count
    assert merge_log == []


@pytest.mark.parametrize("audit_level", list(AuditLevel))
def test_overlay_two_used_secondaries_follow_priority_and_reuse_indexes(monkeypatch, audit_level):
    """Independent cell table covers two used secondary indexes and NONE work."""
    primary = pd.DataFrame(
        {"id": [1, 2], "first": [None, None], "second": [None, None], "third": [None, None]}
    )
    b = pd.DataFrame({"id": [1, 2], "first": [10.0, 11.0], "second": [20.0, None]})
    c = pd.DataFrame({"id": [1, 2], "first": [30.0, None], "third": [40.0, 41.0]})
    p_meta, b_meta, c_meta = (_source_metadata(name) for name in ["primary", "b", "c"])
    request = _compose_request(
        CompositionStrategy.OVERLAY,
        audit_level=audit_level,
        key_columns=["id"],
        primary_source=p_meta.connector_id,
        manual_priorities={b_meta.connector_id: 1, c_meta.connector_id: 2},
        audit_sample_size=3,
        audit_max_entries=10,
    )
    calls = {id(b): 0, id(c): 0}
    original_set_index = pd.DataFrame.set_index

    def observe(self, *args, **kwargs):
        if id(self) in calls:
            calls[id(self)] += 1
        return original_set_index(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "set_index", observe)
    entries_created = 0
    original_entry = MergeLogEntry

    def counted_entry(*args, **kwargs):
        nonlocal entries_created
        entries_created += 1
        return original_entry(*args, **kwargs)

    monkeypatch.setattr(
        "polisyos.fabric.connectors.federation.composer.MergeLogEntry", counted_entry
    )
    composer = _composer()
    result, log = composer.compose(
        [(primary, p_meta), (b, b_meta), (c, c_meta)], request.strategy, request
    )
    assert calls == {id(b): 1, id(c): 1}
    # Derived by explicit primary -> descending secondary priority -> first
    # non-null cell; source B still actually supplies two cells after C.
    expected = [(1, 30.0, 20.0, 40.0), (2, 11.0, None, 41.0)]
    actual = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in result[["id", "first", "second", "third"]].itertuples(False, None)
    ]
    assert actual == expected
    summary = composer.get_last_merge_summary()
    assert summary is not None
    if audit_level == AuditLevel.NONE:
        assert entries_created == 0 and log == [] and summary.total_conflicts == 0
    else:
        assert entries_created == 5 and summary.total_conflicts == 5
        assert summary.by_column == {"first": 2, "second": 1, "third": 2}
        assert summary.by_source_pair == {
            f"{p_meta.connector_id}->{b_meta.connector_id}": 2,
            f"{p_meta.connector_id}->{c_meta.connector_id}": 3,
        }
        assert len(log) == (5 if audit_level == AuditLevel.FULL else 3)
        if audit_level == AuditLevel.FULL:
            events = {
                (entry.row_key["id"], entry.column, entry.chosen_source, entry.chosen_value)
                for entry in log
            }
            assert events == {
                (1, "first", c_meta.connector_id, 30.0),
                (2, "first", b_meta.connector_id, 11.0),
                (1, "second", b_meta.connector_id, 20.0),
                (1, "third", c_meta.connector_id, 40.0),
                (2, "third", c_meta.connector_id, 41.0),
            }


@pytest.mark.parametrize("audit_level", list(AuditLevel))
def test_union_live_census_has_scoped_python_allocation_measurement(monkeypatch, audit_level):
    """Record scoped Python peak separately from detail liveness and native RSS."""
    was_tracing = tracemalloc.is_tracing()
    if not was_tracing:
        tracemalloc.start()
    try:
        tracemalloc.reset_peak()
        with monkeypatch.context() as scoped:
            result, log, summary, live_counts, transient_count = _run_union_with_live_detail_census(
                scoped, audit_level=audit_level, retain_all_transiently=False
            )
        current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        if not was_tracing:
            tracemalloc.stop()
    assert result["value"].tolist() == [10] * 80
    assert transient_count == 0 and peak_bytes >= current_bytes >= 0 and peak_bytes > 0
    if audit_level == AuditLevel.NONE:
        assert log == [] and live_counts == [] and summary.total_conflicts == 0
    else:
        assert len(log) == 1 and summary.total_conflicts == 80 and max(live_counts) <= 2
    print(
        json.dumps(
            {
                "scope": "Python allocations during actual 80-conflict UNION; not pandas/native RSS",
                "audit_level": audit_level.value,
                "current_bytes": current_bytes,
                "peak_bytes": peak_bytes,
                "existing_tracer": was_tracing,
            },
            sort_keys=True,
        )
    )


def test_real_join_summary_evicts_latest_equal_worst_priority(monkeypatch):
    """Mixed priorities preserve earliest equal-hash events at the real JOIN surface."""
    left, right, left_meta, right_meta = _federation_join_case([10, 10, 10, 10])
    priorities = [5, 5, 5, 4]
    monkeypatch.setattr(
        MergeLogCollector, "_stable_hash", lambda self, entry: priorities[entry.row_index]
    )
    request = _federation_join_request(AuditLevel.SUMMARY, sample_size=3)
    composer = _composer()
    result, log = composer.compose(
        [(left, left_meta), (right, right_meta)], CompositionStrategy.JOIN, request
    )
    assert len(result) == 4 and composer.get_last_merge_summary().total_conflicts == 4
    assert [entry.row_index for entry in log] == [3, 0, 1]
    assert _event_ids_from_distinct_join_logs(log, left) == ["event-3", "event-0", "event-1"]
    assert all(entry.source_a_occurrence and entry.source_b_occurrence for entry in log)
