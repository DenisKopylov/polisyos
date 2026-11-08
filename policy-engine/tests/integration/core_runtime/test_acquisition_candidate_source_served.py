"""Protected candidate WDI controls, closed legacy re-entry, and a COV seed.

The refusal controls include both a native source without prior N5 and a genuine
selected labor N4/N5 source. The separate served fiscal COV seed retains its
actual NL/N4/N5 producer; no test promotes modeled inputs to authority.
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
    build_candidate_source_port_owners,
    candidate_route_for_closure,
    labor_candidate_profile,
    run_lane01_candidate_action_served,
    run_lane01_candidate_source_action_in_current_owner,
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
        assert str(refusal.value.__cause__) == "candidate_source_prior_n5_execution_not_established"
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
def test_genuine_labor_candidate_source_reentry_refuses_before_transport_with_prior_n5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    served_recorded_candidate_gateway: object,
) -> None:
    """Keep legacy candidate re-entry closed when its historical owner is absent.

    A genuine selected prior N4/N5 and eligible WDI route do not authorize the
    public @3 action until its historical frontier owner is composed. The exact
    refusal must leave transport, action state, events, and quota unchanged;
    fresh route-owner reads must retain the exact selected source.
    """
    from polisyos.runtime.quality import acquisition_planner
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as served
    from tests._helpers.acquisition_production import resolve_completed_wdi_route
    from tests._helpers.candidate_experiment_served_execution import (
        _standard_invocation_units,
    )

    quota = BudgetInvocationQuotaPolicy(
        allocation_id="labor-source-reentry-exhausted-standard",
        total_units=3,
        protected_units=1,
    )
    monkeypatch.setitem(
        acquisition_planner._ACQUISITION_GAP_BASIS,
        "global.unemployment_rate",
        {
            "basis_ref": "fixture-only:lane01-hypothetical-labor-cost:v1",
            "collection_mode": "Fixture-only modeled unemployment input",
            "expert_hours": 1,
            "calendar_days": 1,
        },
    )
    observed: dict[str, object] = {}

    def observe_seed(**values: object) -> None:
        control = values["control"]
        client = values["client"]
        run_id = values["run_id"]
        assert type(run_id) is str
        closure, mutation = resolve_completed_wdi_route(
            control,
            run_id=run_id,
            tenant_id=served.TENANT,
            cell_id=served.CELL,
        )
        selected = candidate_route_for_closure(control, closure)
        old_simulation = closure.source_cycle.simulation
        assert old_simulation.status == "joint_simulated"
        assert old_simulation.candidate_simulation_n4_source_ref is not None
        assert old_simulation.candidate_simulation_n5_input_ref is not None
        assert old_simulation.candidate_simulation_context_job_ref is not None
        assert old_simulation.simulation_result_ref is not None
        n5_input = CandidateSimulationN5InputV5.model_validate(
            artifacts.load_core_json_artifact(
                control._artifact_store,
                old_simulation.candidate_simulation_n5_input_ref,
            )
        )
        assert n5_input.profile.n5.replications == 2
        assert n5_input.profile.n5.horizon.start == n5_input.profile.n5.horizon.end == 0
        execution_payload = old_simulation.diagnostics.get(
            "candidate_simulation_execution_selected_ref"
        )
        assert isinstance(execution_payload, dict)
        execution_ref = artifacts.ArtifactRef.model_validate(execution_payload)
        n5_execution = CandidateSimulationExecutionV5.model_validate(
            artifacts.load_core_json_artifact(control._artifact_store, execution_ref)
        )
        assert n5_execution.n5_input_ref == old_simulation.candidate_simulation_n5_input_ref
        assert n5_execution.n5_result_ref == old_simulation.simulation_result_ref
        before_units = _standard_invocation_units(control=control, run_id=run_id)
        quota_profile = control._llm_producer_settlement_store.snapshot_safe().invocation_profiles[
            run_id
        ]
        assert quota_profile.allocation_id == quota.allocation_id
        assert (quota_profile.total_units, quota_profile.protected_units) == (3, 1)
        # This is the decisive cheap admission: inspect the real old producer,
        # selected N4/N5, owner scope and remaining quota before any source GET.
        assert before_units == quota_profile.total_units - quota_profile.protected_units
        port_owners = build_candidate_source_port_owners(
            tmp_path=Path(values["key_root"]) / "candidate-action",
            cas_root=Path(values["cas_root"]),
            control_service=control,
            selected=selected,
        )
        bridge = port_owners.bridge
        assert bridge is not None
        assert bridge.candidate_source_selection(closure) == selected
        assert bridge.candidate_source_reentry_preflight(closure=closure) is None
        assert (
            control.acquisition_route_sink.current_action_outcome(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                route_id=closure.route_id,
            )
            is None
        )

        def observe_action(ctx: SimpleNamespace) -> None:
            assert ctx.response.status_code == 409, ctx.response.text
            assert ctx.response.json()["code"] == "candidate_reentry_owner_not_available"
            assert ctx.job is None
            assert ctx.transport_calls == []
            assert ctx.diagnostic_events_after == ctx.diagnostic_events_before
            assert ctx.candidate_artifacts_after == ctx.candidate_artifacts_before
            assert ctx.route_projection_after == ctx.route_projection_before
            assert _standard_invocation_units(control=ctx.control, run_id=run_id) == before_units
            assert (
                ctx.control.acquisition_route_sink.current_action_outcome(
                    tenant_id=closure.tenant_id,
                    cell_id=closure.cell_id,
                    run_id=closure.run_id,
                    source_job_id=closure.source_job_id,
                    route_id=closure.route_id,
                )
                is None
            )
            observed["refused"] = True

        run_lane01_candidate_source_action_in_current_owner(
            tmp_path=Path(values["key_root"]),
            cas_root=Path(values["cas_root"]),
            monkeypatch=monkeypatch,
            client=client,
            control=control,
            closure=closure,
            mutation=mutation,
            selected=selected,
            trust=values["trust"],
            signers=values["signers"],
            identities=values["identities"],
            observer=observe_action,
        )
        observed["before_units"] = before_units
        observed["run_id"] = run_id
        reopened_closure, reopened_mutation = resolve_completed_wdi_route(
            control,
            run_id=run_id,
            tenant_id=closure.tenant_id,
            cell_id=closure.cell_id,
        )
        assert reopened_closure == closure
        assert reopened_mutation == mutation
        assert candidate_route_for_closure(control, reopened_closure) == selected

    # Keep the labor request, WMR and selected SKG produced above. Select only
    # the source root for the existing Catalog/L3/L6 readers so this route uses
    # bounded owner-built fixtures; no synthetic L6 slot/sign input is added.
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        complete_candidate_cycle_catalog_source,
    )

    bounded_source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "bounded-candidate-source-root",
        include_owner_slot_manifest=False,
    )
    from polisyos.runtime.quality.intervention_substrate import default_l6_bundle_paths

    # Preserve the exact five existing L6 data inputs needed by this action.
    # Keep owner_authority_bindings code-owned under REPO_ROOT; the selected
    # two-root reader below will bind these verbatim fixture bytes to its source.
    source_l6_paths = default_l6_bundle_paths(served.REPO_ROOT)
    selected_l6_paths = default_l6_bundle_paths(
        served.REPO_ROOT,
        source_owner_root=bounded_source.root,
    )
    selected_l6_names = (
        "intervention_knob_dictionary",
        "lex_intervention_map",
        "observation_to_contract_manifest",
        "policy_scenario_templates",
        "slot_family_manifest",
    )
    from polisyos.runtime.quality import substrate_registry

    with complete_candidate_cycle_catalog_source(
        bounded_source.root, monkeypatch, synthetic_usa_labor_scope=True
    ) as prepared_catalog:
        catalog_selection, catalog_source, _ = prepared_catalog
        # The canonical catalog fixture writer also creates starter L6 files.
        # Restore the exact already-selected source bytes before rebinding the
        # registry, so the selected N7 input and the actual L6 reader share one
        # content-addressed basis.
        for name in selected_l6_names:
            source_path = source_l6_paths[name]
            selected_path = selected_l6_paths[name]
            original_bytes = source_path.read_bytes()
            selected_path.parent.mkdir(parents=True, exist_ok=True)
            selected_path.write_bytes(original_bytes)
            assert selected_path.read_bytes() == original_bytes

        with substrate_registry.catalog_serving_source_scope(catalog_source):
            selected_registry = substrate_registry.build_substrate_registry_from_existing_catalogs(
                bounded_source.root,
                source_owner_root=bounded_source.root,
            )
            substrate_registry.require_catalog_source_registry_binding(
                bounded_source.root, selected_registry, catalog_source
            )
        prepared_catalog = (catalog_selection, catalog_source, selected_registry)
        result = served._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            provider_mode="synthetic_settled_candidate",
            seed_only_context_observer=observe_seed,
            run_budget_usd=5.0,
            invocation_quota_policy=quota,
            labor_seed=True,
            source_owner_root=bounded_source.root,
            prepared_catalog=prepared_catalog,
        )
    assert result is not None
    assert observed["run_id"] == result["run_id"]
    assert observed["before_units"] == 2
    assert observed["refused"] is True


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


def test_synthetic_labor_recording_preserves_parent_and_consistent_stages(tmp_path: Path) -> None:
    """Validate the synthetic derivative without claiming a runtime N4 result."""
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.pdc import gy_content_hash
    from polisyos.scientist.agent.drafter_models import _ConsolidationPayload, _CritiquePayload
    from polisyos.scientist.agent.formalizer import (
        _normalize_formalizer_payload_for_validation,
        build_production_metric_taxonomy,
    )
    from tests._helpers import acquisition_chain
    from tests._helpers.controlled_candidate_profile import _current_compiler_problem
    from tests._helpers.lane01_candidate_problem import (
        LABOR_SCOPE_SOURCE,
        served_labor_candidate_problem,
    )

    original = acquisition_chain.load_served_wdi_generation_recording()
    original_bytes = json.dumps(original, sort_keys=True)
    fiscal = acquisition_chain.controlled_served_wdi_problem(
        _current_compiler_problem(original), raw_request=acquisition_chain.SERVED_WDI_FISCAL_REQUEST
    )
    problem = served_labor_candidate_problem(
        fiscal,
        raw_request=f"{LABOR_SCOPE_SOURCE} {acquisition_chain.SERVED_WDI_CANDIDATE_ONLY_SOURCE}",
    )
    legacy = acquisition_chain.controlled_served_wdi_generation_recording(
        original, outcome_variable="global.tax_rate"
    )
    assert legacy == acquisition_chain.controlled_served_wdi_generation_recording(
        original, outcome_variable="global.tax_rate", labor_problem=None
    )
    profile = acquisition_chain.synthetic_served_wdi_provider_profile(
        original, problem=problem, evidence_root=tmp_path, labor_scope=True
    )
    controlled = acquisition_chain.controlled_served_wdi_generation_recording(
        original, outcome_variable="global.unemployment_rate", labor_problem=problem
    )
    assert controlled["derived_from_content_hash"] == original["recording_content_hash"]
    assert profile.controlled_recording_content_hash == controlled["recording_content_hash"]
    rows = {stage: json.loads(row) for stage, row in profile.response_rows}
    assert set(rows) == {
        "draft",
        "drafter_multipass",
        "drafter_consolidation",
        "formalizer",
        "critic",
    }
    for row in rows.values():
        assert row["raw_response_hash"] == gy_content_hash(row["raw_response"])
        assert row["parent_response_hash"].startswith("sha256:")
        matches = [
            derived
            for parent, derived in zip(original["responses"], controlled["responses"], strict=True)
            if parent.get("role") == row["parent_role"]
            and parent.get("raw_response_hash") == row["parent_response_hash"]
        ]
        assert len(matches) == 1
        assert matches[0]["raw_response"] == row["raw_response"]
        assert matches[0]["raw_response_hash"] == row["raw_response_hash"]
        assert not any(
            word in row["raw_response"].lower() for word in ("ukrain", "tax_credit", "guarantee")
        )
        assert all(
            word in row["raw_response"].lower()
            for word in ("usa", "2024", "total_labor_force", "unemployment")
        )
    draft = _ConsolidationPayload.model_validate(json.loads(rows["draft"]["raw_response"]))
    _CritiquePayload.model_validate(json.loads(rows["drafter_multipass"]["raw_response"]))
    assert len(draft.interventions) == 1
    formalizer, _events = _normalize_formalizer_payload_for_validation(
        json.loads(rows["formalizer"]["raw_response"]),
        taxonomy=build_production_metric_taxonomy(),
        fail_unknown_metrics=False,
        schema_healing_mode="audit",
        draft_id="synthetic_usa_labor_candidate_draft",
    )
    bundle = TrinityBundle.model_validate(formalizer)
    assert bundle.problem_frame.domain == "social"
    assert bundle.problem_frame.objectives[0].metric_id == "unemployment_rate"
    assert bundle.problem_frame.objectives[0].direction == "minimize"
    assert len(bundle.policy_spec.interventions) == len(bundle.policy_spec.parameters) == 1
    assert bundle.policy_spec.interventions[0].kind == "budget_allocation_multiplier"
    assert bundle.policy_spec.parameters[0].param_path == "multiplier"
    critic = json.loads(rows["critic"]["raw_response"])
    assert critic["verdict"] == "NEEDS_REVISION" and critic["issues"]
    assert critic["ir_ref"] == gy_content_hash(json.loads(rows["formalizer"]["raw_response"]))
    assert json.dumps(original, sort_keys=True) == original_bytes
    assert profile.source_recording_content_hash == original["recording_content_hash"]


def test_genuine_labor_candidate_seed_reopens_selected_n4_and_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, served_recorded_candidate_gateway
) -> None:
    """Exercise the declared labor request through the actual N4 and cycle owners."""
    import hashlib
    from contextlib import contextmanager
    from dataclasses import replace

    from polisyos.data_requirement import (
        DataRequirementCompilationReport,
        compiled_requirements_for_world_slot,
    )
    from polisyos.fabric.connectors.profiles import SourceProfileRegistry
    from polisyos.fabric.data_plane import build_live_execution_authorization
    from polisyos.runtime.http.services.control.generation_cycle import (
        CompiledRecursiveGenerationCycleRun,
    )
    from polisyos.runtime.quality.acquisition_planner import (
        _n7_verify_configured_candidate_report_cycle,
        validate_persisted_data_requirement_compilation_report,
    )
    from polisyos.runtime.quality.acquisition_route_loop import AcquisitionRouteLoop
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedExperimentPolicyTemplate,
        CandidateUnpricedPolicyBinding,
        CandidateUnpricedPolicyScope,
        issue_candidate_unpriced_experiment_policy,
        persist_candidate_unpriced_policy,
        read_candidate_unpriced_policy,
        resolve_current_candidate_unpriced_policy,
    )
    from polisyos.runtime.quality.candidate_experiment_policy_issuer import (
        prepare_candidate_experiment_policies_for_completed_job,
    )
    from polisyos.runtime.quality.candidate_simulation import (
        CandidateSimulationExecutionV5,
        CandidateSimulationN5InputV5,
    )
    from polisyos.runtime.quality.generation_source import GenerationSourceRepository
    from polisyos.scientist.orchestration.engine import BudgetInvocationQuotaPolicy
    from tests._helpers import acquisition_served_history as fixture
    from tests._helpers.candidate_cycle_source_profile import (
        build_candidate_cycle_substrate_route_inputs,
        complete_candidate_cycle_catalog_source,
    )
    from tests._helpers.lane01_candidate_action_served import (
        build_candidate_experiment_issuer_port,
    )
    from tests.unit.fabric.data_plane.test_evidence_journal import (
        _authorization_request,
        _harness_receipt,
        _source_profile,
    )

    source = build_candidate_cycle_substrate_route_inputs(
        tmp_path / "labor-source", include_owner_slot_manifest=True
    )
    observed = []
    quota = BudgetInvocationQuotaPolicy(
        allocation_id="labor-experiment-route", total_units=3, protected_units=1
    )

    def observe(**values) -> None:
        control, job, run_id = values["control"], values["job"], values["run_id"]
        terminal = control.resolve_completed_control_job_core_run_source(
            job, expected_control_run_id=run_id, tenant_id=fixture.TENANT, cell_id=fixture.CELL
        )
        selected = artifacts.ArtifactRef.model_validate(
            job.progress["compiled_recursive_generation_cycle_artifact_ref"]
        )
        assert any(
            artifacts.artifact_ref_identity_key(ref)
            == artifacts.artifact_ref_identity_key(selected)
            for ref in terminal.manifest.outputs
        )
        store = artifacts.FileSystemCAS.open_existing_read_only(values["cas_root"])
        payload = artifacts.load_core_json_artifact(store, job.payload_ref)
        assert payload["run_id"] == run_id
        assert Decimal(str(payload["run_budget_usd"])) == Decimal("5")
        compiled = CompiledRecursiveGenerationCycleRun.model_validate(
            artifacts.load_core_json_artifact(store, selected)
        )
        problem = compiled.design_problem
        assert problem.jurisdiction_time.region == "USA"
        assert problem.outcome_of_interest.target_variable == "global.unemployment_rate"
        assert problem.candidate_lever_space.allowed_operator_kinds == [
            "budget_allocation_multiplier"
        ]
        occurrences = [
            (leaf.cycle_run, cycle)
            for leaf in compiled.recursive_run.leaf_nodes
            if leaf.cycle_run is not None
            for cycle in leaf.cycle_run.cycles
        ]
        assert len(occurrences) == 1
        generation, cycle = occurrences[0]
        (tmp_path / "actual-labor-candidate-cycle.json").write_text(
            json.dumps(
                {
                    "cycles": [cycle.model_dump(mode="json")],
                    "limitations": ["synthetic_scope_not_empirical"],
                },
                indent=2,
                default=str,
            )
            + "\n"
        )
        simulation = cycle.simulation
        assert simulation.status == "joint_simulated"
        assert cycle.value_port.status == "value_pending_n8"
        assert "candidate_scenario_n5_only" in cycle.value_port.authority_blockers
        assert simulation.candidate_simulation_n4_source_ref is not None
        assert simulation.candidate_simulation_context_job_ref is not None
        assert simulation.candidate_simulation_n5_input_ref is not None
        assert simulation.simulation_result_ref is not None
        for ref in (
            simulation.candidate_simulation_n4_source_ref,
            simulation.candidate_simulation_context_job_ref,
            simulation.candidate_simulation_n5_input_ref,
            simulation.simulation_result_ref,
        ):
            assert ref.manifest_profile_sha256
        execution_ref = artifacts.ArtifactRef.model_validate(
            simulation.diagnostics["candidate_simulation_execution_selected_ref"]
        )
        assert execution_ref.manifest_profile_sha256
        execution = CandidateSimulationExecutionV5.model_validate(
            artifacts.load_core_json_artifact(store, execution_ref)
        )
        assert execution.n5_input_ref == simulation.candidate_simulation_n5_input_ref
        assert execution.n5_result_ref == simulation.simulation_result_ref
        assert execution.run_id == run_id and execution.job_id == job.job_id
        artifacts.load_core_json_artifact(store, simulation.simulation_result_ref)
        n5_input = CandidateSimulationN5InputV5.model_validate(
            artifacts.load_core_json_artifact(store, simulation.candidate_simulation_n5_input_ref)
        )
        world = n5_input.profile.context_inputs.world_model_record
        assert world.authority_status == "limited"
        assert {
            "source_time_not_established",
            "source_to_target_measurement_contract_not_established",
            "causal_coupling_not_established",
        }.issubset(world.limitations.admissibility_blockers)
        assert n5_input.context_job_ref == simulation.candidate_simulation_context_job_ref
        assert n5_input.n4_source_ref == simulation.candidate_simulation_n4_source_ref
        n4 = GenerationSourceRepository(store).load_candidate_scenario_source_for_n5(
            n5_input.n4_source_ref,
            expected_run_id=run_id,
            expected_job_id=job.job_id,
            expected_tenant_id=fixture.TENANT,
            expected_cell_id=fixture.CELL,
        )
        assert n4.stable_subject_ref == compiled.design_problem_ref
        assert n4.candidate.candidate_id == cycle.selected_candidate_ref
        assert n5_input.profile.profile_selection_ref == n4.profile_selection_ref
        atom = n4.candidate.atom
        assert atom.direct_effect_bundle.mechanism_id == "budget_allocation_multiplier"
        assert atom.direct_effect_bundle.params == {"multiplier": 2}
        assert atom.causal_do_expr.write_variables == ("government.balance",)
        parameters = [
            parameter
            for parameter in n4.proposal.trinity_bundle.policy_spec.parameters
            if parameter.intervention_id == n4.candidate.intervention_id
        ]
        assert len(parameters) == 1
        parameter = parameters[0]
        assert parameter.param_path == "multiplier"
        assert Decimal(str(parameter.default_value)) == Decimal("2")
        assert Decimal(str(parameter.min_value)) == Decimal("1")
        assert Decimal(str(parameter.max_value)) == Decimal("2")
        report = cycle.acquisition_routing_report
        assert report is not None and report.requirement_basis_binding is not None
        binding = report.requirement_basis_binding
        assert not validate_persisted_data_requirement_compilation_report(
            store, binding, require_selected_writer_profile=True
        )
        compilation = DataRequirementCompilationReport.model_validate(
            artifacts.load_core_json_artifact(store, binding.compiler_report_ref)
        )
        matches = compiled_requirements_for_world_slot(
            world_slot="global.unemployment_rate",
            specs=compilation.specs,
            capability_resolutions=compilation.capability_requirement_resolutions,
        )
        assert len(matches) == 1
        resolutions = [
            row
            for row in compilation.capability_requirement_resolutions or ()
            if row.query.construct_id == "labor.unemployment_rate"
            and row.candidate_discovery is not None
        ]
        assert len(resolutions) == 1
        resolution = resolutions[0]
        assert resolution.query.geography == "USA"
        assert resolution.query.population_filter == {"type": "total_labor_force"}
        assert resolution.query.time_window.start == "2024-01-01"
        assert resolution.query.time_window.end == "2024-12-31"
        candidates = [
            candidate
            for candidate in resolution.candidate_discovery.candidates
            if any(
                asset.get("metadata", {}).get("catalog_fetch_binding", {}).get("dataset_id")
                == "SL.UEM.TOTL.ZS"
                and asset.get("metadata", {}).get("target_world_slot") == "global.unemployment_rate"
                for asset in candidate.source_assets
            )
        ]
        assert len(candidates) == 1 and candidates[0].limitations
        assert candidates[0].descriptor["identification_mode"] == "candidate_unverified"
        assert candidates[0].descriptor["rights_envelope"]["claim_evidence_use_allowed"] is False
        from tests._helpers.acquisition_served_history import REPO_ROOT

        rows_path = (
            REPO_ROOT / "architecture/policy_design_case/layer2_s3_governed_capability_rows.json"
        )
        (tmp_path / "labor-selected-descriptor.json").write_text(
            json.dumps(
                {
                    "governed_rows_path": str(rows_path),
                    "governed_rows_sha256": hashlib.sha256(rows_path.read_bytes()).hexdigest(),
                    "compiler_report_ref": binding.compiler_report_ref.model_dump(mode="json"),
                    "capability_index_ref": resolution.candidate_discovery.capability_index_ref,
                    "requested_scope": problem.runtime_hints["n7_scope_profile"],
                    "selected_requirement": matches[0].model_dump(mode="json"),
                    "query": resolution.query.model_dump(mode="json"),
                    "candidate": candidates[0].model_dump(mode="json"),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n"
        )
        assert report.candidate_lineage is not None
        assert cycle.acquisition_routing_report_ref is not None
        assert cycle.grounding.acquisition_requirement is not None
        join = {
            "artifact_store": store,
            "control_store": control._control_store,
            "report": report,
            "report_ref": cycle.acquisition_routing_report_ref,
            "generation_run": generation,
            "source_cycle": cycle,
            "tenant_id": fixture.TENANT,
            "cell_id": fixture.CELL,
            "run_id": run_id,
            "source_job_id": job.job_id,
            "design_problem_ref": compiled.design_problem_ref,
        }
        selected_source = _n7_verify_configured_candidate_report_cycle(**join)
        without_cov = cycle.model_copy(
            update={
                "grounding": cycle.grounding.model_copy(update={"acquisition_requirement": None})
            }
        )
        with pytest.raises(ValueError):
            _n7_verify_configured_candidate_report_cycle(**{**join, "source_cycle": without_cov})
        without_cov_run = generation.model_copy(
            update={
                "cycles": tuple(
                    without_cov if item.cycle_index == cycle.cycle_index else item
                    for item in generation.cycles
                )
            }
        )
        with pytest.raises(ValueError, match="n7_candidate_report_source_owner_mismatch"):
            _n7_verify_configured_candidate_report_cycle(
                **{**join, "generation_run": without_cov_run, "source_cycle": without_cov}
            )
        foreign_input = simulation.candidate_simulation_n5_input_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
        assert foreign_input.manifest_profile_sha256 != (
            simulation.candidate_simulation_n5_input_ref.manifest_profile_sha256
        )
        substituted = cycle.model_copy(
            update={
                "simulation": simulation.model_copy(
                    update={"candidate_simulation_n5_input_ref": foreign_input}
                )
            }
        )
        with pytest.raises((OSError, ValueError)):
            _n7_verify_configured_candidate_report_cycle(**{**join, "source_cycle": substituted})
        substituted_run = generation.model_copy(
            update={
                "cycles": tuple(
                    substituted if item.cycle_index == cycle.cycle_index else item
                    for item in generation.cycles
                )
            }
        )
        with pytest.raises((OSError, ValueError)):
            _n7_verify_configured_candidate_report_cycle(
                **{**join, "generation_run": substituted_run, "source_cycle": substituted}
            )
        route = AcquisitionRouteLoop(
            control_store=control._control_store,
            artifact_store=control._artifact_store,
            event_log=control._diagnostic_event_log,
            core_source_resolver=control.resolve_completed_control_job_core_run_source,
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
        )
        with pytest.raises(
            acquisition_route_loop.AcquisitionRouteClosureError, match="costed_route_not_unique"
        ):
            route.resolve_current_route(run_id=run_id)
        closure = SimpleNamespace(
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
            run_id=run_id,
            source_job_id=job.job_id,
            source_payload_ref=job.payload_ref,
            capability_manifest_ref=job.capability_manifest_ref,
        )
        evidence = control.verify_candidate_experiment_intent(closure=closure)
        foreign_closure = SimpleNamespace(**{**vars(closure), "tenant_id": "foreign-tenant"})
        with pytest.raises(ValueError):
            control.verify_candidate_experiment_intent(closure=foreign_closure)
        snapshot = control._llm_producer_settlement_store.snapshot_safe()
        selected_quota = snapshot.invocation_profiles[run_id]
        assert selected_quota.allocation_id == quota.allocation_id
        assert any(
            item.run_id == run_id
            and item.profile_digest == selected_quota.profile_digest
            and item.purpose == "standard"
            and item.status == "completed"
            for item in snapshot.invocation_reservations.values()
        )
        policy_scope = CandidateUnpricedPolicyScope(
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
            run_id=run_id,
            source_job_id=job.job_id,
            design_problem_ref=compiled.design_problem_ref,
            design_problem_basis_ref=selected_source.design_problem_basis_ref,
            source_cycle_index=cycle.cycle_index,
            candidate_id=cycle.selected_candidate_ref,
            candidate_content_hash=cycle.selected_candidate_content_hash,
            requirement_id=resolution.query.requirement_id,
            compiled_requirement_ref=matches[0].requirement_id,
            candidate_digest=candidates[0].content_digest,
            planner_report_hash=agent_action_content_hash(report),
            compiled_ref=selected,
            planner_report_ref=cycle.acquisition_routing_report_ref,
            compiler_report_ref=binding.compiler_report_ref,
            configured_port_source_ref=report.candidate_lineage.port_source_ref,
        )
        # Controlled harness evidence names the same labor dataset; live fetch
        # authorization is independently rederived by the executor, not here.
        authorization_request = _authorization_request()
        authorization_request["request_dataset_id"] = "SL.UEM.TOTL.ZS"
        authorization_request["variable_id"] = "global.unemployment_rate"
        harness = _harness_receipt()
        harness["dry_run_attempts"] = tuple(
            {**attempt, "request_dataset_id": "SL.UEM.TOTL.ZS"}
            for attempt in harness["dry_run_attempts"]
        )
        authorization = build_live_execution_authorization(
            attempt_id="n13b-worldbank-cpi-001",
            connector_id="worldbank.wdi",
            request_dataset_id="SL.UEM.TOTL.ZS",
            request=authorization_request,
            schema_contract=authorization_request["schema_contract"],
            source_profile=_source_profile(),
            baseline_sha256="sha256:" + "f" * 64,
            family_receipt=harness,
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
        )
        policy = issue_candidate_unpriced_experiment_policy(
            scope=policy_scope,
            live_authorization=authorization,
            n5_quota_profile=selected_quota,
            source_payload_ref=evidence.source_payload_ref,
            request_content_hash=evidence.request_content_hash,
            original_metered_budget_usd=evidence.run_budget_usd,
            limitations=(
                "acquisition_monetary_cost_not_established",
                "n5_monetary_cost_not_established",
                "per_call_usd_reservation_not_established",
                "candidate_only_no_publication_authority",
                "candidate_experiment_voi_not_established",
                "controlled_synthetic_harness_not_live_authority",
            ),
        )
        policy_ref = persist_candidate_unpriced_policy(
            store=control._artifact_store, event_log=control._diagnostic_event_log, policy=policy
        )
        original_providers = control._registry_providers
        control._registry_providers = replace(
            original_providers,
            candidate_unpriced_policy_bindings=(
                CandidateUnpricedPolicyBinding(scope=policy_scope, policy_ref=policy_ref),
            ),
        )
        experiment = route.resolve_candidate_experiment_origin(run_id=run_id)
        assert experiment.policy_ref == policy_ref
        assert experiment.monetary_cost == experiment.action_authority == "not_established"
        assert cycle.voi_decision.scheduler_action == "reject"
        assert cycle.voi_decision.scheduler_reason == "roi_below_threshold"
        assert experiment.source_cycle.voi_decision == cycle.voi_decision
        action_service = values["action_service"]
        assert action_service is not None
        projection = action_service.get_candidate_experiment_route(
            tenant_id=fixture.TENANT, cell_id=fixture.CELL, run_id=run_id
        )
        assert projection.route_id == experiment.route_id
        assert projection.replay_pins.policy_ref == policy_ref
        assert projection.replay_pins.request_content_hash == evidence.request_content_hash
        assert projection.scheduler_action == "reject"
        assert projection.scheduler_reason == "roi_below_threshold"
        assert projection.action_authority == projection.monetary_cost == "not_established"
        assert projection.publication_authority is False
        from pydantic import ValidationError

        from polisyos.runtime.http.services.acquisition_action_service import (
            AcquisitionActionServiceError,
            CandidateExperimentRouteMutationRequest,
            CandidateExperimentRouteReplayPins,
        )

        request = CandidateExperimentRouteMutationRequest(
            route_id=projection.route_id,
            replay_pins=projection.replay_pins,
            idempotency_key="controlled-experiment-probe",
        )
        assert (
            action_service._validate_candidate_experiment_request(
                tenant_id=fixture.TENANT, cell_id=fixture.CELL, run_id=run_id, request=request
            )
            == projection
        )
        foreign_policy_view = policy_ref.model_copy(
            update={"manifest_profile_sha256": "sha256:" + "f" * 64}
        )
        foreign_request = request.model_copy(
            update={
                "replay_pins": request.replay_pins.model_copy(
                    update={"policy_ref": foreign_policy_view}
                )
            }
        )
        with pytest.raises(
            AcquisitionActionServiceError, match="candidate_experiment_route_revalidation_required"
        ):
            action_service._validate_candidate_experiment_request(
                tenant_id=fixture.TENANT,
                cell_id=fixture.CELL,
                run_id=run_id,
                request=foreign_request,
            )

        malformed_pins = projection.replay_pins.model_dump(mode="json")
        malformed_pins["policy_ref"]["kind"] = "fabric.data_snapshot"
        with pytest.raises(ValidationError, match="candidate_experiment_selected_profile_required"):
            CandidateExperimentRouteReplayPins.model_validate(malformed_pins)

        class SameSelectedView(artifacts.ArtifactRef):
            pass

        class ExtendedSelectedView(artifacts.ArtifactRef):
            extra_semantics: str = "foreign"

        pin_values = {
            name: getattr(projection.replay_pins, name)
            for name in CandidateExperimentRouteReplayPins.model_fields
        }
        same_view = SameSelectedView.model_validate(policy_ref.model_dump(mode="python"))
        assert (
            CandidateExperimentRouteReplayPins.model_validate(
                {**pin_values, "policy_ref": same_view}
            ).policy_ref.manifest_profile_sha256
            == policy_ref.manifest_profile_sha256
        )
        extended_view = ExtendedSelectedView.model_validate(policy_ref.model_dump(mode="python"))
        with pytest.raises(ValidationError, match="candidate_experiment_selected_profile_required"):
            CandidateExperimentRouteReplayPins.model_validate(
                {**pin_values, "policy_ref": extended_view}
            )
        for payload_ref, request_hash, cap in (
            ("sha256:" + "e" * 64, evidence.request_content_hash, evidence.run_budget_usd),
            (evidence.source_payload_ref, "sha256:" + "e" * 64, evidence.run_budget_usd),
            (evidence.source_payload_ref, evidence.request_content_hash, Decimal("6")),
        ):
            foreign_policy = issue_candidate_unpriced_experiment_policy(
                scope=policy_scope,
                live_authorization=authorization,
                n5_quota_profile=selected_quota,
                source_payload_ref=payload_ref,
                request_content_hash=request_hash,
                original_metered_budget_usd=cap,
                limitations=policy.limitations,
            )
            foreign_ref = persist_candidate_unpriced_policy(
                store=control._artifact_store,
                event_log=control._diagnostic_event_log,
                policy=foreign_policy,
            )
            control._registry_providers = replace(
                original_providers,
                candidate_unpriced_policy_bindings=(
                    CandidateUnpricedPolicyBinding(scope=policy_scope, policy_ref=foreign_ref),
                ),
            )
            with pytest.raises(
                acquisition_route_loop.AcquisitionRouteClosureError,
                match="candidate_experiment_intent_not_established",
            ):
                route.resolve_candidate_experiment_origin(run_id=run_id)
        control._registry_providers = original_providers
        with pytest.raises(
            acquisition_route_loop.AcquisitionRouteClosureError,
            match="candidate_experiment_policy_not_unique",
        ):
            route.resolve_candidate_experiment_origin(run_id=run_id)
        control._registry_providers = replace(
            original_providers,
            candidate_unpriced_policy_bindings=(
                CandidateUnpricedPolicyBinding(scope=policy_scope, policy_ref=policy_ref),
            ),
        )

        @contextmanager
        def block_selected_manifest(artifact_id, profile):
            owner = control._artifact_store
            original_path = owner._manifest_path_for_ref(artifact_id, profile)
            assert original_path.is_file() and not original_path.is_symlink()
            hits = []
            if values.get("retained_no_mutation") is True:
                # Consume-only replay: deny the exact read path without moving
                # or altering the retained producer's original manifest.
                original_resolver = owner._manifest_path_for_ref
                with monkeypatch.context() as patcher:

                    def denied_path(aid, selected_profile):
                        if str(aid) == str(artifact_id) and selected_profile == profile:
                            hits.append(True)
                            return tmp_path / "controlled-missing-manifest"
                        return original_resolver(aid, selected_profile)

                    patcher.setattr(owner, "_manifest_path_for_ref", denied_path)
                    yield hits
                return
            withheld = original_path.with_name(original_path.name + ".labor-test-withheld")
            assert not withheld.exists()
            original_path.rename(withheld)
            try:
                assert not original_path.exists()
                yield hits
            finally:
                withheld.rename(original_path)

        with (
            block_selected_manifest(
                artifacts.ArtifactID.model_validate(job.payload_ref), None
            ) as denied_payload,
            pytest.raises((OSError, ValueError)),
        ):
            route.resolve_candidate_experiment_origin(run_id=run_id)
        if values.get("retained_no_mutation") is True:
            assert denied_payload
        source_ref = report.candidate_lineage.port_source_ref
        with (
            block_selected_manifest(
                source_ref.artifact_id, source_ref.manifest_profile_sha256
            ) as denied_source,
            pytest.raises(acquisition_route_loop.AcquisitionRouteClosureError),
        ):
            route.resolve_candidate_experiment_origin(run_id=run_id)
        if values.get("retained_no_mutation") is True:
            assert denied_source
        route.resolve_candidate_experiment_origin(run_id=run_id)
        assert control._llm_producer_settlement_store.snapshot_safe() == snapshot
        control._registry_providers = original_providers

        # Exercise the completed-source issuer using the actual durable V5
        # request, N7 compiler lineage, N5 quota, and a canonical test-owned
        # WDI authority. The fixture authority is not production provenance.
        issuer_owners = build_candidate_experiment_issuer_port(
            tmp_path=tmp_path / "candidate-experiment-issuer",
            artifact_store=control._artifact_store,
        )
        issuer_port = issuer_owners.port
        issuer_quota = snapshot.invocation_profiles[run_id]
        issuer_template = CandidateUnpricedExperimentPolicyTemplate(
            tenant_id=fixture.TENANT,
            cell_id=fixture.CELL,
            authority_entry_id=issuer_owners.entry.entry_id,
            authority_registry_sha256=issuer_owners.registry.content_sha256,
            authority_provision_sha256=issuer_owners.authority.provision_content_sha256,
            attempt_id=issuer_port._provision.live_harness_receipts[0].attempt_id,
            max_http_response_bytes=65_536,
            max_http_decompressed_bytes=65_536,
            max_http_timeout_seconds=15.0,
            max_standard_n5_invocations=(issuer_quota.total_units - issuer_quota.protected_units),
            max_metered_reentry_usd=Decimal("1.00"),
        )
        issuer_providers = replace(
            original_providers,
            source_profiles=SourceProfileRegistry.get_instance(),
            candidate_unpriced_policy_bindings=(),
            candidate_unpriced_policy_templates=(issuer_template,),
        )
        control._registry_providers = issuer_providers
        from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
            POLICY_EVENT,
        )

        policy_events_before = control._diagnostic_event_log.list_events(
            run_id=run_id, job_id=job.job_id, limit=500
        )
        event_count_before = sum(
            row.event.event_type == POLICY_EVENT for row in policy_events_before
        )
        quota_before_issuer = control._llm_producer_settlement_store.snapshot_safe()
        import polisyos.runtime.http.services.acquisition_surface_execution as acquisition_surface

        with monkeypatch.context() as issuer_patch:
            issuer_patch.setattr(
                acquisition_surface,
                "build_production_world_bank_wdi_execution_port",
                lambda *, control_service: issuer_port
                if control_service is control
                else pytest.fail("issuer requested a port for a different control owner"),
            )
            issued_refs = prepare_candidate_experiment_policies_for_completed_job(
                control_service=control,
                source_job_id=job.job_id,
            )
            assert len(issued_refs) == 1
            issued_ref = issued_refs[0]
            selected_ref, issued = resolve_current_candidate_unpriced_policy(
                control_service=control,
                scope=read_candidate_unpriced_policy(
                    store=control._artifact_store,
                    event_log=control._diagnostic_event_log,
                    ref=issued_ref,
                ).scope,
            )
            assert artifacts.artifact_ref_identity_key(selected_ref) == (
                artifacts.artifact_ref_identity_key(issued_ref)
            )
            assert issued.scope.tenant_id == fixture.TENANT
            assert issued.scope.cell_id == fixture.CELL
            assert issued.scope.run_id == run_id
            assert issued.scope.source_job_id == job.job_id
            assert issued.scope.design_problem_ref == compiled.design_problem_ref
            assert issued.scope.design_problem_basis_ref == selected_source.design_problem_basis_ref
            assert issued.scope.source_cycle_index == cycle.cycle_index
            assert issued.scope.candidate_id == cycle.selected_candidate_ref
            assert issued.scope.candidate_content_hash == cycle.selected_candidate_content_hash
            assert issued.scope.requirement_id == resolution.query.requirement_id
            assert issued.scope.compiled_requirement_ref == matches[0].requirement_id
            assert issued.scope.candidate_digest == candidates[0].content_digest
            assert issued.scope.planner_report_hash == agent_action_content_hash(report)
            assert issued.scope.compiled_ref == selected
            assert issued.scope.planner_report_ref == cycle.acquisition_routing_report_ref
            assert issued.scope.compiler_report_ref == binding.compiler_report_ref
            assert (
                issued.scope.configured_port_source_ref == report.candidate_lineage.port_source_ref
            )
            assert issued.source_payload_ref == evidence.source_payload_ref
            assert issued.request_content_hash == evidence.request_content_hash
            assert issued.original_metered_budget_usd == evidence.run_budget_usd
            assert issued.live_authorization.authorized is True
            assert issued.live_authorization.attempt_id == issuer_template.attempt_id
            assert issued.purpose == "bounded_candidate_experiment_voi_unknown"
            assert issued.information_value == "not_established"
            assert issued.monetary_cost == "not_established"
            assert issued.hard_usd_reservation is False
            assert issued.observed_admission is False
            assert issued.publication_authority is False
            issued_origin = route.resolve_candidate_experiment_origin(run_id=run_id)
            assert issued_origin.policy_ref == issued_ref
            assert (
                issued_origin.monetary_cost == issued_origin.action_authority == "not_established"
            )
            policy_events_after_issue = control._diagnostic_event_log.list_events(
                run_id=run_id, job_id=job.job_id, limit=500
            )
            event_count_after_issue = sum(
                row.event.event_type == POLICY_EVENT for row in policy_events_after_issue
            )
            assert event_count_after_issue == event_count_before + 1
            assert control._llm_producer_settlement_store.snapshot_safe() == quota_before_issuer
            assert not issuer_port._runtime_state_root.exists()

            repeated_refs = prepare_candidate_experiment_policies_for_completed_job(
                control_service=control,
                source_job_id=job.job_id,
            )
            assert len(repeated_refs) == 1
            assert artifacts.artifact_ref_identity_key(repeated_refs[0]) == (
                artifacts.artifact_ref_identity_key(issued_ref)
            )
            policy_events_after_repeat = control._diagnostic_event_log.list_events(
                run_id=run_id, job_id=job.job_id, limit=500
            )
            assert (
                sum(row.event.event_type == POLICY_EVENT for row in policy_events_after_repeat)
                == event_count_after_issue
            )
            assert control._llm_producer_settlement_store.snapshot_safe() == quota_before_issuer
            assert not issuer_port._runtime_state_root.exists()

            control._registry_providers = replace(
                issuer_providers, candidate_unpriced_policy_templates=()
            )
            with pytest.raises(ValueError, match="candidate_unpriced_policy_not_selected"):
                resolve_current_candidate_unpriced_policy(
                    control_service=control, scope=issued.scope
                )
            control._registry_providers = issuer_providers
            restored_ref, restored_policy = resolve_current_candidate_unpriced_policy(
                control_service=control, scope=issued.scope
            )
            assert artifacts.artifact_ref_identity_key(restored_ref) == (
                artifacts.artifact_ref_identity_key(issued_ref)
            )
            assert restored_policy == issued
            assert control._llm_producer_settlement_store.snapshot_safe() == quota_before_issuer

        observed.append(run_id)

    with complete_candidate_cycle_catalog_source(
        source.root, monkeypatch, synthetic_usa_labor_scope=True
    ) as prepared:
        entries = prepared[2].resolve(family_id="macro_state")
        assert entries
        assert all(
            entry.schema_regime.schema_regime_id.startswith("synthetic_usa_labor_")
            for entry in entries
        )
        assert all(entry.identification_mode == "bounds_only" for entry in entries)
        result = fixture._produce_served_acquisition_history(
            tmp_path,
            monkeypatch,
            served_recorded_candidate_gateway,
            source_owner_root=source.root,
            prepared_catalog=prepared,
            provider_mode="synthetic_settled_candidate",
            seed_only_observer=observe,
            run_budget_usd=5.0,
            run_budget_scope="metered_paid_producers_and_bounded_candidate",
            candidate_acquisition_intent="bounded_experiment_voi_unknown",
            invocation_quota_policy=quota,
            labor_seed=True,
        )
    assert result is not None and observed == [result["run_id"]]
