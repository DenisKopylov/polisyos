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
- **TrustScorer** — удерживает trust authority до admitted versioned purpose/profile.
- **Adversarial suites** — challenge-наборы для strategic gaming и related failure modes.
- **Temporal evaluation** — trajectory и safe-rejection checks для time-aware scenarios.
- **Trust eligibility** — degraded paths остаются diagnostic, но не повышают trust profile.

## Public API

- `HistoricalValidationPlan`, `MaskingStrategy`, `PredictionSource`
- `BacktestOrchestrator`, `OutcomeMasker`, `PredictionEvaluator`, `TrustScorer`
- `run_phase_d4_challenge_suites(...)` и adversarial challenge models
- `evaluate_temporal_trajectory(...)`, `evaluate_temporal_safe_rejection(...)`,
  `build_temporal_backtest_report(...)`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 17
- Exports: 25
- Недавний delta: пакет теперь является upstream для `BacktestMatrixRunner`
  в `scientist.governance`

## Replay and authority admission

Scientist `n_simulation_runs=K` expands into K scalar backend replays with
separate requested seeds/run identities, row-preserving scenarios and persisted requested,
attempted, completed and failed counts. PROVIDED trajectories execute once;
their original replica parameter is retained without asserting K external runs.
Micro errors pool metric/time cells per replay; equal-scenario macro RMSE stays
separate. Finite observed truths and eligible prediction/truth pairs have
separate denominators; empty comparisons are `not_evaluated`.

Trust grades and the matrix promotion score remain unavailable until the
Scientist trust-profile owner admits a versioned purpose, sampling assumptions
and any meaningful-bias margin/equivalence rule. Non-significant Student t tests
and perfect observed agreement alone do not supply that policy. Per-kind matrix
scores remain explicitly descriptive. Bootstrap accepts a one-dimensional
sample and a scalar statistic; a custom callable label remains
`consumer_asserted`, never verified functional provenance.

The native Scientist facade receives the same configured core CAS. Successful
forecast execution still requires an admitted Trinity/model/registry and a
compatible masked-history materializer. Generic `params.random_seed` is a
dispatch request; the native Foundry `ExecConfig.seed` binding is not established
by this backtest adapter. A missing configured producer remains explicit and
does not turn its native refusal or a controlled dispatch spy into backend PASS.
