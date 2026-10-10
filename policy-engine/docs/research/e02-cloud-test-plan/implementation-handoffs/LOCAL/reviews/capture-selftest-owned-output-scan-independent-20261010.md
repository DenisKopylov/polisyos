# Independent review: self-test owned-output scan patch

**Static patch verdict: GO for root application and the planned fresh self-test/controls.** The hunk widens the scanner scope from the synthetic command’s roots to the complete output-root set verified from the supplied source manifest, while retaining the synthetic roots. I did not apply the patch, run the wrapper or tests, or perform Git operations; this is not a behavioral pass or closure receipt.

## Reviewed inputs

- Patch: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-selftest-owned-output-scan.patch` — SHA-256 `5113c56cd25734071e9c01e3bd4d57981d4c648a8d72cff41f33e06030fe76fd`.
- Wrapper preimage: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py` — SHA-256 `9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81`.
- Decision note: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/capture-selftest-owned-output-scan-decision-20261010.md` — SHA-256 `4d22c477143d09c5b3fc50c38450283ab4403bd5b26f87acc8765d5f321d48ca`.

## Review

The patch changes only the two self-test source scans: it builds `self_test_scan_roots` from `prepared_source_binding["declared_output_roots"]` plus `_command_output_roots(synthetic_command)`, then supplies that same list to both the before and after `discover_local_source_inputs` calls. This is the required whole-set correction: the verified plan output roots are retained and the synthetic fixture’s own roots remain included. The hunk neither skips `LOCAL/raw` wholesale nor adds a symlink alias exception.

The manifest roots are derived rather than caller-invented. `self_test` first obtains `prepared_source_binding` through `verify_raw_source_manifest`; that verifier recomputes output roots from the manifest’s pinned plans and requires the binding to match. `_command_output_roots` requires each declared path to be a strict descendant of `LOCAL/raw` and rejects symlink components. `_self_test_output_directory_from_plan` also proves that the self-test directory is a strict child of the matched Python command’s plan-owned output directory and belongs to that verified root set. Thus the new scan argument is bounded by already-validated plan ownership.

The existing behavioral controls remain intact. The source scan using the verified root set still requires no issues and that a generated `.py` probe under the owned self-test output is absent from the bounded source path set. That assertion detects removal of the output-exclusion property even if its surrounding markers remain. The synthetic command output must still be absent before creation; its generated symlink and regular target must appear in `inventory_command_outputs`; source files and symlink aliases must remain stable across the synthetic output; precreated output is refused; and an untracked executable outside the output roots still fails source identity. The patch does not weaken these assertions or change the inventory path.

The task-supplied census summary reports 310 prior scan issues within the six verified manifest output roots and none outside them. That is consistent with the observed code path: without the added roots, `discover_local_source_inputs` traverses those historical output directories and can classify their pytest symlink directories as source-scan issues; with the roots, only declared output locations are excluded. I did not independently rerun or recompute that census.

## P40 and boundary

**P40: SAME_CLASS_DEEPER.** The finding is the incomplete source/output ownership basis in the self-test scan. This patch widens the basis to the complete verified output-root set in one mechanism rather than adding per-directory exceptions. The independent source-scope finding about self-test-created files outside their owner root is not reopened by this hunk: the inspected preimage requires the self-test directory to be inside the verified command output root, and the hunk preserves the existing source and inventory checks.

Static review supports applying this exact patch. Root must still refresh the root-pinned source manifest after changing the wrapper and run the planned fresh full queue/controls with absent output roots. No self-test, queue, or broader capability is claimed complete here.
