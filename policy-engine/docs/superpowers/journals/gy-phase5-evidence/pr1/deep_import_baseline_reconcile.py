"""Reconcile actual slice/current findings and prove deletion tightens the ratchet."""

# ruff: noqa: S101, S603, T201 - retained local Git provenance and owner removal witness

import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from tools.devx.architecture import guardrails as owner

root = Path.cwd()
evidence = root / "docs/superpowers/journals/gy-phase5-evidence/pr1"
current = json.loads((evidence / "deep-import-current-complete.json").read_text())
base = json.loads((evidence / "deep-import-base-complete.json").read_text())
provenance = []


def git(*arguments: str) -> str:
    command = ["git", *arguments]
    result = subprocess.run(command, cwd=root, capture_output=True, text=True, check=False)
    provenance.append(
        {
            "argv": command,
            "cwd": str(root),
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    )
    assert result.returncode == 0
    return result.stdout


git("status", "-sb")
git("rev-parse", "HEAD")
git("-C", base["root"], "rev-parse", "HEAD")
git("show", "68689784a", "--", "src/polisyos/runtime/quality/acquisition_planner.py")
changed = {
    path.removeprefix("policy-engine/")
    for path in git("diff", "--name-only", "3d572c146", "HEAD").splitlines()
}
input_paths = set(current["complete_observed_input_hashes"]) | set(
    base["complete_observed_input_hashes"]
)
current_edges = current["complete_owner_expected_identities"]
base_edges = base["complete_owner_expected_identities"]
assert current_edges == base_edges
assert current["complete_frozen_identities"] == base["complete_frozen_identities"]
stale = current["frozen_absent_from_expected"]
assert stale == base["frozen_absent_from_expected"]
assert current["expected_absent_from_frozen"] == []
scratch = root / ".tmp/gyphase5-deep-import-ratchet"
scratch.mkdir(parents=True, exist_ok=True)
scratch_baseline = scratch / "owner-expected.json"
real_edges = owner.collect_deep_import_edges(
    owner._parse_public_surface(owner.DEFAULT_PUBLIC_MANIFEST)
)
scratch_baseline.write_text(owner.render_deep_import_baseline_json(real_edges))
happy = owner._check_deep_import_creep(baseline_path=scratch_baseline, current_edges=real_edges)
removal = [
    asdict(issue)
    for issue in owner._check_deep_import_creep(
        baseline_path=scratch_baseline,
        current_edges=[
            *real_edges,
            *(owner.DeepImportEdge(**current["complete_frozen_identities"][key]) for key in stale),
        ],
    )
]
assert happy == []
assert {issue["source_module"] + "->" + issue["target_module"] for issue in removal} == set(stale)
packet = {
    "git_provenance_commands": provenance,
    "complete_actual_expected_sets_equal": current_edges == base_edges,
    "complete_frozen_sets_equal": current["complete_frozen_identities"]
    == base["complete_frozen_identities"],
    "current_expected_added_identities": sorted(current_edges.keys() - base_edges.keys()),
    "current_expected_removed_identities": sorted(base_edges.keys() - current_edges.keys()),
    "full_expected_identity_set": sorted(current_edges),
    "full_frozen_identity_set": sorted(current["complete_frozen_identities"]),
    "stale_identities": stale,
    "complete_changed_paths": sorted(changed),
    "complete_observed_source_denominator_intersection": sorted(changed & input_paths),
    "comparison_input_value_changes": {
        key: {
            "slice": base["complete_observed_input_hashes"].get(key, "ABSENT"),
            "current": current["complete_observed_input_hashes"].get(key, "ABSENT"),
        }
        for key in sorted(input_paths)
        if base["complete_observed_input_hashes"].get(key, "ABSENT")
        != current["complete_observed_input_hashes"].get(key, "ABSENT")
    },
    "tightened_baseline_happy_creep_findings": [],
    "tightened_baseline_reintroduced_stale_edge_findings": removal,
    "scope": (
        "Focused actual baseline owner, not full architecture guardrails; "
        "no P41 inherited-gate claim."
    ),
}
target = evidence / "deep-import-complete-delta.json"
target.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
print(
    json.dumps(
        {
            "evidence": str(target),
            "stale_identities": stale,
            "complete_actual_expected_sets_equal": packet["complete_actual_expected_sets_equal"],
            "tightening_falsifier": removal,
            "complete_observed_source_denominator_intersection": packet[
                "complete_observed_source_denominator_intersection"
            ],
        },
        indent=2,
    )
)
