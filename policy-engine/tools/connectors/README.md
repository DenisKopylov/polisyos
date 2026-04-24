# tools/connectors

Инструменты жизненного цикла коннекторов: проверка контрактов и генерация каркаса новых источников.

## Роль в системе

- гарантировать корректную эволюцию схем коннекторов;
- ускорять добавление новых коннекторов с базовым test harness.

## Скрипты

| Скрипт               | Что делает                                                                                              | Где используется                       |
| -------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| `check_contracts.py` | Сравнивает текущие contracts с snapshot, валидирует required version bump, умеет `--check` и `--update` | `arch.yml` (`--check`) и ручной запуск |
| `scaffold.py`        | Генерирует source+test scaffold для типа `REST/CSV/SQL/SDMX`                                            | ручной запуск                          |

## Связь с другими директориями

- `src/polisyos/fabric/connectors/sources/*` (источники коннекторов)
- `src/polisyos/fabric/connectors/sources/_contracts/*` (реестр контрактов)
- `schemas/snapshots/connectors/contracts.json` (snapshot для gate)
- `tests/fabric/connectors/sources/*` (генерируемые/поддерживаемые тесты)

## Типовой запуск

```bash
PYTHONPATH=src:. uv run python tools/connectors/check_contracts.py --check
PYTHONPATH=src:. uv run python tools/connectors/check_contracts.py --update
PYTHONPATH=src:. uv run python tools/connectors/scaffold.py create --name MySource --type REST --dry-run
```

## Примечания

- `check_contracts.py` ожидает детерминированный snapshot и сравнивает версии через `SchemaEvolution`.
- `scaffold.py` не регистрирует коннектор автоматически: после генерации нужны ручные доработки и регистрация в реестре.
