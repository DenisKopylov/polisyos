"""Candidate-source dispatch at the real WDI execution-port boundary.

The GDP source, canonical authority/registry/provision, bridge, route binding,
and execution port use their real owners. A controlled source-evidence artifact
is reused as the executor result. Readiness, action-phase, and source-budget
preflight are adapted to isolate dispatch; both admission owners stop at raised
sentinels, so this does not exercise or claim a completed served action.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts
from polisyos.data_forge.read_api import catalog
from polisyos.data_requirement import DataRequirementCompilationReport
from polisyos.pdc import gy_content_hash
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
    resolve_world_bank_wdi_route_execution_bindings,
)
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionCandidateSourceRoute,
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
)
from polisyos.runtime.quality.cycle_substrate import cycle_job_profile_selection_ref
from polisyos.runtime.quality.design_problem import DesignProblem
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from tests._helpers.lane01_candidate_source import (
    GDP_COMPILER_INPUT,
    build_lane01_candidate_source,
)
from tests._helpers.lane01_wdi_profiles import GDP_PROFILE, fixture_wdi_response
from tests.unit.runtime.quality.test_candidate_acquisition_world import _problem


@dataclass(frozen=True, slots=True)
class _PlannerMetadata:
    """Small typed planner projection consumed by the live route resolver."""

    compiled_requirement_ref: str
    gap_type: str = "data_snapshot_release"
    requirement_family: str = "data_requirement"
    requirement_schema_version: str = "policyos.runtime.l1_variable_availability_gap.v1"
    missing_requirement_fields: tuple[str, ...] = ("canonical_variable_observations:global.gdp",)
    recommended_strategy: str = "production_snapshot_build"


@dataclass(frozen=True, slots=True)
class _RouteClosure:
    """Typed test transport for the route fields read by binding and selection owners."""

    tenant_id: str
    cell_id: str
    run_id: str
    route_id: str
    design_problem_ref: str
    design_problem_basis: DesignProblem
    planner_record: _PlannerMetadata


class _DispatchReachedError(RuntimeError):
    """Stop at the selected owner boundary without producing an action receipt."""

    def __init__(self, owner: str, payload: dict[str, object]) -> None:
        super().__init__(owner)
        self.owner = owner
        self.payload = payload


def test_observed_gdp_dispatch_uses_only_explicit_candidate_source_selection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = build_lane01_candidate_source(
        tmp_path / "source",
        monkeypatch,
        profile=GDP_PROFILE,
        compiler_input=GDP_COMPILER_INPUT,
        response_body=fixture_wdi_response(GDP_PROFILE),
        tenant_id="tenant-dispatch",
        cell_id="cell-dispatch",
        run_id="run-dispatch",
    )
    report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(fixture.store, fixture.binding.compiler_report_ref)
    )
    specs = tuple(
        row
        for row in report.specs
        if row.metadata.get("capability_binding", {}).get("requirement_id")
        == fixture.requirement_id
    )
    assert len(specs) == 1
    compiled_requirement_ref = specs[0].requirement_id

    problem = _problem(outcome_slot="global.gdp")
    design_problem_ref = gy_content_hash(problem.model_dump(mode="json"))
    route_id = gy_content_hash({"known_fixture_route": "observed-gdp-dispatch"})
    closure = _RouteClosure(
        tenant_id="tenant-dispatch",
        cell_id="cell-dispatch",
        run_id="run-dispatch",
        route_id=route_id,
        design_problem_ref=design_problem_ref,
        design_problem_basis=problem,
        planner_record=_PlannerMetadata(compiled_requirement_ref),
    )
    selected_route = AcquisitionCandidateSourceRoute(
        tenant_id=closure.tenant_id,
        cell_id=closure.cell_id,
        run_id=closure.run_id,
        route_id=closure.route_id,
        design_problem_ref=closure.design_problem_ref,
        compiled_requirement_ref=compiled_requirement_ref,
        requirement_id=fixture.requirement_id,
        candidate_digest=fixture.candidate_digest,
        profile_selection_ref=cycle_job_profile_selection_ref(problem),
        canonical_variable_id=fixture.entry.target_variable,
        target_slot_id=fixture.source.target_slot_id,
        country_code=fixture.source.country_code,
        year=fixture.source.year,
        population=fixture.source.population,
        reentry_budget_usd=Decimal("1.00"),
    )
    registry = catalog.AcquisitionAuthorityRegistry.model_validate_json(
        fixture.authority.registry_path.read_bytes()
    )
    (resolved_binding,) = resolve_world_bank_wdi_route_execution_bindings(
        closure=closure,
        authority=fixture.authority,
        registry=registry,
        provision=fixture.authority.provision,
        provision_content_sha256=fixture.authority.provision_content_sha256,
    )
    assert resolved_binding.authority_entry_id == fixture.entry.entry_id
    assert resolved_binding.authority_registry_content_sha256 == registry.content_sha256
    assert resolved_binding.authority_provision_content_sha256 == (
        fixture.authority.provision_content_sha256
    )
    assert fixture.source.observation_class == "observed"
    assert fixture.source.status == "candidate_only"

    for configured, transition, expected_owner in (
        (True, None, "candidate"),
        (False, None, "observed_admission"),
        (True, "withdraw", None),
        (False, "appoint", None),
    ):
        case_id = f"{configured}-{transition}"
        bridge_runtime = tmp_path / f"bridge-runtime-{case_id}"
        bridge = AcquisitionWorldGrowthBridge(
            config=AcquisitionWorldGrowthConfig(
                candidate_source_routes=(selected_route,) if configured else ()
            ),
            repo_root=fixture.authority.repo_root,
            runtime_root=bridge_runtime,
            authority=fixture.authority,
            artifact_store=fixture.store,
            event_log=RuntimeDiagnosticEventLog(
                store=ControlPlaneStore(
                    backend="sqlite",
                    sqlite_path=tmp_path / f"events-{case_id}.sqlite3",
                ),
                artifact_store=fixture.store,
            ),
            epoch_deployment=None,
        )
        assert (bridge.candidate_source_selection(closure) is not None) is configured

        def replay_fixture_evidence(
            *,
            selected_transition: str | None = transition,
            selected_bridge: AcquisitionWorldGrowthBridge = bridge,
            **kwargs: object,
        ) -> catalog.LiveSourceExecutionEvidence:
            assert kwargs["entry_id"] == fixture.entry.entry_id
            if selected_transition is not None:
                selected_bridge.config = AcquisitionWorldGrowthConfig(
                    candidate_source_routes=(
                        () if selected_transition == "withdraw" else (selected_route,)
                    )
                )
            return fixture.evidence

        port = WorldBankWDIAcquisitionExecutionPort(
            authority=fixture.authority,
            registry=registry,
            provision=fixture.authority.provision,
            provision_content_sha256=fixture.authority.provision_content_sha256,
            runtime_state_root=tmp_path / f"port-runtime-{case_id}",
            artifact_store=fixture.store,
            executor=replay_fixture_evidence,
            world_growth_bridge=bridge,
        )

        # These owner checks need a served action phase, worker lease, and
        # source-budget window. Adapt those preflights only; route binding,
        # authority resolution, provenance resolution, selection, and execute
        # dispatch remain the production implementations.
        monkeypatch.setattr(port, "require_route_ready", lambda _closure: None)
        if configured:
            monkeypatch.setattr(
                bridge,
                "begin_action",
                lambda _closure, _phase: None,
            )
            window = SimpleNamespace(
                effective_limit_usd=Decimal("1.00"),
                scope=object(),
            )
            monkeypatch.setattr(
                bridge,
                "prepare_candidate_source_budget_window",
                lambda window=window, **_kwargs: window,
            )
            monkeypatch.setattr(
                bridge,
                "candidate_source_reentry_preflight",
                lambda **_kwargs: None,
            )

        def candidate_owner(**kwargs: object) -> None:
            raise _DispatchReachedError("candidate", kwargs)

        def observed_owner(**kwargs: object) -> None:
            raise _DispatchReachedError("observed_admission", kwargs)

        monkeypatch.setattr(bridge, "admit_candidate", candidate_owner)
        monkeypatch.setattr(bridge, "admit", observed_owner)

        phase_ref = "phase:observed-gdp-dispatch" if configured else None
        if expected_owner is None:
            from polisyos.runtime.http.services.acquisition_action_service import (
                AcquisitionActionServiceError,
            )

            with pytest.raises(
                AcquisitionActionServiceError, match="acquisition_live_evidence_not_admitted"
            ):
                port.execute(closure, action_phase_ref=phase_ref)
            continue
        with pytest.raises(_DispatchReachedError) as reached:
            port.execute(closure, action_phase_ref=phase_ref)

        assert reached.value.owner == expected_owner
        payload = reached.value.payload
        assert payload["closure"] is closure
        assert payload["evidence"] is fixture.evidence
        resolved = fixture.authority.resolve(fixture.entry.entry_id)
        assert (
            catalog.resolve_source_observation_class(resolved)
            is catalog.ObservationProvenanceClass.OBSERVED
        )
        if configured:
            assert payload["binding"] == resolved_binding
            assert payload["action_phase_ref"] == phase_ref
        else:
            assert payload["binding_id"] == resolved_binding.binding_id
            assert payload["target_variable"] == "global.gdp"
            assert payload["action_phase_ref"] is None
