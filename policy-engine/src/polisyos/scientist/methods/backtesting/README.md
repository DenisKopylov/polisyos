# Backtesting (`polisyos.scientist.methods.backtesting`)

`backtesting` отвечает за историческую проверку policy outputs, сбор trust/evaluation
метрик и выпуск diagnostic evidence, которое теперь напрямую потребляется
governance calibration и backtest matrix контуром.

## Роль в системе

- **Зависит от:** `ir.analytics`, `core.contracts`, `scientist.api`
- **Используется в:** `scientist.governance`, CLI backtest commands, monitoring feedback flows
- Пакет связывает historical plans, prediction evaluation, trust scoring и adversarial/
  temporal suites в единый backtest runtime.

## Ключевые концепции

- **HistoricalValidationPlan** — сценарий проверки предсказаний на исторических данных.
- **BacktestOrchestrator** — координирует одиночные и пакетные backtest runs.
- **TrustScorer** — считает coverage-first trust score и grade.
- **Adversarial suites** — challenge-наборы для strategic gaming и related failure modes.
- **Temporal evaluation** — trajectory и safe-rejection checks для time-aware scenarios.
- **Trust eligibility** — degraded paths остаются diagnostic, но не повышают trust profile.

## Scientist replay и реплики

Для `prediction_source=scientist` backtest сохраняет cutoff-маску как `fabric.data_snapshot` и
передаёт её тому же `run_experiment` в том же CAS. Стандартный workflow сохраняет строгую проверку:
`ModelSpec.data_snapshot_ref` должен указывать на этот срез до связывания входов Foundry. На границе
исполнения backtest повторно проверяет полный выбранный ref из `foundry.input_bindings`.

`n_simulation_runs=K` запускает K отдельных workflow с уникальными `run_id` и seed в фактическом
`ExecuteRequest.exec_config`. Артефакт `scientist.backtest.replica_cohort` сохраняет исходный запрос,
runtime seed source, ссылки на `SimulationResult`/metrics и знаменатель `requested/started/completed/
failed`; итоговый backtest report ссылается на этот артефакт. Одиночная успешная реплика может
передать свою trajectory прежнему evaluator. Для K > 1 результаты сохраняются по репликам, а backtest
явно помечает отсутствие поддержанного multi-run projection и использует naive diagnostic fallback;
он не усредняет реплики в scalar и не размножает его по горизонту.

## Public API

- `HistoricalValidationPlan`, `MaskingStrategy`, `PredictionSource`
- `BacktestOrchestrator`, `OutcomeMasker`, `PredictionEvaluator`, `TrustScorer`
- `run_phase_d4_challenge_suites(...)` и adversarial challenge models
- `evaluate_temporal_trajectory(...)`, `evaluate_temporal_safe_rejection(...)`,
  `build_temporal_backtest_report(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-10-09
- Python modules: 17
- Exports: 25
- Недавний delta: пакет теперь является upstream для `BacktestMatrixRunner`
  в `scientist.governance`
- `bootstrap_metric` and `bootstrap_scenario_metrics` validate a finite one-dimensional
  observation vector before constructing the RNG or evaluating a statistic. Named statistic
  identity is retained in the result; matrix flattening is refused because it would change the
  bootstrap sampling unit. The B175 falsifier and focused verification are recorded in the E02 S3
  empirical handoff.
