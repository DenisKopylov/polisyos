# Workflows Layer: Определения рабочих процессов

**Workflow definitions и builders для scientist experiments**

Workflows содержит определения и builders для стандартных workflow конфигураций.

## Структура

```
workflows/
├── builder.py        # Workflow builders и factories
├── default.py        # Default scientist workflow configuration
└── __init__.py       # Exports
```

## Ключевые компоненты

- **Workflow Builders**: Фабрики для создания workflow specifications
- **Default Workflow**: Стандартная конфигурация scientist эксперимента
- **run_default_workflow()**: Основная entry point функция

## API Использование

```python
from polisyos.scientist.workflows.builder import run_default_workflow

# Запуск стандартного scientist workflow
result = run_default_workflow(initial_experiment_state)
```

## Связи

- Использует **workflow** engines для execution
- Интегрируется с **engine** через node registry
- Управляет полным **scientist** pipeline