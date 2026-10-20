# Backtesting (`polisyos.scientist.methods.backtesting`)

`backtesting` handles historical validation of policy outputs, collection of
trust/evaluation metrics, and production of diagnostic evidence consumed
directly by governance calibration and the backtest-matrix workflow.

## Role in the system

- **Depends on:** `ir.analytics`, `core.contracts`, `scientist.api`
- **Used by:** `scientist.governance`, CLI backtest commands, and monitoring feedback flows
- The package connects historical plans, prediction evaluation, trust scoring, and adversarial/
  temporal suites in one backtest runtime.

## Key concepts

- **HistoricalValidationPlan** — a scenario for validating predictions against historical data.
- **BacktestOrchestrator** — coordinates single and batch backtest runs.
- **TrustScorer** — computes a coverage-first trust score and grade.
- **Adversarial suites** — challenge sets for strategic gaming and related failure modes.
- **Temporal evaluation** — trajectory and safe-rejection checks for time-aware scenarios.
- **Trust eligibility** — degraded paths remain diagnostic and do not raise the trust profile.

## Scientist replay and replicas

For `prediction_source=scientist`, the backtest persists the cutoff mask as
`fabric.data_snapshot` and passes it to the same `run_experiment` in the same CAS.
The standard workflow enforces a strict check: `ModelSpec.data_snapshot_ref` must
point to this slice before Foundry inputs are bound. At the execution boundary,
the backtest rechecks the complete selected ref from `foundry.input_bindings`.

`n_simulation_runs=K` launches K separate workflows with unique `run_id` values
and seeds in the actual `ExecuteRequest.exec_config`. The
`scientist.backtest.replica_cohort` artifact stores the source request, runtime
seed source, references to `SimulationResult`/metrics, and the
`requested/started/completed/failed` denominator; the final backtest report
references this artifact. A single successful replica can pass its trajectory to
the existing evaluator. For K > 1, results are stored per replica, and the
backtest explicitly records that no supported multi-run projection exists and
uses a naive diagnostic fallback; it does not average replicas into a scalar or
replicate one scalar across the horizon.

## Selected artifact profiles

`ForecastOwnerRequest` preserves the complete selected model and policy `ArtifactRefModel` when the caller supplies those typed refs, including `manifest_profile_sha256`. The owner resolves the requested manifest profile and records that exact profile in report lineage; same-ID sibling profiles are not substituted. The legacy scalar-ID form remains an explicitly unselected/default-manifest lookup and does not attest to an alternate profile.

## Public API

- `HistoricalValidationPlan`, `MaskingStrategy`, `PredictionSource`
- `BacktestOrchestrator`, `OutcomeMasker`, `PredictionEvaluator`, `TrustScorer`
- `run_phase_d4_challenge_suites(...)` and adversarial challenge models
- `evaluate_temporal_trajectory(...)`, `evaluate_temporal_safe_rejection(...)`,
  `build_temporal_backtest_report(...)`

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-09
- Python modules: 17
- Exports: 25
- Recent delta: the package now provides the upstream implementation for `BacktestMatrixRunner`
  in `scientist.governance`.
- `bootstrap_metric` and `bootstrap_scenario_metrics` validate a finite one-dimensional
  observation vector before constructing the RNG or evaluating a statistic. Named statistic
  identity is retained in the result; matrix flattening is refused because it would change the
  bootstrap sampling unit. The B175 falsifier and focused verification are recorded in the E02 S3
  empirical handoff.

## Predictive Calibration Owner Facade\n\nThe package root lazily exports `ForecastOwner` and its typed request/result contracts: `ForecastOwnerRequest`, `ForecastOwnerResult`, `CalibrationRuleBinding`, `ForecastMethodParams`, `ForecastTemporalRoles`, and `TrainHoldoutSplit`. `run_forecast_owner` delegates to the same owner class. The evidence is predictive-only and bridge-pending; it does not establish causal-effect authority, treatment assignment, or S10 promotion.

## Selected EMP-01 forecast member

When Runtime supplies a selected profile, `ForecastOwnerRequest` carries the
typed Core `ForecastProfileMemberV1` receipt with the exact profile, activated
projection, observed snapshot/data references, metric, unit, ordered periods,
and observed-series digest. The owner checks the receipt against the resolved
observed bytes and preserves the profile/member edges in the uncertainty bundle
and report. Scientist does not load or interpret Data Forge projection
internals. The receipt remains predictive-only: population scope, completeness,
source relation, source time/currentness, treatment assignment, and causal
calibration remain not established.
