# ENV falsifier output-scope decision

This is a patch-only review artifact for the current E02 candidate. Parent supplied checkpoint `9194` as the intended source baseline; I did not inspect Git state. No source patch was applied and no harness or test was run.

The current harness at `LOCAL/raw/environment_v2_falsifiers.py` SHA-256 `65267dcc6d937668ef5892b2cd6bfdc473e6a64a5254daf3879def33c07ce3ca` accepts only `--output-parent == LOCAL/raw`, then creates its run directory before checking the baseline. The external route plan at `LOCAL/r4-workload/composed-mac-tool-external-consumers-plan-20261010-r2.json` was SHA-256 `df9ce854ac25ec01dff6c7ca0d1d2e52e0caf3c8a7ac5236dba2dca3b4f2e747` at inspection and supplies a command-owned ENV directory below `LOCAL/raw`. Its current plan value is WIP and must be rehashed/rebound by R4 after the agreed argument update. The raw wrapper and environment adapter inspected were `composed_mac_capture.py@9a3e67d963d84c9475f9f9d04df14392501bb3c43d36cfe587b45485be15de81` and `env_manifest_adapter.py@ba037da67a4ebf036687c5fd4a95ac3d37722358a1c1c7236762f2414126e65c`.

The supplied baseline path is:

`policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/baseline-observation.json`

Keep the command-owned root at `.../tools/environment-v2-falsifiers`, and bind `--output-parent` to its strict child `.../tools/environment-v2-falsifiers/harness`. The exact planned arguments after the script path should therefore be:

```text
--repo-root .
--baseline-observation policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/baseline-observation.json
--output-parent policy-engine/docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/environment-v2-falsifiers/harness
```

This keeps the baseline and external command capture files in the command root and puts the harness’s UUID run output under `harness/<uuid>`. The plan’s exact `argv` must be updated before its source-manifest freeze; this note does not authorize treating the present WIP plan hash as final.

The unapplied patch in `LOCAL/raw/environment-v2-falsifiers-output-scope.patch` proposes a single source-bound owner derivation before any output `mkdir`: revalidate the baseline, call the real `verify_raw_source_manifest()` API with the referenced manifest path and digest, select the unique recomputed output binding for command ID `ENVIRONMENT_V2_FALSIFIERS`, verify that exact plan is also present in the manifest’s source-file rows with the same SHA-256, load the actual plan bytes, and reconcile the complete invoked argument list/cwd/script with the command’s planned values. It then checks that the current baseline and supplied output parent are both under that command’s recomputed output-directory root, and that the parent is a new strict descendant. Absolute paths, traversal, symlink components, unbound plans, duplicate owners, plan/output-root mismatch, argv drift, and a pre-existing harness parent fail before directory creation. The exact plan-byte SHA and derived roots are recorded in the eventual run summary as provenance only.

P37 basis: source-manifest identity and plan/output roots are recomputed by the existing wrapper; actual argv and cwd are reconciled against those bound plan bytes. The baseline’s source freeze, exact input denominator, command-input binding, captured command and output hashes remain governed by the existing v2 observation revalidation and baseline checks. A command `PASS` is not sufficient for ownership or for environment acceptance.

P38 property: every harness-created control/result byte must fall inside the exact output directory owned by the frozen ENV command. Current code tests equality with the broad `LOCAL/raw` directory, rejecting the valid command-owned child; changing it to a raw-root prefix or containment check would admit a sibling such as `LOCAL/raw/unowned`. The proposed check measures the property through the actual verified source manifest, wrapper-recomputed plan binding, exact plan bytes and argument reconciliation.

P40 bucket: same output-ownership class, one level deeper. The patch widens the owner mechanism to the source-bound command root and its strict descendants as a whole, rather than adding an exception for this dated directory. No additional path-specific relaxation is proposed.

Before relying on this change, root should apply/review it against the eventual frozen source and run the real command once with a complete retained stdout/stderr/metadata/output inventory. Existing 12 environment falsifiers remain mandatory and nonvacuous. Add owner-scope discriminators to that closeout: the planned `harness` strict child succeeds; owner-root-equal, sibling, and unowned `LOCAL/raw` parents refuse; wrong/missing/duplicated ENV plan binding or plan digest refuses; argv/output-root drift refuses; traversal, absolute unowned path, symlink component, and pre-existing harness parent refuse before any directory is made. These are additional ownership controls, not inferred passes from the existing 12. The V5 partial-only mode is not part of the supplied frozen ENV argv; to run it, bind a separately reviewed command plan rather than bypassing this gate.
