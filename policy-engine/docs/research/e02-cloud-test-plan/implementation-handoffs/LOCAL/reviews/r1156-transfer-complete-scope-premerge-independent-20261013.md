# Independent review: R1119 transfer scope, pre-merge

Verdict: **BLOCK this frozen candidate for the planned native wave.** The virtual patch adds a deterministic contradiction between LessonRegistry.query_with_transfer and its own positive test. This is a static finding; I did not run pytest, import the product, or execute a runtime probe.

## Packet and source boundary

- Patch: raw/r1119-transfer-complete-declared-scope-reconciliation-20261013/candidate-r1119.patch @ fd7674b9a42f7130e6eccf094299b077b39091234da0dd5b8dbc14d83ddf6e48.
- Manifest: raw/r1119-transfer-complete-declared-scope-reconciliation-20261013/manifest-r1119.json @ 0865b0b5cebd1ef7701d9c278bc7c88a7bef1cacccef3b1716168bb1c888838d.
- Frozen source-pre/post inventory: raw/r1119-transfer-complete-declared-scope-reconciliation-20261013/source-prepost-r1119.json @ 0ee0552b66480a8facd170023c7fc55125df60cd8c0c66068259f4c288aa600c.
- Current root readback: HEAD 4ba921b8241afa732d69d6b7ef8c6c43af9bc58d, tree 45e8e04359ac64f554e45cb26ea054f8c857f38e; source frame root-author-source-frame-r1172-20261013.json @ 785f588be67983a6de503efe8fb64307caf1693d5af6134386da718d9974a66b.

I checked the manifest preimages against all 11 actual target files. Ten non-controller targets still match exactly. The controller is a known R1137/root overlap: the frozen patch expects 99e992117d5a042344fa0912e957509ce0735a98526abb3c88176d5d9e237e6d; the current root-owned controller is c6f41ec5139dbf0fa665a7f55fcdb6a89cc849a489af59e8bfddf1a116614cf5. Thus this is a review of the frozen virtual candidate, not an instruction to apply its old controller hunk directly. The overlap is known and must be recomposed by the root.

## Blocking property failure

In the candidate lessons.py, LessonRegistry.query_with_transfer at new line 550 resolves the target at line 561 by passing both transfer_context=target_context and run_id=context.source_run_id or "unknown". The new shared resolver validates the typed target and records its explicitly-set run_id from model_fields_set; it also records the explicit run_id keyword, then compares declarations in transfer_context.py at new lines 504-525. A normal query with an unset optional source run therefore turns absence into a second, conflicting declaration.

The candidate test test_versioned_lesson_scope_distinguishes_none_global_and_foreign at new line 85 constructs LessonQuery(task_family="policy", limit=10) with no source_run_id. Its positive call at new line 128 invokes fresh.query_with_transfer(...) with a target TransferContext(..., run_id="target", ...); line 134 asserts that the result is nonempty. The resolver receives the typed declaration target and synthetic keyword declaration unknown, so it raises TransferScopeRefusedError(INVALID_REQUEST_SCOPE) before lookup. The new positive control cannot pass as written.

This is P38: the intended property is reconciliation of present request declarations, while the consumer actually supplies a synthetic sentinel for an absent field. For P37, the target run_id is recomputed from the validated typed object and its model_fields_set; source_run_id is absent in the query; unknown is consumer-generated and is not evidence of a declared source run. The run-identity gate should not treat that sentinel as a caller declaration. Cross-tenant permission remains not_established.

## P40 bucket and remaining review

Class: SAME_CLASS_DEEPER, the same scope-intake/presence class as R1107-F1. R1107-F1 already recorded this class at the P40 stop point, so this is a worked example, not a reason for another per-leaf repair round. Still, the exact R1119 packet is not GO: it contradicts an added positive semantic test. Any disposition must widen the shared intake/call boundary for the complete resolver-call quantity or explicitly bound the residual and run its falsifier; it must not silently retain a test that is guaranteed to refuse.

Other reviewed controls are coherent at the patch level: R1107-F2's empty-tenant-hash positive fixture is removed while malformed empty hashes remain refusal cases; typed/mapping scope fields and explicit None tenant declarations are reconciled; schema-1.0 profileless history stays unbound and refuses fresh admission. I found no second independent escape in the reviewed 11-path virtual stack.

The author reports Ruff, AST, and compile checks for the virtual Python postimages; I did not rerun them. Runtime/pytest/native/generated-surface checks are UNRUN. This review grants no semantic or G closure; closure_ids=[]. The remaining external permission claim is not_established, and N9-to-Champion remains bridge_missing.