#!/usr/bin/env python3
"""Clean registered .polisyos runtime-state slots with dry-run summaries."""

from __future__ import annotations

import argparse
import json
import shutil
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.lib.imports import repo_root_from

REPO_ROOT = repo_root_from(__file__)
CONTRACT_PATH = Path("architecture/local_runtime_state.toml")
PRODUCTION_SLOT = "production_data"


@dataclass(frozen=True)
class StateClass:
    id: str
    paths: tuple[str, ...]
    legacy_paths: tuple[str, ...]
    owner: str
    retention_class: str
    cleanup_command: str

    @property
    def protected(self) -> bool:
        return self.cleanup_command.strip().lower().startswith("manual approval only")

    @property
    def production_snapshot(self) -> bool:
        return self.id == PRODUCTION_SLOT


@dataclass(frozen=True)
class CleanupTarget:
    path: str
    kind: str
    size_bytes: int


@dataclass(frozen=True)
class SlotCleanupSummary:
    slot: str
    owner: str
    retention_class: str
    protected: bool
    production_snapshot: bool
    target_count: int
    size_bytes: int
    deleted_count: int
    missing_paths: tuple[str, ...]
    targets: tuple[CleanupTarget, ...]


@dataclass(frozen=True)
class CleanupReport:
    status: str
    dry_run: bool
    repo_root: str
    requested_slots: tuple[str, ...]
    approve_protected: bool
    approve_production_snapshots: bool
    blocked_reasons: tuple[str, ...]
    summaries: tuple[SlotCleanupSummary, ...]

    @property
    def exit_code(self) -> int:
        return 0 if self.status in {"dry_run", "applied"} else 2


def load_state_classes(repo_root: Path = REPO_ROOT) -> dict[str, StateClass]:
    contract = tomllib.loads((repo_root / CONTRACT_PATH).read_text(encoding="utf-8"))
    classes: dict[str, StateClass] = {}
    for item in contract.get("state_class", []):
        slot = StateClass(
            id=str(item["id"]),
            paths=tuple(str(path) for path in item.get("paths", ())),
            legacy_paths=tuple(str(path) for path in item.get("legacy_paths", ())),
            owner=str(item.get("owner", "")),
            retention_class=str(item.get("retention_class", "")),
            cleanup_command=str(item.get("cleanup_command", "")),
        )
        classes[slot.id] = slot
    return classes


def build_cleanup_report(
    *,
    repo_root: Path,
    slots: Sequence[str],
    apply: bool,
    approve_protected: bool = False,
    approve_production_snapshots: bool = False,
) -> CleanupReport:
    repo_root = repo_root.resolve()
    state_classes = load_state_classes(repo_root)
    requested = tuple(dict.fromkeys(slots))
    unknown = tuple(slot for slot in requested if slot not in state_classes)
    if unknown:
        available = ", ".join(sorted(state_classes))
        raise ValueError(f"Unknown runtime-state slot(s): {', '.join(unknown)}. Available: {available}")

    dry_run = not apply
    summaries: list[SlotCleanupSummary] = []
    blocked_reasons: list[str] = []

    for slot_id in requested:
        slot = state_classes[slot_id]
        if apply and slot.production_snapshot and not approve_production_snapshots:
            blocked_reasons.append(
                f"{slot.id} requires --approve-production-snapshots before deletion"
            )
        elif apply and slot.protected and not approve_protected and not slot.production_snapshot:
            blocked_reasons.append(f"{slot.id} requires --approve-protected before deletion")

        summary = _summarize_slot(repo_root=repo_root, slot=slot)
        summaries.append(summary)

    status = "blocked" if blocked_reasons else ("applied" if apply else "dry_run")
    if apply and not blocked_reasons:
        summaries = [_apply_summary(repo_root=repo_root, summary=summary) for summary in summaries]

    return CleanupReport(
        status=status,
        dry_run=dry_run,
        repo_root=str(repo_root),
        requested_slots=requested,
        approve_protected=approve_protected,
        approve_production_snapshots=approve_production_snapshots,
        blocked_reasons=tuple(blocked_reasons),
        summaries=tuple(summaries),
    )


def _summarize_slot(*, repo_root: Path, slot: StateClass) -> SlotCleanupSummary:
    targets: list[CleanupTarget] = []
    missing: list[str] = []
    for raw_path in (*slot.paths, *slot.legacy_paths):
        path = _resolve_slot_path(repo_root, raw_path)
        if not path.exists():
            missing.append(_relative(path, repo_root))
            continue
        if path.is_file():
            targets.append(_target_for(path, repo_root))
            continue
        for child in sorted(path.iterdir(), key=lambda item: item.name):
            targets.append(_target_for(child, repo_root))

    return SlotCleanupSummary(
        slot=slot.id,
        owner=slot.owner,
        retention_class=slot.retention_class,
        protected=slot.protected,
        production_snapshot=slot.production_snapshot,
        target_count=len(targets),
        size_bytes=sum(target.size_bytes for target in targets),
        deleted_count=0,
        missing_paths=tuple(missing),
        targets=tuple(targets),
    )


def _apply_summary(*, repo_root: Path, summary: SlotCleanupSummary) -> SlotCleanupSummary:
    deleted = 0
    for target in summary.targets:
        path = (repo_root / target.path).resolve()
        _assert_under_runtime_root(repo_root, path)
        if not path.exists():
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        deleted += 1
    return SlotCleanupSummary(
        slot=summary.slot,
        owner=summary.owner,
        retention_class=summary.retention_class,
        protected=summary.protected,
        production_snapshot=summary.production_snapshot,
        target_count=summary.target_count,
        size_bytes=summary.size_bytes,
        deleted_count=deleted,
        missing_paths=summary.missing_paths,
        targets=summary.targets,
    )


def _resolve_slot_path(repo_root: Path, raw_path: str) -> Path:
    if "*" in raw_path or "?" in raw_path or "[" in raw_path:
        raise ValueError(f"Cleanup paths must not be globs: {raw_path}")
    path = Path(raw_path)
    candidate = path.resolve() if path.is_absolute() else (repo_root / path).resolve()
    _assert_under_runtime_root(repo_root, candidate)
    return candidate


def _assert_under_runtime_root(repo_root: Path, path: Path) -> None:
    runtime_root = (repo_root / ".polisyos").resolve()
    if path == runtime_root:
        raise ValueError("Cleanup must not target the .polisyos root")
    try:
        path.relative_to(runtime_root)
    except ValueError as exc:
        raise ValueError(f"Cleanup path escapes .polisyos: {path}") from exc


def _target_for(path: Path, repo_root: Path) -> CleanupTarget:
    kind = "directory" if path.is_dir() else "file"
    return CleanupTarget(path=_relative(path, repo_root), kind=kind, size_bytes=_size_bytes(path))


def _size_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def _relative(path: Path, repo_root: Path) -> str:
    return path.resolve().relative_to(repo_root).as_posix()


def _report_to_dict(report: CleanupReport) -> dict[str, Any]:
    return asdict(report)


def _format_size(size_bytes: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(size_bytes)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size_bytes} B"


def render_text(report: CleanupReport, *, target_limit: int = 20) -> str:
    lines = [
        f"runtime-state-cleanup: {report.status}",
        f"dry_run: {str(report.dry_run).lower()}",
        f"repo_root: {report.repo_root}",
    ]
    if report.blocked_reasons:
        lines.append("blocked:")
        lines.extend(f"- {reason}" for reason in report.blocked_reasons)

    for summary in report.summaries:
        lines.extend(
            [
                "",
                f"slot: {summary.slot}",
                f"owner: {summary.owner}",
                f"retention_class: {summary.retention_class}",
                f"protected: {str(summary.protected).lower()}",
                f"production_snapshot: {str(summary.production_snapshot).lower()}",
                f"targets: {summary.target_count}",
                f"size: {_format_size(summary.size_bytes)}",
                f"deleted: {summary.deleted_count}",
            ]
        )
        if summary.missing_paths:
            lines.append(f"missing_paths: {len(summary.missing_paths)}")
        for target in summary.targets[:target_limit]:
            lines.append(f"- {target.path} ({target.kind}, {_format_size(target.size_bytes)})")
        remaining = summary.target_count - min(summary.target_count, target_limit)
        if remaining > 0:
            lines.append(f"- ... {remaining} more")
    return "\n".join(lines) + "\n"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--slot", action="append", required=True, help="Runtime-state slot id.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Render summary without deleting.")
    mode.add_argument("--apply", action="store_true", help="Delete selected slot contents.")
    parser.add_argument(
        "--approve-protected",
        action="store_true",
        help="Allow protected non-production slots to be deleted.",
    )
    parser.add_argument(
        "--approve-production-snapshots",
        action="store_true",
        help="Allow production_data cleanup when used with --apply.",
    )
    parser.add_argument("--output-format", choices=("text", "json"), default="text")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_cleanup_report(
        repo_root=args.repo_root,
        slots=args.slot,
        apply=bool(args.apply),
        approve_protected=bool(args.approve_protected),
        approve_production_snapshots=bool(args.approve_production_snapshots),
    )
    if args.output_format == "json":
        print(json.dumps(_report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(render_text(report), end="")
    return report.exit_code


def clean_slots(slots: Iterable[str], *, repo_root: Path = REPO_ROOT) -> CleanupReport:
    """Programmatic dry-run helper for tests and workspace audits."""
    return build_cleanup_report(repo_root=repo_root, slots=tuple(slots), apply=False)


if __name__ == "__main__":
    raise SystemExit(main())
