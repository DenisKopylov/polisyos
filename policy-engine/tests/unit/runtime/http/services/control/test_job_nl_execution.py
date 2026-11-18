"""Completion handoff for one synthetic Generic initial observation.

The source and numerical owners are isolated here; retained-artifact replay
separately exercises their actual selected data and physical work evidence.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.services.control.job_nl_execution import (
    ControlNLJobExecutionMixin,
    _GenericInitialCompletion,
)
from polisyos.runtime.quality import acquisition_evaluation, generation_cycle
from polisyos.runtime.quality import generic_simulation_admission as generic
from polisyos.runtime.quality.joint_simulation_horizon import (
    EnginePlan,
    HorizonSpec,
    JointSimulationRequest,
)
from tests.unit.runtime.http.test_control_plane_store_generic_initial import (
    _initial_frontier_bundle,
)


def test_initial_completion_reopens_selected_binding_and_passes_its_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A matching request reaches the result reader; a swapped request cannot."""
    job = SimpleNamespace(job_id="job-a", run_id="run-a")
    _, selected, _basis, _decision, frontier = _initial_frontier_bundle(tmp_path, job)
    request = JointSimulationRequest.model_construct(
        world_model_record_ref="synthetic-world",
        world_model_record=None,
        intervention_atoms=(),
        selected_outcomes=("outcome",),
        horizon=HorizonSpec(start=0, end=0),
        engine_plan=(
            EnginePlan.model_construct(
                engine_kind="program_graph",
                objective_ref="objective",
                program_semantic_input_bindings_ref=selected.current_method_input_bindings_ref,
            ),
        ),
    )
    source = generic.GenericCycleSimulationN5InputV1.model_construct(
        profile_ref=selected.profile_ref,
        profile=SimpleNamespace(
            context_inputs=SimpleNamespace(
                world_model_record=SimpleNamespace(content_hash="world-hash")
            )
        ),
        job_id=selected.execution_job_id,
        run_id=selected.run_id,
        tenant_id=frontier.key.tenant_id,
        cell_id=frontier.key.cell_id,
        outcome_variable="outcome",
    )
    execution = generic.GenericCycleSimulationN5ExecutionV3.model_construct(
        input_ref=selected.input_ref,
        result_ref=selected.result_ref,
        initial_method_input_purpose="current_use_method_input_revalidation",
        request_binding=SimpleNamespace(request=request),
    )
    events = []
    result = object()

    def load_artifact(_store: object, ref: artifacts.ArtifactRef) -> object:
        events.append(ref)
        if ref == selected.input_ref:
            return source
        assert ref == selected.execution_ref
        return execution

    def load_result(ref: artifacts.ArtifactRef, **kwargs: object) -> object:
        assert ref == selected.result_ref
        assert kwargs["expected_request"] is request
        assert kwargs["expected_world_model_record_content_hash"] == "world-hash"
        assert kwargs["expected_selected_outcomes"] == ("outcome",)
        events.append("result")
        return result

    def verify_work(**kwargs: object) -> None:
        assert kwargs["result"] is result
        assert kwargs["input_record"] is source
        events.append("ledger")

    monkeypatch.setattr(artifacts, "load_core_json_artifact", load_artifact)
    monkeypatch.setattr(
        generic.GenericCycleSimulationN5InputV1, "model_validate", lambda value: value
    )
    monkeypatch.setattr(generic, "parse_generic_cycle_simulation_n5_execution", lambda value: value)
    monkeypatch.setattr(generation_cycle, "load_joint_simulation_result", load_result)
    monkeypatch.setattr(acquisition_evaluation, "verify_generic_initial_physical_work", verify_work)
    owner = SimpleNamespace(
        _artifact_store=object(),
        _generic_cycle_simulation_admission_owner=SimpleNamespace(
            resolve_profile=lambda *_args, **_kwargs: events.append("profile")
        ),
        _llm_producer_settlement_store=object(),
    )
    context = SimpleNamespace(producer_run_binding=object())
    seed = _GenericInitialCompletion(frontier=frontier, request=request)

    ControlNLJobExecutionMixin._revalidate_generic_initial_completion(owner, context, (seed,))
    assert events == [selected.input_ref, "profile", selected.execution_ref, "result", "ledger"]

    events.clear()
    wrong = replace(seed, request=request.model_copy(update={"seed": request.seed + 1}))
    with pytest.raises(ValueError, match=r"^generic_initial_completion_request_binding_mismatch$"):
        ControlNLJobExecutionMixin._revalidate_generic_initial_completion(owner, context, (wrong,))
    assert events == [selected.input_ref, "profile", selected.execution_ref]


def test_initial_completion_with_no_seed_needs_no_owner() -> None:
    """Legacy and ordinary completions do not gain a new read dependency."""
    ControlNLJobExecutionMixin._revalidate_generic_initial_completion(object(), object(), ())
