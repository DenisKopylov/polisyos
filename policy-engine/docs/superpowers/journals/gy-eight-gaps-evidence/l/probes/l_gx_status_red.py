"""Decisive GY-L status omission against the actual admitting validator."""
import copy
import json
from pathlib import Path
from tools.quality.validation import check_layer3_gy_loop_artifacts as owner


def main():
    root = Path.cwd()
    outcome = json.loads((root / owner.OUTCOME_RUN_PATH).read_text())
    replay = json.loads((root / owner.OUTCOME_REPLAY_PATH).read_text())
    baseline = []
    owner.validate_outcome_run(outcome, replay, baseline)
    rows = []
    for label, value in (("fail", "fail"), ("expected_red", "expected_red"),
                         ("not_measured", "not_measured"), ("null", None),
                         ("absent", None), ("unverified_pass", "pass")):
        variant = copy.deepcopy(outcome)
        if label == "absent":
            del variant["gx_validator_status"]
        else:
            variant["gx_validator_status"] = value
        issues = []
        owner.validate_outcome_run(variant, replay, issues)
        rows.append({"variant": label, "issues": issues,
                     "refused": any("gx_validation" in i["code"] or "gx_validator" in i["code"] for i in issues)})
    print(json.dumps({"baseline_issues": baseline, "variants": rows}, indent=2))
    assert all(row["refused"] for row in rows), "Actual outcome admission accepted an unsuccessful or unverified GX status."


if __name__ == "__main__":
    main()
