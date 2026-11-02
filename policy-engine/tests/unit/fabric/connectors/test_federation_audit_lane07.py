"""Resource and indexing controls for the existing federation audit owners."""

from __future__ import annotations

import gc
import weakref
from collections import Counter
from dataclasses import replace

import pandas as pd
import pytest

from polisyos.fabric.connectors.federation import (
    AuditLevel,
    CompositionStrategy,
    ConflictCandidate,
    ConflictContext,
    ConflictPolicy,
    ConflictResolver,
    DataComposer,
    FederationError,
    persist_federation_derivation,
    read_verified_federation_derivation,
)
from polisyos.fabric.connectors.federation.composer import (
    MergeLogCollector,
    _read_persisted_lineage,
)
from polisyos.fabric.connectors.federation.types import MergeLogEntry
from tests.unit.fabric.connectors.test_federation_lane07 import (
    _as_historical_v2,
    _metadata,
    _request,
)


@pytest.mark.parametrize("audit", list(AuditLevel))
@pytest.mark.parametrize("cap", [1, 2])
def test_collector_counts_occurrences_without_retaining_all_payloads(audit, cap):
    collector = MergeLogCollector(audit, cap, cap, "fixed-stream")
    observed = []
    for index in range(80):
        entry = MergeLogEntry(
            row_key={"id": 1},
            column="value",
            source_a_id="a",
            source_b_id="b",
            source_a_value=index,
            source_b_value=index + 1,
            chosen_value=index,
            resolution_policy="trust_highest",
        )
        observed.append(weakref.ref(entry))
        collector.record(entry)
    del entry
    collector.finalize()
    gc.collect()
    assert sum(ref() is not None for ref in observed) <= cap
    if audit is AuditLevel.NONE:
        assert collector.summary.total_conflicts == 0
        assert collector.entries == collector.summary.sample_entries == []
        assert not collector._sample_heap
    else:
        assert collector.summary.total_conflicts == 80
        retained = (
            collector.entries if audit is AuditLevel.FULL else collector.summary.sample_entries
        )
        assert len(retained) == cap
        if audit is AuditLevel.FULL:
            assert collector.summary.extra["audit_entries_dropped"] == 80 - cap


@pytest.mark.parametrize("audit", [AuditLevel.SUMMARY, AuditLevel.FULL])
def test_repeated_same_event_is_not_deduplicated_and_sample_is_stable(audit):
    entry = MergeLogEntry(row_key={"id": 1}, column="value", source_a_id="a", source_b_id="b")
    snapshots = []
    for _ in range(2):
        collector = MergeLogCollector(audit, 2, 1, "fixed-stream")
        for _occurrence in range(80):
            collector.record(entry)
        collector.finalize()
        assert collector.summary.total_conflicts == 80
        if audit is AuditLevel.FULL:
            assert collector.entries == [entry]
            assert collector.summary.extra["audit_entries_dropped"] == 79
        else:
            assert collector.summary.sample_entries == [entry, entry]
        snapshots.append([item.to_dict() for item in collector.summary.sample_entries])
    assert snapshots[0] == snapshots[1]


@pytest.mark.parametrize("audit", list(AuditLevel))
@pytest.mark.parametrize("columns", [3, 8])
def test_overlay_indexes_only_primary_and_used_secondary_once(monkeypatch, audit, columns):
    names = [f"v{index}" for index in range(columns)]
    primary = pd.DataFrame({"id": [1, 2], **{name: [999.0, None] for name in names}})
    used = pd.DataFrame({"id": [1, 2], **{name: [11.0, 22.0] for name in names}})
    unused = pd.DataFrame({"id": [1, 2], **{name: [33.0, 44.0] for name in names}})
    metadata = [_metadata(name) for name in ["primary", "used", "unused"]]
    request = replace(
        _request(CompositionStrategy.OVERLAY),
        primary_source=metadata[0].connector_id,
        audit_level=audit,
    )
    calls = Counter()
    original = pd.DataFrame.set_index

    def observed(frame, *args, **kwargs):
        role = {999.0: "primary", 11.0: "used", 33.0: "unused"}[frame.iloc[0]["v0"]]
        calls[role] += 1
        return original(frame, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "set_index", observed)
    result, entries = DataComposer(ConflictResolver(request.conflict_policy)).compose(
        list(zip([primary, used, unused], metadata, strict=True)), request.strategy, request
    )
    assert calls == {"primary": 1, "used": 1}
    assert result["id"].tolist() == [1, 2]
    for name in names:
        assert result[name].tolist() == [999.0, 22.0]
    basis = _read_persisted_lineage(result)
    assert basis is not None
    for name in names:
        assert metadata[0].connector_id in basis[0][name][0].token
        assert metadata[1].connector_id in basis[1][name][0].token
    assert (not entries) if audit is AuditLevel.NONE else len(entries) > 0


@pytest.mark.parametrize("reverse", [False, True])
def test_empty_union_reconciles_nullable_value_dtypes_without_key_coercion(tmp_path, reverse):
    sources = [
        (
            pd.DataFrame({"id": pd.Series(dtype="int64"), "x": pd.Series(dtype="Float64")}),
            _metadata("a"),
        ),
        (
            pd.DataFrame(
                {
                    "id": pd.Series(dtype="int64"),
                    "x": pd.Series(dtype="float64"),
                    "y": pd.Series(dtype="Int64"),
                }
            ),
            _metadata("b"),
        ),
    ]
    if reverse:
        sources.reverse()
    request = _request(CompositionStrategy.UNION)
    root = tmp_path / "nullable"
    ref = persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    fresh = read_verified_federation_derivation(root, ref)
    assert list(fresh.data.columns) == ["id", "x", "y"]
    assert list(map(str, fresh.data.dtypes)) == ["int64", "Float64", "Int64"]
    assert fresh.data.empty


@pytest.mark.parametrize("policy", [ConflictPolicy.FIRST_AVAILABLE, ConflictPolicy.TRUST_HIGHEST])
def test_numeric_median_admission_does_not_globally_forbid_categorical_policies(policy):
    request = replace(_request(), conflict_policy=policy, strict_conflicts=True)
    candidates = [
        ConflictCandidate("value", "category", _metadata("value")),
        ConflictCandidate("missing", None, _metadata("missing")),
    ]
    result = ConflictResolver(policy).resolve_conflict(
        candidates, ConflictContext(request=request), record_log=False
    )
    assert result.chosen_candidate is candidates[0]


@pytest.mark.parametrize(
    "strategy", [CompositionStrategy.JOIN, CompositionStrategy.OVERLAY, CompositionStrategy.UNION]
)
def test_unaffected_historical_v2_strategies_remain_useful(tmp_path, strategy):
    request = _request(strategy, join_keys=["id"])
    root = tmp_path / "historical"
    sources = [(pd.DataFrame({"id": [1], "value": [12.0]}), _metadata("a"))]
    persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    assert read_verified_federation_derivation(root, _as_historical_v2(root)).data[
        "value"
    ].tolist() == [12.0]


def test_legacy_median_rule_cannot_silently_borrow_current_source_selection(tmp_path):
    request = replace(
        _request(CompositionStrategy.JOIN, join_keys=["id"]), conflict_policy=ConflictPolicy.MEDIAN
    )
    root = tmp_path / "legacy-median"
    sources = [(pd.DataFrame({"id": [1], "value": [12.0]}), _metadata("a"))]
    persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    with pytest.raises(FederationError, match="Historical.*rule.*unavailable"):
        read_verified_federation_derivation(root, _as_historical_v2(root))
