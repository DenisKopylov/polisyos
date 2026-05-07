# Configuration Reference

Related explanation: [Security Model](../explanation/security-model.md).

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `src/polisyos/common/config.py`, `src/polisyos/core/security/settings.py`, `src/polisyos/core/artifacts/backends/config.py`, `src/polisyos/runtime/http/{app.py,execution_policy.py,resilience.py,response_policies.py,mutation_policy.py,routes/runs.py}`
Validation:

- `uv run pytest -q tests/unit/common/test_config_bootstrap.py tests/unit/runtime/http/test_api_maturity.py tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`

This page documents dependency extras, execution/security profiles, and the
`POLISYOS_*` environment variables consumed by WS-7E platform layers.

For the governing docs around install tiers and secret handling, see
[Dependency Platform](dependency-platform.md) and
[Configuration Profiles](configuration-profiles.md).

Related L1 references:

- [Bootstrap Environment Registry](configuration-env-registry.md)
- [Runtime Auth and Tenant Model](api/auth-tenant-model.md)
- [Runtime API Error Semantics](api/error-semantics.md)
- [CAS and Storage Reference](operations/cas-storage.md)
- [Runtime API Versioning and Deprecation Policy](api/versioning.md)

## Installation Groups

```bash
# Minimal contributor
uv sync --frozen --extra lint --extra test

# Docs contributor
uv sync --frozen --extra lint --extra docs

# Runtime contributor
uv sync --frozen --extra lint --extra test --extra runtime

# Full research / causal contributor
uv sync --frozen --extra lint --extra test --extra runtime --extra research

# Full product capability umbrella
pip install -e ".[all]"
```

Selected extras declared in `pyproject.toml`:

| Extra                                                                         | Purpose                                                                          |
| ----------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| `core`                                                                        | Base install alias                                                               |
| `lint`, `docs`, `notebooks`, `mutation`                                       | Contributor-only tooling groups                                                  |
| `runtime`, `research`, `all`                                                  | Curated umbrellas for runtime work, research work, and broad capability coverage |
| `agent-sim`, `apple-metal`                                                    | Opt-in visualization and Apple Metal surfaces                                    |
| `analytics`, `ml`, `bayesian`, `solvers`, `optimization-advanced`             | Foundry/Scientist method stacks                                                  |
| `causal`, `causal-core`, `causal-full`, `causal-discovery`, `causal-symbolic` | Causal backends and discovery                                                    |
| `runtime-http`, `multi-tenant`                                                | FastAPI runtime surface and tenant-aware DB backends                             |
| `security`                                                                    | SPIFFE, Sigstore, SBOM, and PII tooling                                          |
| `observability`                                                               | Prometheus client surface on top of the base OTel stack                          |
| `rag`, `rag-local`, `academic-skg`, `table-extraction`                        | Retrieval/document ingestion helpers                                             |
| `sandbox`, `shapesafe`, `hotreload`                                           | Optional safety/dev tooling                                                      |
| `test`, `dev`                                                                 | Contributor validation and local authoring tooling                               |

## Execution Profiles

Runtime control-plane behavior is derived from `POLISYOS_EXECUTION_PROFILE`
through `RuntimeExecutionPolicyResolver`.

| Profile      | Default worker backend | Default state store | Notes                                                                                 |
| ------------ | ---------------------- | ------------------- | ------------------------------------------------------------------------------------- |
| `dev`        | `embedded`             | `sqlite`            | Allows local execution and mock fallback                                              |
| `research`   | `external`             | `postgres`          | Durable control-plane required unless `POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE=1` |
| `governed`   | `external`             | `postgres`          | Requires security middleware and durable control-plane                                |
| `production` | `external`             | `postgres`          | Requires security middleware and forbids authz shadow mode                            |

## Control Plane Env Vars

| Variable                                      | Default                           | Effect                                                        |
| --------------------------------------------- | --------------------------------- | ------------------------------------------------------------- |
| `POLISYOS_EXECUTION_PROFILE`                  | `dev`                             | Deployment baseline profile                                   |
| `POLISYOS_CONTROL_WORKER_BACKEND`             | profile-dependent                 | `embedded` or `external` worker execution                     |
| `POLISYOS_CONTROL_STATE_STORE_BACKEND`        | profile-dependent                 | `sqlite` or `postgres` job/state backend                      |
| `POLISYOS_CONTROL_SQLITE_PATH`                | `.polisyos/control_plane.sqlite3` | SQLite control-plane DB path                                  |
| `POLISYOS_CONTROL_POSTGRES_DSN`               | empty                             | Required for durable profiles using PostgreSQL                |
| `POLISYOS_RESEARCH_ALLOW_LOCAL_CONTROL_PLANE` | unset                             | Allow embedded/sqlite control-plane in `research` deployments |
| `POLISYOS_LLM_MULTIMODEL_ENABLED`             | `true`                            | Allow multiple NL model variants per launch                   |
| `POLISYOS_REQUIRED_PREFLIGHT_ENABLED`         | `true`                            | Enable required execution-plan preflight gates                |
| `POLISYOS_AUTO_MATERIALIZATION_ENABLED`       | `true`                            | Enable automatic result materialization where supported       |
| `POLISYOS_UNIFIED_DAG_ENABLED`                | `true`                            | Enable unified DAG execution/reporting mode                   |
| `POLISYOS_LLM_GATEWAY_BASE_URL`               | empty                             | Marks the NL gateway as configured in capability manifests    |
| `POLISYOS_LLM_GATEWAY_PROVIDER`               | `gateway`                         | Provider label emitted in capability manifests                |

## LLM Gateway Advanced Env Vars

| Variable                                | Default          | Effect                                                  |
| --------------------------------------- | ---------------- | ------------------------------------------------------- |
| `POLISYOS_LLM_GATEWAY_API_KEY`          | empty            | Backend credential passed to the configured LLM gateway |
| `POLISYOS_LLM_GATEWAY_TIMEOUT_S`        | `60`             | Gateway request timeout in seconds                      |
| `POLISYOS_LLM_GATEWAY_MAX_RETRIES`      | `1`              | Gateway retry budget                                    |
| `POLISYOS_LLM_FALLBACK_URLS`            | empty            | Comma-separated fallback gateway URLs                   |
| `POLISYOS_LLM_CAPTURE_PROMPT`           | empty / disabled | Enable prompt capture in gateway diagnostics            |
| `POLISYOS_LLM_MAX_PROMPT_CAPTURE_CHARS` | `200`            | Cap prompt capture payload length                       |
| `POLISYOS_LLM_CACHE_TTL_S`              | `300`            | Gateway response cache TTL                              |
| `POLISYOS_LLM_CACHE_MAXSIZE`            | `128`            | Gateway response cache size                             |

## CAS And Signing Env Vars

| Variable                            | Default                                 | Effect                                                              |
| ----------------------------------- | --------------------------------------- | ------------------------------------------------------------------- |
| `POLISYOS_CAS_BACKEND`              | `filesystem`                            | Artifact store backend selector                                     |
| `POLISYOS_CAS_ROOT`                 | `.polisyos/cas` for local filesystem    | CAS root directory for filesystem/cache backends                    |
| `POLISYOS_CAS_BUCKET`               | empty                                   | Object bucket for cloud-backed CAS                                  |
| `POLISYOS_CAS_PREFIX`               | `polisyos-cas`                          | Object prefix for cloud-backed CAS                                  |
| `POLISYOS_CAS_REGION`               | `us-east-1`                             | Object storage region                                               |
| `POLISYOS_CAS_LOCAL_CACHE_DIR`      | `.polisyos/cas/_cache` for cached local | Optional local cache directory for cloud-backed stores              |
| `POLISYOS_SIGNING_ENABLED`          | `false`                                 | Enable artifact-signing integration                                 |
| `POLISYOS_SIGN_ON_PUT`              | `false`                                 | Sign new CAS artifacts automatically on write                       |
| `POLISYOS_SIGN_ON_PUT_POLICY`       | `fail`                                  | `fail` raises on signing errors, `warn` keeps the artifact unsigned |
| `POLISYOS_SIGNING_KEY`              | unset                                   | Inline private PEM for signing                                      |
| `POLISYOS_SIGNING_KEY_FILE`         | unset                                   | Path to private PEM for signing                                     |
| `POLISYOS_SIGNING_KEY_ENV`          | `POLISYOS_SIGNING_KEY`                  | Alternate env var name for inline PEM                               |
| `POLISYOS_SIGNING_KEY_FILE_ENV`     | `POLISYOS_SIGNING_KEY_FILE`             | Alternate env var name for key-file path                            |
| `POLISYOS_SIGNING_KEY_DEFAULT_PATH` | `~/.polisyos/keys/polisyos-signing.pem` | Fallback private key path                                           |
| `POLISYOS_SIGN_TRUST_DIR`           | `.polisyos/keys/trusted`                | Directory of trusted public keys                                    |
| `POLISYOS_SIGN_REVOKED_DIR`         | `.polisyos/keys/revoked`                | Directory of revoked public keys                                    |
| `POLISYOS_SIGN_IDENTITIES`          | `.polisyos/keys/identities.json`        | JSON key-id to signer-identity bindings                             |
| `POLISYOS_SIGNING_IDENTITY`         | unset                                   | Default identity hint embedded in new signatures                    |
| `POLISYOS_STRICT_IDENTITY`          | `false`                                 | Treat identity mismatch as verification failure                     |
| `POLISYOS_SIGN_VERIFY_WORKERS`      | `8`                                     | Parallel workers for bulk verification                              |
| `POLISYOS_SIGN_WORKERS`             | `8`                                     | Parallel workers for bulk signing                                   |

## Security Env Vars

| Variable                                   | Default                         | Effect                                                |
| ------------------------------------------ | ------------------------------- | ----------------------------------------------------- |
| `POLISYOS_ENV`                             | `dev`                           | Normalized to `dev`, `prod`, or `airgap`              |
| `POLISYOS_MULTI_TENANT_ENABLED`            | `false`                         | Enable tenant/cell-aware runtime behavior             |
| `POLISYOS_CELL_ID`                         | empty                           | Expected cell binding for JWT middleware              |
| `POLISYOS_CELL_REGISTRY_PATH`              | empty                           | Path to cell/tenant registry JSON                     |
| `POLISYOS_DEFAULT_CELL_TIER`               | `shared`                        | Fallback cell tier                                    |
| `POLISYOS_ALLOWED_REGIONS`                 | empty                           | Region allowlist for cell placement                   |
| `POLISYOS_MULTI_TENANT_FAIL_CLOSED`        | `true`                          | Deny requests when tenant routing metadata is missing |
| `POLISYOS_AUTHN_ENABLED`                   | env-dependent                   | Enable JWT auth middleware                            |
| `POLISYOS_AUTHZ_MODE`                      | `off` in dev, `enforce` in prod | `off`, `shadow`, or `enforce`                         |
| `POLISYOS_EXTERNAL_TENANT_HEADER_FALLBACK` | `true`                          | Allow trusted tenant headers when claims are absent   |
| `POLISYOS_KEYCLOAK_ISSUER_URL`             | empty                           | OIDC issuer for JWT validation                        |
| `POLISYOS_KEYCLOAK_JWKS_URI`               | empty                           | JWKS endpoint for JWT signature verification          |
| `POLISYOS_KEYCLOAK_CLIENT_ID`              | `polisyos-web`                  | Client role namespace used by role mapping            |
| `POLISYOS_KEYCLOAK_AUDIENCE`               | `polisyos-web`                  | Expected JWT audience                                 |
| `POLISYOS_JWT_REQUIRED_MFA_ROLES`          | `admin,analyst`                 | Roles that require MFA claims                         |
| `POLISYOS_SERVICE_SPIFFE_ID`               | unset                           | Env override for local service SPIFFE identity        |
| `POLISYOS_MTLS_SPIFFE_HEADER`              | `l5d-client-id`                 | Header carrying peer SPIFFE identity                  |
| `POLISYOS_OPA_URL`                         | `http://localhost:8181`         | OPA base URL                                          |
| `POLISYOS_OPA_POLICY_PATH`                 | `polisyos/authz/decision`       | OPA data path queried by the authz client             |
| `POLISYOS_OPA_TIMEOUT`                     | `2.0`                           | Authorization query timeout in seconds                |
| `POLISYOS_OPA_CACHE_TTL`                   | `30.0`                          | TTL for authz result cache                            |
| `POLISYOS_OPA_CACHE_SIZE`                  | `1000`                          | Max cached authz decisions                            |
| `POLISYOS_DELEGATION_REQUIRED`             | `false`                         | Require signed delegation context headers             |
| `POLISYOS_DELEGATION_HEADER`               | `x-policyos-context`            | Delegation JWT header name                            |
| `POLISYOS_DELEGATION_SECRET`               | empty                           | HMAC secret for delegation context                    |
| `POLISYOS_DELEGATION_ALGORITHM`            | `HS256`                         | Delegation signing algorithm                          |
| `POLISYOS_DELEGATION_TTL_SECONDS`          | `60`                            | Delegation context TTL                                |
| `POLISYOS_TRUSTED_DELEGATORS`              | empty                           | Allowed delegator SPIFFE IDs                          |
| `POLISYOS_PII_ENABLED`                     | env-dependent                   | Enable PII handling controls                          |

## TEE, SLSA, SBOM, And Observability Env Vars

| Variable                                    | Default                          | Effect                                                            |
| ------------------------------------------- | -------------------------------- | ----------------------------------------------------------------- |
| `POLISYOS_TEE_ENABLED`                      | env-dependent                    | Enable TEE attestation checks                                     |
| `POLISYOS_TEE_REQUIRED`                     | env-dependent                    | Fail closed when attestation is unavailable/invalid               |
| `POLISYOS_TEE_PLATFORM`                     | `sev-snp`                        | Attestation verifier backend                                      |
| `POLISYOS_TEE_REPORT_PATH`                  | empty                            | JSON report path read by the SEV-SNP verifier                     |
| `POLISYOS_TEE_MAX_REPORT_AGE_SECONDS`       | `300`                            | Freshness limit for attestation reports                           |
| `POLISYOS_TEE_MIN_TCB_VERSION`              | `0`                              | Minimum accepted TCB version                                      |
| `POLISYOS_TEE_MIN_GUEST_SVN`                | `0`                              | Minimum accepted guest SVN                                        |
| `POLISYOS_TEE_EXPECTED_MEASUREMENTS`        | empty                            | Comma-separated expected launch measurements                      |
| `POLISYOS_TEE_EXPECTED_HOST_DATA`           | empty                            | Expected host-data payload when matching is required              |
| `POLISYOS_TEE_REQUIRE_SIGNATURE_VALIDATION` | `true`                           | Require provider-validated report signatures                      |
| `POLISYOS_TEE_CACHE_TTL_SECONDS`            | `300`                            | Attestation result cache TTL                                      |
| `POLISYOS_TEE_ENFORCE_TIERS`                | `dedicated`                      | Cell tiers where TEE must be enforced                             |
| `POLISYOS_TEE_ATTESTATION_STATUS`           | empty                            | Optional status emitted into environment manifests                |
| `POLISYOS_TEE_REPORT_HASH`                  | empty                            | Optional report hash emitted into environment manifests           |
| `POLISYOS_TEE_MEASUREMENT`                  | empty                            | Optional measurement emitted into environment manifests           |
| `POLISYOS_TEE_VERIFIED_AT`                  | empty                            | Optional attestation timestamp emitted into environment manifests |
| `POLISYOS_TEE_TCB_VERSION`                  | empty                            | Optional TCB version emitted into environment manifests           |
| `POLISYOS_SLSA_MODE`                        | `off`                            | SLSA signing mode: `off`, `local`, `private`, `public`            |
| `POLISYOS_SLSA_POLICY`                      | `best_effort`                    | `best_effort` or `required`                                       |
| `POLISYOS_SLSA_FULCIO_URL`                  | `https://fulcio.sigstore.dev`    | Fulcio endpoint                                                   |
| `POLISYOS_SLSA_REKOR_URL`                   | `https://rekor.sigstore.dev`     | Rekor endpoint                                                    |
| `POLISYOS_SLSA_OIDC_ISSUER`                 | empty                            | OIDC issuer used by Sigstore flows                                |
| `POLISYOS_SLSA_OIDC_CLIENT_ID`              | `polisyos-scientist`             | OIDC client ID                                                    |
| `POLISYOS_SLSA_OIDC_TOKEN_ENV`              | `POLISYOS_SLSA_OIDC_TOKEN`       | Env var name containing the OIDC token                            |
| `POLISYOS_SLSA_OIDC_TOKEN`                  | unset                            | OIDC token value consumed by the token provider                   |
| `POLISYOS_SLSA_OIDC_SUBJECT`                | `system@local`                   | Local subject fallback                                            |
| `POLISYOS_SLSA_TIMEOUT_SECONDS`             | `30.0`                           | Fulcio/Rekor request timeout                                      |
| `POLISYOS_SLSA_MAX_RETRIES`                 | `2`                              | Max Sigstore retries                                              |
| `POLISYOS_SLSA_LOCAL_TRANSPARENCY_LOG`      | `.polisyos/slsa/rekor.log.jsonl` | Local Rekor fallback log                                          |
| `POLISYOS_SLSA_RETAIN_ED25519`              | `true`                           | Keep local Ed25519 signatures alongside SLSA evidence             |
| `POLISYOS_SBOM_ENABLED`                     | env-dependent                    | Enable SBOM generation and deployment gates                       |
| `POLISYOS_SBOM_PATH`                        | empty                            | Explicit SBOM path override                                       |
| `POLISYOS_SBOM_CVSS_THRESHOLD`              | `7.0`                            | Minimum severity for failing vulnerabilities                      |
| `POLISYOS_SBOM_GRYPE_DB_PATH`               | empty                            | Grype DB path override                                            |
| `POLISYOS_SBOM_ALLOWED_CVES`                | empty                            | Comma-separated CVE allowlist                                     |
| `POLISYOS_AUDIT_CHAIN_ENABLED`              | `0`                              | Enable chained audit sink from run context                        |
| `POLISYOS_AUDIT_HOT_TIER_URL`               | empty                            | HTTP sink for hot-tier audit replication                          |
| `POLISYOS_AUDIT_COLD_TIER_BUCKET`           | empty                            | Object bucket for cold-tier audit archives                        |
| `POLISYOS_AUDIT_COLD_TIER_PREFIX`           | `audit`                          | Cold-tier object prefix                                           |
| `POLISYOS_AUDIT_COLD_TIER_REGION`           | `us-east-1`                      | Cold-tier object storage region                                   |
| `POLISYOS_OTEL_ENABLED`                     | `true`                           | Enable OpenTelemetry wiring                                       |
| `POLISYOS_HPC_OBSERVABILITY_ENABLED`        | `true`                           | Enable CAS/runtime metric + trace instrumentation                 |
| `POLISYOS_OTEL_CONSOLE_EXPORT`              | `false`                          | Export spans to console for local debugging                       |
| `POLISYOS_METRICS_PORT`                     | `9464`                           | Prometheus metrics port                                           |
| `POLISYOS_TRACE_SAMPLING_RATIO`             | `1.0`                            | Base trace sampling ratio                                         |
| `POLISYOS_ALWAYS_SAMPLE_ERRORS`             | `true`                           | Force-sample spans that end in error                              |
| `POLISYOS_DETERMINISM_TIER`                 | unset                            | Reproducibility tier reported by observability helpers            |
| `POLISYOS_LLM_DEFAULT_INPUT_USD`            | built-in default                 | Default per-token LLM input cost fallback                         |
| `POLISYOS_LLM_DEFAULT_OUTPUT_USD`           | built-in default                 | Default per-token LLM output cost fallback                        |

## Runtime HTTP Guard, CSRF, And Versioning Env Vars

| Variable                                                                                    | Default                                              | Effect                                                                                      |
| ------------------------------------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| `POLISYOS_ENABLE_DEV_FIXTURE_IDENTITY`                                                      | `false`                                              | Enable the explicit development fixture identity when the full security chain is disabled   |
| `POLISYOS_CSRF_ENABLED`                                                                     | unset                                                | Explicitly enable CSRF protection for `/api/v1/*` writes                                    |
| `POLISYOS_COOKIE_AUTH_ENABLED`                                                              | unset                                                | Auto-enable CSRF protection when cookie auth is in use and `POLISYOS_CSRF_ENABLED` is unset |
| `POLISYOS_SESSION_COOKIE_NAME`                                                              | `polisyos_session`                                   | Session cookie name used by the CSRF middleware                                             |
| `POLISYOS_CSRF_COOKIE_NAME`                                                                 | `polisyos_csrf`                                      | Double-submit CSRF cookie name                                                              |
| `POLISYOS_CSRF_HEADER_NAME`                                                                 | `X-CSRF-Token`                                       | Header that must match the CSRF cookie                                                      |
| `POLISYOS_RUNTIME_WRITE_RATE_LIMIT`                                                         | `24`                                                 | Per-tenant write budget for `POST /api/v1/control/*`                                        |
| `POLISYOS_RUNTIME_WRITE_RATE_WINDOW_SECONDS`                                                | `60`                                                 | Window for the write budget                                                                 |
| `POLISYOS_RUNTIME_LIVE_RATE_LIMIT`                                                          | `8`                                                  | Per-tenant live-stream connection budget                                                    |
| `POLISYOS_RUNTIME_LIVE_RATE_WINDOW_SECONDS`                                                 | `60`                                                 | Window for live-stream rate limiting                                                        |
| `POLISYOS_RUNTIME_LIVE_CONCURRENCY_LIMIT`                                                   | `4`                                                  | Per-tenant concurrent live-stream cap                                                       |
| `POLISYOS_RUNTIME_LIVE_MIN_INTERVAL_SECONDS`                                                | `1.0`                                                | Minimum SSE poll interval for run live streams                                              |
| `POLISYOS_RUNTIME_LIVE_MAX_INTERVAL_SECONDS`                                                | `5.0`                                                | Maximum SSE poll interval for run live streams                                              |
| `POLISYOS_RUNTIME_LIVE_KEEPALIVE_SECONDS`                                                   | `15.0`                                               | SSE keepalive cadence                                                                       |
| `POLISYOS_RUNTIME_LIVE_MAX_DURATION_SECONDS`                                                | `120`                                                | Max live-stream lifetime before timeout event                                               |
| `POLISYOS_RUNTIME_CAS_TIMEOUT_SECONDS`                                                      | `1.5`                                                | Timeout for guarded blocking CAS operations                                                 |
| `POLISYOS_RUNTIME_CAS_EXECUTOR_MAX_WORKERS`                                                 | `4`                                                  | Executor budget for guarded CAS calls                                                       |
| `POLISYOS_RUNTIME_CAS_BREAKER_{FAILURE_THRESHOLD,TIMEOUT_SECONDS,WINDOW_SECONDS}`           | `3`, `30`, `60`                                      | Circuit-breaker thresholds for CAS dependency failures                                      |
| `POLISYOS_RUNTIME_CONTROL_STORE_TIMEOUT_SECONDS`                                            | `1.5`                                                | Timeout for guarded control-store calls                                                     |
| `POLISYOS_RUNTIME_CONTROL_STORE_EXECUTOR_MAX_WORKERS`                                       | `4`                                                  | Executor budget for guarded control-store calls                                             |
| `POLISYOS_RUNTIME_CONTROL_STORE_BREAKER_{FAILURE_THRESHOLD,TIMEOUT_SECONDS,WINDOW_SECONDS}` | `3`, `30`, `60`                                      | Circuit-breaker thresholds for control-store failures                                       |
| `POLISYOS_RUNTIME_OPA_TIMEOUT_SECONDS`                                                      | `1.5`                                                | Timeout for runtime OPA checks                                                              |
| `POLISYOS_RUNTIME_OPA_BREAKER_{FAILURE_THRESHOLD,TIMEOUT_SECONDS,WINDOW_SECONDS}`           | `3`, `30`, `60`                                      | Circuit-breaker thresholds for runtime OPA failures                                         |
| `POLISYOS_RUNTIME_API_VERSION`                                                              | `1`                                                  | Runtime API major version header value                                                      |
| `POLISYOS_RUNTIME_API_COMPATIBILITY_WINDOW`                                                 | `12 months`                                          | `X-API-Compatibility-Window` header value                                                   |
| `POLISYOS_RUNTIME_API_MIGRATION_GUIDE_URL`                                                  | `https://polisyos.dev/docs/reference/api/versioning` | `Link rel="describedby"` target for versioning docs                                         |
| `POLISYOS_RUNTIME_API_DEPRECATED`                                                           | `false`                                              | Emit `Deprecation: true` on `/api/v1/*` responses                                           |
| `POLISYOS_RUNTIME_API_SUNSET`                                                               | unset                                                | Emit `Sunset` when the surface has a scheduled removal date                                 |

## Common Runtime Env Vars

`polisyos.common.config` is import-side-effect free. Entry points that want
bootstrap defaults must call `apply_process_bootstrap()` explicitly; the
authoritative bootstrap subset is documented in
[Bootstrap Environment Registry](configuration-env-registry.md).

| Variable                                                                                   | Default            | Effect                                                  |
| ------------------------------------------------------------------------------------------ | ------------------ | ------------------------------------------------------- |
| `LOG_LEVEL`                                                                                | `DEBUG`            | Console logging level for `loguru`                      |
| `DUCKDB_MEMORY_LIMIT`                                                                      | `4GB`              | DuckDB memory limit used by platform services           |
| `DUCKDB_THREADS`                                                                           | auto               | DuckDB thread count                                     |
| `JAX_PLATFORM_NAME`                                                                        | `cpu`              | Explicit bootstrap default for JAX backend selection    |
| `JAX_ENABLE_X64`                                                                           | `false`            | Explicit bootstrap default for x64 mode                 |
| `JAX_DISABLE_MOST_OPTIMIZATIONS`                                                           | `true`             | Explicit bootstrap default for safer local JAX posture  |
| `JAX_CHECK_TRACER_LEAKS`                                                                   | `false`            | Explicit bootstrap default for tracer leak checks       |
| `XLA_PYTHON_CLIENT_PREALLOCATE`                                                            | `false` when unset | Bootstrap default for eager device memory preallocation |
| `XLA_FLAGS`                                                                                | auto when unset    | Bootstrap default for CPU intra-op parallelism          |
| `SCIENTIST_TORCH_DEVICE`                                                                   | `cpu`              | Default Scientist Torch device                          |
| `SCIENTIST_TORCH_NUM_THREADS`                                                              | auto               | Torch intra-op thread count                             |
| `SCIENTIST_TORCH_NUM_INTEROP_THREADS`                                                      | `1`                | Torch inter-op thread count                             |
| `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS` | auto               | CPU thread caps for numerical libraries                 |

## Developer Toggles And Compatibility Vars

| Variable                         | Default | Effect                                                               |
| -------------------------------- | ------- | -------------------------------------------------------------------- |
| `POLICY_ENGINE_ALLOW_JAX_METAL`  | unset   | Deprecated compatibility toggle for legacy Metal enablement on macOS |
| `FOUNDRY_HOT_RELOAD`             | unset   | Enable Foundry hot-reload path                                       |
| `FOUNDRY_SHAPE_CHECK`            | unset   | Toggle extra shape-check strictness in Foundry methods               |
| `POLISYOS_DATASET_LEGACY_SERIAL` | unset   | Deprecated dataset ingest compatibility path                         |
| `PUB2TEI_BASE_URL`               | empty   | Deprecated fallback alias for `POLISYOS_PUB2TEI_BASE_URL`            |
| `GROBID_BASE_URL`                | empty   | Deprecated fallback alias for `POLISYOS_GROBID_BASE_URL`             |
