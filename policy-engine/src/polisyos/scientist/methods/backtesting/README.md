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


## Phase D.4 case replay and current selected roster

`phase_d4_source` owns deterministic replay of Phase D.4 challenge suites from selected
persisted inputs. Its versioned `PhaseD4ReplaySource` records run, loop, candidate, the exact
selected `policy_selection` evaluation, and only the allowlisted parameters and artifact refs
consumed by the canonical suite evaluator. The owner verifies candidate and selection lineage
before persisting those refs as direct input edges.

The runtime resolves the current rotating-evaluation refs from the run's benchmark registry.
`PhaseD4SuiteRoster` reloads every selected ref from CAS, derives D.4 membership from the typed
replay-source edge, and binds each suite and version to the exact evaluation and replay-source
profiles, candidate, run, loop, and selection evaluation. D.4 suite order is canonicalized by
suite ID. A missing roster is not an empty roster; only an explicit selected ref list can
establish that no D.4 suite is in the current rotation.

Report composition replaces older D.4 components by their typed suite/evaluation bindings,
not component or source display IDs. The fresh score resolver, Level5 consumer, and promotion
bundle consumer each recompute the roster from their own selected refs and compare it with the
report's direct selected-evaluation edges. A missing, duplicate, stale, or extra suite source
cannot produce an available recomputed score. Non-D.4 finite evidence remains independently
resolvable; a D.4 component without the selected roster remains limited.

Legacy schema 1.1 D.4 bases remain aggregate diagnostics. Without a selected replay source they
do not establish per-case truth and cannot produce an available protected score or
`robust=true`, regardless of component or source label. Historical artifacts are not rewritten.

Replay checks consistency against selected persisted inputs. It does not establish external
empirical truth, calibration authority, selection authority, source currentness, or full Stage
execution. The source, roster, and consumer changes are candidate-only at this frame; adoption
and runtime verification remain pending. Focused test targets are
`tests/unit/scientist/search/test_phase_d4_runtime_integration.py`,
`tests/unit/scientist/search/test_phase_d4_challenge_suites.py`, and
`tests/unit/scientist/nodes/builtins/decide/test_policy_blueprint_runtime_benchmarks.py`.
