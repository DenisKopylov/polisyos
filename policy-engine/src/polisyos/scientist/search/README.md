# Search Framework: Итеративная оптимизация политик

**Фреймворк для эффективной оптимизации параметров экономических политик через итеративный поиск с двухстадийной оценкой**

## Обзор

Модуль `search` реализует интеллектуальный фреймворк для итеративной оптимизации параметров экономических политик. Он использует двухстадийную архитектуру оценки (быстрая предварительная + точная симуляция) и гибкую систему критериев остановки для эффективного поиска оптимальных решений в сложном пространстве параметров.

## Архитектура

### 🔄 Двухстадийная оценка

Фреймворк использует двухуровневую систему оценки кандидатов политик для баланса между скоростью и точностью:

1. **Cheap Stage (Быстрая оценка)**: Предварительная оценка кандидатов с использованием прокси-моделей или упрощенных симуляций
2. **Expensive Stage (Точная оценка)**: Полноценная симуляция через Foundry executor с детальными экономическими метриками

### 📊 Система целей оптимизации

Модуль поддерживает многокритериальную оптимизацию с гибкой конфигурацией целей:

- **Composite Objectives**: Комбинация нескольких целей с весами и порогами
- **Optimization Directions**: Поддержка минимизации и максимизации
- **Preset Objectives**: Готовые конфигурации для типичных экономических целей

### 🛑 Интеллектуальные критерии остановки

Гибкая система критериев для автоматического завершения поиска:

- **MaxIterations**: Ограничение по количеству итераций
- **MaxWallTime**: Ограничение по времени выполнения
- **ImprovementPlateau**: Обнаружение плато в улучшениях
- **TargetAchieved**: Достижение целевых значений
- **Composite Criteria**: Комбинация нескольких критериев

## Структура модуля

```
search/
├── __init__.py          # Экспорт основных компонентов
├── controller.py        # SearchController и управление поиском
├── objective.py         # Определение целей оптимизации
├── stages.py            # Стадии оценки кандидатов
└── stopping.py          # Критерии остановки поиска
```

## Основные компоненты

### 🎮 SearchController

Центральный компонент управления поиском:

```python
from polisyos.scientist.search import SearchController, SearchConfig

# Конфигурация поиска
config = SearchConfig(
    max_iterations=50,
    cheap_stage_evaluations=10,  # кандидатов на cheap stage
    expensive_stage_evaluations=5,  # кандидатов на expensive stage
    objective=CompositeObjective([...])
)

# Создание контроллера
controller = SearchController(config)

# Запуск оптимизации
result = await controller.optimize(initial_candidates)
```

**Ключевые возможности:**
- Управление полным циклом оптимизации
- Отслеживание истории итераций
- Интеллектуальное распределение оценок между стадиями
- Автоматическое завершение по критериям остановки

### 🎯 Objective System

Система определения и комбинации целей оптимизации:

```python
from polisyos.scientist.search import (
    CompositeObjective, GDPGrowthObjective, InequalityObjective,
    OptimizationDirection
)

# Создание составной цели
objective = CompositeObjective([
    ObjectiveValue(
        name="gdp_growth",
        direction=OptimizationDirection.MAXIMIZE,
        weight=0.6
    ),
    ObjectiveValue(
        name="inequality_reduction",
        direction=OptimizationDirection.MINIMIZE,
        weight=0.4,
        threshold=0.1  # минимально приемлемое значение
    )
])

# Использование предустановленных целей
from polisyos.scientist.search import ObjectivePresets

# Цель максимизации экономического роста
gdp_objective = ObjectivePresets.gdp_growth()

# Комплексная цель баланса (рост + снижение неравенства)
balanced_objective = ObjectivePresets.balanced_growth()
```

**Поддерживаемые цели:**
- `GDPGrowthObjective`: Максимизация экономического роста
- `InequalityObjective`: Минимизация неравенства доходов
- `EmploymentObjective`: Максимизация занятости
- `BudgetDeficitObjective`: Минимизация бюджетного дефицита

### 📈 Search Stages

Двухстадийная система оценки с корреляционным анализом:

```python
from polisyos.scientist.search import CheapStage, ExpensiveStage, CorrelationTracker

# Быстрая стадия с прокси-моделью
cheap_stage = CheapStage(
    proxy_model=my_proxy_model,
    evaluation_budget=0.1  # доля от полного бюджета
)

# Точная стадия с полной симуляцией
expensive_stage = ExpensiveStage(
    simulation_runner=foundry_executor,
    metrics=["gdp", "unemployment", "gini_coefficient"]
)

# Трекер корреляции между стадиями
correlation_tracker = CorrelationTracker()
correlation_tracker.update_correlation(
    cheap_score=0.85,
    expensive_score=0.82,
    candidate_id="policy_001"
)
```

**Особенности:**
- **Correlation Tracking**: Отслеживание качества предсказаний cheap stage
- **Adaptive Sampling**: Интеллектуальное распределение кандидатов между стадиями
- **Budget Management**: Контроль вычислительных ресурсов на каждой стадии

### 🛑 Stopping Criteria

Гибкая система критериев завершения поиска:

```python
from polisyos.scientist.search import (
    CompositeStoppingCriterion, MaxIterations, ImprovementPlateau,
    MaxWallTime, TargetAchieved
)

# Комбинированный критерий остановки
stopping_criterion = CompositeStoppingCriterion([
    MaxIterations(max_iterations=100),
    MaxWallTime(max_seconds=3600),  # 1 час
    ImprovementPlateau(
        patience=10,  # итераций без улучшения
        min_improvement=0.001  # минимальное улучшение
    ),
    TargetAchieved(
        target_metric="gdp_growth",
        target_value=0.05  # 5% рост
    )
])

# Проверка условия остановки
condition = stopping_criterion.check(history, current_state)
if condition.should_stop:
    print(f"Поиск завершен: {condition.reason}")
```

## Рабочий процесс

### 1. Настройка целей оптимизации

```python
from polisyos.scientist.search import ObjectivePresets, CompositeObjective

# Выбор базовой цели
base_objective = ObjectivePresets.balanced_growth()

# Кастомизация весов
custom_objective = CompositeObjective([
    ObjectiveValue("gdp_growth", OptimizationDirection.MAXIMIZE, weight=0.5),
    ObjectiveValue("inequality", OptimizationDirection.MINIMIZE, weight=0.3),
    ObjectiveValue("employment", OptimizationDirection.MAXIMIZE, weight=0.2)
])
```

### 2. Конфигурация стадий оценки

```python
from polisyos.scientist.search import SearchStage, CheapStage, ExpensiveStage

# Настройка быстрой оценки
cheap_stage = CheapStage(
    proxy_evaluator=my_fast_model,
    max_evaluations=20
)

# Настройка точной оценки
expensive_stage = ExpensiveStage(
    simulator=foundry_executor,
    required_metrics=["gdp_change", "unemployment_rate", "gini_coefficient"],
    max_evaluations=5
)
```

### 3. Настройка критериев остановки

```python
from polisyos.scientist.search import StoppingPresets

# Использование предустановленных критериев
fast_stopping = StoppingPresets.fast_optimization()  # быстрый поиск
thorough_stopping = StoppingPresets.thorough_optimization()  # тщательный поиск

# Или кастомная конфигурация
custom_stopping = CompositeStoppingCriterion([
    MaxIterations(50),
    ImprovementPlateau(patience=5, min_improvement=0.005)
])
```

### 4. Запуск оптимизации

```python
from polisyos.scientist.search import SearchController, SearchConfig

# Создание конфигурации
config = SearchConfig(
    objective=custom_objective,
    cheap_stage=cheap_stage,
    expensive_stage=expensive_stage,
    stopping_criterion=custom_stopping,
    random_seed=42
)

# Запуск поиска
controller = SearchController(config)
result = await controller.optimize(initial_population)

# Анализ результатов
print(f"Лучший кандидат: {result.best_candidate}")
print(f"Целевая функция: {result.best_objective}")
print(f"Итераций выполнено: {result.iterations_completed}")
```

## Интеграция с другими модулями

### 🔗 Связь с Scientist Orchestrator

Search framework интегрируется с основным workflow через специальный узел оптимизации:

```python
# В workflow scientist используется для оптимизации параметров политики
from polisyos.scientist.orchestrator.optimizer import optimize_mechanisms

# Оптимизация параметров механизма
optimized_params = await optimize_mechanisms(
    policy_ir=policy,
    search_config=config,
    context=experiment_state
)
```

### 🔗 Связь с Foundry Executor

Expensive stage использует Foundry для точных симуляций:

```python
from polisyos.foundry.executor import execute_program_graph

# Выполнение симуляции через Foundry
simulation_result = await execute_program_graph(
    program_graph=policy.program_graph,
    state_snapshot=initial_state,
    metrics_config=required_metrics
)
```

### 🔗 Связь с Governance

Поисковые эксперименты проходят governance проверки:

```python
from polisyos.scientist.governance.preflight import preflight_checks

# Предварительная проверка перед оптимизацией
state, gate_request = preflight_checks({
    "policy_ir": optimized_policy,
    "search_config": config,
    "budget": compute_budget
})
```

## Ключевые возможности

### ⚡ Эффективность оптимизации

- **Two-Stage Evaluation**: Баланс между скоростью и точностью через прокси-модели
- **Correlation-Aware Sampling**: Интеллектуальное распределение вычислительных ресурсов
- **Early Stopping**: Автоматическое завершение при достижении целей или отсутствии прогресса

### 🎯 Гибкость конфигурации

- **Multi-Objective Optimization**: Одновременная оптимизация нескольких конфликтующих целей
- **Pluggable Stages**: Возможность создания кастомных стадий оценки
- **Configurable Stopping**: Гибкие критерии завершения поиска

### 📊 Observability и анализ

- **Iteration History**: Полная история всех итераций оптимизации
- **Performance Metrics**: Метрики эффективности поиска (корреляция, convergence rate)
- **Search Analytics**: Анализ качества оптимизации и рекомендаций по улучшению

### 🔧 Расширяемость

- **Custom Objectives**: Создание специализированных целей оптимизации
- **Custom Stages**: Реализация новых стратегий оценки кандидатов
- **Custom Stopping Criteria**: Определение специфических условий завершения

## Примеры использования

### Оптимизация налоговой политики

```python
from polisyos.scientist.search import SearchController, ObjectivePresets

# Цель: максимизация доходов бюджета при минимизации неравенства
tax_optimization = ObjectivePresets.fiscal_balance()

config = SearchConfig(
    objective=tax_optimization,
    max_iterations=30,
    stopping_criterion=StoppingPresets.fast_optimization()
)

controller = SearchController(config)

# Начальная популяция параметров налогов
initial_tax_rates = [
    {"income_tax_rate": 0.15, "corporate_tax_rate": 0.20},
    {"income_tax_rate": 0.20, "corporate_tax_rate": 0.25},
    # ... другие кандидаты
]

result = await controller.optimize(initial_tax_rates)
```

### Оптимизация социальной политики

```python
# Цель: снижение бедности при контроле бюджетного дефицита
poverty_reduction = CompositeObjective([
    ObjectiveValue("poverty_rate", OptimizationDirection.MINIMIZE, weight=0.7),
    ObjectiveValue("budget_deficit", OptimizationDirection.MINIMIZE, weight=0.3)
])

config = SearchConfig(
    objective=poverty_reduction,
    expensive_stage_evaluations=3,
    stopping_criterion=TargetAchieved("poverty_rate", 0.05)  # цель: 5% бедности
)

controller = SearchController(config)
result = await controller.optimize(social_program_candidates)
```

## Тестирование

### Структура тестов

```
tests/scientist/search/
├── test_controller.py      # Тестирование SearchController
├── test_objective.py       # Тестирование целей оптимизации
├── test_stages.py          # Тестирование стадий оценки
├── test_stopping.py        # Тестирование критериев остановки
└── integration/
    └── test_search_workflow.py  # Интеграционные тесты
```

### Запуск тестов

```bash
# Unit tests для отдельных компонентов
pytest tests/scientist/search/test_controller.py -v
pytest tests/scientist/search/test_objective.py -v
pytest tests/scientist/search/test_stages.py -v
pytest tests/scientist/search/test_stopping.py -v

# Integration tests
pytest tests/scientist/search/integration/test_search_workflow.py -v
```

## Будущие улучшения

### 🚀 Планируемые возможности

- **Multi-Fidelity Optimization**: Поддержка различных уровней точности симуляции
- **Bayesian Optimization**: Использование гауссовских процессов для эффективного поиска
- **Parallel Search**: Распределенная оптимизация на кластере
- **Meta-Learning**: Автоматическое обучение стратегий поиска

### 🔬 Продвинутые алгоритмы

- **Evolutionary Algorithms**: Генетические алгоритмы для дискретных параметров
- **Gradient-Based Methods**: Градиентная оптимизация с автоматическим дифференцированием
- **Reinforcement Learning**: RL для обучения стратегий оптимизации

### 📊 Аналитика и визуализация

- **Search Space Visualization**: Визуализация пространства поиска и траекторий оптимизации
- **Performance Dashboards**: Панели мониторинга эффективности поиска
- **Recommendation Engine**: Автоматические рекомендации по настройке поиска