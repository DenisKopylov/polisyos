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
    AcquisitionEvaluationDecisionV2,
    read_acquisition_basis_or_decision_artifact,
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


def test_custom_seed_observation_continues_without_changing_legacy_stop() -> None:
    """A custom seed requires proof; legacy seed-only hooks still stop."""
    mode = fixture._seed_observer_mode
    assert mode(seed_only=False, seed_only_context=False, continuing=False, custom_seed=False) == (
        "none"
    )
    assert mode(seed_only=True, seed_only_context=False, continuing=False, custom_seed=True) == (
        "stop"
    )
    assert mode(seed_only=False, seed_only_context=True, continuing=False, custom_seed=True) == (
        "stop"
    )
    assert mode(seed_only=False, seed_only_context=False, continuing=True, custom_seed=True) == (
        "continue"
    )
    with pytest.raises(ValueError, match="served_candidate_seed_observer_missing"):
        mode(seed_only=False, seed_only_context=False, continuing=False, custom_seed=True)
    with pytest.raises(ValueError, match="served_candidate_seed_observer_mode_conflict"):
        mode(seed_only=True, seed_only_context=False, continuing=True, custom_seed=True)
    with pytest.raises(
        ValueError, match="served_candidate_continuing_observer_requires_custom_seed"
    ):
        mode(seed_only=False, seed_only_context=False, continuing=True, custom_seed=False)


def test_selected_target_baseline_tracks_the_actually_acquired_slot() -> None:
    """A changed outcome does not imply a changed intervention-target baseline."""
    check = fixture._assert_selected_target_baseline_relation
    check("same", "same", acquired_slot="outcome", target_slot="intervention")
    check("before", "after", acquired_slot="target", target_slot="target")
    with pytest.raises(AssertionError):
        check("before", "after", acquired_slot="outcome", target_slot="intervention")
    with pytest.raises(AssertionError):
        check("same", "same", acquired_slot="target", target_slot="target")
    with pytest.raises(AssertionError):
        check(None, "same", acquired_slot="outcome", target_slot="intervention")


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
        read_acquisition_basis_or_decision_artifact,
        store=store,
        event_log=events,
        ref=terminal.evaluation_decision_ref,
        kind="decision",
    )
    assert type(decision) in (AcquisitionEvaluationDecision, AcquisitionEvaluationDecisionV2)
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
        capture = values["capture"]
        numerical_callable = (
            capture.selected_callable
            if hasattr(capture, "selected_callable")
            else capture.method.pure_step
        )
        oracle.monitor.watch("model_revision_native_ncm", numerical_callable)
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


def test_served_acquired_outcome_revision_replays_real_v2_basis_trio(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: Any,
) -> None:
    """A real changed outcome replays through the V2 source and numerical owners."""
    import json

    from polisyos.runtime.quality import acquisition_planner
    from polisyos.runtime.quality.acquisition_evaluation import AcquisitionEvaluationBasisV2
    from polisyos.runtime.quality.acquisition_model_transition import (
        _native_facets,
        resolve_acquired_outcome_revision,
    )
    from tests._helpers import acquisition_chain, acquisition_production, world_model_record
    from tests._helpers.annual_gdp_candidate import (
        ANNUAL_GDP_VALUE_USD,
        ANNUAL_GDP_WDI_PROFILE,
        annual_gdp_candidate_problem,
        annual_gdp_catalog_source,
        build_annual_gdp_candidate_profile,
        build_annual_gdp_candidate_provider,
    )
    from tests._helpers.candidate_holdout_resource import wdi_response_for_year
    from tests._helpers.lane01_wdi_profiles import build_fixture_wdi_authority
    from tests.integration.core_runtime.test_acquisition_retained_sequential_served import (
        _SequentialOracle,
    )

    base_payload = dict(world_model_record.FABRIC_PAYLOAD)
    base_payload.update(gdp=0.0, tax_rate=0.5)
    monkeypatch.setattr(world_model_record, "FABRIC_PAYLOAD", base_payload)
    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "global.gdp",
        {
            "basis_ref": "fixture-only:hypothetical-gdp-acquisition-input:v1",
            "collection_mode": "fixture-only annual source routing input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )
    _authority, entry = build_fixture_wdi_authority(
        tmp_path / "gdp-entry",
        ANNUAL_GDP_WDI_PROFILE,
        attempt_id=_SequentialOracle.attempt_ids[0],
        subsequent_attempt_ids=_SequentialOracle.attempt_ids[1:],
    )
    monkeypatch.setattr(acquisition_chain, "_entry", lambda: entry)

    def gdp_authority(repo_root: Path, **_kwargs: object) -> Any:
        return build_fixture_wdi_authority(
            repo_root,
            ANNUAL_GDP_WDI_PROFILE,
            attempt_id=_SequentialOracle.attempt_ids[0],
            subsequent_attempt_ids=_SequentialOracle.attempt_ids[1:],
        )

    monkeypatch.setattr(acquisition_chain, "_resolver", gdp_authority)
    monkeypatch.setattr(acquisition_production, "_COUNTRY_CODE", "USA")
    monkeypatch.setattr(acquisition_production, "_START_YEAR", 2024)
    monkeypatch.setattr(acquisition_production, "_END_YEAR", 2024)
    monkeypatch.setattr(acquisition_production, "_INDICATOR_ID", "NY.GDP.MKTP.CD")
    monkeypatch.setattr(
        acquisition_production,
        "_normalized_rows",
        lambda **_kwargs: [
            {
                "country_code": "USA",
                "country_name": "United States",
                "indicator_id": "NY.GDP.MKTP.CD",
                "indicator_name": "GDP (current US$)",
                "year": 2024,
                "value": ANNUAL_GDP_VALUE_USD,
                "unit": "",
                "decimal": 0,
            }
        ],
    )

    def gdp_raw_body(rows: list[dict[str, object]], **_kwargs: object) -> bytes:
        # The changed C value is an explicit synthetic response, not a new
        # external observation; all coordinates and units stay from the capture.
        assert len(rows) == 1
        envelope = json.loads(wdi_response_for_year(2024))
        envelope[1][0]["value"] = rows[0]["value"]
        return json.dumps(envelope, separators=(",", ":")).encode()

    monkeypatch.setattr(acquisition_production, "_raw_body", gdp_raw_body)

    observed: list[object] = []

    def check(**values: Any) -> None:
        ctx, oracle = values["ctx"], values["oracle"]
        previous = values["actual_b"]
        outcome = previous.source.problem.outcome_of_interest.target_variable
        assert outcome == "global.gdp"
        assert previous.input_record.profile.rule.target_world_slot == "global.tax_rate"
        # A controlled second response is fixture input, not an external GDP claim.
        oracle.value = float(ANNUAL_GDP_VALUE_USD + 1_000_000)
        changed = _pair(ctx, oracle, epoch=2, name="outcome-change")
        terminal = changed.receipt
        assert terminal.terminal_outcome == "reentry_completed"
        assert changed.after_calls["n5"] > changed.before_calls["n5"]
        with TestClient(ctx.app()) as client:
            control = client.app.state.runtime_container.control_service
            replay = _reopen(
                ctx,
                control,
                terminal,
                previous_run=ctx.closure.generation_run,
                previous_cycle=ctx.closure.source_cycle,
            )
            assert type(replay.decision) is AcquisitionEvaluationDecisionV2
            assert (
                previous.input_record.n5.baseline_state[outcome]
                != (replay.selected.input_record.n5.baseline_state[outcome])
            )
            revision = fixture._within_fixture_owner(
                resolve_acquired_outcome_revision, **replay.arguments
            )
            assert revision.outcome_world_slot == outcome
            from polisyos.runtime.quality import data_state_substrate

            real_world_reader = data_state_substrate.read_acquired_observation_world_semantic_values
            source_reads: list[object] = []

            def unavailable_world(**kwargs: Any) -> dict[str, object]:
                source_reads.append(kwargs["world_model_record"])
                result = real_world_reader(**kwargs)
                return {
                    **result,
                    "predicate_provenance": "not_established",
                    "reason_codes": ("test_source_owner_unavailable",),
                }

            with monkeypatch.context() as removal:
                removal.setattr(
                    data_state_substrate,
                    "read_acquired_observation_world_semantic_values",
                    unavailable_world,
                )
                with pytest.raises(
                    ValueError,
                    match=r"^acquisition_historical_basis_owner_replay_mismatch:"
                    r"test_source_owner_unavailable$",
                ):
                    fixture._within_fixture_owner(
                        resolve_acquired_outcome_revision, **replay.arguments
                    )
                assert source_reads
            assert (
                fixture._within_fixture_owner(resolve_acquired_outcome_revision, **replay.arguments)
                == revision
            )
            store, events = control._artifact_store, control._diagnostic_event_log
            bases = tuple(
                fixture._within_fixture_owner(
                    read_acquisition_basis_or_decision_artifact,
                    store=store,
                    event_log=events,
                    ref=ref,
                    kind="basis",
                )
                for ref in (
                    replay.decision.prior_basis_ref,
                    replay.decision.current_basis_ref,
                    terminal.selected_basis_ref,
                )
            )
            assert all(type(basis) is AcquisitionEvaluationBasisV2 for basis in bases)
            old, prospective, actual = map(_native_facets, bases)
            assert {"controlled_observation", "world"}.isdisjoint(old)
            assert old["foundry_state"] != actual["foundry_state"]
            assert old["declared_model"] != actual["declared_model"]
            assert old["selected_native_ncm"] != actual["selected_native_ncm"]
            assert old["n5_request_values"] != actual["n5_request_values"]
            assert all(
                prospective[name] == actual[name]
                for name in actual.keys() - {"n5_declared_implementation"}
            )
            observed.append(revision)

    _run_genuine_first_b(
        tmp_path,
        monkeypatch,
        served_recorded_candidate_gateway,
        check,
        seed_problem=annual_gdp_candidate_problem(),
        candidate_profile_builder=build_annual_gdp_candidate_profile,
        candidate_provider_builder=build_annual_gdp_candidate_provider,
        acquisition_slot="global.gdp",
        initial_source_value=float(ANNUAL_GDP_VALUE_USD),
        catalog_source_factory=annual_gdp_catalog_source,
        candidate_refresh_profile=ANNUAL_GDP_WDI_PROFILE,
        source_knob_profile="served_tax_global_scalar",
    )
    assert len(observed) == 1
