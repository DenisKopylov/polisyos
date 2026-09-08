"""Reconcile the complete OpenAPI JSON identities without absence/null collapse."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

type JsonPath = tuple[str | int, ...]


def recursive(value: object, path: JsonPath = ()) -> Iterator[tuple[JsonPath, object]]:
    """Walk every object, array, scalar and explicit empty container."""
    yield path, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from recursive(child, (*path, key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from recursive(child, (*path, index))


def iterative(value: object) -> dict[JsonPath, object]:
    """Independently enumerate the same full set with an explicit stack."""
    pending = [((), value)]
    result = {}
    while pending:
        path, item = pending.pop()
        result[path] = item
        if isinstance(item, dict):
            pending.extend(((*path, key), child) for key, child in item.items())
        elif isinstance(item, list):
            pending.extend(((*path, index), child) for index, child in enumerate(item))
    return result


def main() -> None:
    """Emit the complete changed identity set against the pinned slice source."""
    source = "schemas/runtime_api_v1.openapi.json"
    original = json.loads(
        subprocess.check_output(  # noqa: S603 - fixed local git read
            [  # noqa: S607 - the repository's configured git executable
                "git",
                "show",
                "3d572c146:policy-engine/" + source,
            ]
        )
    )
    current = json.loads(Path(source).read_text())
    left, right = dict(recursive(original)), dict(recursive(current))
    if left != iterative(original) or right != iterative(current):
        raise RuntimeError("independent complete JSON identities disagree")
    rows = []
    for path in sorted(left.keys() | right.keys(), key=str):
        if (
            path in left
            and path in right
            and type(left[path]) is type(right[path])
            and left[path] == right[path]
        ):
            continue
        # Emit every changed leaf and explicit empty container, not duplicate ancestors.
        values = [tree[path] for tree in (left, right) if path in tree]
        if any(isinstance(value, (dict, list)) and value for value in values):
            continue
        rows.append(
            {
                "path": list(path),
                "before_present": path in left,
                "after_present": path in right,
                **({"before": left[path]} if path in left else {}),
                **({"after": right[path]} if path in right else {}),
            }
        )
    sys.stdout.write(
        json.dumps(
            {
                "source": source,
                "base": "3d572c146",
                "denominator": (
                    "every JSON node in both complete documents; "
                    "recursive and iterative traversals agree"
                ),
                "complete_identity_sets_independently_reconciled": True,
                "added_node_identities": [
                    list(p) for p in sorted(right.keys() - left.keys(), key=str)
                ],
                "removed_node_identities": [
                    list(p) for p in sorted(left.keys() - right.keys(), key=str)
                ],
                "changed_leaf_identities": rows,
                "removed_operations": sorted(original["paths"].keys() - current["paths"].keys()),
                "added_operations": sorted(current["paths"].keys() - original["paths"].keys()),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
