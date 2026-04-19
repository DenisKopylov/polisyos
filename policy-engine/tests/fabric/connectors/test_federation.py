"""Tests for federation layer (Phase 2.8)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        DataComposer,
        ConflictResolver,
        FederationPlanner,
        SourceRanker,
        RankingWeights,
        build_composite_evidence_bundle,
    )
except ModuleNotFoundError:  # pragma: no cover
    pytest.skip("Optional dependencies missing for federation tests", allow_module_level=True)
from polisyos.fabric.connectors.types import DatasetDescriptor
from polisyos.ir.connectors import ConnectorMetadataSpec, TrustLevel, QualityTier
from polisyos.fabric.connectors.federation.types import SourceMetadata


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
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=timezone.utc),
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
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "secondary",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=timezone.utc),
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
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=timezone.utc),
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


def test_full_audit_is_truncated_with_summary_metadata():
    years = list(range(2000, 2020))
    source_a = pd.DataFrame({"country": ["UA"] * len(years), "year": years, "gdp": [100] * len(years)})
    source_b = pd.DataFrame({"country": ["UA"] * len(years), "year": years, "gdp": [200] * len(years)})

    meta_a = _make_source_metadata(
        "worldbank",
        TrustLevel.HIGH,
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=timezone.utc),
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
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "minecon",
        TrustLevel.MEDIUM,
        datetime(2024, 6, 1, tzinfo=timezone.utc),
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
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "b",
        TrustLevel.HIGH,
        datetime(2024, 1, 2, tzinfo=timezone.utc),
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
        datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    meta_b = _make_source_metadata(
        "b",
        TrustLevel.MEDIUM,
        datetime(2024, 1, 2, tzinfo=timezone.utc),
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
    now = datetime.now(timezone.utc)
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
    now = datetime.now(timezone.utc)
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
        date_start=datetime(2000, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2010, 1, 1, tzinfo=timezone.utc),
    )
    desc_b = DatasetDescriptor(
        dataset_id="ukraine.gdp",
        name="B",
        date_start=datetime(2011, 1, 1, tzinfo=timezone.utc),
        date_end=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )

    registry = _DummyRegistry([
        _DummyEntry(meta_a, [desc_a]),
        _DummyEntry(meta_b, [desc_b]),
    ])

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
