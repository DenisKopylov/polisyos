"""Read a specified attached commit and disclose the actual working-tree status."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--expected-branch", required=True)
    parser.add_argument("--allow-untracked", action="append", default=[])
    parser.add_argument("--require-untracked", nargs=2, action="append", default=[],
                        metavar=("PATH", "SHA256"))
    args = parser.parse_args()
    root = args.repo_root.resolve()
    branch = args.expected_branch.removeprefix("refs/heads/")
    report = {"repo_root": str(root), "expected_branch": "refs/heads/" + branch,
              "expected_commit": args.expected_commit, "status": "fail"}

    def git(*arguments):
        return subprocess.check_output(
            ["git", "--no-optional-locks", "--literal-pathspecs", "-C", str(root), *arguments], stderr=subprocess.PIPE
        )

    def position():
        return {"branch": git("symbolic-ref", "-q", "HEAD").decode().strip(),
                "head": git("rev-parse", "HEAD").decode().strip(),
                "branch_head": git("rev-parse", report["expected_branch"]).decode().strip()}

    def statuses():
        raw = git("-c", "status.renames=false", "status", "--porcelain=v1", "-z",
                  "--untracked-files=all")
        return [{"xy": os.fsdecode(row[:2]), "path": os.fsdecode(row[3:]),
                 "scope": "product" if row[3:].startswith(b"policy-engine/") else "outside_product"}
                for row in raw.split(b"\0") if row]

    try:
        require(re.fullmatch(r"[0-9a-f]{40}(?:[0-9a-f]{24})?", args.expected_commit),
                "expected_commit_must_be_a_full_object_id")
        require(Path(os.fsdecode(git("rev-parse", "--show-toplevel")).strip()).resolve() == root,
                "repo_root_must_be_the_worktree_root")
        initial = position()
        report["observed_position"] = initial
        require(initial == {"branch": report["expected_branch"], "head": args.expected_commit,
                            "branch_head": args.expected_commit}, "unexpected_branch_or_HEAD")
        parents = git("rev-list", "--parents", "-n", "1", args.expected_commit).split()
        require(len(parents) <= 2, "merge_commit_requires_a_separately_defined_parent_basis")
        allowed = set(args.allow_untracked)
        pins = dict(args.require_untracked)
        require(len(pins) == len(args.require_untracked), "duplicate_required_untracked_path")
        allowed.update(pins)
        for path in allowed:
            p = PurePosixPath(path)
            require(path and not p.is_absolute() and ".." not in p.parts and str(p) == path,
                    "untracked_allowance_must_be_an_exact_repository_relative_path")
        before = statuses()
        report["working_status"] = before
        raw = git("diff-tree", "--root", "--no-commit-id", "--name-status", "--no-renames",
                  "-r", "-z", args.expected_commit).split(b"\0")
        require(raw[-1:] == [b""], "diff_tree_transport_incomplete")
        raw = raw[:-1]
        require(len(raw) % 2 == 0, "diff_tree_identity_shape_invalid")
        changes = {os.fsdecode(raw[i + 1]): os.fsdecode(raw[i]) for i in range(0, len(raw), 2)}
        require(len(changes) * 2 == len(raw), "duplicate_diff_tree_identity")
        numbers = [row.split(b"\t", 2) for row in
                   git("show", "--format=", "--numstat", "--no-renames", "-z",
                       args.expected_commit, "--").split(b"\0") if row]
        require(all(len(row) == 3 for row in numbers), "numstat_identity_shape_invalid")
        independent = [os.fsdecode(row[2]) for row in numbers]
        require(len(independent) == len(set(independent)) and set(independent) == set(changes),
                "complete_commit_identity_derivations_differ")
        entries = {}
        if changes:
            for row in git("ls-tree", "-r", "-z", "--full-tree", args.expected_commit,
                           "--", *sorted(changes)).split(b"\0"):
                if row:
                    metadata, path = row.split(b"\t", 1)
                    entries[os.fsdecode(path)] = metadata.decode().split()
        require(set(entries) == {p for p, change in changes.items() if change != "D"},
                "commit_tree_and_change_status_disagree")
        checked = []
        for path, change in sorted(changes.items()):
            working = root / path
            row = {"path": path, "change": change}
            if change == "D":
                row["working_absent"] = not os.path.lexists(working)
                require(row["working_absent"], "deleted_committed_path_still_present:" + path)
            else:
                mode, kind, oid = entries[path]
                require(kind == "blob" and mode in {"100644", "100755", "120000"},
                        "unsupported_commit_entry:" + path)
                actual_mode = working.lstat().st_mode
                require(stat.S_ISLNK(actual_mode) if mode == "120000" else stat.S_ISREG(actual_mode),
                        "working_entry_type_mismatch:" + path)
                body = os.fsencode(os.readlink(working)) if mode == "120000" else working.read_bytes()
                require(git("cat-file", "blob", oid) == body, "committed_blob_mismatch:" + path)
                if mode != "120000":
                    require(bool(actual_mode & stat.S_IXUSR) == (mode == "100755"),
                            "working_executable_mode_mismatch:" + path)
                row.update(blob=oid, mode=mode, sha256=hashlib.sha256(body).hexdigest(), bytes_match=True)
            checked.append(row)
        report.update(commit_members=checked, diff_tree_count=len(changes), numstat_count=len(independent),
                      complete_commit_identity_sets_equal=True, committed_blobs_match=True)
        after = statuses()
        report.update(working_status=after, exact_untracked_allowances=sorted(allowed),
                      status_unchanged_during_readback=before == after)
        require(before == after, "working_status_changed_during_readback")
        untracked = {row["path"] for row in after if row["xy"] == "??"}
        report["required_untracked_hashes"] = {}
        for path, expected in pins.items():
            require(path in untracked, "required_note_not_untracked:" + path)
            actual = hashlib.sha256((root / path).read_bytes()).hexdigest()
            report["required_untracked_hashes"][path] = actual
            require(actual == expected, "required_untracked_hash_mismatch:" + path)
        require(all(row["xy"] == "??" for row in after), "tracked_working_changes_present")
        require(untracked <= allowed, "unexpected_untracked_paths:" + repr(sorted(untracked - allowed)))
        require(position() == initial, "branch_or_HEAD_changed_during_readback")
        report.update(status="pass", tracked_status_empty=True,
                      limitation="Status observed before stdout/outer recorder retention; allowed untracked paths remain untracked.")
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        report["error"] = type(error).__name__ + ":" + str(error)
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(report["status"] != "pass")


if __name__ == "__main__":
    raise SystemExit(main())
