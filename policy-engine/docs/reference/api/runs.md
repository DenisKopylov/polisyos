# Runs API

Related explanation: [Architecture](../../explanation/architecture.md).

Freshness: 2026-04-27
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/runs.py`, `src/polisyos/runtime/http/dependencies.py`, and `schemas/runtime_api_v1.openapi.json`
Validation:

- `uv run pytest -q tests/unit/runtime/http/test_runs_api.py tests/unit/runtime/http/test_timeline_api.py tests/unit/runtime/http/test_runtime_api_authz.py`
- `uv run pytest -q tests/unit/runtime/http/test_lineage_routes.py tests/unit/runtime/http/test_temporal_routes.py`
- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops/runtime/check_runtime_api_contract.py`

The runs surface is the read-only operational view over runtime executions. Every run-specific endpoint enforces tenant access before returning data.

## Endpoint Summary

| Method | Path                                     | Response body                | Notes                                                                  |
| ------ | ---------------------------------------- | ---------------------------- | ---------------------------------------------------------------------- |
| `GET`  | `/api/v1/runs`                           | `RunsListResponse`           | Cursor pagination with `limit`, `cursor`, `status`, `from_ts`, `to_ts` |
| `POST` | `/api/v1/runs/batch`                     | `RunsBatchResponse`          | Bulk read helper for dashboards and operator tools                     |
| `GET`  | `/api/v1/runs/{run_id}`                  | `RunDetailsResponse`         | Full details for a single run                                          |
| `GET`  | `/api/v1/runs/{run_id}/timeline`         | `RunTimelineResponse`        | Timeline events and summary                                            |
| `GET`  | `/api/v1/runs/{run_id}/nodes`            | `RunNodesResponse`           | Node execution records                                                 |
| `GET`  | `/api/v1/runs/{run_id}/lineage`          | `RunLineageResponse`         | Artifact lineage graph                                                 |
| `GET`  | `/api/v1/runs/{run_id}/quantities`       | `RunQuantitiesResponse`      | QuantityValue coverage for decision and telemetry numbers              |
| `GET`  | `/api/v1/runs/{run_id}/fabric-decision-data` | `FabricDecisionDataResponse` | Fabric trust envelope over decision-bearing quantities                 |
| `GET`  | `/api/v1/runs/{run_id}/agents`           | `AgentPipelineResponse`      | Agent attempts, steps, scoring                                         |
| `GET`  | `/api/v1/runs/{run_id}/evidence-context` | `RunEvidenceContextResponse` | Evidence bundle and context resolution                                 |
| `GET`  | `/api/v1/runs/{run_id}/workflow`         | `RunWorkflowResponse`        | Workflow/DAG view                                                      |
| `GET`  | `/api/v1/runs/live`                      | `text/event-stream`          | Route-only, schema-hidden global live stream                           |
| `GET`  | `/api/v1/runs/{run_id}/live`             | `text/event-stream`          | Route-only, schema-hidden per-run live stream                          |

Common status codes for committed endpoints: `200`, `400`, `401`, `403`, `404`, `422`, `500`.

Validation anchors:

- `tests/unit/runtime/http/test_runs_api.py`
- `tests/unit/runtime/http/test_timeline_api.py`
- `tests/unit/runtime/http/test_core_only_runs_api.py`
- `tests/unit/runtime/http/test_runtime_api_authz.py`
- `tests/unit/runtime/http/test_lineage_routes.py`
- `tests/unit/runtime/http/test_temporal_routes.py`
- `tests/unit/runtime/http/test_access_invariants_properties.py`

## `GET /api/v1/runs`

List runs visible to the current tenant scope.

- Query parameters:
  - `limit`: page size, default `50`, max `200`
  - `cursor`: opaque pagination cursor
  - `q`: optional free-text run search
  - `status`: optional status filter
  - `from_ts`: lower bound timestamp
  - `to_ts`: upper bound timestamp
- Response body: `RunsListResponse`
  - `runs`: array of `RunSummary`
  - `page`: `CursorPage`
  - `meta`: `ApiMeta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs?limit=25&status=completed"
```

```bash
http GET :8000/api/v1/runs \
  "Authorization:Bearer $TOKEN" \
  limit==25 status==completed
```

## `POST /api/v1/runs/batch`

Return many `RunDetails` envelopes in one request so clients can avoid N+1 fetch loops.

- Request body: `RunsBatchRequest`
  - `run_ids`: ordered list of run identifiers
- Response body: `RunsBatchResponse`
  - `runs`: ordered list of `RunDetails`
  - `meta`: `ApiMeta`
- Link relations:
  - response emits `rel="collection"` for `/api/v1/runs`

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/runs/batch" \
  -d '{"run_ids":["R_core_api_001","R_core_api_002"]}'
```

```bash
http POST :8000/api/v1/runs/batch \
  "Authorization:Bearer $TOKEN" \
  run_ids:='["R_core_api_001","R_core_api_002"]'
```

## `GET /api/v1/runs/{run_id}`

Return the full `RunDetailsResponse` payload for a single run.

- Path parameters:
  - `run_id`: runtime run identifier
- Response body: `RunDetailsResponse`
  - `run`: `RunDetails`
  - `meta`: `ApiMeta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/runs/{run_id}/timeline`

Inspect the chronological run event stream captured by the runtime timeline builder.

- Response body: `RunTimelineResponse`
  - `timeline`: `RunTimelineView`
  - `meta`: `ApiMeta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/timeline"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/timeline \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/runs/{run_id}/nodes`

Return per-node execution records for the run.

- Response body: `RunNodesResponse`
  - `run_id`
  - `source_kind`
  - `nodes`: array of `RunNodeRecord`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/nodes"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/nodes \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/runs/{run_id}/lineage`

Build an artifact lineage graph rooted at the run's artifacts.

- Query parameters:
  - `root_artifact_id`: optional repeated artifact root filter
  - `max_depth`: optional depth cap, `1..256`
  - `max_nodes`: optional node cap, `1..20000`
- Response body: `RunLineageResponse`
  - `lineage`: `ArtifactLineageView`
  - `run_id`
  - `meta`
- Special error:
  - `400 lineage_roots_missing` when the run has no lineage roots after filtering

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/lineage?max_depth=3&max_nodes=250"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/lineage \
  "Authorization:Bearer $TOKEN" \
  max_depth==3 max_nodes==250
```

## `GET /api/v1/runs/{run_id}/quantities`

Return a class-aware inventory of numeric values discovered in the run.

- Response body: `RunQuantitiesResponse`
  - `quantities`: `QuantityValue[]`
  - `coverage`: traced/untraced and decision/telemetry counts
  - `entries`: field-level coverage rows

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/quantities"
```

## `GET /api/v1/runs/{run_id}/fabric-decision-data`

Return Fabric trust envelopes for decision-bearing quantities. Each item carries
source contract, quality, lineage, access, temporal, replay, and typed gap state.

- Response body: `FabricDecisionDataResponse`
  - `decision_data`: `FabricDecisionData[]`
  - `coverage`: decision-data coverage and naked-decision-value count
  - `temporal_scope`: echoed when a temporal cursor is requested

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/fabric-decision-data?branch=main"
```

## `GET /api/v1/runs/{run_id}/agents`

Return the agent pipeline view for the run, including attempts and step-level traces.

- Response body: `AgentPipelineResponse`
  - `pipeline`: `AgentPipelineView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/agents"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/agents \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/runs/{run_id}/evidence-context`

Return the evidence context assembled for the run.

- Response body: `RunEvidenceContextResponse`
  - `context`: `RunEvidenceContextView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/evidence-context"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/evidence-context \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/runs/{run_id}/workflow`

Return workflow graph metadata suitable for DAG or orchestration UIs.

- Response body: `RunWorkflowResponse`
  - `workflow`: `RunWorkflowView`
  - `meta`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/workflow"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/workflow \
  "Authorization:Bearer $TOKEN"
```

## Live Streams

The runtime also exposes two server-sent event streams from `routes/runs.py`.
Both are current runtime routes, but they are deliberately excluded from the
committed OpenAPI snapshot and generated clients with `include_in_schema=False`.
They are operator affordances, not a versioned SDK contract.

### `GET /api/v1/runs/live`

Global live stream of run status snapshots.

- Response media type: `text/event-stream`
- Response header: `X-SSE-Flow-Control`
- Event type: `snapshot`
- Payload highlights:
  - `status_counts`
  - `runs[]`
  - `page`
  - `generated_at`

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/live"
```

### `GET /api/v1/runs/{run_id}/live`

Per-run live stream with timeline, agent, governance, and decision-validity summaries.

- Response media type: `text/event-stream`
- Response header: `X-SSE-Flow-Control`
- Event type: `snapshot`
- Payload highlights:
  - `status`
  - `timeline_events`
  - `agent_attempts`
  - `governance_issues`
  - `decision_validity_status`
  - `terminal`

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/live"
```
