# Scholar — пайплайн обогащения знаний

`polisyos.scholar` строит детерминированный knowledge bundle из `ResearchIntent` и `seed_sources`.
Модуль оркестрирует этапы `discover -> acquire -> docs -> claims -> reconcile -> bundle`,
сохраняет результаты в CAS и пишет world event сборки.

## Роль в системе

```text
ResearchIntent (core.contracts.scholar)
          |
          v
     Scholar enrich_topic()
          |
          v
KnowledgeBundleRef (+ optional EnrichmentReportRef)
          |
          v
Scientist node enrich_knowledge / CLI components scholar enrich
```

`scholar` не реализует доменные `docs/claims/world` алгоритмы сам, а использует `fabric.*` и
контракты `core.contracts.scholar`.

## Архитектура директории

```text
scholar/
├── __init__.py                 # lazy exports публичного API
├── api.py                      # фасад: enrich_topic + ScholarService
├── policies.py                 # дефолты budget/threshold/docs/claims/freshness
├── errors.py                   # stage-aware ошибки Scholar*
├── types.py                    # payload/report/result dataclass + Pydantic-модели
├── freshness.py                # freshness policy/check + метрики
├── freshness_store.py          # sidecar runtime state + lock
├── discover/
│   ├── README.md               # детали discover/acquire
│   ├── manual.py               # нормализация, identity, дедуп источников
│   ├── http_fetch.py           # fetch URL
│   └── local_files.py          # read local_file
└── orchestrator/
    ├── README.md               # детали pipeline и bundle persistence
    ├── enrich.py               # основной orchestration flow
    └── bundle.py               # bundle payload/id + CAS/world persist
```

## Публичный API

```python
from pathlib import Path
from polisyos.scholar import ScholarService, enrich_topic

result = enrich_topic(
    cas=cas_store,
    fact_log_root=Path("/tmp/facts"),
    intent=research_intent,
    storage=storage_port,   # предпочтительный путь
    db=legacy_db,           # legacy: auto-wrap в DuckDBStorageAdapter
    policy=scholar_policy,  # optional, иначе ScholarPolicy()
)

service = ScholarService(fact_log_root=Path("/tmp/facts"), storage=storage_port)
bundle_ref = service.enrich(cas_store, research_intent)
```

`enrich_topic()` возвращает `EnrichResultV1`:
- `knowledge_bundle_ref`
- `bundle_id`
- `report`
- `report_ref` (`None`, если `ScholarPolicy.persist_report=False`)

## Pipeline (актуальное поведение)

| Этап | Что делает |
|---|---|
| validation | Валидирует `intent.domain` и `intent.seed_sources`, парсит legacy budgets |
| discover | Нормализует `SourceSpec`, каноникалит URL, резолвит пути, дедупит, режет по `max_docs` |
| acquire | Читает `url/local_file/bytes`, проверяет `max_bytes_per_doc` и `max_bytes_total` |
| docs | `ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc`; skip стадий при наличии refs в meta |
| claims | Bootstrap extractor-компонентов (`SCHOLAR` + `LEX` entry-point groups), extract + normalize claims |
| reconcile | `resolve_conflicts`, строит conflict/trust/quality artifacts |
| filtering | Фильтрует docs по `min_doc_trust_tier`; фильтрует claims по `claim_targets` и citations в выбранные docs |
| bundle | Вычисляет детерминированный `bundle_id`, сохраняет bundle/report в CAS, пишет `KNOWLEDGE_BUNDLE_BUILD` |

Ошибки нормализуются в stage-specific классы: `ScholarValidationError`, `ScholarDiscoverError`,
`ScholarAcquireError`, `ScholarDocsError`, `ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`.

## Freshness и runtime sidecar

- `build_freshness_metadata()` заполняет `FreshnessMetadata` в bundle (детерминированно при заданном source timestamp).
- `FreshnessPolicy.check()` вычисляет `fresh/stale/expired`, cooldown и `needs_refresh`.
- `timed_freshness_check()` публикует метрики в `core.observability`.
- `FreshnessStateStore` хранит mutable runtime state в `<cas_root>/freshness_state`:
  `last_checked_at`, `last_refresh_attempt_at`, `next_retry_at`, `failed_refresh_count`.
- `acquire_lock()` реализует межпроцессный lock для защиты от refresh-storm.

Дефолты порогов freshness живут в `ScholarPolicy.freshness` по доменам:
`fiscal`, `labor`, `health`, `infrastructure`, `education` + fallback.

## Контракты, артефакты, детерминизм

- Входные контракты: `ResearchIntent`, `SourceSpec`, `BudgetsV1`, `ThresholdsV1`
  (`core/contracts/scholar.py`).
- Основной артефакт: `scholar.knowledge_bundle` (`KnowledgeBundlePayloadV1`).
- Отчет: `scholar.enrichment_report` (`EnrichmentReportV1`, опционально).
- `bundle_id` детерминированно зависит от:
  - `intent_core`
  - `doc_version_ids`
  - `claim_ids`
  - `policy_ids_used`
- При каждом билде пишется world event `EventKind.KNOWLEDGE_BUNDLE_BUILD`.

## Связи с другими директориями

Кто использует `scholar`:
- `src/polisyos/scientist/nodes/builtins/data/enrich_knowledge.py` (freshness-check + refresh/reuse логика)
- `src/polisyos/core/components/_cli_scholar.py` (`components scholar enrich`)
- `tests/fabric/test_scholar_*`, `tests/scientist/test_enrich_knowledge_node_freshness.py`

Что использует `scholar`:
- `core.artifacts`, `core.contracts.scholar`, `core.components`
- `fabric.docs`, `fabric.claims`, `fabric.storage`, `fabric.world`
- `ir.world.*` (trust/event/world-id primitives)

Расширение extractors:
- bootstrap идет через `ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS` и `ENTRY_POINT_GROUP_LEX_EXTRACTORS`
- типичный провайдер: `packs/*/scholar_extractors.py`

## Инварианты и ограничения

- CAS-first: bundle/report immutable и content-addressed.
- Идемпотентность: одинаковые входы + policy дают одинаковый `bundle_id`.
- Документный pipeline инкрементальный: normalize/structure/chunk не повторяются, если refs уже есть.
- В `reconcile` предпочтителен `storage: StoragePort`; `db` поддерживается как legacy-совместимость.
- В `scholar` запрещены прямые импорты `polisyos.fabric.io.db`:
  проверка `../../../tools/lint/check_scholar_imports.py`.

## Документация поддиректорий

- [discover/README.md](discover/README.md)
- [orchestrator/README.md](orchestrator/README.md)
