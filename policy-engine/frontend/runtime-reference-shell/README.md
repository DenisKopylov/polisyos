# `runtime-reference-shell` — референсный UI для Runtime API v1

`runtime-reference-shell` демонстрирует API-first путь отладки runtime без прямых чтений DB/CAS/файловой системы.

## Роль и границы

- Роль: опорный UI для run explorer/debug/artifact inspector в рамках Runtime API v1.
- Формат: статический frontend (`index.html` + `app.js` + `styles.css`) без сборки.
- Граница ответственности: только read-only API-вызовы через `RuntimeApiClient`.
- Не-цель: продуктовый UX (SSO, роли, persisted state, write-операции).

## Карта модулей

| Файл | Назначение |
| --- | --- |
| `index.html` | Разметка страниц, форм, табов и зон вывода |
| `app.js` | Управление состоянием UI, запросы к API, рендер таблиц/JSON |
| `styles.css` | Визуальная тема и адаптивная верстка |

## Функциональные поверхности

- `Run List`: `GET /api/v1/runs` с фильтрами `limit`/`status`.
- `Run Timeline + Node Graph`: `GET /api/v1/runs/{run_id}/timeline` и `GET /api/v1/runs/{run_id}/nodes`.
- `Node Debug Panel`: `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`.
- `Artifact Inspector`: `GET /api/v1/artifacts/{artifact_id}` + `content`/`lineage`/`schema`.

Дополнительно:
- click по строке run проставляет `run_id` в формы timeline/debug;
- `Artifact Content` запрашивается с `max_bytes=4096` (preview-режим).

## Архитектурная связь

`app.js` импортирует `../runtime-api-client/runtimeApiClient.js`, поэтому shell напрямую зависит от актуальности сгенерированного клиента и OpenAPI-контракта.

## Ограничения текущей реализации

- UI не экспонирует все методы клиента (например governance debug, run errors, run lineage не вынесены в отдельные страницы).
- Нет UI для пользовательских заголовков авторизации; при защищенном API может потребоваться расширение shell.
- Нет клиентского router/state persistence; вкладки и формы управляются локальным JS-состоянием.

## Локальный запуск

Из корня `policy-engine/`:

```bash
PYTHONPATH=src uv run --extra multi-tenant --extra test python - <<'PY'
from polisyos.runtime.http.app import create_runtime_api_app
import uvicorn

app = create_runtime_api_app()
uvicorn.run(app, host="127.0.0.1", port=8000)
PY

cd frontend/runtime-reference-shell
python -m http.server 4173
```

Открыть `http://127.0.0.1:4173`, указать `API Base URL`, затем проверить страницы `Run List` -> `Timeline` -> `Node Debug` -> `Artifacts`.
