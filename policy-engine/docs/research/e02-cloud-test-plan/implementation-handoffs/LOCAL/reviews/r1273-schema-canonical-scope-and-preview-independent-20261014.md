# R1273 — Independent review of canonical schema scope and previews

Verdict: **BLOCK the exact R1254 candidate from root application/native acceptance.** The three-file patch reconstructs exactly from its declared preimages and implements the intended module-closure behavior for ordinary paths. On this actual Darwin checkout, however, the canonical-output guard compares resolved path strings rather than the filesystem target. A case-variant path aliases the canonical snapshot directory but is classified as a preview, so a filtered generation can still replace the canonical module manifest with a partial one. This is the same P40 filtered-scope class first identified in R1259, one level deeper; widen the canonical-target predicate to the physical destination rather than patching only this spelling.

This review is read-only and static except for standard-library path identity probes. I did not run the candidate tests or generator, mutate product files/index/history, or claim runtime acceptance. `closure_ids=[]`.

## Bound inputs and reconstruction

- Worktree: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`
- HEAD/tree/index: `a746e1b0b1fab1b9ae027c1c4b55eea67f95e02d` / `1355896e91789026d21396d2b087c63827ab251b`; exact current frame is `LOCAL/root-author-source-frame-r1267-20261014.json@a5403a64bcbac9d3a3038396d828bc018fcd96f348060f2150e38a89f7405803`.
- Candidate patch: `LOCAL/raw/r1254-schema-subset-global-manifest-and-check-denominator-20261014/proposal.patch@9e0759da6b542fd0c12598c2b07274b21e2fc513ae7c9a464e227d6269034abc`.
- Manifest: `.../manifest.json@9c211ecc544d14d286940b1e744ec51736b985b44f1aa5ba7302985a8aec6185`; decision: `.../decision.md@86437f68be4bae512ffb51556fd77163bda0807b830b654d9fb1eb5ade38a7db`.
- I verified the current physical hashes of all three candidate source paths against their declared preimages: `gen_schema.py` `39a833a5…191205c`, `test_diagnostics_phase3.py` `72c5e103…1d10fd`, and diagnostics `README.md` `aa508a04…a0b70a` all match. A small standard-library unified-diff reader reconstructed all three postimages in memory; each SHA-256 exactly matches the manifest (`3645dff7…0daa60`, `9ad6b700…b0868f`, `bc067b9e…f84f48`). This confirms packet binding, not physical application.

## Property review

The new `_select_run_entries` mechanism derives the active registry entries, groups selected entries by module, and compares ABI-key sets. It correctly refuses a partial canonical generation before `_resolve_entries`, cache setup, module processing, or file writes for ordinary canonical paths. A canonical filtered check expands to every active entry in each selected module, so `_process_module` recomputes sibling schema bytes and a module-complete manifest. The manifest control drops a sibling row and recomputes `content_hash`; because `_assert_manifest_equals` compares all non-provenance manifest content, the altered manifest still fails. The sibling-schema mutation control also reaches the full selected module. The 106-entry denominator is bound to `abi_models.py@8c43d8085ee94fae96d7c560bb05b2e7b7b84a6f9fca64fd60bf32b46e0d153f`: an independent standard-library AST walk gives IR 103, Fabric 2, Scientist 1, 106 total.

For ordinary custom output paths, the product code retains selected-entry generation/check behavior and skips `generate_reference_docs`; that function writes two global docs on generation and reads them on check. The implementation branch is correct for paths that really are separate directories. The new preview test does not prove this branch: its shared fixture replaces `generate_reference_docs` with an unobserved `lambda` returning `[]`. If the candidate unconditionally called the global generator for previews, that test would still pass. The partial-write test likewise checks that the canonical directory was not created but does not count `_resolve_entry` calls; the source ordering is correct, while the test does not pin its pre-resolution claim. Add spy/failing callbacks and explicit no-call assertions before treating these as behavioral controls (P29).

## Deciding P38 falsifier: path string versus destination identity

The patch’s canonical predicate is `args.output_dir.resolve() == DEFAULT_OUTPUT_DIR.resolve()`. On the actual Darwin 27.0.0 checkout, the filesystem is case-insensitive for this existing directory, while `Path.resolve()` preserves the supplied case:

- canonical: `.../policy-engine/schemas/snapshots`
- alias: `.../policy-engine/schemas/Snapshots`
- resolved-string equality: `False`
- `os.path.samefile(canonical, alias)`: `True`; both have `(st_dev, st_ino) = (16777231, 175366069)`
- the `ir` subdirectories likewise have different resolved strings but `samefile=True`, inode `175366082`.

The minimal discriminating invocation is `gen_schema.py --models abm_result --output-dir .../schemas/Snapshots` (and the corresponding `--check`). The candidate classifies this as `selected_entries`, because the canonical predicate is false. The write path `output_dir / "ir" / "_manifest.json"` is nevertheless the same physical file as `schemas/snapshots/ir/_manifest.json`. Thus the generation route can rewrite the canonical IR manifest from only `abm_result`; the check route can inspect only the selected entry and omit sibling drift. This is a source-derived outcome joined to an independently measured filesystem alias; I did not run the generator or perform the write.

The property is “does this invocation target the canonical artifact store?” The code tests “are the two resolved path strings byte-for-byte equal?” The actual divergent case is the case-variant alias above (P38). The path alias is the second same-class finding: R1259 already established that a filtered run can corrupt or misrepresent the shared module manifest/snapshot set. R1254 widens to module scope but still gates that protection on a string proxy. The mechanism needs a canonical-target check that recognizes the physical destination across aliases (including existing aliases on case-insensitive filesystems); a one-spelling special case would continue the P40 repair ladder.

## CLI compatibility and limits

The existing `verify_scm_v3.py` callers use `--models ir` and `--models fabric` with `--check --output-dir schemas/snapshots`; when run from the product root those resolve to the canonical directory and now check complete IR and Fabric modules. The deprecated `--model` mode is normalized before selection, so a single-model canonical write is intentionally refused; the documented migration is a complete-module canonical generation or an isolated `--output-dir` preview. No CLI flag shape or registry contract changes.

The current `docs/how-to/manage-schemas.md` example `--check --models claim p0 ir` remains a subset check, but the selector plus current full registry actually selects 105 rows (103 IR and 2 Fabric), omitting the one Scientist row. The new diagnostics README correctly distinguishes selected-module scope from full-registry acceptance. A future docs clarification can describe this command as checking the closure of selected modules rather than an exact model subset; it does not change the blocking alias finding.

The new tests, Ruff, generation, filtered checks, and removal probes remain UNRUN here. The R1256/1257 full generation/check receipts are valid baseline evidence but do not exercise R1254’s filtered paths. Required before acceptance: fix the physical-target predicate, add a case-variant alias falsifier on a case-insensitive filesystem, instrument the preview generator callback and refusal resolver callback, then run the retained canonical/preview and manifest/content removal controls against the exact current source frame.

P40 bucket: **same class, second finding**; widen the canonical-target mechanism to the property. P29: tests currently miss two side-effect boundaries. P35: the 106-row registry denominator is recomputed from the complete registry source, not a sample. P39: the README/test are companions to the three-path mechanism. No formal G decision or closure is claimed.
