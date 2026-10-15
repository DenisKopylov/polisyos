# Use the Control Plane

Related reference: [Control Plane API](../reference/api/control.md). Related how-to: [Deploy Runtime](deploy-runtime.md).

> This page is for operators and integrators who need to launch runs, ingestion,
> and Lex jobs through the runtime HTTP surface and understand control-plane
> state.

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/control.py`, the control-plane service bindings, and `docs/reference/api/control.md`.
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; route-source inspection only. No control-plane request or runtime service was exercised in this update.

## Inputs

- a running Runtime API;
- a bearer token, if the auth path is enabled;
- `data_snapshot_ref`, `input_bindings_ref`, or `data_view_request_ref`;
- for a full workflow launch, `trinity_bundle_ref` and related references when
  needed.

## Outputs

- a `job_id` for durable polling;
- a `run_id` for run-facing debug APIs;
- access to the workers/outbox/data/Lex control surface.

## Commands

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/control/workers"
```

The PolicyOS control plane handles write-capable operations:

- launching a workflow run;
- launching a natural-language run;
- data discovery/resolve/ingest;
- Lex batch jobs;
- operational visibility through jobs, workers, outbox, and decision-validity
  endpoints.

## Before you begin

Confirm that the runtime is running:

```bash
uvicorn 'polisyos.runtime.http.app:create_runtime_api_app' --factory --reload
```

Also make a deliberate choice of execution profile and state store:

- `POLISYOS_EXECUTION_PROFILE`
- `POLISYOS_CONTROL_WORKER_BACKEND`
- `POLISYOS_CONTROL_STATE_STORE_BACKEND`
- `POLISYOS_CONTROL_SQLITE_PATH` or `POLISYOS_CONTROL_POSTGRES_DSN`

For more about the environment surface, see [Deploy Runtime](deploy-runtime.md).

## 1. Launch a workflow run

Basic launch:

The hash below is an illustrative placeholder, not an available input artifact.
A successful launch requires a persisted, authorized artifact whose content
matches the supplied `data_snapshot_ref`.

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

The response provides:

- `run_id`
- `job_id`
- `effective_execution_profile`

Use `run_id` for run-facing debug APIs and `job_id` for durable control-job
state.

## 2. Poll durable job state

Check the job immediately after launch rather than infer its state from logs:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
```

Focus on:

- `state`: `pending`, `running`, `completed`, `failed`
- `kind`
- `progress`
- `started_at` / `finished_at`

## 3. Inspect workers and the outbox

If a job is stuck or not progressing, inspect the operational endpoints:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/workers"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/outbox"
```

Look for:

- whether a worker has an active lease;
- whether a job is stuck without a heartbeat;
- whether outbox events are accumulating without downstream consumption;
- whether the expected backend matches the actual deployment mode.

## 4. Use data endpoints as a separate operational layer

The control plane can prepare data as well as launch Scientist workflows:

- `POST /api/v1/control/data/discover`
- `POST /api/v1/control/data/resolve`
- `POST /api/v1/control/data/preview`
- `POST /api/v1/control/data/ingest`
- `GET /api/v1/control/data/connectors`
- `GET /api/v1/control/data/profiles`
- `GET /api/v1/control/data/binding-profiles`

Practical sequence:

1. Discover/resolve candidate datasets.
2. Preview coverage.
3. Ingest and obtain a `data_snapshot_ref`.
4. Launch the workflow run with the prepared snapshot.

## 5. Launch Lex jobs as a control-plane workload

For the Lex batch path:

```bash
curl -X POST "http://localhost:8000/api/v1/control/lex/trigger" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cards_path": "data/lex/cards",
    "texts_path": "data/lex/texts",
    "output_dir": ".polisyos/lex-out",
    "resume": true,
    "execution_profile": "research"
  }'
```

Then use:

- `GET /api/v1/control/jobs/{job_id}`
- `GET /api/v1/control/lex/status/{pipeline_id}`
- `GET /api/v1/control/lex/graph/stats`

## 6. Understand the control-plane boundaries

The control plane does not replace the full runtime debug surface.

Use it for:

- launch/poll/operate;
- durable state;
- worker/outbox visibility;
- write-capable orchestration.

Move to the run/debug APIs when you need:

- a timeline;
- node outcomes;
- artifact lineage;
- evidence context;
- a decision-validity summary for a specific run.

## 7. Minimal operator route

To quickly understand system state, the usual sequence is:

1. `POST /api/v1/control/runs` or `.../lex/trigger`
2. `GET /api/v1/control/jobs/{job_id}`
3. if there is a problem: `GET /api/v1/control/workers`
4. then: `GET /api/v1/control/outbox`
5. if a run has been created: continue to `/api/v1/runs/{run_id}/timeline`,
   `/nodes`, and `/lineage`

## Rollback

For a local control-plane workflow, a safe rollback usually means:

1. Stop the runtime.
2. Remove the scratch SQLite state store if the control plane used a local file.
3. Clean up temporary CAS/data outputs only in the experimental directory.

If the issue has reached the release/canary level, follow the operator runbooks
instead of deleting state manually.

## Troubleshooting

- If launch returns `400 missing_data_source`, provide one of the three fields
  in `data_source`.
- If a `job_id` exists but there is no progress, inspect `/workers` and `/outbox`
  before opening source code.
- If you already have a `run_id`, further triage is usually more effective
  through [Debug Failed Run](debug-failed-run.md).

## Next steps

- For deployment and environment policy, see [Deploy Runtime](deploy-runtime.md).
- For failure triage, see [Debug Failed Run](debug-failed-run.md).
- For the full endpoint catalog, see the [Control Plane API reference](../reference/api/control.md).
