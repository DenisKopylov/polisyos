from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
WORLD_WRITE_OWNER = SRC_ROOT / "polisyos" / "fabric" / "world" / "write.py"
WORLD_DDL = SRC_ROOT / "polisyos" / "fabric" / "world" / "ddl" / "duckdb_world.sql"

_CREATE_TABLE_RE = re.compile(
    r"\bCREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?P<table>[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)
_MUTATING_TARGET_RE = re.compile(
    r"\b(?:"
    r"INSERT\s+INTO|UPDATE|DELETE\s+FROM|MERGE\s+INTO|"
    r"CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|"
    r"ALTER\s+TABLE|DROP\s+TABLE(?:\s+IF\s+EXISTS)?|TRUNCATE\s+TABLE"
    r")\s+(?P<table>[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*)",
    re.IGNORECASE,
)


def _module_name(src_root: Path, path: Path) -> str:
    relative = path.relative_to(src_root)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _module_source_path(src_root: Path, module: str) -> Path | None:
    module_path = src_root.joinpath(*module.split("."))
    package_init = module_path / "__init__.py"
    if package_init.exists():
        return package_init
    module_file = module_path.with_suffix(".py")
    if module_file.exists():
        return module_file
    return None


def _module_import_bindings(
    src_root: Path,
    module: str,
    cache: dict[str, dict[str, tuple[tuple[str, str | None], ...]]],
) -> dict[str, tuple[tuple[str, str | None], ...]]:
    if module in cache:
        return cache[module]
    module_source = _module_source_path(src_root, module)
    if module_source is None:
        cache[module] = {}
        return cache[module]

    tree = ast.parse(
        module_source.read_text(encoding="utf-8"),
        filename=str(module_source),
    )
    mutable_bindings: dict[str, set[tuple[str, str | None]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                public_name = alias.asname or alias.name.rsplit(".", maxsplit=1)[-1]
                mutable_bindings.setdefault(public_name, set()).add((alias.name, None))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                public_name = alias.asname or alias.name
                mutable_bindings.setdefault(public_name, set()).add(
                    (node.module, alias.name)
                )
    bindings = {
        public_name: tuple(sorted(origins))
        for public_name, origins in mutable_bindings.items()
    }
    cache[module] = bindings
    return bindings


def _resolved_import_from_alias(
    src_root: Path,
    module: str,
    imported_name: str,
    *,
    cache: dict[tuple[str, str], frozenset[str]],
    module_bindings_cache: dict[
        str,
        dict[str, tuple[tuple[str, str | None], ...]],
    ],
    seen: frozenset[tuple[str, str]] = frozenset(),
) -> frozenset[str]:
    binding = (module, imported_name)
    if binding in cache:
        return cache[binding]
    if binding in seen:
        return frozenset()

    child_module = f"{module}.{imported_name}"
    if _module_source_path(src_root, child_module) is not None:
        resolved_child = frozenset({child_module})
        cache[binding] = resolved_child
        return resolved_child

    resolved: set[str] = set()
    next_seen = seen | {binding}
    bindings = _module_import_bindings(src_root, module, module_bindings_cache)
    for origin_module, origin_name in bindings.get(imported_name, ()):
        if origin_name is None:
            resolved.add(origin_module)
            continue
        reexported_child = f"{origin_module}.{origin_name}"
        if _module_source_path(src_root, reexported_child) is not None:
            resolved.add(reexported_child)
        else:
            resolved.add(origin_module)
            resolved.update(
                _resolved_import_from_alias(
                    src_root,
                    origin_module,
                    origin_name,
                    cache=cache,
                    module_bindings_cache=module_bindings_cache,
                    seen=next_seen,
                )
            )
    result = frozenset(resolved)
    cache[binding] = result
    return result


def _absolute_imports(
    src_root: Path,
    tree: ast.AST,
    *,
    alias_cache: dict[tuple[str, str], frozenset[str]] | None = None,
    module_bindings_cache: dict[
        str,
        dict[str, tuple[tuple[str, str | None], ...]],
    ]
    | None = None,
) -> tuple[tuple[int, str, str | None, str], ...]:
    alias_cache = alias_cache if alias_cache is not None else {}
    module_bindings_cache = (
        module_bindings_cache if module_bindings_cache is not None else {}
    )
    imports: set[tuple[int, str, str | None, str]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(
                (node.lineno, alias.name, None, alias.name) for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            for alias in node.names:
                imports.add((node.lineno, node.module, alias.name, node.module))
                imports.update(
                    (node.lineno, resolved, alias.name, node.module)
                    for resolved in _resolved_import_from_alias(
                        src_root,
                        node.module,
                        alias.name,
                        cache=alias_cache,
                        module_bindings_cache=module_bindings_cache,
                    )
                )
    return tuple(sorted(imports, key=lambda item: (item[0], item[1], item[2] or "", item[3])))


def _declared_module_exports(src_root: Path, module: str) -> frozenset[str]:
    module_source = _module_source_path(src_root, module)
    if module_source is None:
        return frozenset()
    tree = ast.parse(
        module_source.read_text(encoding="utf-8"),
        filename=str(module_source),
    )
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if isinstance(target, ast.Name) and target.id == "__all__" and value is not None:
            return frozenset(ast.literal_eval(value))
    return frozenset()


def _public_fabric_reexports(src_root: Path) -> frozenset[tuple[str, str]]:
    facade_path = src_root / "polisyos" / "fabric" / "__init__.py"
    if not facade_path.exists():
        return frozenset()
    tree = ast.parse(facade_path.read_text(encoding="utf-8"), filename=str(facade_path))
    declared_names: frozenset[str] = frozenset()
    lazy_imports: dict[str, tuple[str, str]] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        if target.id == "__all__":
            literal = ast.literal_eval(value)
            declared_names = frozenset(literal)
        elif target.id == "_LAZY_IMPORTS":
            lazy_imports = ast.literal_eval(value)
    return frozenset(
        origin
        for public_name, origin in lazy_imports.items()
        if public_name in declared_names
    )


def _mutating_owned_tables(tree: ast.AST, owned_tables: frozenset[str]) -> tuple[str, ...]:
    targets: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        for match in _MUTATING_TARGET_RE.finditer(node.value):
            table = match.group("table").lower()
            if table in owned_tables:
                targets.add(table)
    return tuple(sorted(targets))


def world_owned_tables(ddl_path: Path) -> frozenset[str]:
    """Derive qualified table names from every CREATE TABLE statement."""

    return frozenset(
        match.group("table").lower()
        for match in _CREATE_TABLE_RE.finditer(ddl_path.read_text(encoding="utf-8"))
    )


def world_write_private_modules(src_root: Path, owner_path: Path) -> frozenset[str]:
    """Derive private backend imports, descendants, and owned-table writers."""

    owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"), filename=str(owner_path))
    owner_function = next(
        node
        for node in owner_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "write_world_snapshot"
    )
    private_modules = {
        module
        for _, module, _, _ in _absolute_imports(src_root, owner_function)
        if module.startswith("polisyos.fabric.")
    }

    derived_modules = set(private_modules)
    for module in private_modules:
        module_path = src_root.joinpath(*module.split("."))
        package_init = module_path / "__init__.py"
        module_file = module_path.with_suffix(".py")
        if package_init.exists():
            derived_modules.update(
                _module_name(src_root, descendant)
                for descendant in module_path.rglob("*.py")
            )
        elif module_file.exists():
            derived_modules.add(_module_name(src_root, module_file))

    owned_tables = world_owned_tables(
        src_root / "polisyos" / "fabric" / "world" / "ddl" / "duckdb_world.sql"
    )
    fabric_root = src_root / "polisyos" / "fabric"
    for path in sorted(fabric_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if _mutating_owned_tables(tree, owned_tables):
            derived_modules.add(_module_name(src_root, path))
    return frozenset(derived_modules)


def external_world_write_violations(src_root: Path) -> tuple[str, ...]:
    """Return sorted deep-import and mutating-owned-table AST findings."""

    owner_path = src_root / "polisyos" / "fabric" / "world" / "write.py"
    ddl_path = src_root / "polisyos" / "fabric" / "world" / "ddl" / "duckdb_world.sql"
    if not owner_path.exists():
        return (f"{owner_path.relative_to(src_root.parent).as_posix()}: owner missing",)
    owner_package = src_root / "polisyos" / "fabric"
    forbidden_modules = world_write_private_modules(src_root, owner_path)
    public_fabric_reexports = _public_fabric_reexports(src_root)
    owner_public_facade = _module_name(src_root, owner_path).rpartition(".")[0]
    owner_public_exports = _declared_module_exports(src_root, owner_public_facade)
    owned_tables = world_owned_tables(ddl_path)
    violations: set[str] = set()
    alias_cache: dict[tuple[str, str], frozenset[str]] = {}
    module_bindings_cache: dict[
        str,
        dict[str, tuple[tuple[str, str | None], ...]],
    ] = {}

    for path in sorted((src_root / "polisyos").rglob("*.py")):
        if path.is_relative_to(owner_package):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(src_root.parent).as_posix()
        for lineno, imported_module, imported_name, source_module in _absolute_imports(
            src_root,
            tree,
            alias_cache=alias_cache,
            module_bindings_cache=module_bindings_cache,
        ):
            imports_forbidden_backend = any(
                imported_module == forbidden
                or imported_module.startswith(f"{forbidden}.")
                for forbidden in forbidden_modules
            )
            is_public_shared_symbol = (
                imported_name is not None
                and (imported_module, imported_name) in public_fabric_reexports
            )
            uses_owner_public_facade = (
                source_module == owner_public_facade
                and imported_name is not None
                and imported_name in owner_public_exports
            )
            if (
                imports_forbidden_backend
                and not is_public_shared_symbol
                and not uses_owner_public_facade
            ):
                violations.add(f"{relative}:{lineno}: deep-import {imported_module}")
        for table in _mutating_owned_tables(tree, owned_tables):
            violations.add(f"{relative}: mutates {table}")
    return tuple(sorted(violations))


def _fixture_owner_tree(tmp_path: Path) -> tuple[Path, Path]:
    src_root = tmp_path / "src"
    world_root = src_root / "polisyos" / "fabric" / "world"
    (world_root / "ddl").mkdir(parents=True)
    (world_root / "backend_one").mkdir()
    (world_root / "backend_two").mkdir()
    (world_root / "backend_three").mkdir()
    for package in ("backend_one", "backend_two", "backend_three"):
        (world_root / package / "__init__.py").write_text("", encoding="utf-8")
    owner_path = world_root / "write.py"
    owner_path.write_text(
        """
def write_world_snapshot():
    from polisyos.fabric.world.backend_one import write_one
    from polisyos.fabric.world.backend_two import write_two
    from polisyos.fabric.world.backend_three import write_three
    return write_one, write_two, write_three
""".lstrip(),
        encoding="utf-8",
    )
    ddl_path = world_root / "ddl" / "duckdb_world.sql"
    ddl_path.write_text(
        """
CREATE TABLE world.first_table (id VARCHAR);
CREATE TABLE world.second_table (id VARCHAR);
CREATE TABLE world.third_table (id VARCHAR);
""".lstrip(),
        encoding="utf-8",
    )
    return src_root, owner_path


def test_private_module_derivation_detects_a_fourth_backend_descendant(
    tmp_path: Path,
) -> None:
    src_root, owner_path = _fixture_owner_tree(tmp_path)
    fourth = src_root / "polisyos" / "fabric" / "world" / "backend_four"
    fourth.mkdir()
    (fourth / "__init__.py").write_text("", encoding="utf-8")
    (fourth / "nested.py").write_text("def write_fourth(): pass\n", encoding="utf-8")
    owner_path.write_text(
        owner_path.read_text(encoding="utf-8").replace(
            "    return write_one, write_two, write_three\n",
            "    from polisyos.fabric.world.backend_four import write_fourth\n"
            "    return write_one, write_two, write_three, write_fourth\n",
        ),
        encoding="utf-8",
    )
    runtime = src_root / "polisyos" / "runtime" / "external.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        "from polisyos.fabric.world.backend_four.nested import write_fourth\n",
        encoding="utf-8",
    )

    derived = world_write_private_modules(src_root, owner_path)
    violations = external_world_write_violations(src_root)

    assert "polisyos.fabric.world.backend_four.nested" in derived
    assert any("backend_four.nested" in violation for violation in violations)


def test_private_module_derivation_includes_actual_non_world_fabric_backend(
    tmp_path: Path,
) -> None:
    src_root, owner_path = _fixture_owner_tree(tmp_path)
    io_root = src_root / "polisyos" / "fabric" / "io"
    io_root.mkdir()
    (io_root / "db.py").write_text("class SimulationDB: pass\n", encoding="utf-8")
    owner_path.write_text(
        owner_path.read_text(encoding="utf-8").replace(
            "    return write_one, write_two, write_three\n",
            "    from polisyos.fabric.io.db import SimulationDB\n"
            "    return write_one, write_two, write_three, SimulationDB\n",
        ),
        encoding="utf-8",
    )

    derived = world_write_private_modules(src_root, owner_path)

    assert "polisyos.fabric.io.db" in derived


def test_import_from_child_and_reexport_resolve_to_private_backend(
    tmp_path: Path,
) -> None:
    src_root, owner_path = _fixture_owner_tree(tmp_path)
    store_root = src_root / "polisyos" / "fabric" / "world" / "store"
    store_root.mkdir()
    (store_root / "snapshots.py").write_text(
        "def create_world_snapshot(): pass\n",
        encoding="utf-8",
    )
    (store_root / "__init__.py").write_text(
        "from polisyos.fabric.world.store.snapshots import create_world_snapshot\n",
        encoding="utf-8",
    )
    owner_path.write_text(
        owner_path.read_text(encoding="utf-8").replace(
            "    return write_one, write_two, write_three\n",
            "    from polisyos.fabric.world.store.snapshots import create_world_snapshot\n"
            "    return write_one, write_two, write_three, create_world_snapshot\n",
        ),
        encoding="utf-8",
    )
    runtime_root = src_root / "polisyos" / "runtime"
    runtime_root.mkdir(parents=True)
    (runtime_root / "child_import.py").write_text(
        "from polisyos.fabric.world.store import snapshots\n",
        encoding="utf-8",
    )
    (runtime_root / "symbol_import.py").write_text(
        "from polisyos.fabric.world.store import create_world_snapshot\n",
        encoding="utf-8",
    )

    violations = external_world_write_violations(src_root)

    assert any("child_import.py" in violation for violation in violations)
    assert any("symbol_import.py" in violation for violation in violations)


def test_public_waist_import_is_admitted_but_direct_owner_import_is_forbidden(
    tmp_path: Path,
) -> None:
    src_root, owner_path = _fixture_owner_tree(tmp_path)
    owner_path.write_text(
        owner_path.read_text(encoding="utf-8").replace(
            "def write_world_snapshot():\n",
            "def write_world_snapshot():\n"
            '    sql = "INSERT INTO world.first_table (id) VALUES (?)"\n',
        ),
        encoding="utf-8",
    )
    world_facade = owner_path.parent / "__init__.py"
    world_facade.write_text(
        "from polisyos.fabric.world.write import write_world_snapshot\n"
        '__all__ = ["write_world_snapshot"]\n',
        encoding="utf-8",
    )
    runtime_root = src_root / "polisyos" / "runtime"
    runtime_root.mkdir(parents=True)
    (runtime_root / "facade.py").write_text(
        "from polisyos.fabric.world import write_world_snapshot\n",
        encoding="utf-8",
    )
    (runtime_root / "direct.py").write_text(
        "from polisyos.fabric.world.write import write_world_snapshot\n",
        encoding="utf-8",
    )

    violations = external_world_write_violations(src_root)

    assert not any("facade.py" in violation for violation in violations)
    assert any("direct.py" in violation for violation in violations)


def test_public_shared_fabric_symbol_is_not_world_write_authority(tmp_path: Path) -> None:
    src_root, owner_path = _fixture_owner_tree(tmp_path)
    fabric_root = src_root / "polisyos" / "fabric"
    (fabric_root / "__init__.py").write_text(
        '__all__ = ["SimulationDB"]\n'
        '_LAZY_IMPORTS = {"SimulationDB": '
        '("polisyos.fabric.io.db", "SimulationDB")}\n',
        encoding="utf-8",
    )
    io_root = fabric_root / "io"
    io_root.mkdir()
    (io_root / "db.py").write_text("class SimulationDB: pass\n", encoding="utf-8")
    owner_path.write_text(
        owner_path.read_text(encoding="utf-8").replace(
            "    return write_one, write_two, write_three\n",
            "    from polisyos.fabric.io.db import SimulationDB\n"
            "    return write_one, write_two, write_three, SimulationDB\n",
        ),
        encoding="utf-8",
    )
    reader = src_root / "polisyos" / "runtime" / "reader.py"
    reader.parent.mkdir(parents=True)
    reader.write_text(
        "from polisyos.fabric.io.db import SimulationDB\n",
        encoding="utf-8",
    )

    derived = world_write_private_modules(src_root, owner_path)
    violations = external_world_write_violations(src_root)

    assert "polisyos.fabric.io.db" in derived
    assert not any("reader.py" in violation for violation in violations)


def test_owned_table_derivation_detects_a_fourth_ddl_target(tmp_path: Path) -> None:
    src_root, _owner_path = _fixture_owner_tree(tmp_path)
    ddl_path = src_root / "polisyos" / "fabric" / "world" / "ddl" / "duckdb_world.sql"
    ddl_path.write_text(
        ddl_path.read_text(encoding="utf-8")
        + "CREATE TABLE IF NOT EXISTS world.fourth_table (id VARCHAR);\n",
        encoding="utf-8",
    )
    runtime = src_root / "polisyos" / "runtime" / "external.py"
    runtime.parent.mkdir(parents=True)
    runtime.write_text(
        'SQL = "INSERT INTO world.fourth_table (id) VALUES (?)"\n',
        encoding="utf-8",
    )

    assert "world.fourth_table" in world_owned_tables(ddl_path)
    assert any("mutates world.fourth_table" in item for item in external_world_write_violations(src_root))


def test_legitimate_world_event_reader_is_not_forbidden_by_package_location(
    tmp_path: Path,
) -> None:
    src_root, _owner_path = _fixture_owner_tree(tmp_path)
    reader = src_root / "polisyos" / "runtime" / "reader.py"
    reader.parent.mkdir(parents=True)
    reader.write_text(
        "from polisyos.fabric.world.events import load_world_events\n"
        'QUERY = "SELECT * FROM world.world_events"\n',
        encoding="utf-8",
    )

    assert external_world_write_violations(src_root) == ()


def test_production_modules_use_the_fabric_world_write_waist() -> None:
    violations = external_world_write_violations(SRC_ROOT)

    assert not any("polisyos.fabric.world.events" in item for item in violations)
    assert violations == ()
