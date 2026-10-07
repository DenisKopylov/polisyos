import dataclasses
import json
import subprocess
import sys
from pathlib import Path

from tools.devx.architecture import guardrails as g

root = Path("/workspace/e02-E-cal-review-20261006")
output = Path("/workspace/e02-E-pr38-r3-receipts/imports-r4")
policies = g._parse_public_surface(g.DEFAULT_PUBLIC_MANIFEST)
files = g._iter_py_files()
edges = g.collect_deep_import_edges(policies)
violations = g._check_deep_import_creep(
    baseline_path=g.DEFAULT_DEEP_IMPORT_BASELINE, current_edges=edges
)
receipt = {
    "source_sha": subprocess.check_output(["/usr/bin/git", "rev-parse", "HEAD"], cwd=root)
    .decode()
    .strip(),
    "python_source_denominator": len(files),
    "deep_edge_count": len(edges),
    "violation_count": len(violations),
    "complete_edges": [dataclasses.asdict(e) for e in edges],
    "complete_violations": [dataclasses.asdict(v) for v in violations],
    "scope": (
        "Actual architecture deep-import collector/check before exceptions; "
        "not full guardrails result"
    ),
}
(output / "current-deep-imports-after.json").write_text(json.dumps(receipt, indent=2) + "\n")
sys.stdout.write(
    str({key: value for key, value in receipt.items() if not isinstance(value, list)}) + "\n"
)
for violation in violations:
    sys.stdout.write(violation.message + "\n")
