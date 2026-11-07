"""Real served candidate-model revisions, with retained and refusal controls.

P01/P03/P05/P29/P32/P33: the controlled external provider and configured
synthetic SCM remain candidate inputs. Actual acquisition, CAS, N5 and HTTP
owners must establish the transition; neither a new ID nor this fixture grants
empirical, measurement or publication authority.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from polisyos.core import canon
from polisyos.core.artifacts import ArtifactRef, artifact_ref_identity_key
from polisyos.core.contracts.runtime import RunCandidateSimulationAcquisitionHistoryEntry
from polisyos.ir import prepare_ncm_spec_selected_values
from polisyos.pdc import gy_content_hash
from polisyos.runtime.quality.acquisition_evaluation import (
    AcquisitionEvaluationDecision,
    read_acquisition_evaluation_artifact,
    resolve_selected_acquisition_evaluation_parts,
)
from polisyos.runtime.quality.acquisition_model_transition import (
    resolve_candidate_model_revision,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoopReceiptV2
from polisyos.runtime.quality.candidate_simulation import (
    CandidateSimulationSyntheticModelDeclarationV1,
)
from polisyos.runtime.quality.generation_cycle import AcquisitionOverlayReentryReceipt
from polisyos.runtime.quality.generation_source import GenerationSourceRepository
from polisyos.runtime.quality.n5_execution_basis import exact_n5_content_bytes
from tests._helpers import acquisition_served_history as fixture
from tests.integration.core_runtime.test_acquisition_receiver_constructor_served import (
    _run_genuine_first_b,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def _with_model_values(
    declaration: CandidateSimulationSyntheticModelDeclarationV1, **updates: float
) -> CandidateSimulationSyntheticModelDeclarationV1:
    payload = declaration.model_dump(mode="json", exclude={"content_hash"})
    payload.update(updates)
    return type(declaration).model_validate({**payload, "content_hash": gy_content_hash(payload)})


def _projection(client: TestClient, ctx: SimpleNamespace) -> dict[str, Any]:
    response = client.get(ctx.history_path, headers=ctx.history_headers)
    assert response.status_code == 200, response.text
    return response.json()["run"]["candidate_simulation"]


def _pair(ctx: SimpleNamespace, oracle: Any, *, epoch: int, name: str) -> SimpleNamespace:
    oracle.epoch_id = epoch
    prepared = oracle._action(ctx, name=name + "-prepare", appoint=True)
    selected = oracle._action(ctx, name=name + "-admit", appoint=False)
    assert prepared.receipt.terminal_outcome == "quarantined_no_growth"
    assert prepared.job_id != selected.job_id
    assert prepared.transport_calls and not selected.transport_calls
    assert selected.receipt.action_generation == prepared.receipt.action_generation + 1
    assert type(selected.receipt) is AcquisitionRouteLoopReceiptV2
    return selected


def _reopen(
    ctx: SimpleNamespace,
    control: Any,
    terminal: AcquisitionRouteLoopReceiptV2,
    *,
    previous_run: Any,
    previous_cycle: Any,
) -> SimpleNamespace:
    store, events = control._artifact_store, control._diagnostic_event_log
    assert terminal.reentry_receipt_ref is not None
    reentry = AcquisitionOverlayReentryReceipt.model_validate(
        canon.from_canonical_bytes(
            fixture._within_fixture_owner(store.get_bytes, terminal.reentry_receipt_ref)
        )
    )
    assert reentry.continued_generation_run is not None
    assert reentry.continued_generation_run.cycles[:-1] == previous_run.cycles
    assert reentry.source_cycle_index == previous_cycle.cycle_index
    selected = fixture._within_fixture_owner(
        resolve_selected_acquisition_evaluation_parts,
        artifact_store=store,
        control_store=control._control_store,
        tenant_id=fixture.TENANT,
        cell_id=fixture.CELL,
        run_id=ctx.run_id,
        generation_run=reentry.continued_generation_run,
        source_cycle=reentry.new_cycle,
        design_problem_ref=ctx.closure.design_problem_ref,
    )
    decision = fixture._within_fixture_owner(
        read_acquisition_evaluation_artifact,
        store=store,
        event_log=events,
        ref=terminal.evaluation_decision_ref,
        record_type=AcquisitionEvaluationDecision,
    )
    assert type(decision) is AcquisitionEvaluationDecision
    assert decision.comparison_result == "different"
    assert decision.predicate_provenance == "recomputed" and not decision.reason_codes
    assert terminal.selected_evaluation is not None
    assert terminal.selected_evaluation.basis_ref == terminal.selected_basis_ref
    assert terminal.selected_evaluation.model_dump(exclude={"basis_ref"}) == (
        selected.selected.model_dump(exclude={"basis_ref"})
    )
    arguments = {
        "artifact_store": store,
        "event_log": events,
        "control_store": control._control_store,
        "tenant_id": fixture.TENANT,
        "cell_id": fixture.CELL,
        "run_id": ctx.run_id,
        "design_problem_ref": ctx.closure.design_problem_ref,
        "action_job_id": terminal.job_id,
        "action_generation": terminal.action_generation,
        "route_id": terminal.route_id,
        "decision_ref": terminal.evaluation_decision_ref,
        "selected_basis_ref": terminal.selected_basis_ref,
        "previous_run": previous_run,
        "previous_cycle": previous_cycle,
        "selected_run": reentry.continued_generation_run,
        "selected_cycle": reentry.new_cycle,
    }
    return SimpleNamespace(
        reentry=reentry, selected=selected, decision=decision, arguments=arguments
    )


def _assert_selected_model_ref_controls(
    ctx: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    previous: Any,
    replay: SimpleNamespace,
    expected_revision: Any,
) -> None:
    """Remove actual CAS bytes or substitute a real foreign job's selected ref."""
    with TestClient(ctx.app()) as client:
        control = client.app.state.runtime_container.control_service
        store = control._artifact_store
        arguments = {
            **replay.arguments,
            "artifact_store": store,
            "event_log": control._diagnostic_event_log,
            "control_store": control._control_store,
        }

        def resolve() -> Any:
            return fixture._within_fixture_owner(resolve_candidate_model_revision, **arguments)

        def assert_limited() -> None:
            projection = _projection(client, ctx)
            assert projection["acquisition_history_limitation_code"] == (
                "acquisition_action_history_integrity_not_established"
            ), projection
            assert projection["acquisition_history"] == []

        assert resolve() == expected_revision
        assert _projection(client, ctx)["acquisition_history_limitation_code"] is None
        current = replay.selected.input_record
        for field, reason in (
            ("model_declaration_ref", "candidate_simulation_model_declaration_integrity_failed"),
            ("ncm_ref", "ncm_selected_view_integrity_failed"),
        ):
            ref = getattr(current, field)
            blob, _manifest = store._paths(ref.artifact_id)
            assert blob.is_relative_to(tmp_path) and not blob.is_symlink()
            original_bytes = blob.read_bytes()
            removed = blob.with_name(blob.name + ".model-transition-removal")
            assert not removed.exists()
            blob.rename(removed)
            try:
                with pytest.raises(ValueError, match="^" + reason + "$"):
                    resolve()
                assert_limited()
            finally:
                removed.rename(blob)
            assert blob.read_bytes() == original_bytes
            assert resolve() == expected_revision

        real_load = GenerationSourceRepository.load_candidate_declared_ncm
        for field, reason in (
            ("declaration_ref", "candidate_simulation_model_declaration_owner_profile_mismatch"),
            ("ncm_ref", "n4_candidate_scenario_source_v2_ncm_owner_profile_mismatch"),
        ):
            current_ref = (
                current.model_declaration_ref if field == "declaration_ref" else current.ncm_ref
            )
            foreign_ref = (
                previous.input_record.model_declaration_ref
                if field == "declaration_ref"
                else previous.input_record.ncm_ref
            )
            assert artifact_ref_identity_key(current_ref) != artifact_ref_identity_key(foreign_ref)
            substituted: list[ArtifactRef] = []

            def load_with_foreign_ref(
                repository: Any,
                *,
                selected_field: str = field,
                expected_ref: ArtifactRef = current_ref,
                replacement_ref: ArtifactRef = foreign_ref,
                observed: list[ArtifactRef] = substituted,
                **kwargs: Any,
            ) -> Any:
                if artifact_ref_identity_key(kwargs[selected_field]) == artifact_ref_identity_key(
                    expected_ref
                ):
                    observed.append(kwargs[selected_field])
                    kwargs[selected_field] = replacement_ref
                # Only the input selector is corrupted. The genuine owner reads
                # the real foreign view and decides whether its scope is valid.
                return real_load(repository, **kwargs)

            with monkeypatch.context() as mutation:
                mutation.setattr(
                    GenerationSourceRepository, "load_candidate_declared_ncm", load_with_foreign_ref
                )
                with pytest.raises(ValueError, match="^" + reason + "$"):
                    resolve()
                assert substituted
                before_get = len(substituted)
                assert_limited()
                assert len(substituted) > before_get
            assert resolve() == expected_revision
            assert _projection(client, ctx)["acquisition_history_limitation_code"] is None


def test_served_equal_source_model_revision_reexecutes_and_projects_candidate_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """Trace a configured coefficient through real acquisition, N5 and a fresh GET."""

    def check(**values: Any) -> None:
        ctx, oracle = values["ctx"], values["oracle"]
        previous, old_selected = values["actual_b"], values["selected_b"]
        original = ctx.candidate_model_declaration
        assert type(original) is CandidateSimulationSyntheticModelDeclarationV1
        oracle.monitor.watch("model_revision_native_ncm", values["capture"].method.pure_step)
        with TestClient(ctx.app()) as client:
            store = client.app.state.runtime_container.control_service._artifact_store
            prior_refs = (
                old_selected.n4_source_ref,
                old_selected.context_job_ref,
                old_selected.n5_input_ref,
                old_selected.n5_execution_ref,
                old_selected.n5_result_ref,
                previous.input_record.model_declaration_ref,
                previous.input_record.ncm_ref,
            )
            prior_bytes = tuple(
                (ref, fixture._within_fixture_owner(store.get_bytes, ref)) for ref in prior_refs
            )

        # A fresh object and a new real admission do not create a model delta.
        ctx.set_candidate_model_declaration(original.model_copy(deep=True))
        retained = _pair(ctx, oracle, epoch=2, name="unchanged-model")
        assert retained.receipt.terminal_outcome == "source_admitted_evaluation_retained"
        assert retained.after_calls == retained.before_calls
        assert retained.after_artifacts == retained.before_artifacts
        assert retained.receipt.selected_evaluation.model_dump(exclude={"basis_ref"}) == (
            old_selected.model_dump(exclude={"basis_ref"})
        )
        projection = oracle._fresh_projection(ctx)
        retained_row = next(
            row
            for row in projection["acquisition_history"]
            if row["action_generation"] == retained.receipt.action_generation
        )
        assert retained_row.get("continuation") is None
        assert retained_row["evaluation_provenance"] == "retained_prior"

        replacement = _with_model_values(
            original, outcome_per_target_unit=original.outcome_per_target_unit * 2.0
        )
        assert replacement.model_dump(exclude={"content_hash", "outcome_per_target_unit"}) == (
            original.model_dump(exclude={"content_hash", "outcome_per_target_unit"})
        )
        ctx.set_candidate_model_declaration(replacement)
        changed = _pair(ctx, oracle, epoch=3, name="coefficient-model")
        terminal = changed.receipt
        assert terminal.terminal_outcome == "reentry_completed"
        assert (
            terminal.current_continuation_ref is None and terminal.reentry_receipt_ref is not None
        )
        for name in ("n5", "n5_controller", "reentry_cycle"):
            assert changed.after_calls[name] == changed.before_calls[name] + 1
        assert (
            changed.after_calls["model_revision_native_ncm"]
            > (changed.before_calls["model_revision_native_ncm"])
        )
        oracle.monitor.assert_slots_unchanged()

        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            store = control._artifact_store
            replay = _reopen(
                ctx,
                control,
                terminal,
                previous_run=ctx.closure.generation_run,
                previous_cycle=ctx.closure.source_cycle,
            )
            revision = fixture._within_fixture_owner(
                resolve_candidate_model_revision, **replay.arguments
            )
            selected = replay.selected
            assert selected.source.problem == previous.source.problem
            assert selected.source.semantic_identity_hash == previous.source.semantic_identity_hash
            assert (
                selected.source.candidate_occurrence_hash
                != previous.source.candidate_occurrence_hash
            )
            assert selected.selected.candidate_id == old_selected.candidate_id
            assert selected.selected.cycle_index == old_selected.cycle_index + 1
            assert selected.input_record.n5 == previous.input_record.n5
            assert selected.selected.n5_execution_ref != old_selected.n5_execution_ref
            assert selected.selected.n5_result_ref != old_selected.n5_result_ref
            assert replay.decision.prior_evaluation.model_dump(exclude={"basis_ref"}) == (
                old_selected.model_dump(exclude={"basis_ref"})
            )
            repository = GenerationSourceRepository(store)
            declared = []
            native_ncms = []
            for evaluation in (previous, selected):
                declaration, ncm = fixture._within_fixture_owner(
                    repository.load_candidate_declared_ncm,
                    declaration_ref=evaluation.input_record.model_declaration_ref,
                    ncm_ref=evaluation.input_record.ncm_ref,
                    expected_profile=evaluation.input_record.profile,
                    expected_run_id=ctx.run_id,
                    expected_job_id=evaluation.source.job_id,
                    expected_tenant_id=fixture.TENANT,
                    expected_cell_id=fixture.CELL,
                )
                declared.append(declaration)
                native_ncms.append(prepare_ncm_spec_selected_values(ncm).value_bytes)
            envelope = {"profile_config_ref", "profile_content_hash", "content_hash"}
            old_meaning, new_meaning = (
                declaration.model_dump(exclude=envelope) for declaration in declared
            )
            assert {key for key in old_meaning if old_meaning[key] != new_meaning[key]} == {
                "outcome_per_target_unit"
            }
            assert declared[1].outcome_per_target_unit == replacement.outcome_per_target_unit
            assert native_ncms[0] != native_ncms[1]
            old_effects = tuple(
                tuple(point.effect for point in trajectory.points)
                for trajectory in previous.result.trajectories
            )
            new_effects = tuple(
                tuple(point.effect for point in trajectory.points)
                for trajectory in selected.result.trajectories
            )
            assert old_effects and new_effects
            assert exact_n5_content_bytes(old_effects) != exact_n5_content_bytes(new_effects)
            expected_refs = {
                "evaluation_decision_ref": terminal.evaluation_decision_ref,
                "previous_input_ref": old_selected.n5_input_ref,
                "selected_input_ref": selected.selected.n5_input_ref,
                "previous_declaration_ref": previous.input_record.model_declaration_ref,
                "selected_declaration_ref": selected.input_record.model_declaration_ref,
                "previous_ncm_ref": previous.input_record.ncm_ref,
                "selected_ncm_ref": selected.input_record.ncm_ref,
                "previous_basis_ref": replay.decision.prior_basis_ref,
                "selected_basis_ref": terminal.selected_basis_ref,
            }
            for ref, body in prior_bytes:
                assert fixture._within_fixture_owner(store.get_bytes, ref) == body

        # A new app has no in-memory result from the producing worker.
        projection = oracle._fresh_projection(ctx)
        row = next(
            row
            for row in projection["acquisition_history"]
            if row["action_generation"] == terminal.action_generation
        )
        entry = RunCandidateSimulationAcquisitionHistoryEntry.model_validate(row)
        assert entry.continuation is not None
        displayed_revision = entry.continuation.model_revision
        assert displayed_revision is not None
        for field, ref in expected_refs.items():
            assert getattr(displayed_revision, field) == ref
        assert displayed_revision.changed_field == "outcome_per_target_unit"
        assert displayed_revision.predicate_provenance == "recomputed"
        assert displayed_revision.authority_purpose == "candidate_observation_only"
        assert displayed_revision.publication_authority is False
        assert entry.continuation.acquired_outcome_revision is None
        assert entry.continuation.previous_selected_target_baseline_hash == (
            entry.continuation.selected_target_baseline_hash
        )
        assert entry.continuation.selected_target_baseline_hash is not None
        assert entry.evaluation_provenance == "new_execution"
        observation = entry.selected_n5_observation
        assert observation is not None and observation.result_body is not None
        assert observation.candidate_id == entry.new_candidate_id == old_selected.candidate_id
        assert observation.cycle_index == selected.selected.cycle_index
        assert observation.n5_execution_ref == selected.selected.n5_execution_ref
        assert observation.simulation_result_ref == selected.selected.n5_result_ref
        assert observation.n5_input_ref == displayed_revision.selected_input_ref
        body = observation.result_body
        assert body.model_declaration_ref == displayed_revision.selected_declaration_ref
        assert body.outcome_units == {declared[1].outcome_variable: declared[1].outcome_unit_id}
        assert body.unit_provenance == "declared_candidate_model"
        assert body.publication_authority is False
        assert (
            tuple(
                tuple(point.effects for point in trajectory.points)
                for trajectory in body.trajectories
            )
            == new_effects
        )
        _assert_selected_model_ref_controls(ctx, monkeypatch, tmp_path, previous, replay, revision)

        # A changed unrelated model component has real numerical consequences,
        # but cannot be advertised as the supported coefficient-only revision.
        unrelated = _with_model_values(
            replacement, outcome_noise_stddev=replacement.outcome_noise_stddev + 0.1
        )
        assert unrelated.outcome_per_target_unit == replacement.outcome_per_target_unit
        ctx.set_candidate_model_declaration(unrelated)
        other = _pair(ctx, oracle, epoch=4, name="unrelated-model-component")
        assert other.receipt.terminal_outcome == "reentry_completed"
        assert other.after_calls["n5_controller"] == other.before_calls["n5_controller"] + 1
        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            unsupported = _reopen(
                ctx,
                control,
                other.receipt,
                previous_run=replay.reentry.continued_generation_run,
                previous_cycle=replay.reentry.new_cycle,
            )
            with pytest.raises(
                ValueError,
                match=r"^candidate_model_revision_declaration_difference_not_established$",
            ):
                fixture._within_fixture_owner(
                    resolve_candidate_model_revision, **unsupported.arguments
                )
            projection = _projection(client, ctx)
            assert projection["acquisition_history_limitation_code"] == (
                "acquisition_action_history_integrity_not_established"
            )
            assert projection["acquisition_history"] == []
            for ref, previous_body in prior_bytes:
                assert fixture._within_fixture_owner(control._artifact_store.get_bytes, ref) == (
                    previous_body
                )
        oracle.monitor.assert_slots_unchanged()

    _run_genuine_first_b(tmp_path, monkeypatch, served_recorded_candidate_gateway, check)
