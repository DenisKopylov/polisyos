# Old N6 source-census value triage

**Decision:** preserve the exact unique source file and its patch as a reference, not the 106 MiB snapshot. Do not forward-port the confidence-ledger change as-is and do not call it B30 closure. It contains one potentially useful route-analysis idea, but the canonical A owner and an independent property witness are still required.

## Exact identity and overlap

- Scratch file: `/Users/deniskopylov/.codex/scratch/e02-r2-n6-owner-real-capture-20260926/src/polisyos/runtime/quality/confidence_ledger.py`, 305,248 bytes, 7,366 lines, Git blob `ae95ed59748347c9429b8ef8913e0d791e3fa0b1` (verified with `git hash-object`; blob absent from G's object database).
- G at `9a187afa4ef75af4a7b01ca49f1cc8194f7b6fe7`: `policy-engine/src/polisyos/runtime/quality/confidence_ledger.py`, 271,376 bytes, blob `22f30b69ff2d839bd6e58d0313d223a3940cd9a9`.
- The unique portion adds `N6FixtureRouteAttestation` plus an approximately 1,200-line AST/source-census mechanism. The scratch tree has no tests directory. Its quality README does not describe this new attestation; it states that static source measurements are diagnostic and do not establish runtime execution, persistence, or authority.

## What is useful, and where it fails

- Useful property: the new code walks and hashes every `src/polisyos/**/*.py`, treats absent/read/parse errors as non-PASS, parses actual ASTs for direct/aliased fixture references and dynamic dispatch, resolves a declared served import closure, checks expected N6-vs-workflow route edges, and binds evidence to the loaded module manifest. This is a real source measurement, not a marker-string test.
- It is not presently a producer-to-consumer capability. Repository-wide search finds `capture_n6_fixture_route_attestation` only in this file (definition/export, no call site). The same file's `inspect_packaged_deployment_identity` still hardcodes `verdict="UNRUN"` and `n6_census_verdict="UNRUN"`; currentness therefore never consumes this census. There are no tests in the snapshot to show production behavior or removal controls.
- It is stale against actual G routes. The scanner requires `ControlPlaneService._process_control_job` itself to contain literal `job.kind` dispatch (`_n6_verify_served_route_disjointness`, scratch lines 5154–5238). G's current method at `run_lifecycle.py:4908–4936` only admits the live job and delegates to `_process_control_job_admitted`; actual branches are there (`:4985` natural-language, `:5031` workflow), with N6 recursive execution at `:5472`. Thus on current G the scanner cannot find its required branch and must return UNRUN; no test was run to execute that prediction.
- The source-snapshot predicate is too broad for B30. `_capture_import_time_n6_source_snapshot` records the whole `src/polisyos` Python tree (scratch `:5298–5353`); `_capture_n6_route_source_evidence` requires exact equality later (`:5483–5493`). A change to an unrelated `.py` file after import changes the snapshot and returns `n6_fixture_route_source_snapshot_mismatch`, even if no consumed route dependency changed. B30 requires changed consumed dependencies to invalidate reuse while unrelated files do not. The full tree remains useful as a denominator for forbidden-reference discovery, but must not be the loaded-runtime freshness key.
- The static mechanism explicitly leaves general reflection and dispatch outside its proof and hardcodes root modules, route method names, and expected edges. That can be a bounded source witness; it cannot establish arbitrary runtime reachability or the installed/deployed root. Its typed attestation's digest shape does not fix the missing bridge or consumer (`P01/P29`, and a hard-coded input/root proxy risks `P37/P38`).

## Canonical-owner action

G already has the canonical A-side source observation in `generation_cycle.py`: `inspect_n6_source_census` and `_collect_strangle_source_census` enumerate/parse the full source scope, distinguish missing/read/parse failures and observed callers, and deliberately keep production verdict `UNRUN` because served-root/binding and loaded identity are not reconciled (`N6SourceCensusGateResult`, lines 1922–1971 and 12958–13277). `confidence_ledger.py` currentness is a separate identity gate and explicitly does not read source files (`:4520–4643`). B30's original criterion also says no signed N6/currentness receipt substitutes for its source-tree strangle property (`closure-decisions/A.md:101–102`).

Forward only the route-edge idea to A's canonical `generation_cycle.py` owner, not the new confidence-ledger API. Smallest next slice:

1. Derive/verify the actual served entrypoint and its `job.kind` branches from the current admitted dispatcher (`_process_control_job_admitted`), then establish the N6 recursive branch is disjoint from the actual workflow-to-WorkspaceLoop fixture path. Missing or unsupported dynamic edges stay UNRUN.
2. Keep complete-source denominator/parse-error behavior for forbidden-reference discovery, but bind runtime freshness only to the controlled loaded dependency set. Prove changed consumed dependency invalidates and unrelated-file change does not; do not bind whole-tree snapshot equality to reuse.
3. Wire that recomputed B30 property to the existing A reuse/strangle consumer, separate from signed N6 currentness. Add focused negative/positive witnesses for missing denominator, parse error vs actual forbidden caller, real current route vs fixture route, and changed-vs-unrelated dependency. Until that is done, keep production path/currentness UNRUN.

No files were moved, deleted, or modified outside this ignored report; no tests or environment setup were run.
