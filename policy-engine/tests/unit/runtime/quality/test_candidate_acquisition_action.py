"""Persisted candidate-experiment action reader controls for source identity."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest


def _hash(digit: str) -> str:
    return "sha256:" + digit * 64


def test_experiment_action_reader_replays_emitted_source_kind_and_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real reader accepts the emitted source and rejects kind or scope drift.

    The candidate WDI source, phase and action receipt are persisted through real
    writers and reopened from CAS. Only the upstream action-head projection is a
    test-owned owner boundary; this does not establish current SQL lease or N5 work.
    """
    from polisyos.core import artifacts
    from polisyos.core.artifacts.store import FileSystemCAS
    from polisyos.data_requirement import DataRequirementCompilationReport
    from polisyos.fabric import data_plane
    from polisyos.runtime.http.services.acquisition_surface_execution import (
        WORLD_BANK_WDI_ROUTE_BINDING_SCHEMA_VERSION,
        WorldBankWDIRouteExecutionBinding,
    )
    from polisyos.runtime.http.services.control.run_lifecycle import (
        AcquisitionRouteLoopAuthoritySink,
        VerifiedAcquisitionActionOutcome,
        VerifiedAcquisitionActionPhase,
    )
    from polisyos.runtime.http.services.control_plane_store import (
        AcquisitionActionHeadRecord,
        ControlPlaneStore,
    )
    from polisyos.runtime.quality.acquisition_executor import LiveCatalogExecutionConstraints
    from polisyos.runtime.quality.acquisition_route_loop import (
        AcquisitionCandidateExperimentPhaseReceipt,
    )
    from polisyos.runtime.quality.acquisition_unpriced_candidate_policy import (
        CandidateUnpricedPolicyScope,
    )
    from polisyos.runtime.quality.acquisition_world_growth import (
        AcquisitionCandidateSourceRoute,
        AcquisitionWorldGrowthBridge,
    )
    from polisyos.runtime.quality.candidate_acquisition_action import (
        CANDIDATE_ACTION_KIND,
        CANDIDATE_ACTION_SCHEMA,
        CandidateAcquisitionActionReceipt,
        read_candidate_experiment_acquisition_action,
        receipt_inputs,
    )
    from polisyos.runtime.quality.candidate_acquisition_source import (
        CANDIDATE_ACQUISITION_SOURCE_KIND,
    )
    from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
    from tests._helpers.lane01_candidate_source import (
        UNEMPLOYMENT_COMPILER_INPUT,
        build_lane01_candidate_source,
    )
    from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE
    from tests.unit.runtime.quality.test_candidate_experiment_current_outcome import (
        _selection_case,
    )
    from tests.unit.runtime.quality.test_candidate_experiment_terminal_history import (
        _persist_requested_phase,
        _requested_phase,
    )

    seed_origin, seed_outcomes = _selection_case(1)
    pending_phase = seed_outcomes[-1].latest_receipt
    store = FileSystemCAS(tmp_path / "cas")
    source_case = build_lane01_candidate_source(
        tmp_path / "wdi-source",
        monkeypatch,
        store=store,
        tenant_id=seed_origin.tenant_id,
        cell_id=seed_origin.cell_id,
        run_id=seed_origin.run_id,
        job_id=pending_phase.job_id,
        route_id=seed_origin.route_id,
        profile=UNEMPLOYMENT_PROFILE,
        compiler_input=UNEMPLOYMENT_COMPILER_INPUT,
    )
    source = source_case.source
    assert source_case.source_ref.kind == CANDIDATE_ACQUISITION_SOURCE_KIND
    compiler_report = DataRequirementCompilationReport.model_validate(
        artifacts.load_core_json_artifact(store, source_case.binding.compiler_report_ref)
    )
    selected_specs = tuple(
        spec
        for spec in compiler_report.specs
        if isinstance(spec.metadata.get("capability_binding"), dict)
        and spec.metadata["capability_binding"].get("requirement_id") == source.requirement_id
    )
    assert len(selected_specs) == 1
    compiled_requirement_ref = selected_specs[0].requirement_id

    def selected_marker(kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            {"test_scope_marker": kind},
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    scope_values = seed_origin.policy_scope.model_dump(mode="python")
    scope_values.update(
        tenant_id=source.tenant_id,
        cell_id=source.cell_id,
        run_id=source.run_id,
        requirement_id=source.requirement_id,
        compiled_requirement_ref=compiled_requirement_ref,
        candidate_digest=source.candidate_digest,
        compiler_report_ref=source.compiler_report_ref,
        compiled_ref=selected_marker("runtime.compiled_recursive_generation_cycle"),
        planner_report_ref=selected_marker("runtime.acquisition_planner_report"),
        configured_port_source_ref=selected_marker(
            "runtime.quality.n7_configured_candidate_port_source"
        ),
    )
    scope = CandidateUnpricedPolicyScope.model_validate(scope_values)
    policy_ref = selected_marker("runtime_quality.candidate_unpriced_acquisition_policy")
    decision_ref = selected_marker("runtime_quality.agent_action_authority_decision")
    origin = replace(seed_origin, policy_scope=scope, policy_ref=policy_ref)
    phase_values = _requested_phase().model_dump(mode="python")
    phase_values.update(
        receipt_id=f"{pending_phase.job_id}.executing",
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
        job_id=pending_phase.job_id,
        policy_scope=scope,
        policy_ref=policy_ref,
        authority_decision_ref=decision_ref,
        coarse_phase="executing",
        receipt_phase="executing",
        recovery_state="none",
        predecessor_receipt_ref=_hash("e"),
        owner_receipt_refs=(),
        candidate_receipt_ref=None,
    )
    phase = AcquisitionCandidateExperimentPhaseReceipt.model_validate(phase_values)

    control_store = ControlPlaneStore(
        backend="sqlite", sqlite_path=tmp_path / "control.sqlite3"
    )
    event_log = RuntimeDiagnosticEventLog(store=control_store, artifact_store=store)
    phase_sink = AcquisitionRouteLoopAuthoritySink(
        artifact_store=store,
        event_log=event_log,
        control_store=control_store,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_live_authority",
        lambda *_: None,
    )
    monkeypatch.setattr(
        AcquisitionRouteLoopAuthoritySink,
        "_verify_candidate_experiment_phase_owner",
        lambda *_args, **_kwargs: None,
    )
    bridge = object.__new__(AcquisitionWorldGrowthBridge)
    bridge.artifact_store = store
    bridge.event_log = event_log
    closure = SimpleNamespace(
        tenant_id=origin.tenant_id,
        cell_id=origin.cell_id,
        run_id=origin.run_id,
        source_job_id=origin.source_job_id,
        route_id=origin.route_id,
        compiled_ref=str(source.compiler_report_ref.artifact_id),
        cost_basis_hash=_hash("b"),
    )
    try:
        requested_values = phase.model_dump(mode="python")
        requested_values.update(
            receipt_id=f"{phase.job_id}.requested",
            coarse_phase="requested",
            receipt_phase="requested",
            recovery_state="none",
            predecessor_receipt_ref=None,
        )
        requested_phase = AcquisitionCandidateExperimentPhaseReceipt.model_validate(
            requested_values
        )
        requested_head = _persist_requested_phase(phase_sink, requested_phase)
        phase = phase.model_copy(update={"predecessor_receipt_ref": requested_head.receipt_ref})
        phase_head = _persist_requested_phase(phase_sink, phase)
        assert phase_head.receipt_manifest_profile_sha256 is not None
        phase_ref = artifacts.ArtifactRef(
            artifact_id=phase_head.receipt_ref,
            kind="runtime_quality.acquisition_candidate_experiment_phase_receipt",
            media_type="application/json",
            manifest_profile_sha256=phase_head.receipt_manifest_profile_sha256,
        )
        phase_ref_id = str(phase_ref.artifact_id)

        selection = AcquisitionCandidateSourceRoute(
            tenant_id=source.tenant_id,
            cell_id=source.cell_id,
            run_id=source.run_id,
            route_id=source.route_id,
            design_problem_ref=scope.design_problem_ref,
            compiled_requirement_ref=compiled_requirement_ref,
            requirement_id=source.requirement_id,
            candidate_digest=source.candidate_digest,
            profile_selection_ref=_hash("9"),
            canonical_variable_id=source.resolved_source.entry.target_variable,
            target_slot_id=source.target_slot_id,
            country_code=source.country_code,
            year=source.year,
            population=source.population,
            reentry_budget_usd=Decimal("1.00"),
        )
        constraints = LiveCatalogExecutionConstraints(
            country_code=source.country_code,
            start_year=source.year,
            end_year=source.year,
            page_size=int(source.request_projection["page_size"]),
            max_response_bytes=65_536,
            max_decompressed_bytes=65_536,
            timeout_cap_seconds=15.0,
            heartbeat_cap_seconds=5.0,
        )
        evidence = source.live_source_execution
        binding_values = {
            "schema_version": WORLD_BANK_WDI_ROUTE_BINDING_SCHEMA_VERSION,
            "tenant_id": source.tenant_id,
            "cell_id": source.cell_id,
            "run_id": source.run_id,
            "route_id": source.route_id,
            "target_variable": source.target_slot_id,
            "authority_entry_id": source.resolved_source.entry.entry_id,
            "authority_provision_id": source.resolved_source.authority_provision_id,
            "authority_provision_content_sha256": (
                source.resolved_source.authority_provision_content_sha256
            ),
            "authority_registry_content_sha256": source.resolved_source.registry_content_sha256,
            "connector_id": "worldbank.wdi",
            "attempt_id": evidence.authorization.attempt_id,
            "harness_receipt_content_sha256": evidence.family_receipt_sha256,
            "carrier_receipt_sha256": evidence.authorization.harness.carrier_receipt_sha256,
            "constraints": constraints.model_dump(mode="json"),
        }
        binding = WorldBankWDIRouteExecutionBinding(
            **binding_values,
            binding_id=(
                "acquisition-route-binding:" + data_plane.content_sha256(binding_values)
            ),
        )
        receipt = CandidateAcquisitionActionReceipt(
            tenant_id=origin.tenant_id,
            cell_id=origin.cell_id,
            run_id=origin.run_id,
            source_job_id=origin.source_job_id,
            action_job_id=phase.job_id,
            action_generation=phase.action_generation,
            action_attempt=1,
            selection=selection,
            candidate_budget_window_id="1" * 64,
            candidate_budget_window_digest="2" * 64,
            route_id=origin.route_id,
            action_phase_ref=phase_ref_id,
            selected_action_phase_ref=phase_ref,
            decision_ref=str(phase.authority_decision_ref.artifact_id),
            route_binding_id=binding.binding_id,
            route_binding=binding.model_dump(mode="json"),
            attempt_id=binding.attempt_id,
            compiled_requirement_ref=compiled_requirement_ref,
            requirement_id=source.requirement_id,
            candidate_digest=source.candidate_digest,
            profile_selection_ref=selection.profile_selection_ref,
            canonical_variable_id=selection.canonical_variable_id,
            target_slot_id=source.target_slot_id,
            candidate_source_ref=source_case.source_ref,
            compiler_report_ref=source.compiler_report_ref,
            limitations=source.limitations,
        )

        def persist_action(
            action_receipt: CandidateAcquisitionActionReceipt,
        ) -> artifacts.ArtifactRef:
            persisted = bridge._persist(
                closure,
                action_receipt.model_dump(mode="json"),
                CANDIDATE_ACTION_KIND,
                CANDIDATE_ACTION_SCHEMA,
                "candidate_input_prepared",
                artifact_inputs=receipt_inputs(action_receipt),
                return_selected_profile=True,
            )
            assert isinstance(persisted, artifacts.ArtifactRef)
            return persisted

        action_ref = persist_action(receipt)
        phase_event_id = "test-upstream-head-owner"
        head = AcquisitionActionHeadRecord(
            tenant_id=phase.tenant_id,
            cell_id=phase.cell_id,
            run_id=phase.run_id,
            source_job_id=phase.source_job_id,
            route_id=phase.route_id,
            action_generation=phase.action_generation,
            head_generation=1,
            receipt_ref=phase_ref_id,
            receipt_sha256=phase_ref_id,
            durable_event_id=phase_event_id,
            coarse_phase=phase.coarse_phase,
            receipt_phase=phase.receipt_phase,
            recovery_state=phase.recovery_state,
            job_id=phase.job_id,
            predecessor_receipt_ref=phase.predecessor_receipt_ref,
            created_at=datetime.now(UTC),
            receipt_manifest_profile_sha256=phase_ref.manifest_profile_sha256,
        )
        phase_row = VerifiedAcquisitionActionPhase(
            receipt_ref=phase_ref_id,
            receipt=phase,
            durable_event_id=phase_event_id,
            event=None,
        )
        outcome = VerifiedAcquisitionActionOutcome(
            head=head,
            latest_receipt=phase,
            executing_phase_ref=phase_ref_id,
            executing_phase=phase,
            selection_phase_ref=None,
            selection_phase=None,
            phase_chain=(phase_row,),
        )
        bridge.action_head_sink = SimpleNamespace(
            experiment_action_outcomes=lambda **_kwargs: (outcome,)
        )

        replayed = read_candidate_experiment_acquisition_action(
            bridge=bridge,
            origin=origin,
            receipt_ref=action_ref,
            require_current_action=False,
        )
        assert replayed == receipt
        assert replayed.candidate_source_ref == source_case.source_ref
        assert replayed.candidate_source_ref.kind == CANDIDATE_ACQUISITION_SOURCE_KIND

        foreign_origin = replace(origin, cell_id=origin.cell_id + "-foreign")
        with pytest.raises(ValueError, match="candidate_experiment_action_parent_mismatch"):
            read_candidate_experiment_acquisition_action(
                bridge=bridge,
                origin=foreign_origin,
                receipt_ref=action_ref,
                require_current_action=False,
            )

        wrong_source_ref = source_case.source_ref.model_copy(
            update={"kind": "runtime.quality.unrelated_candidate_source"}
        )
        wrong_kind_receipt = receipt.model_copy(
            update={"candidate_source_ref": wrong_source_ref}
        )
        assert {
            key: value
            for key, value in wrong_kind_receipt.model_dump(mode="json").items()
            if key != "candidate_source_ref"
        } == {
            key: value
            for key, value in receipt.model_dump(mode="json").items()
            if key != "candidate_source_ref"
        }
        wrong_kind_action_ref = persist_action(wrong_kind_receipt)
        with pytest.raises(ValueError, match="candidate_source_ref_profile_mismatch"):
            read_candidate_experiment_acquisition_action(
                bridge=bridge,
                origin=origin,
                receipt_ref=wrong_kind_action_ref,
                require_current_action=False,
            )
    finally:
        control_store.close()
