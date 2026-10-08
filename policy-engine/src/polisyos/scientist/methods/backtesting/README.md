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

### Paired interval admission

`PredictionEvaluator` accepts each supplied interval only as a finite, ordered numeric
pair. It does not reorder reversed bounds, truncate extra components, or coerce strings
and booleans at this direct API. `HistoricalValidationPlan` retains its existing Pydantic
float-coercion contract; validation there is distinct from this post-validation seam.

Invalid, missing, or foreign metric/time interval entries preserve usable point comparisons
and the complete requested metric/time-cell denominator. Their intervals remain unavailable.
The existing scenario metadata carries recomputed `interval_admission` limitations, counts
and `coverage_scope`: partial coverage describes only evaluated pairs. Backtest orchestration
consumes a limited interval admission as a degraded, non-trust-eligible report; the limitation
survives CAS persistence and a fresh reader. Point-only requests do not acquire an interval
limitation. No report or interval schema has changed.

Empirical interval hits measure these paired synthetic/observed cases, not causal identification,
population calibration, equivalence, or institutional authority. The historical heuristic trust
profile on this source remains a separate accountable purpose/profile decision.

### Interval basis through report consumers

The internal `polisyos.calibration.interval_basis` check recomputes completeness from each
scenario's actual bounds, observations, hits and declared counts. Temporal report construction,
matrix scoring, empirical forecast evidence and calibration promotion all consume this same
check. Missing or positive metadata labels cannot turn a partial interval roster into a complete
one; retained producer limitations also remain blocking. Conditional coverage and valid point
errors stay readable while an incomplete interval basis is unavailable for scoring or promotion.

`CalibrationValidationRunner` injects its existing CAS into `CalibrationLeaderboard`.
The optional constructor store argument is additive: callers without a store may still obtain
diagnostic scores, but cannot establish promotion. With a store, the leaderboard resolves and
verifies the report's kind, schema and bytes, scenario/kind roster and recomputed matrix scores.
Complete legacy paired reports need no new metadata marker. Point-only reports remain supported,
and a complete predictive ETS report's separate bridge-pending limitation does not itself imply
an interval-basis defect.

The current `OutcomeComparison` schema has metric names but no row/time identity. This check
does not establish the authentic source roster or detect substituted equal rows whose declared
counts remain consistent. A scientific population/axis admission needs the actual source/row
contract; this internal consistency check supplies no Runtime or institutional authority.

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
