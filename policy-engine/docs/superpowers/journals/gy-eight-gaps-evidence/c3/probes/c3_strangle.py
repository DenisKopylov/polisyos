"""Recompute the C3 default fence; semantic evidence stays in the removal receipts."""
from __future__ import annotations

import ast
import contextlib
import importlib
import io
import json
from pathlib import Path
import subprocess
import sys


def main() -> None:
    census = importlib.import_module(
        "docs.superpowers.journals.gy-eight-gaps-evidence.c1.probes.caller_census"
    )
    census.TERMINALS = {
        "FoundryMethodOutputConsumer", "consume_from_state", "persist_consumption",
        "verify_recorded_panel_method_input", "_verify_method_replay",
        "_require_verified_consumption",
    }
    sys.argv.append("--static-only")
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        census.main()
    callers = json.loads(out.getvalue())
    path = "src/polisyos/runtime/quality/workspace/foundry_consumption.py"
    tree = ast.parse(Path(path).read_text())
    definitions = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    removed = {"_pdc_ref_from_core", "_input_provenance", "_is_typed_artifact_ref"}
    assert not definitions.intersection(removed)
    calls = [row for row in callers["calls"] if row["kind"] == "production"]
    admitted = [row for row in calls if row["call"].endswith("consume_from_state")]
    assert admitted and all(row["path"].endswith("workspace/loop.py") for row in admitted)
    fields = subprocess.check_output([
        "git", "diff", "--numstat", "34852d5b2b3b511b7f0583a6316b2156e4e2dcb9", "--", path,
    ], text=True).strip().split("\t")
    patch = subprocess.check_output([
        "git", "diff", "--no-ext-diff", "--unified=0",
        "34852d5b2b3b511b7f0583a6316b2156e4e2dcb9", "--", path,
    ], text=True)
    removed_lines = sum(line.startswith("-") and not line.startswith("---")
                        for line in patch.splitlines())
    assert removed_lines == int(fields[1]) and removed_lines > 0
    print(json.dumps({
        "receipt_id": "layer3-gy-c3-content-consumption-strangle",
        "predecessor_ref": path + "@34852d5b2b3b511b7f0583a6316b2156e4e2dcb9",
        "replacement_ref": path,
        "disposition": "fenced_default_flipped",
        "default_before": "ref_description_hash_and_kind_based_measurement",
        "default_after": "verified_recorded_binding_and_recomputed_method_output",
        "guard_ref": "test_foundry_consumer_refuses_nonobservations_and_unrelated_cas_documents",
        "deleted_predecessor_functions": sorted(removed),
        "removed_loc": {"git_numstat": int(fields[1]), "patch_lines": removed_lines},
        "remaining_callers": callers,
        "remaining_callers_disposition": "consumer remains the only authority emission seam; missing store/binding refuses",
        "verified_by": ["consumer-final-green.json", "consumer-removal-wave.json"],
        "limitation": "These static identities establish the default fence; only the separately retained live removal probes establish the semantic property. Full C3 is blocked.",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
