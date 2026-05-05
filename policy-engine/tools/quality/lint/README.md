# tools/quality/lint

Архитектурные и quality-гейты для структуры зависимостей, import-policy и freeze-процесса.

## Роль в системе

- проверка границ между пакетами `src/polisyos/*`;
- контроль исключений (`architecture/imports/exceptions.toml`) и долгов (`import_debt_register.csv`);
- сбор метрик для сравнения с baseline в CI.

## Скрипты

| Скрипт                        | Что делает                                                                           | Где используется                                          |
| ----------------------------- | ------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| `lint_imports.py`             | Главный import-gate (`ARCH00x`), циклы, deep-import/legacy-ограничения               | pre-commit, `arch.yml`, `arch-freeze.yml` (через метрики) |
| `lint_foundry.py`             | Ban-list импортов и builtins в `foundry` (policy: `standard/mixed/no_jax`)           | `arch.yml`                                                |
| `check_scholar_imports.py`    | Запрещает связь `scholar -> polisyos.fabric.io.db`                                   | `arch.yml`                                                |
| `lint_connector_hardening.py` | P7-инварианты production-коннекторов (`world_bank`, `eurostat`, `ukons`)             | `arch-freeze.yml`                                         |
| `lint_connectors.py`          | Law A/B для `fabric/connectors` (изоляция от `scientist`/`foundry`)                  | ручной запуск, используется в freeze-метриках             |
| `collect_arch_metrics.py`     | Собирает freeze-артефакты (`architecture/imports/gate_summary.json`, `architecture/imports/gate_baseline.txt`, `ruff_stats.txt`, ...) | `arch-freeze.yml`                                         |
| `compare_baseline.py`         | Сравнивает baseline/current, проверяет exception policy и deep-import drift          | `arch-freeze.yml`                                         |
| `lint_foundry_data_plane.py`  | P8-инварианты data plane (workflow aliases, adapter, assumptions)                    | ручной запуск                                             |
| `lint_legacy_cutover.py`      | P10-инварианты cutover legacy-runtime/facade                                         | ручной запуск                                             |

## Входы и связи с репозиторием

- `architecture/imports/policy.toml`, `architecture/imports/exceptions.toml`, `architecture/imports/exceptions.md`
- `import_debt_register.csv`
- `architecture/imports/gate_summary.json`, `architecture/imports/gate_baseline.txt`
- исходники: `src/polisyos/**`
- CI-конфиги: `ops/ci/templates/workflows/arch.yml`,
  `ops/ci/templates/workflows/arch-freeze.yml`

## Типовой локальный запуск

```bash
PYTHONPATH=src:. uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml
PYTHONPATH=src:. uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml --changed-only --cache-dir _cache/polisyos-tools/cache --baseline-label ci --skip-if-unchanged
PYTHONPATH=src:. uv run python tools/quality/lint/lint_imports.py --policy architecture/imports/policy.toml --exceptions architecture/imports/exceptions.toml --fix
PYTHONPATH=src:. uv run python tools/quality/lint/lint_foundry.py --repo-root .
PYTHONPATH=src:. uv run python tools/quality/lint/lint_foundry.py --repo-root . --fix
PYTHONPATH=src:. uv run python tools/quality/lint/check_scholar_imports.py
PYTHONPATH=src:. uv run python tools/quality/lint/compare_baseline.py --current .arch-freeze/current/summary.json --mode dry-run
```

## Примечания

- `compare_baseline.py` имеет режимы `dry-run` и `blocking`.
- `lint_imports.py` учитывает `TYPE_CHECKING`-импорты только при флаге `--allow-type-checking`.
- `lint_imports.py` использует content-addressable parse cache и умеет `--changed-only`; persisted baseline hash применяется только после успешного прогона, поэтому failing state не начинает silently skip-аться в CI.
- `lint_imports.py --fix` сейчас выполняет только безопасную mechanical операцию: canonical rewrite `architecture/imports/exceptions.toml`. Source imports он не переписывает автоматически.
- `lint_foundry.py` использует registry из `tools/quality/lint/rules/`; новые domain-specific правила можно добавить отдельным модулем без правок в core scanner.
- `lint_foundry.py --fix` ограничен safe autofix-ами. На текущем этапе автоматически удаляются только standalone `print()` debug-вызовы, остальные нарушения остаются report-only.
