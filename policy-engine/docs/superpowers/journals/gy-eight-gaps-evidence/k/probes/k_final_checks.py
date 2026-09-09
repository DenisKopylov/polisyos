"""Reconcile the complete canonical K finding sets and unchanged history bytes."""

import hashlib
import json
from pathlib import Path
import subprocess


root = Path.cwd()
directory = root / "_build/gy-gaps/k"


def read_report(name, code):
    raw = (directory / name).read_bytes()
    receipt = json.loads(raw)
    assert receipt["returncode"] == code and receipt["timed_out"] is False
    report = json.loads(receipt["stdout"])
    identities = [json.dumps(issue, sort_keys=True) for issue in report["issues"]]
    assert len(identities) == len(set(identities))
    return receipt, report, set(identities), hashlib.sha256(raw).hexdigest()


baseline, report, baseline_ids, baseline_sha = read_report("canonical-check.json", 0)
assert report["status"] == "pass" and not baseline_ids
assert "precision" in report["accuracy"] and report["accuracy"]["precision"] is None
assert "recall" in report["accuracy"] and report["accuracy"]["recall"] is None
assert report["accuracy"]["accuracy_status"] == "withheld_pending_adjudicator_appointment"
deltas = []
for name, expected_codes in (
    ("canonical-corrupt.json", {"layer3_gy_openalex_corrupt_field_drift_detected"}),
    ("canonical-corrupt-substance.json", {
        "layer3_gy_openalex_accuracy_substantive_recompute_drift",
        "layer3_gy_openalex_artifact_drift",
    }),
):
    receipt, mutant_report, mutant_ids, digest = read_report(name, 1)
    assert mutant_report["status"] == "fail"
    assert not baseline_ids - mutant_ids
    added = mutant_ids - baseline_ids
    assert {json.loads(identity)["code"] for identity in added} == expected_codes
    deltas.append({"receipt": name, "receipt_sha256": digest,
                   "added_identities": [json.loads(item) for item in sorted(added)],
                   "lost_baseline_identities": []})

raw_receipt = json.loads((directory / "canonical-corrupt-substance.json").read_bytes())
marker = '{\n  "source_ref":'
metadata = json.loads(raw_receipt["stderr"][raw_receipt["stderr"].index(marker):])
current_path = root / metadata["source_ref"]
assert hashlib.sha256(current_path.read_bytes()).hexdigest() == metadata["raw_sha256_before"]
current = json.loads(current_path.read_bytes())
predictions = {
    (observation["case_id"], prediction["claim"]["claim_id"])
    for observation in current["accuracy"]["observations"]
    for prediction in observation["predictions"]
    if isinstance(prediction.get("claim"), dict)
}
independent = []
for observation in current["accuracy"]["observations"]:
    for prediction in observation["predictions"]:
        if isinstance(prediction.get("claim"), dict):
            independent.append((observation["case_id"], prediction["claim"]["claim_id"]))
assert predictions == set(independent) and len(predictions) == len(independent)
assert predictions == {tuple(identity) for identity in metadata["complete_changed_prediction_identities"]}
history = []
for filename in ("layer3_gy_openalex_accuracy_report.json", "layer3_gy_openalex_skg_ingest_records.json"):
    relative = "architecture/policy_design_case/" + filename
    before = subprocess.check_output(["git", "show", f"HEAD:policy-engine/{relative}"])
    after = (root / relative).read_bytes()
    assert before == after
    history.append({"path": relative, "sha256": hashlib.sha256(after).hexdigest(),
                    "unchanged_from_parent_commit": True})
print(json.dumps({
    "baseline_receipt": "canonical-check.json", "baseline_receipt_sha256": baseline_sha,
    "finding_identity_deltas": deltas,
    "complete_current_prediction_denominator": len(predictions),
    "independent_nested_walk_count": len(independent),
    "all_prediction_identities_mutated": True,
    "historical_output_denominator": len(history), "complete_history": history,
    "current_precision_and_recall": "present_and_null_with_explicit_appointment_refusal",
}, indent=2))
