from __future__ import annotations

from typing import ClassVar

import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.common.canonical_profile import CanonicalProfileRefusalError
from polisyos.core.artifacts.manifest import ArtifactRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    FoundryExecConfig,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    LoweredIR,
    LoweredIRRef,
    ProgramEdge,
    ProgramGraph,
    ProgramGraphRef,
    ProgramNode,
    SimulationResult,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import (
    ExecutionStrictness,
    apply_state_delta_and_snapshot,
    execute_program_graph,
    load_state_snapshot,
    put_state_snapshot,
)
from polisyos.foundry.methods.backends.circuit_breaker import CircuitBreakerRegistry
from polisyos.foundry.methods.backends.dispatch import MethodDispatcher
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.base import (
    SlotSpec as MethodSlotSpec,
)
from polisyos.foundry.methods.registry import MethodRegistry
from polisyos.ir.kernel import (
    DEFAULT_MECHANISM_REGISTRY,
    DEFAULT_MERGE_RULE_REGISTRY,
    DEFAULT_SLOT_REGISTRY,
)


def _dummy_ir_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="sha256:" + "a" * 64,
        kind="ir.trinity_bundle",
        media_type="application/json",
    )


def _put_json(store: FileSystemCAS, payload, *, kind: str):
    payload_type = type(payload)
    owner_kind = getattr(payload_type, "ARTIFACT_KIND", kind)
    if owner_kind != kind:
        raise ValueError(f"fixture kind {kind!r} differs from typed owner {owner_kind!r}")
    schema_name = getattr(payload_type, "ARTIFACT_SCHEMA_NAME", None)
    schema_version = getattr(payload_type, "ARTIFACT_SCHEMA_VERSION", None)
    schema = (
        None
        if schema_name is None or schema_version is None
        else SchemaInfo(name=schema_name, version=schema_version)
    )
    media_type = getattr(payload_type, "ARTIFACT_MEDIA_TYPE", "application/json")
    return store.put_json(
        payload,
        PutOptions(kind=kind, media_type=media_type, schema=schema),
    )


def _put_graph_and_plan(
    store: FileSystemCAS,
    *,
    nodes: list[ProgramNode],
    edges: list[ProgramEdge] | None = None,
    order: list[str] | None = None,
    random_seed: int | None = None,
    max_steps: int | None = None,
    mode: str = "dev",
    jit: bool = True,
    determinism_tier: str | None = None,
    environment_fingerprint: str | None = None,
) -> tuple[ProgramGraphRef, ExecPlanRef]:
    lowered_ir_ref = _put_json(
        store,
        LoweredIR(ir_ref=_dummy_ir_ref(), mechanisms=[], constraints=[]),
        kind="foundry.lowered_ir",
    )
    graph = ProgramGraph(
        ir_ref=_dummy_ir_ref(),
        lowered_ir_ref=LoweredIRRef(artifact_id=lowered_ir_ref.artifact_id),
        nodes=nodes,
        edges=list(edges or []),
        entrypoints=[node.node_id for node in nodes if not edges],
    )
    graph_ref = _put_json(store, graph, kind="foundry.program_graph")
    exec_plan = ExecPlan(
        program_ref=ProgramGraphRef(artifact_id=graph_ref.artifact_id),
        order=order or [node.node_id for node in nodes],
        random_seed=random_seed,
        max_steps=max_steps,
        mode=mode,
        jit=jit,
        determinism_tier=determinism_tier,
        environment_fingerprint=environment_fingerprint,
    )
    exec_plan_ref = _put_json(store, exec_plan, kind="foundry.exec_plan")
    return (
        ProgramGraphRef(artifact_id=graph_ref.artifact_id),
        ExecPlanRef(artifact_id=exec_plan_ref.artifact_id),
    )


def _make_input_bindings(
    store: FileSystemCAS,
    *,
    registry_bundle_ref: ArtifactRef,
    base_state: GlobalState,
) -> FoundryInputBindingsRef:
    snapshot_ref = put_state_snapshot(store, state=base_state, step=int(base_state.step))
    state_snapshot_ref = StateSnapshotRef(artifact_id=snapshot_ref.artifact_id)
    data_snapshot_ref = _put_json(
        store,
        DataSnapshot(data_ref=state_snapshot_ref),
        kind="fabric.data_snapshot",
    )
    bindings_ref = _put_json(
        store,
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry_bundle_ref,
            rules=[],
            bound_state_snapshot_ref=state_snapshot_ref,
        ),
        kind="foundry.input_bindings",
    )
    return FoundryInputBindingsRef(artifact_id=bindings_ref.artifact_id)


def _make_method_signature(name: str) -> MethodSignature:
    unit = Unit(dimension="none", symbol="1")
    patch_unit = Unit(dimension="patch_payload", symbol="json")
    return MethodSignature(
        name=name,
        namespace="tests.runtime",
        version="1.0.0",
        input_slots=frozenset({MethodSlotSpec(name="state", slot_type=SlotType.SCALAR, unit=unit)}),
        output_slots=frozenset(
            {MethodSlotSpec(name="patch_records", slot_type=SlotType.SCALAR, unit=patch_unit)}
        ),
        parameters=(),
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )


class _MethodWritesIncome:
    signature: ClassVar[MethodSignature] = _make_method_signature("writes_income")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="writes income patch")

    @staticmethod
    def pure_step(state, params):
        delta = jnp.full_like(state.agents.income, 5.0)
        return {"patch_records": {"agents.income": [{"delta": delta}]}}


class _MethodReadsIncomeWritesReported:
    signature: ClassVar[MethodSignature] = _make_method_signature("reads_income_writes_reported")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="reads visible state")

    @staticmethod
    def pure_step(state, params):
        return {
            "patch_records": {
                "agents.reported_income": [{"value": jnp.asarray(state.agents.income)}]
            }
        }


class _MethodWritesSeededIncome:
    signature: ClassVar[MethodSignature] = _make_method_signature("writes_seeded_income")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="records seeded draw")

    @staticmethod
    def pure_step(state, params):
        draw = float(params["__rng__"].uniform(0.0, 1.0))
        delta = jnp.full_like(state.agents.income, draw)
        return {"patch_records": {"agents.income": [{"delta": delta}]}}


class _MethodWritesSeededBalance:
    signature: ClassVar[MethodSignature] = _make_method_signature("writes_seeded_balance")
    metadata: ClassVar[MethodMetadata] = MethodMetadata(description="records seeded draw")

    @staticmethod
    def pure_step(state, params):
        draw = float(params["__rng__"].uniform(0.0, 1.0))
        return {"patch_records": {"government.balance": [{"delta": draw}]}}


@pytest.fixture(autouse=True)
def _reset_method_runtime():
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()
    MethodDispatcher.reset_instance()
    CircuitBreakerRegistry.reset_instance()


def _scheduled_payload(store: FileSystemCAS):
    return _put_json(
        store,
        {"schedule": {"start_step": 0, "duration_steps": 1}, "params": {}},
        kind="foundry.node_payload",
    )


def test_dependency_boundary_flushes_visible_state_for_mechanism_chain(
    tmp_path, monkeypatch
) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=2, n_firms=1)

    class _IncomeWriter:
        def emit_patches(self, state, key, *, target_mask=None):
            delta = jnp.full_like(state.agents.income, 5.0)
            return {"agents.income": [{"delta": delta}]}, key

    class _IncomeReader:
        def emit_patches(self, state, key, *, target_mask=None):
            return {"agents.reported_income": [{"value": jnp.asarray(state.agents.income)}]}, key

    def _fake_factory(mechanism_type, params, **kwargs):
        if mechanism_type == "writer":
            return _IncomeWriter()
        if mechanism_type == "reader":
            return _IncomeReader()
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.graph.create_mechanism_from_spec", _fake_factory
    )

    writer_payload = _scheduled_payload(store)
    reader_payload = _scheduled_payload(store)
    program_ref, exec_plan_ref = _put_graph_and_plan(
        store,
        nodes=[
            ProgramNode(
                node_id="writer",
                node_kind="mechanism",
                mechanism_type="writer",
                params_ref=writer_payload,
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="reader",
                node_kind="mechanism",
                mechanism_type="reader",
                params_ref=reader_payload,
                inputs=["agents.income"],
                outputs=["agents.reported_income"],
            ),
        ],
        edges=[ProgramEdge(src="writer", dst="reader", relation="depends_on")],
        order=["writer", "reader"],
    )

    exec_artifacts = execute_program_graph(
        store,
        program_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        strictness=ExecutionStrictness.RESEARCH,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([5.0, 5.0], dtype=jnp.float32))
    assert jnp.allclose(
        next_state.agents.reported_income,
        jnp.array([5.0, 5.0], dtype=jnp.float32),
    )


def test_method_nodes_see_visible_state_on_dependency_edges(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry = MethodRegistry.get_instance()
    registry.register(_MethodWritesIncome)
    registry.register(_MethodReadsIncomeWritesReported)
    base_state = GlobalState.empty(n_agents=2, n_firms=1)

    program_ref, exec_plan_ref = _put_graph_and_plan(
        store,
        nodes=[
            ProgramNode(
                node_id="m1",
                node_kind="method",
                method_fqn=_MethodWritesIncome.signature.fqn,
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="m2",
                node_kind="method",
                method_fqn=_MethodReadsIncomeWritesReported.signature.fqn,
                inputs=["agents.income"],
                outputs=["agents.reported_income"],
            ),
        ],
        edges=[ProgramEdge(src="m1", dst="m2", relation="depends_on")],
        order=["m1", "m2"],
    )

    exec_artifacts = execute_program_graph(
        store,
        program_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        strictness=ExecutionStrictness.RESEARCH,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([5.0, 5.0], dtype=jnp.float32))
    assert jnp.allclose(
        next_state.agents.reported_income,
        jnp.array([5.0, 5.0], dtype=jnp.float32),
    )


def test_independent_writers_keep_batched_merge_semantics(tmp_path, monkeypatch) -> None:
    store = FileSystemCAS(tmp_path)
    base_state = GlobalState.empty(n_agents=2, n_firms=1)

    class _DependentDelta:
        def __init__(self, offset: float) -> None:
            self._offset = offset

        def emit_patches(self, state, key, *, target_mask=None):
            delta = jnp.asarray(state.agents.income) + self._offset
            return {"agents.income": [{"delta": delta}]}, key

    def _fake_factory(mechanism_type, params, **kwargs):
        if mechanism_type == "left":
            return _DependentDelta(1.0)
        if mechanism_type == "right":
            return _DependentDelta(2.0)
        raise AssertionError(mechanism_type)

    monkeypatch.setattr(
        "polisyos.foundry.execute._internal.graph.create_mechanism_from_spec", _fake_factory
    )

    left_payload = _scheduled_payload(store)
    right_payload = _scheduled_payload(store)
    program_ref, exec_plan_ref = _put_graph_and_plan(
        store,
        nodes=[
            ProgramNode(
                node_id="left",
                node_kind="mechanism",
                mechanism_type="left",
                params_ref=left_payload,
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="right",
                node_kind="mechanism",
                mechanism_type="right",
                params_ref=right_payload,
                outputs=["agents.income"],
            ),
        ],
        order=["left", "right"],
    )

    exec_artifacts = execute_program_graph(
        store,
        program_ref=program_ref,
        exec_plan_ref=exec_plan_ref,
        base_state=base_state,
        mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        strictness=ExecutionStrictness.RESEARCH,
    )

    next_state, _ = apply_state_delta_and_snapshot(
        store,
        base_state=base_state,
        state_delta_ref=exec_artifacts.state_delta_ref,
        slot_registry=DEFAULT_SLOT_REGISTRY,
        merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
    )

    assert jnp.allclose(next_state.agents.income, jnp.array([3.0, 3.0], dtype=jnp.float32))


def test_method_nodes_get_unique_but_deterministic_child_seeds(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    registry = MethodRegistry.get_instance()
    registry.register(_MethodWritesSeededIncome)
    registry.register(_MethodWritesSeededBalance)
    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    program_ref, exec_plan_ref = _put_graph_and_plan(
        store,
        nodes=[
            ProgramNode(
                node_id="income_seed",
                node_kind="method",
                method_fqn=_MethodWritesSeededIncome.signature.fqn,
                outputs=["agents.income"],
            ),
            ProgramNode(
                node_id="balance_seed",
                node_kind="method",
                method_fqn=_MethodWritesSeededBalance.signature.fqn,
                outputs=["government.balance"],
            ),
        ],
        order=["income_seed", "balance_seed"],
    )

    def _run(seed: int) -> tuple[np.ndarray, float]:
        artifacts = execute_program_graph(
            store,
            program_ref=program_ref,
            exec_plan_ref=exec_plan_ref,
            base_state=base_state,
            mechanism_registry=DEFAULT_MECHANISM_REGISTRY,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
            seed=seed,
            strictness=ExecutionStrictness.RESEARCH,
        )
        state, _ = apply_state_delta_and_snapshot(
            store,
            base_state=base_state,
            state_delta_ref=artifacts.state_delta_ref,
            slot_registry=DEFAULT_SLOT_REGISTRY,
            merge_registry=DEFAULT_MERGE_RULE_REGISTRY,
        )
        return np.asarray(state.agents.income), float(state.government_balance)

    income_a, balance_a = _run(17)
    income_b, balance_b = _run(17)
    income_c, balance_c = _run(18)

    assert income_a[0] != pytest.approx(balance_a)
    assert income_a == pytest.approx(income_b)
    assert balance_a == pytest.approx(balance_b)
    assert not np.allclose(income_a, income_c)
    assert balance_a != pytest.approx(balance_c)


def test_execute_facade_honors_exec_plan_seed_and_request_override(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    registry = MethodRegistry.get_instance()
    registry.register(_MethodWritesSeededIncome)

    base_state = GlobalState.empty(n_agents=2, n_firms=1)
    bindings_ref = _make_input_bindings(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        base_state=base_state,
    )
    graph_nodes = [
        ProgramNode(
            node_id="seeded",
            node_kind="method",
            method_fqn=_MethodWritesSeededIncome.signature.fqn,
            outputs=["agents.income"],
        )
    ]
    _, exec_plan_ref_a = _put_graph_and_plan(
        store,
        nodes=graph_nodes,
        order=["seeded"],
        random_seed=101,
    )
    _, exec_plan_ref_b = _put_graph_and_plan(
        store,
        nodes=graph_nodes,
        order=["seeded"],
        random_seed=202,
    )

    def _run(
        exec_plan_ref: ExecPlanRef, exec_config: FoundryExecConfig | None = None
    ) -> np.ndarray:
        result = execute_foundry(
            store,
            ExecuteRequest(
                exec_plan_ref=exec_plan_ref,
                input_bindings_ref=bindings_ref,
                registry_bundle_ref=bundle.bundle_ref,
                exec_config=exec_config or FoundryExecConfig(),
            ),
        )
        assert result.ok
        sim_payload = from_canonical_bytes(
            store.get_bytes(result.simulation_result_ref.artifact_id)
        )
        sim = SimulationResult.model_validate(sim_payload)
        final_state = load_state_snapshot(store, snapshot_ref=sim.state_snapshot_ref)
        return np.asarray(final_state.agents.income)

    income_a = _run(exec_plan_ref_a)
    income_b = _run(exec_plan_ref_b)
    income_override = _run(exec_plan_ref_a, FoundryExecConfig(seed=202))

    assert not np.allclose(income_a, income_b)
    assert income_override == pytest.approx(income_b)


def test_execute_facade_surfaces_posture_notes_and_blocks_on_max_steps(tmp_path) -> None:
    store = FileSystemCAS(tmp_path)
    bundle = build_default_registry_bundle(store)
    load_registry_bundle_content(store, bundle.bundle_ref)
    registry = MethodRegistry.get_instance()
    registry.register(_MethodWritesSeededIncome)

    base_state = GlobalState.empty(n_agents=2, n_firms=1).replace(
        step=jnp.asarray(4, dtype=jnp.int32)
    )
    bindings_ref = _make_input_bindings(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        base_state=base_state,
    )
    graph_nodes = [
        ProgramNode(
            node_id="seeded",
            node_kind="method",
            method_fqn=_MethodWritesSeededIncome.signature.fqn,
            outputs=["agents.income"],
        )
    ]
    _, exec_plan_ref = _put_graph_and_plan(
        store,
        nodes=graph_nodes,
        order=["seeded"],
        random_seed=7,
        mode="perf",
        jit=True,
        determinism_tier="strict_cpu",
        environment_fingerprint="compile-time-fingerprint",
    )
    result = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=exec_plan_ref,
            input_bindings_ref=bindings_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )

    assert result.ok
    assert any(note.startswith("unsupported_exec_hint:jit") for note in result.notes)
    assert any(note.startswith("unsupported_exec_hint:mode=perf") for note in result.notes)
    assert any(note.startswith("environment_fingerprint_mismatch:") for note in result.notes)

    blocked_state = base_state.replace(step=jnp.asarray(5, dtype=jnp.int32))
    blocked_bindings_ref = _make_input_bindings(
        store,
        registry_bundle_ref=bundle.bundle_ref,
        base_state=blocked_state,
    )
    _, maxed_plan_ref = _put_graph_and_plan(
        store,
        nodes=graph_nodes,
        order=["seeded"],
        random_seed=7,
        max_steps=5,
    )
    blocked = execute_foundry(
        store,
        ExecuteRequest(
            exec_plan_ref=maxed_plan_ref,
            input_bindings_ref=blocked_bindings_ref,
            registry_bundle_ref=bundle.bundle_ref,
        ),
    )

    assert blocked.ok is False
    assert any(note.startswith("max_steps_reached:") for note in blocked.notes)


def test_execute_api_loader_rejects_selected_program_version_drift(tmp_path) -> None:
    from polisyos.foundry.execute.api import _load_model

    store = FileSystemCAS(tmp_path / "cas")
    payload = ProgramGraph(ir_ref=_dummy_ir_ref()).model_dump(mode="json")
    payload["schema_version"] = "0.3"
    ref = store.put_json(
        payload,
        PutOptions(
            kind=ProgramGraph.ARTIFACT_KIND,
            media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
            ),
        ),
    )

    with pytest.raises(
        CanonicalProfileRefusalError,
        match="canon_profile_typed_artifact_schema_version_mismatch",
    ):
        _load_model(store, ref, ProgramGraph)


def test_execute_selected_basis_loads_trinity_through_ir_owner_reader(tmp_path) -> None:
    from polisyos.core.artifacts import ensure_ir_artifact_store, validate_core_model_json_artifact
    from polisyos.core.artifacts.manifest import InputRef
    from polisyos.core.contracts.foundry import FoundryExecutionInputBasis
    from polisyos.ir.governance.policy_spec import PolicySpec
    from polisyos.ir.governance.problem_frame import KPISpec, ProblemDomain, ProblemFrame
    from polisyos.ir.model_layer.model_spec import ModelSpec
    from polisyos.ir.model_layer.types import OptimizationDirection
    from polisyos.ir.trinity import TrinityBundle
    from polisyos.ir.trinity.loaders import load_trinity_bundle_artifact

    store = FileSystemCAS(tmp_path / "cas")
    registry = build_default_registry_bundle(store, return_selected_profile=True)
    state_snapshot_ref = put_state_snapshot(
        store,
        state=GlobalState.empty(n_agents=2, n_firms=1),
        step=0,
        return_selected_profile=True,
    )

    def _input_ref(ref: ArtifactRef, role: str) -> InputRef:
        assert ref.manifest_profile_sha256 is not None
        return InputRef(
            artifact_id=ref.artifact_id,
            role=role,
            manifest_profile_sha256=ref.manifest_profile_sha256,
        )

    data_snapshot_ref = store.put_json(
        DataSnapshot(data_ref=state_snapshot_ref),
        PutOptions(
            kind=DataSnapshot.ARTIFACT_KIND,
            media_type=DataSnapshot.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=DataSnapshot.ARTIFACT_SCHEMA_NAME,
                version=DataSnapshot.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[_input_ref(state_snapshot_ref, "state_snapshot")],
        ),
        return_selected_profile=True,
    )
    candidate_ref = store.put_json(
        {"candidate_id": "candidate_for_execution_basis"},
        PutOptions(
            kind="scientist.policy_design.candidate",
            media_type="application/json",
            schema=SchemaInfo(name="scientist.policy_design.Candidate", version="1.0"),
            inputs=[
                _input_ref(data_snapshot_ref, "world_model_data_snapshot"),
                _input_ref(registry.bundle_ref, "world_model_registry"),
            ],
        ),
        return_selected_profile=True,
    )
    trinity = TrinityBundle(
        problem_frame=ProblemFrame(
            problem_id="selected_execution_basis",
            domain=ProblemDomain.FISCAL,
            kpis=[
                KPISpec(
                    kpi_id="selected_kpi",
                    metric_id="selected_metric",
                    direction=OptimizationDirection.MAXIMIZE,
                )
            ],
        ),
        policy_spec=PolicySpec(policy_id="selected_policy", interventions=[]),
        model_spec=ModelSpec(
            model_id="selected_model",
            data_snapshot_ref=str(data_snapshot_ref.artifact_id),
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )

    def _persist_plan(schema_version: str) -> ExecPlanRef:
        trinity_ref = store.put_json(
            trinity,
            PutOptions(
                kind=TrinityBundle.ARTIFACT_KIND,
                media_type=TrinityBundle.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=TrinityBundle.ARTIFACT_SCHEMA_NAME,
                    version=schema_version,
                ),
                inputs=[_input_ref(candidate_ref, "policy_candidate")],
            ),
            return_selected_profile=True,
        )
        lowered_ir_ref = store.put_json(
            LoweredIR(ir_ref=trinity_ref),
            PutOptions(kind="foundry.lowered_ir", media_type="application/json"),
            return_selected_profile=True,
        )
        graph_ref = store.put_json(
            ProgramGraph(
                ir_ref=trinity_ref,
                lowered_ir_ref=LoweredIRRef.model_validate(
                    lowered_ir_ref.model_dump(mode="python")
                ),
            ),
            PutOptions(
                kind=ProgramGraph.ARTIFACT_KIND,
                media_type=ProgramGraph.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=ProgramGraph.ARTIFACT_SCHEMA_NAME,
                    version=ProgramGraph.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[
                    _input_ref(trinity_ref, "trinity_bundle"),
                    _input_ref(lowered_ir_ref, "lowered_ir"),
                    _input_ref(registry.bundle_ref, "registry_bundle"),
                ],
            ),
            return_selected_profile=True,
        )
        plan_ref = store.put_json(
            ExecPlan(
                program_ref=ProgramGraphRef.model_validate(graph_ref.model_dump(mode="python")),
                order=[],
            ),
            PutOptions(
                kind=ExecPlan.ARTIFACT_KIND,
                media_type=ExecPlan.ARTIFACT_MEDIA_TYPE,
                schema=SchemaInfo(
                    name=ExecPlan.ARTIFACT_SCHEMA_NAME,
                    version=ExecPlan.ARTIFACT_SCHEMA_VERSION,
                ),
                inputs=[_input_ref(graph_ref, "program_graph")],
            ),
            return_selected_profile=True,
        )
        return ExecPlanRef.model_validate(plan_ref.model_dump(mode="python"))

    bindings_ref = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_snapshot_ref,
            registry_bundle_ref=registry.bundle_ref,
            rules=[],
            bound_state_snapshot_ref=StateSnapshotRef.model_validate(
                state_snapshot_ref.model_dump(mode="python")
            ),
        ),
        PutOptions(
            kind=FoundryInputBindings.ARTIFACT_KIND,
            media_type=FoundryInputBindings.ARTIFACT_MEDIA_TYPE,
            schema=SchemaInfo(
                name=FoundryInputBindings.ARTIFACT_SCHEMA_NAME,
                version=FoundryInputBindings.ARTIFACT_SCHEMA_VERSION,
            ),
            inputs=[
                _input_ref(data_snapshot_ref, "data_snapshot"),
                _input_ref(state_snapshot_ref, "bound_state_snapshot"),
                _input_ref(registry.bundle_ref, "registry_bundle"),
            ],
        ),
        return_selected_profile=True,
    )
    request = ExecuteRequest(
        exec_plan_ref=_persist_plan(TrinityBundle.ARTIFACT_SCHEMA_VERSION),
        input_bindings_ref=FoundryInputBindingsRef.model_validate(
            bindings_ref.model_dump(mode="python")
        ),
        registry_bundle_ref=registry.bundle_ref,
        return_selected_profile=True,
    )

    result = execute_foundry(store, request)

    assert result.ok
    assert result.simulation_result_ref is not None
    simulation = validate_core_model_json_artifact(
        SimulationResult, store, result.simulation_result_ref
    )
    assert simulation.execution_input_basis_ref is not None
    basis = validate_core_model_json_artifact(
        FoundryExecutionInputBasis, store, simulation.execution_input_basis_ref
    )
    assert basis.trinity_bundle_ref.manifest_profile_sha256 is not None
    loaded = load_trinity_bundle_artifact(ensure_ir_artifact_store(store), basis.trinity_bundle_ref)
    assert loaded.problem_frame.kpis[0].direction is OptimizationDirection.MAXIMIZE

    with pytest.raises(ValueError, match="manifest does not match its IR owner"):
        execute_foundry(
            store,
            request.model_copy(update={"exec_plan_ref": _persist_plan("9.0")}),
        )
