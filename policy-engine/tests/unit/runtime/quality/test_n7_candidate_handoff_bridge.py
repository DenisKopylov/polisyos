"""N7 handoff bridge behavior against the controlled served-job owner path."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.asyncio
async def test_initial_served_handoff_is_owner_resolved_before_n7_context_ref_use(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Initial N4 handoff resolution retains only its exact owner-read CAS ref.

    This exercises the served setup boundary only. The N7 transition property is
    covered separately by the acquired-world re-entry test.
    """

    from polisyos.runtime.quality.generation_cycle import (
        GenerationCycleController,
        GenerationCycleError,
    )
    from tests.unit.runtime.http import test_control_service_di as served_fixture

    observed_controllers: list[GenerationCycleController] = []
    original = GenerationCycleController._ensure_selected_candidate_source_profile

    def record_resolution(
        self: GenerationCycleController,
        problem: object,
        *,
        previous_problem: object | None = None,
    ) -> None:
        result = original(self, problem, previous_problem=previous_problem)
        if self._candidate_simulation_handoff is not None:
            observed_controllers.append(self)
        return result

    monkeypatch.setattr(
        GenerationCycleController,
        "_ensure_selected_candidate_source_profile",
        record_resolution,
    )
    fixture = await served_fixture._run_controlled_simulate_only_job_fixture(
        monkeypatch,
        tmp_path,
    )
    try:
        assert observed_controllers
        controller = observed_controllers[0]
        handoff = controller._candidate_simulation_handoff
        assert handoff is not None
        assert controller._candidate_cycle_context_job_ref == handoff.context_job_ref
        assert (
            controller._candidate_cycle_context_artifact_owner._store is controller._artifact_store
        )
        assert controller._candidate_cycle_verified_nl_job_scope._was_issued_by_verified_nl_execution_owner
        assert (
            controller._candidate_simulation_context_admission_owner
            is fixture.service._cycle_substrate_context_admission_owner
        )

        # Present-but-foreign job identity cannot fall through to a fresh profile
        # build or reuse the existing context marker.
        foreign_handoff = handoff.model_copy(update={"job_id": "foreign-job"})
        controller._candidate_simulation_handoff = foreign_handoff
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_scope_mismatch",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_handoff = handoff

        # A stale or unestablished lease is refused even when the handoff and
        # owner are still present.
        currentness = controller._candidate_simulation_currentness_resolver
        controller._candidate_simulation_currentness_resolver = lambda: False
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_currentness_not_established",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_currentness_resolver = currentness

        # A malformed supplied value is a refusal, not an absent handoff that
        # permits profile fallback.
        controller._candidate_simulation_handoff = {"job_id": handoff.job_id}
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_untyped",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_handoff = handoff

        # Remove the owner readback property while leaving the typed handoff and
        # claimed currentness callable present. Neither marker can admit a ref.
        from types import SimpleNamespace

        owner = controller._candidate_cycle_context_artifact_owner
        currentness = controller._candidate_simulation_currentness_resolver
        controller._candidate_simulation_currentness_resolver = lambda: True
        monkeypatch.setattr(
            owner,
            "resolve_for_current_job",
            lambda *args, **kwargs: SimpleNamespace(),
        )
        with pytest.raises(
            GenerationCycleError,
            match="n7_candidate_simulation_handoff_owner_readback_mismatch",
        ):
            controller._resolve_candidate_simulation_context_handoff(fixture.problem)
        controller._candidate_simulation_currentness_resolver = currentness
    finally:
        fixture.service.close()
