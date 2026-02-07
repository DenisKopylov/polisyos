# Backtesting: Историческая валидация предсказаний

Проверка качества прогнозов Policy Engine на исторических данных. Backtesting — критический компонент для калибровки доверия к модели: маскирует исторические данные, генерирует предсказания и сравнивает с реальными исходами.

## Структура

```
backtesting/
├── plan.py            # HistoricalValidationPlan, MaskingStrategy, PredictionSource
├── masking.py         # OutcomeMasker — маскирование данных по стратегии
├── evaluator.py       # PredictionEvaluator — RMSE, MAE, MAPE, coverage, bias
├── trust_scorer.py    # TrustScorer — агрегация метрик в trust score (0.0–1.0) и grade (A–F)
├── orchestrator.py    # BacktestOrchestrator — координация множественных бэктестов
└── cli.py             # CLI интерфейс для запуска из терминала
```

## Pipeline

```
Historical Data → OutcomeMasker → Predictions → PredictionEvaluator → TrustScorer → BacktestReport
```

1. **HistoricalValidationPlan** задаёт сценарий: intervention_date, masking strategy, target metrics, prediction source
2. **OutcomeMasker** маскирует данные после intervention_date (DROP_POST / REPLACE_NAN / TRUNCATE)
3. **PredictionEvaluator** вычисляет метрики точности по каждому сценарию
4. **TrustScorer** агрегирует в единый score с весами: coverage (50%), MAPE (30%), bias (20%)
5. **BacktestOrchestrator** координирует N сценариев, сохраняет BacktestReport в CAS

## Метрики и грейды

| Метрика | Отлично | Хорошо | Приемлемо | Плохо |
|---------|---------|--------|-----------|-------|
| RMSE | < 5% | 5–10% | 10–20% | > 20% |
| MAPE | < 10% | 10–20% | 20–50% | > 50% |
| Coverage | ≈ 95% | 90–95% | 85–90% | < 85% |

Trust grades: A (0.9–1.0), B (0.8–0.9), C (0.7–0.8), D (0.6–0.7), F (< 0.6).

## API

```python
from polisyos.scientist.backtesting import (
    HistoricalValidationPlan, BacktestOrchestrator,
    PredictionSource, MaskingStrategy
)

plan = HistoricalValidationPlan(
    plan_id="bt_001",
    intervention_date="2021-01-01",
    ground_truth_outcomes={"gdp_growth": [2.1, 2.3, 2.5]},
    predicted_outcomes={"gdp_growth": [2.0, 2.2, 2.6]},
    prediction_source=PredictionSource.PROVIDED,
    masking_strategy=MaskingStrategy.DROP_POST,
    target_metrics=["gdp_growth"]
)

orchestrator = BacktestOrchestrator(cas_root=".polisyos")
report = orchestrator.run([plan])
# report.trust_score, report.trust_grade, report.scenarios
```

## Связи

- **Core** — FileSystemCAS для хранения BacktestReport
- **Fabric** — загрузка исторических данных
- **Scientist** — может запускать `run_experiment()` для генерации предсказаний (`PredictionSource.SCIENTIST`)
- **IR** — BacktestReport, BacktestScenario контракты
