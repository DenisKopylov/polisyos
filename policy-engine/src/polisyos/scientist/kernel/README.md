# Kernel Layer: FSM управление жизненным циклом

**Конечный автомат состояний с бюджетами и safety controls**

Kernel обеспечивает FSM управление фазами экспериментов с бюджетами, guards и human gates.

## Структура

```
kernel/
├── budgets.py      # Compute/Evidence/Legitimacy/Complexity budgets
├── fsm.py          # Phase enum, KernelState, transition guards
├── guards.py       # State transition validation
└── human_gate.py   # GateRequest/GateDecision для human approval
```

## Ключевые компоненты

- **FSM**: 9 фаз эксперимента (INTAKE → FRAME → PLAN → EXECUTE → DECIDE → PUBLISH)
- **Budgets**: Многоуровневые бюджеты (compute, evidence, legitimacy, complexity)
- **Guards**: Проверки переходов между состояниями
- **Human Gates**: Асинхронные gates для критических решений

## API Использование

```python
from polisyos.scientist.kernel.fsm import Phase, KernelState, advance_phase
from polisyos.scientist.kernel.budgets import ComputeBudget

# Создание бюджета
budget = ComputeBudget(max_llm_calls=5, max_sim_runs=2)

# FSM управление
kernel = KernelState(phase=Phase.FRAME)
if kernel.can_transition(Phase.PLAN):
    new_state = advance_phase(experiment_state, Phase.PLAN)
```

## Связи

- Управляет **engine** execution через phase transitions
- Контролирует **compute** через budget enforcement
- Интегрируется с **governance** для human oversight