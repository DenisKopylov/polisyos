"""Inventory literal source writers for the persisted governance replay inputs."""

from __future__ import annotations

import ast
import sys
from collections import Counter
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[6] / "src" / "polisyos"
TARGET_KINDS = {
    "core.registry_bundle",
    "fabric.data_snapshot",
    "foundry.input_bindings",
    "foundry.state_snapshot",
    "ir.trinity_bundle",
    "lex.norm_pack",
    "scholar.knowledge_bundle",
    "scholar.research_intent",
}


def _module_constants(tree: ast.Module) -> dict[str, object]:
    values: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
            value = node.value
        else:
            continue
        try:
            resolved = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
        for name in names:
            values[name] = resolved
    return values


def _source_literal(node: ast.expr | None, constants: dict[str, object]) -> object | None:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        if isinstance(node, ast.Name):
            return constants.get(node.id)
        return None


def _emit(value: object) -> None:
    sys.stdout.write(f"{value}\n")


def main() -> None:
    files = sorted(SOURCE.rglob("*.py"))
    parsed: list[tuple[Path, ast.Module]] = []
    global_constants: dict[str, set[object]] = {}
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        parsed.append((path, tree))
        for name, value in _module_constants(tree).items():
            try:
                global_constants.setdefault(name, set()).add(value)
            except TypeError:
                continue

    rows: list[tuple[str, int, str, str, str, str]] = []
    for path, tree in parsed:
        constants = _module_constants(tree)
        for node in tree.body:
            if not isinstance(node, ast.ImportFrom):
                continue
            for item in node.names:
                values = global_constants.get(item.name, set())
                if len(values) == 1:
                    constants[item.asname or item.name] = next(iter(values))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            function = ast.unparse(node.func)
            short_name = function.rsplit(".", 1)[-1]
            keywords = {item.arg: item.value for item in node.keywords if item.arg}
            kind = _source_literal(keywords.get("kind"), constants)
            if not isinstance(kind, str) or kind not in TARGET_KINDS:
                continue
            if short_name in {"PutOptions", "ArtifactWriteOptions"}:
                media = _source_literal(keywords.get("media_type"), constants)
                schema = ast.unparse(keywords["schema"]) if "schema" in keywords else "None"
            elif short_name == "put_json_artifact":
                media = "application/json (helper contract)"
                schema = ":".join(
                    ast.unparse(keywords[key])
                    for key in ("schema_name", "schema_version")
                    if key in keywords
                )
            elif short_name == "_cas_put_json":
                media = "application/json (helper contract)"
                schema = "None (helper contract)"
            elif short_name == "_put_registry":
                media = "application/json (_put_registry helper)"
                schema = "_schema_info(name, obj); returns None without payload.schema_version"
            else:
                continue
            rows.append(
                (
                    str(path.relative_to(SOURCE.parent)),
                    node.lineno,
                    kind,
                    str(media),
                    schema,
                    short_name,
                )
            )

    for row in sorted(rows):
        _emit("\t".join(map(str, row)))
    _emit(f"SOURCE_PY_FILES={len(files)}")
    _emit(f"PARSED_SOURCE_PY_FILES={len(parsed)}")
    _emit(f"WRITER_CALLS={len(rows)}")
    for kind, count in sorted(Counter(row[2] for row in rows).items()):
        _emit(f"KIND_COUNT[{kind}]={count}")
    _emit(f"RESEARCH_INTENT_WRITERS={sum(row[2] == 'scholar.research_intent' for row in rows)}")


if __name__ == "__main__":
    main()
