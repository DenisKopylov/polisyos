# Independent review: current 204-path I001 import-order slice

## Decision

**Static GO to commit the exact 204-path import-only slice as one source boundary, with runtime verification pending.** This is a same-class deeper review (`P40: SAME_CLASS_DEEPER`) and is not a test receipt, a native-gate closure, or G acceptance. Keep the 105 non-I001 paths and the nine I001 postimage anomalies outside this source commit.

The source-boundary label must say that import execution order changed. Calling this cohort “alias-order-only” would be inaccurate: the full-source AST reconciliation found module-target sequence changes in 201 of 204 files. After widening review to those complete sequences, I found no concrete internal import cycle or import-time registration divergence in the source inspected. Third-party import initializers and the actual composed application paths have not been executed.

## Exact input and source boundary

Review entry was branch `codex/e02-unified-local-20261009`, HEAD `405e685b72f94455f93a5f0d9848a4df68ffd3e2`, tree `459f2205dd90d1ff23c87ea673f9c73b0692be2e`. The worktree already contained other authors’ changes; I did not modify source or run tests.

The full path/hash matrix is `LOCAL/raw/i001-held-cause-current-20261010.json` at SHA-256 `f031f508027aa4ab85557cf6b4da33f2b8377243d0a8d2f688f40015136712c8`; that inventory records `observed_head` `214e56201613f1098e9791aac4d7b4ec0f57c30e` and its selector `git diff HEAD --name-only -- '*.py' '*.pyi'`. The reviewed cohort is its 204 rows whose `first_cause` is `i001_patch_ordered_import_events_changed`. I independently compared those exact paths with current HEAD/worktree bytes: current HEAD matches each row’s `head_sha256`, and working bytes match `worktree_sha256` (204/204 each). The complete source/test/tool denominator and type counts are recorded in `LOCAL/reviews/source-boundary-triage-20261011.json` at SHA-256 `ea8f322434079383accd34f457568dc5fbf65d45f2ddd5748470eed98ad29714`: 52 product-source, 142 test, and 10 tool paths for this class. Those records retain the exact per-path hashes; this review does not duplicate the matrix.

The 204 rows all parse and retain identical non-import AST, scoped import-binding multiset, comment-token sequence, and `__all__` assignment signatures; all 204 have changed ordered scoped import-binding events. I compared AST import statements from `git show HEAD:<path>` with the current worktree bytes, separating module-execution statements from imports nested in functions. Across the complete 204 paths, all-AST import target sequence changes occur in 201 files and distinct-target first-order changes in 193; 3 preserve target sequence while changing imported-name order; and 9 change the count of AST `Import`/`ImportFrom` nodes through split/regroup. For module-execution lexical order (module/class bodies and guarded module-level control-flow, excluding `TYPE_CHECKING`), statement sequences change in 194 files, target sequences in 185, and distinct target first-order in 179. In the 52 product-source files, module-execution statement sequence changes in 52, target sequence in 51, and distinct target first-order in 50. Separately, deferred function-local import statements change in 11 files. These are full-set counts over the raw 204-path list, not sampled results.

## Order and initialization review

I built a static internal `polisyos` import graph from source AST, excluding `TYPE_CHECKING`-only edges, and compared reordered target pairs across the 52 changed product-source files. There were zero reordered target pairs inside a runtime-mode strongly connected component. An exploratory graph that included type-only edges produced three apparent scientist/search/context cycle pairs; `context.py` declares those relevant claim imports under `if TYPE_CHECKING`, so they are not runtime import edges. This is static graph evidence, not proof that all import-time behavior is inert.

I inspected the changed package/lazy-facade cases found by resolving the `from` targets against current package initializers:

- `src/polisyos/data_forge/kernel/snapshot/finalize.py` now requests the two Data Forge names before importing kernel IO and Merkle targets. Both facade names map to the same `_impl.provenance_manifest` owner; `data_forge.__init__` eagerly loads the read API/version and resolves those build-time names through its explicit lazy map. The prior independent 221-path review inspected this exact source-level route and found no back-edge or registration; it did not execute it. The current exact source pair is in the cited raw matrix.
- `src/polisyos/runtime/quality/scholar_academic_evidence.py` splits `normalize_scholar_academic_evidence_report` into a second `from polisyos.scholar` statement. All requested names map to the same `_impl.evidence` target in the package lazy map. The first name resolution imports that owner module; subsequent resolutions reuse it. No distinct lazy owner order is introduced.
- `src/polisyos/scientist/governance/calibration.py` imports three suite ID names from the backtesting facade before a direct import of its `adversarial` module. Those suite IDs are eagerly re-exported from `.adversarial`; the facade’s `__getattr__` handles different optional helpers, not these names.
- Five changed scientist-node imports request `nodes.builtins.errors`. That name is not in the lazy node-name dispatch; the package `__getattr__` raises for it and import-from falls back to the real `errors` submodule. `errors.py` contains constants, with no registration or dependency on engine-context initialization.

Other order changes I inspected included Fabric’s `security` export package, Foundry backend/compiler imports, and scientist planning/translation facades. The package/module code inspected defines contracts/classes/constants and does not register them into a shared mutable registry at import time. The changed source imports also have no internal runtime-mode SCC pair after removing `TYPE_CHECKING` edges. I found no concrete order-sensitive behavior that blocks the source-only commit.

## Runtime evidence still required

No import, test, lint, or gate command was run for this review. The source-level result does not establish third-party initializer equivalence or a real consumer result. After the 204-path source freeze, retain source-bound fresh-process/importer evidence for the changed package/facade and backend/compiler paths, including the existing targeted checks referenced by `LOCAL/reviews/native-i001-name-and-group-independent-20261010.md` (that review’s file SHA-256 is `650307b36dd1819e7b41ee17ad3bb272de236a7b86931c219c61cf7e26e5d7f1`). At minimum, exercise the current snapshot-provenance finalizer, Scholar evidence reader, builtins error import path, Foundry checkpoint/compiler imports, and the changed translation/planning modules in their normal tests. Preserve any unsupported backend as `SKIP`/`UNRUN`; do not report it as inherited or green.

The original static review covered a broader 221-path historical proposal with different preimages. I reused only its exact inspected `finalize.py` source route and its explicit runtime follow-up guidance. Its broad static GO is not treated as a runtime receipt for this current 204-path composition.

## Review command/results record

Read-only checks used the current checkout, raw snapshot, and Git blobs:

- `git rev-parse HEAD` → `405e685b72f94455f93a5f0d9848a4df68ffd3e2`
- `git rev-parse 'HEAD^{tree}'` → `459f2205dd90d1ff23c87ea673f9c73b0692be2e`
- Python AST/hash census over the raw JSON selector → 204 selected; 204 HEAD SHA matches; 204 worktree SHA matches; structural property counts as above.
- Scope-aware Python AST import census over those 204 files → 201 all-AST target-sequence changes / 193 all-AST distinct-target first-order changes; module-execution lexical order changes in 194 / target sequence in 185 / distinct-target first order in 179; deferred function-local import sequence changes in 11; 3 alias-only target-sequence matches; 9 statement-count changes. Product-source subset: 52 module-execution statement changes / 51 target-sequence changes / 50 distinct-target first-order changes.
- Static `polisyos` import-graph comparison across changed source modules, excluding `TYPE_CHECKING` blocks → 0 reordered target pairs within a runtime-mode SCC.

No product changes were made. Formal adjudication remains with G.
