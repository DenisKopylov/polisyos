"""Exact pointer selection and CAS manifest preflight over controlled bytes.

These focused fixtures exercise pointer custody and manifest selection;
authority admission and generation re-entry are outside this test's scope.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts import (
    ArtifactRef,
    FileSystemCAS,
    ProducerInfo,
    PutOptions,
    SchemaInfo,
    load_core_json_artifact,
)
from polisyos.core.canon import CanonSpec
from polisyos.runtime.quality import acquisition_world_growth as growth


def _write_pointer_fixture_views(
    store: FileSystemCAS,
) -> tuple[ArtifactRef, ArtifactRef, ArtifactRef, ArtifactRef]:
    """Write two real views of one payload and two distinct action identities."""
    action, foreign_action = (
        store.put_json(
            {"test_action_identity": identity},
            PutOptions(kind=growth._CANDIDATE_ACTION_KIND, media_type="application/json"),
            return_selected_profile=True,
        )
        for identity in ("original", "foreign")
    )
    payload = {"controlled_fixture": "pointer-selection-only"}
    selected, sibling = (
        store.put_json(
            payload,
            PutOptions(
                kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
                media_type="application/json",
                schema=SchemaInfo(name=schema_name, version=version),
                producer=ProducerInfo(component="test.selected-pointer-fixture", version="1"),
            ),
            canon_spec=CanonSpec(forbid_floats=False),
            return_selected_profile=True,
        )
        for schema_name, version in (
            ("polisyos.runtime.CandidateAcquisitionWorldCheckpoint", "1.1"),
            ("test.UnrelatedPointerView", "1.0"),
        )
    )
    assert selected.artifact_id == sibling.artifact_id
    assert selected.manifest_profile_sha256
    assert sibling.manifest_profile_sha256
    assert selected.manifest_profile_sha256 != sibling.manifest_profile_sha256
    assert store.get_bytes(selected) == store.get_bytes(sibling)
    return action, foreign_action, selected, sibling


def test_selected_world_pointer_preserves_original_profile_amid_same_byte_views(
    tmp_path: Path,
) -> None:
    """Persisted action selection reopens the writer's view through a fresh CAS."""
    store = FileSystemCAS(tmp_path / "cas")
    action, _foreign_action, selected, sibling = _write_pointer_fixture_views(store)
    pointer = tmp_path / "candidate-world-checkpoint.json"
    growth.AcquisitionWorldGrowthBridge._write_candidate_world_pointer(
        pointer, candidate_action_ref=action, selected_ref=selected
    )
    persisted = json.loads(pointer.read_bytes())
    assert persisted["candidate_action_ref"] == action.model_dump(mode="json")
    assert persisted["selected_ref"] == selected.model_dump(mode="json")
    restored = growth.AcquisitionWorldGrowthBridge._read_candidate_world_pointer(
        pointer,
        candidate_action_ref=action,
        expected_kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
    )
    assert restored == selected
    assert restored.manifest_profile_sha256 != sibling.manifest_profile_sha256
    reader = FileSystemCAS.open_existing_read_only(store.root)
    assert reader.get_manifest(restored).artifact_schema == SchemaInfo(
        name="polisyos.runtime.CandidateAcquisitionWorldCheckpoint", version="1.1"
    )
    assert reader.get_manifest(sibling).artifact_schema == SchemaInfo(
        name="test.UnrelatedPointerView", version="1.0"
    )
    assert load_core_json_artifact(reader, restored) == {
        "controlled_fixture": "pointer-selection-only"
    }


def test_selected_world_pointer_refuses_wrong_identity_and_cas_refuses_wrong_profile(
    tmp_path: Path,
) -> None:
    """Pointer checks and actual manifest admission fail at their own boundaries."""
    store = FileSystemCAS(tmp_path / "cas")
    action, foreign_action, selected, sibling = _write_pointer_fixture_views(store)
    pointer = tmp_path / "candidate-world-checkpoint.json"
    read_pointer = growth.AcquisitionWorldGrowthBridge._read_candidate_world_pointer
    write_pointer = growth.AcquisitionWorldGrowthBridge._write_candidate_world_pointer
    with pytest.raises(ValueError, match="candidate_world_selected_profile_not_established"):
        read_pointer(
            pointer,
            candidate_action_ref=action,
            expected_kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
        )
    write_pointer(pointer, candidate_action_ref=action, selected_ref=selected)
    with pytest.raises(ValueError, match="candidate_world_selected_profile_mismatch"):
        read_pointer(
            pointer,
            candidate_action_ref=foreign_action,
            expected_kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
        )
    with pytest.raises(ValueError, match="candidate_world_selected_profile_mismatch"):
        read_pointer(
            pointer,
            candidate_action_ref=action,
            expected_kind=growth._CANDIDATE_WORLD_INTENT_KIND,
        )
    profileless = selected.model_copy(update={"manifest_profile_sha256": None})
    profileless_pointer = tmp_path / "profileless.json"
    with pytest.raises(ValueError, match="candidate_world_selected_profile_write_conflict"):
        write_pointer(profileless_pointer, candidate_action_ref=action, selected_ref=profileless)
    assert not profileless_pointer.exists()

    # A hostile persisted profileless ref is also refused by the reader.
    profileless_value = json.loads(pointer.read_bytes())
    profileless_value["selected_ref"].pop("manifest_profile_sha256")
    profileless_pointer.write_text(json.dumps(profileless_value), encoding="utf-8")
    with pytest.raises(ValueError, match="candidate_world_selected_profile_mismatch"):
        read_pointer(
            profileless_pointer,
            candidate_action_ref=action,
            expected_kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
        )

    # The pointer carries an exact declared selector. Its CAS consumer must
    # resolve that selector instead of replacing it with the compatible view.
    wrong_profile = selected.model_copy(
        update={"manifest_profile_sha256": sibling.manifest_profile_sha256}
    )
    wrong_pointer = tmp_path / "wrong-profile.json"
    write_pointer(wrong_pointer, candidate_action_ref=action, selected_ref=wrong_profile)
    restored_wrong = read_pointer(
        wrong_pointer,
        candidate_action_ref=action,
        expected_kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
    )
    assert restored_wrong == wrong_profile
    bridge = growth.AcquisitionWorldGrowthBridge.__new__(growth.AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store
    with pytest.raises(CanonicalProfileRefusalError) as refused:
        bridge._read(restored_wrong, growth._CANDIDATE_WORLD_CHECKPOINT_KIND)
    assert refused.value.code == "canon_profile_typed_artifact_profile_mismatch"
    assert (
        read_pointer(
            pointer,
            candidate_action_ref=action,
            expected_kind=growth._CANDIDATE_WORLD_CHECKPOINT_KIND,
        )
        == selected
    )
