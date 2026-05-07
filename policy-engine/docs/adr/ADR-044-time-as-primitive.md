# ADR-044: Time as a UI Primitive

## Status

Approved

## Date

2026-04-22

## Context

Policy analysis is inherently temporal. Every claim has an `as_of`
timestamp; every norm has an enactment date and an expiry; every
observation has a `valid_time` and a `record_time`. The current UI
collapses these into "now" — dashboards show what the system believes
today, with no first-class way to ask "what was the state of the world
at `t = 2025-11-01`?" or to scrub continuously between points.

Best-in-class SaaS tools in adjacent spaces (Observable for
notebooks, Datadog's time-slider for metrics) demonstrate that
**time-as-primitive** — a global scrubbable cursor that every
time-aware component respects — is feasible and categorically raises
the usefulness of an analytical interface.

The design plan (Phase 2.1, primitive B1) proposes time-as-primitive
as a platform law. Before implementation, the contract must be
decided: what does "time-aware" mean for a component, how is the
global cursor propagated, and what is the backend contract for
point-in-time queries?

## Decision

1. Time is a **UI primitive**, not a filter. A `TimeContext` provider
   at the app root exposes:

   ```ts
   type TimeContext = {
     cursor: Temporal.Instant; // current UI time
     setCursor: (t: Temporal.Instant) => void;
     mode: "live" | "historical" | "counterfactual";
     bounds: { min: Temporal.Instant; max: Temporal.Instant };
   };
   ```

   `live` mode ties the cursor to wall clock; `historical` detaches
   and pins to the chosen instant; `counterfactual` mode composes
   with the counterfactual layer (Phase 2.4).

2. The scrubber component (`<TimeScrubber />`, Phase 2.1) owns the
   global cursor and is visible in the top rail when the current
   route is time-aware. Keyboard shortcuts `,` / `.` move the cursor
   by one canonical step; `[` / `]` move by one larger unit.
3. Every time-aware component declares itself via the hook
   `useTimeCursor()`. Components that opt into time awareness must
   re-query their data with `?as_of=<cursor>` or equivalent; the
   runtime exposes `as_of` as a universal query parameter on
   point-in-time endpoints.
4. Backend contract: every read endpoint that can return
   version-sensitive data accepts `?as_of=<RFC3339 timestamp>` and
   returns state as-of that instant, using the lakehouse snapshot
   semantics defined in [ADR-0122](0122-lakehouse-snapshot-semantics.md).
   Endpoints that cannot honour `as_of` (e.g. streaming live feeds)
   return HTTP `400` when the cursor is not `live`.
5. The cursor is persisted per-session in `sessionStorage` under the
   key `polisyos.time.cursor`. Navigating between routes preserves
   the cursor; reloading preserves it; sharing a URL via the
   `?t=<cursor>` query parameter makes the state bookmarkable.
6. Reduced-motion users see no scrubber animation; the cursor jumps
   discretely between points (§5 of [MOTION.md](../brand/MOTION.md)).
7. The cursor interacts with provenance (ADR-043): every
   `ProvenanceRef` exposes `as_of`, and hovering on the scrubber
   highlights components whose `as_of` matches the cursor within a
   configurable tolerance (default: ±1 min).

Source of truth:

- Frontend: `apps/runtime-dashboard/src/shared/time/TimeContext.tsx`
  (new, Phase 2.1).

- Frontend scrubber: `apps/runtime-dashboard/src/shared/time/TimeScrubber.tsx`.
- Backend: `policy-engine/src/policy_engine/runtime/as_of.py` (new,
  Phase 2.1) centralising `as_of` parsing, validation, and routing
  to lakehouse snapshots.

- OpenAPI: each applicable endpoint gains a `$ref` to the shared
  `AsOfQueryParameter`.

## Consequences

- Every backend read endpoint inherits a contract responsibility: if
  it is version-sensitive, it must honour `as_of`; if it cannot, it
  must 400.

- Analysts gain the ability to answer retrospective questions without
  leaving the UI or running separate SQL.

- The lakehouse snapshot layer becomes a hot path — query plans must
  be benchmarked for `as_of` queries specifically (new SLO added in
  Phase 2.1).

- Shareable URLs with `?t=` become a first-class artefact (they are
  implicit deep links into history).

## Concrete impact

Files created or modified in Phase 2.1:

- New: `apps/runtime-dashboard/src/shared/time/TimeContext.tsx`
- New: `apps/runtime-dashboard/src/shared/time/TimeScrubber.tsx`
- New: `apps/runtime-dashboard/src/shared/time/useTimeCursor.ts`
- New: `apps/runtime-dashboard/src/shared/time/time.test.tsx`
- New: `policy-engine/src/policy_engine/runtime/as_of.py`
- New: `policy-engine/tests/unit/runtime/test_as_of.py`
- Modified: every runtime route under `policy-engine/src/policy_engine/runtime/routes/**`
  that returns version-sensitive data (catalogued in Phase 2.1 scope).

- Modified: `policy-engine/schemas/runtime_api_v1.openapi.json` —
  `AsOfQueryParameter` shared schema.

- Modified: `apps/runtime-dashboard/src/api/types.ts` (regenerated).

## Related Decisions

- Extends: [ADR-0122](0122-lakehouse-snapshot-semantics.md) — provides
  the storage primitive that makes `as_of` tractable.

- Related: [ADR-043](ADR-043-provenance-law.md) — provenance `as_of`
  field and scrubber coupling.

- Related: Phase 2.4 counterfactual layer — composes with `mode =
"counterfactual"` of the `TimeContext`.
