"""Read every old/current N9 artifact field and preserve the complete identity delta."""

# ruff: noqa: S101, T201 - complete historical/current readback evidence

import hashlib
import json
from pathlib import Path
from typing import Any

root = Path.cwd()
history = root / "tests/repo_quality/tools/fixtures/layer3_gy_promotion_contract_credal_v1.json"
current = root / "architecture/policy_design_case/layer3_gy_promotion_contract.json"
before_bytes = history.read_bytes()
after_bytes = current.read_bytes()
assert hashlib.sha256(before_bytes).hexdigest() == (
    "4825fd7adac74ef35a351d023dbd0069952b602b26b1c124c7795ef696f1a59a"
)
before = json.loads(before_bytes)
after = json.loads(after_bytes)


def recursive(value: object, path: tuple[str | int, ...] = ()) -> dict[tuple[str | int, ...], Any]:
    """Walk all leaves, retaining null and empty containers as explicit values."""
    if isinstance(value, dict) and value:
        return {
            key: leaf
            for member, child in value.items()
            for key, leaf in recursive(child, (*path, member)).items()
        }
    if isinstance(value, list) and value:
        return {
            key: leaf
            for index, child in enumerate(value)
            for key, leaf in recursive(child, (*path, index)).items()
        }
    return {path: {"type": type(value).__name__, "value": value}}


def iterative(value: object) -> dict[tuple[str | int, ...], Any]:
    """Independently walk the complete object using a work stack."""
    pending = [((), value)]
    found = {}
    while pending:
        path, member = pending.pop()
        if isinstance(member, dict) and member:
            pending.extend(((*path, key), child) for key, child in member.items())
        elif isinstance(member, list) and member:
            pending.extend(((*path, key), child) for key, child in enumerate(member))
        else:
            found[path] = {"type": type(member).__name__, "value": member}
    return found


left = recursive(before)
right = recursive(after)
assert left == iterative(before)
assert right == iterative(after)
all_paths = sorted(left.keys() | right.keys(), key=repr)
differences = [
    {
        "path": list(path),
        "historical": {"presence": "present", **left[path]}
        if path in left
        else {"presence": "absent"},
        "current": {"presence": "present", **right[path]}
        if path in right
        else {"presence": "absent"},
    }
    for path in all_paths
    if path not in left or path not in right or left[path] != right[path]
]
receipts = []
for admission in after["comparison_admission_manifest"]:
    key = admission["json_pointer"].removeprefix("/")
    receipt = after[key]
    reference = receipt["owner_projection"]["credal_reference"]
    receipts.append(
        {
            "identity": key,
            "receipt_schema": receipt["schema_version"],
            "credal_schema": reference["schema_version"] if reference is not None else None,
            "promoted": receipt["promoted"],
            "consumer_promotable": receipt["consumer_promotable"],
        }
    )
packet = {
    "denominator": "Every field of both complete JSON artifacts; recursive and stack walks agree.",
    "historical_sha256": hashlib.sha256(before_bytes).hexdigest(),
    "current_sha256": hashlib.sha256(after_bytes).hexdigest(),
    "historical_field_identities": [list(path) for path in sorted(left, key=repr)],
    "current_field_identities": [list(path) for path in sorted(right, key=repr)],
    "shape_identity_difference": [
        list(path) for path in sorted(left.keys() ^ right.keys(), key=repr)
    ],
    "complete_value_differences": differences,
    "current_receipt_identities": receipts,
    "authority_limit": (
        "Governed verification-only sequence artifact; no production candidate claim."
    ),
}
output = root / "docs/superpowers/journals/gy-phase5-evidence/pr1/d1d-artifact-readback.json"
output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(
    json.dumps(
        {"output": str(output), "receipts": receipts, "current_sha256": packet["current_sha256"]},
        indent=2,
    )
)
