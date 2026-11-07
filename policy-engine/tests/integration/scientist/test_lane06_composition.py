"""Native composition controls for LANE-06's shared owner/consumer boundaries.

The other I06 bindings reuse their existing native test owners. These controls
fill the cache-read budget boundary without replacing its real CAS, ledger,
Core lifecycle or persisted finalization with an in-memory test double.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from decimal import Decimal
from pathlib import Path
from typing import Literal

import pytest
from _helpers.run_lifecycle import (
    assert_one_resumed_terminal_lifecycle,
    interrupt_before_finalize_async,
    resume_same_run,
)

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.core.run.manifest import RunManifest
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.budget import BudgetLimit, BudgetState
from polisyos.scientist.orchestration.engine.budget_ledger import FileBudgetLedger
from polisyos.scientist.orchestration.engine.budget_middleware import BudgetMiddleware
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.executor import WorkflowReport
from polisyos.scientist.orchestration.engine.finalization import (
    FINALIZATION_KIND,
    WorkflowStateFinalization,
)
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

pytestmark = pytest.mark.integration

_NODE_ID = ComponentId.parse("scientist.i06_native_cached_effect@1.0.0")
_COST = Decimal("2")


def _owned_context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, ArtifactRef]:
    """Create the real Core owner without importing unrelated domain fixtures."""
    bundle = build_default_registry_bundle(store, return_selected_profile=True)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    return (
        ExecutionContext(store=store, run=run, logger=logging.getLogger("i06.native")),
        bundle.bundle_ref,
    )


class _OnceEffectNode:
    """Produce a selected value and charge one real, exclusively created effect."""

    spec = NodeSpec(
        metadata=ComponentMetadata(
            component_id=_NODE_ID,
            kind=ComponentKind.SCIENTIST_NODE,
            abi_targets={"world_abi": "1.x"},
            display_name="I06 native cache effect",
            description="Controlled local producer for the cache-read budget boundary",
            tags=["test"],
            capabilities=Capability.SCIENTIST_NODE,
        ),
        state_reads=["params.seed"],
        state_writes=["params.value", "artifacts_index.value"],
        produces=[],
    )

    def __init__(self, effect_path: Path, budget: BudgetMiddleware) -> None:
        self.effect_path = effect_path
        self.budget = budget
        self.calls = 0

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        payload = f"{state.run_id}/physical-compute/{state.params['seed']}".encode()
        # A second physical producer invocation cannot look like a cache hit.
        with self.effect_path.open("xb") as stream:
            stream.write(payload)
        self.budget.settle_spend_safe(
            event_id=f"{state.run_id}/physical-compute",
            key="run",
            amount=_COST,
            provider="i06-local-compute",
            payload_digest=hashlib.sha256(payload).hexdigest(),
        )
        value_ref = ctx.store.put_json(
            {"seed": state.params["seed"], "value": 4},
            PutOptions(kind="scientist.i06.value", media_type="application/json"),
            return_selected_profile=True,
        )
        state.params["value"] = 4
        state.artifacts_index["value"] = value_ref
        return NodeOutcome(status="ok", state=state, artifacts=[value_ref])


def _selected_final_report(
    store: FileSystemCAS,
    run_ref: ArtifactRef,
    finalization_ref: ArtifactRef,
) -> tuple[RunManifest, ExperimentState, WorkflowReport]:
    """Read the protected terminal transition through a newly opened CAS.

    A resumed owner's output history can contain an earlier unfinished workflow
    transition. The Core terminal fact supplies the selected ref; first-by-kind
    selection from that retained history would read the wrong final state.
    """
    assert run_ref.manifest_profile_sha256 is not None
    assert store.verify(run_ref).ok
    manifest = RunManifest.model_validate(from_canonical_bytes(store.get_bytes(run_ref)))
    assert finalization_ref.kind == FINALIZATION_KIND
    assert manifest.outputs.count(finalization_ref) == 1
    finalization = WorkflowStateFinalization.model_validate(
        from_canonical_bytes(store.get_bytes(finalization_ref))
    )
    report_ref = next(
        binding.artifact_ref
        for binding in finalization.output_bindings
        if binding.state_path == "reports_index.workflow_report"
    )
    assert report_ref in manifest.outputs
    state = ExperimentState.model_validate(
        from_canonical_bytes(store.get_bytes(finalization.final_state_ref))
    )
    report = WorkflowReport.model_validate(from_canonical_bytes(store.get_bytes(report_ref)))
    assert state.reports_index["workflow_report"] == report_ref
    assert all(
        ref.manifest_profile_sha256 is not None and store.verify(ref).ok
        for ref in (finalization_ref, report_ref, finalization.final_state_ref)
    )
    return manifest, state, report


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["read_allowed", "read_denied", "cache_miss"])
async def test_i06_cache_read_budget_reaches_actual_owner_and_fresh_finalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case: Literal["read_allowed", "read_denied", "cache_miss"],
) -> None:
    """I06-A-B03: permission to read never grants a new physical computation.

    Only the current read quota or requested seed changes in the negative cases.
    The local cost is deliberately declared, not a production price or external
    provider authority. The CAS observers delegate all real I/O unchanged.
    """
    run_id = f"i06-cache-budget-{case}"
    store = FileSystemCAS(tmp_path / "cas")
    ledger_path = tmp_path / "budget.json"
    limits = BudgetState(
        limits={
            "run": BudgetLimit(key="run", max_usd=_COST),
            "read": BudgetLimit(key="read", max_usd=Decimal("1")),
        }
    )
    budget = BudgetMiddleware(limits, ledger=FileBudgetLedger(ledger_path))
    node = _OnceEffectNode(tmp_path / "effect", budget)
    registry = NodeRegistry()
    registry.register(node)
    ctx, registry_ref = _owned_context(store, run_id)
    workflow = WorkflowSpec(
        workflow_id="i06_native_read_budget",
        nodes=[NodeInvocation(alias="cached", node_id=_NODE_ID)],
    )
    cold_state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": registry_ref},
        params={"seed": 7, "value": 4, "keep": "old"},
    )
    cold_events = await interrupt_before_finalize_async(
        ctx.run,
        lambda: AsyncWorkflowExecutor(ctx, registry).execute(workflow, cold_state),
    )
    assert node.calls == 1
    assert sum(event.get("event") == "NODE_CACHE_STORE" for event in cold_events) == 1
    ledger = FileBudgetLedger(ledger_path)
    assert ledger.snapshot().state.remaining("run") == Decimal("0")
    if case == "read_denied":
        ledger.settle_spend(
            event_id=f"{run_id}/prior-read-quota",
            key="read",
            amount=Decimal("1"),
            payload_digest=hashlib.sha256(b"prior-read-quota").hexdigest(),
        )
    before = ledger.snapshot()
    ledger_bytes = ledger_path.read_bytes()
    effect_bytes = node.effect_path.read_bytes()
    cache_ids = {
        str(artifact_id)
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "scientist.node_cache_entry"
    }
    assert len(cache_ids) == 1
    original_output = next(
        artifact_id
        for artifact_id in store.iter_artifact_ids()
        if store.get_manifest(artifact_id).kind == "scientist.i06.value"
    )

    fresh = FileSystemCAS(store.root)
    resumed_run = resume_same_run(fresh, ctx.run)
    resumed_ctx = ExecutionContext(
        store=fresh,
        run=resumed_run,
        logger=logging.getLogger("i06.native.cache.read"),
    )
    reads: list[tuple[str, str]] = []
    for method_name in ("get_bytes", "get_manifest", "verify"):
        original = getattr(fresh, method_name)

        def observe(ref, *args, _name=method_name, _original=original, **kwargs):
            artifact_id = str(getattr(ref, "artifact_id", ref))
            if artifact_id in cache_ids:
                reads.append((_name, artifact_id))
            return _original(ref, *args, **kwargs)

        monkeypatch.setattr(fresh, method_name, observe)
    warm_budget = BudgetMiddleware(limits, ledger=FileBudgetLedger(ledger_path))
    warm_state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": registry_ref},
        params={"seed": 8 if case == "cache_miss" else 7, "value": 99, "keep": "current"},
    )
    result = await AsyncWorkflowExecutor(
        resumed_ctx,
        registry,
        budget_middleware=warm_budget,
    ).execute(workflow, warm_state)
    cache_reads = tuple(reads)
    assert node.calls == 1
    assert node.effect_path.read_bytes() == effect_bytes
    assert ledger_path.read_bytes() == ledger_bytes
    assert FileBudgetLedger(ledger_path).snapshot() == before
    assert warm_state.params["value"] == 99
    assert result.run_ref is not None
    final_cas = FileSystemCAS(store.root)
    terminal_finalization_ref = resumed_run.read_runtime_workflow_finalization_ref()
    manifest, final_state, report = _selected_final_report(
        final_cas, result.run_ref, terminal_finalization_ref
    )
    assert final_state.params["keep"] == "current"
    events = assert_one_resumed_terminal_lifecycle(resumed_run)
    if case == "read_allowed":
        assert result.report.status == manifest.status == report.status == "ok"
        assert final_state.params["value"] == 4
        output_ref = final_state.artifacts_index["value"]
        assert output_ref.manifest_profile_sha256 is not None
        assert str(output_ref.artifact_id) == str(original_output)
        assert output_ref in manifest.outputs
        assert final_cas.get_bytes(output_ref) == b'{"seed":7,"value":4}'
        assert cache_reads
        assert sum(event.get("event") == "NODE_CACHE_HIT" for event in events) == 1
    else:
        assert result.report.status == manifest.status == report.status == "fail"
        assert final_state.params["value"] == 99
        assert "value" not in final_state.artifacts_index
        assert report.nodes[0].error is not None
        assert report.nodes[0].error.code == "node.budget_exhausted"
        assert report.nodes[0].error.details["budget_key"] == (
            "read" if case == "read_denied" else "run"
        )
        assert sum(event.get("event") == "NODE_CACHE_HIT" for event in events) == 0
        assert not report.nodes[0].artifacts
        if case == "read_denied":
            assert cache_reads == ()
    # Preserved bytes are useful but not automatically selected by a failed run.
    assert final_cas.verify(original_output).ok


class _OrderedNode:
    """Expose real producer ordering while the engine owns all publication."""

    def __init__(
        self,
        alias: str,
        *,
        target: str,
        b_started: asyncio.Event,
        b_release: asyncio.Event,
        b_finished: asyncio.Event,
        c_started: asyncio.Event,
    ) -> None:
        self.alias = alias
        self.target = target
        self.b_started = b_started
        self.b_release = b_release
        self.b_finished = b_finished
        self.c_started = c_started
        self.calls = 0
        self.c_observed: object = None
        self.c_observed_b_finished = False
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse(f"scientist.i06_order_{alias}@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name=f"I06 ordered producer {alias}",
                description="Controlled local producer for native dependency admission",
                tags=["test"],
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.items.0.value"] if alias == "c" else ["params.seed"],
            state_writes=[
                "params.result" if alias == "c" else f"params.items.{target}.value",
                f"artifacts_index.{alias}",
            ],
            produces=[],
        )

    def execute(self, _ctx: ExecutionContext, _state: ExperimentState) -> NodeOutcome:
        raise AssertionError("native readiness producer must use its real execute_async route")

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        if self.alias == "b":
            self.b_started.set()
            await self.b_release.wait()
            self.b_finished.set()
        if self.alias == "c":
            self.c_observed = state.params["items"][0]["value"]
            self.c_observed_b_finished = self.b_finished.is_set()
            self.c_started.set()
            state.params["result"] = self.c_observed
        else:
            state.params["items"][int(self.target)]["value"] = f"from-{self.alias}"
        output_ref = ctx.store.put_json(
            {"alias": self.alias, "observed": self.c_observed},
            PutOptions(kind="scientist.i06.order", media_type="application/json"),
            return_selected_profile=True,
        )
        state.artifacts_index[self.alias] = output_ref
        return NodeOutcome(status="ok", state=state, artifacts=[output_ref])


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["independent", "declared_join", "list_alias"])
async def test_i06_native_target_admission_reaches_fresh_selected_finalization(
    tmp_path: Path,
    case: Literal["independent", "declared_join", "list_alias"],
) -> None:
    """I06-A-B04: changing the join or actual target changes real producer order."""
    run_id = f"i06-native-target-{case}"
    store = FileSystemCAS(tmp_path / "cas")
    ctx, registry_ref = _owned_context(store, run_id)
    b_started, b_release, b_finished, c_started = (asyncio.Event() for _ in range(4))
    nodes = {
        alias: _OrderedNode(
            alias,
            target=("+0" if case == "list_alias" else "1") if alias == "b" else "0",
            b_started=b_started,
            b_release=b_release,
            b_finished=b_finished,
            c_started=c_started,
        )
        for alias in ("a", "b", "c")
    }
    registry = NodeRegistry()
    for node in nodes.values():
        registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="i06_native_target_admission",
        error_policy="continue",
        nodes=[
            NodeInvocation(alias="a", node_id=nodes["a"].spec.metadata.component_id),
            NodeInvocation(alias="b", node_id=nodes["b"].spec.metadata.component_id),
            NodeInvocation(
                alias="c",
                node_id=nodes["c"].spec.metadata.component_id,
                depends_on=["a", "b"] if case == "declared_join" else ["a"],
            ),
        ],
    )
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": registry_ref},
        params={"seed": 7, "items": [{"value": "initial"}, {"value": "untouched"}]},
    )
    execution = asyncio.create_task(
        AsyncWorkflowExecutor(ctx, registry, max_parallelism=2).execute(workflow, state)
    )
    early = False
    try:
        await asyncio.wait_for(b_started.wait(), timeout=5)
        try:
            await asyncio.wait_for(c_started.wait(), timeout=2)
            early = True
        except TimeoutError:
            pass
    finally:
        b_release.set()
        result = await execution

    assert nodes["a"].calls == nodes["b"].calls == 1
    assert result.run_ref is not None
    fresh = FileSystemCAS(store.root)
    manifest, final_state, report = _selected_final_report(
        fresh, result.run_ref, ctx.run.read_runtime_workflow_finalization_ref()
    )
    assert [record.alias for record in report.nodes] == ["a", "b", "c"]
    assert state.params["items"] == [{"value": "initial"}, {"value": "untouched"}]
    if case == "list_alias":
        assert not early
        assert nodes["c"].calls == 0
        assert [record.status for record in report.nodes] == ["fail", "fail", "skip"]
        assert all(
            record.error is not None and record.error.code == "node.parallel_merge_conflict"
            for record in report.nodes[:2]
        )
        assert final_state.params["items"] == state.params["items"]
        assert not any(ref.kind == "scientist.i06.order" for ref in manifest.outputs)
        # Both producers ran: their persisted bytes survive, but the conflict
        # prevents either uncommitted result from becoming a selected output.
        readable = [
            artifact_id
            for artifact_id in fresh.iter_artifact_ids()
            if fresh.get_manifest(artifact_id).kind == "scientist.i06.order"
        ]
        assert len(readable) == 2
        assert all(fresh.verify(artifact_id).ok for artifact_id in readable)
    else:
        assert early is (case == "independent")
        assert nodes["c"].calls == 1
        assert nodes["c"].c_observed_b_finished is (case == "declared_join")
        assert nodes["c"].c_observed == "from-a"
        assert result.report.status == manifest.status == report.status == "ok"
        assert final_state.params["items"] == [{"value": "from-a"}, {"value": "from-b"}]
        assert final_state.params["result"] == "from-a"
        for alias in ("a", "b", "c"):
            ref = final_state.artifacts_index[alias]
            assert ref.manifest_profile_sha256 is not None
            assert ref in manifest.outputs
            assert fresh.verify(ref).ok
