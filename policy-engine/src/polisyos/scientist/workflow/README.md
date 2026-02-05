# Workflow Layer: Движки рабочих процессов

**Workflow engines для декларативного управления экспериментами**

Workflow предоставляет абстракции и реализации движков для декларативного управления процессами.

## Структура

```
workflow/
├── engine_base.py    # WorkflowEngine абстракции
├── engine_langgraph.py # LangGraph движок для complex workflows
└── engine_simple.py  # Simple loop движок для basic scenarios
```

## Ключевые компоненты

- **WorkflowEngine**: Унифицированный интерфейс для разных движков
- **LangGraph Engine**: Продвинутый движок с conditional routing и state management
- **Simple Loop Engine**: Легковесный движок для последовательных процессов
- **WorkflowEngineFactory**: Фабрика для создания движков по конфигурации

## API Использование

```python
from polisyos.scientist.workflow.engine_base import WorkflowEngineFactory

# Создание движка
engine = WorkflowEngineFactory.create("langgraph")

# Выполнение workflow
result = await engine.execute(workflow_spec, initial_state)
```

## Связи

- Используется **workflows** для workflow definitions
- Интегрируется с **engine** для node execution
- Управляет **kernel** phase transitions