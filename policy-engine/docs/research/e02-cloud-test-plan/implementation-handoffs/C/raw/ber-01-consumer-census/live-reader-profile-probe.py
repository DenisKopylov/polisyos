from __future__ import annotations

import json

from polisyos.runtime.quality.explanation_reliability import _validate_bundle_record
from polisyos.scientist.validation.phase5_preflight import _run_berl_validation
from tests.unit.remediation.test_ber_01 import _full_payload

results = []
for version in ("1.0.0", "1.1.0"):
    payload = _full_payload(schema_version=version)
    runtime, runtime_issues = _validate_bundle_record(
        payload,
        thresholds={},
        evidence_ref=f"synthetic://schema-census/{version}",
    )
    phase5 = _run_berl_validation(payload)
    results.append(
        {
            "profile": version,
            "runtime_threshold_status": runtime["threshold_decision"]["status"],
            "runtime_issues": [issue.code for issue in runtime_issues],
            "phase5_passed": phase5["passed"] if phase5 else None,
            "phase5_violations": phase5["violations"] if phase5 else None,
            "fixture_only": True,
        }
    )
print(json.dumps(results, indent=2, sort_keys=True))
