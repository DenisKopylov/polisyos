from __future__ import annotations

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
    return module


def _copy_candidate_read_api(repo_root: Path) -> None:
    product_root = _workspace_product_root()
    source = _candidate_product_root() / "src/polisyos/data_forge/read_api"
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
