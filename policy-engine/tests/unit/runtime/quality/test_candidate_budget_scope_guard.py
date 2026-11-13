"""No-effect controls for the candidate budget-scope preflight boundary.

The route, Control service, CAS and database use existing real fixture owners;
the returned scope is adapted to isolate this guard.  Signed source-request
scope and a protected action must be established by their separate tests.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.data_forge.domains.catalog.knowledge.acquisition_authority import (
    AcquisitionAuthorityRegistry,
)
from polisyos.runtime.http.services import acquisition_surface_execution
from polisyos.runtime.http.services.control.run_lifecycle import (
    ControlPlaneService,
    OriginalRunBudgetScopeEvidence,
    _read_original_run_budget_scope_historical,
    _require_candidate_experiment_intent_historical,
    _require_candidate_unpriced_budget_scope_historical,
)
from polisyos.runtime.quality import acquisition_executor, candidate_acquisition_action
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
)
from polisyos.runtime.quality.generation_cycle import JointSimulationPort
from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
from tests.unit.runtime.quality.test_candidate_evaluation_reentry_owner import (
    _real_reentry_refusal_case,
    _state,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("hard_total_usd", "candidate_source_reentry_hard_total_usd_not_established"),
        (None, "candidate_source_reentry_budget_scope_not_established"),
    ],
)
async def test_explicit_hard_or_null_scope_refuses_before_candidate_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str | None, message: str
) -> None:
    """The bridge stops before query, source reservation, transport, or N5."""
    async with _real_reentry_refusal_case(tmp_path, monkeypatch) as case:
        bridge, closure = case.owner.bridge, case.closure
        bridge.cycle_substrate_context_admission_owner = (
            ConfiguredCandidateSimulationContextAdmissionOwner(
                profiles=(), store=bridge.artifact_store
            )
        )
        bridge.promotion_runtime = SimpleNamespace(store=bridge.artifact_store)
        monkeypatch.setattr(bridge, "candidate_source_selection", lambda _closure: object())
        evidence = OriginalRunBudgetScopeEvidence(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            source_payload_ref=closure.source_payload_ref,
            run_budget_usd=Decimal("5"),
            scope_explicit=True,
            run_budget_scope=mode,
            request_snapshot_schema="polisyos.runtime.control_nl_request_snapshot.v4",
            request_content_hash="sha256:" + "a" * 64,
        )
        monkeypatch.setattr(
            ControlPlaneService, "read_original_run_budget_scope", lambda *_args, **_kw: evidence
        )

        def forbidden(*_args: object, **_kwargs: object) -> object:
            pytest.fail("explicit hard/null budget scope reached candidate work")

        monkeypatch.setattr(candidate_acquisition_action, "_compiler_binding", forbidden)
        monkeypatch.setattr(acquisition_executor, "execute_live_catalog_acquisition", forbidden)
        monkeypatch.setattr(JointSimulationPort, "__call__", forbidden)
        monkeypatch.setattr(bridge, "_prepare_candidate_source_reentry", forbidden)
        before = _state(case)
        with pytest.raises(ValueError, match=message):
            bridge.candidate_source_reentry_preflight(closure=closure)
        assert _state(case) == before

        # Omission preserves the historical path: it reaches the existing
        # compiler owner instead of being reinterpreted as explicit hard USD.
        legacy = replace(evidence, scope_explicit=False, run_budget_scope=None)
        monkeypatch.setattr(
            ControlPlaneService, "read_original_run_budget_scope", lambda *_args, **_kw: legacy
        )

        def reached_compiler(*_args: object, **_kwargs: object) -> object:
            raise ValueError("legacy_compiler_boundary_reached")

        monkeypatch.setattr(candidate_acquisition_action, "_compiler_binding", reached_compiler)
        with pytest.raises(
            ValueError, match="candidate_source_reentry_preflight_not_established"
        ) as captured:
            bridge.candidate_source_reentry_preflight(closure=closure)
        assert str(captured.value.__cause__) == "legacy_compiler_boundary_reached"
        assert _state(case) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("quota_configured", [False, True], ids=("missing-quota", "finite-quota"))
@pytest.mark.parametrize("experiment_intent", [False, True], ids=("scope-only", "experiment"))
async def test_explicit_limited_legacy_prefetch_refuses_without_live_owner_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    quota_configured: bool,
    experiment_intent: bool,
) -> None:
    """Neither a finite quota nor a signed purpose is a live fetch permit."""
    async with _real_reentry_refusal_case(tmp_path, monkeypatch) as case:
        bridge, closure = case.owner.bridge, case.closure
        bridge.cycle_substrate_context_admission_owner = (
            ConfiguredCandidateSimulationContextAdmissionOwner(
                profiles=(), store=bridge.artifact_store
            )
        )
        bridge.promotion_runtime = SimpleNamespace(store=bridge.artifact_store)
        monkeypatch.setattr(bridge, "candidate_source_selection", lambda _closure: object())
        evidence = OriginalRunBudgetScopeEvidence(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            source_payload_ref=closure.source_payload_ref,
            run_budget_usd=Decimal("5"),
            scope_explicit=True,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            request_snapshot_schema=(
                "polisyos.runtime.control_nl_request_snapshot.v5"
                if experiment_intent
                else "polisyos.runtime.control_nl_request_snapshot.v4"
            ),
            request_content_hash="sha256:" + "a" * 64,
            candidate_acquisition_intent_present=experiment_intent,
            candidate_acquisition_intent=(
                "bounded_experiment_voi_unknown" if experiment_intent else None
            ),
        )
        monkeypatch.setattr(
            ControlPlaneService, "read_original_run_budget_scope", lambda *_args, **_kw: evidence
        )
        monkeypatch.setattr(
            ControlPlaneService,
            "verify_candidate_unpriced_budget_scope",
            lambda *_args, **_kw: evidence,
        )
        configured_profile = SimpleNamespace(
            n5=SimpleNamespace(
                invocation_quota_policy=(
                    BudgetInvocationQuotaPolicy(
                        allocation_id="component-finite-quota", total_units=3, protected_units=1
                    )
                    if quota_configured
                    else None
                ),
                invocation_purpose="standard" if quota_configured else None,
            )
        )
        monkeypatch.setattr(
            bridge, "_candidate_source_prior_owner", lambda **_kw: (configured_profile, None, None)
        )

        def forbidden(*_args: object, **_kwargs: object) -> object:
            pytest.fail("unbound limited scope reached a candidate operation")

        monkeypatch.setattr(candidate_acquisition_action, "_compiler_binding", forbidden)
        monkeypatch.setattr(acquisition_executor, "execute_live_catalog_acquisition", forbidden)
        monkeypatch.setattr(JointSimulationPort, "__call__", forbidden)
        monkeypatch.setattr(bridge, "_prepare_candidate_source_reentry", forbidden)
        before = _state(case)
        with pytest.raises(
            ValueError, match="candidate_source_reentry_unpriced_authority_not_established"
        ):
            bridge.candidate_source_reentry_preflight(closure=closure)
        assert _state(case) == before

        # The real WDI port currently stops at the missing re-entry owner,
        # before the scope preflight or any effect.  The source selection and
        # signed scope above remain explicit fixture adapters.
        authority = bridge.authority
        registry = AcquisitionAuthorityRegistry.model_validate_json(
            authority.registry_path.read_bytes()
        )
        port = acquisition_surface_execution.WorldBankWDIAcquisitionExecutionPort(
            authority=authority,
            registry=registry,
            provision=authority.provision,
            provision_content_sha256=authority.provision_content_sha256,
            runtime_state_root=tmp_path / "unpriced-port",
            artifact_store=bridge.artifact_store,
            world_growth_bridge=bridge,
        )
        monkeypatch.setattr(bridge, "begin_action", forbidden)
        monkeypatch.setattr(bridge, "candidate_source_reentry_preflight", forbidden)
        monkeypatch.setattr(port, "reserve_route_binding", forbidden)
        monkeypatch.setattr(
            acquisition_surface_execution, "execute_live_catalog_acquisition", forbidden
        )
        with pytest.raises(
            acquisition_executor.LiveAcquisitionExecutionError,
            match="candidate_reentry_owner_not_available",
        ):
            port.execute(closure, action_phase_ref="sha256:" + "b" * 64)
        assert not (tmp_path / "unpriced-port").exists()
        assert _state(case) == before


@pytest.mark.asyncio
async def test_historical_original_scope_reopens_legacy_job_and_requires_creation_event(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Actual legacy SQL/CAS history remains distinct from declared experiment intent."""
    async with _real_reentry_refusal_case(tmp_path, monkeypatch) as case:
        from polisyos.runtime.http.services.control_plane_store import (
            ControlJobExecutionAdmissionError,
            ControlPlaneStore,
        )

        store = case.service._control_store
        before = _state(case)

        class ReadOnlyCreationRows:
            """Actual typed fixture rows, without a store identity or write facility."""

            def get_job(self, job_id):
                return store.get_job(job_id)

            def get_job_created_event_payload(self, job_id):
                return store.get_job_created_event_payload(job_id)

            def get_job_created_outbox_event(self, job_id):
                return store.get_job_created_outbox_event(job_id)

            def _reconcile_control_job_creation_envelope(self, job):
                return ControlPlaneStore._reconcile_control_job_creation_envelope(self, job)

            def historical_scope(self, **kwargs):
                return ControlPlaneStore.historical_completed_job_execution_scope(self, **kwargs)

        rows = ReadOnlyCreationRows()

        def read():
            return _read_original_run_budget_scope_historical(
                artifact_store=case.service._artifact_store,
                get_job=store.get_job,
                historical_execution_scope=rows.historical_scope,
                get_created_event=store.get_job_created_event_payload,
                closure=case.closure,
            )

        evidence = read()
        assert evidence.source_job_id == case.closure.source_job_id
        assert evidence.scope_explicit is False
        assert evidence.request_content_hash is None
        with pytest.raises(ValueError, match="candidate_unpriced_budget_scope_not_established"):
            _require_candidate_unpriced_budget_scope_historical(evidence)
        with pytest.raises(ValueError, match="candidate_experiment_intent_not_established"):
            _require_candidate_experiment_intent_historical(evidence)

        def missing_event(_job_id):
            raise RuntimeError("control_job_created_event_count_not_one")

        with monkeypatch.context() as patch:
            patch.setattr(rows, "get_job_created_event_payload", missing_event)
            with pytest.raises(
                ControlJobExecutionAdmissionError, match="control_job_created_event_unavailable"
            ):
                read()
        assert read() == evidence
        assert _state(case) == before
