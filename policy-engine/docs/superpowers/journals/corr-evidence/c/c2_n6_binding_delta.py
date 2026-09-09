"""Reconcile the complete pre-admission observations after the report ancestry repair."""

import json
import sys
from pathlib import Path

from .c2_n6_projection import _iterative, _recursive


def main() -> None:
    root = Path(__file__).parent
    prior = json.loads((root / "c2-n6-reissue-binding.json").read_text())
    current = json.loads((root / "c2-n6-reissue-ancestry-binding.json").read_text())
    left = json.loads(prior["stdout"].splitlines()[0])
    right = json.loads(current["stdout"].splitlines()[0])
    for value in (left, right):
        if _recursive(value) != _iterative(value):
            raise ValueError("independent_complete_observation_sets_disagree")
    old_deltas = {tuple(item["identity"]): item for item in left.pop("differences")}
    new_deltas = {tuple(item["identity"]): item for item in right.pop("differences")}
    additional = new_deltas.keys() - old_deltas.keys()
    removed = old_deltas.keys() - new_deltas.keys()
    changed = {
        key for key in old_deltas.keys() & new_deltas.keys() if old_deltas[key] != new_deltas[key]
    }
    if additional != {("synthetic",)} or removed or changed:
        raise ValueError("report_ancestry_delta_not_isolated")
    new_hashes = {
        key: right[key] for key in ("current_comparison_hash", "current_reissue_projection_hash")
    }
    for key in new_hashes:
        left.pop(key)
        right.pop(key)
    if left != right:
        raise ValueError("historical_or_admission_binding_changed")
    sys.stdout.write(
        json.dumps(
            {
                "denominator": "complete previous/current pre-admission observation packets",
                "recursive_iterative_identity_value_sets_equal": True,
                "additional_difference_identities": sorted(additional),
                "removed_difference_identities": sorted(removed),
                "changed_existing_difference_identities": sorted(changed),
                "new_delta": new_deltas[("synthetic",)],
                "all_historical_and_admission_values_equal": True,
                "current_bindings": new_hashes,
            },
            sort_keys=True,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
