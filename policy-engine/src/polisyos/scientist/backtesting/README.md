# Backtesting Layer (`polisyos.scientist.backtesting`)

`backtesting` — историческая валидация предсказаний и расчет trust score для decision packet feedback loop.

## Роль

- запускает backtest-сценарии (`HistoricalValidationPlan`);
- сравнивает прогнозы с ground truth;
- агрегирует метрики качества и систематические bias;
- формирует `BacktestReport` и сохраняет его в CAS;
- определяет, можно ли считать backtest normal trust evidence или только degraded diagnostic artifact.

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

- `PredictionSource.SCIENTIST` может запускать `run_experiment`; если `scientist_state` не передан или прогнозы не извлечены, используется naive fallback, но теперь это явный degraded mode, а не normal trust path.
- `BacktestReport` фиксирует `prediction_mode_requested`, `prediction_mode_effective`, `degraded`, `degraded_reasons`, `trust_eligible`.
- Если `prediction_mode_requested="scientist"` деградирует в naive fallback, `trust_eligible=false`: такой backtest полезен для диагностики, но не поднимает `trust_score`/`trust_grade` в `DecisionPacket.trust_profile`.
- trust grading в `TrustScorer` по-прежнему основан на coverage/mape/bias и coverage-first downgrade правилах, но итоговый trust profile публикуется только для trust-eligible path.

## Связи

- `ir.analytics.backtest` — типы отчета и CAS persistence.
- `scientist.api.run_experiment` — опциональный источник предсказаний.
- `scientist.feedback.build_monitoring_contract_from_packet` — производит monitoring contract из backtest + simulation results.
- `core/components/cli_parts.py` — регистрация CLI subcommand `scientist backtest`.
