"""Measure one ledger projection witness; internal research CLI, not an allocation gate.

Run from the product root with its source/tools on PYTHONPATH. The only output
format is JSON. This calls the actual ledger owner and does not register tasks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from tools.lib.fs import measure_file_reads, measured_read_text
from tools.quality.validation import check_debt_ledger as owner


def probe(root: Path) -> dict[str, Any]:
    """Derive projection loss only from a read registration and actual owner output."""
    failures: list[dict[str, str]] = []
    actual: list[dict[str, Any]] = []
    projected: list[Any] = []
    ids: set[str] = set()
    paths: list[Path] = []
    with measure_file_reads(root) as reads:
        try:
            text = measured_read_text(root / owner.GY_PATH)
            for number, line in enumerate(text.splitlines(), 1):
                match = owner._GY_TASK_ROW.match(line)
                if match and match.group(1) == "GY-AQ1":
                    actual.append({"line": number, "groups": match.groups()})
            projected = owner._parse_gy_tasks(text)
        except (OSError, UnicodeError) as error:
            failures.append({"boundary": str(owner.GY_PATH), "error": type(error).__name__})
        try:
            ids, _, paths = owner._plan_inventory(root)
        except (OSError, UnicodeError) as error:
            failures.append({"boundary": "ledger plan inventory", "error": type(error).__name__})
        measurement = owner._measurement_receipt(reads, complete_verdict=not failures)
    selected_projection = [row._asdict() for row in projected if row.slice_id == "GY-AQ1"]
    reproduced = bool(actual) and not selected_projection if not failures else None
    return {
        "status": "UNRUN" if failures else "COMPLETE",
        "coverage": "partial" if failures else "complete_over_selected_inputs",
        "property": "An actual GY-AQ1 registration is filtered from the owner's open-work output.",
        "counterexample": "Delete the registration but retain its token: projection loss is false.",
        "selector": {
            "registration": str(owner.GY_PATH),
            "identity": "GY-AQ1 via the actual owner's case-sensitive GY table grammar",
            "inventory_roots": [str(path) for path in owner.PLAN_ROOTS],
            "inventory_id_rule": "numeric DS IDs from filenames; not generic task ownership",
        },
        "measurement": measurement,
        "failures": failures,
        "unresolved_by_construction": [
            *measurement["unresolved_by_construction"],
            "Documents/registrations outside the selected GY grammar are not interpreted.",
            "Semantic aliases and accepted ownership acts are not inferred from tokens "
            "or filenames.",
            "A missing GY-AQ1 row is not absence of its task elsewhere.",
        ],
        "actual_registered_GY_AQ1": actual,
        "projected_GY_AQ1": selected_projection,
        "inventory_ids": sorted(ids),
        "inventory_paths": [str(path.relative_to(root)) for path in paths],
        "projection_loss_reproduced": reproduced,
        "conclusion": (
            "UNRUN: selected input unreadable; projection-loss property is undecided."
            if failures
            else "Existing-registration projection loss reproduced."
            if reproduced
            else "Projection loss not reproduced within the selected inputs."
        ),
    }


def main() -> int:
    """Print the full measured JSON result and fail if the witness is not established."""
    result = probe(Path.cwd())
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    return 2 if result["status"] == "UNRUN" else 0 if result["projection_loss_reproduced"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
