"""Enforce the Phase 7 ratchet checklist for new subsystems and major surfaces."""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Callable, Iterable

DECLARATION_LABEL = "This PR introduces a new subsystem or major surface."
REQUIRED_LABELS = (
    "I added or updated the owner path, docs entry point, and test strategy.",
    "I considered compatibility, review / merge governance, and bootstrap / doctor impact.",
    "I considered config / secrets, generated artifacts, observability / rollout, and release / runbook impact.",
    "I linked the relevant evidence or checklist in `policy-engine/docs/reference/ratchet-policy.md`.",
)

PACKAGE_PREFIX = "policy-engine/src/polisyos/"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check Phase 7 PR ratchet evidence")
    parser.add_argument("--repo-root", default=".", help="Workspace root containing policy-engine/")
    parser.add_argument("--pr-body-file", required=True, help="Path to the pull request body markdown")
    parser.add_argument("--base-ref", required=True, help="Base git ref/SHA to diff against")
    parser.add_argument("--head-ref", default="HEAD", help="Head git ref/SHA to diff against")
    return parser


def checkbox_checked(body: str, label: str) -> bool:
    """Return whether a markdown checkbox line containing `label` is checked."""

    pattern = re.compile(
        rf"(?mi)^\s*-\s*\[(?P<state>[ xX])\]\s*.*{re.escape(label)}\s*$"
    )
    match = pattern.search(body)
    return bool(match and match.group("state").lower() == "x")


def parse_changed_paths(repo_root: Path, *, base_ref: str, head_ref: str) -> list[str]:
    """Return the changed paths between two refs."""

    completed = subprocess.run(
        ["git", "diff", "--name-status", "--diff-filter=AMR", base_ref, head_ref],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    changed: list[str] = []
    for raw_line in completed.stdout.splitlines():
        if not raw_line.strip():
            continue
        parts = raw_line.split("\t")
        if not parts:
            continue
        status = parts[0]
        if status.startswith("R") and len(parts) >= 3:
            changed.append(parts[2])
            continue
        if len(parts) >= 2:
            changed.append(parts[1])
    return changed


def package_exists_at_ref(repo_root: Path, ref: str, package: str) -> bool:
    """Return whether the package directory exists at the given git ref."""

    target = f"{ref}:{PACKAGE_PREFIX}{package}"
    result = subprocess.run(
        ["git", "cat-file", "-e", target],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def detect_new_packages(
    changed_paths: Iterable[str],
    *,
    package_exists: Callable[[str], bool],
) -> tuple[str, ...]:
    """Return newly introduced top-level polisyos package roots."""

    packages: set[str] = set()
    for path in changed_paths:
        normalized = path.replace("\\", "/")
        if not normalized.startswith(PACKAGE_PREFIX):
            continue
        remainder = normalized[len(PACKAGE_PREFIX) :]
        package = remainder.split("/", 1)[0]
        if package and not package_exists(package):
            packages.add(package)
    return tuple(sorted(packages))


def evaluate_phase7_ratchet(
    *,
    pr_body: str,
    new_packages: Iterable[str],
    repo_root: Path | None = None,
) -> list[str]:
    """Return human-readable findings for missing ratchet evidence."""

    new_packages = tuple(sorted(set(new_packages)))
    declared = checkbox_checked(pr_body, DECLARATION_LABEL)
    if not declared and not new_packages:
        return []

    findings: list[str] = []
    if new_packages and not declared:
        packages = ", ".join(f"`{package}`" for package in new_packages)
        findings.append(
            "New package roots were added without checking the Phase 7 declaration box: "
            f"{packages}."
        )

    for label in REQUIRED_LABELS:
        if not checkbox_checked(pr_body, label):
            findings.append(f"Phase 7 ratchet checkbox is still unchecked: {label}")

    if repo_root is not None:
        for package in new_packages:
            readme = repo_root / PACKAGE_PREFIX / package / "README.md"
            if not readme.exists():
                findings.append(
                    f"New package `{package}` is missing its package README at `{readme.as_posix()}`."
                )
    return findings


def main() -> int:
    args = _build_parser().parse_args()
    repo_root = Path(args.repo_root).resolve()
    pr_body = Path(args.pr_body_file).read_text(encoding="utf-8")
    changed_paths = parse_changed_paths(repo_root, base_ref=args.base_ref, head_ref=args.head_ref)
    new_packages = detect_new_packages(
        changed_paths,
        package_exists=lambda package: package_exists_at_ref(repo_root, args.base_ref, package),
    )
    findings = evaluate_phase7_ratchet(
        pr_body=pr_body,
        new_packages=new_packages,
        repo_root=repo_root,
    )
    if findings:
        for finding in findings:
            print(f"Phase 7 ratchet: {finding}")
        return 1
    print("Phase 7 ratchet: pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
