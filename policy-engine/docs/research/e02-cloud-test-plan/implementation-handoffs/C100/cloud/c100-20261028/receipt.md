# C100 runtime qualification receipt

## Admission and boundary

- Environment: `polisyos`; cwd and Git root: `/workspace/polisyos`.
- Branch: attached `work`; admitted HEAD `6ed657f7a5250b25db5a6fb2f589b049a964848d`; tree `4e056c197ce34067a1ee9c7225ff8609235de0ab`.
- Entry index and worktree were clean. Final changes are limited to the declared selected-Catalog adaptation and this task-private evidence directory.
- The declared adaptation was applied exactly. Active HTTP module SHA256 is `4ca67cf5079ff5c4d395a59d66be965c403b81ab4fe7530984aa7643437d2d0c` (the commissioned postimage).
- No product source, lifecycle, validity/currentness schema, Core/IR/TC schema, generated schema, or lock file was changed. `closure_ids=[]` remains unchanged.

## Host/profile

Linux `6.18.55`, x86_64; `/workspace/polisyos/policy-engine/.venv/bin/python`, CPython `3.14.4`; pytest `9.0.2`; uv `0.7.22`. Memory was 18,883,018,752 bytes total and 17,718,534,144 bytes available; cgroup memory limit 17,179,869,184 bytes. CPU quota was `200000/100000`, with affinity CPUs 0-2. Disk was 33,770,192,896 bytes total and 29,033,979,904 bytes available. The first native run used one numerical thread, a 600-second external guard, `-B`, `PYTHONDONTWRITEBYTECODE=1`, a task-unique initially empty pycache prefix, native pytest configuration/plugin discovery, a fresh basetemp, and the exact node ID.

`/usr/bin/time` was absent, so the requested aggregate process-tree RSS sampler was unavailable. Wall time was 73,891 ms. The process returned normally (not guard termination/137); no OOM claim is made.

## Deciding results

### Real A/B Runtime producer chain — FAIL (product/profile setup boundary diagnosed)

The exact first selector collected one test and failed at the first launched source job. Actual Runtime admission and real control dispatch occurred, but the workflow failed before the producer chain could complete. Persisted `control_jobs` and `control_job_events` were reopened from the same-case SQLite store. Job `2d327301cd204d1f8dbafc5f37f5fce1`, run `R_93e53de228c0c5d2`, attempt 1, transitioned pending → running → failed with exact error:

```
Unknown node_id: scientist.node_build_data_snapshot@1.0.0
```

Independent registry diagnosis in a fresh process showed zero discovered Scientist nodes and the concrete discovery error:

```
builtin_loader:polisyos.scientist.nodes.components:__polisyos_components__: No module named 'sklearn'
```

Thus this is a missing native ML dependency/setup ERROR feeding a real workflow failure, not a comparison mismatch, guessed OOM, or successful producer. No method-execution selection existed, so CAS→projection→planner→fresh GET was not established.

The one permitted bounded setup attempt, `uv sync --frozen --extra test --extra runtime --extra ml --extra lint`, failed downloading locked `threadpoolctl==3.6.0` after three retries because the configured network tunnel was unavailable. It made no lock change. Per commission rules, the second real planner/revocation selector and genuine Runtime A/A extraction are dependent **UNRUN**, rather than misleading product failures. No production repair or fixture bypass was made.

### Identical-source completed-owner unit seam — PASS

The exact commissioned owner-double test passed (one collected, one passed). This proves only its unit seam; it is not reported as genuine Runtime A/A and does not replace the blocked real A/B chain.

### Independent arithmetic

The requested exact paired arithmetic is independently reproducible:

- A: `((11-10) + (18-20) + (44-40)) / 3 = (1-2+4)/3 = 1`.
- B: `((12-10) + (20-20) + (44-40)) / 3 = (2+0+4)/3 = 2`.
- minimized objectives would be `[-1, -2]`.

Because the Runtime producer did not complete, these remain expectations over the commissioned arrays, not assertions over actual selected captured rows. No causal, calibration, feasibility, holdout, law, or publishability authority follows.

## Control inventory (full denominator: 23 recipes)

All controls are **UNRUN**: the eight defining controls were not started after the first native chain hit the concrete dependency/setup boundary, and the remaining fifteen were not affected. No mutant was applied; therefore no restoration risk exists.

1. compile-binding-bridge — UNRUN
2. root-underscore — UNRUN
3. caller-hash — UNRUN
4. subject-payload — UNRUN
5. producer-transport — UNRUN
6. old-evaluation — UNRUN
7. public-cas-authority — UNRUN
8. actual-source-join — UNRUN (FIRST)
9. declared-source-join — UNRUN (FIRST)
10. baseline-contract — UNRUN (FIRST)
11. seed-contract — UNRUN
12. source-reselection — UNRUN (FIRST)
13. owner-currentness — UNRUN
14. completed-owner-currentness — UNRUN
15. http-currentness — UNRUN (FIRST)
16. blueprint-effective-subject — UNRUN
17. split-gates — UNRUN
18. mutated-subject — UNRUN
19. physical-ancestry — UNRUN
20. physical-prior — UNRUN
21. environment-plan-reconciliation — UNRUN (FIRST)
22. whole-compiled-graph — UNRUN (FIRST)
23. state-view-intake — UNRUN (FIRST)

## Claim limits, occurrence routing, and residual owner

All 21 historical C48 occurrence rows remain distinct and `closure_now=not_adjudicated`: B109, B110, B111, B112, B113, B114, B115, B116, B117, B118, B119, B120, B121, B123, B124, B125, B126, B127, LA-014@SRV-01, LA-015@CTL-01, and LA-015@SRV-03. No occurrence is closed by the unit seam or by this setup diagnosis. B13, B161, and B214 remain related non-C100 routes. No F16/C103, R9, GY, Atlas, integration, G acceptance, full Runtime, full 117, or formal closure claim is made.

Residual owner is environment provisioning/network cache: install the locked ML extra (notably scikit-learn and threadpoolctl) in the existing CPython 3.14 environment, then rerun the exact first selector from a fresh case. Only after it completes should the second selector, genuine Runtime A/A extraction, and eight defining mutant phases proceed. The smallest setup falsifier is a fresh-process `discover_scientist_nodes(include_dev_scan=False)` returning a nonempty registry containing `scientist.node_build_data_snapshot@1.0.0` with no discovery errors.

Pattern disposition: P01/P02/P12 are not claimed because the producer chain did not complete; P05/P15 candidate authority remained fail-closed; P29/P32/P33 controls are UNRUN; P35 denominator is 23/23 explicitly enumerated; P37/P38 distinguish actual persisted failure evidence from transport/exit markers; no P40 repair was attempted; no inherited-red P41 attribution is made.
