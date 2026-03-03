# Fabric

`polisyos.fabric` — data-fabric слой PolicyOS: здесь живут ingestion, документный и claim-пайплайны, world materialization, retrieval и orchestration режимов выполнения.

## Роль в системе

Fabric связывает инфраструктуру (`polisyos.ir`, `polisyos.core`, `polisyos.common`) с прикладными слоями (`polisyos.scientist`, `polisyos.scholar`, `polisyos.lex`).

```text
External APIs / Documents
        |
        v
connectors + docs + claims (+ pii/quality/trust)
        |
        v
CAS artifacts + world fact segments + provenance
        |
        +--> world/store -> world/materialize -> world_query
        |
        +--> data_plane (batch/record/replay/streaming)
        |
        +--> retrieval (fastlane/catalog/explore + execute)
```

## Ключевые entrypoints

- `run_connectors_ingestion(...)` — [ingestion.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/ingestion.py)
- `run(...)` compatibility wrapper — [connectors_ingestion.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/connectors_ingestion.py)
- `fabric_get_data(...)` sync bridge для верхних слоев — [_connector_bridge.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/_connector_bridge.py)
- `execute_world_query(...)` / `query_world_table(...)` — [world_query.py](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world_query.py)

## Архитектурные блоки

- `connectors/` — интеграция с внешними источниками: protocol, registry, discovery, profiles, contracts, resilience, cache, transform, federation.
- `docs/` — pipeline `ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc`.
- `claims/` — extraction/normalization/conflicts, world events/facts, evidence bundles.
- `world/` — append-only segment store + materialization в DuckDB (и optional Kuzu export).
- `data_plane/` — execution modes (`batch_incremental`, `record`, `replay`, `streaming_windowed`) и snapshot/cursor lifecycle.
- `retrieval/` — hybrid resolve+execute: FastLane, optional dataset-catalog lane, ExploreLane, promotion queue.
- `catalog/` — metric contracts и curated source bindings для deterministic resolve.
- `pii/`, `security/` — PII detection stage и column-level query guard/masking.
- `provenance/`, `evidence.py`, `fact_writer.py`, `segment_manifest.py` — трассируемость и сегменты фактов.
- `storage/`, `io/`, `tabular.py` — storage adapters, DuckDB runtime (`SimulationDB`), payload->DataFrame адаптация.

## Публичный API пакета

Через `polisyos.fabric` экспортируются lazy entrypoints:

- `fabric_get_data`
- `run_connectors_ingestion`
- `execute_world_query`
- `query_world_table`
- `query_claims`
- `query_events`
- `WorldQueryRequest`
- `WorldQueryError`
- `world`

Также lazy-доступны ключевые сущности каталога (`DataContract`, `MetricBinding`, `DataContractRegistry`, `MetricSearcher` и др.).

## Важные особенности

- Fabric не должен импортировать прикладные слои обратно (однонаправленная зависимость вниз).
- Ingestion по умолчанию пишет evidence/provenance в CAS и поддерживает optional PII stage (`POLISYOS_PII_*`).
- World materialization идемпотентна на уровне `segment_id + sha256`; hash mismatch считается ошибкой.
- Kuzu materialization выключена по умолчанию и выполняется только при явном включении (`kuzu_enabled=True`).
- `docs/backends/pdf.py` в ядре остается заглушкой (нужны optional deps).

## Где читать детали

- [connectors/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/connectors/README.md)
- [docs/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/docs/README.md)
- [claims/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/claims/README.md)
- [world/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/world/README.md)
- [data_plane/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/data_plane/README.md)
- [retrieval/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/retrieval/README.md)
- [catalog/README.md](/Users/deniskopylov/polisyos/policy-engine/src/polisyos/fabric/catalog/README.md)
