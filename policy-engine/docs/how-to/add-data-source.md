# Добавление источника данных

> Создайте Fabric source connector, reusable profile, schema contract и тесты,
> которые делают источник production-safe.

Freshness: 2026-04-17.

## Вход

- описание upstream source, auth и transport assumptions
- понимание, подходит ли существующая connector family
- sample payload или fixture для schema/normalization decisions

## Выход

- connector class под `src/polisyos/fabric/connectors/sources/`
- export из `sources/__init__.py`
- built-in `SourceProfile`, а при необходимости и schema contract
- source-specific tests и schema-governance evidence

## Команды

```bash
uv run polisyos-tools connectors scaffold create --name "MyDataSource" --type REST --dry-run
uv run pytest tests/fabric/connectors/test_registry.py -q
uv run polisyos-tools validation fabric-schema-governance --check --evidence-out .tmp/fabric-schema-governance.json
```

## Перед началом

Прочитайте [Connector CONTRIBUTING](../connectors/CONTRIBUTING.md),
[Fabric Connectors](../reference/fabric/connectors.md) и
[Fabric Data Plane](../reference/fabric/data-plane.md). Текущая Fabric
платформа содержит 20 exported connector classes и 38 built-in source profiles.

Новый источник должен закрывать D1-L2 obligations: safe query construction,
bounded input, deterministic lifecycle, schema/quality validation,
observability/lineage, quarantine for poison records, and catalog
discoverability.

## 1. Выберите ближайшую family

| Источник | Стартовый класс |
|---|---|
| HTTP/REST JSON | `RestJsonConnector`, `WHOConnector`, `WorldBankConnector` |
| SDMX | `SDMXSourceConnector`, `EurostatConnector` |
| CKAN | `CKANCatalogConnector`, `CKANResourceConnector` |
| Socrata / Opendatasoft | `SocrataConnector`, `OpendatasoftConnector` |
| SPARQL | `SPARQLConnector` |
| CSV, JSONL, Parquet, Excel | `FileTabularConnector` |
| S3/GCS/Azure-style object | `ObjectStorageConnector` |
| SQLite/DuckDB read-only SQL | `SQLQueryConnector` |
| GraphQL | `GraphQLConnector` |
| GeoJSON | `GeoJSONConnector` |
| JSONL event stream | `EventStreamConnector` |

Если нужен новый custom connector, начните со scaffold:

```bash
uv run polisyos-tools connectors scaffold create --name "MyDataSource" --type REST --dry-run
```

`python tools/connectors/scaffold.py ...` остаётся compatibility wrapper, но в
workflow-доках канонический boundary теперь `polisyos-tools connectors ...`.

## 2. Реализуйте connector class

Новый файл размещайте под `src/polisyos/fabric/connectors/sources/`.

Минимальная surface:

| Method | Что должно быть реализовано |
|---|---|
| `connect()` / `disconnect()` | Validate config, create/release handle, close sessions and pools deterministically. |
| `health_check()` | Lightweight source probe returning `HealthStatus`. |
| `fetch()` | Return `FetchResult` with `row_count`, `schema_id`, `schema_version`, `DataVersion`, UTC `fetched_at`, `completeness`, and provenance-friendly hashes/metadata. |
| `validate_config()` | Reject missing auth, unsafe paths/query settings, unsupported formats, or unbounded execution settings. |

Если family поддерживает discovery или streaming, добавьте
`list_datasets()`, `get_dataset_schema()`, `fetch_stream()`, async fetch lease
helpers, или source-specific capability methods.

Полезные production examples:

- `who.py` and `world_bank.py` for HTTP + DataFrame normalization.
- `sdmx_source.py` and `eurostat.py` for statistical APIs and async/bulk hints.
- `file_tabular.py` for files with schema introspection.
- `event_stream.py` for stream chunks and message IDs.
- `geojson.py` for CRS/spatial metadata preservation.

## 3. Примените safety rules

- Не интерполируйте untrusted identifiers/literals в SQL, SPARQL, SoQL, ODSQL,
  REST paths, GraphQL data paths или file/object paths.
- Используйте Fabric safety helpers, включая `safe_path_segment()`,
  `validate_data_path()` and `extract_bounded_data_path()`, либо
  family-specific identifier validators.
- Используйте только timezone-aware UTC datetimes.
- Reject or quarantine `NaN`, `Inf`, out-of-range quality scores and invalid
  row-count bounds.
- Keep resolver caches, prefetch queues, audit logs, and per-source maps
  bounded by TTL/LRU/maxsize.
- Runtime imports из `polisyos.scientist.*` and `polisyos.foundry.*` запрещены.

## 4. Зарегистрируйте connector

Добавьте import/export в `src/polisyos/fabric/connectors/sources/__init__.py`.

Если connector должен быть discoverable через package entry points, добавьте
component в `src/polisyos/fabric/connectors/components.py` и запись в
`pyproject.toml` group `polisyos.fabric_connectors`. Internal/scaffold
families can stay direct-import/registry-only until promoted.

## 5. Добавьте built-in source profile

Profiles находятся в `src/polisyos/fabric/connectors/profiles/builtin_profiles.py`.

Минимальные поля:

- `profile_id`
- `display_name`
- `connector_family`
- `base_url`

Production profiles should also set auth policy, rate limit, max concurrency,
core/backfill transport, group limits, sync/async cell envelopes, capability
cache TTLs, tags, source organization, source URL, and estimated datasets.

## 6. Добавьте schema contract

Если payload shape stable, добавьте contract под:

```text
src/polisyos/fabric/connectors/sources/_contracts/
```

Return matching `schema_id` and `schema_version` from `fetch()` and
`get_dataset_schema()`, and include the contract in `ALL_SOURCE_CONTRACTS`.

Run compatibility gates when schema contracts change:

```bash
uv run python tools/connectors/check_contracts.py --check
uv run python tools/ci/check_fabric_schema_registry.py --check --evidence-out .tmp/fabric-schema-governance.json
uv run --extra ml polisyos-tools diagnostics gen-schema --check
```

Breaking changes require approved major bump metadata: owner, reviewer, risk
level, migration status, downstream impact summary, migration note, and ADR refs
when applicable.

## 7. Протестируйте

Minimum local checks:

```bash
uv run pytest tests/fabric/connectors/test_registry.py -q
uv run pytest tests/fabric/connectors/test_protocol_compliance.py -q
uv run pytest tests/fabric/connectors/test_contract_system.py -q
uv run pytest tests/fabric/connectors/sources/test_connector_family_expansion.py -q
```

Add source-specific tests under `tests/fabric/connectors/sources/`. Live
upstream tests must be marked `integration` and should use recorded fixtures or
record/replay mode where possible.

For streaming, quarantine, or poison-row behavior:

```bash
uv run pytest tests/fabric/data_plane/test_quarantine.py tests/fabric/test_ingestion_quarantine.py -q
uv run pytest tests/fabric/data_plane/test_streaming_runtime.py tests/fabric/data_plane/test_streaming_windowed.py -q
```

## Откат

Если connector family или schema story оказались ошибочными, откат обычно
сводится к трём действиям:

1. удалить незавершённый connector export, built-in profile и source-specific tests;
2. откатить contract/snapshot изменения в
   `src/polisyos/fabric/connectors/sources/_contracts/` и
   `schemas/snapshots/connectors/contracts.json`;
3. повторно прогнать `check-contracts --check` и Fabric schema governance gate,
   чтобы убедиться, что дерево снова совпадает с committed baseline.

## Troubleshooting

- Если connector не виден в registry, проверьте export в `sources/__init__.py`
  и built-in profile wiring.
- Если schema-governance gate сигналит breaking drift, либо добавьте одобренный
  major-bump metadata block, либо откатите accidental schema change.
- Если source-specific tests unstable из-за живого upstream, переходите на
  recorded fixtures или replay-oriented integration path.

## Чеклист

- Connector class under `src/polisyos/fabric/connectors/sources/`.
- Import/export added to `sources/__init__.py`.
- Optional entry-point component added only when package discovery needs it.
- Built-in `SourceProfile` added with bounded execution policy.
- Schema contract added or intentionally omitted with a documented reason.
- Registry, protocol, contract, source-specific, and schema-governance tests
  pass.
- Quality/lineage examples point to current artifacts or executable tests.

## Связанные документы

- [Connector CONTRIBUTING](../connectors/CONTRIBUTING.md)
- [Fabric Connectors](../reference/fabric/connectors.md)
- [Fabric Profiles](../reference/fabric/profiles.md)
- [Fabric Data Plane](../reference/fabric/data-plane.md)
- [Manage Generated Artifacts](manage-generated-artifacts.md)
