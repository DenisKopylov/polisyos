# Governance Layer (`polisyos.scientist.governance`)

`governance` — слой проверок и human-gate интеграции для `scientist`.

## Роль в системе

- выполняет validation passes и формирует issue-листы;
- строит pre/post-flight решения (`GateRequest` / `GateDecision`);
- формирует `GovernanceReport` для workflow.

## Структура

- `pipeline.py` — `ValidationPipeline` (ordered passes + short-circuit по blocker).
- `preflight.py` — `preflight_checks(state, profile)`.
- `postflight.py` — `postflight_checks(state, profile)`.
- `report.py` — `GovernanceReport`, `GovernanceReportLinks`.
- `passes/`:
  - локальные: `BudgetPass`, `SchemaPass`, `PrivacyPass`, `PIICheckPass`, `QualityGatePass`, `ConfidencePass`, `EquityPass`;
  - compatibility re-export: `SafetyPass`, `LegalPass` (из `core.governance`).
- `legal/` — deprecated compatibility re-exports в `core.governance.legal.*`.

## Важный нюанс default workflow

`run_experiment()` через node `scientist.node_run_governance@1.1.0` использует только подмножество проверок (`confidence`, `equity`, `pii_check`) в зависимости от профиля.

`preflight_checks/postflight_checks` — это отдельные API, они не вызываются автоматически default DAG.

## Пример API

```python
from polisyos.scientist.governance import preflight_checks
from polisyos.core.governance.profiles import ValidationProfile

updated_state, gate_request = preflight_checks(state, ValidationProfile.strict())
```

## Связи

- `core.governance.*` — базовые контракты, профили и часть pass-ов.
- `kernel.gate_protocol` — typed human gate lifecycle.
- `nodes/builtins/governance/*` — workflow-интеграция в DAG.
