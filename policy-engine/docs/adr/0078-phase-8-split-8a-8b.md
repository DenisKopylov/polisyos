# ADR-0078: Phase 8 split into 8A + 8B; TransportabilityRequiredPass moved to end of Phase 12

## Status
Proposed

## Date
2026-02-28

## Context
Phase 8 currently bundles two conceptually distinct concerns: (8A) constructing the
transportability diagram by annotating S-nodes for domain differences, and (8B)
checking whether the target causal effect is transportable and aborting if it is not.
The gating check (8B) fires before Phase 12 identification, which means it uses a
heuristic rather than formal s-ID. This causes false negatives: effects that are
formally transportable via do-calculus get rejected by the conservative heuristic.
Moving the hard gate to after Phase 12 identification lets us use the actual s-ID
result.

## Decision
1. Split Phase 8 into Phase 8A ("Build Transportability Diagram") and Phase 8B
   ("Annotate S-nodes and Domain Metadata").
2. Remove `TransportabilityRequiredPass` from its current position in the governance
   pipeline (post-Phase 8).
3. Re-register `TransportabilityRequiredPass` as a post-Phase 12 governance pass,
   after `y0.s_identify` has returned a definitive identification result.
4. Phase 8A/8B become pure annotation steps with no gating behaviour; they always
   succeed and attach metadata to the `CausalGraphModel`.
5. Update the `causal_full` workflow definition and the default workflow builder to
   reflect the new phase ordering.

## Consequences
### Positive
- Eliminates false-negative transportability rejections caused by the heuristic gate.
- Separates annotation (always useful) from gating (context-dependent).
- Post-Phase-12 gate uses formal s-ID, providing a mathematically sound accept/reject.
### Negative
- Phases 9-12 now execute even for non-transportable effects, consuming compute before
  the gate fires. Mitigated by the resolution loop's early-exit on obvious failures.
- Existing tests that assert Phase 8 gating behaviour must be rewritten.
- Workflow versioning: pipelines serialised with the old phase numbering need a
  migration path.
