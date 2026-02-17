# Scholar Orchestrator

`orchestrator` содержит runtime-оркестрацию enrichment pipeline и сборку итогового bundle.

## Состав

- `enrich.py`:
  - основной flow `enrich_topic()`
  - валидация intent, resolve budgets/thresholds, discover/acquire/docs/claims/reconcile/filtering
  - сборка `summary`, `policy_ids_used`, `report_payload`
- `bundle.py`:
  - `compute_bundle_id()` (детерминированный world-id префикса `bundle`)
  - `build_knowledge_bundle_payload()`
  - `persist_bundle_and_event()` (CAS persist + world event + fact segment index)

## Детали `enrich_topic()`

1. **Validation и policy merge**
- Проверяется обязательность `intent.domain` и `intent.seed_sources`.
- Поддержаны `budgets_v1/thresholds_v1` и legacy `budgets` (включая строковые/float значения с валидацией).

2. **Discover/acquire**
- Источники нормализуются и дедупятся через `discover.normalize_seed_sources`.
- Acquire идет по `local_file` / `bytes` / `url` с ограничениями `max_bytes_per_doc` и `max_bytes_total`.
- При превышении общего бюджета добавляется `notes += ["stopped:max_bytes_total"]`.

3. **Docs pipeline**
- На каждый документ вызываются `ingest_doc_bytes`, затем `normalize_doc`, `structure_doc`, `chunk_doc`.
- Если `doc_meta` уже содержит `normalized_ref/structure_ref/chunks_ref`, этап пропускается.
- В отчет пишется статистика `docs.skipped`.

4. **Claims + reconcile**
- Перед extract выполняется bootstrap extractor-компонентов:
  `ENTRY_POINT_GROUP_SCHOLAR_EXTRACTORS` + `ENTRY_POINT_GROUP_LEX_EXTRACTORS`.
- Для каждого doc выбирается extractor через registry selection.
- После normalize claims вызывается `resolve_conflicts()`.
- `resolve_conflicts()` поддерживает `storage` (предпочтительно) и legacy `db`.

5. **Filtering**
- Документы отбираются по trust tier (`thresholds.min_doc_trust_tier`).
- Claims фильтруются:
  - по `intent.claim_targets` (predicate id),
  - по цитированиям: claim исключается, если цитирует только невыбранные docs.

6. **Bundle/report persist**
- `bundle_id` считается от `intent_core + doc_version_ids + claim_ids + policy_ids_used`.
- `build_freshness_metadata()` использует максимальный `retrieved_at` по выбранным документам.
- `persist_bundle_and_event()` сохраняет:
  - `scholar.knowledge_bundle`
  - опционально `scholar.enrichment_report` (`persist_report`)
  - world event `KNOWLEDGE_BUNDLE_BUILD`

## Важные инварианты

- `run_token` влияет только на имена fact segments, но не на `bundle_id`.
- Детерминизм bundle сохраняется при одинаковых входах/policy.
- Report всегда формируется в памяти; в CAS сохраняется только если `persist_report=True`.
- Ошибки нормализуются в `Scholar*Error` по stage.

## Зависимости по слоям

- Контракты/артефакты: `core.contracts.scholar`, `core.artifacts.*`
- Обработка документов: `fabric.docs`
- Claims/reconcile: `fabric.claims`, `fabric.storage`
- Provenance/world: `fabric.world`, `ir.world.*`

