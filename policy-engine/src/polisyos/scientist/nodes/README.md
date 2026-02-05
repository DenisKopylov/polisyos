# Nodes Layer: Workflow узлы

**Реализации узлов для workflow execution**

Nodes содержит реализации workflow узлов для различных операций эксперимента.

## Структура

```
nodes/
├── builtins/        # Built-in node implementations
│   ├── compile/     # Compilation nodes
│   ├── data/        # Data processing nodes
│   ├── decide/      # Decision nodes
│   ├── governance/  # Governance nodes
│   └── simulate/    # Simulation nodes
└── __init__.py      # Node exports
```

## Ключевые компоненты

- **Compile nodes**: Компиляция политик в executable artifacts
- **Data nodes**: Обработка и подготовка данных
- **Decide nodes**: Принятие решений и финализация
- **Governance nodes**: Валидация и compliance checks
- **Simulate nodes**: Запуск симуляций

## API Использование

```python
from polisyos.scientist.nodes.builtins.compile import compile_foundry
from polisyos.scientist.nodes.builtins.simulate import run_simulation

# Узлы используются через engine registry
# Автоматическое обнаружение через discover_nodes()
```

## Связи

- Регистрируется в **engine** registry
- Интегрируется с **agent** для agent operations
- Использует **compute** для job execution
- Поддерживает **governance** validation