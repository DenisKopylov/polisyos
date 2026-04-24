# tools/demos

Демонстрационные и исследовательские сценарии. Это не production-gates и не CI-контур.

Демо-команды доступны для discovery через `polisyos-tools demos --help`, но
legacy/quarantined сценарии намеренно блокируются unified CLI без явного
`--allow-deprecated`.

## Роль

- быстрые эксперименты с идеями и API;
- ручная проверка гипотез для `foundry/fabric`.

## Скрипты

| Скрипт                             | Идея                                                         | Текущее состояние                                                                |
| ---------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------- |
| `run_laffer_demo.py`               | JAX/Optax demo по кривой Лаффера                             | частично актуален, ручной запуск                                                 |
| `run_foundry_ws9_frontier_demo.py` | Smoke walkthrough для WS-9 frontier causal/ML/policy methods | актуален, ручной запуск                                                          |
| `run_export_demo.py`               | Экспорт simulation-данных в DuckDB                           | legacy imports (`foundry.domain.state`, `foundry.engine.kernel`)                 |
| `run_mechanism_design.py`          | E2E differentiable mechanism design                          | legacy imports и path drift                                                      |
| `run_udf_query_demo.py`            | Пример UDF panel/snapshot-запросов                           | требует отсутствующий `polisyos.fabric.udf.*`                                    |
| `run_udf_hybrid_demo.py`           | Гибрид DuckDB + graph UDF                                    | требует отсутствующие `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store` |

## Quarantine policy

- `run_udf_query_demo.py` и `run_udf_hybrid_demo.py` находятся в legacy
  quarantine, потому что их зависимости отсутствуют в текущем пакете.

- `run_export_demo.py` и `run_mechanism_design.py` остаются deprecated reference
  scripts до переписывания на текущие Foundry contracts.

- Quarantine metadata и replacements зафиксированы в
  [`tools/_deprecated/README.md`](../_deprecated/README.md) и
  `tools.registry`.

## Связь с репозиторием

- исторически используют `src/polisyos/foundry/*`, `src/polisyos/fabric/*`, `data/*`
- не подключены к GitHub Actions как обязательные quality gates

## Примечания

- Эти скрипты полезны как reference/examples, но не как источник истинной compatibility-матрицы.
- Перед запуском любого сценария проверяйте актуальность импортов относительно текущего `src/polisyos`.
