#!/usr/bin/env python3
"""Launch a PolicyOS natural-language E2E run on a GCP VM.

The launcher is intentionally resource-aware: it derives a safe CPU budget from
the target machine, sets runtime parallelism env vars, and avoids accidentally
serializing multiple LLM model variants on large VMs.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


DEFAULT_PROJECT = "lex-1-494208"
DEFAULT_ZONE = "europe-west1-b"
DEFAULT_INSTANCE = "msme-replay-20260508"
DEFAULT_REMOTE_REPO = "/workspace/polisyos/policy-engine"
DEFAULT_BUCKET = "gs://lex-1-494208-data"
DEFAULT_REMOTE_CREDENTIAL_FILE = "/tmp/gonka_proxy_key.txt"
DEFAULT_MODELS = (
    "Qwen/Qwen3-235B-A22B-Instruct-2507-FP8",
    "moonshotai/Kimi-K2.6",
)
LIVE_PROVIDER_ENV = "POLISYOS_LLM_GATEWAY_API_KEY"


def _quote(value: object) -> str:
    return shlex.quote(str(value))


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def live_provider_credentials_present(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    return bool(str(source.get(LIVE_PROVIDER_ENV) or "").strip())


def _write_json(path: Path | str, payload: dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=DEFAULT_PROJECT)
    parser.add_argument("--zone", default=DEFAULT_ZONE)
    parser.add_argument("--instance", default=DEFAULT_INSTANCE)
    parser.add_argument("--gcloud-bin", default="gcloud")
    parser.add_argument("--remote-repo", default=DEFAULT_REMOTE_REPO)
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    parser.add_argument("--port", type=int, default=8017)
    parser.add_argument("--run-label", default="policyos-msme-full-real")
    parser.add_argument("--mode", choices=("real", "simulated"), default="real")
    parser.add_argument(
        "--allow-live-provider",
        action="store_true",
        help="Permit real live-provider execution. Required for --mode=real.",
    )
    parser.add_argument(
        "--credential-file",
        default=DEFAULT_REMOTE_CREDENTIAL_FILE,
        help="Remote file containing the live-provider API key.",
    )
    parser.add_argument("--json-output", default="", help="Optional launcher summary JSON path.")
    parser.add_argument(
        "--replace-runtime",
        action="store_true",
        help="Stop an existing uvicorn runtime on the target port before launching.",
    )
    parser.add_argument("--max-iterations", type=int, default=4)
    parser.add_argument("--max-parallel-models", type=int, default=0)
    parser.add_argument("--safe-core-reserve", type=int, default=1)
    parser.add_argument("--llm-timeout-s", type=int, default=90)
    parser.add_argument("--llm-max-retries", type=int, default=2)
    parser.add_argument("--run-timeout-s", type=int, default=7200)
    parser.add_argument("--runner-max-parallelism", type=int, default=0)
    parser.add_argument("--swarm-max-workers", type=int, default=0)
    parser.add_argument("--swarm-max-parallel", type=int, default=0)
    parser.add_argument("--model", action="append", dest="models", default=[])
    parser.add_argument("--dry-run", action="store_true")
    return parser


def _request_payload(args: argparse.Namespace) -> dict[str, Any]:
    models = args.models or list(DEFAULT_MODELS)
    return {
        "request": (
            "Розроби оптимальну державну політику підтримки малого та середнього "
            "бізнесу України в умовах воєнного часу та післявоєнного відновлення. "
            "Запусти повний PolicyOS workflow: ProblemFrame, Fabric data needs, "
            "production_data, фінальний Lex-бандл НПА, Trinity bundle, Foundry/"
            "Scientist оцінку, бюджетні, правові, справедливісні, реалізаційні "
            "та макроекономічні trade-off, критику й ітераційне покращення."
        ),
        "context": {
            "locale": "uk",
            "country": "Ukraine",
            "policy_domain": "wartime_msme_support",
            "run_type": "full_real_policyos_e2e",
            "source_context": {
                "context_id": "EU_COVID_SME_SUPPORT_2020",
                "context_label": "EU/UK COVID-era SME support evidence",
                "countries": ["DE", "PL", "UK"],
                "income_level": "high",
                "publication_year": 2020,
                "time_period": "2020-2021",
                "post_conflict": False,
            },
            "target_context": {
                "context_id": "UA_WARTIME_MSME_2026",
                "context_label": "Ukraine wartime MSME support",
                "countries": ["UA"],
                "income_level": "lower_middle",
                "publication_year": 2026,
                "time_period": "2026",
                "post_conflict": True,
                "post_communist": True,
            },
            "query_treatment": "credit_guarantee",
            "query_outcome": "msme_survival_rate",
            "production_data_root": f"{args.remote_repo}/production_data",
            "lex_bundle_dir": (
                f"{args.remote_repo}/production_data/lex/lex-amendment-only-optimized-20260501-v3"
            ),
            "requirements": [
                "no_mock_fallback",
                "use_real_llm_gateway" if args.mode == "real" else "use_simulated_llm_gateway",
                "use_fabric_retrieval",
                "use_foundry_method_catalog",
                "use_lex_normative_references_when_available",
                "persist_reproducibility_artifacts",
            ],
            "random_seed": 20260508,
        },
        "domain_hint": "Ukraine wartime MSME support policy",
        "max_iterations": args.max_iterations,
        "llm_models": models,
        # Replaced remotely with the resource-derived value when 0.
        "max_parallel_models": args.max_parallel_models,
        "run_budget_usd": 0.5,
        "per_model_budget_usd": 0.5,
        "checkpoint_policy": "strict",
        "execution_profile": "research",
        # Simulation mode swaps the LLM gateway implementation via env without
        # weakening control-plane governance around mock fallback.
        "policy_flags": {"allow_mock_fallback": False},
        "stop_criteria": {
            "approve_if_evaluator_passes": True,
            "max_revision_iterations": args.max_iterations,
            "require_trinity_bundle": True,
            "require_data_snapshot_or_bindings": True,
        },
        "governance_constraints": [
            {
                "constraint_id": "ukraine_legal_feasibility",
                "kind": "legal",
                "severity": "warning",
                "value": {
                    "description": (
                        "Policy must cite or align with available Ukrainian NPA evidence "
                        "when possible."
                    )
                },
            },
            {
                "constraint_id": "wartime_budget_constraint",
                "kind": "budget",
                "severity": "warning",
                "value": {"description": "Prefer targeted, fiscally bounded instruments."},
            },
            {
                "constraint_id": "equity_and_access",
                "kind": "fairness",
                "severity": "warning",
                "value": {
                    "description": (
                        "Assess disparate access and impact for regions, displaced people, "
                        "veterans and women-owned firms."
                    )
                },
            },
        ],
    }


def _remote_script(args: argparse.Namespace, request_json: str) -> str:
    replace_runtime = "1" if args.replace_runtime else "0"
    simulation_mode = "1" if args.mode == "simulated" else "0"
    run_label = f"{args.run_label}-{args.mode}-{_stamp()}"
    gcs_prefix = f"{args.bucket.rstrip('/')}/real_runs/{run_label}"
    return f"""
set -euo pipefail

export REPO={_quote(args.remote_repo)}
export PORT={args.port}
export RUN_LABEL={_quote(run_label)}
export RUN_ROOT="/workspace/policyos_real_runs/${{RUN_LABEL}}"
export GCS_PREFIX={_quote(gcs_prefix)}
export REPLACE_RUNTIME={replace_runtime}
export SIMULATION_MODE={simulation_mode}
export GONKA_PROXY_KEY_FILE={_quote(args.credential_file)}

cd "$REPO"
mkdir -p "$RUN_ROOT"
printf "%s\\n" "$RUN_ROOT" > /workspace/policyos_real_runs/latest_real_run_root.txt
printf "%s\\n" "$GCS_PREFIX" > /workspace/policyos_real_runs/latest_real_run_gcs.txt

CPU_COUNT=$(nproc)
SAFE_CORES=$(( CPU_COUNT - {args.safe_core_reserve} ))
if [ "$SAFE_CORES" -lt 1 ]; then SAFE_CORES=1; fi
RUNNER_PAR={args.runner_max_parallelism}
if [ "$RUNNER_PAR" -le 0 ]; then RUNNER_PAR="$SAFE_CORES"; fi
SWARM_WORKERS={args.swarm_max_workers}
if [ "$SWARM_WORKERS" -le 0 ]; then SWARM_WORKERS="$SAFE_CORES"; fi
SWARM_PAR={args.swarm_max_parallel}
if [ "$SWARM_PAR" -le 0 ]; then SWARM_PAR=$(( SAFE_CORES / 2 )); fi
if [ "$SWARM_PAR" -lt 1 ]; then SWARM_PAR=1; fi

cat > "$RUN_ROOT/launch_request.json" <<'JSON'
{request_json}
JSON

MODEL_COUNT=$(jq '.llm_models | length' "$RUN_ROOT/launch_request.json")
REQ_PAR=$(jq '.max_parallel_models // 0' "$RUN_ROOT/launch_request.json")
if [ "$REQ_PAR" -le 0 ]; then
  REQ_PAR="$MODEL_COUNT"
  if [ "$REQ_PAR" -gt "$SAFE_CORES" ]; then REQ_PAR="$SAFE_CORES"; fi
  if [ "$REQ_PAR" -lt 1 ]; then REQ_PAR=1; fi
  tmp=$(mktemp)
  jq --argjson value "$REQ_PAR" '.max_parallel_models = $value' \\
    "$RUN_ROOT/launch_request.json" > "$tmp"
  mv "$tmp" "$RUN_ROOT/launch_request.json"
fi

cat > "$RUN_ROOT/run_env.sh" <<EOF
set -euo pipefail
cd "$REPO"
set -a
source .env
set +a
export PATH="$HOME/.local/bin:$PATH"
export PYTHONUNBUFFERED=1
export OMP_NUM_THREADS="$SAFE_CORES"
export OPENBLAS_NUM_THREADS="$SAFE_CORES"
export NUMEXPR_NUM_THREADS="$SAFE_CORES"
export DUCKDB_THREADS="$SAFE_CORES"
export JAX_PLATFORM_NAME=cpu
export JAX_PLATFORMS=cpu
export XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=$SAFE_CORES"
export POLISYOS_RUNNER_MAX_PARALLELISM="$RUNNER_PAR"
export POLISYOS_EXECUTION_PROFILE=research
export POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE=1
export POLISYOS_CONTROL_WORKER_BACKEND=embedded
export POLISYOS_CONTROL_STATE_STORE_BACKEND=sqlite
export POLISYOS_CONTROL_SQLITE_PATH=.polisyos/control_plane.sqlite3
export POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY=1
export POLISYOS_RUNTIME_WRITE_RATE_LIMIT=120
export POLISYOS_RUN_CORO_SYNC_TIMEOUT_SECONDS={args.run_timeout_s}
export POLISYOS_NL_PIPELINE_TIMEOUT_SECONDS={args.run_timeout_s}
export POLISYOS_LLM_GATEWAY_BASE_URL="https://proxy.gonka.gg/v1"
export POLISYOS_LLM_GATEWAY_PROVIDER="gonka_proxy"
if [ "$SIMULATION_MODE" = "0" ]; then
  if [ ! -s "$GONKA_PROXY_KEY_FILE" ]; then
    echo "Live-provider credential file $GONKA_PROXY_KEY_FILE is missing or empty." >&2
    exit 2
  fi
  export POLISYOS_LLM_GATEWAY_API_KEY="$(cat "$GONKA_PROXY_KEY_FILE")"
fi
export POLISYOS_LLM_GATEWAY_TIMEOUT_S={args.llm_timeout_s}
export POLISYOS_LLM_GATEWAY_MAX_RETRIES={args.llm_max_retries}
export POLISYOS_LLM_CACHE_MAXSIZE=0
export POLISYOS_LLM_SIMULATION_MODE="$SIMULATION_MODE"
export POLISYOS_SCIENTIST_V2_ENABLED=1
export POLISYOS_SCIENTIST_SHADOW_MODE=0
export POLISYOS_SCIENTIST_WEB_SEARCH_ENABLED=0
export POLISYOS_SCIENTIST_SWARM_ENABLED=1
export POLISYOS_SCIENTIST_SWARM_MAX_WORKERS="$SWARM_WORKERS"
export POLISYOS_SCIENTIST_SWARM_MAX_PARALLEL="$SWARM_PAR"
export POLISYOS_SCIENTIST_REFLEXION_ENABLED=1
export POLISYOS_SCIENTIST_REFLEXION_MAX_ITERS=3
export POLISYOS_SCIENTIST_TOOL_LOOP_MAX_ITERS=4
EOF

cat > "$RUN_ROOT/resource_profile.json" <<EOF
{{"cpu_count":$CPU_COUNT,"safe_cores":$SAFE_CORES,"runner_max_parallelism":$RUNNER_PAR,"swarm_max_workers":$SWARM_WORKERS,"swarm_max_parallel":$SWARM_PAR,"max_parallel_models":$REQ_PAR,"simulation_mode":$SIMULATION_MODE}}
EOF

if [ "$REPLACE_RUNTIME" = "1" ]; then
  pkill -f "uvicorn polisyos.runtime.http.app:create_runtime_api_app.*--port $PORT" 2>/dev/null || true
else
  if ss -ltn "( sport = :$PORT )" | grep -q ":$PORT"; then
    echo "Port $PORT is already in use. Re-run with --replace-runtime or another --port." >&2
    exit 2
  fi
fi

rm -rf .polisyos
mkdir -p .polisyos
nohup bash -lc "source '$RUN_ROOT/run_env.sh'; uv run uvicorn polisyos.runtime.http.app:create_runtime_api_app --factory --host 127.0.0.1 --port '$PORT' --log-level info" > "$RUN_ROOT/runtime_api.log" 2>&1 &
echo $! > "$RUN_ROOT/runtime_api.pid"

for i in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$PORT/health" > "$RUN_ROOT/health.json" 2>>"$RUN_ROOT/runtime_api_startup_wait.log"; then
    break
  fi
  sleep 2
  if [ "$i" = 60 ]; then
    tail -n 120 "$RUN_ROOT/runtime_api.log" >&2 || true
    exit 1
  fi
done

POST_STATUS=000
for attempt in $(seq 1 5); do
  POST_STATUS=$(curl -sS -o "$RUN_ROOT/launch_response.json" -w "%{{http_code}}" \\
    -X POST "http://127.0.0.1:$PORT/api/v1/control/runs/nl" \\
    -H "Content-Type: application/json" \\
    --data-binary "@$RUN_ROOT/launch_request.json" || true)
  POST_STATUS=${{POST_STATUS:-000}}
  if [ "$POST_STATUS" -ge 200 ] && [ "$POST_STATUS" -lt 300 ]; then
    break
  fi
  cp "$RUN_ROOT/launch_response.json" "$RUN_ROOT/launch_response_attempt_${{attempt}}_${{POST_STATUS}}.json" || true
  sleep $(( attempt * 2 ))
done
if [ "$POST_STATUS" -lt 200 ] || [ "$POST_STATUS" -ge 300 ]; then
  echo "Launch POST failed with HTTP $POST_STATUS" >&2
  cat "$RUN_ROOT/launch_response.json" >&2 || true
  exit 1
fi
cat "$RUN_ROOT/launch_response.json" | jq .
JOB_ID=$(jq -r .job_id "$RUN_ROOT/launch_response.json")
echo "$JOB_ID" > "$RUN_ROOT/job_id.txt"

cat > "$RUN_ROOT/monitor_and_sync.sh" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$REPO"
while true; do
  TS=\\$(date -u +%Y%m%dT%H%M%SZ)
  curl -fsS "http://127.0.0.1:$PORT/api/v1/control/jobs/$JOB_ID" > "$RUN_ROOT/job_status_latest.json" || true
  if [ -s "$RUN_ROOT/job_status_latest.json" ]; then
    jq -c . "$RUN_ROOT/job_status_latest.json" >> "$RUN_ROOT/job_status_history.jsonl" || true
    cp "$RUN_ROOT/job_status_latest.json" "$RUN_ROOT/job_status_\\${{TS}}.json" || true
    STATE=\\$(jq -r .state "$RUN_ROOT/job_status_latest.json" 2>/dev/null || echo unknown)
  else
    STATE=unknown
  fi
  du -sh .polisyos "$RUN_ROOT" > "$RUN_ROOT/size_latest.txt" 2>/dev/null || true
  gcloud storage rsync -r "$RUN_ROOT" "$GCS_PREFIX/run_root" >/tmp/policyos_realrun_sync.log 2>&1 || true
  gcloud storage rsync -r .polisyos "$GCS_PREFIX/polisyos_state" >/tmp/policyos_realrun_state_sync.log 2>&1 || true
  if [ "\\${{STATE}}" = completed ] || [ "\\${{STATE}}" = failed ]; then break; fi
  sleep 20
done

RUN_ID=\\$(jq -r '.run_id // empty' "$RUN_ROOT/job_status_latest.json" 2>/dev/null || true)
if [ -n "\\${{RUN_ID}}" ] && [ "\\${{RUN_ID}}" != "null" ]; then
  curl -fsS "http://127.0.0.1:$PORT/api/v1/runs/\\${{RUN_ID}}" \\
    > "$RUN_ROOT/run.json" || true
  curl -fsS "http://127.0.0.1:$PORT/api/v1/runs/\\${{RUN_ID}}/agents" \\
    > "$RUN_ROOT/agents.json" || true
  curl -fsS "http://127.0.0.1:$PORT/api/v1/runs/\\${{RUN_ID}}/timeline" \\
    > "$RUN_ROOT/timeline.json" || true
  curl -fsS "http://127.0.0.1:$PORT/api/v1/runs/\\${{RUN_ID}}/lineage" \\
    > "$RUN_ROOT/lineage.json" || true
fi

python - <<'PY'
import json
import os
from pathlib import Path

from tools.ops_runners.runtime.canary_evidence import assemble_canary_evidence

run_root = Path(os.environ["RUN_ROOT"])

def load_json(name: str):
    path = run_root / name
    if not path.exists() or path.stat().st_size == 0:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None

job = load_json("job_status_latest.json")
progress = job.get("progress") if isinstance(job, dict) else None
details = progress.get("details") if isinstance(progress, dict) else None
provider_preflight = (
    progress.get("provider_preflight")
    if isinstance(progress, dict) and isinstance(progress.get("provider_preflight"), dict)
    else details.get("provider_preflight")
    if isinstance(details, dict) and isinstance(details.get("provider_preflight"), dict)
    else None
)
bundle_dir = assemble_canary_evidence(
    output_root=Path(".polisyos/canary_evidence"),
    canary_kind="staging" if os.environ.get("SIMULATION_MODE") == "1" else "production",
    command_metadata={{
        "runner": "run_policyos_real_e2e_cloud.py",
        "run_label": os.environ.get("RUN_LABEL"),
        "gcs_prefix": os.environ.get("GCS_PREFIX"),
        "simulation_mode": os.environ.get("SIMULATION_MODE"),
    }},
    request_payload=load_json("launch_request.json"),
    job_payload=job,
    run_payload=load_json("run.json"),
    agents_payload=load_json("agents.json"),
    timeline_payload=load_json("timeline.json"),
    lineage_payload=load_json("lineage.json"),
    provider_preflight=provider_preflight,
)
(run_root / "evidence_bundle_path.txt").write_text(str(bundle_dir) + "\\n", encoding="utf-8")
PY

gcloud storage rsync -r "$RUN_ROOT" "$GCS_PREFIX/run_root" >/tmp/policyos_realrun_sync.log 2>&1 || true
gcloud storage rsync -r .polisyos "$GCS_PREFIX/polisyos_state" >/tmp/policyos_realrun_state_sync.log 2>&1 || true
EOF
chmod +x "$RUN_ROOT/monitor_and_sync.sh"
nohup "$RUN_ROOT/monitor_and_sync.sh" > "$RUN_ROOT/monitor_and_sync.log" 2>&1 &
echo $! > "$RUN_ROOT/monitor_and_sync.pid"

printf "RUN_ROOT=%s\\nGCS_PREFIX=%s\\nJOB_ID=%s\\n" "$RUN_ROOT" "$GCS_PREFIX" "$JOB_ID"
""".strip()


def _run(argv: Sequence[str], *, dry_run: bool) -> int:
    print("+ " + shlex.join(list(argv)))
    if dry_run:
        return 0
    return int(subprocess.run(list(argv), check=False).returncode)  # noqa: S603


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.mode == "real" and not args.allow_live_provider:
        payload = {
            "schema_version": "policyos.real_e2e_cloud_launch.v1",
            "status": "blocked",
            "mode": args.mode,
            "failure_envelope": {
                "code": "live_provider_not_enabled",
                "message": "Real cloud E2E runs require --allow-live-provider.",
                "missing": ["--allow-live-provider"],
            },
        }
        if args.json_output:
            _write_json(args.json_output, payload)
        print("Real cloud E2E runs require --allow-live-provider.", file=sys.stderr)
        return 2

    request_json = json.dumps(_request_payload(args), ensure_ascii=False, indent=2)
    script = _remote_script(args, request_json)
    if args.dry_run:
        print("--- remote script ---")
        print(script)
    exit_code = _run(
        [
            args.gcloud_bin,
            "compute",
            "ssh",
            args.instance,
            f"--project={args.project}",
            f"--zone={args.zone}",
            f"--command={script}",
        ],
        dry_run=args.dry_run,
    )
    if args.json_output:
        _write_json(
            args.json_output,
            {
                "schema_version": "policyos.real_e2e_cloud_launch.v1",
                "status": "launched" if exit_code == 0 else "failed",
                "mode": args.mode,
                "exit_code": exit_code,
                "allow_live_provider": bool(args.allow_live_provider),
                "local_credential_env_present": live_provider_credentials_present(),
                "remote_credential_file": args.credential_file,
                "failure_envelope": None
                if exit_code == 0
                else {
                    "code": "real_e2e_cloud_launch_failed",
                    "exit_code": exit_code,
                },
            },
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
