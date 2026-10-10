# V3 same-candidate and measured no-growth companion proposal

Status: **patch-only, unapplied, and untested**. The proposed unified diff is `LOCAL/raw/v3-same-candidate-companion.patch`, SHA-256 `41d8f25effd21792ff7d8fa5dd863c77c9f1876d2d1c801e3363e4fbe1908d76`. `git apply --check` succeeded against the exact current worktree contents; no source or test files were written and no test was run.

## Slice and exact preimages

- Slice base: `c4563fd4da93bf9cc06de3dc77554a8a0d117359`, with root's shared WIP retained.
- Engineering decision: `LOCAL/decisions/v3-same-candidate-final-engineering-20261010.md`, SHA-256 `cae0a0bed11ec4af907f7fefa3f5977316ba16a72de337b25215bb4084c49afb`.
- `src/polisyos/runtime/http/routes/runs.py` — `2d0bec815342d2cd32a2c59e8e1e9a3c28149238c0934210776a3413f0786bd1`.
- `src/polisyos/runtime/quality/acquisition_world_growth.py` — `54c86b3272b77c4c67903f657d32bbd5876b75d76918dbf1743395979354ff88`.
- `src/polisyos/runtime/http/services/acquisition_surface_execution.py` — `8423f88932aa3192ff5dd47d90b593a8396ca6acb2934aa575d1bbe93c849e6f`.
- `tests/integration/core_runtime/test_acquisition_authority_served.py` — `2e9d9dc8748a253c1586eb9a4176350c20da436007b7b835ae923cb47c87f368`.
- Untouched fixture helpers: `tests/_helpers/acquisition_chain.py` SHA-256 `0181432ff573222c7960a45ca57d3547d64a745030c9f2065212e4f5a2aabe28`; `tests/_helpers/acquisition_production.py` SHA-256 `b3d6d8f8aa6a666d33ff56aa284a3499e45cd677f965e7c686bb947d983d1806`.

The patch touches only the four source/test files above. It does not alter the route-history DTO, the `quarantined_no_growth` status, permission/mandate rules, live-provider attempt leases, generation budget, or public authority/currentness claims.

## Proposed same-candidate source binding

The route projection will compare full recomputed semantic identity only when the prior and re-entry candidate IDs match. It requires equal stable subject, semantic identity hash, selected profile, and candidate ID; a distinct immutable source-occurrence hash and WMR hash; and a typed origin ref bound to the prior selected source (or its root origin). A different candidate keeps the existing generic re-entry projection. The served test seeds both N4 actions from the same recorded candidate and checks the actual source records, N5 lineage, and authenticated GET. It derives distinct candidate IDs for changed profile, subject, and model semantics. It also corrects the receipt variable mix-up: the history's old candidate is checked against the decoded `AcquisitionOverlayReentryReceipt.source_candidate_ref`, not the enclosing `AcquisitionRouteLoopReceipt`.

## Proposed third-action no-reissue path

The current WDI port has no available path for a third same-route action after successful growth: readiness sees the existing attempt and returns `acquisition_live_attempt_exhausted` before a fresh membership measurement. The patch allows that action only after the bridge re-verifies the already persisted positive growth receipt. Under the existing owner admission lock, the bridge re-reads the positive growth and attempt, checks their binding/evidence refs and authority scope, verifies every evidence ref, and projects the current owner state. It then calls the existing `_finish_admission` with the same activation and a copy of the original attempt whose `before` snapshot is the just-read current membership. A second positive delta fails closed; the existing `_finish_admission` returns no growth only for an actual zero delta. The bridge reads the owner state again, requires the full before/after snapshots to match, and persists a strict `AcquisitionWorldGrowthNoGrowthReceipt` containing the prior growth/attempt refs, current count, evidence refs, and exact snapshots.

The port enters this branch only for an existing, verified growth pointer. It makes no provider call, does not reserve or reset a live attempt, and does not invoke N4/N5 generation. It returns the existing `quarantined_no_growth` disposition with prior evidence plus the no-growth owner receipt; the action service therefore uses its existing terminal path. Unknown attempts, corrupt pointers, deferred admissions, and routes without a verified positive growth keep their existing fail-closed outcomes. `project_growth` is made read-only for this preflight.

The served test proposes a third normally authorized action with a new idempotency key/job and fresh decision evidence. It reads the no-growth artifact from the action's terminal owner refs and recomputes the zero delta from persisted before/after membership. A fresh authenticated GET must retain the original candidate projection byte-for-value outside action history, keep generations 1 and 2, and add generation 3 as quarantine with no re-entry/candidate fields. Origin and re-entry corruption controls restore the exact original CAS bytes in `finally`.

## Pattern, falsifiers, and limits

P40 is **same class, deeper**: the prior work checked same-candidate source/consumer lineage; this widens that same producer→artifact→action→fresh-reader contour to the ID/time-only no-reissue control. P38's divergent case is a third authorized action that is rejected as attempt-exhausted before membership measurement; a fabricated zero or a marker-only assertion would not test the required property. The proposed bridge instead recomputes the count through the existing native resolver and `_finish_admission`.

The patch and test are not accepted evidence yet. The decisive falsifiers after root review/application are: the third request reaching the provider or producing another source/N5/WMR projection; a no-growth artifact whose exact owner snapshots differ or whose recomputed delta is nonzero; a changed candidate projection; a changed generation-2 re-entry row; a candidate identity changing under only ID/time; or either corrupted source/ref remaining green. The complete served integration command and relevant focused owner tests still need to run on the composed source slice. B09 remains `verification_missing` until that run passes; no formal G closure or publication/currentness authority is claimed.
