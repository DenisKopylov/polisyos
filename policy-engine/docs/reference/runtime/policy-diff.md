# Policy Diff Runtime Contract

Owner: `@runtime-owners`
Source of truth: `src/polisyos/runtime/http/routes/runs.py`, `src/polisyos/runtime/http/services/**`, `packages/runtime-api-client/**`, and `apps/runtime-dashboard/**`

Policy Diff compares two runs through a `ComparisonFrame`, not through raw JSON
or word-level document changes. The endpoint only renders deltas after the
runtime has checked that the runs are comparable enough for the requested frame.

## Endpoint

```http
GET /api/v1/runs/compare?a={run_a}&b={run_b}&valid_at=...&tx_at=...&scenario_id=...
```

The response includes:

- `comparison_frame`: run ids, shared metric set, population, unit policy,
  temporal scope, scenario scope and assumption set.
- `comparability`: `compatible`, `warning` or `blocked`, with typed warnings and
  blocked reasons.
- `deltas`: ranked `DeltaQuantity` entries. Every numeric value inside a delta is
  a `QuantityValue`: `a`, `b`, `delta_absolute`, and `delta_relative`.

If `comparability.status` is `blocked`, clients must not render numeric deltas.

## Candidate Discovery

```http
GET /api/v1/runs/{run_id}/compare-candidates
```

Returns tenant-scoped candidates with a pre-flight `comparability` report. UI
should prefer `compatible`, then `warning`, and hide cross-tenant candidates.
Each candidate includes a `relation` field: `baseline`, `previous`,
`recommended`, or `selected`, so command surfaces can explain why a comparator
is being offered.

## Temporal Correctness

All compare requests accept the same canonical temporal query params as run
detail endpoints:

- `valid_at`
- `tx_at`
- `t`
- `branch`
- `snapshot_id`
- `scenario_id`

Responses echo `temporal_scope`, set `X-Temporal-Scope`, and use an ETag that
includes both run ids plus the full temporal scope.

Deep links use `/compare/{run_a}/{run_b}` and preserve temporal URL params plus
view state params such as `metric` and `panel`. A shared URL must reproduce the
same run pair, temporal scope, selected metric and visible diff panel.

## Client Rules

- Never compute a decision-bearing delta from naked numbers in the UI.
- Use backend deltas when available; a client fallback is allowed only when the
  backend returns normalized, temporal-scoped payloads and the comparability
  report is not blocked.
- Every visible delta must expose provenance drift: source, model/hash,
  freshness and verification changes.
