# E02-R2 write leases

This is the coordination map for candidate writers. No source or test repair edits begin until every file in both the 32-file Appendix A/B matrix and the 37 unique add-on existing test files has a recorded replay at all four bases: `78187878e` (E02 execution base), `00d946c2b` (E02 head), `5fd3ebcc1` (main), and the frozen Phase 0 `codex/e02-r2` integration head. That is 69 test files and 276 file/base cells. Until the broker reports `BASELINES_DONE`, candidates may inspect and diagnose in isolated worktrees, but must not edit repair code or tests; only the baseline broker admits test jobs. After the freeze, only the integration writer applies reviewed candidates. Never run simultaneous writers on `runtime/quality/generation_cycle.py`.

## Compute admission after the interruption

Start with a one-process measured pilot. Admit at most two lightweight test processes only while observed memory and CPU headroom remain; do not reserve the second process when the pilot itself is heavy. Heavy native/numerical or exclusive-resource jobs run alone. The broker stops admission when resource pressure appears and resumes only after processes exit and headroom is observed. Keep the workspace’s 10 GiB free-disk floor. This supersedes the former seven-process-group ceiling for this lane.

## Initial ownership

| Work set | Owner |
|---|---|
| Integration branch/worktree `codex/e02-r2`, generated families, governed artifacts, authorized reissue planning | root integrator |
| `BASELINE_HARNESS.py`, `BASELINES.md`, baseline raw metadata and test admission | baseline broker |
| `RESIDUAL_LEDGER.md`, `residual_ledger.json`, `finding_record_probe.json`, `CROSSWALK.md`, `REGISTER_PROPOSALS.md`, `WRITE_LEASES.md` | ledger writer, candidate branch only |
| `DECISION_RECORDS.md` | decision writer |
| E02 records, DEBT-REGISTER/LEDGER, plans, runtime/test code | their owners; read-only to this writer |

## Candidate write sets after baseline freeze

No repair source or test edits are allowed in any worktree until the same environment completes and records each file’s replay on all four bases for both waves: the 32 Appendix A/B files and 37 unique add-on existing test files. Read-only diagnosis is allowed. Once both waves finish, candidate write sets below become available subject to the sequencing and collision rules. Compute admission stays at the measured one-process pilot; allow a second lightweight process only if observed memory and CPU headroom support it. R12 may inspect the independent acquisition fixture/bootstrap checker during diagnosis, but any R12 edit to `generation_cycle.py` remains serialized after R13, R6, and R11.

| Sequence | Class | Exclusive write set | Handoff / constraint |
|---|---|---|---|
| 1 | R1 + R5 | HTTP control composition, `runtime/quality/recursive_generation_cycle.py`, `runtime/quality/generation_cycle.py`, and recursive epoch-gate tests | One candidate writer owns all three runtime paths and the shared tests; review candidate/authority bands together. Use existing hash-verified compiled-run/context references and the owner resolver; ordinary candidate work may carry a typed unknown. N4 context is verified, while N7 post-growth owner context remains `not_established` and S8 authority stays blocked until a canonical post-growth witness is supplied (possibly by R13). No GenerationCycleRun schema change belongs to this lease. Finish before R2/R13/R6/R11 touch `generation_cycle.py`. |
| 2 | R7 | connector pool and acquisition validation/transport | One writer; no parallel health-probe or network edits. |
| 3 | R8 | `runtime/http/services/control_plane_store.py` and lease/fence guard | One writer; guarded-store stale-worker negative belongs to this candidate. |
| 4 | R3 | `runtime/quality/promotion_sequence.py` | One writer; historical fixtures and serializers are within this lease. |
| 5 | R10 | core artifact signature/integrity public boundary | First shared CAS owner change; normalize IDs at boundary and reconcile all 28 direct call expressions (16 source across 12 files, plus 12 tests). |
| 6 | R9 | core artifact store plus every backend/profile manifest | Follows R10 in the shared artifact-owner lane; all backend/view identities are exclusive. |
| 7 | R2 | `runtime/quality/generation_cycle.py`, source/deployment strangle and confidence-ledger identity; `tests/unit/remediation/test_cyc_05.py` | First generation-cycle lease after R1/R5 handoff. R2 alone owns GenerationCycleRun v3 identity/census evidence and v1/v2 historical serializers; establishes replay/currentness before dependent classes. The four-base baseline must include `test_cyc_05.py`. |
| 8 | R13 | `runtime/quality/generation_cycle.py`, `acquisition_planner.py`, Foundry training adapter | Root serializes this after R2; acquisition/world-growth caller and tenant custody are reviewed together. |
| 9 | R6 | `runtime/quality/generation_cycle.py` / joint N5 input context | Root serializes after the current generation-cycle lease. |
| 10 | R11 | `runtime/quality/generation_cycle.py` / VOI decision consumers | Root serializes after R6; enumerate board, promotion, projection, and recursive consumers. Principal decision remains pending. |
| 11a | R12 diagnosis | independent acquisition fixture/bootstrap checker only; no shared mechanism write | May inspect during diagnosis. If the repair changes `generation_cycle.py`, hand off to sequence 11b. |
| 11b | R12 runtime repair | acquisition contract plus `runtime/quality/generation_cycle.py` | Root serializes after R13, R6, and R11; diagnose then fold into R13 or R2 if evidence shows the same class. |
| 12 | R4 | governed GY-N6 checker and `runtime/quality/generation_cycle.py` | Root serializes after R12 unless measured dependency evidence changes the order; validator returns a typed verdict. |
| 13 | R14 | tooling/release-manifest and core-runtime closeout ledger | Distinct tooling lease after P41 denominator; four same-source cases currently identified (one W5 historic repo ref, three WS-2D release-ledger raw-client refs); attribution and test-file replay pending. |
| 14 | H/N/P | Finding-specific owners after R classes | Census each write set against this map; one writer per intersecting path. N OPT/SIM test sources wait for the 37-file add-on replay. |

## Serialization rules

- Only the candidate holding the current lease may edit `generation_cycle.py`. Required order is R1/R5, R2, R13, R6, R11, R12-runtime, R4; root may change later order only after recording dependency evidence and reassigning the lease. R12 diagnosis outside that file does not hold its lease.
- R1 and R5 share one candidate writer; the `generation_cycle.py` handoff completes before R2 begins.
- R10 precedes R9 in the shared artifact owner lane. If review shows a dependency reversal, stop and revise the lease before further edits.
- Governed epochs and receipts are serialized by the root integrator. Reissue occurs only through an authorized transition; no restamping is permitted.
- H/N/P repair edits begin only after both baseline waves and R-class write sets settle. Any collision becomes an explicit sequential lease.
- The baseline broker controls test process admission and exclusive native resources. This map does not authorize a run or edit during an in-flight job; source stays frozen until `BASELINES_DONE`.
