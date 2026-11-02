"""Selected recipe → fresh canonical compiler → actual runtime qualification."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from polisyos.core.artifacts.store import FileSystemCAS, PutOptions
from polisyos.core.canon import from_canonical_bytes, to_canonical_bytes
from polisyos.foundry.methods.artifacts import (
    ChainArtifact,
    MethodArtifact,
    load_compiled_chain,
    store_chain_artifact,
    store_method_artifact,
)
from polisyos.foundry.methods.compiler.specialization import BackendSpec, build_specialization
from polisyos.foundry.methods.components.composer import MethodComposer, SemanticValidationLevel
from polisyos.foundry.methods.registry import MethodRegistry
from tests._helpers.method_chain import (
    Dependent,
    Independent,
    Left,
    Merge,
    ParameterEcho,
    Required,
    Right,
    Twice,
    register_methods,
)


@pytest.fixture(autouse=True)
def isolated_registry():
    MethodRegistry.reset_instance()
    yield
    MethodRegistry.reset_instance()


def _persist(cas, chain, registry):
    artifacts, refs = {}, {}
    for node_id, method_signature in chain.methods_in_order():
        method_class = registry.get(method_signature.fqn)
        spec = build_specialization(
            method_signature.fqn,
            chain.get_node(node_id).static_params,
            {},
            backend=BackendSpec(platform="cpu", device_count=1, precision="float64"),
            jit_enabled=False,
        )
        artifact = MethodArtifact.from_method(method_class, spec)
        artifacts[node_id] = artifact
        refs[artifact.artifact_id] = store_method_artifact(
            cas, artifact, return_selected_profile=True
        )
    recipe = ChainArtifact.from_chain(chain, artifacts)
    ref = store_chain_artifact(cas, recipe, method_refs=refs, return_selected_profile=True)
    return recipe, ref


def _required_chain(registry):
    composer = MethodComposer(registry=registry)
    composer.add(Dependent.signature.fqn)
    composer.add(Required.signature.fqn)
    composer.add(Independent.signature.fqn)
    return composer.build(validate_semantics=SemanticValidationLevel.STRICT)


@pytest.mark.parametrize("mode", ["sequential", "async"])
def test_selected_recipe_rebuilds_data_adjacency_before_execution(tmp_path, mode):
    registry = register_methods()
    composer = MethodComposer(registry=registry)
    left, right = composer.add(Left.signature.fqn), composer.add(Right.signature.fqn)
    merge, twice = composer.add(Merge.signature.fqn), composer.add(Twice.signature.fqn)
    composer.connect(left, merge, {"left": "left"})
    composer.connect(right, merge, {"right": "right"})
    composer.connect(merge, twice, {"merged": "merged"})
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, chain, registry)
    restored = load_compiled_chain(FileSystemCAS(tmp_path / "cas"), ref, registry=registry)
    assert set(restored.dag.predecessors) == set(restored.dag.nodes)
    assert set(restored.dag.successors) == set(restored.dag.nodes)
    assert restored.dag.predecessors == chain.dag.predecessors
    result = restored.execute_heterogeneous(state={}, registry=registry, executor_mode=mode)
    assert result.final_state["answer"] == 60


@pytest.mark.parametrize("mode", ["sequential", "async"])
def test_selected_recipe_fresh_process_rebuilds_requires_parameters_and_levels(
    tmp_path, mode, record_property
):
    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    chain = _required_chain(registry)
    _, ref = _persist(cas, chain, registry)
    selection = tmp_path / "selection.json"
    selection.write_text(ref.model_dump_json())
    script = """
import asyncio,json,sys
from pathlib import Path
from polisyos.core.artifacts.manifest import ArtifactRef
from polisyos.core.artifacts.store import FileSystemCAS
from polisyos.foundry.methods.artifacts import load_compiled_chain
from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
from polisyos.foundry.methods.components.composer import SemanticValidationLevel
from tests._helpers.method_chain import Required,Dependent,Independent,register_methods
registry=register_methods()
ref=ArtifactRef.model_validate_json(Path(sys.argv[2]).read_text())
chain=load_compiled_chain(FileSystemCAS(sys.argv[1]),ref,registry=registry)
levels=[[chain.signatures[n].fqn for n in group] for group in chain.dag.compute_parallel_levels()]
assert set(levels[0])=={Required.signature.fqn,Independent.signature.fqn}
assert levels[1]==[Dependent.signature.fqn]
assert not chain.bindings
assert chain.validation_context.mode is SemanticValidationLevel.STRICT
result=execute_heterogeneous_chain(chain,state={"sentinel":7},registry=registry,executor_mode=sys.argv[3])
assert result.final_state["answer"]==36
independent_id=next(n for n in chain.execution_order if chain.signatures[n].fqn==Independent.signature.fqn)
assert dict(result.node_results)[independent_id].slot_outputs["independent"]==9
print("E02_CHAIN_RESULT="+json.dumps({"answer":result.final_state["answer"],"levels":levels,"nodes":[str(n) for n in chain.execution_order]}))
"""
    env = dict(os.environ)
    product = Path(__file__).resolve().parents[4]
    if (product / "src").is_dir():
        env["PYTHONPATH"] = str(product / "src") + os.pathsep + str(product)
    else:
        import sysconfig

        from tests._helpers.installed_profile import installed_child_environment

        installed_env = installed_child_environment(
            {
                **env,
                "POLISYOS_INSTALLED_PROFILE_PURELIB": str(
                    Path(sysconfig.get_path("purelib")).resolve(strict=True)
                ),
            }
        )
        assert installed_env is not None
        env = installed_env
    completed = subprocess.run(
        [sys.executable, "-B", "-c", script, str(tmp_path / "cas"), str(selection), mode],
        cwd=product,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    record_property("child_stdout", completed.stdout)
    record_property("child_stderr", completed.stderr)
    record_property("child_exit_code", completed.returncode)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    marker = next(
        line for line in completed.stdout.splitlines() if line.startswith("E02_CHAIN_RESULT=")
    )
    assert json.loads(marker.removeprefix("E02_CHAIN_RESULT="))["answer"] == 36


@pytest.mark.parametrize("corruption", ["edge", "context", "signature", "parameters", "node"])
def test_forged_recipe_cannot_change_executable_meaning(tmp_path, corruption):
    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    chain = _required_chain(registry)
    _, ref = _persist(cas, chain, registry)
    payload = from_canonical_bytes(cas.get_bytes(ref))
    recipe = payload["execution_recipe"]
    if corruption == "edge":
        recipe["predecessors"] = {key: [] for key in recipe["predecessors"]}
    elif corruption == "context":
        recipe["mode"] = "UNESTABLISHED"
    elif corruption == "signature":
        recipe["nodes"][0]["signature_abi_digest"] = "0" * 64
    elif corruption == "parameters":
        recipe["nodes"][0]["dynamic_params"]["unknown"] = 3
    else:
        recipe["nodes"][0]["node_uuid"] = recipe["nodes"][1]["node_uuid"]
    manifest = cas.get_manifest(ref)
    forged = cas.put_bytes(
        to_canonical_bytes(payload),
        PutOptions(
            kind=ref.kind,
            media_type=ref.media_type,
            schema=manifest.artifact_schema,
            producer=manifest.producer,
            inputs=manifest.inputs,
        ),
        return_selected_profile=True,
    )
    with pytest.raises(ValueError):
        load_compiled_chain(FileSystemCAS(tmp_path / "cas"), forged, registry=registry)


def test_requires_abi_drift_cannot_hide_behind_old_method_signature_hash(tmp_path, monkeypatch):
    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, _required_chain(registry), registry)
    monkeypatch.setattr(Dependent, "signature", replace(Dependent.signature, requires=frozenset()))
    with pytest.raises(ValueError, match="source_or_abi"):
        load_compiled_chain(cas, ref, registry=registry)


@pytest.mark.parametrize("mutation", ["replacement", "same_source_code", "sibling_class"])
def test_runtime_operation_replacement_cannot_hide_behind_class_source(
    tmp_path, monkeypatch, mutation
):
    """A source-identical class is insufficient when its actual callable changed."""
    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, _required_chain(registry), registry)
    if mutation == "replacement":
        monkeypatch.setattr(
            Required, "pure_step", staticmethod(lambda state, params: {"value": 777})
        )
    elif mutation == "same_source_code":
        original = Required.pure_step.__code__
        from types import CodeType

        module = compile(
            "def replacement(state, params): return {'value': state['sentinel'] + 777}",
            "<candidate>",
            "exec",
        )
        changed = next(value for value in module.co_consts if isinstance(value, CodeType)).replace(
            co_name=original.co_name,
            co_qualname=original.co_qualname,
            co_filename=original.co_filename,
            co_firstlineno=original.co_firstlineno,
        )
        assert changed.co_filename == original.co_filename
        assert changed.co_qualname == original.co_qualname
        monkeypatch.setattr(Required.pure_step, "__code__", changed)
        assert Required.pure_step({"sentinel": 7}, {}) == {"value": 784}
    else:
        monkeypatch.setattr(Required, "pure_step", staticmethod(Independent.pure_step))
    with pytest.raises(ValueError, match="source_code"):
        load_compiled_chain(cas, ref, registry=registry)


@pytest.mark.parametrize("mode", ["sequential", "async"])
@pytest.mark.parametrize("mutation", ["operation", "registry"])
def test_loaded_recipe_cannot_dispatch_a_later_changed_implementation(
    tmp_path, monkeypatch, mode, mutation
):
    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, _required_chain(registry), registry)
    loaded = load_compiled_chain(cas, ref, registry=registry)
    if mutation == "operation":
        monkeypatch.setattr(
            Required, "pure_step", staticmethod(lambda state, params: {"value": 777})
        )
    else:
        replacement = type(
            "Replacement",
            (),
            {
                "signature": Required.signature,
                "metadata": Required.metadata,
                "pure_step": staticmethod(Required.pure_step),
            },
        )
        registry.register(replacement, override=True)
    with pytest.raises(ValueError, match="implementation"):
        loaded.execute_heterogeneous(state={"sentinel": 7}, registry=registry, executor_mode=mode)


@pytest.mark.parametrize("mode", ["sequential", "async"])
def test_selected_recipe_rechecks_each_actual_node_before_dispatch(tmp_path, monkeypatch, mode):
    from polisyos.foundry.methods.backends.async_chain_executor import AsyncChainExecutionError
    from polisyos.foundry.methods.backends.chain_executor import execute_heterogeneous_chain
    from polisyos.foundry.methods.backends.dispatch import MethodDispatcher

    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, _required_chain(registry), registry)
    loaded = load_compiled_chain(cas, ref, registry=registry)
    dispatcher = MethodDispatcher(enable_runtime_selection=False)
    original, calls = dispatcher.dispatch, []

    def observe(*args, **kwargs):
        calls.append(kwargs["signature"].fqn)
        result = original(*args, **kwargs)
        if kwargs["signature"].fqn == Required.signature.fqn:
            monkeypatch.setattr(
                Dependent, "pure_step", staticmethod(lambda state, params: {"answer": 777})
            )
        return result

    monkeypatch.setattr(dispatcher, "dispatch", observe)
    with pytest.raises((ValueError, AsyncChainExecutionError), match="implementation"):
        execute_heterogeneous_chain(
            loaded,
            state={"sentinel": 7},
            registry=registry,
            dispatcher=dispatcher,
            executor_mode=mode,
        )
    assert Required.signature.fqn in calls
    assert Dependent.signature.fqn not in calls


@pytest.mark.parametrize(
    "override,expected", [(None, 40), ({"scale": 3}, 60), ({"window": 30, "scale": 4}, 120)]
)
def test_persisted_authored_parameters_reach_actual_runtime(tmp_path, override, expected):
    registry = register_methods()
    composer = MethodComposer(registry=registry)
    node = composer.add(ParameterEcho.signature.fqn, window=20, scale=2)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, chain, registry)
    restored = load_compiled_chain(FileSystemCAS(tmp_path / "cas"), ref, registry=registry)
    assert restored.get_node(node.id).static_params == {"window": 20}
    for mode in ("sequential", "async"):
        result = restored.execute_heterogeneous(
            state={},
            registry=registry,
            executor_mode=mode,
            params_per_node=None if override is None else {node.id: override},
        )
        assert result.final_state["answer"] == expected


def test_finite_fractional_parameter_uses_declared_recipe_canonical_profile(tmp_path):
    registry = register_methods()
    composer = MethodComposer(registry=registry)
    node = composer.add(ParameterEcho.signature.fqn, window=20, scale=0.5)
    chain = composer.build(validate_semantics=SemanticValidationLevel.STRICT)
    cas = FileSystemCAS(tmp_path / "cas")
    _, ref = _persist(cas, chain, registry)
    loaded = load_compiled_chain(FileSystemCAS(tmp_path / "cas"), ref, registry=registry)
    assert loaded.get_node(node.id).params["scale"] == 0.5
    assert loaded.execute_heterogeneous(state={}, registry=registry).final_state["answer"] == 10


def test_legacy_recipe_stays_readable_but_not_executable(tmp_path):
    registry = register_methods()
    cas = FileSystemCAS(tmp_path / "cas")
    recipe, _ = _persist(cas, _required_chain(registry), registry)
    legacy = replace(recipe, execution_recipe=None)
    ref = store_chain_artifact(cas, legacy, return_selected_profile=True)
    assert from_canonical_bytes(cas.get_bytes(ref))["schema_version"] == "1.0.0"
    with pytest.raises(ValueError, match="historical_chain_recipe_not_executable"):
        load_compiled_chain(cas, ref, registry=registry)
