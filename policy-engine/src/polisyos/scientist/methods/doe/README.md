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

- Последнее обновление: 2026-04-03
- Python modules: 10
- Exports: 82
- README синхронизирован с тем, что `doe` остается upstream для search/stress flows
