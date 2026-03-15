# Datasets Batch (`polisyos.datasets.batch`)

`polisyos.datasets.batch` — staged pipeline, который строит каталог датасетов и publish-ready артефакты в `snapshot_root/datasets`.

## Роль в системе

- собирает метаданные из внешних статистических источников (SDMX/CKAN/API);
- нормализует их в единую модель `DatasetRecord`;
- загружает граф каталога в DuckDB и строит vector index;
- прогоняет consumer benchmarks для `scientist`, `fabric`, transportability и `foundry`;
- готовит QC и publish manifest;
- опционально заполняет registry-таблицы для transportability (`DatasetRegistry`).

## Стадии pipeline

| Stage | Модуль | Что делает | Основные артефакты |
|---|---|---|---|
| `harvest` | `harvester.py` | Скачивает raw payload по enabled источникам выбранной wave | `raw/<source>/<ts>/payload.jsonl`, `raw/.../manifest.json`, `manifests/harvest.json` |
| `normalize` | `normalizer.py` | Преобразует raw в `DatasetRecord` | `normalized/<source>.jsonl`, `manifests/normalize.json` |
| `merge_dedup` | `dedup.py` | Merge + dedup по `dedup_key` | `merged/all_records.jsonl`, `merged/duplicates_report.csv`, `manifests/merge_dedup.json` |
| `graph_load` | `graph_builder.py` | Загружает данные в DuckDB (`ds_datasets`, `ds_distributions`) | `graph/dataset_catalog.duckdb`, `manifests/graph_load.json` |
| `graph_index` | `graph_builder.py` | Создает вторичные индексы DuckDB | `graph/dataset_catalog.duckdb`, `manifests/graph_index.json` |
| `core_sources_ingest` | `core_sources_ingest.py` | Заполняет `ds_registry_datasets`, `ds_variable_alignments`, `ds_observations` | `graph/dataset_catalog.duckdb`, `manifests/core_sources_ingest.json` |
| `embed` | `embedder.py` | Строит эмбеддинги и HNSW index | `ds_dataset_embeddings.npz`, `ds_dataset_index.hnsw`, `manifests/embed.json` |
| `benchmark` | `benchmark.py` | Считает multilingual search / retrieval / transport / foundry readiness benchmarks | `benchmark_report.json`, `manifests/benchmark.json` |
| `qc` | `qc.py` | Проводит QC checks и fail-fast gate | `qc_report.json`, `manifests/qc.json` |
| `publish` | `publish.py` | Собирает publish manifest и `consumer_readiness.json`, блокируя publish при провале readiness-gates | `publish/manifest.json`, `publish/consumer_readiness.json`, `manifests/publish.json` |

## Snapshot layout

```text
<snapshot_root>/datasets/
  raw/<source>/<timestamp>/{payload.jsonl,manifest.json}
  normalized/*.jsonl
  merged/{all_records.jsonl,duplicates_report.csv}
  graph/dataset_catalog.duckdb
  ds_dataset_embeddings.npz
  ds_dataset_index.hnsw
  benchmark_report.json
  qc_report.json
  manifests/*.json
  publish/{manifest.json,consumer_readiness.json}
```

## Source registry и волны

- Источники объявлены в `source_registry.yaml` (`name`, `family`, `wave`, `endpoint`, фильтры agencies).
- Поддерживаются wave `A/B/C/D`.
- Wave `C` теперь разделён на `data_gov_ua_broad` и `data_gov_ua_exec`; второй строится как curated slice из broad snapshot и тоже идёт последовательным циклом, без параллельного fan-out.
- `--resume` повторно использует последний raw snapshot конкретного source.

Основные `family` в текущем коде:

- `sdmx` (OECD, IMF, ECB, Eurostat, ILO, UNICEF);
- `worldbank`, `wvs`, `ukons`, `who`, `uis`, `unpd`;
- `ckan` (например `data_gov_ua_broad`, `data_gov_ua_exec`);
- `undata`.

## CLI точки входа

CLI расположен в `cli.py`.

Примеры:

```bash
python -m polisyos.datasets.batch.cli run --snapshot-root /abs/path/to/snapshot
python -m polisyos.datasets.batch.cli run --snapshot-root /abs/path/to/snapshot --stages harvest,normalize,merge-dedup
python -m polisyos.datasets.batch.cli core-sources-ingest --snapshot-root /abs/path/to/snapshot
python -m polisyos.datasets.batch.cli benchmark --snapshot-root /abs/path/to/snapshot
python -m polisyos.datasets.batch.cli search --db-path /abs/path/to/snapshot/datasets/graph/dataset_catalog.duckdb --query "gdp per capita"
```

Важно:

- `run` по умолчанию использует полный `DEFAULT_RUN_STAGES`, включая `core_sources_ingest`, `benchmark`, `qc` и `publish`.
- aliases стадий поддерживаются (`merge-dedup`, `graph-load`, `graph-index`, `core-sources-ingest`).

## Конфигурация (`DatasetBatchConfig`)

`config.py` задает общие параметры выполнения:

- директории артефактов и путь к DuckDB;
- набор стадий и `fail_fast_qc`;
- `registry_path`, `wave`, `max_datasets_per_source`, `harvest_timeout`;
- embedding параметры (`model`, `device`, `batch_size`);
- thermal settings (`cooldown_seconds`, `thermal_profile`).

## Операционные особенности

- `graph_load` делает `DELETE` из `ds_datasets`/`ds_distributions` перед загрузкой (refresh текущего snapshot).
- dedup ключ: `source|agency|dataset_id` (или `DatasetRecord.dedup_key` если задан).
- QC пороги в текущей реализации:
  - `empty_title_pct <= 5%`;
  - `empty_description_pct <= 60%`;
  - `url_sample_reachability_pct >= 70%` (warning, если sample пустой).
- Benchmark/readiness gates в текущей реализации:
  - `benchmark_search_top5_relevance_pct >= 80%`;
  - `benchmark_retrieval_ready_pct >= 85%`;
  - `benchmark_transport_ready_pct >= 80%`;
  - `benchmark_foundry_fitness_pct >= 80%`.
- `publish` больше не является “тупой” записью manifest: он требует успешный `qc_report.json`, валидный `benchmark_report.json` и положительный `publish/consumer_readiness.json`.
- Метрики PolicyOS в normalize подключаются через `metrics_map` параметр функции, но стандартный CLI сейчас не передает этот файл отдельным флагом.

## Связи с соседними пакетами

- `polisyos.batch_common.*` — manifests, QC model, thermal helpers, directory layout.
- `polisyos.datasets.knowledge.types` — канонические `DatasetRecord/DistributionRecord` для стадий normalize/merge/graph.
- `polisyos.fabric.connectors.*` — `core_sources_ingest` использует connector profiles и source-specific fetchers для worldbank/wvs/eurostat/oecd/ilo и transport-source REST APIs.
- `polisyos.datasets.knowledge.search` — CLI команда `search` использует runtime-граф поверх собранного каталога.
