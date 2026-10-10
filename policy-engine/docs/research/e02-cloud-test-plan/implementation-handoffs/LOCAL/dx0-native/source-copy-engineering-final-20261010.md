# Native source-copy patch: final author iteration

**Status:** PATCH ONLY; not applied, tested, regenerated, or used for a native-wave verdict. The source-copy boundary is still `not_established` until review, apply, focused tests, canonical generated-reference sync, and the frozen native wave complete.

## Artifacts and exact inputs

- Final candidate: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy.patch@cf070cb08c40de592a3e0f4419e7ac82e646ac3a91c1056f08b65ce5616f3c92` (59,560 bytes).
- Previous candidate preserved byte-for-byte before replacement: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/native-freshness-source-copy.proposal-45535b728a5f08d2.patch@45535b728a5f08d2e3efcd8eb9041f91b473b6fb0f5397616838acd6c7733348`.
- Prior design remains unchanged at `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/dx0-native/source-copy-proposal-design-20261010.md@0c8822e2f2c9bf069076ab46b856283675ec039f340e103510a1448d8f216c46`.
- Candidate is based on HEAD `9194a65fb59355ceac35270c869f429efc7482d8`; all four product preimages still match: `guardrails.py@5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6`, `test_architecture_phase3.py@6cbdbe384c2ea300ffdfed7bdd460fa2a696e5ea22179cf6135db64d9d4a61d2`, `generated_artifacts.toml@0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`, and `check_trust_claim_posture.py@3cc47926a168f903a0dd6921eaa131b2d335ef850e8586e7cfbf2ae5837a5ac5`.
- Patch touches only those four paths. No product file, test, generated artifact, or Git state was changed.

## Widened mechanism

The selected family roots are copied as complete source roots. Structural venv/Hugging Face-name detection no longer drops nested files: the canonical trust source consumer admits contained `src/**/*.py` except `__pycache__`, so Python files beneath those layouts remain selected and copied. New test controls use the real `walk_source_files` consumer, then run a child that reads the copied candidate; both a venv-shaped tree and a Hugging Face-shaped tree retain the source file. Exact `local_only` owner-contract roots remain excluded by their declared paths, not by a basename guess.

The source walk now supplies an `onerror` handler that raises `OSError`. The existing measurement caller maps setup `OSError` to an `environment` `UnrunGeneratedCheck`, so an unreadable untracked descendant cannot silently produce a partial successful copy. The new test injects a real `PermissionError` through the `os.walk` error callback, checks that the copy refuses before destination creation, and leaves the source marker present.

The pnpm receipt still checks package-manager and frozen-lock agreement, and now also derives a SHA-256 inventory from every declared runtime tree. The deterministic traversal records entry names and modes; hashes regular-file bytes; records each symlink’s literal target and checkout-relative resolved target; recursively hashes the resolved target; and refuses unreadable/missing entries, cycles, special files, or targets outside the checkout. The initial inventory digest is printed into the deciding gate output and recomputed after dependent generators; an unavailable or changed tree marks pnpm families `UNRUN`. The package-link counterexample redirects a declared package `node_modules` path outside the checkout and must fail before copy. A second control changes an installed file’s bytes and requires the inventory digest to change.

This is a bounded source/runtime basis repair. It does not claim an OS-level sandbox: arbitrary ambient reads remain `not_established`, and a concurrent runtime mutation that changes and is restored between the before/after inventories is not excluded. The node_modules inventory can add runtime cost proportional to the installed tree; measure that once before budgeting the final wave. A symlink that resolves to an external store fails closed as `UNRUN` until that store has an admitted, content-bound profile.

## P40 / acceptance

**P40: SAME_CLASS_DEEPER.** The latest three findings all concern the same admitted-input quantity: incomplete filesystem enumeration, structural exclusions that conflict with the producer’s source selector, and unresolved or unbound runtime targets. This candidate widens the mechanism to the complete selected filesystem roots and complete declared pnpm runtime trees instead of adding per-path exceptions. There is no issuer waiver or expiry change.

Before a green native claim, reviewers must apply/review this exact patch; run the focused new and importer tests; regenerate and check the mandatory `docs/reference/generated-artifacts.md` renderer companion; verify corrupt-field/drift controls; then run the frozen native wave with full outputs retained. Until then, source-copy completeness, producer output equivalence, and native SOTA pass are `not_established`.
