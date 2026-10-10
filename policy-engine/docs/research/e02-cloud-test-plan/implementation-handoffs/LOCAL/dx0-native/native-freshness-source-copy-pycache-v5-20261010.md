# Native source-copy patch v5: isolated bytecode lookup

Patch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy-v5-pycache-isolation-20261010.patch`
Patch SHA-256: `59912f87649c8fcfb43f0f7b0fc72b750e70c1ffd80b2107bc6b99114a6ee150`

This is an unapplied cumulative patch from the pinned current product snapshot. It includes the v4 phase3 repairs plus the bytecode-isolation fix and adversarial control. The earlier v4 patch remains preserved unchanged.

## Evidence and disposition

- Parent-measured current source census found 2,318 `src/**/*.pyc` files. This is the same source-copy completeness class at a deeper interpreter input boundary (`P40 SAME_CLASS_DEEPER`): copying complete `.py` source while allowing timestamp-valid adjacent `.pyc` reads can execute code that does not match the copied current source.
- `_isolated_probe_environment` now scrubs any inherited `PYTHONPYCACHEPREFIX` then binds it to a per-run `python-bytecode-cache` sibling, outside both copied source and private environment. It retains `PYTHONDONTWRITEBYTECODE=1`; no source-tree bytecode is deleted or filtered.
- The semantic test creates old/new same-size source, writes a timestamp cache, restores the original source mtime, confirms an unisolated `-B` child loads old code, copies the complete source including that `.pyc`, confirms the isolated child loads new code, and removes only the prefix while retaining the same markers to confirm the child regresses to old code.
- The patch preserves v4 changes: shared fixture basis, nearest-existing-ancestor disk preflight, contract-shaped interrupted-setup test double, diagnostic phrase correction, and the public security route test correction.

## Pinned current inputs

- `tools/devx/architecture/guardrails.py@e3d8d2b1336e2559fb6f383f7bcd6e17181e1f3d782579728111a362ceafeaaf`
- `tests/repo_quality/tools/test_architecture_phase3.py@e129358de260a0e03d0e5436a1d61cba5d46fda8239cd56cfe87776f6466c76f`
- `tools/quality/validation/check_trust_claim_posture.py@c5364ba8b2250075cf6557818490aad59a16f100b5266a07425d0b7842686793`
- `architecture/generated_artifacts.toml@2283a5faa66061b66cad5870976dcefd92cb40d74658300d93590ee6fe3e97da`

Patch footprint: only `tools/devx/architecture/guardrails.py` and `tests/repo_quality/tools/test_architecture_phase3.py`. No product files were written and no test was run. Both candidate files parse with `ast.parse`; root must apply and run the focused suite with the negative control.
