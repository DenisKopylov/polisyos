"""Evaluate vulnerability reports against PolicyOS release policy exceptions."""

from __future__ import annotations

import argparse
import json
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

SEVERITY_RANK = {
    "unknown": 0,
    "negligible": 0,
    "low": 1,
    "medium": 2,
    "moderate": 2,
    "high": 3,
    "critical": 4,
}


@dataclass(slots=True)
class Vulnerability:
    vuln_id: str
    severity: str
    package: str
    version: str
    fix_version: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate SBOM vulnerability policy")
    parser.add_argument("--report", required=True, help="Grype JSON report path")
    parser.add_argument("--exceptions", required=True, help="TOML exception policy path")
    parser.add_argument("--fail-on-severity", default="high", help="Minimum blocking severity")
    parser.add_argument("--summary", help="Optional markdown summary output path")
    return parser.parse_args()


def load_vulnerabilities(path: Path) -> list[Vulnerability]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    vulns: list[Vulnerability] = []
    for match in payload.get("matches", []):
        vuln = match.get("vulnerability") or {}
        artifact = match.get("artifact") or {}
        fix = match.get("fix") or {}
        vulns.append(
            Vulnerability(
                vuln_id=str(vuln.get("id", "unknown")),
                severity=str(vuln.get("severity", "unknown")).lower(),
                package=str(artifact.get("name", "unknown")),
                version=str(artifact.get("version", "")),
                fix_version=str(fix.get("versions", [""])[0]) if fix.get("versions") else "",
            )
        )
    return vulns


def load_exceptions(path: Path) -> list[dict[str, str]]:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    return list(payload.get("exception", []))


def evaluate(
    vulns: list[Vulnerability], exceptions: list[dict[str, str]], threshold: str
) -> tuple[list[Vulnerability], list[str]]:
    threshold_rank = SEVERITY_RANK[threshold.lower()]
    today = date.today()
    blockers: list[Vulnerability] = []
    notes: list[str] = []

    for vuln in vulns:
        if SEVERITY_RANK.get(vuln.severity, 0) < threshold_rank:
            continue

        matched_exception = None
        for exception in exceptions:
            package = exception.get("package", "").strip()
            if exception.get("id") != vuln.vuln_id:
                continue
            if package and package != vuln.package:
                continue
            matched_exception = exception
            break

        if matched_exception is None:
            blockers.append(vuln)
            continue

        expiry = matched_exception.get("expires_on")
        if not expiry:
            blockers.append(vuln)
            notes.append(f"{vuln.vuln_id} has an exception without expires_on")
            continue

        if date.fromisoformat(expiry) < today:
            blockers.append(vuln)
            notes.append(f"{vuln.vuln_id} exception expired on {expiry}")
            continue

        reason = matched_exception.get("reason", "no reason recorded")
        notes.append(f"{vuln.vuln_id} tolerated until {expiry}: {reason}")

    return blockers, notes


def write_summary(
    path: Path,
    vulnerabilities: list[Vulnerability],
    blockers: list[Vulnerability],
    notes: list[str],
) -> None:
    lines = ["# Vulnerability Policy Summary", ""]
    lines.append(f"- Reported matches: {len(vulnerabilities)}")
    lines.append(f"- Blocking matches: {len(blockers)}")
    lines.append("")

    if blockers:
        lines.extend(
            [
                "## Blocking Findings",
                "",
                "| ID | Severity | Package | Version | Fix |",
                "|---|---|---|---|---|",
            ]
        )
        for vuln in blockers:
            lines.append(
                f"| `{vuln.vuln_id}` | {vuln.severity} | `{vuln.package}` | `{vuln.version}` | `{vuln.fix_version or 'n/a'}` |"
            )
        lines.append("")

    if notes:
        lines.extend(["## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    args = parse_args()
    vulnerabilities = load_vulnerabilities(Path(args.report))
    exceptions = load_exceptions(Path(args.exceptions))
    blockers, notes = evaluate(vulnerabilities, exceptions, args.fail_on_severity)

    if args.summary:
        write_summary(Path(args.summary), vulnerabilities, blockers, notes)

    if blockers:
        for vuln in blockers:
            print(
                f"Blocking vulnerability: {vuln.vuln_id} {vuln.severity} "
                f"{vuln.package}@{vuln.version}"
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
