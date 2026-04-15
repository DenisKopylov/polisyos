#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import datetime
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


REQUIRED_KEYS = (
    "package_cycles_count",
    "import_violations_count",
    "test_collect_errors_count",
    "ruff_total_issues",
    "stale_sources_missing_paths_count",
)

DELTA_ALIASES = {
    "package_cycles_count": "delta_package_cycles",
    "import_violations_count": "delta_import_violations",
    "test_collect_errors_count": "delta_test_collect_errors",
    "ruff_total_issues": "delta_ruff_total_issues",
    "stale_sources_missing_paths_count": "delta_stale_sources_missing_paths",
}


@dataclass(frozen=True)
class Delta:
    key: str
    alias: str
    baseline: int
    current: int
    delta: int


@dataclass(frozen=True)
class ExceptionFinding:
    level: str
    message: str


def _load_summary(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    result: dict[str, int] = {}
    for key in REQUIRED_KEYS:
        if key not in payload:
            raise ValueError(f"Missing key in {path}: {key}")
        try:
            result[key] = int(payload[key])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid integer value for {key} in {path}: {payload[key]}") from exc
    return result


def _parse_registry_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) < 3:
            continue
        first = parts[1].strip().strip("`")
        if not first or first in {"id", "---", "_no-active-exceptions_", "-"}:
            continue
        ids.add(first)
    return ids


def _validate_exceptions(
    exceptions_path: Path,
    registry_path: Path,
    *,
    max_expiry_days: int,
) -> list[ExceptionFinding]:
    findings: list[ExceptionFinding] = []
    if not exceptions_path.exists():
        findings.append(
            ExceptionFinding(level="error", message=f"Exceptions file not found: {exceptions_path}")
        )
        return findings

    try:
        data = tomllib.loads(exceptions_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        findings.append(
            ExceptionFinding(level="error", message=f"Invalid TOML in {exceptions_path}: {exc}")
        )
        return findings

    today = datetime.date.today()
    max_expiry = today + datetime.timedelta(days=max_expiry_days)
    entries = data.get("exception", [])
    if not isinstance(entries, list):
        findings.append(
            ExceptionFinding(level="error", message="`exception` section must be an array of tables.")
        )
        return findings

    seen_ids: set[str] = set()
    registry_ids = _parse_registry_ids(registry_path)
    if not registry_path.exists():
        findings.append(
            ExceptionFinding(
                level="error",
                message=f"Exceptions registry file not found: {registry_path}",
            )
        )

    for idx, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            findings.append(
                ExceptionFinding(level="error", message=f"exception[{idx}] must be a table.")
            )
            continue

        exception_id = str(item.get("id", "")).strip()
        owner = str(item.get("owner", "")).strip()
        reason = str(item.get("reason", "")).strip()
        expires_raw = str(item.get("expires", "")).strip()

        if not exception_id:
            findings.append(
                ExceptionFinding(level="error", message=f"exception[{idx}] missing required field `id`.")
            )
        elif exception_id in seen_ids:
            findings.append(
                ExceptionFinding(level="error", message=f"duplicate exception id: {exception_id}")
            )
        else:
            seen_ids.add(exception_id)

        if not owner:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=f"exception[{idx}] ({exception_id or 'no-id'}) missing required field `owner`.",
                )
            )
        if not reason:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=f"exception[{idx}] ({exception_id or 'no-id'}) missing required field `reason`.",
                )
            )
        if not expires_raw:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=f"exception[{idx}] ({exception_id or 'no-id'}) missing required field `expires`.",
                )
            )
            continue

        try:
            expires = datetime.date.fromisoformat(expires_raw)
        except ValueError:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=f"exception[{idx}] ({exception_id or 'no-id'}) has invalid date `{expires_raw}`.",
                )
            )
            continue

        if expires < today:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=f"exception `{exception_id or 'no-id'}` is expired (expires {expires.isoformat()}).",
                )
            )
        if expires > max_expiry:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=(
                        f"exception `{exception_id or 'no-id'}` exceeds max expiry window "
                        f"({max_expiry_days} days): {expires.isoformat()}."
                    ),
                )
            )

        if exception_id and registry_path.exists() and exception_id not in registry_ids:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=(
                        f"exception `{exception_id}` missing in registry "
                        f"{registry_path.as_posix()}."
                    ),
                )
            )

    return findings


def _validate_exception_debt_mapping(
    exceptions_path: Path,
    debt_register_path: Path,
) -> list[ExceptionFinding]:
    findings: list[ExceptionFinding] = []
    if not exceptions_path.exists():
        return findings
    if not debt_register_path.exists():
        findings.append(
            ExceptionFinding(
                level="error",
                message=f"Debt register file not found: {debt_register_path}",
            )
        )
        return findings

    try:
        data = tomllib.loads(exceptions_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        findings.append(
            ExceptionFinding(level="error", message=f"Invalid TOML in {exceptions_path}: {exc}")
        )
        return findings

    exception_ids: set[str] = set()
    for item in data.get("exception", []):
        if not isinstance(item, dict):
            continue
        exception_id = str(item.get("id", "")).strip()
        if exception_id:
            exception_ids.add(exception_id)

    try:
        with debt_register_path.open("r", encoding="utf-8", newline="") as fh:
            reader = csv.DictReader(fh)
            if "exception_id" not in (reader.fieldnames or []):
                findings.append(
                    ExceptionFinding(
                        level="error",
                        message=f"Column `exception_id` is missing in {debt_register_path}",
                    )
                )
                return findings
            debt_exception_ids = {
                str((row.get("exception_id") or "")).strip()
                for row in reader
                if str((row.get("exception_id") or "")).strip()
            }
    except Exception as exc:
        findings.append(
            ExceptionFinding(
                level="error",
                message=f"Unable to parse debt register {debt_register_path}: {exc}",
            )
        )
        return findings

    for exception_id in sorted(exception_ids):
        if exception_id not in debt_exception_ids:
            findings.append(
                ExceptionFinding(
                    level="error",
                    message=(
                        f"exception `{exception_id}` is not mapped in "
                        f"{debt_register_path.as_posix()} column `exception_id`."
                    ),
                )
            )

    return findings


def _extract_deep_import_violations(path: Path) -> set[str]:
    if not path.exists():
        return set()
    violations: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if "[ARCH004]" in line or "[ARCH006]" in line:
            normalized = line.strip()
            if normalized.startswith("- "):
                violations.add(normalized)
    return violations


def _detect_new_deep_imports(
    baseline_import_gate: Path,
    current_import_gate: Path,
) -> list[ExceptionFinding]:
    findings: list[ExceptionFinding] = []
    if not baseline_import_gate.exists():
        findings.append(
            ExceptionFinding(
                level="error",
                message=f"Baseline import gate file not found: {baseline_import_gate}",
            )
        )
        return findings
    if not current_import_gate.exists():
        findings.append(
            ExceptionFinding(
                level="error",
                message=f"Current import gate file not found: {current_import_gate}",
            )
        )
        return findings

    baseline_deep = _extract_deep_import_violations(baseline_import_gate)
    current_deep = _extract_deep_import_violations(current_import_gate)
    added = sorted(current_deep - baseline_deep)
    for row in added:
        findings.append(
            ExceptionFinding(
                level="error",
                message=f"new deep-import violation detected: {row}",
            )
        )
    return findings


def _format_delta(delta: Delta) -> str:
    sign = "+" if delta.delta > 0 else ""
    return (
        f"- {delta.alias} ({delta.key}): baseline={delta.baseline}, current={delta.current}, "
        f"delta={sign}{delta.delta}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare architecture metrics against baseline summary.json."
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("summary.json"),
        help="Path to baseline summary.json.",
    )
    parser.add_argument(
        "--current",
        type=Path,
        required=True,
        help="Path to current metrics summary.json.",
    )
    parser.add_argument(
        "--mode",
        choices=("dry-run", "blocking"),
        default="dry-run",
        help="Freeze mode. blocking returns non-zero on violations.",
    )
    parser.add_argument(
        "--exceptions",
        type=Path,
        default=Path("import_exceptions.toml"),
        help="Path to import exceptions TOML.",
    )
    parser.add_argument(
        "--exceptions-registry",
        type=Path,
        default=Path("import_exceptions_registry.md"),
        help="Path to exceptions registry markdown.",
    )
    parser.add_argument(
        "--max-expiry-days",
        type=int,
        default=90,
        help="Maximum allowed exception expiry horizon in days.",
    )
    parser.add_argument(
        "--report-json",
        type=Path,
        default=None,
        help="Optional path to write structured comparison report.",
    )
    parser.add_argument(
        "--baseline-import-gate",
        type=Path,
        default=Path("import_gate.txt"),
        help="Path to baseline import_gate.txt.",
    )
    parser.add_argument(
        "--current-import-gate",
        type=Path,
        default=Path("import_gate.txt"),
        help="Path to current import_gate.txt.",
    )
    parser.add_argument(
        "--debt-register",
        type=Path,
        default=Path("import_debt_register.csv"),
        help="Path to import debt register CSV with exception_id column.",
    )
    args = parser.parse_args()

    try:
        baseline = _load_summary(args.baseline)
        current = _load_summary(args.current)
    except Exception as exc:
        print(f"[ERROR] {exc}")
        return 2

    deltas = [
        Delta(
            key=key,
            alias=DELTA_ALIASES.get(key, f"delta_{key}"),
            baseline=baseline[key],
            current=current[key],
            delta=current[key] - baseline[key],
        )
        for key in REQUIRED_KEYS
    ]

    gate_keys = (
        "package_cycles_count",
        "import_violations_count",
        "test_collect_errors_count",
    )
    growth = [item for item in deltas if item.key in gate_keys and item.delta > 0]
    strict_findings: list[str] = []
    current_import_violations = current["import_violations_count"]
    if current_import_violations > 0:
        strict_findings.append(
            "unmanaged import violations must be 0 under Import Policy v2 "
            f"(current={current_import_violations})"
        )
    exception_findings = _validate_exceptions(
        args.exceptions,
        args.exceptions_registry,
        max_expiry_days=args.max_expiry_days,
    )
    debt_mapping_findings = _validate_exception_debt_mapping(
        args.exceptions,
        args.debt_register,
    )
    deep_import_findings = _detect_new_deep_imports(
        args.baseline_import_gate,
        args.current_import_gate,
    )

    print("Architecture Freeze Comparison")
    print("")
    print(f"Mode: {args.mode}")
    print(f"Baseline: {args.baseline.as_posix()}")
    print(f"Current: {args.current.as_posix()}")
    print("")
    print("Metric deltas:")
    for item in deltas:
        print(_format_delta(item))
    print("")

    if growth:
        print("Freeze violations:")
        for item in growth:
            print(f"- metric `{item.alias}` regressed by +{item.delta}")
        for item in strict_findings:
            print(f"- {item}")
        print("")
    elif strict_findings:
        print("Freeze violations:")
        for item in strict_findings:
            print(f"- {item}")
        print("")
    else:
        print("Freeze violations: none")
        print("")

    all_exception_findings = exception_findings + debt_mapping_findings + deep_import_findings

    if all_exception_findings:
        print("Exception policy findings:")
        for finding in all_exception_findings:
            print(f"- [{finding.level.upper()}] {finding.message}")
        print("")
    else:
        print("Exception policy findings: none")
        print("")

    report = {
        "mode": args.mode,
        "baseline_path": args.baseline.as_posix(),
        "current_path": args.current.as_posix(),
        "deltas": [item.__dict__ for item in deltas],
        "freeze_regressions": [item.__dict__ for item in growth],
        "strict_findings": strict_findings,
        "exception_findings": [finding.__dict__ for finding in all_exception_findings],
    }
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    if args.mode == "blocking" and (growth or strict_findings or all_exception_findings):
        print("[FAIL] Architecture freeze blocking conditions are not satisfied.")
        return 1

    if args.mode == "dry-run" and (growth or strict_findings or all_exception_findings):
        print("[WARN] Architecture freeze dry-run detected regressions/findings.")
    else:
        print("[OK] Architecture freeze checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
