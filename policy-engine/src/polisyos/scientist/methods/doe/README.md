# DoE (`polisyos.scientist.methods.doe`)

`doe` покрывает design-of-experiments и stress-analysis часть Scientist: sensitivity,
ablation и adversarial планы, генерацию sample sets и пост-анализ уязвимостей.

## Роль в системе

- **Зависит от:** numerical sampling/analysis utilities and Scientist evaluation contracts
- **Используется в:** `scientist.search.adversarial`, CLI stress/sensitivity commands
- Пакет формирует controlled experiment plans для проверки robustness и parameter sensitivity.

## Ключевые концепции

- **SensitivityPlan** — параметризованный sensitivity design с failure policy.
- **AdversarialPlan** — сценарный stress-test для policy candidates.
- **Sampling** — генерация sensitivity/adversarial samples.
- **Analysis** — агрегация результатов и уязвимостей после execution.
- **Sensitivity uncertainty** — calibrated CI payloads, rank uncertainty, and retained row blocks.
- **Coverage benchmarks** — analytic truth suites, empirical coverage metrics, and approval profiles.
- **StressTestReport** — итоговая форма публикации robustness issues.

## Observed stress scenario evidence

`StressTestReport` 1.1 adds optional `scenario_evidence` and per-component evidence.
The adversarial producer counts attempts, finite outcomes, violated scenarios,
unknown outcomes and planned scenarios before issue grouping or top-k. Its score
is `(finite_evaluated - violated_scenarios) / finite_evaluated`; each scenario
contributes at most one violation. Severity occurrence counts remain independent
of retained issue examples. Thresholds use the declared objective's coordinates
and direction; absent thresholds, zero finite outcomes and unsupported legacy
component bases yield an unavailable score. Unknown or unfinished runs remain
partial. Complete means the declared observed stream, not the whole parameter
space or a population probability. These fractions do not establish model
uncertainty. The blueprint carries and replaces complete component count bases
without deriving them from issue lists. The D challenge adapter declares
`challenge_case_pass@1.0`: one uniquely named case with an explicit expected
outcome and consistent strict boolean passed/failed result is one finite
observed case. Skipped cases stay outside attempts, while unknown or
inconsistent attempted outcomes remain separate; both prevent completeness.
Empty/zero-finite suites publish unavailable scores and cannot be promoted.
Passing suites also publish their typed basis for the real blueprint consumer.
This adapter consumes existing case outcomes; it does not authenticate or
recompute their scientific predicate.

New readers accept legacy 1.0 reports without inventing scenario evidence;
`is_robust` requires complete, available evidence with no observed violation.
Strict legacy readers must be upgraded before consuming 1.1 output. Optional
absent evidence is omitted from legacy serialization. `StressScenarioEvidence`
and threshold admission live in the documented `doe.stress_report` module. Unknown report schema versions and evidence carried as schema 1.0
are refused. The blueprint records `schema_compatibility` for bounded legacy
reads and still treats legacy scores without scenario evidence as unassessed.
Anonymous delivery retries reuse the existing report identity and bind the
actual canonical payload (excluding its optional CAS handle); changed content
under that identity is refused. This does not authenticate scenario provenance.

The internal blueprint node accepts an optional keyword-only
`PolicyBudgetExecutionContext.budget_middleware` port. A configured caller
constructs this frozen context with the same existing B `BudgetMiddleware`
instance and its usual store/run/logger, then calls the ordinary node. JSON
`ExperimentState.params` never carries the owner. Plain `ExecutionContext`
remains unmanaged; the subtype creates no ledger, permission or authority.
Serialized deployment-factory adoption requires its appointed owner separately.

## Bounded distribution contract (DOE-02)

`ParameterSpec.lower_bound` and `upper_bound` are always physical support.  The
legacy uniform form remains unchanged.  A non-uniform parameter must carry an
explicit versioned `DistributionSpecV1`:

- `NORMAL` requires finite `mean` and positive finite `std`; the pinned SALib
  mapping is `truncnorm` with `[lower, upper, mean, std]`.
- `TRIANGULAR` requires `mode_fraction` in the physical support; the mapping
  is `triang` with `[lower, upper, mode_fraction]`.
- `LOGNORMAL` and legacy non-uniform parameters without a typed specification
  fail closed until a bounded adapter is admitted.  Bounds are never silently
  reinterpreted as log-space or distribution moments, and values are not
  clipped to manufacture support.

Sampling and analysis use the same versioned mapping and expose its fingerprint
in analysis metadata.  A fingerprint identifies the mapping and backend, while
the plan seed remains a separate request input.  Seeded Morris/Sobol streams
are isolated; seeded FAST remains `compatibility_pending` because SALib 1.5.2
mutates process-global NumPy state.

## Morris trajectory admission

Point analysis, PCA component analysis, and elementary-effect uncertainty admit
only complete ungrouped trajectories: every step changes one parameter, every
parameter changes once, and the step and coordinates match the declared grid.
The check uses unit coordinates from the admitted uniform, truncated-normal,
or triangular sampling law. Finite values and divisible row counts alone are
insufficient. Whole valid blocks may be reordered or bootstrapped; individual
row resampling cannot preserve this design. `RankingStabilityChecker` therefore
resamples whole Morris trajectories. Its Sobol/FAST resampling is outside this
bounded repair. It validates the original Morris design before resampling and
refuses failed original runs; ranking stability under dropped or imputed runs
has no admitted selection or recovery contract.

The uniform elementary-effect helper requires explicit physical bounds and
`num_levels`; point and uncertainty effects share normalized units. Nonuniform
uncertainty remains unavailable until its coordinate contract is admitted.
Geometry does not authenticate original trajectory provenance or establish
statistical sufficiency or absence of failure-selection bias.

## Public API

- `SensitivityPlan`, `ScenarioSweep`, `AblationPlan`
- `AdversarialPlan`, `AdversarialStrategy`
- `generate_sensitivity_samples(...)`, `generate_adversarial_samples(...)`
- `analyze_sensitivity(...)`
- `SensitivityUncertaintyConfig`, `SensitivityUncertaintyBundle`
- `analyze_sobol_paired_bootstrap(...)`, `analyze_sobol_asymptotic_delta(...)`
- `analyze_morris_trajectory_bootstrap(...)`, `analyze_rqmc_replicate_ci(...)`
- `analyze_hierarchical_replicate_bootstrap(...)`
- `sobol_storage_from_blocks(...)`, `morris_storage_from_elementary_effects(...)`
- `SensitivityCoverageProfile`, `run_sobol_linear_coverage_benchmark(...)`
- `default_sobol_benchmark_cases(...)`, `default_morris_benchmark_cases(...)`
- `run_sobol_iid_coverage_benchmark(...)`, `run_morris_effect_coverage_benchmark(...)`
- `default_sensitivity_truth_suite(...)`, `sobol_sparse_interaction_truth(...)`
- `resolve_sensitivity_uncertainty_method(...)`, `apply_calibrated_multiplier(...)`
- `StressTestReport`, `Vulnerability`, `VulnerabilityType`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-10-05
- Python modules: 11
- Exports: 82
- README синхронизирован с тем, что `doe` остается upstream для search/stress flows
