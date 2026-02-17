# Governance Layer (`polisyos.scientist.governance`)

`governance` — слой проверок и human-gate интеграции для Scientist.

## Роль в системе

- выполняет validation passes и собирает issue-листы;
- формирует pre/post-flight решения (`GateRequest` / `GateDecision`) в API-режиме;
- формирует `GovernanceReport` для workflow-ноды `run_governance`.

## Структура

- `pipeline.py` — `ValidationPipeline` (ordered passes + short-circuit по blocker).
- `preflight.py` — `preflight_checks(state, profile)`.
- `postflight.py` — `postflight_checks(state, profile)`.
- `report.py` — `GovernanceReport`, `GovernanceReportLinks`.
- `passes/`:
  - локальные: `BudgetPass`, `SchemaPass`, `PrivacyPass`, `PIICheckPass`, `QualityGatePass`, `ConfidencePass`, `EquityPass`;
  - compatibility: `SafetyPass`, `LegalPass` (из `core.governance`).
- `legal/` — deprecated compatibility re-exports на `core.governance.legal.*`.

## Важный нюанс default workflow

`run_experiment()` через `scientist.node_run_governance@1.1.0` использует workflow-ноду, где:
- поддержан typed human-gate lifecycle (`require_human_gate`, `gate_request`, `gate_decision`, escalation);
- выполняется подмножество пассов по профилю (`confidence`, `equity`, `pii_check`);
- при blocker-issue итоговый verdict переводится в `reject` (кроме режима `human_gate`).

`preflight_checks/postflight_checks` — отдельный API; они не вызываются автоматически default DAG.

## Data-plane gate

До дорогого execute-этапа в workflow работает `scientist.node_run_data_plane_gate`, который использует governance passes `QualityGatePass` + `PIICheckPass` и блокирует запуск при blocker-нарушениях.

## Пример API

```python
from polisyos.scientist.governance import preflight_checks
from polisyos.core.governance.profiles import ValidationProfile

updated_state, gate_request = preflight_checks(state, ValidationProfile.strict())
```

## Связи

- `core.governance.*` — базовые контракты/профили/часть пассов.
- `kernel.gate_protocol` — typed gate request/decision lifecycle.
- `nodes/builtins/governance/*` — интеграция governance в DAG.
