from __future__ import annotations

import jax
import jax.numpy as jnp
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
)
from polisyos.foundry.calibration.pure_executor import (
    PreparedNode,
    StaticBundle,
    apply_nodes,
    compile_program,
    run_pure_scan,
)
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.numeric import is_jax_tracer
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _dummy_artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "1" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _build_graph_and_plan(
    nodes: list[ProgramNode],
    *,
    edges: list[ProgramEdge] | None = None,
    max_steps: int | None = None,
) -> tuple[ProgramGraph, ExecPlan]:
    program_graph = ProgramGraph(
        ir_ref=_dummy_artifact_ref(),
        nodes=nodes,
        edges=list(edges or []),
        entrypoints=[],
    )
    exec_plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id="sha256:" + "2" * 64),
        order=[node.node_id for node in nodes],
        max_steps=max_steps,
    )
    return program_graph, exec_plan


def test_compile_program_uses_full_horizon_when_schedule_missing(monkeypatch) -> None:
    class _NoOpMechanism:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda *args, **kwargs: _NoOpMechanism(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                outputs=[],
            )
        ],
        max_steps=4,
    )

    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {"params": {}},
    )

    assert bundle.nodes[0].start == 0
    assert bundle.nodes[0].end == 3


def test_compile_program_requires_horizon_for_missing_schedule(monkeypatch) -> None:
    class _NoOpMechanism:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda *args, **kwargs: _NoOpMechanism(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                outputs=[],
            )
        ]
    )

    with pytest.raises(ValueError, match="exec_plan.max_steps > 0"):
        compile_program(
            graph,
            plan,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            base_state=GlobalState.empty(n_agents=2, n_firms=1),
            parameter_loader=lambda _: {"params": {}},
        )


def test_apply_nodes_flushes_visible_state_on_dependency_boundary(monkeypatch) -> None:
    class _IncomeWriter:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            delta = jnp.full_like(state.agents.income, 5.0)
            return {"agents.income": [{"delta": delta}]}, key

    class _IncomeReader:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {"agents.reported_income": [{"value": jnp.asarray(state.agents.income)}]}, key

    def _factory(mechanism_type, params, **kwargs):
        del params, kwargs
        if mechanism_type == "writer":
            return _IncomeWriter()
        if mechanism_type == "reader":
            return _IncomeReader()
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        _factory,
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="reader",
                node_kind="mechanism",
                mechanism_type="reader",
                inputs=["agents.income"],
                outputs=["agents.reported_income"],
            ),
        ],
        edges=[ProgramEdge(src="writer", dst="reader", relation="depends_on")],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 0, "duration_steps": 1},
        },
    )

    next_state, _ = apply_nodes(
        GlobalState.empty(n_agents=2, n_firms=1),
        jax.random.PRNGKey(0),
        bundle=bundle,
        t=jnp.array(0, dtype=jnp.int32),
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([5.0, 5.0], dtype=jnp.float32))
    assert jnp.allclose(
        next_state.agents.reported_income,
        jnp.array([5.0, 5.0], dtype=jnp.float32),
    )


def test_apply_nodes_preserves_batched_merge_for_independent_writers(monkeypatch) -> None:
    class _DeltaWriter:
        def __init__(self, offset: float) -> None:
            self._offset = offset

        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            delta = jnp.asarray(state.agents.income) + self._offset
            return {"agents.income": [{"delta": delta}]}, key

    def _factory(mechanism_type, params, **kwargs):
        del params, kwargs
        if mechanism_type == "left":
            return _DeltaWriter(1.0)
        if mechanism_type == "right":
            return _DeltaWriter(2.0)
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        _factory,
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="left",
                node_kind="mechanism",
                mechanism_type="left",
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="right",
                node_kind="mechanism",
                mechanism_type="right",
                outputs=["agents.income"],
            ),
        ],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 0, "duration_steps": 1},
        },
    )

    next_state, _ = apply_nodes(
        GlobalState.empty(n_agents=2, n_firms=1),
        jax.random.PRNGKey(0),
        bundle=bundle,
        t=jnp.array(0, dtype=jnp.int32),
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([3.0, 3.0], dtype=jnp.float32))


def test_apply_nodes_skips_inactive_emitter_and_preserves_active_gradient(monkeypatch) -> None:
    class _ScheduledLog:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            self.calls.append("trace" if is_jax_tracer(state.agents.income) else "runtime")
            delta = jnp.log(state.agents.income)
            return {"agents.income": [{"delta": delta}]}, jax.random.fold_in(key, 1)

    mechanism = _ScheduledLog()

    def _factory(mechanism_type, params, **kwargs):
        del params, kwargs
        if mechanism_type == "scheduled_log":
            return mechanism
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        _factory,
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="scheduled-log",
                node_kind="mechanism",
                mechanism_type="scheduled_log",
                outputs=["agents.income"],
            )
        ],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 1, "duration_steps": 1},
        },
    )
    key = jax.random.PRNGKey(7)
    inactive = GlobalState.empty(n_agents=2, n_firms=1)

    inactive_state, inactive_key = apply_nodes(
        inactive,
        key,
        bundle=bundle,
        t=jnp.array(0, dtype=jnp.int32),
    )

    # The eager inactive path never calls the emitter, so log(0) cannot
    # contaminate the state or its carried PRNG key.
    assert mechanism.calls == []
    assert jnp.allclose(inactive_state.agents.income, inactive.agents.income)
    assert jnp.array_equal(inactive_key, key)

    def inactive_objective(income):
        local_state = inactive.replace(agents=inactive.agents.replace(income=income))
        result, _ = apply_nodes(
            local_state,
            key,
            bundle=bundle,
            t=jnp.array(0, dtype=jnp.int32),
        )
        return jnp.sum(result.agents.income)

    inactive_gradient = jax.grad(inactive_objective)(jnp.zeros(2, dtype=jnp.float32))
    assert jnp.all(jnp.isfinite(inactive_gradient))
    # The inactive path is the identity map for the incoming state.  Its
    # gradient is therefore one, while the deferred log emitter contributes
    # no NaN/Inf derivative.
    assert jnp.allclose(inactive_gradient, jnp.ones(2, dtype=jnp.float32))

    active = inactive.replace(
        agents=inactive.agents.replace(income=jnp.full((2,), 2.0, dtype=jnp.float32))
    )
    active_state, active_key = apply_nodes(
        active,
        key,
        bundle=bundle,
        t=jnp.array(1, dtype=jnp.int32),
    )
    assert mechanism.calls == ["runtime"]
    assert jnp.allclose(
        active_state.agents.income,
        jnp.full((2,), 2.0 + jnp.log(2.0), dtype=jnp.float32),
    )
    assert not jnp.array_equal(active_key, key)

    def active_objective(income):
        local_state = active.replace(agents=active.agents.replace(income=income))
        result, _ = apply_nodes(
            local_state,
            key,
            bundle=bundle,
            t=jnp.array(1, dtype=jnp.int32),
        )
        return jnp.sum(result.agents.income)

    active_gradient = jax.grad(active_objective)(jnp.full((2,), 2.0, dtype=jnp.float32))
    assert jnp.all(jnp.isfinite(active_gradient))
    assert jnp.allclose(active_gradient, jnp.full((2,), 1.5, dtype=jnp.float32))
    assert mechanism.calls[0] == "runtime"
    assert all(call == "trace" for call in mechanism.calls[1:])

    # A dynamic schedule is traced through ``lax.cond``.  The inactive
    # runtime branch remains neutral even though the active branch is traced.
    @jax.jit
    def run_dynamic(t):
        return apply_nodes(inactive, key, bundle=bundle, t=t)[0]

    dynamic_inactive = run_dynamic(jnp.array(0, dtype=jnp.int32))
    assert jnp.all(jnp.isfinite(dynamic_inactive.agents.income))
    assert jnp.allclose(dynamic_inactive.agents.income, inactive.agents.income)
    assert mechanism.calls[0] == "runtime"
    assert all(call == "trace" for call in mechanism.calls[1:])


def test_apply_nodes_keeps_active_refusal_on_invalid_input(monkeypatch) -> None:
    class _RefusingMechanism:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            if not is_jax_tracer(state.agents.income) and bool(jnp.any(state.agents.income <= 0)):
                raise ValueError("income must be positive for active log mechanism")
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda mechanism_type, params, **kwargs: _RefusingMechanism(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="refusing-log",
                node_kind="mechanism",
                mechanism_type="refusing_log",
                outputs=["agents.income"],
            )
        ],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 1, "duration_steps": 1},
        },
    )
    with pytest.raises(ValueError, match="income must be positive"):
        apply_nodes(
            GlobalState.empty(n_agents=2, n_firms=1),
            jax.random.PRNGKey(0),
            bundle=bundle,
            t=jnp.array(1, dtype=jnp.int32),
        )


def test_apply_nodes_vmap_preserves_neutral_patch_structure(monkeypatch) -> None:
    class _ScheduledLog:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda mechanism_type, params, **kwargs: _ScheduledLog(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="scheduled-log",
                node_kind="mechanism",
                mechanism_type="scheduled_log",
                outputs=["agents.income"],
            )
        ],
        max_steps=2,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 1, "duration_steps": 1},
        },
    )
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    key = jax.random.PRNGKey(11)

    def run_one(income, t):
        state = base_state.replace(agents=base_state.agents.replace(income=income))
        return apply_nodes(state, key, bundle=bundle, t=t)[0].agents.income

    # eval_shape traces both conditional branches and therefore pins their
    # patch-map structure before the vectorized execution is admitted.
    output_shape = jax.eval_shape(
        run_one,
        jax.ShapeDtypeStruct((2,), jnp.float32),
        jax.ShapeDtypeStruct((), jnp.int32),
    )
    assert output_shape.shape == (2,)

    # Vectorize over independent state rows with one scalar schedule per job;
    # mixed per-row schedules would turn the scalar merge masks into a
    # different batched contract and are outside this native witness.
    def run_inactive(income):
        return run_one(income, jnp.array(0, dtype=jnp.int32))

    def run_active(income):
        return run_one(income, jnp.array(1, dtype=jnp.int32))

    inactive_result = jax.vmap(run_inactive)(jnp.zeros((2, 2), dtype=jnp.float32))
    assert inactive_result.shape == (2, 2)
    assert jnp.all(jnp.isfinite(inactive_result))
    assert jnp.allclose(inactive_result, jnp.zeros((2, 2), dtype=jnp.float32))

    active_result = jax.vmap(run_active)(jnp.full((2, 2), 2.0, dtype=jnp.float32))
    assert active_result.shape == (2, 2)
    assert jnp.all(jnp.isfinite(active_result))
    assert jnp.allclose(
        active_result,
        jnp.full((2, 2), 2.0 + jnp.log(2.0), dtype=jnp.float32),
    )


def test_run_pure_scan_preserves_inactive_gradient_path(monkeypatch) -> None:
    class _ScheduledLog:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, key

    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor.create_mechanism_from_spec",
        lambda mechanism_type, params, **kwargs: _ScheduledLog(),
    )
    graph, plan = _build_graph_and_plan(
        [
            ProgramNode(
                node_id="scheduled-log",
                node_kind="mechanism",
                mechanism_type="scheduled_log",
                outputs=["agents.income"],
            )
        ],
        max_steps=3,
    )
    bundle = compile_program(
        graph,
        plan,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        base_state=GlobalState.empty(n_agents=2, n_firms=1),
        parameter_loader=lambda _: {
            "params": {},
            "schedule": {"start_step": 2, "duration_steps": 1},
        },
    )
    key = jax.random.PRNGKey(13)
    initial = GlobalState.empty(n_agents=2, n_firms=1)
    initial = initial.replace(
        agents=initial.agents.replace(income=jnp.full((2,), 2.0, dtype=jnp.float32))
    )

    final_state, _ = run_pure_scan(
        initial,
        steps=3,
        root_key=key,
        bundle=bundle,
    )
    assert jnp.allclose(
        final_state.agents.income,
        jnp.full((2,), 2.0 + jnp.log(2.0), dtype=jnp.float32),
    )

    def scan_objective(income):
        state = initial.replace(agents=initial.agents.replace(income=income))
        final, _ = run_pure_scan(
            state,
            steps=3,
            root_key=key,
            bundle=bundle,
        )
        return jnp.sum(final.agents.income)

    gradient = jax.grad(scan_objective)(jnp.full((2,), 2.0, dtype=jnp.float32))
    assert jnp.all(jnp.isfinite(gradient))
    assert jnp.allclose(gradient, jnp.full((2,), 1.5, dtype=jnp.float32))


def _instrumented_log_step():
    observed = []
    traced = []

    class _ScheduledLog:
        def emit_patches(self, state, key, *, target_mask=None):
            del target_mask
            traced.append(True)
            # Unlike a Python call counter, this callback observes numerical
            # execution after JIT/vmap/AD, rather than branch tracing.
            jax.debug.callback(lambda income: observed.append(income.tolist()), state.agents.income)
            return {"agents.income": [{"delta": jnp.log(state.agents.income)}]}, jax.random.fold_in(
                key, 1
            )

    bundle = StaticBundle(
        nodes=[
            PreparedNode(
                node_id="scheduled-log",
                mechanism_type="scheduled_log",
                rank=0,
                start=1,
                end=1,
                mechanism=_ScheduledLog(),
                outputs=["agents.income"],
            )
        ],
        incoming_dependencies={},
        slot_registry=DEFAULT_SLOT_REGISTRY,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        selector_field_registry=None,
        trainables=[],
    )
    base = GlobalState.empty(n_agents=2, n_firms=1)

    def run_one(income, t, key):
        state = base.replace(agents=base.agents.replace(income=income))
        result, next_key = apply_nodes(state, key, bundle=bundle, t=t)
        return result.agents.income, next_key

    return run_one, observed, traced


def _evaluate_income_transform(run, income, transform):
    if transform == "eager":
        result = run(income)
    elif transform == "jit":
        result = jax.jit(run)(income)
    elif transform == "grad":
        result = jax.grad(lambda x: jnp.sum(run(x)))(income)
    else:
        result = jax.hessian(lambda x: jnp.sum(run(x)))(income)
    result.block_until_ready()
    jax.effects_barrier()
    return result


@pytest.mark.parametrize("transform", ["eager", "jit", "grad", "hessian"])
def test_apply_nodes_rejects_mapped_schedule_before_emission(transform) -> None:
    run_one, observed, traced = _instrumented_log_step()
    key = jax.random.PRNGKey(11)
    times = jnp.array([0, 1], dtype=jnp.int32)
    income = jnp.array([[0.0, 0.0], [2.0, 2.0]], dtype=jnp.float32)

    def run(x):
        return jax.vmap(lambda row, t: run_one(row, t, key)[0])(x, times)

    with pytest.raises(ValueError, match="does not support mapped schedule predicates"):
        _evaluate_income_transform(run, income, transform)
    assert observed == []
    # These transform orders also reject before emitter tracing; a caller
    # that jits the scalar call before mapping may trace it first (below).
    assert traced == []


def test_apply_nodes_vmap_of_jit_rejects_before_numerical_emission() -> None:
    run_one, observed, _ = _instrumented_log_step()
    key = jax.random.PRNGKey(11)
    compiled = jax.jit(lambda row, t: run_one(row, t, key)[0])
    with pytest.raises(ValueError, match="does not support mapped schedule predicates"):
        jax.vmap(compiled)(
            jnp.array([[0.0, 0.0], [2.0, 2.0]], dtype=jnp.float32),
            jnp.array([0, 1], dtype=jnp.int32),
        )
    jax.effects_barrier()
    assert observed == []


@pytest.mark.parametrize("transform", ["eager", "jit", "grad", "hessian"])
def test_apply_nodes_mixed_schedule_scalar_map_executes_only_active_row(transform) -> None:
    run_one, observed, _ = _instrumented_log_step()
    key = jax.random.PRNGKey(11)
    times = jnp.array([0, 1], dtype=jnp.int32)
    income = jnp.array([[0.0, 0.0], [2.0, 2.0]], dtype=jnp.float32)

    def run(x):
        return jax.lax.map(lambda pair: run_one(*pair, key)[0], (x, times))

    result = _evaluate_income_transform(run, income, transform)
    if transform in {"eager", "jit"}:
        expected = jnp.array([[0.0, 0.0], [2.0 + jnp.log(2.0)] * 2])
    elif transform == "grad":
        expected = jnp.array([[1.0, 1.0], [1.5, 1.5]])
    else:
        expected = jnp.diag(jnp.array([0.0, 0.0, -0.25, -0.25])).reshape((2, 2, 2, 2))
    assert jnp.allclose(result, expected)
    assert observed == [[2.0, 2.0]]

    _, next_keys = jax.lax.map(lambda pair: run_one(*pair, key), (income, times))
    next_keys.block_until_ready()
    jax.effects_barrier()
    assert jnp.array_equal(next_keys[0], key)
    assert jnp.array_equal(next_keys[1], jax.random.fold_in(jax.random.split(key)[1], 1))


@pytest.mark.parametrize("transform", ["eager", "jit", "grad", "hessian"])
@pytest.mark.parametrize("active", [False, True])
def test_apply_nodes_state_vmap_preserves_scalar_schedule_execution(transform, active) -> None:
    run_one, observed, _ = _instrumented_log_step()
    key = jax.random.PRNGKey(11)
    time = jnp.array(int(active), dtype=jnp.int32)
    income = jnp.full((2, 2), 2.0 if active else 0.0, dtype=jnp.float32)

    def run(x):
        return jax.vmap(lambda row: run_one(row, time, key)[0])(x)

    result = _evaluate_income_transform(run, income, transform)
    if transform in {"eager", "jit"}:
        expected = income + jnp.log(2.0) if active else income
    elif transform == "grad":
        expected = jnp.full_like(income, 1.5 if active else 1.0)
    else:
        expected = jnp.eye(4).reshape((2, 2, 2, 2)) * (-0.25 if active else 0.0)
    assert jnp.allclose(result, expected)
    assert observed == ([[2.0, 2.0], [2.0, 2.0]] if active else [])


@pytest.mark.parametrize("time", [0, 1])
def test_apply_nodes_mapped_equal_steps_remain_explicitly_unsupported(time) -> None:
    run_one, observed, traced = _instrumented_log_step()
    key = jax.random.PRNGKey(11)
    with pytest.raises(ValueError, match="does not support mapped schedule predicates"):
        jax.vmap(lambda row, t: run_one(row, t, key)[0])(
            jnp.full((2, 2), 2.0), jnp.full((2,), time, dtype=jnp.int32)
        )
    assert observed == []
    assert traced == []


@pytest.mark.parametrize("transform", ["eager", "grad"])
def test_apply_nodes_admission_removal_exposes_inactive_execution(monkeypatch, transform) -> None:
    # Remove the behavioral admission while retaining the public call, its
    # documentation, and branch/patch structure. Finite value/gradient checks
    # alone cannot detect the inactive emitter execution on this JAX backend.
    monkeypatch.setattr(
        "polisyos.foundry.calibration.pure_executor._admit_schedule_predicate",
        lambda active: active,
    )
    run_one, observed, _ = _instrumented_log_step()
    key = jax.random.PRNGKey(11)
    times = jnp.array([0, 1], dtype=jnp.int32)
    income = jnp.array([[0.0, 0.0], [2.0, 2.0]], dtype=jnp.float32)

    def run(x):
        return jax.vmap(lambda row, t: run_one(row, t, key)[0])(x, times)

    result = _evaluate_income_transform(run, income, transform)
    expected = (
        jnp.array([[1.0, 1.0], [1.5, 1.5]])
        if transform == "grad"
        else jnp.array([[0.0, 0.0], [2.0 + jnp.log(2.0)] * 2])
    )
    assert jnp.allclose(result, expected)
    assert observed == [[0.0, 0.0], [2.0, 2.0]]


@pytest.mark.parametrize("transform", ["eager", "jit", "grad", "hessian"])
def test_apply_nodes_active_invalid_log_is_not_replaced_by_neutral_input(transform) -> None:
    run_one, observed, _ = _instrumented_log_step()
    key = jax.random.PRNGKey(11)

    def run(x):
        return run_one(x, jnp.array(1, dtype=jnp.int32), key)[0]

    result = _evaluate_income_transform(run, jnp.zeros(2, dtype=jnp.float32), transform)
    assert not jnp.all(jnp.isfinite(result))
    assert observed == [[0.0, 0.0]]
