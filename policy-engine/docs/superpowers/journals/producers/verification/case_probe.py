"""Remove the real case source-reader call in memory and run its unchanged negative.

Run from policy-engine with ``uv run python <this-path>``. Exit 1 is the expected
semantic-test failure; import/collection failure is not an accepted probe result.
The script never changes production source or test bytes.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path

import pytest

from polisyos.runtime.quality import global_case_index


def main() -> int:
    """Replace only source resolution with an empty entry tuple for this process."""
    source_path = Path(global_case_index.__file__)
    module = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    producer = next(
        node
        for node in module.body
        if isinstance(node, ast.ClassDef) and node.name == "GlobalCaseIndexProducer"
    )
    method = copy.deepcopy(
        next(
            node
            for node in producer.body
            if isinstance(node, ast.FunctionDef) and node.name == "produce"
        )
    )
    changed = 0
    for node in ast.walk(method):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(target, ast.Name) and target.id == "entries" for target in node.targets
        ):
            continue
        if not any(
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == "_resolve_entry"
            for child in ast.walk(node.value)
        ):
            raise AssertionError("entries assignment no longer invokes the canonical reader")
        node.value = ast.Tuple(elts=[], ctx=ast.Load())
        changed += 1
    if changed != 1:
        raise AssertionError(f"expected one source-reader assignment, found {changed}")
    replacement = ast.fix_missing_locations(ast.Module(body=[method], type_ignores=[]))
    namespace = vars(global_case_index).copy()
    exec(compile(replacement, str(source_path), "exec"), namespace)  # noqa: S102
    global_case_index.GlobalCaseIndexProducer.produce = namespace["produce"]
    return pytest.main(
        [
            "tests/unit/runtime/http/test_capability_discovery_api.py::"
            "test_case_provider_refuses_invalid_persisted_binding",
            "-q",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
