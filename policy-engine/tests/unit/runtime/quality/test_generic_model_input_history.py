"""Recorded call normalization and real immutable-event intake for history.

The component basis below declares unavailable source custody. It establishes
only the selected CAS/event boundary; the served A/B/C scenario proves complete
numerical history replay and separation from present provider admission.
"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from polisyos.core import artifacts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore
from polisyos.runtime.quality import acquisition_evaluation as owner
from polisyos.runtime.quality.authority_reconciliation import AuthorityReconciliationError
from polisyos.runtime.quality.event_log import RuntimeDiagnosticEventLog
from polisyos.runtime.quality.generic_simulation_admission import (
    GenericCycleN5PairedProgramGraphRequestProfileV5,
    GenericCycleN5ProgramGraphRequestProfileV4,
)
from polisyos.runtime.quality.joint_simulation_horizon import (
    HorizonSpec,
    PhysicalSimulationWorkObservation,
    _physical_invocation_binding,
)
from polisyos.runtime.quality.n5_execution_basis import (
    exact_n5_content_bytes,
    exact_n5_content_hash,
)
from polisyos.scientist.orchestration.engine.budget_ledger import BudgetLedgerInvocationProfile
from polisyos.scientist.orchestration.engine.producer_budget import (
    ProducerBudgetObservation,
    ProducerBudgetSourceError,
)
from tests.unit.scientist.orchestration.engine.test_producer_budget_c49 import (
    _diagnostic_owner,
    _settle,
)


class _UnknownPairedProgramGraphProfile(GenericCycleN5PairedProgramGraphRequestProfileV5):
    """A future profile subtype must not inherit the closed V4/V5 admission."""


def _physical_work_case(
    tmp_path: Path,
    *,
    profile_type: type[GenericCycleN5ProgramGraphRequestProfileV4] = (
        GenericCycleN5ProgramGraphRequestProfileV4
    ),
    work_count: int = 1,
    charge_count: int = 1,
    charge_outcome: str = "completed",
    work_statuses: tuple[str, ...] | None = None,
    budget_basis: ProducerBudgetObservation | None = None,
) -> tuple[Any, Any, Any, Any]:
    _ledger, middleware, binding, policy, observer = _diagnostic_owner(
        tmp_path, total=5, protected=1, purpose="standard"
    )
    _settle(middleware, binding, "physical-work-basis", "0.01")
    basis = budget_basis if budget_basis is not None else observer.admit()
    n5 = profile_type(
        budget_ref="budget://test/generic-initial-physical-work",
        horizon=HorizonSpec(start=0, end=0, step=1),
        baseline_state={"outcome": 0.0},
        compile_report_ref=artifacts.ArtifactRef(
            artifact_id="sha256:" + "a" * 64,
            kind="compiler.compile_report",
            media_type="application/json",
            manifest_profile_sha256="sha256:" + "b" * 64,
        ),
        invocation_quota_policy=policy,
    )
    quota_profile = BudgetLedgerInvocationProfile.from_policy(binding, policy)
    work = []
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    for index in range(work_count):
        invocation_id = hashlib.sha256(f"invocation-{index}".encode()).hexdigest()[:32]
        event_id = hashlib.sha256(f"event-{index}".encode()).hexdigest()[:32]
        physical_spec_ref = hashlib.sha256(f"spec-{index}".encode()).hexdigest()
        operation_id, request_digest = _physical_invocation_binding(
            invocation_id, physical_spec_ref, index
        )
        reservation = None
        if index < charge_count:
            with observer.invocation_purpose_scope_from_selected_owner(policy, purpose="standard"):
                reservation = observer.reserve_invocation(operation_id, request_digest)
                assert reservation is not None
                observer.finish_invocation(operation_id, request_digest, charge_outcome)
        status = work_statuses[index] if work_statuses is not None else "completed"
        work.append(
            PhysicalSimulationWorkObservation(
                invocation_id=invocation_id,
                event_id=event_id,
                physical_spec_ref=physical_spec_ref,
                effective_seed=index,
                status=status,
                started_at=started_at,
                completed_at=started_at + timedelta(seconds=1),
                duration_seconds=1.0,
                budget_status="current_owner_checked",
                budget_source_basis_digest=basis.source_basis_digest,
                error_type="RuntimeError" if status == "failed" else None,
                invocation_quota_operation_id=operation_id,
                invocation_quota_request_digest=request_digest,
                invocation_quota_profile_digest=(
                    reservation.profile_digest
                    if reservation is not None
                    else quota_profile.profile_digest
                ),
                invocation_quota_purpose="standard",
                invocation_quota_status=("failed" if status == "failed" else "completed"),
            )
        )
    result = SimpleNamespace(
        physical_work_observations=tuple(work),
        diagnostics={
            "producer_budget_observations": {
                basis.source_basis_digest: basis.model_dump(mode="json")
            }
        },
    )
    input_record = SimpleNamespace(
        n5=n5,
        run_id=binding.run_id,
        job_id=binding.control_job_id,
        tenant_id=binding.tenant_id,
        cell_id=binding.cell_id,
    )
    return result, input_record, middleware, binding


def test_initial_physical_work_reconciles_paired_v5_standard_completion(tmp_path: Path) -> None:
    """Reconcile recorded paired quota rows, not the planned census or numeric result."""
    result, input_record, settlement_store, binding = _physical_work_case(
        tmp_path,
        profile_type=GenericCycleN5PairedProgramGraphRequestProfileV5,
        work_count=2,
        charge_count=2,
    )

    owner.verify_generic_initial_physical_work(
        result=result,
        input_record=input_record,
        settlement_store=settlement_store,
        expected_run_binding=binding,
    )


def test_initial_physical_work_preserves_legacy_v4_standard_completion(tmp_path: Path) -> None:
    result, input_record, settlement_store, binding = _physical_work_case(tmp_path)

    owner.verify_generic_initial_physical_work(
        result=result,
        input_record=input_record,
        settlement_store=settlement_store,
        expected_run_binding=binding,
    )


def test_initial_physical_work_rejects_unrecognized_profile_subclass(tmp_path: Path) -> None:
    result, input_record, settlement_store, binding = _physical_work_case(
        tmp_path, profile_type=_UnknownPairedProgramGraphProfile
    )

    with pytest.raises(ValueError, match=r"^generic_initial_physical_completion_not_established$"):
        owner.verify_generic_initial_physical_work(
            result=result,
            input_record=input_record,
            settlement_store=settlement_store,
            expected_run_binding=binding,
        )


def test_initial_physical_work_requires_a_durable_charge_for_every_observed_unit(
    tmp_path: Path,
) -> None:
    result, input_record, settlement_store, binding = _physical_work_case(
        tmp_path,
        profile_type=GenericCycleN5PairedProgramGraphRequestProfileV5,
        work_count=2,
        charge_count=1,
    )

    with pytest.raises(ProducerBudgetSourceError, match=r"^completed_invocation_record_mismatch$"):
        owner.verify_generic_initial_physical_work(
            result=result,
            input_record=input_record,
            settlement_store=settlement_store,
            expected_run_binding=binding,
        )


def test_initial_physical_work_requires_a_durable_charge_not_just_an_observation(
    tmp_path: Path,
) -> None:
    result, input_record, settlement_store, binding = _physical_work_case(tmp_path, charge_count=0)

    with pytest.raises(ProducerBudgetSourceError, match=r"^completed_invocation_record_mismatch$"):
        owner.verify_generic_initial_physical_work(
            result=result,
            input_record=input_record,
            settlement_store=settlement_store,
            expected_run_binding=binding,
        )


def test_initial_physical_work_rejects_a_durable_noncompleted_charge(tmp_path: Path) -> None:
    result, input_record, settlement_store, binding = _physical_work_case(
        tmp_path, charge_outcome="failed"
    )

    with pytest.raises(ProducerBudgetSourceError, match=r"^completed_invocation_record_mismatch$"):
        owner.verify_generic_initial_physical_work(
            result=result,
            input_record=input_record,
            settlement_store=settlement_store,
            expected_run_binding=binding,
        )


def test_initial_physical_work_rejects_a_noncompleted_work_observation(tmp_path: Path) -> None:
    result, input_record, settlement_store, binding = _physical_work_case(
        tmp_path, charge_count=0, work_statuses=("failed",)
    )

    with pytest.raises(ValueError, match=r"^generic_initial_physical_completion_not_established$"):
        owner.verify_generic_initial_physical_work(
            result=result,
            input_record=input_record,
            settlement_store=settlement_store,
            expected_run_binding=binding,
        )


def test_initial_physical_work_rejects_a_foreign_durable_owner(tmp_path: Path) -> None:
    foreign_directory = tmp_path / "foreign-owner"
    foreign_directory.mkdir()
    _foreign_ledger, foreign_middleware, foreign_binding, _policy, foreign_observer = (
        _diagnostic_owner(foreign_directory, total=5, protected=1, purpose="standard")
    )
    _settle(foreign_middleware, foreign_binding, "foreign-physical-work-basis", "0.01")
    foreign_basis = foreign_observer.admit()
    result, input_record, settlement_store, binding = _physical_work_case(
        tmp_path, budget_basis=foreign_basis
    )

    with pytest.raises(ProducerBudgetSourceError, match=r"^completed_invocation_owner_mismatch$"):
        owner.verify_generic_initial_physical_work(
            result=result,
            input_record=input_record,
            settlement_store=settlement_store,
            expected_run_binding=binding,
        )


def _step(step: int, content: bytes) -> Any:
    return SimpleNamespace(
        step=step,
        calls=(
            SimpleNamespace(
                plan_index=2, node_id="scheduled-node", callable_receiver_hex=content.hex()
            ),
        ),
    )


def test_recorded_call_content_reconciles_every_physical_unit_without_live_code() -> None:
    first = exact_n5_content_bytes({"recorded_callable": "old-provider-a", "parameter": 3})
    second = exact_n5_content_bytes({"recorded_callable": "old-provider-a", "parameter": 4})
    observed = SimpleNamespace(
        numerical_intent_profile=owner.GENERIC_NUMERICAL_INTENT_PROFILE,
        steps=(_step(1, second), _step(0, first), _step(0, first)),
    )

    assert owner._recorded_generic_model_input_calls(observed) == (
        (2, "scheduled-node", 0, first),
        (2, "scheduled-node", 1, second),
    )
    graft = SimpleNamespace(
        numerical_intent_profile=owner.GENERIC_NUMERICAL_INTENT_PROFILE,
        steps=(_step(0, first), _step(0, second)),
    )
    with pytest.raises(ValueError, match="history_call_census_mismatch"):
        owner._recorded_generic_model_input_calls(graft)


@pytest.mark.parametrize("content", [b"not JSON", b' {"mapping":[]}', b"{}\n"])
def test_recorded_call_requires_the_original_canonical_wire(content: bytes) -> None:
    with pytest.raises(ValueError, match="n5_content_wire_invalid"):
        owner._recorded_generic_model_input_calls(
            SimpleNamespace(
                numerical_intent_profile=owner.GENERIC_NUMERICAL_INTENT_PROFILE,
                steps=(_step(0, content),),
            )
        )


def _component_basis(store: Any) -> owner.GenericModelInputEvaluationBasisV1:
    def component_ref(kind: str) -> artifacts.ArtifactRef:
        return store.put_json(
            {"component_only": kind, "source_authority": "not_established"},
            artifacts.ArtifactWriteOptions(kind=kind, media_type="application/json"),
            return_selected_profile=True,
        )

    encoded = exact_n5_content_bytes({"source_custody": "not_established"})
    payload = {
        "schema_version": "GenericModelInputEvaluationBasis@1.0",
        "authority_purpose": "candidate_evaluation_retention_only",
        "comparison_profile": "generic_program_graph_declared_numerical_v2",
        "basis_role": "blocked",
        "tenant_id": "tenant-history",
        "cell_id": "cell-history",
        "run_id": "component-history-run",
        "source_job_id": "component-source",
        "action_job_id": "component-action",
        "route_id": "sha256:" + "1" * 64,
        "design_problem_ref": "sha256:" + "2" * 64,
        "design_problem_basis_ref": "sha256:" + "3" * 64,
        "candidate_id": "component-candidate",
        "input_ref": component_ref("runtime.quality.generic_cycle_simulation_n5_input").model_dump(
            mode="json"
        ),
        "semantic_successor_ref": component_ref(
            "runtime.quality.model_input_successor_selection"
        ).model_dump(mode="json"),
        "bound_state_snapshot_ref": component_ref("foundry.state_snapshot").model_dump(mode="json"),
        "evaluation": None,
        "prospective_basis_ref": None,
        "comparison_decision_ref": None,
        "predicate_provenance": "not_established",
        "reason_codes": ["component_source_not_established"],
        "limitations": ["synthetic_component_only"],
        "closure_residuals": list(owner.CANDIDATE_N5_CLOSURE_RESIDUALS_V2),
        "observed_admission": False,
        "publication_authority": False,
        "numerical_intent_hex": encoded.hex(),
        "numerical_intent_sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
    }
    return owner.GenericModelInputEvaluationBasisV1.model_validate(
        {**payload, "content_hash": exact_n5_content_hash(payload)}
    )


def test_history_intake_cannot_replace_the_selected_profile_or_drop_its_event(
    tmp_path: Path,
) -> None:
    from tests.unit.runtime.quality.test_candidate_experiment_reuse_occurrence import (
        _write_profile_variant,
    )

    database_path = tmp_path / "control.sqlite3"
    with (
        tenant_scope(None, tenant_id="tenant-history", cell_id="cell-history"),
        closing(ControlPlaneStore(backend="sqlite", sqlite_path=database_path)) as control,
    ):
        store = artifacts.FileSystemCAS(tmp_path / "cas")
        events = RuntimeDiagnosticEventLog(store=control, artifact_store=store)
        basis = _component_basis(store)
        ref = owner.persist_acquisition_evaluation_artifact(
            store=store, event_log=events, record=basis
        )
        assert (
            owner.read_acquisition_evaluation_artifact(
                store=store, event_log=events, ref=ref, record_type=type(basis)
            )
            == basis
        )
        foreign = _write_profile_variant(
            store, ref, producer=artifacts.ProducerInfo(component="foreign.producer", version="1")
        )
        assert foreign.artifact_id == ref.artifact_id
        assert foreign.manifest_profile_sha256 != ref.manifest_profile_sha256
        with pytest.raises(ValueError, match="artifact_owner_mismatch"):
            owner.replay_generic_model_input_basis_for_history(
                store=store,
                event_log=events,
                origin=None,
                basis_ref=foreign,
                evaluation_context=None,
            )
        with sqlite3.connect(database_path) as connection:
            removed = connection.execute(
                "DELETE FROM control_diagnostic_events WHERE event_id = ?",
                (owner._generic_model_input_evaluation_event_id(basis),),
            ).rowcount
        assert removed == 1
        with pytest.raises(AuthorityReconciliationError) as refused:
            owner.replay_generic_model_input_basis_for_history(
                store=store,
                event_log=events,
                origin=None,
                basis_ref=ref,
                evaluation_context=None,
            )
        assert refused.value.code == "authority_orphan_cas"
        assert refused.value.details == {
            "event_id": owner._generic_model_input_evaluation_event_id(basis),
            "record_count": 0,
        }
