# Trust View Law

Trust View is an audit rendering mode, not a separate truth surface.

This page states a presentation rule, not a verification or publication
capability. At source pin `bafca83bff9ff49eef1466bc491a8420b5cd1dbb`, the
dashboard has a local Trust View toggle and metadata consumers, but the
projection cannot promote a status into policy authority. Missing or
projection-only verification metadata remains `Unknown`; see the
[current frontend surface map](../reference/frontend/current-surface-map.md)
for the code and inspected tests. Those tests were not run, and no browser or
deployment was inspected for this documentation pass.

## Product Law

Trust View must render over the same response payloads, cache keys and temporal
scope as the normal decision surface. It may reveal additional verification
metadata already embedded in lineage, quantity, artifact or authorship payloads,
but it must not fetch a different "trusted" answer.

## Modes

- `off` keeps the normal decision UI.
- `compact` adds status glyphs and short hash chips where the density budget
  allows.
- `expanded` adds source, method, verifier, timestamp and temporal scope rows on
  decision surfaces. Dense tables collapse to the inspector affordance.

The global shell toggle cycles `off -> compact -> expanded` and the same cycle is
available through `Cmd/Ctrl+Shift+T`.

## Metadata Contract

Verification metadata uses consistent runtime names:

- `hash`
- `verification_status`
- `verified_by`
- `verified_at`
- `verification_method`
- `freshness`
- `dispute_status`
- `temporal_scope`

`verification_status`, when supported by the corresponding owner evidence,
describes lineage/hash verification. It must never be worded as policy
correctness or official endorsement. A Trust View control, chip, hash, or
metadata projection cannot substitute for that evidence or change authority.

## Temporal Rule

Every trust payload that travels through runtime APIs must echo the active
`TemporalScope`. UI query keys must keep the same temporal key as the underlying
run, quantity or lineage fetch.

## Accessibility

Trust metadata must be keyboard reachable, dismissible and persistent. Inline
labels summarize the audit state; the inspector carries the full metadata so
screen readers are not forced to hear the complete provenance graph at every
cell.
