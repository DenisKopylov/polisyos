from __future__ import annotations

from tools.quality.validation.decomposition_preflight import validate_schema_diff


def test_schema_diff_gate_matches_phase3a_baseline() -> None:
    findings = validate_schema_diff()

    assert findings == [], "\n".join(finding.render() for finding in findings)
