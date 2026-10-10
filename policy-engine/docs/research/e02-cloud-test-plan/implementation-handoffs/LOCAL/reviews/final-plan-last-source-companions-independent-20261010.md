# Independent review: final-plan last-source companions

**Disposition: block application pending a narrow correction.** This was a read-only review; the patch remains unapplied. No capture CLI, pytest collection, test, source-manifest generation, or Git operation was run.

## Exact inputs

- Patch: `LOCAL/raw/final-plan-last-source-companions.patch` — SHA-256 `47ad9689d9069d3e97a2b2dc347530333547fb94a4f7433cd8414138a70ecee4`.
- Primary preimage `LOCAL/r4-workload/composed-mac-final-replay-plan-20261010-r2.json` — SHA-256 `eae051fdf3a5bfcade7c08bb0c90a090e36b7bc4d8debab9bc9c8fd6820ade36`.
- Supplement preimage `LOCAL/r4-workload/composed-mac-final-supplement-plan-20261010-r2.json` — SHA-256 `d5edbb3027daefbbc25bc7e38952c7aa97d0af821af43195ef6fd69f2386e237`.
- `TASKS.json` confirms the register-wide `original_denominator` is 282 findings / 291 criterion occurrences. Its Q0 `finding_ids` array has 206 entries.

## Findings that pass

The diff widens existing command 9 (`V3_ACTIVE_ACQUISITION_SERVED_HISTORY`) and supplement command 6 (`Q1_CAN_MAPPING_RAW_IR_PROFILE_AND_VIEW`). It adds no queue command or output root and changes neither command order nor the one-thread numerical environment. The final source commit/tree and supplement execution-freeze fields remain null. The plans still describe unrun work and require final-source selector/input rebinding; the patch makes no result or closure claim.

V6 now names command 7 (`V1_V2_N4_CHILD_AND_HISTORY_UNITS`) in addition to B13. The selected root-client GET tests are present in `test_control_service_di.py`: they exercise a persisted successful N5 result, tenant-scoped CAS readback, actual blob corruption refusal, and the later failed sibling checkpoint. The task-map limitation remains synthetic and does not promote this to authentic source/profile authority.

The C12 direct-input pointers exist and the four supplied hashes match readback: readiness note `c470105927b9a6f7a6e79357bbbcadc4d10e070b9d728afdafbf3895c7c9cd18`, command `.txt` `f7794c16e44c8b942347d99721cb71465b4842eb82bedc549823ea3a7f211e26`, nine-file asset manifest `191a71ec41bc1a69665fffccb5fa7f1c30b3f94ccd60f71cc3ed1f074ecb98ca`, and package-origin profile `22220b814714b9ac7cc811174d4bae895884b6f3184e6a21fcec48f572aaff7f`. The manifest names nine files totaling 2,261,765,112 bytes. This is an input inventory, not evidence the model or HTTP witness ran; the separate C12 capture still needs its own fresh output-plan binding and before/after hashes for all nine assets.

The separately authored tool-self-test plan exists at the path added by the patch; its readback SHA-256 is `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957`. Binding it before manifest generation is consistent with its synthetic output roots. The root-reported external-tool plan (`df9ce…`) remains a separate binding-only plan for seven external runtime commands: it is not execution evidence and is not part of the 19+11 queue.

## Corrections required before application

1. **Keep Q0’s task-specific count distinct from the register denominator.** In `TASKS.json`, the Q0 row has 206 assigned finding IDs; the 282/291 values are the whole-register denominator. The proposed replacement drops the 206 scope and places the global denominator in the Q0 row. Preserve both facts, for example: “Q0’s 206 assigned finding IDs remain criterion-specific; across the full register, the denominator is 282 findings / 291 criterion occurrences. This queue closes none.” The explicit no-closure rule and `formal_closure_ids: []` remain correct.

2. **Complete the scoped direct-input list for the newly selected tests.** The plan explicitly says its manifest covers declared direct inputs, not the full transitive import closure. The additions nevertheless omit files that the newly selected tests directly import or read:
   - `test_acquisition_world_growth_chain.py` imports `src/polisyos/runtime/http/services/acquisition_action_service.py`.
   - `test_storage_protocol_boundaries.py` imports `src/polisyos/core/artifacts/registry.py`, `src/polisyos/core/compiler/report.py`, `src/polisyos/core/registry/builder.py`, `src/polisyos/core/registry/loader.py`, `src/polisyos/ir/kernel.py`, and `src/polisyos/ir/linker.py`. Its `PROTOCOL_BOUNDARY_FILES` also reads `src/polisyos/core/compiler/report.py`, `src/polisyos/core/registry/builder.py`, `src/polisyos/core/registry/builder_from_fragments.py`, `src/polisyos/core/registry/loader.py`, and `src/polisyos/core/run/context.py`; only the last is already in `source_input_paths`.

   Add those exact missing paths to the direct-input manifest. This is a bounded addition for direct imports and source files inspected by the new test, not a demand to enumerate every transitive import. Recompute the plan hashes and review the resulting bytes after that correction.

After these two edits, re-read both target files, recompute their hashes, and re-check that only the existing V3/Q1 routes and their current output roots changed. Keep the freeze fields null until root supplies the final source identity.
