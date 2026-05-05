# PolicyOS GCS Gap Audit — 2026-05-01

Status: planning + upload queue.

This audit identifies useful local PolicyOS data that is not clearly present in
the active GCS bucket, or is present only as part of an experiment-specific
prefix and should be referenced from canonical/archive manifests.

Active GCS bucket:

`gs://lex-1-494208-data`

## Already Present In GCS

These should not be uploaded again from the laptop unless a later verification
finds corruption or incompleteness:

| Data | Local source | GCS evidence | Decision |
| --- | --- | --- | --- |
| Final Lex graph with amendment enrichment | VM/local finalize outputs | `gs://lex-1-494208-data/finalize/lex-amendment-only-optimized-20260501-v3` | Keep as canonical final Lex output. |
| Source NPA XML | `data/data_lex/edrnpa_*_2026-04-05.xml` | `gs://lex-1-494208-data/input/source_xml/` | Already present. |
| Local history Lex output | `tmp/history_local_gentle` | `gs://lex-1-494208-data/finalize_inputs/local_seed_20260428/history_local_gentle/` | Already present; stopped Drive duplicate upload. |
| Queue 1/2 Lex backup | `Downloads/lex_output_backup_2026-04-23` | `gs://lex-1-494208-data/finalize_inputs/local_seed_20260428/lex_output_backup_2026-04-23/` | Already present. |
| Production runtime data | `policy-engine/production_data` | `gs://lex-1-494208-data/experiments/msme_deadline_20260430/input/production_data/` (~8.0 GB) | Already present, but upload a pointer manifest to canonical data. |
| Final MSME experiment outputs | `tmp/msme_final_experiments_export_2026-05-01` | `gs://lex-1-494208-data/experiments/msme_final_fresg_evaluation_v3_20260501/` and discovery addendum prefix | Already present; keep local/Drive export as human-facing bundle. |

## Missing Or Not Clearly Present In GCS

These should be uploaded to GCS because they are useful for reproducibility,
future Data Forge consolidation, or raw/source provenance.

| Local path | Size | Proposed GCS prefix | Why preserve |
| --- | ---: | --- | --- |
| `policy-engine/data/raw/wvs` | 1.3 GB | `gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/raw/wvs/` | Raw WVS input; useful for rebuilding and validating dataset ingestion. |
| `policy-engine/data/raw/benchmarks` | 94 MB | `gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/raw/benchmarks/` | Benchmark fixtures/data. |
| `policy-engine/data/databases` | 16 MB | `gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/databases/` | Small local DB assets. |
| `policy-engine/data/dataset_catalog` | 172 KB | `gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/dataset_catalog/` | Thin catalog fixtures. |
| `policy-engine/data/curated` | 44 KB | `gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/curated/` | Curated fixtures. |
| `policy-engine/data/academic_gold` | 28 KB | `gs://lex-1-494208-data/canonical/local_data_20260501/policy_engine_data/academic_gold/` | Gold examples/tests. |
| `data/data_lex/pre_sharded` | 450 MB | `gs://lex-1-494208-data/canonical/local_data_20260501/lex/pre_sharded_2026-04-05/` | Shard manifests/input splits; source XML is in GCS, but local pre-shards were not clearly present. |
| `data/lex_knowledge` | 296 MB | `gs://lex-1-494208-data/canonical/local_data_20260501/lex/lex_knowledge_local/` | Older/local Lex knowledge support; possibly superseded, but useful as provenance. |
| `data/ukraine_server_support_20260410` | 4.1 GB | `gs://lex-1-494208-data/canonical/local_data_20260501/ukraine_server_support_20260410/` | Useful simulation/server-support data not fully represented by `production_data`. |
| `data/policyos_academic_archive_20260411T112032Z` | 13 GB | `gs://lex-1-494208-data/archive/local_data_20260501/policyos_academic_archive_20260411T112032Z/` | Full academic archive; production slim bundle exists, but full archive is valuable for rebuilds. |
| `data/academic_fulltext_cache` | 18 MB | `gs://lex-1-494208-data/archive/local_data_20260501/academic_fulltext_cache/` | Optional cache, small enough to keep. |
| `data/fulltext_shared_cache` | 23 MB | `gs://lex-1-494208-data/archive/local_data_20260501/fulltext_shared_cache/` | Optional shared cache, small enough to keep. |
| `data/academic_empirical_topics_20260313` | 8 KB | `gs://lex-1-494208-data/archive/local_data_20260501/academic_empirical_topics_20260313/` | Tiny provenance directory. |

## Upload Policy

- Use `gcloud storage rsync --recursive --continue-on-error`.
- Do not delete source or destination data.
- Do not re-upload known duplicate heavy outputs:
  `history_local_gentle`, `lex_output_backup_2026-04-23`,
  source XML, final Lex v3, or production data.
- Upload manifests/docs under:
  `gs://lex-1-494208-data/manifests/data_migration_20260501/`.

## Follow-Up Verification

After upload:

- compare top-level byte counts with local `du`;
- list destination prefixes;
- sample a few large files with `gcloud storage hash`;
- keep local copies until verification passes.
