# C continuation: full denominator and writer leases, 2026-10-06

This is an execution plan, not behavioral evidence or a finding verdict. Root C works from `198076863e143dea9f89f02734b13d50dae3eed5` / tree `2b754a92c27959e2e747738d47ed0b419f3b6dd8`; both the published anchor `1ddcd7b3905e52c0d19db091823a64830139fa64` and analysis source `97c85fae2d4505ec8248540d98b9556296244208` are ancestors. The analysis tree is `e77c0741d3b19acb43e07a0de2bdb97c8fa98ee3`.

The complete `closure-decisions/coverage.json` C set, joined to both owner TSVs and original criterion cards, is **33 bundles / 54 unique findings / 59 criterion occurrences**. `closure-decisions/C.md` and each linked original criterion govern acceptance. Historical ledger status, Appendix-C status, current code outcome, and new verdict remain distinct. Every new verdict is pending below; no historical PASS or bounded closure is transferred to this candidate.

`results/import_results.py --check` exited 0 before baseline use. The full imported denominator is 2,074 cells / 2,524 route edges / 282 finding IDs. The complete C join is 192 distinct cells / 402 edges: 183 reported PASS and 9 reported FAILED; every C route is `candidate_unverified` with adequacy `not_established`. `verification.json` says `transfer_and_navigation_only`, `product_closure=not_established`, zero raw VM archives. Exact finding/cell queries are navigation evidence. P41 inherited-red ownership has not been established.

Each writer below has a separate Git checkout with its actual `codex/e02-C-<slug>-20261006` branch, base above, and saved create/resume admission JSON (both exit 0). Git branch attachment, root, clean state, HEAD and tree were read back. Root uses `codex/e02-C-continuation-20261006`; its sole runtime owner is ING streaming/cursor/modes. App-managed artifact registration is not the Git/workspace admission property. No stale registration was pruned.

| Finding | Complete bundle attachment | Historical ledger | Criterion-backed new verdict | Writer slug |
|---|---|---|---|---|
| B138 | FED-01 | partial | pending verification | federation |
| B139 | FED-02 | partial | pending verification | federation |
| B140 | FED-01 | partial | pending verification | federation |
| B141 | FED-01 | partial | pending verification | federation |
| B142 | FED-02 | partial | pending verification | federation |
| B143 | FED-02 | partial | pending verification | federation |
| B144 | FED-02 | partial | pending verification | federation |
| B145 | FED-01 | partial | pending verification | federation |
| B146 | OBS-01 | partial | pending verification | obs-udf |
| B147 | OBS-02 | partial | pending verification | obs-udf |
| B17 | SCL-01 | partial | pending verification | scholar |
| B79 | ING-01 | partial | pending verification | continuation |
| B80 | ING-01 | partial | pending verification | continuation |
| B81 | ING-02 | partial | pending verification | continuation |
| B82 | ING-02 | partial | pending verification | continuation |
| B83 | ING-03 | partial | pending verification | continuation |
| B84 | ING-03 | partial | pending verification | continuation |
| B85 | ING-02 | partial | pending verification | continuation |
| B86 | ING-03 | partial | pending verification | continuation |
| B88 | ING-01 | closed | pending verification | continuation |
| LA-005 | DFK-01 | held | pending verification | schema |
| LA-006 | DFK-01 | partial | pending verification | schema |
| LA-008 | HYG-02 | partial | pending verification | hygiene |
| LA-009 | HYG-02 | partial | pending verification | hygiene |
| LA-010 | MIG-01 | closed | pending verification | migrations |
| LA-011 | HYG-04 | partial | pending verification | hygiene |
| LA-012 | HYG-04 | partial | pending verification | hygiene |
| LA-013 | HYG-04 | partial | pending verification | hygiene |
| LA-018 | HYG-02 | partial | pending verification | hygiene |
| LA-021 | CAN-01 | closed | pending verification | canon |
| LA-022 | PLG-01 | partial | pending verification | plugins |
| LA-023 | PLG-02, PLG-03 | partial | pending verification | plugins |
| LA-024 | SCL-01 | partial | pending verification | scholar |
| LA-025 | SCL-03 | partial | pending verification | scholar |
| LA-026 | DFK-01 | held | pending verification | schema |
| LA-027 | DFK-01 | held | pending verification | schema |
| LA-028 | DFK-02 | partial | pending verification | catalog |
| LA-029 | UDF-04 | partial | pending verification | obs-udf |
| LA-030 | UDF-01 | partial | pending verification | obs-udf |
| LA-031 | OBS-01, UDF-01, UDF-02 | held | pending verification | obs-udf |
| LA-032 | UDF-05 | held | pending verification | obs-udf |
| LA-034 | BER-01 | partial | pending verification | berl |
| LA-036 | BER-01 | partial | pending verification | berl |
| LA-038 | DFI-01, DFI-02 | partial | pending verification | dfi-emb |
| LA-039 | EMB-01, EMB-02 | partial | pending verification | dfi-emb |
| LA-040 | EMB-03 | partial | pending verification | dfi-emb |
| LA-041 | DFI-03 | partial | pending verification | dfi-emb |
| LA-042 | EMB-03 | partial | pending verification | dfi-emb |
| LA-043 | CLI-01 | partial | pending verification | client |
| LA-044 | CLI-01 | partial | pending verification | client |
| LA-047 | MIG-05 | partial | pending verification | migrations |
| LA-048 | MIG-02 | partial | pending verification | migrations |
| LA-049 | MIG-01 | closed | pending verification | migrations |
| LA-050 | MIG-04 | partial | pending verification | migrations |

## Dependency order and shared owners

DFI/EMB have one author, including generation basis, immutable publication and all three actual readers. OBS/UDF have one author, including common helpers and public read API; DFI's generation-basis API is consumed through an explicit parent-coordinated seam. Catalog owns canonical registry/selection and RetrievalService, with a complete unfiltered declared source view; batch publish/benchmark source-admission predicates have the same author. MIG has one author for the shared CLI/binding registry and all distinct artifact/version/path profiles. HYG owns shared-shim tests and canonical tool-config generation; DFK uses separate tests. CLI owns all affected TS generator/package/dashboard/Atlas paths. Root alone edits root Python dependencies/lock and `fabric/data_plane/streaming.py`. B retains Core CAS and connector/pool lifecycle; A retains HTTP/lifecycle contracts.

The full C tasks are implemented independently in these writer lanes, followed by immutable candidate review. Read-only lanes independently reconcile the complete source/input census, numerical BERL oracle, ING fault/restart/readback, demography consumer set, installed package/client/schema consumers, cross-unit Git dependencies, environment inputs, and adversarial controls. There are 20 direct helpers and no nested delegation. A/C/G share one heavy numerical/full-data slot and one numeric thread; no heavy full-data run is required for the initial bounded fixtures. Client has its own PNPM install/pack slot. Databases, output roots, ports, temp fixtures and caches used for checks are lane-local; production data remains local and read-only.

## Pattern pass and acceptance

P01/P02: require actual producer → persisted typed artifact → bridge → consumer; refusal alone does not close a missing producer. P29/P32/P33: behavioral oracles and removal/adversarial controls keep markers intact while removing the actual law/bound/schema/selector/property. P35: every count above comes from the complete tracked set and full TSV join. P37: classify each deciding premise; declared/caller-supplied completeness, verifier labels, model labels or source identities cannot carry authority. P38: record the intended property, actual predicate, and a distinguishing case. P40: classify a second escape as the same class or a new one; widen the mechanism once or record a bounded residual and its falsifier. P41: inherited red requires exact slice-base replay and complete input-denominator disjointness. Plans and test counts never close findings.

ING separates UTC 86,400-second exact source-event/version dedupe from operator/input/output bounds and row-schema membership. Restored state at a smaller cap must refuse before flush/write/cursor advance; oversized input refuses before runtime materialization. Live keys are never evicted to satisfy a count cap. B86 compares actual membership/quarantine at batch sizes 1/2/8. All windows and CAS frontier cuts are exercised by independent fault controls.

BERL separates conditional `E[f(X)|X_S=x_S]` from background replacement. Gaussian and exact weighted finite-stratum oracles distinguish the games. A real, content-bound, verifier-admitted law and independently established structural model bound are required for certified precision; fixed coalitions/error/seed/cap precede IID draws. Missing E/F law producers remain typed blockers. CAN closes the raw-Core writer class through its canonical owner/strangle, not one adapter per caller; any required B Core change is a supplier contract in Git. FED uses actual JOIN/SUMMARY composer/readback and independent stdlib relational oracles; HTTP/export is surface_out_of_scope.

All remaining C bundle criteria retain their original acceptance: request-scoped DFI context and full resume basis, FQN/resource/wheel/sdist DFK census, immutable embedding selectors and actual readers, distinct migration owners through CLI, registered OBS/UDF stage/read API parity, Scholar exact CAS snapshot downstream, real one-call Economics trainer/actor readback, and importer/package/process HYG census. Unknown FQN support, schema/version policy, registered-stage authority, inventory producer or backend stays held/UNRUN with an exact missing input; no green-test contract is fabricated.

## Delivery and preservation

For each finished slice: verify Git attachment; freeze implementation SHA/tree; independently inspect full base→candidate diff including tests and companions; run focused deciding checks and negative controls; commit implementation; then commit a machine handoff that references that implementation SHA/tree and preserves commands, input identities, outputs, limitations and next owner. Push only the own topic and read back its remote branch/committed handoff. G performs broad regression once after integration freeze and is the sole integration/main publisher. Full-data residuals go to G by SHA without moving data. After deciding outputs and useful changes are preserved, only repeatable test directories/environments may move to Trash; no permanent removal or Trash emptying, and no production/code/useful docs/unique evidence cleanup.
