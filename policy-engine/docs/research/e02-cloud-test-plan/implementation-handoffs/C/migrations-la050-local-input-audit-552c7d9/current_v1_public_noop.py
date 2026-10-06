"""Run the installed 004 DatasetManifest CLI against private local input copies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path


RUNNER = "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/" \
    "polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/venv-base/bin/polisyos-tools"
SOURCE_CWD = "/Users/deniskopylov/.codex/worktrees/e02-c-continuation-20261006/" \
    "polisyos/.tmp/e02-C2/raw/installed/mig-004ae11/source/source/policy-engine"
SOURCE_ROOT = Path(
    "/Users/deniskopylov/polisyos/policy-engine/production_data/canonical/"
    "local_data_20260501/policy_engine_data/curated"
)
NAMES = ("agents", "entity_resolution", "interactions", "macro")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--commands-dir", required=True, type=Path)
    parser.add_argument("--receipt-path", required=True, type=Path)
    args = parser.parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = args.output_dir.resolve()
    commands_dir = args.commands_dir.resolve()
    if output_dir.exists() or commands_dir.exists():
        raise SystemExit("Refusing to overwrite an existing output/commands directory.")
    output_dir.mkdir(mode=0o700)
    commands_dir.mkdir(mode=0o700)
    inputs_dir = run_dir / "inputs"
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYTHONHOME", None)
    results = []
    for name in NAMES:
        original = SOURCE_ROOT / f"{name}_manifest.json"
        copied_input = inputs_dir / f"{name}-manifest.json"
        output = output_dir / f"{name}-manifest.json"
        original_before = _sha256(original)
        input_before = _sha256(copied_input)
        argv = [
            RUNNER,
            "migrations",
            "migrate",
            "dataset_manifest",
            str(copied_input),
            str(output),
            "--to",
            "1.0",
        ]
        started = time.monotonic()
        process = subprocess.run(
            argv,
            cwd=SOURCE_CWD,
            env=environment,
            capture_output=True,
            timeout=90,
        )
        elapsed = time.monotonic() - started
        stdout_path = commands_dir / f"{name}-public-cli.stdout"
        stderr_path = commands_dir / f"{name}-public-cli.stderr"
        exit_path = commands_dir / f"{name}-public-cli.exit"
        stdout_path.write_bytes(process.stdout)
        stderr_path.write_bytes(process.stderr)
        exit_path.write_text(f"{process.returncode}\n")
        row = {
            "name": name,
            "original_path": str(original),
            "original_sha256_before": original_before,
            "original_sha256_after": _sha256(original),
            "input_copy_path": str(copied_input),
            "input_copy_bytes": copied_input.stat().st_size,
            "input_copy_sha256_before": input_before,
            "input_copy_sha256_after": _sha256(copied_input),
            "input_copy_unchanged": input_before == _sha256(copied_input),
            "original_unchanged": original_before == _sha256(original),
            "output_path": str(output),
            "output_exists": output.is_file(),
            "output_bytes": output.stat().st_size if output.is_file() else None,
            "output_sha256": _sha256(output) if output.is_file() else None,
            "json_semantically_equal": (
                json.loads(copied_input.read_bytes()) == json.loads(output.read_bytes())
                if output.is_file()
                else False
            ),
            "argv": argv,
            "cwd": SOURCE_CWD,
            "environment_delta": {"PYTHONPATH": "unset", "PYTHONHOME": "unset"},
            "elapsed_seconds": elapsed,
            "exit_code": process.returncode,
            "stdout_path": str(stdout_path),
            "stdout_bytes": len(process.stdout),
            "stdout_sha256": _sha256(stdout_path),
            "stdout_text": process.stdout.decode("utf-8", errors="replace"),
            "stderr_path": str(stderr_path),
            "stderr_bytes": len(process.stderr),
            "stderr_sha256": _sha256(stderr_path),
            "stderr_text": process.stderr.decode("utf-8", errors="replace"),
            "exit_path": str(exit_path),
            "exit_sha256": _sha256(exit_path),
        }
        results.append(row)
    receipt = {
        "source_candidate": {
            "commit": "004ae11f1a541e2035f71cefa92f89b71bd8f562",
            "tree": "5369c0167bc63096a12ee1bea666b42c837ea78b",
        },
        "installed_wheel_sha256": "6e675a4750312d28098b598abd595805152ffb71bfdef4795609861dee599eb9",
        "input_scope": "Only pre-copied private JSON inputs are passed to the installed CLI. Original local manifests are hashed for before/after preservation checks, never passed as CLI inputs.",
        "private_run_dir": str(run_dir),
        "public_cli_results": results,
    }
    receipt_path = args.receipt_path.resolve()
    if receipt_path.exists():
        raise SystemExit("Refusing to overwrite an existing command receipt.")
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(receipt, sort_keys=True))
    failed = [
        row["name"]
        for row in results
        if row["exit_code"] != 0
        or not row["output_exists"]
        or not row["json_semantically_equal"]
        or not row["original_unchanged"]
        or not row["input_copy_unchanged"]
    ]
    if failed:
        raise SystemExit(f"Current-version CLI property failed for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
