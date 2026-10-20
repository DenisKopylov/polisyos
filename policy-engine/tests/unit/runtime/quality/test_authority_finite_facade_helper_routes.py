from __future__ import annotations

import hashlib
import importlib
import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


def _workspace_product_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "src/polisyos").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("PolicyOS product root could not be derived from the test path")


def _candidate_product_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "postimages/policy-engine"
        if (candidate / "src/polisyos/runtime/quality/confidence_ledger.py").is_file():
            return candidate
    return _workspace_product_root()


def _ensure_workspace_source_path() -> Path:
    source_root = str(_workspace_product_root() / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    return Path(source_root)


def _candidate_ledger() -> object:
    product_root = _workspace_product_root()
    _ensure_workspace_source_path()
    candidate_root = _candidate_product_root()
    source = candidate_root / "src/polisyos/runtime/quality/confidence_ledger.py"
    name = "polisyos.runtime.quality.confidence_ledger"
    if candidate_root == product_root:
        module = importlib.import_module(name)
        if Path(module.__file__).resolve() != source.resolve():
            raise AssertionError("confidence ledger import did not resolve to the current source")
        return module
    spec = importlib.util.spec_from_file_location(name, source)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(name)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = previous
    if Path(module.__file__).resolve() != source.resolve():
        raise AssertionError("candidate confidence ledger import used an unexpected source file")
    return module


def _copy_candidate_read_api(repo_root: Path) -> None:
    product_root = _workspace_product_root()
    candidate_source = _candidate_product_root() / "src/polisyos/data_forge/read_api"
    source = (
        candidate_source
        if (candidate_source / "__init__.py").is_file()
        else product_root / "src/polisyos/data_forge/read_api"
    )
    package = repo_root / "src/polisyos/data_forge"
    read_api = package / "read_api"
    read_api.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    shutil.copyfile(
        product_root / "src/polisyos/data_forge/__init__.py",
        package / "__init__.py",
    )
    for filename in ("__init__.py", "surfaces.py", "surface_routes.py"):
        shutil.copyfile(source / filename, read_api / filename)
    for name in ("academic", "catalog", "legal", "ukraine"):
        (read_api / f"{name}.py").write_text("VALUE = 1\n", encoding="utf-8")


def test_source_owned_data_forge_surface_helper_routes_to_real_catalog_module(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "source-bound-data-forge"
    _copy_candidate_read_api(repo_root)
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})

    parent_route = ledger._source_module_import_route(
        repo_root,
        "polisyos.data_forge",
        "read_api",
        directory_entries={},
        source_index=source_index,
    )
    catalog_route = ledger._source_module_import_route(
        repo_root,
        "polisyos.data_forge.read_api",
        "catalog",
        directory_entries={},
        source_index=source_index,
    )
    read_api_source = repo_root / "src/polisyos/data_forge/read_api/__init__.py"
    read_api_tree = ledger.ast.parse(read_api_source.read_bytes())
    provider_index = ledger._source_module_provider_index(
        repo_root,
        "polisyos.data_forge.read_api",
        read_api_tree,
        directory_entries={},
        source_index=source_index,
    )

    assert parent_route == ("module", "polisyos.data_forge.read_api", None)
    assert catalog_route == ("module", "polisyos.data_forge.read_api.catalog", None)
    assert (provider_index.module_providers_by_export or {}).get("catalog") == frozenset(
        {"polisyos.data_forge.read_api.catalog"}
    )


def test_finite_imported_surface_map_with_missing_provider_does_not_fall_back_to_child(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "wrong-finite-surface-repo"
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    routes = package / "routes.py"
    routes.write_text(
        'SURFACE_MODULES = {"catalog": "polisyos.missing.catalog"}\n',
        encoding="utf-8",
    )
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from importlib import import_module\n"
        "from .routes import SURFACE_MODULES\n"
        "def __getattr__(name):\n"
        "    if name not in SURFACE_MODULES:\n"
        "        raise AttributeError(name)\n"
        "    module = import_module(SURFACE_MODULES[name])\n"
        "    globals()[name] = module\n"
        "    return module\n",
        encoding="utf-8",
    )
    (package / "catalog.py").write_text("VALUE = 1\n", encoding="utf-8")
    entry = repo_root / "src/polisyos/entry.py"
    entry.write_text("from polisyos.facade import catalog\n", encoding="utf-8")

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")


def _write_imported_map_facade(
    repo_root: Path,
    *,
    map_source: str,
    getter_source: str,
    entry_source: str = "from polisyos.facade import catalog\n",
) -> None:
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "routes.py").write_text(map_source, encoding="utf-8")
    (package / "__init__.py").write_text(
        "from importlib import import_module\n"
        "from .routes import SURFACE_MODULES as _SURFACES\n"
        "def __getattr__(name):\n" + getter_source,
        encoding="utf-8",
    )
    (package / "catalog.py").write_text("VALUE = 'catalog-child'\n", encoding="utf-8")
    entry = repo_root / "src/polisyos/entry.py"
    entry.write_text(entry_source, encoding="utf-8")


def test_imported_alias_map_recomputes_when_source_bytes_change(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "changed-source-map"
    _write_imported_map_facade(
        repo_root,
        map_source=('SURFACE_MODULES = {"catalog": "polisyos.facade.catalog"}\n'),
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    return import_module(_SURFACES[name])\n"
        ),
    )
    (repo_root / "src/polisyos/facade/provider_b.py").write_text(
        "VALUE = 'provider-b'\n", encoding="utf-8"
    )
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})

    before = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "catalog",
        directory_entries={},
        source_index=source_index,
    )
    routes = repo_root / "src/polisyos/facade/routes.py"
    routes.write_text(
        'SURFACE_MODULES = {"catalog": "polisyos.facade.provider_b"}\n',
        encoding="utf-8",
    )
    after = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "catalog",
        directory_entries={},
        source_index=source_index,
    )

    assert before == ("module", "polisyos.facade.catalog", None)
    assert after == ("module", "polisyos.facade.provider_b", None)


@pytest.mark.parametrize(
    "map_source",
    [
        pytest.param(
            'SURFACE_MODULES = {"catalog": "polisyos.facade.catalog", '
            '"catalog": "polisyos.facade.provider_b"}\n',
            id="duplicate-key",
        ),
        pytest.param(
            'SURFACE_MODULES = dict(catalog="polisyos.facade.catalog")\n',
            id="opaque-dynamic-map",
        ),
    ],
)
def test_imported_map_duplicate_or_dynamic_source_refuses_route(
    tmp_path: Path, map_source: str
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "invalid-imported-map"
    _write_imported_map_facade(
        repo_root,
        map_source=map_source,
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    return import_module(_SURFACES[name])\n"
        ),
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_module_import_route(
            repo_root,
            "polisyos.facade",
            "catalog",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


def test_imported_map_and_getter_cannot_disagree_on_provider(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "wrong-provider"
    _write_imported_map_facade(
        repo_root,
        map_source=('SURFACE_MODULES = {"catalog": "polisyos.facade.catalog"}\n'),
        getter_source=(
            "    if name != 'catalog':\n"
            "        raise AttributeError(name)\n"
            "    module_name = _SURFACES[name]\n"
            "    module_name = 'polisyos.facade.provider_b'\n"
            "    return import_module(module_name)\n"
        ),
    )
    (repo_root / "src/polisyos/facade/provider_b.py").write_text(
        "VALUE = 'provider-b'\n", encoding="utf-8"
    )

    with pytest.raises(ledger.ConfidenceLedgerError, match="source facade map differs from getter"):
        ledger._source_module_import_route(
            repo_root,
            "polisyos.facade",
            "catalog",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


def test_loaded_module_from_finite_map_must_match_source_map(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "loaded-facade-disagreement"
    _write_imported_map_facade(
        repo_root,
        map_source=('SURFACE_MODULES = {"catalog": "polisyos.facade.catalog"}\n'),
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    module = import_module(_SURFACES[name])\n"
            "    globals()[name] = module\n"
            "    return module\n"
        ),
        entry_source="import polisyos.facade as facade\nfrom polisyos.facade import catalog\n",
    )
    package_root = repo_root / "src/polisyos"
    closure = ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")

    import polisyos

    previous_path = list(polisyos.__path__)
    names = (
        "polisyos.entry",
        "polisyos.facade",
        "polisyos.facade.routes",
        "polisyos.facade.catalog",
    )
    previous_modules = {name: sys.modules.pop(name, None) for name in names}
    polisyos.__path__ = [str(package_root), *previous_path]
    try:
        entry = importlib.import_module("polisyos.entry")
        facade = entry.facade
        assert facade.catalog.__name__ == "polisyos.facade.catalog"
        facade._SURFACES["catalog"] = "polisyos.facade.provider_b"
        (repo_root / "src/polisyos/facade/provider_b.py").write_text(
            "VALUE = 'provider-b'\n", encoding="utf-8"
        )

        with pytest.raises(
            ledger.ConfidenceLedgerError, match="loaded facade map differs from source"
        ):
            ledger._source_facade_runtime_projection(
                repo_root, closure, runtime_binding_references=[]
            )
    finally:
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(
            {name: module for name, module in previous_modules.items() if module is not None}
        )
        polisyos.__path__ = previous_path


def test_loaded_facade_projection_uses_each_facades_own_provider_index(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "two-facade-source"
    package_root = repo_root / "src/polisyos"
    package_root.mkdir(parents=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    for facade_name, export in (("facade_a", "catalog"), ("facade_b", "legal")):
        facade = package_root / facade_name
        facade.mkdir()
        provider = f"polisyos.{facade_name}.{export}"
        (facade / "routes.py").write_text(
            f"SURFACE_MODULES = {{{export!r}: {provider!r}}}\n", encoding="utf-8"
        )
        (facade / "__init__.py").write_text(
            "from importlib import import_module\n"
            "from .routes import SURFACE_MODULES as _SURFACES\n"
            "def __getattr__(name):\n"
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    module = import_module(_SURFACES[name])\n"
            "    globals()[name] = module\n"
            "    return module\n",
            encoding="utf-8",
        )
        (facade / f"{export}.py").write_text("VALUE = 1\n", encoding="utf-8")
    (package_root / "entry.py").write_text(
        "from polisyos.facade_a import catalog\nfrom polisyos.facade_b import legal\n",
        encoding="utf-8",
    )

    closure = ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")
    import polisyos

    previous_path = list(polisyos.__path__)
    names = (
        "polisyos.entry",
        "polisyos.facade_a",
        "polisyos.facade_a.routes",
        "polisyos.facade_a.catalog",
        "polisyos.facade_b",
        "polisyos.facade_b.routes",
        "polisyos.facade_b.legal",
    )
    previous_modules = {name: sys.modules.pop(name, None) for name in names}
    polisyos.__path__ = [str(package_root), *previous_path]
    try:
        importlib.import_module("polisyos.entry")
        projection, supplemental = ledger._source_facade_runtime_projection(
            repo_root,
            closure,
            runtime_binding_references=[],
        )
        assert projection
        assert not supplemental
    finally:
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(
            {name: module for name, module in previous_modules.items() if module is not None}
        )
        polisyos.__path__ = previous_path


def _run_real_python_import(
    repo_root: Path, package_name: str = "polisyos.facade"
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    source_root = str(repo_root / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (source_root, env.get("PYTHONPATH", "")) if part
    )
    return subprocess.run(
        [
            sys.executable,
            "-c",
            f"import types; from {package_name} import catalog; "
            "print('module' if isinstance(catalog, types.ModuleType) else 'symbol'); "
            "print(catalog.__name__ if isinstance(catalog, types.ModuleType) else catalog)",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _write_ordered_self_import_facade(
    repo_root: Path,
    *,
    hook_before_import: bool,
    child_exists: bool,
) -> None:
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "routes.py").write_text(
        'SURFACE_MODULES = {"catalog": "polisyos.facade.provider"}\n', encoding="utf-8"
    )
    imports = "from importlib import import_module\nfrom .routes import SURFACE_MODULES\n"
    getter = (
        "def __getattr__(name):\n"
        "    if name not in SURFACE_MODULES:\n"
        "        raise AttributeError(name)\n"
        "    return import_module(SURFACE_MODULES[name])\n"
    )
    self_import = "from . import catalog\n"
    initializer = (
        imports + getter + self_import if hook_before_import else self_import + imports + getter
    )
    (package / "__init__.py").write_text(initializer, encoding="utf-8")
    (package / "provider.py").write_text("VALUE = 'provider'\n", encoding="utf-8")
    if child_exists:
        (package / "catalog.py").write_text("VALUE = 'child'\n", encoding="utf-8")
    (repo_root / "src/polisyos/entry.py").write_text(
        "from polisyos.facade import catalog\n", encoding="utf-8"
    )


def test_self_import_before_getattr_uses_real_child_not_later_map(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "early-self-import-child"
    _write_ordered_self_import_facade(repo_root, hook_before_import=False, child_exists=True)

    actual = _run_real_python_import(repo_root)
    route = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "catalog",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )

    assert actual.returncode == 0
    assert actual.stdout.splitlines() == ["module", "polisyos.facade.catalog"]
    assert route == ("module", "polisyos.facade.catalog", None)


def test_self_import_before_getattr_without_child_refuses_later_map(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "early-self-import-no-child"
    _write_ordered_self_import_facade(repo_root, hook_before_import=False, child_exists=False)

    actual = _run_real_python_import(repo_root)

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_module_import_route(
            repo_root,
            "polisyos.facade",
            "catalog",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )
    assert actual.returncode != 0
    assert "ImportError" in actual.stderr


def test_self_import_after_getattr_uses_later_hook_when_child_is_absent(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "late-self-import-no-child"
    _write_ordered_self_import_facade(repo_root, hook_before_import=True, child_exists=False)

    actual = _run_real_python_import(repo_root)
    route = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "catalog",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )

    assert actual.returncode == 0
    assert actual.stdout.splitlines() == ["module", "polisyos.facade.provider"]
    assert route == ("module", "polisyos.facade.provider", None)


def _write_symbol_facade_chain(
    repo_root: Path,
    *,
    second_map_source: str = 'SYMBOLS = {"VALUE": ("polisyos.impl", "VALUE")}\n',
    first_target: str = '"polisyos.facade_b", "VALUE"',
    cycle: bool = False,
) -> None:
    package_root = repo_root / "src/polisyos"
    facade_a = package_root / "facade_a"
    facade_b = package_root / "facade_b"
    facade_a.mkdir(parents=True)
    facade_b.mkdir()
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (facade_a / "routes.py").write_text(
        f'SYMBOLS = {{"catalog": ({first_target})}}\n', encoding="utf-8"
    )
    symbol_getter = (
        "from importlib import import_module\n"
        "from .routes import SYMBOLS\n"
        "def __getattr__(name):\n"
        "    if name not in SYMBOLS:\n"
        "        raise AttributeError(name)\n"
        "    module_name, member_name = SYMBOLS[name]\n"
        "    return getattr(import_module(module_name), member_name)\n"
    )
    (facade_a / "__init__.py").write_text(symbol_getter, encoding="utf-8")
    if cycle:
        second_map_source = 'SYMBOLS = {"VALUE": ("polisyos.facade_a", "catalog")}\n'
    (facade_b / "routes.py").write_text(second_map_source, encoding="utf-8")
    (facade_b / "__init__.py").write_text(symbol_getter, encoding="utf-8")
    (package_root / "impl.py").write_text("VALUE = 'nested-symbol'\n", encoding="utf-8")
    (package_root / "entry.py").write_text(
        "from polisyos.facade_a import catalog\n", encoding="utf-8"
    )


def test_imported_symbol_map_resolves_nested_facade_owner_used_by_python(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "nested-imported-symbol-map"
    _write_symbol_facade_chain(repo_root)

    actual = _run_real_python_import(repo_root, "polisyos.facade_a")
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    assert ledger._repository_module_exports_symbol(
        repo_root,
        "polisyos.facade_b",
        "VALUE",
        directory_entries={},
        source_index=source_index,
    )
    closure = ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")

    assert actual.returncode == 0
    assert actual.stdout.splitlines() == ["symbol", "nested-symbol"]
    assert {name for name, _ in closure} >= {
        "polisyos.entry",
        "polisyos.facade_a",
        "polisyos.facade_b",
        "polisyos.impl",
    }


@pytest.mark.parametrize(
    "map_source",
    [
        pytest.param(
            'SYMBOLS = {"VALUE": ("polisyos.impl", "VALUE"), '
            '"VALUE": ("polisyos.impl_alt", "VALUE")}\n',
            id="nested-duplicate-key",
        ),
        pytest.param(
            'SYMBOLS = dict(VALUE=("polisyos.impl", "VALUE"))\n',
            id="nested-dynamic-map",
        ),
    ],
)
def test_nested_imported_symbol_map_ambiguity_or_dynamic_source_fails_closed(
    tmp_path: Path, map_source: str
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "invalid-nested-symbol-map"
    _write_symbol_facade_chain(repo_root, second_map_source=map_source)
    (repo_root / "src/polisyos/impl_alt.py").write_text(
        "VALUE = 'nested-symbol'\n", encoding="utf-8"
    )

    actual = _run_real_python_import(repo_root, "polisyos.facade_a")
    assert not ledger._repository_module_exports_symbol(
        repo_root,
        "polisyos.facade_b",
        "VALUE",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")
    assert actual.returncode == 0
    assert actual.stdout.splitlines() == ["symbol", "nested-symbol"]


def test_nested_imported_symbol_cycle_fails_closed(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "nested-symbol-cycle"
    _write_symbol_facade_chain(repo_root, cycle=True)

    actual = _run_real_python_import(repo_root, "polisyos.facade_a")
    assert not ledger._repository_module_exports_symbol(
        repo_root,
        "polisyos.facade_b",
        "VALUE",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")
    assert actual.returncode != 0


def _link_or_copy(source: str, destination: str) -> str:
    """Materialize source bytes without duplicating checkout data when possible."""

    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)
    return destination


def _materialize_runtime_source_overlay(tmp_path: Path) -> Path:
    """Build an isolated source root that exercises the selected ledger bytes."""

    product_root = _workspace_product_root()
    candidate_root = _candidate_product_root()
    overlay_root = tmp_path / "runtime-source-overlay"
    overlay_root.mkdir()
    for name in ("pyproject.toml", "uv.lock"):
        _link_or_copy(str(product_root / name), str(overlay_root / name))
    shutil.copytree(
        product_root / "src",
        overlay_root / "src",
        copy_function=_link_or_copy,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    for entry in product_root.iterdir():
        if entry.name in {"src", ".git", ".venv", "node_modules", "dist", "build"}:
            continue
        destination = overlay_root / entry.name
        if destination.exists():
            continue
        destination.symlink_to(entry, target_is_directory=entry.is_dir())
    overlay_ledger = overlay_root / "src/polisyos/runtime/quality/confidence_ledger.py"
    overlay_ledger.unlink()
    shutil.copyfile(
        candidate_root / "src/polisyos/runtime/quality/confidence_ledger.py",
        overlay_ledger,
    )
    return overlay_root


def test_runtime_import_and_unbound_bare_facade_provider_branch(
    tmp_path: Path,
) -> None:
    overlay_root = _materialize_runtime_source_overlay(tmp_path)
    script = """
import json
import tempfile
from pathlib import Path
import polisyos.runtime.quality.generation_cycle as generation_cycle
import polisyos.runtime.quality.confidence_ledger as ledger

root = Path(ledger._loaded_policy_engine_root())
assert generation_cycle.__name__ == "polisyos.runtime.quality.generation_cycle"
assert Path(ledger.__file__).resolve() == (
    root / "src/polisyos/runtime/quality/confidence_ledger.py"
).resolve()
with tempfile.TemporaryDirectory() as temporary:
    facade_root = Path(temporary)
    package = facade_root / "src/polisyos"
    package.mkdir(parents=True)
    (facade_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "bare_facade.py").write_text("VALUE = 1\\n", encoding="utf-8")
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    provider = ledger._literal_module_getattr_provider(
        facade_root,
        "polisyos.bare_facade",
        "MISSING",
        directory_entries={},
        source_index=source_index,
    )
    assert provider is None
print(
    json.dumps(
        {
            "generation_cycle": generation_cycle.__name__,
            "bare_provider": provider,
            "authority_failure": ledger._IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE,
        }
    )
)
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(overlay_root / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=overlay_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stderr
    payload = __import__("json").loads(result.stdout)
    assert payload["generation_cycle"] == "polisyos.runtime.quality.generation_cycle"
    assert payload["bare_provider"] is None
    failure = payload["authority_failure"]
    assert failure is None or failure[0] == "canonical_loaded_runtime_mismatch"


def _write_finite_child_getter(
    repo_root: Path,
    *,
    collection_name: str,
    collection_source: str,
    import_target: str = 'f"{__name__}.{name}"',
    prelude: str = "",
    function_prelude: str = "",
) -> None:
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from importlib import import_module\n"
        f"{prelude}"
        f"{collection_name} = {collection_source}\n"
        "def __getattr__(name):\n"
        f"{function_prelude}"
        f"    if name not in {collection_name}:\n"
        "        raise AttributeError(name)\n"
        f"    module = import_module({import_target})\n"
        "    globals()[name] = module\n"
        "    return module\n",
        encoding="utf-8",
    )
    (package / "child.py").write_text("VALUE = 'finite-child'\n", encoding="utf-8")


@pytest.mark.parametrize(
    ("import_target", "expected_module"),
    [
        pytest.param(
            '"polisyos.facade.child"',
            "polisyos.facade.child",
            id="direct-absolute-literal",
        ),
        pytest.param(
            '".child", __name__',
            "polisyos.facade.child",
            id="direct-relative-literal-explicit-package",
        ),
    ],
)
def test_direct_literal_import_module_routes_are_bound_as_modules(
    tmp_path: Path,
    import_target: str,
    expected_module: str,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "direct-literal-import-route"
    _write_finite_child_getter(
        repo_root,
        collection_name="__all__",
        collection_source='["child"]',
        import_target=import_target,
    )
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})

    provider = ledger._literal_module_getattr_provider(
        repo_root,
        "polisyos.facade",
        "child",
        directory_entries={},
        source_index=source_index,
    )
    route = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "child",
        directory_entries={},
        source_index=source_index,
    )

    assert provider == expected_module
    # child.py deliberately exports VALUE only; this must be a module route,
    # not a symbol route that assumes child.child exists.
    assert route == ("module", expected_module, None)


@pytest.mark.parametrize(
    ("import_target", "prelude", "function_prelude", "case_id"),
    [
        pytest.param(
            '".child"',
            "",
            "",
            "relative-package-argument-missing",
        ),
        pytest.param(
            '".child", "polisyos.other"',
            "",
            "",
            "relative-foreign-package-argument",
        ),
        pytest.param(
            '".child", "polisyos.facade"',
            "",
            "",
            "relative-literal-package-argument-is-not-name-binding",
        ),
        pytest.param(
            '".child", __name__',
            "",
            '    __name__ = "polisyos.other"\n',
            "relative-function-local-name-shadow",
        ),
        pytest.param(
            '".child", __name__',
            '__name__ = "polisyos.other"\n',
            "",
            "relative-module-name-shadow",
        ),
    ],
)
def test_direct_relative_import_module_requires_canonical_package_binding(
    tmp_path: Path,
    import_target: str,
    prelude: str,
    function_prelude: str,
    case_id: str,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / case_id
    _write_finite_child_getter(
        repo_root,
        collection_name="__all__",
        collection_source='["child"]',
        import_target=import_target,
        prelude=prelude,
        function_prelude=function_prelude,
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


@pytest.mark.parametrize(
    ("collection_name", "collection_source"),
    [
        pytest.param("__all__", '["child"]', id="literal-list"),
        pytest.param("_SUBPACKAGES", '("child",)', id="literal-tuple"),
        pytest.param("_SUBPACKAGES", 'frozenset({"child"})', id="literal-frozenset"),
    ],
)
def test_finite_membership_getter_routes_exact_package_child(
    tmp_path: Path,
    collection_name: str,
    collection_source: str,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / f"finite-child-{collection_name}"
    _write_finite_child_getter(
        repo_root,
        collection_name=collection_name,
        collection_source=collection_source,
    )
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})

    provider = ledger._literal_module_getattr_provider(
        repo_root,
        "polisyos.facade",
        "child",
        directory_entries={},
        source_index=source_index,
    )
    route = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "child",
        directory_entries={},
        source_index=source_index,
    )

    assert provider == "polisyos.facade.child"
    assert route == ("module", "polisyos.facade.child", None)


def test_canonical_common_and_core_finite_child_routes_are_source_owned() -> None:
    ledger = _candidate_ledger()
    repo_root = _workspace_product_root()
    source_index = ledger._AuthorityImportClosureSourceIndex({}, {})
    cases = (
        ("polisyos.common", "serialization", "polisyos.common.serialization"),
        ("polisyos.core", "components", "polisyos.core.components"),
    )

    for package, export_name, child_module in cases:
        provider = ledger._literal_module_getattr_provider(
            repo_root,
            package,
            export_name,
            directory_entries={},
            source_index=source_index,
        )
        route = ledger._source_module_import_route(
            repo_root,
            package,
            export_name,
            directory_entries={},
            source_index=source_index,
        )
        assert provider == child_module
        assert route == ("module", child_module, None)


def test_read_only_sorted_dir_use_keeps_finite_all_collection(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "read-only-all-consumer"
    _write_finite_child_getter(
        repo_root,
        collection_name="__all__",
        collection_source='["child"]',
        prelude=("def __dir__():\n    return sorted(list(globals().keys()) + __all__)\n"),
    )

    assert (
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )
        == "polisyos.facade.child"
    )


@pytest.mark.parametrize(
    ("collection_name", "collection_source", "import_target", "prelude"),
    [
        pytest.param(
            "__all__",
            "build_exports()",
            'f"{__name__}.{name}"',
            "def build_exports():\n    return ['child']\n",
            id="dynamic-table",
        ),
        pytest.param(
            "__all__",
            '["child"]',
            'f"polisyos.other.{name}"',
            "",
            id="wrong-package-prefix",
        ),
        pytest.param(
            "__all__",
            '["child"]',
            'f"{__name__}.{name}"',
            '__name__ = "polisyos.other"\n',
            id="rebound-package-name",
        ),
    ],
)
def test_finite_child_getter_rejects_dynamic_or_mismatched_route(
    tmp_path: Path,
    collection_name: str,
    collection_source: str,
    import_target: str,
    prelude: str,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "nonliteral-child-route"
    _write_finite_child_getter(
        repo_root,
        collection_name=collection_name,
        collection_source=collection_source,
        import_target=import_target,
        prelude=prelude,
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param('__all__.append("other")\n', id="mutable-list"),
        pytest.param('__all__ = ["other"]\n', id="rebound-list"),
        pytest.param("alias = __all__\n", id="aliased-list"),
        pytest.param("unknown_consumer(__all__)\n", id="unknown-call-escape"),
        pytest.param(
            'def mutate_exports():\n    global __all__\n    __all__.append("other")\n',
            id="nested-global-mutation",
        ),
    ],
)
def test_finite_child_getter_rejects_mutated_or_rebound_list(tmp_path: Path, mutation: str) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "unstable-child-members"
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from importlib import import_module\n"
        '__all__ = ["child"]\n'
        f"{mutation}"
        "def __getattr__(name):\n"
        "    if name not in __all__:\n"
        "        raise AttributeError(name)\n"
        '    return import_module(f"{__name__}.{name}")\n',
        encoding="utf-8",
    )
    (package / "child.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


def test_finite_child_route_rejects_shadowed_read_builtin(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "shadowed-read-builtin"
    _write_finite_child_getter(
        repo_root,
        collection_name="__all__",
        collection_source='["child"]',
        prelude=(
            "sorted = lambda values: values\n"
            "def __dir__():\n"
            "    return sorted(list(globals().keys()) + __all__)\n"
        ),
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


def test_finite_child_route_does_not_admit_false_guard_branch(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "false-finite-child-guard"
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from importlib import import_module\n"
        '__all__ = ["child"]\n'
        "def __getattr__(name):\n"
        "    if False:\n"
        "        if name in __all__:\n"
        '            return import_module(f"{__name__}.{name}")\n'
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    (package / "child.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


def test_finite_child_route_does_not_use_shadowed_collection_name(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "shadowed-finite-child-members"
    package = repo_root / "src/polisyos/facade"
    package.mkdir(parents=True)
    (repo_root / "src/polisyos/__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text(
        "from importlib import import_module\n"
        '__all__ = ["child"]\n'
        "def __getattr__(name):\n"
        '    __all__ = ["other"]\n'
        "    if name not in __all__:\n"
        "        raise AttributeError(name)\n"
        '    return import_module(f"{__name__}.{name}")\n',
        encoding="utf-8",
    )
    (package / "child.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._literal_module_getattr_provider(
            repo_root,
            "polisyos.facade",
            "child",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


def test_selected_source_runtime_imports_finite_common_and_core_children(
    tmp_path: Path,
) -> None:
    overlay_root = _materialize_runtime_source_overlay(tmp_path)
    script = """
import json
import hashlib
from pathlib import Path
import polisyos.common as common
import polisyos.core as core
import polisyos.runtime.quality.confidence_ledger as ledger
assert common.serialization.__name__ == "polisyos.common.serialization"
assert core.components.__name__ == "polisyos.core.components"
failure = ledger._IMPORT_TIME_DEPLOYMENT_IDENTITY_FAILURE
print(json.dumps({"common": common.serialization.__name__,
                  "core": core.components.__name__,
                  "ledger_file": str(Path(ledger.__file__).resolve()),
                  "ledger_sha256": hashlib.sha256(Path(ledger.__file__).read_bytes()).hexdigest(),
                  "common_file": str(Path(common.__file__).resolve()),
                  "core_file": str(Path(core.__file__).resolve()),
                  "failure": None if failure is None else str(failure)}))
"""
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(overlay_root / "src")
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=overlay_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=45,
    )

    assert result.returncode == 0, result.stderr
    payload = __import__("json").loads(result.stdout)
    assert payload["common"] == "polisyos.common.serialization"
    assert payload["core"] == "polisyos.core.components"
    assert payload["ledger_file"] == str(
        (overlay_root / "src/polisyos/runtime/quality/confidence_ledger.py").resolve()
    )
    candidate_source = (
        _candidate_product_root() / "src/polisyos/runtime/quality/confidence_ledger.py"
    )
    assert payload["ledger_sha256"] == hashlib.sha256(candidate_source.read_bytes()).hexdigest()
    assert payload["common_file"] == str(
        (overlay_root / "src/polisyos/common/__init__.py").resolve()
    )
    assert payload["core_file"] == str((overlay_root / "src/polisyos/core/__init__.py").resolve())
    assert "missing repository re-export binding: polisyos.common.serialization" not in str(
        payload["failure"]
    )
    assert "missing repository re-export binding: polisyos.core.components" not in str(
        payload["failure"]
    )
    print(
        "runtime_import_origins="
        + __import__("json").dumps(
            {
                key: payload[key]
                for key in ("ledger_file", "ledger_sha256", "common_file", "core_file")
            },
            sort_keys=True,
        )
    )


def test_relative_module_map_is_package_bound_across_route_and_cached_projection(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "relative-module-map-facade"
    _write_imported_map_facade(
        repo_root,
        map_source='SURFACE_MODULES = {"catalog": ".catalog"}\n',
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    module = import_module(_SURFACES[name], __name__)\n"
            "    globals()[name] = module\n"
            "    return module\n"
        ),
        entry_source=("import polisyos.facade as facade\nfrom polisyos.facade import catalog\n"),
    )
    closure = ledger._resolve_authority_import_closure(repo_root, "polisyos.entry")
    route = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "catalog",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )

    import polisyos

    package_root = repo_root / "src/polisyos"
    previous_path = list(polisyos.__path__)
    names = (
        "polisyos.entry",
        "polisyos.facade",
        "polisyos.facade.routes",
        "polisyos.facade.catalog",
    )
    previous_modules = {name: sys.modules.pop(name, None) for name in names}
    polisyos.__path__ = [str(package_root), *previous_path]
    try:
        entry = importlib.import_module("polisyos.entry")
        assert entry.catalog.__name__ == "polisyos.facade.catalog"
        projection, supplemental = ledger._source_facade_runtime_projection(
            repo_root, closure, runtime_binding_references=[]
        )
        assert projection
        assert not supplemental
    finally:
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(
            {name: module for name, module in previous_modules.items() if module is not None}
        )
        polisyos.__path__ = previous_path

    assert route == ("module", "polisyos.facade.catalog", None)


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            'def __getattr__(name, eager=globals().update({"__name__": "changed"})):\n'
            "    return name\n",
            id="eager-default-namespace-mutation",
        ),
        pytest.param(
            '@globals().update({"__name__": "changed"})\ndef __getattr__(name):\n    return name\n',
            id="eager-decorator-namespace-mutation",
        ),
        pytest.param(
            'globals().update({"__name__": "changed"})\ndef __getattr__(name):\n    return name\n',
            id="module-initializer-namespace-mutation",
        ),
    ],
)
def test_package_effect_scan_keeps_eager_namespace_mutations_fail_closed(
    source: str,
) -> None:
    ledger = _candidate_ledger()
    tree = ledger.ast.parse(source)

    assert ledger._source_package_initializer_effect_is_unknown(tree)


def test_package_effect_scan_ignores_lazy_hook_body_but_retains_map_mutation_guard(
    tmp_path: Path,
) -> None:
    ledger = _candidate_ledger()
    lazy_source = ledger.ast.parse(
        "from importlib import import_module\n"
        '_SURFACES = {"catalog": ".catalog"}\n'
        "def __getattr__(name):\n"
        "    if name not in _SURFACES:\n"
        "        raise AttributeError(name)\n"
        "    return import_module(_SURFACES[name], __name__)\n"
    )
    assert not ledger._source_package_initializer_effect_is_unknown(lazy_source)

    repo_root = tmp_path / "deferred-map-mutation"
    _write_imported_map_facade(
        repo_root,
        map_source='SURFACE_MODULES = {"catalog": ".catalog"}\n',
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            '    _SURFACES[name] = ".changed"\n'
            "    return import_module(_SURFACES[name], __name__)\n"
        ),
        entry_source="from polisyos.facade import catalog\n",
    )
    package_tree = ledger.ast.parse((repo_root / "src/polisyos/facade/__init__.py").read_bytes())
    assert not ledger._source_package_initializer_effect_is_unknown(package_tree)

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_module_import_route(
            repo_root,
            "polisyos.facade",
            "catalog",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )


@pytest.mark.parametrize(
    ("source", "expected_unknown"),
    [
        pytest.param(
            'def __getattr__(name: globals().update({"__name__": "changed"})):\n    return name\n',
            sys.version_info[:2] != (3, 14),
            id="eager-annotation-follows-runtime-policy",
        ),
        pytest.param(
            "from __future__ import annotations\n"
            'def __getattr__(name: globals().update({"__name__": "changed"})):\n'
            "    return name\n",
            False,
            id="future-annotation-is-deferred",
        ),
    ],
)
def test_package_effect_scan_respects_annotation_evaluation_phase(
    source: str,
    expected_unknown: bool,
) -> None:
    ledger = _candidate_ledger()
    tree = ledger.ast.parse(source)

    assert ledger._source_package_initializer_effect_is_unknown(tree) is expected_unknown


def test_relative_map_symbol_target_uses_explicit_package_argument(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "relative-map-symbol-facade"
    _write_imported_map_facade(
        repo_root,
        map_source='SURFACE_MODULES = {"catalog": (".catalog", "VALUE")}\n',
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    module = import_module(_SURFACES[name][0], __name__)\n"
            "    return getattr(module, _SURFACES[name][1])\n"
        ),
    )
    route = ledger._source_module_import_route(
        repo_root,
        "polisyos.facade",
        "catalog",
        directory_entries={},
        source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
    )

    assert route == ("symbol", "polisyos.facade.catalog", "VALUE")


def test_relative_map_target_without_package_argument_fails_closed(tmp_path: Path) -> None:
    ledger = _candidate_ledger()
    repo_root = tmp_path / "relative-map-without-package-facade"
    _write_imported_map_facade(
        repo_root,
        map_source='SURFACE_MODULES = {"catalog": ".catalog"}\n',
        getter_source=(
            "    if name not in _SURFACES:\n"
            "        raise AttributeError(name)\n"
            "    return import_module(_SURFACES[name])\n"
        ),
    )

    with pytest.raises(ledger.ConfidenceLedgerError):
        ledger._source_module_import_route(
            repo_root,
            "polisyos.facade",
            "catalog",
            directory_entries={},
            source_index=ledger._AuthorityImportClosureSourceIndex({}, {}),
        )
