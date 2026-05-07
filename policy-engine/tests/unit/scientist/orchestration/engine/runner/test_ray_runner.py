from __future__ import annotations

import concurrent.futures
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.checkpoint import CASCheckpointHook, resolve_latest_checkpoint
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.runner import _activity_worker as activity_worker_module
from polisyos.scientist.orchestration.engine.runner import ray_runner as ray_runner_module
from polisyos.scientist.orchestration.engine.runner.ray_runner import RayWorkflowRunner
from polisyos.scientist.orchestration.engine.runner.serialization import deserialize_state, serialize_state
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_FAKE_REMOTE_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)


def _meta(raw: str, name: str) -> ComponentMetadata:
    return ComponentMetadata(
        component_id=ComponentId.parse(raw),
        kind=ComponentKind.SCIENTIST_NODE,
        abi_targets={"world_abi": "1.x"},
        display_name=name,
        description=f"{name} test node",
        tags=["test"],
        capabilities=Capability.SCIENTIST_NODE,
    )


class RayLeftNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_ray_left@1.0.0", "RayLeft"),
        state_writes=["params.left"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.params["left"] = 1
        return NodeOutcome(status="ok", state=new_state)


class RayRightNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_ray_right@1.0.0", "RayRight"),
        state_writes=["params.right"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.params["right"] = 2
        return NodeOutcome(status="ok", state=new_state)


class RayFinalizeNode:
    _spec = NodeSpec(
        metadata=_meta("scientist.node_ray_finalize@1.0.0", "RayFinalize"),
        state_reads=["params.left", "params.right"],
        state_writes=["params.final"],
    )

    @property
    def spec(self) -> NodeSpec:
        return self._spec

    def execute(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        new_state = state.model_copy(deep=True)
        new_state.params["final"] = int(new_state.params.get("left", 0)) + int(
            new_state.params.get("right", 0)
        )
        return NodeOutcome(status="ok", state=new_state)


def _workflow() -> WorkflowSpec:
    return WorkflowSpec(
        workflow_id="wf_ray_runner_checkpoint_merge",
        required_binds=["run_id"],
        error_policy="fail_fast",
        nodes=[
            NodeInvocation(
                alias="left",
                node_id=ComponentId.parse("scientist.node_ray_left@1.0.0"),
            ),
            NodeInvocation(
                alias="right",
                node_id=ComponentId.parse("scientist.node_ray_right@1.0.0"),
            ),
            NodeInvocation(
                alias="final",
                node_id=ComponentId.parse("scientist.node_ray_finalize@1.0.0"),
                depends_on=["left", "right"],
            ),
        ],
    )


def _context(store: FileSystemCAS, run_id: str) -> tuple[ExecutionContext, object]:
    bundle = build_default_registry_bundle(store)
    run = RunContext.start(store=store, registry_bundle=bundle.bundle_ref, run_id=run_id)
    ctx = ExecutionContext(store=store, run=run, logger=logging.getLogger("test.ray.runner"))
    return ctx, bundle.bundle_ref


class _FakeObjectRef:
    def __init__(self, future: concurrent.futures.Future[object]) -> None:
        self._future = future

    def future(self) -> concurrent.futures.Future[object]:
        return self._future


class _FakeTask:
    def __init__(self, fn):
        self._fn = fn

    def options(self, **kwargs):
        return self

    def remote(self, *args, **kwargs):
        return _FakeObjectRef(_FAKE_REMOTE_EXECUTOR.submit(self._fn, *args, **kwargs))


@pytest.mark.asyncio
async def test_ray_runner_executes_remote_checkpoint_merge_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ray_runner_module, "_HAS_RAY", True)
    monkeypatch.setattr(
        ray_runner_module,
        "ray",
        SimpleNamespace(
            is_initialized=lambda: True,
            init=lambda **kwargs: None,
            cluster_resources=lambda: {"CPU": 2},
        ),
        raising=False,
    )

    store = FileSystemCAS(tmp_path)
    run_id = "R_ray_remote_merge"
    workflow = _workflow()
    ctx, bundle_ref = _context(store, run_id)
    state = ExperimentState(
        run_id=run_id,
        inputs={"registry_bundle_ref": bundle_ref},
        params={"seed": 17},
    )
    hook = CASCheckpointHook(
        store=store,
        run_dir=tmp_path / "runs" / run_id,
        checkpoint_policy="strict",
    )
    runner = RayWorkflowRunner(address="ray://unused", namespace="test", max_parallelism=2)
    monkeypatch.setattr(runner, "_ensure_init", lambda: None)

    def _discover_nodes(registry: NodeRegistry) -> None:
        registry.register(RayLeftNode())
        registry.register(RayRightNode())
        registry.register(RayFinalizeNode())

    merge_calls: list[list[str]] = []

    def _execute_node_remote(**payload):
        worker_state = deserialize_state(payload["state_bytes"])
        updated_state = worker_state.model_copy(deep=True)
        alias = str(payload["alias"])
        if alias == "left":
            updated_state.params["left"] = 1
        elif alias == "right":
            updated_state.params["right"] = 2
        elif alias == "final":
            updated_state.params["final"] = int(updated_state.params.get("left", 0)) + int(
                updated_state.params.get("right", 0)
            )
        return serialize_state(updated_state)

    def _merge_tier_remote(payload: dict[str, object]) -> dict[str, object]:
        merge_calls.append(list(payload["tier_aliases"]))  # type: ignore[index]
        return activity_worker_module.run_merge_checkpoint_tier_in_worker_sync(payload)

    monkeypatch.setattr(
        "polisyos.scientist.orchestration.engine.registry.discover_nodes",
        _discover_nodes,
    )
    monkeypatch.setattr(
        ray_runner_module,
        "execute_node_task",
        _FakeTask(_execute_node_remote),
        raising=False,
    )
    monkeypatch.setattr(
        ray_runner_module,
        "merge_checkpoint_tier_task",
        _FakeTask(_merge_tier_remote),
        raising=False,
    )

    result = await runner.execute_workflow(
        workflow,
        state,
        ctx,
        NodeRegistry(),
        checkpoint_hook=hook,
    )

    assert result.report.status == "ok"
    assert result.state.params["left"] == 1
    assert result.state.params["right"] == 2
    assert result.state.params["final"] == 3
    assert merge_calls == [["left", "right"], ["final"]]

    resolved = resolve_latest_checkpoint(store, run_id)
    assert resolved is not None
    head, checkpoint_artifact = resolved
    assert head.sequence_number == 2
    assert checkpoint_artifact.metadata.completed_nodes == ["left", "right", "final"]
    assert checkpoint_artifact.state is not None
    assert checkpoint_artifact.state["params"]["final"] == 3


def test_ray_runner_inject_trace_carrier_records_degraded_path_on_runtime_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polisyos.core.observability import propagation

    degraded: list[dict[str, object]] = []

    monkeypatch.setattr(
        ray_runner_module,
        "emit_degraded_path",
        lambda **kwargs: degraded.append(kwargs) or {"reason": kwargs["reason"]},
    )

    def _boom(_carrier: dict[str, str]) -> None:
        raise RuntimeError("trace carrier failure")

    monkeypatch.setattr(propagation, "inject_headers", _boom)

    carrier = ray_runner_module._inject_trace_carrier()

    assert carrier == {}
    assert any(item["reason"] == "trace_carrier_injection_failed" for item in degraded)


@pytest.mark.asyncio
async def test_ray_runner_health_check_returns_unhealthy_on_probe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ray_runner_module, "_HAS_RAY", True)
    monkeypatch.setattr(
        ray_runner_module,
        "ray",
        SimpleNamespace(
            is_initialized=lambda: True,
            init=lambda **kwargs: None,
            cluster_resources=lambda: (_ for _ in ()).throw(RuntimeError("ray down")),
        ),
        raising=False,
    )

    runner = RayWorkflowRunner(address="ray://unused", namespace="test")
    monkeypatch.setattr(runner, "_ensure_init", lambda: None)

    health = await runner.health_check()

    assert health.backend == "ray"
    assert health.healthy is False
    assert "ray down" in health.message
