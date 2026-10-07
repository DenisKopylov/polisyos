# D resume/history runtime review — a795

**Verdict: bounded GO for the consumed-history admission property at the pinned candidate.** I found no current counterexample in the reviewed service/CAS path. This does not close B125 or the LA criteria, establish a production/default caller, or constitute G code acceptance.

## Pinned scope and identity

The closeout at D head `cbc46a0bc87761bc2267a0daa84da489d6702e89` (tree `3e05fcf727bf660a5570225b9600ca410a7082be`) binds this slice to candidate `a795967a80818a61fbc939a8d1b1ec8b0fca6477` (tree `2cd7e7058eeb0431b0571b30af3ad80b9a3c2668`) and production implementation `3b31e136e5ccf9ee17ecb112e1f902cb0f95b0d2` (tree `d5c3a5a797a4f74b5da4c30fdd0a03cf2b3135c4`). The candidate descends from the production SHA. Its only delta from that SHA is `tests/unit/scientist/methods/search/test_service_persistence.py`: the owned `_CheckpointBatch` fixture now saves and validates its complete corpus and cursor. It adds no production guard or exception. Blob identities for the reviewed runtime paths (`search/service.py`, `search/run_state.py`, `search/strategies/adapter.py`, `autotune/bayesian_generator.py`, and `search/sensitivity_adapter.py`) are byte-identical at `3b31` and `a795`; `test_service_history_binding.py` is also unchanged.

This review is bound to the original B125@CTL-02 acceptance text (“full persisted round-trip,” matching next sequence, reject damaged/foreign state, independent random stream) and its four mapped occurrences: B125@CTL-02, LA-014@SRV-01, LA-015@CTL-01 (supplier companion only), and LA-015@SRV-03. It covers the history-consumption part of that contract, not the entire original acceptance set.

## Runtime path and evidence

`NativeSearchService.restore()` reads one verified CAS snapshot, decodes and validates the full typed run state and pending state, checks candidate identity, and calls `validate_checkpoint_history(state.history, generator_state)` before calling `set_state()` or installing the restored run ledger. For an overridden strategy `update`, `StrategyAdapter` requires the actual owner’s `validate_consumed_history`; it checks row count/digests and that owner state against the saved rows before delegating restore. Built-in wrappers additionally restrict checkpoint admission to the exact canonical callable owner. Unsupported stateful/custom profiles stay live but refuse persisted resume.

The key example is a real `SearchLoopRunner` factory → `FileSystemCAS` checkpoint → fresh service restore. The deterministic owner consumes `[1, 2]` from service history `[1, 2, 4]`; the final `4` is a legitimate unconsumed tail. Uninterrupted and fresh next proposal both equal the independent update-law result `1 + sum([1, 2, 4]) = 8`, with no evaluator call during restore. The test checks the actual strategy state and CAS bytes, not only a digest marker.

The committed JUnit and receipt identify distinct exact-candidate scopes; these counts are not additive with other D receipts:

- `new31`: 31 PASS, 0 FAIL/ERROR/SKIP at `a795`.
- `affected22`: 22 PASS, 0 FAIL/ERROR/SKIP at `a795` after the fixture-only repair.
- `consumption-removal1`: one expected assertion failure under a removal plugin, not a current implementation failure.

The 31-case matrix includes empty/truncated digest bindings; count/digest/corpus truncation; changed corpus and changed service-history content; invalid/missing counts; zero-consumed initial state; unsupported stateful profiles; and borrowed/overridden built-in owners. The zero-consumed empty rows/digests case is valid; it is distinct from erasing evidence for a nonzero consumed prefix. The 22-case affected run covers the corrected batch fixture, grid adapter resume/config changes, history-prefix tampering, and composed write/readback failure paths. The historical `3b31` affected run had a fixture-owned refusal (36 PASS/1 FAIL); that red is not presented as a production defect or as a full-suite retest. The exact a795 fixture patch supplies the missing pure corpus/cursor contract and the selected a795 run passes.

The removal probe keeps CAS, schema/config, count/row/digest shape, history, and RNG/state path while removing only `StrategyAdapter._validate_strategy_consumption`. It shortens the outer consumed count/rows/digests to one but leaves inner owner state `[1, 2]`. Fresh restore then accepts the inconsistent state, skips `1`, replays `2, 4`, and proposes `10` instead of `8`. The recorded call-phase assertion failure is the expected falsifier; it demonstrates that current green depends on the owner-state/history relation rather than the markers alone.

## Predicate and residuals

- **P37:** `consumer_asserted` for the generic owner’s hidden update-state/history relation: the service delegates that relation to each supported owner’s validator and refuses opaque stateful owners without one. In the concrete accumulator witness, the independent expected next value and the corrupted-state counterfactual reconcile that assertion for the tested owner.
- **P38:** the implementation checks actual consumed rows against current service history and owner state before restore. The named divergence is the removal case above (10 vs 8); the current code rejects that inconsistent owner state.
- **Boundaries:** the owner validator remains a trusted contract for arbitrary custom strategies; this is not a defense against arbitrary Python monkeypatching or a signature over republished state. The deterministic accumulator is a generic protocol witness, not production scientific evidence. NN direct warm-state/update-owned history remains unsupported for persisted Adapter resume; numerical GP behavior, served/default caller identity, production evaluator/history truth, and independent RNG guarantee over every supported profile are separate criteria/receipts. Full 17,350-path input/origin inventory is preserved only in ignored local raw material, not Git; therefore P41 and full-input portability remain `not_established` here. No finding closure or G acceptance is inferred.

I did not run tests, install dependencies, or write source/ref changes; this is a read-only review of the pinned code and committed receipts. The 31/22 executions are credited only to their committed a795 receipts, not as fresh runs by this reviewer.
