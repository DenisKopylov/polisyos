from __future__ import annotations

from tools.quality.validation.decomposition_preflight import validate_public_surface_snapshot


def test_public_surface_snapshot_gate_matches_phase3a_baseline() -> None:
    findings = validate_public_surface_snapshot()

    assert findings == [], "\n".join(finding.render() for finding in findings)
