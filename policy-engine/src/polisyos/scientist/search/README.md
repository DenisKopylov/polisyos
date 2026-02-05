# Search Layer: Фреймворк оптимизации

**Итеративная оптимизация политик с двухстадийной оценкой**

Search предоставляет фреймворк для итеративной оптимизации политик с intelligent stopping criteria.

## Структура

```
search/
├── controller.py    # SearchController с iteration management
├── objective.py     # Composite objectives (GDP, inequality, employment)
├── stages.py        # Cheap/expensive evaluation stages
└── stopping.py      # Intelligent stopping criteria
```

## Ключевые компоненты

- **SearchController**: Управление полным циклом оптимизации
- **Composite Objectives**: Многокритериальная оптимизация с весами
- **Two-Stage Evaluation**: Быстрая preliminary + дорогая accurate оценка
- **Intelligent Stopping**: Plateau detection, max iterations, target achievement

## API Использование

```python
from polisyos.scientist.search.controller import SearchController
from polisyos.scientist.search.objective import GDPGrowthObjective

# Создание search controller
controller = SearchController(
    objectives=[GDPGrowthObjective(weight=0.7), InequalityObjective(weight=0.3)],
    stopping_criteria=[MaxIterations(50), ImprovementPlateau(window=10)]
)

# Запуск оптимизации
result = await controller.optimize(initial_candidates)
```

## Связи

- Интегрируется с **engine** для workflow execution
- Использует **compute** для parallel evaluation
- Поддерживает **kernel** для budget management