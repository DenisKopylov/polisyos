# Datasets (`polisyos.datasets`)

`polisyos.datasets` — слой построения и чтения каталога статистических датасетов. Он закрывает два контура:

- batch-построение snapshot-артефактов (raw -> normalized -> merged -> DuckDB -> embeddings);
- runtime-доступ к каталогу для поиска датасетов и transportability-оценок (`P*(Z)`, proxy fallback).

## Архитектура директории

- `batch/`
  Staged pipeline и CLI для сборки каталога из внешних источников.
- `knowledge/`
  Read/query API поверх собранного DuckDB + HNSW индекса и registry-таблиц.
- `metrics_map.py`
  Хелпер загрузки `metrics_map.yaml` (hook для маппинга PolicyOS-метрик на этапе normalize).
- `__init__.py`
  Пакетная точка входа.

Подробности вынесены в:

- `batch/README.md`
- `knowledge/README.md`

## Сквозной поток данных

1. `batch.harvest` собирает raw payload по источникам и пишет per-source manifest.
2. `batch.normalize` приводит raw к `DatasetRecord` (DCAT-like) и формирует `normalized/*.jsonl`.
3. `batch.merge_dedup` объединяет данные и удаляет дубликаты по `dedup_key`.
4. `batch.graph_load` загружает `ds_datasets`/`ds_distributions` в DuckDB.
5. `batch.graph_index` строит вторичные индексы.
6. `batch.core_sources_ingest` (опционально) заполняет registry/alignments/observations для transportability.
7. `batch.embed` строит `SentenceTransformer` embeddings и HNSW index.
8. `batch.qc` выполняет проверку качества и пишет `qc_report.json`.
9. `batch.publish` формирует publish-manifest с SHA256 артефактов.

## Роль в системе

- Для `fabric.retrieval` каталог используется как дополнительный lane резолвинга `DataNeed` (metric -> dataset -> connector).
- Для `scientist.agent` каталог используется как tool для dataset discovery и валидации data needs.
- Для `scientist.nodes...resolve_transport` registry-часть (`DatasetRegistry`, proxy resolver) используется в цикле transportability.
- Для `ir.analytics` используются типы/модели transportability и confidence-композиции.

## Связи с другими директориями

- `polisyos.batch_common` — filesystem layout, stage manifests, QC/fail-fast, thermal pacing.
- `polisyos.fabric.connectors` — ingestion `core_sources_ingest` через source profiles и connectors (`WorldBankConnector`, `WVSConnector`).
- `polisyos.fabric.retrieval` — catalog-assisted resolve (`find_by_polisyos_metric`, `get_connector_params`).
- `polisyos.scientist.agent` — typed toolkit API для dataset search.
- `polisyos.scientist.nodes.builtins.causal.resolve_transport` — вычисления `P*(Z)` и proxy fallback.

## Важные текущие особенности

- По умолчанию `run` в batch включает все стадии, кроме `core_sources_ingest`.
- Артефакты пишутся под `snapshot_root/datasets`, а не в `src/polisyos/datasets`.
- Маппинг на PolicyOS-метрики в normalize предусмотрен интерфейсно, но в стандартном CLI не передается отдельным флагом.
