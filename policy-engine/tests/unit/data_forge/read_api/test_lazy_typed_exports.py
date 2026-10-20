from __future__ import annotations

import ast
import copy
import importlib
import importlib.util
import json
import multiprocessing
import os
import sys
from pathlib import Path
from queue import Empty
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pytest

READ_API_MODULES = (
    "polisyos.data_forge.read_api",
    "polisyos.data_forge.read_api.academic",
    "polisyos.data_forge.read_api.catalog",
    "polisyos.data_forge.read_api.legal",
    "polisyos.data_forge.read_api.ukraine",
)


def _product_root() -> Path:
    configured = os.environ.get("POLISYOS_READ_API_PRODUCT_ROOT")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4]


def _source_root() -> Path:
    configured = os.environ.get("POLISYOS_READ_API_SOURCE_ROOT")
    if configured:
        return Path(configured)
    return _product_root() / "src" / "polisyos"


def _facade_path(module_name: str) -> Path:
    if module_name == "polisyos.data_forge.read_api":
        candidate = _source_root() / "data_forge" / "read_api" / "__init__.py"
    else:
        candidate = (
            _source_root() / "data_forge" / "read_api" / f"{module_name.rsplit('.', 1)[1]}.py"
        )
    if candidate.is_file():
        return candidate
    # The isolated candidate overlay contains only changed facade sources.
    return _product_root() / "src" / "polisyos" / "data_forge" / "read_api" / candidate.name


def _import_path(node: ast.ImportFrom, package: str) -> str:
    if node.level == 0:
        assert node.module is not None
        return node.module
    relative = "." * node.level + (node.module or "")
    return importlib.util.resolve_name(relative, package)


def _module_exports(module_name: str) -> dict[str, tuple[str, str]]:
    facade = importlib.import_module(module_name)
    exports = facade._EXPORTS
    assert isinstance(exports, dict)
    resolved: dict[str, tuple[str, str]] = {}
    for name, target in exports.items():
        assert isinstance(name, str)
        if isinstance(target, str):
            resolved[name] = (target, name)
        else:
            assert isinstance(target, tuple)
            assert len(target) == 2
            owner, attribute = target
            assert isinstance(owner, str)
            assert isinstance(attribute, str)
            resolved[name] = (owner, attribute)
    return resolved


def _import_bindings(tree: ast.Module, package: str) -> list[tuple[str, str, str, bool]]:
    bindings: list[tuple[str, str, str, bool]] = []

    def add_import(statement: ast.stmt, type_only: bool) -> None:
        if isinstance(statement, ast.ImportFrom):
            owner = _import_path(statement, package)
            for alias in statement.names:
                bindings.append((alias.asname or alias.name, owner, alias.name, type_only))
        elif isinstance(statement, ast.Import):
            for alias in statement.names:
                bound_name = alias.asname or alias.name.split(".", 1)[0]
                bindings.append((bound_name, alias.name, "<module>", type_only))

    for node in tree.body:
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for statement in node.body:
                add_import(statement, True)
            for statement in node.orelse:
                add_import(statement, False)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            add_import(node, False)
    return bindings


def _binding_errors(
    tree: ast.Module,
    package: str,
    public_name: str,
    owner: str,
    attribute: str,
) -> list[str]:
    bindings = _import_bindings(tree, package)
    alias_bindings = [
        (binding_owner, binding_attribute, type_only)
        for name, binding_owner, binding_attribute, type_only in bindings
        if name == public_name
    ]
    matching = [
        binding for binding in alias_bindings if binding[0] == owner and binding[1] == attribute
    ]
    errors = []
    if not matching:
        errors.append(f"{public_name} has no static import from {owner}.{attribute}")

    conflicting_bindings = [
        ("TYPE_CHECKING" if type_only else "runtime", binding_owner, binding_attribute)
        for binding_owner, binding_attribute, type_only in alias_bindings
        if (binding_owner, binding_attribute) != (owner, attribute)
    ]
    if conflicting_bindings:
        errors.append(
            f"{public_name} has conflicting static import(s) {conflicting_bindings}; "
            f"expected only {owner}.{attribute}"
        )
    return errors


def _remove_canonical_import_bindings(
    tree: ast.Module,
    package: str,
    public_name: str,
    owner: str,
    attribute: str,
) -> int:
    bodies = [tree.body]
    for node in tree.body:
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            bodies.extend((node.body, node.orelse))
    removed = 0
    for body in bodies:
        for statement in list(body):
            if not isinstance(statement, ast.ImportFrom):
                continue
            if _import_path(statement, package) != owner:
                continue
            retained = [
                alias
                for alias in statement.names
                if not ((alias.asname or alias.name) == public_name and alias.name == attribute)
            ]
            removed += len(statement.names) - len(retained)
            if len(retained) == len(statement.names):
                continue
            if retained:
                statement.names = retained
            else:
                body.remove(statement)
    return removed


def test_all_mapped_exports_have_static_bindings_to_their_canonical_owners() -> None:
    for module_name in READ_API_MODULES:
        facade = importlib.import_module(module_name)
        exports = _module_exports(module_name)
        tree = ast.parse(_facade_path(module_name).read_text(encoding="utf-8"))

        for public_name, (owner, attribute) in exports.items():
            assert not (
                errors := _binding_errors(tree, facade.__package__, public_name, owner, attribute)
            ), f"{module_name}: {'; '.join(errors)}"


def test_removing_canonical_bindings_fails_for_every_mapped_export() -> None:
    checked = 0
    for module_name in READ_API_MODULES:
        facade = importlib.import_module(module_name)
        source_tree = ast.parse(_facade_path(module_name).read_text(encoding="utf-8"))
        exports = _module_exports(module_name)

        for public_name, (owner, attribute) in exports.items():
            tree = copy.deepcopy(source_tree)
            removed = _remove_canonical_import_bindings(
                tree, facade.__package__, public_name, owner, attribute
            )
            assert removed, f"{module_name}.{public_name} had no canonical import to remove"
            errors = _binding_errors(tree, facade.__package__, public_name, owner, attribute)
            assert f"{public_name} has no static import from {owner}.{attribute}" in errors
            checked += 1

    assert checked == sum(len(_module_exports(name)) for name in READ_API_MODULES)


def _insert_import_binding(tree: ast.Module, statement: ast.stmt, *, scope: str) -> None:
    if scope == "runtime":
        tree.body.insert(0, statement)
        return

    if scope not in {"TYPE_CHECKING", "TYPE_CHECKING-else/runtime"}:
        raise AssertionError(f"unsupported import scope: {scope}")
    type_checking_block = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ),
        None,
    )
    if type_checking_block is None:
        type_checking_block = ast.If(
            test=ast.Name(id="TYPE_CHECKING", ctx=ast.Load()),
            body=[],
            orelse=[],
        )
        tree.body.insert(0, type_checking_block)
    body = type_checking_block.body if scope == "TYPE_CHECKING" else type_checking_block.orelse
    body.insert(0, statement)


def test_conflicting_static_bindings_fail_for_every_mapped_export() -> None:
    scope_modes = ("runtime", "TYPE_CHECKING", "TYPE_CHECKING-else/runtime")
    binding_variants = ("wrong_owner", "wrong_attribute", "module_alias")
    checked = 0
    for module_name in READ_API_MODULES:
        facade = importlib.import_module(module_name)
        source_tree = ast.parse(_facade_path(module_name).read_text(encoding="utf-8"))
        exports = _module_exports(module_name)

        for public_name, (owner, attribute) in exports.items():
            wrong_owner = "polisyos.data_forge.read_api"
            if wrong_owner == owner:
                wrong_owner = "polisyos.data_forge.read_api._lazy"
            for scope in scope_modes:
                for variant in binding_variants:
                    if variant == "wrong_owner":
                        statement: ast.stmt = ast.ImportFrom(
                            module=wrong_owner,
                            names=[ast.alias(name=attribute, asname=public_name)],
                            level=0,
                        )
                    elif variant == "wrong_attribute":
                        statement = ast.ImportFrom(
                            module=owner,
                            names=[
                                ast.alias(
                                    name=f"{attribute}__wrong_binding_probe",
                                    asname=public_name,
                                )
                            ],
                            level=0,
                        )
                    else:
                        statement = ast.Import(
                            names=[ast.alias(name=wrong_owner, asname=public_name)]
                        )

                    tree = copy.deepcopy(source_tree)
                    _insert_import_binding(tree, statement, scope=scope)
                    errors = _binding_errors(
                        tree, facade.__package__, public_name, owner, attribute
                    )
                    assert any("conflicting static import(s)" in error for error in errors), (
                        f"{module_name}.{public_name} accepted {variant} in {scope} scope"
                    )
                    checked += 1

    total_exports = sum(len(_module_exports(name)) for name in READ_API_MODULES)
    assert checked == len(scope_modes) * len(binding_variants) * total_exports


def _cold_import_probe_worker(module_name: str, product_root: Path, result_queue: object) -> None:
    candidate_source = Path(os.environ["POLISYOS_READ_API_SOURCE_ROOT"])
    candidate_package_path = candidate_source / "data_forge" / "read_api"
    base_package_path = product_root / "src" / "polisyos" / "data_forge" / "read_api"
    importlib.import_module("polisyos")
    importlib.import_module("polisyos.data_forge")
    package_spec = importlib.util.spec_from_file_location(
        "polisyos.data_forge.read_api",
        candidate_package_path / "__init__.py",
        submodule_search_locations=[str(candidate_package_path), str(base_package_path)],
    )
    if package_spec is None or package_spec.loader is None:
        raise AssertionError("could not load the candidate read_api package")
    candidate_package = importlib.util.module_from_spec(package_spec)
    sys.modules["polisyos.data_forge.read_api"] = candidate_package
    package_spec.loader.exec_module(candidate_package)
    facade = importlib.import_module(module_name)
    resolved = {}
    for name, target in facade._EXPORTS.items():
        resolved[name] = (target, name) if isinstance(target, str) else target

    source_tree = ast.parse(_facade_path(module_name).read_text(encoding="utf-8"))
    declared_imports = _import_bindings(source_tree, facade.__package__)
    owners = {owner for owner, _ in resolved.values()}
    prebound = {
        owner
        for name, (owner, attribute) in resolved.items()
        if (name, owner, attribute, False) in declared_imports
    }
    loaded_before_resolution = owners.intersection(sys.modules)
    if loaded_before_resolution != prebound:
        raise AssertionError(
            "mapped owner modules were eager before export access: "
            + json.dumps(
                {
                    "facade": module_name,
                    "expected_prebound_owners": sorted(prebound),
                    "loaded_mapped_owners": sorted(loaded_before_resolution),
                },
                sort_keys=True,
            )
        )

    static_bindings_before = {
        name: tuple(_binding_errors(source_tree, facade.__package__, name, owner, attribute))
        for name, (owner, attribute) in resolved.items()
    }
    if any(static_bindings_before.values()):
        raise AssertionError(
            "canonical import binding failed in a cold facade: "
            + json.dumps(
                {
                    "facade": module_name,
                    "errors": {
                        name: list(errors)
                        for name, errors in static_bindings_before.items()
                        if errors
                    },
                },
                sort_keys=True,
            )
        )

    for name, (owner, attribute) in resolved.items():
        owner_module = importlib.import_module(owner)
        expected = getattr(owner_module, attribute)
        actual = getattr(facade, name)
        if actual is not expected:
            raise AssertionError(
                f"{module_name}.{name} lost canonical identity with {owner}.{attribute}"
            )
    static_bindings_after = {
        name: tuple(_binding_errors(source_tree, facade.__package__, name, owner, attribute))
        for name, (owner, attribute) in resolved.items()
    }
    if static_bindings_after != static_bindings_before:
        raise AssertionError(
            f"static canonical-binding results changed after warming {module_name}"
        )
    result_queue.put({"facade": module_name, "checked": len(resolved)})


def test_every_mapped_export_stays_lazy_and_preserves_owner_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    product_root = _product_root()
    monkeypatch.setenv("POLISYOS_READ_API_SOURCE_ROOT", str(_source_root()))
    python_path = os.pathsep.join(
        part for part in (str(product_root / "src"), os.environ.get("PYTHONPATH", "")) if part
    )
    monkeypatch.setenv("PYTHONPATH", python_path)
    context = multiprocessing.get_context("spawn")
    for module_name in READ_API_MODULES:
        result_queue = context.Queue()
        process = context.Process(
            target=_cold_import_probe_worker,
            args=(module_name, product_root, result_queue),
        )
        process.start()
        process.join(timeout=60)
        if process.is_alive():
            process.terminate()
            process.join()
            raise AssertionError(f"cold import probe timed out for {module_name}")
        assert process.exitcode == 0
        try:
            receipt = result_queue.get(timeout=2)
        except Empty as error:
            raise AssertionError(
                f"cold import probe returned no receipt for {module_name}"
            ) from error
        finally:
            result_queue.close()
        assert receipt == {
            "facade": module_name,
            "checked": len(_module_exports(module_name)),
        }
