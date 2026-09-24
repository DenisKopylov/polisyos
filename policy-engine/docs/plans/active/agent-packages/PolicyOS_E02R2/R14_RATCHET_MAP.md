# R2 sibling witness found during R14 review: Wave 5 historical reference replay

## Classification

This is a same-class R2 witness, discovered while expanding the all-touched-test denominator. Do not open a separate regression class. R2's property is that a persisted record remains historically valid independently of current checkout state, while currentness is a separate typed question. The Wave 5 consumer makes the same mistake at a sibling boundary: it treats a historical `repo://` reference as valid only when that path exists in today's checkout. The R2 map must include historical reference resolution for immutable manifests, not only generation-cycle receipt validation.

This is not the R3 projection-serialization defect and not R13 acquisition routing. Its owner predicate is historical artifact replay. R2's generation-cycle deployment identity mechanism is relevant, but insufficient by itself here: the Wave 5 manifest has no recorded source revision or content digest for its referenced files. The missing capability is an owner-issued, replayable binding from this immutable manifest to its as-of source identity, usable without a live source checkout. No such binding was established in this inspection.

## Exact P41 witness

The exact test key is `tests.repo_quality.tools.test_policy_design_case_capability_ratchet::test_wave5_exit_records_i5_manifest_and_influence_boundaries`. The test file has the same Git blob (`7c4b73fb339f36b21bcc430c1260f35d76a745d6`) on all four bases. The P41 checkpoint records this same key as follows:

| Base | Commit | Same-key result | SHA-verified JUnit artifact path |
|---|---|---:|---|
| E02 execution base | `78187878ee188ff6d27442ba1498bd094da9785b` | pass | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/e02_execution_base/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml` — 6,451 bytes, SHA-256 `24ac90ee7118270b65ce28bad68a9dc884c9e9a13e763732d6af5a522f8ad86b` |
| E02 head | `00d946c2b7d052522be092f9c70eb9902f6521c2` | fail | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/e02_head/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml` — 12,122 bytes, SHA-256 `13d44f90d391fe6cfa7f1d13471767c41e743848d6383085a5662431384e4542` |
| main | `5fd3ebcc15637e98bbd4938de5d62ee5004504a8` | pass | `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-pre-repair-20260924T144020Z-80143/cells/main/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml` — 6,437 bytes, SHA-256 `4aebe1a1e5ed2b8672686870c97fca4b56d7899b95c781b4f2c0d66f58eab140` |
| Phase 0 merge | `73c656744f051d9f40667da7f8bc91c61d8b4ebf` | fail | `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/cells/phase0_merge/test_policy_design_case_capability_ratchet-1208f704fe80.junit.xml` — 12,128 bytes, SHA-256 `ef86ba29e19625866b81baf79d1d82be4c25fa57323788d3b3fefeb55141b2d4` |

These are the checkpoint's per-case rows, not suite-level verdicts. I rehashed all four JUnit files at the paths above; each matched the checkpoint's recorded SHA-256. The execution-base, E02-head, and Phase 0 XMLs had moved from scratch into the package's gitignored `raw/` directory; main remains at its direct scratch path. The failing XMLs confirm the same assertion and code described below. The durable relocation inspection is `policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/P41_ARTIFACT_RELOCATION.md@f60fe1b2c44dbc5c6164a06d2f3c326ac174406a` (commit `5376f7847`): it checked 113 checkpoint rows, all 109 JUnit references (61 direct, 48 relocated), four safety skips with no JUnit by construction, and zero unresolved artifacts. It read `progress.jsonl@sha256:868f0cf3aad030a00827dc136f525c73d8af9ee1e700628e0bac4e4709f35317`. Its complete path/SHA remap is `/Users/deniskopylov/.codex/scratch/e02-r2-p41-artifact-remap-20260924.json@sha256:4f0e2848ec8f83079cc9b20bcbb29aeee90c51d73f3b8cb2d616dad4b9b907be`. That receipt is an in-flight snapshot, not the final baseline verdict.

## Failure and complete input denominator

The test reads `architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json`, checks the manifest's closeout fields, then recursively sends every `repo://` string to `validate_repo_reference`. A complete traversal of this exact manifest finds 36 reference occurrences across 30 distinct target paths. The manifest blob is identical on all four bases (`fa16e56d90fcfb6b90d8de56cb261ae00f69a95d`). Of those 36 references, exactly one target is absent on E02 and Phase 0:

`$.artifacts_produced[0].surface_refs[3]` → `repo://packages/runtime-api-client/runtimeApiClient.ts`

The path exists at the execution base (blob `dfbc37f0ab6aa203cdb4aee4e60434223272306a`) and on main (blob `6bf389e633eacdde0208ee3426e59cc6c3de9262`). E02 deleted it; Phase 0 retains that deletion. `validate_repo_reference` returns issue `capability_repo_ref_file_missing` with “repo reference … points at a missing path,” and `_assert_repo_refs_resolve` asserts that the issue is `None`. The E02-head JUnit confirms the exact assertion: `assert {'code': 'capability_repo_ref_file_missing', 'message': 'repo reference repo://packages/runtime-api-client/runtimeApiClient.ts points at a missing path.', 'path': '$.artifacts_produced[0].surface_refs[3]'} is None`. Phase 0 records the same failure.

The deletion is the only changed input needed to explain the same-key transition: test blob, manifest blob, and validator blob (`1cd361b73a01e7ed7668d18b92a4491e335d8628`) are constant across all four bases. P41 attribution is therefore E02-owned: execution base passes, E02 head fails, and the main control passes. The Phase 0 merge inherits the E02 red; this is not an environmental red.

## Property, implementation, divergence

- **Historical property:** the immutable Wave 5 closeout manifest remains replayable against the source evidence it described when it was accepted; present-day source availability/currentness is reported separately.
- **What the consumer tests today:** `validate_repo_reference` resolves `repo://` under the current `repo_root`, checks containment and `target.exists()`, then optionally checks a text anchor. It accepts no source revision or content digest.
- **P38 divergent case:** main retains a file at the old path and passes this check even though the E02 package README states that the low-level `runtimeApiClient.*` pair is generated in private scratch and is not a committed or public package surface. Presence alone does not establish historical bytes or current public ownership. Conversely, E02 removes the current path while the immutable manifest still names it and the check fails, even though the package's canonical `canonicalRuntimeApiClient.ts` remains present and exported.

The manifest is explicitly registered as a source-committed historical governance record. Its registry rationale says such records are immutable inputs, are not current execution receipts, and are not regenerated or promoted under a later owner. Therefore do not repair this by restoring the retired raw twin or rewriting/restamping the Wave 5 record. The safe class-level direction is to extend the historical-reference owner path so the immutable manifest resolves through an as-of, content-bound source identity; current references continue to require current path/anchor validity. Whether an owner-issued sidecar can supply that historical binding is not established.

## Required probes and controls

- **Observed removal probe:** the raw twin is absent on E02/Phase 0 while the manifest's `status`, capability markers, and `surface_refs` remain unchanged. The same-key test turns red, and the checkpoint records it as failed. This shows the check is not merely accepting marker strings.
- **Required replay falsifier before closure:** remove or alter the as-of bytes/binding for the historical raw-client reference while retaining the immutable manifest and all its markers. A historical resolver must return a typed failure. Current evidence cannot run this probe because no as-of content binding exists.
- **Property-preserving control:** with the raw twin still absent, a currently bound reference to the canonical package entrypoint (`canonicalRuntimeApiClient.ts`) must resolve and remain the exported TypeScript client; the historical manifest must also replay through its historical binding. This guards against converting ordinary candidate/package use into a refusal while keeping current and historical predicates distinct. This control is specified, not run.

## Safe write set and owner handoff

No source or test file was changed for this diagnosis. Before implementation, widen the R2 write lease to cover the historical `repo://` resolver, its recomputing validator and tests, and any owner-issued historical binding record. The current manifest path is registered under `policy-engine/architecture/generated_artifacts.toml` as an immutable source-committed member of the historical governance record family, with owner `team-runtime-quality`; the evidence-path table names the same owner. Follow that owner and inspect the generated-artifact registry/freshness delta if a new sidecar or resolver output is added. Do not edit the debt register or plans. Keep the package README/export route and the absence of the raw twin as the preserving control.

Relevant tracked inputs at the inspected commits:

- `policy-engine/tests/repo_quality/tools/test_policy_design_case_capability_ratchet.py@7c4b73fb339f36b21bcc430c1260f35d76a745d6`
- `policy-engine/tools/quality/validation/check_policy_design_case_capability_ratchet.py@1cd361b73a01e7ed7668d18b92a4491e335d8628`
- `policy-engine/architecture/policy_design_case/wave5_i5_external_consumer_truth_manifest.json@fa16e56d90fcfb6b90d8de56cb261ae00f69a95d`
- `policy-engine/packages/runtime-api-client/README.md@5772d3ab213e8f44a32ceef0de15f6d63d94bacb`
- `policy-engine/packages/runtime-api-client/canonicalRuntimeApiClient.ts@9227640d31e58a3d05572127c5399bf3e4a4bddd`
- `policy-engine/packages/runtime-api-client/package.json@dfa28841133283414ab747f18731dc844cb9652d`
- `policy-engine/architecture/generated_artifacts.toml@9c0f1dfdac86dd02f16d3b17c5bd28da4e0f9165`
- `policy-engine/docs/reference/policy-design-case-evidence-paths.md@df7c0637b4985e82532bc271fc40f1b10a19d6c8`

Pattern pass: P06 (retired low-level compatibility/generated twin remains in evidence), P07 (historical rule/evidence replay), P29 (a path marker is not historical content proof), P38 (current path presence is a proxy for historical validity), and P41 (four-base ownership replay). The live behavior measured here is reference validation; it does not prove the semantic or public status of the API client.
