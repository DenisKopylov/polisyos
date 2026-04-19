# REST API Reference
Related explanation: [Architecture](../../explanation/architecture.md).

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `schemas/runtime_api_v1.openapi.json`, `src/polisyos/runtime/http/app.py`, and `src/polisyos/runtime/http/routes/*.py`
Validation: `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py`

This reference is based on the committed Runtime API OpenAPI snapshot in
`schemas/runtime_api_v1.openapi.json`, with manual notes only for
schema-hidden operational routes in `src/polisyos/runtime/http/routes/`.

Companion L1 reference pages:

- [Runs API](runs.md)
- [Control Plane API](control.md)
- [Artifact Inspection API](artifacts.md)
- [Runtime Auth and Tenant Model](auth-tenant-model.md)
- [Runtime API Error Semantics](error-semantics.md)
- [Runtime API Versioning and Deprecation Policy](versioning.md)
- [Runtime API Migration Guide](migration-guide.md)
- [CAS and Storage Reference](../operations/cas-storage.md)
- [Configuration Reference](../configuration.md)

## Contract Surface

- Committed OpenAPI snapshot: 53 public `GET`/`POST` operations (`38 GET`,
  `15 POST`).
- Current FastAPI runtime surface: the same 53 schema-public operations, plus
  two schema-hidden server-sent event routes for live run snapshots.
- Route-only operations intentionally excluded from the committed OpenAPI
  snapshot and generated clients:
  - `GET /api/v1/runs/live`
  - `GET /api/v1/runs/{run_id}/live`
- Runtime contract check:
  `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py`
- Contract hardening tests:
  `tests/runtime/http/test_runtime_api_contract_hardening.py`

## D1-L1 Source-Of-Truth Map

This lane maps `docs/CORE_COMMON_RUNTIME_AUDIT_REMEDIATION_PLAN.md` into the
runtime API, operations, security, runbook, and package-boundary surfaces
listed below.

| Source phase | Source of truth | Primary docs | Validation anchor |
|---|---|---|---|
| Phase 0: fail-closed auth, runtime write path, crypto/integrity/redaction, race/cache/lifecycle hotfixes | `src/polisyos/core/security/**`, `src/polisyos/core/artifacts/**`, `src/polisyos/runtime/http/{fail_closed_middleware.py,security.py,dependencies.py,mutation_policy.py}` | This page, [Control](control.md), [Artifacts](artifacts.md), [Security Model](../../explanation/security-model.md), [Security and Compliance](../security-compliance.md) | `uv run pytest -q tests/core/security/test_auth_middlewares.py tests/core/security/test_router.py tests/core/security/test_tenant_context.py tests/runtime/http/test_runtime_api_authz.py tests/runtime/http/test_runtime_api_write_path_hardening.py` |
| Phase 1: error semantics, static analysis, property/mutation/fuzz/integration, observability and auditability | `src/polisyos/runtime/http/{errors.py,services/**}`, `src/polisyos/core/observability/**`, `release/core-runtime-closeout.ledger.toml` | [Runs](runs.md), [Control](control.md), [Artifacts](artifacts.md), [Error Semantics](error-semantics.md), [SLO Error Budget](../operations/slo-error-budget.md), [Observability Topology](../operations/observability-topology.md) | `uv run pytest -q tests/runtime/http/test_runtime_api_contract_hardening.py tests/runtime/http/test_runtime_api_observability.py tests/runtime/http/test_access_invariants_properties.py` |
| Phase 2: storage/serialization/immutability, runtime scalability, DI/config, API maturity | `schemas/runtime_api_v1.openapi.json`, `src/polisyos/common/{serialization.py,timestamps.py}`, `src/polisyos/runtime/http/openapi_contract.py`, generated client surfaces | [Versioning Policy](versioning.md), [Migration Guide](migration-guide.md), package READMEs listed below | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py` |
| Phase 3: ADRs, diagrams, runbooks, security/compliance, CI ratchets | `docs/reference/operations/**`, `docs/runbooks/**`, `docs/explanation/security-model.md`, `release/core-runtime-closeout.ledger.toml`, `tools/devx/workspace/acceptance_audit.py` | ops/security references, runtime runbooks, package READMEs | `uv run polisyos-tools workspace acceptance-audit --summary docs/archive/reports/platform-acceptance.md --json-output docs/archive/reports/platform-acceptance.json` |

## Documentation Impact

| Output cluster | Exact files | Source of truth | Validation |
|---|---|---|---|
| API contract reference | `docs/reference/api/index.md`, `docs/reference/api/runs.md`, `docs/reference/api/control.md`, `docs/reference/api/artifacts.md`, `docs/reference/api/auth-tenant-model.md`, `docs/reference/api/error-semantics.md`, `docs/reference/api/versioning.md`, `docs/reference/api/migration-guide.md` | committed OpenAPI snapshot, route handlers, response models, generated client inputs | `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py` |
| Operations and security reference | `docs/reference/operations/slo-error-budget.md`, `docs/reference/operations/observability-topology.md`, `docs/reference/security-compliance.md`, `docs/explanation/security-model.md` | runtime observability emitters, Prometheus alert/rule config, security middleware, artifact-signing and audit code | `uv run pytest -q tests/runtime/http/test_runtime_api_observability.py tests/core/security/test_auth_middlewares.py tests/runtime/http/test_runtime_api_authz.py` |
| Incident runbooks | `docs/runbooks/runtime-api-outage.md`, `docs/runbooks/idempotency-incident.md`, `docs/runbooks/key-rotation.md`, `docs/runbooks/cas-opa-outage.md`, `docs/runbooks/runtime-graceful-shutdown-and-stuck-worker.md` | alert-to-runbook routing, runtime mutation/idempotency controls, key rotation flows, OPA fail-closed posture, worker lifecycle paths | `uv run polisyos-tools workspace acceptance-audit --summary docs/archive/reports/platform-acceptance.md --json-output docs/archive/reports/platform-acceptance.json` |
| Package boundary READMEs | `src/polisyos/common/README.md`, `src/polisyos/core/README.md`, `src/polisyos/runtime/README.md`, `src/polisyos/runtime/http/README.md` | package facades, module boundaries, release-gate expectations, code ownership | `uv run pytest -q tests/common/test_serialization_properties.py tests/core/artifacts/test_storage_protocol_boundaries.py tests/runtime/http/test_runtime_api_contract_hardening.py` |

## Backlog

| Gap | Priority | Tracking note |
|---|---|---|
| No missing required D1-L1 output pages | - | All required D1-L1 files listed in `docs/DOCUMENTATION_SOTA_PLAN.md` are present and mapped above. Future consolidation into a single operator landing page is a D2 cleanup, not a D1 blocker. |

## Base URL

- Local/default base URL: `http://localhost:8000`
- Versioned API base: `http://localhost:8000/api/v1`

## Authentication

The runtime HTTP layer is tenancy-aware, but the committed OpenAPI snapshot does not currently declare a `securitySchemes` section.

- Production-style deployments are expected to front the API with bearer/JWT auth and inject request claims into `request.state`.
- Runtime routes read resolved identity and access scope from request state, then enforce tenant access on run and artifact resources.
- `GET /api/v1/auth/me` reflects the resolved identity and fails closed when claims are absent or invalid. Fixture identity is allowed only behind an explicit development flag.
- Service-to-service authorization uses SPIFFE peer identity plus JWT-derived user scope when available.
- When OPA authorization is enabled in enforce mode and the sidecar is unreachable or returns an invalid shape, the authz client fails closed and returns deny-by-default.

Validation anchors:

- `tests/core/security/test_auth_middlewares.py`
- `tests/core/security/test_router.py`
- `tests/core/security/test_tenant_context.py`
- `tests/runtime/http/test_runtime_api_authz.py`
- `tests/runtime/http/test_access_invariants_properties.py`

## Common Headers

| Header | Required | Notes |
|--------|----------|-------|
| `Authorization: Bearer <token>` | Deployment-dependent | Recommended for any non-local environment |
| `Content-Type: application/json` | For `POST` bodies | All documented `POST` endpoints accept JSON |
| `Accept: application/json` | Usually | Live run streams use `text/event-stream` |
| `X-Idempotency-Key: <key>` | Supported on side-effecting control `POST` routes | Reuse the same key only for the same logical mutation payload |
| `X-Request-ID: <id>` | Optional | Preserved into `meta.request_id` when supplied |
| `X-API-Version: <major>` | Response | Emitted on all `/api/v1/*` responses |
| `X-API-Compatibility-Window: <window>` | Response | Compatibility/deprecation window for the current path major |
| `Deprecation` / `Sunset` | Response | Present when a surface is deprecated |
| `ETag` / `Last-Modified` / `Cache-Control` | Response | Present on immutable or cache-friendly artifact resources |
| `X-SSE-Flow-Control` | Response | Communicates server-side stream pacing expectations on live endpoints |

## Response Envelope

Most JSON responses wrap business data with `meta: ApiMeta`.

| Field | Type | Meaning |
|-------|------|---------|
| `meta.request_id` | `string` | Correlates logs, API responses, and background jobs |
| `meta.generated_at` | `string` | ISO-8601 timestamp when available |
| `meta.source_kinds` | `string[]` | Optional source-kind hints for mixed run/artifact payloads |

## Errors

Problem responses use media type `application/problem+json` and the `RuntimeApiProblem` schema.

| Field | Required | Meaning |
|-------|----------|---------|
| `title` | Yes | Short error title |
| `detail` | Yes | Human-readable explanation |
| `code` | Yes | Stable machine-friendly error code |
| `status` / `status_code` | No | HTTP status code, when populated |
| `request_id` | No | Request correlation identifier |
| `type` | No | Problem type URI or label |
| `instance` | No | Request-specific instance identifier |

Example:

```json
{
  "title": "Bad Request",
  "detail": "At least one data source must be provided",
  "code": "missing_data_source",
  "status_code": 400,
  "request_id": "req-4a6dcb1a"
}
```

Common status codes across the committed contract:

| Status | Meaning |
|--------|---------|
| `200` | Success |
| `400` | Request shape or semantic validation failed |
| `401` | Missing or invalid authentication |
| `403` | Tenant or capability access denied |
| `404` | Run, artifact, job, or pipeline not found |
| `406` | Requested media type is not supported for this artifact surface |
| `409` | Idempotency key reuse conflicts with a different payload or current in-flight state |
| `429` | Tenant or endpoint rate limit exceeded |
| `422` | Pydantic/body validation failure |
| `503` / `504` | Dependency timeout, circuit-breaker, or degraded runtime guard failure |
| `500` | Internal server error |

## Pagination

`GET /api/v1/runs` uses cursor pagination via `CursorPage`.

| Field | Meaning |
|-------|---------|
| `count` | Number of items in the current page |
| `limit` | Requested page size |
| `cursor` | Cursor used to fetch the page |
| `next_cursor` | Cursor for the next page, when available |
| `total` | Best-effort total run count, when available |

## Endpoint Inventory

### Health And Auth

| Method | Path | Description | Source |
|--------|------|-------------|--------|
| `GET` | `/health` | Basic liveness probe | OpenAPI |
| `GET` | `/ready` | Readiness probe | OpenAPI |
| `GET` | `/api/v1/health` | Versioned runtime API health payload | OpenAPI |
| `GET` | `/api/v1/auth/me` | Resolve current identity and permissions | OpenAPI |

### Runs

Detailed reference: [Runs](runs.md)

| Method | Path | Description | Source |
|--------|------|-------------|--------|
| `GET` | `/api/v1/runs` | List runs with cursor pagination and filters | OpenAPI |
| `POST` | `/api/v1/runs/batch` | Return multiple run details in one request | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}` | Return full run details | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/timeline` | Inspect run timeline events | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/nodes` | Inspect node-level state records | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/lineage` | Build artifact lineage graph for a run | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/agents` | Return agent pipeline attempts and steps | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/evidence-context` | Return evidence context used by the run | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/workflow` | Return workflow view and DAG metadata | OpenAPI |
| `GET` | `/api/v1/runs/live` | Server-sent event stream for global run activity | Route-only, schema-hidden |
| `GET` | `/api/v1/runs/{run_id}/live` | Server-sent event stream for a single run | Route-only, schema-hidden |

### Control Plane

Detailed reference: [Control](control.md)

| Method | Path | Description | Source |
|--------|------|-------------|--------|
| `POST` | `/api/v1/control/runs` | Launch a workflow run | OpenAPI |
| `POST` | `/api/v1/control/runs/nl` | Launch a natural-language run | OpenAPI |
| `POST` | `/api/v1/control/runs/{run_id}/feedback/evaluate` | Evaluate post-deployment feedback for a run | OpenAPI |
| `POST` | `/api/v1/control/runs/{run_id}/reissue` | Queue a human-gated reissue run | OpenAPI |
| `GET` | `/api/v1/control/jobs/{job_id}` | Poll durable job status | OpenAPI |
| `GET` | `/api/v1/control/capabilities` | Describe runtime/control-plane capability manifest | OpenAPI |
| `POST` | `/api/v1/control/data/discover` | Run bounded ExploreLane discovery | OpenAPI |
| `POST` | `/api/v1/control/data/resolve` | Resolve `DataNeed[]` into `FetchPlan[]` | OpenAPI |
| `POST` | `/api/v1/control/data/preview` | Preview a fetch plan with quality gates | OpenAPI |
| `POST` | `/api/v1/control/data/ingest` | Execute connector ingestion | OpenAPI |
| `GET` | `/api/v1/control/data/catalog/search` | Search the local metric catalog | OpenAPI |
| `GET` | `/api/v1/control/data/index/stats` | Return retrieval index statistics | OpenAPI |
| `GET` | `/api/v1/control/data/promotion/candidates` | List promotion candidates | OpenAPI |
| `POST` | `/api/v1/control/data/promotion/{promotion_id}/approve` | Approve a promotion candidate | OpenAPI |
| `POST` | `/api/v1/control/data/promotion/{promotion_id}/reject` | Reject a promotion candidate | OpenAPI |
| `GET` | `/api/v1/control/data/connectors` | List runtime connector inventory | OpenAPI |
| `GET` | `/api/v1/control/data/cache` | Inspect data cache entries | OpenAPI |
| `GET` | `/api/v1/control/data/profiles` | List source profiles | OpenAPI |
| `GET` | `/api/v1/control/data/binding-profiles` | List input binding profiles | OpenAPI |
| `GET` | `/api/v1/control/llm/profiles` | List LLM model profiles | OpenAPI |
| `POST` | `/api/v1/control/lex/trigger` | Start a Lex batch pipeline in background | OpenAPI |
| `GET` | `/api/v1/control/lex/status/{pipeline_id}` | Poll Lex pipeline execution state | OpenAPI |
| `GET` | `/api/v1/control/lex/graph/stats` | Inspect Lex graph index statistics | OpenAPI |
| `POST` | `/api/v1/control/lex/search` | Search Lex graph facts | OpenAPI |
| `GET` | `/api/v1/control/workers` | List active or recent control worker leases | OpenAPI |
| `GET` | `/api/v1/control/outbox` | Inspect durable outbox events | OpenAPI |
| `POST` | `/api/v1/control/decision-validity/events` | Publish a decision invalidation event | OpenAPI |
| `GET` | `/api/v1/control/runs/{run_id}/decision-validity` | Read decision validity summary for a run | OpenAPI |
| `GET` | `/api/v1/control/decision-packets/{decision_packet_ref}/decision-validity` | Read decision validity for a decision packet | OpenAPI |

### Artifacts

Detailed reference: [Artifacts](artifacts.md)

| Method | Path | Description | Source |
|--------|------|-------------|--------|
| `GET` | `/api/v1/artifacts/{artifact_id}` | Return manifest metadata for an artifact | OpenAPI |
| `GET` | `/api/v1/artifacts/{artifact_id}/content` | Return content preview or decoded payload | OpenAPI |
| `POST` | `/api/v1/artifacts/batch` | Return multiple artifact manifests in one request | OpenAPI |
| `GET` | `/api/v1/artifacts/{artifact_id}/download` | Download raw artifact bytes | OpenAPI |
| `GET` | `/api/v1/artifacts/{artifact_id}/lineage` | Build lineage graph rooted at an artifact | OpenAPI |
| `GET` | `/api/v1/artifacts/{artifact_id}/schema` | Return schema metadata for an artifact | OpenAPI |

### Debug

| Method | Path | Description | Source |
|--------|------|-------------|--------|
| `GET` | `/api/v1/debug/runs/{run_id}/nodes/{alias}` | Node-level debug payload for a specific alias | OpenAPI |
| `GET` | `/api/v1/debug/runs/{run_id}/governance` | Governance debug view for a run | OpenAPI |
| `GET` | `/api/v1/debug/runs/{run_id}/errors` | Aggregated run errors | OpenAPI |
| `GET` | `/api/v1/debug/runs/{run_id}/feedback` | Recorded feedback and post-deployment signals | OpenAPI |
| `GET` | `/api/v1/debug/runs/{left_run_id}/compare/{right_run_id}` | Compare two runs | OpenAPI |

## Related Pages

- [Runs](runs.md)
- [Control](control.md)
- [Artifacts](artifacts.md)
- [Versioning Policy](versioning.md)
- [Migration Guide](migration-guide.md)
