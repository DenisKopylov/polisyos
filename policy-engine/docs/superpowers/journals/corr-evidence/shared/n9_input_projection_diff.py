"""Measure complete owning projections without migrating or rewriting any receipt."""

from __future__ import annotations

import hashlib
import json
import sys
from collections import deque
from pathlib import Path

from tools.quality.validation import check_layer3_gy_promotion_contract as checker


def _children(value: object) -> list[tuple[str, object]]:
    if isinstance(value, dict):
        return [(str(key).replace("~", "~0").replace("/", "~1"), child)
                for key, child in value.items()]
    if isinstance(value, list):
        return [(str(index), child) for index, child in enumerate(value)]
    return []


def _walk(value: object, path: str = "") -> dict[str, object]:
    children = _children(value)
    result = {path: {"kind": type(value).__name__, "value": value}} if not children else {}
    for key, child in children:
        result.update(_walk(child, path + "/" + key))
    return result


def _independent_walk(value: object) -> dict[str, object]:
    pending = deque([((), value)])
    result = {}
    while pending:
        parts, item = pending.popleft()
        if isinstance(item, dict) and item:
            for key in item:
                escaped = str(key).replace("~", "~0").replace("/", "~1")
                pending.append(((*parts, escaped), item[key]))
        elif isinstance(item, list) and item:
            pending.extend(((*parts, str(index)), item[index]) for index in range(len(item)))
        else:
            result["/" + "/".join(parts) if parts else ""] = {
                "kind": type(item).__name__, "value": item,
            }
    return result


def main() -> None:
    root = Path.cwd()
    previous_raw = (root / checker.OUTPUT_PATH).read_bytes()
    previous = json.loads(previous_raw)
    current, plan = checker._build_payload_with_comparison_plan(root)
    scratch = root / ".tmp/corr-n9-live-before-reissue.json"
    scratch.write_text(json.dumps(current, sort_keys=True))
    excluded = checker._CONTENT_HASH_EXCLUDED_TOP_LEVEL | checker._COMPARISON_IDENTITY_FIELDS
    before = plan.project({key: value for key, value in previous.items() if key not in excluded})
    after = plan.project({key: value for key, value in current.items() if key not in excluded})
    old, new = _walk(before), _walk(after)
    old2, new2 = _independent_walk(before), _independent_walk(after)
    if old != old2 or new != new2:
        raise ValueError("owning_projection_independent_enumeration_mismatch")
    absent = {"kind": "absent"}
    findings = {
        path: {"before": old.get(path, absent), "after": new.get(path, absent)}
        for path in sorted(old.keys() | new.keys())
        if path not in old or path not in new or old[path] != new[path]
    }
    independent_findings = {
        path for path in old2.keys() | new2.keys()
        if path not in old2 or path not in new2 or old2[path] != new2[path]
    }
    if set(findings) != independent_findings:
        raise ValueError("owning_projection_finding_identity_mismatch")
    sys.stdout.write(json.dumps({
        "historical_path": checker.OUTPUT_PATH,
        "historical_bytes_sha256": hashlib.sha256(previous_raw).hexdigest(),
        "current_runtime_output": str(scratch.relative_to(root)),
        "denominator": "complete JSON leaves and empty containers in both typed owning projections",
        "historical_identities": len(old), "current_identities": len(new),
        "finding_count": len(findings), "independent_identity_sets_equal": True,
        "findings": findings,
    }, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
