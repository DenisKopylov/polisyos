# Governance (`polisyos.scientist.governance`)

`governance` — слой policy/runtime проверок Scientist: от pre/post-flight validation
и human gate до новых calibration, backtest-matrix, stress-scenario и leaderboard
контуров для promotion-quality решений.

## Роль в системе

- **Зависит от:** `core.governance`, `ir.observation`, `scientist.backtesting`, `scientist.kernel`
- **Используется в:** builtin governance nodes, `search.judge_stack`, runtime validation APIs
- Пакет связывает pass registry, runtime subsets, calibration evidence и финальный governance report.

## Ключевые концепции

- **ValidationPipeline** — ordered execution governance passes с blocker-aware поведением.
- **Runtime pass registry** — builtin + entry-point passes, теперь с `strategic_response`,
  `checkpoint` и `freshness` fallbacks.
- **Backtest matrix** — обязательный набор backtest kinds по observation families.
- **Calibration governance** — family-aware validation, adversarial suites и active disambiguation.
- **Stress scenarios** — promotion-ориентированные robustness checks по baseline/scenario deltas.
- **Calibration validation bundle** — backtest + stress + leaderboard readout, сохраняемый как artifact.
- **Governance accountability artifact** — единый audit-friendly surface для calibration,
  fairness, threshold rationale, risk-weighted verdict и probabilistic escalation policy.

## Public API

- `preflight_checks(...)`, `postflight_checks(...)`, `ValidationProfile`
- `BacktestMatrixRunner`, `BacktestMatrixResult`, `BacktestKind`
- `CalibrationGovernanceRunner`, `CalibrationGovernanceReport`, `CalibrationGovernanceInput`
- `StressScenarioRunner`, `StressScenarioResult`, `StressScenarioKind`
- `CalibrationValidationRunner`, `CalibrationValidationBundle`,
  `persist_calibration_validation_bundle(...)`
- `GovernanceAccountabilityArtifact`, `GovernanceAccountabilityInput`,
  `build_governance_accountability_artifact(...)`
- `CalibrationLeaderboard`, `CalibrationLeaderboardEntry`, `CalibrationLeaderboardMetrics`
- `GovernanceReport`, `GovernanceReportLinks`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
  - Accountability/doc surface обновлён: 2026-04-12
- Python modules: 44
- Exports: 27
- Недавний delta: добавлены `backtest_matrix.py`, `calibration.py`,
  `calibration_leaderboard.py`, `calibration_validation.py`, `stress_scenarios.py`
  и `passes/strategic_response_pass.py`
