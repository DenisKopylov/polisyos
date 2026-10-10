# Independent review: final plan last-source companions

**Disposition: GO to apply this plan-only delta; NO-GO to execute any route now.** The final source freeze is still null and the primary plan still requires the pending native/V3 source composition. The patch remains unapplied. This review ran no tests, capture/validation CLI, source-manifest generator, or Git operation.

## Exact inputs and readback

- Patch `LOCAL/raw/final-plan-last-source-companions.patch`: SHA-256 `9e84749c1804da6bc167b882fdbbe21113859f418ea5462865c0cfe0d8c77a1f`.
- Primary plan preimage: SHA-256 `eae051fdf3a5bfcade7c08bb0c90a090e36b7bc4d8debab9bc9c8fd6820ade36`.
- Supplement plan preimage: SHA-256 `d5edbb3027daefbbc25bc7e38952c7aa97d0af821af43195ef6fd69f2386e237`.
- External consumers plan: `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json`, SHA-256 `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747`.

## Delta assessment

The prior Q0 wording issue is fixed: the row now retains its 206 assigned finding IDs and separately states the register-wide denominator of 282 findings / 291 criterion occurrences. I counted the Q0 IDs from the named `TASKS.json` row; the global denominator matches its `original_denominator`. The no-closure wording remains intact.

The V6 map now routes through command 7 as well as B13. The named command-7 selectors in `test_control_service_di.py` exercise a real local root-client `GET` after persisted N5 production, verify the tenant-scoped CAS result, reject a corrupted blob, and preserve the successful child beside the failed sibling checkpoint. The task remains explicitly synthetic and does not claim authentic source/profile/context authority.

The V3 route widens existing command 9 to the full acquisition-world-growth integration and unit modules plus the served GET/corruption selector. The Q1 supplement widens existing command 6 to the whole storage-protocol-boundary module. These are existing routes: the patch adds no command or output root, and changes no ordering or one-thread settings. The relevant direct sources, test/helper modules, five storage-boundary source-inspection paths, registry builders, and IR kernel/linker package entrypoints are now listed. The input list is explicitly scoped; it does not claim a complete transitive import closure. The new test modules and their direct local module/file references are covered by the listed inputs.

The final commit/tree and execution-freeze fields remain null. The plans continue to label the selectors unrun and require final-source input rebinding. No PASS or finding closure is implied.

## External-plan boundary and remaining execution gates

The external consumers plan is **binding-only**: it says `capture_cli_execution_compatible: false`, `no_execution_performed: true`, and `heavy_runs_allowed_now: false`; its source freeze is also null. It contains seven external output-binding entries, with unresolved runtime inputs and owner-specific capture needs. Treat those as planned routes, not executable commands or receipts, and keep their output roots separate from the 19+11 queue.

C12’s readiness note and package-origin profile exist; the nine-file asset manifest hash is `191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca` and names nine files totaling 2,261,765,112 bytes. The current witness script and command recipe are present in the patch’s direct-input list. Their current hashes are `95b787162b0bab57be00ad6847f80fe1802754124226a64832b90d46472c241a` and `dfecf3d000742e721edaff5e4cfd905d5b58f0ee0b66aa6ab1d81f82590eb234`; the readiness note still embeds the older values `b7e656…` and `f7794c…`. The separate external plan already requires a final-freeze rebind of the patched script, runtime profile, and nine assets. Keep C12 unrun until that rebind (and the note’s stale digest statements) is resolved, with per-file asset hashes before and after and its own output-plan capture.

**P40 classification:** the earlier Q0 denominator and directly inspected/imported source omissions are the same class; the current delta closes those listed instances. One bounded deeper residual remains outside the stated direct-source scope: `tests/_helpers/acquisition_chain.py` loads the WDI recording through `tools/quality/validation/check_layer3_gy_design_generation_contract.py`, which reads `architecture/policy_design_case/layer3_gy_design_generation_replay_recordings.json`; neither the loader nor recording is separately enumerated in the primary plan’s `source_input_paths`/`fixture_inputs`. Do not call the manifest a full runtime closure. The commit/tree fields bind committed content, but the planned `SOURCE_MODULE_READBACK` only imports modules and records their paths; it does not check clean worktree state or hash that recording. Before execution, root must verify the checkout is clean and matches the frozen commit/tree, or add the loader and recording hashes to the manifest and enforce their pre-run readback. The falsifier is to alter the recording after freeze while leaving declared inputs unchanged: the current module-readback command would not detect that change. This remains an execution gate while the freeze is null; it does not block applying the plan-only delta.

After application, read back both files, recompute their hashes, and confirm the command IDs/order, output roots, thread caps, and null freeze fields. Keep all route execution gated on the root’s final freeze and serialized-slot release.
