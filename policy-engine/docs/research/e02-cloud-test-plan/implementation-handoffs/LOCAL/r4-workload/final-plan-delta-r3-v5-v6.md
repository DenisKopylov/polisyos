# Final replay-plan delta: R3, V5, and V6

This is a **patch-only, unapplied** plan delta against the R2 primary and supplemental plans. The exact primary base is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-final-replay-plan-20261010-r2.json` (`b7bb8bdcc1cfba5d7dffa183fbfd59b8a48387e93995dcb7f3aba047a03aba05`); the supplement base is `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-final-supplement-plan-20261010-r2.json` (`2e0c5e02776c5af1c0a616984f9dc8fc92a8cbb7ceea688ac9330e28423b6f83`). The patch updates the supplement’s candidate-source label only; its 11 commands, selectors, and output roots remain unchanged. The queue remains 19 primary commands followed by 11 supplemental commands.

The primary-plan command delta is limited to three existing rows:

- `R3_MONETARY_AND_HISTORY_GET` retains all current monetary/cost targets and appends the **whole** `tests/unit/runtime/quality/test_authority_reconciliation.py` module for canonical selected-profile, durable-event, attestation, and foreign-view controls.
- `V1_V2_N4_CHILD_AND_HISTORY_UNITS` retains the current real V6 selector `tests/unit/runtime/http/test_control_service_di.py::test_fresh_run_details_get_keeps_n5_and_failed_sibling_checkpoint`. Its purpose now identifies the root-client, actual-child, persisted-source, and fresh-reader path while preserving the bounded source/profile authority statement.
- `V5_NATIVE_DR_B157_L4_80_L3_40_L4_80` now selects the **whole** `tests/unit/scientist/methods/autotune/test_methodjob_execution_work_packets.py` module under its existing `POLISYOS_RUN_NATIVE_METHODJOB_WORK=1` gate. This covers the original direct 80/40/80 witness and the pending native GP/DR/MethodJob/CAS/Search/WarmStart joined witness. The separate `V5_NATIVE_GP_METHODJOB_CAS` GP-profile command remains unchanged.

The source-input manifest appends 93 direct imported production and test-helper paths used by the R3 authority, V3 integration, V6 control-service, and whole V5 work-packet test modules, plus the reviewed V5 native-join imports. The selected-test denominator adds the whole R3 authority module; the V3 real integration target and V6 real selector are retained. This is a direct-input manifest, not a claim of full transitive-import closure. The namespace-only import `tests.unit.runtime.quality` has no standalone file to hash; concrete modules are included where they resolve to files.

The primary and supplemental source labels now name the pending R3/V3 canonical/integration, V6 root-client, and Search source-guard work. The primary known-uncommitted input list records the exact paths supplied for those pending slices. Command order, concurrency (`max_parallel_commands=1`, one numerical thread, one pytest worker), thread-limit environment, all output roots, and the 19/11 command counts are unchanged. The V5 whole-module run remains in its existing single serialized heavy slot.

The primary `final_commit` and `final_tree` remain null; its freeze-input manifest remains ungenerated until root supplies the final freeze; every primary command remains `UNRUN`; the supplement remains `plan_only_not_receipt`. This patch is not an execution or source-freeze receipt.

Artifacts:

- Unapplied patch: `LOCAL/raw/final-plan-delta-r3-v5-v6.patch`
- This note: `LOCAL/r4-workload/final-plan-delta-r3-v5-v6.md`
