# Phase 3 source-copy verification repair patch v4

Patch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy-v4-phase3-repairs.patch`
Patch SHA-256: `cbd329a7f839f85b41f843fbd85885c0abe62c6c5e5b16b099a3c746840f4807`

This is an unapplied patch against the current product snapshot. No product source was written and no tests were rerun.

## Verification input

- Full phase3 receipt: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-source-copy-phase3-verification-20261010`
- Command outcome: 68 tests, 30 failures, 0 errors, 0 skipped; 111.993 s; exit 1.
- Captured JUnit SHA-256: `452a21b570d91cdb22746f03c5096b52160e519391d388cb101134e9ffc25651`.

## Failure disposition

- 21 failures share the incomplete generic `_generated_client_family` fixture basis: 13 direct missing-directory-contract errors plus 8 intended assertions/outcomes preempted by the same early UNRUN. The fixture now materializes a directory contract and declares its temporary repo as the source root; `.git`, `.venv`, and `production_data` are fixture-local-only entries, while explicit source-root tests keep their own narrower roots.
- 6 failures hit disk preflight with a nonexistent destination parent. The copier now measures the nearest existing ancestor without creating the destination tree; the existing preflight test records the exact ancestor and keeps a no-space control.
- 1 failure used an outdated test double that returned `None` where the copier API returns `(runtime_paths, inventory_digest)`; the test double now returns the contract-shaped empty pair and reaches the injected `KeyboardInterrupt`.
- 1 failure expected the phrase “outside the checkout”; production raises the repository-scoped diagnostic. The negative test now matches the actual contract message.
- 1 failure asserted that a public `polisyos.core.security` facade appeared in a deep-import-only edge list. The source explicitly imports the public facade; the test now verifies that AST route and rejects any private `core.security.*` edge.

## Pinned current inputs

- `tools/devx/architecture/guardrails.py@e3d8d2b1336e2559fb6f383f7bcd6e17181e1f3d782579728111a362ceafeaaf`
- `tests/repo_quality/tools/test_architecture_phase3.py@e129358de260a0e03d0e5436a1d61cba5d46fda8239cd56cfe87776f6466c76f`
- `tools/quality/validation/check_trust_claim_posture.py@c5364ba8b2250075cf6557818490aad59a16f100b5266a07425d0b7842686793`
- `architecture/generated_artifacts.toml@2283a5faa66061b66cad5870976dcefd92cb40d74658300d93590ee6fe3e97da`

The patch changes only `tools/devx/architecture/guardrails.py` and `tests/repo_quality/tools/test_architecture_phase3.py`. It does not alter posture source or the generated-artifact manifest.

Static candidate check: both resulting Python texts parse with `ast.parse`. This is not a test pass; the root must apply and rerun the focused suite.
