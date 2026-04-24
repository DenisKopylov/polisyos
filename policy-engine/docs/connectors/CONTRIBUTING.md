# Contributing A Fabric Connector

Freshness: 2026-04-17.

This guide covers the current Fabric connector workflow. A connector is not
ready when it can fetch rows once; it is ready when it is protocol-compliant,
bounded, schema-governed, replayable, and covered by the shared registry and
contract tests.

Related reference: [Fabric Connectors](../reference/fabric/connectors.md).

## Inputs

- upstream source contract, auth story, and bounded query plan
- chosen existing family or a justified need for a new family
- executable sample payloads or fixtures for normalization/schema work

## Outputs

- connector implementation and export
- built-in profile metadata
- schema contract and compatibility evidence when payload shape is stable
- registry/protocol/source-specific tests

## Canonical Commands

```bash
uv run polisyos-tools connectors scaffold create --name MySource --type REST --dry-run
uv run polisyos-tools connectors check-contracts --check
uv run polisyos-tools validation fabric-schema-governance --check --evidence-out .tmp/fabric-schema-governance.json
```

## Source-Plan Contract

Every connector contribution maps to the D1-L2 Fabric remediation phases:

| Phase   | Contributor obligation                                                                                                                                       |
| ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Phase 0 | Validate query identifiers, literals, URL/path segments, REST/GraphQL data paths, bounded response size, provenance serialization, and UTC-aware timestamps. |
| Phase 1 | Close sessions, pools, handles, caches, and background work deterministically; keep shared state locked or immutable; keep queues/caches bounded.            |
| Phase 2 | Return stable `schema_id`, `schema_version`, `DataVersion`, finite quality values, normalized units, and deterministic transform output.                     |
| Phase 3 | Add or update schema contracts and run the schema compatibility gates when payload shape changes.                                                            |
| Phase 5 | Use quarantine/DLQ patterns for poison rows/messages and fixture-backed tests for new families.                                                              |
| Phase 6 | Expose catalog/search metadata in profiles and schemas; do not make natural-language discovery the only resolution path.                                     |

## Choose A Family

Start with the closest existing source module under
`src/polisyos/fabric/connectors/sources/`.

| Need                          | Existing family                                           |
| ----------------------------- | --------------------------------------------------------- |
| Public HTTP JSON API          | `RestJsonConnector`, `WHOConnector`, `WorldBankConnector` |
| SDMX statistical source       | `SDMXSourceConnector`, `EurostatConnector`                |
| CKAN catalog/resource         | `CKANCatalogConnector`, `CKANResourceConnector`           |
| Socrata or Opendatasoft       | `SocrataConnector`, `OpendatasoftConnector`               |
| SPARQL endpoint               | `SPARQLConnector`                                         |
| CSV/JSONL/Parquet/Excel file  | `FileTabularConnector`                                    |
| S3/GCS/Azure-style object     | `ObjectStorageConnector`                                  |
| SQLite/DuckDB read-only query | `SQLQueryConnector`                                       |
| GraphQL API                   | `GraphQLConnector`                                        |
| GeoJSON features              | `GeoJSONConnector`                                        |
| JSONL event stream/replay log | `EventStreamConnector`                                    |

Use the scaffold only for a new custom family:

```bash
uv run polisyos-tools connectors scaffold create --name "MyDataSource" --type REST --dry-run
uv run polisyos-tools architecture scaffold connector --name "MyDataSource" --type REST --dry-run
```

## Implement The Connector

The minimum implementation remains:

| Method                       | Requirement                                                                                                                                   |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `connect()` / `disconnect()` | Validate config, create a handle, and release resources deterministically.                                                                    |
| `health_check()`             | Perform a lightweight source probe and return `HealthStatus`.                                                                                 |
| `fetch()`                    | Return `FetchResult` with row count, schema refs, `DataVersion`, UTC `fetched_at`, completeness, and provenance-friendly content identifiers. |
| `validate_config()`          | Fail early for missing URL/auth headers, unsafe path/query settings, unsupported formats, or unbounded profile settings.                      |

For source families that support discovery or streaming, implement the matching
protocol methods such as `list_datasets()`, `get_dataset_schema()`,
`fetch_stream()`, or async fetch lease helpers.

## Safety Rules

- Do not interpolate untrusted identifiers or literals into SQL, SPARQL, SoQL,
  ODSQL, REST paths, GraphQL data paths, or file/object paths.

- Use Fabric safety helpers such as `safe_path_segment()`,
  `validate_data_path()`, `extract_bounded_data_path()`, and connector-family
  identifier validators.

- Use timezone-aware UTC datetimes only.
- Reject or quarantine non-finite numeric values at public boundaries.
- Keep per-source caches, resolver maps, audit logs, and prefetch queues bounded.
- Never import `polisyos.scientist.*` or `polisyos.foundry.*` from connector
  runtime code.

Run the connector lint checks:

```bash
python tools/lint/lint_connectors.py
python tools/lint/lint_connector_hardening.py
```

## Register The Connector

Add the class export in `src/polisyos/fabric/connectors/sources/__init__.py`.
If the connector should be discoverable through Python package entry points,
also add a component under `src/polisyos/fabric/connectors/components.py` and
wire it in `pyproject.toml` under `polisyos.fabric_connectors`.

For a direct registry-only connector, ensure `ConnectorRegistry.get_instance()`
can discover or register it in tests and local runtime setup.

## Add A Source Profile

Profiles live in `src/polisyos/fabric/connectors/profiles/builtin_profiles.py`.
At minimum provide:

- `profile_id`
- `display_name`
- `connector_family`
- `base_url`

For production connectors, also set concurrency, auth policy, transport
preference, cache TTLs, source organization, tags, and row/cell envelopes where
the source has meaningful limits.

## Add A Schema Contract

Stable payload shapes should have a contract under
`src/polisyos/fabric/connectors/sources/_contracts/` and should be included in
`ALL_SOURCE_CONTRACTS`. Return matching `schema_id` and `schema_version` from
`fetch()` and `get_dataset_schema()`.

Run the schema gates when a connector contract changes:

```bash
uv run python tools/connectors/check_contracts.py --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out .tmp/fabric-schema-governance.json
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

Breaking schema changes require approval metadata: owner, reviewer, risk level,
migration status, downstream impact summary, migration note, and an approved
major version bump.

## Test Requirements

At minimum:

```bash
uv run pytest tests/fabric/connectors/test_registry.py -q
uv run pytest tests/fabric/connectors/test_protocol_compliance.py -q
uv run pytest tests/fabric/connectors/test_contract_system.py -q
uv run pytest tests/fabric/connectors/sources/test_connector_family_expansion.py -q
```

Add source-specific tests under `tests/fabric/connectors/sources/`. Live
upstream tests must be marked as integration and should have recorded fixtures
or replay coverage so CI does not depend on external availability.

For streaming or poison-row behavior, also cover:

```bash
uv run pytest tests/fabric/data_plane/test_quarantine.py tests/fabric/data_plane/test_streaming_runtime.py -q
```

## Rollback

- Remove unfinished exports from `sources/__init__.py` and any built-in profile wiring.
- Revert accidental schema-contract or snapshot changes before regenerating anything else.
- Re-run `check-contracts --check` and the Fabric schema-governance evidence pass to confirm the tree is back on the committed baseline.

## Troubleshooting

- If the connector compiles but is undiscoverable, check export + profile registration first.
- If schema evolution fails review, add the required governance metadata or treat the change as accidental drift and revert it.
- If external availability makes tests flaky, switch to recorded fixtures or replay coverage before asking CI to trust the new family.

## Review Checklist

- Connector class exported from `sources/__init__.py`.
- Optional entry-point component added only when package discovery needs it.
- Built-in profile added with bounded execution policy.
- Schema contract added or the absence of one is intentional and documented.
- Registry, protocol, contract, and source-specific tests pass.
- Schema compatibility gates pass when schema contracts or generated snapshots
  change.

- Quality/lineage metadata points to current artifacts or tests.
