# OPS-R5 Amendment — Factored But Constrained E/X/V/C State Product

Audit defect: `audits/int-r4-ops-r5/int-r4-ops-r5-independent-audit.md:112`.  
Disposition owner: `ops-r5/amendment-ledger.md`, `AUD-F06`.

The four coordinates are retained because they answer different questions. The word `orthogonal` and
any implication of a freely reachable Cartesian product are superseded. The amended model is **factored
but constrained**.

## State And History Predicates

```text
State = (E, X, V, C)

StateInvariant(E, X, V, C, history, authority) :=
    axes_are_well_typed
AND state_has_content_bound_contract_and_claim_objects
AND version_claim_compatibility_holds
AND exposure_restart_compatibility_holds
AND terminal_state_claim_consistency_holds
AND any_external_continuation_has_independent_basis
AND every_required_co_transition_is_recorded
AND no_forbidden_tuple_holds
```

```text
AllowedTransition(old_state, event, evidence, authority) :=
    StateInvariant(old_state, history, authority)
AND event_identity_and_order_are_admitted
AND evidence_satisfies_the_named_transition_charter
AND authority_is_competent_for_every_changed_axis
AND requested_new_state_satisfies_StateInvariant
AND required_co_transitions_are_in_the_same_decision_or_linked_transaction
AND duplicate_or_replay_cannot_repeat_an_irreversible_effect
AND legal_and_review_clocks_are_satisfied
AND protected_restart_or_expansion_has_fresh_restart_evidence
```

`authority` is an evidence reference to a competent grant, not an owner/team label. The predicate
specifies what later implementation must verify; it does not appoint the authority.

## Required Forbidden Tuples And Reverse Case

### FCT-01 — Material reissue cannot retain intact confirmation by default

```text
V == V2_patched_or_reissued
AND C == C0_confirmatory_intact
AND valid_equivalence_evidence == false
→ forbidden
```

Required co-transition: a material `V2` change moves the affected claim to `C1_under_review`,
`C2_exploratory_only` or `C3_withdrawn`. `C0` survives only for an unaffected claim object or after an
admitted equivalence proof.

### FCT-02 — Confirmed unacceptable termination cannot retain the same intact positive claim

```text
E == E4_confirmed_unacceptable
AND X == X4_terminated
AND C == C0_confirmatory_intact
AND claim_object_depends_on_the_unacceptable_basis
→ forbidden
```

A historical proposition unrelated to the unacceptable basis may remain separately versioned; the
same operative positive claim cannot.

### FCT-03 — Rollback cannot reopen full exposure without restart evidence

```text
V == V4_rolled_back
AND X == X0_full
AND valid_restart_evidence == false
→ forbidden
```

Required co-transition: remain `X3_paused`, `X2_narrowed` or `X1_no_expansion` until repair identity,
measurement health, bounded probe, residual-risk review and renewed authority are admitted.

### FCT-04 — Claim withdrawal does not mechanically terminate an externally grounded policy

The following implication is explicitly false:

```text
C == C3_withdrawn  ↛  X == X4_terminated
```

An external policy may continue under a separate legal, protective or emergency basis. The state must
record that independent basis and must close every action path that depended on the withdrawn causal
claim. Conversely, termination does not automatically erase a historically valid causal claim.

## Additional Cross-Axis Invariants

- `C0_confirmatory_intact` identifies an exact claim, population, intervention version and measurement
  epoch; it is not a global green state.
- `E2_credible_anomaly` or `diagnosis_unresolved` may coexist with `X1`, `X2` or `X3` where a
  preauthorized protective envelope permits action before full diagnosis.
- `X4_terminated` is terminal for the named authorization, not necessarily for all related observation,
  remediation, restitution or historical-claim work.
- `V3_redesigned` starts a new causal object and cannot inherit `C0` from the prior design.
- `C3_withdrawn` blocks claim-dependent learning, publication and action gates even when exposure
  continues for another independently evidenced reason.
- A state change on one axis cannot silently be inferred from another. Every co-transition carries its
  own evidence and authority basis.

## Mutation Obligations

A later fixture suite must hold three coordinates fixed and attempt an illegal fourth, at minimum for
FCT-01 through FCT-03. It must also test FCT-04 in both directions:

1. causal claim withdrawn, external policy continues under a valid separate basis;
2. causal claim withdrawn, no separate basis exists, claim-dependent continuation is denied.

No such executable state engine or mutation suite exists at this stage; capability standing remains
`absent/unallocated`.
