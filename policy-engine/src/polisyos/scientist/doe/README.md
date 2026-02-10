# DoE Layer (`polisyos.scientist.doe`)

`doe` — дизайн и анализ экспериментальных планов (sensitivity/adversarial) для Scientist.

## Что внутри

- `designs.py`
  - `ScenarioSweep`, `AblationPlan`
  - `SensitivityPlan`, `ParameterSpec`, `SensitivityMethod`
  - `AdversarialPlan`, `AdversarialStrategy`
  - `SensitivityResult`, `RunFailurePolicy`
- `sampling.py`
  - `generate_sensitivity_samples(plan)`
  - `generate_adversarial_samples(plan)`
- `analysis.py`
  - `analyze_sensitivity(plan, samples, outputs)`
- `stress_report.py`
  - `StressTestReport`, `Vulnerability`, `VulnerabilityType`

## Практические нюансы

- `SensitivityPlan` требует `parameter_specs` (или legacy `parameters`), валидирует лимит ожидаемых запусков.
- `generate_sensitivity_samples` использует SALib (MORRIS/SOBOL/FAST).
- `analyze_sensitivity` умеет обрабатывать частично проваленные запуски через `RunFailurePolicy`.
- `AdversarialPlan` используется слоем `search.adversarial` для stress-test loop.

## Где используется

- CLI `polisyos scientist sensitivity run` (`core/components/_cli_scientist.py`).
- CLI `polisyos scientist stress-test` (через `search.adversarial.run_stress_test`).
