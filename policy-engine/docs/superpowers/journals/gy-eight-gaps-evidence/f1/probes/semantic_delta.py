"""Whole absence-aware semantic comparison; no runtime replay and no copied inputs."""
import hashlib
import json
from pathlib import Path
from tools.quality.validation import check_layer3_workflow_failure_authority as owner

root = Path.cwd()
receipt_path = root / "_build/gy-gaps/f1/canonical-check.json"
receipt = json.loads(receipt_path.read_text())
report = json.loads(receipt["stdout"])
current_path = root / owner.PROOF_PATH
original = json.loads(current_path.read_text())
fresh = report["recomputed_proofs"]

def changes(before, after, path=()):
    if type(before) is not type(after):
        return [{"path": list(path), "before": before, "after": after}]
    if isinstance(before, dict):
        rows = []
        for key in sorted(before.keys() | after.keys()):
            if key not in before or key not in after:
                rows.append({"path": [*path, key], "before_present": key in before,
                             "after_present": key in after,
                             **({"before": before[key]} if key in before else {}),
                             **({"after": after[key]} if key in after else {})})
            else:
                rows.extend(changes(before[key], after[key], (*path, key)))
        return rows
    if isinstance(before, list):
        rows = []
        for index in range(max(len(before), len(after))):
            if index >= len(before) or index >= len(after):
                rows.append({"path": [*path, index], "before_present": index < len(before),
                             "after_present": index < len(after),
                             **({"before": before[index]} if index < len(before) else {}),
                             **({"after": after[index]} if index < len(after) else {})})
            else:
                rows.extend(changes(before[index], after[index], (*path, index)))
        return rows
    return [] if before == after else [{"path": list(path), "before": before, "after": after}]

before = owner.comparison_payload(original)
after = owner.comparison_payload(fresh)
delta = changes(before, after)
print(json.dumps({"committed_source": owner.PROOF_PATH,
                  "committed_sha256": hashlib.sha256(current_path.read_bytes()).hexdigest(),
                  "recomputed_source": str(receipt_path.relative_to(root)) + "::stdout.recomputed_proofs",
                  "recomputed_payload_sha256": hashlib.sha256((json.dumps(fresh, indent=2, sort_keys=True) + "\n").encode()).hexdigest(),
                  "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                  "complete_semantic_delta": delta}, sort_keys=True))
raise SystemExit(1 if delta else 0)
