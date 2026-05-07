# PolicyOS Data Storage Migration Audit — 2026-05-01

Status: planning only. No data was moved or deleted during this audit.

Purpose:

- identify local and cloud data related to PolicyOS;
- separate production/runtime data from archives, intermediate artifacts, caches,
  and temporary experiment outputs;
- define what should be preserved before implementing
  `REPOSITORY_SOTA_PLAN.md` and `DATA_FORGE_CONSOLIDATION_PLAN.md`;
- prepare a safe path toward a thin local checkout with heavy data in cloud
  storage.

## Executive Summary

The local workspace currently holds roughly **47 GB** under
`/Users/deniskopylov/polisyos`, plus roughly **19 GB** of relevant data in
`/Users/deniskopylov/Downloads`.

The active GCP project is:

- Project: `lex-1-494208`
- Active account: `repairkyiv4@gmail.com`
- Main GCS bucket: `gs://lex-1-494208-data`
- Active VM: `msme-exp-main-20260430`
- Active VM disk: `240 GB pd-ssd`, currently about `146 GB` used

The most important keepers are:

- final Lex graph with amendment enrichment:
  `gs://lex-1-494208-data/finalize/lex-amendment-only-optimized-20260501-v3`
- local final experiment export:
  `/Users/deniskopylov/polisyos/tmp/msme_final_experiments_export_2026-05-01`
- production runtime data:
  `/Users/deniskopylov/polisyos/policy-engine/production_data`
- source NPA XML:
  `/Users/deniskopylov/polisyos/data/data_lex`
  and/or `/Users/deniskopylov/Downloads/edrnpa_*_2026-04-05.xml`
- historical Lex output:
  `/Users/deniskopylov/polisyos/tmp/history_local_gentle`
- queue-based Lex output backup:
  `/Users/deniskopylov/Downloads/lex_output_backup_2026-04-23`

The most likely cleanup candidates after cloud verification are:

- Python and frontend dependency folders (`.venv`, `.venv_codex`,
  `node_modules`);
- build/test caches (`.mypy_cache`, `.pytest_cache`, `.ruff_cache`,
  `.hypothesis`, Playwright reports, coverage);
- old GCP repo tarballs under `/Users/deniskopylov/polisyos/tmp/gcp_bundle`;
- failed or superseded amendment-finalize runs after confirming that the v3
  finalized bundle is preserved.

## Local Data Inventory

### Workspace Root

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `/Users/deniskopylov/polisyos` | 47 GB | Full local workspace | Keep code locally; move heavy data to cloud-backed layout. |
| `/Users/deniskopylov/polisyos/data` | 21 GB | Heavy data/archive layer | Preserve in cloud; keep local only as thin manifests/pointers. |
| `/Users/deniskopylov/polisyos/policy-engine` | 14 GB | Code + data + envs | Keep code; remove/rebuild envs and move heavy data. |
| `/Users/deniskopylov/polisyos/tmp` | 11 GB | Mixed experiment/tmp outputs | Preserve selected outputs, then clean temporary residue. |
| `/Users/deniskopylov/polisyos/.venv` | 608 MB | Rebuildable environment | Do not archive; can be deleted/rebuilt. |
| `/Users/deniskopylov/polisyos/.venv-spatial-tests` | 70 MB | Rebuildable environment | Do not archive. |
| `/Users/deniskopylov/polisyos/.mypy_cache` | 196 MB | Cache | Delete after migration. |
| `/Users/deniskopylov/polisyos/.git` | 223 MB | Source control | Keep locally; not data archive. |

### Policy Engine

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `/Users/deniskopylov/polisyos/policy-engine/production_data` | 7.4 GB | Production runtime data | Preserve. Candidate for cloud object storage + local manifest. |
| `/Users/deniskopylov/polisyos/policy-engine/data` | 1.4 GB | Raw/support data | Preserve useful raw data; move to cloud-backed data root. |
| `/Users/deniskopylov/polisyos/policy-engine/.venv` | 1.7 GB | Rebuildable environment | Do not archive. |
| `/Users/deniskopylov/polisyos/policy-engine/.venv_codex` | 1.2 GB | Rebuildable environment | Do not archive. |
| `/Users/deniskopylov/polisyos/policy-engine/frontend` | 862 MB | Frontend mostly dependencies | Keep source; do not preserve `node_modules`. |
| `/Users/deniskopylov/polisyos/policy-engine/apps/runtime-dashboard/node_modules` | 821 MB | Rebuildable dependency cache | Delete/rebuild via package manager. |
| `/Users/deniskopylov/polisyos/policy-engine/.mypy_cache` | 530 MB | Cache | Delete. |
| `/Users/deniskopylov/polisyos/policy-engine/src` | 85 MB | Code | Keep in git. |
| `/Users/deniskopylov/polisyos/policy-engine/tests` | 68 MB | Tests | Keep in git. |
| `/Users/deniskopylov/polisyos/policy-engine/docs` | 11 MB | Docs | Keep in git. |

### `production_data`

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `production_data/policyos_academic_runtime_slim_20260411T112032Z` | 3.2 GB | Academic runtime bundle | Preserve. Useful for Fabric/evidence experiments. |
| `production_data/ukraine_agent_simulation_baseline_20260410` | 1.3 GB | Agent-simulation baseline | Preserve. Useful for Foundry/agent simulation. |
| `production_data/dataset_catalog.duckdb` | 1.2 GB | Dataset graph/catalog | Preserve. |
| `production_data/all_records.jsonl` | 725 MB | Dataset records | Preserve. |
| `production_data/ds_dataset_index.hnsw` | 555 MB | Rebuildable but expensive index | Preserve if cheap; otherwise can be regenerated from embeddings/records. |
| `production_data/ds_dataset_embeddings.npz` | 539 MB | Dataset embeddings | Preserve. |

This directory is production-useful and should not be treated as disposable.
It is a prime candidate for cloud storage with local pointer manifests.

### Local `data`

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `/Users/deniskopylov/polisyos/data/policyos_academic_archive_20260411T112032Z` | 13 GB | Academic archive / heavy source bundle | Preserve in cloud archive; local copy can be removed after verification. |
| `/Users/deniskopylov/polisyos/data/ukraine_server_support_20260410` | 4.1 GB | Ukraine simulation/server support | Preserve in cloud; local copy optional after manifesting. |
| `/Users/deniskopylov/polisyos/data/data_lex` | 3.7 GB | Source Lex/NPA XML + pre-shards | Preserve. This is raw/legal provenance. |
| `/Users/deniskopylov/polisyos/data/lex_knowledge` | 296 MB | Lex knowledge output/support | Preserve if not superseded by final GCS bundle. |
| `/Users/deniskopylov/polisyos/data/academic_fulltext_cache` | 18 MB | Cache | Optional. |
| `/Users/deniskopylov/polisyos/data/fulltext_shared_cache` | 23 MB | Cache | Optional. |

Large files include:

- `data/data_lex/edrnpa_texts_2026-04-05.xml` — 3.1 GB
- `data/policyos_academic_archive_20260411T112032Z/academic/fulltext_resolved.jsonl` — 3.4 GB
- `data/policyos_academic_archive_20260411T112032Z/academic/topic_selection/selected_topic_works.jsonl` — 3.2 GB
- `data/policyos_academic_archive_20260411T112032Z/academic/topic_selection/selected_global_works.jsonl` — 2.7 GB
- `data/ukraine_server_support_20260410/normalized_corpus/normalized/spending_full/budget_flows_monthly_sparse.parquet` — 1.7 GB

### Local `tmp`

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `/Users/deniskopylov/polisyos/tmp/history_local_gentle` | 6.6 GB | Historical Lex deterministic output | Preserve until fully merged into final Lex graph and cloud-verified. |
| `/Users/deniskopylov/polisyos/tmp/gcp_bundle` | 2.9 GB | Old deployment tarballs | Likely disposable after code is in git/cloud. |
| `/Users/deniskopylov/polisyos/tmp/priority_manifests` | 932 MB | Queue/shard manifests | Preserve as provenance until final Lex manifest is accepted. |
| `/Users/deniskopylov/polisyos/tmp/gcs_upload_logs` | 96 MB | Transfer logs | Keep short-term; archive small subset if needed. |
| `/Users/deniskopylov/polisyos/tmp/msme_final_experiments_export_2026-05-01` | 47 MB | Final thesis experiment export | Preserve. Already suitable for Google Drive. |
| `/Users/deniskopylov/polisyos/tmp/msme_final_experiments_export_2026-05-01.zip` | 17 MB | Compressed final experiment export | Preserve/share. |

`history_local_gentle` breakdown:

- `provisions` — 2.2 GB
- `spo_grounded` — 2.1 GB
- `spo_results` — 2.0 GB
- `domains` — 149 MB
- `resolved_references` — 36 MB

### Downloads

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `/Users/deniskopylov/Downloads/lex_output_backup_2026-04-23` | 16 GB | Queue 1/2 Lex backup | Preserve until final GCS bundle and final graph are verified. |
| `/Users/deniskopylov/Downloads/edrnpa_texts_2026-04-05.xml` | 3.1 GB | Source NPA texts | Preserve if not already duplicated in `data/data_lex`. |
| `/Users/deniskopylov/Downloads/edrnpa_cards_2026-04-05.xml` | 162 MB | Source NPA cards | Preserve if not already duplicated in `data/data_lex`. |
| Misc small PolicyOS/docx/design files | < 1 MB each | Documents/design references | Keep separately if needed, not part of heavy data migration. |

`lex_output_backup_2026-04-23` breakdown:

- `queue2_fast_useful_current` — 8.7 GB
- `queue1_core_current_remaining` — 6.8 GB
- `_logs` — 878 MB
- `queue3_wave1_state_core_current` — 34 MB

## Cloud Inventory

### GCP Project and Compute

| Resource | Current State | Recommendation |
| --- | --- | --- |
| Project | `lex-1-494208` | Active project for current data. |
| Bucket | `gs://lex-1-494208-data` | Main cloud archive. |
| VM | `msme-exp-main-20260430` | Still running. Stop/delete only after final data verification. |
| VM disk | 240 GB `pd-ssd`, 146 GB used | Contains cloud working copies and superseded intermediate runs. |

VM `/mnt/experiments` currently uses about **141 GB**:

| Path | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `/mnt/experiments/msme_deadline_20260430` | 46 GB | Experiment input/workdir | Preserve only if not already in GCS/local production data. |
| `/mnt/experiments/lex-amendment-only-optimized-20260501` | 36 GB | Older amendment run | Superseded by v3; keep only until verified. |
| `/mnt/experiments/lex-amendment-only-optimized-20260501-v3` | 21 GB | Final amendment-enriched Lex graph | Preserve; already uploaded to GCS. |
| `/mnt/experiments/lex-amendment-only-optimized-20260501-v2` | 19 GB | Superseded amendment run | Cleanup candidate after verification. |
| `/mnt/experiments/lex-amendment-parallel-20260430` | 19 GB | Superseded amendment run | Cleanup candidate after verification. |
| `/mnt/experiments/polisyos` | 1.9 GB | Cloud code checkout | Rebuildable from git. |
| MSME experiment dirs | ~8–42 MB each | Final experiment outputs | Already exported locally; preserve compact GCS copies. |

### GCS Bucket: `gs://lex-1-494208-data`

Top-level prefixes:

- `bootstrap/`
- `experiments/`
- `finalize/`
- `finalize_inputs/`
- `input/`
- `output/`

Known measured GCS sizes:

| Prefix | Size | Classification | Recommendation |
| --- | ---: | --- | --- |
| `finalize/lex-amendment-only-optimized-20260501-v3` | 21.4 GB | Final Lex graph with amendment enrichment | Keep as canonical final Lex output. |
| `finalize/lex-finalize-20260429` | 49.2 GB | Older full finalize bundle | Preserve short-term; likely superseded by v3 after validation. |
| `finalize/lex-amendment-optimized-20260501` | 917 MB | Incomplete/smaller amendment run | Cleanup candidate after validation. |
| `finalize/lex-amendment-parallel-20260430` | 101 MB | Early/partial amendment run | Cleanup candidate after validation. |
| `experiments/msme_deadline_20260430` | 8.7 GB | Experiment work inputs/results | Preserve until thesis archive is complete. |
| `experiments/msme_causal_discovery_addendum_20260501` | 40 MB | Final discovery addendum | Preserve. |
| `experiments/msme_final_fresg_evaluation_v3_20260501` | 18 MB | Final v3 experiment | Preserve. |
| `experiments/msme_final_fresg_evaluation_v2_20260501` | 33 MB | Older experiment run | Optional archive. |
| `experiments/msme_final_fresg_evaluation_20260501` | 17 MB | Older experiment run | Optional archive. |
| `input/source_xml` | 3.46 GB | Source NPA XML in cloud | Keep. |
| `input/priority_manifests` | 301 MB | Queue/shard manifests | Keep as provenance until final Lex manifest accepted. |
| `input/pre_sharded` | tiny measured marker | Pre-shard prefix | Verify if expected objects are elsewhere. |
| `bootstrap/repo` | 6 MB | Bootstrap repo payload | Rebuildable; optional. |
| `output/priority-apr30-mixed-q3waves-5x6` | 35 MB | Deterministic queue output | Keep until merged/verified. |
| `output/lex1-rescue-20260429` | 3.5 MB | Rescue output | Keep until merged/verified. |

Some `output/*` and `finalize_inputs/local_seed_20260428` prefixes have many
objects and metadata scanning was intentionally stopped after it took too long.
Their directory listing shows:

- `finalize_inputs/local_seed_20260428/history_local_gentle/`
- `finalize_inputs/local_seed_20260428/lex_output_backup_2026-04-23/`
- `output/lex1-resume-20260423/current/`
- `output/lex1-missing-deterministic-20260429/current/`
- `output/priority-apr30-mixed/current/`

For cleanup decisions, these should be treated as **preserve until compacted and
manifested**, because they may contain provenance for the final Lex graph.

## Data Classes and Migration Policy

### Class A — Must Preserve

These are needed for reproducibility, production usage, or legal/data
provenance:

- final Lex graph:
  `gs://lex-1-494208-data/finalize/lex-amendment-only-optimized-20260501-v3`
- source NPA XML:
  `data/data_lex`, `Downloads/edrnpa_*_2026-04-05.xml`,
  `gs://lex-1-494208-data/input/source_xml`
- `policy-engine/production_data`
- `data/ukraine_server_support_20260410`
- final MSME experiment export and GCS experiment outputs
- manifests/checksums associated with each final artifact

### Class B — Preserve Temporarily, Then Compact

These are useful until final bundles are verified, but should not remain as
loose local data forever:

- `Downloads/lex_output_backup_2026-04-23`
- `tmp/history_local_gentle`
- `tmp/priority_manifests`
- `gs://lex-1-494208-data/finalize_inputs/local_seed_20260428`
- `gs://lex-1-494208-data/output/*`
- old GCS `finalize/*` runs superseded by v3

Recommended action: create compact tar/zstd or zip archives with checksums,
store in cloud, then remove local loose copies.

### Class C — Rebuildable / Cleanup Candidates

These should not be moved to Google Drive as project data:

- Python virtual environments:
  `.venv`, `.venv_codex`, `.venv-spatial-tests`
- Node dependencies:
  `apps/runtime-dashboard/node_modules`
- type/test caches:
  `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `.hypothesis`
- Playwright/storybook/coverage outputs if not needed for reports
- old cloud deployment tarballs:
  `tmp/gcp_bundle/policy-engine-20260409-*.tar.gz`

### Class D — Archive but Not Production

These are valuable historically but should not be kept in the hot local tree:

- `data/policyos_academic_archive_20260411T112032Z`
- old MSME v1/v2 experiment outputs
- old amendment-finalize attempts after v3 acceptance

## Recommended Target Layout

Use cloud object storage for heavy machine-readable data and Google Drive for
human-facing archives/reports.

Suggested cloud storage layout:

```text
gs://lex-1-494208-data/
  canonical/
    lex/
      edrnpa_2026-04-05_source_xml/
      final_amendment_enriched_2026-05-01/
    production_data/
      policyos_production_data_2026-05-01/
    experiments/
      msme_final_2026-05-01/
  archive/
    lex_intermediate_queues_2026-04/
    academic_archive_2026-04-11/
    superseded_finalize_runs/
  manifests/
    checksums/
    inventories/
    migration_reports/
```

Suggested Google Drive layout:

```text
PolicyOS Data Archive/
  00_README_AND_MANIFESTS/
  01_FINAL_EXPERIMENT_RESULTS/
  02_LEX_FINAL_REPORTS_AND_POINTERS/
  03_PRODUCTION_DATA_POINTERS/
  04_ARCHIVE_POINTERS/
```

Google Drive should hold compact reports, manifests, zip exports, and pointers.
It should not be the only home for multi-GB machine-readable datasets if GCS is
available, because GCS is better for resumable sync, checksums, and future cloud
compute access.

## Proposed Migration Plan

1. Freeze current state:
   - create a migration manifest with paths, sizes, timestamps, and SHA256 for
     small/medium files;
   - for very large files, record size and existing artifact checksums where
     already available.

2. Promote final cloud artifacts:
   - mark `finalize/lex-amendment-only-optimized-20260501-v3` as canonical Lex
     final output;
   - keep `lex-finalize-20260429` as rollback archive until downstream tests
     pass with v3.

3. Move local heavy-but-useful data to cloud-backed canonical/archive prefixes:
   - `policy-engine/production_data`
   - `data/data_lex`
   - `data/ukraine_server_support_20260410`
   - `data/policyos_academic_archive_20260411T112032Z`
   - `Downloads/lex_output_backup_2026-04-23`
   - `tmp/history_local_gentle`

4. Put only thin local pointers in the repository:
   - `data/README.md`
   - `data/MANIFEST.json`
   - `data/.gitkeep`
   - cloud URI pointer files per dataset

5. Verify:
   - compare object counts and total bytes;
   - sample SHA256 for critical artifacts;
   - run a smoke test that reads production data from the new cloud-backed
     layout or from a local cache restored from it.

6. Clean local rebuildable data:
   - remove virtualenvs, node modules, caches, old gcp bundles;
   - keep code, docs, manifests, and small fixtures.

7. Stop/delete cloud VM only after:
   - v3 finalize bundle is verified in GCS;
   - no unique files remain only on `/mnt/experiments`;
   - migration manifest is saved locally and in cloud.

## Immediate Next Checks Before Moving Anything

- Generate exact object counts for GCS prefixes that were too slow to scan:
  `finalize_inputs/local_seed_20260428` and large `output/*`.
- Compare local `history_local_gentle` and `lex_output_backup_2026-04-23`
  against their GCS copies.
- Decide whether `finalize/lex-finalize-20260429` should remain as rollback
  archive or be replaced entirely by v3.
- Create a single machine-readable migration manifest before any deletion.
- Confirm Google Drive target folder and quota if Drive will also receive
  compact archives.
