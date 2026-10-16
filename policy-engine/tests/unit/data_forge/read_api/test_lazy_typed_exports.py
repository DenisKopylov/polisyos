from __future__ import annotations

import ast
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
    for node in tree.body:
        if (
            isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        ):
            for statement in node.body:
                if not isinstance(statement, ast.ImportFrom):
                    continue
                owner = _import_path(statement, package)
                for alias in statement.names:
                    bindings.append((alias.asname or alias.name, owner, alias.name, True))
        elif isinstance(node, ast.ImportFrom):
            owner = _import_path(node, package)
            for alias in node.names:
                bindings.append((alias.asname or alias.name, owner, alias.name, False))
    return bindings


def _binding_errors(
    tree: ast.Module,
    package: str,
    public_name: str,
    owner: str,
    attribute: str,
    runtime_bound: bool,
) -> list[str]:
    bindings = _import_bindings(tree, package)
    matching = [
        (type_only, binding_owner, binding_attribute)
        for name, binding_owner, binding_attribute, type_only in bindings
        if name == public_name and binding_owner == owner and binding_attribute == attribute
    ]
    errors = []
    if not matching:
        errors.append(f"{public_name} has no static import from {owner}.{attribute}")
    if not any(type_only for type_only, _, _ in matching) and not runtime_bound:
        errors.append(f"{public_name} is neither imported under TYPE_CHECKING nor bound at runtime")
    if runtime_bound and not any(not type_only for type_only, _, _ in matching):
        errors.append(f"{public_name} is runtime-bound without its canonical import")
    return errors


def test_all_mapped_exports_have_static_bindings_to_their_canonical_owners() -> None:
    for module_name in READ_API_MODULES:
        facade = importlib.import_module(module_name)
        exports = _module_exports(module_name)
        tree = ast.parse(_facade_path(module_name).read_text(encoding="utf-8"))

        for public_name, (owner, attribute) in exports.items():
            runtime_bound = public_name in facade.__dict__
            assert not (
                errors := _binding_errors(
                    tree, facade.__package__, public_name, owner, attribute, runtime_bound
                )
            ), f"{module_name}: {'; '.join(errors)}"


def test_removing_a_type_alias_fails_for_each_incomplete_facade() -> None:
    removed_by_facade: dict[str, str] = {}
    for module_name in READ_API_MODULES:
        if module_name == "polisyos.data_forge.read_api.catalog":
            continue
        facade = importlib.import_module(module_name)
        tree = ast.parse(_facade_path(module_name).read_text(encoding="utf-8"))
        exports = _module_exports(module_name)
        type_block = next(
            node
            for node in tree.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "TYPE_CHECKING"
        )

        for public_name, (owner, attribute) in exports.items():
            if public_name in facade.__dict__:
                continue
            for statement in type_block.body:
                if not isinstance(statement, ast.ImportFrom):
                    continue
                if _import_path(statement, facade.__package__) != owner:
                    continue
                retained = [alias for alias in statement.names if alias.name != attribute]
                if len(retained) == len(statement.names):
                    continue
                if retained:
                    statement.names = retained
                else:
                    type_block.body.remove(statement)
                errors = _binding_errors(
                    tree, facade.__package__, public_name, owner, attribute, False
                )
                assert errors
                assert "no static import" in errors[0]
                removed_by_facade[module_name] = public_name
                break
            if module_name in removed_by_facade:
                break

    expected = {
        "polisyos.data_forge.read_api",
        "polisyos.data_forge.read_api.academic",
        "polisyos.data_forge.read_api.legal",
        "polisyos.data_forge.read_api.ukraine",
    }
    assert set(removed_by_facade) == expected


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

    owners = {owner for owner, _ in resolved.values()}
    prebound = {owner for name, (owner, _) in resolved.items() if name in facade.__dict__}
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

    for name, (owner, attribute) in resolved.items():
        owner_module = importlib.import_module(owner)
        expected = getattr(owner_module, attribute)
        actual = getattr(facade, name)
        if actual is not expected:
            raise AssertionError(
                f"{module_name}.{name} lost canonical identity with {owner}.{attribute}"
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
