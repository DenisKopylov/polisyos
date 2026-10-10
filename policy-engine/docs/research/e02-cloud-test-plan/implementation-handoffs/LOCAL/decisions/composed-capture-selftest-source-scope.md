# Capture self-test source-ownership patch proposal

Status: patch-only proposal. The helper was not changed, imported, run, or tested. The fifth plan is a plan-only binding and remains `UNRUN`.

- Target source: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed_mac_capture.py`
- Exact source preimage SHA-256: `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`
- Proposed source patch: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-capture-selftest-source-scope.patch` (SHA-256 `606879d07b731e912215e9c602037be0a745a7401fd4cbddee9346c015223302`)
- Fifth plan: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/r4-workload/composed-mac-tool-selftest-plan-20261010-r2.json` (SHA-256 `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957`)
- Tool plan output root: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-replay-20261010-r2/tools/capture-selftest`
- Self-test artifact child: `.../tools/capture-selftest/capture-wrapper/self-test-artifacts`
- Final manifest path supplied by root at runtime: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-mac-final-source-inputs-20261010-r2.json`

The earlier proposal supplied the root-derived output roots to the scanner but kept generated self-test files in a random `LOCAL/raw/composed-mac-wrapper-selftest-*` directory. Independent review showed that those `.py` and `.json` files would remain outside every declared command output root and would be read as new sources during preflight. This revision moves every self-test artifact below the fifth plan's own `CAPTURE_TOOL_SELF_TEST` output directory. It does not borrow the base or supplement output roots and does not add a `tools/`, `LOCAL/raw/`, or dated-path exclusion.

The proposed helper verifies the full root-pinned manifest before creating anything, then derives the self-test owner by matching the actual Python executable, this script's resolved path, and the complete static argument vector against validated plan bytes. It requires one match, checks the command's `command_output_directory` role in that exact plan binding, and refuses an existing, symlinked, non-child, or otherwise unbound artifact directory. The `untracked-import-probe.py` is asserted present when both scanners run without output roots and absent when the complete verified output-root set is supplied; the existing raw source-drift and manifest-removal controls remain intact.

The runtime source-manifest path and digest cannot both be part of the static argv: the digest is computed from a manifest that includes this plan. The static plan therefore binds `--self-test` and the exact output-directory argument. The proposed `run_one()` bridge passes its already-verified manifest path and SHA-256 to `actual_argv()`. That function appends only `--source-input-manifest <path>` and `--frozen-source-input-manifest-sha256 <digest>` to a Python command whose script resolves to this exact wrapper; all other non-pytest command argv stays unchanged. Existing command metadata records the complete `actual_argv` and the inserted context. The helper parses and strips only those two context pairs, compares their values with the parsed arguments, and then checks that the named manifest path equals the `source_scope.runtime_context.source_input_manifest_path` in the uniquely matching validated owner plan. The verified manifest's current plan binding and digest must still match before any output directory is created. This is a source-bound runtime invocation bridge, not a self-label or a claim that the static plan argv contains its self-referential digest.

The final source manifest preparation must bind this plan as an additional plan alongside the four root-selected old/new plans; the existing helper API accepts `additional_plan_paths`, while the current CLI only accepts one supplement path, so root must use its prepared manifest procedure for the full five-plan set.

The tool plan is separate from the 19-command plus 11-command task queue and makes no route or criterion claim. Its source-freeze fields are null; it is not a receipt, freeze, or test result. After root composes it into the final manifest and freezes source, the scoped falsifier is the self-test itself: if its generated probe appears in the complete-root scan, or if any artifact is created outside its own output child, the proposal fails. No actual browser, server, source test, or helper process was run for this patch-only task.

P40 classification: same source-ownership class, one level deeper. The first proposal closed only the local scanner input omission; review exposed that the self-test's own generated artifacts were not assigned to a plan owner. This widens the mechanism to derive the exact command owner from the entire verified plan set and requires every self-test write to stay inside that command's declared output child.

## V4 source-bound argv bridge

The prior hand-assembled patch artifact was not apply-ready and is retained only as history. V4 is a fresh unified diff generated from the exact source preimage above and the complete proposed source string, with no source application. It fixes the stale hunk context at `run_one()` and supplies the missing runtime bridge: `run_one()` passes its existing `source_manifest_path` and `source_manifest_sha256` values to `actual_argv()`, which appends the two context options only when the Python command's resolved script is this wrapper and its static argv includes `--self-test`. Other non-pytest argv is unchanged. The helper then requires the parsed path/hash to match the runtime args, verifies the exact path against `source_scope.runtime_context.source_input_manifest_path` only on the matching owner command, revalidates the selected manifest's plan bytes and digest, and requires one matching owner before creating the child output directory.

- V4 patch: `docs/research/e02-cloud-test-plan/implementation-handoffs/LOCAL/raw/composed-capture-selftest-source-scope-v4.patch`
- V4 patch SHA-256: `0cb7fa5cdf5574c635f82097d52877d4297720c11422da997c8829df15815313`
- Source preimage SHA-256 re-read during generation: `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`
- Proposed Python AST parse and compile: passed without executing the module. No patch application, wrapper process, or tests were run.
- The existing fifth plan remains the same `UNRUN` plan-only artifact at SHA-256 `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957`.
