# `runtime-reference-shell` — статический диагностический UI

`runtime-reference-shell` это легковесный reference UI для ручной проверки Runtime API v1.

## Роль в системе

- Быстрый API-only путь для диагностики run/timeline/node/artifact.
- Работает без npm/toolchain: только статические файлы.
- Использует сгенерированный `RuntimeApiClient` из соседней директории.

Не является продуктовым интерфейсом и не покрывает control-plane write-функции.

## Состав

| Файл | Назначение |
| --- | --- |
| `index.html` | Табы, формы ввода и контейнеры для вывода данных |
| `app.js` | Локальное UI-состояние, вызовы API, рендер таблиц/JSON |
| `styles.css` | Тема и responsive-верстка |

## Что поддерживается

- `Run List`: `GET /api/v1/runs` (`limit`, `status`).
- `Timeline + Node Graph`: `GET /api/v1/runs/{run_id}/timeline` + `GET /api/v1/runs/{run_id}/nodes`.
- `Node Debug`: `GET /api/v1/debug/runs/{run_id}/nodes/{alias}`.
- `Artifact Inspector`: manifest/content/lineage/schema для `artifact_id`.

Полезные детали:
- клик по строке run переносит `run_id` в формы timeline/debug;
- content preview запрашивается с `max_bytes=4096`.

## Связь с другими модулями

- Импортирует `../runtime-api-client/runtimeApiClient.js`.
- Чувствителен к drift OpenAPI/генерированного клиента.
- Удобен как smoke-check после регенерации `runtime-api-client`.

## Ограничения

- Нет страниц для части endpoint-ов (например run lineage, governance debug, run errors).
- Нет auth UI для кастомных заголовков.
- Нет router/persisted state.

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

Открыть `http://127.0.0.1:4173` и указать `API Base URL`.
