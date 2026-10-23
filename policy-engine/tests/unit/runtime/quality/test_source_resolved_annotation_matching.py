from __future__ import annotations

import ast
import functools
import importlib
import importlib.util
import json
import os
import sys
import types
import typing
from pathlib import Path

import pytest

from polisyos.core.artifacts import store as store_module

STORE_SOURCE = Path(store_module.__file__).resolve()
REPO_ROOT = STORE_SOURCE.parents[4]
STORE_RELATIVE = STORE_SOURCE.relative_to(REPO_ROOT).as_posix()


def _load_candidate_ledger() -> types.ModuleType:
    candidate_path_value = os.environ.get("N11_ANNOTATION_CANDIDATE_SOURCE")
    if candidate_path_value is None:
        return importlib.import_module("polisyos.runtime.quality.confidence_ledger")
    candidate_path = Path(candidate_path_value).resolve()
    spec = importlib.util.spec_from_file_location(
        "n11_annotation_candidate_confidence_ledger",
        candidate_path,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def candidate_ledger() -> types.ModuleType:
    return _load_candidate_ledger()


def test_candidate_loader_defaults_to_canonical_runtime_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The repository test works without a candidate-overlay environment variable."""

    monkeypatch.delenv("N11_ANNOTATION_CANDIDATE_SOURCE", raising=False)
    expected = importlib.import_module("polisyos.runtime.quality.confidence_ledger")
    assert _load_candidate_ledger() is expected


def _transactional_method_nodes() -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    tree = ast.parse(STORE_SOURCE.read_bytes(), filename=str(STORE_SOURCE))
    owner = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "FileSystemCAS"
    )
    selected = []
    for node in owner.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if isinstance(target, ast.Name) and target.id in {
                "_transactional_read",
                "_transactional_write",
            }:
                selected.append(node)
                break
    return tuple(selected)


def _source_annotation_members(
    candidate_ledger: types.ModuleType,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[object, ...]:
    parameters = [*node.args.posonlyargs, *node.args.args]
    assert len(parameters) >= 2
    assert parameters[1].annotation is not None
    tree = ast.parse(STORE_SOURCE.read_bytes(), filename=str(STORE_SOURCE))
    members = candidate_ledger._source_annotation_members(
        parameters[1].annotation,
        tree=tree,
        module=store_module,
        module_name=store_module.__name__,
    )
    assert members is not None
    return members


def _closure_cell(function: types.FunctionType, name: str) -> object:
    assert function.__closure__ is not None
    index = function.__code__.co_freevars.index(name)
    return function.__closure__[index].cell_contents


def _cell(value: object) -> object:
    return (lambda item: lambda: item)(value).__closure__[0]


def _function_with_cell(
    function: types.FunctionType,
    name: str,
    value: object,
) -> types.FunctionType:
    assert function.__closure__ is not None
    cells = list(function.__closure__)
    cells[function.__code__.co_freevars.index(name)] = _cell(value)
    rebound = types.FunctionType(
        function.__code__,
        function.__globals__,
        function.__name__,
        function.__defaults__,
        tuple(cells),
    )
    rebound.__module__ = function.__module__
    rebound.__qualname__ = function.__qualname__
    rebound.__doc__ = function.__doc__
    rebound.__kwdefaults__ = function.__kwdefaults__
    rebound.__annotations__ = dict(function.__annotations__)
    rebound.__dict__.update(function.__dict__)
    return rebound


def _store_manifest(candidate_ledger: types.ModuleType) -> tuple[str, bool]:
    return candidate_ledger._loaded_code_manifest(
        REPO_ROOT,
        ((store_module.__name__, STORE_RELATIVE),),
    )


def test_all_source_declared_transactional_file_system_cas_wrappers_match(
    candidate_ledger: types.ModuleType,
) -> None:
    """The source-derived matcher accepts every actual wrapped CAS reader/writer."""

    methods = _transactional_method_nodes()
    assert len(methods) == 17
    manifest, consistent = _store_manifest(candidate_ledger)
    payload = json.loads(manifest)
    slots = payload[store_module.__name__]["loader_owned_callable_slots"]
    expected_slots = {f"FileSystemCAS.{node.name}" for node in methods}
    assert expected_slots <= set(slots)
    assert all(slots[name]["matches_loader_slot"] is True for name in expected_slots)
    assert consistent is True


def test_resolved_annotation_matching_is_identity_based_and_union_order_independent(
    candidate_ledger: types.ModuleType,
) -> None:
    """Source-bound member identity accepts the two real union encodings only."""

    node = next(
        node
        for node in _transactional_method_nodes()
        if len(_source_annotation_members(candidate_ledger, node)) > 1
    )
    members = _source_annotation_members(candidate_ledger, node)
    expected = candidate_ledger._SourceResolvedAnnotation(members)

    def terminal() -> None:
        return None

    union_alias = typing.Union
    typing_union = union_alias[members]
    pep604_union = functools.reduce(lambda left, right: left | right, members)
    reverse_pep604_union = functools.reduce(lambda left, right: left | right, reversed(members))
    assert candidate_ledger._source_capture_value_matches(typing_union, expected, terminal=terminal)
    assert candidate_ledger._source_capture_value_matches(pep604_union, expected, terminal=terminal)
    assert candidate_ledger._source_capture_value_matches(
        reverse_pep604_union, expected, terminal=terminal
    )

    first_member = members[0]
    decoy_member = type(
        type.__getattribute__(first_member, "__name__"),
        (),
        {"__module__": type.__getattribute__(first_member, "__module__")},
    )
    wrong_members = (decoy_member, *members[1:])
    wrong_union = union_alias[wrong_members]
    assert not candidate_ledger._source_capture_value_matches(
        wrong_union, expected, terminal=terminal
    )
    assert not candidate_ledger._source_capture_value_matches(
        " | ".join(type.__getattribute__(member, "__name__") for member in members),
        expected,
        terminal=terminal,
    )
    assert not candidate_ledger._source_capture_value_matches(object(), expected, terminal=terminal)

    singleton = candidate_ledger._SourceResolvedAnnotation((first_member,))
    assert candidate_ledger._source_capture_value_matches(
        first_member, singleton, terminal=terminal
    )
    assert not candidate_ledger._source_capture_value_matches(
        decoy_member, singleton, terminal=terminal
    )


def test_wrong_live_annotation_member_and_import_binding_refuse(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-named replacement class cannot satisfy source-derived closure evidence."""

    node = next(
        node
        for node in _transactional_method_nodes()
        if any(
            member is store_module.ArtifactRef
            for member in _source_annotation_members(candidate_ledger, node)
        )
    )
    members = _source_annotation_members(candidate_ledger, node)
    method = getattr(store_module.FileSystemCAS, node.name)
    assert isinstance(method, types.FunctionType)
    live_annotation = _closure_cell(method, "selector_annotation")
    actual_members = typing.get_args(live_annotation)
    assert len(actual_members) == len(members)

    expected = candidate_ledger._SourceResolvedAnnotation(members)
    first = next(member for member in members if member is store_module.ArtifactRef)
    decoy_member = type(
        type.__getattribute__(first, "__name__"),
        (),
        {"__module__": type.__getattribute__(first, "__module__")},
    )
    changed_members = tuple(
        decoy_member if member is first else member for member in actual_members
    )
    union_alias = typing.Union
    if typing.get_origin(live_annotation) is union_alias:
        wrong_annotation = union_alias[changed_members]
    elif typing.get_origin(live_annotation) is types.UnionType:
        wrong_annotation = functools.reduce(
            lambda left, right: left | right,
            changed_members,
        )
    else:
        pytest.fail("fixture did not expose a supported runtime union representation")

    assert not candidate_ledger._source_capture_value_matches(
        wrong_annotation, expected, terminal=method.__wrapped__
    )
    rebound = _function_with_cell(method, "selector_annotation", wrong_annotation)
    with monkeypatch.context() as mutation:
        mutation.setattr(store_module.FileSystemCAS, node.name, rebound)
        _manifest, consistent = _store_manifest(candidate_ledger)
        assert consistent is False

    same_named_rebound = type(
        "ArtifactRef",
        (),
        {"__module__": store_module.__name__},
    )
    with monkeypatch.context() as mutation:
        mutation.setattr(store_module, "ArtifactRef", same_named_rebound)
        _manifest, consistent = _store_manifest(candidate_ledger)
        assert consistent is False
