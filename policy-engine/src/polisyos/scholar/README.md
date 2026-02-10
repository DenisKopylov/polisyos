# Scholar — пайплайн обогащения знаний

`polisyos.scholar` превращает набор источников (`url`, `local_file`, `bytes`) в детерминированный `KnowledgeBundle` и опциональный `EnrichmentReport`, сохраняя оба артефакта в CAS.

## Роль в системе

```
ResearchIntent (core.contracts.scholar)
          |
          v
     Scholar (discover -> acquire -> docs -> claims -> reconcile -> bundle)
          |
          v
KnowledgeBundleRef / EnrichmentReportRef (CAS)
          |
          v
Scientist node enrich_knowledge / core CLI scholar enrich
```

Scholar сам не владеет ingest/claims/world-реализацией, а оркестрирует подсистемы `fabric.*` и типы `core.contracts.scholar`.

## Публичный API

```python
from pathlib import Path
from polisyos.scholar import ScholarService, enrich_topic

result = enrich_topic(
    cas=cas_store,
    fact_log_root=Path("/tmp/facts"),
    intent=research_intent,
    storage=storage_port,   # рекомендуемый путь
    db=legacy_db,           # legacy, авто-обертка в DuckDBStorageAdapter
    policy=scholar_policy,
)

service = ScholarService(fact_log_root=Path("/tmp/facts"), storage=storage_port)
bundle_ref = service.enrich(cas_store, research_intent)
```

Возвращаемое значение: `EnrichResultV1` (`knowledge_bundle_ref`, `bundle_id`, `report`, `report_ref`).

## Архитектура директории

```
scholar/
├── __init__.py                # lazy public exports
├── api.py                     # публичный фасад
├── policies.py                # ScholarPolicy + freshness defaults
├── errors.py                  # stage-aware ошибки
├── types.py                   # внутренние dataclass/Pydantic типы
├── freshness.py               # freshness policy/check + metrics
├── freshness_store.py         # sidecar runtime state + lock
├── discover/
│   ├── manual.py              # нормализация/дедуп источников
│   ├── http_fetch.py          # HTTP acquire
│   └── local_files.py         # чтение local_file
└── orchestrator/
    ├── enrich.py              # основной pipeline
    └── bundle.py              # bundle_id, CAS persist, world event
```

## Как работает enrich pipeline

`orchestrator/enrich.py::enrich_topic()` выполняет:

| Шаг | Что происходит |
|---|---|
| validate | Проверка `ResearchIntent` (`domain` и `seed_sources` обязательны) |
| budgets/thresholds | Мерж `budgets_v1/thresholds_v1` intent с дефолтами `ScholarPolicy` |
| discover | Нормализация `SourceSpec`: каноникализация URL, абсолютные пути, hash-identity для bytes, дедуп, срез по `max_docs` |
| acquire | Последовательный fetch/read источников с лимитами `max_bytes_per_doc` и `max_bytes_total` |
| docs | `ingest_doc_bytes -> normalize_doc -> structure_doc -> chunk_doc`; стадии пропускаются, если ref уже есть в CAS |
| claims | bootstrap extractors через `core.components` + извлечение/нормализация claims с учетом claim budget |
| reconcile | `resolve_conflicts`, расчет trust, quality artifacts, выбор winners |
| filtering | Отсев docs ниже `min_doc_trust_tier`, отсев claims по `claim_targets` и по цитируемым выбранным docs |
| bundle | Детерминированный `bundle_id`, сборка payload/report, persist в CAS, запись `KNOWLEDGE_BUNDLE_BUILD` world event |

Ошибки заворачиваются в stage-специфичные исключения: `ScholarValidationError`, `ScholarDiscoverError`, `ScholarAcquireError`, `ScholarDocsError`, `ScholarClaimsError`, `ScholarReconcileError`, `ScholarBundleError`.

## Источники и discover/acquire особенности

- `url`: каноникализация (lower-case host/scheme, сортировка query, удаление fragment).
- `local_file`: путь резолвится в абсолютный; встроенно поддержаны `.txt`, `.html`, `.htm`, иначе нужен `mime_hint`.
- `bytes`: identity формируется как `bytes.sha256_<hash>`.
- Общий stop-condition по acquire: достижение `max_bytes_total` (в report попадает note `stopped:max_bytes_total`).

## Freshness подсистема

Scholar экспортирует freshness primitives, которые используются в runtime (прежде всего узлом `scientist/nodes/builtins/data/enrich_knowledge.py`):

- `freshness.py`
  - `build_freshness_metadata()` добавляет детерминированную freshness metadata в bundle.
  - `FreshnessPolicy.check()` вычисляет `fresh/stale/expired`, cooldown и `needs_refresh`.
  - `timed_freshness_check()` публикует метрики через `core.observability`.
- `freshness_store.py`
  - sidecar-состояние в `<cas_root>/freshness_state`.
  - JSON state (`last_checked_at`, `last_refresh_attempt_at`, `next_retry_at`, `failed_refresh_count`).
  - file-lock (`acquire_lock`) для анти-шторм защиты при конкурентном refresh.

Domain defaults для freshness задаются в `ScholarPolicy.freshness` (`fiscal`, `labor`, `health`, `infrastructure`, `education` + fallback).

## Контракты и артефакты

- Вход: `ResearchIntent`, `SourceSpec`, `BudgetsV1`, `ThresholdsV1` из `core/contracts/scholar.py`.
- Выход:
  - `scholar.knowledge_bundle` (`KnowledgeBundlePayloadV1`)
  - `scholar.enrichment_report` (`EnrichmentReportV1`, если `persist_report=True`)
- Bundle ID строится детерминированно из:
  - normalized intent core,
  - `doc_version_ids`,
  - `claim_ids`,
  - `policy_ids_used`.
- В world layer пишется детерминированный event `EventKind.KNOWLEDGE_BUNDLE_BUILD`.

## Связь с другими директориями

### Кто использует Scholar

- `scientist/nodes/builtins/data/enrich_knowledge.py`: freshness-check, reuse/refetch logic, lock/cooldown.
- `core/components/_cli_scholar.py`: CLI `components scholar enrich`.
- `tests/fabric/test_scholar_*` и `tests/scientist/test_enrich_knowledge_node_freshness.py`: контрактные сценарии.

### Что использует Scholar

- `core/artifacts`, `core/contracts/scholar`, `core/components`.
- `fabric/docs`, `fabric/claims`, `fabric/world`, `fabric/storage`.
- `ir/world/*` (trust tiers, world IDs/events).

Extension point для domain extractors: entry-point group `polisyos.scholar_extractors` (пример: `packs/roads/scholar_extractors.py`).

## Практические инварианты

- CAS-first: все основные артефакты immutable и content-addressed.
- Идемпотентность bundle: одинаковые входы и policy дают одинаковый `bundle_id`.
- Документный pipeline инкрементальный: повторные normalize/structure/chunk не делаются при наличии ссылок в метаданных.
- Предпочтительный интерфейс хранения для reconcile: `storage: StoragePort`; `db=` оставлен как legacy-совместимость.
- В `scholar` запрещена прямая зависимость от `fabric.io.db` (проверяется `tools/lint/check_scholar_imports.py`).
