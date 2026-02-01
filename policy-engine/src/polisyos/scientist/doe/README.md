# Design of Experiments (DoE): Планирование экспериментов

**Систематическое исследование сценариев политики**

DoE Layer предоставляет инструменты для планирования экспериментов и систематического исследования сценариев политики через структурированные дизайны экспериментов.

## Обзор

Папка `doe/` содержит модели дизайнов экспериментов для сравнения политик, анализа чувствительности и оптимизации параметров. Реализует foundation для A/B тестирования и statistical comparison.

## Архитектура

```
doe/
├── __init__.py           # Экспорт основных компонентов
└── designs.py           # Модели дизайнов экспериментов (ScenarioSweep, AblationPlan, SensitivityPlan)
```

## Компоненты

### 🧪 Experiment Designs (designs.py)

Базовые модели для структурированного планирования экспериментов:

#### ScenarioSweep
Сканирование различных сценариев политики:
```python
class ScenarioSweep(BaseModel):
    """Сравнение разных наборов параметров."""
    scenarios: list[dict] = Field(default_factory=list)

    # Пример использования
    sweep = ScenarioSweep(scenarios=[
        {"tax_rate": 0.1, "subsidy_rate": 0.05, "funding_source": "income_tax"},
        {"tax_rate": 0.2, "subsidy_rate": 0.10, "funding_source": "wealth_tax"},
        {"tax_rate": 0.3, "subsidy_rate": 0.15, "funding_source": "carbon_tax"}
    ])
```

#### AblationPlan
Анализ ablation - удаление компонентов для понимания их вклада:
```python
class AblationPlan(BaseModel):
    """Систематическое удаление компонентов политики."""
    targets: list[str] = Field(default_factory=list)

    # Пример использования
    ablation = AblationPlan(targets=[
        "income_tax_mechanism",
        "unemployment_subsidy",
        "corporate_tax_mechanism",
        "progressive_tax_mechanism"
    ])
```

#### SensitivityPlan
Анализ чувствительности параметров:
```python
class SensitivityPlan(BaseModel):
    """Изучение влияния параметров на результаты."""
    parameters: list[str] = Field(default_factory=list)

    # Пример использования
    sensitivity = SensitivityPlan(parameters=[
        "tax_rate_sensitivity",
        "subsidy_elasticity",
        "labor_market_response",
        "consumption_response"
    ])
```

## API Использование

### Scenario Sweep

```python
from polisyos.scientist.doe.designs import ScenarioSweep

# Создание дизайна для сравнения источников финансирования UBI
ubi_scenarios = ScenarioSweep(scenarios=[
    {
        "ubi_amount": 500,
        "funding_source": "income_tax",
        "tax_rate_increase": 0.05
    },
    {
        "ubi_amount": 750,
        "funding_source": "wealth_tax",
        "wealth_tax_rate": 0.02
    },
    {
        "ubi_amount": 1000,
        "funding_source": "carbon_tax",
        "carbon_tax_rate": 0.10
    }
])

# Использование в workflow
workflow.invoke({
    "user_request": "Compare different UBI funding mechanisms",
    "run_id": "ubi_comparison_001",
    "doe_design": ubi_scenarios.model_dump(),
    "optimize": True,
    "budget": {"max_llm_calls": 3, "max_sim_runs": 5}
})
```

### Ablation Analysis

```python
from polisyos.scientist.doe.designs import AblationPlan

# Анализ вклада компонентов налоговой реформы
tax_reform_ablation = AblationPlan(targets=[
    "progressive_income_tax",     # Прогрессивная шкала
    "corporate_tax_cut",          # Снижение корпоративного налога
    "capital_gains_preference",   # Льготы на прирост капитала
    "tax_credits_for_investment"  # Налоговые кредиты на инвестиции
])

# Каждый эксперимент исключает один компонент
# для оценки его marginal contribution
```

### Sensitivity Analysis

```python
from polisyos.scientist.doe.designs import SensitivityPlan

# Анализ чувствительности к ключевым параметрам
policy_sensitivity = SensitivityPlan(parameters=[
    "price_elasticity_of_labor_supply",
    "interest_rate_response",
    "fiscal_multiplier",
    "income_inequality_aversion",
    "consumption_propagation_speed"
])

# Систематическое варьирование параметров
# для оценки robustness политики
```

## Интеграция с Workflow

DoE designs интегрируются в scientist workflow для автоматического выполнения множественных экспериментов:

### Multi-run execution

```python
def execute_doe_design(state: ExperimentState) -> ExperimentState:
    """Выполнение DoE дизайна с множественными прогонами."""

    doe_design = state.get("doe_design")
    if not doe_design:
        return state

    results = []
    for scenario in doe_design.get("scenarios", []):
        # Модификация базовой политики для сценария
        modified_ir = apply_scenario_to_ir(state["ir"], scenario)

        # Выполнение эксперимента
        scenario_state = {**state, "ir": modified_ir, "scenario": scenario}
        scenario_result = run_single_experiment(scenario_state)

        results.append({
            "scenario": scenario,
            "result": scenario_result,
            "metrics": extract_key_metrics(scenario_result)
        })

    return {**state, "doe_results": results}
```

### Statistical comparison

```python
def analyze_doe_results(doe_results: list) -> dict:
    """Статистический анализ результатов DoE."""

    # Извлечение метрик по сценариям
    gdp_impacts = [r["metrics"]["gdp_change"] for r in doe_results]
    unemployment_changes = [r["metrics"]["unemployment_change"] for r in doe_results]

    return {
        "gdp_impact_stats": calculate_statistics(gdp_impacts),
        "unemployment_stats": calculate_statistics(unemployment_changes),
        "best_scenario": find_optimal_scenario(doe_results),
        "robustness_analysis": assess_robustness(doe_results)
    }
```

## Примеры использования

### Сравнение налоговых реформ

```python
# Сценарии разных подходов к налоговой реформе
tax_reform_scenarios = ScenarioSweep(scenarios=[
    {
        "name": "flat_tax",
        "income_tax_rate": 0.20,
        "corporate_tax_rate": 0.20,
        "progressive_brackets": []
    },
    {
        "name": "progressive_tax",
        "income_tax_brackets": [
            {"threshold": 50000, "rate": 0.10},
            {"threshold": 100000, "rate": 0.20},
            {"threshold": 500000, "rate": 0.30}
        ],
        "corporate_tax_rate": 0.25
    },
    {
        "name": "consumption_tax",
        "income_tax_rate": 0.10,
        "consumption_tax_rate": 0.15,
        "corporate_tax_rate": 0.15
    }
])

workflow.invoke({
    "user_request": "Compare different tax reform approaches",
    "doe_design": tax_reform_scenarios.model_dump(),
    "optimize": False,  # Фокус на сравнении, не оптимизации
    "budget": {"max_sim_runs": 3}  # Один прогон на сценарий
})
```

### Анализ чувствительности монетарной политики

```python
# Чувствительность к параметрам monetary policy
monetary_sensitivity = SensitivityPlan(parameters=[
    "central_bank_reaction_function",
    "inflation_target_tolerance",
    "interest_rate_smoothing",
    "forward_guidance_impact",
    "quantitative_easing_effectiveness"
])

# Систематическое исследование robustness
# монетарной политики к изменениям параметров
```

### Ablation study для комплексной политики

```python
# Разбор комплексной политики на компоненты
climate_policy_ablation = AblationPlan(targets=[
    "carbon_tax_mechanism",
    "renewable_energy_subsidies",
    "energy_efficiency_standards",
    "cap_and_trade_system",
    "green_infrastructure_investment",
    "behavioral_nudges_for_sustainability"
])

# Понимание вклада каждого компонента
# в общий эффект климатической политики
```

## Будущие расширения

### Advanced DoE Designs

```python
class FactorialDesign(BaseModel):
    """Полный факторный дизайн для многофакторного анализа."""
    factors: list[Factor] = Field(default_factory=list)
    levels: list[int] = Field(default_factory=list)

class ResponseSurfaceDesign(BaseModel):
    """Response surface methodology для оптимизации."""
    variables: list[str] = Field(default_factory=list)
    ranges: dict[str, tuple[float, float]] = Field(default_factory=dict)

class AdaptiveDesign(BaseModel):
    """Адаптивный дизайн с sequential experimentation."""
    initial_scenarios: list[dict] = Field(default_factory=list)
    adaptation_rules: list[AdaptationRule] = Field(default_factory=list)
```

### Statistical Analysis

```python
class DoeAnalyzer:
    """Статистический анализ результатов DoE."""

    def analyze_variance(self, results: list) -> dict:
        """ANOVA analysis для identification значимых факторов."""

    def calculate_effect_sizes(self, results: list) -> dict:
        """Cohen's d и другие effect size measures."""

    def perform_posthoc_tests(self, results: list) -> dict:
        """Tukey's HSD и другие post-hoc тесты."""

    def assess_robustness(self, results: list) -> dict:
        """Анализ robustness к изменениям параметров."""
```

## Тестирование

### Unit тесты

```bash
# Тестирование DoE компонентов
pytest tests/scientist/test_doe_*.py -v

# Scenario sweep
pytest tests/scientist/test_doe_scenario_sweep.py -v

# Ablation analysis
pytest tests/scientist/test_doe_ablation.py -v
```

### Integration тесты

```python
def test_doe_workflow_integration():
    """Тестирование интеграции DoE с workflow."""

    # Создание дизайна
    design = ScenarioSweep(scenarios=[
        {"param1": "value1"},
        {"param1": "value2"}
    ])

    # Имитация workflow с DoE
    state = {
        "user_request": "Test DoE integration",
        "doe_design": design.model_dump()
    }

    # Проверка обработки дизайна
    processed_state = process_doe_design(state)
    assert len(processed_state["doe_results"]) == 2
```

## Расширение

### Кастомный дизайн экспериментов

```python
from polisyos.scientist.doe.designs import BaseModel
from typing import Any, Dict, List
from pydantic import Field

class CustomDesign(BaseModel):
    """Кастомный дизайн для специфических нужд."""

    custom_parameter: str = Field(...)
    scenarios: List[Dict[str, Any]] = Field(default_factory=list)

    def generate_scenarios(self) -> List[Dict[str, Any]]:
        """Генерация сценариев на основе параметров."""
        # Кастомная логика генерации
        return self.scenarios

    def validate_design(self) -> bool:
        """Валидация корректности дизайна."""
        # Кастомная валидация
        return True
```

### Интеграция с optimization

```python
class OptimizationEnhancedDesign(ScenarioSweep):
    """DoE дизайн с встроенной оптимизацией."""

    optimization_target: str = Field(...)
    optimization_method: str = Field(default="bayesian")

    def optimize_scenarios(self, prior_results: List[Dict]) -> List[Dict]:
        """Оптимизация выбора сценариев на основе предыдущих результатов."""
        # Bayesian optimization или другие методы
        pass
```

## Связанные компоненты

- **Orchestrator**: Интеграция в workflow через `doe_design` поле
- **Kernel**: Budget management для multi-scenario execution
- **Compute**: Job specifications для parallel execution сценариев
- **Runtime**: Artifact management для результатов DoE

## Troubleshooting

### Пустой список сценариев

```
ValueError: scenarios list cannot be empty
```

**Решение**: Убедиться, что `ScenarioSweep.scenarios` содержит хотя бы один сценарий

### Неконсистентные параметры сценариев

```
ValidationError: scenario keys must be consistent across all scenarios
```

**Решение**: Все сценарии должны иметь одинаковый набор ключей

### Превышение бюджета симуляций

```
BudgetExceededError: max_sim_runs exceeded in DoE execution
```

**Решение**: Увеличить `max_sim_runs` в budget или уменьшить количество сценариев

### Отсутствие метрик для сравнения

**Решение**: Убедиться, что все сценарии производят comparable метрики

### Statistical power недостаточен

**Решение**: Увеличить количество репликаций или использовать более мощные статистические тесты