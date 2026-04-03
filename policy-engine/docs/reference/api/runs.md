# Runs API
Related explanation: [Architecture](../../explanation/architecture.md).

The runs surface is the read-only operational view over runtime executions. Every run-specific endpoint enforces tenant access before returning data.

## Endpoint Summary

| Method | Path | Response body | Notes |
|--------|------|---------------|-------|
| `GET` | `/api/v1/runs` | `RunsListResponse` | Cursor pagination with `limit`, `cursor`, `status`, `from_ts`, `to_ts` |
| `GET` | `/api/v1/runs/{run_id}` | `RunDetailsResponse` | Full details for a single run |
| `GET` | `/api/v1/runs/{run_id}/timeline` | `RunTimelineResponse` | Timeline events and summary |
| `GET` | `/api/v1/runs/{run_id}/nodes` | `RunNodesResponse` | Node execution records |
| `GET` | `/api/v1/runs/{run_id}/lineage` | `RunLineageResponse` | Artifact lineage graph |
| `GET` | `/api/v1/runs/{run_id}/agents` | `AgentPipelineResponse` | Agent attempts, steps, scoring |
| `GET` | `/api/v1/runs/{run_id}/evidence-context` | `RunEvidenceContextResponse` | Evidence bundle and context resolution |
| `GET` | `/api/v1/runs/{run_id}/workflow` | `RunWorkflowResponse` | Workflow/DAG view |
| `GET` | `/api/v1/runs/live` | `text/event-stream` | Route-only global live stream |
| `GET` | `/api/v1/runs/{run_id}/live` | `text/event-stream` | Route-only per-run live stream |

Common status codes for committed endpoints: `200`, `400`, `401`, `403`, `404`, `422`, `500`.

## `GET /api/v1/runs`

List runs visible to the current tenant scope.

- Query parameters:
  - `limit`: page size, default `50`, max `200`
  - `cursor`: opaque pagination cursor
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

The runtime also exposes two server-sent event streams from `routes/runs.py`. Both are currently excluded from the committed OpenAPI snapshot.

### `GET /api/v1/runs/live`

Global live stream of run status snapshots.

- Response media type: `text/event-stream`
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
