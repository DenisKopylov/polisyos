# Governance (`polisyos.ir.governance`)

`polisyos.ir.governance` задает policy-facing контракты Trinity: постановку
задачи, спецификацию интервенций, selector expressions, schedule semantics и
gate events. После последних расширений модуль также несет temporal intervention
surface и observation-aware metadata, необходимые для causal readiness и
strategic-response workflows.

## Роль в системе

- **Зависит от:** `polisyos.ir.kernel`, `polisyos.ir.observation.contracts`
- **Используется в:** `polisyos.ir.trinity`, `polisyos.ir.linker`, `polisyos.scientist.governance`, `polisyos.core.governance`
- Governance contracts задают `Why` и `What` части Trinity; `How` остается в `polisyos.ir.model_spec`.

## Ключевые концепции

- **Problem framing** — `ProblemFrame` хранит objectives, KPI, constraints и stakeholders.
- **Policy interventions** — `PolicySpec` описывает interventions, bindings и tunable params.
- **Temporal sequencing** — `TemporalInterventionSequence` и `TemporalInterventionStep` моделируют staged policy rollouts.
- **Observation-aware metadata** — `InterventionSpec` теперь несет `identification_mode`, `strategic_response_expected` и transmission channels.
- **Selector AST** — policy targeting задается через `SelectorPredicate`, `SelectorAll`, `SelectorAny`, `SelectorNot`.
- **Gate protocol** — `GateRequest`, `GateDecision` и `GateEvent` стандартизируют governance decisions.

## Public API

| Type/Function | Description |
|---|---|
| `ProblemFrame` | Контракт постановки policy problem и success criteria |
| `PolicySpec` | Спецификация активных interventions и их bindings |
| `InterventionSpec` | Один intervention с policy metadata, targeting и measurement expectations |
| `TemporalInterventionSequence` | Упорядоченная последовательность temporal intervention steps |
| `ScheduleSpec` | Step-based activation window для interventions |
| `GateRequest`, `GateDecision`, `GateEvent` | Typed governance gate protocol |
| `ValidationIssue`, `ValidationReport` | Validation diagnostics для governance payloads |

Full reference: [docs/reference/ir/](../../../../docs/reference/ir/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Files: 8 Python files
- Exports: package facade from 6 governance modules
- Recent delta: `policy_spec.py` расширен temporal intervention sequence и observation/strategic-response metadata для interventions
