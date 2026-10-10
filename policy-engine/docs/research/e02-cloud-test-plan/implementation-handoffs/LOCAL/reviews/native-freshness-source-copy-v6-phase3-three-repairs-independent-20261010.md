# Independent v6 delta review: phase-3 fixture repairs

## Decision

**GO to apply v6 and rerun the complete 69-case phase-3 suite.** The patch is limited to the test module and its three edits align fixtures/observers with the current source-copy contract. They retain the semantic assertions and do not change production source, weaken a refusal, or convert absent setup into a pass. The previous complete run remains red (66 passed, 3 failed); this review does not claim the fixes pass.

Static review only: I did not apply the patch, run tests, invoke a generator/native wave, or mutate Git.

## Identity and preimage

- Patch: `LOCAL/raw/native-freshness-source-copy-v6-phase3-three-repairs-20261010.patch`, SHA-256 `7c225a67b64731e1371c8cd49f0771e0f78f712b9e26d09f3a7f6b8cd3125f3e`.
- Author note: `LOCAL/dx0-native/native-freshness-source-copy-phase3-three-repairs-v6-20261010.md@95e9ff52b90eaefcfe64a3d65d389bdf3a30d64119e8de1ce9f846086f059be2`.
- Exact current test preimage: `tests/repo_quality/tools/test_architecture_phase3.py@f7f13e6418a3ab25f407ff55b8a62dd828ec5d2bfc3aae458ec282ef4e56f64f`.
- Companion source/manifest hashes match the note: guardrails `ab19751f999d3ca5385eb4997e78855b2a551e5cbbf26bd0f78addc991af9031`; trust checker `c5364ba8b2250075cf6557818490aad59a16f100b5266a07425d0b7842686793`; generated-artifact manifest `2283a5faa66061b66cad5870976dcefd92cb40d74658300d93590ee6fe3e97da`.
- The patch changes only `tests/repo_quality/tools/test_architecture_phase3.py`.

## Three repaired controls

1. The editable-binding fixture now declares its actual `uv.toml` cache path `_cache/uv` as local-only. The copier should therefore exclude the exact cache directory that uv creates, rather than encountering an undeclared symlink. The separate owner-contract control narrows the local-only path from `_cache` to `_cache/uv`, retains and reads `src/_cache/uv/source.py`, and excludes only root `_cache/uv`. That preserves the nested-source falsifier and avoids basename-wide exclusion.
2. The canonical-import test double now forwards `repo_root` and `families` to the actual environment builder. Its existing assertion still requires `canonical_source_origin` and an `environment` `UNRUN` before output creation, so the test exercises the intended import-origin refusal rather than a `TypeError` in the wrapper.
3. The interrupt test now targets the generator command whose `-c` invocation’s output-root argument names `active-family`. This removes subprocess ordinal as a proxy for which family is active; assertions still require the completed-family finding, active-family generator interruption, and pending-family `not_started` status.

These edits address the three precisely reported fixture/observer failures. The v5 stale-bytecode positive and removal controls are untouched. `P40` remains **SAME_CLASS_DEEPER**; the ordinal trigger was a `P38` proxy and is replaced by the active family output-root identity.

## Next verification and limits

Apply this exact patch and rerun the complete 69-case suite, preserving stdout/stderr/JUnit. Any remaining failure must be classified from the new full output; this review does not infer that the prior failures are resolved at runtime. The earlier renderer requirement and frozen native wave remain separate gates. Source-copy completeness, arbitrary ambient-read isolation, and concurrent source-copy atomicity remain `not_established` until their existing controls/receipts say otherwise.
