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
- `pass_registry.py` — discovery/сборка passes через entry points.
- `pass_entrypoints.py` — builtin factory functions для `polisyos.scientist_governance_passes`.
- `report.py` — `GovernanceReport`, `GovernanceReportLinks`.
- `passes/`:
  - локальные: `BudgetPass`, `SchemaPass`, `PrivacyPass`, `PIICheckPass`, `QualityGatePass`, `ConfidencePass`, `EquityPass`, `RefutationPass`, `LiteratureGatePass`, `SutvaCheckPass`, `HumanReviewRequiredPass`;
  - compatibility: `SafetyPass`, `LegalPass` (из `core.governance`).
- `legal/` — deprecated compatibility re-exports на `core.governance.legal.*`.

## Важный нюанс default workflow

`run_experiment()` через `scientist.node_run_governance@1.2.0` использует workflow-ноду, где:
- поддержан typed human-gate lifecycle (`require_human_gate`, `gate_request`, `gate_decision`, escalation);
- выполняется runtime-подмножество `ValidationPipeline` по профилю (`confidence`, `equity`, `pii_check`, `refutation`, `literature_gate`, `sutva_check`, `transportability_required`, `human_review_required`);
- для DoWhy causal reports выполняется `refutation` pass (MVP=warning, STRICT=blocker);
- `literature_gate`: FAST=skip, MVP=warning, STRICT=blocker для `unsupported_by_evidence` edges;
- `sutva_check`: warning для market-wide treatment;
- `transportability_required`: Закон T для external-source `CausalEffectReport` (MVP=warning, STRICT=blocker при отсутствии `transport_result`);
- `human_review_required` в STRICT создаёт `params.human_review_request` / `params.human_review_request_ref` (через `GateRequest`) и не переводит verdict в `human_gate` автоматически;
- при blocker-issue итоговый verdict переводится в `reject` (кроме режима `human_gate`).

`preflight_checks/postflight_checks` — отдельный API; они не вызываются автоматически default DAG.

## Pass discovery

- Канонический источник passes: Python entry points group `polisyos.scientist_governance_passes`.
- В dev/test окружении без установленных entry points используется fallback factories из `pass_entrypoints.py`.

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
