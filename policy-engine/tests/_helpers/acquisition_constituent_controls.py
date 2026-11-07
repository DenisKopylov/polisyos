"""Exercise real acquired-world and model reconcilers with foreign constituents."""

from __future__ import annotations

import math
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any

import numpy as np
import pytest

if TYPE_CHECKING:
    from collections.abc import Callable
    from contextlib import AbstractContextManager


@dataclass
class AcquisitionConstituentControls:
    """Record the controls actually reached by the supplied live owner."""

    value_refusals: set[str] = field(default_factory=set)
    model_refusals: set[str] = field(default_factory=set)
    reconciled_worlds: list[Any] = field(default_factory=list)
    model_reconciliations: list[Any] = field(default_factory=list)


def install_acquisition_constituent_controls(
    monkeypatch: pytest.MonkeyPatch,
    *,
    should_exercise: Callable[[Any], bool] | None = None,
    probe_scope: Callable[[Any, str, Any], AbstractContextManager[None]] | None = None,
    once_per_owner_kind: bool = False,
) -> AcquisitionConstituentControls:
    """Install distinguishing controls around the actual bridge consumers.

    The first three foreign inputs are test-only prospective values. The NCM
    control is a real selected CAS object with the same declaration edge and
    current profile. None of these tests grants source or publication authority.
    """
    from polisyos.ir import candidate_ncm_spec_from_declaration
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository

    observed = AcquisitionConstituentControls()
    original_values = AcquisitionWorldGrowthBridge._reconcile_acquired_candidate_values
    original_model = AcquisitionWorldGrowthBridge._reconcile_acquired_candidate_model_values

    def exercise_values(bridge: Any, *, prospective_values: Any, world_model_record: Any) -> None:
        if (should_exercise is not None and not should_exercise(bridge)) or (
            once_per_owner_kind and observed.reconciled_worlds
        ):
            original_values(
                bridge, prospective_values=prospective_values, world_model_record=world_model_record
            )
            return

        def scope(label: str) -> AbstractContextManager[None]:
            return (
                probe_scope(bridge, label, world_model_record)
                if probe_scope is not None
                else nullcontext()
            )

        original_values(
            bridge, prospective_values=prospective_values, world_model_record=world_model_record
        )
        with scope("foreign_state"):
            actual = prospective_values.materialized_state
            cash = np.asarray(actual.firms.cash)
            assert cash.size > 0
            changed = actual.replace(firms=actual.firms.replace(cash=cash + 17))
            with pytest.raises(
                ValueError, match="acquisition_prospective_state_owner_reconciliation_failed"
            ):
                original_values(
                    bridge,
                    prospective_values=replace(prospective_values, materialized_state=changed),
                    world_model_record=world_model_record,
                )
            observed.value_refusals.add("same_target_changed_other_native_component")
        with scope("foreign_source_path"):
            first, *rest = prospective_values.effective_rules
            changed_rule = first.model_copy(
                update={"source_path": first.source_path + ".not_the_source"}
            )
            with pytest.raises(
                ValueError, match="acquisition_prospective_rule_owner_reconciliation_failed"
            ):
                original_values(
                    bridge,
                    prospective_values=replace(
                        prospective_values, effective_rules=(changed_rule, *rest)
                    ),
                    world_model_record=world_model_record,
                )
            observed.value_refusals.add("same_state_wrong_actual_rule")
        original_values(
            bridge, prospective_values=prospective_values, world_model_record=world_model_record
        )
        observed.reconciled_worlds.append(world_model_record)

    def exercise_model(bridge: Any, *, prospective_model: Any, offer: Any) -> None:
        if (should_exercise is not None and not should_exercise(bridge)) or (
            once_per_owner_kind and observed.model_reconciliations
        ):
            original_model(bridge, prospective_model=prospective_model, offer=offer)
            return

        def scope(label: str) -> AbstractContextManager[None]:
            return probe_scope(bridge, label, offer) if probe_scope is not None else nullcontext()

        original_model(bridge, prospective_model=prospective_model, offer=offer)
        with scope("foreign_baseline"):
            target = prospective_model.declared_model_values.target_world_slot
            wrong_baseline = dict(prospective_model.n5_config.baseline_state)
            baseline = float(wrong_baseline[target])
            float32_limit = float(np.finfo(np.float32).max)
            assert math.isfinite(baseline) and abs(baseline) <= float32_limit
            delta = max(17.0, abs(baseline) * 0.5)
            changed = baseline + delta
            if not math.isfinite(changed) or abs(changed) > float32_limit:
                changed = baseline - delta
            assert math.isfinite(changed) and abs(changed) <= float32_limit
            original_float32, changed_float32 = np.float32(baseline), np.float32(changed)
            assert np.isfinite(original_float32) and np.isfinite(changed_float32)
            assert original_float32 != changed_float32
            wrong_baseline[target] = changed
            with pytest.raises(
                ValueError, match="acquisition_prospective_n5_configuration_mismatch"
            ):
                original_model(
                    bridge,
                    prospective_model=replace(
                        prospective_model,
                        n5_config=prospective_model.n5_config.model_copy(
                            deep=True, update={"baseline_state": wrong_baseline}
                        ),
                    ),
                    offer=offer,
                )
            observed.model_refusals.add("same_source_wrong_n5_baseline")
        declared = prospective_model.declared_model_values
        with scope("foreign_declaration"):
            changed_declaration = replace(
                declared, outcome_per_target_unit=declared.outcome_per_target_unit * 2.0
            )
            with pytest.raises(ValueError, match="acquisition_prospective_declared_model_mismatch"):
                original_model(
                    bridge,
                    prospective_model=replace(
                        prospective_model, declared_model_values=changed_declaration
                    ),
                    offer=offer,
                )
            observed.model_refusals.add("same_state_wrong_declared_scm")

        with scope("foreign_ncm"):
            admission = bridge.control_store.current_execution_job_admission()
            current = admission.job
            repository = GenerationSourceRepository(bridge.artifact_store)
            wrong_spec = candidate_ncm_spec_from_declaration(changed_declaration)
            assert wrong_spec != candidate_ncm_spec_from_declaration(declared)
            assert offer.model_declaration_ref is not None and offer.ncm_ref is not None
            wrong_selected_ncm = repository.persist_candidate_ncm_selected_view(
                ncm_spec=wrong_spec,
                declaration_ref=offer.model_declaration_ref,
                job_id=current.job_id,
                run_id=current.run_id,
                tenant_id=admission.scope.tenant_id,
                cell_id=admission.scope.cell_id,
                profile_content_hash=offer.profile.content_hash,
            )
            assert bridge.artifact_store.verify(wrong_selected_ncm).ok
            assert wrong_selected_ncm.artifact_id != offer.ncm_ref.artifact_id
            with pytest.raises(
                ValueError, match="n4_candidate_scenario_source_v2_ncm_declaration_mismatch"
            ):
                repository.load_candidate_declared_ncm(
                    declaration_ref=offer.model_declaration_ref,
                    ncm_ref=wrong_selected_ncm,
                    expected_profile=offer.profile,
                    expected_run_id=current.run_id,
                    expected_job_id=current.job_id,
                    expected_tenant_id=admission.scope.tenant_id,
                    expected_cell_id=admission.scope.cell_id,
                )
            with pytest.raises(
                ValueError, match="acquisition_prospective_selected_model_not_established"
            ):
                original_model(
                    bridge,
                    prospective_model=prospective_model,
                    offer=offer.model_copy(update={"ncm_ref": wrong_selected_ncm}),
                )
            observed.model_refusals.add("unchanged_declaration_wrong_selected_ncm_bytes")
        original_model(bridge, prospective_model=prospective_model, offer=offer)
        observed.model_reconciliations.append(offer)

    monkeypatch.setattr(
        AcquisitionWorldGrowthBridge, "_reconcile_acquired_candidate_values", exercise_values
    )
    monkeypatch.setattr(
        AcquisitionWorldGrowthBridge, "_reconcile_acquired_candidate_model_values", exercise_model
    )
    return observed


@dataclass
class FirstCandidateExperimentConstituentControls:
    """The first live candidate action and its selected constituent probes."""

    controls: AcquisitionConstituentControls
    probe_results: list[tuple[Any, ...]]

    def assert_selected(self, *, control: Any, history: Any) -> None:
        """Bind the probes to the actual persisted first evaluation."""
        from polisyos.runtime.quality.world_model_record import load_world_model_record

        initial_history = history
        initial_terminal = history.terminal
        initial_basis = history.selected_basis
        assert initial_basis is not None
        assert self.controls.value_refusals == {
            "same_target_changed_other_native_component",
            "same_state_wrong_actual_rule",
        }
        assert self.controls.model_refusals == {
            "same_source_wrong_n5_baseline",
            "same_state_wrong_declared_scm",
            "unchanged_declaration_wrong_selected_ncm_bytes",
        }
        assert {row[0] for row in self.probe_results} == {
            "foreign_state",
            "foreign_source_path",
            "foreign_baseline",
            "foreign_declaration",
            "foreign_ncm",
        }
        assert len(self.probe_results) == 5
        assert all(row[1] == initial_terminal.candidate_action_ref for row in self.probe_results)
        assert all(
            row[2] == initial_history.action.candidate_source_ref for row in self.probe_results
        )
        assert len(self.controls.reconciled_worlds) == 1
        assert len(self.controls.model_reconciliations) == 1
        assert initial_basis.selected_world_model_ref is not None
        selected_world = load_world_model_record(
            control._artifact_store, initial_basis.selected_world_model_ref
        )
        assert self.controls.reconciled_worlds[0] == selected_world
        assert all(row[3] == selected_world.content_hash for row in self.probe_results)
        assert initial_history.evaluation is not None
        selected_input = initial_history.evaluation.input_record
        actual_offer = self.controls.model_reconciliations[0]
        assert actual_offer.profile == selected_input.profile
        assert actual_offer.model_declaration_ref == selected_input.model_declaration_ref
        assert actual_offer.ncm_ref == selected_input.ncm_ref


def install_first_candidate_experiment_constituent_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> FirstCandidateExperimentConstituentControls:
    """Check foreign constituents during the first real candidate worker handoff."""
    from contextlib import contextmanager

    from polisyos.core.artifacts import (
        ArtifactRef,
        artifact_ref_for_manifest,
        load_core_json_artifact,
    )
    from polisyos.core.contracts import DataSnapshot, StateSnapshot
    from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CandidateAcquisitionActionReceipt,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views
    from tests._helpers.candidate_experiment_served_execution import _standard_invocation_units

    active_handoffs = []
    probe_results = []
    original_handoff = AcquisitionWorldGrowthBridge._candidate_source_context_handoff

    def capture_first_handoff(bridge, *, origin=None, **kwargs):
        if origin is None or origin.candidate_terminal_history_chain:
            return original_handoff(bridge, origin=origin, **kwargs)
        active_handoffs.append((bridge, origin, kwargs["candidate_action_ref"]))
        try:
            return original_handoff(bridge, origin=origin, **kwargs)
        finally:
            active_handoffs.pop()

    monkeypatch.setattr(
        AcquisitionWorldGrowthBridge, "_candidate_source_context_handoff", capture_first_handoff
    )

    @contextmanager
    def preserve_current_action(bridge, label, subject):
        assert active_handoffs and active_handoffs[-1][0] is bridge
        _, origin, action_ref = active_handoffs[-1]
        control = bridge._source_control_service
        assert control is not None and control._control_store is bridge.control_store
        store = bridge.artifact_store
        admission = bridge.control_store.current_execution_job_admission()
        assert admission.scope.tenant_id == origin.tenant_id
        assert admission.scope.cell_id == origin.cell_id
        assert admission.job.run_id == origin.run_id
        assert store.verify(action_ref).ok
        action = CandidateAcquisitionActionReceipt.model_validate(
            load_core_json_artifact(store, action_ref)
        )
        assert (action.tenant_id, action.cell_id, action.run_id, action.source_job_id) == (
            origin.tenant_id,
            origin.cell_id,
            origin.run_id,
            origin.source_job_id,
        )
        assert action.action_job_id == admission.job.job_id
        assert action.action_generation == 1
        heads_before = control._control_store.list_acquisition_action_heads_for_source(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
        )
        current_heads = tuple(head for head in heads_before if head.job_id == action.action_job_id)
        assert len(current_heads) == 1
        assert current_heads[0].receipt_phase == "candidate_input_reentry_pending"
        units_before = _standard_invocation_units(control=control, run_id=origin.run_id)
        assert units_before == 2

        is_world = label in {"foreign_state", "foreign_source_path"}
        world = subject if is_world else subject.profile.context_inputs.world_model_record
        views = world_model_artifact_views(world)
        assert views.bound_state_snapshot_ref is not None
        snapshot = DataSnapshot.model_validate(
            load_core_json_artifact(store, views.data_snapshot_ref)
        )
        state = StateSnapshot.model_validate(
            load_core_json_artifact(store, views.bound_state_snapshot_ref)
        )
        prior_simulation = origin.effective_source_cycle.simulation
        prior_execution = ArtifactRef.model_validate(
            prior_simulation.diagnostics["candidate_simulation_execution_selected_ref"]
        )
        selected_refs = [
            action_ref,
            action.candidate_source_ref,
            views.data_snapshot_ref,
            snapshot.data_ref,
            views.registry_bundle_ref,
            views.model_spec_ref,
            views.input_bindings_ref,
            views.bound_state_snapshot_ref,
            state.state_ref,
            prior_simulation.candidate_simulation_n4_source_ref,
            prior_simulation.candidate_simulation_context_job_ref,
            prior_simulation.candidate_simulation_n5_input_ref,
            prior_simulation.simulation_result_ref,
            prior_execution,
        ]
        if not is_world:
            selected_refs.extend((subject.model_declaration_ref, subject.ncm_ref))
        assert all(isinstance(ref, ArtifactRef) for ref in selected_refs)
        selected_refs = [
            artifact_ref_for_manifest(store.get_manifest(ref)) for ref in selected_refs
        ]
        assert all(store.verify(ref).ok for ref in selected_refs)
        before = tuple(
            (ref, store.get_bytes(ref), store.get_manifest(ref)) for ref in selected_refs
        )
        subject_before = subject.model_dump(mode="json")
        n5_attempts = []

        def forbid_n5(*args, **kwargs):
            n5_attempts.append((args, kwargs))
            raise AssertionError("foreign constituent attempted physical N5")

        with monkeypatch.context() as no_n5:
            no_n5.setattr(JointSimulationHorizonController, "run", forbid_n5)
            yield
        assert not n5_attempts
        assert _standard_invocation_units(control=control, run_id=origin.run_id) == units_before
        assert (
            control._control_store.list_acquisition_action_heads_for_source(
                tenant_id=origin.tenant_id,
                cell_id=origin.cell_id,
                run_id=origin.run_id,
                source_job_id=origin.source_job_id,
            )
            == heads_before
        )
        assert subject.model_dump(mode="json") == subject_before
        assert tuple(
            (ref, store.get_bytes(ref), store.get_manifest(ref)) for ref in selected_refs
        ) == (before)
        probe_results.append((label, action_ref, action.candidate_source_ref, world.content_hash))

    constituent_controls = install_acquisition_constituent_controls(
        monkeypatch,
        should_exercise=lambda bridge: bool(active_handoffs and active_handoffs[-1][0] is bridge),
        probe_scope=preserve_current_action,
        once_per_owner_kind=True,
    )

    return FirstCandidateExperimentConstituentControls(constituent_controls, probe_results)
