"""Warm-parent numerical qualification of the native Darwin closed spawn route.

These cases do not qualify Linux fork after JAX initialization. They exercise
an already admitted canonical node, without extending the spawn allowlist.
"""

from __future__ import annotations

import asyncio
import json
import logging
import multiprocessing
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from polisyos.core.artifacts import ArtifactRef, FileSystemCAS, input_ref_from_artifact_ref
from polisyos.core.artifacts import ensure_ir_artifact_store as ir_store_for
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.registry import build_default_registry_bundle
from polisyos.core.run import RunContext, RunManifest, read_runtime_invocation_attempts
from polisyos.core.security.tenant_context import tenant_scope
from polisyos.ir.analytics.causal_graph import (
    CausalEdge,
    CausalGraphModel,
    GraphType,
    persist_causal_graph_model,
)
from polisyos.ir.analytics.context import ContextProfile
from polisyos.ir.analytics.literature import EvidenceParameter
from polisyos.ir.analytics.parameters import (
    ContextAdaptiveParameterBundleV11,
    ParameterApplicability,
    persist_context_adaptive_parameter_bundle_v1_1,
)
from polisyos.ir.analytics.transportability import TransportabilityStatus, TransportMode
from polisyos.scientist.nodes.builtins.causal.resolve_parameters import ResolveParametersNode
from polisyos.scientist.nodes.builtins.state_keys import (
    ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF,
    ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF,
)
from polisyos.scientist.orchestration.engine.async_executor import AsyncWorkflowExecutor
from polisyos.scientist.orchestration.engine.context import ExecutionContext
from polisyos.scientist.orchestration.engine.errors import NodeTimeoutError
from polisyos.scientist.orchestration.engine.executor import WorkflowExecutor
from polisyos.scientist.orchestration.engine.finalization import WorkflowStateFinalization
from polisyos.scientist.orchestration.engine.protocol import NodeOutcome
from polisyos.scientist.orchestration.engine.registry import NodeRegistry
from polisyos.scientist.orchestration.engine.retry import (
    RetryPolicy,
    _timeout_worker_start_method,
    execute_with_retry_async,
    execute_with_retry_sync,
)
from polisyos.scientist.orchestration.engine.state import ExperimentState
from polisyos.scientist.orchestration.engine.workflow_spec import NodeInvocation, WorkflowSpec

pytestmark = pytest.mark.skipif(sys.platform != "darwin", reason="native Darwin spawn profile")

_ALIAS = "warm_parameters"
_DRAWS = 32
_TENANT = "tenant-warm-numerical"
_CELL = "cell-warm-numerical"


@pytest.fixture(autouse=True)
def warm_numerical_tenant():
    """Use the same real scoped local profile admitted by existing spawn tests."""
    with tenant_scope(None, tenant_id=_TENANT, cell_id=_CELL):
        yield


def _warm_jax_and_expected_interval(seed: int) -> tuple[dict[str, Any], dict[str, float]]:
    """Initialize the actual CPU backend and independently calculate its oracle."""
    import jax
    import jax.numpy as jnp
    import numpy as np

    assert jax.default_backend() == "cpu"
    matrix = jnp.arange(64, dtype=jnp.float32).reshape((8, 8))
    warm_result = (matrix @ matrix).sum().block_until_ready()
    arithmetic = sum(
        sum((i * 8 + k) * (k * 8 + j) for k in range(8)) for i in range(8) for j in range(8)
    )
    assert float(warm_result) == arithmetic

    # This oracle uses the declared PRNG sequence and NumPy reductions, not the
    # ParameterTransfer producer or its interval helper. A stale/default seed,
    # NumPy fallback, missing computation or changed uncertainty fails it.
    _next_key, draw_key = jax.random.split(jax.random.PRNGKey(seed))
    samples = np.asarray(2.0 + 0.6 * jax.random.normal(draw_key, shape=(_DRAWS,)))
    expected = {
        "mean": float(np.mean(samples)),
        "std": float(np.std(samples)),
        "ci_low": float(np.quantile(samples, 0.025)),
        "ci_high": float(np.quantile(samples, 0.975)),
        "draws": float(_DRAWS),
    }
    profile = {
        "platform": sys.platform,
        "start_method": _timeout_worker_start_method(),
        "jax_version": jax.__version__,
        "jax_backend": jax.default_backend(),
        "jax_x64": jax.config.x64_enabled,
        "jax_devices": [str(device) for device in jax.devices()],
        "warm_parent_pid": os.getpid(),
        "completed_parent_matmul": float(warm_result),
        "requested_seed": seed,
        "requested_draws": _DRAWS,
        "numerical_scope": "Darwin closed spawn; Linux fork remains separately qualified",
    }
    assert profile["start_method"] == "spawn"
    return profile, expected


def _numerical_request(
    tmp_path: Path, mode: str, *, seed: int
) -> tuple[ExecutionContext, ExperimentState]:
    """Build real selected CAS inputs and an ordinary original Core run."""
    store = FileSystemCAS(tmp_path / "cas", tenant_id=_TENANT, cell_id=_CELL)
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    run_id = f"R_warm_numerical_{mode}"
    run = RunContext.start(
        store, registry.bundle_ref, run_id=run_id, tenant_id=_TENANT, cell_id=_CELL
    )
    context = ExecutionContext(store=store, run=run, logger=logging.getLogger(__name__))
    graph = CausalGraphModel(
        graph_type=GraphType.DAG,
        nodes=["X", "Y"],
        edges=[CausalEdge(src="X", dst="Y")],
    )
    graph_ref = persist_causal_graph_model(ir_store_for(store), graph, return_selected_profile=True)
    core_graph_ref = ArtifactRef.model_validate(graph_ref.model_dump(mode="json"))
    bundle = ContextAdaptiveParameterBundleV11(
        target_context=ContextProfile(context_id="control"),
        simulation_domain="fiscal",
        selected_cross_graph_profile_ref=None,
        parameters={"beta": EvidenceParameter(name="beta", value=2.0, std_error=0.2)},
        applicability={
            "beta": ParameterApplicability(
                parameter_id="beta",
                target_context_id="control",
                transport_status=TransportabilityStatus.IDENTIFIED,
                transport_mode=TransportMode.TRANSPORT_FORMULA,
                transport_confidence=0.6,
                context_distance=0.4,
                is_applicable=True,
                adjustment_required=True,
                uncertainty_multiplier=3.0,
            )
        },
    )
    bundle_ref = persist_context_adaptive_parameter_bundle_v1_1(
        ir_store_for(store),
        bundle,
        inputs=[input_ref_from_artifact_ref(core_graph_ref, role="causal_graph")],
    )
    state = ExperimentState(
        run_id=run_id,
        params={
            "target_context": bundle.target_context.model_dump(mode="json"),
            "required_parameters": ["beta"],
            "domain": "fiscal",
            "phase15_runtime_backend": "jax",
            "phase15_runtime_seed": seed,
            "phase15_runtime_draws": _DRAWS,
            "phase15_runtime_parameter_intervals": {"stale": {}},
        },
    )
    state.artifacts_index[ARTIFACT_RECONCILED_CAUSAL_GRAPH_REF] = core_graph_ref
    state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF] = (
        ArtifactRef.model_validate(bundle_ref.model_dump(mode="json"))
    )
    return context, state


def _interval_matches(state: ExperimentState, expected: dict[str, float]) -> None:
    assert state.params["phase15_runtime_backend_used"] == "jax"
    assert state.params["phase15_runtime_ready"] is True
    actual = state.params["phase15_runtime_parameter_intervals"]
    assert set(actual) == {"beta"}
    assert actual["beta"] == pytest.approx(expected, rel=1e-6, abs=1e-6)
    assert state.params["literature_priors"]["beta"]["__intercept__"]["mean"] == 2.0
    assert state.params["literature_priors"]["beta"]["__intercept__"]["std"] == pytest.approx(0.6)


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_warm_parent_canonical_numerical_spawn_has_bound_fresh_result(
    tmp_path: Path, record_property, mode: str
) -> None:
    """A genuinely warm parent delivers a meaningful, persisted child result."""
    seed = {"sync": 19, "async": 23}[mode]
    profile, expected = _warm_jax_and_expected_interval(seed)
    context, state = _numerical_request(tmp_path, mode, seed=seed)
    node = ResolveParametersNode()
    nodes = NodeRegistry()
    nodes.register(node)
    workflow = WorkflowSpec(
        workflow_id=f"warm_numerical_{mode}",
        nodes=[
            NodeInvocation(
                alias=_ALIAS,
                node_id=node.spec.metadata.component_id,
                timeout_s=60.0,
            )
        ],
    )
    previous_children = {child.pid for child in multiprocessing.active_children()}
    try:
        if mode == "sync":
            result = WorkflowExecutor(context, nodes).execute(workflow, state)
        else:
            result = asyncio.run(AsyncWorkflowExecutor(context, nodes).execute(workflow, state))
        assert result.report.status == "ok", result.report.model_dump(mode="json")
        assert len(result.report.nodes) == 1
        assert result.report.nodes[0].status == "ok"
        _interval_matches(result.state, expected)

        assert result.run_ref is not None
        assert result.run_ref.manifest_profile_sha256 is not None
        reopened = FileSystemCAS(tmp_path / "cas", tenant_id=_TENANT, cell_id=_CELL)
        assert reopened.verify(result.run_ref).ok
        manifest = RunManifest.model_validate(
            from_canonical_bytes(reopened.get_bytes(result.run_ref))
        )
        assert manifest.run_id == state.run_id
        assert (manifest.tenant_id, manifest.cell_id) == (_TENANT, _CELL)
        assert manifest.status == "ok"
        finalization_refs = [
            ref for ref in manifest.outputs if ref.kind == "scientist.workflow_state_finalization"
        ]
        assert len(finalization_refs) == 1
        assert reopened.verify(finalization_refs[0]).ok
        finalization = WorkflowStateFinalization.model_validate(
            from_canonical_bytes(reopened.get_bytes(finalization_refs[0]))
        )
        assert finalization.run_id == state.run_id
        assert finalization.final_state_ref.manifest_profile_sha256 is not None
        assert finalization.final_state_ref in manifest.outputs
        assert reopened.verify(finalization.final_state_ref).ok
        persisted = ExperimentState.model_validate(
            from_canonical_bytes(reopened.get_bytes(finalization.final_state_ref))
        )
        _interval_matches(persisted, expected)
        assert (
            persisted.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF]
            == (state.artifacts_index[ARTIFACT_CONTEXT_ADAPTIVE_PARAMETER_BUNDLE_REF])
        )
        assert context.run.trace_path is not None
        attempts = read_runtime_invocation_attempts(
            reopened, context.run.trace_path, run_id=state.run_id
        )
        assert len(attempts) == 1
        assert attempts[0].basis.node_alias == _ALIAS
        assert attempts[0].outcome is not None
        assert attempts[0].outcome.status == "ok"
        assert reopened.verify(attempts[0].basis.input_state_ref).ok
        trace = [
            json.loads(line)
            for line in context.run.trace_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        started = [row for row in trace if row["event"] == "WORKER_INVOCATION_STARTED"]
        completed = [row for row in trace if row["event"] == "WORKER_INVOCATION_COMPLETED"]
        assert len(started) == len(completed) == 1
        assert started[0]["worker_invocation_id"] == completed[0]["worker_invocation_id"]
        assert started[0]["worker_dispatch_sha256"] == completed[0]["worker_dispatch_sha256"]
        assert started[0]["run_id"] == completed[0]["run_id"] == state.run_id
        record_property("warm_numerical_profile", json.dumps(profile, sort_keys=True))
        record_property("expected_interval", json.dumps(expected, sort_keys=True))
    finally:
        if not context.run._closed and not context.run._suspended:
            context.run.suspend_for_resume()
    assert {child.pid for child in multiprocessing.active_children()} == previous_children


@pytest.mark.parametrize("mode", ["sync", "async"])
def test_warm_parent_refuses_same_id_foreign_node_before_physical_work(
    tmp_path: Path, mode: str
) -> None:
    """Numerical initialization does not permit fallback for a noncanonical node."""
    _warm_jax_and_expected_interval(19)
    context, state = _numerical_request(tmp_path, mode, seed=19)
    effect = tmp_path / "forbidden_effect"

    class ForeignNode:
        spec = ResolveParametersNode().spec

        def execute(self, _ctx, current_state):
            effect.write_text("unauthorized physical dispatch", encoding="utf-8")
            return NodeOutcome(status="ok", state=current_state)

    kwargs = {
        "retry_policy": RetryPolicy(max_retries=0),
        "timeout_s": 60.0,
        "alias": _ALIAS,
        "dispatch_params": {},
    }
    children = {child.pid for child in multiprocessing.active_children()}

    def invoke() -> None:
        if mode == "sync":
            execute_with_retry_sync(ForeignNode(), context, state, **kwargs)
        else:
            asyncio.run(execute_with_retry_async(ForeignNode(), context, state, **kwargs))

    try:
        with pytest.raises(NodeTimeoutError) as failure:
            invoke()
        assert failure.value.code == "node.timeout_worker_unsupported"
        assert failure.value.details["reason"] == "timeout_worker_canonical_node_instance_required"
        assert not effect.exists()
    finally:
        context.run.suspend_for_resume()
    assert {child.pid for child in multiprocessing.active_children()} == children
