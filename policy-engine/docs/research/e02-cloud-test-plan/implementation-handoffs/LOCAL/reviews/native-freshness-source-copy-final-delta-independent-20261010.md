# Independent delta review: native freshness source copy

## Decision

**NO-GO to apply this candidate as-is.** The requested traversal-error repair is incomplete: the patch passes `_probe_walk_error` to `os.walk`, but that name is undefined in the pinned source and is never defined in the patch. Evaluating the argument raises `NameError` before `os.walk` runs. The new permission-error test expects an `OSError`, so it cannot pass. Add a small raising callback (or inline equivalent), then apply and run the focused importer/new tests. This is a concrete implementation defect, not a demand for broader sandboxing.

Once fixed, the other two prior blockers appear materially addressed by the widened mechanism and controls. This is a delta review only: I did not apply the patch, run tests, run a generator/native wave, or mutate Git.

## Frozen inputs and footprint

- Candidate patch: `LOCAL/raw/native-freshness-source-copy.patch`, SHA-256 `cf070cb08c40de592a3e0f4419e7ac82e646ac3a91c1056f08b65ce5616f3c92`, 59,560 bytes.
- Author final note: `LOCAL/dx0-native/source-copy-engineering-final-20261010.md`, SHA-256 `7d1cc0c4169e7bf1d964360552c3fee861af15eaa8fe85cf15a7b28785f997ff`.
- Previous independent review: `LOCAL/reviews/native-freshness-source-copy-final-independent-20261010.md@0135ab77c567fd426b03ebf25989230f1fa2a462c9db20c81312cd570dd94b75`.
- The patch changes four paths: `tools/devx/architecture/guardrails.py`, `tests/repo_quality/tools/test_architecture_phase3.py`, `architecture/generated_artifacts.toml`, and `tools/quality/validation/check_trust_claim_posture.py`. The generated renderer companion `docs/reference/generated-artifacts.md` is not included and remains required before freeze.
- All four product preimages still match: guardrails `5d30de37ed02c5e346458e62e00b2772e7ba0eed501cf8282f72d3058bf9b4f6`; test `6cbdbe384c2ea300ffdfed7bdd460fa2a696e5ea22179cf6135db64d9d4a61d2`; manifest `0a79005a1d37c38ea759509215205284698b4bb12ecabb42c29e70196486eb6a`; trust checker `3cc47926a168f903a0dd6921eaa131b2d335ef850e8586e7cfbf2ae5837a5ac5`.
- The parent reports `git apply --check` passed for this exact artifact; I did not rerun it.

## Delta against the three prior gaps

1. **Walk failures: still blocked.** `os.walk(..., onerror=_probe_walk_error)` appears at patch artifact line 509. Repository search finds no definition in the base or candidate. The new `test_family_source_copy_fails_closed_on_directory_enumeration_error` injects `PermissionError` and expects `OSError` matching “unable to enumerate selected probe source”; as written, the undefined name fails first. The intended fail-closed behavior is sound, but is not implemented until the callback is defined and raises a contextual `OSError`.

2. **Structural environment/Hugging Face exclusions: addressed at the source-copy boundary.** The candidate removes the structural cache exclusions and walks all admitted family roots. Its new environment/HF tests first assert that the canonical `walk_source_files()` selector admits the nested Python file, then verify a copied child can read it. That directly covers the former selector/copy divergence for these layouts. It does not claim those files are all semantically relevant to every consumer; it binds the producer’s actual selected source set.

3. **pnpm target and content binding: addressed for declared runtime trees.** Runtime paths are limited to the three admitted package-manager locations and checked for checkout containment. `_pnpm_runtime_inventory_digest` recursively hashes regular-file bytes and modes, and records each symlink’s literal target, resolved checkout-relative target, and resolved contents. The before/after digest gates pnpm families to `UNRUN` on change or disappearance. New controls refuse an external package-link target and prove that changing installed bytes changes the inventory. This is a current-input inventory, not proof that the installed tree is reproducible from or cryptographically authenticated by the lockfile; the note does not make that stronger claim.

## Remaining boundary and P40

**P40: SAME_CLASS_DEEPER.** These findings remain one admitted-input/source-copy class. The candidate widens selection and runtime inventory rather than adding filename-specific exceptions. The missing callback is the final concrete defect in that widened mechanism; do not add a per-path workaround.

The author correctly leaves arbitrary ambient/absolute child reads `not_established`. The before/after package inventory also cannot detect a runtime mutation that is changed and restored between both snapshots. Those are explicit bounded limits here; the review does not require a hypothetical recursive verifier or claim OS-level isolation. The source-copy itself has no atomic worktree snapshot/content receipt, so concurrent source edits during copying are likewise outside this candidate’s demonstrated guarantee; hold source writers during the frozen wave and keep that boundary `not_established` unless separately closed.

After the callback fix: apply the exact patch, run its focused tests/importer checks, regenerate and check `docs/reference/generated-artifacts.md`, then evaluate the frozen native wave. Until those receipts exist, copied-source completeness, native output equivalence, and native freshness remain `not_established`.
