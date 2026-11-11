"""Retained continuation controls cannot select an earlier generation's blob."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.core import artifacts
from tests._helpers.candidate_experiment_served_execution import (
    _require_distinct_new_candidate_result,
)


def test_new_result_control_protects_prior_blob_even_under_a_different_profile(
    tmp_path: Path,
) -> None:
    prior_path = tmp_path / "prior.blob"
    current_path = tmp_path / "current.blob"
    prior_bytes, current_bytes = b"retained numerical result", b"new numerical result"
    prior_path.write_bytes(prior_bytes)
    current_path.write_bytes(current_bytes)

    def reference(payload: bytes, profile_digit: str) -> artifacts.ArtifactRef:
        return artifacts.ArtifactRef(
            artifact_id=artifacts.ArtifactID.model_validate(
                "sha256:" + hashlib.sha256(payload).hexdigest()
            ),
            kind="runtime.joint_simulation_horizon_result",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + profile_digit * 64,
        )

    prior, current = reference(prior_bytes, "1"), reference(current_bytes, "2")
    _require_distinct_new_candidate_result(
        terminal_outcome="candidate_reentry_completed",
        reentry_result_ref=current,
        current_result_ref=current,
        prior_result_refs=(prior,),
    )
    foreign_profile_alias = reference(prior_bytes, "3")
    controls = (
        ("candidate_blocked", current, current),
        ("candidate_reentry_completed", None, current),
        ("candidate_reentry_completed", current, None),
        ("candidate_reentry_completed", current, reference(current_bytes, "4")),
        ("candidate_reentry_completed", prior, prior),
        ("candidate_reentry_completed", foreign_profile_alias, foreign_profile_alias),
    )
    mutation_calls = []

    def attempt_control(
        outcome: str,
        reentry_ref: artifacts.ArtifactRef | None,
        visible_ref: artifacts.ArtifactRef | None,
    ) -> None:
        _require_distinct_new_candidate_result(
            terminal_outcome=outcome,
            reentry_result_ref=reentry_ref,
            current_result_ref=visible_ref,
            prior_result_refs=(prior,),
        )
        mutation_calls.append(visible_ref)

    for outcome, reentry_ref, visible_ref in controls:
        with pytest.raises(AssertionError):
            attempt_control(outcome, reentry_ref, visible_ref)
        assert prior_path.read_bytes() == prior_bytes
        assert current_path.read_bytes() == current_bytes
    assert mutation_calls == []
