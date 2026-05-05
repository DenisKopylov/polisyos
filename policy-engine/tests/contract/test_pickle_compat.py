from __future__ import annotations

from tools.quality.validation.decomposition_preflight import validate_pickle_fixtures


def test_pickle_compat_gate_loads_canonical_checkpoint_fixtures() -> None:
    findings = validate_pickle_fixtures()

    assert findings == [], "\n".join(finding.render() for finding in findings)
