# Capture self-test owned-output scan patch decision

## Finding and bounded repair

The current frozen wrapper (`composed_mac_capture.py`, SHA-256 `9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81`) has two self-test source scans at lines 3832 and 3847. Both pass only the synthetic command's output roots to `discover_local_source_inputs()`. The real self-test has verified manifest-owned output directories elsewhere under LOCAL; the root's retained census confirmed that traversing one of those historical roots reaches a pytest symlink directory reported as `symlink_directory_in_import_root`. The actual standalone self-test passed manifest and output-owner admission, then failed at line 3848 on `after_output_sources["issues"] == []`.

The unapplied patch at `LOCAL/raw/composed-mac-selftest-owned-output-scan.patch` combines `prepared_source_binding["declared_output_roots"]` with the synthetic command roots for both before/after scans. This uses output ownership already verified from the pinned manifest and command DTO. It does not skip LOCAL, `LOCAL/raw`, or an unbounded path class. The existing self-test controls remain: new output roots must be absent before creation; a synthetic generated symlink and target must appear in the output inventory; source files and source-alias sets must be stable across that output; a precreated source-bearing output is refused; and an untracked source path outside the synthetic output roots still fails identity evaluation.

No patch was applied and no test or product command was run for this preparation. Root's existing exact stderr remains at `LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/capture-selftest/capture-wrapper/stderr.txt`. Its failed run created `.../capture-wrapper/self-test-artifacts`; the wrapper requires that artifact child to be absent, so the same output location cannot be reused. Keep that failed receipt and its outputs intact.

## Resume boundary

Do not add resume or prior-output admission in this patch. `refuse_unadmitted_unselected_outputs()` rejects a preexisting output root when selecting a later subset, and the supplement's readback-history binding currently points to the old base plan. Root's current base output contains only the completed primary `SOURCE_MODULE_READBACK`; it is not a safe same-plan `--start` receipt for the changed queue. The bounded route is one fresh full queue: preserve the readback-only output according to root's availability procedure, create fresh primary/supplement/self-test R3 plan copies with all output roots absent, bind the new supplement to the new primary, and run the full 19-command primary plus 11-command supplement once. Do not forge a history event, skip the source-readback guard, or claim `--start` works. This is a documented harness limitation, not a request to weaken the guard.

## Freeze and input companions

Applying the patch changes the tracked wrapper input, so the current root-pinned source manifest cannot be reused. After review/application, root must create the new source freeze and regenerate the manifest against the resulting source bytes and plans, then use fresh output roots. The current manifest file is `LOCAL/raw/composed-mac-final-source-inputs-20261010-r2.json` with file SHA-256 `da4b6907b177f20cc7bbfda746181be429af177b2e997f5da7c75ccd1ead6c4e`; it binds these six current plans:

- `LOCAL/r4-workload/composed-mac-current-source-replay-plan-20261010.json`
- `LOCAL/r4-workload/composed-mac-final-replay-plan-20261010-r2.json`
- `LOCAL/r4-workload/composed-mac-final-supplement-plan-20261010-r2.json`
- `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json`
- `LOCAL/r4-workload/composed-mac-tool-selftest-plan-20261010-r2.json`
- `LOCAL/raw/composed-mac-current-source-replay-plan-20261010/supplemental-light-gap-checks.json`

For the fresh run, root plans to bind those existing six plus its three new primary/supplement/self-test R3 plan copies (names not yet supplied). The only product source hunk in this patch targets `LOCAL/raw/composed_mac_capture.py`; the manifest, source-tree identity, and R3 plan bindings must be refreshed after source review. Do not treat the unapplied patch artifact or this note as a new executable input.

P40: the historical-output scan was a same source/output-ownership class gap; the patch widens the self-test scan to the complete verified output-root set once. The resume gap remains explicitly bounded by a fresh full-queue run. No closure or successful self-test is claimed.
