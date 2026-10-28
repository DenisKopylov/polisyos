"""Independent relational and pre-allocation oracles for the federation profile."""

from __future__ import annotations

from collections import Counter
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
    persist_federation_derivation,
    read_verified_federation_derivation,
)
from polisyos.fabric.connectors.federation.types import SourceMetadata
from polisyos.ir.connectors import ConnectorMetadataSpec, QualityTier, TrustLevel


def _metadata(name):
    spec = ConnectorMetadataSpec(
        connector_id=name,
        namespace="profile_test",
        version="1.0.0",
        source_name=name,
        source_organization="candidate fixture",
        trust_level=TrustLevel.HIGH,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
    )
    return SourceMetadata(spec.fully_qualified_id, spec, datetime(2026, 1, 1, tzinfo=UTC), 0)


def _pairs(left, right, how, match_nulls):
    """Enumerate actual row occurrences with no pandas grouping/merge implementation."""
    pairs = []
    used_right = set()
    for left_position, left_key in enumerate(left):
        matches = []
        for right_position, right_key in enumerate(right):
            if (
                match_nulls or (None not in left_key and None not in right_key)
            ) and left_key == right_key:
                matches.append(right_position)
                used_right.add(right_position)
        if matches:
            pairs.extend((f"L{left_position}", f"R{position}") for position in matches)
        elif how in {"left", "outer"}:
            pairs.append((f"L{left_position}", None))
    if how == "outer":
        pairs.extend(
            (None, f"R{position}") for position in range(len(right)) if position not in used_right
        )
    return pairs


@pytest.mark.parametrize("relation", ["one_to_one", "many_to_one", "one_to_many", "many_to_many"])
@pytest.mark.parametrize("match_nulls", [False, True])
@pytest.mark.parametrize("how", ["inner", "left", "outer"])
@pytest.mark.parametrize("composite", [False, True])
def test_join_cap_matches_independent_row_occurrence_oracle(
    monkeypatch, relation, match_nulls, how, composite
):
    left = [(1, "x"), (None, "x"), (2, None)]
    right = [(1, "x"), (None, "x"), (3, None)]
    if relation in {"many_to_one", "many_to_many"}:
        left += [left[0], left[1]]
    if relation in {"one_to_many", "many_to_many"}:
        right += [right[0], right[1]]
    if not composite:
        left = [(key[0],) for key in left]
        right = [(key[0],) for key in right]
    keys = [f"key{index}" for index in range(len(left[0]))]
    left_frame = pd.DataFrame(left, columns=keys, dtype=object)
    right_frame = pd.DataFrame(right, columns=keys, dtype=object)
    left_frame["left_event"] = [f"L{position}" for position in range(len(left))]
    right_frame["right_event"] = [f"R{position}" for position in range(len(right))]
    expected = _pairs(left, right, how, match_nulls)
    request = CompositionRequest(
        dataset_pattern="profile_test.events",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=keys,
        join_how=how,
        join_validate=relation,
        join_nulls_match=match_nulls,
        join_max_rows=len(expected),
        audit_level=AuditLevel.NONE,
    )
    composer = DataComposer(ConflictResolver(request.conflict_policy))
    sources = [(left_frame, _metadata("left")), (right_frame, _metadata("right"))]
    calls = 0
    original_merge = pd.DataFrame.merge

    def observed_merge(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original_merge(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", observed_merge)
    actual, _ = composer.compose(sources, request.strategy, request)
    assert calls == 1
    actual_pairs = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in actual[["left_event", "right_event"]].itertuples(False, None)
    ]
    assert Counter(actual_pairs) == Counter(expected)
    assert len(actual) == len(expected)
    if expected:
        calls = 0
        request = replace(request, join_max_rows=len(expected) - 1)
        with pytest.raises(FederationError, match="before materialization"):
            composer.compose(sources, request.strategy, request)
        assert calls == 0
    if relation == "many_to_many":
        calls = 0
        request = replace(request, join_max_rows=None)
        with pytest.raises(FederationError, match="requires join_max_rows"):
            composer.compose(sources, request.strategy, request)
        assert calls == 0


def test_one_to_one_outer_default_profile_checks_actual_union_before_copy(monkeypatch):
    # Each input fits the 4MiB lineage bound; their disjoint result does not.
    left = pd.DataFrame({"id": range(6_000), "left": ["x"] * 6_000})
    right = pd.DataFrame({"id": range(6_000, 12_000), "right": ["y"] * 6_000})
    request = CompositionRequest(
        dataset_pattern="profile_test.events",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
        join_how="outer",
        join_validate="one_to_one",
        join_max_rows=None,
        audit_level=AuditLevel.NONE,
    )
    from polisyos.fabric.connectors.federation import profile

    # A real tighter current engineering cap distinguishes admission of each
    # input from refusal of the 12k result before the real merge allocation.
    monkeypatch.setattr(profile, "MAX_ROWS", 10_000)
    calls = 0
    original_merge = pd.DataFrame.merge

    def observed_merge(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        return original_merge(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", observed_merge)
    with pytest.raises(FederationError, match="work profile"):
        DataComposer(ConflictResolver(request.conflict_policy)).compose(
            [(left, _metadata("left")), (right, _metadata("right"))], request.strategy, request
        )
    assert calls == 0


def test_fresh_reader_checks_decoded_dimensions_before_dataframe_allocation(tmp_path, monkeypatch):
    from polisyos.fabric.connectors.federation import artifact

    request = CompositionRequest(
        dataset_pattern="profile_test.values",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
    )
    root = tmp_path / "dimensions"
    selected = persist_federation_derivation(
        root,
        DataComposer(ConflictResolver(request.conflict_policy)),
        [(pd.DataFrame({"id": [1, 2], "value": [10, 20]}), _metadata("source"))],
        request,
    )
    monkeypatch.setattr(artifact, "MAX_GRAPH_CELLS", 3)

    def forbidden_allocation(*args, **kwargs):
        pytest.fail("over-budget encoded dimensions reached DataFrame allocation")

    monkeypatch.setattr(pd, "DataFrame", forbidden_allocation)
    with pytest.raises(FederationError, match="aggregate cell-work"):
        read_verified_federation_derivation(root, selected)


def test_explicit_row_cap_refuses_before_first_lineage_or_frame_copy(monkeypatch):
    from polisyos.fabric.connectors.federation import composer as owner

    request = CompositionRequest(
        dataset_pattern="profile_test.cap",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
        join_validate="one_to_one",
        join_max_rows=1,
    )
    sources = [
        (pd.DataFrame({"id": [1, 2], "a": [10, 20]}), _metadata("a")),
        (pd.DataFrame({"id": [1, 2], "b": [30, 40]}), _metadata("b")),
    ]

    def forbidden(*args, **kwargs):
        pytest.fail("over-cap input reached initial lineage/copy")

    monkeypatch.setattr(owner, "_input_lineage", forbidden)
    monkeypatch.setattr(pd.DataFrame, "copy", forbidden)
    with pytest.raises(FederationError, match="before materialization"):
        DataComposer(ConflictResolver(request.conflict_policy)).compose(
            sources, request.strategy, request
        )


def test_duplicate_overlay_rows_refuse_before_copy_instead_of_overwriting_basis(monkeypatch):
    request = CompositionRequest(
        dataset_pattern="profile_test.duplicate",
        strategy=CompositionStrategy.OVERLAY,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        key_columns=["id"],
    )
    source = (pd.DataFrame({"id": [1, 1], "value": [10, 20]}), _metadata("a"))

    def forbidden(*args, **kwargs):
        pytest.fail("ambiguous row occurrences reached copy")

    monkeypatch.setattr(pd.DataFrame, "copy", forbidden)
    with pytest.raises(FederationError, match="duplicate keys"):
        DataComposer(ConflictResolver(request.conflict_policy)).compose(
            [source], request.strategy, request
        )


def test_encoded_rows_are_counted_before_json_materialization(tmp_path, monkeypatch):
    import hashlib
    import json

    from polisyos.fabric.connectors.federation import FederationArtifactRef, artifact

    request = CompositionRequest(
        dataset_pattern="profile_test.decode",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
    )
    root = tmp_path / "predecode"
    selected = persist_federation_derivation(
        root,
        DataComposer(ConflictResolver(request.conflict_policy)),
        [(pd.DataFrame({"id": [1], "value": [10]}), _metadata("a"))],
        request,
    )
    manifest = json.loads((root / "manifest.json").read_bytes())
    value = json.loads((root / manifest["sources"][0]["path"]).read_bytes())
    value["frame"] = {"columns": [], "dtypes": [], "rows": [[]] * 100_001}
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    name = f"source-0-{digest}.json"
    (root / name).write_bytes(payload)
    manifest["sources"][0] = {"position": 0, "sha256": digest, "path": name}
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (root / "manifest.json").write_bytes(payload)
    selected = FederationArtifactRef(hashlib.sha256(payload).hexdigest())
    original_loads = artifact.json.loads

    def observed(payload, *args, **kwargs):
        if isinstance(payload, bytes) and b'"rows":[[],[]' in payload:
            pytest.fail("over-limit encoded rows reached full JSON materialization")
        return original_loads(payload, *args, **kwargs)

    monkeypatch.setattr(artifact.json, "loads", observed)
    with pytest.raises(FederationError, match="pre-decode row"):
        read_verified_federation_derivation(root, selected)


def test_union_output_bound_covers_numeric_widening_before_concat(monkeypatch):
    left = pd.DataFrame(
        {"id": range(60), **{f"v{n}": [1] * 60 for n in range(200)}, "text": ["s" * 65_000] * 60}
    )
    right = pd.DataFrame(
        {
            "id": range(60, 120),
            **{f"v{n}": [None] * 60 for n in range(200)},
            "text": ["s" * 65_000] * 60,
        }
    )
    request = CompositionRequest(
        dataset_pattern="profile_test.widen",
        strategy=CompositionStrategy.UNION,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        key_columns=["id"],
    )

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted output dtype expansion reached concat")

    monkeypatch.setattr(pd, "concat", forbidden)
    with pytest.raises(FederationError, match="pre-allocation wire"):
        DataComposer(ConflictResolver(request.conflict_policy)).compose(
            [(left, _metadata("a")), (right, _metadata("b"))], request.strategy, request
        )


def test_aggregate_dimensions_refuse_before_any_scalar_scan(monkeypatch):
    from polisyos.fabric.connectors.federation import composer as owner

    request = CompositionRequest(
        dataset_pattern="profile_test.aggregate",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
    )
    sources = [
        (pd.DataFrame({"id": [1, 2], "value": [10, 20]}), _metadata("a")),
        (pd.DataFrame({"id": [1, 2], "value": [30, 40]}), _metadata("b")),
    ]
    monkeypatch.setattr(owner, "MAX_GRAPH_CELLS", 7)

    def forbidden(*args, **kwargs):
        pytest.fail("over-budget aggregate reached scalar/projection scan")

    monkeypatch.setattr(owner, "admit_frame", forbidden)
    with pytest.raises(FederationError, match="aggregate cell-work"):
        DataComposer(ConflictResolver(request.conflict_policy)).compose(
            sources, request.strategy, request
        )


def test_encoded_source_budget_refuses_before_projection(tmp_path, monkeypatch):
    from polisyos.fabric.connectors.federation import artifact

    request = CompositionRequest(
        dataset_pattern="profile_test.bytes",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
    )
    source = (pd.DataFrame({"id": [1], "value": ["x" * 4_000]}), _metadata("a"))
    monkeypatch.setattr(artifact, "MAX_TOTAL_BYTES", 1_000)

    def forbidden(*args, **kwargs):
        pytest.fail("unadmitted source reached full scalar projection")

    monkeypatch.setattr(artifact, "frame_projection", forbidden)
    with pytest.raises(FederationError, match="pre-allocation byte"):
        persist_federation_derivation(
            tmp_path / "bytes",
            DataComposer(ConflictResolver(request.conflict_policy)),
            [source],
            request,
        )
    assert not (tmp_path / "bytes").exists()


def test_escaped_scalar_budget_refuses_before_json_decode(tmp_path, monkeypatch):
    from polisyos.fabric.connectors.federation import artifact

    root = tmp_path / "escaped"
    root.mkdir()
    (root / "manifest.json").write_bytes(b'{"large":"' + b"\\u0061" * 65_537 + b'"}')

    def forbidden(*args, **kwargs):
        pytest.fail("over-budget escaped scalar reached JSON decode")

    monkeypatch.setattr(artifact.json, "loads", forbidden)
    with pytest.raises(FederationError, match="pre-decode scalar"):
        artifact._read_json(root, "manifest.json", artifact._Budget())


@pytest.mark.parametrize(
    ("left_value", "right_value"),
    [
        (1, 1.0),
        (True, 1),
        (False, -0.0),
        (0.0, -0.0),
        (2**53, float(2**53)),
        (2**53 + 1, float(2**53)),
        (float("inf"), float("inf")),
        (float("-inf"), float("inf")),
        ("1", 1),
        (pd.Timestamp("2026-01-01T00:00:00Z"), pd.Timestamp("2026-01-01T01:00:00+01:00")),
        (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-01-01T00:00:00Z")),
    ],
)
@pytest.mark.parametrize("how", ["inner", "left", "outer"])
@pytest.mark.parametrize("match_nulls", [False, True])
@pytest.mark.parametrize("composite", [False, True])
def test_join_equivalence_matches_independent_pairs_before_actual_allocation(
    monkeypatch, left_value, right_value, how, match_nulls, composite
):
    """One actual relation must govern estimation, merge and every later stage."""
    from polisyos.fabric.connectors.federation import composer as owner

    left_keys = [(left_value, None)] if composite else [(left_value,)]
    right_keys = [(right_value, None)] if composite else [(right_value,)]
    keys = [f"key{position}" for position in range(len(left_keys[0]))]
    expected = _pairs(left_keys, right_keys, how, match_nulls)
    left = pd.DataFrame(left_keys, columns=keys, dtype=object)
    right = pd.DataFrame(right_keys, columns=keys, dtype=object)
    left["left_event"], right["right_event"] = ["L0"], ["R0"]
    request = CompositionRequest(
        dataset_pattern="profile_test.equivalence",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=keys,
        join_how=how,
        join_validate="one_to_one",
        join_max_rows=len(expected),
        join_nulls_match=match_nulls,
        audit_level=AuditLevel.NONE,
    )
    calls = Counter()
    actual_merge = pd.DataFrame.merge
    actual_lineage = owner._input_lineage

    def merge(frame, *args, **kwargs):
        calls["merge"] += 1
        return actual_merge(frame, *args, **kwargs)

    def lineage(*args, **kwargs):
        calls["lineage"] += 1
        return actual_lineage(*args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "merge", merge)
    monkeypatch.setattr(owner, "_input_lineage", lineage)
    sources = [(left, _metadata("left")), (right, _metadata("right"))]
    result, _ = DataComposer(ConflictResolver(request.conflict_policy)).compose(
        sources, request.strategy, request
    )
    actual = [
        tuple(None if pd.isna(value) else value for value in row)
        for row in result[["left_event", "right_event"]].itertuples(False, None)
    ]
    assert Counter(actual) == Counter(expected)
    assert len(result) == len(expected)
    assert calls["merge"] == 1
    if expected:
        calls.clear()
        with pytest.raises(FederationError, match="before materialization"):
            DataComposer(ConflictResolver(request.conflict_policy)).compose(
                sources, request.strategy, replace(request, join_max_rows=len(expected) - 1)
            )
        assert calls == Counter()


@pytest.mark.parametrize("how", ["inner", "left", "outer"])
@pytest.mark.parametrize("match_nulls", [False, True])
def test_join_equivalent_duplicates_and_intermediate_relation_use_same_capacity(
    monkeypatch, how, match_nulls
):
    """Equivalent values count as duplicates and remain equivalent after a merge."""
    first = pd.DataFrame({"id": pd.Series([1, 1.0], dtype=object), "left_event": ["L0", "L1"]})
    second = pd.DataFrame({"id": pd.Series([True], dtype=object), "right_event": ["R0"]})
    third = pd.DataFrame({"id": pd.Series([1.0], dtype=object), "third_event": ["T0"]})
    request = CompositionRequest(
        dataset_pattern="profile_test.stages",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
        join_how=how,
        join_validate="many_to_one",
        join_max_rows=2,
        join_nulls_match=match_nulls,
        audit_level=AuditLevel.NONE,
    )
    sources = [
        (frame, _metadata(name)) for frame, name in [(first, "a"), (second, "b"), (third, "c")]
    ]
    result, _ = DataComposer(ConflictResolver(request.conflict_policy)).compose(
        sources, request.strategy, request
    )
    assert Counter(
        result[["left_event", "right_event", "third_event"]].itertuples(False, None)
    ) == Counter([("L0", "R0", "T0"), ("L1", "R0", "T0")])

    def forbidden(*args, **kwargs):
        pytest.fail("equivalent duplicate/cardinality overflow reached real merge")

    monkeypatch.setattr(pd.DataFrame, "merge", forbidden)
    for invalid in [
        replace(request, join_validate="one_to_one"),
        replace(request, join_max_rows=1),
    ]:
        with pytest.raises(FederationError, match="before materialization"):
            DataComposer(ConflictResolver(invalid.conflict_policy)).compose(
                sources, invalid.strategy, invalid
            )


def test_outer_join_preserves_large_key_for_third_source():
    """Unmatched integral identity survives null extension before the next merge."""
    value = 2**53 + 1
    sources = [
        (pd.DataFrame({"id": pd.Series([value], dtype=object), "a": ["A"]}), _metadata("a")),
        (pd.DataFrame({"id": pd.Series([1.0], dtype=object), "b": ["B"]}), _metadata("b")),
        (pd.DataFrame({"id": pd.Series([value], dtype=object), "c": ["C"]}), _metadata("c")),
    ]
    request = CompositionRequest(
        dataset_pattern="profile_test.intermediate",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
        join_how="outer",
        join_validate="one_to_one",
        join_max_rows=2,
        join_nulls_match=False,
        audit_level=AuditLevel.NONE,
    )
    result, _ = DataComposer(ConflictResolver(request.conflict_policy)).compose(
        sources, request.strategy, request
    )
    rows = [
        (a if pd.notna(a) else None, c if pd.notna(c) else None)
        for a, c in result[["a", "c"]].itertuples(False, None)
    ]
    assert Counter(rows) == Counter([("A", "C"), (None, None)])
    assert value in result["id"].tolist()
