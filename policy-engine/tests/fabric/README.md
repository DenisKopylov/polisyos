# Fabric Tests

`tests/fabric` проверяет data-layer `polisyos.fabric`: connectors, ingestion/data plane, trust/provenance, world и прикладные data pipelines.

Актуально на **17 февраля 2026**.

## Состав

- `62` файла `test_*.py`
- `1` `README.md`
- `1` `conftest.py` (в `connectors/`)

## Структура

| Подкаталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `fabric/` (корень) | 23 | catalog, provenance/trust, world, claims/docs/legal/lex/scholar |
| `fabric/connectors/` | 32 | protocol/registry/schema/cache/resilience/federation/sources |
| `fabric/data_plane/` | 6 | watermark, incremental, cursor store, orchestrator, record replay |
| `fabric/pii/` | 1 | PII detection |

## Ключевые зоны

- Data contracts и quality/trust gates: `test_data_catalog.py`, `test_quality_indicators.py`, `test_trust*.py`, `test_conflicts.py`.
- Provenance и world: `test_provenance.py`, `test_world_*`.
- Domain pipelines: `test_claims_pipeline.py`, `test_docs_pipeline.py`, `test_normpack.py`, `test_legal_evaluation.py`, `test_lex_corpus.py`.
- Scholar/freshness: `test_scholar_*`.

### Connectors

- Framework: `test_protocol_compliance.py`, `test_contract_system.py`, `test_registry.py`, `test_schema_system.py`, `test_type_system.py`.
- Runtime behavior: `test_transform_pipeline.py`, `test_quality_system.py`, `test_cache_system.py`, `test_resilience.py`, `test_federation.py`.
- Sources/reference: `sources/test_*.py`, `reference/test_*.py`.

Только `reference/test_*.py` помечены `@pytest.mark.integration`.

## Связи с кодом

- `policy-engine/src/polisyos/fabric`
- `policy-engine/src/polisyos/lex`
- `policy-engine/src/polisyos/scholar`
- `policy-engine/src/polisyos/ir`

## Запуск

```bash
pytest tests/fabric -q
pytest tests/fabric/connectors -q
pytest tests/fabric/data_plane -q

# integration subset
pytest tests/fabric/connectors/reference -q -m integration
```
