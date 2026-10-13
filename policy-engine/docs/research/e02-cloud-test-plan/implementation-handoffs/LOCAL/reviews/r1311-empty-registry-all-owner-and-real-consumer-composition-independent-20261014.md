# R1311 — Independent review of explicit-empty MethodRegistry handling

**Verdict:** GO on source semantics. Candidate composition is blocked by one newly introduced Ruff formatting failure. Runtime/native acceptance remains UNRUN.

## Binding and scope

Reviewed the immutable R1283 candidate at `raw/r1283-joint-simulation-registry-order-and-typed-refusal-successor-20261014/candidate.patch` (SHA-256 `7cabf6f097b5231aedf677f74ceec20ccb955b332712e2a844c7c3dee14f252d`) and its manifest (SHA-256 `9258f7de83e535823ed33df7fbe8e1545c4e8752f034c0b6d33bb258d5212d57`). The candidate declares original base `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`; the receipt-only source advance is now HEAD `a02f4f8920c60e02e745ba91bbed9ab9524fcbe7`. Current source qualification is frame `root-author-source-frame-r1306-r2-20261014.json` (SHA-256 `cf7bbc6d742ace36a33cb1077dbbeb2effc377da7ef723e3d7bf8d2864dc9d92`), whose source tree retains the same candidate baseline bytes. All 14 declared candidate preimages matched the current files, and `git apply --check` succeeded.

## Whole-class source review

A read-only stdlib AST census at `raw/r1311-methodregistry-census-20261014/census.py` (result `census.json`, SHA-256 `6bbc6a27ee5eef8ef7b12195a1a329ae415628a708014fdd4aa3be820ff5441e`) walked all tracked `policy-engine/src` Python sources: 2,761 `.py` plus 5 `.pyi` files, with zero parse errors. It classified 25 registry-shaped `or` nodes: all 18 actual `MethodRegistry` object-fallback sinks across 12 source files are in the candidate; the remaining nodes are four `PluginRegistry` defaults, two callable-provider defaults, and one non-fallback canonical-controller validation condition. The four PluginRegistry instances have no `__len__`/`__bool__` implementation in the reviewed source. The validation condition checks controller identity and policy, rather than selecting a default. The cycle module’s nested callable-provider choice is also rewritten as an explicit `None` check; execution-plan’s separate callable default remains outside the MethodRegistry-object repair.

`MethodRegistry.__len__` makes an empty instance falsey, so the former `registry or default` expressions discarded a deliberately supplied empty registry. The candidate consistently changes all 18 object-selection sites to use the supplied object whenever it is not `None`; only `None` selects the existing default. It does not add truthiness methods, alter the registry API, change public exports, or change authority/schema semantics. In the cycle bridge, explicit registry selection precedes provider invocation, so deferred provider lookup is retained and skipped for any supplied registry, including an empty one.

The behavior controls exercise both relevant sides. The new composer test puts a method only in the singleton fallback and proves that an explicitly empty registry still refuses the lookup. The joint-simulation fallback test supplies a fresh empty registry, requires the real system-dynamics method to be registered there, executes the compatible candidate, persists the result, and verifies it through a fresh CAS reader. The revised candidate-order tests preserve ordered refusals and verify the no-trajectory result remains rejected by the fresh numerical reader. These controls would fail if the corresponding candidate truthiness behavior were restored; this is source/test-structure inference, not an executed removal probe.

The one-replication assertion change is consistent with the source contract: `checked_interaction_orders` records complete scope coverage, while the result continues to carry `standard_error_not_estimated`, `interaction_sampling_not_established`, and the related authority blockers. It does not turn a one-replication simulation into inferential evidence.

## Finding

**Low severity — formatting blocks composition, not source semantics.** The candidate manifest reports `ruff_check: pass` for `tests/unit/foundry/methods/test_composer.py`, but its formatter record is baseline exit 0 and candidate exit 1. This is a new formatting failure in the added test companion. Format that companion and regenerate/re-hash the candidate before composition.

## Residual verification boundary

This reviewer did not run pytest, import product modules, or run native tests. The required R1283 selector remains for the root native lane; no runtime acceptance or original criterion closure is claimed. The new negative test exercises singleton fallback, while no new control explicitly combines a `registry_scope()` context-local ambient registry with a distinct supplied empty registry through a `get_registry()`-based consumer. The corrected source condition covers that route by inspection; if context-local isolation is a required independent acceptance signal, add that focused control before calling the ambient behavior fully exercised.

P40 classification: same-class deeper falsey-fallback defect, widened to the 18-site MethodRegistry fallback quantity. P29/P33 controls use actual consumer behavior and ordered/refusal cases. `closure_ids: []`.
