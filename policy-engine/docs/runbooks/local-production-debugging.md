# Local Production Debugging Runbook

Owner: `@platform-owners` with `@runtime-owners` (historical routing labels; current on-call/contact not established)
Created: `2026-05-19`
Source of truth: `policy-engine/tools/quality/testing/local_prod_debug_probe.py`, `policy-engine/tools/ops_runners/runtime/run_canary_matrix.py`, `policy-engine/tools/ops_runners/runtime/local_production_canary.py`, `policy-engine/src/polisyos/runtime/http/deployment_security.py`, `policy-engine/CONTRIBUTING.md`, and the operator's isolated local Docker/PostgreSQL and data state.
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on `2026-10-14`.
Scope recorded on `2026-05-19`: local MacBook staging/debug setup for production-like PolicyOS runs.
Evidence paths recorded in the 2026-05-19 note (existence not rechecked): `.polisyos/canary_evidence/local-prod-debug/`, `.polisyos/canary_matrix_runs/local-prod-debug/`, `_build/.tmp/production-quality/`.
Historical rollback actions: stop the local canary or `polisyos-control-pg`; keep or remove the Docker volume according to evidence retention. Current container identity, volume contents, and retention owner have not been checked.

> **Historical record, not a current operations instruction.** This page preserves the `2026-05-19` setup log and command examples. No Docker daemon, container, database, `.env` file, production-data tree, identity provider, OPA service, or provider credential was inspected for this refresh. Do not infer that any named container, port, volume, or path still exists. The Docker, PostgreSQL, canary, provider, and cleanup examples below were not executed or verified for reuse.

The record was written for local production-like debugging, not production promotion. Source presence in the reviewed checkout does not establish runtime or production readiness.

## Revalidation Prerequisites

First pin the source checkout and use the current CLI parser in `policy-engine/tools/quality/testing/local_prod_debug_probe.py`; the relevant command surface is defined by `build_parser()`, `QUICK_CHECKS`, and `POSTGRES_REQUIRED_CHECKS`. In the reviewed source, `quick` includes bootstrap, PostgreSQL lifecycle, stale recovery, production dry-run, PostgreSQL resource, static production-data, and docs-reproduction checks. The PostgreSQL checks require `POLISYOS_CONTROL_POSTGRES_DSN`. The quick set is stateful: PostgreSQL lifecycle/resource checks write probe rows and clean them up unless `--keep-probe-state` is set, so point it only at an isolated, disposable local database, never a shared or production store. The static data check needs `production_data/manifest.json` and usable manifest entries. Provider checks require both `--allow-live-provider` and `POLISYOS_LLM_GATEWAY_API_KEY`; confirm separate approval and budget before any live-provider probe. Check the exact current flags and dependencies at the pinned source and `policy-engine/CONTRIBUTING.md`; none of these checks was run for this documentation refresh.

## 2026-05-19 Local Setup Log (Historical)

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
- The 2026-05-19 note reported that strict `production` bootstrap reached this local blocker:
  `runtime security middlewares and providers`. With `security_chain_available`
  set by a future cloud composition root, the resolver accepts `production`,
  `external`, `postgres`, and a present DSN.
- Tried one simulated workflow smoke and stopped it because local Python CPU
  stayed high. The interrupted local job rows were cleared from the debug DB so
  future runs start from a clean state.

## What The 2026-05-19 Log Reported (Not Revalidated)

- The operator log reported that the runtime connected to a PostgreSQL-backed control-plane store and created its schema.
- It recorded a local canary attempt against the then-present production-data tree and evidence bundle contracts.
- It recorded provider failures as evidence rather than replacing them with deterministic fixtures.

## Limits Of The 2026-05-19 Record

- It is not cloud production and must not be used as promotion evidence by itself.
- It does not satisfy strict `production` profile requirements unless an external worker process and runtime security chain are also deployed.
- It uses the embedded worker in local debug mode so the MacBook can complete a single canary without a separate queue-backed worker service.
- It does not replace the later cloud deployment with real identity, cell registry, OPA/authz, queue-backed workers, managed Postgres, and production secret injection.

## Historical Local Backing-Service Snapshot (2026-05-19)

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

Historical start example; first verify the current Docker context, container identity, port binding, and volume attachment. This command was not executed or checked for reuse:

```bash
docker start polisyos-control-pg
```

Historical read-only status example; no health result is current evidence:

```bash
docker ps --filter name=polisyos-control-pg \
  --format '{{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Historical stop example; confirm the current target and active work before use:

```bash
docker stop polisyos-control-pg
```

Historical destructive cleanup example. Reconfirm the container-to-volume mapping, retained evidence, and current owner approval before considering it:

```bash
docker rm polisyos-control-pg
docker volume rm polisyos-control-pg-data
```

## Historical Local Environment Snapshot (2026-05-19)

The 2026-05-19 note used `policy-engine/.env.prod-local`, an ignored file. Its present existence, contents, permissions, and approved credential source have not been checked. The shell snippet is a historical example only; never copy, print, or commit secret values:

```bash
set -a
source .env >/dev/null 2>&1 || true
source .env.prod-local
set +a
```

The profile below is the one recorded in the 2026-05-19 note; it is not evidence of the current local environment:

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

The 2026-05-19 note expected strict `production` bootstrap to fail locally until
the deployment security document, OPA sidecar, dedicated probe identities,
PostgreSQL store, and an external worker were available. Recheck the resolver in
the pinned source before relying on that historical expectation. Fixture identity
and test-only step-up verifiers were refused outside the development profile in
the noted configuration.

## Historical Runtime Security and Probe Identity Example

The JSON below is a shape/example from the dated note, not a usable trust policy. Its `example` issuer, key IDs, cell registry path, and principal IDs are placeholders. Reuse requires the current deployment-owned issuer, audience, JWKS/key lifecycle, registered cell, OPA policy, and exact least-privilege grants to be verified against the current runtime security contract. Keep access tokens and signing secrets in the authorized secret injector only; no credentials or live identity services were checked here.

The dated note said both local probes composed the runtime from a
deployment-owned security document. Its environment example was:

```bash
export POLISYOS_RUNTIME_SERVICE_PRINCIPAL_GRANTS_PATH="$PWD/.polisyos/local-prod-debug/runtime-security.json"
export POLISYOS_RUNTIME_CANARY_BEARER_TOKEN='<short-lived runtime-canary access token>'
export POLISYOS_RUNTIME_DEBUG_PROBE_BEARER_TOKEN='<short-lived runtime-debug-probe access token>'
```

The 2026-05-19 note described the historical `...GRANTS_PATH` name as retained
for compatibility and treated its JSON example as a public verification/grant
contract. The example is not the current source of truth: validate the active
configuration against `deployment_security.py` and current runtime contracts.

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

The dated example grant list gave the canary `runs.launch` for the launch
mutation and `runs.view` for job/run/timeline/lineage polling. It gave the debug
probe `runs.view` and described a deliberately absent-run request whose HTTP
`404` indicated authorization completed before route lookup. These are reported
semantics of the historical example; validate current authorization behavior
against the pinned runtime implementation before relying on it. The sample
trust values and principal IDs are not deployment inputs.

The 2026-05-19 example expected an external identity provider to issue access
tokens with signed `alg` and `kid` headers and the claims `iss`, `aud`, `sub`,
`exp`, `iat`, `tenant_id`, and `cell_id`. It described Keycloak-style
`realm_access.roles` and `resource_access[polisyos-runtime].roles`, the
`polisyos_viewer` role, MFA inference from `acr` or `amr`, and unique `jti`
correlation. Treat those as claims in the historical note; use the current
deployment-owned trust configuration and source contract when revalidating.

The dated note said high-stakes step-up assertions bound `sub`, `tenant_id`,
`method`, `route`, `permission`, `resource_id`, `resource_digest`,
`resource_kind`, `binding_authority`, `body_sha256`, `step_up_class`,
`scorecard_ref`, and `scorecard_sha256`. It said they required `iss`, `aud`,
`exp`, `iat`, `jti`, `mfa_verified=true`, and a non-empty `assurance`, honored
optional `nbf`, and rejected stale, replayed, non-active-key, or mismatched
request/resource bindings. Recheck those claims against the current source.

The historical note directed that bearer variables remain in the deployment
secret injector and reported that the debug evidence sanitizer recorded their
presence and fingerprint without token bytes. It described the JSON as public
trust metadata whose exact grants affected authority. Verify current sanitizer
and deployment-secret behavior in source before relying on these claims.

## Historical PostgreSQL Store Verification Example

The example initializes/uses the control-plane store and is mutating. Use only an isolated local PostgreSQL instance after confirming the DSN target and disposable-data boundary; source review shows the probe writes diagnostic/job state and cleans those rows unless `--keep-probe-state` is selected. No database was contacted for this refresh.

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

## Historical Validation Order (Source Interface Reviewed 2026-10-14)

The PostgreSQL store check was the first check in the dated procedure. It is not a no-write health check.

The source-defined `quick` probe is a bounded validation bundle, not a read-only
or no-load check: it includes PostgreSQL lifecycle/resource work, stale recovery,
production dry-run, static production-data checks, and docs reproduction. Recheck
the implementation and local DB isolation before reuse:

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

The dated live-provider example requires a current explicit approval for provider
spend, an isolated database, and a current credential injected through the
approved secret path. Its flags and lane must be checked against current source:

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

An empirical note from `2026-05-19`: the full simulated workflow could
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

Historical live-provider lane example. Reuse requires the current explicit
spend approval, isolated database, and approved secret injection described above:

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

The dated note suggested starting locally with `--timeout-s 900` and increasing
it only after a healthy-provider failure envelope justified more wall time. This
was not revalidated as a current timeout recommendation.

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

## Failure Codes Recorded In The Historical Note

- `no_model_variant_completed`: live LLM gateway accepted preflight but failed the actual model call.
- `live_provider_not_enabled`: provider or live-lane checks were requested without both `--allow-live-provider` and `POLISYOS_LLM_GATEWAY_API_KEY`.
- `postgres_dsn_missing`: a Postgres-backed control-plane check was requested before sourcing `.env.prod-local` or passing `--postgres-dsn`.
- `production_data_manifest_missing`: static production-data checks could not find `production_data/manifest.json`.
- `runtime security middlewares and providers`: strict `production` profile was requested without the cloud security chain.
- `POLISYOS_CONTROL_WORKER_BACKEND=external`: strict production/governed profile was requested while using the local embedded worker.
- `pending` job timeout: external worker mode was enabled locally without a worker process leasing jobs.

These are useful local findings. They should be recorded with the evidence path rather than papered over with a broader timeout or a fallback profile.
