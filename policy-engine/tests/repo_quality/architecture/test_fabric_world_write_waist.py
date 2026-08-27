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


def _absolute_imports(tree: ast.AST) -> tuple[tuple[int, str], ...]:
    imports: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend((node.lineno, alias.name) for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            imports.append((node.lineno, node.module))
    return tuple(imports)


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
        for _, module in _absolute_imports(owner_function)
        if module.startswith("polisyos.fabric.world.")
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
    owned_tables = world_owned_tables(ddl_path)
    violations: set[str] = set()

    for path in sorted((src_root / "polisyos").rglob("*.py")):
        if path.is_relative_to(owner_package):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        relative = path.relative_to(src_root.parent).as_posix()
        for lineno, imported_module in _absolute_imports(tree):
            if any(
                imported_module == forbidden
                or imported_module.startswith(f"{forbidden}.")
                for forbidden in forbidden_modules
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
