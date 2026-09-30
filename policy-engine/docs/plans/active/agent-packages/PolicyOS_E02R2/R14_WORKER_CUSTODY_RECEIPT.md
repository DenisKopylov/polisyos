# R14 worker custody — bounded integration receipt

## Discrepancies first

- This is not full E02-R2 acceptance. Four-base whole-file replay, the remaining R1 producer fixture, promotion importer checks and final typecheck gates remain outstanding. The architecture gate ran alone and exited 1; every reported finding is triaged below, without baseline sync or epoch restamping.
- V13 admission reached 79 cases: four EvalSafety fixture failures preceded its intended authority decision because no explicit tenant/actor was supplied. The separate served acquisition case failed while its fixture finalized a run outside the artifact owner scope. The fixtures now supply a controlled owner. V17 reruns both whole files: all five cases pass, including the actual served acquisition chain.
- V15 integration stopped at collection: the newly introduced test helper eagerly imported a control-store type through the control facade, creating a circular import. The helper now delays these imports. V16 reached all five bodies; four passed and the terminal retry failed because the fixture demanded a dispatched job when it correctly expected no job. Both idle-call sites were corrected after an AST census of 2,746 test Python files and all 32 helper calls. V17 passes the five cases.
- V18 DI enumerated 41 cases: 36 pass, one fails and four stop at setup. All five reds stop before N4 at `cycle_substrate_context_job_policy_slot_unresolved`: the fixture combines five historical underscore slots with a three-slot dotted controlled profile. This is not a candidate materializer witness. R1's controlled profile contract is a separate required repair.
- V18 CYC-05 is UNRUN: collection imports the private HTTP context builder retired by the earlier R1 owner-path change. No test body ran. Historical/deployment replay needs an owner-bound fixture migration, not restoration of live-checkout authority.
- V18 architecture guardrails reported 119 bullets: one aggregate, 116 unique import edges and two generated-output mismatches (118 unique leaf findings). Four new private security edges have since been routed through the existing lazy facade. The other 109 edges have UNKNOWN_PROVENANCE until the exact earliest-slice replay. OpenAPI/trust-posture freshness and the separate UNRUN Atlas inventory gate remain recorded; no family exemption or restamp was applied.
- The final V20 whole-file wave enumerated 167 cases across ten files: 158 pass and nine share a producer-fixture setup error. The full log identifies the same unresolved five-slot problem/WMR mismatch before N4. All 148 main worker/store/projection cases, four EvalSafety admission cases, five non-producer promotion cases and the served acquisition case pass. The nine authority/source tests have not exercised their bodies; their intended properties remain UNRUN, not discharged by a review or refusal.
- The production SearchExitContract → closeout/promotion bridge is `bridge_missing`, per the independent complete source census. Purpose-aware projection is not that bridge. No positive S8, publication, current epoch or promotion claim is made.

## Property and bounded implementation

A job executes under its durable creation/admission identity and exact leased attempt. Readback is an observer. Only the handler for the matching completed attempt may publish the final proof, and it must reconcile cleared lease fields, the completion event, exact JSON proof-driving basis and transition history. It merges proof-owned fields into the latest progress, preserves unrelated updates, then commits the progress pointer, event and outbox in one control-store transaction.

The six current proof-driving fields are generic strict-JSON compared with key-presence checks; primitive type changes and absent/null substitution are refused. Source comparison deliberately excludes unrelated progress. The actual store tests exercise SQLite directly and through the production GuardedDependencyProxy; no live PostgreSQL claim is made.

## Deciding runs

Counts below enumerate every JUnit testcase, including collection-error rows. The origin inspection verdict is separate from the pytest result.

| Run | JUnit cases | PASS | FAIL | ERROR | SKIP | pytest exit | loaded source modules | test modules | frozen paths |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| r14-v13-completion | 58 | 58 | 0 | 0 | 0 | 0 | 1693 | 3 | 27 |
| r14-v13-admission | 79 | 75 | 4 | 0 | 0 | 1 | 1759 | 4 | 27 |
| r14-v13-acquisition-served | 1 | 0 | 1 | 0 | 0 | 1 | 1712 | 1 | 27 |
| r14-v14-strict-json-red | 4 | 0 | 4 | 0 | 0 | 1 | 1640 | 1 | 27 |
| r14-v15-main | 148 | 148 | 0 | 0 | 0 | 0 | 1770 | 7 | 27 |
| r14-v15-integration | 1 | 0 | 0 | 1 | 0 | 2 | 1652 | 1 | 27 |
| r14-v16-integration | 5 | 4 | 1 | 0 | 0 | 1 | 1719 | 2 | 28 |
| r14-v17-integration | 5 | 5 | 0 | 0 | 0 | 0 | 1719 | 2 | 28 |
| r14-v18-di | 41 | 36 | 1 | 4 | 0 | 1 | 1724 | 1 | 28 |
| r14-v18-cyc05 | 1 collection row | 0 | 0 | 1 | 0 | 2 | 1481 | 0 | 28 |
| r14-v20-final | 167 | 158 | 0 | 9 setup | 0 | 1 | 1782 | 10 | 32 |

Each run used the same existing offline venv, canonical source/tests, CPU JAX and native thread caps of one, unique retained basetemp, explicit Perl alarm, read-only production-data link and in-process origin plugin. Complete deciding outputs are retained at the paths below. V17 also inspects all 25 loaded test helper/conftest modules: zero foreign origins and zero changed frozen inputs. It took 49.64 seconds, peaked at 1,229,750,272 bytes RSS, and reported zero swaps. The V17 Ruff wave checked all 25 then-changed Python files and passed. The final facade/fixture source cut requires its own freeze, whole-file wave and Ruff verdict; V17 is not substituted for that cut.

## Removal and preserving controls

- V11 deterministic pre-fix readback probe changed progress while the real worker was paused after completion. V13/V15 prove the reader does not write and the worker alone finalizes afterward. This is a control-store readback witness; a served HTTP reader is separately exercised in the existing workspace tests.
- V14 retained all proof markers and changed nested `true` to `1`, or absence to explicit `null`. All four raw/guarded cases were red because publication incorrectly proceeded. V15 makes these cases refuse without progress/outbox mutation.
- V15 preserves a benign sibling progress update, an owner-bound estimate for its exact purpose, and ordinary candidate readback with declared unknown custody. It withholds whole-run approval for acquisition/repair and refuses a different estimate purpose. These projection checks do not claim an absent promotion bridge.

## Evidence paths and digests

- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-completion.junit.xml@sha256:3b02efdc8979795f907daa7ec685f3a72a34c8c2e52098915b163b60e9dac6a8`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-completion.log@sha256:ab5677c39e6b37ac7b5fa22f9d3e6173f214a901ac9c587df2d34fe39a408951`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-completion.origins.json@sha256:5995f5d122a453ca27e9383a5b6b37071f6873a60b5dd27df8e38ae4b7ebe52c`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-admission.junit.xml@sha256:e404001bb707563ebc4c4452ef323cfcb23093977accfeb98418eca5598426a3`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-admission.log@sha256:bd97bbc7ed15fdca36b3ff0dbac872bdfef46cb20f695c22d4d6ce71baf90794`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-admission.origins.json@sha256:b997a7a90ef7a1cd0e614ec1aeaae32d7847a95b7a93b07f70d0417424c692c9`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-acquisition-served.junit.xml@sha256:02ffd808323262621ea8cc6c71031dfd727dfc9b9e70130a814ef4c616459f0b`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-acquisition-served.log@sha256:3f7bb7e0c7bd98ec459e36a23debce9d91746f30442355d3052adcae8410048d`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v13-acquisition-served.origins.json@sha256:f7b9e57094e1a285a4b674b8930b5a7b9bb0d5b648326a84fb2c29aabaccd699`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v14-strict-json-red.junit.xml@sha256:1defc4bcb38183a27eeef84263d8b2044d7e476ee24188586541e7dcd7fdf2d7`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v14-strict-json-red.log@sha256:f3044ea7c779c56411075971839643ff73669cbff07850febb4e5304160c424b`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v14-strict-json-red.origins.json@sha256:ca6263c96347eb6f4e8b9dc650abb1d799b33669f0b1d554b139bef34a21bce6`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v15-main.junit.xml@sha256:18416dcd48a8e0021ce13cb158e3155118be651b350e95b1983de8d2a4cf72f2`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v15-main.log@sha256:aef76683466b12df6e88a86a0af3f4e883b2468cd8a415fbc71c02a63964df80`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v15-main.origins.json@sha256:450da33b17de9b0e6b336317766b5891402c2e6ae700d5e089e61fe10eb4e8ba`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v15-integration.junit.xml@sha256:c7abc6de8f4adf916f408489beba270a5a521d8727dde51ae1df7c5ff92dcef1`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v15-integration.log@sha256:a1a3588ad214b8e7f2e66ceaac4d12d89d25e991faf30f68d368f53e308935d0`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v15-integration.origins.json@sha256:ecd0dc8834c8b95844ec1a2f7d51d799b2e84137067aa9abaa43bb5e8fdb1c5b`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/FROZEN_INPUTS.v15.json@sha256:31c8c60558d3a8c957aa08bf7f7dbe069064bb0525055a7dbd38267910eba4ba`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_CANONICAL_V15_CANDIDATE.patch@sha256:258bef71464350996891e60b6159771f03f1941860c3c20189dc1320ba10e50f`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_V15_PROOF_BASIS_DELTA_REVIEW.md@sha256:d9a13ab0285c016025d2a95f2635a70f90afee2dd6c399a11ff264b50714c252`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_ACQUISITION_OWNER_WITNESS_DESIGN.md@sha256:203f2d0b4bb163c11796da92e42c50ad02dc25503683250bacc95648db60245f`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v11-readback-red.junit.xml@sha256:042203e4a2715a3182d27a361c4270dc6a357f894373493bc6db62c4a7ac93e1`

- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v16-integration.junit.xml@sha256:32f9c81da194ff35beb834c6663455836890296d3525a1e1108a46a1815315f7`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v16-integration.log@sha256:b7d6c7fa93a4de394dc16e8f3b4759b41267f1e2723bcc5f72cbd4ed1ab041db`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v16-integration.origins.json@sha256:f64ef7e518408530ade922f8fa3af3cb00441e9ed82cd38352648b74538b9f87`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v17-integration.junit.xml@sha256:b7da9eb69d74ed7ecb71a7957b45057ad7d3cb55fa9dffcb9d440374c8c59aa8`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v17-integration.log@sha256:f3fcd4f823877707c471275b9a1ae78be0fdef19b0588a202feea5e589ca2f61`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v17-integration.origins.json@sha256:abc0da4050f61e04873db0534e822850c3a3c896056f735d92abfe9cbd420d94`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/FROZEN_INPUTS.v17.json@sha256:59b9e21d325178d755a03502e9101c90f2abd5bc1bfde19a5887ec1178f99841`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_CANONICAL_V17_CANDIDATE.patch@sha256:eb40d9888af002795011582aef099648dc45dd9cde3c4a8fb9f95057fba984c9`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v17-ruff.log@sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_DISPATCH_CALLER_CENSUS_V17.json@sha256:0385dee29b299655ae861bbb709a7d335b0302a5bfd64137e622e9afe7bac3e1`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14_origin_audit_v2.py@sha256:5d604798b104d740d6f205e0b8e9f2c000a3e7fc71b39b994bd9e2872350f00e`

PDC: P04/P05 separate terminal state, purpose and authority; P29 uses behavioral reds; P31/P37 bind execution to durable evidence; P38 records projection versus owner-action divergence; P40 closes exact JSON comparison once in the existing shared predicate; P41 leaves unmeasured/inherited attribution unestablished.

## Final source checkpoint review

The independently reviewed V3 fixture patch preserves the runtime context in all five production-used callbacks. Owner scope is supplied only for controlled fixture setup and direct fixture operations. A raw FileSystemCAS fixture does not prove guarded-store custody or S8. The facade review ACKs only the additive `clear_tenant_context` export and its two owner-generated public-surface companions.

- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-di.junit.xml@sha256:8178b1621a3a6c1f5f32f11682314f41f9ac93addb83211aacc3cb5c8e197a84`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-di.log@sha256:65a7d4984bd5430a4a32657c9828f9d5452538f320a76b03382a8412b2829a85`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-di.origins.json@sha256:a353746620725233642e6dbc479ebdf06a04ea235f33db9c3a29849045370135`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-cyc05.junit.xml@sha256:073197ce529c8869c7d231a8c80a08126b99ae1ca619b8a0d741d246b738fa19`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-cyc05.log@sha256:788705acda64cc3b9e6c2456790eb80ecd48cbd9a536098a97bc1938c2f49edd`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-cyc05.origins.json@sha256:b6e434cfaab8f7a0cf5d34e8beef34ec10c99ec89ef6d61a03ee79cdfebfda11`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v18-architecture-guardrails.log@sha256:849ca53267a3f768c1e873556fb9a276cfd7be1007be1bdcb2222378f1e66050`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/ARCHITECTURE_GUARDRAILS_TRIAGE_V18.md@sha256:ee633cb56c9e070627cb4677ca42c6fbb9735a65ad31b78b3a36286e6054d6ce`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/ARCHITECTURE_GUARDRAILS_TRIAGE_V18.json@sha256:b8aa167cbaffb7a2acfb722de7f2ce5f9ccafc01e92b81c1d5d9ed0373a776ec`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_V3_FIXTURE_AND_FACADE_ACK.md@sha256:f6bd1a5ea7f83c4cd0fcc7c963fbc61814a563bed67c4ee3a38d769c2dc8d4de`

## Final canonical wave and bounded conclusion

V20 uses the reviewed V3 fixture and lazy security facade; V19 stopped before pytest on one import-order Ruff diagnostic, corrected mechanically for V20. No V19 pytest result exists. V20 freezes all 32 changed paths (26 Python), and the in-process origin inspection reports 1,782 loaded source modules, ten collected test modules and 50 helper/conftest modules: zero foreign origins and zero changed frozen inputs. It runs in 156.13 seconds, peaks at 1,322,500,096 bytes RSS and reports zero swaps. All 26 changed Python files pass Ruff.

This checkpoint implements the durable worker/admission and strict completion-publication property in the tested SQLite/raw and guarded-store paths. It retains the R1 producer/profile, CYC-05 owner-fixture migration, historical four-base importer coverage, PostgreSQL, SearchExit-to-promotion bridge, architecture and TypeScript residuals. It is a source boundary with measured limitations, not E02-R2 completion.

- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/FROZEN_INPUTS.v19.json@sha256:3ac893d1ce95ea5e6a4e9a6a97a446ebc10d34c2d5b83120b426cffbbe7c1b43`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v19-ruff.log@sha256:23b5f131a42612450bf4943f660132ed32707e48888c73524a3eefbe8de9bbab`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/FROZEN_INPUTS.v20.json@sha256:ba1a6ddc133072963082204962a13cfcecfb28016f29ad1dcc244ff98bfe08e5`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/R14_CANONICAL_V20_CANDIDATE.patch@sha256:428e3f4d3c0660c2f992971bb8559b2a5420b04447db307ca472d902d0aed675`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v20-final.junit.xml@sha256:2abac3fca4bca9c304711db323b9699cd2ff740827c4cfc333ae4b3096b7a75f`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v20-final.log@sha256:c911ae574c7716e8d49933af47c8958890944365308f82bf9f95bdc0904cca38`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v20-final.origins.json@sha256:92a7fb873527200fdba6eebbea53e7ed430ba389705f3f697982cb3e3d1a6de6`
- `/Users/deniskopylov/.codex/scratch/e02-r14-integrated-2122-20260930/r14-v20-ruff.log@sha256:82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`

The final independent assessment is implementation GO and integrated verification PARTIAL for this bounded class: 158 bodies pass, nine producer-dependent bodies are UNRUN at setup. The source checkpoint does not close the residual class or overwrite the ledger.
