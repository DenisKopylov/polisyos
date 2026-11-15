"""Native N5 bridge refusals and history transport without fabricated action rights.

A genuine Native checkpoint is an integration prerequisite. The handoff below is
an unverified typed candidate, used only to prove refusal before new execution.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from polisyos.core.artifacts import FileSystemCAS, SelectedProfileVerificationReader
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.cycle_substrate import (
    CycleSubstrateContextOwnerError,
    cycle_job_design_problem_ref,
    cycle_job_profile_selection_ref,
)
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleNativeWorldContextHandoffV1,
    GenericCycleSimulationAdmissionOwner,
)
from tests.unit.runtime.quality.test_cycle_substrate import _cycle_context
from tests.unit.runtime.quality.test_generic_simulation_admission_program_graph import (
    _linkage_problem,
    compiled_selection,
)
from tests.unit.runtime.quality.test_native_selected_program_graph_linkage import (
    _unverified_candidate_ref,
)


def _bytes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_native_selection_requires_the_actual_current_action_owner(tmp_path: Path) -> None:
    """A typed Native wrapper cannot borrow the ordinary NL profile grant."""
    case = compiled_selection.__wrapped__(tmp_path)
    problem = _linkage_problem().model_copy(update={"domain": case.world.policy_domain})
    context = _cycle_context(
        domain=problem.domain,
        registry=case.profile.context_inputs.substrate_registry,
        world_model_record=case.world,
        design_problem_ref=cycle_job_design_problem_ref(problem),
    )
    handoff = GenericCycleNativeWorldContextHandoffV1(
        context=context,
        context_job_ref=_unverified_candidate_ref(
            "runtime.quality.cycle_substrate_context_job", "unverified-native-context"
        ),
        profile=case.profile,
        profile_ref=_unverified_candidate_ref(
            "runtime.quality.generic_cycle_simulation_profile", "unverified-original-profile"
        ),
        native_world_checkpoint_ref=_unverified_candidate_ref(
            "runtime_quality.acquisition_candidate_world_checkpoint", "unverified-checkpoint"
        ),
        original_generic_input_ref=_unverified_candidate_ref(
            "runtime.quality.generic_cycle_simulation_n5_input", "unverified-original-input"
        ),
        current_profile_selection_ref=cycle_job_profile_selection_ref(problem),
        source_job_id="original-nl-job",
        job_id="native-acquisition-job",
        run_id="native-run",
        tenant_id="tenant-test",
        cell_id="cell-test",
    )
    owner = GenericCycleSimulationAdmissionOwner(profiles=(case.profile,), store=case.store)
    before = _bytes(case.store.root)
    with pytest.raises(CycleSubstrateContextOwnerError) as unavailable:
        owner.profile_selection_ref_for_handoff(
            handoff=handoff, problem=problem, child_selection=None
        )
    assert unavailable.value.code == "generic_native_world_action_owner_unavailable"
    with pytest.raises(CycleSubstrateContextOwnerError) as child:
        owner.profile_selection_ref_for_handoff(
            handoff=handoff,
            problem=problem,
            child_selection=object(),  # type: ignore[arg-type]
        )
    assert child.value.code == "generic_native_world_child_profile_unsupported"
    assert _bytes(case.store.root) == before


def test_selected_replay_owner_retains_history_without_current_action_rights(
    tmp_path: Path,
) -> None:
    """The existing selected reader retains exact history; it creates no action grant."""
    store = FileSystemCAS(tmp_path / "cas")
    control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite")
    event_log = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
    owner = GenericCycleSimulationAdmissionOwner(profiles=(), store=store)
    owner.bind_native_world_history(control_store=control, event_log=event_log)
    # An opaque process handle is not a valid Native action owner. Even that
    # field must never be copied into the history-only replay owner.
    marker = object()
    owner._native_world_action_owner = marker
    before = _bytes(tmp_path)
    replay = owner._selected_verification_replay_owner()
    assert replay is not owner
    assert type(replay.store) is SelectedProfileVerificationReader
    assert replay._native_action_control_store is control
    assert type(replay._native_action_event_log) is RuntimeDiagnosticEventLog
    assert replay._native_action_event_log._store is control
    assert replay._native_action_event_log.artifact_store is replay.store
    assert replay._native_world_action_owner is None
    assert owner._native_world_action_owner is marker
    assert replay._selected_verification_replay_owner() is replay
    assert _bytes(tmp_path) == before
