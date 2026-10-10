# Independent review: ENV v2 falsifier output ownership

Disposition: **GO to apply and run the bounded source-bound controls; no runtime or acceptance result is claimed.** This is a static review of the patch against the named source and actual planned input paths. The patch was not applied and the harness/tests/model were not run.

## Pinned review inputs

- Harness preimage: `policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/environment_v2_falsifiers.py` @ SHA-256 `65267dcc6d937668ef5892b2cd6bfdc473e6a64a5254daf3879def33c07ce3ca`.
- Proposed patch: `LOCAL/raw/environment-v2-falsifiers-output-scope.patch` @ SHA-256 `9fa715805a2f0e92908ade359202d9264fe6dbe9c0150fa1bd9e7aa15ba3f4d0`.
- Author decision note: `LOCAL/crosswalk/environment-v2-falsifiers-output-scope-decision.md` @ SHA-256 `dee05583c09af419bf4c6d02459fab5355b708ffdc9ccd1d72c03af1c9685b48`.
- Current wrapper used by the proposed bind call: `LOCAL/raw/composed_mac_capture.py` @ SHA-256 `9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81`.
- Current environment adapter: `LOCAL/raw/env_manifest_adapter.py` @ SHA-256 `ba037da67a4ebf036687c5fd4a95ac3d37722358a1c1c7236762f2414126e65c`.
- Current WIP external plan: `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` @ SHA-256 `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747`.

The current WIP plan still has a baseline placeholder and sets `--output-parent` equal to the command output directory. The proposed harness correctly refuses that arrangement: final plan bytes must bind the concrete baseline path and a fresh strict child such as `.../tools/environment-v2-falsifiers/harness`, then the six-plan source manifest must be regenerated and revalidated. The current WIP plan is not a runnable input and its existing hash is not a final source freeze.

## Source-bound owner path

The patch replaces broad `LOCAL/raw` equality with `bind_output_owner()` before any harness output directory is created. That function takes the baseline observation’s source-manifest ref, resolves it through the repository-bound path guard, and calls the real wrapper’s `verify_raw_source_manifest(path, sha256)`. It stops unless the wrapper recomputes a PASS. It then selects exactly one recomputed binding for command ID `ENVIRONMENT_V2_FALSIFIERS`, requires the plan file itself to occur exactly once in the verified manifest’s files with the same hash, reloads that actual plan, and checks exactly one command of the expected `external_output_binding` type.

The planned command’s argv must contain the exact actual CLI arguments after the interpreter and script slots. The command’s script path must resolve to this harness file, and both the planned cwd and actual cwd must resolve to the supplied repository root. The unique output-directory root comes from the wrapper-recomputed command binding and must equal the actual plan’s `outputs.directory`. The baseline and requested output parent must be repository-relative, traversal-free, and symlink-free; both must be below the verified command root; the output parent must be a strict descendant, absent, and different from the command root. This measures the ownership property through actual source-manifest and plan bytes, not a `LOCAL/raw` prefix or a caller-provided ownership label.

After admission, the harness creates only `output_parent` and `output_parent/<uuid>`. The existing control helpers write cases, copied input fixtures, observations, subprocess logs, and the isolated replace-ref repository beneath that run directory. The external plan’s command root remains the outer owner; this child arrangement is compatible with the command’s later whole-directory inventory. The owner binding is carried into the V5 partial summary, incomplete-control-setup summary, and normal final summary. No Python package profile or runtime compatibility claim is inferred from the external command’s argv.

## Baseline and control semantics preserved

The diff leaves `baseline_evidence()`, `actual_plan_projection()`, and `make_controls()` unchanged. The baseline path is nonvacuous: it validates required evidence refs, the actual adapter observation, a resolved source freeze and reconciled exact plan-input denominator, resolved command/source and capture bindings, a successful captured command, exit code zero, and zero JUnit failures/errors. `actual_plan_projection()` calls the real wrapper verifier and requires its recomputed file rows to equal the retained frozen rows.

A source read found 12 control append sites in `make_controls()` (including the isolated replace-ref fixture): PID sidecar path, capture/receipt PID, plugin digest, sidecar bytes, candidate tree, source-manifest ref, command-output digest, forged-complete flag, unattested virtualenv owner, namespace child origins, recomputed input omission, and replace-ref object view. The patch does not weaken or remove them. `run_case()` marks explicit `NotApplicable` requirements `UNRUN`; the aggregate is `INCOMPLETE` unless the nonempty control set is all `PASS`. Baseline or output-owner admission errors print a `NOT_RUN_*` status and return nonzero before creating the output parent. Control setup failure is `INCOMPLETE_CONTROL_SETUP`; neither state can become a positive falsifier result.

One bounded diagnostic nuance remains in existing code: `import_adapter(root)` occurs before the new guarded baseline/owner block, so a missing adapter import exits nonzero without the harness’s JSON `NOT_RUN` record. It does not create the output parent or produce a PASS; the external capture must retain its stderr/exit receipt. Likewise, unexpected per-control exceptions are not the same as a passing control and must be inspected before any `FALSIFIER_EXPOSED` label is interpreted as a substantive property result.

P37 basis: source manifest digest, full source set, plan hashes, plan/output bindings, actual argv/cwd/script, and output-root relation are recomputed or reconciled. The recorded binding is evidence of output ownership only, not Python environment identity, dependency readiness, external-route execution, or formal closure.

P38 property: every byte written by the harness must be below the exact output directory owned by the frozen ENV command. The prior equality check admitted only broad `LOCAL/raw`; replacing it with generic raw-root containment would admit sibling/unowned paths. The proposed code instead requires a strict child of the recomputed command root.

P40 classification: same output-ownership class, one level deeper; the patch widens one owner-binding mechanism across the whole harness output tree rather than adding a dated-path exception. Remaining proof is the root’s source-frozen six-plan binding and the focused positive/refusal controls; this static review is not their receipt.

## Required runtime discriminators

Before treating the harness result as evidence, apply/review the patch and rebind the external plan’s concrete baseline/output-parent arguments, then regenerate the exact six-plan source manifest. Retain full external stdout/stderr, exit code, duration/RSS and recursive command output inventory. The owner child should be admitted; a command-root-equal parent, sibling, unowned `LOCAL/raw` path, traversal, absolute unowned path, symlink component, and pre-existing parent should refuse before making a harness directory. Missing/stale baseline refs, missing/duplicated ENV command ownership, wrong plan hash, argv/cwd/script drift, and output-directory mismatch must produce non-PASS `NOT_RUN` outcomes without creating the child. The valid baseline must preserve the current source-freeze/input-denominator evidence, and all 12 controls must be nonvacuous for the resulting report to say `PASS`.

No command/test/harness execution was performed here. During checkout identification I inadvertently issued one read-only `git rev-parse HEAD` before noticing the task’s no-Git constraint; it made no repository changes. No source files were edited.
