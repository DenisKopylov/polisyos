# B model-scope local check (d18fe09)

## Result

The exact d18fe09b5bc0367c966011144a5418f836b9a4b7 candidate has a real ordinary BaseModel write-scope escape through Pydantic assignment validation. With only params.holder.count granted, an admitted validate_assignment=True model's after-validator changed the ungranted sibling tag from stable to changed-by-validator. The mutation journal contained only params.holder.count; the branch changed and the base stayed unchanged. This is a direct runtime counterexample to the scope property, not evidence of a persisted external effect.

The two authorized deletion controls behaved as claimed: deleting root reports_index or nested model field count raised TypeError("model field deletion is not replayable") before state or journal changes. The exact README declares RootModel supported; a real RootModel[dict[str, int]] was admitted, a granted root.count mutation was journaled, and an ungranted sibling mutation was refused before changing state.

## Existing tests

The final exact-source pytest wave collected and ran 67 cases in 14.386 s: 52 passed, 15 failed, 0 skipped, 0 collection errors. test_state_branching.py passed 8/8. test_producer_scope_reconciliation.py passed 44/59.

The 15 failures group as follows:

- Five worker contour cases in test_real_producer_grants_reconcile_with_reopened_cache_intent fail at the real worker-wire serialization boundary: _JournaledArtifactRef is rejected as an unsupported runner-wire model (serialization.py:250). This is an observed candidate failure, not a platform skip.
- Nine async unsupported-hook cases propagate TypeError from model admission instead of returning the structured failed execution result expected by the test.
- The sequential __new__ refusal case invokes the custom __new__ one extra time (calls: ["new"] -> ["new", "new"]) before refusal.

The full node IDs and traces are in the retained JUnit/stdout. The suite emitted 41 Pydantic serialization warnings for nested models carried in the JSON-typed params field; the tests themselves use ExperimentState.model_construct for those graph cases. Pytest also warned that cache_dir is not recognized with the cache provider disabled.

## Isolation and provenance

- G remained attached to codex/e02-integration at 83e7c0e934d0b40644dec8a24264a0602ef013e7; its tracked tree stayed clean and unchanged.
- The first pytest attempt stopped during collection because an import read the tracked architecture digest-domain registry outside src. No cases ran in that attempt. The repaired closure adds only five tracked inputs from the same d18 commit (three owner registries, uv.lock, and the bound sync tool); the final manifest verifies 2,930 blobs/modes, 56,046,040 bytes, against that exact commit.
- Candidate-only import guard removed the live G product paths. All 1,105 Polisyos modules loaded in the repaired pytest wave resolved to the isolated archive and matched candidate Git blobs; there were no origin errors. The direct probe loaded 87 candidate modules, also with no origin errors. The support statement is in engine README blob d670a631351088fda0e3d42cce6d48536b71c143 (d18fe09).
- Runtime: Python 3.14.3, pytest 9.0.2, pytest-asyncio 1.3.0, Pydantic 2.12.5. No dependency installation or production data was used. Pytest peak RSS was 763,641,856 bytes; direct probe peak RSS was 78,135,296 bytes. Disk free was 24,967,897,088 bytes before and 24,933,957,632 after.
- The c44 oracle test was excluded: its test blob is paired with an older state_branching.py blob and would mix incompatible candidates. The old 3eb FAIL was not treated as a d18 result.

One intermediate repair-harness invocation failed its own preflight because its manifest verifier used the project root instead of the archive root; it launched no candidate process. That verifier path was corrected before the single repaired pytest wave above. The first collection failure and this no-launch harness error are retained as history, not product test failures.

## Evidence files

Complete raw outputs, JUnit, command/environment context, exact source manifests, module-origin maps, and the direct probe's full before/after state and journal are under results/. Machine-readable summary: receipt.json. No candidate source, tests, Git refs, or tracked G files were modified. No finding closure is claimed.
