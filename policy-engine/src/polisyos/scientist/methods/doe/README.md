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
without deriving them from issue lists.

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
bounded repair; those methods return `unsupported` with the requested bootstrap
and input-run denominators before attempting a replicate. Morris reports every
replicate outcome and marks success-only ranking summaries `limited` when any
replicate fails. It validates the original Morris design before resampling and
refuses failed original runs; ranking stability under dropped or imputed runs
has no admitted selection or recovery contract.

The uniform elementary-effect helper requires explicit physical bounds and
`num_levels`; point and uncertainty effects share normalized units. Nonuniform
uncertainty remains unavailable until its coordinate contract is admitted.
Geometry does not authenticate original trajectory provenance or establish
statistical sufficiency or absence of failure-selection bias.

## Ordered experiment and consumer readback

Sobol plans now require `input_law="independent"` and an explicit seed before
sampling. This declares a product parameter experiment; it does not establish
independence of a population source. Analysis reconciles the complete Saltelli
blocks with the canonical seeded SALib sampler, including block multiplicity and
the A/AB/BA/B role order inside each block. Whole blocks with their paired outputs
may be permuted; this preserves the point estimands while changing the actual
ordered design/analysis content IDs. Missing/duplicated blocks, changed interior
roles, correlated, or differently transformed rows are rejected before estimating
indices. A prior receipt cannot bind the new order merely because its numerical
indices agree.

The native interaction oracle uses independent uniform inputs and
`y=x+z+2*x*z`: first-order indices are `12/25` each, the interaction is `1/25`,
and total-order indices are `13/25` each. Its numerical tolerance is declared
separately from the analytic truth. It exercises sampler, analyzer and interaction
ranking; list/tuple shape alone does not verify those quantities.

The autotune `SensitivityBridge` uses this same producer for distribution,
seed, and budget admission. Passing its configured `store` persists a
`doe_sensitivity_analysis` artifact containing the complete plan, ordered
samples, all outcomes (nonfinite failures have explicit tags), denominator, and result.
`_receipt.py` owns this internal writer/loader. The existing search
`SensitivityAwareCandidateGenerator.from_artifact` checks CAS kind/schema and
integrity, reproduces the native analysis, and carries exact design/analysis
IDs and the typed reference through both single and batch candidate paths.
A content-valid receipt with a fabricated index is rejected on readback.

Effects declare `unit_coordinate_full_range` for Morris and `variance_fraction`
for Sobol/FAST; parameter units remain explicit, with `unspecified` preserved
as a limitation. Artifacts are exploratory parameter experiments. Evaluator
provenance, population source-law validity, causal effects, and production
history remain `not_established`; numerical replay does not create authority.

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

- Последнее обновление: 2026-10-06
- Python modules: 12
- Exports: 82
- README синхронизирован с тем, что `doe` остается upstream для search/stress flows
