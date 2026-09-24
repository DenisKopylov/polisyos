# E02-R2 write leases

This is the coordination map for candidate writers. No repair edits begin until both the 32-file Appendix A/B matrix and the queued 22-file touched-test wave finish. During that freeze, candidates may inspect and diagnose in isolated worktrees, but must not edit repair code or tests; the baseline broker owns test admission and receipts. After the freeze, only the integration writer applies reviewed candidates. Never run simultaneous writers on `runtime/quality/generation_cycle.py`.

## Initial ownership

| Work set | Owner |
|---|---|
| Integration branch/worktree `codex/e02-r2`, generated families, governed artifacts, authorized reissue planning | root integrator |
| `BASELINE_HARNESS.py`, `BASELINES.md`, baseline raw metadata and test admission | baseline broker |
| `RESIDUAL_LEDGER.md`, `residual_ledger.json`, `finding_record_probe.json`, `CROSSWALK.md`, `REGISTER_PROPOSALS.md`, `WRITE_LEASES.md` | ledger writer, candidate branch only |
| `DECISION_RECORDS.md` | decision writer |
| E02 records, DEBT-REGISTER/LEDGER, plans, runtime/test code | their owners; read-only to this writer |

## Candidate write sets after baseline freeze

No repair source or test edits are allowed in any worktree until both baseline waves are complete: 32 Appendix A/B files and 22 queued touched-test files. Read-only diagnosis is allowed. Once both waves finish, candidate write sets below become available subject to the listed sequencing and collision rules; the broker still admits only the measured number of resource-bearing test groups. R12 may inspect the independent acquisition fixture/bootstrap checker concurrently with R2 after the freeze, but any R12 edit to `generation_cycle.py` remains serialized after R13, R6, and R11.

| Sequence | Class | Exclusive write set | Handoff / constraint |
|---|---|---|---|
| 1 | R1 + R5 | HTTP control composition and `runtime/quality/recursive_generation_cycle.py` / recursive epoch gate | One candidate writer owns both; the authority/candidate-band consumer contract must be reviewed together. |
| 2 | R7 | connector pool and acquisition validation/transport | One writer; no parallel health-probe or network edits. |
| 3 | R8 | `runtime/http/services/control_plane_store.py` and lease/fence guard | One writer; guarded-store negative belongs to this candidate. |
| 4 | R3 | `runtime/quality/promotion_sequence.py` | One writer; historical fixtures and serializers are within this lease. |
| 5 | R10 | core artifact signature/integrity public boundary | First shared CAS owner change; normalize IDs at boundary and enumerate callers. |
| 6 | R9 | core artifact store plus every backend/profile manifest | Follows R10 in this lane's reviewed order; shared CAS API is exclusive. |
| 7 | R2 | `runtime/quality/generation_cycle.py`, source/deployment strangle and confidence-ledger identity | First generation-cycle lease after R1/R5 handoff. R2 establishes replay/currentness mechanism before dependent classes. |
| 8 | R13 | `runtime/quality/generation_cycle.py`, `acquisition_planner.py`, Foundry training adapter | Root serializes this after R2; acquisition/world-growth caller and tenant custody are reviewed together. |
| 9 | R6 | `runtime/quality/generation_cycle.py` / joint N5 input context | Root serializes after the current generation-cycle lease. |
| 10 | R11 | `runtime/quality/generation_cycle.py` / VOI decision consumers | Root serializes after R6; enumerate board, promotion, projection, and recursive consumers. |
| 11a | R12 diagnosis | independent acquisition fixture/bootstrap checker only; no shared mechanism write | May inspect concurrently with R2 after baseline freeze. If the repair is isolated to this checker, it may use a separate candidate; if it changes `generation_cycle.py`, hand off to sequence 11b. |
| 11b | R12 runtime repair | acquisition contract plus `runtime/quality/generation_cycle.py` | Root serializes after R13, R6, and R11; diagnose then fold into R13 or R2 if evidence shows the same class. |
| 12 | R4 | governed GY-N6 checker and `runtime/quality/generation_cycle.py` | Root serializes after R12 unless evidence requires earlier; measure checker inputs before repair. |
| 13 | R14 | tooling/release-manifest and core-runtime closeout ledger | Distinct tooling lease after P41 denominator; do not fold into runtime edits without a measured shared property. |
| 14 | H/N/P | Finding-specific owners after R classes | Census each write set against this map; one writer per intersecting path. N OPT/SIM test sources wait for the second baseline replay. |

## Serialization rules

- The only active writer of `generation_cycle.py` is the candidate holding the current lease. Required order is R2 then R13, R6, R11, R12-runtime, R4; root may change later order only after recording dependency evidence and reassigning the lease. R12's independent checker diagnosis is not a `generation_cycle.py` lease.
- R1 and R5 share one candidate writer; they hand off before any R2 lease begins.
- R10 precedes R9 in the artifact owner lane as currently assigned. If review shows a dependency reversal, stop and update this lease before writing either class again.
- Governed epochs and receipts are serialized by the root integrator. A required reissue occurs only through an authorized transition; no restamping is permitted.
- H/N/P repair edits begin only after both baseline waves and R-class write sets settle. Any collision becomes an explicit sequential lease.
- The baseline broker owns test process admission and exclusive native resources. This file does not authorize a run or an edit during a run.
