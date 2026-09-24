# ADR-0176: Epoch validity transition admission predicates

## Status

Accepted

## Date

2026-09-13

## Context

The epoch positive path is now built. A lane established, and this architect
verified in the merged source, that `EpochValidityTransitionProducer` previously
resolved history, built a transition, had it signed, read back its exact persisted
bytes, verified them against the canonical transition — and then refused anyway,
with a comment saying why: *the exact signed bytes still cannot appoint their own
producer identity*. That refusal was deliberate and correct. ADR-0176 does not
revisit it; `producer_identity_ref` now carries provenance from the canonical
producer, sealed from the actual completed execution and resolved independently
against artifact, signature, profile, purpose and query, beside an unchanged
`signer_provenance_ref`.

Three admission predicates remained undecided, and the lane stopped at each rather
than guessing. Each is a semantic choice, not an institutional appointment: under
every reading below the institutional slot stays typed and empty. Prose in the
lane's Stage 1 record is not enough, because each changes what a consumer may
admit — cross-component contract semantics, which the Policy Design Case decision
log explicitly directs to be promoted to an ADR rather than logged.

## Decision

1. **Same-epoch transitions are admissible.** `EpochValidityTransitionArtifact._bind_transition`
   rejects `previous_epoch_ref == current_epoch_ref` with no stated purpose. Its
   two sibling invariants already carry the anti-replay property: the target
   vector and dependency graph denominators must agree, and
   `transition_content_hash` must equal the semantic hash of the whole model, so
   two transitions cannot be confused. The distinct-epoch rule is therefore
   strictly stronger than the other invariants require, and it contradicts GY-N12
   Task 4.4, which requires a transition when an owner disposition changed and
   the semantic epoch did not. The model-level predicate becomes **distinct
   epochs, or a declared same-epoch adjudication delta**; the producer, not the
   model, enforces that the declared delta is independently admitted. Strictness
   moves to the layer that can verify it rather than being approximated by a
   proxy the model can see.

2. **The qualified pre-N9 query carrier is extended to admit a positive result.**
   `NativeChronologyQualified` keeps its query at
   `reconciliation.owner_context.query`, while
   `PersistedEpochPromotionQueryStatement._query_is_derived_from_owner_fields`
   reads `getattr(result, "query", None)` and refuses it, and
   `_PersistedNegativeEpochQueryOwner.resolve_for_promotion` requires the failure
   type by construction. The extension reads the query from the qualified
   reconciliation. **Every existing predicate is preserved verbatim** — exact
   equality, persisted proof readback, subject/candidate/query binding, completed
   batch verification — and an unverified qualified marker is not accepted; the
   `current` prior-binding refusal and the superseded-successor refusal remain.
   **The carrier is renamed, or gains a positive sibling.** A class named
   `_PersistedNegativeEpochQueryOwner` that carries a positive result is the
   naming form of exactly the defect this work exists to remove, and leaving the
   name would re-teach the next reader the thing we just spent a week unlearning.

3. **`AdvisoryPerturbationEvent.source_class` gains `semantic_basis_change`.**
   Its current arms are incident, appeal, correction, retraction, legal change and
   discovered bias; none of them means *the native semantic basis of an issued
   certificate changed*, which CB-C03A/D01/D02 require revalidation for.
   Serialising that change as `correction` would assert something the evidence
   does not say — the subject of the Wave-5 non-substitution act. The new arm
   carries the exact old and new basis and the owner dependency binding. This is
   **not** a constitutional §8 trigger: a new source class inside an existing
   event type is not a third kind of outcome beside a grounded claim, an honest
   refusal and custody without a number.

4. **An empty monitor inventory is never evidence that native semantics are
   unchanged.** Stated here because the producing lane stated it and it is the
   disclosure rule applied to this contract: absence of an observation is not an
   observation of absence.

## Consequences

Positive: the epoch positive path can be completed without any appointment; the
Task 4.4 case stops being unreachable; a genuinely qualified result can reach the
carrier that decides promotion; and a semantic-basis change becomes reportable as
itself rather than as a nearby label.

Negative and accepted: decision 1 moves a check from a place that could enforce
it cheaply to a place that must do real work, so the producer's admission path
grows a failure mode the model previously made impossible. Decision 2 widens a
consumer, which is the class of change most likely to be got wrong; it is bounded
by requiring every existing predicate to survive unchanged and by a removal probe
per predicate. Decision 3 adds an enum arm to a contract consumers switch on, so
every exhaustive consumer must be revisited; an unhandled arm must refuse, never
default.

## Concrete impact

- `src/polisyos/runtime/quality/epoch_validity_cascade.py` — `_bind_transition`
  predicate; the producer's same-epoch delta admission.
- `PersistedEpochPromotionQueryStatement._query_is_derived_from_owner_fields` and
  `_PersistedNegativeEpochQueryOwner` — extension and rename/sibling.
- `AdvisoryPerturbationEvent.source_class` and every exhaustive consumer of it.
- Each change carries a remove-the-property-keep-the-markers probe: deleting the
  guarded property while retaining its markers must make the original negative
  fail again.

## Related Decisions

- Related: ADR-0175. Binds under `W5` non-substitution and the 2026-08-30 ruling
  that institutional absence never blocks building.
- The alternative reading of `producer_identity_ref` is withheld, not refused:
  `withheld-propositions-register.md`, `WP-14`.
