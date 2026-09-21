"""Test-first witnesses for FED-02 bounded federation composition."""

from __future__ import annotations

import sys
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
