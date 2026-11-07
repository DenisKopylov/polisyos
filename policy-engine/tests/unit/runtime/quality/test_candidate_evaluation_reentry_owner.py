"""Real reentry-owner refusals before a protected candidate action exists.

The N7 source, route closure, service, CAS, events and empty SQL frontier use
their actual owners. Its recursive leaf is the existing contract-test producer;
it supplies no selected candidate N4/context/N5. Action/intent/basis/reentry
parents below are explicit adversarial component inputs, never owner receipts.
No lease or owner method is replaced. These tests cannot establish empty-to-
fresh selection, blocked withdrawal or retained-limitation propagation.
"""

from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control_plane_store import (
    AcquisitionEvaluationFrontierKey,
    ControlPlaneStore,
)
from polisyos.runtime.quality.acquisition_evaluation import (
    CandidateAcquisitionEvaluationDecision,
    issue_candidate_acquisition_evaluation_decision,
    persist_acquisition_evaluation_artifact,
    read_acquisition_evaluation_artifact,
)
from polisyos.runtime.quality.acquisition_evaluation_dispatch import (
    CandidateAcquisitionEvaluationReentryOwner,
    candidate_terminal_frontier_cas,
)
from polisyos.runtime.quality.acquisition_route_loop import AcquisitionCandidateRouteLoopReceipt
from polisyos.runtime.quality.acquisition_world_growth import (
    AcquisitionWorldGrowthBridge,
    AcquisitionWorldGrowthConfig,
)
from polisyos.runtime.quality.agent_action_authority import agent_action_content_hash
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.joint_simulation_horizon import prepare_joint_simulation_configuration
from tests._helpers.acquisition_production import (
    install_fixture_wdi_cost_basis,
    persist_wdi_route,
)
from tests._helpers.lane01_wdi_profiles import UNEMPLOYMENT_PROFILE, build_fixture_wdi_authority
from tests._helpers.runtime_http import _build_control_service
from tests.unit.runtime.quality.test_substrate_registry import _write_substrate_catalog_fixture

if TYPE_CHECKING:
    from polisyos.runtime.http.services.control.run_lifecycle import ControlPlaneService
    from polisyos.runtime.quality.acquisition_route_loop import VerifiedAcquisitionRouteClosure


@dataclass(frozen=True)
class _ReentryRefusalCase:
    service: ControlPlaneService
    closure: VerifiedAcquisitionRouteClosure
    owner: CandidateAcquisitionEvaluationReentryOwner
    decision: CandidateAcquisitionEvaluationDecision
    decision_ref: artifacts.ArtifactRef
    key: AcquisitionEvaluationFrontierKey


@asynccontextmanager
async def _real_reentry_refusal_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[_ReentryRefusalCase]:
    """Compose actual owners; persist only a caller-proposed unknown decision."""
    install_fixture_wdi_cost_basis(monkeypatch)
    catalog_root = tmp_path / "catalog"
    _write_substrate_catalog_fixture(catalog_root)
    cas = artifacts.FileSystemCAS(tmp_path / "cas")
    service = _build_control_service(tmp_path / "control", artifact_store=cas)
    try:
        closure, _ = await persist_wdi_route(
            service,
            tenant_id="tenant-reentry-component",
            cell_id="cell-reentry-component",
            generation_cycle_repo_root=catalog_root,
        )
        authority, _entry = build_fixture_wdi_authority(
            tmp_path / "candidate-authority", UNEMPLOYMENT_PROFILE
        )
        bridge = AcquisitionWorldGrowthBridge(
            config=AcquisitionWorldGrowthConfig(),
            repo_root=authority.repo_root,
            runtime_root=tmp_path / "candidate-runtime",
            authority=authority,
            artifact_store=cas,
            event_log=service._diagnostic_event_log,
            control_store=service._control_store,
            epoch_deployment=None,
            source_control_service=service,
            action_head_sink=service.acquisition_route_sink,
        )
        with tenant_scope(None, tenant_id=closure.tenant_id, cell_id=closure.cell_id):

            def parent(kind: str, name: str) -> artifacts.ArtifactRef:
                return cas.put_json(
                    {"adversarial_component_input": name, "protected_action_not_established": True},
                    artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
                    return_selected_profile=True,
                )

            action = parent("runtime_quality.acquisition_candidate_action_receipt", "action")
            intent = parent("runtime_quality.acquisition_candidate_world_intent", "intent")
            source = parent("runtime.quality.candidate_acquisition_source", "source")
            basis = parent("runtime_quality.acquisition_evaluation_basis", "basis")
            decision = issue_candidate_acquisition_evaluation_decision(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                run_id=closure.run_id,
                source_job_id=closure.source_job_id,
                action_job_id="unissued-candidate-action",
                action_generation=1,
                route_id=closure.route_id,
                compiled_ref=closure.compiled_ref,
                design_problem_ref=closure.design_problem_ref,
                design_problem_basis_ref=closure.design_problem_basis_ref,
                candidate_id=closure.source_cycle.selected_candidate_ref,
                source_candidate_content_hash=closure.source_cycle.selected_candidate_content_hash,
                candidate_action_ref=action,
                candidate_world_intent_ref=intent,
                candidate_source_ref=source,
                current_basis_ref=basis,
                prior_basis_ref=None,
                prior_evaluation=None,
                comparison_result="not_established",
                predicate_provenance="not_established",
                reason_codes=("candidate_evaluation_prior_basis_not_established",),
                # This is an adversarial declaration of a nonempty expectation,
                # not a SQL frontier. The actual owner below observes an empty key.
                expected_frontier_revision=1,
                expected_frontier_ref=str(basis.artifact_id),
                generated_at=datetime.now(UTC).isoformat(),
            )
            selected = persist_acquisition_evaluation_artifact(
                store=cas, event_log=service._diagnostic_event_log, record=decision
            )
            owner = CandidateAcquisitionEvaluationReentryOwner(
                bridge=bridge,
                closure=closure,
                candidate_action_ref=action,
                candidate_world_intent_ref=intent,
                current_basis_ref=basis,
                decision_ref=selected,
                prior=None,
                prepared_n5_configuration=prepare_joint_simulation_configuration(),
            )
            key = AcquisitionEvaluationFrontierKey(
                tenant_id=closure.tenant_id,
                cell_id=closure.cell_id,
                source_job_id=closure.source_job_id,
                design_problem_ref=closure.design_problem_ref,
                candidate_id=closure.source_cycle.selected_candidate_ref,
            )
            yield _ReentryRefusalCase(service, closure, owner, decision, selected, key)
    finally:
        service.close()


def _state(case: _ReentryRefusalCase) -> tuple[object, ...]:
    """Snapshot every CAS file plus the actual run's events, frontier and action head."""
    cas = case.service._artifact_store
    files = {
        str(path.relative_to(cas.root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in cas.root.rglob("*")
        if path.is_file()
    }
    events = case.service._control_store.list_diagnostic_events(
        run_id=case.closure.run_id, limit=1000
    )
    assert len(events) < 1000
    return (
        files,
        events,
        case.service._control_store.read_acquisition_evaluation_frontier(case.key),
        case.service.acquisition_route_sink.current_action_outcome(
            tenant_id=case.closure.tenant_id,
            cell_id=case.closure.cell_id,
            run_id=case.closure.run_id,
            source_job_id=case.closure.source_job_id,
            route_id=case.closure.route_id,
        ),
    )


@pytest.mark.asyncio
async def test_reentry_owner_refuses_declared_frontier_and_unowned_views_without_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real record is insufficient for current execution or terminal publication."""
    async with _real_reentry_refusal_case(tmp_path, monkeypatch) as case:
        service, owner = case.service, case.owner
        cas, events = service._artifact_store, service._diagnostic_event_log

        def read(
            ref: artifacts.ArtifactRef,
            *,
            store: object = cas,
            event_log: RuntimeDiagnosticEventLog = events,
        ) -> object:
            return read_acquisition_evaluation_artifact(
                store=store,
                event_log=event_log,
                ref=ref,
                record_type=CandidateAcquisitionEvaluationDecision,
            )

        assert read(case.decision_ref) == case.decision
        assert service._control_store.get_job(case.closure.source_job_id).state == "completed"
        assert service._control_store.read_acquisition_evaluation_frontier(case.key) is None
        before = _state(case)
        with pytest.raises(
            ValueError, match=r"^candidate_evaluation_reentry_unknown_not_established$"
        ):
            owner.revalidate()
        assert _state(case) == before

        manifest = cas.get_manifest(case.decision_ref)
        foreign = cas.put_bytes(
            cas.get_bytes(case.decision_ref),
            artifacts.ArtifactWriteOptions(
                kind=case.decision_ref.kind,
                media_type=case.decision_ref.media_type,
                schema=manifest.artifact_schema,
                canon=manifest.canon,
                inputs=manifest.inputs,
                governance=manifest.governance,
                tenant_context=manifest.tenant_context,
                producer=artifacts.ProducerInfo(
                    component="test.foreign-evaluation-owner", version="1"
                ),
            ),
            return_selected_profile=True,
        )
        assert foreign.artifact_id == case.decision_ref.artifact_id
        assert foreign.manifest_profile_sha256 != case.decision_ref.manifest_profile_sha256
        before = _state(case)
        with pytest.raises(ValueError, match=r"^acquisition_evaluation_artifact_owner_mismatch$"):
            replace(owner, decision_ref=foreign).revalidate()
        assert _state(case) == before
        assert read(case.decision_ref) == case.decision

        # A second real SQL event owner has no event for this selected record.
        with closing(
            ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "empty-events.sqlite3")
        ) as empty:
            missing_events = RuntimeDiagnosticEventLog(store=empty, artifact_store=cas)
            before = _state(case)
            with pytest.raises((ValueError, RuntimeError), match=r"event|authority"):
                read(case.decision_ref, event_log=missing_events)
            assert _state(case) == before

        # Withhold only the selected manifest, retaining the same-byte sibling.
        # Restore it in finally; no retained source or event is deleted.
        selected_path = cas._manifest_path_for_ref(
            case.decision_ref.artifact_id, case.decision_ref.manifest_profile_sha256
        )
        held_path = selected_path.with_name(selected_path.name + ".held")
        selected_path.rename(held_path)
        try:
            cold = artifacts.FileSystemCAS.open_existing_read_only(cas.root)
            assert cold.verify(foreign).ok
            with pytest.raises(FileNotFoundError):
                read(case.decision_ref, store=cold)
        finally:
            held_path.rename(selected_path)
        assert read(case.decision_ref) == case.decision

        reentry = cas.put_json(
            {
                "adversarial_component_input": "blocked-reentry",
                "actual_reentry_not_established": True,
            },
            artifacts.ArtifactWriteOptions(
                kind="runtime_quality.candidate_source_reentry_receipt",
                media_type="application/json",
            ),
            return_selected_profile=True,
        )
        proposed = AcquisitionCandidateRouteLoopReceipt(
            receipt_id="unissued-candidate-terminal",
            tenant_id=case.closure.tenant_id,
            cell_id=case.closure.cell_id,
            run_id=case.closure.run_id,
            source_job_id=case.closure.source_job_id,
            route_id=case.closure.route_id,
            action_generation=case.decision.action_generation,
            job_id=case.decision.action_job_id,
            compiled_ref=case.closure.compiled_ref,
            planner_report_hash=agent_action_content_hash(case.closure.planner_report),
            cost_basis_hash=case.closure.cost_basis_hash,
            decision_ref=str(case.decision_ref.artifact_id),
            terminal_outcome="candidate_reentry_completed",
            predecessor_receipt_ref=str(owner.candidate_action_ref.artifact_id),
            owner_receipt_refs=(
                str(owner.candidate_action_ref.artifact_id),
                str(case.decision_ref.artifact_id),
                str(reentry.artifact_id),
            ),
            candidate_action_ref=owner.candidate_action_ref,
            candidate_reentry_ref=reentry,
            evaluation_decision_ref=case.decision_ref,
            selected_basis_ref=owner.current_basis_ref,
            selected_evaluation_witness_ref=reentry,
            generated_at=datetime.now(UTC),
        )
        before = _state(case)
        with pytest.raises(
            ValueError, match=r"^candidate_evaluation_native_terminal_fence_not_established$"
        ):
            candidate_terminal_frontier_cas(
                proposed, artifact_store=cas, control_store=service._control_store
            )
        assert _state(case) == before
