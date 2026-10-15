# Add a Data Source

> Add a Fabric source connector, a reusable profile, a schema contract, and
> fixture-backed tests for verifiable connector-level behavior.

Freshness: 2026-10-14

## Inputs

- a description of the upstream source, authentication, and transport
  assumptions;
- an assessment of whether an existing connector family fits;
- a sample payload or fixture for schema and normalization decisions.

## Outputs

- a connector class under `src/polisyos/fabric/connectors/sources/`;
- an export from `sources/__init__.py`;
- a built-in `SourceProfile` and, when needed, a schema contract;
- source-specific tests and schema-governance evidence.

## Commands

```bash
uv run polisyos-tools connectors scaffold create --name "MyDataSource" --type REST --dry-run
uv run pytest tests/unit/fabric/connectors/test_registry.py -q
uv run polisyos-tools validation fabric-schema-governance --check --evidence-out _build/.tmp/fabric-schema-governance.json
```

## Before you begin

Read [Connector CONTRIBUTING](../connectors/CONTRIBUTING.md),
[Fabric Connectors](../reference/fabric/connectors.md), and
[Fabric Data Plane](../reference/fabric/data-plane.md). Current exports, profiles,
and registration paths are listed in the [connector
reference](../reference/fabric/connectors.md#registration-status); this is a
census of source declarations, not evidence that an upstream provider is
available.

The new source should satisfy D1-L2 obligations: safe query construction,
bounded input, deterministic lifecycle, schema/quality validation,
observability/lineage, quarantine for poison records, and catalog
discoverability.

These checks describe the connector contract and the listed artifacts; they do
not prove live provider readiness, the truth of source content, or a complete
source-to-world/query/policy workflow. For a broader capability, identify the
production caller, persisted artifact, consumer, verification, and surface
separately. If a link is not implemented, record its missing-state label (for
example, `bridge_missing`, `consumer_missing`, or `semantic_test_missing`).

## 1. Choose the closest family

| Source                      | Starting class                                            |
| --------------------------- | --------------------------------------------------------- |
| HTTP/REST JSON              | `RestJsonConnector`, `WHOConnector`, `WorldBankConnector` |
| SDMX                        | `SDMXSourceConnector`, `EurostatConnector`                |
| CKAN                        | `CKANCatalogConnector`, `CKANResourceConnector`           |
| Socrata / Opendatasoft      | `SocrataConnector`, `OpendatasoftConnector`               |
| SPARQL                      | `SPARQLConnector`                                         |
| CSV, JSONL, Parquet, Excel  | `FileTabularConnector`                                    |
| S3/GCS/Azure-style object   | `ObjectStorageConnector`                                  |
| SQLite/DuckDB read-only SQL | `SQLQueryConnector`                                       |
| GraphQL                     | `GraphQLConnector`                                        |
| GeoJSON                     | `GeoJSONConnector`                                        |
| JSONL event stream          | `EventStreamConnector`                                    |

If you need a new custom connector, start with the scaffold:

```bash
uv run polisyos-tools connectors scaffold create --name "MyDataSource" --type REST --dry-run
```

Path-based connector wrappers were retired in Phase 1D; in workflow
documentation, the canonical boundary is now `polisyos-tools connectors ...`.

## 2. Implement the connector class

Place the new file under `src/polisyos/fabric/connectors/sources/`.

Minimum surface:

| Method                       | Required behavior                                                                                                                                               |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `connect()` / `disconnect()` | Validate config, create/release handle, close sessions and pools deterministically.                                                                             |
| `health_check()`             | Lightweight source probe returning `HealthStatus`.                                                                                                              |
| `fetch()`                    | Return `FetchResult` with `row_count`, `schema_id`, `schema_version`, `DataVersion`, UTC `fetched_at`, `completeness`, and provenance-friendly hashes/metadata. |
| `validate_config()`          | Reject missing auth, unsafe paths/query settings, unsupported formats, or unbounded execution settings.                                                         |

If the family supports discovery or streaming, add
`list_datasets()`, `get_dataset_schema()`, `fetch_stream()`, async fetch lease
helpers, or source-specific capability methods.

Useful production examples:

- `who.py` and `world_bank.py` for HTTP + DataFrame normalization.
- `sdmx_source.py` and `eurostat.py` for statistical APIs and async/bulk hints.
- `file_tabular.py` for files with schema introspection.
- `event_stream.py` for stream chunks and message IDs.
- `geojson.py` for CRS/spatial metadata preservation.

## 3. Apply the safety rules

- Do not interpolate untrusted identifiers or literals into SQL, SPARQL, SoQL,
  ODSQL, REST paths, GraphQL data paths, or file/object paths.

- Use Fabric safety helpers, including `safe_path_segment()`,
  `validate_data_path()`, and `extract_bounded_data_path()`, or family-specific
  identifier validators.

- Use only timezone-aware UTC datetimes.
- Reject or quarantine `NaN`, `Inf`, out-of-range quality scores and invalid
  row-count bounds.

- Keep resolver caches, prefetch queues, audit logs, and per-source maps
  bounded by TTL/LRU/maxsize.

- Runtime imports from `polisyos.scientist.*` and `polisyos.foundry.*` are
  prohibited.

## 4. Register the connector

Add the import/export in `src/polisyos/fabric/connectors/sources/__init__.py`.

If the connector should be discoverable through package entry points, add a
component in `src/polisyos/fabric/connectors/components.py` and an entry in
`pyproject.toml` group `polisyos.fabric_connectors`. Internal/scaffold
families can stay direct-import/registry-only until promoted.

## 5. Add a built-in source profile

Profiles are defined in `src/polisyos/fabric/connectors/profiles/builtin_profiles.py`.

Minimum fields:

- `profile_id`
- `display_name`
- `connector_family`
- `base_url`

Production profiles should also set auth policy, rate limit, max concurrency,
core/backfill transport, group limits, sync/async cell envelopes, capability
cache TTLs, tags, source organization, source URL, and estimated datasets.

## 6. Add a schema contract

If the payload shape is stable, add a contract under:

```text
src/polisyos/fabric/connectors/sources/_contracts/
```

Return matching `schema_id` and `schema_version` from `fetch()` and
`get_dataset_schema()`, and include the contract in `ALL_SOURCE_CONTRACTS`.

Run compatibility gates when schema contracts change:

```bash
uv run polisyos-tools connectors check-contracts --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out _build/.tmp/fabric-schema-governance.json
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

Breaking changes require approved major bump metadata: owner, reviewer, risk
level, migration status, downstream impact summary, migration note, and ADR refs
when applicable.

## 7. Test the connector

Minimum local checks:

```bash
uv run pytest tests/unit/fabric/connectors/test_registry.py -q
uv run pytest tests/unit/fabric/connectors/test_protocol_compliance.py -q
uv run pytest tests/unit/fabric/connectors/test_contract_system.py -q
uv run pytest tests/unit/fabric/connectors/sources/test_connector_family_expansion.py -q
```

Add source-specific tests under `tests/unit/fabric/connectors/sources/`. Live
upstream tests must be marked `integration` and should use recorded fixtures or
record/replay mode where possible.

For streaming, quarantine, or poison-row behavior:

```bash
uv run pytest tests/unit/fabric/data_plane/test_quarantine.py tests/unit/fabric/test_ingestion_quarantine.py -q
uv run pytest tests/unit/fabric/data_plane/test_streaming_runtime.py tests/unit/fabric/data_plane/test_streaming_windowed.py -q
```

## Rollback

If the connector family or schema approach proves incorrect, rollback usually
comes down to three actions:

1. Remove the unfinished connector export, built-in profile, and source-specific tests.
2. Revert the contract/snapshot changes in
   `src/polisyos/fabric/connectors/sources/_contracts/`, and
   `schemas/snapshots/connectors/contracts.json`;
3. Rerun `check-contracts --check` and the Fabric schema governance gate to
   confirm that the tree matches the committed baseline again.

## Troubleshooting

- If the connector does not appear in the registry, check the export in
  `sources/__init__.py` and built-in profile wiring.

- If the schema-governance gate reports breaking drift, add an approved
  major-bump metadata block or revert the accidental schema change.

- If source-specific tests are unstable because of a live upstream, switch to
  recorded fixtures or a replay-oriented integration path.

## Checklist

- Connector class under `src/polisyos/fabric/connectors/sources/`.
- Import/export added to `sources/__init__.py`.
- Optional entry-point component added only when package discovery needs it.
- Built-in `SourceProfile` added with bounded execution policy.
- Schema contract added or intentionally omitted with a documented reason.
- Registry, protocol, contract, source-specific, and schema-governance tests
  pass.

- Quality/lineage examples point to current artifacts or executable tests;
  fixture-backed examples are not live-provider or whole-system evidence.

## Related documents

- [Connector CONTRIBUTING](../connectors/CONTRIBUTING.md)
- [Fabric Connectors](../reference/fabric/connectors.md)
- [Fabric Profiles](../reference/fabric/profiles.md)
- [Fabric Data Plane](../reference/fabric/data-plane.md)
- [Manage Generated Artifacts](manage-generated-artifacts.md)
