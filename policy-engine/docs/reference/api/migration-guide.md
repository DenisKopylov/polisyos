# Runtime API Migration Guide

Related reference: [REST API Reference](index.md), [Runtime API Versioning and
Deprecation Policy](versioning.md).

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `schemas/runtime_api_v1.openapi.json`, `src/polisyos/runtime/http/{app.py,mutation_policy.py,response_policies.py}`, and the route handlers under `src/polisyos/runtime/http/routes/`
Validation:

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py`
- `uv run pytest -q tests/unit/runtime/http/test_runtime_api_authz.py tests/unit/runtime/http/test_runtime_api_write_path_hardening.py tests/unit/runtime/http/test_artifact_inspector_api.py tests/unit/runtime/http/test_api_maturity.py`

> Use this page when upgrading dashboard, SDK, or operator workflows from older
> runtime behavior to the hardened `/api/v1` contract.

## Current Client Expectations

| Surface                    | Old assumption                                    | Current contract                                                                |
| -------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------- |
| Authentication             | Local/dev could silently receive fixture identity | Missing claims fail closed unless an explicit dev flag enables fixture identity |
| Artifact reads             | JSON preview was the implicit only mode           | Use content negotiation for preview vs raw bytes                                |
| Immutable artifact caching | Clients had to poll blindly                       | Use `ETag`, `Last-Modified`, and `Cache-Control`                                |
| High-fanout dashboards     | Fetch one run or artifact at a time               | Prefer `POST /api/v1/runs/batch` and `POST /api/v1/artifacts/batch`             |
| Write retries              | Client retries could create duplicates            | Reuse `X-Idempotency-Key` on supported mutation routes                          |
| Deprecation visibility     | Docs or release notes only                        | Watch `Deprecation`, `Sunset`, and `Link` headers                               |
| Live streams               | Polling/backpressure policy was implicit          | Respect `X-SSE-Flow-Control` and bounded server budgets                         |

The current committed OpenAPI snapshot contains 53 public `GET`/`POST`
operations. The two run live-stream routes are schema-hidden and should not be
treated as generated-client contract surface.

## Required Client Updates

### 1. Treat auth as fail-closed

- `GET /api/v1/auth/me` is no longer a safe way to "discover" a local fixture
  identity in normal runtime mode.

- Test/dev tooling that depends on fixture identities must enable the explicit
  development flag and must not assume production parity.

### 2. Add idempotency keys for write retries

For supported `POST /api/v1/control/*` endpoints:

- generate one `X-Idempotency-Key` per logical mutation attempt;
- reuse the same key for safe retry of the same payload;
- never reuse a key for a different payload.

### 3. Prefer batch reads

Dashboard and operator clients should migrate from N+1 retrieval loops to:

- `POST /api/v1/runs/batch`
- `POST /api/v1/artifacts/batch`

### 4. Use explicit artifact media negotiation

- default preview workflows should keep requesting JSON;
- raw artifact retrieval should use `GET /api/v1/artifacts/{artifact_id}/download`
  or request an explicit binary media type.

### 5. Honor cache validators

Immutable artifact resources may return `304 Not Modified` when clients present
matching validators. Client caches should preserve and replay:

- `ETag`
- `If-None-Match`
- `Last-Modified`
- `If-Modified-Since`

## Rollout Checklist

- verify bearer/JWT flows against the fail-closed `/auth/me` behavior;
- add `X-Idempotency-Key` to all client-side safe retry loops for supported
  mutations;

- replace one-by-one read loops with batch endpoints where possible;
- update generated client/OpenAPI review to include deprecation headers and
  cache validators;

- capture request IDs in client logs so support can correlate with audit trails.

## Validation Checklist

Run these before declaring a Runtime API client migration complete:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py
uv run pytest -q tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/core/security/test_auth_middlewares.py \
  tests/unit/core/security/test_router.py
```

Client-facing behavior is also covered by:

- `tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`
- `tests/unit/runtime/http/test_artifact_inspector_api.py`
- `tests/unit/runtime/http/test_runs_api.py`
- `tests/unit/runtime/http/test_api_maturity.py`
