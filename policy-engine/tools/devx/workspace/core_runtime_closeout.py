#!/usr/bin/env python3
"""Validate and render the CORE common/runtime closeout ledger."""

from __future__ import annotations

import argparse
import json
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from tools._lib.imports import repo_root_from

PRODUCT_ROOT = repo_root_from(__file__)
WORKSPACE_ROOT = PRODUCT_ROOT.parent
DEFAULT_LEDGER_PATH = PRODUCT_ROOT / "release" / "core-runtime-closeout.ledger.toml"
DEFAULT_PLAN_PATH = PRODUCT_ROOT / "docs" / "CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md"
VALID_STATUSES = frozenset({"implemented", "partial", "missing", "reopened"})
WORKSTREAM_HEADING_RE = re.compile(r"^###\s+(WS-\d[A-Z])\.")

MANUAL_CHECKS: dict[str, tuple[str, str]] = {
    "engineering_signoff": (
        "Engineering signoff",
        "Platform/runtime owners reviewed the closure ledger, "
        "confirmed the current statuses, and triaged every "
        "non-implemented workstream.",
    ),
    "operator_signoff": (
        "Operator signoff",
        "Operator-facing dashboards, runbooks, "
        "rotation/retention flows, and degraded-mode procedures "
        "were reviewed against the current implementation.",
    ),
    "release_review_bundle": (
        "Release-review bundle reviewed",
        "The latest core-runtime release-review bundle was "
        "inspected and matched the current CI gates, benchmark "
        "baselines, and alert/runbook references.",
    ),
    "reopened_followups": (
        "Residual follow-ups triaged",
        "Every partial/missing/reopened workstream has an "
        "explicit owner path or residual PR ticket before "
        "final closeout.",
    ),
}


@dataclass(frozen=True, slots=True)
class WorkstreamEntry:
    """One workstream row in the closeout ledger."""

    workstream_id: str
    title: str
    status: str
    summary: str
    blocking_gaps: tuple[str, ...]
    code_evidence: tuple[str, ...]
    test_evidence: tuple[str, ...]
    docs_evidence: tuple[str, ...]
    ops_evidence: tuple[str, ...]
    ci_evidence: tuple[str, ...]

    @property
    def evidence(self) -> tuple[str, ...]:
        return (
            *self.code_evidence,
            *self.test_evidence,
            *self.docs_evidence,
            *self.ops_evidence,
            *self.ci_evidence,
        )


@dataclass(frozen=True, slots=True)
class ManualEvidenceEntry:
    """Optional manual evidence attached to final closeout."""

    status: bool
    notes: str = ""
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ManualCheck:
    """Rendered status for one manual closeout requirement."""

    check_id: str
    title: str
    status: str
    detail: str
    evidence: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CloseoutReport:
    """Structured report for the core-runtime closeout ledger."""

    ledger_path: str
    plan_path: str
    workstreams: tuple[WorkstreamEntry, ...]
    manual_checks: tuple[ManualCheck, ...]

    @property
    def blocking_workstreams(self) -> tuple[WorkstreamEntry, ...]:
        return tuple(entry for entry in self.workstreams if entry.status != "implemented")

    @property
    def missing_manual(self) -> tuple[ManualCheck, ...]:
        return tuple(check for check in self.manual_checks if check.status != "pass")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate and render the CORE common/runtime closeout ledger.",
    )
    parser.add_argument(
        "--ledger",
        type=Path,
        default=DEFAULT_LEDGER_PATH,
        help="Ledger TOML path. Defaults to release/core-runtime-closeout.ledger.toml.",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN_PATH,
        help="Plan document used to validate workstream coverage.",
    )
    parser.add_argument(
        "--manual-evidence",
        type=Path,
        help="Optional TOML file with manual closeout evidence.",
    )
    parser.add_argument(
        "--require-manual-evidence",
        action="store_true",
        help="Fail when any manual closeout evidence is missing or false.",
    )
    parser.add_argument(
        "--require-full-closeout",
        action="store_true",
        help="Fail when any workstream remains partial/missing/reopened.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        help="Optional markdown summary output path.",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Optional JSON output path.",
    )
    return parser


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_path(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate

    product_candidate = PRODUCT_ROOT / candidate
    if product_candidate.exists():
        return product_candidate

    workspace_candidate = WORKSPACE_ROOT / candidate
    if workspace_candidate.exists():
        return workspace_candidate

    return product_candidate


def _normalize_string_list(
    payload: dict[str, object],
    key: str,
    *,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    raw_value = payload.get(key, list(default))
    if raw_value is None:
        return default
    if not isinstance(raw_value, list) or not all(isinstance(item, str) for item in raw_value):
        raise SystemExit(f"`{key}` must be a list of strings.")
    cleaned = tuple(item.strip() for item in raw_value if item.strip())
    return cleaned


def _expected_workstream_ids(plan_path: Path) -> tuple[str, ...]:
    ids: list[str] = []
    for line in _read_text(plan_path).splitlines():
        match = WORKSTREAM_HEADING_RE.match(line.strip())
        if match is not None:
            ids.append(match.group(1))
    if not ids:
        raise SystemExit(f"Failed to discover workstreams in plan: {plan_path}")
    return tuple(ids)


def _validate_evidence(paths: tuple[str, ...], *, field_name: str, workstream_id: str) -> None:
    for path in paths:
        resolved = _resolve_path(path)
        if not resolved.exists():
            raise SystemExit(
                f"{workstream_id}: evidence path from `{field_name}` does not exist: {path}"
            )


def load_manual_evidence(path: Path | None) -> dict[str, ManualEvidenceEntry]:
    """Load optional structured manual evidence entries from a TOML file."""

    if path is None:
        return {}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    manual = payload.get("manual", payload)
    if not isinstance(manual, dict):
        raise SystemExit(
            "manual evidence file must contain a [manual] table "
            "or top-level key/value pairs."
        )
    result: dict[str, ManualEvidenceEntry] = {}
    for key, value in manual.items():
        if key not in MANUAL_CHECKS:
            continue
        if isinstance(value, bool):
            result[key] = ManualEvidenceEntry(status=value)
            continue
        if not isinstance(value, dict):
            raise SystemExit(
                f"manual evidence value for `{key}` must be true/false or a table with `status`."
            )
        status = value.get("status")
        if not isinstance(status, bool):
            raise SystemExit(f"manual evidence table for `{key}` must contain boolean `status`.")
        notes = value.get("notes", "")
        if notes is None:
            notes = ""
        if not isinstance(notes, str):
            raise SystemExit(f"manual evidence table for `{key}` must use string `notes`.")
        evidence_value = value.get("evidence", [])
        if evidence_value is None:
            evidence_value = []
        if not isinstance(evidence_value, list) or not all(
            isinstance(item, str) for item in evidence_value
        ):
            raise SystemExit(f"manual evidence table for `{key}` must use string-list `evidence`.")
        result[key] = ManualEvidenceEntry(
            status=status,
            notes=notes.strip(),
            evidence=tuple(item for item in evidence_value if item.strip()),
        )
    return result


def _manual_checks(
    manual_evidence: dict[str, ManualEvidenceEntry],
    *,
    require_manual_evidence: bool,
    manual_path: Path | None,
) -> tuple[ManualCheck, ...]:
    checks: list[ManualCheck] = []
    default_evidence = (str(manual_path),) if manual_path is not None else ()
    for key, (title, expectation) in MANUAL_CHECKS.items():
        entry = manual_evidence.get(key)
        notes_suffix = f" Notes: {entry.notes}" if entry and entry.notes else ""
        evidence = (*default_evidence, *(entry.evidence if entry is not None else ()))
        if entry is not None and entry.status is True:
            checks.append(
                ManualCheck(
                    check_id=f"manual.{key}",
                    title=title,
                    status="pass",
                    detail=f"{expectation}{notes_suffix}",
                    evidence=evidence,
                )
            )
            continue
        if require_manual_evidence:
            status = "fail"
            detail = (
                f"{expectation} Record it in --manual-evidence "
                f"before final closeout.{notes_suffix}"
            )
        else:
            status = "pending"
            detail = f"{expectation} Not yet recorded in manual evidence.{notes_suffix}"
        checks.append(
            ManualCheck(
                check_id=f"manual.{key}",
                title=title,
                status=status,
                detail=detail,
                evidence=evidence,
            )
        )
    return tuple(checks)


def load_workstreams(ledger_path: Path, plan_path: Path) -> tuple[WorkstreamEntry, ...]:
    """Load and validate the closeout ledger against the plan document."""

    payload = tomllib.loads(ledger_path.read_text(encoding="utf-8"))
    raw_workstreams = payload.get("workstreams")
    if not isinstance(raw_workstreams, list):
        raise SystemExit("ledger must contain a [[workstreams]] array.")

    expected_ids = _expected_workstream_ids(plan_path)
    seen_ids: list[str] = []
    result: list[WorkstreamEntry] = []

    for item in raw_workstreams:
        if not isinstance(item, dict):
            raise SystemExit("each [[workstreams]] entry must be a table.")

        workstream_id = item.get("id")
        title = item.get("title")
        status = item.get("status")
        summary = item.get("summary")
        if not isinstance(workstream_id, str) or not workstream_id.strip():
            raise SystemExit("each workstream entry must define non-empty `id`.")
        if not isinstance(title, str) or not title.strip():
            raise SystemExit(f"{workstream_id}: missing non-empty `title`.")
        if not isinstance(status, str) or status not in VALID_STATUSES:
            raise SystemExit(
                f"{workstream_id}: `status` must be one of {sorted(VALID_STATUSES)}."
            )
        if not isinstance(summary, str) or not summary.strip():
            raise SystemExit(f"{workstream_id}: missing non-empty `summary`.")

        blocking_gaps = _normalize_string_list(item, "blocking_gaps")
        code_evidence = _normalize_string_list(item, "code_evidence")
        test_evidence = _normalize_string_list(item, "test_evidence")
        docs_evidence = _normalize_string_list(item, "docs_evidence")
        ops_evidence = _normalize_string_list(item, "ops_evidence")
        ci_evidence = _normalize_string_list(item, "ci_evidence")

        if status == "implemented" and blocking_gaps:
            raise SystemExit(
                f"{workstream_id}: implemented workstreams must "
                "not list `blocking_gaps`."
            )
        if status != "implemented" and not blocking_gaps:
            raise SystemExit(
                f"{workstream_id}: non-implemented workstreams "
                "must declare `blocking_gaps`."
            )
        if not any((code_evidence, test_evidence, docs_evidence, ops_evidence, ci_evidence)):
            raise SystemExit(f"{workstream_id}: at least one evidence path is required.")

        for field_name, paths in (
            ("code_evidence", code_evidence),
            ("test_evidence", test_evidence),
            ("docs_evidence", docs_evidence),
            ("ops_evidence", ops_evidence),
            ("ci_evidence", ci_evidence),
        ):
            _validate_evidence(paths, field_name=field_name, workstream_id=workstream_id)

        seen_ids.append(workstream_id)
        result.append(
            WorkstreamEntry(
                workstream_id=workstream_id,
                title=title.strip(),
                status=status,
                summary=summary.strip(),
                blocking_gaps=blocking_gaps,
                code_evidence=code_evidence,
                test_evidence=test_evidence,
                docs_evidence=docs_evidence,
                ops_evidence=ops_evidence,
                ci_evidence=ci_evidence,
            )
        )

    if len(set(seen_ids)) != len(seen_ids):
        raise SystemExit("ledger contains duplicate workstream ids.")

    missing_ids = [workstream_id for workstream_id in expected_ids if workstream_id not in seen_ids]
    unexpected_ids = [
        workstream_id for workstream_id in seen_ids if workstream_id not in expected_ids
    ]
    if missing_ids or unexpected_ids:
        parts: list[str] = []
        if missing_ids:
            parts.append(f"missing workstreams in ledger: {', '.join(missing_ids)}")
        if unexpected_ids:
            parts.append(f"unexpected workstreams in ledger: {', '.join(unexpected_ids)}")
        raise SystemExit("; ".join(parts))

    by_id = {entry.workstream_id: entry for entry in result}
    return tuple(by_id[workstream_id] for workstream_id in expected_ids)


def run_closeout(
    *,
    ledger_path: Path,
    plan_path: Path,
    manual_evidence: dict[str, ManualEvidenceEntry] | None = None,
    require_manual_evidence: bool = False,
    manual_path: Path | None = None,
) -> CloseoutReport:
    """Collect the core-runtime closeout report."""

    workstreams = load_workstreams(ledger_path, plan_path)
    manual_checks = _manual_checks(
        manual_evidence or {},
        require_manual_evidence=require_manual_evidence,
        manual_path=manual_path,
    )
    return CloseoutReport(
        ledger_path=str(ledger_path),
        plan_path=str(plan_path),
        workstreams=workstreams,
        manual_checks=manual_checks,
    )


def write_summary(path: Path, report: CloseoutReport) -> None:
    """Write a markdown summary for the core-runtime closeout ledger."""

    status_counts = {
        status: sum(1 for workstream in report.workstreams if workstream.status == status)
        for status in VALID_STATUSES
    }
    lines = [
        "# Core Runtime Closeout Ledger",
        "",
        f"- Plan: `{Path(report.plan_path).as_posix()}`",
        f"- Ledger: `{Path(report.ledger_path).as_posix()}`",
        f"- Implemented: {status_counts['implemented']}",
        f"- Partial: {status_counts['partial']}",
        f"- Missing: {status_counts['missing']}",
        f"- Reopened: {status_counts['reopened']}",
        f"- Manual checks pending/failing: {len(report.missing_manual)}",
        "",
        "| Workstream | Status | Code | Tests | Docs | Ops | CI |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for workstream in report.workstreams:
        lines.append(
            f"| {workstream.workstream_id} | {workstream.status} | "
            f"{len(workstream.code_evidence)} | "
            f"{len(workstream.test_evidence)} | {len(workstream.docs_evidence)} | "
            f"{len(workstream.ops_evidence)} | {len(workstream.ci_evidence)} |"
        )
    lines.append("")

    if report.blocking_workstreams:
        lines.extend(["## Reopen / Residual Gaps", ""])
        for workstream in report.blocking_workstreams:
            lines.append(f"### {workstream.workstream_id} — {workstream.title}")
            lines.append("")
            lines.append(workstream.summary)
            lines.append("")
            for gap in workstream.blocking_gaps:
                lines.append(f"- {gap}")
            lines.append("")
    else:
        lines.extend(
            [
                "## Reopen / Residual Gaps",
                "",
                "- No non-implemented workstreams remain in the ledger.",
                "",
            ]
        )

    lines.extend(["## Manual Closeout Checks", ""])
    for check in report.manual_checks:
        lines.append(f"- `{check.status}` {check.title}: {check.detail}")
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _workstream_payload(entry: WorkstreamEntry) -> dict[str, object]:
    return {
        "id": entry.workstream_id,
        "title": entry.title,
        "status": entry.status,
        "summary": entry.summary,
        "blocking_gaps": list(entry.blocking_gaps),
        "code_evidence": list(entry.code_evidence),
        "test_evidence": list(entry.test_evidence),
        "docs_evidence": list(entry.docs_evidence),
        "ops_evidence": list(entry.ops_evidence),
        "ci_evidence": list(entry.ci_evidence),
    }


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    manual_evidence = load_manual_evidence(args.manual_evidence)
    report = run_closeout(
        ledger_path=args.ledger.resolve(),
        plan_path=args.plan.resolve(),
        manual_evidence=manual_evidence,
        require_manual_evidence=args.require_manual_evidence,
        manual_path=args.manual_evidence.resolve() if args.manual_evidence else None,
    )

    if args.summary:
        write_summary(args.summary.resolve(), report)
    if args.json_output:
        args.json_output.resolve().write_text(
            json.dumps(
                {
                    "ledger_path": report.ledger_path,
                    "plan_path": report.plan_path,
                    "workstreams": [_workstream_payload(entry) for entry in report.workstreams],
                    "blocking_workstreams": [
                        _workstream_payload(entry) for entry in report.blocking_workstreams
                    ],
                    "manual_checks": [asdict(check) for check in report.manual_checks],
                    "manual_pending_or_failing": [asdict(check) for check in report.missing_manual],
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    for workstream in report.workstreams:
        print(
            f"[{workstream.status.upper()}] {workstream.workstream_id} "
            f"{workstream.title}: {workstream.summary}"
        )
        for gap in workstream.blocking_gaps:
            print(f"  - gap: {gap}")

    for check in report.manual_checks:
        print(f"[{check.status.upper()}] {check.title}: {check.detail}")

    if args.require_full_closeout and report.blocking_workstreams:
        print(
            "core-runtime closeout is incomplete: "
            f"{len(report.blocking_workstreams)} blocking workstream(s)."
        )
        return 1
    if args.require_manual_evidence and report.missing_manual:
        print(
            "core-runtime closeout is missing manual signoff: "
            f"{len(report.missing_manual)} check(s)."
        )
        return 1

    print("core-runtime closeout ledger validated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
