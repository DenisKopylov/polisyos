# Native Ruff I001 scoped proposal — independent full-set review (2026-10-10)

## Verdict

**GO for the exact 438-file format-only cohort in this unapplied proposal.** The full changed set is source-bound to the current I001 denominator, and the in-memory patch check found no import binding/order/grouping, comment-association, parse, or non-import-AST change. This is a static source-equivalence review, not a test or Ruff pass receipt.

P40 bucket: **SAME_CLASS_DEEPER** for the import-format cleanup class. This review covers the whole currently proposed 438-file cohort rather than another hand-selected subset. The remaining 221 current I001 paths are outside this proposal; their potential order/grouping changes are not implicitly approved. A hypothetical future I001 diagnostic outside this frozen set is not evidence against this cohort.

## Inputs and denominator

- Candidate root reviewed: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos/policy-engine`.
- Proposal patch: `LOCAL/raw/native-i001-scoped-reviewed-proposal.patch`, SHA-256 `ab382dac3becba1629ed5b52cb5a0fdc60c3bacb3d7bd801320fc2c2a40681db`.
- Proposal note: `LOCAL/dx0-native/native-i001-scoped-proposal.md`, SHA-256 `b4a4773b0638a7b9bbd213db76f9bcc62090b5168c49ebf2bcc11fb6519a4309`.
- Classified diagnostics input: `LOCAL/raw/pre-freeze-canonical-ruff-check-20261010/canonical-ruff-classified-diagnostics.json` (the proposal records SHA-256 `d10452030a3479ff77de3dd068e4101a6487f31a0920f44576d4352b32bd8831` and source-manifest SHA-256 `d6fdd4f919c00e0c611b2cee81eeb132de8ff412c87a856b88edfc7999b55fb7`).

I recomputed the I001 denominator from the primary `rows` array: 2,027 total diagnostic rows, 682 I001 rows, and 659 unique I001 paths. I hashed all 659 current path preimages against the embedded source manifest: 659 matched, zero missing, zero mismatches. The patch has 438 unique paths; every path is in that I001 set, and `659 - 438 = 221` paths remain unpatched.

## Full 438-file patch recomputation

I parsed the complete unified patch, resolved its repository-root `policy-engine/` prefix against this product root, checked every hunk against the current preimage, and applied the hunks in memory without writing files. All 438 patch preimages matched the input hash manifest and all 438 hunks matched the current source.

For every one of the 438 before/after pairs I independently compared: ordered `Import`/`ImportFrom` AST signatures (statement kind, module, relative level, alias grouping/order and `asname`); exact comment-token text sequence and its within/same-line/neighboring-import association; and the full AST after replacing import statements with equivalent placeholders. Results: zero hunk/application failures, zero parse failures, zero import-signature changes, zero comment-text or comment-association changes, and zero non-import-AST changes. A separate diff-line check found 173 changed nonblank lines, all inside import AST spans; 424 changed lines were blank-line spacing.

Thus the exact proposed 438-file transformation preserves import execution sequence and binding structure, comments and their import attachment, and every non-import syntax tree. No Ruff configuration, selectors, `noqa` directives, or source files were edited by this review. I did not run tests or Ruff, and did not apply the patch.

## Boundary

The 221-path holdout is a real residual, not part of the GO: the proposal note categorizes those as import-atom reordering or statement-grouping changes, which this review did not apply or independently regenerate. The 438-file GO does not clear the remaining I001 backlog or certify future Ruff output. Since the proposed cohort is syntax-preserving formatting only, no runtime test was run under this read-only review; after application, the relevant lint check should confirm the intended I001 diagnostics are removed without changing the held paths.
