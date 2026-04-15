# Bootstrap Environment Registry

`polisyos.common.config` no longer mutates process state on import.

Bootstrap now happens explicitly through `apply_process_bootstrap()`, which resolves defaults, validates conflicts, and optionally initializes logging sinks.

## Ownership map

- `common`: process-wide runtime posture such as `LOG_LEVEL`, `DUCKDB_*`, `JAX_*`, `XLA_*`
- `runtime`: tenant/cell routing defaults such as `POLISYOS_MULTI_TENANT_ENABLED`, `POLISYOS_CELL_REGISTRY_PATH`, `POLISYOS_DEFAULT_CELL_TIER`
- `security`: JWT key rotation, CSRF cookie-mode posture, signing trust-store
  paths, and authz dependency controls
- `scientist`: Torch and BLAS thread posture such as `SCIENTIST_TORCH_*`, `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS`, `NUMEXPR_NUM_THREADS`

## Validation rules

- `JAX_PLATFORM_NAME` must be present in `JAX_PLATFORMS` when both are set.
- Thread-count settings must stay positive integers.
- `POLISYOS_JWT_REVOKED_KIDS` always overrides keys listed in
  `POLISYOS_JWT_ALLOWED_KIDS`.
- Cookie-authenticated runtime deployments must set `POLISYOS_CSRF_ENABLED=true`
  or `POLISYOS_COOKIE_AUTH_ENABLED=true`; bearer-only deployments can leave CSRF
  off.
- Bootstrap-time conflicts fail fast before logger/environment mutation happens.

## Security and compliance variables

| Variable | Owner | Default | Purpose |
|---|---|---|---|
| `POLISYOS_JWT_ALLOWED_KIDS` | security | empty | Optional allowlist for JWT signing key IDs accepted during rotation |
| `POLISYOS_JWT_REVOKED_KIDS` | security | empty | Denylist for compromised/retired JWT signing key IDs |
| `POLISYOS_JWKS_CACHE_TTL_SECONDS` | security | `300` | JWKS cache lifetime; lower during active rotation if needed |
| `POLISYOS_CSRF_ENABLED` | runtime/security | unset | Enables runtime CSRF middleware explicitly |
| `POLISYOS_COOKIE_AUTH_ENABLED` | runtime/security | unset | Enables CSRF middleware automatically for cookie-auth deployments |
| `POLISYOS_SESSION_COOKIE_NAME` | runtime/security | `polisyos_session` | Session cookie name protected by CSRF middleware |
| `POLISYOS_CSRF_COOKIE_NAME` | runtime/security | `polisyos_csrf` | Double-submit CSRF cookie name |
| `POLISYOS_CSRF_HEADER_NAME` | runtime/security | `X-CSRF-Token` | Header that must match the CSRF cookie |

## Operator note

If a deployment needs custom bootstrap posture, set the environment before the entrypoint calls `apply_process_bootstrap()` rather than relying on module import side effects.
