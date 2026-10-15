# Kernel (`polisyos.scientist.orchestration.kernel`)

`kernel` contains lightweight Scientist orchestration primitives: a phase FSM,
budget models, and a typed human-gate protocol that connects runtime governance
to canonical gate artifacts.

## Role in the system

- **Depends on:** `ir.governance.gate`
- **Used by:** `scientist.governance`, built-in governance nodes, and orchestration guards
- The package is small but critical to phase transitions and the human-review lifecycle.

## Key concepts

- **Phase FSM** — allowed orchestration-phase transitions.
- **KernelState** — minimal phase-state carrier.
- **Guards** — helpers for phase advancement and artifact requirements.
- **HumanGateProtocol** — typed request/decision persistence path for human review.
- **Budget models** — compute/evidence/legitimacy/complexity envelopes for orchestration.

## Public API

- `Phase`, `KernelState`, `ALLOWED_TRANSITIONS`
- `advance_phase(...)`
- `gate_protocol.py` and `budgets.py` provide the supporting human-gate and budget models

Details: [Reference →](../../../../../docs/reference/scientist/index.md)

## Current state

- Last updated: 2026-10-14
- Python modules: 5 direct `.py` modules in this package.
- Public surface: imported symbols in `__init__.py` plus `gate_protocol.py`/`budgets.py`
- The README was expanded because the previous description understated the package's runtime role.
