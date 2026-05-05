#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    name: str
    command: list[str]
    exit_code: int
    output: str


def _run(command: list[str], cwd: Path, name: str) -> CommandResult:
    proc = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )
    out = proc.stdout or ""
    err = proc.stderr or ""
    if err:
        if out and not out.endswith("\n"):
            out += "\n"
        out += err
    return CommandResult(name=name, command=command, exit_code=proc.returncode, output=out)


def _extract_section(text: str, header: str) -> list[str]:
    lines = text.splitlines()
    captured: list[str] = []
    in_section = False
    for line in lines:
        if line.strip() == header:
            in_section = True
            continue
        if not in_section:
            continue
        if not line.strip():
            break
        captured.append(line)
    return captured


def _count_import_violations(lint_output: str) -> int:
    rows = _extract_section(lint_output, "Violations:")
    if not rows:
        return 0
    if len(rows) == 1 and rows[0].strip().lower() == "none":
        return 0
    return sum(1 for row in rows if row.startswith("- "))


def _count_package_cycles(lint_output: str) -> int:
    rows = _extract_section(lint_output, "Cycles (runtime imports, package-level):")
    if not rows:
        return 0
    if len(rows) == 1 and rows[0].strip().lower() == "none":
        return 0
    return sum(1 for row in rows if row.startswith("- "))


def _count_pytest_collect_errors(test_collect_output: str) -> int:
    interrupted = re.search(
        r"Interrupted:\s*(\d+)\s+errors?\s+during collection",
        test_collect_output,
        flags=re.IGNORECASE,
    )
    if interrupted:
        return int(interrupted.group(1))

    summary_matches = re.findall(
        r"^ERROR\s+.+$",
        test_collect_output,
        flags=re.MULTILINE,
    )
    return len(summary_matches)


def _count_ruff_issues(ruff_output: str) -> int:
    match = re.search(r"Found\s+(\d+)\s+errors?\.", ruff_output)
    if match:
        return int(match.group(1))
    if "All checks passed!" in ruff_output:
        return 0
    return 0


def _count_missing_sources(repo_root: Path) -> tuple[int, list[str]]:
    sources = repo_root / "src" / "policy_engine.egg-info" / "SOURCES.txt"
    if not sources.exists():
        return 0, []
    missing: list[str] = []
    for raw in sources.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not (repo_root / line).exists():
            missing.append(line)
    return len(missing), missing


def _render_command_block(result: CommandResult) -> str:
    cmd = " ".join(result.command)
    body = result.output.rstrip()
    parts = [f"$ {cmd}", f"[exit_code={result.exit_code}]"]
    if body:
        parts.append(body)
    return "\n".join(parts) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect architecture freeze metrics and baseline artifacts."
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repository root directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("."),
        help="Directory for output artifacts.",
    )
    parser.add_argument(
        "--summary-path",
        type=Path,
        default=None,
        help="Optional explicit path for summary.json (defaults to <output-dir>/summary.json).",
    )
    parser.add_argument(
        "--print-summary",
        action="store_true",
        help="Print parsed summary metrics to stdout.",
    )
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.summary_path.resolve() if args.summary_path else output_dir / "summary.json"

    lint_imports = _run(
        [
            "python3",
            "tools/quality/lint/lint_imports.py",
            "--policy",
            "architecture/imports/policy.toml",
            "--exceptions",
            "architecture/imports/exceptions.toml",
            "--top",
            "80",
            "--fail-on-cycles",
            "--allow-type-checking",
        ],
        cwd=repo_root,
        name="lint_imports",
    )
    lint_connectors = _run(
        [
            "python3",
            "tools/quality/lint/lint_connectors.py",
            "--src-root",
            "src/polisyos/fabric/connectors",
        ],
        cwd=repo_root,
        name="lint_connectors",
    )
    check_scholar_imports = _run(
        ["python3", "tools/quality/lint/check_scholar_imports.py"],
        cwd=repo_root,
        name="check_scholar_imports",
    )
    pytest_collect = _run(
        ["pytest", "--collect-only", "-q"],
        cwd=repo_root,
        name="pytest_collect",
    )
    compileall = _run(
        ["python3", "-m", "compileall", "-q", "src/polisyos"],
        cwd=repo_root,
        name="compileall",
    )
    ruff = _run(
        ["python3", "-m", "ruff", "check", "src/polisyos", "tests", "--statistics"],
        cwd=repo_root,
        name="ruff_statistics",
    )

    import_gate_txt = (
        _render_command_block(lint_imports)
        + "\n"
        + _render_command_block(lint_connectors)
        + "\n"
        + _render_command_block(check_scholar_imports)
    )
    (output_dir / "import_gate.txt").write_text(import_gate_txt, encoding="utf-8")

    test_collect_txt = _render_command_block(pytest_collect)
    (output_dir / "test_collect.txt").write_text(test_collect_txt, encoding="utf-8")

    compileall_txt = _render_command_block(compileall)
    (output_dir / "compileall.txt").write_text(compileall_txt, encoding="utf-8")

    ruff_txt = _render_command_block(ruff)
    (output_dir / "ruff_stats.txt").write_text(ruff_txt, encoding="utf-8")

    stale_missing_count, stale_missing = _count_missing_sources(repo_root)
    (output_dir / "stale_sources_missing_paths.txt").write_text(
        "\n".join(stale_missing) + ("\n" if stale_missing else ""),
        encoding="utf-8",
    )

    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "package_cycles_count": _count_package_cycles(lint_imports.output),
        "import_violations_count": _count_import_violations(lint_imports.output),
        "test_collect_errors_count": _count_pytest_collect_errors(pytest_collect.output),
        "ruff_total_issues": _count_ruff_issues(ruff.output),
        "stale_sources_missing_paths_count": stale_missing_count,
        "commands": {
            lint_imports.name: lint_imports.exit_code,
            lint_connectors.name: lint_connectors.exit_code,
            check_scholar_imports.name: check_scholar_imports.exit_code,
            pytest_collect.name: pytest_collect.exit_code,
            compileall.name: compileall.exit_code,
            ruff.name: ruff.exit_code,
        },
    }
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )

    if args.print_summary:
        print(json.dumps(summary, indent=2, ensure_ascii=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
