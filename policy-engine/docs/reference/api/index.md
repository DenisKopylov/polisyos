# REST API Reference
Related explanation: [Architecture](../../explanation/architecture.md).

This reference is based on the committed Runtime API OpenAPI snapshot in `schemas/runtime_api_v1.openapi.json`, with light manual enrichment from `src/polisyos/runtime/http/routes/` and `src/polisyos/runtime/http/services/`.

## Contract Surface

- Committed OpenAPI snapshot: 50 documented `GET`/`POST` operations.
- Current route surface: 52 `GET`/`POST` handlers across runtime routes.
- Route-only operations not present in the committed snapshot:
  - `GET /api/v1/runs/live`
  - `GET /api/v1/runs/{run_id}/live`

## Base URL

- Local/default base URL: `http://localhost:8000`
- Versioned API base: `http://localhost:8000/api/v1`

## Authentication

The runtime HTTP layer is tenancy-aware, but the committed OpenAPI snapshot does not currently declare a `securitySchemes` section.

- Production-style deployments are expected to front the API with bearer/JWT auth and inject request claims into `request.state`.
- Runtime routes read resolved identity and access scope from request state, then enforce tenant access on run and artifact resources.
- `GET /api/v1/auth/me` reflects the resolved identity. If no claims are present, it falls back to a fixture analyst identity for local/dev use.
- Service-to-service authorization uses SPIFFE peer identity plus JWT-derived user scope when available.
- When OPA authorization is enabled in enforce mode and the sidecar is unreachable or returns an invalid shape, the authz client fails closed and returns deny-by-default.

## Common Headers

| Header | Required | Notes |
|--------|----------|-------|
| `Authorization: Bearer <token>` | Deployment-dependent | Recommended for any non-local environment |
| `Content-Type: application/json` | For `POST` bodies | All documented `POST` endpoints accept JSON |
| `Accept: application/json` | Usually | Live run streams use `text/event-stream` |
| `X-Request-ID: <id>` | Optional | Preserved into `meta.request_id` when supplied |

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
| `422` | Pydantic/body validation failure |
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
| `GET` | `/api/v1/runs/{run_id}` | Return full run details | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/timeline` | Inspect run timeline events | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/nodes` | Inspect node-level state records | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/lineage` | Build artifact lineage graph for a run | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/agents` | Return agent pipeline attempts and steps | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/evidence-context` | Return evidence context used by the run | OpenAPI |
| `GET` | `/api/v1/runs/{run_id}/workflow` | Return workflow view and DAG metadata | OpenAPI |
| `GET` | `/api/v1/runs/live` | Server-sent event stream for global run activity | Route-only |
| `GET` | `/api/v1/runs/{run_id}/live` | Server-sent event stream for a single run | Route-only |

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
