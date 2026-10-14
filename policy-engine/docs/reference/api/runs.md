# Runs API

Related explanation: [Architecture](../../explanation/architecture.md).

Freshness: 2026-10-12
Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/runs.py`, `src/polisyos/runtime/http/dependencies.py`, and `schemas/runtime_api_v1.openapi.json`
Validation:

- `uv run pytest -q tests/unit/runtime/http/test_runs_api.py tests/unit/runtime/http/test_timeline_api.py tests/unit/runtime/http/test_runtime_api_authz.py`
- `uv run pytest -q tests/unit/runtime/http/test_lineage_routes.py tests/unit/runtime/http/test_temporal_routes.py`
- `uv run pytest -q tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py`
- `PYTHONPATH=src:. uv run --extra runtime --extra ml python tools/ops_runners/runtime/check_runtime_api_contract.py`

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
| `GET`  | `/api/v1/runs/{run_id}/paper`            | `RunPaperPacket`             | Replay-pinned run paper and selected artifact refs                      |
| `GET`  | `/api/v1/runs/{run_id}/workflow`         | `RunWorkflowResponse`        | Workflow/DAG view                                                      |
| `POST` | `/api/v1/runs/{run_id}/predictive-calibration` | `PredictiveCalibrationResponse` | Run-bound candidate diagnostic; appends a selected CAS ref event |
| `GET`  | `/api/v1/runs/{run_id}/predictive-calibration` | `PredictiveCalibrationResponse` | Reopens the latest appended diagnostic and recomputes S10 |
| `GET`  | `/api/v1/runs/live`                      | `text/event-stream`          | Route-only, schema-hidden global live stream                           |
| `GET`  | `/api/v1/runs/{run_id}/live`             | `text/event-stream`          | Route-only, schema-hidden per-run live stream                          |

Common status codes for committed endpoints: `200`, `400`, `401`, `403`, `404`, `422`, `500`.

Validation anchors:

- `tests/unit/runtime/http/test_runs_api.py`
- `tests/integration/runtime_quality/test_generic_n4_child_profile_set_served.py`
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

`run.generic_cycle_simulation` is present when the run persisted a generic cycle
simulation projection. It exposes the exact source, profile-family, complete
N4-derived child-profile-set, N5 input/execution, and result references that the
read path could resolve and bind from the run's persisted history. Each child
binding carries its source result and atom references, semantic selection key,
context-job ref, selected profile ref, and an explicit historical-binding
status. A sibling failure remains visible in `recursive_cycle_checkpoint`; it
does not erase an independently replayed successful sibling observation.

This projection is candidate-only: `authority_purpose` is
`cycle_input_candidate_only`, `publication_authority` is `false`, and
`currentness_status` is `not_established`. An N5 result is exposed as an N8
conditional value only after the persisted request binding, result, and value
port are replayed together. It does not establish world currentness, external
truth, or publication authority. When persisted lineage cannot be resolved,
the response carries a typed `not_established` status and limitation code; a
field marker or profile self-label does not establish the join.

An explicitly enabled contract-testing runtime may also expose a persisted
`credal_source_attempt_ref` when the actual N4 producer terminates without a
CredalReference. That record keeps `credal_source_status` and
`currentness_status` at `not_established`, carries no CredalReference or edge
body, and is not produced by default. A fresh read reopens the attempt, N4
source, selected context, and profile. It replays a configured profile family
when the terminal source has one; a source that produced no child family has no
family ref, while the N4 manifest and parent context/profile are still
revalidated. Failed replay remains a typed limitation and never becomes an
estimate or confidence claim.
The server-only setting is accepted only under the `dev` execution profile.

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
  - `notes`: optional limitation codes. When the workflow report is genuinely absent, the nodes
    are a timeline fallback and `notes` contains `workflow_report_missing_or_unavailable`. A
    present malformed report still returns the typed canonical-profile refusal. Older servers may
    omit `notes`; that leaves fallback status unreported.

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
Persisted root ArtifactRefs pass through with their selected manifest profiles. Legacy
profile-less refs remain unqualified; the root_artifact_id filter is an ID-only unqualified override.
The response includes root_artifact_refs in addition to the compatibility ID list.


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
- Cost event rows preserve `reported`, `estimated`, `reuse`, and `unknown` origins with
  producer event identity and settlement status. Unknown amounts remain null; the aggregate
  `cost_usd` is null when any included event has unknown or unsettled cost. Reported and
  estimated totals remain separately available, and token-price estimates are heuristic.
- Producer model and logical-route identity are pinned by the configured pre-dispatch intent;
  response-declared labels do not rebind served event identity or estimate basis.
- Compiler/preflight and model-variant events appear in distinct steps. Identical event IDs
  across persisted sources count once; a conflicting payload for the same ID is refused.
- These rows reflect local producer settlement and do not assert an external invoice or provider
  billing receipt.

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
- `data_snapshot_ref` and `data_view_request_ref` retain complete selected artifact refs, including
  manifest-profile digests when present. The request ref is returned only when the exact selected
  snapshot manifest has one unique profile-bound `data_view_request_ref` edge that resolves to a
  supported JSON request artifact. Missing, ambiguous, or stale lineage is surfaced in `warnings`;
  the endpoint never reconstructs request context from an artifact ID alone.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/evidence-context"
```

```bash
http GET :8000/api/v1/runs/$RUN_ID/evidence-context \
  "Authorization:Bearer $TOKEN"
```

## `GET /api/v1/runs/{run_id}/paper`

Return one replay-pinned `RunPaperPacket` for the run.

- Each `artifact_links[].artifact_ref` retains `manifest_profile_sha256` when the producer
  supplied a selected manifest view.
- The matching `href` carries that exact profile in the `manifest_profile_sha256` query. A
  profile-less legacy ref remains unqualified and gets an ID-only href; it does not claim a
  selected manifest profile.
- Run Report and Case Workspace preserve the full ref identity when rendering same-content refs
  with distinct profiles.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/paper"
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


Timeline events expose the complete typed artifact refs already emitted by the
trace producer in addition to the legacy ID lists. Temporal lineage filtering
uses those refs, so same-ID sibling profiles are not interchangeable. Older
profile-less run roots remain explicitly limited; the reader's current default
view is not retroactive producer attestation.

## Predictive calibration

POST /api/v1/runs/{run_id}/predictive-calibration accepts an explicit `intent_id`, full selected refs for the resolved run candidate source and observed snapshot, plus model, policy, and calibration-rule refs, a contiguous train/holdout split, six distinct caller-declared temporal roles, a threshold, method parameters, and seed. The route reuses the existing `runs.feedback.evaluate` permission with ownership binding to the exact run; no role grant is added. The service resolves the completed control job and exact Core manifest, requires the candidate source in the run’s resolved candidate projection and the observed snapshot, model, policy, and calibration-rule refs as exact full-profile run roots, reopens each selected CAS profile, runs ForecastOwner, persists the empirical calibration bridge and limited S10 candidate projection, then appends a versioned association-ref event to the existing diagnostic event log. Earlier associations are not rewritten.

GET /api/v1/runs/{run_id}/predictive-calibration uses `runs.review` with ownership binding to the exact run. It reads the latest association ref from the event log, verifies the payload hash, reopens the CAS association and evidence, verifies the current run binding, and recomputes S10 before returning it. No event yields 404; a mismatched event, selected profile, payload hash, or recomputed projection yields 409. POST returns 201 on success and 422 when selected inputs cannot be resolved or admitted. A purpose-scoped SQL intent row serializes identical authenticated-principal/run/intent requests across app instances sharing the database; the body digest binds the selected refs and run profile. Same-body completed retries resolve the stored exact association, changed bodies conflict, and pending/recovery states fail closed. Event publication and row completion share the database transaction. An abrupt process loss may leave a pending row for manual reconciliation; no automatic takeover or external exactly-once claim is made. Events created before principal scope was captured are not replayed under the new owner and return `predictive_calibration_legacy_intent_scope_unverifiable`. SQLite cross-instance/process checks are authored but UNRUN; PostgreSQL behavior remains unverified.

The DTO remains limited and `predictive_only`; issuer, source-time currentness, population scope, and counterfactual credibility remain `not_established`. The association is not a causal effect, recommendation, promotion, or publication authorization. The normal runtime application/container root enables this candidate route by default; `allow_candidate_run_predictive_calibration_surface=False` disables both operations before producer execution. The setting does not add a permission and is separate from the artifact-preview diagnostic gate. Canonical OpenAPI/client regeneration and execution of the composed HTTP integration test remain pending.

The response distinguishes observed holdout hit rate from nominal confidence metadata and preserves selected refs to the backtest report, empirical evidence, and forecasting uncertainty bundle. The dashboard opens the exact uncertainty-bundle profile in the artifact viewer so an operator can inspect forecast points and predictive intervals. Every result remains assessment=limited and authority_scope=predictive_only; issuer, source time, population scope, and counterfactual credibility remain not_established. A passing calibration floor does not establish causal credibility or publication authority.


A served acquisition re-entry using receipt schema v3 appends a continued `GenerationCycleRun` and records its N6/N9 result in the run-details acquisition history. For same-candidate re-entry, the typed history binds the prior and selected N4/N5 refs, preserves the profile selection identity with separate prior/current profile content hashes, and requires the exact selected target baseline to change. Current occurrences and fronts are projected from the continued run. The history remains candidate-only and does not confer publication authority. Historical v1/v2 re-entry receipts remain readable without this projection.

## Selected profile status in quantity and fabric views

`GET /api/v1/runs/{run_id}/quantities` and
`GET /api/v1/runs/{run_id}/fabric-decision-data` resolve the run's exact
`decision_packet_ref` before projecting source-contract or quantity data. The
Core reader checks a present raw manifest profile against the same selected
bytes; malformed declarations and declared-profile mismatches return HTTP `409`
with a typed `canon_profile_*` refusal. Quantity inventory reports
`canon_read_status` for this read. An absent profile is refused by default. Only explicit candidate-only compatibility
reads return `profile_absent_unqualified_candidate`; this does not establish historical
eligibility or producer attestation.
The current acquisition-route projection v1.1 reports `world_growth` from the
selected route's reverified owner receipt. `not_established` means no current
selected outcome receipt has established a result; `admitted_observation_delta`
is null. `no_growth` requires a current typed zero-delta receipt bound to the
active selected epoch, its original admission and attempt, and the route's
tenant, cell, run and source job; its delta is 0. `admitted_delta` requires the
current positive admission receipt and reports its positive delta. In the
canonical DS15 criterion, that positive outcome is named `grew`; the transport
literal `admitted_delta` is its wire representation, not a distinct semantic
state. Decision-request and accepted-job responses remain `not_established`
because those stages have not measured the owner outcome. A recovered selected
zero receipt terminates as quarantined without re-entry. These candidate-level
observations describe selected membership only; they do not establish legal
approval, publication authority, or whole-model closure.

The POST responses from `/api/v1/runs/{run_id}/acquisition-routes/{route_id}/decision-request`
and `/execute` also now return `world_growth="not_established"`. Their previous
v1 response models defaulted this field to `no_growth` before any owner outcome
was measured. This literal change is breaking for v1 clients that enumerate the
old value. Update both response decoders to accept `not_established`; when reading
legacy `no_growth` from an older server, treat it as unknown unless a selected,
verified zero-delta receipt is available. Coordinate this response change with
all consumers before deployment; the GET projection's v1.1 migration does not
make either POST response additive.

The v1.1 projection versions the explicit tri-state and nullable delta. The
dashboard continues to read v1.0 packets: pending `no_growth` (with or without
a zero default) is presented as `not_established`, because the older wire shape
did not bind that value to a measured zero receipt. Positive v1.0
`admitted_delta` remains a positive selected outcome. New server responses use
v1.1; generated OpenAPI and dashboard types are regenerated from the frozen
source after the source review.
