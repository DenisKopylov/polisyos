# ADR-048: Native value projection is a two-sided output-contract capability

## Status

Approved

## Date

2026-07-13

## Context

The GY-N10 value-method advisor classified methods from names, namespaces,
families, tags, and free-form catalog text.  A live census found that this
admitted 275 of 390 registered methods, while only 70 signatures expose a
contracted native result type capable of projecting uncertainty.  The 205
false positives included diagnostics such as Hausman tests.  This violated the
Foundry output-contract law: a report owner, not a family label, owns the
semantics needed to project value evidence.

A slot-only marker or runtime callable check would still be trust-by-form.  The
selection denominator needs a typed, content-hashed declaration before a
method runs, while the projector must verify the resolved native result after
execution.  Neither side alone is authority.

## Decision

1. `OutputContractDeclaration` in `polisyos.ir.analytics.uncertainty` is the
   canonical native-output declaration.  The typed
   `VALUE_UNCERTAINTY_PROJECTION` capability means that the owner implements
   estimand-aware `to_value_uncertainty(*, estimand)` semantics.
2. `SlotSpec` carries a default-empty typed contract-capability witness.
   `SlotSpec.for_output_contract(...)` derives the contract ID and capabilities
   from the native owner; callers may not infer them from names or tags.
3. The content-addressed Foundry catalog serializes the witnessed capability.
   The value advisor denominator derives exclusively from verified output
   declarations.  Domain names, method FQNs, method families, and output-slot
   spellings are not selection authority.
4. `MethodValueEvidence` verifies both sides before projection: the selected
   slot witness and the resolved native result owner's declaration must match
   the same contract ID and capability.  Projection then calls only the
   uniform estimand-aware owner method.
5. Legacy slots remain valid with an empty capability witness.  Their existing
   ABI digest stays stable.  Only explicitly migrated capable signatures
   receive a new digest and catalog identity.

## Consequences

The advisor can no longer select diagnostics merely because their vocabulary
looks value-related.  A new domain or method family becomes reachable by
declaring a capable native output contract, without an engine enum or FQN
branch.  Forged slot markers and shaped callables still fail closed because the
projector checks the native owner declaration and exact contract identity.

Native owners using the older `to_uncertainty_envelope` convention need thin
estimand-aware wrappers before their slots can be migrated.  Persisted method
catalog and N8 selection receipts for migrated methods must be regenerated
through their canonical writers.  Contracts that cannot bind an estimand stay
outside the denominator until their owner gains honest semantics.

## Concrete impact

- `src/polisyos/ir/analytics/uncertainty.py` owns the declaration vocabulary.
- `src/polisyos/foundry/methods/base.py` owns the ABI witness and constructor.
- Native posterior, econometric, forecasting, distributional,
  partial-identification, and transport contracts declare their capability.
- `src/polisyos/foundry/methods/catalog/snapshot.py` content-binds declarations.
- `src/polisyos/foundry/methods/selection/advisor.py` removes the token
  classifier from the value denominator.
- `src/polisyos/foundry/methods/components/value_evidence.py` enforces the
  two-sided check and the uniform projector contract.
- GY-N10 tests cover diagnostic exclusion, forged declarations, the six native
  families, and an unseen third-domain contract owner.

## Related Decisions

- Related: GY-N10 Rev-16 Fork B in
  `docs/superpowers/plans/2026-07-10-depth-n-universality.md`.
- Related: P27 (single owner), P29 (behavioral verification), P31 (class fix),
  and P32 (no trust-by-form) in the policy-design failure register.
