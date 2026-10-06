"""Behavioral witness for resuming a genuinely partial REP-01 workflow."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.nodes.builtins.state_keys import INPUT_REGISTRY_BUNDLE_REF
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.checkpoint import (
    COMPLETED_NODE_STATUS_CONTRACT,
    CASCheckpointHook,
    load_checkpoint_history,
    resolve_latest_checkpoint,
    resume_from_checkpoint,
)
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner.config import WorkflowRunnerConfig
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_PARTIAL_RUN_ID = "R_rep_01_partial_resume"
_FRESH_RUN_ID = "R_rep_01_partial_fresh"
_INCOME_NODE_ID = "scientist.node_rep01_income@1.0.0"
_RATE_NODE_ID = "scientist.node_rep01_rate@1.0.0"
_TAX_NODE_ID = "scientist.node_rep01_tax@1.0.0"
_INPUT_INCOME_CENTS = 10_000
_INPUT_RATE_BASIS_POINTS = 1_000
_BASIS_POINTS_PER_WHOLE = 10_000


def _metadata(component_id: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(component_id),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} REP-01 partial-resume test node",
        tags=["test", "rep-01"],
        capabilities=Capability.SCIENTIST_NODE,
    )


class _CopyInputNode:
    def __init__(
        self,
        *,
        node_id: str,
        name: str,
        input_key: str,
        output_key: str,
    ) -> None:
        self.input_key = input_key
        self.output_key = output_key
        self._spec = NodeSpec(
            metadata=_metadata(node_id, name),
            state_reads=[f"params.{input_key}"],
            state_writes=[f"params.{output_key}"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def _execute(self, state: ExperimentState) -> NodeOutcome:
        updated = state.model_copy(deep=True)
        updated.params[self.output_key] = updated.params[self.input_key]
        return NodeOutcome(status="ok", state=updated)

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return self._execute(state)

    async def execute_async(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        return self._execute(state)


class _TaxCalculationNode:
    def __init__(
        self,
        *,
        interrupted_run_id: str | None = None,
        started: asyncio.Event | None = None,
        release: asyncio.Event | None = None,
        late_finished: asyncio.Event | None = None,
    ) -> None:
        self.interrupted_run_id = interrupted_run_id
        self.started = started
        self.release = release
        self.late_finished = late_finished
        self.invocations = 0
        self._interrupted_once = False
        self._spec = NodeSpec(
            metadata=_metadata(_TAX_NODE_ID, "Tax calculation"),
            state_reads=["params.gross_income_cents", "params.tax_rate_basis_points"],
            state_writes=["params.tax_cents", "params.net_income_cents"],
        )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def _calculate(self, state: ExperimentState) -> NodeOutcome:
        updated = state.model_copy(deep=True)
        gross_income_cents = int(updated.params["gross_income_cents"])
        rate_basis_points = int(updated.params["tax_rate_basis_points"])
        tax_numerator = gross_income_cents * rate_basis_points
        assert tax_numerator % _BASIS_POINTS_PER_WHOLE == 0
        tax_cents = tax_numerator // _BASIS_POINTS_PER_WHOLE
        updated.params["tax_cents"] = tax_cents
        updated.params["net_income_cents"] = gross_income_cents - tax_cents
        return NodeOutcome(status="ok", state=updated)

    def execute(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.invocations += 1
        return self._calculate(state)

    async def execute_async(self, _ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.invocations += 1
        if state.run_id == self.interrupted_run_id and not self._interrupted_once:
            assert self.started is not None
            assert self.release is not None
            assert self.late_finished is not None
            self._interrupted_once = True

            # The runtime passes async attempts an isolated state copy. Mutate
            # it before the real node deadline, then return the poisoned result
            # only after the timed-out caller has stopped waiting.
            state.params["tax_cents"] = 999_999
            state.params["net_income_cents"] = -989_999
            self.started.set()
            await self.release.wait()
            self.late_finished.set()
            return NodeOutcome(status="ok", state=state)
        return self._calculate(state)


def _workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="rep_01_partial_resume",
        required_binds=["params.income_input_cents", "params.tax_rate_input_basis_points"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="income",
                node_id=ComponentId.parse(_INCOME_NODE_ID),
            ),
            NodeInvocation(
                alias="rate",
                node_id=ComponentId.parse(_RATE_NODE_ID),
                depends_on=["income"],
            ),
            NodeInvocation(
                alias="tax",
                node_id=ComponentId.parse(_TAX_NODE_ID),
                depends_on=["rate"],
                timeout_s=1.0,
            ),
        ],
    )


def _registry(
    *,
    interrupted_run_id: str | None = None,
    started: asyncio.Event | None = None,
    release: asyncio.Event | None = None,
    late_finished: asyncio.Event | None = None,
) -> tuple[NodeRegistry, _TaxCalculationNode]:
    registry = NodeRegistry()
    registry.register(
        _CopyInputNode(
            node_id=_INCOME_NODE_ID,
            name="Gross income",
            input_key="income_input_cents",
            output_key="gross_income_cents",
        )
    )
    registry.register(
        _CopyInputNode(
            node_id=_RATE_NODE_ID,
            name="Tax rate",
            input_key="tax_rate_input_basis_points",
            output_key="tax_rate_basis_points",
        )
    )
    tax_node = _TaxCalculationNode(
        interrupted_run_id=interrupted_run_id,
        started=started,
        release=release,
        late_finished=late_finished,
    )
    registry.register(tax_node)
    return registry, tax_node


def _context(
    store: FileSystemCAS,
    *,
    registry_bundle_ref: ArtifactRef,
    run_id: str,
) -> ExecutionContext:
    run = RunContext.start(
        store=store,
        registry_bundle=registry_bundle_ref,
        run_id=run_id,
    )
    return ExecutionContext(
        store=store,
        run=run,
        logger=logging.getLogger("rep_01_partial_resume"),
    )


def _initial_state(run_id: str, registry_bundle_ref: ArtifactRef) -> ExperimentState:
    return ExperimentState(
        run_id=run_id,
        inputs={INPUT_REGISTRY_BUNDLE_REF: registry_bundle_ref},
        params={
            "income_input_cents": _INPUT_INCOME_CENTS,
            "tax_rate_input_basis_points": _INPUT_RATE_BASIS_POINTS,
        },
    )


@pytest.mark.integration
def test_real_partial_checkpoint_resumes_only_the_remaining_tax_node(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout after two real node commits must resume to the fresh-run result."""
    store = FileSystemCAS(tmp_path / "cas")
    registry_bundle = build_default_registry_bundle(store)
    workflow = _workflow()
    run_dir = store.root / "runs" / _PARTIAL_RUN_ID

    async def _execute_until_partial_checkpoint() -> tuple[NodeRegistry, _TaxCalculationNode]:
        started = asyncio.Event()
        release = asyncio.Event()
        late_finished = asyncio.Event()
        registry, tax_node = _registry(
            interrupted_run_id=_PARTIAL_RUN_ID,
            started=started,
            release=release,
            late_finished=late_finished,
        )
        ctx = _context(
            store,
            registry_bundle_ref=registry_bundle.bundle_ref,
            run_id=_PARTIAL_RUN_ID,
        )
        hook = CASCheckpointHook(store=store, run_dir=run_dir)
        try:
            result = await AsyncWorkflowExecutor(
                ctx,
                registry,
                checkpoint_hook=hook,
                max_parallelism=1,
            ).execute(
                workflow,
                _initial_state(_PARTIAL_RUN_ID, registry_bundle.bundle_ref),
            )

            assert started.is_set(), "the terminal node did not enter its real async attempt"
            assert result.report.status == "fail"
            assert [record.alias for record in result.report.nodes] == ["income", "rate", "tax"]
            assert [record.status for record in result.report.nodes] == ["ok", "ok", "fail"]
            terminal = result.report.nodes[-1]
            assert terminal.error is not None
            assert terminal.error.code == "node.timeout"
            assert tax_node.invocations == 1

            before_late_result = resolve_latest_checkpoint(store, _PARTIAL_RUN_ID)
            assert before_late_result is not None
            before_head, before_checkpoint = before_late_result
            before_state = ExperimentState.model_validate(before_checkpoint.state)
            assert before_checkpoint.metadata.completed_nodes == ["income", "rate"]
            assert before_checkpoint.metadata.completed_node_status_contract == (
                COMPLETED_NODE_STATUS_CONTRACT
            )
            assert before_head.sequence_number == 1
            assert before_state.params["gross_income_cents"] == _INPUT_INCOME_CENTS
            assert before_state.params["tax_rate_basis_points"] == _INPUT_RATE_BASIS_POINTS
            assert "tax_cents" not in before_state.params
            assert "net_income_cents" not in before_state.params
            assert before_state.inputs[INPUT_REGISTRY_BUNDLE_REF] == registry_bundle.bundle_ref

            history_before_late_result = load_checkpoint_history(run_dir)
            assert history_before_late_result is not None
            assert [entry.node_alias for entry in history_before_late_result.entries] == [
                "income",
                "rate",
            ]
        finally:
            # Let the timed-out, shielded async attempt return so its late
            # result can be checked against the durable partial frontier.
            release.set()
            if started.is_set():
                await late_finished.wait()

        after_late_result = resolve_latest_checkpoint(store, _PARTIAL_RUN_ID)
        assert after_late_result is not None
        after_head, after_checkpoint = after_late_result
        after_state = ExperimentState.model_validate(after_checkpoint.state)
        assert after_head.checkpoint_ref == before_head.checkpoint_ref
        assert after_checkpoint.metadata.completed_nodes == ["income", "rate"]
        assert after_state.params == before_state.params
        assert "tax_cents" not in after_state.params
        assert "net_income_cents" not in after_state.params
        history_after_late_result = load_checkpoint_history(run_dir)
        assert history_after_late_result is not None
        assert [entry.node_alias for entry in history_after_late_result.entries] == [
            "income",
            "rate",
        ]
        return registry, tax_node

    registry, tax_node = asyncio.run(_execute_until_partial_checkpoint())

    # The canonical owner must find the saved source reference in the real
    # checkpoint input. Supplying a new registry-bundle ref here would mask
    # whether the continuation retained its original execution input.
    monkeypatch.setenv("POLISYOS_RUNNER_BACKEND", "local")
    monkeypatch.setenv("POLISYOS_RUNNER_MAX_PARALLELISM", "1")
    assert WorkflowRunnerConfig.from_env().backend == "local"
    resumed = resume_from_checkpoint(
        store,
        _PARTIAL_RUN_ID,
        workflow=workflow,
        registry=registry,
    )
    assert resumed.report.status == "ok"
    assert [record.alias for record in resumed.report.nodes] == ["tax"]
    assert [record.status for record in resumed.report.nodes] == ["ok"]
    assert tax_node.invocations == 2

    resumed_frontier = resolve_latest_checkpoint(store, _PARTIAL_RUN_ID)
    assert resumed_frontier is not None
    resumed_head, resumed_checkpoint = resumed_frontier
    resumed_state = ExperimentState.model_validate(resumed_checkpoint.state)
    assert resumed_head.node_alias == "tax"
    assert resumed_checkpoint.metadata.completed_nodes == ["income", "rate", "tax"]
    assert resumed_state.inputs[INPUT_REGISTRY_BUNDLE_REF] == registry_bundle.bundle_ref

    direct_registry, direct_tax_node = _registry()
    direct_run = asyncio.run(
        AsyncWorkflowExecutor(
            _context(
                store,
                registry_bundle_ref=registry_bundle.bundle_ref,
                run_id=_FRESH_RUN_ID,
            ),
            direct_registry,
            checkpoint_hook=CASCheckpointHook(
                store=store,
                run_dir=store.root / "runs" / _FRESH_RUN_ID,
            ),
            max_parallelism=1,
        ).execute(
            workflow,
            _initial_state(_FRESH_RUN_ID, registry_bundle.bundle_ref),
        )
    )
    assert direct_run.report.status == "ok"
    assert [record.alias for record in direct_run.report.nodes] == ["income", "rate", "tax"]
    assert direct_tax_node.invocations == 1
    direct_frontier = resolve_latest_checkpoint(store, _FRESH_RUN_ID)
    assert direct_frontier is not None
    _, direct_checkpoint = direct_frontier
    direct_state = ExperimentState.model_validate(direct_checkpoint.state)
    assert direct_checkpoint.metadata.completed_nodes == ["income", "rate", "tax"]
    assert direct_state.inputs[INPUT_REGISTRY_BUNDLE_REF] == registry_bundle.bundle_ref

    # This oracle is calculated from immutable initial values, independently
    # of both node results and both persisted execution states.
    oracle_tax_numerator = _INPUT_INCOME_CENTS * _INPUT_RATE_BASIS_POINTS
    assert oracle_tax_numerator % _BASIS_POINTS_PER_WHOLE == 0
    oracle_tax_cents = oracle_tax_numerator // _BASIS_POINTS_PER_WHOLE
    oracle_net_income_cents = _INPUT_INCOME_CENTS - oracle_tax_cents
    expected_outputs = {
        "gross_income_cents": _INPUT_INCOME_CENTS,
        "tax_rate_basis_points": _INPUT_RATE_BASIS_POINTS,
        "tax_cents": oracle_tax_cents,
        "net_income_cents": oracle_net_income_cents,
    }
    for key, expected in expected_outputs.items():
        assert resumed_state.params[key] == expected
        assert direct_state.params[key] == expected
        assert resumed_state.params[key] == direct_state.params[key]
    assert oracle_tax_cents == 1_000
    assert oracle_net_income_cents == 9_000
