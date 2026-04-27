# Fabric Profiles

Related explanation: [Data Fabric](../../explanation/data-fabric.md).

Freshness: 2026-04-26.
Owner: `@fabric-owners`
Source plan: `docs/FABRIC_AUDIT_REMEDIATION_PLAN.md`, D1-L2 section in `docs/DOCUMENTATION_SOTA_PLAN.md`
Source of truth: `src/polisyos/fabric/connectors/profiles/**`, `tests/fabric/connectors/profiles/test_source_profiles.py`, `tests/fabric/test_retrieval_service_catalog.py`
Best-in-class inventory: [best-in-class-inventory.md](best-in-class-inventory.md)

`SourceProfile` describes a source endpoint in planner-friendly terms, while
`SourceExecutionPolicy` is the normalized runtime subset used by schedulers,
capability caches, retrieval, backfill planning, and future scale-out planners.
TTL fields control capability-cache freshness only; they do not imply HTTP
response caching unless a connector cache layer is configured separately.

## D1-L2 Profile Rules

| Source-plan phase | Profile implication                                                                                                                                                                                         |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Phase 0           | Profiles carry bounded-input and transport hints such as concurrency, page/cell envelopes, async support, auth policy, and schema preflight. They must not allow unbounded fetches by default.              |
| Phase 1           | Profiles feed deterministic lifecycle and bounded-memory behavior: max concurrency, quota ceilings, capability cache TTLs, and negative-cache TTLs must be explicit for low-rate or large-response sources. |
| Phase 2           | Profiles do not replace schema contracts; they help planners choose schema preflight and transport paths before `FetchResult` validation enforces schema and numeric quality bounds.                        |
| Phase 3           | Profile metadata should preserve classification, ownership, and observability labels without introducing high-cardinality telemetry.                                                                        |
| Phase 5           | New connector families need a scaffold/demo profile before promotion to production entry point.                                                                                                             |
| Phase 6           | Semantic discovery can enrich profiles, but deterministic fields remain the fallback and invalidation source for stale embeddings.                                                                          |

## Key Fields

| Field                                       | Semantics                                                            |
| ------------------------------------------- | -------------------------------------------------------------------- |
| `max_concurrency`                           | Maximum simultaneous requests the source should see                  |
| `requests_per_hour`                         | Coarse quota ceiling for low-rate APIs                               |
| `preferred_core_transport`                  | Preferred transport for regular online workloads                     |
| `preferred_backfill_transport`              | Preferred transport for bulk or historical backfills                 |
| `supports_async_large_responses`            | Whether the source has a safe async path for large payloads          |
| `supports_async_fetch`                      | Whether planners may choose an async fetch mode at all               |
| `schema_preflight`                          | Whether metadata / structure should be validated before fetch        |
| `supports_content_constraints`              | Whether dataset content constraints can be probed explicitly         |
| `supports_availability_constraints`         | Whether availability / coverage constraints can be probed explicitly |
| `core_group_limit` / `backfill_group_limit` | Per-request grouping ceilings for online vs backfill workloads       |
| `max_sync_cells` / `max_async_cells`        | Rough row / cell envelopes used to choose sync vs async paths        |
| `capability_cache_ttl_hours`                | Positive capability cache lifetime                                   |
| `negative_cache_ttl_hours`                  | Hard negative cache lifetime after definite failures                 |
| `soft_negative_cache_ttl_hours`             | Shorter retry horizon for soft capability failures                   |

## Built-in Profiles

The current `builtin_profiles.py` defines 38 built-in profiles.

| Family                             | Count | Example profile ids                                                                                                |
| ---------------------------------- | ----: | ------------------------------------------------------------------------------------------------------------------ |
| `sdmx`                             | 7     | `ecb_sdmx`, `oecd_sdmx`, `imf_sdmx`, `bis_sdmx`, `ilo_sdmx`, `fao_sdmx`, `unsd_sdmx`                               |
| `ckan`                             | 6     | `data_gov_md`, `data_gov_ro`, `data_gov_ua`, `data_gov_uk`, `data_gov_us`, `eu_open_data`                          |
| `rest`                             | 6     | `data_gov_pl`, `eia_api`, `nvd_cve`, `open_meteo`, `openaq_v2`, `usgs_earthquake`                                  |
| `socrata`                          | 2     | `nyc_opendata`, `chicago_opendata`                                                                                 |
| `opendatasoft`                     | 2     | `opendatasoft_public`, `paris_opendata`                                                                            |
| `sparql`                           | 2     | `wikidata_sparql`, `dbpedia_sparql`                                                                                |
| Production single-profile families | 7     | `worldbank_wdi`, `wvs_wave7`, `eurostat_public`, `ukons_public`, `who_gho`, `unpd_dataportal`, `unesco_uis_public` |
| Phase 5 scaffold families          | 6     | `files_demo_tabular`, `object_storage_demo`, `sqlite_demo`, `graphql_demo`, `geojson_demo`, `stream_jsonl_demo`    |

## Resolution Flow

| Step                     | Function                                 | Output                                                          |
| ------------------------ | ---------------------------------------- | --------------------------------------------------------------- |
| Connection normalization | `resolve_connection_config()`            | `ConnectionConfig` for connector runtime                        |
| Execution normalization  | `resolve_execution_policy()`             | Frozen `SourceExecutionPolicy` for planners                     |
| Registry access          | `SourceProfileRegistry.get_instance()`   | Singleton profile registry bootstrapped from `BUILTIN_PROFILES` |
| Family lookup            | `SourceProfileRegistry.list_by_family()` | Profiles available to a connector family and tests              |

`resolve_execution_policy()` also clamps concurrency and cache TTLs to safe
positive values and normalizes fallback transport defaults. That behavior is
covered in the model/resolver tests rather than being an undocumented planner
convention.

## Validation Anchors

```bash
uv run pytest tests/fabric/connectors/profiles/test_source_profiles.py -q
uv run pytest tests/fabric/connectors/bindings/test_binding_profiles.py -q
uv run pytest tests/fabric/connectors/sources/test_connector_family_expansion.py -q
uv run pytest tests/fabric/test_retrieval_service_catalog.py -q
```

When a profile changes schema behavior or generated connector metadata, also run
the schema gates listed in [connectors.md](connectors.md#schema-contracts-and-compatibility).

## API Reference

::: polisyos.fabric.connectors.profiles.models

::: polisyos.fabric.connectors.profiles.resolver

::: polisyos.fabric.connectors.profiles.registry
