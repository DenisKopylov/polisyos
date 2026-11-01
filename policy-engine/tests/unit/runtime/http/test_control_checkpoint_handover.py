"""Native candidate checkpoint continuation through the registered Runtime worker.

The primary collaborator is an actual local fixture backend with SQLite effects,
selected CAS outputs and durable accounting. It is not a deployment, institutional
issuer, external billing receipt, or proof of an arbitrary distributed effect.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts import (
    ArtifactRef,
    input_ref_from_artifact_ref,
    read_core_json_artifact,
)
from polisyos.core.artifacts.manifest import SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.artifacts.write_contract import ArtifactWriteOptions
from polisyos.core.contracts.control import WorkflowRunRequest
from polisyos.core.contracts.fabric import DataSnapshot, DataSnapshotRef
from polisyos.core.run import read_runtime_invocation_attempts
from polisyos.core.security.access_scope import AccessScope
from polisyos.core.security.tenant_context import (
    reset_current_access_scope,
    set_current_access_scope,
    tenant_scope,
)
from polisyos.runtime.http.execution_policy import (
    RuntimeExecutionPolicyResolver,
    RuntimePrincipal,
)
from polisyos.runtime.http.resilience import guard_runtime_control_store
from polisyos.runtime.http.services.control import ControlPlaneService
from polisyos.runtime.http.services.control_plane_store import (
    ControlJobLeaseLostError,
    ControlPlaneStore,
)
from polisyos.runtime.http.services.control_worker import ControlWorker
from polisyos.scientist.orchestration.engine import checkpoint as checkpoint_module
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.checkpoint import (
    load_checkpoint,
    load_checkpoint_head,
    materialize_checkpoint_state,
)
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec
from polisyos.scientist.orchestration.workflows import builder
from tests._helpers.control_worker import dispatch_one_control_job
from tests._helpers.dur02_effects import (
    _CheckpointedEffectNode,
    _confirmed_effect_receipt,
    _effects,
    _LostCheckpointReply,
    _RemainingEffectNode,
    _UnbudgetedEffectNode,
    _UnbudgetedRemainingEffectNode,
)
from tests.unit.remediation.test_dur_02_process import _PrimaryCheckpointHook
from tests.unit.runtime.http.test_control_job_core_attempts import (
    _core_only_registry_providers,
    _NoOpRetrievalService,
)

if TYPE_CHECKING:
    from collections.abc import Iterator


@contextmanager
def _execution_scope(scope: AccessScope) -> Iterator[None]:
    token = set_current_access_scope(scope)
    try:
        with tenant_scope(None, tenant_id=scope.tenant_id, cell_id=scope.cell_id):
            yield
    finally:
        reset_current_access_scope(token)


def _snapshot(store: FileSystemCAS, *, value: int = 1) -> DataSnapshotRef:
    data = store.put_json(
        {"fixture": "dur02-local-effect", "value": value},
        ArtifactWriteOptions(
            kind="fixture.dur02.source",
            media_type="application/json",
            schema=SchemaInfo(name="tests.DUR02Source", version="1.0"),
        ),
        return_selected_profile=True,
    )
    snapshot = DataSnapshot(
        data_ref=data,
        stats={"rows": 1},
        notes=["Synthetic input for a bounded runtime test; no production provenance."],
    )
    ref = store.put_json(
        snapshot.model_dump(mode="json"),
        ArtifactWriteOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[input_ref_from_artifact_ref(data, role="source_data")],
        ),
        return_selected_profile=True,
    )
    return DataSnapshotRef.model_validate(ref.model_dump(mode="python"))


@pytest.mark.parametrize(
    "outcome",
    [
        "remaining",
        "exhausted",
        "unknown",
        "stale_ledger",
        "late_stale_ledger",
        "wrong_params",
        "wrong_input",
        "wrong_type",
        "lost_lease",
        "lost_owner_after_settlement",
        "unbudgeted",
    ],
)
def test_registered_worker_reconciles_same_job_checkpoint_and_real_ledger(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str
) -> None:
    """Both attempts use the registered handler with real admission/resume code."""
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    unbudgeted = outcome == "unbudgeted"
    cas_root = tmp_path / "cas"
    cas = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()
    raw_control = ControlPlaneStore(backend="sqlite", sqlite_path=tmp_path / "control.sqlite3")
    control = guard_runtime_control_store(raw_control)
    budget_path = tmp_path / "budget.json"
    limit = Decimal(7) if outcome == "exhausted" else Decimal(10)
    middleware = (
        None
        if unbudgeted
        else BudgetMiddleware(
            BudgetState(
                limits={"run": BudgetLimit(key="run", max_usd=limit)}, spent={"run": Decimal(5)}
            ),
            ledger=FileBudgetLedger(budget_path),
        )
    )
    initial_ledger = budget_path.read_bytes() if not unbudgeted else None
    scope = AccessScope.for_service(
        tenant_id="dur02-runtime-tenant",
        cell_id="dur02-runtime-cell",
        spiffe_id="spiffe://polisyos-test/dur02-runtime-worker",
    )
    registry = NodeRegistry()
    resolver = RuntimeExecutionPolicyResolver(
        default_profile="dev",
        worker_backend="external",
        state_store_backend="sqlite",
        sqlite_path=str(tmp_path / "control.sqlite3"),
        postgres_dsn=None,
    )
    service = ControlPlaneService(
        cas_root=cas_root,
        core_runs_root=cas_root / "runs",
        artifact_store=cas,
        control_store=control,
        retrieval_service=_NoOpRetrievalService(),
        registry_providers=_core_only_registry_providers(),
        policy_resolver=resolver,
        workflow_continuation_registry=registry,
        workflow_continuation_ledger=None if unbudgeted else FileBudgetLedger(budget_path),
        workflow_continuation_access_scope=scope,
        workflow_continuation_profile=(
            "reconciled_local_v1" if unbudgeted else "single_owner_local_v1"
        ),
    )
    try:
        with _execution_scope(scope):
            launch = service.launch_workflow_run(
                WorkflowRunRequest(
                    data_source={"data_snapshot_ref": _snapshot(cas)},
                    params={
                        "control_plane_transition": "legacy_shadow",
                        "workflow_id": "scientist_default",
                        "backend": "primary",
                        "lose_remaining_reply": outcome == "unknown",
                        "policy_target": "submitted",
                        "numeric_policy": "1.5",
                    },
                ),
                principal=RuntimePrincipal.from_access_scope(scope, fixture_identity=True),
            )
        job_id, run_id = launch.job_id, launch.run_id
        database = tmp_path / "effects.sqlite3"
        effect = (
            _UnbudgetedEffectNode(database, operation_id=run_id)
            if unbudgeted
            else _CheckpointedEffectNode(database, operation_id=run_id)
        )
        remaining = (
            _UnbudgetedRemainingEffectNode(database)
            if unbudgeted
            else _RemainingEffectNode(database)
        )
        registry.register(effect)
        registry.register(remaining)
        workflow = WorkflowSpec(
            workflow_id="scientist_default",
            nodes=[
                NodeInvocation(alias="effect", node_id=effect.spec.metadata.component_id),
                NodeInvocation(
                    alias="remaining",
                    node_id=remaining.spec.metadata.component_id,
                    depends_on=["effect"],
                ),
            ],
        )
        # Substitute only the fixture DAG/registry and the precise reply-loss
        # boundary. Primary admission, API forwarding, original Core invocation,
        # budget enforcement and the runner are the production implementations.
        monkeypatch.setattr(builder, "default_workflow_spec", lambda: workflow)
        monkeypatch.setattr(builder, "build_registry_with_builtin_nodes", lambda **_kw: registry)
        monkeypatch.setattr(
            builder,
            "CASCheckpointHook",
            partial(_PrimaryCheckpointHook, lose_after_first=outcome != "unknown"),
        )
        run_dir = cas_root / "runs" / run_id
        original_producer = service._run_legacy_scientist_workflow
        if outcome in {"wrong_params", "wrong_input", "wrong_type"}:
            with _execution_scope(scope):
                alternate_input = _snapshot(cas, value=2)

            def divergent_producer(state_payload, *, job):
                # The adversary creates a genuine owner/attempt/checkpoint chain
                # for this job, but starts from a different immutable policy input.
                changed = deepcopy(state_payload)
                if outcome == "wrong_params":
                    changed["params"]["policy_target"] = "different"
                elif outcome == "wrong_type":
                    changed["params"]["numeric_policy"] = Decimal("1.5")
                else:
                    changed["inputs"]["data_snapshot_ref"] = alternate_input
                return original_producer(changed, job=job)

            monkeypatch.setattr(service, "_run_legacy_scientist_workflow", divergent_producer)
        if outcome == "lost_owner_after_settlement":
            from polisyos.scientist.orchestration.engine import retry as retry_module

            acknowledge = retry_module._acknowledged_view_spend
            observed_cut = {}

            def lose_owner_before_wrapper_verification(view, before):
                # The actual node has returned its selected receipt. The
                # engine's unchanged verifier must now reject the stale owner.
                assert not observed_cut and before == Decimal(5)
                selected = view._acknowledged_settlement()
                assert selected is not None
                payload_ref, receipt_ref = selected
                assert receipt_ref.manifest_profile_sha256 is not None
                assert cas.verify(payload_ref).ok and cas.verify(receipt_ref).ok
                receipt = BudgetLedgerSpendReceipt.model_validate(
                    read_core_json_artifact(cas, receipt_ref).value
                )
                snapshot = FileBudgetLedger(budget_path).snapshot()
                assert receipt.amount == Decimal(2)
                assert snapshot.state.spent["run"] == Decimal(7)
                assert snapshot.spend_receipts == {receipt.event_id: receipt}
                original_owner = raw_control.current_execution_job_record()
                assert original_owner.attempt == 1
                admin_control = ControlPlaneStore(
                    backend="sqlite", sqlite_path=tmp_path / "control.sqlite3"
                )
                with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
                    connection.execute(
                        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job_id),
                    )
                winner = admin_control.lease_next_job(
                    worker_id="post-receipt-winner", lease_seconds=300
                )
                assert winner is not None and winner.attempt == 2
                observed_cut.update(original=original_owner, winner=winner, receipt=receipt)
                return acknowledge(view, before)

            monkeypatch.setattr(
                retry_module, "_acknowledged_view_spend", lose_owner_before_wrapper_verification
            )
            assert (
                dispatch_one_control_job(
                    store=control, handler=service._process_control_job, expected_job_id=job_id
                )
                == job_id
            )
            monkeypatch.setattr(retry_module, "_acknowledged_view_spend", acknowledge)
            winner = observed_cut["winner"]
            receipt = observed_cut["receipt"]
            assert raw_control.get_job(job_id) == winner
            assert winner.state == "running" and winner.progress.get("budgets") is None
            assert len(_effects(database)) == 1
            with _execution_scope(scope):
                attempts = read_runtime_invocation_attempts(
                    cas, run_dir / "trace.jsonl", run_id=run_id
                )
                assert len(attempts) == 1
                assert attempts[0].outcome is None or (
                    attempts[0].outcome.status == "unknown"
                    and attempts[0].outcome.outcome_state_ref is None
                )
            # The actual replacement handler has no accepted completed
            # frontier. It must refuse, preserving the real charge as unknown.
            replacement = ControlWorker(
                store=control,
                handler=service._process_control_job,
                worker_id=winner.lease_owner,
                lease_seconds=300,
            )
            replacement._run_with_lease_heartbeat(winner)
            current = raw_control.get_job(job_id)
            response = service.get_job_status(job_id)
            assert current is not None and current.attempt == 2 and current.state == "failed"
            assert response.failure is not None
            assert response.failure.code == "checkpoint_handover_outcome_unknown"
            assert response.failure.retryable is False
            assert current.progress["effect_state"] == "outcome_unknown"
            assert current.progress.get("budgets") is None
            assert current.progress.get("checkpoint_ref") is None
            assert len(_effects(database)) == 1
            with sqlite3.connect(database) as connection:
                assert (
                    connection.execute("SELECT COUNT(*) FROM remaining_effects").fetchone()[0] == 0
                )
            fresh = FileBudgetLedger(budget_path)
            assert fresh.load().spent["run"] == Decimal(7)
            assert fresh.resolve_spend(receipt.event_id) == receipt
            original_owner = observed_cut["original"]
            with (
                pytest.raises(ControlJobLeaseLostError),
                control.job_execution_fence(
                    job_id=job_id,
                    worker_id=original_owner.lease_owner,
                    attempt=original_owner.attempt,
                ),
            ):
                control.complete_job(job_id=job_id)
            assert raw_control.get_job(job_id) == current
            return
        with pytest.raises((_LostCheckpointReply, BaseExceptionGroup)) as lost:
            dispatch_one_control_job(
                store=control, handler=service._process_control_job, expected_job_id=job_id
            )
        if isinstance(lost.value, BaseExceptionGroup):
            interrupted, other = lost.value.split(_LostCheckpointReply)
            assert interrupted is not None and other is None
        monkeypatch.setattr(service, "_run_legacy_scientist_workflow", original_producer)
        first = raw_control.get_job(job_id)
        assert first is not None and first.attempt == 1 and first.state == "running"
        assert first.lease_owner is not None
        with _execution_scope(scope):
            head = load_checkpoint_head(run_dir)
            assert head is not None
            original = load_checkpoint(cas, head.checkpoint_ref)
            assert original.metadata.completed_nodes == ["effect"]
            attempts = read_runtime_invocation_attempts(cas, run_dir / "trace.jsonl", run_id=run_id)
            actual_initial = read_core_json_artifact(cas, attempts[0].basis.input_state_ref).value
            assert type(actual_initial["params"]["numeric_policy"]) is (
                Decimal if outcome == "wrong_type" else str
            )
            assert original.metadata.execution_budget_contract == "admitted_workflow_budget_v1"
            # This original production entrypoint admits an unbounded workflow.
            # The separate bounded native fixture exercises finite expiry.
            assert original.metadata.execution_deadline_at is None
            receipt = None
            if unbudgeted:
                assert attempts[0].basis.budget_middleware_active is False
                assert attempts[0].basis.budget_owner_identity is None
            else:
                receipt = _confirmed_effect_receipt(cas, run_dir, run_id)
                assert receipt is not None and receipt.amount == Decimal(2)
                assert middleware is not None
                assert middleware.resolve_spend_safe(receipt.event_id) == receipt
        if outcome == "stale_ledger":
            assert initial_ledger is not None
            budget_path.write_bytes(initial_ledger)
        if outcome == "late_stale_ledger":
            pre_check = BudgetMiddleware.pre_check
            rollback_seen = []

            def restore_before_precheck(self, alias, budget_key="run"):
                if alias == "remaining":
                    assert not rollback_seen
                    rollback_seen.append(True)
                    assert initial_ledger is not None
                    budget_path.write_bytes(initial_ledger)
                return pre_check(self, alias, budget_key=budget_key)

            monkeypatch.setattr(BudgetMiddleware, "pre_check", restore_before_precheck)
        with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
            connection.execute(
                "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job_id),
            )
        replacement_seen = {}
        if outcome == "lost_lease":
            reconcile = checkpoint_module._reconcile_checkpoint_attempts

            def take_over_after_reconciliation(*args, **kwargs):
                result = reconcile(*args, **kwargs)
                # B entered under a live SQL fence and finished actual owner
                # reconciliation. C now wins before B's residual dispatch.
                with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
                    connection.execute(
                        "UPDATE control_jobs SET lease_expires_at = ? WHERE job_id = ?",
                        ((datetime.now(UTC) - timedelta(seconds=1)).isoformat(), job_id),
                    )
                admin_control = ControlPlaneStore(
                    backend="sqlite", sqlite_path=tmp_path / "control.sqlite3"
                )
                winner = admin_control.lease_next_job(worker_id="fixture-C", lease_seconds=300)
                assert winner is not None and winner.attempt == 3
                replacement_seen["job"] = winner
                return result

            monkeypatch.setattr(
                checkpoint_module, "_reconcile_checkpoint_attempts", take_over_after_reconciliation
            )
        assert (
            dispatch_one_control_job(
                store=control, handler=service._process_control_job, expected_job_id=job_id
            )
            == job_id
        )
        record = raw_control.get_job(job_id)
        assert record is not None and record.run_id == run_id
        assert record.attempt == (3 if outcome == "lost_lease" else 2)
        response = service.get_job_status(job_id)
        assert response.job_id == job_id
        assert len(_effects(database)) == 1
        with sqlite3.connect(database) as connection:
            remaining_rows = connection.execute(
                "SELECT operation_id FROM remaining_effects"
            ).fetchall()
        assert len(remaining_rows) == (
            1 if outcome in {"remaining", "unknown", "unbudgeted"} else 0
        )
        with (
            pytest.raises(ControlJobLeaseLostError),
            control.job_execution_fence(
                job_id=job_id, worker_id=first.lease_owner, attempt=first.attempt
            ),
        ):
            raw_control.complete_job(job_id=job_id)
        with sqlite3.connect(tmp_path / "control.sqlite3") as connection:
            assert connection.execute("SELECT COUNT(*) FROM control_jobs").fetchone()[0] == 1
        if outcome == "lost_lease":
            assert receipt is not None
            winner = replacement_seen["job"]
            assert record.state == "running" and record.lease_owner == "fixture-C"
            assert record.progress == winner.progress
            assert FileBudgetLedger(budget_path).load().spent["run"] == Decimal(7)
            assert FileBudgetLedger(budget_path).resolve_spend(receipt.event_id) == receipt
        elif outcome in {"remaining", "unbudgeted"}:
            assert record.state == "completed"
            assert record.progress["logical_operation_id"] == run_id
            assert record.progress["checkpoint_handover"] == "reconciled"
            assert record.progress["authority_result"] == "candidate_only"
            assert record.progress["completed_nodes"] == ["effect", "remaining"]
            selected = ArtifactRef.model_validate(record.progress["checkpoint_ref"])
            with _execution_scope(scope):
                fresh_cas = FileSystemCAS(cas_root).with_ambient_ownership_enforcement()
                final = load_checkpoint(fresh_cas, selected)
                final_state = materialize_checkpoint_state(fresh_cas, selected)
            assert final.metadata.execution_deadline_at == original.metadata.execution_deadline_at
            if unbudgeted:
                assert not budget_path.exists()
                assert final_state["budgets"] == {}
            else:
                assert receipt is not None
                assert final_state["budgets"]["run_spent_usd"] == Decimal(8)
                assert FileBudgetLedger(budget_path).load().spent["run"] == Decimal(8)
                assert FileBudgetLedger(budget_path).resolve_spend(receipt.event_id) == receipt
        else:
            assert record.state == "failed"
            assert response.failure is not None and response.failure.retryable is False
            if outcome in {"unknown", "stale_ledger", "wrong_params", "wrong_input", "wrong_type"}:
                assert response.failure.code == "checkpoint_handover_outcome_unknown"
                assert record.progress["effect_state"] == "outcome_unknown"
            if outcome == "late_stale_ledger":
                assert rollback_seen == [True]
                assert response.failure.code == "checkpoint_handover_outcome_unknown"
                assert record.progress["effect_state"] == "outcome_unknown"
            if outcome in {"wrong_params", "wrong_input", "wrong_type"}:
                assert (
                    response.failure.message
                    == "checkpoint_handover_original_payload_state_mismatch"
                )
    finally:
        service.close()


@pytest.mark.parametrize(
    ("workflow_id", "backend", "reason"),
    [
        ("scientist_discovery", "local", "workflow_budget_profile_requires_scientist_default"),
        ("scientist_default", "temporal", "workflow_budget_profile_requires_local_backend"),
        ("scientist_default", "ray", "workflow_budget_profile_requires_local_backend"),
    ],
)
def test_configured_workflow_budget_refuses_unsupported_profile_before_producer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    workflow_id: str,
    backend: str,
    reason: str,
) -> None:
    """Neither an unsupported DAG nor distributed setup may drop an active budget."""
    from polisyos.scientist.api import run_experiment

    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", backend)
    ledger = FileBudgetLedger(tmp_path / "budget.json")
    middleware = BudgetMiddleware(
        BudgetState(
            limits={"run": BudgetLimit(key="run", max_usd=Decimal(10))},
            spent={"run": Decimal(5)},
        ),
        ledger=ledger,
    )
    before = middleware.snapshot_safe()
    cas = FileSystemCAS(tmp_path / "cas")
    with pytest.raises(ValueError, match=reason):
        run_experiment(
            {"run_id": "unsupported-budget-profile", "params": {"workflow_id": workflow_id}},
            store=cas,
            budget_middleware=middleware,
        )
    assert middleware.snapshot_safe() == before
    assert not (tmp_path / "cas" / "runs").exists()
