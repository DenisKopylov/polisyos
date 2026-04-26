---
title: Repository SOTA Phase -1 Inventory
status: report
owner: team-polisyos
created: 2026-04-24
last_verified: 2026-04-24
stability: snapshot
---

# Repository SOTA Phase -1 Inventory

This is the read-only Phase -1 inventory for
`docs/plans/active/REPOSITORY_SOTA_PLAN.md` under the temporary conservative
overlay. It records current repository facts before any structural moves. It is
not a remediation plan and does not authorize changes to protected Lex/cloud
production surfaces.

## Snapshot

| Field | Value |
| ----- | ----- |
| Date | 2026-04-24 |
| Branch | `main` |
| HEAD | `057ed6cb` |
| Mode | Conservative overlay / read-only inventory |

The working tree was already dirty during collection. Observed non-inventory
changes included active Data Forge files, the Data Forge plan, the Repository
SOTA plan, a public API facade test, and the moved lint/format plan. This report
does not classify or modify those changes.

## Freeze Boundary

Protected production surfaces observed in place:

| Surface | Inventory |
| ------- | --------- |
| `src/polisyos/lex/batch` | 57 files |
| `src/polisyos/batch_common` | 8 files |
| `src/polisyos/batch_snapshot` | 3 files |
| `tools/ops/cloud` | 41 files |
| `tools/cloud` | 40 compatibility-wrapper files |
| `tools/ops/ukraine_data/pre_shard_lex_corpus.py` | active file |
| `tools/ukraine_data/pre_shard_lex_corpus.py` | compatibility wrapper |

No inventory action moved, rewrote, deleted, or ran these surfaces.

## Topology Inventory

Existing machine-readable architecture contracts:

- `architecture/topology.toml`
- `architecture/package_boundaries.toml`
- `architecture/import_contracts.toml`
- `architecture/migration_shims.toml`
- `architecture/complexity_exceptions.toml`
- `architecture/generated_artifacts.toml`
- `architecture/public_surface.toml`
- `architecture/public_surface_inventory.json`
- `architecture/deep_import_baseline.json`
- `schemas/topology/*.schema.json`

Immediate topology comparison against `architecture/topology.toml` path entries:

| Scope | Registered path entries | Actual immediate entries | Notes |
| ----- | ----------------------- | ------------------------ | ----- |
| repo root | 19 | 40 | Several loose files are governed by loose-file allow/deny lists rather than path entries. |
| product root | 47 | 94 | Product root contains expected targets plus legacy wrappers, local outputs, caches, and loose files. |

Target product-root directories already present:

- `architecture/`
- `schemas/`
- `docs/`
- `src/`
- `tests/`
- `tools/`
- `ops/`
- `frontend/`
- `benchmarks/`
- `release/`
- `release-fragments/`
- `data/`
- `.polisyos/`

Notable topology observations:

- `policy-engine/packs` is registered in topology but is not present as a
  product-root directory; `src/polisyos/packs` exists and currently has no
  source files.
- Legacy wrapper/topology-migration paths are present: `cloud_deploy/`,
  `deploy/`, `docker/`, `gcp/`, and `scripts/`.
- Root loose-file pressure matches the planned Phase -1.5 work:
  `compileall.txt`, `import_gate.txt`, `ruff_stats.txt`, `summary.json`,
  `test_collect.txt`, `stale_sources_missing_paths.txt`, `topics.csv`,
  `filter_topics.py`, `organize_relevant_topics.py`, and
  `scm-implementation-spec-v3.md`.
- Product-root loose-file pressure includes `=2.5.0`, `.DS_Store`,
  `env_example.txt`, `all_1000_policy_topics.csv`, and 18
  `audit_R_recover_*.polisyos-audit.tar.gz` bundles.

## Source Package Inventory

Python file counts under `src/polisyos`:

| Package | Python files | Markdown files | Other files |
| ------- | ------------ | -------------- | ----------- |
| `academic` | 59 | 4 | 0 |
| `batch_common` | 7 | 1 | 0 |
| `batch_snapshot` | 2 | 1 | 0 |
| `calibration` | 7 | 0 | 0 |
| `common` | 11 | 2 | 0 |
| `core` | 185 | 12 | 2 |
| `data_forge` | 36 | 1 | 1 |
| `datasets` | 28 | 3 | 1 |
| `fabric` | 266 | 8 | 6 |
| `foundry` | 476 | 12 | 3 |
| `ir` | 179 | 10 | 3 |
| `lex` | 95 | 7 | 1 |
| `packs` | 0 | 0 | 0 |
| `runtime` | 49 | 4 | 2 |
| `scholar` | 24 | 3 | 1 |
| `scientist` | 446 | 16 | 4 |
| `synthetic_world` | 31 | 1 | 4 |
| `ukraine_data` | 10 | 0 | 0 |

## Import Graph Inventory

The AST import scan parsed all Python files under `src/polisyos` with zero parse
errors. This scan counted direct `polisyos.*` imports by top-level package. It
is an inventory, not an enforcement result.

Highest internal-import sources:

| Source | Internal imports |
| ------ | ---------------- |
| `scientist` | 2740 |
| `foundry` | 1991 |
| `fabric` | 1055 |
| `ir` | 575 |
| `lex` | 422 |
| `runtime` | 299 |
| `core` | 292 |
| `academic` | 225 |
| `scholar` | 103 |
| `datasets` | 99 |

High-volume cross-package edges:

| Source | Target | Count |
| ------ | ------ | ----- |
| `scientist` | `core` | 650 |
| `foundry` | `ir` | 485 |
| `scientist` | `ir` | 375 |
| `foundry` | `core` | 323 |
| `fabric` | `core` | 248 |
| `fabric` | `ir` | 180 |
| `runtime` | `core` | 130 |
| `scientist` | `foundry` | 104 |
| `scientist` | `common` | 93 |
| `lex` | `ir` | 74 |
| `lex` | `core` | 64 |
| `fabric` | `common` | 61 |
| `scholar` | `core` | 38 |
| `lex` | `fabric` | 34 |
| `core` | `common` | 31 |

Edges to treat as report-only review candidates before fail-closed gates:

- `runtime -> scientist`, `runtime -> fabric`, `runtime -> foundry`, and
  `runtime -> lex` are present.
- `scientist -> lex`, `scientist -> academic`, `scientist -> datasets`, and
  `scientist -> runtime` are present.
- `ir -> foundry`, `ir -> scientist`, and `ir -> datasets` are present.
- `core -> scientist` is present.
- `batch_common` is still imported by `academic`, `datasets`, `lex`,
  `ukraine_data`, and `batch_snapshot`.

These observations match the current migration window and should remain
report-only while protected Lex/shared-batch paths are frozen.

## Tools Inventory

The tools surface already has a zoned registry in `tools/registry.py`:

| Zone | Categories |
| ---- | ---------- |
| `devx` | `workspace`, `architecture`, `connectors`, `foundry` |
| `quality` | `lint`, `diagnostics`, `validation`, `testing`, `ci` |
| `ops` | `cloud`, `release`, `migrations`, `runtime`, `data`, `ukraine_data`, `calibration` |
| `research` | `benchmarks`, `demos` |

Top-level tool file counts show both canonical zoned packages and compatibility
packages:

| Path | Files |
| ---- | ----- |
| `tools/ops` | 83 |
| `tools/quality` | 64 |
| `tools/devx` | 42 |
| `tools/cloud` | 40 |
| `tools/research` | 32 |
| `tools/workspace` | 21 |
| `tools/benchmarks` | 22 |
| `tools/ukraine_data` | 12 |
| `tools/data` | 6 |

Notable duplicate surfaces:

- `tools/cloud/*` mirrors `tools/ops/cloud/*`; both must remain stable during
  the Lex production freeze.
- `tools/ukraine_data/*` mirrors `tools/ops/ukraine_data/*`, including
  `pre_shard_lex_corpus.py`.
- `tools/data/*` mirrors `tools/ops/data/*`.
- `tools/workspace/*` mirrors `tools/devx/workspace/*`.
- `tools/benchmarks/*` mirrors `tools/research/benchmarks/*`.
- `tools/lint`, `tools/diagnostics`, `tools/validation`, `tools/testing`, and
  `tools/ci` mirror `tools/quality/*` categories.

The duplicate inventory supports future topology cleanup, but no wrapper should
be removed or tightened while queued cloud jobs may still depend on it.

## Data-Root Inventory

Root `data/` is a local lake-like workspace today:

| Entry | Inventory |
| ----- | --------- |
| `data/data_lex` | 4 dirs, 15 files; includes `pre_sharded/2026-04-05` |
| `data/lex_knowledge` | 524 dirs, 6328 files; includes `_shards/shard_00_of_05` through `shard_04_of_05`, `provisions/`, and `spo_results/` |
| `data/policyos_academic_archive_20260411T112032Z` | 13 dirs, 79 files |
| `data/ukraine_server_support_20260410` | 35 dirs, 66 files |
| `data/academic_fulltext_cache` | 1 file |
| `data/fulltext_shared_cache` | 1 file |
| `data/academic_empirical_topics_20260313` | 1 file |

Product-root `policy-engine/data/` is mixed fixture/demo data:

| Entry | Inventory |
| ----- | --------- |
| `README.md` | present |
| `academic_gold` | 4 files |
| `curated` | 11 files |
| `databases` | 8 DuckDB/Kuzu demo/test databases |
| `dataset_catalog` | 4 files |
| `raw` | 11 dirs, 45 files |

Product-root `policy-engine/production_data/` contains large local runtime
artifacts and should remain local/ignored:

| Entry | Size / inventory |
| ----- | ---------------- |
| `all_records.jsonl` | 760,531,505 bytes |
| `dataset_catalog.duckdb` | 1,320,693,760 bytes |
| `ds_dataset_embeddings.npz` | 565,029,308 bytes |
| `ds_dataset_index.hnsw` | 582,241,124 bytes |
| `policyos_academic_runtime_slim_20260411T112032Z` | 5 dirs, 21 files |
| `ukraine_agent_simulation_baseline_20260410` | 10 dirs, 41 files |

Local output/cache surfaces observed:

- Repo root: `output/`, `runs/`, `tmp/`, `.benchmarks/`, `.tmp/`,
  `.pytest_cache/`, `.ruff_cache/`, `.mypy_cache/`, `.hypothesis/`, `.venv/`,
  and `.venv-spatial-tests/`.
- Product root: `runs/`, `tmp/`, `logs/`, `out/`, `dist/`, `site/`,
  `benchmark-results/`, `.benchmarks/`, `.tmp/`, `.cache/`, `.pytest_cache/`,
  `.ruff_cache/`, `.mypy_cache/`, `.hypothesis/`, `.uv-cache/`, `.venv/`,
  `.venv_codex/`, and `.tmp_c7_venv/`.

## Safe Next Steps

These are safe under the conservative overlay:

1. Add a report-only topology inventory command or documented manual command
   that compares actual paths against `architecture/topology.toml` plus
   `loose_files.*`.
2. Add or refresh import graph evidence in report-only mode, without changing
   `import_contracts.toml` enforcement for protected paths.
3. Classify root loose files and product-root audit bundles for Phase -1.5, but
   do not move active Lex queue assets or deploy assets.
4. Classify `data/lex_knowledge`, `data/data_lex`, and cloud deploy assets as
   freeze-protected until Queue 2 and Queue 3 Waves 1-5 complete and pass
   merge/QC.
5. Prepare docs-only mapping for legacy tools and ops paths; defer physical
   moves and wrapper removals until the overlay ends.

## Deferred Actions

Do not perform these during the overlay:

1. Move or rename `src/polisyos/lex/batch`, `src/polisyos/batch_common`,
   `src/polisyos/batch_snapshot`, `tools/ops/cloud`, `tools/cloud`, or
   `tools/*ukraine_data*/pre_shard_lex_corpus.py`.
2. Rewrite active cloud runner imports to Data Forge paths.
3. Change production manifest schemas, output layouts, resume markers, cache
   keys, idempotency keys, or cleanup behavior.
4. Remove compatibility wrappers that queued cloud jobs may still call.
5. Turn topology/import/generated/complexity gates fail-closed for protected
   paths.
