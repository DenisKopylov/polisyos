from __future__ import annotations

import ast
import dataclasses
import importlib
import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest

from polisyos.core.artifacts._integrity_ops import (
    ArtifactBoundedManifestRead,
    ArtifactStoreReadUsage,
)
from polisyos.foundry.methods.base import MethodMetadata


def _load_candidate_ledger() -> types.ModuleType:
    candidate_path_value = os.environ.get("N11_DATACLASS_CANDIDATE_SOURCE")
    if candidate_path_value is None:
        return importlib.import_module("polisyos.runtime.quality.confidence_ledger")
    candidate_path = Path(candidate_path_value).resolve()
    spec = importlib.util.spec_from_file_location(
        "n11_dataclass_candidate_confidence_ledger",
        candidate_path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def candidate_ledger() -> types.ModuleType:
    return _load_candidate_ledger()


def _supports_source_dataclass(
    candidate_ledger: types.ModuleType,
    cls: type[object],
    *,
    owner_module: types.ModuleType | None = None,
) -> bool:
    module = owner_module or importlib.import_module(cls.__module__)
    module_path = Path(module.__file__).resolve()
    repo_root = (
        module_path.parents[4] if cls.__module__.startswith("polisyos.") else module_path.parent
    )
    relative = module_path.relative_to(repo_root)
    tree = ast.parse(module_path.read_bytes(), filename=str(module_path))
    statement = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls.__name__
    )
    return candidate_ledger._source_python_dataclass_binding_supported(
        repo_root,
        cls.__module__,
        cls.__name__,
        relative,
        tree,
        statement,
    )


def _direct_source_route(
    candidate_ledger: types.ModuleType,
    cls: type[object],
) -> tuple[str, str, str | None] | None:
    module = importlib.import_module(cls.__module__)
    module_path = Path(module.__file__).resolve()
    repo_root = module_path.parents[4]
    return candidate_ledger._source_module_direct_binding_route(
        repo_root,
        cls.__module__,
        cls.__name__,
        directory_entries={},
        source_index=candidate_ledger._AuthorityImportClosureSourceIndex({}, {}),
        visited=frozenset(),
    )


def _load_source_module(path: Path, module_name: str) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cell(value: object) -> types.CellType:
    return (lambda item: lambda: item)(value).__closure__[0]


def _function_with_replaced_cell(
    function: types.FunctionType,
    name: str,
    value: object,
) -> types.FunctionType:
    assert function.__closure__ is not None
    cells = list(function.__closure__)
    cells[function.__code__.co_freevars.index(name)] = _cell(value)
    replacement = types.FunctionType(
        function.__code__,
        function.__globals__,
        function.__name__,
        function.__defaults__,
        tuple(cells),
    )
    replacement.__module__ = function.__module__
    replacement.__qualname__ = function.__qualname__
    replacement.__doc__ = function.__doc__
    replacement.__kwdefaults__ = function.__kwdefaults__
    replacement.__annotations__ = dict(function.__annotations__)
    replacement.__dict__.update(function.__dict__)
    return replacement


def _function_with_code(
    function: types.FunctionType,
    replacement_code: types.CodeType,
) -> types.FunctionType:
    replacement = types.FunctionType(
        replacement_code,
        function.__globals__,
        function.__name__,
        function.__defaults__,
        function.__closure__,
    )
    replacement.__module__ = function.__module__
    replacement.__qualname__ = function.__qualname__
    replacement.__doc__ = function.__doc__
    replacement.__kwdefaults__ = function.__kwdefaults__
    replacement.__annotations__ = dict(function.__annotations__)
    replacement.__dict__.update(function.__dict__)
    return replacement


def test_actual_supported_stdlib_dataclass_owners_match_complete_source_replay(
    candidate_ledger: types.ModuleType,
) -> None:
    for cls in (MethodMetadata, ArtifactBoundedManifestRead, ArtifactStoreReadUsage):
        assert _supports_source_dataclass(candidate_ledger, cls)
        assert _direct_source_route(candidate_ledger, cls) == (
            "symbol",
            cls.__module__,
            cls.__name__,
        )


def test_source_defined_class_cell_swap_changes_behavior_and_is_rejected(
    candidate_ledger: types.ModuleType,
    tmp_path: Path,
) -> None:
    source = tmp_path / "dataclass_owner.py"
    source.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "@dataclass(frozen=True, slots=True)\n"
        "class Owner:\n"
        "    value: int\n"
        "    def owner_type(self) -> type[object]:\n"
        "        return __class__\n",
        encoding="utf-8",
    )
    module = _load_source_module(source, "n11_dataclass_owner_probe")
    owner = module.Owner
    assert _supports_source_dataclass(candidate_ledger, owner, owner_module=module)
    method = owner.__dict__["owner_type"]
    assert "__class__" in method.__code__.co_freevars
    index = method.__code__.co_freevars.index("__class__")
    actual_class_cell = method.__closure__[index].cell_contents
    decoy = type(
        "Owner",
        (),
        {
            "__module__": module.__name__,
            "__qualname__": "Owner",
            "value": None,
        },
    )
    assert owner(1).owner_type() is actual_class_cell
    owner.owner_type = _function_with_replaced_cell(method, "__class__", decoy)
    assert owner(1).owner_type() is decoy
    assert not _supports_source_dataclass(candidate_ledger, owner, owner_module=module)


def test_property_getter_behavior_mutation_is_rejected(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usage = ArtifactStoreReadUsage(
        observed_manifest_selection_bytes=1,
        observed_manifest_verification_bytes=2,
        observed_payload_bytes=3,
        observed_payload_size=3,
        payload_integrity_verified=True,
        failure_stage=None,
    )
    assert usage.observed_source_bytes == 6
    assert _supports_source_dataclass(candidate_ledger, ArtifactStoreReadUsage)
    monkeypatch.setattr(
        ArtifactStoreReadUsage,
        "observed_source_bytes",
        property(lambda _self: -1),
    )
    assert usage.observed_source_bytes == -1
    assert not _supports_source_dataclass(candidate_ledger, ArtifactStoreReadUsage)


def test_property_descriptor_components_are_reconciled_exactly(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = ArtifactStoreReadUsage
    name = "observed_source_bytes"
    original = owner.__dict__[name]
    assert type(original) is property
    getter = original.fget
    assert type(getter) is types.FunctionType
    assert _supports_source_dataclass(candidate_ledger, owner)

    abstract_getter = _function_with_code(getter, getter.__code__)
    abstract_getter.__dict__["__isabstractmethod__"] = True
    changed = (
        property(getter, lambda _self, _value: None, doc=original.__doc__),
        property(getter, fdel=lambda _self: None, doc=original.__doc__),
        property(getter, doc="changed documentation"),
        property(abstract_getter, doc=original.__doc__),
    )
    for descriptor in changed:
        monkeypatch.setattr(owner, name, descriptor)
        assert not _supports_source_dataclass(candidate_ledger, owner)
        monkeypatch.setattr(owner, name, original)


def test_generated_order_method_behavior_mutation_is_rejected(
    candidate_ledger: types.ModuleType,
    tmp_path: Path,
) -> None:
    source = tmp_path / "ordered_owner.py"
    source.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "@dataclass(order=True, frozen=True, slots=True)\n"
        "class OrderedOwner:\n"
        "    value: int\n",
        encoding="utf-8",
    )
    module = _load_source_module(source, "n11_ordered_owner_probe")
    owner = module.OrderedOwner
    assert _supports_source_dataclass(candidate_ledger, owner, owner_module=module)
    assert owner(1) < owner(2)

    def wrong_less_than(_self: object, _other: object) -> bool:
        return False

    owner.__lt__ = _function_with_code(owner.__lt__, wrong_less_than.__code__)
    assert not (owner(1) < owner(2))
    assert not _supports_source_dataclass(candidate_ledger, owner, owner_module=module)


def test_generated_method_runtime_global_rebind_is_rejected(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)
    value = MethodMetadata(description="runtime global binding control")
    original = MethodMetadata.__getstate__
    before = value.__getstate__()
    changed_globals = dict(original.__globals__)
    changed_globals["fields"] = lambda _instance: ()
    changed = types.FunctionType(
        original.__code__,
        changed_globals,
        original.__name__,
        original.__defaults__,
        original.__closure__,
    )
    changed.__module__ = original.__module__
    changed.__qualname__ = original.__qualname__
    changed.__doc__ = original.__doc__
    changed.__kwdefaults__ = original.__kwdefaults__
    changed.__annotations__ = dict(original.__annotations__)
    changed.__dict__.update(original.__dict__)
    monkeypatch.setattr(MethodMetadata, "__getstate__", changed)
    assert before != value.__getstate__()
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)


def test_hidden_raw_initvar_field_map_entry_is_rejected(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)
    value = MethodMetadata(description="hidden raw field-map control")
    dataclasses.replace(value)
    hidden = dataclasses.field()
    hidden.name = "unassigned"
    hidden.type = object
    hidden.init = True
    hidden._field_type = dataclasses._FIELD_INITVAR
    monkeypatch.setitem(MethodMetadata.__dataclass_fields__, "unassigned", hidden)
    with pytest.raises(TypeError, match="InitVar"):
        dataclasses.replace(value)
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)


def test_stdlib_dataclass_provider_rebind_is_rejected(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_module = importlib.import_module(MethodMetadata.__module__)
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)
    monkeypatch.setattr(owner_module, "dataclass", lambda cls=None, **_kwargs: cls)
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)


def test_provider_source_environment_rejects_live_global_mutation(
    candidate_ledger: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    live_provider = sys.modules["dataclasses"]
    assert live_provider is dataclasses
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)

    source = tmp_path / "post_init_owner.py"
    source.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Owner:\n"
        "    value: int\n"
        "    def __post_init__(self) -> None:\n"
        "        self.post_init_called = True\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(dataclasses, "_POST_INIT_NAME", "__mutated_no_post_init__")
    module = _load_source_module(source, "n11_mutated_post_init_owner")
    owner = module.Owner
    assert owner(1).__dict__ == {"value": 1}
    assert not _supports_source_dataclass(
        candidate_ledger,
        owner,
        owner_module=module,
    )
    assert sys.modules["dataclasses"] is live_provider

    monkeypatch.undo()
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)
    monkeypatch.setattr(types, "MappingProxyType", lambda value: value)
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)


def test_runtime_only_load_global_shadow_is_rejected(
    candidate_ledger: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "runtime_only_shadow.py"
    source.write_text(
        """from __future__ import annotations
from dataclasses import dataclass
from typing import ClassVar
@dataclass
class Owner:
    value: ClassVar[int] = 3
""",
        encoding="utf-8",
    )
    baseline = _load_source_module(source, "n11_runtime_only_shadow_baseline")
    assert baseline.Owner.__dataclass_fields__["value"]._field_type is dataclasses._FIELD_CLASSVAR
    baseline_projection = candidate_ledger._python_dataclass_transform_source_projection()
    assert baseline_projection["provider_module"] == "dataclasses"

    builtin_isinstance = __import__("builtins").isinstance

    def shadowed_isinstance(value: object, kind: object) -> bool:
        if value == "ClassVar[int]" and kind is str:
            return False
        return builtin_isinstance(value, kind)

    monkeypatch.setattr(dataclasses, "isinstance", shadowed_isinstance, raising=False)
    mutated = _load_source_module(source, "n11_runtime_only_shadow_mutated")
    assert "value" in mutated.Owner.__dataclass_fields__
    assert mutated.Owner.__dataclass_fields__["value"]._field_type is dataclasses._FIELD
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)
    with pytest.raises(candidate_ledger.ConfidenceLedgerError):
        candidate_ledger._python_dataclass_transform_source_projection()


def test_runtime_only_behavior_preserving_builtin_shadow_is_rejected(
    candidate_ledger: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = candidate_ledger._python_dataclass_transform_source_projection()
    consumed_builtins = set(projection["consumed_builtin_names"])
    assert {"getattr", "isinstance"} <= consumed_builtins
    assert projection["provider_builtin_binding_count"] == len(consumed_builtins)
    assert projection["provider_load_global_binding_count"] == len(
        projection["consumed_load_global_names"]
    )
    assert set(projection["consumed_load_global_names"]) == (
        set(projection["consumed_global_names"]) | consumed_builtins
    )
    assert projection["provider_global_binding_count"] == (
        len(projection["global_bindings"]) + len(projection["consumed_class_binding_names"])
    )
    assert projection["provider_class_binding_count"] == len(
        projection["provider_source_class_names"]
    )

    builtin_getattr = __import__("builtins").getattr

    def shadowed_getattr(value: object, name: str, *default: object) -> object:
        return builtin_getattr(value, name, *default)

    monkeypatch.setattr(dataclasses, "getattr", shadowed_getattr, raising=False)
    source = tmp_path / "behavior_preserving_builtin_shadow.py"
    source.write_text(
        """from dataclasses import dataclass
@dataclass
class Owner:
    value: int = 7
""",
        encoding="utf-8",
    )
    module = _load_source_module(source, "n11_behavior_preserving_builtin_shadow")
    assert module.Owner().value == 7
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)
    with pytest.raises(candidate_ledger.ConfidenceLedgerError):
        candidate_ledger._python_dataclass_transform_source_projection()


def test_unconsumed_provider_global_does_not_block_source_support(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection = candidate_ledger._python_dataclass_transform_source_projection()
    extra_name = "_n11_unconsumed_provider_binding"
    assert extra_name not in projection["consumed_load_global_names"]
    monkeypatch.setattr(dataclasses, extra_name, object(), raising=False)
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)


def test_source_graph_reconciliation_tracks_cycles_aliases_and_only_verified_pairs(
    candidate_ledger: types.ModuleType,
) -> None:
    graph = candidate_ledger._ProviderSourceGraphReconciliation()
    expected_cycle: list[object] = []
    expected_cycle.append(expected_cycle)
    actual_cycle: list[object] = []
    actual_cycle.append(actual_cycle)

    assert graph.enter(expected_cycle, actual_cycle) is None
    assert graph.enter(expected_cycle, actual_cycle) is True
    graph.finish(expected_cycle, actual_cycle, matched=True)
    assert graph.enter(expected_cycle, actual_cycle) is True

    expected_shared: list[object] = []
    first_actual: list[object] = []
    different_actual: list[object] = []
    assert graph.bind(expected_shared, first_actual)
    assert graph.enter(expected_shared, different_actual) is False

    expected_failed: dict[str, object] = {}
    actual_failed: dict[str, object] = {}
    assert graph.enter(expected_failed, actual_failed) is None
    graph.finish(expected_failed, actual_failed, matched=False)
    assert graph.enter(expected_failed, actual_failed) is None
    graph.finish(expected_failed, actual_failed, matched=False)


def test_provider_mapping_proxy_content_mutation_is_rejected(
    candidate_ledger: types.ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = tmp_path / "mapping_proxy_owner.py"
    source.write_text(
        "from __future__ import annotations\n"
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class Owner:\n"
        "    value: int\n",
        encoding="utf-8",
    )
    baseline = _load_source_module(source, "n11_mapping_proxy_owner_baseline")
    assert _supports_source_dataclass(
        candidate_ledger,
        baseline.Owner,
        owner_module=baseline,
    )
    assert dict(baseline.Owner.__dataclass_fields__["value"].metadata) == {}

    mutated_metadata = types.MappingProxyType({"runtime_only": "provider-global"})
    monkeypatch.setattr(dataclasses, "_EMPTY_METADATA", mutated_metadata)
    mutated = _load_source_module(source, "n11_mapping_proxy_owner_mutated")
    assert dict(mutated.Owner.__dataclass_fields__["value"].metadata) == {
        "runtime_only": "provider-global"
    }
    with pytest.raises(candidate_ledger.ConfidenceLedgerError):
        candidate_ledger._python_dataclass_transform_source_projection()
    assert not _supports_source_dataclass(
        candidate_ledger,
        mutated.Owner,
        owner_module=mutated,
    )


def test_cyclic_consumed_provider_global_is_rejected(
    candidate_ledger: types.ModuleType,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert _supports_source_dataclass(candidate_ledger, MethodMetadata)
    cyclic_action = dict(dataclasses._hash_action)
    key = next(iter(cyclic_action))
    cyclic_action[key] = cyclic_action
    assert cyclic_action[key] is cyclic_action

    monkeypatch.setattr(dataclasses, "_hash_action", cyclic_action)
    with pytest.raises(candidate_ledger.ConfidenceLedgerError):
        candidate_ledger._python_dataclass_transform_source_projection()
    assert not _supports_source_dataclass(candidate_ledger, MethodMetadata)
