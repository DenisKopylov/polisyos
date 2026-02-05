# Engine Layer: Workflow execution engine

**ПлаггABLE workflow execution с node registry и state management**

Engine предоставляет execution engine для декларативных workflow с pluggable nodes, registry и state management.

## Структура

```
engine/
├── builtins/        # Built-in workflow nodes
├── context.py       # Execution context
├── errors.py        # Engine-specific errors
├── executor.py      # WorkflowExecutor
├── protocol.py      # Node, NodeSpec protocols
├── registry.py      # NodeRegistry, discover_nodes
├── state.py         # ExperimentState (90+ полей)
├── telemetry.py     # Engine telemetry
└── workflow_spec.py # WorkflowSpec, NodeInvocation
```

## Ключевые компоненты

- **WorkflowExecutor**: Основной движок выполнения workflow
- **NodeRegistry**: Registry для pluggable workflow nodes
- **ExperimentState**: Центральное состояние эксперимента (90+ полей)
- **Built-ins**: Встроенные узлы (emit_artifact, noop, set_state)
- **Protocol**: Typed contracts для node implementations

## API Использование

```python
from polisyos.scientist.engine.executor import WorkflowExecutor
from polisyos.scientist.engine.registry import discover_nodes

# Создание executor с registry
registry = discover_nodes()
executor = WorkflowExecutor(registry=registry)

# Выполнение workflow
result = await executor.execute(workflow_spec, initial_state)
```

## Связи

- Интегрируется с **agent** layer через node implementations
- Управляет **kernel** для FSM transitions
- Использует **governance** для validation passes