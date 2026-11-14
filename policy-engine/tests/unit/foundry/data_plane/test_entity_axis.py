from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from polisyos.core.artifacts import CoreJsonReadLimits
from polisyos.core.artifacts.manifest import (
    ArtifactRef,
    CanonInfo,
    InputRef,
    ProducerInfo,
    SchemaInfo,
)
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import CanonSpec, to_canonical_bytes
from polisyos.core.contracts.entity_axis import EntityAxisMemberId
from polisyos.foundry.data_plane.entity_axis import (
    ENTITY_AXIS_PRODUCER,
    ENTITY_AXIS_PRODUCER_VERSION,
    EntityAxisRefusal,
    align_entity_values,
    build_caller_declared_entity_axis,
    build_selected_source_entity_axis,
    reconcile_entity_axis,
)


def _limits() -> CoreJsonReadLimits:
    return CoreJsonReadLimits(
        max_manifest_bytes=100_000,
        max_bytes=1_000_000,
        max_depth=32,
        max_elements=10_000,
    )


def _put_view(store: FileSystemCAS, ids: list[str | int]) -> ArtifactRef:
    ref = store.put_json(
        {"entity_ids": ids},
        PutOptions(
            kind="tests.selected_source_view",
            media_type="application/json",
            producer=ProducerInfo(
                component="tests.unit.foundry.data_plane.test_entity_axis",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(
            forbid_floats=False,
            forbid_nan_inf=True,
            exclude_none=False,
        ),
        return_selected_profile=True,
    )
    assert isinstance(ref, ArtifactRef)
    return ref


def test_selected_view_axis_is_recomputed_by_a_fresh_reader(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    view_ref = _put_view(store, ["unit-b", "unit-a"])

    result = build_selected_source_entity_axis(
        store=store,
        source_view_ref=view_ref,
        namespace="survey-response",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    )

    assert [member.value for member in result.axis.members] == ["unit-a", "unit-b"]
    canonical_members = [member.model_dump(mode="json") for member in result.axis.members]
    digest_payload = json.dumps(
        canonical_members,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    assert result.axis.membership_sha256 == "sha256:" + hashlib.sha256(digest_payload).hexdigest()
    fresh_store = FileSystemCAS.open_existing_read_only(tmp_path / "cas")
    reconciled = reconcile_entity_axis(
        store=fresh_store,
        axis_ref=result.ref,
        limits=_limits(),
    )
    assert reconciled == result.axis


def test_source_axis_rejects_duplicate_and_untyped_ids(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    duplicate_ref = _put_view(store, ["same", "same"])
    with pytest.raises(EntityAxisRefusal, match="duplicate_member"):
        build_selected_source_entity_axis(
            store=store,
            source_view_ref=duplicate_ref,
            namespace="survey-response",
            member_values_pointer="/entity_ids",
            limits=_limits(),
        )

    bool_ref = _put_view(store, [1, True])
    with pytest.raises(EntityAxisRefusal, match="source_member_id_invalid"):
        build_selected_source_entity_axis(
            store=store,
            source_view_ref=bool_ref,
            namespace="survey-response",
            member_values_pointer="/entity_ids",
            limits=_limits(),
        )


def test_axis_identity_preserves_typed_ids_and_namespace(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    numeric_view = _put_view(store, [7])
    textual_view = _put_view(store, ["7"])
    numeric_axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=numeric_view,
        namespace="entities",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis
    textual_axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=textual_view,
        namespace="entities",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis
    other_namespace_axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=numeric_view,
        namespace="other-entities",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis

    assert numeric_axis.members[0] == EntityAxisMemberId(kind="integer", value=7)
    assert textual_axis.members[0] == EntityAxisMemberId(kind="string", value="7")
    assert numeric_axis.axis_sha256 != textual_axis.axis_sha256
    assert numeric_axis.axis_sha256 != other_namespace_axis.axis_sha256

    mixed_axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=_put_view(store, [7, "7"]),
        namespace="entities",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis
    assert {(member.kind, member.value) for member in mixed_axis.members} == {
        ("integer", 7),
        ("string", "7"),
    }


def test_alignment_is_permutation_invariant_and_rejects_wrong_membership(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    view_ref = _put_view(store, ["a", "b"])
    axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=view_ref,
        namespace="cohort",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis

    aligned = align_entity_values(
        axis=axis,
        member_ids=(
            EntityAxisMemberId(kind="string", value="b"),
            EntityAxisMemberId(kind="string", value="a"),
        ),
        values=np.asarray([20.0, 10.0], dtype=np.float64),
        dtype="float64",
        unit_id="count",
    )
    assert aligned.values.tolist() == [10.0, 20.0]
    same_order = align_entity_values(
        axis=axis,
        member_ids=(
            EntityAxisMemberId(kind="string", value="a"),
            EntityAxisMemberId(kind="string", value="b"),
        ),
        values=np.asarray([10.0, 20.0], dtype=np.float64),
        dtype="float64",
        unit_id="count",
    )
    assert same_order.identity.aligned_value_sha256 == aligned.identity.aligned_value_sha256
    assert same_order.identity.alignment_sha256 == aligned.identity.alignment_sha256
    assert same_order.identity.input_order_sha256 != aligned.identity.input_order_sha256

    exposed = aligned.values
    assert exposed.flags.writeable is False
    with pytest.raises(ValueError):
        exposed.setflags(write=True)
    with pytest.raises(ValueError):
        exposed[0] = 99.0
    try:
        exposed.shape = (1, 2)
    except ValueError:
        pass
    assert aligned.values.shape == (2,)
    assert aligned.values.flags.writeable is False

    with pytest.raises(EntityAxisRefusal, match="input_duplicate_member"):
        align_entity_values(
            axis=axis,
            member_ids=(
                EntityAxisMemberId(kind="string", value="a"),
                EntityAxisMemberId(kind="string", value="a"),
            ),
            values=np.asarray([10.0, 20.0], dtype=np.float64),
            dtype="float64",
            unit_id="count",
        )
    with pytest.raises(EntityAxisRefusal, match="membership_mismatch"):
        align_entity_values(
            axis=axis,
            member_ids=(
                EntityAxisMemberId(kind="string", value="a"),
                EntityAxisMemberId(kind="string", value="foreign"),
            ),
            values=np.asarray([10.0, 20.0], dtype=np.float64),
            dtype="float64",
            unit_id="count",
        )
    with pytest.raises(EntityAxisRefusal, match="input_members_invalid"):
        align_entity_values(
            axis=axis,
            member_ids=(EntityAxisMemberId(kind="string", value="a"),),
            values=np.asarray([10.0, 20.0], dtype=np.float64),
            dtype="float64",
            unit_id="count",
        )
    with pytest.raises(EntityAxisRefusal, match="value_shape_mismatch"):
        align_entity_values(
            axis=axis,
            member_ids=(
                EntityAxisMemberId(kind="string", value="a"),
                EntityAxisMemberId(kind="string", value="b"),
            ),
            values=np.asarray([10.0], dtype=np.float64),
            dtype="float64",
            unit_id="count",
        )


def test_equal_values_on_a_different_axis_have_different_alignment_identity(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    first_axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=_put_view(store, ["a", "b"]),
        namespace="cohort",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis
    second_axis = build_selected_source_entity_axis(
        store=store,
        source_view_ref=_put_view(store, ["a", "c"]),
        namespace="cohort",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis

    first = align_entity_values(
        axis=first_axis,
        member_ids=(
            EntityAxisMemberId(kind="string", value="a"),
            EntityAxisMemberId(kind="string", value="b"),
        ),
        values=np.asarray([1.0, 2.0], dtype=np.float64),
        dtype="float64",
        unit_id="count",
    )
    second = align_entity_values(
        axis=second_axis,
        member_ids=(
            EntityAxisMemberId(kind="string", value="a"),
            EntityAxisMemberId(kind="string", value="c"),
        ),
        values=np.asarray([1.0, 2.0], dtype=np.float64),
        dtype="float64",
        unit_id="count",
    )

    assert first.identity.value_sha256 == second.identity.value_sha256
    assert first.identity.axis_sha256 != second.identity.axis_sha256
    assert first.identity.aligned_value_sha256 == second.identity.aligned_value_sha256
    assert first.identity.alignment_sha256 != second.identity.alignment_sha256


def test_same_membership_from_different_source_bytes_has_different_axis_identity(
    tmp_path: Path,
) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    first = build_selected_source_entity_axis(
        store=store,
        source_view_ref=_put_view(store, ["a", "b"]),
        namespace="cohort",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis
    second_ref = store.put_json(
        {"entity_ids": ["b", "a"], "source_note": "new source view"},
        PutOptions(
            kind="tests.selected_source_view",
            media_type="application/json",
            producer=ProducerInfo(
                component="tests.unit.foundry.data_plane.test_entity_axis",
                version="1.0",
            ),
        ),
        canon_spec=CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
        return_selected_profile=True,
    )
    assert isinstance(second_ref, ArtifactRef)
    second = build_selected_source_entity_axis(
        store=store,
        source_view_ref=second_ref,
        namespace="cohort",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    ).axis

    assert first.membership_sha256 == second.membership_sha256
    assert first.axis_sha256 != second.axis_sha256


def test_axis_reconcile_rejects_removed_or_grafted_source_lineage(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    source_ref = _put_view(store, ["a", "b"])
    foreign_source_ref = _put_view(store, ["c", "d"])
    built = build_selected_source_entity_axis(
        store=store,
        source_view_ref=source_ref,
        namespace="cohort",
        member_values_pointer="/entity_ids",
        limits=_limits(),
    )
    payload_bytes = to_canonical_bytes(
        built.axis.model_dump(mode="json", exclude_none=False),
        CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False),
    )
    schema = SchemaInfo(
        name=built.axis.ARTIFACT_SCHEMA_NAME,
        version=built.axis.ARTIFACT_SCHEMA_VERSION,
    )

    def put_forged_axis(inputs: list[InputRef]) -> ArtifactRef:
        ref = store.put_bytes(
            payload_bytes,
            PutOptions(
                kind=built.axis.ARTIFACT_KIND,
                media_type=built.axis.ARTIFACT_MEDIA_TYPE,
                schema=schema,
                producer=ProducerInfo(
                    component=ENTITY_AXIS_PRODUCER,
                    version=ENTITY_AXIS_PRODUCER_VERSION,
                ),
                inputs=inputs,
                canon=CanonInfo.from_spec(
                    CanonSpec(forbid_floats=False, forbid_nan_inf=True, exclude_none=False)
                ),
            ),
            return_selected_profile=True,
        )
        assert isinstance(ref, ArtifactRef)
        return ref

    removed_ref = put_forged_axis([])
    grafted_ref = put_forged_axis(
        [
            InputRef(
                artifact_id=foreign_source_ref.artifact_id,
                role="selected_source_view",
                manifest_profile_sha256=foreign_source_ref.manifest_profile_sha256,
            )
        ]
    )

    for forged_ref in (removed_ref, grafted_ref):
        with pytest.raises(EntityAxisRefusal, match="lineage_mismatch"):
            reconcile_entity_axis(store=store, axis_ref=forged_ref, limits=_limits())


def test_caller_declared_axis_stays_not_established_after_reconcile(tmp_path: Path) -> None:
    store = FileSystemCAS(tmp_path / "cas", ownership_enforced=False)
    built = build_caller_declared_entity_axis(
        store=store,
        namespace="model-local-cohort",
        revision="rev-3",
        member_ids=(
            EntityAxisMemberId(kind="string", value="member-b"),
            EntityAxisMemberId(kind="string", value="member-a"),
        ),
        limits=_limits(),
    )

    assert built.axis.identity_basis == "caller_declared_model_axis"
    assert built.axis.membership_provenance == "consumer_asserted"
    assert built.axis.model_selection_status == "not_established"
    reconciled = reconcile_entity_axis(store=store, axis_ref=built.ref, limits=_limits())
    assert reconciled == built.axis
    assert reconciled.membership_provenance == "consumer_asserted"
    assert reconciled.model_selection_status == "not_established"
