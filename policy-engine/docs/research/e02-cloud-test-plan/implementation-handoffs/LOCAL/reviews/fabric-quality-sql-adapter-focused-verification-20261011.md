# Fabric quality, data-requirement adapter, and I001 residual verification packet

## Read-only result

This packet maps the current bounded source candidate to real call paths and existing tests. I ran no tests, imports, lint, CLI, or build, and changed no product files. Every proposed command below is therefore **UNRUN**; a skipped DuckDB test is not evidence.

Checkout: `/Users/deniskopylov/.codex/worktrees/e02-unified-local-20261009/polisyos`. The requested source base is `8c42e13b76e13c0d1f81ab3b2b3e974c9e2cdf71` (tree `e1e4833c523f65dc07a8a9f751e8b08ae34dd460`). Current branch HEAD is `785944776c39722923c3a34d4ab7a3594dc03287` (tree `cb0c7a5bbed0fbfe5910bfbe9d0cb21457e664db`); HEAD itself does not contain these path edits. The current worktree has ten target paths modified relative to HEAD, all unstaged: 69 insertions and 37 deletions. It is not a clean checkout, and this review does not assign any unrelated red as inherited.

The earlier selected-89 inventory is `LOCAL/reviews/residual-source-boundaries-independent-20261011.json` (SHA-256 `4925b2d84684c06fee482e9422158356750e84b56c86ad9c76c01669cb5b8798`) with its review `.../residual-source-boundaries-independent-20261011.md` (SHA-256 `ec768705f49ef2188364c9b9595420e9286b1733f8642658af62cf9f6814b36f`). Its Fabric route names five paths and marks runtime unrun. The current candidate hashes for those five paths below match that inventory’s candidate hashes. The earlier eight-I001 anomaly review is `LOCAL/reviews/residual-eight-import-anomalies-final-independent-20261011.json` (SHA-256 `763b5f13f10bfe5277cb0075cde9812463c04b99a0daf094a03bd8b3d8558d4d`) and its Markdown companion (SHA-256 `90d59165319a37274e82345a522a2ebd5a289f45f87922f6f9d8ea94eee367b8`). Seven of its eight candidate files still match that reviewed postimage; `tools/archive/migrate_to_trinity.py` is now a different candidate and is assessed below. These prior files are bounded source-review inputs, not current test receipts.

## Exact current footprint

The table gives SHA-256 of the file at the requested base and SHA-256 of the current worktree bytes. The only target changes are these ten paths: the five Fabric quality/adapter paths plus the five non-Fabric remainder paths from the eight-I001 anomaly cohort.

| Path | Base SHA-256 | Current SHA-256 | Current change |
|---|---|---|---|
| `src/polisyos/fabric/_adapters/observability.py` | `7ed4578be91e2d28b201c05e19bfbac0eb3f355635aa78fbb3b669fa34673502` | `85744adcedbe5bb1a1d6cb026096598f1f49678219146d40982fafa1b294c457` | RUF022: reorder `__all__`; names retained. |
| `src/polisyos/fabric/quality/__init__.py` | `9600f49bb3ac6915eb41017f2f5ccbeee4b67ea1b7777697dc796bca6cb69151` | `f8d579044b9143c63012912f2bea947712c9a644d9089696076fd5243ac3c0ff` | Reorder facade imports; explicit `_default_metrics` package alias retained. |
| `src/polisyos/fabric/quality/quality.py` | `8dc607b2fd88a44f796e81dd6eb62e0b7f8098a06af742d4392d4e8fcd632ea9` | `cd288a354f471ff5cf8f2ad6369b922295081a77dea994254f5949ca4e155a76` | Import reorder; three narrow S608 suppressions/comments on existing validated-identifier SQL. |
| `tests/unit/fabric/catalog/test_data_requirement_adapter.py` | `aeda0665c3df07c2575c57f91ea6c07c7deeb662d04f76f8c00ed31e7d332702` | `24c1c187c6eba363dc5a653b0e5fab1bf89c9603963a0d03ee6df98a7e092f10` | RUF015: replace `[0]` selection with first-match `next(..., None)` and explicit presence assertions. |
| `tests/unit/fabric/test_quality_indicators.py` | `6602f58b4d87a6b74b040e883c0d1c56d649827cd79e4f73b5297ff30a8359cf` | `27bb3f801e5fca5d65c703657934baf08df1a016377615ea30576a3542c11437` | Import reorder; add malicious DuckDB catalog-column refusal and table-preservation assertion. |
| `tests/unit/remediation/test_dfi_02.py` | `f72982b622be5d5bdf5eb67f77370312796f6ee40049d0617c4200dc4677cc18` | `f2c8e6cb2e80138bd21c7835f39dfd4d8776df0ef5c4c340f0e84c282042be30` | Import reorder; replace a one-argument test lambda with same-result local function. |
| `tests/unit/remediation/test_dur_02.py` | `22aa14c0d4e8a3ad6c0bcc0ae1101bfeff551f2fb69c89610507cf80210449a8` | `9e9e1eeb0eab109210a27b422267c7973ff0364efde915c33afb1b4a2469e162` | Preserve eager control imports with ordered `import_module` calls; reorder runner imports. |
| `tools/archive/migrate_to_trinity.py` | `7376bd594c637bae7962a2ba7cc73ac2fe48cc1268b1b85cb191ef058279cd9e` | `dec998baa9e959b50ab1dd18aba76724eee670a185c3e7dcc79056ce79a0b473` | Keep runtime `collections.abc.Iterator` binding with explicit TC003 suppression; reorder imports. |
| `tools/ops_runners/experiments/run_msme_final_fresg_suite_v3.py` | `07a9d4d94c478895d0763079c9686006f5e7c5eaa9268ec68337b333af93558d` | `589606102888b3c7685222175c371b1e8bc57a9ab8503e4c1fc864be55bca38a` | Sort sklearn imports; remove `f` from literal text; rename unused loop variable. |
| `tools/quality/diagnostics/check_setup.py` | `30dc443f37ba7e55a6cd37ec4854b1db25c91064163e0ddf16062c02abe76a80` | `19a14fd32a2216a53fa6dae5d08753b08428983c55efcfb314f805388ff14e75` | Correct comment and sort imports; DuckDB/JAX remain before `common.config`. |

For a bounded source commit, use only this ten-path allowlist (or split the five Fabric paths from the five non-Fabric anomaly remainder). Do not stage the surrounding worktree. This packet is a review companion, not part of that source commit.

## Call paths and deciding checks

**DuckDB quality calculation.** `compute_quality_from_duckdb` in `src/polisyos/fabric/quality/quality.py` validates and quotes the table identifier before connecting, counts rows and describes the table, validates discovered column names, then composes null/non-finite SQL from quoted identifiers. The S608 comments do not change SQL construction. The new catalog-column test reaches this function with a malicious DuckDB column name, expects `UnsafeIdentifierError`, and checks the table still contains its row. Its “before dynamic queries” title is bounded: the function has already run the safe-table row count and `DESCRIBE`; the column-derived checks are the queries that must not be assembled from the malicious identifier. Existing table-injection, non-finite-as-missingness, and injected-metrics cases are in the same class.

Static caller census found no production caller of `compute_quality_from_duckdb`; direct calls are in `test_quality_indicators.py`. It returns `QualityIndicators` and may record a metric, but the production `QualityGatePass` path consumes a `DataQualityReport`/`QualityIndicators.from_quality_report`. Therefore a direct DuckDB helper test is not evidence that this function is bridged into the production quality-gate flow (`bridge_missing` for that broader route). Do not widen this lint/security change into a capability claim. Also, the existing injected-metrics test monkeypatches the package alias `polisyos.fabric.quality._default_metrics`, while the function resolves the module global in `polisyos.fabric.quality.quality`; the test proves the supplied registry receives a score and that the supplied branch is used, but not that an accidental *additional* module-global lookup is absent.

**Data-requirement adapter.** `build_source_contract_requirement_bindings` is re-exported by `polisyos.fabric` and `polisyos.fabric.catalog`. It maps selected/blocked capability rows and rejected alternatives into typed-by-schema dictionaries carrying requirement/claim refs, source asset/field refs, rights, quality, limitations, and reasons. Runtime consumers are `producer_pipeline._fabric_requirement_report` → `_fabric_pipeline_bindings` and `ProductionDataContractIndex.build_data_requirement_binding_report`. The edited unit test invokes the actual adapter with a selected capability plus rejected alternative and checks those fields; its assertion change preserves first-match selection while turning absent expected rows into readable failures.

The strongest existing producer-consumer selector is `tests/unit/runtime/quality/test_wave7_requirement_pipeline_integration.py::test_requirement_spec_pipeline_runs_real_w7_adapters_and_acquisition_bridge`: it invokes the non-stub requirement pipeline with a compiled data spec and source-contract candidate, then checks selected Fabric result, emitted binding state, and acquisition records. It does not establish a persisted source-contract artifact/CAS round-trip. `tests/unit/runtime/quality/test_production_data_contract_index.py::test_contract_index_can_bind_directly_against_compiled_data_requirement_specs` covers the index adapter’s selected report. The corpus-stub producer-pipeline test is not a substitute for the real Fabric path because the implementation branches around `_fabric_requirement_report` when stub responses are supplied.

**Import/export anomalies.** The current quality package order still initializes `quality.quality` first because `fitness_report` imports it; the package’s explicit `__all__` stays `DataFitnessReport`, `MetricFitness`. The tested package import in `test_quality_indicators.py` exercises `QualityIndicators`; `test_semantic_group_imports.py::test_fabric_quality_group_preserves_report_and_processing_contract_behavior` exercises report/processing behavior through owner modules. These do not directly assert package-export object identity, so a fresh-process identity comparison should accompany the quality facade check. The observability file only moves the same `__all__` names; `test_observability_governance_quality_phase4.py::test_fabric_slo_contract_covers_phase4_slis_and_blocks_burned_budget` exercises real SLO behavior through direct module imports, not list order.

The DFI change is covered semantically by `tests/unit/remediation/test_dfi_02.py::test_pipeline_consumes_canonical_api_and_preserves_ingest_counters`, `::test_facade_override_is_scoped_to_supported_loader_binding`, and `tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py::test_core_sources_facade_does_not_broadcast_new_globals_to_leaf_group`. The DUR import statements deliberately initialize the same compatibility modules before the store; run `tests/unit/remediation/test_dur_02.py` plus `tests/unit/remediation/test_dur_02_process.py::test_actual_handler_loses_every_protected_write_after_expiry_and_takeover` to exercise both module import and worker behavior.

**Archived migration utility.** The current `dec998…` version retains `Iterator` as a runtime global, so the earlier type-reflection concern from the intermediate candidate that moved it under `TYPE_CHECKING` does not apply. However, the import `polisyos.ir.legacy.migrations.surface_to_trinity` has no corresponding tree under `src/polisyos/ir`; the README classifies this script as an archived historical utility. This CLI is not presently established as runnable, and no CLI/function behavior is claimed or test command proposed until that missing dependency is resolved.

## Commands for the post-freeze owner

Run from `policy-engine/` with the candidate’s normal test environment. These selectors are recommendations, not results from this review.

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/fabric/test_quality_indicators.py::TestDuckDBQualityComputation \
  tests/unit/fabric/test_safety.py \
  tests/unit/fabric/test_semantic_group_imports.py::test_fabric_quality_group_preserves_report_and_processing_contract_behavior \
  tests/unit/fabric/test_observability_governance_quality_phase4.py::test_fabric_slo_contract_covers_phase4_slis_and_blocks_burned_budget
```

Require zero skips for `TestDuckDBQualityComputation`, especially `test_rejects_unsafe_catalog_column_before_dynamic_queries`; otherwise the DuckDB safety witness remains unrun.

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/fabric/catalog/test_data_requirement_adapter.py \
  tests/unit/runtime/quality/test_production_data_contract_index.py::test_contract_index_can_bind_directly_against_compiled_data_requirement_specs \
  tests/unit/runtime/quality/test_wave7_requirement_pipeline_integration.py::test_requirement_spec_pipeline_runs_real_w7_adapters_and_acquisition_bridge \
  tests/unit/runtime/quality/test_producer_pipeline.py::test_second_pass_requires_selected_rejected_or_blocked_requirement_binding

PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/remediation/test_dfi_02.py \
  tests/unit/data_forge/domains/catalog/batch/test_core_sources_ingest.py::test_core_sources_facade_does_not_broadcast_new_globals_to_leaf_group

PYTHONPATH=src .venv/bin/python -m pytest -q \
  tests/unit/remediation/test_dur_02.py \
  tests/unit/remediation/test_dur_02_process.py::test_actual_handler_loses_every_protected_write_after_expiry_and_takeover
```

`tools/ops_runners/experiments/run_msme_final_fresg_suite_v3.py` has no focused test found; do not claim experiment output equivalence from import inspection or run it as part of this narrow packet. `check_setup.py` likewise has no focused test; the import reorder does not change DuckDB/JAX-before-config order or establish bootstrap execution. If either executable’s behavior is needed, bind a separate exact command after freeze. The archived Trinity tool is excluded until its missing module is supplied.

## P40 and current limits

The import/export portion is **SAME_CLASS_DEEPER** with the existing I001 import-binding/order and initialization-observability cohort, not a new class. The earlier eight-anomaly review already records observable package-global order and requires no per-path repair ladder. In the current candidate, the type-annotation binding in `migrate_to_trinity.py` is preserved; its missing legacy module is an independently bounded execution limit, not a new consequence of import sorting.

The S608 statements are actual guarded identifier interpolation and receive source-local suppressions; the targeted DuckDB negative is the deciding security property. The data-adapter test is a test-only clarity change. No formal G finding disposition or closure follows from this packet, from a prior static review, or from a proposed test command.
