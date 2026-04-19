# Control Plane API
Related explanation: [Security Model](../../explanation/security-model.md).

Freshness: 2026-04-17
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/control.py`, `src/polisyos/runtime/http/services/control.py`, `src/polisyos/runtime/http/mutation_policy.py`, `src/polisyos/runtime/http/execution_policy.py`, and `schemas/runtime_api_v1.openapi.json`
Validation:
- `uv run pytest -q tests/runtime/http/test_control_api.py tests/runtime/http/test_runtime_api_write_path_hardening.py tests/runtime/http/test_control_hardening.py`
- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/runtime/check_runtime_api_contract.py`

The control plane is the write-capable orchestration surface for launching runs, driving data collection, and operating Lex and decision-validity workflows.

## Execution Model

`ControlPlaneService` bridges HTTP requests to scientist and fabric operations.

- Workflow launches return a `RunLaunchResponse` with `status`, `run_id`, `job_id`, and `effective_execution_profile`.
- Lex triggers return a similar accepted response with `pipeline_id` and `job_id`.
- Durable job state is read through `GET /api/v1/control/jobs/{job_id}`.
- When the resolved worker backend is `embedded`, `ControlWorker` leases jobs from the durable control store and renews heartbeats while processing them.
- `TaskRunner` is the lightweight in-process thread-pool executor intended for local/dev use. It is not the durable production path.

## Write-Path Controls

All `POST /api/v1/control/*` mutations pass through
`MutationProtectionMiddleware` before the route handler.

- Per-tenant write rate limits return `429 rate_limit_exceeded`.
- Reused `X-Idempotency-Key` values replay the original successful response
  only when tenant, method, path, and request hash match.
- Reusing a key for a different payload returns `409 idempotency_key_reused`.
- Concurrent reuse while the first request is still pending returns
  `409 idempotency_request_in_progress`.
- Mutation audit entries are appended to
  `.polisyos/runtime/audit/mutations.jsonl`.
- Control-store and CAS dependency guards return typed `503`/`504` problem
  responses instead of hanging worker threads silently.

Validation anchors:

- `tests/runtime/http/test_runtime_api_write_path_hardening.py`
- `tests/runtime/http/test_control_hardening.py`
- `tests/runtime/http/test_control_plane_store.py`
- `tests/runtime/http/test_control_service_di.py`
- `tests/runtime/http/test_runtime_api_observability.py`

## Endpoint Summary

### Run Launch And Feedback

| Method | Path | Request body | Response body |
|--------|------|--------------|---------------|
| `POST` | `/api/v1/control/runs` | `WorkflowRunRequest` | `RunLaunchResponse` |
| `POST` | `/api/v1/control/runs/nl` | `NaturalLanguageRunRequest` | `RunLaunchResponse` |
| `POST` | `/api/v1/control/runs/{run_id}/feedback/evaluate` | None | `FeedbackActionResponse` |
| `POST` | `/api/v1/control/runs/{run_id}/reissue` | None | `FeedbackActionResponse` |
| `GET` | `/api/v1/control/jobs/{job_id}` | None | `ControlJobResponse` |

### Data Discovery, Resolution, And Ingestion

| Method | Path | Request body | Response body |
|--------|------|--------------|---------------|
| `POST` | `/api/v1/control/data/discover` | `DataDiscoverRequest` | `DataDiscoverResponse` |
| `POST` | `/api/v1/control/data/resolve` | `DataResolveRequest` | `DataResolveResponse` |
| `POST` | `/api/v1/control/data/preview` | `DataPreviewRequest` | `DataPreviewResponse` |
| `POST` | `/api/v1/control/data/ingest` | `IngestRequest` | `IngestResponse` |
| `GET` | `/api/v1/control/data/catalog/search` | None | `DataCatalogSearchResponse` |
| `GET` | `/api/v1/control/data/index/stats` | None | `IndexStatsResponse` |
| `GET` | `/api/v1/control/data/promotion/candidates` | None | `PromotionCandidatesResponse` |
| `POST` | `/api/v1/control/data/promotion/{promotion_id}/approve` | `PromotionDecisionRequest` | `PromotionDecisionResponse` |
| `POST` | `/api/v1/control/data/promotion/{promotion_id}/reject` | `PromotionDecisionRequest` | `PromotionDecisionResponse` |
| `GET` | `/api/v1/control/data/connectors` | None | `ConnectorsListResponse` |
| `GET` | `/api/v1/control/data/cache` | None | `CacheStatusResponse` |
| `GET` | `/api/v1/control/data/profiles` | None | `SourceProfilesListResponse` |
| `GET` | `/api/v1/control/data/binding-profiles` | None | `BindingProfilesListResponse` |
| `GET` | `/api/v1/control/capabilities` | None | `CapabilityManifestResponse` |
| `GET` | `/api/v1/control/llm/profiles` | None | `ModelProfilesListResponse` |

### Lex Operations

| Method | Path | Request body | Response body |
|--------|------|--------------|---------------|
| `POST` | `/api/v1/control/lex/trigger` | `LexTriggerRequest` | `LexTriggerResponse` |
| `GET` | `/api/v1/control/lex/status/{pipeline_id}` | None | `LexPipelineStatusResponse` |
| `GET` | `/api/v1/control/lex/graph/stats` | None | `LexGraphStatsResponse` |
| `POST` | `/api/v1/control/lex/search` | `LexSearchRequest` | `LexSearchResponse` |

### Operational Endpoints

| Method | Path | Request body | Response body |
|--------|------|--------------|---------------|
| `GET` | `/api/v1/control/workers` | None | `ControlWorkersResponse` |
| `GET` | `/api/v1/control/outbox` | None | `ControlOutboxEventsResponse` |
| `POST` | `/api/v1/control/decision-validity/events` | `DecisionValidityEventRequest` | `DecisionValidityEventResponse` |
| `GET` | `/api/v1/control/runs/{run_id}/decision-validity` | None | `DecisionValiditySummaryResponse` |
| `GET` | `/api/v1/control/decision-packets/{decision_packet_ref}/decision-validity` | None | `DecisionValiditySummaryResponse` |

Committed OpenAPI endpoints share the common response codes `200`, `400`,
`401`, `403`, `404`, `422`, and `500`. Hardened write paths may additionally
return `409`, `429`, `503`, or `504` depending on idempotency, rate-limit, and
dependency state.

## Workflow Runs

### `POST /api/v1/control/runs`

Launch a workflow run using bound input artifacts or a data view request.

- Request body: `WorkflowRunRequest`
  - Required: `data_source`
  - Useful optional refs: `trinity_bundle_ref`, `policy_spec_ref`, `model_spec_ref`, `research_intent_ref`, `knowledge_bundle_ref`, `norm_pack_ref`, `calibration_report_ref`
  - Optional execution controls: `execution_profile`, `checkpoint_policy`, `params`, `policy_flags`
- Response body: `RunLaunchResponse`
  - `status`
  - `run_id`
  - `job_id`
  - `effective_execution_profile`
  - `message`
- Special error:
  - `400 missing_data_source` when no `data_snapshot_ref`, `input_bindings_ref`, or `data_view_request_ref` is supplied

```bash
curl -X POST "http://localhost:8000/api/v1/control/runs" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_source": {
      "data_snapshot_ref": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    },
    "execution_profile": "research"
  }'
```

```bash
http POST :8000/api/v1/control/runs \
  "Authorization:Bearer $TOKEN" \
  data_source:='{"data_snapshot_ref":"sha256:1111111111111111111111111111111111111111111111111111111111111111"}' \
  execution_profile=research
```

### `POST /api/v1/control/runs/nl`

Launch an agent-circuit run from a natural-language request.

- Request body: `NaturalLanguageRunRequest`
  - Required: `request`
  - Optional: `context`, `data_source`, `domain_hint`, `execution_profile`, `expected_outputs`, `governance_constraints`, `llm_model`, `llm_models`, `max_iterations`
- Response body: `RunLaunchResponse`

```bash
curl -X POST "http://localhost:8000/api/v1/control/runs/nl" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Estimate the welfare effect of a temporary wage subsidy for urban households.",
    "data_source": {
      "data_snapshot_ref": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
    },
    "execution_profile": "research",
    "max_iterations": 6
  }'
```

```bash
http POST :8000/api/v1/control/runs/nl \
  "Authorization:Bearer $TOKEN" \
  request="Estimate the welfare effect of a temporary wage subsidy for urban households." \
  data_source:='{"data_snapshot_ref":"sha256:1111111111111111111111111111111111111111111111111111111111111111"}' \
  execution_profile=research \
  max_iterations:=6
```

### `POST /api/v1/control/runs/{run_id}/feedback/evaluate`

Run post-deployment monitoring evaluation for an existing run.

- Request body: none
- Response body: `FeedbackActionResponse`
  - `action`
  - `status`
  - optional `monitoring_report_ref`
  - optional `compare_report_ref`
  - optional `reissue_plan_ref`

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/runs/$RUN_ID/feedback/evaluate"
```

```bash
http POST :8000/api/v1/control/runs/$RUN_ID/feedback/evaluate \
  "Authorization:Bearer $TOKEN"
```

### `POST /api/v1/control/runs/{run_id}/reissue`

Queue a human-gated reissue run using the run's reissue plan.

- Request body: none
- Response body: `FeedbackActionResponse`
  - `action="reissue"`
  - `status="accepted"`
  - optional `reissued_run_id`
  - optional monitoring/compare/reissue plan refs

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/runs/$RUN_ID/reissue"
```

```bash
http POST :8000/api/v1/control/runs/$RUN_ID/reissue \
  "Authorization:Bearer $TOKEN"
```

### `GET /api/v1/control/jobs/{job_id}`

Poll durable background job state.

- Response body: `ControlJobResponse`
  - `job_id`
  - `kind`: `workflow_run`, `natural_language_run`, or `lex_pipeline`
  - `state`: `pending`, `running`, `completed`, or `failed`
  - `run_id` or `pipeline_id` where applicable
  - `progress`
  - `submitted_at`, `started_at`, `finished_at`

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
```

```bash
http GET :8000/api/v1/control/jobs/$JOB_ID \
  "Authorization:Bearer $TOKEN"
```

## Data Discovery And Ingestion

### `POST /api/v1/control/data/discover`

Run bounded ExploreLane discovery over connector metadata.

- Request body: `DataDiscoverRequest`
  - Required: `data_needs`
  - Optional budgets: `cost_budget_usd`, `time_budget_ms`
  - Optional fan-out limits: `max_candidates_total`, `max_discovery_calls_per_source`, `max_sources_per_query`
- Response body: `DataDiscoverResponse`
  - `candidates`
  - `docs_fetched_total`
  - `index_stats`
  - `warnings`

```bash
curl -X POST "http://localhost:8000/api/v1/control/data/discover" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data_needs": [
      {
        "metric": "unemployment_rate",
        "granularity": "monthly",
        "purpose": "policy_baseline"
      }
    ],
    "max_candidates_total": 10,
    "time_budget_ms": 5000
  }'
```

```bash
http POST :8000/api/v1/control/data/discover \
  "Authorization:Bearer $TOKEN" \
  data_needs:='[{"metric":"unemployment_rate","granularity":"monthly","purpose":"policy_baseline"}]' \
  max_candidates_total:=10 \
  time_budget_ms:=5000
```

### `POST /api/v1/control/data/resolve`

Resolve `DataNeed[]` into concrete `FetchPlan[]`.

- Request body: `DataResolveRequest`
  - Required: `data_needs`
  - Optional: `mode` (`fastlane`, `explorelane`, `hybrid`), `allow_explore_fallback`
- Response body: `DataResolveResponse`
  - `mode`
  - `candidates`
  - `fetch_plans`
  - `warnings`

```bash
curl -X POST "http://localhost:8000/api/v1/control/data/resolve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "hybrid",
    "allow_explore_fallback": true,
    "data_needs": [
      {
        "metric": "unemployment_rate",
        "granularity": "monthly"
      }
    ]
  }'
```

```bash
http POST :8000/api/v1/control/data/resolve \
  "Authorization:Bearer $TOKEN" \
  mode=hybrid \
  allow_explore_fallback:=true \
  data_needs:='[{"metric":"unemployment_rate","granularity":"monthly"}]'
```

### `POST /api/v1/control/data/preview`

Preview a single fetch plan through the quality gate.

- Request body: `DataPreviewRequest`
  - Required: `fetch_plan`
  - Optional: `allow_fallback`
- Response body: `DataPreviewResponse`
  - `preview`: `FetchPreview`

```bash
curl -X POST "http://localhost:8000/api/v1/control/data/preview" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "allow_fallback": true,
    "fetch_plan": {
      "plan_id": "plan-unemployment-monthly",
      "metric_id": "unemployment_rate",
      "connector_id": "world_bank",
      "dataset_id": "SL.UEM.TOTL.ZS",
      "max_preview_rows": 50
    }
  }'
```

```bash
http POST :8000/api/v1/control/data/preview \
  "Authorization:Bearer $TOKEN" \
  allow_fallback:=true \
  fetch_plan:='{"plan_id":"plan-unemployment-monthly","metric_id":"unemployment_rate","connector_id":"world_bank","dataset_id":"SL.UEM.TOTL.ZS","max_preview_rows":50}'
```

### `POST /api/v1/control/data/ingest`

Execute connector ingestion and optionally emit a data snapshot and input bindings.

- Request body: `IngestRequest`
  - Optional connector batch: `datasets[]`
  - Optional resolved plans: `fetch_plans[]`
  - Optional controls: `execution_mode`, `cache_policy`, `binding_profile_id`, `produce_data_snapshot`, `produce_input_bindings`
- Response body: `IngestResponse`
  - `status`
  - `message`
  - optional `data_snapshot_ref`
  - optional `input_bindings_ref`
  - optional `evidence_bundle_ref`
  - optional `warnings[]`

```bash
curl -X POST "http://localhost:8000/api/v1/control/data/ingest" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "source": "world_bank",
    "datasets": [
      {
        "connector_id": "world_bank",
        "dataset_id": "SL.UEM.TOTL.ZS"
      }
    ],
    "produce_data_snapshot": true,
    "produce_input_bindings": true
  }'
```

```bash
http POST :8000/api/v1/control/data/ingest \
  "Authorization:Bearer $TOKEN" \
  source=world_bank \
  datasets:='[{"connector_id":"world_bank","dataset_id":"SL.UEM.TOTL.ZS"}]' \
  produce_data_snapshot:=true \
  produce_input_bindings:=true
```

## Catalog, Promotion, And Capability Surfaces

### Search And Inspection Endpoints

| Method | Path | Key query parameters | Response body |
|--------|------|----------------------|---------------|
| `GET` | `/api/v1/control/data/catalog/search` | `metric` required, `geo`, `limit` | `DataCatalogSearchResponse` |
| `GET` | `/api/v1/control/data/index/stats` | None | `IndexStatsResponse` |
| `GET` | `/api/v1/control/data/connectors` | None | `ConnectorsListResponse` |
| `GET` | `/api/v1/control/data/cache` | None | `CacheStatusResponse` |
| `GET` | `/api/v1/control/data/profiles` | None | `SourceProfilesListResponse` |
| `GET` | `/api/v1/control/data/binding-profiles` | None | `BindingProfilesListResponse` |
| `GET` | `/api/v1/control/capabilities` | None | `CapabilityManifestResponse` |
| `GET` | `/api/v1/control/llm/profiles` | None | `ModelProfilesListResponse` |

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/catalog/search?metric=unemployment_rate&geo=UA&limit=10"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/index/stats"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/connectors"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/cache"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/profiles"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/binding-profiles"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/capabilities"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/llm/profiles"
```

```bash
http GET :8000/api/v1/control/data/catalog/search \
  "Authorization:Bearer $TOKEN" \
  metric==unemployment_rate geo==UA limit==10

http GET :8000/api/v1/control/data/index/stats "Authorization:Bearer $TOKEN"
http GET :8000/api/v1/control/data/connectors "Authorization:Bearer $TOKEN"
http GET :8000/api/v1/control/data/cache "Authorization:Bearer $TOKEN"
http GET :8000/api/v1/control/data/profiles "Authorization:Bearer $TOKEN"
http GET :8000/api/v1/control/data/binding-profiles "Authorization:Bearer $TOKEN"
http GET :8000/api/v1/control/capabilities "Authorization:Bearer $TOKEN"
http GET :8000/api/v1/control/llm/profiles "Authorization:Bearer $TOKEN"
```

### Promotion Endpoints

| Method | Path | Request body | Response body |
|--------|------|--------------|---------------|
| `GET` | `/api/v1/control/data/promotion/candidates` | None | `PromotionCandidatesResponse` |
| `POST` | `/api/v1/control/data/promotion/{promotion_id}/approve` | `PromotionDecisionRequest` | `PromotionDecisionResponse` |
| `POST` | `/api/v1/control/data/promotion/{promotion_id}/reject` | `PromotionDecisionRequest` | `PromotionDecisionResponse` |

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/data/promotion/candidates"

curl -X POST "http://localhost:8000/api/v1/control/data/promotion/$PROMOTION_ID/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Validated by data governance review."}'

curl -X POST "http://localhost:8000/api/v1/control/data/promotion/$PROMOTION_ID/reject" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"Coverage below required threshold."}'
```

```bash
http GET :8000/api/v1/control/data/promotion/candidates \
  "Authorization:Bearer $TOKEN"

http POST :8000/api/v1/control/data/promotion/$PROMOTION_ID/approve \
  "Authorization:Bearer $TOKEN" \
  reason="Validated by data governance review."

http POST :8000/api/v1/control/data/promotion/$PROMOTION_ID/reject \
  "Authorization:Bearer $TOKEN" \
  reason="Coverage below required threshold."
```

## Lex Control Endpoints

### `POST /api/v1/control/lex/trigger`

Start a Lex batch pipeline and return a durable job handle.

- Request body: `LexTriggerRequest`
  - Required: `cards_path`, `texts_path`, `output_dir`
  - Optional: `execution_profile`, `llm_model`, `resume`, `stages`, `status_filter`, `policy_flags`
- Response body: `LexTriggerResponse`
  - `pipeline_id`
  - `job_id`
  - `status`
  - `effective_execution_profile`

```bash
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cards_path": "data/lex/cards",
    "texts_path": "data/lex/texts",
    "output_dir": "var/lex/pipeline-2026-04-03",
    "resume": true
  }'
```

```bash
http POST :8000/api/v1/control/lex/trigger \
  "Authorization:Bearer $TOKEN" \
  cards_path=data/lex/cards \
  texts_path=data/lex/texts \
  output_dir=var/lex/pipeline-2026-04-03 \
  resume:=true
```

### `GET /api/v1/control/lex/status/{pipeline_id}`

Poll Lex pipeline execution state.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/lex/status/$PIPELINE_ID"
```

```bash
http GET :8000/api/v1/control/lex/status/$PIPELINE_ID \
  "Authorization:Bearer $TOKEN"
```

### `GET /api/v1/control/lex/graph/stats`

Inspect Lex knowledge graph statistics for a given output directory.

- Query parameters:
  - `output_dir`: required filesystem path to the Lex graph/index output

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/lex/graph/stats?output_dir=var/lex/pipeline-2026-04-03"
```

```bash
http GET :8000/api/v1/control/lex/graph/stats \
  "Authorization:Bearer $TOKEN" \
  output_dir==var/lex/pipeline-2026-04-03
```

### `POST /api/v1/control/lex/search`

Search indexed Lex facts.

- Request body: `LexSearchRequest`
  - Required: `query`, `output_dir`
  - Optional: `top_k`

```bash
curl -X POST "http://localhost:8000/api/v1/control/lex/search" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "державна допомога домогосподарствам",
    "output_dir": "var/lex/pipeline-2026-04-03",
    "top_k": 10
  }'
```

```bash
http POST :8000/api/v1/control/lex/search \
  "Authorization:Bearer $TOKEN" \
  query="державна допомога домогосподарствам" \
  output_dir=var/lex/pipeline-2026-04-03 \
  top_k:=10
```

## Operational Endpoints

### `GET /api/v1/control/workers`

List current or recent control worker leases.

- Query parameters:
  - `active_only`: default `true`
- Response body: `ControlWorkersResponse`
  - `active_only`
  - `workers[]` with `worker_id`, `state`, `backend`, `active_job_id`, heartbeat and lease timestamps

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/workers?active_only=true"
```

### `GET /api/v1/control/outbox`

Inspect durable outbox events emitted by the control plane.

- Query parameters:
  - `state`: default `pending`
  - `limit`: default `100`, max `500`
- Response body: `ControlOutboxEventsResponse`
  - `state`
  - `limit`
  - `events[]` with topic, event key, job/run ids, payload, publish state, and error message

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/outbox?state=pending&limit=50"
```

### `POST /api/v1/control/decision-validity/events`

Publish a durable decision-validity event.

- Request body: `DecisionValidityEventRequest`
  - Required: `trigger_type`, `status`, `reason`
  - Optional: `dependency_keys`, `source_ref`, `dedupe_key`, `occurred_at`, `payload`
- Response body: `DecisionValidityEventResponse`
  - `event_id`
  - `dedupe_key`
  - `affected_packets`
  - `affected_statuses`
  - `message`

```bash
curl -X POST "http://localhost:8000/api/v1/control/decision-validity/events" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "trigger_type": "law_change",
    "status": "warning",
    "reason": "Tax code amendment changes eligibility thresholds.",
    "dependency_keys": ["norm_pack:ua-tax-code-2026-04"],
    "source_ref": "sha256:2222222222222222222222222222222222222222222222222222222222222222"
  }'
```

### `GET /api/v1/control/runs/{run_id}/decision-validity`

Read the full decision-validity lifecycle for a run's decision packet.

- Response body: `DecisionValiditySummaryResponse`
  - `decision_packet_ref`
  - `status`
  - `checked_at`
  - `reasons`
  - `triggers`
  - `review_required`
  - `recommended_action`
  - `lifecycle`
- Special error:
  - `404 decision_packet_missing` when the run has no decision packet

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/runs/$RUN_ID/decision-validity"
```

### `GET /api/v1/control/decision-packets/{decision_packet_ref}/decision-validity`

Read the same decision-validity summary directly by decision-packet artifact reference.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/decision-packets/$DECISION_PACKET_REF/decision-validity"
```
