"""Read the new commit from its attached branch and compare its entire file set."""

import argparse
import json
import subprocess
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
repo = Path.cwd().parent


def git(*arguments):
    return subprocess.check_output(["git", "-C", str(repo), *arguments])


branch = git("symbolic-ref", "-q", "HEAD").decode().strip()
assert branch == "refs/heads/codex/gy-eight-gaps", branch
sha = git("rev-parse", branch).decode().strip()
paths = set(git("diff-tree", "--no-commit-id", "--name-only", "-r", "-z", sha).decode().strip("\0").split("\0"))
independent = {
    row.split("\t", 2)[2]
    for row in git("show", "--format=", "--numstat", sha).decode().splitlines() if row
}
assert paths == independent
mismatches = [
    path for path in sorted(paths)
    if git("show", f"{branch}:{path}") != (repo / path).read_bytes()
]
clean = not git("status", "--porcelain").strip()
receipt = {
    "branch": branch, "commit": sha,
    "complete_changed_path_denominator": len(paths),
    "independent_numstat_count": len(independent),
    "branch_bytes_match_working_tree": not mismatches, "mismatches": mismatches,
    "tracked_tree_clean": clean,
}
args.output.write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
assert not mismatches and clean
