"""Remove actual post-output execution, retain declarations, report consumer red."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch


def main() -> int:
    from tools.quality.validation import check_layer3_gy_loop_artifacts as owner

    root = Path.cwd()
    source = Path(owner.__file__)
    raw = source.read_bytes()
    claimed = {
        "verification": {
            "schema_version": "policyos.layer3.gy.post_output_gx_verification.v1",
            "proof_source": "complete_gx_owner_on_fresh_output_family",
            "status": "pass",
            "finding_identities": [],
        }
    }
    with patch.object(owner, "_run_full_gx_on_new_artifacts", return_value=claimed):
        report = owner.validate(root)
    assert source.read_bytes() == raw
    decisive = [
        row for row in report["issues"]
        if row["code"] == "layer3_gy_live_recomputation_failed"
        and "post_gx_result_not_actual_owner_execution" in row["reason"]
    ]
    print(json.dumps({
        "control": "actual_post_output_execution_removed_markers_retained",
        "source": source.relative_to(root).as_posix(),
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_bytes_unchanged": True,
        "declared_result_kept": claimed,
        "complete_consumer_report": report,
        "decisive_refusal": decisive,
        "consumer_refused_removed_property": report["status"] == "fail" and bool(decisive),
    }, indent=2, sort_keys=True))
    assert report["status"] == "fail" and decisive, "removed execution was not refused"
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
