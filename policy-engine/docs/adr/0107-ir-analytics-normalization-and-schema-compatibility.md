# ADR-0107: IR Analytics Normalization and Schema Compatibility Policy

Status: accepted

Date: 2026-04-13

## Context

Several analytics IR models used validation as a hidden normalization boundary.
That made construction, cloning, and re-parse behavior harder to reason about,
especially for derived fields such as `n_samples`, targeting efficiency,
transportability modes, year aliases, span IDs, and mediation proportions.

Separately, `schema_version` fields existed on many IR payloads but did not
provide a rule-based answer to producer/consumer mismatches. The project needed
an explicit compatibility surface rather than relying on snapshot drift and ad
hoc migration code.

## Decision

Analytics report contracts are frozen by default. Mutable analytics objects are
allowed only when they are explicit builders or runtime accumulators, not
persisted report contracts. The current exception in this workstream is
`SelectionDiagramBuilder`, which is not a Pydantic report model and documents
its mutable builder role.

Validators may validate invariants, but they must not mutate `self`. Derived or
legacy-read normalization belongs in explicit class methods such as
`normalize_payload(...)`, `from_payload(...)`, `from_estimates(...)`, or
`from_totals(...)`. Pydantic `mode="before"` validators may call those helpers
only as compatibility shims for old serialized payloads.

The migration layer owns a schema compatibility registry with four modes:

- `FULL`: same-major producer/consumer payloads are directly readable in both
  directions unless a narrower rule is registered.

- `BACKWARD`: newer consumer code can directly read older producer payloads for
  the declared compatible line.

- `FORWARD`: older consumer code can directly read declared newer producer
  payloads only when the rule explicitly allows it.

- `NONE`: direct read compatibility is not promised; a registered migration or
  rejection is required.

Schema rules may declare additive optional fields, removed fields, renamed
fields, and canonical defaults. Additive optional fields are backward-compatible
when old payloads remain valid under the new reader. Field removal and rename
are not silently compatible; they require either explicit dual-read aliases or a
migration edge. Unknown canonical `_type` values remain fail-closed per
ADR-0104. Canonical defaults must be listed when a reader stamps or normalizes a
missing version/default field.

`negotiate_schema_version(artifact, producer_version, consumer_version)` is the
rule-based API for release review and migration planning. It reports whether a
payload can be read directly, whether migration is required, the compatibility
mode involved, and a stable reason code.

## Consequences

`TransportabilityResult`, `HTEResult`, literature extraction contracts,
actual-causality contracts, and mediation contracts have predictable assignment
semantics: report fields cannot be rewritten after validation. Derived fields
are produced through explicit normalizers/factories and therefore appear
consistently on construction, model copy, and JSON re-parse.

Schema evolution now has an executable policy surface. Release review can ask
whether a new consumer can read an old payload, whether an old consumer can read
a new payload, and whether a migration edge is required, without inferring that
answer from snapshots alone.
