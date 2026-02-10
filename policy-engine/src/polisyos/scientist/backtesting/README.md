# Backtesting Layer (`polisyos.scientist.backtesting`)

`backtesting` — историческая валидация предсказаний и расчет trust score.

## Роль

- запускает backtest-сценарии (`HistoricalValidationPlan`);
- сравнивает прогнозы с ground truth;
- агрегирует метрики качества и систематические bias;
- формирует `BacktestReport` и сохраняет его в CAS.

## Ключевые компоненты

- `plan.py` — `HistoricalValidationPlan`, `MaskingStrategy`, `PredictionSource`.
- `masking.py` — `OutcomeMasker`.
- `evaluator.py` — `PredictionEvaluator` (RMSE/MAE/MAPE/Coverage).
- `trust_scorer.py` — `TrustScorer` (coverage/mape/bias weighted score + grade).
- `orchestrator.py` — `BacktestOrchestrator.run(plans)`.
- `cli.py` — команда `polisyos scientist backtest`.

## Входной контракт плана

`HistoricalValidationPlan` требует:

- `historical_data_ref` или `historical_data_path`;
- `ground_truth_outcomes`;
- `target_metrics` (если пусто, берутся ключи из `ground_truth_outcomes`).

Для `prediction_source="provided"` обязательно `predicted_outcomes`.

## Особенности

- `PredictionSource.SCIENTIST` может запускать `run_experiment`; если `scientist_state` не передан или прогнозы не извлечены, используется naive fallback с warning.
- trust grading в `TrustScorer` основан на coverage/mape/bias и coverage-first downgrade правилах.

## Связи

- `ir.analytics.backtest` — типы отчета и CAS persistence.
- `scientist.api.run_experiment` — опциональный источник предсказаний.
- `core/components/cli_parts.py` — регистрация CLI subcommand `scientist backtest`.
