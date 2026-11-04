"""Candidate planner relations preserve numerical and source roles separately."""

from __future__ import annotations

import pytest

from polisyos.core.artifacts import ArtifactRef
from polisyos.runtime.quality.acquisition_planner import AcquisitionWorldSnapshot


def _ref(digit: str, kind: str, *, selected: bool = True) -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + digit * 64,
        kind=kind,
        media_type="application/json",
        manifest_profile_sha256="sha256:" + digit * 64 if selected else None,
    )


def test_candidate_planner_relation_retains_old_world_and_exact_selected_refs() -> None:
    legacy = AcquisitionWorldSnapshot(world_ref="sha256:" + "1" * 64)
    assert not any(key.startswith("current_candidate_") for key in legacy.model_dump(mode="json"))
    basis = _ref("2", "runtime_quality.acquisition_evaluation_basis")
    action = _ref("3", "runtime_quality.acquisition_candidate_action_receipt")
    source = _ref("4", "runtime.quality.candidate_acquisition_source")
    payload = {
        "world_ref": legacy.world_ref,
        "world_model_record_ref": legacy.world_ref,
        "current_candidate_basis_ref": basis,
        "current_candidate_action_ref": action,
        "current_candidate_source_ref": source,
    }
    selected = AcquisitionWorldSnapshot.model_validate(payload)
    assert selected.world_ref == legacy.world_ref
    assert selected.current_candidate_basis_ref == basis
    assert selected.current_candidate_action_ref == action
    assert selected.current_candidate_source_ref == source
    assert selected.current_acquisition_growth_ref is None
    assert AcquisitionWorldSnapshot.model_validate(selected.model_dump(mode="json")) == selected

    for changed in (
        {"current_candidate_source_ref": None},
        {"current_candidate_source_ref": _ref("4", source.kind, selected=False)},
        {"current_candidate_action_ref": _ref("3", "runtime_quality.foreign_action")},
        {"world_ref": "sha256:" + "f" * 64},
        {"current_acquisition_basis_ref": basis},
    ):
        with pytest.raises(ValueError):
            AcquisitionWorldSnapshot.model_validate({**payload, **changed})
