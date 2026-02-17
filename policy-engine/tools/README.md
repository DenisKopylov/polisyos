# Tools — инженерный слой CLI и quality gates

`tools/` содержит standalone-скрипты для поддержки разработки, релизного контура и CI/CD в `policy-engine`.

По состоянию на **17 февраля 2026** структура разделена на тематические подпапки, чтобы не перегружать один `README`.

## Роль в архитектуре

```text
tools/*  ->  src/polisyos/*, schemas/*, frontend/*, runs/*, data/*
```

- `tools/` не является runtime-слоем приложения.
- Допустимое направление зависимости: `tools/* -> src/polisyos/*`.
- Скрипты запускаются вручную, из pre-commit или из GitHub Actions.

## Карта подпапок

| Папка | Роль | Детали |
|---|---|---|
| `tools/lint` | Архитектурные и import-gates, freeze-метрики | [`tools/lint/README.md`](./lint/README.md) |
| `tools/diagnostics` | Диагностика ABI/контрактов/производительности и локальные проверки среды | [`tools/diagnostics/README.md`](./diagnostics/README.md) |
| `tools/runtime` | OpenAPI/клиент Runtime API и утилиты для legacy runs | [`tools/runtime/README.md`](./runtime/README.md) |
| `tools/connectors` | Проверка контрактов коннекторов и scaffold новых источников | [`tools/connectors/README.md`](./connectors/README.md) |
| `tools/migrations` | Миграции артефактов и перенос DuckDB -> PostgreSQL | [`tools/migrations/README.md`](./migrations/README.md) |
| `tools/demos` | Исследовательские и демонстрационные сценарии | [`tools/demos/README.md`](./demos/README.md) |
| `tools/benchmarks` | Ручные нагрузочные/производительные smoke-скрипты | [`tools/benchmarks/README.md`](./benchmarks/README.md) |

## Что реально используется автоматически

- Pre-commit:
  - `tools/lint/lint_imports.py`
  - `tools/diagnostics/gen_schema.py --check`
- GitHub Actions:
  - `arch.yml`: import/foundry/scholar/state_reads/runtime/connector gates
  - `abi.yml`: генерация ABI snapshots + `abi_diff.py`
  - `arch-freeze.yml`: freeze-метрики и сравнение baseline
  - `perf.yml`: `check_perf_regression.py`

## Локальный запуск

Рабочая директория: `policy-engine/`.

```bash
PYTHONPATH=src:. uv run python tools/<subdir>/<script>.py --help
```

Если окружение установлено как editable package (типичный CI-контур), допустим и формат `python3 tools/...`.

## Важные ограничения (актуальный дрейф)

- В репозитории нет исходников `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store`; скрипты `tools/diagnostics/check_udf_perf.py` и часть UDF-демо работают как legacy и требуют актуализации.
- `tools/migrations/migrate.py` импортирует `POLICY_IR_CURRENT_VERSION` из `polisyos.common.migrations`, но этот символ там не экспортируется.
- Значимая часть `tools/demos/*` и `tools/benchmarks/*` использует старые пути `foundry` (например, `foundry.domain.state`, `foundry.engine.kernel`) и не входит в CI-гейты.
