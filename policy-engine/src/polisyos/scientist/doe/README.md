# Design of Experiments (DoE): Планирование экспериментов

**Систематическое исследование сценариев политики**

DoE предоставляет инструменты для планирования экспериментов и систематического исследования сценариев политики через структурированные дизайны экспериментов.

## Структура

```
doe/
├── designs.py      # ScenarioSweep, AblationPlan, SensitivityPlan, AdversarialPlan
├── sampling.py     # SALib sampling + adversarial sample generation
├── analysis.py     # Sensitivity index analysis
└── stress_report.py # Stress test report contracts
```

## Ключевые компоненты

- **ScenarioSweep**: Сравнение разных наборов параметров политики
- **AblationPlan**: Анализ вклада компонентов через их удаление
- **SensitivityPlan**: Исследование чувствительности к параметрам
- **AdversarialPlan**: Поиск worst-case сценариев
- **SensitivityResult**: Ранжирование параметров по влиянию
- **StressTestReport**: Сводка найденных уязвимостей

## API Использование

```python
from polisyos.scientist.doe.designs import ScenarioSweep, AblationPlan

# Сравнение сценариев финансирования UBI
scenarios = ScenarioSweep(scenarios=[
    {"ubi_amount": 500, "funding": "income_tax"},
    {"ubi_amount": 750, "funding": "wealth_tax"}
])

# Анализ ablation компонентов политики
ablation = AblationPlan(targets=["tax_mechanism", "subsidy_mechanism"])
```

## Связи

- Интегрируется с **engine** layer для multi-run execution
- Поддерживает **kernel** для budget management
- Использует **compute** для parallel scenario execution
