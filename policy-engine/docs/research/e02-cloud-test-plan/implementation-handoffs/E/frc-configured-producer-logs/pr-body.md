## Summary

A configured ETS forecast owner now emits observed heldout pairs, separate empirical evidence, and a separate content-bound candidate receipt through the same CAS. The fresh receipt loader replays source positions, ordered pairs, train/holdout/horizon, method/rule, times, seed and threshold; a changed configured request is rejected before the numerical callback.

Candidate receipts preserve predictive-only scope and `verifier_provenance=not_established`. A owns trusted profile admission, the independent verifier, default generation-cycle bridge, and served POST/persist/GET readback. This change grants no causal, treatment or S10 authority and closes no finding by itself.

## Change Categories

- [x] runtime behavior
- [x] contract / schema (internal candidate artifact only)
- [x] docs

## Compatibility Classification

- [x] internal

## Labels and Ownership

- [x] `kind:runtime-behavior`, `compat:internal`, `release:fix`
- Owned areas: E ForecastOwner/ETS and calibration.forecast_bridge.
- Migration owner: A for default runtime wiring and independent verifier; E for this producer.
- Review owner: independent E review assigned by root; G integration review.

## Validation

- Registered NumPy ETS backend, 5 focused tests passed in 13.52s.
- Same forecasts with changed holdout outcomes give 4/4 versus 0/4 and different persisted evidence.
- Fresh CAS consumers reject schema-valid/hash-valid false counts and a switched source request.
- Removing source/pair replay makes the forgery negative fail, despite retained receipt/schema markers.
- Ruff check and format passed. Native FRC consumer suite on implementation SHA `5bd27323ecb0935a38908d2b09fa652762c5e4ea`: 61 passed in 31.72s. Independent root review: 19 passed, 2 FRC-01 failures remain on the A reader path; isolated E producer scope accepted with explicit limits. Complete outputs are committed in the handoff.
- FRC-01 replay on literal slice base reproduced 2 failures/5 passes. Attribution remains `not_established` under P41 because changed bridge paths intersect its importer inputs.

## Rollout Checklist

- [x] Internal artifact schemas have distinct kinds; empirical v1.0/v1.1 remains unchanged.
- [x] Existing unconfigured owner path remains supported.
- [x] Internal README and release fragment describe configuration and authority limits.
- [ ] A default served bridge and trusted verifier are implemented and tested.
- [ ] Independent reviews and frozen combined E wave complete.

Pattern pass: P01/P02/P05/P08/P10/P14/P27/P29/P31–P33/P35/P37/P38/P40/P41. Configuration admission is consumer_asserted until A trusted composition; source/pair/counter integrity is recomputed. Nominal coverage remains descriptive and does not stand in for measured coverage.
