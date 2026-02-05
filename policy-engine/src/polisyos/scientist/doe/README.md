# Design of Experiments (DoE): Планирование экспериментов

**Систематическое исследование сценариев политики**

DoE предоставляет инструменты для планирования экспериментов и систематического исследования сценариев политики через структурированные дизайны экспериментов.

## Структура

```
doe/
└── designs.py      # ScenarioSweep, AblationPlan, SensitivityPlan
```

## Ключевые компоненты

- **ScenarioSweep**: Сравнение разных наборов параметров политики
- **AblationPlan**: Анализ вклада компонентов через их удаление
- **SensitivityPlan**: Исследование чувствительности к параметрам

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