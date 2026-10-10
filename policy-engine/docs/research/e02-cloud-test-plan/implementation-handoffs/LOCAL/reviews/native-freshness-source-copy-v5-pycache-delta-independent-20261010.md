# Independent v5 delta review: isolated Python bytecode cache

## Decision

**GO to apply v5 and run the whole focused phase-3 suite plus its semantic controls.** The patch closes the observed stale-bytecode read path at the Python subprocess environment boundary without deleting or excluding copied `.pyc` files. The test is an actual counterfactual: same-size source and restored timestamp make the unisolated child execute old cached code; the isolated child executes current source; removing only the cache-prefix variable while retaining markers reproduces the stale result.

This is static review only. I did not apply the patch, run tests, generate artifacts, run the native wave, or mutate Git. The author’s 68-test replay still has 30 failures at the v3 baseline; v5 contains repairs for those fixture/diagnostic issues, but they need to be validated by the next run.

## Patch and source identity

- Patch: `LOCAL/raw/native-freshness-source-copy-v5-pycache-isolation-20261010.patch`, SHA-256 `59912f87649c8fcfb43f0f7b0fc72b750e70c1ffd80b2107bc6b99114a6ee150`.
- Author note: `LOCAL/dx0-native/native-freshness-source-copy-pycache-v5-20261010.md@6ce7dcdef11d278f90d5aa3233f1f3b864cb065ba46e9643e24961f828bea5d8`.
- Current source preimages match the pins: guardrails `e3d8d2b1336e2559fb6f383f7bcd6e17181e1f3d782579728111a362ceafeaaf`; test `e129358de260a0e03d0e5436a1d61cba5d46fda8239cd56cfe87776f6466c76f`; trust checker `c5364ba8b2250075cf6557818490aad59a16f100b5266a07425d0b7842686793`; manifest `2283a5faa66061b66cad5870976dcefd92cb40d74658300d93590ee6fe3e97da`.
- Patch footprint is two files: `tools/devx/architecture/guardrails.py` and `tests/repo_quality/tools/test_architecture_phase3.py`.

## Property review

The runtime environment builder removes inherited `PYTHONPYCACHEPREFIX`, then sets it to `source_root.parent / "python-bytecode-cache"`. This path is absolute and outside both the copied source and the private Python environment. `PYTHONDONTWRITEBYTECODE=1` remains set. The change neither filters nor removes cached files from selected source roots; it prevents the child interpreter from consulting their adjacent `__pycache__` entries by redirecting bytecode lookup to a fresh per-run prefix.

The new test constructs an actual timestamp-valid stale cache: it compiles the old source, writes equal-length new source, then restores the original mtime. A plain `-B` child reads the old value from the copied source tree. With the production environment builder, the child reads the new source value. Removing only `PYTHONPYCACHEPREFIX` from that same environment makes the child read the stale value again. That is a behavioral remove-the-property control, not a marker check.

The other v4 repairs in this cumulative patch also look like focused fixes to the reported failures: the shared family fixture now supplies the required basis and directory contract; disk preflight resolves to the nearest existing ancestor without creating parents; the interruption double returns the copier’s tuple; the assertion matches the emitted path-error wording; and the security-route check compares actual AST imports with the private deep-edge set. These changes do not appear to bypass the selectors or turn missing setup into a blank success. Their runtime behavior still needs the requested whole-suite replay.

## P40 and bounded limits

**P40: SAME_CLASS_DEEPER.** Stale `.pyc` execution is another interpreter-input escape within the same source-copy/freshness class. The patch widens runtime isolation with a per-run cache prefix; it does not add a per-module deletion or path exception.

Keep arbitrary ambient reads, concurrent source-copy atomicity, and a runtime mutation that changes and is restored between inventory checks `not_established`. Do not claim OS-level isolation. The prior generated-artifact renderer companion obligation remains from v3; v5 does not change the manifest or generated-reference source.

Next verification should apply this exact patch and run the whole phase-3 suite with the stale-cache negative control, then preserve full outputs. The generated-reference renderer and frozen native wave remain separate gates. Until those receipts exist, native source completeness and output equivalence remain `not_established`.
