"""Compare complete public-export identities using two independent traversals."""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path


def main() -> None:
    """Retain every export identity and require only the admitted facade additions."""
    walkers = importlib.import_module(
        "docs.superpowers.journals.gy-phase5-evidence.shared.openapi_delta"
    )
    path = "architecture/public_surface/inventory.json"
    old = json.loads(subprocess.check_output(  # noqa: S603 — fixed local git read.
        ["git", "show", "3d572c146:policy-engine/" + path]  # noqa: S607
    ))
    new = json.loads(Path(path).read_text())
    versions = {}
    for label, value in (("slice_base", old), ("current", new)):
        recursive = dict(walkers.recursive(value))
        iterative = walkers.iterative(value)
        if recursive != iterative:
            raise ValueError("complete_inventory_traversals_disagree")
        identities = {
            (item["module"], export)
            for item in recursive.values()
            if isinstance(item, dict) and "module" in item and "exports" in item
            for export in item["exports"]
        }
        versions[label] = identities
    added = versions["current"] - versions["slice_base"]
    removed = versions["slice_base"] - versions["current"]
    expected = {
        ("polisyos.core.contracts", "ControlJobResponse"),
        ("polisyos.foundry", "MethodRouteConstraint"),
        ("polisyos.foundry", "method_accepts_input_contract"),
    }
    sys.stdout.write(json.dumps({
        "path_denominator": path,
        "file_type_denominator": "complete JSON document, every module/export identity",
        "independent_recursive_and_iterative_identity_walks_agree": True,
        "identity_sets": {key: sorted(value) for key, value in versions.items()},
        "added": sorted(added),
        "removed": sorted(removed),
        "expected_additions": sorted(expected),
    }, indent=2) + "\n")
    if added != expected or removed:
        raise ValueError("public_export_delta_outside_decision")


if __name__ == "__main__":
    main()
