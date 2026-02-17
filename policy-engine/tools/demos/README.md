# tools/demos

Демонстрационные и исследовательские сценарии. Это не production-gates и не CI-контур.

## Роль

- быстрые эксперименты с идеями и API;
- ручная проверка гипотез для `foundry/fabric`.

## Скрипты

| Скрипт | Идея | Текущее состояние |
|---|---|---|
| `run_laffer_demo.py` | JAX/Optax demo по кривой Лаффера | частично актуален, ручной запуск |
| `run_export_demo.py` | Экспорт simulation-данных в DuckDB | legacy imports (`foundry.domain.state`, `foundry.engine.kernel`) |
| `run_mechanism_design.py` | E2E differentiable mechanism design | legacy imports и path drift |
| `run_udf_query_demo.py` | Пример UDF panel/snapshot-запросов | требует отсутствующий `polisyos.fabric.udf.*` |
| `run_udf_hybrid_demo.py` | Гибрид DuckDB + graph UDF | требует отсутствующие `polisyos.fabric.udf.*` и `polisyos.fabric.io.graph_store` |

## Связь с репозиторием

- исторически используют `src/polisyos/foundry/*`, `src/polisyos/fabric/*`, `data/*`
- не подключены к GitHub Actions как обязательные quality gates

## Примечания

- Эти скрипты полезны как reference/examples, но не как источник истинной compatibility-матрицы.
- Перед запуском любого сценария проверяйте актуальность импортов относительно текущего `src/polisyos`.
