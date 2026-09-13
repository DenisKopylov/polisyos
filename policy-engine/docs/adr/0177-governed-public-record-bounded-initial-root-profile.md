# ADR-0177: The governed public record admits a bounded initial-root profile

## Status

Accepted

## Date

2026-09-13

## Context

The governed public record now has an admission half. Before it existed, three
`promoted_record: Literal[None]` anchors and their consumers could express a
refusal and nothing else; a single-value literal cannot carry a record. The
refusal half is untouched and still reachable — this ADR is about what the new
positive half is permitted to claim.

While building it, the lane found that later epoch heads lack a complete
historical replay of their evidence and their reducer. It therefore admits only
the initial root snapshot whose owner can verify it, and refuses later heads
explicitly rather than publishing what it cannot reconstruct. It also reproduced
the counterexample that forced the limit: changing the linked ledger and the
bridge result together let an assertion pass that the epoch reducer had never
produced.

The lane asked whether that bound is acceptable. It is a question about public
evidence semantics, which the decision log directs to an ADR.

## Decision

1. **The bounded initial-root profile is accepted.** The governed public record
   admits the root snapshot its owner can verify and **refuses later heads by
   name**. A declared limit that refuses is the correct shape; silent partial
   coverage is not. The refused class is registered as its own debt so the bound
   is visible as owed work rather than as a property of the design.

2. **The admitted proposition is bounded to custody and says so.** It asserts
   that the configured issuer issued this exact public record of these
   owner-admitted assertions and statuses, at the stated publication time, for
   the declared bounded custody purpose. It asserts nothing about firstness,
   complete public history, current policy authority, or policy performance.
   This is the `INT-K06` custody family, not a fourth kind of outcome.

3. **Grounded performance remains a separate obligation.** A custody record may
   not close `DS11-GROUNDED-PERFORMANCE` by implication. Accepting a bounded
   custody assertion as evidence of policy performance would substitute one kind
   of evidence for another, which the Wave-5 act forbids. The row stays open and
   keeps its own producer and publication consumer.

4. **The publication signing slot stays typed and empty in production.**
   Possessing a signing key does not appoint its holder; appointing a publisher
   later is configuration plus external authorization evidence, not a new type
   and not a rewrite of the consumer.

5. **The two `ds8` rows are not adjudicated by building.** Both turn on slice
   scope. They are reconciled in the register by the architect; a lane that
   builds toward them has misread them.

## Consequences

Positive: a real public record can be issued, verified anonymously, rendered and
consumed by custody, with its limitations carried into the viewer rather than
dropped at the projection boundary. The bound is stated where a reader meets it.

Negative and accepted: the published population is smaller than the eventual one,
and any consumer that treats the admitted set as complete public history is
wrong. The refusal for later heads must therefore be loud and named, not an
empty result — an unreadable or unreplayable head is ambiguous, never absent.

## Concrete impact

- `src/polisyos/scientist/governance/continuous/governed_public_record*.py` —
  the admission owner, its projection and the bounded profile's refusal arm.
- `src/polisyos/runtime/http/routes/public_decisions.py` — the positive response
  branch beside the unchanged `promoted_record: Literal[None]` report response.
- `PublicationSigningSlot` — empty default retained.
- The refused later-head class gets a register row; so does the separate
  performance obligation, which already has one.

## Related Decisions

- Binds under `INT-K06`, the `PV-K01..K09` projection acts, and `W5`
  non-substitution. Related: ADR-0176.
