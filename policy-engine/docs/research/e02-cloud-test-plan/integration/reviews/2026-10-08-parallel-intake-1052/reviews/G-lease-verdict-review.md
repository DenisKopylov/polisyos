# G 1052 continuation lease delta review

Read-only review of the draft `integration/reviews/2026-10-08-parallel-intake-1052/{README.md,verdict.json,continuation-leases.json}` against entry G `d23ea5e9dd252214fc9e0c5c941a8a3789cead0a`, current dispatch, and E ownership. No source/test review reruns or modifications were made.

## Finding

No same-file ownership collision or product-scope overclaim found. The B190 decision remains **limited**, with `consumer_missing` / `implemented_but_not_orchestrated` and no formal closure. The ORCH03 interval source remains HOLD. The draft correctly separates supplier acceptance from finding closure, leaves C11 assembly/registration, C07 IR, C10 served/S10, and G generated/global artifacts with their owners, and keeps G as sole publisher.

`continuation-leases.json` pins the dispatch blob to `f2e8d2096b86148fb93d4eb61520d22002228a1d`, which is the dispatch blob at entry G. The six `exact_additional_targets` are unique and do not match a competing role’s source path: the three B190 Node/test paths and three interval helper/README/test paths are explicitly named in the supplement. The source scopes also leave C07 IR, C08 graph/method, C10 served/runtime, C11 assembly, and G generated families separate. E remains the assigned B190 finding owner (UQP-01), and the new Node work is an exact C09/E continuation lease, not a new node, registry, or authority issuer.

The interval lease has 17 unique exact paths. It retains the prior C09 backtesting/forecast/governance paths, explicitly adds the canonical calibration helper/README/test, and now includes the existing `test_evaluator_interval_admission.py` path as C09-owned. That resolves the prior path-list omission. The Node bridge adds only `propagate_uncertainty.py` and its two mirrored tests to the existing E/C09 B190 writer. The `existing_write_paths` remain the accepted supplier’s paths; no supplier reimplementation is proposed.

## Scope and wording

The additional canonical calibration and Node paths are outside the current `dispatch.json#/roles/C09.source_scopes`. The supplement explicitly grants them and checks all 15 roles for conflicts, so this is a bounded, intentional path-level extension and preserves E’s original semantic ownership. To avoid conflict with C09.md’s statement that dispatch source scopes are an upper boundary, add one short sentence in the README or lease clarifying that this continuation lease is the **only exact-path supplement** for these named files; it does not widen C09’s standing scope or authorize adjacent files. This is a clarity fix, not evidence of a competing owner.

The interval property remains precise: recompute one basis from actual rows/bounds/hits/full requested denominator and preserve its limitation through named consumers; `report.degraded` alone is not the gate. The B190 property is likewise bounded to the existing Node’s source/target/axes/units/config binding, recomputation, addressed unknowns, and persisted/fresh-read outputs. Positive and partial/refusal/counterfeit/removal controls are required before acceptance. Neither lane infers covariance/noise authority from Fisher rank, changes B172/B173, nor claims the bridge now passes.

## Handoff boundary

The resume contract is correct: use the existing matching cloud lane, take a fresh exact branch/path snapshot on that host immediately before mutation, then read back attachment/HEAD/status. The G-side receipt is not a cloud admission and does not reserve a name or path. No new checkout, history rewrite, or publication to `main` is authorized.

**Recommendation:** publish after the one-sentence exact-supplement clarification. Otherwise the lease split, owner boundaries, conditional status, and required evidence are implementable without another full source/test review.
