# Runtime HTTP Services (`polisyos.runtime.http.services`)

`services/` — прикладной слой runtime API: run index, timeline/debug/lineage views, artifact inspection и control-plane orchestration.

Документ отражает текущее состояние кода на **2026-03-03**.

## Структура и ответственность

- `run_index.py`
  - Кэширует run-индекс из `core_runs_root` (TTL по умолчанию 2s, cursor pagination).
  - Адаптирует `core_run` через `adapters/core_run.py`.
  - Поддерживает фильтрацию по status/time/tenant.
  - Строит `artifact_id -> tenant_id` mapping для tenant enforcement.

- `adapters/core_run.py`
  - Читает `trace.jsonl`, ищет `RUN_FINALIZED` и `core.run_manifest` ref.
  - Нормализует данные в `CoreRunAdapterResult` и вытаскивает workflow/experiment/decision refs.
  - При ошибках манифеста возвращает run со `status="unknown"` и warning, а не падает.

- `timeline.py`
  - Конвертирует `TraceRecord` в детерминированный ordered timeline.
  - Строит summary по phase/status/cache метрикам и длительности выполнения.

- `debug.py`
  - Формирует `nodes`, `node debug`, `governance`, `errors`, `agent pipeline`, `workflow graph`.
  - Объединяет несколько источников: workflow report, workflow spec, trace timeline, experiment state, decision packet.
  - Санитизирует чувствительные поля (`authorization`, `password`, `token`, `api_key`, ...).
  - Для agent pipeline поддерживает fallback-цепочку источников: `audit_trail -> timeline -> reflexion/model-variant params`.

- `lineage.py`
  - Агрегирует dependency graph для одного или нескольких корневых артефактов.
  - Возвращает `is_complete`, missing/corrupted IDs, nodes/edges и суммарный размер.

- `artifact_inspector.py`
  - Отдаёт `manifest/content/schema/lineage` представления артефактов CAS.
  - Preview limit: default 64 KiB, clamp `1024..2_000_000`.
  - Автоматически редактирует sensitive kinds (`secret|token|credential|password|key_material`) и поддерживает кастомные redaction hooks.

- `control.py`
  - Оркестрация `/api/v1/control/*`:
  - workflow launch (`/runs`) и NL launch (`/runs/nl`);
  - fabric ingestion/resolve/discover/preview/catalog/promotion;
  - connectors/profiles/cache introspection;
  - Lex batch trigger/status/stats/search.
  - Кэширует RetrievalService и использует `TaskRunner` для фоновых операций.

- `task_runner.py`
  - In-process `ThreadPoolExecutor` (без персистентной очереди задач).
  - Подходит для local/dev; в production нужен внешний job runner.

## Control-service: важные детали

- `launch_workflow_run(...)` запускает `scientist.run_experiment(...)` в фоне, собирая `state_payload` из обязательного data source и optional refs.
- `launch_nl_run(...)` поддерживает multi-model execution (если разрешено), budget guards, evaluator/preflight/reproducibility артефакты и fallback на mock agents при недоступном LLM gateway.
- В NL path возможна auto-materialization retrieval результатов в `DataSnapshot`/`InputBindings`.
- `run_data_ingestion(...)` поддерживает режимы orchestrated, `batch_incremental`, `streaming_windowed`, а также record/replay ветки.
- Статусы Lex pipeline (`_lex_pipelines`) хранятся в памяти процесса и теряются при рестарте.

## Важные ограничения

- Источник run-данных для runtime API: только `core_run`.
- Run включается в индекс только при наличии `trace.jsonl`.
- Tenant enforcement артефактов опирается на mapping, собранный из известных run refs; «чужие»/непривязанные артефакты режутся политикой.

## Зависимости слоя

- `polisyos.core.artifacts.*` — CAS, manifests, dependency graph.
- `polisyos.core.contracts.runtime/control` — API DTO.
- `polisyos.core.trace.record.TraceRecord` — timeline/debug extraction.
- `polisyos.scientist`, `polisyos.fabric`, `polisyos.lex` — backend control-plane execution.
