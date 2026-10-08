"""Treasury CAS lineage must decide the real stochastic execution stream."""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from polisyos.core.artifacts.manifest import ArtifactRef, InputRef, SchemaInfo
from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes
from polisyos.core.compiler.report import CompileReport
from polisyos.core.contracts.fabric import DataSnapshot
from polisyos.core.contracts.foundry import (
    CompileRequest,
    ExecPlan,
    ExecPlanRef,
    ExecuteRequest,
    FoundryCompileConfig,
    FoundryExecConfig,
    FoundryInputBindings,
    FoundryInputBindingsRef,
    ProgramGraph,
    SimulationResult,
    StateDelta,
    StateSnapshotRef,
)
from polisyos.core.registry import build_default_registry_bundle, load_registry_bundle_content
from polisyos.foundry.agent_sim.agents import AdaptiveAgentMechanism
from polisyos.foundry.compile.api import compile
from polisyos.foundry.compile.randomization import TreasuryPlan, build_treasury_plan
from polisyos.foundry.contracts.state import GlobalState
from polisyos.foundry.execute._internal.graph import execute_program_graph
from polisyos.foundry.execute._internal.ops import apply_ops_to_state
from polisyos.foundry.execute.api import execute as execute_foundry
from polisyos.foundry.execute.executor import load_state_snapshot, put_state_snapshot
from polisyos.ir.governance.policy_spec import InterventionSpec, PolicySpec
from polisyos.ir.governance.problem_frame import ProblemDomain, ProblemFrame
from polisyos.ir.model_layer.model_spec import ModelSpec
from polisyos.ir.trinity import TrinityBundle

PROFILE = "randomization:treasury_salts_v1"
PARAMS = {
    "observation_space": ["agents.income"],
    "action_space": {"type": "continuous", "affects": ["agents.income"]},
    "policy_model": {"type": "mlp", "hidden_layers": []},
    "utility": "linear",
    "seed": 0,
    "stochastic": True,
}


def _load(store, ref, model):
    return model.model_validate(from_canonical_bytes(store.get_bytes(ref)))


def _compile(root: Path, seed: int = 17):
    store = FileSystemCAS(root)
    registry = build_default_registry_bundle(store)
    bundle = TrinityBundle(
        problem_frame=ProblemFrame(problem_id="treasury_execution", domain=ProblemDomain.FISCAL),
        policy_spec=PolicySpec(
            policy_id="treasury_execution",
            interventions=[
                InterventionSpec(
                    intervention_id="stochastic_action",
                    kind="adaptive_agent",
                    target={"kind": "predicate", "field": "id", "operator": "==", "value": "all"},
                    schedule={"start_step": 0, "duration_steps": 2},
                    params=PARAMS,
                ),
            ],
        ),
        model_spec=ModelSpec(
            model_id="treasury_execution",
            data_snapshot_ref="sha256:" + "0" * 64,
            registry_bundle_ref=str(registry.bundle_ref.artifact_id),
        ),
    )
    ref = store.put_json(
        bundle, PutOptions(kind="ir.trinity_bundle", media_type="application/json")
    )
    result = compile(
        store,
        CompileRequest(
            policy_ref=ref,
            registry_bundle_ref=registry.bundle_ref,
            compile_config=FoundryCompileConfig(random_seed=seed),
        ),
    )
    assert result.ok, result.notes
    report = _load(store, result.compile_report_ref, CompileReport)
    content = load_registry_bundle_content(store, registry.bundle_ref)
    return store, report, content


def _base_state():
    state = GlobalState.empty(n_agents=32, n_firms=0)
    return state.replace(
        agents=state.agents.replace(active=jnp.ones(32, dtype=jnp.bool_), income=jnp.zeros(32))
    )


def _execute(store, report, content, **kwargs):
    base = _base_state()
    output = execute_program_graph(
        store,
        program_ref=report.program_graph_ref,
        exec_plan_ref=report.exec_plan_ref,
        base_state=base,
        mechanism_registry=content.mechanism_registry,
        slot_registry=content.slot_registry,
        merge_registry=content.merge_registry,
        selector_field_registry=content.selector_field_registry,
        welfare_bound_mode="off",
        **kwargs,
    )
    assert not output.failure_cards
    delta = _load(store, output.state_delta_ref, StateDelta)
    changed = apply_ops_to_state(
        store,
        base_state=base,
        ops=delta.ops,
        slot_registry=content.slot_registry,
        merge_registry=content.merge_registry,
    )
    return np.asarray(changed.agents.income)


def _oracle(seed, root_seed, node_id):
    key = jax.random.PRNGKey(seed)
    for label in ("stream:default", f"node:{node_id}"):
        label = label if root_seed == 0 else f"{root_seed}:{label}"
        salt = int(sha256(label.encode()).hexdigest()[:16], 16)
        key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
        key = jax.random.fold_in(key, salt >> 32)
    _, draw_key = jax.random.split(key)
    mechanism = AdaptiveAgentMechanism(**PARAMS)
    patches, _ = mechanism.emit_patches(
        _base_state(), draw_key, target_mask=jnp.ones(32, dtype=jnp.bool_)
    )
    return np.asarray(patches["agents.income"][0]["value"])


@pytest.mark.parametrize("seed", [None, 0, 17, 2147483655])
def test_compiled_seed_and_persisted_salts_drive_actual_native_kernel(tmp_path, seed):
    store, report, content = _compile(tmp_path / "cas", seed)
    plan = _load(store, report.exec_plan_ref, ExecPlan)
    graph = _load(store, report.program_graph_ref, ProgramGraph)
    treasury = _load(store, report.treasury_plan_ref, TreasuryPlan)
    assert treasury.root_seed == (seed or 0)
    assert plan.random_seed == seed
    assert PROFILE in plan.notes
    (edge,) = [
        x for x in store.get_manifest(report.exec_plan_ref).inputs if x.role == "treasury_plan"
    ]
    assert edge.artifact_id == report.treasury_plan_ref.artifact_id
    assert edge.manifest_profile_sha256 == report.treasury_plan_ref.manifest_profile_sha256
    (node,) = [n for n in graph.nodes if n.mechanism_type == "adaptive_agent"]
    reopened = FileSystemCAS(tmp_path / "cas")
    actual = _execute(reopened, report, content)
    np.testing.assert_array_equal(actual, _oracle(seed or 0, seed or 0, node.node_id))
    np.testing.assert_array_equal(_execute(reopened, report, content), actual)
    override = _execute(reopened, report, content, seed=101)
    np.testing.assert_array_equal(override, _oracle(101, seed or 0, node.node_id))
    assert not np.array_equal(actual, override)


def _replace_plan(store, report, *, plan=None, inputs=None):
    plan = plan or _load(store, report.exec_plan_ref, ExecPlan)
    manifest = store.get_manifest(report.exec_plan_ref)
    ref = store.put_json(
        plan,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs if inputs is None else inputs,
        ),
    )
    return report.model_copy(update={"exec_plan_ref": ref})


@pytest.mark.parametrize("seed", [None, 0, 17])
def test_unmarked_historical_plan_keeps_sequential_default_and_override(tmp_path, seed):
    store, report, content = _compile(tmp_path / "cas")
    plan = _load(store, report.exec_plan_ref, ExecPlan)
    historical = plan.model_copy(update={"notes": [], "random_seed": 4321})
    report = _replace_plan(store, report, plan=historical)
    kwargs = {} if seed is None else {"seed": seed}
    _, draw_key = jax.random.split(jax.random.PRNGKey(seed or 0))
    patches, _ = AdaptiveAgentMechanism(**PARAMS).emit_patches(
        _base_state(), draw_key, target_mask=jnp.ones(32, dtype=jnp.bool_)
    )
    np.testing.assert_array_equal(
        _execute(store, report, content, **kwargs), np.asarray(patches["agents.income"][0]["value"])
    )


@pytest.mark.parametrize(
    "defect,reason",
    [
        ("unknown_profile", "unsupported_randomization_profile"),
        ("duplicate_profile", "unsupported_randomization_profile"),
        ("missing_treasury", "treasury_requires_one_treasury_plan_input"),
        ("duplicate_treasury", "treasury_requires_one_treasury_plan_input"),
        ("wrong_plan_program", "treasury_exec_program_mismatch"),
        ("wrong_program_input", "treasury_program_input_mismatch"),
        ("wrong_treasury_program", "treasury_source_program_mismatch"),
        ("wrong_root", "treasury_seed_or_salts_mismatch"),
        ("wrong_node_salt", "treasury_seed_or_salts_mismatch"),
        ("missing_node", "treasury_seed_or_salts_mismatch"),
        ("extra_node", "treasury_seed_or_salts_mismatch"),
        ("wrong_stream", "treasury_seed_or_salts_mismatch"),
        ("wrong_kind", "Artifact reference type does not match selected manifest"),
        ("wrong_schema", "treasury_manifest_schema_or_kind"),
    ],
)
def test_profile_rejects_cas_bound_same_shape_wrong_property_before_kernel(
    tmp_path, monkeypatch, defect, reason
):
    store, report, content = _compile(tmp_path / "cas")
    plan = _load(store, report.exec_plan_ref, ExecPlan)
    inputs = list(store.get_manifest(report.exec_plan_ref).inputs)
    if defect == "unknown_profile":
        plan = plan.model_copy(update={"notes": ["randomization:treasury_salts_v2"]})
    elif defect == "duplicate_profile":
        plan = plan.model_copy(update={"notes": [PROFILE, PROFILE]})
    elif defect == "wrong_plan_program":
        plan = plan.model_copy(
            update={
                "program_ref": plan.program_ref.model_copy(
                    update={"artifact_id": report.treasury_plan_ref.artifact_id}
                )
            }
        )
    elif defect == "missing_treasury":
        inputs = [x for x in inputs if x.role != "treasury_plan"]
    elif defect == "duplicate_treasury":
        inputs += [x for x in inputs if x.role == "treasury_plan"]
    elif defect == "wrong_program_input":
        inputs = [
            x.model_copy(update={"artifact_id": report.treasury_plan_ref.artifact_id})
            if x.role == "program_graph"
            else x
            for x in inputs
        ]
    else:
        treasury = _load(store, report.treasury_plan_ref, TreasuryPlan)
        manifest = store.get_manifest(report.treasury_plan_ref)
        treasury_inputs = manifest.inputs
        kind, schema = manifest.kind, manifest.artifact_schema
        if defect == "wrong_treasury_program":
            treasury_inputs = [
                InputRef(artifact_id=report.exec_plan_ref.artifact_id, role="program_graph")
            ]
        elif defect == "wrong_kind":
            kind = "test.valid_wrong_owner"
        elif defect == "wrong_schema":
            schema = SchemaInfo(name="polisyos.foundry.TreasuryPlan", version="2.0")
        elif defect == "wrong_root":
            treasury = treasury.model_copy(update={"root_seed": 0})
        elif defect == "wrong_stream":
            treasury = treasury.model_copy(update={"stream_salts": {"default": 0}})
        else:
            salts = dict(treasury.node_salts)
            node = next(iter(salts))
            if defect == "wrong_node_salt":
                salts[node] ^= 1 << 48
            elif defect == "missing_node":
                salts.pop(node)
            elif defect == "extra_node":
                salts["unbound_node"] = 0
            treasury = treasury.model_copy(update={"node_salts": salts})
        ref = store.put_json(
            treasury,
            PutOptions(
                kind=kind, media_type="application/json", schema=schema, inputs=treasury_inputs
            ),
        )
        inputs = [
            InputRef(
                artifact_id=ref.artifact_id,
                role="treasury_plan",
                manifest_profile_sha256=ref.manifest_profile_sha256,
            )
            if x.role == "treasury_plan"
            else x
            for x in inputs
        ]
    report = _replace_plan(store, report, plan=plan, inputs=inputs)

    def forbidden_kernel(*args, **kwargs):
        pytest.fail("invalid treasury reached a native kernel")

    monkeypatch.setattr(AdaptiveAgentMechanism, "emit_patches", forbidden_kernel)
    with pytest.raises(ValueError, match=reason):
        _execute(FileSystemCAS(tmp_path / "cas"), report, content)


@pytest.mark.parametrize("removal", ["all_salts", "high_word", "stream_salt"])
def test_actual_rng_bridge_removal_is_detected_while_profile_and_cas_remain(
    tmp_path, monkeypatch, removal
):
    from polisyos.foundry.execute._internal import graph as executor

    store, report, content = _compile(tmp_path / "cas")
    graph = _load(store, report.program_graph_ref, ProgramGraph)
    (node,) = [n for n in graph.nodes if n.mechanism_type == "adaptive_agent"]
    expected = _oracle(17, 17, node.node_id)

    def removed(root_key, treasury, node_id):
        key = root_key
        if removal == "all_salts":
            return key
        salts = (
            (treasury.node_salts[node_id],)
            if removal == "stream_salt"
            else (treasury.stream_salts["default"], treasury.node_salts[node_id])
        )
        for salt in salts:
            key = jax.random.fold_in(key, salt & 0xFFFFFFFF)
            if removal != "high_word":
                key = jax.random.fold_in(key, salt >> 32)
        return key

    monkeypatch.setattr(executor, "_treasury_node_key", removed)
    assert PROFILE in _load(store, report.exec_plan_ref, ExecPlan).notes
    actual = _execute(store, report, content)
    assert not np.array_equal(actual, expected)


@pytest.mark.parametrize("override", [None, 0, 101])
def test_public_execute_cas_snapshot_consumer_uses_bound_profile(tmp_path, override):
    store, report, content = _compile(tmp_path / "cas", seed=17)
    (registry_edge,) = [
        x
        for x in store.get_manifest(report.program_graph_ref).inputs
        if x.role == "registry_bundle"
    ]
    registry_ref = ArtifactRef(
        artifact_id=registry_edge.artifact_id,
        kind="core.registry_bundle",
        media_type="application/json",
        manifest_profile_sha256=registry_edge.manifest_profile_sha256,
    )
    snapshot = put_state_snapshot(store, state=_base_state(), step=0)
    snapshot_ref = StateSnapshotRef(artifact_id=snapshot.artifact_id)
    data_ref = store.put_json(
        DataSnapshot(data_ref=snapshot_ref),
        PutOptions(kind="fabric.data_snapshot", media_type="application/json"),
    )
    bindings = store.put_json(
        FoundryInputBindings(
            data_snapshot_ref=data_ref,
            registry_bundle_ref=registry_ref,
            rules=[],
            bound_state_snapshot_ref=snapshot_ref,
        ),
        PutOptions(kind="foundry.input_bindings", media_type="application/json"),
    )
    config = FoundryExecConfig() if override is None else FoundryExecConfig(seed=override)
    fresh = FileSystemCAS(tmp_path / "cas")
    result = execute_foundry(
        fresh,
        ExecuteRequest(
            exec_plan_ref=ExecPlanRef.model_validate(report.exec_plan_ref.model_dump()),
            input_bindings_ref=FoundryInputBindingsRef(artifact_id=bindings.artifact_id),
            registry_bundle_ref=registry_ref,
            exec_config=config,
            welfare_bound_mode="ex_ante",
        ),
    )
    assert result.ok, result.notes
    simulation = _load(fresh, result.simulation_result_ref, SimulationResult)
    final = load_state_snapshot(fresh, snapshot_ref=simulation.state_snapshot_ref)
    graph = _load(fresh, report.program_graph_ref, ProgramGraph)
    (node,) = [n for n in graph.nodes if n.mechanism_type == "adaptive_agent"]
    np.testing.assert_array_equal(
        np.asarray(final.agents.income),
        _oracle(17 if override is None else override, 17, node.node_id),
    )


def _replace_graph(store, report, graph):
    manifest = store.get_manifest(report.program_graph_ref)
    program_ref = store.put_json(
        graph,
        PutOptions(
            kind=manifest.kind,
            media_type=manifest.media_type,
            schema=manifest.artifact_schema,
            inputs=manifest.inputs,
        ),
    )
    treasury = build_treasury_plan(graph, root_seed=17)
    program_edge = InputRef(
        artifact_id=program_ref.artifact_id,
        role="program_graph",
        manifest_profile_sha256=program_ref.manifest_profile_sha256,
    )
    treasury_ref = store.put_json(
        treasury,
        PutOptions(
            kind="foundry.treasury_plan",
            media_type="application/json",
            schema=SchemaInfo(name="polisyos.foundry.TreasuryPlan", version="1.0"),
            inputs=[program_edge],
        ),
    )
    plan = _load(store, report.exec_plan_ref, ExecPlan)
    plan = plan.model_copy(
        update={
            "program_ref": plan.program_ref.model_copy(
                update={"artifact_id": program_ref.artifact_id}
            )
        }
    )
    inputs = [
        program_edge,
        InputRef(
            artifact_id=treasury_ref.artifact_id,
            role="treasury_plan",
            manifest_profile_sha256=treasury_ref.manifest_profile_sha256,
        ),
    ]
    return _replace_plan(
        store,
        report.model_copy(
            update={"program_graph_ref": program_ref, "treasury_plan_ref": treasury_ref}
        ),
        plan=plan,
        inputs=inputs,
    )


def test_versioned_legacy_mechanism_node_and_graph_storage_permutation(tmp_path):
    store, report, content = _compile(tmp_path / "cas")
    graph = _load(store, report.program_graph_ref, ProgramGraph)
    (node,) = [n for n in graph.nodes if n.mechanism_type == "adaptive_agent"]
    nodes = [
        n.model_copy(update={"node_kind": "mechanism", "op": None})
        if n.node_id == node.node_id
        else n
        for n in graph.nodes
    ]
    # The execution order is unchanged; storage order cannot change a node stream.
    graph = graph.model_copy(update={"nodes": list(reversed(nodes))})
    report = _replace_graph(store, report, graph)
    np.testing.assert_array_equal(
        _execute(FileSystemCAS(tmp_path / "cas"), report, content), _oracle(17, 17, node.node_id)
    )


def test_actual_registered_dispatcher_consumes_versioned_node_seed(tmp_path, monkeypatch):
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    store, report, content = _compile(tmp_path / "cas")
    graph = _load(store, report.program_graph_ref, ProgramGraph)
    (node,) = [n for n in graph.nodes if n.mechanism_type == "adaptive_agent"]
    method_node = node.model_copy(
        update={
            "node_kind": "method",
            "op": None,
            "mechanism_type": None,
            "method_fqn": "adaptive_agent",
            "method_version": "1.0.0",
            "method_params": PARAMS,
            "outputs": [],
        }
    )
    graph = graph.model_copy(
        update={"nodes": [method_node if n.node_id == node.node_id else n for n in graph.nodes]}
    )
    report = _replace_graph(store, report, graph)
    dispatcher = MethodDispatcher.get_instance()
    original = dispatcher.dispatch
    observed = []

    def observe(**kwargs):
        result = original(**kwargs)
        observed.append((kwargs["seed"], result))
        return result

    monkeypatch.setattr(dispatcher, "dispatch", observe)
    _execute(store, report, content)
    seed, result = observed.pop()
    key = jax.random.PRNGKey(17)
    for label in ("stream:default", f"node:{node.node_id}"):
        salt = int(sha256(f"17:{label}".encode()).hexdigest()[:16], 16)
        for word in (salt & 0xFFFFFFFF, salt >> 32):
            key = jax.random.fold_in(key, word)
    _, step_key = jax.random.split(key)
    expected_seed = 0
    for word in np.asarray(jax.random.key_data(step_key), dtype=np.uint32):
        expected_seed = (expected_seed * 1664525 + int(word) + 1013904223) % (2**31 - 1)
    assert seed == (expected_seed or 1) == result.reproducibility.seed
    expected, _ = AdaptiveAgentMechanism(**PARAMS).emit_patches(
        _base_state(), jax.random.PRNGKey(seed)
    )
    np.testing.assert_array_equal(
        np.asarray(result.output["result"]["patches"]["agents.income"][0]["value"]),
        np.asarray(expected["agents.income"][0]["value"]),
    )
    # This registered method returns its own result slot. No state-activation claim is made.
    assert observed == []


def test_native_skipped_prior_draw_cannot_move_versioned_node_stream(tmp_path):
    store, report, content = _compile(tmp_path / "cas")
    graph = _load(store, report.program_graph_ref, ProgramGraph)
    (node,) = [n for n in graph.nodes if n.mechanism_type == "adaptive_agent"]
    payload = from_canonical_bytes(store.get_bytes(node.params_ref))
    payload["schedule"] = {"start_step": 0, "duration_steps": 1}
    payload["params"] = dict(
        PARAMS, action_space={"type": "continuous", "affects": ["agents.reported_income"]}
    )
    prelude_params = store.put_json(
        payload, PutOptions(kind="foundry.mechanism_params", media_type="application/json")
    )
    prelude = node.model_copy(
        update={
            "node_id": "native_prelude",
            "node_kind": "mechanism",
            "op": None,
            "params_ref": prelude_params,
            "outputs": ["agents.reported_income"],
        }
    )
    graph = graph.model_copy(update={"nodes": [prelude, *graph.nodes]})
    report = _replace_graph(store, report, graph)
    plan = _load(store, report.exec_plan_ref, ExecPlan)
    plan = plan.model_copy(update={"order": [prelude.node_id, *plan.order]})
    report = _replace_plan(store, report, plan=plan)
    first = _execute(store, report, content, step=0)
    second = _execute(store, report, content, step=1)
    np.testing.assert_array_equal(first, _oracle(17, 17, node.node_id))
    np.testing.assert_array_equal(first, second)
    legacy = _replace_plan(store, report, plan=plan.model_copy(update={"notes": []}))
    # The same native kernel changes the historical sequential stream when it draws.
    assert not np.array_equal(
        _execute(store, legacy, content, step=0), _execute(store, legacy, content, step=1)
    )
