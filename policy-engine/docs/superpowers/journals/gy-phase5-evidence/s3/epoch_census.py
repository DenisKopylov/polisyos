"""Enumerate every git-visible old/new S3 epoch binding without decoding omissions."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[5]
    paths = sorted(set(subprocess.check_output(
        ["git", "ls-files", "-co", "--exclude-standard", "-z"], cwd=root,
    ).decode().split("\0")) - {""})
    keys = ["policyos.runtime.intervention_substrate_lift.v1",
            "policyos.runtime.intervention_substrate_lift.v2",
            "policyos.policy_design_case.layer3_gy.intervention_substrate_contract.v1",
            "policyos.policy_design_case.layer3_gy.intervention_substrate_contract.v2",
            "policyos.foundry.method_selection_context.v3",
            "policyos.foundry.method_selection_context.v4",
            "policyos.runtime.grounding_credal_reference.v1",
            "policyos.runtime.grounding_credal_reference.v2"]
    first, second, ambiguous = set(), set(), []
    for name in paths:
        path = root / name
        if not path.is_file():
            ambiguous.append({"path": name, "reason": "not_readable_file"})
            continue
        try:
            raw = path.read_bytes()
        except OSError as exc:
            ambiguous.append({"path": name, "reason": str(exc)})
            continue
        for key in keys:
            target = key.encode()
            for line, value in enumerate(raw.splitlines(), 1):
                if target in value:
                    first.add((name, line, key))
            for match in re.finditer(re.escape(target), raw):
                second.add((name, raw[:match.start()].count(b"\n") + 1, key))
    rows = []
    for name, line, key in sorted(first):
        kind = ("historical_evidence" if name.startswith("docs/superpowers/")
                or "fixtures/intervention_law_lift_v1.json" in name else
                "current_generated_owner" if name.startswith("architecture/") else
                "current_source_or_companion")
        rows.append({"path": name, "line": line, "key": key, "classification": kind})
    print(json.dumps({"denominator": paths, "file_type": "all git-visible file bytes",
                      "findings": rows, "ambiguous": ambiguous,
                      "first_only": sorted(first-second), "second_only": sorted(second-first)},
                     indent=2))
    assert first == second


if __name__ == "__main__":
    main()
