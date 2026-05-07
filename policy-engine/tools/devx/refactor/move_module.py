#!/usr/bin/env python3
"""Move a Python module and rewrite imports with libcst."""

from __future__ import annotations

import argparse
import ast
import difflib
import json
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

_BOOTSTRAP_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_BOOTSTRAP_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_BOOTSTRAP_REPO_ROOT))

try:
    import libcst as cst
except ModuleNotFoundError:  # pragma: no cover - exercised in preflight environments.
    cst = None  # type: ignore[assignment]

from tools.lib.fs import atomic_write_text
from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
SRC_ROOT = REPO_ROOT / "src"
PYTHON_REWRITE_ROOTS = ("src", "tests", "tools")
TEXT_REWRITE_ROOTS = ("packages/runtime-api-client/scripts",)
SHIMS_PATH = REPO_ROOT / "architecture" / "shims.toml"


def _module_to_path(module: str, repo_root: Path) -> Path:
    parts = module.split(".")
    if parts[0] != "polisyos":
        raise ValueError(f"Only polisyos modules can be moved: {module}")
    return repo_root / "src" / Path(*parts).with_suffix(".py")


def _module_to_package_init_path(module: str, repo_root: Path) -> Path:
    return _module_to_path(module, repo_root).with_suffix("") / "__init__.py"


def _relative_module(old_module: str, new_module: str) -> str:
    old_parent = old_module.rsplit(".", 1)[0].split(".")
    new_parts = new_module.split(".")
    common = 0
    for left, right in zip(old_parent, new_parts, strict=False):
        if left != right:
            break
        common += 1
    dots = "." * (len(old_parent) - common + 1)
    suffix = ".".join(new_parts[common:])
    return f"{dots}{suffix}" if suffix else dots


def _exported_names(source_path: Path) -> list[str]:
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    exports: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets
        ):
            if isinstance(node.value, (ast.Tuple, ast.List)):
                exports = [
                    item.value
                    for item in node.value.elts
                    if isinstance(item, ast.Constant) and isinstance(item.value, str)
                ]
                break
    if exports:
        return sorted(dict.fromkeys(exports))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and not target.id.startswith("_"):
                    names.append(target.id)
    return sorted(dict.fromkeys(names))


def _required_init_files(repo_root: Path, target_path: Path) -> list[Path]:
    src_root = repo_root / "src"
    try:
        relative_parent = target_path.parent.resolve().relative_to(src_root.resolve())
    except ValueError:
        return []

    paths: list[Path] = []
    current = src_root
    for part in relative_parent.parts:
        current /= part
        init_path = current / "__init__.py"
        if not init_path.exists():
            paths.append(init_path)
    return paths


def _shim_source(
    old_module: str, new_module: str, names: Sequence[str], *, package_shim: bool = False
) -> str:
    import_target = new_module if package_shim else _relative_module(old_module, new_module)
    lines = [
        '"""Compatibility shim for a Phase 5/6 decomposition module move."""',
        "",
        "from __future__ import annotations",
        "",
    ]
    if package_shim:
        rendered_names = ", ".join(json.dumps(name) for name in names)
        lines.extend(
            [
                "import importlib",
                "from typing import Any",
                "",
                f"__all__ = ({rendered_names},)",
                "",
            ]
        )
        if names:
            lines.append("_LAZY_IMPORTS: dict[str, tuple[str, str]] = {")
            for name in names:
                lines.append(
                    f"    {json.dumps(name)}: ({json.dumps(new_module)}, {json.dumps(name)}),"
                )
            lines.append("}")
        else:
            lines.append("_LAZY_IMPORTS: dict[str, tuple[str, str]] = {}")
        lines.extend(
            [
                "",
                "",
                "def __getattr__(name: str) -> Any:",
                "    if name not in _LAZY_IMPORTS:",
                f"        raise AttributeError(f\"module '{old_module}' has no attribute {{name!r}}\")",
                "    module_name, attr_name = _LAZY_IMPORTS[name]",
                "    value = getattr(importlib.import_module(module_name), attr_name)",
                "    globals()[name] = value",
                "    return value",
                "",
                "",
                "def __dir__() -> list[str]:",
                "    return sorted(list(globals().keys()) + list(_LAZY_IMPORTS.keys()))",
                "",
            ]
        )
        return "\n".join(lines)
    if names:
        if len(names) <= 4:
            lines.append(f"from {import_target} import {', '.join(names)}  # noqa: F401")
        else:
            lines.append(f"from {import_target} import (")
            for name in names:
                lines.append(f"    {name},")
            lines.append(")  # noqa: F401")
        rendered_names = ", ".join(json.dumps(name) for name in names)
        lines.append("")
        lines.append(f"__all__ = ({rendered_names},)")
    else:
        lines.append(f"# No public names were detected in {new_module}.")
        lines.append("__all__: tuple[str, ...] = ()")
    lines.append("")
    return "\n".join(lines)


class _ImportRewriter(cst.CSTTransformer):  # type: ignore[misc]
    def __init__(self, old_module: str, new_module: str) -> None:
        self.old_module = old_module
        self.new_module = new_module
        self.old_parent, self.old_leaf = old_module.rsplit(".", 1)
        self.new_parent, self.new_leaf = new_module.rsplit(".", 1)

    def leave_ImportAlias(
        self,
        original_node: cst.ImportAlias,
        updated_node: cst.ImportAlias,
    ) -> cst.ImportAlias:
        if _dotted_name(original_node.name) != self.old_module:
            return updated_node
        return updated_node.with_changes(name=_parse_dotted_name(self.new_module))

    def leave_ImportFrom(
        self,
        original_node: cst.ImportFrom,
        updated_node: cst.ImportFrom,
    ) -> cst.ImportFrom:
        if original_node.module is None:
            return updated_node
        if _dotted_name(original_node.module) != self.old_module:
            return updated_node
        return updated_node.with_changes(module=_parse_dotted_name(self.new_module))

    def leave_SimpleStatementLine(
        self,
        original_node: cst.SimpleStatementLine,
        updated_node: cst.SimpleStatementLine,
    ) -> object:
        if len(original_node.body) != 1:
            return updated_node
        statement = original_node.body[0]
        if not isinstance(statement, cst.ImportFrom):
            return updated_node
        if statement.module is None or _dotted_name(statement.module) != self.old_parent:
            return updated_node
        if isinstance(statement.names, cst.ImportStar):
            return updated_node

        moved_aliases: list[cst.ImportAlias] = []
        remaining_aliases: list[cst.ImportAlias] = []
        for alias in statement.names:
            if _dotted_name(alias.name) != self.old_leaf:
                remaining_aliases.append(alias)
                continue
            asname = alias.asname
            if asname is None and self.new_leaf != self.old_leaf:
                asname = cst.AsName(cst.Name(self.old_leaf))
            moved_aliases.append(alias.with_changes(name=cst.Name(self.new_leaf), asname=asname))
        if not moved_aliases:
            return updated_node

        moved_import = statement.with_changes(
            module=_parse_dotted_name(self.new_parent),
            names=tuple(moved_aliases),
        )
        if not remaining_aliases:
            return updated_node.with_changes(body=(moved_import,))

        remaining_import = statement.with_changes(names=tuple(remaining_aliases))
        return cst.FlattenSentinel(
            [
                updated_node.with_changes(body=(remaining_import,)),
                updated_node.with_changes(body=(moved_import,)),
            ]
        )


def _dotted_name(node: object) -> str:
    if cst is None:
        return ""
    if isinstance(node, cst.Name):
        return node.value
    if isinstance(node, cst.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr.value}" if parent else node.attr.value
    return ""


def _parse_dotted_name(value: str) -> object:
    if cst is None:
        raise RuntimeError("libcst is required to rewrite imports")
    node: object = cst.Name(value.split(".")[0])
    for part in value.split(".")[1:]:
        node = cst.Attribute(value=node, attr=cst.Name(part))
    return node


def _iter_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for root_name in PYTHON_REWRITE_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        files.extend(
            path
            for path in root.rglob("*.py")
            if "__pycache__" not in path.parts and path.is_file()
        )
    return sorted(files)


def _iter_text_files(repo_root: Path) -> list[Path]:
    suffixes = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
    files: list[Path] = []
    for root_name in TEXT_REWRITE_ROOTS:
        root = repo_root / root_name
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*") if path.is_file() and path.suffix in suffixes)
    return sorted(files)


def _rewrite_python(path: Path, old_module: str, new_module: str) -> str | None:
    if cst is None:
        raise RuntimeError("libcst is required; install the dev dependency group")
    original = path.read_text(encoding="utf-8")
    if old_module not in original and old_module.rsplit(".", 1)[0] not in original:
        return None
    module = cst.parse_module(original)
    updated = module.visit(_ImportRewriter(old_module, new_module)).code
    return updated if updated != original else None


def _rewrite_text(path: Path, old_module: str, new_module: str) -> str | None:
    original = path.read_text(encoding="utf-8")
    updated = original.replace(old_module, new_module)
    return updated if updated != original else None


def _render_diff(path: Path, original: str, updated: str, repo_root: Path) -> str:
    rel = path.resolve().relative_to(repo_root).as_posix()
    return "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{rel}",
            tofile=f"b/{rel}",
        )
    )


def _append_shim_record(
    *,
    repo_root: Path,
    old_module: str,
    new_module: str,
    old_path: Path,
    new_path: Path,
    names: Sequence[str],
) -> None:
    shims_path = repo_root / "architecture" / "shims.toml"
    existing = shims_path.read_text(encoding="utf-8") if shims_path.exists() else ""
    created = datetime.now(UTC).date()
    sunset = created + timedelta(days=max(60, 2 * _max_registered_shim_lifetime_days(existing)))
    shim_id = f"decomp-{old_module.removeprefix('polisyos.').replace('.', '-')}"
    block = [
        "",
        "[[shim]]",
        f'id = "{shim_id}"',
        f'source_path = "{old_path.resolve().relative_to(repo_root).as_posix()}"',
        f'target_path = "{new_path.resolve().relative_to(repo_root).as_posix()}"',
        'type = "python_reexport"',
        f'source_fqn = "{old_module}"',
        f'target_fqn = "{new_module}"',
        f"reexported_names = [{', '.join(json.dumps(name) for name in names)}]",
        'reason = "Phase 5/6 decomposition compatibility shim"',
        'owner = "team-scientist/team-foundry"',
        f'created = "{created.isoformat()}"',
        f'sunset_date = "{sunset.isoformat()}"',
        'issue = "docs/plans/active/DECOMPOSITION_BLUEPRINT.md"',
        "",
    ]
    atomic_write_text(shims_path, existing.rstrip() + "\n" + "\n".join(block))


def _max_registered_shim_lifetime_days(toml_text: str) -> int:
    lifetimes: list[int] = []
    for block in toml_text.split("[[shim]]"):
        created: datetime | None = None
        sunset: datetime | None = None
        shim_type: str | None = None
        for line in block.splitlines():
            if line.startswith("created = "):
                created = _parse_iso_date(line)
            elif line.startswith("sunset_date = "):
                sunset = _parse_iso_date(line)
            elif line.startswith("type = "):
                shim_type = line.split("=", 1)[1].strip().strip('"')
        if shim_type != "python_reexport" and created is not None and sunset is not None:
            lifetimes.append(max(1, (sunset.date() - created.date()).days))
    return max(lifetimes or [30])


def _parse_iso_date(line: str) -> datetime | None:
    try:
        value = line.split("=", 1)[1].strip().strip('"')
        return datetime.fromisoformat(value)
    except (IndexError, ValueError):
        return None


def plan_move(repo_root: Path, old_module: str, new_module: str) -> dict[str, object]:
    old_path = _module_to_path(old_module, repo_root)
    new_path = _module_to_path(new_module, repo_root)
    shim_path = _module_to_package_init_path(old_module, repo_root)
    if not old_path.exists():
        raise FileNotFoundError(old_path)
    if new_path.exists():
        raise FileExistsError(new_path)
    names = _exported_names(old_path)
    rewrites: list[str] = []
    for path in [*_iter_python_files(repo_root), *_iter_text_files(repo_root)]:
        if path == old_path:
            continue
        text = path.read_text(encoding="utf-8")
        if old_module in text or f"from {old_module.rsplit('.', 1)[0]} import" in text:
            rewrites.append(path.resolve().relative_to(repo_root).as_posix())
    return {
        "from": old_module,
        "to": new_module,
        "source_path": old_path.resolve().relative_to(repo_root).as_posix(),
        "target_path": new_path.resolve().relative_to(repo_root).as_posix(),
        "shim_path": shim_path.resolve().relative_to(repo_root).as_posix(),
        "init_files": [
            path.resolve().relative_to(repo_root).as_posix()
            for path in _required_init_files(repo_root, new_path)
        ],
        "reexported_names": names,
        "rewrite_candidates": rewrites,
    }


def move_module(repo_root: Path, old_module: str, new_module: str, *, dry_run: bool) -> int:
    plan = plan_move(repo_root, old_module, new_module)
    old_path = repo_root / str(plan["source_path"])
    new_path = repo_root / str(plan["target_path"])
    shim_path = repo_root / str(plan["shim_path"])
    names = [str(name) for name in plan["reexported_names"]]
    updates: dict[Path, str] = {}
    diffs: list[str] = []

    for path in _iter_python_files(repo_root):
        if path == old_path:
            continue
        updated = _rewrite_python(path, old_module, new_module)
        if updated is None:
            continue
        updates[path] = updated
        diffs.append(_render_diff(path, path.read_text(encoding="utf-8"), updated, repo_root))
    for path in _iter_text_files(repo_root):
        updated = _rewrite_text(path, old_module, new_module)
        if updated is None:
            continue
        updates[path] = updated
        diffs.append(_render_diff(path, path.read_text(encoding="utf-8"), updated, repo_root))

    shim = _shim_source(old_module, new_module, names, package_shim=True)
    for init_file in [repo_root / str(path) for path in plan["init_files"]]:
        if init_file == shim_path:
            continue
        diffs.append(
            "".join(
                difflib.unified_diff(
                    [],
                    ['"""Phase 5/6 decomposition package."""\n'],
                    fromfile=f"a/{init_file.resolve().relative_to(repo_root).as_posix()}",
                    tofile=f"b/{init_file.resolve().relative_to(repo_root).as_posix()}",
                )
            )
        )
    diffs.append(
        "".join(
            difflib.unified_diff(
                [],
                shim.splitlines(keepends=True),
                fromfile=f"a/{plan['shim_path']}",
                tofile=f"b/{plan['shim_path']}",
            )
        )
    )

    if dry_run:
        print(json.dumps(plan, indent=2, ensure_ascii=False))
        for diff in diffs:
            if diff:
                print(diff)
        return 0

    new_path.parent.mkdir(parents=True, exist_ok=True)
    for init_file in [repo_root / str(path) for path in plan["init_files"]]:
        if init_file == shim_path:
            continue
        atomic_write_text(init_file, '"""Phase 5/6 decomposition package."""\n')
    subprocess.run(["git", "mv", str(old_path), str(new_path)], cwd=repo_root, check=True)
    for path, updated in updates.items():
        atomic_write_text(path, updated)
    shim_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(shim_path, shim)
    _append_shim_record(
        repo_root=repo_root,
        old_module=old_module,
        new_module=new_module,
        old_path=shim_path,
        new_path=new_path,
        names=names,
    )
    print(json.dumps(plan, indent=2, ensure_ascii=False))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="from_module", required=True)
    parser.add_argument("--to", dest="to_module", required=True)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        return move_module(
            args.repo_root.resolve(),
            args.from_module,
            args.to_module,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(f"move_module failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
