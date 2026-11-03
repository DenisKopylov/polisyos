"""Protected candidate WDI controls and a separate genuine COV seed extraction.

Action controls use a native recursive-controller source without a prior N5.
The separate served fiscal COV seed retains its actual NL/N4/N5 producer and
limitations; it does not establish a labor WDI route or an acquired continuation.
No test promotes modeled inputs to observed, causal, or publication authority.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from polisyos.core import artifacts, canon
from polisyos.runtime.http.services.acquisition_surface_execution import (
    WorldBankWDIAcquisitionExecutionPort,
    resolve_world_bank_wdi_route_execution_bindings,
)
from polisyos.runtime.quality import acquisition_route_loop, candidate_acquisition_action
from polisyos.runtime.quality.acquisition_executor import LiveAcquisitionExecutionError
from polisyos.runtime.quality.acquisition_world_growth import AcquisitionWorldGrowthBridge
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.candidate_acquisition_action import (
    CANDIDATE_ACTION_KIND,
    CandidateAcquisitionActionReceipt,
    _current_action,
    _require_compiler_relation,
    read_candidate_acquisition_action,
)
from polisyos.runtime.quality.candidate_acquisition_source import read_candidate_acquisition_source
from polisyos.runtime.quality.cycle_substrate import (
    ConfiguredCandidateSimulationContextAdmissionOwner,
)
from polisyos.runtime.quality.generation_cycle import CandidateSourceReentryReceipt
from tests._helpers.lane01_candidate_action_served import (
    build_candidate_port_owners,
    labor_candidate_profile,
    run_lane01_candidate_action_served,
)

pytest_plugins = ("tests._helpers.acquisition_served_history",)


def _assert_actual_report_hash_and_readback_controls(
    ctx: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise finite hashing and corrupted reads over this actual N7 producer."""
    payload = ctx.closure.planner_report.model_dump(mode="json")
    float_paths: list[tuple[str | int, ...]] = []

    def collect(value: object, path: tuple[str | int, ...] = ()) -> None:
        if isinstance(value, float):
            assert math.isfinite(value)
            float_paths.append(path)
        elif isinstance(value, dict):
            for key, child in value.items():
                collect(child, (*path, key))
        elif isinstance(value, list | tuple):
            for index, child in enumerate(value):
                collect(child, (*path, index))

    collect(payload)
    assert float_paths, "the actual candidate report must exercise its finite numeric metadata"
    finite_report_hash = agent_action_content_hash(ctx.closure.planner_report)
    assert ctx.request.planner_report_hash == finite_report_hash
    assert agent_action_content_hash(payload) == finite_report_hash
    # Route identifiers retain their existing float-free canonical policy.
    legacy_payload = {"run_id": ctx.closure.run_id, "source_job_id": ctx.closure.source_job_id}
    assert acquisition_route_loop._content_hash(legacy_payload) == agent_action_content_hash(
        legacy_payload
    )
    for nonfinite in (math.nan, math.inf, -math.inf):
        invalid = deepcopy(payload)
        parent = invalid
        for segment in float_paths[0][:-1]:
            parent = parent[segment]
        parent[float_paths[0][-1]] = nonfinite
        with pytest.raises(canon.CanonViolation):
            agent_action_content_hash(invalid)

    control, closure = ctx.control, ctx.closure

    def resolve():
        return acquisition_route_loop.AcquisitionRouteLoop(
            control_store=control._control_store,
            artifact_store=control._artifact_store,
            event_log=control._diagnostic_event_log,
            core_source_resolver=control.resolve_completed_control_job_core_run_source,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
        ).resolve_current_route(run_id=closure.run_id)

    reopened = resolve()
    assert reopened.route_id == closure.route_id
    assert agent_action_content_hash(reopened.planner_report) == ctx.request.planner_report_hash
    planner_ref = closure.source_cycle.acquisition_routing_report_ref
    assert planner_ref is not None
    get_bytes = control._artifact_store.get_bytes
    for selected_ref, field, replacement, expected_codes in (
        (
            planner_ref,
            "run_id",
            "corrupted-selected-report",
            {
                "acquisition_planner_report_readback_failed",
                "acquisition_planner_report_readback_mismatch",
            },
        ),
        (
            closure.compiled_ref,
            "content_hash",
            "sha256:" + "0" * 64,
            {
                "source_artifact_unverified",
                "source_core_attempt_not_established",
            },
        ),
    ):
        original = get_bytes(selected_ref)
        changed = canon.from_canonical_bytes(original)
        changed[field] = replacement
        tampered = canon.to_canonical_bytes(changed, canon.CanonSpec(forbid_floats=False))
        selected_id = str(getattr(selected_ref, "artifact_id", selected_ref))

        def corrupted_bytes(ref, *args, selected_id=selected_id, tampered=tampered, **kwargs):
            if str(getattr(ref, "artifact_id", ref)) == selected_id:
                return tampered
            return get_bytes(ref, *args, **kwargs)

        with monkeypatch.context() as corrupt:
            corrupt.setattr(control._artifact_store, "get_bytes", corrupted_bytes)
            with pytest.raises(acquisition_route_loop.AcquisitionRouteClosureError) as refused:
                resolve()
            assert refused.value.code in expected_codes
        assert get_bytes(selected_ref) == original
        assert resolve().route_id == closure.route_id


@pytest.mark.integration
def test_candidate_port_refuses_distinct_canonical_authority_owner(tmp_path: Path) -> None:
    """Equivalent real authority bytes cannot replace the bridge's actual owner."""
    case = build_candidate_port_owners(tmp_path)
    try:
        assert case.authority is not case.same_source_authority
        assert case.authority.resolve(case.entry.entry_id) == case.same_source_authority.resolve(
            case.entry.entry_id
        )
        arguments = {
            "registry": case.registry,
            "provision": case.authority.provision,
            "provision_content_sha256": case.authority.provision_content_sha256,
            "runtime_state_root": case.runtime_root,
            "artifact_store": case.store,
            "world_growth_bridge": case.bridge,
        }
        accepted = WorldBankWDIAcquisitionExecutionPort(authority=case.authority, **arguments)
        assert accepted._world_growth_bridge is case.bridge
        with pytest.raises(ValueError, match=r"^acquisition_world_growth_authority_mismatch$"):
            WorldBankWDIAcquisitionExecutionPort(authority=case.same_source_authority, **arguments)
        assert not case.runtime_root.exists()
    finally:
        case.control_store.close()


@pytest.mark.integration
@pytest.mark.parametrize("mode", ["no_bridge", "bridge_without_candidate"])
def test_model_output_route_refuses_missing_candidate_owner_before_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str
) -> None:
    """Actual modeled source bindings cannot consume a lease without their owner."""

    def observe(ctx: SimpleNamespace) -> None:
        port = ctx.cases[-1].port
        if mode == "no_bridge":
            assert port._world_growth_bridge is None
        else:
            assert type(port._world_growth_bridge) is AcquisitionWorldGrowthBridge
            assert port._world_growth_bridge.candidate_source_selection(ctx.closure) is None
        with pytest.raises(
            LiveAcquisitionExecutionError, match="candidate_source_owner_not_configured"
        ):
            port.require_route_ready(ctx.closure)
        assert ctx.response.status_code == 409, ctx.response.text
        assert ctx.response.json()["code"] == "candidate_source_owner_not_configured"
        assert ctx.job is None
        assert ctx.transport_calls == []
        bindings = resolve_world_bank_wdi_route_execution_bindings(
            closure=ctx.closure,
            authority=port._authority,
            registry=port._registry,
            provision=port._provision,
            provision_content_sha256=port._provision_content_sha256,
        )
        assert len(bindings) == 1
        assert bindings[0].target_variable == "global.unemployment_rate"
        for binding in bindings:
            assert not port._lease_path(binding).exists()
            assert not port._execution_claim_path(binding).exists()

    run_lane01_candidate_action_served(
        tmp_path,
        monkeypatch,
        observe,
        candidate_owner_mode=mode,
    )


def _assert_persisted_candidate_movement_refusal(ctx: SimpleNamespace, supplier_ref: str) -> None:
    """Read the installed movement consumer's actual refusal for this terminal."""
    if ctx.client.app.state.runtime_container.acquisition_movement_service is None:
        return
    store = ctx.control._artifact_store
    inventory = store.manifest_inventory_snapshot(kind="runtime_quality.movement_intake")
    assert inventory.verdict == "pass"
    matched = []
    for entry in inventory.entries:
        ref = artifacts.artifact_ref_for_manifest(entry.manifest)
        value = artifacts.load_core_json_artifact(store, ref)
        if value["supplier_receipt_ref"] == supplier_ref:
            matched.append((ref, value))
    assert len(matched) == 1
    ref, intake = matched[0]
    assert intake["status"] == "refused"
    assert intake["reason"] == "supplier_no_reentry"
    assert intake["movement_record"] is None
    assert intake["candidate_ref"] is None
    events = ctx.control._diagnostic_event_log.list_events(
        run_id=ctx.closure.run_id,
        job_id=ctx.job_id,
        limit=1000,
    )
    matching_events = [
        row
        for row in events
        if row.event.phase == "movement_admission"
        and str(ref.artifact_id) in row.event.artifact_refs
    ]
    assert len(matching_events) == 1
    assert matching_events[0].event.input_refs == (supplier_ref,)
    assert matching_events[0].event.state_after == "refused"


def _assert_genuine_candidate_fresh_get(
    ctx: SimpleNamespace, outcome: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reopen the actual selected continuation and refuse its missing custody."""
    control, store = ctx.control, ctx.control._artifact_store
    inventory = store.manifest_inventory_snapshot(
        kind="runtime_quality.candidate_source_reentry_receipt"
    )
    assert inventory.verdict == "pass"
    selected_refs = [
        artifacts.artifact_ref_for_manifest(entry.manifest)
        for entry in inventory.entries
        if str(entry.manifest.artifact_id) in outcome.latest_receipt.owner_receipt_refs
    ]
    assert len(selected_refs) == 1
    selected_ref = selected_refs[0]
    receipt = CandidateSourceReentryReceipt.model_validate(
        artifacts.load_core_json_artifact(store, selected_ref)
    )
    assert receipt.action_job_id == ctx.job_id
    assert receipt.candidate_source_ref.manifest_profile_sha256
    source_job = control._control_store.get_job(ctx.closure.source_job_id)
    assert source_job is not None
    path = f"/api/v1/runs/{source_job.progress['core_run_id']}"
    headers = {
        "Authorization": f"Bearer {ctx.trust.tokens['acquisition-operator']}",
        "X-Tenant-ID": ctx.closure.tenant_id,
    }

    def fresh():
        response = ctx.client.get(path, headers=headers)
        assert response.status_code == 200, response.text
        return response.json()["run"]["candidate_simulation"]

    projected = fresh()
    rows = [
        row
        for row in projected["acquisition_history"]
        if row["schema_version"]
        == "policyos.runtime.run_candidate_simulation_acquisition_history.v4"
    ]
    assert len(rows) == 1
    row = rows[0]
    assert row["reentry_receipt_ref"] == selected_ref.model_dump(mode="json")
    assert row["route_receipt_ref"]["artifact_id"] == outcome.head.receipt_ref
    for field in (
        "candidate_action_ref",
        "candidate_source_ref",
        "data_snapshot_ref",
        "world_model_ref",
        "context_job_ref",
        "model_declaration_ref",
        "ncm_ref",
        "n4_source_ref",
        "n5_input_ref",
        "n5_execution_ref",
        "n5_result_ref",
    ):
        expected = getattr(receipt, field)
        assert row[field] == (expected.model_dump(mode="json") if expected is not None else None)
    assert row["simulation_status"] == receipt.new_cycle.simulation.status
    assert row["simulation_authority_blockers"] == list(
        receipt.new_cycle.simulation.authority_blockers
    )
    assert row["continued_generation_run_content_hash"] == (
        receipt.continued_generation_run_content_hash
    )
    assert row["observed_admission"] is False
    assert row["publication_authority"] is False
    current = projected["candidate_source_current_projection"]
    assert current["status"] == "resolved"
    assert current["generation_run_content_hash"] == receipt.continued_generation_run_content_hash
    assert current["basis_cycle_index"] == receipt.new_cycle.cycle_index
    assert current["basis_transition_content_hash"] == receipt.basis_transition.content_hash
    assert current["certified_candidate_ids"] == []
    assert current["fronts"]["decision_candidate_ids"] == []
    assert all(not occurrence["certified_by_n9"] for occurrence in current["occurrences"])
    assert projected["acquisition_history_limitation_code"] is None
    source_ref = projected["source_ref"]
    get_bytes = store.get_bytes
    # Both selectors originate in the actual selected receipt, rather than
    # constructor-only wrong-ref DTOs. A fresh GET must reopen their custody.
    for withheld in (selected_ref, receipt.candidate_source_ref):
        original = get_bytes(withheld)
        withheld_id = str(withheld.artifact_id)

        def unavailable(ref, *args, withheld_id=withheld_id, **kwargs):
            if str(getattr(ref, "artifact_id", ref)) == withheld_id:
                raise FileNotFoundError("actual selected candidate custody withheld")
            return get_bytes(ref, *args, **kwargs)

        with monkeypatch.context() as removed:
            removed.setattr(store, "get_bytes", unavailable)
            refused = fresh()
            assert refused["source_ref"] == source_ref
            assert refused["acquisition_history_limitation_code"] is not None
            assert not any(
                row["schema_version"]
                == "policyos.runtime.run_candidate_simulation_acquisition_history.v4"
                for row in refused["acquisition_history"]
            )
            view = refused["candidate_source_current_projection"]
            assert view["status"] == "not_established"
            assert view["occurrences"] == []
            assert view["fronts"] is None
        assert get_bytes(withheld) == original
        assert fresh() == projected


def _assert_genuine_labor_candidate_action(
    monkeypatch: pytest.MonkeyPatch,
    run_genuine_action: Callable[[Callable[[SimpleNamespace], None]], None],
) -> None:
    """Assert action custody only for a caller-supplied genuine prior N4/N5 seed.

    The native N7 fixture below cannot call this helper: it has no selected
    prior N4/N5/context artifacts. No positive lifecycle claim is collected
    until a real source producer supplies this runner.
    """
    assert callable(getattr(AcquisitionWorldGrowthBridge, "complete_candidate_reentry", None))
    live_lease_checks: list[str] = []
    orphan_checks: list[artifacts.ArtifactRef] = []
    selected_handoff_checks: list[artifacts.ArtifactRef] = []
    execute = WorldBankWDIAcquisitionExecutionPort.execute
    persist = candidate_acquisition_action.persist_candidate_acquisition_action
    handoff = AcquisitionWorldGrowthBridge.candidate_source_context_handoff

    def inspect_handoff(bridge, *, closure, candidate_action_ref):
        outcome = bridge.action_head_sink.current_action_outcome(
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
            run_id=closure.run_id,
            source_job_id=closure.source_job_id,
            route_id=closure.route_id,
        )
        assert outcome is not None
        if outcome.head.receipt_phase == "candidate_input_reentry_pending":
            assert outcome.selection_phase is not None
            assert (
                str(candidate_action_ref.artifact_id) in outcome.latest_receipt.owner_receipt_refs
            )
            selected_handoff_checks.append(candidate_action_ref)
        return handoff(bridge, closure=closure, candidate_action_ref=candidate_action_ref)

    def inspect_unselected_receipt(*, bridge, closure, **kwargs):
        # The real producer has persisted this receipt under the current worker
        # lease, but admit_candidate has not prepared or selected its outcome.
        # Readback is valid here; world handoff is not.
        ref, receipt = persist(bridge=bridge, closure=closure, **kwargs)
        assert (
            read_candidate_acquisition_action(
                bridge=bridge,
                closure=closure,
                receipt_ref=ref,
                require_current_action=True,
            )
            == receipt
        )
        with pytest.raises(ValueError, match=r"^candidate_source_action_not_selected_for_reentry$"):
            bridge.candidate_source_context_handoff(closure=closure, candidate_action_ref=ref)
        orphan_checks.append(ref)
        return ref, receipt

    monkeypatch.setattr(
        candidate_acquisition_action,
        "persist_candidate_acquisition_action",
        inspect_unselected_receipt,
    )
    monkeypatch.setattr(
        AcquisitionWorldGrowthBridge, "candidate_source_context_handoff", inspect_handoff
    )

    def inspect_execute(port, closure, *, action_phase_ref=None):
        bridge = port._world_growth_bridge
        owner = bridge.cycle_substrate_context_admission_owner
        assert type(owner) is ConfiguredCandidateSimulationContextAdmissionOwner
        selection = bridge.candidate_source_selection(closure)
        assert selection is not None
        configured = owner.configured_profile_for_selection_ref(selection.profile_selection_ref)
        assert configured.profile_selection_ref == selection.profile_selection_ref
        assert configured.context_inputs.world_model_record.population_scope == "total_labor_force"
        settlement = bridge._source_control_service.llm_producer_settlement_store
        assert settlement is not None
        assert len(settlement.settlement_owner_identity) == 3
        assert action_phase_ref is not None
        selected, phase, admission = _current_action(bridge, closure, action_phase_ref)
        assert admission.job.kind == "acquisition"
        assert admission.job.state == "running"
        assert admission.job.job_id == phase.job_id
        assert admission.job.job_id != closure.source_job_id
        assert admission.scope.actor_authenticated is True
        assert selected.target_slot_id == "global.unemployment_rate"
        # These are variants of the real owner closure and its actual requested
        # predecessor, not invented receipts that merely satisfy a constructor.
        with pytest.raises(ValueError, match="candidate_action_route_not_configured"):
            _current_action(
                bridge,
                closure.model_copy(update={"route_id": "sha256:" + "0" * 64}),
                action_phase_ref,
            )
        with pytest.raises(ValueError, match="acquisition_action_phase_source_binding_mismatch"):
            _current_action(
                bridge,
                closure.model_copy(update={"source_job_id": admission.job.job_id}),
                action_phase_ref,
            )
        with pytest.raises(ValueError, match="acquisition_action_phase_source_binding_mismatch"):
            _current_action(bridge, closure, phase.predecessor_receipt_ref)
        live_lease_checks.append(action_phase_ref)
        return execute(port, closure, action_phase_ref=action_phase_ref)

    monkeypatch.setattr(WorldBankWDIAcquisitionExecutionPort, "execute", inspect_execute)

    def observe(ctx: SimpleNamespace) -> None:
        control, closure = ctx.control, ctx.closure
        assert ctx.job is not None
        assert ctx.job.kind == "acquisition"
        assert ctx.job.job_id != closure.source_job_id
        assert ctx.transport_calls == [
            (
                "GET",
                "https://api.worldbank.org/v2/country/USA/indicator/SL.UEM.TOTL.ZS",
                {"date": "2024:2024", "format": "json", "page": "1", "per_page": "1000"},
            )
        ]
        scope = {
            "tenant_id": closure.tenant_id,
            "cell_id": closure.cell_id,
            "run_id": closure.run_id,
            "source_job_id": closure.source_job_id,
            "route_id": closure.route_id,
        }
        outcome = control.acquisition_route_sink.current_action_outcome(**scope)
        assert outcome is not None
        assert outcome.head.job_id == ctx.job_id
        assert outcome.head.receipt_phase in {"candidate_input_reentry_pending", "terminal"}
        if outcome.head.receipt_phase == "terminal":
            assert outcome.latest_receipt.terminal_outcome == "candidate_reentry_completed"
            assert ctx.job.state == "completed"
            _assert_persisted_candidate_movement_refusal(ctx, outcome.head.receipt_ref)
            _assert_genuine_candidate_fresh_get(ctx, outcome, monkeypatch)
        else:
            assert ctx.job.state == "failed"
            assert ctx.job.progress.get("receipt_phase") != "terminal"
        inventory = control._artifact_store.manifest_inventory_snapshot(kind=CANDIDATE_ACTION_KIND)
        assert inventory.verdict == "pass"
        assert len(inventory.entries) == 1
        selected = artifacts.artifact_ref_for_manifest(inventory.entries[0].manifest)
        receipt = CandidateAcquisitionActionReceipt.model_validate(
            artifacts.load_core_json_artifact(control._artifact_store, selected)
        )
        assert receipt.action_job_id == ctx.job_id
        assert receipt.source_job_id == closure.source_job_id
        assert receipt.route_id == closure.route_id
        assert receipt.profile_selection_ref == ctx.selected.profile_selection_ref
        assert receipt.candidate_digest == ctx.selected.candidate_digest
        assert (
            receipt.compiler_report_ref
            == closure.planner_report.requirement_basis_binding.compiler_report_ref
        )
        assert receipt.selected_action_phase_ref.manifest_profile_sha256
        assert receipt.admitted_observation_delta == 0
        assert receipt.observed_admission is False
        assert receipt.publication_authority is False
        for forbidden_kind in (
            "runtime_quality.acquisition_world_growth_receipt",
            "epoch.prepared",
            "epoch.production_receipt",
            "epoch.acquisition_passport_snapshot",
        ):
            forbidden = control._artifact_store.manifest_inventory_snapshot(kind=forbidden_kind)
            assert forbidden.verdict == "pass"
            assert forbidden.entries == (), forbidden_kind
        source = read_candidate_acquisition_source(
            control._artifact_store,
            source_ref=receipt.candidate_source_ref,
            authority=ctx.cases[-1].bridge.authority,
        )
        assert source.job_id == ctx.job_id
        assert source.route_id == closure.route_id
        assert source.observation == pytest.approx(0.175)
        assert (source.country_code, source.year, source.population) == (
            "USA",
            2024,
            "total_labor_force",
        )
        assert (source.target_slot_id, source.canonical_unit, source.observation_class) == (
            "global.unemployment_rate",
            "ratio",
            "model_output",
        )
        assert {
            "measurement_validity_not_established",
            "causal_validity_not_established",
            "claim_evidence_not_established",
            "publication_authority_not_established",
        }.issubset(source.limitations)
        assert receipt.limitations == source.limitations
        assert live_lease_checks == [receipt.action_phase_ref]
        assert orphan_checks == [selected]
        assert selected_handoff_checks
        assert all(ref == selected for ref in selected_handoff_checks)
        basis = closure.planner_report.requirement_basis_binding
        for changed in (
            {"compiled_requirement_ref": receipt.compiled_requirement_ref + ":foreign"},
            {"requirement_id": receipt.requirement_id + ":foreign"},
            {"candidate_digest": "sha256:" + "0" * 64},
        ):
            with pytest.raises(ValueError, match="candidate_action_compiler_selection"):
                _require_compiler_relation(
                    control._artifact_store,
                    basis,
                    **(
                        {
                            "compiled_requirement_ref": receipt.compiled_requirement_ref,
                            "requirement_id": receipt.requirement_id,
                            "candidate_digest": receipt.candidate_digest,
                        }
                        | changed
                    ),
                )
        for field, foreign in (
            ("run_id", "another-real-scope"),
            ("source_job_id", ctx.job_id),
            ("route_id", "sha256:" + "0" * 64),
        ):
            with pytest.raises(ValueError, match="candidate_action_receipt_route_scope_mismatch"):
                read_candidate_acquisition_action(
                    bridge=ctx.cases[-1].bridge,
                    closure=closure.model_copy(update={field: foreign}),
                    receipt_ref=selected,
                    require_current_action=False,
                )
        with pytest.raises(ValueError, match="candidate_action_receipt_profile_unselected"):
            read_candidate_acquisition_action(
                bridge=ctx.cases[-1].bridge,
                closure=closure,
                receipt_ref=selected.model_copy(update={"manifest_profile_sha256": None}),
                require_current_action=False,
            )
        get_bytes = control._artifact_store.get_bytes

        def without_selected_report(ref, *args, **kwargs):
            if str(getattr(ref, "artifact_id", ref)) == str(
                receipt.compiler_report_ref.artifact_id
            ):
                raise FileNotFoundError("selected compiler report removed")
            return get_bytes(ref, *args, **kwargs)

        with monkeypatch.context() as removed:
            removed.setattr(control._artifact_store, "get_bytes", without_selected_report)
            with pytest.raises(
                (ValueError, FileNotFoundError), match=r"compiler_binding_invalid|removed"
            ):
                read_candidate_acquisition_action(
                    bridge=ctx.cases[-1].bridge,
                    closure=closure,
                    receipt_ref=selected,
                    require_current_action=False,
                )

    run_genuine_action(observe)


@pytest.mark.integration
def test_protected_candidate_action_refuses_missing_reentry_owner_before_fetch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unavailable consumer cannot consume the one-shot WDI source attempt."""
    monkeypatch.delattr(AcquisitionWorldGrowthBridge, "complete_candidate_reentry", raising=False)

    def observe(ctx: SimpleNamespace) -> None:
        assert ctx.response.status_code == 409, ctx.response.text
        assert ctx.response.json()["code"] == "candidate_reentry_owner_not_available"
        _assert_actual_report_hash_and_readback_controls(ctx, monkeypatch)
        assert ctx.transport_calls == []
        assert ctx.job is None
        assert (
            ctx.control.acquisition_route_sink.current_action_outcome(
                tenant_id=ctx.closure.tenant_id,
                cell_id=ctx.closure.cell_id,
                run_id=ctx.closure.run_id,
                source_job_id=ctx.closure.source_job_id,
                route_id=ctx.closure.route_id,
            )
            is None
        )
        inventory = ctx.control._artifact_store.manifest_inventory_snapshot(
            kind=CANDIDATE_ACTION_KIND
        )
        assert inventory.verdict == "pass"
        assert inventory.entries == ()

    run_lane01_candidate_action_served(tmp_path, monkeypatch, observe)


@pytest.mark.integration
def test_native_labor_source_refuses_reentry_without_actual_prior_n5(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Real configured inputs cannot substitute for a missing prior N4/N5 producer."""

    def observe(ctx: SimpleNamespace) -> None:
        bridge = ctx.cases[-1].bridge
        owner = bridge.cycle_substrate_context_admission_owner
        assert type(owner) is ConfiguredCandidateSimulationContextAdmissionOwner
        assert owner.store is ctx.control._artifact_store
        profile = owner.configured_profile_for_selection_ref(ctx.selected.profile_selection_ref)
        assert profile.context_inputs.world_model_record.population_scope == "total_labor_force"
        settlement = ctx.control.llm_producer_settlement_store
        assert settlement is not None
        assert len(settlement.settlement_owner_identity) == 3
        simulation = ctx.closure.source_cycle.simulation
        assert simulation.candidate_simulation_n4_source_ref is None
        assert simulation.candidate_simulation_n5_input_ref is None
        assert simulation.candidate_simulation_context_job_ref is None
        with pytest.raises(
            ValueError, match=r"^candidate_source_reentry_preflight_not_established$"
        ) as refusal:
            bridge.candidate_source_reentry_preflight(closure=ctx.closure)
        expected_cause = (
            "acquisition_prior_actual_n5_not_established"
            if simulation.status != "joint_simulated"
            else "acquisition_prior_selected_evaluation_refs_missing"
        )
        assert str(refusal.value.__cause__) == expected_cause
        assert ctx.response.status_code == 409, ctx.response.text
        assert ctx.response.json()["code"] == (
            "candidate_source_reentry_preflight_not_established"
            if callable(getattr(bridge, "complete_candidate_reentry", None))
            else "candidate_reentry_owner_not_available"
        )
        assert ctx.transport_calls == []
        assert ctx.job is None

    run_lane01_candidate_action_served(
        tmp_path,
        monkeypatch,
        observe,
        candidate_profile_builder=labor_candidate_profile,
    )


@pytest.mark.integration
def test_genuine_cov_seed_only_retains_actual_candidate_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_recorded_candidate_gateway
) -> None:
    """Extract the real fiscal COV prior; it is not a labor or WDI route witness."""
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality import generation_cycle as cycle_owner
    from polisyos.runtime.quality.acquisition_route_loop import _resolve_source_cycle_problem_basis
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.generation_source import (
        GenerationSourceRepository,
        N4CandidateScenarioSourceRecordV3,
    )
    from tests._helpers import acquisition_served_history as fixture
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        complete_candidate_cycle_catalog_source,
    )

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "candidate-source", include_owner_slot_manifest=True
    )
    observed = []

    def observe(**values) -> None:
        control, job, run_id = values["control"], values["job"], values["run_id"]
        terminal = control.resolve_completed_control_job_core_run_source(
            job, expected_control_run_id=run_id, tenant_id=fixture.TENANT, cell_id=fixture.CELL
        )
        assert terminal.manifest.status == "ok"
        selected = artifacts.ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        assert any(
            artifacts.artifact_ref_identity_key(ref)
            == artifacts.artifact_ref_identity_key(selected)
            for ref in terminal.manifest.outputs
        )
        fresh = artifacts.FileSystemCAS.open_existing_read_only(values["cas_root"])
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            artifacts.load_core_json_artifact(fresh, selected)
        )
        cycles = [
            (leaf.cycle_run, cycle)
            for leaf in compiled.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for cycle in leaf.cycle_run.cycles
        ]
        assert len(cycles) == 1
        generation, cycle = cycles[0]
        problem = _resolve_source_cycle_problem_basis(
            generation_run=generation,
            source_cycle=cycle,
            design_problem=compiled.design_problem,
            design_problem_ref=compiled.design_problem_ref,
        )
        request = cycle.revision_request.strategy_payload["acquisition_request"]
        gap, refusal = cycle_owner._n7_cycle_source_gap(
            problem, cycle=cycle, acquisition_request=request
        )
        payload = artifacts.load_core_json_artifact(fresh, job.payload_ref)
        simulation = cycle.simulation
        selected_payloads = {}
        for name, ref in (
            ("n4_source", simulation.candidate_simulation_n4_source_ref),
            ("context_job", simulation.candidate_simulation_context_job_ref),
            ("n5_input", simulation.candidate_simulation_n5_input_ref),
            ("n5_result", simulation.simulation_result_ref),
        ):
            if ref is not None:
                selected_payloads[name] = artifacts.load_core_json_artifact(fresh, ref)
        raw_execution = simulation.diagnostics.get("candidate_simulation_execution_selected_ref")
        execution_ref = (
            artifacts.ArtifactRef.model_validate(raw_execution)
            if raw_execution is not None
            else None
        )
        if execution_ref is not None:
            selected_payloads["n5_execution"] = artifacts.load_core_json_artifact(
                fresh, execution_ref
            )
        diagnostic = {
            "run_id": run_id,
            "source_job": asdict(job),
            "core_terminal_manifest": terminal.manifest.model_dump(mode="json"),
            "compiled_ref": selected.model_dump(mode="json"),
            "original_source_payload": payload,
            "original_payload_run_budget_usd": payload.get("run_budget_usd"),
            "budget_headroom": "not_established",
            "actual_problem": problem.model_dump(mode="json"),
            "actual_cycle": cycle.model_dump(mode="json"),
            "selected_source_payloads": selected_payloads,
            "actual_source_gap": gap.model_dump(mode="json") if gap is not None else None,
            "actual_gap_refusal": refusal,
            "limitations": [
                "candidate_scenario_only",
                "fiscal_cov_source_not_labor_wdi_route",
                "observed_admission_not_established",
                "causal_authority_not_established",
            ],
        }
        (tmp_path / "actual-candidate-cov-seed.json").write_text(
            json.dumps(diagnostic, indent=2, sort_keys=True, default=str) + "\n"
        )
        assert job.state == "completed" and job.kind == "natural_language_run"
        assert payload["run_id"] == run_id
        assert Decimal(str(payload["run_budget_usd"])) == Decimal("5")
        assert simulation.status == "joint_simulated"
        assert cycle.value_port.status == "value_pending_n8"
        assert "candidate_scenario_n5_only" in cycle.value_port.authority_blockers
        assert not cycle.grounding.current_valid
        assert simulation.candidate_simulation_n4_source_ref is not None
        assert simulation.candidate_simulation_context_job_ref is not None
        assert simulation.candidate_simulation_n5_input_ref is not None
        assert simulation.simulation_result_ref is not None
        assert execution_ref is not None and execution_ref.manifest_profile_sha256
        execution = CandidateSimulationExecutionV5.model_validate(selected_payloads["n5_execution"])
        assert execution.n5_input_ref == simulation.candidate_simulation_n5_input_ref
        assert execution.n5_result_ref == simulation.simulation_result_ref
        assert execution.run_id == run_id and execution.job_id == job.job_id
        n5_input = CandidateSimulationN5InputV5.model_validate(selected_payloads["n5_input"])
        n4 = GenerationSourceRepository(fresh).load_candidate_scenario_source_for_n5(
            n5_input.n4_source_ref,
            expected_run_id=run_id,
            expected_job_id=job.job_id,
            expected_tenant_id=fixture.TENANT,
            expected_cell_id=fixture.CELL,
        )
        assert type(n4) is N4CandidateScenarioSourceRecordV3
        assert n4.origin_source_ref is None
        assert n4.stable_subject_ref == compiled.design_problem_ref
        assert n4.profile_selection_ref == values["profile_selection_ref"]
        assert n5_input.profile.profile_selection_ref == n4.profile_selection_ref
        assert n5_input.context_job_ref == simulation.candidate_simulation_context_job_ref
        assert n5_input.n4_source_ref == simulation.candidate_simulation_n4_source_ref
        assert n5_input.original_candidate_id == cycle.selected_candidate_ref
        assert n4.candidate.candidate_id == cycle.selected_candidate_ref
        from polisyos.runtime.quality.generation_cycle import (
            RealValueOwnerGateway,
            ValueOwnerAccessError,
        )
        from polisyos.runtime.quality.substrate_registry import catalog_serving_source_scope

        # This read asks the real owner about the already-selected COV seed;
        # it does not replace its grounding gap or fabricate an L1 obligation.
        gateway = RealValueOwnerGateway(
            repo_root=source.root,
            catalog_serving_source=prepared[1],
            artifact_store=fresh,
        )
        with catalog_serving_source_scope(prepared[1]):
            try:
                value_profile = gateway.load_value_data_profile(
                    candidate=n4.candidate,
                    problem=problem,
                    world_record=n5_input.profile.context_inputs.world_model_record,
                )
            except ValueOwnerAccessError as exc:
                owner_gap = exc.owner_gap_evidence
                probe = {
                    "status": "owner_refusal",
                    "code": exc.code,
                    "source_refusal_code": exc.source_refusal_code,
                    "owner_gap_evidence": (
                        owner_gap.model_dump(mode="json")
                        if hasattr(owner_gap, "model_dump")
                        else owner_gap
                    ),
                }
            else:
                probe = {"status": "resolved", "profile": value_profile.model_dump(mode="json")}
        (tmp_path / "actual-cov-value-owner-probe.json").write_text(
            json.dumps(probe, indent=2, sort_keys=True, default=str) + "\n"
        )
        assert refusal is None and gap is not None
        routing = cycle.value_port.candidate_n5_l1_routing
        assert routing is not None and routing.requirement_gap == gap
        assert routing.source_ref == simulation.candidate_simulation_n4_source_ref
        assert routing.context_job_ref == simulation.candidate_simulation_context_job_ref
        assert routing.n5_input_ref == simulation.candidate_simulation_n5_input_ref
        assert routing.n5_execution_ref == execution_ref
        assert routing.n5_result_ref == simulation.simulation_result_ref
        assert probe["status"] == "owner_refusal"
        assert probe["code"] == "acquire_data:value_panel_data_missing"
        from polisyos.pdc import gy_content_hash
        from polisyos.runtime.quality.acquisition_planner import (
            l1_variable_availability_requirement_gap,
        )

        expected_gap = l1_variable_availability_requirement_gap(
            candidate_id=n4.candidate.candidate_id,
            candidate_content_hash=n4.candidate.atom.content_hash,
            design_problem_ref=gy_content_hash(problem.model_dump(mode="json")),
            availability=probe["owner_gap_evidence"],
            authority_level=problem.authority_profile.requested_authority_level,
        )
        assert gap == expected_gap
        cov = cycle.grounding.acquisition_requirement
        assert cov is not None and cov.metadata["source"] == "cgf_grounding_coverage"
        assert cov.metadata["acquisition_family"] == "COV"
        assert cov.metadata["authority_purpose"] == "routing_only"
        assert request["accompanying_requirement_gaps"] == [cov.model_dump(mode="json")]
        report = cycle.acquisition_routing_report
        assert report is not None, "fiscal mixed-obligation planner did not produce a report"
        assert report.status == "blocked"
        assert report.basis_limitation_code in {
            "requirement_basis_not_established",
            "unbound_requirement_input_refused",
        }
        assert report.cost_estimation_status == "not_estimated"
        assert cycle.acquisition_cost_basis_record is None
        assert cycle.acquisition_receipt is None
        observed.append(run_id)

    with complete_candidate_cycle_catalog_source(source.root, monkeypatch) as prepared:
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_observer=observe,
            run_budget_usd=5.0,
        )
    assert result is not None and observed == [result["run_id"]]
