"""Corrupt one decisive committed proof field at its real reader, without writing it."""
import copy
import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import patch
from tools.quality.validation import check_layer3_workflow_failure_authority as owner

actual_read = owner._read_json
expected_path = Path.cwd().resolve() / owner.PROOF_PATH
mutated_paths = []

def corrupt_read(path, issues):
    payload = actual_read(path, issues)
    if path != expected_path:
        return payload
    mutated_paths.append(str(path))
    changed = copy.deepcopy(payload)
    indices = [index for index, proof in enumerate(changed["proofs"])
               if proof["scenario"] == "legacy_shadow_candidate"]
    assert len(indices) == 1
    index = indices[0]
    before = changed["proofs"][index]["authority_result"]
    assert before == "candidate_only"
    changed["proofs"][index]["authority_result"] = "grounded_admissible"
    mutated = (json.dumps(changed, indent=2, sort_keys=True) + "\n").encode()
    print(json.dumps({"probe": "actual_committed_reader_decisive_field_corruption",
                      "path": owner.PROOF_PATH,
                      "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                      "mutated_sha256": hashlib.sha256(mutated).hexdigest(),
                      "delta": {"path": f"proofs[{index}].authority_result",
                                "before": before, "after": "grounded_admissible"}}, sort_keys=True))
    return changed

with patch.object(owner, "_read_json", corrupt_read):
    rc = owner.main(["--repo-root", str(Path.cwd().resolve()), "--check", "--output-format", "json"])
assert mutated_paths == [str(expected_path)]
print(json.dumps({"actual_mutated_reader_paths": mutated_paths}), file=sys.stderr)
raise SystemExit(rc)
