# Polisyos Tools Reference

Generated from `tools.registry` command metadata.

## D1-L5 Source Phase Map

| Source phase | Focus | Current evidence |
|---|---|---|
| Phase 0 | SQL/shell injection, shell safety, destructive operation guardrails | `tools._lib.runner`, `tools._lib.sql`, `tools._lib.fs` |
| Phase 1 | atomicity, rollback, resource/I/O validation, degraded mode, legacy quarantine | `tools._lib.fs`, `tools._lib.http`, `tools._lib.preflight`, lifecycle status metadata |
| Phase 2 | unified CLI, shared runtime, packaging/import normalization, dependency graph, docs metadata | `polisyos-tools`, `tools.registry`, `tools.cli`, compatibility package shims |
| Phase 3 | critical tool test program, structured CI output, timing telemetry | `tests/tools/**`, `tools._lib.output`, `tools._lib.timing`, workspace gates |
| Phase 4 | cloud/scripts/benchmarks consolidation and deprecated cleanup | `tools/ops/**`, `tools/research/**`, compatibility wrappers and deprecation metadata |
| Phase 5 | incremental execution, cache, autofix/rule registry, hot-path maintainability | `tools._lib.cache`, `tools/quality/lint/**`, targeted `--fix` and changed-file modes |

## Validation Contract

- Regenerate this page with `uv run polisyos-tools docs --output docs/reference/tools.md`.
- `polisyos-tools workspace ci-parity` includes docs accuracy, strict MkDocs build, and semantic docstring checks unless `--skip-docs` is set.
- Deprecated and quarantined commands must keep `status`, `replacement`, and `reason` metadata in `tools.registry`.

## Documentation Impact

| Output cluster | Exact files | Source of truth | Validation |
|---|---|---|---|
| Generated command reference | `docs/reference/tools.md` | `tools.registry` command metadata, dependency graph edges, lifecycle status metadata | `uv run polisyos-tools docs --output docs/reference/tools.md` |
| Tooling READMEs | `tools/README.md`, `tools/validation/README.md`, `tools/devx/workspace/README.md`, `tools/devx/architecture/README.md` | canonical CLI behavior, workspace gates, validation helpers, architecture guardrails | `uv run polisyos-tools workspace ci-parity --skip-browser` |
| Shared D1-L5 how-to/reference pages | `docs/how-to/operate-ci-cd-platform.md`, `docs/how-to/manage-generated-artifacts.md`, `docs/how-to/release-policy.md`, `docs/reference/quality-gates.md`, `docs/reference/dependency-platform.md`, `docs/reference/merge-governance.md`, `docs/reference/ratchet-policy.md` | repo workflows, generated-artifact guardrails, release tooling, ratchet policy docs | `uv run polisyos-tools architecture guardrails check` |

## Backlog

| Gap | Priority | Tracking note |
|---|---|---|
| No missing required D1-L5 output pages | - | All required D1-L5 files listed in `docs/DOCUMENTATION_SOTA_PLAN.md` are present. |
| Additional per-category README expansion outside the D1 scope | P3 | Further category-local docs can land in D2 without blocking the D1 closure criteria. |

## Zones

| Zone | Categories |
|---|---|
| `devx` | `workspace`, `architecture`, `connectors`, `foundry` |
| `quality` | `lint`, `diagnostics`, `validation`, `testing`, `ci` |
| `ops` | `cloud`, `release`, `migrations`, `runtime`, `data`, `ukraine_data`, `calibration` |
| `research` | `benchmarks`, `demos` |

## Commands

### `devx`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
|---|---|---|---|---|---|---|---|
| `workspace` | `acceptance-audit` | `active` | `polisyos-tools workspace acceptance-audit` | Run the Phase 7 platform acceptance audit for the policy-engine workspace. | - | `./scripts/acceptance-audit` | - |
| `workspace` | `bootstrap` | `active` | `polisyos-tools workspace bootstrap` | Bootstrap a contributor machine for the policy-engine workspace. | - | `./scripts/bootstrap` | `workspace.doctor` |
| `workspace` | `ci-parity` | `active` | `polisyos-tools workspace ci-parity` | Run a local validation pass that approximates the main CI surfaces. | - | `./scripts/ci-parity` | - |
| `workspace` | `core-runtime-basedpyright` | `active` | `polisyos-tools workspace core-runtime-basedpyright` | Run basedpyright across the full core-runtime surface plus curated extras. | - | - | - |
| `workspace` | `core-runtime-closeout` | `active` | `polisyos-tools workspace core-runtime-closeout` | Validate and render the CORE common/runtime closeout ledger. | - | `./scripts/core-runtime-closeout` | - |
| `workspace` | `core-runtime-long-soak` | `active` | `polisyos-tools workspace core-runtime-long-soak` | Run the core-runtime long-soak evidence suite and emit machine-readable reports. | - | - | - |
| `workspace` | `core-runtime-mypy` | `active` | `polisyos-tools workspace core-runtime-mypy` | Run strict mypy over every Python file in the core runtime surface. | - | - | - |
| `workspace` | `doctor` | `active` | `polisyos-tools workspace doctor` | Preflight validation for contributor machines and local quality gates. | - | `./scripts/doctor` | - |
| `workspace` | `remote-acceptance` | `active` | `polisyos-tools workspace remote-acceptance` | Provision and drive a remote Linux runner for acceptance closeout. | - | `./scripts/remote-acceptance` | - |
| `workspace` | `verify` | `active` | `polisyos-tools workspace verify` | Run the standard fast local gate for policy-engine contributors. | - | `./scripts/verify` | `workspace.doctor` |
| `architecture` | `guardrails` | `active` | `polisyos-tools architecture guardrails` | architecture/guardrails | - | - | - |
| `architecture` | `scaffold` | `active` | `polisyos-tools architecture scaffold` | architecture/scaffold | - | - | - |
| `connectors` | `check-contracts` | `active` | `polisyos-tools connectors check-contracts` | connectors/check_contracts | - | - | - |
| `connectors` | `scaffold` | `active` | `polisyos-tools connectors scaffold` | CLI scaffold generator for Policy OS connectors. | - | - | - |
| `foundry` | `generate-stubs` | `active` | `polisyos-tools foundry generate-stubs` | Generate Foundry method stubs through the canonical tools surface. | - | `./scripts/generate_stubs.py`, `python scripts/generate_stubs.py`, `python3 scripts/generate_stubs.py` | - |
| `foundry` | `update-signature-baseline` | `active` | `polisyos-tools foundry update-signature-baseline` | Refresh the Foundry signature baseline through the canonical tools surface. | - | `./scripts/update_signature_baseline.py`, `python scripts/update_signature_baseline.py`, `python3 scripts/update_signature_baseline.py` | - |

### `quality`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
|---|---|---|---|---|---|---|---|
| `lint` | `check-scholar-imports` | `active` | `polisyos-tools lint check-scholar-imports` | lint/check_scholar_imports | - | - | - |
| `lint` | `collect-arch-metrics` | `active` | `polisyos-tools lint collect-arch-metrics` | lint/collect_arch_metrics | - | - | - |
| `lint` | `compare-baseline` | `active` | `polisyos-tools lint compare-baseline` | lint/compare_baseline | - | - | - |
| `lint` | `lint-connector-hardening` | `active` | `polisyos-tools lint lint-connector-hardening` | Enforce P7 connector hardening invariants for production HTTP connectors. | - | - | - |
| `lint` | `lint-connectors` | `active` | `polisyos-tools lint lint-connectors` | Law A & Law B enforcement for the connectors subtree. | - | - | - |
| `lint` | `lint-foundry` | `active` | `polisyos-tools lint lint-foundry` | lint/lint_foundry | - | - | - |
| `lint` | `lint-foundry-data-plane` | `active` | `polisyos-tools lint lint-foundry-data-plane` | lint/lint_foundry_data_plane | - | - | - |
| `lint` | `lint-imports` | `active` | `polisyos-tools lint lint-imports` | lint/lint_imports | - | - | - |
| `lint` | `lint-legacy-cutover` | `active` | `polisyos-tools lint lint-legacy-cutover` | lint/lint_legacy_cutover | - | - | - |
| `diagnostics` | `abi-diff` | `active` | `polisyos-tools diagnostics abi-diff` | diagnostics/abi_diff | - | - | `diagnostics.gen-schema` |
| `diagnostics` | `capture-env` | `active` | `polisyos-tools diagnostics capture-env` | CLI tool to capture and compare environment manifests. | - | - | - |
| `diagnostics` | `check-perf-regression` | `active` | `polisyos-tools diagnostics check-perf-regression` | Performance regression checker for CI/CD. | - | - | - |
| `diagnostics` | `check-scientist-node-version-bump` | `active` | `polisyos-tools diagnostics check-scientist-node-version-bump` | diagnostics/check_scientist_node_version_bump | - | - | - |
| `diagnostics` | `check-setup` | `active` | `polisyos-tools diagnostics check-setup` | Smoke test для проверки корректной установки всех компонентов Policy Engine. | - | - | - |
| `diagnostics` | `check-state-reads` | `active` | `polisyos-tools diagnostics check-state-reads` | diagnostics/check_state_reads | - | - | - |
| `diagnostics` | `check-udf-perf` | `quarantined` | `polisyos-tools diagnostics check-udf-perf` | diagnostics/check_udf_perf | diagnostics check-setup | - | - |
| `diagnostics` | `gen-schema` | `active` | `polisyos-tools diagnostics gen-schema` | diagnostics/gen_schema | - | - | - |
| `diagnostics` | `generate-ir-reference-catalog` | `active` | `polisyos-tools diagnostics generate-ir-reference-catalog` | diagnostics/generate_ir_reference_catalog | - | - | - |
| `diagnostics` | `generate-ir-schema` | `active` | `polisyos-tools diagnostics generate-ir-schema` | diagnostics/generate_ir_schema | - | - | - |
| `diagnostics` | `scan-fabric` | `active` | `polisyos-tools diagnostics scan-fabric` | Bootstrap utility to scan DuckDB files and generate draft data contracts. | - | - | - |
| `diagnostics` | `verify-scm-v3` | `active` | `polisyos-tools diagnostics verify-scm-v3` | Run SCM v3 verification checks and emit JSON/Markdown reports. | - | - | - |
| `diagnostics` | `verify-scm-v3-fullspec` | `active` | `polisyos-tools diagnostics verify-scm-v3-fullspec` | Build detailed SCM v3 full-spec verification (DoD 162 + Laws + SL layers). | - | - | - |
| `diagnostics` | `visualize-provenance` | `active` | `polisyos-tools diagnostics visualize-provenance` | Provenance visualization / validation utility. | - | - | - |
| `validation` | `check-ci-ratchets` | `active` | `polisyos-tools validation check-ci-ratchets` | Ratchet targeted CI escapes across common/core/runtime HTTP packages. | - | - | - |
| `validation` | `check-docs-accuracy` | `active` | `polisyos-tools validation check-docs-accuracy` | Validate published docs against current repository reality. | - | - | - |
| `validation` | `check-docs-gate` | `active` | `polisyos-tools validation check-docs-gate` | Run the Phase D6 path-aware documentation drift gate. | - | - | - |
| `validation` | `check-docstring-quality` | `active` | `polisyos-tools validation check-docstring-quality` | Fail CI when public API docstrings regress to generic placeholders. | - | - | - |
| `validation` | `fabric-schema-governance` | `active` | `polisyos-tools validation fabric-schema-governance` | Validate Fabric connector contract evolution against governance policy. | - | - | - |
| `testing` | `check-playwright-quarantines` | `active` | `polisyos-tools testing check-playwright-quarantines` | Validate Playwright flaky/quarantine tags against the shared quarantine registry. | - | - | - |
| `testing` | `local-integration-stack` | `active` | `polisyos-tools testing local-integration-stack` | Run the local runtime-dashboard integration stack and smoke profile. | - | - | - |
| `testing` | `mutation` | `active` | `polisyos-tools testing mutation` | Run canonical mutmut-based mutation suites for Foundry and Scientist. | - | - | - |
| `testing` | `report-test-economics` | `active` | `polisyos-tools testing report-test-economics` | Summarize slow suites and unstable tests from JUnit XML plus quarantine metadata. | - | - | - |
| `ci` | `check-action-freshness` | `active` | `polisyos-tools ci check-action-freshness` | Audit pinned third-party GitHub Actions against latest upstream releases. | - | - | - |
| `ci` | `check-foundry-domain-coverage` | `active` | `polisyos-tools ci check-foundry-domain-coverage` | Enforce Foundry coverage thresholds by domain instead of only globally. | - | - | - |
| `ci` | `check-phase7-ratchet` | `active` | `polisyos-tools ci check-phase7-ratchet` | Enforce the Phase 7 ratchet checklist for new subsystems and major surfaces. | - | - | - |
| `ci` | `check-workflow-policy` | `active` | `polisyos-tools ci check-workflow-policy` | Lightweight repo policy checks for GitHub Actions workflows. | - | - | - |

### `ops`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
|---|---|---|---|---|---|---|---|
| `cloud` | `build-priority-manifests` | `active` | `polisyos-tools cloud build-priority-manifests` | Build priority queue manifests for the Lex production pipeline. | - | - | - |
| `cloud` | `canonical-auto-approve` | `active` | `polisyos-tools cloud canonical-auto-approve` | Canonical variable auto-approval with preview and staged publish. | - | - | - |
| `cloud` | `check-progress` | `active` | `polisyos-tools cloud check-progress` | Inspect remote shard progress through the canonical shard helper surface. | - | - | - |
| `cloud` | `deploy-to-server` | `active` | `polisyos-tools cloud deploy-to-server` | Deploy one prepared shard bundle to a reviewed remote server workflow. | - | - | `cloud.prepare-shards`, `cloud.setup-server` |
| `cloud` | `gcp-preflight` | `active` | `polisyos-tools cloud gcp-preflight` | Validate a GCP worker without launching the Lex processing pipeline. | - | - | - |
| `cloud` | `merge-shards` | `active` | `polisyos-tools cloud merge-shards` | Merge pipeline output shards into a single unified graph snapshot. | - | - | `cloud.run-lex-from-manifest` |
| `cloud` | `prepare-shards` | `active` | `polisyos-tools cloud prepare-shards` | Prepare canonical shard assets under ``tools/cloud/deploy/assets``. | - | - | - |
| `cloud` | `run-datasets-validation` | `active` | `polisyos-tools cloud run-datasets-validation` | Run the canonical datasets validation cloud wrapper. | - | - | `cloud.run-pipeline` |
| `cloud` | `run-diagnostic` | `active` | `polisyos-tools cloud run-diagnostic` | Run the canonical diagnostic cloud pipeline wrapper. | - | - | `cloud.run-pipeline` |
| `cloud` | `run-lex-from-manifest` | `active` | `polisyos-tools cloud run-lex-from-manifest` | Run the Lex sharded pipeline from a pre-materialized JSONL.ZST shard manifest. | - | - | `cloud.gcp-preflight` |
| `cloud` | `run-pipeline` | `active` | `polisyos-tools cloud run-pipeline` | Run the canonical remote academic pipeline wrapper. | - | - | - |
| `cloud` | `run-remaining-stages` | `deprecated` | `polisyos-tools cloud run-remaining-stages` | Resume a reviewed snapshot through the canonical remaining-stages bridge. | cloud run-pipeline --resume --snapshot-root ... | - | `cloud.run-pipeline` |
| `cloud` | `setup-server` | `active` | `polisyos-tools cloud setup-server` | Run the canonical cloud host setup helper. | - | - | - |
| `release` | `build-release-notes` | `active` | `polisyos-tools release build-release-notes` | Render Keep-a-Changelog style release notes from structured TOML fragments. | - | - | - |
| `release` | `check-release-artifact-sizes` | `active` | `polisyos-tools release check-release-artifact-sizes` | Check release artifact sizes against repo-tracked thresholds. | - | - | - |
| `release` | `check-release-version` | `active` | `polisyos-tools release check-release-version` | Validate that a release tag matches packaged versions and fragment state. | - | - | - |
| `release` | `evaluate-vuln-report` | `active` | `polisyos-tools release evaluate-vuln-report` | Evaluate vulnerability reports against PolicyOS release policy exceptions. | - | - | - |
| `release` | `run-release-canary` | `active` | `polisyos-tools release run-release-canary` | Launch a live runtime canary from the installed release artifact and probe it. | - | - | - |
| `release` | `stage-release-snapshot` | `active` | `polisyos-tools release stage-release-snapshot` | Freeze unreleased fragments into an immutable versioned release snapshot. | - | - | `release.check-release-version`, `runtime.export-runtime-openapi` |
| `migrations` | `migrate` | `active` | `polisyos-tools migrations migrate` | Migrate schema artifacts to their declared target versions. | - | - | - |
| `migrations` | `migrate-duckdb-to-pg` | `active` | `polisyos-tools migrations migrate-duckdb-to-pg` | Migrate tenant-scoped data from DuckDB to PostgreSQL. | - | - | - |
| `runtime` | `archive-legacy-runs` | `active` | `polisyos-tools runtime archive-legacy-runs` | runtime/archive_legacy_runs | - | - | - |
| `runtime` | `backfill-decision-validity` | `active` | `polisyos-tools runtime backfill-decision-validity` | runtime/backfill_decision_validity | - | - | - |
| `runtime` | `check-runtime-api-contract` | `active` | `polisyos-tools runtime check-runtime-api-contract` | runtime/check_runtime_api_contract | - | - | - |
| `runtime` | `export-runtime-openapi` | `active` | `polisyos-tools runtime export-runtime-openapi` | runtime/export_runtime_openapi | - | - | - |
| `runtime` | `generate-runtime-client` | `active` | `polisyos-tools runtime generate-runtime-client` | runtime/generate_runtime_client | - | - | `runtime.export-runtime-openapi` |
| `runtime` | `inventory-legacy-runs` | `active` | `polisyos-tools runtime inventory-legacy-runs` | runtime/inventory_legacy_runs | - | - | - |
| `data` | `build-academic-gold-candidates` | `active` | `polisyos-tools data build-academic-gold-candidates` | Build seed candidate pools for manual academic gold annotation. | - | `./scripts/build_academic_gold_candidates.py` | - |
| `data` | `build-expert-review-bundle` | `active` | `polisyos-tools data build-expert-review-bundle` | Build a single expert-ready JSON bundle for screen and claim gold review. | - | `./scripts/build_expert_review_bundle.py` | - |
| `data` | `generate-wvs-registry` | `active` | `polisyos-tools data generate-wvs-registry` | Generate WVS indicator registry YAML from Excel codebook + CSV data. | - | `./scripts/generate_wvs_registry.py` | - |
| `data` | `record-fixtures` | `active` | `polisyos-tools data record-fixtures` | Record API response fixtures for connector integration tests. | - | `./scripts/record_fixtures.py` | - |
| `ukraine_data` | `build-edr-identity-seed-candidates` | `active` | `polisyos-tools ukraine_data build-edr-identity-seed-candidates` | ukraine_data/build_edr_identity_seed_candidates | - | - | - |
| `ukraine_data` | `build-p1-source-bindings` | `active` | `polisyos-tools ukraine_data build-p1-source-bindings` | Build pragmatic D1 source bindings from downloaded public raw layers. | - | - | - |
| `ukraine_data` | `build-spending-contracts-procurement-proxy` | `active` | `polisyos-tools ukraine_data build-spending-contracts-procurement-proxy` | Materialize the Spending contracts procurement proxy as a standalone source run. | - | - | - |
| `ukraine_data` | `fetch-p0-sources` | `active` | `polisyos-tools ukraine_data fetch-p0-sources` | Fetch and record official P0 source inputs for the Ukraine build stack. | - | - | - |
| `ukraine_data` | `fetch-p1-p2-public-sources` | `active` | `polisyos-tools ukraine_data fetch-p1-p2-public-sources` | Fetch and record public D1/D3 raw source inputs for the Ukraine build stack. | - | - | - |
| `ukraine_data` | `harvest-prozorro-contract-details` | `active` | `polisyos-tools ukraine_data harvest-prozorro-contract-details` | Resumable server-side harvest of detailed Prozorro contract records. | - | - | - |
| `ukraine_data` | `harvest-prozorro-contract-feed` | `active` | `polisyos-tools ukraine_data harvest-prozorro-contract-feed` | Resumable server-side harvest of the Prozorro public contracts feed. | - | - | - |
| `ukraine_data` | `harvest-spending-contracts-by-disposer` | `active` | `polisyos-tools ukraine_data harvest-spending-contracts-by-disposer` | Resumable server-side harvest for Spending contracts grouped by disposerId. | - | - | - |
| `ukraine_data` | `harvest-spending-daily` | `active` | `polisyos-tools ukraine_data harvest-spending-daily` | Resumable server-side backfill for Spending.gov.ua daily transactions. | - | - | - |
| `ukraine_data` | `pre-shard-lex-corpus` | `active` | `polisyos-tools ukraine_data pre-shard-lex-corpus` | Pre-materialize the ЄДРНПА corpus into per-pass shard JSONL.ZST manifests. | - | - | - |
| `calibration` | `compare-shards` | `active` | `polisyos-tools calibration compare-shards` | Compare calibration results across Lex shard hypotheses. | - | - | - |

### `research`

| Category | Command | Status | Canonical | Summary | Replacement | Aliases | Dependencies |
|---|---|---|---|---|---|---|---|
| `benchmarks` | `benchmark-lex-llm-steady-state` | `active` | `polisyos-tools benchmarks benchmark-lex-llm-steady-state` | Compatibility wrapper for the Lex steady-state benchmark entry point. | - | `./scripts/benchmark_lex_llm_steady_state.py` | - |
| `benchmarks` | `benchmark-lex-llm-sweep` | `active` | `polisyos-tools benchmarks benchmark-lex-llm-sweep` | Compatibility wrapper for the Lex sweep benchmark entry point. | - | `./scripts/benchmark_lex_llm_sweep.py` | - |
| `benchmarks` | `build-release-summary` | `active` | `polisyos-tools benchmarks build-release-summary` | Merge benchmark JSON artifacts into a contour-aware release summary. | - | - | - |
| `benchmarks` | `prepare-real-benchmark-data` | `active` | `polisyos-tools benchmarks prepare-real-benchmark-data` | Download a lightweight real-data benchmark pack for local execution. | - | - | - |
| `benchmarks` | `run-all` | `active` | `polisyos-tools benchmarks run-all` | Run the benchmark suite registry through the canonical tools surface. | - | - | - |
| `benchmarks` | `run-local-sota-profile` | `active` | `polisyos-tools benchmarks run-local-sota-profile` | Run the local SOTA benchmark profile through the zoned research tooling surface. | - | - | - |
| `benchmarks` | `run-parallel` | `active` | `polisyos-tools benchmarks run-parallel` | Parallel benchmark runner with worker and memory-aware scheduling. | - | - | - |
| `demos` | `run-export-demo` | `deprecated` | `polisyos-tools demos run-export-demo` | demos/run_export_demo | runtime export-runtime-openapi | - | - |
| `demos` | `run-foundry-ws9-frontier-demo` | `active` | `polisyos-tools demos run-foundry-ws9-frontier-demo` | demos/run_foundry_ws9_frontier_demo | - | - | - |
| `demos` | `run-laffer-demo` | `active` | `polisyos-tools demos run-laffer-demo` | demos/run_laffer_demo | - | - | - |
| `demos` | `run-mechanism-design` | `deprecated` | `polisyos-tools demos run-mechanism-design` | End-to-end demo: Mechanism Design через IR/Compiler/Foundry runtime + JAX grad. | benchmarks bench-domain | - | - |
| `demos` | `run-udf-hybrid-demo` | `quarantined` | `polisyos-tools demos run-udf-hybrid-demo` | demos/run_udf_hybrid_demo | diagnostics check-setup | - | - |
| `demos` | `run-udf-query-demo` | `quarantined` | `polisyos-tools demos run-udf-query-demo` | demos/run_udf_query_demo | diagnostics check-setup | - | - |

## Compatibility Wrappers

| Legacy Path | Canonical Command |
|---|---|
| `benchmarks/build_release_summary.py` | `polisyos-tools benchmarks build-release-summary` |
| `benchmarks/prepare_real_benchmark_data.py` | `polisyos-tools benchmarks prepare-real-benchmark-data` |
| `benchmarks/run_all_benchmarks.sh` | `polisyos-tools benchmarks run-all` |
| `benchmarks/run_local_sota_profile.sh` | `polisyos-tools benchmarks run-local-sota-profile` |
| `benchmarks/run_parallel.py` | `polisyos-tools benchmarks run-parallel` |
| `scripts/acceptance-audit` | `polisyos-tools workspace acceptance-audit` |
| `scripts/benchmark_lex_llm_steady_state.py` | `polisyos-tools benchmarks benchmark-lex-llm-steady-state` |
| `scripts/benchmark_lex_llm_sweep.py` | `polisyos-tools benchmarks benchmark-lex-llm-sweep` |
| `scripts/bootstrap` | `polisyos-tools workspace bootstrap` |
| `scripts/build_academic_gold_candidates.py` | `polisyos-tools data build-academic-gold-candidates` |
| `scripts/build_expert_review_bundle.py` | `polisyos-tools data build-expert-review-bundle` |
| `scripts/ci-parity` | `polisyos-tools workspace ci-parity` |
| `scripts/core-runtime-closeout` | `polisyos-tools workspace core-runtime-closeout` |
| `scripts/doctor` | `polisyos-tools workspace doctor` |
| `scripts/generate_stubs.py` | `polisyos-tools foundry generate-stubs` |
| `scripts/generate_wvs_registry.py` | `polisyos-tools data generate-wvs-registry` |
| `scripts/mutation_test.sh` | `polisyos-tools testing mutation --suite foundry --target <target>` |
| `scripts/mutation_test_scientist.sh` | `polisyos-tools testing mutation --suite scientist --target <target>` |
| `scripts/record_fixtures.py` | `polisyos-tools data record-fixtures` |
| `scripts/remote-acceptance` | `polisyos-tools workspace remote-acceptance` |
| `scripts/update_signature_baseline.py` | `polisyos-tools foundry update-signature-baseline` |
| `scripts/verify` | `polisyos-tools workspace verify` |

## Deprecated And Quarantined Commands

| Category | Command | Status | Replacement | Reason |
|---|---|---|---|---|
| `diagnostics` | `check-udf-perf` | `quarantined` | diagnostics check-setup | legacy UDF stack depends on modules that are not present in the current package |
| `cloud` | `run-remaining-stages` | `deprecated` | cloud run-pipeline --resume --snapshot-root ... | remaining-stage execution is now a compatibility bridge to the reviewed resume workflow |
| `demos` | `run-export-demo` | `deprecated` | runtime export-runtime-openapi | demo uses historical Foundry import paths and is retained only as reference material |
| `demos` | `run-mechanism-design` | `deprecated` | benchmarks bench-domain | manual research demo predates the current Foundry method registry |
| `demos` | `run-udf-hybrid-demo` | `quarantined` | diagnostics check-setup | legacy hybrid UDF demo depends on removed UDF/graph-store APIs |
| `demos` | `run-udf-query-demo` | `quarantined` | diagnostics check-setup | legacy UDF demo depends on the removed fabric.udf module family |

## Policy

- `tools/` is the only canonical executable surface.
- `scripts/` and root `benchmarks/*` executables are compatibility wrappers for one deprecation window.
- New tools must be added to the zone/category manifest before creating any new top-level `tools/<category>` package.
- `tools/benchmarks` is the executable surface; root `benchmarks/` is benchmark-domain support code.

## Dependency Graph

```mermaid
graph TD
  "cloud.gcp-preflight" --> "cloud.run-lex-from-manifest"
  "cloud.prepare-shards" --> "cloud.deploy-to-server"
  "cloud.run-lex-from-manifest" --> "cloud.merge-shards"
  "cloud.run-pipeline" --> "cloud.run-datasets-validation"
  "cloud.run-pipeline" --> "cloud.run-diagnostic"
  "cloud.run-pipeline" --> "cloud.run-remaining-stages"
  "cloud.setup-server" --> "cloud.deploy-to-server"
  "diagnostics.gen-schema" --> "diagnostics.abi-diff"
  "release.check-release-version" --> "release.stage-release-snapshot"
  "runtime.export-runtime-openapi" --> "release.stage-release-snapshot"
  "runtime.export-runtime-openapi" --> "runtime.generate-runtime-client"
  "workspace.doctor" --> "workspace.bootstrap"
  "workspace.doctor" --> "workspace.verify"
```

_Repo root: `/Users/deniskopylov/polisyos/policy-engine`_
