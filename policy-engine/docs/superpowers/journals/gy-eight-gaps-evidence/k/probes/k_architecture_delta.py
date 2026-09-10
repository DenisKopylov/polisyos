"""Diff complete architecture finding identities across K's reviewed edge addition."""

import json
from pathlib import Path
import re


directory = Path("_build/gy-gaps/k")
pattern = re.compile(r"- New deep-import creep detected: (\S+) -> (\S+) \(([^)]+)\)\.")


def identities(name):
    receipt = json.loads((directory / name).read_bytes())
    assert receipt["returncode"] == 1 and not receipt["timed_out"]
    findings = [line for line in receipt["stdout"].splitlines() if line.startswith("- ")]
    result = set()
    edges = []
    for finding in findings:
        match = pattern.match(finding)
        if match:
            identity = match.groups()
            edges.append(identity)
            result.add(("deep_import", *identity))
        else:
            assert finding.startswith("- Deep-import baseline drift detected."), finding
            result.add(("deep_import_baseline_drift",))
    assert len(edges) == len(set(edges))
    assert len(findings) == len(result)
    return result


before = identities("architecture-boundaries.json")
after = identities("architecture-boundaries-after-k.json")
resolved = ("deep_import", "polisyos.scholar.search.providers",
            "polisyos.ir.analytics.literature", "src/polisyos/scholar/search/providers.py")
assert before - after == {resolved}
assert not after - before
print(json.dumps({
    "resolved_identities": sorted(before - after), "added_identities": [],
    "complete_remaining_identities": sorted(after),
    "remaining_disposition": "This lane's C1/C3/D1 return; not inherited or externally blocked",
}, indent=2))
