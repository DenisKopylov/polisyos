#!/usr/bin/env python3
"""Preflight validation for contributor machines and local quality gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.lib.imports import ensure_repo_import_roots

ensure_repo_import_roots(__file__, include_src_root=False)

from ._common import (
    FRONTEND_ROOT,
    OPTIONAL_SURFACES,
    PRODUCT_ROOT,
    PYTHON_BASELINE,
    UV_BASELINE,
    node_baseline_matches,
    python_baseline_matches,
    surface_status,
    uv_baseline_matches,
    uv_command,
    version_text,
)

PLAYWRIGHT_SMOKE = """
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch({ headless: true });
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
""".strip()


@dataclass(frozen=True, slots=True)
class CheckResult:
    """One doctor check outcome."""

    name: str
    ok: bool
    message: str


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate local prerequisites for policy-engine.")
    parser.add_argument(
        "--worktree-admission",
        choices=("create", "resume"),
        help="Read-only admission of an exact branch/path pair; emit a JSON receipt and exit.",
    )
    parser.add_argument(
        "--branch", help="Exact short branch name; no ref expressions or substitutes."
    )
    parser.add_argument(
        "--path", help="Exact absolute worktree root, not its product subdirectory."
    )
    parser.add_argument(
        "--surface",
        action="append",
        default=[],
        choices=sorted(OPTIONAL_SURFACES),
        help="Optional env surface to validate (repeatable).",
    )
    parser.add_argument(
        "--list-surfaces",
        action="store_true",
        help="Print known optional surfaces and exit.",
    )
    parser.add_argument(
        "--skip-playwright",
        action="store_true",
        help="Skip the Playwright browser smoke-check.",
    )
    parser.add_argument(
        "--skip-lockfile-checks",
        action="store_true",
        help="Skip uv.lock and package-lock freshness checks.",
    )
    parser.add_argument(
        "--skip-contract-checks",
        action="store_true",
        help="Skip generated-contract freshness checks.",
    )
    return parser


@dataclass
class _AdmissionEvidence:
    commands: list[dict[str, Any]] = field(default_factory=list)
    filesystem_reads: list[dict[str, Any]] = field(default_factory=list)

    def git(
        self, root: Path, *args: str, codes: tuple[int, ...] = (0,)
    ) -> subprocess.CompletedProcess[str]:
        argv = ["git", "--no-optional-locks", "-C", str(root), *args]
        record: dict[str, Any] = {"argv": argv, "predicate_class": "recomputed"}
        self.commands.append(record)
        try:
            result = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            record.update(status="unreadable", error=str(exc))
            raise ValueError(f"git_observation_unavailable: {argv}") from exc
        record.update(exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)
        if result.returncode not in codes:
            raise ValueError(f"git_observation_failed: {argv}: {result.returncode}")
        return result

    def state(self, path: Path) -> dict[str, Any]:
        record: dict[str, Any] = {
            "path": str(path),
            "operation": "lstat",
            "predicate_class": "recomputed",
        }
        self.filesystem_reads.append(record)
        try:
            try:
                resolved = str(path.resolve(strict=True))
            except FileNotFoundError:
                resolved = str(path.resolve())
            info = path.lstat()
            kind = (
                "symlink"
                if stat.S_ISLNK(info.st_mode)
                else "directory"
                if stat.S_ISDIR(info.st_mode)
                else "file"
            )
            result = {
                "exists": True,
                "kind": kind,
                "resolved": resolved,
                "device": info.st_dev,
                "inode": info.st_ino,
            }
        except FileNotFoundError:
            result = {"exists": False, "kind": "absent", "resolved": resolved}
        except (OSError, RuntimeError) as exc:
            record.update(status="unreadable", error=str(exc))
            raise ValueError(f"path_identity_unreadable: {path}: {exc}") from exc
        record.update(status="observed", result=result)
        return result

    def read(self, path: Path) -> str:
        record: dict[str, Any] = {
            "path": str(path),
            "operation": "read_bytes",
            "predicate_class": "recomputed",
        }
        self.filesystem_reads.append(record)
        try:
            data = path.read_bytes()
            record.update(status="read", sha256=hashlib.sha256(data).hexdigest(), bytes=len(data))
            text = data.decode("utf-8")
            record["text"] = text
            return text.removesuffix("\n")
        except (OSError, UnicodeError) as exc:
            record.update(status="unreadable", error=str(exc))
            raise

    def children(self, path: Path) -> list[Path]:
        record: dict[str, Any] = {
            "path": str(path),
            "operation": "iterdir",
            "predicate_class": "recomputed",
        }
        self.filesystem_reads.append(record)
        try:
            children = sorted(path.iterdir())
        except OSError as exc:
            record.update(status="unreadable", error=str(exc))
            raise
        record.update(status="read", members=[str(child) for child in children])
        return children


def _worktree_records(porcelain: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    current: dict[str, Any] = {}
    for token in porcelain.split("\0"):
        if not token:
            if current:
                if "worktree" not in current:
                    raise ValueError("worktree_record_missing_path")
                records.append(current)
                current = {}
            continue
        key, _, value = token.partition(" ")
        if key in current:
            raise ValueError(f"duplicate_worktree_field: {key}")
        current[key] = value
    if current or not records:
        raise ValueError("incomplete_worktree_porcelain")
    paths = [row["worktree"] for row in records]
    if len(paths) != len(set(paths)):
        raise ValueError("duplicate_registered_path")
    return records


def _admission_registry(
    evidence: _AdmissionEvidence,
    common: Path,
    records: list[dict[str, Any]],
    admins: list[dict[str, Any]],
) -> None:
    admin_root = common / "worktrees"
    by_path = {row["worktree"]: row for row in records}
    children = evidence.children(admin_root) if evidence.state(admin_root)["exists"] else []
    for admin in children:
        item: dict[str, Any] = {"admin_dir": str(admin)}
        admins.append(item)
        if evidence.state(admin)["kind"] != "directory":
            raise ValueError(f"admin_record_not_directory: {admin}")
        for name in ("gitdir", "commondir", "HEAD"):
            item[name] = evidence.read(admin / name)
        locked = evidence.state(admin / "locked")
        if locked["exists"]:
            item["locked"] = evidence.read(admin / "locked")
        gitdir = Path(item["gitdir"])
        if not gitdir.is_absolute() or gitdir.name != ".git":
            raise ValueError(f"admin_gitdir_not_absolute_marker: {admin}")
        item["worktree"] = str(gitdir.parent)
        if (admin / item["commondir"]).resolve() != common:
            raise ValueError(f"admin_common_repository_mismatch: {admin}")
        row = by_path.get(item["worktree"])
        if row is None or "admin_dir" in row:
            raise ValueError(f"admin_registration_set_mismatch: {admin}")
        head = item["HEAD"]
        if head.startswith("ref: "):
            if head[5:] != row.get("branch"):
                raise ValueError(f"admin_branch_mismatch: {admin}")
        elif head != row.get("HEAD") or "detached" not in row:
            raise ValueError(f"admin_detached_head_mismatch: {admin}")
        row["admin_dir"] = str(admin)
    if len([row for row in records if "admin_dir" not in row]) != 1:
        raise ValueError("main_linked_registration_denominator_mismatch")
    for row in records:
        path = Path(row["worktree"])
        row["path_state"] = evidence.state(path)
        if not row["path_state"]["exists"]:
            continue
        if row["path_state"]["kind"] != "directory":
            raise ValueError(f"registered_path_not_directory: {path}")
        marker = path / ".git"
        if "admin_dir" in row:
            if evidence.state(marker)["kind"] != "file":
                raise ValueError(f"linked_marker_unreadable: {marker}")
            target = evidence.read(marker)
            if not target.startswith("gitdir: ") or (path / target[8:]).resolve() != Path(
                row["admin_dir"]
            ):
                raise ValueError(f"linked_marker_backlink_mismatch: {marker}")
        live = {
            "root": evidence.git(path, "rev-parse", "--show-toplevel").stdout.rstrip("\n"),
            "common_dir": evidence.git(
                path, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).stdout.rstrip("\n"),
            "git_dir": evidence.git(path, "rev-parse", "--absolute-git-dir").stdout.rstrip("\n"),
            "branch": evidence.git(path, "symbolic-ref", "-q", "HEAD", codes=(0, 1)).stdout.rstrip(
                "\n"
            ),
            "head": evidence.git(path, "rev-parse", "--verify", "HEAD").stdout.rstrip("\n"),
        }
        row["live"] = live
        if (
            Path(live["root"]).resolve() != path.resolve()
            or Path(live["common_dir"]).resolve() != common
            or live["branch"] != row.get("branch", "")
            or live["head"] != row.get("HEAD")
        ):
            raise ValueError(f"live_registration_mismatch: {path}")
        if "admin_dir" in row and Path(live["git_dir"]).resolve() != Path(row["admin_dir"]):
            raise ValueError(f"live_admin_mismatch: {path}")


def _worktree_admission(mode: str, branch: str | None, raw_path: str | None) -> int:
    evidence = _AdmissionEvidence()
    report: dict[str, Any] = {
        "schema_version": "polisyos.workspace.worktree-admission.v1",
        "requested": {"mode": mode, "branch": branch, "path": raw_path},
        "selector_predicate_class": "consumer_asserted",
        "started_at": datetime.now(UTC).isoformat(),
        "status": "unrun",
        "complete_verdict": False,
        "registrations": [],
        "admin_records": [],
        "findings": [],
        "unresolved_inputs": [],
        "commands": evidence.commands,
        "filesystem_reads": evidence.filesystem_reads,
        "measurement": {
            "selector": "exact branch ref AND exact worktree root; create availability or resume attachment",
            "path_denominator": "all Git worktree registrations, all linked admin directories, their required records and live backlinks, requested path",
            "file_type_denominator": "Git porcelain/ref outputs; gitdir, commondir, HEAD, optional locked and .git markers; filesystem lstat/iterdir",
            "predicate_class": "independently_reconciled",
        },
        "unresolved_by_construction": [
            {
                "boundary": "moved_directories_outside_registered_paths",
                "detail": "No wider filesystem/mount search; missing registered directories do not prove abandonment or prune safety.",
            },
            {
                "boundary": "non_atomic_observation",
                "detail": "Git and filesystem reads are sequential, not an atomic snapshot; changes after or between reads can escape observation.",
            },
            {
                "boundary": "name_reservation",
                "detail": "This read-only command reserves nothing. Root serializes commissioning, reruns immediately before creation and reads back exact attachment afterward.",
            },
            {
                "boundary": "external_prompt_writers",
                "detail": "Receipt does not intercept or enforce arbitrary commissioning prompts.",
            },
        ],
    }
    code = 2
    try:
        if not branch or not raw_path or not Path(raw_path).is_absolute():
            raise ValueError("exact_branch_and_absolute_path_required")
        if branch.startswith(("-", "refs/")):
            raise ValueError("short_branch_name_required_no_ref_aliases")
        overrides = sorted(
            name
            for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE")
            if name in os.environ
        )
        if overrides:
            raise ValueError(f"git_repository_environment_override: {overrides}")
        ref = f"refs/heads/{branch}"
        evidence.git(PRODUCT_ROOT, "check-ref-format", ref)
        checked = evidence.git(PRODUCT_ROOT, "check-ref-format", "--branch", branch)
        if checked.stdout.removesuffix("\n") != branch:
            raise ValueError("branch_substitution_rejected")
        common = Path(
            evidence.git(
                PRODUCT_ROOT, "rev-parse", "--path-format=absolute", "--git-common-dir"
            ).stdout.rstrip("\n")
        ).resolve()
        report["repository_common_dir"] = str(common)
        initial = evidence.git(PRODUCT_ROOT, "worktree", "list", "--porcelain", "-z").stdout
        records = _worktree_records(initial)
        report["registrations"] = records
        _admission_registry(evidence, common, records, report["admin_records"])
        branch_result = evidence.git(
            PRODUCT_ROOT, "show-ref", "--verify", "--quiet", ref, codes=(0, 1)
        )
        branch_exists = branch_result.returncode == 0
        path = Path(raw_path)
        path_state = evidence.state(path)
        report["branch_exists"] = branch_exists
        report["path_state"] = path_state
        matching = [
            row
            for row in records
            if row["worktree"] == raw_path
            or row["path_state"]["resolved"] == path_state["resolved"]
        ]
        findings = report["findings"]
        if raw_path != str(path) or raw_path != path_state["resolved"]:
            findings.append(
                {
                    "code": "path_alias",
                    "detail": "Supplied spelling differs from resolved identity; no substitution is admitted.",
                }
            )
        if mode == "create":
            if branch_exists:
                findings.append({"code": "branch_occupied", "ref": ref})
            if matching:
                findings.append(
                    {
                        "code": "path_registered",
                        "registrations": [row["worktree"] for row in matching],
                    }
                )
            if path_state["exists"]:
                findings.append({"code": "path_exists", "path": raw_path})
        elif (
            not branch_exists
            or len(matching) != 1
            or matching[0]["worktree"] != raw_path
            or matching[0].get("live", {}).get("branch") != ref
        ):
            findings.append(
                {"code": "resume_attachment_mismatch", "branch": branch, "path": raw_path}
            )
        final = evidence.git(PRODUCT_ROOT, "worktree", "list", "--porcelain", "-z").stdout
        if final != initial:
            raise ValueError("worktree_registrations_changed_during_observation")
        report.update(status="rejected" if findings else "admitted", complete_verdict=True)
        code = 1 if findings else 0
    except (OSError, ValueError, UnicodeError) as exc:
        report["unresolved_inputs"].append({"code": "observation_incomplete", "detail": str(exc)})
    report["finished_at"] = datetime.now(UTC).isoformat()
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


def _print_surfaces() -> int:
    for name in sorted(OPTIONAL_SURFACES):
        description = OPTIONAL_SURFACES[name]["description"]
        assert isinstance(description, str)
        print(f"{name}: {description}")
    return 0


def _run_checked(argv: list[str], *, cwd: str | None = None) -> None:
    subprocess.run(argv, cwd=cwd or str(PRODUCT_ROOT), check=True)


def _check_python() -> CheckResult:
    version_info = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    rendered = ".".join(str(part) for part in version_info)
    if python_baseline_matches(version_info):
        return CheckResult("python", True, f"Python {rendered} via {sys.executable}")
    return CheckResult(
        "python",
        False,
        f"Expected Python {PYTHON_BASELINE}.x, found {rendered} via {sys.executable}",
    )


def _check_node() -> CheckResult:
    try:
        node_version = version_text(("node", "--version"))
    except (subprocess.CalledProcessError, FileNotFoundError):
        return CheckResult("node", False, "Node is missing from PATH; expected Node 22.x")

    if node_baseline_matches(node_version):
        return CheckResult("node", True, f"Node {node_version}")
    return CheckResult("node", False, f"Expected Node 22.x, found {node_version}")


def _check_uv() -> CheckResult:
    command = uv_command()
    if command[0] == sys.executable:
        return CheckResult("uv", False, "uv is missing from PATH")

    try:
        rendered = version_text((command[0], "--version"))
    except subprocess.CalledProcessError:
        return CheckResult("uv", False, f"uv exists at {command[0]} but failed to execute")

    if not uv_baseline_matches(rendered):
        return CheckResult(
            "uv",
            False,
            f"Expected uv {UV_BASELINE}, found {rendered} at {command[0]}",
        )
    return CheckResult("uv", True, f"{rendered} at {command[0]}")


def _check_playwright() -> CheckResult:
    try:
        _run_checked(["node", "-e", PLAYWRIGHT_SMOKE], cwd=str(FRONTEND_ROOT))
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return CheckResult(
            "playwright",
            False,
            f"Chromium launch smoke-check failed in apps/runtime-dashboard ({exc})",
        )
    return CheckResult("playwright", True, "Chromium browser is launchable")


def _check_lockfiles() -> list[CheckResult]:
    results: list[CheckResult] = []
    uv = list(uv_command())

    try:
        _run_checked([*uv, "lock", "--check"])
    except subprocess.CalledProcessError as exc:
        results.append(CheckResult("uv.lock", False, f"uv.lock is stale or inconsistent ({exc})"))
    else:
        results.append(CheckResult("uv.lock", True, "uv.lock is up to date"))

    try:
        _run_checked(
            [
                "corepack",
                "pnpm",
                "install",
                "--frozen-lockfile",
                "--lockfile-only",
                "--ignore-scripts",
            ],
            cwd=str(PRODUCT_ROOT),
        )
    except subprocess.CalledProcessError as exc:
        results.append(
            CheckResult(
                "pnpm-lock",
                False,
                f"pnpm-lock.yaml is stale or inconsistent ({exc})",
            )
        )
    else:
        results.append(CheckResult("pnpm-lock", True, "pnpm-lock.yaml matches package manifests"))

    return results


def _check_generated_contracts() -> list[CheckResult]:
    results: list[CheckResult] = []
    uv = list(uv_command())

    contract_commands = [
        (
            "schemas",
            [
                *uv,
                "run",
                "--extra",
                "ml",
                "python",
                "tools/quality/diagnostics/gen_schema.py",
                "--check",
            ],
        ),
        (
            "runtime-openapi",
            [
                *uv,
                "run",
                "--extra",
                "runtime",
                "--extra",
                "ml",
                "python",
                "tools/ops_runners/runtime/check_runtime_api_contract.py",
            ],
        ),
        (
            "frontend-contracts",
            ["corepack", "pnpm", "run", "contracts:verify"],
        ),
    ]

    for name, argv in contract_commands:
        try:
            target_root = FRONTEND_ROOT if name == "frontend-contracts" else PRODUCT_ROOT
            _run_checked(argv, cwd=str(target_root))
        except subprocess.CalledProcessError as exc:
            results.append(CheckResult(name, False, f"Generated contract check failed ({exc})"))
        else:
            results.append(CheckResult(name, True, "fresh"))

    return results


def _check_optional_surfaces(surfaces: list[str]) -> list[CheckResult]:
    if not surfaces:
        return [CheckResult("optional-surfaces", True, "No optional surfaces selected")]

    results: list[CheckResult] = []
    for surface in surfaces:
        ok, message = surface_status(surface)
        results.append(CheckResult(surface, ok, message))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.worktree_admission:
        return _worktree_admission(args.worktree_admission, args.branch, args.path)
    if args.branch is not None or args.path is not None:
        parser.error("--branch and --path require --worktree-admission")
    if args.list_surfaces:
        return _print_surfaces()

    results = [_check_python(), _check_node(), _check_uv()]

    if not args.skip_playwright:
        results.append(_check_playwright())
    if not args.skip_lockfile_checks:
        results.extend(_check_lockfiles())
    if not args.skip_contract_checks:
        results.extend(_check_generated_contracts())

    results.extend(_check_optional_surfaces(args.surface))

    failures = [result for result in results if not result.ok]
    for result in results:
        marker = "PASS" if result.ok else "FAIL"
        print(f"[{marker}] {result.name}: {result.message}")

    if failures:
        print(f"doctor failed with {len(failures)} issue(s).")
        return 1

    print("doctor passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
