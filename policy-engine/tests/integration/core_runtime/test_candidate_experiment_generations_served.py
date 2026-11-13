"""Served candidate experiments retain equivalent evaluations and advance changed bases."""

from __future__ import annotations

import sys
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import CodeType, SimpleNamespace

import pytest

pytest_plugins = ("tests._helpers.acquisition_served_history",)


@contextmanager
def _forbid_retained_generation_n5() -> Iterator[list[str]]:
    """Refuse entry to the actual N5 controller without replacing its callable."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )

    owner = JointSimulationHorizonController.run
    code = getattr(owner, "__code__", None)
    if not isinstance(code, CodeType):
        raise RuntimeError("candidate_retention_n5_owner_code_unavailable")
    monitoring = sys.monitoring
    tool_id = None
    for candidate in (3, 4):
        if monitoring.get_tool(candidate) is not None:
            continue
        try:
            monitoring.use_tool_id(candidate, "candidate-retention-n5-entry-guard")
        except ValueError:
            continue
        tool_id = candidate
        break
    if tool_id is None:
        raise RuntimeError("candidate_retention_n5_monitor_unavailable")

    entries: list[str] = []
    registered = False
    enabled = False

    def record_entry(observed: CodeType, _offset: int) -> None:
        if observed is code:
            entries.append("n5_controller")
            raise AssertionError("candidate_retention_unexpected_n5_entry")

    try:
        monitoring.clear_tool_id(tool_id)
        if monitoring.get_events(tool_id) != 0:
            raise RuntimeError("candidate_retention_n5_monitor_not_isolated")
        previous = monitoring.register_callback(tool_id, monitoring.events.PY_START, record_entry)
        registered = True
        if previous is not None:
            raise RuntimeError("candidate_retention_n5_monitor_callback_occupied")
        monitoring.set_local_events(tool_id, code, monitoring.events.PY_START)
        enabled = True
        yield entries
        assert JointSimulationHorizonController.run is owner
        assert owner.__code__ is code
    finally:
        try:
            if enabled:
                monitoring.set_local_events(tool_id, code, 0)
        finally:
            try:
                if registered:
                    monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
            finally:
                monitoring.free_tool_id(tool_id)


def test_retained_generation_n5_guard_rejects_real_controller_entry() -> None:
    """The guard trips on the actual method before its body or any numerical work."""
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
        JointSimulationRequest,
    )

    controller = JointSimulationHorizonController.__new__(JointSimulationHorizonController)
    # This is only a typed call-shape sentinel, not a valid simulation request.
    request = JointSimulationRequest.model_construct(intervention_atoms=())

    def assert_guard_refuses() -> None:
        with pytest.raises(AssertionError, match="candidate_retention_unexpected_n5_entry"):
            controller.run(request)

    with _forbid_retained_generation_n5() as entries:
        assert_guard_refuses()
    assert entries == ["n5_controller"]
    assert "_last_n5_implementation_capture" not in controller.__dict__

    # Remove the tested guard. A separate monitor stops the real producer at
    # entry so the intentionally incomplete request cannot reach its body.
    # The same assertion must now fail with the distinct removal signal.
    monitoring = sys.monitoring
    code = JointSimulationHorizonController.run.__code__
    tool_id = next((item for item in (3, 4) if monitoring.get_tool(item) is None), None)
    if tool_id is None:
        raise RuntimeError("candidate_retention_n5_control_monitor_unavailable")
    monitoring.use_tool_id(tool_id, "candidate-retention-n5-removal-control")
    registered = False
    enabled = False
    observed: list[str] = []

    def stop_removed_guard(observed_code: CodeType, _offset: int) -> None:
        if observed_code is code:
            observed.append("n5_controller")
            raise AssertionError("candidate_retention_guard_removed")

    try:
        monitoring.clear_tool_id(tool_id)
        monitoring.register_callback(tool_id, monitoring.events.PY_START, stop_removed_guard)
        registered = True
        monitoring.set_local_events(tool_id, code, monitoring.events.PY_START)
        enabled = True
        with pytest.raises(AssertionError, match="candidate_retention_guard_removed"):
            assert_guard_refuses()
    finally:
        try:
            if enabled:
                monitoring.set_local_events(tool_id, code, 0)
        finally:
            try:
                if registered:
                    monitoring.register_callback(tool_id, monitoring.events.PY_START, None)
            finally:
                monitoring.free_tool_id(tool_id)
    assert observed == ["n5_controller"]
    assert "_last_n5_implementation_capture" not in controller.__dict__


def _assert_changed_candidate_n5_numeric_outcomes(
    *, control: object, first: object, changed: object, allow_blocked: bool = False
) -> None:
    """Reopen both real N5 outputs and compare their declared numerical outcomes."""
    import json

    import numpy as np

    from polisyos.core import canon
    from polisyos.foundry.execute.executor import get_state_path, load_state_snapshot
    from polisyos.runtime.quality.candidate_acquisition_source import (
        read_candidate_acquisition_source,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationN5InputV5,
        CandidateSimulationSyntheticModelDeclarationV1,
    )
    from polisyos.runtime.quality.generation_cycle import load_joint_simulation_result
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.runtime.quality.world_model_record import world_model_artifact_views

    store = control._artifact_store
    values: list[tuple[float, float]] = []
    # The selected fixture uses float32 state input. This fixed tolerance is
    # chosen before seeing any result and is tight relative to the .035 shift.
    tolerance = 1e-7
    for execution, source_value, expected_outcome in (
        (first, 0.175, 0.177),
        (changed, 0.21, 0.212),
    ):
        history = execution.terminal_history
        evaluation = history.evaluation
        if evaluation is None and allow_blocked:
            assert history.terminal.selected_evaluation is None
            assert history.selected_basis.basis_role == "blocked"
            evaluation = history.reentry_evaluation
        assert evaluation is not None
        selected = evaluation.selected
        n5_input = CandidateSimulationN5InputV5.model_validate(
            canon.from_canonical_bytes(store.get_bytes(selected.n5_input_ref))
        )
        assert n5_input == evaluation.input_record
        assert evaluation.execution.n5_input_ref == selected.n5_input_ref
        assert evaluation.execution.n5_result_ref == selected.n5_result_ref
        declaration = CandidateSimulationSyntheticModelDeclarationV1.model_validate(
            canon.from_canonical_bytes(store.get_bytes(n5_input.model_declaration_ref))
        )
        assert declaration.target_world_slot == "government.balance"
        assert declaration.outcome_variable == "global.unemployment_rate"
        assert declaration.target_unit_id == n5_input.profile.rule.unit_id == "usd"
        assert declaration.outcome_unit_id == "ratio"
        assert declaration.outcome_per_target_unit == pytest.approx(0.001, rel=0, abs=1e-12)
        assert declaration.outcome_noise_stddev == 0.0
        assert float(n5_input.materialization.value) == pytest.approx(2.0, rel=0, abs=1e-12)
        assert history.source.observation == pytest.approx(source_value, rel=0, abs=tolerance)
        reopened_source = read_candidate_acquisition_source(
            store,
            source_ref=history.action.candidate_source_ref,
        )
        assert reopened_source == history.source
        raw_source = json.loads(store.get_bytes(reopened_source.raw_source_ref))
        assert len(raw_source) == 2 and len(raw_source[1]) == 1
        assert raw_source[1][0]["countryiso3code"] == "USA"
        assert raw_source[1][0]["date"] == "2024"
        assert raw_source[1][0]["unit"] == "percent"
        # The source fixture supplies percent; the source owner must derive the
        # canonical ratio used as the actual N5 baseline (17.5% -> .175, 21% -> .21).
        assert raw_source[1][0]["value"] == pytest.approx(source_value * 100, rel=0, abs=1e-12)
        assert reopened_source.target_slot_id == "global.unemployment_rate"
        assert reopened_source.canonical_unit == "ratio"
        reopened_declaration, ncm = GenerationSourceRepository(store).load_candidate_declared_ncm(
            declaration_ref=n5_input.model_declaration_ref,
            ncm_ref=n5_input.ncm_ref,
            expected_profile=n5_input.profile,
            expected_run_id=n5_input.run_id,
            expected_job_id=n5_input.job_id,
            expected_tenant_id=n5_input.tenant_id,
            expected_cell_id=n5_input.cell_id,
        )
        assert reopened_declaration == declaration
        assert ncm.scm_spec is not None
        outcome_mechanisms = [
            row for row in ncm.scm_spec.mechanisms if row.variable == declaration.outcome_variable
        ]
        assert len(outcome_mechanisms) == 1
        model = outcome_mechanisms[0]
        assert model.parents == [declaration.target_world_slot]
        assert model.family_params["coefficients"] == {declaration.target_world_slot: 0.001}
        assert model.family_params["intercept"] == pytest.approx(source_value, rel=0, abs=tolerance)
        assert model.family_params["noise_std"] == 0.0

        world = n5_input.profile.context_inputs.world_model_record
        state_ref = world_model_artifact_views(world).bound_state_snapshot_ref
        assert state_ref is not None and state_ref.manifest_profile_sha256 is not None
        state = load_state_snapshot(store, snapshot_ref=state_ref)
        state_values: dict[str, float] = {}
        for slot in (declaration.target_world_slot, declaration.outcome_variable):
            binding = world.slot_binding(slot)
            assert binding is not None and binding.state_path
            actual = np.asarray(get_state_path(state, binding.state_path))
            assert actual.size == 1
            state_values[slot] = float(actual.item())
        assert state_values[declaration.target_world_slot] == pytest.approx(
            0.0, rel=0, abs=tolerance
        )
        assert state_values[declaration.outcome_variable] == pytest.approx(
            source_value, rel=0, abs=tolerance
        )
        assert declaration.target_baseline == state_values[declaration.target_world_slot]
        assert declaration.outcome_baseline == state_values[declaration.outcome_variable]
        assert n5_input.n5.baseline_state == state_values

        atom_id = n5_input.materialization.derived_n5_atom.intervention_id
        result = load_joint_simulation_result(
            selected.n5_result_ref,
            store=store,
            expected_world_model_record_content_hash=selected.world_model_record_hash,
            expected_atom_ids=(atom_id,),
            expected_selected_outcomes=(declaration.outcome_variable,),
            expected_receipt_payload_hash=evaluation.execution.n5_result_content_hash,
        )
        assert result == evaluation.result
        trajectories = [
            item
            for item in result.trajectories
            if item.run_level == "joint" and item.atom_ids == (atom_id,)
        ]
        assert len(trajectories) == 1 and trajectories[0].points
        for point in trajectories[0].points:
            effect = point.effect[declaration.outcome_variable]
            outcome = point.outcomes[declaration.outcome_variable]
            assert effect == pytest.approx(0.002, rel=0, abs=tolerance)
            assert outcome == pytest.approx(expected_outcome, rel=0, abs=tolerance)
            assert point.replication_sampling is not None
            assert point.replication_sampling.replicate_count == 2
            assert len(point.replication_sampling.samples) == 2
            for sample in point.replication_sampling.samples:
                assert sample.effects[declaration.outcome_variable] == pytest.approx(
                    0.002, rel=0, abs=tolerance
                )
                assert sample.outcomes[declaration.outcome_variable] == pytest.approx(
                    expected_outcome, rel=0, abs=tolerance
                )
            values.append((source_value, outcome))

    old = [outcome for source, outcome in values if source == 0.175]
    new = [outcome for source, outcome in values if source == 0.21]
    assert old and new
    for before in old:
        for after in new:
            assert after - before == pytest.approx(0.035, rel=0, abs=tolerance)


def _continue_genuine_candidate_experiment_generations(
    *,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    observed: dict[str, object],
    constituent_controls: object,
    **first_values: object,
) -> None:
    """Continue an actual B1 terminal through the shared B2/B3/C owner checks."""
    from datetime import UTC, datetime, timedelta

    from polisyos.core import artifacts, canon
    from polisyos.runtime.http.permissions import CANDIDATE_EXPERIMENT_REUSE_PERMISSION
    from polisyos.runtime.http.services.acquisition_action_service import (
        CandidateExperimentRouteProjection,
    )
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WorldBankWDIAcquisitionExecutionPort,
    )
    from polisyos.runtime.quality.acquisition_evaluation_history import (
        verify_candidate_experiment_terminal_history,
    )
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceiptV2,
    )
    from polisyos.runtime.quality.agent_action_authority import (
        AGENT_ACTION_DECISION_ARTIFACT_KIND,
        CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
        AgentActionAuthorityDecision,
    )
    from polisyos.runtime.quality.candidate_experiment_reuse import (
        CandidateExperimentReuseActionRequest,
    )
    from polisyos.runtime.quality.joint_simulation_horizon import (
        JointSimulationHorizonController,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        _candidate_experiment_reopened_runtime,
        _standard_invocation_units,
        candidate_experiment_served_execution_owner,
        run_candidate_experiment_served_execution,
    )
    from tests._helpers.control_worker import dispatch_one_control_job
    from tests._helpers.lane01_candidate_action_served import _approve_candidate_action
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        _assert_candidate_experiment_n5_uses_current_wmr,
        _install_candidate_mandate,
        run_candidate_experiment_action_oracle,
    )

    first = first_values["execution"]
    values = first_values["values"]
    policy_ref = first_values["policy_ref"]
    policy_owner = first_values["policy_owner"]
    policy = first_values["policy"]
    origin = first_values["origin"]
    quota = first_values["quota"]

    # B1 and C are the only source attempts under the signed policy.
    # B2 and B3 have their own PA2/DS9 decisions and reuse the source from B1.
    authorized_attempt_ids = tuple(item.attempt_id for item in policy.authorized_source_attempts)
    assert len(authorized_attempt_ids) == 2
    assert len(set(authorized_attempt_ids)) == len(authorized_attempt_ids)
    assert policy.configured_template is not None
    assert policy.configured_template.subsequent_attempt_ids == authorized_attempt_ids[1:]

    assert first.standard_invocation_units_before == 2
    assert first.standard_invocation_units_after == 4
    assert quota.total_units == 7
    assert quota.protected_units == 1
    assert policy_owner.template.max_standard_n5_invocations == 6
    assert origin.policy_ref == policy_ref
    assert origin.action_authority == "not_established"
    assert policy.scope == origin.policy_scope
    assert policy.observed_admission is False
    assert policy.publication_authority is False
    assert policy.information_value == policy.monetary_cost == "not_established"

    initial_history = first.terminal_history
    initial_terminal = initial_history.terminal
    initial_evaluation = initial_terminal.selected_evaluation
    initial_current_basis = initial_history.current_basis
    initial_basis = initial_history.selected_basis
    assert initial_terminal.terminal_outcome == "candidate_reentry_completed"
    assert initial_evaluation is not None
    assert initial_current_basis is not None
    assert initial_basis is not None
    assert initial_history.source.observation == pytest.approx(0.175)
    assert initial_history.source.status == "candidate_only"
    assert initial_history.source.observation_class == "model_output"
    assert initial_history.source.source_currentness == "source_currentness_not_established"
    assert initial_current_basis.basis_role == "prospective"
    assert initial_current_basis.predicate_provenance == "recomputed"
    assert initial_current_basis.observed_admission is False
    assert initial_current_basis.publication_authority is False
    assert initial_basis.basis_role == "evaluated"
    assert initial_basis.predicate_provenance == "recomputed"
    assert initial_basis.observed_admission is False
    assert initial_basis.publication_authority is False
    assert initial_history.frontier_after is not None
    assert initial_history.reentry is not None
    assert initial_current_basis.preparation_inputs.base_world_model_ref is None
    assert initial_basis.preparation_inputs.base_world_model_ref is None
    constituent_controls.assert_selected(control=first_values["control"], history=initial_history)
    root_policy_scope = origin.policy_scope
    initial_frontier = initial_history.frontier_after
    initial_selected_evaluation = initial_evaluation

    def assert_exact_retry_and_fresh_get(
        *, action_values: dict[str, object], execution: object
    ) -> None:
        action_context = action_values["values"]
        action_origin = action_values["origin"]
        action_request = action_values["request"]
        action_decision_ref = action_values["decision_ref"]
        action_control = action_context["control"]
        action_service = action_context["action_service"]
        action_client = action_context["client"]
        action_trust = action_context["trust"]
        retry_owner_args = {
            "action_service": action_service,
            "origin": action_origin,
            "policy_owner": policy_owner,
            "monkeypatch": monkeypatch,
        }
        run_id = action_origin.run_id
        route_id = action_origin.route_id
        execute_path = f"/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute"
        execute_route = "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute"
        get_path = f"/api/v1/runs/{run_id}/candidate-acquisition-experiment"
        execute_body = {
            "request": action_request.model_dump(mode="json"),
            "decision_ref": str(action_decision_ref),
        }
        units_before = _standard_invocation_units(control=action_control, run_id=run_id)
        assert units_before == execution.standard_invocation_units_after
        budget_store = action_control._llm_producer_settlement_store
        budget_before = budget_store.snapshot_safe()

        def forbid_n5(*_args: object, **_kwargs: object) -> object:
            raise AssertionError("candidate experiment duplicate retry or GET attempted N5")

        with candidate_experiment_served_execution_owner(**retry_owner_args) as retry_owner:
            with monkeypatch.context() as no_n5:
                no_n5.setattr(JointSimulationHorizonController, "run", forbid_n5)
                retry_response, retry_digest = action_trust.post(
                    action_client,
                    execute_path,
                    execute_body,
                    route=execute_route,
                )
                assert retry_response.status_code in {200, 202}, retry_response.text
                assert retry_response.json()["job_id"] == execution.job_id
                assert retry_digest == execution.response_digest

                current_response = action_client.get(
                    get_path,
                    headers={
                        "Authorization": action_trust.authorization_header("acquisition-operator"),
                        "X-Tenant-ID": action_origin.tenant_id,
                    },
                )
                assert current_response.status_code == 200, current_response.text
                current = current_response.json()["current_action"]
                assert current["status"] == "completed"
                assert current["job_id"] == execution.job_id
                assert current["action_generation"] == (
                    execution.terminal_history.head.action_generation
                )
                assert current["receipt_phase"] == "terminal"
                assert current["terminal_outcome"] == (
                    execution.terminal_history.terminal.terminal_outcome
                )
                assert current["evaluation_disposition"] == (
                    execution.current_action.evaluation_disposition
                )
                selected_receipt = current["selected_receipt_ref"]
                assert selected_receipt["artifact_id"] == str(execution.terminal_ref.artifact_id)
                assert selected_receipt["manifest_profile_sha256"] == (
                    execution.terminal_ref.manifest_profile_sha256
                )

            assert retry_owner.transport_calls == []
        units_after = _standard_invocation_units(control=action_control, run_id=run_id)
        assert units_after == units_before
        assert budget_store.snapshot_safe() == budget_before

    control = first_values["control"]
    action_service = first_values["action_service"]
    client, trust = values["client"], values["trust"]
    action_heads_scope = {
        "tenant_id": origin.tenant_id,
        "cell_id": origin.cell_id,
        "run_id": origin.run_id,
        "source_job_id": origin.source_job_id,
    }
    reuse_route = "/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/reuse"
    reuse_path = reuse_route.format(run_id=origin.run_id, route_id=origin.route_id)
    get_path = f"/api/v1/runs/{origin.run_id}/candidate-acquisition-experiment"
    independent_failures: list[AssertionError] = []

    def assert_independently(check: Callable[[], None]) -> None:
        # An independent readback/control failure must still fail this test,
        # but it need not stop the next real producer if its head is sound.
        try:
            check()
        except AssertionError as exc:
            independent_failures.append(exc)

    assert_independently(
        lambda: assert_exact_retry_and_fresh_get(action_values=first_values, execution=first)
    )

    def reuse_request(
        *, predecessor: object, generation: int
    ) -> CandidateExperimentReuseActionRequest:
        history = predecessor.terminal_history
        terminal = history.terminal
        selected = terminal.selected_evaluation
        assert selected is not None and terminal.candidate_action_ref is not None
        return CandidateExperimentReuseActionRequest.model_validate(
            {
                "route_id": origin.route_id,
                "predecessor_terminal_ref": predecessor.terminal_ref.model_dump(mode="python"),
                "predecessor_action_ref": terminal.candidate_action_ref.model_dump(mode="python"),
                "source_ref": history.action.candidate_source_ref.model_dump(mode="python"),
                "n5_input_ref": selected.n5_input_ref.model_dump(mode="python"),
                "n5_execution_ref": selected.n5_execution_ref.model_dump(mode="python"),
                "n5_result_ref": selected.n5_result_ref.model_dump(mode="python"),
                "policy_ref": policy_ref.model_dump(mode="python"),
                "idempotency_key": f"served-labor-candidate-reuse-{generation}",
            }
        )

    def assert_fresh_reuse_get(*, history: object) -> None:
        with _candidate_experiment_reopened_runtime(
            control=control, trust=trust, monkeypatch=monkeypatch
        ) as (reader, _fresh_control, _sqlite_path, _cas_root):
            response = reader.get(
                get_path,
                headers={
                    "Authorization": trust.authorization_header("acquisition-operator"),
                    "X-Tenant-ID": origin.tenant_id,
                },
            )
            assert response.status_code == 200, response.text
            projection = CandidateExperimentRouteProjection.model_validate(response.json())
            assert projection.action_authority == "not_established"
            assert projection.publication_authority is False
            action = projection.current_action
            assert action.status == action.job_state == "completed"
            assert action.job_id == history.head.job_id
            assert action.action_generation == history.head.action_generation
            assert action.receipt_phase == "terminal"
            assert action.terminal_outcome == "candidate_evaluation_retained"
            assert action.evaluation_disposition == "retained"
            assert action.selected_receipt_ref == history.terminal_ref
            assert action.selected_evaluation == initial_selected_evaluation
            assert action.candidate_n5_result is None

    def post_fresh_reuse_execute(envelope: dict[str, object], *, subject: str):
        # A retry receives its own signed identity and normal route-bound
        # step-up, while preserving the authenticated actor subject.
        with trust.authorization_exchange(subject):
            return trust.post(
                client,
                reuse_path + "/execute",
                envelope,
                route=reuse_route + "/execute",
                subject=subject,
            )

    def run_reuse(*, generation: int, predecessor: object) -> object:
        request = reuse_request(predecessor=predecessor, generation=generation)
        authority_valid_until = datetime.now(UTC) + timedelta(minutes=90)
        body = request.model_dump(mode="json")
        heads_before = control._control_store.list_acquisition_action_heads_for_source(
            **action_heads_scope
        )
        assert len(heads_before) == generation - 1
        assert heads_before[-1] == predecessor.terminal_history.head
        ledger_store = control._llm_producer_settlement_store
        ledger_before = ledger_store.snapshot_safe()
        ledger_path = ledger_store._ledger._path
        ledger_bytes_before = ledger_path.read_bytes()
        standard_units = _standard_invocation_units(control=control, run_id=origin.run_id)
        assert standard_units == 4
        source_entries: list[str] = []

        def forbid_source(*_args: object, **_kwargs: object) -> object:
            source_entries.append("candidate_source_producer")
            raise AssertionError("same-basis reuse entered the real source producer")

        with (
            trust.authorization_exchange("acquisition-operator"),
            trust.authorization_exchange("human-reviewer-1"),
            candidate_experiment_served_execution_owner(
                action_service=action_service,
                origin=origin,
                policy_owner=policy_owner,
                monkeypatch=monkeypatch,
            ) as owner,
            _forbid_retained_generation_n5() as n5_entries,
            monkeypatch.context() as no_source,
        ):
            no_source.setattr(
                WorldBankWDIAcquisitionExecutionPort,
                "execute_candidate_experiment",
                forbid_source,
            )
            refused, resource_digest = trust.post(
                client,
                reuse_path + "/decision-request",
                body,
                route=reuse_route + "/decision-request",
            )
            assert refused.status_code == 200, refused.text
            assert refused.json()["outcome"] == "decision_required"
            refusal_ref = refused.json()["authority_decision_ref"]
            store = control._artifact_store
            manifest = store.get_manifest(refusal_ref)
            assert manifest.kind == AGENT_ACTION_DECISION_ARTIFACT_KIND
            closure = manifest.same_input_closure
            assert closure is not None
            assert (closure.tenant_id, closure.cell_id, closure.run_id) == (
                origin.tenant_id,
                origin.cell_id,
                origin.run_id,
            )
            job_id = closure.job_id
            assert job_id.startswith("candidate-experiment-reuse-")
            assert control._control_store.get_job(job_id) is None
            refusal = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(store.get_bytes(refusal_ref))
            )
            assert refusal.outcome == "refused"
            assert refusal.action_kind == CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND
            assert "delegation_contract_not_persisted" in refusal.refusal_reasons

            slot, install_provider = _install_candidate_mandate(
                control=control,
                trust=trust,
                signers=values["signers"],
                identities=values["identities"],
                origin=origin,
                action_service=action_service,
                client=client,
                request=request,
                resource_digest=resource_digest,
                tmp_path=tmp_path,
                key_root=Path(values["key_root"]),
                action_kind=CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND,
                required_permission=CANDIDATE_EXPERIMENT_REUSE_PERMISSION,
                action_job_id=job_id,
                authority_valid_until=authority_valid_until,
            )
            install_provider()
            _approve_candidate_action(
                client=client,
                control=control,
                closure=origin,
                path=reuse_path,
                template=reuse_route,
                mutation=request,
                job_id=job_id,
                slot=slot,
                cas_root=Path(values["cas_root"]),
                trust=trust,
                signers=values["signers"],
                identities=values["identities"],
                authority_valid_until=authority_valid_until,
            )
            install_provider()
            allowed, allowed_digest = trust.post(
                client,
                reuse_path + "/decision-request",
                body,
                route=reuse_route + "/decision-request",
            )
            assert allowed.status_code == 200, allowed.text
            assert allowed_digest == resource_digest
            assert allowed.json()["outcome"] == "decision_available", allowed.text
            decision_ref = allowed.json()["authority_decision_ref"]
            decision = AgentActionAuthorityDecision.model_validate(
                canon.from_canonical_bytes(store.get_bytes(decision_ref))
            )
            assert decision.outcome == "allowed"
            assert decision.action_kind == CANDIDATE_EXPERIMENT_REUSE_ACTION_KIND
            assert decision.human_decision_record_ref == slot["human_decision_record_ref"]
            assert decision.permission_snapshot is not None
            assert decision.permission_snapshot.required_permission == "runs.launch"
            assert control._control_store.get_job(job_id) is None
            assert (
                control._control_store.list_acquisition_action_heads_for_source(
                    **action_heads_scope
                )
                == heads_before
            )

            execute_envelope = {"request": body, "decision_ref": decision_ref}
            execute, _ = trust.post(
                client,
                reuse_path + "/execute",
                execute_envelope,
                route=reuse_route + "/execute",
            )
            assert execute.status_code in {200, 202}, execute.text
            assert execute.json()["job_id"] == job_id
            assert execute.json()["authority_decision_ref"] == str(decision_ref)
            assert execute.json()["status"] == "accepted"
            assert execute.json()["receipt_phase"] == "requested"
            pending_job = control._control_store.get_job(job_id)
            pending_head = control._control_store.get_acquisition_action_head(
                **action_heads_scope, route_id=origin.route_id, action_generation=generation
            )
            pending_heads = control._control_store.list_acquisition_action_heads_for_source(
                **action_heads_scope
            )
            assert pending_job is not None and pending_head is not None
            pending_retry, _ = post_fresh_reuse_execute(
                execute_envelope,
                subject="acquisition-operator",
            )
            assert pending_retry.status_code in {200, 202}, pending_retry.text
            assert pending_retry.json()["job_id"] == job_id
            assert pending_retry.json()["authority_decision_ref"] == str(decision_ref)
            assert pending_retry.json()["status"] == "accepted"
            assert pending_retry.json()["receipt_phase"] == "requested"
            assert control._control_store.get_job(job_id) == pending_job
            assert (
                control._control_store.get_acquisition_action_head(
                    **action_heads_scope, route_id=origin.route_id, action_generation=generation
                )
                == pending_head
            )
            assert (
                control._control_store.list_acquisition_action_heads_for_source(
                    **action_heads_scope
                )
                == pending_heads
            )
            assert (
                dispatch_one_control_job(
                    store=control._control_store,
                    handler=control._process_control_job,
                    expected_job_id=job_id,
                )
                == job_id
            )
            job = control._control_store.get_job(job_id)
            assert job is not None and job.state == "completed", job
            assert job.attempt == 1
            head = control._control_store.get_acquisition_action_head(
                **action_heads_scope, route_id=origin.route_id, action_generation=generation
            )
            assert head is not None and head.job_id == job_id
            assert head.receipt_phase == "terminal"
            assert head.receipt_manifest_profile_sha256 is not None
            terminal_ref = artifacts.ArtifactRef(
                artifact_id=artifacts.ArtifactID.model_validate(head.receipt_ref),
                kind="runtime_quality.acquisition_route_loop_receipt",
                media_type="application/json",
                manifest_profile_sha256=head.receipt_manifest_profile_sha256,
            )
            history = verify_candidate_experiment_terminal_history(
                control_service=control, head=head, terminal_ref=terminal_ref
            )
            assert type(history.terminal) is AcquisitionCandidateExperimentTerminalReceiptV2
            assert history.terminal.terminal_outcome == "candidate_evaluation_retained"
            occurrence = history.reuse_occurrence
            assert occurrence is not None
            assert occurrence.selection.request == request
            assert occurrence.selection.action_job_id == job_id
            assert occurrence.selection.action_generation == generation
            assert occurrence.selection.predecessor_action_generation == generation - 1
            assert occurrence.selection.predecessor_terminal_ref == predecessor.terminal_ref
            assert occurrence.pa2_decision_ref == artifacts.artifact_ref_for_manifest(
                store.get_manifest(decision_ref)
            )
            completed_job = control._control_store.get_job(job_id)
            completed_heads = control._control_store.list_acquisition_action_heads_for_source(
                **action_heads_scope
            )
            completed_retry, _ = post_fresh_reuse_execute(
                execute_envelope,
                subject="acquisition-operator",
            )
            assert completed_retry.status_code in {200, 202}, completed_retry.text
            assert completed_retry.json()["job_id"] == job_id
            assert completed_retry.json()["authority_decision_ref"] == str(decision_ref)
            assert completed_retry.json()["status"] == "completed"
            assert completed_retry.json()["receipt_phase"] == "terminal"
            assert control._control_store.get_job(job_id) == completed_job
            assert (
                control._control_store.get_acquisition_action_head(
                    **action_heads_scope, route_id=origin.route_id, action_generation=generation
                )
                == head
            )
            assert (
                control._control_store.list_acquisition_action_heads_for_source(
                    **action_heads_scope
                )
                == completed_heads
            )
            assert occurrence.source_currentness == "source_currentness_not_established"
            assert occurrence.observed_data_authority is False
            assert occurrence.publication_authority is False
            phase = next(
                item for item in history.phase_chain if item.receipt.receipt_phase == "executing"
            )
            assert phase.receipt.job_id == job_id
            assert phase.receipt.action_generation == generation
            phase_head = control._control_store.get_acquisition_action_head_by_receipt(
                **action_heads_scope,
                route_id=origin.route_id,
                action_generation=generation,
                receipt_ref=phase.receipt_ref,
            )
            assert phase_head is not None
            assert occurrence.executing_phase_ref == artifacts.ArtifactRef(
                artifact_id=artifacts.ArtifactID.model_validate(phase.receipt_ref),
                kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
                media_type="application/json",
                manifest_profile_sha256=phase_head.receipt_manifest_profile_sha256,
            )
            assert history.budget_window is None
            assert history.reentry is None
            assert history.action == initial_history.action
            assert history.source == initial_history.source
            assert history.terminal.selected_evaluation == initial_selected_evaluation

            # A changed request body and a different signed decision must
            # fail against this durable job without replacing its terminal.
            changed_body = CandidateExperimentReuseActionRequest.model_validate(
                {
                    **request.model_dump(mode="python"),
                    "idempotency_key": request.idempotency_key + "-tampered",
                }
            )
            mismatch_snapshot = (
                control._control_store.get_job(job_id),
                control._control_store.list_acquisition_action_heads_for_source(
                    **action_heads_scope
                ),
                ledger_store.snapshot_safe(),
                ledger_path.read_bytes(),
                _standard_invocation_units(control=control, run_id=origin.run_id),
            )
            for altered, altered_decision_ref in (
                (request, refusal_ref),
                (changed_body, decision_ref),
            ):
                refused_retry, _ = post_fresh_reuse_execute(
                    {
                        "request": altered.model_dump(mode="json"),
                        "decision_ref": str(altered_decision_ref),
                    },
                    subject="acquisition-operator",
                )
                assert refused_retry.status_code == 409, refused_retry.text
                assert refused_retry.json()["code"] == (
                    "candidate_experiment_reuse_retry_payload_mismatch"
                )
                assert (
                    control._control_store.get_job(job_id),
                    control._control_store.list_acquisition_action_heads_for_source(
                        **action_heads_scope
                    ),
                    ledger_store.snapshot_safe(),
                    ledger_path.read_bytes(),
                    _standard_invocation_units(control=control, run_id=origin.run_id),
                ) == mismatch_snapshot
            assert_independently(lambda: assert_fresh_reuse_get(history=history))
            assert owner.transport_calls == []

        assert source_entries == []
        assert n5_entries == []
        assert ledger_store.snapshot_safe() == ledger_before
        assert ledger_path.read_bytes() == ledger_bytes_before
        return SimpleNamespace(
            job_id=job_id,
            terminal_history=history,
            terminal_ref=terminal_ref,
            standard_invocation_units_before=standard_units,
            standard_invocation_units_after=_standard_invocation_units(
                control=control, run_id=origin.run_id
            ),
        )

    def assert_wrong_reuse_refused(*, predecessor: object) -> None:
        # A still-valid old B1 terminal cannot replace the selected B2
        # head. Nor can a different genuine N5 result from the A cycle.
        stale = reuse_request(predecessor=first, generation=3)
        current = reuse_request(predecessor=predecessor, generation=3)
        a_result = origin.effective_source_cycle.simulation.simulation_result_ref
        assert a_result is not None and a_result != current.n5_result_ref
        foreign = CandidateExperimentReuseActionRequest.model_validate(
            {
                **current.model_dump(mode="python"),
                "n5_result_ref": a_result.model_dump(mode="python"),
            }
        )
        heads_before = control._control_store.list_acquisition_action_heads_for_source(
            **action_heads_scope
        )
        with trust.authorization_exchange("acquisition-operator"):
            for request, expected_codes in (
                (
                    stale,
                    {
                        "candidate_experiment_reuse_predecessor_not_current",
                        "candidate_experiment_reuse_predecessor_not_latest_verified",
                        "candidate_experiment_reuse_predecessor_not_current_control_head",
                    },
                ),
                (foreign, {"candidate_experiment_reuse_predecessor_pins_mismatch"}),
            ):
                denied, _ = trust.post(
                    client,
                    reuse_path + "/decision-request",
                    request.model_dump(mode="json"),
                    route=reuse_route + "/decision-request",
                )
                assert denied.status_code == 409, denied.text
                assert denied.json()["code"] in expected_codes
        assert (
            control._control_store.list_acquisition_action_heads_for_source(**action_heads_scope)
            == heads_before
        )

    def assert_withdrawn_source_refused(*, action_values: dict[str, object]) -> None:
        action_origin = action_values["origin"]
        action_request = action_values["request"]
        action_decision_ref = action_values["decision_ref"]
        providers = control._registry_providers
        assert providers.candidate_unpriced_policy_templates == (policy_owner.template,)
        heads_before = control._control_store.list_acquisition_action_heads_for_source(
            **action_heads_scope
        )
        assert len(heads_before) == 3
        job_id = action_service._candidate_experiment_job_id(action_origin, action_request)
        assert control._control_store.get_job(job_id) is None
        path = (
            f"/api/v1/runs/{origin.run_id}/candidate-acquisition-experiment/"
            f"{origin.route_id}/execute"
        )
        units = _standard_invocation_units(control=control, run_id=origin.run_id)
        with monkeypatch.context() as withdrawal, _forbid_retained_generation_n5() as entries:
            withdrawal.setattr(
                control,
                "_registry_providers",
                replace(providers, candidate_unpriced_policy_templates=()),
            )
            denied, _ = trust.post(
                client,
                path,
                {
                    "request": action_request.model_dump(mode="json"),
                    "decision_ref": str(action_decision_ref),
                },
                route="/api/v1/runs/{run_id}/candidate-acquisition-experiment/{route_id}/execute",
            )
            assert denied.status_code == 409, denied.text
            assert denied.json()["code"] == "candidate_experiment_policy_not_unique"
        assert entries == []
        assert control._control_store.get_job(job_id) is None
        assert (
            control._control_store.list_acquisition_action_heads_for_source(**action_heads_scope)
            == heads_before
        )
        assert _standard_invocation_units(control=control, run_id=origin.run_id) == units

    def run_changed_source() -> object:
        result: dict[str, object] = {}
        authority_valid_until = datetime.now(UTC) + timedelta(minutes=90)

        def execute_after_replay(**action_values: object) -> None:
            assert_independently(
                lambda: assert_withdrawn_source_refused(action_values=action_values)
            )
            # Reopen the real current source and evaluation owners before
            # C's source request and second numerical N5. This is a dry
            # port preflight: it validates the exact changed-generation
            # route without reserving a lease, fetching bytes, or running N5.
            c_origin = action_values["origin"]
            c_values = action_values["values"]
            assert len(c_origin.candidate_terminal_history_chain) == 3
            assert tuple(
                item.head.action_generation for item in c_origin.candidate_terminal_history_chain
            ) == (1, 2, 3)
            assert (
                _standard_invocation_units(control=c_values["control"], run_id=c_origin.run_id) == 4
            )
            with (
                candidate_experiment_served_execution_owner(
                    action_service=c_values["action_service"],
                    origin=c_origin,
                    policy_owner=policy_owner,
                    monkeypatch=monkeypatch,
                    wdi_response_value=21.0,
                ) as c_preflight,
                _forbid_retained_generation_n5() as c_preflight_n5,
            ):
                selected_route = c_preflight.port.preflight_candidate_experiment(origin=c_origin)
                assert selected_route == c_preflight.selection
                assert selected_route.candidate_digest == c_origin.policy_scope.candidate_digest
                assert (
                    selected_route.tenant_id,
                    selected_route.cell_id,
                    selected_route.run_id,
                    selected_route.route_id,
                    selected_route.target_slot_id,
                    selected_route.country_code,
                    selected_route.year,
                    selected_route.population,
                ) == (
                    c_origin.tenant_id,
                    c_origin.cell_id,
                    c_origin.run_id,
                    c_origin.route_id,
                    "global.unemployment_rate",
                    "USA",
                    2024,
                    "total_labor_force",
                )
                assert c_preflight.transport_calls == []
                assert c_preflight.execution_calls == []
                assert c_preflight_n5 == []
            execution = run_candidate_experiment_served_execution(
                values=action_values["values"],
                origin=action_values["origin"],
                request=action_values["request"],
                decision_ref=action_values["decision_ref"],
                policy_owner=policy_owner,
                monkeypatch=monkeypatch,
                wdi_response_value=21.0,
            )
            assert_independently(
                lambda: assert_exact_retry_and_fresh_get(
                    action_values=action_values,
                    execution=execution,
                )
            )
            result["execution"] = execution

        action_result = run_candidate_experiment_action_oracle(
            tmp_path=tmp_path / "candidate-generation-4",
            values=values,
            policy_ref=policy_ref,
            monkeypatch=monkeypatch,
            idempotency_key="served-labor-candidate-experiment-generation-4",
            exercise_controls=False,
            after_replay=execute_after_replay,
            authority_valid_until=authority_valid_until,
        )
        assert action_result["policy_ref"] == str(policy_ref.artifact_id)
        return result["execution"]

    b1 = first
    b2 = run_reuse(generation=2, predecessor=b1)
    assert_independently(lambda: assert_wrong_reuse_refused(predecessor=b2))
    b3 = run_reuse(generation=3, predecessor=b2)
    changed = run_changed_source()
    executions = (b1, b2, b3, changed)
    changed_history = changed.terminal_history
    changed_terminal = changed_history.terminal
    changed_current_basis = changed_history.current_basis
    changed_basis = changed_history.selected_basis
    assert changed.standard_invocation_units_before == 4
    assert changed.standard_invocation_units_after == 6
    assert len(changed.execution_owner.execution_calls) == 1
    assert changed.execution_owner.execution_calls[0].exception_chain is None
    assert_independently(
        lambda: _assert_changed_candidate_n5_numeric_outcomes(
            control=control, first=first, changed=changed, allow_blocked=True
        )
    )
    # Report a failed current selection after testing the actual outputs.
    if changed_basis is None or changed_basis.basis_role != "evaluated":
        reasons = changed_basis.reason_codes if changed_basis is not None else ()
        raise ExceptionGroup(
            "Changed source produced no selected evaluated basis",
            [*independent_failures, AssertionError(f"C basis blockers: {reasons}")],
        )

    # A later frontier advance must not invalidate the immutable history of
    # an earlier committed terminal. The last terminal still has to match
    # the live selected frontier.
    for execution in executions:
        reopened = verify_candidate_experiment_terminal_history(
            control_service=control,
            head=execution.terminal_history.head,
            terminal_ref=execution.terminal_ref,
        )
        assert reopened.frontier_after == execution.terminal_history.frontier_after

    latest = changed
    latest_frontier = latest.terminal_history.frontier_after
    assert latest_frontier is not None
    read_frontier = control._control_store.read_acquisition_evaluation_frontier

    def read_stale_frontier(key: object) -> object:
        if key == latest_frontier.key:
            return initial_frontier
        return read_frontier(key)

    with monkeypatch.context() as stale_current:
        stale_current.setattr(
            control._control_store,
            "read_acquisition_evaluation_frontier",
            read_stale_frontier,
        )
        with pytest.raises(
            ValueError,
            match="candidate_experiment_terminal_frontier_after_mismatch",
        ):
            verify_candidate_experiment_terminal_history(
                control_service=control,
                head=latest.terminal_history.head,
                terminal_ref=latest.terminal_ref,
            )

    foreign_frontier = replace(
        latest_frontier,
        key=replace(latest_frontier.key, candidate_id="foreign-candidate"),
    )

    def read_foreign_frontier(key: object) -> object:
        if key == latest_frontier.key:
            return foreign_frontier
        return read_frontier(key)

    with monkeypatch.context() as foreign_current:
        foreign_current.setattr(
            control._control_store,
            "read_acquisition_evaluation_frontier",
            read_foreign_frontier,
        )
        with pytest.raises(
            ValueError,
            match="candidate_experiment_terminal_frontier_after_mismatch",
        ):
            verify_candidate_experiment_terminal_history(
                control_service=control,
                head=latest.terminal_history.head,
                terminal_ref=latest.terminal_ref,
            )

    assert tuple(item.terminal_history.head.action_generation for item in executions) == (
        1,
        2,
        3,
        4,
    )
    assert (
        b1.terminal_history.action.attempt_id,
        changed.terminal_history.action.attempt_id,
    ) == authorized_attempt_ids
    assert (
        len(b1.execution_owner.transport_calls) == len(changed.execution_owner.transport_calls) == 1
    )
    assert len({item.job_id for item in executions}) == len(executions)
    assert len(
        {artifacts.artifact_ref_identity_key(item.terminal_ref) for item in executions}
    ) == len(executions)
    assert b1.standard_invocation_units_before == 2
    assert b1.standard_invocation_units_after == 4
    assert b2.standard_invocation_units_before == 4
    assert b2.standard_invocation_units_after == 4
    assert b3.standard_invocation_units_before == 4
    assert b3.standard_invocation_units_after == 4

    # Each later request is based on the exact ordered history and current source.
    for prior_count, execution in enumerate(executions[1:], start=1):
        current_origin = execution.terminal_history.origin
        current_chain = current_origin.candidate_terminal_history_chain
        assert tuple(item.head.action_generation for item in current_chain) == tuple(
            range(1, prior_count + 1)
        )
        assert len(current_chain) == prior_count
        assert current_origin.source_attempt_prefix == authorized_attempt_ids[:1]
        assert execution.terminal_history.action.attempt_id == (
            authorized_attempt_ids[1] if execution is changed else authorized_attempt_ids[0]
        )
        for prior_execution, current_history in zip(
            executions[:prior_count], current_chain, strict=True
        ):
            prior_history = prior_execution.terminal_history
            assert current_history.head == prior_history.head
            assert current_history.terminal_ref == prior_history.terminal_ref
            assert current_history.terminal == prior_history.terminal
            assert current_history.frontier_after == prior_history.frontier_after
        assert current_origin.policy_scope == root_policy_scope
        assert current_origin.policy_ref == policy_ref
        assert current_origin.action_authority == "not_established"
        assert execution.terminal_history.current_basis is not None
        preparation = execution.terminal_history.current_basis.preparation_inputs
        if execution is changed:
            assert preparation.base_world_model_ref == initial_history.reentry.world_model_ref
        else:
            assert preparation == initial_basis.preparation_inputs
        assert execution.terminal_history.source.status == "candidate_only"
        assert execution.terminal_history.source.observation_class == "model_output"
        assert (
            execution.terminal_history.source.source_currentness
            == "source_currentness_not_established"
        )
        assert current_origin.effective_generation_run == (
            initial_history.reentry.continued_generation_run
        )
        assert current_origin.effective_source_cycle == initial_history.reentry.new_cycle

    # B2/B3 recompute current cheap consequences while retaining the
    # exact prior N5 witness and atomically advancing the selected frontier.
    retained_frontiers = []
    retained_continuations = []
    retained_n5_refs = []
    for index, execution in enumerate((b2, b3), start=1):
        history = execution.terminal_history
        terminal = history.terminal
        basis = history.current_basis
        selected_basis = history.selected_basis
        continuation = history.continuation
        assert terminal.terminal_outcome == "candidate_evaluation_retained"
        assert history.decision is not None
        assert history.decision.comparison_result == "equivalent"
        assert history.decision.predicate_provenance == "recomputed"
        assert history.decision.observed_admission is False
        assert history.decision.publication_authority is False
        assert history.reentry is None
        assert basis is not None
        assert basis.basis_role == "prospective"
        assert basis.predicate_provenance == "recomputed"
        assert basis.effective_values_sha256 == initial_basis.effective_values_sha256
        assert basis.observed_admission is False
        assert basis.publication_authority is False
        assert selected_basis == initial_basis
        assert terminal.selected_evaluation == initial_selected_evaluation
        assert terminal.selected_evaluation is not None
        retained_n5_refs.append(
            (
                terminal.selected_evaluation.n5_input_ref,
                terminal.selected_evaluation.n5_execution_ref,
                terminal.selected_evaluation.n5_result_ref,
            )
        )
        assert terminal.selected_evaluation_witness_ref == (
            initial_terminal.selected_evaluation_witness_ref
        )
        assert terminal.current_continuation_ref is not None
        assert continuation is not None
        assert continuation.action_generation == index + 1
        assert continuation.action_job_id == execution.job_id
        assert continuation.retained_evaluation == initial_selected_evaluation
        assert continuation.predicate_provenance == "recomputed"
        assert continuation.observed_admission is False
        assert continuation.publication_authority is False
        assert history.source.observation == initial_history.source.observation
        assert history.frontier_before is not None
        assert history.frontier_after is not None
        assert history.frontier_after.revision == history.frontier_before.revision + 1
        assert history.frontier_after.selected_evaluation_witness_ref == (
            initial_frontier.selected_evaluation_witness_ref
        )
        retained_frontiers.append(history.frontier_after)
        retained_continuations.append(terminal.current_continuation_ref)

    assert b2.terminal_history.frontier_before == initial_frontier
    assert b3.terminal_history.frontier_before == retained_frontiers[0]
    assert retained_frontiers[0].frontier_ref != retained_frontiers[1].frontier_ref
    assert retained_continuations[0] != retained_continuations[1]
    assert (
        retained_n5_refs[0]
        == retained_n5_refs[1]
        == (
            initial_selected_evaluation.n5_input_ref,
            initial_selected_evaluation.n5_execution_ref,
            initial_selected_evaluation.n5_result_ref,
        )
    )
    b2_occurrence = b2.terminal_history.reuse_occurrence
    b3_occurrence = b3.terminal_history.reuse_occurrence
    assert b2_occurrence is not None and b3_occurrence is not None
    assert b2_occurrence.pa2_decision_ref != b3_occurrence.pa2_decision_ref
    assert b2_occurrence.executing_phase_ref != b3_occurrence.executing_phase_ref
    assert b2_occurrence.control_payload_ref != b3_occurrence.control_payload_ref
    assert b2.terminal_history.terminal.reuse_occurrence_ref != (
        b3.terminal_history.terminal.reuse_occurrence_ref
    )

    # C changes the actual WDI observation, so it must produce a new basis,
    # N5 witness, and model transition instead of retaining the old result.
    assert changed_history.decision is not None
    assert changed_history.decision.comparison_result == "different"
    assert changed_history.decision.predicate_provenance == "recomputed"
    assert changed_history.decision.observed_admission is False
    assert changed_history.decision.publication_authority is False
    assert changed_current_basis is not None
    assert changed_current_basis.basis_role == "prospective"
    assert changed_current_basis.observed_admission is False
    assert changed_current_basis.publication_authority is False
    assert changed_current_basis.effective_values_sha256 != (initial_basis.effective_values_sha256)
    assert changed_basis.predicate_provenance == "recomputed"
    assert changed_basis.effective_values_sha256 != initial_basis.effective_values_sha256
    assert changed_history.source.observation == pytest.approx(0.21)
    assert changed_history.source.observation != initial_history.source.observation
    # The existing B oracle expects the immediate source run/cycle. Supply
    # the owner-derived effective B view for C without manufacturing a new
    # authority-bearing origin.
    current_origin = changed_history.origin
    predecessor_run = current_origin.effective_generation_run
    preceding_view = SimpleNamespace(
        run_id=current_origin.run_id,
        source_job_id=current_origin.source_job_id,
        generation_run=predecessor_run,
        source_cycle=predecessor_run.cycles[-1],
    )
    _assert_candidate_experiment_n5_uses_current_wmr(
        control=control, origin=preceding_view, execution=changed
    )
    assert changed_basis.selected_data_snapshot_ref != initial_basis.selected_data_snapshot_ref
    assert changed_basis.selected_world_model_ref != initial_basis.selected_world_model_ref
    assert changed_basis.selected_data_snapshot_ref is not None
    assert changed_basis.selected_world_model_ref is not None
    assert changed_basis.observed_admission is False
    assert changed_basis.publication_authority is False
    assert changed_terminal.terminal_outcome == "candidate_reentry_completed"
    assert changed_terminal.current_continuation_ref is None
    assert changed_history.reentry is not None
    transition = changed_history.reentry.basis_transition
    assert transition.to_cycle_index == transition.from_cycle_index + 1
    assert artifacts.artifact_ref_identity_key(
        transition.data_snapshot_ref
    ) == artifacts.artifact_ref_identity_key(changed_basis.selected_data_snapshot_ref)
    assert artifacts.artifact_ref_identity_key(
        transition.world_model_ref
    ) == artifacts.artifact_ref_identity_key(changed_basis.selected_world_model_ref)
    assert changed_terminal.selected_evaluation is not None
    for actual, selected in (
        (transition.n5_input_ref, changed_terminal.selected_evaluation.n5_input_ref),
        (transition.n5_execution_ref, changed_terminal.selected_evaluation.n5_execution_ref),
        (transition.n5_result_ref, changed_terminal.selected_evaluation.n5_result_ref),
    ):
        assert actual is not None
        assert artifacts.artifact_ref_identity_key(actual) == artifacts.artifact_ref_identity_key(
            selected
        )
    assert changed_terminal.selected_evaluation.n5_input_ref != (
        initial_selected_evaluation.n5_input_ref
    )
    assert changed_terminal.selected_evaluation.n5_execution_ref != (
        initial_selected_evaluation.n5_execution_ref
    )
    assert changed_terminal.selected_evaluation.n5_result_ref != (
        initial_selected_evaluation.n5_result_ref
    )
    assert changed_terminal.selected_evaluation.world_model_record_hash != (
        initial_selected_evaluation.world_model_record_hash
    )
    assert changed_history.frontier_before == retained_frontiers[-1]
    assert changed_history.frontier_after is not None
    assert changed_history.frontier_after.revision == (changed_history.frontier_before.revision + 1)
    assert changed_history.frontier_after.selected_evaluation_witness_ref == str(
        changed_terminal.selected_evaluation_witness_ref.artifact_id
    )
    assert changed.current_action.evaluation_disposition == "new"
    assert changed.current_action.selected_receipt_ref is not None
    assert changed.current_action.selected_receipt_ref.manifest_profile_sha256
    assert changed.current_action.selected_receipt_ref == changed.terminal_ref
    assert len(changed.execution_owner.transport_calls) == 1

    snapshot = control._llm_producer_settlement_store.snapshot_safe()
    profile = snapshot.invocation_profiles[origin.run_id]
    standard_units = sum(
        row.units
        for row in snapshot.invocation_reservations.values()
        if row.run_id == origin.run_id
        and row.profile_digest == profile.profile_digest
        and row.purpose == "standard"
    )
    protected_used = sum(
        row.units
        for row in snapshot.invocation_reservations.values()
        if row.run_id == origin.run_id
        and row.profile_digest == profile.profile_digest
        and row.purpose in {"diagnostic", "counterevidence"}
    )
    standard_remaining = profile.total_units - profile.protected_units - standard_units
    protected_remaining = profile.protected_units - protected_used
    assert profile.total_units == 7
    assert profile.protected_units == 1
    assert standard_units == 6
    assert standard_remaining == 0
    assert protected_used == 0
    assert protected_remaining == 1

    if independent_failures:
        raise ExceptionGroup(
            "Independent candidate experiment controls failed", independent_failures
        )
    observed["executions"] = executions
    observed["policy_scope"] = root_policy_scope


def test_genuine_candidate_experiment_generations_retain_then_advance_frontier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway,
) -> None:
    """Run A→B→B→B→C through fresh signed decisions and the real served worker."""
    import os
    from datetime import UTC, datetime, timedelta

    from tests._helpers.acquisition_constituent_controls import (
        install_first_candidate_experiment_constituent_controls,
    )
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        run_genuine_candidate_experiment_scenario,
    )

    initial_a_observer = None
    if os.environ.get("POLISYOS_TEST_REQUIRE_LIVE_N5_INITIAL_A") == "1":
        from polisyos.runtime.quality.confidence_ledger import _retained_n5_host_capture

        if _retained_n5_host_capture() is None:
            raise RuntimeError("live_initial_n5_profile_requires_authority_launcher")
        from tests.integration.runtime_quality.test_n5_implementation_witness import (
            assert_live_initial_a_capture,
        )

        initial_a_observer = assert_live_initial_a_capture

    observed: dict[str, object] = {}
    constituent_controls = install_first_candidate_experiment_constituent_controls(monkeypatch)

    def after_first_execution(**first_values: object) -> None:
        _continue_genuine_candidate_experiment_generations(
            tmp_path=tmp_path,
            monkeypatch=monkeypatch,
            observed=observed,
            constituent_controls=constituent_controls,
            **first_values,
        )

    scenario = run_genuine_candidate_experiment_scenario(
        tmp_path=tmp_path,
        monkeypatch=monkeypatch,
        gateway=served_recorded_candidate_gateway,
        total_units=7,
        subsequent_attempt_ids=("lane01-generation-c",),
        after_execution=after_first_execution,
        authority_valid_until=lambda: datetime.now(UTC) + timedelta(minutes=90),
        before_action_observer=initial_a_observer,
    )
    assert scenario["source_status"] == "completed"
    assert len(observed["executions"]) == 4
