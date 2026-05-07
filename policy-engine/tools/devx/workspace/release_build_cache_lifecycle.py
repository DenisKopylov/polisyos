#!/usr/bin/env python3
"""Check and clean release/build/cache lifecycle state."""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import time
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ._common import GIT_ROOT, PRODUCT_ROOT

SECONDS_PER_DAY = 24 * 60 * 60
DEFAULT_RETENTION_DAYS = 90
GENERATED_MANIFEST = PRODUCT_ROOT / "architecture" / "generated_artifacts.toml"
IGNORED_TRACKED_UMBRELLAS = ("_build", "_cache")
GENERATED_IGNORED_LIFECYCLES = {"generated_ignored", "scratch_ignored", "runtime_ignored"}
STALE_WARN_BEHAVIORS = {"warn", "cleanup_eligible", "block_release"}
RELEASE_INPUT_ROOTS = (
    "release",
    "release-fragments/README.md",
    "release-fragments/template.toml",
    "release-fragments/unreleased",
)


@dataclass(frozen=True)
class GeneratedFamily:
    family_id: str
    lifecycle: str
    generator: str
    verifier: str
    promotion_target: str
    stale_output_behavior: str
    outputs: tuple[Path, ...]
    regenerate_commands: tuple[str, ...]
    commit_policy: str
    retention_days: int | None


@dataclass(frozen=True)
class CleanupCandidate:
    path: Path
    reason: str
    family_id: str = ""
    retention_days: int | None = None
    manifest_owned: bool = False

    def key(self) -> tuple[str, str]:
        return (str(self.path.resolve()), self.reason)


@dataclass(frozen=True)
class LifecycleReport:
    violations: tuple[str, ...]
    warnings: tuple[str, ...]
    cleanup_candidates: tuple[CleanupCandidate, ...]

    @property
    def failed(self) -> bool:
        return bool(self.violations)


IgnoreChecker = Callable[[Path], bool]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate and clean the release/build/cache lifecycle split. The cleanup action "
            "is a dry run unless --apply is passed."
        )
    )
    parser.add_argument(
        "action",
        nargs="?",
        choices=("check", "cleanup"),
        default="check",
        help="Run lifecycle validation or list/remove cleanup candidates.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually remove cleanup candidates. Without this flag cleanup is dry-run only.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=DEFAULT_RETENTION_DAYS,
        help="Fallback retention window for ignored generated outputs without an explicit family retention_days.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=GENERATED_MANIFEST,
        help="Generated artifact lifecycle manifest.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON report path.",
    )
    return parser


def parse_generated_families(
    manifest: Path, *, product_root: Path = PRODUCT_ROOT
) -> tuple[GeneratedFamily, ...]:
    payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
    families: list[GeneratedFamily] = []
    for item in payload.get("family", []):
        retention = item.get("retention_days")
        families.append(
            GeneratedFamily(
                family_id=str(item.get("id", "")),
                lifecycle=str(item.get("lifecycle", "")),
                generator=str(item.get("generator", "")),
                verifier=str(item.get("verifier", "")),
                promotion_target=str(item.get("promotion_target", "")),
                stale_output_behavior=str(item.get("stale_output_behavior", "")),
                outputs=tuple(
                    _resolve_manifest_output(str(output), product_root)
                    for output in item.get("outputs", [])
                ),
                regenerate_commands=tuple(
                    str(command) for command in item.get("regenerate_commands", [])
                ),
                commit_policy=str(item.get("commit_policy", "")),
                retention_days=int(retention) if retention is not None else None,
            )
        )
    return tuple(families)


def build_report(
    *,
    product_root: Path = PRODUCT_ROOT,
    git_root: Path = GIT_ROOT,
    manifest: Path = GENERATED_MANIFEST,
    families: tuple[GeneratedFamily, ...] | None = None,
    tracked_paths: set[str] | None = None,
    ignore_checker: IgnoreChecker | None = None,
    now: float | None = None,
    fallback_retention_days: int = DEFAULT_RETENTION_DAYS,
) -> LifecycleReport:
    product_root = product_root.resolve()
    git_root = git_root.resolve()
    families = (
        parse_generated_families(manifest, product_root=product_root)
        if families is None
        else families
    )
    tracked_paths = _git_tracked_paths(git_root) if tracked_paths is None else set(tracked_paths)
    ignore_checker = _git_ignore_checker(git_root) if ignore_checker is None else ignore_checker
    now = time.time() if now is None else now

    violations: list[str] = []
    warnings: list[str] = []
    cleanup_candidates: list[CleanupCandidate] = []

    product_prefix = _relative_to_git(product_root, git_root)
    for tracked in sorted(tracked_paths):
        product_relative = _strip_prefix(tracked, product_prefix)
        if product_relative is None:
            continue
        parts = Path(product_relative).parts
        if parts and parts[0] in IGNORED_TRACKED_UMBRELLAS:
            violations.append(f"tracked file lives under ignored build/cache umbrella: {tracked}")
        if (
            len(parts) >= 3
            and parts[0] == "_build"
            and parts[1] in {"release", "release-fragments"}
        ):
            violations.append(f"release source/output boundary violation under _build: {tracked}")

    for release_input in RELEASE_INPUT_ROOTS:
        path = product_root / release_input
        if path.exists() and ignore_checker(path):
            violations.append(f"committed release input path is ignored by git: {release_input}")

    for family in families:
        if family.lifecycle != "generated_committed":
            continue
        if not _family_has_tracked_output(family, tracked_paths, git_root):
            continue
        if not family.generator.strip() or not family.regenerate_commands:
            violations.append(
                f"committed generated output family `{family.family_id}` is missing a generator entry"
            )
        if not family.verifier.strip():
            violations.append(
                f"committed generated output family `{family.family_id}` is missing a verifier entry"
            )

    cleanup_candidates.extend(_fixed_cleanup_candidates(product_root, git_root))
    stale_candidates = _stale_generated_output_candidates(
        families=families,
        ignore_checker=ignore_checker,
        now=now,
        fallback_retention_days=fallback_retention_days,
    )
    for candidate in stale_candidates:
        age = "unknown"
        if candidate.retention_days is not None:
            age = f">{candidate.retention_days}d"
        warnings.append(
            f"ignored generated output is stale ({age}): {candidate.path.as_posix()} "
            f"[family={candidate.family_id}]"
        )
    cleanup_candidates.extend(stale_candidates)

    return LifecycleReport(
        violations=tuple(dict.fromkeys(violations)),
        warnings=tuple(dict.fromkeys(warnings)),
        cleanup_candidates=_dedupe_candidates(cleanup_candidates),
    )


def apply_cleanup(
    report: LifecycleReport,
    *,
    product_root: Path = PRODUCT_ROOT,
    git_root: Path = GIT_ROOT,
    tracked_paths: set[str] | None = None,
    ignore_checker: IgnoreChecker | None = None,
    apply: bool = False,
) -> tuple[str, ...]:
    tracked_paths = _git_tracked_paths(git_root) if tracked_paths is None else set(tracked_paths)
    ignore_checker = _git_ignore_checker(git_root) if ignore_checker is None else ignore_checker
    errors: list[str] = []
    for candidate in report.cleanup_candidates:
        path = candidate.path.resolve()
        if not path.exists():
            continue
        if not _is_safe_cleanup_target(
            path,
            product_root=product_root,
            git_root=git_root,
            candidate=candidate,
            ignore_checker=ignore_checker,
        ):
            errors.append(f"unsafe cleanup target skipped: {path.as_posix()}")
            continue
        tracked = _tracked_descendants(path, tracked_paths, git_root)
        if tracked:
            errors.append(
                f"cleanup target contains tracked files and was skipped: {path.as_posix()} ({', '.join(tracked[:5])})"
            )
            continue
        if not apply:
            continue
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()
    return tuple(errors)


def _resolve_manifest_output(raw: str, product_root: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return product_root / path


def _git_tracked_paths(git_root: Path) -> set[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=git_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def _git_ignore_checker(git_root: Path) -> IgnoreChecker:
    def _check(path: Path) -> bool:
        rel = _relative_to_git(path, git_root)
        if rel == ".":
            return False
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", rel],
            cwd=git_root,
            check=False,
        )
        return result.returncode == 0

    return _check


def _relative_to_git(path: Path, git_root: Path) -> str:
    try:
        return path.resolve().relative_to(git_root.resolve()).as_posix()
    except ValueError:
        return os.path.relpath(path.resolve(), git_root.resolve())


def _strip_prefix(path: str, prefix: str) -> str | None:
    if prefix in {"", "."}:
        return path
    if path == prefix:
        return ""
    prefix_with_sep = f"{prefix}/"
    if path.startswith(prefix_with_sep):
        return path[len(prefix_with_sep) :]
    return None


def _family_has_tracked_output(
    family: GeneratedFamily, tracked_paths: set[str], git_root: Path
) -> bool:
    for output in _expand_existing_or_literal_outputs(family.outputs):
        rel = _relative_to_git(output, git_root)
        if any(path == rel or path.startswith(f"{rel.rstrip('/')}/") for path in tracked_paths):
            return True
    return False


def _fixed_cleanup_candidates(product_root: Path, git_root: Path) -> list[CleanupCandidate]:
    candidates = [
        CleanupCandidate(product_root / "_build" / "scratch", "local scratch"),
        CleanupCandidate(product_root / "_cache", "product-root cache"),
    ]
    if git_root.resolve() != product_root.resolve():
        candidates.extend(
            [
                CleanupCandidate(git_root / "_build", "wrong-root build residue"),
                CleanupCandidate(git_root / "_cache", "wrong-root cache residue"),
                CleanupCandidate(git_root / "tmp", "wrong-root tmp residue"),
            ]
        )
        candidates.extend(
            CleanupCandidate(path, "wrong-root tmp residue")
            for path in sorted(git_root.glob(".tmp_*"))
        )
    return [candidate for candidate in candidates if candidate.path.exists()]


def _stale_generated_output_candidates(
    *,
    families: tuple[GeneratedFamily, ...],
    ignore_checker: IgnoreChecker,
    now: float,
    fallback_retention_days: int,
) -> list[CleanupCandidate]:
    candidates: list[CleanupCandidate] = []
    for family in families:
        if family.lifecycle not in GENERATED_IGNORED_LIFECYCLES:
            continue
        if family.stale_output_behavior not in STALE_WARN_BEHAVIORS:
            continue
        retention_days = family.retention_days or fallback_retention_days
        cutoff = now - (retention_days * SECONDS_PER_DAY)
        for output in _expand_existing_or_literal_outputs(family.outputs):
            if not output.exists() or not ignore_checker(output):
                continue
            newest = _newest_mtime(output)
            if newest <= cutoff:
                candidates.append(
                    CleanupCandidate(
                        output,
                        "expired ignored generated output",
                        family_id=family.family_id,
                        retention_days=retention_days,
                        manifest_owned=True,
                    )
                )
    return candidates


def _expand_existing_or_literal_outputs(outputs: tuple[Path, ...]) -> tuple[Path, ...]:
    expanded: list[Path] = []
    for output in outputs:
        rendered = output.as_posix()
        if any(marker in rendered for marker in "*?["):
            expanded.extend(Path(match) for match in glob.glob(rendered))
        else:
            expanded.append(output)
    return tuple(expanded)


def _newest_mtime(path: Path) -> float:
    newest = path.stat().st_mtime
    if not path.is_dir() or path.is_symlink():
        return newest
    stack = [path]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        stat = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    newest = max(newest, stat.st_mtime)
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(Path(entry.path))
        except OSError:
            continue
    return newest


def _dedupe_candidates(candidates: list[CleanupCandidate]) -> tuple[CleanupCandidate, ...]:
    seen: set[tuple[str, str]] = set()
    deduped: list[CleanupCandidate] = []
    for candidate in candidates:
        key = candidate.key()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return tuple(sorted(deduped, key=lambda item: item.path.as_posix()))


def _is_safe_cleanup_target(
    path: Path,
    *,
    product_root: Path,
    git_root: Path,
    candidate: CleanupCandidate,
    ignore_checker: IgnoreChecker,
) -> bool:
    product_root = product_root.resolve()
    git_root = git_root.resolve()
    protected = tuple((product_root / root).resolve() for root in RELEASE_INPUT_ROOTS)
    if any(path == root or _is_relative_to(path, root) for root in protected):
        return False

    allowed_roots = [
        product_root / "_build",
        product_root / "_cache",
        git_root / "_build",
        git_root / "_cache",
        git_root / "tmp",
    ]
    if any(
        path == root.resolve() or _is_relative_to(path, root.resolve()) for root in allowed_roots
    ):
        return True
    if path.parent == git_root and path.name.startswith(".tmp_"):
        return True
    return candidate.manifest_owned and ignore_checker(path)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _tracked_descendants(path: Path, tracked_paths: set[str], git_root: Path) -> list[str]:
    rel = _relative_to_git(path, git_root).rstrip("/")
    return sorted(
        tracked for tracked in tracked_paths if tracked == rel or tracked.startswith(f"{rel}/")
    )


def _report_payload(report: LifecycleReport, cleanup_errors: tuple[str, ...]) -> dict[str, object]:
    return {
        "status": "failed" if report.failed or cleanup_errors else "passed",
        "violations": list(report.violations),
        "warnings": list(report.warnings),
        "cleanup_errors": list(cleanup_errors),
        "cleanup_candidates": [
            {
                "path": candidate.path.as_posix(),
                "reason": candidate.reason,
                "family_id": candidate.family_id,
                "retention_days": candidate.retention_days,
                "manifest_owned": candidate.manifest_owned,
            }
            for candidate in report.cleanup_candidates
        ],
    }


def _print_report(
    report: LifecycleReport, cleanup_errors: tuple[str, ...], *, action: str, apply: bool
) -> None:
    if report.violations:
        print("Release/build/cache lifecycle check FAILED:")
        for violation in report.violations:
            print(f"- {violation}")
    else:
        print("Release/build/cache lifecycle check passed.")

    if report.warnings:
        print("Warnings:")
        for warning in report.warnings:
            print(f"- {warning}")

    if cleanup_errors:
        print("Cleanup errors:")
        for error in cleanup_errors:
            print(f"- {error}")

    if action == "cleanup":
        mode = "removed" if apply else "dry-run"
        print(f"Cleanup candidates ({mode}):")
        if not report.cleanup_candidates:
            print("- none")
        for candidate in report.cleanup_candidates:
            print(f"- {candidate.path.as_posix()} [{candidate.reason}]")


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_report(
        manifest=args.manifest,
        fallback_retention_days=args.retention_days,
    )
    cleanup_errors: tuple[str, ...] = ()
    if args.action == "cleanup":
        cleanup_errors = apply_cleanup(report, apply=args.apply)

    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(_report_payload(report, cleanup_errors), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    _print_report(report, cleanup_errors, action=args.action, apply=args.apply)
    return 1 if report.failed or cleanup_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
