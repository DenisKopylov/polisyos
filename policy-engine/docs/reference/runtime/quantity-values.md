# Quantity Values

Freshness: 2026-04-24.
Owner: `@runtime-api-owners`
Source of truth: `src/polisyos/core/contracts/runtime.py`

`QuantityValue` is the runtime contract for every number that can influence a
PolicyOS decision. It prevents naked decision numbers by carrying the value,
unit, lineage, uncertainty, temporal scope, and classification as one envelope.

## Shape

```json
{
  "point": 0.23,
  "unit": {
    "code": "1",
    "system": "ucum",
    "display": "ratio"
  },
  "metric_id": "employment_rate_delta",
  "lineage": {
    "id": "artifact:sha256:...",
    "status": "verified",
    "freshness": "current",
    "summary": {
      "source": "decision_packet.simulation_results.employment_rate_delta"
    },
    "compact_summary": [
      { "kind": "source", "label": "Decision packet" },
      { "kind": "result", "label": "employment_rate_delta" }
    ]
  },
  "uncertainty": {
    "ci_95": [0.15, 0.31],
    "method": "bootstrap",
    "identifiability": "estimated",
    "disputed": false
  },
  "time": {
    "valid_at": "2026-04-15T12:00:00Z",
    "tx_at": "2026-04-16T09:20:00Z"
  },
  "quantity_class": "decision"
}
```

## Classes

| Class       | Rule                                                                 |
| ----------- | -------------------------------------------------------------------- |
| `decision`  | Must be `QuantityValue`; UI renders through `<Quantity />`.          |
| `telemetry` | May remain primitive only when explicitly classified as telemetry.   |
| `layout`    | Excluded from provenance law.                                        |
| `debug`     | Allowed only in tests, stories, mocks, or explicit fixture modules.  |

## Untraced Values

`LineageRef.status = "untraced"` requires:

- `reason_code`
- `tracking_issue`

The literal id `untraced` is valid only with `status = "untraced"`. This keeps
missing lineage visible in API payloads and coverage reports.

## Runtime Endpoints

| Endpoint                                      | Purpose                                  |
| --------------------------------------------- | ---------------------------------------- |
| `GET /api/v1/lineage/{lineage_id}`            | Single compact plus full lineage graph   |
| `POST /api/v1/lineage/batch`                  | Batch lookup for tables and dashboards   |
| `GET /api/v1/lineage/{lineage_id}/export/*`   | OpenLineage or PROV export payload       |
| `GET /api/v1/runs/{run_id}/quantities`        | Run-level quantity coverage inventory    |

## Migration

1. Inventory numeric render sites with `tools/design/report-quantity-coverage.ts`.
2. Migrate simple decision numbers with `tools/design/migrate-numbers-to-quantity.ts`.
3. Enable `policyos/quantity-must-be-wrapped` in warn mode for one feature
   slice.
4. Convert backend payloads to `QuantityValue` before tightening the frontend
   rule to error.
5. Keep telemetry/layout/debug explicit so the warning stream stays actionable.
