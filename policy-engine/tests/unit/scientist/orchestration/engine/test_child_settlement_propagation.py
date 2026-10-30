"""An uncertain committed release must retain its receipt and never be retried."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.child_custody import (
    ChildComputationOutcomeUnknown,
    ChildGuardedStageWriteUnknown,
    ChildParentSettlementError,
    ChildReleaseReceipt,
)
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.protocol import NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import RetryPolicy
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

if TYPE_CHECKING:
    from pathlib import Path


_REF = ArtifactRef(
    artifact_id="sha256:" + "a" * 64,
    kind="test.release",
    media_type="application/json",
    manifest_profile_sha256="sha256:" + "b" * 64,
)
_SPEC = NodeSpec(
    metadata=ComponentMetadata(
        component_id=ComponentId.parse("scientist.node_settlement_unknown_probe@1.0.0"),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name="Settlement unknown probe",
        description="A committed release with uncertain parent effects",
        capabilities=Capability.SCIENTIST_NODE,
    )
)


class _UnknownNode:
    def __init__(self, error: ChildComputationOutcomeUnknown) -> None:
        self.error = error
        self.calls = 0

    @property
    def spec(self) -> NodeSpec:
        return _SPEC

    def execute(self, _ctx: ExecutionContext, _state: ExperimentState) -> None:
        self.calls += 1
        raise self.error


def _fixture(tmp_path: Path) -> tuple[ExecutionContext, NodeRegistry, WorkflowSpec, _UnknownNode]:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id="unknown-run")
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("settlement-test"))
    receipt = ChildReleaseReceipt(
        release_id="test-release",
        release_ref=_REF,
        projection_ref=_REF,
        released_refs=(_REF,),
        execution_outcome="completed",
        release_outcome="released",
    )
    node = _UnknownNode(ChildParentSettlementError(receipt))
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="settlement_unknown",
        nodes=[
            NodeInvocation(
                alias="unknown",
                node_id=_SPEC.metadata.component_id,
                retry=RetryPolicy(max_retries=2),
            )
        ],
    )
    return ctx, registry, workflow, node


def test_sync_executor_preserves_receipt_and_never_retries(tmp_path: Path) -> None:
    ctx, registry, workflow, node = _fixture(tmp_path)
    with pytest.raises(ChildParentSettlementError) as observed:
        WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id="unknown-run"))
    assert observed.value is node.error
    assert observed.value.receipt is node.error.receipt
    assert node.calls == 1


def test_search_stage_does_not_convert_unknown_effect_into_rejection() -> None:
    """The real generic expensive-stage fallback cannot turn unknown into a result."""
    from polisyos.scientist.methods.search.stages import ExpensiveStage

    unknown = ChildComputationOutcomeUnknown("effect outcome requires reconciliation")

    class Engine:
        calls = 0

        def run(self, _initial_state: object) -> object:
            self.calls += 1
            raise unknown

    engine = Engine()
    with pytest.raises(ChildComputationOutcomeUnknown) as observed:
        ExpensiveStage(engine).evaluate({}, {})
    assert observed.value is unknown
    assert engine.calls == 1


def _leaves(exc: BaseException) -> list[BaseException]:
    if isinstance(exc, BaseExceptionGroup):
        return [leaf for child in exc.exceptions for leaf in _leaves(child)]
    return [exc]


def test_async_host_preserves_receipt_and_never_retries(tmp_path: Path) -> None:
    ctx, registry, workflow, node = _fixture(tmp_path)
    with pytest.raises((ChildParentSettlementError, BaseExceptionGroup)) as observed:
        asyncio.run(
            AsyncWorkflowExecutor(ctx, registry).execute(
                workflow, ExperimentState(run_id="unknown-run")
            )
        )
    errors = _leaves(observed.value)
    assert any(error is node.error for error in errors)
    assert node.error.receipt.release_ref == _REF
    assert node.calls == 1


@pytest.mark.parametrize("async_host", [False, True])
def test_guarded_stage_unknown_never_retries(tmp_path: Path, async_host: bool) -> None:
    ctx, registry, workflow, node = _fixture(tmp_path)
    stage_unknown = ChildGuardedStageWriteUnknown(
        release_id="test-release",
        root_run_id="unknown-run",
        parent_attempt_id="parent-a",
        parent_basis_json=b"{}",
        job_intent_locator=None,
    )
    node.error = stage_unknown
    if async_host:
        with pytest.raises((ChildGuardedStageWriteUnknown, BaseExceptionGroup)) as observed:
            asyncio.run(
                AsyncWorkflowExecutor(ctx, registry).execute(
                    workflow, ExperimentState(run_id="unknown-run")
                )
            )
        assert any(error is stage_unknown for error in _leaves(observed.value))
    else:
        with pytest.raises(ChildGuardedStageWriteUnknown) as observed:
            WorkflowExecutor(ctx, registry).execute(workflow, ExperimentState(run_id="unknown-run"))
        assert observed.value is stage_unknown
    assert node.calls == 1
