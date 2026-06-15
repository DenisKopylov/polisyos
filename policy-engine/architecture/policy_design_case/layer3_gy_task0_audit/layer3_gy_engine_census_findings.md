# GY-0 Engine Reality Census — Findings & Methodology

**Date:** 2026-06-14 · **Branch:** `codex/consolidated-all-changes-20260612` ·
**Case:** `ua-msme-affordable-loans-2022` (credit_access → firm_survival; route G1→G2→G4→G5→G6→G7)

Artifacts produced by this task:

- `architecture/policy_design_case/layer3_gy_task0_audit/layer3_gy_engine_census.json` — the census: **69 rows**, zero `unknown`, one row per pinned-route asset plus explicit split rows where the first pass conflated producer / consumer / surface.
- `tools/quality/validation/check_layer3_gy_engine_census.py` — the completeness gate: **PASS, 0 violations** on the current census; rejects `n/a` / see-file hashes, unnamed upstream blockers, stale `row_count` / digest, laundering gap mismatches, and tools-only `wired_and_works` claims.
- `tests/repo_quality/tools/test_layer3_gy_engine_census.py` — negative coverage for the exact loopholes found in the second pass.
- This note — methodology, reproducible smokes + hashes, duplication map, and the GY-0.5 implications.

## Census Discipline Actually Applied

Every execution/evidence-bearing status is backed by a `sha256:<64 hex>` run/probe hash. `never_invoked` rows are allowed only when the row names the observed reason: a DAG skip, a missing producer, an omitted catalog injection, or an explicit out-of-route boundary. No README, registry tier, seed label, or prior plan prose was treated as evidence.

The second pass hardened the first pass in four places:

- Split mixed rows: RetrievalService fastlane vs catalog lane, run_experiment workflow path vs NL-surfaced path, DataNeedSpec existing NL path vs missing catalog enrichment.
- Reclassified false greens: top-level scientist workflow is `fails` / `wired_but_rotten`; Manski is an executable producer with no pinned-route consumer; connector rows are registered but not invoked.
- Separated DAG skip causes: three `blocked_input` nodes are missing non-lex inputs; nineteen downstream rows are `blocked_upstream` by lex.
- Added out-of-route reuse rows for Scholar/OpenAlex so GY-6 can wire existing code rather than invent a new search engine.

## Reproducible Smokes

All runs were from repo root with `sys.path.insert(0, "src")`. Foundry/simulation paths require `JAX_PLATFORMS=cpu`.

| # | Smoke | Result | output_hash |
| - | --- | --- | --- |
| 1 | `DatasetCatalogGraph(prod_catalog).search_datasets(<pinned terms>)` | 8 on-target hits/query over 137,176 datasets; text arm only because embedder is absent | `sha256:70959ff19fd70e5379539a60ea9ce0cc6901cfdb9759023ad0e6adabb1510845` |
| 2 | `MetricSearcher` / `SemanticCatalogIndex` over production curated contracts | 3 contracts indexed; hashing-BOW surrogate confirmed | `sha256:bf7bb8a1d267839e4841bb764291a92ab3bc6428c141213c0f50ac5e4be18ae1` |
| 3 | `RetrievalService(dataset_catalog=None).resolve(DataNeed(metric=gdp))` | curated fastlane resolves one fetch plan; catalog lane absent | `sha256:edf2c6030a9769452d34426896cc61774fd30f49a0c0ba9bc5d913771ded2771` |
| 4 | `run_selected_workflow(scientist_policy_design)` on real UA panel | final status `fail`; 14 ok / 1 fail / 22 skip | `sha256:66dcc7012bbc08aa79023c441dac05ab97d06053939df0f8c18d01e45955866e` |
| 5 | `causal.bounds.manski.pure_step(...)` on real 40-point catalog panel | ATE bounds `[-0.475, 0.525]`, width 1.0, naive 0.051 | `sha256:ae6aece3a480d078305ed1964661fda25382cc6b0c37f0f41a32a0c0e20ff0f3` |
| 6 | `get_registry(); ensure_all_methods_registered(); list_all()` | 389 registered methods, 157 namespaces, 714 tags, 172 route-relevant | `sha256:48b4014792dcb71ed0e4f1e509071061d17a3c2203c6e1facef80e4f4070f68f` |
| 7 | connector/tier census | 12 route connector ids; transport_ready 34,308 / catalog 14,870 / fetchable 7,668 | `sha256:55dcca3f80a29ce244310662135bdd2efc61a15f86b50604e727dab4fc7cc286` |
| 8 | `DataNeedSpec` → `DataNeed` → `RetrievalService` smoke | existing NL demand contract reaches retrieval; 1 spec, 1 fetch plan | `sha256:d31e9b698692f61aabbd9acfcd6a76aa0ff2e8a4e287929d9797a3c248ecab6a` |
| 9 | `check_policy_design_case_layer3_gx_hardening.py --output-format json` | status=pass; expected_red_check_count=0; issue_count=0 | `sha256:e30d15c7bbaa3d425b9a5ab58bc265b4afd70369d9bfb99c43f0e2c72cb62048` |

Production catalog scale for the route: 137,176 datasets, 56,846 metric bindings, 3,708,006 observations. The hnsw index and embeddings are present on disk, but `sentence_transformers` is absent, so vector search degrades to text-only in the current environment.

## Critical Findings

1. **The "~1184 reducer_provenance_missing" progress meter is stale.** The GX hardening validator now reports 0 expected-red and 0 issues on this consolidated branch. GY-0.5 must re-baseline; tasks framed as "drive 1184 to zero" are already obsolete.

2. **The pinned-route baseline shifted.** Current final outcome is `search_ceiling_repair_required`, provisional `unchanged_blocker`, not the plan precondition's `typed_blocker`. That points first at GY-1 catalog wiring and search recall/freshness, not provenance backfill. The positive-status laundering firewall remains clean: positive candidate statuses are excluded.

3. **The scientist workflow is invoked, persisted, and failed.** `run_lifecycle.py:1408` calls `run_experiment` and discards its return, but the scientist executor still persists the workflow report/final state to CAS and run indexes. `nl_pipeline.py:6596/6618` can surface the report. Because the current report is failed/candidate and bypasses G4/G5 producer-root reducers, GY-2 is repair-then-govern, not wire/build.

4. **Lex is the real stop-rule repair.** `run_hierarchical_policy_search` is wired and invoked, but fails with `verified_policy_option_rate: lower>=upper`. The seed label `wired_and_works` was never an execution fact. Repair lex or its thin-input degeneracy before governing downstream workflow outputs.

5. **Not every DAG skip is lex.** `build_literature_prior`, `reconcile_causal_graph`, and `run_causal_evaluation` are `blocked_input` because the pinned route lacks causal/literature/observational inputs. The foundry/simulation/governance/decision-packet path is `blocked_upstream` by lex.

6. **Foundry method coverage is registry coverage, not route consumption.** The registry loads 389 methods and the DAG catalog/preflight nodes work. The Manski method smoke proves a representative method is executable on real arrays, but it is `producer_without_consumer` until the pinned DAG reaches compile/simulation after lex repair.

7. **DataNeedSpec was under-credited.** NL → `DataNeedSpec` → `DataNeed` → `RetrievalService` already works. GY-3 should build only the `RequiredDataSpec` → `DataNeedSpec` bridge. GY-1 should also wire `LLMDataNeedExtractorAgent.dataset_catalog` enrichment, because the agent accepts a catalog but production constructs it with `None`.

8. **Connector reality remains precise, not green.** All 12 route connectors have implementations and generic replay fixtures, but the fixtures are scaffolds and real outward fetches were not run. Rows are `built_not_wired` / `not_exercised_network` until GY-1 emits catalog-backed fetch plans and the optional network suite is run. The SDMX fixture reference was corrected to `tests/_data/fabric/shared/source_contracts/sdmx.generic.replay.json`.

9. **Scholar/OpenAlex is a follow-on reuse target.** Scholar deep search is out of the pinned route, but the census records that default provider failover exists and `data_forge.domains.academic.openalex.OpenAlexClient` already exists. GY-6 should wire/extend that client rather than build a new academic search engine.

10. **Environment constraints are named, not hidden.** Foundry/simulation require `JAX_PLATFORMS=cpu` because the Metal backend raises `UNIMPLEMENTED: default_memory_space`. The search hnsw/vector arm needs `sentence_transformers`; without it, the text arm remains executable but the vector arm is degraded.

## Seed-Finding Corrections

| Seed asset | Seed claim | Census verdict |
| --- | --- | --- |
| scientist DAG | `run_experiment` at `run_lifecycle.py:1408`; destination unknown | Confirmed production invocation; return discarded; bundles persist to CAS/run index; NL can surface failed/candidate output; GY-2 = repair-then-govern |
| `run_policy_design_workflow` | lives in `workflows/policy_design.py` | Function is `builder.py:635`; `policy_design.py` holds the spec |
| lex adapter | `wired_and_works` | Corrected to `wired_but_rotten`; invoked and fails on real input |
| RetrievalService catalog | built with no `dataset_catalog` | Split: curated fastlane runs; catalog lane exists and is `built_not_wired` |
| `SemanticCatalogIndex` | duplicate | Confirmed bounded hashing-BOW surrogate; demote/bound under GY-1 |
| `DataNeedSpec` | exists but not invoked | Corrected: NL path reaches retrieval; missing bridge is `RequiredDataSpec` → `DataNeedSpec` |
| Foundry methods | method layer works | Refined: registry works; representative method smoke works; per-method route consumption blocked behind lex/foundry DAG |
| connectors | transport-ready implies executable | Corrected: registered/replay-scaffold only; real network fetch unverified |
| reducer provenance meter | ~1184 missing | Corrected: GX validator now reports 0 |

## Duplication Map

- **Search engine:** canonical = `data_forge.DatasetCatalogGraph` (hnsw+text, 137k datasets). Duplicate/bounded surrogate = `fabric.SemanticCatalogIndex` (hashing-BOW, curated contracts). Runtime today = `RetrievalService(dataset_catalog=None)` curated fastlane; GY-1 wires `RetrievalService.dataset_catalog_lane`.
- **Demand contract:** canonical = `scientist.agent.DataNeedSpec`. Existing NL path works. GY-3 builds `foundry.RequiredDataSpec` → `DataNeedSpec`; GY-1 wires `LLMDataNeedExtractorAgent.dataset_catalog`.
- **Design space:** canonical = lex `HierarchicalPolicySearchAdapter` + `TemporalInterventionSequencer`, subordinated through DAG node `run_hierarchical_policy_search`. GY-5 folds into GY-2 repair/governance.
- **Design process:** canonical = scientist workflow invoked via `run_experiment`; no second DAG execution path should be built.
- **Engine-side ports:** canonical = `scientist/adapters/foundry_bridge.py` and `scientist/adapters/fabric_bridge.py`; foundry bridge is exercised, fabric bridge waits on catalog-backed retrieval.
- **Scholar search:** out-of-route follow-on = existing `ScholarDeepSearchService` provider policy plus existing `OpenAlexClient`.

## GY-0.5 Implications

- **GY-1:** wire existing catalog lanes, specifically `RetrievalService.dataset_catalog_lane` and `LLMDataNeedExtractorAgent.dataset_catalog`; demote/bound `SemanticCatalogIndex`; then rerun the search ceiling baseline.
- **GY-2:** insert lex repair before governance. After lex passes, govern the existing persisted scientist workflow/NL surface through G4/G5 producer-root reducers.
- **GY-3:** build only the `RequiredDataSpec` → `DataNeedSpec` producer bridge; do not introduce a parallel demand type.
- **GY-5:** fold into GY-2 because lex is already subordinated through the DAG node; the work is repair/provenance of the existing path.
- **Connectors:** after GY-1 emits fetch plans, run the optional network suite and convert connector rows from `not_exercised_network` to real fetch hashes where possible.
- **GY-6:** if Scholar widening is retained, wire the existing OpenAlex client into the existing provider failover policy.
- **Stale-premise tasks:** delete or rebaseline any task whose only target is the old reducer provenance count.

## Honest Scope Boundary

The census covers engine assets touched by the pinned UA-MSME route plus two explicit out-of-route reuse discoveries. It does not claim per-method Foundry execution for all 172 route-relevant methods, real network fetches for all connectors, or downstream analytic correctness for nodes blocked by lex/input gaps. Those surfaces are named blockers, not hidden unknowns.
