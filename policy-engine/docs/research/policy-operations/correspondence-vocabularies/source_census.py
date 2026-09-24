"""Replay a bounded source-mention census; this does not determine semantic ownership.

Internal research caller: run this file from the repository root with Python.
There is no production runtime caller or authority-bearing output. JSON is the
only output format. Every selected file is read, including comments/docstrings.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


def measure(repo: Path, roots: list[str], terms: list[str]) -> dict[str, Any]:
    """Count literal substrings in tracked Python files and disclose unread boundaries."""
    git_reads: list[dict[str, Any]] = []

    def git(*args: str) -> bytes:
        process = subprocess.run(  # noqa: S603 - fixed Git verbs, argv only, no shell
            ["git", "-C", str(repo), *args],  # noqa: S607 - repository Git toolchain
            capture_output=True,
            check=False,
        )
        git_reads.append(
            {
                "argv": ["git", "-C", str(repo), *args],
                "exit_code": process.returncode,
                "stdout_sha256": hashlib.sha256(process.stdout).hexdigest(),
                "stderr": process.stderr.decode("utf-8", errors="replace"),
            }
        )
        if process.returncode:
            raise RuntimeError(f"Git observation failed: {args!r}")
        return process.stdout

    result: dict[str, Any] = {
        "schema_version": "research.source-mentions.v1",
        "authority": "research_only_not_semantic_owner_or_capability_verdict",
        "predicate": {
            "roots": roots,
            "suffixes": [".py"],
            "inclusion": "git ls-files --cached --full-name, exact .py suffix under roots",
            "matching": "literal substring anywhere in UTF-8 text; count files, not occurrences",
            "case_modes": ["case_sensitive", "case_insensitive_str_casefold"],
            "exclusions": (
                "untracked files, other suffixes, paths outside roots; no content exclusions"
            ),
            "package": (
                "first component after polisyos/ within a root; otherwise first relative component"
            ),
        },
        "search_counterexample": {
            "example": "Capitalised Estimand or NormativeAuditStatus with no lowercase spelling",
            "reachable": "casefold mode returns it; case-sensitive mode can omit it",
            "nonlexical_owner": "An owner expressed with other words is unresolved in both modes",
        },
        "git_reads": git_reads,
        "file_reads": [],
        "unresolved_by_construction": [
            "unselected_authority_documents_and_other_roots_or_suffixes",
            "untracked_files_and_other_revisions",
            "lexical_presence_does_not_determine_definition_semantics_demand_or_ownership",
            "sequential_worktree_observation_not_atomic",
        ],
        "status": "UNRUN",
    }

    def selected(name: str) -> bool:
        return Path(name).suffix == ".py" and any(
            name.startswith(root.rstrip("/") + "/") for root in roots
        )

    try:
        result["head"] = git("rev-parse", "HEAD").decode().strip()
        index = set(git("ls-files", "--cached", "--full-name", "-z").decode().split("\0"))
        tree = set(git("ls-tree", "-r", "--name-only", "-z", "HEAD").decode().split("\0"))
        names = sorted(name for name in index if selected(name))
        tree_names = sorted(name for name in tree if selected(name))
        result["enumerated_denominator"] = len(names)
        result["independent_tree_denominator"] = len(tree_names)
        result["selector_reconciliation"] = {
            "index_only": sorted(set(names) - set(tree_names)),
            "tree_only": sorted(set(tree_names) - set(names)),
        }
        result["working_tree_delta_from_head"] = git("diff", "HEAD", "--", *roots).decode(
            "utf-8", errors="replace"
        )
    except (OSError, UnicodeError, RuntimeError) as error:
        result["observation_error"] = f"{type(error).__name__}: {error}"
        return result

    contents: dict[str, str] = {}
    for name in names:
        receipt: dict[str, Any] = {"path": name, "operation": "read_bytes + strict UTF-8 decode"}
        try:
            path = repo / name
            if path.is_symlink():
                raise OSError("symlink content not admitted by this selector")
            data = path.read_bytes()
            receipt["sha256"] = hashlib.sha256(data).hexdigest()
            receipt["bytes"] = len(data)
            contents[name] = data.decode("utf-8")
            receipt["status"] = "read"
        except (OSError, UnicodeError) as error:
            receipt.update(status="ambiguous", error=f"{type(error).__name__}: {error}")
        result["file_reads"].append(receipt)

    def package(name: str) -> str:
        root = next(root for root in roots if name.startswith(root.rstrip("/") + "/"))
        parts = name[len(root.rstrip("/")) + 1 :].split("/")
        return parts[1] if parts[0] == "polisyos" and len(parts) > 2 else parts[0]

    measured: dict[str, Any] = {}
    for term in terms:
        modes: dict[str, Any] = {}
        for insensitive in (False, True):
            matches = [
                name
                for name, content in contents.items()
                if (term.casefold() in content.casefold() if insensitive else term in content)
            ]
            modes["case_insensitive" if insensitive else "case_sensitive"] = {
                "observed_matching_files": len(matches),
                "package_distribution": dict(sorted(Counter(map(package, matches)).items())),
                "matching_paths": matches,
            }
        measured[term] = modes
    result["terms"] = measured
    result["successful_read_denominator"] = len(contents)
    if len(contents) == len(names) and names == tree_names:
        result["status"] = "complete_within_declared_selector"
    else:
        result["unresolved_by_construction"].append("unreadable_or_unreconciled_selected_input")
    return result


def main() -> int:
    """Print one complete research receipt and return 2 for incomplete observation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--root", action="append", dest="roots")
    parser.add_argument("--term", action="append", dest="terms")
    args = parser.parse_args()
    receipt = measure(
        args.repo.resolve(),
        args.roots or ["policy-engine/src"],
        args.terms or ["estimand", "normative", "write_operation", "assurance_level"],
    )
    print(json.dumps(receipt, indent=2, ensure_ascii=False))  # noqa: T201 - JSON command output
    return 0 if receipt["status"] == "complete_within_declared_selector" else 2


if __name__ == "__main__":
    raise SystemExit(main())
