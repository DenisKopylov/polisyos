"""Corrupt every current extracted claim/span through the real committed reader."""

import copy
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from tools.quality.validation import check_layer3_gy_openalex_artifacts as owner


root = Path.cwd().resolve()
target = root / owner.ACCURACY_PATH
original = target.read_bytes()
payload = json.loads(original)
mutant = copy.deepcopy(payload)
changes = []
for observation in mutant["accuracy"]["observations"]:
    for prediction in observation["predictions"]:
        claim = prediction.get("claim")
        if not isinstance(claim, dict):
            continue
        claim["claim_text"] = "Constructed false claim absent from the selected source."
        for span in claim["supporting_spans"]:
            span["text"] = "Constructed false span absent from the selected source."
        changes.append([observation["case_id"], claim["claim_id"]])
independent = [
    [observation["case_id"], prediction["claim"]["claim_id"]]
    for observation in payload["accuracy"]["observations"]
    for prediction in observation["predictions"] if isinstance(prediction.get("claim"), dict)
]
assert changes and changes == independent
replacement = json.dumps(mutant, indent=2, sort_keys=True) + "\n"
read_text = Path.read_text
matched = []


def read_current(path, *args, **kwargs):
    if path.resolve() == target:
        matched.append(path.as_posix())
        return replacement
    return read_text(path, *args, **kwargs)


with patch.object(Path, "read_text", read_current):
    code = owner.main(["--repo-root", str(root), "--check", "--output-format", "json"])
assert matched, "The actual committed reader was not exercised"
assert target.read_bytes() == original, "Probe must not mutate the committed artifact"
print(json.dumps({
    "source_ref": owner.ACCURACY_PATH,
    "raw_sha256_before": hashlib.sha256(original).hexdigest(),
    "raw_sha256_mutant": hashlib.sha256(replacement.encode()).hexdigest(),
    "complete_changed_prediction_identities": changes,
    "independent_prediction_identity_set_equal": changes == independent,
    "delta": "Every extracted claim_text/supporting_span.text fabricated; all markers and numeric fields retained",
    "actual_reader_paths": matched,
    "actual_gate_returncode": code,
}, indent=2), file=sys.stderr)
raise SystemExit(code)
