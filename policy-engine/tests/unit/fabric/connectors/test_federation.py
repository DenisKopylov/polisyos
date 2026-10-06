"""Tests for federation layer (Phase 2.8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

try:
    from polisyos.fabric.connectors.federation import (
        AuditLevel,
        CompositionRequest,
        CompositionStrategy,
        ConflictCandidate,
        ConflictContext,
        ConflictPolicy,
        ConflictResolutionError,
        ConflictResolver,
        DataComposer,
        FederationPlanner,
        RankingWeights,
        SchemaIncompatibilityError,
        SourceRanker,
        build_composite_evidence_bundle,
    )
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("Optional dependencies missing for federation tests", allow_module_level=True)
from polisyos.fabric.connectors.federation.types import SourceMetadata
from polisyos.fabric.connectors.types import DatasetDescriptor
from polisyos.ir.connectors import ConnectorMetadataSpec, QualityTier, TrustLevel


def _make_source_metadata(
    short_id: str,
    trust_level: TrustLevel,
    fetched_at: datetime,
    *,
    last_updated: datetime | None = None,
    observed_latency_ms: float | None = None,
) -> SourceMetadata:
    metadata = ConnectorMetadataSpec(
        connector_id=short_id,
        version="1.0.0",
        namespace="test",
        source_name=f"Source {short_id}",
        source_organization="Test",
        trust_level=trust_level,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
        last_updated=last_updated,
        observed_latency_ms=observed_latency_ms,
    )
    return SourceMetadata(
        connector_id=metadata.fully_qualified_id,
        metadata=metadata,
        fetched_at=fetched_at,
        row_count=0,
    )


def test_conflict_resolver_internal_log_is_bounded():
    now = datetime(2024, 1, 1, tzinfo=UTC)
    meta_a = _make_source_metadata("source_a", TrustLevel.HIGH, now)
    meta_b = _make_source_metadata("source_b", TrustLevel.MEDIUM, now - timedelta(days=1))
    request = CompositionRequest(
        dataset_pattern="phase2.conflicts",
        strategy=CompositionStrategy.OVERLAY,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        audit_level=AuditLevel.FULL,
    )
    context = ConflictContext(request=request, column="value")
    resolver = ConflictResolver(
        policy=ConflictPolicy.TRUST_HIGHEST,
        store_logs=True,
        max_log_entries=2,
    )

    for index in range(5):
        resolver.resolve_conflict(
            [
                ConflictCandidate("source_a", index, meta_a),
                ConflictCandidate("source_b", index + 100, meta_b),
            ],
            context,
        )

    stats = resolver.get_statistics()
    assert len(resolver.get_conflict_log()) == 2
    assert stats["total_resolutions"] == 5
    assert stats["log_entries_retained"] == 2
    assert stats["log_entries_truncated"] is True
    assert stats["log_entries_dropped"] == 3


def test_union_overlap_uses_key_columns():
    source_a = pd.DataFrame(
        {
            "country": ["UA", "UA"],
            "year": [2020, 2021],
            "gdp": [100, 110],
        }
    )
    source_b = pd.DataFrame(
        {
            "country": ["UA", "UA"],
            "year": [2021, 2022],
            "gdp": [115, 120],
        }
    )

    meta_a = _make_source_metadata(
        "worldbank",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=UTC),
    )

    request = CompositionRequest(
        dataset_pattern="ukraine.gdp",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        time_dimension="year",
        key_columns=["country", "year"],
        audit_level=AuditLevel.FULL,
    )

    resolver = ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    composer = DataComposer(conflict_resolver=resolver)

    result, merge_log = composer.compose(
        sources=[(source_a, meta_a), (source_b, meta_b)],
        strategy=request.strategy,
        request=request,
    )

    assert len(result) == 3
    assert list(result["year"]) == [2020, 2021, 2022]
    year_2021 = result[result["year"] == 2021]["gdp"].iloc[0]
    assert year_2021 == 110
    assert merge_log
    assert merge_log[0].row_key == {"country": "UA", "year": 2021}


def test_overlay_aligns_on_keys():
    primary = pd.DataFrame(
        {
            "country": ["UA", "UA"],
            "year": [2021, 2020],
            "gdp": [None, 100.0],
        }
    )
    secondary = pd.DataFrame(
        {
            "country": ["UA", "UA"],
            "year": [2020, 2021],
            "gdp": [102.0, 110.0],
        }
    )

    meta_a = _make_source_metadata(
        "primary",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "secondary",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=UTC),
    )

    request = CompositionRequest(
        dataset_pattern="ukraine.gdp",
        strategy=CompositionStrategy.OVERLAY,
        conflict_policy=ConflictPolicy.FIRST_AVAILABLE,
        key_columns=["country", "year"],
        time_dimension="year",
        audit_level=AuditLevel.FULL,
    )

    resolver = ConflictResolver(policy=ConflictPolicy.FIRST_AVAILABLE)
    composer = DataComposer(conflict_resolver=resolver)

    result, _ = composer.compose(
        sources=[(primary, meta_a), (secondary, meta_b)],
        strategy=request.strategy,
        request=request,
    )

    year_2021 = result[result["year"] == 2021]["gdp"].iloc[0]
    year_2020 = result[result["year"] == 2020]["gdp"].iloc[0]
    assert year_2021 == 110.0
    assert year_2020 == 100.0


def test_join_duplicate_column_uses_resolver():
    source_a = pd.DataFrame({"country": ["UA"], "year": [2020], "gdp": [100]})
    source_b = pd.DataFrame({"country": ["UA"], "year": [2020], "gdp": [102]})

    meta_a = _make_source_metadata(
        "worldbank",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=UTC),
    )

    request = CompositionRequest(
        dataset_pattern="ukraine.gdp",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["country", "year"],
        audit_level=AuditLevel.FULL,
    )

    resolver = ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    composer = DataComposer(conflict_resolver=resolver)

    result, merge_log = composer.compose(
        sources=[(source_a, meta_a), (source_b, meta_b)],
        strategy=request.strategy,
        request=request,
    )

    assert result["gdp"].iloc[0] == 100
    assert merge_log
    assert merge_log[0].source_a_id == meta_a.connector_id
    assert merge_log[0].source_b_id == meta_b.connector_id


def test_join_preserves_cell_lineage_across_three_sources():
    source_a = pd.DataFrame({"key": [1, 2], "value": [10, None]})
    source_b = pd.DataFrame({"key": [1, 2], "value": [None, 20]})
    source_c = pd.DataFrame({"key": [1, 2], "value": [100, 200]})

    fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
    meta_a = _make_source_metadata("source_a", TrustLevel.HIGH, fetched_at)
    meta_b = _make_source_metadata("source_b", TrustLevel.LOW, fetched_at)
    meta_c = _make_source_metadata("source_c", TrustLevel.MEDIUM, fetched_at)
    request = CompositionRequest(
        dataset_pattern="test.lineage",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        audit_level=AuditLevel.FULL,
    )

    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    result, merge_log = composer.compose(
        sources=[(source_a, meta_a), (source_b, meta_b), (source_c, meta_c)],
        strategy=request.strategy,
        request=request,
    )

    assert result.set_index("key")["value"].to_dict() == {1: 10, 2: 200}
    row_two = [entry for entry in merge_log if entry.row_key == {"key": 2}]
    assert row_two
    assert row_two[-1].source_a_id == meta_b.connector_id
    assert row_two[-1].source_b_id == meta_c.connector_id


def test_join_mixed_cell_lineage_survives_saved_result_readback(tmp_path: Path):
    """Per-cell producer lineage selects values correctly through a later JOIN."""
    duckdb = pytest.importorskip("duckdb")
    now = datetime(2024, 1, 1, tzinfo=UTC)
    meta_a = _make_source_metadata("lineage_a", TrustLevel.HIGH, now)
    meta_b = _make_source_metadata("lineage_b", TrustLevel.LOW, now)
    meta_c = _make_source_metadata("lineage_c", TrustLevel.MEDIUM, now)
    sources = [
        (pd.DataFrame({"key": [1, 2], "value": [10, None]}), meta_a),
        (pd.DataFrame({"key": [1, 2], "value": [None, 20]}), meta_b),
        (pd.DataFrame({"key": [1, 2], "value": [100, 200]}), meta_c),
    ]
    request = CompositionRequest(
        dataset_pattern="test.lineage-readback",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        audit_level=AuditLevel.FULL,
    )

    results: list[pd.DataFrame] = []
    for source_order in (sources, [sources[0], sources[2], sources[1]]):
        composer = DataComposer(
            conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
        )
        result, merge_log = composer.compose(
            sources=source_order,
            strategy=request.strategy,
            request=request,
        )
        results.append(result.sort_values("key").reset_index(drop=True))
        if source_order[1][1] is meta_b:
            row_two_conflict = next(
                entry for entry in merge_log if entry.row_key == {"key": 2}
            )
            assert row_two_conflict.source_a_id == meta_b.connector_id
            assert row_two_conflict.source_b_id == meta_c.connector_id

    expected = pd.DataFrame(
        {"key": pd.Series([1, 2], dtype="int64"), "value": pd.Series([10.0, 200.0])}
    )
    pd.testing.assert_frame_equal(results[0], expected)
    pd.testing.assert_frame_equal(results[1], expected)

    database = tmp_path / "mixed-lineage.duckdb"
    with duckdb.connect(str(database)) as connection:
        connection.register("mixed_result", results[0])
        connection.execute("CREATE TABLE composed_result AS SELECT * FROM mixed_result")
    with duckdb.connect(str(database), read_only=True) as connection:
        persisted = connection.execute(
            "SELECT key, value FROM composed_result ORDER BY key"
        ).df()
        schema = connection.execute("DESCRIBE composed_result").fetchall()

    pd.testing.assert_frame_equal(persisted, expected)
    assert [(row[0], row[1]) for row in schema] == [
        ("key", "BIGINT"),
        ("value", "DOUBLE"),
    ]


def test_join_rejects_undeclared_many_to_many_before_materialization():
    left = pd.DataFrame({"key": [1, 1], "left_value": [10, 20]})
    right = pd.DataFrame({"key": [1, 1], "right_value": [100, 200]})

    fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
    meta_left = _make_source_metadata("left", TrustLevel.HIGH, fetched_at)
    meta_right = _make_source_metadata("right", TrustLevel.MEDIUM, fetched_at)
    request = CompositionRequest(
        dataset_pattern="test.cardinality",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        audit_level=AuditLevel.NONE,
    )

    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    with pytest.raises(SchemaIncompatibilityError, match="many|cardinality|multiplicity"):
        composer.compose(
            sources=[(left, meta_left), (right, meta_right)],
            strategy=request.strategy,
            request=request,
        )


def test_join_does_not_match_unknown_null_keys():
    left = pd.DataFrame({"key": [None], "left_value": [10]})
    right = pd.DataFrame({"key": [None], "right_value": [20]})

    fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
    meta_left = _make_source_metadata("left", TrustLevel.HIGH, fetched_at)
    meta_right = _make_source_metadata("right", TrustLevel.MEDIUM, fetched_at)
    request = CompositionRequest(
        dataset_pattern="test.unknown-key",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        audit_level=AuditLevel.NONE,
    )

    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    result, _ = composer.compose(
        sources=[(left, meta_left), (right, meta_right)],
        strategy=request.strategy,
        request=request,
    )

    assert result.empty


def test_join_declared_cardinality_matches_independent_relational_oracle():
    """A declared many-to-one left JOIN preserves the left grain and unknown keys."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    left = pd.DataFrame(
        {
            "observation": ["a", "b", "c", "d"],
            "key": [1, 2, None, 1],
            "amount": [10, 20, 30, 40],
        }
    )
    right = pd.DataFrame(
        {"key": [1, 3, None], "region": ["north", "west", "unknown"]}
    )
    meta_left = _make_source_metadata("grain_left", TrustLevel.HIGH, now)
    meta_right = _make_source_metadata("grain_right", TrustLevel.MEDIUM, now)
    request = CompositionRequest(
        dataset_pattern="test.join-grain",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="left",
        join_validate="many_to_one",
        join_max_rows=4,
        audit_level=AuditLevel.NONE,
    )

    result, _ = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    ).compose(
        sources=[(left, meta_left), (right, meta_right)],
        strategy=request.strategy,
        request=request,
    )

    # This nested-loop oracle does not call pandas merge or composer helpers.
    right_by_key = {1: "north", 3: "west"}
    expected = [
        (
            row.observation,
            row.key if pd.notna(row.key) else None,
            row.amount,
            right_by_key.get(row.key) if pd.notna(row.key) else None,
        )
        for row in left.itertuples(index=False)
    ]
    observed = [
        (
            row[0],
            None if pd.isna(row[1]) else row[1],
            row[2],
            None if pd.isna(row[3]) else row[3],
        )
        for row in result[["observation", "key", "amount", "region"]].itertuples(
            index=False, name=None
        )
    ]
    assert observed == expected
    assert len(result) == len(left)
    assert int(result["amount"].sum()) == int(left["amount"].sum())
    assert pd.isna(result.loc[result["observation"] == "c", "region"]).all()


def test_join_explicit_many_to_many_is_bounded_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Declared expansion succeeds within its bound and fails before merge above it."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    left = pd.DataFrame({"key": [1, 1], "amount": [10, 20]})
    right = pd.DataFrame({"key": [1, 1], "label": ["x", "y"]})
    meta_left = _make_source_metadata("m2m_left", TrustLevel.HIGH, now)
    meta_right = _make_source_metadata("m2m_right", TrustLevel.MEDIUM, now)
    request = CompositionRequest(
        dataset_pattern="test.declared-m2m",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        join_validate="many_to_many",
        join_max_rows=4,
        audit_level=AuditLevel.NONE,
    )
    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    result, _ = composer.compose(
        sources=[(left, meta_left), (right, meta_right)],
        strategy=request.strategy,
        request=request,
    )
    assert list(result[["amount", "label"]].itertuples(index=False, name=None)) == [
        (10, "x"),
        (10, "y"),
        (20, "x"),
        (20, "y"),
    ]
    assert int(result["amount"].sum()) == 60

    too_small = CompositionRequest(
        **{
            **request.__dict__,
            "join_max_rows": 3,
        }
    )
    merge_calls = 0
    original_merge = pd.DataFrame.merge

    def count_merge(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal merge_calls
        merge_calls += 1
        return original_merge(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", count_merge)
    with pytest.raises(SchemaIncompatibilityError, match="join_max_rows"):
        composer.compose(
            sources=[(left, meta_left), (right, meta_right)],
            strategy=too_small.strategy,
            request=too_small,
        )
    assert merge_calls == 0


def test_join_explicit_null_category_is_the_only_null_match_control() -> None:
    """Unknown nulls stay separate unless the request declares one shared category."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    left = pd.DataFrame({"key": [None], "left_value": [10]})
    right = pd.DataFrame({"key": [None], "right_value": [20]})
    sources = [
        (left, _make_source_metadata("null_left", TrustLevel.HIGH, now)),
        (right, _make_source_metadata("null_right", TrustLevel.MEDIUM, now)),
    ]
    base = CompositionRequest(
        dataset_pattern="test.null-category",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        join_validate="one_to_one",
        audit_level=AuditLevel.NONE,
    )
    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    unknown_result, _ = composer.compose(sources, base.strategy, base)
    explicit_category = CompositionRequest(**{**base.__dict__, "join_nulls_match": True})
    categorized_result, _ = composer.compose(
        sources, explicit_category.strategy, explicit_category
    )

    assert unknown_result.empty
    assert len(categorized_result) == 1
    assert categorized_result.loc[0, "left_value"] == 10
    assert categorized_result.loc[0, "right_value"] == 20


def test_union_preserves_user_source_id_column():
    source = pd.DataFrame(
        {"key": [1], "__source_id": ["original-label"], "value": [10]}
    )
    metadata = _make_source_metadata(
        "connector",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    request = CompositionRequest(
        dataset_pattern="test.internal-name",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        key_columns=["key"],
        audit_level=AuditLevel.NONE,
    )

    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    result, _ = composer.compose(
        sources=[(source, metadata)],
        strategy=request.strategy,
        request=request,
    )

    assert result["__source_id"].tolist() == ["original-label"]


def test_join_preserves_user_suffix_like_column_names():
    left = pd.DataFrame({"key": [1], "value": [10], "value_left": [777]})
    right = pd.DataFrame({"key": [1], "value": [20]})

    fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
    meta_left = _make_source_metadata("left", TrustLevel.HIGH, fetched_at)
    meta_right = _make_source_metadata("right", TrustLevel.MEDIUM, fetched_at)
    request = CompositionRequest(
        dataset_pattern="test.internal-suffix",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        audit_level=AuditLevel.NONE,
    )

    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    result, _ = composer.compose(
        sources=[(left, meta_left), (right, meta_right)],
        strategy=request.strategy,
        request=request,
    )

    assert result["value"].tolist() == [10]
    assert result["value_left"].tolist() == [777]


def test_join_generated_internal_name_families_remain_user_data():
    """Generated-looking fields survive a real join with their input dtypes."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    left_fields = {
        "__source_id": "left-source",
        "__policyos_source_id": "left-transport-like",
        "__policyos_lineage": "left-lineage-like",
        "__policyos_right_key": "left-right-key-like",
        "__policyos_join_key": "left-join-key-like",
        "x_left": "left-suffix",
        "x": "left-x",
    }
    right_fields = {
        "__policyos_right_lineage": "right-lineage-like",
        "__policyos_right_column": "right-column-like",
        "__policyos_join_key_1": "right-join-key-like",
        "__policyos_source_id": "right-source-like",
        "__source_id_right": "right-source-suffix",
        "x_right": "right-suffix",
        "x": "right-x",
    }
    left = pd.DataFrame({"key": pd.Series([1], dtype="int64"), **left_fields})
    right = pd.DataFrame({"key": pd.Series([1], dtype="int64"), **right_fields})
    left = left.astype(dict.fromkeys(left_fields, "string"))
    right = right.astype(dict.fromkeys(right_fields, "string"))
    request = CompositionRequest(
        dataset_pattern="test.internal-families",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        audit_level=AuditLevel.NONE,
    )

    result, _ = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    ).compose(
        [
            (left, _make_source_metadata("names_left", TrustLevel.HIGH, now)),
            (right, _make_source_metadata("names_right", TrustLevel.MEDIUM, now)),
        ],
        request.strategy,
        request,
    )

    expected = pd.DataFrame({"key": pd.Series([1], dtype="int64"), **left_fields})
    expected = expected.astype(dict.fromkeys(left_fields, "string"))
    expected["__policyos_right_lineage"] = pd.Series(["right-lineage-like"], dtype="string")
    expected["__policyos_right_column"] = pd.Series(["right-column-like"], dtype="string")
    expected["__policyos_join_key_1"] = pd.Series(["right-join-key-like"], dtype="string")
    expected["__source_id_right"] = pd.Series(["right-source-suffix"], dtype="string")
    expected["x_right"] = pd.Series(["right-suffix"], dtype="string")
    right_only_fields = [column for column in right_fields if column not in left_fields]
    expected = expected[[*left.columns, *right_only_fields]]
    pd.testing.assert_frame_equal(result, expected)


def test_generated_looking_fields_survive_all_strategies_and_sql_readback(
    tmp_path: Path,
) -> None:
    """User columns resembling transport aliases survive all composer strategies."""
    duckdb = pytest.importorskip("duckdb")
    now = datetime(2024, 1, 1, tzinfo=UTC)
    aliases = [
        "__source_id",
        "__policyos_source_id",
        "__policyos_lineage",
        "__policyos_lineage_1",
        "__policyos_right_key",
        "__policyos_right_key_1",
        "__policyos_right_column",
        "__policyos_right_column_1",
        "__policyos_right_lineage",
        "__policyos_join_key",
        "__policyos_join_key_1",
        "value_left",
        "value_right",
    ]
    source = pd.DataFrame(
        {"key": pd.Series([1], dtype="int64"), **{name: [i + 10] for i, name in enumerate(aliases)}}
    )
    metadata = _make_source_metadata("reserved_names", TrustLevel.HIGH, now)
    secondary_metadata = _make_source_metadata("reserved_names_secondary", TrustLevel.LOW, now)
    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    )

    union_request = CompositionRequest(
        dataset_pattern="test.reserved-union",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        key_columns=["key"],
        audit_level=AuditLevel.NONE,
    )
    union_result, _ = composer.compose(
        [(source, metadata)], union_request.strategy, union_request
    )

    right = source.copy()
    right[aliases] = right[aliases] + 100
    join_request = CompositionRequest(
        dataset_pattern="test.reserved-join",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["key"],
        join_how="inner",
        audit_level=AuditLevel.NONE,
    )
    join_result, _ = composer.compose(
        [(source, metadata), (right, secondary_metadata)],
        join_request.strategy,
        join_request,
    )

    overlay_request = CompositionRequest(
        dataset_pattern="test.reserved-overlay",
        strategy=CompositionStrategy.OVERLAY,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        key_columns=["key"],
        primary_source=metadata.connector_id,
        audit_level=AuditLevel.NONE,
    )
    overlay_result, _ = composer.compose(
        [(source, metadata), (right, secondary_metadata)],
        overlay_request.strategy,
        overlay_request,
    )

    consensus_request = CompositionRequest(
        dataset_pattern="test.reserved-consensus",
        strategy=CompositionStrategy.CONSENSUS,
        conflict_policy=ConflictPolicy.MEDIAN,
        key_columns=["key"],
        aggregation_func="mean",
        audit_level=AuditLevel.NONE,
    )
    consensus_result, _ = composer.compose(
        [(source, metadata), (right, secondary_metadata)],
        consensus_request.strategy,
        consensus_request,
    )
    consensus_expected = pd.DataFrame(
        {
            "key": pd.Series([1], dtype="int64"),
            **{name: pd.Series([float(i + 60)], dtype="float64") for i, name in enumerate(aliases)},
        }
    )
    consensus_expected = consensus_expected[["key", *sorted(aliases)]]

    expected_by_strategy = {
        "union": source,
        "join": source,
        "overlay": source,
        "consensus": consensus_expected,
    }
    actual_by_strategy = {
        "union": union_result,
        "join": join_result,
        "overlay": overlay_result,
        "consensus": consensus_result,
    }
    for strategy, expected in expected_by_strategy.items():
        pd.testing.assert_frame_equal(actual_by_strategy[strategy], expected)

    database = tmp_path / "reserved-columns.duckdb"
    with duckdb.connect(str(database)) as connection:
        for strategy, frame in actual_by_strategy.items():
            connection.register(f"frame_{strategy}", frame)
            connection.execute(
                f"CREATE TABLE result_{strategy} AS SELECT * FROM frame_{strategy}"
            )
    with duckdb.connect(str(database), read_only=True) as connection:
        for strategy, expected in expected_by_strategy.items():
            persisted = connection.execute(f"SELECT * FROM result_{strategy}").df()
            pd.testing.assert_frame_equal(persisted, expected)


def test_consensus_strict_rejects_non_finite_candidates():
    source_a = pd.DataFrame({"key": [1], "value": [10.0]})
    source_b = pd.DataFrame({"key": [1], "value": [float("inf")]})
    fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
    meta_a = _make_source_metadata("source_a", TrustLevel.HIGH, fetched_at)
    meta_b = _make_source_metadata("source_b", TrustLevel.MEDIUM, fetched_at)
    request = CompositionRequest(
        dataset_pattern="test.consensus-finite",
        strategy=CompositionStrategy.CONSENSUS,
        conflict_policy=ConflictPolicy.MEDIAN,
        key_columns=["key"],
        aggregation_func="median",
        strict_conflicts=True,
        audit_level=AuditLevel.NONE,
    )

    composer = DataComposer(conflict_resolver=ConflictResolver(policy=ConflictPolicy.MEDIAN))

    with pytest.raises(ConflictResolutionError, match="non-finite"):
        composer.compose(
            sources=[(source_a, meta_a), (source_b, meta_b)],
            strategy=request.strategy,
            request=request,
        )


def test_consensus_strict_rejects_invalid_numeric_candidates():
    source_a = pd.DataFrame({"key": [1], "value": [10.0]})
    source_b = pd.DataFrame({"key": [1], "value": ["bad"]})
    fetched_at = datetime(2024, 1, 1, tzinfo=UTC)
    meta_a = _make_source_metadata("source_a", TrustLevel.HIGH, fetched_at)
    meta_b = _make_source_metadata("source_b", TrustLevel.MEDIUM, fetched_at)
    request = CompositionRequest(
        dataset_pattern="test.consensus-invalid",
        strategy=CompositionStrategy.CONSENSUS,
        conflict_policy=ConflictPolicy.MEDIAN,
        key_columns=["key"],
        aggregation_func="median",
        strict_conflicts=True,
        audit_level=AuditLevel.NONE,
    )

    composer = DataComposer(conflict_resolver=ConflictResolver(policy=ConflictPolicy.MEDIAN))

    with pytest.raises(ConflictResolutionError, match="non-numeric|non-finite|invalid"):
        composer.compose(
            sources=[(source_a, meta_a), (source_b, meta_b)],
            strategy=request.strategy,
            request=request,
        )


def test_consensus_reports_exact_finite_participants_and_exclusions():
    """CONSENSUS counts only finite numeric contributors and names each exclusion."""
    now = datetime(2024, 1, 1, tzinfo=UTC)
    meta_a = _make_source_metadata("consensus_a", TrustLevel.HIGH, now)
    meta_b = _make_source_metadata("consensus_b", TrustLevel.MEDIUM, now)
    request = CompositionRequest(
        dataset_pattern="test.consensus-admissibility",
        strategy=CompositionStrategy.CONSENSUS,
        conflict_policy=ConflictPolicy.MEDIAN,
        key_columns=["key"],
        aggregation_func="mean",
        audit_level=AuditLevel.SUMMARY,
    )
    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.MEDIAN)
    )
    valid_result, _ = composer.compose(
        [
            (pd.DataFrame({"key": ["r1"], "value": [10]}), meta_a),
            (pd.DataFrame({"key": ["r1"], "value": [14]}), meta_b),
        ],
        request.strategy,
        request,
    )
    valid_summary = composer.get_last_merge_summary()
    assert valid_summary is not None
    assert valid_result.loc[0, "value"] == 12.0
    valid_stats = valid_summary.extra["consensus"]["value"]
    assert valid_stats["participants"] == 2
    assert valid_stats["excluded"] == 0
    assert valid_stats["participant_sources"] == {
        json.dumps({"key": "r1"}, sort_keys=True): [meta_a.connector_id, meta_b.connector_id]
    }

    meta_bad = _make_source_metadata("consensus_bad", TrustLevel.LOW, now)
    meta_inf = _make_source_metadata("consensus_inf", TrustLevel.LOW, now)
    meta_missing = _make_source_metadata("consensus_missing", TrustLevel.LOW, now)
    partial_result, _ = composer.compose(
        [
            (pd.DataFrame({"key": ["r1"], "value": [10]}), meta_a),
            (pd.DataFrame({"key": ["r1"], "value": ["bad"]}), meta_bad),
            (pd.DataFrame({"key": ["r1"], "value": [float("inf")]}), meta_inf),
            (pd.DataFrame({"key": ["r1"], "value": [None]}), meta_missing),
        ],
        request.strategy,
        request,
    )
    partial_summary = composer.get_last_merge_summary()
    assert partial_summary is not None
    assert partial_result.loc[0, "value"] == 10.0
    partial_stats = partial_summary.extra["consensus"]["value"]
    row_id = json.dumps({"key": "r1"}, sort_keys=True)
    assert partial_stats["participants"] == 1
    assert partial_stats["excluded"] == 2
    assert partial_stats["excluded_by_reason"] == {
        "non_numeric": 1,
        "non_finite": 1,
    }
    assert partial_stats["participant_sources"] == {row_id: [meta_a.connector_id]}
    assert partial_stats["exclusions"] == {
        row_id: [
            {"source_id": meta_bad.connector_id, "reason": "non_numeric"},
            {"source_id": meta_inf.connector_id, "reason": "non_finite"},
        ]
    }


def test_full_audit_is_truncated_with_summary_metadata():
    years = list(range(2000, 2020))
    source_a = pd.DataFrame(
        {"country": ["UA"] * len(years), "year": years, "gdp": [100] * len(years)}
    )
    source_b = pd.DataFrame(
        {"country": ["UA"] * len(years), "year": years, "gdp": [200] * len(years)}
    )

    meta_a = _make_source_metadata(
        "worldbank",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=UTC),
    )

    request = CompositionRequest(
        dataset_pattern="ukraine.gdp",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["country", "year"],
        audit_level=AuditLevel.FULL,
        audit_max_entries=5,
    )

    resolver = ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST)
    composer = DataComposer(conflict_resolver=resolver)

    _result, merge_log = composer.compose(
        sources=[(source_a, meta_a), (source_b, meta_b)],
        strategy=request.strategy,
        request=request,
    )
    summary = composer.get_last_merge_summary()

    assert summary is not None
    assert summary.total_conflicts == len(years)
    assert len(merge_log) == 5
    assert summary.extra["audit_entries_retained"] == 5
    assert summary.extra["audit_entries_truncated"] is True
    assert summary.extra["audit_entries_dropped"] == len(years) - 5


def test_data_composer_accepts_injected_tracer(monkeypatch: pytest.MonkeyPatch):
    class _Span:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return None

    class _Tracer:
        def __init__(self) -> None:
            self.names: list[str] = []

        def start_as_current_span(self, name: str, *, attributes=None):
            del attributes
            self.names.append(name)
            return _Span()

    monkeypatch.setattr(
        "polisyos.fabric.connectors.federation.composer._default_tracer",
        lambda: (_ for _ in ()).throw(
            AssertionError("global tracer lookup should not run when tracer is injected")
        ),
    )
    source_a = pd.DataFrame({"country": ["UA"], "year": [2020], "gdp": [100]})
    source_b = pd.DataFrame({"country": ["UA"], "year": [2021], "gdp": [110]})
    meta_a = _make_source_metadata(
        "worldbank",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=UTC),
    )
    request = CompositionRequest(
        dataset_pattern="ukraine.gdp",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        time_dimension="year",
        key_columns=["country", "year"],
        audit_level=AuditLevel.NONE,
    )
    tracer = _Tracer()
    composer = DataComposer(
        conflict_resolver=ConflictResolver(policy=ConflictPolicy.TRUST_HIGHEST),
        tracer=tracer,
    )

    result, merge_log = composer.compose(
        sources=[(source_a, meta_a), (source_b, meta_b)],
        strategy=request.strategy,
        request=request,
    )

    assert len(result) == 2
    assert merge_log == []
    assert tracer.names == ["fabric.federation.compose"]


def test_first_available_handles_nan():
    resolver = ConflictResolver(policy=ConflictPolicy.FIRST_AVAILABLE)

    request = CompositionRequest(
        dataset_pattern="test",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.FIRST_AVAILABLE,
        audit_level=AuditLevel.NONE,
    )

    meta_a = _make_source_metadata(
        "a",
        TrustLevel.LOW,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "b",
        TrustLevel.HIGH,
        datetime(2024, 1, 2, tzinfo=UTC),
    )

    candidates = [
        ConflictCandidate(source_id=meta_a.connector_id, value=np.nan, metadata=meta_a),
        ConflictCandidate(source_id=meta_b.connector_id, value=5, metadata=meta_b),
    ]

    context = ConflictContext(request=request, column="gdp")
    resolution = resolver.resolve_conflict(candidates, context, record_log=False)

    assert resolution.chosen_candidate.value == 5


def test_median_strict_rejects_non_finite_candidates():
    resolver = ConflictResolver(policy=ConflictPolicy.MEDIAN)
    request = CompositionRequest(
        dataset_pattern="test",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.MEDIAN,
        strict_conflicts=True,
    )
    meta_a = _make_source_metadata(
        "a",
        TrustLevel.MEDIUM,
        datetime(2024, 1, 1, tzinfo=UTC),
    )
    meta_b = _make_source_metadata(
        "b",
        TrustLevel.MEDIUM,
        datetime(2024, 1, 2, tzinfo=UTC),
    )
    candidates = [
        ConflictCandidate(source_id=meta_a.connector_id, value=1.0, metadata=meta_a),
        ConflictCandidate(
            source_id=meta_b.connector_id,
            value=float("inf"),
            metadata=meta_b,
        ),
    ]

    with pytest.raises(ConflictResolutionError, match="non-finite"):
        resolver.resolve_conflict(
            candidates,
            ConflictContext(request=request, column="value"),
            record_log=False,
        )


def test_ranker_freshness_latency():
    now = datetime.now(UTC)
    meta_fresh = ConnectorMetadataSpec(
        connector_id="fresh",
        version="1.0.0",
        namespace="test",
        source_name="Fresh",
        source_organization="Test",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
        last_updated=now,
        observed_latency_ms=50.0,
    )
    meta_stale = ConnectorMetadataSpec(
        connector_id="stale",
        version="1.0.0",
        namespace="test",
        source_name="Stale",
        source_organization="Test",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
        last_updated=now - timedelta(days=10),
        observed_latency_ms=50.0,
    )

    ranker = SourceRanker(
        weights=RankingWeights(trust=0.1, completeness=0.1, freshness=0.7, latency=0.1)
    )

    request = CompositionRequest(
        dataset_pattern="test",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        max_staleness=timedelta(days=30),
    )

    ranked = ranker.rank_sources([meta_stale, meta_fresh], request=request)
    assert ranked[0].connector_id == meta_fresh.fully_qualified_id


def test_ranker_keeps_scores_finite_with_bad_quality_inputs():
    now = datetime.now(UTC)
    metadata = ConnectorMetadataSpec(
        connector_id="bad_quality",
        version="1.0.0",
        namespace="test",
        source_name="Bad Quality",
        source_organization="Test",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
        last_updated=now,
        observed_latency_ms=50.0,
    ).model_copy(
        update={"observed_latency_ms": float("nan")},
    )
    ranker = SourceRanker()
    request = CompositionRequest(
        dataset_pattern="test",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
    )

    ranked = ranker.rank_sources([metadata], request=request)

    assert 0.0 <= ranked[0].relevance_score <= 1.0
    assert 0.0 <= ranked[0].score_components["latency"] <= 1.0


class _DummyEntry:
    def __init__(self, metadata: ConnectorMetadataSpec, descriptors: list[DatasetDescriptor]):
        self.metadata = metadata
        self.dataset_descriptors = tuple(descriptors)


class _DummyRegistry:
    def __init__(self, entries: list[_DummyEntry]):
        self._entries = {entry.metadata.fully_qualified_id: entry for entry in entries}

    def find_connectors_for_dataset(self, dataset_pattern: str, preferences=None):
        return [(entry.metadata, 0.0) for entry in self._entries.values()]

    def get_entry(self, connector_id: str):
        return self._entries[connector_id]


def test_planner_union_complementary():
    meta_a = ConnectorMetadataSpec(
        connector_id="a",
        version="1.0.0",
        namespace="test",
        source_name="A",
        source_organization="Test",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
    )
    meta_b = ConnectorMetadataSpec(
        connector_id="b",
        version="1.0.0",
        namespace="test",
        source_name="B",
        source_organization="Test",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.SILVER,
        capabilities=0,
    )

    desc_a = DatasetDescriptor(
        dataset_id="ukraine.gdp",
        name="A",
        date_start=datetime(2000, 1, 1, tzinfo=UTC),
        date_end=datetime(2010, 1, 1, tzinfo=UTC),
    )
    desc_b = DatasetDescriptor(
        dataset_id="ukraine.gdp",
        name="B",
        date_start=datetime(2011, 1, 1, tzinfo=UTC),
        date_end=datetime(2020, 1, 1, tzinfo=UTC),
    )

    registry = _DummyRegistry(
        [
            _DummyEntry(meta_a, [desc_a]),
            _DummyEntry(meta_b, [desc_b]),
        ]
    )

    planner = FederationPlanner(registry=registry, ranker=SourceRanker())

    request = CompositionRequest(
        dataset_pattern="ukraine.gdp",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
    )

    plan = planner.plan(request)
    ids = {source.connector_id for source in plan.primary_sources}
    assert meta_a.fully_qualified_id in ids
    assert meta_b.fully_qualified_id in ids


def test_composite_evidence_deterministic(tmp_path: Path):
    try:
        from polisyos.core.artifacts.store import FileSystemCAS
        from polisyos.core.contracts.fabric import EvidenceBundle
    except ModuleNotFoundError:  # pragma: no cover
        pytest.skip("OpenTelemetry dependency missing for evidence store")

    bundle_a = EvidenceBundle(sources=[], transforms=[])
    bundle_b = EvidenceBundle(sources=[], transforms=[])

    store = FileSystemCAS(tmp_path)

    composite_1 = build_composite_evidence_bundle(
        source_bundles=[bundle_a, bundle_b],
        composition_strategy=CompositionStrategy.UNION,
        merge_log=[],
        store=store,
        deterministic=True,
    )

    composite_2 = build_composite_evidence_bundle(
        source_bundles=[bundle_a, bundle_b],
        composition_strategy=CompositionStrategy.UNION,
        merge_log=[],
        store=store,
        deterministic=True,
    )

    assert composite_1.provenance_ref is not None
    assert composite_2.provenance_ref is not None
    assert composite_1.provenance_ref.stable_id == composite_2.provenance_ref.stable_id
