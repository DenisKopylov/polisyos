# Debug a Failed Run

Related reference: [Runs API](../reference/api/runs.md). Related how-to: [Use Control Plane](use-control-plane.md).

> This page is for engineers and operators who need to quickly locate a failure
> and determine whether it comes from orchestration, data, governance, or
> control-plane infrastructure.

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/runs.py`, `src/polisyos/runtime/http/routes/control.py`, and the linked Runtime API references.
Repository source reviewed: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb` on 2026-10-14; route-source inspection only. No runtime request was made in this update.

## Inputs

- a `job_id` and/or `run_id`;
- a bearer token, if the auth path is enabled;
- access to the runtime URL and related runbooks.

## Outputs

- the failing layer: control plane, runtime DAG, data/lineage, or governance;
- the smallest set of endpoints needed for the next step;
- a decision to fix inputs, continue triage, replay/reissue, or follow a rollback
  runbook.

## Commands

```bash
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
curl -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/runs/$RUN_ID/timeline"
curl -N -H "Authorization: Bearer $TOKEN" "http://localhost:8000/api/v1/runs/$RUN_ID/live"
```

In PolicyOS, the most practical approach is to start with observable layers and
work downward, rather than begin with source code.

## 1. Start with the job state

If the run was started through the control plane, check the job first:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/control/jobs/$JOB_ID"
```

Important signals:

- `state=failed` indicates that the problem has been recorded in the durable
  state store;
- `progress` shows whether the job may be stuck partway through;
- `kind` distinguishes a workflow failure from a Lex pipeline failure.

If the job is not progressing, check these next:

- `GET /api/v1/control/workers`
- `GET /api/v1/control/outbox`

## 2. Move to the run timeline

Once you have a `run_id`, inspect the timeline:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/timeline"
```

The timeline helps answer three questions:

- which node the workflow stopped at;
- whether the failure occurred before or after a governance gate;
- whether a successful checkpoint or artifact emission occurred immediately
  before the failure.

## 3. Inspect node outcomes and the workflow view

The following two endpoints usually provide the highest signal-to-noise ratio:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/nodes"

curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/workflow"
```

Look for:

- a node status/error that stopped the graph;
- missing prerequisites;
- divergence between the expected DAG and the steps that actually ran.

## 4. Trace artifact lineage

If you suspect a data/input problem, inspect lineage:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/lineage?max_depth=3&max_nodes=250"
```

This is especially useful when you need to determine:

- which `data_snapshot_ref` actually entered the run;
- whether a `NormPack` or evidence bundle was assembled;
- whether the run reached decision-packet or replay artifacts.

## 5. Check the governance and decision-validity layers

If the run did not fail technically but stopped for policy/gate reasons, inspect:

- `GET /api/v1/runs/{run_id}/evidence-context`
- `GET /api/v1/control/runs/{run_id}/decision-validity`

Signs of a governance-related stop:

- issues with severity `BLOCKER`;
- a human-review requirement;
- missing evidence/trust/replay prerequisites.

## 6. Use the live stream for active debugging

When a run is still executing and you need a near-real-time trace:

```bash
curl -N -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/api/v1/runs/$RUN_ID/live"
```

The live stream is especially useful for:

- timeline events;
- governance summaries;
- decision-validity state;
- agent/pipeline progress.

## 7. Think about checkpoints and replay

If a failure occurred after partial progress, check:

- which `checkpoint_policy` was used at launch;
- whether `last_checkpoint_ref` exists in run-facing artifacts/state;
- whether replayable audit artifacts have already been assembled.

Practical rule:

- if the failure occurred before artifacts were materialized, fix the
  input/orchestration;
- if the failure occurred after a checkpoint, continue triage from lineage and
  replay-ready artifacts;
- if the failure appears nondeterministic, compare checkpoint/reference trails
  across two runs.

## 8. Troubleshooting

1. `job failed` with no worker heartbeat: inspect the control-plane backend and
   worker leases.
2. `job completed`, but the run is unusable: inspect governance,
   decision-validity, and evidence-context.
3. `run stalled` mid-DAG: inspect `timeline`, `nodes`, and `workflow`.
4. `unexpected result` after successful completion: inspect `lineage`, input
   artifacts, and the replay trail.

## Rollback

If the failure already affects a canary or production path, stop local-only
forensics and follow the operational rollback procedures:

- [Runtime API Outage](../runbooks/runtime-api-outage.md)
- [Replay Or Restore](../runbooks/replay-or-restore.md)
- [Canary Rollback Or Promotion Failure](../runbooks/canary-rollback-or-promotion-failure.md)

## Next steps

- For the launch/poll operational surface, see [Use Control Plane](use-control-plane.md).
- For environment and deployment posture, see [Deploy Runtime](deploy-runtime.md).
- For API details, see the [Runs API reference](../reference/api/runs.md).
