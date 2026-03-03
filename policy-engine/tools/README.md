# Tools — инженерный CLI-слой и quality gates

`tools/` содержит standalone-скрипты, которые поддерживают архитектурные проверки, контрактные гейты, миграции и операционные задачи вокруг `policy-engine`.

Актуализировано: **3 марта 2026**.

## Роль в архитектуре

```text
tools/* -> src/polisyos/*, schemas/*, frontend/*, docs/reports/*, runs/*, data/*
```

- `tools/` не является runtime-слоем приложения.
- Базовое направление зависимостей: `tools/* -> src/polisyos/*`.
- Исполнение: локально, в `pre-commit`, и в GitHub Actions.

## Карта подпапок

| Папка | Роль в системе | Auto/Manual |
|---|---|---|
| `tools/lint` | Архитектурные import-gates, freeze-метрики, debt/baseline контроль | CI + local |
| `tools/diagnostics` | ABI/контрактные проверки, SCM v3 verification, env/provenance диагностика | CI + local |
| `tools/runtime` | Runtime API OpenAPI/client контур и cutover-утилиты для `runs/` | CI + release + ops |
| `tools/connectors` | Контрактные проверки коннекторов и scaffold новых источников | CI + local |
| `tools/migrations` | Миграции артефактов и перенос данных DuckDB -> PostgreSQL | ops/manual |
| `tools/demos` | Демонстрационные и исследовательские сценарии | local only |
| `tools/benchmarks` | Ручные JAX smoke/benchmark сценарии | local only |

Подробности по каждой папке:
- [`tools/lint/README.md`](./lint/README.md)
- [`tools/diagnostics/README.md`](./diagnostics/README.md)
- [`tools/runtime/README.md`](./runtime/README.md)
- [`tools/connectors/README.md`](./connectors/README.md)
- [`tools/migrations/README.md`](./migrations/README.md)
- [`tools/demos/README.md`](./demos/README.md)
- [`tools/benchmarks/README.md`](./benchmarks/README.md)

## Что запускается автоматически

| Контур | Основные скрипты |
|---|---|
| `pre-commit` | `tools/lint/lint_imports.py`, `tools/diagnostics/gen_schema.py --check` |
| `arch.yml` | import/foundry/scholar/state-reads/runtime/connectors gates |
| `abi.yml` | `gen_schema.py`, `abi_diff.py` |
| `arch-freeze.yml` | `lint_connector_hardening.py`, `collect_arch_metrics.py`, `compare_baseline.py` |
| `perf.yml` | `check_perf_regression.py` |

## Связь с другими директориями

- `src/polisyos/*`: источник правил, контрактов и runtime API, которые валидируют скрипты.
- `schemas/snapshots/*`: ABI/connector/OpenAPI snapshots.
- `frontend/runtime-api-client/*`: generated client из `tools/runtime`.
- `docs/reports/*`: verification evidence/matrix, включая SCM v3 отчеты.
- `runs/*`, `data/*`: операционные входы/выходы migration и diagnostics сценариев.

## Базовый локальный запуск

Рабочая директория: `policy-engine/`.

```bash
PYTHONPATH=src:. uv run python tools/<subdir>/<script>.py --help
```

В CI и editable окружениях допустим и формат `python3 tools/...`.

## Актуальные ограничения

- В `src/polisyos` отсутствуют `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store`; UDF-скрипты в `tools/diagnostics` и часть `tools/demos` сейчас legacy.
- `tools/migrations/migrate.py` импортирует `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но этот символ в пакете не экспортируется.
- Значимая часть `tools/demos/*` и `tools/benchmarks/*` использует старые импорты `foundry` и не входит в обязательные CI-gates.
