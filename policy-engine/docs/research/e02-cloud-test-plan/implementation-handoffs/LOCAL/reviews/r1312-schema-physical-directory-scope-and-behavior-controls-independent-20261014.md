# R1312 — Independent review of R1288-R1 schema directory identity

Verdict: **GO for root source application and the specified deciding run; native acceptance remains UNRUN.** This is a read-only static review of the exact three-path virtual patch. It is not a test receipt, an applied-source claim, a G acceptance, or a closure. `closure_ids=[]`.

## Bound inputs

- Worktree and branch: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`, `codex/e02-unified-local-20261009`.
- Candidate source preimage HEAD/tree: `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d` / `1355896e91789026d21396d2b087c63827ab251b`; this was the attached HEAD when the exact patch preimages were first checked.
- Original source frame: `LOCAL/root-author-source-frame-r1267-20261014.json@a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803`.
- Known later receipt-only advance: HEAD `a02f4f8920c60e02e745ba91bbed9ab9524fcbe7`, tree `da829953b1c170f3bc69420059dc7d1af4fb06f7`; its source frame `LOCAL/root-author-source-frame-r1306-20261014.json@b87c7b5fe6bb4f56efa87f020784be72873c88d87fc5f76faa6fa4d5edf2bddb` records `source_implementation_head=a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d`. All three candidate target files still match the same manifest preimages after that advance. The review remains source-byte-bound; it does not treat receipt history as a new implementation base.
- Candidate: `LOCAL/raw/r1288-schema-directory-identity-and-prewrite-behavior-successor-r1-20261014/proposal.patch@6fae3cea8005da489901946bcb1864fd679f78052ca99dff55b9e2b762a6e776`; manifest `@c76f73e369f59f29a69da4c4f330c66c14debd4b3f7ce90569d9fd0122f9f86e`; decision `@e7daeb89600e6136342e27fa7c8b022503575a126a0ba6306f3d6cb1488fab8f`.
- Scope is exactly three paths: `tools/quality/diagnostics/gen_schema.py`, `tests/repo_quality/tools/test_diagnostics_phase3.py`, and `tools/quality/diagnostics/README.md`. Each physical file matched its manifest preimage hash. `git apply --check` exited 0. An in-memory unified-diff reconstruction matched all three declared postimage hashes; both Python postimages passed `ast.parse`. No source, index, Git history, generator, test, native gate, or database was changed or run.

## Property review

R1273's P38 counterexample is present on this checkout: `schemas/snapshots` and `schemas/Snapshots` resolve to different strings, while `samefile` is true and both report device/inode `16777231/175366069`. This is the physical-target property the old string comparison missed.

R1288-R1 uses a single directory-identity predicate. Existing directories are compared with `Path.samefile`; missing destinations are related through the nearest existing directory and the complete unresolved suffix. Symlink and case aliases in existing ancestors are therefore compared by physical identity. Equal-depth, differently spelled missing suffixes under the same physical ancestor return unknown and fail closed; the code does not lowercase names or infer identity from a path string. The error is raised immediately after deprecated-argument normalization and before entry resolution, cache setup/access, reference-page generation, or output writes.

The scope mechanism remains pathwise coherent: a partial canonical generation is refused; a filtered canonical check expands to the complete selected module; a genuinely separate custom output retains selected-entry behavior. The callback branches match that boundary: canonical paths invoke the global IR reference generator, while preview generation/check avoids it. The preview fixture has an existing canonical directory and a missing sibling preview path, so it exercises a usable custom preview without depending on the intentionally ambiguous “both sibling destinations missing” case.

The proposed tests address the earlier R1273 proof gaps with runtime seams and whole-tree byte snapshots: `_resolve_entry` and reference-doc callback counts; alias matrices over implicit default, `--output-dir`, deprecated directory output, and deprecated JSON-parent output; ABI-key, priority, and FQN selectors; symlink and conditional case aliases; missing destinations under aliased ancestors; and an ambiguous missing-sibling refusal. They also include sibling-schema corruption, manifest-row removal with recomputed `content_hash`, and selected-preview content corruption. The 106-row denominator remains bound to the complete registry census and `abi_models.py` hash recorded in the preserved R1273 review.

I found no static blocker in R1. Its stated residual is appropriately narrow and fail-closed: two absent sibling paths at equal depth under one physical parent are not admitted as a preview unless the caller pre-creates a distinct directory or selects a path under a distinct existing parent. The included preview path remains usable when the canonical directory exists, as it does in this checkout.

## Required evidence still outstanding

The candidate remains virtual. Root must requalify the three exact preimages at application time, apply the patch, and run the focused mirrored tests and Ruff. The full canonical 106-entry generator `--check`, plus the actual sibling-schema-corruption and recomputed-manifest-row removal controls, remain UNRUN. The preview selected-content check and its zero-callback behavior also remain UNRUN. Until those outputs are retained against the applied source, this review does not establish `verification_missing` as closed or support a global E02 finding closure.

Pattern pass: P29 is addressed structurally by callback/resolver counts and byte snapshots; P35 keeps the complete registry denominator source-bound; P38 replaces resolved-string equality with physical identity; P39 includes the mechanism and both mandatory companions; P40 classifies this as the same filtered-scope class, second finding, and widens the mechanism across output forms rather than adding an alias exception. No formal G finding is adjudicated here.
