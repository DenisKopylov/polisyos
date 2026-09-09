"""Observe the existing N6 writer's complete historical/current owner projections."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from polisyos.pdc import GyComparisonProjectionPlan


def _recursive(value: object, path: tuple[str, ...] = ()) -> dict[tuple[str, ...], object]:
    result: dict[tuple[str, ...], object] = {path: {"node_type": type(value).__name__}}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(_recursive(item, (*path, str(key))))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            result.update(_recursive(item, (*path, str(index))))
    else:
        result[path] = {"node_type": type(value).__name__, "value": value}
    return result


def _iterative(value: object) -> dict[tuple[str, ...], object]:
    result = {}
    pending = [((), value)]
    while pending:
        path, item = pending.pop()
        result[path] = {"node_type": type(item).__name__}
        if isinstance(item, dict):
            pending.extend(((*path, str(key)), child) for key, child in item.items())
        elif isinstance(item, list):
            pending.extend(((*path, str(index)), child) for index, child in enumerate(item))
        else:
            result[path] = {"node_type": type(item).__name__, "value": item}
    return result


def main() -> None:
    """Retain deltas, then call the unchanged comparison owner and preserve its refusal."""
    from tools.quality.validation import check_layer3_gy_generation_cycle_contract as owner

    original = owner._reconcile_frozen_contract

    def observe(
        repo_root: Path, live: dict[str, object], plan: GyComparisonProjectionPlan
    ) -> dict[str, object]:
        frozen = json.loads((repo_root / owner.OUTPUT_PATH).read_bytes())
        old_plan = owner.build_gy_comparison_projection_plan_from_manifest(
            frozen,
            manifest=frozen["comparison_admission_manifest"],
            owner_rule_registry=owner.canonical_promotion_verification_comparison_owner_rule_registry(),
        )
        excluded = owner._CONTENT_HASH_EXCLUDED_TOP_LEVEL | owner._COMPARISON_IDENTITY_FIELDS
        old = old_plan.project({key: value for key, value in frozen.items() if key not in excluded})
        new = plan.project({key: value for key, value in live.items() if key not in excluded})
        left, right = _recursive(old), _recursive(new)
        if left != _iterative(old) or right != _iterative(new):
            raise ValueError("independent_projection_enumerations_disagree")
        differences = [
            {
                "identity": identity,
                "old_present": identity in left,
                "new_present": identity in right,
                "old": left.get(identity, "ABSENT"),
                "new": right.get(identity, "ABSENT"),
            }
            for identity in sorted(left.keys() | right.keys())
            if identity not in left or identity not in right or left[identity] != right[identity]
        ]
        sys.stdout.write(
            json.dumps(
                {
                    "denominator": "complete existing owner-projected historical/current envelopes",
                    "recursive_iterative_identity_and_value_sets_equal": True,
                    "historical_contract_hash_valid": frozen["contract_content_hash"]
                    == owner._contract_content_hash(frozen),
                    "historical_comparison_hash_valid": frozen["comparison_content_hash"]
                    == owner._comparison_content_hash(frozen, old_plan),
                    "old_manifest": old_plan.manifest,
                    "new_manifest": plan.manifest,
                    "differences": differences,
                },
                sort_keys=True,
            )
            + "\n"
        )
        sys.stdout.flush()
        return original(repo_root, live, plan)

    owner._reconcile_frozen_contract = observe
    owner.build_contract_json_for_write(Path.cwd())


if __name__ == "__main__":
    main()
