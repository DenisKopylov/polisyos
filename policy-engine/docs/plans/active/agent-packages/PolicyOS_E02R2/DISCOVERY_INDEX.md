# E02-R2 discovery index

As of 2026-09-24. This is a pointer index for the candidate lanes. **None of the candidate documents below has been integrated into `codex/e02-r2`; this file does not claim integration.** A `GO` is a document/map review result, not behavioral closure.

## P41 replay state

The `codex/e02-r2` harness at `c08977e4ffc96adde4d4dfaddb0ad0f214065fd1` is **NO-GO**: a mixed-case resource-summary issue remains under repair. The four-base replay is not `BASELINES_DONE`; integration source and test edits remain frozen.

Stopped 400-cell receipt: `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/results.json@sha256:51dba304cf2384e26f1be269c31bf62ed106eb6638f446a696e5da94861b27e6`; sibling checkpoint progress: `/Users/deniskopylov/.codex/worktrees/e02-r2/polisyos/policy-engine/docs/plans/active/agent-packages/PolicyOS_E02R2/raw/p41-pre-repair-20260924T161246Z-93931/checkpoint/progress.jsonl@sha256:0765e069c28f90432f8527cf300fcbf4dd536c323f5ae8efc77f57f7dbbb5646`.

The denominator is 400 cells: 69 completed with pass/fail outcomes (not summarized here), 273 interrupted as SIGINT/`UNRUN`, and 58 absent/`UNRUN`. Four proposed safety-skip cells are a subset of the 273 interrupted cells, leaving 269 present jobs eligible for resumption. These are stopped-run counts, not a completed baseline or a regression classification.

## Candidate documents and review state

| Lane | Candidate branch and exact HEAD | Documents to open | Review and evidence state |
|---|---|---|---|
| Decisions | `codex/e02-r2-decisions` @ `dcf8e09dca037e8af7a8f38901ab75544720a0f7` | `DECISION_RECORDS.md`, `IMPLEMENTATION_MAP.md`, `R3_HISTORY_MAP.md` | Implementation and R3 history maps **GO**. Decision-record drafts await Denis. Proposed repairs remain unrun. |
| Residual ledger | `codex/e02-r2-ledger` @ `bc4818146c37ea8c7741075031a32db2f8c58da9` | `RESIDUAL_LEDGER.md`, `residual_ledger.json`, `CROSSWALK.md`, `REGISTER_PROPOSALS.md`, `WRITE_LEASES.md`, `R8_LEASE_MAP.md`, `R9_CAS_VIEW_MAP.md` | R8 lease map **GO**. The overall ledger/crosswalk delta is **pending review**; R9 view map review is pending. Ledger statuses and proposals are not behavioral results. |
| Held and no-record | `codex/e02-r2-held-review` @ `d08e31358a5ecc613104c540b7559eca79796c94` | `HELD_REVIEW.md`, `NO_RECORD_REVIEW.md`, `H_IMPLEMENTATION_MAP.md`, `N_IMPLEMENTATION_MAP.md`, `PHASE0_REISSUE.md`, `R10_SIGNATURE_MAP.md` | H/N maps and R10 signature map **GO**. Finding-level proposed selectors remain `UNRUN`, except evidence explicitly marked measured in the source documents. |
| Partial triage | `codex/e02-r2-partial-triage` @ `a4ae728124ec5a9c5109a0664cd182428a006ddf` | `PARTIAL_TRIAGE.md`, `partial_triage.json`, `P_DECISION_DRAFTS.md`, `R13_ROUTE_MAP.md`, `REAL_DATA_WITNESSES.md` | P triage **GO** at `10009d39e` and unchanged at this HEAD: 118/118 rows classified (76 engineering, 16 principal decisions, 26 typed blockers). R13 route map **GO** at this HEAD. Triage is proposed next work, not closure evidence. |
| Canonicalization and egress | `codex/e02r2-can01-audit` @ `1e0e83e84d67c620d53d230e4b04cc810a873448` | `LA021_CANONICALIZATION_RECHECK.md`, `R7_EGRESS_MAP.md`, `P41_SAFETY_AUDIT.md`, `R2_DEPLOYMENT_MAP.md` | R7 egress map **GO**. LA-021 instrument **PASS** within its measured corpus (2,867 tracked JSON paths, 2,833 unique blobs); four-base unit replay and the architect's exact 418-input comparison remain `UNRUN`/not reproduced. Other maps are pending unless individually reviewed. |

The GO/NO-GO states above describe review of the cited candidate material. Read the exact branch/commit before reusing a map; later edits require their own delta review. Test identities in the maps are proposals or `UNRUN` unless tied to an explicit measured receipt. The 21/21 prior-checkpoint reuse is admitted only after source-import identity and JUnit reconciliation, as recorded in the current write lease.
