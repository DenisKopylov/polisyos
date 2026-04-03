# DoE (`polisyos.scientist.doe`)

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
- **StressTestReport** — итоговая форма публикации robustness issues.

## Public API

- `SensitivityPlan`, `ScenarioSweep`, `AblationPlan`
- `AdversarialPlan`, `AdversarialStrategy`
- `generate_sensitivity_samples(...)`, `generate_adversarial_samples(...)`
- `analyze_sensitivity(...)`
- `StressTestReport`, `Vulnerability`, `VulnerabilityType`

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 8
- Exports: 16
- README синхронизирован с тем, что `doe` остается upstream для search/stress flows
