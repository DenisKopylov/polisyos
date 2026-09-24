# Phase 0 Reissue Audit

## Discrepancies first

This is a read-only inspection of the Phase 0 merge at 73c656744f051d9f40667da7f8bc91c61d8b4ebf (E02 00d946c2b + main 5fd3ebcc1), repeated on candidate branch codex/e02-r2-held-review. No tests, gates, owner writers, or generators were run.

The committed trust-posture projection is stale against the merged source: the recorded source inventory has 126 paths; direct SHA-256 comparison of every recorded content_digest with current tracked bytes yields 112 equal, 14 mismatched, and 0 missing. Its own live_repository_freshness is not_established, and its page accessibility receipt is blocked with replay_establishment not_established. The exact mismatched inputs are below. Each row gives the recorded digest, then the current file digest.

| Tracked source path | Recorded SHA-256 | Current SHA-256 |
| --- | --- | --- |
| src/polisyos/core/contracts/runtime.py | 6cd47f5f0517d018a74a6cd42c67b8b078c9399a6c3b2bd980f72f1b0e1d5e44 | efa4c1416a651199a3c76b757f924e6818e0d8871c16b90b3b9a9412dbcc6bf9 |
| src/polisyos/data_forge/domains/academic/batch/best_snapshot.py | 54a8504817ecdd29c67a806e97eb5964288019bdfd3d5e4ae95034a8b155d3a7 | 2d45e808711c42254cf8da0e3d67df1a9b53c9f6c931f2aa6a7c2b68b3e05140 |
| src/polisyos/foundry/data_plane/bindings.py | ce409dc776cf89be6df817a6037933c77a51524bc492d87e0a69374a1dea5b6d | 454bf9ea7b2cf79eec13f4ca06f00a21c6e62055c6d854709a5921180e9be416 |
| src/polisyos/pdc/_impl/layer2_design_search.py | a1ce7a010c9183835940134f1d257c7c55d9508c0cc6239a3a34b6893573b4f1 | 914a86f4179e736ab56e49b8e750307f544bcfd30d3eca71bc940ee287dac3c4 |
| src/polisyos/runtime/http/openapi_contract.py | 477cb53c8ec421c492d4dcccaa82261676fa998a08608bb8b5d29c0c3a84b60f | d0223be603ecdde252a96ded5970f2fedfecf3099401a3a8608bb70fd27b1e3c |
| src/polisyos/runtime/quality/acquisition_planner.py | 9079a8e29745559ff10b33f53c9ca480c534f3190575f38976dc697c8ade75a3 | 143c7139b4cf388d2d0960cdaecbbd1f6b1205db863e9494ba618e8c9d4fe228 |
| src/polisyos/runtime/quality/data_forge_binding.py | 3b2c511d2f5a8adac86d45267252c9ae25c1c8a149fcaf411fee55ee079012b6 | a6091cdb0cd9490dd5f86d046afc122663390223290dfc8f162af6cdcef742ac |
| src/polisyos/runtime/quality/design_axes/outcome_prediction.py | 0024b1abd7ac64ef2240f1a9c72684a5e0948fe33cc01e891f47c9444b676df1 | ab0c9c125124c4273ba0d696c912c7434d77e3b987480bab456dd38d753846da |
| src/polisyos/runtime/quality/design_axes/value_choice_provenance.py | 9308670836cb8eb0c690f277e1ec4f082ee052499c5c80789402ea090933ae22 | aec0bbae140b8c5e4176fc1b13c7b5525c6b4dfd8e20f9637a3be29031a7f5e2 |
| src/polisyos/runtime/quality/generation_cycle.py | 7f4eeb68239be05955bd470451f6de7813134690bd5f653d6a74259e880f4aa3 | 8ea492a13d35847d048dff8db87c1ed8711611741a2f9b1f96ba821da0f6e33e |
| src/polisyos/runtime/quality/joint_simulation_horizon.py | cc7635b5b7a9ee57dae326506524d22ef1085ba4051434f55c7d5d7b85689886 | 6a77e82e6422c59859796c427cfb6aa1ba841c5fdd6ecaa8986dadd0c3a7ee7e |
| src/polisyos/runtime/quality/proving_ground/causal_forecast_search.py | 33489489a0e6b6e2f00d7ee2a99e0cd310ef6d125ad3282c8b65c56c1d8fe14c | 8b9444f5c4662bb2b518c2bf9491c68bef786d555ed1634c2bf2bea374f02602 |
| src/polisyos/runtime/quality/proving_ground/substrate_grounding_search.py | 6e47c1d6b930df97308cbf3ec4dd9df3614c10445d91249bc7daff907a24cd0a | 076b0be55356e34e556765f3d2daba3ec8d60e6e2dcdd6811a6c793b301ce831 |
| src/polisyos/runtime/quality/workspace/loop.py | 921af88b4d6b8d0d14953655486e2ea6b381149b5b870547799301e159a30b52 | ba4f847b29052e76ae67676e69b39b17fe6f49155b758373e86fd1b17ccc5e09 |

The trust-posture artifact is policy-engine/apps/runtime-dashboard/public/atlas/trust-claim-posture.v1.json @ 38f8b0b40ca439aa5e52cf39b3c8cda894391db6. Its slice_base_ref is f935e0c2e9359bc1202ce5d36ea706de58f7aaab, register_as_of is 2026-09-17, source_set_digest is sha256:f3e2d28aa2bbad7d94b785d4f145c1cc687d1478710c34273efed2a317494e96, and payload_digest is sha256:71185157bf7ecf2fd40df98ebaab7e1508a142769ffed62b3a98653c58538592. The posture owner is team-architecture; its writer is policy-engine/tools/quality/validation/check_trust_claim_posture.py @ 416252d6ba3495063d2ea181693970e67907230e. The normal write path is that owner’s --write mode. The --check closure signal only reconstructs committed projection bytes; the artifact explicitly says live repository freshness is not established. Current freshness verdict: stale source pins measured; overall currentness UNRUN / not_established.

## Runtime identity and GY artifacts

There is no standalone tracked canonical loaded-runtime manifest. policy-engine/src/polisyos/runtime/quality/confidence_ledger.py @ c3775ce0a96966fcbc46fa243e5cc03f3a80c84b builds _IMPORT_TIME_LOADED_CODE_MANIFEST at process import. Its deployment baseline includes pyproject.toml @ cca033814076335ee0e089e2797522ec434313e7, uv.lock @ 8ab2864e371a710f39f3a8f8b36b4d7fd4344cb2, and the authority import closure. The guard compares loaded code and disk against that import-time baseline. No fresh process admission was run, so current loaded-runtime identity is UNRUN / not_established. Re-derive through the owner in a fresh process after the merged tree is frozen; do not hand-write a manifest.

Three tracked GY outputs carry identity or epoch inputs and are unchanged between main and the Phase 0 merge:

| Output path @ git blob | Owner path @ git blob | Inspection |
| --- | --- | --- |
| policy-engine/architecture/policy_design_case/layer3_gy_promotion_contract.json @ 3a53eb1a73a07ed3c8910854b98d11cc6e67728c | policy-engine/tools/quality/validation/check_layer3_gy_promotion_contract.py @ 16dd37b38fddcc7b5f182d041ed7e520311c3ab8 | N9 promotion receipts contain deployment_identity, head refs, and comparison schema/rule versions. |
| policy-engine/architecture/policy_design_case/layer3_gy_intervention_substrate_contract.json @ d42bd03aff1573b434348a46859ca3d2a4419800 | policy-engine/tools/quality/validation/check_layer3_gy_intervention_substrate_contract.py @ 9be44b37eb8f8a9d26e914ce0fd68fcac084845c | Source-derived substrate contract, schema v4. |
| policy-engine/architecture/policy_design_case/layer3_gy_confidence_ledger_contract.json @ 58a81301ba500bf2ff9c5aaed765a4d9365a17b3 | policy-engine/tools/quality/validation/check_layer3_gy_confidence_ledger.py @ f18726c6d7896450089c0a992d6fe701d2894fd6 | N11 contract repeats deployment_identity in four projections. |

The N9 promotion output embeds deployment_identity sha256:ba88b7495b40d32fffd03a6992ef9ffc7a60830334ec03693acb1adcfb444eff in three projections; the N11 contract embeds sha256:53618d6b3dba9590997d9bea42713f878dc6bcbca777f26d6db65fe8d9e3db03 in four. These are environment-derived identity digests; their difference alone is not evidence of a defect. The synthetic N9 receipt projections also contain epoch_validity_projection: null. No owner check or reissue was run, so GY currentness is UNRUN / not_established.

The relevant open register row is merged-lanes-need-a-reissue-path-neither-lane-declared in policy-engine/docs/plans/active/DEBT-REGISTER.md @ 2c59d765fd53d8b363ab0a5b96ec121d71b0f727. It records the prior merged-lane write refusing with promotion_comparison_admission_manifest_drift and names only four authorization predicates: corr input, credal input, v3-to-v6 comparison, and v6 source/scope epoch. The architecture ruling already says lane transitions should be declared from their shared merge base. The missing fifth merged-state predicate belongs to runtime/quality: it must state the merged premise, admissibility, and what is preserved from both predecessors. Only after that owner-authored transition is present should the normal writer run. The two owner commands are check_layer3_gy_promotion_contract.py --write and check_layer3_gy_intervention_substrate_contract.py --write; the N11 command is check_layer3_gy_confidence_ledger.py --write. No artifact should be restamped manually.

## Raw runtime client census

At main 5fd3ebcc15637e98bbd4938de5d62ee5004504a8, the literal source-path census covered 3,949 tracked code files under policy-engine/src, apps, and packages (.py, .ts, .tsx, .js, .jsx, .mjs, .cjs). It found no production import of the raw generated runtimeApiClient.ts/js modules. One package-owned self-test imports ./runtimeApiClient.js; a separate integration test contains a synthetic raw-client import fixture. Root imports of @polisyos/runtime-api-client resolve to canonicalRuntimeApiClient.js/.ts per packages/runtime-api-client/package.json @ dfa28841133283414ab747f18731dc844cb9652d. The test-only raw reference does not identify a production consumer.

## Inputs and unresolved-by-construction

Inputs were the tracked Phase 0 tree, the recorded trust-posture artifact and its 126 embedded source digests, owner source and CLI definitions, the tracked GY JSON outputs, and the register row. The candidate worktree had no tracked modifications during this inspection. Hash comparison measures byte equality only.

Not measured here: a fresh import-time loaded-runtime admission; current verdicts from the trust-posture, N11, N9, or intervention-substrate gates; a current page accessibility receipt; and the newly authorized fifth merged-state transition. Those remain UNRUN / not_established until their owners produce and read back the authorized evidence. No tests, gates, generators, epochs, receipts, plans, or register files were modified or executed.
