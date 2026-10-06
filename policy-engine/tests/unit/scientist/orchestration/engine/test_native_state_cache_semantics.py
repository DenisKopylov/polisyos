"""Real reopened cache consumers distinguish input presence and journal effects."""

from __future__ import annotations

import json
import logging

import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec


class _PresenceNode:
    def __init__(self):
        self.calls = 0
        self.refs: list[ArtifactRef] = []
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.presence_consumer@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Presence consumer",
                description="Exact observed input presence and type",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.threshold"],
            state_writes=["params.observed"],
        )

    def execute(self, ctx, state):
        raise AssertionError("Actual async method required")

    async def execute_async(self, ctx, state):
        self.calls += 1
        observed = {
            "present": "threshold" in state.params,
            "type": type(state.params["threshold"]).__name__
            if "threshold" in state.params
            else None,
            "value": state.params.get("threshold"),
        }
        ref = ctx.store.put_json(
            observed, PutOptions(kind="scientist.presence_effect", media_type="application/json")
        )
        self.refs.append(ref)
        state.params["observed"] = observed
        return NodeOutcome(status="ok", state=state, artifacts=[ref])


@pytest.mark.asyncio
async def test_five_distinct_presence_inputs_reopen_and_replay_only_their_native_result(tmp_path):
    root = tmp_path / "cas"
    store = FileSystemCAS(root)
    bundle_ref = build_default_registry_bundle(store).bundle_ref
    node = _PresenceNode()
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="native_presence",
        nodes=[NodeInvocation(alias="consume", node_id=node.spec.metadata.component_id)],
    )
    inputs = [{}, {"threshold": None}, {"threshold": 0}, {"threshold": False}, {"threshold": []}]
    for ordinal, params in enumerate(inputs, start=1):
        expected = {
            "present": "threshold" in params,
            "type": type(params["threshold"]).__name__ if "threshold" in params else None,
            "value": params.get("threshold"),
        }
        for warm in (False, True):
            reopened = FileSystemCAS(root)
            run = RunContext.start(reopened, bundle_ref, run_id="R_presence")
            ctx = ExecutionContext(
                store=reopened, run=run, logger=logging.getLogger("presence-consumer")
            )
            state = ExperimentState(
                run_id="R_presence",
                params={**params, "unrelated": "warm-current" if warm else "cold-original"},
            )
            result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, state)
            assert result.report.status == "ok"
            assert result.state.params["observed"] == expected
            assert result.state.params["unrelated"] == state.params["unrelated"]
            assert "observed" not in state.params
            assert node.calls == ordinal
            effect = result.report.nodes[0].artifacts[0]
            assert reopened.verify(effect).ok
            assert json.loads(reopened.get_bytes(effect)) == expected
            assert reopened.get_manifest(effect).kind == "scientist.presence_effect"
            assert reopened.verify(result.run_ref).ok
            records = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
            hits = [record for record in records if record.get("event") == "NODE_CACHE_HIT"]
            assert len(hits) == ordinal if warm else len(hits) == ordinal - 1
            stores = [record for record in records if record.get("event") == "NODE_CACHE_STORE"]
            assert len(stores) == ordinal
            refs = [ArtifactRef.model_validate(record["refs"]["outputs"][0]) for record in stores]
            assert len({str(ref.artifact_id) for ref in refs}) == ordinal
            assert all(reopened.verify(ref).ok for ref in refs)
    assert node.calls == 5
    assert len({str(ref.artifact_id) for ref in node.refs}) == 5
