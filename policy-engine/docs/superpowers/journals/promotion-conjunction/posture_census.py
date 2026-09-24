"""Census direct named posture constructors; dynamic deserialization stays unresolved."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

TARGETS = frozenset({
    "Layer2S6BlindSpotPostureInput",
    "Layer2S7DelegationPostureInput",
    "Layer2S8ValuePostureInput",
})


def main() -> int:
    """Read every source Python file and emit the complete census as JSON."""
    files = sorted(Path("src").rglob("*.py"))
    result = subprocess.run(
        ["git", "ls-files", "src"],  # noqa: S607 - the repository Git on PATH is the owner.
        check=True, capture_output=True, text=True,
    )
    tracked = {path for path in result.stdout.splitlines() if path.endswith(".py")}
    read, unread, rows = [], [], []
    named_refs: dict[str, list[dict[str, object]]] = {name: [] for name in sorted(TARGETS)}
    for path in files:
        try:
            content = path.read_bytes()
            tree = ast.parse(content, filename=str(path))
            read.append({"path": str(path), "sha256": hashlib.sha256(content).hexdigest()})
        except (OSError, SyntaxError) as exc:
            unread.append({"path": str(path), "reason": str(exc)})
            continue
        aliases = {name: name for name in TARGETS}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in TARGETS:
                        aliases[alias.asname or alias.name] = alias.name

        def name_of(node: ast.AST, aliases: dict[str, str] = aliases) -> str | None:
            if isinstance(node, ast.Name):
                return aliases.get(node.id)
            if isinstance(node, ast.Attribute) and node.attr in TARGETS:
                return node.attr
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.Name, ast.Attribute)):
                target = name_of(node)
                if target:
                    named_refs[target].append({"path": str(path), "line": node.lineno})
            if not isinstance(node, ast.Call):
                continue
            target, mechanism = name_of(node.func), "constructor"
            if (not target and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {
                        "model_validate", "model_validate_json", "model_construct",
                    }):
                target, mechanism = name_of(node.func.value), node.func.attr
            if target:
                rows.append({
                    "dto": target, "path": str(path), "line": node.lineno,
                    "mechanism": mechanism,
                    "source": ast.get_source_segment(content.decode(), node),
                })
    payload = {
        "predicate": "direct named DTO constructor or model_validate/model_validate_json/"
        "model_construct call, import aliases resolved; entire src/**/*.py AST set",
        "file_type_denominator": len(files),
        "independent_git_tracked_python_count": len(tracked),
        "untracked_python": sorted(set(map(str, files)) - tracked),
        "tracked_missing_on_disk": sorted(tracked - set(map(str, files))),
        "inputs_read": read, "unreadable_members": unread,
        "producer_calls": rows, "named_refs": named_refs,
        "unresolved_by_construction": [
            "dynamic_attribute_or_factory_dispatch_not_named_for_these_DTOs",
            "semantic_admission_not_inferred_from_constructor_presence",
        ],
    }
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")
    return 1 if unread else 0


if __name__ == "__main__":
    raise SystemExit(main())
