#!/usr/bin/env python3
"""Run SCM v3 verification checks and emit JSON/Markdown reports."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from tools._lib.imports import repo_root_from

if __package__ in {None, ""}:
    sys.path.insert(0, str(repo_root_from(__file__)))

from tools._lib.runner import parse_trusted_command, render_command, run_command

_ALLOWED_COMMAND_PREFIXES: tuple[tuple[str, ...], ...] = (("uv", "run", "python"),)


def _trusted_command(command: str) -> tuple[str, ...]:
    return parse_trusted_command(command, allowed_prefixes=_ALLOWED_COMMAND_PREFIXES)


@dataclass(frozen=True)
class CheckSpec:
    label: str
    phase: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CheckResult:
    label: str
    phase: str
    command: str
    status: str
    exit_code: int
    log: str
    duration_sec: float


QUICK_CHECKS: tuple[CheckSpec, ...] = (
    CheckSpec(
        label="gate_lint_imports",
        phase="phase--1",
        command=_trusted_command(
            "uv run python tools/lint/lint_imports.py "
            "--policy import_policy.toml --exceptions import_exceptions.toml"
        ),
    ),
    CheckSpec(
        label="gate_lint_foundry",
        phase="phase--1",
        command=_trusted_command("uv run python tools/lint/lint_foundry.py --repo-root ."),
    ),
    CheckSpec(
        label="gate_schema_ir",
        phase="phase--1",
        command=_trusted_command(
            "uv run python tools/diagnostics/gen_schema.py "
            "--models ir --check --output-dir schemas/snapshots"
        ),
    ),
    CheckSpec(
        label="gate_schema_fabric",
        phase="phase--1",
        command=_trusted_command(
            "uv run python tools/diagnostics/gen_schema.py "
            "--models fabric --check --output-dir schemas/snapshots"
        ),
    ),
    CheckSpec(
        label="phase0_quality_integration",
        phase="phase-0",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/integration/test_phase0_quality_validation.py -m integration"
        ),
    ),
    CheckSpec(
        label="phase9_reconciliation",
        phase="phase-9",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/foundry/methods/catalog/causal/test_graph_reconciliation.py"
        ),
    ),
    CheckSpec(
        label="phase12_transportability",
        phase="phase-12",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/foundry/methods/catalog/causal/test_transport_check.py "
            "tests/scientist/test_run_transportability_node.py"
        ),
    ),
    CheckSpec(
        label="phase12b_symbolic_bridge",
        phase="phase-12b",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/foundry/methods/catalog/causal/test_symbolic_identify_y0.py "
            "tests/foundry/methods/catalog/causal/test_full_transport_bridge.py"
        ),
    ),
    CheckSpec(
        label="phase6_7_jax_ci_backend",
        phase="phase-6-7",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/foundry/methods/catalog/causal/test_ci_backends_jax.py "
            "tests/foundry/methods/catalog/causal/test_pcmci_discovery.py "
            "tests/foundry/methods/catalog/causal/test_constraint_discovery.py"
        ),
    ),
    CheckSpec(
        label="phase15_parameters",
        phase="phase-15",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/scientist/test_resolve_parameters_node.py "
            "tests/foundry/methods/catalog/causal/test_parameter_transfer.py"
        ),
    ),
)

FULL_CHECKS: tuple[CheckSpec, ...] = QUICK_CHECKS + (
    CheckSpec(
        label="causal_methods_suite",
        phase="phase-2-14",
        command=_trusted_command("uv run python -m pytest -q tests/foundry/methods/catalog/causal"),
    ),
    CheckSpec(
        label="governance_suite",
        phase="phase-8",
        command=_trusted_command("uv run python -m pytest -q tests/scientist/governance"),
    ),
    CheckSpec(
        label="ir_contracts_suite",
        phase="cross-layer",
        command=_trusted_command("uv run python -m pytest -q tests/ir"),
    ),
    CheckSpec(
        label="workflow_guards",
        phase="phase--1",
        command=_trusted_command(
            "uv run python -m pytest -q "
            "tests/scientist/test_causal_full_workflow_guard.py "
            "tests/scientist/test_default_workflow_guard.py"
        ),
    ),
)


def _run_check(
    spec: CheckSpec,
    *,
    repo_root: Path,
    logs_dir: Path,
    timeout_sec: int,
) -> CheckResult:
    started = datetime.now(UTC)
    log_path = logs_dir / f"{spec.label}.log"
    env = dict(os.environ)
    env["PYTHONPATH"] = "src:."
    with open(log_path, "w", encoding="utf-8") as log_file:
        log_file.write(f"$ {render_command(spec.command)}\n")
        log_file.flush()
        try:
            proc = run_command(
                spec.command,
                cwd=repo_root,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                env=env,
                timeout=max(60, int(timeout_sec)),
                check=False,
                allowed_prefixes=_ALLOWED_COMMAND_PREFIXES,
            )
            exit_code = int(proc.returncode)
            status = "PASS" if exit_code == 0 else "FAIL"
        except subprocess.TimeoutExpired as exc:
            log_file.write(f"\n[TIMEOUT] {exc}\n")
            exit_code = 124
            status = "TIMEOUT"
    duration = (datetime.now(UTC) - started).total_seconds()
    return CheckResult(
        label=spec.label,
        phase=spec.phase,
        command=render_command(spec.command),
        status=status,
        exit_code=exit_code,
        log=str(log_path.relative_to(repo_root)),
        duration_sec=round(duration, 3),
    )


def _write_markdown(
    *,
    path: Path,
    generated_at: str,
    spec_path: Path,
    profile: str,
    results: list[CheckResult],
) -> None:
    status_counts: dict[str, int] = {}
    for result in results:
        status_counts[result.status] = status_counts.get(result.status, 0) + 1

    lines: list[str] = []
    lines.append("# SCM v3 Verification")
    lines.append("")
    lines.append(f"- Generated (UTC): `{generated_at}`")
    lines.append(f"- Spec: `{spec_path}`")
    lines.append(f"- Profile: `{profile}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    for key in sorted(status_counts):
        lines.append(f"- {key}: **{status_counts[key]}**")
    lines.append("")
    lines.append("## Checks")
    lines.append("")
    lines.append("| Label | Phase | Status | Duration (s) | Log |")
    lines.append("|---|---|---|---:|---|")
    for result in results:
        lines.append(
            f"| {result.label} | {result.phase} | {result.status} | "
            f"{result.duration_sec:.3f} | `{result.log}` |"
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify SCM v3 implementation on current HEAD.")
    parser.add_argument(
        "--profile",
        choices=("quick", "full"),
        default="quick",
        help="Check profile. quick is faster; full executes broader suites.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/reports"),
        help="Directory for evidence JSON and matrix Markdown.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=1800,
        help="Timeout per check command in seconds.",
    )
    args = parser.parse_args()

    repo_root = repo_root_from(__file__)
    output_dir = (repo_root / args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    logs_dir = output_dir / f"_logs_verify_{stamp}"
    logs_dir.mkdir(parents=True, exist_ok=True)

    checks = FULL_CHECKS if args.profile == "full" else QUICK_CHECKS
    results = [
        _run_check(
            spec,
            repo_root=repo_root,
            logs_dir=logs_dir,
            timeout_sec=int(args.timeout_sec),
        )
        for spec in checks
    ]

    generated_at = datetime.now(UTC).isoformat()
    evidence = {
        "generated_at_utc": generated_at,
        "profile": args.profile,
        "spec_path": str((repo_root.parent / "scm-implementation-spec-v3.md").resolve()),
        "workspace_root": str(repo_root),
        "checks": [asdict(item) for item in results],
        "summary": {
            "total": len(results),
            "pass": sum(1 for item in results if item.status == "PASS"),
            "fail": sum(1 for item in results if item.status == "FAIL"),
            "timeout": sum(1 for item in results if item.status == "TIMEOUT"),
        },
    }

    evidence_path = output_dir / f"scm_v3_verification_evidence_{stamp}.json"
    matrix_path = output_dir / f"scm_v3_verification_matrix_{stamp}.md"
    evidence_path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    _write_markdown(
        path=matrix_path,
        generated_at=generated_at,
        spec_path=(repo_root.parent / "scm-implementation-spec-v3.md").resolve(),
        profile=args.profile,
        results=results,
    )

    print(f"[verify_scm_v3] wrote: {evidence_path}")
    print(f"[verify_scm_v3] wrote: {matrix_path}")

    if any(item.status != "PASS" for item in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
