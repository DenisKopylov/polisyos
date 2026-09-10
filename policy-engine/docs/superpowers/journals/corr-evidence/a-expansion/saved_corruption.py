"""Use the existing surgical corruption owner against only the new saved report."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = Path(__file__).resolve().parents[5]


def main() -> int:
    """Require live drift evidence and exact restoration, not an exit code alone."""
    corruption = importlib.import_module(
        "docs.superpowers.journals.corr-evidence.shared.report_artifact_corruption"
    )
    artifact = (HERE / "2026-09-09-refusal-expansion.json").relative_to(ROOT)
    original = json.loads((ROOT / artifact).read_bytes())
    previous = original["families"][0]["intended_mismatch_detected_count"]
    if type(previous) is not int:
        raise ValueError("deciding_detection_count_is_not_an_integer")
    evidence = corruption.run_probe(
        artifact=artifact,
        # runpy is the standard module launcher, preserving the real checker's
        # qualified namespace without changing the shared owner's identifier rule.
        checker_module="runpy",
        checker_args=[
            "docs.superpowers.journals.corr-evidence.a-expansion.suite",
            "--check",
            "--execution-receipt",
            str((HERE / "official-write.json").relative_to(ROOT)),
        ],
        pointer="/families/0/intended_mismatch_detected_count",
        replacement=previous + 1,
        timeout_seconds=900,
        root=ROOT,
    )
    expected = {
        "refusal_expansion_saved_result_drift",
        "refusal_expansion_original_execution_capture_mismatch",
    }
    observed: set[str] | None = None
    try:
        payload = json.loads(evidence["stdout"])
        if isinstance(payload, dict) and isinstance(payload["issues"], list):
            observed = set(payload["issues"])
    except (ValueError, KeyError, TypeError):
        pass  # A malformed child output is a nonreceipt, never the intended red.
    passed = (
        evidence["disposition"] == "completed"
        and evidence["returncode"] == 1
        and evidence["byte_identical_restoration"] is True
        and evidence["only_selected_token_changed"] is True
        and observed == expected
    )
    result = {
        **evidence,
        "schema_version": "corr.refusal_expansion_saved_corruption.v1",
        "synthetic": True,
        "expected_issues": sorted(expected),
        "observed_issues": sorted(observed) if observed is not None else None,
        "property_passed": passed,
    }
    sys.stdout.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
