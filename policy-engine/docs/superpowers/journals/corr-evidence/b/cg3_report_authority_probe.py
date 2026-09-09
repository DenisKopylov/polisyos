"""Require the existing CG3 report gate to reject synthetic authority claims."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tools.quality.validation import check_grounding_admission_contract as owner


def main() -> None:
    """Corrupt only the claimed source/authority relationship in a real capture."""
    payload = json.loads(Path(owner.OUTPUT_PATH).read_bytes())
    payload["schema_version"] = owner.SCHEMA_VERSION
    payload["synthetic"] = True
    positive = payload["probes"]["admit_real_novel_data_only_free_grow"]
    positive["synthetic"] = True
    positive["authority_limitation"] = "synthetic_input_cannot_grant_authority"
    positive["production_promotable"] = True
    report = owner.validate_payload(payload)
    codes = sorted({row["code"] for row in report["issues"]})
    result = {"gate_status": report["status"], "issue_codes": codes}
    sys.stdout.write(json.dumps(result, indent=2) + "\n")
    if "grounding_admission_synthetic_authority_escape" not in codes:
        raise AssertionError("report accepted a synthetic authority claim")


if __name__ == "__main__":
    main()
