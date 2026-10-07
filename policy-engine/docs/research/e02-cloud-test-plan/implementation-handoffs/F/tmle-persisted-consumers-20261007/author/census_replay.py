"""Reconcile every actual fresh-reader observation with the complete JUnit set."""
import collections
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

scratch = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent
rows = []
raw = (scratch / "native.stdout.txt").read_bytes()
for line in raw.decode().splitlines():
    candidate = line.lstrip(".")
    if not candidate.startswith("{"):
        continue
    try:
        row = json.loads(candidate)
    except json.JSONDecodeError:
        continue
    if "child_exit" in row:
        row["measured"] = json.loads(row["child_stdout"].splitlines()[-1])
        rows.append(row)
suite = ET.parse(scratch / "native.xml").getroot().find("testsuite")
assert suite is not None
assert len(rows) == int(suite.attrib["tests"]) == 53
assert all(suite.attrib[key] == "0" for key in ("errors", "failures", "skipped"))
assert all(row["child_exit"] == 0 for row in rows)
for key in ("bundle_id", "report_id", "source_id", "report_method", "report_status", "point"):
    assert len({json.dumps(row["measured"][key]) for row in rows}) == 1, key
forged = [row for row in rows if row["case"].get("relabelled", True)]
assert len(forged) == 52
assert len({tuple(row["case"][key] for key in ("simulation_kind", "simulation_location", "causal_location", "min_ratio")) for row in forged}) == 52
assert sum(bool(row["child_stderr"]) for row in rows) == 36
summary = {
    "schema": "policyos.e02.native_consumer_census.v1",
    "source_sha": "0c81614f5aa737a4b26c6c74044955a842b26cf4",
    "suite_attributes": suite.attrib,
    "actual_fresh_readers": len(rows),
    "forged_envelope_reader_cases": len(forged),
    "unmodified_native_reader_cases": 1,
    "simulation_failed_load_warnings": 36,
    "pytest_warnings": 0,
    "test_cases": [case.attrib for case in suite.findall("testcase")],
    "case_denominator": [row["case"] for row in rows],
    "single_report_identity": {key: rows[0]["measured"][key] for key in ("bundle_id", "report_id", "source_id", "report_method", "report_status", "point", "ci", "persisted_envelope_point", "persisted_envelope_ci")},
    "value_refusal_counts": dict(collections.Counter(row["measured"]["value_refusal"]["reason_code"] for row in rows)),
    "causal_blocker_counts": dict(collections.Counter(str(sum(issue["severity"] == "blocker" and issue["path"] == ["artifacts_index", "causal_envelope_ref"] for issue in row["measured"]["confidence_issues"])) for row in rows)),
    "full_stdout": {"path": str(scratch / "native.stdout.txt"), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
    "limits": ["Known synthetic bounded DGP and configured two-fold one-repeat consumer fixture; no real-data, coverage, cache or default-fold rerun.", "Upstream value contract refused; downstream gate predicate not reached.", "Positive statistical/operational authority and actual admitted competing-study budget remain UNRUN."],
}
(scratch / "native-census.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({key: summary[key] for key in ("actual_fresh_readers", "forged_envelope_reader_cases", "simulation_failed_load_warnings", "pytest_warnings", "value_refusal_counts", "causal_blocker_counts")}))
