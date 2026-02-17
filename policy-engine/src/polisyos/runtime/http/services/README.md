# Runtime HTTP Services (`polisyos.runtime.http.services`)

`services/` — слой прикладной логики для runtime HTTP routes: индексация run, debug/timeline/lineage представления, artifact inspection и control-plane orchestration.

Документ отражает текущее состояние кода на **2026-02-17**.

## Структура и ответственность

- `run_index.py`
  - Строит кэш run-индекса из `core_runs_root` (TTL по умолчанию 2s).
  - Адаптирует `core_run` через `adapters/core_run.py`.
  - Поддерживает artifact->tenant mapping для tenant enforcement.

- `timeline.py`
  - Парсит `trace.jsonl` в ordered timeline events.
  - Строит summary: phase/node counts, duration, cache hit/store/bypass.

- `debug.py`
  - Возвращает node debug, governance debug, run errors, agent pipeline и workflow graph view.
  - Объединяет `workflow_report` + trace timeline.
  - Редактирует чувствительные поля (`token`, `password`, `authorization`, ...).

- `lineage.py`
  - Обертка над `resolve_dependency_graph`.
  - Возвращает объединенный lineage view с `is_complete`, missing/corrupted ids и графом зависимостей.

- `artifact_inspector.py`
  - Manifest/content/schema/lineage представления для CAS-артефактов.
  - Preview лимит: default 64 KiB; clamp диапазона `1024..2_000_000`.
  - Sensitive kind redaction + custom redaction hooks.

- `control.py`
  - Control-plane orchestration:
    - workflow launch (`/runs`), NL launch (`/runs/nl`);
    - ingestion/retrieval (`/data/*`);
    - connectors/profiles/cache endpoints;
    - Lex batch trigger/status/stats/search.
  - Для фоновых операций использует `TaskRunner`.

- `task_runner.py`
  - In-process thread-pool executor (`ThreadPoolExecutor`).
  - Подходит для local/dev режима; не замена внешней job queue.

- `adapters/core_run.py`
  - Нормализует файловый run (`trace.jsonl` + `core.run_manifest`) в `CoreRunAdapterResult`.
  - Извлекает ссылки на workflow/experiment/decision artifacts.

## Важные особенности

- Источник run-данных для Runtime API: только `core_run`.
- `run_index` считает run доступным только при наличии `trace.jsonl` в директории запуска.
- Tenant enforcement артефактов опирается на mapping, сформированный из root/manifest/trace/workflow refs run.
- Control-service хранит Lex pipeline статус в памяти процесса (эпhemeral state).

## Зависимости слоя

- `polisyos.core.artifacts.*` — CAS, artifact IDs, lineage graph.
- `polisyos.core.contracts.runtime/control` — DTO responses/requests.
- `polisyos.core.trace.record.TraceRecord` — timeline/debug extraction.
- `polisyos.scientist`, `polisyos.fabric`, `polisyos.lex` — backend реализации control-plane операций.
