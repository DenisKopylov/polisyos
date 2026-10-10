# Independent final-wave manifest caller and ENV binding review

Date: 2026-10-10. Review was read-only. No manifest builder, ENV harness, test, or Git command was run, and no manifest/output receipt was produced.

## Inputs read

- Caller: `LOCAL/raw/prepare_final_wave_manifest.py` SHA-256 `bf29fcee75c3234bb150368d77b36c67dd5a0c5716ff9cd62b55a1e4f4298ab0`.
- Existing API: `LOCAL/raw/composed_mac_capture.py` SHA-256 `9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81`.
- Applied ENV harness: `LOCAL/raw/environment_v2_falsifiers.py` SHA-256 `03c471471d694eafa135b9049bc861231861f3a95121d6f58b4bef757dc69fce`.
- Approved ENV output-scope patch: `LOCAL/raw/environment-v2-falsifiers-output-scope.patch` SHA-256 `9fa715805a2f0e92908ade359202d9264fe6dbe9c0150fa1bd9e7aa15ba3f4d0`.

## Manifest caller

The current caller makes the primary plan required and supports repeated, explicit `--additional-plan` values. It rejects symlink paths/components before resolving, rejects duplicate resolved paths, hashes all supplied plan bytes before and after the existing `prepare_raw_source_manifest` call, then calls `verify_raw_source_manifest` against the returned file hash and requires `status == PASS`. The existing API enforces product-root plan paths, validates each plan, requires output-binding-only DTOs to be named as extras, checks the product-Python constraint on executable plans, derives output roots from validated commands, scans the complete raw import root and declared local source paths, and recomputes plan/output bindings during readback. No route inventory is imported by the caller.

For the parent-specified six-path invocation, the current input files are present regular files (none is a symlink):

| Role | Path below `LOCAL/` | SHA-256 |
|---|---|---|
| New primary | `r4-workload/composed-mac-final-replay-plan-20261010-r2.json` | `ceff2fd9dc3f8706117e86f63a05ffc1e945958174717e4279ca65ecc8e58ed4` |
| New supplement | `r4-workload/composed-mac-final-supplement-plan-20261010-r2.json` | `c74a05534834468fd6aeb2efb996e7ba5b3fdc9898affa73ce0e403fc0934004` |
| Prior base | `r4-workload/composed-mac-current-source-replay-plan-20261010.json` | `48512a6a40a43a3d6c4d2723b2cb6ecde34d6725251ab03187ebd69b0b9e430a` |
| Prior supplement | `raw/composed-mac-current-source-replay-plan-20261010/supplemental-light-gap-checks.json` | `67199b1ad751cafd275732abc9d49a1607a2ed237214278267befa694398d1b2` |
| Self-test plan | `r4-workload/composed-mac-tool-selftest-plan-20261010-r2.json` | `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957` |
| External-route plan, updated | `r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` | `e2078784e2d046e01102bc5953cf8ce71e7e363326e33a58d8f1906ed284e2fd` |

The chosen primary is a canonical plan with no embedded `_source_plan_paths`; both supplements' declared base plans are also explicitly present in the six paths. The supplement adapter validates each `base_plan` reference and contributes its declared source paths. Thus this intended input set does not depend on hidden plan-route enumeration.

The caller is generic and does not itself assert exactly six paths or particular plan IDs. I found no recorded invocation of this helper in `LOCAL`; the six-path command is the parent-specified planned invocation, not an observed execution. Final preparation should preserve that exact explicit list. The prior caller readback before the symlink guard was SHA `31d42b611b982cc321f8441a287e6851aee7785ab2b78d6d6a7162f7a89f48c5`; current `bf29...` rejects symlink components before resolution.

## Applied ENV output-owner binding

Static comparison of the applied file's changed sections with patch `9fa715...` found the approved behavior present: it requires `--output-parent`; revalidates the baseline and source manifest; derives one ENV command from recomputed plan/output bindings; verifies that the external plan is byte-bound and has the typed `external_output_binding` command; compares the actual argv and cwd to the plan; derives the command output root; requires baseline/output paths beneath that root; and creates no output directory until these checks succeed. The final summary carries `output_owner_binding`. This is fail-closed ownership binding, not an execution or closure receipt.

The earlier external plan bytes used absolute values for `--baseline-observation` and `--output-parent`, which the harness correctly rejected as non-repository-relative. The current external plan SHA above changes those two argv values to repository-relative strings while retaining the same declared command output roots. They now match `_owned_repo_path`'s input contract and the harness's exact argv comparison. This closes the static argv mismatch; the changed plan must be included by the final six-plan manifest preparation.

At review time the specified baseline observation file and harness output parent are both absent. That is the expected pre-run state for the output parent, but it means no baseline admission or ENV run can be claimed yet. The authorized final invocation still needs a present, source-valid baseline observation beneath the declared command root, a freshly generated/read-back manifest bound to the current six plan hashes, exact planned argv/cwd, and confirmation that the harness child output parent remains absent immediately before it runs.

## Verdict and boundary

**Static GO** for the explicit six-plan caller and the current ENV output-owner path shape: no implicit plan-route selection or source/profile admission bypass was found in the intended invocation, and the previous absolute/relative mismatch is corrected in the current external plan. This is not a manifest-preparation receipt or a harness result; both remain unrun in this review. P40 is **same class, deeper**: the output-owner property is now checked at the harness boundary, and the plan's current relative argv satisfies that check. No production authority or formal closure is asserted.
