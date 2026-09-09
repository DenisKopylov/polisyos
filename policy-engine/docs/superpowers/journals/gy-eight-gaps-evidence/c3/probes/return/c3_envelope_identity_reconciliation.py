"""Reconcile actual pytest outcome identities for the bounded C3 repair."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def outcomes(path: Path) -> tuple[dict[str, object], dict[str, str]]:
    receipt = json.loads(path.read_bytes())
    rows = re.findall(r"^(PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS) (.+)$", receipt["stdout"], re.M)
    identities = {identity: status for status, identity in rows}
    if len(rows) != len(identities):
        raise RuntimeError(f"duplicate pytest outcome identities in {path}")
    return receipt, identities


def main() -> int:
    folder = Path("_build/gy-gaps/c3")
    baseline_path = folder / "envelope-intake-final-green.json"
    baseline, identities = outcomes(baseline_path)
    progress = re.findall(r"^([.FEsxX]+)\s+\[\s*\d+%\]", baseline["stdout"], re.M)
    if (
        baseline["returncode"] != 0 or baseline["timed_out"]
        or not identities or set(identities.values()) != {"PASSED"}
        or sum(len(row) for row in progress) != len(identities)
    ):
        raise RuntimeError("baseline outcome identities/progress/exit do not reconcile")
    deltas = []
    for name in (
        "intake-readback-removal.json", "intake-context-removal.json",
        "intake-lineage-presence-removal.json", "envelope-dispatch-removal.json",
        "envelope-source-equality-removal.json",
    ):
        path = folder / name
        receipt, observed = outcomes(path)
        failures = {identity for identity, status in observed.items() if status == "FAILED"}
        if (
            receipt["returncode"] != 1 or receipt["timed_out"]
            or not failures or set(observed) - identities.keys()
            or set(observed.values()) - {"PASSED", "FAILED"}
        ):
            raise RuntimeError(f"unexpected or missing removal result identities: {name}")
        deltas.append({
            "receipt": f"{path}@sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}",
            "selected_observed_denominator": len(observed),
            "baseline_pass_to_fail": sorted(failures),
            "baseline_pass_preserved": sorted(set(observed) - failures),
            "identities_not_in_baseline": sorted(set(observed) - identities.keys()),
        })
    print(json.dumps({  # noqa: T201 - complete deciding identity diff
        "baseline_receipt": (
            f"{baseline_path}@sha256:{hashlib.sha256(baseline_path.read_bytes()).hexdigest()}"
        ),
        "baseline_passed_identity_count": len(identities),
        "independent_progress_result_count": sum(len(row) for row in progress),
        "comparison_scope": (
            "each explicitly selected removal control, not the unrun baseline remainder"
        ),
        "deltas": deltas,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
