"""Reopen an explicitly selected experiment intent from the served NL owner.

The source candidate, N4/N5, planner report and job are produced by the
existing controlled recorded gateway. The small closure adapter carries only
that job's actual identity. The issuer persists its real selected policy.
This test does not establish a permit to execute an acquisition.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.runtime.http.services.acquisition_action_service import AcquisitionActionServiceError
from polisyos.runtime.http.services.control.run_lifecycle import (
    ControlPlaneService,
    OriginalRunBudgetScopeEvidence,
)
from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
    CandidateUnpricedPolicyBinding,
    issue_candidate_unpriced_experiment_policy,
    persist_candidate_unpriced_policy,
    read_candidate_unpriced_policy,
    verify_candidate_unpriced_experiment_policy_intent,
)
from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
    prepare_candidate_experiment_policies_for_completed_job,
)
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from tests._helpers import acquisition_served_history as fixture
from tests._helpers.candidate_cycle_source_profile import (
    build_candidate_cycle_substrate_route_inputs,
    complete_candidate_cycle_catalog_source,
)
from tests._helpers.candidate_experiment_served_execution import (
    bind_candidate_test_execution_port_factory,
)
from tests.integration.core_runtime.test_candidate_experiment_action_served import (
    _candidate_experiment_policy_owner,
    run_candidate_experiment_action_oracle,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def test_served_experiment_intent_replays_original_job_and_refuses_source_removal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_recorded_candidate_gateway
) -> None:
    """A real explicit request is not inherited by foreign or missing source bytes."""
    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "scope-source", include_owner_slot_manifest=True
    )
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="fixture-explicit-budget-scope", total_units=3, protected_units=1
    )
    observed: list[str] = []

    def observe(**values: object) -> None:
        control, job, run_id = values["control"], values["job"], values["run_id"]
        closure = SimpleNamespace(
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
            run_id=run_id,
            source_job_id=job.job_id,
            source_payload_ref=job.payload_ref,
            capability_manifest_ref=job.capability_manifest_ref,
        )
        evidence = control.verify_candidate_experiment_intent(closure=closure)
        assert type(evidence) is OriginalRunBudgetScopeEvidence
        assert evidence.run_budget_scope == "metered_paid_producers_and_bounded_candidate"
        assert evidence.run_budget_usd == Decimal("5")
        assert evidence.source_payload_ref == job.payload_ref
        assert evidence.source_job_id == job.job_id and evidence.run_id == run_id
        assert evidence.candidate_acquisition_intent_present is True
        assert evidence.candidate_acquisition_intent == "bounded_experiment_voi_unknown"
        assert evidence.request_snapshot_schema == "polisyos.runtime.control_nl_request_snapshot.v5"
        assert evidence.request_content_hash.startswith("sha256:")

        # The real budget owner, not the request mode or replications, must
        # account for a selected finite N5 policy and its physical reservation.
        snapshot = control._llm_producer_settlement_store.snapshot_safe()
        profiles = tuple(
            profile
            for profile in snapshot.invocation_profiles.values()
            if profile.run_binding.run_id == run_id
            and profile.run_binding.control_job_id == job.job_id
            and profile.allocation_id == quota.allocation_id
        )
        assert len(profiles) == 1
        selected_quota = profiles[0]
        assert selected_quota.total_units == quota.total_units
        assert selected_quota.protected_units == quota.protected_units
        assert selected_quota.price_origin == "unknown"
        reservations = tuple(
            row
            for row in snapshot.invocation_reservations.values()
            if row.run_id == run_id and row.profile_digest == selected_quota.profile_digest
        )
        assert any(row.purpose == "standard" and row.status == "completed" for row in reservations)
        assert sum(row.units for row in reservations if row.purpose == "standard") <= 2

        # Produce the policy through the real issuer from the selected N7
        # report, compiler relation, source job, quota and WDI authority.
        store = control._artifact_store
        owner = _candidate_experiment_policy_owner(
            control=control, fixture_root=tmp_path / "candidate-issuer", run_id=run_id
        )
        original_providers = control._registry_providers
        control._registry_providers = replace(
            original_providers,
            source_profiles=owner.source_profiles,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(owner.template,),
        )
        try:
            bind_candidate_test_execution_port_factory(
                monkeypatch=monkeypatch,
                control_service=control,
                fixture_port=owner.issuer.port,
            )
            refs = prepare_candidate_experiment_policies_for_completed_job(
                control_service=control, source_job_id=job.job_id
            )
            assert len(refs) == 1
            policy_ref = refs[0]
            issued_policy = read_candidate_unpriced_policy(
                store=store, event_log=control._diagnostic_event_log, ref=policy_ref
            )
            policy_scope = issued_policy.scope

            def verify_signed_action_after_withdrawal(**selected: object) -> None:
                action_service = values["action_service"]
                origin = selected["origin"]
                request = selected["request"]
                decision_ref = selected["decision_ref"]
                job_id = action_service._candidate_experiment_job_id(origin, request)
                original_history = (
                    action_service._authority_provider.load_candidate_experiment_decision_history(
                        origin=origin, request=request, job_id=job_id, decision_ref=decision_ref
                    )
                )
                selected_providers = control._registry_providers
                control._registry_providers = replace(
                    selected_providers,
                    candidate_unpriced_policy_bindings=(),
                    candidate_unpriced_policy_templates=(),
                )
                try:
                    assert (
                        verify_candidate_unpriced_experiment_policy_intent(
                            control_service=control,
                            closure=closure,
                            scope=policy_scope,
                            policy_ref=policy_ref,
                            require_current=False,
                        )
                        == evidence
                    )
                    history = action_service._authority_provider.load_candidate_experiment_decision_history(
                        origin=origin, request=request, job_id=job_id, decision_ref=decision_ref
                    )
                    assert history == original_history
                    assert history.decision.outcome == "allowed"
                    assert history.current_authority == "not_revalidated"
                    with pytest.raises(
                        AcquisitionActionServiceError,
                        match="candidate_experiment_policy_not_unique",
                    ):
                        action_service.replay_candidate_experiment_authority(
                            tenant_id=fixture.TENANT,
                            cell_id=fixture.CELL,
                            run_id=run_id,
                            route_id=origin.route_id,
                            request=request,
                            job_id=job_id,
                            decision_ref=decision_ref,
                            effect_handler=lambda _invocation: pytest.fail(
                                "withdrawn policy executed an effect"
                            ),
                        )
                finally:
                    control._registry_providers = selected_providers

            signed_action = run_candidate_experiment_action_oracle(
                tmp_path=tmp_path,
                values=values,
                policy_ref=policy_ref,
                monkeypatch=monkeypatch,
                exercise_controls=False,
                after_replay=verify_signed_action_after_withdrawal,
            )
            assert signed_action["policy_ref"] == str(policy_ref.artifact_id)
            assert signed_action["source_status"] == "completed"
        finally:
            control._registry_providers = original_providers
        policy_scope = issued_policy.scope
        authorization = issued_policy.live_authorization
        limitations = (
            "acquisition_monetary_cost_not_established",
            "n5_monetary_cost_not_established",
            "per_call_usd_reservation_not_established",
            "candidate_only_no_publication_authority",
            "candidate_experiment_voi_not_established",
        )

        def write_policy(*, payload_ref: str, request_hash: str, cap: Decimal):
            policy = issue_candidate_unpriced_experiment_policy(
                scope=policy_scope,
                live_authorization=authorization,
                n5_quota_profile=selected_quota,
                source_payload_ref=payload_ref,
                request_content_hash=request_hash,
                original_metered_budget_usd=cap,
                limitations=limitations,
            )
            return persist_candidate_unpriced_policy(
                store=store, event_log=control._diagnostic_event_log, policy=policy
            )

        providers = replace(
            control._registry_providers,
            candidate_unpriced_policy_bindings=(
                CandidateUnpricedPolicyBinding(scope=policy_scope, policy_ref=policy_ref),
            ),
            candidate_unpriced_policy_templates=(),
        )
        bound = ControlPlaneService(
            cas_root=values["cas_root"],
            core_runs_root=values["cas_root"] / "runs",
            repo_root=control._repo_root,
            artifact_store=store,
            control_store=control._control_store,
            policy_resolver=control._policy_resolver,
            registry_providers=providers,
            llm_producer_settlement_store=control._llm_producer_settlement_store,
        )
        assert bound.catalog_serving_source == control.catalog_serving_source
        assert (
            verify_candidate_unpriced_experiment_policy_intent(
                control_service=bound, closure=closure, scope=policy_scope, policy_ref=policy_ref
            )
            == evidence
        )
        # The historical join reopens the selected policy and the original
        # signed source even after its current binding is withdrawn. This
        # proves no present permit to fetch or reuse the observation.
        bound._registry_providers = replace(
            providers,
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(),
        )
        assert (
            verify_candidate_unpriced_experiment_policy_intent(
                control_service=bound,
                closure=closure,
                scope=policy_scope,
                policy_ref=policy_ref,
                require_current=False,
            )
            == evidence
        )
        with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
            verify_candidate_unpriced_experiment_policy_intent(
                control_service=bound, closure=closure, scope=policy_scope, policy_ref=policy_ref
            )
        wrong_scope = policy_scope.model_copy(update={"candidate_id": "foreign-candidate"})
        with pytest.raises(ValueError, match="candidate_experiment_policy_intent_not_established"):
            verify_candidate_unpriced_experiment_policy_intent(
                control_service=bound,
                closure=closure,
                scope=wrong_scope,
                policy_ref=policy_ref,
                require_current=False,
            )
        alternate_profile = policy_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "d" * 64}
        )
        with pytest.raises((OSError, ValueError)):
            verify_candidate_unpriced_experiment_policy_intent(
                control_service=bound,
                closure=closure,
                scope=policy_scope,
                policy_ref=alternate_profile,
                require_current=False,
            )
        policy_events = bound._diagnostic_event_log.list_events

        def without_selected_policy(**kwargs):
            return [
                row
                for row in policy_events(**kwargs)
                if str(policy_ref.artifact_id) not in row.event.artifact_refs
            ]

        with monkeypatch.context() as patch:
            patch.setattr(bound._diagnostic_event_log, "list_events", without_selected_policy)
            with pytest.raises(ValueError):
                verify_candidate_unpriced_experiment_policy_intent(
                    control_service=bound,
                    closure=closure,
                    scope=policy_scope,
                    policy_ref=policy_ref,
                    require_current=False,
                )
        bound._registry_providers = providers
        for wrong in (
            {
                "payload_ref": "sha256:" + "f" * 64,
                "request_hash": evidence.request_content_hash,
                "cap": Decimal("5"),
            },
            {
                "payload_ref": job.payload_ref,
                "request_hash": "sha256:" + "e" * 64,
                "cap": Decimal("5"),
            },
            {
                "payload_ref": job.payload_ref,
                "request_hash": evidence.request_content_hash,
                "cap": Decimal("6"),
            },
        ):
            wrong_ref = write_policy(**wrong)
            bound._registry_providers = replace(
                providers,
                candidate_unpriced_policy_bindings=(
                    CandidateUnpricedPolicyBinding(scope=policy_scope, policy_ref=wrong_ref),
                ),
            )
            with pytest.raises(
                ValueError, match="candidate_experiment_policy_intent_not_established"
            ):
                verify_candidate_unpriced_experiment_policy_intent(
                    control_service=bound, closure=closure, scope=policy_scope, policy_ref=wrong_ref
                )
        bound._registry_providers = providers

        foreign = SimpleNamespace(**vars(closure))
        foreign.tenant_id = "foreign-tenant"
        with pytest.raises(ValueError, match="acquisition_source_budget_scope_not_established"):
            control.verify_candidate_experiment_intent(closure=foreign)
        foreign = SimpleNamespace(**vars(closure))
        foreign.source_payload_ref = "sha256:" + "f" * 64
        with pytest.raises(ValueError, match="acquisition_source_budget_payload_changed"):
            control.verify_candidate_experiment_intent(closure=foreign)

        artifact_id = artifacts.ArtifactID.model_validate(job.payload_ref)
        manifest_path = store._manifest_path_for_ref(artifact_id, None)
        held = manifest_path.with_name(manifest_path.name + ".scope-test-held")
        manifest_path.rename(held)
        try:
            with pytest.raises((FileNotFoundError, OSError, ValueError)):
                control.verify_candidate_experiment_intent(closure=closure)
        finally:
            held.rename(manifest_path)
        assert control.verify_candidate_experiment_intent(closure=closure) == evidence
        # Policy selection and every refusal above are read-only with respect
        # to the actual physical-work and paid-producer budget owners.
        assert control._llm_producer_settlement_store.snapshot_safe() == snapshot
        observed.append(run_id)

    with complete_candidate_cycle_catalog_source(
        source.root, monkeypatch, synthetic_usa_labor_scope=True
    ) as prepared:
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_context_observer=observe,
            run_budget_usd=5.0,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            candidate_acquisition_intent="bounded_experiment_voi_unknown",
            invocation_quota_policy=quota,
            labor_seed=True,
        )
    assert result is not None and observed == [result["run_id"]]
