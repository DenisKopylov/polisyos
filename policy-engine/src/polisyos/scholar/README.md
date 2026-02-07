# Scholar — система сбора и обогащения знаний

Модуль `polisyos.scholar` реализует полный пайплайн преобразования сырых источников данных (URL, файлы, байты) в структурированные **KnowledgeBundle** — пакеты знаний с извлечёнными утверждениями, оценками доверия и метаданными провенанса.

## Место в архитектуре

```
Внешние источники (URL, файлы, байты)
         │
         ▼
   ┌───────────┐    ResearchIntent
   │  Scholar   │◄── (domain, sources, budgets)
   └─────┬─────┘
         │ KnowledgeBundleRef
         ▼
   Scientist / Foundry ──► IR
```

Scholar — **потребитель** сервисов Fabric (документы, утверждения, world-граф) и Core (CAS, контракты). Обратных зависимостей на Scholar из других модулей нет — он вызывается Scientist/Foundry как сервис обогащения.

## Публичный API

```python
from polisyos.scholar import ScholarService, enrich_topic

# Функциональный стиль
result = enrich_topic(
    cas=cas_store,
    fact_log_root=Path("/logs"),
    intent=research_intent,
    db=simulation_db,       # опционально
    policy=scholar_policy,  # опционально
)
# result.knowledge_bundle_ref — ссылка на пакет в CAS
# result.report              — EnrichmentReportV1

# Сервис-обёртка
service = ScholarService(fact_log_root=Path("/logs"), db=db, policy=policy)
bundle_ref = service.enrich(cas_store, research_intent)
```

## Структура модуля

```
scholar/
├── api.py              # Фасад: ScholarService, enrich_topic()
├── types.py            # Внутренние типы пайплайна
├── policies.py         # ScholarPolicy — конфигурация всех стадий
├── errors.py           # Иерархия ошибок по стадиям
├── discover/           # Обнаружение и получение источников
│   ├── manual.py       #   нормализация, каноникализация, дедупликация
│   ├── http_fetch.py   #   HTTP/HTTPS загрузка с таймаутами
│   └── local_files.py  #   чтение локальных файлов
└── orchestrator/       # Координация пайплайна обогащения
    ├── enrich.py       #   7-стадийный пайплайн
    └── bundle.py       #   сборка KnowledgeBundle + WorldEvent
```

## Пайплайн обогащения

`enrich_topic()` проводит источники через семь последовательных стадий:

| # | Стадия | Что делает | Ошибка при сбое |
|---|--------|------------|-----------------|
| 1 | **validate** | Проверка `ResearchIntent` (domain, seed_sources обязательны), разрешение бюджетов и порогов | `ScholarValidationError` |
| 2 | **discover** | Нормализация URL (каноникализация хоста, сортировка query-параметров), разрешение путей, SHA-256 идентификация bytes-источников, дедупликация, обрезка по `max_docs` | `ScholarDiscoverError` |
| 3 | **acquire** | Последовательное получение данных: `fetch_url` (HTTP с таймаутом), `read_local_file`, прямое чтение bytes. Останов при достижении `max_bytes_total` | `ScholarAcquireError` |
| 4 | **docs** | Для каждого документа: `ingest_doc_bytes` → `normalize_doc` → `structure_doc` → `chunk_doc`. Пропускает стадии при наличии результатов в CAS | `ScholarDocsError` |
| 5 | **claims** | Выбор экстрактора через `ClaimExtractorRegistry` (с учётом domain/jurisdiction/language). Извлечение утверждений, нормализация. Останов при исчерпании `max_claims_total` | `ScholarClaimsError` |
| 6 | **reconcile** | `resolve_conflicts`: обнаружение противоречий, оценка доверия (`TrustAssessment`), выбор победителей. Фильтрация документов ниже `min_doc_trust_tier`, фильтрация утверждений по `claim_targets` | `ScholarReconcileError` |
| 7 | **bundle** | Детерминированный `bundle_id` (SHA от intent + docs + claims + policies). Персистенция KnowledgeBundle и EnrichmentReport в CAS. Эмиссия `WorldEvent` (KNOWLEDGE_BUNDLE_BUILD) с провенансом | `ScholarBundleError` |

## Типы источников (discover/)

| Тип | Идентификация | Особенности |
|-----|--------------|-------------|
| `url` | `canonical_url` (каноникализированный) | HTTP-загрузка, определение MIME из Content-Type, таймаут + User-Agent из политики |
| `local_file` | `source_locator` (абсолютный путь) | Разрешение `~` и относительных путей, MIME по расширению (.txt, .html, .htm) или mime_hint |
| `bytes` | `bytes.sha256_{hash}` | Данные передаются в памяти, MIME из mime_hint |

## Политики (ScholarPolicy)

Все стадии конфигурируются через единую `ScholarPolicy`:

| Секция | Параметры | Значения по умолчанию |
|--------|-----------|----------------------|
| `budgets` | `max_docs`, `max_bytes_total`, `max_claims_total`, `max_bytes_per_doc` | 16 docs, 20 MB, 2000 claims |
| `thresholds` | `min_doc_trust_tier` | `TrustTier.MEDIUM` |
| `docs` | `normalize_options`, `structure_options`, `chunk_options` | `DocChunkOptions(min_chunk_chars=1)` |
| `claims` | `extractor_id`, `extract_options`, `normalize_options`, `resolve_options` | `explicit_lines_v1` |
| `conflict` | `policy_id` | `policy.conflicts.default_v1` |
| `acquire` | `timeout_s`, `user_agent` | 10 с, `polisyos-scholar/1.0` |
| `persist_report` | булевый флаг | `True` |

Бюджеты из `ResearchIntent.budgets_v1` имеют приоритет над `ScholarPolicy.budgets` — политика задаёт дефолты, intent может переопределить.

## Ключевые типы

**Контракты** (определены в `core.contracts.scholar`):
- `ResearchIntent` — входной конверт: domain, topic, jurisdictions, seed_sources, budgets_v1, thresholds_v1, claim_targets
- `SourceSpec` — спецификация источника (kind + identity + payload)
- `KnowledgeBundleRef` / `EnrichmentReportRef` — CAS-ссылки на артефакты

**Внутренние типы** (`scholar.types`):
- `AcquireResult` — результат получения данных (raw_bytes + mime + DocSourceSpec)
- `DocPipelineRefs` / `ClaimsPipelineRefs` / `ReconcileRefs` — ссылки на промежуточные артефакты стадий
- `KnowledgeBundlePayloadV1` — полный payload бандла (Pydantic, `extra="forbid"`)
- `EnrichmentReportV1` — отчёт: статистика по docs/claims/conflicts/trust/quality
- `EnrichResultV1` — финальный результат: `knowledge_bundle_ref` + `bundle_id` + `report`

## Иерархия ошибок

```
ScholarError(stage, source_identity, details)
├── ScholarValidationError   (stage="validation")
├── ScholarDiscoverError     (stage="discover")
├── ScholarAcquireError      (stage="acquire")
├── ScholarDocsError         (stage="docs")
├── ScholarClaimsError       (stage="claims")
├── ScholarReconcileError    (stage="reconcile")
└── ScholarBundleError       (stage="bundle")
```

Каждое исключение несёт `stage`, `source_identity` и `details` dict для диагностики.

## Зависимости

| Модуль | Используемые компоненты |
|--------|------------------------|
| `core.artifacts` | `FileSystemCAS`, `ArtifactID`, `InputRef`, `SchemaInfo` |
| `core.contracts.scholar` | `ResearchIntent`, `SourceSpec`, `BudgetsV1`, `ThresholdsV1`, `KnowledgeBundleRef`, `EnrichmentReportRef` |
| `fabric.docs` | `DocSourceSpec`, `ingest_doc_bytes`, `normalize_doc`, `structure_doc`, `chunk_doc` |
| `fabric.claims` | `extract_claims_from_doc`, `normalize_claims`, `resolve_conflicts`, `ClaimExtractorRegistry` |
| `fabric.claims.persist` | `load_claim`, `load_doc_meta`, `load_json_artifact` |
| `fabric.io.db` | `SimulationDB` (опционально, для persist) |
| `fabric.world` | `persist_world_event`, `emit_world_event_facts`, `write_world_fact_segment` |
| `ir.world.trust` | `TrustAssessment`, `TrustTier` |
| `ir.world.event` | `WorldEvent`, `EventKind`, `ProvAgent`, `ProvActivity` |
| `ir.world.ids` | `stable_world_id_from_canon`, `world_event_id_from_payload` |

## Особенности реализации

- **Content-addressed storage** — все артефакты (бандлы, отчёты, промежуточные результаты) адресуются по содержимому через CAS. Детерминированный `bundle_id` гарантирует идемпотентность при одинаковых входах.
- **Провенанс** — каждый бандл сопровождается `WorldEvent` типа `KNOWLEDGE_BUNDLE_BUILD` с полным графом inputs/outputs и ProvAgent/ProvActivity.
- **Инкрементальная обработка документов** — стадии docs пропускаются, если CAS уже содержит результат (normalized_ref, structure_ref, chunks_ref).
- **Расширяемые экстракторы** — выбор экстрактора утверждений через `ClaimExtractorRegistry.select()` с учётом domain, jurisdiction, language и MIME-типа.
- **Фильтрация по доверию** — после reconcile документы с `TrustTier` ниже порога исключаются, связанные утверждения каскадно отфильтровываются.
