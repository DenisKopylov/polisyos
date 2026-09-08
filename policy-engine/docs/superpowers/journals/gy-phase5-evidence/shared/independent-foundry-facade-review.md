# Independent Foundry facade delta review — 2026-09-08

No findings in this bounded D4 review. **Approve the Foundry facade exports, existing-owner imports and same-owner reentrancy correction for final integration.** D3f remains outside this review.

## Specification and owner placement

`polisyos.foundry` exports `MethodRouteConstraint` and `method_accepts_input_contract` through its existing lazy map, type-checking imports and public export list. Each points to the existing selection owner; no wrapper, second class, nested manifest parser or second input-contract predicate is introduced. S3's new corresponding imports in `intervention_substrate.py` and the route-constraint annotation in `generation_cycle.py` use that facade. Existing unrelated imports and completed owner algorithms are outside this correction.

`test_route_constraint_facade_reuses_actual_input_contract_owner` resolves the actual facade exports and compares object identity with the existing advisor owner. It then calls that same predicate with the actual survival estimator's real input contract and a nonexistent contract, establishing both substantive acceptance and refusal. This is more than testing names in `__all__`.

## Reentrant locking is required by an observed import path

The existing `_resolve_lazy_export` holds its owner lock across module import and attribute resolution, and acquires that lock before even reading its resolved-object cache. `d4-facade-python-stack.json` records an actual cold facade import, interrupted after 120 seconds with the complete Python stack. The chain begins at `MethodRouteConstraint`, imports the selection advisor and catalogue, reaches policy `frontier.py`, and reenters the same Foundry facade for its existing embedder exports. It stops at the second `_RESOLVE_LOCK` acquisition on the same thread. Thus the initial apparent slow import was a concrete nonreentrant-lock deadlock, not a reason to enlarge the timeout indefinitely.

Changing this single existing `threading.Lock` to `threading.RLock` preserves the serialized shared cache and exact owner lookup while allowing the observed same-thread nested export. It does not move imports outside synchronization or create a parallel resolver. No authority/receipt epoch or routing semantics change follows from that synchronization correction.

The finite regression runs in a separate process, warms real owner objects before timing synchronization, and makes the actual lazy resolver reenter itself through its import callback. The normal resolver must return the exact `advisor.MethodRouteConstraint` object. Replacing only the lock with a nonreentrant lock must hit the two-second synchronization timer. The child prints its success marker only after those behavioral assertions; the parent imposes a finite process budget. The altered lock/import callback cannot leak into other tests because the probe runs in its own process. This is a bounded reproduction of the observed mechanism, not a claim about every hypothetical cross-thread import topology.

## Evidence readback and scope

Complete commands/outputs were read in the S3 evidence records:

- `d4-facade-red.json`: missing actual facade export, RC 1, 2.996 seconds.
- `d4-facade-green.json`: the initial attempt was interrupted at the lock, RC 2; its name does not make it a green receipt.
- `d4-facade-python-stack.json`: complete actual recursive import stack, RC 1, 120.692 seconds, identifies the second same-owner acquisition.
- `d4-reentry-red.json`: finite regression before repair, RC 1, 27.785 seconds, explicit `same_owner_lazy_reentry_deadlocked` at the real resolver.
- `d4-facade-final.json`: actual identity/contract behavior and finite reentry/removal tests, RC 0, 52.767 seconds.
- `d4-facade-final-ruff.json`: facade, S3 importer source and mirrored test Ruff, RC 0, 0.059 seconds.

P40 disposition: this completes the already named D4 public-owner/facade boundary. The observed same-owner liveness failure is its concrete nested-import consequence; this review finds no further new class or deeper escape requiring another repair round. No recursive verifier or unrelated facade redesign is requested. This reviewer made no product edits, ran no tests/generator/report, and touched no composed-WMR scratch. Root owns current S3 report regeneration and final common guardrails.
