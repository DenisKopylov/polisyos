# Native source-copy phase 3 fixture repair patch v6

Patch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy-v6-phase3-three-repairs-20261010.patch`
Patch SHA-256: `7c225a67b64731e1371c8cd49f0771e0f78f712b9e26d09f3a7f6b8cd3125f3e`

This is an unapplied, test-only patch against the pinned product snapshot. It makes the three failures from the complete 69-case run reach the intended owner-contract, import-origin, and interruption properties. It does not change the source copier or weaken the stale-bytecode and complete-source checks.

## Complete deciding run

- Receipt directory: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-source-copy-complete-basis-pycache-verification-20261010`
- JUnit: `junit.xml@d86e9762472bb07606dbb5fa562db19243d0e72e98e102a6ec601df6c85384ee`
- Result: 69 tests, 66 passed, 3 failed, 0 errors, 0 skipped; pytest 206.676 s; total wall 210.156 s; exit 1.
- Captured stdout: `stdout.txt@29f921f5bcc413247c968c102caf1cb4461ff08247e2c4e21e56a0adafe99523` (4,901 bytes). Captured stderr: `stderr.txt@e778d205a3136307f60398f54f3cf82c0e6c3fbb3ce96cc5b93fd3d0fd4cb166` (777 bytes).
- Prior v5 controls still passed in that run, including stale bytecode and the remove-prefix control. No tests were rerun while preparing v6.

## Failure disposition

1. `test_generated_probe_preserves_caller_editable_binding` failed because the uv cache symlink was under `caller/_cache/uv`, but the fixture had not declared that exact path local-only. The copier correctly rejected the symlink. The patch pins a fixture-local `uv.toml` cache path and declares only `_cache/uv` local-only in that fixture; it does not exclude `_cache` by basename. The local-only-root control now separately proves that `src/_cache/uv/source.py` remains selected while root `_cache/uv` state is excluded.
2. `test_isolated_python_import_origin_rejects_canonical_source_with_matching_bytes` never reached the origin probe: its monkeypatched `_isolated_probe_environment` wrapper omitted the caller's current `repo_root` and `families` keywords, raising `TypeError`, which the generic boundary reported as `measurement`. The patch forwards both arguments, so the existing assertion requires a real child to import byte-identical canonical source, report `canonical_source_origin`, and remain `environment` UNRUN before any generator output. No production phase classification was changed.
3. `test_interrupted_generator_is_unrun_and_keeps_completed_findings` counted every `subprocess.run`. The new import-origin preflight is the first subprocess, so count 2 interrupted `completed-family`, not `active-family`. The patch targets the command whose output-root argument names `active-family`. The test still requires the prior completed-family drift finding plus active-family `[generator]` and pending-family `[not_started]` UNRUN records.

P40: SAME test-fixture alignment class after the full source-basis/bytecode behavior was introduced. These three are fixture/observer defects, not new source-copy escapes. P38 was present in the interruption test: it used subprocess ordinal as a stand-in for the active generator. The v6 correction selects the actual family command. No P41 inherited-red claim is made; these are three failures in the complete current replay.

## Patch and companion footprint

The patch changes only `tests/repo_quality/tools/test_architecture_phase3.py`; no production source, generated inventory, policy, expiry, baseline, or documentation is modified. The nested-source semantic control is retained and sharpened for the exact `_cache/uv` suffix.

Pinned current inputs:

- `tools/devx/architecture/guardrails.py@ab19751f999d3ca5385eb4997e78855b2a551e5cbbf26bd0f78addc991af9031`
- `tests/repo_quality/tools/test_architecture_phase3.py@f7f13e6418a3ab25f407ff55b8a62dd828ec5d2bfc3aae458ec282ef4e56f64f` (candidate result SHA-256 `ef386e1ea57653fc5ec626609916fad6ace4ba8779d7eb3f4162777c37227ef3`)
- `tools/quality/validation/check_trust_claim_posture.py@c5364ba8b2250075cf6557818490aad59a16f100b5266a07425d0b7842686793`
- `architecture/generated_artifacts.toml@2283a5faa66061b66cad5870976dcefd92cb40d74658300d93590ee6fe3e97da`

Static candidate check: the updated test module parses with `ast.parse`. This is not runtime verification. Root must apply and run the focused phase 3 suite; the 69-case native replay remains the deciding check.
