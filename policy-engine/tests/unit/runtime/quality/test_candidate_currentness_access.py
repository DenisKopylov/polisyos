"""Currentness must distinguish owner denial from unavailable candidate state.

The selected CAS view and its ownership are real.  The candidate action lookup
is adapted to reach that view without asserting an established action or N5.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, cast

import pytest

from polisyos.core import artifacts
from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    CandidateAcquisitionEvaluationCurrentOwner,
)
from tests.unit.runtime.quality.test_candidate_evaluation_reentry_owner import (
    _real_reentry_refusal_case,
    _state,
)

if TYPE_CHECKING:
    from polisyos.runtime.quality.acquisition_evaluation import ResolvedAcquisitionEvaluation


@pytest.mark.asyncio
async def test_candidate_currentness_preserves_selected_owner_denial(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A selected foreign view is an access denial, not a stale-state result."""
    async with _real_reentry_refusal_case(tmp_path, monkeypatch) as case:
        bridge = case.owner.bridge
        owner = CandidateAcquisitionEvaluationCurrentOwner(
            bridge=bridge,
            closure=case.closure,
            candidate_action_ref=case.owner.candidate_action_ref,
            candidate_world_intent_ref=case.owner.candidate_world_intent_ref,
            current_basis_ref=case.owner.current_basis_ref,
            decision_ref=case.owner.decision_ref,
            prior=cast("ResolvedAcquisitionEvaluation", None),
            prepared_n5_configuration=case.owner.prepared_n5_configuration,
        )
        root = tmp_path / "selected-cas"
        selected_owner = artifacts.FileSystemCAS(root).for_tenant("owner-a", cell_id="cell-a")
        foreign_owner = artifacts.FileSystemCAS(root).for_tenant("owner-b", cell_id="cell-b")
        ref = selected_owner.put_json(
            {"selected_currentness_input": True},
            artifacts.ArtifactWriteOptions(
                kind="test.currentness.input", media_type="application/json"
            ),
            return_selected_profile=True,
        )
        assert ref.manifest_profile_sha256 is not None
        selected = [selected_owner]
        wrap_denial = [False]

        def selected_action_lookup(**_kwargs: object) -> None:
            try:
                selected[0].get_manifest(ref)
            except artifacts.ArtifactOwnershipError as exc:
                if wrap_denial[0]:
                    raise ValueError("selected action lookup refused") from exc
                raise
            raise ValueError("candidate action is not established")

        monkeypatch.setattr(bridge, "_require_selected_candidate_action", selected_action_lookup)
        before = _state(case)
        assert owner.currentness_resolver() is False

        selected[0] = foreign_owner
        with pytest.raises(artifacts.ArtifactOwnershipError):
            owner.currentness_resolver()
        wrap_denial[0] = True
        with pytest.raises(artifacts.ArtifactOwnershipError):
            owner.currentness_resolver()

        selected[0] = selected_owner
        with monkeypatch.context() as fault:

            def unavailable(_ref: object) -> None:
                raise artifacts.ArtifactReadOnlyUnavailableError("selected view unavailable")

            fault.setattr(selected_owner, "get_manifest", unavailable)
            assert owner.currentness_resolver() is False
        assert owner.currentness_resolver() is False
        assert _state(case) == before
