# Independent CAN reader-profile delta review

## Frozen source

- Base: `fe8bfb2c8017750e2a4e5edc4c12b2e9cd640990` / tree `f624ea8bed3b56a5a312350c282af6fdd0ed521e`.
- Candidate: `55b45d9a5c95c3b773fc3b4d8679786b3993eb1e` / tree `70ed14e004063536ff3a12d30d14d9bdd79a4916` (parent is the stated base).
- Worktree: `codex/e02-C-canon-20261006`, clean at readback. Delta is the expected three paths: `policy-engine/src/polisyos/ir/artifacts/io.py`, its README, and `tests/unit/core/artifacts/test_ir_adapter.py`. `git diff --check fe8b..55b45d9` exits 0.

## Finding and bounded verdict

**GO for the C-owned shared IR reader’s profile-required property.** `get_json_artifact` now raises `CanonViolation("unsupported_ir_canon_profile")` when the persisted manifest lacks `canon`; for present profiles it calls the existing strict supported-profile validator before requesting payload bytes, then decodes with the persisted `max_depth` (`io.py:174–181`). The absent-profile fallback constant is deleted. Kind/schema strings and actual readable bytes do not grant a profile.

The new negative test writes a real Core CAS artifact with no `canon`, preserves `kind="ir.legacy-json"` and a schema marker, reads the stored bytes to prove the object exists, then tracks `get_bytes` while invoking the IR reader. It gets the typed refusal with zero payload reads (`test_ir_adapter.py:384–416`). Unsupported and malformed profile tests likewise assert zero reads. Positive tests still cover a persisted depth of 129 and rejection at an insufficient depth of 128. The README says profile-less historical artifact readability remains unconfirmed/on hold; it does not claim a migration or historical-compatibility path.

The source/test removal evidence is useful and property-specific: the author’s baseline-red receipt for the new unprofiled-marker test fails against the former fallback (one failing test), while its final candidate run passes. The separate shape-only profile-policy mutant makes all five unsupported/malformed-profile tests fail; it does not mutate the missing-profile guard. Thus the latter is evidence for profile validation, while baseline-red→candidate-green is the direct evidence for the newly closed absence-proxy class.

## Consumers and residual scope

Author’s AST census is complete for the declared local denominator: `policy-engine/src/polisyos`, 2,698 Python source files, zero parse errors, 133 direct calls to `get_json_artifact` in 72 files (`consumer-census.json`, SHA-256 `28b37f97ab3308c5a97f4fb0ffad738623a19fa4cd4c0f83ba1bfb85779680a4`). The census recognizes imports from `polisyos.ir.artifacts` and `.io`; it establishes local direct consumers of this common gate, not contents of stores, historical manifests, dynamically resolved consumers, or third-party consumers. The scoped baseline keyword sweep of the IR artifact source and `docs/reference/ir` found no explicit local “historical/legacy canon” promise (exit 1, empty output); this is not proof that no such external promise or persisted data exists. So an owner-supported historical profile-less input remains **not established**, not disproven. No discriminator or legacy bypass should be inferred from labels.

The C delta therefore closes the shared-reader escape. The full LA021 capability remains **held** for the separate raw Core writer/profile-strangle admission boundary; this delta does not alter it or prove historical data compatibility. No new source bypass around the shared `get_json_artifact` gate was found in the declared census. External artifacts/consumers remain outside this evidence.

## Fresh independent check

Ran the exact command in `focused-reader-tests.command.txt` using the private `policy-engine/.venv`, CPU and BLAS thread counts set to one, with output preserved in `focused-reader-tests.log`. Result: **8 passed in 0.20s**. It covers missing-profile refusal with markers and zero `get_bytes`, valid and too-low depth, unsupported profile identity/version/negative depth, and malformed parameters. The correct log SHA-256 is recorded below.

The author’s focused receipt is `can-reader-profile/final-required-focused-v2.log` (40 passed in 17.68s; SHA-256 `57605fdd2e911128e9615cfee9e70156fcc7ce9a92488578f1de072f831c6a72`, exit 0). Ruff check and format receipts exit 0: `final-v2-ruff-check.log` SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`; `final-v2-ruff-format.log` SHA-256 `3bc53bf3e981a98a34a852e175bf9b77af841edea74fca595d9aedcbaf9a4938`.

No tracked files were edited. No build, install, or broad test suite was run.
