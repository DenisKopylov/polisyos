"""RUN-03: actual registered return/raise retry policy and durable cost witness.

The ordinary typed failure is an explicit logical-failure signal. With a real
issued settlement proof the engine can persist that failure and its local cost;
this does not infer a logical outcome from money alone. Without that profile,
the legacy raised completion remains unknown. Unknown/timeout cause chains are
separate controls and are not qualified by this finite plain-error producer.
"""

from __future__ import annotations

import logging
import sqlite3
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from _helpers.lane06_failure_parity import (
    PARITY_CODE,
    PARITY_NODE_ID,
    AsyncCostedFailureNode,
    CostedFailureNode,
)

from polisyos.core.artifacts import read_core_json_artifact
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run import RunContext, read_runtime_invocation_attempts, read_terminal_run
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import (
    BudgetLedgerSpendReceipt,
    FileBudgetLedger,
)
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import ErrorCategory
from polisyos.scientist.orchestration.engine.executor import WorkflowReport
from polisyos.scientist.orchestration.engine.finalization import WorkflowStateFinalization
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

pytestmark = pytest.mark.integration


async def _execute_and_read(
    root: Path,
    *,
    route: Literal["sync_bridge", "genuine_async"],
    delivery: str,
    costed: bool = True,
    category: ErrorCategory = ErrorCategory.FATAL,
    allow_retry: bool = True,
) -> tuple[int, Decimal | None, str, WorkflowReport]:
    root.mkdir()
    store = FileSystemCAS(root / "cas")
    registry_bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run_id = f"run03-parity-{route}-{delivery}"
    run = RunContext.start(store=store, registry_bundle=registry_bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    ledger_path = root / "budget.json"
    middleware = None
    if costed:
        middleware = BudgetMiddleware(
            BudgetState(limits={"run": BudgetLimit(key="run", max_usd=Decimal("20"))}),
            ledger=FileBudgetLedger(ledger_path),
            invocation_settlement_profile="single_owner_local_v1",
        )
        middleware.record_spend_safe("run", Decimal("5"))
    effects_path = root / "effects.sqlite"
    node_type = AsyncCostedFailureNode if route == "genuine_async" else CostedFailureNode
    node = node_type(effects_path, costed=costed)
    registry = NodeRegistry()
    registry.register(node)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": registry_bundle.bundle_ref},
        params={"delivery": delivery, "category": category.value, "untouched": "baseline"},
        budgets={"run_spent_usd": Decimal("5")} if costed else {},
    )
    workflow = WorkflowSpec(
        workflow_id="lane06_registered_failure_parity",
        nodes=[
            NodeInvocation(
                alias="effect",
                node_id=PARITY_NODE_ID,
                retry=RetryPolicy(
                    max_retries=1,
                    retry_on=[PARITY_CODE] if allow_retry else [],
                    backoff_base_s=0.1,
                    jitter="none",
                ),
            )
        ],
    )
    result = await AsyncWorkflowExecutor(
        ctx,
        registry,
        max_parallelism=1,
        budget_middleware=middleware,
        strict_budget_attempts=costed,
    ).execute(workflow, state)
    assert result.run_ref is not None
    baseline_params = {"delivery": delivery, "category": category.value, "untouched": "baseline"}
    assert state.params == baseline_params
    fresh = FileSystemCAS(store.root)
    run_dir = store.root / "runs" / run_id
    terminal = read_terminal_run(fresh, run_dir, run_id=run_id, access_scope=None)
    assert terminal.run_ref == result.run_ref
    assert terminal.run_manifest.status == "fail"
    assert len(terminal.terminal_inputs) == 1
    finalization = WorkflowStateFinalization.model_validate(
        read_core_json_artifact(fresh, terminal.terminal_inputs[0]).value
    )
    final_state = ExperimentState.model_validate(
        read_core_json_artifact(fresh, finalization.final_state_ref).value
    )
    report_ref = next(
        item.artifact_ref
        for item in finalization.output_bindings
        if item.state_path == "reports_index.workflow_report"
    )
    report = WorkflowReport.model_validate(read_core_json_artifact(fresh, report_ref).value)
    assert report.status == "fail" and len(report.nodes) == 1
    assert report.nodes[0].status == "fail"
    assert final_state.params == baseline_params
    assert not any(ref.kind == "fixture.run03.effect" for ref in terminal.run_manifest.outputs)

    attempts = read_runtime_invocation_attempts(fresh, run_dir / "trace.jsonl", run_id=run_id)
    with sqlite3.connect(effects_path) as connection:
        effects = connection.execute(
            "SELECT attempt_id, basis_ref, payload_ref, receipt_ref FROM effects ORDER BY rowid"
        ).fetchall()
    assert len(effects) == len(attempts)
    ledger = FileBudgetLedger(ledger_path) if costed else None
    for attempt, (attempt_id, raw_basis, raw_payload, raw_receipt) in zip(
        attempts, effects, strict=True
    ):
        basis_ref = ArtifactRef.model_validate_json(raw_basis)
        payload_ref = ArtifactRef.model_validate_json(raw_payload)
        assert attempt.basis.attempt_id == attempt_id
        assert attempt.basis_ref == basis_ref
        assert attempt.basis.node_alias == "effect"
        assert attempt.basis.component_id == str(PARITY_NODE_ID)
        # That identity is intentionally limited to four protected builtins.
        # A registered candidate is not promoted into one by this witness.
        assert attempt.basis.implementation_identity is None
        assert all(
            ref.manifest_profile_sha256 is not None and fresh.verify(ref).ok
            for ref in (attempt.basis.workflow_spec_ref, attempt.basis.input_state_ref)
        )
        selected_workflow = WorkflowSpec.model_validate(
            read_core_json_artifact(fresh, attempt.basis.workflow_spec_ref).value
        )
        assert selected_workflow == workflow
        selected_input = ExperimentState.model_validate(
            read_core_json_artifact(fresh, attempt.basis.input_state_ref).value
        )
        assert selected_input.run_id == run_id and selected_input.params == baseline_params
        assert attempt.basis.budget_middleware_active is costed
        assert attempt.basis.invocation_settlement_profile == (
            "single_owner_local_v1" if costed else None
        )
        assert all(
            ref.manifest_profile_sha256 is not None and fresh.verify(ref).ok
            for ref in (basis_ref, payload_ref)
        )
        payload = read_core_json_artifact(fresh, payload_ref).value
        assert payload == {"run_id": run_id, "attempt_id": attempt_id, "cause": PARITY_CODE}
        receipt_ref = None
        if costed:
            assert ledger is not None
            receipt_ref = ArtifactRef.model_validate_json(raw_receipt)
            assert receipt_ref.manifest_profile_sha256 is not None and fresh.verify(receipt_ref).ok
            receipt = BudgetLedgerSpendReceipt.model_validate(
                read_core_json_artifact(fresh, receipt_ref).value
            )
            assert receipt.amount == Decimal("2") and receipt.provider == "run03-local-fixture"
            assert ledger.resolve_spend(receipt.event_id) == receipt
            receipt_manifest = fresh.get_manifest(receipt_ref)
            assert any(
                item.role == "invocation_basis"
                and item.artifact_id == basis_ref.artifact_id
                and item.manifest_profile_sha256 == basis_ref.manifest_profile_sha256
                for item in receipt_manifest.inputs
            )
        else:
            assert raw_receipt is None
        assert attempt.outcome is not None
        if delivery == "return":
            assert attempt.outcome.status == "fail"
            assert attempt.outcome.budget_receipt_ref == receipt_ref
            assert report.nodes[0].error is not None
            assert report.nodes[0].error.code == PARITY_CODE
            assert report.nodes[0].error.category is category
        elif costed:
            # The explicitly raised typed failure establishes the failure;
            # the independently verified receipt establishes only its cost.
            assert attempt.outcome.status == "fail"
            assert attempt.outcome.budget_receipt_ref == receipt_ref
            assert attempt.outcome.outcome_state_ref is not None
            completed_failure = ExperimentState.model_validate(
                read_core_json_artifact(fresh, attempt.outcome.outcome_state_ref).value
            )
            assert completed_failure.params == baseline_params
            assert completed_failure.budgets["run_spent_usd"] == Decimal("7")
        else:
            # Without the issued monetary completion profile, the existing
            # protocol records no reconstructed completed producer state.
            assert attempt.outcome.status == "unknown"
            assert attempt.outcome.outcome_state_ref is None
            assert attempt.outcome.budget_receipt_ref is None
    spent = ledger.snapshot().state.spent["run"] if ledger is not None else None
    if costed:
        assert final_state.budgets["run_spent_usd"] == spent
    else:
        assert final_state.budgets == {}
    return len(effects), spent, report.nodes[0].status, report


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["sync_bridge", "genuine_async"])
async def test_registered_costed_permanent_return_raise_have_one_attempt_and_known_spend(
    tmp_path: Path, route: Literal["sync_bridge", "genuine_async"]
) -> None:
    """Same declared permanent cause refuses retry after the real local effect."""
    projections = []
    for delivery in ("return", "raise"):
        attempts, spent, status, _report = await _execute_and_read(
            tmp_path / delivery, route=route, delivery=delivery
        )
        assert attempts == 1, "permanent cause repeated its physical effect"
        assert spent == Decimal("7")
        projections.append((attempts, spent, status))
    assert projections == [(1, Decimal("7"), "fail")] * 2


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["sync_bridge", "genuine_async"])
@pytest.mark.parametrize(
    ("category", "allow_retry", "expected_attempts"),
    [
        (ErrorCategory.FATAL, True, 1),
        (ErrorCategory.TRANSIENT, True, 2),
        (ErrorCategory.TRANSIENT, False, 1),
    ],
)
async def test_registered_return_raise_reach_the_same_category_and_filter_policy(
    tmp_path: Path,
    route: Literal["sync_bridge", "genuine_async"],
    category: ErrorCategory,
    allow_retry: bool,
    expected_attempts: int,
) -> None:
    """Typed category changes real dispatch count while the code stays fixed.

    The non-monetary profile removes the strict receipt-completion refusal
    that would otherwise mask exception classification. It still uses the
    actual registry, Core attempt callbacks, CAS and terminal fresh reader.
    Its SQLite rows count actual entries with a declared known fixture failure;
    they are not evidence that replaying an unknown external action is safe.
    A matching code plus diagnostic category is insufficient for the fatal
    case; the empty retry filter also constrains a typed transient cause.
    """
    projections = []
    for delivery in ("return", "raise"):
        attempts, spent, status, _report = await _execute_and_read(
            tmp_path / delivery,
            route=route,
            delivery=delivery,
            costed=False,
            category=category,
            allow_retry=allow_retry,
        )
        assert attempts == expected_attempts
        assert spent is None
        projections.append((attempts, status))
    assert projections == [(expected_attempts, "fail")] * 2
