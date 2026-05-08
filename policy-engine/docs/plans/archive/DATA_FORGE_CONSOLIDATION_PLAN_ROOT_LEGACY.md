# Data Forge: Unified Data Collection & Preprocessing Pipeline

**Status:** Plan  
**Date:** 2026-04-13  
**Scope:** Consolidate `academic`, `datasets`, `ukraine_data`, `batch_common`, `batch_snapshot`, `lex` (batch layer) into a single `polisyos.data_forge` package, and use that migration to clean up repository/file placement boundaries.

**Repository-wide split (2026-04-18):** this document remains the detailed
Data Forge consolidation record. The repository-wide SOTA contract now lives in
`docs/plans/active/REPOSITORY_SOTA_PLAN.md`; the focused active implementation
plan lives in `docs/plans/active/DATA_FORGE_CONSOLIDATION_PLAN.md`. Mandatory
architecture decisions are tracked in ADR-0111 through ADR-0120, and Phase 0
machine-readable contracts start in `architecture/topology.toml`,
`architecture/packages/boundaries.toml`,
`architecture/imports/contracts.toml`, and
`architecture/migration_shims.toml`.

**Status note (2026-05-02):** this historical plan has been superseded by the
active Data Forge plan. `polisyos.academic`, `polisyos.datasets`,
`polisyos.ukraine_data`, `polisyos.batch_common`, and
`polisyos.batch_snapshot` were physically removed in Phase 8; canonical code
ownership is now under `polisyos.data_forge`.

---

## 1. Problem Statement

Six directories currently handle offline data collection and preprocessing:

| Directory         | LOC   | Files | Domain                                                                                       |
| ----------------- | ----- | ----- | -------------------------------------------------------------------------------------------- |
| `academic/`       | ~23k  | 62    | Academic literature: OpenAlex harvest, fulltext resolution, LLM extraction, SKG graph        |
| `datasets/`       | ~19k  | 28    | Dataset catalog: 40+ source harvest, DCAT normalization, metric bindings, transportability   |
| `ukraine_data/`   | ~9k   | 9     | Country data: EDR/Prozorro/macro sources, agent/cell registries, network graphs, calibration |
| `lex/batch/`      | ~12k  | 45    | Legal corpus: XML/NPA parsing, provision anchoring, SPO extraction, knowledge graph          |
| `batch_common/`   | ~0.5k | 7     | Shared: manifests, hashing, paths, QC models, thermal throttling                             |
| `batch_snapshot/` | ~0.2k | 2     | Snapshot finalization: aggregates publish manifests                                          |

**Total: ~64k LOC, ~153 files** with substantial architectural overlap.

### 1.1 Observed Overlap

All six directories independently implement:

1. **Pipeline orchestration** -- ordered stages, resume/skip logic, stage manifests
2. **Config dataclass** -- stage selection, path properties, concurrency limits, API keys
3. **Harvest/fetch** -- async HTTP with rate limiting, retries, backoff, caching
4. **Normalize/parse** -- raw payload transformation into canonical models
5. **Merge/dedup** -- quality-ranked deduplication by composite keys
6. **Graph building** -- DuckDB schema DDL, table loading, index creation
7. **Embedding** -- sentence-transformers + HNSW index construction
8. **QC** -- threshold-based checks with critical/warning severity
9. **Benchmarking** -- deterministic test cases for search/retrieval quality
10. **Publish** -- manifest writing, consumer readiness, snapshot finalization
11. **LLM extraction** -- Gonka/OpenAI API calls with gating, batching, verification passes

### 1.2 Anti-Patterns to Eliminate

These are concrete issues found in the current codebase that MUST be fixed during consolidation, not carried forward.

#### 1.2.1 God Classes / God Files

| File                                    | LOC   | Problem                                                                                                                                                           | Action                                                                                                                                           |
| --------------------------------------- | ----- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `academic/batch/resolve_extract.py`     | 4,246 | Mixed concerns: fulltext fetching, LLM coordination, progress state machine, claim normalization, evidence bundling, metadata reconciliation, targeted extraction | Split into 5 modules: `fulltext_fetcher.py`, `extraction_coordinator.py`, `progress_tracker.py`, `claim_normalizer.py`, `targeted_extraction.py` |
| `academic/batch/article_extractor.py`   | 1,979 | 40+ normalization functions mixed with orchestration                                                                                                              | Extract `normalization_helpers.py` (~800 LOC)                                                                                                    |
| `datasets/batch/core_sources_ingest.py` | 7,862 | Combines ingestion, alignment, observation loading for 8+ sources                                                                                                 | Split per-source into `ingest/{worldbank,eurostat,oecd,ilo,who,...}.py` + shared `ingest/base.py` protocol                                       |
| `lex/batch/graph_builder.py`            | 3,542 | DDL, loading, entity resolution, amendment detection, trust tier all in one file                                                                                  | Split: `ddl.py` (schema), `loader.py` (bulk load), `entity_resolver.py`, `trust.py`                                                              |
| `lex/batch/pipeline.py`                 | 1,509 | `_process_spo_chunk()` contains ~70% of pipeline logic                                                                                                            | Split into `spo_orchestrator.py` with separate deterministic/llm/gap_fill/audit paths                                                            |

#### 1.2.2 Mutable Config State

**Current (academic/batch/pipeline.py:121):**

```python
config.extraction_lane = lane_name  # Mutation during multi-lane extraction
try:
    result = await run_resolve_extract(config)
finally:
    config.extraction_lane = original  # Fragile restoration
```

**Fix:** Use `dataclasses.replace()` everywhere:

```python
lane_config = replace(config, extraction_lane=lane_name)
result = await run_resolve_extract(lane_config)
```

**Rule:** All `BasePipelineConfig` subclasses MUST use `frozen=True`. Stage-specific overrides via `replace()` only.

#### 1.2.3 Duplicated Design Tier Mappings

Three independent copies of design tier dicts:

- `academic/trust.py:5-29`
- `academic/batch/resolve_extract.py:74-97`
- `academic/batch/graph_builder.py:37-58`

**Fix:** Single source of truth in `data_forge/academic/trust.py`.

#### 1.2.4 Missing DuckDB Transaction Boundaries

**Current (academic/batch/graph_builder.py `_flush_all()`):**

```python
con.executemany("INSERT INTO ac_works ...", work_batch)       # Success
con.executemany("INSERT INTO ac_estimates ...", est_batch)     # FAILS mid-batch
# -> Corrupted state: works inserted, estimates partially inserted
```

**Fix:** Explicit transaction boundaries in `DuckDBGraphBuilder` (see Section 4.5).

#### 1.2.5 Silent Failures

| Location                              | Problem                                               | Fix                                                                                      |
| ------------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------------------------------------- |
| `batch_common/manifest.py:65`         | Missing payload_path returns empty sha256 silently    | Raise `FileNotFoundError` or log warning with `findings`                                 |
| `batch_snapshot/cli.py:42`            | Recomputes SHA256 on-the-fly if missing from manifest | Raise `ManifestIntegrityError` -- hash must come from pipeline                           |
| `batch_snapshot/cli.py:64`            | Symlink OSError caught and ignored                    | Log error + set `symlink_created: false` in manifest                                     |
| `datasets/batch/harvester.py:520,598` | Bare `except Exception`                               | Catch `aiohttp.ClientError`, `asyncio.TimeoutError`, `json.JSONDecodeError` specifically |

#### 1.2.6 Hardcoded Pipelines & Dead Code

- `batch_snapshot/cli.py:27`: `pipelines = ("datasets", "academic", "lex")` -- hardcoded list -> use domain registry auto-discovery
- `batch_common/hashing.py:sha256_jsonl()` -- trivial wrapper over `sha256_file()` -> remove, callers use `sha256_file()` directly
- `batch_common/manifest.py` `filters` parameter in `write_raw_manifest()` -- unused across entire codebase -> remove dead parameter

#### 1.2.7 SQL Injection Risk in DuckDB

**Current (ukraine_data/adapters.py:393-435):**

```python
chunk_glob = str(chunk_dir / "*.parquet").replace("'", "''")
con.execute(f"... from read_parquet('{chunk_glob}')")  # Manual escaping -- fragile
```

**Fix:** Use parameterized queries:

```python
con.execute("SELECT * FROM read_parquet(?)", [str(chunk_dir / "*.parquet")])
```

### 1.3 Boundary with `fabric`

`fabric` is the **runtime data access layer**: it fetches from external APIs via connectors, materializes world state in CAS/DuckDB, and exposes query APIs. It operates at **request time**.

`data_forge` is the **offline batch preprocessing layer**: it harvests, extracts, transforms, and indexes large corpora into ready-to-consume artifacts. It operates at **build time**.

**Clear contract:** data_forge writes artifacts (DuckDB, HNSW, Parquet, JSONL, manifests) to `production_data/`. Downstream modules read them.

---

## 2. Target Architecture

### 2.1 Package Layout

```text
polisyos/data_forge/
|-- __init__.py                     # Public API facade (lazy imports)
|-- _version.py                     # Semantic version for artifact compatibility
|-- errors.py                       # Structured error hierarchy
|
|-- pipeline/                       # Generic pipeline framework
|   |-- __init__.py
|   |-- config.py                   # BasePipelineConfig (frozen dataclass)
|   |-- stage.py                    # Stage protocol, StageContract, StageResult, Finding
|   |-- orchestrator.py             # DAG executor: topo-sort, parallel, resume, circuit-breaker
|   |-- checkpoints.py              # Content-addressed skip detection (SHA256 + mtime hybrid)
|   |-- manifest.py                 # Unified manifest models (ArtifactRef, StageManifest, PublishManifest)
|   |-- lineage.py                  # W3C PROV-compatible lineage tracking
|   |-- scheduler.py                # Resource budget enforcement (memory, disk, time)
|   |-- registry.py                 # Domain pipeline auto-discovery registry
|   |-- telemetry.py                # Structured events, Prometheus, JSONL, OTLP export
|   |-- progress.py                 # Real-time progress tracking for long stages
|   |-- cli_common.py               # Shared CLI argument patterns
|   `-- secrets.py                  # SecretsConfig (env-only, never serialized)
|
|-- io/                             # Shared I/O layer
|   |-- __init__.py
|   |-- hashing.py                  # SHA256 file hashing
|   |-- paths.py                    # Snapshot directory layout helpers
|   |-- jsonl.py                    # Streaming JSONL read/write with Pydantic validation
|   |-- parquet.py                  # Parquet read/write/stats helpers
|   |-- duckdb_loader.py            # DuckDB schema migration, bulk load, transaction boundaries
|   `-- cas_bridge.py               # FileSystemCAS integration for artifact persistence
|
|-- harvest/                        # Generic async harvest framework
|   |-- __init__.py
|   |-- fetcher.py                  # Async HTTP: retries, backoff, circuit breaker, Retry-After
|   |-- rate_limiter.py             # Token-bucket rate limiter (replaces 3 implementations)
|   |-- adapter.py                  # SourceAdapter protocol (discover -> fetch -> normalize -> validate)
|   |-- cache.py                    # Fetch cache with TTL, fingerprint-based invalidation
|   `-- thermal.py                  # Thermal throttling profiles
|
|-- transform/                      # Shared transformation primitives
|   |-- __init__.py
|   |-- dedup.py                    # Quality-ranked deduplication (generic, configurable scorer)
|   |-- normalizer.py               # Base normalizer protocol + common helpers
|   |-- country_codes.py            # ISO country normalization
|   |-- canonical_variables.py      # Variable canonization
|   `-- interpolation.py            # Panel interpolation
|
|-- extraction/                     # LLM + deterministic extraction framework
|   |-- __init__.py
|   |-- llm_client.py               # Unified LLM client pool: multi-key rotation, adaptive rate
|   |-- llm_gate.py                 # Routing: deterministic/LLM/gap-fill/audit
|   |-- llm_cache.py                # Content-addressed SQLite response cache (WAL mode)
|   |-- prompt_registry.py          # Prompt template registry by domain
|   |-- deterministic.py            # Regex-based extraction protocol
|   |-- hallucination_detector.py   # Output sanity checks
|   `-- audit_sampler.py            # Stratified audit sampling for LLM QA
|
|-- index/                          # Embedding & vector index construction
|   |-- __init__.py
|   |-- embedder.py                 # EmbeddingPipeline: shard-based, streaming, memory-safe
|   |-- backends.py                 # SentenceTransformerBackend / OpenAIBatchBackend
|   |-- hnsw_builder.py             # HNSW index build from shards
|   `-- text_formatters.py          # Domain-specific text concatenation (Protocol)
|
|-- quality/                        # QC + benchmarking framework
|   |-- __init__.py
|   |-- qc.py                       # QCCheck/QCReport models (Severity enum, not strings)
|   |-- phase0.py                   # Pre-stage deterministic gates
|   |-- benchmark.py                # Generic benchmark runner protocol
|   |-- publish.py                  # Consumer readiness + publish manifest
|   `-- golden.py                   # Golden test framework (capture/verify byte-identical outputs)
|
|-- snapshot/                       # Multi-pipeline snapshot finalization
|   |-- __init__.py
|   `-- finalize.py                 # Auto-discovers pipelines from registry
|
|   # --- Domain pipelines (one sub-package per data domain) ---
|
|-- academic/                       # Academic literature pipeline
|   |-- __init__.py
|   |-- config.py                   # AcademicConfig(BasePipelineConfig)
|   |-- pipeline.py                 # Declarative stage DAG: topic_select -> ... -> publish
|   |-- cli.py
|   |-- openalex/                   # OpenAlex topic selection & work harvesting
|   |   |-- client.py
|   |   |-- selector.py
|   |   |-- topic_catalog.py
|   |   `-- priority_filter.py
|   |-- stages/                     # Pipeline stages (domain-specific logic only)
|   |   |-- harvester.py
|   |   |-- parser.py
|   |   |-- fulltext_fetcher.py     # (extracted from resolve_extract.py)
|   |   |-- extraction_coordinator.py
|   |   |-- claim_normalizer.py
|   |   |-- doc_normalize.py
|   |   |-- resolve_finalize.py
|   |   |-- numeric_extract.py
|   |   |-- claim_adjudicator.py
|   |   |-- conflict_resolve.py
|   |   |-- graph_builder.py        # SKG DDL + domain-specific data mapping
|   |   |-- edge_synthesize.py
|   |   |-- transport_score.py
|   |   |-- topic_select.py
|   |   `-- demand_harvest.py
|   |-- prompts/                    # LLM extraction prompts (domain-specific)
|   |-- trust.py                    # Single source of truth for design-tier scoring
|   `-- knowledge/                  # Read-side SKG query API
|       |-- types.py
|       |-- store.py
|       |-- search.py
|       |-- skg_query.py
|       |-- skg_store.py
|       |-- skg_versioning.py
|       |-- parameter_selector.py
|       |-- variable_canonizer.py
|       |-- canonical_resolver.py
|       |-- canonical_seed.py
|       `-- runtime_canonical_registry.py
|
|-- catalog/                        # Dataset catalog pipeline
|   |-- __init__.py
|   |-- config.py                   # CatalogConfig(BasePipelineConfig)
|   |-- pipeline.py                 # Declarative stage DAG
|   |-- cli.py
|   |-- source_registry.py          # YAML source definitions
|   |-- stages/
|   |   |-- harvester.py            # Async 40+ source fetch
|   |   |-- normalizer.py           # DCAT normalization + metric inference
|   |   |-- core_sources_ingest.py  # Split per-source with shared base protocol
|   |   `-- graph_builder.py        # ds_* DDL + metric bindings
|   |-- curation/
|   |   |-- ckan_curation.py
|   |   `-- metrics_map.py
|   `-- knowledge/                  # Read-side catalog query API
|       |-- types.py
|       |-- store.py
|       |-- search.py
|       |-- registry.py
|       |-- variable_alignment.py
|       |-- proxy_penalties.py
|       `-- proxy_resolver.py
|
|-- ukraine/                        # Ukraine Part B pipeline
|   |-- __init__.py
|   |-- config.py                   # UkraineConfig(BasePipelineConfig)
|   |-- pipeline.py                 # Stage DAG: D0_P0 -> D5
|   |-- cli.py
|   |-- server.py                   # Server bootstrap & Part A gate
|   |-- adapters.py                 # TabularSourceAdapter + AgentIdentityResolver
|   |-- stages/
|   |   `-- builders.py             # D0_P0 through D5 stage builders
|   |-- manifests.py                # Ukraine-specific manifest extensions
|   `-- resources.py                # Resource tracking + Prometheus
|
|-- legal/                          # Legal corpus batch pipeline
|   |-- __init__.py
|   |-- config.py                   # LegalConfig(BasePipelineConfig)
|   |-- pipeline.py                 # Declarative stage DAG
|   |-- cli.py
|   |-- stages/
|   |   |-- xml_parser.py
|   |   |-- structurer.py           # Provision anchoring
|   |   |-- spo_extractor.py        # LLM-based SPO extraction
|   |   |-- deterministic_spo/      # Regex SPO extraction
|   |   |-- reference_extractor.py
|   |   |-- domain_classifier.py
|   |   |-- graph_builder.py        # KG DDL + domain-specific loading
|   |   |-- entity_resolver.py
|   |   `-- embedder.py             # Domain-specific text formatting
|   |-- prompts/                    # SPO extraction prompts
|   |-- jurisdictions/              # UA/EU-specific patterns
|   |-- patterns/                   # Locale keyword patterns
|   |-- quality/                    # Hallucination, consistency, amendment detection
|   `-- spo_cache.py
|
|-- testing/                        # Shared test infrastructure
|   |-- __init__.py
|   |-- fixtures.py                 # Minimal corpora for unit/integration tests
|   `-- golden.py                   # Golden snapshot capture/verify CLI
|
`-- py.typed                        # PEP 561 marker
```

### 2.2 What Stays Outside data_forge

| Module                | Reason                                                                                                                                                                                                                |
| --------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `lex/` (non-batch)    | `lex.corpus`, `lex.normpack`, `lex.legal_evaluation`, legal impact/what-if analysis, and legal-to-IR intervention compilation stay as `polisyos.lex`; DTR execution and Scientist policy-search bridges split upward. |
| `fabric/`             | Runtime data access layer. Consumes what data_forge produces.                                                                                                                                                         |
| `academic/knowledge/` | Read-side API. Moves **into** `data_forge/academic/knowledge/` since it queries artifacts data_forge builds.                                                                                                          |
| `datasets/knowledge/` | Read-side API. Moves into `data_forge/catalog/knowledge/` for same reason.                                                                                                                                            |

### 2.3 Responsibility Boundary

```text
+-------------------------------------------------------------+
|                      BUILD TIME                              |
|                                                              |
|  data_forge/                                                 |
|  +---------+  +---------+  +---------+  +---------+         |
|  |academic |  | catalog |  | ukraine |  |  legal  |         |
|  |pipeline |  |pipeline |  |pipeline |  |pipeline |         |
|  +----+----+  +----+----+  +----+----+  +----+----+         |
|       |             |            |             |             |
|       v             v            v             v             |
|  +--------------------------------------------------+       |
|  |              production_data/                     |       |
|  |  DuckDB  Parquet  HNSW  JSONL  NPZ  Manifests   |       |
|  +--------------------------------------------------+       |
+-------------------------------------------------------------+
                           |
                           |  reads artifacts
                           v
+-------------------------------------------------------------+
|                      RUNTIME                                 |
|                                                              |
|  fabric/                    lex/               scientist/    |
|  +--------------+   +--------------+   +--------------+     |
|  | connectors   |   | normpack     |   | calibration  |     |
|  | world state  |   | evaluation   |   | governance   |     |
|  | query APIs   |   | simulator    |   | policy search|     |
|  +--------------+   +--------------+   +--------------+     |
+-------------------------------------------------------------+
```

**data_forge owns:** External data acquisition, text/document parsing, LLM & deterministic extraction, deduplication & canonicalization, graph/index building, quality assurance, artifact publishing, snapshot management.

**fabric owns:** Runtime connector registry, live data fetching, CAS-based persistence, world state materialization, query APIs, PII detection for live flows.

**lex (non-batch) owns:** NormPack assembly, legal evaluation, norm impact
analysis, and legal-to-IR intervention compilation. Foundry DTR execution and
Scientist policy search are consumed through upward bridges, not owned by Lex.

### 2.4 Repository and File Placement Target

This consolidation is also the cleanup boundary for the repository tree. The
goal is not only to move imports into `polisyos.data_forge`, but to remove
ambiguous top-level locations where scripts, generated artifacts, local data,
and product source currently mix.

#### 2.4.1 Product Root Boundary

`policy-engine/` remains the canonical product root. Repository root remains a
workspace gateway and repo control plane only.

```text
polisyos/
|-- .github/                    # Active GitHub control plane
|-- README.md                   # Workspace gateway
|-- SECURITY.md
|-- SUPPORT.md
|-- CODE_OF_CONDUCT.md
|-- lefthook.yml
|-- renovate.json
|-- design/                     # Design explorations, not product source
|-- data/                       # Local datasets, ignored by default
`-- policy-engine/              # Canonical product root

policy-engine/
|-- pyproject.toml
|-- uv.lock
|-- README.md
|-- CHANGELOG.md
|-- CONTRIBUTING.md
|-- mkdocs.yml
|-- architecture/               # Import policy, public surface, generated artifact registry
|-- src/polisyos/               # Product Python packages
|-- tests/                      # Mirrors package topology
|-- docs/                       # Canonical product documentation
|-- schemas/                    # Committed ABI/API snapshots
|-- frontend/                   # Dashboard, generated API client, shells
|-- tools/                      # Maintained automation and devx commands
|-- benchmarks/                 # Benchmark source, not ad-hoc outputs
|-- ops/                        # Deployment, cloud, runtime operations
|-- examples/
`-- release-fragments/
```

#### 2.4.2 Data Forge Source Placement

All maintained offline acquisition and preprocessing code moves under:

```text
policy-engine/src/polisyos/data_forge/
```

Domain-specific batch code belongs under one of:

| Domain              | Target package                 | Old source              |
| ------------------- | ------------------------------ | ----------------------- |
| Academic literature | `polisyos.data_forge.academic` | `polisyos.academic`     |
| Dataset catalog     | `polisyos.data_forge.catalog`  | `polisyos.datasets`     |
| Ukraine data        | `polisyos.data_forge.ukraine`  | `polisyos.ukraine_data` |
| Legal batch corpus  | `polisyos.data_forge.legal`    | `polisyos.lex.batch`    |

Shared batch infrastructure belongs in `data_forge/pipeline`,
`data_forge/io`, `data_forge/harvest`, `data_forge/transform`,
`data_forge/extraction`, `data_forge/index`, `data_forge/quality`, and
`data_forge/snapshot`. New shared code must not be added to the old
`batch_common` or domain batch packages after Phase 0 starts.

#### 2.4.3 Artifact and Local Data Placement

The source tree should distinguish committed source of truth from local or
generated state:

| Kind                                      | Target location                                                     | Commit policy                                                    |
| ----------------------------------------- | ------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Small committed schemas and ABI snapshots | `policy-engine/schemas/`                                            | Committed, registered in `architecture/generated_artifacts.toml` |
| Curated tiny test fixtures                | `policy-engine/tests/**/fixtures/`                                  | Committed when deterministic and reviewable                      |
| Golden migration snapshots                | `policy-engine/tests/unit/data_forge/golden/` or external artifact store | Committed only when small; otherwise referenced by manifest      |
| Local full datasets                       | repository root `data/` or external object storage                  | Ignored                                                          |
| Production-scale generated bundles        | `policy-engine/production_data/` or external object storage         | Ignored by default                                               |
| Runtime state, audit bundles, local CAS   | `policy-engine/.polisyos/`                                          | Ignored                                                          |
| Build outputs                             | `policy-engine/site/`, `policy-engine/dist/`, `frontend/**/dist/`   | Ignored                                                          |
| Run scratch                               | `policy-engine/.tmp/`, `policy-engine/tmp/`, root `tmp/`            | Ignored                                                          |
| Reports worth keeping                     | `policy-engine/docs/archive/reports/`                               | Committed only when curated                                      |

Rule: if a generated artifact is committed, it needs a source of truth,
regeneration command, freshness rule, and owner in
`architecture/generated_artifacts.toml`.

#### 2.4.4 Deployment and Operations Placement

Deployment and operations files should converge under `policy-engine/ops/`.
Current overlapping locations such as `cloud_deploy/`, `deploy/`, `docker/`,
and `gcp/` should either move under `ops/` or become thin compatibility
wrappers during the migration.

Target:

```text
policy-engine/ops/
|-- ci/
|-- cloud/
|   |-- gcp/
|   `-- deploy/
|-- docker/
|-- runtime/
|-- release/
`-- data/
```

Repository root `.github/` remains the active workflow location. Nested
`policy-engine/.github/` files must either move to root `.github/` or be
renamed into explicit templates under `policy-engine/ops/ci/templates/`.

#### 2.4.5 Data Roots and Artifact Lake Model

Raw, input, output, benchmark, baseline, and temporary data need their own
topology. The product source tree should not be the data lake.

Current data-heavy roots:

| Path                               | Current role                                                                                             | Target role                                                                                                                     |
| ---------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| repository root `data/`            | Large local data lake: academic archives, fulltext caches, legal corpus, Ukraine server support          | Keep as ignored local/external data lake; organize by layer/domain/snapshot                                                     |
| `policy-engine/data/`              | Mixed small tracked gold scaffolding plus ignored raw WVS data, local DuckDB/Kuzu DBs, curated manifests | Reduce to small committed fixtures, contracts, source registries, and README/manifests only                                     |
| `policy-engine/production_data/`   | Ignored release/publish bundles and promoted runtime artifacts                                           | Local release cache only; canonical release identity is a manifest with hashes and logical artifact URIs                        |
| `policy-engine/benchmark-results/` | Ignored benchmark outputs and visual reports                                                             | Move transient output to `.polisyos/benchmarks/`; commit only curated baselines/reports through the generated-artifact registry |
| `policy-engine/baseline/`          | Small tracked architecture freeze baselines                                                              | Keep small and committed, or move to `architecture/baselines/` with compatibility docs                                          |
| `policy-engine/tmp/`               | Ignored local probes and manual integration logs                                                         | Move to `.tmp/` or `.polisyos/tmp/`; no source of truth                                                                         |
| repository root `tmp/`             | Large local scratch: GCP bundles, legal history probes, priority manifests                               | Ignored local scratch only; cleanup/TTL managed outside product automation                                                      |

Target data lake shape for ignored local data:

```text
data/
|-- raw/                         # Immutable source downloads, by domain/source/snapshot
|   |-- academic/openalex/<snapshot_id>/
|   |-- legal/edrnpa/<snapshot_id>/
|   |-- catalog/wvs/<snapshot_id>/
|   `-- ukraine/<source>/<snapshot_id>/
|-- cache/                       # Rebuildable caches: fulltext, LLM, HTTP, embeddings
|-- work/                        # Intermediate pipeline working directories
|-- snapshots/                   # Reproducible build-time snapshots
|-- releases/                    # Local copies of promoted runtime bundles
|-- archives/                    # Cold evidence/provenance archives
`-- manifests/                   # Small local index of snapshots/releases
```

Target product-root data shape:

```text
policy-engine/data/
|-- README.md
|-- fixtures/                    # Tiny deterministic fixtures only
|-- gold/                        # Small human-curated gold sets
|-- contracts/                   # Data contracts, schema seeds, source registry fragments
`-- manifests/                   # Small committed manifest templates or sample manifests
```

Rules:

1. Raw/source downloads are immutable and ignored by Git.
2. Working outputs are disposable and live under `data/work/`, `.tmp/`, or
   `.polisyos/runs/`.
3. Published runtime bundles are addressed by `(domain, snapshot_id, manifest
sha256)`, not by a machine-local path.
4. Committed manifests must avoid machine-specific absolute paths as the only
   artifact reference. Use logical URIs plus optional local cache paths.
5. Large benchmark outputs are not committed. A curated benchmark report or
   baseline must be registered in `architecture/generated_artifacts.toml`.
6. `policy-engine/data/README.md` must describe the actual target layout. The
   current Raw -> Staging -> Curated prose should be reconciled with Data Forge
   snapshot/release semantics.
7. `policy-engine/data/databases/` is local test/demo state, not committed
   source. Prefer deterministic fixture generation over storing DuckDB/Kuzu
   databases in the product root.

#### 2.4.6 SOTA Topology Controls

The final tree should be enforced by small machine-checkable contracts, not by
memory.

| Control                     | Target                                               | Purpose                                                                                                          |
| --------------------------- | ---------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Topology registry           | `architecture/topology.toml`                         | Lists allowed top-level directories, owner, path type, commit policy, and sunset date for temporary paths        |
| Import policy               | `import_policy.toml`                                 | Adds `data_forge` as a first-class root and removes old batch roots after compatibility shims expire             |
| Generated artifact registry | `architecture/generated_artifacts.toml`              | Registers every committed generated family, including Data Forge schemas, fixture captures, and golden baselines |
| Ownership map               | `.github/CODEOWNERS` + `docs/reference/ownership.md` | Adds `src/polisyos/data_forge/**`, Data Forge docs, and Data Forge tools to an explicit owner group              |
| Explorer hygiene            | `.vscode/settings.json`                              | Hides generated and local state from normal development views without hiding source-of-truth files               |
| Topology gate               | `tools/architecture/guardrails.py`                   | Fails when product source appears in repository root or unknown top-level paths are added                        |

The topology registry should use path categories rather than ad-hoc prose:

```text
source | docs | test_fixture | golden_fixture | generated_committed |
local_data | runtime_state | build_output | cache | scratch | wrapper
```

Every category has a default commit policy:

| Category                                                          | Default policy                                                       |
| ----------------------------------------------------------------- | -------------------------------------------------------------------- |
| `source`, `docs`, `test_fixture`                                  | Committed                                                            |
| `golden_fixture`                                                  | Committed only when small and deterministic; otherwise manifest-only |
| `generated_committed`                                             | Committed only through `architecture/generated_artifacts.toml`       |
| `local_data`, `runtime_state`, `build_output`, `cache`, `scratch` | Ignored                                                              |
| `wrapper`                                                         | Temporary; must have a target path and sunset phase                  |

#### 2.4.7 Fixtures, Testdata, and Golden Baselines

Fixtures are source only when they are small, deterministic, and reviewable.
Large or live-captured data belongs outside the source tree with a manifest.

| Kind                                  | Target                                                              |
| ------------------------------------- | ------------------------------------------------------------------- |
| Cross-cutting unit fixtures           | `tests/fixtures/`                                                   |
| Domain fixtures                       | `tests/<domain>/fixtures/`                                          |
| Data Forge migration goldens          | `tests/unit/data_forge/golden/` or external artifact store + manifest    |
| Benchmark fixtures                    | `benchmarks/<suite>/fixtures/`                                      |
| Recorded live connector fixtures      | `tests/unit/fabric/connectors/sources/fixtures/`                         |
| Full datasets or production snapshots | root `data/`, `production_data/`, or object storage, ignored by Git |

No new `testdata/`, `sample_data/`, or one-off fixture directories should be
added without registering them in the topology inventory.

#### 2.4.8 Tools and Scripts Policy

`tools/` is the maintained automation package. `scripts/` should become
wrapper-only or disappear.

| Rule                         | Target                                                                            |
| ---------------------------- | --------------------------------------------------------------------------------- |
| Maintained Python automation | `tools/<area>/...` and exposed through `tools/cli.py` when user-facing            |
| Legacy executable wrappers   | `scripts/<command>` thinly delegates to `python -m tools.cli ...`                 |
| Deprecated tools             | `tools/archive/` with removal phase and replacement path                      |
| Cloud/ops tools              | Prefer `tools/ops/...`; avoid parallel `tools/ops/cloud` and `tools/ops/cloud` growth |
| Data Forge tools             | `tools/ops/data_forge/` or `tools/ops/data/` only if not part of the package runtime      |

The cleanup phase should eliminate duplicate homes such as `tools/ops/cloud` vs
`tools/ops/cloud`, `tools/ops/data` vs domain-specific Data Forge CLIs, and
`scripts/*.py` copies of maintained tools.

#### 2.4.9 Documentation Lifecycle

Active migration plans can live in `docs/` only when explicitly unignored and
owned. Once accepted, each plan should leave behind:

1. An ADR for irreversible architecture decisions.
2. Reference documentation for stable commands, layouts, and policies.
3. Runbooks for operational procedures.
4. The original plan moved to `docs/plans/archive/`.

This prevents long-lived root docs from becoming a second, stale source of
truth beside `docs/reference/**`.

#### 2.4.10 Loose Top-Level File Disposition

Loose files at repository root and product root require stricter rules than
directories: every new file must either be a recognized tool sentinel or have a
documented home under `docs/`, `tools/`, `architecture/`, `ops/`, `tests/`, or
an ignored artifact directory.

Repository root disposition:

| File(s)                                                                                                                      | Target disposition                                                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.gitignore`, `README.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `SUPPORT.md`, `lefthook.yml`, `renovate.json`                | Keep at repository root as workspace gateway / repo control plane                                                                                                                       |
| `filter_topics.py`, `organize_relevant_topics.py`                                                                            | Move maintained logic to `policy-engine/tools/research/topics/`; remove or wrap old root paths                                                                                          |
| `topics.csv`                                                                                                                 | Move to root `data/topics/` if local, or to a registered fixture/curated data path if canonical                                                                                         |
| `compileall.txt`, `import_gate.txt`, `ruff_stats.txt`, `stale_sources_missing_paths.txt`, `summary.json`, `test_collect.txt` | Treat as local freeze outputs; keep curated baselines in `policy-engine/baseline/` or curated reports in `docs/archive/reports/`; otherwise write to `.polisyos/reports/`               |
| `scm-implementation-spec-v3.md`                                                                                              | If canonical product spec, move to `policy-engine/docs/contracts/` or `docs/plans/archive/` and update diagnostics; if external/private input, keep ignored and document as local input |
| `.DS_Store`                                                                                                                  | Delete locally; ignored                                                                                                                                                                 |

`policy-engine/` product-root disposition:

| File(s)                                                                                                                                                                         | Target disposition                                                                                                                                                 |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `pyproject.toml`, `uv.lock`, `mkdocs.yml`, `.gitignore`, `.env.example`, `.nvmrc`, `.python-version`, `.pre-commit-config.yaml` | Keep: standard product-root sentinels and tool-discovered config                                                                                                   |
| `Dockerfile.reproducible`                                                                                                                                                       | Keep only if product-root Docker discovery needs it; otherwise move to `ops/docker/Dockerfile.reproducible` with documented build command                          |
| `import_policy.toml`, `import_exceptions.toml`                                                                                                                                  | Keep during migration because import tooling defaults resolve from product root; long-term target is `architecture/` if CLI defaults and docs are updated together |
| `import_exceptions_registry.md`                                                                                                                                                 | Move to `architecture/import_exceptions_registry.md` or `docs/reference/import-exceptions.md`; keep root compatibility only during transition                      |
| `freeze_policy.md`                                                                                                                                                              | Move to `docs/explanation/freeze-policy.md` or `docs/reference/quality-gates.md`; remove root duplicate                                                            |
| `env_example.txt`                                                                                                                                                               | Remove after confirming `.env.example` is the canonical example                                                                                                    |
| `install.sh`                                                                                                                                                                    | Convert to thin wrapper or remove in favor of `python3 -m tools.cli workspace bootstrap` documented in README                                                      |
| `migrate.py`                                                                                                                                                                    | Move to `tools/migrations/` or keep as wrapper to `polisyos-tools` only                                                                                            |
| `jax_bootstrap.py`                                                                                                                                                              | Move to `tools/lib/` or `tools/research/benchmarks/jax/`; update imports that currently rely on product-root importability                                        |
| `all_1000_policy_topics.csv`                                                                                                                                                    | Move to ignored local data, curated fixture, or registered Data Forge input manifest depending on whether it is source-of-truth                                    |
| `audit_*.polisyos-audit.tar.gz`                                                                                                                                                 | Move to `.polisyos/audits/`; keep curated evidence in `docs/archive/reports/` only                                                                                 |
| `.env`                                                                                                                                                                          | Keep local and ignored; never commit                                                                                                                               |
| `.DS_Store`, `=2.5.0`                                                                                                                                                           | Delete locally; ignored                                                                                                                                            |

Topology gate rule: after Phase -1, adding a new loose top-level file requires
one of:

1. It is on the explicit sentinel allowlist.
2. It is registered in `architecture/topology.toml`.
3. It is ignored as local state, cache, scratch, local data, or build output.
4. It is a temporary wrapper with a target path and sunset phase.

### 2.5 Source Package Topology Target

The directory cleanup must also fix package boundaries inside
`policy-engine/src/polisyos`. Moving files without enforcing import direction
would leave the tree tidy but architecturally ambiguous.

Current factual import graph highlights:

| Source package | Current cross-package smell                                                                                       | Target correction                                                                                                                  |
| -------------- | ----------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `ir`           | Imports `foundry`, `scientist`, and `datasets` from analytics/observation modules                                 | `ir` must contain contracts, schemas, pure transforms, and artifact codecs only; execution adapters move upward                    |
| `core`         | `core/components/_cli_scientist.py` imports Scientist modules                                                     | Scientist CLI glue belongs in `tools/` or `scientist`, not in platform core                                                        |
| `fabric`       | `fabric/retrieval/service.py` imports `datasets.batch.source_registry`                                            | Runtime source-registry contracts move to `fabric.catalog` or `core.contracts`; Data Forge only generates/updates registry content |
| `foundry`      | Imports `scientist`, `lex`, `academic`, and `ukraine_data` in a few modules                                       | Foundry must be a domain-neutral compute layer; domain bridges live in Scientist, packs, ops, or Data Forge                        |
| `lex`          | `lex/interventions.py` imports Foundry DTR and Scientist search; `lex/batch/benchmark.py` imports Scientist tools | Lex emits legal/IR contracts; Foundry executes methods; Scientist searches/plans                                                   |
| `runtime`      | HTTP control service imports `lex.batch` and low-level Foundry/Scientist internals                                | Runtime should call service facades only; no direct batch internals after Data Forge extraction                                    |
| `ukraine_data` | Builders import Lex, Foundry, and Scientist while also acting as a data pipeline                                  | Build-time assembly moves to `data_forge.ukraine`; reusable runtime/domain pieces move to `packs/ukraine` or service facades       |

#### 2.5.1 Layered Ownership Model

Target dependency direction:

```text
common
  -> ir
  -> core
  -> fabric / data_forge / lex / foundry / scholar
  -> scientist
  -> runtime
  -> ops / tools / packs
```

This is a dependency guideline, not a forced directory nesting. The important
property is that lower layers do not import orchestration, domain packs, batch
pipelines, or runtime delivery code.

| Package      | Owns                                                                                                     | May depend on                                               | Must not depend on                                                                 |
| ------------ | -------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `common`     | Small generic helpers with no PolicyOS semantics                                                         | stdlib and tiny external utilities                          | any `polisyos.*` package                                                           |
| `ir`         | Stable contracts, ABI models, schemas, references, pure validation, portable artifact codecs             | `common` only, plus explicitly approved pure dependencies   | `core`, `fabric`, `foundry`, `scientist`, `runtime`, `data_forge`, domain packages |
| `core`       | Platform primitives: artifacts, canon, contracts, governance passes, observability, security, registries | `common`, `ir`                                              | `fabric`, `foundry`, `scientist`, `runtime`, domain pipelines                      |
| `fabric`     | Runtime data access, connector protocols, retrieval, document/claim/world materialization, live storage  | `common`, `ir`, `core`                                      | batch pipelines, `scientist`, `lex` domain logic, `foundry` execution              |
| `data_forge` | Offline acquisition, preprocessing, extraction, indexing, snapshot/release publishing                    | `common`, `ir`, `core`, selected Fabric connector protocols | runtime services, Scientist planning, Foundry execution internals                  |
| `lex`        | Legal domain contracts, corpus runtime APIs, NormPack assembly, legal evaluation, norm impact analysis   | `common`, `ir`, `core`, Fabric read/materialization APIs    | Foundry methods, Scientist search/orchestration, Data Forge batch internals        |
| `foundry`    | Compile/execute, numerical methods, simulations, calibration, uncertainty, method catalog                | `common`, `ir`, `core`, narrow Fabric data-plane contracts  | `scientist`, `lex`, `academic`, `datasets`, `ukraine_data`, domain packs           |
| `scholar`    | Research-intent enrichment and knowledge-bundle service facade                                           | `common`, `ir`, `core`, `fabric`                            | Foundry execution, Data Forge batch internals except optional artifact readers     |
| `scientist`  | Agents, search, governance orchestration, policy design, replay/backtesting, cross-domain bridges        | lower layers and stable public facades                      | HTTP/runtime delivery details                                                      |
| `runtime`    | API/HTTP delivery and adapter wiring                                                                     | public service facades from lower layers                    | direct batch modules, generated artifact internals, private module paths           |
| `packs`      | Domain packs, examples, policy families, domain-specific adapters                                        | public facades only                                         | private internals of core packages; wildcard imports should be temporary           |

#### 2.5.2 Placement Heuristics

Use the dominant reason a module exists:

| If code primarily...                                                                           | Home                     |
| ---------------------------------------------------------------------------------------------- | ------------------------ |
| Defines portable schemas, references, IDs, or serialization contracts                          | `ir` or `core.contracts` |
| Fetches, parses, deduplicates, indexes, or publishes offline source data                       | `data_forge/<domain>`    |
| Resolves live data needs or materializes runtime evidence/world state                          | `fabric`                 |
| Represents legal norms, validates legal compliance, or computes legal impact                   | `lex`                    |
| Executes numerical methods, simulations, DTR/causal estimators, calibration, or ABM/RL runtime | `foundry`                |
| Chooses policies, searches candidates, coordinates agents, applies governance workflows        | `scientist`              |
| Serves HTTP/API requests or translates transport-layer payloads                                | `runtime`                |
| Is a command, audit, migration, cleanup, or release procedure                                  | `tools/` or `ops/`       |

If one file does more than one of these, split it. Do not pick the "least bad"
single home for a mixed module.

#### 2.5.3 Concrete Source Relocation Decisions

| Current path                                                        | Decision                                                                                                                                         | Rationale                                                                                                                                              |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `polisyos.lex.simulator`                                            | Keep under Lex, but rename/reframe to `lex.impact` or move the analyzer into `lex.legal_evaluation.impact` after compatibility shims exist       | It runs legal/safety governance over old/new `NormPack` objects and publishes legal impact reports; it is not a general Foundry runtime                |
| `polisyos.lex.simulator.diff` and `mutator`                         | Keep Lex/IR-adjacent, possibly under `lex.normpack.whatif`                                                                                       | Pure NormPack diff/mutation belongs close to NormPack semantics                                                                                        |
| `polisyos.lex.interventions`                                        | Split into three homes                                                                                                                           | Legal-to-IR directive/compiler stays in Lex; DTR execution moves to Foundry or Scientist bridge; hierarchical policy search adapter moves to Scientist |
| `polisyos.lex.batch`                                                | Move to `data_forge.legal`                                                                                                                       | It is offline corpus/SPO/KG generation, not runtime Lex                                                                                                |
| `polisyos.lex.batch.benchmark`                                      | Move with legal Data Forge benchmarks or `benchmarks/legal/`                                                                                     | A benchmark must not make Lex depend on Scientist                                                                                                      |
| `polisyos.foundry.release_acceptance`                               | Move to `ops/release` or `data_forge.ukraine.release_acceptance` with a compatibility shim                                                       | It imports Ukraine manifests and Scientist postflight checks, so it is a release procedure, not Foundry core                                           |
| `polisyos.foundry.agent_sim.wiring.contracts`                       | Replace direct `CompiledLexIntervention` import with neutral IR/core intervention payloads; place Lex-to-agent-sim adapter in Scientist or packs | Foundry should consume executable/vectorized contracts, not legal-domain compiler classes                                                              |
| `polisyos.foundry.methods.catalog.causal.literature_prior`          | Route through Scholar or a dependency-light knowledge artifact facade                                                                            | Foundry methods should not import `academic` pipeline code                                                                                             |
| `polisyos.foundry.methods.catalog.causal.composition_failure_cards` | Move `TypedFailureCard`/`FailureSeverity` contracts downward to `ir.analytics` or `core.contracts`                                               | Foundry can emit typed failure data without importing Scientist search internals                                                                       |
| `polisyos.foundry.methods.catalog.policy.frontier`                  | Move embedding/search orchestration to Scientist, or inject embedder protocol into Foundry                                                       | Foundry method catalog should not depend on Scientist agent embedders                                                                                  |
| `polisyos.foundry.calibration.calibrator` lazy Scientist import     | Replace with callback/protocol or move meta-override application to Scientist orchestration                                                      | Calibration engine can expose hooks; Scientist owns policy for using them                                                                              |
| `polisyos.ir.analytics.strategic`                                   | Move `ComputeBudget` to core/IR contract and move Foundry-specific bundle construction upward                                                    | IR should not import Scientist or Foundry execution builders                                                                                           |
| `polisyos.ir.analytics.transportability`                            | Move dataset proxy contracts into IR/core or Data Forge artifact contracts; replace `to_source_domain()` with neutral payload export             | IR cannot construct Foundry classes directly                                                                                                           |
| `polisyos.ir.analytics.alignment_certification`                     | Keep certificate models in IR; move proxy-resolution and ontology-warning service code upward                                                    | IR should not import Data Forge/Dataset knowledge or Scientist compiler services                                                                       |
| `polisyos.fabric.retrieval.service` source registry import          | Move registry contract/read API to `fabric.catalog` or `core.contracts`; Data Forge writes the registry                                          | Runtime Fabric can read registry content without importing batch code                                                                                  |
| `polisyos.core.components._cli_scientist`                           | Move to `tools/scientist/` or `scientist/cli.py`                                                                                                 | Core should not contain Scientist CLI adapters                                                                                                         |
| `polisyos.ukraine_data.builders`                                    | Split into `data_forge.ukraine` build pipeline plus optional `packs/ukraine` runtime/domain package                                              | Current file mixes data assembly, Foundry bundle prep, Lex interventions, and Scientist governance                                                     |
| `polisyos.runtime.http.services.control` batch calls                | Replace direct `lex.batch` calls with Data Forge job/service facade                                                                              | Runtime can trigger jobs, but should not import batch internals                                                                                        |

#### 2.5.4 Data Forge vs Runtime Read Facades

Data Forge owns production of artifacts. It should not become a grab bag that
runtime packages import for heavy batch dependencies.

Rule:

1. Pipeline/build modules live under `data_forge/**` and are not imported by
   `fabric`, `foundry`, `lex`, `scientist`, or `runtime`.
2. Dependency-light artifact readers and schemas can live in `core.contracts`,
   `ir`, `fabric.catalog`, `scholar`, or an explicitly documented
   `data_forge.<domain>.read_api` facade if it has no batch/runtime side
   effects.
3. When a runtime package needs a dataset/source registry, it consumes a stable
   contract and local/external artifact reference. Data Forge is only the
   producer.

This avoids a common monorepo failure mode where "offline pipeline" packages
become mandatory runtime imports.

#### 2.5.5 Import Policy Target

`import_policy.toml` should evolve from today's permissive migration state to
explicit anti-edges:

| Package   | Final rule                                                                                                                       |
| --------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `ir`      | no imports from `core`, `fabric`, `foundry`, `scientist`, `runtime`, `data_forge`, `academic`, `datasets`, `ukraine_data`, `lex` |
| `core`    | no imports from `fabric`, `foundry`, `scientist`, `runtime`, `data_forge`, or domain packages                                    |
| `fabric`  | no imports from batch domains; only stable registry/contracts/read APIs                                                          |
| `foundry` | no imports from `scientist`, `lex`, `academic`, `datasets`, `ukraine_data`, `data_forge`, `runtime`                              |
| `lex`     | no imports from `foundry`, `scientist`, `runtime`, or Data Forge pipeline modules                                                |
| `runtime` | imports only public facades; no `*.batch.*`, no private `_` modules except compatibility windows                                 |
| `packs`   | replace current wildcard allowance with package-specific public-facade imports                                                   |

Temporary exceptions must live in `import_exceptions.toml` with owner, reason,
target path, and sunset phase.

### 2.6 Directory-by-Directory Work Register

This register captures concrete cleanup work found in the current tree. It is
the backlog for making the repository layout match Sections 2.4 and 2.5.

#### 2.6.1 Source Packages

| Area                                            | Finding                                                                                                                                      | Target work                                                                                                             |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `src/polisyos/academic`                         | Mostly build-time literature pipeline; several large batch modules, including `batch/resolve_extract.py` at ~4.2k LOC                        | Move to `data_forge.academic`; split resolve/extract/graph/index/publish concerns before or during the move             |
| `src/polisyos/datasets`                         | Build-time dataset catalog; `batch/core_sources_ingest.py` is ~7.9k LOC and mixes source registry, fetch, normalize, publish                 | Move to `data_forge.catalog`; split per-source adapters, registry contracts, normalization, and publishing              |
| `src/polisyos/lex/batch`                        | Offline legal corpus/SPO/KG pipeline; `graph_builder.py`, `pipeline.py`, `structurer.py`, `spo_extractor.py` are large orchestration modules | Move to `data_forge.legal`; keep only dependency-light runtime read facades for Lex/Fabric                              |
| `src/polisyos/lex/interventions.py`             | One file spans legal directive compilation, DTR execution, strategic-response registry, and Scientist search bridge                          | Split into Lex compiler, Foundry/Scientist DTR bridge, and Scientist policy-search adapter                              |
| `src/polisyos/lex/simulator`                    | Name suggests generic simulation, but code is legal NormPack what-if and governance impact analysis                                          | Rename/reframe to `lex.impact` or `lex.legal_evaluation.impact`; keep compatibility shim                                |
| `src/polisyos/ukraine_data`                     | No package README; `builders.py` is ~5k LOC and mixes build-time data assembly with Lex, Foundry, and Scientist governance                   | Move build pipeline to `data_forge.ukraine`; move runtime/domain adapters to `packs/ukraine` if they are not build-only |
| `src/polisyos/foundry`                          | Domain-neutral compute layer contains release/domain bridges and several causal mega-modules                                                 | Move domain bridges out; split method catalog files by algorithm family and keep public method facade stable            |
| `src/polisyos/ir`                               | Analytics/observation modules import Foundry, Scientist, and Datasets                                                                        | Keep models/contracts in IR; move execution adapters and service helpers upward                                         |
| `src/polisyos/runtime/http/services/control.py` | ~4k LOC control surface imports many lower-level internals, including batch paths                                                            | Split by bounded service surface: data, runs, artifacts, lex, admin; call public facades only                           |
| `src/polisyos/scientist/nodes/builtins`         | Several large built-in node files combine orchestration and payload construction                                                             | Split large node implementations into contracts, loaders, execution, and presentation helpers                           |
| `src/polisyos/packs`                            | Empty-ish namespace with no README while import policy currently allows wildcard dependencies                                                | Define pack policy, add README, and narrow imports to public facades                                                    |
| `src/polisyos/**/__pycache__` and `.DS_Store`   | Local generated files are present throughout source packages                                                                                 | Keep ignored; add cleanup/doctor command and IDE excludes so source views stay clean                                    |

#### 2.6.2 Tests, Fixtures, and Benchmarks

| Area                                                                        | Finding                                                                                 | Target work                                                                                                                                      |
| --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `tests/academic`, `tests/datasets`, `tests/ukraine_data`, `tests/unit/lex/batch` | Tests mirror old package boundaries                                                     | Move or alias tests with the code: `tests/unit/data_forge/academic`, `tests/unit/data_forge/catalog`, `tests/unit/data_forge/ukraine`, `tests/unit/data_forge/legal` |
| `tests/fixtures`                                                            | Shared fixture directory lacks README/ownership policy                                  | Add fixture README with size, determinism, refresh, and commit policy                                                                            |
| `tests/unit/foundry` and `tests/unit/scientist`                                       | Very large test subtrees; many pycache artifacts present locally                        | Keep source layout, but hide generated caches and require suite-level README/ownership for large subtrees                                        |
| `benchmarks/_reports`                                                       | Ignored generated benchmark output lives beside benchmark source and is ~9.5 MB locally | Route transient reports to `.polisyos/benchmarks/`; move curated summaries to `docs/archive/reports/` or register as generated artifacts         |
| `benchmark-results`                                                         | Ignored final/visual benchmark output lives at product root                             | Treat as local output only; canonical baseline summaries go through the generated-artifact registry                                              |
| `benchmarks/*`                                                              | Many benchmark suites lack README files                                                 | Add suite-level READMEs for non-obvious suites or create a central benchmark registry with owner, inputs, outputs, and expected runtime          |

#### 2.6.3 Tools, Scripts, and Operations

| Area                                                  | Finding                                                                                      | Target work                                                                                                                                        |
| ----------------------------------------------------- | -------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `tools/ops/cloud` vs `tools/ops/cloud`                    | Exact duplicated basenames across the cloud tool tree                                        | Pick `tools/ops/cloud` as canonical; make `tools/ops/cloud` wrapper-only with sunset, then remove                                                      |
| `tools/quality/lint` vs `tools/quality/lint`                  | Duplicate lint command homes                                                                 | Pick `tools/quality/lint` for quality gates; keep old path wrappers only during transition                                                         |
| `tools/quality/diagnostics` vs `tools/quality/diagnostics`    | Duplicate diagnostics command homes                                                          | Pick one canonical diagnostics namespace under `tools/quality` or `tools/devx`; document command aliases                                           |
| `tools/quality/validation` vs `tools/quality/validation`      | Duplicate validation command homes                                                           | Consolidate validation under `tools/quality/validation`                                                                                            |
| `tools/quality/testing` vs `tools/quality/testing`            | Duplicate testing helpers                                                                    | Consolidate under `tools/quality/testing` unless a helper is pure developer workflow                                                               |
| `tools/ops/data` vs `tools/ops/data`                      | Duplicate data utility homes                                                                 | Split: Data Forge CLIs under package/tools, operational data jobs under `tools/ops/data`                                                           |
| `tools/ops/release` vs `tools/ops/release`                | Duplicate release utility homes                                                              | Use `tools/ops/release` for release procedures; keep `release/` for release policy/config only                                                     |
| `tools/ops/ukraine_data` vs `tools/ops/ukraine_data`      | Duplicate Ukraine operational tooling                                                        | Move build-time tooling to `data_forge.ukraine` or `tools/ops/data_forge/ukraine`; operations to `tools/ops/ukraine_data`                              |
| `scripts/`                                            | Mix of bootstrap wrappers, benchmark scripts, fixture recorders, and generated `__pycache__` | Keep only stable executable wrappers; move maintained Python logic to `tools/` or package CLIs                                                     |
| `cloud_deploy/`, `gcp/`, `deploy/`, `docker/`, `ops/` | Multiple operations/deployment homes; `cloud_deploy` contains local env/shard files          | Consolidate under `ops/cloud`, `ops/docker`, `ops/observability`, and `ops/release`; local env/shards move to ignored `.polisyos/` or root `data/` |
| nested `policy-engine/.github`                        | Duplicate GitHub config/workflows beside root `.github`                                      | Root `.github` is active; move product templates to `ops/ci/templates` or delete obsolete nested workflows                                         |

#### 2.6.4 Frontend

| Area                                                                                                   | Finding                                                       | Target work                                                                                                                                   |
| ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `apps/runtime-dashboard/node_modules`                                                              | ~760 MB local dependency tree                                 | Ignored/local only; hide in IDE and cleanup command                                                                                           |
| `apps/runtime-dashboard/dist`, `coverage`, `storybook-static`, `playwright-report`, `test-results` | Generated outputs live beside source                          | Keep ignored; route persistent curated reports to docs/archive or CI artifacts                                                                |
| `apps/runtime-dashboard/src/api/types.ts`                                                          | Large generated API type file (~8.2k LOC) is tracked          | Register as generated artifact with source OpenAPI command, owner, and freshness rule                                                         |
| `packages/runtime-api-client`                                                                          | Generated client is tracked                                   | Register as generated artifact; ensure generation command is canonical and CI-verifiable                                                      |
| `apps/runtime-dashboard/.tmp`                                                                      | Local fixture/generated runtime payloads live inside frontend | Keep ignored; if fixtures become canonical, move to `src/test/fixtures` or `tests/frontend/fixtures` with README                              |
| `apps/runtime-dashboard/src/features/*`                                                            | Feature-sliced layout is mostly healthy                       | Keep; apply the same boundary policy: features consume `src/api`, `shared`, and domain models through public barrels rather than deep imports |

#### 2.6.5 Docs, Architecture, and Release Metadata

| Area                                  | Finding                                                                                                 | Target work                                                                                                                                |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| `docs/*.md`                           | Many active root-level plan docs coexist with reference/how-to/runbook docs                             | Every active plan gets owner and `.gitignore` exception; accepted plans move to `docs/plans/archive/` with ADR/reference/runbook follow-up |
| `docs/.DS_Store`                      | Local Finder artifact in docs root                                                                      | Delete locally; keep ignored                                                                                                               |
| active docs with absolute local paths | Active docs should not contain `/Users/...` or machine-local paths except intentional archived evidence | Keep archive evidence if needed; fix active reference docs and rely on docs accuracy gate                                                  |
| `architecture/`                       | Already has public surface and generated artifact registry                                              | Add `topology.toml` and `package_boundaries.toml`; make guardrails read these instead of hardcoded assumptions                             |
| `release/`                            | Release policy/config is small and tracked                                                              | Keep as policy/config; move runnable release procedures to `tools/ops/release`                                                             |

#### 2.6.6 Local Data, Runtime State, and Generated Outputs

| Area                                                                                               | Finding                                                                    | Target work                                                                                                   |
| -------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `policy-engine/data`                                                                               | Only README/guidelines are tracked; ignored raw WVS/local DB data is large | Keep tracked docs/gold only; move raw/local DBs to root `data/` or `.polisyos/`                               |
| `production_data`                                                                                  | 7.4 GB local release cache with DuckDB/HNSW/JSONL/NPZ bundles              | Keep ignored; manifests use logical artifact URIs + hashes, not local absolute paths                          |
| `runs/`, `logs/`, `tmp/`, `.tmp/`, `.polisyos/`                                                    | Local runtime/scratch state appears in several places                      | Route product-local state to `.polisyos/` by default and scratch to `.tmp/`; root `tmp/` is user scratch only |
| `site/`, `dist/`, `out/`                                                                           | Generated docs/build/batch outputs in product root                         | Keep ignored; add doctor checks when generated output grows outside approved roots                            |
| `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.hypothesis`, `.uv-cache`, `.venv*` | Expected local caches and environments                                     | Keep ignored; add `tools/devx/workspace/clean` or `polisyos doctor --cleanup` recipe                               |

---

## 3. Design Decisions

### 3.1 Naming: `data_forge`

"forge" evokes transformation (raw -> refined), distinct from fabric's "weaving" metaphor. Alternatives considered:

- "pipeline" -- too generic (every module has pipelines)
- "ingestion" -- understates scope (includes extraction, graph building, embedding)
- "data_plane_batch" -- too infrastructure-y for a domain module

### 3.2 Knowledge subpackages: Inside data_forge

`academic/knowledge/` and `catalog/knowledge/` move into data_forge because:

1. They query DuckDB/HNSW artifacts that data_forge produces
2. They version-track with the schema that data_forge defines
3. Build-time schema and artifact readers version with the producing pipeline

Read-side APIs must stay behind a dependency-light facade so downstream
consumers have a stable import surface. If Fabric, Foundry, Lex, Scientist, or
Runtime needs a registry/knowledge lookup at runtime, it should import a public
contract/read facade from `fabric.catalog`, `scholar`, `core.contracts`, `ir`,
or a documented side-effect-free `data_forge.<domain>.read_api` module -- not a
pipeline stage, batch orchestrator, or domain builder.

### 3.3 Lex batch boundary

- **Moves to `data_forge/legal/`:** batch pipeline, config, stages, jurisdictions, patterns, quality checks, spo_cache, hallucination_detector, graph_builder, embeddings
- **Stays in `polisyos.lex`:** corpus/, normpack/, legal_evaluation/, impact/what-if analysis, legal-to-IR intervention compiler, errors.py, types.py, api.py, common.py, factlog.py, artifacts.py
- **Splits out of Lex:** DTR execution and hierarchical policy-search adapters currently colocated in `lex/interventions.py`
- Rationale: lex.corpus depends on fabric.docs (runtime). lex.normpack depends on fabric.claims (runtime).
- Rationale: legal impact analysis is NormPack/governance semantics, not
  generic Foundry runtime. Foundry should execute DTR/causal methods from
  neutral IR contracts, while Scientist owns search/planning orchestration.

### 3.4 Monorepo: Stay as subpackage

data_forge shares types with fabric, scientist, foundry. Separate package would require a shared types package -- premature. Consider extracting only when >3 teams work independently.

### 3.5 Source adapter protocol: Promote to generic

Ukraine's `SourceAdapter` protocol (discover -> fetch -> normalize -> validate) generalized for all pipelines as `data_forge/harvest/adapter.py`. Domain implementations:

- `OpenAlexAdapter` -- academic
- `SDMXAdapter`, `CKANAdapter` -- catalog
- `TabularAdapter` -- ukraine
- `XMLCorpusAdapter` -- legal

---

## 4. Generic Pipeline Framework

The core value of this consolidation: extract repeated pipeline orchestration into a reusable framework that all four domain pipelines inherit. Design informed by Dagster's software-defined assets, Prefect 3's decorator-based flows, Apache Beam's PTransform composites, and dbt's manifest-driven DAG model.

### 4.1 Stage Protocol

```python
# data_forge/pipeline/stage.py

from __future__ import annotations
from typing import Protocol, Any, runtime_checkable
from dataclasses import dataclass, field
from enum import Enum


class StageStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class Severity(str, Enum):
    CRITICAL = "critical"   # Blocks pipeline
    ERROR = "error"         # Blocks publish, logged prominently
    WARNING = "warning"     # Logged, doesn't block
    INFO = "info"           # Informational metric


@dataclass(frozen=True)
class Finding:
    """Structured validation finding (replaces untyped string lists)."""
    severity: Severity
    code: str                            # machine-readable: "missing_sha256", "low_coverage"
    message: str                         # human-readable
    stage: str = ""
    artifact: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class StageResult:
    """Uniform result from any pipeline stage."""
    status: StageStatus
    outputs: dict[str, ArtifactRef]      # artifact_name -> ref with path+sha256+size+rows
    metrics: dict[str, int | float]      # counters, timings, quality scores
    findings: list[Finding]              # structured warnings/errors
    elapsed_seconds: float
    lineage: list[LineageRecord] = field(default_factory=list)


@dataclass(frozen=True)
class StageContract:
    """Declares what a stage requires and produces -- verified at DAG build time."""
    input_artifacts: frozenset[str]               # required artifact names from predecessors
    output_artifacts: frozenset[str]               # artifact names this stage produces
    input_schemas: dict[str, type[BaseModel]] = field(default_factory=dict)
    output_schemas: dict[str, type[BaseModel]] = field(default_factory=dict)
    idempotent: bool = True                        # safe to retry on failure?
    parallelizable: bool = False                   # can run concurrently with siblings?


@dataclass(frozen=True)
class ResourceEstimate:
    """Pre-flight resource estimate for scheduler decisions."""
    peak_memory_gib: float = 0.0
    disk_write_gib: float = 0.0
    estimated_seconds: float = 0.0
    requires_network: bool = False
    requires_gpu: bool = False


@runtime_checkable
class Stage(Protocol):
    """Contract every pipeline stage must satisfy."""

    @property
    def stage_id(self) -> str: ...

    @property
    def depends_on(self) -> tuple[str, ...]: ...

    @property
    def contract(self) -> StageContract: ...

    async def run(self, ctx: StageContext) -> StageResult: ...

    def estimate_resources(self, ctx: StageContext) -> ResourceEstimate:
        """Pre-flight resource estimate for scheduler decisions."""
        return ResourceEstimate()
```

**Why this matters:**

- `@runtime_checkable` enables `isinstance(stage, Stage)` validation at DAG build time
- `StageContract` catches misconfigured DAGs before execution (compile-time safety)
- `ResourceEstimate` enables smart scheduling (memory/disk pre-checks)
- `Finding` replaces untyped `list[str]` -- enables programmatic filtering, severity routing

### 4.2 Pipeline Config

```python
# data_forge/pipeline/config.py

class ResumeMode(str, Enum):
    SMART = "smart"     # Skip if inputs unchanged + outputs exist (content-addressed)
    FORCE = "force"     # Always rerun
    OFF = "off"         # No checkpointing at all


@dataclass(frozen=True)
class BasePipelineConfig:
    """
    Base config all domain pipelines extend.
    FROZEN: stages use dataclasses.replace() for overrides.
    """

    # --- Immutable core ---
    snapshot_root: Path
    stages: frozenset[str] = field(default_factory=frozenset)   # empty = all
    resume_mode: ResumeMode = ResumeMode.SMART
    fail_fast: bool = True
    max_cascade_failures: int = 3
    stage_timeout_seconds: float = 0.0                          # 0 = no timeout

    # --- Resource budget ---
    thermal_profile: str = "default"
    max_workers: int = 4
    resource_budget: ResourceBudget = field(default_factory=ResourceBudget)

    # --- LLM extraction (shared) ---
    llm_provider: str = "gonka"
    llm_model: str = "qwen3-235b"
    llm_temperature: float = 0.1
    max_concurrent_llm: int = 12
    llm_rate_limit_rps: float = 5.0
    llm_cache_enabled: bool = True

    # --- Embedding (shared) ---
    embedding_backend: str = "sentence_transformers"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_device: str = "auto"          # auto | cpu | cuda | mps
    embedding_dim: int = 1024
    embedding_batch_size: int = 32

    # --- Output paths (computed) ---
    @property
    def raw_dir(self) -> Path: return self.snapshot_root / "raw"
    @property
    def graph_dir(self) -> Path: return self.snapshot_root / "graph"
    @property
    def index_dir(self) -> Path: return self.snapshot_root / "index"
    @property
    def manifests_dir(self) -> Path: return self.snapshot_root / "manifests"

    @abstractmethod
    def all_stage_ids(self) -> tuple[str, ...]:
        """Ordered list of all stage IDs for this domain pipeline."""
        ...

    def __post_init__(self):
        if not self.snapshot_root.is_absolute():
            raise ValueError(f"snapshot_root must be absolute: {self.snapshot_root}")
        if self.max_workers < 1:
            raise ValueError(f"max_workers must be >= 1: {self.max_workers}")
        unknown = self.stages - frozenset(self.all_stage_ids())
        if unknown:
            raise ValueError(f"Unknown stages: {unknown}")

    def with_overrides(self, **kw) -> BasePipelineConfig:
        return replace(self, **kw)
```

**Secrets are separated -- never serialized into manifests:**

```python
# data_forge/pipeline/secrets.py

@dataclass(frozen=True)
class SecretsConfig:
    gonka_api_keys: tuple[str, ...] = ()
    openai_api_key: str = ""
    openalex_email: str = ""
    unpaywall_email: str = ""
    semantic_scholar_api_key: str = ""

    @classmethod
    def from_env(cls) -> SecretsConfig:
        gonka_keys = []
        if key := os.environ.get("GONKA_API_KEY", ""):
            gonka_keys.append(key)
        for i in range(1, 10):
            if key := os.environ.get(f"GONKA_API_KEY_{i}", ""):
                gonka_keys.append(key)
        return cls(
            gonka_api_keys=tuple(gonka_keys),
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openalex_email=os.environ.get("OPENALEX_EMAIL", ""),
            unpaywall_email=os.environ.get("UNPAYWALL_EMAIL",
                                           os.environ.get("OPENALEX_EMAIL", "")),
            semantic_scholar_api_key=os.environ.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        )
```

### 4.3 DAG Orchestrator

```python
# data_forge/pipeline/orchestrator.py

class PipelineOrchestrator:
    """
    Production DAG executor. Features:
    - Topological sort with cycle detection (Kahn's algorithm)
    - Parallel execution of independent stages at same DAG level
    - Content-addressed skip detection (not just mtime)
    - Per-stage transaction boundaries
    - Resource budget enforcement via pre-flight estimates
    - Circuit breaker on cascading failures
    - Per-stage timeout via asyncio.wait_for()
    - Structured event emission for observability
    """

    def __init__(
        self,
        config: BasePipelineConfig,
        stages: list[Stage],
        telemetry: PipelineTelemetry,
    ):
        self._config = config
        self._stages = {s.stage_id: s for s in stages}
        self._telemetry = telemetry
        self._dag = self._build_and_validate_dag(stages)

    def _build_and_validate_dag(self, stages: list[Stage]) -> dict[str, list[str]]:
        """Build DAG with compile-time contract validation."""
        # 1. Check for duplicate stage_ids
        # 2. Check all depends_on references exist
        # 3. Check for cycles (Kahn's algorithm)
        # 4. Validate contracts: every stage's input_artifacts
        #    must be in some predecessor's output_artifacts
        # 5. Return adjacency list
        ...

    async def run(self) -> PipelineResult:
        cascade_failures = 0

        for level in self._topo_levels():     # grouped by dependency level
            if len(level) > 1 and all(s.contract.parallelizable for s in level):
                results = await asyncio.gather(
                    *(self._run_stage(s) for s in level),
                    return_exceptions=True,
                )
            else:
                results = [await self._run_stage(s) for s in level]

            for stage, result in zip(level, results):
                if isinstance(result, Exception):
                    cascade_failures += 1
                    if cascade_failures >= self._config.max_cascade_failures:
                        raise CascadeFailureError(
                            f"Pipeline halted: {cascade_failures} consecutive failures")
                elif result.status == StageStatus.COMPLETED:
                    cascade_failures = 0

        return self._aggregate_results()

    async def _run_stage(self, stage: Stage) -> StageResult:
        if self._should_skip(stage):
            return StageResult(status=StageStatus.SKIPPED, ...)

        # Pre-flight resource check
        estimate = stage.estimate_resources(ctx)
        self._check_resource_budget(stage, estimate)

        # Execute with telemetry
        self._telemetry.stage_started(stage.stage_id)
        ctx = self._build_context(stage)
        try:
            result = await asyncio.wait_for(
                stage.run(ctx),
                timeout=self._config.stage_timeout_seconds or None,
            )
        except asyncio.TimeoutError:
            result = StageResult(
                status=StageStatus.FAILED,
                findings=[Finding(Severity.CRITICAL, "stage_timeout", ...)],
                ...)

        # Post-stage validation + persist
        self._validate_output_contracts(stage, result)
        self._persist_manifest(stage, result)
        self._telemetry.stage_completed(stage.stage_id, result)

        # Thermal cooldown
        if self._thermal.cooldown_seconds > 0:
            await asyncio.sleep(self._thermal.cooldown_seconds)

        return result
```

### 4.4 Declarative Pipeline Definition (per domain)

Instead of imperative `if stage == "X": run_X()` chains, declare typed stage lists:

```python
# data_forge/academic/pipeline.py

ACADEMIC_STAGES = [
    TopicSelectStage(),          # depends_on=()
    DemandHarvestStage(),        # depends_on=("topic_select",)
    HarvestStage(),              # depends_on=("topic_select",)
    DocNormalizeStage(),         # depends_on=("harvest",)
    ResolveExtractStage(),       # depends_on=("doc_normalize",)
    ResolveFinalizeStage(),      # depends_on=("resolve_extract",)
    NumericExtractStage(),       # depends_on=("resolve_finalize",)
    MergeStage(),                # depends_on=("resolve_finalize",)
    ClaimAdjudicateStage(),      # depends_on=("merge",)
    ConflictResolveStage(),      # depends_on=("claim_adjudicate",)
    GraphLoadStage(),            # depends_on=("conflict_resolve",)
    EdgeSynthesizeStage(),       # depends_on=("graph_load",)
    GraphIndexStage(),           # depends_on=("edge_synthesize",)
    TransportScoreStage(),       # depends_on=("graph_index",)
    EmbedStage(),                # depends_on=("graph_load",), parallelizable=True
    BenchmarkStage(),            # depends_on=("embed", "transport_score")
    QCStage(),                   # depends_on=("benchmark",)
    PublishStage(),              # depends_on=("qc",)
]

async def run_academic_pipeline(config: AcademicConfig) -> PipelineResult:
    return await PipelineOrchestrator(config, ACADEMIC_STAGES).run()
```

**Benefits:**

- Automatic topological sort and parallel stage execution where dependencies allow
- Each stage is independently testable
- `depends_on` makes data flow explicit and auditable
- Adding a new stage = one class + one list entry

**Parallelizable stages identified:**

```text
Academic:  topic_select -> [harvest, demand_harvest]
           resolve_finalize -> [numeric_extract, merge]
           graph_load -> [embed, transport_score]

Catalog:   graph_load -> [embed, core_sources_ingest]

Legal:     spo -> [ground_quotes, resolve_refs]
```

### 4.5 Unified DuckDB Graph Builder

```python
# data_forge/io/duckdb_loader.py

class DuckDBGraphBuilder:
    """
    Generic DuckDB schema manager. Replaces independent implementations in
    academic/batch/graph_builder.py (1831 LOC), datasets/batch/graph_builder.py (400 LOC),
    and lex/batch/graph_builder.py (3542 LOC).

    Domain-specific DDL and data mapping stay in each pipeline's graph_builder.py.
    """

    SCHEMA_VERSION_TABLE = """
        CREATE TABLE IF NOT EXISTS _schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            migration_name TEXT
        )
    """

    def __init__(self, db_path: Path, *, read_only: bool = False):
        self._db_path = db_path
        self._con = duckdb.connect(str(db_path), read_only=read_only)
        if not read_only:
            self._con.execute(self.SCHEMA_VERSION_TABLE)

    def apply_schema(self, ddl: str, version: int, migration_name: str = "") -> None:
        """Apply DDL only if version > current. Forward-only migration."""
        current = self._current_version()
        if version <= current:
            return
        with self.transaction():
            self._con.execute(ddl)
            self._con.execute(
                "INSERT INTO _schema_version (version, migration_name) VALUES (?, ?)",
                [version, migration_name])

    def bulk_load(
        self, table: str, source: Path, *,
        format: str = "jsonl",
        batch_size: int = 10_000,
        on_conflict: str = "REPLACE",
    ) -> int:
        """Bulk load with transaction boundary. Returns row count."""
        with self.transaction():
            if format == "parquet":
                return self._load_parquet(table, source, on_conflict)
            elif format == "jsonl":
                return self._load_jsonl_batched(table, source, batch_size, on_conflict)
            else:
                raise ValueError(f"Unsupported format: {format}")

    def create_indexes(self, index_defs: list[IndexDef]) -> None:
        """Create indexes from declarative definitions -- idempotent."""
        for idx in index_defs:
            self._con.execute(
                f"CREATE INDEX IF NOT EXISTS {idx.name} "
                f"ON {idx.table} ({', '.join(idx.columns)})")

    def vacuum_and_checkpoint(self) -> None:
        self._con.execute("CHECKPOINT")

    @contextmanager
    def transaction(self):
        """Explicit transaction boundary -- prevents partial writes."""
        self._con.execute("BEGIN TRANSACTION")
        try:
            yield
            self._con.execute("COMMIT")
        except Exception:
            self._con.execute("ROLLBACK")
            raise
```

**Indexes as data** (instead of 25+ hardcoded CREATE INDEX statements):

```python
ACADEMIC_INDEXES = [
    IndexDef("idx_works_topic",    "ac_works",              ["topic_id"]),
    IndexDef("idx_works_year",     "ac_works",              ["year"]),
    IndexDef("idx_estimates_work", "ac_parameter_estimates", ["work_id"]),
    IndexDef("idx_claims_cause",   "ac_causal_claims",      ["cause"]),
    ...
]
```

### 4.6 Content-Addressed Checkpointing

```python
# data_forge/pipeline/checkpoints.py

class ContentAddressedCheckpoint:
    """
    Consolidates:
    - datasets/batch/checkpoints.py (mtime+size fingerprinting)
    - ukraine_data/orchestrator.py (manifest-based resume)
    - academic/batch/pipeline.py (no checkpointing -- always full rerun)

    Hybrid approach: fast mtime check + SHA256 verification on mismatch.
    """

    def should_skip(self, stage_id: str, input_refs: list[ArtifactRef]) -> bool:
        """
        Skip if:
        1. Previous run completed successfully
        2. Input artifacts unchanged (content-addressed)
        3. All output artifacts still exist
        """
        prev = self._state.get(stage_id)
        if prev is None or prev.status != "completed":
            return False

        # Fast path: check mtime first
        if self._mtimes_match(prev.input_fingerprints, input_refs):
            return self._outputs_exist(prev.output_refs)

        # Slow path: verify via SHA256
        if self._hashes_match(prev.input_fingerprints, input_refs):
            return self._outputs_exist(prev.output_refs)

        return False  # Inputs changed -> must rerun

    def record(self, stage_id: str, result: StageResult, input_refs: list[ArtifactRef]):
        """Record checkpoint with both mtime and content hash."""
        ...
```

### 4.7 Unified Manifest Model

```python
# data_forge/pipeline/manifest.py

@dataclass(frozen=True)
class ArtifactRef:
    path: str
    sha256: str
    size_bytes: int = 0
    row_count: int | None = None

@dataclass
class StageManifest:
    pipeline: str                       # "academic" | "catalog" | "ukraine" | "legal"
    stage: str
    status: str                         # "completed" | "failed" | "skipped"
    started_at: str                     # ISO UTC
    finished_at: str
    elapsed_seconds: float
    inputs: list[ArtifactRef]
    outputs: list[ArtifactRef]
    metrics: dict[str, Any]
    findings: list[Finding]
    resource_usage: ResourceUsage | None = None

@dataclass
class PublishManifest:
    pipeline: str
    version: str
    artifacts: list[ArtifactRef]
    qc_report_ref: str | None = None
    benchmark_report_ref: str | None = None
    consumer_readiness: dict[str, bool] = field(default_factory=dict)
```

### 4.8 Lineage & Provenance

W3C PROV-compatible lineage tracking (reuses existing `RunProvenanceDAG` from `scientist.provenance`):

```python
@dataclass(frozen=True)
class LineageRecord:
    artifact_id: str            # SHA256-based content address
    pipeline: str               # "academic" | "catalog" | "ukraine" | "legal"
    stage: str
    parent_artifacts: list[str] # IDs of input artifacts
    transform: str              # Stage class name
    timestamp: str              # ISO UTC
    config_hash: str            # Hash of stage config for reproducibility
```

Every artifact gets a lineage record in `manifests/lineage.jsonl`. Enables:

- Full backward tracing from any production artifact to raw source
- Diff detection: which artifacts changed between runs
- Audit compliance for data provenance requirements

### 4.9 Resource Scheduler

```python
# data_forge/pipeline/scheduler.py

class ResourceScheduler:
    """
    Decides whether a stage can run given current system resources.
    Generalizes ukraine_data's ResourceBudget + ResourceTracker for all pipelines.
    """

    def can_run(self, estimate: ResourceEstimate) -> tuple[bool, str]:
        available_mem = self._available_memory_gib()
        if estimate.peak_memory_gib > 0 and estimate.peak_memory_gib > available_mem * 0.8:
            return False, f"Insufficient memory: need {estimate.peak_memory_gib:.1f} GiB"
        available_disk = self._available_disk_gib()
        if estimate.disk_write_gib > 0 and estimate.disk_write_gib > available_disk * 0.9:
            return False, f"Insufficient disk: need {estimate.disk_write_gib:.1f} GiB"
        return True, ""
```

### 4.10 Domain Pipeline Registry

```python
# data_forge/pipeline/registry.py

@dataclass(frozen=True)
class DomainPipelineInfo:
    name: str                          # "academic", "catalog", "ukraine", "legal"
    config_class: type[BasePipelineConfig]
    stages: list[type[Stage]]
    cli_help: str
    default_profile: str = "prod_full"

DOMAIN_PIPELINES: list[DomainPipelineInfo] = []

def register_pipeline(info: DomainPipelineInfo) -> None:
    """Called by each domain's __init__.py at import time."""
    DOMAIN_PIPELINES.append(info)
```

Eliminates hardcoded pipeline lists. New domains auto-register with one line in `__init__.py`. CLI and snapshot finalization discover pipelines dynamically.

### 4.11 Structured Error Hierarchy

```python
# data_forge/errors.py

class DataForgeError(Exception):
    """Base for all data_forge errors."""
    def __init__(self, message: str, *, stage: str = "", pipeline: str = "",
                 details: dict | None = None):
        super().__init__(message)
        self.stage = stage
        self.pipeline = pipeline
        self.details = details or {}

class StageFailedError(DataForgeError): ...
class ContractViolationError(DataForgeError): ...
class CascadeFailureError(DataForgeError): ...
class ManifestIntegrityError(DataForgeError): ...
class CircuitOpenError(DataForgeError): ...
class ResourceBudgetExceededError(DataForgeError): ...
```

Generalizes the lex error hierarchy pattern (the best of the current implementations).

---

## 5. Shared Infrastructure Modules

### 5.1 Async Harvest Framework

#### Fetcher with Circuit Breaker

```python
# data_forge/harvest/fetcher.py

class AsyncFetcher:
    """
    Consolidates:
    - academic/openalex/client.py (retry + backoff + 429 handling)
    - datasets/batch/harvester.py (retry + Retry-After parsing + timeout)
    - lex/batch/spo_client.py (adaptive rate + connection pooling)
    """

    def __init__(
        self,
        rate_limiter: TokenBucketLimiter,
        *,
        max_retries: int = 5,
        base_backoff_seconds: float = 0.5,
        max_backoff_seconds: float = 60.0,
        timeout_seconds: float = 60.0,
        circuit_breaker_threshold: int = 10,
    ): ...

    async def fetch(self, url: str, *, method: str = "GET",
                    headers: dict | None = None, json_body: Any = None) -> FetchResult:
        """Fetch with token-bucket rate limiting, exponential backoff on 429/5xx,
        Retry-After header parsing, circuit breaker."""
        ...

    def _backoff_delay(self, attempt: int) -> float:
        return min(self._base_backoff * (2 ** attempt), self._max_backoff)
```

#### Token-Bucket Rate Limiter (replaces 3 implementations)

```python
# data_forge/harvest/rate_limiter.py

class TokenBucketLimiter:
    """
    Replaces:
    - academic/openalex/rate_limiter.py (sliding window + semaphore)
    - lex/batch/spo_client.py (adaptive sliding window)
    - datasets/batch/harvester.py (inline sleep)

    Token bucket: simpler, more predictable, supports burst.
    """

    def __init__(self, rate: float, burst: int = 1, max_concurrent: int = 10): ...
    async def acquire(self) -> None: ...
    def release(self) -> None: ...
```

#### Source Adapter Protocol

```python
# data_forge/harvest/adapter.py

@runtime_checkable
class SourceAdapter(Protocol):
    @property
    def adapter_id(self) -> str: ...
    async def discover(self, source: SourceSpec, ctx: HarvestContext) -> list[str]: ...
    async def fetch(self, source: SourceSpec, ctx: HarvestContext) -> FetchManifest: ...
    async def normalize(self, source: SourceSpec, raw: FetchManifest, ctx: HarvestContext) -> NormalizeManifest: ...
    def validate(self, manifest: NormalizeManifest) -> list[Finding]: ...
```

### 5.2 LLM Extraction Framework

#### Unified Client Pool

```python
# data_forge/extraction/llm_client.py

class LLMClientPool:
    """
    Consolidates academic AcademicLLMClient + lex GonkaClientPool.
    Features:
    - Multi-key rotation with per-key rate limiting
    - Adaptive rate adjustment based on 429 frequency
    - Structured cost tracking per stage/domain
    - Response caching (SQLite, content-addressed)
    """

    async def complete(
        self, messages: list[dict], *,
        model: str, temperature: float = 0.1,
        response_schema: type[BaseModel] | None = None,
        cache_key: str | None = None,
    ) -> LLMResponse: ...
```

#### Unified Gate System

```python
# data_forge/extraction/llm_gate.py

class LLMGate:
    """
    Unified routing: deterministic vs LLM vs deferred.
    Both academic (irreducibility score) and lex (feature-based routing)
    use the same pattern: compute features -> score -> route by threshold.
    """

    def __init__(self, config: GateConfig, domain_features: DomainFeatureExtractor): ...

    def decide(self, text: str, det_confidence: float, **ctx) -> GateDecision: ...


class DomainFeatureExtractor(Protocol):
    """Domain-specific feature extraction."""
    def extract(self, text: str, **ctx) -> GateFeatures: ...

# Domain implementations keep their specific weights:
class AcademicFeatureExtractor(DomainFeatureExtractor): ...   # numeric density, ambiguity
class LegalFeatureExtractor(DomainFeatureExtractor): ...      # modality markers, amendment signals
```

#### Content-Addressed Response Cache

```python
# data_forge/extraction/llm_cache.py

class LLMResponseCache:
    """
    Consolidates lex/batch/spo_cache.py (SQLite) + academic dedup (in-memory).
    Content-addressed, domain-agnostic, WAL-mode SQLite.
    Shared across all pipelines -> ~30% cross-domain cache overlap expected.
    """
    ...
```

### 5.3 Embedding Pipeline

```python
# data_forge/index/embedder.py

class EmbeddingBackend(Protocol):
    async def embed_batch(self, texts: list[str]) -> np.ndarray: ...

class SentenceTransformerBackend(EmbeddingBackend): ...
class OpenAIBatchBackend(EmbeddingBackend): ...


class EmbeddingPipeline:
    """
    Consolidates:
    - academic/batch/embedder.py (sentence-transformers, title+abstract, thermal pause)
    - datasets/batch/embedder.py (sentence-transformers, title+desc+keywords)
    - lex/batch/openai_batch_embeddings.py (OpenAI batch API, 3-phase, mmap shards)

    Key: shard-based processing (from lex pattern) prevents OOM on large corpora.
    """

    async def build_index(
        self,
        records: AsyncIterable[tuple[str, str]],   # (id, text) -- streaming
        output_dir: Path,
        prefix: str,                                # "ac_work" | "ds_dataset" | "lex_provision"
        *,
        batch_size: int = 32,
        shard_size: int = 5000,
        thermal_pause: float = 0.0,
    ) -> EmbeddingManifest: ...
```

Domain pipelines provide the `(id, text)` iterator via `TextFormatter` protocol and choose the backend.

```python
# data_forge/index/text_formatters.py

class TextFormatter(Protocol):
    def format(self, record: dict[str, Any]) -> str: ...

class AcademicTextFormatter(TextFormatter):
    """title + abstract[:1200]"""
class CatalogTextFormatter(TextFormatter):
    """title + description[:500] + keywords[:20] + variables[:20]"""
class LegalTextFormatter(TextFormatter):
    """subject + predicate + object (for facts); plain text (for provisions)"""
```

### 5.4 Streaming JSONL I/O

Replaces the identical hand-rolled JSONL loading pattern repeated across dedup.py, graph_builder.py, resolve_extract.py, etc.

```python
# data_forge/io/jsonl.py

def iter_jsonl(
    path: Path, model: type[T], *,
    batch_size: int = 0,
    skip_invalid: bool = False,
    progress: StageProgress | None = None,
) -> Iterator[T] | Iterator[list[T]]:
    """Streaming JSONL reader with Pydantic validation, batching, progress."""
    ...

def write_jsonl(path: Path, records: Iterable[BaseModel], *, append: bool = False) -> int:
    """Write Pydantic models as JSONL. Returns count."""
    ...
```

### 5.5 Incremental Processing

```python
# data_forge/pipeline/incremental.py

class IncrementalStrategy:
    """Determines which records need reprocessing."""

    def changed_since(self, last_run: StageManifest) -> set[str]:
        """Compare input fingerprints with last run's inputs."""
        ...

    def merge_incremental(self, existing: Path, new: Path, key: str) -> Path:
        """Merge new records into existing output, dedup by key."""
        ...
```

Domain-specific strategies:

- **Academic:** re-extract only papers with new fulltext availability or retraction status
- **Catalog:** re-harvest only sources whose upstream data changed (via ETag/Last-Modified)
- **Ukraine:** re-build only stages whose normalized parquet inputs changed
- **Legal:** re-extract only documents with new amendments

---

## 6. Quality Framework

### 6.1 Four-Tier Quality Cascade

```text
Tier 0 (compile-time):   StageContract validation at DAG build
                          -> Catches misconfigured pipelines before any execution
                          -> NEW: not in any current pipeline

Tier 1 (pre-stage):      Phase 0 deterministic gates (counts, schema, coverage)
                          -> BLOCK if critical thresholds unmet
                          -> Prevents wasting compute on bad inputs

Tier 2 (post-stage):     Output contract validation + statistical checks
                          -> BLOCK if outputs violate contracts
                          -> Catches extraction/transformation errors

Tier 3 (pre-publish):    Benchmark suite + consumer readiness + golden test
                          -> BLOCK if quality below acceptance threshold
                          -> Ensures downstream consumers get reliable data
```

### 6.2 QC Model

```python
# data_forge/quality/qc.py

@dataclass(frozen=True)
class QCCheck:
    name: str
    passed: bool
    severity: Severity                  # Enum, not unvalidated string
    value: float | int | str = ""
    threshold: float | int | str = ""
    message: str = ""
    group: str = ""                     # "completeness", "freshness", "accuracy"
    details: dict[str, Any] = field(default_factory=dict)

@dataclass
class QCReport:
    scope: str
    checks: list[QCCheck] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    config_hash: str = ""              # Reproducibility

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks if c.severity == Severity.CRITICAL)

    @property
    def has_errors(self) -> bool:
        return any(not c.passed and c.severity == Severity.ERROR for c in self.checks)

    def failed_checks(self, min_severity: Severity = Severity.WARNING) -> list[QCCheck]: ...
```

### 6.3 Data Contracts (Schema-First)

Enforce typed contracts between stages using Pydantic models with `ConfigDict(extra="forbid")`:

```python
class StageContract:
    input_schemas: dict[str, type[BaseModel]]    # artifact_name -> Pydantic model
    output_schemas: dict[str, type[BaseModel]]    # artifact_name -> Pydantic model
```

- **Compile-time validation:** orchestrator checks that every stage's inputs are satisfied by predecessor outputs
- **Runtime validation:** sample rows validated against output schema after each stage
- **Schema versioning:** `SchemaInfo(name, version)` attached to every artifact

### 6.4 Golden Test Framework

```python
# data_forge/quality/golden.py

class GoldenTestRunner:
    """
    Verify migration produces byte-identical outputs.
    Critical for Phase 1-4 migrations.

    1. Pre-migration: snapshot outputs as golden references
    2. Post-migration: run pipeline, compare outputs
    3. Report: per-artifact comparison with diff details

    For deterministic artifacts (DuckDB, Parquet): byte-identical.
    For LLM outputs: structural comparison (same fields, same types).
    """
    def capture_golden(self, snapshot_root: Path, pipeline: str) -> GoldenSnapshot: ...
    def verify_against_golden(self, golden: GoldenSnapshot, current_root: Path) -> GoldenTestResult: ...
```

---

## 7. Observability

### 7.1 Unified Telemetry

```python
# data_forge/pipeline/telemetry.py

class PipelineTelemetry:
    """
    Consolidates:
    - ukraine_data/resources.py (Prometheus textfile, stage_metrics.json, resource_usage.jsonl)
    - datasets/batch/pipeline.py (telemetry.json)
    - academic/batch/pipeline.py (PipelineStats + stage_times)
    - lex/batch/pipeline.py (progress.jsonl)

    Export formats: Prometheus, JSONL, OTLP JSON, human-readable summary.
    """

    def stage_started(self, stage_id: str) -> None: ...
    def stage_completed(self, stage_id: str, result: StageResult) -> None: ...
    def record_metric(self, name: str, value: float, tags: dict) -> None: ...
    def record_resource_snapshot(self) -> None: ...
    def write_prometheus(self, path: Path) -> None: ...
    def write_jsonl(self, path: Path) -> None: ...
    def write_summary(self, path: Path) -> None: ...
    def write_opentelemetry(self, path: Path) -> None: ...
```

### 7.2 Progress Tracking

```python
# data_forge/pipeline/progress.py

class StageProgress:
    """
    Real-time progress tracking for stages with many items.
    Replaces ad-hoc print statements (datasets/batch/harvester.py: "if index % 32 == 0: print(...)").
    Reports every 5% or every 60 seconds with rate and ETA.
    """

    def advance(self, n: int = 1, **metrics) -> None: ...
```

---

## 8. Unified CLI

```bash
# Run specific pipeline
python -m polisyos.data_forge academic --stages topic_select,harvest --resume smart
python -m polisyos.data_forge catalog --profile prod_full
python -m polisyos.data_forge ukraine build d2 --resume smart
python -m polisyos.data_forge legal --stages parse,structure,spo --shard 0/4

# Cross-cutting commands
python -m polisyos.data_forge snapshot finalize /path/to/snapshot
python -m polisyos.data_forge status                # Show all pipeline run statuses
python -m polisyos.data_forge lineage artifact_id    # Trace artifact provenance
python -m polisyos.data_forge diff run1 run2         # Compare two pipeline runs
python -m polisyos.data_forge validate /path/to/snap # Run QC without re-running pipeline
python -m polisyos.data_forge doctor                 # Pre-flight environment check
python -m polisyos.data_forge config academic        # Show resolved config with defaults
python -m polisyos.data_forge clean /path/to/snap    # Remove intermediate artifacts
python -m polisyos.data_forge --dry-run academic     # Show execution plan without running

# Global options
--profile <name>       # Config profile (prod_full, preflight, dev)
--snapshot-root <path> # Override snapshot root
--thermal <profile>    # Thermal profile (default, m2_air_16gb)
--resume <mode>        # Resume mode (smart, force, off)
--stages <list>        # Comma-separated stage list
--verbose              # Verbose logging
--dry-run              # Show what would run without executing
```

Commands `doctor`, `validate`, `config`, `clean`, `diff` are new. Rationale:

- `doctor` -- pre-flight environment validation. Generalizes Ukraine's `probe_local_server_capabilities()`.
- `config` -- show resolved config. Helps debug "why did it use this model?"
- `validate` -- run QC on existing snapshot without re-running pipeline. Post-migration verification.
- `clean` -- remove intermediate artifacts. No cleanup strategy exists currently.
- `--dry-run` -- show execution plan without running. Critical for DAG configuration validation.

---

## 9. Migration Strategy

### 9.1 Principles

1. **Zero downtime.** Old import paths stay alive via `__init__.py` re-exports until all consumers migrate.
2. **Bottom-up.** Extract shared infrastructure first, then migrate domain pipelines one at a time.
3. **Test parity.** Each migration phase must pass existing tests before proceeding.
4. **No behavior changes.** Pure structural refactor -- identical outputs for identical inputs.
5. **Golden test gating.** Every phase must pass golden test before merge.
6. **Topology before deletion.** Classify every moved file as source, fixture, generated artifact, local data, or runtime state before deleting the old path.
7. **Small PRs with stable aliases.** Directory moves use compatibility shims until downstream imports, CI, docs, and runbooks have switched.

### 9.2 Phase -1: Repository Topology Baseline

Create a factual inventory of the current tree before moving domain code. This
phase is intentionally low-risk and should not change runtime behavior.

| Task                             | Details                                                                                                                                                                                                                                |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Produce top-level inventory      | List every repository-root and `policy-engine/` top-level path with owner, type, size, Git status, and target home                                                                                                                     |
| Produce package import graph     | Generate current package-level and subpackage-level imports for `src/polisyos/**`; record all reverse edges from Section 2.5                                                                                                           |
| Produce directory work register  | Use Section 2.6 as the initial backlog; add owner, priority, target phase, and compatibility strategy to each item                                                                                                                     |
| Inventory data roots             | Classify `data/`, `tmp/`, `policy-engine/data/`, `policy-engine/production_data/`, `policy-engine/benchmark-results/`, `policy-engine/baseline/`, and `policy-engine/tmp/` by layer, domain, snapshot id, commit policy, and retention |
| Inventory duplicate tool homes   | Compare `tools/*`, `tools/ops/*`, `tools/quality/*`, `tools/research/*`, `scripts/`, and ops directories for duplicate command names and owners                                                                                        |
| Classify loose files             | Apply the disposition matrix in Section 2.4.10 to every top-level file in repository root and `policy-engine/`                                                                                                                         |
| Classify files                   | Use categories: source, docs, test fixture, generated committed artifact, local data, runtime state, build output, cache, scratch                                                                                                      |
| Draft package boundary ledger    | Add an import-boundary appendix or `architecture/packages/boundaries.toml` covering owner, allowed dependencies, public facade, and sunset exceptions for each package                                                                  |
| Confirm ignored plan files       | Add explicit `.gitignore` exceptions for source-of-truth plans that must be reviewed                                                                                                                                                   |
| Draft topology registry          | Add `architecture/topology.toml` with allowed top-level paths, category, owner, commit policy, and sunset phase                                                                                                                        |
| Add topology gate                | Extend `tools/architecture/guardrails.py` to flag unknown top-level paths and product source under repository root                                                                                                                     |
| Update ownership                 | Add `data_forge` ownership to `.github/CODEOWNERS` and `docs/reference/ownership.md`                                                                                                                                                   |
| Define quarantine paths          | Use `.polisyos/audits/`, `.polisyos/reports/`, `.tmp/`, `tmp/`, and root `data/` for local state instead of ad-hoc root files                                                                                                          |
| Update IDE excludes              | Hide caches, virtualenvs, build outputs, `production_data/`, `node_modules/`, `site/`, `dist/`, `tmp/`, and local CAS from normal explorer views                                                                                       |
| Document allowed top-level paths | Update README or contributor docs with a short allowlist for root and `policy-engine/` top-level directories                                                                                                                           |
| Add loose-file gate              | Fail CI when a new top-level file is neither a sentinel, registered topology entry, ignored local artifact, nor temporary wrapper                                                                                                      |

**Validation:** No imports change. `git status --ignored` shows expected local
artifacts as ignored, and source-of-truth docs are visible to Git.

### 9.3 Phase 0: Foundation + Golden Snapshots

Create `data_forge/` package with shared infrastructure modules. No domain code moves yet.

#### 9.3.1 Pre-Migration: Capture Golden Snapshots

| Task                       | Details                                                                                     |
| -------------------------- | ------------------------------------------------------------------------------------------- |
| Capture academic golden    | Run academic pipeline on 50-paper test corpus -> snapshot all outputs (DuckDB, JSONL, HNSW) |
| Capture catalog golden     | Run catalog pipeline with `preflight_core` profile -> snapshot outputs                      |
| Capture legal golden       | Run lex batch on 10-document test corpus -> snapshot outputs                                |
| Capture ukraine golden     | Use existing D0_P0 test fixtures -> snapshot outputs                                        |
| Create golden test harness | `data_forge/testing/golden.py` with `capture` and `verify` commands                         |

#### 9.3.2 Framework Unit Tests FIRST

Write unit tests for the framework before any domain code migrates:

| Test Module              | Tests                                                          |
| ------------------------ | -------------------------------------------------------------- |
| `test_stage_protocol.py` | Contract validation, DAG building, cycle detection             |
| `test_orchestrator.py`   | Topo sort, skip detection, parallel execution, cascade failure |
| `test_checkpoints.py`    | Content-addressed skip, mtime fast path, output existence      |
| `test_manifest.py`       | Write/read roundtrip, SHA256 computation, ArtifactRef          |
| `test_rate_limiter.py`   | Token bucket, burst, concurrent limit                          |
| `test_fetcher.py`        | Retry, backoff, circuit breaker, 429 handling                  |
| `test_dedup.py`          | Quality-ranked replacement, key generation                     |
| `test_qc.py`             | Severity filtering, fail-fast evaluation                       |

**Rule:** Framework must have >90% test coverage before Phase 1.

#### 9.3.3 Move Shared Infrastructure

| Task                         | Source                                      | Target                                  |
| ---------------------------- | ------------------------------------------- | --------------------------------------- |
| Create `pipeline/` framework | New code, patterns from all orchestrators   | `data_forge/pipeline/`                  |
| Move hashing                 | `batch_common/hashing.py`                   | `data_forge/io/hashing.py`              |
| Move paths                   | `batch_common/paths.py`                     | `data_forge/io/paths.py`                |
| Move manifests               | `batch_common/manifest.py`                  | `data_forge/pipeline/manifest.py`       |
| Move QC models               | `batch_common/qc.py`                        | `data_forge/quality/qc.py`              |
| Move phase0 gates            | `batch_common/phase0_quality_validation.py` | `data_forge/quality/phase0.py`          |
| Move thermal                 | `batch_common/thermal.py`                   | `data_forge/harvest/thermal.py`         |
| Move snapshot                | `batch_snapshot/cli.py`                     | `data_forge/snapshot/finalize.py`       |
| Move checkpoints             | `datasets/batch/checkpoints.py`             | `data_forge/pipeline/checkpoints.py`    |
| Move country_codes           | `datasets/knowledge/country_codes.py`       | `data_forge/transform/country_codes.py` |
| Move interpolation           | `datasets/batch/interpolation.py`           | `data_forge/transform/interpolation.py` |
| Move rate_limiter            | `academic/openalex/rate_limiter.py`         | `data_forge/harvest/rate_limiter.py`    |
| Re-export from old locations | Add compatibility shims                     | `batch_common/__init__.py`, etc.        |

**Validation:** All existing tests pass with re-exports.

#### 9.3.4 Directory Guardrails for New Shared Code

| Guardrail                      | Rule                                                                                                                                           |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| No new old-package infra       | Do not add new shared helpers under `batch_common`, `academic/batch`, `datasets/batch`, `lex/batch`, or `ukraine_data` after this phase starts |
| One public facade              | `polisyos.data_forge` owns the new public batch facade; old packages only re-export                                                            |
| Generated artifacts registered | Any committed schema, manifest, report, or fixture family is added to `architecture/generated_artifacts.toml`                                  |
| Local outputs redirected       | New CLI defaults write scratch to `.polisyos/` or `.tmp/`, not to product root                                                                 |
| Import policy staged           | Add `data_forge` to `import_policy.toml` while old roots remain allowed only for compatibility shims                                           |
| Reverse edges frozen           | No new `ir -> foundry/scientist/datasets`, `foundry -> scientist/lex/domain`, or `lex -> foundry/scientist` imports after Phase 0              |
| Fixtures normalized            | Data Forge test fixtures use `tests/unit/data_forge/**`; migration goldens use the fixture policy in Section 2.4.7                                  |

### 9.4 Phase 1: Academic Pipeline

Move `academic/` into `data_forge/academic/`.

| Task                     | Details                                                                                     |
| ------------------------ | ------------------------------------------------------------------------------------------- |
| Move batch stages        | `academic/batch/*.py` -> `data_forge/academic/stages/`                                      |
| Move config              | `academic/batch/config.py` -> `data_forge/academic/config.py`, inherit `BasePipelineConfig` |
| Move pipeline            | `academic/batch/pipeline.py` -> `data_forge/academic/pipeline.py`, use generic orchestrator |
| Move OpenAlex            | `academic/openalex/` -> `data_forge/academic/openalex/`                                     |
| Move prompts             | `academic/batch/prompts/` -> `data_forge/academic/prompts/`                                 |
| Move knowledge           | `academic/knowledge/` -> `data_forge/academic/knowledge/`                                   |
| Move trust               | `academic/trust.py` -> `data_forge/academic/trust.py`                                       |
| Extract LLM client       | `academic/batch/llm_extractor.py` -> `data_forge/extraction/llm_client.py` (generic)        |
| Extract embedder         | `academic/batch/embedder.py` -> `data_forge/index/embedder.py` (generic)                    |
| Split resolve_extract.py | 4,246 LOC god file -> 5 modules (see Section 1.2.1)                                         |
| Re-export                | `polisyos.academic` -> `polisyos.data_forge.academic`                                       |

**Validation:** Academic pipeline produces identical outputs on test corpus. Golden test passes.

### 9.5 Phase 2: Dataset Catalog Pipeline

Move `datasets/` into `data_forge/catalog/`. **Can run in parallel with Phase 1.**

| Task                         | Details                                                                               |
| ---------------------------- | ------------------------------------------------------------------------------------- |
| Move batch stages            | `datasets/batch/*.py` -> `data_forge/catalog/stages/`                                 |
| Move config                  | Inherit `BasePipelineConfig`, reuse shared LLM/embedding/thermal fields               |
| Move source_registry         | `datasets/batch/source_registry.py` -> `data_forge/catalog/source_registry.py`        |
| Move knowledge               | `datasets/knowledge/` -> `data_forge/catalog/knowledge/`                              |
| Move curation                | `datasets/batch/ckan_curation.py`, `metrics_map.py` -> `data_forge/catalog/curation/` |
| Split core_sources_ingest.py | 7,862 LOC -> per-source modules + shared base protocol                                |
| Reuse generic dedup          | Replace `datasets/batch/dedup.py` with `data_forge/transform/dedup.py`                |
| Reuse generic embedder       | Replace `datasets/batch/embedder.py` with `data_forge/index/embedder.py`              |
| Reuse generic QC             | Replace `datasets/batch/qc.py` with domain-specific checks on `data_forge/quality/`   |

**Validation:** Dataset pipeline produces identical catalog DuckDB. Golden test passes.

### 9.6 Phase 3: Legal Batch Pipeline

Extract batch layer from `lex/` into `data_forge/legal/`. **Can run in parallel with Phase 4.**

| Task                   | Details                                                                                                                        |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Move batch pipeline    | `lex/batch/*.py` -> `data_forge/legal/stages/`                                                                                 |
| Move config            | `lex/batch/config.py` -> `data_forge/legal/config.py`                                                                          |
| Move jurisdictions     | `lex/batch/jurisdictions/` -> `data_forge/legal/jurisdictions/`                                                                |
| Move patterns          | `lex/batch/patterns/` -> `data_forge/legal/patterns/`                                                                          |
| Extract LLM gate       | Merge `lex/batch/llm_gate.py` + `academic/batch/llm_gate` -> `data_forge/extraction/llm_gate.py`                               |
| Extract hallucination  | `lex/batch/hallucination_detector.py` -> `data_forge/extraction/hallucination_detector.py`                                     |
| Split graph_builder.py | 3,542 LOC -> `ddl.py` + `loader.py` + `entity_resolver.py` + `trust.py`                                                        |
| Reuse generic embedder | Replace lex OpenAI batch embedder with shared embedder + OpenAI backend                                                        |
| Update lex imports     | `polisyos.lex` non-batch modules import only from side-effect-free legal knowledge/read facades, never Data Forge batch stages |

**Validation:** Lex batch produces identical KG and SPO outputs. Golden test passes.

### 9.7 Phase 4: Ukraine Pipeline

Move `ukraine_data/` into `data_forge/ukraine/`. **Can run in parallel with Phase 3.**

| Task                    | Details                                                                                                 |
| ----------------------- | ------------------------------------------------------------------------------------------------------- |
| Move all files          | `ukraine_data/*.py` -> `data_forge/ukraine/`                                                            |
| Refactor config         | Inherit `BasePipelineConfig`, keep Ukraine-specific `ServerConfig`, `StageConfig`                       |
| Refactor orchestrator   | Replace `UkraineDataOrchestrator` with generic `PipelineOrchestrator` + Ukraine-specific gates (Part A) |
| Keep adapters           | `TabularSourceAdapter` stays in `data_forge/ukraine/adapters.py` (too Ukraine-specific)                 |
| Reuse generic manifests | Replace Ukraine manifest models with extended `StageManifest`                                           |

**Validation:** Ukraine pipeline produces identical release bundle. Golden test passes.

### 9.8 Phase 5: Directory and Import Cleanup

| Task                                  | Details                                                                                                                                                                            |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Remove old directories                | Delete `academic/`, `datasets/`, `ukraine_data/`, `batch_common/`, `batch_snapshot/`                                                                                               |
| Remove re-export shims                | Clean up compatibility imports                                                                                                                                                     |
| Update all imports                    | Global find-replace across `fabric`, `scientist`, `foundry`, `lex`, tests                                                                                                          |
| Update CI/CD                          | Pipeline configs, Docker, GitHub Actions                                                                                                                                           |
| Update documentation                  | ADRs, runbooks, reference docs                                                                                                                                                     |
| Update import policy                  | Remove old roots from `import_policy.toml`; leave only `data_forge` and non-batch runtime packages                                                                                 |
| Update ownership                      | CODEOWNERS and `docs/reference/ownership.md` point to final Data Forge paths                                                                                                       |
| Fix SQL injection                     | Parameterized queries in all DuckDB paths                                                                                                                                          |
| Fix silent failures                   | All issues from Section 1.2.5                                                                                                                                                      |
| Remove dead code                      | `sha256_jsonl()`, unused `filters` parameter                                                                                                                                       |
| Remove root scratch files             | Move or delete root-level local reports such as `compileall.txt`, `import_gate.txt`, `ruff_stats.txt`, `summary.json`, and `test_collect.txt`                                      |
| Move root research scripts            | Move maintained scripts such as `filter_topics.py` and `organize_relevant_topics.py` under `policy-engine/tools/research/topics/` or delete if obsolete                            |
| Clean product-root loose files        | Resolve `env_example.txt`, `freeze_policy.md`, `install.sh`, `migrate.py`, `jax_bootstrap.py`, `all_1000_policy_topics.csv`, `.DS_Store`, and `=2.5.0` according to Section 2.4.10 |
| Consolidate ops dirs                  | Move `cloud_deploy/`, `deploy/`, `docker/`, and `gcp/` into `policy-engine/ops/` or replace with documented compatibility wrappers                                                 |
| Resolve nested GitHub config          | Move active workflows to root `.github/`; move templates to `policy-engine/ops/ci/templates/`                                                                                      |
| Normalize tools/scripts               | Move maintained `scripts/*.py` into `tools/`; keep only thin wrappers or remove obsolete scripts                                                                                   |
| Consolidate duplicate tool homes      | Resolve duplicate pairs from Section 2.6.3 with one canonical home plus temporary wrappers                                                                                         |
| Quarantine audit bundles              | Move local `*.polisyos-audit.tar.gz` into `.polisyos/audits/`; keep curated audit evidence in `docs/archive/reports/` only                                                         |
| Verify top-level allowlist            | `policy-engine/` top-level paths match Section 2.4 or have a documented owner and sunset date                                                                                      |
| Enforce package boundary policy       | Apply Section 2.5 package layering and make import policy fail on newly forbidden anti-edges                                                                                       |
| Split Lex intervention bridge         | Keep legal-to-IR compiler in `lex`; move DTR execution to Foundry/Scientist bridge and hierarchical search adapter to Scientist                                                    |
| Reframe Lex simulator                 | Rename or relocate `lex.simulator` to `lex.impact` / `lex.legal_evaluation.impact` with compatibility shims; do not move it wholesale to Foundry                                   |
| Move Foundry release/domain bridges   | Move `foundry.release_acceptance` to `ops/release` or `data_forge.ukraine`; remove Foundry imports of `academic`, `ukraine_data`, and Lex compiler classes                         |
| Invert IR execution dependencies      | Move Foundry/Scientist/Dataset-dependent logic out of `ir.analytics` and `ir.observation`; keep neutral contracts and pure codecs in IR                                            |
| Move Scientist CLI glue out of Core   | Relocate `core/components/_cli_scientist.py` behavior to `tools/scientist/` or `scientist/cli.py`                                                                                  |
| Demote Runtime batch imports          | Replace runtime direct imports of `lex.batch` with Data Forge job/service facades                                                                                                  |
| Tighten packs policy                  | Replace `packs = ["*"]` with explicit package-specific public facade dependencies                                                                                                  |
| Normalize tests after source moves    | Move old-domain tests to `tests/unit/data_forge/**` or keep wrapper tests that assert compatibility imports                                                                             |
| Register generated frontend artifacts | Add `packages/runtime-api-client/**` and `apps/runtime-dashboard/src/api/types.ts` to the generated-artifact registry with regeneration commands                               |

**Validation:** Package import graph has no new reverse edges from Section 2.5,
and all remaining temporary exceptions have owners and sunset phases in
`import_exceptions.toml`.

### 9.9 Phase 6: Artifact and Data Store Normalization

This phase can happen after import cleanup because it changes operational
paths more than Python package paths.

| Task                                | Details                                                                                                                                                        |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Normalize local data roots          | Keep full local datasets in root `data/` or an external object store; organize by `raw/cache/work/snapshots/releases/archives/manifests`                       |
| Shrink `policy-engine/data/`        | Keep only tiny fixtures, gold sets, contracts, registry seeds, README, and manifest templates; move raw WVS and local DBs out                                  |
| Normalize production outputs        | Keep `production_data/` ignored by default as local release cache; add manifest references and logical artifact URIs for reproducible bundles                  |
| Normalize reports                   | Curated reports live in `docs/archive/reports/`; transient reports live in `.polisyos/reports/`                                                                |
| Normalize benchmark outputs         | Benchmark source stays in `benchmarks/`; transient outputs move to `.polisyos/benchmarks/`; curated baselines are registered                                   |
| Normalize frontend outputs          | Keep `node_modules`, `dist`, `coverage`, `storybook-static`, `playwright-report`, and `test-results` ignored/local; route CI artifacts outside the source tree |
| Normalize baselines                 | Keep `baseline/` small and committed, or move to `architecture/baselines/` with updated docs/tool defaults                                                     |
| Normalize temp dirs                 | Route product scratch to `.tmp/` or `.polisyos/tmp/`; root `tmp/` remains local scratch with TTL cleanup                                                       |
| Remove absolute-path-only manifests | Data Forge publish manifests use logical URIs + content hashes; local absolute paths are optional cache hints only                                             |
| Add cleanup command                 | `python -m polisyos.data_forge clean` removes intermediate artifacts by snapshot, domain, or age                                                               |
| Add doctor checks                   | `python -m polisyos.data_forge doctor` warns when large generated outputs appear in product source roots                                                       |

**Validation:** A clean checkout plus documented external artifacts can rebuild
the same golden outputs. Local generated state can be deleted without losing
source-of-truth files.

### 9.10 Timeline

Phases 1+2 and 3+4 can overlap since each domain pipeline is independent:

```text
Week 0:  Phase -1 (topology baseline + explorer/ignore hygiene)      -- sequential, blocking
Week 1:  Phase 0 (foundation + golden snapshots + framework tests)   -- sequential, blocking
Week 2:  Phase 1 (academic) + Phase 2 (catalog)                      -- PARALLEL
Week 3:  Phase 3 (legal) + Phase 4 (ukraine)                         -- PARALLEL
Week 4:  Phase 5 (directory/import cleanup)                          -- sequential, blocking
Week 5:  Phase 6 (artifact/data store normalization)                  -- sequential, can trail
```

### 9.11 Per-Phase PR Checklist

Each phase PR must include:

- [ ] All existing tests pass (old import paths via re-exports)
- [ ] Golden test passes (byte-identical outputs)
- [ ] New unit tests for migrated code
- [ ] `mypy --strict` on new modules (PEP 561 compliance)
- [ ] No circular imports (verified via `importlab` or manual check)
- [ ] Import re-exports added to old locations
- [ ] Directory moves listed in the topology inventory
- [ ] New generated artifacts registered or explicitly ignored
- [ ] No new product source files in repository root
- [ ] CHANGELOG entry added

---

## 10. Testing Strategy

### 10.1 Test Pyramid

```text
                    +-------------+
                    |  E2E Golden  |  1 per pipeline: full run -> compare to golden
                    |  Tests (4)   |  ~30 min each, CI nightly
                    +------+------+
                   +-------+--------+
                   |  Integration   |  Stage combinations: harvest+normalize,
                   |  Tests (~20)   |  extract+graph. Real DuckDB, small corpus.
                   |                |  ~5 min each, CI on PR
                   +-------+--------+
              +------------+------------+
              |     Unit Tests (~100)    |  Per-module: rate_limiter, dedup, hashing,
              |                          |  gate logic, trust scoring, normalizers.
              |                          |  <1s each, CI on every commit
              +------------+-------------+
         +-----------------+-----------------+
         |  Contract / Property Tests (~30)  |  StageContract validation, config
         |                                   |  validation, DAG cycle detection.
         |                                   |  <1s each, CI on every commit
         +-----------------------------------+
```

### 10.2 Missing Unit Tests to Add

| Module                  | Currently Tested? | Tests Needed                                                                                    |
| ----------------------- | ----------------- | ----------------------------------------------------------------------------------------------- |
| `hashing.py`            | Only indirectly   | `test_sha256_file`, `test_sha256_empty_file`, `test_sha256_large_file`                          |
| `thermal.py`            | No                | `test_resolve_profile`, `test_unknown_profile_returns_default`                                  |
| `paths.py`              | No                | `test_snapshot_component_dir_creates`, `test_ensure_dirs`                                       |
| `rate_limiter.py`       | No                | `test_acquire_respects_rate`, `test_backoff_on_429`, `test_concurrent_limit`                    |
| `dedup.py`              | Indirectly        | `test_quality_ranked_replacement`, `test_dedup_key_generation`                                  |
| `llm_gate.py`           | No                | `test_auto_route_high_confidence`, `test_llm_route_low_confidence`                              |
| `batch_snapshot/cli.py` | No                | `test_finalize_snapshot`, `test_missing_pipeline_manifest`                                      |
| DAG orchestrator        | N/A (new)         | `test_cycle_detection`, `test_topo_sort`, `test_contract_validation`, `test_parallel_execution` |

### 10.3 Deterministic Test Fixtures

```python
# data_forge/testing/fixtures.py

@pytest.fixture
def minimal_academic_corpus(tmp_path: Path) -> Path:
    """5 papers with known extraction results for unit testing."""

@pytest.fixture
def minimal_catalog_sources(tmp_path: Path) -> Path:
    """3 sources (worldbank, oecd, ckan) with known datasets."""

@pytest.fixture
def minimal_legal_corpus(tmp_path: Path) -> Path:
    """2 NPA documents with known SPO extraction results."""

@pytest.fixture
def pipeline_config(tmp_path: Path) -> BasePipelineConfig:
    """Minimal config for testing with all paths under tmp_path."""
```

---

## 11. Performance Optimizations

### 11.1 Parallel Stage Execution

Many stages are independent and can run concurrently (see Section 4.4 for identified parallelizable stages). Mark them via `StageContract(parallelizable=True)`. The orchestrator groups stages by DAG level and runs same-level parallelizable stages with `asyncio.gather()`.

### 11.2 DuckDB Parquet Direct Loading

For large stages, write Parquet directly and use DuckDB's native reader (10-100x faster than JSONL row-by-row):

```python
def _load_parquet(self, table: str, source: Path, on_conflict: str) -> int:
    self._con.execute(f"""
        INSERT OR {on_conflict} INTO {table}
        SELECT * FROM read_parquet(?)
    """, [str(source)])
```

**When to apply:** graph_load stages (100k+ works, 40k+ datasets, millions of observations). NOT for small stages (<1000 records).

### 11.3 Lazy Module Imports

`import sentence_transformers` takes ~2s, `import duckdb` takes ~0.5s. CLI startup should be instant for `--help`:

```python
# data_forge/__init__.py
def __getattr__(name: str):
    if name == "run_academic_pipeline":
        from data_forge.academic.pipeline import run_academic_pipeline
        return run_academic_pipeline
    raise AttributeError(f"module 'data_forge' has no attribute {name}")
```

### 11.4 Shard-Based Embedding

The lex pipeline already discovered that large corpora OOM when stacking all vectors in memory. The shard pattern (5000 vectors per NPZ file, then memory-mapped HNSW construction) is the correct approach for all pipelines.

---

## 12. Risk Mitigation

| Risk                                                                | Mitigation                                                                                                                                                               |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Breaking imports**                                                | Phase 0 creates re-export shims; old paths work until Phase 5 directory/import cleanup                                                                                   |
| **Output divergence**                                               | Golden test: snapshot before migration, verify byte-identical outputs after                                                                                              |
| **LLM non-determinism**                                             | Freeze LLM cache for migration testing; compare structure, not exact text                                                                                                |
| **Partial migration failures**                                      | Each phase independently revertable via git; no phase depends on another                                                                                                 |
| **CI pipeline disruption**                                          | Run old and new paths in parallel during migration; switch when green                                                                                                    |
| **Production data path changes**                                    | Source-code moves do not change `production_data/`; any data-store normalization happens separately in Phase 6                                                           |
| **Large PR risk**                                                   | One PR per phase; each PR reviewable in isolation                                                                                                                        |
| **God class decomposition breaks internal contracts**               | Extract into modules within same directory first (move functions, not files). Test at function level before reorganizing files.                                          |
| **Unified gate logic diverges from domain-specific tuning**         | Keep `DomainFeatureExtractor` protocol -- domain-specific weights stay in domain code. Only transport/retry/cache unifies.                                               |
| **Frozen config breaks dynamic stage configuration**                | `dataclasses.replace()` is the escape hatch. `with_overrides(**kw)` convenience method.                                                                                  |
| **Parallel stage execution introduces race conditions**             | Only stages marked `parallelizable=True` run concurrently. Each writes to its own output directory. No shared mutable state.                                             |
| **DuckDB schema migration breaks existing databases**               | Migration is forward-only. `_schema_version` table tracks what's applied. Old DROP IF EXISTS still works for fresh builds.                                               |
| **Thermal profile changes affect benchmark reproducibility**        | Thermal pauses NOT included in `elapsed_seconds`. Only compute time measured.                                                                                            |
| **Directory cleanup deletes useful local evidence**                 | Phase -1 classifies files first; curated evidence moves to `docs/archive/reports/`, local evidence moves to `.polisyos/`                                                 |
| **Ignored source-of-truth docs disappear from review**              | Phase -1 checks `git status --ignored` and adds narrow `.gitignore` exceptions for canonical plans and docs                                                              |
| **Ops files move but automation still points at old paths**         | Phase 5 keeps compatibility wrappers until CI, Docker, docs, and runbooks point at `policy-engine/ops/`                                                                  |
| **Topology registry becomes bureaucracy**                           | Keep `architecture/topology.toml` short: top-level paths plus exceptional generated families only; detailed file inventories stay generated                              |
| **Import policy blocks compatibility shims too early**              | Phase 0 adds `data_forge` without removing old roots; Phase 5 removes old roots only after shims and downstream imports are gone                                         |
| **Fixture policy slows test authoring**                             | Small deterministic fixtures stay easy to add under `tests/<domain>/fixtures/`; only large/live/generated fixtures need registry entries                                 |
| **Loose-file cleanup breaks scripts that import from product root** | Convert files like `jax_bootstrap.py`, `install.sh`, and `migrate.py` into wrappers first; only remove wrappers after docs, tests, and tool registry aliases are updated |
| **Duplicate tool consolidation breaks muscle memory**               | Keep one deprecation cycle of wrapper aliases; print canonical command path in wrapper output                                                                            |
| **Mega-module splits create review churn**                          | Split by extracting private helper modules in-place first, then move packages after tests and imports stabilize                                                          |
| **Frontend generated files drift from backend OpenAPI**             | Register generated clients/types with regeneration command and CI freshness check                                                                                        |
| **Archived evidence contains local absolute paths**                 | Allow local paths only in curated archived evidence; active docs and reference docs must pass the docs accuracy gate                                                     |

---

## 13. Success Metrics

| Metric                                     | Before                                                                                                             | Target                                                                                                       |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------ |
| Shared infra code (LOC)                    | ~500 (batch_common only)                                                                                           | ~4,000 (full framework + scheduler + progress + errors + testing)                                            |
| Domain-specific code (LOC)                 | ~64k with duplication                                                                                              | ~45k (god class decomposition eliminates hidden duplication)                                                 |
| DRY violations (duplicate patterns)        | 11 identified                                                                                                      | 0 structural + 0 behavioral (gate logic, rate limiting unified)                                              |
| Time to add new domain pipeline            | ~2 weeks (copy-paste-modify)                                                                                       | ~1 day (register pipeline + implement stages, framework does rest)                                           |
| Test coverage of pipeline infra            | Ad-hoc per domain                                                                                                  | >90% framework + golden tests for all 4 domains                                                              |
| Artifact lineage                           | Per-domain, inconsistent                                                                                           | Unified lineage.jsonl + content-addressed provenance chain                                                   |
| CLI entry points                           | 4 separate (academic, datasets, lex, ukraine)                                                                      | 1 unified + doctor/validate/diff/clean/config subcommands                                                    |
| DuckDB transaction safety                  | None                                                                                                               | All bulk loads in explicit transactions                                                                      |
| LLM cache hit rate                         | Per-domain caches                                                                                                  | Unified cache across pipelines (~30% cross-domain overlap expected)                                          |
| Resume reliability                         | Mtime-only or none                                                                                                 | Content-addressed + mtime hybrid (correct on NFS/CI)                                                         |
| Mean stage startup time                    | ~3s (import overhead)                                                                                              | <0.5s (lazy imports)                                                                                         |
| Parallel stage speedup                     | 0% (all sequential)                                                                                                | ~25% on academic, ~15% on catalog (independent stages run concurrently)                                      |
| Ambiguous product-root files               | Multiple tracked scripts/reports at repository root                                                                | 0 product source files at root; root remains gateway/control plane only                                      |
| Undocumented top-level directories         | Several overlapping ops/data/artifact homes                                                                        | Every top-level directory has owner, type, target home, and cleanup policy                                   |
| Local artifacts visible in normal IDE tree | Caches, venvs, build outputs, and generated data mixed with source                                                 | Explorer excludes hide generated state; Git ignore rules match artifact policy                               |
| Topology enforcement                       | Mostly prose and convention                                                                                        | `tools/architecture/guardrails.py` validates topology registry in CI                                         |
| Tool/script duplication                    | Maintained logic split across `scripts/`, `tools/ops/cloud`, `tools/ops`, and domain tools                             | `tools/` is canonical; `scripts/` contains only wrappers or is removed                                       |
| Duplicate tool homes                       | Exact duplicate command families across `tools/ops/cloud`, `tools/ops/cloud`, `tools/quality/lint`, `tools/quality/lint`, etc. | One canonical namespace per command family; old homes are wrappers with sunset phase                         |
| Ownership coverage                         | Existing owners cover old roots only                                                                               | `data_forge`, topology, fixtures, and generated artifacts have explicit owners                               |
| Loose top-level files                      | Mixed sentinel files, wrappers, local reports, CSVs, and accidental artifacts                                      | Only explicit sentinels remain loose; all other files move to registered homes or ignored artifact roots     |
| Data-root ambiguity                        | `data/`, `production_data/`, `benchmark-results/`, `baseline/`, and `tmp/` mix raw/input/output/cache roles        | Each data root has a layer, domain, snapshot id, commit policy, and retention rule                           |
| Product-root data bulk                     | `policy-engine/data/` contains ignored raw data and local databases                                                | Product-root data contains only small fixtures, gold sets, contracts, registry seeds, and manifest templates |
| Manifest portability                       | Some manifests rely on machine-local absolute paths                                                                | Published manifests use logical artifact URIs plus sha256; local paths are optional cache hints              |
| Frontend generated state                   | `node_modules`, build outputs, coverage, storybook, and Playwright reports can dominate the tree                   | Generated frontend state is ignored, hidden, and cleanable; tracked generated clients are registered         |
| Python cache noise                         | Thousands of local `__pycache__`/`.pyc` files can appear across source, tests, tools, and benchmarks               | Clean/doctor command removes caches and IDE excludes hide them                                               |

---

## 14. Cross-Module Dependencies (Current)

```text
academic/batch/*       --imports--> batch_common/{manifest, thermal, paths}
academic/batch/*       --imports--> ir.analytics.{literature, context, causal_graph, transportability}
academic/knowledge/*   --imports--> ir.analytics.{literature, transportability}

datasets/batch/*       --imports--> batch_common/{manifest, thermal, paths}
datasets/batch/*       --imports--> academic.knowledge (CANONICAL_VARIABLES, runtime_canonical_registry)
datasets/knowledge/*   --imports--> fabric.connectors (WorldBank, Eurostat, ILO, WHO, etc.)

ukraine_data/*         --imports--> batch_common/{paths, hashing}
ukraine_data/*         --imports--> ir.observation.{contracts, measurement, bundles, governance}
ukraine_data/*         --imports--> foundry.{layout, data_plane, release_acceptance, methods.catalog}
ukraine_data/*         --imports--> scientist.{calibration, governance}
ukraine_data/*         --imports--> core.{artifacts, contracts, registry, canon}

lex/batch/*            --imports--> batch_common/{manifest, paths}
lex/corpus/*           --imports--> fabric.{docs, claims, world}
lex/normpack/*         --imports--> fabric.claims, ir.norm_pack, ir.world
lex/legal_evaluation/* --imports--> core.governance, ir.governance

batch_snapshot/cli.py  --imports--> batch_common.hashing
```

After consolidation, all `batch_common` imports become internal `data_forge.pipeline` / `data_forge.io` imports. Cross-domain imports (e.g., datasets -> academic.knowledge for CANONICAL_VARIABLES) become `data_forge.catalog` -> `data_forge.academic.knowledge` -- same package, cleaner path.
