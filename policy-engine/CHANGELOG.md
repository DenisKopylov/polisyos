# Changelog

All notable changes to PolicyOS Policy Engine will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows [Semantic Versioning](https://semver.org/).

Backfill below was reconstructed from `git log` since January 1, 2026, with WIP and pure noise
commits filtered out.

## [Unreleased]

### Added

- Add top-level documentation entry points: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, and
  explanation pages for architecture, Trinity, and freeze policy.

- Add a tested Foundry quickstart helper so the root README can demonstrate a real compile ->
  execute flow.

### Changed

- Change packaging extras by adding umbrella `all` and MkDocs tooling to the `dev` extra.
- Change the `polisyos` CLI to expose `--version` for installation verification.

## [0.1.0] - 2026-04-03

### January 2026

#### Added

- Add the initial `policy-engine` scaffold with package metadata, install flow, base simulation
  modules, policy IR files, and core configuration.

- Add Policy Scientist orchestration, workflow state, queue and data staging, Fabric ingestion, and
  audit / run-record plumbing.

- Add the consolidated `src/polisyos/*` package structure across `common`, `fabric`, `foundry`,
  `ir`, `runtime`, and `scientist`.

- Add `core/*` and IR kernel foundations for artifacts, canonical JSON, contracts, registry,
  tracing, run context, and kernel constraints / metrics / units.

- Add the Foundry calibration package together with the first calibration tests.
- Add Foundry agent simulation modules, plugin wiring, and test coverage.
- Add the governance and legal stack: legal contracts, AST-backed policy evaluation, governance
  passes and profiles, decision card, run timeline, provenance, quality gates, NaN guard,
  conflict checker, and cost model.

- Add the Fabric catalog, connector discovery / pool / registry layers, transform pipeline,
  resilience layer, and connector test harness.

- Add observability and Scientist LLM tracing modules with tests.

#### Changed

- Change the repository layout to the consolidated `src/polisyos/*` boundaries and one-path
  architecture.

- Change calibration and import structure while splitting oversized type modules into smaller files.

#### Fixed

- Fix linting and formatting regressions across IR, Foundry, Scientist, and tests.

#### Removed

- Remove legacy code during the initial architecture cleanup and boundary refactor.

### February 2026

#### Added

- Add the Foundry methods registry, linker and type-checker, compiler and specialization pipeline,
  discovery method, and the wider causal / econometrics / distributional / HTE / backtesting /
  DOE / stress toolchain.

- Add the Trinity migration path with `docs/contracts/TRINITY.md`, `src/polisyos/ir/trinity/*`,
  loaders, migration reporting, and `migrate_to_trinity.py`.

- Add the IR norms and citations linker.
- Add the Fabric world layer: ABI contracts, world store, world materialization, Kuzu
  materialization, and docs pipeline.

- Add Lex and Scholar subsystems, NormPack assembly, and legal-evaluation APIs and contracts.
- Add Scientist engine features for checkpoint / resume, node idempotency, replay protocol, SLOs,
  and human-gate support.

- Add the security module with authz middleware, audit chain, and PII checks.
- Add Scientist agent RAG, code-verification, diversity, and orchestrator expansions.
- Add the runtime dashboard, generated runtime API client, control-plane routes and services, and
  runtime API hardening tests.

- Add new connector and data-plane surfaces including `ckan_*`, `opendatasoft`, `rest_json`,
  `socrata`, `sparql`, `sdmx_source`, source-profile registries, cursor store, replay store, and
  watermarks.

#### Changed

- Change the codebase structure by splitting oversized modules and reorganizing core, Fabric,
  Foundry, and Scientist internals.

- Change module and architecture docs to reflect Trinity, Lex, runtime, and frontend surfaces.

#### Removed

- Remove legacy modules and obsolete files during the core / Foundry / IR cleanup wave.

### March 2026

#### Added

- Add benchmark suites and scorecards across discovery, estimation, interference, transport,
  temporal, adversarial, reproducibility, and capability-wins scenarios.

- Add academic and datasets batch pipelines for harvesting, claim adjudication, graph building,
  normalization, publishing, QC, and source-registry flows.

- Add a major Foundry causal catalog expansion with transport, data fusion, actual causality,
  missing-data, superlearner, synthetic-control, forest-DR, and symbolic-identification tooling.

- Add Lex batch quality and structure processors including amendment detection, hallucination
  detection, entity and reference resolution, jurisdiction handling, and temporal parsing.

- Add Scientist search, autotune, backtesting, discovery, policy-design, provenance, and new
  causal built-in nodes.

#### Changed

- Change Fabric connectors and execution surfaces across `world_bank`, `eurostat`, `sdmx_source`,
  `wvs`, `who`, `unpd`, builtin profiles, bindings, and data-plane orchestration.

- Change core, IR, and runtime contracts together with analytics schema snapshots and broader
  `ir/analytics/*` coverage.

- Change CLI, benchmark harness, observability, and security plumbing to support the expanded
  Scientist and Foundry surface.
