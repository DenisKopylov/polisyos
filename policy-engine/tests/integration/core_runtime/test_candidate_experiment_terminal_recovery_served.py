"""Crash recovery through the real served candidate experiment route."""

from __future__ import annotations

import copy
import hashlib
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_candidate_terminal_cas_crash_reuses_timestamp_and_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway,
) -> None:
    """A writer crash reuses its exact terminal CAS on attempt two without N5."""
    from polisyos.runtime.http.services import acquisition_surface_execution
    from polisyos.runtime.http.services.control import run_lifecycle
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentTerminalReceipt,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        complete_candidate_cycle_catalog_source,
    )
    from tests._helpers.candidate_experiment_served_execution import (
        run_candidate_experiment_served_execution,
    )
    from tests.integration.core_runtime.test_candidate_experiment_action_served import (
        _assert_candidate_experiment_n5_uses_current_wmr,
        _candidate_experiment_policy_owner,
        run_candidate_experiment_action_oracle,
    )

    monkeypatch.setenv("POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS", "3")
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "labor-source", include_owner_slot_manifest=True
    )
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="served-labor-candidate-experiment-recovery",
        total_units=5,
        protected_units=1,
    )
    crash: dict[str, object] = {"writer_calls": 0, "interrupted": False}
    observed: dict[str, object] = {}

    def serve_action(**values) -> None:
        control = values["control"]
        run_id = str(values["run_id"])
        assert values["job"].kind == "natural_language_run"
        assert values["job"].state == "completed"
        policy_owner = _candidate_experiment_policy_owner(
            control=control,
            fixture_root=tmp_path / "candidate-issuer",
            run_id=run_id,
        )
        issuer, template = policy_owner.issuer, policy_owner.template
        original_providers = control._registry_providers
        control._registry_providers = replace(
            original_providers,
            source_profiles=policy_owner.source_profiles,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(template,),
        )
        try:
            monkeypatch.setattr(
                acquisition_surface_execution,
                "build_production_world_bank_wdi_execution_port",
                lambda *, control_service: issuer.port
                if control_service is control
                else pytest.fail("candidate issuer reopened an unrelated control service"),
            )
            refs = prepare_candidate_experiment_policies_for_completed_job(
                control_service=control,
                source_job_id=values["job"].job_id,
            )
            assert len(refs) == 1
            policy_ref, policy = resolve_current_candidate_unpriced_policy(
                control_service=control,
                scope=read_candidate_unpriced_policy(
                    store=control._artifact_store,
                    event_log=control._diagnostic_event_log,
                    ref=refs[0],
                ).scope,
            )
            assert policy.observed_admission is False
            assert policy.publication_authority is False
            assert policy.information_value == policy.monetary_cost == "not_established"
            assert policy.purpose == "bounded_candidate_experiment_voi_unknown"

            def arm_terminal_writer_crash(_execution_owner, job_id: str) -> None:
                original_writer = run_lifecycle.write_runtime_authority_artifact

                def write_then_interrupt(artifact_store, event_log, payload, options, **fields):
                    result = original_writer(artifact_store, event_log, payload, options, **fields)
                    schema = options.schema
                    if (
                        options.kind == "runtime_quality.acquisition_route_loop_receipt"
                        and schema is not None
                        and schema.name
                        == "polisyos.runtime.AcquisitionCandidateExperimentTerminalReceipt"
                    ):
                        crash["writer_calls"] = int(crash["writer_calls"]) + 1
                        if not crash["interrupted"]:
                            if not isinstance(payload, dict):
                                raise AssertionError(
                                    "terminal writer payload was not canonical JSON"
                                )
                            crash["saved_ref"] = result.cas_ref
                            crash["saved_payload"] = copy.deepcopy(payload)
                            crash["job_id"] = job_id
                            crash["interrupted"] = True
                            raise KeyboardInterrupt("controlled terminal writer process crash")
                        if result.cas_ref != crash["saved_ref"]:
                            raise AssertionError("terminal retry wrote a different CAS profile")
                        if payload != crash["saved_payload"]:
                            raise AssertionError(
                                "terminal retry changed the saved terminal payload"
                            )
                    return result

                monkeypatch.setattr(
                    run_lifecycle,
                    "write_runtime_authority_artifact",
                    write_then_interrupt,
                )

            def execute_after_replay(**execution_values) -> None:
                execution = run_candidate_experiment_served_execution(
                    values=execution_values["values"],
                    origin=execution_values["origin"],
                    request=execution_values["request"],
                    decision_ref=execution_values["decision_ref"],
                    policy_owner=policy_owner,
                    monkeypatch=monkeypatch,
                    before_first_delivery=arm_terminal_writer_crash,
                    recover_worker_crash=True,
                )
                assert crash["interrupted"] is True
                assert crash["job_id"] == execution.job_id
                assert crash["writer_calls"] == 2
                assert execution.attempts == (1, 2)
                assert execution.interrupted_job is not None
                assert execution.interrupted_job.state == "running"
                assert execution.interrupted_job.attempt == 1
                assert execution.final_job.attempt == 2
                assert execution.interrupted_outcome is not None
                assert (
                    execution.interrupted_outcome.head.receipt_phase
                    == "candidate_input_reentry_pending"
                )
                assert execution.standard_invocation_units_before == 2
                assert execution.standard_invocation_units_after_interrupted == 4
                assert execution.standard_invocation_units_after == 4
                assert execution.terminal_history.frontier_after is not None
                assert type(execution.terminal_history.terminal) is (
                    AcquisitionCandidateExperimentTerminalReceipt
                )
                saved_ref = crash["saved_ref"]
                assert execution.terminal_ref == saved_ref
                assert (
                    execution.terminal_history.terminal.model_dump(mode="json")
                    == (crash["saved_payload"])
                )
                saved_generated_at = datetime.fromisoformat(
                    str(crash["saved_payload"]["generated_at"])
                )
                assert execution.terminal_history.terminal.generated_at == saved_generated_at
                assert (
                    execution.terminal_history.head.receipt_manifest_profile_sha256
                    == saved_ref.manifest_profile_sha256
                )
                assert execution.current_action.evaluation_disposition == "new"
                assert template.max_standard_n5_invocations == 4
                assert execution.execution_owner.transport_calls == [
                    (
                        "GET",
                        "https://api.worldbank.org/v2/country/USA/indicator/SL.UEM.TOTL.ZS",
                        {
                            "date": "2024:2024",
                            "format": "json",
                            "page": "1",
                            "per_page": "1000",
                        },
                    )
                ]
                _assert_candidate_experiment_n5_uses_current_wmr(
                    control=control,
                    origin=execution_values["origin"],
                    execution=execution,
                )
                terminal = execution.terminal_history.terminal
                event_id = (
                    "evt_acquisition_"
                    + str(terminal.action_generation)
                    + "_experiment_terminal_"
                    + hashlib.sha256(terminal.receipt_id.encode()).hexdigest()[:16]
                )
                rows = control._diagnostic_event_log.list_events(
                    event_id=event_id,
                    run_id=terminal.run_id,
                    job_id=terminal.job_id,
                    limit=10,
                )
                assert len(rows) == 1
                terminal_head = control._control_store.get_acquisition_action_head_by_receipt(
                    tenant_id=terminal.tenant_id,
                    cell_id=terminal.cell_id,
                    run_id=terminal.run_id,
                    source_job_id=terminal.source_job_id,
                    route_id=terminal.route_id,
                    action_generation=terminal.action_generation,
                    receipt_ref=str(execution.terminal_ref.artifact_id),
                )
                assert terminal_head is not None
                assert terminal_head.head_generation == 5
                assert (
                    terminal_head.receipt_manifest_profile_sha256
                    == execution.terminal_ref.manifest_profile_sha256
                )
                assert terminal_head.receipt_phase == "terminal"
                observed["execution"] = execution

            observed.update(
                run_candidate_experiment_action_oracle(
                    tmp_path=tmp_path,
                    values=values,
                    policy_ref=policy_ref,
                    monkeypatch=monkeypatch,
                    after_replay=execute_after_replay,
                )
            )
            assert observed["source_status"] == "completed"
        finally:
            control._registry_providers = original_providers

    with complete_candidate_cycle_catalog_source(
        source.root, monkeypatch, synthetic_usa_labor_scope=True
    ) as prepared:
        assert prepared[2].resolve(family_id="macro_state")
        result = served._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_context_observer=serve_action,
            run_budget_usd=5.0,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            candidate_acquisition_intent="bounded_experiment_voi_unknown",
            invocation_quota_policy=quota,
            labor_seed=True,
        )
    assert result is not None
    assert observed["source_status"] == "completed"
    execution = observed["execution"]
    assert execution.terminal_history.origin.generation_run.run_id == result["run_id"]
