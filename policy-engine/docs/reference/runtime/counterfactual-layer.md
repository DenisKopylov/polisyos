# Counterfactual Layer

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/scenarios.py`, `src/polisyos/runtime/http/services/scenarios.py`, `src/polisyos/ir/`, and `tests/unit/runtime/http/test_scenarios_api.py`
Source pin: `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`
Validation status: Source and test-reference inspection only for this documentation update; the tests and scenario routes were not run.

PolicyOS counterfactuals are named scenario manifests, not anonymous forecast
flags. Any value rendered as a scenario value must point to a `ScenarioRef`, and
the referenced scenario must include interventions, assumptions, temporal scope,
model lineage, baseline lineage and known limitations.

The scenario route and typed manifest provide candidate projections. They do
not establish causal identification, producer authority, current world truth,
or permission to publish a recommendation; keep unresolved assumptions or
scope as typed limitations.

## Core Contracts

- `ScenarioManifest` is the source of truth for a scenario. It names the
  baseline run, policy question, author, affected population, validity window,
  model family, interventions, assumptions, constraints and stale reasons.
- `ScenarioRef` is embedded in every counterfactual metric. It carries the
  scenario id, status, baseline run, temporal scope, manifest hash, lineage and
  assumption ids.
- `CounterfactualMetric` contains `actual`, `counterfactual` and `delta`
  quantities. Each is a `QuantityValue` envelope. The `counterfactual` and
  `delta` quantities must carry `time.scenario_id`.
- `ScenarioCapability` declares which surfaces and metrics support scenario
  rendering. Unsupported metrics return explicit reason codes.

## Runtime Endpoints

```http
GET  /api/v1/runs/{run_id}/scenarios
POST /api/v1/runs/{run_id}/scenarios
GET  /api/v1/runs/{run_id}/metrics?scenario_id=...
GET  /api/v1/scenarios/{scenario_id}
GET  /api/v1/scenarios/{scenario_id}/capabilities
```

All run-scoped endpoints accept the same temporal query parameters as run
quantities: `valid_at`, `tx_at`, `t`, `branch`, `snapshot_id` and `scenario_id`.
Responses echo `temporal_scope`, set `X-Temporal-Scope`, and include temporal
scope in the response ETag.

## Rendering Rules

- Scenario values must never render without `ScenarioRef`.
- Scenario values must show an assumption cue and expose assumption lineage in
  provenance views.
- `actual_vs_scenario` mode should use one normalized payload from
  `/api/v1/runs/{run_id}/metrics` so the UI does not double-fetch actual values.
- Stale scenarios must show stale state when baseline evidence, lineage or model
  version changed after scenario computation.

## Failure Modes

- Missing `scenario_id` on `/metrics` is a request validation error.
- A scenario whose baseline does not match the requested run returns
  `scenario_baseline_mismatch`.
- Runs without decision-bearing quantities return unsupported capabilities and
  do not fabricate scenario metrics.
