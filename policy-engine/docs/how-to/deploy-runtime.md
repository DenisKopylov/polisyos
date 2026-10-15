# Deploy the Runtime

> Understand the current Runtime HTTP app factory, configuration surface,
> dashboard, and production considerations.

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/app.py`, `src/polisyos/runtime/http/routes/`, `src/polisyos/runtime/http/deployment_security.py`, and `pyproject.toml`.
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; source inspection only. No runtime service or deployment was started in this update.

!!! info "Historical local bootstrap receipt — 2026-04-17"
At that time, the recorded checks covered the import
`from polisyos.runtime.http.app import create_runtime_api_app`,
calling `create_runtime_api_app()`,
and route-path presence for
`/api/v1/control/jobs/{job_id}`
and `/api/v1/runs/{run_id}/live`. This is a dated local bootstrap receipt,
not a current service check, production deployment, or end-to-end capability
verification.

## Inputs

- a Python environment with runtime extras;
- a selected execution profile and control-plane state store;
- decisions about the auth/authz, OPA, and observability paths.

## Outputs

- a local development Runtime API at `:8000` if the documented command and its
  environment prerequisites succeed
- a list of key environment variables for execution, security, and telemetry;
- a clear path to the dashboard, control plane, and runtime runs surface.

## Commands

```bash
pip install -e ".[runtime]"
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
uv run polisyos-tools runtime check-runtime-api-contract
```

## 1. Local development

Install runtime dependencies from source:

```bash
pip install -e ".[runtime]"
```

For a minimal HTTP-only path without the observability umbrella:

```bash
pip install -e ".[runtime-http]"
```

If you also need the tutorial/causal pages in the same environment:

```bash
pip install -e ".[all]"
```

Current app factory:

```text
polisyos.runtime.http.app:create_runtime_api_app
```

Local development-server example:

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
```

To serve a local Legal generation with the existing source-owned runtime
material profile, use the module entrypoint and pass the same profile root used
by `embed-local`:

```bash
python -m polisyos.data_forge.domains.legal.batch embed-local \
  --output-dir /path/to/legal-output \
  --runtime-material-profile-root /path/to/legal-runtime-profile
python -m polisyos.runtime.http.profiled_server \
  --runtime-material-profile-root /path/to/legal-runtime-profile
```

The profile root contains `hf-cache/` and `asset-file-manifest.txt`; the owner
rechecks the source-pinned manifest and model members. Keep the same Python
environment, source checkout, working directory, and module invocation context
for both commands. The runtime fingerprint includes the module search path, so
launching the server through an alternate Uvicorn `app_dir` does not preserve
the same profile. Without a profile root the existing app remains profileless
and a vector query is refused. This is a local candidate-serving path; it does
not establish legal authority or production currentness.

Default local URLs:

- `http://localhost:8000`
- Swagger UI: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`

## 2. Configuration

### Environment variables for execution and the control plane

| Variable                                      | Purpose                                                                              |
| --------------------------------------------- | ------------------------------------------------------------------------------------ |
| `POLISYOS_EXECUTION_PROFILE`                  | Selects the runtime deployment profile (`dev`, `research`, `governed`, `production`) |
| `POLISYOS_CONTROL_WORKER_BACKEND`             | Backend for the control-plane worker                                                 |
| `POLISYOS_CONTROL_STATE_STORE_BACKEND`        | Backend for the control-plane state store                                            |
| `POLISYOS_CONTROL_SQLITE_PATH`                | SQLite path for control-plane state                                                  |
| `POLISYOS_CONTROL_POSTGRES_DSN`               | Postgres DSN for control-plane state                                                 |
| `POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE` | Allows a local control plane in research mode                                        |
| `POLISYOS_LLM_GATEWAY_BASE_URL`               | Base URL of the external LLM gateway                                                 |
| `POLISYOS_LLM_GATEWAY_PROVIDER`               | LLM gateway provider identifier                                                      |
| `POLISYOS_CONTROL_MAX_WORKERS`                | `TaskRunner` worker-pool size                                                        |

### Environment variables for security, auth, tenancy, OPA, and attestation

| Variable                                    | Purpose                               |
| ------------------------------------------- | ------------------------------------- |
| `POLISYOS_ENV`                              | Global runtime environment name       |
| `POLISYOS_DB_BACKEND`                       | Selects the database backend          |
| `POLISYOS_MULTI_TENANT_ENABLED`             | Enables cell/tenant routing           |
| `POLISYOS_CELL_REGISTRY_PATH`               | Cell registry path                    |
| `POLISYOS_DEFAULT_CELL_TIER`                | Default cell tier                     |
| `POLISYOS_ALLOWED_REGIONS`                  | Region allowlist                      |
| `POLISYOS_MULTI_TENANT_FAIL_CLOSED`         | Fails closed on tenancy errors        |
| `POLISYOS_AUTHN_ENABLED`                    | Enables authentication                |
| `POLISYOS_AUTHZ_MODE`                       | Authorization mode                    |
| `POLISYOS_EXTERNAL_TENANT_HEADER_FALLBACK`  | Fallback to an external tenant header |
| `POLISYOS_KEYCLOAK_ISSUER_URL`              | Keycloak issuer                       |
| `POLISYOS_KEYCLOAK_JWKS_URI`                | Keycloak JWKS URI                     |
| `POLISYOS_KEYCLOAK_CLIENT_ID`               | Keycloak client id                    |
| `POLISYOS_KEYCLOAK_AUDIENCE`                | JWT audience                          |
| `POLISYOS_JWT_REQUIRED_MFA_ROLES`           | Roles that require MFA                |
| `POLISYOS_OPA_URL`                          | OPA base URL                          |
| `POLISYOS_OPA_POLICY_PATH`                  | OPA policy path                       |
| `POLISYOS_OPA_TIMEOUT`                      | OPA timeout                           |
| `POLISYOS_OPA_CACHE_TTL`                    | OPA cache TTL                         |
| `POLISYOS_OPA_CACHE_SIZE`                   | OPA cache size                        |
| `POLISYOS_MTLS_SPIFFE_HEADER`               | SPIFFE identity header                |
| `POLISYOS_DELEGATION_REQUIRED`              | Requires delegated requests           |
| `POLISYOS_DELEGATION_HEADER`                | Delegation header name                |
| `POLISYOS_DELEGATION_SECRET`                | Delegation signing secret             |
| `POLISYOS_DELEGATION_ALGORITHM`             | Delegation signing algorithm          |
| `POLISYOS_DELEGATION_TTL_SECONDS`           | TTL delegation                        |
| `POLISYOS_TRUSTED_DELEGATORS`               | Trusted delegator list                |
| `POLISYOS_PII_ENABLED`                      | Enables PII controls                  |
| `POLISYOS_TEE_ENABLED`                      | Enables TEE checks                    |
| `POLISYOS_TEE_REQUIRED`                     | Requires TEE attestation              |
| `POLISYOS_TEE_PLATFORM`                     | TEE platform name                     |
| `POLISYOS_TEE_REPORT_PATH`                  | Attestation report path               |
| `POLISYOS_TEE_MAX_REPORT_AGE_SECONDS`       | Maximum report age                    |
| `POLISYOS_TEE_MIN_TCB_VERSION`              | Minimum TCB version                   |
| `POLISYOS_TEE_MIN_GUEST_SVN`                | Minimum guest SVN                     |
| `POLISYOS_TEE_EXPECTED_MEASUREMENTS`        | Expected measurements                 |
| `POLISYOS_TEE_EXPECTED_HOST_DATA`           | Expected host data                    |
| `POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION` | Requires report signature validation  |
| `POLISYOS_TEE_CACHE_TTL_SECONDS`            | TEE cache TTL                         |
| `POLISYOS_TEE_ENFORCE_TIERS`                | Enables tiered TEE policy             |
| `POLISYOS_SBOM_ENABLED`                     | Enables SBOM checks                   |
| `POLISYOS_SBOM_PATH`                        | SBOM path                             |
| `POLISYOS_SBOM_CVSS_THRESHOLD`              | SBOM CVSS threshold                   |
| `POLISYOS_SBOM_GRYPE_DB_PATH`               | Grype DB path                         |
| `POLISYOS_SBOM_ALLOWED_CVES`                | Allowlist CVE                         |

### Environment variables for observability

| Variable                             | Purpose                                  |
| ------------------------------------ | ---------------------------------------- |
| `OTEL_EXPORTER_OTLP_ENDPOINT`        | OTLP collector endpoint                  |
| `OTEL_EXPORTER_OTLP_PROTOCOL`        | OTLP transport protocol                  |
| `OTEL_SERVICE_NAME`                  | Service name                             |
| `POLISYOS_OTEL_ENABLED`              | Enables OpenTelemetry                    |
| `POLISYOS_HPC_OBSERVABILITY_ENABLED` | Enables HPC-specific observability hooks |
| `POLISYOS_OTEL_CONSOLE_EXPORT`       | Enables the console exporter             |
| `POLISYOS_METRICS_PORT`              | Prometheus metrics port                  |
| `POLISYOS_TRACE_SAMPLING_RATIO`      | Trace sampling ratio                     |
| `POLISYOS_ALWAYS_SAMPLE_ERRORS`      | Always samples error paths               |

## 3. Endpoint overview

At the reviewed source pin, the app factory composes its HTTP surface from
these route modules (this is a source map, not a route-count or live-runtime
receipt):

- `routes/health.py`
- `routes/auth.py`
- `routes/runs.py`
- `routes/debug.py`
- `routes/artifacts.py`
- `routes/control.py`
- `routes/review.py`

Representative endpoint groups:

- health:
  - `/health`
  - `/ready`
- runs:
  - `GET /api/v1/runs`
  - `GET /api/v1/runs/{run_id}`
  - `GET /api/v1/runs/{run_id}/timeline`
  - `GET /api/v1/runs/{run_id}/nodes`
  - `GET /api/v1/runs/{run_id}/lineage`
  - `GET /api/v1/runs/{run_id}/workflow`
- control plane:
  - `POST /api/v1/control/runs`
  - `POST /api/v1/control/runs/nl`
  - `POST /api/v1/control/runs/{run_id}/feedback/evaluate`
  - `POST /api/v1/control/runs/{run_id}/reissue`
  - `GET /api/v1/control/jobs/{job_id}`
  - `GET /api/v1/control/workers`
  - `GET /api/v1/control/outbox`
  - several `/api/v1/control/data/...` endpoints

Useful implementation notes:

- the app factory is `create_runtime_api_app(...)`;
- heavy modules are imported lazily enough to keep bootstrap fast;
- runtime security middleware is enabled only when required by the deployment
  profile;
- `ControlPlaneService` uses `TaskRunner`, which uses `ThreadPoolExecutor`;
- the NL endpoint returns the typed refusal `llm_model_unconfigured` when no
  model is specified; mock agents are available only through the non-published
  contract-testing owner.

## 4. Frontend dashboard

Dashboard package:

```text
apps/runtime-dashboard
```

Local startup:

```bash
cd apps/runtime-dashboard
corepack pnpm install --frozen-lockfile
corepack pnpm run dev
```

Default local frontend URL:

```text
http://localhost:5173
```

Current workspace routes:

- `/` -> command center
- `/compose` with alias `/launch` -> scenario composer
- `/runs` -> runs and decisions workspace
- `/evidence` with aliases `/sources` and `/data` -> evidence fabric
- `/knowledge` with alias `/lex` -> Lex knowledge
- `/platform` with alias `/health` -> platform health

## 5. Production considerations

- Use a proper ASGI setup, such as `gunicorn` with `uvicorn` workers.
- If you enable policy-based authorization, run OPA alongside the runtime as a
  sidecar or neighboring service.
- If you enable service identity, use SPIFFE or an equivalent mTLS identity
  layer.
- Terminate TLS at ingress or an upstream proxy.
- For substantial production load, replace the local `TaskRunner` with a
  queue-backed execution backend.

## 6. Monitoring and telemetry

The runtime already imports observability helpers:

- `get_tracer()`
- `get_metrics()`

What the application currently does:

- telemetry middleware records route, method, status, and duration;
- health and readiness routers are connected;
- OpenAPI enrichment is installed through `openapi_contract.py`.

Operational recommendations:

- Connect OTLP to a collector.
- Collect Prometheus metrics if the exporter is enabled.
- Correlate structured logs through `X-Request-ID`.

## Rollback

For a local rollback:

1. Stop `uvicorn`.
2. Remove the scratch state store if you used a local SQLite path such as
   `POLISYOS_CONTROL_SQLITE_PATH`.
3. Clean up temporary CAS/runtime outputs if you experimented in a local
   directory and do not want to retain them as a baseline.

If the change affected the runtime contract surface, also revert the
OpenAPI/client artifacts to their committed versions.

## Troubleshooting

- If `create_runtime_api_app()` cannot be imported, check that `.[runtime]` or
  at least `.[runtime-http]` is installed.
- If a control-plane job remains `pending`, check the state-store backend,
  `POLISYOS_CONTROL_MAX_WORKERS`, and the worker/outbox endpoints in [Use
  Control Plane](use-control-plane.md).
- If auth is enabled and `curl` returns `401/403`, recheck the OIDC/JWT/OPA
  environment variables before debugging business logic.

## 7. Related files

- `src/polisyos/runtime/http/app.py`
- `src/polisyos/runtime/http/execution_policy.py`
- `src/polisyos/runtime/http/routes/runs.py`
- `src/polisyos/runtime/http/routes/control.py`
- `src/polisyos/runtime/http/services/control/__init__.py`
- `src/polisyos/runtime/http/services/control/api.py`
- `src/polisyos/runtime/http/services/control/run_lifecycle.py`
- `src/polisyos/runtime/http/services/task_runner.py`
- `apps/runtime-dashboard/src/app/workspaces.ts`
