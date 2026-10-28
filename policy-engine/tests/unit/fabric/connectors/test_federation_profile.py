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
