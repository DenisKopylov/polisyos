"""Read immutable Git trees and pinned family heads; never execute product code."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--repo", required=True)
parser.add_argument("--base", required=True)
parser.add_argument("--candidate", required=True)
parser.add_argument(
    "--families", required=True, help="JSON family -> head, optional base/allowed_source_paths"
)
parser.add_argument("--output", required=True)
args = parser.parse_args()
repo = Path(args.repo).resolve()


def git(*command: str, check: bool = True) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", "-C", str(repo), *command], capture_output=True, check=check)


def resolve(ref: str) -> str:
    return git("rev-parse", ref).stdout.decode().strip()


def tree(sha: str) -> dict[str, dict[str, str]]:
    records = {}
    for item in git("ls-tree", "-r", "-z", sha).stdout.split(b"\0"):
        if not item:
            continue
        metadata, path = item.split(b"\t", 1)
        mode, kind, blob = metadata.decode().split()
        records[path.decode()] = {"mode": mode, "kind": kind, "blob": blob}
    return records


def changed(before: str, after: str) -> list[dict[str, str]]:
    tokens = git("diff", "--name-status", "-z", "--no-renames", before, after).stdout.split(b"\0")
    return [
        {"status": tokens[i].decode(), "path": tokens[i + 1].decode()}
        for i in range(0, len(tokens) - 1, 2)
    ]


def category(path: str) -> str:
    if path.startswith("policy-engine/tests/") or "/tests/" in path:
        return "test_or_fixture"
    if (
        "/implementation-handoffs/" in path
        or "/integration/checks/" in path
        or "/coordination-evidence/" in path
    ):
        return "handoff_or_evidence_companion"
    if path.startswith("policy-engine/release-fragments/"):
        return "release_fragment"
    if path.startswith("policy-engine/docs/") or Path(path).suffix == ".md":
        return "documentation"
    if Path(path).suffix in {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh"}:
        return "production_source"
    return "other_tracked"


base, candidate = resolve(args.base), resolve(args.candidate)
base_tree, candidate_tree = tree(base), tree(candidate)
head_before = resolve("HEAD")
family_spec_path = Path(args.families)
family_spec = json.loads(family_spec_path.read_text())
assert len(family_spec) == 6, "Exact six-family denominator required from root"
family_results = {}
source_owners = defaultdict(list)
tracked_owners = defaultdict(list)
source_mismatches = []
lease_violations = []
lease_missing = []

for name, spec in sorted(family_spec.items()):
    head = resolve(spec["head"])
    family_base = resolve(spec.get("base", base))
    ancestor = git("merge-base", "--is-ancestor", head, candidate, check=False).returncode == 0
    head_tree = tree(head)
    delta = changed(family_base, head)
    sources = [row["path"] for row in delta if category(row["path"]) == "production_source"]
    for change in delta:
        tracked_owners[change["path"]].append(name)
    allowed = spec.get("allowed_source_paths")
    if allowed is None:
        lease_missing.append(name)
    for path in sources:
        source_owners[path].append(name)
        if head_tree.get(path) != candidate_tree.get(path):
            source_mismatches.append(
                {
                    "family": name,
                    "path": path,
                    "head_blob": head_tree.get(path),
                    "candidate_blob": candidate_tree.get(path),
                }
            )
        if allowed is not None and not any(
            fnmatch.fnmatchcase(path, pattern) for pattern in allowed
        ):
            lease_violations.append({"family": name, "path": path})
    family_results[name] = {
        "head": head,
        "base": family_base,
        "ancestor_of_candidate": ancestor,
        "complete_changed_path_count": len(delta),
        "by_category": dict(sorted(Counter(category(row["path"]) for row in delta).items())),
        "unused_authorized_source_basenames": spec.get("unused_authorized_source_basenames", []),
        "production_source_paths": sources,
        "allowed_source_paths": allowed,
        "lease_basis": spec.get("lease_basis", "root supplied pinned family specification"),
    }

rows = []
for change in changed(base, candidate):
    path = change["path"]
    rows.append(
        {
            **change,
            "path": path,
            "category": category(path),
            "file_type": Path(path).suffix or "<none>",
            "base_blob": base_tree.get(path),
            "candidate_blob": candidate_tree.get(path),
            "family_delta_membership": tracked_owners.get(path, []),
            "source_owners": source_owners.get(path, [])
            if category(path) == "production_source"
            else [],
        }
    )
root_sources = {row["path"] for row in rows if row["category"] == "production_source"}
unattributed = sorted(root_sources - set(source_owners))
source_overlap = {path: owners for path, owners in sorted(source_owners.items()) if len(owners) > 1}
known_guard = {
    "A-generation_cycle": "policy-engine/src/polisyos/runtime/quality/generation_cycle.py",
    "A-run_lifecycle": "policy-engine/src/polisyos/runtime/http/services/control/run_lifecycle.py",
    "C-streaming": "policy-engine/src/polisyos/fabric/data_plane/streaming.py",
}
basename_guards = sorted(
    path
    for path in set(base_tree) | set(candidate_tree)
    if path.startswith("policy-engine/src/")
    and Path(path).name in {"generation_cycle.py", "run_lifecycle.py", "streaming.py"}
)
guards = [
    {
        "guard": name,
        "path": path,
        "base_blob": base_tree.get(path),
        "candidate_blob": candidate_tree.get(path),
        "zero_byte_and_mode_diff": base_tree.get(path) == candidate_tree.get(path),
        "exists_both": path in base_tree and path in candidate_tree,
    }
    for name, path in sorted(known_guard.items())
]
additional_guards = [
    {
        "path": path,
        "zero_byte_and_mode_diff": base_tree.get(path) == candidate_tree.get(path),
        "base_blob": base_tree.get(path),
        "candidate_blob": candidate_tree.get(path),
    }
    for path in basename_guards
    if path not in known_guard.values()
]
family_failure = [
    name for name, result in family_results.items() if not result["ancestor_of_candidate"]
]
head_after = resolve("HEAD")
tracked_worktree_status = git("status", "--porcelain=v1", "--untracked-files=no").stdout.decode()
working_source_diffs = [
    path
    for path in git("diff", "--name-only", candidate).stdout.decode().splitlines()
    if category(path) == "production_source"
]
problems = dict(
    family_heads_not_ancestors=family_failure,
    unattributed_production_source_paths=unattributed,
    cross_family_production_source_paths=source_overlap,
    source_blob_mismatches=source_mismatches,
    source_lease_violations=lease_violations,
    missing_lease_specification=lease_missing,
    working_source_diffs_from_candidate=working_source_diffs,
    frozen_HEAD_mismatch=[] if head_before == head_after == candidate else [head_before, head_after, candidate],
    tracked_worktree_changes=tracked_worktree_status.splitlines(),
)
failures = any(
    value for key, value in problems.items() if key != "missing_lease_specification"
) or any(not g["zero_byte_and_mode_diff"] or not g["exists_both"] for g in guards) or any(not g["zero_byte_and_mode_diff"] for g in additional_guards)
verdict = (
    "FAIL"
    if failures
    else (
        "BOUNDED_SOURCE_PROVENANCE_PASS_LEASE_AUTHORIZATION_NOT_ESTABLISHED"
        if lease_missing
        else "PASS"
    )
)
result = {
    "schema": "policyos.e02.final_footprint_census.v1",
    "unit": "B",
    "predicate_basis": "recomputed",
    "command_argv": [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:]],
    "cwd": str(Path.cwd()),
    "environment": {
        "python": sys.version,
        "platform": platform.platform(),
        "git": git("--version").stdout.decode().strip(),
    },
    "input_closure": {
        "repo": str(repo),
        "base_sha": base,
        "base_tree": resolve(base + "^{tree}"),
        "candidate_sha": candidate,
        "candidate_tree": resolve(candidate + "^{tree}"),
        "actual_HEAD_before": head_before,
        "actual_HEAD_after": head_after,
        "frozen_HEAD_matches": head_before == head_after == candidate,
        "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "family_spec_path": str(family_spec_path.resolve()),
        "family_spec_sha256": hashlib.sha256(family_spec_path.read_bytes()).hexdigest(),
        "all_trees": "complete git ls-tree -r -z; differences via no-renames NUL-delimited git diff; object IDs compare content and executable mode",
        "production_execution": "none; no checkout/create/mutations or runtime tests",
    },
    "denominator": {
        "base_tracked_paths": len(base_tree),
        "candidate_tracked_paths": len(candidate_tree),
        "union_tracked_paths": len(set(base_tree) | set(candidate_tree)),
        "complete_changed_tracked_paths": len(rows),
        "by_category": dict(sorted(Counter(row["category"] for row in rows).items())),
        "by_file_type": dict(sorted(Counter(row["file_type"] for row in rows).items())),
        "by_change_status": dict(sorted(Counter(row["status"] for row in rows).items())),
        "pinned_family_heads": len(family_results),
        "A_C_owned_paths": len(guards),
        "all_matching_guard_source_basenames": len(basename_guards),
    },
    "family_results": family_results,
    "owned_A_C_guards": guards,
    "additional_basename_guards": additional_guards,
    "changed_paths": rows,
    "cross_family_tracked_path_overlaps": [{"path": path, "category": category(path), "families": names} for path, names in sorted(tracked_owners.items()) if len(names) > 1],
    "root_only_changed_paths": [row["path"] for row in rows if not row["family_delta_membership"]],
    "family_delta_paths_absent_from_final_diff": sorted(set(tracked_owners) - {row["path"] for row in rows}),
    "problems": problems,
    "verdict": verdict,
    "limitations": [
        "Finite immutable Git/source provenance census only; no runtime correctness, dataset behavior or opaque external consumer claim.",
        "Intended ownership is checked only against explicit root-supplied source leases; missing leases remain not_established rather than inferred from commit authors or file presence.",
        "Handoff/evidence/doc/release paths are counted separately from mechanism source and tests; complete changed tracked denominator remains included.",
    ],
}
assert sum(result["denominator"]["by_category"].values()) == len(rows)
assert sum(result["denominator"]["by_file_type"].values()) == len(rows)
Path(args.output).write_text(json.dumps(result, separators=(",", ":")) + "\n")
print(  # noqa: T201 - deciding census stdout
    json.dumps(
        {
            "verdict": verdict,
            "denominator": result["denominator"],
            "problems": problems,
            "output": args.output,
            "sha256": hashlib.sha256(Path(args.output).read_bytes()).hexdigest(),
        },
        separators=(",", ":"),
    )
)
