# Fabric Tests

`tests/fabric` покрывает data layer `polisyos.fabric`: connectors, catalog/contracts, trust/provenance и world/materialization pipelines.

Актуально на **10 февраля 2026**.

## Роль в системе

- Валидирует ingestion-контур и контракты data connectors.
- Проверяет качество, доверие и provenance для данных перед downstream-использованием.
- Защищает world/materialization/query слой и domain pipelines (claims, lex/normpack/legal, scholar).
- Фиксирует гейты совместимости между `fabric`, `ir`, `lex`, `scholar` и `core`.

## Снимок структуры

- `46` файлов `test_*.py`
- `48` Python-файлов
- `1` `conftest.py` (в `connectors/`)
- `1` `README.md`

| Подкаталог | `test_*.py` | Зона ответственности |
|---|---:|---|
| корень `fabric/` | 23 | Catalog/provenance/trust/quality, world, claims/docs/normpack/legal/lex/scholar |
| `connectors/` | 22 | Connector protocol, registry, schema/types/cache/federation/resilience, reference/sources |
| `pii/` | 1 | PII detector checks |

## Ключевые модули

### Core Fabric

- `test_data_catalog.py` — data contracts, bindings, search/disambiguation
- `test_provenance.py` — lineage/provenance graph и persistence
- `test_quality_indicators.py` — quality scoring/gates
- `test_trust.py`, `test_trust_two_pass.py`, `test_trust_adapter.py`, `test_conflict_uncertainty_adapter.py`
- `test_conflicts.py`, `test_storage_port.py`

### World/data-plane и domain pipelines

- `test_world_store.py`, `test_world_materialization.py`, `test_world_query_multibackend.py`, `test_world_query_column_masking.py`, `test_world_kuzu.py`
- `test_claims_pipeline.py`, `test_docs_pipeline.py`
- `test_normpack.py`, `test_legal_evaluation.py`, `test_lex_corpus.py`
- `test_scholar_mvp.py`, `test_scholar_freshness.py`, `test_scholar_freshness_store.py`, `test_scholar_extractor_components.py`
- `pii/test_presidio_detector.py`

### Connectors (`fabric/connectors/`)

- Protocol/contracts: `test_protocol_compliance.py`, `test_contract_system.py`, `test_ingestion_fetch_activity_contract.py`
- Registry/type/schema: `test_registry.py`, `test_type_system.py`, `test_schema_system.py`
- Runtime качества: `test_quality_system.py`, `test_transform_pipeline.py`, `test_cache_system.py`, `test_schema_aware_cache.py`, `test_resilience.py`, `test_federation.py`
- Integration/harness/bridge: `test_integration.py`, `test_harness.py`, `test_components_bridge.py`
- Reference connectors: `reference/test_static_csv.py`, `reference/test_rest_json.py`, `reference/test_sdmx.py`
- Source policy checks: `sources/test_http_connector_base.py`, `test_http_version_policy.py`, `test_no_duplicate_http_helpers.py`, `test_production_connectors.py`

## Инфраструктура тестов

### `connectors/conftest.py`

- Добавляет `--record-mode` для `APISimulator`.
- Даёт изолированный `ConnectorRegistry` на тест.
- Поднимает fixtures для `ConnectionConfig`, `FetchRequest`, `FetchResult`, sample schema/dataframe.
- Управляет session event loop для `pytest-asyncio` сценариев.

### Integration и optional зависимости

- `connectors/reference/*` используют `@pytest.mark.integration`.
- Optional зависимости/условные skip:
  - `aiohttp` (HTTP connector tests)
  - `kuzu` (`test_world_kuzu.py`)
  - `hypothesis` (часть transform pipeline tests)
  - дополнительные skip-ветки для missing governance/OTel/lint tooling в отдельных connector-тестах

## Связи с другими директориями

| Здесь | Связанные директории | Назначение связи |
|---|---|---|
| `tests/fabric/` | `src/polisyos/fabric` | Основной объект тестирования |
| `tests/fabric/` | `src/polisyos/core`, `src/polisyos/ir` | Контракты, артефакты, data/version models |
| `tests/fabric/` | `src/polisyos/lex`, `src/polisyos/scholar` | Lex/legal/scholar pipelines поверх fabric-данных |

## Запуск

Команды из `policy-engine/`:

```bash
# весь fabric-контур
pytest tests/fabric -q

# connectors и reference integration
pytest tests/fabric/connectors -q
pytest tests/fabric/connectors/reference -q -m integration

# ключевые зоны
pytest tests/fabric/test_data_catalog.py -q
pytest tests/fabric/test_quality_indicators.py -q
pytest tests/fabric/test_provenance.py -q
pytest tests/fabric/test_world_materialization.py -q
```
