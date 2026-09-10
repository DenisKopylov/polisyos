"""A recorded authority decision must not turn an unrelated HTTP 409 into evidence."""
import copy
import json
from pathlib import Path
from tools.quality.validation import check_layer3_workflow_failure_authority as owner

payload = json.loads(Path(owner.HISTORICAL_PROOF_PATH).read_text())
results = []
for proof in payload["proofs"]:
    for observed in proof["surface_readbacks"]:
        if observed["surface"] not in {"public_packet"}:
            continue
        changed = copy.deepcopy(observed)
        changed["error_code"] = "unrelated_conflict"
        issues = []
        owner._validate_readback(proof["scenario"], changed, issues)
        results.append({"scenario": proof["scenario"], "surface": observed["surface"], "issues": issues})
print(json.dumps({"historical_source": owner.HISTORICAL_PROOF_PATH,
                  "historical_sha256": owner.HISTORICAL_PROOF_SHA256,
                  "mutation": "status409 and authority decision stay; actual response code unrelated",
                  "results": results}, sort_keys=True))
assert all(any(row["code"] == "workflow_public_authority_response_invalid" for row in result["issues"]) for result in results)
