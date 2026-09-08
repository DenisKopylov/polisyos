"""Observe actual N9 frozen/live comparison without changing its disposition."""

# ruff: noqa: ANN001, ANN201, SIM114, SIM401, T201 - historical read-only observer
import json
from pathlib import Path

from tools.quality.validation import check_layer3_gy_promotion_contract as owner

root = Path.cwd()
destination = root / ".tmp/gyphase5-promotion-comparison-diagnostic"
destination.mkdir(parents=True, exist_ok=True)
original = owner._reconcile_frozen_contract
missing = object()


def lookup(value, path):
    for part in path:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, (list, tuple)) and isinstance(part, int) and part < len(value):
            value = value[part]
        else:
            return missing
    return value


def describe(value):
    return {"presence": "absent"} if value is missing else {"presence": "present", "value": value}


def diff(left, right, path=()):
    if isinstance(left, dict) and isinstance(right, dict):
        return [
            row
            for key in sorted(set(left) | set(right))
            for row in diff(
                left[key] if key in left else missing,
                right[key] if key in right else missing,
                (*path, key),
            )
        ]
    if isinstance(left, (list, tuple)) and isinstance(right, (list, tuple)):
        return [
            row
            for index in range(max(len(left), len(right)))
            for row in diff(
                left[index] if index < len(left) else missing,
                right[index] if index < len(right) else missing,
                (*path, index),
            )
        ]
    if type(left) is not type(right) or left != right:
        return [{"path": list(path), "frozen": describe(left), "live": describe(right)}]
    return []


def observe(repo_root, live, plan):
    frozen = json.loads((repo_root / owner.OUTPUT_PATH).read_text())
    comparisons = []
    for entry in plan.entries:
        left = lookup(frozen, entry.path)
        right = lookup(live, entry.path)
        item = {
            "admitted_path": list(entry.path),
            "owner_rule": str(entry.owner_rule),
            "action": str(entry.action),
        }
        try:
            left_projection = entry.projector(left)
            right_projection = entry.projector(right)
            item.update(
                {
                    "frozen_projection": left_projection,
                    "live_projection": right_projection,
                    "differences": diff(left_projection, right_projection),
                }
            )
        except Exception as error:
            item["projection_error"] = {"type": type(error).__name__, "message": str(error)}
        comparisons.append(item)
    packet = {
        "frozen_payload": frozen,
        "live_payload": live,
        "comparison_manifest": plan.manifest,
        "admitted_comparisons": comparisons,
        "full_payload_differences": diff(frozen, live),
    }
    (destination / "complete-observation.json").write_text(
        json.dumps(packet, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                "observation": str(destination / "complete-observation.json"),
                "admitted_differences": [
                    {
                        key: value
                        for key, value in item.items()
                        if key not in {"frozen_projection", "live_projection"}
                    }
                    for item in comparisons
                ],
            },
            indent=2,
        ),
        flush=True,
    )
    return original(repo_root, live, plan)


owner._reconcile_frozen_contract = observe
raise SystemExit(owner.main(["--check", "--output-format", "json"]))
