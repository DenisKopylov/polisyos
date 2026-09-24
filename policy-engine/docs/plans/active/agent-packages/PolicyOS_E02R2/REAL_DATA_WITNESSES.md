# Real production-data witnesses for E02-R2

This is a witness plan, not a test receipt. No test was run and no native database was opened while preparing it. Use the existing read-only `production_data` symlink; do not copy, clone, archive, or write beneath it.

Canonical data root: `/Users/deniskopylov/polisyos/policy-engine/production_data`.
Root manifest: `policy-engine/production_data/manifest.json@sha256:9e0e0aa0acd3c91f0120a80a2570be358ff16a63218abcd998f4d6f0212b6105`.
The inspected top-level entries include `datasets_full_phase3full_20260327_183054`, `canonical/local_data_20260501/ukraine_server_support_20260410`, `ukraine_agent_simulation_baseline_20260410`, `lex`, and `policyos_academic_runtime_slim_20260411T112032Z`.

Finding cards: `PolicyOS_E02_Combined_Agent_Package/source/B_r19_original.md@sha256:9c98584cbfa72996b058abf127f6c689f919a3421cdd563a82c84a7324ab39b5` (including B61) and `PolicyOS_E02_Combined_Agent_Package/source/LA_r09_original.md@sha256:2e13d05d40ab162dba6f1ed495865037bc08fc359a987e7a42c4d445a9b8d727` (including LA-021, LA-031, and LA-032).

## Required R13 witness: served WDI acquisition and tenant-safe re-entry

The existing served witnesses are:

- `tests/integration/core_runtime/test_acquisition_world_growth_chain.py::test_actual_wdi_admits_delta_and_reenters_same_case[False/True]` — `@sha256:656b39a16877682deac0547cfada8c22579a16e85da7136e3a1fc8cf659ebbe9`.
- `tests/integration/core_runtime/test_acquisition_tenant_custody.py::test_actual_acquisition_producers_preserve_tenant_custody_through_reentry` — `@sha256:3b7e3c89f42ec1ebdaadb2f99224f46901ebc15e94872816a79ac61645ce4fa0`.

These exercise the served chain, but do not directly name the production-data root. R13 needs one real-catalog witness through the existing `AcquisitionWorldGrowthBridge` / served acquisition caller. Resolve the selected WDI source and indicator from the real catalog, use an intercepted deterministic response for the one authorized connector request, and prove overlay admission, passport and native-epoch qualification, then same-case re-entry with tenant custody. Retain the negative proving the local legacy route cannot mint an authoritative WMR. A source-only selector test or the existing fixture-based integration test is not the production-data witness.

The relevant catalog is `production_data/datasets_full_phase3full_20260327_183054/dataset_catalog.duckdb`. The existing acquisition/substrate owners open DuckDB in read-only mode, including `substrate_registry.py@sha256:6321750ec9641369e683c9a38795405c93dc5e4dc8d245e25c61f2cc199bbd5a`. Keep connector egress inside the authorized request and journal; no health probe or unrelated fetch. Use the runtime-supplied artifact store. Put the CAS, overlay, and receipts under pytest `tmp_path` or a per-job scratch directory outside `production_data`.

Resource estimate: one medium integration process group. Use the intercepted transport. Read-only catalog readers may coexist, but avoid running this at the same time as the numerical panel job to limit combined I/O and memory pressure.

## N5/N8 real-panel witness: conditional on SIM-03 finding closure

The N/no-record SIM-03 findings B19, B21, B23, B25, and B26 concern simulation comparison, replication, reuse, metric completeness, and joint composition. Their distinguishing checks need behavioral tests. If the lane claims these findings closed through the live runtime, include a real-panel witness through the existing `GenerationCycleController` N5/N8 owners: use the real world-model record, show N5 consumes the actual panel and declared baseline/replication semantics, and show N8 either consumes bound evidence or remains typed pending. Do not manufacture a positive calibration result.

The closest current data-backed basis is `tests/integration/runtime_quality/test_data_state_substrate.py::test_real_l4_data_state_builds_populated_world_model_record_and_executes_sim` — file `@sha256:ec7191b1713b09f2a312ea229cc1d538ebfe8306b1de2fe365e480b9211c7adf`. It builds from the canonical Ukraine support corpus with `agent_limit=128`, observes a registry exceeding 8 million rows, and runs Foundry. It does **not** exercise the generation-cycle N5/N8 path; do not report it alone as the SIM-03 real-path witness.

**Whole-file P41 invocation of `test_data_state_substrate.py` is UNRUN and must remain so:** its `test_l5_proxy_identification_materializes_bounded_state_and_toggle_changes_it` calls `_repo_with_household_identification_mode`, which uses `shutil.copytree` on a directory inside `production_data`. Copying any portion of the production tree is prohibited. Do not run the file as a whole. If a data-backed test from this file is needed, select only an inspected safe test, or first replace the copying fixture with a symlink plus a derived writable scratch override, then review that delta before running it. Selected safe tests must keep all CAS/workspace outputs outside the data tree.

Resource estimate: one exclusive native/numerical process group with `JAX_PLATFORMS=cpu`. The bounded agent count controls simulation size, not the cost of scanning the underlying catalog/corpus. Run after the R13 job; do not overlap with the Ukraine builder or large DuckDB jobs.

## Held findings that touch production substrates

### Ukraine builders: H LA-031 and LA-032

The cards explicitly name `data_forge/domains/ukraine/builders/common.py` / its D4 imports (LA-031) and the Ukraine demographic reader’s mixed-layout behavior (LA-032). The card discriminators are namespace/caller and bundle-layout semantics; focused fixture tests can establish those properties without rebuilding the full production corpus. Existing tests include `tests/unit/data_forge/domains/ukraine/test_builders.py@sha256:abc71b5e91b36a481ef496f780f82195542e03c1628559b173bb7eff58765f18` and `test_cli.py@sha256:0ff9d327d3164c4cf52894188beba3f3d42547157f879dbaf01e448c0634bec7`.

If a report claims an end-to-end production builder witness, use the existing `ukraine-data` CLI owner, `cli.py@sha256:eacccf70eb26bc857c44c628a8e7938d6076c0af34883e2752bfc91995b22a1b`, with a reviewed config whose inputs are read-only and whose `--root` points outside production data. Never use its default build root (`production_data/ukraine_part_b`). The CLI is server-gated by default, and the available canonical/Ukraine bundles are not proof that its configured raw-input route is local. If this cannot be established, keep LA-031/032 at their single named consumer/cutover blocker; do not launch a server build as a substitute.

Resource estimate: unit witnesses are light. A full builder run is a separate, potentially high-I/O job; schedule only after its input and output roots are resolved, and run exclusively.

### Academic runtime: H B61 only if its snapshot blocker changes

B61 concerns SKG cache identity when the database changes at a stable path. Its current held blocker is the owner-issued SKG snapshot. Until that evidence exists, a production database query cannot close the finding; retain the named blocker instead of paying for a large snapshot scan. If the owner snapshot is supplied, the existing `SKGQuery` path opens DuckDB with `read_only=True`; never copy or mutate the database. Keep any derived result in job scratch.

`tests/integration/runtime_quality/test_gy_s2_knowledge_substrate_lift.py@sha256:c82b86bca60801021e1c636a76cca0a5f86bcc512871597c8af567740ec8d8e1` reads the real academic and Lex databases, but it is GY-S2 plan coverage, not a B61 cache-identity witness. `tests/integration/scholar_scientist/test_extraction_strength_vocabulary.py@sha256:cfe578508eaac899556c53b5928f0fb15b2d42b10aa484f1a8f56fdcfc51f278` also uses the real academic snapshot; do not run it as general E02-R2 coverage. If B61 is reopened, isolate its query from the panel job because it reads a large DuckDB snapshot.

## Lex production database is out of scope for the named R/H/N findings

LA-021 is the canonical-codec finding; its re-verification uses the codec input corpus (the architect reported 418 inputs), not the production Lex knowledge graph. The held LA-005/026/027 are Data Forge/schema findings, and LA-031/032 concern Ukraine builders. No named R/H/N item in this lane requires reading `production_data/lex`. The Lex DB reader uses `LegalKnowledgeStore` with `read_only=True` if another task later requires it, but GY-S2 Lex coverage is optional plan scope here.

## Scratch, database, and concurrency rules

- Keep the canonical path and manifest SHA above as the data receipt. Do not copy, clone, archive, extract bulk data from, or write into any production-data subtree.
- Set `POLISYOS_PRODUCTION_DATA_ROOT` to the canonical root for owners that honor it. Use pytest `tmp_path` or a unique per-job directory under `$TMPDIR/e02-r2-prod-witness/` for CAS, derived DuckDBs, reports, and all other outputs.
- Open every production DuckDB with `read_only=True`; never `ATTACH` in write mode. Derived databases belong in scratch.
- Treat the panel run as exclusive. Schedule at most one other light test group alongside the R13 integration, and keep Ukraine build or academic/Lex full-database reads out of the numerical panel window.
- This document records a plan, not execution evidence. Every required witness still needs its own command, exit status, and captured receipt when run.
