# Fabric Profiles
Related explanation: [Data Fabric](../../explanation/data-fabric.md).

`SourceProfile` describes a source endpoint in planner-friendly terms, while `SourceExecutionPolicy` is the normalized runtime subset used by schedulers, capability caches, and backfill planning.

## Key Fields

| Field | Semantics |
|-------|-----------|
| `max_concurrency` | Maximum simultaneous requests the source should see |
| `requests_per_hour` | Coarse quota ceiling for low-rate APIs |
| `preferred_core_transport` | Preferred transport for regular online workloads |
| `preferred_backfill_transport` | Preferred transport for bulk or historical backfills |
| `supports_async_large_responses` | Whether the source has a safe async path for large payloads |
| `supports_async_fetch` | Whether planners may choose an async fetch mode at all |
| `schema_preflight` | Whether metadata / structure should be validated before fetch |
| `supports_content_constraints` | Whether dataset content constraints can be probed explicitly |
| `supports_availability_constraints` | Whether availability / coverage constraints can be probed explicitly |
| `core_group_limit` / `backfill_group_limit` | Per-request grouping ceilings for online vs backfill workloads |
| `max_sync_cells` / `max_async_cells` | Rough row / cell envelopes used to choose sync vs async paths |
| `capability_cache_ttl_hours` | Positive capability cache lifetime |
| `negative_cache_ttl_hours` | Hard negative cache lifetime after definite failures |
| `soft_negative_cache_ttl_hours` | Shorter retry horizon for soft capability failures |

## Built-in Profiles

The current `builtin_profiles.py` defines 32 builtin profiles.

| Family | Count | Example profile ids |
|--------|-------|---------------------|
| `sdmx` | 7 | `ecb_sdmx`, `oecd_sdmx`, `imf_sdmx`, `bis_sdmx`, `ilo_sdmx`, `fao_sdmx`, `unsd_sdmx` |
| `ckan` | 6 | `data_gov_md`, `data_gov_ro`, `data_gov_ua`, `data_gov_uk`, `data_gov_us`, `eu_open_data` |
| `rest` | 6 | `data_gov_pl`, `eia_api`, `nvd_cve`, `open_meteo`, `openaq_v2`, `usgs_earthquake` |
| `socrata` | 2 | `nyc_opendata`, `chicago_opendata` |
| `opendatasoft` | 2 | `opendatasoft_public`, `paris_opendata` |
| `sparql` | 2 | `wikidata_sparql`, `dbpedia_sparql` |
| Single-profile families | 7 | `worldbank_wdi`, `wvs_wave7`, `eurostat_public`, `ukons_public`, `who_gho`, `unpd_dataportal`, `unesco_uis_public` |

## Resolution Flow

| Step | Function | Output |
|------|----------|--------|
| Connection normalization | `resolve_connection_config()` | `ConnectionConfig` for connector runtime |
| Execution normalization | `resolve_execution_policy()` | Frozen `SourceExecutionPolicy` for planners |
| Registry access | `SourceProfileRegistry.get_instance()` | Singleton profile registry bootstrapped from `BUILTIN_PROFILES` |

## API Reference

::: polisyos.fabric.connectors.profiles.models

::: polisyos.fabric.connectors.profiles.resolver

::: polisyos.fabric.connectors.profiles.registry

