# Independent review: output-binding-only plan admission

Review status: **NO-GO on v1; awaiting the execution-admission companion.** This is a read-only static review of the exact patch artifact and its source preimage. I did not apply the patch or run tests, capture commands, model code, or Git operations.

## Inputs

- Product candidate HEAD: `9194a65fb59355ceac35270c869f429efc7482d8`.
- Current helper/source preimage: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py` @ SHA-256 `8d4c418a7966915d45e5a4821e548fe6b80cce1cdf8fb81f7380e12b439f9454`.
- Reviewed unapplied proposal: `LOCAL/raw/composed-mac-output-binding-admission-v1.patch` @ SHA-256 `290429cd54b6c1b2e78fdc2fa424e0577fe04b354d6482d5c824ef517ac64b0a`.
- Author decision note: `LOCAL/decisions/composed-mac-output-binding-admission.md` @ SHA-256 `d5753c21986ad590ac385762bdfbcca082ea084367dc8ea109acfc508baa862f`.
- External plan bytes: `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` @ SHA-256 `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747`.

## Finding

The output-root binding proposal is directionally sound for the explicitly additional external plan, but it does not close the plan-kind boundary at execution admission. The external plan is explicitly `plan_only_output_binding_routes_not_execution_receipts`, sets `execution_mode.capture_cli_execution_compatible` false and `no_execution_performed` true, and has seven commands all tagged `external_output_binding`. The proposal's classifier requires those fields and admits this plan only when explicitly named as an additional plan. It also adds each plan's declared local source paths to the manifest denominator.

However, the classifier is only called from `create_raw_source_manifest`. In the existing execution path, `main()` loads a selected plan and proceeds to output-root admission and directory creation before any plan-kind refusal. `validate_canonical_plan()` validates cwd, threading, command order/status, paths, and argv/environment shape, but does not constrain command types or `execution_mode`. `select_commands()` selects IDs only. For non-pytest commands, `actual_argv()` returns planned argv unchanged, and `run_one()` passes it to `capture_process()`. The runtime-profile guard checks only that each command's argv[0] resolves to the product `.venv/bin/python`; a self-declared external-output plan can therefore use that interpreter and pass this unrelated check. The parent's supplied counterexample additionally reports an external-output plan with product-venv argv reaching a zero-exit classification. Thus output-only admission is not currently separated from execution admission.

P40 classification: **same class, one level deeper**—plan-kind routing is being guarded at manifest intake but not at the execution consumer. One structural rule must bind both places: external-output plans are eligible for additional source-manifest binding but categorically refused as selected primary plans, including `--validate-only`, before any output directory creation or runtime profiling. This is not a reason to weaken or alter product-Python execution-profile gates.

## Properties that appear correctly composed in the proposal

- The class test is structural and nonempty: exact plan-only status, explicit `capture_cli_execution_compatible is False`, `no_execution_performed is True`, nonempty purpose/reason, and a nonempty all-`external_output_binding` command list. Missing or mistyped required fields and mixed/unknown command types fail this classifier. It does not enumerate the current command IDs.
- For an admitted external command, the patch calls `assert_command_output_roots_absent`. That helper derives command directory, separate output files, cache/receipt paths, and pytest basetemp, rejects paths outside `LOCAL/raw`, checks every path component for symlinks, and refuses any existing derived root.
- The manifest binding recomputes plan hashes and path/root associations. The overlap pass rejects equal or ancestor/descendant roots owned by distinct plan-command pairs. The patch preserves the primary product-Python check and expands explicit source paths to every accepted plan's `declared_local_source_paths`.

These are source-level observations only; the patch note correctly says the required controls have not been executed. I make no claim about package inventories, product environment readiness, or the external routes' execution compatibility.

## Required delta and bounded verification

Before GO, review an applied or exact patch delta that refuses `capture_cli_execution_compatible=False` and any selected `external_output_binding` command at the execution entrypoint, including validate-only, before `admit_plan_output_root()` can `mkdir`. Retain primary source-manifest preparation for the Python plan plus explicitly listed external binding plan. The acceptance controls should distinguish: legitimate external plan as an additional manifest binding; external plan as primary with all valid product-Python argv; external plan under validate-only; missing/true/string-valued compatibility flag; missing/malformed `no_execution_performed`; empty/mixed/unknown command types; an existing root, a symlink component, and pairwise overlapping roots. For the six-plan denominator, read back all six plan bindings and their declared direct inputs; do not infer runtime or package-profile truth from the external plan.

No code/test was executed for this review. The manifest denominator and all-root/path controls remain `verification_missing` until root binds the six plans and runs the focused adversarial probes. The external plan remains a route-output declaration, not an execution receipt or a Python runtime profile.

## V2 delta review

V2 delta review status: **GO to apply and run the focused controls; not a runtime/test PASS and not a closure decision.** This review inspected the patch only; no patch was applied and no tests or commands were run.

- V2 patch: `LOCAL/raw/composed-mac-output-binding-admission-v2.patch` @ SHA-256 `0025294599ba1a9f9b560b49adeb50d9a7760aa625eb9343bac8c1f8e36799b9`.
- V2 author note: `LOCAL/decisions/composed-mac-output-binding-admission-v2.md` @ SHA-256 `fbdb1e5683ff7c09fce797bf201b69e7815a6cf13261f52236a46f0c73f92383`.
- Source preimage remains `LOCAL/raw/composed_mac_capture.py` @ SHA-256 `8d4c418a7966915d45e5a4821e548fe6b80cce1cdf8fb81f7380e12b439f9454`; candidate HEAD remains `9194a65fb59355ceac35270c869f429efc7482d8`.

The v2 delta closes the v1 execution-admission gap structurally. `_require_capture_cli_selected_plan()` is invoked for both primary-plan paths: source-manifest preparation immediately after `load_and_validate_plan()`, and execution/`--validate-only` immediately after plan load and before `admit_plan_output_root()`, `output_root.mkdir()`, or lock acquisition. The predicate refuses the exact output-only status, any `external_output_binding` command, and any present non-dict `execution_mode` or mode whose `capture_cli_execution_compatible` value is not the boolean `True`. Therefore a forged product `.venv/bin/python` argv cannot make the external plan selectable. The preparation guard also runs before preparation writes asset/source manifests. This is the right boundary for the parent’s discriminator.

The additional-plan path remains separate: an exact output-binding-only DTO is accepted only as an explicitly named extra; it is rejected as primary, must pass the exact status/mode/no-execution/purpose/reason/all-command classifier, and each command’s derived output roots are required absent and symlink-free. The existing root-escape checks and cross-command overlap rejection remain in `_command_output_roots` / `_manifest_output_bindings`. All additional plan `declared_local_source_paths` are unioned into the source manifest set. The primary plan’s product-Python admission remains intact.

Malformed mode controls covered by the source predicate include a missing compatibility field, false or non-boolean value, a non-mapping `execution_mode`, or any exact output-only / external-command marker, even when other fields or argv are altered. The predicate is intentionally not a schema validator for arbitrary unknown extra keys inside a mode dictionary; no execution-mode schema for ordinary plans exists in the reviewed source. That bounded fact does not reopen the reviewed external plan, whose status, false compatibility field, and external command types are each independently rejected at selection. Root’s adversarial controls should still exercise malformed/missing mode values and ensure refusal occurs before any output-root/lock creation.

P40 classification: **same class, deeper level addressed by widening one plan-kind boundary across manifest intake and selected-plan execution**. No per-plan executable exception was added. Acceptance remains `verification_missing` until the root applies this exact delta, binds the six plans and complete declared input denominator, and runs the requested focused positive/refusal/root-path controls. Do not interpret the external plan’s argv, commands, or this static review as a Python package profile, execution receipt, or evidence that its separate backends are ready.
