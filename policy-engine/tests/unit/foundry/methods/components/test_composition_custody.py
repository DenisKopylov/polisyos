"""Behavioral C60 witnesses; synthetic methods establish mechanics only."""

from __future__ import annotations

import asyncio
import itertools
import json
import threading
from dataclasses import replace
from typing import ClassVar

import pytest

from polisyos.foundry.methods.backends.chain_executor import (
    execute_heterogeneous_chain,
    execute_heterogeneous_chain_async,
)
from polisyos.foundry.methods.backends.checkpointing import (
    ChainCheckpoint,
    CheckpointDigestMismatchError,
    CheckpointingChainExecutor,
)
from polisyos.foundry.methods.base import (
    ComplexityClass,
    ComputeBackend,
    FidelityLevel,
    MethodMetadata,
    MethodSignature,
    ParameterSpec,
    SlotSpec,
    SlotType,
    Unit,
)
from polisyos.foundry.methods.components.composer import (
    MethodComposer,
    SemanticValidationLevel,
    ValidationContext,
)
from polisyos.foundry.methods.components.linker import LinkerConfig, SlotLinker
from polisyos.foundry.methods.components.semantic_validator import CrossMethodValidator
from polisyos.foundry.methods.exceptions import SlotConnectionError
from polisyos.foundry.methods.registry import MethodRegistry


@pytest.fixture(autouse=True)
def registry():
    """Isolate real synthetic methods from builtin discovery."""
    MethodRegistry.reset_instance()
    yield MethodRegistry.get_instance()
    MethodRegistry.reset_instance()


def slot(name, contract=None, *, dimension="custody", vector=False):
    return SlotSpec(
        name=name,
        slot_type=SlotType.VECTOR if vector else SlotType.SCALAR,
        unit=Unit(dimension, "unit"),
        contract_id=contract,
        shape=(2,) if vector else (),
    )


def method(
    registry,
    name,
    *,
    inputs=(),
    outputs=(),
    parameters=(),
    requires=(),
    family="fixture",
    step=None,
):
    signature = MethodSignature(
        name=name,
        namespace="tests.c60",
        version="1.0.0",
        input_slots=frozenset(inputs),
        output_slots=frozenset(outputs),
        parameters=parameters,
        requires=frozenset(requires),
        family=family,
        fidelity=FidelityLevel.LOW,
        complexity=ComplexityClass.O_1,
        backend=ComputeBackend.NUMPY,
        supports_jit=False,
        supports_vmap=False,
        supports_grad=False,
    )

    class SyntheticMethod:
        signature: ClassVar[MethodSignature]
        metadata = MethodMetadata(description="C60 synthetic mechanics witness", tags=frozenset())

        @staticmethod
        def pure_step(state, params):
            return step(state, params) if step is not None else None

    SyntheticMethod.signature = signature
    registry.register(SyntheticMethod, override=True)
    return signature.fqn


def merge_chain(
    registry,
    *,
    route="explicit",
    missing=False,
    reverse=False,
    level=SemanticValidationLevel.STRICT,
):
    left_fqn = method(
        registry, "left_source", outputs=(slot("x", "left"),), step=lambda _s, _p: {"x": 10}
    )
    right_fqn = method(
        registry, "right_source", outputs=(slot("y", "right"),), step=lambda _s, _p: {"y": 30}
    )
    merge_fqn = method(
        registry,
        "merge",
        inputs=(slot("left", "left"), slot("right", "right")),
        outputs=(slot("merged"),),
        step=lambda state, _params: {"merged": state["left"] + state["right"]},
    )
    composer = MethodComposer(registry=registry, linker=SlotLinker(LinkerConfig.strict()))
    order = (right_fqn, left_fqn) if reverse else (left_fqn, right_fqn)
    nodes = {fqn: composer.add(fqn) for fqn in order}
    target = composer.add(merge_fqn)
    for fqn, source, dest in ((left_fqn, "x", "left"), (right_fqn, "y", "right")):
        if missing and dest == "right":
            continue
        composer.connect(nodes[fqn], target, {source: dest} if route == "explicit" else None)
    return composer.build(validate_semantics=level)


@pytest.mark.parametrize("route", ["auto", "explicit"])
@pytest.mark.parametrize("reverse", [False, True])
def test_joint_strict_dag_executes_independent_merge_value(registry, route, reverse, tmp_path):
    """B45/B48: union of two valid edges executes 10+30 despite name/ID order."""
    chain = merge_chain(registry, route=route, reverse=reverse)
    initial = {"left": -100, "right": -100}
    sequential = execute_heterogeneous_chain(chain, state=initial, registry=registry)
    asynchronous = asyncio.run(
        execute_heterogeneous_chain_async(chain, state=initial, registry=registry)
    )
    checkpointed = CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry)
    checkpointed.execute(chain, initial_state=initial)
    # Reopen an actual partial prefix, then use a fresh consumer instance.
    prefix = ChainCheckpoint.load(sorted(tmp_path.glob("*_0001_*.json"))[0])
    resumed = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state=initial, checkpoint=prefix
    )
    for result in (sequential, asynchronous, resumed):
        assert result.final_state["merged"] == 40, "joint DAG merge value"
        assert result.warnings == chain.warnings
        assert result.validation_context == chain.validation_context
    assert [value.output for _, value in resumed.node_results] == [
        value.output for _, value in sequential.node_results
    ]
    assert prefix.history_complete


@pytest.mark.parametrize("route", ["auto", "explicit"])
def test_joint_strict_dag_refuses_missing_input_at_final_gate(registry, route):
    """The positive builder route must not erase final required-slot refusal."""
    with pytest.raises(ValueError, match="Unconnected required inputs"):
        merge_chain(registry, route=route, missing=True)


@pytest.mark.parametrize("field,value", [("ruleset", "unknown@9"), ("schema_version", 9)])
def test_context_rejects_unknown_rule_or_schema_even_when_warning_hash_agrees(
    registry, tmp_path, field, value
):
    chain = merge_chain(registry)
    assert chain.validation_context is not None
    invalid = replace(chain, validation_context=replace(chain.validation_context, **{field: value}))
    with pytest.raises(CheckpointDigestMismatchError, match="validation context"):
        CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
            invalid, initial_state={}
        )


def test_off_restamped_strict_replays_the_actual_compiler(registry, tmp_path):
    """A clean hash cannot launder an OFF-built ordering violation as STRICT."""
    sensitivity = method(registry, "sensitivity", family="sensitivity")
    composer = MethodComposer(registry=registry)
    composer.add(sensitivity)
    off = composer.build(validate_semantics=SemanticValidationLevel.OFF)
    assert off.validation_context is not None
    forged = replace(
        off,
        validation_context=ValidationContext.create(
            mode=SemanticValidationLevel.STRICT, warnings=off.warnings
        ),
    )
    with pytest.raises(CheckpointDigestMismatchError, match="validation context"):
        CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
            forged, initial_state={}
        )
    # OFF is an explicit limitation; a genuine OFF checkpoint remains OFF.
    executor = CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry)
    executor.execute(off, initial_state={})
    reopened = ChainCheckpoint.load(next(tmp_path.glob("*.json")))
    resumed = CheckpointingChainExecutor(registry=registry).execute(
        off, initial_state={}, checkpoint=reopened
    )
    assert resumed.validation_context.mode is SemanticValidationLevel.OFF


@pytest.mark.parametrize("prefix", [0, 2])
@pytest.mark.parametrize(
    "mutation", ["missing", "warnings", "mode", "ruleset", "diagnostic_digest", "schema"]
)
def test_reopened_context_cannot_erase_limitation(registry, tmp_path, prefix, mutation):
    chain = merge_chain(registry, level=SemanticValidationLevel.WARN)
    executor = CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry)
    executor.execute(chain, initial_state={})
    checkpoint = ChainCheckpoint.load(next(tmp_path.glob(f"*_{prefix:04d}_*.json")))
    assert checkpoint.validation_context is not None
    if mutation == "missing":
        checkpoint.validation_context = None
    elif mutation == "warnings":
        checkpoint.composition_warnings = ["invented warning"]
    else:
        key, value = {
            "mode": ("mode", "off"),
            "ruleset": ("ruleset", "unknown@1"),
            "diagnostic_digest": ("diagnostics_digest", "0" * 64),
            "schema": ("schema_version", 2),
        }[mutation]
        checkpoint.validation_context[key] = value
    with pytest.raises(CheckpointDigestMismatchError, match="validation|diagnostic"):
        CheckpointingChainExecutor(registry=registry).execute(
            chain, initial_state={}, checkpoint=checkpoint
        )


@pytest.mark.parametrize(
    "sequence,offending",
    [
        (("estimate", "sensitivity", "estimate"), None),
        (("sensitivity", "estimate", "sensitivity"), 0),
    ],
)
def test_repeated_real_occurrences_retain_identity_and_static_parameters(
    registry, sequence, offending
):
    fqns = {
        kind: method(
            registry,
            kind,
            family="estimation" if kind == "estimate" else kind,
            parameters=(ParameterSpec("window", 7, is_static=True),),
        )
        for kind in set(sequence)
    }
    composer = MethodComposer(registry=registry)
    nodes = [composer.add(fqns[kind], window=20 + index) for index, kind in enumerate(sequence)]
    # Explicit empty data edges preserve the declared order without slot shortcuts.
    for first, second in itertools.pairwise(nodes):
        composer.connect(first, second, {})
    chain = composer.build(validate_semantics=SemanticValidationLevel.WARN)
    report = CrossMethodValidator(strict=True).validate_chain(chain)
    issues = [issue for issue in report.errors if issue.category == "ordering"]
    if offending is None:
        assert not issues, "early real prerequisite must not be replaced by last FQN"
        composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    else:
        assert len(issues) == 1, "early invalid dependent must remain visible"
        assert issues[0].target_node_id == nodes[offending].id
        assert issues[0].target_index == offending
        assert chain.get_node(issues[0].target_node_id).static_params["window"] == 20
        with pytest.raises(ValueError, match="semantic validation"):
            composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    result = execute_heterogeneous_chain(chain, state={}, registry=registry)
    assert [node_id for node_id, _ in result.node_results] == [node.id for node in nodes]
    if offending is not None:
        assert any(
            f"node={nodes[offending].id}, index={offending}" in warning
            for warning in result.warnings
        ), "executed diagnostic retains offending occurrence"


def test_finite_typed_lowering_matches_independent_exhaustive_assignments():
    """B47: exhaust the declared typed fixture universe, not arbitrary graphs."""
    # Frozen facts: two units, scalar/vector shape, and None/A/B contracts.
    profiles = (
        (None, "u", False),
        ("A", "u", False),
        ("B", "u", False),
        (None, "v", False),
        (None, "u", True),
        ("B", "u", True),
    )
    graphs = set()
    cases = 0
    for facts in itertools.product(profiles, repeat=4):
        sources, targets = facts[:2], facts[2:]
        allowed = {
            (i, j)
            for i, src in enumerate(sources)
            for j, tgt in enumerate(targets)
            if src[1:] == tgt[1:] and (src[0] is None or tgt[0] is None or src[0] == tgt[0])
        }
        expected = any(
            all((assignment[j], j) in allowed for j in range(2))
            for assignment in itertools.permutations(range(2))
        )
        graphs.add(tuple(sorted(allowed)))
        source_slots = tuple(
            slot(f"s{i}", fact[0], dimension=fact[1], vector=fact[2])
            for i, fact in enumerate(sources)
        )
        target_slots = tuple(
            slot(f"t{j}", fact[0], dimension=fact[1], vector=fact[2])
            for j, fact in enumerate(targets)
        )

        def signature(name, inputs=(), outputs=()):
            return MethodSignature(
                name=name,
                namespace="tests.c60",
                version="1.0.0",
                input_slots=frozenset(inputs),
                output_slots=frozenset(outputs),
                parameters=(),
                fidelity=FidelityLevel.LOW,
                complexity=ComplexityClass.O_1,
            )

        producer, consumer = (
            signature("producer", outputs=source_slots),
            signature("consumer", inputs=target_slots),
        )
        linker = SlotLinker(LinkerConfig.strict())
        # Independently reconcile every lowered edge before testing matching.
        actual_edges = set()
        for i, j in itertools.product(range(2), repeat=2):
            try:
                linker._link_composition_edge(producer, consumer, {f"s{i}": f"t{j}"})
            except Exception as exc:
                from polisyos.foundry.methods.exceptions import (
                    ShapeMismatchError,
                    UnitMismatchError,
                )

                assert isinstance(exc, (SlotConnectionError, ShapeMismatchError, UnitMismatchError))
            else:
                actual_edges.add((i, j))
        assert actual_edges == allowed, "typed lowering differs from frozen fixture facts"
        try:
            result = linker.link(producer, consumer)
        except SlotConnectionError:
            actual = False
        else:
            actual = not result.unconnected_inputs
            assert len({binding.source_slot for binding in result.bindings}) == len(result.bindings)
        assert actual == expected, "bounded exhaustive assignment existence"
        cases += 1
    assert cases == len(profiles) ** 4
    print(
        json.dumps(
            {
                "typed_cases": cases,
                "unique_lowered_graphs": len(graphs),
                "profile_count": len(profiles),
                "source_slots": 2,
                "target_slots": 2,
                "authority": "bounded feasibility only",
            }
        )
    )


def test_requires_execution_barrier_keeps_parallel_sibling_and_fresh_prefix(registry, tmp_path):
    """B43: execute the effective graph with independent event/reachability oracles."""
    required_started, sibling_started = threading.Event(), threading.Event()
    required_finished = threading.Event()

    def required_step(_state, _params):
        required_started.set()
        assert sibling_started.wait(3), "independent sibling did not execute concurrently"
        required_finished.set()
        return {"required_value": 12}

    def sibling_step(_state, _params):
        sibling_started.set()
        assert required_started.wait(3), "prerequisite did not execute concurrently"
        return {"sibling_value": 5}

    def dependent_step(state, _params):
        assert required_finished.is_set(), "dependent executed before required event"
        return {"answer": state["required_value"] * 3}

    required = method(registry, "required", outputs=(slot("required_value"),), step=required_step)
    sibling = method(registry, "sibling", outputs=(slot("sibling_value"),), step=sibling_step)
    dependent = method(
        registry, "dependent", outputs=(slot("answer"),), requires=(required,), step=dependent_step
    )
    composer = MethodComposer(registry=registry)
    dep, req, sib = composer.add(dependent), composer.add(required), composer.add(sibling)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    # Expected reachability is independently declared from fixture facts.
    result = asyncio.run(execute_heterogeneous_chain_async(chain, state={}, registry=registry))
    assert chain.dag.predecessors[dep.id] == frozenset({req.id})
    assert chain.dag.predecessors[sib.id] == frozenset()
    assert result.final_state["answer"] == 36, "requires-edge executed value"
    # The sequential producer does not need the concurrency rendezvous anymore.
    CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
        chain, initial_state={}
    )
    prefix = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    resumed = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state={}, checkpoint=prefix
    )
    assert resumed.final_state["answer"] == 36
    assert [node for node, _ in resumed.node_results] == list(chain.execution_order)
    invalid = replace(
        chain, dag=replace(chain.dag, predecessors={**chain.dag.predecessors, dep.id: frozenset()})
    )
    with pytest.raises(CheckpointDigestMismatchError, match="validation|execution identity"):
        CheckpointingChainExecutor(registry=registry).execute(
            invalid, initial_state={}, checkpoint=prefix
        )


@pytest.mark.parametrize("overrides,expected", [({}, 51), ({"scale": 3}, 71)])
def test_real_static_dynamic_override_and_runtime_seed_survive_fresh_resume(
    registry, tmp_path, overrides, expected
):
    """B44: window=20 must not fall back to 7 in any real execution consumer."""
    observations = []

    def payload_step(state, params):
        observed = (params["window"], params["scale"], params["__seed__"])
        observations.append(observed)
        return {"value": state["initial"] + params["window"] * params["scale"] + params["__seed__"]}

    start = method(registry, "start", outputs=(slot("start"),), step=lambda _s, _p: {"start": 1})
    payload = method(
        registry,
        "payload",
        outputs=(slot("value"),),
        requires=(start,),
        parameters=(ParameterSpec("window", 7, is_static=True), ParameterSpec("scale", 2)),
        step=payload_step,
    )
    composer = MethodComposer(registry=registry)
    composer.add(start)
    node = composer.add(payload, window=20)
    with pytest.raises(ValueError, match="Unknown parameters"):
        composer.add(payload, unknown_static=9)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    params = {node.id: overrides}
    state, seed = {"initial": 4}, 7
    sequential = execute_heterogeneous_chain(
        chain, state=state, registry=registry, seed=seed, params_per_node=params
    )
    asynchronous = asyncio.run(
        execute_heterogeneous_chain_async(
            chain, state=state, registry=registry, seed=seed, params_per_node=params
        )
    )
    CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
        chain, initial_state=state, seed=seed, params_per_node=params
    )
    prefix = ChainCheckpoint.load(next(tmp_path.glob("*_0000_*.json")))
    resumed = CheckpointingChainExecutor(registry=registry).execute(
        chain, initial_state=state, seed=seed, params_per_node=params, checkpoint=prefix
    )
    for result in (sequential, asynchronous, resumed):
        assert result.final_state["value"] == expected, "nondefault static numerical output"
        assert result.node_results[-1][1].reproducibility.seed == seed
    assert observations == [(20, overrides.get("scale", 2), 7)] * 4, "actual node-observed payload"
    assert [item.output for _, item in resumed.node_results] == [
        item.output for _, item in sequential.node_results
    ]


def test_async_partial_error_retains_real_compiler_limitation(registry):
    """The partial result remains terminal and carries aggregate context."""
    from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutionError

    def failure(_state, _params):
        raise ValueError("intentional partial-level failure")

    good = method(
        registry,
        "good",
        outputs=(slot("good"),),
        family="sensitivity",
        step=lambda _s, _p: {"good": 1},
    )
    bad = method(registry, "bad", step=failure)
    composer = MethodComposer(registry=registry)
    good_node, bad_node = composer.add(good), composer.add(bad)
    chain = composer.build(validate_semantics=SemanticValidationLevel.WARN)
    with pytest.raises(AsyncChainExecutionError) as raised:
        asyncio.run(execute_heterogeneous_chain_async(chain, state={}, registry=registry))
    partial = raised.value.partial_result
    assert partial is not None
    assert [node for node, _ in partial.node_results] == [good_node.id]
    assert raised.value.node_errors[0].node_id == bad_node.id
    assert partial.warnings == chain.warnings and partial.warnings
    assert partial.validation_context == chain.validation_context


def test_real_ray_result_retains_compiler_warning_when_backend_is_available(registry):
    """A missing Ray backend is an explicit skip, never a substitute witness."""
    ray = pytest.importorskip("ray")
    from polisyos.foundry.methods.backends.ray_chain_executor import RayChainExecutor

    fqn = method(
        registry,
        "ray_warning",
        outputs=(slot("ray_value"),),
        family="sensitivity",
        step=lambda _s, _p: {"ray_value": 17},
    )
    composer = MethodComposer(registry=registry)
    composer.add(fqn)
    chain = composer.build(validate_semantics=SemanticValidationLevel.WARN)
    started_here = not ray.is_initialized()
    if started_here:
        ray.init(num_cpus=2, include_dashboard=False)
    try:
        result = RayChainExecutor(registry=registry).execute(chain, initial_state={})
        assert result.final_state["ray_value"] == 17
        assert result.warnings == chain.warnings and result.warnings
        assert result.validation_context == chain.validation_context
    finally:
        if started_here:
            ray.shutdown()


@pytest.mark.parametrize("route", ["explicit", "auto"])
@pytest.mark.parametrize("consumer", ["sequential", "async", "checkpoint"])
def test_replaced_binding_set_refuses_at_actual_execution_boundary(
    registry, route, consumer, tmp_path
):
    """A finalized plan cannot bypass the shared gate by replacing its bindings."""
    chain = merge_chain(registry, route=route)
    invalid = replace(chain, bindings=chain.bindings[:1])

    def consume_invalid_plan() -> None:
        if consumer == "sequential":
            execute_heterogeneous_chain(invalid, state={}, registry=registry)
        elif consumer == "async":
            asyncio.run(execute_heterogeneous_chain_async(invalid, state={}, registry=registry))
        else:
            CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry).execute(
                invalid, initial_state={}
            )

    with pytest.raises(
        (ValueError, CheckpointDigestMismatchError), match="validation replay|validation context"
    ):
        consume_invalid_plan()


def test_live_self_hash_cannot_remove_real_compiler_warning(registry, tmp_path):
    """A warning digest computed from the forgery is not compiler provenance."""
    fqn = method(registry, "limited", family="sensitivity")
    composer = MethodComposer(registry=registry)
    composer.add(fqn)
    chain = composer.build(validate_semantics=SemanticValidationLevel.WARN)
    assert chain.warnings
    executor = CheckpointingChainExecutor(checkpoint_dir=tmp_path, registry=registry)
    executor.execute(chain, initial_state={})
    reopened = ChainCheckpoint.load(next(tmp_path.glob("*.json")))
    forged = replace(
        chain,
        warnings=(),
        validation_context=ValidationContext.create(mode=SemanticValidationLevel.WARN, warnings=()),
    )
    with pytest.raises(CheckpointDigestMismatchError, match="validation context"):
        CheckpointingChainExecutor(registry=registry).execute(
            forged, initial_state={}, checkpoint=reopened
        )
    assert reopened.composition_warnings == list(chain.warnings)


@pytest.mark.parametrize("error_kind", ["optional_missing", "internal_initialization"])
def test_fresh_async_lazy_import_preserves_real_error_identity(error_kind):
    """B42: an optional miss must not swallow an internal initialization error."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    script = r"""
import importlib.abc
import sys
from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
name = "polisyos.foundry.methods.backends.async_chain_executor"
assert name not in sys.modules, "async owner was imported eagerly"
kind = sys.argv[1]
class BrokenOwner(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == name:
            if kind == "optional_missing":
                raise ModuleNotFoundError("missing optional c60 backend", name="c60_optional_backend")
            raise RuntimeError("c60 internal initialization failure")
sys.meta_path.insert(0, BrokenOwner())
try:
    execute_heterogeneous_chain(None, state={}, executor_mode="async")
except ModuleNotFoundError as exc:
    assert kind == "optional_missing" and exc.name == "c60_optional_backend", "wrong optional dependency identity"
except RuntimeError as exc:
    assert kind == "internal_initialization" and str(exc) == "c60 internal initialization failure", "internal initialization was masked"
else:
    raise AssertionError("missing/internal import failure was silently converted to availability")
"""
    product = Path(__file__).resolve().parents[5]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(product / "src") + os.pathsep + env.get("PYTHONPATH", "")
    run = subprocess.run(
        [sys.executable, "-c", script, error_kind],
        cwd=product,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert run.returncode == 0, f"fresh lazy import error identity: {run.stdout}\n{run.stderr}"
