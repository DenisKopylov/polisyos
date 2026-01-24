# Demo Tests

Тесты интеграции с демонстрационными скриптами и инструментами из директории `tools/demos/`.

**Последнее обновление:** Январь 2026
**Уровень:** Integration (демо-скрипты)
**Зависимости:** tools/demos/ скрипты, pathlib

## Архитектурный контекст

Demo тесты обеспечивают корректную интеграцию между тестовой инфраструктурой и демонстрационными скриптами. Они проверяют, что demo-скрипты из `tools/demos/` корректно запускаются и завершаются без ошибок.

## Структура тестов

```
demos/
└── run_laffer_demo.py            # Тест запуска демо Laffer curve из tools/demos/
```

## Категории тестов

### Laffer Demo (`run_laffer_demo.py`)

**Цель:** Валидация интеграции с демонстрационным скриптом кривой Лаффера.

**Ключевые аспекты:**
- **Path Resolution**: Корректное разрешение относительных путей к репозиторию
- **Script Execution**: Успешный запуск demo-скрипта через `runpy.run_path`
- **Import Validation**: Проверка доступности модулей и зависимостей
- **Runtime Integrity**: Завершение выполнения без исключений

**Принципы:**
- **Tool Integration**: Прямая интеграция с инструментами из `tools/` директории
- **Repository Path Handling**: Корректная навигация по структуре репозитория
- **Execution Safety**: Изолированное выполнение без side effects на основную систему
- **Dependency Validation**: Проверка доступности всех необходимых модулей

## Запуск тестов

```bash
# Все demo тесты
pytest tests/demos/ -v

# Конкретный demo тест
pytest tests/demos/run_laffer_demo.py -v
```

## Связи с другими модулями

### Зависимости Demo Tests

**Tools Directory** (`tools/demos/`):
- **Laffer Demo Script**: Демонстрационный скрипт для кривой Лаффера
- **Path Resolution**: Относительные пути к корню репозитория

### Архитектурные инварианты

- **Repository Structure**: Сохранение约定ной структуры репозитория
- **Tool Accessibility**: Demo скрипты доступны из стандартных locations
- **Execution Environment**: Совместимость с тестовым окружением

## Разработка и расширение

### Добавление новых demo тестов

1. Создайте соответствующий demo скрипт в `tools/demos/`
2. Добавьте тест в `tests/demos/` с pattern `run_{demo_name}_demo.py`
3. Используйте `runpy.run_path` для выполнения скрипта
4. Проверяйте успешное завершение без исключений
5. Валидируйте path resolution к корню репозитория

### Структура demo теста

```python
from __future__ import annotations

import runpy
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "tools" / "demos" / "{demo_name}_demo.py"
    runpy.run_path(str(script), run_name="__main__")


if __name__ == "__main__":
    main()
```

## Troubleshooting

### Распространенные проблемы

**Path resolution failures:**
```bash
# Проверьте структуру директорий
find . -name "*laffer*" -type f
# Убедитесь что tools/demos/ существует
```

**Import errors:**
```bash
# Проверьте доступность модулей
python -c "import polisyos; print('Policy OS available')"
```

**Script execution failures:**
```bash
# Запустите demo скрипт вручную
python tools/demos/run_laffer_demo.py
```