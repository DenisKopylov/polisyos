#!/usr/bin/env python3
"""Run the Ukraine repository-only Part A gate from the ops layer."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from polisyos.data_forge.domains.ukraine.manifests import (
    PartAGateManifest,
    utc_now_iso,
)
from polisyos.data_forge.domains.ukraine.orchestrator import (
    UkraineDataOrchestrator,
    load_pipeline_config,
)
from polisyos.data_forge.domains.ukraine.server import (
    PartAGateRunner,
    classify_part_a_gate_result,
    is_repository_checkout,
)
from polisyos.data_forge.domains.ukraine.server import (
    run_part_a_gate as _run_gate_with_runner,
)

if TYPE_CHECKING:
    from polisyos.data_forge.domains.ukraine.models import PipelineConfig, ServerConfig


def _run_repository_gate(config: ServerConfig, workspace_root: Path | None) -> PartAGateManifest:
    """Execute C7 against the supplied checkout after domain admission."""

    if workspace_root is None or not is_repository_checkout(workspace_root):
        # The outer domain adapter normally performs this check.  Keep the
        # callback fail-closed when it is called directly by an ops consumer.
        reason = (
            "repository checkout is unavailable for the installed package"
            if workspace_root is None
            else f"repository checkout is unavailable at {workspace_root}"
        )
        return PartAGateManifest(
            status="unavailable",
            command=[],
            server_only=True,
            passed=False,
            skipped=False,
            notes=[reason],
        )

    command = [
        config.uv_bin,
        "run",
        "pytest",
        "-q",
        "tests/integration/test_c7_synthetic_full_pipeline.py",
    ]
    env = dict(os.environ)
    env["POLISYOS_RUN_INTEGRATION"] = "1"
    completed = subprocess.run(
        command,
        cwd=workspace_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    stdout = completed.stdout or ""
    status, passed, skipped = classify_part_a_gate_result(completed.returncode, stdout)
    notes: list[str] = []
    if stdout.strip():
        notes.append(stdout.strip()[-5000:])
    stderr = (completed.stderr or "").strip()
    if stderr:
        notes.append(stderr[-2000:])
    return PartAGateManifest(
        status=status,
        command=command,
        server_only=True,
        passed=passed,
        skipped=skipped,
        created_at=utc_now_iso(),
        notes=notes,
    )


def run_part_a_gate(config: ServerConfig, workspace_root: Path | None) -> PartAGateManifest:
    """Run the repository gate through the ops-owned subprocess callback."""

    runner: PartAGateRunner = _run_repository_gate
    return _run_gate_with_runner(config, workspace_root, runner=runner)


def build_orchestrator(
    config: PipelineConfig,
    workspace_root: Path | None,
) -> UkraineDataOrchestrator:
    """Compose the domain orchestrator with this ops-owned gate runner."""

    return UkraineDataOrchestrator(
        config,
        workspace_root=workspace_root,
        part_a_gate_runner=run_part_a_gate,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--root", type=Path, default=None, help="Artifact/build root.")
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=None,
        help="Repository checkout containing the C7 integration test.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Execute the gate and persist its typed manifest for the operator."""

    args = _build_parser().parse_args(argv)
    config = load_pipeline_config(args.config, root=args.root)
    summary = build_orchestrator(config, args.workspace_root).validate_part_a()
    print(
        json.dumps(
            summary.manifest.model_dump(mode="json"),
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary.status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
