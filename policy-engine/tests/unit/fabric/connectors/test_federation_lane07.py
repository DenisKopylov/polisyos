"""Native federation point, typed-empty and versioned-replay regressions."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction
from itertools import permutations

import pandas as pd
import pytest

from polisyos.fabric.connectors.contracts.schema import DataSchema, FieldSpec, SchemaType
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
    FederationArtifactRef,
    FederationError,
    SchemaIncompatibilityError,
    persist_federation_derivation,
    read_verified_federation_derivation,
)
from polisyos.fabric.connectors.federation.types import SourceMetadata
from polisyos.ir.connectors import ConnectorMetadataSpec, QualityTier, TrustLevel


def _metadata(name: str) -> SourceMetadata:
    spec = ConnectorMetadataSpec(
        connector_id=name,
        version="1.0.0",
        namespace="lane07",
        source_name=name,
        source_organization="controlled candidate; not an issuer",
        trust_level=TrustLevel.MEDIUM,
        quality_tier=QualityTier.UNVERIFIED,
        capabilities=0,
    )
    return SourceMetadata(spec.fully_qualified_id, spec, datetime(2026, 1, 1, tzinfo=UTC), 1)


def _request(strategy=CompositionStrategy.CONSENSUS, **kwargs) -> CompositionRequest:
    return CompositionRequest(
        dataset_pattern="lane07.values",
        strategy=strategy,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        key_columns=["id"],
        audit_level=AuditLevel.SUMMARY,
        **kwargs,
    )


def _rational_point(values: list[float], aggregation: str) -> float:
    """Round once from exact binary rationals, independently of producer reductions."""
    if aggregation == "mean":
        return float(sum(map(Fraction.from_float, values), Fraction()) / len(values))
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return float((Fraction.from_float(ordered[mid - 1]) + Fraction.from_float(ordered[mid])) / 2)


@pytest.mark.parametrize("audit", list(AuditLevel))
@pytest.mark.parametrize("aggregation", ["mean", "median"])
@pytest.mark.parametrize(
    "values",
    [
        [1e308, 1e308],
        [10.0, 14.0],
        [math.ulp(0.0), 2 * math.ulp(0.0)],
        [1e308, -1e308, 3 * math.ulp(0.0)],
    ],
)
def test_finite_consensus_point_persists_and_replays_exactly(tmp_path, audit, aggregation, values):
    request = replace(_request(aggregation_func=aggregation), audit_level=audit)
    sources = [
        (pd.DataFrame({"id": [1], "value": [value]}), _metadata(f"source{position}"))
        for position, value in enumerate(values)
    ]
    root = tmp_path / "point"
    ref = persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    fresh = read_verified_federation_derivation(root, ref)
    actual = fresh.data.at[0, "value"]
    assert math.isfinite(actual)
    assert actual.hex() == _rational_point(values, aggregation).hex()
    assert fresh.assurance == "software_derivation_candidate"
    assert fresh.merge_summary["extra"]["consensus"]["value"]["participants"] == len(values)


@pytest.mark.parametrize("bad", [float("inf"), "bad"])
def test_strict_median_validates_before_effective_singleton(bad):
    request = replace(_request(), conflict_policy=ConflictPolicy.MEDIAN, strict_conflicts=True)
    candidates = [
        ConflictCandidate("bad", bad, _metadata("bad")),
        ConflictCandidate("none", None, _metadata("none")),
    ]
    with pytest.raises(ConflictResolutionError, match="non-finite|non-numeric"):
        ConflictResolver(ConflictPolicy.MEDIAN).resolve_conflict(
            candidates, ConflictContext(request=request, column="value"), record_log=False
        )


@pytest.mark.parametrize("peer", [None, 2.0])
def test_strict_median_unrepresentable_integer_is_typed_invalid(peer):
    request = replace(_request(), conflict_policy=ConflictPolicy.MEDIAN, strict_conflicts=True)
    candidates = [
        ConflictCandidate("huge", 10**400, _metadata("huge")),
        ConflictCandidate("peer", peer, _metadata("peer")),
    ]
    with pytest.raises(ConflictResolutionError, match="non-finite|non-numeric"):
        ConflictResolver(ConflictPolicy.MEDIAN).resolve_conflict(
            candidates, ConflictContext(request=request, column="value"), record_log=False
        )


def test_non_strict_median_unrepresentable_integer_preserves_fallback():
    request = replace(_request(), conflict_policy=ConflictPolicy.MEDIAN, strict_conflicts=False)
    candidate = ConflictCandidate("huge", 10**400, _metadata("huge"))
    result = ConflictResolver(ConflictPolicy.MEDIAN).resolve_conflict(
        [candidate], ConflictContext(request=request, column="value"), record_log=False
    )
    assert result.chosen_candidate is candidate
    assert "TRUST_HIGHEST" in result.reasoning


@pytest.mark.parametrize("values", [[10.0, None], [None, None]])
def test_median_preserves_genuine_singleton_and_absence(values):
    request = replace(_request(), conflict_policy=ConflictPolicy.MEDIAN, strict_conflicts=True)
    candidates = [
        ConflictCandidate(f"s{i}", value, _metadata(f"s{i}")) for i, value in enumerate(values)
    ]
    result = ConflictResolver(ConflictPolicy.MEDIAN).resolve_conflict(
        candidates, ConflictContext(request=request, column="value"), record_log=False
    )
    assert any(result.chosen_candidate is candidate for candidate in candidates)
    assert result.chosen_candidate.value == values[0]


def test_scalar_even_median_selects_a_genuine_large_producer_for_each_permutation():
    request = replace(_request(), conflict_policy=ConflictPolicy.MEDIAN, strict_conflicts=True)
    candidates = [
        ConflictCandidate(f"s{i}", value, _metadata(f"s{i}"))
        for i, value in enumerate([2.0, 1e308, 1e308, 1e308])
    ]
    chosen = set()
    for ordered in permutations(candidates):
        result = ConflictResolver(ConflictPolicy.MEDIAN).resolve_conflict(
            list(ordered), ConflictContext(request=request, column="value"), record_log=False
        )
        assert result.chosen_candidate.value == 1e308
        assert any(result.chosen_candidate is candidate for candidate in candidates)
        chosen.add(result.chosen_candidate.source_id)
    assert len(chosen) == 1


@pytest.mark.parametrize("values", [[1.0, 3.0], [-1e308, 1e308]])
def test_scalar_median_preserves_declared_order_for_equal_nearest_distance(values):
    request = replace(_request(), conflict_policy=ConflictPolicy.MEDIAN, strict_conflicts=True)
    candidates = [
        ConflictCandidate(f"s{i}", value, _metadata(f"s{i}")) for i, value in enumerate(values)
    ]
    target = sum(map(Fraction.from_float, values), Fraction()) / 2
    assert abs(Fraction.from_float(values[0]) - target) == abs(
        Fraction.from_float(values[1]) - target
    )
    for ordered in permutations(candidates):
        result = ConflictResolver(ConflictPolicy.MEDIAN).resolve_conflict(
            list(ordered), ConflictContext(request=request, column="value"), record_log=False
        )
        # Outside the near-midpoint tolerance the existing policy is declared
        # input precedence, not a newly introduced seeded nearest-source rule.
        assert result.chosen_candidate is ordered[0]


def _empty_sources():
    return [
        (
            pd.DataFrame({"id": pd.Series(dtype="int64"), "x": pd.Series(dtype="float64")}),
            _metadata("a"),
        ),
        (
            pd.DataFrame({"id": pd.Series(dtype="int64"), "y": pd.Series(dtype="float64")}),
            _metadata("b"),
        ),
    ]


def _declared_schema(extra_type=SchemaType.INT64):
    return DataSchema(
        schema_id="lane07.values",
        version="1.0.0",
        primary_key=("id",),
        fields=(
            FieldSpec(name="id", data_type=SchemaType.INT64),
            FieldSpec(name="x", data_type=SchemaType.FLOAT64),
            FieldSpec(name="y", data_type=SchemaType.FLOAT64),
            FieldSpec(name="z", data_type=extra_type),
        ),
    )


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("explicit", [False, True])
def test_empty_union_schema_reaches_native_artifact_and_sql(tmp_path, reverse, explicit):
    import duckdb

    sources = _empty_sources()
    if reverse:
        sources.reverse()
    request = _request(CompositionStrategy.UNION, schema=_declared_schema() if explicit else None)
    root = tmp_path / "empty"
    ref = persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    fresh = read_verified_federation_derivation(root, ref)
    expected_columns = ["id", "x", "y", "z"] if explicit else ["id", "x", "y"]
    assert list(fresh.data.columns) == expected_columns
    assert fresh.data.empty
    assert fresh.source_ids_by_cell == ()
    if explicit:
        assert str(fresh.data["z"].dtype) == "Int64"
    with duckdb.connect(":memory:") as connection:
        connection.register("qualified_empty", fresh.data)
        assert connection.execute("SELECT count(*) FROM qualified_empty").fetchone() == (0,)
        assert [
            item[0] for item in connection.execute("SELECT * FROM qualified_empty").description
        ] == expected_columns


def test_empty_union_rejects_unsupported_declared_dtype_before_publication(tmp_path):
    request = _request(CompositionStrategy.UNION, schema=_declared_schema(SchemaType.DURATION))
    with pytest.raises(SchemaIncompatibilityError, match="dtype"):
        persist_federation_derivation(
            tmp_path / "bad",
            DataComposer(ConflictResolver(request.conflict_policy)),
            _empty_sources(),
            request,
        )
    assert not (tmp_path / "bad").exists()


def _as_historical_v2(root):
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["format"] = "policyos.federation.derivation/2"
    manifest.pop("composition_rule", None)
    payload = json.dumps(
        manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()
    (root / "manifest.json").write_bytes(payload)
    return FederationArtifactRef(hashlib.sha256(payload).hexdigest())


def test_new_derivation_binds_rule_and_preserves_unaffected_v2_replay(tmp_path):
    request = _request(CompositionStrategy.JOIN, join_keys=["id"])
    root = tmp_path / "legacy"
    sources = [(pd.DataFrame({"id": [1], "x": [12.0]}), _metadata("a"))]
    ref = persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    assert read_verified_federation_derivation(root, ref).data.at[0, "x"] == 12.0
    manifest = json.loads((root / "manifest.json").read_bytes())
    assert manifest["format"] == "policyos.federation.derivation/3"
    assert manifest["composition_rule"]
    assert (
        read_verified_federation_derivation(root, _as_historical_v2(root)).data.at[0, "x"] == 12.0
    )


@pytest.mark.parametrize("strategy", [CompositionStrategy.CONSENSUS, CompositionStrategy.UNION])
def test_affected_v2_rule_is_explicitly_unavailable_not_reinterpreted(tmp_path, strategy):
    request = _request(strategy, aggregation_func="mean")
    sources = (
        _empty_sources()
        if strategy is CompositionStrategy.UNION
        else [(pd.DataFrame({"id": [1], "x": [12.0]}), _metadata("a"))]
    )
    root = tmp_path / "legacy"
    persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    ref = _as_historical_v2(root)
    with pytest.raises(FederationError, match="Historical.*rule.*unavailable"):
        read_verified_federation_derivation(root, ref)


def test_cancellation_oracle_distinguishes_removed_mean_with_rule_marker_intact(
    tmp_path, monkeypatch
):
    from polisyos.fabric.connectors.federation import composer as owner

    values = [1e308, 3 * math.ulp(0.0), -1e308]
    sources = [
        (pd.DataFrame({"id": [1], "value": [value]}), _metadata(f"source{i}"))
        for i, value in enumerate(values)
    ]
    request = _request(aggregation_func="mean")
    expected = _rational_point(values, "mean")
    root = tmp_path / "good"
    ref = persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    assert read_verified_federation_derivation(root, ref).data.at[0, "value"] == expected
    with monkeypatch.context() as control:
        control.setattr(owner, "finite_binary64_mean", lambda group: float(pd.Series(group).mean()))
        removed = tmp_path / "removed"
        removed_ref = persist_federation_derivation(
            removed, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
        )
        actual = read_verified_federation_derivation(removed, removed_ref).data.at[0, "value"]
        assert actual == 0.0
        with pytest.raises(AssertionError):
            assert actual == expected
        manifest = json.loads((removed / "manifest.json").read_bytes())
        assert (
            manifest["composition_rule"]
            == json.loads((root / "manifest.json").read_bytes())["composition_rule"]
        )
