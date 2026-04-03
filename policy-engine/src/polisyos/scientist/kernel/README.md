# Kernel (`polisyos.scientist.kernel`)

`kernel` содержит lightweight orchestration primitives Scientist: phase FSM,
budget models и typed human-gate protocol, который связывает runtime governance
с canonical gate artifacts.

## Роль в системе

- **Зависит от:** `ir.governance.gate`
- **Используется в:** `scientist.governance`, builtin governance nodes, orchestration guards
- Пакет небольшой, но критичен для phase transitions и human-review lifecycle.

## Ключевые концепции

- **Phase FSM** — допустимые переходы orchestration phases.
- **KernelState** — minimal phase-state carrier.
- **Guards** — helpers для phase advance и artifact requirements.
- **HumanGateProtocol** — typed request/decision persistence path для human review.
- **Budget models** — compute/evidence/legitimacy/complexity envelopes для orchestration.

## Public API

- `Phase`, `KernelState`, `ALLOWED_TRANSITIONS`
- `advance_phase(...)`
- `gate_protocol.py` and `budgets.py` provide the supporting human-gate and budget models

Подробности: [Reference →](../../../../docs/reference/scientist/index.md)

## Текущее состояние

- Последнее обновление: 2026-04-03
- Python modules: 5
- Public surface: imported symbols in `__init__.py` plus `gate_protocol.py`/`budgets.py`
- README расширен: раньше пакет был описан слишком минимально относительно его runtime роли
