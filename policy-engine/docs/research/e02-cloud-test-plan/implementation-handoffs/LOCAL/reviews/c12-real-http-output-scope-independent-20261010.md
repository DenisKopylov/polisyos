# Independent review: C12 real HTTP output scope

**Review result: static GO for the helper output-root delta; no runtime receipt and no G acceptance.** The patch makes the witness require a new absolute case directory outside its fixed model/profile tree and routes all explicit witness outputs through that directory. The selected plan invocation matches the new CLI. Before the final source/input freeze, reconcile the stale standalone command recipe described below.

## Exact review inputs

- Patch: `LOCAL/raw/c12-real-http-output-scope.patch` @ SHA-256 `a666173ee65c8cc99a3a4f202fba05fa49e4b407a7355429616d61c619831984`.
- Helper preimage, unchanged in the worktree: `LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.py` @ SHA-256 `b7e656b6f0653821228d5ca5ee2f2521893df419a8a782e8c156a289ce6833ab`.
- Selected external-consumer plan: `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` @ SHA-256 `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747`.
- Scope decision: `LOCAL/decisions/c12-real-http-output-scope.md` @ SHA-256 `a171e3018760f24fb235af2f8a671b0f3b6d2554547a5ac0994cebf4f5755543`.
- Standalone command recipe: `LOCAL/raw/c12-real-encoder-profile/real_legal_http_witness.command.txt` @ SHA-256 `f7794c16e44c8b942347d99721cb71465b4842eb82bedc549823ea3a7f211e26`.

## Property and evidence

The patch changes one source path and makes no deletions. It removes the UUID-named run directory beneath the profile, adds required `--case-root`, expands `~`, refuses relative paths, refuses existing paths including dangling symlinks, resolves the candidate and rejects equality or ancestor/descendant overlap with the resolved profile root, then reserves the leaf with `mkdir(..., exist_ok=False)`. The fixed profile is `LOCAL/raw/c12-real-encoder-profile`; the plan-selected case path is a child of the C12 command output root and is outside that profile.

In the unchanged helper body, `run_root` parents the fixture database/output, three generated embedding/index generations, runtime CAS, runtime cache, and result JSON. The producer still builds and selects entity, fact, and provision generations, checks the generation/member basis, releases the producer, and loads a distinct fresh encoder. The positive HTTP search still asserts vector mode and `fact-1`; the stale fact-generation intent still asserts text fallback with `query_profile_stale_or_mismatched`. The model/profile reads remain rooted at the existing profile and are not redirected into the case directory. The patch does not edit the producer, query intent, encoder identity, API, or either semantic assertion.

The plan's `C12_REAL_LEGAL_HTTP` argv explicitly supplies the new `--case-root` under `.../tools/c12-real-http/case`; the command output root is `.../tools/c12-real-http`, and the plan requires a complete recursive inventory of that root. Both that root and `case/` were absent when checked. The plan remains `plan_only_output_binding_routes_not_execution_receipts`; `final_commit`/`final_tree` are null, its shared input manifest is not generated, and no command was run here. This is static path/contract review only.

## P40 and remaining source-recipe drift

P40 bucket: **NEW_CLASS — stale invocation recipe/input binding**, not a second case-root escape. The selected plan has the correct new argv, but the standalone `real_legal_http_witness.command.txt` still invokes the helper without `--case-root` and redirects stdout/stderr into the fixed profile. The plan's `freeze_input_manifest.source_input_paths` still includes that file. This does not invalidate the plan's selected argv or the helper patch, but it leaves two incompatible invocation records in the frozen input set. Before final freeze, update the recipe/capture path to the selected invocation or mark the file historical and remove it from the selected source-input set; regenerate and read back the final manifest.

The output-scope claim also depends on the selected plan's path binder rejecting symlink components before invocation. The case-root helper resolves existing ancestors and rejects profile overlap, while exclusive leaf creation closes the absent-leaf race. Static review does not establish the binder's runtime behavior or that libraries create no incidental files outside the explicit roots; final command capture must inventory the complete output tree and compare pinned input bytes after the run.

## Verification boundary

Read-only review used the patch and listed source/plan artifacts, SHA-256 reads, and an existence check for the planned output paths. No source patch was applied; no test, helper, model, or HTTP request was run. The C12 heavy witness remains `UNRUN`. The plan's eventual source/profile freeze must bind the applied helper bytes, current product import tree, isolated interpreter/package origins, and all nine model asset hashes before a real run. This review makes no claim of live-production currentness, legal authority, grounding, or G closure.


## Applied-recipe confirmation (read-only delta)

Root subsequently applied the reviewed patch. Readback confirms the helper is exactly the expected candidate bytes at SHA-256 `95b787162b0bab57be00ad6847f80fe1802754124226a64832b90d46472c241a` (13,413 bytes). The current `real_legal_http_witness.command.txt` is SHA-256 `dfecf3d000742e721edaff5e4cfd905d5b58f0ee0b66aa6ab1d81f82590eb234`; it invokes that script with `--case-root` at the same case path selected by the plan, uses `-B` and single-thread/offline environment settings, and has no shell redirection into the fixed profile. The old recipe is retained separately as `real_legal_http_witness.command.historical-7574.txt` at its original SHA-256 `f7794c16e44c8b942347d99721cb71465b4842eb82bedc549823ea3a7f211e26`.

This resolves the previously recorded `NEW_CLASS` recipe drift for the current command record; the historical recipe is clearly named and remains available as historical evidence. The plan still uses the same case path beneath its command output root and still has no final source/tree or generated freeze-input manifest. No helper, model, HTTP request, or test was executed during this delta review. The witness remains `UNRUN`, and the earlier static-only scope conclusion does not upgrade to a runtime or authority claim.
