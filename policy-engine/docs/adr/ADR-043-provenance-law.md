# ADR-043: Provenance Law Through QuantityValue

## Status

Approved

## Date

2026-04-22

## Context

PolicyOS already records artifact lineage, Fabric value lineage, time-travel
scope, and governance metadata. The weak point was the API/UI boundary: a raw
number could still appear in a decision surface without its unit, uncertainty,
temporal scope, verification status, or lineage.

That creates false confidence. A dashboard value that came from a verified
artifact and a value copied from an untraced fixture look identical unless the
reader opens a separate debug path.

## Decision

Provenance is enforced as a data law:

1. Every decision-bearing numeric value MUST be emitted as `QuantityValue`.
2. `QuantityValue` is atomic. Callers pass `point`, `unit`, `lineage`,
   `uncertainty`, and `time` together, not as detached props.
3. `LineageRef.status = "untraced"` is allowed only with both `reason_code`
   and `tracking_issue`.
4. Telemetry, layout, and debug numbers are classified separately. They may
   remain primitives only when the classification is explicit.
5. Runtime lineage APIs expose both compact summaries and full graph payloads.
   Hover surfaces consume compact summaries; deep-dive panels lazy-load the
   full graph.
6. The frontend canonical renderer is `<Quantity value={quantityValue} />`.
   Decision surfaces must not render primitive decision numbers directly.

## Contract

`QuantityValue` contains:

- `point`: numeric value.
- `unit`: `UnitRef` with machine code and display label.
- `metric_id`: stable metric identifier when known.
- `lineage`: `LineageRef` with verification status, freshness, summary, and
  optional compact summary.
- `uncertainty`: confidence intervals, quantiles, method, identifiability, and
  dispute flag.
- `time`: `TemporalRef` for valid time, transaction time, snapshot, branch, and
  scenario scope.
- `quantity_class`: `decision`, `telemetry`, `layout`, or `debug`.

The runtime API exposes:

- `GET /api/v1/lineage/{lineage_id}`
- `POST /api/v1/lineage/batch`
- `GET /api/v1/lineage/{lineage_id}/export/openlineage`
- `GET /api/v1/lineage/{lineage_id}/export/prov`
- `GET /api/v1/runs/{run_id}/quantities`

## Consequences

- The backend can emit partially migrated payloads, but missing lineage must be
  visible as typed `untraced` status, not hidden behind a decorative id.
- The UI can build progressive disclosure consistently: inline value first,
  hover/focus compact lineage second, full graph third.
- ESLint and coverage tooling provide a phased warning path by feature slice.
- Generated OpenAPI and frontend API types include the quantity and lineage
  contracts.

## Related Decisions

- Extends [ADR-0123](0123-artifact-ref-governance.md).
- Related to [ADR-044](ADR-044-time-as-primitive.md).
- Related to [ADR-046](ADR-046-authored-text-registry.md).
