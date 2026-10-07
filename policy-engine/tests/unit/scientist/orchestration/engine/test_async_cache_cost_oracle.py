"""Measure real async cache costs without inventing a latency SLA.

The finite profiles retain individual monotonic samples, actual serialized CAS
bytes and empirical nearest-rank p95/p99. An injected cache-only I/O delay still
delegates to FileSystemCAS; neighbour progress and reopened native state/output
effects distinguish off-loop cache work from a marker-only hit declaration.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import os
import threading
import time
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, PutOptions
from polisyos.core.components import Capability, ComponentId, ComponentKind, ComponentMetadata
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run.context import RunContext
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.metrics import NoopEngineMetrics
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome, NodeSpec
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

_CACHE_KINDS = {"scientist.node_cache_entry", "scientist.node_outcome"}
_IO_DELAY_S = 0.012
_TIMER_PERIOD_S = 0.002
_WARM_REPETITIONS = 12


def _nearest_rank(values: list[int], percentile: float) -> int:
    """Report a finite empirical order statistic, never an inferred SLA."""
    assert values
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


class _ObservedMetrics(NoopEngineMetrics):
    def __init__(self) -> None:
        self.completed: list[dict[str, Any]] = []

    def record_node_completed(self, **kwargs: Any) -> None:
        self.completed.append(kwargs)


class _MeasuredCAS(FileSystemCAS):
    """Observe actual serialized bytes and worker ownership at the real store."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.recording = False
        self.samples: list[dict[str, Any]] = []
        self._sample_lock = threading.Lock()

    def _record(self, operation: str, kind: str, started_ns: int, data: bytes) -> None:
        with self._sample_lock:
            self.samples.append(
                {
                    "operation": operation,
                    "kind": kind,
                    "started_ns": started_ns,
                    "finished_ns": time.monotonic_ns(),
                    "thread_id": threading.get_ident(),
                    "serialized_bytes": len(data),
                    "sha256": hashlib.sha256(data).hexdigest(),
                }
            )

    def put_bytes(self, data: bytes, opts: PutOptions) -> ArtifactRef:
        measured = self.recording and opts.kind in _CACHE_KINDS
        started_ns = time.monotonic_ns()
        if measured:
            time.sleep(_IO_DELAY_S)
        ref = super().put_bytes(data, opts)
        if measured:
            self._record("put", opts.kind, started_ns, data)
        return ref

    def get_bytes(self, artifact_id: Any) -> bytes:
        kind = super().get_manifest(artifact_id).kind if self.recording else ""
        measured = self.recording and kind in _CACHE_KINDS
        started_ns = time.monotonic_ns()
        if measured:
            time.sleep(_IO_DELAY_S)
        data = super().get_bytes(artifact_id)
        if measured:
            self._record("get", kind, started_ns, data)
        return data


class _PhysicalNode:
    def __init__(self, provider_path: Path) -> None:
        self.provider_path = provider_path
        self.calls = 0
        self.spec = NodeSpec(
            metadata=ComponentMetadata(
                component_id=ComponentId.parse("scientist.cache_cost_oracle@1.0.0"),
                kind=ComponentKind.SCIENTIST_NODE,
                abi_targets={"world_abi": "1.x"},
                display_name="Physical cache cost oracle",
                description="Return an actual verified output and declared replay operations",
                capabilities=Capability.SCIENTIST_NODE,
            ),
            state_reads=["params.payload"],
            state_writes=["params.result", "params.expanded"],
        )

    def execute(self, _ctx: ExecutionContext, _state: ExperimentState) -> NodeOutcome:
        raise AssertionError("The actual async producer must be selected")

    async def execute_async(self, ctx: ExecutionContext, state: ExperimentState) -> NodeOutcome:
        self.calls += 1
        payload = state.params["payload"]
        result = {"digest": hashlib.sha256(payload.encode()).hexdigest(), "bytes": len(payload)}
        with self.provider_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(result, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        output = ctx.store.put_json(
            result, PutOptions(kind="scientist.cache_cost_effect", media_type="application/json")
        )
        state.params["result"] = result
        state.params["expanded"] = payload
        return NodeOutcome(status="ok", state=state, artifacts=[output])


@pytest.mark.parametrize("payload_bytes", [1024, 65536])
@pytest.mark.asyncio
async def test_real_async_cache_costs_and_neighbour_waits(
    tmp_path: Path, payload_bytes: int
) -> None:
    root = tmp_path / "cas"
    initial_store = FileSystemCAS(root)
    bundle_ref = build_default_registry_bundle(initial_store).bundle_ref
    provider_path = tmp_path / "physical-provider.jsonl"
    node = _PhysicalNode(provider_path)
    registry = NodeRegistry()
    registry.register(node)
    workflow = WorkflowSpec(
        workflow_id="cache_cost_profile",
        nodes=[NodeInvocation(alias="compute", node_id=node.spec.metadata.component_id)],
    )
    run_id = f"B52-cost-{payload_bytes}"
    run_dir = tmp_path / "run"
    payload = "x" * payload_bytes
    expected = {"digest": hashlib.sha256(payload.encode()).hexdigest(), "bytes": payload_bytes}
    measurements: list[dict[str, Any]] = []
    for ordinal in range(_WARM_REPETITIONS + 1):
        # Reopening both the real CAS and executor makes every warm consumer
        # resolve persisted trace/cache bytes rather than a retained object.
        store = _MeasuredCAS(root)
        run = RunContext.start(store, bundle_ref, run_id=run_id, run_dir=run_dir)
        metrics = _ObservedMetrics()
        ctx = ExecutionContext(
            store=store, run=run, logger=logging.getLogger("cache-cost-oracle"), metrics=metrics
        )
        current = ExperimentState(
            run_id=run_id, params={"payload": payload, "unrelated": f"current-{ordinal}"}
        )
        waits: list[dict[str, int]] = []
        done = asyncio.Event()

        async def neighbour(done_event: asyncio.Event, timer_samples: list[dict[str, int]]) -> None:
            while not done_event.is_set():
                scheduled_ns = time.monotonic_ns() + int(_TIMER_PERIOD_S * 1_000_000_000)
                await asyncio.sleep(_TIMER_PERIOD_S)
                resumed_ns = time.monotonic_ns()
                timer_samples.append(
                    {
                        "scheduled_ns": scheduled_ns,
                        "resumed_ns": resumed_ns,
                        "lateness_ns": resumed_ns - scheduled_ns,
                    }
                )

        loop_thread = threading.get_ident()
        neighbour_task = asyncio.create_task(neighbour(done, waits))
        await asyncio.sleep(0)
        started_ns = time.monotonic_ns()
        store.recording = True
        try:
            result = await AsyncWorkflowExecutor(ctx, registry).execute(workflow, current)
        finally:
            finished_ns = time.monotonic_ns()
            store.recording = False
            done.set()
            await neighbour_task
        cache_samples = store.samples
        record = {
            "ordinal": ordinal,
            "warm": ordinal > 0,
            "workflow_started_ns": started_ns,
            "workflow_finished_ns": finished_ns,
            "workflow_return_cost_ns": finished_ns - started_ns,
            "loop_thread_id": loop_thread,
            "neighbour_timer_samples": waits,
            "cache_io_samples": cache_samples,
            "serialized_cache_put_bytes": sum(
                row["serialized_bytes"] for row in cache_samples if row["operation"] == "put"
            ),
            "cache_read_bytes": sum(
                row["serialized_bytes"] for row in cache_samples if row["operation"] == "get"
            ),
            "native_node_completed_metrics": metrics.completed,
            "actual_provider_calls": node.calls,
        }
        measurements.append(record)
        # Retain all actual observations before any property assertion.
        (tmp_path / "individual-costs.json").write_text(
            json.dumps(measurements, indent=2) + "\n", encoding="utf-8"
        )
        assert result.report.status == "ok"
        assert node.calls == 1
        assert result.state.params["result"] == expected
        assert result.state.params["expanded"] == payload
        assert result.state.params["unrelated"] == f"current-{ordinal}"
        assert "result" not in current.params and "expanded" not in current.params
        assert len(metrics.completed) == 1
        assert metrics.completed[0]["cache_hit"] is (ordinal > 0)
        assert len(provider_path.read_text().splitlines()) == 1
        output = result.report.nodes[0].artifacts[0]
        assert store.verify(output).ok
        assert json.loads(store.get_bytes(output)) == expected
        assert store.get_manifest(output).kind == "scientist.cache_cost_effect"
        assert store.verify(result.run_ref).ok
        assert cache_samples and waits
        for sample in cache_samples:
            assert sample["thread_id"] != loop_thread
            assert any(
                sample["started_ns"] < tick["resumed_ns"] < sample["finished_ns"] for tick in waits
            )
        assert (
            record["serialized_cache_put_bytes"] == 0
            if ordinal
            else record["serialized_cache_put_bytes"] > payload_bytes
        )
        trace = [json.loads(line) for line in run.trace_path.read_text().splitlines()]
        stores = [row for row in trace if row.get("event") == "NODE_CACHE_STORE"]
        hits = [row for row in trace if row.get("event") == "NODE_CACHE_HIT"]
        assert len(stores) == 1 and len(hits) == ordinal
        cache_ref = ArtifactRef.model_validate(stores[0]["refs"]["outputs"][0])
        assert store.verify(cache_ref).ok
        cache_bytes = store.get_bytes(cache_ref)
        assert len(cache_bytes) == measurements[0]["serialized_cache_put_bytes"]
        assert store.get_manifest(cache_ref).kind == "scientist.node_cache_entry"
    lateness = [
        tick["lateness_ns"] for row in measurements for tick in row["neighbour_timer_samples"]
    ]
    warm_cost = [row["workflow_return_cost_ns"] for row in measurements if row["warm"]]
    summary = {
        "payload_bytes": payload_bytes,
        "cold_workflow_return_cost_ns": measurements[0]["workflow_return_cost_ns"],
        "warm_observations": len(warm_cost),
        "neighbour_observations": len(lateness),
        "neighbour_wait_p95_ns": _nearest_rank(lateness, 0.95),
        "neighbour_wait_p99_ns": _nearest_rank(lateness, 0.99),
        "warm_workflow_return_cost_p95_ns": _nearest_rank(warm_cost, 0.95),
        "warm_workflow_return_cost_p99_ns": _nearest_rank(warm_cost, 0.99),
        "serialized_cache_put_bytes": measurements[0]["serialized_cache_put_bytes"],
        "raw_individual_measurements": str(tmp_path / "individual-costs.json"),
        "qualification": "Finite 1KiB/64KiB workloads, injected12ms actual-cache-I/O delay; empirical nearest-rank statistics, no SLA or general speedup claim. Workflow hit return includes recovery/read/apply/state/report/finalize, not only disk read. CPU/GIL timing not isolated.",
    }
    (tmp_path / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("B52_REAL_CACHE_COST " + json.dumps(summary))
