"""Producer-to-persisted-artifact-to-fresh-consumer federation tests."""

from __future__ import annotations

import hashlib
import json
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
    FederationArtifactRef,
    FederationError,
    SelectedFederationInput,
    persist_federation_derivation,
    read_verified_federation_derivation,
)
from polisyos.fabric.connectors.federation.types import SourceMetadata
from polisyos.ir.connectors import ConnectorMetadataSpec, QualityTier, TrustLevel


def _metadata(name: str, trust: TrustLevel, version: str = "1.0.0") -> SourceMetadata:
    spec = ConnectorMetadataSpec(
        connector_id=name,
        version=version,
        namespace="portable_test",
        source_name=name,
        source_organization="consumer configured; not an issuer",
        trust_level=trust,
        quality_tier=QualityTier.GOLD,
        capabilities=0,
    )
    return SourceMetadata(spec.fully_qualified_id, spec, datetime(2026, 1, 1, tzinfo=UTC), 2)


def _request() -> CompositionRequest:
    return CompositionRequest(
        dataset_pattern="portable.values",
        strategy=CompositionStrategy.JOIN,
        conflict_policy=ConflictPolicy.TRUST_HIGHEST,
        join_keys=["id"],
        join_validate="one_to_one",
        join_max_rows=2,
        audit_level=AuditLevel.SUMMARY,
    )


def test_selected_derivation_reopens_and_recomputes_exact_cell_sources(tmp_path):
    a = (
        pd.DataFrame({"id": [1, 2], "value": [10.0, None]}),
        _metadata("same", TrustLevel.HIGH, "1.0.0"),
    )
    b = (
        pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}),
        _metadata("same", TrustLevel.LOW, "2.0.0"),
    )
    c = (pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}), _metadata("c", TrustLevel.MEDIUM))
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))

    mixed_dir = tmp_path / "mixed"
    mixed_ref = persist_federation_derivation(mixed_dir, composer, [a, b], _request())
    mixed = read_verified_federation_derivation(mixed_dir, mixed_ref)
    assert mixed.data["value"].tolist() == [10.0, 20.0]
    assert mixed.source_ids_by_cell[0]["value"] != mixed.source_ids_by_cell[1]["value"]

    # Reopened bytes are a fresh first input.  The real composer must compare B-low
    # at row 2 to C-medium, rather than assigning the mixed carrier A's authority.
    result, _ = composer.compose([(mixed.data, a[1]), c], CompositionStrategy.JOIN, _request())
    assert result["value"].tolist() == [10.0, 200.0]

    # The same selected mixed basis is also valid in the second input position.
    right_result, _ = composer.compose(
        [c, (mixed.data, a[1])], CompositionStrategy.JOIN, _request()
    )
    assert right_result["value"].tolist() == [10.0, 200.0]


@pytest.mark.parametrize("mixed_first", [True, False])
def test_selected_parent_relation_survives_second_persistence_and_fresh_read(tmp_path, mixed_first):
    a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), _metadata("b", TrustLevel.LOW))
    c = (
        pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}),
        _metadata("c", TrustLevel.MEDIUM),
    )
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    first_root = tmp_path / "first"
    first_ref = persist_federation_derivation(first_root, composer, [a, b], _request())
    mixed = read_verified_federation_derivation(first_root, first_ref)

    held_parent = SelectedFederationInput(first_root, first_ref, a[1])
    mixed.data.attrs.clear()
    mixed.data.loc[1, "value"] = 999.0
    nested_sources = [held_parent, c] if mixed_first else [c, held_parent]
    nested_root = tmp_path / "nested"
    nested_ref = persist_federation_derivation(nested_root, composer, nested_sources, _request())
    reopened = read_verified_federation_derivation(
        nested_root, nested_ref, held_parents={first_ref.manifest_sha256: first_root}
    )
    assert reopened.data["value"].tolist() == [10.0, 200.0]
    assert "portable_test.a@" in reopened.source_ids_by_cell[0]["value"]
    assert "portable_test.c@" in reopened.source_ids_by_cell[1]["value"]


@pytest.mark.parametrize("attack", ["mapping", "output", "rule", "source", "erase"])
def test_selected_ref_rejects_coherent_or_partial_forgery(tmp_path, attack):
    a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), _metadata("b", TrustLevel.LOW))
    root = tmp_path / attack
    selected = persist_federation_derivation(
        root, DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)), [a, b], _request()
    )
    manifest = json.loads((root / "manifest.json").read_text())
    if attack == "mapping":
        manifest["source_ids_by_cell"][1]["value"] = manifest["source_ids_by_cell"][0]["value"]
    elif attack == "output":
        output = root / manifest["result"]["path"]
        value = json.loads(output.read_text())
        value["rows"][1][1] = {"t": "float64", "v": float(999).hex()}
        output.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
    elif attack == "rule":
        manifest["request"]["conflict_policy"] = "first_available"
    elif attack == "source":
        source = root / manifest["sources"][1]["path"]
        value = json.loads(source.read_text())
        value["frame"]["rows"][1][1] = {"t": "float64", "v": float(21).hex()}
        source.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
    else:
        manifest.pop("source_ids_by_cell")
    # An attacker may coherently rewrite every mutable digest and marker.  They
    # cannot rewrite the separately selected manifest digest.
    (root / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    with pytest.raises(FederationError, match="selected ref|content mismatch|format"):
        read_verified_federation_derivation(root, selected)


def test_exact_codec_distinguishes_float_and_submillisecond_timestamp(tmp_path):
    frame = pd.DataFrame(
        {
            "id": [1, 2],
            "value": [1.000000000001, 1.000000000002],
            "at": [
                pd.Timestamp("2026-01-01T00:00:00.000001"),
                pd.Timestamp("2026-01-01T00:00:00.000002"),
            ],
        }
    )
    source = (frame, _metadata("precise", TrustLevel.HIGH))
    request = _request()
    root = tmp_path / "precise"
    selected = persist_federation_derivation(
        root, DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)), [source], request
    )
    reopened = read_verified_federation_derivation(root, selected).data
    assert reopened["value"].iat[0].hex() != reopened["value"].iat[1].hex()
    assert reopened["at"].iat[0].value != reopened["at"].iat[1].value


def test_wrong_selected_ref_and_unsupported_scalar_are_typed_refusals(tmp_path):
    source = (pd.DataFrame({"id": [1], "value": [10.0]}), _metadata("a", TrustLevel.HIGH))
    root = tmp_path / "selected"
    selected = persist_federation_derivation(
        root, DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)), [source], _request()
    )
    with pytest.raises(FederationError, match="selected ref"):
        read_verified_federation_derivation(root, FederationArtifactRef("0" * 64))
    source = (pd.DataFrame({"id": [1], "value": ["x" * 65_537]}), source[1])
    with pytest.raises(FederationError, match="scalar"):
        persist_federation_derivation(
            tmp_path / "unsupported",
            DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)),
            [source],
            _request(),
        )


@pytest.mark.parametrize("mode", list(CompositionStrategy))
def test_every_mode_persists_reopens_and_continues_with_selected_parent(tmp_path, mode):
    """The actual producer and fresh reader preserve cells, collisions and nested lineage."""
    frame = pd.DataFrame(
        {
            "id": [1, 2],
            "value": [10.0, 20.0],
            "__source_id": [3.0, 4.0],
            "value_left": [5.0, 6.0],
            "__policyos_lineage": [7.0, 8.0],
        }
    )
    metadata = _metadata("all_modes", TrustLevel.HIGH)
    request = _request()
    request = replace(request, strategy=mode)
    request = replace(request, key_columns=["id"])
    composer = DataComposer(ConflictResolver(request.conflict_policy))
    parent_root = tmp_path / "parent"
    parent = persist_federation_derivation(parent_root, composer, [(frame, metadata)], request)
    first = read_verified_federation_derivation(parent_root, parent)
    child_root = tmp_path / "child"
    child = persist_federation_derivation(
        child_root, composer, [SelectedFederationInput(parent_root, parent, metadata)], request
    )
    fresh = read_verified_federation_derivation(
        child_root, child, held_parents={parent.manifest_sha256: parent_root}
    )
    pd.testing.assert_frame_equal(fresh.data, first.data)
    # Selected graph edge occurrences are distinct from the parent's local tokens,
    # while each cell retains the same complete leaf declarations.
    for row in range(len(frame)):
        for column in frame.columns:

            def declarations(result, row=row, column=column):
                tokens = result.source_ids_by_cell[row][column]
                tokens = [tokens] if isinstance(tokens, str) else tokens
                return [
                    result.data.attrs["policyos_federation_lineage_v1"]["source_declarations"][
                        token
                    ]
                    for token in tokens
                ]

            assert declarations(fresh) == declarations(first)
    assert set(fresh.data.columns) == set(frame.columns)
    assert all(set(row) == set(frame.columns) for row in fresh.source_ids_by_cell)
    assert fresh.assurance == "software_derivation_candidate"
    with pytest.raises(FederationError, match="not held"):
        read_verified_federation_derivation(child_root, child)


def _reselect(root, manifest):
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    (root / "manifest.json").write_bytes(payload)
    return FederationArtifactRef(hashlib.sha256(payload).hexdigest())


def _rewrite_member(root, manifest, position, value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    digest = hashlib.sha256(payload).hexdigest()
    name = f"source-{position}-{digest}.json"
    (root / name).write_bytes(payload)
    manifest["sources"][position] = {"position": position, "path": name, "sha256": digest}


@pytest.mark.parametrize("attack", ["mapping", "frame", "wrong_held_bytes", "missing_parent"])
def test_coherently_reselected_child_cannot_replace_held_parent_basis(tmp_path, attack):
    """Unlike the old-selector probe, the attacker gets a coherent NEW child selector."""
    a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), _metadata("b", TrustLevel.LOW))
    c = (pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}), _metadata("c", TrustLevel.MEDIUM))
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    parent_root = tmp_path / "parent"
    parent_ref = persist_federation_derivation(parent_root, composer, [a, b], _request())
    parent = read_verified_federation_derivation(parent_root, parent_ref)
    child_root = tmp_path / "child"
    child_ref = persist_federation_derivation(
        child_root,
        composer,
        [SelectedFederationInput(parent_root, parent_ref, a[1]), c],
        _request(),
    )
    manifest = json.loads((child_root / "manifest.json").read_bytes())
    source = json.loads((child_root / manifest["sources"][0]["path"]).read_bytes())
    assert source["parent"] == parent_ref.manifest_sha256
    held = {parent_ref.manifest_sha256: parent_root}
    if attack == "mapping":
        source["selected_lineage"] = parent.data.attrs["policyos_federation_lineage_v1"]
        source["selected_lineage"]["rows"][1]["value"] = source["selected_lineage"]["rows"][0][
            "value"
        ]
        _rewrite_member(child_root, manifest, 0, source)
    elif attack == "frame":
        # Keep the true parent digest and provide a coherent child-owned replacement frame.
        source["frame"] = {
            "columns": ["id", "value"],
            "dtypes": ["int64", "float64"],
            "rows": [
                [{"t": "int", "v": "1"}, {"t": "float64", "v": float(10).hex()}],
                [{"t": "int", "v": "2"}, {"t": "float64", "v": float(20).hex()}],
            ],
        }
        _rewrite_member(child_root, manifest, 0, source)
    elif attack == "wrong_held_bytes":
        held[parent_ref.manifest_sha256] = child_root
    else:
        held.clear()
    selected_attack = _reselect(child_root, manifest)
    assert selected_attack.manifest_sha256 != "0" * 64
    assert child_ref.manifest_sha256 != "0" * 64
    with pytest.raises(FederationError):
        read_verified_federation_derivation(child_root, selected_attack, held_parents=held)
    # Restore original source/selector and verify the independently held parent remains honest.
    assert read_verified_federation_derivation(parent_root, parent_ref).data["value"].tolist() == [
        10.0,
        20.0,
    ]


def test_direct_attrs_relabel_copy_and_changed_carrier_fail_closed(tmp_path):
    a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), _metadata("b", TrustLevel.LOW))
    c = (pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}), _metadata("c", TrustLevel.MEDIUM))
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    owned, _ = composer.compose([a, b], CompositionStrategy.JOIN, _request())
    copied = owned.copy(deep=True)
    with pytest.raises(FederationError, match="Unverified"):
        composer.compose([(copied, a[1]), c], CompositionStrategy.JOIN, _request())
    attrs = owned.attrs["policyos_federation_lineage_v1"]
    attrs["rows"][1]["value"] = attrs["rows"][0]["value"]
    with pytest.raises(FederationError, match="projection changed"):
        composer.compose([(owned, a[1]), c], CompositionStrategy.JOIN, _request())
    # Erasing a mutable projection does not erase the separate owner-held basis.
    owned.attrs.clear()
    output, _ = composer.compose([(owned, a[1]), c], CompositionStrategy.JOIN, _request())
    assert output["value"].tolist() == [10.0, 200.0]
    owned.loc[1, "value"] = 999.0
    with pytest.raises(FederationError, match="carrier changed"):
        composer.compose([(owned, a[1]), c], CompositionStrategy.JOIN, _request())


def test_content_and_occurrence_distinguish_identical_source_declarations(tmp_path):
    metadata = _metadata("same", TrustLevel.HIGH)
    a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), metadata)
    b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), metadata)
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    selected = persist_federation_derivation(tmp_path / "selected", composer, [a, b], _request())
    result = read_verified_federation_derivation(tmp_path / "selected", selected)
    assert result.source_ids_by_cell[0]["value"] != result.source_ids_by_cell[1]["value"]
    # Even duplicate identical payloads remain two selected physical occurrences.
    request = _request()
    request = replace(request, strategy=CompositionStrategy.CONSENSUS)
    request = replace(request, key_columns=["id"])
    selected = persist_federation_derivation(tmp_path / "duplicates", composer, [a, a], request)
    result = read_verified_federation_derivation(tmp_path / "duplicates", selected)
    contributors = result.source_ids_by_cell[0]["value"]
    assert isinstance(contributors, list) and len(contributors) == len(set(contributors)) == 2
    assert (
        len(
            json.loads((tmp_path / "duplicates" / "manifest.json").read_bytes())[
                "source_declarations"
            ]
        )
        == 2
    )


def test_summary_per_column_enum_replays_its_effective_runtime_type(tmp_path):
    from datetime import timedelta

    a = (pd.DataFrame({"id": [1], "value": [10.0]}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1], "value": [20.0]}), _metadata("b", TrustLevel.LOW))
    b[1].fetched_at += timedelta(days=1)
    request = _request()
    request = replace(request, column_policies={"value": ConflictPolicy.MOST_RECENT})
    selected = persist_federation_derivation(
        tmp_path / "columns",
        DataComposer(ConflictResolver(request.conflict_policy)),
        [a, b],
        request,
    )
    result = read_verified_federation_derivation(tmp_path / "columns", selected)
    assert result.data["value"].tolist() == [20.0]
    assert result.merge_summary["by_policy"] == {ConflictPolicy.MOST_RECENT.value: 1}


def test_typed_empty_union_is_durable_and_queryable(tmp_path):
    frame = pd.DataFrame({"id": pd.Series(dtype="int64"), "value": pd.Series(dtype="float64")})
    request = _request()
    request = replace(request, strategy=CompositionStrategy.UNION)
    request = replace(request, key_columns=["id"])
    root = tmp_path / "empty"
    selected = persist_federation_derivation(
        root,
        DataComposer(ConflictResolver(request.conflict_policy)),
        [(frame, _metadata("empty", TrustLevel.LOW))],
        request,
    )
    result = read_verified_federation_derivation(root, selected)
    pd.testing.assert_frame_equal(result.data.query("id > 0"), frame)
    assert result.source_ids_by_cell == ()
    manifest = json.loads((root / "manifest.json").read_bytes())
    assert len(manifest["source_declarations"]) == 1
    with pytest.raises(FederationError, match="requires"):
        persist_federation_derivation(
            tmp_path / "failed",
            DataComposer(ConflictResolver(request.conflict_policy)),
            [],
            request,
        )
    assert not (tmp_path / "failed").exists()


def test_consensus_records_exact_participants_exclusions_and_aggregate_limit(tmp_path):
    values = [10.0, 14.0, float("inf"), "malformed", None]
    sources = [
        (pd.DataFrame({"id": [1], "value": [value]}), _metadata(str(position), TrustLevel.HIGH))
        for position, value in enumerate(values)
    ]
    request = _request()
    request = replace(request, strategy=CompositionStrategy.CONSENSUS)
    request = replace(request, key_columns=["id"])
    request = replace(request, aggregation_func="mean")
    root = tmp_path / "aggregate"
    composer = DataComposer(ConflictResolver(request.conflict_policy))
    selected = persist_federation_derivation(root, composer, sources, request)
    result = read_verified_federation_derivation(root, selected)
    assert result.data["value"].tolist() == [12.0]
    assert len(result.source_ids_by_cell[0]["value"]) == 2
    stats = result.merge_summary["extra"]["consensus"]["value"]
    assert stats["participants"] == 2 and stats["excluded"] == 2
    assert stats["excluded_by_reason"] == {"non_finite": 1, "non_numeric": 1}
    assert len(json.loads((root / "manifest.json").read_bytes())["source_declarations"]) == 5
    with pytest.raises(FederationError, match="Aggregate cell"):
        composer.compose(
            [
                (result.data, sources[0][1]),
                (pd.DataFrame({"id": [1], "value": [99.0]}), sources[1][1]),
            ],
            CompositionStrategy.JOIN,
            _request(),
        )
    request = replace(request, strict_conflicts=True)
    with pytest.raises(FederationError, match="non-finite|non-numeric"):
        persist_federation_derivation(tmp_path / "strict", composer, sources, request)
    assert not (tmp_path / "strict").exists()


def test_unsupported_request_refuses_before_producer_or_publication(tmp_path, monkeypatch):
    class CustomResolver(ConflictResolver):
        pass

    request = _request()
    source = (pd.DataFrame({"id": [1], "value": [1.0]}), _metadata("a", TrustLevel.HIGH))
    composer = DataComposer(CustomResolver(request.conflict_policy))

    def forbidden(*args, **kwargs):
        pytest.fail("unsupported request reached composition")

    monkeypatch.setattr(composer, "compose", forbidden)
    with pytest.raises(FederationError, match="Custom"):
        persist_federation_derivation(tmp_path / "unsupported", composer, [source], request)
    assert not (tmp_path / "unsupported").exists()


def test_manifest_and_outer_join_limits_refuse_before_copy_or_merge(tmp_path, monkeypatch):
    # The original 100k-row, 9.9MB lineage witness now hits a conservative
    # pre-allocation relation bound before a copy, merge or manifest publication.
    frame = pd.DataFrame({"id": range(100_000), "value": range(100_000)})
    metadata = _metadata("a", TrustLevel.HIGH)
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    original_copy = pd.DataFrame.copy
    copied = 0

    def observe_copy(self, *args, **kwargs):
        nonlocal copied
        copied += 1
        return original_copy(self, *args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "copy", observe_copy)
    request = _request()
    request = replace(request, join_max_rows=None)
    with pytest.raises(FederationError, match="pre-allocation"):
        composer.compose([(frame, metadata)], CompositionStrategy.JOIN, request)
    assert copied == 0
    assert not (tmp_path / "oversized").exists()


def test_actual_manifest_cap_and_aggregate_read_budget(tmp_path, monkeypatch):
    from polisyos.fabric.connectors.federation import artifact

    source = (pd.DataFrame({"id": [1], "value": [1.0]}), _metadata("a", TrustLevel.HIGH))
    root = tmp_path / "bounded"
    selected = persist_federation_derivation(
        root, DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)), [source], _request()
    )
    assert read_verified_federation_derivation(root, selected).data["value"].tolist() == [1.0]
    manifest = json.loads((root / "manifest.json").read_bytes())
    prefix_bytes = (root / "manifest.json").stat().st_size + sum(
        (root / record["path"]).stat().st_size for record in manifest["sources"]
    )
    # Actual aggregate charge fails during the final source member read.
    monkeypatch.setattr(artifact, "MAX_TOTAL_BYTES", prefix_bytes - 1)
    with pytest.raises(FederationError, match="aggregate byte"):
        read_verified_federation_derivation(root, selected)
    # The conservative remaining result-member reservation has a separate
    # admission threshold; exact stored total is not that pre-work property.
    threshold = prefix_bytes + artifact.MAX_FILE_BYTES
    monkeypatch.setattr(artifact, "MAX_TOTAL_BYTES", threshold - 1)
    with pytest.raises(FederationError, match="reserved result"):
        read_verified_federation_derivation(root, selected)
    monkeypatch.setattr(artifact, "MAX_TOTAL_BYTES", threshold)
    assert read_verified_federation_derivation(root, selected).data["value"].tolist() == [1.0]
    monkeypatch.setattr(artifact, "MAX_FILE_BYTES", (root / "manifest.json").stat().st_size - 1)
    with pytest.raises(FederationError, match="byte profile"):
        read_verified_federation_derivation(root, selected)


def test_unknown_history_limit_is_typed_and_survives_erased_copy_and_selected_replay(tmp_path):
    a = (pd.DataFrame({"id": [1, 2], "value": [10.0, None]}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1, 2], "value": [None, 20.0]}), _metadata("b", TrustLevel.LOW))
    c = (pd.DataFrame({"id": [1, 2], "value": [100.0, 200.0]}), _metadata("c", TrustLevel.MEDIUM))
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    mixed, _ = composer.compose([a, b], CompositionStrategy.JOIN, _request())
    detached = mixed.copy()
    detached.attrs.clear()
    candidate, _ = composer.compose([(detached, a[1]), c], CompositionStrategy.JOIN, _request())
    assert candidate["value"].tolist() == [10.0, 20.0]
    basis = candidate.attrs["policyos_federation_lineage_v1"]["basis_status"]
    assert basis == {
        "selected_bytes": "consumer_asserted",
        "leaf_history": "consumer_asserted",
        "limitation": "limited_candidate_unverified_leaf_history",
    }
    root = tmp_path / "limited"
    selected = persist_federation_derivation(root, composer, [(detached, a[1]), c], _request())
    reopened = read_verified_federation_derivation(root, selected)
    assert reopened.basis_status.selected_bytes == "recomputed"
    assert reopened.basis_status.leaf_history == "consumer_asserted"
    assert reopened.basis_status.limitation == "limited_candidate_unverified_leaf_history"
    child = tmp_path / "limited-child"
    child_ref = persist_federation_derivation(
        child, composer, [SelectedFederationInput(root, selected, a[1])], _request()
    )
    continued = read_verified_federation_derivation(
        child, child_ref, held_parents={selected.manifest_sha256: root}
    )
    assert continued.basis_status.limitation == reopened.basis_status.limitation
    assert (
        json.loads((child / "manifest.json").read_bytes())["basis_status"]["leaf_history"]
        == "consumer_asserted"
    )


def test_nested_selected_parent_occurrences_cannot_alias_identical_local_leaves(tmp_path):
    source = (pd.DataFrame({"id": [1], "value": [10.0]}), _metadata("same", TrustLevel.HIGH))
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    p_request, q_request = _request(), _request()
    p_request = replace(p_request, tie_breaker_seed="P")
    q_request = replace(q_request, tie_breaker_seed="Q")
    p_root, q_root = tmp_path / "P", tmp_path / "Q"
    p_ref = persist_federation_derivation(p_root, composer, [source], p_request)
    q_ref = persist_federation_derivation(q_root, composer, [source], q_request)
    assert p_ref != q_ref
    request = _request()
    request = replace(request, strategy=CompositionStrategy.CONSENSUS, key_columns=["id"])
    root = tmp_path / "two-parents"
    selected = persist_federation_derivation(
        root,
        composer,
        [
            SelectedFederationInput(p_root, p_ref, source[1]),
            SelectedFederationInput(q_root, q_ref, source[1]),
        ],
        request,
    )
    result = read_verified_federation_derivation(
        root, selected, held_parents={p_ref.manifest_sha256: p_root, q_ref.manifest_sha256: q_root}
    )
    tokens = result.source_ids_by_cell[0]["value"]
    assert isinstance(tokens, list) and len(tokens) == len(set(tokens)) == 2
    assert len(result.data.attrs["policyos_federation_lineage_v1"]["source_declarations"]) == 2


def test_duplicate_logical_ids_have_physical_participant_exclusion_and_null_identity(tmp_path):
    metadata = _metadata("same", TrustLevel.HIGH)
    sources = [
        (pd.DataFrame({"id": [1], "value": [value]}), metadata) for value in [10.0, "bad", None]
    ]
    request = _request()
    request = replace(
        request, strategy=CompositionStrategy.CONSENSUS, key_columns=["id"], aggregation_func="mean"
    )
    root = tmp_path / "physical-summary"
    selected = persist_federation_derivation(
        root, DataComposer(ConflictResolver(request.conflict_policy)), sources, request
    )
    result = read_verified_federation_derivation(root, selected)
    assert result.data["value"].tolist() == [10.0]
    physical = result.merge_summary["extra"]["consensus"]["value"]["physical_basis"]
    participant = next(iter(physical["participants"].values()))
    exclusions = next(iter(physical["exclusions"].values()))
    absence = next(iter(physical["absence"].values()))
    assert len(participant) == 1
    assert exclusions[0]["reason"] == "non_numeric" and exclusions[0]["source_position"] == 1
    assert absence[0]["reason"] == "null" and absence[0]["source_position"] == 2
    identities = (
        participant + exclusions[0]["source_occurrences"] + absence[0]["selected_input_occurrences"]
    )
    assert len(identities) == len(set(identities)) == 3


def test_nullable_extension_scalars_and_null_masks_round_trip(tmp_path):
    frame = pd.DataFrame(
        {
            "id": pd.Series([1, 2], dtype="Int64"),
            "uint": pd.Series([3, None], dtype="UInt64"),
            "number": pd.Series([1.25, None], dtype="Float32"),
            "flag": pd.Series([True, None], dtype="boolean"),
        }
    )
    root = tmp_path / "nullable"
    selected = persist_federation_derivation(
        root,
        DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)),
        [(frame, _metadata("nullable", TrustLevel.HIGH))],
        _request(),
    )
    result = read_verified_federation_derivation(root, selected)
    pd.testing.assert_frame_equal(result.data, frame)


def test_depth_refusal_reserves_new_root_before_any_publication(tmp_path):
    composer = DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST))
    metadata = _metadata("leaf", TrustLevel.HIGH)
    request = _request()
    root = tmp_path / "depth-0"
    ref = persist_federation_derivation(
        root, composer, [(pd.DataFrame({"id": [1], "value": [10.0]}), metadata)], request
    )
    parents = {}
    for depth in range(1, 9):
        parents[ref.manifest_sha256] = root
        target = tmp_path / f"depth-{depth}"
        ref = persist_federation_derivation(
            target, composer, [SelectedFederationInput(root, ref, metadata, dict(parents))], request
        )
        root = target
    parents[ref.manifest_sha256] = root
    with pytest.raises(FederationError, match="depth"):
        persist_federation_derivation(
            tmp_path / "depth-9",
            composer,
            [SelectedFederationInput(root, ref, metadata, dict(parents))],
            request,
        )
    assert not (tmp_path / "depth-9").exists()


@pytest.mark.parametrize(
    ("field", "bad"),
    [
        ("manual_priorities", {1: 10}),
        ("column_policies", {1: ConflictPolicy.MOST_RECENT}),
        ("join_max_rows", True),
        ("join_how", "right"),
    ],
)
def test_strict_request_contract_refuses_before_compose_and_publication(
    tmp_path, monkeypatch, field, bad
):
    request = _request()
    request = replace(request, **{field: bad})
    composer = DataComposer(ConflictResolver(request.conflict_policy))

    def forbidden(*args, **kwargs):
        pytest.fail("unsupported typed request reached producer")

    monkeypatch.setattr(composer, "compose", forbidden)
    with pytest.raises(FederationError):
        persist_federation_derivation(
            tmp_path / "invalid",
            composer,
            [(pd.DataFrame({"id": [1], "value": [10.0]}), _metadata("a", TrustLevel.HIGH))],
            request,
        )
    assert not (tmp_path / "invalid").exists()


def test_failed_staged_readback_never_publishes_partial_root(tmp_path, monkeypatch):
    from polisyos.fabric.connectors.federation import artifact

    def refused(*args, **kwargs):
        raise FederationError("deliberate fresh readback refusal")

    monkeypatch.setattr(artifact, "read_verified_federation_derivation", refused)
    with pytest.raises(FederationError, match="readback refusal"):
        persist_federation_derivation(
            tmp_path / "unpublished",
            DataComposer(ConflictResolver(ConflictPolicy.TRUST_HIGHEST)),
            [(pd.DataFrame({"id": [1], "value": [10.0]}), _metadata("a", TrustLevel.HIGH))],
            _request(),
        )
    assert not (tmp_path / "unpublished").exists()


@pytest.mark.parametrize("mode", list(CompositionStrategy))
def test_generated_looking_payload_families_survive_actual_multi_input_fresh_and_nested_read(
    tmp_path, mode
):
    """Exercise the temporary-name boundary through actual multi-source operations."""
    prefixes = [
        "__policyos_source_id",
        "__policyos_lineage",
        "__policyos_right_key",
        "__policyos_right_column",
        "__policyos_join_key",
    ]
    columns = [prefix + suffix for prefix in prefixes for suffix in ["", "_0", "_1", "_2"]]
    columns += ["__source_id", "value_left", "value_right"]
    a_values = {
        column: [float(index + 10), float(index + 20)] for index, column in enumerate(columns)
    }
    b_values = {column: [value + 100 for value in values] for column, values in a_values.items()}
    a_values[columns[0]][1] = None
    a = (pd.DataFrame({"id": [1, 2], **a_values}), _metadata("a", TrustLevel.HIGH))
    b = (pd.DataFrame({"id": [1, 2], **b_values}), _metadata("b", TrustLevel.LOW))
    request = replace(
        _request(),
        strategy=mode,
        key_columns=["id"],
        aggregation_func="mean",
        primary_source=a[1].connector_id,
    )
    expected = {"id": [1, 2]}
    for column in columns:
        values = []
        for row in range(2):
            left, right = a_values[column][row], b_values[column][row]
            if mode == CompositionStrategy.CONSENSUS:
                values.append(right if left is None else (left + right) / 2)
            elif mode == CompositionStrategy.UNION:
                values.append(left)
            else:
                values.append(right if left is None else left)
        expected[column] = values
    composer = DataComposer(ConflictResolver(request.conflict_policy))
    root = tmp_path / "collision"
    selected = persist_federation_derivation(root, composer, [a, b], request)
    first = read_verified_federation_derivation(root, selected)
    order = ["id", *columns]
    pd.testing.assert_frame_equal(first.data[order], pd.DataFrame(expected)[order])
    child_root = tmp_path / "collision-child"
    child = persist_federation_derivation(
        child_root, composer, [SelectedFederationInput(root, selected, a[1])], request
    )
    fresh = read_verified_federation_derivation(
        child_root, child, held_parents={selected.manifest_sha256: root}
    )
    pd.testing.assert_frame_equal(fresh.data[order], first.data[order])
    assert set(fresh.data.columns) == set(order)


@pytest.mark.parametrize("mode", list(CompositionStrategy))
def test_independent_full_scalar_and_dtype_oracle_across_every_actual_strategy(tmp_path, mode):
    """Large keys, nullable integers/booleans and floats never share a row float buffer."""
    first, second = 9_007_199_254_740_993, 9_007_199_254_740_995
    a_frame = pd.DataFrame(
        {
            "id": pd.Series([first, second], dtype="int64"),
            "value": pd.Series([1.5, 2.5], dtype="float64"),
            "quantity": pd.Series([first + 6, None], dtype="Int64"),
            "unsigned": pd.Series([2**63 + 1, 2**63 + 3], dtype="UInt64"),
            "flag": pd.Series([True, None], dtype="boolean"),
        }
    )
    b_frame = pd.DataFrame(
        {
            "id": pd.Series([first, second], dtype="int64"),
            "value": pd.Series([3.5, 4.5], dtype="float64"),
            "quantity": pd.Series([first + 8, second + 10], dtype="Int64"),
            "unsigned": pd.Series([2**63 + 1, 2**63 + 3], dtype="UInt64"),
            "flag": pd.Series([True, False], dtype="boolean"),
        }
    )
    a_meta, b_meta = _metadata("a", TrustLevel.HIGH), _metadata("b", TrustLevel.LOW)
    request = replace(
        _request(),
        strategy=mode,
        key_columns=["id"],
        aggregation_func="mode",
        primary_source=a_meta.connector_id,
    )
    is_union = mode == CompositionStrategy.UNION
    expected = pd.DataFrame(
        {
            "id": pd.Series([first, second], dtype="int64"),
            "value": pd.Series([1.5, 2.5], dtype="float64"),
            "quantity": pd.Series([first + 6, None if is_union else second + 10], dtype="Int64"),
            "unsigned": pd.Series([2**63 + 1, 2**63 + 3], dtype="UInt64"),
            "flag": pd.Series([True, None if is_union else False], dtype="boolean"),
        }
    )
    composer = DataComposer(ConflictResolver(request.conflict_policy))
    direct, _ = composer.compose([(a_frame, a_meta), (b_frame, b_meta)], mode, request)
    order = list(expected.columns)
    pd.testing.assert_frame_equal(direct[order], expected)
    root = tmp_path / "scalar-profile"
    selected = persist_federation_derivation(
        root, composer, [(a_frame, a_meta), (b_frame, b_meta)], request
    )
    fresh = read_verified_federation_derivation(root, selected)
    pd.testing.assert_frame_equal(fresh.data[order], expected)
    child_root = tmp_path / "scalar-child"
    child = persist_federation_derivation(
        child_root, composer, [SelectedFederationInput(root, selected, a_meta)], request
    )
    continued = read_verified_federation_derivation(
        child_root, child, held_parents={selected.manifest_sha256: root}
    )
    pd.testing.assert_frame_equal(continued.data[order], expected)
    assert isinstance(continued.source_declarations, tuple)
    assert all(
        isinstance(token, str) and isinstance(declaration, str)
        for token, declaration in continued.source_declarations
    )


def test_unrepresentable_common_dtype_is_a_typed_refusal_before_publication(tmp_path):
    a = (
        pd.DataFrame({"id": [1], "value": pd.Series([9_007_199_254_740_993], dtype="int64")}),
        _metadata("a", TrustLevel.HIGH),
    )
    b = (
        pd.DataFrame({"id": [2], "value": pd.Series([None], dtype="float64")}),
        _metadata("b", TrustLevel.LOW),
    )
    request = replace(_request(), strategy=CompositionStrategy.UNION, key_columns=["id"])
    with pytest.raises(FederationError, match="represent.*exactly|lossless dtype"):
        persist_federation_derivation(
            tmp_path / "cannot-represent",
            DataComposer(ConflictResolver(request.conflict_policy)),
            [a, b],
            request,
        )
    assert not (tmp_path / "cannot-represent").exists()
