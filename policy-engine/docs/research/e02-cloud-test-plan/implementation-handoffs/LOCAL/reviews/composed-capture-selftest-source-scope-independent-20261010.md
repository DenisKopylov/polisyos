# Independent review: self-test source scope

## Verdict

**NO-GO for the supplied-manifest → self-test → replay lifecycle.** The patch correctly verifies the input manifest and uses its recomputed plan-output roots for the local scan. However, the self-test then writes new Python import sources elsewhere under `LOCAL/raw` and leaves them there. The same verified manifest is stale after a successful self-test, so the next replay identity check rejects it.

P40 bucket: **SAME_CLASS_DEEPER**. The prior issue was an incomplete output-root basis for a source scan. This patch widens the basis to all verified roots, but the self-test creates its own source outside that basis and changes the source denominator. The whole invariant is that the harness self-test must not invalidate the frozen source input set it is asked to verify.

## Scope and evidence

- Patch artifact: `LOCAL/raw/composed-capture-selftest-source-scope.patch`, SHA-256 `14a724fb2032abe01e66ad6100196a2e9d8be2d4ba1662c5349e8a8497e95471`.
- Exact wrapper preimage: `LOCAL/raw/composed_mac_capture.py`, SHA-256 `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`.
- Patch-only, read-only review. I did not apply the patch, run the wrapper, run tests, or perform Git operations.

The positive part is structurally sound: the proposed CLI requires both `--source-input-manifest` and `--frozen-source-input-manifest-sha256`; `self_test` calls `verify_raw_source_manifest` before making artifacts; and the returned `declared_output_roots` come from `_manifest_output_bindings`, which reloads every listed plan, checks its pinned bytes, recomputes its command roots, and rejects overlapping roots. The source verifier then checks the full executable/config path set and bytes, raw import path set and bytes, named environment/package bindings, and source-profile constraints. Passing those derived roots to `discover_local_source_inputs` avoids a new alias exception or broad `LOCAL/raw` skip.

The later manifest probe also includes every distinct plan path from the verified binding list, excluding the canonical plan that it supplies directly. `create_raw_source_manifest` adds the selected plan's referenced source plans, de-duplicates paths, validates each plan, and derives output roots from the resulting binding list. Thus the code shape is generic over the binding list rather than hard-coded to two historical roots. I did not run the patch; the available `composed-mac-current-source-inputs-20261010-7574c864.json` is a historical two-binding snapshot, not independent evidence of the reported final four-binding preparation.

## Blocking counterexample

In the current preimage, `self_test` creates `root = LOCAL_RAW / "composed-mac-wrapper-selftest-<uuid>"` at line 3338. It writes `untracked-import-probe.py` under that root at line 3441, and later writes `precreated-source-output/injected.py` under the same root at lines 3574–3576. Neither path is one of the command roots derived from the actual plans; the synthetic command-root object used later exists only as a separate local fixture. The function ends by writing its receipt and returning at line 3883, without removing or relocating those Python files.

`discover_raw_source_inputs` recursively scans `LOCAL/raw` and includes `.py` files unless they are beneath a passed plan-derived output root. The pre-existing source manifest demonstrates the consequence: its raw import inventory already includes `untracked-import-probe.py` from older self-test directories, and `injected.py` from prior self-tests (for example, its entries around lines 7902–7956). A new run creates a new UUID path not present in the supplied manifest. Therefore the post-self-test raw import set differs from the manifest that was verified at entry. On the next `verify_raw_source_manifest` or command preflight using that exact manifest/hash, `same_raw_paths` becomes false and source identity fails.

The proposed `complete_manifest` does not close this gap: it is constructed and verified at line 3507, before `injected.py` is created, and is an internal synthetic manifest, not the CLI-supplied manifest. The self-test does not perform a final verification of the supplied manifest after its writes.

## Required correction

Keep the discriminator while preventing the self-test from mutating the real source set. For example, run the raw-scanner source-probe against an isolated temporary raw root or a controlled scanner root parameter, then assert the original verified manifest still verifies at self-test exit. Do not add a blanket raw exclusion or silently bless the newly written `.py` files. If the chosen lifecycle instead regenerates and root-repins the final manifest after every self-test, that refreshed manifest and ordering must be explicit; the self-test’s entry manifest would not be the final replay manifest.

No formal closure or acceptance decision is implied by this review.

## Delta review: plan-owned self-test output

This section reviews the later proposal and supersedes the preceding source-denominator finding for that proposal only.

- Proposed patch: `LOCAL/raw/composed-capture-selftest-source-scope.patch`, SHA-256 `3dd3f28bbe5565ad8ae56c922761e7952579a86b746966c40a1ef45d090f1e06`.
- Wrapper preimage remains `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`.
- Fifth plan: `LOCAL/r4-workload/composed-mac-tool-selftest-plan-20261010-r2.json`, SHA-256 `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957`; its command remains plan-only and UNRUN.
- No patch application, wrapper/helper process, tests, or Git operations were performed.

The patch closes the earlier source-denominator defect at the code level. It maps the invocation to exactly one Python command among the source-manifest-bound plans by resolving the executable and script, comparing the complete static argv after removing only the two manifest-context pairs, and requiring the output child to be a strict descendant of that command's verified `command_output_directory`. It refuses an existing child, checks the plan output roots and symlink components, and writes the self-test artifacts—including the `.py` probes—under that child. The scanner control preserves the discriminator: the probe is visible without output roots and absent with the complete verified roots. This is a whole-output-root ownership rule, not a per-alias exception or scanner exclusion. P40 for this part is SAME_CLASS_DEEPER, and the ownership widening is sufficient by static inspection.

There is still a concrete plan-to-runtime blocker. The fifth plan's actual static argv is only `.venv/bin/python`, the wrapper path, `--self-test`, and `--self-test-output-directory <child>`. The self-test branch now requires `--source-input-manifest` and `--frozen-source-input-manifest-sha256`. In the current wrapper, `actual_argv()` returns `command["argv"]` unchanged for every non-pytest command, and `run_one()` calls it without supplying manifest context before launching that argv. Thus running this fifth plan through the current capture runner launches the child without the two required arguments; the helper exits before any of the new ownership checks. This is a NEW runtime-context bridge class, separate from the repaired source-ownership class. The plan note describes an external runtime overlay but does not bind an executable caller or its receipt. A caller outside this wrapper could close the gap, but none was part of this read-only scope.

There is a related binding detail within that same runtime-context gap: `_self_test_static_arguments` verifies that runtime path/hash pairs equal the parsed CLI values and the manifest hash is then recomputed, but it does not compare the runtime manifest path with the selected plan's declared `source_scope.runtime_context.source_input_manifest_path`. The plan names a canonical path; that path is currently documentation rather than a checked predicate. If the exact canonical path is required, bind it when selecting the owner command. The digest still binds the bytes, so this is a path/provenance mismatch rather than evidence of different manifest content.

The fifth plan also requires the final source manifest to include it as an additional plan alongside the four root-selected plans. `create_raw_source_manifest` supports an arbitrary `additional_plan_paths` list, while the normal preparation CLI exposes only one supplement. The handoff explicitly assigns this preparation to a root procedure; until that procedure supplies a five-plan manifest and an invocation path that records the dynamic argv, the operational plan remains **NO-GO**. No formal closure or acceptance decision is implied.

## Delta review: capture-runner bridge for the fifth-plan self-test

This delta supersedes the runtime-context blocker above for the supplied patch and stated plan identity, subject to the root creating and validating the five-plan source manifest and running the requested controls.

- Patch artifact: `LOCAL/raw/composed-capture-selftest-source-scope.patch`, SHA-256 `606879d07b731e912215e9c602037be0a745a7401fd4cbddee9346c015223302`.
- Wrapper preimage: `LOCAL/raw/composed_mac_capture.py`, SHA-256 `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`.
- Fifth plan identity supplied/read at review start: SHA-256 `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957`. The plan was no longer present at its named path during a later reread, so this delta review relies on that initial hash and the plan content recorded in the preceding section; this is not a fresh final-path readback.
- Patch-only read. I did not apply it, execute the wrapper or helper, run tests, or use Git.

The new bridge addresses the missing caller path. `run_one` supplies its already frozen source-manifest path and digest to `actual_argv`; that function appends only the two context options when the command is Python, includes exactly one `--self-test`, and its resolved script is this wrapper. It rejects static plans that pre-supply either dynamic option, requires an absolute path and a 64-hex digest, and records both `actual_argv` and `harness_added_argv` alongside the frozen source-manifest path and digest in the existing command receipt. Non-pytest commands that are not this exact self-wrapper invocation retain their planned argv; the existing pytest basetemp insertion remains unchanged.

On the child side, `_self_test_static_arguments` removes only the two recognized context pairs, rejects missing, duplicate, empty, or mismatched values, and leaves the complete remaining static argv for exact owner-command matching. Before creating the output child, the helper verifies the supplied manifest, reloads and recomputes each manifest-bound plan output binding, matches the Python executable, wrapper script, and complete static argv, and checks that the plan's declared `source_scope.runtime_context.source_input_manifest_path` resolves to the same product-relative path supplied at runtime. It then requires exactly one match and a new strict child of that command's verified output directory. This closes the same-class source/output ownership chain with an actual caller binding; it does not introduce a broad adapter or a per-plan exception.

P40 classification remains **SAME_CLASS_DEEPER**: the previous defect was the self-test's source/output lifecycle; this delta binds the root-pinned manifest context through the real capture caller into the existing verified plan/output ownership rule. The added caller bridge reaches the whole needed quantity (the exact self-test command and its two dynamic context values), so I found no second residual requiring another patch. Static review is **GO for root application and the bounded actual self-test/negative-control run**, conditional on root creating the reviewed five-plan manifest and confirming the fifth plan's exact current bytes/path. The plan output from this review was not executed, and no behavioral pass or formal G acceptance is claimed.

## Delta review: corrected `run_one` callsite

This delta supersedes the prior patch's patch-application concern and confirms the same bridge against a regenerated unified diff from the unchanged wrapper preimage.

- Patch artifact: `LOCAL/raw/composed-capture-selftest-source-scope-v4.patch`, SHA-256 `0cb7fa5cdf5574c635f82097d52877d4297720c11422da997c8829df15815313`.
- Wrapper preimage: `LOCAL/raw/composed_mac_capture.py`, SHA-256 `c9d6c5b77335e7833323f6616de94c743bc39ec05fd62f17d68f802857aac5a9`.
- Fifth plan hash remains `7cee5538169a888bf8b6c4c3e8ef31c6a2a6a8a7618559c5310f11714260c957` per the parent-provided current-path readback. I did not obtain a fresh plan-file readback during this delta review.
- Patch-only read. I did not apply it, execute the wrapper or helper, run tests, or use Git.

The callsite correction is present in the patch: the `run_one` call passes `source_manifest_path` and `source_manifest_sha256`, which are the exact keyword-only parameter names in the current `run_one` signature. The previous patch variant's mismatched variable names are absent. There is no default/fallback substitution: for a Python command whose resolved script is this wrapper and whose argv contains `--self-test`, `actual_argv` requires an absolute supplied manifest path and a 64-hex digest, refuses pre-supplied static context options, and appends the normalized digest and exact path. The resulting list and inserted pairs are captured in `actual_argv` and `harness_added_argv`; receipt fields also bind the frozen source manifest path and hash. Other non-pytest commands return their planned argv unchanged, and the existing pytest path remains intact.

The child-side checks remain wired to the real values: it strips only the two dynamic pairs, verifies they equal the parsed manifest arguments, checks the recomputed source manifest, revalidates the bound plan/output mappings, matches one command by Python executable, wrapper script, and full static argv, then compares the supplied manifest path with the matched plan's declared `source_scope.runtime_context.source_input_manifest_path` before creating the self-test directory. It requires the self-test output to be a new strict child of the matched command's plan-owned output directory.

Verdict: **GO for root application and the bounded actual self-test/oracle run**, with the same prerequisite that the root-generated five-plan manifest and current plan path/hash are verified before execution. P40 remains **SAME_CLASS_DEEPER**; this version fixes the concrete callsite defect without widening the mechanism or leaving a second residual. This is a static code review, not a behavioral execution receipt or formal G acceptance.
