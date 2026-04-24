# Configuration Profiles

Related reference: [Configuration](configuration.md), [Environment Matrix](environment-matrix.md), [Security Model](../explanation/security-model.md), [Key Rotation](../key-rotation.md).

Owner: `@runtime-owners`
Source of truth: `docs/reference/configuration.md`, `src/polisyos/common/config.py`, `src/polisyos/core/security/settings.py`, `policy-engine/.env.example`, and `frontend/runtime-dashboard/.env.example`

This page governs environment-variable taxonomy, example profile composition,
and secret handling for PolicyOS.

Canonical sources:

- variable-by-variable reference: [`reference/configuration.md`](configuration.md)
- safe local examples: `policy-engine/.env.example` and `frontend/runtime-dashboard/.env.example`

## Taxonomy

| Category                     | Definition                                                                  | Representative variables                                                                                                       |
| ---------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Public config                | Safe to expose to the browser or public build outputs                       | `VITE_RUNTIME_API_URL`, `VITE_FF_*`, `VITE_SENTRY_RELEASE`                                                                     |
| Sensitive runtime config     | Required by backend/runtime services and must stay secret or tightly scoped | `POLISYOS_CONTROL_POSTGRES_DSN`, `POLISYOS_DELEGATION_SECRET`, `POLISYOS_LLM_GATEWAY_API_KEY`                                  |
| CI-only secrets              | Needed only inside CI or release automation                                 | `SENTRY_AUTH_TOKEN`, `SENTRY_ORG`, `SENTRY_PROJECT`, `POLISYOS_SLSA_OIDC_TOKEN`                                                |
| Local developer-only toggles | Safe, non-production defaults used to shape workstation behavior            | `LOG_LEVEL`, `DUCKDB_THREADS`, `POLISYOS_OTEL_CONSOLE_EXPORT`, `POLICY_ENGINE_ALLOW_JAX_METAL`                                 |
| Deprecated variables         | Compatibility fallbacks that should not be introduced into new setup docs   | `POLICY_ENGINE_ALLOW_JAX_METAL`, `POLISYOS_DATASET_LEGACY_SERIAL`, unprefixed `PUB2TEI_BASE_URL`, unprefixed `GROBID_BASE_URL` |

## Twelve-Factor Rules

- Deploy-varying configuration lives outside code.
- Environment variables are orthogonal controls, not named bundles like `staging-eu-2`.
- Repo-local `.env` files are a local developer convenience layer only.
- Already injected environment variables win over `.env`; production and CI should inject values directly instead of depending on repo files.

## Profile Examples

### Local Dev

Use `policy-engine/.env.example` as the safe baseline for:

- embedded worker backend;
- SQLite control plane;
- filesystem CAS;
- local logging and tracing defaults.

For the dashboard, use `frontend/runtime-dashboard/.env.example` for browser-safe `VITE_*` values only.

### Research / Durable Local Runtime

```bash
export POLISYOS_EXECUTION_PROFILE=research
export POLISYOS_CONTROL_WORKER_BACKEND=external
export POLISYOS_CONTROL_STATE_STORE_BACKEND=postgres
export POLISYOS_CONTROL_POSTGRES_DSN='postgresql://...'
export POLISYOS_LLM_GATEWAY_BASE_URL='https://...'
```

Use shell/session injection or a local secret manager for the DSN and gateway
credentials. Do not commit them to `.env.example` files.

### Governed / Production

```bash
export POLISYOS_EXECUTION_PROFILE=production
export POLISYOS_CONTROL_WORKER_BACKEND=external
export POLISYOS_CONTROL_STATE_STORE_BACKEND=postgres
export POLISYOS_AUTHZ_MODE=enforce
export POLISYOS_SIGNING_ENABLED=true
export POLISYOS_SBOM_ENABLED=true
```

Production-only secrets are injected by the deployment platform, not by
repository files.

## Secret Lifecycle Policy

| Surface                 | Injection path                                                | Storage rule                                                                        | Owner / rotation expectation                                  |
| ----------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------- | ------------------------------------------------------------- |
| Local developer secrets | Shell exports, `direnv`, or a local secret store              | May live in a personal, untracked `.env`, but never in tracked files                | Rotated by the developer or service owner when access changes |
| CI secrets              | GitHub Actions secrets or OIDC-issued short-lived credentials | Prefer platform-managed secrets; avoid duplicating prod secrets into every workflow | Platform owners rotate on workflow or credential changes      |
| Production secrets      | Deployment platform secret store / managed identity           | Never stored in repo files or copied into casual local workflows                    | Service owners rotate per provider policy and after incidents |

Secrets that may never be stored in tracked `.env` files:

- signing private keys and trust bundles (`POLISYOS_SIGNING_KEY`, private PEM files);
- OIDC bearer tokens (`POLISYOS_SLSA_OIDC_TOKEN`);
- long-lived cloud access keys;
- production database DSNs;
- release/upload tokens such as `SENTRY_AUTH_TOKEN`.

## Preferred Credential Strategy

- Prefer short-lived machine credentials such as OIDC-based cloud auth over long-lived CI secrets whenever the target platform supports it.
- Prefer individually scoped secret values over structured JSON/YAML secret blobs so rotation and audit scope stay narrow.
- Use protected deployment environments and required reviewers for production promotions and high-risk deploy secrets.

## Generated Security Artifacts

Generated security artifacts are not casual developer state:

- hidden sourcemaps remain build artifacts and should only be uploaded through CI/release flows;
- signing bundles and trust stores follow [`Key Rotation`](../key-rotation.md);
- SBOMs, audit exports, and similar reports are generated artifacts that belong in controlled artifact storage, not in ad hoc `.env` files.

## Deprecated / Compatibility Variables

| Variable                         | Status                          | Replacement / guidance                                                      |
| -------------------------------- | ------------------------------- | --------------------------------------------------------------------------- |
| `POLICY_ENGINE_ALLOW_JAX_METAL`  | Deprecated compatibility toggle | Prefer the opt-in `apple-metal` extra and explicit JAX platform selection   |
| `POLISYOS_DATASET_LEGACY_SERIAL` | Deprecated migration toggle     | Use the current dataset ingest path and keep the legacy path off by default |
| `PUB2TEI_BASE_URL`               | Deprecated unprefixed alias     | Prefer `POLISYOS_PUB2TEI_BASE_URL`                                          |
| `GROBID_BASE_URL`                | Deprecated unprefixed alias     | Prefer `POLISYOS_GROBID_BASE_URL`                                           |
