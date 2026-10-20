# B108 R8 — terminal score-state reconciliation

Status: author candidate for independent review; no formal closure claimed. The R7 source and review receipts remain immutable.

## R7 same-class finding

Independent R7 v2 review found one B108 status-propagation escape after the R7 projection and missing-assessment terminal fixes. A source-bound `UNAVAILABLE` assessment could be replayed against a changed source as `INVALID`; reconciliation then discarded the old assessment because its status differed from the replay, and a later completion check interpreted the missing assessment as `NOT_ESTABLISHED`. The explicit completion route therefore deferred an invalid source mismatch instead of rejecting it. The second route was implicit terminalization: a final structurally promising stage with no assessment/value and `NOT_ESTABLISHED` could fall through `_mark_terminal` to `complete`.

Both findings are the same score-state propagation class under B108/P40. R8 carries one typed `ObjectiveScoreAdmission` with the reported assessment, source-recomputed assessment, status, and reason. Reconciliation retains `INVALID` even if the assessment/value projection is absent; it does not promote a malformed or changed source to absence. A single terminal-completion finalizer runs after both explicit and implicit terminalization and requires the same source-recomputed `AVAILABLE` admission. A genuine `0.0` remains available. Missing or validly unavailable scores defer; invalid source/status remains rejected; incomplete structural candidates can still continue at earlier stages with a declared limitation.

The finalizer also updates the terminal stage result and trace from the same typed admission before `FunnelOutcome` and the runtime surface are emitted. The public projection includes status and source hashes, not copied source values. A terminal result’s reported `APPROVE` marker and `is_promising` flag do not grant score admission.

## Evidence and boundary

The focused control matrix is derived from all `ObjectiveScoreStatus` members and exercises explicit completion and implicit finalization. It includes an available genuine zero, unavailable selected units, malformed supplied measurement, absent assessment, and an unavailable assessment whose source mutates to malformed. Assertions cover the direct `FunnelOutcome`, terminal trace, and runtime reporting projection; the mutation control requires the recomputed `INVALID` evidence to survive.

This changes the runtime status transition and the typed admission carrier used by existing score surfaces. It introduces no new objective, measurement law, unit conversion, scientific weighting, calibration, issuer authority, or production-currentness claim. The unconfigured direct BayesianOptimizer candidate-only boundary and all R7 limitations are unchanged. No runtime test, persistence replay, installed-wheel, rebuilt-sdist, or full composed replay has run for R8; those remain for the reviewed source freeze and root-owned verification slot. `closure_ids` remains empty and B108 remains an author proposal for G.
