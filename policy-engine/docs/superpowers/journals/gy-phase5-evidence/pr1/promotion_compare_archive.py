"""Archive complete observed comparison and independently reconcile field identities."""

# ruff: noqa: ANN001, ANN201, S101, S603, T201 - bounded research reconciliation
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

root = Path.cwd()
scratch = root / ".tmp/gyphase5-promotion-comparison-diagnostic"
destination = root / "docs/superpowers/journals/gy-phase5-evidence/pr1"
observed = json.loads((scratch / "complete-observation.json").read_text())


def leaf_map(value):
    result = {}
    stack = [((), value)]
    while stack:
        path, current = stack.pop()
        if isinstance(current, dict) and current:
            stack.extend(((*path, key), child) for key, child in current.items())
        elif isinstance(current, list) and current:
            stack.extend(((*path, index), child) for index, child in enumerate(current))
        else:
            result[path] = {"type": type(current).__name__, "value": current}
    return result


reconciled = []
for comparison in observed["admitted_comparisons"]:
    left = leaf_map(comparison["frozen_projection"])
    right = leaf_map(comparison["live_projection"])
    differences = {
        path
        for path in set(left) | set(right)
        if path not in left or path not in right or left[path] != right[path]
    }
    recursive = {tuple(item["path"]) for item in comparison["differences"]}
    assert differences == recursive
    reconciled.append(
        {
            "admitted_path": comparison["admitted_path"],
            "frozen_leaf_identities": [list(path) for path in sorted(left, key=repr)],
            "live_leaf_identities": [list(path) for path in sorted(right, key=repr)],
            "shape_identity_difference": [
                list(path) for path in sorted(set(left) ^ set(right), key=repr)
            ],
            "independent_differing_field_identities": [
                list(path) for path in sorted(differences, key=repr)
            ],
            "recursive_differing_field_identities": [
                list(path) for path in sorted(recursive, key=repr)
            ],
            "identity_sets_equal": differences == recursive,
        }
    )

paths = [
    "src/polisyos/runtime/quality/promotion_sequence.py",
    "tools/quality/validation/check_layer3_gy_promotion_contract.py",
    "architecture/policy_design_case/layer3_gy_promotion_contract.json",
    "src/polisyos/runtime/quality/credal_reference.py",
]
sources = []
commands = []
for relative in paths:
    argv = ["git", "show", f"3d572c146:policy-engine/{relative}"]
    result = subprocess.run(argv, cwd=root, capture_output=True)
    assert result.returncode == 0
    base = result.stdout
    current = (root / relative).read_bytes()
    sources.append(
        {
            "path": relative,
            "slice_base_sha256": hashlib.sha256(base).hexdigest(),
            "current_sha256": hashlib.sha256(current).hexdigest(),
            "bytes_equal": base == current,
        }
    )
    commands.append(
        {
            "argv": argv,
            "cwd": str(root),
            "returncode": result.returncode,
            "stdout": base.decode(),
            "stderr": result.stderr.decode(),
        }
    )

packet = {
    "denominator": (
        "Every admitted path in the actual ephemeral N9 comparison plan and every leaf of both "
        "complete owner-produced semantic projections; four explicit source/capture paths are "
        "a bounded attribution comparison, not an import-closure census."
    ),
    "admitted_plan_manifest": observed["comparison_manifest"],
    "independent_reconciliation": reconciled,
    "bounded_source_attribution": sources,
    "source_read_commands": commands,
    "p41": (
        "Exact slice-base gate replay and complete input-disjointness were not executed; no "
        "inherited finding claim. The measured governing epoch delta is introduced by S3 D1b."
    ),
}
(destination / "promotion-comparison-identity-reconciliation.json").write_text(
    json.dumps(packet, indent=2, sort_keys=True) + "\n"
)
for original, name in [
    (scratch / "complete-observation.json", "promotion-comparison-complete-observation.json"),
    (scratch / "command.json", "promotion-comparison-command.json"),
    (root / ".tmp/gyphase5_promotion_compare_observer.py", "promotion_compare_observer.py"),
    (root / ".tmp/gyphase5_promotion_compare_runner.py", "promotion_compare_runner.py"),
    (Path(__file__), "promotion_compare_archive.py"),
]:
    shutil.copyfile(original, destination / name)
print(
    json.dumps(
        {
            "reconciled_admitted_paths": [row["admitted_path"] for row in reconciled],
            "differing_field_identities": [
                {
                    "admitted_path": row["admitted_path"],
                    "fields": row["independent_differing_field_identities"],
                }
                for row in reconciled
            ],
            "bounded_source_attribution": sources,
        },
        indent=2,
    )
)
