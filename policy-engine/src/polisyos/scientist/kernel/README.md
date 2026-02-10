# Kernel Layer (`polisyos.scientist.kernel`)

`kernel` — утилиты оркестрации: phase FSM, бюджеты и typed human gate protocol.

## Состав

- `fsm.py` — `Phase`, `ALLOWED_TRANSITIONS`, `KernelState`, `ReflexionGuard`.
- `guards.py` — `advance_phase()` и `require_artifacts()`.
- `budgets.py` — модели бюджетов (`ComputeBudget`, `EvidenceBudget`, `LegitimacyBudget`, `ComplexityBudget`).
- `gate_protocol.py` — `HumanGateProtocol` (создание/фиксация gate request/decision в CAS + trace events).

## Что важно знать

- FSM поддерживает не только линейный путь (`INTAKE -> ... -> ARCHIVE`), но и search/reflexion фазы.
- `engine` сам по себе не продвигает фазу автоматически; переходы применяются через state/guards на уровне нод и orchestration-логики.
- `scientist.node_run_governance` использует `HumanGateProtocol` для typed gate артефактов (`ir.gate_request`, `ir.gate_decision`).

## Связи

- `governance` — gate decisions и escalation flow.
- `engine` — хранит phase/budget значения в `ExperimentState.params`.
- `ir.governance.gate` — canonical контракты GateContext/GateRequest/GateDecision.
