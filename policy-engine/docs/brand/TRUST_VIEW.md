# Trust View Law

Trust View is an audit rendering mode, not a separate truth surface.

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

`verification_status` means the lineage/hash was checked. It must never be
worded as policy correctness or official endorsement.

## Temporal Rule

Every trust payload that travels through runtime APIs must echo the active
`TemporalScope`. UI query keys must keep the same temporal key as the underlying
run, quantity or lineage fetch.

## Accessibility

Trust metadata must be keyboard reachable, dismissible and persistent. Inline
labels summarize the audit state; the inspector carries the full metadata so
screen readers are not forced to hear the complete provenance graph at every
cell.
