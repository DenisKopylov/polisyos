"""Complete tracked textual fan-out of the existing F1 proof identity."""
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path


def test_f1_tracked_consumers_are_enumerated():
    extensions = {".py", ".toml", ".json", ".md"}
    forbidden = {"DEBT-REGISTER.md", "LEDGER.md"}
    tracked = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    paths = sorted(path for path in tracked if path and Path(path).suffix in extensions and Path(path).name not in forbidden)
    second = subprocess.check_output(["git", "ls-files", "-z", "--", "*.py", "*.toml", "*.json", "*.md"]).decode().split("\0")
    independent = sorted(path for path in second if path and Path(path).name not in forbidden)
    assert paths == independent
    needles = (
        "layer3_gy_workflow_failure_authority_proofs.json",
        "layer3_gy.workflow_failure_authority.v1",
        "check_layer3_workflow_failure_authority",
    )
    matches = []
    unreadable = []
    for relative in paths:
        try:
            raw = Path(relative).read_bytes()
            source = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            unreadable.append({"path": relative, "status": "ambiguous", "reason": str(exc)})
            continue
        findings = [{"line": index, "bindings": [needle for needle in needles if needle in line]}
                    for index, line in enumerate(source.splitlines(), 1)
                    if any(needle in line for needle in needles)]
        if findings:
            matches.append({"path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "finding_identities": findings})
    print(json.dumps({
        "file_type_denominator": dict(sorted(Counter(Path(path).suffix for path in paths).items())),
        "total_file_denominator": len(paths),
        "independent_git_glob_denominator": len(independent),
        "excluded_by_user": sorted(forbidden),
        "unreadable": unreadable,
        "matches": matches,
    }, sort_keys=True, indent=2))
