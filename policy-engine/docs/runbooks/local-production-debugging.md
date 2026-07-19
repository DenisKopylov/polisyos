# Local Production Debugging Runbook

Owner: `@platform-owners` with `@runtime-owners`
Created: `2026-05-19`
Scope: local MacBook staging/debug setup for production-like PolicyOS runs.
Evidence path: `.polisyos/canary_evidence/local-prod-debug/`, `.polisyos/canary_matrix_runs/local-prod-debug/`, `_build/.tmp/production-quality/`.
Rollback path: stop the local canary, stop `polisyos-control-pg`, and keep or remove the Docker volume depending on whether durable debug state is still needed.

Use this runbook when we need to debug the production-quality runtime path locally before the full cloud deployment exists. This setup is intentionally small: one PostgreSQL container, one canary lane at a time, bounded provider retries, and no dashboard smoke unless explicitly requested.

## 2026-05-19 Local Setup Log

- Started Docker Desktop for the local backing service.
- Created Docker volume `polisyos-control-pg-data`.
- Created container `polisyos-control-pg` from `postgres:16-alpine`.
- Bound Postgres to `127.0.0.1:54329` only.
- Applied container limits: `1` CPU and `512 MB` RAM.
- Created local env file `.env.prod-local`; it is ignored by git.
- Verified `ControlPlaneStore` can connect to the DSN and create the
  PostgreSQL schema.
- Confirmed these tables exist: `control_jobs`, `control_job_events`,
  `control_job_progress`, `control_worker_leases`, `control_outbox_events`,
  `control_diagnostic_events`, and `control_dead_letter_jobs`.
- Confirmed strict `production` bootstrap reaches the expected local blocker:
  `runtime security middlewares and providers`. With `security_chain_available`
  set by a future cloud composition root, the resolver accepts `production`,
  `external`, `postgres`, and a present DSN.
- Tried one simulated workflow smoke and stopped it because local Python CPU
  stayed high. The interrupted local job rows were cleared from the debug DB so
  future runs start from a clean state.

## What This Setup Proves

- The runtime can use a PostgreSQL-backed control-plane state store instead of SQLite.
- Control-plane tables are created by `ControlPlaneStore` against the configured DSN.
- A local canary can exercise the serious research/public-golden path with canonical production data and the same evidence bundle contracts used by production-quality gates.
- Live-provider failures are captured as evidence instead of being hidden by deterministic fixtures.

## What This Setup Does Not Claim

- It is not cloud production and must not be used as promotion evidence by itself.
- It does not satisfy strict `production` profile requirements unless an external worker process and runtime security chain are also deployed.
- It uses the embedded worker in local debug mode so the MacBook can complete a single canary without a separate queue-backed worker service.
- It does not replace the later cloud deployment with real identity, cell registry, OPA/authz, queue-backed workers, managed Postgres, and production secret injection.

## Local Backing Service

The local PostgreSQL service is:

```text
container: polisyos-control-pg
image: postgres:16-alpine
bind: 127.0.0.1:54329 -> 5432
volume: polisyos-control-pg-data
limits: 1 CPU, 512 MB RAM
database: polisyos_control
user: polisyos
```

Start it if it is not already running:

```bash
docker start polisyos-control-pg
```

Check health:

```bash
docker ps --filter name=polisyos-control-pg \
  --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Stop it after local debugging:

```bash
docker stop polisyos-control-pg
```

Remove local durable debug state only when the evidence/debug history is no longer needed:

```bash
docker rm polisyos-control-pg
docker volume rm polisyos-control-pg-data
```

## Local Env

The local env file is `policy-engine/.env.prod-local`. It is ignored by git. Load it after `.env` so the approved live-provider key can remain in the existing local secret source:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a
```

The default local debug profile is:

```text
POLISYOS_EXECUTION_PROFILE=research
POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE=1
POLISYOS_CONTROL_WORKER_BACKEND=embedded
POLISYOS_CONTROL_STATE_STORE_BACKEND=postgres
POLISYOS_CONTROL_POSTGRES_DSN=postgresql://polisyos:...@127.0.0.1:54329/polisyos_control
```

This is deliberate. It keeps the local runner lightweight while still using the real PostgreSQL state store. For strict production-profile bootstrap, change to:

```bash
export POLISYOS_EXECUTION_PROFILE=production
export POLISYOS_CONTROL_WORKER_BACKEND=external
unset POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE
```

Strict production profile is expected to fail locally until the deployment
security document, OPA sidecar, dedicated probe identities, PostgreSQL store,
and an external worker are available. Fixture identity and test-only step-up
verifiers are refused outside the development profile.

## Runtime Security and Probe Identity

Both local probes compose the runtime from one strict deployment-owned security
document. Point the runtime at that document; do not put a bearer token or a
signing secret in it:

```bash
export POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH="$PWD/.polisyos/local-prod-debug/runtime-security.json"
export POLISYOS_RUNTIME_CANARY_BEARER_TOKEN='<short-lived runtime-canary access token>'
export POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN='<short-lived runtime-debug-probe access token>'
```

The historical `...GRANTS_PATH` name is retained for compatibility, but the
referenced JSON is the complete public verification and grant contract:

```json
{
  "identity_verifier": {
    "issuer": "https://idp.example/realms/polisyos",
    "audience": "polisyos-runtime",
    "algorithms": ["RS256"],
    "jwks_uri": "https://idp.example/realms/polisyos/protocol/openid-connect/certs",
    "allowed_key_ids": ["identity-2026-07"],
    "revoked_key_ids": [],
    "keycloak_client_id": "polisyos-runtime",
    "jwks_cache_ttl_seconds": 300,
    "provenance": {
      "source": "deployment_config",
      "reference": "runtime-idp/trust-policy@2026-07"
    }
  },
  "step_up_verifier": {
    "issuer": "https://idp.example/realms/polisyos-step-up",
    "audience": "polisyos-runtime-step-up",
    "algorithms": ["RS256"],
    "jwks_uri": "https://idp.example/realms/polisyos-step-up/protocol/openid-connect/certs",
    "allowed_key_ids": ["step-up-2026-07"],
    "revoked_key_ids": [],
    "maximum_age_seconds": 300,
    "clock_skew_seconds": 30,
    "provenance": {
      "source": "deployment_config",
      "reference": "runtime-idp/step-up-trust-policy@2026-07"
    }
  },
  "cell_registry_path": "/absolute/path/to/runtime-cells.json",
  "opa": {
    "url": "http://127.0.0.1:8181",
    "policy_path": "polisyos/authz/decision",
    "timeout_seconds": 2.0
  },
  "service_principals": [
    {
      "issuer": "https://idp.example/realms/polisyos",
      "audience": "polisyos-runtime",
      "subject": "runtime-canary",
      "tenant_id": "<canary-tenant-uuid>",
      "cell_id": "<registered-cell-uuidv7>",
      "permissions": ["runs.launch", "runs.view"]
    },
    {
      "issuer": "https://idp.example/realms/polisyos",
      "audience": "polisyos-runtime",
      "subject": "runtime-debug-probe",
      "tenant_id": "<debug-tenant-uuid>",
      "cell_id": "<registered-cell-uuidv7>",
      "permissions": ["runs.view"]
    }
  ]
}
```

The canary needs exactly `runs.launch` for the launch mutation and `runs.view`
for job/run/timeline/lineage polling. The debug probe needs exactly `runs.view`
and proves the identity/OPA chain by requesting a deliberately absent run; HTTP
`404` is success for that check because authorization completed before route
lookup. A coarse token role never adds permissions to either configured
principal. A subject named in this document with any issuer, audience, tenant,
or cell mismatch receives an empty grant and is denied.

The external identity provider must issue access tokens with signed `alg` and
`kid` headers and the claims `iss`, `aud`, `sub`, `exp`, `iat`, `tenant_id`, and
`cell_id`; `roles`, `mfa_verified`, and `jti` must also be supplied for normal
runtime identity/audit semantics. Issuer, audience, algorithm, active/revoked
key sets, JWKS endpoint, tenant, and cell must exactly match the document and
cell registry.

High-stakes step-up assertions additionally bind `sub`, `tenant_id`, `method`,
`route`, `permission`, `resource_id`, `resource_digest`, `resource_kind`,
`binding_authority`, `body_sha256`, `step_up_class`, `scorecard_ref`, and
`scorecard_sha256`. They require `iss`, `aud`, `exp`, `iat`, `jti`,
`mfa_verified=true`, and a non-empty `assurance`; optional `nbf` is honored.
Assertions are rejected when stale, replayed, signed by a non-active key, or
different from any request/resource binding.

Keep the two bearer variables in the deployment secret injector only. The
debug evidence sanitizer records presence and a fingerprint, never token bytes.
The JSON document contains public trust metadata and exact grants, but should
still be deployment-managed and reviewed because changing it changes authority.

## Verify PostgreSQL Store

Run this from `policy-engine/`:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a

PYTHONPATH=src:. uv run --extra runtime --extra multi-tenant python - <<'PY'
import os
from pathlib import Path
from polisyos.runtime.http.services.control_plane_store import ControlPlaneStore

ControlPlaneStore(
    backend=os.environ["POLISYOS_CONTROL_STATE_STORE_BACKEND"],
    sqlite_path=Path(".polisyos/local-prod-debug/control_plane.sqlite3"),
    postgres_dsn=os.environ["POLISYOS_CONTROL_POSTGRES_DSN"],
)
print("postgres control-plane schema ready")
PY
```

Expected output:

```text
postgres control-plane schema ready
```

## Low-Load Validation Order

Start with the PostgreSQL store check above. It is the default low-load smoke for
this local setup.

For the normal local prod-debug loop, use the lightweight probe instead of a
full canary matrix. It validates fail-closed bootstrap behavior, the
PostgreSQL-backed control-plane lifecycle, stale lease recovery, strict
production `/health` composition, bounded resource timings, static production
data, and this runbook:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a

uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py \
  --repo-root . \
  --checks quick \
  --output _build/.tmp/production-quality/local_prod_debug_quick.json
```

Run live-provider and evidence-inspection checks only when the operator
explicitly approves provider spend:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a

uv run --extra runtime --extra multi-tenant --extra ml python tools/quality/testing/local_prod_debug_probe.py \
  --repo-root . \
  --checks provider-preflight,live-research-lane,evidence-inspection \
  --allow-live-provider \
  --output _build/.tmp/production-quality/local_prod_debug_live.json
```

An empirical note from `2026-05-19`: the full simulated workflow can still
register the full method catalog and sustain high Python CPU on a MacBook. Do
not use it as the default "cheap" check. Run it only when you intentionally want
workflow evidence and are comfortable stopping it if local CPU stays high.

Optional simulated single-lane smoke:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a

uv run --extra runtime --extra multi-tenant --extra ml python -m tools.ops_runners.runtime.local_production_canary \
  --mode simulated \
  --execution-profile research \
  --canary-kind staging \
  --production-data-root production_data \
  --quality-scenario ukraine_msme_wartime_credit_support \
  --output-root .polisyos/canary_evidence/local-prod-debug/simulated \
  --run-root .polisyos/local_production_canary/local-prod-debug/simulated \
  --max-iterations=1 \
  --provider-timeout-s 20 \
  --timeout-s 180
```

Then run one live-provider lane only when the operator wants to spend provider budget:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a

test -n "${POLISYOS_LLM_GATEWAY_API_KEY:-}" && echo "live provider credential present"

uv run --extra runtime --extra multi-tenant --extra ml python tools/ops_runners/runtime/run_canary_matrix.py \
  --lane-id profile-research__provider-live_gonka_proxy__data-canonical_production__scenario-public_golden__ui-api_only \
  --allow-live-provider \
  --output-root .polisyos/canary_evidence/local-prod-debug/live-research \
  --run-root .polisyos/canary_matrix_runs/local-prod-debug/live-research \
  --json-output _build/.tmp/production-quality/local_prod_debug_live_research_lane.json \
  --timeout-s 900
```

Use `--timeout-s 900` locally first. Increase only if the failure envelope says the provider is healthy but the pipeline legitimately needs more wall time.

## Inspect Results

When a bundle is produced, inspect:

```bash
BUNDLE=<printed evidence bundle path>

uv run python - "$BUNDLE" <<'PY'
import json
import sys
from pathlib import Path

bundle = Path(sys.argv[1])
scorecard = json.loads((bundle / "quality_evidence" / "quality_scorecard.json").read_text())
print("execution_status=", scorecard.get("execution_status"))
print("quality_status=", scorecard.get("quality_status"))
print("approval_state=", scorecard.get("approval_state"))
print("blocking_failures=", len(scorecard.get("blocking_quality_failures") or []))
for failure in scorecard.get("blocking_quality_failures") or []:
    print(f"- {failure.get('code')}: {failure.get('layer')} {failure.get('phase')} -> {failure.get('next_action')}")
PY
```

For matrix runs, inspect:

```bash
uv run python - <<'PY'
import json
from pathlib import Path

path = Path("_build/.tmp/production-quality/local_prod_debug_live_research_lane.json")
payload = json.loads(path.read_text())
print(json.dumps(payload.get("summary"), indent=2, sort_keys=True))
for lane in payload.get("lanes") or []:
    print(lane.get("lane_id"), lane.get("status"), lane.get("scorecard_status"), lane.get("bundle_path"))
    if lane.get("failure_envelope"):
        print(json.dumps(lane["failure_envelope"], indent=2, sort_keys=True))
PY
```

## Expected Local Blockers

- `no_model_variant_completed`: live LLM gateway accepted preflight but failed the actual model call.
- `live_provider_not_enabled`: provider or live-lane checks were requested without both `--allow-live-provider` and `POLISYOS_LLM_GATEWAY_API_KEY`.
- `postgres_dsn_missing`: a Postgres-backed control-plane check was requested before sourcing `.env.prod-local` or passing `--postgres-dsn`.
- `production_data_manifest_missing`: static production-data checks could not find `production_data/manifest.json`.
- `runtime security middlewares and providers`: strict `production` profile was requested without the cloud security chain.
- `POLISYOS_CONTROL_WORKER_BACKEND=external`: strict production/governed profile was requested while using the local embedded worker.
- `pending` job timeout: external worker mode was enabled locally without a worker process leasing jobs.

These are useful local findings. They should be recorded with the evidence path rather than papered over with a broader timeout or a fallback profile.
