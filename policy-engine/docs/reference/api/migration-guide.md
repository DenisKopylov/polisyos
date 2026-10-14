# Runtime API Migration Guide

Related reference: [REST API Reference](index.md), [Runtime API Versioning and
Deprecation Policy](versioning.md).

Freshness: 2026-10-14
Owner: `@runtime-owners`
Source of truth: `schemas/runtime_api_v1.openapi.json`, `src/polisyos/runtime/http/{app.py,mutation_policy.py,response_policies.py}`, and the route handlers under `src/polisyos/runtime/http/routes/`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Source inspection only for this documentation update; the contract check and listed test anchors were not run.
Validation:

- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`
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

The committed OpenAPI snapshot is canonical for schema-described generated
client operations. Run live-stream routes are schema-hidden and should
not be treated as generated-client contract surface. This page does not freeze
an operation count; inspect the snapshot for its complete current set and route
owners for route-only operations.

## Optional deployment catalog input

The app factory accepts an optional typed catalog selector for deployments
that need candidate L1 reads from a snapshot root:

```python
from pathlib import Path

from polisyos.runtime.http import create_runtime_api_app
from polisyos.runtime.quality.substrate_registry import CatalogServingSourceSelection

app = create_runtime_api_app(
    catalog_source_selection=CatalogServingSourceSelection(
        snapshot_root=Path("/srv/policyos/catalog-snapshot"),
        catalog_run_profile="prod_full",
    ),
)
```

The selected database must exist at
snapshot_root/datasets/graph/dataset_catalog.duckdb. Its profile must agree
with catalog_run_profile; when the app option is omitted, the repository
default and existing behavior remain in force. A selected path is candidate
input only. It does not establish source provenance, publisher lineage,
profile coverage, freshness/currentness, or publication authority. This is
deployment configuration, not a client request or generated-client migration;
no persisted-data migration is required.

## Required Client Updates

### 1. Treat auth as fail-closed

- `GET /api/v1/auth/me` is no longer a safe way to "discover" a local fixture
  identity in normal runtime mode.

- Test/dev tooling that depends on fixture identities must enable the explicit
  development flag and must not assume production parity.

### 2. Add idempotency keys for write retries

For middleware-supported mutations, use `X-Idempotency-Key` where the route
documents that contract. Natural-language launch has a separate required
`Idempotency-Key` owner contract:

- send a stable key on every `POST /api/v1/control/runs/nl`, for every
  execution profile;
- retry only with the same authenticated principal and exact immutable request
  intent; never reuse a key for changed intent;
- after a lost or ambiguous reply, query
  `GET /api/v1/control/admission-attempts/by-idempotency-key` with the same
  key under the same authentication scope;
- treat a `404` lookup as unresolved, not proof that an attempt or provider
  event is absent.

`X-Idempotency-Key` is not a substitute for `Idempotency-Key` on this route.
The admission-attempt response also includes the shared owner purpose, route scope,
principal digest, normalized request-intent digest, and complete status history.
Clients preserve the key while producer status is unavailable. A refused attempt
can release it only when the provider-preflight producer explicitly reports
`no_call` before completion and the history and aggregate response include the exact typed `producer_no_call_reason` joined to the failure code; an
empty ledger or event list by itself never proves no call. A dev direct-admission
history is valid only with a concrete job and `not_applicable` settlement evidence.
The generic middleware response cache is intentionally skipped for natural-language
launches and run-bound predictive-calibration writes; each route replays only its
shared typed operation owner. Natural-language same-key recovery is served only
after the route validates its required key and immutable intent. Route-owner
requests remain subject to the per-tenant write quota; mutation audit remains active.

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
- add route-specific `Idempotency-Key` to every natural-language launch caller
  and preserve it across same-intent retries; use `X-Idempotency-Key` only on
  middleware-supported routes that document it;

- replace one-by-one read loops with batch endpoints where possible;
- update generated client/OpenAPI review to include deprecation headers and
  cache validators;

- capture request IDs in client logs so support can correlate with audit trails.

## Validation Checklist

Run these before declaring a Runtime API client migration complete:

```bash
PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py
uv run pytest -q tests/unit/runtime/http/test_runtime_api_authz.py \
  tests/unit/core/security/test_auth_middlewares.py \
  tests/unit/core/security/test_router.py
```

Client-facing behavior is also covered by:

- `tests/unit/runtime/http/test_runtime_api_write_path_hardening.py`
- `tests/unit/runtime/http/test_artifact_inspector_api.py`
- `tests/unit/runtime/http/test_runs_api.py`
- `tests/unit/runtime/http/test_api_maturity.py`

### Shared operation identity migration

`runtime_operation_intents` now uses typed scope as part of its primary key, so a route intent is distinct even when its candidate run id matches another route claim. The SQLite migration transaction rebuilds the table when the old primary key still includes `run_id`; PostgreSQL replaces that primary-key constraint in its migration transaction. Both preserve stored claim rows and values. Only recognized `run.predictive_calibration.v1` rows are backfilled from their stored `run_id`, and only recognized `control.nl_pre_admission.v1` rows receive the fixed `control.runs.nl` route scope. Unclassified rows, duplicate identities after rekeying, or malformed scopes abort migration rather than inventing identity. The R3 NL attempt handle continues to derive from owner purpose/route, authenticated tenant/cell/subject, and the hashed idempotency key; its actual candidate `run_id` remains separate provenance, and raw keys are not stored. The event-observation response adds the `no_call` literal for a producer-attested refusal before provider completion. Regenerate OpenAPI and generated clients after source freeze; no generated artifacts are hand-authored in this source proposal.
