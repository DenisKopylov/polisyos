"""Reconcile complete architecture JSON source-member records and preserved owners."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def records(value):
    if isinstance(value, dict):
        if value.get("member_kind") == "source":
            yield value
        for child in value.values():
            yield from records(child)
    elif isinstance(value, list):
        for child in value:
            yield from records(child)


if __name__ == "__main__":
    root = Path.cwd()
    first = set((root / "architecture").rglob("*.json"))
    second = {
        Path(directory) / name
        for directory, _, files in os.walk(root / "architecture")
        for name in files if name.endswith(".json")
    }
    assert first == second
    target = "module:polisyos.runtime.http.services.control_plane_store"
    new_target = "module:polisyos.runtime.quality.adaptation_transition"
    structured_count = 0
    textual_count = 0
    matching = []
    new_matches = []
    ambiguous = []
    for path in sorted(first):
        try:
            text = path.read_text()
            payload = json.loads(text)
        except (OSError, UnicodeError, ValueError):
            ambiguous.append(str(path.relative_to(root)))
            continue
        members = list(records(payload))
        structured_count += len(members)
        textual_count += len(re.findall(r'"member_kind"\s*:\s*"source"', text))
        for member in members:
            if member.get("member_id") == target:
                matching.append({"artifact": str(path.relative_to(root)), **member})
            if member.get("member_id") == new_target:
                new_matches.append(str(path.relative_to(root)))
    assert not ambiguous
    assert structured_count == textual_count
    preserved = []
    for relative in (
        "src/polisyos/runtime/http/services/control_plane_store.py",
        "src/polisyos/core/artifacts/ownership.py",
        "src/polisyos/fabric/io/atomic.py",
    ):
        before = subprocess.check_output(["git", "show", f"07c89304d:policy-engine/{relative}"])
        after = (root / relative).read_bytes()
        assert before == after
        preserved.append({"path": relative, "sha256": hashlib.sha256(after).hexdigest()})
    sys.stdout.write(json.dumps({
        "denominator": "architecture/**/*.json", "rglob_files": len(first),
        "os_walk_files": len(second), "identity_sets_equal": True,
        "unreadable_ambiguous": ambiguous,
        "source_member_dict_occurrences": structured_count,
        "independent_literal_source_member_occurrences": textual_count,
        "exact_existing_owner_member_records": matching,
        "new_module_recorded_source_member_matches": new_matches,
        "preserved_owner_bytes_against_lane_base": preserved,
        "scope": "recorded source-member dictionary identities; not inferred transitive closure",
    }, indent=2) + "\n")
