#!/usr/bin/env python3
"""Launch the MSME final v3 full rerun on the current GCP VM and download artifacts."""

from __future__ import annotations

import argparse
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


DEFAULT_PROJECT = "lex-1-494208"
DEFAULT_ZONE = "europe-west1-b"
DEFAULT_INSTANCE = "msme-replay-20260508"
DEFAULT_REMOTE_REPO = "/workspace/polisyos/policy-engine"
DEFAULT_REMOTE_PRODUCTION_DATA = "/workspace/polisyos/policy-engine/production_data"
DEFAULT_REMOTE_WORKDIR = "/workspace/experiments/msme_final_fresg_evaluation_v3_rerun_20260509"
DEFAULT_GCS_PREFIX = (
    "gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v3_rerun_20260509"
)


def utc_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"msme_final_fresg_evaluation_v3_full_rerun_{stamp}"


def quote(value: object) -> str:
    return shlex.quote(str(value))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--zone", default=DEFAULT_ZONE)
    parser.add_argument("--instance", default=DEFAULT_INSTANCE)
    parser.add_argument("--gcloud-bin", default="gcloud")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--remote-repo", default=DEFAULT_REMOTE_REPO)
    parser.add_argument("--remote-production-data", default=DEFAULT_REMOTE_PRODUCTION_DATA)
    parser.add_argument("--remote-workdir", default=DEFAULT_REMOTE_WORKDIR)
    parser.add_argument("--gcs-prefix", default=DEFAULT_GCS_PREFIX)
    parser.add_argument("--local-download-root", default=str(Path.home() / "Downloads"))
    parser.add_argument(
        "--profile",
        default="default",
        choices=("deadline_safe", "default", "stretch"),
    )
    parser.add_argument("--threads", type=int, default=12)
    parser.add_argument("--policy-count", type=int, default=192)
    parser.add_argument("--causal-panel-rows", type=int, default=750_000)
    parser.add_argument("--bootstrap-replicates", type=int, default=200)
    parser.add_argument("--discovery-bootstrap-resamples", type=int, default=100)
    parser.add_argument("--ranking-bootstrap-resamples", type=int, default=100)
    parser.add_argument("--agent-count", type=int, default=220_000)
    parser.add_argument("--simulation-seeds", type=int, default=64)
    parser.add_argument("--fairness-bootstrap-resamples", type=int, default=200)
    parser.add_argument("--skip-uv-sync", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def runner_command(args: argparse.Namespace, run_id: str) -> str:
    argv = [
        "uv",
        "run",
        "python",
        "tools/ops_runners/experiments/run_msme_final_fresg_suite_v3.py",
        "--mode",
        "run",
        "--profile",
        args.profile,
        "--run-id",
        run_id,
        "--repo-root",
        args.remote_repo,
        "--production-data",
        args.remote_production_data,
        "--workdir",
        args.remote_workdir,
        "--gcs-prefix",
        args.gcs_prefix,
        "--threads",
        args.threads,
        "--policy-count",
        args.policy_count,
        "--causal-panel-rows",
        args.causal_panel_rows,
        "--bootstrap-replicates",
        args.bootstrap_replicates,
        "--discovery-bootstrap-resamples",
        args.discovery_bootstrap_resamples,
        "--ranking-bootstrap-resamples",
        args.ranking_bootstrap_resamples,
        "--agent-count",
        args.agent_count,
        "--simulation-seeds",
        args.simulation_seeds,
        "--fairness-bootstrap-resamples",
        args.fairness_bootstrap_resamples,
    ]
    return " ".join(quote(part) for part in argv)


def remote_script(args: argparse.Namespace, run_id: str) -> str:
    uv_sync = "" if args.skip_uv_sync else "uv sync --all-extras --dev"
    return f"""
set -euo pipefail

export REPO={quote(args.remote_repo)}
export PRODUCTION_DATA={quote(args.remote_production_data)}
export WORKDIR={quote(args.remote_workdir)}
export GCS_PREFIX={quote(args.gcs_prefix)}
export RUN_ID={quote(run_id)}

cd "$REPO"

test -d "$PRODUCTION_DATA"
{uv_sync}

mkdir -p "$WORKDIR"

{runner_command(args, run_id)} 2>&1 | tee "$WORKDIR/${{RUN_ID}}.log"

gcloud storage rsync -r "$WORKDIR/$RUN_ID" "$GCS_PREFIX/$RUN_ID"

printf '\\nCloud rerun completed.\\n'
printf 'RUN_ID=%s\\n' "$RUN_ID"
printf 'GCS=%s/%s\\n' "$GCS_PREFIX" "$RUN_ID"
""".strip()


def run(argv: Sequence[str], *, dry_run: bool) -> int:
    sys.stdout.write("+ " + shlex.join(list(argv)) + "\n")
    if dry_run:
        return 0
    completed = subprocess.run(list(argv), check=False)  # noqa: S603
    return int(completed.returncode)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_id = args.run_id or utc_run_id()
    gcs_run_prefix = f"{args.gcs_prefix.rstrip('/')}/{run_id}"
    local_download = Path(args.local_download_root).expanduser() / run_id
    script = remote_script(args, run_id)

    ssh_argv = [
        args.gcloud_bin,
        "compute",
        "ssh",
        args.instance,
        f"--project={args.project}",
        f"--zone={args.zone}",
        f"--command={script}",
    ]

    sys.stdout.write(f"RUN_ID={run_id}\n")
    sys.stdout.write(f"GCS={gcs_run_prefix}\n")
    sys.stdout.write(f"LOCAL_DOWNLOAD={local_download}\n")
    if args.dry_run:
        sys.stdout.write("\n--- remote script ---\n")
        sys.stdout.write(script + "\n")

    exit_code = run(ssh_argv, dry_run=args.dry_run)
    if exit_code != 0:
        return exit_code

    if args.no_download:
        return 0

    local_download.mkdir(parents=True, exist_ok=True)
    download_argv = [
        args.gcloud_bin,
        "storage",
        "rsync",
        "-r",
        gcs_run_prefix,
        str(local_download),
    ]
    exit_code = run(download_argv, dry_run=args.dry_run)
    if exit_code == 0:
        sys.stdout.write(f"\nDownloaded rerun artifacts to: {local_download}\n")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
