# E02-R2 discovery index

As of 2026-09-24. This is a pointer index for the candidate lanes. **None of the candidate documents below has been integrated into `codex/e02-r2`; this file does not claim integration.** A `GO` is a document/map review result, not behavioral closure.

## P41 replay state

The earlier `codex/e02-r2` harness at `c08977e4ffc96adde4d4dfaddb0ad0f214065fd1` was **NO-GO** for a mixed-case resource-summary issue. Its follow-up at `8cf3028c05438dda01ebe30225ef5119ed5637d5` is independently **GO**. The resumed five-group broker session started 2026-09-24 at approximately 17:16 UTC. Its results are pending/`UNRUN`; there are no current outcome claims. The four-base replay is not yet `BASELINES_DONE`, so integration source and test edits remain frozen.

In-flight scratch run and mutable checkpoint: `/Users/deniskopylov/.codex/scratch/e02-r2-baselines/p41-pre-repair-20260924T171600Z-23461/checkpoint/` (`manifest.json`, `progress.jsonl`). The checkpoint has not yet been moved/published to package `raw/`; no current results or final result SHA are claimed.

Historical stopped 400-cell receipt: `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/results.json@sha256:51dba304cf2384e26f1be269c31bf62ed106eb6638f446a696e5da94861b27e6`; sibling checkpoint progress: `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/checkpoint/progress.jsonl@sha256:0765e069c28f90432f8527cf300fcbf4dd536c323f5ae8efc77f57f7dbbb5646`.

The historical denominator is 400 cells: 69 completed with pass/fail outcomes (not summarized here), 273 interrupted as SIGINT/`UNRUN`, and 58 absent/`UNRUN`. Four proposed safety-skip cells are a subset of the 273 interrupted cells, leaving 269 present jobs eligible for resumption. These are stopped-run counts, not a completed baseline or a regression classification; resumed-run results remain pending/`UNRUN`.

## Candidate documents and review state

| Lane | Candidate branch and exact HEAD | Documents to open | Review and evidence state |
|---|---|---|---|
| Decisions | `codex/e02-r2-decisions` @ `ccc5af8d6192451b2db641bd675e2c4dcc7c81ac` | `DECISION_RECORDS.md`, `IMPLEMENTATION_MAP.md`, `R3_HISTORY_MAP.md` | R3 history map **GO**. R5 candidate-band selector residual is documented; independent technical and decision-form reviews are pending. Decision-record drafts await Denis. Proposed repairs remain unrun. |
| Residual ledger | `codex/e02-r2-ledger` @ `b1c010eab21855455e6d5e0aefd572b54e9088ba` | `RESIDUAL_LEDGER.md`, `residual_ledger.json`, `CROSSWALK.md`, `REGISTER_PROPOSALS.md`, `WRITE_LEASES.md`, `R8_LEASE_MAP.md`, `R9_CAS_VIEW_MAP.md` | R8 lease map **GO**. The overall ledger/crosswalk delta is **pending review**; R9 view map review is pending. Ledger statuses and proposals are not behavioral results. |
| Held and no-record | `codex/e02-r2-held-review` @ `ff33d58023da1c5121786d82b94fcf9710b63e0c` | `HELD_REVIEW.md`, `NO_RECORD_REVIEW.md`, `H_IMPLEMENTATION_MAP.md`, `N_IMPLEMENTATION_MAP.md`, `PHASE0_REISSUE.md`, `R10_SIGNATURE_MAP.md`, `R6_N5_CONTEXT_MAP.md` | H/N and R10 maps **GO**; N witness edits are in `f1c598e9b26a28b9ba96aa3e60fef27ab2c06501`. R6 correction at this HEAD also received independent **GO** from `r1_bridge_review`. Finding selectors remain `UNRUN` unless explicitly tied to measured evidence. |
| Partial triage | `codex/e02-r2-partial-triage` @ `4862f3895a33107da8ec36a19116daf03819ae15` | `PARTIAL_TRIAGE.md`, `partial_triage.json`, `P_DECISION_DRAFTS.md`, `R13_ROUTE_MAP.md`, `REAL_DATA_WITNESSES.md`, `R4_CONTRACT_MAP.md` | P triage **GO** at `10009d39e` and unchanged at this HEAD: 118/118 rows classified (76 engineering, 16 principal decisions, 26 typed blockers). R13 route map **GO**. R4 map's correction at this HEAD is **pending delta review**. Triage is proposed next work, not closure evidence. |
| Canonicalization, egress, and safety | `codex/e02r2-can01-audit` @ `1def32e5f4d68cb6785581b570284b3a4fe8b9a0` | `LA021_CANONICALIZATION_RECHECK.md`, `R7_EGRESS_MAP.md`, `P41_SAFETY_AUDIT.md`, `R2_DEPLOYMENT_MAP.md`, `P41_D2_SAFE_FIX_PLAN.md`, `R14_TEST_SAFETY_AUDIT.md` | R7 egress map **GO**. LA-021 instrument **PASS** within its measured corpus (2,867 tracked JSON paths, 2,833 unique blobs); four-base unit replay and the architect's exact 418-input comparison remain `UNRUN`/not reproduced. D2 safe plan and R14 static safety audit are proposed/static-only; review pending, with no runtime outcome claim. |

## Documentation commits since the prior index

- R5 candidate-band residual: `codex/e02-r2-decisions` @ `ccc5af8d6192451b2db641bd675e2c4dcc7c81ac`; `DECISION_RECORDS.md` and `IMPLEMENTATION_MAP.md`. Proposed discriminator; independent technical and decision-form reviews pending.
- N18 behavioral witness update: `codex/e02-r2-held-review` @ `f1c598e9b26a28b9ba96aa3e60fef27ab2c06501`; `N_IMPLEMENTATION_MAP.md`. H/N map review **GO**; test identities remain `UNRUN` unless separately measured.
- R6 N5 foreign-context map: initial `0f376a4370ee0e169c38ce246986dea8b129770c`, corrected `ff33d58023da1c5121786d82b94fcf9710b63e0c`, both on `codex/e02-r2-held-review`; corrected map review **GO** from `r1_bridge_review`.
- R4 GY-N6 contract map: initial `0e749d0888ee9a66798b03cf2005d33c5ebf5f55`, corrected `4862f3895a33107da8ec36a19116daf03819ae15`, both on `codex/e02-r2-partial-triage`; corrected delta review is pending.
- D2 behavior-test plan: `codex/e02r2-can01-audit` @ `25661d659acd94bedb452120e1232f8adbb731ff`; proposed test plan only, no behavior run.
- R14 safety audit: `codex/e02r2-can01-audit` @ `1def32e5f4d68cb6785581b570284b3a4fe8b9a0`; static inspection enumerates 344 test paths / 1,376 cells, 1,052 present and 324 absent. One D2-copy test file has four typed `UNRUN` safety dispositions. No runtime outcomes; review pending.

The GO/NO-GO states above describe review of the cited candidate material. Read the exact branch/commit before reusing a map; later edits require their own delta review. Test identities in the maps are proposals or `UNRUN` unless tied to an explicit measured receipt. The 21/21 prior-checkpoint reuse is admitted only after source-import identity and JUnit reconciliation, as recorded in the current write lease.
