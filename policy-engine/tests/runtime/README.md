# Runtime Tests

`tests/runtime` проверяет runtime-layer: replay/completeness, manifest path semantics и HTTP API контракты.

Актуально на **11 марта 2026**.

## Состав

- `18` файлов `test_*.py`
- `1` `conftest.py` (в `runtime/http/`)

## Структура

| Подкаталог | `test_*.py` | Что покрывает |
|---|---:|---|
| `runtime/` (корень) | 3 | replay completeness/verification, manifest path portability |
| `runtime/http/` | 15 | runs/timeline/debug/insights/control/artifact APIs + OpenAPI hardening + feedback loop surfaces |

## Ключевые инварианты

- API выдает только `source_kind="core_run"` (без legacy runtime surface).
- Problem+JSON contract для ошибок (`application/problem+json`).
- Tenant/authz guards и redaction чувствительных данных.
- `debug` surfaces покрывают `feedback` и `run compare`; `control` surfaces покрывают `feedback/evaluate` и human-gated `reissue`.
- Replay completeness требует `input_bindings_ref`.
- Relative path semantics для runtime manifest (перенос run-root не ломает ссылки).

## Зависимости

- `runtime/http` использует `fastapi.testclient`; часть тестов пропускается без `fastapi`/`PyJWT`.

## Связи с кодом

- `policy-engine/src/polisyos/runtime`
- `policy-engine/src/polisyos/runtime/http`
- `policy-engine/src/polisyos/core/run`
- `policy-engine/src/polisyos/core/security`

## Запуск

```bash
pytest tests/runtime -q
pytest tests/runtime/http -q

# точечно
pytest tests/runtime/test_replay_runtime.py -q
pytest tests/runtime/http/test_runs_api.py -q
pytest tests/runtime/http/test_control_api.py -q
```
